"""Stage-13 read-only views plus a closed, no-device producer integration check."""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import pytest

from test_arrival_wizard_arm_power_ui import report, terminal
from test_arrival_wizard_reopen_ui import browser, commissioning


PENDING = [
    "bootstrap_phase_receipt",
    "reference_characterization_phase_receipt",
    "arm_to_board_transform",
    "controller_model_correlation",
    "free_state_tool_tcp",
    "keyboard_target_map",
    "phone_target_map",
    "outcome_observer_candidates",
]

WORKSPACE = Path(__file__).resolve().parents[3]


def reference_summary():
    return {
        "schema": "rocell.rehearsal_reference_summary.v1",
        "graph": {
            "nominal_artifacts": 15,
            "parent_edges": 27,
            "context_edges": 41,
            "detected_edges": 68,
        },
        "numeric": {
            "training_points": 4,
            "heldout_points": 2,
            "training_rms_mm": 0.0001,
            "heldout_rms_mm": 0.0002,
            "max_roundtrip_error_mm": 1e-12,
        },
        "target_coverage": {
            "keyboard": {"selected": ["A"], "catalog_total": 46},
            "phone": {"selected": ["key_q"], "catalog_total": 29},
        },
        "claim": "TWO_TARGET_COORDINATE_ROUNDTRIPS_NOT_REACHABILITY_OR_COMPLETE_COVERAGE",
        "physical_components_pending": list(PENDING),
        "camera_role": "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT",
        "controller_feedback_role": "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT",
    }


def projection():
    result = commissioning()
    value = report("reference_frame_calibration")
    value["outcome"] = "REHEARSAL_CHECKS_PASSED"
    value["checks"][0]["passed"] = True
    value["meaning"] = (
        "Nominal reference math and refusal checks; no installed calibration."
    )
    value["reference_summary"] = reference_summary()
    result["reference_evaluation"] = value
    return result


def render(value):
    page = browser(value)
    console = terminal(value)
    assert page["status"] == "Local service connected"
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["controls"] == browser(commissioning())["controls"]
    return page["text"], console


def assert_holds(page, console):
    for output in (page, console):
        assert "Eight physical reference components remain pending" in output
        assert "physical bootstrap/reference receipt importer" in output
        assert (
            "Camera stages 6, 7 and 8 are DEPENDENCY_ONLY_NOT_NUMERIC_INPUT" in output
        )
        assert "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT" in output
        assert "does not turn T105 fields into calibrated joints" in output
        assert "Noncontact acceptance requires its own exact assessment" in output
        assert "No bootstrap importer or physical calibration control" in output
    for component in PENDING:
        assert component.replace("_", " ") in page.lower()
        assert component in console
    # The terminal helper shows startup and one explicit view. Each rendering,
    # not the concatenated transcript, must list exactly eight physical holds.
    sections = console.split("\nEight physical reference components remain pending\n")
    assert len(sections) == 3
    for section in sections[1:]:
        assert (
            section.split("Camera stages 6, 7 and 8", 1)[0].count(
                '"physical_status": "PENDING"'
            )
            == 8
        )


def test_nominal_graph_fit_and_limited_target_coverage_do_not_qualify_hardware():
    page, console = render(projection())
    assert_holds(page, console)
    for output in (page, console):
        assert "Reference summary is missing" not in output
        assert "Nominal graph and injected-staleness coverage" in output
        assert "Synthetic point fit and coordinate roundtrips" in output
        assert "Explicit target subset" in output
        assert "not all 75 keyboard/phone targets" in output
        assert "no IK reachability" in output
        assert "not measured calibration quality" in output
        assert "Small errors do not measure installed geometry" in output
        assert "NEVER_RENDER_RAW_PROTOCOL_LOG" not in output
        assert "a" * 64 in output and "b" * 64 in output
    assert "NOMINAL CHECK PASSED REHEARSAL" in page
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" in console


