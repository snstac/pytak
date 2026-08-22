#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# client_functions.py from https://github.com/snstac/pytak
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""PyTAK functions for creating network & CLI TAK clients."""

import argparse
import asyncio
import errno
import hashlib
import importlib
import ipaddress
import logging
import os
import platform
import pprint
import random
import re
import secrets
import socket
import ssl
import struct
import sys
import warnings
import tempfile

from asyncio import get_running_loop
from configparser import ConfigParser, SectionProxy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import ParseResult, urlparse, parse_qs, unquote
from typing import Any, Awaitable, Callable, Optional, Tuple, Union

import pytak

from pytak.functions import unzip_file, find_file, load_preferences, connectString2url

from pytak.asyncio_dgram import (
    DatagramClient,
    DatagramFanoutClient,
    connect as dgconnect,
    from_socket,
)

from pytak.crypto_functions import convert_cert


def parse_tak_url(tak_url: str) -> dict:
    """Parse a TAK enrollment deep-link URL.

    Supported format:
        tak://com.atakmap.app/enroll?host=<host>&username=<user>&token=<secret>

    ``host`` may include an explicit port (e.g. ``takserver.example.com:8443``).
    If omitted, PyTAK uses the default TAK WebSocket/Marti port.

    Returns a dict with keys: hostname, port, username, token, explicit_port.
    """
    parsed = urlparse(tak_url.strip())
    if parsed.scheme.lower() != "tak":
        raise ValueError(f"Expected tak:// URL, got scheme {parsed.scheme!r}")

    qs = parse_qs(parsed.query, keep_blank_values=False)

    def _one(param: str) -> str:
        vals = qs.get(param)
        if not vals or not str(vals[0]).strip():
            raise ValueError(f"TAK URL missing required parameter: {param!r}")
        return unquote(str(vals[0]).strip())

    host_param = _one("host")
    username = _one("username")
    token = _one("token")

    if ":" in host_param:
        hostname, port_str = host_param.rsplit(":", 1)
        try:
            port = int(port_str)
            explicit_port = True
        except ValueError:
            hostname = host_param
            port = pytak.DEFAULT_TAK_STREAMING_PORT
            explicit_port = False
    else:
        hostname = host_param
        port = pytak.DEFAULT_TAK_STREAMING_PORT
        explicit_port = False

    return {
        "hostname": hostname,
        "port": port,
        "username": username,
        "token": token,
        "explicit_port": explicit_port,
    }


def _cert_cache_paths(hostname: str, port: int, username: str) -> Tuple[str, str]:
    """Return (p12_path, pass_path) for the on-disk cert cache.

    The cache key incorporates *hostname*, *port*, and *username* so that
    connections to the same host on different ports, or to a rebuilt server
    instance where the CA may have changed, are not confused with one another.
    The SHA-256 prefix is 32 hex characters (128 bits) to reduce accidental
    collision probability.
    """
    cache_dir = Path.home() / ".pytak" / "certs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{hostname}:{port}:{username}".encode()).hexdigest()[:32]
    return str(cache_dir / f"{key}.p12"), str(cache_dir / f"{key}.pass")


def _cert_cache_server_fingerprint_path(p12_path: str) -> str:
    """Return the sidecar path storing the server certificate fingerprint."""
    return str(Path(p12_path).with_suffix(".server"))


def _legacy_cert_cache_paths(hostname: str, username: str) -> Tuple[str, str]:
    """Return (p12_path, pass_path) using the pre-7.3.13 cache key format.

    The old key included only *hostname* and *username* with a 16-character
    SHA-256 prefix.  This helper is used as a migration fallback: if the new
    cache path has no cert but the legacy path does, the legacy cert is reused
    for one more connection rather than forcing unnecessary re-enrollment on
    upgrade.  The legacy files are **not** renamed or deleted automatically.
    """
    cache_dir = Path.home() / ".pytak" / "certs"
    key = hashlib.sha256(f"{hostname}:{username}".encode()).hexdigest()[:16]
    return str(cache_dir / f"{key}.p12"), str(cache_dir / f"{key}.pass")


def _cached_cert_valid(
    p12_path: str,
    passphrase: str,
    buffer_days: int = pytak.DEFAULT_CERT_CACHE_BUFFER_DAYS,
) -> bool:
    """Return True if the cached p12 exists and won't expire within buffer_days."""
    if not os.path.exists(p12_path):
        return False
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12

        with open(p12_path, "rb") as f:
            data = f.read()
        pw = passphrase.encode("utf-8") if passphrase else None
        _, cert, _ = pkcs12.load_key_and_certificates(data, pw)
        if cert is None:
            return False
        now = datetime.now(timezone.utc)
        try:
            expiry = cert.not_valid_after_utc
        except AttributeError:
            expiry = cert.not_valid_after.replace(tzinfo=timezone.utc)
        return now < (expiry - timedelta(days=buffer_days))
    except Exception as exc:
        logging.debug("Cached cert check failed: %s", exc)
        return False


