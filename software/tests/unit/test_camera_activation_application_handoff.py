"""V2 application composition with modeled native facts and real tiny pixels.

No test starts a helper, enumerates a device, or authenticates physical hardware.
The installed supervisor/codecs and application lifecycle are exercised; only
their process owner and source observation are explicitly modeled. These are
not original-store admission or received-hardware acceptance tests.
"""

from dataclasses import asdict
import hashlib
import io
from pathlib import Path
import subprocess
from threading import Event
from types import SimpleNamespace

import pytest
from PIL import Image

from rocell.application import physical_camera_capture_workflow as workflow_module
from rocell.application.camera_activation_campaign_evidence import (
    camera_activation_evidence,
)
from rocell.application.camera_capture_dataset import iter_native_frame
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.physical_camera_configuration import (
    derive_physical_camera_capabilities,
)
from rocell.application.physical_camera_selection import PhysicalCameraSelection
from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
)
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraWorkerError,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_activation_expectation import (
    CameraActivationExpectation,
)
from rocell.providers.windows.native_camera_activation_registration import (
    NativeCameraActivationRuntime,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_protocol import fixture as result_fixture
from test_native_camera_activation_registration import ready
from test_native_camera_activation_supervisor import (
    ModelOwner,
    Clock,
    no_physical_owner,
)
from test_physical_camera_activation_campaign import campaign
from test_physical_camera_coordinator import SOURCE


PIXELS = bytes([16, 128, 56, 128, 96, 128, 136, 128] * 2)


@pytest.fixture(autouse=True)
def no_device_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Application handoff test attempted process/device access")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)
    monkeypatch.setattr(workflow_module, "source_fingerprint", lambda path: SOURCE)


def observation(directory, monkeypatch, prepared, *, fault=None, raw_change=None):
    """Bind a modeled observation to this exact preparation, then parse normally."""
    purpose = prepared.runtime.to_dict()["purpose"]
    raw_owner, args = modeled(directory, purpose)
    args["ready_wire"] = ready(prepared)
    _, _, raw = result_fixture(purpose)
    request = prepared.admission_request.to_dict()
    raw.update(
        request_sha256=prepared.admission_request.request_sha256,
        permit_sha256=request["permit_sha256"],
    )
    if purpose == "capture":
        raw["native_receipt"]["requested_mode"] = asdict(
            prepared.camera_plan.request.mode
        )
        # The generic wire fixture intentionally has a negative media timestamp;
        # that is useful for protocol tests but not representable by this dataset.
        raw["native_receipt"]["frames"][0]["media_timestamp_100ns"] = 0
    if raw_change is not None:
        raw_change(raw)
    raw_owner.stdout = args["ready_wire"] + canonical(raw) + b"\n"
    owner = ModelOwner(raw_owner, args, fault)
    monkeypatch.setattr(supervisor, "_new_owner", lambda: owner)
    outcome = supervisor._supervise(
        prepared,
        prepared.registration,
        cancellation=Event(),
        deadline_ns=25_000_000_000,
        _clock=Clock(),
        revalidate_consumed_permit=lambda exact: None,
    )
    return camera_activation_evidence(prepared, outcome)


def references(prepared, evidence):
    return dict(
        expected_preparation=prepared,
        expected_evidence_sha256=evidence[0].payload_sha256,
        expected_supervision_sha256=evidence[1].payload_sha256,
    )


def workflow_fixture(
    tmp_path, monkeypatch, *, capture_fault=None, configuration_verification=False,
    sealed_configuration_capture=False,
):
    probe_campaign = campaign(tmp_path)
    plan = probe_campaign.plan()
    workflow = workflow_module.PhysicalCameraCaptureWorkflow(
        tmp_path,
        Path(plan["assigned_parent_directory"]),
        source_sha256=SOURCE,
        cell_id=plan["cell_id"],
        session_id=plan["session_id"],
        selection=PhysicalCameraSelection(canonical(plan["selection"])),
        probe_runtime=NativeCameraActivationRuntime(canonical(plan["runtime"])),
        capture_runtime=NativeCameraActivationRuntime(
            canonical(campaign(tmp_path, "capture").plan()["runtime"])
        ),
        activation_expectation=CameraActivationExpectation(
            canonical(plan["expectation"])
        ),
    )
    probe = probe_campaign._prepare("attempt-probe", "e" * 64)
    probe_evidence = observation(tmp_path, monkeypatch, probe)
    capabilities = workflow.accept_probe(
        probe_evidence, **references(probe, probe_evidence)
    )
    configuration = workflow.stage_settings(
        capabilities.view()["modes"][0]["choice_id"],
        (),
        expected_capabilities_sha256=capabilities.capabilities_sha256,
    )
    capture_plan = workflow.capture_plan(
        budget=CameraCampaignBudget(5000, 1, 16, 16),
        configuration_verification=configuration_verification,
        sealed_configuration_capture=sealed_configuration_capture,
    )
    capture = PhysicalCameraActivationCampaign.from_plan(capture_plan)._prepare(
        "attempt-capture", "f" * 64
    )
    evidence = observation(tmp_path, monkeypatch, capture, fault=capture_fault)
    return SimpleNamespace(
        workflow=workflow,
        probe=probe,
        probe_evidence=probe_evidence,
        capabilities=capabilities,
        configuration=configuration,
        capture=capture,
        evidence=evidence,
    )


def accept(f, **overrides):
    arguments = references(f.capture, f.evidence)
    arguments.update(
        expected_settings_epoch=f.configuration.settings_epoch, cancellation=Event()
    )
    arguments.update(overrides)
    return f.workflow.accept_capture(f.evidence, **arguments)


def write_pixels(f, content=PIXELS):
    output = Path(f.capture.camera_plan.request.output_directory)
    output.mkdir(parents=True)
    (output / "frame-000000.yuy2").write_bytes(content)


def test_v2_probe_settings_capture_ingest_preview_has_explicit_evidence_pair(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch)
    write_pixels(f)
    result = accept(f)
    assert result is not None and result.verification.content_verified
    assert b"".join(iter_native_frame(result.dataset.path, "frame-000000")) == PIXELS
    view = f.workflow.view()
    assert view["status"] == "CONTENT_VERIFIED"
    assert view["physical_authority"] is view["hardware_qualified"] is False
    assert view["configuration"]["readback"]["frame_content_verified"] is False
    assert (
        view["last_frame"]["native_frame_sha256"] == hashlib.sha256(PIXELS).hexdigest()
    )
    assert view["last_frame"]["frame_content_verified"] is True
    assert view["last_frame"]["live"] is False
    with Image.open(io.BytesIO(f.workflow.last_preview().png_bytes)) as image:
        assert image.size == (4, 2)
    diagnostic = f.workflow.retained_diagnostics()
    for name in ("probe", "capture"):
        assert (
            diagnostic[name]["schema"] == "rocell.camera_activation_observation_pair.v2"
        )
        assert set(diagnostic[name]) == {"schema", "run", "supervision"}
    assert f.workflow.staged_copy().retained_diagnostics() == diagnostic


@pytest.mark.parametrize(
    "fault",
    [
        "run-hash",
        "supervision-hash",
        "no-supervision",
        "single-run",
        "reversed",
        "wrong-purpose",
    ],
)
def test_probe_rejects_missing_or_substituted_original_references(
    tmp_path, monkeypatch, fault
):
    f = workflow_fixture(tmp_path, monkeypatch)
    evidence = f.probe_evidence
    arguments = references(f.probe, evidence)
    if fault == "run-hash":
        arguments["expected_evidence_sha256"] = "1" * 64
    elif fault == "supervision-hash":
        arguments["expected_supervision_sha256"] = "1" * 64
    elif fault == "no-supervision":
        arguments.pop("expected_supervision_sha256")
    elif fault == "single-run":
        evidence = (evidence[0],)
    elif fault == "reversed":
        evidence = tuple(reversed(evidence))
    else:
        evidence = f.evidence
        arguments = references(f.capture, evidence)
    with pytest.raises(ValueError):
        derive_physical_camera_capabilities(
            evidence, expected_source_sha256=SOURCE, **arguments
        )


@pytest.mark.parametrize(
    "fault", ["bad-result", "cleanup-error", "cleanup-missing-resource"]
)
def test_failed_native_capture_never_reads_pixels_or_publishes(
    tmp_path, monkeypatch, fault
):
    f = workflow_fixture(tmp_path, monkeypatch, capture_fault=fault)

    def forbidden(*args, **kwargs):
        pytest.fail("Failed native result reached the pixel validator")

    monkeypatch.setattr(workflow_module, "validate_capture_artifacts", forbidden)
    result = accept(f)
    assert result is None
    assert f.workflow.last_preview() is None
    assert f.workflow.view()["status"] == "HELD"
    assert f.workflow.retained_diagnostics()["capture"]["run"]


@pytest.mark.parametrize(
    "fault", ["missing", "short", "cancelled", "epoch", "supervision"]
)
def test_pixel_and_context_faults_remain_held_without_retention_replay(
    tmp_path, monkeypatch, fault
):
    f = workflow_fixture(tmp_path, monkeypatch)
    overrides = {}
    if fault != "missing":
        write_pixels(f, b"short" if fault == "short" else PIXELS)
    if fault == "cancelled":
        stop = Event()
        stop.set()
        overrides["cancellation"] = stop
    elif fault == "epoch":
        overrides["expected_settings_epoch"] = "9" * 64
    elif fault == "supervision":
        overrides["expected_supervision_sha256"] = "9" * 64
    errors = {
        "missing": PhysicalOnboardingDurabilityError,
        "short": CameraWorkerError,
    }
    with pytest.raises(errors.get(fault, ValueError)):
        accept(f, **overrides)
    assert f.workflow.last_preview() is None
    assert f.workflow.view()["status"] == "HELD"


def test_staged_copies_share_one_use_pixel_retention_ledger(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch)
    write_pixels(f)
    staged = f.workflow.staged_copy()
    assert accept(f) is not None
    f.workflow = staged
    with pytest.raises(ValueError, match="ALREADY"):
        accept(f)
    assert staged.last_preview() is None
