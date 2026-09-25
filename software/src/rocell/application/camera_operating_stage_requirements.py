"""Assign diagnostic holds to stage owners without assessing or passing a stage.

The operating report intentionally spans more than stage 5. This projection
prevents a later freshness/optics requirement being confused with a mode-control
prerequisite. It never removes a hold, reads hardware or changes stage policy.
"""

from typing import Any

from .camera_operating_evidence_preflight import CHECK_IDS, OWNER_OBLIGATIONS

SCHEMA = "rocell.camera_operating_stage_requirements.v1"
RETENTION_HOLD = "PROPOSAL_AND_ASSESSMENT_ORIGINAL_STAGE_RETENTION_NOT_IMPLEMENTED"
MODE_STAGE = "camera_mode_controls"
_LATER = {
    "FRAME_FRESHNESS_NOT_ASSESSED": ("camera_frame_freshness",),
    "INSTALLED_OPTICS_AND_CALIBRATION_DEFERRED": (
        "optics_intrinsics",
        "static_registration",
    ),
}
_HOLD_ORDER = (*OWNER_OBLIGATIONS, RETENTION_HOLD)


class CameraStageRequirementsError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_STAGE_REQUIREMENTS_INVALID")


def _selection(value: Any, allowed: tuple[str, ...]) -> set[str]:
    # Exact strings and a closed finite roster; no best-effort filtering of an
    # unknown hold that could make a checklist look more complete than it is.
    if (
        type(value) not in (list, tuple)
        or len(value) > len(allowed)
        or any(type(item) is not str or item not in allowed for item in value)
        or len(set(value)) != len(value)
    ):
        raise CameraStageRequirementsError()
    return set(value)


def project_operating_requirements(
    unresolved_checks: list[str] | tuple[str, ...],
    failed_metadata_checks: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Deterministic presentation data, not a new acceptance state machine.

    Even empty lists do not prove a stage passed. The original stage owner must
    authenticate its complete prerequisites and a separately retained review.
    One combined optics hold has two owners; it remains one diagnostic hold.
    """
    holds = _selection(unresolved_checks, _HOLD_ORDER)
    failed = _selection(failed_metadata_checks, CHECK_IDS)
    return dict(
        schema=SCHEMA,
        scope="OWNERSHIP_PROJECTION_NOT_STAGE_ACCEPTANCE",
        metadata_check_owner=MODE_STAGE,
        failed_metadata_checks=[key for key in CHECK_IDS if key in failed],
        requirements=[
            dict(
                id=key,
                owner_stages=list(_LATER.get(key, (MODE_STAGE,))),
                scope="LATER_STAGE" if key in _LATER else "MODE_CONTROL_STAGE",
            )
            for key in _HOLD_ORDER
            if key in holds
        ],
        stage_passed=False,
        original_store_authenticated=False,
        physical_authority=False,
        hardware_qualified=False,
    )
