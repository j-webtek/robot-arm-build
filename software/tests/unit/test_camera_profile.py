from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import pytest

from rocell.vision.camera_profile import (
    CAMERA_PROFILE_SCHEMA,
    DEFAULT_B0477_CAMERA_PROFILE,
    MAX_CAMERA_PROFILE_BYTES,
    CameraProfileError,
    load_camera_profile,
    parse_camera_profile_json,
)
from rocell.simulation.synthetic_raster import (
    MAX_SYNTHETIC_RASTER_HEIGHT_PX,
    MAX_SYNTHETIC_RASTER_PIXELS,
    MAX_SYNTHETIC_RASTER_WIDTH_PX,
)
from rocell.vision.pixel_detector import DEFAULT_MAXIMUM_IMAGE_PIXELS


def _document() -> dict[str, Any]:
    return json.loads(DEFAULT_B0477_CAMERA_PROFILE.read_text(encoding="utf-8"))


def _payload(document: object) -> bytes:
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def test_selected_b0477_profile_is_purchased_but_has_zero_live_authority() -> None:
    profile = load_camera_profile()

    assert profile.source_path == DEFAULT_B0477_CAMERA_PROFILE.resolve()
    assert profile.profile_id == "arducam-b0477-imx283-16mm-purchased-001"
    assert profile.record_state == "PURCHASED_PENDING_RECEIPT"
    assert (profile.manufacturer, profile.model, profile.sensor) == (
        "Arducam",
        "B0477",
        "Sony IMX283",
    )
    assert (profile.lens_mount, profile.focal_length_mm) == ("C-mount", 16.0)
    assert profile.live_ready is False
    assert profile.authority == {
        "hardware_presence_authority": False,
        "live_capture_authority": False,
        "calibration_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
    }
    assert profile.physical_observation_state == "OPEN_PENDING_RECEIPT_INSPECTION"
    assert profile.usb_observation_state == "OPEN_PENDING_ENUMERATION"
    assert profile.commissioning_state == "OPEN_NOT_COMMISSIONED"
    assert len(profile.open_blockers) == 8


def test_all_manufacturer_published_modes_are_retained_as_unmeasured_claims() -> None:
    profile = load_camera_profile()

    assert [
        (mode.host_bus, mode.width_px, mode.height_px, mode.maximum_fps, mode.pixel_format)
        for mode in profile.published_modes
    ] == [
        ("USB_3_2_GEN_1", 1280, 720, 120.0, "YUY2"),
        ("USB_3_2_GEN_1", 1920, 1080, 60.0, "YUY2"),
        ("USB_3_2_GEN_1", 2720, 1536, 40.0, "YUY2"),
        ("USB_3_2_GEN_1", 3840, 2160, 20.0, "YUY2"),
        ("USB_3_2_GEN_1", 5472, 3648, 9.0, "YUY2"),
        ("USB_2_0", 1280, 720, 10.0, "YUY2"),
    ]
    assert all(
        mode.evidence_state == "MANUFACTURER_PUBLISHED_UNMEASURED"
        for mode in profile.published_modes
    )
    native = profile.published_mode("USB_3_2_GEN_1", 5472, 3648)
    fallback = profile.published_mode("USB_2_0", 1280, 720)
    assert native is not None and native.maximum_fps == 9.0
    assert fallback is not None and fallback.maximum_fps == 10.0
    assert profile.published_mode("USB_2_0", 5472, 3648) is None


def test_provenance_separates_manufacturer_claims_from_user_purchase_report() -> None:
    profile = load_camera_profile()

    assert [source.source_kind for source in profile.provenance] == [
        "MANUFACTURER_DATASHEET",
        "MANUFACTURER_PRODUCT_PAGE",
        "USER_REPORT",
    ]
    assert profile.provenance[0].evidence_state == "PUBLISHED_NOT_MEASURED"
    assert profile.provenance[1].evidence_state == "PUBLISHED_NOT_MEASURED"
    assert profile.provenance[2].evidence_state == "USER_REPORTED_NOT_RECEIPT_VERIFIED"
    assert profile.provenance[2].url is None


def test_simulation_proxy_is_exact_half_scale_and_preserves_aspect_and_fov() -> None:
    proxy = load_camera_profile().simulation_proxy

    assert proxy.state == "SYNTHETIC_ONLY_NOT_PHYSICAL_CALIBRATION"
    assert proxy.calibration_state == "DERIVED_NOMINAL_NOT_PHYSICAL_CALIBRATION"
    assert proxy.scale == 0.5
    assert (proxy.source_width_px, proxy.source_height_px) == (5472, 3648)
    assert (proxy.width_px, proxy.height_px) == (2736, 1824)
    assert proxy.width_px * 2 == proxy.source_width_px
    assert proxy.height_px * 2 == proxy.source_height_px
    assert proxy.width_px * proxy.source_height_px == (
        proxy.height_px * proxy.source_width_px
    )
    assert proxy.aspect_ratio == 1.5

    recovered_horizontal, recovered_vertical = proxy.recovered_field_of_view_deg()
    assert math.isclose(recovered_horizontal, 49.0, abs_tol=1e-12)
    assert math.isclose(recovered_vertical, 38.0, abs_tol=1e-12)
    assert proxy.fx_px == proxy.width_px / (2.0 * math.tan(math.radians(24.5)))
    assert proxy.fy_px == proxy.height_px / (2.0 * math.tan(math.radians(19.0)))
    assert (proxy.cx_px, proxy.cy_px) == (1368.0, 912.0)


