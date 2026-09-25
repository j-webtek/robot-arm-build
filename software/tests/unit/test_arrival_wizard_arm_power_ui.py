"""Cached retained-check UI projections; no evaluator, M1, device or power I/O."""

from copy import deepcopy
from pathlib import Path

import pytest

from test_arrival_wizard_reopen_ui import ReopenService, browser, commissioning
from test_arrival_wizard_terminal import dispatched, run


STAGES = [
    ("arm_identity_evaluation", "arm_identity"),
    ("power_evaluation", "power_safety"),
    ("power_evaluation", "power_on_observation"),
]


def report(stage):
    return {
        "stage": stage,
        "outcome": "BLOCKED",
        "evaluation_sha256": "a" * 64,
        "selected_inputs_sha256": "b" * 64,
        "physical_authority": False,
        "meaning": "Fixed synthetic assessor checks; not received hardware.",
        "provenance": {
            "kind": "SYNTHETIC_TYPED_ASSESSOR_REHEARSAL",
            "input_origin": "CLOSED_SYNTHETIC_FIXTURE",
            "physical_observations": False,
        },
        "checks": [
            {
                "check_id": "nominal_contract",
                "check_kind": "NOMINAL",
                "passed": False,
                "observed": {"diagnostic_ready": False, "reason_codes": ["REGRESSED"]},
                "meaning": "Nominal input must satisfy the real contract.",
            },
            {
                "check_id": "reject_unsafe_fixture",
                "check_kind": "EXPECTED_FAULT",
                "passed": True,
                "observed": {"hold_required": True, "side_effect_uncertain": True},
                "meaning": "Injected uncertainty must remain an explicit hold.",
            },
            {
                "check_id": "physical_identity_held",
                "check_kind": "INVARIANT",
                "passed": True,
                "observed": {"device_open_count": 0},
                "meaning": "Rehearsal must not qualify received identity or energy.",
            },
        ],
        # Full records are retained elsewhere; neither frontend may expand this
        # incidental field through the generic commissioning facts renderer.
        "reports": {"raw_protocol_log": "NEVER_RENDER_RAW_PROTOCOL_LOG"},
    }


def projection(field, value):
    result = commissioning()
    result[field] = value
    return result


def terminal(value):
    service = ReopenService(value)
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0
    assert all(call[0] == "view" for call in service.calls)
    assert dispatched(service, "prepare") == []
    assert dispatched(service, "execute") == []
    assert dispatched(service, "operation") == []
    assert service.shutdown_count == 0
    return "\n".join(output)


@pytest.mark.parametrize("field,stage", STAGES)
def test_frontends_distinguish_nominal_failure_expected_fault_and_invariant(
    field, stage
):
    value = projection(field, report(stage))
    rendered = browser(value)
    console = terminal(value)
    assert rendered["status"] == "Local service connected"
    for output in (rendered["text"], console):
        assert "BLOCKED" in output
        assert "Nominal input must satisfy" in output
        assert "Injected uncertainty must remain" in output
        assert "cannot replace passing nominal checks" in output
        assert "not received hardware" in output
        assert "firmware are unverified" in output
        assert "NEVER_RENDER_RAW_PROTOCOL_LOG" not in output
        assert "a" * 64 in output and "b" * 64 in output
    assert "EXPECTED FAULT CHECK PASSED REHEARSAL" in rendered["text"]
    assert "EXPECTED_FAULT_CHECK_PASSED_REHEARSAL" in console
    assert "NOMINAL CHECK PASSED REHEARSAL" not in rendered["text"]
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" not in console
    assert "INVARIANT CHECK PASSED REHEARSAL" in rendered["text"]
    assert rendered["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None}
    ]
    assert rendered["controls"] == browser(commissioning())["controls"]


