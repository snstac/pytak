#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for building CoT in any form and sending/receiving it in either TAK
Protocol version (#49, #88): cot2wire(), wire2cot(), and PYTAK_RX_FORMAT."""

import asyncio
import contextlib
import logging
import xml.etree.ElementTree as ET
from unittest import mock

import pytest

takproto = pytest.importorskip("takproto")

from takproto.functions import msg2proto, xml2message  # noqa: E402
from takproto.proto import TakMessage  # noqa: E402
from google.protobuf import json_format  # noqa: E402

import pytak  # noqa: E402
from pytak.classes import (  # noqa: E402
    MQTTRXWorker,
    MQTTTXWorker,
    RXWorker,
    TXWorker,
    WSRXWorker,
    WSTXWorker,
    _CoTEventTooLargeError,
    _MQTTSession,
)

COT = (
    b'<event version="2.0" uid="FMT-1" type="a-f-G-U-C" how="m-g" '
    b'time="2024-01-01T00:00:00.000Z" start="2024-01-01T00:00:00.000Z" '
    b'stale="2024-01-01T00:05:00.000Z">'
    b'<point lat="47.6062" lon="-122.3321" hae="12.5" ce="9.0" le="9.0"/>'
    b'<detail><contact callsign="FMT"/><remarks>hello</remarks></detail>'
    b"</event>"
)
COT2 = COT.replace(b"FMT-1", b"FMT-2")


def _msg(xml=COT) -> TakMessage:
    return xml2message(xml)


def _stream(xml=COT) -> bytes:
    return bytes(msg2proto(_msg(xml), takproto.TAKProtoVer.STREAM))


def _mesh(xml=COT) -> bytes:
    return bytes(msg2proto(_msg(xml), takproto.TAKProtoVer.MESH))


def _uid(xml: bytes) -> str:
    return ET.fromstring(xml).get("uid")


class _Writer:
    def __init__(self):
        self.sent = []

    def write(self, data):
        self.sent.append(bytes(data))

    async def drain(self):
        return None


def _reader(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


@contextlib.contextmanager
def _capture(caplog, level=logging.WARNING):
    """pytak loggers do not propagate, so attach caplog's handler directly."""
    logger = pytak.classes.Worker._logger
    logger.addHandler(caplog.handler)
    try:
        yield
    finally:
        logger.removeHandler(caplog.handler)


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


# ---------------------------------------------------------------------------
# cot2wire()
# ---------------------------------------------------------------------------


def test_cot2wire_xml_bytes_unchanged_for_tak_proto_0():
    assert pytak.cot2wire(COT, 0) is COT


def test_cot2wire_protobuf_bytes_unchanged_for_tak_proto_0():
    """Pre-encoded bytes keep being sent as-is with TAK_PROTO=0."""
    assert pytak.cot2wire(_stream(), 0) == _stream()


def test_cot2wire_str_and_element_to_xml():
    assert pytak.cot2wire(COT.decode(), 0) == COT
    out = pytak.cot2wire(ET.fromstring(COT), 0)
    assert isinstance(out, bytes)
    assert _uid(out) == "FMT-1"


def test_cot2wire_xml_to_stream_and_mesh():
    assert bytes(pytak.cot2wire(COT, 1)) == _stream()
    assert bytes(pytak.cot2wire(COT, 1, mesh=True)) == _mesh()


def test_cot2wire_element_to_protobuf():
    assert bytes(pytak.cot2wire(ET.fromstring(COT), 1)) == _stream()


def test_cot2wire_takmessage_to_xml():
    out = pytak.cot2wire(_msg(), 0)
    event = ET.fromstring(out)
    assert event.get("uid") == "FMT-1"
    assert event.get("type") == "a-f-G-U-C"
    assert event.find("point").get("lat") == "47.6062"
    assert event.find("detail/contact").get("callsign") == "FMT"
    assert event.find("detail/remarks").text == "hello"


def test_cot2wire_takmessage_to_stream_and_mesh():
    assert bytes(pytak.cot2wire(_msg(), 1)) == _stream()
    assert bytes(pytak.cot2wire(_msg(), 1, mesh=True)) == _mesh()


def test_cot2wire_dict_round_trip():
    as_dict = json_format.MessageToDict(_msg())
    assert bytes(pytak.cot2wire(as_dict, 1)) == _stream()
    assert _uid(pytak.cot2wire(as_dict, 0)) == "FMT-1"


def test_cot2wire_reframes_protobuf_for_transport():
    assert bytes(pytak.cot2wire(_mesh(), 1, mesh=False)) == _stream()
    assert bytes(pytak.cot2wire(_stream(), 1, mesh=True)) == _mesh()
    # Already in the right framing: passed through untouched.
    assert pytak.cot2wire(_stream(), 1) == _stream()
    assert pytak.cot2wire(_mesh(), 1, mesh=True) == _mesh()


def test_cot2wire_takmessage_without_uid_raises():
    with pytest.raises(ValueError):
        pytak.cot2wire(TakMessage(), 0)


def test_cot2wire_requires_takproto_for_protobuf():
    with mock.patch("pytak.classes.takproto", None):
        assert pytak.cot2wire(COT, 0) is COT
        with pytest.raises(ValueError, match="takproto"):
            pytak.cot2wire(COT, 1)
        with pytest.raises(ValueError, match="takproto"):
            pytak.cot2wire({"cotEvent": {"uid": "x"}}, 0)


def test_cot2wire_none():
    assert pytak.cot2wire(None, 1) is None


# ---------------------------------------------------------------------------
# wire2cot()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wire", [COT, b"\n  " + COT, _stream(), _mesh()])
def test_wire2cot_xml(wire):
    out = pytak.wire2cot(wire, "xml")
    assert _uid(out.strip()) == "FMT-1"


def test_wire2cot_xml_leaves_xml_untouched():
    assert pytak.wire2cot(COT, "xml") is COT


@pytest.mark.parametrize("wire", [COT, b"\n" + COT, _stream(), _mesh(), _msg()])
def test_wire2cot_proto(wire):
    out = pytak.wire2cot(wire, "proto")
    assert isinstance(out, TakMessage)
    assert out.cotEvent.uid == "FMT-1"
    assert out.cotEvent.detail.contact.callsign == "FMT"


def test_wire2cot_dict():
    out = pytak.wire2cot(_mesh(), "dict")
    assert out["cotEvent"]["uid"] == "FMT-1"
    assert out["cotEvent"]["lat"] == pytest.approx(47.6062)


def test_wire2cot_raw_and_bad_format():
    assert pytak.wire2cot(_mesh(), "raw") == _mesh()
    with pytest.raises(ValueError):
        pytak.wire2cot(COT, "json")


def test_wire2cot_malformed_xml_for_proto_raises():
    with pytest.raises(ET.ParseError):
        pytak.wire2cot(b"<event uid='x'", "proto")


# ---------------------------------------------------------------------------
# TXWorker: any CoT object on the TX queue, serialized for TAK_PROTO
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_txworker_takmessage_sent_as_xml_with_tak_proto_0():
    writer = _Writer()
    worker = TXWorker(asyncio.Queue(), {"TAK_PROTO": "0"}, writer)
    await worker.send_data(_msg())
    assert len(writer.sent) == 1
    assert _uid(writer.sent[0]) == "FMT-1"


@pytest.mark.asyncio
async def test_txworker_xml_bytes_unchanged_with_tak_proto_0():
    writer = _Writer()
    worker = TXWorker(asyncio.Queue(), {"TAK_PROTO": "0"}, writer)
    await worker.send_data(COT)
    assert writer.sent == [COT]


@pytest.mark.asyncio
async def test_txworker_element_and_dict_sent_as_stream_protobuf():
    writer = _Writer()
    config = {"TAK_PROTO": "1", "COT_URL": "tcp://takserver.example.com:8087"}
    worker = TXWorker(asyncio.Queue(), config, writer)
    await worker.send_data(ET.fromstring(COT))
    await worker.send_data(json_format.MessageToDict(_msg()))
    assert writer.sent == [_stream(), _stream()]


@pytest.mark.asyncio
async def test_txworker_multicast_uses_mesh_framing_for_takmessage():
    writer = _Writer()
    config = {"TAK_PROTO": "1", "COT_URL": "udp://239.2.3.1:6969"}
    worker = TXWorker(asyncio.Queue(), config, writer)
    await worker.send_data(_msg())
    await worker.send_data(_stream())  # re-framed for multicast
    assert writer.sent == [_mesh(), _mesh()]


@pytest.mark.asyncio
async def test_txworker_drops_unserializable_object(caplog):
    writer = _Writer()
    worker = TXWorker(asyncio.Queue(), {"TAK_PROTO": "1"}, writer)
    with _capture(caplog):
        await worker.send_data({"cotEvent": {"no_such_field": 1}})
    assert writer.sent == []
    assert "dropping" in caplog.text


@pytest.mark.asyncio
async def test_txworker_bad_xml_still_sent_raw(caplog):
    writer = _Writer()
    worker = TXWorker(asyncio.Queue(), {"TAK_PROTO": "1"}, writer)
    with _capture(caplog):
        await worker.send_data(b"not xml")
    assert writer.sent == [b"not xml"]
    assert "sending raw" in caplog.text


# ---------------------------------------------------------------------------
# RXWorker: PYTAK_RX_FORMAT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rx_format_defaults_to_raw():
    worker = RXWorker(asyncio.Queue(), {}, _reader(COT))
    assert worker.rx_format == "raw"
    assert await worker.readcot() == COT


@pytest.mark.asyncio
async def test_rx_format_invalid_falls_back_to_raw(caplog):
    with _capture(caplog):
        worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "json"}, None)
    assert worker.rx_format == "raw"
    assert "PYTAK_RX_FORMAT" in caplog.text


