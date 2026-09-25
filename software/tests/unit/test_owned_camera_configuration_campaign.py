"""Pure/injected campaign joins; no child, M1 store, image or device access.

Nominal native/process observations below are explicit in-memory fixtures, not
claims that a worker ran. Separate owned-runner tests execute the fixed child.
"""

import base64
from copy import deepcopy
from dataclasses import replace
import threading
import time

import pytest

import rocell.application.owned_camera_probe_campaign as probe_campaign
import rocell.application.owned_camera_rehearsal_campaign as capture_campaign
import rocell.application.rehearsal_owned_camera_evidence as capture_evidence
from rocell.application.camera_configuration import (
    compare_camera_readback,
    stage_camera_configuration,
)
from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CommissioningMode,
    ExactOperationPermit,
    RegisteredActionRequest,
)
from rocell.application.commissioning_m1_persistence import rehearsal_source_binding
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.rehearsal_camera_probe_evidence import (
    retain_rehearsal_camera_probe_evidence,
)
from rocell.application.wizard_camera_configuration import (
    configuration_fields,
    effective_camera_settings_epoch,
    stage_wizard_camera_configuration,
)
from rocell.providers.windows._owned_camera_fixture import fixture_readback
from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    NativeControlObservation,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.owned_camera_codec import CONFIG_RESULT_SCHEMA
from rocell.providers.windows.owned_worker_process import (
    OwnedWindowsWorker,
    PinnedWorkerFile,
)
from test_owned_camera_rehearsal_campaign import arguments
from test_rehearsal_camera_probe_evidence import probe_inputs
from test_rehearsal_owned_camera_evidence import complete_inputs


def _forbidden(*args, **kwargs):
    pytest.fail(
        "This test may not dispatch workers, render templates or access devices"
    )


@pytest.fixture(autouse=True)
def incapable_boundary(monkeypatch):
    # Production constructors hash their fixed script only at explicit execution.
    # This planning suite injects that observation without reading any file.
    pin = lambda path, maximum: PinnedWorkerFile(path, "7" * 64, maximum)
    monkeypatch.setattr(probe_campaign, "_pin", pin)
    monkeypatch.setattr(capture_campaign, "_pin", pin)
    monkeypatch.setattr(OwnedWindowsWorker, "run", _forbidden)
    monkeypatch.setattr(
        capture_campaign.OwnedBinaryCameraWorker, "_prepare_templates", _forbidden
    )
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, _forbidden)


def configuration_pair(args, *, session="rehearsal-config-session", controls=()):
    inputs = probe_inputs()
    binding = inputs["binding"]
    binding.update(
        session_id=session,
        source_sha256=args["source_sha256"],
        selected_identity_sha256=capture_campaign._hash(args["selected_camera"]),
    )
    request = inputs["activation_request"]
    request = replace(
        request,
        source_sha256=binding["source_sha256"],
        binding=replace(
            request.binding, binding_sha256=binding["selected_identity_sha256"]
        ),
    )
    inputs["activation_request"] = request
    inputs["owned_payload"]["camera_request"] = capture_evidence._plain(request)
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["fixture_result"]["camera_request_sha256"] = capture_evidence._hash(
        capture_evidence._plain(request)
    )
    inputs["process_result"] = replace(
        inputs["process_result"],
        stdout=capture_evidence._canonical(wire),
        parsed_result=wire,
    )
    evidence = retain_rehearsal_camera_probe_evidence(**inputs)
    capabilities = evidence.capabilities()
    configuration = stage_camera_configuration(
        capabilities,
        capabilities.view()["modes"][0]["choice_id"],
        controls,
        expected_probe_evidence_sha256=evidence.evidence_sha256,
        expected_source_sha256=args["source_sha256"],
        expected_selected_identity_sha256=binding["selected_identity_sha256"],
    )
    return capabilities, configuration


def permit_for(worker, *, session="rehearsal-config-session"):
    registration = (
        worker.registration()
        if isinstance(worker, probe_campaign.OwnedCameraProbeWorker)
        else worker.registration(STAGE_ORDER[4])
    )
    admission = AdmissionSnapshot(
        "cell-fixture",
        session,
        CommissioningMode.REHEARSAL,
        registration.stage,
        V2StageState.WAITING_OPERATOR,
        1,
        rehearsal_source_binding(worker.source_sha256),
        *(["7" * 64] * 7),
        ("8" * 64,) * 8,
        capture_campaign._hash(worker.selected_camera),
        False,
        0,
    )
    request = RegisteredActionRequest(
        admission.cell_id,
        session,
        registration.action_id,
        "request-camera-fixture",
        admission.challenge_sha256,
    )
    now = time.monotonic_ns()
    return ExactOperationPermit(
        "attempt-camera-fixture",
        request,
        admission,
        registration,
        now,
        now + 30_000_000_000,
        "9" * 64,
    )


