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
import errno
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
            ret = super().__call__(*args, **kwargs)

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


@pytest.mark.parametrize("load_error", [None, ValueError("bad certificate")])
def test_get_ssl_ctx_removes_pkcs12_temporary_pems(tmp_path, load_error):
    """PKCS#12 extraction must not accumulate PEMs across reconnects."""
    p12_path = tmp_path / "client.p12"
    p12_path.write_bytes(b"placeholder")
    pem_paths = []
    for name in ("key.pem", "cert.pem", "ca.pem"):
        path = tmp_path / name
        path.write_bytes(b"temporary")
        pem_paths.append(str(path))

    defaults = {
        "PYTAK_TLS_CLIENT_CERT": str(p12_path),
        "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE": "secret",
        "PYTAK_TLS_DONT_VERIFY": "1",
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": "1",
    }
    parser = ConfigParser(defaults)
    parser.add_section("pytak")
    config = parser["pytak"]
    converted = {
        "pk_pem_path": pem_paths[0],
        "cert_pem_path": pem_paths[1],
        "ca_pem_path": pem_paths[2],
    }
    ssl_ctx = mock.MagicMock()
    ssl_ctx.options = 0
    ssl_ctx.load_cert_chain.side_effect = load_error

    with mock.patch(
        "pytak.client_functions.convert_cert", return_value=converted
    ), mock.patch("pytak.client_functions.ssl.SSLContext", return_value=ssl_ctx):
        if load_error:
            with pytest.raises(ValueError, match="Error opening resource"):
                pytak.client_functions.get_ssl_ctx(config)
        else:
            assert pytak.client_functions.get_ssl_ctx(config) is ssl_ctx

    assert not any(os.path.exists(path) for path in pem_paths)


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
async def test_protocol_factory_udp_multicast_ro():
    """Test creating a multicast UDP reader only with `pytak.protocol_factory()`."""
    test_url1: str = "udp+ro://239.2.3.1"
    config: dict = {"COT_URL": test_url1}
    reader, writer = await pytak.protocol_factory(config)
    assert isinstance(reader, pytak.asyncio_dgram.DatagramServer)
    assert writer is None


@pytest.mark.asyncio
async def test_protocol_factory_passes_plural_multicast_addresses():
    """The plural multicast setting takes the dedicated UDP factory path."""
    config = {
        "COT_URL": "udp+wo://239.2.3.1:6969",
        "PYTAK_MULTICAST_LOCAL_ADDR": "10.41.0.1",
        "PYTAK_MULTICAST_LOCAL_ADDRS": "192.0.2.10, 169.254.2.3",
        "PYTAK_MULTICAST_TTL": "2",
    }
    sentinel = mock.MagicMock()
    with mock.patch(
        "pytak.create_udp_client", AsyncMock(return_value=(None, sentinel))
    ) as factory:
        reader, writer = await pytak.protocol_factory(config)

    assert reader is None
    assert writer is sentinel
    args = factory.await_args.args
    assert args[1] == ("10.41.0.1", 0)
    assert args[2:] == ("2", "192.0.2.10, 169.254.2.3")


@pytest.mark.asyncio
async def test_multicast_writer_fans_out_and_survives_partial_connect_failure():
    """One unusable interface must not prevent a healthy multicast output."""
    healthy = mock.MagicMock()
    healthy.sockname = ("192.0.2.10", 12345)
    healthy.send = AsyncMock()

    async def connect(_remote, *, local_addr, allow_broadcast):
        del allow_broadcast
        if local_addr[0] == "169.254.2.3":
            raise OSError(errno.ENETUNREACH, "gone")
        return healthy

    with mock.patch("pytak.client_functions.dgconnect", side_effect=connect):
        reader, writer = await pytak.create_udp_client(
            urlparse("udp+wo://239.2.3.1:6969"),
            multicast_local_addrs="192.0.2.10,169.254.2.3",
        )

    assert reader is None
    assert writer is healthy
    await writer.send(b"cot")
    healthy.send.assert_awaited_once_with(b"cot")


@pytest.mark.asyncio
async def test_datagram_fanout_drops_failed_link_but_keeps_healthy_link():
    """A runtime failure on one fanout member does not poison the others."""
    good = mock.MagicMock()
    good.send = AsyncMock()
    bad = mock.MagicMock()
    bad.send = AsyncMock(side_effect=OSError(errno.ENETDOWN, "down"))
    writer = pytak.asyncio_dgram.DatagramFanoutClient([good, bad])

    await writer.send(b"first")
    await writer.send(b"second")

    assert writer.clients == (good,)
    assert good.send.await_count == 2
    bad.send.assert_awaited_once_with(b"first")
    bad.close.assert_called_once()


