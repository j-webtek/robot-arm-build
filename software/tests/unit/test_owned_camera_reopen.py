"""Independent pure record joins; parent integration owns actual M1/content I/O."""

from copy import deepcopy
from dataclasses import asdict, replace
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import rocell.application.commissioning_rehearsal_reopen as reopen
import rocell.application.windows_camera_capture_ingest as ingest
from rocell.application.camera_rehearsal_campaign import camera_settings
from rocell.application.camera_configuration import compare_camera_readback
from rocell.application.wizard_camera_configuration import (
    effective_camera_settings_epoch,
)
from rocell.application.camera_capture_dataset import (
    PLAN_SCHEMA,
    _DECLARATIONS,
    DatasetQuotas,
    DatasetReceipt,
    DatasetVerification,
    FramePlan,
)
from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    AttemptResult,
    CampaignBudget,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    MAX_RETAINED_CAMPAIGN_BYTES,
    ObservedPowerState,
    RegisteredActionRequest,
    WorkerReceipt,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    rehearsal_source_binding,
)
from rocell.application.owned_camera_rehearsal_campaign import OwnedBinaryCameraWorker
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.rehearsal_owned_camera_evidence import (
    retain_owned_camera_evidence,
)
from rocell.providers.windows.camera_worker_client import (
    CameraEndpointBinding,
    CameraCampaignBudget,
    CameraCandidate,
    NativeControlObservation,
)
from rocell.providers.windows._owned_camera_fixture import fixture_readback
from rocell.providers.windows.owned_camera_codec import CONFIG_RESULT_SCHEMA
from rocell.safety.effects import EffectCertainty, EffectClass

from test_rehearsal_owned_camera_evidence import complete_inputs, canonical, digest
from rocell.application.rehearsal_owned_camera_evidence import _plain

SOURCE = "a" * 64
STAGE = PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
SCRIPT = b"closed camera fixture source pin"
SCRIPT_SHA = hashlib.sha256(SCRIPT).hexdigest()
STORE = Path("C:/owned-camera-reopen-fixture")
FIXTURE = STORE / ("binary-fixture-" + "3" * 32)
SELECTED = {
    "candidate_id": "synthetic-b0477",
    "provenance": "SYNTHETIC_NOT_ENUMERATED",
    "model": "B0477",
    "unit_id": "SYNTHETIC-UNIT-A",
    "endpoint": "incapable-fixture-only",
}


def record(kind, data):
    # These stand for records already checked by tx._audit_records; no unit
    # fixture here pretends that hashing a dictionary is a real M1 ledger audit.
    return {"kind": kind, "data": json.loads(canonical(data))}


