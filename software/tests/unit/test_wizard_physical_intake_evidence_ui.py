"""Real pure intake codecs -> cached renderers; modeled audited M1 context.

Observed values, references and storage state are explicitly test models, not
received-hardware or durability proof. Rendering uses GET/view only, no service
construction, attachment IO, discovery, submission, review or device activity.
"""

from copy import deepcopy
from threading import RLock
from types import SimpleNamespace

import pytest

from rocell.ui.terminal import (
    _PhysicalIntakeEvidenceDisplay,
    _PhysicalSetupDisplay,
    _WorkspaceSourceDisplay,
)
from test_physical_configuration_epochs import epoch_fixture
from test_physical_intake_submission import intake_fixture
from test_wizard_physical_camera_epochs_ui import setup as epoch_setup
from test_wizard_workspace_source_ui import modeled, snapshot, render_snapshot


@pytest.fixture(
    scope="module", params=[False, True], ids=["unknown", "modeled-observed"]
)
def produced(request):
    return intake_fixture(observed=request.param)


def fixture_view(tmp_path, produced, state="REVIEWED_BLOCKED"):
    setup = modeled(epoch_setup(tmp_path, epoch_fixture()), reviewed=True)
    setup["schema"] = "rocell.wizard_physical_camera_setup.v3"
    c = {
        "collection_id": produced.submission.to_dict()["collection_id"],
        "state": state,
        "submission": produced.submission.safe_summary(),
        "assessment": produced.assessment.safe_summary(),
        "review": produced.review.safe_summary(),
    }
    canonical = {
        "INCOMPLETE": "WAITING_OPERATOR",
        "REVIEW_PENDING": "REVIEW_PENDING",
        "REVIEW_RETAINED_NOT_COMMITTED": "REVIEW_PENDING",
        "REVIEWED_BLOCKED": "BLOCKED",
    }[state]
    if state == "REVIEW_PENDING":
        c["review"] = None
    if state == "INCOMPLETE":
        c.update(submission=None, assessment=None, review=None)
    setup["source_workflow"].update(
        schema="rocell.wizard_workspace_source_workflow.v2",
        original_source_state="BLOCKED",
        supplementary={"collection_id": c["collection_id"], "state": canonical},
    )
    setup["session"]["stages"][0]["state"] = canonical
    view = snapshot(setup)
    b = produced.submission.safe_summary()["binding"]
    view["physical_intake_evidence"] = {
        "schema": "rocell.wizard_physical_intake_evidence.v1",
        "source_sha256": setup["source_sha256"],
        "launch_session_id": setup["launch_session_id"],
        "original_context": {k: b[k] for k in _PhysicalIntakeEvidenceDisplay.CONTEXT},
        "publication": {"status": "CURRENT", "operation_id": "intake-operation"},
        "status": {
            "INCOMPLETE": "INCOMPLETE_HELD",
            "REVIEW_PENDING": "SUBMITTED_REVIEW_PENDING",
            "REVIEW_RETAINED_NOT_COMMITTED": "INCOMPLETE_HELD",
            "REVIEWED_BLOCKED": "REVIEWED",
        }[state],
        "discovery": {
            "schema": "rocell.physical_intake_inbox.v1",
            "status": "NOT_DISCOVERED",
            "directory": setup["session"]["binding"]["workspace"]
            + "/software/runs/physical-intake-inbox",
            "source_sha256": setup["source_sha256"],
            "launch_session_id": setup["launch_session_id"],
            "discovery_sha256": None,
            "files": [],
            "issues": [],
            "physical_authority": False,
            "device_io_performed": False,
        },
        "collection": c,
        "collection_count": 1,
        "physical_authority": False,
        "hardware_qualified": False,
        "meaning": "Cached original-subject metadata only; no physical acceptance.",
    }
    return view


def panel(text):
    return text.split("Retained passive intake evidence", 1)[1].split(
        "Physical camera acquisition", 1
    )[0]