@pytest.mark.parametrize("field,stage", STAGES)
def test_passing_nominal_checks_still_do_not_claim_physical_authority(field, stage):
    data = report(stage)
    data["outcome"] = "REHEARSAL_CHECKS_PASSED"
    data["checks"][0]["passed"] = True
    value = projection(field, data)
    rendered = browser(value)
    console = terminal(value)
    assert "NOMINAL CHECK PASSED REHEARSAL" in rendered["text"]
    assert "NOMINAL_CHECK_PASSED_REHEARSAL" in console
    for output in (rendered["text"], console):
        assert "firmware are unverified" in output
        assert "does not assess, review, replay, or advance a stage" in output
    if field == "power_evaluation":
        assert "not a power-state observation" in rendered["text"]
        assert "No power-on, power-off, reset or firmware control" in console


@pytest.mark.parametrize("field,stage", STAGES)
@pytest.mark.parametrize(
    "mutation",
    [
        {"stage": "feedback_only_connection"},
        {"outcome": "PASS"},
        {"physical_authority": True},
        {"evaluation_sha256": "unbound"},
        {"selected_inputs_sha256": None},
        {"meaning": None},
        {"provenance": None},
        {"checks": []},
        {"checks": [None] * 17},
    ],
    ids=[
        "wrong-stage",
        "physical-pass-label",
        "authority",
        "unbound",
        "missing-inputs",
        "missing-meaning",
        "missing-provenance",
        "empty-checks",
        "too-many-checks",
    ],
)
def test_malformed_projection_is_visible_unverified_not_silently_truncated(
    field, stage, mutation
):
    data = report(stage)
    data.update(mutation)
    value = projection(field, data)
    rendered = browser(value)
    console = terminal(value)
    assert rendered["status"] == "Local service connected"
    assert "NOT VERIFIED" in rendered["text"]
    assert "NOT_VERIFIED" in console
    for output in (rendered["text"], console):
        assert "no report is silently truncated" in output
        assert "CHECK_PASSED_REHEARSAL" not in output
        assert "CHECK PASSED REHEARSAL" not in output
        assert "NEVER_RENDER_RAW_PROTOCOL_LOG" not in output


@pytest.mark.parametrize(
    "check",
    [
        None,
        {},
        {"check_kind": "POWER_ON"},
        {"passed": "true"},
        {"passed": 1},
        {"observed": "x" * 2049},
        {"observed": [[[[[[[0]]]]]]]},
        {"observed": {"values": list(range(33))}},
        {"observed": {"x": "a" * 2048, "y": "b" * 2048}},
        {"observed": [[0, 0, 0, 0] for _ in range(31)]},
        {"observed": 10**30},
        {"meaning": "x" * 513},
    ],
    ids=[
        "null",
        "empty",
        "unknown-kind",
        "string-bool",
        "integer-bool",
        "large-text",
        "deep-data",
        "long-array",
        "rendered-data-limit",
        "node-count-limit",
        "unsafe-number",
        "long-meaning",
    ],
)
def test_bad_check_never_gets_a_pass_badge(check):
    data = report("arm_identity")
    row = deepcopy(data["checks"][1])
    if check is None or check == {}:
        row = check
    else:
        row.update(check)
    data["checks"] = [row]
    value = projection("arm_identity_evaluation", data)
    rendered = browser(value)
    console = terminal(value)
    assert rendered["status"] == "Local service connected"
    assert "NOT VERIFIED" in rendered["text"] and "NOT_VERIFIED" in console
    assert "CHECK PASSED REHEARSAL" not in rendered["text"]
    assert "CHECK_PASSED_REHEARSAL" not in console


@pytest.mark.parametrize("value", [None, "invalid", [], False])
def test_absent_or_scalar_projection_never_crashes_or_dispatches(value):
    data = projection("arm_identity_evaluation", value)
    rendered = browser(data)
    console = terminal(data)
    assert rendered["status"] == "Local service connected"
    assert rendered["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None}
    ]
    if value is None:
        assert "Retained synthetic arm-identity checks" not in rendered["text"]
        assert "Retained synthetic arm-identity checks" not in console
    else:
        assert "NOT VERIFIED" in rendered["text"] and "NOT_VERIFIED" in console


def test_text_is_literal_and_terminal_control_sequences_are_escaped():
    data = report("power_safety")
    data["checks"][1][
        "meaning"
    ] = "<img src=x onerror=alert(1)>\x1b[31m expected handling"
    data["checks"][1]["observed"] = {"disposition": "\x1b[2JHOLD"}
    value = projection("power_evaluation", data)
    rendered = browser(value)
    console = terminal(value)
    assert rendered["status"] == "Local service connected"
    assert "<img src=x onerror=alert(1)>" in rendered["text"]
    assert "\x1b" not in console
    assert "\\u001b" in console


