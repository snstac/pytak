#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""PyTAK Functions."""

import asyncio
import os
import socket
import ssl
import urllib

import pytak
import pytak.asyncio_dgram

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


async def create_udp_client(url: urllib.parse.ParseResult) -> pytak.asyncio_dgram.DatagramClient:
    """Creates an async UDP network client."""
    host, port = pytak.parse_cot_url(url)
    stream: pytak.asyncio_dgram.DatagramClient = await pytak.asyncio_dgram.connect((host, port))
    if "broadcast" in url.scheme:
        sock = stream.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


async def protocol_factory(cot_url: urllib.parse.ParseResult):
    """
    Given a COT Destination URL, create a Connection Class Instance for the given protocol.

    :param cot_url: COT Destination URL
    :return:
    """
    reader = None
    writer = None
    scheme = cot_url.scheme.lower()

    if scheme in ["tcp"]:
        host, port = pytak.parse_cot_url(cot_url)
        reader, writer = await asyncio.open_connection(host, port)
    elif scheme in ["tls", "ssl"]:
        host, port = pytak.parse_cot_url(cot_url)

        client_cert = os.getenv("PYTAK_TLS_CLIENT_CERT")
        client_key = os.getenv("PYTAK_TLS_CLIENT_KEY")
        client_cafile = os.getenv("PYTAK_TLS_CLIENT_CAFILE")
        client_ciphers = os.getenv(
            "PYTAK_TLS_CLIENT_CIPHERS", pytak.DEFAULT_FIPS_CIPHERS)

        dont_check_hostname = bool(os.getenv("PYTAK_TLS_DONT_CHECK_HOSTNAME"))
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
                "pytak TLS Certificate Verification DISABLED by Environment.")
            print("pytak TLS Hostname Check DISABLED by Environment.")
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        # Default to checking hostnames:
        if dont_check_hostname:
            print("pytak TLS Hostname Check DISABLED by Environment.")
            ssl_ctx.check_hostname = False

        reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
    elif "udp" in scheme:
        writer = await pytak.create_udp_client(cot_url)
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
