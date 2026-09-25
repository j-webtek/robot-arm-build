"""Pinned r70 release evidence shared by installer and startup validation."""
from .product_ghost_export_review import _read

APP_SHA = 'd4e860492602492477e67e58436a681a252adc2b9eeb934315abb05b98113134'
APP_BYTES = 1200656
REVIEW = 'wizard-20260924T100747862852Z-c7418427c73b49d88f13873f383a6169'


def review_release(root):
    report, digest = _read(root/'runs/wizard-exports', REVIEW, 'attachment-r70-p4-elbow-review.json')
    expected = dict(schema='rocell.r70_p4_elbow_review.v1', app_sha256=APP_SHA,
        app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
        source_pose='T4', target_pose='P4E', synchronized_servo_ids=[14],
        targets=[2711], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    if any(type(report.get(k)) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Pinned r70 release review differs')
    return report, digest