def assert_valid(view):
    assert _PhysicalSetupDisplay.setup(view["physical_camera_setup"]) is not None
    assert (
        _PhysicalIntakeEvidenceDisplay.projection(
            view["physical_intake_evidence"], view
        )
        == view["physical_intake_evidence"]
    )
    before = deepcopy(view)
    outputs = render_snapshot(view)
    assert view == before
    for output in outputs:
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in output
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in output
        assert "PHYSICAL_INTAKE_EVIDENCE_NOT_VERIFIED" not in output
    return tuple(panel(output) for output in outputs)


def test_actual_pure_submission_assessment_review_to_both_renderers(tmp_path, produced):
    view = fixture_view(tmp_path, produced)
    for output in assert_valid(view):
        assert produced.submission.sha256 in output
        assert produced.assessment.sha256 in output
        assert produced.review.sha256 in output
        assert "BYTES / PROCEDURAL REVIEW ONLY" in output
        assert "The source verdict remains BLOCKED" in output
        assert "INT-005 acceptance stays deferred" in output
        assert "not redacted" in output
        assert "not authenticated people" in output
        assert "Reviewer_B" in output
        for row in produced.submission.safe_summary()["rows"]:
            assert f"{row['record_id']}: {row['measurement']}" in output
            assert row["observed_value"] in output
            assert row["method"] in output
        assert ("Retained original:" in output) == bool(
            produced.submission.safe_summary()["attachments"]
        )
    assert (
        view["physical_intake_evidence"]["collection"]["submission"]["rows"][4][
            "acceptance_status"
        ]
        == "DEFERRED_LIMIT"
    )


def test_actual_evidence_service_cached_projection_to_both_renderers(
    tmp_path, produced
):
    from rocell.application.physical_intake_evidence_service import (
        PhysicalIntakeEvidenceService,
    )

    view = fixture_view(tmp_path, produced)
    base = view["physical_intake_evidence"]
    setup = view["physical_camera_setup"]
    # Actual production .view() over an explicitly modeled original-reader
    # cache. No constructor, original-store read, inbox operation or codec
    # acquisition is invoked; pure full documents come from the real producer.
    service = object.__new__(PhysicalIntakeEvidenceService)
    service._lock = RLock()
    service.source_sha256 = base["source_sha256"]
    service.launch_id = base["launch_session_id"]
    service.setup = SimpleNamespace(
        view=lambda: deepcopy(setup),
        session=SimpleNamespace(
            descriptor=lambda: {"cell_id": base["original_context"]["cell_id"]}
        ),
    )
    service._publication = deepcopy(base["publication"])
    service._discovery_published = False
    service._empty_discovery = deepcopy(base["discovery"])
    service._workflow = {
        "binding": deepcopy(setup["session"]["binding"]),
        "session_header_sha256": base["original_context"]["header_sha256"],
        "prerequisites": {
            "document": produced.prerequisites.to_dict(),
            "evidence_sha256": produced.prerequisites.evidence_sha256,
        },
        "intake_collections": [
            {
                "collection_id": base["collection"]["collection_id"],
                "state": "REVIEWED_BLOCKED",
                **{
                    role: {"document": getattr(produced, role).to_dict()}
                    for role in ("submission", "assessment", "review")
                },
            }
        ],
    }
    view["physical_intake_evidence"] = service.view()
    for output in assert_valid(view):
        assert produced.submission.sha256 in output
        assert "Reviewer_B" in output


def test_empty_historical_discovery_is_held_not_current(tmp_path, produced):
    view = fixture_view(tmp_path, produced)
    discovery(view)
    value = view["physical_intake_evidence"]
    value.update(status="NOT_STARTED", collection=None, collection_count=0)
    value["publication"]["status"] = "HISTORICAL_HELD"
    for output in assert_valid(view):
        assert "HISTORICAL ONLY" in output


