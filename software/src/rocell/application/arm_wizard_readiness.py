"""Inert guidance derived from the wizard's current cached publications.

This projection never grants authority, selects a candidate or initiates work.
The action registry remains the authority for eligibility and input validation.
"""

from typing import Any


SCHEMA = "rocell.arm_wizard_readiness.v1"
STATES = frozenset(
    {
        "WAIT_FOR_OPERATION",
        "REVIEW_SERVICE_HOLD",
        "INSPECT_METADATA",
        "REVIEW_CANDIDATE",
        "INSPECT_NATIVE_METADATA",
        "REVIEW_METADATA_HOLD",
        "PHYSICAL_BACKEND_PENDING",
        "REHEARSAL_ONLY",
    }
)


def physical_connection_worklist() -> list[dict[str, str]]:
    """Outstanding implementation/review work, never an admission checklist.

    These entries deliberately have no user-settable PASS or approval field.
    Replace a pending entry only when its real producer/acceptance exists.
    Fresh dictionaries keep caller mutations out of future service projections.
    """
    return [
        {
            "id": "received_board",
            "owner": "Operator and hardware reviewer",
            "milestone": "A2",
            "required": "Retain the operator's received RoArm-M3 Pro association with the exact reviewed USB unit. Do not repeat model identification. Unknown board revision and firmware remain unknown; bridge metadata does not establish them.",
        },
        {
            "id": "power_and_startup",
            "owner": "Hardware reviewer and operator",
            "milestone": "A2/A4",
            "required": "Approved policy ROCELL-ARM-USB-PASSIVE-ENTRY-002 accepts vendor-design review plus current operator-reported USB-only setup for one passive test. Measured isolation remains unknown and reset on open remains possible. Do not reconnect external power for this check.",
        },
        {
            "id": "original_admission",
            "owner": "Software developer",
            "milestone": "A2/A3",
            "required": "Complete canonical original commissioning and release evidence beyond the separately gated diagnostic attempts. Rehearsal checksums and recovered diagnostics cannot authorize a new physical attempt.",
        },
        {
            "id": "qualified_lifecycle",
            "owner": "Software developer and hardware reviewer",
            "milestone": "A3",
            "required": "Keep each bounded physical diagnostic's identity, containment and cleanup requirements separate from general connection and motion qualification. A diagnostic result cannot release a persistent connection or motion executor.",
        },
        {
            "id": "explicit_passive_start",
            "owner": "Operator, after the preceding work",
            "milestone": "A4",
            "required": "Acquire fresh metadata and attest current setup, then explicitly start one supervised USB-only attempt. No outbound JSON, automatic retry, reset, home or torque command.",
        },
        {
            "id": "feedback_then_calibration",
            "owner": "Developer and operator",
            "milestone": "A5-A10",
            "required": "Complete canonical identity/power/startup and feedback acceptance; then installed static camera/board/tool calibration, noncontact motion and separate keyboard/phone contact acceptance.",
        },
    ]


def arm_wizard_readiness(view: dict[str, Any]) -> dict[str, Any]:
    """Produce guidance from a service-owned view, without any I/O."""
    inventory = (
        "inventory_devices"
        if view["mode"] == "physical"
        else "rehearse_device_inventory"
    )
    native_action = (
        "inspect_native_arm_metadata"
        if view["mode"] == "physical"
        else "rehearse_native_arm_metadata"
    )
    native = view["native_arm_metadata"]
    selection = view["device_selection"]
    report = native.get("report")
    if view["status"] == "DIAGNOSTIC_RUNNING":
        state, action, message = (
            "WAIT_FOR_OPERATION",
            None,
            "Wait for the current operation's terminal result. Do not start another device test.",
        )
    elif view["status"] != "READY_FOR_DIAGNOSTICS":
        state, action, message = (
            "REVIEW_SERVICE_HOLD",
            "export_logs",
            "Review the service hold and export diagnostics. Restart must not replay a device action.",
        )
    elif selection.get("status") in ("NO_INVENTORY", "INVALIDATED"):
        state, action, message = (
            "INSPECT_METADATA",
            inventory,
            "Inspect attached OS metadata explicitly. This does not open a serial port or verify actuator power state; follow the current metadata form's requirements.",
        )
    elif not selection["devices"]["SERIAL"].get("review"):
        state, action, message = (
            "REVIEW_CANDIDATE",
            "review_arm_candidate",
            "Review one exact SERIAL candidate. Do not select the first COM port or assume a bridge serial is the chassis serial.",
        )
    elif native.get("status") != "CURRENT" or report is None:
        state, action, message = (
            "INSPECT_NATIVE_METADATA",
            native_action,
            "Inspect fresh native metadata for the reviewed candidate. Historical results cannot establish current identity.",
        )
    elif report.get("status") != "METADATA_CORRELATED":
        state, action, message = (
            "REVIEW_METADATA_HOLD",
            "export_logs",
            "The retained native mapping is held. Export and review its blockers before a new explicit inspection.",
        )
    elif view["mode"] == "rehearsal":
        state, action, message = (
            "REHEARSAL_ONLY",
            "export_logs",
            "Synthetic metadata matched; no received hardware was observed. Export the rehearsal result without promoting it to physical evidence.",
        )
    else:
        state, action, message = (
            "PHYSICAL_BACKEND_PENDING",
            "export_logs",
            "Metadata matched; general Connect and motion remain held. Passive observation, telemetry and one-shot feedback are separately gated diagnostics. Inspect their current forms and export existing evidence; no physical operation is started or authorized by this guidance.",
        )
    definition = next(
        (item for item in view["actions"] if item["action_id"] == action), None
    )
    return {
        "schema": SCHEMA,
        "state": state,
        "message": message,
        "next_action_id": action,
        "action_enabled": definition is not None and definition.get("enabled") is True,
        "blocked_reasons": (
            list(definition.get("blocked_reasons", [])) if definition else []
        ),
        "export_directory": view["exports"]["directory"],
        "physical_connection_worklist": physical_connection_worklist(),
        "startup_warning": "Vendor documentation describes automatic joint motion on power-up. USB metadata, a rehearsal PASS or a closed serial port does not authorize power-up or initialization.",
        "startup_reference": "https://docs.waveshare.net/RoArm-M3/Introduction/",
        "connected": False,
        "physical_authority": False,
    }
