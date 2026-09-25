#!/usr/bin/env python3
"""Restore the locally missing Freeze-004 archive after the Freeze-005 audit.

Freeze 005 was applied before append-only archival was added to the re-freeze
tool.  This bounded recovery reconstructs the six prior JSON aliases from the
captured Freeze-004 snapshot and the known synchronized 004->005 transition.
It never changes an active alias and refuses to overwrite existing evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


WORKSPACE = Path(__file__).resolve().parents[2]
OLD_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-004"
NEW_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-005"
ORIGINAL_REVIEWED_PLAN_SHA256 = (
    "d567aea93b481876e53c42ebbc53b809209f8b9a420741ac7d1615562248a839"
)
OLD_SNAPSHOT = {
    "BOM.csv": "30055b6924826e709035ae0adc0c5c3ae49348ae314a7a4c2cc3256cc6b88d14",
    "config/workcell_layout.json": "fa8ce087d091318d8770e2f274e21b8547ee21e6b1582e34c37983341375b0fa",
    "config/parameters.json": "32ba6a7a887ced0e5ef5b5b8d7710a71fefdefebc43223bc8a4c25d41e059136",
    "config/print_profiles.json": "5de3272e5b0ebe82575f7cec94e07bb7f0cd99f2a9d48478be48d8926ab4c17e",
    "config/print_jobs.json": "8e82aa18177843ee97b135fd1b08f5983a44761980371d4df0606cd4500ed5b5",
    "config/measurement_record.json": "0b93bae0c9691a78b2d3552b3d47fdb2f2c9884c10b40cfb51c356e94e2e0359",
    "config/assembly_steps.json": "cfe04dd3a2434a6ec3c8cb00ed7047fed1fa971ae14940793506d539747a3a8e",
    "config/v1_prehardware_configuration.json": "04c4e394e8ded36106811a1626b9e2265d7e652869b03c5c0cf76770932b3f63",
    "config/camera_architecture_decision.json": "93b51f5635373c7a2a3d561e5a6ed0eb23c5b20c5243f158261a144e78c63c6b",
    "config/hardware_candidates.json": "1e33702b54e54ba41789b8c50362eecc19977cf534f848e50a7231e70a546e2b",
    "config/digital_fit_report.json": "1d7be5b0148d13d06875025af0531991feb94b3c63096742e616d450f9ba1deb",
    "config/robot_reach_screening.json": "348fccf9be88fc32299ab10fce14e764869422191a43963631e4f5f0ccb9e53b",
    "fiducials/apriltag_map.json": "538680cb2343ec551daa5bf5be8ce50019efea56a51d4f9c0b3866ff09f21696",
    "BUILD_BY_STEP/ACTIVE_BUILD.json": "0f6193f3ea96dba21ac42386c0e3d605d20e7471dc44ff72734eaccbd330d774",
    "BUILD_BY_STEP/INDEX.json": "f335fcec8b4f299a6e5e72cd2275a11591b0f2f0038b2c5d64528d3dbd531137",
    "BUILD_BY_STEP/PACKAGE_VALIDATION.json": "f22e1af98e6207076ba933ec5de53e4de485fe5fa8fbf91a7ef41913e6afb15e",
    "drawings/documentation_sync.json": "e0f2639c985bf0f58ea81c617a889fe4b3a3c84c894ca28fb5a9ff68c35d2397",
    "RELEASE_VALIDATION.json": "b384f45b0fec68eb2e208b2d3bd388173d412d48300bbf5f4fd3f7a531cf2a5c",
    "PRINT_READINESS.json": "4157d65930072ac39ce2704baa06e4b2318aff3ddbe6b973ba3a04dc94fd7f58",
    "BUILD_TRACKER.json": "0e7760e4de4de3db7d4842d6c374ac1d306e25c9d92fee9f01d4fd9e4ff788c1",
    "PREHARDWARE_READINESS.json": "cda1c678f1be9e4f3863703d397a525690d4408395102b3cdd277e5e380cd403",
}
OLD_BUNDLE_ARTIFACT_HASHES = {
    "simulation_hardware_profile": "9d98f58ec89989bf8883729d9c93843bd7b583ca91ed34d321fe30ee4d99326e",
    "nominal_target_profiles": "6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2",
    "arm_frame_contract": "5e3d39388149bdd191855e0bdd8c5eb7387f0419da9bc31a15cf3d807f1b9d6d",
    "camera_manifest": "bd8bd83f2382463d3541c55e68c24c0d358c8ee8fd64f07cf1498ddc87fbef26",
    "local_roarm_urdf": "a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _render(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


def _write_new(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite audit evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".restore", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    config = WORKSPACE / "software/config"
    registry_path = WORKSPACE / "software/calibrations/registry.json"
    current_paths = {
        "system_manifest": config / "system_manifest.json",
        "camera_manifest": config / "camera_manifest.json",
        "simulation_hardware_profile": config / "simulation_hardware_profile.json",
        "gate_projection": config / "gate_projection.json",
        "simulation_bundle_lock": config / "simulation_bundle_lock.json",
        "calibration_registry": registry_path,
    }
    current = {name: _load(path) for name, path in current_paths.items()}
    if current["system_manifest"].get("manifest_id") != NEW_ID:
        raise ValueError("Active manifest is not the expected Freeze 005")

    old = json.loads(json.dumps(current))
    manifest = old["system_manifest"]
    manifest["manifest_id"] = OLD_ID
    for entry in manifest["rc03"]["source_snapshot"]:
        entry["sha256"] = OLD_SNAPSHOT[entry["path"]]
    manifest["current_build_state"].update(
        {
            "ready_jobs": 6,
            "waiting_jobs": 14,
            "physical_gate_pass_count": 9,
            "physical_gate_not_tested_count": 70,
        }
    )
    old["camera_manifest"]["system_freeze_id"] = OLD_ID
    old["simulation_hardware_profile"]["binding"]["system_manifest_id"] = OLD_ID
    old["gate_projection"]["projection_id"] = "ROCELL-RC03-CAPABILITIES-FREEZE-004"
    old["gate_projection"]["system_manifest_id"] = OLD_ID
    old["calibration_registry"]["system_manifest_id"] = OLD_ID
    old_bundle = old["simulation_bundle_lock"]
    old_bundle["bundle_id"] = "ROCELL-SIM-BUNDLE-RC03-INT-R1-FREEZE-004-004"
    old_bundle["system_manifest_id"] = OLD_ID
    for artifact_id, digest in OLD_BUNDLE_ARTIFACT_HASHES.items():
        old_bundle["artifacts"][artifact_id]["sha256"] = digest

    archive_root = WORKSPACE / "software/freezes" / OLD_ID
    archive_names = {
        "system_manifest": "system_manifest.json",
        "camera_manifest": "camera_manifest.json",
        "simulation_hardware_profile": "simulation_hardware_profile.json",
        "gate_projection": "gate_projection.json",
        "simulation_bundle_lock": "simulation_bundle_lock.json",
        "calibration_registry": "calibration_registry.json",
    }
    archives = {
        name: (archive_root / archive_names[name], _render(document))
        for name, document in old.items()
    }
    old_aliases = {
        name: {
            "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
            "sha256": _digest(payload),
        }
        for name, (path, payload) in archives.items()
    }
    new_aliases = {
        name: {
            "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
            "sha256": _file_digest(path),
        }
        for name, path in current_paths.items()
    }
    new_snapshot = {
        entry["path"]: entry["sha256"]
        for entry in current["system_manifest"]["rc03"]["source_snapshot"]
    }
    transaction = {
        "schema": "rocell.refreeze_transaction.v1",
        "schema_version": 1,
        "transaction_id": "ROCELL-REFREEZE-004-TO-005",
        "commit_state": "APPLIED_AND_POSTCOMMIT_AUDIT_RECONSTRUCTED",
        "physical_release_effect": "NONE",
        "old_manifest_id": OLD_ID,
        "new_manifest_id": NEW_ID,
        "freeze_date": "2026-09-01",
        "reason": "Synchronize the complete coherent 14-source RC03 change set after package validation.",
        "approval_reference": "User instruction 'proceed' in the active Codex build thread; external signer identity was not captured.",
        "original_reviewed_plan_sha256": ORIGINAL_REVIEWED_PLAN_SHA256,
        "original_apply_tool_sha256": None,
        "audit_reconstruction": {
            "required": True,
            "reason": "Append-only archival was added only after the first Freeze-005 transaction audit.",
            "method": "Deterministic reverse projection from active Freeze 005 plus the captured Freeze-004 source and bundle hashes.",
            "recovery_tool": "software/tools/restore_freeze004_audit.py",
            "recovery_tool_sha256": _file_digest(Path(__file__).resolve()),
            "hardened_refreeze_tool_sha256": _file_digest(
                WORKSPACE / "software/tools/refreeze_build_alignment.py"
            ),
        },
        "old_alias_archive": old_aliases,
        "new_active_aliases": new_aliases,
        "source_changes": [
            {
                "path": path,
                "old_sha256": OLD_SNAPSHOT[path],
                "new_sha256": new_snapshot[path],
                "changed": OLD_SNAPSHOT[path] != new_snapshot[path],
            }
            for path in OLD_SNAPSHOT
        ],
        "preflight": {
            "rc03_release_status": "PASS",
            "build_step_package_status": "PASS",
            "physical_release": "UNRELEASED",
            "active_build_id": "2026-09-01_CELL-A",
            "print_readiness_summary": {
                "ready": 5,
                "waiting": 15,
                "not_selected": 4,
                "total_jobs": 24,
            },
            "measurement_gate_status_counts": {"NA": 4, "NOT_TESTED": 72, "PASS": 8},
            "prehardware_state": "DIGITALLY_CONSISTENT_ENGINEERING_AND_PHYSICAL_RELEASE_BLOCKED",
        },
        "postcommit_alignment_validation": {
            "status": "ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED",
            "errors": [],
            "contact_enabled": False,
        },
    }
    transaction_path = (
        WORKSPACE / "software/freezes/transactions" / f"{OLD_ID}__{NEW_ID}.json"
    )
    outputs = [*archives.values(), (transaction_path, _render(transaction))]
    for path, payload in outputs:
        _write_new(path, payload)
    checksum_lines = [
        f"{_digest(payload)}  {path.relative_to(WORKSPACE).as_posix()}"
        for path, payload in sorted(outputs, key=lambda item: str(item[0]))
    ]
    checksum_path = transaction_path.with_suffix(".sha256")
    _write_new(checksum_path, ("\n".join(checksum_lines) + "\n").encode("utf-8"))
    print(
        json.dumps(
            {
                "status": "FREEZE004_ARCHIVE_RESTORED",
                "active_manifest_unchanged": NEW_ID,
                "archive": str(archive_root.relative_to(WORKSPACE)).replace("\\", "/"),
                "transaction": str(transaction_path.relative_to(WORKSPACE)).replace("\\", "/"),
                "files_written": len(outputs) + 1,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
