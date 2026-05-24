#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for TAK onboarding data package generation."""

import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pytak.crypto_functions import (
    load_cert,
    pkcs12_encryption_for_atak_compatible,
    serialize_pkcs12_bundle,
    serialize_trust_pkcs12,
    write_enrollment_artifacts,
)
from pytak.onboarding_packages import (
    build_connection_config_pref_xml,
    build_connection_data_package_zip,
    build_connection_manifest_xml,
    sanitize_package_stem,
)


@pytest.fixture
def sample_p12_bundle(tmp_path):
    """Minimal client + CA PKCS#12 for ZIP layout tests."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )
    ee_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "testuser")])
    ee_cert = (
        x509.CertificateBuilder()
        .subject_name(ee_name)
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )
    password = "test-pass-123"
    p12_path = tmp_path / "testuser.p12"
    blob = serialize_pkcs12_bundle(
        private_key=key,
        certificate=ee_cert,
        ca_certificates=[ca_cert],
        passphrase=password,
        name=b"testuser",
    )
    p12_path.write_bytes(blob)
    trust_path = tmp_path / "testuser-trust.p12"
    trust_path.write_bytes(serialize_trust_pkcs12([ca_cert], password))
    return {
        "p12_path": str(p12_path),
        "trust_p12_path": str(trust_path),
        "password": password,
        "certs_dir": str(tmp_path),
        "stem": "testuser",
    }


def test_sanitize_package_stem():
    assert sanitize_package_stem("user@host") == "user_host"
    assert sanitize_package_stem("  ") == "enrollment"


def test_config_pref_xml_atak_vs_itak_paths():
    atak = build_connection_config_pref_xml(
        stream_description="desc",
        streaming_host="tak.example.com",
        streaming_port=8089,
        ca_password="pw",
        client_password="pw",
        location_callsign="CALL",
        package_layout="atak",
    )
    assert "cert/caCert.p12" in atak
    assert "cert/clientCert.p12" in atak
    itak = build_connection_config_pref_xml(
        stream_description="desc",
        streaming_host="tak.example.com",
        streaming_port=8089,
        ca_password="pw",
        client_password="pw",
        location_callsign="CALL",
        package_layout="itak",
    )
    assert "caCert.p12" in itak
    assert "cert/caCert.p12" not in itak


def test_manifest_xml_zip_entries():
    atak = build_connection_manifest_xml(
        uid="uid-1", display_name="atak.zip", package_layout="atak"
    )
    assert 'zipEntry="certs/config.pref"' in atak
    itak = build_connection_manifest_xml(
        uid="uid-2", display_name="itak.zip", package_layout="itak"
    )
    assert 'zipEntry="config.pref"' in itak
    assert "certs/" not in itak


def test_connection_zip_layouts(sample_p12_bundle):
    pref = build_connection_config_pref_xml(
        stream_description="d",
        streaming_host="host",
        streaming_port=8089,
        ca_password=sample_p12_bundle["password"],
        client_password=sample_p12_bundle["password"],
        location_callsign="c",
        package_layout="atak",
    )
    manifest = build_connection_manifest_xml(
        uid="u", display_name="n", package_layout="atak"
    )
    atak_bytes = build_connection_data_package_zip(
        config_pref_xml=pref,
        manifest_xml=manifest,
        client_p12_path=sample_p12_bundle["p12_path"],
        trust_p12_path=sample_p12_bundle["trust_p12_path"],
        package_layout="atak",
    )
    with zipfile.ZipFile(io.BytesIO(atak_bytes)) as zf:
        names = zf.namelist()
    assert "MANIFEST/manifest.xml" in names
    assert "certs/config.pref" in names
    assert "certs/caCert.p12" in names
    assert "certs/clientCert.p12" in names

    itak_bytes = build_connection_data_package_zip(
        config_pref_xml=pref,
        manifest_xml=build_connection_manifest_xml(
            uid="u", display_name="n", package_layout="itak"
        ),
        client_p12_path=sample_p12_bundle["p12_path"],
        trust_p12_path=sample_p12_bundle["trust_p12_path"],
        package_layout="itak",
    )
    with zipfile.ZipFile(io.BytesIO(itak_bytes)) as zf:
        names = zf.namelist()
    assert "config.pref" in names
    assert "caCert.p12" in names
    assert "clientCert.p12" in names
    assert not any(n.startswith("certs/") for n in names)


def test_write_enrollment_artifacts(sample_p12_bundle, tmp_path):
    out_dir = tmp_path / "out"
    result = write_enrollment_artifacts(
        sample_p12_bundle["p12_path"],
        sample_p12_bundle["password"],
        str(out_dir),
        sample_p12_bundle["stem"],
    )
    assert result["pkcs12_path"]
    assert result["pkcs12_truststore_path"]
    for key in ("private_key_path", "certificate_path", "ca_bundle_path"):
        assert result[key]
        assert __import__("os").path.isfile(result[key])


def test_pkcs12_atak_encryption_roundtrip(sample_p12_bundle):
    enc = pkcs12_encryption_for_atak_compatible(sample_p12_bundle["password"])
    assert enc is not None
    _key, cert, cas = load_cert(
        sample_p12_bundle["p12_path"], sample_p12_bundle["password"]
    )
    assert cert is not None
    assert cas
