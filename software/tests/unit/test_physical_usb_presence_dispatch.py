"""Genuine isolated M1 dispatch; physical observations and prior facts MODELED.

Original runtime review, binding package, leases, journal, attempt ledger, five
consumed rechecks, immutable evidence and reopening are real NTFS operations.
Earlier baseline/metadata/boot and native/Job observations are explicitly
physical-shaped test models. No process/CIM/device/native helper executes.
"""

from dataclasses import asdict
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import json
import os
import subprocess
import time

import pytest

from rocell.application import physical_usb_presence_dispatch as dispatch
from rocell.application import commissioning_usb_presence_persistence as persistence
from rocell.application import physical_usb_presence_campaign as campaign_module
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows import owned_usb_presence_evidence as evidence
from rocell.providers.windows import owned_usb_presence_runner as runner
from rocell.providers.windows import host_boot_observation as boot
from rocell.providers.windows import usb_presence_protocol as wire
from rocell.providers.windows.usb_presence_review import review_usb_presence_runtime
from test_commissioning_usb_identity import runtime_and_adapter, _modeled_ready
from test_commissioning_usb_presence_persistence import (
    subjects,
    facts,
    adapter,
    POLICY,
    STAGE,
    SOURCE,
    SESSION,
    CELL,
    LEASES,
)
from test_physical_camera_prerequisites import workspace
from test_physical_received_camera import prerequisites
from test_physical_usb_presence_campaign import modeled_presence_campaign, execute_model

WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="Genuine isolated Windows M1/NTFS leases"
)


