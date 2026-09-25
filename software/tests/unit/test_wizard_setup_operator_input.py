"""Portable setup IDs fail at preview; newer display-label rules stay distinct."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    PORTABLE_SETUP_ACTORS,
    PORTABLE_SETUP_OPERATOR_HELP,
    WizardError,
    portable_setup_operator_valid,
    validate_action_input,
)
from test_arrival_wizard_service import make_service, _ticket


PORTABLE_ACTIONS = sorted({*PORTABLE_SETUP_ACTORS, "physical_camera_configuration"})


def inputs(action_id, label):
    definition = ACTION_BY_ID[action_id]
    fields = deepcopy(definition.fields)
    values = {PORTABLE_SETUP_ACTORS.get(action_id, "operator_id"): label}
    # Supply unrelated required fields so these tests isolate operator grammar.
    # These are validation-only fixtures, never retained physical observations.
    values.update({
        "record_first_motion_measurements": dict(unit_serial="A" * 32,
            angle_deg=0, angle_uncertainty_deg=1, distal_radius_mm=50,
            radius_uncertainty_mm=1, observation_notes="Synthetic input-validation fixture"),
        "run_endpoint_trial": dict(draft_sha256="a" * 64),
        "run_first_motion": dict(selection_sha256="b" * 64),
    }.get(action_id, {}))
    for field in fields:
        if field["type"] == "checkbox":
            values[field["name"]] = True
        elif field["type"] == "select":
            # Use actual closed choices (e.g. measurement method). Only empty
            # dynamic selectors need an opaque validation-only original.
            if not field["options"]:
                field["options"] = [{"value": "modeled-original", "label": "Modeled"}]
            values[field["name"]] = field["options"][0]["value"]
    return replace(definition, fields=fields), values


@pytest.mark.parametrize("action_id", PORTABLE_ACTIONS)
@pytest.mark.parametrize(
    "label", ["MODELED refresh operator", " leading", "a/b", "é", "a\t"]
)
def test_bad_portable_label_rejected_by_the_preview_contract(action_id, label):
    definition, values = inputs(action_id, label)
    assert not portable_setup_operator_valid(label)
    with pytest.raises(WizardError) as error:
        validate_action_input(definition, values)
    assert error.value.code in (
        {"INVALID_TEXT", "INVALID_FIRST_MOTION_MEASUREMENTS"}
        if action_id == "record_first_motion_measurements" else {"INVALID_TEXT"}
    )


@pytest.mark.parametrize("action_id", PORTABLE_ACTIONS)
@pytest.mark.parametrize("label", ["MODELED-refresh-operator", "A._-1", "a" * 64])
def test_existing_portable_id_language_is_unchanged(action_id, label):
    definition, values = inputs(action_id, label)
    assert portable_setup_operator_valid(label)
    assert validate_action_input(definition, values) == values
    field = next(
        field
        for field in definition.view(mode="physical", busy=False)["fields"]
        if field["name"] == PORTABLE_SETUP_ACTORS.get(action_id, "operator_id")
    )
    assert field["help"] == PORTABLE_SETUP_OPERATOR_HELP
    assert all("help" not in field for field in definition.fields)


@pytest.mark.parametrize("label", [None, True, 1, "", "a" * 65, "_operator", "a\n"])
def test_shared_execution_rule_refuses_non_ids(label):
    assert portable_setup_operator_valid(label) is False


@pytest.mark.parametrize(
    "action_id",
    [
        "physical_camera_mode_enter",
        "physical_camera_probe_prepare",
        "physical_camera_probe_review",
    ],
)
def test_newer_trimmed_display_labels_still_allow_spaces(action_id):
    values = dict(operator_id="MODELED probe reviewer", file_only=True)
    assert validate_action_input(ACTION_BY_ID[action_id], values) == values


def test_bad_public_initialization_label_has_no_ticket_log_or_store_side_effect(
    make_service,
):
    app, runner, _ = make_service(mode="physical")
    before = app.view()
    with pytest.raises(WizardError) as error:
        _ticket(app, "physical_camera_initialize", dict(operator_id="contains spaces"))
    assert error.value.code == "INVALID_TEXT"
    after = app.view()
    for key in ("revision", "operations", "events", "physical_camera_setup"):
        assert after[key] == before[key]
    assert not runner.calls
    assert not Path(
        app._physical_camera_setup.session.descriptor()["directory"]
    ).exists()
