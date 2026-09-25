"""Production-size codec/projection/export budgets, without physical activity.

The original inventory and published service caches are explicitly modeled.
Actual immutable intake codecs, service projections, Arrival action forms,
sanitizer and temporary-directory exporter are exercised. No M1 audit,
received-hardware observation, attachment acquisition or device call is made.
"""

from copy import deepcopy
import hashlib
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

import pytest

from rocell.application import physical_intake_submission as codec
from rocell.application import wizard_diagnostic_export as export
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.application.physical_intake_evidence_service import (
    PhysicalIntakeEvidenceService,
)
from rocell.application.physical_intake_inbox import PhysicalIntakeInbox
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.ui.terminal import _PhysicalIntakeEvidenceDisplay
from rocell.providers.windows.owned_worker_process import (
    OwnedWorkerError,
    decode_owned_json,
)
from test_arrival_wizard_service import _run, make_service  # noqa: F401
from test_physical_configuration_epochs import reference
from test_physical_intake_submission import canonical, intake_fixture
from test_wizard_physical_intake_evidence_ui import fixture_view


def _maximum_notebook(fixture, *, summary_heavy=False):
    """All field bounds filled; escaped text approaches the real 64 KiB cap."""
    original = fixture.notebook.to_dict()

    def candidate(escaped):
        value = deepcopy(original)
        for row in value["rows"]:
            row["observation"].update(
                observed_value="1" * 256 if row["unit"] in {"mm", "g"} else "V" * 256,
                method='"' * max(0, escaped - 1024)
                + "M" * (512 - max(0, escaped - 1024)),
                evidence_note='"' * min(1024, escaped)
                + "E" * (1024 - min(1024, escaped)),
                operator_id="O" * 64,
            )
            if summary_heavy:
                row["observation"].update(
                    observed_value=(
                        "1" * 256 if row["unit"] in {"mm", "g"} else "é" * 128
                    ),
                    method="é" * 256,
                    evidence_note="é" * escaped + "E" * (1024 - 2 * escaped),
                )
        return canonical(value)

    low, high = 0, 512 if summary_heavy else 1536
    while low < high:
        middle = (low + high + 1) // 2
        if len(candidate(middle)) <= 64 * 1024:
            low = middle
        else:
            high = middle - 1
    payload = candidate(low)
    notebook = PhysicalIntakeNotebook.from_payload(
        payload,
        prerequisites=fixture.prerequisites,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    assert 65472 <= len(payload) <= 65536
    return notebook


def maximum_case(*, collections, originals, summary_heavy=False):
    """Genuine codecs; modeled references with honest payload hash/length."""
    fixture = intake_fixture(observed=True)
    notebook = _maximum_notebook(fixture, summary_heavy=summary_heavy)
    # Five existing records: requirements, epochs and original source trio.
    inventory = [*fixture.snapshot.evidence]
    inventory.extend(
        reference(
            STAGE_ORDER[0], b"MODELED ORIGINAL SOURCE RECORD " + bytes([i]), salt=str(i)
        )
        for i in range(4)
    )
    raw = []
    for index in range(originals):
        payload = (b"MODELED ORIGINAL; NOT HARDWARE EVIDENCE\n" * 4096) + bytes([index])
        ref = reference(STAGE_ORDER[0], payload, salt="raw-" + str(index))
        inventory.append(ref)
        basename = f"{index:02d}-" + "a" * 88 + ".txt"  # actual inbox maximum: 95
        raw.append(codec.IntakeAttachment(ref, basename, "text/plain"))
    raw.sort(key=lambda attachment: attachment.reference.evidence_id)
    predecessor = None
    rows = []
    latest = None
    for number in range(1, collections + 1):
        if number > 1:
            old = notebook.to_dict()["rows"][-1]
            notebook = notebook.record(
                record_id=old["record_id"],
                observation_status="OBSERVED",
                observed_value="V" * 255 + str(number),
                method=old["observation"]["method"],
                evidence_note=old["observation"]["evidence_note"],
                operator_id="O" * 64,
                recorded_at_ns=number + 50,
            )
        collection_id = "intake-" + f"{number:032x}"
        submission = codec.build_physical_intake_submission(
            fixture.prerequisites,
            notebook,
            cell_id=fixture.snapshot.header.cell_id,
            header_sha256=fixture.snapshot.header.header_sha256,
            collection_id=collection_id,
            operator_id="O" * 64,
            submitted_at_ns=number * 100,
            attachments=tuple(raw),
            row_attachments=tuple(
                codec.IntakeRowAttachment(
                    row["record_id"], raw[index % originals].reference.evidence_id
                )
                for index, row in enumerate(notebook.to_dict()["rows"])
            ),
            evidence_inventory=tuple(
                sorted(inventory, key=lambda ref: ref.evidence_id)
            ),
            predecessor=predecessor,
        )
        assessment = codec.assess_physical_intake_submission(submission)
        review = codec.review_physical_intake_submission(
            submission,
            assessment,
            reviewer_id="R" * 64,
            review_launch_id="wizard-" + "f" * 32,
            reviewed_at_ns=number * 100 + 1,
            decision="ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
        )
        records = {}
        for role, artifact in (
            ("submission", submission),
            ("assessment", assessment),
            ("review", review),
        ):
            ref = reference(STAGE_ORDER[0], artifact.payload, salt=f"{number}-{role}")
            inventory.append(ref)
            records[role] = {
                "label": f"physical-intake-{role}-v1:{collection_id}",
                "document": artifact.to_dict(),
                "evidence_sha256": artifact.sha256,
                "retention": "M1_FULL_BYTES_READ_BACK",
                "reference": ref.to_dict(),
            }
        rows.append(
            {
                "collection_id": collection_id,
                "state": "REVIEWED_BLOCKED",
                "attachments": [
                    {
                        "label": "physical-intake-original-v1:intake-"
                        + f"{1:032x}:{index:02d}",
                        "index": index,
                        "media_type": attachment.media_type,
                        "evidence_sha256": attachment.reference.payload_sha256,
                        "retention": "M1_FULL_BYTES_READ_BACK",
                        "reference": attachment.reference.to_dict(),
                    }
                    for index, attachment in enumerate(raw)
                ],
                **records,
            }
        )
        predecessor = submission
        latest = SimpleNamespace(
            submission=submission, assessment=assessment, review=review
        )
    assert len(inventory) <= 32
    assert sum(ref.payload_bytes for ref in inventory) <= 4 * 1024 * 1024
    return SimpleNamespace(
        fixture=fixture,
        notebook=notebook,
        collections=rows,
        latest=latest,
        inventory=tuple(inventory),
        raw=raw,
    )


def cached_service(tmp_path, case, *, retain_attempt=True):
    """Only the audited upstream cache is modeled; production view code runs."""
    fixture = case.fixture
    service = object.__new__(PhysicalIntakeEvidenceService)
    service._lock = RLock()
    service.workspace = tmp_path
    service.source_sha256 = fixture.prerequisites.to_dict()["binding"]["source_sha256"]
    service.launch_id = "wizard-" + "f" * 32
    service.inbox = PhysicalIntakeInbox(
        tmp_path, launch_id=service.launch_id, source_sha256=service.source_sha256
    )
    service._empty_discovery = service.inbox.view()
    files = [
        {
            "choice_id": "intake-file-" + f"{i:032x}",
            "basename": f"{i:02d}-" + "a" * 88 + ".txt",
            "media_type": "text/plain",
            "payload_bytes": 512 * 1024,
            "payload_sha256": hashlib.sha256(str(i).encode()).hexdigest(),
        }
        for i in range(32)
    ]
    discovered = service.inbox.view()
    discovered.update(status="READY", files=files, discovery_sha256="b" * 64)
    service.inbox._cached = discovered
    service.inbox._choices = {row["choice_id"]: row for row in files}
    service._workflow = {
        "binding": {"cell_id": fixture.snapshot.header.cell_id},
        "session_header_sha256": fixture.snapshot.header.header_sha256,
        "prerequisites": {
            "document": fixture.prerequisites.to_dict(),
            "evidence_sha256": hashlib.sha256(
                fixture.prerequisites.payload
            ).hexdigest(),
        },
        "intake_collections": case.collections,
    }
    service._publication = {"status": "CURRENT", "operation_id": "budget-operation"}
    service._attempt = (
        {
            "collection_id": case.collections[-1]["collection_id"],
            "records": {
                role: deepcopy(case.collections[-1][role]) for role in ("review",)
            },
        }
        if retain_attempt
        else None
    )
    service._export_receipt = None
    service._discovery_published = True
    service.setup = SimpleNamespace(
        mode="physical",
        view=lambda: {"publication": {"status": "CURRENT"}},
        original_source_workflow=lambda: service._workflow,
        session=SimpleNamespace(retained_source_workflow=lambda: service._workflow),
    )
    return service


def metrics(value):
    def shape(item, depth=0):
        children = (
            item.values()
            if isinstance(item, dict)
            else item if isinstance(item, list) else ()
        )
        sizes = [shape(child, depth + 1) for child in children]
        return 1 + sum(size[0] for size in sizes), max(
            [depth, *(size[1] for size in sizes)]
        )

    nodes, depth = shape(value)
    return {
        "pretty_bytes": len(export._json_bytes(value)),
        "nodes": nodes,
        "depth": depth,
    }


@pytest.fixture(scope="module")
def maximum_single():
    return maximum_case(collections=1, originals=16, summary_heavy=True)


@pytest.fixture(scope="module")
def maximum_history():
    return maximum_case(collections=8, originals=3)


@pytest.mark.parametrize("case_name", ["maximum_single", "maximum_history"])
def test_actual_codec_service_metadata_budget(request, tmp_path, case_name):
    case = request.getfixturevalue(case_name)
    service = cached_service(tmp_path, case)
    value = service.retained_diagnostics()
    print(
        case_name,
        "notebook",
        len(case.notebook.payload),
        "refs",
        len(case.inventory),
        "original_bytes",
        sum(ref.payload_bytes for ref in case.inventory),
        "metadata",
        metrics(value),
    )
    assert export.sanitize_diagnostic_record(value, maximum_bytes=1024 * 1024) == value


@pytest.mark.parametrize("case_name", ["maximum_single", "maximum_history"])
def test_pending_summary_survives_exact_action_result_depth(
    request, tmp_path, case_name
):
    case = request.getfixturevalue(case_name)
    service = cached_service(tmp_path, case)
    projection = service.view()
    result = {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": "physical_intake_submit",
        "status": "SUCCEEDED",
        "steps": [
            {
                "name": "physical_intake_submit",
                "exit_code": 0,
                "report": {
                    **projection["collection"],
                    "collection_count": len(case.collections),
                },
            }
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }
    print(case_name, "pending", metrics(result))
    assert (
        export.sanitize_diagnostic_record(result, maximum_bytes=1024 * 1024) == result
    )


def published_arrival(make_service, monkeypatch, tmp_path, case):
    service, _, _ = make_service(mode="physical")
    intake = cached_service(tmp_path, case)
    # No upstream publication is performed. Only its already-validated cache
    # and original-context blocking decision are modeled for size inspection.
    monkeypatch.setattr(intake, "blocked_reason", lambda *args: None)
    service._physical_intake_evidence = intake
    service._physical_intake = case.notebook
    monkeypatch.setattr(service, "_intake_is_current", lambda: True)
    # Real prerequisite/epoch projections with the original source assessment
    # and M1 publication state explicitly modeled, as in the UI seam tests.
    setup = fixture_view(tmp_path, case.latest)["physical_camera_setup"]
    monkeypatch.setattr(service._physical_camera_setup, "view", lambda: deepcopy(setup))
    return service


def test_full_arrival_live_snapshot_has_bounded_unabridged_choices(
    make_service,
    monkeypatch,
    tmp_path,
    maximum_single,
):
    service = published_arrival(make_service, monkeypatch, tmp_path, maximum_single)
    snapshot = service.view()
    action = next(
        row
        for row in snapshot["actions"]
        if row["action_id"] == "physical_intake_submit"
    )
    attachment_fields = [
        row for row in action["fields"] if row["name"].startswith("attachment_")
    ]
    assert len(attachment_fields) == 16
    assert all(len(row["options"]) == 33 for row in attachment_fields)
    snapshot["events"] = []  # exact final-export exclusion
    snapshot["exports"] = {"directory": str(tmp_path / "exports"), "export_count": 0}
    print("actual_arrival_snapshot", metrics(snapshot))
    action_compact = deepcopy(snapshot)
    for row in action_compact["actions"]:
        row.pop("fields", None)
    print("proposed_export_without_action_form_fields", metrics(action_compact))
    # The GET projection has no export-snapshot cap; the export must provide a
    # faithful bounded representation instead of silently truncating the view.
    assert (
        export.sanitize_diagnostic_record(snapshot, maximum_bytes=1024 * 1024)
        == snapshot
    )


def test_actual_arrival_export_maximum_view_and_original_metadata(
    make_service,
    monkeypatch,
    tmp_path,
    maximum_single,
):
    service = published_arrival(make_service, monkeypatch, tmp_path, maximum_single)
    for index in range(32):
        result = _run(
            service,
            "record_note",
            {"note": f"Budget test note {index}; no hardware action."},
        )
        assert result["status"] == "SUCCEEDED"
    assert len(service.view()["operations"]) == 32
    result = service._export()
    assert result["verification"]["valid"] is True
    directory = Path(result["receipt"]["path"])
    attachment = export._parse_json(
        (directory / "attachment-intake-evidence.json").read_bytes()
    )
    assert attachment["original_bytes_preserved"] is True
    assert (
        attachment["collection_1_submission"]
        == maximum_single.latest.submission.to_dict()
    )


def test_actual_exporter_full_metadata_retains_exact_documents(
    tmp_path, maximum_history
):
    service = cached_service(tmp_path, maximum_history)
    diagnostics = service.retained_diagnostics()
    payload = export._json_bytes(
        {
            **diagnostics,
            "schema": "rocell.wizard_physical_intake_evidence_export.v1",
            "original_bytes_preserved": True,
        }
    )
    exporter = export.WizardDiagnosticExporter(tmp_path / "metadata-export")
    exporter.prepare(create=True)
    receipt = exporter.export(
        {"mode": "physical", "physical_authority": False},
        [],
        attachments={"intake-evidence.json": payload},
    )
    assert export.verify_export(Path(receipt["path"]))["valid"] is True
    retained = (Path(receipt["path"]) / "attachment-intake-evidence.json").read_bytes()
    assert retained == payload


def test_maximum_codec_projection_is_accepted_by_current_ui(tmp_path, maximum_single):
    view = fixture_view(tmp_path, maximum_single.latest)
    assert (
        _PhysicalIntakeEvidenceDisplay.projection(
            view["physical_intake_evidence"], view
        )
        is not None
    )


def test_partial_eighth_submission_preserves_full_metadata(tmp_path, maximum_history):
    # Model the exact post-SUBMITTED/pre-review cache. A retained current
    # attempt repeats submission+assessment, but never invents a committed review.
    service = cached_service(tmp_path, maximum_history, retain_attempt=False)
    service._workflow = deepcopy(service._workflow)
    last = service._workflow["intake_collections"][-1]
    last["review"] = None
    last["state"] = "REVIEW_PENDING"
    service._attempt = {
        "collection_id": last["collection_id"],
        "records": {
            role: deepcopy(last[role]) for role in ("submission", "assessment")
        },
    }
    value = service.retained_diagnostics()
    print("partial_eighth_submission", metrics(value))
    assert export.sanitize_diagnostic_record(value, maximum_bytes=1024 * 1024) == value
    assert value["collections"][-1]["review"] is None
    assert value["attempt_submission"] == maximum_history.latest.submission.to_dict()


def test_eight_collection_original_cache_does_not_use_native_ipc_node_budget(
    tmp_path,
    monkeypatch,
    maximum_history,
):
    """A modeled audited cache, not an imported history or new M1 readback."""
    service = cached_service(tmp_path, maximum_history)
    expected = service.retained_diagnostics()
    original = deepcopy(service._workflow)
    original["schema"] = "rocell.physical_camera_source_workflow_readback.v3"
    payload = canonical(original)
    context = maximum_history.fixture.prerequisites.to_dict()["binding"]
    original_owner = PhysicalCameraSession(
        tmp_path,
        tmp_path
        / "software/runs/physical-camera-acquisition"
        / context["launch_session_id"],
        launch_id=context["launch_session_id"],
        source_sha256=context["source_sha256"],
        cell_id=maximum_history.fixture.snapshot.header.cell_id,
        session_id=context["session_id"],
    )
    original_owner._retained_source_workflow = payload
    service.setup.session = original_owner
    measured = metrics(original)
    print("original_session_eight_collection_cache", measured)
    assert measured["nodes"] > 4096
    assert measured["nodes"] < 20000
    # Preserve the separate lower IPC bound: it is not the right decoder for
    # this already-verified original session's aggregate private history.
    with pytest.raises(OwnedWorkerError, match="IPC_STRUCTURE_LIMIT"):
        decode_owned_json(payload, maximum=4 * 1024 * 1024)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "historical cache retrieval must not read storage or start processes"
        )

    import subprocess
    from rocell.application import physical_camera_session as session_module

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "read_bytes", forbidden)
        patch.setattr(session_module, "source_fingerprint", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        restored = original_owner.retained_source_workflow()
        assert canonical(restored) == payload
        retained = service.retained_diagnostics()
        assert retained == expected
        assert (
            export.sanitize_diagnostic_record(retained, maximum_bytes=1024 * 1024)
            == retained
        )
        for number, collection in enumerate(maximum_history.collections, 1):
            for role in ("submission", "assessment", "review"):
                assert (
                    retained[f"collection_{number}_{role}"]
                    == collection[role]["document"]
                )
        restored["intake_collections"].clear()
        retained["collection_8_submission"]["notebook"]["rows"].clear()
        assert canonical(original_owner.retained_source_workflow()) == payload
        assert service.retained_diagnostics() == expected
        assert original_owner._retained_source_workflow == payload
