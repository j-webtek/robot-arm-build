"""Actual pure bindings and fixed incapable Job lifecycle; no physical queries.

Original received/USB/boot observations, references and consumed transaction
facts are MODELED. The one actual child is separately linked to FixtureApi, not
WindowsPresenceApi. No production presence, USB, camera or CIM helper is run.
"""

from dataclasses import asdict, replace
from pathlib import Path
from threading import Event
import os
import time
from types import SimpleNamespace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignRegistration,
    ExactOperationPermit,
    RegisteredActionRequest,
    UsbPresenceAdmissionSnapshot,
)
from rocell.application.consumed_commissioning_scope import ConsumedCommissioningScope
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows import usb_presence_registration as registration
from rocell.providers.windows import owned_usb_presence_runner as runner
from rocell.providers.windows import owned_usb_presence_evidence as evidence
from rocell.providers.windows import owned_worker_process as shared
from rocell.providers.windows.usb_presence_protocol import canonical
from rocell.safety.effects import EffectClass
from test_physical_camera_coordinator import admission
from test_physical_received_camera import prerequisites, workspace
from test_usb_presence_review import review_fixture
from test_owned_usb_identity_runner import ModeledScopeTransaction

_MODELED = {}


def presence_runner_fixture(prerequisites, *, incapable=True, fail_at=None):
    # The expensive original codec chain is built once; each attempt gets a
    # freshly issued modeled permit and a new one-use transaction/scope.
    if incapable not in _MODELED:
        _MODELED[incapable] = review_fixture(prerequisites, incapable=incapable)
    reviewed = _MODELED[incapable]
    phase, runtime, review, policy = (
        reviewed.phase,
        reviewed.runtime,
        reviewed.review,
        reviewed.args["policy"],
    )
    binding = phase.to_dict()["binding"]
    a = asdict(admission())
    a.update(
        cell_id=binding["cell_id"],
        session_id=binding["session_id"],
        stage=PhysicalOnboardingStage.CAMERA_IDENTITY,
        stage_state=V2StageState.WAITING_OPERATOR,
        selected_identity_sha256=phase.sha256,
    )
    snapshot = UsbPresenceAdmissionSnapshot(
        **a,
        usb_presence_policy_sha256=policy.sha256,
        phase_binding_sha256=phase.sha256,
        runtime_review_sha256=review.sha256,
    )
    request = RegisteredActionRequest(
        snapshot.cell_id,
        snapshot.session_id,
        policy.to_dict()["action_id"],
        "MODELED-presence-query",
        snapshot.challenge_sha256,
    )
    campaign = CampaignRegistration(
        policy.to_dict()["action_id"],
        PhysicalOnboardingStage.CAMERA_IDENTITY,
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        policy.to_dict()["worker_id"],
        runtime.to_dict()["helper"]["sha256"],
        reviewed.args["operation_sha256"],
        (LeaseLevel.CAMERA,),
        CampaignBudget(**policy.to_dict()["budget"]),
    )
    now = time.monotonic_ns()
    permit = ExactOperationPermit(
        "attempt-" + "8" * 32,
        request,
        snapshot,
        campaign,
        now,
        now + 30_000_000_000,
        "9" * 64,
    )
    args = dict(
        phase_binding=phase,
        policy=policy,
        review=review,
        permit=permit,
        request_nonce="a" * 64,
    )
    prepared = (
        registration.prepare_incapable_usb_presence
        if incapable
        else registration.prepare_owned_usb_presence
    )(runtime, **args)
    cancel = Event()
    tx = ModeledScopeTransaction(permit, fail_at)
    deadline = now + 25_000_000_000
    scope = ConsumedCommissioningScope(
        permit,
        transaction=tx,
        deadline_ns=deadline,
        cancellation=cancel,
        monotonic_ns=time.monotonic_ns,
    )
    return SimpleNamespace(
        runtime=runtime,
        phase=phase,
        review=review,
        policy=policy,
        args=args,
        prepared=prepared,
        permit=permit,
        cancellation=cancel,
        deadline_ns=deadline,
        transaction=tx,
        scope=scope,
    )


