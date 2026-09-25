"""Modeled owner lifecycle; an autouse guard forbids real owner construction."""

from dataclasses import replace
import threading
import time

import pytest

from rocell.providers.windows import native_camera_activation_supervisor as module
from rocell.providers.windows import owned_worker_process as shared
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_native_camera_activation_evidence import modeled


class Clock:
    def __init__(self):
        self.tick = 1_000_000_000
        self.error = None

    def __call__(self):
        if self.error is not None:
            raise self.error
        self.tick += 1_000_000
        return self.tick


class ModelOwner:
    def __init__(self, owner, args, fault=None):
        self.__dict__.update(vars(owner))
        self.ready = args["ready_wire"]
        self.result = owner.stdout[len(self.ready) :]
        self.stdout = self.stderr = b""
        self.created = self.resumed = self.tree_exited = False
        self.stdout_eof = self.stderr_eof = False
        self.returncode = None
        self.written = self.peak_processes = self.peak_handles = 0
        self.fault = fault
        self.phase = "initial"
        self.cleaned = False

    def __getattribute__(self, name):
        if (
            name == "stdout"
            and object.__getattribute__(self, "cleaned")
            and object.__getattribute__(self, "fault") == "lose-output-after-cleanup"
        ):
            raise OSError("Do not retain arbitrary exception text")
        return object.__getattribute__(self, name)

    def pin(self, registration):
        self.handles = {1: "modeled-pin"}
        self.pins = ["modeled-pin"]
        self.peak_handles = 8
        if self.fault == "pin":
            raise OSError("MODELED_PIN_FAILURE")

    def start(self, registration, request, *, check, keep_stdin_open):
        assert keep_stdin_open is True
        check()
        if self.fault == "start":
            raise OSError("MODELED_CREATE_FAILURE")
        self.created = self.resumed = True
        self.peak_processes = 1
        self.written = len(request)
        self.stdout = self.ready
        self.phase = "ready"
        if self.fault == "wrong-pid":
            self.pid += 1
        elif self.fault == "output-before-release":
            self.stdout += self.result
        elif self.fault == "ready-overflow":
            self.stdout = b"x" * 1025
        elif self.fault == "no-ready":
            self.stdout = b"unfinished"

    def poll(self, budget):
        if (
            self.fault == "poll-ready"
            or self.phase == "result"
            and self.fault == "poll-result"
        ):
            raise RuntimeError("MODELED_POLL_FAILURE")
        if self.fault == "no-ready":
            return True
        if self.phase == "ready":
            return False
        self.returncode = 0
        self.tree_exited = self.stdout_eof = self.stderr_eof = True
        if self.fault == "no-eof":
            self.stdout_eof = False
        return True

    def send_final_input(self, wire, *, check):
        check()
        if self.fault == "send":
            raise OSError("MODELED_RELEASE_WRITE_FAILURE")
        self.written += len(wire)
        self.stdout += self.result
        self.phase = "result"
        if self.fault == "bad-result":
            self.stdout = self.ready + b"not-json"

    def cleanup(self, deadline_ns):
        self.cleaned = True
        if self.fault == "cleanup-throw":
            raise KeyboardInterrupt("Test cleanup interruption")
        self.tree_exited = self.created
        self.handles = {}
        self.pins = []
        if self.fault == "cleanup-invalid":
            return None
        if self.fault == "cleanup-resource":
            self.pins = ["modeled-unclosed-pin"]
        if self.fault == "cleanup-missing-resource":
            del self.unclosed_handles
        if self.fault == "cleanup-error":
            return ("MODELED_CLOSE_FAILED",)
        return ()


@pytest.fixture(autouse=True)
def no_physical_owner(monkeypatch):
    assert shared._UNRESOLVED_BACKEND is None

    def forbidden():
        pytest.fail("Unit test attempted real owner construction")

    monkeypatch.setattr(module, "_new_owner", forbidden)
    yield
    if shared._UNRESOLVED_BACKEND is not None:
        # Only discard this explicitly modeled owner; never clear a real hold.
        assert type(shared._UNRESOLVED_BACKEND) is ModelOwner
        shared._UNRESOLVED_BACKEND = None
    assert shared._DISPATCH_LOCK.acquire(blocking=False)
    shared._DISPATCH_LOCK.release()


