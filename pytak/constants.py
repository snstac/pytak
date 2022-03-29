#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Constants."""

import logging
import os

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


if bool(os.environ.get('DEBUG')):
    LOG_LEVEL: int = logging.DEBUG
    LOG_FORMAT: logging.Formatter = logging.Formatter(
        ('%(asctime)s pytak %(levelname)s %(name)s.%(funcName)s:%(lineno)d - '
         '%(message)s'))
    logging.debug('pytak Debugging Enabled via DEBUG Environment Variable.')
else:
    LOG_LEVEL: int = logging.INFO
    LOG_FORMAT: logging.Formatter = logging.Formatter(
        ('%(asctime)s pytak %(levelname)s - %(message)s'))


DEFAULT_COT_PORT: int = 8087
DEFAULT_ATAK_PORT: int = 4242
DEFAULT_BROADCAST_PORT: int = 6969
DEFAULT_BACKOFF: int = 120
DEFAULT_SLEEP: int = 5
DEFAULT_COT_STALE: int = 120
DEFAULT_FIPS_CIPHERS: str = "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384"
ISO_8601_UTC = "%Y-%m-%dT%H:%M:%S.%fZ"

TC_TOKEN_URL = 'https://app-api.parteamconnect.com/api/v1/auth/token'
DEFAULT_TC_TOKEN_URL = os.getenv('TC_TOKEN_URL', TC_TOKEN_URL)