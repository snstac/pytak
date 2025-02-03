#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# test_crypto_functions.py
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

"""Tests for PyTAK Crypto Functions."""

import os

from unittest import mock
from tempfile import NamedTemporaryFile

import pytak


def test_convert_cert():
    cert_path = "test_cert.p12"
    cert_pass = "test_pass"

    # Mock the load_cert function
    with mock.patch("pytak.crypto_functions.load_cert") as mock_load_cert:
        mock_private_key = mock.Mock()
        mock_cert = mock.Mock()
        mock_additional_certificates = [mock.Mock()]

        mock_load_cert.return_value = (
            mock_private_key,
            mock_cert,
            mock_additional_certificates,
        )

        # Mock the save_pem function
        with mock.patch("pytak.crypto_functions.save_pem") as mock_save_pem:
            mock_save_pem.side_effect = lambda pem: NamedTemporaryFile(
                delete=False
            ).name

            cert_paths = pytak.crypto_functions.convert_cert(cert_path, cert_pass)

            assert "pk_pem_path" in cert_paths
            assert "cert_pem_path" in cert_paths
            assert "ca_pem_path" in cert_paths

            assert os.path.exists(cert_paths["pk_pem_path"])
            assert os.path.exists(cert_paths["cert_pem_path"])
            assert os.path.exists(cert_paths["ca_pem_path"])

            # Clean up temporary files
            os.remove(cert_paths["pk_pem_path"])
            os.remove(cert_paths["cert_pem_path"])
            os.remove(cert_paths["ca_pem_path"])
