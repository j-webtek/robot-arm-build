from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
from typing import cast

import pytest

import rocell.vision.uvc_inventory as uvc_module
from rocell.vision.camera_profile import PurchasedCameraProfile, load_camera_profile
from rocell.vision.uvc_inventory import (
    DETERMINISTIC_FAKE_PROVIDER_ID,
    MAX_CONTROLS_PER_SNAPSHOT,
    MAX_DEVICES_PER_SNAPSHOT,
    MAX_MODES_PER_DEVICE,
    MAX_REOPEN_SNAPSHOTS,
    MAX_UVC_INVENTORY_BYTES,
    DeterministicFakeUvcInventoryProvider,
    UvcCaptureControl,
    UvcDevice,
    UvcDeviceIdentity,
    UvcInventory,
    UvcInventoryError,
    UvcInventoryProvider,
    UvcMode,
    UvcReopenSnapshot,
    assess_uvc_inventory,
    assessment_checks_by_id,
    collect_uvc_inventory,
    parse_uvc_inventory_json,
)


PERSISTENT_PATH = "usb://vid_2bc5&pid_0477/B0477-SIM-0001"


def _target_mode() -> UvcMode:
    return UvcMode(
        width_px=5472,
        height_px=3648,
        fps=9.0,
        fourcc="YUY2",
        host_bus="USB_3_2_GEN_1",
    )


def _fast_mode() -> UvcMode:
    return UvcMode(
        width_px=1280,
        height_px=720,
        fps=120.0,
        fourcc="YUY2",
        host_bus="USB_3_2_GEN_1",
    )


def _identity(
    *,
    serial_number: str | None = "B0477-SIM-0001",
    persistent_path: str | None = PERSISTENT_PATH,
    manufacturer: str = "Arducam",
    product: str = "Arducam B0477 20MP USB Camera",
) -> UvcDeviceIdentity:
    return UvcDeviceIdentity(
        vid="2bc5",
        pid="0477",
        serial_number=serial_number,
        persistent_path=persistent_path,
        manufacturer=manufacturer,
        product=product,
    )


def _controls(
    *,
    exposure_mode: str = "manual",
    exposure_value: float = -6.0,
    white_balance_mode: str = "manual",
) -> tuple[UvcCaptureControl, ...]:
    return (
        UvcCaptureControl("exposure", exposure_mode, exposure_value, "ev"),
        UvcCaptureControl(
            "white_balance", white_balance_mode, 4500.0, "kelvin"
        ),
        UvcCaptureControl("gain", "manual", 1.0, "relative"),
    )


def _snapshot(
    ordinal: int,
    *,
    identity: UvcDeviceIdentity | None = None,
    modes: tuple[UvcMode, ...] | None = None,
    selected_mode: UvcMode | None = None,
    negotiated_bus: str = "USB_3_2_GEN_1",
    controls: tuple[UvcCaptureControl, ...] | None = None,
    extra_devices: tuple[UvcDevice, ...] = (),
) -> UvcReopenSnapshot:
    device = UvcDevice(
        identity=identity or _identity(),
        modes=modes or (_target_mode(), _fast_mode()),
    )
    return UvcReopenSnapshot(
        reopen_ordinal=ordinal,
        devices=(device,) + extra_devices,
        negotiated_bus=negotiated_bus,
        selected_mode=selected_mode or _target_mode(),
        controls=controls or _controls(),
    )


def _inventory(
    profile: PurchasedCameraProfile,
    *,
    snapshots: tuple[UvcReopenSnapshot, ...] | None = None,
    profile_id: str | None = None,
    profile_sha256: str | None = None,
    selector_value: str = PERSISTENT_PATH,
    provider_id: str = DETERMINISTIC_FAKE_PROVIDER_ID,
    hardware_accessed: bool = False,
) -> UvcInventory:
    return UvcInventory(
        profile_id=profile_id or profile.profile_id,
        profile_sha256=profile_sha256 or profile.canonical_sha256,
        provider_id=provider_id,
        hardware_accessed=hardware_accessed,
        selector_kind="persistent_path",
        selector_value=selector_value,
        reopen_snapshots=snapshots or (_snapshot(0), _snapshot(1)),
    )


@pytest.fixture(scope="module")
def profile() -> PurchasedCameraProfile:
    return load_camera_profile()


def _checks(profile: PurchasedCameraProfile, inventory: UvcInventory) -> dict[str, bool]:
    report = assess_uvc_inventory(profile, inventory)
    return {check.check_id: check.passed for check in report.checks}


