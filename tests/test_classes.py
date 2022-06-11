#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2022 Greg Albrecht <oss@undef.net>
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
# Author:: Greg Albrecht W2GMD <oss@undef.net>
# Copyright:: Copyright 2022 Greg Albrecht
# License:: Apache License, Version 2.0
#

"""Python Team Awareness Kit (PyTAK) Module Tests.

Some methods borrowed from https://github.com/aio-libs/aiohttp"""


import asyncio
import enum
import inspect
import sys
from unittest import mock

import pytest

import pytak

# Python 3.6 support:
if sys.version_info[:2] >= (3, 7):
    from asyncio import get_running_loop
else:
    from asyncio import get_event_loop as get_running_loop


__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


_SENTINEL = enum.Enum("_SENTINEL", "sentinel")
sentinel = _SENTINEL.sentinel


def make_mocked_coro(return_value=sentinel, raise_exception=sentinel):
    """Creates a coroutine mock."""

    async def mock_coro(*args, **kwargs):
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
    await worker.run(1)
    event = await event_queue.get()
    assert "taco2" == event


@pytest.mark.asyncio
async def test_eventworker():
    event_queue: asyncio.Queue = asyncio.Queue()
    await event_queue.put(b"taco1")
    await event_queue.put(b"taco2")

    transport.write = mock.Mock()
    transport.is_closing = mock.Mock()
    protocol._drain_helper = make_mocked_coro()

    loop = get_running_loop()
    writer = asyncio.StreamWriter(transport, protocol, None, loop)

    worker: pytak.Worker = pytak.TXWorker(event_queue, {}, writer)

    await worker.run(1)
    remaining_event = await event_queue.get()
    assert b"taco2" == remaining_event

    popped = transport.write.mock_calls.pop()

    # Python 3.7: popped[1][0]
    # Python 3.8+: popped.args[0]
    assert b"taco1" == popped[1][0]
