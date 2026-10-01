#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for WSTXWorker, WSRXWorker, and ws_factory."""

import asyncio
import enum
from unittest import mock

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(mock.MagicMock):
        def __call__(self, *args, **kwargs):
            super().__call__(*args, **kwargs)
            ret = self.return_value
            async def _coro():
                return ret
            return _coro()

import pytest

import pytak
from pytak.classes import WSTXWorker, WSRXWorker, _make_workers
import contextlib
import logging


SAMPLE_COT = (
    b'<?xml version="1.0"?>'
    b'<event version="2.0" uid="WS-TEST" type="a-f-G-U-C" '
    b'time="2024-01-01T00:00:00Z" start="2024-01-01T00:00:00Z" '
    b'stale="2024-01-01T00:05:00Z" how="m-g">'
    b'<point lat="37.7749" lon="-122.4194" hae="0" ce="9999999" le="9999999"/>'
    b"</event>"
)

SAMPLE_PROTO_BYTES = b"\xbf\x01\x00"  # minimal fake proto frame


# ---------------------------------------------------------------------------
# WSTXWorker
# ---------------------------------------------------------------------------



@contextlib.contextmanager
def capture_from(logger, caplog, level=logging.WARNING):
    """Capture records from a logger that does not propagate.

    pytak's _setup_logger() sets `propagate = False` (classes.py), so records
    never reach the root logger where pytest's caplog handler lives. Using
    `caplog.at_level(..., logger=...)` only changes the LEVEL on that logger --
    it does not attach the handler to it -- so nothing is captured and the
    assertion sees zero records.

    That this passed on Python 3.10+ and failed on 3.7-3.9 was pytest-version
    luck, not a language difference. Attaching caplog's own handler directly to
    the logger works the same way on every supported version.
    """
    handler = caplog.handler
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(level)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


@pytest.mark.asyncio
async def test_ws_tx_worker_sends_bytes():
    """WSTXWorker.handle_data() should call send_bytes on the WebSocket."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock()

    worker = WSTXWorker(queue, {}, mock_ws)

    with mock.patch("pytak.classes.takproto", None):
        await worker.handle_data(SAMPLE_COT)

    mock_ws.send_bytes.assert_called_once_with(SAMPLE_COT)


@pytest.mark.asyncio
async def test_ws_tx_worker_skips_empty():
    """WSTXWorker.handle_data() should not call send_bytes for empty data."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock()

    worker = WSTXWorker(queue, {}, mock_ws)
    await worker.handle_data(b"")
    mock_ws.send_bytes.assert_not_called()

    await worker.handle_data(None)
    mock_ws.send_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_ws_tx_worker_encodes_protobuf_when_available():
    """WSTXWorker.handle_data() should encode CoT as Protobuf when takproto is present."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock()

    fake_proto = b"\xbf\x01\x99"
    mock_takproto = mock.MagicMock()
    mock_takproto.xml2proto.return_value = fake_proto
    mock_takproto.TAKProtoVer.STREAM = "STREAM"

    worker = WSTXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.handle_data(SAMPLE_COT)

    mock_takproto.xml2proto.assert_called_once_with(SAMPLE_COT, "STREAM")
    mock_ws.send_bytes.assert_called_once_with(fake_proto)


@pytest.mark.asyncio
async def test_ws_tx_worker_falls_back_on_proto_error():
    """WSTXWorker.handle_data() should send raw bytes if Protobuf encoding fails."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock()

    mock_takproto = mock.MagicMock()
    mock_takproto.xml2proto.side_effect = Exception("bad xml")
    mock_takproto.TAKProtoVer.STREAM = "STREAM"

    worker = WSTXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.handle_data(SAMPLE_COT)

    # Should fall back to raw bytes
    mock_ws.send_bytes.assert_called_once_with(SAMPLE_COT)


@pytest.mark.asyncio
async def test_ws_tx_worker_warns_once_when_takproto_missing(caplog):
    """WSTXWorker should warn that raw XML sent to a TAK Protocol endpoint is dropped."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock()

    cot_url = f"wss://takserver.example.com:8443{pytak.DEFAULT_WS_PATH}"
    worker = WSTXWorker(queue, {"COT_URL": cot_url}, mock_ws)

    with mock.patch("pytak.classes.takproto", None):
        with capture_from(worker._logger, caplog):
            await worker.handle_data(SAMPLE_COT)
            await worker.handle_data(SAMPLE_COT)

    warnings = [r for r in caplog.records if "takproto" in r.getMessage()]
    assert len(warnings) == 1
    assert cot_url in warnings[0].getMessage()
    assert mock_ws.send_bytes.await_count == 2


@pytest.mark.asyncio
async def test_ws_tx_worker_does_not_warn_for_non_takproto_endpoint(caplog):
    """No warning for a plain WebSocket server that accepts raw CoT XML."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock()

    worker = WSTXWorker(queue, {"COT_URL": "ws://example.com/cot"}, mock_ws)

    with mock.patch("pytak.classes.takproto", None):
        with capture_from(worker._logger, caplog):
            await worker.handle_data(SAMPLE_COT)

    assert not [r for r in caplog.records if "takproto" in r.getMessage()]


