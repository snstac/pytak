#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Class Definitions."""

import asyncio
import logging
import os
import queue
import random
import urllib

import pytak

# Legacy use of pycot
with_pycot = False
try:
    import pycot
    with_pycot = True
except ImportError:
    pass

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2021 Orion Labs, Inc."
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

    def __init__(self, event_queue: asyncio.Queue) -> None:
        self.event_queue: asyncio.Queue = event_queue

    async def fts_compat(self) -> None:
        if os.getenv("FTS_COMPAT") or os.getenv("PYTAK_SLEEP"):
            sleep_period: int = int(os.getenv("PYTAK_SLEEP") or (pytak.DEFAULT_SLEEP * random.random()))
            self._logger.debug("Sleeping for sleep_period=%s Seconds", sleep_period)
            await asyncio.sleep(sleep_period)

    async def handle_event(self, event: str) -> None:
        """Placeholder handle_event Method for this Class."""
        self._logger.warning("Overwrite this method!")

    async def run(self, number_of_iterations=-1):
        """Runs EventWorker Thread, reads in CoT Event Queue & passes CoT Events to CoT Event Handler."""
        self._logger.info("Running EventWorker")

        # We're instantiating the while loop this way, and using get_nowait(), to allow unit testing of at least one
        # call of this loop.
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

    def __init__(self, event_queue: asyncio.Queue, writer) -> None:
        super().__init__(event_queue)
        self.writer = writer

    async def handle_event(self, event: str) -> None:
        """CoT Event Handler, accepts CoT Events from the CoT Event Queue and processes them for writing."""
        self._logger.debug("CoT Event Handler event='%s'", event)

        if with_pycot and isinstance(event, pycot.Event):
            _event = event.render(encoding="UTF-8", standalone=True)
        else:
            _event = event

        if hasattr(self.writer, "send"):
            await self.writer.send(_event)
        else:
            self.writer.write(_event)
            await self.writer.drain()


EventTransmitter = EventWorker


class MessageWorker(Worker):  # pylint: disable=too-few-public-methods

    """
    MessageWorker handles getting non-CoT messages from a non-CoT Input,
    encoding them as CoT, and putting them onto a CoT Event Queue.

    The CoT Event Queue is handled by the `pytak.EventWorker` Class.
    """

    def __init__(self, event_queue: asyncio.Queue,
                 cot_stale: int = None) -> None:
        super().__init__(event_queue)
        self.cot_stale = cot_stale or pytak.DEFAULT_COT_STALE

    async def _put_event_queue(self, event: str) -> None:
        """Puts Event onto the CoT Event Queue."""
        try:
            await self.event_queue.put(event)
        except queue.Full:
            self._logger.warning(
                "Lost CoT Event (queue full): '%s'", event)


class EventReceiver(Worker):  # pylint: disable=too-few-public-methods

    def __init__(self, rx_queue: asyncio.Queue, reader) -> None:
        super().__init__(rx_queue)
        self.reader = reader

    async def run(self):
        self._logger.info("Running EventReceiver")

        while 1:
            rx_event = await self.event_queue.get()
            self._logger.debug("rx_event='%s'", rx_event)
