#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Behavioural coverage tests for pytak.classes."""

import asyncio
import logging
import queue as std_queue
import xml.etree.ElementTree as ET
import zipfile
from configparser import ConfigParser
from unittest import mock

try:
    from unittest.mock import AsyncMock
except ImportError:
    # Python < 3.8: keep __call__ sync so MagicMock records calls / fires side_effect
    class AsyncMock(mock.MagicMock):
        def __call__(self, *args, **kwargs):
            super().__call__(*args, **kwargs)
            ret = self.return_value

            async def _coro():
                return ret

            return _coro()


import pytest

import pytak
from pytak import classes as pytak_classes

try:
    import takproto  # type: ignore
except ImportError:  # pragma: no cover
    takproto = None

needs_takproto = pytest.mark.skipif(takproto is None, reason="takproto missing")

SAMPLE_XML = (
    b'<event version="2.0" uid="u1" type="a-f-G" how="m-g" access="Undefined"'
    b' qos="1-r-c" time="2020-01-01T00:00:00Z" start="2020-01-01T00:00:00Z"'
    b' stale="2030-01-01T00:00:00Z"><point lat="1.5" lon="2.5" hae="0" ce="9"'
    b' le="9"/><detail><remarks>hi</remarks><track speed="3" course="90"/>'
    b'<contact callsign="cs"/></detail></event>'
)


class _StopLoop(Exception):
    """Raised by test doubles to break out of a worker's endless run loop."""


def _proto_bytes():
    return takproto.xml2proto(SAMPLE_XML, takproto.TAKProtoVer.STREAM)


def _proto_msg():
    return takproto.parse_proto(_proto_bytes())


def _section(**values):
    cfg = ConfigParser()
    cfg.add_section("pytak")
    for key, val in values.items():
        cfg["pytak"][key] = val
    return cfg["pytak"]


# --- _takmsg2xml -------------------------------------------------------------


@needs_takproto
def test_takmsg2xml_round_trips_fields():
    event = ET.fromstring(pytak_classes._takmsg2xml(_proto_msg()))
    assert event.get("uid") == "u1"
    assert event.get("access") == "Undefined"
    assert event.get("qos") == "1-r-c"
    assert event.find("detail/remarks").text == "hi"
    assert event.find("detail/track").get("course") == "90.0"
    assert event.find("detail/contact").get("callsign") == "cs"


@needs_takproto
def test_takmsg2xml_keeps_unparseable_xml_detail_as_text():
    msg = _proto_msg()
    msg.cotEvent.detail.xmlDetail = "<broken"
    event = ET.fromstring(pytak_classes._takmsg2xml(msg))
    assert event.find("detail").text == "<broken"


@needs_takproto
def test_takmsg2xml_without_uid_returns_none():
    msg = _proto_msg()
    msg.cotEvent.uid = ""
    assert pytak_classes._takmsg2xml(msg) is None


def test_takmsg2xml_bad_object_returns_none():
    assert pytak_classes._takmsg2xml(object()) is None


# --- queue helpers -----------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_queue_put_on_full_non_asyncio_queue_drops_oldest():
    q = std_queue.Queue(maxsize=1)
    q.put_nowait(b"old")
    await pytak_classes._safe_queue_put(q, b"new", logging.getLogger("t"))
    assert q.get_nowait() == b"new"
    assert q.empty()


@pytest.mark.asyncio
async def test_worker_handle_full_queue_drops_oldest():
    q = asyncio.Queue(maxsize=2)
    q.put_nowait(b"a")
    q.put_nowait(b"b")
    await pytak.Worker(q, {})._handle_full_queue(q)
    assert q.qsize() == 1 and q.get_nowait() == b"b"


# --- Worker ------------------------------------------------------------------


def test_worker_debug_true_raises_handler_level():
    handler = mock.MagicMock()
    with mock.patch.object(pytak.Worker._logger, "handlers", [handler]):
        pytak.Worker(asyncio.Queue(), {"DEBUG": "yes"})
    handler.setLevel.assert_called_once_with(logging.DEBUG)


def test_worker_warns_when_tak_proto_without_takproto():
    with mock.patch.object(pytak_classes, "takproto", None), mock.patch.object(
        pytak.Worker._logger, "warning"
    ) as warning:
        worker = pytak.Worker(asyncio.Queue(), {"TAK_PROTO": "1"})
    assert worker.use_protobuf is False
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_fts_compat_uses_pytak_sleep():
    worker = pytak.Worker(asyncio.Queue(), {"PYTAK_SLEEP": "3"})
    with mock.patch.object(pytak_classes.asyncio, "sleep", AsyncMock()) as sleep:
        await worker.fts_compat()
    sleep.assert_called_once_with(3)