@pytest.fixture
def case(prerequisites):
    return presence_runner_fixture(prerequisites)


@pytest.fixture(autouse=True)
def modeled_workspace_source(monkeypatch):
    # General checkout identity is explicitly modeled. Fixed native source,
    # artifact and build-record bytes remain checked by the actual inspector.
    monkeypatch.setattr(runner, "source_fingerprint", lambda path: "a" * 64)
    monkeypatch.setattr(registration, "source_fingerprint", lambda path: "a" * 64)


def run_case(case, guard=lambda: None):
    cls = (
        runner.IncapableUsbPresenceRunner
        if type(case.prepared) is registration.PreparedIncapableUsbPresence
        else runner.OwnedUsbPresenceRunner
    )
    owner = cls(
        case.prepared,
        permit=case.permit,
        authorization=case.scope,
        application_guard=guard,
    )
    return owner, owner.run(
        cancellation=case.cancellation, deadline_ns=case.deadline_ns
    )


def test_preparation_is_inert_exact_review_and_original_presence_permit(
    case, monkeypatch
):
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure preparation reads file")
    )
    monkeypatch.setattr(
        runner, "_new_owner", lambda: pytest.fail("constructor starts owner")
    )
    restored = type(case.prepared)(case.prepared.payload)
    assert restored.payload == case.prepared.payload
    assert canonical(asdict(restored.permit)) == canonical(asdict(case.permit))
    request = restored.request.to_dict()
    assert (
        request["target_instance_id"]
        == case.phase.to_dict()["target"]["physical_usb_instance_id"]
    )
    assert (
        request["selected_identity_sha256"]
        == request["phase_binding_sha256"]
        == case.phase.sha256
    )
    assert restored.review.sha256 == case.permit.admission.runtime_review_sha256
    assert restored.required_lifetime_ns == 15_000_000_000
    assert restored.registration.budget.run_timeout_ms == 13000
    assert restored.registration.budget.cleanup_timeout_ms == 2000
    assert len(restored.payload) <= registration.MAX_PREPARATION_BYTES == 24 * 1024
    runner.IncapableUsbPresenceRunner(
        restored,
        permit=case.permit,
        authorization=case.scope,
        application_guard=lambda: None,
    )
    assert case.transaction.acks == case.transaction.checks == 0


@pytest.mark.parametrize(
    "fault",
    [
        "old-domain",
        "review",
        "phase",
        "target",
        "helper",
        "operation",
        "runtime",
        "nonce",
        "schema",
        "budget",
    ],
)
def test_preparation_rejects_substituted_review_permit_or_request(case, fault):
    d = case.prepared.to_dict()
    if fault == "old-domain":
        del d["permit"]["admission"]["runtime_review_sha256"]
    elif fault == "review":
        d["review"]["operation_sha256"] = "f" * 64
    elif fault == "phase":
        d["phase_binding"]["binding"]["header_sha256"] = "f" * 64
    elif fault == "schema":
        d["schema"] = registration.PREPARATION_SCHEMA
    elif fault == "budget":
        d["runtime"]["budget"]["run_timeout_ms"] = 15000
    elif fault == "target":
        d["request"]["target_instance_id"] += "X"
        d["request"]["target_instance_id_sha256"] = evidence.digest(
            d["request"]["target_instance_id"].encode()
        )
    else:
        key = {
            "helper": "helper_sha256",
            "operation": "operation_sha256",
            "runtime": "runtime_registration_sha256",
            "nonce": "request_nonce",
        }[fault]
        d["request"][key] = "invalid" if fault == "nonce" else "f" * 64
    with pytest.raises(ValueError):
        type(case.prepared)(canonical(d))


def test_separate_runtime_preparation_types_cannot_swap(case):
    with pytest.raises(ValueError):
        registration.PreparedOwnedUsbPresence(case.prepared.payload)
    with pytest.raises(ValueError):
        runner.OwnedUsbPresenceRunner(
            case.prepared,
            permit=case.permit,
            authorization=case.scope,
            application_guard=lambda: None,
        )
    with pytest.raises(ValueError):
        registration.prepare_owned_usb_presence(case.runtime, **case.args)


