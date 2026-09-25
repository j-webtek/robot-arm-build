"""Pinned r69 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = '121a4c5b98c7fbb6e94ad448ac056341c284530416bf583c690850792b12a7a8'
APP_BYTES = 1200640
REVIEW = 'wizard-20260924T095406798973Z-101a20213e394687ac42c076bedb9b43'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r69-t4-wrist-review.json')
    expected = dict(schema='rocell.r69_t4_wrist_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='T4L', target_pose='T4', synchronized_servo_ids=[15],
        targets=[1915], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r69 release review differs')
    return report, digest
