"""Pure capability/configuration/readback checks; no settings are applied."""

from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from rocell.application import camera_configuration as configuration
from rocell.application.rehearsal_owned_camera_evidence import _canonical, _plain
from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    NativeCameraMode,
    NativeControlObservation,
    WindowsCameraWorkerClient,
)
from test_rehearsal_camera_probe_evidence import retained_probe


def configuration_inputs(controls=None):
    inputs, probe = retained_probe()
    caps = probe.capabilities()
    if controls is None:
        controls = (CameraControlSetting("exposure", -5, "manual"),)
    config = configuration.stage_camera_configuration(
        caps,
        caps.view()["modes"][0]["choice_id"],
        controls,
        expected_probe_evidence_sha256=probe.evidence_sha256,
        expected_source_sha256=inputs["binding"]["source_sha256"],
        expected_selected_identity_sha256=inputs["binding"]["selected_identity_sha256"],
    )
    native = inputs["native_receipt"]
    values = {c.control_id: c for c in controls}
    observed = tuple(
        (
            replace(
                c,
                value=(
                    values[c.control_id].value
                    if values[c.control_id].mode == "manual"
                    else c.default
                ),
                flags=1 if values[c.control_id].mode == "auto" else 2,
            )
            if c.control_id in values
            else c
        )
        for c in native.controls
    )
    capture = replace(
        native,
        operation="capture",
        requested_mode=config.mode,
        observed_mode=config.mode,
        controls=observed,
    )
    # The capture is unexecuted readback metadata only, not a claim of retained
    # frames/activation. The parent evidence layer verifies those separately.
    return inputs, probe, caps, config, capture


def stage(caps, controls, **expected_overrides):
    document = caps.to_dict()
    expected = {
        "expected_probe_evidence_sha256": document["probe_evidence_sha256"],
        "expected_source_sha256": document["binding"]["source_sha256"],
        "expected_selected_identity_sha256": document["binding"][
            "selected_identity_sha256"
        ],
    }
    expected.update(expected_overrides)
    return configuration.stage_camera_configuration(
        caps, caps.view()["modes"][0]["choice_id"], controls, **expected
    )


def test_exact_immutable_epoch_and_reopen_without_selection_or_application():
    inputs, probe, caps, config, _ = configuration_inputs()
    assert config.settings_epoch == hashlib.sha256(config.payload).hexdigest()
    assert config.to_dict()["probe_evidence_sha256"] == probe.evidence_sha256
    assert (
        config.view()["applied"]
        is config.view()["physical_authority"]
        is config.view()["qualified"]
        is False
    )
    restored_caps = configuration.CameraCapabilities.from_payload(
        caps.payload,
        expected_probe_evidence_sha256=probe.evidence_sha256,
        expected_binding=inputs["binding"],
    )
    restored = configuration.verify_camera_configuration(
        config.payload, expected_capabilities=restored_caps
    )
    assert (
        restored.payload == config.payload
        and restored.settings_epoch == config.settings_epoch
    )
    assert restored.controls == (CameraControlSetting("exposure", -5, "manual"),)
    assert config.view()["status"] == "STAGED_NOT_APPLIED_REHEARSAL"
    assert "control_capabilities" not in config.view()
    assert "settings_epoch" not in config.to_dict()  # No self-hash cycle.


@pytest.mark.parametrize(
    "expected_key",
    [
        "expected_probe_evidence_sha256",
        "expected_source_sha256",
        "expected_selected_identity_sha256",
    ],
)
def test_stale_expected_bindings_rejected(expected_key):
    _, _, caps, _, _ = configuration_inputs()
    with pytest.raises(configuration.CameraConfigurationError) as caught:
        stage(caps, (), **{expected_key: "a" * 64})
    assert caught.value.code == "STALE_PROBE_BINDING"


@pytest.mark.parametrize(
    "field",
    [
        "session_id",
        "attempt_id",
        "source_sha256",
        "permit_sha256",
        "operation_sha256",
        "selected_identity_sha256",
    ],
)
def test_restored_capabilities_require_every_original_binding(field):
    inputs, probe, caps, _, _ = configuration_inputs()
    expected = deepcopy(inputs["binding"])
    expected[field] = "other-id" if field.endswith("_id") else "a" * 64
    with pytest.raises(ValueError):
        configuration.CameraCapabilities.from_payload(
            caps.payload,
            expected_probe_evidence_sha256=probe.evidence_sha256,
            expected_binding=expected,
        )


@pytest.mark.parametrize(
    "setting,code",
    [
        (CameraControlSetting("gain", 1, "auto"), "CONTROL_MODE_UNSUPPORTED"),
        (CameraControlSetting("exposure", 0), "CONTROL_OUT_OF_RANGE"),
        (CameraControlSetting("white_balance", 4550), "CONTROL_OFF_STEP"),
        (CameraControlSetting("brightness", -65), "CONTROL_OUT_OF_RANGE"),
    ],
)
def test_control_values_validate_against_exact_report(setting, code):
    _, _, caps, _, _ = configuration_inputs()
    with pytest.raises(configuration.CameraConfigurationError) as caught:
        stage(caps, (setting,))
    assert caught.value.code == code