@pytest.mark.asyncio
async def test_unicast_udp_ignores_multicast_source_settings():
    """A multicast interface choice must never bind a localhost feeder output."""
    client = mock.MagicMock()
    with mock.patch(
        "pytak.client_functions.dgconnect", AsyncMock(return_value=client)
    ) as connect:
        await pytak.create_udp_client(
            urlparse("udp+wo://127.0.0.1:28087"),
            ("10.41.0.1", 0),
            multicast_local_addrs="169.254.2.3",
        )

    assert connect.await_args.kwargs["local_addr"] == ("0.0.0.0", 0)


def test_parse_cot_scheme_tls_wo():
    """parse_cot_scheme strips +wo and sets write_only."""
    assert pytak.parse_cot_scheme("tls+wo") == ("tls", True, False)


def test_parse_cot_scheme_marti_http():
    """parse_cot_scheme preserves marti+http base scheme."""
    assert pytak.parse_cot_scheme("marti+http") == ("marti+http", False, False)


def test_parse_cot_scheme_wo_and_ro_raises():
    """parse_cot_scheme rejects +wo and +ro together."""
    with pytest.raises(SyntaxError, match="both \\+wo and \\+ro"):
        pytak.parse_cot_scheme("tcp+wo+ro")


@pytest.mark.asyncio
async def test_protocol_factory_tcp_wo():
    """tcp+wo still opens a full-duplex stream (discard is at worker layer)."""
    test_url1: str = "tcp+wo://localhost:8087"
    config: dict = {"COT_URL": test_url1}
    with mock.patch("asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
        mock_conn.return_value = (mock.MagicMock(), mock.MagicMock())
        reader, writer = await pytak.protocol_factory(config)
        assert reader is not None
        assert writer is not None
        mock_conn.assert_called_once()


@pytest.mark.asyncio
async def test_make_workers_tls_wo():
    """_make_workers uses DiscardRXWorker for tls+wo."""
    from pytak.classes import DiscardRXWorker, TXWorker, _make_workers

    config_p = ConfigParser()
    config_p.add_section("test")
    config_p.set("test", "COT_URL", "tls+wo://localhost:8089")
    config = config_p["test"]
    tx_q = asyncio.Queue()
    rx_q = asyncio.Queue()
    mock_reader = mock.MagicMock()
    mock_writer = mock.MagicMock()

    with mock.patch(
        "pytak.protocol_factory",
        AsyncMock(return_value=(mock_reader, mock_writer)),
    ):
        write_worker, read_worker = await _make_workers(tx_q, rx_q, config)

    assert isinstance(write_worker, TXWorker)
    assert isinstance(read_worker, DiscardRXWorker)


@pytest.mark.asyncio
async def test_make_workers_tls_ro():
    """_make_workers skips TXWorker for tls+ro."""
    from pytak.classes import RXWorker, _make_workers

    config_p = ConfigParser()
    config_p.add_section("test")
    config_p.set("test", "COT_URL", "tls+ro://localhost:8089")
    config = config_p["test"]
    tx_q = asyncio.Queue()
    rx_q = asyncio.Queue()
    mock_reader = mock.MagicMock()
    mock_writer = mock.MagicMock()

    with mock.patch(
        "pytak.protocol_factory",
        AsyncMock(return_value=(mock_reader, mock_writer)),
    ):
        write_worker, read_worker = await _make_workers(tx_q, rx_q, config)

    assert write_worker is None
    assert isinstance(read_worker, RXWorker)


@pytest.mark.asyncio
async def test_make_workers_udp_wo():
    """_make_workers skips read worker for udp+wo (no reader socket)."""
    from pytak.classes import TXWorker, _make_workers

    config_p = ConfigParser()
    config_p.add_section("test")
    config_p.set("test", "COT_URL", "udp+wo://239.2.3.1:6969")
    config = config_p["test"]
    tx_q = asyncio.Queue()
    rx_q = asyncio.Queue()
    mock_writer = mock.MagicMock()

    with mock.patch(
        "pytak.protocol_factory",
        AsyncMock(return_value=(None, mock_writer)),
    ):
        write_worker, read_worker = await _make_workers(tx_q, rx_q, config)

    assert isinstance(write_worker, TXWorker)
    assert read_worker is None


@pytest.mark.asyncio
async def test_discard_rx_worker_does_not_enqueue():
    """DiscardRXWorker drains the reader without putting on rx_queue."""
    from pytak.classes import DiscardRXWorker

    config_p = ConfigParser()
    config_p.add_section("test")
    config_p.set("test", "COT_URL", "tls+wo://localhost:8089")
    config = config_p["test"]
    rx_q = asyncio.Queue()
    mock_reader = mock.MagicMock()
    mock_reader.readuntil = AsyncMock(
        return_value=b'<event version="2.0"></event>'
    )
    worker = DiscardRXWorker(rx_q, config, mock_reader)
    await worker.run_once()
    assert rx_q.empty()


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


@pytest.mark.asyncio
async def test_run_with_reconnect_backs_off_transient_failures():
    """Transient transport failures stay in-process with bounded backoff."""
    config_p = ConfigParser(
        {
            "PYTAK_RECONNECT_INITIAL": "1",
            "PYTAK_RECONNECT_MAX": "4",
            "PYTAK_RECONNECT_FACTOR": "2",
            "PYTAK_RECONNECT_JITTER": "0",
            "PYTAK_RECONNECT_RESET": "300",
        }
    )
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]
    fake_main = AsyncMock(
        side_effect=[
            ConnectionRefusedError("server offline"),
            ConnectionAbortedError("WebSocket closed by server"),
            None,
        ]
    )
    fake_sleep = AsyncMock()
    fake_loop = mock.MagicMock()
    fake_loop.time.side_effect = [0, 0.1, 1, 1.1, 2]

    with mock.patch(
        "pytak.client_functions.main", new=fake_main
    ), mock.patch(
        "pytak.client_functions.asyncio.sleep", new=fake_sleep
    ), mock.patch(
        "pytak.client_functions.asyncio.get_running_loop", return_value=fake_loop
    ):
        await pytak.client_functions.run_with_reconnect(
            "fakeapp", config, config_p
        )

    assert fake_main.call_count == 3
    assert fake_sleep.call_args_list == [mock.call(1), mock.call(2)]


