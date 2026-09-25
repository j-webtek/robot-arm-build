from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import rehearsal_optics_stages as optics


WORKSPACE = Path(__file__).resolve().parents[3]


def binding(stage: str = "optics_intrinsics") -> optics.RehearsalOpticsBinding:
    return optics.RehearsalOpticsBinding(
        "a" * 64,
        "b" * 64,
        "cell-fixture",
        "session-fixture",
        "operator-fixture",
        stage,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
        "1" * 64,
    )


def encoded(document: dict[str, Any]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def verify(
    document: dict[str, Any], stage: str = "static_registration"
) -> optics.RehearsalOpticsEvidence:
    return optics.verify_rehearsal_optics_evidence(
        encoded(document), expected_binding=binding(stage)
    )


@pytest.fixture(scope="module")
def retained() -> dict[str, optics.RehearsalOpticsEvidence]:
    # These are actual existing parsers and JPEG pixel probes, never a provider.
    return {
        stage: optics.evaluate_rehearsal_optics_stage(WORKSPACE, binding(stage))
        for stage in ("optics_intrinsics", "static_registration")
    }


@pytest.mark.parametrize("stage", ["optics_intrinsics", "static_registration"])
def test_actual_evaluation_and_strict_retained_round_trip(retained, stage):
    report = retained[stage]
    document = report.to_dict()
    assert report.outcome == "REHEARSAL_CHECKS_PASSED"
    assert 10_000 < len(report.canonical_bytes()) < optics.MAX_EVIDENCE_BYTES
    assert all(item["passed"] is True for item in report.checks)
    assert document["authority"]["physical_authority"] is False
    assert document["authority"]["stage_advance_authority"] is False
    assert (
        document["provenance"]["camera_dataset_role"]
        == "DEPENDENCY_ONLY_NOT_EVALUATED_PIXELS"
    )
    assert (
        optics.verify_rehearsal_optics_evidence(
            report.canonical_bytes(),
            expected_binding=binding(stage),
            expected_evidence_sha256=report.evidence_sha256,
            expected_evaluator_source_sha256=document["evaluator"][
                "source_file_sha256"
            ],
        ).canonical_bytes()
        == report.canonical_bytes()
    )


def test_reports_retain_substantive_actual_data(retained):
    intrinsic = retained["optics_intrinsics"].to_dict()["reports"]["intrinsics"]
    assert intrinsic["assessment"]["training_view_count"] == 24
    assert intrinsic["assessment"]["held_out_view_count"] == 8
    assert (
        hashlib.sha256(intrinsic["fixture_utf8"].encode()).hexdigest()
        == intrinsic["fixture_sha256"]
    )
    vision = retained["static_registration"].to_dict()["reports"]
    normal, loss = vision["normal"], vision["tag_loss"]
    assert normal["tag_ids"]["planar_pose_inliers"] == [0, 1, 2, 3]
    assert [
        row["tag_id"]
        for row in normal["board_registration"]["held_out_station_residuals"]
    ] == [4, 5]
    assert loss["status"] == "REJECTED"
    assert loss["pose_comparison"]["estimate_available"] is False
    assert (
        normal["pixel_statistics"]["jpeg_sha256"]
        != loss["pixel_statistics"]["jpeg_sha256"]
    )


def test_verify_never_reruns_probes_reads_files_or_calls_assessor(
    retained, monkeypatch
):
    import rocell.application.b0477_static_vision as vision
    import rocell.calibration.static_camera_intrinsics as intrinsics

    def forbidden(*args, **kwargs):
        raise AssertionError("retained verification attempted external work")

    monkeypatch.setattr(vision, "run_b0477_static_vision_rehearsal", forbidden)
    monkeypatch.setattr(vision, "run_b0477_static_vision_capture_rehearsal", forbidden)
    monkeypatch.setattr(
        intrinsics, "assess_static_camera_intrinsics_rehearsal", forbidden
    )
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    for stage, report in retained.items():
        assert (
            optics.verify_rehearsal_optics_evidence(
                report.canonical_bytes(),
                expected_binding=binding(stage),
            ).outcome
            == "REHEARSAL_CHECKS_PASSED"
        )


def test_regressed_nominal_evaluator_cannot_pass_despite_negative_success(
    retained, monkeypatch
):
    import rocell.application.b0477_static_vision as vision

    reports = retained["static_registration"].to_dict()["reports"]
    normal = optics._vision_report(reports["normal"])
    loss = optics._vision_report(reports["tag_loss"])
    regressed = replace(
        normal,
        pose_comparison=replace(normal.pose_comparison, translation_error_mm=2.0),
        status="REJECTED",
        detail_code="B0477_STATIC_PIXEL_POSE_QUALITY_REJECTED",
    )
    calls = []

    def evaluator(root, *, sequence, mode):
        calls.append(mode)
        return regressed if mode is vision.B0477StaticVisionMode.NORMAL else loss

    monkeypatch.setattr(vision, "run_b0477_static_vision_rehearsal", evaluator)
    result = optics.evaluate_rehearsal_optics_stage(
        WORKSPACE, binding("static_registration")
    )
    assert len(calls) == 2
    assert result.outcome == "BLOCKED"
    checks = {row["check_id"]: row["passed"] for row in result.checks}
    assert checks["nominal_pose_policy"] is False
    assert checks["tag_loss_rejected"] is True
    assert verify(result.to_dict()).outcome == "BLOCKED"


def test_negative_rejected_label_with_available_pose_does_not_pass(
    retained, monkeypatch
):
    import rocell.application.b0477_static_vision as vision

    reports = retained["static_registration"].to_dict()["reports"]
    normal = optics._vision_report(reports["normal"])
    loss = optics._vision_report(reports["tag_loss"])
    regressed_loss = replace(
        loss,
        pose_comparison=normal.pose_comparison,
        held_out_station_residuals=normal.held_out_station_residuals,
        source_hashes=tuple(
            sorted(
                {
                    **dict(loss.source_hashes),
                    "pose_observation": dict(normal.source_hashes)["pose_observation"],
                }.items()
            )
        ),
        detail_code="B0477_STATIC_TAG_LOSS_INJECTION_NOT_REJECTED",
    )
    monkeypatch.setattr(
        vision,
        "run_b0477_static_vision_rehearsal",
        lambda root, *, sequence, mode: (
            normal if mode is vision.B0477StaticVisionMode.NORMAL else regressed_loss
        ),
    )
    result = optics.evaluate_rehearsal_optics_stage(
        WORKSPACE, binding("static_registration")
    )
    assert result.outcome == "BLOCKED"
    assert {c["check_id"]: c["passed"] for c in result.checks}[
        "tag_loss_rejected"
    ] is False


def test_assessor_reported_failure_is_not_replaced_with_parser_success(
    retained, monkeypatch
):
    import rocell.calibration.static_camera_intrinsics as intrinsics

    assessment = retained["optics_intrinsics"].to_dict()["reports"]["intrinsics"][
        "assessment"
    ]
    assessment["structural_gates_passed"] = False
    monkeypatch.setattr(
        intrinsics,
        "assess_static_camera_intrinsics_rehearsal",
        lambda *a, **k: SimpleNamespace(to_dict=lambda: deepcopy(assessment)),
    )
    result = optics.evaluate_rehearsal_optics_stage(WORKSPACE, binding())
    assert result.outcome == "BLOCKED"
    assert verify(result.to_dict(), "optics_intrinsics").outcome == "BLOCKED"


@pytest.mark.parametrize("field", list(binding().to_dict()))
def test_exact_expected_binding_fields_are_required(retained, field):
    document = retained["optics_intrinsics"].to_dict()
    document["binding"][field] = "changed"
    with pytest.raises(optics.RehearsalOpticsError):
        verify(document, "optics_intrinsics")


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("authority",),
        ("evaluator",),
        ("provenance",),
        ("reports",),
        ("reports", "normal"),
        ("reports", "normal", "camera"),
        ("reports", "normal", "source_hashes"),
        ("reports", "normal", "nominal_projection"),
        ("reports", "normal", "board_registration"),
        ("reports", "normal", "pose_comparison"),
    ],
)
def test_unknown_fields_rejected_even_when_outer_hashes_are_refreshed(retained, path):
    document = retained["static_registration"].to_dict()
    target = document
    for key in path:
        target = target[key]
    target["unexpected"] = False
    document["report_hashes"] = {
        k: optics._hash(v) for k, v in document["reports"].items()
    }
    with pytest.raises(optics.RehearsalOpticsError):
        verify(document)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.update(outcome="PASS"),
        lambda d: d["checks"][0].update(passed=False),
        lambda d: d["report_hashes"].update(normal="0" * 64),
        lambda d: d.update(selected_inputs_sha256="0" * 64),
        lambda d: d["selected_inputs"].update(normal_jpeg_sha256="0" * 64),
        lambda d: d["authority"].update(physical_authority=True),
        lambda d: d["authority"].update(hardware_accessed=0),
        lambda d: d["provenance"].update(camera_dataset_role="EVALUATED_PIXELS"),
        lambda d: d["reports"]["normal"]["pose_comparison"].update(
            translation_error_mm=99.0
        ),
        lambda d: d["reports"]["normal"]["pose_comparison"].update(
            estimate_available=1
        ),
        lambda d: d["reports"]["normal"]["nominal_projection"].update(
            derivation_state="MEASURED"
        ),
        lambda d: d.update(sequence=True),
        lambda d: d.update(sequence=1),
    ],
)
def test_tampered_values_and_derived_claims_rejected(retained, mutator):
    document = retained["static_registration"].to_dict()
    mutator(document)
    with pytest.raises(optics.RehearsalOpticsError):
        verify(document)


