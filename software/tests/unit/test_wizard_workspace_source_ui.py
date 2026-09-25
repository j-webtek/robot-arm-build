"""Cached original source subjects -> UI; no M1 mutation/device/evaluator calls.

Most source-subject summaries below are explicitly modeled against actual fixed
prerequisite questions and typed modeled storage snapshots. Separate producer
tests collect the real fixed files and use actual receipt/assessment/review codecs
plus the root cached wrapper. Neither group is storage durability proof.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from threading import Event, RLock
from time import monotonic_ns
from types import SimpleNamespace

import pytest

from rocell.ui.terminal import (
    _PhysicalSetupDisplay,
    _TerminalWizard,
    _WorkspaceSourceDisplay,
)
from test_arrival_wizard_device_selection_ui import browser as _browser, selection
from test_arrival_wizard_terminal import Service, action, dispatched, run
from test_wizard_native_arm_ui import CachedView
from test_wizard_physical_camera_restart_ui import version_two
from test_wizard_physical_camera_setup_ui import complete_setup, prerequisite_summary


FLAGS = {
    "physical_authority": False,
    "canonical_stage_pass": False,
    "device_io_performed": False,
    "power_state": "UNKNOWN",
}


def browser(*args, **kwargs):
    # Node emits UTF-8. Windows' default subprocess text decoder can otherwise
    # corrupt Unicode labels in this test harness, not in the real browser.
    original = subprocess.run

    def utf8(*arguments, **options):
        options.setdefault("encoding", "utf-8")
        return original(*arguments, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "run", utf8)
        return _browser(*args, **kwargs)


RECEIPT = "1" * 64
ASSESSMENT = "2" * 64
REVIEW = "3" * 64
CHECKS = (
    "controlled_build_sources",
    "foundation_semantics",
    "unchanged_file_snapshot",
    "runtime_fail_closed",
    "launcher_and_bootstrap_present",
    "base_software_ready",
    "static_camera_plan_selected",
)
MISSING = [
    "DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED",
    "HZ_012_QUALIFICATION_EVIDENCE_MISSING",
    "STATIC_CAMERA_RELEASE_NOT_QUALIFIED",
]


def modeled(data, *, reviewed=False, failed_software=False, reopened=False):
    setup = version_two(data, reopened=reopened)
    b = setup["session"]["binding"]
    binding = {
        "source_sha256": setup["source_sha256"],
        "session_id": b["session_id"],
        "origin_launch_id": b["launch_id"],
        "collection_launch_id": b["launch_id"],
        "header_sha256": setup["session"]["verification"]["session"]["header_sha256"],
        "prerequisites_sha256": setup["prerequisites"]["evidence_sha256"],
        "operator_id": "source_operator_é",
    }
    checks = [
        {
            "check_id": name,
            "passed": not (failed_software and name == "base_software_ready"),
        }
        for name in CHECKS
    ]
    receipt = {
        "schema": "rocell.workspace_source_receipt_summary.v1",
        "status": "FILE_FACTS_COLLECTED",
        "binding": deepcopy(binding),
        "receipt_sha256": RECEIPT,
        "software_checks": deepcopy(checks),
        "source_file_count": 27,
        "foundation_contract_count": 4,
        "host_blocker_count": int(failed_software),
        **FLAGS,
    }
    assessment = {
        "schema": "rocell.workspace_source_assessment_summary.v1",
        "status": "ASSESSED",
        "verdict": "BLOCKED",
        "binding": deepcopy(binding),
        "receipt_sha256": RECEIPT,
        "assessment_sha256": ASSESSMENT,
        "software_checks": deepcopy(checks),
        "missing_requirements": MISSING
        + (["SOFTWARE_PREREQUISITES_NOT_READY"] if failed_software else []),
        **FLAGS,
    }
    review = (
        {
            "schema": "rocell.workspace_source_review_summary.v1",
            "status": "ACKNOWLEDGED_BLOCKED",
            "verdict": "BLOCKED",
            "binding": deepcopy(binding),
            "receipt_sha256": RECEIPT,
            "assessment_sha256": ASSESSMENT,
            "review_sha256": REVIEW,
            "reviewer_id": "source_reviewer_é",
            "review_launch_id": b["launch_id"],
            "distinct_operator_labels": True,
            "authenticated_independent_people": False,
            **FLAGS,
        }
        if reviewed
        else None
    )
    setup["source_workflow"] = {
        "schema": "rocell.wizard_workspace_source_workflow.v1",
        "status": "REVIEWED_BLOCKED" if reviewed else "REVIEW_PENDING",
        "receipt": receipt,
        "assessment": assessment,
        "review": review,
        **FLAGS,
    }
    setup["session"]["stages"][0].update(
        state="BLOCKED" if reviewed else "REVIEW_PENDING",
        last_event_sequence=3 if reviewed else 2,
    )
    return setup


def snapshot(setup):
    view = Service([]).view()
    view.update(
        mode="physical",
        session_id=setup["launch_session_id"],
        source_binding_sha256=setup["source_sha256"],
        device_selection=None,
        camera={},
        arm={},
        operations=[],
        stages=[],
        physical_camera_setup=setup,
    )
    return view


def render(setup):
    return render_snapshot(snapshot(setup))


def render_snapshot(view):
    page = browser(selection(), "camera", snapshot=deepcopy(view))
    assert page["status"] == "Local service connected", page["error"]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["dialogOpen"] is False
    service = CachedView(view)
    code, output, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)] and service.shutdown_count == 0
    return page["text"], "\n".join(output)


def panel(text):
    return text.split("Saved workspace-source assessment and review", 1)[1].split(
        "Stage 1–4", 1
    )[0]


@pytest.fixture(scope="module")
def actual_source_subjects(prerequisite_summary):
    """Actual file-only producer; only the broad source identity is modeled."""
    from rocell.application import physical_camera_prerequisites as prerequisites
    from rocell.application import physical_source_stage_evidence as codec

    workspace = Path(__file__).resolve().parents[3]
    binding = prerequisite_summary["binding"]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            prerequisites, "source_fingerprint", lambda _: binding["source_sha256"]
        )
        patch.setattr(codec, "source_fingerprint", lambda _: binding["source_sha256"])
        original = prerequisites.collect_physical_camera_prerequisites(
            workspace,
            source_sha256=binding["source_sha256"],
            session_id=binding["session_id"],
            launch_session_id=binding["launch_session_id"],
            cancellation=Event(),
            deadline_ns=monotonic_ns() + 30_000_000_000,
        )
        assert original.safe_summary() == prerequisite_summary
        receipt = codec.collect_workspace_source_receipt(
            workspace,
            prerequisites=original,
            source_sha256=binding["source_sha256"],
            session_id=binding["session_id"],
            origin_launch_id=binding["launch_session_id"],
            collection_launch_id=binding["launch_session_id"],
            header_sha256="6" * 64,  # Explicit modeled original M1 header.
            operator_id="actual_source_operator_é",
            cancellation=Event(),
        )
    assessment = codec.assess_workspace_source_receipt(receipt)
    review = codec.review_workspace_source_assessment(
        receipt,
        assessment,
        reviewer_id="actual_source_reviewer_é",
        review_launch_id=binding["launch_session_id"],
    )
    return receipt, assessment, review


def actual_wrapper(setup, subjects, *, reviewed, publication="CURRENT"):
    """Call the real cached service method, with explicitly modeled M1 state."""
    from rocell.application.physical_camera_setup_service import (
        PhysicalCameraSetupService,
    )

    selected = dict(zip(("receipt", "assessment", "review"), subjects))
    if not reviewed:
        del selected["review"]
    owner = SimpleNamespace(
        _lock=RLock(),
        _source_workflow={
            "state": "BLOCKED" if reviewed else "REVIEW_PENDING",
            "review": subjects[2].to_dict() if reviewed else None,
        },
        _source_summaries={
            key: value.safe_summary() for key, value in selected.items()
        },
        _publication={"status": publication, "operation_id": "modeled-publication"},
    )
    setup["source_workflow"] = PhysicalCameraSetupService.source_workflow_view(owner)
    setup["session"]["stages"][0].update(
        state="BLOCKED" if reviewed else "REVIEW_PENDING",
        last_event_sequence=3 if reviewed else 2,
    )
    setup["publication"] = deepcopy(owner._publication)
    if publication != "CURRENT":
        setup["prerequisites"] = None
        setup["requirements_provenance"] = "NONE"
    return setup


@pytest.mark.parametrize("reviewed", [False, True])
@pytest.mark.parametrize("reopened", [False, True])
def test_actual_file_codec_cached_wrapper_and_both_renderers(
    complete_setup, actual_source_subjects, reviewed, reopened
):
    setup = actual_wrapper(
        version_two(complete_setup, reopened=reopened),
        actual_source_subjects,
        reviewed=reviewed,
    )
    before = deepcopy(setup)
    receipt, assessment, review = actual_source_subjects
    summary = receipt.safe_summary()
    assert [row["check_id"] for row in summary["software_checks"]] == list(CHECKS)
    assert all(row["passed"] for row in summary["software_checks"][:3])
    assert 0 < summary["source_file_count"] <= 128
    assert 0 < summary["foundation_contract_count"] <= 32
    assert assessment.safe_summary()["verdict"] == "BLOCKED"
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        assert "Saved assessment verdict: BLOCKED" in text
        assert "PHYSICAL ACCEPTANCE BLOCKED" in text
        assert "power observation: UNKNOWN" in text
        assert "actual_source_operator_é" in text
        assert receipt.sha256 in text and assessment.sha256 in text
        for row in summary["software_checks"]:
            status = (
                "SOFTWARE_CHECK_PASSED" if row["passed"] else "SOFTWARE_CHECK_BLOCKED"
            )
            assert f"{row['check_id']}: {status}" in text
        for missing in assessment.safe_summary()["missing_requirements"]:
            assert missing in text
        if reviewed:
            assert review.sha256 in text and "actual_source_reviewer_é" in text
            assert "not authenticated independent people" in text
        else:
            assert "Original stage is REVIEW_PENDING" in text
        if reopened:
            assert setup["origin_launch_id"] != setup["launch_session_id"]
            assert setup["origin_launch_id"] in text
            assert setup["launch_session_id"] in text
    assert setup == before


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_actual_cached_wrapper_withholds_pending_and_marks_history(
    complete_setup, actual_source_subjects, publication
):
    setup = actual_wrapper(
        version_two(complete_setup, reopened=True),
        actual_source_subjects,
        reviewed=True,
        publication=publication,
    )
    wrapper = setup["source_workflow"]
    if publication == "PENDING":
        assert wrapper["status"] == "NOT_STARTED"
        assert all(wrapper[key] is None for key in ("receipt", "assessment", "review"))
    else:
        assert wrapper["status"] == "HISTORICAL_HELD"
        assert wrapper["review"]["review_sha256"] == actual_source_subjects[2].sha256
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        if publication == "PENDING":
            assert actual_source_subjects[0].sha256 not in text
            assert "actual_source_operator_é" not in text
        else:
            assert "HISTORICAL_HELD" in text
            assert "actual_source_operator_é" in text
            assert "actual_source_reviewer_é" in text
            assert "PHYSICAL ACCEPTANCE BLOCKED" in text


@pytest.mark.parametrize("at_limit", [False, True])
def test_retained_event_history_preserves_repeated_evidence_references(
    complete_setup, at_limit
):
    # V2 snapshots concatenate the references from each committed event. The
    # review event correctly reuses the exact receipt and assessment subjects.
    setup = modeled(complete_setup, reviewed=True, reopened=True)
    refs = ["evidence-" + digest for digest in (RECEIPT, ASSESSMENT, REVIEW)]
    ordered_history = [refs[0]] * 256 if at_limit else [*refs[:2], *refs]
    setup["session"]["stages"][0].update(
        evidence_ids=ordered_history, last_event_sequence=2
    )
    original = deepcopy(setup)
    assert _PhysicalSetupDisplay.setup(setup) == setup
    assert not _PhysicalSetupDisplay.identifiers(ordered_history)
    page, console = render(setup)
    for rendered in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in rendered
        assert "Saved assessment verdict: BLOCKED" in panel(rendered)
        assert "not additional evidence files" in rendered
    count, unique = len(ordered_history), len(set(ordered_history))
    assert f"{count} retained reference occurrences ({unique} unique IDs)" in page
    assert f'"evidence_reference_occurrence_count": {count}' in console
    assert f'"unique_evidence_id_count": {unique}' in console
    assert setup == original


@pytest.mark.parametrize(
    "references",
    [
        ["evidence-" + RECEIPT] * 257,
        ["evidence-" + RECEIPT, 1],
        ["evidence-" + RECEIPT, "unsafe/reference"],
        ["evidence-" + RECEIPT, "x" * 97],
    ],
)
def test_stage_reference_sequence_keeps_existing_item_and_count_bounds(
    complete_setup, references
):
    setup = modeled(complete_setup, reviewed=True)
    setup["session"]["stages"][0]["evidence_ids"] = references
    assert _PhysicalSetupDisplay.setup(setup) is None
    for rendered in render(setup):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" in rendered


def test_actual_two_launch_export_with_accumulated_evidence_history():
    """Exact local export; optional on machines without this preserved run."""
    from rocell.application.wizard_diagnostic_export import verify_export

    directory = (
        Path(__file__).resolve().parents[3]
        / "software/runs/wizard-exports"
        / "wizard-20260908T162558337607Z-0052699bacce42e3b115a3d1603c7ba7"
    )
    report = directory / "report.json"
    if not report.exists():
        pytest.skip("Original two-launch source-workflow export is not installed")
    raw = report.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "0b70ea70b1b1003501a827bdf6f93f99a1b4071c9907d265ca5f3bbc43395b89"
    )
    assert verify_export(directory)["valid"] is True
    view = json.loads(raw)["snapshot"]
    assert view["source_binding_sha256"] == (
        "129c50e767be3cc0ad6e852ad3f04d260e65999af135d6f60ef10ae8d647d94b"
    )
    original = deepcopy(view)
    setup = view["physical_camera_setup"]
    assert setup["origin_launch_id"] != setup["launch_session_id"]
    assert setup["requirements_provenance"] == "REOPENED_ORIGINAL_CONTEXT"
    stages = setup["session"]["stages"]
    assert stages[0]["state"] == "BLOCKED"
    assert all(row["state"] == "PENDING" for row in stages[1:])
    references = stages[0]["evidence_ids"]
    assert len(references) == 5 and len(set(references)) == 3
    assert references[:2] == references[2:4]
    assert _PhysicalSetupDisplay.setup(setup) == setup
    page, console = render_snapshot(view)
    assert "5 retained reference occurrences (3 unique IDs)" in page
    assert '"evidence_reference_occurrence_count": 5' in console
    assert '"unique_evidence_id_count": 3' in console
    for rendered in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in rendered
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in rendered
        text = panel(rendered)
        assert "Saved assessment verdict: BLOCKED" in text
        assert "Original workspace_sources stage: BLOCKED" in text
        for role, key in (
            ("receipt", "receipt_sha256"),
            ("assessment", "assessment_sha256"),
            ("review", "review_sha256"),
        ):
            assert setup["source_workflow"][role][key] in text
        assert "PHYSICAL ACCEPTANCE BLOCKED" in text
    assert view == original
    assert report.read_bytes() == raw
    assert verify_export(directory)["valid"] is True


@pytest.mark.parametrize("reviewed", [False, True])
@pytest.mark.parametrize("failed_software", [False, True])
def test_saved_software_facts_and_physical_gaps_are_distinct(
    complete_setup, reviewed, failed_software
):
    setup = modeled(complete_setup, reviewed=reviewed, failed_software=failed_software)
    original = deepcopy(setup)
    assert _PhysicalSetupDisplay.setup(setup) == setup
    assert (
        _WorkspaceSourceDisplay.projection(setup["source_workflow"], setup)
        == setup["source_workflow"]
    )
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        assert "Saved assessment verdict: BLOCKED" in text
        assert (
            "PHYSICAL ACCEPTANCE BLOCKED" in text
            and "power observation: UNKNOWN" in text
        )
        assert "controlled_build_sources: SOFTWARE_CHECK_PASSED" in text
        assert (
            "base_software_ready: "
            + ("SOFTWARE_CHECK_BLOCKED" if failed_software else "SOFTWARE_CHECK_PASSED")
            in text
        )
        assert "source_operator_é" in text
        for reason in MISSING:
            assert reason in text
        assert ("SOFTWARE_PREREQUISITES_NOT_READY" in text) is failed_software
        if reviewed:
            assert "source_reviewer_é" in text and REVIEW in text
            assert "Original workspace_sources stage: BLOCKED" in text
            assert "not authenticated independent people" in text
        else:
            assert "Original stage is REVIEW_PENDING" in text
            assert "no control can change it to PASS" in text
    assert setup == original


def test_reopen_preserves_original_collection_review_and_current_launch(complete_setup):
    setup = modeled(complete_setup, reviewed=True, reopened=True)
    original = setup["origin_launch_id"]
    current = setup["launch_session_id"]
    assert original != current
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        assert f"Current application launch: {current}" in text
        assert f"Collection launch: {original}" in text
        assert f"review launch: {original}" in text
        assert "Stored authorship is not rewritten on reopen" in text


@pytest.mark.parametrize("state", ["absent", "null", "NOT_STARTED", "HISTORICAL_HELD"])
def test_initial_or_legacy_state_does_not_infer_receipt(complete_setup, state):
    setup = version_two(complete_setup)
    if state != "absent":
        setup["source_workflow"] = (
            None
            if state == "null"
            else {
                "schema": "rocell.wizard_workspace_source_workflow.v1",
                "status": state,
                "receipt": None,
                "assessment": None,
                "review": None,
                **FLAGS,
            }
        )
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        assert "Saved assessment verdict:" not in text
        assert (
            "no receipt or review is inferred" in text
            or "No saved source receipt" in text
            or "Historical original source evidence" in text
        )


@pytest.mark.parametrize("kept", ["receipt", "assessment", "review"])
def test_historical_partial_evidence_is_not_a_current_commit(complete_setup, kept):
    setup = modeled(complete_setup, reviewed=True)
    setup["source_workflow"]["status"] = "HISTORICAL_HELD"
    if kept != "review":
        setup["source_workflow"]["review"] = None
    if kept == "receipt":
        setup["source_workflow"]["assessment"] = None
    setup["publication"]["status"] = "HISTORICAL_HELD"
    setup["prerequisites"] = None
    setup["requirements_provenance"] = "NONE"
    setup["session"].update(status="HELD", verification=None, stages=None)
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in text
        assert "Historical original source evidence only" in text
        assert "Original workspace_sources stage: BLOCKED" not in text
        assert RECEIPT in text


def test_pending_publication_hides_even_completed_inner_subjects(complete_setup):
    setup = modeled(complete_setup, reviewed=True)
    setup["publication"]["status"] = "PENDING"
    setup["prerequisites"] = None
    setup["requirements_provenance"] = "NONE"
    for rendered in render(setup):
        text = panel(rendered)
        assert "Source-stage publication pending" in text
        assert RECEIPT not in text and "source_operator_é" not in text
        assert "Saved assessment verdict:" not in text


@pytest.mark.parametrize(
    "mutation",
    [
        lambda w: w.update(extra="RAW_SENTINEL"),
        lambda w: w.update(physical_authority=True),
        lambda w: w.update(canonical_stage_pass=0),
        lambda w: w.update(device_io_performed="false"),
        lambda w: w.update(power_state="DISCONNECTED"),
        lambda w: w.update(status="PASS"),
        lambda w: w.update(receipt=None),
        lambda w: w.update(assessment=None),
        lambda w: w["receipt"].update(raw_payload="RAW_SENTINEL"),
        lambda w: w["receipt"].update(source_file_count=129),
        lambda w: w["receipt"].update(foundation_contract_count=True),
        lambda w: w["receipt"].update(host_blocker_count=65),
        lambda w: w["receipt"]["software_checks"][0].update(passed=False),
        lambda w: w["receipt"]["software_checks"][1].update(passed=1),
        lambda w: w["receipt"]["software_checks"][3].update(check_id="unknown"),
        lambda w: w["receipt"]["binding"].update(operator_id="RAW_SENTINEL\x1b[31m"),
        lambda w: w["receipt"]["binding"].update(operator_id="é" * 65),
        lambda w: w["receipt"]["binding"].update(source_sha256="g" * 64),
        lambda w: w["assessment"].update(verdict="PASS"),
        lambda w: w["assessment"].update(receipt_sha256="f" * 64),
        lambda w: w["assessment"].update(missing_requirements=[]),
        lambda w: w["assessment"].update(
            missing_requirements=[*MISSING, "SOFTWARE_PREREQUISITES_NOT_READY"]
        ),
        lambda w: w["assessment"]["software_checks"][3].update(passed=False),
        lambda w: w["assessment"]["binding"].update(collection_launch_id="other"),
        lambda w: w["review"].update(assessment_sha256="f" * 64),
        lambda w: w["review"].update(authenticated_independent_people=True),
        lambda w: w["review"].update(distinct_operator_labels=False),
        lambda w: w["review"].update(reviewer_id="source_operator_é"),
        lambda w: w["review"].update(review_sha256="a" * 63),
        lambda w: w["review"].update(verdict="PASS"),
    ],
)
def test_malformed_or_authority_claiming_subjects_are_withheld(
    complete_setup, mutation
):
    setup = modeled(complete_setup, reviewed=True)
    mutation(setup["source_workflow"])
    assert _WorkspaceSourceDisplay.projection(setup["source_workflow"], setup) is None
    for rendered in render(setup):
        text = panel(rendered)
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" in text
        assert "Saved assessment verdict:" not in text and "RAW_SENTINEL" not in text


@pytest.mark.parametrize(
    "key",
    [
        "source_sha256",
        "session_id",
        "origin_launch_id",
        "header_sha256",
        "prerequisites_sha256",
    ],
)
def test_internally_consistent_subjects_must_match_the_original_store(
    complete_setup, key
):
    setup = modeled(complete_setup, reviewed=True)
    for role in ("receipt", "assessment", "review"):
        setup["source_workflow"][role]["binding"][key] = (
            "f" * 64 if key.endswith("sha256") else "other-original"
        )
    for rendered in render(setup):
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" in panel(rendered)


@pytest.mark.parametrize("state", ["PENDING", "WAITING_OPERATOR", "PASS"])
def test_reviewed_projection_requires_original_blocked_commit(complete_setup, state):
    setup = modeled(complete_setup, reviewed=True)
    setup["session"]["stages"][0]["state"] = state
    for rendered in render(setup):
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" in panel(rendered)


def test_cached_terminal_has_no_file_or_m1_calls(complete_setup, monkeypatch):
    setup = modeled(complete_setup, reviewed=True)
    output = []
    renderer = _TerminalWizard(
        Service([]), lambda _: "quit", output.append, lambda _: None
    )

    def forbidden(*_a, **_k):
        pytest.fail("Cached source workflow attempted file or process I/O")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "read_text", "read_bytes"):
            guard.setattr(Path, name, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        renderer.show_workspace_source_workflow(setup)
    assert any("ACKNOWLEDGED_BLOCKED" in str(line) for line in output)


@pytest.mark.parametrize("review", [False, True])
def test_generic_source_actions_preview_only_with_explicit_consent(
    complete_setup, review
):
    from rocell.application.wizard_actions import ACTION_BY_ID

    name = (
        "physical_camera_review_sources" if review else "physical_camera_assess_sources"
    )
    actor = "reviewer_id" if review else "operator_id"
    definition = ACTION_BY_ID[name]
    assert (
        definition.mode == "physical" and definition.worker == "physical_camera_setup"
    )
    assert [field["name"] for field in definition.fields] == [actor, "file_only"]
    assert "default" not in definition.fields[0]
    assert definition.fields[1].get("default", False) is False
    item = action(name, fields=list(definition.fields))
    item["section"] = "camera"
    view = snapshot(modeled(complete_setup))
    view["actions"] = [item]
    for consent in (False, True):
        page = browser(
            selection(),
            "camera",
            snapshot=view,
            prepare=True,
            action=name,
            values={actor: "literal_actor", "file_only": consent},
        )
        assert [r["path"] for r in page["requests"]] == ["/api/view"] + (
            ["/api/prepare"] if consent else []
        )
        assert not any(r["path"] == "/api/execute" for r in page["requests"])
    service = Service([item])
    code, _, _ = run(
        service, [name, "literal_actor", "yes", "yes to all hardware", "quit"]
    )
    assert (
        code == 0
        and len(dispatched(service, "prepare")) == 1
        and not dispatched(service, "execute")
    )
