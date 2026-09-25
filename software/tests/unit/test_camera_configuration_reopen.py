"""Pure already-audited-record stand-ins; no M1/process/filesystem execution."""

import base64
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application.camera_configuration import stage_camera_configuration
from rocell.application.cell_commissioning_coordinator import (
    AttemptResult,
    CampaignBudget,
    CampaignRegistration,
    ExactOperationPermit,
    MAX_RETAINED_CAMPAIGN_BYTES,
    ObservedPowerState,
    RegisteredActionRequest,
    WorkerReceipt,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.rehearsal_camera_probe_evidence import (
    retain_rehearsal_camera_probe_evidence,
)
from rocell.application.rehearsal_owned_camera_evidence import _canonical, _plain
from rocell.application.wizard_camera_configuration import (
    effective_camera_settings_epoch,
)
from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.owned_camera_codec import CAMERA_FIXTURE_PATH
from rocell.safety.effects import EffectCertainty, EffectClass
from test_owned_camera_reopen import (
    scenario as capture_scenario,
    record,
    wrapped,
    SCRIPT_SHA,
    STORE,
    SOURCE,
)
from test_rehearsal_camera_probe_evidence import probe_inputs


def digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def retained(document, label, when):
    item = wrapped(document, at=when)
    return replace(item, reference=replace(item.reference, evidence_id=label))


def probe_context(monkeypatch, *, configured=True, controls=None):
    capture_doc, _, _, _, prior_permit = capture_scenario(monkeypatch)
    selected = capture_doc["plan"]["selected_camera"]
    plan = {
        "composition": reopen.INCAPABLE_COMPOSITION,
        "process_backend": "OWNED_INCAPABLE_CAMERA_PROBE",
        "selected_camera": selected,
        "fault": "none",
        "native_duration_ms": 5000,
        "process_timeout_ms": 10000,
        "process_cleanup_timeout_ms": 2000,
        "stdout_bytes": 32768,
        "stderr_bytes": 8192,
        "frames_requested": 0,
        "control_writes_requested": 0,
        "artifact_qualification": "DIAGNOSTIC_ONLY_NOT_PHYSICAL_QUALIFICATION",
    }
    registration = CampaignRegistration(
        "rehearsal-owned-camera-probe",
        STAGE_ORDER[4],
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        "incapable-owned-camera-probe",
        SCRIPT_SHA,
        digest(plan),
        (LeaseLevel.CAMERA,),
        CampaignBudget(60000, MAX_RETAINED_CAMPAIGN_BYTES, 1, 0, 0, 0, 1),
    )
    admission = prior_permit.admission
    action = RegisteredActionRequest(
        admission.cell_id,
        admission.session_id,
        registration.action_id,
        "request-probe-fixture",
        admission.challenge_sha256,
    )
    permit = ExactOperationPermit(
        "attempt-" + "9" * 32, action, admission, registration, 100, 1000, "a" * 64
    )
    inputs = probe_inputs()
    request = replace(
        inputs["activation_request"],
        campaign_id=permit.attempt_id,
        source_sha256=SOURCE,
        helper_sha256=SCRIPT_SHA,
        binding=replace(
            inputs["activation_request"].binding,
            binding_sha256=admission.selected_identity_sha256,
        ),
    )
    prepared = WindowsCameraWorkerClient(CAMERA_FIXTURE_PATH, SCRIPT_SHA).prepare_probe(
        request.binding,
        source_sha256=SOURCE,
        campaign_id=permit.attempt_id,
        budget=request.budget,
    )
    request = prepared.request
    binding = {
        "session_id": admission.session_id,
        "attempt_id": permit.attempt_id,
        "source_sha256": SOURCE,
        "permit_sha256": permit.permit_sha256,
        "operation_sha256": registration.operation_sha256,
        "selected_identity_sha256": admission.selected_identity_sha256,
    }
    payload = {
        **inputs["owned_payload"],
        "camera_request": _plain(request),
        "native_arguments": list(prepared.arguments),
        "working_directory": str(STORE / ("camera-probe-" + permit.attempt_id)),
    }
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["attempt_id"] = permit.attempt_id
    wire["fixture_result"]["camera_request_sha256"] = digest(_plain(request))
    process = replace(
        inputs["process_result"],
        attempt_id=permit.attempt_id,
        stdout=_canonical(wire),
        parsed_result=wire,
    )
    artifact = retain_rehearsal_camera_probe_evidence(
        binding=binding,
        activation_request=request,
        process_result=process,
        native_receipt=inputs["native_receipt"],
        owned_payload=payload,
    )
    receipt = WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        SCRIPT_SHA,
        admission.selected_identity_sha256,
        EffectCertainty.CONFIRMED,
        True,
        ObservedPowerState.UNKNOWN,
        1,
        0,
        0,
        0,
        1,
        len(artifact.payload),
        (artifact.evidence_sha256,),
    )
    result = AttemptResult(
        permit.attempt_id,
        AttemptState.SEALED_KNOWN,
        permit.permit_sha256,
        (),
        receipt,
        False,
    )
    common_record = {
        "attempt_id": permit.attempt_id,
        "permit_sha256": permit.permit_sha256,
    }
    records = {
        "probe-request": record(
            "EXACT_REQUEST_RESERVED",
            {
                **common_record,
                "request_key": action.request_key,
                "permit": asdict(permit),
            },
        ),
        "probe-result": record(
            "CAMPAIGN_RESULT", {**common_record, "result": asdict(result)}
        ),
        "probe-observed": record(
            "CAMPAIGN_RECEIPT",
            {**common_record, "state": "EFFECT_OBSERVED", "receipt": asdict(receipt)},
        ),
        "probe-cleanup": record(
            "CAMPAIGN_RECEIPT",
            {**common_record, "state": "CLEANUP_CONFIRMED", "receipt": asdict(receipt)},
        ),
        "probe-evidence": record(
            "CAMPAIGN_EVIDENCE",
            {
                **common_record,
                "evidence": [
                    {
                        "schema": "rocell.rehearsal_camera_probe_evidence.v1",
                        "label": "owned-camera-probe",
                        "payload_bytes": len(artifact.payload),
                        "payload_sha256": artifact.evidence_sha256,
                        "payload_base64": base64.b64encode(artifact.payload).decode(
                            "ascii"
                        ),
                    }
                ],
            },
        ),
    }
    common = {
        "composition": reopen.INCAPABLE_COMPOSITION,
        "stage": STAGE_ORDER[4].value,
        "session_id": admission.session_id,
        "cell_id": admission.cell_id,
        "workspace_source_sha256": SOURCE,
        "operator_id": "operator-a",
        "catalog_sha256": "b" * 64,
        "physical_observation": False,
    }
    document = {
        **common,
        "schema": "rocell.rehearsal_camera_probe_receipt.v1",
        "plan": plan,
        "attempt_result": asdict(result),
        "retained_probe_sha256": artifact.evidence_sha256,
        "probe": artifact.view(),
    }
    document = json.loads(_canonical(document))
    opening = {**common, "schema": "rocell.rehearsal_camera_stage_open.v1"}
    settings = {
        **common,
        "schema": "rocell.rehearsal_camera_settings.v1",
        "settings": capture_doc["plan"]["settings"],
        "settings_epoch": capture_doc["plan"]["settings_epoch"],
    }
    evidence = {
        "opening": retained(opening, "opening", 10),
        "settings": retained(settings, "settings", 20),
        "probe": retained(document, "probe", 30),
    }
    configuration = None
    if configured:
        caps = artifact.capabilities()
        configuration = stage_camera_configuration(
            caps,
            caps.view()["modes"][0]["choice_id"],
            (CameraControlSetting("exposure", -5),) if controls is None else controls,
            expected_probe_evidence_sha256=artifact.evidence_sha256,
            expected_source_sha256=SOURCE,
            expected_selected_identity_sha256=admission.selected_identity_sha256,
        )
        config_doc = {
            **common,
            "schema": "rocell.rehearsal_camera_configuration_receipt.v1",
            "probe_evidence_sha256": artifact.evidence_sha256,
            "configuration": configuration.to_dict(),
            "electronic_settings_epoch": configuration.settings_epoch,
            "synthetic_settings_epoch": settings["settings_epoch"],
            "effective_settings_epoch": effective_camera_settings_epoch(
                settings["settings_epoch"], configuration
            ),
        }
        evidence["configuration"] = retained(config_doc, "configuration", 40)
    return document, records, evidence, artifact, configuration


