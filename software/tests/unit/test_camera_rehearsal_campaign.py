"""Binary fixture checks; these tests never invoke a device or native helper."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from rocell.application.camera_rehearsal_campaign import (
    FRAME_BYTES,
    SyntheticBinaryCameraWorker,
    camera_settings,
)

WORKSPACE = Path(__file__).resolve().parents[3]


def worker(root, count=1, fault="none", offset=0):
    settings = camera_settings(offset)
    epoch = hashlib.sha256(
        json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return SyntheticBinaryCameraWorker(
        WORKSPACE,
        root,
        executable_sha256="b" * 64,
        source_sha256="a" * 64,
        frame_count=count,
        fault=fault,
        settings=settings,
        settings_epoch=epoch,
    )


def permit():
    return SimpleNamespace(
        attempt_id="attempt-fixture-001",
        permit_sha256="c" * 64,
        admission=SimpleNamespace(selected_identity_sha256="d" * 64),
    )


def test_construction_is_inert_and_settings_are_not_driver_controls(tmp_path):
    instance = worker(tmp_path / "not-created")
    assert instance.capture is None
    assert list(tmp_path.iterdir()) == []
    assert (
        camera_settings(0)["exposure_policy"]
        == "SYNTHETIC_LUMA_OFFSET_NOT_DRIVER_CONTROL"
    )


@pytest.mark.parametrize("value", [True, 0.0, -65, 65, "0", None])
def test_settings_reject_widening(value):
    with pytest.raises(ValueError):
        camera_settings(value)


@pytest.mark.parametrize("count", [0, 5, True, 1.0])
def test_frame_count_is_finite(tmp_path, count):
    with pytest.raises(ValueError):
        worker(tmp_path, count=count)


def test_cancel_before_work_creates_nothing(tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(RuntimeError, match="cancelled"):
        worker(tmp_path).run_campaign(
            permit(), deadline_ns=time.monotonic_ns() + 10**9, cancellation=cancel
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("fault", ["identity-mismatch", "cleanup-uncertain"])
def test_faults_report_uncertainty_without_fake_binary_success(tmp_path, fault):
    instance = worker(tmp_path, fault=fault)
    receipt = instance.run_campaign(
        permit(),
        deadline_ns=time.monotonic_ns() + 10**9,
        cancellation=threading.Event(),
    )
    assert receipt.evidence_sha256s == ()
    assert instance.capture is None
    assert list(tmp_path.iterdir()) == []
    if fault == "identity-mismatch":
        assert receipt.selected_identity_sha256 != "d" * 64
    else:
        assert receipt.cleanup_confirmed is False


def test_full_sized_binary_frame_is_retained_and_preview_comes_from_ingestion(tmp_path):
    instance = worker(tmp_path, offset=-12)
    receipt = instance.run_campaign(
        permit(),
        deadline_ns=time.monotonic_ns() + 60 * 10**9,
        cancellation=threading.Event(),
    )
    capture = instance.capture
    assert capture.verification.content_verified
    assert capture.verification.plan.binding.provenance == "SYNTHETIC"
    assert capture.dataset.logical_bytes >= FRAME_BYTES
    assert len(list(tmp_path.rglob("*.yuy2"))) == 1
    assert next(tmp_path.rglob("*.yuy2")).stat().st_size == FRAME_BYTES
    assert capture.latest_preview.png_bytes.startswith(b"\x89PNG")
    assert capture.latest_preview.transform.output_width == 912
    assert capture.dataset.manifest_sha256 in receipt.evidence_sha256s
    assert capture.envelope_sha256 in receipt.evidence_sha256s
    assert capture.to_dict()["physical_authority"] is False
    assert capture.to_dict()["m1_qualified"] is False
