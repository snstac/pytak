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

"""Regression tests for client_functions.py and functions.py bug fixes."""

import asyncio
import socket
import sys
import types

from configparser import ConfigParser
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

import pytest

import pytak
import pytak.client_functions as cf

from pytak.functions import parse_mqtt_url

# ---------------------------------------------------------------------------
# Bug 1: IMPORT_OTHER_CONFIGS parsing and section selection in main()
# ---------------------------------------------------------------------------


def _install_fake_app(monkeypatch, name="fake_pytak_app"):
    module = types.ModuleType(name)
    module.create_tasks = lambda config, clitool: set()
    monkeypatch.setitem(sys.modules, name, module)
    return name


async def _run_main(monkeypatch, ini_text, app_name):
    calls = []

    async def fake_create_workers(self, config):
        calls.append(config.name)

    async def fake_run(self):
        return None

    monkeypatch.setattr(pytak.CLITool, "create_workers", fake_create_workers)
    monkeypatch.setattr(pytak.CLITool, "run", fake_run)

    full_config = ConfigParser()
    full_config.read_string(ini_text)
    await cf.main(app_name, full_config[app_name], full_config)
    return calls


@pytest.mark.asyncio
async def test_import_other_configs_zero_does_not_import(monkeypatch):
    """IMPORT_OTHER_CONFIGS=0 must not create workers for other sections."""
    app = _install_fake_app(monkeypatch)
    calls = await _run_main(
        monkeypatch,
        f"[{app}]\nCOT_URL=tcp://takserver.example.com:8087\n"
        "IMPORT_OTHER_CONFIGS=0\n"
        "[other]\nCOT_URL=tcp://takserver.example.com:8088\n",
        app,
    )
    assert calls == [app]


@pytest.mark.asyncio
async def test_import_other_configs_unset_keeps_legacy_import(monkeypatch):
    """Unset keeps the historical behaviour: other sections are imported.

    Existing multi-section config.ini files must not silently lose a
    destination; only an explicit off value disables the import.
    """
    app = _install_fake_app(monkeypatch)
    calls = await _run_main(
        monkeypatch,
        f"[{app}]\nCOT_URL=tcp://takserver.example.com:8087\n"
        "[other]\nCOT_URL=tcp://takserver.example.com:8088\n",
        app,
    )
    assert calls == [app, "other"]


@pytest.mark.asyncio
async def test_import_other_configs_skips_own_section_not_first(monkeypatch):
    """The app's own section is skipped wherever it appears in the file."""
    app = _install_fake_app(monkeypatch)
    calls = await _run_main(
        monkeypatch,
        "[other]\nCOT_URL=tcp://takserver.example.com:8088\n"
        f"[{app}]\nCOT_URL=tcp://takserver.example.com:8087\n"
        "IMPORT_OTHER_CONFIGS=1\n"
        "[third]\nCOT_URL=tcp://takserver.example.com:8089\n",
        app,
    )
    assert calls == [app, "other", "third"]


@pytest.mark.asyncio
async def test_import_other_configs_accepts_dict_config(monkeypatch):
    """A plain dict config is tolerated (no getboolean / name attribute)."""
    app = _install_fake_app(monkeypatch)
    calls = []

    async def fake_create_workers(self, config):
        calls.append(getattr(config, "name", "dict"))

    async def fake_run(self):
        return None

    monkeypatch.setattr(pytak.CLITool, "create_workers", fake_create_workers)
    monkeypatch.setattr(pytak.CLITool, "run", fake_run)

    full_config = ConfigParser()
    full_config.read_string(
        f"[{app}]\nCOT_URL=tcp://takserver.example.com:8087\n"
        "[other]\nCOT_URL=tcp://takserver.example.com:8088\n"
    )
    config = {"COT_URL": "tcp://takserver.example.com:8087"}
    config["IMPORT_OTHER_CONFIGS"] = "true"
    await cf.main(app, config, full_config)
    assert calls == ["dict", "other"]


# ---------------------------------------------------------------------------
# Bug 2: get_tls_config must not re-interpolate '%' in values
# ---------------------------------------------------------------------------


def test_get_tls_config_preserves_percent_in_password():
    """A TLS password containing '%' must survive get_tls_config()."""
    parser = ConfigParser()
    parser.read_string(
        "[app]\nPYTAK_TLS_CLIENT_CERT=/nonexistent/client.p12\n"
        "PYTAK_TLS_CLIENT_PASSWORD=ab%%cd\n"
    )
    config = parser["app"]
    assert config.get("PYTAK_TLS_CLIENT_PASSWORD") == "ab%cd"

    tls_config = cf.get_tls_config(config)
    assert tls_config.get("PYTAK_TLS_CLIENT_PASSWORD") == "ab%cd"
    assert tls_config.get("PYTAK_TLS_CLIENT_CERT") == "/nonexistent/client.p12"


# ---------------------------------------------------------------------------
# Bug 3: parse_tak_url double-decoding and IPv6 hosts
# ---------------------------------------------------------------------------