def test_expected_fault_success_cannot_replace_regressed_nominal_reference_math():
    value = projection()
    reference = value["reference_evaluation"]
    reference["outcome"] = "BLOCKED"
    reference["checks"][0]["passed"] = False
    reference["reference_summary"]["graph"]["detected_edges"] = 67
    page, console = render(value)
    assert_holds(page, console)
    for output in (page, console):
        assert "BLOCKED" in output
        assert "cannot replace passing nominal checks" in output
    assert "EXPECTED FAULT CHECK PASSED REHEARSAL" in page
    assert "EXPECTED_FAULT_CHECK_PASSED_REHEARSAL" in console
    assert "NOMINAL CHECK PASSED REHEARSAL" not in page
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" not in console


@pytest.mark.parametrize(
    "mutation",
    [
        {"stage": "reference_calibration"},
        {"outcome": "PASS"},
        {"physical_authority": True},
        {"evaluation_sha256": None},
        {"selected_inputs_sha256": "unbound"},
        {"checks": [None] * 17},
    ],
)
def test_invalid_outer_projection_never_promotes_a_reference_check(mutation):
    data = projection()
    data["reference_evaluation"].update(mutation)
    page, console = render(data)
    assert_holds(page, console)
    assert "NOT VERIFIED" in page and "NOT_VERIFIED" in console
    assert "CHECK PASSED REHEARSAL" not in page
    assert "CHECK_PASSED_REHEARSAL" not in console


@pytest.mark.parametrize(
    "metric", ["training_rms_mm", "heldout_rms_mm", "max_roundtrip_error_mm"]
)
def test_unavailable_numeric_metric_is_not_replaced_with_zero(metric):
    value = projection()
    value["reference_evaluation"]["reference_summary"]["numeric"][metric] = None
    page, console = render(value)
    assert "Reference summary is missing" not in page
    assert "Reference summary is missing" not in console
    assert "NOT AVAILABLE" in page and "NOT_AVAILABLE" in console
    assert_holds(page, console)


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "wrong"),
        (("camera_role",), "MEASURED_INPUT"),
        (("controller_feedback_role",), "CALIBRATED_JOINTS"),
        (("claim",), "ALL_TARGETS_REACHABLE"),
        (("graph", "nominal_artifacts"), 16),
        (("graph", "detected_edges"), 69),
        (("graph", "detected_edges"), True),
        (("graph", "parent_edges"), -1),
        (("numeric", "training_points"), 3),
        (("numeric", "heldout_points"), "2"),
        (("numeric", "heldout_rms_mm"), -1.0),
        (("numeric", "training_rms_mm"), True),
        (("numeric", "max_roundtrip_error_mm"), 2**63),
        (("target_coverage", "phone", "selected"), []),
        (("target_coverage", "phone", "selected"), ["key_q", "key_w"]),
        (("target_coverage", "keyboard", "selected"), ["A\x1b[2J"]),
        (("target_coverage", "keyboard", "catalog_total"), 1),
        (("target_coverage", "phone", "catalog_total"), 30),
        (("physical_components_pending",), PENDING[:-1]),
        (("physical_components_pending",), [*PENDING[:-1], PENDING[0]]),
        (("physical_components_pending",), [*PENDING[:-1], {"status": "PASS"}]),
    ],
)
def test_invalid_reference_summary_keeps_pending_components_and_refuses_numeric_claims(
    path, value
):
    data = projection()
    selected = data["reference_evaluation"]["reference_summary"]
    for part in path[:-1]:
        selected = selected[part]
    selected[path[-1]] = deepcopy(value)
    page, console = render(data)
    assert_holds(page, console)
    for output in (page, console):
        assert (
            "Reference summary is missing, inconsistent or exceeds display bounds"
            in output
        )
        assert (
            "No zero residual, complete coverage or installed calibration is inferred"
            in output
        )
        assert "Synthetic point fit and coordinate roundtrips" not in output
        assert "Explicit target subset" not in output