def scenario(monkeypatch, *, stage=STAGE, count=1, configuration=None):
    monkeypatch.setattr(
        reopen, "read_bounded_regular_file", lambda path, *, maximum_bytes: SCRIPT
    )
    settings = camera_settings(0)
    epoch = digest(settings)
    plan = {
        "composition": INCAPABLE_COMPOSITION,
        "process_backend": "OWNED_INCAPABLE_CAMERA_PROCESS",
        "selected_camera": SELECTED.copy(),
        "mode": dict(reopen._MODE),
        "frame_count": count,
        "fault": "none",
        "settings": settings,
        "settings_epoch": epoch,
        "native_frame_bytes_generated": True,
        "binary_artifact_budget_bytes": (2 * 39923712 + 4990464) * count
        + 128 * 1024 * 1024,
        "artifact_qualification": "DIAGNOSTIC_ONLY_NOT_M1_QUALIFIED",
        "process_timeout_ms": 25000,
        "process_cleanup_timeout_ms": 2000,
        "native_duration_ms": 20000,
        "stdout_bytes": 32768,
        "stderr_bytes": 8192,
    }
    controls = configuration.controls if configuration is not None else ()
    capture_epoch = epoch
    if configuration is not None:
        capture_epoch = effective_camera_settings_epoch(epoch, configuration)
        plan.update(
            electronic_configuration=configuration.to_dict(),
            probe_evidence_sha256=configuration.to_dict()["probe_evidence_sha256"],
            effective_settings_epoch=capture_epoch,
        )
    registration = CampaignRegistration(
        "rehearsal-owned-camera-campaign",
        stage,
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        "incapable-owned-camera-campaign",
        SCRIPT_SHA,
        digest(plan),
        (LeaseLevel.CAMERA,),
        CampaignBudget(
            60000, MAX_RETAINED_CAMPAIGN_BYTES, 1, count, len(controls), count, 1
        ),
    )
    session, attempt = "rehearsal-" + "4" * 32, "attempt-" + "5" * 32
    admission = AdmissionSnapshot(
        "wizard-rehearsal-" + "6" * 16,
        session,
        CommissioningMode.REHEARSAL,
        stage,
        V2StageState.WAITING_OPERATOR,
        1,
        rehearsal_source_binding(SOURCE),
        *(["7" * 64] * 7),
        ("8" * 64,) * 8,
        digest(SELECTED),
        False,
        0,
    )
    request = RegisteredActionRequest(
        admission.cell_id,
        session,
        registration.action_id,
        "request-camera",
        admission.challenge_sha256,
    )
    permit = ExactOperationPermit(
        attempt, request, admission, registration, 100, 1000, "9" * 64
    )
    inputs = complete_inputs(count)
    camera_binding = CameraEndpointBinding(
        SELECTED["endpoint"],
        hashlib.sha256(SELECTED["endpoint"].encode()).hexdigest(),
        digest(SELECTED),
    )
    activation = replace(
        inputs["activation_request"],
        campaign_id=attempt,
        binding=camera_binding,
        helper_sha256=SCRIPT_SHA,
        budget=CameraCampaignBudget(20000, count, 39923712, 39923712 * count),
        output_directory=str(FIXTURE / "native"),
        controls=controls,
    )
    native = replace(
        inputs["native_receipt"],
        selected_endpoint=SELECTED["endpoint"],
        candidates=(CameraCandidate(SELECTED["endpoint"], "Incapable fixture"),),
    )
    if controls:
        native = replace(
            native,
            controls=tuple(
                NativeControlObservation(**row)
                for row in fixture_readback(_plain(controls))
            ),
            counts={**native.counts, "control_set_attempts": len(controls)},
        )
    ingest_plan = ingest.prepare_windows_camera_ingest(
        activation,
        capture_directory=FIXTURE / "native",
        dataset_root=FIXTURE / "datasets",
        source_sha256=SOURCE,
        settings_epoch=capture_epoch,
        domain="INCAPABLE_NATIVE_FIXTURE",
        frames=tuple(FramePlan(f"frame-{i:06d}") for i in range(count)),
        quotas=DatasetQuotas(disk_reserve_bytes=0),
    )
    capture_plan, _ = ingest._validate_receipt(activation, native, ingest_plan)
    dataset_path = (
        FIXTURE / "datasets" / ("ingest-" + "1" * 32) / ("capture-" + "2" * 32)
    )
    dataset = DatasetReceipt(
        dataset_path,
        "f" * 64,
        digest(
            {
                "schema": PLAN_SCHEMA,
                "plan": _plain(capture_plan),
                "declarations": _DECLARATIONS,
            },
            newline=True,
        ),
        count,
        count * 39923712,
    )
    verification = DatasetVerification(
        dataset_path,
        dataset.manifest_sha256,
        capture_plan,
        count,
        dataset.logical_bytes,
        True,
        True,
    )
    source = {
        **inputs["source_contract"],
        "plan": _plain(ingest_plan),
        "activation_request": _plain(activation),
        "native_receipt": _plain(native),
        "native_receipt_sha256": digest(_plain(native), newline=True),
        "capture_plan": _plain(capture_plan),
    }
    capture = replace(
        inputs["capture"],
        dataset=dataset,
        verification=verification,
        envelope_path=dataset_path.parent / "ingest-receipt.json",
        source_contract_sha256=digest(source, newline=True),
    )
    envelope = {
        key: value
        for key, value in capture.to_dict().items()
        if key not in {"envelope_path", "envelope_sha256"}
    }
    envelope.update(
        activation_request_sha256=ingest.activation_request_sha256(activation),
        native_receipt_sha256=source["native_receipt_sha256"],
    )
    capture = replace(capture, envelope_sha256=digest(envelope, newline=True))
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["attempt_id"] = attempt
    wire["fixture_result"]["camera_request_sha256"] = digest(_plain(activation))
    wire["fixture_result"]["native_receipt"]["selected_endpoint"] = SELECTED["endpoint"]
    wire["fixture_result"]["native_receipt"]["devices"] = _plain(native.candidates)
    if controls:
        wire["schema"] = CONFIG_RESULT_SCHEMA
        wire["fixture_result"]["native_receipt"].update(
            controls=_plain(native.controls), counts=dict(native.counts)
        )
    process = replace(
        inputs["process_result"],
        attempt_id=attempt,
        stdout=canonical(wire),
        parsed_result=wire,
    )
    evidence = retain_owned_camera_evidence(
        binding={
            "session_id": session,
            "attempt_id": attempt,
            "source_sha256": SOURCE,
            "permit_sha256": permit.permit_sha256,
            "operation_sha256": registration.operation_sha256,
            "selected_identity_sha256": admission.selected_identity_sha256,
            "settings_epoch": capture_epoch,
        },
        activation_request=activation,
        native_receipt=native,
        process_result=process,
        capture=capture,
        capture_envelope=envelope,
        source_contract=source,
        error=None,
    )
    receipt = WorkerReceipt(
        attempt,
        permit.permit_sha256,
        SCRIPT_SHA,
        admission.selected_identity_sha256,
        EffectCertainty.CONFIRMED,
        True,
        ObservedPowerState.UNKNOWN,
        1,
        count,
        len(controls),
        count,
        1,
        len(evidence.payload),
        (evidence.evidence_sha256,),
    )
    result = AttemptResult(
        attempt, AttemptState.SEALED_KNOWN, permit.permit_sha256, (), receipt, False
    )
    common = {"attempt_id": attempt, "permit_sha256": permit.permit_sha256}
    records = {
        "request.json": record(
            "EXACT_REQUEST_RESERVED",
            {**common, "request_key": request.request_key, "permit": asdict(permit)},
        ),
        "result.json": record("CAMPAIGN_RESULT", {**common, "result": asdict(result)}),
        "observed.json": record(
            "CAMPAIGN_RECEIPT",
            {**common, "state": "EFFECT_OBSERVED", "receipt": asdict(receipt)},
        ),
        "cleanup.json": record(
            "CAMPAIGN_RECEIPT",
            {**common, "state": "CLEANUP_CONFIRMED", "receipt": asdict(receipt)},
        ),
        "evidence.json": record(
            "CAMPAIGN_EVIDENCE",
            {
                **common,
                "evidence": [
                    {
                        "schema": "rocell.rehearsal_owned_camera_evidence.v1",
                        "label": "owned-camera-campaign",
                        "payload_bytes": len(evidence.payload),
                        "payload_sha256": evidence.evidence_sha256,
                        "payload_base64": base64.b64encode(evidence.payload).decode(
                            "ascii"
                        ),
                    }
                ],
            },
        ),
    }
    document = json.loads(
        canonical(
            {
                "schema": "rocell.rehearsal_camera_campaign.v2",
                "composition": INCAPABLE_COMPOSITION,
                "session_id": session,
                "stage": stage.value,
                "operator_id": "operator-a",
                "workspace_source_sha256": SOURCE,
                "plan": plan,
                "attempt_result": asdict(result),
                "physical_observation": False,
                "capture_dataset": capture.to_dict(),
                "retained_campaign_sha256": evidence.evidence_sha256,
                "camera_process": evidence.view(),
            }
        )
    )
    if configuration is not None:
        document["camera_readback"] = compare_camera_readback(
            configuration, native, expected_settings_epoch=configuration.settings_epoch
        )
    return document, records, evidence, verification, permit


