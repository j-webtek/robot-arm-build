"""Deterministic, hardware-independent startup for the virtual RoCell workcell.

This module is the single read-only assembly boundary for simulation.  It
validates runtime policy before constructing any simulated component, reloads
the complete hash-linked :class:`~rocell.application.context.SimulationContext`,
and records physical/calibration/collision omissions as declared gaps.  A gap
does not prevent software simulation; malformed or mutually inconsistent
configuration does.

No function in this module imports an optional hardware backend, opens a
device, creates an evidence directory, or issues an arm command.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell import __version__
from rocell.arm.connection import ArmConnectionProfile, load_arm_connection_profile
from rocell.calibration import CalibrationRegistry
from rocell.calibration.requirements import REQUIREMENTS
from rocell.rc03 import Capability, project_capabilities
from rocell.simulation import SyntheticFiducialObserver

from .collision_readiness import (
    CurrentCollisionReadinessReport,
    assess_current_collision_readiness,
)
from .context import SimulationContext, load_simulation_context


BOOTSTRAP_SCHEMA = "rocell.virtual_workcell_bootstrap.v1"
RUNTIME_SCHEMA_VERSION = 1
MAX_STARTUP_JSON_BYTES = 1_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_FIELDS = frozenset(
    {
        "schema_version",
        "runtime_id",
        "system_manifest",
        "camera_manifest",
        "default_mode",
        "live_hardware_enabled",
        "contact_enabled",
        "evidence_root",
        "calibration_manifest",
        "calibration_registry_root",
        "policy",
    }
)
_RUNTIME_POLICY = MappingProxyType(
    {
        "semantic_actions_only_at_user_boundary": True,
        "raw_robot_coordinates_allowed_at_user_boundary": False,
        "automatic_resume_after_fault": False,
        "automatic_camera_backend_fallback": False,
        "automatic_motion_retry": False,
    }
)
_GATE_FIELDS = frozenset(
    {"schema_version", "projection_id", "system_manifest_id", "capabilities"}
)
_GATE_ENTRY_FIELDS = frozenset({"allowed", "reason"})
_CALIBRATION_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "registry_id",
        "system_manifest_id",
        "active_build_id",
        "artifacts",
        "status",
    }
)


class BootstrapConfigurationError(ValueError):
    """A virtual-workcell startup source is malformed or inconsistent."""


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapConfigurationError(f"Duplicate startup JSON field {key!r}")
        result[key] = value
    return result


def _load_strict_json(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    """Read one bounded JSON object once and return its exact byte digest."""

    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_STARTUP_JSON_BYTES + 1)
    except OSError as exc:
        raise BootstrapConfigurationError(f"Could not read {label}: {path}") from exc
    if len(payload) > MAX_STARTUP_JSON_BYTES:
        raise BootstrapConfigurationError(
            f"{label} exceeds {MAX_STARTUP_JSON_BYTES} bytes"
        )
    digest = hashlib.sha256(payload).hexdigest()
    try:
        text = payload.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                BootstrapConfigurationError(
                    f"Nonfinite startup JSON constant {value!r} in {label}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, BootstrapConfigurationError) as exc:
        if isinstance(exc, BootstrapConfigurationError):
            raise
        raise BootstrapConfigurationError(f"Invalid strict JSON in {label}: {exc}") from exc
    if not isinstance(document, dict):
        raise BootstrapConfigurationError(f"{label} must contain a JSON object")
    return document, digest


def _exact_fields(document: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = set(document)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise BootstrapConfigurationError(
            f"{label} fields are not exact; missing={missing}, extra={extra}"
        )


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BootstrapConfigurationError(f"{label} must be non-empty text")
    return value.strip()


def _schema_one(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value != 1:
        raise BootstrapConfigurationError(f"{label} must be integer schema version 1")


def _resolve_runtime_path(
    workspace: Path,
    value: object,
    label: str,
    *,
    kind: str,
) -> tuple[str, Path]:
    relative = _text(value, label)
    raw = Path(relative)
    if raw.is_absolute():
        raise BootstrapConfigurationError(f"{label} must be workspace-relative")
    resolved = (workspace / raw).resolve()
    try:
        canonical = resolved.relative_to(workspace).as_posix()
    except ValueError as exc:
        raise BootstrapConfigurationError(f"{label} escapes the workspace") from exc
    if kind == "file" and not resolved.is_file():
        raise BootstrapConfigurationError(f"{label} file is missing: {canonical}")
    if kind == "directory" and not resolved.is_dir():
        raise BootstrapConfigurationError(f"{label} directory is missing: {canonical}")
    return canonical, resolved


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    """Strict zero-authority runtime configuration and contained source paths."""

    workspace: Path
    source_path: Path
    source_sha256: str
    runtime_id: str
    system_manifest_relative: str
    system_manifest_path: Path
    camera_manifest_relative: str
    camera_manifest_path: Path
    evidence_root_relative: str
    evidence_root_path: Path
    calibration_manifest_relative: str
    calibration_manifest_path: Path
    calibration_registry_root_relative: str
    calibration_registry_root_path: Path
    policy: Mapping[str, bool]

    def __post_init__(self) -> None:
        root = Path(self.workspace).resolve()
        object.__setattr__(self, "workspace", root)
        for name in (
            "source_path",
            "system_manifest_path",
            "camera_manifest_path",
            "evidence_root_path",
            "calibration_manifest_path",
            "calibration_registry_root_path",
        ):
            path = Path(getattr(self, name)).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise BootstrapConfigurationError(
                    f"RuntimePolicy.{name} escapes the workspace"
                ) from exc
            object.__setattr__(self, name, path)
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise BootstrapConfigurationError("Runtime policy SHA-256 is invalid")
        object.__setattr__(self, "runtime_id", _text(self.runtime_id, "runtime_id"))
        frozen_policy = dict(self.policy)
        if frozen_policy != dict(_RUNTIME_POLICY):
            raise BootstrapConfigurationError("Runtime safety policy changed after loading")
        object.__setattr__(self, "policy", MappingProxyType(frozen_policy))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "runtime_id": self.runtime_id,
            "source_path": self.source_path.relative_to(self.workspace).as_posix(),
            "source_sha256": self.source_sha256,
            "default_mode": "simulation",
            "live_hardware_enabled": False,
            "contact_enabled": False,
            "system_manifest": self.system_manifest_relative,
            "camera_manifest": self.camera_manifest_relative,
            "evidence_root": self.evidence_root_relative,
            "calibration_manifest": self.calibration_manifest_relative,
            "calibration_registry_root": self.calibration_registry_root_relative,
            "policy": dict(sorted(self.policy.items())),
        }


def load_runtime_policy(
    workspace: Path,
    runtime_path: Path | None = None,
) -> RuntimePolicy:
    """Load the simulation-only runtime policy without constructing adapters."""

    root = Path(workspace).resolve()
    if not root.is_dir():
        raise BootstrapConfigurationError(f"Workspace directory is missing: {root}")
    if runtime_path is None:
        selected = (root / "software/config/runtime.json").resolve()
    else:
        requested = Path(runtime_path)
        selected = (
            requested if requested.is_absolute() else root / requested
        ).resolve()
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise BootstrapConfigurationError(
            "Runtime configuration must be beneath the workspace"
        ) from exc
    document, digest = _load_strict_json(selected, label="runtime configuration")
    _exact_fields(document, _RUNTIME_FIELDS, "runtime configuration")
    _schema_one(document.get("schema_version"), "runtime schema_version")
    if document.get("default_mode") != "simulation":
        raise BootstrapConfigurationError("Runtime default_mode must be simulation")
    if document.get("live_hardware_enabled") is not False:
        raise BootstrapConfigurationError("Virtual runtime must disable live hardware")
    if document.get("contact_enabled") is not False:
        raise BootstrapConfigurationError("Virtual runtime must disable contact")
    raw_policy = document.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise BootstrapConfigurationError("runtime.policy must be an object")
    if set(raw_policy) != set(_RUNTIME_POLICY):
        missing = sorted(set(_RUNTIME_POLICY) - set(raw_policy))
        extra = sorted(set(raw_policy) - set(_RUNTIME_POLICY))
        raise BootstrapConfigurationError(
            f"runtime.policy fields are not exact; missing={missing}, extra={extra}"
        )
    for key, required in _RUNTIME_POLICY.items():
        if raw_policy.get(key) is not required:
            raise BootstrapConfigurationError(
                f"Runtime safety policy {key} must remain {required}"
            )

    manifest_relative, manifest_path = _resolve_runtime_path(
        root, document.get("system_manifest"), "system_manifest", kind="file"
    )
    camera_relative, camera_path = _resolve_runtime_path(
        root, document.get("camera_manifest"), "camera_manifest", kind="file"
    )
    evidence_relative, evidence_path = _resolve_runtime_path(
        root, document.get("evidence_root"), "evidence_root", kind="directory"
    )
    calibration_relative, calibration_path = _resolve_runtime_path(
        root,
        document.get("calibration_manifest"),
        "calibration_manifest",
        kind="file",
    )
    registry_relative, registry_path = _resolve_runtime_path(
        root,
        document.get("calibration_registry_root"),
        "calibration_registry_root",
        kind="directory",
    )
    return RuntimePolicy(
        workspace=root,
        source_path=selected,
        source_sha256=digest,
        runtime_id=_text(document.get("runtime_id"), "runtime_id"),
        system_manifest_relative=manifest_relative,
        system_manifest_path=manifest_path,
        camera_manifest_relative=camera_relative,
        camera_manifest_path=camera_path,
        evidence_root_relative=evidence_relative,
        evidence_root_path=evidence_path,
        calibration_manifest_relative=calibration_relative,
        calibration_manifest_path=calibration_path,
        calibration_registry_root_relative=registry_relative,
        calibration_registry_root_path=registry_path,
        policy={key: bool(raw_policy[key]) for key in _RUNTIME_POLICY},
    )


@dataclass(frozen=True, slots=True)
class GateProjectionEvidence:
    projection_id: str
    source_relative: str
    source_sha256: str
    allowed: tuple[tuple[str, bool], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "source": self.source_relative,
            "source_sha256": self.source_sha256,
            "allowed": dict(self.allowed),
            "exact_capability_set_verified": True,
            "derived_projection_match": True,
        }


def _load_gate_projection(
    policy: RuntimePolicy,
    context: SimulationContext,
) -> GateProjectionEvidence:
    path = policy.workspace / "software/config/gate_projection.json"
    document, digest = _load_strict_json(path, label="gate projection")
    _exact_fields(document, _GATE_FIELDS, "gate projection")
    _schema_one(document.get("schema_version"), "gate projection schema_version")
    if document.get("system_manifest_id") != context.snapshot.manifest_id:
        raise BootstrapConfigurationError(
            "Gate projection references a different system manifest"
        )
    raw_capabilities = document.get("capabilities")
    if not isinstance(raw_capabilities, Mapping):
        raise BootstrapConfigurationError("gate projection capabilities must be an object")
    expected_ids = {capability.value for capability in Capability}
    if set(raw_capabilities) != expected_ids:
        missing = sorted(expected_ids - set(raw_capabilities))
        extra = sorted(set(raw_capabilities) - expected_ids)
        raise BootstrapConfigurationError(
            f"Gate projection capability set mismatch; missing={missing}, extra={extra}"
        )
    derived = project_capabilities(context.snapshot)
    allowed: list[tuple[str, bool]] = []
    for capability in sorted(Capability, key=lambda item: item.value):
        raw_entry = raw_capabilities[capability.value]
        if not isinstance(raw_entry, Mapping):
            raise BootstrapConfigurationError(
                f"Gate projection {capability.value} must be an object"
            )
        _exact_fields(raw_entry, _GATE_ENTRY_FIELDS, f"gate projection {capability.value}")
        configured_allowed = raw_entry.get("allowed")
        if not isinstance(configured_allowed, bool):
            raise BootstrapConfigurationError(
                f"Gate projection {capability.value}.allowed must be boolean"
            )
        _text(raw_entry.get("reason"), f"gate projection {capability.value}.reason")
        if configured_allowed is not derived[capability].allowed:
            raise BootstrapConfigurationError(
                f"Gate projection for {capability.value} disagrees with derived capability"
            )
        allowed.append((capability.value, configured_allowed))
    return GateProjectionEvidence(
        projection_id=_text(document.get("projection_id"), "projection_id"),
        source_relative=path.relative_to(policy.workspace).as_posix(),
        source_sha256=digest,
        allowed=tuple(allowed),
    )


@dataclass(frozen=True, slots=True)
class CalibrationInventory:
    registry_id: str
    manifest_relative: str
    manifest_sha256: str
    registry_root_relative: str
    index_sha256: str | None
    current_artifacts: tuple[tuple[str, str], ...]
    artifact_file_sha256: tuple[tuple[str, str], ...]
    missing_requirement_ids: tuple[str, ...]
    status: str

    @property
    def physical_calibration_complete(self) -> bool:
        return not self.missing_requirement_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "manifest": self.manifest_relative,
            "manifest_sha256": self.manifest_sha256,
            "registry_root": self.registry_root_relative,
            "index_sha256": self.index_sha256,
            "current_artifacts": dict(self.current_artifacts),
            "artifact_file_sha256": dict(self.artifact_file_sha256),
            "missing_requirement_ids": list(self.missing_requirement_ids),
            "physical_calibration_complete": self.physical_calibration_complete,
            "status": self.status,
            "structural_inventory_valid": True,
        }


def _load_calibration_inventory(
    policy: RuntimePolicy,
    context: SimulationContext,
) -> CalibrationInventory:
    manifest, manifest_digest = _load_strict_json(
        policy.calibration_manifest_path,
        label="calibration manifest",
    )
    _exact_fields(manifest, _CALIBRATION_MANIFEST_FIELDS, "calibration manifest")
    _schema_one(manifest.get("schema_version"), "calibration manifest schema_version")
    registry_id = _text(manifest.get("registry_id"), "calibration registry_id")
    if manifest.get("system_manifest_id") != context.snapshot.manifest_id:
        raise BootstrapConfigurationError(
            "Calibration manifest references a different system manifest"
        )
    expected_build_id = context.snapshot.active_build_id
    configured_build_id = manifest.get("active_build_id")
    if configured_build_id is not None and not isinstance(configured_build_id, str):
        raise BootstrapConfigurationError(
            "Calibration manifest active_build_id must be text or null"
        )
    if configured_build_id != expected_build_id:
        raise BootstrapConfigurationError(
            "Calibration manifest references a different active build"
        )
    raw_manifest_artifacts = manifest.get("artifacts")
    if not isinstance(raw_manifest_artifacts, Mapping):
        raise BootstrapConfigurationError("Calibration manifest artifacts must be an object")
    manifest_artifacts: dict[str, str] = {}
    for artifact_id, digest in raw_manifest_artifacts.items():
        identifier = _text(artifact_id, "calibration artifact id")
        if "/" in identifier or "\\" in identifier or identifier in {".", ".."}:
            raise BootstrapConfigurationError("Calibration artifact id must not be a path")
        digest_text = _text(digest, f"calibration artifact {identifier} digest").lower()
        if _SHA256.fullmatch(digest_text) is None:
            raise BootstrapConfigurationError(
                f"Calibration artifact {identifier} digest must be lowercase SHA-256"
            )
        manifest_artifacts[identifier] = digest_text

    root = policy.calibration_registry_root_path
    index_path = root / "index.json"
    index_digest: str | None = None
    current: dict[str, str] = {}
    if index_path.exists():
        index, index_digest = _load_strict_json(index_path, label="calibration index")
        _exact_fields(index, frozenset({"schema", "current"}), "calibration index")
        if index.get("schema") != CalibrationRegistry.INDEX_SCHEMA:
            raise BootstrapConfigurationError("Unsupported calibration index schema")
        raw_current = index.get("current")
        if not isinstance(raw_current, Mapping):
            raise BootstrapConfigurationError("Calibration index current must be an object")
        for artifact_id, digest in raw_current.items():
            identifier = _text(artifact_id, "calibration current artifact id")
            digest_text = _text(
                digest, f"calibration current {identifier} digest"
            ).lower()
            if _SHA256.fullmatch(digest_text) is None:
                raise BootstrapConfigurationError(
                    f"Calibration current {identifier} digest must be lowercase SHA-256"
                )
            current[identifier] = digest_text
    if current != manifest_artifacts:
        raise BootstrapConfigurationError(
            "Calibration manifest artifacts differ from the content-addressed registry index"
        )

    registry = CalibrationRegistry(root)
    artifact_files: list[tuple[str, str]] = []
    for artifact_id, digest in sorted(current.items()):
        try:
            artifact = registry.get_current(artifact_id)
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            raise BootstrapConfigurationError(
                f"Calibration artifact {artifact_id} failed integrity validation: {exc}"
            ) from exc
        if artifact is None or artifact.content_hash != digest:
            raise BootstrapConfigurationError(
                f"Calibration artifact {artifact_id} is missing or hash-inconsistent"
            )
        artifact_path = root / "artifacts" / artifact_id / f"{digest}.json"
        try:
            artifact_path.resolve().relative_to(root)
        except ValueError as exc:
            raise BootstrapConfigurationError(
                f"Calibration artifact {artifact_id} escapes its registry root"
            ) from exc
        _, file_digest = _load_strict_json(
            artifact_path,
            label=f"calibration artifact {artifact_id}",
        )
        artifact_files.append((artifact_id, file_digest))

    status = _text(manifest.get("status"), "calibration manifest status")
    if not current and status != "EMPTY_PHYSICAL_CALIBRATION_BLOCKED":
        raise BootstrapConfigurationError(
            "An empty calibration inventory must retain its blocked status"
        )
    missing = tuple(sorted(set(REQUIREMENTS) - set(current)))
    return CalibrationInventory(
        registry_id=registry_id,
        manifest_relative=policy.calibration_manifest_relative,
        manifest_sha256=manifest_digest,
        registry_root_relative=policy.calibration_registry_root_relative,
        index_sha256=index_digest,
        current_artifacts=tuple(sorted(current.items())),
        artifact_file_sha256=tuple(artifact_files),
        missing_requirement_ids=missing,
        status=status,
    )


@dataclass(frozen=True, slots=True)
class SyntheticOverviewHealth:
    scenario_id: str
    tag_count: int
    visible_tag_count: int

    @property
    def healthy(self) -> bool:
        return self.tag_count > 0 and self.visible_tag_count == self.tag_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_is_arm_mounted_camera": False,
            "tag_count": self.tag_count,
            "visible_tag_count": self.visible_tag_count,
            "healthy": self.healthy,
            "physical_camera_accessed": False,
        }


def _synthetic_overview_health(context: SimulationContext) -> SyntheticOverviewHealth:
    fixture = context.scenario.overview
    observations = SyntheticFiducialObserver(
        fixture.camera,
        fixture.camera_T_board,
    ).observe_scene(context.scene)
    health = SyntheticOverviewHealth(
        scenario_id=fixture.scenario_id,
        tag_count=len(observations),
        visible_tag_count=sum(observation.visible for observation in observations),
    )
    if not health.healthy:
        raise BootstrapConfigurationError(
            "Synthetic overview fixture cannot observe every locked fiducial"
        )
    return health


@dataclass(frozen=True, slots=True)
class BootstrapCheck:
    check_id: str
    status: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _text(self.check_id, "bootstrap check id"))
        if self.status not in {"PASS", "DECLARED_GAP"}:
            raise BootstrapConfigurationError("Bootstrap check status is invalid")
        object.__setattr__(self, "detail", _text(self.detail, "bootstrap check detail"))

    def to_dict(self) -> dict[str, str]:
        return {"id": self.check_id, "status": self.status, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class VirtualWorkcellBootstrap:
    """Fully validated virtual startup state with permanently zero authority."""

    workspace: Path
    runtime: RuntimePolicy
    context: SimulationContext
    gate_projection: GateProjectionEvidence
    calibration_inventory: CalibrationInventory
    arm_connection: ArmConnectionProfile
    arm_connection_relative: str
    arm_connection_sha256: str
    overview_health: SyntheticOverviewHealth
    collision_readiness: CurrentCollisionReadinessReport
    checks: tuple[BootstrapCheck, ...]

    def __post_init__(self) -> None:
        root = Path(self.workspace).resolve()
        object.__setattr__(self, "workspace", root)
        if self.runtime.workspace != root or self.context.workspace != root:
            raise BootstrapConfigurationError(
                "Bootstrap components must share one resolved workspace"
            )
        if _SHA256.fullmatch(self.arm_connection_sha256) is None:
            raise BootstrapConfigurationError("Arm connection SHA-256 is invalid")
        checks = tuple(self.checks)
        if not checks or len({check.check_id for check in checks}) != len(checks):
            raise BootstrapConfigurationError(
                "Bootstrap checks must be non-empty with unique IDs"
            )
        object.__setattr__(self, "checks", checks)

    @property
    def simulation_ready(self) -> bool:
        return self.overview_health.healthy and all(
            check.status in {"PASS", "DECLARED_GAP"} for check in self.checks
        )

    @property
    def status(self) -> str:
        return "READY_SIMULATION_ONLY_WITH_DECLARED_GAPS"

    def _report_without_hash(self) -> dict[str, Any]:
        snapshot = self.context.snapshot
        bundle = self.context.bundle_lock
        scene_hashes = dict(sorted(self.context.scene.source_hashes.items()))
        return {
            "schema": BOOTSTRAP_SCHEMA,
            "runtime_version": __version__,
            "status": self.status,
            "simulation_ready": self.simulation_ready,
            "runtime": self.runtime.to_dict(),
            "verified_context": {
                "manifest_id": snapshot.manifest_id,
                "manifest_sha256": snapshot.manifest_sha256,
                "snapshot_hash": snapshot.snapshot_hash,
                "design_revision": snapshot.design_revision,
                "active_build_id": snapshot.active_build_id,
                "bundle_id": bundle.bundle_id,
                "bundle_lock_sha256": bundle.source_lock_sha256,
                "bundle_artifacts": {
                    key: artifact.sha256
                    for key, artifact in sorted(bundle.artifacts.items())
                },
                "scene_source_hashes": scene_hashes,
                "target_profile_sha256": self.context.targets.content_sha256,
                "alignment_status": self.context.alignment.status,
                "alignment_report_hash": self.context.alignment.report_hash,
            },
            "gate_projection": self.gate_projection.to_dict(),
            "calibration_inventory": self.calibration_inventory.to_dict(),
            "arm_connection": {
                "source": self.arm_connection_relative,
                "source_sha256": self.arm_connection_sha256,
                "profile_id": self.arm_connection.profile_id,
                "model": self.arm_connection.model,
                "commissioned": self.arm_connection.commissioned,
                "auto_connect": self.arm_connection.auto_connect,
                "auto_initialize": self.arm_connection.auto_initialize,
                "hardware_accessed": False,
            },
            "synthetic_overview": self.overview_health.to_dict(),
            "collision_readiness": {
                "status": self.collision_readiness.status,
                "report_hash": self.collision_readiness.report_hash,
                "diagnostic_ready": (
                    self.collision_readiness.geometry_audit.diagnostic_ready
                ),
                "missing_required_body_ids": list(
                    self.collision_readiness.missing_required_body_ids
                ),
                "unknown_required_body_ids": list(
                    self.collision_readiness.unknown_required_body_ids
                ),
            },
            "physical_holds": {
                "snapshot_hard_blockers": list(snapshot.hard_blockers),
                "safe_to_power_robot": snapshot.safe_to_power_robot,
                "contact_enabled": snapshot.contact_enabled,
                "missing_calibrations": list(
                    self.calibration_inventory.missing_requirement_ids
                ),
                "collision_diagnostic_ready": (
                    self.collision_readiness.geometry_audit.diagnostic_ready
                ),
                "eye_on_arm_installation_simulated": False,
            },
            "checks": [check.to_dict() for check in self.checks],
            "authority": {
                "simulation_only": True,
                "execution_authorized": False,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "can_release_physical_gates": False,
                "safe_to_power_robot_conferred": False,
                "contact_enabled_conferred": False,
            },
        }

    @property
    def bootstrap_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self._report_without_hash(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self._report_without_hash(), "bootstrap_hash": self.bootstrap_hash}


def _verify_scene_snapshot_hashes(context: SimulationContext) -> None:
    mismatches: list[str] = []
    for relative, actual in sorted(context.scene.source_hashes.items()):
        expected = context.snapshot.source_hashes.get(relative)
        if expected != actual:
            mismatches.append(
                f"{relative}: snapshot={expected!r}, scene={actual!r}"
            )
    if mismatches:
        raise BootstrapConfigurationError(
            "Scene bytes differ from the verified RC03 snapshot: " + "; ".join(mismatches)
        )


def bootstrap_virtual_workcell(
    workspace: Path,
    runtime_path: Path | None = None,
) -> VirtualWorkcellBootstrap:
    """Validate and assemble one zero-I/O virtual workcell startup snapshot."""

    runtime = load_runtime_policy(workspace, runtime_path)
    try:
        context = load_simulation_context(
            runtime.workspace,
            runtime.system_manifest_path,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise BootstrapConfigurationError(
            f"Could not load the coherent simulation context: {exc}"
        ) from exc
    _verify_scene_snapshot_hashes(context)
    locked_camera = context.bundle_lock.artifact("camera_manifest").path
    if runtime.camera_manifest_path != locked_camera:
        raise BootstrapConfigurationError(
            "Runtime camera manifest differs from the locked simulation camera manifest"
        )

    gate_projection = _load_gate_projection(runtime, context)
    calibration_inventory = _load_calibration_inventory(runtime, context)
    arm_path = runtime.workspace / "software/config/arm_connection.json"
    arm_document, arm_digest = _load_strict_json(
        arm_path,
        label="arm connection profile",
    )
    # The dedicated loader repeats the parse deliberately: it owns the detailed
    # serial-identity contract, while the bounded strict read above supplies the
    # exact startup digest and rejects an oversized source first.
    del arm_document
    try:
        arm_connection = load_arm_connection_profile(runtime.workspace, arm_path)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise BootstrapConfigurationError(
            f"Arm connection profile is invalid: {exc}"
        ) from exc
    if arm_connection.model != "Waveshare RoArm-M3 Pro":
        raise BootstrapConfigurationError(
            "Arm connection profile does not identify the selected RoArm-M3 Pro"
        )
    overview = _synthetic_overview_health(context)
    try:
        collision = assess_current_collision_readiness(context)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise BootstrapConfigurationError(
            f"Collision readiness inventory could not be constructed: {exc}"
        ) from exc

    checks = (
        BootstrapCheck("runtime_policy", "PASS", "strict simulation-only policy loaded"),
        BootstrapCheck("simulation_context", "PASS", "complete hash-linked context loaded"),
        BootstrapCheck(
            "scene_snapshot_hashes",
            "PASS",
            "scene layout and tag-map bytes match the verified RC03 snapshot",
        ),
        BootstrapCheck(
            "gate_projection",
            "PASS",
            "configured capability set exactly matches derived capabilities",
        ),
        BootstrapCheck(
            "calibration_inventory",
            "PASS",
            "calibration manifest and content-addressed inventory are structurally valid",
        ),
        BootstrapCheck(
            "physical_calibration",
            (
                "PASS"
                if calibration_inventory.physical_calibration_complete
                else "DECLARED_GAP"
            ),
            (
                "all calibration families are present"
                if calibration_inventory.physical_calibration_complete
                else f"{len(calibration_inventory.missing_requirement_ids)} physical calibration families are absent"
            ),
        ),
        BootstrapCheck(
            "arm_connection_nonopening",
            "PASS",
            "arm profile parsed without importing or opening a serial backend",
        ),
        BootstrapCheck(
            "synthetic_overview",
            "PASS",
            f"{overview.visible_tag_count}/{overview.tag_count} locked tags visible",
        ),
        BootstrapCheck(
            "collision_geometry",
            "PASS" if collision.geometry_audit.diagnostic_ready else "DECLARED_GAP",
            collision.status,
        ),
        BootstrapCheck(
            "physical_release",
            (
                "PASS"
                if context.snapshot.safe_to_power_robot
                and context.snapshot.contact_enabled
                else "DECLARED_GAP"
            ),
            (
                "physical power and contact state are released"
                if context.snapshot.safe_to_power_robot
                and context.snapshot.contact_enabled
                else "physical power/contact authority remains outside virtual startup"
            ),
        ),
    )
    return VirtualWorkcellBootstrap(
        workspace=runtime.workspace,
        runtime=runtime,
        context=context,
        gate_projection=gate_projection,
        calibration_inventory=calibration_inventory,
        arm_connection=arm_connection,
        arm_connection_relative=arm_path.relative_to(runtime.workspace).as_posix(),
        arm_connection_sha256=arm_digest,
        overview_health=overview,
        collision_readiness=collision,
        checks=checks,
    )


def revalidate_virtual_workcell(bootstrap: VirtualWorkcellBootstrap) -> None:
    """Fail closed if any startup source or in-memory report has changed."""

    if not isinstance(bootstrap, VirtualWorkcellBootstrap):
        raise TypeError("bootstrap must be a VirtualWorkcellBootstrap")
    try:
        verified = bootstrap_virtual_workcell(
            bootstrap.workspace,
            bootstrap.runtime.source_path,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise BootstrapConfigurationError(
            f"Could not revalidate virtual workcell startup: {exc}"
        ) from exc
    if bootstrap.runtime.source_path != verified.runtime.source_path:
        raise BootstrapConfigurationError("Runtime source path changed after bootstrap")
    if bootstrap.to_dict() != verified.to_dict():
        raise BootstrapConfigurationError(
            "Virtual workcell startup differs from freshly verified sources"
        )


__all__ = [
    "BOOTSTRAP_SCHEMA",
    "BootstrapCheck",
    "BootstrapConfigurationError",
    "CalibrationInventory",
    "GateProjectionEvidence",
    "RuntimePolicy",
    "SyntheticOverviewHealth",
    "VirtualWorkcellBootstrap",
    "bootstrap_virtual_workcell",
    "load_runtime_policy",
    "revalidate_virtual_workcell",
]