def setup(tmp_path, monkeypatch, purpose="probe", fault=None):
    raw_owner, args = modeled(tmp_path, purpose)
    owner = ModelOwner(raw_owner, args, fault)
    monkeypatch.setattr(module, "_new_owner", lambda: owner)
    calls = []

    def current(prepared):
        assert prepared.payload == args["prepared"].payload
        calls.append(prepared.preparation_sha256)

    return owner, args["prepared"], calls, current


def run(prepared, current, **kwargs):
    options = dict(
        cancellation=threading.Event(),
        deadline_ns=25_000_000_000,
        _clock=Clock(),
        revalidate_consumed_permit=current,
    )
    options.update(kwargs)
    return module._supervise(prepared, prepared.registration, **options)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_complete_model_run_uses_parent_and_produces_reverifiable_record(
    tmp_path, monkeypatch, purpose
):
    owner, prepared, calls, current = setup(tmp_path, monkeypatch, purpose)
    observed = run(prepared, current)
    record = observed.run_evidence(prepared)
    assert calls == [prepared.preparation_sha256] * 2
    assert record.assessment().status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
    assert observed.before_cleanup.values()["handles_remaining"] == 1
    assert observed.after_cleanup.values()["handles_remaining"] == 0
    assert (
        observed.before_cleanup.values()["stdout"]
        == observed.after_cleanup.values()["stdout"]
    )
    assert observed.accepted_result_sha256 == digest(owner.result)
    assert not observed.unresolved_owner_retained
    assert len(canonical(observed.diagnostics())) < module.MAX_SUPERVISION_BYTES


@pytest.mark.parametrize("boundary", [1, 2])
@pytest.mark.parametrize("fault", ["deny", "cancel", "boolean"])
def test_scope_failure_never_delivers_release(tmp_path, monkeypatch, boundary, fault):
    owner, prepared, calls, ordinary = setup(tmp_path, monkeypatch)
    cancellation = threading.Event()

    def current(exact):
        ordinary(exact)
        if len(calls) == boundary:
            if fault == "deny":
                raise PermissionError("MODELED_SCOPE_DENIED")
            if fault == "cancel":
                cancellation.set()
            else:
                return False

    observed = run(prepared, current, cancellation=cancellation)
    assert observed.primary_error is not None
    assert not observed.release_check_passed and observed.accepted_result_sha256 is None
    assert owner.written == (
        0 if boundary == 1 else len(prepared.admission_request.wire())
    )
    assert owner.created == (boundary == 2)
    assert observed.run_evidence(prepared).assessment().native is None
    assert not observed.unresolved_owner_retained


@pytest.mark.parametrize(
    "fault",
    [
        "pin",
        "start",
        "wrong-pid",
        "poll-ready",
        "poll-result",
        "send",
        "output-before-release",
        "ready-overflow",
        "no-ready",
        "bad-result",
        "no-eof",
    ],
)
def test_faults_preserve_bytes_and_do_not_become_success(tmp_path, monkeypatch, fault):
    owner, prepared, _, current = setup(tmp_path, monkeypatch, fault=fault)
    observed = run(prepared, current)
    record = observed.run_evidence(prepared)
    assert record.assessment().status == "FAILED"
    assert record.assessment().native is None
    assert observed.after_cleanup.values()["stdout"] == owner.stdout
    assert not observed.unresolved_owner_retained


