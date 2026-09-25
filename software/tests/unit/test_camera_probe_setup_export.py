"""Complete diagnostic reconstruction with modeled records; never hardware."""

from copy import deepcopy
from threading import Event
from time import monotonic_ns
import json

import pytest

from rocell.application import camera_probe_setup_export as export
from rocell.application import camera_probe_setup_service as writer
from rocell.application.wizard_diagnostic_export import (
    verify_export,
    sanitize_diagnostic_record,
    MAX_ATTACHMENT_BYTES,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_probe_setup_service import modeled, execute, SOURCE, PROBE_LAUNCH
from test_camera_probe_preparation_readback import prepared_subject
from test_physical_camera_identity_readback import identity_inputs
from test_camera_mode_entry_layout import reference
from rocell.application.physical_onboarding import STAGE_ORDER


def diagnostics(c):
    original = deepcopy(c.original.get("camera_probe_preparation"))
    if original is not None:
        original["meaning"] = (
            "MODELED original-store readback, not authenticated hardware"
        )
    return dict(
        schema=export.DIAGNOSTICS_SCHEMA,
        source_sha256=SOURCE,
        launch_session_id=PROBE_LAUNCH,
        publication=dict(status="HISTORICAL_HELD", operation_id=None),
        original=original,
        attempts=deepcopy(c.setup._probe_attempts),
        queues=deepcopy(c.setup._probe_queues),
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        meaning="MODELED writer/export input. No device or original store is accessed by export.",
    )


@pytest.mark.parametrize("state", ["queued", "prepared", "reviewed", "attempt-only"])
def test_exact_complete_and_partial_diagnostics_round_trip(modeled, state):
    c = modeled
    if state != "queued":
        execute(c)
    if state == "reviewed":
        execute(c, writer.REVIEW)
    if state == "attempt-only":
        c.original.pop("camera_probe_preparation")
    value = diagnostics(c)
    before = deepcopy(value)
    summary, parts = export.prepare_probe_setup_export(value)
    assert summary["original_bytes_preserved"] is True
    assert export.restore_probe_setup_export(summary, parts) == value == before
    assert all(0 < len(raw) <= MAX_ATTACHMENT_BYTES for raw in parts.values())
    assert all(
        sanitize_diagnostic_record(json.loads(raw), maximum_bytes=MAX_ATTACHMENT_BYTES)
        == json.loads(raw)
        for raw in parts.values()
    )


def test_maximum_supported_inventory_is_not_truncated(modeled):
    c = modeled
    previous = identity_inputs(source=SOURCE, maximum_inventory=True)["enrollment"]
    prep = prepared_subject(c.original, c.bound, previous=previous)
    ref = reference(prep.payload, "preparation", STAGE_ORDER[4])
    value = diagnostics(c)
    value["original"] = dict(
        state="INCOMPLETE",
        preparation=dict(
            document=prep.to_dict(),
            evidence_sha256=prep.sha256,
            reference=ref.to_dict(),
            retention="M1_FULL_BYTES_READ_BACK",
        ),
        review=None,
        events=[],
        meaning="MODELED large original",
    )
    summary, parts = export.prepare_probe_setup_export(value)
    restored = export.restore_probe_setup_export(summary, parts)
    assert restored == value
    assert (
        len(
            restored["original"]["preparation"]["document"]["enrollment"][
                "inventory_packet"
            ]["receipt"]["devices"]
        )
        == 64
    )


def test_redaction_precedes_flattening_and_never_claims_original_bytes(modeled):
    c = modeled
    execute(c)
    value = diagnostics(c)
    value["meaning"] = "password=do-not-share"
    summary, parts = export.prepare_probe_setup_export(value)
    restored = export.restore_probe_setup_export(summary, parts)
    assert summary["original_bytes_preserved"] is False
    assert summary["credential_redaction_applied"] is True
    assert "do-not-share" not in str(restored)
    assert all(b"do-not-share" not in raw for raw in parts.values())
    assert value["meaning"] == "password=do-not-share"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "changed-bytes",
        "changed-root",
        "claim-current",
        "wrong-source",
        "wrong-count",
        "wrong-original-hash",
    ],
)
def test_reconstruction_rejects_partial_or_changed_bundle(modeled, fault):
    execute(modeled)
    summary, parts = export.prepare_probe_setup_export(diagnostics(modeled))
    if fault == "missing":
        parts.pop(next(iter(parts)))
    elif fault == "extra":
        parts["extra.json"] = b"{}"
    elif fault == "changed-bytes":
        parts[next(iter(parts))] += b" "
    elif fault == "changed-root":
        summary["root_sha256"] = "f" * 64
    elif fault == "claim-current":
        summary["physical_authority"] = True
    elif fault == "wrong-source":
        summary["source_binding_sha256"] = "f" * 64
    elif fault == "wrong-count":
        summary["node_count"] = True
    else:
        summary["original_diagnostics_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        export.restore_probe_setup_export(summary, parts)


def test_actual_assigned_export_and_cancel_before_write(modeled, tmp_path):
    c = modeled
    execute(c)
    folder = tmp_path / "assigned-exports"
    stopped = Event()
    stopped.set()
    with pytest.raises(ValueError):
        export.export_probe_setup(
            diagnostics(c),
            export_parent=folder,
            cancellation=stopped,
            deadline_ns=monotonic_ns() + export.TIMEOUT_NS,
        )
    assert not folder.exists()
    receipt = export.export_probe_setup(
        diagnostics(c),
        export_parent=folder,
        cancellation=Event(),
        deadline_ns=monotonic_ns() + export.TIMEOUT_NS,
    )
    assert receipt
    children = list(folder.iterdir())
    assert len(children) == 1
    checked = verify_export(children[0])
    assert checked
    report = json.loads((children[0] / "report.json").read_bytes())
    parts = {
        path.name[len("attachment-") :]: path.read_bytes()
        for path in children[0].glob("attachment-*.json")
    }
    assert export.restore_probe_setup_export(report["snapshot"], parts) == diagnostics(
        c
    )