def test_valid_fake_inventory_passes_only_the_diagnostic_rehearsal(
    profile: PurchasedCameraProfile,
) -> None:
    inventory = _inventory(profile)
    provider = DeterministicFakeUvcInventoryProvider(inventory)

    assert isinstance(provider, UvcInventoryProvider)
    assert collect_uvc_inventory(provider) is inventory
    assert collect_uvc_inventory(provider) is inventory

    report = assess_uvc_inventory(profile, inventory)
    assert report.status == "DIAGNOSTIC_REHEARSAL_PASS"
    assert report.passed is True
    assert all(check.passed for check in report.checks)
    assert report.purpose == "DIAGNOSTIC_REHEARSAL_ONLY"
    assert report.hardware_accessed is False
    assert report.live_capture_performed is False
    assert report.camera_frames_requested == 0
    assert report.arm_commands == 0
    assert report.commissioned is False
    assert report.live_capture_authority is False
    assert report.robot_motion_authority is False
    assert report.contact_authority is False
    assert report.physical_release_effect == "NONE"
    assert len(report.canonical_sha256) == 64
    assert report.inventory_sha256 == inventory.canonical_sha256
    assert assessment_checks_by_id(report)["native_mode_selected"].passed is True

    document = report.to_dict()
    assert document["execution"] == {
        "hardware_accessed": False,
        "live_capture_performed": False,
        "camera_frames_requested": 0,
        "arm_commands": 0,
    }
    assert document["authority"] == {
        "commissioned": False,
        "live_capture_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "physical_release_effect": "NONE",
    }


def test_models_are_immutable_and_do_not_import_opencv(
    profile: PurchasedCameraProfile,
) -> None:
    inventory = _inventory(profile)
    with pytest.raises(FrozenInstanceError):
        inventory.hardware_accessed = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        inventory.reopen_snapshots[0].negotiated_bus = "USB_2_0"  # type: ignore[misc]
    assert isinstance(inventory.reopen_snapshots, tuple)
    assert "cv2" not in vars(uvc_module)


def test_identity_and_selector_reject_numeric_indices_and_noncanonical_hex(
    profile: PurchasedCameraProfile,
) -> None:
    with pytest.raises(UvcInventoryError, match="lowercase hex"):
        replace(_identity(), vid="2BC5")
    with pytest.raises(UvcInventoryError, match="lowercase hex"):
        replace(_identity(), pid="0x47")
    with pytest.raises(UvcInventoryError, match="numeric camera index"):
        replace(_identity(), persistent_path="0")
    with pytest.raises(UvcInventoryError, match="numeric camera index"):
        _inventory(profile, selector_value="12")
    with pytest.raises(UvcInventoryError, match="selector_kind"):
        replace(_inventory(profile), selector_kind="camera_index")


@pytest.mark.parametrize(
    ("identity", "failed_check"),
    [
        (_identity(serial_number=None), "identity_policy"),
        (_identity(persistent_path=None), "persistent_selector"),
        (_identity(manufacturer="Not Arducam"), "profile_product"),
        (_identity(product="Generic USB Camera"), "profile_product"),
    ],
)
def test_missing_stable_identity_or_wrong_product_is_blocked(
    profile: PurchasedCameraProfile,
    identity: UvcDeviceIdentity,
    failed_check: str,
) -> None:
    inventory = _inventory(
        profile,
        snapshots=(_snapshot(0, identity=identity), _snapshot(1, identity=identity)),
    )

    report = assess_uvc_inventory(profile, inventory)
    assert report.status == "DIAGNOSTIC_REHEARSAL_BLOCKED"
    assert _checks(profile, inventory)[failed_check] is False
    assert report.commissioned is False


def test_wrong_profile_id_or_digest_is_blocked(profile: PurchasedCameraProfile) -> None:
    wrong_id = _inventory(profile, profile_id="another-purchased-profile")
    wrong_digest = _inventory(profile, profile_sha256="0" * 64)

    assert _checks(profile, wrong_id)["profile_binding"] is False
    assert _checks(profile, wrong_digest)["profile_binding"] is False


