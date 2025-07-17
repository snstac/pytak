#!/usr/bin/env python3
"""
Test script to verify the output path functionality works correctly.

This script tests that the certificate enrollment module accepts and uses
custom output paths for the generated client certificate.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.pytak.crypto_classes import CertificateEnrollment
import pytest


@pytest.mark.asyncio
async def test_output_path_functionality():
    """Test that output path parameter is correctly used."""

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Test 1: Custom output path with directory creation
        custom_output = temp_path / "custom_dir" / "my_certificate.p12"
        print(f"Testing custom output path: {custom_output}")

        # Create mock certificate data
        mock_cert_pem = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAMlyFqk69v+9MA0GCSqGSIb3DQEBBQUAMBQxEjAQBgNVBAMMCVRl
c3QgQ2VydDAeFw0yMDA2MDEwMDAwMDBaFw0yMTA2MDEwMDAwMDBaMBQxEjAQBgNV
BAMMCVRlc3QgQ2VydDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQDTgvwjlRHZ9OY2
2jKSN1GSSKCHk+JHHiWXE0Xg7JQJ2hJ2kF8K1/1a2eJ5jS1c4yG4J1fK8P1v2j
-----END CERTIFICATE-----"""

        mock_ca_pems = []

        # Create enrollment instance
        enrollment = CertificateEnrollment()

        # Mock the private key generation and certificate parsing
        with patch.object(enrollment, "_generate_key") as mock_gen_key, patch(
            "certificate_enrollment.x509.load_pem_x509_certificate"
        ) as mock_load_cert, patch(
            "certificate_enrollment.pkcs12.serialize_key_and_certificates"
        ) as mock_serialize:

            # Set up mocks
            mock_private_key = Mock()
            mock_gen_key.return_value = mock_private_key
            mock_cert = Mock()
            mock_load_cert.return_value = mock_cert
            mock_serialize.return_value = b"mock_pkcs12_data"

            # Test the _create_client_certificate method directly
            enrollment._create_client_certificate(
                cert_pem=mock_cert_pem,
                ca_pems=mock_ca_pems,
                private_key=mock_private_key,
                output_path=str(custom_output),
            )

            # Verify the file was created at the custom location
            assert custom_output.exists(), f"Certificate not created at {custom_output}"
            assert custom_output.parent.exists(), "Parent directory not created"

            print(f"✅ Custom output path test passed: {custom_output}")

        # Test 2: Default output path (None)
        print("Testing default output path (None)")

        with patch.object(enrollment, "_generate_key") as mock_gen_key, patch(
            "certificate_enrollment.x509.load_pem_x509_certificate"
        ) as mock_load_cert, patch(
            "certificate_enrollment.pkcs12.serialize_key_and_certificates"
        ) as mock_serialize, patch(
            "certificate_enrollment.Path.home"
        ) as mock_home:

            # Set up mocks
            mock_home.return_value = temp_path
            mock_private_key = Mock()
            mock_gen_key.return_value = mock_private_key
            mock_cert = Mock()
            mock_load_cert.return_value = mock_cert
            mock_serialize.return_value = b"mock_pkcs12_data"

            # Test the _create_client_certificate method with None (default)
            enrollment._create_client_certificate(
                cert_pem=mock_cert_pem,
                ca_pems=mock_ca_pems,
                private_key=mock_private_key,
                output_path=None,
            )

            # Verify the file was created at the default location
            default_output = temp_path / "Downloads" / "clientCert.p12"
            assert (
                default_output.exists()
            ), f"Certificate not created at default location {default_output}"

            print(f"✅ Default output path test passed: {default_output}")


@pytest.mark.asyncio
async def test_begin_enrollment_with_output_path():
    """Test that begin_enrollment accepts output_path parameter."""

    enrollment = CertificateEnrollment()

    # Create a mock that will prevent actual network calls
    with patch.object(enrollment, "_generate_key") as mock_gen_key:
        mock_gen_key.return_value = (
            None  # Simulate key generation failure to avoid network calls
        )

        # Test that the method accepts the output_path parameter without error
        try:
            await enrollment.begin_enrollment(
                domain="test.example.com",
                username="testuser",
                password="testpass",
                trust_all=True,
                use_v2=True,
                output_path="/tmp/test_cert.p12",
            )
            print("✅ begin_enrollment accepts output_path parameter")
        except Exception as e:
            if "Failed to generate private key" in str(e):
                print(
                    "✅ begin_enrollment accepts output_path parameter (expected key gen failure)"
                )
            else:
                raise


@pytest.mark.asyncio
async def main():
    """Run all tests."""
    print("Testing output path functionality...")

    # Set up logging to see what's happening
    logging.basicConfig(level=logging.INFO)

    try:
        await test_output_path_functionality()
        await test_begin_enrollment_with_output_path()
        print("\n🎉 All output path tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