@pytest.mark.asyncio
async def test_fts_compat_true_uses_random_sleep():
    worker = pytak.Worker(asyncio.Queue(), {"FTS_COMPAT": "true"})
    with mock.patch.object(
        pytak_classes.random, "random", return_value=0.5
    ), mock.patch.object(pytak_classes.asyncio, "sleep", AsyncMock()) as sleep:
        await worker.fts_compat()
    sleep.assert_called_once_with(int(int(pytak.DEFAULT_SLEEP) * 0.5))


@pytest.mark.asyncio
async def test_worker_run_processes_queue_until_error():
    q = asyncio.Queue()
    q.put_nowait(b"one")
    q.put_nowait(b"two")
    seen = []

    class _W(pytak.Worker):
        async def handle_data(self, data):
            await super().handle_data(data)
            seen.append(data)
            if len(seen) == 2:
                raise _StopLoop()

    worker = _W(q, {})
    with pytest.raises(_StopLoop):
        await worker.run()
    assert seen == [b"one", b"two"]
    assert await worker.close() is None


# --- TXWorker ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_txworker_send_none_is_skipped():
    writer = mock.MagicMock()
    await pytak.TXWorker(asyncio.Queue(), {}, writer).send_data(None)
    writer.write.assert_not_called()


@pytest.mark.asyncio
async def test_txworker_writes_drains_and_flushes():
    writer = mock.MagicMock(spec=["write", "drain", "flush"])
    writer.drain = AsyncMock()
    await pytak.TXWorker(asyncio.Queue(), {}, writer).handle_data(b"<event/>")
    writer.write.assert_called_once_with(b"<event/>")
    writer.drain.assert_called_once()
    writer.flush.assert_called_once()


@pytest.mark.asyncio
async def test_txworker_uses_send_when_available():
    writer = mock.MagicMock(spec=["send"])
    writer.send = AsyncMock()
    await pytak.TXWorker(asyncio.Queue(), {}, writer).send_data(b"x")
    writer.send.assert_called_once_with(b"x")


@pytest.mark.parametrize(
    "url,expected",
    [
        ("udp://239.2.3.1:6969", "MESH"),
        ("tcp://takserver.example.com:8087", "STREAM"),
    ],
)
@pytest.mark.asyncio
async def test_txworker_protobuf_selects_mesh_or_stream(url, expected):
    fake = mock.MagicMock()
    fake.xml2proto.return_value = b"PROTO"
    writer = mock.MagicMock(spec=["write"])
    with mock.patch.object(pytak_classes, "takproto", fake):
        worker = pytak.TXWorker(
            asyncio.Queue(), {"TAK_PROTO": "1", "COT_URL": url}, writer
        )
        await worker.send_data(b"<event/>")
    fake.xml2proto.assert_called_once_with(
        b"<event/>", getattr(fake.TAKProtoVer, expected)
    )
    writer.write.assert_called_once_with(b"PROTO")


@pytest.mark.asyncio
async def test_txworker_protobuf_parse_error_sends_raw():
    fake = mock.MagicMock()
    fake.xml2proto.side_effect = ET.ParseError("bad")
    writer = mock.MagicMock(spec=["write"])
    with mock.patch.object(pytak_classes, "takproto", fake):
        worker = pytak.TXWorker(
            asyncio.Queue(),
            {"TAK_PROTO": "1", "COT_URL": "tcp://takserver.example.com:1"},
            writer,
        )
        await worker.send_data(b"<bad")
    writer.write.assert_called_once_with(b"<bad")


# --- RXWorker ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_rxworker_reads_datagram_reader():
    reader = mock.MagicMock(spec=["recv"])
    reader.recv = AsyncMock(return_value=(b"<event/>", ("127.0.0.1", 1)))
    worker = pytak.RXWorker(asyncio.Queue(), {}, reader)
    await worker.handle_data(b"ignored")
    assert await worker.readcot() == b"<event/>"


@needs_takproto
@pytest.mark.asyncio
async def test_rxworker_parses_protobuf_payload():
    reader = mock.MagicMock(spec=["recv"])
    reader.recv = AsyncMock(return_value=(_proto_bytes(), None))
    worker = pytak.RXWorker(asyncio.Queue(), {"TAK_PROTO": "1"}, reader)
    msg = await worker.readcot()
    assert msg.cotEvent.uid == "u1"


