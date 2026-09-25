"""Pinned offline review for the multi-joint hover candidate."""
from .air_typing_multi_hover_recipe import SOURCE_GOALS, SOURCE_POSITIONS, TARGETS
from .product_ghost_export_review import _read


APP_SHA = "d1e141a9b73d0b104ffb2ac1b07cae213c1321300a2251bd8cd3dcf0596f97cd"
APP_BYTES = 1204880
REVIEW = "wizard-20260925T020327021598Z-ae6a24035f51487d9215ea119ab91c99"


def review_release(root):
    report,digest = _read(root/"runs/wizard-exports", REVIEW,
                          "attachment-r84-multi-hover-review.json")
    expected = dict(schema="rocell.r84_multi_hover_review.v1",
        target="configured-diagnostic-candidate-r84",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=83,
        predecessor_sha256="5baaa670dd27e1e1f621fa5357f67eba765101b182be4513908e30192d4a00d6",
        selector="AIRM5",maximum_writes=5,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-multi-hover/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    if any(type(report.get(key)) is not type(value) or report[key] != value
           for key,value in expected.items()):
        raise ValueError("Pinned r84 review differs")
    return report,digest
