"""Application-level closed planning checks; no process or M1 store is created."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.camera_rehearsal_campaign import camera_settings
from rocell.application.owned_camera_rehearsal_campaign import OwnedBinaryCameraWorker
from rocell.application.physical_onboarding import STAGE_ORDER


def arguments(tmp_path):
    settings = camera_settings(0)
    return {
        "workspace": Path(__file__).resolve().parents[3],
        "root": tmp_path / "not-created",
        "source_sha256": "a" * 64,
        "frame_count": 1,
        "fault": "none",
        "settings": settings,
        "settings_epoch": hashlib.sha256(
            json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "selected_camera": {
            "candidate_id": "synthetic-b0477",
            "provenance": "SYNTHETIC_NOT_ENUMERATED",
            "model": "B0477",
            "unit_id": "SYNTHETIC-UNIT-A",
            "endpoint": "incapable-fixture-only",
        },
    }


@pytest.mark.parametrize("count", [True, False, 0, 5, -1, 1.0, "1", None])
def test_frame_count_is_an_exact_bounded_integer(tmp_path, count):
    args = arguments(tmp_path)
    args["frame_count"] = count
    with pytest.raises(ValueError, match="Unknown or oversized"):
        OwnedBinaryCameraWorker(**args)
    assert not args["root"].exists()


@pytest.mark.parametrize("fault", ["nominal", "retry", "capture", "", None])
def test_no_unregistered_scenario_or_backend_alias(tmp_path, fault):
    args = arguments(tmp_path)
    args["fault"] = fault
    with pytest.raises(ValueError, match="Unknown or oversized"):
        OwnedBinaryCameraWorker(**args)


@pytest.mark.parametrize("count", [1, 4])
def test_planning_copies_inputs_and_keeps_fixed_retained_budget(tmp_path, count):
    args = arguments(tmp_path)
    args["frame_count"] = count
    original = deepcopy(args)
    worker = OwnedBinaryCameraWorker(**args)
    args["selected_camera"]["endpoint"] = "not-a-device"
    args["settings"]["brightness_offset"] = 99
    plan = worker.plan()
    assert plan["selected_camera"] == original["selected_camera"]
    assert plan["settings"] == original["settings"]
    assert plan["process_backend"] == "OWNED_INCAPABLE_CAMERA_PROCESS"
    assert plan["binary_artifact_budget_bytes"] == (
        (2 * 39_923_712 + 4_990_464) * count + 128 * 1024 * 1024
    )
    for stage in STAGE_ORDER[4:6]:
        registration = worker.registration(stage)
        assert registration.action_id == "rehearsal-owned-camera-campaign"
        assert registration.budget.maximum_output_bytes == 128 * 1024
        assert registration.budget.maximum_frames == count
        assert registration.budget.maximum_writes == 0
        assert registration.budget.timeout_ms == 60_000
    assert worker.capture is None and worker.evidence is None
    assert not original["root"].exists()
    with pytest.raises(ValueError, match="retained-evidence"):
        worker.run_campaign()


@pytest.mark.parametrize(
    "stage", [STAGE_ORDER[0], STAGE_ORDER[3], STAGE_ORDER[6], STAGE_ORDER[-1]]
)
def test_only_due_camera_stages_have_a_registration(tmp_path, stage):
    worker = OwnedBinaryCameraWorker(**arguments(tmp_path))
    with pytest.raises(ValueError, match="due camera stage"):
        worker.registration(stage)


def test_changed_settings_epoch_rejected_before_artifacts(tmp_path):
    args = arguments(tmp_path)
    args["settings_epoch"] = "b" * 64
    with pytest.raises(ValueError, match="exact epoch"):
        OwnedBinaryCameraWorker(**args)
    assert not args["root"].exists()
