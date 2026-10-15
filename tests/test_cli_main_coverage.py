#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

"""Coverage tests for pytak.cli_main (CLITool and network are mocked)."""

import asyncio
import io
import os
import types
import xml.etree.ElementTree as ET
from argparse import Namespace
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

from pytak import cli_main
from pytak.cli_main import (
    FileWorker,
    StdinWorker,
    StdoutWorker,
    _indent_xml,
    _pretty_xml,
    _resolve_tak_url,
    _tak_connection_candidates,
)

TAK_URL = (
    "tak://com.atakmap.app/enroll?host=takserver.example.com&" "username=user&token=tok"
)

EVENT = b'<event uid="A"><point lat="1" lon="2"/></event>'


def _args(**kwargs):
    base = dict(
        url="tcp://takserver.example.com:8087",
        rx_only=False,
        tx_only=False,
        tx_file=None,
        tls_cert=None,
        tls_key=None,
        tls_ca=None,
        tls_pass=None,
        no_verify=False,
        debug=False,
    )
    base.update(kwargs)
    return Namespace(**base)


class FakeCLITool:
    """Stand-in for pytak.CLITool recording configs and tasks."""

    instances = []
    run_side_effects = []

    def __init__(self, config):
        self.config = dict(config)
        self.tx_queue = asyncio.Queue()
        self.rx_queue = asyncio.Queue()
        self.tasks = set()
        FakeCLITool.instances.append(self)

    async def setup(self):
        return None

    def add_tasks(self, tasks):
        self.tasks |= tasks

    async def run(self):
        if FakeCLITool.run_side_effects:
            exc = FakeCLITool.run_side_effects.pop(0)
            if exc is not None:
                raise exc


@pytest.fixture
def fake_clitool():
    FakeCLITool.instances = []
    FakeCLITool.run_side_effects = []
    with mock.patch("pytak.CLITool", FakeCLITool):
        yield FakeCLITool


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def test_pretty_xml_indents_and_preserves_content():
    out = _pretty_xml(EVENT)
    assert b"\n  <point" in out
    assert ET.fromstring(out).find("point").get("lat") == "1"


def test_pretty_xml_returns_input_on_parse_error():
    assert _pretty_xml(b"<not xml") == b"<not xml"


def test_pretty_xml_uses_fallback_without_et_indent():
    no_indent_et = types.SimpleNamespace(
        fromstring=ET.fromstring, tostring=ET.tostring, ParseError=ET.ParseError
    )
    with mock.patch.object(cli_main, "ET", no_indent_et):
        out = _pretty_xml(EVENT)
    assert b"\n  <point" in out


def test_indent_xml_fallback_nested():
    root = ET.fromstring("<a><b><c/></b><d/></a>")
    _indent_xml(root)
    text = ET.tostring(root, encoding="unicode")
    assert text == "<a>\n  <b>\n    <c />\n  </b>\n  <d />\n</a>"


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stdin_worker_run_reads_pipe_and_frames():
    rfd, wfd = os.pipe()
    os.write(wfd, EVENT + b"\n<event uid='B'/>\n<event partial")
    os.close(wfd)
    rfile = os.fdopen(rfd, "rb")
    fake_stdin = mock.MagicMock()
    fake_stdin.buffer = rfile
    queue = asyncio.Queue()
    worker = StdinWorker(queue, {})
    try:
        with mock.patch.object(cli_main.sys, "stdin", fake_stdin):
            with mock.patch.object(worker, "_logger") as logger:
                await asyncio.wait_for(worker.run(), timeout=2)
    finally:
        rfile.close()
    assert queue.qsize() == 2
    assert await queue.get() == EVENT
    assert await queue.get() == b"<event uid='B'/>"
    assert logger.warning.called


@pytest.mark.asyncio
async def test_file_worker_large_file_spanning_chunks(tmp_path):
    events = [b'<event uid="%d"/>' % i for i in range(500)]
    path = tmp_path / "big.xml"
    path.write_bytes(b"\n".join(events))
    queue = asyncio.Queue()
    await FileWorker(queue, {}, str(path)).run()
    got = [queue.get_nowait() for _ in range(queue.qsize())]
    assert got == events


