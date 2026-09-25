"""Mode/control review diagnostics, with modeled hardware and no device I/O."""

from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from rocell.application import camera_operating_mode_guidance as guidance
from rocell.application import physical_camera_configuration as config_module
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    NativeCameraMode,
    NativeControlObservation,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.vision.camera_profile import load_camera_profile
from test_physical_camera_configuration import (
    capabilities_fixture,
    forbid_process_and_devices,
    physical_configuration_fixture,
    reported_control,
)


REFERENCE = NativeCameraMode(5472, 3648, 9, 1, stride_bytes=10944)


@pytest.mark.parametrize(
    "mode,status",
    [
        (None, "NOT_OBSERVED"),
        (REFERENCE, "REFERENCE_MATCH_REVIEW_REQUIRED"),
        (
            replace(REFERENCE, fps_numerator=9000, fps_denominator=1000),
            "REFERENCE_MATCH_REVIEW_REQUIRED",
        ),
        (replace(REFERENCE, fps_numerator=8), "EIGHT_FPS_VARIANCE_REVIEW_REQUIRED"),
        (
            replace(REFERENCE, fps_numerator=8000, fps_denominator=1000),
            "EIGHT_FPS_VARIANCE_REVIEW_REQUIRED",
        ),
        (
            replace(REFERENCE, fps_numerator=8999, fps_denominator=1000),
            "OTHER_MODE_REVIEW_REQUIRED",
        ),
        (replace(REFERENCE, subtype="MJPG"), "OTHER_MODE_REVIEW_REQUIRED"),
        (replace(REFERENCE, width=1920, height=1080), "OTHER_MODE_REVIEW_REQUIRED"),
    ],
)
def test_exact_modes_are_review_only_and_preserve_wire_values(mode, status):
    result = guidance.mode_review(mode)
    assert result["status"] == status
    assert result["reported_mode"] == (None if mode is None else asdict(mode))
    assert result["guidance_sha256"] == digest(canonical(result["rules"]))
    assert result["review_required"] is True
    assert result["rules"]["approved_operating_policy"] is False
    assert result["rules"]["automatic_fallback"] is False
    for name in (
        "physical_authority",
        "hardware_qualified",
        "canonical_stage_pass",
        "evidence_authenticated",
    ):
        assert result[name] is False


@pytest.mark.parametrize("bad", [True, {}, 8, "8 fps"])
def test_untyped_mode_is_not_coerced(bad):
    with pytest.raises(ValueError, match="Exact native mode"):
        guidance.mode_review(bad)


def test_detached_rule_output_and_alignment_with_unchanged_purchase_profile():
    profile = load_camera_profile()
    assert profile.published_mode("USB_3_2_GEN_1", 5472, 3648).maximum_fps == 9
    result = guidance.mode_review(REFERENCE)
    result["rules"]["reference_mode"]["fps_numerator"] = 8
    assert (
        guidance.mode_review(REFERENCE)["rules"]["reference_mode"]["fps_numerator"] == 9
    )


@pytest.mark.parametrize(
    "flags,support,expected",
    [
        (2, 3, "reported manual, not verified"),
        (1, 3, "auto/ambiguous"),
        (3, 3, "auto/ambiguous"),
        (1, 1, "manual support not reported"),
    ],
)
def test_probe_controls_are_support_not_selected_or_stable(flags, support, expected):
    control = NativeControlObservation(
        **{**reported_control("exposure", flags=flags), "capability_flags": support}
    )
    text = guidance.probe_guidance((replace(REFERENCE, fps_numerator=8),), (control,))
    assert "9 fps reference not reported" in text and "8 fps reported" in text
    assert expected in text and "white_balance: not reported" in text
    assert "No mode approved or selected" in text
    assert len(text.encode()) <= 512


def test_both_modes_and_missing_inventory_do_not_guess_support():
    both = guidance.probe_guidance((REFERENCE, replace(REFERENCE, fps_numerator=8)), ())
    assert "9 fps reference reported" in both and "8 fps reported" in both
    empty = guidance.probe_guidance((), ())
    assert "9 fps reference not reported" in empty and "8 fps reported" not in empty


@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_required_manual_intent_is_separate_from_readback(mode):
    controls = tuple(
        CameraControlSetting(name, 0, mode) for name in ("exposure", "white_balance")
    )
    text = guidance.intent_guidance(REFERENCE, controls)
    assert ("Manual intent incomplete" in text) is (mode == "auto")
    assert "NOT APPLIED" in text and "no automatic fallback" in text


@pytest.mark.parametrize(
    "fault", [None, "missing", "auto", "ambiguous", "mismatch", "no-observation"]
)
def test_required_readback_never_claims_reopen_stability(fault):
    rows = [
        dict(control_id=name, matched=True, observed=reported_control(name))
        for name in ("exposure", "white_balance")
    ]
    if fault == "missing":
        rows.pop()
    elif fault in {"auto", "ambiguous"}:
        rows[0]["observed"]["flags"] = 1 if fault == "auto" else 3
    elif fault == "mismatch":
        rows[0]["matched"] = False
    elif fault == "no-observation":
        rows[0]["observed"] = None
    text = guidance.readback_guidance(REFERENCE, rows, matched=fault is None)
    assert ("Manual readback unresolved" in text) is (fault is not None)
    assert ("stability unproven" in text) is (fault is None)
    assert "No pixel, USB-speed, power or stage qualification" in text
    assert len(text.encode()) <= 512


def test_views_are_inert_and_do_not_change_evidence_bytes(tmp_path, monkeypatch):
    parts = physical_configuration_fixture(tmp_path)
    objects = parts[2], parts[3], parts[6]
    originals = [obj.payload for obj in objects]

    def forbidden(*args, **kwargs):
        pytest.fail("guidance accessed the filesystem")

    for name in ("open", "read_bytes", "stat", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    for obj, original in zip(objects, originals):
        before = set(obj.view())
        for _ in range(3):
            view = obj.view()
            assert guidance.GUIDANCE_ID in view["meaning"]
            assert len(view["meaning"].encode()) <= 512
            assert obj.payload == original and set(view) == before
            assert view["physical_authority"] is view["hardware_qualified"] is False


def test_real_settings_field_builder_labels_eight_fps_without_default_or_fallback(
    tmp_path,
):
    # Modeled native-shaped contract, not a trusted original observation.
    _, _, caps = capabilities_fixture(tmp_path)
    raw = caps.to_dict()
    raw["modes"] = [asdict(replace(REFERENCE, fps_numerator=8))]
    caps = config_module.PhysicalCameraCapabilities(canonical(raw))
    service = object.__new__(PhysicalCameraAcquisitionService)
    service._lock = threading.RLock()
    service._capture_workflow = SimpleNamespace(
        view=lambda: {"configuration": {"capabilities": caps.view()}}
    )
    fields = service.configuration_fields()
    assert "default" not in fields[0]
    assert len(fields[0]["options"]) == 1
    option = fields[0]["options"][0]
    assert (
        "8/1 fps" in option["label"] and "8 fps variance from 9 fps" in option["label"]
    )
    assert option["value"] == caps.view()["modes"][0]["choice_id"]
    fields[0]["options"].clear()
    assert service.configuration_fields()[0]["options"]
