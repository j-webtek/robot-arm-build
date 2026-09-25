"""Pinned offline review for the nearby held-out elbow target candidate."""
from .air_typing_elbow_shift_recipe import SOURCE_GOALS,SOURCE_POSITIONS,TARGETS
from .product_ghost_export_review import _read


APP_SHA="0be3db4edf21396c881ee9eeee62f625bc99ebaf33bf96b35656c5dffd3a937c"
APP_BYTES=1204912
REVIEW="wizard-20260925T012833866287Z-4e003aae4ab14f4cb3af4f750979536a"


def review_release(root):
    report,digest=_read(root/"runs/wizard-exports",REVIEW,
                        "attachment-r82-elbow-shift-review.json")
    expected=dict(schema="rocell.r82_elbow_shift_review.v1",
        target="configured-diagnostic-candidate-r82",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=81,
        predecessor_sha256="2580a872ce612c331cb02dce15be9b34f75f1e19ac4bc6043072e438e8b948d1",
        selector="AIRH8",maximum_writes=8,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-elbow-shift/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key]!=value
           for key,value in expected.items()):
        raise ValueError("Pinned r82 review differs")
    return report,digest