def wrapped(document, *, at=20):
    payload = canonical(document)
    stage = PhysicalOnboardingStage(document.get("stage", STAGE.value))
    reference = EvidenceReference(
        "evidence-fixture",
        stage,
        "a" * 64,
        "b" * 64,
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )
    return reopen.VerifiedRehearsalEvidence(reference, payload, at)


@pytest.mark.parametrize(
    "stage", [STAGE, PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS]
)
def test_original_owned_attempt_retained_result_and_view_join_without_worker(
    monkeypatch, stage
):
    document, records, evidence, _, _ = scenario(monkeypatch, stage=stage)
    monkeypatch.setattr(
        OwnedBinaryCameraWorker,
        "__init__",
        lambda *a, **k: pytest.fail("Reopen constructed a worker"),
    )
    verified = reopen._verify_owned_camera_campaign(document, SOURCE, records)
    assert verified.payload == evidence.payload
    assert verified.view()["status"] == "RETAINED_COMPLETE_REHEARSAL"
    assert verified.view()["physical_authority"] is False


@pytest.mark.parametrize(
    "missing",
    ["request.json", "result.json", "observed.json", "cleanup.json", "evidence.json"],
)
def test_any_missing_audited_lifecycle_component_holds(monkeypatch, missing):
    document, records, _, _, _ = scenario(monkeypatch)
    records.pop(missing)
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_owned_camera_campaign(document, SOURCE, records)
    assert error.value.code == "OWNED_CAMERA_RECORD_MISMATCH"


