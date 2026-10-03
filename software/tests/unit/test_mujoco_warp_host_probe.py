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
PERSISTENT_SPEC = importlib.util.spec_from_file_location(
    "mujoco_warp_persistent_campaign_probe",
    ROOT / "software/integrations/mujoco_warp/persistent_campaign_probe.py",
)
PERSISTENT_PROBE = importlib.util.module_from_spec(PERSISTENT_SPEC)
assert PERSISTENT_SPEC.loader is not None
PERSISTENT_SPEC.loader.exec_module(PERSISTENT_PROBE)


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


def test_persistent_manifest_is_compact_disjoint_and_self_bound():
    manifest = PERSISTENT_PROBE.build_manifest()
    PERSISTENT_PROBE.validate_manifest(manifest)
    assert len(manifest["shards"]) == 16
    assert {item["world_count"] for item in manifest["shards"]} == {16_384}
    assert len({item["seed"] for item in manifest["shards"]}) == 16
    assert manifest["hardware_write_count"] == 0
    assert manifest["physical_authority"] is False


def test_persistent_manifest_rejects_an_altered_seed():
    manifest = PERSISTENT_PROBE.build_manifest()
    manifest["shards"][0]["seed"] += 1
    try:
        PERSISTENT_PROBE.validate_manifest(manifest)
    except ValueError as exc:
        assert "differs from frozen" in str(exc)
    else:
        raise AssertionError("altered manifest was accepted")


def fake_persistent_orchestration(mode, wall_seconds, *, safety=True):
    manifest = PERSISTENT_PROBE.build_manifest()
    children = []
    for device in PERSISTENT_PROBE.DEVICES:
        shards = []
        for item in manifest["shards"]:
            if item["device"] != device:
                continue
            suffix = item["shard_id"]
            shards.append(
                {
                    "shard_id": suffix,
                    "initial_qpos_sha256": f"initial-qpos-{suffix}",
                    "initial_qvel_sha256": f"initial-qvel-{suffix}",
                    "replays": [
                        {
                            "final_qpos_sha256": f"final-qpos-{suffix}",
                            "final_qvel_sha256": f"final-qvel-{suffix}",
                        }
                    ],
                }
            )
        child = {
            "schema": "rocell.mujoco_warp_persistent_worker.v1",
            "device_requested": device,
            "manifest_sha256": manifest["manifest_sha256"],
            "mjcf_sha256": PERSISTENT_PROBE.EXPECTED_MJCF_SHA256,
            "model_load_count": 1,
            "world_allocation_count": 1,
            "shards": shards,
            "safety_pass": safety,
        }
        child["receipt_sha256"] = PERSISTENT_PROBE.canonical_sha256(child)
        children.append(child)
    receipt = {
        "schema": "rocell.mujoco_warp_persistent_orchestration.v1",
        "mode": mode,
        "manifest_sha256": manifest["manifest_sha256"],
        "wall_seconds_including_launch_and_receipt_writes": wall_seconds,
        "children": children,
        "safety_pass": safety,
    }
    receipt["receipt_sha256"] = PERSISTENT_PROBE.canonical_sha256(receipt)
    return receipt


def test_persistent_admission_accepts_exact_state_parity_and_wall_scaling():
    manifest = PERSISTENT_PROBE.build_manifest()
    sequential = fake_persistent_orchestration("sequential", 20.0)
    concurrent = fake_persistent_orchestration("concurrent", 10.0)
    result = PERSISTENT_PROBE.admit(manifest, sequential, concurrent)
    assert result["status"] == "ADOPT_PERSISTENT_LARGE_BATCH_RESEARCH"
    assert result["concurrent_scaling"] == 2.0
    assert result["shard_count"] == 16
    assert result["physical_authority"] is False


def test_persistent_admission_rejects_tampering_safety_and_slow_scaling():
    manifest = PERSISTENT_PROBE.build_manifest()
    sequential = fake_persistent_orchestration("sequential", 16.0)
    concurrent = fake_persistent_orchestration("concurrent", 10.0, safety=False)
    concurrent["children"][0]["shards"][0]["replays"][0][
        "final_qpos_sha256"
    ] = "tampered"
    result = PERSISTENT_PROBE.admit(manifest, sequential, concurrent)
    assert result["status"] == "RESEARCH_ONLY"
    assert any("safety gate failed" in error for error in result["errors"])
    assert any("receipt hash mismatch" in error for error in result["errors"])
    assert "sequential/concurrent state identity mismatch" in result["errors"]
    assert "persistent concurrent scaling gate failed" in result["errors"]
