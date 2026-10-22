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

"""Behavioural coverage tests for pytak.functions."""

import json
import os
import xml.etree.ElementTree as ET

from unittest import mock
from urllib.parse import urlparse

import pytest

import pytak
import pytak.functions as fn


def test_truncate_float_rejects_negative_precision():
    with pytest.raises(ValueError, match="precision"):
        fn.truncate_float(1.5, -1)


def test_parse_url_multicast_without_port_warns_and_uses_default():
    with pytest.warns(DeprecationWarning, match="multicast"):
        host, port = fn.parse_url("udp+multicast://239.2.3.1")
    assert host == "239.2.3.1"
    assert port == int(pytak.DEFAULT_BROADCAST_PORT)


def test_parse_url_plain_without_port_uses_cot_port():
    assert fn.parse_url(urlparse("tcp://takserver.example.com")) == (
        "takserver.example.com",
        int(pytak.DEFAULT_COT_PORT),
    )


def test_parse_mqtt_url_requires_hostname():
    with pytest.raises(SyntaxError, match="broker hostname"):
        fn.parse_mqtt_url("mqtt:///cot")


def test_parse_mqtt_url_requires_mqtt_scheme():
    with pytest.raises(SyntaxError, match="mqtt://"):
        fn.parse_mqtt_url("tcp://broker.example.com/cot")


def test_parse_mqtt_url_reassembles_fragment_from_parse_result():
    """A ParseResult that split at '#' still yields the full topic."""
    parts = fn.parse_mqtt_url(urlparse("mqtt://broker.example.com/cot/#sub"))
    assert parts.topic == "cot/#sub"


def test_cot_event_extra_attrs_skip_none_values():
    event = fn.cot_event(
        uid="uid-1", extra_attrs={"custom": 5, "skipped": None}, relto="parent-1"
    )
    assert event.get("custom") == "5"
    assert "skipped" not in event.attrib
    assert event.get("rel_to") == "parent-1"


def test_sanitize_url_credentials_empty():
    assert fn.sanitize_url_credentials("") == ""


def test_find_file_missing_raises_eof(tmp_path):
    with pytest.raises(EOFError, match=r"\*\.pref"):
        fn.find_file(str(tmp_path), "*.pref")


def test_gen_cot_passes_through_non_element():
    with mock.patch.object(fn, "gen_cot_xml", return_value=None):
        assert fn.gen_cot(uid="x") is None


def test_tak_pong_event():
    event = ET.fromstring(fn.tak_pong())
    assert event.tag == "event"
    assert event.get("uid") == "takPong"
    assert event.get("type") == "t-x-d-d"
    assert event.get("time") == event.get("start")
    assert event.get("stale") > event.get("time")


@pytest.mark.parametrize("passphrase", [None, "given-passphrase"])
@pytest.mark.asyncio
async def test_enroll_tak(passphrase):
    seen = {}

    class FakeEnrollment:
        async def begin_enrollment(self, **kwargs):
            seen.update(kwargs)

    with mock.patch.object(
        pytak.crypto_classes, "CertificateEnrollment", FakeEnrollment
    ):
        output_path, used = await fn.enroll_tak(
            "takserver.example.com", "user", "example-password", passphrase
        )

    try:
        assert output_path.endswith(".p12")
        assert os.path.exists(output_path)
        assert seen["domain"] == "takserver.example.com"
        assert seen["trust_all"] is True
        assert seen["output_path"] == output_path
        assert seen["passphrase"] == used
        if passphrase:
            assert used == passphrase
        else:
            assert len(used) > 0
    finally:
        os.remove(output_path)


class _Response:
    def __init__(self, json_exc=None, json_value=None, text=""):
        self._json_exc = json_exc
        self._json_value = json_value
        self._text = text

    async def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_value

    async def text(self):
        return self._text


@pytest.mark.asyncio
async def test_decode_response_json():
    assert await fn.decode_response(_Response(json_value={"a": 1})) == {"a": 1}


@pytest.mark.asyncio
async def test_decode_response_json_text_with_wrong_content_type():
    response = _Response(json_exc=ValueError("content-type"), text=json.dumps([1]))
    assert await fn.decode_response(response) == [1]


@pytest.mark.asyncio
async def test_decode_response_plain_text(capsys):
    response = _Response(json_exc=ValueError("content-type"), text="not json")
    assert await fn.decode_response(response) == "not json"
    assert "Failed to decode JSON" in capsys.readouterr().out