@pytest.mark.parametrize(
    "fault",
    [
        "cleanup-throw",
        "cleanup-invalid",
        "cleanup-resource",
        "cleanup-missing-resource",
        "cleanup-error",
    ],
)
def test_uncertain_cleanup_keeps_real_owner_reference_and_complete_native_result(
    tmp_path, monkeypatch, fault
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch, fault=fault)
    observed = run(prepared, current)
    assert observed.unresolved_owner_retained and shared._UNRESOLVED_BACKEND is owner
    record = observed.run_evidence(prepared)
    assert record.assessment().status == "FAILED"
    assert record.assessment().native is not None
    assert not record.assessment().process_cleanup_confirmed
    # A subsequent attempt cannot replace the uncertain owner.
    later = run(prepared, current)
    assert later.primary_error == "PROCESS_CLEANUP_HOLD"
    assert not later.owner_constructed and shared._UNRESOLVED_BACKEND is owner


def test_before_cleanup_bytes_survive_unavailable_later_attribute(
    tmp_path, monkeypatch
):
    owner, prepared, _, current = setup(
        tmp_path, monkeypatch, fault="lose-output-after-cleanup"
    )
    observed = run(prepared, current)
    assert observed.before_cleanup.values()["stdout"] == owner.ready + owner.result
    assert "stdout" in observed.after_cleanup.unavailable_fields
    assert observed.run_evidence(prepared).assessment().native is None
    assert observed.diagnostics()["before_cleanup"]["fields"]["stdout"]["available"]


@pytest.mark.parametrize("deadline", [True, None, 0, -1, 2**63, 1, 5_000_000_000])
def test_invalid_or_insufficient_deadline_constructs_no_owner(tmp_path, deadline):
    _, args = modeled(tmp_path)
    outcome = run(args["prepared"], lambda exact: None, deadline_ns=deadline)
    assert outcome.primary_error is not None and not outcome.owner_constructed
    assert outcome.run_evidence(args["prepared"]).assessment().native is None


@pytest.mark.parametrize("tick", [-1, True, None, 2**63])
def test_invalid_initial_clock_is_unknown_not_zero(tmp_path, tick):
    _, args = modeled(tmp_path)
    outcome = run(args["prepared"], lambda exact: None, _clock=lambda: tick)
    assert outcome.started_ns is None and outcome.finished_ns is None
    assert not outcome.owner_constructed
    assert outcome.run_evidence(args["prepared"]).assessment().native is None


def test_global_reservation_is_not_released_when_not_owned(tmp_path):
    _, args = modeled(tmp_path)
    assert shared._DISPATCH_LOCK.acquire(blocking=False)
    try:
        outcome = run(args["prepared"], lambda exact: None)
        assert outcome.primary_error == "OWNED_PROCESS_ALREADY_RUNNING"
        assert not outcome.owner_constructed and shared._DISPATCH_LOCK.locked()
    finally:
        shared._DISPATCH_LOCK.release()


def test_exact_entry_is_inert_and_one_use_even_after_pre_start_stop(tmp_path):
    _, args = modeled(tmp_path)
    calls = []
    supervisor = module.ActivationProcessSupervisor(
        args["prepared"], revalidate_consumed_permit=lambda exact: calls.append(exact)
    )
    assert not supervisor.status()["consumed"] and not calls
    stopped = threading.Event()
    stopped.set()
    observed = supervisor.run(
        cancellation=stopped, deadline_ns=time.monotonic_ns() + 25_000_000_000
    )
    assert observed.primary_error == "CANCELLED" and not observed.owner_constructed
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        supervisor.run(
            cancellation=threading.Event(),
            deadline_ns=time.monotonic_ns() + 25_000_000_000,
        )
    assert not calls


def test_different_executed_registration_cannot_become_physical_run_record(
    tmp_path, monkeypatch
):
    _, prepared, _, current = setup(tmp_path, monkeypatch)
    fixture_registration = replace(
        prepared.registration,
        worker_id="modeled-fixture",
        composition="INCAPABLE_PROCESS_FIXTURE",
    )
    observed = module._supervise(
        prepared,
        fixture_registration,
        revalidate_consumed_permit=current,
        cancellation=threading.Event(),
        deadline_ns=25_000_000_000,
        _clock=Clock(),
    )
    assert (
        observed.diagnostics()["actual_registration"]["composition"]
        == "INCAPABLE_PROCESS_FIXTURE"
    )
    with pytest.raises(ValueError, match="EXECUTED_ACTIVATION_REGISTRATION_MISMATCH"):
        observed.run_evidence(prepared)


