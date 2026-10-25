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

"""Behavioural coverage tests for pytak.client_functions."""

import asyncio
import builtins
import errno
import hashlib
import os
import socket
import ssl
import sys
import types

from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

import pytest

import pytak
import pytak.client_functions as cf

DATA_DIR = Path(__file__).parent / "data"


def _section(values, name="app"):
    parser = ConfigParser(interpolation=None)
    parser[name] = values
    return parser[name]


def _awaitable(value=None, exc=None):
    """Return an async function returning ``value`` (or raising ``exc``)."""
    calls = []

    async def _fn(*args, **kwargs):
        calls.append((args, kwargs))
        if exc is not None:
            raise exc
        return value

    _fn.calls = calls
    return _fn


# ---------------------------------------------------------------------------
# parse_tak_url / cert cache helpers
# ---------------------------------------------------------------------------


def test_parse_tak_url_non_numeric_port_keeps_host():
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=takserver.example.com:abc"
        "&username=u&token=t"
    )
    assert result["hostname"] == "takserver.example.com:abc"
    assert result["port"] == pytak.DEFAULT_TAK_STREAMING_PORT
    assert result["explicit_port"] is False


def test_parse_tak_url_bracketed_ipv6_bad_port_uses_default():
    result = cf.parse_tak_url(
        "tak://com.atakmap.app/enroll?host=[2001:db8::1]:x&username=u&token=t"
    )
    assert result["hostname"] == "[2001:db8::1]"
    assert result["port"] == pytak.DEFAULT_TAK_STREAMING_PORT
    assert result["explicit_port"] is False


def test_cached_cert_valid_rejects_p12_without_certificate(tmp_path):
    p12 = tmp_path / "c.p12"
    p12.write_bytes(b"data")
    with mock.patch(
        "cryptography.hazmat.primitives.serialization.pkcs12."
        "load_key_and_certificates",
        return_value=(None, None, None),
    ):
        assert cf._cached_cert_valid(str(p12), "pw") is False


@pytest.mark.parametrize("days,expected", [(365, True), (1, False)])
def test_cached_cert_valid_legacy_not_valid_after(tmp_path, days, expected):
    """Older cryptography lacks not_valid_after_utc; the naive value is used."""
    p12 = tmp_path / "c.p12"
    p12.write_bytes(b"data")
    cert = types.SimpleNamespace(
        not_valid_after=(datetime.now(timezone.utc) + timedelta(days=days)).replace(
            tzinfo=None
        )
    )
    with mock.patch(
        "cryptography.hazmat.primitives.serialization.pkcs12."
        "load_key_and_certificates",
        return_value=(None, cert, None),
    ):
        assert cf._cached_cert_valid(str(p12), "", buffer_days=30) is expected


def _fake_tls_connection(der):
    sock = mock.MagicMock()
    sock.__enter__.return_value = sock
    tls_sock = mock.MagicMock()
    tls_sock.__enter__.return_value = tls_sock
    tls_sock.getpeercert.return_value = der
    ctx = mock.MagicMock()
    ctx.wrap_socket.return_value = tls_sock
    return sock, ctx


def test_server_cert_fingerprint_hashes_peer_certificate():
    sock, ctx = _fake_tls_connection(b"der-bytes")
    with mock.patch.object(
        cf.socket, "create_connection", return_value=sock
    ) as create, mock.patch.object(cf.ssl, "create_default_context", return_value=ctx):
        fingerprint = cf._server_cert_fingerprint("takserver.example.com", 8443)

    assert fingerprint == hashlib.sha256(b"der-bytes").hexdigest()
    create.assert_called_once_with(("takserver.example.com", 8443), timeout=5.0)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE
    ctx.wrap_socket.assert_called_once_with(
        sock, server_hostname="takserver.example.com"
    )


def test_server_cert_fingerprint_requires_peer_certificate():
    sock, ctx = _fake_tls_connection(None)
    with mock.patch.object(
        cf.socket, "create_connection", return_value=sock
    ), mock.patch.object(cf.ssl, "create_default_context", return_value=ctx):
        with pytest.raises(RuntimeError, match="No TLS peer certificate"):
            cf._server_cert_fingerprint("takserver.example.com", 8443)


@pytest.mark.asyncio
async def test_server_cert_fingerprint_async_success_and_failure():
    with mock.patch.object(cf, "_server_cert_fingerprint", return_value="ab12"):
        assert await cf._server_cert_fingerprint_async("h.example.com", 1) == "ab12"
    with mock.patch.object(
        cf, "_server_cert_fingerprint", side_effect=OSError("refused")
    ):
        assert await cf._server_cert_fingerprint_async("h.example.com", 1) is None


