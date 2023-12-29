#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

"""Python Team Awareness Kit (PyTAK) Module.

:source: <https://github.com/snstac/pytak>
"""

__version__ = "6.2.3"


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
    DEFAULT_MIN_ASYNC_SLEEP,
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
)

from .classes import (  # NOQA
    Worker,
    TXWorker,
    RXWorker,
    QueueWorker,
    CLITool,
)

from .functions import (
    split_host,
    parse_url,
    hello_event,
    cot_time,
    gen_cot,
    gen_cot_xml,
)  # NOQA

from .client_functions import (  # NOQA
    create_udp_client,
    protocol_factory,
    txworker_factory,
    rxworker_factory,
    cli,
    read_pref_package,
)

from . import asyncio_dgram  # NOQA

# from .crypto_functions import *

__author__ = "Greg Albrecht <gba@snstac.com>"
__copyright__ = "Copyright Sensors & Signals LLC https://www.snstac.com"
__license__ = "Apache License, Version 2.0"
