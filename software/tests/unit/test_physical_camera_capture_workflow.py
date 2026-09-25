"""Production lifecycle with modeled native observations + real tiny YUY2 files.

No process, camera, metadata collector or serial device runs. The source hash,
native process facts and driver reports are explicit test models, not physical
observations. Windows file guards and actual dataset/PNG bytes are exercised.
"""

from dataclasses import asdict, replace
from contextlib import contextmanager
import hashlib
import io
from pathlib import Path
import subprocess
from threading import Event
from types import SimpleNamespace

import pytest
from PIL import Image

from rocell.application import physical_camera_capture_workflow as module
from rocell.application.camera_capture_dataset import iter_native_frame
from rocell.application.physical_native_camera_campaign import (
    PhysicalNativeCameraCampaign,
)
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_capture_registration import (
    create_native_camera_capture_runtime_registration,
)
from rocell.providers.windows.native_camera_capture_registration import (
    PreparedOwnedNativeCapture,
)
from rocell.providers.windows.native_camera_registration import (
    create_native_camera_runtime_registration,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_configuration import modeled_native_evidence, reported_control
from test_physical_camera_coordinator import CELL, SESSION, SOURCE
from test_physical_camera_selection import physical_enrollment, selected
from test_windows_camera_worker import receipt


@pytest.fixture(autouse=True)
def no_device_or_process_calls(monkeypatch):
    def denied(*a, **kw):
        pytest.fail("capture workflow attempted a native helper/process/device call")

    monkeypatch.setattr(subprocess, "Popen", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)


def workflow_fixture(tmp_path, monkeypatch, *, fault=None, count=1, accepted=False):
    """Shared modeled producer; actual files only beneath the test-owned root.

    Returns SimpleNamespace(workflow,args,kwargs,probe,probe_evidence,
    capabilities,configuration,capture,capture_evidence,raw,pixels,result).
    `accepted=True` runs the real file validator/ingester/verifier. Original
    native evidence itself is deliberately modeled, never a fixture-origin
    assertion admitted by a real physical service or M1 store.
    """
    workspace, parent = tmp_path / "workspace", tmp_path / "assigned"
    kwargs = dict(
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
        selection=selected(physical_enrollment()),
        probe_runtime=create_native_camera_runtime_registration(
            workspace,
            source_sha256=SOURCE,
            catalog_sha256="b" * 64,
            helper_sha256="c" * 64,
            build_record_sha256="d" * 64,
        ),
        capture_runtime=create_native_camera_capture_runtime_registration(
            workspace,
            source_sha256=SOURCE,
            catalog_sha256="8" * 64,
            helper_sha256="9" * 64,
            build_record_sha256="7" * 64,
        ),
    )
    workflow = module.PhysicalCameraCaptureWorkflow(workspace, parent, **kwargs)
    monkeypatch.setattr(module, "source_fingerprint", lambda path: SOURCE)
    base = PhysicalNativeCameraCampaign(
        workspace,
        parent,
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
        selection=kwargs["selection"],
        runtime=kwargs["probe_runtime"],
    )
    probe = base._prepare("attempt-probe", "e" * 64)
    raw = receipt("probe")
    endpoint = kwargs["selection"].binding.symbolic_link
    raw["selected_endpoint"] = endpoint
    raw["devices"][0]["symbolic_link"] = endpoint
    raw["controls"] = [reported_control("brightness")]
    pe = modeled_native_evidence(probe, raw)
    capabilities = workflow.accept_probe(
        pe, expected_preparation=probe, expected_evidence_sha256=pe.evidence_sha256
    )
    config = workflow.stage_settings(
        capabilities.view()["modes"][0]["choice_id"],
        (CameraControlSetting("brightness", 4),),
        expected_capabilities_sha256=capabilities.capabilities_sha256,
    )
    plan = workflow.capture_plan(
        budget=CameraCampaignBudget(5000, count, 16, 16 * count)
    )
    capture = PhysicalNativeCameraCampaign.from_plan(plan)._prepare(
        "attempt-capture", "f" * 64
    )
    raw = receipt("capture")
    raw["selected_endpoint"] = endpoint
    raw["devices"][0]["symbolic_link"] = endpoint
    raw["requested_mode"] = asdict(config.mode)
    raw["controls"] = [reported_control("brightness", 4)]
    raw["counts"].update(
        control_set_attempts=1, samples_received=count, frames_written=count
    )
    raw["frames"] = [
        {
            **raw["frames"][0],
            "filename": f"frame-{i:06d}.yuy2",
            "host_sequence": i,
            "media_timestamp_100ns": i * 10_000,
            "host_arrival_qpc": 1234567 + i * 10_000,
        }
        for i in range(count)
    ]
    if fault == "readback-drift":
        raw["controls"][0]["minimum"] = -2
    if fault == "native-cleanup":
        raw.update(status="FAILED", reason_code="SOURCE_SHUTDOWN_FAILED")
        raw["cleanup"]["source_shutdown_hr"] = -1
    ce = modeled_native_evidence(
        capture,
        raw,
        cleanup=("CLOSE_FAILED:job",) if fault == "process-cleanup" else (),
    )
    pixels = bytes(
        [16, 128, 56, 128, 96, 128, 136, 128, 36, 128, 76, 128, 116, 128, 156, 128]
    )
    output = Path(capture.camera_plan.request.output_directory)
    output.mkdir(parents=True)
    for row in raw["frames"]:
        (output / row["filename"]).write_bytes(pixels)
    result = None
    if accepted:
        result = workflow.accept_capture(
            ce,
            expected_preparation=capture,
            expected_evidence_sha256=ce.evidence_sha256,
            expected_settings_epoch=config.settings_epoch,
            cancellation=Event(),
        )
    return SimpleNamespace(
        workflow=workflow,
        args=(workspace, parent),
        kwargs=kwargs,
        probe=probe,
        probe_evidence=pe,
        capabilities=capabilities,
        configuration=config,
        capture=capture,
        capture_evidence=ce,
        raw=raw,
        pixels=pixels,
        result=result,
    )


def accept(f, **overrides):
    args = dict(
        expected_preparation=f.capture,
        expected_evidence_sha256=f.capture_evidence.evidence_sha256,
        expected_settings_epoch=f.configuration.settings_epoch,
        cancellation=Event(),
    )
    args.update(overrides)
    return f.workflow.accept_capture(f.capture_evidence, **args)


def test_actual_small_pixels_full_lifecycle_is_not_m1_or_hardware_acceptance(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch, count=2, accepted=True)
    result, view = f.result, f.workflow.view()
    assert result is not None and result.verification.content_verified
    assert result.domain == "PHYSICAL_UNVERIFIED" and not result.m1_qualified
    assert view["status"] == "CONTENT_VERIFIED"
    assert view["physical_authority"] is view["hardware_qualified"] is False
    assert view["configuration"]["readback"]["frame_content_verified"] is False
    assert view["last_frame"]["frame_content_verified"] is True
    assert view["last_frame"]["live"] is False
    assert view["last_frame"]["frame_index"] == 1
    assert (
        view["last_frame"]["native_frame_sha256"]
        == hashlib.sha256(f.pixels).hexdigest()
    )
    assert b"".join(iter_native_frame(result.dataset.path, "frame-000001")) == f.pixels
    preview = f.workflow.last_preview()
    assert preview is not None
    with Image.open(io.BytesIO(preview.png_bytes)) as image:
        assert image.size == (4, 2)
        assert image.getpixel((0, 0)) == (0, 0, 0)
    diagnostics = f.workflow.retained_diagnostics()
    assert diagnostics["capture"] == f.capture_evidence.to_dict()
    assert diagnostics["ingest"] == result.to_dict()
    assert f.probe.runtime.registration_sha256 != f.capture.runtime.registration_sha256
    assert result.envelope_path.parent.parent == f.args[1] / "capture-datasets"


def test_constructor_and_cached_operations_are_inert_detached(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch)

    def noio(*a, **kw):
        pytest.fail("cached/pure operation performed I/O")

    with monkeypatch.context() as m:
        for name in ("open", "stat", "mkdir", "iterdir", "resolve"):
            m.setattr(Path, name, noio)
        m.setattr(module, "source_fingerprint", noio)
        fresh = module.PhysicalCameraCaptureWorkflow(*f.args, **f.kwargs)
        assert fresh.view()["status"] == "HELD"
        assert fresh.last_preview() is None
        clone = f.workflow.staged_copy()
        clone.view()["configuration"]["candidate"]["controls"].clear()
        clone.retained_diagnostics().clear()
        assert f.workflow.view()["configuration"]["candidate"]["controls"]
        assert f.workflow.retained_diagnostics()
        assert clone.capture_plan(budget=CameraCampaignBudget(5000, 1, 16, 16))


@pytest.mark.parametrize(
    "fault", ["readback-drift", "native-cleanup", "process-cleanup"]
)
def test_failed_readback_retained_without_file_access(tmp_path, monkeypatch, fault):
    f = workflow_fixture(tmp_path, monkeypatch, fault=fault)
    monkeypatch.setattr(
        module,
        "validate_capture_artifacts",
        lambda *a, **kw: pytest.fail("mismatched readback read files"),
    )
    assert accept(f) is None
    assert f.workflow.view()["status"] == "HELD"
    assert f.workflow.last_preview() is None
    assert f.workflow.retained_diagnostics()["capture"] == f.capture_evidence.to_dict()
    assert (
        f.workflow.view()["configuration"]["readback"]["status"]
        == "READBACK_MISMATCH_UNQUALIFIED"
    )


@pytest.mark.parametrize(
    "fault", ["wrong-hash", "wrong-settings", "cancelled", "expired"]
)
def test_rejected_before_binary_retention(tmp_path, monkeypatch, fault):
    f = workflow_fixture(tmp_path, monkeypatch)
    extra = {}
    if fault == "wrong-hash":
        extra["expected_evidence_sha256"] = "0" * 64
    if fault == "wrong-settings":
        extra["expected_settings_epoch"] = "0" * 64
    if fault == "cancelled":
        event = Event()
        event.set()
        extra["cancellation"] = event
    if fault == "expired":
        extra["deadline_ns"] = 1
    with pytest.raises(ValueError):
        accept(f, **extra)
    assert not (f.args[1] / "capture-datasets").exists()
    assert f.workflow.last_preview() is None


@pytest.mark.parametrize("fault", ["missing", "length", "extra"])
def test_original_files_not_metadata_are_required(tmp_path, monkeypatch, fault):
    f = workflow_fixture(tmp_path, monkeypatch)
    directory = Path(f.capture.camera_plan.request.output_directory)
    file = directory / "frame-000000.yuy2"
    if fault == "missing":
        file.unlink()
    elif fault == "length":
        file.write_bytes(b"bad")
    else:
        (directory / "extra.yuy2").write_bytes(b"extra")
    with pytest.raises(Exception):
        accept(f)
    assert (
        f.workflow.retained_diagnostics()["readback"]["status"]
        == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
    )
    assert f.workflow.last_preview() is None
    assert not (f.args[1] / "capture-datasets").exists()


def test_replay_is_refused_across_discarded_staged_publication(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch)
    original = f.workflow
    f.workflow = original.staged_copy()
    assert accept(f) is not None
    assert original.last_preview() is None
    f.workflow = original.staged_copy()
    with pytest.raises(
        module.PhysicalCameraCaptureWorkflowError, match="ALREADY_ATTEMPTED"
    ):
        accept(f)


def test_invalidate_preserves_full_historical_bytes_not_current_image(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch, accepted=True)
    retained = f.workflow.retained_diagnostics()
    f.workflow.invalidate()
    assert f.workflow.view()["configuration"] == dict(
        capabilities=None, candidate=None, readback=None
    )
    assert f.workflow.last_preview() is None
    assert f.workflow.retained_diagnostics() == retained


@pytest.mark.parametrize(
    "boundary", ["validate_capture_artifacts", "verify_windows_capture_ingest"]
)
@pytest.mark.parametrize("fault", ["cancel", "timeout", "source"])
def test_late_sync_work_never_publishes_current_pixels(
    tmp_path, monkeypatch, boundary, fault
):
    f = workflow_fixture(tmp_path, monkeypatch)
    real = getattr(module, boundary)
    event = Event()
    now = module.time.monotonic_ns()

    def wrapped(*a, **kw):
        result = real(*a, **kw)
        if fault == "cancel":
            event.set()
        elif fault == "timeout":
            monkeypatch.setattr(
                module.time, "monotonic_ns", lambda: now + 200_000_000_000
            )
        else:
            monkeypatch.setattr(module, "source_fingerprint", lambda path: "0" * 64)
        return result

    monkeypatch.setattr(module, boundary, wrapped)
    with pytest.raises(ValueError):
        accept(f, cancellation=event)
    assert f.workflow.last_preview() is None
    assert f.workflow.view()["status"] == "HELD"
    assert f.workflow.retained_diagnostics()["capture"] == f.capture_evidence.to_dict()
    if boundary == "verify_windows_capture_ingest":
        assert "ingest" in f.workflow.retained_diagnostics()


@pytest.mark.parametrize("field", ["session_id", "operation_sha256", "permit_sha256"])
def test_exact_preparation_and_independent_evidence_are_not_interchangeable(
    tmp_path, monkeypatch, field
):
    f = workflow_fixture(tmp_path, monkeypatch)
    value = f.capture.to_dict()
    value["admission_request"][field] = (
        "another-session" if field == "session_id" else "0" * 64
    )
    other = PreparedOwnedNativeCapture(canonical(value))
    # A changed permit is meaningful only if its original independently trusted
    # preparation and full evidence both match. Here original evidence must fail.
    with pytest.raises(ValueError):
        accept(f, expected_preparation=other)
    assert not (f.args[1] / "capture-datasets").exists()


@pytest.mark.parametrize("which", ["probe", "capture"])
def test_different_assigned_parent_is_not_an_original_store(
    tmp_path, monkeypatch, which
):
    f = workflow_fixture(tmp_path / "first", monkeypatch)
    other = workflow_fixture(tmp_path / "second", monkeypatch)
    if which == "probe":
        with pytest.raises(
            module.PhysicalCameraCaptureWorkflowError, match="CONTEXT_MISMATCH"
        ):
            f.workflow.accept_probe(
                other.probe_evidence,
                expected_preparation=other.probe,
                expected_evidence_sha256=other.probe_evidence.evidence_sha256,
            )
    else:
        with pytest.raises(
            module.PhysicalCameraCaptureWorkflowError, match="CONTEXT_MISMATCH"
        ):
            f.workflow.accept_capture(
                other.capture_evidence,
                expected_preparation=other.capture,
                expected_evidence_sha256=other.capture_evidence.evidence_sha256,
                expected_settings_epoch=f.configuration.settings_epoch,
                cancellation=Event(),
            )
    assert f.workflow.last_preview() is None


def test_source_change_before_retention_does_not_create_dataset(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: "0" * 64)
    with pytest.raises(
        module.PhysicalCameraCaptureWorkflowError, match="SOURCE_CHANGED"
    ):
        accept(f)
    assert not (f.args[1] / "capture-datasets").exists()
    assert f.workflow.retained_diagnostics()["capture"] == f.capture_evidence.to_dict()


@pytest.mark.parametrize("fault", ["raise", "cancel", "timeout", "invalidate"])
def test_last_guard_exit_failure_withholds_current_but_keeps_verified_diagnostics(
    tmp_path, monkeypatch, fault
):
    f = workflow_fixture(tmp_path, monkeypatch)
    original = module._directory_guard
    event = Event()
    now = module.time.monotonic_ns()

    @contextmanager
    def guarded(path):
        with original(path):
            yield
        if path == f.args[1]:
            if fault == "raise":
                raise OSError("modeled file guard exit failure")
            elif fault == "cancel":
                event.set()
            elif fault == "timeout":
                monkeypatch.setattr(
                    module.time, "monotonic_ns", lambda: now + 200_000_000_000
                )
            else:
                f.workflow.invalidate()

    monkeypatch.setattr(module, "_directory_guard", guarded)
    with pytest.raises((ValueError, OSError)):
        accept(f, cancellation=event)
    assert f.workflow.last_preview() is None
    assert f.workflow.retained_diagnostics()["ingest"]["verification"][
        "content_verified"
    ]


def test_new_settings_clear_stale_content_even_when_invalid(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch, accepted=True)
    with pytest.raises(ValueError):
        f.workflow.stage_settings(
            "mode-" + "0" * 24,
            (),
            expected_capabilities_sha256=f.capabilities.capabilities_sha256,
        )
    view = f.workflow.view()
    assert view["last_frame"] is None
    assert view["configuration"]["candidate"] is None
    assert view["configuration"]["readback"] is None
    assert "ingest" in f.workflow.retained_diagnostics()


def test_bad_new_probe_clears_old_settings_and_pixels(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch, accepted=True)
    with pytest.raises(ValueError):
        f.workflow.accept_probe(
            f.probe_evidence,
            expected_preparation=f.probe,
            expected_evidence_sha256="0" * 64,
        )
    assert f.workflow.view()["configuration"] == dict(
        capabilities=None, candidate=None, readback=None
    )
    assert f.workflow.last_preview() is None


def test_fixed_retention_budget_does_not_redeem_or_extend_native_deadline(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch)
    assert f.capture_evidence.to_dict()["parent_deadline_ns"] == 20_000_000_000
    # The modeled original native deadline is long past. This distinct bounded
    # file operation neither calls a worker/authorizer nor edits that evidence.
    original = f.capture_evidence.payload
    assert accept(f) is not None
    assert canonical(f.workflow.retained_diagnostics()["capture"]) == original
    assert module.RETENTION_TIMEOUT_MS == 120_000


def test_claim_capacity_is_finite_and_failure_is_not_retried(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch)
    f.workflow._claims.update(f"old-{i}" for i in range(module.MAX_RETENTION_ATTEMPTS))
    with pytest.raises(
        module.PhysicalCameraCaptureWorkflowError, match="ATTEMPT_LIMIT"
    ):
        accept(f)
    assert not (f.args[1] / "capture-datasets").exists()


def test_actual_ingestion_identity_and_manifest_tamper_are_rejected(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch)
    original = module.verify_windows_capture_ingest

    def corrupted(value, **kwargs):
        manifest = Path(value["dataset"]["path"]) / "manifest.json"
        manifest.write_bytes(b"corrupt test-owned manifest")
        return original(value, **kwargs)

    monkeypatch.setattr(module, "verify_windows_capture_ingest", corrupted)
    with pytest.raises(ValueError):
        accept(f)
    assert f.workflow.last_preview() is None
    assert "ingest" in f.workflow.retained_diagnostics()