@pytest.mark.asyncio
async def test_stdout_worker_run_skips_empty_and_writes():
    queue = asyncio.Queue()
    worker = StdoutWorker(queue, {})
    written = []

    async def fake_handle(data):
        written.append(data)
        if len(written) == 1:
            raise asyncio.CancelledError()

    queue.put_nowait(b"")
    queue.put_nowait(EVENT)
    with mock.patch.object(worker, "handle_data", fake_handle):
        with pytest.raises(asyncio.CancelledError):
            await worker.run()
    assert written == [EVENT]


# ---------------------------------------------------------------------------
# _resolve_tak_url / candidates / cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_tak_url_exits_on_generic_failure(capsys):
    with mock.patch(
        "pytak.resolve_tak_url", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        with pytest.raises(SystemExit) as exc_info:
            await _resolve_tak_url(TAK_URL, {})
    assert exc_info.value.code == 1
    assert "Enrollment failed: boom" in capsys.readouterr().err


def test_tak_candidates_tls_adds_streaming_fallback():
    url = TAK_URL.replace("takserver.example.com", "takserver.example.com:8089")
    cands = _tak_connection_candidates(url, "tls://takserver.example.com:8089")
    assert cands == ["tls://takserver.example.com:8089"]


def test_tak_candidates_wss_explicit_non_default_port():
    url = TAK_URL.replace("takserver.example.com", "takserver.example.com:9443")
    cands = _tak_connection_candidates(url, "wss://takserver.example.com:9443/x")
    port = cli_main.pytak.DEFAULT_MARTI_PORT
    assert cands[0] == "wss://takserver.example.com:9443/x"
    assert "marti://takserver.example.com:9443" in cands
    assert "marti://takserver.example.com:%s" % port in cands
    assert any(c.startswith("wss://takserver.example.com:%s" % port) for c in cands)


def test_clear_tak_cert_cache_ignores_missing_and_oserror(tmp_path):
    with mock.patch("pytak.cli_main.Path.home", return_value=tmp_path):
        cli_main._clear_tak_cert_cache(TAK_URL)  # files missing: no error
    with mock.patch("pytak.cli_main.Path.home", return_value=tmp_path):
        with mock.patch("pathlib.Path.unlink", side_effect=PermissionError("ro")):
            cli_main._clear_tak_cert_cache(TAK_URL)  # OSError swallowed


def test_is_certificate_rejected_follows_context_chain():
    inner = RuntimeError("tlsv1 alert unknown ca")
    outer = RuntimeError("wrapped")
    outer.__context__ = inner
    assert cli_main._is_certificate_rejected_error(outer) is True


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_builds_config_and_file_and_stdout_workers(fake_clitool, tmp_path):
    path = tmp_path / "e.xml"
    path.write_bytes(EVENT)
    args = _args(
        tx_file=str(path),
        tls_cert="c.pem",
        tls_key="k.pem",
        tls_ca="ca.pem",
        tls_pass="pw",
        no_verify=True,
        debug=True,
    )
    with mock.patch.object(cli_main, "_get_tx_source", return_value="file"):
        await cli_main._run(args)
    (tool,) = fake_clitool.instances
    cfg = tool.config
    assert cfg["cot_url"] == args.url
    assert cfg["debug"] == "1"
    assert cfg["pytak_tls_client_cert"] == "c.pem"
    assert cfg["pytak_tls_client_key"] == "k.pem"
    assert cfg["pytak_tls_client_cafile"] == "ca.pem"
    assert cfg["pytak_tls_client_password"] == "pw"
    assert cfg["pytak_tls_dont_verify"] == "1"
    assert cfg["pytak_tls_dont_check_hostname"] == "1"
    kinds = sorted(type(t).__name__ for t in tool.tasks)
    assert kinds == ["FileWorker", "StdoutWorker"]


@pytest.mark.asyncio
async def test_run_stdin_tx_only_adds_only_stdin_worker(fake_clitool):
    with mock.patch.object(cli_main, "_get_tx_source", return_value="stdin"):
        await cli_main._run(_args(tx_only=True))
    (tool,) = fake_clitool.instances
    assert [type(t).__name__ for t in tool.tasks] == ["StdinWorker"]


@pytest.mark.asyncio
async def test_run_no_tasks_when_tx_only_and_no_source(fake_clitool):
    with mock.patch.object(cli_main, "_get_tx_source", return_value="none"):
        await cli_main._run(_args(tx_only=True))
    assert fake_clitool.instances[0].tasks == set()


@pytest.mark.asyncio
async def test_run_non_tak_error_is_raised(fake_clitool):
    fake_clitool.run_side_effects = [RuntimeError("ssl handshake failed")]
    with mock.patch.object(cli_main, "_get_tx_source", return_value="none"):
        with pytest.raises(RuntimeError, match="handshake"):
            await cli_main._run(_args())
    assert len(fake_clitool.instances) == 1


def _fake_resolve(cot_url):
    async def _resolve(raw_url, cfg):
        cfg["COT_URL"] = cot_url

    return _resolve


@pytest.mark.asyncio
async def test_run_tak_url_falls_back_to_next_candidate(fake_clitool, capsys):
    fake_clitool.run_side_effects = [RuntimeError("SSL handshake failed"), None]
    with mock.patch.object(
        cli_main, "_resolve_tak_url", _fake_resolve("wss://takserver.example.com/x")
    ):
        with mock.patch.object(cli_main, "_get_tx_source", return_value="none"):
            await cli_main._run(_args(url=TAK_URL))
    urls = [t.config["cot_url"] for t in fake_clitool.instances]
    assert urls[0] == "wss://takserver.example.com/x"
    assert urls[1].startswith("marti://takserver.example.com")
    err = capsys.readouterr().err
    assert "Trying transport 1/" in err
    assert "Retrying" in err


@pytest.mark.asyncio
async def test_run_tak_url_non_ssl_error_stops_and_reports(fake_clitool, capsys):
    fake_clitool.run_side_effects = [ValueError("bad config")]
    with mock.patch.object(
        cli_main, "_resolve_tak_url", _fake_resolve("wss://takserver.example.com/x")
    ):
        with mock.patch.object(cli_main, "_get_tx_source", return_value="none"):
            with pytest.raises(ValueError, match="bad config"):
                await cli_main._run(_args(url=TAK_URL))
    assert len(fake_clitool.instances) == 1
    err = capsys.readouterr().err
    assert "All enrolled transport candidates failed" in err
    assert "Final failure: ValueError: bad config" in err


@pytest.mark.asyncio
async def test_run_tak_url_cert_rejected_reenrolls_once(fake_clitool, capsys):
    rejected = RuntimeError("SSLV3_ALERT_CERTIFICATE_UNKNOWN")
    # cycle 1: candidate 1 rejected (retry), candidate 2 fails -> break;
    # re-enroll; cycle 2: candidate 1 succeeds.
    fake_clitool.run_side_effects = [rejected, ValueError("x"), None]
    resolve_calls = []

    async def _resolve(raw_url, cfg):
        resolve_calls.append(raw_url)
        cfg["COT_URL"] = "wss://takserver.example.com/x"

    with mock.patch.object(cli_main, "_resolve_tak_url", _resolve):
        with mock.patch.object(cli_main, "_clear_tak_cert_cache") as clear:
            with mock.patch.object(cli_main, "_get_tx_source", return_value="none"):
                await cli_main._run(_args(url=TAK_URL))
    assert len(resolve_calls) == 2
    clear.assert_called_once_with(TAK_URL)
    assert len(fake_clitool.instances) == 3
    assert "re-enrolling once" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# dp_main
# ---------------------------------------------------------------------------


def _dp_result(with_optional=True):
    enroll = {
        "pkcs12_path": "pkg/certs/u.p12",
        "certificate_path": "pkg/certs/u.pem",
        "private_key_path": "pkg/certs/u-key.pem",
    }
    if with_optional:
        enroll["ca_bundle_path"] = "pkg/certs/ca.pem"
        enroll["pkcs12_truststore_path"] = "pkg/certs/trust.p12"
    return {
        "package_folder": "pkg",
        "data_package_zip": "pkg/a.zip",
        "data_package_itak_zip": "pkg/i.zip",
        "streaming_connect_string": "takserver.example.com:8089:ssl",
        "pkcs12_password": "example-pass",
        "enrollment": enroll,
    }


def test_dp_main_rejects_non_tak_url():
    with pytest.raises(SystemExit) as exc_info:
        cli_main.dp_main(["https://takserver.example.com"])
    assert exc_info.value.code == 2


def test_dp_main_prints_paths_verbose(capsys):
    import pytak.onboarding_packages as op

    fake = AsyncMock(return_value=_dp_result())
    with mock.patch.object(op, "enroll_onboarding_package", fake):
        cli_main.dp_main([TAK_URL, "-o", "out", "--package-stem", "dev", "-v"])
    kwargs = fake.call_args[1]
    assert fake.call_args[0] == (TAK_URL, "out")
    assert kwargs["package_stem"] == "dev"
    out, err = capsys.readouterr()
    assert "package_dir=pkg" in out
    assert "ca_pem=pkg/certs/ca.pem" in out
    assert "trust_p12=pkg/certs/trust.p12" in out
    assert "connect_string=takserver.example.com:8089:ssl" in out
    assert "example-pass" in err


def test_dp_main_omits_optional_paths(capsys):
    import pytak.onboarding_packages as op

    fake = AsyncMock(return_value=_dp_result(with_optional=False))
    with mock.patch.object(op, "enroll_onboarding_package", fake):
        cli_main.dp_main([TAK_URL])
    out, err = capsys.readouterr()
    assert "ca_pem=" not in out
    assert "trust_p12=" not in out
    assert "example-pass" not in err


def test_dp_main_enrollment_failure_exits(capsys):
    import pytak.onboarding_packages as op

    fake = AsyncMock(side_effect=RuntimeError("denied"))
    with mock.patch.object(op, "enroll_onboarding_package", fake):
        with pytest.raises(SystemExit) as exc_info:
            cli_main.dp_main([TAK_URL, "-v"])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Enrollment failed: denied" in err
    assert "Traceback" in err


def test_dp_main_missing_dependency_exits(capsys):
    with mock.patch.dict("sys.modules", {"pytak.onboarding_packages": None}):
        with pytest.raises(SystemExit) as exc_info:
            cli_main.dp_main([TAK_URL])
    assert exc_info.value.code == 1
    assert "requires pytak[with-aiohttp,with-crypto]" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _main(argv, tty=True):
    fake_stdin = mock.MagicMock()
    fake_stdin.isatty.return_value = tty
    with mock.patch.object(cli_main.sys, "argv", ["pytak"] + argv):
        with mock.patch.object(cli_main.sys, "stdin", fake_stdin):
            cli_main.main()


def test_main_runs_with_parsed_args():
    captured = {}

    async def fake_run(args):
        captured["args"] = args

    with mock.patch.object(cli_main, "_run", fake_run):
        _main(["--rx-only", "-d", "tcp://takserver.example.com:8087"])
    assert captured["args"].rx_only is True
    assert captured["args"].debug is True


def test_main_rejects_rx_only_with_tx_only(capsys):
    with pytest.raises(SystemExit) as exc_info:
        _main(["--rx-only", "--tx-only", "tcp://takserver.example.com:8087"])
    assert exc_info.value.code == 2
    assert "cannot be used together" in capsys.readouterr().err


def test_main_reports_ambiguous_tx_source(capsys):
    with mock.patch.object(
        cli_main, "_get_tx_source", side_effect=ValueError("Ambiguous TX source")
    ):
        with pytest.raises(SystemExit) as exc_info:
            _main(["--tx-file", "e.xml", "tcp://takserver.example.com:8087"])
    assert exc_info.value.code == 2
    assert "Ambiguous TX source" in capsys.readouterr().err


def test_main_swallows_keyboard_interrupt():
    async def fake_run(args):
        raise KeyboardInterrupt

    with mock.patch.object(cli_main, "_run", fake_run):
        _main(["tcp://takserver.example.com:8087"])


def test_main_reports_runtime_error(capsys):
    async def fake_run(args):
        raise ConnectionRefusedError("refused")

    with mock.patch.object(cli_main, "_run", fake_run):
        with pytest.raises(SystemExit) as exc_info:
            _main(["tcp://takserver.example.com:8087"])
    assert exc_info.value.code == 1
    assert "ConnectionRefusedError: refused" in capsys.readouterr().err


def test_stdin_is_data_source_tty_short_circuits():
    assert cli_main._stdin_is_data_source(True) is False


def test_stdin_is_data_source_without_fileno():
    with mock.patch.object(cli_main.sys, "stdin", io.StringIO()):
        assert cli_main._stdin_is_data_source(False) is True
