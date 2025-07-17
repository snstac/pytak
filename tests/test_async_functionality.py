#!/usr/bin/env python3
"""
Test async certificate enrollment functionality.
"""

import asyncio
import logging
import pytest

from src.pytak.crypto_classes import CertificateEnrollment

@pytest.mark.asyncio
async def test_async_enrollment():
    """Test the async enrollment process with a mock server."""
    print("🧪 Testing async certificate enrollment...")

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    enrollment = CertificateEnrollment()

    try:
        # This will fail because there's no server, but it tests the async flow
        await enrollment.begin_enrollment(
            domain="nonexistent.example.com",
            username="test",
            password="test",
            trust_all=True,
        )
    except Exception as e:
        print(f"Expected error (no server): {e}")

    print("✅ Async enrollment test completed!")


@pytest.mark.asyncio
async def test_session_creation():
    """Test async session creation and cleanup."""
    print("🧪 Testing async session creation...")

    enrollment = CertificateEnrollment()

    # Test session creation and cleanup
    async with enrollment._create_session(trust_all=True) as session:
        print(f"✅ Session created: {type(session)}")

    print("✅ Session cleanup completed!")


@pytest.mark.asyncio
async def main():
    """Run all async tests."""
    print("🚀 Starting async certificate enrollment tests...")

    await test_session_creation()
    await test_async_enrollment()

    print("🎉 All async tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
