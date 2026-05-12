#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""pytak command-line client.

Unix pipe interface to the TAK network:

    # Receive CoT from a TAK Server, print to stdout
    pytak tcp://takserver.example.com:8087

    # Send CoT from stdin to a TAK Server
    echo '<event .../>' | pytak tcp://takserver.example.com:8087

    # Send CoT from a file to a TAK Server (with TLS)
    pytak --tx-file events.xml tls://takserver.example.com:8089 --tls-cert client.pem

    # Send only — suppress received CoT output
    pytak --tx-only --tx-file events.xml tcp://takserver.example.com:8087

    # Receive only — ignore stdin
    pytak --rx-only tcp://takserver.example.com:8087

    # Enroll via tak:// URL, then connect over WebSocket
    pytak "tak://com.atakmap.app/enroll?host=takserver.example.com&"
    "username=user&token=xxx"

    # Pipe CoT through two TAK Servers
    pytak --rx-only tcp://server1:8087 | pytak --tx-only tcp://server2:8087
"""

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

import pytak

try:
    from pytak.constants import DEFAULT_WS_PATH
except ImportError:
    DEFAULT_WS_PATH = "/takproto/1"

_LOG = logging.getLogger(__name__)

# CoT XML event boundary used for stdin framing
_COT_END = b"</event>"


def _pretty_xml(data: bytes) -> bytes:
    """Return *data* pretty-printed as indented XML, or the original bytes on failure."""
    try:
        root = ET.fromstring(data.decode("utf-8", errors="replace"))
        # xml.etree.ElementTree.indent() is available in Python >=3.9.
        # Keep a local fallback for Python 3.7/3.8 test compatibility.
        if hasattr(ET, "indent"):
            ET.indent(root, space="  ")
        else:
            _indent_xml(root, space="  ")
        return ET.tostring(root, encoding="unicode").encode("utf-8")
    except ET.ParseError:
        return data


def _indent_xml(elem: ET.Element, level: int = 0, space: str = "  ") -> None:
    """In-place indentation fallback for Python versions without ET.indent."""
    indent = "\n" + (level * space)
    child_indent = "\n" + ((level + 1) * space)
    children = list(elem)
    if children:
        if not elem.text or not elem.text.strip():
            elem.text = child_indent
        for child in children:
            _indent_xml(child, level + 1, space)
            if not child.tail or not child.tail.strip():
                child.tail = child_indent
        if not children[-1].tail or not children[-1].tail.strip():
            children[-1].tail = indent


def _frame_cot_xml_events(buf: bytes):
    """Yield complete CoT XML events from *buf* and return remainder bytes."""
    events = []
    while _COT_END in buf:
        idx = buf.index(_COT_END) + len(_COT_END)
        event = buf[:idx].strip()
        buf = buf[idx:]
        if event:
            events.append(event)
    return events, buf


class StdinWorker(pytak.QueueWorker):
    """Read CoT XML events from stdin and put each one on the TX queue.

    Frames on ``</event>`` boundaries so multiple concatenated events
    (e.g. from ``cat events.xml``) are handled correctly.
    Stops when stdin reaches EOF.
    """

    async def handle_data(self, data: bytes) -> None:
        await self.put_queue(data)

    async def run(self, _=-1) -> None:
        self._logger.info("Running: %s", self.__class__.__name__)
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        buf = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf += chunk
            events, buf = _frame_cot_xml_events(buf)
            for event in events:
                await self.handle_data(event)


class FileWorker(pytak.QueueWorker):
    """Read CoT XML events from a file and put each one on the TX queue."""

    def __init__(self, queue, config, file_path: str):
        super().__init__(queue, config)
        self.file_path = file_path

    async def handle_data(self, data: bytes) -> None:
        await self.put_queue(data)

    async def run(self, _=-1) -> None:
        self._logger.info("Running: %s", self.__class__.__name__)
        with open(self.file_path, "rb") as tx_file:
            buf = b""
            while True:
                chunk = tx_file.read(4096)
                if not chunk:
                    break
                buf += chunk
                events, buf = _frame_cot_xml_events(buf)
                for event in events:
                    await self.handle_data(event)


def _get_tx_source(args, stdin_is_tty: bool) -> str:
    """Return TX source mode: ``none``, ``stdin``, or ``file``."""
    if args.rx_only:
        return "none"

    has_stdin_data = not stdin_is_tty
    has_file_data = bool(args.tx_file)

    if has_stdin_data and has_file_data:
        raise ValueError(
            "Ambiguous TX source: stdin pipe and --tx-file were both provided. "
            "Use one source at a time."
        )

    if has_file_data:
        return "file"

    if has_stdin_data:
        return "stdin"

    return "none"


class StdoutWorker(pytak.QueueWorker):
    """Read CoT events from the RX queue and write each one to stdout.

    Outputs CoT XML, pretty-printed (indented) for readability.
    Each event is followed by a newline so stdout can be piped to other
    tools (``grep``, ``xmllint``, etc.).
    """

    async def handle_data(self, data: bytes) -> None:
        try:
            out = _pretty_xml(data)
            sys.stdout.buffer.write(out)
            if not out.endswith(b"\n"):
                sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
        except BrokenPipeError:
            pass

    async def run(self, _=-1) -> None:
        self._logger.info("Running: %s", self.__class__.__name__)
        while True:
            data = await self.queue.get()
            if data:
                await self.handle_data(data)


async def _resolve_tak_url(raw_url: str, cfg: dict) -> None:
    """Enroll via a tak:// URL and update cfg in place with tls:// settings.

    Prints progress to stderr so stdout stays clean for CoT data.
    """
    print("[pytak] Enrolling via TAK URL ...", file=sys.stderr, flush=True)
    try:
        resolved = await pytak.resolve_tak_url(raw_url)
    except ImportError as exc:
        print(
            "[pytak] ERROR: tak:// enrollment requires "
            "pytak[with-aiohttp,with-crypto].\n"
            f"        python3 -m pip install pytak[with-aiohttp,with-crypto]\n"
            f"        {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[pytak] ERROR: Enrollment failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # resolve_tak_url returns a concrete WSS/TLS target for the enrolled cert.
    # The default tak:// path uses the WebSocket/Marti listener on 8446, while
    # explicit tak://...:8443 URLs keep 8443 available for test environments
    # that expose WebSocket/Marti there.
    cfg.update(resolved)
    cot_url = resolved.get("COT_URL", "")
    print(f"[pytak] Enrolled. Connecting to {cot_url}", file=sys.stderr, flush=True)


def _is_ssl_transport_error(exc: Exception) -> bool:
    """Return True if *exc* looks like a TLS/SSL transport failure."""
    cur = exc
    for _ in range(8):
        text = f"{type(cur).__name__}: {cur}".lower()
        if any(
            token in text
            for token in (
                "ssl",
                "tls",
                "certificate",
                "handshake",
                "clientoserror",
                "wsserverhandshakeerror",
            )
        ):
            return True
        nxt = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
        if not isinstance(nxt, Exception):
            break
        cur = nxt
    return False


def _is_certificate_rejected_error(exc: Exception) -> bool:
    """Return True if *exc* indicates client certificate rejection."""
    cur = exc
    for _ in range(8):
        text = f"{type(cur).__name__}: {cur}".lower()
        if any(
            token in text
            for token in (
                "certificate_unknown",
                "unknown ca",
                "unknown_ca",
                "bad certificate",
                "bad_certificate",
                "sslv3_alert_certificate_unknown",
            )
        ):
            return True
        nxt = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
        if not isinstance(nxt, Exception):
            break
        cur = nxt
    return False


def _clear_tak_cert_cache(raw_url: str) -> None:
    """Delete cached tak:// enrollment cert + passphrase for this host/user."""
    params = pytak.parse_tak_url(raw_url)
    hostname = params["hostname"]
    username = params["username"]

    cache_dir = Path.home() / ".pytak" / "certs"
    key = hashlib.sha256(f"{hostname}:{username}".encode()).hexdigest()[:16]
    p12_path = cache_dir / f"{key}.p12"
    pass_path = cache_dir / f"{key}.pass"
    for path in (p12_path, pass_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _tak_connection_candidates(raw_url: str, resolved_cot_url: str) -> list:
    """Build ordered COT_URL candidates for tak:// enrollment connections."""
    tak_params = pytak.parse_tak_url(raw_url)
    hostname = tak_params["hostname"]
    explicit_port = tak_params.get("explicit_port", False)
    port = tak_params["port"] if explicit_port else pytak.DEFAULT_MARTI_PORT

    candidates = [resolved_cot_url]

    if resolved_cot_url.startswith("wss://"):
        candidates.append(f"marti://{hostname}:{port}")
        if explicit_port and port != pytak.DEFAULT_MARTI_PORT:
            candidates.append(f"wss://{hostname}:{pytak.DEFAULT_MARTI_PORT}{DEFAULT_WS_PATH}")
            candidates.append(f"marti://{hostname}:{pytak.DEFAULT_MARTI_PORT}")
    elif resolved_cot_url.startswith("tls://"):
        # Keep a streaming fallback only when the tak:// URL explicitly names
        # the streaming port.
        candidates.append(f"tls://{hostname}:{port}")

    # Keep order but drop duplicates.
    deduped = []
    for url in candidates:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


async def _run(args) -> None:
    raw_url: str = args.url

    # Build flat config dict from CLI args + environment
    env = {k: v for k, v in os.environ.items() if "%" not in v}
    cfg: dict = {**env}
    cfg["COT_URL"] = raw_url
    cfg["DEBUG"] = "1" if args.debug else cfg.get("DEBUG", "0")

    if args.tls_cert:
        cfg["PYTAK_TLS_CLIENT_CERT"] = args.tls_cert
    if args.tls_key:
        cfg["PYTAK_TLS_CLIENT_KEY"] = args.tls_key
    if args.tls_ca:
        cfg["PYTAK_TLS_CLIENT_CAFILE"] = args.tls_ca
    if args.tls_pass:
        cfg["PYTAK_TLS_CLIENT_PASSWORD"] = args.tls_pass
    if args.no_verify:
        cfg["PYTAK_TLS_DONT_VERIFY"] = "1"
        cfg["PYTAK_TLS_DONT_CHECK_HOSTNAME"] = "1"

    # Resolve tak:// onboarding URL before building the CLITool
    transport_candidates = [raw_url]
    if raw_url.lower().startswith("tak://"):
        await _resolve_tak_url(raw_url, cfg)
        transport_candidates = _tak_connection_candidates(raw_url, cfg.get("COT_URL", ""))

    tx_source = _get_tx_source(args, sys.stdin.isatty())

    last_exc = None
    is_tak_url = raw_url.lower().startswith("tak://")
    re_enrolled_once = False

    while True:
        cert_rejected_in_cycle = False

        for idx, candidate_url in enumerate(transport_candidates):
            cfg["COT_URL"] = candidate_url
            if is_tak_url:
                print(
                    f"[pytak] Trying transport {idx + 1}/{len(transport_candidates)}: {candidate_url}",
                    file=sys.stderr,
                    flush=True,
                )

            # Build a ConfigParser SectionProxy (what CLITool expects)
            full_config = RawConfigParser()
            full_config.add_section("pytak")
            for k, v in cfg.items():
                full_config.set("pytak", k, str(v))
            config = full_config["pytak"]

            clitool = pytak.CLITool(config)

            try:
                await clitool.setup()

                tasks = set()

                if tx_source == "stdin":
                    tasks.add(StdinWorker(clitool.tx_queue, config))
                elif tx_source == "file":
                    tasks.add(FileWorker(clitool.tx_queue, config, args.tx_file))

                # RX: write received CoT to stdout
                if not args.tx_only:
                    tasks.add(StdoutWorker(clitool.rx_queue, config))

                if tasks:
                    clitool.add_tasks(tasks)

                await clitool.run()
                return
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_exc = exc

                has_more_candidates = idx < (len(transport_candidates) - 1)
                if is_tak_url and has_more_candidates and _is_ssl_transport_error(exc):
                    if _is_certificate_rejected_error(exc):
                        cert_rejected_in_cycle = True
                    print(
                        f"[pytak] Transport failed ({type(exc).__name__}: {exc}). Retrying...",
                        file=sys.stderr,
                        flush=True,
                    )
                    continue
                if is_tak_url:
                    break
                raise

        if is_tak_url and cert_rejected_in_cycle and not re_enrolled_once:
            re_enrolled_once = True
            print(
                "[pytak] Certificate appears rejected by server. "
                "Clearing cache and re-enrolling once...",
                file=sys.stderr,
                flush=True,
            )
            _clear_tak_cert_cache(raw_url)
            await _resolve_tak_url(raw_url, cfg)
            transport_candidates = _tak_connection_candidates(
                raw_url, cfg.get("COT_URL", "")
            )
            continue

        break

    if last_exc is not None:
        if is_tak_url:
            print(
                "[pytak] All enrolled transport candidates failed.",
                file=sys.stderr,
                flush=True,
            )
            print(
                "[pytak] Final failure: "
                f"{type(last_exc).__name__}: {last_exc}",
                file=sys.stderr,
                flush=True,
            )
        raise last_exc


def main() -> None:
    """Entry point for the ``pytak`` command."""
    parser = argparse.ArgumentParser(
        prog="pytak",
        description="TAK network client — reads CoT from stdin, writes CoT to stdout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
URL schemes
-----------
  tcp://host:port           Plain TCP (CoT XML)
  tls://host:port           TLS mutual auth (CoT XML, requires --tls-cert)
  udp://group:port          UDP multicast — Mesh SA
  udp+wo://host:port        UDP write-only
  ws://host/path            WebSocket plain (TAK Protocol v1 Protobuf)
    wss://host:8446/path       WebSocket TLS   (default for tak://)
    wss://host:8443/path       WebSocket TLS   (explicit tak://...:8443)
  marti://host:port         TAK Server Marti REST API (TLS)
  marti+http://host:port    TAK Server Marti REST API (plain HTTP)
  tak://...                 TAK enrollment deep-link — auto-enrolls, connects via wss://
  log://stdout              Print CoT to stdout (debug / dry-run)

Examples
--------
  # Print received CoT to stdout
  pytak tcp://takserver.example.com:8087

  # Send a CoT event
  echo '<event version="2.0" type="t-x-d-d" uid="ping" how="m-g"
        time="2026-01-01T00:00:00Z" start="2026-01-01T00:00:00Z"
        stale="2026-01-01T01:00:00Z"/>' | pytak tcp://takserver.example.com:8087

  # Stream events from a file, receive replies
  pytak --tx-file events.xml tls://takserver.example.com:8089 --tls-cert client.pem

    # Enroll and connect via WebSocket
    pytak "tak://com.atakmap.app/enroll?host=takserver.example.com&"
    "username=user&token=xxx"

  # Pipe CoT through two TAK Servers
  pytak --rx-only tcp://server1:8087 | pytak --tx-only tcp://server2:8087
""",
    )

    parser.add_argument("url", help="TAK destination URL (see schemes above)")
    parser.add_argument(
        "--rx-only", action="store_true",
        help="Receive only — ignore stdin, only write to stdout",
    )
    parser.add_argument(
        "--tx-only", action="store_true",
        help="Send only — read from stdin, suppress stdout output",
    )
    parser.add_argument(
        "--tx-file", metavar="PATH",
        help="Send CoT from file (frames XML events on </event>)",
    )
    parser.add_argument(
        "--tls-cert", metavar="PATH",
        help="TLS client certificate (.pem or .p12)",
    )
    parser.add_argument(
        "--tls-key", metavar="PATH",
        help="TLS client private key (.pem), if separate from --tls-cert",
    )
    parser.add_argument(
        "--tls-ca", metavar="PATH",
        help="CA trust chain (.pem) for server certificate verification",
    )
    parser.add_argument(
        "--tls-pass", metavar="PASSWORD",
        help="Password for --tls-cert (.p12) or encrypted private key",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip TLS certificate and hostname verification (development only)",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # argparse validation that depends on runtime stdin state
    try:
        _get_tx_source(args, sys.stdin.isatty())
    except ValueError as exc:
        parser.error(str(exc))

    if args.rx_only and args.tx_only:
        parser.error("--rx-only and --tx-only cannot be used together")

    log_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[pytak] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