@pytest.mark.asyncio
async def test_resolve_tak_url_cache_hit_records_missing_server_fingerprint(tmp_path):
    """A cache hit with no stored server fingerprint stores the current one."""
    url = "tak://com.atakmap.app/enroll?host=takserver.example.com&username=u&token=t"
    with mock.patch("pathlib.Path.home", return_value=tmp_path):
        p12_path, pass_path = cf._cert_cache_paths(
            "takserver.example.com", pytak.DEFAULT_TAK_STREAMING_PORT, "u"
        )
        Path(p12_path).write_bytes(b"p12")
        Path(pass_path).write_text("secret")
        with mock.patch.object(
            cf, "_server_cert_fingerprint_async", _awaitable("fp1")
        ), mock.patch.object(cf, "_cached_cert_valid", return_value=True):
            result = await cf.resolve_tak_url(url)

    fp_path = Path(cf._cert_cache_server_fingerprint_path(p12_path))
    assert fp_path.read_text() == "fp1"
    assert oct(fp_path.stat().st_mode & 0o777) == "0o600"
    assert result["PYTAK_TLS_CLIENT_CERT"] == p12_path
    assert result["PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE"] == "secret"


# ---------------------------------------------------------------------------
# Marti / WebSocket / MQTT factories
# ---------------------------------------------------------------------------


async def _marti_session_ssl(config):
    """Run _marti_session and return (session, base_url, uid, connector ssl)."""
    import aiohttp

    with mock.patch.object(
        aiohttp, "TCPConnector", wraps=aiohttp.TCPConnector
    ) as connector:
        session, base_url, uid = await cf._marti_session(config)
    return session, base_url, uid, connector.call_args[1]["ssl"]


@pytest.mark.asyncio
async def test_marti_session_plain_http():
    config = _section(
        {"COT_URL": "marti+http://takserver.example.com:8080", "MARTI_COT_UID": "u1"}
    )
    session, base_url, uid, ssl_arg = await _marti_session_ssl(config)
    try:
        assert ssl_arg is None
        assert base_url == "http://takserver.example.com:8080"
        assert uid == "u1"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_marti_session_tls_without_cert_defaults_port():
    config = _section(
        {"COT_URL": "marti://takserver.example.com", "COT_HOST_ID": "host-1"}
    )
    session, base_url, uid, ssl_arg = await _marti_session_ssl(config)
    try:
        assert base_url == f"https://takserver.example.com:{pytak.DEFAULT_MARTI_PORT}"
        assert uid == "host-1"
        assert ssl_arg is False
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_marti_session_tls_bad_cert_falls_back_to_no_verify(tmp_path):
    config = _section(
        {
            "COT_URL": "marti://takserver.example.com:8443",
            "PYTAK_TLS_CLIENT_CERT": str(tmp_path / "missing.pem"),
        }
    )
    session, _, _, ssl_arg = await _marti_session_ssl(config)
    try:
        assert ssl_arg is False
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_marti_session_tls_uses_client_cert():
    config = _section(
        {
            "COT_URL": "marti://takserver.example.com:8443",
            "PYTAK_TLS_CLIENT_CERT": "/certs/client.pem",
        }
    )
    ctx = ssl.create_default_context()
    with mock.patch.object(cf, "get_ssl_ctx", return_value=ctx) as get_ctx:
        session, _, _, ssl_arg = await _marti_session_ssl(config)
    try:
        assert ssl_arg is ctx
        assert get_ctx.call_args[0][0]["PYTAK_TLS_CLIENT_CERT"] == ("/certs/client.pem")
    finally:
        await session.close()


def _block_import(name):
    real_import = builtins.__import__

    def _import(mod, *args, **kwargs):
        if mod == name:
            raise ImportError(f"no {name}")
        return real_import(mod, *args, **kwargs)

    return mock.patch("builtins.__import__", side_effect=_import)


@pytest.mark.asyncio
async def test_marti_session_requires_aiohttp():
    config = _section({"COT_URL": "marti://takserver.example.com"})
    with _block_import("aiohttp"):
        with pytest.raises(ImportError, match="with-aiohttp"):
            await cf._marti_session(config)


@pytest.mark.asyncio
async def test_marti_worker_factories():
    session = mock.MagicMock()
    config = _section(
        {
            "COT_URL": "marti://takserver.example.com",
            "MARTI_POLL_INTERVAL": "7",
            "MARTI_POLL_SECONDS_AGO": "42",
        }
    )
    fake = _awaitable((session, "https://takserver.example.com:8443", "uid-9"))
    with mock.patch.object(cf, "_marti_session", fake):
        tx = await cf.marti_txworker_factory(asyncio.Queue(), config)
        rx = await cf.marti_rxworker_factory(asyncio.Queue(), config)

    assert isinstance(tx, pytak.MartiTXWorker)
    assert isinstance(rx, pytak.MartiRXWorker)
    assert rx._poll_interval == 7
    assert rx._seconds_ago == 42


