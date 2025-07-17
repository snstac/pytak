#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
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

"""PyTAK Tests."""


import asyncio

from configparser import ConfigParser, SectionProxy
import io
from unittest import mock
from urllib.parse import ParseResult, urlparse

import pytest
import pytak

@pytest.fixture(params=["tcp", "udp"])
def gen_url(request) -> ParseResult:
    """Generate a Parsed URL for tests fixtures."""
    test_url1: str = f"{request.param}://localhost"
    parsed_url1: ParseResult = urlparse(test_url1)
    return parsed_url1


@pytest.mark.asyncio
async def test_protocol_factory_udp():
    """Test creating a UDP reader & writer with `pytak.protocol_factory()`."""
    test_url1: str = "udp://localhost"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert isinstance(reader, pytak.asyncio_dgram.DatagramServer)
    assert isinstance(writer, pytak.asyncio_dgram.DatagramClient)


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
    """Test creating a TLS config."""
    base_config: dict = {
        "PYTAK_TLS_CLIENT_CERT": "test_get_tls_config",
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": "1",
    }
    config_p = ConfigParser(base_config)
    config_p.add_section("pytak")
    config = config_p["pytak"]
    tls_config: ConfigParser = pytak.client_functions.get_tls_config(config)

    assert isinstance(tls_config, SectionProxy)
    assert tls_config.get("PYTAK_TLS_CLIENT_CERT") == "test_get_tls_config"
    assert not tls_config.getboolean("PYTAK_TLS_DONT_VERIFY")
    assert tls_config.getboolean("PYTAK_TLS_DONT_CHECK_HOSTNAME")


def _test_get_tls_config_incomplete():
    """Test creating an incomplete TLS config."""
    base_config: dict = {
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": "1",
    }
    config_p = ConfigParser(base_config)
    config_p.add_section("pytak")
    config = config_p["pytak"]
    with pytest.raises(Exception):
        pytak.client_functions.get_tls_config(config)


@pytest.mark.asyncio
async def test_protocol_factory_udp_broadcast():
    """Test creating a broadcast UDP reader & writer with `pytak.protocol_factory()`."""
    test_url1: str = "udp+broadcast://localhost:6666"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert isinstance(reader, pytak.asyncio_dgram.DatagramServer)
    assert isinstance(writer, pytak.asyncio_dgram.DatagramClient)


@pytest.mark.asyncio
async def test_protocol_factory_udp_multicast():
    """Test creating a multicast UDP reader & writer with `pytak.protocol_factory()`."""
    test_url1: str = "udp://239.2.3.1"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert isinstance(reader, pytak.asyncio_dgram.DatagramServer)
    assert isinstance(writer, pytak.asyncio_dgram.DatagramClient)


@pytest.mark.asyncio
async def test_protocol_factory_udp_multicast_wo():
    """Test creating a multicast UDP writer only with `pytak.protocol_factory()`."""
    test_url1: str = "udp+wo://239.2.3.1"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert reader == None
    assert isinstance(writer, pytak.asyncio_dgram.DatagramClient)


@pytest.mark.asyncio
async def test_protocol_factory_bad_url():
    """Test calling `pytak.protocol_factory()` with a bad URL."""
    test_url1: str = "udp:localhost"
    config: dict = {"COT_URL": test_url1}
    with pytest.warns(SyntaxWarning, match="Invalid COT_URL"):
        with pytest.raises(Exception):
            await pytak.protocol_factory(config)


@pytest.mark.asyncio
async def test_protocol_factory_tcp():
    """Test creating a TCP reader & writer with `pytak.protocol_factory()`."""
    test_url1: str = "tcp://localhost"
    config: dict = {"COT_URL": test_url1}
    with mock.patch("socket.socket.connect"):
        reader, writer = await pytak.protocol_factory(config)
        assert isinstance(reader, asyncio.StreamReader)
        assert isinstance(writer, asyncio.StreamWriter)


@pytest.mark.asyncio
async def test_protocol_factory_http_url():
    """Test calling `pytak.protocol_factory()` with an HTTP URL."""
    test_url1: str = "http://localhost"
    config: dict = {"COT_URL": test_url1}
    with pytest.raises(Exception):
        await pytak.protocol_factory(config)


@pytest.mark.asyncio
async def test_protocol_factory_log_stdout_url():
    """Test calling `pytak.protocol_factory()` with an HTTP URL."""
    test_url1: str = "log://stdout"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert reader is None
    assert isinstance(writer, io.FileIO)


@pytest.mark.asyncio
async def test_protocol_factory_log_stderr_url():
    """Test calling `pytak.protocol_factory()` with an HTTP URL."""
    test_url1: str = "log://stderr"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert reader is None
    assert isinstance(writer, io.FileIO)


@pytest.mark.asyncio
async def test_protocol_factory_unknown_url():
    """Test calling `pytak.protocol_factory()` with an HTTP URL."""
    test_url1: str = "foo://bar"
    config: dict = {"COT_URL": test_url1}
    with pytest.raises(Exception):
        await pytak.protocol_factory(config)
