#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# classes.py from https://github.com/snstac/pytak
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""PyTAK Class Definitions."""

import abc
import asyncio
import ipaddress
import logging
import multiprocessing as mp
import random
import re
from datetime import datetime, timezone, timedelta


import os
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Dict, Any
import argparse
import sys


import xml.etree.ElementTree as ET

from dataclasses import dataclass
from typing import Set, Union

from configparser import ConfigParser, SectionProxy

import pytak

try:
    import takproto  # type: ignore
except ImportError:
    takproto = None


def _takmsg2xml(msg) -> Optional[bytes]:
    """Convert a takproto TakMessage back to CoT XML bytes.

    Reverses the xml2message() transform: extracts fields from msg.cotEvent
    and reconstructs a minimal but complete <event> element.
    """
    try:
        from datetime import timezone as _tz
        cot = msg.cotEvent
        if not cot.uid:
            return None

        def _ms2iso(ms: int) -> str:
            return datetime.fromtimestamp(ms / 1000.0, tz=_tz.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        attrib = {
            "type": cot.type,
            "uid": cot.uid,
            "how": cot.how,
            "time": _ms2iso(cot.sendTime),
            "start": _ms2iso(cot.startTime),
            "stale": _ms2iso(cot.staleTime),
            "version": "2.0",
        }
        if cot.access:
            attrib["access"] = cot.access
        if cot.qos:
            attrib["qos"] = cot.qos

        event = ET.Element("event", attrib)
        ET.SubElement(event, "point", {
            "lat": str(cot.lat),
            "lon": str(cot.lon),
            "hae": str(cot.hae),
            "ce": str(cot.ce),
            "le": str(cot.le),
        })

        detail = ET.SubElement(event, "detail")
        d = cot.detail
        if d.xmlDetail:
            try:
                # xmlDetail is a raw XML fragment; wrap it to parse, then graft children
                frag = ET.fromstring(f"<x>{d.xmlDetail}</x>")
                for child in frag:
                    detail.append(child)
            except ET.ParseError:
                detail.text = (detail.text or "") + d.xmlDetail
        if d.HasField("contact") and (d.contact.callsign or d.contact.endpoint):
            ET.SubElement(detail, "contact", {
                k: v for k, v in [("callsign", d.contact.callsign), ("endpoint", d.contact.endpoint)] if v
            })
        if d.HasField("group") and d.group.name:
            ET.SubElement(detail, "__group", {"name": d.group.name, "role": d.group.role})
        if d.HasField("track") and (d.track.speed or d.track.course):
            ET.SubElement(detail, "track", {
                "speed": str(d.track.speed),
                "course": str(d.track.course),
            })
        if d.HasField("takv") and d.takv.version:
            ET.SubElement(detail, "takv", {
                k: v for k, v in [
                    ("device", d.takv.device), ("platform", d.takv.platform),
                    ("os", d.takv.os), ("version", d.takv.version),
                ] if v
            })

        return ET.tostring(event, encoding="unicode").encode("utf-8")
    except Exception:  # pylint: disable=broad-except
        return None

try:
    import aiohttp as _aiohttp  # type: ignore
except ImportError:
    _aiohttp = None


# Optimized: Shared logger configuration to avoid duplication
def _setup_logger(logger: logging.Logger, level: int = None) -> logging.Logger:
    """Configure a logger with standard PyTAK formatting."""
    if not logger.handlers:
        log_level = level or pytak.LOG_LEVEL
        logger.setLevel(log_level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(pytak.LOG_FORMAT)
        logger.addHandler(console_handler)
        logger.propagate = False
    return logger


class Worker:
    """Meta class for all other Worker Classes."""

    _logger = _setup_logger(logging.getLogger(__name__))
    logging.getLogger("asyncio").setLevel(pytak.LOG_LEVEL)

    def __init__(
        self,
        queue: Union[asyncio.Queue, mp.Queue],
        config: Union[None, SectionProxy, dict] = None,
    ) -> None:
        """Initialize a Worker instance."""
        self.queue: Union[asyncio.Queue, mp.Queue] = queue
        if config:
            self.config = config
        else:
            config_p = ConfigParser({})
            config_p.add_section("pytak")
            self.config = config_p["pytak"] or {}

        if bool(self.config.get("DEBUG")):
            for handler in self._logger.handlers:
                handler.setLevel(logging.DEBUG)

        tak_proto_version = int(self.config.get("TAK_PROTO") or pytak.DEFAULT_TAK_PROTO)

        if tak_proto_version > 0 and takproto is None:
            self._logger.warning(
                "TAK_PROTO is set to '%s', but the 'takproto' Python module is not installed.\n"
                "Try: python -m pip install pytak[with_takproto]\n"
                "See Also: https://pytak.rtfd.io/en/latest/compatibility/#tak-protocol-payload-version-1-protobuf",
                tak_proto_version,
            )

        self.use_protobuf = tak_proto_version > 0 and takproto is not None

    async def fts_compat(self) -> None:
        """Apply FreeTAKServer (FTS) compatibility.

        If the FTS_COMPAT (or PYTAK_SLEEP) config options are set, will async sleep for
        either a given (PYTAK_SLEEP) or random (FTS_COMPAT) time.
        """
        pytak_sleep: int = int(self.config.get("PYTAK_SLEEP") or 0)
        if bool(self.config.get("FTS_COMPAT") or pytak_sleep):
            sleep_period: int = int(
                pytak_sleep or (int(pytak.DEFAULT_SLEEP) * random.random())
            )
            self._logger.debug("COMPAT: Sleeping for %ss", sleep_period)
            await asyncio.sleep(sleep_period)

    @abc.abstractmethod
    async def handle_data(self, data: bytes) -> None:
        """Handle data (placeholder method, please override)."""
        pass

    async def _handle_full_queue(self, queue: Union[asyncio.Queue, mp.Queue]) -> None:
        """Handle a full queue by removing oldest item. Optimized to reduce code duplication."""
        self._logger.warning(
            "Queue full, dropping oldest data. Consider raising MAX_IN_QUEUE or MAX_OUT_QUEUE see https://pytak.rtfd.io/"
        )
        if isinstance(queue, asyncio.Queue):
            await queue.get()
        else:
            queue.get_nowait()

    async def run_once(self) -> None:
        """Reads Data from Queue & passes data to next Handler."""
        data = await self.queue.get()
        await self.handle_data(data)
        await self.fts_compat()

    async def run(self, _=-1) -> None:
        """Run this Thread - calls run_once() in a loop."""
        self._logger.info("Running: %s", self.__class__.__name__)
        while True:
            await self.run_once()
            await asyncio.sleep(0)  # make sure other tasks have a chance to run

    async def close(self) -> None:
        """Release resources held by this worker (override where needed)."""
        return


class TXWorker(Worker):
    """Works data queue and hands off to Protocol Workers.

    You should create an TXWorker Instance using the `pytak.txworker_factory()`
    Function.

    Data is put onto the Queue using a `pytak.QueueWorker()` instance.
    """

    def __init__(
        self,
        queue: Union[asyncio.Queue, mp.Queue],
        config: Union[None, SectionProxy, dict],
        writer: asyncio.Protocol,
    ) -> None:
        """Initialize a TXWorker instance."""
        super().__init__(queue, config)
        self.writer: asyncio.Protocol = writer

    async def handle_data(self, data: bytes) -> None:
        """Accept CoT event from CoT event queue and process for writing."""
        # self._logger.debug("TX (%s): %s", self.config.get('name'), data)
        await self.send_data(data)

    async def send_data(self, data: bytes) -> None:
        """Send Data using the appropriate Protocol method."""
        if data is None:
            self._logger.warning("send_data called with None data, skipping send.")
            return

        if self.use_protobuf:
            host, _ = pytak.parse_url(self.config.get("COT_URL", pytak.DEFAULT_COT_URL))
            is_multicast: bool = False

            try:
                is_multicast = ipaddress.ip_address(host).is_multicast
            except ValueError:
                # It's probably not an ip address...
                pass

            if is_multicast:
                proto = takproto.TAKProtoVer.MESH
            else:
                proto = takproto.TAKProtoVer.STREAM

            try:
                data = takproto.xml2proto(data, proto)
            except ET.ParseError as exc:
                self._logger.warning(exc)
                self._logger.warning("Could not convert XML to Proto.")

        if hasattr(self.writer, "send"):
            await self.writer.send(data)
        else:
            if hasattr(self.writer, "write"):
                self.writer.write(data)
            if hasattr(self.writer, "drain"):
                await self.writer.drain()
            if hasattr(self.writer, "flush"):
                # FIXME: This should be an asyncio.Future?:
                self.writer.flush()


class RXWorker(Worker):
    """Async receive (input) queue worker.

    Reads events from a `pytak.protocol_factory()` reader and adds them to
    an `rx_queue`.

    Most implementations use this to drain an RX buffer on a socket.

    pytak([asyncio.Protocol]->[pytak.EventReceiver]->[queue.Queue])
    """

    def __init__(
        self,
        queue: Union[asyncio.Queue, mp.Queue],
        config: Union[None, SectionProxy, dict],
        reader: asyncio.Protocol,
    ) -> None:
        """Initialize a RXWorker instance."""
        super().__init__(queue, config)
        self.reader: asyncio.Protocol = reader
        self.reader_queue = None

    @abc.abstractmethod
    async def handle_data(self, data: bytes) -> None:
        """Handle data (placeholder method, please override)."""
        pass

    async def readcot(self):
        """Read CoT from the wire until we hit an event boundary."""
        cot = None
        try:
            if hasattr(self.reader, "readuntil"):
                cot = await self.reader.readuntil("</event>".encode("UTF-8"))
            elif hasattr(self.reader, "recv"):
                cot, _ = await self.reader.recv()

            if self.use_protobuf:
                tak_v1 = takproto.parse_proto(cot)
                if tak_v1 != -1:
                    cot = tak_v1  # .SerializeToString()
            return cot
        except asyncio.IncompleteReadError:
            return None

    async def run_once(self) -> None:
        """Run this worker once."""
        if self.reader:
            data: bytes = await self.readcot()
            if data:
                self._logger.debug("RX data: %s", data)
                self.queue.put_nowait(data)

    async def run(self, _=-1) -> None:
        """Run this worker."""
        self._logger.info("Running: %s", self.__class__.__name__)
        while True:
            await self.run_once()
            await asyncio.sleep(0)  # make sure other tasks have a chance to run


def _extract_cot_events(text: str) -> list:
    """Extract <event>...</event> blocks from a text blob (Marti API response)."""
    return re.findall(r"<event\b[^>]*>.*?</event>", text, re.DOTALL)


def _is_fatal_tls_cert_error(exc: Exception) -> bool:
    """Return True when *exc* indicates server-side client-cert rejection."""
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


class MartiTXWorker(Worker):
    """Transmit CoT events to a TAK Server via the Marti REST API.

    Dequeues CoT bytes and POSTs each one to
    ``POST /Marti/api/injectors/cot/uid`` as JSON
    ``{"uid": "<client_uid>", "toInject": "<cot_xml>"}``.

    Create via ``pytak.marti_txworker_factory()``.
    """

    def __init__(self, queue, config, session, base_url: str, client_uid: str) -> None:
        super().__init__(queue, config)
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._client_uid = client_uid

    async def handle_data(self, data: bytes) -> None:
        cot_xml = data.decode("utf-8", errors="ignore").strip()
        if not cot_xml:
            return
        payload = {"uid": self._client_uid, "toInject": cot_xml}
        try:
            async with self._session.post(
                f"{self._base_url}/Marti/api/injectors/cot/uid",
                json=payload,
            ) as resp:
                if resp.status not in (200, 201, 204):
                    self._logger.warning(
                        "Marti inject returned HTTP %s", resp.status
                    )
        except Exception as exc:
            if _is_fatal_tls_cert_error(exc):
                raise PermissionError(
                    f"Marti TX rejected client certificate: {exc}"
                ) from exc
            self._logger.error("Marti TX error: %s", exc)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


class MartiRXWorker(Worker):
    """Receive CoT events from a TAK Server via the Marti REST API.

    Polls ``GET /Marti/api/cot/sa`` on a timer and puts each received
    CoT event onto the rx queue.

    Create via ``pytak.marti_rxworker_factory()``.
    """

    def __init__(
        self,
        queue,
        config,
        session,
        base_url: str,
        poll_interval: int = pytak.DEFAULT_MARTI_POLL_INTERVAL,
        seconds_ago: int = pytak.DEFAULT_MARTI_POLL_SECONDS_AGO,
    ) -> None:
        super().__init__(queue, config)
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._poll_interval = poll_interval
        self._last_poll: Optional[datetime] = None
        self._seconds_ago = seconds_ago

    async def handle_data(self, data: bytes) -> None:
        pass

    async def run_once(self) -> None:
        now = datetime.now(timezone.utc)
        start = self._last_poll or (now - timedelta(seconds=self._seconds_ago))
        self._last_poll = now

        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        params = {"start": start.strftime(fmt), "end": now.strftime(fmt)}
        try:
            async with self._session.get(
                f"{self._base_url}/Marti/api/cot/sa",
                params=params,
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    for event_xml in _extract_cot_events(text):
                        self.queue.put_nowait(event_xml.encode("utf-8"))
                else:
                    self._logger.debug("Marti RX returned HTTP %s", resp.status)
        except Exception as exc:
            if _is_fatal_tls_cert_error(exc):
                raise PermissionError(
                    f"Marti RX rejected client certificate: {exc}"
                ) from exc
            self._logger.error("Marti RX error: %s", exc)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def run(self, _=-1) -> None:
        self._logger.info("Running: %s", self.__class__.__name__)
        while True:
            await self.run_once()
            await asyncio.sleep(self._poll_interval)


class WSTXWorker(Worker):
    """Transmit CoT events to a TAK Server via WebSocket (ws:// or wss://).

    Encodes CoT XML as TAK Protocol v1 Protobuf (STREAM variant) before
    sending as a binary WebSocket frame.  Falls back to raw bytes if
    ``takproto`` is not installed, which is useful for custom WS servers
    that accept plain XML.

    Create via ``pytak.ws_factory()``.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        config,
        ws,
        session=None,
    ) -> None:
        super().__init__(queue, config)
        self._ws = ws
        self._session = session

    async def handle_data(self, data: bytes) -> None:
        if not data:
            return
        if takproto is not None:
            try:
                data = takproto.xml2proto(data, takproto.TAKProtoVer.STREAM)
            except Exception as exc:
                self._logger.warning("WS TX: Protobuf encode failed, sending raw: %s", exc)
        try:
            await self._ws.send_bytes(data)
        except Exception as exc:
            raise ConnectionError(f"WebSocket TX send failed: {exc}") from exc

    async def close(self) -> None:
        try:
            await self._ws.close()
        except Exception:
            pass
        if self._session:
            await self._session.close()


