"""Cached stage-only UI models, not observed isolation, ownership or M1 proof.

Fixed prerequisite questions are produced from real controlled files. New
qualification outcomes and original storage commits here are explicitly modeled.
Both production renderers consume these summaries without device or store I/O.
"""

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from rocell.ui.terminal import _SourceReassessmentDisplay, _TerminalWizard
from test_arrival_wizard_terminal import Service
from test_wizard_physical_camera_setup_ui import (
    complete_setup,
    prerequisite_summary,
)  # noqa: F401
from test_wizard_workspace_source_ui import CHECKS, modeled, render_snapshot, snapshot


TITLE = "Workspace-source reassessment — stage-only admission"
ACCEPTED = "Stage 1 accepted only — no camera runtime release."


def fixture_view(data, *, verdict="PASS", reviewed=True, reopened=False, stage2=False):
    setup = modeled(data, reviewed=True, reopened=reopened)
    setup["source_workflow"]["status"] = "HISTORICAL_HELD"
    binding = setup["session"]["binding"]
    original = setup["source_workflow"]
    q = {
        "qualification_id": "sourcequal-" + "a" * 32,
        "collection_launch_id": binding["launch_id"],
        "operator_id": "source_operator",
        "original_subjects": {
            role + "_sha256": original[role][role + "_sha256"]
            for role in ("receipt", "assessment", "review")
        },
        "receipt_sha256": "4" * 64,
        "assessment_sha256": "5" * 64,
        "software_checks": [{"check_id": name, "passed": True} for name in CHECKS],
        "isolation": {
            "state": "OBSERVED_DISCONNECTED" if verdict == "PASS" else "UNKNOWN",
            "statement": "MODELED isolation statement_only; no hardware observation in this test.",
            "attachment_sha256": "6" * 64 if verdict == "PASS" else None,
            "measurement_truth_verified": False,
        },
        "ownership": {
            "status": "SOFTWARE_MECHANISMS_PASSED",
            "report_sha256": "7" * 64,
            "checks": [
                {
                    "check_id": name,
                    "passed": True,
                    "provenance": (
                        "CONTROLLED_FAULT_INJECTION"
                        if index == 5
                        else "ACTUAL_HOST_MECHANISM"
                    ),
                }
                for index, name in enumerate(_SourceReassessmentDisplay.OWNERSHIP)
            ],
        },
        "verdict": verdict,
        "missing_requirements": (
            [] if verdict == "PASS" else ["DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED"]
        ),
        "review": (
            {
                "review_sha256": "8" * 64,
                "reviewer_id": "source_reviewer",
                "review_launch_id": setup["launch_session_id"],
                "verdict": verdict,
                "distinct_operator_labels": True,
                "authenticated_independent_people": False,
            }
            if reviewed
            else None
        ),
    }
    stage1 = verdict if reviewed else "REVIEW_PENDING"
    setup["session"]["stages"][0].update(state=stage1, last_event_sequence=7)
    setup["session"]["stages"][1].update(
        state="WAITING_OPERATOR" if stage2 else "PENDING",
        last_event_sequence=8 if stage2 else None,
    )
    view = snapshot(setup)
    view["source_reassessment"] = {
        "schema": "rocell.wizard_source_reassessment.v1",
        "status": "REVIEWED_" + verdict if reviewed else "REVIEW_PENDING",
        "source_sha256": setup["source_sha256"],
        "launch_session_id": setup["launch_session_id"],
        "original_context": {
            "source_sha256": setup["source_sha256"],
            "session_id": binding["session_id"],
            "cell_id": binding["cell_id"],
            "origin_launch_id": binding["launch_id"],
            "header_sha256": setup["session"]["verification"]["session"][
                "header_sha256"
            ],
            "prerequisites_sha256": setup["prerequisites"]["evidence_sha256"],
        },
        "publication": {
            "status": "CURRENT",
            "operation_id": "source-qualification-operation",
        },
        "stage_states": {
            "workspace_sources": stage1,
            "static_camera_contract": "WAITING_OPERATOR" if stage2 else "PENDING",
        },
        "qualification": q,
        "next_action": (
            "physical_static_contract_begin"
            if reviewed and verdict == "PASS" and not stage2
            else None
        ),
        "physical_authority": False,
        "hardware_qualified": False,
        "native_release_allowed": False,
        "device_io_performed": False,
        "meaning": "Explicitly modeled source-stage evidence for presentation tests only.",
    }
    return view


