#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for pytak CLI workers and helpers."""

import asyncio
import io
from argparse import Namespace
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

from pytak.cli_main import (
    FileWorker,
    StdinWorker,
    StdoutWorker,
    _frame_cot_xml_events,
    _get_tx_source,
    _resolve_tak_url,
)


SAMPLE_COT = (
    b'<event version="2.0" uid="TEST" type="a-f-G" '
    b'time="2024-01-01T00:00:00Z" start="2024-01-01T00:00:00Z" '
    b'stale="2024-01-01T00:05:00Z" how="m-g">'
    b'<point lat="37.0" lon="-122.0" hae="0" ce="9999999" le="9999999"/>'
    b"</event>"
)


# ---------------------------------------------------------------------------
# StdoutWorker
# ---------------------------------------------------------------------------


def _mock_stdout():
    """Return a mock stdout with a writable BytesIO buffer."""
    buf = io.BytesIO()
    mock_stdout = mock.MagicMock()
    mock_stdout.buffer = buf
    return mock_stdout, buf


@pytest.mark.asyncio
async def test_stdout_worker_writes_to_stdout():
    """StdoutWorker.handle_data() should write CoT bytes to stdout."""
    queue = asyncio.Queue()
    worker = StdoutWorker(queue, {})

    mock_stdout, buf = _mock_stdout()
    with mock.patch("pytak.cli_main.sys") as mock_sys:
        mock_sys.stdout = mock_stdout
        await worker.handle_data(SAMPLE_COT)

    output = buf.getvalue()
    assert b"<event" in output
    assert b"TEST" in output
    assert output.endswith(b"\n")


@pytest.mark.asyncio
async def test_stdout_worker_adds_newline():
    """StdoutWorker.handle_data() appends a newline if not already present."""
    queue = asyncio.Queue()
    worker = StdoutWorker(queue, {})

    mock_stdout, buf = _mock_stdout()
    with mock.patch("pytak.cli_main.sys") as mock_sys:
        mock_sys.stdout = mock_stdout
        await worker.handle_data(b"<event/>")

    assert buf.getvalue().endswith(b"\n")


@pytest.mark.asyncio
async def test_stdout_worker_no_double_newline():
    """StdoutWorker.handle_data() should not add a newline if already present."""
    queue = asyncio.Queue()
    worker = StdoutWorker(queue, {})

    mock_stdout, buf = _mock_stdout()
    with mock.patch("pytak.cli_main.sys") as mock_sys:
        mock_sys.stdout = mock_stdout
        await worker.handle_data(b"<event/>\n")

    out = buf.getvalue()
    # ET.tostring may normalise <event/> → <event /> depending on Python version;
    # the important invariant is exactly one trailing newline.
    assert out.endswith(b"\n")
    assert out.count(b"\n") == 1


@pytest.mark.asyncio
async def test_stdout_worker_handles_broken_pipe():
    """StdoutWorker.handle_data() should not raise on BrokenPipeError."""
    queue = asyncio.Queue()
    worker = StdoutWorker(queue, {})

    mock_buf = mock.MagicMock()
    mock_buf.write.side_effect = BrokenPipeError
    mock_stdout = mock.MagicMock()
    mock_stdout.buffer = mock_buf
    with mock.patch("pytak.cli_main.sys") as mock_sys:
        mock_sys.stdout = mock_stdout
        await worker.handle_data(SAMPLE_COT)  # should not raise


# ---------------------------------------------------------------------------
# StdinWorker (framing logic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stdin_worker_frames_single_event():
    """StdinWorker should put a single complete CoT event on the queue."""
    queue = asyncio.Queue()
    worker = StdinWorker(queue, {})

    # Simulate connect_read_pipe + StreamReader providing one event then EOF
    async def fake_run(_=-1):
        await worker.handle_data(SAMPLE_COT)

    with mock.patch.object(worker, "run", fake_run):
        await worker.run()

    assert queue.qsize() == 1
    assert await queue.get() == SAMPLE_COT


