"""Real scoped worker/core plus unchanged held native runner; no device calls.

Metadata selection/runtime pins are explicitly modeled physical-shaped records.
The in-memory transaction is incapable and not an M1 durability qualification.
Only source_fingerprint is replaced for deterministic source continuity tests;
the actual physical runner and its physical hold are never replaced/enabled.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import os
import threading
import time
from typing import Any

import pytest

import rocell.application.physical_native_camera_campaign as module
from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
    CommissioningMode,
    EnergizationEnvelope,
    ObservedPowerState,
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
)
from rocell.application.physical_native_camera_campaign import (
    CAPTURE_ACTION_ID,
    PROBE_ACTION_ID,
    PhysicalNativeCameraCampaign,
    PhysicalNativeCameraCampaignError,
    verify_physical_native_camera_campaign_evidence,
)
from rocell.application.physical_camera_selection import PhysicalCameraSelection
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    CameraWorkerError,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_registration import (
    PreparedOwnedNativeProbe,
    create_native_camera_runtime_registration,
)
from rocell.providers.windows.native_camera_capture_registration import (
    PreparedOwnedNativeCapture,
    create_native_camera_capture_runtime_registration,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)
from rocell.safety.effects import EffectCertainty

from test_physical_camera_coordinator import (
    CELL,
    SESSION,
    SOURCE,
    CameraProtocolStore,
    admission,
)
from test_physical_camera_selection import physical_enrollment, selected


@pytest.fixture(autouse=True)
def no_native_or_device_calls(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
):
    import ctypes
    import subprocess

    def denied(*args: Any, **kwargs: Any):
        pytest.fail("physical campaign test attempted a process, DLL or device call")

    monkeypatch.setattr(subprocess, "Popen", denied)
    # Qualified M1 tests legitimately load Windows filesystem/lease APIs. They
    # still prohibit every device entry point and assert no runner owner exists.
    if (
        request.node.name
        != "test_actual_m1_scope_retains_real_native_runner_pre_owner_hold"
    ):
        monkeypatch.setattr(ctypes, "WinDLL", denied, raising=False)
        monkeypatch.setattr(ctypes, "CDLL", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)


def arguments(tmp_path: Path, *, capture: bool = False, unicode: bool = False):
    workspace = tmp_path / "model-workspace"
    selection = selected(physical_enrollment(unicode=unicode))
    factory = (
        create_native_camera_capture_runtime_registration
        if capture
        else create_native_camera_runtime_registration
    )
    runtime = factory(
        workspace,
        source_sha256=SOURCE,
        catalog_sha256="b" * 64,
        helper_sha256=("9" if capture else "c") * 64,
        build_record_sha256="d" * 64,
    )
    return (workspace, tmp_path / "assigned-output"), {
        "source_sha256": SOURCE,
        "cell_id": CELL,
        "session_id": SESSION,
        "selection": selection,
        "runtime": runtime,
        "mode": NativeCameraMode(4, 2, 9, 1, "YUY2", 8) if capture else None,
        "controls": (CameraControlSetting("brightness", 4),) if capture else (),
        "budget": CameraCampaignBudget(5000, 2, 16, 32) if capture else None,
    }


def campaign_fixture(tmp_path: Path, *, capture: bool = False, unicode: bool = False):
    args, kwargs = arguments(tmp_path, capture=capture, unicode=unicode)
    return PhysicalNativeCameraCampaign(*args, **kwargs)


def components(campaign: PhysicalNativeCameraCampaign):
    reg = campaign.registration()
    snapshot = admission(
        stage=reg.stage,
        selected_identity_sha256=campaign.plan()["selected_identity_sha256"],
    )
    store = CameraProtocolStore(snapshot)
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(reg,),
        workers={reg.worker_id: campaign},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, reg.action_id, "one-held-camera", snapshot.challenge_sha256
    )
    return core, store, core.prepare(request)


@pytest.mark.parametrize("capture", [False, True])
def test_constructor_plan_registration_and_preparation_are_filesystem_inert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture: bool
):
    args, kwargs = arguments(tmp_path, capture=capture, unicode=True)

    def denied(*args: Any, **kwargs: Any):
        pytest.fail("pure camera plan touched filesystem/source")

    for method in ("open", "stat", "lstat", "resolve", "mkdir", "iterdir", "exists"):
        monkeypatch.setattr(Path, method, denied)
    monkeypatch.setattr(module, "source_fingerprint", denied)
    campaign = PhysicalNativeCameraCampaign(*args, **kwargs)
    core, _, permit = components(campaign)
    prepared = campaign.preparation_for_permit(permit)
    assert type(prepared) is (
        PreparedOwnedNativeCapture if capture else PreparedOwnedNativeProbe
    )
    plan = campaign.plan()
    assert campaign.evidence is None
    assert campaign.registration().operation_sha256 == digest(canonical(plan))
    assert campaign.registration().resources == (LeaseLevel.CAMERA,)
    assert campaign.registration().action_id == (
        CAPTURE_ACTION_ID if capture else PROBE_ACTION_ID
    )
    assert (
        prepared.admission_request.to_dict()["selected_identity_sha256"]
        == kwargs["selection"].sha256
    )
    assert (
        kwargs["selection"].identity_document["launch_session_id"]
        != permit.request.session_id
    )
    assert prepared.admission_request.to_dict()["permit_sha256"] == permit.permit_sha256
    assert (
        prepared.admission_request.to_dict()["operation_sha256"]
        == campaign.registration().operation_sha256
    )
    assert prepared.camera_plan.request.binding == kwargs["selection"].binding
    assert "測試" in prepared.camera_plan.request.binding.symbolic_link
    assert str(prepared.registration.working_directory) == str(
        args[1] / ("native-camera-" + permit.attempt_id)
    )
    if capture:
        assert prepared.camera_plan.request.output_directory == str(
            prepared.registration.working_directory / ("capture-" + permit.attempt_id)
        )
        assert prepared.camera_plan.request.mode == kwargs["mode"]
        assert prepared.camera_plan.request.controls == kwargs["controls"]
    else:
        assert prepared.camera_plan.request.output_directory is None
    assert PhysicalNativeCameraCampaign.from_plan(plan).plan() == plan
    plan["runtime"]["helper"]["sha256"] = "f" * 64
    assert campaign.worker_executable_sha256 != "f" * 64
    assert campaign.plan()["output_policy"]["create_directories"] is False
    assert core is not None


@pytest.mark.parametrize("capture", [False, True])
def test_real_scoped_core_retains_unchanged_runner_hold_no_owner_or_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture: bool
):
    campaign = campaign_fixture(tmp_path, capture=capture)
    core, store, permit = components(campaign)
    source_reads = []
    monkeypatch.setattr(
        module, "source_fingerprint", lambda path: source_reads.append(path) or SOURCE
    )
    monkeypatch.setattr(
        Path, "mkdir", lambda *a, **k: pytest.fail("held call created a directory")
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.receipt is not None
    assert result.receipt.effect_certainty is EffectCertainty.UNCERTAIN
    assert result.receipt.cleanup_confirmed is False
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert [
        result.receipt.opens,
        result.receipt.reads,
        result.receipt.writes,
        result.receipt.frames,
        result.receipt.closes,
    ] == [0] * 5
    assert core.execute(permit) == result
    assert len(source_reads) == 2
    assert store.trace.count("ACKNOWLEDGED_ONCE") == 1
    assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 1
    assert (
        len(store.evidence) == 1
        and store.evidence[0].payload == campaign.evidence.payload
    )
    assert result.receipt.evidence_sha256s == (campaign.evidence.evidence_sha256,)
    assert result.receipt.output_bytes == len(campaign.evidence.payload) <= 128 * 1024
    document = campaign.evidence.to_dict()
    assert document["primary_error"] == "PHYSICAL_PROVIDER_QUALIFICATION_HELD"
    assert document["owner_constructed"] is False
    assert document["process"]["created"] is False
    assert document["process"]["written"] == 0
    assert document["ready_wire"]["retained_bytes"] == 0
    assert document["release_wire"]["retained_bytes"] == 0
    assert document["native_validated"] is False
    assert campaign.evidence.native_receipt is None
    assert (
        document["physical_authority"] is False
        and document["hardware_qualified"] is False
    )
    assert not (tmp_path / "assigned-output").exists()

    # Pure reopen verification reuses actual retained bytes, not a replay.
    monkeypatch.setattr(
        module,
        "source_fingerprint",
        lambda *a: pytest.fail("retained verifier read source"),
    )
    restored = PhysicalNativeCameraCampaign.from_plan(campaign.plan())
    assert (
        verify_physical_native_camera_campaign_evidence(
            campaign.evidence.to_dict(),
            campaign=restored,
            expected_permit=permit,
            expected_evidence_sha256=store.evidence[0].payload_sha256,
        ).payload
        == campaign.evidence.payload
    )
    with pytest.raises(PhysicalNativeCameraCampaignError, match="CONSUMED"):
        campaign.run_scoped_campaign(
            permit,
            deadline_ns=time.monotonic_ns() + 1,
            cancellation=threading.Event(),
            authorization=object(),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"cell_id": "wizard-rehearsal-" + "b" * 16},
        {"session_id": "rehearsal-" + "c" * 32},
        {"source_sha256": "f" * 64},
        {"selection": None},
        {"runtime": None},
        {"mode": NativeCameraMode(4, 2, 9, 1)},
        {"controls": (CameraControlSetting("brightness", 4),)},
        {"budget": CameraCampaignBudget(6000, 1, 16, 16)},
    ],
)
def test_invalid_probe_plan_input_is_rejected_before_source_or_runner(
    tmp_path: Path, change: Any
):
    args, kwargs = arguments(tmp_path)
    kwargs.update(change)
    with pytest.raises((ValueError, CameraWorkerError)):
        PhysicalNativeCameraCampaign(*args, **kwargs)


@pytest.mark.parametrize(
    "bad",
    [
        Path("C:\\"),
        Path("relative"),
        Path(r"\\server\share\private"),
        Path(r"C:\assigned\..\other"),
        Path(r"C:\assigned\stream:ads"),
        Path(r"C:\assigned\CON"),
    ],
)
def test_output_parent_must_be_exact_local_nonroot_path(tmp_path: Path, bad: Path):
    args, kwargs = arguments(tmp_path)
    with pytest.raises(ValueError):
        PhysicalNativeCameraCampaign(args[0], bad, **kwargs)


@pytest.mark.parametrize(
    "change",
    [
        {"mode": None},
        {"budget": None},
        {"mode": NativeCameraMode(3, 2, 9, 1)},
        {"mode": NativeCameraMode(4, 2, 9, 1, "MJPG")},
        {"mode": NativeCameraMode(4, 2, 9, 1, "YUY2", 16)},
        {"budget": CameraCampaignBudget(6000, 2, 16, 32)},
        {"controls": [CameraControlSetting("brightness", 4)]},
        {
            "controls": (
                CameraControlSetting("gain", 1),
                CameraControlSetting("brightness", 4),
            )
        },
        {
            "controls": (
                CameraControlSetting("gain", 1),
                CameraControlSetting("gain", 1),
            )
        },
    ],
)
def test_invalid_capture_settings_or_budget_are_rejected_by_existing_native_preparation(
    tmp_path: Path, change: Any
):
    args, kwargs = arguments(tmp_path, capture=True)
    kwargs.update(change)
    with pytest.raises((ValueError, CameraWorkerError)):
        PhysicalNativeCameraCampaign(*args, **kwargs)


def test_nested_input_objects_are_copied_and_forged_fields_rejected(tmp_path: Path):
    args, kwargs = arguments(tmp_path, capture=True)
    mode = kwargs["mode"]
    campaign = PhysicalNativeCameraCampaign(*args, **kwargs)
    object.__setattr__(mode, "width", 16384)
    object.__setattr__(kwargs["selection"], "payload", b"{}")
    assert campaign.plan()["mode"]["width"] == 4
    assert (
        PhysicalCameraSelection(canonical(campaign.plan()["selection"])).sha256
        == campaign.plan()["selected_identity_sha256"]
    )
    args, kwargs = arguments(tmp_path, capture=True)
    object.__setattr__(kwargs["mode"], "unreviewed", True)
    with pytest.raises(ValueError, match="FIELDS"):
        PhysicalNativeCameraCampaign(*args, **kwargs)


@pytest.mark.parametrize(
    "field",
    ["source", "identity", "mode", "session", "cell", "registration", "envelope"],
)
def test_permit_must_bind_exact_plan_new_identity_and_domain(
    tmp_path: Path, field: str
):
    campaign = campaign_fixture(tmp_path)
    _, _, permit = components(campaign)
    if field in {"source", "identity", "mode"}:
        changes = {
            "source": {"source_binding_sha256": "f" * 64},
            "identity": {"selected_identity_sha256": "e" * 64},
            "mode": {"mode": CommissioningMode.REHEARSAL},
        }[field]
        changed = replace(permit.admission, **changes)
        permit = replace(
            permit,
            admission=changed,
            request=replace(
                permit.request, expected_challenge_sha256=changed.challenge_sha256
            ),
        )
    elif field in {"cell", "session"}:
        permit = replace(
            permit, request=replace(permit.request, **{field + "_id": "other"})
        )
    elif field == "registration":
        permit = replace(
            permit, registration=replace(permit.registration, operation_sha256="f" * 64)
        )
    else:
        permit = replace(
            permit,
            envelope=EnergizationEnvelope(
                "energy", SOURCE, *("a" * 64,) * 4, "operator", "observer", 0, 1
            ),
        )
    with pytest.raises(PhysicalNativeCameraCampaignError, match="PERMIT_BINDING"):
        campaign.preparation_for_permit(permit)


@pytest.mark.parametrize("phase", ["before", "during-current-check"])
def test_source_drift_after_consumption_never_reaches_native_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
):
    campaign = campaign_fixture(tmp_path)
    core, store, permit = components(campaign)
    calls = []

    def source(path: Path):
        calls.append(path)
        return "f" * 64 if phase == "before" or len(calls) > 1 else SOURCE

    monkeypatch.setattr(module, "source_fingerprint", source)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and campaign.evidence is None
    assert not store.evidence
    assert store.trace.count("ACKNOWLEDGED_ONCE") == 1
    assert len(calls) == (1 if phase == "before" else 2)


def test_stop_before_dispatch_does_not_consume_worker_or_read_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    campaign = campaign_fixture(tmp_path)
    core, store, permit = components(campaign)
    monkeypatch.setattr(
        module,
        "source_fingerprint",
        lambda *a: pytest.fail("cancelled worker source read"),
    )
    cancelled = threading.Event()
    cancelled.set()
    result = core.execute(permit, cancellation=cancelled)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert campaign.evidence is None and not store.evidence


@pytest.mark.parametrize(
    "mutation",
    ["authority", "extra", "output-policy", "identity-hash", "runtime-purpose"],
)
def test_rehashed_plan_tampering_is_not_accepted_as_same_contract(
    tmp_path: Path, mutation: str
):
    plan = campaign_fixture(tmp_path).plan()
    if mutation == "authority":
        plan["physical_authority"] = True
    elif mutation == "extra":
        plan["runner"] = "arbitrary"
    elif mutation == "output-policy":
        plan["output_policy"]["create_directories"] = True
    elif mutation == "identity-hash":
        plan["selected_identity_sha256"] = "f" * 64
    else:
        plan["runtime"]["purpose"] = "METADATA"
    with pytest.raises(ValueError):
        PhysicalNativeCameraCampaign.from_plan(plan)


def test_no_unscoped_or_authorized_boolean_execution_api(tmp_path: Path):
    campaign = campaign_fixture(tmp_path)
    _, _, permit = components(campaign)
    for method in (campaign.run_campaign, campaign.run_retained_campaign):
        with pytest.raises(PhysicalNativeCameraCampaignError):
            method(permit)
    with pytest.raises(PhysicalNativeCameraCampaignError, match="EXACT_CONSUMED_SCOPE"):
        campaign.run_scoped_campaign(
            permit,
            deadline_ns=time.monotonic_ns() + 10**9,
            cancellation=threading.Event(),
            authorization=True,
        )


def test_trusted_retained_hash_and_original_preparation_are_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    campaign = campaign_fixture(tmp_path)
    core, _, permit = components(campaign)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)
    core.execute(permit)
    evidence = campaign.evidence
    assert evidence is not None
    for wrong_hash in ("f" * 64, None, True):
        with pytest.raises(ValueError):
            verify_physical_native_camera_campaign_evidence(
                evidence,
                campaign=campaign,
                expected_permit=permit,
                expected_evidence_sha256=wrong_hash,
            )
    changed = evidence.to_dict()
    changed["parent_deadline_ns"] = permit.expires_at_ns + 1
    # Structurally valid diagnostic bytes can still violate the original permit.
    altered = OwnedNativeCameraRunEvidence(canonical(changed))
    with pytest.raises(ValueError, match="DEADLINE"):
        verify_physical_native_camera_campaign_evidence(
            altered,
            campaign=campaign,
            expected_permit=permit,
            expected_evidence_sha256=altered.evidence_sha256,
        )
    with pytest.raises(ValueError):
        verify_physical_native_camera_campaign_evidence(
            evidence,
            campaign=campaign,
            expected_permit=replace(permit, nonce="9" * 64),
            expected_evidence_sha256=evidence.evidence_sha256,
        )


@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="actual qualified NTFS and Windows leases")
def test_actual_m1_scope_retains_real_native_runner_pre_owner_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Actual M1 -> scoped core -> real held runner -> full immutable evidence.

    Predecessor records are clearly marked incapable storage fixtures. This is
    not a received-device or complete physical-onboarding qualification test.
    """
    from rocell.application.commissioning_camera_persistence import (
        M1PhysicalCameraPersistence,
        PhysicalCameraAdmissionFacts,
        physical_camera_source_binding,
    )
    from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
    from test_commissioning_camera_persistence import runtime_and_adapter, facts
    from test_physical_camera_coordinator import LEASES

    runtime, adapter = runtime_and_adapter(tmp_path)
    campaign = campaign_fixture(tmp_path)
    original_facts = facts(None, None)
    selected_document = campaign.plan()["selection"]

    def actual_facts(request: Any, snapshot: Any):
        return PhysicalCameraAdmissionFacts(
            original_facts.hazard_assessment_document,
            original_facts.configuration_epoch_documents,
            selected_document,
        )

    adapter._facts = actual_facts
    monkeypatch.setattr(module, "source_fingerprint", lambda *args: SOURCE)
    reg = campaign.registration()
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=adapter,
        registrations=(reg,),
        workers={reg.worker_id: campaign},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, reg.action_id, "actual-held-native-once", "1" * 64
    )
    with adapter.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    permit = core.prepare(request)
    outcome = core.execute(permit)
    assert outcome.state is AttemptState.SEALED_UNCERTAIN
    assert (
        outcome.receipt is not None
        and outcome.receipt.effect_certainty is EffectCertainty.UNCERTAIN
    )
    assert outcome.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert outcome.physical_authority == "NONE"
    evidence = campaign.evidence
    assert evidence is not None, outcome.reason_codes
    assert evidence.to_dict()["primary_error"] == "PHYSICAL_PROVIDER_QUALIFICATION_HELD"
    assert evidence.to_dict()["owner_constructed"] is False
    assert evidence.to_dict()["process"]["created"] is False
    assert evidence.native_receipt is None
    assert core.execute(permit) == outcome
    verified_runtime = runtime.verify(SESSION)
    assert verified_runtime.quarantined
    assert permit.attempt_id in verified_runtime.uncertain_attempt_ids
    assert not verified_runtime.active_lease_owners
    assert not (tmp_path / "assigned-output").exists()
    with adapter.stage_transaction(
        SESSION, expected_challenge_sha256=verified_runtime.challenge_sha256
    ) as tx:
        retained = tx.read_campaign_evidence(permit.attempt_id)
        assert retained[0].payload == evidence.payload
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert len(tx._audit_records()) >= 3
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=actual_facts
    )
    with fresh.stage_transaction(
        SESSION, expected_challenge_sha256=fresh.verification(SESSION).challenge_sha256
    ) as tx:
        raw = tx.read_campaign_evidence(permit.attempt_id)[0]
        original_permit = tx.read_campaign_permit(permit.attempt_id)
    monkeypatch.setattr(
        module,
        "source_fingerprint",
        lambda *a: pytest.fail("reopen replay/read source"),
    )
    audited = verify_physical_native_camera_campaign_evidence(
        OwnedNativeCameraRunEvidence(raw.payload),
        campaign=PhysicalNativeCameraCampaign.from_plan(campaign.plan()),
        expected_permit=original_permit,
        expected_evidence_sha256=raw.payload_sha256,
    )
    assert audited.payload == evidence.payload
