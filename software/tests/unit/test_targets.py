from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.targets import TargetMapError, load_nominal_target_catalog
from rocell.typing import development_keyboard_profile, development_phone_profile


@pytest.fixture
def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_actual_nominal_catalog_is_aligned_and_nonexecuting(workspace_root: Path) -> None:
    catalog = load_nominal_target_catalog(workspace_root)

    assert catalog.simulation_only is True
    assert catalog.to_dict()["physical_release_effect"] == "NONE"
    assert len(catalog.keyboard_targets) == 46
    assert len(catalog.phone_targets) == 29
    assert catalog.resolve("keyboard", "A").center.frame == "board"
    assert catalog.resolve("phone", "key_a").center.z == pytest.approx(11.9)
    assert catalog.keyboard_semantic_profile_id == (
        "development/keyboard-us-lowercase-semantic-v1"
    )
    assert catalog.phone_semantic_profile_id == (
        "development/phone-lowercase-semantic-v1"
    )
    assert catalog.keyboard_semantic_profile_sha256 == (
        development_keyboard_profile().semantic_content_sha256
    )
    assert catalog.phone_semantic_profile_sha256 == (
        development_phone_profile().semantic_content_sha256
    )


def test_catalog_covers_development_typing_targets(workspace_root: Path) -> None:
    catalog = load_nominal_target_catalog(workspace_root)
    keyboard_required = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") | {
        "SPACE",
        "ENTER",
        "TAB",
        "PERIOD",
        "COMMA",
        "MINUS",
        "EQUAL",
        "SLASH",
        "SEMICOLON",
        "APOSTROPHE",
    }
    phone_required = {f"key_{letter}" for letter in "abcdefghijklmnopqrstuvwxyz"} | {
        "key_space",
        "key_period",
        "key_enter",
    }
    assert keyboard_required == set(catalog.keyboard_targets)
    assert phone_required == set(catalog.phone_targets)


def test_every_safe_rectangle_stays_inside_rc03_device_envelope(workspace_root: Path) -> None:
    catalog = load_nominal_target_catalog(workspace_root)
    envelopes = {
        "keyboard": (85.0, 85.0, 85.0 + 315.0, 85.0 + 147.0),
        "phone": (499.2, 84.2, 499.2 + 77.9, 84.2 + 164.4),
    }
    for device, targets in (
        ("keyboard", catalog.keyboard_targets),
        ("phone", catalog.phone_targets),
    ):
        envelope = envelopes[device]
        for target in targets.values():
            left, front, right, rear = target.safe_rectangle_board_mm
            assert envelope[0] <= left < right <= envelope[2]
            assert envelope[1] <= front < rear <= envelope[3]


def test_import_rejects_profile_that_can_affect_physical_release(
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    original = json.loads(
        (workspace_root / "software/config/nominal_target_profiles.json").read_text(
            encoding="utf-8"
        )
    )
    original["physical_release_effect"] = "PASS"
    changed = tmp_path / "targets.json"
    changed.write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(TargetMapError, match="no physical release effect"):
        load_nominal_target_catalog(workspace_root, changed)


def test_unknown_target_fails_closed(workspace_root: Path) -> None:
    catalog = load_nominal_target_catalog(workspace_root)
    with pytest.raises(TargetMapError, match="Unknown keyboard target"):
        catalog.resolve("keyboard", "NOT_A_KEY")


def test_import_rejects_missing_semantic_profile_binding(
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    original = json.loads(
        (workspace_root / "software/config/nominal_target_profiles.json").read_text(
            encoding="utf-8"
        )
    )
    del original["keyboard"]["semantic_profile_id"]
    changed = tmp_path / "targets.json"
    changed.write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(TargetMapError, match="semantic_profile_id"):
        load_nominal_target_catalog(workspace_root, changed)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("keyboard", "pitch_mm", 20.0), "pitch_mm"),
        (("keyboard", "semantic_profile_sha256", "not-a-digest"), "SHA-256"),
        (("phone", "orientation", "landscape"), "orientation"),
        (("phone", "ui_state_id", "SYMBOLS"), "KEYBOARD_LOWER"),
        (
            ("phone", "synthetic_gboard_region_local_rect_mm", [0, 0, 20, 20]),
            "Gboard region",
        ),
    ],
)
def test_import_rejects_changed_coordinate_and_ui_contracts(
    workspace_root: Path,
    tmp_path: Path,
    mutation: tuple[str, str, object],
    message: str,
) -> None:
    document = json.loads(
        (workspace_root / "software/config/nominal_target_profiles.json").read_text(
            encoding="utf-8"
        )
    )
    device, field, value = mutation
    document[device][field] = value
    changed = tmp_path / f"{device}-{field}.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(TargetMapError, match=message):
        load_nominal_target_catalog(workspace_root, changed)
