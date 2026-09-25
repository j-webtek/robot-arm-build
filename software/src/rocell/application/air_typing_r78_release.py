"""Pinned reviewed r78 four-leg A-side noncontact candidate evidence."""
from .product_ghost_export_review import _read


APP_SHA="3b9989e03cd64690e831049c4e19ff38d6c10ab6e2c6c22f3ad1d7e61e1f3aaa"
APP_BYTES=1204848
REVIEW="wizard-20260924T234109427898Z-cee1f774526e4a7f95a8bfa8000af08c"


def review_release(root):
    report,digest=_read(root/"runs/wizard-exports",REVIEW,"attachment-r78-air-typing-review.json")
    expected=dict(schema="rocell.r78_air_typing_review.v1",
        target="configured-diagnostic-candidate-r78",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=77,
        predecessor_sha256="7a2059d76243b37e9b443c822093ef597611f136f5497a055f01278c3bcda496",
        selector="AIR4",maximum_writes=4,
        source_goals=[1994,2076,2038,2598,2234,2040,2047],
        source_positions=[1987,2082,2031,2600,2235,2041,2047],
        targets=[[2047,2075,2039,2600,2233,2040,2047],
                 [2047,2093,2021,2618,2197,2040,2047],
                 [2047,2105,2009,2630,2173,2040,2047],
                 [2047,2075,2039,2600,2233,2040,2047]],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-type-last/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key]!=value
           for key,value in expected.items()):
        raise ValueError("Pinned r78 review differs")
    return report,digest
