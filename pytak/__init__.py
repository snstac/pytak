#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Python Team Awareness Kit (PyTAK) Module.

"""
Python Team Awareness Kit (PyTAK) Module.
~~~~


:author: Greg Albrecht W2GMD <oss@undef.net>
:copyright: Copyright 2020 Orion Labs, Inc.
:license: Apache License, Version 2.0
:source: <https://github.com/ampledata/pytak>

"""

from .constants import (LOG_LEVEL, LOG_FORMAT, DEFAULT_COT_PORT,  # NOQA
                        DEFAULT_BACKOFF)

from .classes import NetworkClient, CoTWorker  # NOQA

__author__ = 'Greg Albrecht W2GMD <oss@undef.net>'
__copyright__ = 'Copyright 2020 Orion Labs, Inc.'
__license__ = 'Apache License, Version 2.0'
