#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Constants."""

import logging
import os

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2020 Orion Labs, Inc."
__license__ = "Apache License, Version 2.0"


if bool(os.environ.get('DEBUG')):
    LOG_LEVEL = logging.DEBUG
    LOG_FORMAT = logging.Formatter(
        ('%(asctime)s pytak %(levelname)s %(name)s.%(funcName)s:%(lineno)d - '
         '%(message)s'))
    logging.debug('pytak Debugging Enabled via DEBUG Environment Variable.')
else:
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = logging.Formatter(
        ('%(asctime)s pytak %(levelname)s - %(message)s'))


DEFAULT_COT_PORT: int = 8087
DEFAULT_ATAK_PORT: int = 4242
DEFAULT_BROADCAST_PORT: int = 6969
DEFAULT_BACKOFF: int = 120
DEFAULT_SLEEP: int = 5

DEFAULT_HEX_RANGES: dict = {
    "US": [0xA00000, 0xAFFFFF],
    "CA": [0xC00000, 0xC3FFFF],
    "NZ": [0xC80000, 0xC87FFF],
    "AU": [0x440000, 0x447FFF],
    "UK": [0x400000, 0x43FFFF]
}

DOMESTIC_AIRLINES: list = [
    "AAL",
    "UAL",
    "FDX",
    "UPS",
    "SWA"
]