def configured_inputs():
    """Pure typed/native v2 receipt without claiming verified capture files."""
    inputs = complete_inputs()
    setting = CameraControlSetting("gain", 21)
    request = replace(inputs["activation_request"], controls=(setting,))
    observations = tuple(
        NativeControlObservation(**row)
        for row in fixture_readback([capture_evidence._plain(setting)])
    )
    native = replace(
        inputs["native_receipt"],
        controls=observations,
        counts={**inputs["native_receipt"].counts, "control_set_attempts": 1},
    )
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["schema"] = CONFIG_RESULT_SCHEMA
    wire["fixture_result"]["camera_request_sha256"] = capture_evidence._hash(
        capture_evidence._plain(request)
    )
    wire["fixture_result"]["native_receipt"].update(
        controls=capture_evidence._plain(observations), counts=dict(native.counts)
    )
    inputs.update(
        activation_request=request,
        native_receipt=native,
        process_result=replace(
            inputs["process_result"],
            stdout=capture_evidence._canonical(wire),
            parsed_result=wire,
        ),
        capture=None,
        capture_envelope=None,
        source_contract=None,
    )
    return inputs


def test_configured_plan_and_registration_bind_intent_and_composite_epoch(tmp_path):
    args = arguments(tmp_path)
    capabilities, configuration = configuration_pair(
        args,
        controls=(
            CameraControlSetting("gain", 21),
            CameraControlSetting("exposure", -7, "auto"),
        ),
    )
    worker = capture_campaign.OwnedBinaryCameraWorker(
        **args, configuration=configuration, capabilities=capabilities
    )
    plan = worker.plan()
    assert plan["electronic_configuration"] == configuration.to_dict()
    assert (
        plan["probe_evidence_sha256"]
        == configuration.to_dict()["probe_evidence_sha256"]
    )
    assert plan["effective_settings_epoch"] == effective_camera_settings_epoch(
        args["settings_epoch"], configuration
    )
    assert plan["effective_settings_epoch"] != args["settings_epoch"]
    assert plan["effective_settings_epoch"] != configuration.settings_epoch
    for stage in STAGE_ORDER[4:6]:
        reg = worker.registration(stage)
        assert reg.operation_sha256 == capture_campaign._hash(plan)
        assert reg.budget.maximum_writes == 2
        assert reg.budget.maximum_frames == reg.budget.maximum_reads == 1
        assert reg.budget.timeout_ms == 60000
    assert worker.capture is worker.evidence is worker.readback is None
    assert not args["root"].exists()


def test_settings_epoch_changes_with_each_bound_input(tmp_path):
    args = arguments(tmp_path)
    caps, first = configuration_pair(args, controls=(CameraControlSetting("gain", 21),))
    second = stage_camera_configuration(
        caps,
        first.to_dict()["mode_choice_id"],
        (CameraControlSetting("gain", 22),),
        expected_probe_evidence_sha256=first.to_dict()["probe_evidence_sha256"],
        expected_source_sha256=args["source_sha256"],
        expected_selected_identity_sha256=capture_campaign._hash(
            args["selected_camera"]
        ),
    )
    values = {
        effective_camera_settings_epoch(args["settings_epoch"], first),
        effective_camera_settings_epoch("b" * 64, first),
        effective_camera_settings_epoch(args["settings_epoch"], second),
    }
    assert len(values) == 3
    changed = first.to_dict()
    changed["controls"][0]["value"] = 999
    assert first.controls[0].value == 21


@pytest.mark.parametrize(
    "fault", ["source", "identity", "missing-capabilities", "missing-configuration"]
)
def test_stale_config_and_unpaired_capabilities_fail_before_any_artifacts(
    tmp_path, fault
):
    args = arguments(tmp_path)
    caps, config = configuration_pair(args)
    if fault == "source":
        args["source_sha256"] = "b" * 64
    elif fault == "identity":
        args["selected_camera"]["unit_id"] = "SYNTHETIC-OTHER"
    elif fault == "missing-capabilities":
        caps = None
    else:
        config = None
    with pytest.raises(ValueError):
        capture_campaign.OwnedBinaryCameraWorker(
            **args, configuration=config, capabilities=caps
        )


