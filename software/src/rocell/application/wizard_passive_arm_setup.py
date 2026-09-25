"""Service-owned setup original for the approved USB-only bench lane.

This records operator reports and exact existing metadata, not electrical
measurements. It opens only regular workspace files, never a device endpoint.
The future physical Start must bind this original and recheck setup freshness.
"""

import base64
import hashlib
from pathlib import Path
import re

from . import wizard_native_arm_metadata as metadata
from .arm_bench_qualification_contract import _canonical
from .physical_onboarding_durability import (
    PublicationMode,
    publish_bytes,
    read_bounded_regular_file,
    contained_path,
)

ACTION = "record_passive_arm_setup"
MAX_BYTES = 1024 * 1024


def record_setup(
    *,
    workspace,
    root,
    session_id,
    operation_id,
    source_sha256,
    generic_review,
    native_report,
    operator_id,
    power_disconnected,
    secured_and_clear,
    now_monotonic_ns
):
    if power_disconnected is not True or secured_and_clear is not True:
        raise ValueError("Explicit current USB-only and secured/clear reports required")
    if (
        type(operator_id) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", operator_id) is None
    ):
        raise ValueError("Portable operator ID required")
    if (
        type(operation_id) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", operation_id) is None
    ):
        raise ValueError("Service-owned operation ID required")
    if type(now_monotonic_ns) is not int or not 0 < now_monotonic_ns < 2**63:
        raise ValueError("Live launch clock required")
    original = metadata._owned(native_report, metadata.MAX_REPORT_BYTES)
    # Rebuild using the FULL service-retained generic original, not a UI summary
    # or caller-provided PASS bit, to detect substituted metadata/review bytes.
    rebuilt = metadata.correlate_native_arm_metadata(
        original["snapshot"],
        generic_review,
        mode="physical",
        session_id=session_id,
        source_sha256=source_sha256,
        operation_id=original["binding"]["operation_id"],
    )
    if (
        _canonical(rebuilt) != _canonical(original)
        or rebuilt["status"] != "METADATA_CORRELATED"
    ):
        raise ValueError("Current exact physical metadata original required")
    documents = {}
    for name in (
        "ARM_USB_ONLY_ENTRY_POLICY_PROPOSAL.md",
        "ARM_USB_ELECTRICAL_DESIGN_REVIEW.md",
    ):
        path = contained_path(
            Path(workspace), "software/docs/" + name, label="passive policy document"
        )
        documents[name] = read_bounded_regular_file(path, maximum_bytes=32768)
    policy = documents["ARM_USB_ONLY_ENTRY_POLICY_PROPOSAL.md"]
    if (
        b"ROCELL-ARM-USB-PASSIVE-ENTRY-002" not in policy
        or b"USER APPROVED; IMPLEMENTATION IN PROGRESS; NO PHYSICAL RELEASE"
        not in policy
    ):
        raise ValueError("Approved versioned USB-only entry policy required")
    record = {
        "schema": "rocell.wizard_passive_arm_setup_original.v1",
        "session_id": session_id,
        "operation_id": operation_id,
        "source_sha256": source_sha256,
        "recorded_monotonic_ns": now_monotonic_ns,
        "operator_report": {
            "operator_id": operator_id,
            "external_adapter_disconnected": True,
            "secured_and_clear": True,
            "model_association": "RoArm-M3 Pro",
            "model_association_basis": "PREVIOUS_OPERATOR_REPORT_NOT_NEW_INSPECTION",
        },
        "measured_isolation": "NOT_ESTABLISHED",
        "reset_on_open": "POSSIBLE",
        "generic_review": generic_review,
        "native_report": original,
        "documents": {
            name: {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "base64": base64.b64encode(raw).decode("ascii"),
            }
            for name, raw in documents.items()
        },
        "connected": False,
        "physical_authority": False,
        "replay_allowed": False,
    }
    raw = _canonical(record)
    path = publish_bytes(
        Path(root),
        operation_id + "-passive-setup-original.json",
        raw,
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_BYTES,
    )
    if read_bounded_regular_file(path, maximum_bytes=MAX_BYTES) != raw:
        raise ValueError("Setup original readback mismatch")
    # The UI gets a compact receipt. Original bytes remain in the durable file
    # and are included explicitly as a pinned export attachment by the service.
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": ACTION,
        "status": "SUCCEEDED",
        "steps": [
            {
                "name": "passive_arm_setup_original",
                "exit_code": 0,
                "report": {
                    "status": "SETUP_RECORDED_NOT_CONNECTED",
                    "path": str(path),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "recorded_monotonic_ns": now_monotonic_ns,
                    "native_report_sha256": original["report_sha256"],
                    "measured_isolation": "NOT_ESTABLISHED",
                    "physical_authority": False,
                    "connected": False,
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
