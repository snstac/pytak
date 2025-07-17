#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# crypto_functions.py from https://github.com/snstac/pytak
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

"""PyTAK Crypto (as in cryptography) Functions."""

import os
import tempfile
import warnings
import ssl

from typing import Union,Tuple


INSTALL_MSG = (
    "Python cryptography module not installed. Install with: "
    " python3 -m pip install cryptography"
)

# Check if cryptography is installed
USE_CRYPTOGRAPHY = False
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
    from cryptography.x509 import Certificate
    from cryptography.hazmat.primitives.asymmetric import rsa

    USE_CRYPTOGRAPHY = True
except ImportError as exc:
    warnings.warn(str(exc))


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


def load_cert(
    cert_path: str, cert_pass: str
):  # -> Set[_RSAPrivateKey, Certificate, Certificate]:
    """Load RSA Keys & Certs from a pkcs12 ().p12) file."""
    if not USE_CRYPTOGRAPHY:
        raise ValueError(INSTALL_MSG)

    with open(cert_path, "br+") as cp_fd:
        p12_data = cp_fd.read()

    res = pkcs12.load_key_and_certificates(p12_data, str.encode(cert_pass))
    assert len(res) == 3
    return res


def convert_cert(cert_path: str, cert_pass: str) -> dict:
    """Convert a P12 cert to PEM."""
    if not USE_CRYPTOGRAPHY:
        raise ValueError(INSTALL_MSG)

    cert_paths = {
        "pk_pem_path": None,
        "cert_pem_path": None,
        "ca_pem_path": None,
    }

    private_key, cert, additional_certificates = load_cert(cert_path, cert_pass)

    # Load privkey
    pk_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_paths["pk_pem_path"] = save_pem(pk_pem)

    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    cert_paths["cert_pem_path"] = save_pem(cert_pem)

    ca_cert: Certificate = additional_certificates[0]
    ca_pem = ca_cert.public_bytes(encoding=serialization.Encoding.PEM)
    cert_paths["ca_pem_path"] = save_pem(ca_pem)

    assert all(cert_paths)
    return cert_paths



def convert_p12_to_pem(output_path: str, passphrase: str) -> Tuple[str, str]:
    # Convert .p12 to PEM
    with open(output_path, "rb") as p12_file:
        p12_data = p12_file.read()
    private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
        p12_data, passphrase.encode()
    )
    
    # Write PEM files
    pem_key_path = output_path + ".key.pem"
    pem_cert_path = output_path + ".cert.pem"
    
    with open(pem_key_path, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption()
            )
        )
        
    with open(pem_cert_path, "wb") as cert_file:
        cert_file.write(cert.public_bytes(Encoding.PEM))
        if additional_certs:
            for ca in additional_certs:
                cert_file.write(ca.public_bytes(Encoding.PEM))
                
    return pem_key_path, pem_cert_path


def create_ssl_context(output_path, passphrase):
    """Creates an SSL Context from a PKCS#12 certificate container."""
    # Convert the .p12 file to PEM format
    pem_key_path, pem_cert_path = convert_p12_to_pem(output_path, passphrase)
    print(f"Converted PKCS#12 to PEM. Key path: {pem_key_path}, Cert path: {pem_cert_path}")
    
    # Create an SSL context using the PEM files
    # ssl_context = ssl.create_default_context()
    ssl_context = ssl._create_unverified_context()
    ssl_context.load_cert_chain(certfile=pem_cert_path, keyfile=pem_key_path)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    return ssl_context