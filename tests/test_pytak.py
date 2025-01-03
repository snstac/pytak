#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2023 Sensors & Signals LLC
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

"""Python Team Awareness Kit (PyTAK) Module Tests."""

import asyncio
import urllib

import pytest
import pytak

__author__ = "Greg Albrecht <gba@snstac.com>"
__copyright__ = "Copyright 2023 Sensors & Signals LLC"
__license__ = "Apache License, Version 2.0"


@pytest.fixture
def my_queue():
    return asyncio.Queue()


@pytest.fixture
def my_Worker(my_queue):
    return pytak.Worker(my_queue)


class MyWriter:
    """Mock CoT Event Writer."""

    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)


@pytest.fixture
def my_writer():
    return MyWriter()


@pytest.mark.asyncio
async def test_EventWorker(my_queue, my_writer):
    """Tests that EventWorker processes CoT Events from a CoT Event Queue."""
    test_data = b"test test"
    test_eventworker = pytak.TXWorker(my_queue, {}, my_writer)
    await my_queue.put(test_data)
    await test_eventworker.run_once()

    assert my_writer.events.pop() == test_data
