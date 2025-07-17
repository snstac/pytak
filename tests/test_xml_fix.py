#!/usr/bin/env python3
"""
Test script to verify the XML parsing fix works with real TAK server XML.
"""

from src.pytak.crypto_classes import CertificateEnrollment


def test_real_xml():
    """Test with the actual XML that was failing."""
    enrollment = CertificateEnrollment()

    # This is the actual XML from your error log
    xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns2:certificateConfig xmlns="http://bbn.com/marti/xml/config" xmlns:ns2="com.bbn.marti.config"><nameEntries><nameEntry name="O" value="SNSTAC"/><nameEntry name="OU" value="TAK"/></nameEntries></ns2:certificateConfig>"""

    config = enrollment._parse_config_xml(xml_content)

    print("✅ XML Parsing Test Results:")
    print(f"   Original XML: {xml_content[:50]}...")
    print(f"   Parsed config: {config}")

    expected = {"O": "SNSTAC", "OU": "TAK"}
    if config == expected:
        print("✅ SUCCESS: XML parsing is working correctly!")
        return True
    else:
        print(f"❌ FAILED: Expected {expected}, got {config}")
        return False


if __name__ == "__main__":
    success = test_real_xml()
    exit(0 if success else 1)
