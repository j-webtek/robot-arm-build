"""Original service/NTFS handoff fault injection, never a capable native owner."""

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.camera_capture_checksum import CameraCaptureChecksum
from rocell.application.camera_sealed_capture_evidence import (
    SealedCameraCaptureEvidence,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_camera_configuration_originals import make_context, WINDOWS
from test_camera_original_configuration_service import run_capture
from test_camera_activation_dispatch_handoff import install_owner
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner


@WINDOWS
@pytest.mark.parametrize(
    "fault", ["changed-pixels", "checksum", "receipt", "lease-exit", "missing-pixels"]
)
def test_sealed_readback_fault_never_publishes_or_replays(tmp_path, monkeypatch, fault):
    c = make_context(tmp_path, monkeypatch, sealed_configuration_capture=True)
    owners = install_owner(
        tmp_path, monkeypatch, purpose="capture", pixels=fault != "missing-pixels"
    )
    reads, handoffs = [], []
    read = M1PhysicalCameraTransaction.read_camera_activation_evidence

    def observed_read(tx, attempt):
        value = read(tx, attempt)
        if type(value) is SealedCameraCaptureEvidence:
            reads.append(tx)
            if fault == "checksum":
                data = value.checksum.to_dict()
                data["frame"]["sha256"] = "a" * 64
                return SealedCameraCaptureEvidence(
                    value.native, CameraCaptureChecksum(canonical(data))
                )
        return value

    monkeypatch.setattr(
        M1PhysicalCameraTransaction, "read_camera_activation_evidence", observed_read
    )
    transaction = M1PhysicalCameraPersistence.transaction

    @contextmanager
    def exiting(store, leases):
        with transaction(store, leases) as tx:
            yield tx
        if fault == "lease-exit" and tx in reads:
            raise ValueError("MODELED_ORIGINAL_READBACK_EXIT_FAILED")

    monkeypatch.setattr(M1PhysicalCameraPersistence, "transaction", exiting)
    if fault == "receipt":
        original_result = M1PhysicalCameraTransaction.read_campaign_result

        def substituted(tx, attempt):
            value = original_result(tx, attempt)
            if value.receipt is not None and len(value.receipt.evidence_sha256s) == 3:
                return replace(
                    value,
                    receipt=replace(
                        value.receipt,
                        evidence_sha256s=value.receipt.evidence_sha256s[:2]
                        + ("f" * 64,),
                    ),
                )
            return value

        monkeypatch.setattr(
            M1PhysicalCameraTransaction, "read_campaign_result", substituted
        )
    stage = c.service.stage_retained_capture

    def handoff(*args, **kwargs):
        handoffs.append(kwargs["capture_checksum"])
        # The actual original transaction and OS leases have ended before any
        # pixel ingestion, even though the stored capture itself succeeded.
        assert reads and not c.runtime.verify(c.service.session_id).active_lease_owners
        for tx in reads:
            with pytest.raises(
                M1CommissioningPersistenceError, match="scope has ended"
            ):
                tx._check_scope()
        if fault == "changed-pixels":
            path = (
                Path(
                    kwargs["expected_preparation"].camera_plan.request.output_directory
                )
                / "frame-000000.yuy2"
            )
            with path.open("r+b") as stream:
                stream.write(b"\xff")
        return stage(*args, **kwargs)

    monkeypatch.setattr(c.service, "stage_retained_capture", handoff)
    with pytest.raises(ValueError):
        run_capture(c)
    assert len(owners) == 1 and owners[0].cleaned
    assert len(handoffs) == int(fault == "changed-pixels")
    assert c.service.cache_published_preview("image-" + "7" * 32) is None
    packet = c.service.retained_configuration_diagnostics()
    assert packet["admission"]["status"] == "FAILED_HELD"
    if fault == "missing-pixels":
        assert packet["dispatch"]["transaction"]["attempt_state"] == "SEALED_UNCERTAIN"
        assert (
            packet["dispatch"]["original_evidence"]["capture_checksum"]["status"]
            == "PIXEL_READ_FAILED"
        )
    # Ingestion failures also withdraw the published settings owner. That earlier
    # eligibility guard may reject first; the consumed claim must still remain.
    assert "MODELED-settings-original" in c.service._original_configuration_claims
    with pytest.raises(ValueError):
        run_capture(c)
    assert len(owners) == 1
