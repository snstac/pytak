#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Tests for MQTTTXWorker, MQTTRXWorker, mqtt_factory, and parse_mqtt_url."""

import asyncio
from configparser import ConfigParser
from unittest import mock

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(mock.MagicMock):
        def __call__(self, *args, **kwargs):
            super().__call__(*args, **kwargs)
            ret = self.return_value

            async def _coro():
                return ret

            return _coro()

import pytest

import pytak
from pytak.classes import MQTTTXWorker, MQTTRXWorker, _MQTTSession, _make_workers
from pytak.functions import parse_mqtt_url


SAMPLE_COT = (
    b'<?xml version="1.0"?>'
    b'<event version="2.0" uid="MQTT-TEST" type="a-f-G-U-C" '
    b'time="2024-01-01T00:00:00Z" start="2024-01-01T00:00:00Z" '
    b'stale="2024-01-01T00:05:00Z" how="m-g">'
    b'<point lat="37.7749" lon="-122.4194" hae="0" ce="9999999" le="9999999"/>'
    b"</event>"
)

SAMPLE_PROTO_BYTES = b"\xbf\x01\x00"


def _make_message(payload: bytes):
    msg = mock.MagicMock()
    msg.payload = payload
    return msg


# ---------------------------------------------------------------------------
# parse_mqtt_url
# ---------------------------------------------------------------------------


def test_parse_mqtt_url_basic():
    parts = parse_mqtt_url("mqtt://broker.example.com:1883/cot")
    assert parts.host == "broker.example.com"
    assert parts.port == 1883
    assert parts.topic == "cot"
    assert parts.username is None
    assert parts.password is None
    assert parts.use_tls is False


def test_parse_mqtt_url_default_port():
    parts = parse_mqtt_url("mqtt://broker.example.com/cot/events")
    assert parts.port == pytak.DEFAULT_MQTT_PORT
    assert parts.topic == "cot/events"


def test_parse_mqtt_url_mqtts_default_port():
    parts = parse_mqtt_url("mqtts://broker.example.com/secure/cot")
    assert parts.port == pytak.DEFAULT_MQTTS_PORT
    assert parts.use_tls is True
    assert parts.topic == "secure/cot"


def test_parse_mqtt_url_auth():
    parts = parse_mqtt_url("mqtt://user:secret@broker.example.com:1883/cot")
    assert parts.username == "user"
    assert parts.password == "secret"


def test_parse_mqtt_url_wo_scheme():
    parts = parse_mqtt_url("mqtt+wo://broker.example.com:1883/cot/out")
    assert parts.topic == "cot/out"


def test_parse_mqtt_url_empty_topic_raises():
    with pytest.raises(SyntaxError, match="topic"):
        parse_mqtt_url("mqtt://broker.example.com:1883")


def test_parse_mqtt_url_bad_scheme_raises():
    with pytest.raises(SyntaxError, match="mqtt"):
        parse_mqtt_url("tcp://broker.example.com:8087/cot")


def test_parse_cot_scheme_mqtt_wo():
    base, wo, ro = pytak.parse_cot_scheme("mqtt+wo")
    assert base == "mqtt"
    assert wo is True
    assert ro is False


def test_parse_cot_scheme_mqtts_ro():
    base, wo, ro = pytak.parse_cot_scheme("mqtts+ro")
    assert base == "mqtts"
    assert wo is False
    assert ro is True


# ---------------------------------------------------------------------------
# MQTTTXWorker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mqtt_tx_worker_publishes_bytes():
    queue = asyncio.Queue()
    mock_client = mock.MagicMock()
    mock_client.publish = AsyncMock()
    session = _MQTTSession(mock_client)

    worker = MQTTTXWorker(queue, {}, mock_client, "cot", 0, session)

    with mock.patch("pytak.classes.takproto", None):
        await worker.handle_data(SAMPLE_COT)

    mock_client.publish.assert_called_once_with("cot", SAMPLE_COT, qos=0)


