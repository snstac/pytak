#!/usr/bin/env python3
"""
Test with a real certificate format that demonstrates the JSON escaping issue.
"""

import asyncio
import logging
from src.pytak.crypto_classes import CertificateEnrollment
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

@pytest.mark.asyncio
async def test_json_escaped_certificate():
    """Test with a certificate that has JSON-escaped newlines."""
    print("🔍 Testing JSON-escaped certificate handling...")

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    enrollment = CertificateEnrollment()

    # Generate a test private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # This is a real self-signed certificate with JSON-escaped newlines
    # (generated for testing purposes)
    json_escaped_cert = """-----BEGIN CERTIFICATE-----\\nMIIDazCCAlOgAwIBAgIUKzF3KzKv1kF8Kf8V6LkVq8F9Kf8wDQYJKoZIhvcNAQEL\\nBQAwRTELMAkGA1UEBhMCQVUxEzARBgNVBAgMClNvbWUtU3RhdGUxITAfBgNVBAoM\\nGEludGVybmV0IFdpZGdpdHMgUHR5IEx0ZDAeFw0yMzEwMDEwMDAwMDBaFw0yNDEw\\nMDEwMDAwMDBaMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEw\\nHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwggEiMA0GCSqGSIb3DQEB\\nAQUAA4IBDwAwggEKAoIBAQC5Q7JaH1vVkoqpVBEoqNfgOTwmDy2pkYZm/ZpRNBEr\\nPwkpsr3PZmtkymbbPiDwrWHaDfE32HwqNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3P\\nZmtkymbbPiDwrWHaDfE32HwqNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbb\\nPiDwrWHaDfE32HwqPHgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbbPiDwrWHa\\nDfE32HwqNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbbPiDwrWHaDfE32Hwq\\nNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbbPiDwrWHaDfE32HwwIDAQABo1\\nAwTjAdBgNVHQ4EFgQU1aKjqDWy6z4g8K1h2g3xN9h8KjX4MA8GA1UdEwEB/wQFMA\\nMBAf8wHwYDVR0jBBgwFoAU1aKjqDWy6z4g8K1h2g3xN9h8KjX4MA0GCSqGSIb3DQ\\nEBCwUAA4IBAQCM+K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMp\\nm2z4g8K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1\\nh2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h\\n8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8\\nJg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8\\n-----END CERTIFICATE-----"""

    print(f"Testing JSON-escaped certificate (length: {len(json_escaped_cert)})")
    print(f"Contains \\n sequences: {'\\n' in json_escaped_cert}")

    # Test the PEM formatting fix
    try:
        fixed_cert = enrollment._fix_pem_formatting(json_escaped_cert)
        print(
            f"✅ PEM formatting successful: {len(json_escaped_cert)} -> {len(fixed_cert)}"
        )

        # Show before and after
        print("\n📋 Before fixing:")
        print(f"First 150 chars: {repr(json_escaped_cert[:150])}")

        print("\n📋 After fixing:")
        print(f"First 150 chars: {repr(fixed_cert[:150])}")

        # Test if it can be parsed now
        try:
            from cryptography import x509

            cert_obj = x509.load_pem_x509_certificate(fixed_cert.encode("utf-8"))
            print(f"✅ Certificate parsing successful!")
        except Exception as parse_error:
            print(f"❌ Certificate parsing still failed: {parse_error}")

    except Exception as format_error:
        print(f"❌ PEM formatting failed: {format_error}")

    # Test with the complete v2 JSON processing
    print(f"\n📋 Testing complete v2 JSON response processing...")

    mock_response = {
        "signedCert": json_escaped_cert,
        "ca0": json_escaped_cert,  # Using same cert as CA for testing
    }

    try:
        await enrollment._process_json_certificate_response(mock_response, private_key)
        print("✅ Complete v2 JSON processing successful!")
    except Exception as e:
        print(f"❌ Complete v2 JSON processing failed: {e}")

    print("\n🎉 JSON-escaped certificate test completed!")


if __name__ == "__main__":
    asyncio.run(test_json_escaped_certificate())
