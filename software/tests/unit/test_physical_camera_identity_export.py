"""Complete metadata exports under real generic limits; no native/device calls."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import physical_camera_identity_export as module
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    MAX_DEPTH,
    MAX_EXPORT_BYTES,
    MAX_NODES,
    WizardDiagnosticExporter,
    sanitize_diagnostic_record,
    verify_export,
)
from test_windows_camera_driver_metadata import driver_fixture
from test_physical_camera_identity_readback import (
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    identity_inputs,
    identity_subjects,
)


SOURCE = "a" * 64
LAUNCH = "wizard-" + "1" * 32


def reference(document, index=1):
    """Modeled stage-owned reference; never a claim of M1 retention."""
    digest = module._sha(document)
    return EvidenceReference(
        "evidence-" + f"{index:064x}",
        STAGE_ORDER[3],
        f"{index:064x}",
        f"{index + 100:064x}",
        digest,
        len(module._canonical(document)),
    ).to_dict()


def record(document, index=1):
    return dict(
        document=document,
        evidence_sha256=module._sha(document),
        retention="M1_FULL_BYTES_READ_BACK",
        reference=reference(document, index),
    )


def diagnostics(cycles=(), attempt=None):
    return dict(
        schema=module.DIAGNOSTICS_SCHEMA,
        source_sha256=SOURCE,
        launch_session_id=LAUNCH,
        original_context={
            "source_sha256": SOURCE,
            "session_id": "physical-camera-" + "2" * 32,
        },
        publication={"status": "HISTORICAL_HELD", "reason": "SOURCE_CHANGED"},
        stage_states={"camera_identity": "BLOCKED", "camera_modes": "PENDING"},
        cycles=list(cycles),
        attempt=attempt,
        meaning="MODELED cache only; no device observation.",
        **module._FLAGS,
    )


def cycle(index=1, documents=None):
    if documents is None:
        documents = {
            role: {
                "schema": "MODELED_NOT_STAGE_EVIDENCE",
                "role": role,
                "native": driver_fixture(),
            }
            for role in module.ROLE_BYTES
        }
    return dict(
        identity_id=f"cameraidentity-{index:032x}",
        sequence=index,
        state="REVIEWED_BLOCKED",
        **{
            role: record(document, index * 10 + i)
            for i, (role, document) in enumerate(documents.items(), 1)
        },
    )


def attempt(row, *, unretained=False):
    records = {}
    for role in module.ROLE_BYTES:
        rec = deepcopy(row[role])
        if rec is None:
            continue
        rec["label"] = f"camera-identity-{role}-v1:{row['identity_id']}"
        if unretained:
            rec.update(reference=None, retention="COLLECTED_NOT_M1_RETAINED")
        records[role] = rec
    return dict(
        action_id="physical_camera_identity_collect",
        identity_id=row["identity_id"],
        records=records,
    )


def prepare(value):
    return module.prepare_camera_identity_metadata_export(
        value, source_sha256="b" * 64, launch_id="wizard-" + "9" * 32
    )


def export(value, parent, **kwargs):
    return module.export_camera_identity_metadata(
        value,
        export_parent=parent,
        source_sha256="b" * 64,
        launch_id="wizard-" + "9" * 32,
        cancellation=kwargs.pop("cancellation", Event()),
        deadline_ns=kwargs.pop("deadline_ns", time.monotonic_ns() + 100_000_000_000),
        **kwargs,
    )


def read_export(receipt):
    directory = Path(receipt["path"])
    snapshot = json.loads((directory / "report.json").read_bytes())["snapshot"]
    parts = {
        row["attachment"]: (directory / row["attachment"]).read_bytes()
        for row in snapshot["parts"]
    }
    return snapshot, parts


def shape(value, depth=0):
    children = (
        value.values() if type(value) is dict else value if type(value) is list else ()
    )
    rows = [shape(child, depth + 1) for child in children]
    return 1 + sum(row[0] for row in rows), max([depth, *(row[1] for row in rows)])


def test_actual_five_subject_codecs_export_and_original_hash_reconstruction(
    identity_ready, tmp_path
):
    made = identity_subjects(identity_ready, **identity_inputs())
    row = dict(
        identity_id=made.subjects["metadata"].to_dict()["binding"]["identity_id"],
        sequence=1,
        state="REVIEWED_BLOCKED",
        **{
            role: dict(
                document=subject.to_dict(),
                evidence_sha256=subject.sha256,
                retention="M1_FULL_BYTES_READ_BACK",
                reference=made.refs[role].to_dict(),
            )
            for role, subject in made.subjects.items()
        },
    )
    value = diagnostics([row], attempt(row))
    before = deepcopy(value)
    receipt = export(value, tmp_path / "actual-codec-export")
    assert receipt["valid"] and verify_export(Path(receipt["path"]))["valid"]
    snapshot, parts = read_export(receipt)
    restored = module.restore_camera_identity_metadata(
        snapshot, parts, expected_original_diagnostics_sha256=module._sha(value)
    )
    assert restored == before == value
    assert snapshot["reconstruction_status"] == "ORIGINAL_BYTES_RECONSTRUCTIBLE"
    assert len(snapshot["coverage"]) == 10
    for role, subject in made.subjects.items():
        assert (
            module._canonical(restored["cycles"][0][role]["document"])
            == subject.payload
        )
    assert restored["cycles"][0]["assessment"]["document"]["verdict"] == "BLOCKED"


def test_four_actual_maximum_inventory_codec_cycles_and_last_attempt_export(
    identity_ready, tmp_path
):
    inputs = identity_inputs(maximum_inventory=True)
    rows = []
    predecessor = previous_refs = None
    subjects = []
    for sequence in range(1, 5):
        made = identity_subjects(
            identity_ready,
            **inputs,
            identity_id=f"cameraidentity-{sequence:032x}",
            sequence=sequence,
            predecessor=predecessor,
            previous_refs=previous_refs,
        )
        rows.append(
            dict(
                identity_id=f"cameraidentity-{sequence:032x}",
                sequence=sequence,
                state="REVIEWED_BLOCKED",
                **{
                    role: dict(
                        document=subject.to_dict(),
                        evidence_sha256=subject.sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=made.refs[role].to_dict(),
                    )
                    for role, subject in made.subjects.items()
                },
            )
        )
        subjects.append(made.subjects)
        predecessor, previous_refs = made.predecessor, made.refs
    value = diagnostics(rows, attempt(rows[-1]))
    receipt = export(value, tmp_path / "maximum-actual-producer")
    assert receipt["valid"] and verify_export(Path(receipt["path"]))["valid"]
    snapshot, parts = read_export(receipt)
    restored = module.restore_camera_identity_metadata(
        snapshot, parts, expected_original_diagnostics_sha256=module._sha(value)
    )
    assert restored == value
    for index, family in enumerate(subjects):
        for role, subject in family.items():
            assert (
                module._canonical(restored["cycles"][index][role]["document"])
                == subject.payload
            )
    print(
        json.dumps(
            {
                "actual_codec_parts": len(parts),
                "actual_codec_part_bytes": list(map(len, parts.values())),
                "original_identity_cache_bytes": len(module._canonical(value)),
                "original_identity_cache_nodes": shape(value)[0],
            }
        )
    )


def maximum_document(role, index):
    """Capacity model, explicitly not authored as successful stage evidence."""
    maximum = module.ROLE_BYTES[role]
    doc = {
        "schema": "MODELED_CAPACITY_ONLY",
        "role": role,
        "identity_sequence": index,
        "text": [],
    }
    while len(module._canonical(doc)) + 16_500 < maximum:
        doc["text"].append(f"{index}-{role}-{len(doc['text'])}:" + "x" * 16_384)
    doc["text"].append("")
    remaining = maximum - len(module._canonical(doc))
    doc["text"][-1] = "z" * remaining
    assert len(module._canonical(doc)) == maximum
    return doc


def test_four_exact_role_caps_and_full_distinct_failed_attempt_fit_unchanged_limits(
    tmp_path,
):
    cycles = [
        cycle(
            index, {role: maximum_document(role, index) for role in module.ROLE_BYTES}
        )
        for index in range(1, 5)
    ]
    failed = cycle(5, {role: maximum_document(role, 5) for role in module.ROLE_BYTES})
    value = diagnostics(cycles, attempt(failed, unretained=True))
    snapshot, parts = prepare(value)
    assert len(parts) <= MAX_ATTACHMENTS == 8
    assert len(snapshot["coverage"]) == 25 and snapshot["cycle_count"] == 4
    for raw in parts.values():
        packet = json.loads(raw)
        assert len(raw) <= MAX_ATTACHMENT_BYTES == 1024 * 1024
        nodes, depth = shape(packet)
        assert nodes <= MAX_NODES == 20000 and depth <= MAX_DEPTH == 12
        assert (
            sanitize_diagnostic_record(packet, maximum_bytes=MAX_ATTACHMENT_BYTES)
            == packet
        )
    receipt = export(value, tmp_path / "maximum-export")
    assert verify_export(Path(receipt["path"]))["valid"]
    actual_snapshot, actual_parts = read_export(receipt)
    assert actual_snapshot == snapshot and set(actual_parts) == {
        "attachment-" + name for name in parts
    }
    assert (
        module.restore_camera_identity_metadata(actual_snapshot, actual_parts) == value
    )
    manifest = json.loads((Path(receipt["path"]) / "manifest.json").read_bytes())
    assert (
        sum(row["bytes"] for row in manifest["files"]) + 32 * 1024
        <= MAX_EXPORT_BYTES
        == 8 * 1024 * 1024
    )
    print(
        json.dumps(
            {
                "parts": len(parts),
                "part_bytes": [len(raw) for raw in parts.values()],
                "max_nodes": max(shape(json.loads(raw))[0] for raw in parts.values()),
                "max_depth": max(shape(json.loads(raw))[1] for raw in parts.values()),
                "total_part_bytes": sum(map(len, parts.values())),
            }
        )
    )


def test_exact_duplicate_attempt_subjects_are_not_stored_twice():
    row = cycle()
    base_snapshot, base = prepare(diagnostics([row]))
    with_snapshot, with_attempt = prepare(diagnostics([row], attempt(row)))
    assert len(with_snapshot["coverage"]) == 10
    assert with_snapshot["node_count"] < 2 * base_snapshot["node_count"]
    assert sum(map(len, with_attempt.values())) < 2 * sum(map(len, base.values()))


def test_deep_original_is_flattened_without_opaque_strings_or_hiding_redaction(
    tmp_path,
):
    doc = {
        "observation": "modeled",
        "credentials": {"password": "secret-value"},
        "note": "Authorization: Bearer private-value",
    }
    for i in range(17):
        doc = {"nested": doc}
    row = cycle(documents={role: doc for role in module.ROLE_BYTES})
    value = diagnostics([row])
    receipt = export(value, tmp_path / "redacted-export")
    snapshot, parts = read_export(receipt)
    assert snapshot["reconstruction_status"] == "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
    assert not snapshot["original_bytes_preserved"]
    assert all(not row["original_bytes_preserved"] for row in snapshot["coverage"])
    restored = module.restore_camera_identity_metadata(snapshot, parts)
    assert restored != value
    assert all(
        module._sha(restored["cycles"][0][role]["document"])
        != row[role]["evidence_sha256"]
        for role in module.ROLE_BYTES
    )
    assert all(
        b"secret-value" not in raw and b"private-value" not in raw
        for raw in parts.values()
    )
    assert max(shape(json.loads(raw))[1] for raw in parts.values()) <= 12


@pytest.mark.parametrize(
    "fault",
    [
        "role_hash",
        "raw_role_field",
        "raw_reference_field",
        "stage",
        "missing_role",
        "cycle_count",
        "role_bytes",
        "bad_retention",
        "false_authority",
    ],
)
def test_bad_input_rejected_before_any_export_directory(tmp_path, fault):
    value = diagnostics([cycle()])
    row = value["cycles"][0]
    if fault == "role_hash":
        row["metadata"]["evidence_sha256"] = "c" * 64
    elif fault == "raw_role_field":
        row["metadata"]["raw_bytes_base64"] = "AAAA"
    elif fault == "raw_reference_field":
        row["metadata"]["reference"]["raw_bytes"] = "pixels"
    elif fault == "stage":
        row["metadata"]["reference"]["stage"] = "camera_receipt"
    elif fault == "missing_role":
        row.pop("helper")
    elif fault == "cycle_count":
        value["cycles"] = [cycle(i) for i in range(1, 6)]
    elif fault == "role_bytes":
        row["review"] = record(maximum_document("receipt", 1))
    elif fault == "bad_retention":
        row["review"]["retention"] = []
    else:
        value["physical_authority"] = True
    parent = tmp_path / fault
    with pytest.raises(module.CameraIdentityMetadataExportError):
        export(value, parent)
    assert not parent.exists()


def test_dense_individual_container_over_generic_item_limit_rejects_without_dropping(
    tmp_path,
):
    row = cycle(
        documents={
            role: (
                {"values": list(range(20000))} if role == "metadata" else {"role": role}
            )
            for role in module.ROLE_BYTES
        }
    )
    with pytest.raises(module.CameraIdentityMetadataExportError, match="CAPACITY"):
        export(diagnostics([row]), tmp_path / "cannot-fit")
    assert not (tmp_path / "cannot-fit").exists()


@pytest.mark.parametrize(
    "fault",
    [
        "missing_part",
        "changed_bytes",
        "subject_hash",
        "preserved_flag",
        "coverage",
        "source_identity",
    ],
)
def test_pure_restore_rejects_partial_or_rehashed_claim_tampering(fault):
    snapshot, parts = prepare(diagnostics([cycle()]))
    if fault == "missing_part":
        parts.pop(next(iter(parts)))
    elif fault == "changed_bytes":
        parts[next(iter(parts))] += b" "
    elif fault == "subject_hash":
        snapshot["original_diagnostics_sha256"] = "c" * 64
    elif fault == "preserved_flag":
        snapshot["original_bytes_preserved"] = False
    elif fault == "coverage":
        snapshot["coverage"][0]["evidence_sha256"] = "c" * 64
    else:
        snapshot["source_identity"]["source_sha256"] = "c" * 64
    with pytest.raises(module.CameraIdentityMetadataExportError):
        module.restore_camera_identity_metadata(snapshot, parts)


def test_pure_prepare_restore_never_read_files_or_launch_processes(monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected I/O")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    value = diagnostics([cycle()])
    snapshot, parts = prepare(value)
    assert module.restore_camera_identity_metadata(snapshot, parts) == value


def test_stop_deadline_prewrite_and_late_success_retention(monkeypatch, tmp_path):
    value = diagnostics([cycle()])
    cancelled = Event()
    cancelled.set()
    with pytest.raises(module.CameraIdentityMetadataExportError, match="CANCELLED"):
        export(value, tmp_path / "pre-stop", cancellation=cancelled)
    assert not (tmp_path / "pre-stop").exists()
    original_prepare = module.prepare_camera_identity_metadata_export
    tick = [100]
    monkeypatch.setattr(module, "monotonic_ns", lambda: tick[0])

    def late(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        tick[0] = 201
        return result

    monkeypatch.setattr(module, "prepare_camera_identity_metadata_export", late)
    with pytest.raises(module.CameraIdentityMetadataExportError, match="TIMED_OUT"):
        export(value, tmp_path / "late-preflight", deadline_ns=200)
    assert not (tmp_path / "late-preflight").exists()
    monkeypatch.setattr(
        module, "prepare_camera_identity_metadata_export", original_prepare
    )
    monkeypatch.setattr(module, "monotonic_ns", time.monotonic_ns)
    stop = Event()
    original_export = WizardDiagnosticExporter.export

    def completed(*args, **kwargs):
        receipt = original_export(*args, **kwargs)
        stop.set()
        return receipt

    monkeypatch.setattr(WizardDiagnosticExporter, "export", completed)
    receipt = export(value, tmp_path / "late-stop", cancellation=stop)
    assert stop.is_set() and receipt["valid"]


def test_empty_and_partial_attempt_only_export_keep_every_supplied_role(tmp_path):
    value = diagnostics(attempt=attempt(cycle(), unretained=True))
    del value["attempt"]["records"]["review"]
    receipt = export(value, tmp_path / "partial")
    snapshot, parts = read_export(receipt)
    assert snapshot["cycle_count"] == 0 and snapshot["attempt_included"]
    assert len(snapshot["coverage"]) == 4
    assert module.restore_camera_identity_metadata(snapshot, parts) == value
    snapshot, parts = prepare(diagnostics())
    assert not snapshot["coverage"]
    assert module.restore_camera_identity_metadata(snapshot, parts) == diagnostics()


@pytest.mark.parametrize(
    "fault", ["orphan", "node_hash", "extra_part", "missing_coverage", "cycle_state"]
)
def test_rehashed_graph_and_coverage_tampering_is_rejected(fault):
    if fault == "cycle_state":
        value = diagnostics([cycle()])
        value["cycles"][0]["review"] = None
        with pytest.raises(module.CameraIdentityMetadataExportError):
            prepare(value)
        return
    snapshot, parts = prepare(diagnostics([cycle()]))
    name = next(iter(parts))
    packet = json.loads(parts[name])
    if fault == "orphan":
        node = {"kind": "array", "values": ["unreferenced"]}
        packet["nodes"][module._sha(node)] = node
        snapshot["node_count"] += 1
    elif fault == "node_hash":
        node = packet["nodes"][next(iter(packet["nodes"]))]
        node["kind"] = "unknown"
    elif fault == "extra_part":
        parts["camera-identity-part-99.json"] = parts[name]
    else:
        snapshot["coverage"].pop()
    parts[name] = module._json_bytes(packet)
    row = snapshot["parts"][0]
    row.update(bytes=len(parts[name]), sha256=hashlib.sha256(parts[name]).hexdigest())
    with pytest.raises(module.CameraIdentityMetadataExportError):
        module.restore_camera_identity_metadata(snapshot, parts)
