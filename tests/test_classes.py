#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Python Team Awareness Kit (PyTAK) Module Tests.

Some methods borrowed from https://github.com/aio-libs/aiohttp"""


import asyncio
import enum
import inspect

from configparser import ConfigParser
from typing import Any
from unittest import mock

import pytest

import pytak


_SENTINEL = enum.Enum("_SENTINEL", "sentinel")
sentinel = _SENTINEL.sentinel


def make_mocked_coro(
    return_value: Any = sentinel, raise_exception: Any = sentinel
) -> Any:
    """Creates a coroutine mock."""

    async def mock_coro(*args: Any, **kwargs: Any) -> Any:
        if raise_exception is not sentinel:
            raise raise_exception
        if not inspect.isawaitable(return_value):
            return return_value
        await return_value

    return mock.Mock(wraps=mock_coro)


@pytest.fixture
def transport(buf):
    transport = mock.Mock()

    def write(chunk):
        buf.extend(chunk)

    transport.write.side_effect = write
    transport.is_closing.return_value = False
    return transport


@pytest.fixture
def protocol(loop, transport):
    protocol = mock.Mock(transport=transport)
    protocol._drain_helper = make_mocked_coro()
    return protocol


@pytest.mark.asyncio
async def test_worker():
    event_queue: asyncio.Queue = asyncio.Queue()
    await event_queue.put("taco1")
    await event_queue.put("taco2")
    await event_queue.put("taco3")
    worker: pytak.Worker = pytak.Worker(event_queue)
    worker.handle_data = lambda data: event_queue.put(data)
    await worker.run_once()
    event = await event_queue.get()
    assert "taco2" == event


@pytest.mark.asyncio
async def test_eventworker() -> None:
    """Test EventWorker."""
    event_queue: asyncio.Queue = asyncio.Queue()
    await event_queue.put(b"taco1")
    await event_queue.put(b"taco2")

    transport = mock.Mock()
    transport.write = mock.Mock()
    transport.is_closing = mock.Mock()
    protocol._drain_helper = make_mocked_coro()

    loop = asyncio.get_event_loop()
    writer = asyncio.StreamWriter(transport, protocol, None, loop)

    worker: pytak.Worker = pytak.TXWorker(event_queue, {}, writer)

    await worker.run_once()
    remaining_event = await event_queue.get()
    assert b"taco2" == remaining_event

    popped = transport.write.mock_calls.pop()

    # Python 3.7: popped[1][0]
    # Python 3.8+: popped.args[0]
    assert b"taco1" == popped[1][0]


def test_simple_cot_event_to_xml() -> None:
    """Test SimpleCOTEvent to XML."""
    event = pytak.SimpleCOTEvent(
        lat=37.7749, lon=-122.4194, uid="user1", stale=60, cot_type="a-f-G-U-C"
    )
    xml = event.to_xml()
    assert xml.tag == "event"
    assert xml.attrib["version"] == "2.0"
    assert xml.attrib["uid"] == "user1"
    assert xml.attrib["type"] == "a-f-G-U-C"

    point = xml.find("point")
    assert point is not None
    assert point.attrib["lat"] == "37.7749"
    assert point.attrib["lon"] == "-122.4194"


def test_cot_event_to_xml():
    """Test COTEvent to XML."""
    event = pytak.COTEvent(
        lat=37.7749,
        lon=-122.4194,
        uid="user1",
        stale=60,
        cot_type="a-f-G-U-C",
        le=100,
        ce=200,
        hae=300,
    )
    xml = event.to_xml()
    assert xml.tag == "event"
    assert xml.attrib["version"] == "2.0"
    assert xml.attrib["uid"] == "user1"
    assert xml.attrib["type"] == "a-f-G-U-C"

    point = xml.find("point")
    assert point is not None
    assert point.attrib["lat"] == "37.7749"
    assert point.attrib["lon"] == "-122.4194"
    assert point.attrib["le"] == "100"
    assert point.attrib["ce"] == "200"
    assert point.attrib["hae"] == "300"


def test_simple_cot_event_as_obj():
    """Test SimpleCOTEvent as object."""
    event = pytak.SimpleCOTEvent(
        lat=37.7749, lon=-122.4194, uid="user1", stale=60, cot_type="a-f-G-U-C"
    )
    assert event.lat == 37.7749
    assert event.lon == -122.4194
    assert event.uid == "user1"
    assert event.stale == 60
    assert event.cot_type == "a-f-G-U-C"


def test_simple_cot_as_str():
    """Test SimpleCOTEvent as str."""
    event = pytak.SimpleCOTEvent(
        lat=37.7749, lon=-122.4194, uid="user1", stale=60, cot_type="a-f-G-U-C"
    )
    event = str(event)
    assert "37.7749" in event
    assert "-122.4194" in event
    assert "user1" in event
    assert "a-f-G-U-C" in event


def test_cot_event_as_obj():
    """Test COTEvent as object."""
    event = pytak.COTEvent(
        lat=37.7749,
        lon=-122.4194,
        uid="user1",
        stale=60,
        cot_type="a-f-G-U-C",
        le=100,
        ce=200,
        hae=300,
    )
    assert event.lat == 37.7749
    assert event.lon == -122.4194
    assert event.uid == "user1"
    assert event.stale == 60
    assert event.cot_type == "a-f-G-U-C"
    assert event.le == 100
    assert event.ce == 200
    assert event.hae == 300


def test_cot_event_as_str():
    """Test COTEvent as str."""
    event = pytak.COTEvent(
        lat=37.7749,
        lon=-122.4194,
        uid="user1",
        stale=60,
        cot_type="a-f-G-U-C",
        le=100,
        ce=200,
        hae=300,
    )
    print(event)
    event = str(event)
    assert "37.7749" in event
    assert "-122.4194" in event
    assert "user1" in event
    assert "a-f-G-U-C" in event
    assert "100" in event
    assert "200" in event
    assert "300" in event


@pytest.fixture
def config():
    config = ConfigParser()
    config.add_section("pytak")
    config.set("pytak", "COT_URL", "tcp://example.com:8087")
    config.set("pytak", "COT_HOST_ID", "user1")
    config = config["pytak"]
    return config


@pytest.fixture
def tx_queue():
    return asyncio.Queue()


@pytest.fixture
def rx_queue():
    return asyncio.Queue()


@pytest.fixture
def cli_tool(config, tx_queue, rx_queue):
    return pytak.CLITool(config, tx_queue, rx_queue)


def test_clitool_init(config, tx_queue, rx_queue):
    cli_tool = pytak.CLITool(config, tx_queue, rx_queue)
    assert cli_tool.config == config
    assert cli_tool.tx_queue == tx_queue
    assert cli_tool.rx_queue == rx_queue


@pytest.mark.asyncio
async def test_clitool_hello_event(cli_tool, tx_queue):
    await cli_tool.hello_event()
    assert tx_queue.qsize() == 1
