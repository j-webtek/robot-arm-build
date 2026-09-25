"""Finite DOM/terminal checks only; modeled camera records, no device access."""

from dataclasses import asdict

import pytest

from rocell.application import physical_camera_configuration as config_module
from rocell.providers.windows.camera_worker_client import NativeCameraMode
from rocell.providers.windows.native_camera_protocol import canonical
from test_physical_camera_configuration import (
    capabilities_fixture,
    modeled_native_evidence,
    physical_configuration_fixture,
)
from test_wizard_physical_camera_ui import actual_projection, physical, render


def projection(caps, candidate=None, readback=None):
    data = physical()
    data.update(
        status="OBSERVATION_RETAINED",
        configuration=dict(
            capabilities=caps.view(),
            candidate=None if candidate is None else candidate.view(),
            readback=None if readback is None else readback.view(),
        ),
        reviewed_endpoint=dict(
            endpoint_sha256=caps.to_dict()["binding"]["endpoint_sha256"],
            identity_sha256="b" * 64,
            metadata_review_binding_sha256="c" * 64,
            generic_candidate_sha256="d" * 64,
        ),
    )
    return data


def test_eight_fps_and_missing_controls_are_visible_without_approval(tmp_path):
    _, _, original = capabilities_fixture(tmp_path)
    raw = original.to_dict()
    raw["modes"] = [asdict(NativeCameraMode(5472, 3648, 8, 1, stride_bytes=10944))]
    caps = config_module.PhysicalCameraCapabilities(canonical(raw))
    for output in render(projection(caps)):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "b0477-mode-review-v1" in output
        assert "9 fps reference not reported" in output
        assert "8 fps reported: separate operating-policy review required" in output
        assert "exposure: not reported" in output
        assert "No mode approved or selected" in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output


def test_intent_and_readback_guidance_are_rendered_by_both_frontends(actual_projection):
    for output in render(actual_projection):
        assert "Manual intent incomplete: exposure, white_balance" in output
        assert "Manual readback unresolved: exposure, white_balance" in output
        assert "NOT APPLIED" in output


def test_equivalent_native_readback_fraction_renders_from_real_comparator(tmp_path):
    # Actual pure native evidence/setting joins, with explicitly modeled wire.
    _, _, caps, cfg, capture, evidence, _ = physical_configuration_fixture(tmp_path)
    raw = evidence.to_dict()["validated_result"]["native_receipt"]
    raw["observed_mode"]["fps_numerator"] *= 1000
    raw["observed_mode"]["fps_denominator"] *= 1000
    equivalent = modeled_native_evidence(capture, raw)
    readback = config_module.compare_physical_camera_readback(
        cfg,
        equivalent,
        expected_preparation=capture,
        expected_capture_evidence_sha256=equivalent.evidence_sha256,
        expected_settings_epoch=cfg.settings_epoch,
    )
    assert readback.to_dict()["mode_matched"] is True
    for output in render(projection(caps, cfg, readback)):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "Settings comparison matched" in output


@pytest.mark.parametrize(
    "fault",
    [
        "different-fps",
        "zero-denominator",
        "coerced-numerator",
        "changed-width",
        "changed-stride",
    ],
)
def test_rational_display_fix_does_not_admit_mismatched_or_malformed_claims(
    actual_projection, fault
):
    observed = actual_projection["configuration"]["readback"]["observed_mode"]
    if fault == "different-fps":
        observed["fps_numerator"] += 1
    elif fault == "zero-denominator":
        observed["fps_denominator"] = 0
    elif fault == "coerced-numerator":
        observed["fps_numerator"] = str(observed["fps_numerator"])
    elif fault == "changed-width":
        observed["width"] += 2
    else:
        observed["stride_bytes"] += 2
    for output in render(actual_projection):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" in output
        assert "Settings comparison matched" not in output