@pytest.mark.parametrize("fault", ["cancel", "scope", "guard", "source", "depleted"])
def test_preowner_refusal_keeps_complete_failed_evidence_and_no_device_calls(
    case, monkeypatch, fault
):
    monkeypatch.setattr(
        runner, "_new_owner", lambda: pytest.fail("refused scope created process owner")
    )
    guard = lambda: None
    if fault == "cancel":
        case.cancellation.set()
    elif fault == "scope":
        case.scope.close_scope()
    elif fault == "guard":
        guard = lambda: True
    elif fault == "source":
        monkeypatch.setattr(runner, "source_fingerprint", lambda path: "f" * 64)
    else:
        case.deadline_ns = time.monotonic_ns() + 14_000_000_000
    owner, report = run_case(case, guard)
    assert report.no_attempt and not report.released
    assert report.actual_counts == dict(
        api_calls=0, device_handle_opens=0, configuration_writes=0, frames=0
    )
    assert report.status not in {"PRESENT", "ABSENT", "HELD"}
    assert report.payload == owner.retained_evidence.payload
    assert (
        evidence.verify_owned_usb_presence_run_evidence(
            report,
            expected_preparation_sha256=case.prepared.sha256,
            expected_evidence_sha256=report.sha256,
        ).payload
        == report.payload
    )
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        owner.run(cancellation=case.cancellation, deadline_ns=case.deadline_ns)


@pytest.mark.skipif(os.name != "nt", reason="fixed Windows incapable Job/pipe entry")
def test_actual_incapable_presence_one_process_ready_release_and_owned_readback(case):
    assert shared._UNRESOLVED_BACKEND is None
    # A clipped original campaign window is a reduction, not a renewed TTL.
    case.deadline_ns = case.permit.issued_at_ns + 24_000_000_000
    owner, report = run_case(case)
    d = report.to_dict()
    print(
        "INCAPABLE_PRESENCE_OWNED_SUMMARY="
        + canonical(report.safe_summary()).decode("ascii"),
        flush=True,
    )
    assert report.status == "ABSENT", report.safe_summary()
    assert d["provenance"] == "INCAPABLE_USB_PRESENCE"
    assert report.observation.to_dict()["provider"] == "INCAPABLE_FIXTURE"
    assert report.actual_counts == dict(
        api_calls=4, device_handle_opens=0, configuration_writes=0, frames=0
    )
    assert report.process_cleanup_confirmed and report.native_cleanup_confirmed
    assert d["process"]["peak_processes"] == 1
    assert (
        d["process"]["tree_exited"]
        and d["process"]["stdout_eof"]
        and d["process"]["stderr_eof"]
    )
    assert d["process"]["handles_remaining"] == d["process"]["pins_remaining"] == 0
    assert case.transaction.acks == 1 and case.transaction.checks == 5
    assert d["original_deadline_ns"] == case.deadline_ns
    assert d["finished_monotonic_ns"] < case.deadline_ns
    assert d["scope_checks"][-1]["finished_ns"] < d["run_deadline_ns"]
    assert d["run_deadline_ns"] <= d["scope_checks"][2]["started_ns"] + 13_000_000_000
    assert (
        d["cleanup_started_ns"] <= d["cleanup_finished_ns"] <= d["cleanup_deadline_ns"]
    )
    assert d["cleanup_deadline_ns"] == min(
        case.deadline_ns, d["cleanup_started_ns"] + 2_000_000_000
    )
    assert len(report.payload) <= evidence.MAX_EVIDENCE_BYTES == 128 * 1024
    assert owner.retained_evidence.payload == report.payload
    assert shared._UNRESOLVED_BACKEND is None
    native = report.observation.to_dict()
    # Exercise detached strict reconstruction against the actual producer,
    # never a hand-authored successful native observation.
    for field, value in (
        ("started_utc_ns", native["started"]["utc_ns"] + 1),
        ("finished_utc_ns", native["finished"]["utc_ns"] - 1),
        ("started_utc_ns", case.review.to_dict()["reviewed_at_ns"] - 1),
        ("original_deadline_ns", case.permit.expires_at_ns + 1),
        ("original_deadline_ns", case.permit.issued_at_ns),
        ("original_deadline_ns", d["started_monotonic_ns"] + 25_000_000_001),
        ("run_deadline_ns", None),
        ("run_deadline_ns", d["original_deadline_ns"]),
        ("run_deadline_ns", d["scope_checks"][-1]["finished_ns"]),
        ("cleanup_started_ns", None),
        ("cleanup_deadline_ns", d["cleanup_deadline_ns"] + 1),
        ("cleanup_finished_ns", None),
    ):
        changed = dict(d, **{field: value})
        with pytest.raises(ValueError):
            evidence.OwnedUsbPresenceRunEvidence(canonical(changed))
    for field, value in (
        ("peak_processes", 2),
        ("pins_remaining", 1),
        ("handles_remaining", 1),
        ("pending", True),
        ("stdout_eof", False),
        ("stderr_eof", False),
    ):
        changed = dict(d, process=dict(d["process"], **{field: value}))
        with pytest.raises(ValueError):
            evidence.OwnedUsbPresenceRunEvidence(canonical(changed))
    changed = dict(d, started_utc_ns=native["started"]["utc_ns"] + 1)
    held = evidence.retain_owned_usb_presence_run(changed)
    assert held.status == "FAILED" and held.actual_counts == report.actual_counts
    assert held.error == "PRESENCE_OBSERVATION_OUTSIDE_OWNED_INTERVAL"
    assert held.to_dict()["stdout"] == d["stdout"]
    late = dict(
        d,
        cleanup_finished_ns=d["cleanup_deadline_ns"] + 1,
        finished_monotonic_ns=d["cleanup_deadline_ns"] + 2,
    )
    late_report = evidence.retain_owned_usb_presence_run(late)
    assert late_report.status == "CLEANUP_UNCERTAIN"
    assert late_report.actual_counts == report.actual_counts
    assert not late_report.process_cleanup_confirmed
    assert late_report.to_dict()["stdout"] == d["stdout"]


