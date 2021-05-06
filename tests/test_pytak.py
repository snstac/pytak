#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Tests."""

import asyncio
import urllib

import pytest
import pytak

__author__ = 'Greg Albrecht W2GMD <oss@undef.net>'
__copyright__ = 'Copyright 2020 Orion Labs, Inc.'
__license__ = 'Apache License, Version 2.0'


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
    test_eventworker = pytak.EventWorker(my_queue, my_writer)
    await my_queue.put(test_data)
    await test_eventworker.run(number_of_iterations=1)

    assert my_writer.events.pop() == test_data