def test_simulation_proxy_fits_actual_current_raster_limits_and_grants_no_authority() -> None:
    profile = load_camera_profile()
    proxy = profile.simulation_proxy
    document = _document()

    assert proxy.pixel_count == 4_990_464
    assert proxy.synthetic_raster_max_width_px == MAX_SYNTHETIC_RASTER_WIDTH_PX
    assert proxy.synthetic_raster_max_height_px == MAX_SYNTHETIC_RASTER_HEIGHT_PX
    assert proxy.synthetic_raster_max_pixels == MAX_SYNTHETIC_RASTER_PIXELS
    assert proxy.pixel_detector_maximum_image_pixels == DEFAULT_MAXIMUM_IMAGE_PIXELS
    assert proxy.within_current_raster_limits is True
    assert set(document["simulation_proxy"]["authority"].values()) == {False}
    assert profile.live_ready is False


def test_canonical_digest_is_semantic_and_source_digest_is_byte_exact() -> None:
    document = _document()
    compact = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    pretty = json.dumps(document, indent=7, ensure_ascii=False).encode("utf-8")

    compact_profile = parse_camera_profile_json(compact)
    pretty_profile = parse_camera_profile_json(pretty)

    assert compact_profile.canonical_sha256 == pretty_profile.canonical_sha256
    assert compact_profile.source_file_sha256 != pretty_profile.source_file_sha256
    assert compact_profile.source_file_sha256 == hashlib.sha256(compact).hexdigest()
    assert len(compact_profile.canonical_sha256) == 64


@pytest.mark.parametrize(
    ("section", "mutation", "message"),
    [
        ("root", lambda doc: doc.__setitem__("surprise", True), "unknown"),
        (
            "mode",
            lambda doc: doc["published_native_modes"][4].__setitem__("maximum_fps", 30.0),
            "maximum_fps",
        ),
        (
            "authority",
            lambda doc: doc["authority"].__setitem__("live_capture_authority", True),
            "live_capture_authority",
        ),
        (
            "physical",
            lambda doc: doc["physical_observation"].__setitem__("model_label", "B0477"),
            "must remain null",
        ),
        (
            "usb",
            lambda doc: doc["usb_observation"].__setitem__("vid", "0x1234"),
            "must remain null",
        ),
        (
            "calibration",
            lambda doc: doc["commissioning"].__setitem__(
                "intrinsics_artifact_sha256", "0" * 64
            ),
            "must remain null",
        ),
        (
            "claim_class",
            lambda doc: doc["published_identity"].__setitem__(
                "evidence_state", "MEASURED"
            ),
            "evidence_state",
        ),
        (
            "blocker",
            lambda doc: doc["open_blockers"].pop(),
            "exact purchase-time holds",
        ),
    ],
)
def test_mutations_fail_closed(
    section: str,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    del section  # Gives parametrized failures a readable id without affecting behavior.
    document = deepcopy(_document())
    mutation(document)

    with pytest.raises(CameraProfileError, match=message):
        parse_camera_profile_json(_payload(document))


def test_nested_unknown_and_missing_fields_fail_closed() -> None:
    unknown = _document()
    unknown["published_optics"]["marketing_zoom"] = "none"
    with pytest.raises(CameraProfileError, match="unknown=.*marketing_zoom"):
        parse_camera_profile_json(_payload(unknown))

    missing = _document()
    del missing["usb_observation"]["serial_number"]
    with pytest.raises(CameraProfileError, match="missing=.*serial_number"):
        parse_camera_profile_json(_payload(missing))


def test_strict_json_boundary_rejects_duplicate_nonfinite_invalid_and_large_input() -> None:
    with pytest.raises(CameraProfileError, match="duplicate key 'schema'"):
        parse_camera_profile_json(
            b'{"schema":"rocell.purchased_camera_profile.v1","schema":null}'
        )
    with pytest.raises(CameraProfileError, match="invalid JSON constant 'NaN'"):
        parse_camera_profile_json(b'{"value":NaN}')
    with pytest.raises(CameraProfileError, match="must be UTF-8"):
        parse_camera_profile_json(b"\xff")
    with pytest.raises(CameraProfileError, match="empty"):
        parse_camera_profile_json(b"")
    with pytest.raises(CameraProfileError, match="exceeds"):
        parse_camera_profile_json(b" " * (MAX_CAMERA_PROFILE_BYTES + 1))


def test_schema_and_purchase_state_are_exact() -> None:
    document = _document()
    assert document["schema"] == CAMERA_PROFILE_SCHEMA

    document["record_state"] = "RECEIVED"
    with pytest.raises(CameraProfileError, match="record_state"):
        parse_camera_profile_json(_payload(document))


def test_missing_profile_is_reported_without_device_access(tmp_path: Path) -> None:
    missing = tmp_path / "not-present.json"
    with pytest.raises(CameraProfileError, match="cannot read camera profile"):
        load_camera_profile(missing)