def test_normal_and_negative_reports_cannot_be_swapped(retained):
    document = retained["static_registration"].to_dict()
    document["reports"]["normal"], document["reports"]["tag_loss"] = (
        document["reports"]["tag_loss"],
        document["reports"]["normal"],
    )
    document["report_hashes"] = {
        k: optics._hash(v) for k, v in document["reports"].items()
    }
    with pytest.raises(optics.RehearsalOpticsError, match="roles"):
        verify(document)


def test_intrinsics_fixture_tamper_rejected_even_with_new_byte_hash(retained):
    document = retained["optics_intrinsics"].to_dict()
    report = document["reports"]["intrinsics"]
    fixture = json.loads(report["fixture_utf8"])
    fixture["artifact_id"] = "tampered"
    report["fixture_utf8"] = json.dumps(fixture)
    report["fixture_sha256"] = hashlib.sha256(
        report["fixture_utf8"].encode()
    ).hexdigest()
    document["report_hashes"]["intrinsics"] = optics._hash(report)
    with pytest.raises(optics.RehearsalOpticsError):
        verify(document, "optics_intrinsics")


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]",
        b"\xff",
        b'{"schema":1,"schema":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b"[" * 1000 + b"]" * 1000,
        b" " * (optics.MAX_EVIDENCE_BYTES + 1),
    ],
    ids=[
        "empty",
        "array",
        "invalid-utf8",
        "duplicate",
        "nan",
        "infinity",
        "deep",
        "oversize",
    ],
)
def test_invalid_bounded_json_fails(payload):
    with pytest.raises(optics.RehearsalOpticsError):
        optics.verify_rehearsal_optics_evidence(payload, expected_binding=binding())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_evidence_sha256": "0" * 64},
        {"expected_evaluator_source_sha256": "0" * 64},
    ],
)
def test_independent_retained_hashes_reject_substitution(retained, kwargs):
    with pytest.raises(optics.RehearsalOpticsError):
        optics.verify_rehearsal_optics_evidence(
            retained["optics_intrinsics"].canonical_bytes(),
            expected_binding=binding(),
            **kwargs,
        )


