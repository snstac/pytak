#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""PyTAK Functions."""

import asyncio
import socket

import asyncio_dgram

import pytak

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2020 Orion Labs, Inc."
__license__ = "Apache License, Version 2.0"


def split_host(host, port: int = None) -> tuple:
    """Given a host:port and/or port, returns host, port."""
    if ":" in host:
        addr, port = host.split(":")
        port = int(port)
    elif port:
        addr = host
        port = int(port)
    else:
        addr = host
        port = int(pytak.DEFAULT_COT_PORT)
    return addr, port


def parse_cot_url(url) -> tuple:
    """Parses a Cursor on Target destination URL."""
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
    """Create a CoT UDP Network Client"""
    host, port = parse_cot_url(url)
    stream = await asyncio_dgram.connect((host, port))
    if "broadcast" in url.scheme:
        sock = stream.socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


async def multicast_client(url):
    """Create a CoT Multicast Network Client."""
    host, port = parse_cot_url(url)
    stream = await asyncio_dgram.bind((host, port))
    sock = stream.socket
    # group = socket.inet_aton(host)
    # mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    # sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return stream


async def protocol_factory(cot_url, fts_token: str = None):
    reader = None
    writer = None
    if "http" in cot_url.scheme and fts_token:  # pylint: disable=no-else-raise
        raise Exception(
            "HTTP Support is not implemented yet. Send beer to gba@undef.net")
        # event_worker = pytak.FTSClient(
        #    event_queue,
        #    cot_url.geturl(),
        #    fts_token
        # )
    elif "tcp" in cot_url.scheme:
        host, port = pytak.parse_cot_url(cot_url)
        reader, writer = await asyncio.open_connection(host, port)
    elif "udp" in cot_url.scheme:
        reader = None
        writer = await pytak.udp_client(cot_url)
    else:
        raise Exception(
            "Please specify a protocol in your URL, for example: tcp:xxx or "
            "udp:xxx")
    return reader, writer


async def eventworker_factory(cot_url: str, event_queue,
                              fts_token: str = None) -> pytak.Worker:
    """
    Creates a Cursor on Target Event Worker based on URL parameters.

    :param cot_url: URL to CoT Destination.
    :param event_queue: asyncio.Queue worker to get events from.
    :param fts_token: If supplied, API Token to use for FreeTAKServer REST.
    :return: EventWorker or asyncio Protocol
    """
    reader, writer = await protocol_factory(cot_url, fts_token)
    return pytak.EventWorker(event_queue, writer)


def hex_country_lookup(icao_int: int) -> str:
    """
    Pull country from ICAO Hex within the stdin file when there is no match to
    csv files (e.g., faa-aircraft.csv).
    """
    for country_dict in pytak.ICAO_RANGES:
        start = country_dict["start"]
        end = country_dict["end"]
        if start <= icao_int <= end:
            return country_dict["country"]


def faa_to_cot_type(icao_hex: int, category: str = None,
                    flight: str = None) -> str:
    """
    Classify Cursor on Target Event Type from ICAO, and if available, from
    Emitter Category & Flight.
    """
    affil = "C"  # Affiliation, default = Civilian
    attitude = "."  # Attitude

    icao_int = int(f"0x{icao_hex.replace('~', '')}", 16)

    if flight:
        for dom in pytak.DOMESTIC_AIRLINES:
            if flight.startswith(dom):
                # SN: Should be "n" for Mil/Fed posture.
                attitude = "f"  # FIXME: Default posture depends on user.

    tw_start = 0x899000
    tw_end = 0x8993FF
    if tw_start <= icao_int <= tw_end:
        attitude = "n"

    civs = ["US-CIV", "CAN-CIV", "NZ-CIV", "AUS-CIV", "UK-CIV"]
    for civ in civs:
        civ_start = pytak.DEFAULT_HEX_RANGES[civ]["start"]
        civ_end = pytak.DEFAULT_HEX_RANGES[civ]["end"]
        if civ_start <= icao_int <= civ_end:
            attitude = "n"

    if hex_country_lookup(icao_int):
        attitude = "n"

    # Friendly Mil:
    mil = ["US-MIL", "CAN-MIL", "NZ-MIL", "AUS-MIL", "UK-MIL"]
    for fvey in mil:
        mil_start = pytak.DEFAULT_HEX_RANGES[fvey]["start"]
        mil_end = pytak.DEFAULT_HEX_RANGES[fvey]["end"]
        if mil_start <= icao_int <= mil_end:
            attitude = "f"
            affil = "M"

    cot_type = f"a-{attitude}-A-{affil}"

    if category:
        _category = str(category)

        if _category in ["1", "2", "3", "4", "5", "6", "A1", "A2", "A3", "A4", "A5", "A6"]:  # Fixed
            cot_type = f"a-{attitude}-A-{affil}-F"
        elif _category in ["7", "A7"]:  # Rotor/Helicopter
            cot_type = f"a-{attitude}-A-{affil}-H"
        elif _category in ["10", "B2"]:  # Balloon
            cot_type = f"a-{attitude}-A-{affil}-L"
        elif _category in ["14", "B6"]:  # Drone
            cot_type = f"a-{attitude}-A-{affil}-F-q"
        elif _category in ["17", "18", "C1", "C2"]:
            cot_type = "a-.-G-E-V-C-U"
        elif _category in ["19"]:
            cot_type = f"a-{attitude}-G-I-U-T-com-tow"

    return cot_type