class FaultOwner:
    """MODELED ownership state only; cannot start any process or device API."""

    def __init__(self, case, fault):
        self.case, self.fault = case, fault
        for field, default in evidence.PROCESS_DEFAULTS.items():
            setattr(self, field, default)
        self.stdout = self.stderr = b""
        self.handles, self.unclosed_handles, self.pins = {}, {}, []
        self.errors = []
        self.cleanup_calls = self.start_calls = self.release_calls = 0

    def pin(self, registration):
        self.pins.append(object())
        if self.fault == "pin":
            raise OSError("PIN_FAILED")

    def start(self, registration, wire, *, check, keep_stdin_open):
        from rocell.providers.windows.usb_presence_protocol import READY_SCHEMA

        self.start_calls += 1
        assert keep_stdin_open and wire == self.case.prepared.request.payload + b"\n"
        check()
        self.created, self.pid, self.peak_processes = True, 31415, 1
        check()
        self.resumed = True
        check()
        self.written = len(wire)
        self.stdout = (
            canonical(
                dict(
                    schema=READY_SCHEMA,
                    request_sha256=self.case.prepared.request.sha256,
                    child_pid=self.pid,
                    challenge="e" * 64,
                    permit_sha256=self.case.permit.permit_sha256,
                )
            )
            + b"\n"
        )
        if self.fault == "bad-ready":
            self.stdout = b'{"broken":1}\n'
        elif self.fault == "partial-ready":
            self.stdout = self.stdout[:40]
            self.returncode = 2
        elif self.fault == "early-output":
            self.stdout += b"UNAUTHORIZED_EXTRA"
        elif self.fault == "oversize-ready":
            self.stdout = b"x" * 1024

    def poll(self, budget):
        if self.fault == "process-count":
            self.peak_processes = 2
        if self.fault == "cancel-poll":
            self.case.cancellation.set()
        if self.returncode is not None:
            self.tree_exited = self.stdout_eof = self.stderr_eof = True
            return True
        return False

    def send_final_input(self, wire, *, check):
        check()
        self.release_calls += 1
        assert wire.endswith(b"\n")
        self.written += len(wire)
        self.stdout += b"ORIGINAL_MALFORMED_RESULT"
        self.stderr = b"INCAPABLE_FAULT_DIAGNOSTIC"
        if self.fault == "changed-ready-prefix":
            self.stdout = b"CHANGED_ORIGINAL_STDOUT"
        if self.fault in {"full-streams", "oversize-streams", "stderr-limit"}:
            header = self.stdout.split(b"\n", 1)[0] + b"\n"
            extra = 50 if self.fault == "oversize-streams" else 0
            self.stdout = header + b"x" * (66 * 1024 - len(header) + extra)
            self.stderr = b"y" * (4 * 1024 + extra)
            raise ValueError(
                "STDERR_LIMIT" if self.fault == "stderr-limit" else "STDOUT_LIMIT"
            )
        if self.fault == "write":
            raise OSError("WRITE_FAILED")
        self.returncode = 1

    def cleanup(self, deadline_ns):
        self.cleanup_calls += 1
        self.tree_exited = self.created
        if self.fault in {"cleanup", "cleanup-many"}:
            if self.fault == "cleanup-many":
                self.tree_exited = False
                self.pending = True
                return tuple(
                    "OWNER_CLOSE_" + str(i) + "_" + "x" * 109 for i in range(32)
                )
            return ("PIN_CLOSE_UNCONFIRMED",)
        self.pins.clear()
        if self.fault == "late-stop":
            self.case.cancellation.set()
        return ()


