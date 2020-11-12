#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""APRS Cursor-on-Target Constants."""

import asyncio
import socket
import struct

import asyncio_dgram

import pytak

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2020 Orion Labs, Inc."
__license__ = "Apache License, Version 2.0"


def split_host(host, port) -> tuple:
    if ':' in host:
        addr, port = host.split(':')
        port = int(port)
    elif port:
        addr = host
        port = int(port)
    else:
        addr = host
        port = int(pytak.DEFAULT_COT_PORT)

    return addr, port


def parse_cot_url(url) -> tuple:
    if ":" in url.path:
        host, port = str(url.path).split(":")
    else:
        host = url.path
        if "broadcast" in url.scheme:
            port = pytak.DEFAULT_BROADCAST_PORT
        else:
            port = pytak.DEFAULT_COT_PORT
    return host, port


async def udp_client(url):
    """Create a UDP Network client, simulate other transports."""
    host, port = parse_cot_url(url)
    stream = await asyncio_dgram.connect((host, port))
    if "broadcast" in url.scheme:
        sock = stream.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


async def multicast_client(url):
    """Create a UDP Network client, simulate other transports."""
    host, port = parse_cot_url(url)
    group = socket.inet_aton(host)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    stream = await asyncio_dgram.bind((host, port))
    sock = stream.socket
    #sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


async def eventworker_factory(cot_url: str, event_queue,
                              fts_token: str = None):
    """
    Creates a Cursor on Target Event Worker based on URL parameters.

    :param cot_url: URL to CoT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :param fts_token: If supplied, API Token to use for FreeTAKServer REST.
    :return: EventWorker or asyncio Protocol
    """
    # CoT/TAK Event Workers (transmitters):
    if "http" in cot_url.scheme and fts_token:
        eventworker = pytak.FTSClient(
            event_queue,
            cot_url.geturl(),
            fts_token
        )
    elif "tcp" in cot_url.scheme:
        host, port = pytak.parse_cot_url(cot_url)
        _, writer = await asyncio.open_connection(host, port)
        eventworker = pytak.EventWorker(event_queue, writer)
    elif "udp" in cot_url.scheme:
        writer = await pytak.udp_client(cot_url)
        eventworker = pytak.EventWorker(event_queue, writer)

    return eventworker


def faa_to_cot_type(icao_hex: int, category: str = None,
                    flight: str = None) -> str:
    """
    Classify Cursor on Target Event Type from ICAO, and if available, from
    Emitter Category & Flight.
    """
    cm = "C"  # Civ
    attitude = "u"  # Unknown

    icao_int = int(f"0x{icao_hex.replace('~', '')}", 16)

    if flight:
        for dom in pytak.DOMESTIC_AIRLINES:
            if flight.startswith(dom):
                # SN: Should be "n" for Mil/Fed posture.
                attitude = "f"  # FIXME: Default posture depends on user.

    # SN: Leave "neutral" as Taiwan uses this subset instead of PRC China....
    tw_start = 0x899000
    tw_end = 0x8993FF
    if tw_start <= icao_int <= tw_end:
        attitude = "n"

    # SN: Make the US range (all non-mil) ICAO addresses just generic "n"
    us_civ_start = pytak.DEFAULT_HEX_RANGES["US-CIV"]["start"]
    us_civ_end = pytak.DEFAULT_HEX_RANGES["US-CIV"]["end"]
    if us_civ_start <= icao_int <= us_civ_end:
        attitude = "n"

    # Friendly Mil:
    # mil = ["US-MIL", "UK-MIL", "CA-MIL", "NZ-MIL", "AU-MIL"]
    # for fvey in mil:
    #    mil_start = pytak.DEFAULT_HEX_RANGES[fvey]["start"]
    #    mil_end = pytak.DEFAULT_HEX_RANGES[fvey]["end"]
    #    if mil_start <= icao_int <= mil_end:
    #        attitude = "f"
    #        cm = "M"

    # Default Fixed Wing
    cot_type = f"a-{attitude}-A-{cm}-F"

    if category:
        _category = str(category)

        if _category in ["7", "A7"]:  # Rotor/Helicopter
            cot_type = f"a-{attitude}-A-{cm}-H"
        if _category in ["10", "B2"]:  # Balloon
            cot_type = f"a-{attitude}-A-{cm}-L"
        elif _category in ["14", "B6"]:  # Drone
            cot_type = f"a-{attitude}-A-{cm}-F-q"
        elif _category in ["17", "18", "C1", "C2"]:
            cot_type = f"a-.-G-E-V-C-U"
        elif _category in ["19"]:
            cot_type = f"a-{attitude}-G-I-U-T-com-tow"

    return cot_type
