"""Exercise the unchanged descriptor supervisor with an in-memory pipe peer.

Only the OS process/USB observations are modeled. The production runner still
owns its five admission checks, original deadlines, READY/release parsing,
runtime-file inspection, cleanup and final evidence derivation. No native
helper, process, DLL, USB handle or camera is opened by this peer.
"""

from types import SimpleNamespace
import time

import pytest

from rocell.providers.windows import owned_usb_identity_runner as runner
from rocell.providers.windows import usb_identity_protocol as wire
from test_owned_usb_identity_runner import FaultOwner, usb_fixture
from test_physical_usb_presence_binding import observed_native


# Capture before parent public fixtures replace the effect observer. Restoring
# this explicit test subclass never installs a production bypass or backend.
REAL_RUNNER = runner.OwnedUsbIdentityRunner
REAL_RUN = runner._Runner.run


class ModeledObservedPipe(FaultOwner):
    """Fixed protocol peer; supplied preparation is never interpreted as argv."""

    def __init__(self, prepared, cancellation, *, record=None):
        super().__init__(
            SimpleNamespace(request=prepared.request, cancellation=cancellation), None
        )
        self.record = {} if record is None else record
        self.record.update(
            provenance="IN_MEMORY_PIPE_PEER_NO_PROCESS_OR_USB", releases=0
        )

    def start(self, registration, request_wire, *, check, keep_stdin_open):
        assert request_wire == self.case.request.wire() and keep_stdin_open is True
        super().start(
            registration, request_wire, check=check, keep_stdin_open=keep_stdin_open
        )
        self.peak_handles, self.peak_processes = 14, 1

    def send_final_input(self, release_wire, *, check):
        check()
        ready = wire.parse_usb_identity_ready(
            self.stdout,
            expected_request_sha256=self.case.request.request_sha256,
            expected_child_pid=self.pid,
        )
        assert release_wire == wire.usb_identity_release(self.case.request, ready)
        assert self.record["releases"] == 0
        self.record["releases"] += 1
        observation = observed_native(self.case.request)
        result = dict(
            schema=wire.RESULT_SCHEMA,
            request_sha256=self.case.request.request_sha256,
            child_pid=self.pid,
            challenge_sha256=ready.challenge_sha256,
            permit_sha256=self.case.request.to_dict()["permit_sha256"],
            native_receipt=observation.to_dict(),
        )
        self.stdout += wire.canonical(result)
        self.written += len(release_wire)
        self.returncode = 0

    def cleanup(self, deadline_ns):
        result = super().cleanup(deadline_ns)
        self.stdout_eof = self.stderr_eof = True
        return result


@pytest.fixture
def runner_case(monkeypatch):
    case = usb_fixture(incapable=False)
    monkeypatch.setattr(runner, "source_fingerprint", lambda _: "a" * 64)
    clock = SimpleNamespace(now=time.monotonic_ns(), wall=time.time_ns())
    original = clock.now
    # Virtual elapsed time makes boundary tests deterministic, without changing
    # the production deadline constants or permit. The original scope's own
    # elapsed-time guard is real; modeled delays are additionally checked by
    # the runner that is under test.
    monkeypatch.setattr(
        runner,
        "time",
        SimpleNamespace(
            monotonic_ns=lambda: clock.now,
            time_ns=lambda: clock.wall + clock.now - original,
        ),
    )
    peer = ModeledObservedPipe(case.prepared, case.cancellation)
    monkeypatch.setattr(runner, "_new_owner", lambda: peer)
    original_revalidate = case.transaction.revalidate_consumed_permit

    def run(durations):
        def delayed(permit):
            index = case.transaction.checks
            original_revalidate(permit)
            clock.now += int(durations[index] * 1e9)

        monkeypatch.setattr(case.transaction, "revalidate_consumed_permit", delayed)
        owner = REAL_RUNNER(
            case.prepared,
            permit=case.permit,
            authorization=case.scope,
            application_guard=lambda: None,
        )
        evidence = REAL_RUN(
            owner, cancellation=case.cancellation, deadline_ns=case.deadline_ns
        )
        return evidence

    return case, peer, run


def test_real_runner_retains_complete_modeled_observation(runner_case):
    case, peer, run = runner_case
    evidence = run((0.1,) * 5)
    assert evidence.status == "OBSERVED", evidence.to_dict()["primary_error"]
    assert evidence.usb_cleanup_confirmed and evidence.process_cleanup_confirmed
    assert case.transaction.checks == 5 and case.transaction.acks == 1
    assert peer.cleanup_calls == peer.record["releases"] == 1
    assert evidence.bounded_effect_summary()["actual_counts"]["hub_open_attempts"] == 3
    assert evidence.to_dict()["physical_authority"] is False


def test_real_runner_keeps_five_second_ready_deadline(runner_case):
    case, peer, run = runner_case
    evidence = run((0.1, 0.1, 2.6, 2.6, 0.1))
    assert evidence.status == "FAILED"
    assert evidence.to_dict()["primary_error"] == "USB_ADMISSION_TIMED_OUT"
    assert peer.record["releases"] == 0 and case.transaction.checks == 4
    assert evidence.bounded_effect_summary()["actual_counts"] is None


def test_real_runner_keeps_twenty_second_post_pin_floor(runner_case):
    case, peer, run = runner_case
    evidence = run((3, 3, 0.1, 0.1, 0.1))
    assert evidence.status == "FAILED"
    assert evidence.to_dict()["primary_error"] == "FULL_USB_LIFETIME_DOES_NOT_FIT"
    assert peer.record["releases"] == 0 and not peer.created
    assert case.transaction.checks == 2
    assert evidence.bounded_effect_summary()["actual_counts"]["hub_open_attempts"] == 0


def test_real_runner_does_not_erase_late_result_counts(runner_case):
    case, peer, run = runner_case
    evidence = run((0.1, 0.1, 0.1, 0.1, 19))
    assert evidence.status == "TIMED_OUT"
    assert peer.record["releases"] == 1 and case.transaction.checks == 5
    assert evidence.bounded_effect_summary()["actual_counts"]["hub_open_attempts"] == 3
    assert not evidence.bounded_effect_summary()["current_complete"]
