#!/usr/bin/env python3
# Copyright Sensors & Signals LLC https://www.snstac.com/
# SPDX-License-Identifier: Apache-2.0
"""Runtime status for pytak gateways, for management UIs to read.

A gateway that is working and a gateway that is wedged look identical from the
outside: both are "active (running)" to systemd, and both hold a socket open.
The only difference is whether contacts are still arriving, and until now
nothing in pytak recorded that. Operators were left reading journal text.

This module gives every gateway a small, bounded, machine-readable status file:

    /run/<app_name>/status.json

containing lifetime counters, a per-minute trend suitable for a sparkline, and
a ring buffer of the most recent contacts. Cockpit plugins read it with
``cockpit.file().watch()``, so the UI updates on write with no polling.

Three properties matter more than the schema:

**A stats failure must never take down the gateway.** Moving CoT is the job;
reporting on it is not. Every write is wrapped, and failures are counted rather
than raised.

**But silence must not look like calm.** Swallowing errors invisibly is how you
get a UI that cheerfully reports an idle gateway when really the status file has
been unwritable for an hour. Write failures are counted in ``write_errors`` and
logged once, and the file carries ``wall_t`` so a reader can tell "quiet" from
"stopped updating" -- see :meth:`StatusWriter.write`.

**It must be bounded.** A gateway runs for months. ``recent`` is a ring buffer
and the trend is a fixed number of buckets, so the file has a ceiling size no
matter how much traffic passes through.

**One writer per file.** Each write serialises a WHOLE document, so two
processes sharing an ``app_name`` do not merge -- the file alternates between
two disjoint sets of counters, once a second, and every reader sees whichever
process wrote last. A gateway with several workers should give the writer to
the single choke point they all feed, not to each worker.

This is easy to get wrong and invisible when you do, so :class:`StatusWriter`
detects it: if the file it is about to replace was written by a different live
process, it says so once rather than silently fighting over it.
"""

import json
import logging
import os
import tempfile
import time
from collections import deque
from typing import Any, Dict, List, Optional

__all__ = ["StatusWriter", "status_path"]

# Where systemd's RuntimeDirectory= lands. tmpfs, so this costs no flash wear
# on the SD cards these gateways run from -- which is why it is not /var.
DEFAULT_STATUS_ROOT: str = "/run"

# Enough recent contacts to show a meaningful feed without turning the status
# file into a log. The UI shows ~10; the extra headroom means a burst is still
# visible to a reader that arrives slightly late.
DEFAULT_MAX_RECENT: int = 25

# One bucket per minute for an hour: a sparkline with enough history to show a
# trend, and a hard bound on file size.
DEFAULT_TREND_BUCKETS: int = 60
DEFAULT_TREND_INTERVAL: float = 60.0


def status_path(app_name: str, root: Optional[str] = None) -> str:
    """Return the status file path for ``app_name``.

    Falls back to ``XDG_RUNTIME_DIR`` and then to the system temp directory, so
    a gateway run from a developer shell -- with no systemd
    ``RuntimeDirectory=`` and no write access to /run -- still produces a status
    file instead of silently producing nothing.
    """
    if root is None:
        root = DEFAULT_STATUS_ROOT
        app_runtime_dir = os.path.join(root, app_name)

        # Under systemd, RuntimeDirectory=<app_name> is owned by the service
        # account while /run itself remains root-only. Checking only /run made
        # every unprivileged gateway incorrectly fall back to /tmp even though
        # its intended runtime directory already existed and was writable.
        app_runtime_writable = os.path.isdir(app_runtime_dir) and os.access(
            app_runtime_dir, os.W_OK
        )
        if not app_runtime_writable and not os.access(root, os.W_OK):
            root = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(root, app_name, "status.json")


