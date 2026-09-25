"""Exact incapable process tests and injected lifecycle faults; no camera helper."""

import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time

import pytest

from rocell.providers.windows import owned_native_camera_runner as module
from rocell.providers.windows import owned_worker_process as shared
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    READY_SCHEMA,
)
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
    verify_owned_native_camera_run_evidence,
)
from rocell.providers.windows.owned_native_camera_runner import (
    OwnedNativeCameraRunner,
    IncapableNativeAdmissionRunner,
    PreparedIncapableNativeAdmission,
    prepare_incapable_native_admission,
)
from test_native_camera_parent_admission import preparation


class IncapableOwner:
    """Pure owned-API fixture. It has no DLL/subprocess/device access."""

    def __init__(self, fault=None, cancellation=None):
        self.fault, self.cancel = fault, cancellation
        self.created = self.resumed = self.tree_exited = self.pending = False
        self.stdout_eof = self.stderr_eof = False
        self.returncode = None
        self.pid = self.written = self.peak_handles = self.peak_processes = 0
        self.stdout = self.stderr = b""
        self.handles, self.unclosed_handles, self.pins = {}, {}, []
        self.cleanup_calls = 0
        self.calls = []

    def pin(self, registration):
        self.calls.append("pin")
        self.pins.append(object())
        if self.fault == "pin-failed":
            raise OSError("PIN_FAILED")

    def start(self, registration, wire, *, check, keep_stdin_open):
        self.calls.append("start")
        assert keep_stdin_open is True
        check()
        self.created = True
        self.pid = 123
        check()
        self.resumed = True
        check()
        self.written = len(wire)
        self.request = json.loads(wire)
        ready = {
            "schema": READY_SCHEMA,
            "request_sha256": digest(wire[:-1]),
            "child_pid": 124 if self.fault == "wrong-pid" else self.pid,
            "challenge": "1" * 64,
        }
        self.stdout = canonical(ready) + b"\n"
        if self.fault == "malformed-ready":
            self.stdout = b"not-json\n"
        if self.fault == "ready-too-large":
            self.stdout = b"x" * 1024 + b"\n"
        if self.fault == "early-result":
            self.stdout += b"unexpected"
        self.peak_handles, self.peak_processes = 8, 1

    def send_final_input(self, wire, *, check):
        self.calls.append("send_final_input")
        if self.fault == "cancel-before-release":
            self.cancel.set()
        check()
        self.written += len(wire)
        release = json.loads(wire)
        result = {
            "schema": module.INCAPABLE_RESULT_SCHEMA,
            "admitted": True,
            "request_sha256": release["request_sha256"],
            "child_pid": self.pid,
            "challenge_sha256": release["challenge_sha256"],
            "device_effects": 0,
        }
        if self.fault == "wrong-result":
            result["child_pid"] = 124
        if self.fault == "physical-result":
            result["schema"] = "rocell.owned_native_camera_result.v1"
        self.stdout += (
            b"not-json"
            if self.fault == "malformed-result"
            else canonical(result) + b"\n"
        )
        self.returncode = 2 if self.fault == "failed-exit" else 0
        self.stderr = b"incapable stderr diagnostic"

    def poll(self, budget):
        if self.returncode is None:
            return False
        self.tree_exited = self.stdout_eof = self.stderr_eof = True
        if self.fault == "late-cancel":
            self.cancel.set()
        if self.fault == "poll-exception":
            raise OSError("POLL_FAILED")
        return True

    def cleanup(self, deadline_ns):
        self.cleanup_calls += 1
        self.calls.append("cleanup")
        if self.fault == "cleanup-exception":
            raise OSError("CLOSE_FAILED")
        self.tree_exited = self.created
        if self.fault == "cleanup-uncertain":
            return ("PIN_CLOSE_UNCONFIRMED",)
        self.pins.clear()
        return ()


@pytest.fixture(autouse=True)
def isolated_owner_hold(monkeypatch):
    assert shared._UNRESOLVED_BACKEND is None
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)


