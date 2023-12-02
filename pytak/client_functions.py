#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

"""PyTAK Client & CLI Functions."""

import argparse
import asyncio
import importlib
import ipaddress
import logging
import os
import platform
import pprint
import socket
import ssl
import struct
import sys
import warnings

from configparser import ConfigParser, SectionProxy
from urllib.parse import ParseResult, urlparse
from typing import Any, Tuple, Union, Optional

import pytak

from pytak.functions import unzip_file, find_file, load_preferences, connectString2url

from pytak.asyncio_dgram import (
    DatagramClient,
    connect as dgconnect,
    bind as dgbind,
    from_socket,
)

from pytak.crypto_functions import convert_cert

# Python 3.6 support:
if sys.version_info[:2] >= (3, 7):  # pragma: no cover
    from asyncio import get_running_loop
else:  # pragma: no cover
    warnings.warn("Using Python < 3.7, consider upgrading Python.")
    from asyncio import get_event_loop as get_running_loop

__author__ = "Greg Albrecht <gba@snstac.com>"
__copyright__ = "Copyright Sensors & Signals LLC https://www.snstac.com"
__license__ = "Apache License, Version 2.0"


async def create_udp_client(
    url: ParseResult, local_addr=None
) -> Tuple[Union[DatagramClient, None], DatagramClient]:
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

    is_write_only: bool = "+wo" in url.scheme
    is_broadcast: bool = "broadcast" in url.scheme
    is_multicast: bool = "multicast" in url.scheme

    try:
        is_multicast = ipaddress.ip_address(host).is_multicast
    except ValueError:
        # It's probably not an ip address...
        pass

    # Create the Writer
    writer: DatagramClient = await dgconnect(
        (host, port), local_addr=local_addr, allow_broadcast=is_broadcast
    )

    if is_broadcast:
        writer.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    if is_write_only:
        return reader, writer

    # Create the Reader
    rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    bindall = sys.platform == "win32"
    rsock.bind(("" if bindall else host, port))

    reader = await from_socket(rsock)

    if not reader:
        return reader, writer

    if is_broadcast:
        # SO_BROADCAST
        reader.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    if is_broadcast or is_multicast:
        # SO_REUSEADDR
        reader.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # SO_REUSEPORT
            reader.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            # Some systems don't support SO_REUSEPORT
            pass

    # Create Multicast Reader
    if is_multicast:
        ip = (
            socket.INADDR_ANY
            if local_addr[0] is None
            else int(ipaddress.IPv4Address(local_addr[0]))
        )
        group = int(ipaddress.IPv4Address(host))
        mreq = struct.pack("!LL", group, ip)

        reader.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        reader.socket.setsockopt(
            socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("b", 1)
        )

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


