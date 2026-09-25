"""Zero-authority rehearsal for the static-overhead Phase-1 calibration graph.

The physical registry is only read.  Separately, deterministic ``NOMINAL_ONLY``
artifacts are built in memory and passed through the production
``CalibrationRegistry.assess`` logic.  Each parent-artifact and external-source
edge is then invalidated independently.  This proves dependency behavior before
hardware exists without manufacturing calibration evidence or enabling robot
execution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, TYPE_CHECKING

from rocell.calibration import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
    CalibrationRegistry,
)
from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_AUTHORITY,
    STATIC_OVERHEAD_PHASE1_GRAPH,
)
from rocell.typing import development_keyboard_profile, development_phone_profile

from .context import SimulationContext, revalidate_simulation_context

if TYPE_CHECKING:
    from .static_simulation_context import StaticSimulationContext


STATIC_PHASE1_CALIBRATION_REHEARSAL_SCHEMA = (
    "rocell.static_phase1_calibration_rehearsal.v1"
)
STATIC_PHASE1_SYNTHETIC_MANIFEST_ID = "STATIC-PHASE1-SYNTHETIC-NO-FREEZE"
STATIC_PHASE1_SYNTHETIC_BUILD_ID = "STATIC-PHASE1-SYNTHETIC-NO-BUILD"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GRAPH_CONTEXT_DEPENDENCY = "static_phase1_requirement_graph"
_PHYSICAL_REGISTRY_RELATIVE = Path("software/calibrations")
_SOURCE_PATHS: Mapping[str, Path] = MappingProxyType(
    {
        "camera_architecture_plan": Path(
            "software/config/camera_architecture_plan.json"
        ),
        "b0477_catalog_profile": Path(
            "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
        ),
        "static_camera_support": Path(
            "hardware/static_overhead_camera/config/support_design.json"
        ),
    }
)


class StaticPhase1CalibrationError(ValueError):
    """The synthetic graph rehearsal could not be completed safely."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _validate_hash(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise StaticPhase1CalibrationError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _sha256_workspace_file(workspace: Path, relative: Path) -> str:
    """Hash one required source without following it outside the workspace."""

    root = workspace.resolve()
    unresolved = root / relative
    try:
        resolved = unresolved.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise StaticPhase1CalibrationError(
            f"Required static Phase-1 source is unavailable: {relative.as_posix()}"
        ) from exc
    if not resolved.is_file():
        raise StaticPhase1CalibrationError(
            f"Required static Phase-1 source is not a file: {relative.as_posix()}"
        )
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def static_phase1_context_hashes(
    context: SimulationContext,
) -> Mapping[str, str]:
    """Derive every source hash named by the selected Phase-1 graph.

    The existing simulation-context validation is intentionally retained: it
    keeps the historical frozen model coherent.  The three additive static
    camera sources are then hashed directly because Freeze 009 does not and
    must not claim to bind the new architecture.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)

    hashes = {
        "system_manifest": context.snapshot.manifest_sha256,
        "kinematic_model": context.scenario.model_sha256,
        "workcell_layout": context.scene.source_hashes[
            "config/workcell_layout.json"
        ],
        "apriltag_map": context.scene.source_hashes[
            "fiducials/apriltag_map.json"
        ],
        "target_catalog": context.targets.content_sha256,
        "keyboard_semantic_profile": (
            development_keyboard_profile().semantic_content_sha256
        ),
        "phone_semantic_profile": development_phone_profile().semantic_content_sha256,
        **{
            source_id: _sha256_workspace_file(context.workspace, relative)
            for source_id, relative in _SOURCE_PATHS.items()
        },
    }
    required = set(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids)
    if set(hashes) != required:
        missing = tuple(sorted(required - set(hashes)))
        unexpected = tuple(sorted(set(hashes) - required))
        raise StaticPhase1CalibrationError(
            "Static Phase-1 context binding mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return MappingProxyType(
        {key: _validate_hash(value, key) for key, value in sorted(hashes.items())}
    )


class _InMemoryCalibrationRegistry(CalibrationRegistry):
    """Read-only adapter that reuses production assessment semantics."""

    def __init__(self, artifacts: Mapping[str, CalibrationArtifact]) -> None:
        # Deliberately do not create a filesystem root.  ``assess`` only calls
        # ``get_current``, which this adapter serves from immutable memory.
        self._memory_artifacts = MappingProxyType(dict(artifacts))

    def get_current(self, artifact_id: str) -> CalibrationArtifact | None:
        return self._memory_artifacts.get(artifact_id)

    def install(self, artifact: CalibrationArtifact) -> str:
        raise RuntimeError("Synthetic calibration registry is read-only")


@dataclass(frozen=True, slots=True)
class StaticPhase1StalenessProbe:
    """Result of changing exactly one upstream hash."""

    edge_kind: str
    upstream_id: str
    downstream_id: str
    expected_reason: str
    observed_stale_reasons: tuple[str, ...]
    detected: bool

    def __post_init__(self) -> None:
        if self.edge_kind not in {"PARENT_ARTIFACT", "CONTEXT_SOURCE"}:
            raise StaticPhase1CalibrationError(
                f"Unsupported staleness edge kind {self.edge_kind!r}"
            )
        if not self.upstream_id or not self.downstream_id:
            raise StaticPhase1CalibrationError("Staleness edge IDs must be non-empty")
        reason_prefix = (
            "STALE_PARENT_CALIBRATION"
            if self.edge_kind == "PARENT_ARTIFACT"
            else "STALE_CALIBRATION_DEPENDENCY"
        )
        exact_expected = (
            f"{reason_prefix}:{self.downstream_id}:{self.upstream_id}"
        )
        if self.expected_reason != exact_expected:
            raise StaticPhase1CalibrationError(
                "Staleness probe expected reason does not describe its edge"
            )
        reasons = tuple(self.observed_stale_reasons)
        object.__setattr__(self, "observed_stale_reasons", reasons)
        if self.detected != (reasons == (self.expected_reason,)):
            raise StaticPhase1CalibrationError(
                "Staleness probe detected flag differs from its exact observed reason"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_kind": self.edge_kind,
            "upstream_id": self.upstream_id,
            "downstream_id": self.downstream_id,
            "expected_reason": self.expected_reason,
            "observed_stale_reasons": list(self.observed_stale_reasons),
            "detected": self.detected,
            "hardware_accessed": False,
            "execution_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class StaticPhase1SyntheticClosure:
    """Nominal-only artifacts plus exhaustive staleness-edge evidence."""

    context_hashes: tuple[tuple[str, str], ...]
    artifacts: tuple[CalibrationArtifact, ...]
    baseline_assessments: tuple[ArtifactAssessment, ...]
    staleness_probes: tuple[StaticPhase1StalenessProbe, ...]

    def __post_init__(self) -> None:
        normalized_context = _normalized_context_hashes(dict(self.context_hashes))
        if tuple(normalized_context.items()) != self.context_hashes:
            raise StaticPhase1CalibrationError(
                "Synthetic context hashes must be unique and canonically ordered"
            )
        expected_order = STATIC_OVERHEAD_PHASE1_GRAPH.ordered_requirements
        if tuple(artifact.artifact_id for artifact in self.artifacts) != expected_order:
            raise StaticPhase1CalibrationError(
                "Synthetic artifacts must follow the complete graph order"
            )
        if tuple(row.artifact_id for row in self.baseline_assessments) != expected_order:
            raise StaticPhase1CalibrationError(
                "Baseline assessments must follow the complete graph order"
            )
        if any(artifact.state is not ArtifactState.NOMINAL_ONLY for artifact in self.artifacts):
            raise StaticPhase1CalibrationError(
                "Synthetic artifacts must remain NOMINAL_ONLY"
            )
        artifacts = {row.artifact_id: row for row in self.artifacts}
        for artifact in self.artifacts:
            requirement = STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                artifact.artifact_id
            ]
            if (
                artifact.version != 1
                or artifact.manifest_id != STATIC_PHASE1_SYNTHETIC_MANIFEST_ID
                or artifact.active_build_id != STATIC_PHASE1_SYNTHETIC_BUILD_ID
            ):
                raise StaticPhase1CalibrationError(
                    f"{artifact.artifact_id} has a noncanonical synthetic identity"
                )
            expected_parents = {
                parent: artifacts[parent].content_hash
                for parent in requirement.prerequisites
            }
            if dict(artifact.parent_artifact_hashes) != expected_parents:
                raise StaticPhase1CalibrationError(
                    f"{artifact.artifact_id} does not bind every declared parent"
                )
            expected_dependencies = {
                _GRAPH_CONTEXT_DEPENDENCY: (
                    STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash
                ),
                **{
                    dependency: normalized_context[dependency]
                    for dependency in requirement.context_dependencies
                },
            }
            if dict(artifact.dependency_hashes) != expected_dependencies:
                raise StaticPhase1CalibrationError(
                    f"{artifact.artifact_id} has incomplete source bindings"
                )
            if (
                artifact.payload.get("synthetic") is not True
                or artifact.payload.get("physical_measurements_present") is not False
                or artifact.payload.get("execution_authorized") is not False
                or artifact.payload.get("physical_release_effect") != "NONE"
            ):
                raise StaticPhase1CalibrationError(
                    f"{artifact.artifact_id} synthetic authority boundary is invalid"
                )
        for artifact, assessment in zip(
            self.artifacts, self.baseline_assessments
        ):
            if (
                assessment.artifact_hash != artifact.content_hash
                or assessment.state is not ArtifactState.NOMINAL_ONLY
                or assessment.reasons
                != (
                    "CALIBRATION_STATE:"
                    f"{artifact.artifact_id}:NOMINAL_ONLY",
                )
            ):
                raise StaticPhase1CalibrationError(
                    f"{artifact.artifact_id} baseline assessment is not nominal-only"
                )

    @property
    def artifact_hashes(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (artifact.artifact_id, artifact.content_hash) for artifact in self.artifacts
        )

    @property
    def baseline_parent_bindings_coherent(self) -> bool:
        stale_prefixes = (
            "STALE_CALIBRATION_DEPENDENCY:",
            "STALE_PARENT_CALIBRATION:",
        )
        return all(
            not any(reason.startswith(stale_prefixes) for reason in row.reasons)
            for row in self.baseline_assessments
        )

    @property
    def all_edges_exercised(self) -> bool:
        graph = STATIC_OVERHEAD_PHASE1_GRAPH
        expected = {
            ("PARENT_ARTIFACT", parent, child)
            for parent, child in graph.parent_edges
        }
        expected.update(
            (
                "CONTEXT_SOURCE",
                dependency,
                artifact_id,
            )
            for artifact_id in graph.ordered_requirements
            for dependency in (
                _GRAPH_CONTEXT_DEPENDENCY,
                *graph.requirements[artifact_id].context_dependencies,
            )
        )
        observed = tuple(
            (probe.edge_kind, probe.upstream_id, probe.downstream_id)
            for probe in self.staleness_probes
        )
        return (
            len(observed) == len(set(observed))
            and set(observed) == expected
            and all(probe.detected for probe in self.staleness_probes)
        )

    @property
    def simulation_graph_verified(self) -> bool:
        return self.baseline_parent_bindings_coherent and self.all_edges_exercised

    def to_dict(self) -> dict[str, Any]:
        assessments = {row.artifact_id: row for row in self.baseline_assessments}
        return {
            "status": (
                "SYNTHETIC_GRAPH_VERIFIED_PHYSICAL_EVIDENCE_NOT_CREATED"
                if self.simulation_graph_verified
                else "SYNTHETIC_GRAPH_REHEARSAL_FAILED"
            ),
            "authority": STATIC_OVERHEAD_PHASE1_AUTHORITY,
            "context_hashes": dict(self.context_hashes),
            "artifacts": [
                {
                    "artifact_id": artifact.artifact_id,
                    "requirement_artifact_schema": (
                        STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                            artifact.artifact_id
                        ].artifact_schema
                    ),
                    "calibration_container_schema": artifact.schema,
                    "version": artifact.version,
                    "state": artifact.state.value,
                    "artifact_hash": artifact.content_hash,
                    "dependency_hashes": dict(artifact.dependency_hashes),
                    "parent_artifact_hashes": dict(
                        artifact.parent_artifact_hashes
                    ),
                    "baseline_reasons": list(
                        assessments[artifact.artifact_id].reasons
                    ),
                    "physical_evidence": False,
                }
                for artifact in self.artifacts
            ],
            "baseline_parent_bindings_coherent": (
                self.baseline_parent_bindings_coherent
            ),
            "staleness_probes": [probe.to_dict() for probe in self.staleness_probes],
            "all_edges_exercised": self.all_edges_exercised,
            "simulation_graph_verified": self.simulation_graph_verified,
            "physical_artifacts_created": False,
            "physical_registry_written": False,
            "hardware_accessed": False,
            "robot_commands_sent": 0,
            "execution_authorized": False,
            "physical_release_effect": "NONE",
        }

    @property
    def closure_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class StaticPhase1DeviceClosure:
    device: str
    terminals: tuple[str, ...]
    ordered_requirements: tuple[str, ...]
    physical_assessments: tuple[ArtifactAssessment, ...]

    @property
    def physical_artifacts_all_valid(self) -> bool:
        return bool(self.physical_assessments) and all(
            row.valid for row in self.physical_assessments
        )

    def to_dict(self) -> dict[str, Any]:
        by_id = {row.artifact_id: row for row in self.physical_assessments}
        return {
            "device": self.device,
            "terminals": list(self.terminals),
            "ordered_requirements": [
                {
                    **STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                        artifact_id
                    ].to_dict(),
                    "physical_assessment": {
                        "state": by_id[artifact_id].state.value,
                        "valid": by_id[artifact_id].valid,
                        "artifact_hash": by_id[artifact_id].artifact_hash,
                        "reasons": list(by_id[artifact_id].reasons),
                    },
                }
                for artifact_id in self.ordered_requirements
            ],
            "physical_artifacts_all_valid": self.physical_artifacts_all_valid,
        }


@dataclass(frozen=True, slots=True)
class StaticPhase1CalibrationRehearsalReport:
    manifest_id: str
    active_build_id: str | None
    physical_registry_index_present: bool
    physical_assessments: tuple[ArtifactAssessment, ...]
    device_closures: tuple[StaticPhase1DeviceClosure, ...]
    synthetic: StaticPhase1SyntheticClosure
    schema: str = STATIC_PHASE1_CALIBRATION_REHEARSAL_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != STATIC_PHASE1_CALIBRATION_REHEARSAL_SCHEMA:
            raise StaticPhase1CalibrationError(
                "Unsupported static Phase-1 rehearsal schema"
            )
        expected = STATIC_OVERHEAD_PHASE1_GRAPH.ordered_requirements
        if tuple(row.artifact_id for row in self.physical_assessments) != expected:
            raise StaticPhase1CalibrationError(
                "Physical assessments must cover the complete static graph"
            )
        if tuple(row.device for row in self.device_closures) != ("keyboard", "phone"):
            raise StaticPhase1CalibrationError(
                "Device closures must cover keyboard and phone in order"
            )

    @property
    def physical_artifacts_all_valid(self) -> bool:
        return bool(self.physical_assessments) and all(
            row.valid for row in self.physical_assessments
        )

    @property
    def physical_registry_blocked(self) -> bool:
        return not self.physical_artifacts_all_valid

    @property
    def status(self) -> str:
        if not self.synthetic.simulation_graph_verified:
            return "SYNTHETIC_PHASE1_GRAPH_REHEARSAL_FAILED"
        if self.physical_registry_blocked:
            return "SYNTHETIC_PHASE1_GRAPH_VERIFIED_PHYSICAL_REGISTRY_BLOCKED"
        return "SYNTHETIC_PHASE1_GRAPH_VERIFIED_PHYSICAL_ARTIFACTS_PRESENT_NO_AUTHORITY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "graph": {
                **STATIC_OVERHEAD_PHASE1_GRAPH.to_dict(),
                "graph_hash": STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
            },
            "manifest_id": self.manifest_id,
            "active_build_id": self.active_build_id,
            "physical_registry": {
                "relative_path": _PHYSICAL_REGISTRY_RELATIVE.as_posix(),
                "index_present": self.physical_registry_index_present,
                "assessment_count": len(self.physical_assessments),
                "missing_artifact_ids": [
                    row.artifact_id
                    for row in self.physical_assessments
                    if row.state is ArtifactState.MISSING
                ],
                "physical_artifacts_all_valid": self.physical_artifacts_all_valid,
                "blocked": self.physical_registry_blocked,
                "read_only": True,
                "written": False,
            },
            "device_closures": [row.to_dict() for row in self.device_closures],
            "synthetic_rehearsal": {
                **self.synthetic.to_dict(),
                "closure_hash": self.synthetic.closure_hash,
            },
            "historical_eye_on_arm_requirement_graph_modified": False,
            "historical_calibration_registry_modified": False,
            "hardware_accessed": False,
            "robot_commands_sent": 0,
            "camera_frames_captured": 0,
            "execution_authorized": False,
            "power_authorized": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self.to_dict())


def _normalized_context_hashes(
    context_hashes: Mapping[str, str],
) -> Mapping[str, str]:
    if not isinstance(context_hashes, Mapping):
        raise TypeError("context_hashes must be a mapping")
    required = set(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids)
    if set(context_hashes) != required:
        missing = tuple(sorted(required - set(context_hashes)))
        unexpected = tuple(sorted(set(context_hashes) - required))
        raise StaticPhase1CalibrationError(
            "Synthetic context hashes must exactly match the graph: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return MappingProxyType(
        {
            key: _validate_hash(context_hashes[key], key)
            for key in sorted(context_hashes)
        }
    )


def _changed_hash(original: str) -> str:
    replacement = "0" * 64
    return "1" * 64 if original == replacement else replacement


def build_static_phase1_synthetic_closure(
    context_hashes: Mapping[str, str],
) -> StaticPhase1SyntheticClosure:
    """Build and exhaustively invalidate a nominal-only in-memory chain."""

    normalized = _normalized_context_hashes(context_hashes)
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    artifacts: dict[str, CalibrationArtifact] = {}

    for artifact_id in graph.ordered_requirements:
        requirement = graph.requirements[artifact_id]
        dependency_hashes = {
            _GRAPH_CONTEXT_DEPENDENCY: graph.graph_hash,
            **{
                dependency: normalized[dependency]
                for dependency in requirement.context_dependencies
            },
        }
        artifacts[artifact_id] = CalibrationArtifact(
            artifact_id=artifact_id,
            version=1,
            state=ArtifactState.NOMINAL_ONLY,
            created_utc="2000-01-01T00:00:00Z",
            manifest_id=STATIC_PHASE1_SYNTHETIC_MANIFEST_ID,
            active_build_id=STATIC_PHASE1_SYNTHETIC_BUILD_ID,
            dependency_hashes=dependency_hashes,
            parent_artifact_hashes={
                parent: artifacts[parent].content_hash
                for parent in requirement.prerequisites
            },
            payload={
                "requirement_artifact_schema": requirement.artifact_schema,
                "graph_id": graph.graph_id,
                "graph_hash": graph.graph_hash,
                "authority": STATIC_OVERHEAD_PHASE1_AUTHORITY,
                "synthetic": True,
                "physical_measurements_present": False,
                "hardware_accessed": False,
                "execution_authorized": False,
                "physical_release_effect": "NONE",
            },
        )

    assessment_context = {
        _GRAPH_CONTEXT_DEPENDENCY: graph.graph_hash,
        **normalized,
    }
    registry = _InMemoryCalibrationRegistry(artifacts)
    baseline = tuple(
        registry.assess(
            artifact_id,
            assessment_context,
            manifest_id=STATIC_PHASE1_SYNTHETIC_MANIFEST_ID,
            active_build_id=STATIC_PHASE1_SYNTHETIC_BUILD_ID,
        )
        for artifact_id in graph.ordered_requirements
    )

    probes: list[StaticPhase1StalenessProbe] = []
    for parent_id, child_id in graph.parent_edges:
        original_parent = artifacts[parent_id]
        rotated_parent = replace(
            original_parent,
            version=original_parent.version + 1,
            payload={
                **dict(original_parent.payload),
                "synthetic_staleness_probe_revision": 2,
            },
        )
        rotated_artifacts = {**artifacts, parent_id: rotated_parent}
        assessment = _InMemoryCalibrationRegistry(rotated_artifacts).assess(
            child_id,
            assessment_context,
            manifest_id=STATIC_PHASE1_SYNTHETIC_MANIFEST_ID,
            active_build_id=STATIC_PHASE1_SYNTHETIC_BUILD_ID,
        )
        expected = f"STALE_PARENT_CALIBRATION:{child_id}:{parent_id}"
        observed = tuple(
            reason
            for reason in assessment.reasons
            if reason.startswith("STALE_PARENT_CALIBRATION:")
        )
        probes.append(
            StaticPhase1StalenessProbe(
                edge_kind="PARENT_ARTIFACT",
                upstream_id=parent_id,
                downstream_id=child_id,
                expected_reason=expected,
                observed_stale_reasons=observed,
                detected=observed == (expected,),
            )
        )

    for artifact_id in graph.ordered_requirements:
        artifact = artifacts[artifact_id]
        dependency_ids = (
            _GRAPH_CONTEXT_DEPENDENCY,
            *graph.requirements[artifact_id].context_dependencies,
        )
        for dependency_id in dependency_ids:
            changed_context = dict(assessment_context)
            changed_context[dependency_id] = _changed_hash(
                changed_context[dependency_id]
            )
            assessment = registry.assess(
                artifact_id,
                changed_context,
                manifest_id=STATIC_PHASE1_SYNTHETIC_MANIFEST_ID,
                active_build_id=STATIC_PHASE1_SYNTHETIC_BUILD_ID,
            )
            expected = (
                f"STALE_CALIBRATION_DEPENDENCY:{artifact_id}:{dependency_id}"
            )
            observed = tuple(
                reason
                for reason in assessment.reasons
                if reason.startswith("STALE_CALIBRATION_DEPENDENCY:")
            )
            probes.append(
                StaticPhase1StalenessProbe(
                    edge_kind="CONTEXT_SOURCE",
                    upstream_id=dependency_id,
                    downstream_id=artifact_id,
                    expected_reason=expected,
                    observed_stale_reasons=observed,
                    detected=observed == (expected,),
                )
            )

    return StaticPhase1SyntheticClosure(
        context_hashes=tuple(normalized.items()),
        artifacts=tuple(artifacts[item] for item in graph.ordered_requirements),
        baseline_assessments=baseline,
        staleness_probes=tuple(probes),
    )


def run_static_phase1_calibration_rehearsal(
    context: SimulationContext,
) -> StaticPhase1CalibrationRehearsalReport:
    """Assess physical absence and rehearse the complete static Phase-1 graph.

    This is the root application integration point.  It never opens a camera,
    connects to the arm, writes the physical registry, or grants execution
    authority.
    """

    context_hashes = static_phase1_context_hashes(context)
    return _run_calibration_rehearsal(context, context_hashes)


def run_static_context_calibration_rehearsal(
    context: StaticSimulationContext,
) -> dict[str, Any]:
    """Rehearse the same graph through the explicitly selected static context.

    The new envelope binds the static software bundle and preserves the existing
    graph report's meaning. No historical report/default route is reinterpreted,
    and no nominal artifact is installed into the physical registry.
    """
    from .static_simulation_context import (
        revalidate_static_simulation_context,
        static_simulation_context_hashes,
    )

    hashes = static_simulation_context_hashes(context)
    report = _run_calibration_rehearsal(context, hashes)
    revalidate_static_simulation_context(context)
    return {
        "schema": "rocell.static_context_calibration_rehearsal.v1",
        "bundle_sha256": context.bundle.source_sha256,
        "semantic_bindings_sha256": context.bundle.semantic_bindings_sha256,
        "graph_sha256": context.bundle.graph_hash,
        "target_catalog_sha256": context.targets.content_sha256,
        "optical_contract_sha256": context.optical_contract.content_sha256,
        "rehearsal": report.to_dict(),
        "simulation_only": True,
        "physical_authority": False,
        "installed_calibration_accepted": False,
        "hardware_commands_generated": 0,
    }


def _run_calibration_rehearsal(
    context: SimulationContext | StaticSimulationContext,
    context_hashes: Mapping[str, str],
) -> StaticPhase1CalibrationRehearsalReport:
    """Shared graph/registry behavior after the selected route's source guard."""
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    build_id = context.snapshot.active_build_id or "UNASSIGNED"
    physical_registry = CalibrationRegistry(
        context.workspace / _PHYSICAL_REGISTRY_RELATIVE
    )
    physical_resolution = physical_registry.resolve(
        graph.ordered_requirements,
        {
            _GRAPH_CONTEXT_DEPENDENCY: graph.graph_hash,
            **context_hashes,
        },
        manifest_id=context.snapshot.manifest_id,
        active_build_id=build_id,
    )
    physical_assessments = tuple(
        physical_resolution.assessments[artifact_id]
        for artifact_id in graph.ordered_requirements
    )
    by_id = {row.artifact_id: row for row in physical_assessments}
    device_closures = tuple(
        StaticPhase1DeviceClosure(
            device=device,
            terminals=graph.device_terminals[device],
            ordered_requirements=graph.device_closure(device),
            physical_assessments=tuple(
                by_id[artifact_id]
                for artifact_id in graph.device_closure(device)
            ),
        )
        for device in ("keyboard", "phone")
    )

    return StaticPhase1CalibrationRehearsalReport(
        manifest_id=context.snapshot.manifest_id,
        active_build_id=context.snapshot.active_build_id,
        physical_registry_index_present=physical_registry.index_path.is_file(),
        physical_assessments=physical_assessments,
        device_closures=device_closures,
        synthetic=build_static_phase1_synthetic_closure(context_hashes),
    )


__all__ = [
    "STATIC_PHASE1_CALIBRATION_REHEARSAL_SCHEMA",
    "STATIC_PHASE1_SYNTHETIC_BUILD_ID",
    "STATIC_PHASE1_SYNTHETIC_MANIFEST_ID",
    "StaticPhase1CalibrationError",
    "StaticPhase1CalibrationRehearsalReport",
    "StaticPhase1DeviceClosure",
    "StaticPhase1StalenessProbe",
    "StaticPhase1SyntheticClosure",
    "build_static_phase1_synthetic_closure",
    "run_static_phase1_calibration_rehearsal",
    "run_static_context_calibration_rehearsal",
    "static_phase1_context_hashes",
]