def test_duplicate_and_unreported_controls_are_not_inferred():
    _, _, caps, _, _ = configuration_inputs()
    with pytest.raises(ValueError):
        stage(caps, (CameraControlSetting("gain", 1),) * 2)
    document = caps.to_dict()
    document["controls"] = []
    empty = configuration.CameraCapabilities(_canonical(document))
    assert set(empty.view()["unavailable_controls"]) == set(configuration.CONTROL_IDS)
    with pytest.raises(configuration.CameraConfigurationError) as caught:
        stage(empty, (CameraControlSetting("gain", 1),))
    assert caught.value.code == "CONTROL_NOT_REPORTED"
    assert stage(empty, ()).controls == ()


@pytest.mark.parametrize(
    "controls",
    [
        [],
        [CameraControlSetting("gain", 1)],
        ({"control_id": "gain", "value": 1, "mode": "manual"},),
        None,
    ],
)
def test_staging_requires_exact_typed_immutable_control_tuple(controls):
    _, _, caps, _, _ = configuration_inputs()
    with pytest.raises(ValueError):
        stage(caps, controls)


@pytest.mark.parametrize(
    "field,value",
    [("value", True), ("value", 1.0), ("mode", "MANUAL"), ("control_id", "focus")],
)
def test_forged_frozen_control_objects_are_revalidated(field, value):
    _, _, caps, _, _ = configuration_inputs()
    setting = CameraControlSetting("gain", 1)
    object.__setattr__(setting, field, value)
    with pytest.raises(ValueError):
        stage(caps, (setting,))


@pytest.mark.parametrize(
    "mode_update,code",
    [
        ({"subtype": "MJPG"}, "UNSUPPORTED_PIXEL_FORMAT"),
        ({"width": 5471}, "ODD_YUY2_WIDTH"),
        ({"height": 16384}, "FRAME_BUDGET_EXCEEDED"),
        ({"stride_bytes": 1}, "INVALID_REPORTED_STRIDE"),
    ],
)
def test_all_reported_modes_remain_visible_but_unsupported_choices_refuse(
    mode_update, code
):
    _, _, caps, _, _ = configuration_inputs()
    document = caps.to_dict()
    document["modes"][0].update(mode_update)
    modified = configuration.CameraCapabilities(_canonical(document))
    row = modified.view()["modes"][0]
    assert not row["selectable"] and code in row["blockers"]
    with pytest.raises(configuration.CameraConfigurationError) as caught:
        stage(modified, ())
    assert caught.value.code == "UNSUPPORTED_CAPTURE_MODE"


def test_opaque_mode_choices_bind_exact_report_occurrence_without_default():
    _, _, caps, _, _ = configuration_inputs()
    raw = caps.to_dict()
    raw["modes"] *= 2
    duplicate = configuration.CameraCapabilities(_canonical(raw))
    rows = duplicate.view()["modes"]
    assert rows[0]["mode"] == rows[1]["mode"]
    assert rows[0]["choice_id"] != rows[1]["choice_id"]
    before = caps.view()["modes"][0]["choice_id"]
    raw["probe_evidence_sha256"] = "d" * 64
    changed = configuration.CameraCapabilities(_canonical(raw))
    assert changed.view()["modes"][0]["choice_id"] != before
    assert "selected_mode" not in caps.view()


@pytest.mark.parametrize("current_flags", [1, 2, 3])
def test_reported_flag_bits_preserved_without_inventing_current_mode(current_flags):
    _, _, caps, _, _ = configuration_inputs()
    raw = caps.to_dict()
    raw["controls"][0]["flags"] = current_flags
    reported = configuration.CameraCapabilities(_canonical(raw))
    assert reported.view()["controls"][0]["flags"] == current_flags
    assert (
        stage(reported, (CameraControlSetting("exposure", -5),)).controls[0].mode
        == "manual"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("flags", 0),
        ("flags", 4),
        ("flags", True),
        ("capability_flags", 0),
        ("capability_flags", 7),
        ("step", 0),
        ("default", 999),
        ("value", 999),
        ("unit", "bad\nunit"),
        ("control_id", "focus"),
    ],
)
def test_malformed_reported_control_fields_refuse(field, value):
    _, _, caps, _, _ = configuration_inputs()
    raw = caps.to_dict()
    raw["controls"][0][field] = value
    with pytest.raises(ValueError):
        configuration.CameraCapabilities(_canonical(raw))


def test_candidate_restore_rejects_recomputed_tampered_configuration():
    _, _, caps, config, _ = configuration_inputs()
    for change in (
        lambda d: d.update(probe_evidence_sha256="a" * 64),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(applied=True),
        lambda d: d["control_capabilities"][0].update(maximum=0),
        lambda d: d.update(extra=True),
    ):
        raw = config.to_dict()
        change(raw)
        with pytest.raises(ValueError):
            configuration.verify_camera_configuration(
                _canonical(raw), expected_capabilities=caps
            )


