## PyTAK 7.1.0

Happy Lunar New Year 2025 - Year of the Snake.

- Fixes 


## PyTAK 7.0.1

Happy Summer Solstice

- Fixes #72: Add a config variable for users to set expected CN when using CA verification. Thanks @ahoenerBE
- Added configuration parameter: PYTAK_TLS_SERVER_EXPECTED_HOSTNAME
- Rewrote GitHub actions, moved most logic to shell script and Makefile.
- Renamed Debian package from python3-pytak to pytak.
- Standardized Makefile for all PyTAK based programs.
- Cleaned, simplified and expanded documentation.
- Created Makefile jobs for Debian packaging and PyTAK customization.
- Moved all media to media sub directory under docs/.
- Converted README.rst to README.md.
- Style & Linting of code.
- Refactored TLS client creation, abstracted many functions.
- Added TLS client cert and key checks and improved error messages.

## PyTAK 6.4.0

- Fixes #69: PyTAK's TAK_PROTO=1 doesn't always work with iTAK.

## PyTAK 6.3.1

- Fixes #67: Add constrained logging for systemd invocation.

## PyTAK 6.3.0

- Fixes #58: TypeError: can't multiply sequence by non-int of type 'float'.
- Fixes #64 (?): Cryptography functions deprecated
- Fixes #65: Performance issues with large queues, sleep only on empty queue.
- Fixes #66: Add config params MAX_OUT_QUEUE & MAX_IN_QUEUE to allow queue tuning.

## PyTAK 6.2.4

- Fixes #63: Python 3.6: AttributeError: module 'asyncio' has no attribute 'exceptions'.

## PyTAK 6.2.1

- Add 'PEM pass phrase' prompt instructions. Fixes #54.

## PyTAK 6.2.0

- Fixes #12: Encrypted TLS Private Keys (Private Keys with Passphrases).
- Fixes #33: PyTAK Multicast read/write & write-only do not work on Windows.
- Fixes #40: Fix multicast binding on Windows.
- Fixes #48: Apply multicast membership to specified interface.
- Fixes #50: Add support for flow-tags.
- Fixes #51: CoT Time/Start/Stale timestamps aren't actually ISO-8601.
- Fixes #52: Add additional default CoT attributes.
- Fixes #53: Add generic CoT generation function.
- Various documentation fixes.

## PyTAK 6.1.0

- Fixes #43: Add broadcast UDP support.
- Fixes #46: Move documentation from Sphinx to Markdown.
- Fixed #47: Change default constants to match config type hints (e.g. str instead of int).
- Updated Type Hints for function & method parameters.
- Updated Coverage for Python version work-arounds.
- Refactored `udp_client()` function, API unchanged.
- Fixed vague Exceptions.
- Renamed `cs2url()` to `connectString2url()`.

## PyTAK 6.0.0

- Moved & expanded documentation at https://pytak.readthedocs.io/
- ``COT_URL`` now defaults to ``udp+wo://239.2.3.1:6969``, aka 'Mesh SA' in ATAK & WinTAK. This disables receiveing CoT by default. To enable receiving CoT, remove the ``+wo`` modifier. 
* Fixes #31: 'protobuf support', "TAK Protocol, Version 1" is now the default output from PyTAK, *BUT* you must install the ``takproto`` python module seperately to ENABLE, otherwise reverts to CoT XML. PyTAK will automatically detect if the ``COT_URL`` is multicast or unicast, and use the appropriate protobuf format. See: https://github.com/snstac/takproto
* Fixes #36: 'Network is unreachable', added ``PYTAK_MULTICAST_LOCAL_ADDR`` to allow setting bind port on network connections.
* Fixes #37: 'unknown compression', reverted to github builder ubuntu-20.04
- Added support for reading PKCS#12 (.p12) files containing public-private key pairs. Set p12 file with ``PYTAK_TLS_CLIENT_CERT``, and keystore password with ``PYTAK_TLS_CLIENT_PASSWORD``.
- Updates for AirTAK v1 support: https://www.snstac.com/blog/introducing-airtak-v1
- Moved setup.py metadata to setup.cfg
- Style, lint and layout cleanup of code.
- Added CI testing for Python 3.11
- Added Read The Docs builder.
- Added PyTAK shield logo & screenshots.

## PyTAK 5.6.1

Exported `read_pref_package()` from client_functions.

PyTAK 5.6.0
-----------
New Features:
- Made cryptography an install extras: You'll need this to use data packages! To install: `python3 -m pip install pytak[with_crypto]`
- Added write-only socket option to UDP sockets. Add `+wo` to the URL schema, as in: `udp+wo://239.2.3.1:6969`.

Bug Fixes:
- Fixed bad parsing of env var '%' characters on config import.

PyTAK 5.5.0
-----------
New Features:
- Added multicast receive support.
- Added pref package / data package .zip support.

Other:
- Code cleanup.
- Documentation & README updates.
- 2023 copyright updates.
- Ramped up code coverage to at least 50% on most files.
- Added example of takproto support.

PyTAK 5.4.1
-----------
Fixes #24, const as bytes not str.

PyTAK 5.4.0
-----------
Added CoT XML Declaration constant, should be included with all output XML CoT.

PyTAK 5.3.1
-----
Readme cleanup.

Changed behavior of while loops to sleep 0.1 instead of 0, which was causing
high CPU. See https://github.com/snstac/pytak/pull/22 thanks @PeterQFR.


PyTAK 5.2.0
-----
New Features:
- Added support for both AsyncIO & Multiprocessing Queues in PyTAK Workers classes.
- Added support for specifying TX & RX queue when instantiating PyTAK CLITool.

Bug & Performance Fixes:
- Added async sleeps to each TX & RX loops iteration to fix broken async regiment in PYTAK.
