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

from __future__ import annotations

import os
import tempfile
import warnings
import ssl

from typing import Any, Dict, List, Optional, Tuple, Union


INSTALL_MSG = (
    "The 'cryptography' package is required but not installed. "
    "Install it with: python3 -m pip install pytak[with-crypto]"
)

# Check if cryptography is installed
USE_CRYPTOGRAPHY = False
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import (
        pkcs12,
        Encoding,
        PrivateFormat,
        NoEncryption,
    )
    from cryptography.x509 import Certificate
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives.asymmetric import rsa

    USE_CRYPTOGRAPHY = True
except ImportError:
    warnings.warn(INSTALL_MSG)


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
    if additional_certificates:
        for ca_cert in additional_certificates:
            cert_pem += ca_cert.public_bytes(encoding=serialization.Encoding.PEM)
    cert_paths["cert_pem_path"] = save_pem(cert_pem)

    if additional_certificates:
        ca_cert_obj: Certificate = additional_certificates[0]
        ca_pem = ca_cert_obj.public_bytes(encoding=serialization.Encoding.PEM)
        cert_paths["ca_pem_path"] = save_pem(ca_pem)

    assert cert_paths["pk_pem_path"] and cert_paths["cert_pem_path"]
    return cert_paths


def _require_crypto() -> None:
    if not USE_CRYPTOGRAPHY:
        raise ValueError(INSTALL_MSG)


def _pkcs12_friendly_name(cert: Certificate) -> Optional[bytes]:
    """PKCS#12 bag friendlyName (CN); matches TAK Server exports."""
    try:
        attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if attrs:
            return attrs[0].value.encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        pass
    return None


def _cas_for_pkcs12(ca_list: List[Certificate]) -> Optional[Tuple[Any, ...]]:
    if not ca_list:
        return None
    return tuple(
        pkcs12.PKCS12Certificate(c, _pkcs12_friendly_name(c)) for c in ca_list
    )


def pkcs12_encryption_for_atak_compatible(
    password: Union[str, bytes],
) -> serialization.KeySerializationEncryption:
    """PKCS#12 encryption ATAK/Android KeyStore accepts for cot_streams bundles."""
    _require_crypto()
    pwb = password.encode("utf-8") if isinstance(password, str) else password
    return (
        PrivateFormat.PKCS12.encryption_builder()
        .hmac_hash(hashes.SHA1())
        .kdf_rounds(2048)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .build(pwb)
    )


def serialize_pkcs12_bundle(
    *,
    private_key,
    certificate: Certificate,
    ca_certificates: Optional[List[Certificate]],
    passphrase: str,
    name: bytes = b"TAK Client Cert",
) -> bytes:
    """Serialize identity or trust PKCS#12 with ATAK-compatible encryption."""
    _require_crypto()
    encryption = (
        pkcs12_encryption_for_atak_compatible(passphrase)
        if passphrase
        else NoEncryption()
    )
    return pkcs12.serialize_key_and_certificates(
        name=name,
        key=private_key,
        cert=certificate,
        cas=_cas_for_pkcs12(ca_certificates or []),
        encryption_algorithm=encryption,
    )


def serialize_trust_pkcs12(
    ca_certificates: List[Certificate],
    passphrase: str,
    name: bytes = b"cadata",
) -> bytes:
    """Serialize CA-only PKCS#12 trust store with ATAK-compatible encryption."""
    _require_crypto()
    if not ca_certificates:
        raise ValueError("No CA certificates for trust PKCS#12")
    encryption = pkcs12_encryption_for_atak_compatible(passphrase)
    return pkcs12.serialize_key_and_certificates(
        name=name,
        key=None,
        cert=None,
        cas=_cas_for_pkcs12(ca_certificates),
        encryption_algorithm=encryption,
    )


def rewrite_pkcs12_atak_compatible(p12_path: str, passphrase: str) -> None:
    """Re-encode an existing PKCS#12 file using ATAK-compatible encryption."""
    _require_crypto()
    private_key, cert, additional = load_cert(p12_path, passphrase)
    if cert is None:
        raise ValueError(f"No certificate in PKCS#12: {p12_path}")
    cas = list(additional or [])
    blob = serialize_pkcs12_bundle(
        private_key=private_key,
        certificate=cert,
        ca_certificates=cas,
        passphrase=passphrase,
        name=os.path.basename(p12_path).encode("utf-8"),
    )
    with open(p12_path, "wb") as f:
        f.write(blob)
    os.chmod(p12_path, 0o600)


def write_enrollment_artifacts(
    p12_path: str,
    passphrase: str,
    output_dir: str,
    stem: str,
) -> Dict[str, Optional[str]]:
    """Write PEM files and ATAK-compatible client/trust PKCS#12 under *output_dir*."""
    _require_crypto()
    os.makedirs(output_dir, exist_ok=True)
    private_key, cert, additional = load_cert(p12_path, passphrase)
    if cert is None:
        raise ValueError(f"No certificate in PKCS#12: {p12_path}")
    ca_list = list(additional or [])

    key_path = os.path.join(output_dir, f"{stem}-key.pem")
    cert_path = os.path.join(output_dir, f"{stem}.pem")
    ca_path = os.path.join(output_dir, f"{stem}-ca.pem") if ca_list else None
    trust_p12_path = os.path.join(output_dir, f"{stem}-trust.p12") if ca_list else None
    client_p12_path = os.path.join(output_dir, f"{stem}.p12")

    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    os.chmod(key_path, 0o600)

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(encoding=serialization.Encoding.PEM))
    os.chmod(cert_path, 0o644)

    if ca_list:
        with open(ca_path, "w", encoding="utf-8") as f:
            for ca_cert in ca_list:
                f.write(
                    ca_cert.public_bytes(encoding=serialization.Encoding.PEM).decode(
                        "utf-8"
                    )
                )
        os.chmod(ca_path, 0o644)

        trust_blob = serialize_trust_pkcs12(ca_list, passphrase)
        with open(trust_p12_path, "wb") as f:
            f.write(trust_blob)
        os.chmod(trust_p12_path, 0o600)

    client_blob = serialize_pkcs12_bundle(
        private_key=private_key,
        certificate=cert,
        ca_certificates=ca_list,
        passphrase=passphrase,
        name=stem.encode("utf-8"),
    )
    with open(client_p12_path, "wb") as f:
        f.write(client_blob)
    os.chmod(client_p12_path, 0o600)

    return {
        "private_key_path": key_path,
        "certificate_path": cert_path,
        "ca_bundle_path": ca_path,
        "pkcs12_path": client_p12_path,
        "pkcs12_truststore_path": trust_p12_path,
        "pkcs12_password": passphrase,
    }


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