@pytest.mark.asyncio
async def test_rxworker_run_skips_empty_reads():
    q = asyncio.Queue()
    results = iter([(b"", None), (b"<e/>", None)])

    class _Reader:
        async def recv(self):
            for item in results:
                return item
            raise _StopLoop()

    reader = _Reader()
    with pytest.raises(_StopLoop):
        await pytak.RXWorker(q, {}, reader).run()
    assert q.qsize() == 1 and q.get_nowait() == b"<e/>"


# --- _socket_workers / TLS error classification ------------------------------


@pytest.mark.parametrize(
    "write_only,read_only,tx_cls,rx_cls",
    [
        (True, False, pytak.TXWorker, pytak.DiscardRXWorker),
        (False, True, type(None), pytak.RXWorker),
        (False, False, pytak.TXWorker, pytak.RXWorker),
    ],
)
def test_socket_workers_modes(write_only, read_only, tx_cls, rx_cls):
    tx, rx = pytak_classes._socket_workers(
        asyncio.Queue(), asyncio.Queue(), {}, object(), object(), write_only, read_only
    )
    assert type(tx) is tx_cls
    assert type(rx) is rx_cls


def test_is_fatal_tls_cert_error_follows_cause_chain():
    try:
        try:
            raise OSError("sslv3_alert_certificate_unknown")
        except OSError as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as outer:
        assert pytak_classes._is_fatal_tls_cert_error(outer)
    assert not pytak_classes._is_fatal_tls_cert_error(RuntimeError("other"))


# --- Marti workers -----------------------------------------------------------


class _Resp:
    def __init__(self, status, text=""):
        self.status = status
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _marti_tx(session):
    return pytak.MartiTXWorker(
        asyncio.Queue(), {}, session, "https://takserver.example.com/", "uid-1"
    )


@pytest.mark.asyncio
async def test_marti_tx_posts_payload():
    session = mock.MagicMock()
    session.post.return_value = _Resp(500)
    await _marti_tx(session).handle_data(b" <event/> ")
    args, kwargs = session.post.call_args
    assert args[0] == "https://takserver.example.com/Marti/api/injectors/cot/uid"
    assert kwargs["json"] == {"uid": "uid-1", "toInject": "<event/>"}


@pytest.mark.asyncio
async def test_marti_tx_ignores_blank_and_logs_errors():
    session = mock.MagicMock()
    worker = _marti_tx(session)
    await worker.handle_data(b"   ")
    session.post.assert_not_called()
    session.post.side_effect = OSError("down")
    await worker.handle_data(b"<event/>")  # logged, not raised


@pytest.mark.asyncio
async def test_marti_tx_cert_rejection_is_fatal_and_close():
    session = mock.MagicMock()
    session.close = AsyncMock()
    session.post.side_effect = OSError("bad certificate")
    worker = _marti_tx(session)
    with pytest.raises(PermissionError):
        await worker.handle_data(b"<event/>")
    await worker.close()
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_marti_rx_cert_rejection_and_run_loop():
    session = mock.MagicMock()
    session.close = AsyncMock()
    session.get.side_effect = OSError("unknown ca")
    q = asyncio.Queue()
    worker = pytak.MartiRXWorker(q, {}, session, "https://takserver.example.com")
    await worker.handle_data(b"x")
    with pytest.raises(PermissionError):
        await worker.run_once()

    session.get.side_effect = None
    session.get.return_value = _Resp(200, "<event uid='a'></event>junk")
    with mock.patch.object(
        pytak_classes.asyncio, "sleep", AsyncMock(side_effect=_StopLoop())
    ):
        with pytest.raises(_StopLoop):
            await worker.run()
    assert q.get_nowait() == b"<event uid='a'></event>"
    await worker.close()
    session.close.assert_called_once()


# --- WebSocket workers -------------------------------------------------------


def _ws_types():
    fake = mock.MagicMock()
    fake.WSMsgType.BINARY = "BINARY"
    fake.WSMsgType.CLOSE = "CLOSE"
    fake.WSMsgType.CLOSED = "CLOSED"
    fake.WSMsgType.ERROR = "ERROR"
    return fake


@pytest.mark.asyncio
async def test_ws_tx_close_tolerates_ws_error():
    ws = mock.MagicMock()
    ws.close = AsyncMock(side_effect=RuntimeError("gone"))
    session = mock.MagicMock()
    session.close = AsyncMock()
    await pytak.WSTXWorker(asyncio.Queue(), {}, ws, session).close()
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_ws_rx_without_aiohttp_is_noop():
    ws = mock.MagicMock()
    worker = pytak.WSRXWorker(asyncio.Queue(), {}, ws)
    await worker.handle_data(b"x")
    with mock.patch.object(pytak_classes, "_aiohttp", None):
        await worker.run_once()
    ws.receive.assert_not_called()


