"""Pure B0477 review guidance, never original evidence or operating approval.

The reference is the workspace commissioning target, not a declaration that the
selected USB endpoint is this model. Historical 8 fps bench results are not inputs
here: only the supplied current report is described. No files/devices are read.
"""

from dataclasses import asdict
import json

from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    NativeCameraMode,
    NativeControlObservation,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest


GUIDANCE_ID = "b0477-mode-review-v1"
_REFERENCE = NativeCameraMode(5472, 3648, 9, 1)
_VARIANCE = NativeCameraMode(5472, 3648, 8, 1)
_REQUIRED_CONTROLS = ("exposure", "white_balance")
# Immutable rule bytes only. No observation, decision or owner is cached.
_RULES = canonical(
    dict(
        guidance_id=GUIDANCE_ID,
        reference_mode=asdict(_REFERENCE),
        variance_candidate=asdict(_VARIANCE),
        required_manual_controls=list(_REQUIRED_CONTROLS),
        purpose="DISPLAY_REVIEW_GUIDANCE_ONLY",
        approved_operating_policy=False,
        automatic_fallback=False,
    )
)
GUIDANCE_SHA256 = digest(_RULES)


def _classification(mode: NativeCameraMode | None) -> tuple[str, str]:
    if mode is not None and type(mode) is not NativeCameraMode:
        raise ValueError(
            "Exact native mode or an explicit missing observation required"
        )
    status, label = "NOT_OBSERVED", "mode not observed"
    if mode is not None:
        if mode.same_format(_REFERENCE):
            status, label = "REFERENCE_MATCH_REVIEW_REQUIRED", "9 fps reference match"
        elif mode.same_format(_VARIANCE):
            status, label = (
                "EIGHT_FPS_VARIANCE_REVIEW_REQUIRED",
                "8 fps variance from 9 fps",
            )
        else:
            status, label = (
                "OTHER_MODE_REVIEW_REQUIRED",
                "different from 9 fps reference",
            )
    return status, label


def mode_review(mode: NativeCameraMode | None) -> dict:
    """Preserve fractions/layout; never round 8 fps into 9 fps.

    same_format ignores stride for the numerical reference match. Existing
    configuration checks still own layout support. A match always needs review.
    """
    status, label = _classification(mode)
    return dict(
        schema="rocell.camera_mode_review_guidance.v1",
        rules=json.loads(_RULES),
        guidance_sha256=GUIDANCE_SHA256,
        status=status,
        label=label,
        reported_mode=None if mode is None else asdict(mode),
        review_required=True,
        physical_authority=False,
        hardware_qualified=False,
        canonical_stage_pass=False,
        evidence_authenticated=False,
    )


def mode_choice_label(mode: NativeCameraMode) -> str:
    """A reported selectable layout is not an approved commissioning mode."""
    return _classification(mode)[1] + "; review required"


def probe_guidance(
    modes: tuple[NativeCameraMode, ...],
    controls: tuple[NativeControlObservation, ...],
) -> str:
    """Describe reported support, without interpreting it as selected/applied."""
    statuses = {_classification(mode)[0] for mode in modes}
    modes_note = (
        "9 fps reference reported"
        if "REFERENCE_MATCH_REVIEW_REQUIRED" in statuses
        else "9 fps reference not reported"
    )
    if "EIGHT_FPS_VARIANCE_REVIEW_REQUIRED" in statuses:
        modes_note += "; 8 fps reported: separate operating-policy review required"
    reported = {item.control_id: item for item in controls}
    notes = []
    for name in _REQUIRED_CONTROLS:
        item = reported.get(name)
        if item is None:
            state = "not reported"
        elif not item.capability_flags & 2:
            state = "manual support not reported"
        elif item.flags == 2:
            state = "reported manual, not verified"
        else:
            state = "auto/ambiguous; manual intent needs review"
        notes.append(f"{name}: {state}")
    return (
        f"{GUIDANCE_ID}: {modes_note}. "
        + "; ".join(notes)
        + ". No mode approved or selected; USB identity/speed and reopen stability remain separate."
    )


def intent_guidance(
    mode: NativeCameraMode, controls: tuple[CameraControlSetting, ...]
) -> str:
    requested = {item.control_id: item for item in controls}
    incomplete = [
        name
        for name in _REQUIRED_CONTROLS
        if name not in requested or requested[name].mode != "manual"
    ]
    note = (
        "Manual intent incomplete: " + ", ".join(incomplete)
        if incomplete
        else "Manual exposure/white_balance requested, not read back"
    )
    return (
        f"{GUIDANCE_ID}: {mode_choice_label(mode)}. {note}. "
        "NOT APPLIED; no automatic fallback, operating-policy approval or stage acceptance."
    )


def readback_guidance(
    observed_mode: NativeCameraMode | None, rows: list[dict], *, matched: bool
) -> str:
    """Summarize already-validated comparison rows; do not reauthenticate them."""
    observed = {row["control_id"]: row for row in rows}
    missing = []
    for name in _REQUIRED_CONTROLS:
        row = observed.get(name)
        if (
            row is None
            or row["matched"] is not True
            or row["observed"] is None
            or row["observed"]["flags"] != 2
        ):
            missing.append(name)
    note = (
        "Manual readback unresolved: " + ", ".join(missing)
        if missing
        else "Manual exposure/white_balance observed once; stability unproven"
    )
    return (
        f"{GUIDANCE_ID}: {_classification(observed_mode)[1]}; review required. "
        + ("Settings comparison matched. " if matched else "Settings comparison held. ")
        + note
        + ". No pixel, USB-speed, power or stage qualification; no fallback."
    )
