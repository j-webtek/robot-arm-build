"""Draft-only pure contract; fixture reads source requirements, never hardware."""

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application import physical_intake_notebook as module
from rocell.application.physical_camera_prerequisites import PhysicalCameraPrerequisites
from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
from test_physical_camera_prerequisites import collect, workspace

CURRENT = "wizard-current-fixture"


@pytest.fixture
def notebook(workspace):
    return module.PhysicalIntakeNotebook.start(
        collect(workspace), launch_session_id=CURRENT
    )


def record(notebook, **changes):
    fields = dict(
        record_id="INT-001",
        observation_status="UNKNOWN",
        observed_value="Hardware not received",
        method="Not measured",
        evidence_note="Not supplied",
        operator_id="draft-operator",
        recorded_at_ns=1,
    )
    fields.update(changes)
    return notebook.record(**fields)


def test_start_derives_exact_original_questions_without_values(notebook):
    view = notebook.view()
    assert view["schema"] == module.SCHEMA
    assert view["revision"] == 0 and view["previous_sha256"] is None
    assert view["snapshot_sha256"] == notebook.sha256
    assert view["coverage"] == dict(total=16, observed=0, unknown=0, unrecorded=16)
    assert view["binding"]["launch_session_id"] == CURRENT
    assert view["binding"]["origin_launch_id"] != CURRENT
    originals = next(
        row
        for row in notebook._prerequisites.to_dict()["requirements"]["stages"]
        if row["stage"] == "camera_receipt"
    )["intake_rows"]
    assert view["rows"] == originals
    assert all(row["observation"] is None for row in view["rows"])
    assert len(notebook.choices()) == 16
    assert "INT-018" not in {row["value"] for row in notebook.choices()}
    assert all(view[name] is False for name in module._FALSE)


def test_record_revise_and_restore_are_immutable(notebook):
    first = record(notebook)
    second = record(
        first,
        observation_status="OBSERVED",
        observed_value="610.00",
        method="Modeled unit-test example",
        recorded_at_ns=2,
    )
    assert first.to_dict()["coverage"] == dict(
        total=16, observed=0, unknown=1, unrecorded=15
    )
    assert second.to_dict()["coverage"] == dict(
        total=16, observed=1, unknown=0, unrecorded=15
    )
    assert second.to_dict()["previous_sha256"] == first.sha256
    assert first.to_dict()["previous_sha256"] == notebook.sha256
    assert notebook.to_dict()["revision"] == 0
    restored = module.PhysicalIntakeNotebook.from_payload(
        second.payload,
        prerequisites=notebook._prerequisites,
        expected_sha256=second.sha256,
    )
    assert restored.payload == second.payload
    detached = restored.view()
    detached["rows"][0]["observation"]["observed_value"] = "changed"
    assert restored.to_dict()["rows"][0]["observation"]["observed_value"] == "610.00"
    with pytest.raises(FrozenInstanceError):
        restored.payload = b"{}"


@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "-1",
        "+1",
        "1e3",
        "1E3",
        "NaN",
        "nan",
        "Infinity",
        ".5",
        "1.",
        "1,000",
        "1 mm",
        " 1",
        "1 ",
        "",
        "\n1",
        "1\x00",
        "١٢",
    ],
)
def test_invalid_dimension_decimals_never_become_observations(notebook, raw):
    with pytest.raises(module.PhysicalIntakeNotebookError):
        record(notebook, observation_status="OBSERVED", observed_value=raw)
    assert notebook.to_dict()["coverage"]["unrecorded"] == 16


def test_explicit_relaunch_revision_preserves_observation_provenance(notebook):
    original = record(notebook, recorded_at_ns=123, operator_id="original-recorder")
    revised = original.revise_for_launch(launch_session_id="wizard-next-launch")
    assert revised.to_dict()["rows"] == original.to_dict()["rows"]
    assert revised.to_dict()["revision"] == original.to_dict()["revision"] + 1
    assert revised.to_dict()["previous_sha256"] == original.sha256
    assert revised.to_dict()["binding"]["launch_session_id"] == "wizard-next-launch"
    for key in (
        "source_sha256",
        "session_id",
        "origin_launch_id",
        "prerequisites_sha256",
    ):
        assert revised.to_dict()["binding"][key] == original.to_dict()["binding"][key]
    assert original.to_dict()["binding"]["launch_session_id"] == CURRENT