class WSRXWorker(Worker):
    """Receive CoT events from a TAK Server via WebSocket (ws:// or wss://).

    Reads binary WebSocket frames, decodes TAK Protocol v1 Protobuf to CoT
    XML bytes, and puts each event onto the rx queue.

    Create via ``pytak.ws_factory()``.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        config,
        ws,
        session=None,
    ) -> None:
        super().__init__(queue, config)
        self._ws = ws
        self._session = session

    async def handle_data(self, data: bytes) -> None:
        pass  # data flows directly to queue in run_once

    async def run_once(self) -> None:
        if _aiohttp is None:
            return
        msg = await self._ws.receive()
        if msg.type == _aiohttp.WSMsgType.BINARY:
            payload: Optional[bytes] = msg.data
            if takproto is not None:
                tak_msg = takproto.parse_proto(payload)
                if tak_msg and tak_msg != -1:
                    if isinstance(tak_msg, bytes):
                        payload = tak_msg
                    else:
                        payload = _takmsg2xml(tak_msg)
                else:
                    payload = None
            if payload:
                self.queue.put_nowait(payload)
        elif msg.type in (_aiohttp.WSMsgType.CLOSE, _aiohttp.WSMsgType.CLOSED):
            raise ConnectionAbortedError("WebSocket closed by server")
        elif msg.type == _aiohttp.WSMsgType.ERROR:
            raise ConnectionError(f"WebSocket error: {self._ws.exception()}")

    async def run(self, _=-1) -> None:
        self._logger.info("Running: %s", self.__class__.__name__)
        while True:
            await self.run_once()


class QueueWorker(Worker):
    """Read non-CoT Messages from an async network client.

    (`asyncio.Protocol` or similar async network client)
    Serializes it as COT, and puts it onto an `asyncio.Queue`.

    Implementations should handle serializing messages as COT Events, and
    putting them onto the `event_queue`.

    The `event_queue` is handled by the `pytak.EventWorker` Class.

    pytak([asyncio.Protocol]->[pytak.MessageWorker]->[asyncio.Queue])
    """

    def __init__(
        self,
        queue: Union[asyncio.Queue, mp.Queue],
        config: Union[None, SectionProxy, dict],
    ) -> None:
        super().__init__(queue, config)
        self._logger.info("Using COT_URL='%s'", self.config.get("COT_URL"))

    @abc.abstractmethod
    async def handle_data(self, data: bytes) -> None:
        """Handle data (placeholder method, please override)."""
        pass

    async def put_queue(
        self, data: bytes, queue_arg: Union[asyncio.Queue, mp.Queue, None] = None
    ) -> None:
        """Put Data onto the Queue."""
        _queue = queue_arg or self.queue
        self._logger.debug("Queue size=%s", _queue.qsize())
        
        # Optimized: Check for full queue once and handle uniformly
        if _queue.full():
            await self._handle_full_queue(_queue)
        
        if isinstance(_queue, asyncio.Queue):
            await _queue.put(data)
        else:
            _queue.put_nowait(data)


async def _make_workers(tx_queue, rx_queue, config):
    """Return (write_worker, read_worker) for the given config.

    Dispatches to the appropriate worker pair based on the ``COT_URL`` scheme:
    - ``marti://`` / ``marti+http://`` → Marti REST API workers
    - ``ws://`` / ``wss://`` → WebSocket workers
    - everything else → standard socket TXWorker / RXWorker
    """
    cot_url_str = config.get("COT_URL", "")
    scheme = cot_url_str.split("://")[0].lower() if "://" in cot_url_str else ""

    if scheme in ("marti", "marti+http"):
        write_worker = await pytak.marti_txworker_factory(tx_queue, config)
        read_worker = await pytak.marti_rxworker_factory(rx_queue, config)
    elif scheme in ("ws", "wss"):
        write_worker, read_worker = await pytak.ws_factory(tx_queue, rx_queue, config)
    else:
        reader, writer = await pytak.protocol_factory(config)
        write_worker = pytak.TXWorker(tx_queue, config, writer)
        read_worker = pytak.RXWorker(rx_queue, config, reader)

    return write_worker, read_worker


class CLITool:
    """Wrapper Object for CLITools."""

    _logger = _setup_logger(logging.getLogger(__name__))
    logging.getLogger("asyncio").setLevel(pytak.LOG_LEVEL)

    def __init__(
        self,
        config: Union[ConfigParser, SectionProxy],
        tx_queue: Union[asyncio.Queue, mp.Queue, None] = None,
        rx_queue: Union[asyncio.Queue, mp.Queue, None] = None,
    ) -> None:
        """Initialize CLITool instance."""
        self.tasks: Set = set()
        self.running_tasks: Set = set()
        self._config = config
        self.queues: dict = {}

        self.max_in_queue = int(
            self._config.get("MAX_IN_QUEUE") or pytak.DEFAULT_MAX_IN_QUEUE
        )
        self.max_out_queue = int(
            self._config.get("MAX_OUT_QUEUE") or pytak.DEFAULT_MAX_OUT_QUEUE
        )
        self.tx_queue: Union[asyncio.Queue, mp.Queue] = tx_queue or asyncio.Queue(
            self.max_out_queue
        )
        self.rx_queue: Union[asyncio.Queue, mp.Queue] = rx_queue or asyncio.Queue(
            self.max_in_queue
        )

        if isinstance(self._config, SectionProxy) and bool(self._config.get("DEBUG")):
            for handler in self._logger.handlers:
                handler.setLevel(logging.DEBUG)

    @property
    def config(self):
        """Return the config object."""
        return self._config

    @config.setter
    def config(self, val):
        """Set the config object."""
        self._config = val

    async def create_workers(self, i_config):
        """
        Create and run queue workers with specified config parameters.

        Parameters
        ----------
        i_config : `configparser.SectionProxy`
            Configuration options & values.
        """
        tx_queue = asyncio.Queue(self.max_out_queue)
        rx_queue = asyncio.Queue(self.max_in_queue)
        if len(self.queues) == 0:
            # If the queue list is empty, make this the default.
            self.tx_queue = tx_queue
            self.rx_queue = rx_queue
        self.queues[i_config.name] = {"tx_queue": tx_queue, "rx_queue": rx_queue}

        write_worker, read_worker = await _make_workers(tx_queue, rx_queue, i_config)
        self.add_task(write_worker)
        self.add_task(read_worker)

    async def setup(self) -> None:
        """Set up CLITool.

        Creates protocols, queue workers and adds them to our task list.
        """
        write_worker, read_worker = await _make_workers(
            self.tx_queue, self.rx_queue, self.config
        )
        self.add_task(write_worker)
        self.add_task(read_worker)

    async def hello_event(self):
        """Send a 'hello world' style event to the Queue."""
        hello = pytak.hello_event(self.config.get("COT_HOST_ID"))
        if hello:
            self.tx_queue.put_nowait(hello)

    def add_task(self, task):
        """Add the given task to our coroutine task list."""
        self._logger.debug("Add Task: %s", task)
        self.tasks.add(task)

    def add_tasks(self, tasks):
        """Add the given list or set of tasks to our couroutine task list."""
        for task in tasks:
            self.add_task(task)

    def run_task(self, task):
        """Run the given coroutine task."""
        self._logger.debug("Run Task: %s", task)
        future = asyncio.ensure_future(task.run())
        setattr(future, "_pytak_worker", task)
        self.running_tasks.add(future)
        # self.running_tasks.add(run_coroutine_in_thread(task.run()))

    async def _close_running_workers(self, tasks: Set[asyncio.Task]) -> None:
        """Close worker resources associated with completed/pending tasks."""
        workers = []
        for task in tasks:
            worker = getattr(task, "_pytak_worker", None)
            if worker is not None and worker not in workers:
                workers.append(worker)

        for worker in workers:
            try:
                await worker.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._logger.debug("Worker close error for %s: %s", worker, exc)

    def run_tasks(self, tasks=None):
        """Run the given list or set of couroutine tasks."""
        tasks = tasks or self.tasks
        for task in tasks:
            self.run_task(task)
        self.tasks.clear()

    async def run(self):
        """Run this Thread and its associated coroutine tasks."""
        self._logger.info("Run: %s", self.__class__.__name__)

        if not self.config.get("PYTAK_NO_HELLO", False):
            await self.hello_event()

        self.run_tasks()

        done, pending = await asyncio.wait(
            self.running_tasks, return_when=asyncio.FIRST_EXCEPTION
        )

        failing_exc = None
        try:
            for task in done:
                self._logger.info("Complete: %s", task)
                exc = task.exception()
                if exc is not None and failing_exc is None:
                    failing_exc = exc

            if failing_exc is not None:
                for pending_task in pending:
                    pending_task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                raise failing_exc
        finally:
            await self._close_running_workers(done | pending)


@dataclass
class SimpleCOTEvent:
    """CoT Event Dataclass."""

    lat: Union[bytes, str, float, None] = None
    lon: Union[bytes, str, float, None] = None
    uid: Union[str, None] = None
    stale: Union[float, int, None] = None
    cot_type: Union[str, None] = None

    def __str__(self) -> str:
        """Return a formatted string representation of the dataclass."""
        event = self.to_xml()
        return ET.tostring(event, encoding="unicode")

    def to_bytes(self) -> bytes:
        """Return the class as bytes."""
        event = self.to_xml()
        return ET.tostring(event, encoding="utf-8")

    def to_xml(self) -> ET.Element:
        """Return a CoT Event as an XML string."""
        cotevent = COTEvent(
            lat=self.lat,
            lon=self.lon,
            uid=self.uid,
            stale=self.stale,
            cot_type=self.cot_type,
            le=pytak.DEFAULT_COT_VAL,
            ce=pytak.DEFAULT_COT_VAL,
            hae=pytak.DEFAULT_COT_VAL,
        )
        event = pytak.cot2xml(cotevent)
        return event


@dataclass
class COTEvent(SimpleCOTEvent):
    """COT Event Dataclass."""

    ce: Union[bytes, str, float, int, None] = None
    hae: Union[bytes, str, float, int, None] = None
    le: Union[bytes, str, float, int, None] = None

    def to_xml(self) -> ET.Element:
        """Return a CoT Event as an XML string."""
        cotevent = COTEvent(
            lat=self.lat,
            lon=self.lon,
            uid=self.uid,
            stale=self.stale,
            cot_type=self.cot_type,
            le=self.le,
            ce=self.ce,
            hae=self.hae,
        )
        event = pytak.cot2xml(cotevent)
        return event


class TAKDataPackage:
    """
    Generator for TAK Data Package formatted zip files.
    """
    
    def __init__(self, name: str, uid: Optional[str] = None, on_receive_delete: bool = False):
        """
        Initialize TAK Data Package generator.
        
        Args:
            name: Display name for the data package
            uid: Unique identifier (auto-generated if None)
            on_receive_delete: Whether to delete package after import
        """
        self.name = name
        self.uid = uid or str(uuid.uuid4())
        self.on_receive_delete = on_receive_delete
        self.files: List[Dict[str, Any]] = []
        
    def add_file(self, file_path: str, ignore: bool = False, zip_entry_name: Optional[str] = None):
        """
        Add a file to the data package.
        
        Args:
            file_path: Path to the file to include
            ignore: Whether to ignore this file during import
            zip_entry_name: Custom name for the file in the zip (uses filename if None)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        entry_name = zip_entry_name or os.path.basename(file_path)
        
        self.files.append({
            'path': file_path,
            'zip_entry': entry_name,
            'ignore': ignore
        })
        
    def add_directory(self, dir_path: str, recursive: bool = True, ignore_pattern: Optional[str] = None):
        """
        Add all files from a directory to the data package.
        
        Args:
            dir_path: Path to the directory
            recursive: Whether to include subdirectories
            ignore_pattern: File pattern to ignore (simple wildcard matching)
        """
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
            
        dir_path = Path(dir_path)
        
        if recursive:
            files = dir_path.rglob('*')
        else:
            files = dir_path.glob('*')
            
        for file_path in files:
            if file_path.is_file():
                # Simple pattern matching for ignore_pattern
                if ignore_pattern and ignore_pattern in file_path.name:
                    continue
                    
                # Calculate relative path for zip entry
                relative_path = file_path.relative_to(dir_path)
                self.add_file(str(file_path), zip_entry_name=str(relative_path))
    
    def _generate_manifest_xml(self) -> str:
        """
        Generate the manifest.xml content based on current configuration.
        
        Returns:
            XML string for the manifest
        """
        # Create root element
        root = ET.Element("MissionPackageManifest", version="2")
        
        # Configuration section
        config = ET.SubElement(root, "Configuration")
        
        # Add parameters
        uid_param = ET.SubElement(config, "Parameter")
        uid_param.set("name", "uid")
        uid_param.set("value", self.uid)
        
        name_param = ET.SubElement(config, "Parameter")
        name_param.set("name", "name")
        name_param.set("value", self.name)
        
        delete_param = ET.SubElement(config, "Parameter")
        delete_param.set("name", "onReceiveDelete")
        delete_param.set("value", str(self.on_receive_delete).lower())
        
        # Contents section
        contents = ET.SubElement(root, "Contents")
        
        for file_info in self.files:
            content = ET.SubElement(contents, "Content")
            content.set("ignore", str(file_info['ignore']).lower())
            content.set("zipEntry", file_info['zip_entry'])
        
        # Format XML with proper indentation
        self._indent_xml(root)
        
        # Convert to string
        xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
        return xml_str
    
    def _indent_xml(self, elem, level=0):
        """Add proper indentation to XML elements."""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
    
    def create_package(self, output_path: str, use_dpk_extension: bool = False, include_manifest: bool = True):
        """
        Create the TAK Data Package zip file.
        
        Args:
            output_path: Path where to save the package
            use_dpk_extension: Use .dpk extension instead of .zip
            include_manifest: Whether to include the manifest (if False, files are imported serially)
        """
        if not self.files:
            raise ValueError("No files added to the package")
        
        # Ensure proper extension
        if use_dpk_extension and not output_path.endswith('.dpk'):
            output_path = output_path.rsplit('.', 1)[0] + '.dpk'
        elif not use_dpk_extension and not output_path.endswith('.zip'):
            output_path = output_path.rsplit('.', 1)[0] + '.zip'
        
        # Create the zip file
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files
            for file_info in self.files:
                zipf.write(file_info['path'], file_info['zip_entry'])
                print(f"Added: {file_info['zip_entry']}")
            
            # Add manifest if requested
            if include_manifest:
                manifest_xml = self._generate_manifest_xml()
                
                # Create MANIFEST directory and add manifest.xml
                zipf.writestr('MANIFEST/manifest.xml', manifest_xml)
                print("Added: MANIFEST/manifest.xml")
        
        print(f"\nTAK Data Package created: {output_path}")
        print(f"Package UID: {self.uid}")
        print(f"Files included: {len(self.files)}")

