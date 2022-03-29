#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Tests."""


import asyncio
from cmath import isnan
import enum
import inspect
import urllib

from unittest import mock

import pytest

import pytak


__author__ = 'Greg Albrecht W2GMD <oss@undef.net>'
__copyright__ = 'Copyright 2022 Greg Albrecht'
__license__ = 'Apache License, Version 2.0'


@pytest.fixture(params=['tcp', 'udp'])
def gen_url(request) -> urllib.parse.ParseResult:
    test_url1: str = f"{request.param}://localhost"
    parsed_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    return parsed_url1


@pytest.mark.asyncio
async def test_protocol_factory_udp():
    test_url1: str = 'udp://localhost'
    parsed_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    reader, writer = await pytak.protocol_factory(parsed_url1)
    assert reader == None
    assert isinstance(writer, pytak.asyncio_dgram.aio.DatagramClient)


@pytest.mark.asyncio
async def test_eventworker_factory_udp():
    test_url1: str = 'udp://localhost'
    parsed_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    event_queue: asyncio.Queue = asyncio.Queue()
    worker = await pytak.eventworker_factory(parsed_url1, event_queue)
    assert isinstance(worker, pytak.classes.EventWorker)