class _FakeWSSession:
    def __init__(self, ws=None, exc=None):
        self.ws = ws
        self.exc = exc
        self.closed = False
        self.ssl = "unset"

    async def ws_connect(self, url, ssl=None):
        self.url = url
        self.ssl = ssl
        if self.exc is not None:
            raise self.exc
        return self.ws

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_ws_factory_wss_without_cert_disables_verification():
    import aiohttp

    ws = mock.MagicMock()
    fake = _FakeWSSession(ws=ws)
    config = _section({"COT_URL": "wss://takserver.example.com:8443/takproto/1"})
    with mock.patch.object(aiohttp, "ClientSession", return_value=fake):
        tx, rx = await cf.ws_factory(asyncio.Queue(), asyncio.Queue(), config)

    assert isinstance(tx, pytak.WSTXWorker)
    assert isinstance(rx, pytak.WSRXWorker)
    assert fake.url == "wss://takserver.example.com:8443/takproto/1"
    assert fake.ssl.verify_mode == ssl.CERT_NONE
    assert fake.ssl.check_hostname is False
    assert not fake.closed


@pytest.mark.asyncio
async def test_ws_factory_wss_with_cert_uses_ssl_ctx():
    import aiohttp

    fake = _FakeWSSession(ws=mock.MagicMock())
    ctx = object()
    config = _section(
        {
            "COT_URL": "wss://takserver.example.com:8443/takproto/1",
            "PYTAK_TLS_CLIENT_CERT": "/certs/client.p12",
        }
    )
    with mock.patch.object(aiohttp, "ClientSession", return_value=fake), mock.patch(
        "pytak.client_functions.get_ssl_ctx", return_value=ctx
    ):
        await cf.ws_factory(asyncio.Queue(), asyncio.Queue(), config)
    assert fake.ssl is ctx


@pytest.mark.asyncio
async def test_ws_factory_plain_ws_connection_error_closes_session():
    import aiohttp

    fake = _FakeWSSession(exc=aiohttp.ClientConnectionError("refused"))
    config = _section({"COT_URL": "ws://takserver.example.com:8080/takproto/1"})
    with mock.patch.object(aiohttp, "ClientSession", return_value=fake):
        with pytest.raises(aiohttp.ClientConnectionError):
            await cf.ws_factory(asyncio.Queue(), asyncio.Queue(), config)
    assert fake.ssl is None
    assert fake.closed


@pytest.mark.asyncio
async def test_ws_factory_handshake_error_non_403_reraised():
    import aiohttp

    exc = aiohttp.WSServerHandshakeError(mock.MagicMock(), (), status=500)
    fake = _FakeWSSession(exc=exc)
    config = _section({"COT_URL": "ws://takserver.example.com:8080/takproto/1"})
    with mock.patch.object(aiohttp, "ClientSession", return_value=fake):
        with pytest.raises(aiohttp.WSServerHandshakeError):
            await cf.ws_factory(asyncio.Queue(), asyncio.Queue(), config)
    assert fake.closed


@pytest.mark.asyncio
async def test_ws_factory_403_removes_cached_cert(tmp_path, monkeypatch):
    import aiohttp

    # Only certs inside pytak's own enrollment cache are removed (#99, #117).
    monkeypatch.setenv("HOME", str(tmp_path))
    cache = tmp_path / ".pytak" / "certs"
    cache.mkdir(parents=True)
    p12 = cache / "cached.p12"
    p12.write_bytes(b"p12")
    passfile = cache / "cached.pass"
    passfile.write_text("pw")
    exc = aiohttp.WSServerHandshakeError(mock.MagicMock(), (), status=403)
    fake = _FakeWSSession(exc=exc)
    config = _section(
        {
            "COT_URL": "wss://takserver.example.com:8443/takproto/1",
            "PYTAK_TLS_CLIENT_CERT": str(p12),
        }
    )
    with mock.patch.object(aiohttp, "ClientSession", return_value=fake), mock.patch(
        "pytak.client_functions.get_ssl_ctx", return_value=object()
    ):
        with pytest.raises(PermissionError, match="403"):
            await cf.ws_factory(asyncio.Queue(), asyncio.Queue(), config)
    assert not p12.exists()
    assert not passfile.exists()
    assert fake.closed


@pytest.mark.asyncio
async def test_ws_factory_requires_aiohttp():
    config = _section({"COT_URL": "ws://takserver.example.com:8080/takproto/1"})
    with _block_import("aiohttp"):
        with pytest.raises(ImportError, match="with-aiohttp"):
            await cf.ws_factory(asyncio.Queue(), asyncio.Queue(), config)


