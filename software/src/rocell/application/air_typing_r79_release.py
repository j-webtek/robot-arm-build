"""Pinned offline review for the fixed six-leg noncontact repeat candidate."""
from .product_ghost_export_review import _read


APP_SHA="f82f1f87e6e9917dfdf2e9c60c30aaedf18025bdbd3b9777600b46a1458f7e82"
APP_BYTES=1204896
REVIEW="wizard-20260925T004555953367Z-a2eb05a722184082a6740e964b7365f7"


def review_release(root):
    report,digest=_read(root/"runs/wizard-exports",REVIEW,
                        "attachment-r79-air-typing-repeat-review.json")
    expected=dict(schema="rocell.r79_air_typing_repeat_review.v1",
        target="configured-diagnostic-candidate-r79",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=78,
        predecessor_sha256="3b9989e03cd64690e831049c4e19ff38d6c10ab6e2c6c22f3ad1d7e61e1f3aaa",
        selector="AIR6",maximum_writes=6,
        source_goals=[2047,2075,2039,2600,2233,2040,2047],
        source_positions=[2041,2081,2033,2609,2233,2041,2047],
        targets=[[2047,2093,2021,2618,2197,2040,2047],
                 [2047,2105,2009,2630,2173,2040,2047],
                 [2047,2075,2039,2600,2233,2040,2047],
                 [2047,2093,2021,2618,2197,2040,2047],
                 [2047,2105,2009,2630,2173,2040,2047],
                 [2047,2075,2039,2600,2233,2040,2047]],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-type-repeat/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key]!=value
           for key,value in expected.items()):
        raise ValueError("Pinned r79 review differs")
    return report,digest
