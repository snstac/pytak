#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""APRS Cursor-on-Target Constants."""

import pytak


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
