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

"""PyTAK DPConnect tests."""

import os

import pytak


__folder__ = os.path.dirname(__file__)


def test_load_preferences() -> None:
    """Test loading a preferences file."""
    test_pref: str = __folder__ + "/data/test_pref.pref"
    prefs: dict = pytak.functions.load_preferences(test_pref, __folder__ + "/data")
    assert all(prefs)


def test_load_connectString2url() -> None:
    """Test converting a TAK connectString to a URL"""
    test_pref: str = __folder__ + "/data/test_pref.pref"
    prefs: dict = pytak.functions.load_preferences(test_pref, __folder__ + "/data")
    connect_string: str = prefs.get("connect_string")
    url: str = pytak.functions.connectString2url(connect_string)
    assert url == "ssl://takserver.example.com:8089"


def test_load_cert() -> None:
    cert: list = pytak.crypto_functions.load_cert(
        __folder__ + "/data/test_user_cert.p12", "atakatak"
    )
    assert len(cert) == 3


def test_load_convert_cert():
    """Test converting P12 certs to a PEM certs."""
    test_pref: str = __folder__ + "/data/test_pref.pref"
    prefs: dict = pytak.functions.load_preferences(test_pref, __folder__ + "/data")

    client_password: str = prefs.get("client_password")
    assert client_password

    certificate_location: str = prefs.get("certificate_location")
    assert os.path.exists(certificate_location)

    pem_certs: dict = pytak.crypto_functions.convert_cert(
        certificate_location, client_password
    )
    print(pem_certs)

    pk_pem_path: str = pem_certs.get("pk_pem_path")
    cert_pem_path: str = pem_certs.get("cert_pem_path")
    ca_pem_path: str = pem_certs.get("ca_pem_path")

    assert os.path.exists(pk_pem_path)
    assert os.path.exists(cert_pem_path)
    assert os.path.exists(ca_pem_path)

    with open(__folder__ + "/data/test_pk.pem", "rb+") as tpk_fd:
        test_pk = tpk_fd.read()
        with open(pk_pem_path, "rb+") as pk_fd:
            assert pk_fd.read() == test_pk

    with open(__folder__ + "/data/test_user_cert.pem", "rb+") as tc_fd:
        test_cert = tc_fd.read()
        with open(cert_pem_path, "rb+") as ck_fd:
            assert ck_fd.read() == test_cert

    with open(__folder__ + "/data/test_ca_cert.pem", "rb+") as tc_fd:
        test_cert = tc_fd.read()
        with open(ca_pem_path, "rb+") as ck_fd:
            assert ck_fd.read() == test_cert


def test_read_read_pref_package():
    pref_package = __folder__ + "/data/test_pref_package.zip"
    prefs = pytak.client_functions.read_pref_package(pref_package)
    assert all(prefs)
