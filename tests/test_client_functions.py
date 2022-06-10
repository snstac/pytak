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

"""Python Team Awareness Kit (PyTAK) Module Tests."""


import asyncio
from cmath import isnan

from configparser import ConfigParser, SectionProxy
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
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert reader == None
    assert isinstance(writer, pytak.asyncio_dgram.aio.DatagramClient)


@pytest.mark.asyncio
async def test_txworker_factory_udp():
    test_url1: str = "udp://localhost"

    config_p = ConfigParser()
    config_p.add_section("pytak")
    config = config_p["pytak"]
    config.setdefault("COT_URL", test_url1)

    queue: asyncio.Queue = asyncio.Queue()
    worker = await pytak.txworker_factory(queue, config)
    assert isinstance(worker, pytak.classes.TXWorker)


@pytest.mark.asyncio
async def test_rxworker_factory_udp():
    test_url1: str = "udp://localhost"

    config_p = ConfigParser()
    config_p.add_section("pytak")
    config = config_p["pytak"]
    config.setdefault("COT_URL", test_url1)

    queue: asyncio.Queue = asyncio.Queue()
    worker = await pytak.rxworker_factory(queue, config)
    assert isinstance(worker, pytak.classes.RXWorker)


def test_get_tls_config():
    base_config: dict = {
        "PYTAK_TLS_CLIENT_CERT": "test_get_tls_config",
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": 1,
    }
    config_p = ConfigParser(base_config)
    config_p.add_section("pytak")
    config = config_p["pytak"]
    tls_config: ConfigParser = pytak.client_functions.get_tls_config(config)
    print(tls_config)

    assert isinstance(tls_config, SectionProxy)
    assert tls_config.get("PYTAK_TLS_CLIENT_CERT") == "test_get_tls_config"
    assert not tls_config.getboolean("PYTAK_TLS_DONT_VERIFY")
    assert tls_config.getboolean("PYTAK_TLS_DONT_CHECK_HOSTNAME")