def rendered(view):
    before = deepcopy(view)
    assert (
        _SourceReassessmentDisplay.projection(view["source_reassessment"], view)
        == view["source_reassessment"]
    )
    texts = render_snapshot(view)
    for text in texts:
        assert "SOURCE_REASSESSMENT_NOT_VERIFIED" not in text
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        assert TITLE in text
    assert view == before
    return texts


@pytest.mark.parametrize("reopened", [False, True])
@pytest.mark.parametrize("stage2", [False, True])
def test_reviewed_source_only_pass_preserves_original_blocked_history(
    complete_setup, reopened, stage2
):
    view = fixture_view(complete_setup, reopened=reopened, stage2=stage2)
    for text in rendered(view):
        assert ACCEPTED in text
        assert "Saved assessment verdict: BLOCKED" in text
        assert "Original BLOCKED source subjects — unchanged" in text
        assert "not current electrical telemetry" in text
        assert "MODELED isolation statement_only" in text
        assert "not authenticated independent people" in text
        assert "CONTROLLED_FAULT_INJECTION" in text
        assert "not observed operating-system PID reuse" in text
        assert (
            "remains WAITING_OPERATOR, not accepted" in text
            if stage2
            else "Stage 2 remains PENDING" in text
        )
        assert (
            view["source_reassessment"]["original_context"]["origin_launch_id"] in text
        )
        assert view["source_reassessment"]["launch_session_id"] in text


@pytest.mark.parametrize("verdict", ["PASS", "BLOCKED"])
def test_assessed_verdict_never_becomes_a_committed_pass_before_review(
    complete_setup, verdict
):
    for text in rendered(fixture_view(complete_setup, verdict=verdict, reviewed=False)):
        assert ACCEPTED not in text
        assert "Exact-subject review is still required" in text
        assert "An assessed PASS is not a committed source-stage PASS" in text


def test_unknown_isolation_stays_blocked(complete_setup):
    for text in rendered(fixture_view(complete_setup, verdict="BLOCKED")):
        assert ACCEPTED not in text
        assert "DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED" in text
        assert "UNKNOWN cannot satisfy isolation" in text


def test_empty_unknown_statement_is_not_an_invented_observation(complete_setup):
    view = fixture_view(complete_setup, verdict="BLOCKED")
    view["source_reassessment"]["qualification"]["isolation"]["statement"] = ""
    for text in rendered(view):
        assert "No isolation statement recorded." in text
        assert ACCEPTED not in text


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_pending_historical_withholding_never_relabels_original_acceptance(
    complete_setup, publication
):
    view = fixture_view(complete_setup)
    value = view["source_reassessment"]
    value.update(status="HISTORICAL_HELD", next_action=None)
    value["publication"]["status"] = publication
    if publication == "PENDING":
        value["qualification"] = None
    else:
        view["source_binding_sha256"] = "f" * 64
        view["session_id"] = "wizard-" + "b" * 32
    for text in rendered(view):
        assert ACCEPTED not in text
        assert (
            "publication pending" in text
            if publication == "PENDING"
            else "Historical source qualification subject only" in text
        )
        if publication == "PENDING":
            assert "MODELED isolation statement_only" not in text


@pytest.mark.parametrize("status", ["NOT_STARTED", "INCOMPLETE_HELD"])
def test_no_complete_subject_is_inferred_for_initial_or_partial_state(
    complete_setup, status
):
    view = fixture_view(complete_setup)
    view["source_reassessment"].update(
        status=status, qualification=None, next_action="physical_source_qualify"
    )
    for text in rendered(view):
        assert ACCEPTED not in text
        assert (
            "Incomplete qualification attempt" in text
            if status == "INCOMPLETE_HELD"
            else "No complete source qualification is retained" in text
        )


