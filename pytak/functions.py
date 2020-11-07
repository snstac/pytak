#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""APRS Cursor-on-Target Constants."""

import asyncio
import socket

import pytak

import asyncio_dgram

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


def faa_to_cot_type(category: int, flight: str = None,
                    icao_hex: str = None) -> str:
    """
    Determine Cursor on Target Event Type from ADS-B Emitter Category & Flight.

    :param category:
    :param flight:
    :return:
    """
    cm = "C"  # Civ/Mil

    fof = "u"  # Non-FVEY

    if flight:
        for dom in pytak.DOMESTIC_AIRLINES:
            if flight.startswith(dom):
                fof = "f"

    if (pytak.DEFAULT_HEX_RANGES["US"][0] <= int(f"0x{icao_hex}", 16) <=
            pytak.DEFAULT_HEX_RANGES["US"][1]):
        fof = "f"

    fvey = ["UK", "CA", "NZ", "AU"]
    for fkey in fvey:
        if (pytak.DEFAULT_HEX_RANGES[fkey][0] <= int(f"0x{icao_hex}", 16) <=
                pytak.DEFAULT_HEX_RANGES[fkey][1]):
            fof = "n"

    if category == 7:  # Rotor/Helicopter
        cot_type = f"a-{fof}-A-{cm}-H"
    if category == 10:  # Balloon
        cot_type = f"a-{fof}-A-{cm}-L"
    elif category == 14:  # Drone
        cot_type = f"a-{fof}-A-{cm}-F-q"
    elif category == 17 or category == 18:
        cot_type = f"a-{fof}-G-E-V-C"
    elif category == 19:
        cot_type = f"a-{fof}-G-I-U-T-com-tow"
    else:  # Default Fixed Wing
        cot_type = f"a-{fof}-A-{cm}-F"

    return cot_type
