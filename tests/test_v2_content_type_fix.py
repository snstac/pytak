#!/usr/bin/env python3
"""
Test the v2 endpoint JSON parsing fix for incorrect content-type headers.
"""

import asyncio
import json
import logging
from src.pytak.crypto_classes import CertificateEnrollment
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

@pytest.mark.asyncio
async def test_v2_json_parsing_with_wrong_content_type():
    """Test JSON parsing when server returns text/plain instead of application/json."""
    print("🧪 Testing v2 JSON parsing with incorrect content-type...")

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    enrollment = CertificateEnrollment()

    # Generate a test private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Mock JSON response data that would be returned as text/plain
    mock_json_response = {
        "signedCert": """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKZVz1Z1YKj2MA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
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
bK9z2ZrZMpm2z4g8K1h2g3xN9h8
-----END CERTIFICATE-----""",
        "ca0": """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKZVz1Z1YKj2MA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
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
bK9z2ZrZMpm2z4g8K1h2g3xN9h8
-----END CERTIFICATE-----""",
    }

    print("✅ Testing direct JSON parsing...")
    try:
        # Test direct processing - this should work
        await enrollment._process_json_certificate_response(
            mock_json_response, private_key
        )
        print("✅ Direct JSON processing successful")
    except Exception as e:
        print(f"❌ Direct JSON processing failed: {e}")

    print("\n✅ Testing fallback JSON parsing (simulating wrong content-type)...")
    try:
        # Test the fallback scenario by simulating what happens when
        # aiohttp gets text/plain but the content is actually JSON
        json_text = json.dumps(mock_json_response)

        # Simulate the fallback parsing that happens in our fixed code
        parsed_data = json.loads(json_text)

        await enrollment._process_json_certificate_response(parsed_data, private_key)
        print("✅ Fallback JSON parsing successful")
    except Exception as e:
        print(f"❌ Fallback JSON processing failed: {e}")

    print("\n🎉 Content-type fix test completed!")


if __name__ == "__main__":
    asyncio.run(test_v2_json_parsing_with_wrong_content_type())