def run_fake(tmp_path, monkeypatch, fault=None, callback=None):
    prepared = prepare_incapable_native_admission(preparation(tmp_path))
    cancel, calls = threading.Event(), []
    owner = IncapableOwner(fault, cancel)
    monkeypatch.setattr(module, "_new_owner", lambda: owner)

    def authority(exact):
        calls.append(exact.preparation_sha256)
        assert exact.payload == prepared.probe.payload
        assert owner.calls[0] == "pin"
        if callback:
            return callback(exact, calls, owner)

    runner = IncapableNativeAdmissionRunner(
        prepared, revalidate_consumed_permit=authority
    )
    value = runner.run(
        cancellation=cancel, deadline_ns=time.monotonic_ns() + 20_000_000_000
    )
    return value, owner, calls, runner


def test_default_physical_runner_is_one_use_inert_and_held(tmp_path, monkeypatch):
    prepared = preparation(tmp_path)

    def forbidden(*a, **kw):
        pytest.fail("Held physical runner attempted effect or authorization")

    runner = OwnedNativeCameraRunner(prepared, revalidate_consumed_permit=forbidden)
    with monkeypatch.context() as patch:
        for method in ("open", "stat", "lstat", "mkdir", "resolve"):
            patch.setattr(Path, method, forbidden)
        patch.setattr(module, "_new_owner", forbidden)
        assert runner.status()["consumed"] is False
        value = runner.run(
            cancellation=threading.Event(),
            deadline_ns=time.monotonic_ns() + 20_000_000_000,
        )
        assert value.safe_summary()["status"] == "HELD"
        assert not value.to_dict()["owner_constructed"]
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        runner.run(cancellation=threading.Event(), deadline_ns=1)


def test_closed_test_registration_is_inert_and_cannot_swap_executables(
    tmp_path, monkeypatch
):
    probe = preparation(tmp_path)

    def forbidden(*a, **kw):
        pytest.fail("Inert fixture preparation accessed files")

    with monkeypatch.context() as patch:
        for name in ("stat", "open", "lstat", "mkdir"):
            patch.setattr(Path, name, forbidden)
        prepared = prepare_incapable_native_admission(probe)
        runner = IncapableNativeAdmissionRunner(
            prepared, revalidate_consumed_permit=forbidden
        )
        assert runner.status()["consumed"] is False
        assert prepared.registration.executable.path == module.INCAPABLE_CHILD_PATH
    changed = prepared.to_dict()
    changed["registration"]["executable"]["path"] = str(
        probe.registration.executable.path
    )
    with pytest.raises(ValueError, match="FIXED_INCAPABLE"):
        PreparedIncapableNativeAdmission(canonical(changed))
    with pytest.raises(ValueError, match="EXACT_PREPARATION"):
        OwnedNativeCameraRunner(prepared, revalidate_consumed_permit=forbidden)
    with pytest.raises(ValueError, match="EXACT_INCAPABLE"):
        IncapableNativeAdmissionRunner(probe, revalidate_consumed_permit=forbidden)