def _server_cert_fingerprint(hostname: str, port: int, timeout: float = 5.0) -> str:
    """Return the SHA-256 fingerprint for a server TLS certificate."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with socket.create_connection((hostname, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as tls_sock:
            der_cert = tls_sock.getpeercert(binary_form=True)

    if not der_cert:
        raise RuntimeError(f"No TLS peer certificate from {hostname}:{port}")
    return hashlib.sha256(der_cert).hexdigest()


async def _server_cert_fingerprint_async(hostname: str, port: int) -> Optional[str]:
    """Best-effort async wrapper for reading a server TLS cert fingerprint."""
    loop = get_running_loop()
    try:
        return await loop.run_in_executor(
            None, _server_cert_fingerprint, hostname, port
        )
    except Exception as exc:
        logging.debug(
            "Could not read TAK server certificate fingerprint for %s:%s: %s",
            hostname, port, exc,
        )
        return None


async def resolve_tak_url(tak_url: str) -> dict:
    """Resolve a tak:// onboarding URL to PyTAK TLS config parameters.

    Parses the URL, checks the cert cache (~/.pytak/certs/), re-enrolls only
    when no valid cached cert is found, and returns a config dict ready for
    ``config.update()``.

        The returned dict sets:
            - ``COT_URL`` → ``wss://<hostname>:8443/takproto/1`` by default when the
                URL omits an explicit port
            - ``COT_URL`` → ``wss://<hostname>:<port>/takproto/1`` when the URL
                explicitly names a non-streaming port such as ``8443``
            - ``COT_URL`` → ``tls://<hostname>:8089`` when the URL explicitly names
                the TAK streaming port
      - ``PYTAK_TLS_CLIENT_CERT`` → path to the cached .p12
      - ``PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE`` → p12 password
      - ``PYTAK_TLS_DONT_VERIFY`` / ``PYTAK_TLS_DONT_CHECK_HOSTNAME`` → ``"1"``
        (TAK servers routinely use self-signed certificates)
    """
    params = parse_tak_url(tak_url)
    hostname = params["hostname"]
    port = params["port"]
    explicit_port = params["explicit_port"]
    username = params["username"]
    token = params["token"]

    new_p12_path, new_pass_path = _cert_cache_paths(hostname, port, username)
    new_server_fp_path = _cert_cache_server_fingerprint_path(new_p12_path)
    logging.debug(
        "TAK cert cache path (new key): %s (host=%s port=%s user=%s)",
        new_p12_path, hostname, port, username,
    )

    # Resolve which cache entry to read: prefer new-format; fall back to legacy
    # when upgrading from pre-7.3.13 so we do not force unnecessary re-enrollment.
    p12_path, pass_path = new_p12_path, new_pass_path
    server_fp_path = new_server_fp_path
    if not os.path.exists(new_p12_path):
        legacy_p12, legacy_pass = _legacy_cert_cache_paths(hostname, username)
        if os.path.exists(legacy_p12):
            logging.info(
                "TAK cert cache: new key miss - falling back to legacy cache "
                "path for %s@%s (legacy: %s)",
                username, hostname, legacy_p12,
            )
            p12_path, pass_path = legacy_p12, legacy_pass
            server_fp_path = _cert_cache_server_fingerprint_path(legacy_p12)

    passphrase: str = ""
    if os.path.exists(pass_path):
        with open(pass_path) as f:
            passphrase = f.read().strip()

    fingerprint_port = (
        port
        if explicit_port
        else pytak.DEFAULT_MARTI_PORT
    )
    current_server_fp = await _server_cert_fingerprint_async(hostname, fingerprint_port)

    cached_server_fp = ""
    if os.path.exists(server_fp_path):
        with open(server_fp_path) as f:
            cached_server_fp = f.read().strip()

    server_cert_changed = (
        bool(current_server_fp)
        and bool(cached_server_fp)
        and current_server_fp != cached_server_fp
    )

    if server_cert_changed:
        logging.info(
            "TAK cert cache stale: server certificate changed for %s:%s",
            hostname, fingerprint_port,
        )

    if (
        passphrase
        and _cached_cert_valid(p12_path, passphrase)
        and not server_cert_changed
    ):
        logging.info(
            "TAK cert cache hit: using cached certificate for %s@%s:%s",
            username, hostname, port,
        )
    else:
        logging.info(
            "TAK cert cache miss: enrolling new certificate for %s@%s:%s",
            username, hostname, port,
        )
        from pytak.crypto_classes import CertificateEnrollment

        passphrase = secrets.token_urlsafe(
            pytak.DEFAULT_TLS_ENROLLMENT_CERT_PASSPHRASE_LENGTH
        )
        enrollment = CertificateEnrollment()
        # Enrollment always writes to the new-format path.
        await enrollment.begin_enrollment(
            domain=hostname,
            username=username,
            password=token,
            output_path=new_p12_path,
            passphrase=passphrase,
            trust_all=True,
        )
        if not os.path.exists(new_p12_path):
            raise RuntimeError(
                f"TAK certificate enrollment failed for {username}@{hostname}"
            )
        with open(new_pass_path, "w") as f:
            f.write(passphrase)
        os.chmod(new_pass_path, 0o600)
        os.chmod(new_p12_path, 0o600)
        if current_server_fp:
            with open(new_server_fp_path, "w") as f:
                f.write(current_server_fp)
            os.chmod(new_server_fp_path, 0o600)
        logging.info("TAK client certificate cached at %s", new_p12_path)
        # Return dict will use new-format paths.
        p12_path = new_p12_path
        server_fp_path = new_server_fp_path

    if current_server_fp and not cached_server_fp and os.path.exists(p12_path):
        with open(server_fp_path, "w") as f:
            f.write(current_server_fp)
        os.chmod(server_fp_path, 0o600)

    if explicit_port and port == pytak.DEFAULT_TAK_STREAMING_PORT:
        cot_url = f"tls://{hostname}:{port}"
    else:
        if not explicit_port:
            port = pytak.DEFAULT_MARTI_PORT
        cot_url = f"wss://{hostname}:{port}{pytak.DEFAULT_WS_PATH}"

    return {
        "COT_URL": cot_url,
        "PYTAK_TLS_CLIENT_CERT": p12_path,
        "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE": passphrase,
        "PYTAK_TLS_DONT_VERIFY": "1",
        "PYTAK_TLS_DONT_CHECK_HOSTNAME": "1",
    }


async def _marti_session(config):
    """Return (aiohttp.ClientSession, base_url, client_uid) for a marti:// COT_URL.

    Uses the existing PYTAK_TLS_* config params for mTLS when present;
    falls back to unverified SSL for ``marti://`` and plain HTTP for ``marti+http://``.
    """
    try:
        import aiohttp
    except ImportError as exc:
        raise ImportError(
            "Marti HTTP transport requires aiohttp. "
            "Install with: python3 -m pip install pytak[with-aiohttp]"
        ) from exc

    cot_url = get_cot_url(config)
    use_tls = "http" not in cot_url.scheme  # marti:// → TLS; marti+http:// → plain
    port = cot_url.port or pytak.DEFAULT_MARTI_PORT
    scheme = "https" if use_tls else "http"
    base_url = f"{scheme}://{cot_url.hostname}:{port}"
    client_uid = config.get(
        "MARTI_COT_UID",
        config.get("COT_HOST_ID", pytak.DEFAULT_HOST_ID),
    )

    ssl_ctx: Any = None
    if use_tls:
        client_cert = config.get("PYTAK_TLS_CLIENT_CERT")
        if client_cert:
            try:
                ssl_ctx = get_ssl_ctx(get_tls_config(config))
            except Exception:
                ssl_ctx = False  # fall back to no-verify
        else:
            ssl_ctx = False  # no cert configured → skip verification

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    session = aiohttp.ClientSession(connector=connector)
    return session, base_url, client_uid


async def marti_txworker_factory(
    queue: asyncio.Queue, config: SectionProxy
) -> "pytak.MartiTXWorker":
    """Create a MartiTXWorker that POSTs CoT to the Marti REST API."""
    session, base_url, client_uid = await _marti_session(config)
    return pytak.MartiTXWorker(queue, config, session, base_url, client_uid)


async def marti_rxworker_factory(
    queue: asyncio.Queue, config: SectionProxy
) -> "pytak.MartiRXWorker":
    """Create a MartiRXWorker that polls CoT from the Marti REST API."""
    session, base_url, _ = await _marti_session(config)
    poll_interval = int(
        config.get("MARTI_POLL_INTERVAL", pytak.DEFAULT_MARTI_POLL_INTERVAL)
    )
    seconds_ago = int(
        config.get("MARTI_POLL_SECONDS_AGO", pytak.DEFAULT_MARTI_POLL_SECONDS_AGO)
    )
    return pytak.MartiRXWorker(
        queue, config, session, base_url, poll_interval, seconds_ago
    )


async def ws_factory(
    tx_queue: asyncio.Queue, rx_queue: asyncio.Queue, config: SectionProxy
) -> Tuple["pytak.WSTXWorker", "pytak.WSRXWorker"]:
    """Create a WSTXWorker and WSRXWorker for ws:// or wss:// connections.

    Both workers share a single persistent WebSocket connection.  The TX
    worker encodes CoT XML as TAK Protocol v1 Protobuf (STREAM) before
    sending; the RX worker decodes incoming binary frames back to CoT bytes.

    Requires ``pytak[with_aiohttp]``.  TAK Protocol v1 encoding/decoding also
    requires ``pytak[with_takproto]`` (falls back to raw bytes if absent).
    """
    try:
        import aiohttp
    except ImportError as exc:
        raise ImportError(
            "WebSocket transport requires aiohttp. "
            "Install with: python3 -m pip install pytak[with-aiohttp]"
        ) from exc

    cot_url = get_cot_url(config)
    use_tls = cot_url.scheme.lower() == "wss"

    ssl_ctx: Any = None
    if use_tls:
        tls_config = get_tls_config(config)
        has_cert = bool(tls_config.get("PYTAK_TLS_CLIENT_CERT"))
        if has_cert:
            ssl_ctx = get_ssl_ctx(tls_config)
        else:
            # No client cert — connect with server-cert verification disabled
            # (TAK servers routinely use self-signed certs)
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = _ssl.CERT_NONE

    raw_url = config.get("COT_URL", "")
    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(raw_url, ssl=ssl_ctx)
    except aiohttp.WSServerHandshakeError as exc:
        await session.close()
        if exc.status == 403:
            # Server rejected the cert — clear the cert cache so the next
            # run forces a fresh enrollment with the new token.
            cert_path = config.get("PYTAK_TLS_CLIENT_CERT", "")
            if cert_path and os.path.exists(cert_path):
                pass_path = cert_path.replace(".p12", ".pass")
                for p in (cert_path, pass_path):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                raise PermissionError(
                    f"WebSocket connection rejected (403): server does not trust "
                    f"the cached certificate. The stale cert has been deleted. "
                    f"Re-run pytak with the same tak:// URL to re-enroll."
                ) from exc
        raise
    except Exception:
        await session.close()
        raise

    tx_worker = pytak.WSTXWorker(tx_queue, config, ws, session)
    rx_worker = pytak.WSRXWorker(rx_queue, config, ws, session)
    return tx_worker, rx_worker


async def mqtt_factory(
    tx_queue: asyncio.Queue,
    rx_queue: asyncio.Queue,
    config: SectionProxy,
) -> Tuple[Optional[Any], Optional[Any]]:
    """Create MQTTTXWorker and/or MQTTRXWorker for mqtt:// or mqtts:// URLs.

    The MQTT topic is taken from the URL path.  Both workers share a single
    persistent MQTT connection.  ``+wo`` and ``+ro`` modifiers select
    write-only or read-only mode.

    Requires ``pytak[with-mqtt]``.  TAK Protocol v1 encoding/decoding also
    requires ``pytak[with-takproto]`` when ``TAK_PROTO`` is set.
    """
    try:
        import aiomqtt  # noqa: F401 pylint: disable=unused-import
    except ImportError as exc:
        raise ImportError(
            "MQTT transport requires aiomqtt. "
            "Install with: python3 -m pip install pytak[with-mqtt]"
        ) from exc

    from pytak.functions import parse_mqtt_url

    raw_url = config.get("COT_URL", "")
    scheme = raw_url.split("://")[0].lower() if "://" in raw_url else ""
    _, write_only, read_only = pytak.parse_cot_scheme(scheme)

    cot_url = get_cot_url(config)
    parts = parse_mqtt_url(cot_url)

    username = parts.username or config.get("MQTT_USERNAME")
    password = parts.password or config.get("MQTT_PASSWORD")
    qos = int(config.get("MQTT_QOS", pytak.DEFAULT_MQTT_QOS))
    keepalive = int(config.get("MQTT_KEEPALIVE", pytak.DEFAULT_MQTT_KEEPALIVE))
    client_id = config.get("MQTT_CLIENT_ID", pytak.DEFAULT_HOST_ID)

    tls_context: Any = None
    if parts.use_tls:
        tls_config = get_tls_config(config)
        has_cert = bool(tls_config.get("PYTAK_TLS_CLIENT_CERT"))
        if has_cert:
            tls_context = get_ssl_ctx(tls_config)
        else:
            import ssl as _ssl

            tls_context = _ssl.create_default_context()
            tls_context.check_hostname = False
            tls_context.verify_mode = _ssl.CERT_NONE

    import aiomqtt

    client = aiomqtt.Client(
        hostname=parts.host,
        port=parts.port,
        username=username,
        password=password,
        identifier=client_id,
        keepalive=keepalive,
        tls_context=tls_context,
    )

    from pytak.classes import MQTTTXWorker, MQTTRXWorker, _MQTTSession

    await client.__aenter__()
    session = _MQTTSession(client)

    try:
        if not write_only:
            await client.subscribe(parts.topic, qos=qos)
    except Exception:
        await session.close()
        raise

    tx_worker: Optional[MQTTTXWorker] = None
    rx_worker: Optional[MQTTRXWorker] = None

    if not read_only:
        tx_worker = MQTTTXWorker(tx_queue, config, client, parts.topic, qos, session)
    if not write_only:
        rx_worker = MQTTRXWorker(rx_queue, config, client, session)

    return tx_worker, rx_worker


def get_cot_url(config) -> ParseResult:
    """Verify and parse a raw COT_URL."""
    raw_cot_url: str = config.get("COT_URL", pytak.DEFAULT_COT_URL)

    if "://" not in raw_cot_url:
        warnings.warn(f"Invalid COT_URL={raw_cot_url}", SyntaxWarning)
        raise SyntaxError(
            "Specify COT_URL as a full URL. For example: tcp://tak.example.com:1234"
        )

    cot_url: ParseResult = urlparse(raw_cot_url)
    return cot_url


async def protocol_factory(  # NOQA pylint: disable=too-many-locals,too-many-branches,too-many-statements
    config: SectionProxy,
) -> Any:
    """Create input, output, or input-output clients for network and file protocols.

    Parameters
    ----------
    config : `SectionProxy`
        Configuration parameters & values.

    Returns
    -------
    `Any`
        Varies by input-output protocol.
    """
    reader: Any = None
    writer: Any = None

    cot_url: ParseResult = get_cot_url(config)
    base_scheme, _, _ = pytak.parse_cot_scheme(cot_url.scheme.lower())

    # TCP
    if base_scheme == "tcp":
        host, port = pytak.parse_url(cot_url)
        reader, writer = await asyncio.open_connection(host, port)

    # TLS
    elif base_scheme in ("tls", "ssl"):
        reader, writer = await create_tls_client(config, cot_url)

    # UDP
    elif "udp" in base_scheme:
        # Support Linux hosts with no default gateway defined with local addr.
        # The plural setting deliberately remains a string here: create_udp_client
        # owns validation and backward-compatible fallback to the singular value.
        local_addr = (
            config.get(
                "PYTAK_MULTICAST_LOCAL_ADDR", pytak.DEFAULT_PYTAK_MULTICAST_LOCAL_ADDR
            ),
            0,
        )
        local_addrs = config.get("PYTAK_MULTICAST_LOCAL_ADDRS")
        multicast_ttl = config.get("PYTAK_MULTICAST_TTL", 1)
        reader, writer = await pytak.create_udp_client(
            cot_url, local_addr, multicast_ttl, local_addrs
        )

    # LOG
    elif "log" in base_scheme:
        if cot_url.hostname:
            dest: str = cot_url.hostname.lower()
            if "stderr" in dest:
                writer = sys.stderr.buffer
            else:
                writer = sys.stdout.buffer
    # File output
    elif "file" in base_scheme:
        path = cot_url.netloc + cot_url.path
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        writer = open(file_path, 'wb+')

    # TAK onboarding URL — enroll, cache cert, then connect as TLS
    elif base_scheme == "tak":
        tak_config = await resolve_tak_url(config.get("COT_URL", ""))
        config.update(tak_config)
        reader, writer = await create_tls_client(config, urlparse(tak_config["COT_URL"]))

    # Default
    if not reader and not writer:
        raise SyntaxError(
            "Invalid COT_URL protocol specified. "
            "See: https://pytak.rtfd.io/en/stable/configuration/"
        )

    return reader, writer


async def create_udp_client(
    url: ParseResult,
    local_addr=None,
    multicast_ttl=1,
    multicast_local_addrs=None,
) -> Tuple[Any, Any]:
    """Create an AsyncIO UDP network client for Unicast, Broadcast & Multicast.

    Parameters
    ----------
    url : `ParseResult`
        A parsed fully-qualified URL parsed with `urllib.parse.urlparse()`.
        An input to urparse() would be: udp://tak.example.com:4242

    Returns
    -------
    `DatagramClient`
        An AsyncIO UDP network stream client.
    """
    reader: Union[DatagramClient, None] = None
    rsock: Union[socket.socket, None] = None

    host, port = pytak.parse_url(url)

    local_addr = local_addr or "0.0.0.0"

    _, is_write_only, is_read_only = pytak.parse_cot_scheme(url.scheme)
    is_broadcast: bool = "broadcast" in url.scheme
    is_multicast: bool = "multicast" in url.scheme

    # Optimized: Single try-catch for IP address validation
    if not is_multicast:
        try:
            is_multicast = ipaddress.ip_address(host).is_multicast
        except ValueError:
            # It's probably not an ip address...
            pass

    def _local_host(value) -> str:
        if isinstance(value, (tuple, list)):
            return str(value[0])
        return str(value)

    def _multicast_hosts() -> Tuple[str, ...]:
        raw = multicast_local_addrs
        values = re.split(r"[\s,]+", str(raw).strip()) if raw else []
        if not values:
            values = [_local_host(local_addr)]
        hosts = []
        for value in values:
            if not value:
                continue
            address = str(ipaddress.IPv4Address(value))
            if address not in hosts:
                hosts.append(address)
        if not hosts:
            hosts.append("0.0.0.0")
        return tuple(hosts)

    multicast_hosts = _multicast_hosts() if is_multicast else ("0.0.0.0",)
    writer: Any = None

    if not is_read_only:
        clients = []
        failures = []
        for local_host in multicast_hosts:
            client = None
            try:
                client = await dgconnect(
                    (host, port),
                    local_addr=(local_host, 0),
                    allow_broadcast=is_broadcast,
                )
                if is_broadcast:
                    client.socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_BROADCAST, 1
                    )
                if is_multicast:
                    client.socket.setsockopt(
                        socket.IPPROTO_IP,
                        socket.IP_MULTICAST_TTL,
                        struct.pack("b", int(multicast_ttl)),
                    )
                    if local_host != "0.0.0.0":
                        client.socket.setsockopt(
                            socket.IPPROTO_IP,
                            socket.IP_MULTICAST_IF,
                            socket.inet_aton(local_host),
                        )
                clients.append(client)
            except (OSError, ValueError) as exc:
                if client is not None:
                    client.close()
                failures.append((local_host, exc))

        if not clients:
            if failures:
                raise failures[0][1]
            raise OSError(errno.ENETUNREACH, "No usable UDP output interface")
        if failures:
            logging.getLogger(__name__).warning(
                "Multicast output unavailable on %s; continuing on %s",
                ", ".join(item[0] for item in failures),
                ", ".join(client.sockname[0] for client in clients),
            )
        writer = clients[0] if len(clients) == 1 else DatagramFanoutClient(clients)

    if is_write_only:
        return reader, writer

    # Create the Reader
    rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # SO_REUSEADDR/SO_REUSEPORT MUST be set BEFORE bind() -- setting them
    # afterwards has no effect on a bind that already happened.
    #
    # They used to be applied after, which meant only ONE process per host could
    # subscribe to a given multicast group. Observed on an AryaOS box: the
    # neighbour-discovery daemon holds 239.2.3.1:6969, so gdltak died with
    #
    #   OSError: [Errno 98] Address already in use
    #
    # restarted 10 times, hit the systemd start limit and left the machine
    # `degraded`. Two subscribers to one CoT multicast group is a normal
    # arrangement, not an error.
    if is_broadcast:
        rsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    if is_broadcast or is_multicast:
        rsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            rsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            # Not every platform has SO_REUSEPORT; SO_REUSEADDR alone is enough
            # for multiple multicast subscribers on Linux.
            pass

    bindall = sys.platform == "win32"
    rsock.bind(("" if bindall else host, port))

    reader = await from_socket(rsock)

    if not reader:
        return reader, writer

    # Create Multicast Reader
    if is_multicast:
        group = int(ipaddress.IPv4Address(host))
        memberships = 0
        membership_errors = []
        for local_host in multicast_hosts:
            ip = (
                socket.INADDR_ANY
                if local_host == "0.0.0.0"
                else int(ipaddress.IPv4Address(local_host))
            )
            try:
                mreq = struct.pack("!LL", group, ip)
                reader.socket.setsockopt(
                    socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
                )
                memberships += 1
            except OSError as exc:
                membership_errors.append(exc)
        if not memberships:
            reader.close()
            if writer is not None:
                writer.close()
            raise membership_errors[0]

    return reader, writer


def get_tls_config(config: SectionProxy) -> SectionProxy:
    """Get the TLS config and ensures required TLS params are set.

    Parameters
    ----------
    config : `SectionProxy`
        Configuration parameters & values.

    Returns
    -------
    `SectionProxy`
        A PyTAK TLS configuration.
    """
    tls_config_req: dict = dict(
        zip(
            pytak.DEFAULT_TLS_PARAMS_REQ,
            [config.get(x) for x in pytak.DEFAULT_TLS_PARAMS_REQ],
        )
    )

    if not all(tls_config_req.values()):
        raise SyntaxError(
            f"Not all required TLS Params specified: {pytak.DEFAULT_TLS_PARAMS_REQ}"
        )

    tls_config_opt: dict = dict(
        zip(
            pytak.DEFAULT_TLS_PARAMS_OPT,
            [config.get(x) for x in pytak.DEFAULT_TLS_PARAMS_OPT],
        )
    )

    tls_config_req.update(tls_config_opt)

    return ConfigParser(dict(filter(lambda x: x[1], tls_config_req.items())))["DEFAULT"]


async def create_tls_client(
    config, cot_url
) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Create a two-way TLS socket.

    Establishing a socket requires:
    1. Enabling or disabling TLS Verifications.
    2. Establishing a TLS Context.
    3. Configuring an async TCP read-write socket.

     Parameters
     ----------
     config : `SectionProxy`
     Configuration parameters for this socket.
     cot_url : `str`
     The COT_URL as a string (un-parsed).
    """

    reader, writer = None, None
    host, port = pytak.parse_url(cot_url)
    tls_config: SectionProxy = get_tls_config(config)

    if tls_config.get("PYTAK_TLS_CERT_ENROLLMENT_USERNAME") and tls_config.get(
        "PYTAK_TLS_CERT_ENROLLMENT_PASSWORD"
    ):
        from pytak.crypto_classes import CertificateEnrollment

        enrollment = CertificateEnrollment()

        cert_enrollment_username = tls_config.get("PYTAK_TLS_CERT_ENROLLMENT_USERNAME")
        cert_enrollment_password = tls_config.get("PYTAK_TLS_CERT_ENROLLMENT_PASSWORD")
        cert_enrollment_url = tls_config.get("PYTAK_TLS_CERT_ENROLLMENT_URL", host)

        cert_enrollment_passphrase = tls_config.get(
            "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE"
        )
        if not cert_enrollment_passphrase:
            # Generate a random passphrase for the PKCS#12 file.
            cert_enrollment_passphrase = secrets.token_urlsafe(16)
            print(
                f"Using generated passphrase for enrollment: {cert_enrollment_passphrase}"
            )
            tls_config["PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE"] = (
                cert_enrollment_passphrase
            )

        with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as tmpfile:
            output_path = tmpfile.name

        await enrollment.begin_enrollment(
            domain=host,
            username=cert_enrollment_username,
            password=cert_enrollment_password,
            output_path=output_path,
            passphrase=cert_enrollment_passphrase,
        )
        # Update TLS config with the output path of the cert enrollment.
        tls_config["PYTAK_TLS_CLIENT_CERT"] = output_path

    ssl_ctx = get_ssl_ctx(tls_config)

    if ssl_ctx.check_hostname:
        expected_server_hostname = tls_config.get("PYTAK_TLS_SERVER_EXPECTED_HOSTNAME")
    else:
        expected_server_hostname = None

    try:
        reader, writer = await asyncio.open_connection(
            host.strip("[]"), port, ssl=ssl_ctx, server_hostname=expected_server_hostname
        )
    except ssl.SSLCertVerificationError as exc:
        raise SyntaxError(
            (
                "Could not verify TLS Certificate for TAK Server."
                "Bypass with PYTAK_TLS_DONT_CHECK_HOSTNAME=1 or PYTAK_TLS_DONT_VERIFY=1"
                "See: https://pytak.rtfd.io/en/stable/configuration"
            )
        ) from exc

    return reader, writer