@pytest.mark.parametrize("value", [None, False, [], "invalid", {}])
def test_missing_or_minimal_projection_is_inert_and_never_invents_results(value):
    data = commissioning()
    data["reference_evaluation"] = value
    page, console = render(data)
    if value is None:
        assert "Retained synthetic reference-frame checks" not in page
        assert "Retained synthetic reference-frame checks" not in console
    else:
        assert_holds(page, console)
        assert "NOT VERIFIED" in page and "NOT_VERIFIED" in console
        assert "Synthetic point fit and coordinate roundtrips" not in page


def test_full_technical_reports_are_not_expanded_by_generic_facts_or_summary():
    data = projection()
    data["reference_evaluation"]["technical_reports"] = {
        "full_graph_and_numeric_report": "NEVER_RENDER_FULL_REFERENCE_REPORT" * 3000
    }
    page, console = render(data)
    assert "NEVER_RENDER_FULL_REFERENCE_REPORT" not in page
    assert "NEVER_RENDER_FULL_REFERENCE_REPORT" not in console
    assert_holds(page, console)


def test_unknown_summary_fields_are_not_silently_truncated_or_displayed():
    data = projection()
    data["reference_evaluation"]["reference_summary"][
        "arbitrary_command"
    ] = "NEVER_RENDER_COMMAND"
    page, console = render(data)
    assert "Reference summary is missing, inconsistent" in page
    assert "Reference summary is missing, inconsistent" in console
    assert "NEVER_RENDER_COMMAND" not in page and "NEVER_RENDER_COMMAND" not in console
    assert_holds(page, console)


@pytest.fixture(scope="module")
def actual_reference_evidence():
    """Run the real closed fixture once, not a constructed passing summary.

    The binding's predecessor hashes are test-only inputs, not authenticated M1
    history. This proves producer/presentation compatibility, not durability,
    source-domain qualification or permission to advance a physical stage.
    """
    from rocell.application import rehearsal_reference_stage as reference
    from test_rehearsal_reference_binding import make_binding

    binding = make_binding(reference.read_reference_source_context(WORKSPACE))
    evidence = reference.evaluate_rehearsal_reference_stage(WORKSPACE, binding)
    source_digest = hashlib.sha256(Path(reference.__file__).read_bytes()).hexdigest()
    assert evidence.outcome == "REHEARSAL_CHECKS_PASSED"
    assert evidence.to_dict()["evaluator_source_sha256"] == source_digest
    return binding, evidence, source_digest


def actual_projection(evidence):
    from rocell.application.commissioning_rehearsal_service import (
        CommissioningRehearsalService,
    )

    # Mimic exact retained JSON readback before applying the real service
    # projection. No full technical report is sent to either cached view.
    receipt = json.loads(
        json.dumps(
            {
                "stage": "reference_frame_calibration",
                "evaluation": evidence.to_dict(),
                "evaluation_sha256": evidence.evidence_sha256,
            },
            allow_nan=False,
        )
    )
    return receipt, CommissioningRehearsalService._reference_projection(receipt)


