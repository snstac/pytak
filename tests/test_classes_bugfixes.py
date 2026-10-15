#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regression tests for bugs fixed in pytak.classes."""

import asyncio
import os
import zipfile
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

import pytak
from pytak import classes as pytak_classes
from pytak.client_functions import _retryable_transport_error

try:
    import takproto  # type: ignore
except ImportError:  # pragma: no cover
    takproto = None


def _stream_reader(data: bytes, eof: bool = True) -> asyncio.StreamReader:
    """Return a real StreamReader pre-fed with *data*."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    if eof:
        reader.feed_eof()
    return reader


# --- Bug 1: peer EOF must surface as a retryable error ----------------------


@pytest.mark.asyncio
async def test_readcot_raises_retryable_error_on_peer_eof():
    reader = _stream_reader(b'<event uid="a"></event><event uid="partial">')
    worker = pytak.RXWorker(asyncio.Queue(), {}, reader)

    assert await worker.readcot() == b'<event uid="a"></event>'
    with pytest.raises(ConnectionResetError) as excinfo:
        await worker.readcot()
    assert _retryable_transport_error(excinfo.value)
    assert isinstance(excinfo.value.__cause__, asyncio.IncompleteReadError)


@pytest.mark.asyncio
async def test_rxworker_run_terminates_on_peer_eof():
    queue = asyncio.Queue()
    reader = _stream_reader(b'<event uid="a"></event>')
    worker = pytak.RXWorker(queue, {}, reader)

    with pytest.raises(ConnectionResetError):
        await asyncio.wait_for(worker.run(), timeout=1)
    assert queue.get_nowait() == b'<event uid="a"></event>'


@pytest.mark.asyncio
async def test_discard_rxworker_run_terminates_on_peer_eof():
    queue = asyncio.Queue()
    reader = _stream_reader(b'<event uid="a"></event>')
    worker = pytak.DiscardRXWorker(queue, {}, reader)

    with pytest.raises(ConnectionResetError):
        await asyncio.wait_for(worker.run(), timeout=1)
    assert queue.empty()


# --- Bug 2: events larger than the StreamReader limit ------------------------


@pytest.mark.asyncio
async def test_readcot_reads_event_larger_than_stream_limit():
    big = (
        b'<event uid="big"><detail><remarks>'
        + b"x" * 200000
        + b"</remarks></detail></event>"
    )
    nxt = b'<event uid="next"></event>'
    reader = _stream_reader(big + nxt)
    worker = pytak.RXWorker(asyncio.Queue(), {}, reader)

    assert await worker.readcot() == big
    assert await worker.readcot() == nxt


@pytest.mark.asyncio
async def test_readcot_rejects_event_over_total_cap():
    reader = _stream_reader(b"<event>" + b"x" * 5000, eof=False)
    reader._limit = 1024  # pylint: disable=protected-access
    worker = pytak.RXWorker(asyncio.Queue(), {}, reader)

    with mock.patch.object(pytak_classes, "_MAX_COT_EVENT_SIZE", 2048):
        with pytest.raises(pytak_classes._CoTEventTooLargeError) as excinfo:
            await asyncio.wait_for(worker.readcot(), timeout=1)
    # Retryable: the stream is desynchronised, so reconnecting is the recovery.
    assert _retryable_transport_error(excinfo.value)
    assert isinstance(excinfo.value, ValueError)


# --- Bug 3: XML input with TAK_PROTO>0 must not be dropped -------------------


@pytest.mark.skipif(takproto is None, reason="takproto not installed")
@pytest.mark.asyncio
async def test_readcot_keeps_xml_when_tak_proto_enabled():
    event = b'<event uid="a" type="a-f-G"></event>'
    reader = _stream_reader(event)
    worker = pytak.RXWorker(asyncio.Queue(), {"TAK_PROTO": "1"}, reader)
    assert worker.use_protobuf

    assert await worker.readcot() == event


# --- Bug 4: Marti RX must not lose a poll window on failure ------------------


class _Resp:
    def __init__(self, status, text=""):
        self.status = status
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_marti_rx_keeps_window_after_failed_poll():
    session = mock.MagicMock()
    session.get.side_effect = OSError("boom")
    worker = pytak.MartiRXWorker(
        asyncio.Queue(), {}, session, "https://takserver.example.com"
    )
    earlier = datetime.now(timezone.utc) - timedelta(seconds=30)
    worker._last_poll = earlier  # pylint: disable=protected-access

    await worker.run_once()
    assert worker._last_poll == earlier  # pylint: disable=protected-access

    session.get.side_effect = None
    session.get.return_value = _Resp(503)
    await worker.run_once()
    assert worker._last_poll == earlier  # pylint: disable=protected-access

    session.get.return_value = _Resp(200, '<event uid="a"></event>')
    await worker.run_once()
    params = session.get.call_args[1]["params"]
    assert params["start"] == earlier.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    assert worker._last_poll > earlier  # pylint: disable=protected-access


# --- Bug 5: boolean config strings -------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("No", False),
        ("off", False),
        (False, False),
        (0, False),
        ("1", True),
        ("true", True),
        ("YES", True),
        (" on ", True),
        (True, True),
        (1, True),
        ("2", True),
        ("00", False),
    ],
)
def test_is_true(value, expected):
    assert pytak_classes._is_true(value) is expected


@pytest.mark.asyncio
async def test_fts_compat_false_string_does_not_sleep():
    worker = pytak.Worker(asyncio.Queue(), {"FTS_COMPAT": "0"})
    with mock.patch.object(pytak_classes.asyncio, "sleep") as sleep:
        await worker.fts_compat()
    sleep.assert_not_called()


def test_worker_debug_false_string_does_not_enable_debug():
    handler = mock.MagicMock()
    with mock.patch.object(pytak.Worker._logger, "handlers", [handler]):
        pytak.Worker(asyncio.Queue(), {"DEBUG": "0"})
    handler.setLevel.assert_not_called()


def test_clitool_debug_false_string_does_not_enable_debug():
    from configparser import ConfigParser

    cfg = ConfigParser()
    cfg.add_section("pytak")
    cfg["pytak"]["DEBUG"] = "0"
    handler = mock.MagicMock()
    with mock.patch.object(pytak.CLITool._logger, "handlers", [handler]):
        pytak.CLITool(cfg["pytak"])
    handler.setLevel.assert_not_called()


@pytest.mark.asyncio
async def test_clitool_no_hello_false_string_sends_hello():
    clitool = pytak.CLITool({"PYTAK_NO_HELLO": "false"})
    clitool.hello_event = mock.MagicMock(side_effect=_noop)
    clitool.add_task(_DoneWorker())
    await clitool.run()
    clitool.hello_event.assert_called_once()


async def _noop():
    return None


class _DoneWorker:
    """Minimal worker whose run() returns immediately."""

    async def run(self):
        return None

    async def close(self):
        return None


# --- Bug 6: dotted directory names in TAKDataPackage output path -------------


def test_create_package_dotted_directory(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("hello")
    outdir = tmp_path / "v1.2" / "out"
    outdir.mkdir(parents=True)

    pkg = pytak.TAKDataPackage("mission")
    pkg.add_file(str(src))
    pkg.create_package(str(outdir / "mission"))

    expected = outdir / "mission.zip"
    assert expected.exists()
    assert not (tmp_path / "v1.zip").exists()
    with zipfile.ZipFile(str(expected)) as zf:
        assert "a.txt" in zf.namelist()


def test_create_package_replaces_file_extension(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("hello")
    outdir = tmp_path / "v1.2"
    outdir.mkdir()

    pkg = pytak.TAKDataPackage("mission")
    pkg.add_file(str(src))
    pkg.create_package(str(outdir / "mission.zip"), use_dpk_extension=True)
    assert os.path.exists(str(outdir / "mission.dpk"))
