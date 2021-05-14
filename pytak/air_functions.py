#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""PyTAK Functions."""

import asyncio
import datetime
import os
import socket
import ssl
import xml
import xml.etree.ElementTree


import pytak
import pytak.asyncio_dgram

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2021 Orion Labs, Inc."
__license__ = "Apache License, Version 2.0"


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
    ### TODO:  pull this out into a custom csv or txt file of known aircraft you want to assign a specific CoT type based on FlightID AND/OR ICAO HEX address
    if flight and len(flight) >= 3 and flight[:2] in ["C6", b"C6"]:
        if affil and affil in ["M", b"M"]:
            return True


# flight ID is limited to 8 digits in the DO-260B specification
def adsb_to_cot_type(icao_hex: int, category: str = None, flight: str = None) -> str:
    """
    Classify Cursor on Target Event Type from ICAO address (binary, decimal, octal, or hex; and if available, from
    ADS-B DO-260B or GDL90 Emitter Category & Flight ID.
    """
    affil = "C"  # Affiliation, default = Civilian
    attitude = "."  # Attitude

    # TODO: If the adsbx has a leading underscore and registry "_N1234A" then that means they are calculating the
    #  registration with no Flight ID field transmited
    # TODO: If no specific country allocated ICAO address range, e.g. "country": "Rsrvd (ICAO SAM Region)" or
    #  "country": "ICAO (special use)" set
    #         OMMIT {affil}
    #         {attitude} = u    (unknown)

    # The "~" is a adsbexchange (possibly a few others) visual customization to indicate a non (MLAT, ADS-B ICAO hex)
    # ADS-B track injected by the FAA via the ADS-B rebroadcast, usually FAA Secondary Radar Mode A/C tracks for safety
    # and ground vehicles
    icao_int = int(f"0x{icao_hex.replace('~', 'TIS-B_')}", 16)

    # TODO: Eliminate this if section, as it will already be coded as neutral civil cot type if left alone which
    #  fits the cot framework.
    if flight:
        for dom in pytak.DOMESTIC_AIRLINES:
            if flight.startswith(dom):
                attitude = "n"

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

        # Fixed wing. No CoT exists to further categorize based on DO-260B/GDL90 emitter catagory, cannot determine if
        # Cargo, Passenger, or other without additional info.
        if _category in ["1", "2", "3", "4", "5", "A1", "A2", "A3", "A4", "A5"]:
            cot_type = f"a-{attitude}-A-{affil}-F"
        # Fixed wing. High Performance (basically a fighter jet) type="a-.-A-M-F-F" capable: >5g & >400 knots
        elif _category in ["6", "A6"]:
            # Force the MIL {affil} "F" icon for fast mover, even if a civil ICAO address, no pink/magenta 2525 icon
            # exists; just = s_apmff--------.png
            affil = "M"
            cot_type = f"a-{attitude}-A-{affil}-F-F"
        # Rotor/Helicopter
        elif _category in ["7", "A7"]:
            cot_type = f"a-{attitude}-A-{affil}-H"
        # Glider/sailplane
        elif _category in ["9", "B1"]:
            cot_type = f"a-{attitude}-A-{affil}-F"
        # Lighter-than-air, Balloon
        elif _category in ["10", "B2"]:
            cot_type = f"a-{attitude}-A-{affil}-L"
        # Drone/UAS/RPV
        elif _category in ["14", "B6"]:
            # This will have to have {affil}=M to generate a 2525B marker in TAK.
            # Cannot be CIV "C" as no CIV drone icons exist for 2525B
            affil = "M"
            cot_type = f"a-{attitude}-A-{affil}-F-Q"
        # Space/Trans-atmospheric vehicle. (e.g SpaceX, Blue Origin, Virgin Galactic)
        elif _category in ["15", "B7"]:
            # Will having -P- affect anything??? ...different than line 223.
            cot_type = f"a-{attitude}-P-{affil}"
        # Surface Vehicle. Includes emergency and service vehicles, as there is no specific 2525B icon for each.
        elif _category in ["17", "18", "C1", "C2"]:
            cot_type = f"a-.-G-E-V-C-U"
        # elif _category in ["17", "C1"]:  #  ***OPTION***  Surface Vehicle - Emergency Vehicle
        #     cot_type = f"a-.-G-E-V-U-A"   # MILSTD 2525B icon = Ambulance (blue circle w/ Cross)
        # "point obstacle (includes tethered ballons)" & "cluster obstacles" i.e. fixed tower -
        #   radio, beacon, tethered ballons, etc  (MILSTD 2525 "D" has a tethered balloon icon that "B" doesn't)
        elif _category in ["19", "20", "C3", "C4"]:
            cot_type = f"a-{attitude}-G-I-U-T-com-tow"
        # This catagory is for all the "No ADS-B Emitter Catagory Information" undefined/unattributed/reserved
        # emmitter catagories in DO-260B/GDL90.
        # adsbexchange will often set A0 for MLAT (TCAS or MODE-S only transponders) tracks
        # add elif or if for:
        #   if no definitive {attitude} and {affil} possible, for the UNKNOWN DO-260B/GDL90 emmitter catagories,
        #   make cot_type = a-u-A
        elif _category in ["0", "8", "13", "16", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32",
                           "33", "34", "35", "36", "37", "38", "39", "A0", "B0", "B5", "C0", "C6", "C7", "D0", "D1",
                           "D2", "D3", "D4", "D5", "D6", "D7"]:
            cot_type = f"a-{attitude}-A-{affil}"

    if dolphin(flight, affil):
        # -H-H is CSAR rotary wing 2525B icon
        cot_type = f"a-f-A-{affil}-H-H"

    return cot_type


faa_to_cot_type = adsb_to_cot_type