def get_ssl_ctx(tls_config: SectionProxy) -> ssl.SSLContext:
    """Configure a TLS socket context."""

    client_cert = tls_config.get("PYTAK_TLS_CLIENT_CERT")
    client_key = tls_config.get("PYTAK_TLS_CLIENT_KEY")
    client_cafile = tls_config.get("PYTAK_TLS_CLIENT_CAFILE")
    client_password = tls_config.get(
        "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE",
        tls_config.get("PYTAK_TLS_CLIENT_PASSWORD"),
    )

    client_ciphers = tls_config.get("PYTAK_TLS_CLIENT_CIPHERS") or "ALL"

    # Do not verify CA against our trust store.
    dont_verify = tls_config.getboolean("PYTAK_TLS_DONT_VERIFY")

    dont_check_hostname = dont_verify or tls_config.getboolean(
        "PYTAK_TLS_DONT_CHECK_HOSTNAME"
    )

    # Cert is always required.
    if client_cert:
        if not os.path.exists(client_cert):
            raise SyntaxError(
                f"Resource not found: PYTAK_TLS_CLIENT_CERT={client_cert}"
            )
    else:
        raise SyntaxError("Missing value: PYTAK_TLS_CLIENT_CERT")

    if client_key:
        if not os.path.exists(client_key):
            raise SyntaxError(f"Resource not found: PYTAK_TLS_CLIENT_KEY={client_key}")

    # SSL Context
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.options |= ssl.OP_NO_TLSv1
    ssl_ctx.options |= ssl.OP_NO_TLSv1_1
    ssl_ctx.set_ciphers(client_ciphers)
    # Checks & Verifications
    ssl_ctx.check_hostname = True
    ssl_ctx.verify_mode = ssl.VerifyMode.CERT_REQUIRED

    # PKCS#12. OpenSSL's load_cert_chain() requires filesystem paths, but the
    # extracted PEMs are needed only for that call. Keeping them in /tmp for
    # the life of a gateway leaks three files on every reconnect and can fill a
    # RAM-backed tmpfs during a long TAK Server outage.
    temporary_cert_paths = []
    if client_cert.endswith(".p12"):
        cert_paths = convert_cert(client_cert, client_password)
        temporary_cert_paths = [path for path in cert_paths.values() if path]
        client_cert = cert_paths["cert_pem_path"]
        client_key = cert_paths["pk_pem_path"]

    try:
        if not os.path.exists(client_cert) or not os.path.exists(client_key):
            raise SystemError(
                f"Missing PKCS#12 extracted {client_cert} & {client_key}."
            )
        ssl_ctx.load_cert_chain(
            client_cert, keyfile=client_key, password=client_password
        )
    except Exception as exc:
        raise ValueError(
            f"Error opening resource. Using: PYTAK_TLS_CLIENT_CERT={client_cert} "
            f"[PYTAK_TLS_CLIENT_KEY={client_key}] Using "
            f"Password: {bool(client_password)}?"
        ) from exc
    finally:
        for path in temporary_cert_paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    # CA File
    if client_cafile:
        ssl_ctx.load_verify_locations(cafile=client_cafile)

    # Disables TLS Server Common Name Verification
    if dont_check_hostname:
        warnings.warn("Disabled TLS Server Common Name Verification")
        ssl_ctx.check_hostname = False

    # Disables TLS Server Certificate Verification
    if dont_verify:
        warnings.warn("Disabled TLS Server Certificate Verification")
        ssl_ctx.verify_mode = ssl.CERT_NONE

    return ssl_ctx


