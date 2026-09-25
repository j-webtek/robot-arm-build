"""Actual data/settings/publication joins, not physical dispatch or M1 proof.

Native records are explicitly modeled physical-shaped fixtures sent through the
real immutable codecs. No helper, OS inventory, device or commissioning store is
run. Only isolated diagnostic logs/exports and, where stated, tiny YUY2 fixtures
may touch disk. An internal handoff is not an authenticated M1 receipt.
"""

from copy import deepcopy
from dataclasses import asdict
import ctypes
import json
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

import pytest

from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_native_camera_campaign import (
    PhysicalNativeCameraCampaign,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import _complete, _run, _ticket, make_service
from test_physical_camera_acquisition_service import SOURCE, reviewed_enrollment
from test_physical_camera_configuration import modeled_native_evidence, reported_control
from test_windows_camera_worker import receipt


ACTION = "physical_camera_configuration"
PROBE_OPERATION = "operation-" + "1" * 32
SETTINGS_OPERATION = "operation-" + "2" * 32


@pytest.fixture(autouse=True)
def no_process_or_devices(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Publication test attempted a process, device or M1 operation")

    # Python 3.10's cold Windows platform query may invoke ``ver``. This is
    # explicitly modeled host text, not observed runtime/platform evidence.
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "release", lambda: "MODELED_NOT_OBSERVED")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    original_windll = getattr(ctypes, "WinDLL", None)

    def file_guards_only(name, *args, **kwargs):
        # Real temp-file denial-of-replacement guards are part of this test;
        # camera/serial/metadata loaders are not. Do not replace file guards
        # with successful mocks merely to make content publication pass.
        caller = sys._getframe(1).f_globals.get("__name__")
        if name == "kernel32" and caller in {
            "rocell.application.physical_onboarding_durability",
            "rocell.application.windows_camera_capture_ingest",
            "rocell.application.wizard_diagnostic_export",
        }:
            assert original_windll is not None
            return original_windll(name, *args, **kwargs)
        return forbidden(name, *args, **kwargs)

    monkeypatch.setattr(ctypes, "WinDLL", file_guards_only, raising=False)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, forbidden)
    monkeypatch.setattr(
        "rocell.providers.windows.owned_native_camera_runner.OwnedNativeCameraRunner.run",
        forbidden,
    )
    for method in ("initialize", "refresh"):
        monkeypatch.setattr(
            "rocell.application.physical_camera_session.PhysicalCameraSession."
            + method,
            forbidden,
        )


def pending_probe(owner, enrollment, *, unit="device_native_units"):
    """Real immutable preparation/evidence, modeled observations and hashes."""
    plan = owner.preview_plan("probe", enrollment)["native_campaign_plan"]
    campaign = PhysicalNativeCameraCampaign.from_plan(plan)
    # This pure preparation seam deliberately supplies modeled permit identity;
    # no coordinator has consumed or authenticated a physical operation here.
    prepared = campaign._prepare("attempt-" + "3" * 32, "4" * 64)
    raw = receipt("probe")
    endpoint = prepared.camera_plan.request.binding.symbolic_link
    raw["selected_endpoint"] = endpoint
    raw["devices"][0]["symbolic_link"] = endpoint
    raw["controls"] = [reported_control("brightness"), reported_control("gain")]
    for control in raw["controls"]:
        control["unit"] = unit
    evidence = modeled_native_evidence(prepared, raw)
    owner.accept_retained_probe(
        enrollment,
        evidence,
        expected_preparation=prepared,
        expected_evidence_sha256=evidence.evidence_sha256,
    )
    return prepared, evidence


def settings_values(owner, *, gain=2):
    values = {
        field["name"]: field["default"]
        for field in owner.configuration_fields()
        if "default" in field
    }
    mode = owner.configuration_fields()[0]
    values.update(
        mode_choice_id=mode["options"][0]["value"],
        operator_id="settings-operator",
        gain_mode="manual",
        gain_value=gain,
    )
    return values