def test_actual_producer_service_projection_and_both_views_preserve_typed_summary(
    actual_reference_evidence,
):
    binding, evidence, _ = actual_reference_evidence
    receipt, compact = actual_projection(evidence)
    full = evidence.to_dict()
    assert "technical_reports" in full and "technical_reports" not in compact
    assert set(compact) == {
        "stage",
        "outcome",
        "checks",
        "provenance",
        "evaluation_sha256",
        "selected_inputs_sha256",
        "reference_summary",
        "physical_authority",
        "meaning",
    }
    assert len(json.dumps(compact).encode()) < 32 * 1024
    assert compact["checks"] == full["checks"]
    assert compact["provenance"] == full["provenance"]
    assert compact["physical_authority"] is False
    assert compact["selected_inputs_sha256"] == binding.binding_sha256
    assert compact["evaluation_sha256"] == evidence.evidence_sha256
    assert 1 <= len(compact["checks"]) <= 12
    assert {row["check_kind"] for row in compact["checks"]} == {
        "NOMINAL",
        "EXPECTED_FAULT",
        "INVARIANT",
    }

    summary = compact["reference_summary"]
    assert summary["graph"] == {
        "nominal_artifacts": 15,
        "parent_edges": 27,
        "context_edges": 41,
        "detected_edges": 68,
    }
    assert summary["physical_components_pending"] == PENDING
    assert summary["target_coverage"] == {
        "keyboard": {"selected": ["A"], "catalog_total": 46},
        "phone": {"selected": ["key_q"], "catalog_total": 29},
    }
    assert summary["camera_role"] == "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT"
    assert (
        summary["controller_feedback_role"]
        == "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT"
    )
    numeric = summary["numeric"]
    assert type(numeric["training_points"]) is int and numeric["training_points"] == 4
    assert type(numeric["heldout_points"]) is int and numeric["heldout_points"] == 2
    for metric in ("training_rms_mm", "heldout_rms_mm", "max_roundtrip_error_mm"):
        assert type(numeric[metric]) in (int, float)
        assert math.isfinite(numeric[metric]) and numeric[metric] >= 0

    data = commissioning()
    data["reference_evaluation"] = compact
    page, console = render(data)
    assert_holds(page, console)
    for output in (page, console):
        assert "Reference summary is missing" not in output
        assert "exceeds display bounds" not in output
        assert evidence.evidence_sha256 in output
        assert binding.binding_sha256 in output
        assert "not all 75 keyboard/phone targets" in output
        assert "technical_reports" not in output
    assert "NOT VERIFIED" not in page and "NOT_VERIFIED" not in console
    assert "NOMINAL CHECK PASSED REHEARSAL" in page
    assert "EXPECTED FAULT CHECK PASSED REHEARSAL" in page
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" in console
    assert "EXPECTED_FAULT_CHECK_PASSED_REHEARSAL" in console

    # Inspect the rendered facts, not merely the input dictionary. JavaScript's
    # finite-number formatting may differ while preserving the numeric value.
    rendered_numeric = page.split("Synthetic point fit and coordinate roundtrips", 1)[
        1
    ].split("Residuals use synthetic points", 1)[0]
    lines = [line.strip() for line in rendered_numeric.splitlines() if line.strip()]
    for name, expected in numeric.items():
        assert float(lines[lines.index(name.replace("_", " ")) + 1]) == expected
    terminal_numeric, _ = json.JSONDecoder().raw_decode(
        console.split("Synthetic point fit and coordinate roundtrips", 1)[1].lstrip()
    )
    assert terminal_numeric == numeric

    # The service projection is detached: display-side mutation must never
    # change the full receipt that assessment/review authenticates.
    compact["reference_summary"]["graph"].clear()
    compact["checks"][0]["observed"].clear()
    assert receipt["evaluation"] == full


def test_actual_retained_verification_source_read_and_views_never_replay_probes(
    actual_reference_evidence, monkeypatch
):
    from rocell.application import rehearsal_reference_stage as reference
    from rocell.calibration import rigid_correspondence as fitter
    from rocell.geometry import UrdfModel

    binding, evidence, source_digest = actual_reference_evidence

    def forbidden(*args, **kwargs):
        pytest.fail("A retained reference view or source read reran an evaluator")

    monkeypatch.setattr(reference, "evaluate_rehearsal_reference_stage", forbidden)
    monkeypatch.setattr(reference, "run_static_phase1_calibration_rehearsal", forbidden)
    monkeypatch.setattr(reference, "fit_rigid_correspondence", forbidden)
    monkeypatch.setattr(fitter, "fit_rigid_correspondence", forbidden)
    monkeypatch.setattr(UrdfModel, "forward_kinematics", forbidden)
    assert reference.read_reference_source_context(WORKSPACE) == binding.source_context
    verified = reference.verify_rehearsal_reference_evidence(
        evidence.canonical_bytes(),
        expected_binding=binding,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_evaluator_source_sha256=source_digest,
    )
    assert verified.canonical_bytes() == evidence.canonical_bytes()
    _, compact = actual_projection(verified)
    data = commissioning()
    data["reference_evaluation"] = compact
    page, console = render(data)
    assert_holds(page, console)
    assert "NOT VERIFIED" not in page and "NOT_VERIFIED" not in console