def test_rx_format_without_takproto_falls_back_to_raw():
    with mock.patch("pytak.classes.takproto", None):
        worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "xml"}, None)
    assert worker.rx_format == "raw"


@pytest.mark.asyncio
async def test_rx_stream_mixed_xml_and_protobuf_as_xml():
    """A TCP stream carrying XML and TAK Protocol v1 Stream messages."""
    wire = COT + b"\n" + _stream(COT2) + COT
    worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "xml"}, _reader(wire))
    got = [await worker.readcot() for _ in range(3)]
    assert [_uid(x.strip()) for x in got] == ["FMT-1", "FMT-2", "FMT-1"]
    assert got[0] == COT


@pytest.mark.asyncio
async def test_rx_stream_mixed_as_proto():
    wire = _stream() + COT2
    worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "proto"}, _reader(wire))
    first = await worker.readcot()
    second = await worker.readcot()
    assert isinstance(first, TakMessage) and isinstance(second, TakMessage)
    assert [first.cotEvent.uid, second.cotEvent.uid] == ["FMT-1", "FMT-2"]


@pytest.mark.asyncio
async def test_rx_stream_multibyte_varint_length():
    big = COT.replace(b"hello", b"x" * 400)
    frame = _stream(big)
    assert frame[2] & 0x80 == 0 and frame[1] & 0x80  # length needs 2 bytes
    worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "proto"}, _reader(frame))
    msg = await worker.readcot()
    assert msg.cotEvent.detail.xmlDetail.count("x") >= 400


