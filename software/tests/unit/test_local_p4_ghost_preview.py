"""The local preview cannot quietly turn into a live route or a board claim."""
from pathlib import Path

import pytest

from rocell.application.local_p4_ghost_preview import (
    EXPECTED_SOURCE, preview_local_p4_ghost,
)


MODEL = Path(__file__).resolve().parents[2] / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"


def test_local_aba_reference_sweep_is_reproducible_and_offline():
    first = preview_local_p4_ghost(EXPECTED_SOURCE, MODEL)
    second = preview_local_p4_ghost(EXPECTED_SOURCE, MODEL)
    assert first == second
    assert first["status"] == "OFFLINE_REFERENCE_PASS_NOT_EXECUTABLE"
    assert len(first["legs"]) == 12
    assert [row["key"] for row in first["legs"]] == list("AAAABBBBAAAA")
    assert all(row["status"] == "REFERENCE_SWEEP_PASS" for row in first["legs"])
    assert first["minimum_nonadjacent_proxy_distance_mm"] > 30
    assert first["hardware_access"] is False
    assert first["motion_authorized"] is False
    assert first["physical_clearance_verified"] is False
    assert first["physical_accuracy_verified"] is False
    assert first["installed_stylus_offset_applied"] is False


@pytest.mark.parametrize("changed", [
    (2047, 2225, 1890, 2716, 1978, 2041, 2047),
    (2047, 2225, 1890, 2716, 1979, 2041, 2048),
    (),
])
def test_changed_source_is_rejected(changed):
    with pytest.raises(ValueError, match="Exact independently verified P4 source"):
        preview_local_p4_ghost(changed, MODEL)
