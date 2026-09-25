"""Read-only calibration readiness projection for keyboard/phone missions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from rocell.calibration import (
    REQUIREMENTS,
    ArtifactAssessment,
    CalibrationRegistry,
    ordered_requirement_closure,
)
from rocell.typing import development_keyboard_profile, development_phone_profile

from .context import SimulationContext, revalidate_simulation_context


@dataclass(frozen=True, slots=True)
class CalibrationStatusReport:
    device: str
    ordered_requirements: tuple[str, ...]
    assessments: tuple[ArtifactAssessment, ...]
    manifest_id: str
    simulation_bundle_id: str
    simulation_bundle_sha256: str
    active_build_id: str | None

    @property
    def all_valid(self) -> bool:
        return bool(self.assessments) and all(item.valid for item in self.assessments)

    def to_dict(self) -> dict[str, Any]:
        by_id = {item.artifact_id: item for item in self.assessments}
        return {
            "schema": "rocell.calibration_status.v1",
            "status": "READY" if self.all_valid else "BLOCKED_MISSING_OR_STALE",
            "device": self.device,
            "manifest_id": self.manifest_id,
            "simulation_bundle_id": self.simulation_bundle_id,
            "simulation_bundle_sha256": self.simulation_bundle_sha256,
            "active_build_id": self.active_build_id,
            "all_valid": self.all_valid,
            "physical_release_effect": "NONE",
            "hardware_accessed": False,
            "execution_authorized": False,
            "ordered_requirements": [
                {
                    "artifact_id": artifact_id,
                    "prerequisites": list(REQUIREMENTS[artifact_id].prerequisites),
                    "purpose": REQUIREMENTS[artifact_id].purpose,
                    "acceptance_evidence": REQUIREMENTS[artifact_id].acceptance_evidence,
                    "assessment": {
                        "state": by_id[artifact_id].state.value,
                        "valid": by_id[artifact_id].valid,
                        "artifact_hash": by_id[artifact_id].artifact_hash,
                        "reasons": list(by_id[artifact_id].reasons),
                    },
                }
                for artifact_id in self.ordered_requirements
            ],
        }

    @property
    def report_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def assess_calibration_status(
    context: SimulationContext,
    device: str,
) -> CalibrationStatusReport:
    """Resolve the complete prerequisite graph against immutable artifacts."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    if device == "keyboard":
        requested = development_keyboard_profile().required_calibrations
    elif device == "phone":
        requested = development_phone_profile().required_calibrations
    else:
        raise ValueError(f"Unsupported device {device!r}")
    ordered = ordered_requirement_closure(requested)
    snapshot = context.snapshot
    hashes = {
        "system_manifest": snapshot.manifest_sha256,
        "simulation_bundle": context.bundle_lock.source_lock_sha256,
        "simulation_profile": context.scenario.source_profile_sha256,
        "target_profile": context.targets.content_sha256,
        "kinematic_model": context.scenario.model_sha256,
        "camera_manifest": context.hardware_profile.source_camera_manifest_sha256,
        "workcell_layout": context.scene.source_hashes["config/workcell_layout.json"],
        "apriltag_map": context.scene.source_hashes["fiducials/apriltag_map.json"],
    }
    build_id = snapshot.active_build_id or "UNASSIGNED"
    registry = CalibrationRegistry(context.workspace / "software/calibrations")
    resolution = registry.resolve(
        ordered,
        hashes,
        manifest_id=snapshot.manifest_id,
        active_build_id=build_id,
    )
    return CalibrationStatusReport(
        device=device,
        ordered_requirements=ordered,
        assessments=tuple(
            resolution.assessments[artifact_id] for artifact_id in ordered
        ),
        manifest_id=snapshot.manifest_id,
        simulation_bundle_id=context.bundle_lock.bundle_id,
        simulation_bundle_sha256=context.bundle_lock.source_lock_sha256,
        active_build_id=snapshot.active_build_id,
    )
