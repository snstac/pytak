#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __init__.py from https://github.com/snstac/pytak
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

"""Python Team Awareness Kit (PyTAK) Module."""

from .constants import (  # NOQA
    LOG_LEVEL,
    LOG_FORMAT,
    DEFAULT_COT_PORT,
    DEFAULT_BACKOFF,
    DEFAULT_SLEEP,
    DEFAULT_ATAK_PORT,
    DEFAULT_BROADCAST_PORT,
    DEFAULT_COT_STALE,
    DEFAULT_FIPS_CIPHERS,
    W3C_XML_DATETIME,
    DEFAULT_TC_TOKEN_URL,
    DEFAULT_COT_URL,
    DEFAULT_TLS_PARAMS_OPT,
    DEFAULT_TLS_PARAMS_REQ,
    DEFAULT_HOST_ID,
    BOOLEAN_TRUTH,
    DEFAULT_XML_DECLARATION,
    DEFAULT_IMPORT_OTHER_CONFIGS,
    DEFAULT_TAK_PROTO,
    DEFAULT_PYTAK_MULTICAST_LOCAL_ADDR,
    DEFAULT_COT_ACCESS,
    DEFAULT_COT_CAVEAT,
    DEFAULT_COT_RELTO,
    DEFAULT_COT_QOS,
    DEFAULT_COT_OPEX,
    DEFAULT_COT_VAL,
    DEFAULT_MAX_OUT_QUEUE,
    DEFAULT_MAX_IN_QUEUE,
    ISO_8601_UTC,
    DEFAULT_TLS_ENROLLMENT_CERT_PASSPHRASE_LENGTH
)

from .classes import (  # NOQA
    Worker,
    TXWorker,
    RXWorker,
    QueueWorker,
    CLITool,
    SimpleCOTEvent,
    COTEvent,
    TAKDataPackage
)

from .functions import (  # NOQA
    split_host,
    parse_url,
    hello_event,
    cot_time,
    gen_cot,
    gen_cot_xml,
    cot2xml,
    enroll_tak,
    decode_response
)

from .client_functions import (  # NOQA
    create_udp_client,
    protocol_factory,
    txworker_factory,
    rxworker_factory,
    cli,
    read_pref_package,
)

from . import asyncio_dgram  # NOQA
