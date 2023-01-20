#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2023 Greg Albrecht <oss@undef.net>
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

"""PyTAK Crypto (as in cryptography) Functions."""

import os
import tempfile
import warnings

from typing import Union


INSTALL_MSG = (
    "Python cryptography module not installed. Install with: "
    " python3 -m pip install cryptography"
)

USE_CRYPTOGRAPHY = False
try:
    from cryptography.hazmat.backends.openssl.rsa import _RSAPrivateKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509 import Certificate

    USE_CRYPTOGRAPHY = True
except ImportError:
    warnings.warn(INSTALL_MSG)


__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2023 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


def save_pem(pem: bytes, dest: Union[str, None] = None) -> str:
    """Save PEM data to dest."""
    if dest:
        with open(dest, "wb+") as dest_fd:
            dest_fd.write(pem)
        pem_path: str = dest
    else:
        pem_fd, pem_path = tempfile.mkstemp(suffix=".pem")
        with os.fdopen(pem_fd, "wb+") as pfd:
            pfd.write(pem)

    assert os.path.exists(pem_path)
    return pem_path


def load_cert(cert_path: str, cert_pass: str): # -> Set[_RSAPrivateKey, Certificate, Certificate]:
    """Load RSA Keys & Certs from a pkcs12 ().p12) file."""
    if not USE_CRYPTOGRAPHY:
        raise Exception(INSTALL_MSG)

    with open(cert_path, "br+") as cp_fd:
        p12_data = cp_fd.read()

    res = pkcs12.load_key_and_certificates(p12_data, str.encode(cert_pass))
    assert len(res) == 3
    return res


def convert_cert(cert_path: str, cert_pass: str) -> dict:
    """Convert a P12 cert to PEM."""
    if not USE_CRYPTOGRAPHY:
        raise Exception(INSTALL_MSG)

    cert_paths = {
        "pk_pem_path": None,
        "cert_pem_path": None,
        "ca_pem_path": None,
    }

    res = load_cert(cert_path, cert_pass)

    private_key: _RSAPrivateKey = res[0]
    cert: Certificate = res[1]
    ca_cert: Certificate = res[2][0]

    # Load privkey
    pk_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_paths["pk_pem_path"] = save_pem(pk_pem)

    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    cert_paths["cert_pem_path"] = save_pem(cert_pem)

    ca_pem = ca_cert.public_bytes(encoding=serialization.Encoding.PEM)
    cert_paths["ca_pem_path"] = save_pem(ca_pem)

    assert all(cert_paths)
    return cert_paths