# ---------------------------------------------------------------------------
# WSRXWorker
# ---------------------------------------------------------------------------


def _make_ws_msg(msg_type, data=None):
    """Build a minimal mock aiohttp WSMessage."""
    msg = mock.MagicMock()
    msg.type = msg_type
    msg.data = data
    return msg


@pytest.mark.asyncio
async def test_ws_rx_worker_enqueues_decoded_cot():
    """WSRXWorker.run_once() should decode a binary frame and put CoT on the queue."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()

    fake_cot = b"<event/>"
    mock_ws.receive = AsyncMock(return_value=_make_ws_msg("BINARY", SAMPLE_PROTO_BYTES))

    mock_aiohttp = mock.MagicMock()
    mock_aiohttp.WSMsgType.BINARY = "BINARY"
    mock_aiohttp.WSMsgType.CLOSE = "CLOSE"
    mock_aiohttp.WSMsgType.CLOSED = "CLOSED"
    mock_aiohttp.WSMsgType.ERROR = "ERROR"

    mock_takproto = mock.MagicMock()
    mock_takproto.parse_proto.return_value = fake_cot

    worker = WSRXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes._aiohttp", mock_aiohttp), \
         mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.run_once()

    assert queue.qsize() == 1
    assert await queue.get() == fake_cot


@pytest.mark.asyncio
async def test_ws_rx_worker_skips_failed_proto_decode():
    """WSRXWorker.run_once() should not enqueue if Protobuf decode returns -1."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.receive = AsyncMock(return_value=_make_ws_msg("BINARY", SAMPLE_PROTO_BYTES))

    mock_aiohttp = mock.MagicMock()
    mock_aiohttp.WSMsgType.BINARY = "BINARY"
    mock_aiohttp.WSMsgType.CLOSE = "CLOSE"
    mock_aiohttp.WSMsgType.CLOSED = "CLOSED"
    mock_aiohttp.WSMsgType.ERROR = "ERROR"

    mock_takproto = mock.MagicMock()
    mock_takproto.parse_proto.return_value = -1

    worker = WSRXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes._aiohttp", mock_aiohttp), \
         mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.run_once()

    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_ws_rx_worker_handles_close():
    """WSRXWorker.run_once() should raise when server closes the socket."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.receive = AsyncMock(return_value=_make_ws_msg("CLOSE"))

    mock_aiohttp = mock.MagicMock()
    mock_aiohttp.WSMsgType.BINARY = "BINARY"
    mock_aiohttp.WSMsgType.CLOSE = "CLOSE"
    mock_aiohttp.WSMsgType.CLOSED = "CLOSED"
    mock_aiohttp.WSMsgType.ERROR = "ERROR"

    worker = WSRXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes._aiohttp", mock_aiohttp):
        with pytest.raises(ConnectionAbortedError, match="WebSocket closed by server"):
            await worker.run_once()

    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_ws_tx_worker_raises_on_send_error():
    """WSTXWorker.handle_data() should raise on websocket send failures."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    mock_ws.send_bytes = AsyncMock(side_effect=RuntimeError("socket closed"))

    worker = WSTXWorker(queue, {}, mock_ws)

    with mock.patch("pytak.classes.takproto", None):
        with pytest.raises(ConnectionError, match="WebSocket TX send failed"):
            await worker.handle_data(SAMPLE_COT)


@pytest.mark.asyncio
async def test_ws_rx_worker_enqueues_raw_bytes_without_takproto():
    """WSRXWorker.run_once() should enqueue raw frame bytes when takproto is absent."""
    queue = asyncio.Queue()
    mock_ws = mock.MagicMock()
    raw = b"<event/>"
    mock_ws.receive = AsyncMock(return_value=_make_ws_msg("BINARY", raw))

    mock_aiohttp = mock.MagicMock()
    mock_aiohttp.WSMsgType.BINARY = "BINARY"
    mock_aiohttp.WSMsgType.CLOSE = "CLOSE"
    mock_aiohttp.WSMsgType.CLOSED = "CLOSED"
    mock_aiohttp.WSMsgType.ERROR = "ERROR"

    worker = WSRXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes._aiohttp", mock_aiohttp), \
         mock.patch("pytak.classes.takproto", None):
        await worker.run_once()

    assert queue.qsize() == 1
    assert await queue.get() == raw