@pytest.fixture
def installed(make_service, tmp_path, monkeypatch):
    def create(*, publish=True, unit="device_native_units"):
        from rocell.application import physical_camera_capture_workflow as workflow

        monkeypatch.setattr(workflow, "source_fingerprint", lambda _: SOURCE)
        arrival, runner, source = make_service(mode="physical")
        owner = PhysicalCameraAcquisitionService(
            tmp_path / arrival.session_id,
            launch_id=arrival.session_id,
            source_sha256=SOURCE,
            mode="physical",
        )
        enrollment = reviewed_enrollment(arrival.session_id)
        arrival._physical_camera = owner
        arrival._native_camera = enrollment
        prepared, evidence = pending_probe(owner, enrollment, unit=unit)
        if publish:
            # Models the trusted dispatcher's *already completed* retention/log
            # handoff. Public settings actions below use the real event log.
            owner.publish_retained_observation(PROBE_OPERATION)
        return arrival, owner, enrollment, prepared, evidence, runner, source

    return create


def assert_no_authority(view):
    assert view["connected"] is False
    assert view["physical_authority"] is False
    assert view["hardware_qualified"] is False
    assert view["last_frame"] is None


def test_pending_probe_is_retained_without_publishing_capabilities(installed):
    arrival, owner, enrollment, prepared, evidence, runner, _ = installed(publish=False)
    state = owner.view()
    assert state["publication"]["status"] == "PENDING"
    assert state["configuration"]["capabilities"] is None
    assert owner.retained_capture_diagnostics()["pending"] is not None
    assert_no_authority(state)
    with pytest.raises(WizardError):
        _ticket(arrival, ACTION, {"mode_choice_id": "invented", "operator_id": "x"})
    with pytest.raises(WizardError):
        owner.accept_retained_probe(
            enrollment,
            evidence,
            expected_preparation=prepared,
            expected_evidence_sha256=evidence.evidence_sha256,
        )
    owner.publish_retained_observation(PROBE_OPERATION)
    assert owner.view()["configuration"]["capabilities"] is not None
    assert owner.view()["publication"]["status"] == "CURRENT"
    assert not runner.calls and not owner.directory.exists()


def test_data_handoff_withdrawal_preserves_exact_evidence_but_cannot_publish(installed):
    _, owner, _, _, evidence, _, _ = installed(publish=False)
    before = canonical(owner.retained_capture_diagnostics())
    owner.invalidate()
    assert evidence.evidence_sha256 in before.decode()
    assert (
        evidence.evidence_sha256
        in canonical(owner.retained_capture_diagnostics()).decode()
    )
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert_no_authority(owner.view())
    with pytest.raises(WizardError):
        owner.publish_retained_observation(PROBE_OPERATION)


def test_direct_settings_handoff_requires_exact_result_and_completed_publication(
    installed,
):
    _, owner, _, _, _, _, _ = installed()
    context = owner.configuration_context_sha256()
    result = owner.stage_configuration(
        settings_values(owner),
        expected_context_sha256=context,
        cancellation=threading.Event(),
    )
    assert owner.view()["publication"]["status"] == "PENDING"
    assert owner.view()["configuration"]["candidate"] is None
    original = deepcopy(result)
    result["steps"][0]["report"]["settings_epoch"] = "f" * 64
    with pytest.raises(WizardError):
        owner.validate_configuration_publication(result)
    owner.validate_configuration_publication(original)
    assert owner.view()["configuration"]["candidate"] is None
    owner.publish_configuration(SETTINGS_OPERATION, original)
    candidate = owner.view()["configuration"]["candidate"]
    assert (
        candidate["settings_epoch"] == original["steps"][0]["report"]["settings_epoch"]
    )
    assert candidate["applied"] is False
    assert_no_authority(owner.view())


def test_public_settings_preview_execute_is_file_free_and_explicit(
    installed, monkeypatch
):
    arrival, owner, _, _, _, runner, _ = installed()
    values = settings_values(owner)
    before = owner.view()

    def forbidden(*_args, **_kwargs):
        pytest.fail("Cached data/settings planning attempted filesystem I/O")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "mkdir"):
            guard.setattr(Path, name, forbidden)
        view = arrival.view()
        action = next(row for row in view["actions"] if row["action_id"] == ACTION)
        assert action["enabled"] is True
        assert "default" not in action["fields"][0]
        ticket = _ticket(arrival, ACTION, values)
        assert owner.view() == before
    execution = arrival.execute_action(ticket["ticket_id"])
    outcome = _complete(arrival, execution["operation_id"])
    assert outcome["status"] == "SUCCEEDED", json.dumps(outcome, indent=2)
    assert outcome["completion_log_persisted"] is True
    report = outcome["result"]["steps"][0]["report"]
    assert (
        owner.view()["configuration"]["candidate"]["settings_epoch"]
        == report["settings_epoch"]
    )
    assert report["applied"] is False
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == execution["operation_id"]
    )
    assert not runner.calls and not owner.directory.exists()
    assert_no_authority(arrival.view()["physical_camera"])
    assert all(row["state"] == "PHYSICAL_PENDING" for row in arrival.view()["stages"])


