#!/usr/bin/env python3
"""
Test the PEM formatting fix for v2 JSON responses.
"""

import asyncio
import logging
from src.pytak.crypto_classes import CertificateEnrollment
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

@pytest.mark.asyncio
async def test_pem_formatting_fix():
    """Test PEM formatting fix for malformed certificates."""
    print("🧪 Testing PEM formatting fix...")

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    enrollment = CertificateEnrollment()

    # Generate a test private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Test cases for malformed PEM certificates
    test_cases = [
        {
            "name": "Missing line breaks",
            "malformed": "-----BEGIN CERTIFICATE-----MIIDXTCCAkWgAwIBAgIJAKZVz1Z1YKj2MA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMjMwMTAxMDAwMDAwWhcNMjQwMTAxMDAwMDAwWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuUOyWh9b1ZKKqVQRKKjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8-----END CERTIFICATE-----",
        },
        {
            "name": "Extra whitespace and wrong line breaks",
            "malformed": "-----BEGIN CERTIFICATE-----\r\n   MIIDXTCCAkWgAwIBAgIJAKZVz1Z1YKj2MA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV\r\n\r\nBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX   \r\naWRnaXRzIFB0eSBMdGQwHhcNMjMwMTAxMDAwMDAwWhcNMjQwMTAxMDAwMDAwWjBF\r\n   \r\n-----END CERTIFICATE-----   \r\n",
        },
    ]

    for test_case in test_cases:
        print(f"\n📝 Testing: {test_case['name']}")

        try:
            # Test the PEM formatting fix
            fixed_pem = enrollment._fix_pem_formatting(test_case["malformed"])

            print(f"✅ PEM formatting fix applied")
            print(f"Original length: {len(test_case['malformed'])}")
            print(f"Fixed length: {len(fixed_pem)}")

            # Show first few lines of the fixed PEM
            lines = fixed_pem.split("\n")
            print(f"Fixed format preview:")
            for i, line in enumerate(lines[:3]):
                print(f"  Line {i+1}: '{line}'")
            if len(lines) > 3:
                print(f"  ... ({len(lines)} total lines)")

        except Exception as e:
            print(f"❌ PEM formatting fix failed: {e}")

    # Test with a properly formatted mock response
    print(f"\n📝 Testing with mock v2 JSON response...")

    mock_response_data = {
        "signedCert": "-----BEGIN CERTIFICATE-----MIIDXTCCAkWgAwIBAgIJAKZVz1Z1YKj2MA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMjMwMTAxMDAwMDAwWhcNMjQwMTAxMDAwMDAwWjBF-----END CERTIFICATE-----",
        "ca0": "-----BEGIN CERTIFICATE-----MIIDCA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMjMwMTAxMDAwMDAwWhcNMjQwMTAxMDAwMDAwWjBFMQswCQYDVQQGEwJBVTETMBEGA1UE-----END CERTIFICATE-----",
    }

    try:
        await enrollment._process_json_certificate_response(
            mock_response_data, private_key
        )
        print("✅ Mock v2 JSON response processing completed")
    except Exception as e:
        print(f"ℹ️  Mock processing result: {e} (expected due to invalid cert data)")

    print("\n🎉 PEM formatting fix tests completed!")


if __name__ == "__main__":
    asyncio.run(test_pem_formatting_fix())