def test_parse_tak_url_decodes_values_once():
    """'%2541' decodes once to '%41', not twice to 'A'."""
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=takserver.example.com"
        "&username=user%2541&token=ab%2541cd"
    )
    assert result["token"] == "ab%41cd"
    assert result["username"] == "user%41"


def test_parse_tak_url_bare_ipv6_literal():
    """A bare IPv6 literal has no port; it is not split on its last colon."""
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=::1&username=u&token=t"
    )
    assert result["hostname"] == "::1"
    assert result["port"] == pytak.DEFAULT_TAK_STREAMING_PORT
    assert result["explicit_port"] is False


def test_parse_tak_url_bracketed_ipv6_with_port():
    """'[addr]:8089' keeps the bracketed host (stable cache key) and the port."""
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=%5B2001:db8::1%5D:8089&username=u&token=t"
    )
    assert result["hostname"] == "[2001:db8::1]"
    assert result["port"] == 8089
    assert result["explicit_port"] is True


def test_parse_tak_url_bracketed_ipv6_without_port():
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=[2001:db8::1]&username=u&token=t"
    )
    assert result["hostname"] == "[2001:db8::1]"
    assert result["port"] == pytak.DEFAULT_TAK_STREAMING_PORT
    assert result["explicit_port"] is False


def test_parse_tak_url_bracketed_ipv6_cache_key_unchanged():
    """Existing IPv6 users must keep hitting their cached certificate."""
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=[fd00::1]:8089&username=u&token=t"
    )
    # Before the IPv6 fix the hostname was '[fd00::1]'; the cache key derives
    # from it, so changing it would force a re-enrollment.
    assert cf._cert_cache_paths(
        result["hostname"], result["port"], "u"
    ) == cf._cert_cache_paths("[fd00::1]", 8089, "u")


@pytest.mark.parametrize(
    "host,expected",
    [
        ("[2001:db8::1]:8089", "tls://[2001:db8::1]:8089"),
        ("2001:db8::1", "wss://[2001:db8::1]:8443/takproto/1"),
    ],
)
@pytest.mark.asyncio
async def test_resolve_tak_url_brackets_ipv6_in_cot_url(tmp_path, host, expected):
    """The rewritten COT_URL must be a valid URL for IPv6 hosts."""
    enrollment = mock.MagicMock()
    domains = []

    async def begin_enrollment(**kwargs):
        domains.append(kwargs["domain"])
        Path(kwargs["output_path"]).write_bytes(b"p12")

    enrollment.begin_enrollment = begin_enrollment

    async def no_fingerprint(hostname, port):
        assert hostname == "2001:db8::1"
        return None

    with mock.patch("pathlib.Path.home", return_value=tmp_path), mock.patch.object(
        cf, "_server_cert_fingerprint_async", no_fingerprint
    ), mock.patch(
        "pytak.crypto_classes.CertificateEnrollment", return_value=enrollment
    ):
        result = await cf.resolve_tak_url(
            f"tak://com.atakmap.app/enroll?host={host}&username=u&token=t"
        )

    assert result["COT_URL"] == expected
    parsed = urlparse(result["COT_URL"])
    assert parsed.hostname == "2001:db8::1"
    # Enrollment builds https://{domain}:8446/... so it needs the bracketed form.
    assert domains == ["[2001:db8::1]"]


# ---------------------------------------------------------------------------
# Bug 4: unicast UDP reader must not bind to the remote address
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unicast_udp_reader_binds_locally_not_to_remote_host():
    """udp://<remote>:<port> must create a reader without EADDRNOTAVAIL."""
    writer = mock.MagicMock()
    routes = []

    def fake_local_address_for(host, port):
        routes.append(host)
        return "127.0.0.1"

    with _patch_dgconnect(writer), mock.patch.object(
        cf, "_local_address_for", fake_local_address_for
    ):
        reader, out = await pytak.create_udp_client(urlparse("udp://192.0.2.10:0"))
    try:
        assert out is writer
        assert reader is not None
        assert routes == ["192.0.2.10"]
        # Bound to the routed local interface address, not to all interfaces.
        assert reader.socket.getsockname()[0] == "127.0.0.1"
    finally:
        reader.close()


def test_local_address_for_loopback_peer():
    """The routed local address for a loopback peer is a loopback address."""
    assert cf._local_address_for("127.0.0.1", 6969).startswith("127.")


@pytest.mark.skipif(sys.platform == "win32", reason="Windows binds all")
@pytest.mark.asyncio
async def test_unicast_udp_reader_keeps_local_bind_address():
    """A local unicast address (e.g. loopback) is still bound explicitly."""
    reader, writer = await pytak.create_udp_client(urlparse("udp+ro://127.0.0.1:0"))
    try:
        assert writer is None
        assert reader.socket.getsockname()[0] == "127.0.0.1"
    finally:
        reader.close()