@pytest.mark.parametrize(
    "extra", ["evidence", "source_sha256", "output_directory", "dispatch_enabled"]
)
def test_public_settings_is_not_an_evidence_upload_or_activation_route(
    installed, extra
):
    arrival, owner, *_ = installed()
    values = settings_values(owner)
    values[extra] = "untrusted-browser-value"
    with pytest.raises(WizardError):
        _ticket(arrival, ACTION, values)
    assert owner.view()["configuration"]["candidate"] is None


@pytest.mark.parametrize("cause", ["source", "stop", "enrollment"])
def test_public_late_context_failure_does_not_publish_staged_settings(
    installed, monkeypatch, cause
):
    arrival, owner, enrollment, _, evidence, runner, source = installed()
    original = owner.stage_configuration

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if cause == "source":
            source["hash"] = "f" * 64
        elif cause == "stop":
            kwargs["cancellation"].set()
        else:
            enrollment.invalidate_review("GENERIC_CAMERA_REVIEW_CHANGED")
        return result

    monkeypatch.setattr(owner, "stage_configuration", changed)
    outcome = _run(arrival, ACTION, settings_values(owner))
    assert outcome["status"] in {"FAILED", "CANCELLED"}, outcome
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert owner.view()["configuration"]["candidate"] is None
    assert (
        evidence.evidence_sha256
        in canonical(owner.retained_capture_diagnostics()).decode()
    )
    assert_no_authority(owner.view())
    assert not runner.calls


@pytest.mark.parametrize("event", ["ACTION_EXECUTED", "ACTION_FINISHED"])
def test_failed_settings_log_never_publishes_candidate(installed, monkeypatch, event):
    arrival, owner, _, _, evidence, _, _ = installed()
    append = arrival._log.append

    def fail(name, details):
        if name == event:
            raise OSError("Isolated diagnostic log failure")
        return append(name, details)

    monkeypatch.setattr(arrival._log, "append", fail)
    outcome = _run(arrival, ACTION, settings_values(owner))
    assert outcome["status"] == "FAILED", outcome
    assert owner.view()["configuration"]["candidate"] is None
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert (
        evidence.evidence_sha256
        in canonical(owner.retained_capture_diagnostics()).decode()
    )


def test_changed_settings_result_cannot_publish_even_if_json_is_valid(
    installed, monkeypatch
):
    arrival, owner, *_ = installed()
    validate = arrival._validated_result

    def altered(action_id, value):
        if action_id == ACTION:
            value["steps"][0]["report"]["settings_epoch"] = "f" * 64
        return validate(action_id, value)

    monkeypatch.setattr(arrival, "_validated_result", altered)
    outcome = _run(arrival, ACTION, settings_values(owner))
    assert outcome["status"] == "FAILED", outcome
    assert owner.view()["configuration"]["candidate"] is None
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"


def test_old_preview_ticket_cannot_stage_against_a_new_settings_epoch(installed):
    arrival, owner, *_ = installed()
    ticket = _ticket(arrival, ACTION, settings_values(owner))
    result = owner.stage_configuration(
        settings_values(owner, gain=4),
        expected_context_sha256=owner.configuration_context_sha256(),
        cancellation=threading.Event(),
    )
    owner.publish_configuration(SETTINGS_OPERATION, result)
    with pytest.raises(WizardError):
        arrival.execute_action(ticket["ticket_id"])
    assert (
        owner.view()["configuration"]["candidate"]["settings_epoch"]
        == result["steps"][0]["report"]["settings_epoch"]
    )


