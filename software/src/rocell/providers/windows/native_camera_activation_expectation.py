"""Closed activation expectation data, with no enrollment, device or I/O access.

A valid expectation is not authority or proof of a current physical identity.
"""

from dataclasses import dataclass
import re
from typing import Any

from rocell.providers.windows.native_camera_protocol import canonical, digest, _load

SCHEMA = "rocell.camera_activation_identity_expectation.v1"
MAX_BYTES = 16 * 1024
FIELDS = {
    "schema",
    "original_identity_sha256",
    "endpoint",
    "instance_id",
    "container_id",
    "location_paths_json",
    "driver_provider",
    "driver_service",
    "driver_version",
    "driver_inf",
}


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def text(value: Any, maximum_units: int) -> None:
    require(type(value) is str and bool(value), "ACTIVATION_TEXT_REQUIRED")
    try:
        units, size = len(value.encode("utf-16-le")) // 2, len(value.encode("utf-8"))
    except UnicodeError:
        raise ValueError("ACTIVATION_INVALID_UNICODE") from None
    require(units <= maximum_units and size <= 4096, "ACTIVATION_TEXT_BOUNDS")
    require(
        not any(ord(c) < 32 or ord(c) == 127 for c in value),
        "ACTIVATION_CONTROL_CHARACTER",
    )


def document(payload: bytes) -> dict[str, Any]:
    value = _load(payload, MAX_BYTES - 1, line=False)
    require(
        set(value) == FIELDS and value["schema"] == SCHEMA,
        "ACTIVATION_EXPECTATION_SCHEMA",
    )
    require(
        all(type(item) is str for item in value.values()), "ACTIVATION_STRING_FIELDS"
    )
    require(
        bool(re.fullmatch(r"[0-9a-f]{64}", value["original_identity_sha256"]))
        and value["original_identity_sha256"] != "0" * 64,
        "ACTIVATION_ORIGINAL_IDENTITY_HASH",
    )
    text(value["endpoint"], 4096)
    for field in (
        "instance_id",
        "driver_provider",
        "driver_service",
        "driver_version",
        "driver_inf",
    ):
        text(value[field], 1024)
    require(
        bool(
            re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                value["container_id"],
            )
        )
        and value["container_id"] != "00000000-0000-0000-0000-000000000000",
        "ACTIVATION_CONTAINER",
    )
    paths = _load(
        value["location_paths_json"].encode("ascii"), MAX_BYTES - 1, line=False
    )
    require(
        1 <= len(paths) <= 16
        and list(paths) == [f"path_{i:02d}" for i in range(len(paths))],
        "ACTIVATION_LOCATION_ORDER",
    )
    for path in paths.values():
        text(path, 1024)
    require(len(set(paths.values())) == len(paths), "ACTIVATION_DUPLICATE_LOCATION")
    return value


@dataclass(frozen=True, slots=True)
class CameraActivationExpectation:
    payload: bytes

    def __post_init__(self) -> None:
        document(self.payload)

    @property
    def sha256(self) -> str:
        document(self.payload)
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return document(self.payload)