async def protocol_factory(  # NOQA pylint: disable=too-many-locals,too-many-branches,too-many-statements
    config: SectionProxy,
) -> Any:
    """Create a network connection class instance.

    Class is for the protocol specified by the COT_URL parameter in the config object.

    Parameters
    ----------
    config : `SectionProxy`
        Configuration parameters & values.

    Returns
    -------
    `Any`
        Return value depends on the network protocol.
    """
    reader: Any = None
    writer: Any = None

    _cot_url: str = config.get("COT_URL", pytak.DEFAULT_COT_URL)

    if "://" not in _cot_url:
        warnings.warn(f"Invalid COT_URL: '{_cot_url}'", SyntaxWarning)
        raise SyntaxError(
            "Please specify COT_URL as a full URL, including '://', for "
            "example: tcp://tak.example.com:1234"
        )

    cot_url: ParseResult = urlparse(_cot_url)
    scheme: str = cot_url.scheme.lower()

    if scheme in ["tcp"]:
        host, port = pytak.parse_url(cot_url)
        reader, writer = await asyncio.open_connection(host, port)
    elif scheme in ["tls", "ssl"]:
        host, port = pytak.parse_url(cot_url)
        tls_config: SectionProxy = get_tls_config(config)

        client_cert = tls_config.get("PYTAK_TLS_CLIENT_CERT")
        client_key = tls_config.get("PYTAK_TLS_CLIENT_KEY")
        client_cafile = tls_config.get("PYTAK_TLS_CLIENT_CAFILE")
        client_password = tls_config.get("PYTAK_TLS_CLIENT_PASSWORD")

        # Default cipher suite: ALL.
        #  Also available in FIPS: DEFAULT_FIPS_CIPHERS
        client_ciphers = tls_config.get("PYTAK_TLS_CLIENT_CIPHERS") or "ALL"

        # If the cert's CA isn't in our trust chain, set this:
        dont_verify = tls_config.getboolean("PYTAK_TLS_DONT_VERIFY")

        # If the cert's CN doesn't match the hostname, set this:
        dont_check_hostname = dont_verify or tls_config.getboolean(
            "PYTAK_TLS_DONT_CHECK_HOSTNAME"
        )

        # SSL Context setup:
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_ctx.options |= ssl.OP_NO_TLSv1
        ssl_ctx.options |= ssl.OP_NO_TLSv1_1
        ssl_ctx.set_ciphers(client_ciphers)
        ssl_ctx.check_hostname = True
        ssl_ctx.verify_mode = ssl.VerifyMode.CERT_REQUIRED

        if client_cert.endswith(".p12"):
            cert_paths = convert_cert(client_cert, client_password)
            client_cert = cert_paths["cert_pem_path"]
            client_key = cert_paths["pk_pem_path"]

        if client_key:
            ssl_ctx.load_cert_chain(
                client_cert, keyfile=client_key, password=client_password
            )
        else:
            ssl_ctx.load_cert_chain(client_cert, password=client_password)

        if client_cafile:
            ssl_ctx.load_verify_locations(cafile=client_cafile)

        # Default to checking hostnames:
        if dont_check_hostname:
            warnings.warn(
                "TLS CN/Hostname Check DISABLED by PYTAK_TLS_DONT_CHECK_HOSTNAME."
            )
            ssl_ctx.check_hostname = False

        # Default to verifying cert:
        if dont_verify:
            warnings.warn(
                "TLS Certificate Verification DISABLED by PYTAK_TLS_DONT_VERIFY."
            )
            ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
        except ssl.SSLCertVerificationError as exc:
            raise SyntaxError(
                "Consider setting PYTAK_TLS_DONT_CHECK_HOSTNAME=1 ?"
            ) from exc
    elif "udp" in scheme:
        local_addr = (
            config.get(
                "PYTAK_MULTICAST_LOCAL_ADDR", pytak.DEFAULT_PYTAK_MULTICAST_LOCAL_ADDR
            ),
            0,
        )
        reader, writer = await pytak.create_udp_client(cot_url, local_addr)
    elif "http" in scheme:
        raise SyntaxError("TeamConnect / Sit(x) Support comming soon.")
        # writer = await pytak.create_tc_client(cot_url)
    elif "log" in scheme:
        if cot_url.hostname:
            dest: str = cot_url.hostname.lower()
            if "stderr" in dest:
                writer = sys.stderr.buffer
            else:
                writer = sys.stdout.buffer

    if not reader and not writer:
        raise SyntaxError(
            "Please specify a protocol in your COT Destination URL. See PyTAK README."
        )

    return reader, writer


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
    """Create a PyTAK TXWorker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    reader, _ = await protocol_factory(config)
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

    debug = config.getboolean("DEBUG")
    if debug:
        print(f"Showing Config: {config_file}")
        print("=" * 10)
        pprint.pprint(dict(config))
        print("=" * 10)

    if sys.version_info[:2] >= (3, 7):
        asyncio.run(main(app_name, config, full_config), debug=debug)
    else:
        loop = get_running_loop()
        try:
            loop.run_until_complete(main(app_name, config, full_config))
        finally:
            loop.close()


# TeamConnect / Sit(x) Support TK:
#
# def tc_get_auth(
#     client_id: str, client_secret: str, scope_url: str = ".bridge-both"
# ) -> dict:
#     """
#     Authenticates against the Team Connect API.

#     Returns the complete auth payload, including `access_token`
#     """
#     payload: dict = {
#         "grant_type": "client_credentials",
#         "client_id": client_id,
#         "client_secret": client_secret,
#         "scope": scope_url,
#     }
#     payload: str = json.dumps(payload)
#     url: str = pytak.DEFAULT_TC_TOKEN_URL

#     req: urllib.request.Request = urllib.request.Request(
#         url=url, data=bytes(payload.encode("utf-8")), method="POST"
#     )
#     req.add_header("Content-type", "application/json; charset=UTF-8")

#     with urllib.request.urlopen(req) as resp:
#         if resp.status == 200:
#             response_data = json.loads(resp.read().decode("utf-8"))
#             return response_data
#     return {}