@pytest.mark.asyncio
async def test_mqtt_tx_worker_skips_empty():
    queue = asyncio.Queue()
    mock_client = mock.MagicMock()
    mock_client.publish = AsyncMock()
    session = _MQTTSession(mock_client)

    worker = MQTTTXWorker(queue, {}, mock_client, "cot", 0, session)
    await worker.handle_data(b"")
    mock_client.publish.assert_not_called()


@pytest.mark.asyncio
async def test_mqtt_tx_worker_protobuf_when_takproto():
    queue = asyncio.Queue()
    mock_client = mock.MagicMock()
    mock_client.publish = AsyncMock()
    session = _MQTTSession(mock_client)

    mock_takproto = mock.MagicMock()
    mock_takproto.TAKProtoVer.STREAM = "STREAM"
    mock_takproto.xml2proto.return_value = SAMPLE_PROTO_BYTES

    worker = MQTTTXWorker(queue, {"TAK_PROTO": "1"}, mock_client, "cot", 1, session)
    worker.use_protobuf = True

    with mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.handle_data(SAMPLE_COT)

    mock_takproto.xml2proto.assert_called_once()
    mock_client.publish.assert_called_once_with("cot", SAMPLE_PROTO_BYTES, qos=1)


@pytest.mark.asyncio
async def test_mqtt_tx_worker_raises_on_publish_error():
    queue = asyncio.Queue()
    mock_client = mock.MagicMock()
    mock_client.publish = AsyncMock(side_effect=RuntimeError("broker down"))
    session = _MQTTSession(mock_client)

    worker = MQTTTXWorker(queue, {}, mock_client, "cot", 0, session)

    with mock.patch("pytak.classes.takproto", None):
        with pytest.raises(ConnectionError, match="MQTT TX publish failed"):
            await worker.handle_data(SAMPLE_COT)


# ---------------------------------------------------------------------------
# MQTTRXWorker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mqtt_rx_worker_enqueues_raw_bytes():
    queue = asyncio.Queue()
    mock_client = mock.MagicMock()
    message_iter = mock.MagicMock()
    message_iter.__anext__ = AsyncMock(return_value=_make_message(b"<event/>"))
    mock_client.messages = mock.MagicMock()
    mock_client.messages.__aiter__ = mock.MagicMock(return_value=message_iter)
    session = _MQTTSession(mock_client)

    worker = MQTTRXWorker(queue, {}, mock_client, session)
    worker.use_protobuf = False

    await worker.run_once()

    assert queue.qsize() == 1
    assert await queue.get() == b"<event/>"


@pytest.mark.asyncio
async def test_mqtt_rx_worker_decodes_protobuf():
    queue = asyncio.Queue()
    mock_client = mock.MagicMock()
    message_iter = mock.MagicMock()
    message_iter.__anext__ = AsyncMock(return_value=_make_message(SAMPLE_PROTO_BYTES))
    mock_client.messages = mock.MagicMock()
    mock_client.messages.__aiter__ = mock.MagicMock(return_value=message_iter)
    session = _MQTTSession(mock_client)

    mock_takproto = mock.MagicMock()
    mock_takproto.parse_proto.return_value = SAMPLE_COT

    worker = MQTTRXWorker(queue, {"TAK_PROTO": "1"}, mock_client, session)
    worker.use_protobuf = True

    with mock.patch("pytak.classes.takproto", mock_takproto):
        await worker.run_once()

    assert queue.qsize() == 1
    assert await queue.get() == SAMPLE_COT


# ---------------------------------------------------------------------------
# mqtt_factory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mqtt_factory_full_duplex():
    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "mqtt://broker.example.com:1883/cot")
    cfg = config["test"]

    mock_client = mock.MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.subscribe = AsyncMock()
    mock_client.messages = mock.MagicMock()
    mock_client.messages.__aiter__ = mock.MagicMock(return_value=mock.MagicMock())

    mock_aiomqtt = mock.MagicMock()
    mock_aiomqtt.Client.return_value = mock_client

    with mock.patch.dict("sys.modules", {"aiomqtt": mock_aiomqtt}):
        tx_q, rx_q = asyncio.Queue(), asyncio.Queue()
        tx_worker, rx_worker = await pytak.mqtt_factory(tx_q, rx_q, cfg)

    assert isinstance(tx_worker, MQTTTXWorker)
    assert isinstance(rx_worker, MQTTRXWorker)
    mock_client.subscribe.assert_called_once_with("cot", qos=0)