async def txworker_factory(
    queue: asyncio.Queue, config: SectionProxy
) -> pytak.TXWorker:
    """Create a PyTAK TXWorker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    _, writer = await protocol_factory(config)
    return pytak.TXWorker(queue, config, writer)


async def rxworker_factory(
    queue: asyncio.Queue, config: SectionProxy
) -> pytak.RXWorker:
    """Create a PyTAK RXWorker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    cot_url = get_cot_url(config)
    _, write_only, _ = pytak.parse_cot_scheme(cot_url.scheme.lower())
    reader, _ = await protocol_factory(config)
    if write_only and reader is not None:
        return pytak.DiscardRXWorker(queue, config, reader)
    return pytak.RXWorker(queue, config, reader)


async def main(app_name: str, config: SectionProxy, full_config: ConfigParser) -> None:
    """
    Abstract implementation of an async main function.

    Parameters
    ----------
    app_name : `str`
        Name of the app calling this function.
    config : `SectionProxy`
        A dict of configuration parameters & values.
    full_config : `ConfigParser`
        A full dict of configuration parameters & values.
    """
    app = importlib.__import__(app_name)
    clitool: pytak.CLITool = pytak.CLITool(config)
    create_tasks = getattr(app, "create_tasks")
    await clitool.create_workers(config)
    if bool(config.get("IMPORT_OTHER_CONFIGS", pytak.DEFAULT_IMPORT_OTHER_CONFIGS)):
        try:
            for i in full_config.sections()[1:]:
                await clitool.create_workers(full_config[i])
        except EOFError:
            logging.warning("No more configs to create workers for!")
    # await clitool.setup()
    clitool.add_tasks(create_tasks(config, clitool))
    await clitool.run()


