"""Pinned r76 one-move noncontact continuation candidate evidence."""
from .product_ghost_export_review import _read

APP_SHA = "874c89ca5af7bbb5e492cb5b3cf95ea47116c19fc65190151c638e47aeac0987"
APP_BYTES = 1202960
REVIEW = "wizard-20260924T224547887579Z-0aadc7abbb7c44d9a366db3945b7dc58"


def review_release(root):
    report, digest = _read(root / "runs/wizard-exports", REVIEW,
                           "attachment-r76-b-hover-review.json")
    expected = dict(schema="rocell.r76_b_hover_review.v1",
                    target="configured-diagnostic-candidate-r76", app_sha256=APP_SHA,
                    app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
                    predecessor_revision=75,
                    predecessor_sha256="da56d6d353918f2654f919914a48a8de4f3a7377ee718c5c122dac397bb92f2d",
                    selector="AIRB1", maximum_writes=1,
                    source_goals=[1941,2080,2034,2591,2236,2040,2047],
                    target_goals=[1941,2098,2016,2609,2201,2040,2047],
                    synchronized_servo_ids=[11,12,13,14,15,16,17],
                    requires_durable_export_receipt=True, retry_allowed=False,
                    settings_preserved_by_design=True, hardware_access=False,
                    firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key] != value
           for key, value in expected.items()):
        raise ValueError("Pinned r76 review differs")
    return report, digest
