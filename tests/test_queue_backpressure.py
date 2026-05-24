#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for queue backpressure when RX workers enqueue into a full queue."""

import asyncio
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

from pytak.classes import MartiRXWorker, RXWorker, WSRXWorker


SAMPLE_COT = (
    b'<?xml version="1.0"?>'
    b'<event version="2.0" uid="PYTAK-TEST" type="a-f-G-U-C" '
    b'time="2024-01-01T00:00:00Z" start="2024-01-01T00:00:00Z" '
    b'stale="2024-01-01T00:05:00Z" how="m-g">'
    b'<point lat="37.7749" lon="-122.4194" hae="0" ce="9999999" le="9999999"/>'
    b"</event>"
)

SAMPLE_SA_RESPONSE = """
<events>
  <event version="2.0" uid="UNIT-1" type="a-f-G" time="2024-01-01T00:00:00Z"
         start="2024-01-01T00:00:00Z" stale="2024-01-01T00:05:00Z" how="m-g">
    <point lat="37.0" lon="-122.0" hae="0" ce="9999999" le="9999999"/>
  </event>
  <event version="2.0" uid="UNIT-2" type="a-f-G" time="2024-01-01T00:00:01Z"
         start="2024-01-01T00:00:01Z" stale="2024-01-01T00:05:01Z" how="m-g">
    <point lat="38.0" lon="-121.0" hae="0" ce="9999999" le="9999999"/>
  </event>
</events>
"""


class _AsyncCM:
    """Minimal async context manager for mocked aiohttp responses."""

    def __init__(self, status, text=""):
        self.status = status
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return self._text


def _make_ws_msg(msg_type, data=None):
    msg = mock.MagicMock()
    msg.type = msg_type
    msg.data = data
    return msg


@pytest.mark.asyncio
async def test_ws_rx_worker_drops_oldest_on_full_queue():
    """WSRXWorker should drop the oldest item instead of raising QueueFull."""
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait(b"old-event")

    new_event = b"<event/>"
    mock_ws = mock.MagicMock()
    mock_ws.receive = AsyncMock(return_value=_make_ws_msg("BINARY", b"\xbf\x01\x00"))

    mock_aiohttp = mock.MagicMock()
    mock_aiohttp.WSMsgType.BINARY = "BINARY"
    mock_aiohttp.WSMsgType.CLOSE = "CLOSE"
    mock_aiohttp.WSMsgType.CLOSED = "CLOSED"
    mock_aiohttp.WSMsgType.ERROR = "ERROR"

    mock_takproto = mock.MagicMock()
    mock_takproto.parse_proto.return_value = new_event

    worker = WSRXWorker(queue, {}, mock_ws)
    with mock.patch("pytak.classes._aiohttp", mock_aiohttp), \
         mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.run_once()

    assert queue.full()
    assert await queue.get() == new_event


@pytest.mark.asyncio
async def test_rx_worker_drops_oldest_on_full_queue():
    """RXWorker should drop the oldest item instead of raising QueueFull."""
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait(b"old-event")

    new_event = SAMPLE_COT
    mock_reader = mock.MagicMock()

    class _TestRXWorker(RXWorker):
        async def handle_data(self, data: bytes) -> None:
            pass

    worker = _TestRXWorker(queue, {}, mock_reader)
    worker.readcot = AsyncMock(return_value=new_event)

    await worker.run_once()

    assert queue.full()
    assert await queue.get() == new_event


@pytest.mark.asyncio
async def test_marti_rx_worker_drops_oldest_on_full_queue():
    """MartiRXWorker should drop the oldest item instead of raising QueueFull."""
    queue = asyncio.Queue(maxsize=1)

    mock_session = mock.MagicMock()
    mock_session.get = mock.MagicMock(
        return_value=_AsyncCM(200, SAMPLE_SA_RESPONSE)
    )

    worker = MartiRXWorker(queue, {}, mock_session, "https://tak.example.com:8443")
    await worker.run_once()

    assert queue.full()
    event = await queue.get()
    assert b"UNIT-2" in event
    assert b"UNIT-1" not in event