@pytest.mark.parametrize(
    "fault", ["work-timeout", "cleanup-late", "clock-reversal", "clock-throw"]
)
def test_deadline_and_clock_failures_are_retained_without_renewal(
    tmp_path, monkeypatch, fault
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)
    clock = Clock()
    ordinary_cleanup, ordinary_poll = owner.cleanup, owner.poll

    def poll(budget):
        if fault == "work-timeout":
            clock.tick += 11_000_000_000
        return ordinary_poll(budget)

    def cleanup(deadline_ns):
        answer = ordinary_cleanup(deadline_ns)
        if fault == "cleanup-late":
            clock.tick = deadline_ns + 1
        elif fault == "clock-reversal":
            clock.tick = 1
        elif fault == "clock-throw":
            clock.error = RuntimeError("MODELED_CLOCK_FAILURE")
        return answer

    monkeypatch.setattr(owner, "poll", poll)
    monkeypatch.setattr(owner, "cleanup", cleanup)
    observed = run(prepared, current, _clock=clock)
    record = observed.run_evidence(prepared)
    assert record.assessment().status in ("FAILED", "TIMED_OUT")
    assert observed.parent_deadline_ns == 25_000_000_000
    if fault == "work-timeout":
        assert observed.primary_error == "TIMED_OUT"
        assert not observed.unresolved_owner_retained
        assert record.assessment().native is None
    else:
        assert (
            observed.unresolved_owner_retained and shared._UNRESOLVED_BACKEND is owner
        )
        assert record.assessment().native is not None
    if fault in ("clock-reversal", "clock-throw"):
        assert observed.finished_ns is None and observed.supervisor_errors


