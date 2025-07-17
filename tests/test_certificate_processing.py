#!/usr/bin/env python3
"""
Test the improved certificate processing functionality.
"""

from src.pytak.crypto_classes import CertificateEnrollment

import tempfile
import os
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import datetime


def create_test_pkcs12():
    """Create a test PKCS12 file for testing."""
    # Generate a test private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Create a test certificate
    subject = x509.Name(
        [
            x509.NameAttribute(x509.NameOID.COMMON_NAME, "test"),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, "Test Org"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )

    # Create PKCS12 data
    pkcs12_data = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"atakatak"),
    )

    return pkcs12_data


def test_certificate_processing():
    """Test the certificate processing functionality."""
    print("🧪 Testing certificate processing...")

    enrollment = CertificateEnrollment()

    # Create test PKCS12 data
    test_pkcs12 = create_test_pkcs12()

    # Create a test private key for the enrollment
    test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    try:
        # Test the certificate processing
        enrollment._process_certificate_response(test_pkcs12, test_private_key)
        print("✅ Certificate processing test completed")

        # Check if the certificate was created
        from pathlib import Path

        cert_file = Path.home() / "Downloads" / "clientCert.p12"
        if cert_file.exists():
            print(f"✅ Certificate file created: {cert_file}")
            print(f"📁 File size: {cert_file.stat().st_size} bytes")
        else:
            print("⚠️  Certificate file not found")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    test_certificate_processing()
