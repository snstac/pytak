#!/usr/bin/env python3
"""
Test script for Certificate Enrollment module.

This script tests the basic functionality without requiring a live server.
"""

import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys
import os


from src.pytak.crypto_classes import CertificateEnrollment


class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases."""

    def setUp(self):
        """Set up async test environment."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up async test environment."""
        self.loop.close()

    def async_test(self, coro):
        """Helper to run async tests."""
        return self.loop.run_until_complete(coro)


class TestCertificateEnrollment(AsyncTestCase):
    """Test cases for CertificateEnrollment class."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.enrollment = CertificateEnrollment()

    def test_init(self):
        """Test initialization of CertificateEnrollment."""
        self.assertIsNotNone(self.enrollment)
        self.assertIsNotNone(self.enrollment.logger)

    def test_generate_key(self):
        """Test private key generation."""
        private_key = self.enrollment._generate_key()
        self.assertIsNotNone(private_key)
        # Test key size
        self.assertEqual(private_key.key_size, 4096)

    def test_parse_config_xml(self):
        """Test XML configuration parsing."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <configuration>
            <entry name="C" value="US"/>
            <entry name="ST" value="Virginia"/>
            <entry name="L" value="City"/>
            <entry name="O" value="Organization"/>
            <entry name="OU" value="Unit"/>
        </configuration>"""

        config = self.enrollment._parse_config_xml(xml_content)

        expected_config = {
            "C": "US",
            "ST": "Virginia",
            "L": "City",
            "O": "Organization",
            "OU": "Unit",
        }

        self.assertEqual(config, expected_config)

    def test_parse_namespaced_config_xml(self):
        """Test XML configuration parsing with namespaces (newer TAK format)."""
        xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns2:certificateConfig xmlns="http://bbn.com/marti/xml/config" xmlns:ns2="com.bbn.marti.config"><nameEntries><nameEntry name="O" value="SNSTAC"/><nameEntry name="OU" value="TAK"/></nameEntries></ns2:certificateConfig>"""

        config = self.enrollment._parse_config_xml(xml_content)

        expected_config = {"O": "SNSTAC", "OU": "TAK"}

        self.assertEqual(config, expected_config)

    def test_create_session_trust_all(self):
        """Test session creation with trust_all=True."""

        async def _test():
            session = self.enrollment._create_session(trust_all=True)
            self.assertIsNotNone(session)
            await session.close()

        self.async_test(_test())

    def test_create_session_normal(self):
        """Test session creation with normal SSL verification."""

        async def _test():
            session = self.enrollment._create_session(trust_all=False)
            self.assertIsNotNone(session)
            await session.close()

        self.async_test(_test())
        # For aiohttp sessions, we don't have a direct verify attribute
        # But we know it was created successfully

    def test_create_csr_from_config(self):
        """Test CSR creation from configuration."""
        config = {"CN": "testuser", "O": "Test Organization", "C": "US"}

        private_key = self.enrollment._generate_key()
        csr_pem = self.enrollment._create_csr_from_config(config, private_key)

        self.assertIsNotNone(csr_pem)
        self.assertIn("-----BEGIN CERTIFICATE REQUEST-----", csr_pem)
        self.assertIn("-----END CERTIFICATE REQUEST-----", csr_pem)

    def test_empty_xml_config(self):
        """Test handling of empty XML configuration."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <configuration>
        </configuration>"""

        config = self.enrollment._parse_config_xml(xml_content)
        self.assertEqual(config, {})

    def test_invalid_xml_config(self):
        """Test handling of invalid XML."""
        xml_content = "This is not valid XML"

        config = self.enrollment._parse_config_xml(xml_content)
        self.assertEqual(config, {})


def run_tests():
    """Run all tests."""
    print("Running Certificate Enrollment tests...")

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCertificateEnrollment)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    if result.wasSuccessful():
        print(f"\n✅ All {result.testsRun} tests passed!")
    else:
        print(
            f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)"
        )
        return False

    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