def modeled_owner(case, monkeypatch, fault):
    owner = FaultOwner(case, fault)
    monkeypatch.setattr(runner, "_new_owner", lambda: owner)
    monkeypatch.setattr(runner, "inspect_usb_presence_runtime", lambda *a, **k: None)
    # Only this incapable Python object is held; isolate it from real owner state.
    assert shared._UNRESOLVED_BACKEND is None
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)
    return owner


@pytest.mark.parametrize(
    "fault",
    [
        "pin",
        "bad-ready",
        "partial-ready",
        "early-output",
        "oversize-ready",
        "cancel-poll",
        "write",
        "malformed-result",
        "cleanup",
        "cleanup-many",
        "full-streams",
        "oversize-streams",
        "stderr-limit",
        "process-count",
        "late-stop",
        "changed-ready-prefix",
    ],
)
def test_modeled_owner_failures_preserve_bounded_originals(case, monkeypatch, fault):
    low = modeled_owner(case, monkeypatch, fault)
    owner, report = run_case(case)
    d = report.to_dict()
    assert low.cleanup_calls == 1
    assert report.status not in {"PRESENT", "ABSENT", "HELD"}
    assert evidence.stream_bytes(d["stdout"], 66 * 1024) == low.stdout[: 66 * 1024]
    assert evidence.stream_bytes(d["stderr"], 4 * 1024) == low.stderr[: 4 * 1024]
    assert len(report.payload) <= 128 * 1024
    assert owner.retained_evidence.payload == report.payload
    assert report.actual_counts is None if low.created else report.no_attempt
    if fault in {"cleanup", "cleanup-many", "oversize-streams"}:
        assert shared._UNRESOLVED_BACKEND is low
        assert report.status == "CLEANUP_UNCERTAIN"
    if fault == "cleanup-many":
        assert len(d["cleanup_errors"]) == 34
        assert all(code in d["cleanup_errors"] for code in low.cleanup(0))
    if fault in {"full-streams", "oversize-streams", "stderr-limit"}:
        name = "stderr" if fault == "stderr-limit" else "stdout"
        assert d[name]["coverage"] == "OWNER_LIMIT_PREFIX"
        assert d[name]["total_length_bytes"] is None
        assert d[name]["total_sha256"] is None
        assert not d[name]["complete"] and not d["result_validated"]
    if fault == "process-count":
        assert d["process"]["peak_processes"] == 2
        assert not report.released and low.release_calls == 0
    if fault == "changed-ready-prefix":
        assert (
            report.error == "USB_READY_PREFIX_CHANGED" and report.actual_counts is None
        )
        assert (
            evidence.stream_bytes(d["stdout"], 66 * 1024) == b"CHANGED_ORIGINAL_STDOUT"
        )
        assert d["ready_length"] > len(low.stdout)
        accepted = evidence.stream_bytes(d["ready_wire"], 1024)
        assert len(accepted) == d["ready_length"] and accepted.endswith(b"\n")
        assert report.released and not d["result_validated"]


