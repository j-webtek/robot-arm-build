"""Pinned r67 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = '92623957b1a2bf9f11bafce8a3a8db6788121232d26cb6fed1406c0ecb002c05'
APP_BYTES = 1200640
REVIEW = 'wizard-20260923T232955852188Z-fb654061ff6b4aefa4d5a71b2276c7c5'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r67-p3-wrist-review.json')
    expected = dict(schema='rocell.r67_p3_wrist_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P3E', target_pose='P3', synchronized_servo_ids=[15],
        targets=[1850], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r67 release review differs')
    return report, digest
