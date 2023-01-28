PyTAK 5.6.1
-----------
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
high CPU. See https://github.com/ampledata/pytak/pull/22 thanks @PeterQFR.


PyTAK 5.2.0
-----
New Features:
- Added support for both AsyncIO & Multiprocessing Queues in PyTAK Workers classes.
- Added support for specifying TX & RX queue when instantiating PyTAK CLITool.

Bug & Performance Fixes:
- Added async sleeps to each TX & RX loops iteration to fix broken async regiment in PYTAK.