@pytest.mark.parametrize("boundary", ["constructor", "pin", "start", "poll"])
def test_interrupted_work_still_cleans_up_and_returns_diagnostics(
    tmp_path, monkeypatch, boundary
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt("Interruption fixture; not UI text")

    if boundary == "constructor":
        monkeypatch.setattr(module, "_new_owner", interrupted)
    else:
        monkeypatch.setattr(owner, boundary, interrupted)
    observed = run(prepared, current)
    assert observed.primary_error == "KeyboardInterrupt"
    assert observed.owner_constructed == (boundary != "constructor")
    assert not observed.unresolved_owner_retained
    assert observed.run_evidence(prepared).assessment().native is None


@pytest.mark.parametrize("changed", ["preparation", "registration"])
def test_changed_inputs_after_pin_are_refused_before_process_creation(
    tmp_path, monkeypatch, changed
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)
    registration = prepared.registration
    pin = owner.pin

    def mutate(reg):
        pin(reg)
        if changed == "preparation":
            object.__setattr__(prepared, "payload", b"changed")
        else:
            object.__setattr__(registration, "argv", ("--changed",))

    monkeypatch.setattr(owner, "pin", mutate)
    observed = module._supervise(
        prepared,
        registration,
        revalidate_consumed_permit=current,
        cancellation=threading.Event(),
        deadline_ns=25_000_000_000,
        _clock=Clock(),
    )
    assert observed.primary_error == (
        "PREPARATION_CHANGED"
        if changed == "preparation"
        else "PROCESS_REGISTRATION_CHANGED"
    )
    assert observed.owner_constructed and not owner.created
    assert not observed.unresolved_owner_retained


def test_stop_after_result_delivery_cannot_promote_unaccepted_result(
    tmp_path, monkeypatch
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)
    cancellation = threading.Event()
    ordinary_poll = owner.poll

    def stop(budget):
        ended = ordinary_poll(budget)
        if owner.phase == "result":
            cancellation.set()
        return ended

    monkeypatch.setattr(owner, "poll", stop)
    observed = run(prepared, current, cancellation=cancellation)
    assert observed.primary_error == "CANCELLED"
    assert observed.before_cleanup.values()["stdout"] == owner.ready + owner.result
    assert observed.accepted_result_sha256 is None
    assert observed.run_evidence(prepared).assessment().native is None
    assert not observed.unresolved_owner_retained


def test_drifted_registration_cannot_expand_cleanup_or_snapshot_limits(
    tmp_path, monkeypatch
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)
    registration = prepared.registration
    clock = Clock()
    pin, cleanup = owner.pin, owner.cleanup
    observed_limits = []

    def changed(reg):
        pin(reg)
        object.__setattr__(
            reg,
            "budget",
            replace(reg.budget, cleanup_timeout_ms=5000, stdout_bytes=128),
        )

    def finish(deadline_ns):
        observed_limits.append(deadline_ns - clock.tick)
        return cleanup(deadline_ns)

    monkeypatch.setattr(owner, "pin", changed)
    monkeypatch.setattr(owner, "cleanup", finish)
    observed = module._supervise(
        prepared,
        registration,
        revalidate_consumed_permit=current,
        cancellation=threading.Event(),
        deadline_ns=25_000_000_000,
        _clock=clock,
    )
    assert observed.primary_error == "PROCESS_REGISTRATION_CHANGED"
    assert observed_limits == [2_000_000_000]
    assert observed.after_cleanup.to_dict()["stdout_limit"] == 256 * 1024
    assert not owner.created and not observed.unresolved_owner_retained


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_one_use_exact_entry_completes_with_model_owner(tmp_path, monkeypatch, purpose):
    _, prepared, calls, current = setup(tmp_path, monkeypatch, purpose)
    supervisor = module.ActivationProcessSupervisor(
        prepared, revalidate_consumed_permit=current
    )
    observed = supervisor.run(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 25_000_000_000
    )
    assert (
        observed.run_evidence(prepared).assessment().status
        == "SUCCEEDED_NATIVE_DIAGNOSTIC"
    )
    assert calls == [prepared.preparation_sha256] * 2
    assert (
        supervisor.status()["consumed"]
        and not supervisor.status()["process_cleanup_hold"]
    )
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        supervisor.run(
            cancellation=threading.Event(),
            deadline_ns=time.monotonic_ns() + 25_000_000_000,
        )


def test_interrupted_post_cleanup_decoding_retains_owner_and_diagnostic_error(
    tmp_path, monkeypatch
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch)
    original = module.ActivationOwnerObservation.values

    def interrupted(observation):
        if owner.cleaned:
            raise KeyboardInterrupt("During final observation decoding")
        return original(observation)

    with monkeypatch.context() as patch:
        patch.setattr(module.ActivationOwnerObservation, "values", interrupted)
        observed = run(prepared, current)
    assert observed.unresolved_owner_retained and shared._UNRESOLVED_BACKEND is owner
    assert "AFTER_CLEANUP_VALUES:KeyboardInterrupt" in observed.supervisor_errors
    assert observed.primary_error == "SUPERVISOR_OBSERVATION_FAILED"
    assert observed.run_evidence(prepared).assessment().status == "FAILED"


def test_unexpected_retention_exception_does_not_drop_uncertain_owner(
    tmp_path, monkeypatch
):
    owner, prepared, _, current = setup(tmp_path, monkeypatch, fault="cleanup-resource")
    ordinary_require = module._require

    def interrupted(condition, code):
        # Interrupt the first normal hold publication, then let the finally
        # fallback preserve the owner. This is not a real process in the test.
        if code == "UNRESOLVED_OWNER_ALREADY_RETAINED":
            monkeypatch.setattr(module, "_require", ordinary_require)
            raise KeyboardInterrupt("During final retention")
        ordinary_require(condition, code)

    monkeypatch.setattr(module, "_require", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(prepared, current)
    assert shared._UNRESOLVED_BACKEND is owner
    assert not shared._DISPATCH_LOCK.locked()
