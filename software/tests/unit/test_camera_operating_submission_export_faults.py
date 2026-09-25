"""Public export faults with a full compound and MODELED cached provenance.

The real compound codec, sanitizer, general exporter, manifests and wizard logs
run. No original-store or hardware provenance is claimed by this fixture.
"""

from copy import deepcopy
import json

import pytest

from rocell.application.camera_operating_submission import CameraOperatingSubmission
from rocell.application.wizard_diagnostic_export import (
    MAX_NODES,
    MAX_STRING_CHARS,
    verify_export,
)
from rocell.application.arrival_wizard_service import MAX_RESULT_BYTES
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _run
from test_camera_operating_submission import seed, build
from test_commissioning_camera_persistence import forbid_device_and_process_calls
from test_native_camera_activation_supervisor import no_physical_owner


def modeled_packet(app, subject):
    """Only the export boundary is modeled; full document bytes are real codecs."""
    return dict(
        schema="rocell.wizard_camera_operating_submission_diagnostics.v1",
        source_sha256=app.source_sha256,
        launch_session_id=app.session_id,
        documents={subject.sha256: subject.to_dict()},
        attempts=[dict(operation_id="MODELED-attempt", state="HISTORICAL_HELD")],
        original_readback=None,
        approved_operating_policy=False,
        physical_authority=False,
        current_connection_restored=False,
        meaning="MODELED cached export subjects, not authenticated M1 originals.",
    )


@pytest.mark.parametrize("redacted", [False, True])
def test_public_full_compound_export_discloses_redaction_and_preserves_cache(
    make_service, seed, monkeypatch, redacted
):
    app, runner, _ = make_service(mode="physical")
    if redacted:
        seed = {**seed, "operator_id": "token=MODELED_FAKE_VALUE"}
    subject = build(seed)
    packet = modeled_packet(app, subject)
    before = deepcopy(packet)
    monkeypatch.setattr(app._operating_submission, "packet", lambda: deepcopy(packet))
    done = _run(app, "export_logs", {})
    assert done["status"] == "SUCCEEDED", done
    folders = list(app.export_directory.iterdir())
    assert len(folders) == 1 and verify_export(folders[0])["valid"]
    payload = (folders[0] / "attachment-camera-operating-submissions.json").read_bytes()
    saved = json.loads(payload)
    assert saved["original_bytes_preserved"] is (not redacted)
    document = saved["diagnostics"]["documents"][subject.sha256]
    if redacted:
        assert b"MODELED_FAKE_VALUE" not in payload
        assert "[REDACTED]" in document["operator_id"]
        assert digest(canonical(document)) != subject.sha256
    else:
        assert saved["diagnostics"] == packet
        assert CameraOperatingSubmission(canonical(document)).payload == subject.payload
    assert packet == before and not runner.calls
    assert not saved["diagnostics"]["physical_authority"]
    assert not saved["diagnostics"]["current_connection_restored"]


@pytest.mark.parametrize("fault", ["string", "depth", "nodes", "bytes"])
def test_over_limit_submission_export_fails_without_truncation_or_new_folder(
    make_service, seed, monkeypatch, fault
):
    app, runner, _ = make_service(mode="physical")
    packet = modeled_packet(app, build(seed))
    if fault == "string":
        packet["modeled_extra_diagnostics"] = "x" * (MAX_STRING_CHARS + 1)
    elif fault == "depth":
        value = None
        for _ in range(16):
            value = {"nested": value}
        packet["modeled_extra_diagnostics"] = value
    elif fault == "nodes":
        packet["modeled_extra_diagnostics"] = [None] * MAX_NODES
    else:
        packet["modeled_extra_diagnostics"] = ["x" * 1024] * (
            MAX_RESULT_BYTES // 1024 + 1
        )
    before = deepcopy(packet)
    monkeypatch.setattr(app._operating_submission, "packet", lambda: deepcopy(packet))
    folders = (
        set(app.export_directory.iterdir()) if app.export_directory.exists() else set()
    )
    done = _run(app, "export_logs", {})
    assert done["status"] != "SUCCEEDED", done
    after = (
        set(app.export_directory.iterdir()) if app.export_directory.exists() else set()
    )
    assert after == folders and packet == before
    assert not runner.calls and not app.view()["physical_authority"]
