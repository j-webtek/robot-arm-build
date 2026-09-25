"""Pinned r72 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = 'e8d27dc8085d4e21ae6450be4eff0c41eb46a39962ba2d47baf084b01ee3afe9'
APP_BYTES = 1202960
REVIEW = 'wizard-20260924T184141008989Z-79063803346e4c808f31072252a55339'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r72-p4-repeat-review.json')
    expected = dict(schema='rocell.r72_p4_repeat_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P4', target_pose='P4R12', synchronized_servo_ids=[15],
        targets=[1915,1947,1980,1947,1915,1980]*2, maximum_writes=12, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r72 release review differs')
    return report, digest