@pytest.mark.asyncio
async def test_run_with_reconnect_resets_after_stable_session():
    """A long-lived connection gets the fast initial retry when it drops."""
    config_p = ConfigParser(
        {
            "PYTAK_RECONNECT_INITIAL": "1",
            "PYTAK_RECONNECT_MAX": "8",
            "PYTAK_RECONNECT_FACTOR": "2",
            "PYTAK_RECONNECT_JITTER": "0",
            "PYTAK_RECONNECT_RESET": "5",
        }
    )
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]
    fake_main = AsyncMock(
        side_effect=[
            ConnectionRefusedError("offline"),
            ConnectionError("dropped"),
            None,
        ]
    )
    fake_sleep = AsyncMock()
    fake_loop = mock.MagicMock()
    fake_loop.time.side_effect = [0, 0.1, 1, 11, 12]

    with mock.patch(
        "pytak.client_functions.main", new=fake_main
    ), mock.patch(
        "pytak.client_functions.asyncio.sleep", new=fake_sleep
    ), mock.patch(
        "pytak.client_functions.asyncio.get_running_loop", return_value=fake_loop
    ):
        await pytak.client_functions.run_with_reconnect(
            "fakeapp", config, config_p
        )

    assert fake_sleep.call_args_list == [mock.call(1), mock.call(1)]


@pytest.mark.asyncio
async def test_run_with_reconnect_keeps_configuration_errors_fatal():
    """Retry scaffolding must not hide invalid local configuration."""
    config_p = ConfigParser()
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]
    fake_sleep = AsyncMock()

    with mock.patch(
        "pytak.client_functions.main",
        new=AsyncMock(side_effect=ValueError("invalid setting")),
    ), mock.patch("pytak.client_functions.asyncio.sleep", new=fake_sleep):
        with pytest.raises(ValueError, match="invalid setting"):
            await pytak.client_functions.run_with_reconnect(
                "fakeapp", config, config_p
            )

    fake_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_run_with_reconnect_keeps_local_os_errors_fatal():
    """Missing files and full disks are not TAK reachability failures."""
    config_p = ConfigParser()
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]
    fake_sleep = AsyncMock()

    with mock.patch(
        "pytak.client_functions.main",
        new=AsyncMock(side_effect=FileNotFoundError("missing local input")),
    ), mock.patch("pytak.client_functions.asyncio.sleep", new=fake_sleep):
        with pytest.raises(FileNotFoundError, match="missing local input"):
            await pytak.client_functions.run_with_reconnect(
                "fakeapp", config, config_p
            )

    fake_sleep.assert_not_called()


