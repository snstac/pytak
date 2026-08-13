#!/usr/bin/env python3
# Copyright Sensors & Signals LLC https://www.snstac.com/
# SPDX-License-Identifier: Apache-2.0
"""Tests for pytak.status.

Weighted towards failure modes rather than the happy path. The bug this module
exists to prevent is a UI that renders "everything is fine" from data that
stopped being true an hour ago, so the tests that matter most are the ones
about staleness, boundedness, and what happens when writing fails.
"""

import json
import os
import stat

import pytest

from pytak.status import DEFAULT_STATUS_ROOT, StatusWriter, status_path


@pytest.fixture
def writer(tmp_path):
    return StatusWriter(
        "testcot",
        path=str(tmp_path / "testcot" / "status.json"),
        version="1.2.3",
        now=1000.0,
    )


class TestCollection:
    def test_counters_accumulate(self, writer):
        writer.count("rx", 5)
        writer.count("rx")
        writer.count("emitted")
        doc = writer.as_dict(now=1000.0)
        assert doc["counters"] == {"rx": 6, "emitted": 1}

    def test_record_passes_gateway_fields_through(self, writer):
        """The UI renders whatever columns it is given; no schema is imposed."""
        writer.record(now=1000.0, tail="N954SW", flight="OO5738", label="M21")
        entry = writer.as_dict(now=1000.0)["recent"][0]
        assert entry["tail"] == "N954SW"
        assert entry["label"] == "M21"
        assert entry["t"] == 1000.0

    def test_recent_is_bounded(self, tmp_path):
        """A gateway runs for months; the file must have a ceiling."""
        w = StatusWriter("t", path=str(tmp_path / "s.json"), max_recent=5, now=0.0)
        for i in range(100):
            w.record(now=float(i), seq=i)
        recent = w.as_dict(now=100.0)["recent"]
        assert len(recent) == 5
        # ...and it keeps the NEWEST, not the first five it happened to see.
        assert [e["seq"] for e in recent] == [95, 96, 97, 98, 99]

    def test_set_adds_top_level_fields(self, writer):
        writer.set(tracked=42)
        assert writer.as_dict(now=1000.0)["tracked"] == 42

    def test_common_health_contract_is_present_by_default(self, writer):
        doc = writer.as_dict(now=1000.0)
        assert doc["health"]["state"] == "ok"
        assert doc["input"] == {}
        assert doc["output"]["state"] == "unknown"

    def test_common_health_contract_accepts_normalized_activity(self, writer):
        writer.set_health("degraded", "receiver quiet", since=900.0)
        writer.set_input(last_observation=990.0, rate_min=12.5, total=42, tracked=3)
        writer.set_output(
            "retrying",
            last_success=980.0,
            rate_min=10,
            total=40,
            destination="tls://example:8089",
            retry_in_s=5,
            last_error="offline",
        )
        doc = writer.as_dict(now=1000.0)
        assert doc["health"] == {
            "state": "degraded",
            "detail": "receiver quiet",
            "since": 900.0,
        }
        assert doc["input"]["last_observation"] == 990.0
        assert doc["input"]["tracked"] == 3
        assert doc["output"]["state"] == "retrying"
        assert doc["output"]["destination"] == "tls://example:8089"

    @pytest.mark.parametrize("method,state", [("health", "green"), ("output", "up")])
    def test_common_health_contract_rejects_ambiguous_states(
        self, writer, method, state
    ):
        with pytest.raises(ValueError):
            if method == "health":
                writer.set_health(state)
            else:
                writer.set_output(state)


class TestTrend:
    def test_counts_per_bucket(self, tmp_path):
        w = StatusWriter("t", path=str(tmp_path / "s.json"), trend_interval=60.0)
        for _ in range(3):
            w.record(now=600.0)
        w.record(now=660.0)
        assert w.trend(now=660.0)[-2:] == [3, 1]

    def test_idle_gap_is_zero_filled_not_compressed(self, tmp_path):
        """Silence must render as silence.

        If gaps were dropped, an hour of hearing nothing would draw the same
        sparkline as an hour of steady traffic.
        """
        w = StatusWriter("t", path=str(tmp_path / "s.json"), trend_interval=60.0)
        w.record(now=0.0)
        trend = w.trend(now=300.0)
        assert trend[-5:] == [0, 0, 0, 0, 0]
        assert sum(trend) == 1

    def test_trend_is_bounded(self, tmp_path):
        w = StatusWriter(
            "t", path=str(tmp_path / "s.json"), trend_buckets=10, trend_interval=60.0
        )
        for i in range(500):
            w.record(now=i * 60.0)
        assert len(w.trend(now=499 * 60.0)) == 10

    def test_old_buckets_drop_out_of_the_window(self, tmp_path):
        w = StatusWriter(
            "t", path=str(tmp_path / "s.json"), trend_buckets=5, trend_interval=60.0
        )
        w.record(now=0.0)
        # Far in the future: the old bucket is outside the window entirely.
        assert sum(w.trend(now=100_000.0)) == 0


