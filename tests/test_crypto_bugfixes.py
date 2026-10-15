#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regression tests for bugs fixed in pytak.crypto_functions / crypto_classes."""

import asyncio
import datetime
import os

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("aiohttp")

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from pytak import crypto_functions
from pytak.crypto_classes import CertificateEnrollment

PASSWORD = "test-p12-pass"


def _make_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _make_cert(key, common_name="pytak-test", issuer_key=None, issuer_name=None):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name or name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(issuer_key or key, hashes.SHA256())
    )


def _write_p12(path, key, cert, cas, password=PASSWORD):
    data = pkcs12.serialize_key_and_certificates(
        b"test",
        key,
        cert,
        cas,
        serialization.BestAvailableEncryption(password.encode()),
    )
    path.write_bytes(data)
    return str(path)


@pytest.fixture
def trust_store_p12(tmp_path):
    """A CA trust-store style .p12: CA certs only, no key, no client cert."""
    ca_key = _make_key()
    ca_cert = _make_cert(ca_key, "test-ca")
    return _write_p12(tmp_path / "truststore.p12", None, None, [ca_cert])


def test_convert_cert_trust_store_p12_raises_value_error(trust_store_p12):
    """GitHub issue #74: convert_cert crashed with AttributeError on NoneType."""
    with pytest.raises(ValueError, match="no private key and/or client certificate"):
        crypto_functions.convert_cert(trust_store_p12, PASSWORD)


def test_convert_cert_trust_store_p12_writes_no_temp_files(
    trust_store_p12, monkeypatch
):
    saved = []
    real_save_pem = crypto_functions.save_pem

    def _tracking_save_pem(pem, dest=None):
        path = real_save_pem(pem, dest)
        saved.append(path)
        return path

    monkeypatch.setattr(crypto_functions, "save_pem", _tracking_save_pem)
    with pytest.raises(ValueError):
        crypto_functions.convert_cert(trust_store_p12, PASSWORD)
    assert saved == []


def test_convert_p12_to_pem_trust_store_p12_raises_value_error(trust_store_p12):
    """GitHub issue #74: convert_p12_to_pem crashed and left an empty key file."""
    with pytest.raises(ValueError, match="no private key and/or client certificate"):
        crypto_functions.convert_p12_to_pem(trust_store_p12, PASSWORD)
    assert not os.path.exists(trust_store_p12 + ".key.pem")
    assert not os.path.exists(trust_store_p12 + ".cert.pem")


def test_convert_p12_to_pem_cert_without_key_raises_value_error(tmp_path):
    key = _make_key()
    cert = _make_cert(key)
    p12 = _write_p12(tmp_path / "certonly.p12", None, cert, None)
    with pytest.raises(ValueError, match="no private key and/or client certificate"):
        crypto_functions.convert_p12_to_pem(p12, PASSWORD)
    assert not os.path.exists(p12 + ".key.pem")


def test_write_enrollment_artifacts_cert_without_key_raises_value_error(
    tmp_path, monkeypatch
):
    # cryptography files an unpaired cert under additional certs, so stub
    # load_cert to model a PKCS#12 that yields a client cert but no key.
    key = _make_key()
    cert = _make_cert(key)
    monkeypatch.setattr(
        crypto_functions, "load_cert", lambda path, password: (None, cert, [])
    )
    p12 = str(tmp_path / "certonly.p12")
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="No private key"):
        crypto_functions.write_enrollment_artifacts(p12, PASSWORD, str(out_dir), "c")
    assert not (out_dir / "c-key.pem").exists()


class _FakeResponse:
    def __init__(self, status=200, body=b""):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self):
        return self._body


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append(url)
        return self.response


def test_process_csr_v1_pkcs12_writes_encrypted_client_cert(tmp_path, monkeypatch):
    """_process_csr's v1 path passed 4 args to a 3-arg method (TypeError).

    The resulting client .p12 must also honour the requested passphrase.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ca_key = _make_key()
    ca_cert = _make_cert(ca_key, "test-ca")
    client_key = _make_key()
    client_cert = _make_cert(
        client_key, "client", issuer_key=ca_key, issuer_name=ca_cert.subject
    )
    server_p12 = pkcs12.serialize_key_and_certificates(
        b"srv",
        None,
        client_cert,
        [ca_cert],
        serialization.BestAvailableEncryption(b"atakatak"),
    )
    session = _FakeSession(_FakeResponse(200, server_p12))
    output_path = tmp_path / "certs" / "client.p12"

    enrollment = CertificateEnrollment()
    asyncio.run(
        enrollment._process_csr(
            "user",
            "pass",
            session,
            "takserver.example.com",
            "CSR",
            client_key,
            use_v2=False,
            output_path=str(output_path),
            passphrase="enroll-pass",
        )
    )

    assert session.posts == [
        "https://takserver.example.com:8446/Marti/api/tls/signClient?clientUid=test"
    ]
    assert output_path.exists()
    key, cert, cas = pkcs12.load_key_and_certificates(
        output_path.read_bytes(), b"enroll-pass"
    )
    assert cert.subject == client_cert.subject
    assert key.private_numbers() == client_key.private_numbers()
    assert [c.subject for c in cas] == [ca_cert.subject]
