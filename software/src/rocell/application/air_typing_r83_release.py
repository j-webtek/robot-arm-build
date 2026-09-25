"""Pinned offline review for the two-goal elbow grid candidate."""
from .air_typing_elbow_grid_recipe import SOURCE_GOALS,SOURCE_POSITIONS,TARGETS
from .product_ghost_export_review import _read


APP_SHA="5baaa670dd27e1e1f621fa5357f67eba765101b182be4513908e30192d4a00d6"
APP_BYTES=1205024
REVIEW="wizard-20260925T014502481083Z-1335fccc4b584efab236218e215f773d"


def review_release(root):
    report,digest=_read(root/"runs/wizard-exports",REVIEW,
                        "attachment-r83-elbow-grid-review.json")
    expected=dict(schema="rocell.r83_elbow_grid_review.v1",
        target="configured-diagnostic-candidate-r83",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=82,
        predecessor_sha256="0be3db4edf21396c881ee9eeee62f625bc99ebaf33bf96b35656c5dffd3a937c",
        selector="AIRG16",maximum_writes=16,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-elbow-grid/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key]!=value
           for key,value in expected.items()):
        raise ValueError("Pinned r83 review differs")
    return report,digest