def test_probe_exact_record_join_and_configuration_restoration(monkeypatch):
    doc, records, evidence, probe, config = probe_context(monkeypatch)
    verified = reopen._verify_camera_probe_receipt(
        doc, SOURCE, records, directory=STORE
    )
    assert verified.payload == probe.payload
    restored = reopen._verify_camera_configuration_context(
        evidence, records, SOURCE, doc["session_id"], directory=STORE
    )
    assert restored[0] == doc and restored[1].payload == probe.payload
    assert restored[2] == evidence["configuration"].document()
    assert restored[3].payload == config.payload


@pytest.mark.parametrize(
    "name",
    [
        "probe-request",
        "probe-result",
        "probe-evidence",
        "probe-observed",
        "probe-cleanup",
    ],
)
def test_missing_or_duplicate_record_never_reconstructs_known_probe(monkeypatch, name):
    doc, records, _, _, _ = probe_context(monkeypatch)
    missing = deepcopy(records)
    del missing[name]
    with pytest.raises(ValueError):
        reopen._verify_camera_probe_receipt(doc, SOURCE, missing)
    records["duplicate"] = deepcopy(records[name])
    with pytest.raises(ValueError):
        reopen._verify_camera_probe_receipt(doc, SOURCE, records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_duration_ms", 6000),
        ("frames_requested", 1),
        ("control_writes_requested", True),
        ("fault", "cleanup-uncertain"),
        ("process_timeout_ms", 25000),
    ],
)
def test_probe_plan_is_exact_not_just_hash_shaped(monkeypatch, field, value):
    doc, records, _, _, _ = probe_context(monkeypatch)
    doc["plan"][field] = value
    with pytest.raises(ValueError):
        reopen._verify_camera_probe_receipt(doc, SOURCE, records)