class _FakeMQTTClient:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.messages = mock.MagicMock()
        self.subscribe_exc = None
        self.exited = False
        _FakeMQTTClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    async def subscribe(self, topic, qos=0):
        if self.subscribe_exc is not None:
            raise self.subscribe_exc


def _fake_aiomqtt(subscribe_exc=None):
    module = types.ModuleType("aiomqtt")

    def factory(**kwargs):
        client = _FakeMQTTClient(**kwargs)
        client.subscribe_exc = subscribe_exc
        return client

    module.Client = factory
    return module


@pytest.mark.asyncio
async def test_mqtt_factory_mqtts_without_cert_disables_verification():
    config = _section(
        {
            "COT_URL": "mqtts+wo://user:pa%40ss@broker.example.com/cot",
            "MQTT_CLIENT_ID": "client-1",
        }
    )
    _FakeMQTTClient.instances = []
    with mock.patch.dict("sys.modules", {"aiomqtt": _fake_aiomqtt()}):
        tx, rx = await cf.mqtt_factory(asyncio.Queue(), asyncio.Queue(), config)

    assert rx is None
    assert tx is not None
    kwargs = _FakeMQTTClient.instances[0].kwargs
    assert kwargs["hostname"] == "broker.example.com"
    assert kwargs["port"] == pytak.DEFAULT_MQTTS_PORT
    assert kwargs["username"] == "user"
    assert kwargs["password"] == "pa@ss"
    assert kwargs["identifier"] == "client-1"
    assert kwargs["tls_context"].verify_mode == ssl.CERT_NONE


@pytest.mark.asyncio
async def test_mqtt_factory_mqtts_with_cert_uses_ssl_ctx():
    ctx = object()
    config = _section(
        {
            "COT_URL": "mqtts+wo://broker.example.com/cot",
            "PYTAK_TLS_CLIENT_CERT": "/certs/client.pem",
        }
    )
    _FakeMQTTClient.instances = []
    with mock.patch.dict("sys.modules", {"aiomqtt": _fake_aiomqtt()}), mock.patch(
        "pytak.client_functions.get_ssl_ctx", return_value=ctx
    ):
        await cf.mqtt_factory(asyncio.Queue(), asyncio.Queue(), config)
    assert _FakeMQTTClient.instances[0].kwargs["tls_context"] is ctx


@pytest.mark.asyncio
async def test_mqtt_factory_subscribe_failure_closes_session():
    config = _section({"COT_URL": "mqtt://broker.example.com/cot"})
    _FakeMQTTClient.instances = []
    module = _fake_aiomqtt(subscribe_exc=RuntimeError("denied"))
    with mock.patch.dict("sys.modules", {"aiomqtt": module}):
        with pytest.raises(RuntimeError, match="denied"):
            await cf.mqtt_factory(asyncio.Queue(), asyncio.Queue(), config)
    assert _FakeMQTTClient.instances[0].exited


# ---------------------------------------------------------------------------
# get_cot_url / protocol_factory / worker factories
# ---------------------------------------------------------------------------


def test_get_cot_url_rejects_missing_scheme():
    with pytest.warns(SyntaxWarning):
        with pytest.raises(SyntaxError, match="full URL"):
            cf.get_cot_url({"COT_URL": "takserver.example.com:8087"})


@pytest.mark.asyncio
async def test_protocol_factory_tls_delegates_to_create_tls_client():
    fake = _awaitable(("r", "w"))
    config = _section({"COT_URL": "tls://takserver.example.com:8089"})
    with mock.patch.object(cf, "create_tls_client", fake):
        assert await cf.protocol_factory(config) == ("r", "w")
    assert fake.calls[0][0][1].hostname == "takserver.example.com"


@pytest.mark.asyncio
async def test_protocol_factory_file_writer(tmp_path):
    target = tmp_path / "sub" / "out.cot"
    config = _section({"COT_URL": f"file://{target}"})
    reader, writer = await cf.protocol_factory(config)
    try:
        assert reader is None
        writer.write(b"<event/>")
    finally:
        writer.close()
    assert target.read_bytes() == b"<event/>"


@pytest.mark.asyncio
async def test_protocol_factory_tak_resolves_then_connects_tls():
    resolved = {
        "COT_URL": "tls://takserver.example.com:8089",
        "PYTAK_TLS_CLIENT_CERT": "/certs/c.p12",
    }
    tls = _awaitable(("r", "w"))
    config = _section(
        {
            "COT_URL": "tak://com.atakmap.app/enroll?host=takserver.example.com"
            "&username=u&token=t"
        }
    )
    with mock.patch.object(
        cf, "resolve_tak_url", _awaitable(resolved)
    ), mock.patch.object(cf, "create_tls_client", tls):
        assert await cf.protocol_factory(config) == ("r", "w")
    assert config["COT_URL"] == "tls://takserver.example.com:8089"
    assert config["PYTAK_TLS_CLIENT_CERT"] == "/certs/c.p12"
    assert tls.calls[0][0][1].port == 8089