@pytest.fixture(autouse=True)
def forbid_process_devices(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Presence dispatch test attempted a process/CIM/device operation")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(runner, "_new_owner", forbidden)
    monkeypatch.setattr(boot, "_native_owner", forbidden)
    monkeypatch.setattr(boot, "_system_powershell", forbidden)


def modeled_owned_presence(
    prepared,
    *,
    deadline_ns,
    checks,
    started_ns,
    started_utc_ns,
    native_started_utc_ns=None,
    finished_ns=None,
    finished_utc_ns=None,
    outcome="ABSENT",
    missing_result=False,
):
    """Strict owned wire model for an exact real prepared/permit/nonce subject.

    Checks may be measured real consumed-M1 calls; native/Job observations are
    still MODELED, never claims about a launched process. No verifier override.
    """
    permit, request, deadline, issued = (
        prepared.permit,
        prepared.request,
        deadline_ns,
        started_ns,
    )
    native_start = (
        started_utc_ns if native_started_utc_ns is None else native_started_utc_ns
    )

    def moment(ms):
        return dict(monotonic_ms=ms, utc_ns=native_start + ms * 1_000_000)

    ids = [] if outcome == "ABSENT" else [request.to_dict()["target_instance_id"]]
    observation = dict(
        schema=wire.OBSERVATION_SCHEMA,
        request=request.to_dict(),
        request_sha256=request.sha256,
        # This is an explicit model of the physical wire, not a relabeled
        # incapable execution. No claim is made that this API actually ran.
        provider="WINDOWS_CONFIGURATION_MANAGER",
        filter=wire.physical_device_filter(request.to_dict()["target_instance_id"]),
        scope="PRESENT_PHYSICAL_USB_DEVICE_INSTANCES",
        outcome=outcome,
        error=None if outcome != "HELD" else "SIZE_API_FAILED",
        started=moment(10),
        finished=moment(30),
        samples=(
            [
                dict(
                    started=moment(11 + i * 5),
                    finished=moment(14 + i * 5),
                    required_chars=8192,
                    used_chars=sum(len(x) + 1 for x in ids) + 1,
                    api_calls=2,
                    native_code=0,
                    complete=True,
                    target_present=bool(ids),
                    error=None,
                    instance_ids=list(ids),
                )
                for i in range(2)
            ]
            if outcome != "HELD"
            else [
                dict(
                    started=moment(11),
                    finished=moment(12),
                    required_chars=0,
                    used_chars=0,
                    api_calls=1,
                    native_code=13,
                    complete=False,
                    target_present=None,
                    error="SIZE_API_FAILED",
                    instance_ids=[],
                )
            ]
        ),
        api_calls=1 if outcome == "HELD" else 4,
        device_handle_opens=0,
        configuration_writes=0,
        frames=0,
        physical_authority=False,
    )
    observed = wire.UsbPresenceObservation(wire.canonical(observation))
    ready = dict(
        schema=wire.READY_SCHEMA,
        request_sha256=request.sha256,
        permit_sha256=permit.permit_sha256,
        child_pid=31415,
        challenge="e" * 64,
    )
    ready_raw = wire.canonical(ready) + b"\n"
    release = wire.encode_usb_presence_release(ready, request, child_pid=31415) + b"\n"
    result = (
        wire.canonical(
            dict(
                schema=wire.RESULT_SCHEMA,
                request_sha256=request.sha256,
                child_pid=31415,
                challenge_sha256=wire.digest(ready["challenge"].encode("ascii")),
                permit_sha256=permit.permit_sha256,
                observation=observation,
            )
        )
        + b"\n"
    )
    start = issued + 1_000_000
    cleanup_start = start + 250_000_000
    raw = dict(
        schema=evidence.SCHEMA,
        preparation=prepared.to_dict(),
        preparation_sha256=prepared.sha256,
        provenance="PHYSICAL_USB_PRESENCE",
        original_deadline_ns=deadline,
        run_deadline_ns=start + 13_000_000_000,
        cleanup_started_ns=cleanup_start,
        cleanup_deadline_ns=cleanup_start + 2_000_000_000,
        cleanup_finished_ns=cleanup_start + 1_000_000,
        started_monotonic_ns=start,
        finished_monotonic_ns=cleanup_start + 2_000_000,
        started_utc_ns=native_start,
        finished_utc_ns=native_start + 300_000_000,
        scope_checks=[
            dict(
                boundary=b,
                started_ns=start + (i + 1) * 40_000_000,
                finished_ns=start + (i + 1) * 40_000_000 + 1,
                passed=True,
            )
            for i, b in enumerate(evidence.BOUNDARIES)
        ],
        owner_constructed=True,
        process=dict(
            evidence.PROCESS_DEFAULTS,
            created=True,
            resumed=True,
            tree_exited=True,
            returncode=1 if outcome == "HELD" else 0,
            pid=31415,
            written=len(request.payload) + 1 + len(release),
            peak_handles=14,
            peak_processes=1,
            stdout_eof=True,
            stderr_eof=True,
        ),
        stdout=evidence.stream_record(ready_raw + result, complete=True),
        stderr=evidence.stream_record(b"", complete=True),
        ready_length=len(ready_raw),
        ready_wire=evidence.stream_record(ready_raw, complete=True),
        release_wire=evidence.stream_record(release, complete=True),
        release_write_attempted=True,
        release_check_passed=True,
        release_delivery_confirmed=True,
        result_validated=False,
        primary_error=None,
        cleanup_errors=[],
        status="FAILED",
        physical_authority=False,
        hardware_qualified=False,
        retries=0,
    )
    finish = time.monotonic_ns() if finished_ns is None else finished_ns
    utc_finish = time.time_ns() if finished_utc_ns is None else finished_utc_ns
    cleanup = checks[-1]["finished_ns"]
    raw.update(
        started_monotonic_ns=started_ns,
        finished_monotonic_ns=finish,
        started_utc_ns=started_utc_ns,
        finished_utc_ns=utc_finish,
        original_deadline_ns=deadline_ns,
        run_deadline_ns=min(
            deadline_ns - 2_000_000_000, checks[2]["started_ns"] + 13_000_000_000
        ),
        cleanup_started_ns=cleanup,
        cleanup_deadline_ns=min(deadline_ns, cleanup + 2_000_000_000),
        cleanup_finished_ns=finish,
        scope_checks=checks,
    )
    if missing_result:
        raw.update(
            stdout=evidence.stream_record(ready_raw, complete=True),
            stderr=evidence.stream_record(
                b"MODELED missing native result", complete=True
            ),
            primary_error="MODELED_MISSING_RESULT",
        )
    return evidence.retain_owned_usb_presence_run(raw)


def composition(
    workspace, monkeypatch, *, outcome="ABSENT", missing_result=False, after=None
):
    runtime, camera = runtime_and_adapter(workspace, ready=False)
    _modeled_ready(runtime, camera)
    case = subjects(
        workspace,
        monkeypatch,
        header=runtime.session_snapshot(SESSION).header.header_sha256,
    )
    operation = campaign_module.usb_presence_operation(
        phase_binding=case.phase,
        runtime=case.runtime,
        policy=POLICY,
        operation_id="usbphase-" + "d" * 32,
        launch_session_id="wizard-MODELED-presence-current",
        request_nonce="a" * 64,
    )
    case.operation = operation.sha256
    case.review = review_usb_presence_runtime(
        case.runtime,
        phase_binding=case.phase,
        policy=POLICY,
        operation_sha256=operation.sha256,
        operator_id="MODELED-operator",
        reviewer_id="MODELED-reviewer",
        launch_session_id=operation.to_dict()["launch_session_id"],
        reviewed_at_ns=case.phase.to_dict()["not_before_utc_ns"] + 1,
    )
    timestamp = case.review.to_dict()["reviewed_at_ns"]
    suffix = case.phase.to_dict()["binding"]["trial_id"][9:].upper()
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        phase_ref = tx.store_evidence(
            STAGE,
            case.phase.payload,
            label="MODELED-original-absence-binding",
            media_type="application/json",
            captured_at_ns=timestamp,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        assert tx.read_stage_evidence(phase_ref) == case.phase.payload
        ref = tx.store_evidence(
            STAGE,
            case.review.payload,
            label="MODELED-original-presence-runtime-review",
            media_type="application/json",
            captured_at_ns=timestamp,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        assert tx.read_stage_evidence(ref) == case.review.payload
        for offset, state, code, refs in (
            (
                1,
                V2StageState.REVIEW_PENDING,
                "MODELED_PRESENCE_REVIEW_CANDIDATE",
                (phase_ref, ref),
            ),
            (
                2,
                V2StageState.BLOCKED,
                "CAMERA_USB_PRESENCE_RUNTIME_REVIEWED_" + suffix,
                (ref,),
            ),
            (
                3,
                V2StageState.WAITING_OPERATOR,
                "CAMERA_USB_PRESENCE_QUERY_REQUESTED_" + suffix,
                (ref,),
            ),
        ):
            tx.commit_stage_state(
                STAGE,
                state,
                occurred_at_ns=timestamp + offset,
                detail_code=code,
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=tuple(sorted(refs, key=lambda r: r.evidence_id)),
            )
        case.reference, case.event = ref, tx.snapshot().committed_events[-2]
    case.revision = 0
    facts_calls = []

    def fresh_facts(request, snapshot):
        # The full snapshot is freshly audited by the actual original M1 owner.
        # Prior subjects remain explicit models; the exact binding package and
        # independent review are real original bytes, not browser claims.
        assert phase_ref in snapshot.evidence
        assert (
            snapshot.header.header_sha256
            == case.phase.to_dict()["binding"]["header_sha256"]
        )
        facts_calls.append(snapshot.head.head_sha256)
        return facts(case)

    store = persistence.M1PhysicalUsbPresencePersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=POLICY,
        expected_usb_presence_policy_sha256=POLICY.sha256,
        admission_facts=fresh_facts,
    )
    campaign = campaign_module.PhysicalUsbPresenceCampaign(
        operation, review=case.review
    )
    calls = []

    class ModelRunner:
        def __init__(self, prepared, *, permit, authorization, application_guard):
            self.prepared, self.permit, self.scope, self.guard = (
                prepared,
                permit,
                authorization,
                application_guard,
            )

        def run(self, *, cancellation, deadline_ns):
            started, utc = time.monotonic_ns(), time.time_ns()
            assert not cancellation.is_set() and self.guard() is None
            self.scope.acknowledge(self.permit)
            checks, native_utc = [], None
            for boundary in evidence.BOUNDARIES:
                before = time.monotonic_ns()
                self.scope.revalidate(self.permit)
                checks.append(
                    dict(
                        boundary=boundary,
                        started_ns=before,
                        finished_ns=time.monotonic_ns(),
                        passed=True,
                    )
                )
                if boundary == "PRE_RELEASE":
                    native_utc = time.time_ns()
            observed = modeled_owned_presence(
                self.prepared,
                deadline_ns=deadline_ns,
                checks=checks,
                started_ns=started,
                started_utc_ns=utc,
                native_started_utc_ns=native_utc,
                outcome=outcome,
                missing_result=missing_result,
            )
            calls.append((self.permit, observed, self.scope, checks))
            if after:
                after(cancellation)
            return observed

    monkeypatch.setattr(runner, "OwnedUsbPresenceRunner", ModelRunner)
    monkeypatch.setattr(dispatch, "source_fingerprint", lambda path: SOURCE)
    owner = dispatch.PhysicalUsbPresenceDispatchOwner(
        store, campaign, revalidate_context=lambda: None
    )
    print(
        "PRESERVED_PRESENCE_DISPATCH_STORE=" + str(runtime.deployment_root), flush=True
    )
    return SimpleNamespace(
        runtime=runtime,
        camera=camera,
        store=store,
        campaign=campaign,
        owner=owner,
        calls=calls,
        facts_calls=facts_calls,
        case=case,
    )


def assert_strict_json(value):
    if type(value) is dict:
        assert all(type(key) is str for key in value)
        for nested in value.values():
            assert_strict_json(nested)
    elif type(value) is list:
        for nested in value:
            assert_strict_json(nested)
    else:
        assert type(value) in (str, int, bool, type(None))


@WINDOWS
@pytest.mark.parametrize("missing_result", [False, True])
def test_actual_original_dispatch_five_checks_exact_evidence_and_reopen(
    workspace, monkeypatch, missing_result
):
    c = composition(workspace, monkeypatch, missing_result=missing_result)
    pending = c.owner.perform(
        request_key="MODELED-one-original-presence", cancellation=Event()
    )
    assert len(c.calls) == 1
    permit, observed, scope, checks = c.calls[0]
    assert len(checks) == 5 and all(row["passed"] for row in checks)
    assert len(c.facts_calls) >= 8
    assert pending["status"] == ("HELD" if missing_result else "ABSENT")
    assert pending["attempt_state"] == (
        "SEALED_UNCERTAIN" if missing_result else "SEALED_KNOWN"
    )
    assert pending["pending_completion_log"] is True
    original = c.owner.retained_diagnostics()["original"]
    assert original["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert wire.canonical(original["evidence"]) == observed.payload
    assert wire.canonical(original["permit"]) == wire.canonical(asdict(permit))
    assert original["admission_evidence"]["selected_identity"] == c.case.phase.to_dict()
    assert original["admission_evidence"]["runtime_review"] == c.case.review.to_dict()
    assert (
        original["reference"]["schema"] == "rocell.usb_presence_campaign_reference.v1"
    )
    assert c.owner.retained_diagnostics()["collected"] is None
    assert c.owner.view()["readback_scope"] == "EXITED"
    assert_strict_json(c.owner.retained_diagnostics())
    assert_strict_json(pending)
    if missing_result:
        assert original["result"]["receipt"] is None and observed.actual_counts is None
        assert pending["execution"]["counter_coverage"] == "NOT_REPORTED"
        assert c.runtime.verify(SESSION).quarantined
    else:
        receipt = original["result"]["receipt"]
        assert (
            receipt["reads"] == 4
            and receipt["opens"]
            == receipt["writes"]
            == receipt["frames"]
            == receipt["closes"]
            == 0
        )
        assert receipt["final_power_state"] == "UNKNOWN"
        assert observed.actual_counts == dict(
            api_calls=4, device_handle_opens=0, configuration_writes=0, frames=0
        )
    with c.store.stage_transaction(
        SESSION,
        expected_challenge_sha256=c.store.verification(SESSION).challenge_sha256,
    ) as tx:
        assert len(tx.held_leases) == 2
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert (
            tx.read_campaign_evidence(permit.attempt_id)[0].payload == observed.payload
        )
        assert (
            tx.read_campaign_result(permit.attempt_id).state.value
            == pending["attempt_state"]
        )
        assert tx.snapshot().state_for(STAGE) is V2StageState.WAITING_OPERATOR
        assert all(
            ref.payload_sha256 != observed.sha256 for ref in tx.snapshot().evidence
        )
    # Fresh original owner audit includes all sibling camera/USB record domains.
    reopened = type(c.runtime).open(
        c.runtime.deployment_root,
        source_binding_sha256=c.runtime.source_binding_sha256,
        cell_id=CELL,
    )
    assert reopened.verify(SESSION).quarantined is missing_result
    with pytest.raises(Exception):
        scope.revalidate(permit)
    c.owner.validate_publication(pending)
    with pytest.raises(ValueError):
        c.owner.validate_publication(dict(pending, status="PRESENT"))
    c.owner.publication_completed("MODELED-durable-log-completion")
    assert c.owner.view()["phase"] == "CURRENT"
    with pytest.raises(ValueError, match="ALREADY_USED"):
        c.owner.perform(request_key="different-key", cancellation=Event())
    c.owner.invalidate()
    assert c.owner.view()["phase"] == "HISTORICAL_HELD"
    assert (
        c.owner.retained_diagnostics()["original"]["evidence_sha256"] == observed.sha256
    )
    print(
        "PRESENCE_ORIGINAL_EVIDENCE="
        + observed.sha256
        + " bytes="
        + str(len(observed.payload)),
        flush=True,
    )


@WINDOWS
def test_actual_readback_failure_preserves_original_terminal_and_collected_bytes(
    workspace, monkeypatch
):
    c = composition(workspace, monkeypatch, missing_result=True)

    def fail_read(self, attempt_id):
        raise ValueError("MODELED_ORIGINAL_READBACK_FAILURE")

    with monkeypatch.context() as patch:
        patch.setattr(
            persistence.M1PhysicalUsbPresenceTransaction,
            "read_campaign_evidence",
            fail_read,
        )
        with pytest.raises(ValueError, match="MODELED_ORIGINAL_READBACK_FAILURE"):
            c.owner.perform(
                request_key="MODELED-readback-failure", cancellation=Event()
            )
    permit, observed, *_ = c.calls[0]
    diagnostics = c.owner.retained_diagnostics()
    assert (
        diagnostics["original"]["retention"] == "M1_TERMINAL_READ_BACK_EVIDENCE_PENDING"
    )
    assert diagnostics["original"]["evidence"] is None
    assert wire.canonical(diagnostics["collected"]["document"]) == observed.payload
    assert diagnostics["collected"]["retention"] == "COLLECTED_NOT_M1_READ_BACK"
    assert c.owner.view()["readback_scope"] == "EXIT_OR_FINAL_VALIDATION_UNCONFIRMED"
    with pytest.raises(ValueError):
        c.owner.publication_completed("cannot-publish")
    with c.store.stage_transaction(
        SESSION,
        expected_challenge_sha256=c.store.verification(SESSION).challenge_sha256,
    ) as tx:
        assert (
            tx.read_campaign_evidence(permit.attempt_id)[0].payload == observed.payload
        )
        assert (
            tx.read_campaign_result(permit.attempt_id).state
            is AttemptState.SEALED_UNCERTAIN
        )
    assert_strict_json(diagnostics)


@WINDOWS
def test_actual_preparation_failure_has_no_intent_or_worker(workspace, monkeypatch):
    c = composition(workspace, monkeypatch)

    def fail_prepare(self, permit):
        assert c.runtime._attempts.snapshot().events == ()
        raise ValueError("MODELED_PREPARATION_TOO_LARGE")

    monkeypatch.setattr(
        campaign_module.PhysicalUsbPresenceCampaign,
        "preparation_for_permit",
        fail_prepare,
    )
    with pytest.raises(ValueError, match="MODELED_PREPARATION_TOO_LARGE"):
        c.owner.perform(request_key="MODELED-preparation-hold", cancellation=Event())
    assert not c.calls and c.runtime._attempts.snapshot().events == ()
    assert c.owner.view()["phase"] == "FAILED_NO_REPLAY"
    assert c.owner.retained_diagnostics()["original"] is None
    with pytest.raises(ValueError, match="ALREADY_USED"):
        c.owner.perform(request_key="not-a-retry", cancellation=Event())


@pytest.fixture
def pure_owner(prerequisites, monkeypatch):
    """MODELED transactions test adapter error handling, not M1 admission."""
    from rocell.application.cell_commissioning_coordinator import AttemptResult

    seed = modeled_presence_campaign(prerequisites)
    output = execute_model(seed, monkeypatch)
    campaign = campaign_module.PhysicalUsbPresenceCampaign(
        seed.operation, review=seed.review
    )
    campaign._evidence = seed.owned_run.payload  # Explicit modeled worker cache.
    p = object.__new__(persistence.M1PhysicalUsbPresencePersistence)
    context = seed.operation.to_dict()
    p._runtime = SimpleNamespace(
        cell=SimpleNamespace(cell_id=context["cell_id"]),
        source_binding_sha256=dispatch.physical_camera_source_binding(
            context["source_sha256"]
        ),
    )
    p._policy = seed.policy
    c = SimpleNamespace(
        seed=seed,
        campaign=campaign,
        persistence=p,
        cancellation=Event(),
        receipt=output.receipt,
        artifacts=output.evidence,
        exit_fault=None,
        after_exit=None,
        source=context["source_sha256"],
        guard_value=None,
        transactions=0,
    )
    c.result = AttemptResult(
        seed.permit.attempt_id,
        AttemptState.SEALED_KNOWN,
        seed.permit.permit_sha256,
        (),
        c.receipt,
        False,
        campaign.composition,
    )
    tx = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(
            header=SimpleNamespace(
                header_sha256=context["header_sha256"],
                session_id=context["session_id"],
                cell_id=context["cell_id"],
            )
        ),
        read_admission=lambda request: seed.permit.admission,
        read_campaign_permit=lambda attempt: seed.permit,
        read_campaign_result=lambda attempt: c.result,
        read_campaign_admission_evidence=lambda attempt: {"provenance": "MODELED_ONLY"},
        read_campaign_evidence=lambda attempt: c.artifacts,
        read_optional_campaign_evidence=lambda attempt: c.artifacts,
    )

    @contextmanager
    def transaction(leases):
        c.transactions += 1
        yield tx

    @contextmanager
    def stage_transaction(*a, **k):
        yield tx
        if c.after_exit:
            c.after_exit()
        if c.exit_fault:
            raise ValueError(c.exit_fault)

    monkeypatch.setattr(p, "transaction", transaction)
    monkeypatch.setattr(p, "stage_transaction", stage_transaction)
    monkeypatch.setattr(
        p, "verification", lambda sid: SimpleNamespace(challenge_sha256="f" * 64)
    )
    monkeypatch.setattr(dispatch, "source_fingerprint", lambda path: c.source)
    c.owner = dispatch.PhysicalUsbPresenceDispatchOwner(
        p, campaign, revalidate_context=lambda: c.guard_value
    )
    monkeypatch.setattr(c.owner._core, "prepare", lambda request: seed.permit)
    monkeypatch.setattr(c.owner._core, "execute", lambda permit, cancellation: c.result)
    return c


def test_pure_constructor_and_cached_views_do_not_do_io(pure_owner, monkeypatch):
    c = pure_owner

    def forbidden(*a, **k):
        pytest.fail("cached dispatch access performed I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(dispatch, "source_fingerprint", forbidden)
    value = c.owner.retained_diagnostics()
    assert value["dispatch"]["phase"] == "NOT_STARTED" and c.transactions == 0
    assert value["collected"]["retention"] == "COLLECTED_NOT_M1_READ_BACK"
    assert_strict_json(value)


@pytest.mark.parametrize("fault", ["stop", "source", "guard"])
def test_pure_stale_preflight_enters_no_original_transaction(pure_owner, fault):
    c = pure_owner
    if fault == "stop":
        c.cancellation.set()
    elif fault == "source":
        c.source = "f" * 64
    else:
        c.guard_value = True
    with pytest.raises(ValueError):
        c.owner.perform(request_key="stale-modeled", cancellation=c.cancellation)
    assert c.transactions == 0 and c.owner.view()["phase"] == "FAILED_NO_REPLAY"


@pytest.mark.parametrize("receipt_present", [False, True])
def test_pure_no_artifact_requires_no_receipt_and_never_infers_zero(
    pure_owner, receipt_present
):
    from dataclasses import replace

    c = pure_owner
    c.artifacts = ()
    if not receipt_present:
        c.result = replace(
            c.result,
            state=AttemptState.SEALED_UNCERTAIN,
            receipt=None,
            quarantine_latched=True,
        )
        result = c.owner.perform(
            request_key="no-original-artifact", cancellation=c.cancellation
        )
        assert result["status"] == "HELD"
        assert (
            result["execution"]
            is result["reference"]
            is result["evidence_sha256"]
            is None
        )
        assert (
            c.owner.retained_diagnostics()["original"]["retention"]
            == "M1_TERMINAL_READ_BACK_NO_EVIDENCE"
        )
    else:
        with pytest.raises(ValueError, match="RECEIPT_WITHOUT_ARTIFACT"):
            c.owner.perform(
                request_key="invalid-original-receipt", cancellation=c.cancellation
            )
        assert c.owner.view()["phase"] == "FAILED_NO_REPLAY"
    assert c.owner.retained_diagnostics()["collected"] is not None


@pytest.mark.parametrize("fault", ["exit", "stop", "source"])
def test_pure_post_readback_loss_preserves_full_original_without_publication(
    pure_owner, fault
):
    c = pure_owner
    if fault == "exit":
        c.exit_fault = "MODELED_EXIT_FAILURE"
    elif fault == "stop":
        c.after_exit = c.cancellation.set
    else:
        c.after_exit = lambda: setattr(c, "source", "f" * 64)
    with pytest.raises(ValueError):
        c.owner.perform(request_key="modeled-late-loss", cancellation=c.cancellation)
    d = c.owner.retained_diagnostics()
    assert wire.canonical(d["original"]["evidence"]) == c.seed.owned_run.payload
    assert d["original"]["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert d["dispatch"]["phase"] == "FAILED_NO_REPLAY"
    with pytest.raises(ValueError):
        c.owner.publication_completed("not-current")
    assert_strict_json(d)
