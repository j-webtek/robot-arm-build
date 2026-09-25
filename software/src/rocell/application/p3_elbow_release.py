"""Pinned r66 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = '3dd1401b58cec43fb3c5c27c8d2072987487964d8a4609552d38cf8bf7e73812'
APP_BYTES = 1200656
REVIEW = 'wizard-20260923T212529489183Z-9d668b37f0c44de79284a1566a79b076'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r66-p3-elbow-review.json')
    expected = dict(schema='rocell.r66_p3_elbow_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P2', target_pose='P3E', synchronized_servo_ids=[14],
        targets=[2777], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r66 release review differs')
    return report, digest
