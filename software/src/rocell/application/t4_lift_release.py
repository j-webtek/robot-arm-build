"""Pinned r68 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = '70ea81de94d578360a6afb68462b1e87b660b0c7a4bf1d5c644491ba7136dbad'
APP_BYTES = 1200720
REVIEW = 'wizard-20260924T001859367881Z-8f0f4bec18db4ba4b793e6c59f9ebab6'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r68-t4-lift-review.json')
    expected = dict(schema='rocell.r68_t4_lift_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P3', target_pose='T4L', synchronized_servo_ids=[12,13],
        targets=[2217,1897], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r68 release review differs')
    return report, digest