@pytest.mark.parametrize(
    "path,value",
    [
        (("physical_authority",), True),
        (("hardware_qualified",), True),
        (("native_release_allowed",), True),
        (("device_io_performed",), 0),
        (("schema",), "unsupported"),
        (("next_action",), "camera_connect"),
        (("source_sha256",), "f" * 64),
        (("launch_session_id",), "wizard-" + "f" * 32),
        (("original_context", "header_sha256"), "f" * 64),
        (("original_context", "prerequisites_sha256"), "f" * 64),
        (("original_context", "cell_id"), "other-cell"),
        (("original_context", "session_id"), "other-session"),
        (("original_context", "origin_launch_id"), "wizard-" + "f" * 32),
        (("qualification", "original_subjects", "review_sha256"), "f" * 64),
        (("qualification", "qualification_id"), "raw/path"),
        (("qualification", "software_checks", 0, "passed"), 1),
        (("qualification", "software_checks", 0, "passed"), False),
        (("qualification", "isolation", "state"), "UNKNOWN"),
        (("qualification", "isolation", "attachment_sha256"), None),
        (("qualification", "isolation", "measurement_truth_verified"), True),
        (("qualification", "isolation", "statement"), "x" * 513),
        (("qualification", "isolation", "statement"), "hidden\nline"),
        (("qualification", "ownership", "status"), "HELD"),
        (
            ("qualification", "ownership", "checks", 5, "provenance"),
            "ACTUAL_HOST_MECHANISM",
        ),
        (("qualification", "ownership", "checks", 0, "passed"), "true"),
        (("qualification", "ownership", "checks", 0, "check_id"), "UNKNOWN_CHECK"),
        (("qualification", "review", "reviewer_id"), "SOURCE_OPERATOR"),
        (("qualification", "review", "verdict"), "BLOCKED"),
        (("qualification", "review", "authenticated_independent_people"), True),
        (("stage_states", "workspace_sources"), "BLOCKED"),
        (("stage_states", "static_camera_contract"), "PASS"),
        (("publication", "status"), "PENDING"),
        (("publication", "operation_id"), None),
    ],
)
def test_malformed_or_unbound_acceptance_is_withheld_in_both_renderers(
    complete_setup, path, value
):
    view = fixture_view(complete_setup)
    target = view["source_reassessment"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert (
        _SourceReassessmentDisplay.projection(view["source_reassessment"], view) is None
    )
    for text in render_snapshot(view):
        assert "SOURCE_REASSESSMENT_NOT_VERIFIED" in text
        assert ACCEPTED not in text


def test_legacy_snapshot_has_no_inferred_reassessment(complete_setup):
    view = snapshot(modeled(complete_setup, reviewed=True))
    for text in render_snapshot(view):
        assert "No source reassessment projection in this legacy snapshot" in text
        assert "Saved assessment verdict: BLOCKED" in text and ACCEPTED not in text


def test_prior_intake_and_original_source_remain_readable_after_stage_advancement(
    tmp_path,
):
    from test_physical_intake_submission import intake_fixture
    from test_wizard_physical_intake_evidence_ui import fixture_view as intake_view

    legacy = intake_view(tmp_path, intake_fixture(observed=False))
    original = deepcopy(legacy["physical_camera_setup"]["source_workflow"])
    view = fixture_view(legacy["physical_camera_setup"])
    setup = view["physical_camera_setup"]
    setup["schema"] = "rocell.wizard_physical_camera_setup.v3"
    original["status"] = "HISTORICAL_HELD"
    setup["source_workflow"] = original
    intake = deepcopy(legacy["physical_intake_evidence"])
    intake["status"] = "HISTORICAL_HELD"
    intake["publication"]["status"] = "HISTORICAL_HELD"
    view["physical_intake_evidence"] = intake
    for text in rendered(view):
        assert "PHYSICAL_INTAKE_EVIDENCE_NOT_VERIFIED" not in text
        assert ACCEPTED in text and "Saved assessment verdict: BLOCKED" in text
        assert intake["collection"]["submission"]["submission_sha256"] in text
        assert intake["collection"]["review"]["review_sha256"] in text


def test_isolation_statement_is_literal_text_not_markup_or_humanized(complete_setup):
    view = fixture_view(complete_setup)
    statement = (
        'MODELED statement_with_underscores é <img src="x" onerror="activate()">'
    )
    view["source_reassessment"]["qualification"]["isolation"]["statement"] = statement
    for text in rendered(view):
        assert statement in text


def test_terminal_summary_render_never_reads_files_or_runs_qualification(
    complete_setup, monkeypatch
):
    view = fixture_view(complete_setup)
    output = []
    wizard = _TerminalWizard(
        Service([]), lambda _: "quit", output.append, lambda _: None
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("Cached source reassessment attempted external I/O")

    with monkeypatch.context() as guard:
        for method in ("read_bytes", "read_text", "open", "stat"):
            guard.setattr(Path, method, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        wizard.show_source_reassessment(view["source_reassessment"], view)
    assert ACCEPTED in output