def _retryable_transport_error(exc: Exception) -> bool:
    """Return whether a failed client run can recover without configuration changes."""
    if isinstance(exc, (ConnectionError, TimeoutError, socket.gaierror, ssl.SSLError)):
        return True
    if isinstance(exc, OSError):
        # Socket failures inherit from OSError, but local faults such as
        # ENOENT, EACCES, and ENOSPC must remain fatal instead of disappearing
        # into an endless TAK reconnect loop.
        network_errnos = {
            errno.ECONNABORTED,
            errno.ECONNREFUSED,
            errno.ECONNRESET,
            errno.EHOSTUNREACH,
            errno.ENETDOWN,
            errno.ENETUNREACH,
            # Linux can report EPERM from UDP sendto() while nftables,
            # routes, or network namespaces are being replaced. Treat it as
            # a transport outage so an appliance update cannot terminate a
            # high-rate feeder during that short transition.
            errno.EPERM,
            errno.ETIMEDOUT,
        }
        if hasattr(errno, "EHOSTDOWN"):
            network_errnos.add(errno.EHOSTDOWN)
        return exc.errno in network_errnos
    try:
        import aiohttp

        return isinstance(exc, aiohttp.ClientError)
    except ImportError:
        return False


def _safe_error_text(exc: Exception) -> str:
    """Redact enrollment credentials from an exception before logging it."""
    text = re.sub(r"tak://[^\s\"'<>]+", "tak://REDACTED", str(exc))
    return re.sub(
        r"(?i)(token|username|password)=([^&\s\"'<>]+)",
        r"\1=REDACTED",
        text,
    )


