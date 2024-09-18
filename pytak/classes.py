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
import queue as _queue
import random

import xml.etree.ElementTree as ET

from dataclasses import dataclass
from typing import Set, Union

from configparser import ConfigParser, SectionProxy

import pytak

try:
    import takproto  # type: ignore
except ImportError:
    takproto = None


class Worker:
    """Meta class for all other Worker Classes."""

    _logger = logging.getLogger(__name__)
    if not _logger.handlers:
        _logger.setLevel(pytak.LOG_LEVEL)
        _console_handler = logging.StreamHandler()
        _console_handler.setLevel(pytak.LOG_LEVEL)
        _console_handler.setFormatter(pytak.LOG_FORMAT)
        _logger.addHandler(_console_handler)
        _logger.propagate = False
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

        self.min_period = pytak.DEFAULT_MIN_ASYNC_SLEEP

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

    async def run(self, number_of_iterations=-1):
        """Run this Thread, reads Data from Queue & passes data to next Handler."""
        self._logger.info("Run: %s", self.__class__.__name__)

        # We're instantiating the while loop this way, and using get_nowait(),
        # to allow unit testing of at least one call of this loop.
        while number_of_iterations != 0:
            if self.queue.qsize() == 0:
                await asyncio.sleep(self.min_period)
                continue

            # self._logger.debug("TX queue size=%s", self.queue.qsize())
            data = None
            try:
                data = self.queue.get_nowait()
            except (asyncio.QueueEmpty, _queue.Empty):
                continue

            if not data:
                continue

            await self.handle_data(data)
            await self.fts_compat()

            number_of_iterations -= 1


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

    async def run(self, number_of_iterations=-1) -> None:
        """Run this worker."""
        self._logger.info("Run: %s", self.__class__.__name__)

        while 1:
            await asyncio.sleep(self.min_period)
            if self.reader:
                data: bytes = await self.readcot()
                if data:
                    self._logger.debug("RX: %s", data)
                    self.queue.put_nowait(data)


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
        if isinstance(_queue, asyncio.Queue):
            if _queue.full():
                self._logger.warning("Queue full, dropping oldest data.")
                await _queue.get()
            await _queue.put(data)
        else:
            if _queue.full():
                self._logger.warning("Queue full, dropping oldest data.")
                _queue.get_nowait()
            _queue.put_nowait(data)


class CLITool:
    """Wrapper Object for CLITools."""

    _logger = logging.getLogger(__name__)
    if not _logger.handlers:
        _logger.setLevel(pytak.LOG_LEVEL)
        _console_handler = logging.StreamHandler()
        _console_handler.setLevel(pytak.LOG_LEVEL)
        _console_handler.setFormatter(pytak.LOG_FORMAT)
        _logger.addHandler(_console_handler)
        _logger.propagate = False
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

        if bool(self._config.get("DEBUG") or 0):
            for handler in self._logger.handlers:
                handler.setLevel(logging.DEBUG)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, val):
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

        reader, writer = await pytak.protocol_factory(i_config)
        write_worker = pytak.TXWorker(tx_queue, i_config, writer)
        read_worker = pytak.RXWorker(rx_queue, i_config, reader)
        self.add_task(write_worker)
        self.add_task(read_worker)

    async def setup(self) -> None:
        """Set up CLITool.

        Creates protocols, queue workers and adds them to our task list.
        """
        # Create our TX & RX Protocol Worker
        reader, writer = await pytak.protocol_factory(self.config)
        write_worker = pytak.TXWorker(self.tx_queue, self.config, writer)
        read_worker = pytak.RXWorker(self.rx_queue, self.config, reader)
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
        self.running_tasks.add(asyncio.ensure_future(task.run()))
        # self.running_tasks.add(run_coroutine_in_thread(task.run()))

    def run_tasks(self, tasks=None):
        """Run the given list or set of couroutine tasks."""
        tasks = tasks or self.tasks
        for task in tasks:
            self.run_task(task)
        self.tasks.clear()

    async def run(self):
        """Run this Thread and its associated coroutine tasks."""
        self._logger.info("Run: %s", self.__class__.__name__)

        await self.hello_event()
        self.run_tasks()

        done, _ = await asyncio.wait(
            self.running_tasks, return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            self._logger.info("Complete: %s", task)


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
