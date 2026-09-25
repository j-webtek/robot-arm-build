"""Inert form definitions for explicit received-unit observations.

Defaults are unknown/blank, never the purchased model or a nominal measurement.
The service supplies only cached opaque inbox choices; there is no path input.
"""

from copy import deepcopy

from .physical_received_camera_submission import RECORD_IDS
from .wizard_actions import ACTION_BY_ID


def _text(name, label, maximum=64, required=True):
    return dict(
        name=name,
        label=label,
        type="text",
        default="",
        required=required,
        max_length=maximum,
    )


def _select(name, label, choices, default="", required=True):
    return dict(
        name=name,
        label=label,
        type="select",
        options=deepcopy(choices),
        default=default,
        required=required,
    )


def _options(*values):
    return [dict(value=value, label=value) for value in values]


def _check(name, label, default=False, required=False):
    return dict(
        name=name, label=label, type="checkbox", default=default, required=required
    )


def received_camera_fields(action, *, notebook, choices):
    """Complete replacement fields, shared by browser and terminal actions."""
    file_only = _check(
        "file_only",
        "File-only records; no device access or physical release",
        required=True,
    )
    if action == "physical_received_camera_draft_record":
        fields = deepcopy(ACTION_BY_ID["physical_intake_record"].fields)
        for field in fields:
            if field["name"] == "record_id":
                field["options"] = [] if notebook is None else notebook.choices()
        return (file_only, *fields)
    if action == "physical_received_camera_draft_start":
        return (
            file_only,
            _select(
                "mode",
                "Start blank or explicitly revise the last BLOCKED original",
                _options("BLANK", "REVISE_LAST"),
            ),
        )
    if action == "physical_received_camera_review":
        return (
            file_only,
            _text(
                "reviewer_id", "Distinct reviewer label (procedural, not authenticated)"
            ),
            _select(
                "decision",
                "Review the exact saved notebook, inspection and assessment",
                _options("ACKNOWLEDGE_EXACT", "REJECT"),
            ),
        )
    if action != "physical_received_camera_submit":
        return (file_only,)
    originals = [dict(value="", label="No original selected (UNKNOWN only)"), *choices]
    rows = tuple(
        _select(
            "attachment_" + record_id,
            record_id + " original evidence",
            originals,
            required=False,
        )
        for record_id in RECORD_IDS
    )
    conditions = _options("UNCERTAIN", "ACCEPTABLE", "DAMAGED")
    return (
        file_only,
        _text("operator_id", "Submitting operator label"),
        *rows,
        _select(
            "inspection_state",
            "Structured received-camera inspection",
            _options("UNKNOWN", "RECORDED"),
            "UNKNOWN",
        ),
        _check(
            "inspection_observed_now",
            "I performed this inspection for this submission; these are not copied or assumed observations",
        ),
        _text("observed_manufacturer", "Manufacturer as observed", 256, False),
        _text("observed_product_id", "Product ID as observed", 256, False),
        _text(
            "observed_camera_serial",
            "Serial / explicitly recorded serial absence",
            256,
            False,
        ),
        _text(
            "observed_lens_focal_length_mm",
            "Observed focal length in mm (blank means unknown)",
            3,
            False,
        ),
        *(
            _select(name, name.replace("_", " "), conditions, "UNCERTAIN")
            for name in ("body_condition", "lens_condition", "connector_condition")
        ),
        *(
            _check(name, name.replace("_", " "))
            for name in (
                "identity_label_legible",
                "purchase_record_matches",
                "package_contents_complete",
            )
        ),
        _select(
            "inspection_uncertain",
            "Inspection certainty",
            _options("UNCERTAIN", "CERTAIN"),
            "UNCERTAIN",
        ),
        _select("purchase_choice", "Purchase original", originals, required=False),
        _select(
            "inspection_image_choice",
            "Inspection image original (PNG/JPEG)",
            originals,
            required=False,
        ),
    )
