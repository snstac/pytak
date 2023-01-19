#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2023 Greg Albrecht <oss@undef.net>
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
# Author:: Greg Albrecht W2GMD <oss@undef.net>
#

"""PyTAK Class Definitions."""

import asyncio
import logging
import multiprocessing as mp
import queue as _queue
import random

from typing import Set, Union

from configparser import ConfigParser

import pytak

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2023 Greg Albrecht"
__license__ = "Apache License, Version 2.0"


class Worker:  # pylint: disable=too-few-public-methods
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
        config: ConfigParser = None
    ) -> None:
        """Initialize a Worker instance."""
        self.queue: Union[asyncio.Queue, mp.Queue] = queue
        if config:
            self.config = config
        else:
            config_p = ConfigParser({})
            config_p.add_section("pytak")
            self.config = config_p["pytak"]
        if self.config.getboolean("DEBUG", False):
            _ = [x.setLevel(logging.DEBUG) for x in self._logger.handlers]

        self.min_period = pytak.DEFAULT_MIN_ASYNC_SLEEP

    async def fts_compat(self) -> None:
        """Apply FreeTAKServer (FTS) compatibility.

        If the FTS_COMPAT (or PYTAK_SLEEP) config options are set, will async sleep for
        either a given (PYTAK_SLEEP) or random (FTS_COMPAT) time.
        """
        pytak_sleep: int = self.config.get("PYTAK_SLEEP", 0)
        if self.config.getboolean("FTS_COMPAT") or pytak_sleep:
            sleep_period: int = int(
                pytak_sleep or (pytak.DEFAULT_SLEEP * random.random())
            )
            self._logger.debug("COMPAT: Sleeping for %ss", sleep_period)
            await asyncio.sleep(sleep_period)

    async def handle_data(self, data: bytes) -> None:
        """Handle data (placeholder method, please override)."""
        del data
        self._logger.warning("Override this method!")

    async def run(self, number_of_iterations=-1):
        """Run this Thread, reads Data from Queue & passes data to next Handler."""
        self._logger.info("Run: %s", self.__class__)

        # We're instantiating the while loop this way, and using get_nowait(),
        # to allow unit testing of at least one call of this loop.
        while number_of_iterations != 0:
            await asyncio.sleep(self.min_period)

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


class TXWorker(Worker):  # pylint: disable=too-few-public-methods
    """Works data queue and hands off to Protocol Workers.

    You should create an TXWorker Instance using the `pytak.txworker_factory()`
    Function.

    Data is put onto the Queue using a `pytak.QueueWorker()` instance.
    """

    def __init__(
        self, queue: asyncio.Queue, config: ConfigParser, writer: asyncio.Protocol
    ) -> None:
        """Initialize a TXWorker instance."""
        super().__init__(queue, config)
        self.writer: asyncio.Protocol = writer

    async def handle_data(self, data: bytes) -> None:
        """Accept CoT event from CoT event queue and process for writing."""
        self._logger.debug("TX: %s", data)
        await self.send_data(data)

    async def send_data(self, data: bytes) -> None:
        """Send Data using the appropriate Protocol method."""
        if hasattr(self.writer, "send"):
            await self.writer.send(data)
        else:
            self.writer.write(data)
            if hasattr(self.writer, "drain"):
                await self.writer.drain()
            if hasattr(self.writer, "flush"):
                # FIXME: This should be an asyncio.Future?:
                self.writer.flush()


class RXWorker(Worker):  # pylint: disable=too-few-public-methods
    """Async receive (input) queue worker.
    
    Reads events from a `pytak.protocol_factory()` reader and adds them to 
    an `rx_queue`.

    Most implementations use this to drain an RX buffer on a socket.

    pytak([asyncio.Protocol]->[pytak.EventReceiver]->[queue.Queue])
    """

    def __init__(
        self, queue: asyncio.Queue, config: dict, reader: asyncio.Protocol
    ) -> None:
        """Initialize a RXWorker instance."""
        super().__init__(queue, config)
        self.reader: asyncio.Protocol = reader
        self.reader_queue: asyncio.Queue = asyncio.Queue

    async def readcot(self):
        if hasattr(self.reader, 'readuntil'):
            return await self.reader.readuntil("</event>".encode("UTF-8"))
        elif hasattr(self.reader, 'recv'):
            buf, _ = await self.reader.recv()
            return buf

    async def run(self, number_of_iterations=-1) -> None:
        self._logger.info("Run: %s", self.__class__)

        while 1:
            await asyncio.sleep(self.min_period)
            if self.reader:
                data: bytes = await self.readcot()
                self._logger.debug("RX: %s", data)
                self.queue.put_nowait(data)


class QueueWorker(Worker):  # pylint: disable=too-few-public-methods
    """Read non-CoT Messages from an async network client.

    (`asyncio.Protocol` or similar async network client)
    Serializes it as COT, and puts it onto an `asyncio.Queue`.

    Implementations should handle serializing messages as COT Events, and
    putting them onto the `event_queue`.

    The `event_queue` is handled by the `pytak.EventWorker` Class.

    pytak([asyncio.Protocol]->[pytak.MessageWorker]->[asyncio.Queue])
    """

    def __init__(self, queue: asyncio.Queue, config: dict) -> None:
        super().__init__(queue, config)
        self._logger.info("CoT_URL Dest: %s", self.config.get("COT_URL"))

    async def put_queue(self, data: bytes) -> None:
        """Put Data onto the Queue."""
        try:
            await self.queue.put(data)
        except asyncio.QueueFull:
            self._logger.warning("Lost Data (queue full): '%s'", data)


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
        config: ConfigParser,
        tx_queue: Union[asyncio.Queue, mp.Queue, None] = None,
        rx_queue: Union[asyncio.Queue, mp.Queue, None] = None,
    ) -> None:
        """Initialize CLITool instance."""
        self.tasks: Set = set()
        self.running_tasks: Set = set()

        self.config = config
        self.tx_queue: Union[asyncio.Queue, mp.Queue] = tx_queue or asyncio.Queue()
        self.rx_queue: Union[asyncio.Queue, mp.Queue] = rx_queue or asyncio.Queue()

        if self.config.getboolean("DEBUG", False):
            for handler in self._logger.handlers:
                handler.setLevel(logging.DEBUG)

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

    def run_tasks(self, tasks=None):
        """Run the given list or set of couroutine tasks."""
        tasks = tasks or self.tasks
        for task in tasks:
            self.run_task(task)

    async def run(self):
        """Run this Thread and its associated coroutine tasks."""
        self._logger.info("Run: %s", self.__class__)

        await self.hello_event()
        self.run_tasks()

        done, _ = await asyncio.wait(
            self.running_tasks, return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            self._logger.info("Complete: %s", task)