def test_injected_nominal_keeps_separate_protocol_and_cleanup_facts(
    tmp_path, monkeypatch
):
    evidence, owner, calls, runner = run_fake(tmp_path, monkeypatch)
    assert len(calls) == 2 and owner.cleanup_calls == 1
    summary = evidence.safe_summary()
    assert summary["status"] == "SUCCEEDED_ADMISSION_ONLY"
    assert summary["process_cleanup_confirmed"] is True
    assert (
        summary["native_receipt_valid"] is summary["native_cleanup_confirmed"] is False
    )
    assert summary["physical_authority"] is summary["hardware_qualified"] is False
    assert summary["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    data = evidence.to_dict()
    assert base64.b64decode(data["stdout"]["base64"]) == owner.stdout
    assert base64.b64decode(data["stderr"]["base64"]) == owner.stderr
    assert data["stdout"]["omitted_bytes_exact"] == 0
    assert data["process"]["written"] == owner.written
    assert runner.status()["consumed"]


@pytest.mark.parametrize(
    "fault",
    [
        "pin-failed",
        "wrong-pid",
        "malformed-ready",
        "ready-too-large",
        "early-result",
        "cancel-before-release",
        "wrong-result",
        "physical-result",
        "malformed-result",
        "failed-exit",
        "late-cancel",
        "poll-exception",
        "cleanup-exception",
        "cleanup-uncertain",
    ],
)
def test_faults_retain_diagnostics_and_never_become_native_success(
    tmp_path, monkeypatch, fault
):
    evidence, owner, calls, _ = run_fake(tmp_path, monkeypatch, fault)
    summary, data = evidence.safe_summary(), evidence.to_dict()
    assert summary["status"] in {"FAILED", "CANCELLED"}
    assert owner.cleanup_calls == 1
    assert summary["native_receipt_valid"] is False
    assert base64.b64decode(data["stdout"]["base64"]) == owner.stdout
    assert base64.b64decode(data["stderr"]["base64"]) == owner.stderr
    if fault in {"cleanup-exception", "cleanup-uncertain"}:
        assert shared._UNRESOLVED_BACKEND is owner
        assert not summary["process_cleanup_confirmed"]
        assert data["admission_only_validated"] is True
        assert "PROCESS_RESOURCES_RETAINED" in data["cleanup_errors"]
    if fault == "pin-failed":
        assert calls == []
    if fault == "cancel-before-release":
        assert len(calls) == 1 and not data["release_check_passed"]


@pytest.mark.parametrize("which", [1, 2])
def test_live_consumed_permit_denial_at_each_boundary_is_not_redeemed_again(
    tmp_path, monkeypatch, which
):
    def callback(exact, calls, owner):
        if len(calls) == which:
            raise ValueError("CONSUMED_SCOPE_CHANGED")

    evidence, owner, calls, _ = run_fake(tmp_path, monkeypatch, callback=callback)
    assert len(calls) == which and owner.cleanup_calls == 1
    assert evidence.to_dict()["primary_error"] == "CONSUMED_SCOPE_CHANGED"
    assert not evidence.to_dict()["release_check_passed"]
    if which == 1:
        assert not owner.created


def test_uncertain_owner_hold_is_shared_with_old_and_new_runners(tmp_path, monkeypatch):
    evidence, owner, _, _ = run_fake(tmp_path, monkeypatch, "cleanup-uncertain")
    assert shared._UNRESOLVED_BACKEND is owner

    def forbidden():
        pytest.fail("Uncertain owner was replaced")

    monkeypatch.setattr(module, "_new_owner", forbidden)
    prepared = prepare_incapable_native_admission(preparation(tmp_path))
    new = IncapableNativeAdmissionRunner(
        prepared, revalidate_consumed_permit=lambda _: None
    )
    held = new.run(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 20_000_000_000
    )
    assert held.to_dict()["primary_error"] == "PROCESS_CLEANUP_HOLD"
    old = shared.OwnedWindowsWorker(prepared.registration, authorizer=lambda *a: None)
    assert old.status()["process_cleanup_hold"] is True
    request = shared.OwnedWorkerRequest(
        "attempt",
        "session",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        time.monotonic_ns() + 20_000_000_000,
    )
    assert (
        old.run(
            request, cancellation=threading.Event(), deadline_ns=request.expires_at_ns
        ).primary_error
        == "PROCESS_CLEANUP_HOLD"
    )
    assert shared._UNRESOLVED_BACKEND is owner


def test_actual_backend_hyphenated_close_labels_are_retained_exactly(
    tmp_path, monkeypatch
):
    original = IncapableOwner.cleanup

    def cleanup(owner, deadline):
        original(owner, deadline)
        owner.unclosed_handles[12] = "stdin-parent"
        return ("CLOSE_FAILED:stdin-parent",)

    monkeypatch.setattr(IncapableOwner, "cleanup", cleanup)
    evidence, owner, _, _ = run_fake(tmp_path, monkeypatch)
    assert evidence.to_dict()["cleanup_errors"] == [
        "CLOSE_FAILED:stdin-parent",
        "PROCESS_RESOURCES_RETAINED",
    ]
    assert shared._UNRESOLVED_BACKEND is owner


def test_active_dispatch_reservation_cannot_be_entered_by_new_runner(
    tmp_path, monkeypatch
):
    shared._DISPATCH_LOCK.acquire()
    try:
        evidence, owner, calls, _ = run_fake(tmp_path, monkeypatch)
        assert evidence.to_dict()["primary_error"] == "OWNED_PROCESS_ALREADY_RUNNING"
        assert owner.calls == [] and calls == []
    finally:
        shared._DISPATCH_LOCK.release()


@pytest.mark.parametrize("fault", ["cancelled", "invalid-deadline", "too-short"])
def test_pre_dispatch_limits_hold_before_owner_or_authority(
    tmp_path, monkeypatch, fault
):
    prepared = prepare_incapable_native_admission(preparation(tmp_path))

    def forbidden(*a, **kw):
        pytest.fail("Denied dispatch reached owner or authority")

    monkeypatch.setattr(module, "_new_owner", forbidden)
    cancel = threading.Event()
    deadline = time.monotonic_ns() + 20_000_000_000
    if fault == "cancelled":
        cancel.set()
    elif fault == "invalid-deadline":
        deadline = True
    else:
        deadline = time.monotonic_ns() + 1_000_000_000
    runner = IncapableNativeAdmissionRunner(
        prepared, revalidate_consumed_permit=forbidden
    )
    evidence = runner.run(cancellation=cancel, deadline_ns=deadline)
    assert (
        evidence.to_dict()["primary_error"]
        == {
            "cancelled": "CANCELLED",
            "invalid-deadline": "INVALID_PARENT_DEADLINE",
            "too-short": "FULL_LIFETIME_DOES_NOT_FIT",
        }[fault]
    )
    assert not evidence.to_dict()["owner_constructed"]


def test_last_poll_cannot_accept_result_after_original_run_deadline(
    tmp_path, monkeypatch
):
    original_poll = IncapableOwner.poll
    real_clock = time.monotonic_ns
    now = [real_clock()]

    def poll(owner, budget):
        ended = original_poll(owner, budget)
        if ended:
            now[0] += 11_000_000_000
        return ended

    monkeypatch.setattr(IncapableOwner, "poll", poll)
    # The parent handshake's default clock remains the real monotonic function;
    # this seam specifically probes the supervisor's final-poll admission check.
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: now[0])
    evidence, owner, calls, _ = run_fake(tmp_path, monkeypatch)
    assert evidence.to_dict()["status"] == "TIMED_OUT"
    assert not evidence.to_dict()["admission_only_validated"]
    assert b'"admitted":true' in owner.stdout and len(calls) == 2
    assert owner.cleanup_calls == 1


