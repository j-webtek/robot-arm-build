"""Pure ownership projection: unchanged holds and no stage authority."""

from itertools import combinations

import pytest

from rocell.application import camera_operating_stage_requirements as module
from rocell.application.camera_operating_evidence_preflight import (
    CHECK_IDS,
    OWNER_OBLIGATIONS,
)
from rocell.application.physical_onboarding import STAGE_ORDER


def test_every_existing_hold_has_a_canonical_owner_without_advancing_a_stage():
    holds = [*OWNER_OBLIGATIONS, module.RETENTION_HOLD]
    result = module.project_operating_requirements(holds, CHECK_IDS)
    assert [row["id"] for row in result["requirements"]] == holds
    assert result["failed_metadata_checks"] == list(CHECK_IDS)
    assert result["metadata_check_owner"] == STAGE_ORDER[4].value
    allowed = {stage.value for stage in STAGE_ORDER}
    for row in result["requirements"]:
        assert set(row["owner_stages"]) <= allowed
        assert not set(row["owner_stages"]) & {s.value for s in STAGE_ORDER[8:]}
    assert {
        row["id"] for row in result["requirements"] if row["scope"] == "LATER_STAGE"
    } == {
        "FRAME_FRESHNESS_NOT_ASSESSED",
        "INSTALLED_OPTICS_AND_CALIBRATION_DEFERRED",
    }
    assert all(
        result[key] is False
        for key in (
            "stage_passed",
            "original_store_authenticated",
            "physical_authority",
            "hardware_qualified",
        )
    )


@pytest.mark.parametrize(
    "holds", [list(c) for n in range(3) for c in combinations(OWNER_OBLIGATIONS, n)]
)
def test_subsets_preserve_exact_requirements_and_deterministic_order(holds):
    a = module.project_operating_requirements(holds, [])
    b = module.project_operating_requirements(list(reversed(holds)), ())
    assert a == b
    assert {row["id"] for row in a["requirements"]} == set(holds)
    assert not a["stage_passed"]
    a["requirements"].clear()
    assert len(module.project_operating_requirements(holds, [])["requirements"]) == len(
        holds
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        {},
        set(),
        [True],
        [1],
        [[]],
        ["unknown"],
        [OWNER_OBLIGATIONS[0]] * 2,
        [OWNER_OBLIGATIONS[0]] * 100,
    ],
)
def test_malformed_or_unknown_holds_are_not_silently_dropped(bad):
    with pytest.raises(module.CameraStageRequirementsError):
        module.project_operating_requirements(bad, [])


@pytest.mark.parametrize(
    "bad", [None, "", {}, [False], ["unknown"], [CHECK_IDS[0]] * 2]
)
def test_malformed_metadata_check_roster_fails_closed(bad):
    with pytest.raises(module.CameraStageRequirementsError):
        module.project_operating_requirements([], bad)