@pytest.mark.parametrize("boundary", [2, 3, 4])
def test_stale_original_scope_cannot_release(case, monkeypatch, boundary):
    case.transaction.fail_at = boundary
    low = modeled_owner(case, monkeypatch, "malformed-result")
    _, report = run_case(case)
    d = report.to_dict()
    assert case.transaction.checks == boundary
    assert not d["release_write_attempted"] and not d["release_check_passed"]
    assert not report.released and low.release_calls == 0
    if boundary == 4:
        assert d["ready_length"] > 0 and report.actual_counts is None


def test_slow_post_pin_refuses_before_process_creation_without_deadline_renewal(
    case, monkeypatch
):
    low = modeled_owner(case, monkeypatch, "malformed-result")
    real_now = time.monotonic_ns
    elapsed = [0]
    monkeypatch.setattr(
        runner,
        "time",
        SimpleNamespace(
            monotonic_ns=lambda: real_now() + elapsed[0],
            time_ns=time.time_ns,
        ),
    )
    monkeypatch.setattr(
        runner,
        "inspect_usb_presence_runtime",
        lambda *a, **k: elapsed.__setitem__(0, 11_000_000_000),
    )
    _, report = run_case(case)
    assert report.error == "FULL_USB_LIFETIME_DOES_NOT_FIT"
    assert report.no_attempt and report.actual_counts["api_calls"] == 0
    assert case.transaction.checks == 2 and low.start_calls == low.release_calls == 0
    assert low.cleanup_calls == 1 and report.process_cleanup_confirmed
    assert report.to_dict()["original_deadline_ns"] == case.deadline_ns


def test_maximum_stream_and_error_envelope_fits_unchanged_retention(case, monkeypatch):
    low = modeled_owner(case, monkeypatch, "full-streams")
    _, report = run_case(case)
    d = report.to_dict()
    d["cleanup_errors"] = [str(i) + "_" + "x" * (127 - len(str(i))) for i in range(36)]
    d["status"] = "CLEANUP_UNCERTAIN"
    checked = evidence.OwnedUsbPresenceRunEvidence(canonical(d))
    assert len(checked.payload) < 128 * 1024
    assert evidence.stream_bytes(d["stdout"], 66 * 1024) == low.stdout
    assert evidence.stream_bytes(d["stderr"], 4 * 1024) == low.stderr
    # Independent conservative capacity envelope. Replace preparation with its
    # admitted byte cap, release with its full stream cap, all counters/times
    # with longest allowed encodings and all five scope rows. This is arithmetic
    # over the closed schema, NOT a fabricated valid native success receipt.
    cap = dict(d)
    cap["preparation"] = None
    cap["release_wire"] = evidence.stream_record(b"r" * 1024, complete=True)
    cap["ready_wire"] = evidence.stream_record(b"r" * 1024, complete=True)
    cap["primary_error"] = "x" * 128
    cap["status"] = "CLEANUP_UNCERTAIN"
    cap["provenance"] = "INCAPABLE_USB_PRESENCE"
    cap["ready_length"] = 1024
    for key in (
        "original_deadline_ns",
        "started_monotonic_ns",
        "finished_monotonic_ns",
        "started_utc_ns",
        "finished_utc_ns",
        "run_deadline_ns",
        "cleanup_started_ns",
        "cleanup_deadline_ns",
        "cleanup_finished_ns",
    ):
        cap[key] = 2**63 - 1
    cap["scope_checks"] = [
        dict(boundary=b, started_ns=2**63 - 1, finished_ns=2**63 - 1, passed=False)
        for b in evidence.BOUNDARIES
    ]
    cap["process"] = {
        key: (
            False
            if type(value) is bool
            else -(2**31) if key == "returncode" else 2**32 - 1
        )
        for key, value in evidence.PROCESS_DEFAULTS.items()
    }
    # Full-stream metadata is slightly longer than prefix-only metadata.
    cap["stdout"] = evidence.stream_record(low.stdout, complete=True)
    cap["stderr"] = evidence.stream_record(low.stderr, complete=True)
    for key, value in list(cap.items()):
        if type(value) is bool:
            cap[key] = False  # Five bytes is the longer boolean encoding.
    upper_bound = (
        len(canonical(cap)) - len(b"null") + registration.MAX_PREPARATION_BYTES
    )
    print(
        f"PRESENCE_RETAINED_CAPACITY actual={len(checked.payload)} upper_bound={upper_bound} cap={128*1024}"
    )
    assert upper_bound <= 128 * 1024