@pytest.mark.asyncio
async def test_mqtt_factory_write_only():
    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "mqtt+wo://broker.example.com:1883/cot")
    cfg = config["test"]

    mock_client = mock.MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.subscribe = AsyncMock()

    mock_aiomqtt = mock.MagicMock()
    mock_aiomqtt.Client.return_value = mock_client

    with mock.patch.dict("sys.modules", {"aiomqtt": mock_aiomqtt}):
        tx_worker, rx_worker = await pytak.mqtt_factory(
            asyncio.Queue(), asyncio.Queue(), cfg
        )

    assert isinstance(tx_worker, MQTTTXWorker)
    assert rx_worker is None
    mock_client.subscribe.assert_not_called()


@pytest.mark.asyncio
async def test_mqtt_factory_read_only():
    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "mqtt+ro://broker.example.com:1883/cot")
    cfg = config["test"]

    mock_client = mock.MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.subscribe = AsyncMock()
    mock_client.messages = mock.MagicMock()
    mock_client.messages.__aiter__ = mock.MagicMock(return_value=mock.MagicMock())

    mock_aiomqtt = mock.MagicMock()
    mock_aiomqtt.Client.return_value = mock_client

    with mock.patch.dict("sys.modules", {"aiomqtt": mock_aiomqtt}):
        tx_worker, rx_worker = await pytak.mqtt_factory(
            asyncio.Queue(), asyncio.Queue(), cfg
        )

    assert tx_worker is None
    assert isinstance(rx_worker, MQTTRXWorker)
    mock_client.subscribe.assert_called_once_with("cot", qos=0)


@pytest.mark.asyncio
async def test_mqtt_factory_import_error():
    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "mqtt://broker.example.com:1883/cot")
    cfg = config["test"]

    import builtins

    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "aiomqtt":
            raise ImportError("no aiomqtt")
        return real_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=_import):
        with pytest.raises(ImportError, match="with-mqtt"):
            await pytak.mqtt_factory(asyncio.Queue(), asyncio.Queue(), cfg)


# ---------------------------------------------------------------------------
# _make_workers dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_workers_mqtt_scheme():
    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "mqtt://broker.example.com:1883/cot")
    cfg = config["test"]

    mock_tx = mock.MagicMock(spec=MQTTTXWorker)
    mock_rx = mock.MagicMock(spec=MQTTRXWorker)

    with mock.patch(
        "pytak.mqtt_factory",
        new=AsyncMock(return_value=(mock_tx, mock_rx)),
    ) as mock_factory:
        tx_q, rx_q = asyncio.Queue(), asyncio.Queue()
        write_worker, read_worker = await _make_workers(tx_q, rx_q, cfg)
        mock_factory.assert_called_once_with(tx_q, rx_q, cfg)
        assert write_worker is mock_tx
        assert read_worker is mock_rx


@pytest.mark.asyncio
async def test_make_workers_mqtts_scheme():
    config = ConfigParser()
    config.add_section("test")
    config.set("test", "COT_URL", "mqtts://broker.example.com:8883/cot")
    cfg = config["test"]

    mock_tx = mock.MagicMock(spec=MQTTTXWorker)
    mock_rx = mock.MagicMock(spec=MQTTRXWorker)

    with mock.patch(
        "pytak.mqtt_factory",
        new=AsyncMock(return_value=(mock_tx, mock_rx)),
    ) as mock_factory:
        await _make_workers(asyncio.Queue(), asyncio.Queue(), cfg)
        mock_factory.assert_called_once()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_mqtt_constants():
    assert pytak.DEFAULT_MQTT_PORT == 1883
    assert pytak.DEFAULT_MQTTS_PORT == 8883
    assert pytak.DEFAULT_MQTT_QOS == 0
    assert pytak.DEFAULT_MQTT_KEEPALIVE == 60