class StatusWriter:
    """Collects gateway activity and writes it out as JSON.

    Typical use from a worker::

        self.status = StatusWriter("acarscot", version=acarscot.__version__)
        ...
        self.status.count("rx")
        self.status.record(tail="N954SW", flight="OO5738", placed=True)
        self.status.write()

    :param app_name: Gateway name; also the /run subdirectory.
    :param path: Explicit path, overriding :func:`status_path`.
    :param version: Gateway version, surfaced in the UI.
    :param max_recent: Ring buffer depth for recent contacts.
    :param trend_buckets: Number of trend buckets to retain.
    :param trend_interval: Seconds per trend bucket.
    :param min_write_interval: Floor between writes; see :meth:`write`.
    """

    def __init__(
        self,
        app_name: str,
        path: Optional[str] = None,
        version: Optional[str] = None,
        max_recent: int = DEFAULT_MAX_RECENT,
        trend_buckets: int = DEFAULT_TREND_BUCKETS,
        trend_interval: float = DEFAULT_TREND_INTERVAL,
        min_write_interval: float = 1.0,
        now: Optional[float] = None,
    ) -> None:
        self.app_name = app_name
        self.version = version
        self.path = path or status_path(app_name)
        self.max_recent = max_recent
        self.trend_buckets = trend_buckets
        self.trend_interval = trend_interval
        self.min_write_interval = min_write_interval

        self._logger = logging.getLogger(__name__)
        self._started = now if now is not None else time.time()
        self._counters: Dict[str, int] = {}
        self._recent: deque = deque(maxlen=max_recent)
        self._extra: Dict[str, Any] = {}

        # Trend is kept as (bucket_index, count) so an idle gap costs nothing
        # to store; gaps are filled with zeros only at render time.
        self._trend: deque = deque(maxlen=trend_buckets)

        self.write_errors: int = 0
        self._logged_write_error = False
        self._last_write: float = 0.0
        self._pid = os.getpid()
        self._last_contention_check: float = 0.0
        self._logged_contention = False
        #: Set when another live process is found writing the same file.
        self.contended_with: Optional[int] = None

    # -- collection -------------------------------------------------------

    def count(self, key: str, n: int = 1) -> None:
        """Increment a lifetime counter, and the current trend bucket.

        Only the ``rx`` counter drives the trend, because a sparkline of "things
        that arrived" is the one an operator reads as "is it hearing anything".
        """
        self._counters[key] = self._counters.get(key, 0) + n

    def record(self, now: Optional[float] = None, **fields: Any) -> None:
        """Add a contact to the recent ring buffer and advance the trend.

        ``fields`` are gateway-specific and passed through verbatim: a tail
        number and ACARS label here, an MMSI and vessel name there. The UI
        renders whatever columns it is given rather than imposing a schema, so
        adding a field to a gateway needs no change to this module.
        """
        now = now if now is not None else time.time()
        entry = {"t": round(now, 3)}
        entry.update(fields)
        self._recent.append(entry)
        self._bump_trend(now)

    def set(self, **fields: Any) -> None:
        """Set free-form top-level fields, e.g. a tracked-object count."""
        self._extra.update(fields)

    def _bump_trend(self, now: float) -> None:
        bucket = int(now // self.trend_interval)
        if self._trend and self._trend[-1][0] == bucket:
            self._trend[-1] = (bucket, self._trend[-1][1] + 1)
        else:
            self._trend.append((bucket, 1))

    # -- rendering --------------------------------------------------------

    def trend(self, now: Optional[float] = None) -> List[int]:
        """Return contact counts per bucket, oldest first, gaps zero-filled.

        Zero-filling happens here rather than at collection time so that a
        gateway idle for an hour costs no memory, and so the sparkline shows
        the silence honestly instead of compressing it away.
        """
        now = now if now is not None else time.time()
        current = int(now // self.trend_interval)
        oldest = current - self.trend_buckets + 1
        counts = {b: c for b, c in self._trend if b >= oldest}
        return [counts.get(b, 0) for b in range(oldest, current + 1)]

    def as_dict(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Build the status document."""
        now = now if now is not None else time.time()
        doc: Dict[str, Any] = {
            "app": self.app_name,
            "version": self.version,
            # Unix time of this write. A reader compares it to its own clock to
            # distinguish "no contacts lately" from "this gateway stopped
            # writing", which look the same if you only inspect `recent`.
            "wall_t": round(now, 3),
            "uptime_s": round(now - self._started, 1),
            "pid": os.getpid(),
            "counters": dict(self._counters),
            "trend": self.trend(now=now),
            "trend_interval_s": self.trend_interval,
            "recent": list(self._recent),
            # Surfaced deliberately: if this is non-zero the UI is showing stale
            # data and should say so rather than quietly rendering it as fact.
            "write_errors": self.write_errors,
        }
        if self.contended_with is not None:
            # A reader seeing this knows the figures may be from another
            # process entirely, and should say so rather than render them.
            doc["contended_with"] = self.contended_with
        doc.update(self._extra)
        return doc

    # -- output -----------------------------------------------------------


    def _check_sole_writer(self, now: float) -> None:
        """Warn once if another live process is writing this same file.

        Two writers on one path is not a crash, which is what makes it nasty:
        the file simply alternates between two disjoint documents and whichever
        wrote last wins. A UI then shows counters that flicker between two
        gateways' worth of traffic, and nothing anywhere reports a problem.

        Checked periodically rather than per write, and only until it has
        something to say, so the common (correct) case costs nothing.
        """
        if self._logged_contention or (now - self._last_contention_check) < 30.0:
            return
        self._last_contention_check = now
        try:
            with open(self.path, "r") as handle:
                other = json.load(handle)
        except (OSError, ValueError):
            return  # absent or mid-replace; nothing to conclude

        pid = other.get("pid")
        if not isinstance(pid, int) or pid == self._pid:
            return

        try:
            os.kill(pid, 0)  # signal 0: liveness test, sends nothing
        except ProcessLookupError:
            return  # a previous run of ours; taking the file over is correct
        except OSError:
            pass  # exists but not ours to signal -- still a live process

        self.contended_with = pid
        self._logged_contention = True
        self._logger.warning(
            "Status file %s is also being written by PID %s. Each write "
            "replaces the whole document, so the two will overwrite one "
            "another and readers will see only whichever wrote last. Give the "
            "StatusWriter to a single choke point rather than to each worker.",
            self.path,
            pid,
        )

    def write(self, now: Optional[float] = None, force: bool = False) -> bool:
        """Write the status file atomically. Returns True if written.

        Rate-limited to ``min_write_interval`` so a gateway taking hundreds of
        messages per second does not spend its time serialising JSON; callers
        can therefore call this on every message without thinking about it.

        The write is to a temporary file in the same directory followed by
        :func:`os.replace`, so a reader polling the file never observes a
        partially written document -- a real hazard here, because Cockpit's
        file watcher fires on change and would otherwise parse a truncated
        object and render an empty panel.

        Never raises. A gateway must not die because it could not write a
        status file, but the failure is counted into ``write_errors`` and
        logged once so it is not invisible.
        """
        now = now if now is not None else time.time()
        if not force and (now - self._last_write) < self.min_write_interval:
            return False

        self._check_sole_writer(now)

        try:
            directory = os.path.dirname(self.path)
            os.makedirs(directory, exist_ok=True)
            payload = json.dumps(self.as_dict(now=now), default=str)

            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".status-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as handle:
                    handle.write(payload)
                os.replace(tmp, self.path)
            except BaseException:
                # Do not leave the temp file behind on failure; a gateway that
                # fails to write once will usually fail repeatedly, and that
                # would fill the runtime directory.
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

            self._last_write = now
            return True
        except Exception as exc:  # noqa: BLE001 -- see docstring
            self.write_errors += 1
            if not self._logged_write_error:
                self._logged_write_error = True
                self._logger.warning(
                    "Could not write status to %s (%s). The gateway continues; "
                    "management UIs will show stale or missing status.",
                    self.path,
                    exc,
                )
            return False