@pytest.mark.asyncio
async def test_protocol_factory_unknown_scheme():
    config = _section({"COT_URL": "gopher://takserver.example.com:70"})
    with pytest.raises(SyntaxError, match="Invalid COT_URL protocol"):
        await cf.protocol_factory(config)


@pytest.mark.asyncio
async def test_rxworker_factory_write_only_discards():
    config = _section({"COT_URL": "tcp+wo://takserver.example.com:8087"})
    reader = mock.MagicMock()
    with mock.patch.object(cf, "protocol_factory", _awaitable((reader, "w"))):
        worker = await cf.rxworker_factory(asyncio.Queue(), config)
    assert isinstance(worker, pytak.DiscardRXWorker)


@pytest.mark.asyncio
async def test_txworker_factory_uses_writer():
    config = _section({"COT_URL": "tcp://takserver.example.com:8087"})
    writer = mock.MagicMock()
    with mock.patch.object(cf, "protocol_factory", _awaitable((None, writer))):
        worker = await cf.txworker_factory(asyncio.Queue(), config)
    assert isinstance(worker, pytak.TXWorker)
    assert worker.writer is writer


# ---------------------------------------------------------------------------
# create_udp_client edge cases
# ---------------------------------------------------------------------------


def _patch_dgconnect(result=None, side_effect=None):
    calls = []

    async def fake_connect(remote, local_addr=None, allow_broadcast=False):
        calls.append({"remote": remote, "local_addr": local_addr})
        if side_effect is not None:
            return side_effect(remote, local_addr)
        return result

    return mock.patch.object(cf, "dgconnect", fake_connect), calls


@pytest.mark.asyncio
async def test_udp_multicast_empty_address_list_uses_any_interface():
    writer = mock.MagicMock()
    patcher, calls = _patch_dgconnect(writer)
    with patcher:
        reader, out = await cf.create_udp_client(
            urlparse("udp+wo://239.2.3.1:6969"), multicast_local_addrs=" , "
        )
    assert reader is None
    assert out is writer
    assert [c["local_addr"] for c in calls] == [("0.0.0.0", 0)]
    # INADDR_ANY: no explicit IP_MULTICAST_IF is selected.
    opts = [c[0][1] for c in writer.socket.setsockopt.call_args_list]
    assert socket.IP_MULTICAST_TTL in opts
    assert socket.IP_MULTICAST_IF not in opts


@pytest.mark.asyncio
async def test_udp_writer_all_interfaces_failing_raises_first_error():
    clients = []

    def make(remote, local_addr):
        client = mock.MagicMock()
        client.socket.setsockopt.side_effect = OSError(errno.ENODEV, local_addr[0])
        clients.append(client)
        return client

    patcher, _ = _patch_dgconnect(side_effect=make)
    with patcher:
        with pytest.raises(OSError) as excinfo:
            await cf.create_udp_client(
                urlparse("udp+wo://239.2.3.1:6969"),
                multicast_local_addrs="192.0.2.10 192.0.2.11",
            )
    assert excinfo.value.errno == errno.ENODEV
    assert "192.0.2.10" in str(excinfo.value)
    assert len(clients) == 2
    for client in clients:
        client.close.assert_called_once()


@pytest.mark.asyncio
async def test_udp_broadcast_writer_enables_so_broadcast():
    writer = mock.MagicMock()
    patcher, _ = _patch_dgconnect(writer)
    with patcher:
        _, out = await cf.create_udp_client(
            urlparse("udp+broadcast+wo://192.0.2.255:6969")
        )
    assert out is writer
    writer.socket.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows binds all")
@pytest.mark.asyncio
async def test_udp_reader_bind_in_use_is_not_masked_and_closes_writer():
    holder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    holder.bind(("127.0.0.1", 0))
    port = holder.getsockname()[1]
    writer = mock.MagicMock()
    patcher, _ = _patch_dgconnect(writer)
    try:
        with patcher:
            with pytest.raises(OSError) as excinfo:
                await cf.create_udp_client(urlparse(f"udp://127.0.0.1:{port}"))
    finally:
        holder.close()
    assert excinfo.value.errno == errno.EADDRINUSE
    writer.close.assert_called_once()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows binds all")
