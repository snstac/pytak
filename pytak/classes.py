#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python Team Awareness Kit (PyTAK) Module Class Definitions."""

import logging
import os
import queue
import random
import socket
import threading
import time

import pytak

__author__ = 'Greg Albrecht W2GMD <oss@undef.net>'
__copyright__ = 'Copyright 2020 Orion Labs, Inc.'
__license__ = 'Apache License, Version 2.0'


# Dear Reader, Py3 doesn't need to inherit from Object anymore!
class NetworkClient:
    """CoT Network Client (TX)."""

    _logger = logging.getLogger(__name__)
    if not _logger.handlers:
        _logger.setLevel(pytak.LOG_LEVEL)
        _console_handler = logging.StreamHandler()
        _console_handler.setLevel(pytak.LOG_LEVEL)
        _console_handler.setFormatter(pytak.LOG_FORMAT)
        _logger.addHandler(_console_handler)
        _logger.propagate = False

    def __init__(self, cot_host: str, cot_port: int = None,
                 broadcast: bool = False) -> None:
        self.broadcast = broadcast

        self.socket: socket.socket = None
        self.addr: str = None
        self.port: int = None

        if ':' in cot_host:
            self.addr, port = cot_host.split(':')
            self.port = int(port)
        elif cot_port:
            self.addr = cot_host
            self.port = int(cot_port)
        else:
            self.addr = cot_host
            self.port = int(pytak.DEFAULT_COT_PORT)

        self.socket_addr = f'{self.addr}:{self.port}'

        if self.broadcast:
            self._logger.info(
                'Using Broadcast Socket, CoT Destination: %s',
                self.socket_addr)
            self._setup_broadcast_socket()
        else:
            self._logger.info(
                'Using Unicast Socket, CoT Destination: %s',
                self.socket_addr)
            self._setup_unicast_socket()

    def _setup_unicast_socket(self) -> None:
        """Sets up the TCP Unicast Socket for sending CoT events."""
        self._logger.debug(
            'Setting up Unicast Socket to CoT Destination: %s',
            self.socket_addr)
        if self.socket is not None:
            self.socket.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.addr, self.port))

    def _setup_broadcast_socket(self) -> None:
        """Sets up the UDP Broadcast Socket for sending CoT events."""
        self._logger.debug(
            'Setting up Broadcast Socket to CoT Destination: %s',
            self.socket_addr)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send_cot(self, event: bytes, timeout: int = 10) -> bool:
        """Wrapper for sending TCP Unicast or UDP Broadcast CoT Events."""
        if os.environ.get('DONT_ADD_NEWLINE'):
            _event = event
        else:
            _event = event + b'\n'

        self._logger.debug('Sending CoT to %s: "%s"', self.socket_addr, _event)

        if self.broadcast:  # pylint: disable=no-else-return
            return self.sendto(_event)
        else:
            return self.sendall(_event, timeout)

    def close(self):
        """Closes this instance's network socket."""
        return self.socket.close()

    def sendall(self, event: bytes, timeout: int = 10) -> bool:
        """Sends a CoT Event to a TCP Unicast address."""
        # is the socket alive?
        if self.socket.fileno() is -1:
            self._logger.warning(
                'Restarting Socket as socket.fileno() returned -1')
            self._setup_unicast_socket()
            return False

        self.socket.settimeout(timeout)

        try:
            self.socket.sendall(event)
            if not os.environ.get('DISABLE_RANDOM_SLEEP'):
                time.sleep(random.random())
            return True
        except Exception as exc:
            self._logger.error(
                'socket.sendall() raised an Exception, sleeping: ')
            self._logger.exception(exc)
            time.sleep(pytak.DEFAULT_BACKOFF * random.random())
            self._setup_unicast_socket()
            return False

    def sendto(self, event: bytes) -> bool:
        """Sends a CoT Event to a UDP Broadcast address."""
        try:
            self.socket.sendto(event, (self.addr, self.port))
            return True
        except Exception as exc:
            self._logger.error(
                'socket.sendto() raised an Exception, sleeping: ')
            self._logger.exception(exc)
            time.sleep(pytak.DEFAULT_BACKOFF * random.random())
            self._setup_broadcast_socket()
            return False


class CoTWorker(threading.Thread):

    """CoTWorker Thread."""

    _logger = logging.getLogger(__name__)
    if not _logger.handlers:
        _logger.setLevel(pytak.LOG_LEVEL)
        _console_handler = logging.StreamHandler()
        _console_handler.setLevel(pytak.LOG_LEVEL)
        _console_handler.setFormatter(pytak.LOG_FORMAT)
        _logger.addHandler(_console_handler)
        _logger.propagate = False

    def __init__(self, msg_queue: queue.Queue, cot_host: str,
                 cot_port: int = None, broadcast: bool = False) -> None:
        self.msg_queue: queue.Queue = msg_queue

        self.net_client = NetworkClient(
            cot_host=cot_host,
            cot_port=cot_port,
            broadcast=broadcast
        )

        # Thread setup:
        threading.Thread.__init__(self)
        self.daemon = True
        self._stopper = threading.Event()

    def stop(self):
        """Stop the thread at the next opportunity."""
        self._logger.debug('Stopping CoTWorker')
        self.net_client.close()
        self._stopper.set()

    def stopped(self):
        """Checks if the thread is stopped."""
        return self._stopper.isSet()

    def run(self):
        """Runs this Thread, reads in Message Queue & sends out CoT."""
        self._logger.info('Running CoTWorker')

        while not self.stopped():
            try:
                msg = self.msg_queue.get(True, 1)
                self._logger.debug('From msg_queue: "%s"', msg)
                if not msg:
                    continue
                self.net_client.send_cot(msg)
            except queue.Empty:
                pass
