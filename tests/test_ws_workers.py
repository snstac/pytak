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
# Constants
# ---------------------------------------------------------------------------


def test_ws_constants():
    assert pytak.DEFAULT_WS_PATH == "/takproto/1"
    assert pytak.DEFAULT_WS_PORT == 8443
