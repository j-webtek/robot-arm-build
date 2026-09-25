"""Real file exports of actual pure codecs; all input observations are modeled."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace

import pytest

from rocell.application import physical_received_camera_export as module
from rocell.application import physical_received_camera_submission as codec
from rocell.application.physical_onboarding_receipts import BoundEvidence
from rocell.application.wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    MAX_DEPTH,
    MAX_NODES,
    WizardDiagnosticExporter,
    verify_export,
)
from test_physical_received_camera import prerequisites, workspace
from test_physical_received_camera_submission import submission_fixture
from test_physical_intake_export_budgets import _maximum_notebook


def diagnostics(*, cycles=(), draft=None, attempt=None):
    return dict(
        schema=module.DIAGNOSTICS_SCHEMA,
        original_context={
            "source_sha256": "a" * 64,
            "session_id": "physical-camera-" + "1" * 32,
        },
        publication={"status": "HISTORICAL_HELD", "operation_id": None},
        stage_states={"camera_receipt": "BLOCKED", "camera_identity": "PENDING"},
        cycles=list(cycles),
        draft=draft,
        draft_origin_notebook_sha256=None,
        attempt=attempt,
        camera_identity_request=None,
        physical_authority=False,
        hardware_qualified=False,
        native_release_allowed=False,
        device_io_performed=False,
        meaning="Explicit modeled original history, not hardware.",
    )


def export(value, directory, **changes):
    return module.export_received_camera_metadata(
        value,
        export_parent=directory,
        source_sha256="b" * 64,
        launch_id="wizard-" + "9" * 32,
        cancellation=changes.pop("cancellation", Event()),
        deadline_ns=changes.pop("deadline_ns", time.monotonic_ns() + 100_000_000_000),
        **changes,
    )


def record(document, *, reference=None):
    return dict(
        document=document,
        evidence_sha256=module._sha(document),
        retention="M1_FULL_BYTES_READ_BACK",
        reference=reference,
    )


def maximum_families(prerequisites):
    """Four strict codec families with near-64KiB notebook originals and media refs.

    Pure modeled references are not a claim that M1 or hardware was observed.
    The actual deterministic foundation makes these extreme dimensions BLOCKED.
    """
    seed = submission_fixture(prerequisites)
    book = _maximum_notebook(
        SimpleNamespace(notebook=seed["notebook"], prerequisites=prerequisites)
    )
    previous, result, subjects = None, [], []
    for index in range(1, 5):
        row = book.to_dict()["rows"][-1]
        observation = dict(row["observation"])
        observation["evidence_note"] = observation["evidence_note"][:-1] + str(index)
        book = book.record(
            record_id=row["record_id"],
            observation_status=observation.pop("status"),
            **observation,
        )
        refs = tuple(
            replace(
                ref,
                evidence_id="evidence-" + f"{index * 10000 + i:064x}",
                package_sha256=f"{index * 10000 + i:064x}",
                payload_sha256=book.sha256 if i == 0 else ref.payload_sha256,
                payload_bytes=len(book.payload) if i == 0 else ref.payload_bytes,
            )
            for i, ref in enumerate(seed["kwargs"]["evidence_inventory"])
        )
        inspection = replace(
            seed["kwargs"]["inspection"],
            binding=replace(
                seed["kwargs"]["inspection"].binding,
                evidence=tuple(BoundEvidence.from_reference(ref) for ref in refs),
            ),
            purchase_record_evidence_id=refs[1].evidence_id,
            inspection_image_evidence_ids=(refs[2].evidence_id,),
        )
        attachments = tuple(
            replace(old, reference=ref)
            for old, ref in zip(seed["kwargs"]["attachments"], refs[1:])
        )
        binding = {
            **seed["kwargs"]["binding"],
            "receipt_id": f"receivedcamera-{index:032x}",
        }
        submission = codec.build_received_camera_submission(
            prerequisites,
            book,
            binding=binding,
            notebook_reference=refs[0],
            inspection=inspection,
            attachments=attachments,
            row_links=tuple(
                codec.ReceivedCameraRowLink(row["record_id"], refs[1].evidence_id)
                for row in book.to_dict()["rows"]
            ),
            submitted_at_ns=index * 10000,
            evidence_inventory=refs,
            predecessor=previous,
        )
        assessment = codec.assess_received_camera_submission(submission)
        review = codec.review_received_camera_submission(
            submission,
            assessment,
            decision="ACKNOWLEDGE_EXACT",
            reviewer_id="modeled-reviewer",
            review_launch_id=binding["collection_launch_id"],
            reviewed_at_ns=index * 10000 + 1,
        )
        assert review.to_dict()["verdict"] == "BLOCKED"
        previous = (submission, assessment, review)
        originals = [
            dict(
                label=f"received-camera-original-v1:{binding['receipt_id']}:{i:02}",
                index=i,
                media_type=attachment.media_type,
                evidence_sha256=attachment.reference.payload_sha256,
                retention="M1_FULL_BYTES_READ_BACK",
                reference=attachment.reference.to_dict(),
            )
            for i, attachment in enumerate(attachments)
        ]
        cycle = dict(
            receipt_id=binding["receipt_id"],
            sequence=index,
            state="REVIEWED_BLOCKED",
            originals=originals,
            notebook=record(book.to_dict(), reference=refs[0].to_dict()),
            **{
                role: record(artifact.to_dict())
                for role, artifact in zip(
                    ("submission", "assessment", "review"), previous
                )
            },
        )
        result.append(cycle)
        subjects.append((book, *previous))
    return result, subjects


def shape(value, depth=0):
    children = (
        value.values()
        if isinstance(value, dict)
        else value if isinstance(value, list) else ()
    )
    rows = [shape(item, depth + 1) for item in children]
    return 1 + sum(row[0] for row in rows), max([depth, *(row[1] for row in rows)])


def test_four_near_limit_full_families_draft_attempt_real_export_exact_reconstruction(
    prerequisites, tmp_path
):
    cycles, subjects = maximum_families(prerequisites)
    attempt = dict(
        action_id="received_camera_submit",
        receipt_id=cycles[-1]["receipt_id"],
        records={
            role: {
                **cycles[-1][role],
                "label": f"received-camera-{role}-v1:{cycles[-1]['receipt_id']}",
            }
            for role in ("notebook", "submission", "assessment", "review")
        },
    )
    attempt["records"]["original_00"] = {
        key: value
        for key, value in cycles[-1]["originals"][0].items()
        if key not in {"index", "media_type"}
    }
    value = diagnostics(cycles=cycles, draft=subjects[-1][0].to_dict(), attempt=attempt)
    value["failed_draft"] = dict(
        document=subjects[-2][0].to_dict(),
        draft_origin_notebook_sha256=subjects[-3][0].sha256,
    )
    before = deepcopy(value)
    receipt = export(value, tmp_path / "metadata")
    directory = Path(receipt["path"])
    assert receipt["valid"] and verify_export(directory)["valid"]
    assert len(list(directory.glob("attachment-*.json"))) == 6
    snapshot = json.loads((directory / "report.json").read_bytes())["snapshot"]
    assert snapshot["original"]["publication"]["status"] == "HISTORICAL_HELD"
    assert snapshot["original"]["original_context"]["source_sha256"] == "a" * 64
    assert snapshot["source_identity"]["source_sha256"] == "b" * 64
    assert snapshot["original_diagnostics_sha256"] == module._sha(value)
    assert snapshot["original_field_names"] == sorted(value)
    assert snapshot["metadata_bytes_preserved"] is True
    measurements = []
    for index, (cycle, originals) in enumerate(zip(cycles, subjects), 1):
        raw = (
            directory / f"attachment-received-camera-cycle-{index:02}.json"
        ).read_bytes()
        packet = json.loads(raw)
        assert (
            packet["original_bytes_preserved"]
            and not packet["credential_redaction_applied"]
        )
        restored = module.restore_received_camera_family(
            packet, expected_original_family_sha256=module._sha(cycle)
        )
        assert restored == cycle
        for role, artifact in zip(
            ("notebook", "submission", "assessment", "review"), originals
        ):
            assert module._canonical(restored[role]["document"]) == artifact.payload
            assert restored[role]["evidence_sha256"] == artifact.sha256
        assert len(originals[0].payload) >= 65000
        nodes, depth = shape(packet)
        assert (
            len(raw) <= MAX_ATTACHMENT_BYTES
            and nodes <= MAX_NODES
            and depth <= MAX_DEPTH
        )
        assert module._sha(originals[0].to_dict()) in packet["documents"]
        measurements.append(
            dict(
                bytes=len(raw),
                nodes=nodes,
                depth=depth,
                original_bytes=len(module._canonical(cycle)),
            )
        )
    for family, expected in (
        (
            "draft",
            {
                key: value.get(key)
                for key in ("draft", "draft_origin_notebook_sha256", "failed_draft")
            },
        ),
        ("attempt", attempt),
    ):
        packet = json.loads(
            (directory / f"attachment-received-camera-{family}.json").read_bytes()
        )
        assert module.restore_received_camera_family(packet) == expected
    assert value == before
    print(
        json.dumps(
            {"families": measurements, "total_export_bytes": receipt["total_bytes"]}
        )
    )


def test_redaction_explicitly_prevents_original_claim_but_preserves_whole_family(
    tmp_path,
):
    value = diagnostics(
        draft={
            "schema": "modeled-notebook",
            "note": "password=private123",
            "all_other_fields": [1, 2, 3],
        }
    )
    receipt = export(value, tmp_path / "export")
    packet = json.loads(
        (Path(receipt["path"]) / "attachment-received-camera-draft.json").read_bytes()
    )
    restored = module.restore_received_camera_family(packet)
    assert (
        packet["original_bytes_preserved"] is False
        and packet["credential_redaction_applied"] is True
    )
    assert packet["original_family_sha256"] != packet["restored_family_sha256"]
    assert restored["draft"]["all_other_fields"] == [1, 2, 3]
    assert "private123" not in json.dumps(packet)
    assert value["draft"]["note"] == "password=private123"


def test_context_redaction_is_also_explicit_without_rewriting_subject_hashes(tmp_path):
    value = diagnostics()
    value["original_context"]["note"] = "password=private123"
    receipt = export(value, tmp_path / "export")
    packet = json.loads((Path(receipt["path"]) / "report.json").read_bytes())[
        "snapshot"
    ]
    assert packet["metadata_credential_redaction_applied"] is True
    assert packet["metadata_bytes_preserved"] is False
    assert packet["original_metadata_sha256"] != packet["exported_metadata_sha256"]
    assert packet["original_diagnostics_sha256"] == module._sha(value)
    assert "private123" not in json.dumps(packet)


@pytest.mark.parametrize(
    "kind", ["missing", "unused", "cycle", "changed", "subject", "flag"]
)
def test_reconstruction_rejects_tampering(kind):
    packet = module._family(
        "draft", {"notebook": {"schema": "modeled", "rows": [1, 2]}}
    )
    digest = next(iter(packet["documents"]))
    if kind == "missing":
        packet["documents"].clear()
    elif kind == "unused":
        packet["documents"]["f" * 64] = {}
    elif kind == "cycle":
        packet["documents"][digest] = {module._REFERENCE: digest}
    elif kind == "changed":
        packet["documents"][digest]["rows"].append(3)
    elif kind == "subject":
        packet["original_family_sha256"] = "a" * 64
    else:
        packet["physical_authority"] = True
    with pytest.raises(module.ReceivedCameraMetadataExportError):
        module.restore_received_camera_family(packet)


def tiny_cycle():
    return dict(
        receipt_id="receivedcamera-" + "1" * 32,
        sequence=1,
        state="INCOMPLETE",
        originals=[],
        notebook=record({"schema": "modeled"}),
        submission=None,
        assessment=None,
        review=None,
    )


@pytest.mark.parametrize(
    "kind",
    [
        "raw",
        "encoded",
        "extra_role",
        "extra_cycle",
        "too_many",
        "duplicate",
        "authority",
        "nested",
        "bytes",
        "large",
    ],
)
def test_closed_metadata_boundary_refuses_before_directory_creation(tmp_path, kind):
    cycle = tiny_cycle()
    value = diagnostics(cycles=[cycle])
    if kind in {"raw", "encoded"}:
        cycle["originals"] = [
            dict(
                label="modeled",
                index=0,
                media_type="text/plain",
                evidence_sha256="a" * 64,
                retention="M1_FULL_BYTES_READ_BACK",
                reference={},
                **{kind: "PRIVATE"},
            )
        ]
    elif kind == "extra_role":
        cycle["notebook"]["raw"] = "PRIVATE"
    elif kind == "extra_cycle":
        cycle["raw"] = "PRIVATE"
    elif kind == "too_many":
        value["cycles"] *= 5
    elif kind == "duplicate":
        value["cycles"].append({**cycle, "sequence": 2})
    elif kind == "authority":
        value["native_release_allowed"] = True
    elif kind == "nested":
        for _ in range(22):
            cycle["notebook"]["document"] = {"nested": cycle["notebook"]["document"]}
    elif kind == "bytes":
        cycle["notebook"]["document"] = b"PRIVATE"
    else:
        cycle["notebook"]["document"] = {"note": "x" * 65537}
    with pytest.raises(module.ReceivedCameraMetadataExportError):
        export(value, tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


def test_stop_and_timeout_before_writes_and_no_renewal(tmp_path, monkeypatch):
    event = Event()
    event.set()
    with pytest.raises(module.ReceivedCameraMetadataExportError, match="CANCELLED"):
        export(diagnostics(), tmp_path / "absent", cancellation=event)
    times = iter([10, 10, 22])
    monkeypatch.setattr(module, "monotonic_ns", lambda: next(times))
    with pytest.raises(module.ReceivedCameraMetadataExportError, match="TIMED_OUT"):
        export(diagnostics(), tmp_path / "absent", deadline_ns=20)
    assert not (tmp_path / "absent").exists()


def test_completed_receipt_survives_late_stop_and_deadline(tmp_path, monkeypatch):
    event, clock = Event(), [10]
    monkeypatch.setattr(module, "monotonic_ns", lambda: clock[0])
    actual = WizardDiagnosticExporter.export

    def late(self, *args, **kwargs):
        receipt = actual(self, *args, **kwargs)
        event.set()
        clock[0] = 100
        return receipt

    monkeypatch.setattr(WizardDiagnosticExporter, "export", late)
    receipt = export(
        diagnostics(draft={"schema": "modeled"}),
        tmp_path / "export",
        cancellation=event,
        deadline_ns=20,
    )
    assert (
        event.is_set()
        and receipt["valid"]
        and verify_export(Path(receipt["path"]))["valid"]
    )


def test_original_partial_history_and_failed_only_draft_are_not_dropped(tmp_path):
    value = diagnostics(cycles=[tiny_cycle()])
    value["failed_draft"] = {
        "document": {"schema": "modeled", "note": "unpublished"},
        "draft_origin_notebook_sha256": "a" * 64,
    }
    receipt = export(value, tmp_path / "export")
    path = Path(receipt["path"])
    assert len(list(path.glob("attachment-*.json"))) == 2
    assert (
        module.restore_received_camera_family(
            json.loads((path / "attachment-received-camera-cycle-01.json").read_bytes())
        )
        == value["cycles"][0]
    )
    restored = module.restore_received_camera_family(
        json.loads((path / "attachment-received-camera-draft.json").read_bytes())
    )
    assert (
        restored["draft"] is None and restored["failed_draft"] == value["failed_draft"]
    )
