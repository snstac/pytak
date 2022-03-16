#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""PyTAK Functions."""

import datetime
import xml
import xml.etree.ElementTree

import pytak
import pytak.asyncio_dgram

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


def parse_cot_url(url: str) -> tuple:
    """Parses a COT destination URL."""
    if ":" in url.netloc:
        host, port = url.netloc.split(":")
    else:
        host = url.netloc
        if "broadcast" in url.scheme:
            port = pytak.DEFAULT_BROADCAST_PORT
        else:
            port = pytak.DEFAULT_COT_PORT
    return host, int(port)


def hello_event(uid="pytak") -> str:
    """Generates a Hello COT Event."""
    time = datetime.datetime.now(datetime.timezone.utc)

    root = xml.etree.ElementTree.Element("event")

    root.set("version", "2.0")
    root.set("type", "t-x-d-d")
    root.set("uid", uid)
    root.set("how", "m-g")
    root.set("time", time.strftime(pytak.ISO_8601_UTC))
    root.set("start", time.strftime(pytak.ISO_8601_UTC))
    root.set("stale", (time + datetime.timedelta(hours=1)).strftime(pytak.ISO_8601_UTC) )

    return xml.etree.ElementTree.tostring(root)
