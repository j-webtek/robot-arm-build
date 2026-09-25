"""Pinned r65 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = '7ed18ca356194e2b226936c5146e46ec079c326d8140667a07a49923b935b4de'
APP_BYTES = 1200624
REVIEW = 'wizard-20260923T195347216230Z-1526901a57e64f2b8ef1fa0d1083d0a0'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r65-p2-wrist-review.json')
    expected = dict(schema='rocell.r65_p2_wrist_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P2L', target_pose='P2', synchronized_servo_ids=[15],
        targets=[1785], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r65 release review differs')
    return report, digest
