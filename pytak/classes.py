#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Class Definitions."""

import asyncio
import logging
import os
import queue
import random
import urllib

import pycot

import pytak

__author__ = "Greg Albrecht W2GMD <oss@undef.net>"
__copyright__ = "Copyright 2020 Orion Labs, Inc."
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

    async def run(self) -> None:
        """Placeholder Run Method for this Class."""
        self._logger.warning("Overwrite this method!")


class EventWorker(Worker):  # pylint: disable=too-few-public-methods

    """
    EventWorker handles getting Cursor on Target Events from a queue, and
    passing them off to a transport worker.

    You should create an EventWorker Instance using the
    `pytak.eventworker_factory` Function.

    CoT Events are put onto the CoT Event Queue using `pytak.MessageWorker`
    Class.
    """

    def __init__(self, event_queue: asyncio.Queue, writer) -> None:
        super().__init__(event_queue)
        self.writer = writer

    async def run(self):
        """Runs this Thread, reads in Message Queue & sends out CoT."""
        self._logger.info('Running EventWorker')

        while 1:
            event = await self.event_queue.get()
            if not event:
                continue
            self._logger.debug("event='%s'", event)

            if isinstance(event, pycot.Event):
                _event = event.render(encoding='UTF-8', standalone=True)
            else:
                _event = event

            if hasattr(self.writer, "send"):
                await self.writer.send(_event)
            else:
                self.writer.write(_event)
                await self.writer.drain()

            if not os.environ.get('DISABLE_RANDOM_SLEEP'):
                await asyncio.sleep(pytak.DEFAULT_SLEEP * random.random())


class MessageWorker(Worker):  # pylint: disable=too-few-public-methods

    """
    MessageWorker handles getting non-CoT messages from a non-CoT Input,
    encoding them as CoT, and putting them onto a CoT Event Queue.

    The CoT Event Queue is handled by the `pytak.EventWorker` Class.
    """

    def __init__(self, event_queue: asyncio.Queue,
                 url: urllib.parse.ParseResult, cot_stale: int = None) -> None:
        super().__init__(event_queue)
        self.url = url
        self.cot_stale = cot_stale

    async def _put_event_queue(self, event: pycot.Event) -> None:
        """Puts Event onto the CoT Event Queue."""
        try:
            await self.event_queue.put(event)
        except queue.Full:
            self._logger.warning(
                "Lost CoT Event (queue full): '%s'", event)