def test_duplicate_device_identity_path_mode_or_control_is_ambiguous(
    profile: PurchasedCameraProfile,
) -> None:
    duplicate_device = UvcDevice(_identity(), (_target_mode(), _fast_mode()))
    ambiguous = _inventory(
        profile,
        snapshots=(
            _snapshot(0, extra_devices=(duplicate_device,)),
            _snapshot(1, extra_devices=(duplicate_device,)),
        ),
    )
    duplicate_mode = _inventory(
        profile,
        snapshots=(
            _snapshot(0, modes=(_target_mode(), _target_mode())),
            _snapshot(1, modes=(_target_mode(), _target_mode())),
        ),
    )
    duplicate_controls = _controls() + (
        UvcCaptureControl("exposure", "manual", -6.0, "ev"),
    )
    duplicate_control = _inventory(
        profile,
        snapshots=(
            _snapshot(0, controls=duplicate_controls),
            _snapshot(1, controls=duplicate_controls),
        ),
    )

    assert _checks(profile, ambiguous)["unique_inventory"] is False
    assert _checks(profile, ambiguous)["persistent_selector"] is False
    assert _checks(profile, duplicate_mode)["unique_inventory"] is False
    assert _checks(profile, duplicate_control)["unique_inventory"] is False
    assert _checks(profile, duplicate_control)["manual_exposure"] is False


def test_missing_exact_native_mode_is_blocked(profile: PurchasedCameraProfile) -> None:
    snapshots = (
        _snapshot(0, modes=(_fast_mode(),)),
        _snapshot(1, modes=(_fast_mode(),)),
    )
    checks = _checks(profile, _inventory(profile, snapshots=snapshots))

    assert checks["native_mode_advertised"] is False
    assert checks["native_mode_selected"] is False


def test_usb2_downgrade_is_blocked(profile: PurchasedCameraProfile) -> None:
    fallback = UvcMode(1280, 720, 10.0, "YUY2", "USB_2_0")
    snapshots = (
        _snapshot(
            0,
            modes=(_target_mode(), fallback),
            selected_mode=fallback,
            negotiated_bus="USB_2_0",
        ),
        _snapshot(
            1,
            modes=(_target_mode(), fallback),
            selected_mode=fallback,
            negotiated_bus="USB_2_0",
        ),
    )
    checks = _checks(profile, _inventory(profile, snapshots=snapshots))

    assert checks["usb3_negotiated"] is False
    assert checks["native_mode_selected"] is False


@pytest.mark.parametrize(
    ("controls", "failed_check"),
    [
        (_controls(exposure_mode="automatic"), "manual_exposure"),
        (_controls(white_balance_mode="automatic"), "manual_white_balance"),
        (
            tuple(control for control in _controls() if control.control_id != "exposure"),
            "manual_exposure",
        ),
    ],
)
def test_automatic_or_missing_required_controls_are_blocked(
    profile: PurchasedCameraProfile,
    controls: tuple[UvcCaptureControl, ...],
    failed_check: str,
) -> None:
    snapshots = (_snapshot(0, controls=controls), _snapshot(1, controls=controls))
    assert _checks(profile, _inventory(profile, snapshots=snapshots))[failed_check] is False


def test_setting_drift_after_reopen_is_blocked(profile: PurchasedCameraProfile) -> None:
    snapshots = (
        _snapshot(0, controls=_controls(exposure_value=-6.0)),
        _snapshot(1, controls=_controls(exposure_value=-5.0)),
    )
    inventory = _inventory(profile, snapshots=snapshots)

    assert snapshots[0].settings_sha256 != snapshots[1].settings_sha256
    assert _checks(profile, inventory)["settings_stability"] is False


def test_reconnect_identity_drift_is_blocked(profile: PurchasedCameraProfile) -> None:
    snapshots = (
        _snapshot(0),
        _snapshot(1, identity=_identity(serial_number="B0477-SIM-CHANGED")),
    )
    checks = _checks(profile, _inventory(profile, snapshots=snapshots))

    assert checks["persistent_selector"] is True
    assert checks["reconnect_identity"] is False


