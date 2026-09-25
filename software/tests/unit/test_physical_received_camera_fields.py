"""Pure form/default compatibility: no setup, file or device fixture needed."""

import pytest

from rocell.application.physical_received_camera_fields import received_camera_fields
from rocell.application.physical_received_camera_service import (
    PhysicalReceivedCameraService,
    SUBMIT,
)
from rocell.application.wizard_actions import WizardError


def test_receipt_form_has_no_prechecked_answers_and_unknown_certainty():
    fields = received_camera_fields(SUBMIT, notebook=None, choices=[])
    assert len(fields) == 33
    assert all(row["default"] is False for row in fields if row["type"] == "checkbox")
    certainty = next(row for row in fields if row["name"] == "inspection_uncertain")
    assert certainty["type"] == "select" and certainty["default"] == "UNCERTAIN"
    assert [row["value"] for row in certainty["options"]] == ["UNCERTAIN", "CERTAIN"]


def inspect(values):
    # This scalar preflight does not consult service state. Avoid constructing a
    # setup just to prove that categories map to the immutable boolean receipt.
    service = object.__new__(PhysicalReceivedCameraService)
    return service._inspection_values(values)


@pytest.mark.parametrize(
    "value,expected",
    [("UNCERTAIN", True), ("CERTAIN", False), (True, True), (False, False)],
)
def test_certainty_category_normalizes_to_the_receipt_boolean(value, expected):
    result = inspect(
        dict(
            inspection_state="RECORDED",
            inspection_observed_now=True,
            observed_manufacturer="MODELED",
            observed_product_id="MODELED",
            observed_camera_serial="MODELED",
            inspection_uncertain=value,
            purchase_choice="modeled-choice",
            inspection_image_choice="modeled-image",
        )
    )
    assert result["inspection_uncertain"] is expected


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false", "", [], {}])
def test_no_truthy_coercion_or_arbitrary_certainty_categories(value):
    with pytest.raises(WizardError):
        inspect({"inspection_uncertain": value})


def test_unknown_inspection_keeps_uncertainty_without_an_automatic_answer():
    assert inspect({}) is None
    assert inspect({"inspection_uncertain": "UNCERTAIN"}) is None
    with pytest.raises(WizardError):
        inspect({"inspection_uncertain": "CERTAIN"})
