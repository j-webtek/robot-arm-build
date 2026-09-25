"""Pinned offline review for the isolated-elbow eight-leg candidate."""
from .air_typing_elbow_direction_recipe import SOURCE_GOALS, SOURCE_POSITIONS, TARGETS
from .product_ghost_export_review import _read


APP_SHA="2580a872ce612c331cb02dce15be9b34f75f1e19ac4bc6043072e438e8b948d1"
APP_BYTES=1204944
REVIEW="wizard-20260925T010836375660Z-6b85c8a6aeed475a95f252a1e1f39ed7"


def review_release(root):
    report,digest=_read(root/"runs/wizard-exports",REVIEW,
                        "attachment-r81-elbow-direction-review.json")
    expected=dict(schema="rocell.r81_elbow_direction_review.v1",
        target="configured-diagnostic-candidate-r81",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=79,
        predecessor_sha256="f82f1f87e6e9917dfdf2e9c60c30aaedf18025bdbd3b9777600b46a1458f7e82",
        selector="AIRE8",maximum_writes=8,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-elbow-direction/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key]!=value
           for key,value in expected.items()):
        raise ValueError("Pinned r81 review differs")
    return report,digest
