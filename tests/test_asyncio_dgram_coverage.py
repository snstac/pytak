#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Coverage tests for the bundled pytak.asyncio_dgram (loopback sockets only)."""

import asyncio
import socket
import sys
from unittest import mock

import pytest

from pytak import asyncio_dgram

LOOPBACK = ("127.0.0.1", 0)


@pytest.mark.asyncio
async def test_bind_connect_roundtrip():
    server = await asyncio_dgram.bind(LOOPBACK)
    client = await asyncio_dgram.connect(server.sockname)
    try:
        assert isinstance(server, asyncio_dgram.DatagramServer)
        assert isinstance(client, asyncio_dgram.DatagramClient)
        assert server.peername is None
        assert client.peername == server.sockname
        assert server.socket is not None
        assert client.exception is None

        await client.send(b"ping")
        data, addr = await asyncio.wait_for(server.recv(), 1)
        assert data == b"ping"
        assert addr == client.sockname

        await server.send(b"pong", addr)
        data, addr = await asyncio.wait_for(client.recv(), 1)
        assert data == b"pong"
        assert addr == server.sockname
    finally:
        client.close()
        server.close()


@pytest.mark.asyncio
async def test_send_and_recv_after_close_raise_transport_closed():
    server = await asyncio_dgram.bind(LOOPBACK)
    server.close()
    with pytest.raises(asyncio_dgram.TransportClosed):
        await server.send(b"x", ("127.0.0.1", 9))
    with pytest.raises(asyncio_dgram.TransportClosed):
        await server.recv()


@pytest.mark.asyncio
async def test_recv_pending_raises_when_connection_lost():
    server = await asyncio_dgram.bind(LOOPBACK)
    pending = asyncio.ensure_future(server.recv())
    await asyncio.sleep(0)
    server.close()
    with pytest.raises(asyncio_dgram.TransportClosed):
        await asyncio.wait_for(pending, 1)


@pytest.mark.asyncio
async def test_exception_property_raises_queued_error():
    server = await asyncio_dgram.bind(LOOPBACK)
    try:
        server._excq.put_nowait(OSError("queued"))
        with pytest.raises(OSError, match="queued"):
            _ = server.exception
        assert server.exception is None
    finally:
        server.close()


@pytest.mark.asyncio
async def test_bind_and_connect_unix_path(tmp_path):
    if sys.platform == "win32" or not hasattr(socket, "AF_UNIX"):
        pytest.skip("AF_UNIX datagram sockets unavailable")
    path = tmp_path / "s.sock"
    server = await asyncio_dgram.bind(path)
    client = await asyncio_dgram.connect(path)
    try:
        await client.send(b"unix")
        data, _ = await asyncio.wait_for(server.recv(), 1)
        assert data == b"unix"
        assert server.socket.family == socket.AF_UNIX
    finally:
        client.close()
        server.close()


@pytest.mark.asyncio
async def test_from_socket_unconnected_and_connected():
    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv_sock.bind(LOOPBACK)
    server = await asyncio_dgram.from_socket(srv_sock)
    assert isinstance(server, asyncio_dgram.DatagramServer)

    cli_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cli_sock.connect(server.sockname)
    client = await asyncio_dgram.from_socket(cli_sock)
    try:
        assert isinstance(client, asyncio_dgram.DatagramClient)
        await client.send(b"fs")
        data, _ = await asyncio.wait_for(server.recv(), 1)
        assert data == b"fs"
    finally:
        client.close()
        server.close()


@pytest.mark.asyncio
async def test_from_socket_rejects_bad_type_and_family():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(TypeError, match="socket type"):
            await asyncio_dgram.from_socket(tcp)
    finally:
        tcp.close()

    fake = mock.MagicMock()
    fake.family = -1
    with pytest.raises(TypeError, match="socket family"):
        await asyncio_dgram.from_socket(fake)