def modeled_capture(owner, *, fault=None):
    """Exact service-selected plan + modeled native record + real 16-byte file."""
    plan = owner._capture_workflow.capture_plan(
        budget=CameraCampaignBudget(5000, 1, 16, 16)
    )
    prepared = PhysicalNativeCameraCampaign.from_plan(plan)._prepare(
        "attempt-" + "6" * 32, "7" * 64
    )
    request = prepared.camera_plan.request
    raw = receipt("capture")
    raw["selected_endpoint"] = request.binding.symbolic_link
    raw["devices"][0]["symbolic_link"] = request.binding.symbolic_link
    raw["requested_mode"] = asdict(request.mode)
    raw["controls"] = [reported_control("brightness"), reported_control("gain", 2)]
    raw["counts"]["control_set_attempts"] = 1
    raw["frames"][0]["media_timestamp_100ns"] = 0
    if fault == "readback":
        # Still-valid driver metadata; the changed range contradicts the probe.
        raw["controls"][1]["minimum"] = -2
    evidence = modeled_native_evidence(prepared, raw)
    output = Path(request.output_directory)
    output.mkdir(parents=True)
    pixels = bytes([16, 128, 56, 128, 96, 128, 136, 128] * 2)
    (output / raw["frames"][0]["filename"]).write_bytes(pixels)
    if fault == "missing":
        (output / raw["frames"][0]["filename"]).unlink()
    return prepared, evidence, pixels


def stage_capture(owner, prepared, evidence, *, cancellation=None):
    return owner.stage_retained_capture(
        evidence,
        expected_preparation=prepared,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_settings_epoch=owner.view()["configuration"]["candidate"][
            "settings_epoch"
        ],
        cancellation=cancellation or threading.Event(),
        deadline_ns=time.monotonic_ns() + 120_000_000_000,
    )


def finish_modeled_observation(arrival, owner, action="physical_camera_capture"):
    """Exercise real result/logging code, not a physical dispatch/M1 decision."""
    operation_id = "operation-" + "8" * 32
    result = owner.pending_observation_result(action)
    assert result["schema"] == "rocell.wizard_retained_native_camera_data.v1"
    assert "device_open_count" not in result  # Never invent zero native effects.
    arrival._operations[operation_id] = {
        "operation_id": operation_id,
        "action_id": action,
        "label": "Modeled retained native data handoff; no dispatched device",
        "status": "RUNNING",
        "created_at": "2026-09-08T00:00:00+00:00",
        "progress_count": 0,
        "physical_authority": False,
        "mode": "physical",
        "result": None,
        "result_retention": "NOT_FINISHED",
        "error": None,
    }
    with arrival._lock:
        arrival._finish(operation_id, "SUCCEEDED", result)
    return operation_id, result


def accepted_capture(installed):
    arrival, owner, enrollment, probe, probe_evidence, runner, source = installed()
    outcome = _run(arrival, ACTION, settings_values(owner))
    assert outcome["status"] == "SUCCEEDED", outcome
    prepared, evidence, pixels = modeled_capture(owner)
    ingest = stage_capture(owner, prepared, evidence)
    assert ingest is not None and ingest.domain == "PHYSICAL_UNVERIFIED"
    assert owner.view()["last_frame"] is None
    assert arrival.view()["camera"]["image_id"] is None
    return (
        arrival,
        owner,
        enrollment,
        prepared,
        evidence,
        pixels,
        ingest,
        runner,
        source,
    )


def test_actual_tiny_content_publishes_only_after_exact_logged_handoff(installed):
    arrival, owner, _, prepared, evidence, pixels, ingest, runner, _ = accepted_capture(
        installed
    )
    operation_id, result = finish_modeled_observation(arrival, owner)
    assert arrival.operation(operation_id)["completion_log_persisted"] is True
    assert owner.view()["last_frame"] is None
    arrival._publish_physical_camera_observation(
        operation_id, result, cancellation=threading.Event()
    )
    frame = arrival.view()["physical_camera"]["last_frame"]
    assert frame["frame_content_verified"] is True and frame["live"] is False
    assert frame["native_frame_sha256"] == digest(pixels)
    assert frame["image_id"] == arrival.view()["camera"]["image_id"]
    png, mime = arrival.image(frame["image_id"])
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and mime == "image/png"
    assert digest(png) == frame["preview_sha256"]
    assert (
        owner.retained_capture_diagnostics()["current"]["capture"] == evidence.to_dict()
    )
    assert owner.retained_capture_diagnostics()["current"]["ingest"] == ingest.to_dict()
    assert arrival.view()["physical_camera"]["connected"] is False
    assert all(row["state"] == "PHYSICAL_PENDING" for row in arrival.view()["stages"])
    assert not runner.calls
    # User-facing native actions remain held; there is no test-only enable flag.
    for action in ("physical_camera_probe", "physical_camera_capture"):
        with pytest.raises(WizardError):
            _ticket(arrival, action)


