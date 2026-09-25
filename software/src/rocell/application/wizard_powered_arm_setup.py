"""Retain operator-reported powered startup, without granting serial authority.

This is a prebuild engineering observation, not canonical power-stage acceptance
or an electrical measurement. Firmware identity remains unknown. Consumers must
bind the original receipt and separately qualify any feedback operation.
"""

import hashlib
from pathlib import Path
import re

from .arm_bench_qualification_contract import _canonical
from .physical_onboarding_durability import (
    PublicationMode,
    publish_bytes,
    read_bounded_regular_file,
)

ACTION = "record_powered_arm_startup"


def record_startup(
    *,
    root,
    session_id,
    operation_id,
    source_sha256,
    operator_id,
    adapter_on,
    usb_connected,
    secured_and_clear,
    stationary,
    startup_motion,
    now_monotonic_ns
):
    """Record only explicitly reported current facts; never energize hardware."""
    for value, pattern in (
        (session_id, r"wizard-[a-f0-9]{32}"),
        (operation_id, r"operation-[a-f0-9]{32}"),
        (source_sha256, r"[a-f0-9]{64}"),
        (operator_id, r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"),
    ):
        if type(value) is not str or re.fullmatch(pattern, value) is None:
            raise ValueError("Exact service context and portable operator ID required")
    if any(
        value is not True
        for value in (adapter_on, usb_connected, secured_and_clear, stationary)
    ):
        raise ValueError(
            "Explicit powered, connected, secured/clear and stationary reports required"
        )
    if type(startup_motion) is not str or startup_motion not in {
        "observed",
        "not_observed",
        "unknown",
    }:
        raise ValueError("Closed startup observation required")
    if type(now_monotonic_ns) is not int or not 0 < now_monotonic_ns < 2**63:
        raise ValueError("Live recording timestamp required")
    original = {
        "schema": "rocell.powered_arm_startup_original.v1",
        "session_id": session_id,
        "operation_id": operation_id,
        "source_sha256": source_sha256,
        "recorded_monotonic_ns": now_monotonic_ns,
        "operator_id": operator_id,
        "reported": {
            "external_adapter_on": True,
            "usb_connected": True,
            "secured_and_clear": True,
            "stationary": True,
            "startup_motion": startup_motion,
        },
        "evidence_kind": "OPERATOR_REPORT_NOT_SENSOR_MEASUREMENT",
        "supply_voltage_measurement": None,
        "installed_firmware_identity": "UNKNOWN",
        "controller_identity_verified": False,
        "canonical_power_stage_accepted": False,
        "usb_only_policy_applicable": False,
        "feedback_authorized": False,
        "motion_authorized": False,
        "physical_authority": False,
    }
    raw = _canonical(original)
    path = publish_bytes(
        Path(root),
        operation_id + "-powered-startup-original.json",
        raw,
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=32768,
    )
    if read_bounded_regular_file(path, maximum_bytes=32768) != raw:
        raise ValueError("Powered startup original readback mismatch")
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": ACTION,
        "status": "SUCCEEDED",
        "steps": [
            {
                "name": "powered_arm_startup_original",
                "exit_code": 0,
                "report": {
                    "status": "POWERED_STARTUP_RECORDED_NOT_AUTHORIZED",
                    "path": str(path),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "recorded_monotonic_ns": now_monotonic_ns,
                    "usb_only_policy_applicable": False,
                    "feedback_authorized": False,
                    "physical_authority": False,
                },
            }
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }
