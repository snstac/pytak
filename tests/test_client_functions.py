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
import os

from configparser import ConfigParser, SectionProxy
import io
from argparse import Namespace
from unittest import mock
from urllib.parse import ParseResult, urlparse

import pytest
import pytak

try:
    from unittest.mock import AsyncMock
except ImportError:

    class AsyncMock(mock.MagicMock):
        def __call__(self, *args, **kwargs):
            super().__call__(*args, **kwargs)
            ret = self.return_value

            async def _coro():
                return ret

            return _coro()

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


@pytest.mark.asyncio
async def test_main_bootstraps_downstream_create_tasks():
    """main() should invoke the downstream create_tasks(config, clitool) contract."""
    config_p = ConfigParser()
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]

    fake_app = mock.MagicMock()
    fake_tasks = {mock.sentinel.worker}
    fake_app.create_tasks.return_value = fake_tasks

    fake_clitool = mock.MagicMock()
    fake_clitool.create_workers = AsyncMock()
    fake_clitool.run = AsyncMock()

    with mock.patch(
        "pytak.client_functions.importlib.__import__", return_value=fake_app
    ), mock.patch(
        "pytak.client_functions.pytak.CLITool", return_value=fake_clitool
    ):
        await pytak.client_functions.main("fakeapp", config, config_p)

    assert fake_clitool.create_workers.call_count == 1
    assert fake_clitool.create_workers.call_args == mock.call(config)
    fake_app.create_tasks.assert_called_once_with(config, fake_clitool)
    fake_clitool.add_tasks.assert_called_once_with(fake_tasks)
    assert fake_clitool.run.call_count == 1
    assert fake_clitool.run.call_args == mock.call()


@pytest.mark.asyncio
async def test_main_bootstraps_import_other_configs():
    """main() should create workers for additional config sections when enabled."""
    config_p = ConfigParser()
    config_p.add_section("fakeapp")
    config_p.set("fakeapp", "IMPORT_OTHER_CONFIGS", "1")
    config_p.add_section("secondary")
    config_p.set("secondary", "COT_URL", "udp://239.2.3.1:6969")

    config = config_p["fakeapp"]

    fake_app = mock.MagicMock()
    fake_tasks = {mock.sentinel.worker}
    fake_app.create_tasks.return_value = fake_tasks

    fake_clitool = mock.MagicMock()
    fake_clitool.create_workers = AsyncMock()
    fake_clitool.run = AsyncMock()

    with mock.patch(
        "pytak.client_functions.importlib.__import__", return_value=fake_app
    ), mock.patch(
        "pytak.client_functions.pytak.CLITool", return_value=fake_clitool
    ):
        await pytak.client_functions.main("fakeapp", config, config_p)

    assert fake_clitool.create_workers.call_count == 2
    assert fake_clitool.create_workers.call_args_list == [
        mock.call(config),
        mock.call(config_p["secondary"]),
    ]
    fake_app.create_tasks.assert_called_once_with(config, fake_clitool)
    fake_clitool.add_tasks.assert_called_once_with(fake_tasks)
    assert fake_clitool.run.call_count == 1
    assert fake_clitool.run.call_args == mock.call()


def test_cli_builds_downstream_config_and_calls_main():
    """cli() should build config defaults expected by downstream command wrappers."""
    fake_app = mock.MagicMock()
    fake_app.DEFAULT_COT_STALE = "42"

    fake_main = AsyncMock()

    with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
        "pytak.client_functions.importlib.__import__", return_value=fake_app
    ), mock.patch(
        "pytak.client_functions.argparse.ArgumentParser.parse_args",
        return_value=Namespace(CONFIG_FILE="missing.ini", PREF_PACKAGE=None),
    ), mock.patch(
        "pytak.client_functions.os.path.exists", return_value=False
    ), mock.patch(
        "pytak.client_functions.main", new=fake_main
    ), mock.patch(
        "pytak.client_functions.platform.node", return_value="testnode"
    ):
        pytak.client_functions.cli("fakeapp")

    assert fake_main.call_count == 1
    app_name, config, full_config = fake_main.call_args.args

    assert app_name == "fakeapp"
    assert isinstance(config, SectionProxy)
    assert isinstance(full_config, ConfigParser)
    assert config.get("COT_URL") == pytak.DEFAULT_COT_URL
    assert config.get("COT_HOST_ID") == "fakeapp@testnode"
    assert config.get("COT_STALE") == "42"
    assert config.get("TAK_PROTO") == pytak.DEFAULT_TAK_PROTO
