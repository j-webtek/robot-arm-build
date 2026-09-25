"""V14 file-only suffix constants; names do not grant stage authority.

The original reader must independently authenticate the full unchanged v13
predecessor before recognizing this suffix. No extra device campaign, permit,
native query or camera/arm release is introduced by these constants.
"""

import re


SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA = (
    "rocell.physical_camera_source_workflow_readback.v14"
)
USB_COMPLETE_ROLE_BYTES = {
    "series": 16 * 1024,
    "assessment": 32 * 1024,
    "review": 8 * 1024,
}
MAX_USB_COMPLETE_EVENTS = 3
USB_COMPLETE_EVENTS = (
    "ASSESSMENT_REQUESTED",
    "ASSESSMENT_RETAINED",
    "REVIEWED",
)
USB_COMPLETE_STATES = (
    "ASSESSMENT_REQUESTED",
    "REVIEW_PENDING",
    "REVIEWED_PASS",
    "REVIEWED_BLOCKED",
    "INCOMPLETE",
)
USB_COMPLETE_LABEL = re.compile(
    r"camera-usb-complete-(series|assessment|review)-v1:(usbseries-[0-9a-f]{32})"
)
USB_COMPLETE_EVENT = re.compile(
    r"CAMERA_USB_COMPLETE_(" + "|".join(USB_COMPLETE_EVENTS) + r")_([0-9A-F]{32})"
)
_SERIES_ID = re.compile(r"usbseries-[0-9a-f]{32}\Z")
_SERIES_PREFIX = "usbseries-"


def usb_complete_event(kind: str, series_id: str) -> str:
    """Format an exact closed event; callers still validate original transitions."""
    if (
        type(kind) is not str
        or kind not in USB_COMPLETE_EVENTS
        or type(series_id) is not str
        or _SERIES_ID.fullmatch(series_id) is None
    ):
        raise ValueError("USB_COMPLETE_SUFFIX_INVALID")
    # This prefix is ten characters, unlike the nine-character usbphase- ID.
    # Slice by its declared length instead of copying an earlier phase offset.
    return (
        "CAMERA_USB_COMPLETE_" + kind + "_" + series_id[len(_SERIES_PREFIX) :].upper()
    )


def usb_complete_label(role: str, series_id: str) -> str:
    if type(role) is not str or role not in USB_COMPLETE_ROLE_BYTES:
        raise ValueError("USB_COMPLETE_SUFFIX_INVALID")
    usb_complete_event("ASSESSMENT_REQUESTED", series_id)
    return "camera-usb-complete-" + role + "-v1:" + series_id
