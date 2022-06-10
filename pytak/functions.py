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

import datetime
import platform
import xml.etree.ElementTree as ET

from urllib.parse import ParseResult, urlparse

import pytak  # pylint: disable=cyclic-import

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
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
    return addr, int(port)


def parse_url(url: str) -> tuple:
    """Parses a COT destination URL."""
    if isinstance(url, str):
        url: ParseResult = urlparse(url)

    if ":" in url.netloc:
        host, port = url.netloc.split(":")
    else:
        host = url.netloc
        if "broadcast" in url.scheme:
            port = pytak.DEFAULT_BROADCAST_PORT
        elif "multicast" in url.scheme:
            port = pytak.DEFAULT_BROADCAST_PORT
        else:
            port = pytak.DEFAULT_COT_PORT
    return host, int(port)


def cot_time(cot_stale: int = None) -> datetime.datetime:
    """
    Returns the current time UTC in ISO-8601 format.

    Parameters
    ----------
    cot_stale : `int`
        Time in seconds to add to the current time, for use with Cursor-On-Target
        'stale' attributes.

    Returns
    -------
    `datetime.datetime`
        Current time UTC in ISO-8601 Format
    """
    time = datetime.datetime.now(datetime.timezone.utc)
    if cot_stale:
        time = time + datetime.timedelta(seconds=int(cot_stale))
    return time.strftime(pytak.ISO_8601_UTC)


def hello_event(uid: str = None) -> str:
    """Generates a Hello COT Event."""
    uid: str = uid or f"pytak@{platform.node()}"

    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", "t-x-d-d")
    root.set("uid", uid)
    root.set("how", "m-g")
    root.set("time", cot_time())
    root.set("start", cot_time())
    root.set("stale", cot_time(3600))

    return ET.tostring(root)
