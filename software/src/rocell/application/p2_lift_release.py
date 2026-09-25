"""Pinned r64 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = 'a8480d215bdfce5768dd0fcd6d81c97bab9cae9c6b2d33ea0894eefe28275ba8'
APP_BYTES = 1200720
REVIEW = 'wizard-20260923T094445930836Z-6bdb8da4d67b4bb495de827d4c5c8511'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r64-p2-lift-review.json')
    expected = dict(schema='rocell.r64_p2_lift_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='P1', target_pose='P2L', synchronized_servo_ids=[12,13],
        targets=[2283,1831], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r64 release review differs')
    return report, digest
