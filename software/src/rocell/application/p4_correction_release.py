"""Pinned r73 comparison candidate evidence for installer and startup review."""
from .product_ghost_export_review import _read

APP_SHA='ec2b9f63e6c2157185584f596a7a04551c995bed9de811d9bcd94b7bc3c2373a'
APP_BYTES=1203040
REVIEW='wizard-20260924T192053184753Z-50d3d6002a3a4585aeb61fe82f63621c'
TARGETS=[1947,1980,1944,1980,1944,1980,1947,1980,
         1944,1980,1947,1980,1947,1980,1944,1980]


def review_release(root):
    report,digest=_read(root/'runs/wizard-exports',REVIEW,'attachment-r73-p4-correction-review.json')
    expected=dict(schema='rocell.r73_p4_correction_review.v1',app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=72,source_pose='P4',target_pose='P4C16',
        synchronized_servo_ids=[15],targets=TARGETS,maximum_writes=16,
        retry_allowed=False,hardware_access=False,firmware_uploaded=False,
        deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k]!=v for k,v in expected.items()):
        raise ValueError('Pinned r73 review differs')
    return report,digest