@pytest.mark.asyncio
async def test_udp_broadcast_reader_bind_error_not_retried_on_any():
    """Broadcast keeps binding to the named address; errors propagate."""
    with pytest.raises(OSError) as excinfo:
        await cf.create_udp_client(urlparse("udp+broadcast+ro://192.0.2.10:0"))
    assert excinfo.value.errno == errno.EADDRNOTAVAIL


@pytest.mark.asyncio
async def test_udp_reuseport_unavailable_is_tolerated():
    real_socket = socket.socket

    class NoReusePort(real_socket):
        def setsockopt(self, level, option, value):
            if option == getattr(socket, "SO_REUSEPORT", object()):
                raise OSError(errno.ENOPROTOOPT, "no reuseport")
            return super().setsockopt(level, option, value)

    with mock.patch.object(cf.socket, "socket", NoReusePort):
        reader, writer = await cf.create_udp_client(
            urlparse("udp+broadcast+ro://0.0.0.0:0")
        )
    try:
        assert writer is None
        assert reader.socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
    finally:
        reader.close()


@pytest.mark.asyncio
async def test_udp_multicast_membership_failure_closes_everything():
    writer = mock.MagicMock()
    fake_reader = mock.MagicMock()
    fake_reader.socket.setsockopt.side_effect = OSError(errno.ENODEV, "no iface")
    patcher, _ = _patch_dgconnect(writer)
    with patcher, mock.patch.object(cf, "from_socket", _awaitable(fake_reader)):
        with pytest.raises(OSError) as excinfo:
            await cf.create_udp_client(urlparse("udp://239.2.3.1:0"))
    assert excinfo.value.errno == errno.ENODEV
    fake_reader.close.assert_called_once()
    writer.close.assert_called_once()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows binds all")
@pytest.mark.asyncio
async def test_udp_multicast_reader_joins_group():
    reader, writer = await cf.create_udp_client(urlparse("udp+ro://239.2.3.1:0"))
    try:
        assert writer is None
        assert reader.socket.getsockname()[0] == "239.2.3.1"
    finally:
        reader.close()


@pytest.mark.asyncio
async def test_udp_reader_none_from_socket_returns_writer():
    writer = mock.MagicMock()
    patcher, _ = _patch_dgconnect(writer)
    with patcher, mock.patch.object(cf, "from_socket", _awaitable(None)):
        reader, out = await cf.create_udp_client(urlparse("udp://127.0.0.1:0"))
    assert reader is None
    assert out is writer


# ---------------------------------------------------------------------------
# TLS client / SSL context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_limit", [None, "131072"])
async def test_create_tls_client_passes_expected_hostname(configured_limit):
    ctx = mock.MagicMock()
    ctx.check_hostname = True
    values = {"PYTAK_TLS_SERVER_EXPECTED_HOSTNAME": "takserver.example.com"}
    if configured_limit is not None:
        values["STREAM_LIMIT"] = configured_limit
    config = _section(values)
    opener = _awaitable(("r", "w"))
    with mock.patch.object(cf, "get_ssl_ctx", return_value=ctx), mock.patch.object(
        cf.asyncio, "open_connection", opener
    ):
        result = await cf.create_tls_client(
            config, urlparse("tls://[2001:db8::1]:8089")
        )
    assert result == ("r", "w")
    args, kwargs = opener.calls[0]
    assert args == ("2001:db8::1", 8089)
    assert kwargs == {
        "ssl": ctx,
        "server_hostname": "takserver.example.com",
        "limit": (
            int(configured_limit)
            if configured_limit is not None
            else pytak.DEFAULT_STREAM_LIMIT
        ),
    }


@pytest.mark.asyncio
async def test_create_tls_client_no_hostname_check_and_verify_error():
    ctx = mock.MagicMock()
    ctx.check_hostname = False
    config = _section({"PYTAK_TLS_SERVER_EXPECTED_HOSTNAME": "ignored.example.com"})
    opener = _awaitable(exc=ssl.SSLCertVerificationError("bad cert"))
    with mock.patch.object(cf, "get_ssl_ctx", return_value=ctx), mock.patch.object(
        cf.asyncio, "open_connection", opener
    ):
        with pytest.raises(SyntaxError, match="Could not verify TLS Certificate"):
            await cf.create_tls_client(
                config, urlparse("tls://takserver.example.com:8089")
            )
    assert opener.calls[0][1]["server_hostname"] is None