def test_returned_documents_do_not_mutate_retained_bytes(retained):
    result = retained["static_registration"]
    original = result.evidence_sha256
    result.to_dict()["checks"].clear()
    result.checks[0]["passed"] = False
    assert result.evidence_sha256 == original
    assert result.checks[0]["passed"] is True


@pytest.mark.parametrize(
    "stage,sequence",
    [
        ("optics_intrinsics", 1),
        ("static_registration", True),
        ("static_registration", -1),
        ("static_registration", optics.MAX_SEQUENCE + 1),
    ],
)
def test_sequence_rejected_before_any_evaluation(stage, sequence, monkeypatch):
    monkeypatch.setattr(
        Path, "read_bytes", lambda *a: pytest.fail("source read before input rejection")
    )
    with pytest.raises(optics.RehearsalOpticsError):
        optics.evaluate_rehearsal_optics_stage(
            WORKSPACE, binding(stage), sequence=sequence
        )


def test_no_hardware_or_provider_override_parameter():
    for keyword in ("allow_hardware", "provider", "camera_path", "destination"):
        with pytest.raises(TypeError):
            optics.evaluate_rehearsal_optics_stage(
                WORKSPACE, binding(), **{keyword: True}
            )


def test_exact_binding_types_and_fields():
    for changes in (
        {"settings_epoch": True},
        {"stage": "arm_identity"},
        {"operator_id": " x"},
    ):
        with pytest.raises(optics.RehearsalOpticsError):
            replace(binding(), **changes)
    with pytest.raises(optics.RehearsalOpticsError):
        optics.verify_rehearsal_optics_evidence(b"{}", expected_binding={})
