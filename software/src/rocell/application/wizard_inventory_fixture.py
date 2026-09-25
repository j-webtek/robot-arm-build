"""Closed metadata fixtures for the wizard's real candidate-review contracts.

These records exercise the existing OS-output parsers, not OS enumeration.
Names, USB IDs, serials and timestamps are deliberately synthetic. No fixture
is a received-unit profile, endpoint binding or hardware activation capability.
"""

from __future__ import annotations

from dataclasses import replace
import json

from rocell.application.physical_device_inventory import (
    ArgvCommandResult,
    RawSerialPortObservation,
    compose_physical_device_inventory_report,
    inventory_serial_ports_from_provider,
    inventory_windows_pnp_cameras,
)


class _FixturePnp:
    def __init__(self, records: list[dict], *, failed: bool) -> None:
        self._records, self._failed = records, failed

    def run(self, argv: tuple[str, ...], *, timeout_seconds: int) -> ArgvCommandResult:
        # Intentionally never execute argv; only the canonical parser is used.
        return ArgvCommandResult(
            returncode=1 if self._failed else 0,
            stdout=json.dumps(self._records).encode("utf-8"),
            stderr=b"",
        )


class _FixtureSerial:
    def __init__(self, observations: tuple[RawSerialPortObservation, ...]) -> None:
        self._observations = observations

    def enumerate_serial_ports(self) -> tuple[RawSerialPortObservation, ...]:
        return self._observations


def rehearsal_device_inventory(scenario: str) -> dict:
    """Materialize one fixed bounded scenario without importing a live provider."""
    if scenario not in {
        "nominal",
        "missing-identity",
        "duplicate-identity",
        "partial-inventory",
    }:
        raise ValueError("Unknown metadata rehearsal scenario")
    camera = {
        "Status": "OK",
        "Class": "Camera",
        "FriendlyName": "SYNTHETIC camera candidate - not received B0477",
        "InstanceId": "USB\\VID_FFFE&PID_0001\\SYNTHETIC-CAMERA-A",
        "Present": True,
        "Manufacturer": "SYNTHETIC",
        "Product": "SYNTHETIC metadata fixture",
        "Service": "usbvideo",
        "SerialNumber": "SYNTHETIC-CAMERA-A",
        "ContainerId": "{11111111-2222-3333-4444-555555555555}",
        "HardwareIds": ["USB\\VID_FFFE&PID_0001"],
    }
    arm = RawSerialPortObservation(
        port_name="COM91",
        description="SYNTHETIC serial candidate - not received RoArm",
        hwid="USB VID:PID=FFFE:0002 SER=SYNTHETIC-ARM-A",
        vid="fffe",
        pid="0002",
        serial_number="SYNTHETIC-ARM-A",
        location="SYNTHETIC-PORT-A",
        manufacturer="SYNTHETIC",
        product="SYNTHETIC serial fixture",
        interface="SYNTHETIC interface",
    )
    cameras = [camera]
    arms: tuple[RawSerialPortObservation, ...] = (arm,)
    if scenario == "missing-identity":
        camera["SerialNumber"] = None
        arm = replace(arm, serial_number=None, hwid="USB VID:PID=FFFE:0002")
        arms = (arm,)
    elif scenario == "duplicate-identity":
        cameras.append(
            {**camera, "InstanceId": "USB\\VID_FFFE&PID_0001\\SYNTHETIC-DUPLICATE"}
        )
        arms = (arm, replace(arm, port_name="COM92", location="SYNTHETIC-PORT-B"))
    return compose_physical_device_inventory_report(
        platform_system="Windows",
        captured_at_unix_ns=1,  # Fixture time, not a host/device observation.
        camera_inventory=inventory_windows_pnp_cameras(
            _FixturePnp(cameras, failed=scenario == "partial-inventory")
        ),
        serial_inventory=inventory_serial_ports_from_provider(_FixtureSerial(arms)),
    ).to_dict()
