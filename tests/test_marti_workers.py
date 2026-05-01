#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for MartiTXWorker, MartiRXWorker, and the Marti factory functions."""

import asyncio
from unittest import mock

import pytest

import pytak
from pytak.classes import _extract_cot_events, MartiTXWorker, MartiRXWorker


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


# ---------------------------------------------------------------------------
# _extract_cot_events
# ---------------------------------------------------------------------------


def test_extract_cot_events_two():
    events = _extract_cot_events(SAMPLE_SA_RESPONSE)
    assert len(events) == 2
    assert 'uid="UNIT-1"' in events[0]
    assert 'uid="UNIT-2"' in events[1]


def test_extract_cot_events_empty():
    assert _extract_cot_events("no events here") == []


def test_extract_cot_events_single():
    events = _extract_cot_events(SAMPLE_COT.decode())
    assert len(events) == 1
    assert "PYTAK-TEST" in events[0]


# ---------------------------------------------------------------------------
# MartiTXWorker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marti_tx_worker_posts_cot():
    """MartiTXWorker.handle_data() should POST CoT as JSON to the inject endpoint."""
    queue = asyncio.Queue()
    config = {"COT_HOST_ID": "test-uid"}

    mock_response = mock.AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = mock.AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = mock.AsyncMock(return_value=False)

    mock_session = mock.MagicMock()
    mock_session.post = mock.MagicMock(return_value=mock_response)

    worker = MartiTXWorker(queue, config, mock_session, "https://tak.example.com:8443", "test-uid")
    await worker.handle_data(SAMPLE_COT)

    mock_session.post.assert_called_once()
    call_kwargs = mock_session.post.call_args
    assert "/Marti/api/injectors/cot/uid" in call_kwargs[0][0]
    payload = call_kwargs[1]["json"]
    assert payload["uid"] == "test-uid"
    assert "<event" in payload["toInject"]


@pytest.mark.asyncio
async def test_marti_tx_worker_skips_empty():
    """MartiTXWorker.handle_data() should not POST empty data."""
    queue = asyncio.Queue()
    mock_session = mock.MagicMock()
    worker = MartiTXWorker(queue, {}, mock_session, "https://tak.example.com:8443", "uid")
    await worker.handle_data(b"")
    mock_session.post.assert_not_called()


@pytest.mark.asyncio
async def test_marti_tx_worker_logs_non_200():
    """MartiTXWorker.handle_data() should log a warning on non-200 response."""
    queue = asyncio.Queue()

    mock_response = mock.AsyncMock()
    mock_response.status = 500
    mock_response.__aenter__ = mock.AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = mock.AsyncMock(return_value=False)

    mock_session = mock.MagicMock()
    mock_session.post = mock.MagicMock(return_value=mock_response)

    worker = MartiTXWorker(queue, {}, mock_session, "https://tak.example.com:8443", "uid")
    # Should not raise even on a 500
    await worker.handle_data(SAMPLE_COT)
    mock_session.post.assert_called_once()


# ---------------------------------------------------------------------------
# MartiRXWorker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marti_rx_worker_polls_and_enqueues():
    """MartiRXWorker.run_once() should GET /Marti/api/cot/sa and enqueue events."""
    queue = asyncio.Queue()

    mock_response = mock.AsyncMock()
    mock_response.status = 200
    mock_response.text = mock.AsyncMock(return_value=SAMPLE_SA_RESPONSE)
    mock_response.__aenter__ = mock.AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = mock.AsyncMock(return_value=False)

    mock_session = mock.MagicMock()
    mock_session.get = mock.MagicMock(return_value=mock_response)

    worker = MartiRXWorker(queue, {}, mock_session, "https://tak.example.com:8443")
    await worker.run_once()

    assert queue.qsize() == 2
    event1 = await queue.get()
    event2 = await queue.get()
    assert b"UNIT-1" in event1
    assert b"UNIT-2" in event2


@pytest.mark.asyncio
async def test_marti_rx_worker_handles_empty_response():
    """MartiRXWorker.run_once() should handle a response with no CoT events."""
    queue = asyncio.Queue()

    mock_response = mock.AsyncMock()
    mock_response.status = 200
    mock_response.text = mock.AsyncMock(return_value="<events></events>")
    mock_response.__aenter__ = mock.AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = mock.AsyncMock(return_value=False)

    mock_session = mock.MagicMock()
    mock_session.get = mock.MagicMock(return_value=mock_response)

    worker = MartiRXWorker(queue, {}, mock_session, "https://tak.example.com:8443")
    await worker.run_once()
    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_marti_rx_worker_handles_http_error():
    """MartiRXWorker.run_once() should not raise on non-200 response."""
    queue = asyncio.Queue()

    mock_response = mock.AsyncMock()
    mock_response.status = 503
    mock_response.__aenter__ = mock.AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = mock.AsyncMock(return_value=False)

    mock_session = mock.MagicMock()
    mock_session.get = mock.MagicMock(return_value=mock_response)

    worker = MartiRXWorker(queue, {}, mock_session, "https://tak.example.com:8443")
    await worker.run_once()
    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_marti_constants():
    assert pytak.DEFAULT_MARTI_PORT == 8443
    assert pytak.DEFAULT_MARTI_POLL_INTERVAL == 5
    assert pytak.DEFAULT_MARTI_POLL_SECONDS_AGO == 30


# ---------------------------------------------------------------------------
# _make_workers dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_workers_marti_scheme():
    """_make_workers should return Marti workers for marti:// scheme."""
    from pytak.classes import _make_workers
    from configparser import ConfigParser

    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "marti://tak.example.com:8443")
    cfg = config["test"]

    with mock.patch(
        "pytak.marti_txworker_factory", new=mock.AsyncMock(return_value=mock.MagicMock(spec=MartiTXWorker))
    ) as mock_tx, mock.patch(
        "pytak.marti_rxworker_factory", new=mock.AsyncMock(return_value=mock.MagicMock(spec=MartiRXWorker))
    ) as mock_rx:
        tx_q, rx_q = asyncio.Queue(), asyncio.Queue()
        write_worker, read_worker = await _make_workers(tx_q, rx_q, cfg)
        mock_tx.assert_called_once_with(tx_q, cfg)
        mock_rx.assert_called_once_with(rx_q, cfg)