@pytest.mark.parametrize(
    "duplicate",
    ["request.json", "result.json", "observed.json", "cleanup.json", "evidence.json"],
)
def test_duplicate_record_for_same_attempt_never_selects_first(monkeypatch, duplicate):
    document, records, _, _, _ = scenario(monkeypatch)
    records["duplicate"] = deepcopy(records[duplicate])
    with pytest.raises(reopen.RehearsalReopenError):
        reopen._verify_owned_camera_campaign(document, SOURCE, records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("process_backend", "IN_PROCESS"),
        ("frame_count", True),
        ("fault", "cleanup-uncertain"),
        ("binary_artifact_budget_bytes", 0),
        ("process_timeout_ms", 26000),
        ("process_cleanup_timeout_ms", 3000),
        ("native_duration_ms", 25000),
        ("stdout_bytes", 65536),
        ("stderr_bytes", 65536),
        ("settings_epoch", "0" * 64),
        ("native_frame_bytes_generated", 1),
        ("unexpected", False),
    ],
)
def test_owned_plan_is_closed_and_exact(monkeypatch, field, value):
    document, records, _, _, _ = scenario(monkeypatch)
    document["plan"][field] = value
    with pytest.raises(reopen.RehearsalReopenError):
        reopen._verify_owned_camera_campaign(document, SOURCE, records)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(retained_campaign_sha256="0" * 64),
        lambda d: d["camera_process"]["process"].update(tree_exit_confirmed=False),
        lambda d: d["capture_dataset"]["dataset"].update(manifest_sha256="0" * 64),
        lambda d: d.update(workspace_source_sha256="0" * 64),
        lambda d: d.update(physical_observation=True),
        lambda d: d.update(stage=PhysicalOnboardingStage.ARM_IDENTITY.value),
    ],
)
def test_stage_receipt_cannot_substitute_capture_summary_or_scope(monkeypatch, change):
    document, records, _, _, _ = scenario(monkeypatch)
    change(document)
    with pytest.raises((reopen.RehearsalReopenError, ValueError)):
        reopen._verify_owned_camera_campaign(document, SOURCE, records)


def test_changed_current_fixed_child_source_holds_instead_of_replaying(monkeypatch):
    document, records, _, _, _ = scenario(monkeypatch)
    monkeypatch.setattr(
        reopen,
        "read_bounded_regular_file",
        lambda path, *, maximum_bytes: b"different source",
    )
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_owned_camera_campaign(document, SOURCE, records)
    assert error.value.code == "OWNED_CAMERA_PERMIT_MISMATCH"


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "other.v1"),
        ("label", "other-role"),
        ("payload_sha256", "0" * 64),
        ("payload_bytes", True),
        ("payload_base64", "%%%"),
    ],
)
def test_full_retained_blob_exact_role_and_bytes_required(monkeypatch, field, value):
    document, records, _, _, _ = scenario(monkeypatch)
    records["evidence.json"]["data"]["evidence"][0][field] = value
    with pytest.raises((ValueError, M1CommissioningPersistenceError)):
        reopen._verify_owned_camera_campaign(document, SOURCE, records)


def test_external_result_evidence_tuple_cannot_revert_to_dataset_hashes(monkeypatch):
    document, records, _, _, _ = scenario(monkeypatch)
    old_hashes = [
        document["capture_dataset"]["envelope_sha256"],
        document["capture_dataset"]["dataset"]["manifest_sha256"],
    ]
    document["attempt_result"]["receipt"]["evidence_sha256s"] = old_hashes
    records["result.json"]["data"]["result"] = deepcopy(document["attempt_result"])
    for name in ("observed.json", "cleanup.json"):
        records[name]["data"]["receipt"] = deepcopy(
            document["attempt_result"]["receipt"]
        )
    with pytest.raises(M1CommissioningPersistenceError):
        reopen._verify_owned_camera_campaign(document, SOURCE, records)