def test_probe_cwd_and_summary_are_bound_to_exact_original_attempt(monkeypatch):
    doc, records, _, _, _ = probe_context(monkeypatch)
    with pytest.raises(ValueError):
        reopen._verify_camera_probe_receipt(
            doc, SOURCE, records, directory=STORE / "wrong"
        )
    doc["probe"]["native"]["mode_count"] = 0
    with pytest.raises(ValueError):
        reopen._verify_camera_probe_receipt(doc, SOURCE, records)


@pytest.mark.parametrize(
    "field",
    [
        "probe_evidence_sha256",
        "electronic_settings_epoch",
        "synthetic_settings_epoch",
        "effective_settings_epoch",
        "operator_id",
        "session_id",
    ],
)
def test_configuration_dependencies_and_actor_are_exact(monkeypatch, field):
    doc, records, evidence, _, _ = probe_context(monkeypatch)
    raw = evidence["configuration"].document()
    raw[field] = "other" if field.endswith("_id") else "d" * 64
    evidence["configuration"] = retained(raw, "configuration", 40)
    with pytest.raises(ValueError):
        reopen._verify_camera_configuration_context(
            evidence, records, SOURCE, doc["session_id"]
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-probe",
        "duplicate-probe",
        "duplicate-config",
        "config-before-probe",
        "different-opening",
        "different-settings-operator",
    ],
)
def test_orphan_duplicate_and_reordered_auxiliaries_hold(monkeypatch, mutation):
    doc, records, evidence, _, _ = probe_context(monkeypatch)
    if mutation == "missing-probe":
        del evidence["probe"]
    elif mutation == "duplicate-probe":
        evidence["duplicate"] = evidence["probe"]
    elif mutation == "duplicate-config":
        evidence["duplicate"] = evidence["configuration"]
    elif mutation == "config-before-probe":
        evidence["configuration"] = replace(
            evidence["configuration"], captured_at_ns=29
        )
    else:
        key = "opening" if mutation == "different-opening" else "settings"
        raw = evidence[key].document()
        raw["operator_id"] = "other"
        evidence[key] = retained(raw, key, 10 if key == "opening" else 20)
    with pytest.raises(ValueError):
        reopen._verify_camera_configuration_context(
            evidence, records, SOURCE, doc["session_id"]
        )


