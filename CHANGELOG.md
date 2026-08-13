## PyTAK 7.4.3

- PyTAK-backed gateways now survive transient TAK transport failures in the
  same process. DNS failures, refused connections, timeouts, TLS failures, and
  server-side WebSocket closes retry with exponential backoff from 5 seconds
  to a two-minute ceiling. Twenty percent jitter prevents a recovering server
  from receiving a synchronized fleet reconnect. A connection stable for five
  minutes resets the delay, while invalid local configuration still fails
  immediately.
- Fixed a PKCS#12 conversion leak which left three temporary PEM files behind
  on every connection attempt. Long server outages could fill a RAM-backed
  `/tmp`, prevent unrelated services from creating temporary files, and turn a
  recoverable network outage into a host-wide resource incident.
- Enrollment credentials are redacted from reconnect diagnostics. Worker
  queues and sockets are rebuilt between attempts, bounding memory use during
  an arbitrarily long outage.

## PyTAK 7.4.1

- Fixed gateway processes remaining `active (running)` after a transport worker
  failed. Worker close hooks now run before PyTAK waits for cancelled sibling
  tasks, and both cleanup and cancellation waits are bounded and identify any
  worker that stalls. The original transport exception reaches systemd so its
  restart policy can reconnect the gateway.

## PyTAK 7.4.0

- Added `pytak.StatusWriter`, a small runtime-status surface for gateways.
  A gateway that is working and a gateway that is wedged look identical from
  the outside -- both are `active (running)` to systemd and both hold their
  socket open -- and nothing in PyTAK recorded whether contacts were still
  arriving. Operators were left reading journal text.
- `StatusWriter` maintains `/run/<app>/status.json` with lifetime counters, a
  per-minute trend suitable for a sparkline, and a ring buffer of recent
  contacts. Management UIs (the AryaOS Cockpit plugins) read it with a file
  watch, so they update on write with no polling.
- Writes are atomic (tempfile + `os.replace`), so a reader never observes a
  partially written document.
- Bounded by design: `recent` is a ring buffer and the trend is a fixed number
  of buckets, so a gateway running for months has a file size ceiling.
- A status-write failure never raises into the gateway -- moving CoT is the
  job, reporting on it is not -- but it is not silent either: failures are
  counted into `write_errors`, surfaced in the document so a UI can report
  stale data rather than render it as fact, and logged once rather than per
  message.
- The document carries `wall_t` so a reader can distinguish a gateway that is
  quiet from one that has stopped writing; `recent` alone looks identical for
  both.
- `status_path()` falls back to `XDG_RUNTIME_DIR` or the temp directory when
  `/run` is not writable, so a gateway started from a developer shell still
  produces a status file.
- Fixed the WS TX warning tests, which had been failing on Python 3.7, 3.8 and
  3.9 since 7.3.14. PyTAK's logger sets `propagate = False`, so records never
  reached the root logger where pytest's `caplog` handler lives. The behaviour
  under test was correct throughout; only the test was wrong.

## PyTAK 7.3.13

- Fixed a stale-certificate reuse bug in the `tak://` onboarding flow that
  could cause SSL handshake failures (`TLSV1_ALERT_INTERNAL_ERROR`) when
  connecting to a rebuilt TAK server whose CA had changed.
- Strengthened cert cache keying in `_cert_cache_paths`: the cache key now
  incorporates `hostname`, `port`, **and** `username` (previously only
  `hostname:username`), and the SHA-256 hash prefix is extended from 16 to 32
  hex characters to reduce accidental collisions.
- Added `_legacy_cert_cache_paths` helper that computes the old (pre-7.3.13)
  key for backward-compatible migration: on upgrade, if the new-format cache
  entry is absent but a legacy entry exists, the legacy cert is reused for the
  current connection without forcing unnecessary re-enrollment.
- Fresh certificates obtained via enrollment are always stored under the new
  32-char key so the legacy path is naturally superseded over time.
- Added a server TLS certificate fingerprint sidecar for cached enrollment
  certs; if a TAK server is rebuilt at the same host/port and presents a new
  server certificate, PyTAK now treats the cached client cert as stale and
  re-enrolls automatically.
- Improved decision-point logging in `resolve_tak_url`: cache path chosen,
  cache hit/miss, and legacy fallback are all now logged at INFO/DEBUG level.

## PyTAK 7.3.12

- Added reusable CoT construction helpers for PyTAK child clients:
  `cot_point()`, `cot_detail()`, `cot_event()`, `add_remarks()`,
  `remarks_text()`, `serialize_cot()`, and `sanitize_url_credentials()`.
- Kept `gen_cot_xml()` and `gen_cot()` backward-compatible while routing them
  through the shared CoT event builder.
- Standardized TAK-safe latitude/longitude truncation in the shared point helper
  for AryaOS-driven client compatibility.

## PyTAK 7.3.0 (Draft)

Release draft for the next PyTAK version after `7.2.1`.

- Added certificate enrollment workflow support in TLS client setup via `CertificateEnrollment`.
- Added support for `PYTAK_TLS_CERT_ENROLLMENT_USERNAME`, `PYTAK_TLS_CERT_ENROLLMENT_PASSWORD`, and `PYTAK_TLS_CERT_ENROLLMENT_PASSPHRASE`.
- Improved TLS behavior and diagnostics, including optional expected server hostname handling (`PYTAK_TLS_SERVER_EXPECTED_HOSTNAME`).
- Improved queue and worker behavior with better handling of full queues and `None` payload edge cases (`TXWorker.send_data()`).
- Added `PYTAK_NO_HELLO` to disable initial Hello events for deployments that require quiet startup.
- Added multicast TTL configuration support for UDP/multicast workflows.
- Added/expanded helper APIs including `SimpleCOTEvent`, `COTEvent`, and `cot2xml`.
- Improved Python 3.12 compatibility and removed Python 3.6 support in CI and packaging metadata.
- Improved packaging/release pipeline and version management (`VERSION` file based versioning).
- Expanded examples, tests, and project documentation.


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
# 7.5.0

* Add a common, additive runtime health contract to `StatusWriter`: `health`,
  `input`, and `output` blocks describe process state, receiver activity, and
  egress connection health without removing gateway-specific counters.