@pytest.mark.parametrize("fault", ["cancel", "late", "exception-with-primary"])
def test_cleanup_cannot_override_primary_or_ignore_its_budget(
    tmp_path, monkeypatch, fault
):
    original_cleanup = IncapableOwner.cleanup
    now = [time.monotonic_ns()]

    def cleanup(owner, deadline):
        result = original_cleanup(owner, deadline)
        if fault == "cancel":
            owner.cancel.set()
        elif fault == "late":
            now[0] += 3_000_000_000
        else:
            raise OSError("CLEANUP_FAILURE")
        return result

    monkeypatch.setattr(IncapableOwner, "cleanup", cleanup)
    if fault == "late":
        monkeypatch.setattr(module.time, "monotonic_ns", lambda: now[0])
    evidence, owner, _, _ = run_fake(
        tmp_path,
        monkeypatch,
        "wrong-result" if fault == "exception-with-primary" else None,
    )
    data = evidence.to_dict()
    assert owner.cleanup_calls == 1
    if fault == "cancel":
        assert data["status"] == "CANCELLED"
    elif fault == "late":
        assert "CLEANUP_DEADLINE_EXCEEDED" in data["cleanup_errors"]
        assert shared._UNRESOLVED_BACKEND is owner
        assert data["status"] == "FAILED"
    else:
        assert data["primary_error"] == "INCAPABLE_RESULT_BINDING"
        assert "CLEANUP_EXCEPTION:OSError" in data["cleanup_errors"]


