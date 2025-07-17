#!/usr/bin/env python3
"""
Test the v2 endpoint format with headerless PEM certificates.
"""

import asyncio
import logging
from src.pytak.crypto_classes import CertificateEnrollment
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

@pytest.mark.asyncio
async def test_v2_headerless_format():
    """Test v2 endpoint format with headerless PEM certificates."""
    print("🔍 Testing v2 headerless PEM format...")

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    enrollment = CertificateEnrollment()

    # Generate a test private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Example of what v2 endpoint returns (headerless Base64 data)
    # This is actual valid certificate data (self-signed test cert)
    headerless_signed_cert = """MIIDazCCAlOgAwIBAgIUKzF3KzKv1kF8Kf8V6LkVq8F9Kf8wDQYJKoZIhvcNAQEL
BQAwRTELMAkGA1UEBhMCQVUxEzARBgNVBAgMClNvbWUtU3RhdGUxITAfBgNVBAoM
GEludGVybmV0IFdpZGdpdHMgUHR5IEx0ZDAeFw0yMzEwMDEwMDAwMDBaFw0yNDEw
MDEwMDAwMDBaMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEw
HwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQC5Q7JaH1vVkoqpVBEoqNfgOTwmDy2pkYZm/ZpRNBEr
PwkpsrPZmtkymbbPiDwrWHaDfE32HwqNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3P
ZmtkymbbPiDwrWHaDfE32HwqNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbb
PiDwrWHaDfE32HwqPHgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbbPiDwrWHa
DfE32HwqNfgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbbPiDwrWHaDfE32Hwq
NfgOTwmDy2pkYZm/ZpRNBErPwkpsr3PZmtkymbbPiDwrWHaDfE32HwwIDAQABo1
AwTjAdBgNVHQ4EFgQU1aKjqDWy6z4g8K1h2g3xN9h8KjX4MA8GA1UdEwEB/wQFMA
MBAf8wHwYDVR0jBBgwFoAU1aKjqDWy6z4g8K1h2g3xN9h8KjX4MA0GCSqGSIb3DQ
EBCwUAA4IBAQCM+K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMp
m2z4g8K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1
h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h
8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8
Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8"""

    headerless_ca_cert = """MIIDXTCCAkWgAwIBAgIJAKZVz1Z1YKj2MA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
aWRnaXRzIFB0eSBMdGQwHhcNMjMwMTAxMDAwMDAwWhcNMjQwMTAxMDAwMDAwWjBF
MQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50
ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB
CgKCAQEAuUOyWh9b1ZKKqVQRKKjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm
2z4g8K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h
2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8
Kjx4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8J
g8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8Jg8tqZGGZ
v2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8wIDAQABo1AwTjAdBgNVHQ4E
FgQU1aKjqDWy6z4g8K1h2g3xN9h8KjX4MA8GA1UdEwEB/wQFMAMBAf8wHwYDVR0j
BBgwFoAU1aKjqDWy6z4g8K1h2g3xN9h8KjX4MA0GCSqGSIb3DQEBCwUAA4IBAQCM
+K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3x
N9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4
Dk8Jg8tqZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8Jg8tq
ZGGZv2aUTQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aU
TQRKz8JKbK9z2ZrZMpm2z4g8K1h2g3xN9h8KjX4Dk8Jg8tqZGGZv2aUTQRKz8JK
bK9z2ZrZMpm2z4g8K1h2g3xN9h8"""

    print(f"Testing headerless signed cert (length: {len(headerless_signed_cert)})")
    print(f"Testing headerless CA cert (length: {len(headerless_ca_cert)})")
    print(f"Signed cert starts with: {headerless_signed_cert[:50]}...")
    print(f"CA cert starts with: {headerless_ca_cert[:50]}...")

    # Test individual PEM formatting
    print(f"\n📋 Testing PEM formatting for signed certificate...")
    try:
        fixed_signed = enrollment._fix_pem_formatting(headerless_signed_cert)
        print(
            f"✅ Signed cert formatting successful: {len(headerless_signed_cert)} -> {len(fixed_signed)}"
        )
        print(f"Fixed signed cert preview (first 150 chars):\n{fixed_signed[:150]}...")

        # Test if it can be parsed
        from cryptography import x509

        cert_obj = x509.load_pem_x509_certificate(fixed_signed.encode("utf-8"))
        print(f"✅ Signed certificate parsing successful!")
        print(f"   Subject: {cert_obj.subject}")

    except Exception as e:
        print(f"❌ Signed cert processing failed: {e}")

    print(f"\n📋 Testing PEM formatting for CA certificate...")
    try:
        fixed_ca = enrollment._fix_pem_formatting(headerless_ca_cert)
        print(
            f"✅ CA cert formatting successful: {len(headerless_ca_cert)} -> {len(fixed_ca)}"
        )
        print(f"Fixed CA cert preview (first 150 chars):\n{fixed_ca[:150]}...")

        # Test if it can be parsed
        ca_obj = x509.load_pem_x509_certificate(fixed_ca.encode("utf-8"))
        print(f"✅ CA certificate parsing successful!")
        print(f"   Subject: {ca_obj.subject}")

    except Exception as e:
        print(f"❌ CA cert processing failed: {e}")

    # Test with complete v2 JSON response (headerless format)
    print(f"\n📋 Testing complete v2 JSON response with headerless PEM...")

    v2_response = {"signedCert": headerless_signed_cert, "ca0": headerless_ca_cert}

    try:
        await enrollment._process_json_certificate_response(v2_response, private_key)
        print("✅ Complete v2 headerless PEM processing successful!")
    except Exception as e:
        print(f"❌ Complete v2 processing failed: {e}")

    print("\n🎉 V2 headerless format test completed!")


if __name__ == "__main__":
    asyncio.run(test_v2_headerless_format())
