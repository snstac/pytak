#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2022 Greg Albrecht <oss@undef.net>
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
# Author:: Greg Albrecht W2GMD <oss@undef.net>
#

"""PyTAK Functions."""

import argparse
import asyncio
import importlib
import logging
import os
import platform
import socket
import ssl
import sys

from configparser import ConfigParser, SectionProxy
from urllib.parse import ParseResult, urlparse
from typing import Any

import pytak

from pytak.asyncio_dgram import (
    DatagramClient,
    connect as dgconnect,
)

# Python 3.6 support:
if sys.version_info[:2] >= (3, 7):
    from asyncio import get_running_loop
else:
    from asyncio import (  # pylint: disable=no-name-in-module
        _get_running_loop as get_running_loop,
    )

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


async def create_udp_client(url: ParseResult) -> DatagramClient:
    """
    Creates an AsyncIO UDP network client for Unicast, Broadcast & Multicast.

    Parameters
    ----------
    url : `ParseResult`
        A parsed fully-qualified URL parsed with `urllib.parse.urlparse()`.
        For example: udp://tak.example.com:4242

    Returns
    -------
    `DatagramClient`
        An AsyncIO UDP network stream client.
    """
    host, port = pytak.parse_url(url)
    stream: DatagramClient = await dgconnect((host, port))

    if "broadcast" in url.scheme:
        sock = stream.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


def get_tls_config(config: SectionProxy) -> SectionProxy:
    """
    Gets the TLS config and ensures required TLS params are set.

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

    if None in tls_config_req.values():
        raise Exception(f"Not all TLS Params specified: {pytak.DEFAULT_TLS_PARAMS_REQ}")

    tls_config_opt: dict = dict(
        zip(
            pytak.DEFAULT_TLS_PARAMS_OPT,
            [config.get(x) for x in pytak.DEFAULT_TLS_PARAMS_OPT],
        )
    )

    tls_config_req.update(tls_config_opt)
    return ConfigParser(dict(filter(lambda x: x[1], tls_config_req.items())))["DEFAULT"]


async def protocol_factory(  # pylint: disable=too-many-locals,too-many-branches
    config: SectionProxy,
) -> Any:
    """
    Creates a network connection class instances for the protocol specified by
    the COT_URL parameter in the config object.

    Parameters
    ----------
    config : `SectionProxy`
        Configuration parameters & values.

    Returns
    -------
    `Any`
        Return value depends on the network protocol.
    """
    reader = None
    writer = None

    cot_url: ParseResult = urlparse(config.get("COT_URL"))
    scheme: str = cot_url.scheme.lower()

    if scheme in ["tcp"]:
        host, port = pytak.parse_url(cot_url)
        reader, writer = await asyncio.open_connection(host, port)
    elif scheme in ["tls", "ssl"]:
        host, port = pytak.parse_url(cot_url)
        tls_config: ConfigParser = get_tls_config(config)

        client_cert = tls_config.get("PYTAK_TLS_CLIENT_CERT")
        client_key = tls_config.get("PYTAK_TLS_CLIENT_KEY")
        client_cafile = tls_config.get("PYTAK_TLS_CLIENT_CAFILE")

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

        if client_key:
            ssl_ctx.load_cert_chain(client_cert, keyfile=client_key)
        else:
            ssl_ctx.load_cert_chain(client_cert)

        if client_cafile:
            ssl_ctx.load_verify_locations(cafile=client_cafile)

        # Default to checking hostnames:
        if dont_check_hostname:
            print(
                "WARN: pytak TLS CN/Hostname Check DISABLED by "
                "PYTAK_TLS_DONT_CHECK_HOSTNAME environment."
            )
            ssl_ctx.check_hostname = False

        # Default to verifying cert:
        if dont_verify:
            print(
                "WARN: pytak TLS Certificate Verification DISABLED by "
                "PYTAK_TLS_DONT_VERIFY environment."
            )
            ssl_ctx.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
    elif "udp" in scheme:
        writer = await pytak.create_udp_client(cot_url)
    elif "http" in scheme:
        raise Exception("TeamConnect / Sit(x) Support comming soon.")
        # writer = await pytak.create_tc_client(cot_url)
    elif "log" in scheme:
        dest: str = cot_url.hostname.lower()
        if "stderr" in dest:
            writer = sys.stderr.buffer
        else:
            writer = sys.stdout.buffer
    else:
        raise Exception(
            "Please specify a protocol in your COT Destination URL. See PyTAK README."
        )

    return reader, writer


async def txworker_factory(
    queue: asyncio.Queue, config: SectionProxy
) -> pytak.TXWorker:
    """
    Creates a PyTAK TXWorker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    _, writer = await protocol_factory(config)
    return pytak.TXWorker(queue, config, writer)


async def rxworker_factory(
    queue: asyncio.Queue, config: SectionProxy
) -> pytak.RXWorker:
    """
    Creates a PyTAK TXWorker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    reader, _ = await protocol_factory(config)
    return pytak.RXWorker(queue, config, reader)


async def main(app_name: str, config: SectionProxy) -> None:
    """
    Abstract implementation of an async main function.

    Parameters
    ----------
    app_name : `str`
        Name of the app calling this function.
    config : `SectionProxy`
        A dict of configuration parameters & values.
    """
    app = importlib.__import__(app_name)
    clitool: pytak.CLITool = pytak.CLITool(config)
    create_tasks = getattr(app, "create_tasks")
    await clitool.setup()
    clitool.add_tasks(create_tasks(config, clitool))
    await clitool.run()


def cli(app_name: str) -> None:
    """
    Abstract implementation of a Command Line Interface (CLI).

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
    namespace = parser.parse_args()
    cli_args = {k: v for k, v in vars(namespace).items() if v is not None}

    # Read config:
    env_vars = os.environ
    env_vars["COT_URL"] = env_vars.get("COT_URL", pytak.DEFAULT_COT_URL)
    env_vars["COT_HOST_ID"] = f"{app_name}@{platform.node()}"
    env_vars["COT_STALE"] = getattr(app, "DEFAULT_COT_STALE", pytak.DEFAULT_COT_STALE)
    config: ConfigParser = ConfigParser(env_vars)

    config_file = cli_args.get("CONFIG_FILE")
    if os.path.exists(config_file):
        logging.info("Reading configuration from %s", config_file)
        config.read(config_file)
    else:
        config.add_section(app_name)

    config: SectionProxy = config[app_name]

    debug = config.getboolean("DEBUG")
    if debug:
        import pprint  # pylint: disable=import-outside-toplevel

        print("Showing Config: %s", config_file)
        print("=" * 10)
        pprint.pprint(config)
        print("=" * 10)

    if sys.version_info[:2] >= (3, 7):
        asyncio.run(main(app_name, config), debug=debug)
    else:
        loop = get_running_loop()
        try:
            loop.run_until_complete(main(app_name, config))
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