@pytest.mark.asyncio
async def test_udp_reader_setup_failure_closes_writer_and_socket():
    """If reader setup fails, the writer and reader socket must not leak."""
    writer = mock.MagicMock()
    sockets = []
    real_socket = socket.socket

    def tracking_socket(*args, **kwargs):
        sock = real_socket(*args, **kwargs)
        sockets.append(sock)
        return sock

    async def failing_from_socket(sock):
        raise OSError("boom")

    with _patch_dgconnect(writer), mock.patch(
        "pytak.client_functions.socket.socket", side_effect=tracking_socket
    ), mock.patch("pytak.client_functions.from_socket", failing_from_socket):
        with pytest.raises(OSError, match="boom"):
            await pytak.create_udp_client(urlparse("udp://127.0.0.1:0"))

    writer.close.assert_called_once()
    assert len(sockets) == 1
    assert sockets[0].fileno() == -1


def _patch_dgconnect(writer):
    async def fake_connect(*args, **kwargs):
        return writer

    return mock.patch("pytak.client_functions.dgconnect", fake_connect)


# ---------------------------------------------------------------------------
# Bug 5: MQTT '#' wildcard must be preserved in the topic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,topic",
    [
        ("mqtt://broker.example.com:1883/cot/#", "cot/#"),
        ("mqtt://broker.example.com/#", "#"),
        ("mqtts://broker.example.com/cot/+/events/#", "cot/+/events/#"),
    ],
)
def test_parse_mqtt_url_keeps_multilevel_wildcard(url, topic):
    assert parse_mqtt_url(url).topic == topic


def test_parse_mqtt_url_keeps_wildcard_from_parse_result():
    parsed = urlparse("mqtt://broker.example.com/cot/#", allow_fragments=False)
    assert parse_mqtt_url(parsed).topic == "cot/#"


@pytest.mark.asyncio
async def test_mqtt_factory_subscribes_with_multilevel_wildcard():
    """mqtt_factory must subscribe to 'cot/#', not the truncated 'cot/'."""
    parser = ConfigParser()
    parser.add_section("test")
    parser.set("test", "COT_URL", "mqtt+ro://broker.example.com:1883/cot/#")

    subscribed = []

    class FakeMessages:
        # MagicMock does not support __aiter__ on Python 3.7.
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.messages = FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def subscribe(self, topic, qos=0):
            subscribed.append((topic, qos))

    fake_aiomqtt = types.ModuleType("aiomqtt")
    fake_aiomqtt.Client = FakeClient

    with mock.patch.dict("sys.modules", {"aiomqtt": fake_aiomqtt}):
        tx_worker, rx_worker = await cf.mqtt_factory(
            asyncio.Queue(), asyncio.Queue(), parser["test"]
        )

    assert tx_worker is None
    assert rx_worker is not None
    assert subscribed == [("cot/#", 0)]


# ---------------------------------------------------------------------------
# cli(): environment variables differing only by case
# ---------------------------------------------------------------------------


def test_cli_tolerates_env_vars_differing_only_by_case(monkeypatch, tmp_path):
    """no_proxy + NO_PROXY (common behind proxies) crashed cli() at startup.

    ConfigParser lower-cases option names, so building it from os.environ
    raised DuplicateOptionError.
    """
    module = types.ModuleType("fake_case_app")
    monkeypatch.setitem(sys.modules, "fake_case_app", module)
    monkeypatch.setattr(
        cf.os,
        "environ",
        {
            "no_proxy": "lower.example.com",
            "NO_PROXY": "upper.example.com",
            "cot_url": "udp://239.2.3.1:6969",
            "COT_URL": "tcp://takserver.example.com:8087",
        },
    )
    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(tmp_path / "missing.ini")])
    captured = {}

    def fake_run_with_reconnect(app_name, config, full_config, tak_url):
        captured["config"] = config
        return "coroutine-sentinel"

    monkeypatch.setattr(cf, "run_with_reconnect", fake_run_with_reconnect)
    monkeypatch.setattr(cf.asyncio, "run", lambda coro, debug=False: None)

    cf.cli("fake_case_app")

    config = captured["config"]
    # The upper-case spelling (PyTAK's documented form) wins.
    assert config["COT_URL"] == "tcp://takserver.example.com:8087"
    assert config["NO_PROXY"] == "upper.example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_limit", [None, "131072", "256"])
async def test_tcp_stream_limit_with_real_large_event(configured_limit):
    """A real TCP reader accepts large events or enforces an explicit small limit."""
    payload = b"<event>" + b"x" * 70000 + b"</event>"

    async def send_event(reader, writer):
        try:
            writer.write(payload)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(send_event, "127.0.0.1", 0)
    writer = None
    try:
        port = server.sockets[0].getsockname()[1]
        config = {"COT_URL": "tcp://127.0.0.1:%s" % port}
        if configured_limit is not None:
            config["STREAM_LIMIT"] = configured_limit
        reader, writer = await pytak.protocol_factory(config)
        read_event = asyncio.wait_for(reader.readuntil(b"</event>"), timeout=5)
        if configured_limit == "256":
            with pytest.raises(asyncio.LimitOverrunError):
                await read_event
        else:
            assert await read_event == payload
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        server.close()
        await server.wait_closed()
