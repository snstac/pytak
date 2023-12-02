#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
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

"""Python Team Awareness Kit (PyTAK) Module Tests."""

import asyncio
import urllib

import pytest
import pytak

__author__ = "Greg Albrecht <gba@snstac.com>"
__copyright__ = "Copyright Sensors & Signals LLC https://www.snstac.com"
__license__ = "Apache License, Version 2.0"


def test_parse_cot_url_https_noport():
    test_url1: str = "https://www.example.com/"
    cot_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    host1, port1 = pytak.parse_url(cot_url1)
    assert "www.example.com" == host1
    assert 8087 == port1


def test_parse_cot_url_tls_noport():
    test_url1: str = "tls://www.example.com"
    cot_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    host1, port1 = pytak.parse_url(cot_url1)
    assert "www.example.com" == host1
    assert 8087 == port1


def test_parse_cot_url_udp_port():
    test_url1: str = "udp://www.example.com:9999"
    cot_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    host1, port1 = pytak.parse_url(cot_url1)
    assert "www.example.com" == host1
    assert 9999 == port1


def test_parse_cot_url_udp_broadcast():
    test_url1: str = "udp+broadcast://www.example.com"
    cot_url1: urllib.parse.ParseResult = urllib.parse.urlparse(test_url1)
    host1, port1 = pytak.parse_url(cot_url1)
    assert "www.example.com" == host1
    assert 6969 == port1


def test_split_host():
    test_host1 = "www.example.com"
    test_port1 = "9999"
    combined_host_port = ":".join([test_host1, test_port1])
    addr, port = pytak.split_host(combined_host_port)
    assert "www.example.com" == addr
    assert 9999 == port


def test_split_host_port():
    test_host1 = "www.example.com"
    test_port1 = "9999"
    addr, port = pytak.split_host(test_host1, test_port1)
    assert "www.example.com" == addr
    assert 9999 == port


def test_split_host_only():
    test_host1 = "www.example.com"
    addr, port = pytak.split_host(test_host1)
    assert "www.example.com" == addr
    assert pytak.DEFAULT_COT_PORT == str(port)


def test_split_host():
    test_host1 = "www.example.com"
    test_port1 = "9999"
    combined_host_port = ":".join([test_host1, test_port1])
    addr, port = pytak.split_host(combined_host_port)
    assert "www.example.com" == addr
    assert 9999 == port


def test_gen_cot():
    """Test gen_cot() XML CoT generator."""
    event = pytak.gen_cot(uid="taco")
    assert b"taco" in event
    assert b"a-u-G" in event


def test_hello_event():
    """Test test_hello_event() Hello Event generator."""
    event = pytak.hello_event("taco")
    assert b"taco" in event
    assert b"t-x-d-d" in event


def test_cot_time():
    """Test that cot_time() returns the proper dateTime string."""
    cot_time = pytak.cot_time()
    assert "Z" in cot_time[-1]