def test_other_session_configuration_rejected_before_permit_acknowledgment(tmp_path):
    args = arguments(tmp_path)
    caps, config = configuration_pair(args, session="other-reviewed-session")
    worker = capture_campaign.OwnedBinaryCameraWorker(
        **args, configuration=config, capabilities=caps
    )
    permit = permit_for(worker)
    with pytest.raises(ValueError):
        worker.run_retained_campaign(
            permit,
            deadline_ns=time.monotonic_ns() + 60_000_000_000,
            cancellation=threading.Event(),
            authorize_consumed_permit=_forbidden,
        )


@pytest.mark.parametrize("controlled", [False, True])
def test_invalid_permit_cannot_reach_capture_template_preparation(tmp_path, controlled):
    args = arguments(tmp_path)
    kwargs = {}
    if controlled:
        caps, config = configuration_pair(
            args, controls=(CameraControlSetting("gain", 21),)
        )
        kwargs = {"capabilities": caps, "configuration": config}
    worker = capture_campaign.OwnedBinaryCameraWorker(**args, **kwargs)
    permit = permit_for(worker)
    permit = replace(
        permit, registration=replace(permit.registration, operation_sha256="e" * 64)
    )
    with pytest.raises(ValueError):
        worker.run_retained_campaign(
            permit,
            deadline_ns=time.monotonic_ns() + 60_000_000_000,
            cancellation=threading.Event(),
            authorize_consumed_permit=_forbidden,
        )


def test_probe_plan_is_zero_frame_zero_write_and_exact_registration(tmp_path):
    args = arguments(tmp_path)
    worker = probe_campaign.OwnedCameraProbeWorker(
        args["workspace"],
        args["root"],
        source_sha256=args["source_sha256"],
        selected_camera=args["selected_camera"],
    )
    plan = worker.plan()
    reg = worker.registration()
    assert reg.stage == STAGE_ORDER[4]
    assert reg.operation_sha256 == capture_campaign._hash(plan)
    assert (
        reg.budget.maximum_reads
        == reg.budget.maximum_writes
        == reg.budget.maximum_frames
        == 0
    )
    assert reg.budget.maximum_opens == reg.budget.maximum_closes == 1
    assert (
        reg.budget.timeout_ms == 60000 and reg.budget.maximum_output_bytes == 128 * 1024
    )
    assert plan["native_duration_ms"] == 5000 and plan["process_timeout_ms"] == 10000
    assert plan["frames_requested"] == plan["control_writes_requested"] == 0
    plan["selected_camera"]["endpoint"] = "different"
    assert worker.plan()["selected_camera"]["endpoint"] == "incapable-fixture-only"
    with pytest.raises(ValueError, match="retained"):
        worker.run_campaign()
    permit = permit_for(worker)
    permit = replace(
        permit, admission=replace(permit.admission, selected_identity_sha256="f" * 64)
    )
    with pytest.raises(ValueError):
        worker.run_retained_campaign(
            permit,
            deadline_ns=time.monotonic_ns() + 60_000_000_000,
            cancellation=threading.Event(),
            authorize_consumed_permit=_forbidden,
        )


def test_wizard_fields_are_closed_reported_choices_and_stage_without_io(tmp_path):
    args = arguments(tmp_path)
    caps, config = configuration_pair(args)
    fields = configuration_fields(caps)
    assert len(fields) == 13
    values = {field["name"]: field["default"] for field in fields if "default" in field}
    values["mode_choice_id"] = fields[0]["options"][0]["value"]
    values.update(
        gain_mode="manual", gain_value=21, exposure_mode="auto", exposure_value=-7
    )
    staged = stage_wizard_camera_configuration(
        caps,
        values,
        source_sha256=args["source_sha256"],
        selected_identity_sha256=capture_campaign._hash(args["selected_camera"]),
    )
    assert len(staged.controls) == 2 and not staged.to_dict()["applied"]
    assert staged.to_dict()["physical_authority"] is False
    for mutation in (
        {"unexpected": "arbitrary"},
        {"gain_mode": "auto"},
        {"gain_value": True},
        {"white_balance_mode": "manual", "white_balance_value": 4550},
        {"mode_choice_id": "index-0"},
    ):
        with pytest.raises(ValueError):
            stage_wizard_camera_configuration(
                caps,
                {**values, **mutation},
                source_sha256=args["source_sha256"],
                selected_identity_sha256=capture_campaign._hash(
                    args["selected_camera"]
                ),
            )