@pytest.mark.asyncio
async def test_rx_stream_oversized_length_raises():
    # 0xbf, then varint 2**40.
    wire = b"\xbf" + b"\x80\x80\x80\x80\x80\x20"
    worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "xml"}, _reader(wire))
    with pytest.raises(_CoTEventTooLargeError):
        await worker.readcot()


@pytest.mark.asyncio
async def test_rx_stream_truncated_protobuf_is_connection_reset():
    wire = _stream()[:-5]
    worker = RXWorker(asyncio.Queue(), {"PYTAK_RX_FORMAT": "xml"}, _reader(wire))
    with pytest.raises(ConnectionResetError):
        await worker.readcot()


@pytest.mark.asyncio
async def test_rx_datagram_mesh_decoded_with_tak_proto_0():
    """ATAK mixes v0 and v1 on multicast; decode both into one format."""
    reader = mock.MagicMock(spec=["recv"])
    reader.recv = mock.MagicMock()
    datagrams = [(_mesh(), None), (COT2, None)]
    reader.recv.side_effect = [_AsyncReturn(d)() for d in datagrams]
    config = {"TAK_PROTO": "0", "PYTAK_RX_FORMAT": "xml"}
    worker = RXWorker(asyncio.Queue(), config, reader)
    assert _uid(await worker.readcot()) == "FMT-1"
    assert await worker.readcot() == COT2


@pytest.mark.asyncio
async def test_rx_datagram_raw_mode_unchanged_with_tak_proto_0():
    reader = mock.MagicMock(spec=["recv"])
    reader.recv = _AsyncReturn((_mesh(), None))
    worker = RXWorker(asyncio.Queue(), {"TAK_PROTO": "0"}, reader)
    assert await worker.readcot() == _mesh()


@pytest.mark.asyncio
async def test_rx_undecodable_message_dropped(caplog):
    reader = mock.MagicMock(spec=["recv"])
    reader.recv = _AsyncReturn((b"\xbf\x01\xbf\xff\xff", None))
    queue = asyncio.Queue()
    worker = RXWorker(queue, {"PYTAK_RX_FORMAT": "xml"}, reader)
    with _capture(caplog):
        await worker.run_once()
    assert queue.empty()
    assert "dropping" in caplog.text