class TestStaleness:
    def test_wall_t_lets_a_reader_detect_a_stopped_gateway(self, writer):
        """The whole point of wall_t.

        `recent` looks identical for a gateway that is quiet and one that died
        ten minutes ago. Only the write timestamp distinguishes them.
        """
        writer.record(now=1000.0, tail="N1")
        doc = writer.as_dict(now=1000.0)
        assert doc["wall_t"] == 1000.0
        # A reader at t=2000 can see the document is 1000s old.
        assert doc["wall_t"] < 2000.0

    def test_uptime_reported(self, writer):
        assert writer.as_dict(now=1600.0)["uptime_s"] == 600.0


class TestWrite:
    def test_writes_valid_json(self, writer):
        assert writer.write(now=1000.0) is True
        doc = json.loads(open(writer.path).read())
        assert doc["app"] == "testcot"
        assert doc["version"] == "1.2.3"

    def test_creates_the_runtime_directory(self, tmp_path):
        w = StatusWriter("t", path=str(tmp_path / "deep" / "nested" / "s.json"))
        assert w.write(force=True) is True
        assert os.path.exists(w.path)

    def test_rate_limited(self, writer):
        assert writer.write(now=1000.0) is True
        assert writer.write(now=1000.5) is False
        assert writer.write(now=1002.0) is True

    def test_force_bypasses_the_rate_limit(self, writer):
        writer.write(now=1000.0)
        assert writer.write(now=1000.1, force=True) is True

    def test_replace_is_atomic_so_readers_never_see_a_partial_file(self, writer):
        """Cockpit's watcher fires on change and would parse a truncated doc.

        Verified by checking that no temp file survives and the target is only
        ever a complete document.
        """
        for i in range(20):
            writer.record(now=1000.0 + i, seq=i)
            writer.write(now=1000.0 + i, force=True)
            json.loads(open(writer.path).read())  # never raises
        leftovers = [
            f
            for f in os.listdir(os.path.dirname(writer.path))
            if f.startswith(".status-")
        ]
        assert leftovers == []


class TestWriteFailureIsSurvivable:
    """Moving CoT is the job; reporting on it is not."""

    def _readonly_writer(self, tmp_path):
        d = tmp_path / "ro"
        d.mkdir()
        w = StatusWriter("t", path=str(d / "sub" / "status.json"))
        d.chmod(stat.S_IRUSR | stat.S_IXUSR)  # no write permission
        return w, d

    def test_write_failure_does_not_raise(self, tmp_path):
        w, d = self._readonly_writer(tmp_path)
        try:
            assert w.write(force=True) is False  # returns, does not explode
        finally:
            d.chmod(stat.S_IRWXU)

    def test_write_failure_is_counted_not_silent(self, tmp_path):
        """Swallowing this invisibly is how a UI shows an hour-old lie."""
        w, d = self._readonly_writer(tmp_path)
        try:
            for _ in range(3):
                w.write(force=True)
            assert w.write_errors == 3
        finally:
            d.chmod(stat.S_IRWXU)

    def test_write_errors_surface_in_the_document(self, writer):
        """So the UI can say "stale" instead of rendering it as fact."""
        assert "write_errors" in writer.as_dict(now=1000.0)

    def test_failure_is_logged_once_not_per_message(self, tmp_path, caplog):
        """A gateway at 100 msg/s must not fill the journal with this."""
        w, d = self._readonly_writer(tmp_path)
        try:
            with caplog.at_level("WARNING"):
                for _ in range(50):
                    w.write(force=True)
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) == 1
        finally:
            d.chmod(stat.S_IRWXU)

    def test_unserialisable_field_does_not_kill_the_gateway(self, writer):
        """A gateway may hand us an object json cannot encode."""

        class Weird:
            pass

        writer.record(now=1000.0, thing=Weird())
        assert writer.write(now=1000.0, force=True) is True
        json.loads(open(writer.path).read())  # encoded via default=str


