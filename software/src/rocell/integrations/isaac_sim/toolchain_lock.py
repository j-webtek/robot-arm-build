"""Fail-closed selection record for an external Isaac Sim installation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import IsaacSimContractError

LOCK_SCHEMA = "rocell.isaac_sim_toolchain_lock.v1"
_FIELDS = {
    "schema", "selection_status", "isaac_sim_version", "installation_sha256",
    "extension_lock_sha256", "settings_profile_sha256", "runner_platform",
    "launch_method", "license_review_status", "hardware_access",
    "physical_authority", "wire_commands",
}


@dataclass(frozen=True, slots=True)
class IsaacSimToolchainLock:
    isaac_sim_version: str
    installation_sha256: str
    extension_lock_sha256: str
    settings_profile_sha256: str
    runner_platform: str
    launch_method: str
    license_review_status: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IsaacSimToolchainLock":
        if not isinstance(value, Mapping):
            raise IsaacSimContractError("toolchain lock must be an object")
        missing = sorted(_FIELDS.difference(value))
        extra = sorted(set(value).difference(_FIELDS))
        if missing:
            raise IsaacSimContractError(
                f"toolchain lock missing fields: {', '.join(missing)}")
        if extra:
            raise IsaacSimContractError(
                f"toolchain lock has unknown fields: {', '.join(extra)}")
        if value["schema"] != LOCK_SCHEMA:
            raise IsaacSimContractError("unsupported toolchain lock schema")
        if value["selection_status"] != "SELECTED":
            raise IsaacSimContractError("Isaac Sim toolchain is not selected")
        if value["hardware_access"] is not False or value["physical_authority"] is not False or value["wire_commands"] != []:
            raise IsaacSimContractError("toolchain lock violates zero authority")
        required_text = (
            "isaac_sim_version", "runner_platform", "launch_method",
            "license_review_status",
        )
        for field in required_text:
            if not isinstance(value[field], str) or not value[field]:
                raise IsaacSimContractError(f"toolchain lock {field} is unselected")
        if value["license_review_status"] != "REVIEWED_FOR_INTERNAL_INTEGRATION":
            raise IsaacSimContractError("toolchain license review is incomplete")
        digests = (
            "installation_sha256", "extension_lock_sha256",
            "settings_profile_sha256",
        )
        for field in digests:
            digest = value[field]
            if not isinstance(digest, str) or len(digest) != 64:
                raise IsaacSimContractError(f"toolchain lock {field} is invalid")
            try:
                int(digest, 16)
            except ValueError as exc:
                raise IsaacSimContractError(
                    f"toolchain lock {field} is invalid") from exc
            if digest.lower() != digest:
                raise IsaacSimContractError(
                    f"toolchain lock {field} is invalid")
        return cls(**{field: value[field] for field in (
            "isaac_sim_version", "installation_sha256",
            "extension_lock_sha256", "settings_profile_sha256",
            "runner_platform", "launch_method", "license_review_status",
        )})

    @classmethod
    def load(cls, path: Path) -> "IsaacSimToolchainLock":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IsaacSimContractError(
                f"cannot load Isaac Sim toolchain lock: {path}") from exc
        return cls.from_dict(value)

