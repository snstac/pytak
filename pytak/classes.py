#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2022 Greg Albrecht <oss@undef.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author:: Greg Albrecht W2GMD <oss@undef.net>
# Copyright:: Copyright 2022 Greg Albrecht
# License:: Apache License, Version 2.0
#

"""PyTAK Class Definitions."""

import asyncio
import configparser
import logging
import queue
import random

from urllib.parse import ParseResult, urlparse

import pytak

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2022 Greg Albrecht"
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

    def __init__(self, event_queue: asyncio.Queue, config: dict=None) -> None:
        self.event_queue: asyncio.Queue = event_queue
        if config:
            self.config = config
        else:
            config_p = configparser.ConfigParser({})
            config_p.add_section("pytak")
            self.config = config_p["pytak"]

    async def fts_compat(self) -> None:
        """
        If FTS_COMPAT or PYTAK_SLEEP are set, sleeps for a given or random time.
        """
        pytak_sleep: int = self.config.get("PYTAK_SLEEP", 0)
        if self.config.getboolean("FTS_COMPAT") or pytak_sleep:
            sleep_period: int = int(pytak_sleep or (pytak.DEFAULT_SLEEP * random.random())
            )
            self._logger.debug("COMPAT: Sleeping for %ss", sleep_period)
            await asyncio.sleep(sleep_period)

    async def handle_event(self, event: str) -> None:
        """Placeholder handle_event Method for this Class."""
        self._logger.warning("Overwrite this method!")

    async def run(self, number_of_iterations=-1):
        """
        Runs EventWorker Thread, reads in CoT Event Queue & passes COT Events
        to COT Event Handler.
        """
        self._logger.info("Running EventWorker")

        # We're instantiating the while loop this way, and using get_nowait(),
        # to allow unit testing of at least one call of this loop.
        while number_of_iterations != 0:
            event = await self.event_queue.get()
            if not event:
                continue
            await self.handle_event(event)
            await self.fts_compat()
            number_of_iterations -= 1


class EventWorker(Worker):  # pylint: disable=too-few-public-methods
    """
    EventWorker handles getting Cursor on Target Events from a queue, and
    passing them off to a Transport Worker.

    You should create an EventWorker Instance using the
    `pytak.eventworker_factory` Function.

    CoT Events are put onto the CoT Event Queue using `pytak.MessageWorker`
    Class.
    """

    def __init__(self, event_queue: asyncio.Queue, config: dict, writer: asyncio.Protocol) -> None:
        super().__init__(event_queue, config)
        self.writer: asyncio.Protocol = writer

    async def handle_event(self, event: str) -> None:
        """
        COT Event Handler, accepts COT Events from the COT Event Queue and
        processes them for writing.
        """
        self._logger.debug("COT Event Handler event='%s'", event)
        await self.send_event(event)

    async def send_event(self, event) -> None:
        """Sends an event with the appropriate 'tx' method."""
        if hasattr(self.writer, "send"):
            await self.writer.send(event)
        else:
            self.writer.write(event)
            if hasattr(self.writer, "drain"):
                await self.writer.drain()
            if hasattr(self.writer, "flush"):
                self.writer.flush()


class MessageWorker(Worker):  # pylint: disable=too-few-public-methods
    """
    Reads/gets Messages (!COT) from an `asyncio.Protocol` or similar async
    network client, serializes it as COT, and puts it onto an `asyncio.Queue`.

    Implementations should handle serializing Messages as COT Events, and
    putting them onto the `event_queue`.

    The `event_queue` is handled by the `pytak.EventWorker` Class.

    pytak([asyncio.Protocol]->[pytak.MessageWorker]->[asyncio.Queue])
    """

    def __init__(self, event_queue: asyncio.Queue, config: dict) -> None:
        super().__init__(event_queue, config)

    async def _put_event_queue(self, event: str) -> None:
        """Puts Event onto the COT Event Queue."""
        try:
            await self.event_queue.put(event)
        except queue.Full:
            self._logger.warning("Lost COT Event (queue full): '%s'", event)


class EventReceiver(Worker):  # pylint: disable=too-few-public-methods
    """
    Async receive (input) queue worker. Reads events from a
    `pytak.protocol_factory` reader and adds them to an `rx_queue`.

    Most implementations use this to drain an RX buffer on a socket.

    pytak([asyncio.Protocol]->[pytak.EventReceiver]->[queue.Queue])
    """

    def __init__(self, rx_queue: asyncio.Queue, config: dict, reader: asyncio.Protocol) -> None:
        super().__init__(rx_queue, config)
        self.reader: asyncio.Protocol = reader

    async def run(self) -> None:
        self._logger.info("Running EventReceiver")

        while 1:
            rx_event = await self.event_queue.get()
            self._logger.debug("rx_event='%s'", rx_event)


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

    def __init__(self, config):
        self.tasks = set()
        self.running_tasks = set()
        self.tx_queue: asyncio.Queue = asyncio.Queue()
        self.rx_queue: asyncio.Queue = asyncio.Queue()
        self.config = config

    async def setup(self):
        # Create our COT Event Queue Worker
        reader, writer = await pytak.protocol_factory(self.config)
        write_worker = pytak.EventWorker(self.tx_queue, self.config, writer)
        read_worker = pytak.EventReceiver(self.rx_queue, self.config, reader)
        self.add_task(write_worker)
        self.add_task(read_worker)

    async def hello_event(self):
        await self.tx_queue.put(pytak.hello_event(self.config.get("COT_HOST_ID")))

    def add_task(self, task):
        self._logger.debug("Adding Task: %s", task)
        self.tasks.add(task)

    def add_tasks(self, tasks):
        for task in tasks:
            self.add_task(task)

    def run_task(self, task):
        self._logger.debug("Running Task: %s", task)
        self.running_tasks.add(asyncio.ensure_future(task.run()))

    def run_tasks(self, tasks=None):
        tasks = tasks or self.tasks
        for task in tasks:
            self.run_task(task)

    async def run(self):
        self._logger.info("Running CLITool")
        await self.hello_event()
        self.run_tasks()
        done, _ = await asyncio.wait(
            self.running_tasks, return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            self._logger.info(f"Completed Task: {task}")
