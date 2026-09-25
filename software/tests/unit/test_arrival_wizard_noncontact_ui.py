"""NC-01 cached-display contract, not a collision/accuracy or M1 proof.

The initial fixtures deliberately model bounded display data. The producer join
below separately exercises actual retained evaluator output when available.
Neither frontend is allowed to dispatch an evaluator or a device operation.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_arrival_wizard_arm_power_ui import report, terminal
from test_arrival_wizard_reopen_ui import browser, commissioning


def projection():
    value = report("noncontact_acceptance")
    del value["reports"]
    value["meaning"] = (
        "Readiness gap diagnostics only: historical collision inventory and separate "
        "static requirements, synthetic accuracy controls, and unmeasured real-build "
        "terms. Nominal gaps remain BLOCKED; no noncontact motion, handoff, power or contact authority."
    )
    terms = [f"term_{index}" for index in range(10)]
    controls = []
    for index, case_id in enumerate(
        (
            "real_unmeasured",
            "missing_term",
            "stale_term",
            "domain_term",
            "target_margin",
            "finite_control",
        )
    ):
        controls.append(
            {
                "case_id": case_id,
                "disposition": (
                    "BLOCKED_UNBOUNDED"
                    if index < 4
                    else (
                        "BLOCKED_TARGET_MARGIN"
                        if index == 4
                        else "DIAGNOSTIC_FITS_ZERO_AUTHORITY"
                    )
                ),
                "blocking_term_ids": (
                    list(terms) if index == 0 else [terms[0]] if index < 4 else []
                ),
                "conservative_error_micrometers": None if index < 4 else 100,
                "eroded_target_radius_micrometers": -10 if index == 4 else 1000,
                "remaining_margin_micrometers": (
                    None if index < 4 else -110 if index == 4 else 900
                ),
            }
        )
    value["safe_summary"] = {
        "schema": "rocell.rehearsal_noncontact_summary.v1",
        "nominal_readiness": "BLOCKED",
        "collision_historical": {
            "scope": "HISTORICAL_EYE_ON_ARM",
            "status": "COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE",
            "required_body_count": 19,
            "proxy_body_count": 6,
            "urdf_collision_element_count": 0,
            "missing_body_ids": ["robot_base", "link_1"],
            "unknown_body_ids": ["historical_camera_holder"],
        },
        "static_geometry": {
            "status": "NOT_EVALUATED",
            "required_body_count": 26,
            "required_source_count": 9,
            "missing_geometry_body_ids": [
                f"static_body_{index}" for index in range(26)
            ],
            "missing_source_keys": [f"geometry_source_{index}" for index in range(9)],
        },
        "accuracy": {
            "status": "BLOCKED_UNBOUNDED",
            "unit": "micrometers",
            "unmeasured_term_ids": terms,
            "conservative_error_micrometers": None,
            "remaining_margin_micrometers": None,
            "controls": controls,
        },
        "selection": {
            "domain": "NOMINAL_SOURCE_GEOMETRY",
            "tool_case_id": "nominal_tool_100mm",
            "target_scope": "NO_TARGET_REACHABILITY_EVALUATED",
            "keyboard_targets_evaluated": 0,
            "keyboard_catalog_total": 46,
            "phone_targets_evaluated": 0,
            "phone_catalog_total": 29,
        },
        "dependencies": {
            "reference_binding_sha256": "c" * 64,
            "reference_evidence_sha256": "d" * 64,
            "predecessor_receipt_sha256": "e" * 64,
            "predecessor_assessment_sha256": "f" * 64,
            "predecessor_review_sha256": "1" * 64,
            "camera_role": "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT",
            "feedback_role": "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT",
        },
        "not_evaluated": [
            "POSE",
            "ROUTE",
            "SENSITIVITY",
            "VISIBILITY",
            "DYNAMICS",
            "PHYSICAL_MOTION",
        ],
        "physical_authority": False,
    }
    return value


def render(value):
    snapshot = commissioning()
    snapshot["noncontact_evaluation"] = value
    page = browser(snapshot)
    console = terminal(snapshot)
    assert page["status"] == "Local service connected"
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["controls"] == browser(commissioning())["controls"]
    return page["text"], console


def test_nominal_gaps_and_actual_missing_measurements_remain_blocked():
    page, console = render(projection())
    for output in (page, console):
        assert "Noncontact projection is missing" not in output
        assert "Nominal build readiness" in output
        assert "BLOCKED_UNBOUNDED" in output
        assert (
            "Historical collision audit" in output and "HISTORICAL_EYE_ON_ARM" in output
        )
        assert "Separate static-camera geometry requirements" in output
        assert (
            "historical 19-body audit" in output
            and "All 26 static body requirements" in output
        )
        assert "Real-build accuracy" in output and "UNBOUNDED" in output
        assert "real_unmeasured calculation uses a synthetic target boundary" in output
        assert "Separate synthetic accuracy controls" in output
        assert "DIAGNOSTIC_FITS_ZERO_AUTHORITY" in output
        assert "-110" in output and "-10" in output
        assert "NOT_AVAILABLE" in output and "NOT_EVALUATED" in output
        assert "0 of 46 keyboard targets and 0 of 29 phone targets" in output
        assert "nominal_tool_100mm" in output
        assert "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT" in output
        assert "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT" in output
        assert "No passing UNMEASURED_SENSITIVITY_OVERLAY was substituted" in output
        assert "No power, movement or contact is authorized" in output
        assert "cannot advance to handoff" in output
        assert "Zero actual device opens" in output
        for key in (
            "POSE",
            "ROUTE",
            "SENSITIVITY",
            "VISIBILITY",
            "DYNAMICS",
            "PHYSICAL_MOTION",
        ):
            assert key in output
        for character in ("a", "b", "c", "d", "e", "f", "1"):
            assert character * 64 in output
    assert "NOMINAL CHECK PASSED REHEARSAL" not in page
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" not in console
    assert "EXPECTED FAULT CHECK PASSED REHEARSAL" in page
    assert "EXPECTED_FAULT_CHECK_PASSED_REHEARSAL" in console


@pytest.mark.parametrize("value", [None, {}, [], "invalid"])
def test_absent_or_malformed_never_infers_an_evaluation(value):
    page, console = render(value)
    for output in (page, console):
        assert "DIAGNOSTIC_FITS_ZERO_AUTHORITY" not in output
        if value is not None:
            assert "Noncontact projection is missing" in output
        else:
            assert "Retained noncontact readiness gaps" not in output


@pytest.mark.parametrize(
    "path,value",
    [
        (("stage",), "reference_frame_calibration"),
        (("outcome",), "REHEARSAL_CHECKS_PASSED"),
        (("evaluation_sha256",), "invalid"),
        (("selected_inputs_sha256",), None),
        (("physical_authority",), True),
        (("extra",), "RAW_REPORT_MUST_NOT_RENDER"),
        (("checks",), []),
        (("checks", 0, "passed"), 0),
        (("checks", 0, "passed"), True),
        (("checks", 1, "check_kind"), "PASS"),
        (("checks", 1, "extra"), "RAW_REPORT_MUST_NOT_RENDER"),
        (("safe_summary", "schema"), "other"),
        (("safe_summary", "extra"), "RAW_REPORT_MUST_NOT_RENDER"),
        (("safe_summary", "nominal_readiness"), "PASS"),
        (("safe_summary", "physical_authority"), True),
        (("safe_summary", "collision_historical", "scope"), "STATIC_CAMERA"),
        (("safe_summary", "collision_historical", "required_body_count"), 26),
        (("safe_summary", "collision_historical", "proxy_body_count"), True),
        (("safe_summary", "collision_historical", "urdf_collision_element_count"), -1),
        (
            ("safe_summary", "collision_historical", "missing_body_ids"),
            ["duplicate", "duplicate"],
        ),
        (("safe_summary", "collision_historical", "unknown_body_ids"), ["../path"]),
        (("safe_summary", "static_geometry", "status"), "PASS"),
        (("safe_summary", "static_geometry", "required_body_count"), "26"),
        (("safe_summary", "static_geometry", "required_source_count"), True),
        (("safe_summary", "static_geometry", "missing_geometry_body_ids"), []),
        (("safe_summary", "accuracy", "status"), "BOUNDED"),
        (("safe_summary", "accuracy", "unit"), "mm"),
        (("safe_summary", "accuracy", "unmeasured_term_ids"), []),
        (("safe_summary", "accuracy", "conservative_error_micrometers"), 0),
        (("safe_summary", "accuracy", "remaining_margin_micrometers"), 0),
        (("safe_summary", "accuracy", "controls"), []),
        (("safe_summary", "accuracy", "controls", 0, "case_id"), "finite_control"),
        (("safe_summary", "accuracy", "controls", 0, "blocking_term_ids"), []),
        (
            ("safe_summary", "accuracy", "controls", 0, "remaining_margin_micrometers"),
            0,
        ),
        (("safe_summary", "accuracy", "controls", 1, "disposition"), "PASS"),
        (
            (
                "safe_summary",
                "accuracy",
                "controls",
                4,
                "eroded_target_radius_micrometers",
            ),
            True,
        ),
        (
            ("safe_summary", "accuracy", "controls", 4, "remaining_margin_micrometers"),
            -(2**53),
        ),
        (
            (
                "safe_summary",
                "accuracy",
                "controls",
                5,
                "conservative_error_micrometers",
            ),
            -1,
        ),
        (
            ("safe_summary", "accuracy", "controls", 5, "remaining_margin_micrometers"),
            -1,
        ),
        (
            (
                "safe_summary",
                "accuracy",
                "controls",
                5,
                "eroded_target_radius_micrometers",
            ),
            0,
        ),
        (("safe_summary", "selection", "domain"), "UNMEASURED_SENSITIVITY_OVERLAY"),
        (
            ("safe_summary", "selection", "tool_case_id"),
            "<script>RAW_REPORT_MUST_NOT_RENDER</script>",
        ),
        (("safe_summary", "selection", "keyboard_targets_evaluated"), 46),
        (("safe_summary", "selection", "phone_targets_evaluated"), False),
        (("safe_summary", "selection", "keyboard_catalog_total"), 75),
        (("safe_summary", "dependencies", "predecessor_review_sha256"), None),
        (("safe_summary", "dependencies", "camera_role"), "PIXELS_EVALUATED"),
        (("safe_summary", "dependencies", "feedback_role"), "CALIBRATED_JOINTS"),
        (("safe_summary", "not_evaluated"), ["POSE"]),
    ],
)
def test_malformed_projection_is_withheld_whole_without_partial_pass(path, value):
    data = projection()
    selected = data
    for key in path[:-1]:
        selected = selected[key]
    selected[path[-1]] = deepcopy(value)
    page, console = render(data)
    for output in (page, console):
        assert "Noncontact projection is missing" in output
        assert "RAW_REPORT_MUST_NOT_RENDER" not in output
        assert "DIAGNOSTIC_FITS_ZERO_AUTHORITY" not in output
        assert "No power, movement or contact is authorized" in output
    assert "CHECK PASSED REHEARSAL" not in page
    assert "CHECK_PASSED_REHEARSAL" not in console


def test_literal_identifiers_and_safety_narratives_survive_without_humanization():
    value = projection()
    narrative = "observer_note_a_b <b>literal safety note</b> & not_approved"
    value["checks"][1]["meaning"] = narrative
    page, console = render(value)
    assert narrative in page
    assert narrative in console
    assert "nominal_tool_100mm" in page and "nominal_tool_100mm" in console
    assert "static_body_25" in page and "static_body_25" in console
    assert "observer note a b" not in page


def test_unsupported_partial_technical_report_never_leaks_through_generic_facts():
    value = projection()
    value["technical_reports"] = {"raw": "RAW_REPORT_MUST_NOT_RENDER"}
    page, console = render(value)
    assert "RAW_REPORT_MUST_NOT_RENDER" not in page + console
    assert "Noncontact projection is missing" in page + console


def test_finite_control_regression_is_visible_without_weakening_nominal_hold():
    value = projection()
    row = value["safe_summary"]["accuracy"]["controls"][-1]
    row.update(
        disposition="BLOCKED_UNBOUNDED",
        blocking_term_ids=["term_0"],
        conservative_error_micrometers=None,
        remaining_margin_micrometers=None,
    )
    value["checks"][1]["passed"] = False
    page, console = render(value)
    assert "Noncontact projection is missing" not in page + console
    assert "DIAGNOSTIC_FITS_ZERO_AUTHORITY" not in page + console
    assert "finite_control" in page and "finite_control" in console
    assert "BLOCKED_UNBOUNDED" in page and "BLOCKED_UNBOUNDED" in console


def test_retained_design_hashes_do_not_become_installed_geometry():
    value = projection()
    value["safe_summary"]["static_geometry"]["missing_source_keys"] = [
        f"missing_source_{index}" for index in range(5)
    ]
    page, console = render(value)
    for output in (page, console):
        assert "Noncontact projection is missing" not in output
        assert "Retained source-design hashes are not installed geometry" in output
        assert "missing_source_4" in output
        assert "static_body_25" in output


def test_actual_evaluator_to_service_projection_and_both_renderers(monkeypatch):
    """Real numeric/source producer; predecessor hashes are modeled, not M1 proof."""
    from rocell.application import rehearsal_noncontact_stage as evaluator
    from rocell.application.commissioning_rehearsal_service import (
        CommissioningRehearsalService,
    )
    from rocell.application.rehearsal_noncontact_binding import (
        RehearsalNoncontactBinding,
    )
    from rocell.application.rehearsal_reference_stage import (
        read_reference_source_context,
    )
    from test_rehearsal_reference_binding import make_binding

    workspace = Path(__file__).resolve().parents[3]
    reference = make_binding(read_reference_source_context(workspace))
    binding = RehearsalNoncontactBinding(
        reference,
        "nc-operator",
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        evaluator.read_noncontact_source_context(workspace),
    )
    artifact = evaluator.evaluate_rehearsal_noncontact_stage(workspace, binding)
    document = artifact.to_dict()
    full_before = artifact.canonical_bytes()
    assert len(full_before) < 128 * 1024
    assert document["outcome"] == "BLOCKED"
    assert (
        sum(
            row["check_kind"] == "NOMINAL" and row["passed"] is False
            for row in document["checks"]
        )
        == 3
    )
    assert sum(row["passed"] is True for row in document["checks"]) == 5

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Rendering/projection may not reread sources, evaluate or acquire hardware"
        )

    for name in (
        "evaluate_rehearsal_noncontact_stage",
        "read_noncontact_source_context",
        "load_simulation_context",
        "assess_current_collision_readiness",
        "assess_target_accuracy_budget",
        "_read",
    ):
        monkeypatch.setattr(evaluator, name, forbidden)
    compact = CommissioningRehearsalService._noncontact_projection(
        {
            "stage": "noncontact_acceptance",
            "evaluation": document,
            "evaluation_sha256": artifact.evidence_sha256,
        }
    )
    assert len(json.dumps(compact)) < 24 * 1024
    assert "technical_reports" not in compact
    page, console = render(compact)
    summary = compact["safe_summary"]
    assert summary["collision_historical"]["required_body_count"] == 19
    assert summary["collision_historical"]["proxy_body_count"] == 6
    assert summary["collision_historical"]["urdf_collision_element_count"] == 0
    assert summary["static_geometry"]["required_body_count"] == 26
    assert summary["static_geometry"]["required_source_count"] == 9
    assert len(summary["static_geometry"]["missing_source_keys"]) == 5
    assert len(summary["accuracy"]["unmeasured_term_ids"]) == 10
    assert summary["accuracy"]["controls"][-1]["remaining_margin_micrometers"] == 3000
    assert summary["accuracy"]["controls"][-2]["remaining_margin_micrometers"] == -1500
    for output in (page, console):
        assert "Noncontact projection is missing" not in output
        assert "The retained check projection is missing" not in output
        assert "Check data is not verified" not in output
        assert summary["selection"]["tool_case_id"] in output
        assert artifact.evidence_sha256 in output
        assert "-1500" in output and "3000" in output
        assert "BLOCKED_UNBOUNDED" in output
        assert "cannot advance to handoff" in output
    assert "NOMINAL CHECK PASSED REHEARSAL" not in page
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" not in console
    assert artifact.canonical_bytes() == full_before
