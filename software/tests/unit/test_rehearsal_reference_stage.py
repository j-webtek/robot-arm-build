"""Actual nominal graph/FK/fit evidence, strict replay-free verification."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application import rehearsal_reference_stage as reference
from rocell.application.context import load_simulation_context
from rocell.application.static_phase1_calibration import (
    run_static_phase1_calibration_rehearsal,
)
from rocell.calibration.registry import CalibrationRegistry
from rocell.geometry import UrdfModel
from test_rehearsal_reference_binding import make_binding


WORKSPACE = Path(__file__).resolve().parents[3]


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


@pytest.fixture(scope="module")
def actual():
    binding = make_binding(reference.read_reference_source_context(WORKSPACE))
    evidence = reference.evaluate_rehearsal_reference_stage(WORKSPACE, binding)
    source_hash = hashlib.sha256(Path(reference.__file__).read_bytes()).hexdigest()
    return binding, evidence, source_hash


def verify(document, actual, *, binding=None):
    expected_binding, _, source_hash = actual
    payload = encoded(document)
    return reference.verify_rehearsal_reference_evidence(
        payload,
        expected_binding=binding or expected_binding,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        expected_evaluator_source_sha256=source_hash,
    )


def test_actual_complete_graph_numeric_evidence_and_nominal_truth(actual):
    binding, result, _ = actual
    report = result.to_dict()
    assert result.outcome == "REHEARSAL_CHECKS_PASSED"
    assert len(result.checks) == 9 and all(row["passed"] for row in result.checks)
    assert 100_000 < len(result.canonical_bytes()) <= 112 * 1024
    assert len(binding.source_context_json) < 16 * 1024
    context = load_simulation_context(
        WORKSPACE, WORKSPACE / "software/config/system_manifest.json"
    )
    assert (
        report["technical_reports"]["graph"]
        == run_static_phase1_calibration_rehearsal(context).to_dict()
    )
    graph = report["technical_reports"]["graph"]["synthetic_rehearsal"]
    assert len(graph["artifacts"]) == 15
    assert len(graph["staleness_probes"]) == 68
    assert all(row["state"] == "NOMINAL_ONLY" for row in graph["artifacts"])
    summary = report["reference_summary"]
    assert summary["numeric"]["training_points"] == 4
    assert summary["numeric"]["heldout_points"] == 2
    for key in ("training_rms_mm", "heldout_rms_mm", "max_roundtrip_error_mm"):
        assert 0 <= summary["numeric"][key] < 1e-7
    assert len(summary["physical_components_pending"]) == 8
    assert summary["target_coverage"] == {
        "keyboard": {"selected": ["A"], "catalog_total": 46},
        "phone": {"selected": ["key_q"], "catalog_total": 29},
    }
    assert summary["camera_role"] == "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT"
    assert (
        summary["controller_feedback_role"]
        == "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT"
    )
    assert not report["physical_authority"]
    assert all(value == 0 for value in report["actual_physical_effects"].values())


def test_shifted_heldout_fault_never_changes_training_fit_or_nominal_readiness(actual):
    _, result, _ = actual
    reports = result.to_dict()["technical_reports"]
    nominal, fault = reports["nominal_fit"], reports["heldout_fault_fit"]
    assert nominal["diagnostic_pass"] is True
    assert fault["diagnostic_pass"] is False
    assert nominal["candidate_transform"] == fault["candidate_transform"]
    assert nominal["input"]["training"] == fault["input"]["training"]
    assert nominal["input"]["held_out"] != fault["input"]["held_out"]
    assert set(fault["diagnostic_failures"]) == {
        "HELD_OUT_RMS_EXCEEDED",
        "HELD_OUT_MAXIMUM_EXCEEDED",
    }
    assert all(
        row["provenance"]["held_out_used_for_fit"] is False for row in (nominal, fault)
    )


def test_pure_verifier_has_no_files_fitter_fk_evaluator_or_registry_access(
    actual, monkeypatch
):
    binding, evidence, digest = actual

    def forbidden(*args, **kwargs):
        raise AssertionError("provider/evaluator/source replay is forbidden")

    monkeypatch.setattr(reference, "evaluate_rehearsal_reference_stage", forbidden)
    monkeypatch.setattr(reference, "read_reference_source_context", forbidden)
    monkeypatch.setattr(reference, "load_simulation_context", forbidden)
    monkeypatch.setattr(reference, "run_static_phase1_calibration_rehearsal", forbidden)
    monkeypatch.setattr(reference, "fit_rigid_correspondence", forbidden)
    monkeypatch.setattr(UrdfModel, "forward_kinematics", forbidden)
    monkeypatch.setattr(CalibrationRegistry, "assess", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    result = reference.verify_rehearsal_reference_evidence(
        evidence.canonical_bytes(),
        expected_binding=binding,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_evaluator_source_sha256=digest,
    )
    assert result.canonical_bytes() == evidence.canonical_bytes()


@pytest.mark.parametrize(
    "field",
    [
        "workspace_source_sha256",
        "catalog_sha256",
        "cell_id",
        "session_id",
        "operator_id",
        "camera_capture_receipt_sha256",
        "feedback_binding_sha256",
        "campaign_context_binding_sha256",
        "retained_campaign_sha256",
        "feedback_inner_evidence_sha256",
        "feedback_request_sha256",
        "controller_binding_sha256",
        "final_power_observation_sha256",
    ],
)
def test_exact_source_session_controller_and_predecessor_context_is_required(
    actual, field
):
    binding, evidence, _ = actual
    changed = (
        "another-identity"
        if field in {"cell_id", "session_id", "operator_id"}
        else "9" * 64
    )
    with pytest.raises(reference.RehearsalReferenceError):
        verify(evidence.to_dict(), actual, binding=replace(binding, **{field: changed}))


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize(
    "field",
    ["receipt_sha256", "assessment_sha256", "review_sha256", "evaluation_sha256"],
)
def test_each_reviewed_predecessor_digest_is_required(actual, index, field):
    binding, evidence, _ = actual
    predecessors = list(binding.predecessors)
    predecessors[index] = replace(predecessors[index], **{field: "9" * 64})
    with pytest.raises(reference.RehearsalReferenceError):
        verify(
            evidence.to_dict(),
            actual,
            binding=replace(binding, predecessors=tuple(predecessors)),
        )


@pytest.mark.parametrize(
    "path",
    [
        ("physical_authority",),
        ("binding", "physical_authority"),
        ("technical_reports", "graph", "hardware_accessed"),
        (
            "technical_reports",
            "graph",
            "synthetic_rehearsal",
            "artifacts",
            0,
            "physical_evidence",
        ),
        ("technical_reports", "frame_chain", "physical_measurements_present"),
        ("technical_reports", "nominal_fit", "provenance", "physical_authority"),
    ],
)
def test_synthetic_as_physical_claims_reject_even_with_fresh_outer_hash(actual, path):
    document = actual[1].to_dict()
    selected = document
    for key in path[:-1]:
        selected = selected[key]
    selected[path[-1]] = True
    with pytest.raises(reference.RehearsalReferenceError):
        verify(document, actual)


@pytest.mark.parametrize(
    "case",
    [
        "matrix",
        "fk_joint",
        "fk_point",
        "fk_residual",
        "target_residual",
        "fit_residual",
        "fit_training_point",
        "fit_heldout_point",
        "fit_certificate",
        "fit_split_leakage",
        "missing_edge",
        "duplicate_edge",
        "wrong_edge",
        "nominal_promoted",
        "missing_source",
        "extra_field",
        "bool_count",
        "negative_check",
        "pending_removed",
        "coverage_expanded",
    ],
)
def test_numerical_graph_or_schema_tampering_cannot_be_rehashed_into_success(
    actual, case
):
    report = actual[1].to_dict()
    technical = report["technical_reports"]
    frame = technical["frame_chain"]
    fit = technical["nominal_fit"]
    graph = technical["graph"]["synthetic_rehearsal"]
    if case == "matrix":
        frame["rows"][0]["world_T_hand"]["matrix_mm"][3] += 2
    elif case == "fk_joint":
        frame["rows"][0]["joint_positions_rad"][0] += 0.1
    elif case == "fk_point":
        frame["rows"][0]["world_tip"]["xyz_mm"][0] += 2
    elif case == "fk_residual":
        frame["rows"][0]["roundtrip_error_mm"] += 2
    elif case == "target_residual":
        frame["target_roundtrips"][0]["roundtrip_error_mm"] += 2
    elif case == "fit_residual":
        fit["residuals"][0]["residual_mm"] += 2
    elif case == "fit_training_point":
        fit["input"]["training"][0]["target"]["xyz_mm"][0] += 2
    elif case == "fit_heldout_point":
        fit["input"]["held_out"][0]["target"]["xyz_mm"][0] += 2
    elif case == "fit_certificate":
        fit["spectral_certificate"]["cross_singular_values_mm2"][0] += 50
    elif case == "fit_split_leakage":
        fit["input"]["held_out"][0] = fit["input"]["training"][0]
    elif case == "missing_edge":
        graph["staleness_probes"].pop()
    elif case == "duplicate_edge":
        graph["staleness_probes"][1] = graph["staleness_probes"][0]
    elif case == "wrong_edge":
        graph["staleness_probes"][0]["upstream_id"] = "another"
    elif case == "nominal_promoted":
        graph["artifacts"][0]["state"] = "VALID"
    elif case == "missing_source":
        report["dependency_source_sha256s"].pop(
            next(iter(report["dependency_source_sha256s"]))
        )
    elif case == "extra_field":
        frame["rows"][0]["physical_pass"] = True
    elif case == "bool_count":
        report["reference_summary"]["numeric"]["training_points"] = True
    elif case == "negative_check":
        report["checks"][4]["passed"] = False
    elif case == "pending_removed":
        report["reference_summary"]["physical_components_pending"].pop()
    elif case == "coverage_expanded":
        report["reference_summary"]["target_coverage"]["keyboard"]["selected"].append(
            "B"
        )
    # Recompute subordinate hashes where present, then the entire trusted-hash
    # argument. Algebra and exact input binding must still reject the mutation.
    fit["input_sha256"] = hashlib.sha256(encoded(fit["input"])).hexdigest()
    graph["closure_hash"] = hashlib.sha256(
        encoded({k: v for k, v in graph.items() if k != "closure_hash"})
    ).hexdigest()
    with pytest.raises(reference.RehearsalReferenceError):
        verify(report, actual)


def test_a_failed_expected_refusal_remains_blocked_not_nominal_success(actual):
    document = actual[1].to_dict()
    row = document["technical_reports"]["refusal_faults"]["wrong_joint_units"]
    row.update(disposition="ACCEPTED", error_type=None, error_message=None)
    # A coherent retained implementation regression is inspectable as BLOCKED.
    checks, summary = reference._derive(document, actual[0])
    document.update(checks=checks, reference_summary=summary, outcome="BLOCKED")
    result = verify(document, actual)
    assert result.outcome == "BLOCKED"
    assert all(row["passed"] for row in result.checks if row["check_kind"] == "NOMINAL")
    assert not next(
        row for row in result.checks if row["check_id"] == "wrong_joint_units"
    )["passed"]


def test_edge_fault_failure_does_not_relabel_the_nominal_artifact_baseline(actual):
    document = actual[1].to_dict()
    graph = document["technical_reports"]["graph"]
    synthetic = graph["synthetic_rehearsal"]
    synthetic["staleness_probes"][0].update(observed_stale_reasons=[], detected=False)
    synthetic.update(
        all_edges_exercised=False,
        simulation_graph_verified=False,
        status="SYNTHETIC_GRAPH_REHEARSAL_FAILED",
    )
    synthetic["closure_hash"] = hashlib.sha256(
        encoded(
            {key: value for key, value in synthetic.items() if key != "closure_hash"}
        )
    ).hexdigest()
    graph["status"] = "SYNTHETIC_PHASE1_GRAPH_REHEARSAL_FAILED"
    checks, summary = reference._derive(document, actual[0])
    document.update(checks=checks, reference_summary=summary, outcome="BLOCKED")
    result = verify(document, actual)
    assert result.outcome == "BLOCKED"
    assert (
        next(
            row for row in result.checks if row["check_id"] == "nominal_graph_baseline"
        )["passed"]
        is True
    )
    assert (
        next(row for row in result.checks if row["check_id"] == "dependency_staleness")[
            "passed"
        ]
        is False
    )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{}",
        b"null",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b" " * (112 * 1024 + 1),
        "not-bytes",
        None,
    ],
    ids=[
        "empty",
        "empty-object",
        "null",
        "duplicate",
        "nan",
        "infinity",
        "oversize",
        "text",
        "none",
    ],
)
def test_malformed_or_oversized_payloads_reject(actual, payload):
    binding, _, source_hash = actual
    with pytest.raises(reference.RehearsalReferenceError):
        reference.verify_rehearsal_reference_evidence(
            payload,
            expected_binding=binding,
            expected_evidence_sha256="9" * 64,
            expected_evaluator_source_sha256=source_hash,
        )


def test_expected_hashes_required_and_not_self_authored(actual):
    binding, evidence, source_hash = actual
    for evidence_hash, evaluator_hash in (
        ("9" * 64, source_hash),
        (evidence.evidence_sha256, "9" * 64),
    ):
        with pytest.raises(reference.RehearsalReferenceError):
            reference.verify_rehearsal_reference_evidence(
                evidence.canonical_bytes(),
                expected_binding=binding,
                expected_evidence_sha256=evidence_hash,
                expected_evaluator_source_sha256=evaluator_hash,
            )
    with pytest.raises(TypeError):
        reference.verify_rehearsal_reference_evidence(
            evidence.canonical_bytes(), expected_binding=binding
        )


def test_new_source_context_must_equal_fresh_locked_sources_before_evaluation(actual):
    binding, _, _ = actual
    changed = binding.source_context
    changed["nominal_geometry"]["board_T_world"]["matrix_mm"][3] += 5
    changed_binding = replace(binding, source_context_json=encoded(changed))
    with pytest.raises(
        reference.RehearsalReferenceError, match="fresh reference source"
    ):
        reference.evaluate_rehearsal_reference_stage(WORKSPACE, changed_binding)


def test_evidence_is_bounded_immutable_and_detached(actual):
    _, evidence, _ = actual
    original = evidence.canonical_bytes()
    evidence.to_dict()["technical_reports"]["frame_chain"]["rows"].clear()
    assert evidence.canonical_bytes() == original
    with pytest.raises(FrozenInstanceError):
        evidence._payload = b"{}"
    with pytest.raises(reference.RehearsalReferenceError):
        reference.RehearsalReferenceEvidence(b" " * (112 * 1024 + 1))
