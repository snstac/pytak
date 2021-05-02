#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""PyTAK Functions."""

import asyncio
import os
import socket
import ssl

import asyncio_dgram

import pytak

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2021 Orion Labs, Inc."
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
    """
    Given a CoT Destination URL, create a Connection Class Instance for the given protocol.

    :param cot_url: CoT Destination URL
    :param fts_token:
    :return:
    """
    reader = None
    writer = None
    scheme = cot_url.scheme.lower()
    if scheme in ["https", "http", "ws", "wss"]:  # NOQA pylint: disable=no-else-raise
        if "teamconnect" in cot_url.geturl():
            writer = await pytak.TCClient(cot_url).create()
            reader = writer
    elif scheme in ["tcp"]:
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
    elif scheme in ["udp"]:
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


def dolphin(flight: str = None, affil: str = None) -> str:
    """
    Classify an aircraft as USCG Dolphin, or not.
    What, are you afraid of water?
    """
    # MH-65D Dolphins out of Air Station SF use older ADS-B, but luckily have
    # a similar "flight" name.
    # For example:
    # * C6540 / AE2682 https://globe.adsbexchange.com/?icao=ae2682
    # * C6604 / AE26BB https://globe.adsbexchange.com/?icao=ae26bb
    if flight and len(flight) >= 3 and flight[:2] in ["C6", b"C6"]:
        if affil and affil in ["M", b"M"]:
            return True


def adsb_to_cot_type(icao_hex: int, category: str = None,     #change faa_to_cot_type to adsb_to_cot_type....need to update other entries... not specifically a FAA thing...
                    flight: str = None) -> str:               # flight ID is limited to 8 digits in the DO-260B specification
    """
    Classify Cursor on Target Event Type from ICAO address (binary, decimal, octal, or hex; and if available, from
    ADS-B DO-260B or GDL90 Emitter Category & Flight ID.
    """
    affil = "C"  # Affiliation, default = Civilian
    attitude = "."  # Attitude
                                    ### TODO:  If the adsbx has a leading underscore and registry "_N1234A" then that means they are calculating the registration with no Flight ID field transmited

    icao_int = int(f"0x{icao_hex.replace('~', 'TIS-B_')}", 16)  # the "~" is a adsbexchange (possibly a few others) visual customization to indicate a non (MLAT, ADS-B ICAO hex) ADS-B track injected by the FAA via the ADS-B rebroadcast, usually FAA Secondary Radar Mode A/C tracks for safety and ground vehicles

    if flight:
        for dom in pytak.DOMESTIC_AIRLINES:  # can eliminate this if section, as it will already be coded as neutral civil cot type if left alone which fits the cot framework.
            if flight.startswith(dom):
                attitude = "n"
                   
    # tw_start = 0x899000
    # tw_end = 0x8993FF
    # if tw_start <= icao_int <= tw_end:
    #    attitude = "n"

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

        if _category in ["1", "2", "3", "4", "5", "A1", "A2", "A3", "A4", "A5"]:  # Fixed wing
            cot_type = f"a-{attitude}-A-{affil}-F"
        if _category in ["6", "A6"]:              # Fixed wing...High Performance (basically a fighter jet) type="a-.-A-M-F-F"  capable: >5g & >400 knots
            cot_type = f"a-{attitude}-A-M-F-F"    # force the MIL "F" icon for fast mover, even if a civil ICAO address               
        elif _category in ["7", "A7"]:  # Rotor/Helicopter
            cot_type = f"a-{attitude}-A-{affil}-H"
        elif _category in ["9", "B1"]:  # Glider/sailplane
            cot_type = f"a-{attitude}-A-{affil}-F"
        elif _category in ["10", "B2"]:  # Lighter-than-air, Balloon
            cot_type = f"a-{attitude}-A-{affil}-L"
        elif _category in ["14", "B6"]:  # Drone/UAS/RPV
            cot_type = f"a-{attitude}-A-M-F-Q" # this will have to have {affil}=M to generate a 2525B marker in TAK...cannot be CIV "C" as no CIV drone icons exist for 2525B
        elif _category in ["15", "B7"]:  # Space/Trans-atmospheric vehicle - SpaceX, Blue Origin, Virgin Galactic 
            cot_type = f"a-{attitude}-P-{affil}"    # will having -P- affect anything??? ...different than line 223.
        elif _category in ["17", "18", "C1", "C2"]:
            cot_type = f"a-.-G-E-V-C-U"
        elif _category in ["17", "18", "C1", "C2"]:  # includes emergency and service vehicles, as there is no specific 2525B icon for each
            cot_type = f"a-.-G-E-V-C-U"
        elif _category in ["19", "C3"]:
            cot_type = f"a-{attitude}-G-I-U-T-com-tow" # "pont obstacle" i.e. fixed tower - radio, beacon, tethered ballons, etc  (MILSTD 2525 "D" has a tethered balloon icon that "B" doesn't)
        elif _category in ["0", "8", "13", "16", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "A0", "B0", "B5", "C0", "C6", "C7", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7"]:
            cot_type = f"a-{attitude}-A-{affil}"  # unknown air track, need to make sure it is type="a-u-A" if not a specific attitude/affil attribution
                   
    if dolphin(flight, affil):
        cot_type = f"a-f-A-{affil}-H-H"  # -H-H is CSAR rotary wing 2525B icon

    return cot_type