# ---------------------------------------------------------------------------
# _make_workers dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_workers_ws_scheme():
    """_make_workers should return WS workers for ws:// scheme."""
    from configparser import ConfigParser

    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "ws://takserver.example.com/takproto/1")
    cfg = config["test"]

    mock_tx = mock.MagicMock(spec=WSTXWorker)
    mock_rx = mock.MagicMock(spec=WSRXWorker)

    with mock.patch("pytak.ws_factory", new=AsyncMock(return_value=(mock_tx, mock_rx))) as mock_factory:
        tx_q, rx_q = asyncio.Queue(), asyncio.Queue()
        write_worker, read_worker = await _make_workers(tx_q, rx_q, cfg)
        mock_factory.assert_called_once_with(tx_q, rx_q, cfg)
        assert write_worker is mock_tx
        assert read_worker is mock_rx


@pytest.mark.asyncio
async def test_make_workers_wss_scheme():
    """_make_workers should return WS workers for wss:// scheme."""
    from configparser import ConfigParser

    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "wss://takserver.example.com/takproto/1")
    cfg = config["test"]

    mock_tx = mock.MagicMock(spec=WSTXWorker)
    mock_rx = mock.MagicMock(spec=WSRXWorker)

    with mock.patch("pytak.ws_factory", new=AsyncMock(return_value=(mock_tx, mock_rx))) as mock_factory:
        tx_q, rx_q = asyncio.Queue(), asyncio.Queue()
        write_worker, read_worker = await _make_workers(tx_q, rx_q, cfg)
        mock_factory.assert_called_once_with(tx_q, rx_q, cfg)


# ---------------------------------------------------------------------------
# ws_factory 403 handling (issue #99)
# ---------------------------------------------------------------------------


def _wss_config(cert_path):
    from configparser import ConfigParser

    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "wss://takserver.example.com:8443/takproto/1")
    config.set("test", "PYTAK_TLS_CLIENT_CERT", str(cert_path))
    return config["test"]


async def _run_ws_factory_with_403(cfg):
    import aiohttp

    exc = aiohttp.WSServerHandshakeError(
        mock.MagicMock(), (), status=403, message="Forbidden"
    )
    with mock.patch("pytak.client_functions.get_ssl_ctx", return_value=mock.MagicMock()):
        with mock.patch(
            "aiohttp.ClientSession.ws_connect", new=AsyncMock(side_effect=exc)
        ):
            await pytak.ws_factory(asyncio.Queue(), asyncio.Queue(), cfg)


@pytest.mark.asyncio
async def test_ws_factory_403_keeps_user_provided_cert(tmp_path, monkeypatch):
    """A 403 must never delete a user-managed PYTAK_TLS_CLIENT_CERT (#99)."""
    import aiohttp

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    user_pem = tmp_path / "client.pem"
    user_pem.write_text("user managed cert")

    with pytest.raises(aiohttp.WSServerHandshakeError):
        await _run_ws_factory_with_403(_wss_config(user_pem))

    assert user_pem.read_text() == "user managed cert"


@pytest.mark.asyncio
async def test_ws_factory_403_keeps_user_p12_outside_cache(tmp_path, monkeypatch):
    """A user .p12 outside ~/.pytak/certs is not a cache file (#99)."""
    import aiohttp

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    user_p12 = tmp_path / "mine.p12"
    user_p12.write_text("user p12")
    user_pass = tmp_path / "mine.pass"
    user_pass.write_text("secret")

    with pytest.raises(aiohttp.WSServerHandshakeError):
        await _run_ws_factory_with_403(_wss_config(user_p12))

    assert user_p12.exists()
    assert user_pass.exists()


@pytest.mark.asyncio
async def test_ws_factory_403_clears_enrollment_cache_p12(tmp_path, monkeypatch):
    """A 403 still clears the stale p12 that pytak itself cached."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cache_dir = tmp_path / ".pytak" / "certs"
    cache_dir.mkdir(parents=True)
    cached_p12 = cache_dir / "abc123.p12"
    cached_pass = cache_dir / "abc123.pass"
    cached_p12.write_text("cached")
    cached_pass.write_text("pw")

    with pytest.raises(PermissionError):
        await _run_ws_factory_with_403(_wss_config(cached_p12))

    assert not cached_p12.exists()
    assert not cached_pass.exists()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_ws_constants():
    assert pytak.DEFAULT_WS_PATH == "/takproto/1"
    assert pytak.DEFAULT_WS_PORT == 8443
