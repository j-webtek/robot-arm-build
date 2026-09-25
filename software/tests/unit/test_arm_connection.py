from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.arm import (
    ArmConnectionConfigurationError,
    load_arm_connection_profile,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def test_checked_in_connection_profile_is_explicitly_uncommissioned_and_nonopening() -> None:
    profile = load_arm_connection_profile(WORKSPACE)

    assert profile.model == "Waveshare RoArm-M3 Pro"
    assert profile.port is None
    assert profile.baudrate == 115200
    assert profile.commissioned is False
    assert profile.to_dict()["hardware_accessed"] is False
    with pytest.raises(ArmConnectionConfigurationError, match="not fully commissioned"):
        profile.require_commissioned_port("COM9")


def _qualified_profile(tmp_path: Path) -> Path:
    document = json.loads(
        (WORKSPACE / "software/config/arm_connection.json").read_text(encoding="utf-8")
    )
    document["port"] = "COM9"
    document["identity"] = {
        "controller_usb_identity": "USB\\VID_1234&PID_5678\\CONTROLLER-1",
        "arm_serial_number": "ROARM-M3-PRO-TEST-1",
        "firmware_revision": "commissioned-test-firmware",
        "state": "QUALIFIED",
    }
    path = tmp_path / "software/config/arm_connection.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_qualified_connection_requires_exact_commissioned_port(tmp_path: Path) -> None:
    path = _qualified_profile(tmp_path)
    profile = load_arm_connection_profile(tmp_path, path)

    assert profile.commissioned is True
    profile.require_commissioned_port("COM9")
    with pytest.raises(ArmConnectionConfigurationError, match="does not match"):
        profile.require_commissioned_port("COM10")


def test_connection_loader_rejects_auto_connect_and_blind_retry(tmp_path: Path) -> None:
    path = _qualified_profile(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["blind_retry"] = True
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ArmConnectionConfigurationError, match="Blind serial retry"):
        load_arm_connection_profile(tmp_path, path)


def test_connection_loader_rejects_ambiguous_json(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version": 1, "schema_version": 1}',
        encoding="utf-8",
    )
    with pytest.raises(ArmConnectionConfigurationError, match="Duplicate"):
        load_arm_connection_profile(tmp_path, duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"schema_version": NaN}', encoding="utf-8")
    with pytest.raises(ArmConnectionConfigurationError, match="Nonfinite"):
        load_arm_connection_profile(tmp_path, nonfinite)
