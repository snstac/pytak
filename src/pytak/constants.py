#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# constants.py from https://github.com/snstac/pytak
#
# Copyright Sensors & Signals LLC https://www.snstac.com
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

"""PyTAK Constants."""

import logging
import os
import platform

from typing import Optional


LOG_LEVEL: int = logging.INFO
LOG_FORMAT: logging.Formatter = logging.Formatter(
    ("%(asctime)s pytak %(levelname)s - %(message)s")
)

if os.environ.get("INVOCATION_ID"):
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = logging.Formatter(("[%(levelname)s] %(message)s"))
    logging.debug("Systemd format logging enabled via INVOCATION_ID env var.")

if bool(os.environ.get("DEBUG")):
    LOG_LEVEL = logging.DEBUG
    LOG_FORMAT = logging.Formatter(
        (
            "%(asctime)s pytak %(levelname)s %(name)s.%(funcName)s:%(lineno)d - "
            "%(message)s"
        )
    )
    logging.debug("pytak Debugging Enabled via DEBUG Environment Variable.")

DEFAULT_COT_URL: str = "udp+wo://239.2.3.1:6969"  # ATAK Default multicast
DEFAULT_COT_STALE: str = "120"  # Config wants all values as strings, we'll cast later.
DEFAULT_HOST_ID: str = f"pytak@{platform.node()}"
DEFAULT_COT_PORT: str = "8087"
DEFAULT_ATAK_PORT: str = "4242"
DEFAULT_BROADCAST_PORT: str = "6969"

DEFAULT_BACKOFF: str = "120"
DEFAULT_SLEEP: str = "5"
DEFAULT_FIPS_CIPHERS: str = (
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384"
)

W3C_XML_DATETIME: str = "%Y-%m-%dT%H:%M:%S.%fZ"
ISO_8601_UTC = W3C_XML_DATETIME  # Issue 51: Not technically correct.

TC_TOKEN_URL = "https://app-api.parteamconnect.com/api/v1/auth/token"
DEFAULT_TC_TOKEN_URL = os.getenv("TC_TOKEN_URL", TC_TOKEN_URL)

DEFAULT_TLS_PARAMS_REQ: tuple = ()

# Optimized: Use tuple instead of list for immutable constant (faster access)
DEFAULT_TLS_PARAMS_OPT: tuple = (
    "PYTAK_TLS_CLIENT_CERT",
    "PYTAK_TLS_CLIENT_KEY",
    "PYTAK_TLS_CLIENT_CAFILE",
    "PYTAK_TLS_CLIENT_CIPHERS",
    "PYTAK_TLS_DONT_CHECK_HOSTNAME",
    "PYTAK_TLS_DONT_VERIFY",
    "PYTAK_TLS_CLIENT_PASSWORD",
    "PYTAK_TLS_SERVER_EXPECTED_HOSTNAME",
    "PYTAK_TLS_CERT_ENROLLMENT_USERNAME",
    "PYTAK_TLS_CERT_ENROLLMENT_PASSWORD",
    "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE",
)

DEFAULT_IMPORT_OTHER_CONFIGS: str = "0"

# Optimized: Use tuple for immutable truth values (faster lookups)
BOOLEAN_TRUTH: tuple = ("true", "yes", "y", "on", "1")
DEFAULT_COT_VAL: str = "9999999.0"

# TAK Protocol to use for CoT output, one of: 0 (XML, default), 1 (Mesh/Stream).
# Doesn't always work with iTAK. Recommend sticking with 0 (XML).
DEFAULT_TAK_PROTO: str = "0"

# Python <3.8 has no way of including XML Declaration in ET.tostring():
DEFAULT_XML_DECLARATION: bytes = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
)

# Multicast
DEFAULT_PYTAK_MULTICAST_LOCAL_ADDR: str = "0.0.0.0"

# See MIL-STD-6090.
DEFAULT_COT_ACCESS: Optional[str] = os.getenv("COT_ACCESS", "UNCLASSIFIED")
DEFAULT_COT_CAVEAT: Optional[str] = os.getenv("COT_CAVEAT", "")
DEFAULT_COT_RELTO: Optional[str] = os.getenv("COT_RELTO", "")
DEFAULT_COT_QOS: Optional[str] = os.getenv("COT_QOS", "")
DEFAULT_COT_OPEX: Optional[str] = os.getenv("COT_OPEX", "")

DEFAULT_MAX_OUT_QUEUE = 100
DEFAULT_MAX_IN_QUEUE = 500

DEFAULT_TLS_ENROLLMENT_CERT_PASSPHRASE_LENGTH: int = 16