@pytest.mark.parametrize(
    "state",
    [
        "INCOMPLETE",
        "REVIEW_PENDING",
        "REVIEW_RETAINED_NOT_COMMITTED",
        "REVIEWED_BLOCKED",
    ],
)
def test_supplementary_canonical_state_never_replaces_original_source_verdict(
    tmp_path, produced, state
):
    view = fixture_view(tmp_path, produced, state)
    assert_valid(view)
    for output in render_snapshot(view):
        assert "Original source assessment/review remains BLOCKED" in output
        assert "This is a different subject" in output
        if state in ("INCOMPLETE", "REVIEW_RETAINED_NOT_COMMITTED"):
            assert "not a committed review" in output


def test_pending_withholds_all_new_subjects_and_discovery(tmp_path, produced):
    view = fixture_view(tmp_path, produced)
    value = view["physical_intake_evidence"]
    value.update(status="HISTORICAL_HELD", collection=None)
    value["publication"]["status"] = "PENDING"
    for output in assert_valid(view):
        assert "Publication pending" in output
        assert produced.submission.sha256 not in output
        assert "Assigned inbox — explicit discovery only" not in output


def test_initial_absence_is_readable_and_does_not_start_work(tmp_path, produced):
    view = fixture_view(tmp_path, produced)
    value = view["physical_intake_evidence"]
    value.update(
        status="NOT_STARTED", collection=None, collection_count=0, original_context=None
    )
    value["publication"] = {"status": "NOT_PUBLISHED", "operation_id": None}
    for output in assert_valid(view):
        assert "No published collection" in output
    view.pop("physical_intake_evidence")
    for output in render_snapshot(view):
        assert "No retained intake projection" in output


def test_historical_original_subjects_need_no_current_draft_or_setup_prerequisites(
    tmp_path, produced
):
    view = fixture_view(tmp_path, produced)
    value = view["physical_intake_evidence"]
    value.update(status="HISTORICAL_HELD")
    value["publication"]["status"] = "HISTORICAL_HELD"
    # No current notebook exists after restart. Original retained summary does
    # not silently rebind its submission launch to this new application launch.
    view["session_id"] = "wizard-new-reader"
    view["physical_intake"] = None
    for output in assert_valid(view):
        assert "HISTORICAL ONLY" in output
        assert (
            produced.submission.safe_summary()["binding"]["submission_launch_id"]
            in output
        )


def discovery(view, count=1):
    value = view["physical_intake_evidence"]
    value["status"] = "DISCOVERED"
    d = value["discovery"]
    d.update(
        status="READY",
        discovery_sha256="b" * 64,
        files=[
            {
                "choice_id": f"intake-file-{i:032x}",
                "basename": f"input_{i}.txt",
                "media_type": "text/plain",
                "payload_bytes": 12,
                "payload_sha256": "c" * 64,
            }
            for i in range(count)
        ],
    )
    return d