@needs_takproto
@pytest.mark.asyncio
async def test_ws_rx_decodes_protobuf_to_xml():
    ws = mock.MagicMock()
    ws.receive = AsyncMock(
        return_value=mock.MagicMock(type="BINARY", data=_proto_bytes())
    )
    q = asyncio.Queue()
    with mock.patch.object(pytak_classes, "_aiohttp", _ws_types()):
        await pytak.WSRXWorker(q, {}, ws).run_once()
    assert ET.fromstring(q.get_nowait()).get("uid") == "u1"


@pytest.mark.asyncio
async def test_ws_rx_close_and_error_raise():
    ws = mock.MagicMock()
    ws.exception.return_value = "kaput"
    worker = pytak.WSRXWorker(asyncio.Queue(), {}, ws)
    with mock.patch.object(pytak_classes, "_aiohttp", _ws_types()):
        ws.receive = AsyncMock(return_value=mock.MagicMock(type="CLOSED"))
        with pytest.raises(ConnectionAbortedError):
            await worker.run()
        ws.receive = AsyncMock(return_value=mock.MagicMock(type="ERROR"))
        with pytest.raises(ConnectionError, match="kaput"):
            await worker.run_once()


# --- MQTT workers ------------------------------------------------------------


@pytest.mark.asyncio
async def test_mqtt_session_close_is_idempotent():
    client = mock.MagicMock()
    client.__aexit__ = AsyncMock()
    session = pytak_classes._MQTTSession(client)
    await session.close()
    await session.close()
    client.__aexit__.assert_called_once_with(None, None, None)


@pytest.mark.asyncio
async def test_mqtt_tx_encode_failure_sends_raw_and_publish_failure_raises():
    fake = mock.MagicMock()
    fake.xml2proto.side_effect = ValueError("nope")
    client = mock.MagicMock()
    client.publish = AsyncMock()
    session = mock.MagicMock()
    session.close = AsyncMock()
    with mock.patch.object(pytak_classes, "takproto", fake):
        worker = pytak.MQTTTXWorker(
            asyncio.Queue(), {"TAK_PROTO": "1"}, client, "cot", 1, session
        )
        await worker.handle_data(b"<event/>")
    client.publish.assert_called_once_with("cot", b"<event/>", qos=1)

    client.publish = AsyncMock(side_effect=RuntimeError("broker gone"))
    with pytest.raises(ConnectionError):
        await worker.handle_data(b"<event/>")
    await worker.close()
    session.close.assert_called_once()


def _mqtt_rx(payloads, config):
    msgs = iter([mock.MagicMock(payload=p) for p in payloads])

    class _Iter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(msgs)
            except StopIteration:
                raise _StopLoop()

    client = mock.MagicMock()
    client.messages = _Iter()
    session = mock.MagicMock()
    session.close = AsyncMock()
    return pytak.MQTTRXWorker(asyncio.Queue(), config, client, session), session


@needs_takproto
@pytest.mark.asyncio
async def test_mqtt_rx_decodes_protobuf_and_drops_garbage():
    worker, session = _mqtt_rx([_proto_bytes(), b"\x00garbage"], {"TAK_PROTO": "1"})
    await worker.handle_data(b"x")
    with pytest.raises(_StopLoop):
        await worker.run()
    assert worker.queue.qsize() == 1
    assert ET.fromstring(worker.queue.get_nowait()).get("uid") == "u1"
    await worker.close()
    session.close.assert_called_once()


# --- QueueWorker / CLITool ---------------------------------------------------


@pytest.mark.asyncio
async def test_queue_worker_base_handle_data_is_noop():
    class _QW(pytak.QueueWorker):
        async def handle_data(self, data):
            return await super().handle_data(data)

    assert await _QW(asyncio.Queue(), {}).handle_data(b"x") is None


def test_clitool_debug_true_and_config_property():
    handler = mock.MagicMock()
    with mock.patch.object(pytak.CLITool._logger, "handlers", [handler]):
        tool = pytak.CLITool(_section(DEBUG="1"))
    handler.setLevel.assert_called_once_with(logging.DEBUG)
    new_cfg = _section(COT_URL="tcp://takserver.example.com:8087")
    tool.config = new_cfg
    assert tool.config is new_cfg


@pytest.mark.asyncio
async def test_clitool_create_workers_and_setup():
    tool = pytak.CLITool(_section())
    tx_w, rx_w = object(), object()
    with mock.patch.object(
        pytak_classes, "_make_workers", AsyncMock(return_value=(tx_w, rx_w))
    ):
        await tool.create_workers(_section())
        assert tool.queues["pytak"]["tx_queue"] is tool.tx_queue
        await tool.setup()
    assert tool.tasks == {tx_w, rx_w}
    tool.add_tasks([1, 2])
    assert {1, 2} <= tool.tasks


