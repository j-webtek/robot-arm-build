from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "software/tests/unit")]

import test_trajectory_execution_envelope_v2 as envelope_fixture  # noqa: E402
from rocell.application.controller_configuration_epoch_intake_v1 import (  # noqa: E402
    build_synthetic_controller_configuration_epoch_rehearsal_v1,
)
from rocell.application.r97_independent_review_decision_v1 import (  # noqa: E402
    build_synthetic_r97_review_rehearsal_v1,
)
from rocell.application.synthetic_epoch_model_arm_rehearsal_v1 import (  # noqa: E402
    SyntheticEpochModelArmRehearsalError,
    assess_synthetic_epoch_model_arm_rehearsal_v1,
)
from rocell.application.trajectory_execution_envelope_v2 import (  # noqa: E402
    bind_trajectory_execution_envelope_v2,
)
from rocell.application.zero_write_waveshare_adapter_v1 import (  # noqa: E402
    WaveshareT102EncodingProfileV1,
    ZeroWriteWaveshareAdapterV1,
    issue_zero_write_encoding_permit_v1,
    trajectory_limits_sha256,
)


def _lineage():
    decision, _review_report = build_synthetic_r97_review_rehearsal_v1(
        rehearsal_id="arm-036",
        review_started_utc="2026-09-26T13:00:00Z",
        review_completed_utc="2026-09-26T13:01:00Z",
    )
    epoch, epoch_report = (
        build_synthetic_controller_configuration_epoch_rehearsal_v1(
            rehearsal_id="arm-037", firmware_review_decision=decision,
            measured_monotonic_ns=100, valid_until_monotonic_ns=300,
            evaluated_monotonic_ns=200))
    batch, planner_report = envelope_fixture._planner_inputs()
    planner_report = envelope_fixture._synthetic_ready(planner_report)
    inner = replace(
        envelope_fixture._inner(
            batch.batch_sha256,
            planner_report["derived_v1_surrogate_sha256"],
            planner_report["measured_planner_gate_sha256"]),
        configuration_epoch_sha256=epoch.configuration_epoch_sha256,
    )
    envelope = bind_trajectory_execution_envelope_v2(
        batch, batch.proposals[0], planner_report, inner)
    profile = WaveshareT102EncodingProfileV1(
        profile_id="waveshare-t102-synthetic-epoch-preview-v1",
        vendor_source_sha256="1" * 64,
        controller_joint_mapping_sha256="2" * 64,
        expected_trajectory_limits_sha256=trajectory_limits_sha256(envelope),
        controller_session_id=inner.controller_session_id,
        configuration_epoch_sha256=epoch.configuration_epoch_sha256,
        fixed_gripper_rad=0.25, speed=20, acceleration=1,
    )
    permit = issue_zero_write_encoding_permit_v1(
        envelope, profile, issued_monotonic_ns=10,
        expires_monotonic_ns=2_000_000_000)
    receipt = ZeroWriteWaveshareAdapterV1().preview(
        envelope, permit, profile, now_monotonic_ns=100)
    return decision, epoch, epoch_report, batch, envelope, profile, receipt


def _assess(values):
    names = (
        "review_decision", "configuration_epoch",
        "configuration_epoch_report", "batch", "envelope",
        "encoding_profile", "preview_receipt",
    )
    return assess_synthetic_epoch_model_arm_rehearsal_v1(
        **dict(zip(names, values, strict=True)))


def test_exact_model_epoch_trajectory_and_preview_lineage_is_proven():
    values = _lineage()
    report = _assess(values)
    document = report.to_dict()

    assert document["status"] == "ZERO_WRITE_LINEAGE_PROVEN_PRODUCTION_BLOCKED"
    assert document["configuration_epoch_sha256"] == (
        values[1].configuration_epoch_sha256)
    assert document["batch_sha256"] == values[3].batch_sha256
    assert document["command_count"] == 1
    assert document["configuration_epoch_blockers"] == [
        "FIRMWARE_REVIEW_DECISION_BLOCKED",
        "COMPONENT_NOT_PHYSICAL_ORIGINAL",
    ]
    assert document["production_dispatch_allowed"] is False
    assert document["transport_opened"] is False
    assert document["transport_write_count"] == 0
    assert document["hardware_access"] is False
    assert document["physical_authority"] is False
    schema = json.loads((
        ROOT / "software/ai/schemas/synthetic_epoch_model_arm_rehearsal_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


def test_crossed_epoch_or_model_lineage_fails_closed():
    values = list(_lineage())
    inner = replace(
        values[4].measured_envelope,
        configuration_epoch_sha256="f" * 64,
    )
    values[4] = replace(values[4], measured_envelope=inner)
    with pytest.raises(SyntheticEpochModelArmRehearsalError, match="epoch"):
        _assess(values)


def test_crossed_preview_receipt_fails_closed():
    values = list(_lineage())
    values[6] = replace(values[6], encoding_profile_sha256="f" * 64)
    with pytest.raises(SyntheticEpochModelArmRehearsalError, match="receipt"):
        _assess(values)


def test_production_ready_epoch_is_not_accepted_as_synthetic_rehearsal():
    values = list(_lineage())
    values[2] = replace(values[2], blockers=())
    with pytest.raises(SyntheticEpochModelArmRehearsalError, match="fresh assessment"):
        _assess(values)
