"""Runtime-manifest proposal rejects out-of-envelope or arbitrary routes."""
from copy import deepcopy

import pytest

from rocell.application.reviewed_hover_manifest import ghost_key_manifest, validate_manifest


def test_ghost_key_manifest_is_exact_finite_offline_contract():
    result = validate_manifest(ghost_key_manifest())
    assert result["leg_count"] == 16
    assert result["targets"][:8] == result["targets"][8:]
    assert result["status"] == "OFFLINE_MANIFEST_VALID_NOT_EXECUTABLE"
    assert not result["controller_support_verified"]


@pytest.mark.parametrize("change",[
    {"pose_ids":["B_DOWN"]},
    {"pose_ids":["A_HOVER"]*17},
    {"speed":100},
    {"acceleration":2},
    {"acceleration":True},
    {"maximum_writes":100},
    {"maximum_writes":16.0},
    {"one_use_per_boot":False},
    {"motion_authorized":True},
    {"source_pose":"B_CLEAR"},
])
def test_manifest_rejects_unreviewed_variants(change):
    document = deepcopy(ghost_key_manifest())
    document.update(change)
    with pytest.raises(ValueError):
        validate_manifest(document)


def test_manifest_rejects_extra_arbitrary_target_field():
    document = ghost_key_manifest()
    document["raw_targets"] = [[0]*7]
    with pytest.raises(ValueError,match="Exact"):
        validate_manifest(document)
