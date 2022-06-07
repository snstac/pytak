#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2022 Greg Albrecht <oss@undef.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author:: Greg Albrecht W2GMD <oss@undef.net>
# Copyright:: Copyright 2022 Greg Albrecht
# License:: Apache License, Version 2.0
#

"""
Python Team Awareness Kit (PyTAK) Module.
~~~~


:author: Greg Albrecht W2GMD <oss@undef.net>
:copyright: Copyright 2022 Greg Albrecht
:license: Apache License, Version 2.0
:source: <https://github.com/ampledata/pytak>

"""

from .constants import (
    LOG_LEVEL,
    LOG_FORMAT,
    DEFAULT_COT_PORT,
    DEFAULT_BACKOFF,
    DEFAULT_SLEEP,
    DEFAULT_ATAK_PORT,
    DEFAULT_BROADCAST_PORT,
    DEFAULT_COT_STALE,
    DEFAULT_FIPS_CIPHERS,
    ISO_8601_UTC,
    DEFAULT_TC_TOKEN_URL,
    DEFAULT_COT_URL,
    DEFAULT_TLS_PARAMS_OPT,
    DEFAULT_TLS_PARAMS_REQ,
    DEFAULT_HOST_ID,
)

from .classes import (
    Worker,
    EventWorker,
    MessageWorker,
    EventReceiver,
    CLITool,
)

from .functions import split_host, parse_cot_url, hello_event, cot_time

from .client_functions import (
    create_udp_client,
    eventworker_factory,
    protocol_factory,
    cli,
)

from . import asyncio_dgram


__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
__license__ = "Apache License, Version 2.0"