def test_callback_mutation_or_unexpected_return_does_not_allow_resume(
    tmp_path, monkeypatch
):
    def callback(exact, calls, owner):
        return True

    evidence, owner, calls, _ = run_fake(tmp_path, monkeypatch, callback=callback)
    assert evidence.to_dict()["primary_error"] == "PERMIT_CHECK_MUST_RETURN_NONE"
    assert len(calls) == 1 and not owner.created


def test_prepared_object_changed_after_constructor_does_not_dispatch(
    tmp_path, monkeypatch
):
    prepared = prepare_incapable_native_admission(preparation(tmp_path))

    def forbidden(*a, **kw):
        pytest.fail("Mutated preparation reached execution")

    runner = IncapableNativeAdmissionRunner(
        prepared, revalidate_consumed_permit=forbidden
    )
    monkeypatch.setattr(module, "_new_owner", forbidden)
    object.__setattr__(prepared, "payload", b"{}")
    evidence = runner.run(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 20_000_000_000
    )
    assert evidence.to_dict()["primary_error"] == "PREPARATION_CHANGED"


def test_evidence_verifier_is_pure_copy_isolated_and_requires_independent_hashes(
    tmp_path, monkeypatch
):
    evidence, _, _, _ = run_fake(tmp_path, monkeypatch)
    data = evidence.to_dict()

    def forbidden(*a, **kw):
        pytest.fail("Pure verification touched runtime/files")

    with monkeypatch.context() as patch:
        patch.setattr(module, "_new_owner", forbidden)
        patch.setattr(Path, "open", forbidden)
        verified = verify_owned_native_camera_run_evidence(
            data,
            expected_preparation_sha256=data["preparation_sha256"],
            expected_evidence_sha256=evidence.evidence_sha256,
        )
    data["validated_result"]["admitted"] = False
    assert verified.to_dict()["validated_result"]["admitted"] is True
    with pytest.raises(ValueError, match="TRUSTED_HASH"):
        verify_owned_native_camera_run_evidence(
            data,
            expected_preparation_sha256=data["preparation_sha256"],
            expected_evidence_sha256=evidence.evidence_sha256,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "raw",
        "raw-hash",
        "pid",
        "release",
        "source",
        "registration",
        "native-claim",
        "cleanup-claim",
        "power",
        "bytes",
        "bool-count",
        "unknown-field",
    ],
)
def test_rehashed_evidence_still_rejects_invalid_structural_joins(
    tmp_path, monkeypatch, fault
):
    evidence, _, _, _ = run_fake(tmp_path, monkeypatch)
    data = evidence.to_dict()
    if fault == "raw":
        data["stdout"]["base64"] = base64.b64encode(b"wrong").decode()
    elif fault == "raw-hash":
        data["stdout"]["retained_sha256"] = "0" * 64
    elif fault == "pid":
        data["process"]["pid"] += 1
    elif fault == "release":
        data["release_check_passed"] = False
    elif fault == "source":
        data["source_sha256"] = "0" * 64
    elif fault == "registration":
        data["registration"]["argv"] = ["probe"]
    elif fault == "native-claim":
        data["native_validated"] = True
    elif fault == "cleanup-claim":
        data["process"]["pins_remaining"] = 1
    elif fault == "power":
        data["final_power_state"] = "SAFE"
    elif fault == "bytes":
        data["process"]["written"] -= 1
    elif fault == "bool-count":
        data["process"]["written"] = True
    else:
        data["extra"] = 0
    with pytest.raises(ValueError):
        OwnedNativeCameraRunEvidence(canonical(data))