def test_reconnect_keeps_local_access_denied_fatal():
    """Ordinary local file access failures remain configuration errors."""
    error = PermissionError(errno.EACCES, "Permission denied")
    assert not pytak.client_functions._retryable_transport_error(error)


@pytest.mark.asyncio
async def test_run_with_reconnect_retries_transient_udp_permission_error():
    """A firewall transition must not terminate a UDP-backed gateway."""
    config_p = ConfigParser(
        {
            "PYTAK_RECONNECT_INITIAL": "1",
            "PYTAK_RECONNECT_MAX": "2",
            "PYTAK_RECONNECT_FACTOR": "2",
            "PYTAK_RECONNECT_JITTER": "0",
            "PYTAK_RECONNECT_RESET": "300",
        }
    )
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]
    fake_main = AsyncMock(
        side_effect=[PermissionError(errno.EPERM, "Operation not permitted"), None]
    )
    fake_sleep = AsyncMock()

    with mock.patch(
        "pytak.client_functions.main", new=fake_main
    ), mock.patch("pytak.client_functions.asyncio.sleep", new=fake_sleep):
        await pytak.client_functions.run_with_reconnect(
            "fakeapp", config, config_p
        )

    assert fake_main.call_count == 2
    fake_sleep.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_custom_client_supervisor_rebuilds_after_udp_permission_error():
    """Custom CLITool integrations get the same in-process recovery policy."""
    config_p = ConfigParser(
        {
            "PYTAK_RECONNECT_INITIAL": "1",
            "PYTAK_RECONNECT_MAX": "2",
            "PYTAK_RECONNECT_FACTOR": "2",
            "PYTAK_RECONNECT_JITTER": "0",
            "PYTAK_RECONNECT_RESET": "300",
        }
    )
    config_p.add_section("custom")
    run_once = AsyncMock(
        side_effect=[PermissionError(errno.EPERM, "Operation not permitted"), None]
    )
    fake_sleep = AsyncMock()

    with mock.patch("pytak.client_functions.asyncio.sleep", new=fake_sleep):
        await pytak.supervise_with_reconnect(config_p["custom"], run_once)

    assert run_once.call_count == 2
    fake_sleep.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_run_with_reconnect_retries_tak_enrollment_resolution():
    """A transient enrollment failure retries from the original deep link."""
    config_p = ConfigParser(
        {
            "PYTAK_RECONNECT_INITIAL": "1",
            "PYTAK_RECONNECT_MAX": "2",
            "PYTAK_RECONNECT_FACTOR": "2",
            "PYTAK_RECONNECT_JITTER": "0",
            "PYTAK_RECONNECT_RESET": "300",
        }
    )
    config_p.add_section("fakeapp")
    config = config_p["fakeapp"]
    tak_url = "tak://com.atakmap.app/enroll?host=example&token=redacted"
    resolved = {"COT_URL": "wss://example:8443/takproto/1"}
    fake_resolve = AsyncMock(side_effect=[ConnectionError("offline"), resolved])
    fake_main = AsyncMock()
    fake_sleep = AsyncMock()

    with mock.patch(
        "pytak.client_functions.resolve_tak_url", new=fake_resolve
    ), mock.patch(
        "pytak.client_functions.main", new=fake_main
    ), mock.patch("pytak.client_functions.asyncio.sleep", new=fake_sleep):
        await pytak.client_functions.run_with_reconnect(
            "fakeapp", config, config_p, tak_url
        )

    assert fake_resolve.call_count == 2
    fake_main.assert_called_once_with("fakeapp", config, config_p)
    fake_sleep.assert_called_once_with(1)
    assert config.get("COT_URL") == resolved["COT_URL"]


def test_reconnect_log_redacts_enrollment_credentials():
    """Retry diagnostics must never print one-time onboarding secrets."""
    error = OSError(
        "failed tak://com.atakmap.app/enroll?host=example&username=user&token=secret"
    )
    text = pytak.client_functions._safe_error_text(error)
    assert text == "failed tak://REDACTED"
    assert "user" not in text
    assert "secret" not in text


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
    app_name, config, full_config = fake_main.call_args[0]

    assert app_name == "fakeapp"
    assert isinstance(config, SectionProxy)
    assert isinstance(full_config, ConfigParser)
    assert config.get("COT_URL") == pytak.DEFAULT_COT_URL
    assert config.get("COT_HOST_ID") == "fakeapp@testnode"
    assert config.get("COT_STALE") == "42"
    assert config.get("TAK_PROTO") == pytak.DEFAULT_TAK_PROTO
