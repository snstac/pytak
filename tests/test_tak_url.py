#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for tak:// URL parsing and cert cache helpers."""

import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

import pytest

import pytak
from pytak.client_functions import (
    parse_tak_url,
    _cert_cache_paths,
    _cached_cert_valid,
    resolve_tak_url,
)


# ---------------------------------------------------------------------------
# parse_tak_url
# ---------------------------------------------------------------------------


def test_parse_tak_url_full():
    url = "tak://com.atakmap.app/enroll?host=tak.example.com:8089&username=alice&token=supersecrettoken"
    result = parse_tak_url(url)
    assert result["hostname"] == "tak.example.com"
    assert result["port"] == 8089
    assert result["username"] == "alice"
    assert result["token"] == "supersecrettoken"


def test_parse_tak_url_no_port():
    url = "tak://com.atakmap.app/enroll?host=tak.example.com&username=bob&token=mytoken"
    result = parse_tak_url(url)
    assert result["hostname"] == "tak.example.com"
    assert result["port"] == pytak.DEFAULT_TAK_STREAMING_PORT
    assert result["username"] == "bob"


def test_parse_tak_url_default_port_value():
    assert pytak.DEFAULT_TAK_STREAMING_PORT == 8089


def test_parse_tak_url_bad_scheme():
    with pytest.raises(ValueError, match="tak://"):
        parse_tak_url("https://tak.example.com/enroll?host=x&username=u&token=t")


def test_parse_tak_url_missing_username():
    with pytest.raises(ValueError, match="username"):
        parse_tak_url("tak://com.atakmap.app/enroll?host=tak.example.com&token=t")


def test_parse_tak_url_missing_token():
    with pytest.raises(ValueError, match="token"):
        parse_tak_url("tak://com.atakmap.app/enroll?host=tak.example.com&username=u")


def test_parse_tak_url_missing_host():
    with pytest.raises(ValueError, match="host"):
        parse_tak_url("tak://com.atakmap.app/enroll?username=u&token=t")


def test_parse_tak_url_url_encoded_values():
    url = "tak://com.atakmap.app/enroll?host=tak.example.com%3A8089&username=alice%40org&token=tok"
    result = parse_tak_url(url)
    assert result["hostname"] == "tak.example.com"
    assert result["port"] == 8089
    assert result["username"] == "alice@org"


# ---------------------------------------------------------------------------
# _cached_cert_valid
# ---------------------------------------------------------------------------


def test_cached_cert_valid_missing_file():
    assert _cached_cert_valid("/nonexistent/path.p12", "pass") is False


def test_cached_cert_valid_bad_passphrase(tmp_path):
    p12 = tmp_path / "cert.p12"
    p12.write_bytes(b"not a real p12")
    assert _cached_cert_valid(str(p12), "wrongpass") is False


def test_cached_cert_valid_with_real_cert(tmp_path):
    """Generate a real (self-signed) cert, serialize to p12, and validate."""
    pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )

    passphrase = "testpass"
    p12_data = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(
            passphrase.encode()
        ),
    )
    p12_path = str(tmp_path / "cert.p12")
    with open(p12_path, "wb") as f:
        f.write(p12_data)

    assert _cached_cert_valid(p12_path, passphrase) is True


def test_cached_cert_valid_expired(tmp_path):
    """Cert that expires in 3 days is invalid with default 7-day buffer."""
    pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=30))
        .not_valid_after(now + timedelta(days=3))  # expires in 3 days
        .sign(key, hashes.SHA256())
    )

    passphrase = "testpass"
    p12_data = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(
            passphrase.encode()
        ),
    )
    p12_path = str(tmp_path / "cert.p12")
    with open(p12_path, "wb") as f:
        f.write(p12_data)

    # default buffer is 7 days → cert expiring in 3 days should be invalid
    assert _cached_cert_valid(p12_path, passphrase) is False
    # but with a 2-day buffer it's still valid
    assert _cached_cert_valid(p12_path, passphrase, buffer_days=2) is True


# ---------------------------------------------------------------------------
# resolve_tak_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_tak_url_enrolls_when_no_cache(tmp_path):
    """resolve_tak_url should enroll and write cert when cache is empty."""
    url = "tak://com.atakmap.app/enroll?host=tak.example.com:8089&username=alice&token=secret"

    mock_p12 = tmp_path / "cert.p12"

    def fake_enroll(*a, **kw):
        mock_p12.write_bytes(b"fakep12data")
        return None

    with mock.patch(
        "pytak.client_functions._cert_cache_paths",
        return_value=(str(mock_p12), str(tmp_path / "cert.pass")),
    ), mock.patch(
        "pytak.client_functions._cached_cert_valid", return_value=False
    ), mock.patch(
        "pytak.crypto_classes.CertificateEnrollment.begin_enrollment",
        new=mock.AsyncMock(side_effect=fake_enroll),
    ):
        result = await resolve_tak_url(url)

    assert result["COT_URL"] == "tls://tak.example.com:8089"
    assert result["PYTAK_TLS_CLIENT_CERT"] == str(mock_p12)
    assert result["PYTAK_TLS_DONT_VERIFY"] == "1"
    assert result["PYTAK_TLS_DONT_CHECK_HOSTNAME"] == "1"
    assert "PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE" in result


@pytest.mark.asyncio
async def test_resolve_tak_url_uses_cached_cert(tmp_path):
    """resolve_tak_url should skip enrollment when a valid cached cert exists."""
    url = "tak://com.atakmap.app/enroll?host=tak.example.com&username=bob&token=tok"

    mock_p12 = tmp_path / "cert.p12"
    mock_p12.write_bytes(b"fakep12data")
    mock_pass = tmp_path / "cert.pass"
    mock_pass.write_text("stored_passphrase")

    with mock.patch(
        "pytak.client_functions._cert_cache_paths",
        return_value=(str(mock_p12), str(mock_pass)),
    ), mock.patch(
        "pytak.client_functions._cached_cert_valid", return_value=True
    ), mock.patch(
        "pytak.crypto_classes.CertificateEnrollment.begin_enrollment"
    ) as mock_enroll:
        result = await resolve_tak_url(url)
        mock_enroll.assert_not_called()

    assert result["COT_URL"] == f"tls://tak.example.com:{pytak.DEFAULT_TAK_STREAMING_PORT}"
    assert result["PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE"] == "stored_passphrase"


@pytest.mark.asyncio
async def test_resolve_tak_url_raises_when_enrollment_fails(tmp_path):
    """resolve_tak_url raises RuntimeError if enrollment doesn't produce a cert."""
    url = "tak://com.atakmap.app/enroll?host=tak.example.com&username=alice&token=tok"

    missing_p12 = str(tmp_path / "missing.p12")

    with mock.patch(
        "pytak.client_functions._cert_cache_paths",
        return_value=(missing_p12, str(tmp_path / "missing.pass")),
    ), mock.patch(
        "pytak.client_functions._cached_cert_valid", return_value=False
    ), mock.patch(
        "pytak.crypto_classes.CertificateEnrollment.begin_enrollment",
        new=mock.AsyncMock(),  # does nothing → file never written
    ):
        with pytest.raises(RuntimeError, match="enrollment failed"):
            await resolve_tak_url(url)