@pytest.mark.asyncio
async def test_create_tls_client_enrolls_when_credentials_set(capsys):
    enrollment = mock.MagicMock()
    seen = {}

    async def begin_enrollment(**kwargs):
        seen.update(kwargs)

    enrollment.begin_enrollment = begin_enrollment
    ctx = mock.MagicMock()
    ctx.check_hostname = False
    config = _section(
        {
            "PYTAK_TLS_CERT_ENROLLMENT_USERNAME": "user",
            "PYTAK_TLS_CERT_ENROLLMENT_PASSWORD": "example-password",
        }
    )
    with mock.patch(
        "pytak.crypto_classes.CertificateEnrollment", return_value=enrollment
    ), mock.patch.object(
        cf, "get_ssl_ctx", return_value=ctx
    ) as get_ctx, mock.patch.object(
        cf.asyncio, "open_connection", _awaitable(("r", "w"))
    ):
        await cf.create_tls_client(config, urlparse("tls://takserver.example.com:8089"))

    try:
        tls_config = get_ctx.call_args[0][0]
        assert seen["domain"] == "takserver.example.com"
        assert seen["username"] == "user"
        assert seen["password"] == "example-password"
        assert seen["passphrase"]
        assert tls_config["PYTAK_TLS_CLIENT_CERT"] == seen["output_path"]
        assert tls_config["PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE"] == seen["passphrase"]
    finally:
        os.remove(seen["output_path"])


def test_get_tls_config_requires_required_params(monkeypatch):
    monkeypatch.setattr(pytak, "DEFAULT_TLS_PARAMS_REQ", ("PYTAK_TLS_CLIENT_CERT",))
    with pytest.raises(SyntaxError, match="required TLS Params"):
        cf.get_tls_config(_section({"COT_URL": "tls://takserver.example.com:8089"}))


def test_get_ssl_ctx_requires_client_cert():
    with pytest.raises(SyntaxError, match="Missing value"):
        cf.get_ssl_ctx(_section({}))


def test_get_ssl_ctx_missing_cert_file(tmp_path):
    with pytest.raises(SyntaxError, match="PYTAK_TLS_CLIENT_CERT"):
        cf.get_ssl_ctx(_section({"PYTAK_TLS_CLIENT_CERT": str(tmp_path / "x.pem")}))


def test_get_ssl_ctx_missing_key_file(tmp_path):
    with pytest.raises(SyntaxError, match="PYTAK_TLS_CLIENT_KEY"):
        cf.get_ssl_ctx(
            _section(
                {
                    "PYTAK_TLS_CLIENT_CERT": str(DATA_DIR / "test_user_cert.pem"),
                    "PYTAK_TLS_CLIENT_KEY": str(tmp_path / "missing.key"),
                }
            )
        )


def test_get_ssl_ctx_p12_extraction_missing_files(tmp_path):
    p12 = tmp_path / "client.p12"
    p12.write_bytes(b"p12")
    paths = {
        "cert_pem_path": str(tmp_path / "gone-cert.pem"),
        "pk_pem_path": str(tmp_path / "gone-key.pem"),
        "ca_pem_path": None,
    }
    with mock.patch.object(cf, "convert_cert", return_value=paths):
        with pytest.raises(ValueError, match="Error opening resource") as excinfo:
            cf.get_ssl_ctx(_section({"PYTAK_TLS_CLIENT_CERT": str(p12)}))
    assert isinstance(excinfo.value.__cause__, SystemError)


def test_get_ssl_ctx_verifies_with_cafile():
    ctx = cf.get_ssl_ctx(
        _section(
            {
                "PYTAK_TLS_CLIENT_CERT": str(DATA_DIR / "test_user_cert.pem"),
                "PYTAK_TLS_CLIENT_KEY": str(DATA_DIR / "test_pk.pem"),
                "PYTAK_TLS_CLIENT_CAFILE": str(DATA_DIR / "test_ca_cert.pem"),
            }
        )
    )
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.cert_store_stats()["x509_ca"] >= 1


# ---------------------------------------------------------------------------
# main / reconnect supervisor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_stops_importing_on_eof(monkeypatch, caplog):
    module = types.ModuleType("fake_cov_app")
    module.create_tasks = lambda config, clitool: set()
    monkeypatch.setitem(sys.modules, "fake_cov_app", module)
    calls = []

    async def create_workers(self, config):
        calls.append(config.name)
        if config.name == "second":
            raise EOFError("done")

    async def run(self):
        calls.append("run")

    monkeypatch.setattr(pytak.CLITool, "create_workers", create_workers)
    monkeypatch.setattr(pytak.CLITool, "run", run)
    full = ConfigParser()
    full.read_string(
        "[fake_cov_app]\nIMPORT_OTHER_CONFIGS=yes\n[second]\nA=1\n[third]\nA=2\n"
    )
    await cf.main("fake_cov_app", full["fake_cov_app"], full)
    assert calls == ["fake_cov_app", "second", "run"]
    assert "No more configs" in caplog.text


def test_retryable_transport_error_without_aiohttp():
    with _block_import("aiohttp"):
        assert cf._retryable_transport_error(ValueError("x")) is False