@pytest.mark.parametrize("configured", [False, True])
def test_partial_probe_only_or_staged_state_reopens_without_replay(
    monkeypatch, configured
):
    doc, records, evidence, _, _ = probe_context(monkeypatch, configured=configured)
    stage = STAGE_ORDER[4]
    snapshot = SimpleNamespace(
        header=SimpleNamespace(
            session_id=doc["session_id"], cell_id=doc["cell_id"], header_sha256="e" * 64
        ),
        head=SimpleNamespace(head_sha256="f" * 64),
        next_action=SimpleNamespace(
            stage=stage, stage_state=V2StageState.WAITING_OPERATOR
        ),
        committed_events=(
            SimpleNamespace(
                stage=stage,
                state=V2StageState.WAITING_OPERATOR,
                evidence=(),
                detail_code="REHEARSAL_STAGE_OPENED",
                occurred_at_ns=1,
            ),
        ),
    )
    verification = SimpleNamespace(
        evidence_inventory_sha256="a" * 64, challenge_sha256="b" * 64
    )
    probe_dir = STORE / ("camera-probe-" + doc["attempt_result"]["attempt_id"])
    monkeypatch.setattr(reopen, "_read_evidence", lambda *args: evidence)
    monkeypatch.setattr(
        reopen.V2CommittedHead,
        "build",
        lambda *args: SimpleNamespace(head_sha256="c" * 64),
    )
    monkeypatch.setattr(
        reopen, "_entries", lambda path, maximum: [probe_dir] if path == STORE else []
    )
    monkeypatch.setattr(reopen, "safe_root", lambda path, **kwargs: path)
    restored = reopen._reconstruct(
        STORE, snapshot, verification, SOURCE, doc["catalog_sha256"], records
    )
    assert restored.disposition == "WAITING_NO_RECEIPT"
    assert restored.receipt is restored.latest_capture is None
    assert restored.operator_id == "operator-a"
    assert len(restored.stage_evidence) == (4 if configured else 3)
    # A separate capture reservation without a published stage receipt still
    # holds; allowing a completed auxiliary probe never authorizes replay.
    _, capture_records, _, _, _ = capture_scenario(monkeypatch)
    with pytest.raises(reopen.RehearsalReopenError) as caught:
        reopen._reconstruct(
            STORE,
            snapshot,
            verification,
            SOURCE,
            doc["catalog_sha256"],
            {**records, **capture_records},
        )
    assert caught.value.code == "CAMPAIGN_RECEIPT_MISSING"


def test_probe_bound_session_cannot_downgrade_to_legacy_capture(monkeypatch):
    doc, records, evidence, _, _ = probe_context(monkeypatch)
    camera_doc, camera_records, _, _, _ = capture_scenario(monkeypatch)
    with pytest.raises(reopen.RehearsalReopenError) as caught:
        reopen._verify_owned_camera_campaign(
            camera_doc, SOURCE, {**records, **camera_records}, evidence=evidence
        )
    assert caught.value.code == "CAMERA_CONFIGURATION_DOWNGRADE"


def test_no_auxiliary_state_returns_empty_context(monkeypatch):
    assert reopen._verify_camera_configuration_context(
        {}, {}, SOURCE, "rehearsal-none"
    ) == (None, None, None, None)


@pytest.mark.parametrize(
    "controls",
    [
        (),
        (
            CameraControlSetting("gain", 32),
            CameraControlSetting("exposure", -5, "auto"),
        ),
    ],
)
def test_complete_configured_capture_joins_probe_epoch_and_readback(
    monkeypatch, controls
):
    _, probe_records, evidence, probe, configuration = probe_context(
        monkeypatch, controls=controls
    )
    doc, capture_records, artifact, _, _ = capture_scenario(
        monkeypatch, configuration=configuration
    )
    evidence["camera"] = retained(doc, "camera", 50)
    records = {**probe_records, **capture_records}
    verified = reopen._verify_owned_camera_campaign(
        doc, SOURCE, records, evidence=evidence
    )
    assert verified.payload == artifact.payload
    assert verified.view()["status"] == "RETAINED_COMPLETE_REHEARSAL"
    assert (
        verified.to_dict()["binding"]["settings_epoch"]
        == doc["plan"]["effective_settings_epoch"]
    )
    assert doc["plan"]["probe_evidence_sha256"] == probe.evidence_sha256
    assert doc["plan"]["effective_settings_epoch"] != configuration.settings_epoch
    assert doc["plan"]["effective_settings_epoch"] != doc["plan"]["settings_epoch"]
    assert doc["camera_readback"]["physical_authority"] is False

    for altered in ("camera_readback", "effective_settings_epoch", "missing_context"):
        changed = deepcopy(doc)
        if altered == "camera_readback":
            changed["camera_readback"]["settings_epoch"] = "0" * 64
        elif altered == "effective_settings_epoch":
            changed["plan"]["effective_settings_epoch"] = changed["plan"][
                "settings_epoch"
            ]
        with pytest.raises(reopen.RehearsalReopenError):
            reopen._verify_owned_camera_campaign(
                changed,
                SOURCE,
                records,
                evidence=None if altered == "missing_context" else evidence,
            )