@pytest.mark.parametrize("count", [0, 1, 32])
def test_bounded_discovery_can_include_refusals_without_inferred_selection(
    tmp_path, produced, count
):
    view = fixture_view(tmp_path, produced)
    d = discovery(view, count)
    d["issues"] = [{"code": "INTAKE_INBOX_FILE_TYPE", "basename": "unsupported.exe"}]
    for output in assert_valid(view):
        assert "INTAKE_INBOX_FILE_TYPE" in output
        assert "does not read files or submit automatically" in output
        assert "intake-file-" not in output  # Opaque tokens belong only to forms.


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("physical_authority",), True),
        (("publication", "status"), "PASS"),
        (("collection_count",), True),
        (("original_context", "header_sha256"), "f" * 64),
        (("original_context", "source_sha256"), "f" * 64),
        (("collection", "submission", "binding", "session_id"), "other-session"),
        (("collection", "submission", "binding", "source_binding_sha256"), "f" * 64),
        (("collection", "submission", "coverage", "unknown"), True),
        (("collection", "submission", "rows", 0, "observed_value"), "raw\ntext"),
        (("collection", "submission", "rows", 0, "method"), "x" * 513),
        (("collection", "submission", "rows", 0, "measurement"), "changed question"),
        (("collection", "submission", "rows", 4, "acceptance_status"), "NOT_ASSESSED"),
        (
            ("collection", "submission", "rows", 0, "attachment_evidence_id"),
            "unknown-evidence",
        ),
        (("collection", "assessment", "physical_readiness"), True),
        (("collection", "assessment", "submission_sha256"), "f" * 64),
        (("collection", "review", "reviewer_id"), "operator_a"),
        (("collection", "review", "assessment_sha256"), "f" * 64),
        (("collection", "review", "authenticated_independent_people"), True),
        (("collection", "review", "status"), "APPROVED"),
        (("discovery", "directory"), "C:/private/other-folder"),
        (("discovery", "issues"), [{"code": "UNRECOGNIZED", "basename": None}]),
    ],
)
def test_tampered_projection_is_withheld_without_raw_fallback(
    tmp_path, produced, path, replacement
):
    view = fixture_view(tmp_path, produced)
    row = view["physical_intake_evidence"]
    for key in path[:-1]:
        row = row[key]
    row[path[-1]] = replacement
    assert (
        _PhysicalIntakeEvidenceDisplay.projection(
            view["physical_intake_evidence"], view
        )
        is None
    )
    for output in render_snapshot(view):
        text = panel(output)
        assert "PHYSICAL_INTAKE_EVIDENCE_NOT_VERIFIED" in text
        assert produced.submission.sha256 not in text


@pytest.mark.parametrize(
    "fault", ["too-many", "duplicate", "raw-path", "too-large", "unknown-key"]
)
def test_discovery_strict_rows_and_limits(tmp_path, produced, fault):
    view = fixture_view(tmp_path, produced)
    d = discovery(view, 33 if fault == "too-many" else 1)
    if fault == "duplicate":
        d["files"].append(deepcopy(d["files"][0]))
    if fault == "raw-path":
        d["files"][0]["basename"] = "../private.txt"
    if fault == "too-large":
        d["files"][0]["payload_bytes"] = 2 * 1024 * 1024 + 1
    if fault == "unknown-key":
        d["files"][0]["base64"] = "not-allowed"
    assert (
        _PhysicalIntakeEvidenceDisplay.projection(
            view["physical_intake_evidence"], view
        )
        is None
    )
    for output in render_snapshot(view):
        assert "PHYSICAL_INTAKE_EVIDENCE_NOT_VERIFIED" in panel(output)


def test_literal_narratives_preserve_underscores_and_markup_as_text(tmp_path, produced):
    view = fixture_view(tmp_path, produced)
    s = view["physical_intake_evidence"]["collection"]["submission"]
    s["rows"][0].update(
        status="UNKNOWN",
        observed_value="unknown_value <script>not_markup</script>",
        method="method_A & method_B",
    )
    if s["coverage"]["observed"]:
        s["coverage"].update(observed=15, unknown=1)
        a = view["physical_intake_evidence"]["collection"]["assessment"]
        a.update(
            coverage=deepcopy(s["coverage"]),
            observation_completeness="UNKNOWN_ROWS_REMAIN",
            unknown_record_ids=["INT-001"],
        )
    for output in assert_valid(view):
        assert "unknown_value <script>not_markup</script>" in output
        assert "method_A & method_B" in output


def test_source_v2_pending_null_does_not_fabricate_old_review(tmp_path, produced):
    view = fixture_view(tmp_path, produced)
    setup = view["physical_camera_setup"]
    setup["publication"]["status"] = "PENDING"
    setup.update(prerequisites=None, requirements_provenance="NONE")
    setup["configuration_records"].update(status="NOT_RETAINED", summary=None)
    source = setup["source_workflow"]
    source.update(
        status="NOT_STARTED",
        receipt=None,
        assessment=None,
        review=None,
        supplementary=None,
    )
    assert _WorkspaceSourceDisplay.projection(source, setup) == source
    for output in render_snapshot(view):
        assert "Source-stage publication pending" in output