def test_dataset_read_happens_after_record_join_and_uses_exact_original_binding(
    monkeypatch,
):
    document, records, _, verification, _ = scenario(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "rocell.application.camera_capture_dataset.verify_capture_dataset",
        lambda path, **kw: (calls.append(("metadata", path, kw)) or verification),
    )
    monkeypatch.setattr(
        ingest,
        "verify_windows_capture_ingest",
        lambda report, **kw: (calls.append(("content", report, kw)) or verification),
    )
    settings = wrapped(
        {
            "settings": document["plan"]["settings"],
            "settings_epoch": document["plan"]["settings_epoch"],
        },
        at=10,
    )
    root = reopen._verify_camera_receipt(
        STORE, wrapped(document), SOURCE, settings, records=records
    )
    assert root == FIXTURE
    assert [call[0] for call in calls] == ["metadata", "content"]
    expected = calls[-1][2]
    assert expected["expected_source_sha256"] == SOURCE
    assert expected["expected_settings_epoch"] == document["plan"]["settings_epoch"]
    assert expected["expected_campaign_id"] == document["attempt_result"]["attempt_id"]
    assert (
        expected["expected_endpoint_sha256"]
        == hashlib.sha256(b"incapable-fixture-only").hexdigest()
    )
    records.pop("evidence.json")
    calls.clear()
    with pytest.raises(reopen.RehearsalReopenError):
        reopen._verify_camera_receipt(
            STORE, wrapped(document), SOURCE, settings, records=records
        )
    assert calls == []


def test_owned_camera_cannot_reopen_without_audited_records(monkeypatch):
    document, _, _, _, _ = scenario(monkeypatch)
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_camera_receipt(
            STORE,
            wrapped(document),
            SOURCE,
            wrapped(
                {
                    "settings": document["plan"]["settings"],
                    "settings_epoch": document["plan"]["settings_epoch"],
                }
            ),
        )
    assert error.value.code == "OWNED_CAMERA_RECORDS_MISSING"


def test_removing_owned_marker_cannot_downgrade_an_owned_attempt_to_legacy(monkeypatch):
    document, records, _, _, _ = scenario(monkeypatch)
    document["plan"].pop("process_backend")
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_camera_receipt(
            STORE, wrapped(document), SOURCE, wrapped({}), records=records
        )
    assert error.value.code == "OWNED_CAMERA_BACKEND_MISMATCH"


def test_legacy_inprocess_v2_path_remains_supported_without_owned_blob(monkeypatch):
    document, _, _, verification, _ = scenario(monkeypatch)
    for key in (
        "process_backend",
        "process_timeout_ms",
        "process_cleanup_timeout_ms",
        "native_duration_ms",
        "stdout_bytes",
        "stderr_bytes",
    ):
        document["plan"].pop(key)
    document.pop("retained_campaign_sha256")
    document.pop("camera_process")
    document["plan"]["binary_artifact_budget_bytes"] -= 4990464
    monkeypatch.setattr(
        "rocell.application.camera_capture_dataset.verify_capture_dataset",
        lambda *a, **kw: verification,
    )
    monkeypatch.setattr(
        ingest, "verify_windows_capture_ingest", lambda *a, **kw: verification
    )
    settings = wrapped(
        {
            "settings": document["plan"]["settings"],
            "settings_epoch": document["plan"]["settings_epoch"],
        },
        at=10,
    )
    assert (
        reopen._verify_camera_receipt(STORE, wrapped(document), SOURCE, settings)
        == FIXTURE
    )


def test_read_evidence_accepts_owned_extension_only_with_both_exact_fields(monkeypatch):
    document, _, _, _, _ = scenario(monkeypatch)

    def read(item):
        receipt = wrapped(item)
        snapshot = SimpleNamespace(
            evidence=(receipt.reference,),
            header=SimpleNamespace(session_id=document["session_id"]),
        )

        def fake_document(path, **kw):
            return (
                (deepcopy(item), receipt.payload)
                if path.name == "payload.bin"
                else ({"captured_at_ns": 20}, b"{}")
            )

        monkeypatch.setattr(reopen, "_document", fake_document)
        return reopen._read_evidence(STORE, snapshot, SOURCE, "b" * 64)

    assert read(document)
    for key in ("camera_process", "retained_campaign_sha256"):
        changed = deepcopy(document)
        changed.pop(key)
        with pytest.raises(reopen.RehearsalReopenError):
            read(changed)
    changed = deepcopy(document)
    changed["schema"] = "rocell.rehearsal_camera_campaign.v1"
    with pytest.raises(reopen.RehearsalReopenError):
        read(changed)
