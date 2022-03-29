#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""PyTAK Functions."""

import asyncio
import json
import os
import socket
import ssl
import urllib
import urllib.request

import pytak
import pytak.asyncio_dgram

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


async def create_udp_client(
        url: urllib.parse.ParseResult) -> pytak.asyncio_dgram.DatagramClient:
    """
    Creates an async UDP network client. Supports UDP unicast & broadcast.

    `url` is urllib-parsed URL to remote host. eg. 'udp://example.com:1234'
    """
    host, port = pytak.parse_cot_url(url)
    stream: pytak.asyncio_dgram.DatagramClient = \
        await pytak.asyncio_dgram.connect((host, port))

    if "broadcast" in url.scheme:
        sock = stream.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


async def protocol_factory(cot_url: urllib.parse.ParseResult):
    """
    Given a COT Destination URL, create a Connection Class Instance for the 
    given protocol.

    `url` is urllib-parsed URL to remote host. eg. 'udp://example.com:1234'
    """
    reader = None
    writer = None
    scheme = cot_url.scheme.lower()

    if scheme in ["tcp"]:
        host, port = pytak.parse_cot_url(cot_url)
        reader, writer = await asyncio.open_connection(host, port)
    elif scheme in ["tls", "ssl"]:
        host, port = pytak.parse_cot_url(cot_url)

        # End-user will either need to:
        #  A) Create the default files for these parameters, or;
        #  B) Set these environmental variables to point to the files.
        client_cert = os.getenv("PYTAK_TLS_CLIENT_CERT")
        client_key = os.getenv("PYTAK_TLS_CLIENT_KEY")
        client_cafile = os.getenv("PYTAK_TLS_CLIENT_CAFILE")

        # Default cipher suite: ALL.
        #  Also available in FIPS: DEFAULT_FIPS_CIPHERS
        client_ciphers = os.getenv("PYTAK_TLS_CLIENT_CIPHERS") or "ALL"

        # If the cert's CN doesn't match the hostname, set this:
        dont_check_hostname = bool(os.getenv("PYTAK_TLS_DONT_CHECK_HOSTNAME"))

        # If the cert's CA isn't in our trust chain, set this:
        dont_verify = bool(os.getenv("PYTAK_TLS_DONT_VERIFY"))

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
            print(
                "WARN: pytak TLS Certificate Verification DISABLED by "
                "PYTAK_TLS_DONT_VERIFY environment.")
            print(
                "WARN: pytak TLS CN/Hostname Check DISABLED by "
                "PYTAK_TLS_DONT_VERIFY environment.")
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        # Default to checking hostnames:
        if dont_check_hostname:
            print(
                "WARN: pytak TLS CN/Hostname Check DISABLED by "
                "PYTAK_TLS_DONT_CHECK_HOSTNAME environment.")
            ssl_ctx.check_hostname = False

        reader, writer = await asyncio.open_connection(
            host, port, ssl=ssl_ctx)
    elif "udp" in scheme:
        writer = await pytak.create_udp_client(cot_url)
    elif "http" in scheme:
        writer = await pytak.create_tc_client(cot_url)
    else:
        raise Exception(
            "Please specify a protocol in your CoT Destination URL, "
            "for example: tcp:xxx:9876, tls:xxx:1234, udp:xxx:9999, etc.")

    return reader, writer


async def eventworker_factory(cot_url: urllib.parse.ParseResult, 
                              event_queue: asyncio.Queue) -> pytak.Worker:
    """
    Creates a COT Event Worker based on URL parameters.

    :param cot_url: URL to COT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :return: EventWorker or asyncio Protocol
    """
    reader, writer = await protocol_factory(cot_url)
    return pytak.EventWorker(event_queue, writer)


def tc_get_auth(client_id: str, client_secret: str, 
                scope_url: str = '.bridge-both') -> dict:
    """
    Authenticates against the Team Connect API.
    
    Returns the complete auth payload, including `access_token`
    """
    payload: dict = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': scope_url
    }
    payload: str = json.dumps(payload)
    url: str = pytak.DEFAULT_TC_TOKEN_URL

    req: urllib.request.Request = urllib.request.Request(
        url = url, data = bytes(payload.encode('utf-8')), method = 'POST')
    req.add_header('Content-type', 'application/json; charset=UTF-8')

    with urllib.request.urlopen(req) as resp:
        if resp.status == 200:
            response_data = json.loads(resp.read().decode('utf-8'))
            return response_data
    return {}