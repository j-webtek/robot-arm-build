"""Test-only presence observations with the real runner's unchanged time gates.

No native process is modeled as actually executed. Original admission callbacks
may be genuine consumed-M1 checks in the public acceptance fixture; this module
never changes a permit, budget, verifier or original reference to make one fit.
"""

from copy import deepcopy
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch
import time

import pytest

from rocell.providers.windows import owned_usb_presence_evidence as owned
from rocell.providers.windows import owned_usb_presence_runner as runner
from rocell.providers.windows import usb_presence_protocol as wire
from test_physical_usb_presence_dispatch import modeled_owned_presence
from test_physical_usb_presence_campaign import (
    case,
    prerequisites,
    workspace,
    no_process_or_devices,
)


def run_timed_presence_model(
    prepared,
    *,
    permit,
    authorization,
    guard,
    cancellation,
    deadline_ns,
    record,
    monotonic_ns=time.monotonic_ns,
    utc_ns=time.time_ns,
):
    """Retain literal timing failures; never force the expected ABSENT outcome."""
    started, utc = monotonic_ns(), utc_ns()
    checks = []
    state = dict(owner=False, created=False, released=False, ready=b"", release=b"")
    run_deadline = deadline_ns - 2_000_000_000
    retained_run_deadline = None
    admission_deadline = None
    native_utc = None
    primary = None
    record.update(
        provenance="EXPLICITLY_MODELED_NATIVE_AND_PROCESS_OBSERVATIONS",
        preparation=prepared.to_dict(),
        permit_sha256=permit.permit_sha256,
        started_monotonic_ns=started,
        started_utc_ns=utc,
        original_deadline_ns=deadline_ns,
        required_lifetime_ns=prepared.required_lifetime_ns,
        scope_checks=checks,
        acknowledgement=None,
        raw_finalization_input=None,
        error=None,
    )

    def need(ok, code):
        if not ok:
            raise runner.OwnedUsbPresenceRunnerError(code)

    def current():
        need(not cancellation.is_set(), "CANCELLED")
        need(monotonic_ns() < run_deadline, "TIMED_OUT")
        need(guard() is None, "USB_GUARD_CANNOT_GRANT_AUTHORITY")
        need(not cancellation.is_set(), "CANCELLED")
        need(monotonic_ns() < run_deadline, "TIMED_OUT")

    def boundary(name):
        current()
        row = dict(
            boundary=name,
            started_ns=monotonic_ns(),
            finished_ns=monotonic_ns(),
            passed=False,
        )
        checks.append(row)
        try:
            authorization.revalidate(permit)
            current()
            row["passed"] = True
        finally:
            row["finished_ns"] = monotonic_ns()

    try:
        current()
        need(
            monotonic_ns() + prepared.required_lifetime_ns <= deadline_ns,
            "FULL_USB_LIFETIME_DOES_NOT_FIT",
        )
        acknowledgement = dict(started_ns=monotonic_ns(), finished_ns=None)
        record["acknowledgement"] = acknowledgement
        try:
            authorization.acknowledge(permit)
        finally:
            acknowledgement["finished_ns"] = monotonic_ns()
        boundary("PRE_PIN")
        state["owner"] = True
        boundary("POST_PIN")
        record["post_pin_remaining_ns"] = deadline_ns - monotonic_ns()
        need(
            monotonic_ns() + prepared.required_lifetime_ns <= deadline_ns,
            "FULL_USB_LIFETIME_DOES_NOT_FIT",
        )
        run_deadline = min(deadline_ns - 2_000_000_000, monotonic_ns() + 13_000_000_000)
        retained_run_deadline = run_deadline
        admission_deadline = monotonic_ns() + 5_000_000_000
        record["run_deadline_ns"] = run_deadline
        record["admission_deadline_ns"] = admission_deadline
        current()
        need(monotonic_ns() < admission_deadline, "USB_ADMISSION_TIMED_OUT")
        boundary("PRE_START")
        current()
        need(monotonic_ns() < admission_deadline, "USB_ADMISSION_TIMED_OUT")
        state["created"] = True
        ready = dict(
            schema=wire.READY_SCHEMA,
            request_sha256=prepared.request.sha256,
            permit_sha256=permit.permit_sha256,
            child_pid=31415,
            challenge="e" * 64,
        )
        state["ready"] = wire.canonical(ready) + b"\n"
        state["release"] = (
            wire.encode_usb_presence_release(ready, prepared.request, child_pid=31415)
            + b"\n"
        )
        boundary("PRE_RELEASE")
        current()
        moment = monotonic_ns()
        need(moment < admission_deadline, "USB_ADMISSION_TIMED_OUT")
        need(
            moment + 2_000_000_000 < run_deadline
            and moment + 4_000_000_000 <= deadline_ns,
            "USB_NATIVE_LIFETIME_DOES_NOT_FIT",
        )
        state["released"] = True
        native_utc = utc_ns()
        boundary("POST_RESULT")
    except BaseException as error:
        primary = runner._label(error)
        record["error"] = dict(
            type=type(error).__name__, code=primary, message=str(error)
        )

    record["native_started_utc_ns"] = native_utc
    record["before_retention_monotonic_ns"] = monotonic_ns()
    record["run_deadline_ns"] = retained_run_deadline
    record["released"] = state["released"]
    finalize = owned.retain_owned_usb_presence_run

    def captured_finalizer(raw):
        raw["run_deadline_ns"] = retained_run_deadline
        raw["primary_error"] = primary
        record["raw_finalization_input"] = deepcopy(raw)
        try:
            return finalize(raw)
        except BaseException as error:
            record["finalization_error"] = dict(
                type=type(error).__name__, code=runner._label(error), message=str(error)
            )
            raise

    if state["released"]:
        # A complete modeled result precedes POST_RESULT; a late failed recheck
        # cannot erase its exact native bytes/counts or become a clean outcome.
        with patch.object(owned, "retain_owned_usb_presence_run", captured_finalizer):
            result = modeled_owned_presence(
                prepared,
                deadline_ns=deadline_ns,
                checks=checks,
                started_ns=started,
                started_utc_ns=utc,
                native_started_utc_ns=native_utc,
                finished_ns=monotonic_ns(),
                finished_utc_ns=utc_ns(),
            )
    else:
        finished, utc_finished = monotonic_ns(), utc_ns()
        cleanup = finished if state["owner"] else None
        process = dict(owned.PROCESS_DEFAULTS)
        if state["created"]:
            process.update(
                created=True,
                resumed=True,
                tree_exited=True,
                returncode=2,
                pid=31415,
                written=len(prepared.request.payload) + 1,
                peak_handles=14,
                peak_processes=1,
                stdout_eof=True,
                stderr_eof=True,
            )
        raw = dict(
            schema=owned.SCHEMA,
            preparation=prepared.to_dict(),
            preparation_sha256=prepared.sha256,
            provenance="PHYSICAL_USB_PRESENCE",
            original_deadline_ns=deadline_ns,
            run_deadline_ns=retained_run_deadline,
            cleanup_started_ns=cleanup,
            cleanup_deadline_ns=(
                None if cleanup is None else min(deadline_ns, cleanup + 2_000_000_000)
            ),
            cleanup_finished_ns=cleanup,
            started_monotonic_ns=started,
            finished_monotonic_ns=finished,
            started_utc_ns=utc,
            finished_utc_ns=utc_finished,
            scope_checks=checks,
            owner_constructed=state["owner"],
            process=process,
            stdout=owned.stream_record(state["ready"], complete=True),
            stderr=owned.stream_record(b"", complete=True),
            ready_length=len(state["ready"]),
            ready_wire=owned.stream_record(state["ready"], complete=True),
            release_wire=owned.stream_record(state["release"], complete=True),
            release_write_attempted=False,
            release_check_passed=False,
            release_delivery_confirmed=False,
            result_validated=False,
            primary_error=primary,
            cleanup_errors=[],
            status="FAILED",
            physical_authority=False,
            hardware_qualified=False,
            retries=0,
        )
        result = captured_finalizer(raw)
    record["finished_monotonic_ns"] = monotonic_ns()
    record["evidence_sha256"] = result.sha256
    record["status"] = result.status
    record["actual_counts"] = result.actual_counts
    return result