class TestStatusPath:
    def test_uses_run_by_default_when_writable(self, monkeypatch):
        monkeypatch.setattr(os, "access", lambda p, m: True)
        assert status_path("acarscot") == f"{DEFAULT_STATUS_ROOT}/acarscot/status.json"

    def test_falls_back_when_run_is_not_writable(self, monkeypatch, tmp_path):
        """A gateway run from a dev shell should still produce a status file.

        Otherwise the panel is empty during development and the developer
        concludes the feature is broken.
        """
        monkeypatch.setattr(os, "access", lambda p, m: False)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        assert status_path("acarscot") == str(tmp_path / "acarscot" / "status.json")

    def test_uses_systemd_runtime_directory_when_run_root_is_not_writable(
        self, monkeypatch
    ):
        """RuntimeDirectory is writable by the service; /run itself is not."""
        app_dir = f"{DEFAULT_STATUS_ROOT}/acarscot"
        monkeypatch.setattr(os.path, "isdir", lambda path: path == app_dir)
        monkeypatch.setattr(
            os,
            "access",
            lambda path, mode: path == app_dir and mode == os.W_OK,
        )
        assert status_path("acarscot") == f"{app_dir}/status.json"

    def test_explicit_root_wins(self, tmp_path):
        assert status_path("x", root=str(tmp_path)).startswith(str(tmp_path))


class TestSingleWriter:
    """Two writers on one path is silent damage, so it must not be silent.

    Each write serialises a whole document, so two processes sharing an
    app_name do not merge: the file alternates between two disjoint sets of
    counters and every reader sees whichever wrote last. Three separate
    gateway integrations hit this independently, which is why the class now
    detects it rather than only documenting it.
    """

    def test_warns_once_when_another_live_process_owns_the_file(self, tmp_path, caplog):
        path = str(tmp_path / "status.json")
        # A document written by a DIFFERENT but live pid: our own parent works,
        # and is guaranteed to exist without inventing one.
        other_pid = os.getppid()
        with open(path, "w") as handle:
            json.dump({"app": "other", "pid": other_pid, "wall_t": 1000.0}, handle)

        w = StatusWriter("t", path=path)
        with caplog.at_level("WARNING"):
            w.write(now=1000.0, force=True)
            w._last_contention_check = 0.0  # allow a second check
            w.write(now=2000.0, force=True)

        warnings = [r for r in caplog.records if "also being written" in r.getMessage()]
        assert len(warnings) == 1, "must warn, and only once"
        assert w.contended_with == other_pid

    def test_contention_is_surfaced_in_the_document(self, tmp_path):
        """So a UI can say the figures may not be this gateway's."""
        path = str(tmp_path / "status.json")
        with open(path, "w") as handle:
            json.dump({"app": "other", "pid": os.getppid(), "wall_t": 1.0}, handle)
        w = StatusWriter("t", path=path)
        w.write(now=1000.0, force=True)
        assert json.loads(open(path).read())["contended_with"] == os.getppid()

    def test_our_own_file_is_not_contention(self, tmp_path, caplog):
        w = StatusWriter("t", path=str(tmp_path / "status.json"))
        with caplog.at_level("WARNING"):
            w.write(now=1000.0, force=True)
            w._last_contention_check = 0.0
            w.write(now=2000.0, force=True)
        assert w.contended_with is None
        assert not [r for r in caplog.records if "also being written" in r.getMessage()]

    def test_a_dead_pid_is_not_contention(self, tmp_path, caplog):
        """Our own previous run left this behind; taking it over is correct."""
        path = str(tmp_path / "status.json")
        # PID 2^22 is above the default pid_max on Linux, so it cannot be live.
        with open(path, "w") as handle:
            json.dump({"app": "old", "pid": 4194304, "wall_t": 1.0}, handle)
        w = StatusWriter("t", path=path)
        with caplog.at_level("WARNING"):
            w.write(now=1000.0, force=True)
        assert w.contended_with is None

    def test_missing_or_corrupt_file_is_not_contention(self, tmp_path):
        path = str(tmp_path / "status.json")
        w = StatusWriter("t", path=path)
        w.write(now=1000.0, force=True)  # absent
        with open(path, "w") as handle:
            handle.write("{not json")
        w._last_contention_check = 0.0
        w.write(now=2000.0, force=True)  # corrupt
        assert w.contended_with is None

    def test_check_does_not_run_on_every_write(self, tmp_path):
        """The correct case must cost nothing."""
        w = StatusWriter("t", path=str(tmp_path / "status.json"), min_write_interval=0)
        calls = []
        original = w._check_sole_writer
        w._check_sole_writer = lambda now: (calls.append(now), original(now))[1]
        for i in range(20):
            w.write(now=1000.0 + i, force=True)
        # Called every time, but the expensive read is rate-limited inside.
        assert len(calls) == 20
        assert w._last_contention_check == 1000.0