@pytest.mark.parametrize("fault", ["stop", "source", "enrollment", "log", "result"])
def test_late_capture_publication_failure_keeps_original_but_no_current_frame(
    installed, monkeypatch, fault
):
    arrival, owner, enrollment, _, evidence, _, ingest, _, source = accepted_capture(
        installed
    )
    if fault == "log":
        append = arrival._log.append

        def fail(name, details):
            if name == "ACTION_FINISHED":
                raise OSError("Isolated retained-data completion log failure")
            return append(name, details)

        monkeypatch.setattr(arrival._log, "append", fail)
    operation_id, result = finish_modeled_observation(arrival, owner)
    cancellation = threading.Event()
    if fault == "stop":
        cancellation.set()
    elif fault == "source":
        source["hash"] = "f" * 64
    elif fault == "enrollment":
        enrollment.invalidate_review("GENERIC_CAMERA_REVIEW_CHANGED")
    elif fault == "result":
        result = deepcopy(result)
        result["steps"][0]["report"]["workflow_sha256"] = "f" * 64
    with pytest.raises((ValueError, WizardError)):
        arrival._publish_physical_camera_observation(
            operation_id, result, cancellation=cancellation
        )
    assert arrival.view()["camera"]["image_id"] is None
    assert owner.view()["last_frame"] is None
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    retained = canonical(owner.retained_capture_diagnostics()).decode()
    assert evidence.evidence_sha256 in retained
    assert ingest.envelope_sha256 in retained


@pytest.mark.parametrize("fault", ["readback", "missing"])
def test_failed_capture_data_never_becomes_a_publishable_result(installed, fault):
    arrival, owner, *_ = installed()
    assert _run(arrival, ACTION, settings_values(owner))["status"] == "SUCCEEDED"
    prepared, evidence, _ = modeled_capture(owner, fault=fault)
    if fault == "readback":
        assert stage_capture(owner, prepared, evidence) is None
    else:
        with pytest.raises((ValueError, OSError)):
            stage_capture(owner, prepared, evidence)
    with pytest.raises(WizardError):
        owner.pending_observation_result("physical_camera_capture")
    assert arrival.view()["camera"]["image_id"] is None
    assert owner.view()["last_frame"] is None
    assert (
        owner.retained_capture_diagnostics()["pending"]["capture"] == evidence.to_dict()
    )


def test_redacted_native_control_text_withholds_exact_settings_publication(installed):
    arrival, owner, *_ = installed(unit="token=modeled-sensitive-sentinel")
    outcome = _run(arrival, ACTION, settings_values(owner))
    assert outcome["status"] == "FAILED", outcome
    assert "modeled-sensitive-sentinel" not in json.dumps(outcome)
    assert "[REDACTED]" in json.dumps(outcome)
    assert owner.view()["configuration"]["candidate"] is None
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"


def test_full_native_data_export_survives_generic_eviction_with_exact_counts(installed):
    arrival, owner, _, _, evidence, _, ingest, runner, _ = accepted_capture(installed)
    operation_id, result = finish_modeled_observation(arrival, owner)
    arrival._publish_physical_camera_observation(
        operation_id, result, cancellation=threading.Event()
    )
    retained = owner.retained_capture_diagnostics()
    for index in range(9):
        note = _run(
            arrival, "record_note", {"note": f"Model-only publication note {index}"}
        )
        assert note["status"] == "SUCCEEDED", note
    assert arrival.operation(operation_id)["result"] is None
    exported = _run(arrival, "export_logs")
    assert exported["status"] == "SUCCEEDED", json.dumps(exported, indent=2)
    folder = Path(exported["result"]["receipt"]["path"])
    assert folder.is_relative_to(arrival.export_directory)
    assert verify_export(folder)["valid"] is True
    saved = json.loads((folder / "attachment-native-camera-data.json").read_bytes())
    assert saved["schema"] == "rocell.wizard_native_camera_data_export.v1"
    assert saved["original_bytes_preserved"] is True
    assert saved["publication"] == "CURRENT"
    assert saved["current_capture"] == evidence.to_dict()
    assert saved["current_ingest"] == ingest.to_dict()
    assert (
        saved["current_capture"]["validated_result"]["native_receipt"]["counts"][
            "source_activation_attempts"
        ]
        == 1
    )
    for phase, documents in retained.items():
        if documents is not None:
            for name, document in documents.items():
                assert saved[f"{phase}_{name}"] == document
    assert not runner.calls


