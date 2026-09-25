"""Bounded test-only timing; delegates unchanged and never supplies a clock.

This observer owns no production authority. Timings are inclusive nested spans,
not mutually exclusive costs. Instrumentation itself adds overhead; observations
must not be used to extend a deadline or replace a failed admission decision.
"""

from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import inspect
from threading import Lock, get_ident
from time import monotonic_ns

import pytest


class CameraAdmissionTimingTrace:
    """Observe one serialized public action across its caller/worker threads."""

    def __init__(self, *, max_entries=4096):
        if type(max_entries) is not int or not 1 <= max_entries <= 4096:
            raise ValueError("timing entry cap must be an integer from 1 to 4096")
        self._limit = max_entries
        self._lock = Lock()
        self._action = None
        self._entries = []
        self._started = self._finished = self._dropped = self._errors = 0

    @contextmanager
    def action(self, action_id):
        if type(action_id) is not str or not 1 <= len(action_id) <= 128:
            raise ValueError("one bounded action label is required")
        with self._lock:
            if self._action is not None:
                raise ValueError("public timing action scopes must be serialized")
            self._action = action_id
        try:
            yield
        finally:
            with self._lock:
                self._action = None

    def _begin(self, label):
        with self._lock:
            action = self._action
            if action is None:
                return None
            started = monotonic_ns()
            self._started += 1
            entry = None
            if len(self._entries) < self._limit:
                entry = dict(
                    sequence=self._started,
                    action_id=action,
                    function=label,
                    thread_id=get_ident(),
                    started_ns=started,
                    finished_ns=None,
                    duration_ns=None,
                    outcome="IN_PROGRESS",
                )
                self._entries.append(entry)
            else:
                self._dropped += 1
            return entry, started

    def _finish(self, token, outcome):
        if token is None:
            return
        finished = monotonic_ns()
        entry, started = token
        with self._lock:
            self._finished += 1
            if entry is not None:
                entry.update(
                    finished_ns=finished,
                    duration_ns=finished - started,
                    outcome=outcome,
                )

    def _observe(self, callback, *args):
        # Observation failures must never suppress the delegated function or
        # replace its return object/exception. Record only an error count; do
        # not invent a timestamp, renew time, retry, or inspect sensitive args.
        try:
            return callback(*args)
        except BaseException:
            self._errors += 1
            return None

    def wrap(self, function, label):
        if (
            not callable(function)
            or type(label) is not str
            or not 1 <= len(label) <= 160
        ):
            raise ValueError("a callable and bounded timing label are required")

        @wraps(function)
        def observed(*args, **kwargs):
            token = self._observe(self._begin, label)
            try:
                value = function(*args, **kwargs)
            except BaseException:
                self._observe(self._finish, token, "RAISED")
                raise
            self._observe(self._finish, token, "RETURNED")
            return value

        return observed

    @contextmanager
    def instrument(self, targets):
        """Temporarily wrap plain methods/functions; restore inherited lookup too."""
        with pytest.MonkeyPatch.context() as patch:
            for owner, name, label in targets:
                descriptor = inspect.getattr_static(owner, name)
                if isinstance(descriptor, (staticmethod, classmethod, property)):
                    raise TypeError("timing targets must be plain methods/functions")
                delegated = getattr(owner, name)
                patch.setattr(owner, name, self.wrap(delegated, label))
            yield

    def snapshot(self):
        """Detached diagnostic data only; no reads of sources, devices or clocks."""
        with self._lock:
            return dict(
                schema="rocell.test_camera_admission_timing_trace.v1",
                clock="time.monotonic_ns (unmodified real clock)",
                timing_semantics="INCLUSIVE_NESTED_SPANS_DO_NOT_SUM_AS_EXCLUSIVE",
                scope="TEST_ONLY_PUBLIC_SUCCESSOR_ACTIONS_AFTER_COMPLETE_EARLIER_HISTORY",
                max_entries=self._limit,
                retained_entries=len(self._entries),
                started_spans=self._started,
                finished_spans=self._finished,
                unfinished_spans=self._started - self._finished,
                dropped_entries=self._dropped,
                observer_errors=self._errors,
                current_action=self._action,
                entries=deepcopy(self._entries),
                argument_or_result_payloads_recorded=False,
                production_decisions_modified=False,
                deadlines_modified=False,
                physical_authority=False,
                hardware_qualified=False,
                meaning="Actual delegated calls timed in a test fixture. Nested inclusive durations overlap and tracing adds overhead. Failures remain failures; this is neither an exclusive-cost profile nor physical qualification.",
            )
