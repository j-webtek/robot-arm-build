"""Pinned r75 noncontact fixed campaign candidate evidence."""
from .product_ghost_export_review import _read

APP_SHA = "da56d6d353918f2654f919914a48a8de4f3a7377ee718c5c122dac397bb92f2d"
APP_BYTES = 1203040
REVIEW = "wizard-20260924T202600940966Z-b8ea449443234383a8ef4eef33c3562a"


def review_release(root):
    report, digest = _read(root / "runs/wizard-exports", REVIEW,
                           "attachment-r75-air-typing-review.json")
    expected = dict(schema="rocell.r75_air_typing_review.v1",
                    target="configured-diagnostic-candidate-r75", app_sha256=APP_SHA,
                    app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
                    predecessor_revision=74,
                    predecessor_sha256="1f2c6822f428b9dd9fdf2eb17444d3f89f5d7243a7aad89edae4acda0b721bc5",
                    selector="AIR17", maximum_writes=17,
                    synchronized_servo_ids=[11, 12, 13, 14, 15, 16, 17],
                    requires_durable_export_receipt=True, retry_allowed=False,
                    settings_preserved_by_design=True, hardware_access=False,
                    firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key] != value
           for key, value in expected.items()):
        raise ValueError("Pinned r75 review differs")
    return report, digest