@pytest.mark.asyncio
async def test_clitool_close_workers_handles_errors_and_timeouts():
    tool = pytak.CLITool(_section())
    loop = asyncio.get_event_loop()

    bad = mock.MagicMock()
    bad.close = AsyncMock(side_effect=RuntimeError("close failed"))
    slow = mock.MagicMock()
    slow.close = mock.MagicMock(side_effect=lambda: asyncio.Event().wait())

    futs = []
    for worker in (bad, slow, bad):
        fut = loop.create_future()
        fut._pytak_worker = worker
        futs.append(fut)

    with mock.patch.object(pytak_classes, "_WORKER_SHUTDOWN_TIMEOUT", 0.05):
        await tool._close_running_workers(set(futs))
    bad.close.assert_called_once()
    slow.close.assert_called_once()


@pytest.mark.asyncio
async def test_clitool_cancels_stalled_workers():
    tool = pytak.CLITool(_section())
    loop = asyncio.get_event_loop()
    stalled_future = loop.create_future()
    named = loop.create_future()
    named._pytak_worker = pytak.Worker(asyncio.Queue(), {})
    assert tool._worker_name(named) == "Worker"
    assert "Future" in tool._worker_name(stalled_future)

    with mock.patch.object(pytak_classes, "_WORKER_SHUTDOWN_TIMEOUT", 0.05):
        await tool._wait_for_cancelled_workers({stalled_future})
        await tool._wait_for_cancelled_workers(set())
    assert stalled_future.cancelled()


@pytest.mark.asyncio
async def test_clitool_run_ignores_cancelled_workers():
    class _Cancelled:
        async def run(self):
            raise asyncio.CancelledError()

        async def close(self):
            return None

    tool = pytak.CLITool(_section(PYTAK_NO_HELLO="1"))
    tool.hello_event = AsyncMock()
    tool.add_task(_Cancelled())
    await tool.run()
    tool.hello_event.assert_not_called()


# --- COTEvent / TAKDataPackage -----------------------------------------------


def test_cot_event_to_bytes():
    event = pytak.COTEvent(
        lat=1.0, lon=2.0, uid="u1", stale=60, cot_type="a-f-G", ce=1, hae=2, le=3
    )
    root = ET.fromstring(event.to_bytes())
    assert root.get("uid") == "u1"
    assert root.find("point").get("hae") == "2"


def test_data_package_errors(tmp_path):
    pkg = pytak.TAKDataPackage("p")
    with pytest.raises(ValueError):
        pkg.create_package(str(tmp_path / "out.zip"))
    with pytest.raises(FileNotFoundError):
        pkg.add_file(str(tmp_path / "missing.txt"))
    with pytest.raises(FileNotFoundError):
        pkg.add_directory(str(tmp_path / "missing"))


def test_data_package_directory_and_manifest(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.kml").write_text("a")
    (src / "skip.tmp").write_text("s")
    (src / "sub" / "b.kml").write_text("b")

    flat = pytak.TAKDataPackage("flat")
    flat.add_directory(str(src), recursive=False)
    assert sorted(f["zip_entry"] for f in flat.files) == ["a.kml", "skip.tmp"]

    pkg = pytak.TAKDataPackage("Mission", uid="uid-1", on_receive_delete=True)
    pkg.add_directory(str(src), ignore_pattern=".tmp")
    out = tmp_path / "mission.zip"
    pkg.create_package(str(out))

    with zipfile.ZipFile(str(out)) as zf:
        names = set(zf.namelist())
        manifest = ET.fromstring(zf.read("MANIFEST/manifest.xml"))
    assert names == {"a.kml", "sub/b.kml", "MANIFEST/manifest.xml"}
    params = {p.get("name"): p.get("value") for p in manifest.iter("Parameter")}
    assert params == {"uid": "uid-1", "name": "Mission", "onReceiveDelete": "true"}
    entries = {c.get("zipEntry") for c in manifest.iter("Content")}
    assert entries == {"a.kml", "sub/b.kml"}


def test_data_package_without_manifest(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("a")
    pkg = pytak.TAKDataPackage("p")
    pkg.add_file(str(src), ignore=True, zip_entry_name="renamed.txt")
    out = tmp_path / "p.dpk"
    pkg.create_package(str(out), use_dpk_extension=True, include_manifest=False)
    with zipfile.ZipFile(str(out)) as zf:
        assert zf.namelist() == ["renamed.txt"]
