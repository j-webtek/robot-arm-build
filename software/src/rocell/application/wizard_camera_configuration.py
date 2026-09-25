"""Pure wizard fields and settings joins; never discovers or opens hardware.

The probe reports driver units, not measured optics or promises about the
received Arducam. Staging is immutable intent; only a later retained capture
can provide independent control readback.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .camera_configuration import (
    CameraCapabilities,
    StagedCameraConfiguration,
    stage_camera_configuration,
)
from .camera_rehearsal_campaign import MODE
from .wizard_actions import WizardError
from rocell.providers.windows.camera_worker_client import CameraControlSetting


def effective_camera_settings_epoch(
    synthetic_settings_epoch: str, configuration: StagedCameraConfiguration
) -> str:
    """Bind image-generation settings AND the exact probe-derived camera intent."""
    value = {
        "synthetic_settings_epoch": synthetic_settings_epoch,
        "electronic_settings_epoch": configuration.settings_epoch,
        "probe_evidence_sha256": configuration.to_dict()["probe_evidence_sha256"],
    }
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("ascii")
    ).hexdigest()


def configuration_fields(
    capabilities: CameraCapabilities | None,
) -> tuple[dict[str, Any], ...]:
    """Closed choices from a cached verified report, shared by UI and validation."""
    view = capabilities.view() if capabilities else {"modes": [], "controls": []}
    fields: list[dict[str, Any]] = [
        {
            "name": "mode_choice_id",
            "label": "Explicitly select a reported camera mode",
            "type": "select",
            "required": True,
            "options": [
                {
                    "value": item["choice_id"],
                    "label": (
                        f"{item['mode']['width']} × {item['mode']['height']} "
                        f"{item['mode']['fps_numerator']}/{item['mode']['fps_denominator']} fps "
                        f"{item['mode']['subtype']} — modeled rehearsal"
                    ),
                }
                for item in view["modes"]
                if item["selectable"]
                and item["mode"]["width"] == MODE.width
                and item["mode"]["height"] == MODE.height
                and item["mode"]["fps_numerator"] == MODE.fps_numerator
                and item["mode"]["fps_denominator"] == MODE.fps_denominator
                and item["mode"]["subtype"] == MODE.subtype
            ],
        }
    ]
    for control in view["controls"]:
        cid = control["control_id"]
        options = [{"value": "unchanged", "label": "Do not request a change"}]
        for flag, name in ((2, "manual"), (1, "auto")):
            if control["capability_flags"] & flag:
                options.append({"value": name, "label": name})
        fields.extend(
            (
                {
                    "name": cid + "_mode",
                    "label": f"{cid.replace('_', ' ')} control intent",
                    "type": "select",
                    "required": True,
                    "default": "unchanged",
                    "options": options,
                },
                {
                    "name": cid + "_value",
                    "label": f"{cid.replace('_', ' ')} value ({control['unit']}; used only when requested)",
                    "type": "number",
                    "required": True,
                    "default": control["value"],
                    "min": control["minimum"],
                    "max": control["maximum"],
                    "step": control["step"],
                },
            )
        )
    return tuple(fields)


def stage_wizard_camera_configuration(
    capabilities: CameraCapabilities,
    values: dict[str, Any],
    *,
    source_sha256: str,
    selected_identity_sha256: str,
) -> StagedCameraConfiguration:
    """Validate all semantic fields before retaining intent or doing any I/O."""
    fields = configuration_fields(capabilities)
    expected = {field["name"] for field in fields}
    public = {key: value for key, value in values.items() if not key.startswith("_")}
    if set(public) != expected:
        raise WizardError(
            "CAMERA_CONFIGURATION_FIELDS", "Use the current reported fields only."
        )
    controls = []
    for item in capabilities.view()["controls"]:
        cid = item["control_id"]
        mode, value = public[cid + "_mode"], public[cid + "_value"]
        if mode not in {"unchanged", "manual", "auto"} or type(value) is not int:
            raise WizardError(
                "CAMERA_CONFIGURATION_FIELDS",
                "Control modes and integer driver units must be exact.",
            )
        if mode != "unchanged":
            controls.append(CameraControlSetting(cid, value, mode))
    candidate = stage_camera_configuration(
        capabilities,
        public["mode_choice_id"],
        tuple(controls),
        expected_probe_evidence_sha256=capabilities.to_dict()["probe_evidence_sha256"],
        expected_source_sha256=source_sha256,
        expected_selected_identity_sha256=selected_identity_sha256,
    )
    if not candidate.mode.same_format(MODE):
        raise WizardError(
            "UNREGISTERED_FIXTURE_MODE",
            "The contained placemat fixture currently supports its fixed full-resolution YUY2 mode only.",
        )
    return candidate
