import pytest

from rocell.application.second_heldout_pair_validation import draft
from test_shoulder_repeatability_plan import frozen


def test_second_heldout_plan_is_fixed_discriminating_and_inert():
    model = frozen()
    value = draft(model, [[0, 4095]] * 7,
                  evidence_export="wizard-evidence",
                  evidence_model_sha256=model["sha256"])
    assert value["desired"] == [2387, 1729]
    assert value["candidate"]["manifest"]["goals"] == [
        [2377, 1737], [2389, 1725], [2378, 1736]]
    assert value["control"]["manifest"]["goals"] == [
        [2389, 1725], [2377, 1737], [2389, 1725], [2386, 1728]]
    assert value["candidate"]["frozen_prediction"] == pytest.approx([2387 + 2/3, 1729])
    assert value["proposal"]["uncompensated_predicted_error"] == [3, -5]
    assert value["model_refitted"] is False
    assert value["hardware_access"] is False and value["movement_authorized"] is False


def test_second_heldout_plan_rejects_changed_model_binding():
    with pytest.raises(ValueError):
        draft(frozen(), [[0, 4095]] * 7, evidence_export="wizard-evidence",
              evidence_model_sha256="0" * 64)
