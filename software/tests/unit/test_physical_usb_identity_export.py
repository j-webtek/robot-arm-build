"""USB cache exports: actual bounded files, modeled records, no hardware I/O."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import physical_usb_identity_export as module
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.application.wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    WizardDiagnosticExportError,
    verify_export,
)

SOURCE = "a" * 64
LAUNCH = "wizard-" + "1" * 32


def record(document=None):
    document = usb_identity_stage_policy().to_dict() if document is None else document
    return dict(
        document=document,
        evidence_sha256=module._hash(document),
        reference=None,
        retention="COLLECTED_NOT_M1_RETAINED",
    )


def diagnostics():
    return dict(
        schema=module.DIAGNOSTICS_SCHEMA,
        source_sha256=SOURCE,
        launch_session_id=LAUNCH,
        original_context=dict(session_id="MODELED_NOT_M1"),
        publication=dict(status="HISTORICAL_HELD", operation_id=None),
        stage_states=dict(camera_identity="WAITING_OPERATOR", camera_modes="PENDING"),
        metadata=None,
        baseline=None,
        inspection_attempt=record(),
        attempt=None,
        meaning="Explicitly modeled export cache; no device or original store.",
        **module._FLAGS,
    )


def prepare(value):
    return module.prepare_usb_identity_diagnostics_export(
        value, source_sha256=SOURCE, launch_id=LAUNCH
    )


def exported(value, parent, **changes):
    return module.export_usb_identity_diagnostics(
        value,
        export_parent=parent,
        source_sha256=SOURCE,
        launch_id=LAUNCH,
        cancellation=changes.pop("cancellation", Event()),
        deadline_ns=changes.pop("deadline_ns", time.monotonic_ns() + 100_000_000_000),
        **changes,
    )


def read_receipt(receipt):
    path = Path(receipt["path"])
    snapshot = json.loads((path / "report.json").read_bytes())["snapshot"]
    attachments = {
        row["attachment"]: (path / row["attachment"]).read_bytes()
        for row in snapshot["parts"]
    }
    return snapshot, attachments


def test_actual_export_reconstructs_original_and_preserves_existing_folder(tmp_path):
    parent = tmp_path / "exports"
    parent.mkdir()
    before = sorted(parent.iterdir())
    value = diagnostics()
    untouched = deepcopy(value)
    receipt = exported(value, parent)
    assert receipt["valid"] and verify_export(Path(receipt["path"]))["valid"]
    assert set(before) <= set(parent.iterdir())
    snapshot, parts = read_receipt(receipt)
    restored = module.restore_usb_identity_diagnostics(
        snapshot,
        parts,
        expected_original_diagnostics_sha256=module._hash(value),
    )
    assert restored == value == untouched
    assert snapshot["original_bytes_preserved"]
    assert (
        snapshot["coverage"][0]["evidence_sha256"] == usb_identity_stage_policy().sha256
    )
    assert receipt["export_root"] == str(parent)
    assert receipt["physical_authority"] == "NONE"


def test_second_export_creates_new_child_without_overwriting(tmp_path):
    first = exported(diagnostics(), tmp_path / "exports")
    second = exported(diagnostics(), tmp_path / "exports")
    assert first["path"] != second["path"]
    assert verify_export(Path(first["path"]))["valid"]
    assert verify_export(Path(second["path"]))["valid"]


def test_partial_dispatch_and_unknown_effects_are_not_zeroed():
    value = diagnostics()
    value["attempt"] = dict(
        action_id="physical_usb_identity_collect",
        usb_id="MODELED",
        records={},
        dispatch=dict(
            dispatch=dict(error_code="USB_ACCOUNTING_UNAVAILABLE"),
            original=dict(
                permit={"attempt_id": "MODELED"},
                result={"receipt": None},
                evidence=None,
                evidence_sha256=None,
                reference=None,
                retention="M1_TERMINAL_READ_BACK_EVIDENCE_PENDING",
            ),
        ),
    )
    snapshot, parts = prepare(value)
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    assert restored == value
    assert restored["attempt"]["dispatch"]["original"]["result"]["receipt"] is None


def test_subject_deduplication_preserves_all_original_paths():
    value = diagnostics()
    value["baseline"] = {"inspection": deepcopy(value["inspection_attempt"])}
    snapshot, parts = prepare(value)
    assert len(snapshot["coverage"]) == 2
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value
    repeated = module._hash(value["inspection_attempt"]["document"])
    assert all(row["evidence_sha256"] == repeated for row in snapshot["coverage"])


def test_redaction_keeps_original_hash_but_marks_not_reconstructible(tmp_path):
    value = diagnostics()
    value["inspection_attempt"] = record(
        {"details": {"password": "not-for-sharing", "note": "token=abc"}}
    )
    original_sha = value["inspection_attempt"]["evidence_sha256"]
    receipt = exported(value, tmp_path / "exports")
    snapshot, parts = read_receipt(receipt)
    assert not snapshot["original_bytes_preserved"]
    assert snapshot["credential_redaction_applied"]
    assert snapshot["reconstruction_status"] == "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    assert restored["inspection_attempt"]["evidence_sha256"] == original_sha
    assert (
        restored["inspection_attempt"]["document"]["details"]["password"]
        == "[REDACTED]"
    )
    assert b"not-for-sharing" not in b"".join(parts.values())
    assert snapshot["coverage"][0]["original_bytes_preserved"] is False


def test_split_parts_support_deep_complete_diagnostics_without_quota_changes(tmp_path):
    # Two large distinct records and a repeated latest-attempt copy. The
    # descriptor payloads are explicitly modeled ordinary text, not pixels.
    value = diagnostics()
    one = {f"descriptor{i}": f"MODELED_{i}_" + "a" * 40_000 for i in range(16)}
    two = {f"descriptor{i}": f"MODELED_{i}_" + "b" * 40_000 for i in range(16)}
    value["metadata"] = {"metadata": record(one), "helper": record(two)}
    nested = {"plain": "modeled deep original"}
    for _ in range(18):
        nested = {"next": nested}
    value["baseline"] = dict(execution=record(nested))
    value["attempt"] = dict(records=deepcopy(value["metadata"]))
    receipt = exported(value, tmp_path / "exports")
    snapshot, parts = read_receipt(receipt)
    assert 1 < len(parts) <= MAX_ATTACHMENTS
    assert all(len(raw) <= MAX_ATTACHMENT_BYTES for raw in parts.values())
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(extra=True),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(arm_access_authorized=0),
        lambda d: d.update(schema="other"),
        lambda d: d.update(source_sha256="wrong"),
        lambda d: d.update(launch_session_id="wrong"),
        lambda d: d.update(metadata=[]),
        lambda d: d["inspection_attempt"].update(evidence_sha256="b" * 64),
        lambda d: d.update(meaning=b"not json"),
        lambda d: d.update(attempt={"x": float("nan")}),
        lambda d: d.update(attempt={"x": 2**63}),
        lambda d: d.update(attempt={"x": "x" * (64 * 1024 + 1)}),
    ],
)
def test_invalid_input_refused_before_creating_directory(tmp_path, change):
    value = diagnostics()
    change(value)
    parent = tmp_path / "must-not-exist"
    with pytest.raises((module.UsbIdentityExportError, WizardDiagnosticExportError)):
        exported(value, parent)
    assert not parent.exists()


def test_cycle_rejected_with_bounded_depth():
    value = diagnostics()
    value["attempt"] = value
    with pytest.raises(module.UsbIdentityExportError):
        prepare(value)


def test_stop_before_export_leaves_no_directory(tmp_path):
    cancellation = Event()
    cancellation.set()
    parent = tmp_path / "not-created"
    with pytest.raises(module.UsbIdentityExportError, match="CANCELLED"):
        exported(diagnostics(), parent, cancellation=cancellation)
    assert not parent.exists()


@pytest.mark.parametrize("offset", [-1, 121_000_000_000])
def test_invalid_deadline_refused(tmp_path, offset):
    with pytest.raises(module.UsbIdentityExportError):
        exported(
            diagnostics(), tmp_path / "unused", deadline_ns=time.monotonic_ns() + offset
        )
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize(
    "field, replacement",
    [
        ("physical_authority", True),
        ("node_count", True),
        ("root_sha256", "b" * 64),
        ("original_bytes_preserved", False),
        ("coverage", []),
        ("reconstruction_status", "PASS"),
        ("source_identity", {}),
        ("session_id", "bad"),
    ],
)
def test_tampered_manifest_refused(field, replacement):
    snapshot, parts = prepare(diagnostics())
    snapshot[field] = replacement
    with pytest.raises(module.UsbIdentityExportError):
        module.restore_usb_identity_diagnostics(snapshot, parts)


def test_changed_extra_and_missing_parts_refused():
    snapshot, parts = prepare(diagnostics())
    name = next(iter(parts))
    for changed in (
        {},
        {**parts, "extra.json": b"{}"},
        {**parts, name: parts[name] + b" "},
    ):
        with pytest.raises(module.UsbIdentityExportError):
            module.restore_usb_identity_diagnostics(snapshot, changed)


def test_export_source_label_cannot_replace_original_diagnostic_identity():
    value = diagnostics()
    with pytest.raises(module.UsbIdentityExportError, match="SOURCE_MISMATCH"):
        module.prepare_usb_identity_diagnostics_export(
            value, source_sha256="b" * 64, launch_id=LAUNCH
        )
    snapshot, parts = prepare(value)
    snapshot["source_binding_sha256"] = "b" * 64
    snapshot["source_identity"] = dict(source_sha256="b" * 64)
    with pytest.raises(module.UsbIdentityExportError, match="SOURCE_MISMATCH"):
        module.restore_usb_identity_diagnostics(snapshot, parts)


def test_new_export_launch_preserves_original_source_and_collection_launch():
    value = diagnostics()
    exporting_launch = "wizard-" + "9" * 32
    snapshot, parts = module.prepare_usb_identity_diagnostics_export(
        value,
        source_sha256=SOURCE,
        launch_id=exporting_launch,
    )
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    assert snapshot["session_id"] == exporting_launch
    assert restored["launch_session_id"] == LAUNCH
    assert restored["source_sha256"] == snapshot["source_binding_sha256"]


def test_unused_node_cannot_be_smuggled_in_with_rehashed_part():
    snapshot, parts = prepare(diagnostics())
    name = next(iter(parts))
    packet = json.loads(parts[name])
    node = dict(kind="object", values=[["unused", "must fail"]])
    packet["nodes"][module._hash(node)] = node
    raw = module._json_bytes(packet)
    parts[name] = raw
    snapshot["parts"][0].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    snapshot["node_count"] += 1
    with pytest.raises(module.UsbIdentityExportError):
        module.restore_usb_identity_diagnostics(snapshot, parts)


@pytest.mark.parametrize("no_attempt", [True, False])
@pytest.mark.skipif(os.name != "nt", reason="actual incapable Windows Job path")
def test_exact_owned_run_original_bytes_survive_export(
    tmp_path, monkeypatch, no_attempt
):
    """Real codecs/Job, explicitly modeled admission, separately incapable EXE."""
    from rocell.providers.windows import owned_usb_identity_runner as runner
    from rocell.providers.windows.owned_usb_identity_evidence import (
        OwnedUsbIdentityRunEvidence,
    )
    from test_owned_usb_identity_runner import usb_fixture, run_case

    monkeypatch.setattr(runner, "source_fingerprint", lambda _: SOURCE)
    case = usb_fixture(fail_at=1 if no_attempt else None)
    if no_attempt:
        monkeypatch.setattr(
            runner, "_new_owner", lambda: pytest.fail("owner after refused scope")
        )
    _, evidence = run_case(case)
    assert evidence.no_attempt is no_attempt
    assert evidence.to_dict()["provenance"] == "INCAPABLE_USB_QUERY"
    value = diagnostics()
    value["baseline"] = dict(execution=record(evidence.to_dict()))
    value["attempt"] = dict(
        dispatch=dict(
            original=dict(
                evidence=evidence.to_dict(),
                evidence_sha256=evidence.sha256,
                retention="MODELED_REFERENCE_WITH_ACTUAL_INCAPABLE_CHILD_BYTES",
            )
        )
    )
    receipt = exported(value, tmp_path / "exports")
    snapshot, parts = read_receipt(receipt)
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    restored_evidence = OwnedUsbIdentityRunEvidence(
        module._canonical(restored["baseline"]["execution"]["document"])
    )
    assert restored_evidence.payload == evidence.payload
    assert restored_evidence.no_attempt is no_attempt
    assert restored_evidence.actual_counts["hub_open_attempts"] == (
        0 if no_attempt else 5
    )
    assert all(row["original_bytes_preserved"] for row in snapshot["coverage"])