def test_both_reports_remain_separate_when_present_together():
    value = projection("arm_identity_evaluation", report("arm_identity"))
    value["power_evaluation"] = report("power_on_observation")
    rendered = browser(value)
    console = terminal(value)
    for output in (rendered["text"], console):
        assert "Retained synthetic arm-identity checks" in output
        assert "Retained synthetic power/startup checks" in output
    assert rendered["controls"] == browser(commissioning())["controls"]


def assert_actual_projection_fits(field, projected):
    value = projection(field, projected)
    rendered = browser(value)
    console = terminal(value)
    assert rendered["status"] == "Local service connected"
    assert "NOT VERIFIED" not in rendered["text"]
    assert '"check_status": "NOT_VERIFIED"' not in console
    assert "NOT_VERIFIED:" not in console
    assert "exceeds display bounds" not in rendered["text"]
    for row in projected["checks"]:
        assert row["check_id"].replace("_", " ") in rendered["text"]
        assert row["check_id"] in console
    assert rendered["controls"] == browser(commissioning())["controls"]


def test_actual_stage9_evaluator_and_service_projection_fit_without_truncation(
    monkeypatch,
):
    from rocell.application import physical_device_inventory as inventory
    from rocell.application import rehearsal_arm_identity_stage as evaluator
    from rocell.application.commissioning_rehearsal_service import (
        CommissioningRehearsalService,
    )

    def forbidden(*args, **kwargs):
        pytest.fail(
            "A retained-check presentation test must not enumerate host devices"
        )

    for name in (
        "inventory_serial_ports_with_pyserial",
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
    ):
        monkeypatch.setattr(inventory, name, forbidden)
    binding = evaluator.RehearsalArmIdentityBinding(
        workspace_source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        cell_id="fixture-cell",
        session_id="fixture-session",
        operator_id="fixture-operator",
        predecessor_receipt_sha256="c" * 64,
        predecessor_assessment_sha256="d" * 64,
        predecessor_review_sha256="e" * 64,
        static_registration_evidence_sha256="f" * 64,
    )
    evidence = evaluator.evaluate_rehearsal_arm_identity_stage(
        Path(__file__).resolve().parents[3], binding
    )
    # Use the real service's pure cached projection, not a second UI-shaped
    # substitute. No service is constructed or durable storage qualified.
    projected = CommissioningRehearsalService._arm_setup_projection(
        {
            "stage": binding.stage,
            "evaluation": evidence.to_dict(),
            "evaluation_sha256": evidence.evidence_sha256,
        }
    )
    assert_actual_projection_fits("arm_identity_evaluation", projected)


@pytest.mark.parametrize("stage", ["power_safety", "power_on_observation"])
def test_actual_power_evaluator_and_service_projection_fit_without_truncation(stage):
    from rocell.application import rehearsal_power_stages as evaluator
    from rocell.application.commissioning_rehearsal_service import (
        CommissioningRehearsalService,
    )

    binding = evaluator.RehearsalPowerBinding(
        workspace_source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        cell_id="fixture-cell",
        session_id="fixture-session",
        operator_id="fixture-operator",
        stage=stage,
        predecessor_receipt_sha256="c" * 64,
        predecessor_assessment_sha256="d" * 64,
        predecessor_review_sha256="e" * 64,
        arm_identity_evidence_sha256="f" * 64,
    )
    # The implementation exposes only closed typed assessor fixtures, with no
    # injectable power/provider interface and no storage or hardware calls.
    evidence = evaluator.evaluate_rehearsal_power_stage(
        Path(__file__).resolve().parents[3], binding
    )
    projected = CommissioningRehearsalService._arm_setup_projection(
        {
            "stage": stage,
            "evaluation": evidence.to_dict(),
            "evaluation_sha256": evidence.evidence_sha256,
        }
    )
    assert_actual_projection_fits("power_evaluation", projected)
