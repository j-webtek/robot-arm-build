"""Actual NTFS M1 + fixed incapable Job child + YUY2 ingestion integration.

Source bindings come from this workspace, never a synthetic hash. No hardware
inventory, native camera helper or serial transport is available in this lane.
The first four stages are really collected/assessed/reviewed for each store;
there is no cloned ledger, injected PASS snapshot or worker replay on reopening.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import threading

import pytest

from rocell.application import commissioning_rehearsal_service as service_module
from rocell.application import owned_camera_rehearsal_campaign as campaign_module
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows import camera_worker_client as camera_module
from rocell.providers.windows.owned_camera_runner import FRAME_BYTES
from test_commissioning_rehearsal_service import assess_review, collect, invoke


WORKSPACE = Path(__file__).resolve().parents[3]
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.name != "nt", reason="Real owned Job + local NTFS M1"),
]


@pytest.fixture
def ready_service(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "Owned fixture path must not use hardware or the old in-process fallback"
        )

    monkeypatch.setattr(service_module, "SyntheticBinaryCameraWorker", forbidden)
    for method in ("enumerate_metadata", "resolve_identity_metadata", "probe"):
        monkeypatch.setattr(camera_module.WindowsCameraWorkerClient, method, forbidden)
    # The owned Job implementation uses exact Win32 CreateProcess, not Popen.
    # Blocking this catches the old/default camera subprocess path if substituted.
    monkeypatch.setattr(camera_module.subprocess, "Popen", forbidden)
    source = source_fingerprint(WORKSPACE)
    print(f"owned M1 integration: source {source}", flush=True)
    service = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "owned-store", source_sha256=source
    )
    print("owned M1 integration: initialize", flush=True)
    invoke(service, "initialize")
    for index in range(4):
        print(f"owned M1 integration: first-four stage {index + 1}", flush=True)
        collect(service)
        assess_review(service)
    collect(service)
    assert service.view()["stage"] == "camera_mode_controls"
    assert (
        source_fingerprint(WORKSPACE) == source
    ), "Production source changed during real M1 setup; rerun explicitly"
    print("owned M1 integration: ready for contained capture", flush=True)
    return service


def retained(service):
    receipt = service._receipt
    assert receipt is not None
    attempt_id = receipt["attempt_result"]["attempt_id"]
    leases = (
        LeaseSpec(LeaseLevel.CELL, service.cell_id),
        LeaseSpec(LeaseLevel.SESSION, service.session_id),
        LeaseSpec(LeaseLevel.CAMERA, service.cell_id),
    )
    with service._store.transaction(leases) as tx:
        blobs = tx.read_campaign_evidence(attempt_id)
        records = tx._audit_records()
    assert len(blobs) == 1
    blob = blobs[0]
    assert blob.schema == "rocell.rehearsal_owned_camera_evidence.v1"
    assert (
        hashlib.sha256(blob.payload).hexdigest() == receipt["retained_campaign_sha256"]
    )
    document = json.loads(blob.payload)
    assert document["physical_authority"] is False and document["qualified"] is False
    assert document["binding"]["source_sha256"] == service.source_sha256
    assert document["binding"]["attempt_id"] == attempt_id
    assert document["binding"]["session_id"] == service.session_id
    for name in ("stdout", "stderr"):
        wire = base64.b64decode(document[name]["data"], validate=True)
        assert len(wire) == document[name]["bytes"]
        assert hashlib.sha256(wire).hexdigest() == document[name]["sha256"]
        assert document["process_result"][name + "_bytes"] == len(wire)
    return document, records


def test_current_source_owned_capture_retains_complete_m1_binary_and_process(
    ready_service,
    monkeypatch,
):
    service = ready_service
    before = service.view()
    values = service.bind(
        "rehearsal_owned_camera_campaign", {"frame_count": 1, "fault": "none"}
    )
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(WizardError, match="Cancelled"):
        service.perform(
            "rehearsal_owned_camera_campaign",
            values,
            cancellation=cancelled,
            progress=lambda _: None,
        )
    assert service.view()["journal_head_sha256"] == before["journal_head_sha256"]
    result = invoke(service, "owned_camera_campaign", frame_count=1, fault="none")
    assert result["status"] == "SUCCEEDED", service.view()
    assert result["physical_authority"] is False and result["device_open_count"] == 0
    assert result["metadata_inventory_performed"] is False
    assert all(
        result[key] == 0
        for key in (
            "serial_write_count",
            "power_event_count",
            "motion_command_count",
            "contact_command_count",
        )
    )
    view = service.view()
    assert not view["quarantined"] and not view["unresolved_attempt_ids"]
    assert service._receipt["attempt_result"]["state"] == "SEALED_KNOWN"
    assert view["camera_process"]["status"] == "RETAINED_COMPLETE_REHEARSAL"
    assert view["camera_process"]["process"]["tree_exit_confirmed"] is True
    assert view["camera_process"]["process"]["cleanup_errors"] == []
    assert view["camera_process"]["native"]["receipt_valid"] is True
    assert view["camera_process"]["device_cleanup_proven"] is False
    assert service.latest_preview().startswith(b"\x89PNG\r\n\x1a\n")
    capture = view["capture_dataset"]
    assert capture["physical_authority"] is False
    assert capture["dataset"]["frames"] == 1
    assert capture["dataset"]["logical_bytes"] == FRAME_BYTES + len(
        service.latest_preview()
    )
    document, records = retained(service)
    assert document["error"] is None
    assert document["capture"] == capture
    assert document["capture_envelope"] and document["source_contract"]
    process = document["process_result"]
    assert process["process_created"] and process["initial_thread_resumed"]
    assert (
        process["physical_authority"] is False
        and process["device_cleanup_confirmed"] is False
    )
    assert process["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    wire = json.loads(base64.b64decode(document["stdout"]["data"]))
    assert wire == process["parsed_result"]
    assert wire["request_sha256"] == process["request_sha256"]
    assert (
        wire["fixture_result"]["native_receipt"]["frames"][0]["length_bytes"]
        == FRAME_BYTES
    )
    assert any(record["kind"] == "CAMPAIGN_EVIDENCE" for record in records.values())
    assert any(record["kind"] == "CAMPAIGN_RESULT" for record in records.values())
    assert service.blocked_reason("rehearsal_owned_camera_campaign") is not None
    with pytest.raises(WizardError):
        invoke(service, "owned_camera_campaign", frame_count=1, fault="none")
    print("owned M1 integration: known retained capture verified", flush=True)

    def no_replay(*args, **kwargs):
        pytest.fail("Assessment, reopening and review must not rerun a camera worker")

    monkeypatch.setattr(
        campaign_module.OwnedBinaryCameraWorker, "run_retained_campaign", no_replay
    )
    invoke(service, "assess")
    assert service.view()["assessment"]["outcome"] == "PASS"
    print(
        "owned M1 integration: assessment accepted; reopening pending review",
        flush=True,
    )
    restored = CommissioningRehearsalService(
        WORKSPACE,
        service.directory.parent / "unused-restart",
        source_sha256=service.source_sha256,
    )
    invoke(restored, "discover")
    choices = restored.reopen_choices()
    assert len(choices) == 1
    reopened = invoke(restored, "reopen", choice_id=choices[0]["choice_id"])
    assert reopened["status"] == "SUCCEEDED", restored.view()
    assert (
        restored.directory == service.directory
        and restored.session_id == service.session_id
    )
    assert restored.view()["stage_state"] == "REVIEW_PENDING"
    assert restored.view()["camera_process"] == service.view()["camera_process"]
    assert (
        restored.latest_preview() is None
    )  # Retained image is never implicitly shown as live.
    invoke(restored, "review", reviewer_id="reviewer-b", accept_assessment=True)
    assert restored.view()["stages"][4]["state"] == "PASS"
    assert restored.view()["stage"] == "camera_frame_freshness"
    assert restored.view()["physical_authority"] is False
    print(
        "owned M1 integration: original-store review accepted; testing content tamper",
        flush=True,
    )
    # A known M1 seal does not qualify immutable dataset bytes after corruption.
    # Mutate only this test's exact retained chunk; never repair it afterwards.
    chunk = next((Path(capture["dataset"]["path"]) / "chunks").glob("*.bin"))
    with chunk.open("r+b") as stream:
        first = stream.read(1)
        stream.seek(0)
        stream.write(bytes([first[0] ^ 1]))
    held = CommissioningRehearsalService(
        WORKSPACE,
        service.directory.parent / "unused-after-tamper",
        source_sha256=service.source_sha256,
    )
    invoke(held, "discover")
    held_choices = held.reopen_choices()
    assert len(held_choices) == 1
    held_result = invoke(held, "reopen", choice_id=held_choices[0]["choice_id"])
    assert held_result["status"] == "FAILED"
    assert held.view()["reopen_result"]["status"] == "READ_ONLY_HOLD"
    assert held.latest_preview() is None and held.view().get("capture_dataset") is None
    assert held.blocked_reason("rehearsal_owned_camera_campaign") is not None
    assert held.view()["physical_authority"] is False
    assert (
        source_fingerprint(WORKSPACE) == service.source_sha256
    ), "Source changed during integration; rerun explicitly"
    print("owned M1 integration: tampered content held without replay", flush=True)


@pytest.mark.parametrize(
    "fault", ["identity-mismatch", "cleanup-uncertain", "malformed-result"]
)
def test_owned_failures_retain_raw_and_quarantine_without_fallback(
    ready_service, fault
):
    service = ready_service
    result = invoke(service, "owned_camera_campaign", frame_count=1, fault=fault)
    assert result["status"] == "FAILED"
    view = service.view()
    assert view["quarantined"] and view["status"] == "HELD"
    assert service.latest_preview() is None and view["capture_dataset"] is None
    document, records = retained(service)
    assert document["capture"] is None and document["error"] is not None
    process = document["process_result"]
    assert process["tree_exit_confirmed"] and not process["cleanup_errors"]
    stdout = base64.b64decode(document["stdout"]["data"])
    assert stdout
    if fault == "malformed-result":
        assert stdout == b'{"duplicate":1,"duplicate":2}'
        assert process["parsed_result"] is None and document["native_receipt"] is None
    elif fault == "identity-mismatch":
        assert document["native_receipt"] is None
        raw = json.loads(stdout)["fixture_result"]["native_receipt"]
        assert (
            raw["selected_endpoint"]
            != document["activation_request"]["binding"]["symbolic_link"]
        )
    else:
        assert process["primary_error"] == "WORKER_EXIT_FAILED"
        assert document["native_receipt"]["status"] == "FAILED"
        assert document["native_receipt"]["cleanup_confirmed"] is False
    assert view["camera_process"]["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert any(record["kind"] == "CAMPAIGN_EVIDENCE" for record in records.values())
    assert service.blocked_reason("rehearsal_assess") is not None
    with pytest.raises(WizardError):
        invoke(service, "owned_camera_campaign", frame_count=1, fault="none")
    assert (
        source_fingerprint(WORKSPACE) == service.source_sha256
    ), "Source changed during failure integration"