@pytest.mark.parametrize("native_cleanup_ok", [True, False])
def test_pure_native_wire_retention_separates_device_and_process_cleanup(
    tmp_path, monkeypatch, native_cleanup_ok
):
    """Fabricated protocol bytes exercise only the pure unqualified verifier.

    This does not dispatch the physical runner or constitute received evidence.
    The outer trusted evidence digest would have to come from real M1 retention.
    """
    from test_windows_camera_worker import receipt
    from rocell.providers.windows.native_camera_protocol import RESULT_SCHEMA
    from rocell.providers.windows.owned_worker_process import (
        owned_registration_document,
    )
    from rocell.providers.windows.native_camera_registration import (
        PreparedOwnedNativeProbe,
    )

    fixture_evidence, _, _, _ = run_fake(tmp_path, monkeypatch)
    data = fixture_evidence.to_dict()
    probe = PreparedOwnedNativeProbe(canonical(data["preparation"]))
    ready = base64.b64decode(data["ready_wire"]["base64"])
    release = json.loads(base64.b64decode(data["release_wire"]["base64"]))
    inner = receipt("probe")
    if not native_cleanup_ok:
        inner["status"] = "FAILED"
        inner["reason_code"] = "SOURCE_SHUTDOWN_FAILED"
        inner["cleanup"]["source_shutdown_hr"] = -1
    outer = {
        "schema": RESULT_SCHEMA,
        "request_sha256": release["request_sha256"],
        "child_pid": release["child_pid"],
        "challenge_sha256": release["challenge_sha256"],
        "permit_sha256": release["permit_sha256"],
        "native_receipt": inner,
    }
    stdout = ready + canonical(outer) + b"\n"
    data.update(
        fixture_preparation=None,
        provenance="PHYSICAL_UNQUALIFIED",
        native_validated=True,
        admission_only_validated=False,
        validated_result=outer,
        primary_error=None if native_cleanup_ok else "NATIVE_DIAGNOSTIC_FAILED",
        status="SUCCEEDED_NATIVE_DIAGNOSTIC" if native_cleanup_ok else "FAILED",
    )
    data["registration"] = owned_registration_document(probe.registration)
    data["registration_sha256"] = digest(canonical(data["registration"]))
    data["process"]["returncode"] = 0 if native_cleanup_ok else 1
    data["stdout"].update(
        base64=base64.b64encode(stdout).decode(),
        retained_bytes=len(stdout),
        retained_sha256=digest(stdout),
    )
    evidence = OwnedNativeCameraRunEvidence(canonical(data))
    summary = evidence.safe_summary()
    assert summary["native_receipt_valid"] is True
    assert summary["native_cleanup_confirmed"] is native_cleanup_ok
    assert summary["process_cleanup_confirmed"] is True
    assert summary["hardware_qualified"] is summary["physical_authority"] is False
    assert summary["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"


@pytest.mark.skipif(
    os.name != "nt" or not module.INCAPABLE_CHILD_PATH.is_file(),
    reason="Requires reviewed separately compiled camera-incapable entry target",
)
def test_actual_fixed_incapable_child_through_full_runner(tmp_path):
    probe = preparation(tmp_path)
    probe.registration.working_directory.mkdir()
    prepared = prepare_incapable_native_admission(probe)
    calls = []

    def authority(exact):
        assert exact.payload == probe.payload
        calls.append(exact.preparation_sha256)

    runner = IncapableNativeAdmissionRunner(
        prepared, revalidate_consumed_permit=authority
    )
    evidence = runner.run(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 20_000_000_000
    )
    # Preserve the complete native-incapable result even if the assertion fails;
    # a shortened pytest dictionary must not hide pin/cleanup diagnostics.
    (tmp_path / "native-incapable-original-evidence.json").write_bytes(evidence.payload)
    assert (
        evidence.safe_summary()["status"] == "SUCCEEDED_ADMISSION_ONLY"
    ), evidence.to_dict()
    assert evidence.safe_summary()["process_cleanup_confirmed"] is True
    assert len(calls) == 2 and shared._UNRESOLVED_BACKEND is None
    assert evidence.to_dict()["process"]["returncode"] == 0
    assert evidence.to_dict()["native_validated"] is False
