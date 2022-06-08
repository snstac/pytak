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
import configparser
import json
import importlib
import logging
import os
import platform
import socket
import ssl
import sys
import urllib
import urllib.request

from urllib.parse import ParseResult, urlparse

from typing import Any, Tuple, Union

import pytak
import pytak.asyncio_dgram

# Python 3.6 support:
if sys.version_info[:2] >= (3, 7):
    from asyncio import get_running_loop
else:
    from asyncio import _get_running_loop as get_running_loop

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


async def create_udp_client(url: ParseResult) -> pytak.asyncio_dgram.DatagramClient:
    """
    Creates an async UDP network client, Unicast, Broadcast & Multicast.

    Parameters
    ----------
    url : ParseResult
        A parsed fully-qualified URL, for example: udp://tak.example.com:4242

    Returns
    -------
    pytak.asyncio_dgram.DatagramClient
        An async UDP network stream client.
    """
    host, port = pytak.parse_url(url)
    stream: pytak.asyncio_dgram.DatagramClient = await pytak.asyncio_dgram.connect(
        (host, port)
    )

    if "broadcast" in url.scheme:
        sock = stream.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


def get_tls_config(config: Union[dict, configparser.ConfigParser]) -> dict:
    """
    Gets the TLS config and ensures required TLS params are set.

    Parameters
    ----------
    config : dict, configparser.ConfigParser
        A dict of configuration parameters & values.

    Returns
    -------
    dict
        A TLS configuration.
    """
    tls_config_req: dict = dict(zip(pytak.DEFAULT_TLS_PARAMS_REQ, [config.get(x) for x in pytak.DEFAULT_TLS_PARAMS_REQ]))

    if None in tls_config_req.values():
        raise Exception("Not all TLS Params specified: %s", pytak.DEFAULT_TLS_PARAMS_REQ)
    
    tls_config_opt: dict = dict(zip(pytak.DEFAULT_TLS_PARAMS_OPT, [config.get(x) for x in pytak.DEFAULT_TLS_PARAMS_OPT]))    

    tls_config_req.update(tls_config_opt)
    return tls_config_req


async def protocol_factory(config: Union[dict, configparser.ConfigParser]) -> Any:
    """
    Creates a network connection class instances for the protocol specified by 
    the COT_URL parameter in the config object.

    Parameters
    ----------
    config : dict, configparser.ConfigParser
        A dict of configuration parameters & values.

    Returns
    -------
    Any
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
        tls_config: dict = get_tls_config()

        client_cert = tls_config.get("PYTAK_TLS_CLIENT_CERT")
        client_key = tls_config.get("PYTAK_TLS_CLIENT_KEY")
        client_cafile = tls_config.get("PYTAK_TLS_CLIENT_CAFILE")

        # Default cipher suite: ALL.
        #  Also available in FIPS: DEFAULT_FIPS_CIPHERS
        client_ciphers = tls_config.get("PYTAK_TLS_CLIENT_CIPHERS") or "ALL"

        # If the cert's CN doesn't match the hostname, set this:
        dont_check_hostname = bool(tls_config.get("PYTAK_TLS_DONT_CHECK_HOSTNAME"))

        # If the cert's CA isn't in our trust chain, set this:
        dont_verify = bool(tls_config.get("PYTAK_TLS_DONT_VERIFY"))

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

        # Default to verifying cert:
        if dont_verify:
            dont_check_hostname = True
            print(
                "WARN: pytak TLS Certificate Verification DISABLED by "
                "PYTAK_TLS_DONT_VERIFY environment."
            )
            ssl_ctx.verify_mode = ssl.CERT_NONE

        # Default to checking hostnames:
        if dont_check_hostname:
            print(
                "WARN: pytak TLS CN/Hostname Check DISABLED by "
                "PYTAK_TLS_DONT_CHECK_HOSTNAME environment."
            )
            ssl_ctx.check_hostname = False

        reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
    elif "udp" in scheme:
        writer = await pytak.create_udp_client(cot_url)
    elif "http" in scheme:
        writer = await pytak.create_tc_client(cot_url)
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


async def eventworker_factory(config: dict, event_queue: asyncio.Queue) -> pytak.Worker:
    """
    Creates a COT Event Worker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    reader, writer = await protocol_factory(config)
    return pytak.EventWorker(event_queue, config, writer)


def tc_get_auth(
    client_id: str, client_secret: str, scope_url: str = ".bridge-both"
) -> dict:
    """
    Authenticates against the Team Connect API.

    Returns the complete auth payload, including `access_token`
    """
    payload: dict = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope_url,
    }
    payload: str = json.dumps(payload)
    url: str = pytak.DEFAULT_TC_TOKEN_URL

    req: urllib.request.Request = urllib.request.Request(
        url=url, data=bytes(payload.encode("utf-8")), method="POST"
    )
    req.add_header("Content-type", "application/json; charset=UTF-8")

    with urllib.request.urlopen(req) as resp:
        if resp.status == 200:
            response_data = json.loads(resp.read().decode("utf-8"))
            return response_data
    return {}


async def main(app_name: str, config: Union[dict, configparser.ConfigParser]) -> None:
    """
    Abstract implementation of an async main function.
    
    Parameters
    ----------
    app_name : str
        Name of the app calling this function.
    config : dict, configparser.ConfigParser
        A dict of configuration parameters & values.

    Returns
    -------
    None
    """
    app = importlib.__import__(app_name)
    clitool = pytak.CLITool(config)
    create_tasks = getattr(app, "create_tasks")
    await clitool.setup()
    clitool.add_tasks(create_tasks(config, clitool))
    await clitool.run()


def cli(app_name: str, main_func: str = "main") -> None:
    """
    Abstract implementation of a Command Line Interface (CLI).

    Parameters
    ----------
    app_name : str
        Name of the app calling this function.
    main_func : str
        Name of the main function to call within the app.

    Returns
    -------
    None
    """
    app = importlib.__import__(app_name)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--CONFIG_FILE", dest="CONFIG_FILE", default="config.ini", type=str, help="Optional configuration file. Default: config.ini"
    )
    namespace = parser.parse_args()
    cli_args = {k: v for k, v in vars(namespace).items() if v is not None}

    # Read config:
    env_vars = os.environ
    env_vars["COT_URL"] = env_vars.get("COT_URL", pytak.DEFAULT_COT_URL)
    env_vars["COT_HOST_ID"] = f"{app_name}@{platform.node()}"
    env_vars["COT_STALE"] = getattr(app, "DEFAULT_COT_STALE", pytak.DEFAULT_COT_STALE)
    config = configparser.ConfigParser(env_vars)

    config_file = cli_args.get("CONFIG_FILE")
    if os.path.exists(config_file):
        logging.info("Reading configuration from %s", config_file)
        config.read(config_file)
    else:
        config.add_section(app_name)

    config = config[app_name]

    debug = config.getboolean("DEBUG")
    if debug:
        import pprint
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