def _reconnect_number(config: SectionProxy, key: str, default: str) -> float:
    """Read and validate a positive reconnect tuning value."""
    value = float(config.get(key, default))
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return value


def _reconnect_jitter(config: SectionProxy) -> float:
    """Read a reconnect jitter fraction in the half-open range [0, 1)."""
    value = float(
        config.get("PYTAK_RECONNECT_JITTER", pytak.DEFAULT_RECONNECT_JITTER)
    )
    if value < 0 or value >= 1:
        raise ValueError("PYTAK_RECONNECT_JITTER must be >= 0 and < 1")
    return value


async def supervise_with_reconnect(
    config: SectionProxy,
    run_once: Callable[[], Awaitable[None]],
) -> None:
    """Run a client factory continuously through transient TAK outages.

    Worker failures tear down their sockets and source tasks cleanly, then this
    supervisor calls ``run_once`` again in the same process. Custom PyTAK
    integrations should construct a fresh ``CLITool`` and workers inside that
    callback so queues are bounded and transports are not reused after a
    failure. Backoff keeps DNS failures, refused connections, server-side
    WebSocket closes, and transient network-policy replacement from becoming
    a systemd crash loop.
    """
    reconnect = config.getboolean("PYTAK_RECONNECT", fallback=True)
    initial = _reconnect_number(
        config, "PYTAK_RECONNECT_INITIAL", pytak.DEFAULT_RECONNECT_INITIAL
    )
    maximum = _reconnect_number(
        config, "PYTAK_RECONNECT_MAX", pytak.DEFAULT_BACKOFF
    )
    factor = _reconnect_number(
        config, "PYTAK_RECONNECT_FACTOR", pytak.DEFAULT_RECONNECT_FACTOR
    )
    jitter = _reconnect_jitter(config)
    reset_after = _reconnect_number(
        config, "PYTAK_RECONNECT_RESET", pytak.DEFAULT_RECONNECT_RESET
    )
    if maximum < initial:
        raise ValueError("PYTAK_RECONNECT_MAX must be >= PYTAK_RECONNECT_INITIAL")
    if factor < 1:
        raise ValueError("PYTAK_RECONNECT_FACTOR must be >= 1")

    delay = initial
    while True:
        started = asyncio.get_running_loop().time()
        try:
            await run_once()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not reconnect or not _retryable_transport_error(exc):
                raise

            connected_for = asyncio.get_running_loop().time() - started
            if connected_for >= reset_after:
                delay = initial
            sleep_for = delay
            if jitter:
                sleep_for = min(
                    maximum, delay * random.uniform(1 - jitter, 1 + jitter)
                )
            logging.warning(
                "TAK transport unavailable (%s: %s); retrying in %.1fs",
                type(exc).__name__,
                _safe_error_text(exc),
                sleep_for,
            )
            await asyncio.sleep(sleep_for)
            delay = min(maximum, delay * factor)


