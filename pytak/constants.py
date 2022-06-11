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

"""PyTAK Constants."""

import logging
import os
import platform


__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


if bool(os.environ.get("DEBUG")):
    LOG_LEVEL: int = logging.DEBUG
    LOG_FORMAT: logging.Formatter = logging.Formatter(
        (
            "%(asctime)s pytak %(levelname)s %(name)s.%(funcName)s:%(lineno)d - "
            "%(message)s"
        )
    )
    logging.debug("pytak Debugging Enabled via DEBUG Environment Variable.")
else:
    LOG_LEVEL: int = logging.INFO
    LOG_FORMAT: logging.Formatter = logging.Formatter(
        ("%(asctime)s pytak %(levelname)s - %(message)s")
    )

DEFAULT_COT_URL: str = "udp://239.2.3.1:6969"  # ATAK Default multicast
DEFAULT_COT_STALE: int = "120"
DEFAULT_HOST_ID: str = f"pytak@{platform.node()}"

DEFAULT_COT_PORT: int = 8087
DEFAULT_ATAK_PORT: int = 4242
DEFAULT_BROADCAST_PORT: int = 6969

DEFAULT_BACKOFF: int = 120
DEFAULT_SLEEP: int = 5
DEFAULT_FIPS_CIPHERS: str = (
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384"
)
ISO_8601_UTC = "%Y-%m-%dT%H:%M:%S.%fZ"

TC_TOKEN_URL = "https://app-api.parteamconnect.com/api/v1/auth/token"
DEFAULT_TC_TOKEN_URL = os.getenv("TC_TOKEN_URL", TC_TOKEN_URL)

DEFAULT_TLS_PARAMS_REQ: list = [
    "PYTAK_TLS_CLIENT_CERT",
]

DEFAULT_TLS_PARAMS_OPT: list = [
    "PYTAK_TLS_CLIENT_KEY",
    "PYTAK_TLS_CLIENT_CAFILE",
    "PYTAK_TLS_CLIENT_CIPHERS",
    "PYTAK_TLS_DONT_CHECK_HOSTNAME",
    "PYTAK_TLS_DONT_VERIFY",
]
