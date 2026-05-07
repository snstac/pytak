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
import logging
import os
import sys
import xml.etree.ElementTree as ET
from configparser import RawConfigParser

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
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode").encode("utf-8")
    except ET.ParseError:
        return data


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
    """Enroll via a tak:// URL and update cfg in place with wss:// settings.

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

    # resolve_tak_url returns COT_URL=tls://hostname:8089 (streaming port).
    # For the CLI we use WebSocket instead: wss://hostname:8443/takproto/1
    tak_params = pytak.parse_tak_url(raw_url)
    hostname = tak_params["hostname"]
    ws_url = f"wss://{hostname}:{pytak.DEFAULT_WS_PORT}{DEFAULT_WS_PATH}"

    cfg.update(resolved)
    cfg["COT_URL"] = ws_url
    print(f"[pytak] Enrolled. Connecting to {ws_url}", file=sys.stderr, flush=True)


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
    if raw_url.lower().startswith("tak://"):
        await _resolve_tak_url(raw_url, cfg)

    # Build a ConfigParser SectionProxy (what CLITool expects)
    full_config = RawConfigParser()
    full_config.add_section("pytak")
    for k, v in cfg.items():
        full_config.set("pytak", k, str(v))
    config = full_config["pytak"]

    clitool = pytak.CLITool(config)
    await clitool.setup()

    tasks = set()

    tx_source = _get_tx_source(args, sys.stdin.isatty())
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
  wss://host:8443/path       WebSocket TLS   (TAK Protocol v1 Protobuf)
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


if __name__ == "__main__":
    main()