async def run_with_reconnect(
    app_name: str,
    config: SectionProxy,
    full_config: ConfigParser,
    tak_url: str = "",
) -> None:
    """Run a standard PyTAK integration through transient TAK outages."""

    async def run_once() -> None:
        if tak_url:
            config.update(await resolve_tak_url(tak_url))
        await main(app_name, config, full_config)

    await supervise_with_reconnect(config, run_once)


def read_pref_package(pref_package: str) -> dict:
    """Read a pref package / data package of preferences."""
    pref_config = {
        "COT_URL": "",
        "PYTAK_TLS_CLIENT_CERT": None,
        "PYTAK_TLS_CLIENT_KEY": None,
        "PYTAK_TLS_CLIENT_CAFILE": None,
    }

    dp_path: str = unzip_file(pref_package)
    pref_file: str = find_file(dp_path, "*.pref")
    prefs: dict = load_preferences(pref_file, dp_path)

    connect_string: str = prefs.get("connect_string", "")
    assert connect_string
    pref_config["COT_URL"] = connectString2url(connect_string)

    cert_location: str = prefs.get("certificate_location", "")
    assert os.path.exists(cert_location)

    client_password: str = prefs.get("client_password", "")
    assert client_password

    import pytak.crypto_functions

    pem_certs: dict = pytak.crypto_functions.convert_cert(
        cert_location, client_password
    )
    pref_config["PYTAK_TLS_CLIENT_CERT"] = pem_certs.get("cert_pem_path")
    pref_config["PYTAK_TLS_CLIENT_KEY"] = pem_certs.get("pk_pem_path")
    pref_config["PYTAK_TLS_CLIENT_CAFILE"] = pem_certs.get("ca_pem_path")

    assert all(pref_config)
    return pref_config