def test_del_ignores_runtime_error_from_closed_loop():
    transport = mock.MagicMock()
    transport.close.side_effect = RuntimeError("Event loop is closed")
    stream = asyncio_dgram.DatagramStream(transport, None, None, None)
    stream.__del__()  # must not raise
    assert transport.close.called


def test_sockname_and_peername_empty_string_is_none():
    transport = mock.MagicMock()
    transport.get_extra_info.return_value = ""
    stream = asyncio_dgram.DatagramStream(transport, None, None, None)
    assert stream.sockname is None
    assert stream.peername is None


# ---------------------------------------------------------------------------
# Protocol callbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protocol_callbacks():
    recvq, excq, drained = asyncio.Queue(), asyncio.Queue(), asyncio.Event()
    proto = asyncio_dgram.Protocol(recvq, excq, drained)
    assert drained.is_set()

    transport = mock.MagicMock()
    proto.connection_made(transport)
    proto.datagram_received(b"d", ("127.0.0.1", 1))
    assert recvq.get_nowait() == (b"d", ("127.0.0.1", 1))

    err = OSError("icmp")
    proto.error_received(err)
    assert excq.get_nowait() is err

    proto.pause_writing()
    assert not drained.is_set()
    proto.resume_writing()
    assert drained.is_set()

    lost = ConnectionResetError("gone")
    proto.connection_lost(lost)
    assert excq.get_nowait() is lost
    assert recvq.get_nowait() == (None, None)
    assert transport.close.called
    assert proto._transport is None

    # A second connection_lost with no transport and no error is harmless.
    proto.connection_lost(None)
    assert recvq.get_nowait() == (None, None)
    assert excq.empty()


# ---------------------------------------------------------------------------
# DatagramFanoutClient
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, exc=None):
        self.exc = exc
        self.sent = []
        self.closed = False

    async def send(self, data):
        if self.exc is not None:
            raise self.exc
        self.sent.append(data)

    def close(self):
        self.closed = True


def test_fanout_requires_clients():
    with pytest.raises(ValueError):
        asyncio_dgram.DatagramFanoutClient([])


@pytest.mark.asyncio
async def test_fanout_drops_failed_clients_and_keeps_healthy():
    good, bad = _FakeClient(), _FakeClient(OSError("down"))
    fan = asyncio_dgram.DatagramFanoutClient([good, bad])
    await fan.send(b"x")
    assert good.sent == [b"x"]
    assert bad.closed
    assert fan.clients == (good,)


@pytest.mark.asyncio
async def test_fanout_all_failed_raises_first_failure():
    fan = asyncio_dgram.DatagramFanoutClient([_FakeClient(OSError("a"))])
    with pytest.raises(OSError, match="a"):
        await fan.send(b"x")
    with pytest.raises(asyncio_dgram.TransportClosed):
        await fan.send(b"y")


@pytest.mark.asyncio
async def test_fanout_propagates_cancellation():
    fan = asyncio_dgram.DatagramFanoutClient([_FakeClient(asyncio.CancelledError())])
    with pytest.raises(asyncio.CancelledError):
        await fan.send(b"x")


def test_fanout_close_closes_all():
    a, b = _FakeClient(), _FakeClient()
    fan = asyncio_dgram.DatagramFanoutClient([a, b])
    fan.close()
    assert a.closed and b.closed
    assert fan.clients == ()


@pytest.mark.asyncio
async def test_fanout_over_real_loopback_clients():
    server = await asyncio_dgram.bind(LOOPBACK)
    c1 = await asyncio_dgram.connect(server.sockname)
    c2 = await asyncio_dgram.connect(server.sockname)
    fan = asyncio_dgram.DatagramFanoutClient([c1, c2])
    try:
        await fan.send(b"fan")
        got = {(await asyncio.wait_for(server.recv(), 1))[1] for _ in range(2)}
        assert got == {c1.sockname, c2.sockname}
    finally:
        fan.close()
        server.close()
