"""Pinned r71 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = '1ebaff62ea6348f072c35ce48005f67f5e2ff025c1c43de046ff23086bdcbf0b'
APP_BYTES = 1200640
REVIEW = 'wizard-20260924T181822158409Z-30e68aecefdc40658431d724744f39e9'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r71-p4-wrist-review.json')
    expected = dict(schema='rocell.r71_p4_wrist_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P4E', target_pose='P4', synchronized_servo_ids=[15],
        targets=[1980], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r71 release review differs')
    return report, digest