def test_new_settings_withdraw_frame_before_intent_log_and_queued_stage(
    installed, monkeypatch
):
    arrival, owner, _, _, evidence, _, _, _, _ = accepted_capture(installed)
    operation_id, result = finish_modeled_observation(arrival, owner)
    arrival._publish_physical_camera_observation(
        operation_id, result, cancellation=threading.Event()
    )
    assert owner.view()["last_frame"] is not None
    append, stage = arrival._log.append, owner.stage_configuration
    at_stage, release = threading.Event(), threading.Event()
    logged_views = []

    def observe_log(name, details):
        if name == "ACTION_EXECUTED" and details["action_id"] == ACTION:
            logged_views.append((owner.view(), arrival.view()["camera"]["image_id"]))
        return append(name, details)

    def queued(*args, **kwargs):
        at_stage.set()
        assert release.wait(3), "Test did not release the isolated staging boundary"
        return stage(*args, **kwargs)

    monkeypatch.setattr(arrival._log, "append", observe_log)
    monkeypatch.setattr(owner, "stage_configuration", queued)
    ticket = _ticket(arrival, ACTION, settings_values(owner, gain=4))
    execution = arrival.execute_action(ticket["ticket_id"])
    try:
        assert at_stage.wait(3)
        assert len(logged_views) == 1
        logged, image_id = logged_views[0]
        assert logged["last_frame"] is None and image_id is None
        assert logged["status"] == "HELD"
        assert logged["publication"]["status"] == "PENDING"
        assert owner.view()["last_frame"] is None
        assert arrival.view()["camera"]["image_id"] is None
        assert (
            owner.retained_capture_diagnostics()["current"]["capture"]
            == evidence.to_dict()
        )
    finally:
        release.set()
    outcome = _complete(arrival, execution["operation_id"])
    assert outcome["status"] == "SUCCEEDED", outcome
    assert owner.view()["last_frame"] is None


@pytest.mark.parametrize("fault", ["process-cleanup", "native-cleanup"])
def test_failed_verified_probe_keeps_full_bytes_in_dedicated_export(installed, fault):
    arrival, previous, enrollment, prepared, original, runner, _ = installed()
    # A fresh service models the first admitted handoff failing; this is not a
    # retry on the previous instance, a new provider call or a store replacement.
    owner = PhysicalCameraAcquisitionService(
        previous.workspace,
        launch_id=arrival.session_id,
        source_sha256=SOURCE,
        mode="physical",
    )
    arrival._physical_camera = owner
    raw = original.to_dict()["validated_result"]["native_receipt"]
    if fault == "native-cleanup":
        raw.update(status="FAILED", reason_code="SOURCE_SHUTDOWN_FAILED")
        raw["cleanup"]["source_shutdown_hr"] = -1
    failed = modeled_native_evidence(
        prepared,
        raw,
        cleanup=("CLOSE_FAILED:job",) if fault == "process-cleanup" else (),
    )
    with pytest.raises(ValueError):
        owner.accept_retained_probe(
            enrollment,
            failed,
            expected_preparation=prepared,
            expected_evidence_sha256=failed.evidence_sha256,
        )
    assert owner.retained_capture_diagnostics()["pending"]["probe"] == failed.to_dict()
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert owner.view()["configuration"]["capabilities"] is None
    with pytest.raises(WizardError):
        owner.pending_observation_result("physical_camera_probe")
    with pytest.raises(WizardError):
        owner.publish_retained_observation(PROBE_OPERATION)
    exported = _run(arrival, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    saved = json.loads((folder / "attachment-native-camera-data.json").read_bytes())
    assert saved["publication"] == "HISTORICAL_HELD"
    assert saved["original_bytes_preserved"] is True
    assert saved["pending_probe"] == failed.to_dict()
    assert digest(canonical(saved["pending_probe"])) == failed.evidence_sha256
    assert (
        saved["pending_probe"]["validated_result"]["native_receipt"]["counts"][
            "source_activation_attempts"
        ]
        == 1
    )
    assert verify_export(folder)["valid"] is True
    assert not runner.calls and not owner.directory.exists()
