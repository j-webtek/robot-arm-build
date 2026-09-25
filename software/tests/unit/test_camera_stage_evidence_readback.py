"""Original-store readback with actual NTFS leases, never device access."""

from dataclasses import replace
import os
from pathlib import Path
from typing import Any

import pytest

import rocell.application.commissioning_camera_persistence as module
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from test_commissioning_camera_persistence import runtime_and_adapter
from test_physical_camera_coordinator import LEASES, SESSION


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="actual NTFS and Windows leases"
)
PAYLOAD = b'{"provenance":"INCAPABLE_READBACK_TEST","physical_authority":false}'


@pytest.fixture(autouse=True)
def no_devices(monkeypatch):
    import subprocess

    def denied(*args: Any, **kwargs: Any):
        pytest.fail(
            "stage evidence readback must not execute processes or access devices"
        )

    monkeypatch.setattr(subprocess, "Popen", denied)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, denied)


def retain(tx):
    tx.commit_stage_state(
        STAGE_ORDER[0],
        V2StageState.WAITING_OPERATOR,
        occurred_at_ns=2001,
        detail_code="INCAPABLE_READBACK_TEST_WAITING",
        expected_head_sha256=tx.snapshot().head.head_sha256,
    )
    return tx.store_evidence(
        STAGE_ORDER[0],
        PAYLOAD,
        label="incapable original byte readback fixture",
        media_type="application/json",
        captured_at_ns=2002,
        expected_head_sha256=tx.snapshot().head.head_sha256,
    )


def stage(adapter):
    return adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    )


def test_original_readback_is_exact_scoped_and_never_passes_pending_stages(tmp_path):
    _, adapter = runtime_and_adapter(tmp_path, ready=False)
    with stage(adapter) as tx:
        ref = retain(tx)
        head = tx.snapshot().head.head_sha256
        assert tx.read_stage_evidence(ref) == PAYLOAD
        assert tx.snapshot().head.head_sha256 == head
        assert tx.snapshot().stages[0].state is V2StageState.WAITING_OPERATOR
        assert all(
            row.state is V2StageState.PENDING for row in tx.snapshot().stages[1:]
        )
        invalid = (
            ref.to_dict(),
            replace(ref, payload_bytes=True),
            replace(ref, payload_bytes=ref.payload_bytes + 1),
            replace(ref, payload_sha256="f" * 64),
            replace(ref, evidence_id="../elsewhere"),
            replace(ref, stage=STAGE_ORDER[1]),
        )
        for changed in invalid:
            with pytest.raises(M1CommissioningPersistenceError):
                tx.read_stage_evidence(changed)
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        tx.read_stage_evidence(ref)
    with adapter.transaction(LEASES) as camera_tx:
        with pytest.raises(M1CommissioningPersistenceError, match="stage-only"):
            camera_tx.read_stage_evidence(ref)
    # A new original-store stage scope can still read; no replay or new package.
    with stage(adapter) as original:
        assert original.read_stage_evidence(ref) == PAYLOAD
        assert len(original.snapshot().evidence) == 1


def test_readback_independently_checks_opened_bytes_and_postread_scope(
    tmp_path, monkeypatch
):
    _, adapter = runtime_and_adapter(tmp_path, ready=False)
    with stage(adapter) as tx:
        ref = retain(tx)
        real_read = module.read_bounded_regular_file
        with monkeypatch.context() as patch:
            patch.setattr(
                module, "read_bounded_regular_file", lambda *a, **k: b"x" * len(PAYLOAD)
            )
            with pytest.raises(
                M1CommissioningPersistenceError, match="payload changed"
            ):
                tx.read_stage_evidence(ref)
        with monkeypatch.context() as patch:
            patch.setattr(
                module, "read_bounded_regular_file", lambda *a, **k: PAYLOAD + b"x"
            )
            with pytest.raises(
                M1CommissioningPersistenceError, match="payload changed"
            ):
                tx.read_stage_evidence(ref)

        def end_scope(path, **kwargs):
            assert kwargs["maximum_bytes"] == len(PAYLOAD)
            value = real_read(path, **kwargs)
            tx.close_scope()
            return value

        monkeypatch.setattr(module, "read_bounded_regular_file", end_scope)
        with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
            tx.read_stage_evidence(ref)


@pytest.mark.parametrize("fault", ["payload", "manifest", "extra-file", "hardlink"])
def test_changed_original_package_is_rejected_without_repair(tmp_path, fault):
    _, adapter = runtime_and_adapter(tmp_path, ready=False)
    with stage(adapter) as tx:
        ref = retain(tx)
        package = tx._session.directory / "evidence" / ref.evidence_id
        target = package / "payload.bin"
        if fault == "payload":
            target.write_bytes(b"x" * len(PAYLOAD))
        elif fault == "manifest":
            (package / "manifest.json").write_bytes(b"{}\n")
        elif fault == "extra-file":
            (package / "unexpected.bin").write_bytes(b"unchanged evidence retained")
        else:
            os.link(target, tmp_path / "alias.bin")
        with pytest.raises((ValueError, RuntimeError, OSError)):
            tx.read_stage_evidence(ref)
        assert target.exists()
        if fault == "payload":
            assert target.read_bytes() == b"x" * len(PAYLOAD)
        elif fault == "manifest":
            assert (package / "manifest.json").read_bytes() == b"{}\n"
        elif fault == "extra-file":
            assert (package / "unexpected.bin").exists()
        else:
            assert (tmp_path / "alias.bin").exists()


def test_full_package_is_reverified_after_payload_read(tmp_path, monkeypatch):
    _, adapter = runtime_and_adapter(tmp_path, ready=False)
    with stage(adapter) as tx:
        ref = retain(tx)
        real_read = module.read_bounded_regular_file

        def change_manifest(path: Path, **kwargs):
            payload = real_read(path, **kwargs)
            (path.parent / "manifest.json").write_bytes(b"{}\n")
            return payload

        monkeypatch.setattr(module, "read_bounded_regular_file", change_manifest)
        with pytest.raises((ValueError, RuntimeError)):
            tx.read_stage_evidence(ref)
