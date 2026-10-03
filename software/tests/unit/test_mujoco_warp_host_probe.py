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
ASSET_SPEC = importlib.util.spec_from_file_location(
    "mujoco_warp_asset_parity_probe",
    ROOT / "software/integrations/mujoco_warp/asset_parity_probe.py",
)
ASSET_PROBE = importlib.util.module_from_spec(ASSET_SPEC)
assert ASSET_SPEC.loader is not None
ASSET_SPEC.loader.exec_module(ASSET_PROBE)
BATCH_SPEC = importlib.util.spec_from_file_location(
    "mujoco_warp_batch_probe",
    ROOT / "software/integrations/mujoco_warp/batch_probe.py",
)
BATCH_PROBE = importlib.util.module_from_spec(BATCH_SPEC)
assert BATCH_SPEC.loader is not None
BATCH_SPEC.loader.exec_module(BATCH_PROBE)
LARGE_SPEC = importlib.util.spec_from_file_location(
    "mujoco_warp_large_batch_probe",
    ROOT / "software/integrations/mujoco_warp/large_batch_probe.py",
)
LARGE_PROBE = importlib.util.module_from_spec(LARGE_SPEC)
assert LARGE_SPEC.loader is not None
LARGE_SPEC.loader.exec_module(LARGE_PROBE)


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


def test_kinematic_converter_maps_every_joint_and_blocks_dynamic_claims():
    urdf = ROOT / "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
    asset = ASSET_PROBE.parse_urdf(urdf)
    xml, provenance = ASSET_PROBE.build_kinematic_mjcf(asset)
    assert [joint["name"] for joint in asset["joints"] if joint["type"] == "revolute"] == ASSET_PROBE.JOINT_ORDER
    assert xml.count("<joint ") == 6
    assert xml.count("<inertial ") == 6
    assert provenance["compiled_inertia"] == "EXPLICIT_KINEMATIC_ONLY_PLACEHOLDER"
    assert provenance["dynamics_claim"] == "BLOCKED"
    assert provenance["contact_claim"] == "BLOCKED"


def fake_batch_receipt(device, rate, safety=True):
    results = []
    for nworld in BATCH_PROBE.WORLD_COUNTS:
        results.append(
            {
                "nworld": nworld,
                "pass": safety,
                "timing": {"median_world_steps_per_second": rate * nworld},
            }
        )
    return {
        "device_requested": device,
        "mjcf_sha256": BATCH_PROBE.EXPECTED_MJCF_SHA256,
        "safety_pass": safety,
        "results": results,
        "receipt_sha256": f"fixture-{device}",
    }


def test_batch_admission_preserves_device_shards_and_applies_speed_gate():
    standard = fake_batch_receipt("cpu", 10)
    gpu0 = fake_batch_receipt("cuda:0", 40)
    gpu1 = fake_batch_receipt("cuda:1", 35)
    result = BATCH_PROBE.admit(standard, gpu0, gpu1)
    assert result["status"] == "ADOPT_FOR_DECLARED_SCOPE"
    assert result["dual_gpu_aggregation_performed"] is False
    assert result["speedups_vs_standard_mujoco"]["cuda:0"]["4096"] == 4


def test_batch_admission_rejects_overflow_or_underperforming_shard():
    standard = fake_batch_receipt("cpu", 10)
    gpu0 = fake_batch_receipt("cuda:0", 40)
    gpu1 = fake_batch_receipt("cuda:1", 20, safety=False)
    result = BATCH_PROBE.admit(standard, gpu0, gpu1)
    assert result["status"] == "RESEARCH_ONLY"
    assert any("safety/repeatability" in error for error in result["errors"])
    assert any("speedup below gate" in error for error in result["errors"])


def fake_large_shard(device, rate, safety=True):
    return {
        "device_requested": device,
        "mjcf_sha256": LARGE_PROBE.EXPECTED_MJCF_SHA256,
        "world_counts": LARGE_PROBE.WORLD_COUNTS,
        "safety_pass": safety,
        "results": [
            {"nworld": count, "median_world_steps_per_second": rate}
            for count in LARGE_PROBE.WORLD_COUNTS
        ],
        "receipt_sha256": f"large-{device}",
    }


def test_large_batch_admission_is_separate_from_general_mw2_scope():
    gpu0 = fake_large_shard("cuda:0", 1_300_000)
    gpu1 = fake_large_shard("cuda:1", 1_250_000)
    concurrent = {
        "aggregate_median_world_steps_per_second": 2_400_000,
        "safety_pass": True,
        "receipt_sha256": "concurrent",
    }
    result = LARGE_PROBE.admit(gpu0, gpu1, concurrent)
    assert result["status"] == "ADOPT_LARGE_BATCH_RESEARCH"
    assert result["dual_gpu_state_aggregation"] is False
    assert "MW2 general-purpose rejection remains unchanged" in result["limitations"]


def test_large_batch_admission_fails_closed_on_scaling_or_safety():
    gpu0 = fake_large_shard("cuda:0", 1_300_000)
    gpu1 = fake_large_shard("cuda:1", 900_000, safety=False)
    concurrent = {
        "aggregate_median_world_steps_per_second": 1_500_000,
        "safety_pass": False,
        "receipt_sha256": "concurrent",
    }
    result = LARGE_PROBE.admit(gpu0, gpu1, concurrent)
    assert result["status"] == "RESEARCH_ONLY"
    assert any("safety gate failed" in error for error in result["errors"])
    assert "concurrent shard safety gate failed" in result["errors"]
