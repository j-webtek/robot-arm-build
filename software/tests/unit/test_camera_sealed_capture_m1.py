"""Real NTFS/M1 capture collection retention, modeled predecessors/native bytes.

This tests original write/read/reopen and corruption, not the camera hardware,
production source/predecessor qualification or public capture-collector wiring.
"""

from dataclasses import replace
import json

import pytest

from rocell.application.camera_sealed_capture_contract import is_sealed_capture
from rocell.application.camera_sealed_capture_evidence import (
    checksum_part_name,
    index_name,
)
from rocell.application.cell_commissioning_coordinator import (
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
    PHYSICAL_CAMERA_COMPOSITION,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    physical_camera_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_storage import (
    QualifiedWindowsOnboardingPublication,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_sealed_capture_contract import sealed_profile, sealed_execution
from test_commissioning_camera_persistence import (
    runtime_and_adapter,
    facts,
    records_root,
    WINDOWS,
    forbid_device_and_process_calls,
)
import test_commissioning_camera_persistence as fixture
from test_physical_camera_coordinator import CELL, SESSION, SOURCE, LEASES
from test_native_camera_activation_supervisor import Clock, no_physical_owner

pytestmark = [WINDOWS, pytest.mark.slow]


def components(tmp_path, monkeypatch, *, status="CAPTURE_BYTES_HASHED", fault=None):
    reg = sealed_profile()
    monkeypatch.setattr(fixture, "STAGE", reg.stage)
    runtime, store = runtime_and_adapter(tmp_path)
    clock = Clock()

    class Worker:
        composition = PHYSICAL_CAMERA_COMPOSITION
        worker_executable_sha256 = reg.worker_executable_sha256
        calls = 0
        execution = None

        def run_scoped_campaign(
            self, permit, *, deadline_ns, cancellation, authorization
        ):
            self.calls += 1
            authorization.acknowledge(permit)
            self.execution = sealed_execution(
                tmp_path,
                monkeypatch,
                permit,
                deadline_ns,
                status=status,
                fault=fault,
                clock=clock,
                current=lambda exact: authorization.revalidate(permit),
            )
            return self.execution

    worker = Worker()
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(reg,),
        workers={reg.worker_id: worker},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
        monotonic_ns=clock,
    )
    request = RegisteredActionRequest(
        CELL, SESSION, reg.action_id, "sealed-capture-original", "1" * 64
    )
    with store.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    permit = core.prepare(request)
    return runtime, store, core, worker, permit


@pytest.mark.parametrize(
    "status,fault",
    [
        ("CAPTURE_BYTES_HASHED", None),
        ("PIXEL_READ_FAILED", None),
        ("PIXEL_READ_INTERRUPTED", None),
        ("PIXEL_READ_NOT_ATTESTED", None),
        ("CAPTURE_BYTES_HASHED", "bad-result"),
    ],
)
def test_exact_original_collection_and_receipt_survive_fresh_store_reopen(
    tmp_path, monkeypatch, status, fault
):
    runtime, store, core, worker, permit = components(
        tmp_path, monkeypatch, status=status, fault=fault
    )
    assert is_sealed_capture(permit)
    result = core.execute(permit)
    expected_known = status == "CAPTURE_BYTES_HASHED" and fault is None
    assert result.state is (
        AttemptState.SEALED_KNOWN if expected_known else AttemptState.SEALED_UNCERTAIN
    )
    assert result.quarantine_latched is (not expected_known)
    assert worker.calls == 1 and worker.execution is not None
    with store.transaction(LEASES) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert (
            tx.read_camera_activation_evidence(permit.attempt_id)
            == worker.execution.evidence
        )
    assert core.execute(permit) == result and worker.calls == 1
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=facts
    )
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        original = tx.read_camera_activation_evidence(permit.attempt_id)
        assert original == worker.execution.evidence
        if result.receipt:
            assert result.receipt.evidence_sha256s == original.evidence_sha256s
            assert result.receipt.frames == 1
    assert not reopened.verify(SESSION).active_lease_owners
    assert worker.calls == 1


@pytest.mark.parametrize("fault", ["missing", "rehash"])
def test_original_receipt_rejects_removed_or_self_rehashed_checksum(
    tmp_path, monkeypatch, fault
):
    import base64

    runtime, store, core, worker, permit = components(tmp_path, monkeypatch)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    root = records_root(runtime)
    part_path = root / checksum_part_name(permit.attempt_id)
    if fault == "missing":
        part_path.unlink()
    else:
        # Change all part/index/self hashes consistently. The original lifecycle
        # receipt still binds the earlier checksum subject and must reject this.
        part = json.loads(part_path.read_bytes())
        checksum = json.loads(base64.b64decode(part["data"]["payload_base64"]))
        checksum["frame"]["sha256"] = "d" * 64
        payload = canonical(checksum)
        part["data"].update(
            payload_base64=base64.b64encode(payload).decode("ascii"),
            payload_sha256=digest(payload),
            payload_bytes=len(payload),
        )
        final_path = root / index_name(permit.attempt_id)
        final = json.loads(final_path.read_bytes())
        final["data"]["checksum"].update(
            payload_sha256=digest(payload), payload_bytes=len(payload)
        )
        for path, record in ((part_path, part), (final_path, final)):
            record["record_sha256"] = digest(
                canonical_json_bytes(
                    {
                        key: value
                        for key, value in record.items()
                        if key != "record_sha256"
                    }
                )
            )
            path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(
        (ValueError, RuntimeError),
        match="invalid original camera activation evidence|camera receipt disagrees",
    ):
        with store.transaction(LEASES) as tx:
            tx.read_campaign_result(permit.attempt_id)
    assert worker.calls == 1


def test_failed_index_write_preserves_partial_parts_and_never_replays_capture(
    tmp_path, monkeypatch
):
    runtime, store, core, worker, permit = components(tmp_path, monkeypatch)
    original = QualifiedWindowsOnboardingPublication.write_new_file
    writes = []

    def failing(publication, path, payload):
        if path.name == index_name(permit.attempt_id) and path.parent == records_root(
            runtime
        ):
            writes.append(path)
            raise OSError("MODELED_DISK_FULL_AT_FINAL_CAPTURE_INDEX")
        return original(publication, path, payload)

    monkeypatch.setattr(
        QualifiedWindowsOnboardingPublication, "write_new_file", failing
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert len(writes) == 1 and worker.calls == 1
    assert (records_root(runtime) / checksum_part_name(permit.attempt_id)).is_file()
    assert not (records_root(runtime) / index_name(permit.attempt_id)).exists()
    assert core.execute(permit) == result and worker.calls == 1
    with store.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        with pytest.raises(M1CommissioningPersistenceError, match="incomplete"):
            tx.read_camera_activation_evidence(permit.attempt_id)
