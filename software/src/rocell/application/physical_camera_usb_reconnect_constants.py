"""Closed v12 reconnect suffix limits; no acquisition or admission imports."""

import re

USB_RECONNECT_ROLE_BYTES = {
    "operator_event": 8 * 1024,
    "enrollment": 768 * 1024,
    "preparation": 128 * 1024,
    "operation": 80 * 1024,
    "policy_review": 8 * 1024,
    "runtime_review": 8 * 1024,
    "identity": 16 * 1024,
    "boot_request": 16 * 1024,
    "host_boot": 32 * 1024,
    "execution": 128 * 1024,
    "phase_record": 32 * 1024,
}
USB_RECONNECT_EVENTS = (
    "PREPARATION_REQUESTED",
    "PREPARED",
    "REVIEWED",
    "BOOT_REQUESTED",
    "BOOT_RETAINED",
    "BOOT_HELD",
    "BOOT_UNCERTAIN",
    "QUERY_REQUESTED",
    "RETAINED",
)

SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA = (
    "rocell.physical_camera_source_workflow_readback.v12"
)
MAX_USB_RECONNECT_EVENTS = 7
USB_RECONNECT_STATES = (
    "PREPARATION_REQUESTED",
    "PREPARED",
    "REVIEWED",
    "BOOT_REQUESTED",
    "BOOT_RETAINED",
    "BOOT_HELD",
    "BOOT_UNCERTAIN",
    "QUERY_REQUESTED",
    "RETAINED_BLOCKED",
    "INCOMPLETE",
    "ORIGINAL_CAMPAIGN_HELD",
)
USB_RECONNECT_LABEL = re.compile(
    r"camera-usb-trial-reconnect-(operator-event|enrollment|preparation|operation|policy-review|"
    r"runtime-review|identity|boot-request|host-boot|execution|phase-record)-v1:"
    r"(usbphase-[0-9a-f]{32})"
)
USB_RECONNECT_EVENT = re.compile(
    r"CAMERA_USB_TRIAL_RECONNECT_("
    + "|".join(USB_RECONNECT_EVENTS)
    + r")_([0-9A-F]{32})"
)


def usb_reconnect_event(kind: str, phase_id: str) -> str:
    if (
        type(kind) is not str
        or kind not in USB_RECONNECT_EVENTS
        or type(phase_id) is not str
        or re.fullmatch(r"usbphase-[0-9a-f]{32}", phase_id) is None
    ):
        raise ValueError("USB_RECONNECT_PREPARATION_INVALID")
    return "CAMERA_USB_TRIAL_RECONNECT_" + kind + "_" + phase_id[9:].upper()


def usb_reconnect_label(role: str, phase_id: str) -> str:
    if type(role) is not str or role not in USB_RECONNECT_ROLE_BYTES:
        raise ValueError("USB_RECONNECT_PREPARATION_INVALID")
    usb_reconnect_event("PREPARATION_REQUESTED", phase_id)
    return "camera-usb-trial-reconnect-" + role.replace("_", "-") + "-v1:" + phase_id
