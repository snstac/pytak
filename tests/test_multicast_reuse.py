#!/usr/bin/env python3
# Copyright Sensors & Signals LLC https://www.snstac.com/
# SPDX-License-Identifier: Apache-2.0
"""Two subscribers to one CoT multicast group must both bind.

Regression test for socket options applied AFTER bind(), which has no effect on
a bind that already happened.

Observed on an AryaOS box (aryaos-ca87): the neighbour-discovery daemon holds
239.2.3.1:6969, so gdltak could not subscribe --

    OSError: [Errno 98] Address already in use
    gdltak.service: Scheduled restart job, restart counter is at 10.
    gdltak.service: Start request repeated too quickly.

-- and the machine ended up in systemd `degraded`. Two subscribers to one CoT
multicast group is a normal arrangement, not an error: the whole point of a
multicast SA feed is that several tools consume it.
"""

import asyncio
import socket
import unittest
from unittest import mock
from urllib.parse import urlparse

import pytak


GROUP = "239.2.3.77"
PORT = 26969


class MulticastReuseTestCase(unittest.TestCase):
    def test_destructor_tolerates_closed_event_loop(self):
        """Best-effort cleanup must not raise after asyncio.run() teardown."""
        transport = mock.Mock()
        transport.close.side_effect = RuntimeError("Event loop is closed")
        stream = pytak.asyncio_dgram.DatagramStream(
            transport, mock.sentinel.recvq, mock.sentinel.excq, mock.sentinel.drained
        )

        stream.__del__()

        transport.close.assert_called_once_with()
        transport.close.side_effect = None

    def test_second_subscriber_can_bind(self):
        """A second reader on the same group/port must not raise EADDRINUSE."""

        async def go():
            first = await pytak.create_udp_client(urlparse(f"udp+ro://{GROUP}:{PORT}"))
            second = (None, None)
            try:
                # This is the call that used to raise OSError(98).
                second = await pytak.create_udp_client(urlparse(f"udp+ro://{GROUP}:{PORT}"))
                for _r, _w in (second,):
                    pass
                self.assertIsNotNone(second)
            finally:
                for pair in (second, first):
                    for sock in pair:
                        if sock is not None and hasattr(sock, "close"):
                            try:
                                sock.close()
                            except Exception:  # noqa: BLE001 - teardown only
                                pass

        asyncio.run(go())

    def test_reuseaddr_is_set_before_bind(self):
        """The option must be observable on the bound socket.

        Setting SO_REUSEADDR after bind() leaves the flag readable as 1 while the
        bind itself was made without it -- so asserting the flag alone would pass
        against the bug. This test binds a plain socket FIRST and then asks pytak
        to bind the same port: only a correctly-ordered implementation succeeds.
        """
        holder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        holder.bind(("", PORT + 1))

        async def go():
            reader, _writer = await pytak.create_udp_client(
                urlparse(f"udp+ro://{GROUP}:{PORT + 1}")
            )
            try:
                return reader is not None
            finally:
                if reader is not None:
                    reader.close()

        try:
            self.assertTrue(asyncio.run(go()))
        finally:
            holder.close()


if __name__ == "__main__":
    unittest.main()