def test_explicit_blank_relaunch_never_invents_an_observation_revision(notebook):
    revised = notebook.revise_for_launch(launch_session_id="wizard-next-launch")
    assert revised.to_dict()["revision"] == 0
    assert revised.to_dict()["previous_sha256"] is None
    assert revised.to_dict()["rows"] == notebook.to_dict()["rows"]


@pytest.mark.parametrize("launch", ["", "../other", None, "bad launch"])
def test_explicit_relaunch_rejects_invalid_binding(notebook, launch):
    with pytest.raises(module.PhysicalIntakeNotebookError):
        notebook.revise_for_launch(launch_session_id=launch)


def test_explicit_relaunch_respects_existing_revision_budget(notebook):
    for _ in range(module.MAX_REVISIONS):
        notebook = record(notebook)
    with pytest.raises(module.PhysicalIntakeNotebookError):
        notebook.revise_for_launch(launch_session_id="wizard-next-launch")


def test_flatness_zero_does_not_accept_its_deferred_limit(notebook):
    draft = record(
        notebook,
        record_id="INT-005",
        observation_status="OBSERVED",
        observed_value="0.000",
    )
    row = next(row for row in draft.to_dict()["rows"] if row["record_id"] == "INT-005")
    assert row["acceptance"] == {
        "status": "DEFERRED_LIMIT",
        "owner_stage": "noncontact_acceptance",
        "prerequisites": ["TARGET_ACCURACY_BUDGET_CLOSED"],
        "measurement_required": True,
    }
    assert draft.to_dict()["canonical_stage_pass"] is False


@pytest.mark.parametrize(
    "field,limit",
    [
        ("observed_value", 256),
        ("method", 512),
        ("evidence_note", 1024),
        ("operator_id", 64),
    ],
)
def test_every_narrative_field_has_nonempty_utf8_byte_limit(notebook, field, limit):
    assert record(notebook, **{field: "x" * limit})
    for invalid in (
        "",
        " ",
        "x" * (limit + 1),
        "é" * (limit // 2 + 1),
        "x\n",
        "x\u200by",
        None,
        True,
    ):
        with pytest.raises(module.PhysicalIntakeNotebookError):
            record(notebook, **{field: invalid})


@pytest.mark.parametrize(
    "changes",
    [
        dict(observation_status="PASS"),
        dict(observation_status="NA"),
        dict(record_id="INT-018"),
        dict(record_id=True),
        dict(recorded_at_ns=True),
        dict(recorded_at_ns=0),
        dict(recorded_at_ns=-1),
        dict(recorded_at_ns=2**63),
        dict(recorded_at_ns=1.0),
    ],
)
def test_no_approval_status_or_invalid_record_time(notebook, changes):
    with pytest.raises(module.PhysicalIntakeNotebookError):
        record(notebook, **changes)


def test_unknown_never_counts_as_observed_complete_coverage(notebook):
    current = notebook
    for index, choice in enumerate(notebook.choices()):
        current = record(current, record_id=choice["value"], recorded_at_ns=index + 1)
    assert current.to_dict()["coverage"] == dict(
        total=16, observed=0, unknown=16, unrecorded=0
    )
    assert all(current.to_dict()[name] is False for name in module._FALSE)


def test_revision_limit_preserves_original_snapshot(notebook):
    current = notebook
    for index in range(128):
        current = record(current, recorded_at_ns=index + 1)
    original = current.payload
    with pytest.raises(module.PhysicalIntakeNotebookError) as caught:
        record(current, recorded_at_ns=129)
    assert caught.value.code == "REVISION_LIMIT"
    assert current.payload == original


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "source",
        "session",
        "origin",
        "prerequisites",
        "question",
        "acceptance",
        "coverage",
        "authority",
        "attachment",
        "revision",
        "previous",
        "status",
        "viewhash",
    ],
)
def test_tampered_snapshot_rejected_even_with_recomputed_outer_hash(notebook, change):
    first = record(notebook)
    data = first.to_dict()
    if change == "extra":
        data["approved"] = True
    elif change in {"source", "session", "origin", "prerequisites"}:
        field = {
            "source": "source_sha256",
            "session": "session_id",
            "origin": "origin_launch_id",
            "prerequisites": "prerequisites_sha256",
        }[change]
        data["binding"][field] = "f" * 64
    elif change == "question":
        data["rows"][0]["candidate_or_requirement"] = "changed"
    elif change == "acceptance":
        data["rows"][0]["acceptance"]["status"] = "PASS"
    elif change == "coverage":
        data["coverage"]["unknown"] = True
    elif change == "authority":
        data["physical_authority"] = 0
    elif change == "attachment":
        data["attachment_bytes_verified"] = True
    elif change == "revision":
        data["revision"] = 0
    elif change == "previous":
        data["previous_sha256"] = None
    elif change == "status":
        data["rows"][0]["observation"]["status"] = "PASS"
    else:
        data["snapshot_sha256"] = first.sha256
    payload = module._canonical(data)
    with pytest.raises(module.PhysicalIntakeNotebookError):
        module.PhysicalIntakeNotebook.from_payload(
            payload,
            prerequisites=notebook._prerequisites,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )


def test_wrong_trusted_hash_and_prerequisite_type_refused(notebook):
    with pytest.raises(module.PhysicalIntakeNotebookError) as caught:
        module.PhysicalIntakeNotebook.from_payload(
            notebook.payload,
            prerequisites=notebook._prerequisites,
            expected_sha256="f" * 64,
        )
    assert caught.value.code == "HASH_MISMATCH"
    for value in ({}, notebook._prerequisites.to_dict(), None):
        with pytest.raises(module.PhysicalIntakeNotebookError):
            module.PhysicalIntakeNotebook.start(value, launch_session_id=CURRENT)


def test_complete_public_result_and_export_wrapper_remain_lossless(notebook):
    current = record(notebook)
    result = {
        "steps": [
            {
                "name": "physical_intake_record",
                "exit_code": 0,
                "report": {"notebook": current.view()},
            }
        ],
        "physical_authority": False,
    }
    assert sanitize_diagnostic_record(result) == result
    export = {
        "schema": "rocell.physical_intake_export.v1",
        "status": "CURRENT_DRAFT",
        "notebook": current.view(),
        "snapshot_sha256": current.sha256,
    }
    assert sanitize_diagnostic_record(export) == export
    assert len(current.payload) < 32 * 1024
    assert len(json.dumps(result, indent=2).encode()) < 64 * 1024


def test_all_operations_are_pure_after_typed_requirements_exist(notebook, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Draft contract performed filesystem or device work")

    for name in ("open", "stat", "resolve", "iterdir", "read_bytes"):
        monkeypatch.setattr(Path, name, denied)
    fresh = module.PhysicalIntakeNotebook.start(
        notebook._prerequisites, launch_session_id=CURRENT
    )
    current = record(fresh)
    assert current.view() and current.choices()
    assert (
        module.PhysicalIntakeNotebook.from_payload(
            current.payload,
            prerequisites=notebook._prerequisites,
            expected_sha256=current.sha256,
        ).payload
        == current.payload
    )


def test_byte_limit_rejects_without_truncation(notebook, monkeypatch):
    monkeypatch.setattr(module, "MAX_NOTEBOOK_BYTES", len(notebook.payload))
    with pytest.raises(module.PhysicalIntakeNotebookError) as caught:
        record(notebook)
    assert caught.value.code == "BYTE_LIMIT"
    assert notebook.to_dict()["revision"] == 0
