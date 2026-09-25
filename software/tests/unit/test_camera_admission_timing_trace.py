"""Fast observer contracts; no original store, fake clock, process or device."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time

import pytest

import camera_admission_timing_trace as timing


def test_exact_arguments_return_identity_and_real_monotonic_observations():
    trace = timing.CameraAdmissionTimingTrace()
    argument, keyword, answer = object(), object(), object()
    seen = []

    def delegated(value, *, named):
        seen.append((value, named))
        return answer

    observed = trace.wrap(delegated, "MODELED.delegated")
    assert observed.__wrapped__ is delegated
    assert timing.monotonic_ns is time.monotonic_ns
    before = time.monotonic_ns()
    with trace.action("physical_camera_probe"):
        assert observed(argument, named=keyword) is answer
    after = time.monotonic_ns()
    assert seen == [(argument, keyword)]
    result = trace.snapshot()
    entry = result["entries"][0]
    assert before <= entry["started_ns"] <= entry["finished_ns"] <= after
    assert entry["duration_ns"] == entry["finished_ns"] - entry["started_ns"]
    assert entry["outcome"] == "RETURNED"
    assert entry["action_id"] == "physical_camera_probe"
    assert result["observer_errors"] == result["unfinished_spans"] == 0
    assert result["current_action"] is None
    result["entries"][0]["outcome"] = "MUTATED_EXPORT"
    assert trace.snapshot()["entries"][0]["outcome"] == "RETURNED"


@pytest.mark.parametrize("exception_type", [ValueError, KeyboardInterrupt, SystemExit])
def test_exact_exception_object_propagates_without_retry(exception_type):
    trace = timing.CameraAdmissionTimingTrace()
    failure = exception_type("MODELED delegated failure")
    calls = []

    def delegated(value):
        calls.append(value)
        raise failure

    with pytest.raises(exception_type) as raised:
        with trace.action("physical_camera_probe"):
            trace.wrap(delegated, "MODELED.failure")("one invocation")
    assert raised.value is failure
    assert calls == ["one invocation"]
    result = trace.snapshot()
    assert result["entries"][0]["outcome"] == "RAISED"
    assert result["finished_spans"] == 1 and result["current_action"] is None


def test_entry_cap_drops_only_observations_and_never_delegated_calls():
    trace = timing.CameraAdmissionTimingTrace(max_entries=2)
    calls = []

    def delegated(value):
        calls.append(value)
        return value

    observed = trace.wrap(delegated, "MODELED.capacity")
    with trace.action("physical_camera_configuration_capture"):
        assert [observed(number) for number in range(5)] == list(range(5))
    result = trace.snapshot()
    assert calls == list(range(5))
    assert result["retained_entries"] == result["max_entries"] == 2
    assert result["dropped_entries"] == 3
    assert result["started_spans"] == result["finished_spans"] == 5
    assert result["unfinished_spans"] == result["observer_errors"] == 0


def test_inherited_method_and_module_function_restore_even_after_failure():
    trace = timing.CameraAdmissionTimingTrace()

    class Base:
        def run(self, value, *, keyword):
            return value, keyword

    class Child(Base):
        pass

    def function(value):
        return value

    module = SimpleNamespace(function=function)
    assert "run" not in vars(Child)
    failure = ValueError("MODELED outer action failure")
    with pytest.raises(ValueError) as raised:
        with trace.instrument(
            [(Child, "run", "Child.run"), (module, "function", "module.function")]
        ), trace.action("physical_camera_probe"):
            assert Child.run is not Base.run
            assert Child().run("one", keyword="two") == ("one", "two")
            assert module.function("three") == "three"
            raise failure
    assert raised.value is failure
    assert "run" not in vars(Child) and Child.run is Base.run
    assert module.function is function
    assert trace.snapshot()["retained_entries"] == 2


def test_worker_thread_inherits_action_label_and_nested_times_are_inclusive():
    trace = timing.CameraAdmissionTimingTrace()
    inner = trace.wrap(lambda: object(), "MODELED.inner")
    outer = trace.wrap(lambda: inner(), "MODELED.outer")
    with ThreadPoolExecutor(max_workers=1) as worker:
        with trace.action("physical_camera_probe"):
            assert worker.submit(outer).result() is not None
    result = trace.snapshot()
    outside, inside = result["entries"]
    assert outside["function"] == "MODELED.outer"
    assert inside["function"] == "MODELED.inner"
    assert outside["thread_id"] == inside["thread_id"]
    assert all(row["action_id"] == "physical_camera_probe" for row in result["entries"])
    assert outside["started_ns"] <= inside["started_ns"]
    assert inside["finished_ns"] <= outside["finished_ns"]
    assert (
        result["timing_semantics"] == "INCLUSIVE_NESTED_SPANS_DO_NOT_SUM_AS_EXCLUSIVE"
    )


def test_calls_outside_action_delegate_without_recording():
    trace = timing.CameraAdmissionTimingTrace()
    answer = object()
    assert trace.wrap(lambda: answer, "MODELED.outside")() is answer
    assert trace.snapshot()["started_spans"] == 0


def test_snapshot_exposes_unfinished_span_without_fabricating_an_end_time():
    trace = timing.CameraAdmissionTimingTrace()

    def delegated():
        during = trace.snapshot()
        assert during["unfinished_spans"] == 1
        assert during["entries"][0]["outcome"] == "IN_PROGRESS"
        assert during["entries"][0]["finished_ns"] is None
        assert during["entries"][0]["duration_ns"] is None

    with trace.action("physical_camera_probe"):
        trace.wrap(delegated, "MODELED.inflight")()
    assert trace.snapshot()["unfinished_spans"] == 0


def test_observer_failure_does_not_replace_delegated_return_or_exception(monkeypatch):
    trace = timing.CameraAdmissionTimingTrace()
    answer = object()
    failure = ValueError("MODELED actual failure")

    def observer_failure(*args):
        raise RuntimeError("MODELED observer failure, not a clock override")

    def delegated_failure():
        raise failure

    monkeypatch.setattr(trace, "_begin", observer_failure)
    monkeypatch.setattr(trace, "_finish", observer_failure)
    with trace.action("physical_camera_probe"):
        assert trace.wrap(lambda: answer, "MODELED.return")() is answer
        with pytest.raises(ValueError) as raised:
            trace.wrap(delegated_failure, "MODELED.raise")()
    assert raised.value is failure
    assert trace.snapshot()["observer_errors"] == 4
    assert timing.monotonic_ns is time.monotonic_ns


@pytest.mark.parametrize("limit", [None, True, 0, -1, 4097, 1.5])
def test_invalid_entry_caps_reject(limit):
    with pytest.raises(ValueError, match="entry cap"):
        timing.CameraAdmissionTimingTrace(max_entries=limit)