def timed_case(case, *, durations, remaining=25, cancel_at=None):
    start = case.permit.issued_at_ns + 1_000_000_000
    wall = case.review.to_dict()["reviewed_at_ns"] + 100_000_000
    clock = SimpleNamespace(now=start, checks=0, acknowledged=0)
    cancellation = Event()

    class Scope:
        def acknowledge(self, permit):
            assert permit is case.permit
            clock.acknowledged += 1

        def revalidate(self, permit):
            assert permit is case.permit
            clock.now += int(durations[clock.checks] * 1e9)
            clock.checks += 1
            if clock.checks == cancel_at:
                cancellation.set()

    record = {}
    result = run_timed_presence_model(
        case.prepared,
        permit=case.permit,
        authorization=Scope(),
        guard=lambda: None,
        cancellation=cancellation,
        deadline_ns=start + int(remaining * 1e9),
        record=record,
        monotonic_ns=lambda: clock.now,
        utc_ns=lambda: wall + clock.now - start,
    )
    return result, record, clock


@pytest.mark.parametrize("remaining", (24, 25))
def test_comfortable_window_keeps_complete_absent_bytes(case, remaining):
    result, record, clock = timed_case(case, durations=(0.1,) * 5, remaining=remaining)
    assert result.status == "ABSENT" and result.released
    assert result.actual_counts == dict(
        api_calls=4, device_handle_opens=0, configuration_writes=0, frames=0
    )
    assert clock.acknowledged == 1 and clock.checks == 5
    assert record["error"] is None and record["raw_finalization_input"]
    assert record["run_deadline_ns"] <= record["original_deadline_ns"] - 2_000_000_000


