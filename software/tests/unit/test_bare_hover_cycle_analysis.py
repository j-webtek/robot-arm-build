"""r95 evidence proves composition in counts, never physical key accuracy."""
import json
from pathlib import Path

import pytest

from rocell.application.bare_hover_cycle_analysis import analyze


ROOT = Path(__file__).resolve().parents[2]
EXPORTS = (
    "wizard-20260925T175239899544Z-b01b2d4bd0014798bcd16078e6fac8a3",
    "wizard-20260925T184230842590Z-c53992896fce4d4f99d27db7cad107a8",
    "wizard-20260925T184309529486Z-0ef21c5ddcdc4d9492cdd8b564cb9bf3",
    "wizard-20260925T184440994897Z-ee8a958090454b44b20c5283f8b61319",
    "wizard-20260925T184552652527Z-43a68b4aa26347deb4bc89f9d087eb74",
)


def records():
    return [json.loads((ROOT / "runs/wizard-exports" / export_id /
                        "attachment-bare-hover-leg.json").read_text())
            for export_id in EXPORTS]


def test_completed_cycle_is_composable_but_not_board_calibrated():
    result = analyze(records())
    assert result["maximum_selected_goal_residual_counts"] == 9
    assert result["hover_nonbase_repeatability_max_counts"] == 1
    assert result["clear_nonbase_repeatability_max_counts"] == 0
    assert result["stroke_vector_difference_max_counts"] == 1
    assert result["corresponding_endpoint_base_separation_counts"] == {
        "hover": 40, "clear": 40}
    model = result["pinned_firmware_reference_model"]
    assert model["status"] == "MODEL_ONLY_NOT_INSTALLED_BOARD_FRAME"
    assert model["clear_to_hover_distance_mm"] == pytest.approx(6.05, abs=.01)
    assert model["region_separation_distance_mm"] == pytest.approx(15.05, abs=.01)
    assert not result["board_to_controller_verified"]
    assert not result["physical_key_centers_verified"]
    assert not result["motion_authorized"]
