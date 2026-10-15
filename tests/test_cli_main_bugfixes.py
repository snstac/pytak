#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Regression tests for bugs fixed in pytak.cli_main and pytak.asyncio_dgram."""

import asyncio
import os
import socket
import warnings
from argparse import Namespace
from unittest import mock

import pytest

from pytak import asyncio_dgram
from pytak import cli_main
from pytak.cli_main import FileWorker, _frame_cot_xml_events, _get_tx_source

SELF_CLOSING = (
    b'<event version="2.0" type="t-x-d-d" uid="ping" how="m-g" '
    b'time="2026-01-01T00:00:00Z" start="2026-01-01T00:00:00Z" '
    b'stale="2026-01-01T01:00:00Z"/>'
)

FULL_EVENT = (
    b'<event version="2.0" uid="TEST" type="a-f-G" how="m-g">'
    b'<point lat="37.0" lon="-122.0" hae="0" ce="9999999" le="9999999"/>'
    b"</event>"
)


# ---------------------------------------------------------------------------
# Bug 1: self-closing <event .../> was never framed
# ---------------------------------------------------------------------------


def test_frame_self_closing_event():
    """A self-closing root <event .../> is a complete CoT event."""
    events, remainder = _frame_cot_xml_events(SELF_CLOSING + b"\n")
    assert events == [SELF_CLOSING]
    assert remainder.strip() == b""


def test_frame_mixed_self_closing_and_full_events():
    """Self-closing and regular events interleave in order."""
    payload = SELF_CLOSING + b"\n" + FULL_EVENT + b"\n" + SELF_CLOSING
    events, remainder = _frame_cot_xml_events(payload)
    assert events == [SELF_CLOSING, FULL_EVENT, SELF_CLOSING]
    assert remainder == b""


def test_frame_nested_self_closing_child_does_not_end_event():
    """A child element's '/>' must not terminate a non-self-closing event."""
    partial = FULL_EVENT[: FULL_EVENT.index(b"</event>")]
    events, remainder = _frame_cot_xml_events(partial)
    assert events == []
    assert remainder == partial


def test_frame_slash_gt_inside_attribute_value_is_not_end():
    """'/>' inside a quoted attribute must not close the start tag."""
    event = b'<event uid="a/>b" type="x">' b"<detail/></event>"
    events, remainder = _frame_cot_xml_events(event)
    assert events == [event]
    assert remainder == b""


def test_frame_self_closing_split_across_chunks():
    """An incomplete self-closing tag is kept until the rest arrives."""
    head, tail = SELF_CLOSING[:-1], SELF_CLOSING[-1:]
    events, remainder = _frame_cot_xml_events(head)
    assert events == []
    assert remainder == head
    events, remainder = _frame_cot_xml_events(remainder + tail)
    assert events == [SELF_CLOSING]


@pytest.mark.asyncio
async def test_file_worker_sends_self_closing_event(tmp_path):
    """FileWorker must emit a file holding only a self-closing event."""
    cot_file = tmp_path / "events.xml"
    cot_file.write_bytes(SELF_CLOSING + b"\n")
    queue = asyncio.Queue()
    await FileWorker(queue, {}, str(cot_file)).run()
    assert queue.qsize() == 1
    assert await queue.get() == SELF_CLOSING


@pytest.mark.asyncio
async def test_file_worker_warns_about_incomplete_trailing_data(tmp_path):
    """Incomplete trailing bytes at EOF are reported rather than silently lost."""
    cot_file = tmp_path / "events.xml"
    cot_file.write_bytes(FULL_EVENT + b"<event uid='x'")
    queue = asyncio.Queue()
    worker = FileWorker(queue, {}, str(cot_file))
    with mock.patch.object(worker, "_logger") as logger:
        await worker.run()
    assert queue.qsize() == 1
    assert logger.warning.called


# ---------------------------------------------------------------------------
# Bug 2: non-TTY stdin (e.g. </dev/null under cron) made --tx-file ambiguous
# ---------------------------------------------------------------------------


def _run_with_stdin(path, args):
    """Call _get_tx_source with sys.stdin backed by *path*."""
    with open(path, "rb") as fobj:
        fake_stdin = mock.MagicMock()
        fake_stdin.fileno.return_value = fobj.fileno()
        with mock.patch.object(cli_main.sys, "stdin", fake_stdin):
            return _get_tx_source(args, False)


def test_tx_file_with_dev_null_stdin_is_not_ambiguous():
    """--tx-file with stdin redirected from /dev/null must select the file."""
    args = Namespace(rx_only=False, tx_file="events.xml")
    assert _run_with_stdin(os.devnull, args) == "file"


def test_dev_null_stdin_without_tx_file_is_none():
    """A non-TTY character device on stdin is not a TX data source."""
    args = Namespace(rx_only=False, tx_file=None)
    assert _run_with_stdin(os.devnull, args) == "none"


def test_pipe_stdin_with_tx_file_is_still_ambiguous():
    """A real pipe on stdin plus --tx-file is still rejected."""
    rfd, wfd = os.pipe()
    try:
        fake_stdin = mock.MagicMock()
        fake_stdin.fileno.return_value = rfd
        with mock.patch.object(cli_main.sys, "stdin", fake_stdin):
            with pytest.raises(ValueError, match="Ambiguous"):
                _get_tx_source(Namespace(rx_only=False, tx_file="e.xml"), False)
            assert (
                _get_tx_source(Namespace(rx_only=False, tx_file=None), False) == "stdin"
            )
    finally:
        os.close(rfd)
        os.close(wfd)


def test_regular_file_stdin_is_a_data_source(tmp_path):
    """stdin redirected from a regular file is a TX data source."""
    src = tmp_path / "in.xml"
    src.write_bytes(SELF_CLOSING)
    args = Namespace(rx_only=False, tx_file=None)
    assert _run_with_stdin(str(src), args) == "stdin"


@pytest.mark.skipif(not hasattr(socket, "socketpair"), reason="no socketpair")
def test_socket_stdin_is_a_data_source():
    """socat/inetd/systemd socket activation hand pytak a socket as stdin."""
    left, right = socket.socketpair()
    try:
        fake_stdin = mock.MagicMock()
        fake_stdin.fileno.return_value = left.fileno()
        args = Namespace(rx_only=False, tx_file=None)
        with mock.patch.object(cli_main.sys, "stdin", fake_stdin):
            assert _get_tx_source(args, False) == "stdin"
    finally:
        left.close()
        right.close()


# ---------------------------------------------------------------------------
# Bug 3: warnings.warn called with logging-style args -> TypeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protocol_connection_made_twice_warns_without_type_error():
    """Re-initialising a Protocol transport emits a formatted warning."""
    proto = asyncio_dgram.Protocol(asyncio.Queue(), asyncio.Queue(), asyncio.Event())
    old = mock.MagicMock()
    old.get_extra_info.return_value = ("127.0.0.1", 1111)
    new = mock.MagicMock()
    new.get_extra_info.return_value = ("127.0.0.1", 2222)

    proto.connection_made(old)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        proto.connection_made(new)

    assert len(caught) == 1
    msg = str(caught[0].message)
    assert "1111" in msg and "2222" in msg
    assert proto._transport is new
