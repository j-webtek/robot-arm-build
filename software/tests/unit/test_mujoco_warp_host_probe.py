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
QUEUE_SPEC = importlib.util.spec_from_file_location(
    "mujoco_warp_resumable_queue_probe",
    ROOT / "software/integrations/mujoco_warp/resumable_queue_probe.py",
)
QUEUE_PROBE = importlib.util.module_from_spec(QUEUE_SPEC)
assert QUEUE_SPEC.loader is not None
QUEUE_SPEC.loader.exec_module(QUEUE_PROBE)


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


def fake_atomic_shard_receipt(manifest, shard):
    result = {
        "shard_id": shard["shard_id"],
        "seed": shard["seed"],
        "world_count": shard["world_count"],
        "unique_initial_poses": shard["world_count"],
        "initial_qpos_sha256": "1" * 64,
        "initial_qvel_sha256": (f"{shard['seed']:064x}")[-64:],
        "replays": [
            {
                "replay": index,
                "finite": True,
                "world_count_preserved": True,
                "overflow_zero": True,
                "elapsed_seconds": 1.0,
                "world_steps_per_second": 2_000_000.0,
                "final_qpos_sha256": "2" * 64,
                "final_qvel_sha256": "3" * 64,
            }
            for index in range(PERSISTENT_PROBE.REPLAYS)
        ],
        "maximum_qpos_delta": 0.0,
        "maximum_qvel_delta": 0.0,
        "pass": True,
    }
    return QUEUE_PROBE.build_shard_receipt(manifest, shard, result)


def populate_atomic_receipts(root, manifest, device):
    root.mkdir(parents=True, exist_ok=True)
    for shard in manifest["shards"]:
        if shard["device"] != device:
            continue
        QUEUE_PROBE.atomic_write(
            root / f"{shard['shard_id']}.json",
            fake_atomic_shard_receipt(manifest, shard),
        )


def test_atomic_receipt_write_leaves_no_temporary_file(tmp_path):
    destination = tmp_path / "receipt.json"
    QUEUE_PROBE.atomic_write(destination, {"value": 7})
    assert json.loads(destination.read_text(encoding="utf-8")) == {"value": 7}
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_resumable_queue_skips_every_valid_shard_without_model_load(
    tmp_path, monkeypatch
):
    manifest = PERSISTENT_PROBE.build_manifest()
    receipt_dir = tmp_path / "cuda0"
    populate_atomic_receipts(receipt_dir, manifest, "cuda:0")
    monkeypatch.setattr(
        QUEUE_PROBE.BASE,
        "sha256",
        lambda _path: QUEUE_PROBE.BASE.EXPECTED_MJCF_SHA256,
    )
    result = QUEUE_PROBE.run_queue(
        manifest, tmp_path / "unused.mjcf", "cuda:0", receipt_dir
    )
    assert result["complete"] is True
    assert result["model_load_count"] == 0
    assert result["world_allocation_count"] == 0
    assert len(result["skipped_shard_ids"]) == 8
    assert result["executed_shard_ids"] == []


def test_invalid_shard_is_preserved_in_quarantine_and_returns_pending(tmp_path):
    manifest = PERSISTENT_PROBE.build_manifest()
    receipt_dir = tmp_path / "cuda0"
    populate_atomic_receipts(receipt_dir, manifest, "cuda:0")
    first = manifest["shards"][0]
    path = receipt_dir / f"{first['shard_id']}.json"
    altered = json.loads(path.read_text(encoding="utf-8"))
    altered["result"]["seed"] += 1
    path.write_text(json.dumps(altered), encoding="utf-8")
    result = QUEUE_PROBE.inspect_queue(
        manifest, receipt_dir, "cuda:0", quarantine=True
    )
    assert [item["shard_id"] for item in result["pending"]] == [first["shard_id"]]
    assert len(result["valid"]) == 7
    assert len(result["quarantined"]) == 1
    assert not path.exists()
    quarantined = list((receipt_dir / "_quarantine").glob("*.invalid.json"))
    assert len(quarantined) == 1
    assert json.loads(quarantined[0].read_text())["result"]["seed"] == first["seed"] + 1


def test_nonfinite_or_wrong_type_evidence_is_rejected_without_exception():
    manifest = PERSISTENT_PROBE.build_manifest()
    shard = manifest["shards"][0]
    receipt = fake_atomic_shard_receipt(manifest, shard)
    receipt["result"]["maximum_qpos_delta"] = "zero"
    receipt["result"]["replays"][0]["elapsed_seconds"] = float("nan")
    errors = QUEUE_PROBE.validate_shard_receipt(receipt, manifest, shard)
    assert "qpos repeatability failed" in errors
    assert "replay 0: timing evidence invalid" in errors
    assert "canonical receipt hash mismatch" in errors


def test_resumable_assembly_requires_exact_allowlist_and_disjoint_states(tmp_path):
    manifest = PERSISTENT_PROBE.build_manifest()
    cuda0 = tmp_path / "cuda0"
    cuda1 = tmp_path / "cuda1"
    populate_atomic_receipts(cuda0, manifest, "cuda:0")
    populate_atomic_receipts(cuda1, manifest, "cuda:1")
    admitted = QUEUE_PROBE.assemble(manifest, cuda0, cuda1)
    assert admitted["status"] == "ADMIT_RESUMABLE_RESEARCH_QUEUE"
    assert len(admitted["receipts"]) == 16
    (cuda1 / "unexpected.json").write_text("{}", encoding="utf-8")
    rejected = QUEUE_PROBE.assemble(manifest, cuda0, cuda1)
    assert rejected["status"] == "REJECTED"
    assert "cuda:1: root receipt allowlist mismatch" in rejected["errors"]
