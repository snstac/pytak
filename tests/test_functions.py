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


def test_cot2xml():
    """Test gen_cot_xml2() function."""
    event = pytak.COTEvent(
        lat=37.7749,
        lon=-122.4194,
        ce=10,
        hae=100,
        le=5,
        uid="test_uid",
        stale=3600,
        cot_type="a-f-G",
    )
    xml_element = pytak.cot2xml(event)
    assert xml_element is not None
    assert xml_element.tag == "event"
    assert xml_element.get("version") == "2.0"
    assert xml_element.get("type") == "a-f-G"
    assert xml_element.get("uid") == "test_uid"
    assert xml_element.get("how") == "m-g"
    assert xml_element.get("time") is not None
    assert xml_element.get("start") is not None
    assert xml_element.get("stale") is not None

    point_element = xml_element.find("point")
    assert point_element is not None
    assert point_element.get("lat") == "37.7749"
    assert point_element.get("lon") == "-122.4194"
    assert point_element.get("le") == "5"
    assert point_element.get("hae") == "100"
    assert point_element.get("ce") == "10"

    detail_element = xml_element.find("detail")
    assert detail_element is not None
    flow_tags_element = detail_element.find("_flow-tags_")
    assert flow_tags_element is not None
    assert (
        flow_tags_element.get(f"{pytak.DEFAULT_HOST_ID}-pytak".replace("@", "-"))
        is not None
    )