def test_manual_and_auto_readback_keep_requested_values_distinct():
    _, _, _, config, receipt = configuration_inputs(
        (CameraControlSetting("exposure", -5, "auto"), CameraControlSetting("gain", 20))
    )
    view = configuration.compare_camera_readback(
        config, receipt, expected_settings_epoch=config.settings_epoch
    )
    assert view["status"] == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
    assert view["reasons"] == [] and view["mode_matched"]
    auto, manual = view["controls"]
    assert auto["requested"] == {"value": -5, "mode": "auto"}
    assert auto["observed"]["value"] == -6 and auto["observed"]["flags"] == 1
    assert manual["requested"]["value"] == manual["observed"]["value"] == 20
    assert view["physical_authority"] is view["qualified"] is False


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("manual-value", "MANUAL_VALUE_READBACK_MISMATCH"),
        ("auto-flag", "CONTROL_MODE_READBACK_MISMATCH"),
        ("both-flags", "CONTROL_MODE_READBACK_MISMATCH"),
        ("missing", "CONTROL_READBACK_MISSING"),
        ("capability", "CONTROL_CAPABILITY_DRIFT"),
    ],
)
def test_readback_mismatch_is_not_reclassified_as_applied(fault, reason):
    _, _, _, config, receipt = configuration_inputs()
    controls = list(receipt.controls)
    if fault == "manual-value":
        controls[0] = replace(controls[0], value=-6)
    elif fault == "auto-flag":
        controls[0] = replace(controls[0], flags=1)
    elif fault == "both-flags":
        controls[0] = replace(controls[0], flags=3)
    elif fault == "missing":
        controls = controls[1:]
    elif fault == "capability":
        controls[0] = replace(controls[0], step=2)
    view = configuration.compare_camera_readback(
        config,
        replace(receipt, controls=tuple(controls)),
        expected_settings_epoch=config.settings_epoch,
    )
    assert view["status"] == "READBACK_MISMATCH_REHEARSAL"
    assert reason in view["controls"][0]["reasons"]
    assert not view["controls"][0]["matched"]
    assert config.view()["applied"] is False


@pytest.mark.parametrize(
    "changed,reason",
    [
        ("selected_endpoint", "ENDPOINT_MISMATCH"),
        ("observed_mode", "MODE_READBACK_MISMATCH"),
        ("requested_mode", "MODE_READBACK_MISMATCH"),
        ("cleanup_confirmed", "CAPTURE_NOT_SUCCESSFULLY_CLOSED"),
        ("operation", "CAPTURE_NOT_SUCCESSFULLY_CLOSED"),
    ],
)
def test_readback_requires_endpoint_mode_and_successful_closure(changed, reason):
    _, _, _, config, receipt = configuration_inputs()
    value = {
        "selected_endpoint": "other",
        "observed_mode": None,
        "requested_mode": None,
        "cleanup_confirmed": False,
        "operation": "probe",
    }[changed]
    view = configuration.compare_camera_readback(
        config,
        replace(receipt, **{changed: value}),
        expected_settings_epoch=config.settings_epoch,
    )
    assert reason in view["reasons"]
    assert view["status"] == "READBACK_MISMATCH_REHEARSAL"


def test_unknown_readback_flag_and_stale_epoch_refuse():
    _, _, _, config, receipt = configuration_inputs()
    with pytest.raises(ValueError):
        configuration.compare_camera_readback(
            config, receipt, expected_settings_epoch="a" * 64
        )
    malformed = replace(receipt.controls[0], flags=4)
    with pytest.raises(ValueError):
        configuration.compare_camera_readback(
            config,
            replace(receipt, controls=(malformed, *receipt.controls[1:])),
            expected_settings_epoch=config.settings_epoch,
        )


def test_every_pure_operation_is_inert_and_returns_detached_objects(monkeypatch):
    inputs, probe, caps, config, receipt = configuration_inputs()

    def forbidden(*args, **kwargs):
        pytest.fail("Configuration must not use filesystem/device APIs")

    for name in ("probe", "capture", "enumerate_metadata", "_campaign"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)
    for name in ("open", "read_bytes", "stat", "mkdir", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    restored_caps = configuration.CameraCapabilities.from_payload(
        caps.payload,
        expected_probe_evidence_sha256=probe.evidence_sha256,
        expected_binding=inputs["binding"],
    )
    staged = stage(restored_caps, config.controls)
    configuration.verify_camera_configuration(
        staged.payload, expected_capabilities=restored_caps
    )
    staged.to_dict()["controls"].clear()
    staged.view()["controls"].clear()
    restored_caps.view()["controls"].clear()
    assert staged.controls == config.controls
    assert (
        configuration.compare_camera_readback(
            staged, receipt, expected_settings_epoch=staged.settings_epoch
        )["status"]
        == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
    )