@pytest.mark.parametrize(
    "values,match",
    [
        ({"PYTAK_RECONNECT_INITIAL": "0"}, "greater than zero"),
        ({"PYTAK_RECONNECT_JITTER": "1"}, "JITTER"),
        ({"PYTAK_RECONNECT_INITIAL": "10", "PYTAK_RECONNECT_MAX": "5"}, "MAX"),
        ({"PYTAK_RECONNECT_FACTOR": "0.5"}, "FACTOR"),
    ],
)
@pytest.mark.asyncio
async def test_supervise_with_reconnect_validates_tuning(values, match):
    run_once = _awaitable()
    with pytest.raises(ValueError, match=match):
        await cf.supervise_with_reconnect(_section(values), run_once)
    assert run_once.calls == []


@pytest.mark.asyncio
async def test_supervise_with_reconnect_raises_fatal_errors():
    run_once = _awaitable(exc=ValueError("bad config"))
    with pytest.raises(ValueError, match="bad config"):
        await cf.supervise_with_reconnect(_section({}), run_once)
    assert len(run_once.calls) == 1


@pytest.mark.asyncio
async def test_supervise_with_reconnect_applies_jitter():
    attempts = []

    async def run_once():
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionRefusedError(errno.ECONNREFUSED, "refused")

    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    config = _section(
        {
            "PYTAK_RECONNECT_INITIAL": "2",
            "PYTAK_RECONNECT_MAX": "60",
            "PYTAK_RECONNECT_JITTER": "0.5",
        }
    )
    with mock.patch.object(cf.asyncio, "sleep", fake_sleep), mock.patch.object(
        cf.random, "uniform", return_value=1.25
    ) as uniform:
        await cf.supervise_with_reconnect(config, run_once)

    uniform.assert_called_once_with(0.5, 1.5)
    assert sleeps == [2.5]
    assert len(attempts) == 2


# ---------------------------------------------------------------------------
# cli()
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_env(monkeypatch):
    module = types.ModuleType("fake_cli_app")
    module.DEFAULT_COT_STALE = "120"
    monkeypatch.setitem(sys.modules, "fake_cli_app", module)
    # cli() builds its DEFAULT section from os.environ; keep it minimal so the
    # test does not depend on the host environment.
    monkeypatch.setattr(os, "environ", {"HOME": "/nonexistent"})
    captured = {}

    def fake_run_with_reconnect(app_name, config, full_config, tak_url):
        captured.update(
            app_name=app_name, config=config, full_config=full_config, tak_url=tak_url
        )
        return "coroutine-sentinel"

    def fake_asyncio_run(coro, debug=False):
        captured.update(coro=coro, debug=debug)

    monkeypatch.setattr(cf, "run_with_reconnect", fake_run_with_reconnect)
    monkeypatch.setattr(cf.asyncio, "run", fake_asyncio_run)
    return captured


def test_cli_without_config_file_uses_defaults(cli_env, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(tmp_path / "missing.ini")])
    cf.cli("fake_cli_app")
    config = cli_env["config"]
    assert cli_env["coro"] == "coroutine-sentinel"
    assert not cli_env["debug"]
    assert cli_env["tak_url"] == ""
    assert config.name == "fake_cli_app"
    assert config["COT_URL"] == pytak.DEFAULT_COT_URL
    assert config["COT_STALE"] == "120"


def test_cli_reads_config_file_tak_url_and_debug(
    cli_env, monkeypatch, tmp_path, capsys
):
    tak_url = (
        "tak://com.atakmap.app/enroll?host=takserver.example.com&username=u&token=t"
    )
    ini = tmp_path / "config.ini"
    ini.write_text(f"[fake_cli_app]\nCOT_URL = {tak_url}\nDEBUG = 1\n")
    monkeypatch.setattr(sys, "argv", ["prog", "--CONFIG_FILE", str(ini)])
    cf.cli("fake_cli_app")
    assert cli_env["tak_url"] == tak_url
    assert cli_env["debug"] is True
    assert "Showing Config" in capsys.readouterr().out


def test_cli_applies_pref_package(cli_env, monkeypatch, tmp_path):
    package = tmp_path / "prefs.zip"
    package.write_bytes(b"zip")
    monkeypatch.setattr(sys, "argv", ["prog", "-c", "", "-p", str(package)])
    with mock.patch.object(
        cf,
        "read_pref_package",
        return_value={"COT_URL": "tls://takserver.example.com:8089"},
    ) as reader:
        cf.cli("fake_cli_app")
    reader.assert_called_once_with(str(package))
    assert cli_env["config"]["COT_URL"] == "tls://takserver.example.com:8089"
