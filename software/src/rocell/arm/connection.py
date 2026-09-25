"""Strict, non-opening loader for the controlled RoArm serial identity."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


class ArmConnectionConfigurationError(ValueError):
    """The serial/identity profile is malformed or not commissioned."""


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate fields instead of silently accepting the last value.

    Connection settings sit immediately in front of the only live hardware
    adapter currently exposed by the CLI. Ambiguous JSON must therefore fail
    before a serial backend can be imported or opened.
    """

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArmConnectionConfigurationError(
                f"Duplicate arm connection field {key!r}"
            )
        result[key] = value
    return result


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArmConnectionConfigurationError(f"{name} must be non-empty text")
    return value.strip()


def _optional_text(value: object, name: str) -> str | None:
    return None if value is None else _text(value, name)


def _positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArmConnectionConfigurationError(f"{name} must be a positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ArmConnectionConfigurationError(f"{name} must be a positive number")
    return result


@dataclass(frozen=True, slots=True)
class ArmConnectionProfile:
    """Controlled serial settings and observed identity evidence.

    Loading this type performs no import, enumeration, serial open, reset, or
    controller command.
    """

    profile_id: str
    model: str
    port: str | None
    baudrate: int
    read_timeout_s: float
    write_timeout_s: float
    controller_usb_identity: str | None
    arm_serial_number: str | None
    firmware_revision: str | None
    identity_state: str
    auto_connect: bool
    auto_initialize: bool
    rts: bool
    dtr: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile id"))
        object.__setattr__(self, "model", _text(self.model, "model"))
        object.__setattr__(self, "port", _optional_text(self.port, "port"))
        object.__setattr__(
            self, "identity_state", _text(self.identity_state, "identity state")
        )
        for name in (
            "controller_usb_identity",
            "arm_serial_number",
            "firmware_revision",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(getattr(self, name), name),
            )
        if isinstance(self.baudrate, bool) or self.baudrate != 115200:
            raise ArmConnectionConfigurationError("RoArm baudrate must be 115200")
        object.__setattr__(
            self, "read_timeout_s", _positive(self.read_timeout_s, "read timeout")
        )
        object.__setattr__(
            self, "write_timeout_s", _positive(self.write_timeout_s, "write timeout")
        )
        for name in ("auto_connect", "auto_initialize", "rts", "dtr"):
            if not isinstance(getattr(self, name), bool):
                raise ArmConnectionConfigurationError(f"{name} must be boolean")

    @property
    def commissioned(self) -> bool:
        return (
            self.port is not None
            and self.controller_usb_identity is not None
            and self.arm_serial_number is not None
            and self.firmware_revision is not None
            and self.identity_state == "QUALIFIED"
            and self.auto_connect is False
            and self.auto_initialize is False
            and self.rts is False
            and self.dtr is False
        )

    def require_commissioned_port(self, requested_port: str) -> None:
        """Fail closed unless the request exactly matches qualified evidence."""

        selected = _text(requested_port, "requested port")
        if not self.commissioned:
            raise ArmConnectionConfigurationError(
                "Arm connection identity is not fully commissioned"
            )
        if selected != self.port:
            raise ArmConnectionConfigurationError(
                "Requested serial port does not match the commissioned port identity"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "model": self.model,
            "transport": "usb_serial",
            "port": self.port,
            "baudrate": self.baudrate,
            "read_timeout_s": self.read_timeout_s,
            "write_timeout_s": self.write_timeout_s,
            "identity": {
                "controller_usb_identity": self.controller_usb_identity,
                "arm_serial_number": self.arm_serial_number,
                "firmware_revision": self.firmware_revision,
                "state": self.identity_state,
            },
            "commissioned": self.commissioned,
            "auto_connect": self.auto_connect,
            "auto_initialize": self.auto_initialize,
            "rts": self.rts,
            "dtr": self.dtr,
            "hardware_accessed": False,
        }


def load_arm_connection_profile(
    workspace: Path,
    profile_path: Path | None = None,
) -> ArmConnectionProfile:
    """Load the controlled serial profile without touching a serial backend."""

    root = Path(workspace).resolve()
    selected = (
        Path(profile_path).resolve()
        if profile_path is not None
        else (root / "software/config/arm_connection.json").resolve()
    )
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise ArmConnectionConfigurationError(
            "Arm connection profile must be beneath the workspace"
        ) from exc
    try:
        document = json.loads(
            selected.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ArmConnectionConfigurationError(
                    f"Nonfinite arm connection value {value!r}"
                )
            ),
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ArmConnectionConfigurationError,
    ) as exc:
        raise ArmConnectionConfigurationError(
            f"Could not read arm connection profile: {exc}"
        ) from exc
    if not isinstance(document, Mapping):
        raise ArmConnectionConfigurationError("Arm connection profile must be an object")
    if document.get("schema_version") != 1:
        raise ArmConnectionConfigurationError("Unsupported arm connection schema")
    if document.get("model") != "Waveshare RoArm-M3 Pro":
        raise ArmConnectionConfigurationError("Arm connection model is not RoArm-M3 Pro")
    if document.get("transport") != "usb_serial":
        raise ArmConnectionConfigurationError("Arm transport must be usb_serial")
    if document.get("wire_format") != "newline_terminated_json":
        raise ArmConnectionConfigurationError("Arm wire format must be newline JSON")
    if document.get("transmit_terminator") != "LF":
        raise ArmConnectionConfigurationError("Arm transmit terminator must be LF")
    if document.get("accepted_receive_terminators") != ["LF", "CRLF"]:
        raise ArmConnectionConfigurationError("Arm receive terminator contract changed")
    for field_name in (
        "blind_retry",
        "auto_connect",
        "auto_initialize",
        "rts",
        "dtr",
    ):
        if not isinstance(document.get(field_name), bool):
            raise ArmConnectionConfigurationError(f"{field_name} must be boolean")
    if document.get("blind_retry") is not False:
        raise ArmConnectionConfigurationError("Blind serial retry must remain disabled")
    for field_name in ("auto_connect", "auto_initialize", "rts", "dtr"):
        if document.get(field_name) is not False:
            raise ArmConnectionConfigurationError(f"{field_name} must remain disabled")
    if document.get("exclusive_owner_required") is not True:
        raise ArmConnectionConfigurationError("Serial transport must require one owner")
    baud = document.get("baud")
    if isinstance(baud, bool) or not isinstance(baud, int) or baud != 115200:
        raise ArmConnectionConfigurationError("RoArm baud must be the controlled 115200")
    identity = document.get("identity")
    if not isinstance(identity, Mapping):
        raise ArmConnectionConfigurationError("Arm identity must be an object")
    return ArmConnectionProfile(
        profile_id=_text(document.get("profile_id"), "profile id"),
        model=_text(document.get("model"), "model"),
        port=_optional_text(document.get("port"), "port"),
        baudrate=baud,
        read_timeout_s=_positive(document.get("read_timeout_s"), "read timeout"),
        write_timeout_s=_positive(document.get("write_timeout_s"), "write timeout"),
        controller_usb_identity=_optional_text(
            identity.get("controller_usb_identity"), "controller USB identity"
        ),
        arm_serial_number=_optional_text(identity.get("arm_serial_number"), "arm serial"),
        firmware_revision=_optional_text(
            identity.get("firmware_revision"), "firmware revision"
        ),
        identity_state=_text(identity.get("state"), "identity state"),
        auto_connect=document["auto_connect"],
        auto_initialize=document["auto_initialize"],
        rts=document["rts"],
        dtr=document["dtr"],
    )
