#!/usr/bin/env python3
"""
Certificate Enrollment Module

Performs certificate enrollment operations similar to the Android Java implementation.
This module handles certificate signing requests, key generation, and certificate processing.
Uses async/await for improved performance and modern Python patterns.
"""

import asyncio
import base64
import json
import logging
import os
import secrets
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from pathlib import Path

import urllib
import warnings

from pytak.crypto_functions import INSTALL_MSG


USE_CRYPTOGRAPHY = False
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    USE_CRYPTOGRAPHY = True
except ImportError as exc:
    warnings.warn(str(exc))

USE_AIOHTTP = False
try:
    import aiohttp
    from aiohttp import BasicAuth, ClientTimeout
    USE_AIOHTTP = True
except ImportError as exc:
    warnings.warn(str(exc))


class CertificateEnrollment:
    """
    Perform certificate enrollment operations using async/await.

    This class handles the certificate enrollment process including:
    - Key generation
    - Certificate Signing Request (CSR) creation
    - Certificate retrieval and processing
    - Keystore creation
    """

    def __init__(
        self,
        trust_store_path: Optional[str] = None,
    ):
        """
        Initialize the certificate enrollment class.

        Args:
            trust_store_path: Optional path to the trust store certificate file
        """
        if not USE_CRYPTOGRAPHY:
            raise ValueError(INSTALL_MSG)

        if not USE_AIOHTTP:
            raise ValueError(
                "This module requires aiohttp for asynchronous HTTP requests. "
                "Please install it using 'pip install aiohttp'. " 
                "See https://pytak.rtfd.io/ for more details."
            )

        self.logger = logging.getLogger(__name__)
        self.trust_store_path = trust_store_path
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        # Enable debug logging for this module when verbose is needed
        # Uncomment the next line to see more detailed parsing info
        # self.logger.setLevel(logging.DEBUG)

    async def begin_enrollment(
        self,
        domain: str,
        username: str,
        password: str,
        trust_all: bool = False,
        use_v2: bool = True,
        output_path: Optional[str] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        """
        Begin the certificate enrollment process.

        Args:
            domain: The domain for certificate enrollment
            username: Username for authentication
            password: Password for authentication
            trust_all: If True, skip certificate verification (NOT for production)
            use_v2: If True, use the v2 endpoint that returns JSON (default: True)
            output_path: Custom path for the output certificate file. If None,
                        defaults to ~/Downloads/clientCert.p12
        """
        private_key = self._generate_key()
        if private_key is None:
            self.logger.error("Failed to generate private key")
            return

        self.logger.info("Private key generated successfully")

        # Run enrollment asynchronously
        await self._enrollment_process(
            domain,
            username,
            password,
            trust_all,
            private_key,
            use_v2,
            output_path,
            passphrase,
        )

    async def _enrollment_process(
        self,
        domain: str,
        username: str,
        password: str,
        trust_all: bool,
        private_key,
        use_v2: bool = True,
        output_path: Optional[str] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        """
        Async function to handle the enrollment process.

        Args:
            domain: The domain for certificate enrollment
            username: Username for authentication
            password: Password for authentication
            trust_all: If True, skip certificate verification
            private_key: The generated private key
            use_v2: If True, use the v2 endpoint that returns JSON
            output_path: Custom path for the output certificate file
        """
        try:
            async with self._create_session(trust_all) as session:
                csr = await self._generate_csr(
                    username, password, session, domain, private_key
                )
                if csr:
                    await self._process_csr(
                        username,
                        password,
                        session,
                        domain,
                        csr,
                        private_key,
                        use_v2,
                        output_path,
                        passphrase=passphrase,
                    )
        except Exception as e:
            self.logger.error(f"Error in enrollment process: {e}")

    def _generate_key(self, key_size: int = 4096) -> Optional[rsa.RSAPrivateKey]:
        """
        Generate a private RSA key.

        Args:
            key_size: Size of the RSA key (default: 4096)

        Returns:
            RSA private key or None if generation fails
        """
        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=key_size
            )
            return private_key
        except Exception as e:
            self.logger.error(f"Failed to generate private key: {e}")
            return None

    def _create_session(self, trust_all: bool) -> aiohttp.ClientSession:
        """
        Create an aiohttp session with appropriate SSL configuration.

        Args:
            trust_all: If True, disable SSL verification

        Returns:
            Configured aiohttp ClientSession
        """
        # Configure timeout
        timeout = ClientTimeout(total=30)

        # Configure SSL context
        ssl_context = None
        trust_all = True
        if trust_all:
            ssl_context = False
            self.logger.warning("SSL verification disabled - NOT for production use!")
        elif self.trust_store_path and os.path.exists(self.trust_store_path):
            # For aiohttp, we would need to create a custom SSL context
            # For now, we'll use the default verification
            ssl_context = None

        # Create connector with retry configuration
        # Don't pass loop parameter to avoid event loop issues
        connector = aiohttp.TCPConnector(limit=10, ssl=ssl_context)

        return aiohttp.ClientSession(connector=connector, timeout=timeout)

    async def _generate_csr(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        domain: str,
        private_key,
    ) -> Optional[str]:
        """
        Generate a Certificate Signing Request.

        Args:
            username: Username for authentication
            password: Password for authentication
            session: aiohttp ClientSession to use
            domain: Domain for the request
            private_key: Private key for the CSR

        Returns:
            CSR string or None if generation fails
        """
        try:
            url = f"https://{domain}:8446/Marti/api/tls/config"
            auth = BasicAuth(username, password)

            async with session.get(url, auth=auth) as response:
                response.raise_for_status()
                response_text = await response.text()

            self.logger.info(f"Received config response: {response_text}")

            # Parse XML response
            csr_config = self._parse_config_xml(response_text)
            if not csr_config:
                self.logger.error("Failed to parse config XML")
                return None

            # Add username as CN
            csr_config["CN"] = username

            # Generate CSR
            csr = self._create_csr_from_config(csr_config, private_key)
            self.logger.info("CSR generated successfully")
            return csr

        except Exception as e:
            self.logger.error(f"Error generating CSR: {e}")
            return None

    def _parse_config_xml(self, xml_content: str) -> Dict[str, str]:
        """
        Parse the XML configuration response.

        Args:
            xml_content: XML content string

        Returns:
            Dictionary of configuration parameters
        """
        try:
            root = ET.fromstring(xml_content)
            config = {}

            # Handle different XML structures - try both formats
            # First try the namespaced format (newer TAK servers)
            # The namespace might be different, so we'll search by tag name regardless of namespace
            for elem in root.iter():
                if elem.tag.endswith("nameEntry") or elem.tag == "nameEntry":
                    name = elem.get("name", "")
                    value = elem.get("value", "")
                    if name and value:
                        config[name] = value

            # If no entries found, try the older format with simple "entry" elements
            if not config:
                for elem in root.iter():
                    if elem.tag.endswith("entry") or elem.tag == "entry":
                        name = elem.get("name", "")
                        value = elem.get("value", "")
                        if name and value:
                            config[name] = value

            self.logger.debug(f"Parsed config: {config}")
            return config
        except Exception as e:
            self.logger.error(f"Error parsing XML config: {e}")
            return {}

    def _create_csr_from_config(self, config: Dict[str, str], private_key) -> str:
        """
        Create a CSR from configuration parameters.

        Args:
            config: Configuration dictionary
            private_key: Private key for the CSR

        Returns:
            PEM-encoded CSR string
        """
        # Build subject name from config
        subject_components = []

        if "CN" in config:
            subject_components.append(
                x509.NameAttribute(x509.NameOID.COMMON_NAME, config["CN"])
            )
        if "O" in config:
            subject_components.append(
                x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, config["O"])
            )
        if "OU" in config:
            subject_components.append(
                x509.NameAttribute(x509.NameOID.ORGANIZATIONAL_UNIT_NAME, config["OU"])
            )
        if "C" in config:
            subject_components.append(
                x509.NameAttribute(x509.NameOID.COUNTRY_NAME, config["C"])
            )
        if "ST" in config:
            subject_components.append(
                x509.NameAttribute(x509.NameOID.STATE_OR_PROVINCE_NAME, config["ST"])
            )
        if "L" in config:
            subject_components.append(
                x509.NameAttribute(x509.NameOID.LOCALITY_NAME, config["L"])
            )

        subject = x509.Name(subject_components)

        # Create CSR
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(subject)
            .sign(private_key, hashes.SHA256())
        )

        # Return PEM-encoded CSR
        return csr.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    async def _process_csr(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        domain: str,
        csr: str,
        private_key,
        use_v2: bool = True,
        output_path: Optional[str] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        """
        Process the CSR by sending it for signing and handling the response.

        Args:
            username: Username for authentication
            password: Password for authentication
            session: aiohttp ClientSession to use
            domain: Domain for the request
            csr: Certificate Signing Request
            private_key: Private key corresponding to the CSR
            use_v2: If True, use the v2 endpoint that returns JSON
            output_path: Custom path for the output certificate file
        """
        try:
            # Choose endpoint based on version
            if use_v2:
                url = (
                    f"https://{domain}:8446/Marti/api/tls/signClient/v2?clientUid=test"
                )
                content_type = "application/pkcs10"
            else:
                url = f"https://{domain}:8446/Marti/api/tls/signClient?clientUid=test"
                content_type = "application/pkcs10"

            auth = BasicAuth(username, password)

            async with session.post(
                url,
                auth=auth,
                data=csr.encode("utf-8"),
                headers={"Content-Type": content_type},
            ) as response:
                self.logger.info(f"Response code: {response.status}")

                if response.status == 200:
                    if use_v2:
                        # v2 endpoint returns JSON (but might have incorrect content-type)
                        try:
                            response_data = await response.json()
                        except Exception as json_error:
                            # If JSON parsing fails due to content-type, try parsing text as JSON
                            self.logger.warning(
                                f"JSON parsing failed ({json_error}), trying to parse text as JSON"
                            )
                            response_text = await response.text()
                            response_data = json.loads(response_text)

                        await self._process_json_certificate_response(
                            response_data, private_key, output_path, passphrase
                        )
                    else:
                        # Original endpoint returns PKCS12
                        response_content = await response.read()
                        await self._process_pkcs12_certificate_response(
                            response_content, private_key, output_path, passphrase
                        )
                else:
                    self.logger.error(
                        f"Certificate signing failed with status: {response.status}"
                    )
                    # If v2 fails, try fallback to v1
                    if use_v2:
                        self.logger.info("Trying fallback to v1 endpoint...")
                        await self._process_csr(
                            username,
                            password,
                            session,
                            domain,
                            csr,
                            private_key,
                            use_v2=False,
                            output_path=output_path,
                            passphrase=passphrase,
                        )

        except Exception as e:
            self.logger.error(f"Error processing CSR: {e}")
            # If v2 fails with exception, try fallback to v1
            if use_v2:
                self.logger.info(
                    "v2 endpoint failed, trying fallback to v1 endpoint..."
                )
                try:
                    await self._process_csr(
                        username,
                        password,
                        session,
                        domain,
                        csr,
                        private_key,
                        use_v2=False,
                        output_path=output_path,
                        passphrase=passphrase,
                    )
                except Exception as fallback_error:
                    self.logger.error(
                        f"Both v2 and v1 endpoints failed: {fallback_error}"
                    )

    async def _process_json_certificate_response(
        self,
        response_data: dict,
        private_key,
        output_path: Optional[str] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        """
        Process the JSON certificate response from v2 endpoint.

        Args:
            response_data: JSON response containing certificate data
            private_key: Private key for the certificate
            output_path: Custom path for the output certificate file
        """
        try:
            self.logger.info("Processing JSON certificate response from v2 endpoint")
            self.logger.debug(f"Response data keys: {list(response_data.keys())}")

            # Extract the signed certificate
            signed_cert_pem = response_data.get("signedCert")
            if not signed_cert_pem:
                self.logger.error("No 'signedCert' found in JSON response")
                return

            # Extract CA certificates - they might be named ca0, ca1, ca2, etc.
            ca_pems = []
            ca_index = 0
            while f"ca{ca_index}" in response_data:
                ca_pem = response_data[f"ca{ca_index}"]
                if ca_pem:
                    ca_pems.append(ca_pem)
                ca_index += 1

            self.logger.info(
                f"Found signed certificate and {len(ca_pems)} CA certificates"
            )

            # Debug: Log certificate formats to help diagnose PEM issues
            self.logger.debug(f"Signed cert starts with: {signed_cert_pem[:50]}...")
            if ca_pems:
                self.logger.debug(f"CA cert 0 starts with: {ca_pems[0][:50]}...")

            # Debug: Log raw certificate lengths and check for obvious issues
            self.logger.info(f"Raw signed cert length: {len(signed_cert_pem)}")
            self.logger.info(
                f"Raw CA cert lengths: {[len(ca_pem) for ca_pem in ca_pems]}"
            )

            # Check if certificates have proper PEM structure or are headerless (v2 format)
            if not signed_cert_pem.startswith("-----BEGIN"):
                self.logger.info(
                    "Signed certificate appears to be headerless (v2 format) - will add headers"
                )
            else:
                self.logger.info("Signed certificate has PEM headers")

            for i, ca_pem in enumerate(ca_pems):
                if not ca_pem.startswith("-----BEGIN"):
                    self.logger.info(
                        f"CA certificate {i} appears to be headerless (v2 format) - will add headers"
                    )
                else:
                    self.logger.info(f"CA certificate {i} has PEM headers")

            # Fix PEM formatting if needed
            self.logger.info("Applying PEM formatting fixes...")
            try:
                signed_cert_pem = self._fix_pem_formatting(signed_cert_pem)
                ca_pems = [self._fix_pem_formatting(ca_pem) for ca_pem in ca_pems]

                # Debug: Log post-fix certificate info
                self.logger.info(f"Fixed signed cert length: {len(signed_cert_pem)}")
                self.logger.debug(
                    f"Fixed signed cert preview:\n{signed_cert_pem[:200]}..."
                )

                # Validate that certificates can be parsed before trying to create PKCS12
                self.logger.info("Pre-validating certificate parsing...")
                from cryptography import x509

                test_cert = x509.load_pem_x509_certificate(
                    signed_cert_pem.encode("utf-8")
                )
                self.logger.info(f"✅ Signed certificate validation passed")

                for i, ca_pem in enumerate(ca_pems):
                    test_ca = x509.load_pem_x509_certificate(ca_pem.encode("utf-8"))
                    self.logger.info(f"✅ CA certificate {i} validation passed")

            except Exception as validation_error:
                self.logger.error(
                    f"❌ Certificate validation failed: {validation_error}"
                )
                self.logger.error(
                    "This appears to be a server-side certificate format issue."
                )
                self.logger.info(
                    "Will attempt to save raw certificate data for manual inspection..."
                )

                # Save raw certificate data for debugging
                debug_dir = Path.home() / "Downloads" / "cert_debug"
                debug_dir.mkdir(exist_ok=True)

                with open(debug_dir / "raw_signed_cert.pem", "w") as f:
                    f.write(signed_cert_pem)
                with open(debug_dir / "raw_ca_certs.txt", "w") as f:
                    for i, ca_pem in enumerate(ca_pems):
                        f.write(f"=== CA Certificate {i} ===\n")
                        f.write(ca_pem)
                        f.write("\n\n")

                self.logger.info(f"Raw certificate data saved to: {debug_dir}")
                return

            # Create client certificate file
            self._create_client_certificate(
                signed_cert_pem, ca_pems, private_key, output_path, passphrase
            )

        except Exception as e:
            self.logger.error(f"Error processing JSON certificate response: {e}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")

    async def _process_pkcs12_certificate_response(
        self, response_content: bytes, private_key, output_path: Optional[str] = None
    ) -> None:
        """
        Process the certificate response and create client keystore.

        Args:
            response_content: Raw response content (PKCS12 data)
            private_key: Private key for the certificate
            output_path: Custom path for the output certificate file
        """
        try:
            self.logger.info(
                f"Processing certificate response, size: {len(response_content)} bytes"
            )

            # First, let's try to load it as PKCS12 using the original method
            try:
                pkcs12_data = pkcs12.load_key_and_certificates(
                    response_content, b"atakatak"  # Default password from original code
                )
                private_key_from_p12, certificate, additional_certificates = pkcs12_data

                self.logger.info(
                    f"PKCS12 data loaded - Certificate: {certificate is not None}, "
                    f"Additional certs: {len(additional_certificates) if additional_certificates else 0}"
                )

                # Handle the case where the main certificate might be None
                # but we have certificates in additional_certificates
                if certificate is None and additional_certificates:
                    self.logger.info(
                        "Main certificate is None, checking additional certificates"
                    )
                    # Look for the signed certificate - it might be the first one or have a specific pattern
                    certificate = additional_certificates[0]
                    additional_certificates = (
                        additional_certificates[1:]
                        if len(additional_certificates) > 1
                        else []
                    )
                    self.logger.info(
                        "Using first additional certificate as main certificate"
                    )

                if certificate is None:
                    self.logger.error("No certificate found in PKCS12 response")
                    return

                # Convert certificate to PEM
                cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode(
                    "utf-8"
                )

                # Convert CA certificates to PEM
                ca_pems = []
                if additional_certificates:
                    for ca_cert in additional_certificates:
                        ca_pem = ca_cert.public_bytes(
                            serialization.Encoding.PEM
                        ).decode("utf-8")
                        ca_pems.append(ca_pem)

                self.logger.info("Certificate processing completed successfully")
                self.logger.info(f"Found {len(ca_pems)} CA certificates")

                # Create client certificate file
                self._create_client_certificate(
                    cert_pem, ca_pems, private_key, output_path
                )

            except Exception as pkcs12_error:
                self.logger.error(f"Failed to load as PKCS12: {pkcs12_error}")
                # Try to save the raw response for debugging
                debug_file = Path.home() / "Downloads" / "server_response.p12"
                with open(debug_file, "wb") as f:
                    f.write(response_content)
                self.logger.info(
                    f"Saved raw server response to {debug_file} for debugging"
                )
                raise

        except Exception as e:
            self.logger.error(f"Error processing certificate response: {e}")
            # Log additional debugging information
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")

    def _create_client_certificate(
        self,
        cert_pem: str,
        ca_pems: List[str],
        private_key,
        output_path: Optional[str] = None,
        passphrase: Optional[bytes] = None,
    ) -> None:
        """
        Create a client certificate file (PKCS12 format).

        Args:
            cert_pem: Client certificate in PEM format
            ca_pems: CA certificates in PEM format
            private_key: Private key for the certificate
            output_path: Custom path for the output certificate file. If None,
                        defaults to ~/Downloads/clientCert.p12
            passphrase: Optional password for PKCS12 encryption (bytes).
        """
        try:
            self.logger.info("Creating client certificate from PEM data...")

            # Parse the certificate
            self.logger.debug("Parsing signed certificate...")
            try:
                certificate = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
                self.logger.info("✅ Signed certificate parsed successfully")
            except Exception as cert_error:
                self.logger.error(
                    f"❌ Failed to parse signed certificate: {cert_error}"
                )
                self.logger.error(
                    f"Signed cert content (first 300 chars):\n{cert_pem[:300]}"
                )
                raise

            # Parse CA certificates
            ca_certificates = []
            for i, ca_pem in enumerate(ca_pems):
                self.logger.debug(f"Parsing CA certificate {i}...")
                try:
                    ca_cert = x509.load_pem_x509_certificate(ca_pem.encode("utf-8"))
                    ca_certificates.append(ca_cert)
                    self.logger.info(f"✅ CA certificate {i} parsed successfully")
                except Exception as ca_error:
                    self.logger.error(
                        f"❌ Failed to parse CA certificate {i}: {ca_error}"
                    )
                    self.logger.error(
                        f"CA cert {i} content (first 300 chars):\n{ca_pem[:300]}"
                    )
                    raise

            # Create PKCS12 data
            pkcs12_data = pkcs12.serialize_key_and_certificates(
                name=b"TAK Client Cert",
                key=private_key,
                cert=certificate,
                cas=ca_certificates if ca_certificates else None,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    passphrase.encode("utf-8")
                ),
            )

            # Save to file
            if output_path:
                cert_file = Path(output_path)
                # Create parent directories if they don't exist
                cert_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                downloads_dir = Path.home() / "Downloads"
                downloads_dir.mkdir(
                    parents=True, exist_ok=True
                )  # Ensure Downloads directory exists
                cert_file = downloads_dir / "clientCert.p12"

            with open(cert_file, "wb") as f:
                f.write(pkcs12_data)

            self.logger.info(f"Client certificate saved to: {cert_file}")

        except Exception as e:
            self.logger.error(f"Error creating client certificate: {e}")

    def _fix_pem_formatting(self, pem_content: str) -> str:
        """
        Fix PEM certificate formatting issues.

        Some servers may return PEM certificates with incorrect line breaks
        or formatting that causes parsing issues. The v2 endpoint specifically
        returns PEM strings WITHOUT headers/footers and may not end with newlines.

        Args:
            pem_content: Raw PEM content that may have formatting issues

        Returns:
            Properly formatted PEM content with headers/footers
        """
        if not pem_content:
            return pem_content

        # First, handle JSON-escaped newlines (common in JSON responses)
        content = pem_content.replace("\\n", "\n").replace("\\r", "\r")

        # Normalize line breaks
        content = content.replace("\r\n", "\n").replace("\r", "\n").strip()

        # Check if this content lacks PEM headers/footers (v2 endpoint behavior)
        if not content.startswith("-----BEGIN") and not content.endswith("-----"):
            # This is likely a headerless PEM from v2 endpoint
            self.logger.debug(
                "Detected headerless PEM data from v2 endpoint, adding headers/footers"
            )

            # Remove any existing line breaks and whitespace
            cert_data = content.replace("\n", "").replace(" ", "").replace("\t", "")

            # Format as proper PEM with headers/footers
            formatted_lines = ["-----BEGIN CERTIFICATE-----"]

            # Add certificate data in 64-character lines (standard PEM format)
            for i in range(0, len(cert_data), 64):
                formatted_lines.append(cert_data[i : i + 64])

            formatted_lines.append("-----END CERTIFICATE-----")

            result = "\n".join(formatted_lines) + "\n"
            self.logger.debug(
                f"Added PEM headers/footers: {len(content)} -> {len(result)} chars"
            )
            return result

        # Check if this is a single-line certificate with headers (less common)
        if (
            "-----BEGIN" in content
            and "-----END" in content
            and "\n" not in content.strip()
        ):
            # Split on the boundaries to extract parts
            begin_match = content.find("-----BEGIN")
            end_match = content.find("-----END")

            if begin_match != -1 and end_match != -1:
                # Extract header
                header_end = content.find("-----", begin_match + 5) + 5
                header = content[begin_match:header_end]

                # Extract footer
                footer_start = content.find("-----END")
                footer_end = content.find("-----", footer_start + 5) + 5
                footer = content[footer_start:footer_end]

                # Extract certificate data (between header and footer)
                cert_data = content[header_end:footer_start].strip()

                # Format properly
                formatted_lines = [header]

                # Add certificate data in 64-character lines
                for i in range(0, len(cert_data), 64):
                    formatted_lines.append(cert_data[i : i + 64])

                formatted_lines.append(footer)

                result = "\n".join(formatted_lines) + "\n"
                self.logger.debug(
                    f"Fixed single-line PEM: {len(content)} -> {len(result)} chars"
                )
                return result

        # Handle multi-line case with headers (original logic)
        lines = content.split("\n")

        # Remove empty lines and strip whitespace
        lines = [line.strip() for line in lines if line.strip()]

        # Find the header and footer
        header_line = None
        footer_line = None
        cert_data_lines = []

        for i, line in enumerate(lines):
            if line.startswith("-----BEGIN"):
                header_line = line
            elif line.startswith("-----END"):
                footer_line = line
            elif header_line and not footer_line:
                # This is certificate data
                cert_data_lines.append(line)

        if not header_line or not footer_line:
            self.logger.warning("PEM header or footer not found, returning as-is")
            return pem_content

        # Reconstruct properly formatted PEM
        formatted_lines = [header_line]

        # Add certificate data in 64-character lines (standard PEM format)
        cert_data = "".join(cert_data_lines)
        for i in range(0, len(cert_data), 64):
            formatted_lines.append(cert_data[i : i + 64])

        formatted_lines.append(footer_line)

        result = "\n".join(formatted_lines) + "\n"

        self.logger.debug(
            f"Fixed multi-line PEM formatting: {len(pem_content)} -> {len(result)} chars"
        )
        return result


async def main():
    """Example usage of the CertificateEnrollment class."""
    # Example usage
    enrollment = CertificateEnrollment()

    # For testing with self-signed certificates (NOT for production)
    domain = "example.com"
    username = "testuser"
    password = "testpass"

    # Use v2 endpoint by default (returns JSON)
    # Example with custom output path
    await enrollment.begin_enrollment(
        domain,
        username,
        password,
        trust_all=True,
        use_v2=True,
        output_path="./my_client_cert.p12",
    )


if __name__ == "__main__":
    asyncio.run(main())