def test_configured_v2_retention_matches_raw_without_claiming_file_verification():
    inputs = configured_inputs()
    artifact = capture_evidence.retain_owned_camera_evidence(**inputs)
    assert artifact.view()["native"]["receipt_valid"] is True
    assert artifact.view()["native"]["counts"]["control_set_attempts"] == 1
    assert artifact.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert (
        artifact.view()["physical_authority"] is artifact.view()["qualified"] is False
    )
    assert (
        base64.b64decode(artifact.to_dict()["stdout"]["data"])
        == inputs["process_result"].stdout
    )
    verified = capture_evidence.verify_owned_camera_evidence(
        artifact.payload, inputs["binding"]
    )
    assert verified.payload == artifact.payload


def test_configured_v2_unknown_unrequested_flags_cannot_be_valid_wire():
    inputs = configured_inputs()
    native = inputs["native_receipt"]
    controls = list(native.controls)
    controls[0] = replace(controls[0], flags=3)
    inputs["native_receipt"] = replace(native, controls=tuple(controls))
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["fixture_result"]["native_receipt"]["controls"][0]["flags"] = 3
    inputs["process_result"] = replace(
        inputs["process_result"],
        stdout=capture_evidence._canonical(wire),
        parsed_result=wire,
    )
    artifact = capture_evidence.retain_owned_camera_evidence(**inputs)
    assert artifact.view()["native"]["receipt_valid"] is False


def test_readback_drift_keeps_raw_without_valid_typed_receipt():
    inputs = configured_inputs()
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["fixture_result"]["scenario"] = "control-readback-drift"
    wire["fixture_result"]["native_receipt"]["controls"][1]["value"] = 20
    inputs["process_result"] = replace(
        inputs["process_result"],
        stdout=capture_evidence._canonical(wire),
        parsed_result=wire,
    )
    inputs["native_receipt"] = None  # Unchanged native client rejected this packet.
    inputs["error"] = {
        "code": "INVALID_CAMERA_CONTRACT",
        "message": "Modeled readback mismatch",
    }
    artifact = capture_evidence.retain_owned_camera_evidence(**inputs)
    assert artifact.view()["native"] is None
    assert artifact.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert (
        base64.b64decode(artifact.to_dict()["stdout"]["data"])
        == inputs["process_result"].stdout
    )
    assert artifact.view()["process"]["tree_exit_confirmed"] is True


@pytest.mark.parametrize("mode", ["manual", "auto"])
def test_independent_readback_keeps_requested_values_distinct_from_observations(
    tmp_path, mode
):
    args = arguments(tmp_path)
    _, configuration = configuration_pair(
        args, controls=(CameraControlSetting("exposure", -7, mode),)
    )
    native = complete_inputs()["native_receipt"]
    observed = tuple(
        NativeControlObservation(**row)
        for row in fixture_readback(
            [{"control_id": "exposure", "value": -7, "mode": mode}]
        )
    )
    native = replace(
        native,
        controls=observed,
        selected_endpoint=args["selected_camera"]["endpoint"],
    )
    report = compare_camera_readback(
        configuration, native, expected_settings_epoch=configuration.settings_epoch
    )
    assert report["status"] == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
    row = report["controls"][0]
    assert row["requested"] == {"value": -7, "mode": mode}
    assert row["observed"]["value"] == (-7 if mode == "manual" else -6)
    assert row["observed"]["flags"] == (2 if mode == "manual" else 1)
    assert report["physical_authority"] is False
    with pytest.raises(ValueError):
        compare_camera_readback(configuration, native, expected_settings_epoch="f" * 64)
    drifted = replace(
        native,
        controls=tuple(
            NativeControlObservation(**row)
            for row in fixture_readback(
                [{"control_id": "exposure", "value": -7, "mode": mode}], drift=True
            )
        ),
    )
    failed = compare_camera_readback(
        configuration, drifted, expected_settings_epoch=configuration.settings_epoch
    )
    assert failed["status"] == "READBACK_MISMATCH_REHEARSAL"
    assert not failed["controls"][0]["matched"]
