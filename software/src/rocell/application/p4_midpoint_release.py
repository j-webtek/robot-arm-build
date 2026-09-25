"""Pinned r74 comparison candidate evidence for installer and startup review."""
from .product_ghost_export_review import _read

APP_SHA='1f2c6822f428b9dd9fdf2eb17444d3f89f5d7243a7aad89edae4acda0b721bc5'
APP_BYTES=1203024
REVIEW='wizard-20260924T193948839702Z-0bdf328537544aac9229484e9cdb57f4'
TARGETS=[1944,1980,1945,1980,1945,1980,1944,1980,
         1945,1980,1944,1980,1944,1980,1945,1980]


def review_release(root):
    report,digest=_read(root/'runs/wizard-exports',REVIEW,'attachment-r74-p4-midpoint-review.json')
    expected=dict(schema='rocell.r74_p4_midpoint_review.v1',app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=73,source_pose='P4',target_pose='P4M16',
        synchronized_servo_ids=[15],targets=TARGETS,maximum_writes=16,
        retry_allowed=False,hardware_access=False,firmware_uploaded=False,
        deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k]!=v for k,v in expected.items()):
        raise ValueError('Pinned r74 review differs')
    return report,digest