@pytest.mark.asyncio
async def test_rx_run_once_enqueues_dict():
    queue = asyncio.Queue()
    worker = RXWorker(queue, {"PYTAK_RX_FORMAT": "dict"}, _reader(_stream()))
    await worker.run_once()
    assert (await queue.get())["cotEvent"]["uid"] == "FMT-1"


# ---------------------------------------------------------------------------
# WebSocket and MQTT workers
# ---------------------------------------------------------------------------


def _ws_msg(data):
    msg = mock.MagicMock()
    msg.type = "BINARY"
    msg.data = data
    return msg


def _mock_aiohttp():
    mock_aiohttp = mock.MagicMock()
    mock_aiohttp.WSMsgType.BINARY = "BINARY"
    mock_aiohttp.WSMsgType.CLOSE = "CLOSE"
    mock_aiohttp.WSMsgType.CLOSED = "CLOSED"
    mock_aiohttp.WSMsgType.ERROR = "ERROR"
    return mock_aiohttp


@pytest.mark.asyncio
async def test_ws_tx_sends_takmessage_as_stream():
    ws = mock.MagicMock()
    sent = []

    async def send_bytes(data):
        sent.append(bytes(data))

    ws.send_bytes = send_bytes
    worker = WSTXWorker(asyncio.Queue(), {}, ws)
    await worker.handle_data(_msg())
    await worker.handle_data(_stream())  # already encoded: not double-encoded
    assert sent == [_stream(), _stream()]


@pytest.mark.asyncio
async def test_ws_rx_format_proto():
    ws = mock.MagicMock()
    ws.receive = _AsyncReturn(_ws_msg(_stream()))
    queue = asyncio.Queue()
    worker = WSRXWorker(queue, {"PYTAK_RX_FORMAT": "proto"}, ws)
    with mock.patch("pytak.classes._aiohttp", _mock_aiohttp()):
        await worker.run_once()
    assert (await queue.get()).cotEvent.uid == "FMT-1"


@pytest.mark.asyncio
async def test_mqtt_tx_takmessage_as_xml_and_rx_dict_with_tak_proto_0():
    client = mock.MagicMock()
    published = []

    async def publish(topic, data, qos=0):
        published.append(data)

    client.publish = publish
    tx = MQTTTXWorker(asyncio.Queue(), {}, client, "cot", 0, _MQTTSession(client))
    await tx.handle_data(_msg())
    assert _uid(published[0]) == "FMT-1"

    message = mock.MagicMock()
    message.payload = _stream()
    message_iter = mock.MagicMock()
    message_iter.__anext__ = _AsyncReturn(message)
    client.messages = mock.MagicMock()
    client.messages.__aiter__ = mock.MagicMock(return_value=message_iter)
    queue = asyncio.Queue()
    rx = MQTTRXWorker(queue, {"PYTAK_RX_FORMAT": "dict"}, client, _MQTTSession(client))
    await rx.run_once()
    assert (await queue.get())["cotEvent"]["uid"] == "FMT-1"


# ---------------------------------------------------------------------------
# End to end over a real TCP socket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_round_trip_takmessage_out_mixed_stream_in():
    """Client sends a TakMessage with TAK_PROTO=1; the server answers with a
    mix of XML and TAK Protocol v1 Stream messages, received as TakMessages."""
    received = asyncio.get_running_loop().create_future()

    async def server(reader, writer):
        received.set_result(await reader.readexactly(len(_stream())))
        writer.write(COT2 + b"\n" + _stream() + b"\n")
        await writer.drain()
        writer.close()

    srv = await asyncio.start_server(server, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    config = {
        "COT_URL": f"tcp://127.0.0.1:{port}",
        "TAK_PROTO": "1",
        "PYTAK_RX_FORMAT": "proto",
    }
    try:
        reader, writer = await pytak.protocol_factory(config)
        tx = TXWorker(asyncio.Queue(), config, writer)
        rx = RXWorker(asyncio.Queue(), config, reader)
        await tx.send_data(_msg())
        assert await asyncio.wait_for(received, 5) == _stream()
        first = await asyncio.wait_for(rx.readcot(), 5)
        second = await asyncio.wait_for(rx.readcot(), 5)
        assert [first.cotEvent.uid, second.cotEvent.uid] == ["FMT-2", "FMT-1"]
        writer.close()
    finally:
        srv.close()