def test_inventory_json_is_strict_bounded_and_has_byte_and_canonical_hashes(
    profile: PurchasedCameraProfile,
) -> None:
    original = _inventory(profile)
    payload = json.dumps(original.to_dict(), indent=2).encode("utf-8")
    parsed = parse_uvc_inventory_json(payload)

    assert parsed.to_dict() == original.to_dict()
    assert parsed.source_file_sha256 == hashlib.sha256(payload).hexdigest()
    assert parsed.canonical_sha256 == original.canonical_sha256

    # Enumeration order is not evidence and therefore cannot alter the digest.
    reordered_snapshots = tuple(
        replace(
            snapshot,
            devices=tuple(reversed(snapshot.devices)),
            controls=tuple(reversed(snapshot.controls)),
        )
        for snapshot in original.reopen_snapshots
    )
    assert replace(original, reopen_snapshots=reordered_snapshots).canonical_sha256 == (
        original.canonical_sha256
    )

    unknown = original.to_dict()
    cast(dict[str, object], unknown)["unexpected"] = False
    with pytest.raises(UvcInventoryError, match="unknown=.*unexpected"):
        parse_uvc_inventory_json(json.dumps(unknown).encode())

    missing = original.to_dict()
    del cast(dict[str, object], missing["selector"])["value"]
    with pytest.raises(UvcInventoryError, match="missing=.*value"):
        parse_uvc_inventory_json(json.dumps(missing).encode())

    overclaim = original.to_dict()
    cast(dict[str, object], overclaim["authority"])["commissioned"] = True
    with pytest.raises(UvcInventoryError, match="must remain false"):
        parse_uvc_inventory_json(json.dumps(overclaim).encode())

    with pytest.raises(UvcInventoryError, match="duplicate key 'schema'"):
        parse_uvc_inventory_json(b'{"schema":"a","schema":"b"}')
    with pytest.raises(UvcInventoryError, match="invalid JSON constant"):
        parse_uvc_inventory_json(b'{"value":NaN}')
    with pytest.raises(UvcInventoryError, match="UTF-8"):
        parse_uvc_inventory_json(b"\xff")
    with pytest.raises(UvcInventoryError, match="empty"):
        parse_uvc_inventory_json(b"")
    with pytest.raises(UvcInventoryError, match="exceeds"):
        parse_uvc_inventory_json(b" " * (MAX_UVC_INVENTORY_BYTES + 1))


def test_resource_and_numeric_validation_fail_closed(
    profile: PurchasedCameraProfile,
) -> None:
    with pytest.raises(UvcInventoryError, match="mode.width_px"):
        replace(_target_mode(), width_px=0)
    with pytest.raises(UvcInventoryError, match="mode.fps"):
        replace(_target_mode(), fps=math.inf)
    with pytest.raises(UvcInventoryError, match="fourcc"):
        replace(_target_mode(), fourcc="yuy2")
    with pytest.raises(UvcInventoryError, match="control.value"):
        UvcCaptureControl("gain", "manual", math.nan, "relative")
    with pytest.raises(UvcInventoryError, match="device.modes"):
        UvcDevice(_identity(), tuple(_target_mode() for _ in range(MAX_MODES_PER_DEVICE + 1)))
    with pytest.raises(UvcInventoryError, match="snapshot.devices"):
        replace(
            _snapshot(0),
            devices=tuple(
                UvcDevice(
                    _identity(
                        serial_number=f"serial-{index}",
                        persistent_path=f"usb://device/{index}",
                    ),
                    (_target_mode(),),
                )
                for index in range(MAX_DEVICES_PER_SNAPSHOT + 1)
            ),
        )
    with pytest.raises(UvcInventoryError, match="snapshot.controls"):
        replace(
            _snapshot(0),
            controls=tuple(
                UvcCaptureControl(f"control_{index}", "manual", 0.0, "raw")
                for index in range(MAX_CONTROLS_PER_SNAPSHOT + 1)
            ),
        )
    base = _inventory(profile)
    too_many_document = base.to_dict()
    snapshots = cast(list[dict[str, object]], too_many_document["reopen_snapshots"])
    snapshots.extend(snapshots[:1] * (MAX_REOPEN_SNAPSHOTS - len(snapshots) + 1))
    with pytest.raises(UvcInventoryError, match="reopen_snapshots"):
        parse_uvc_inventory_json(json.dumps(too_many_document).encode())


def test_provider_seam_rejects_provenance_spoofing(
    profile: PurchasedCameraProfile,
) -> None:
    inventory = _inventory(profile)

    class SpoofedProvider:
        provider_id = "different_provider"
        hardware_accessed = False

        def collect_inventory(self) -> UvcInventory:
            return inventory

    with pytest.raises(UvcInventoryError, match="provider_id differs"):
        collect_uvc_inventory(SpoofedProvider())

    with pytest.raises(UvcInventoryError, match="fake inventory cannot claim"):
        DeterministicFakeUvcInventoryProvider(
            _inventory(profile, hardware_accessed=True)
        )
