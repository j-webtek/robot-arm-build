"""Actual codec/readback subjects into bounded export; storage/facts MODELED."""

from rocell.application import physical_usb_identity_export as exporter
from rocell.application.wizard_diagnostic_export import verify_export
from test_physical_camera_usb_absence_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    absence_subjects,
    presence_result,
    refresh_read,
    canonical,
    session,
    LAUNCH,
)
from test_usb_absence_export import absence_cache
from test_physical_usb_identity_export import read_receipt
from threading import Event
from pathlib import Path
import time


def test_complete_typed_v11_originals_restore_exactly_with_existing_caps(
    ready, monkeypatch, tmp_path
):
    made = absence_subjects(ready, monkeypatch, stop="query")
    presence_result(made)
    workflow = refresh_read(ready)
    cache = absence_cache()
    cache.update(
        source_sha256=workflow["binding"]["source_sha256"],
        launch_session_id=LAUNCH,
        qualification_trial=workflow["usb_qualification_trial"],
        qualification_baseline=workflow["usb_qualification_baseline"],
        qualification_absence=workflow["usb_qualification_absence"],
        qualification_attempt=None,
        qualification_absence_attempt=None,
    )
    raw = canonical(workflow)

    def measure(value, depth=0):
        children = (
            value.values()
            if isinstance(value, dict)
            else value if isinstance(value, list) else ()
        )
        rows = [measure(child, depth + 1) for child in children]
        return (max([depth, *[r[0] for r in rows]]), 1 + sum(r[1] for r in rows))

    depth, nodes = measure(workflow)
    assert session._decode_cached_source_workflow(raw) == workflow
    assert (
        len(raw) <= session.MAX_USB_ABSENCE_WORKFLOW_BYTES
        and depth <= 16
        and nodes <= 262144
    )
    receipt = exporter.export_usb_identity_diagnostics(
        cache,
        export_parent=tmp_path / "assigned-v11-exports",
        source_sha256=cache["source_sha256"],
        launch_id=LAUNCH,
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 100_000_000_000,
    )
    assert verify_export(Path(receipt["path"]))["valid"]
    snapshot, parts = read_receipt(receipt)
    assert exporter.restore_usb_identity_diagnostics(snapshot, parts) == cache
    assert snapshot["original_bytes_preserved"]
    print(
        f"V11_CACHE bytes={len(raw)} depth={depth} nodes={nodes}; EXPORT bytes={sum(map(len,parts.values()))} parts={len(parts)}"
    )