@pytest.mark.asyncio
async def test_stdin_worker_frames_multiple_events():
    """StdinWorker.handle_data() should enqueue each complete CoT event."""
    queue = asyncio.Queue()
    worker = StdinWorker(queue, {})

    await worker.handle_data(SAMPLE_COT)
    await worker.handle_data(SAMPLE_COT)

    assert queue.qsize() == 2


def test_frame_cot_xml_events_with_remainder():
    """Framing helper should return complete events and keep trailing bytes."""
    payload = SAMPLE_COT + SAMPLE_COT + b"<event partial"

    events, remainder = _frame_cot_xml_events(payload)

    assert len(events) == 2
    assert events[0] == SAMPLE_COT
    assert events[1] == SAMPLE_COT
    assert remainder == b"<event partial"


@pytest.mark.asyncio
async def test_file_worker_frames_multiple_events(tmp_path):
    """FileWorker should enqueue all complete events found in a file."""
    queue = asyncio.Queue()
    cot_file = tmp_path / "events.xml"
    cot_file.write_bytes(SAMPLE_COT + SAMPLE_COT)

    worker = FileWorker(queue, {}, str(cot_file))
    await worker.run()

    assert queue.qsize() == 2
    assert await queue.get() == SAMPLE_COT
    assert await queue.get() == SAMPLE_COT


def test_get_tx_source_modes():
    """TX source selector should pick stdin/file/none based on inputs."""
    assert _get_tx_source(Namespace(rx_only=False, tx_file=None), False) == "stdin"
    assert (
        _get_tx_source(Namespace(rx_only=False, tx_file="events.xml"), True)
        == "file"
    )
    assert (
        _get_tx_source(Namespace(rx_only=True, tx_file="events.xml"), False)
        == "none"
    )


def test_get_tx_source_raises_on_ambiguous_input():
    """TX source selector should reject simultaneous stdin pipe and --tx-file."""
    with pytest.raises(ValueError):
        _get_tx_source(Namespace(rx_only=False, tx_file="events.xml"), False)


# ---------------------------------------------------------------------------
# _resolve_tak_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_tak_url_sets_wss_url():
    """_resolve_tak_url should convert tls:// in resolved config to wss://."""
    tak_url = (
        "tak://com.atakmap.app/enroll?host=takserver.example.com&"
        "username=user&token=tok"
    )

    fake_resolved = {
        "COT_URL": "tls://takserver.example.com:8089",
        "PYTAK_TLS_CLIENT_CERT": "/tmp/fake.p12",
        "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE": "secret",
        "PYTAK_TLS_DONT_VERIFY": "1",
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": "1",
    }

    cfg = {}
    with mock.patch(
        "pytak.resolve_tak_url", new=AsyncMock(return_value=fake_resolved)
    ):
        await _resolve_tak_url(tak_url, cfg)

    assert cfg["COT_URL"].startswith("wss://takserver.example.com")
    assert "/takproto/1" in cfg["COT_URL"]
    assert cfg["PYTAK_TLS_CLIENT_CERT"] == "/tmp/fake.p12"


@pytest.mark.asyncio
async def test_resolve_tak_url_exits_on_import_error(capsys):
    """_resolve_tak_url should exit with message if aiohttp is missing."""
    tak_url = (
        "tak://com.atakmap.app/enroll?host=takserver.example.com&"
        "username=u&token=t"
    )

    with mock.patch(
        "pytak.resolve_tak_url",
        new=AsyncMock(side_effect=ImportError("no aiohttp")),
    ):
        with pytest.raises(SystemExit):
            await _resolve_tak_url(tak_url, {})

    captured = capsys.readouterr()
    assert "pip install" in captured.err


# ---------------------------------------------------------------------------
# CLI exports
# ---------------------------------------------------------------------------


def test_cli_workers_exported():
    """StdinWorker and StdoutWorker should be importable from pytak."""
    import pytak
    assert hasattr(pytak, "StdinWorker")
    assert hasattr(pytak, "StdoutWorker")
