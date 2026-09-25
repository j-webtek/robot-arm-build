"""Real NTFS identity-service submit/review/export/restart, no device access.

The received-unit, isolation, ownership and metadata facts in the shared prefix
are explicitly modeled. Original M1 files, leases, journal commits, readback,
clocks, 120-second service deadlines and the diagnostic exporter are real.
Arrival completion logging is modeled explicitly; this is not a public native
acquisition run or a received-unit/driver qualification.
"""

from copy import deepcopy
from pathlib import Path
from threading import Event
import os
import time

import pytest

from rocell.application import physical_camera_identity_service as service_module
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application import physical_camera_identity_export as export_module
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    _parse_evidence_reference,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical

from test_physical_camera_identity_readback import (
    actual_identity_entry,
    identity_inputs,
    no_devices,
    workspace,
)
from test_physical_camera_identity_service import values
from test_physical_camera_identity_export import read_export
from test_physical_camera_session import SOURCE, LAUNCH, session_fixture, perform


def adopt_actual_original(session, original, *, launch_id=LAUNCH):
    """Test-only explicit owner selection after actual original-store audit."""
    acquisition = PhysicalCameraAcquisitionService(
        Path(session.descriptor()["workspace"]),
        launch_id=launch_id,
        source_sha256=SOURCE,
        mode="physical",
    )
    setup = setup_impl.PhysicalCameraSetupService(acquisition)
    # Match production ordering: construct the current-launch owner inertly,
    # then explicitly switch both existing owners to the audited original.
    acquisition.bind_verified_session(session)
    setup.session = session  # Exact already audited original, never a fake store.
    setup._adopt_source_workflow(original)
    setup._publication = {"status": "PENDING", "operation_id": None}
    setup.publication_completed("MODELED-original-readback-completion-log")
    owner = service_module.PhysicalCameraIdentityService(setup)
    owner.observe_setup()
    return owner, acquisition


def execute(owner, inputs, action, *, export_parent=None):
    """Actual service execution; explicit modeled outer completion only."""
    started = time.monotonic_ns()
    result = owner.perform(
        action,
        values(action),
        **inputs,
        expected_context_sha256=owner.context_sha256(**inputs),
        cancellation=Event(),
        progress=lambda _: None,
        export_parent=export_parent,
    )
    elapsed = time.monotonic_ns() - started
    assert 0 < elapsed < 120_000_000_000
    assert result["status"] == "SUCCEEDED"
    assert result["metadata_inventory_performed"] is False
    assert result["physical_authority"] is False
    for key in (
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ):
        assert result[key] == 0
    assert owner.view()["publication"]["status"] == "PENDING"
    owner.validate_publication(result)
    if action != service_module.EXPORT:
        assert owner.setup.view()["publication"]["status"] == "PENDING"
        owner.setup.publication_completed("MODELED-identity-action-completion-log")
    owner.publication_completed("MODELED-identity-action-completion-log")
    print(f"real NTFS {action}: {elapsed / 1e9:.3f}s under original 120s bound")
    return result


def read_original(session, header):
    return session.read_original_source_workflow(
        expected_header_sha256=header,
        cancellation=Event(),
        progress=lambda _: None,
        deadline_ns=time.monotonic_ns() + 120_000_000_000,
    )


