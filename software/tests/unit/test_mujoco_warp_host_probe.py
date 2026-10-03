import importlib.util
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROBE_PATH = ROOT / "software/integrations/mujoco_warp/host_probe.py"
FIXTURE_PATH = ROOT / "software/tests/fixtures/mujoco_warp/fake_host_observation.json"
SPEC = importlib.util.spec_from_file_location("mujoco_warp_host_probe", PROBE_PATH)
PROBE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROBE)


def fixture_pair():
    observed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["observed"]
    lock = {
        "schema": "rocell.mujoco_warp_toolchain_lock.v1",
        "python_version": observed["python_version"],
        "packages": deepcopy(observed["packages"]),
        "host": {
            "platform_prefix": "Windows-fixture",
            "minimum_gpu_count": 2,
            "gpu_uuids": [gpu["uuid"] for gpu in observed["gpus"]],
            "gpu_name": "Fixture GPU",
            "driver_version": "fixture-driver",
            "compute_capability": "8.6",
        },
    }
    return lock, observed


def test_matching_fixture_passes_without_simulator_import_or_model_load():
    lock, observed = fixture_pair()
    result = PROBE.validate_lock(lock, observed)
    assert result["status"] == "PASS"
    assert result["simulator_modules_imported"] is False
    assert result["model_load_attempted"] is False
    assert result["hardware_write_count"] == 0
    assert result["physical_movement_count"] == 0


def test_package_mismatch_rejects_before_simulator_import_or_model_load():
    lock, observed = fixture_pair()
    observed["packages"]["mujoco-warp"] = "99.0.0"
    result = PROBE.validate_lock(lock, observed)
    assert result["status"] == "REJECTED_LOCK_MISMATCH"
    assert result["errors"] == ["package mismatch: mujoco-warp"]
    assert result["simulator_modules_imported"] is False
    assert result["model_load_attempted"] is False


def test_gpu_identity_mismatch_rejects_fail_closed():
    lock, observed = fixture_pair()
    observed["gpus"][0]["uuid"] = "altered"
    result = PROBE.validate_lock(lock, observed)
    assert result["status"] == "REJECTED_LOCK_MISMATCH"
    assert "GPU identity or order mismatch" in result["errors"]
    assert result["physical_authority"] is False