def test_post_pin_full_fifteen_second_floor_refuses_before_process(case):
    result, record, clock = timed_case(case, durations=(0.6, 0.6), remaining=16)
    assert clock.checks == 2 and not result.released and result.no_attempt
    assert result.error == "FULL_USB_LIFETIME_DOES_NOT_FIT"
    assert record["post_pin_remaining_ns"] == 14_800_000_000
    assert result.actual_counts == dict(
        api_calls=0, device_handle_opens=0, configuration_writes=0, frames=0
    )


def test_original_five_second_admission_refuses_slow_prestart_and_release(case):
    # The actual01 rounded rechecks already exceeded this inner window.
    result, record, clock = timed_case(case, durations=(0.1, 0.1, 3.187, 3.188))
    assert clock.checks == 4 and not result.released and not result.no_attempt
    assert result.error == "USB_ADMISSION_TIMED_OUT"
    assert result.actual_counts is None
    assert record["scope_checks"][-1]["finished_ns"] > record["admission_deadline_ns"]
    assert result.to_dict()["ready_length"] > 0


@pytest.mark.parametrize(
    "remaining,durations",
    ((25, (0.1, 0.1, 0.1, 0.1, 13)), (16, (0.1, 0.1, 0.1, 0.1, 14))),
)
def test_late_post_result_retains_observation_but_not_clean_currentness(
    case, remaining, durations
):
    result, record, clock = timed_case(case, durations=durations, remaining=remaining)
    assert result.status == "TIMED_OUT" and result.released and clock.checks == 5
    assert result.actual_counts["api_calls"] == 4
    assert result.observation.to_dict()["outcome"] == "ABSENT"
    assert not result.bounded_effect_summary()["current_complete"]
    assert record["scope_checks"][-1]["passed"] is False


def test_post_release_cancellation_retains_raw_receipt_and_never_retries(case):
    result, record, clock = timed_case(case, durations=(0.1,) * 5, cancel_at=5)
    assert result.status == "CANCELLED" and result.released
    assert result.actual_counts["api_calls"] == 4
    assert clock.acknowledged == 1 and clock.checks == 5
    assert record["error"]["code"] == "CANCELLED"
