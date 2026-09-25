"""Semantic device profiles; physical target geometry is calibrated elsewhere."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _semantic_sha256(payload: Mapping[str, Any]) -> str:
    """Hash semantic behavior independently of Python mapping insertion order."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class KeyboardProfile:
    profile_id: str
    character_keys: Mapping[str, tuple[str, ...]]
    required_calibrations: tuple[str, ...] = (
        "camera_intrinsics",
        "eye_on_arm_extrinsic",
        "measured_tag_map",
        "robot_reference",
        "arm_board",
        "controller_correlation",
        "keyboard_pose",
        "keyboard_tcp",
        "keyboard_outcome_observer",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, "profile_id"))
        normalized: dict[str, tuple[str, ...]] = {}
        for character, keys in self.character_keys.items():
            if not isinstance(character, str) or len(character) != 1:
                raise ValueError("Keyboard profile character keys must be one Unicode code point")
            key_sequence = tuple(_identifier(key, "key id") for key in keys)
            if not key_sequence:
                raise ValueError(f"Character {character!r} has an empty key sequence")
            normalized[character] = key_sequence
        object.__setattr__(self, "character_keys", MappingProxyType(normalized))
        object.__setattr__(
            self,
            "required_calibrations",
            tuple(_identifier(value, "calibration id") for value in self.required_calibrations),
        )

    @property
    def semantic_content_sha256(self) -> str:
        """Content-address the complete character-to-key behavior and dependencies."""

        return _semantic_sha256(
            {
                "schema": "rocell.keyboard_semantic_profile.v1",
                "profile_id": self.profile_id,
                "character_keys": {
                    character: list(sequence)
                    for character, sequence in self.character_keys.items()
                },
                "required_calibrations": list(self.required_calibrations),
            }
        )


@dataclass(frozen=True, slots=True)
class PhoneKeySpec:
    target_id: str
    required_state: str
    resulting_state: str | None = None
    verify_after: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _identifier(self.target_id, "target_id"))
        object.__setattr__(self, "required_state", _identifier(self.required_state, "required_state"))
        if self.resulting_state is not None:
            object.__setattr__(
                self,
                "resulting_state",
                _identifier(self.resulting_state, "resulting_state"),
            )


@dataclass(frozen=True, slots=True)
class PhoneProfile:
    profile_id: str
    character_targets: Mapping[str, PhoneKeySpec]
    initial_state: str = "KEYBOARD_LOWER"
    required_calibrations: tuple[str, ...] = (
        "camera_intrinsics",
        "eye_on_arm_extrinsic",
        "measured_tag_map",
        "robot_reference",
        "arm_board",
        "controller_correlation",
        "phone_screen",
        "phone_tcp",
        "phone_ui_observer",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, "profile_id"))
        object.__setattr__(self, "initial_state", _identifier(self.initial_state, "initial_state"))
        normalized: dict[str, PhoneKeySpec] = {}
        for character, spec in self.character_targets.items():
            if not isinstance(character, str) or len(character) != 1:
                raise ValueError("Phone profile character keys must be one Unicode code point")
            if not isinstance(spec, PhoneKeySpec):
                raise TypeError("Phone target mappings must contain PhoneKeySpec values")
            normalized[character] = spec
        object.__setattr__(self, "character_targets", MappingProxyType(normalized))
        object.__setattr__(
            self,
            "required_calibrations",
            tuple(_identifier(value, "calibration id") for value in self.required_calibrations),
        )

    @property
    def semantic_content_sha256(self) -> str:
        """Content-address targets, UI-state transitions, verification, and dependencies."""

        return _semantic_sha256(
            {
                "schema": "rocell.phone_semantic_profile.v1",
                "profile_id": self.profile_id,
                "initial_state": self.initial_state,
                "character_targets": {
                    character: {
                        "target_id": spec.target_id,
                        "required_state": spec.required_state,
                        "resulting_state": spec.resulting_state,
                        "verify_after": spec.verify_after,
                    }
                    for character, spec in self.character_targets.items()
                },
                "required_calibrations": list(self.required_calibrations),
            }
        )
