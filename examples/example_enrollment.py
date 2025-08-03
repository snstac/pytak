#!/usr/bin/env python3
"""
Example usage of the Certificate Enrollment module.

This script demonstrates how to use the CertificateEnrollment class
to enroll certificates with a TAK server using async/await.
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

from certificate_enrollment import CertificateEnrollment


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("enrollment.log"),
        ],
    )


async def main():
    """Main function to handle command line arguments and run enrollment."""
    parser = argparse.ArgumentParser(description="Certificate Enrollment Tool")
    parser.add_argument("domain", help="Domain for certificate enrollment")
    parser.add_argument("username", help="Username for authentication")
    parser.add_argument("password", help="Password for authentication")
    parser.add_argument(
        "--trust-all",
        action="store_true",
        help="Skip certificate verification (NOT for production)",
    )
    parser.add_argument(
        "--trust-store", type=str, help="Path to trust store certificate file"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--use-v1",
        action="store_true",
        help="Use v1 endpoint (PKCS12 response) instead of v2 (JSON response)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output path for the client certificate file (default: ~/Downloads/clientCert.p12)",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Initialize certificate enrollment
        enrollment = CertificateEnrollment(trust_store_path=args.trust_store)

        logger.info(f"Starting certificate enrollment for user: {args.username}")
        logger.info(f"Domain: {args.domain}")

        if args.trust_all:
            logger.warning("SSL verification disabled - NOT for production use!")

        # Determine which endpoint version to use
        use_v2 = not args.use_v1  # Default to v2 unless --use-v1 is specified

        if use_v2:
            logger.info("Using v2 endpoint (JSON response)")
        else:
            logger.info("Using v1 endpoint (PKCS12 response)")

        # Begin enrollment process (now async)
        await enrollment.begin_enrollment(
            domain=args.domain,
            username=args.username,
            password=args.password,
            trust_all=args.trust_all,
            use_v2=use_v2,
            output_path=args.output,
        )

        logger.info("Enrollment process completed.")

        # Check if certificate was created
        if args.output:
            cert_file = Path(args.output)
        else:
            downloads_dir = Path.home() / "Downloads"
            cert_file = downloads_dir / "clientCert.p12"

        if cert_file.exists():
            logger.info(f"Certificate enrollment completed successfully!")
            logger.info(f"Client certificate saved to: {cert_file}")
        else:
            logger.warning("Certificate file not found. Check logs for errors.")

    except KeyboardInterrupt:
        logger.info("Enrollment process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during enrollment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