def cli(app_name: str) -> None:
    """Abstract implementation of a Command Line Interface (CLI).

    Parameters
    ----------
    app_name : `str`
        Name of the app calling this function.
    """
    app = importlib.__import__(app_name)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--CONFIG_FILE",
        dest="CONFIG_FILE",
        default="config.ini",
        type=str,
        help="Optional configuration file. Default: config.ini",
    )
    parser.add_argument(
        "-p",
        "--PREF_PACKAGE",
        dest="PREF_PACKAGE",
        required=False,
        type=str,
        help="Optional connection preferences package zip file (aka data package).",
    )
    namespace = parser.parse_args()
    cli_args = {k: v for k, v in vars(namespace).items() if v is not None}

    # Read config:
    env_vars = os.environ

    # Remove env vars that contain '%', which ConfigParser or pprint barf on:
    env_vars = {key: val for key, val in env_vars.items() if "%" not in val}

    env_vars["COT_URL"] = env_vars.get("COT_URL", pytak.DEFAULT_COT_URL)
    env_vars["COT_HOST_ID"] = f"{app_name}@{platform.node()}"
    env_vars["COT_STALE"] = getattr(app, "DEFAULT_COT_STALE", pytak.DEFAULT_COT_STALE)
    env_vars["TAK_PROTO"] = env_vars.get("TAK_PROTO", pytak.DEFAULT_TAK_PROTO)

    orig_config: ConfigParser = ConfigParser(env_vars)

    config_file = cli_args.get("CONFIG_FILE", "")
    if os.path.exists(config_file):
        logging.info("Reading configuration from %s", config_file)
        orig_config.read(config_file)
    else:
        orig_config.add_section(app_name)

    config: SectionProxy = orig_config[app_name]
    full_config: ConfigParser = orig_config

    pref_package: str = config.get("PREF_PACKAGE", cli_args.get("PREF_PACKAGE"))
    if pref_package and os.path.exists(pref_package):
        pref_config = read_pref_package(pref_package)
        config.update(pref_config)

    # Resolve tak:// onboarding URLs before starting the event loop.
    # Honour TAK_URL env var or a tak:// scheme in COT_URL.
    tak_url: str = config.get("TAK_URL", "")
    if not tak_url:
        _cot = config.get("COT_URL", "")
        if _cot.lower().startswith("tak://"):
            tak_url = _cot
    debug = config.getboolean("DEBUG")
    if debug:
        print(f"Showing Config: {config_file}")
        print("=" * 10)
        pprint.pprint(dict(config))
        print("=" * 10)

    if sys.version_info[:2] >= (3, 7):
        asyncio.run(
            run_with_reconnect(app_name, config, full_config, tak_url), debug=debug
        )
    else:
        loop = get_running_loop()
        try:
            loop.run_until_complete(
                run_with_reconnect(app_name, config, full_config, tak_url)
            )
        finally:
            loop.close()
