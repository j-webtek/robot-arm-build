"""Closed v11 original role grammar; importing this module performs no I/O."""

import re

SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA = (
    "rocell.physical_camera_source_workflow_readback.v11"
)
MAX_USB_ABSENCE_EVENTS = 10
USB_ABSENCE_ROLE_BYTES = {
    "operation": 32 * 1024,
    "operator_event": 8 * 1024,
    "preparation": 16 * 1024,
    "boot_intent": 16 * 1024,
    "boot_review": 8 * 1024,
    "host_boot": 32 * 1024,
    "runtime_review": 8 * 1024,
    "execution": 128 * 1024,
    "phase_record": 16 * 1024,
}
USB_ABSENCE_STATES = (
    "PREPARATION_REQUESTED",
    "PREPARED",
    "BOOT_REVIEWED",
    "BOOT_REQUESTED",
    "BOOT_RETAINED",
    "BOOT_HELD",
    "BOOT_UNCERTAIN",
    "PRESENCE_REVIEW_REQUESTED",
    "PRESENCE_REVIEW_PREPARED",
    "RUNTIME_REVIEWED",
    "QUERY_REQUESTED",
    "RETAINED_BLOCKED",
    "INCOMPLETE",
    "ORIGINAL_CAMPAIGN_HELD",
)
_BOOT_EVENTS = frozenset(
    (
        "PREPARATION_REQUESTED",
        "BOOT_REVIEWED",
        "BOOT_REQUESTED",
        "BOOT_RETAINED",
        "BOOT_HELD",
        "BOOT_UNCERTAIN",
    )
)
_PHASE_EVENTS = _BOOT_EVENTS | {
    "PREPARED",
    "PRESENCE_REVIEW_REQUESTED",
    "PRESENCE_REVIEW_PREPARED",
    "RETAINED",
}
USB_ABSENCE_LABEL = re.compile(
    r"camera-usb-absence-(operation|operator-event|preparation|boot-intent|"
    r"boot-review|host-boot|runtime-review|execution|phase-record)-v1:"
    r"(usbphase-[0-9a-f]{32})"
)
USB_ABSENCE_EVENT = re.compile(
    r"CAMERA_USB_TRIAL_ABSENCE_("
    + "|".join(sorted(_PHASE_EVENTS))
    + r")_([0-9A-F]{32})"
)
USB_ABSENCE_PRESENCE_EVENT = re.compile(
    r"CAMERA_USB_PRESENCE_(RUNTIME_REVIEWED|QUERY_REQUESTED)_([0-9A-F]{32})"
)


def usb_absence_event(kind: str, phase_id: str, *, trial_id: str | None = None) -> str:
    if type(kind) is not str:
        raise ValueError("USB_ABSENCE_EVENT_INVALID")
    if (
        type(phase_id) is not str
        or re.fullmatch(r"usbphase-[0-9a-f]{32}", phase_id) is None
    ):
        raise ValueError("USB_ABSENCE_PHASE_ID_INVALID")
    if kind in _BOOT_EVENTS:
        from .physical_usb_absence_boot import usb_absence_boot_event

        return usb_absence_boot_event(kind, phase_id)
    if kind in _PHASE_EVENTS:
        return "CAMERA_USB_TRIAL_ABSENCE_" + kind + "_" + phase_id[9:].upper()
    if kind in {"RUNTIME_REVIEWED", "QUERY_REQUESTED"}:
        if (
            type(trial_id) is not str
            or re.fullmatch(r"usbtrial-[0-9a-f]{32}", trial_id) is None
        ):
            raise ValueError("USB_ABSENCE_TRIAL_ID_INVALID")
        return "CAMERA_USB_PRESENCE_" + kind + "_" + trial_id[9:].upper()
    raise ValueError("USB_ABSENCE_EVENT_INVALID")


def usb_absence_label(role: str, phase_id: str) -> str:
    if type(role) is not str or role not in USB_ABSENCE_ROLE_BYTES:
        raise ValueError("USB_ABSENCE_ROLE_INVALID")
    usb_absence_event("PREPARATION_REQUESTED", phase_id)
    if role in {"boot_intent", "boot_review", "host_boot"}:
        from .physical_usb_absence_boot import usb_absence_boot_label

        return usb_absence_boot_label(role, phase_id)
    return "camera-usb-absence-" + role.replace("_", "-") + "-v1:" + phase_id