@pytest.mark.skipif(os.name != "nt", reason="Actual original NTFS owner required")
def test_actual_ntfs_identity_service_submit_review_export_and_restart(
    workspace, monkeypatch
):
    # No clock, transaction, store, original reader, codec or exporter injection.
    # Only broad source identity is modeled, as in the shared original fixture.
    monkeypatch.setattr(service_module, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(setup_impl, "source_fingerprint", lambda _: SOURCE)
    assert service_module.monotonic_ns is time.monotonic_ns
    assert setup_impl.monotonic_ns is time.monotonic_ns

    session, prerequisites, state = actual_identity_entry(workspace, monkeypatch)
    descriptor = session.descriptor()
    header = state["header"].header_sha256
    original = read_original(session, header)
    assert original["schema"] == "rocell.physical_camera_source_workflow_readback.v6"
    owner, acquisition = adopt_actual_original(session, original)
    assert acquisition.session_id == descriptor["session_id"]
    assert acquisition.cell_id == descriptor["cell_id"]
    inputs = identity_inputs(source=SOURCE, launch=owner.launch_id, return_owners=True)
    expected_enrollment = inputs["native_camera"].export_snapshot()
    expected_helper = inputs["helper"].export_snapshot()
    assert owner.view()["status"] == "WAITING_METADATA"

    execute(owner, inputs, service_module.SUBMIT)
    submitted = owner.setup.original_source_workflow()
    first = submitted["camera_identity_cycles"][0]
    assert first["state"] == "REVIEW_PENDING"
    assert first["metadata"]["document"]["enrollment"] == expected_enrollment
    assert first["helper"]["document"]["helper_report"] == expected_helper
    assert first["review"] is None
    assert owner.view()["status"] == "REVIEW_PENDING"
    assert first["assessment"]["document"]["verdict"] == "BLOCKED"
    assert first["receipt"]["document"]["observation"]["state"] == "UNKNOWN"

    execute(owner, inputs, service_module.REVIEW)
    reviewed = owner.setup.original_source_workflow()
    cycle = reviewed["camera_identity_cycles"][0]
    assert cycle["state"] == owner.view()["status"] == "REVIEWED_BLOCKED"
    assert cycle["review"]["document"]["decision"] == "ACKNOWLEDGE_EXACT"
    assert cycle["review"]["document"]["verdict"] == "BLOCKED"
    assert reviewed["received_camera_cycles"] == original["received_camera_cycles"]
    assert reviewed["qualification_cycles"] == original["qualification_cycles"]
    assert reviewed["original_source_state"] == "BLOCKED"
    assert reviewed["prerequisites"]["evidence_sha256"] == prerequisites.evidence_sha256
    for role, record in ((role, cycle[role]) for role in export_module.ROLE_BYTES):
        assert record["retention"] == "M1_FULL_BYTES_READ_BACK"
        assert record["reference"]["stage"] == STAGE_ORDER[3].value
        assert record["reference"]["payload_bytes"] == len(
            canonical(record["document"])
        )

    # Independent original bytes read after the service's stage-lease exit.
    with session.stage_transaction(
        expected_challenge_sha256=session.view()["verification"]["challenge_sha256"]
    ) as tx:
        before = tx.snapshot()
        assert len([ref for ref in before.evidence if ref.stage is STAGE_ORDER[3]]) == 5
        for role in export_module.ROLE_BYTES:
            record = cycle[role]
            assert tx.read_stage_evidence(
                _parse_evidence_reference(record["reference"])
            ) == canonical(record["document"])
        assert tx.snapshot().head == before.head

    diagnostic = deepcopy(owner.retained_diagnostics())
    export_parent = workspace / "software/runs/identity-service-test-exports"
    execute(owner, inputs, service_module.EXPORT, export_parent=export_parent)
    receipt = owner.export_metadata()
    assert receipt["valid"]
    assert Path(receipt["path"]).parent == export_parent
    assert verify_export(Path(receipt["path"]))["valid"]
    snapshot, parts = read_export(receipt)
    restored = export_module.restore_camera_identity_metadata(
        snapshot,
        parts,
        expected_original_diagnostics_sha256=export_module._sha(diagnostic),
    )
    assert restored == diagnostic
    assert restored["cycles"][0] == cycle
    assert snapshot["reconstruction_status"] == "ORIGINAL_BYTES_RECONSTRUCTIBLE"

    # A new owner explicitly reopens the same actual original store. No live
    # metadata/helper owners are supplied or repopulated by original readback.
    fresh_session = session_fixture(workspace)
    fresh_view = perform(fresh_session, "refresh")
    fresh_original = read_original(fresh_session, header)
    assert fresh_original == reviewed
    assert (
        fresh_view["verification"]["session"]["head_sha256"] == before.head.head_sha256
    )
    assert all(row["state"] == "PENDING" for row in fresh_view["stages"][4:])
    fresh, fresh_acquisition = adopt_actual_original(
        fresh_session, fresh_original, launch_id="wizard-" + "9" * 32
    )
    assert fresh.view()["launch_session_id"] != owner.launch_id
    assert fresh.view()["original_context"] == owner.view()["original_context"]
    assert fresh.view()["cycles"] == owner.view()["cycles"]
    assert fresh.view()["status"] == "REVIEWED_BLOCKED"
    assert (
        fresh.blocked_reason(service_module.SUBMIT, native_camera=None, helper=None)
        is not None
    )
    assert fresh_acquisition.view()["reviewed_endpoint"] is None
    assert fresh.setup.session.retained_source_workflow() == reviewed
    print(
        f"actual original session: {descriptor['session_id']}; stage4 BLOCKED; later stages PENDING"
    )