def test_physical_preparation_cannot_dispatch_without_exact_consumed_scope(
    prerequisites, monkeypatch
):
    physical = presence_runner_fixture(prerequisites, incapable=False)
    monkeypatch.setattr(
        runner, "_new_owner", lambda: pytest.fail("production helper forbidden")
    )
    with pytest.raises(ValueError, match="EXACT_USB_SCOPED_GUARD"):
        runner.OwnedUsbPresenceRunner(
            physical.prepared,
            permit=physical.permit,
            authorization=object(),
            application_guard=lambda: None,
        )
    physical.cancellation.set()
    _, held = run_case(physical)
    assert held.status == "CANCELLED" and held.no_attempt
    assert held.to_dict()["provenance"] == "PHYSICAL_USB_PRESENCE"
    assert held.actual_counts["api_calls"] == 0


def test_old_descriptor_domain_permit_is_not_presence_permission(case):
    from test_owned_usb_identity_runner import usb_fixture

    original = usb_fixture()
    with pytest.raises(ValueError):
        registration.prepare_incapable_usb_presence(
            case.runtime, **dict(case.args, permit=original.permit)
        )
    with pytest.raises(ValueError, match="EXACT_PRESENCE_DOMAIN_PERMIT"):
        runner.IncapableUsbPresenceRunner(
            case.prepared,
            permit=original.permit,
            authorization=original.scope,
            application_guard=lambda: None,
        )


@pytest.mark.parametrize(
    "field",
    [
        "ready_length",
        "release_wire",
        "stream_hash",
        "stream_total",
        "created",
        "count",
        "counter_boolean",
        "preparation_hash",
    ],
)
def test_detached_failure_evidence_cannot_claim_inconsistent_originals(
    case, monkeypatch, field
):
    modeled_owner(case, monkeypatch, "malformed-result")
    _, report = run_case(case)
    d = report.to_dict()
    if field == "ready_length":
        d["ready_length"] -= 1
    elif field == "release_wire":
        d[field] = evidence.stream_record(
            evidence.stream_bytes(d[field], 1024)[:-1], complete=True
        )
    elif field == "stream_hash":
        d["stdout"]["sha256"] = "f" * 64
    elif field == "stream_total":
        d["stdout"]["total_length_bytes"] += 1
    elif field == "created":
        d["process"]["created"] = d["process"]["resumed"] = False
    elif field == "count":
        d["process"]["written"] -= 1
    elif field == "counter_boolean":
        d["process"]["peak_processes"] = True
    else:
        d["preparation_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        evidence.OwnedUsbPresenceRunEvidence(canonical(d))
