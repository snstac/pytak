#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Tests."""


import asyncio
import configparser

from cmath import isnan
from urllib.parse import ParseResult, urlparse

from unittest import mock

import pytest

import pytak


__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


@pytest.fixture(params=["tcp", "udp"])
def gen_url(request) -> ParseResult:
    test_url1: str = f"{request.param}://localhost"
    parsed_url1: ParseResult = urlparse(test_url1)
    return parsed_url1


@pytest.mark.asyncio
async def test_protocol_factory_udp():
    test_url1: str = "udp://localhost"
    config: dict = {"COT_URL": urlparse(test_url1)}
    reader, writer = await pytak.protocol_factory(config)
    assert reader == None
    assert isinstance(writer, pytak.asyncio_dgram.aio.DatagramClient)


@pytest.mark.asyncio
async def test_eventworker_factory_udp():
    test_url1: str = "udp://localhost"
    config: dict = {"COT_URL": urlparse(test_url1)}
    event_queue: asyncio.Queue = asyncio.Queue()
    worker = await pytak.eventworker_factory(config, event_queue)
    assert isinstance(worker, pytak.classes.EventWorker)


def test_get_tls_config():
    base_config: dict = {"PYTAK_TLS_CLIENT_CERT": "TEST"}
    config_p = configparser.ConfigParser(base_config)
    config_p.add_section("pytak")
    config = config_p["pytak"]
    tls_config: dict = pytak.client_functions.get_tls_config(config)
    print(tls_config)
    assert isinstance(tls_config, dict)

