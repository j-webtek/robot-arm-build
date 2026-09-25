"""Deterministic authorization-v2 bridge for hardware-free rehearsals.

This module closes three synthetic integration gaps without weakening the
physical boundary:

* it projects an exact :class:`StaticPhase1SyntheticClosure` into the
  capability-specific shape required by ``authorization_v2`` while retaining
  an explicit ``NOMINAL_ONLY`` provenance record;
* it assembles deterministic :class:`AuthorizationEvidence` from exact hashes,
  ordered simulated contact occurrences, and an ordered command tuple; and
* it emits strictly advancing synthetic interlock continuity samples suitable
  for consuming an ``OrderedSimulationPermit``.

The bridge imports no camera, serial, wire-protocol, or live-motion adapter.
Every output is permanently zero-authority.  In particular, nominal synthetic
calibrations are useful for exercising dependency and ordering logic but are
not physical calibration evidence and cannot authorize T=104 or contact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading

from rocell.application.static_phase1_calibration import (
    StaticPhase1StalenessProbe,
    StaticPhase1SyntheticClosure,
)
from rocell.calibration.artifacts import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
)
from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_AUTHORITY,
    STATIC_OVERHEAD_PHASE1_GRAPH,
)

from .authorization_v2 import (
    ZERO_AUTHORITY,
    AuthorizationContinuityEvidence,
    AuthorizationEvidence,
    BuildReleaseIdentity,
    CalibrationArtifactBinding,
    CalibrationClosureEvidence,
    CollisionClearanceState,
    CollisionTrajectoryEvidence,
    ControllerSessionEvidence,
    EvidenceOnlyReleaseScope,
    InterlockChannel,
    InterlockChannelEvidence,
    InterlockEvidenceBundle,
    InterlockEvidenceState,
    NamedSha256,
    OperatorArmEvidence,
    SimulatedContactCapability,
    SimulationTrajectoryCommand,
    canonical_record_sha256,
    continuity_from_authorization,
    trajectory_sequence_sha256,
)


SYNTHETIC_CALIBRATION_PROJECTION_SCHEMA = (
    "rocell.zero_authority.synthetic_calibration_projection.v1"
)
SYNTHETIC_EMULATOR_IDENTITY_SCHEMA = (
    "rocell.zero_authority.synthetic_emulator_identity.v1"
)
SYNTHETIC_AUTHORIZATION_BUNDLE_SCHEMA = (
    "rocell.zero_authority.synthetic_authorization_bundle.v1"
)
SYNTHETIC_CONTINUITY_SAMPLE_SCHEMA = (
    "rocell.zero_authority.synthetic_continuity_sample.v1"
)
SYNTHETIC_ISSUANCE_MONOTONIC = 100.0
SYNTHETIC_PERMIT_TTL_S = 10.0
SYNTHETIC_INTERLOCK_MAX_AGE_S = 0.1

_BASE_MONOTONIC = SYNTHETIC_ISSUANCE_MONOTONIC
_INTERLOCK_TICK_S = 0.0001
_CONSUMPTION_OFFSET_S = 0.00005
_OPERATOR_ARMED_AT = 99.0
_OPERATOR_EXPIRES_AT = 130.0
_MAX_TEXT_LENGTH = 512
_MAX_COMMANDS = 65_536
_MAX_PHYSICAL_OCCURRENCES = 4_096
_SHA256_HEX = frozenset("0123456789abcdef")


class SyntheticAuthorizationError(ValueError):
    """Synthetic source evidence or an exact bridge binding is invalid."""


def _sha256(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        raise SyntheticAuthorizationError(
            f"{label} must be exactly 64 lowercase hexadecimal characters"
        )
    return value


def _text(value: object, label: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > _MAX_TEXT_LENGTH
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise SyntheticAuthorizationError(
            f"{label} must be bounded, trimmed, non-empty text"
        )
    return value


def _zero_authority_document() -> dict[str, object]:
    return {
        "authority": ZERO_AUTHORITY,
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "power_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }


def _named_hashes_document(
    values: tuple[NamedSha256, ...],
) -> list[dict[str, str]]:
    return [item.to_dict() for item in values]


def _revalidate_named_hashes(
    values: object,
    *,
    label: str,
    expected_names: tuple[str, ...],
) -> tuple[NamedSha256, ...]:
    if type(values) is not tuple:
        raise SyntheticAuthorizationError(f"{label} must be an immutable tuple")
    typed = values
    if any(type(item) is not NamedSha256 for item in typed):
        raise SyntheticAuthorizationError(
            f"{label} contains a substituted named-hash type"
        )
    result = tuple(typed)
    for item in result:
        try:
            item.__post_init__()
        except (TypeError, ValueError, RuntimeError) as exc:
            raise SyntheticAuthorizationError(f"{label} is invalid") from exc
    if tuple(item.name for item in result) != expected_names:
        raise SyntheticAuthorizationError(
            f"{label} names differ from the exact expected order"
        )
    return result


def _snapshot_static_closure(
    source: StaticPhase1SyntheticClosure,
) -> StaticPhase1SyntheticClosure:
    """Detach and fully revalidate the nominal graph before projection."""

    if type(source) is not StaticPhase1SyntheticClosure:
        raise TypeError("source must be exactly StaticPhase1SyntheticClosure")
    for name in (
        "context_hashes",
        "artifacts",
        "baseline_assessments",
        "staleness_probes",
    ):
        if type(getattr(source, name)) is not tuple:
            raise SyntheticAuthorizationError(
                f"source {name} must be an immutable tuple"
            )

    required_context_names = tuple(
        sorted(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids)
    )
    if tuple(name for name, _ in source.context_hashes) != required_context_names:
        raise SyntheticAuthorizationError(
            "source context names differ from the complete static Phase-1 graph"
        )
    context_hashes: list[tuple[str, str]] = []
    for name, digest in source.context_hashes:
        context_hashes.append((_text(name, "context name"), _sha256(digest, name)))

    if any(type(item) is not CalibrationArtifact for item in source.artifacts):
        raise SyntheticAuthorizationError(
            "source contains a substituted calibration artifact type"
        )
    artifacts: list[CalibrationArtifact] = []
    try:
        for artifact in source.artifacts:
            copied_artifact = CalibrationArtifact.from_dict(artifact.to_dict())
            if (
                copied_artifact != artifact
                or copied_artifact.content_hash != artifact.content_hash
            ):
                raise SyntheticAuthorizationError(
                    f"source artifact {artifact.artifact_id} changed while snapshotting"
                )
            artifacts.append(copied_artifact)
    except SyntheticAuthorizationError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise SyntheticAuthorizationError("source artifact is invalid") from exc

    if any(
        type(item) is not ArtifactAssessment
        for item in source.baseline_assessments
    ):
        raise SyntheticAuthorizationError(
            "source contains a substituted baseline assessment type"
        )
    assessments: list[ArtifactAssessment] = []
    try:
        for assessment in source.baseline_assessments:
            copied_assessment = ArtifactAssessment(
                artifact_id=assessment.artifact_id,
                state=assessment.state,
                artifact_hash=assessment.artifact_hash,
                reasons=assessment.reasons,
            )
            if copied_assessment != assessment:
                raise SyntheticAuthorizationError(
                    "source assessment "
                    f"{assessment.artifact_id} changed while snapshotting"
                )
            assessments.append(copied_assessment)
    except SyntheticAuthorizationError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise SyntheticAuthorizationError("source assessment is invalid") from exc

    if any(
        type(item) is not StaticPhase1StalenessProbe
        for item in source.staleness_probes
    ):
        raise SyntheticAuthorizationError(
            "source contains a substituted staleness-probe type"
        )
    probes: list[StaticPhase1StalenessProbe] = []
    try:
        for probe in source.staleness_probes:
            copied_probe = StaticPhase1StalenessProbe(
                edge_kind=probe.edge_kind,
                upstream_id=probe.upstream_id,
                downstream_id=probe.downstream_id,
                expected_reason=probe.expected_reason,
                observed_stale_reasons=probe.observed_stale_reasons,
                detected=probe.detected,
            )
            if copied_probe != probe:
                raise SyntheticAuthorizationError(
                    "source staleness probe changed while snapshotting"
                )
            probes.append(copied_probe)
    except SyntheticAuthorizationError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise SyntheticAuthorizationError("source staleness probe is invalid") from exc

    try:
        snapshot = StaticPhase1SyntheticClosure(
            context_hashes=tuple(context_hashes),
            artifacts=tuple(artifacts),
            baseline_assessments=tuple(assessments),
            staleness_probes=tuple(probes),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise SyntheticAuthorizationError(
            "source closure failed exact graph validation"
        ) from exc
    if snapshot.to_dict() != source.to_dict():
        raise SyntheticAuthorizationError(
            "source closure representation changed while snapshotting"
        )
    if not snapshot.simulation_graph_verified:
        raise SyntheticAuthorizationError(
            "source closure did not verify every synthetic graph edge"
        )
    document = snapshot.to_dict()
    if (
        document.get("authority") != STATIC_OVERHEAD_PHASE1_AUTHORITY
        or document.get("physical_artifacts_created") is not False
        or document.get("physical_registry_written") is not False
        or document.get("hardware_accessed") is not False
        or document.get("robot_commands_sent") != 0
        or document.get("execution_authorized") is not False
        or document.get("physical_release_effect") != "NONE"
    ):
        raise SyntheticAuthorizationError(
            "source closure changed its zero-authority semantics"
        )
    return snapshot


def _device_for_capability(capability: SimulatedContactCapability) -> str:
    if type(capability) is not SimulatedContactCapability:
        raise TypeError("capability must be exactly SimulatedContactCapability")
    if capability is SimulatedContactCapability.KEYBOARD:
        return "keyboard"
    if capability is SimulatedContactCapability.PHONE:
        return "phone"
    raise SyntheticAuthorizationError("unsupported simulated contact capability")


@dataclass(frozen=True, slots=True)
class SyntheticCalibrationProjection:
    """Capability closure plus explicit nominal-only source provenance."""

    capability: SimulatedContactCapability
    source_closure_sha256: str
    source_context_hashes: tuple[NamedSha256, ...]
    nominal_artifact_hashes: tuple[NamedSha256, ...]
    calibration: CalibrationClosureEvidence
    schema: str = SYNTHETIC_CALIBRATION_PROJECTION_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            canonical_record_sha256(self._document_unvalidated()),
        )

    def _validate_unsealed(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != SYNTHETIC_CALIBRATION_PROJECTION_SCHEMA
        ):
            raise SyntheticAuthorizationError(
                "unsupported synthetic calibration projection schema"
            )
        device = _device_for_capability(self.capability)
        _sha256(self.source_closure_sha256, "source_closure_sha256")
        contexts = _revalidate_named_hashes(
            self.source_context_hashes,
            label="source_context_hashes",
            expected_names=tuple(
                sorted(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids)
            ),
        )
        required_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
        nominal = _revalidate_named_hashes(
            self.nominal_artifact_hashes,
            label="nominal_artifact_hashes",
            expected_names=required_ids,
        )
        if type(self.calibration) is not CalibrationClosureEvidence:
            raise SyntheticAuthorizationError(
                "calibration must be exactly CalibrationClosureEvidence"
            )
        try:
            self.calibration.__post_init__()
        except (TypeError, ValueError, RuntimeError) as exc:
            raise SyntheticAuthorizationError(
                "projected calibration evidence is invalid"
            ) from exc
        if self.calibration.capability is not self.capability:
            raise SyntheticAuthorizationError(
                "projected calibration capability changed"
            )
        if (
            self.calibration.graph_id != STATIC_OVERHEAD_PHASE1_GRAPH.graph_id
            or self.calibration.graph_sha256
            != STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash
        ):
            raise SyntheticAuthorizationError("projected calibration graph drifted")
        if tuple(item.artifact_id for item in self.calibration.artifacts) != required_ids:
            raise SyntheticAuthorizationError(
                "projected calibration artifact order drifted"
            )

        context_by_name = {item.name: item.sha256 for item in contexts}
        nominal_by_id = {item.name: item.sha256 for item in nominal}
        for binding in self.calibration.artifacts:
            requirement = STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                binding.artifact_id
            ]
            if binding.artifact_sha256 != nominal_by_id[binding.artifact_id]:
                raise SyntheticAuthorizationError(
                    f"projected artifact hash drifted for {binding.artifact_id}"
                )
            if tuple(item.name for item in binding.dependency_hashes) != (
                requirement.prerequisites
            ):
                raise SyntheticAuthorizationError(
                    f"projected parents drifted for {binding.artifact_id}"
                )
            if any(
                item.sha256 != nominal_by_id[item.name]
                for item in binding.dependency_hashes
            ):
                raise SyntheticAuthorizationError(
                    f"projected parent hash drifted for {binding.artifact_id}"
                )
            if tuple(item.name for item in binding.context_hashes) != (
                requirement.context_dependencies
            ):
                raise SyntheticAuthorizationError(
                    f"projected contexts drifted for {binding.artifact_id}"
                )
            if any(
                item.sha256 != context_by_name[item.name]
                for item in binding.context_hashes
            ):
                raise SyntheticAuthorizationError(
                    f"projected context hash drifted for {binding.artifact_id}"
                )

    def _document_unvalidated(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_static_phase1": {
                "closure_sha256": self.source_closure_sha256,
                "authority": STATIC_OVERHEAD_PHASE1_AUTHORITY,
                "graph_id": STATIC_OVERHEAD_PHASE1_GRAPH.graph_id,
                "graph_sha256": STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
                "context_hashes": _named_hashes_document(
                    self.source_context_hashes
                ),
            },
            "capability": self.capability.value,
            "artifacts": [
                {
                    "artifact_id": item.name,
                    "artifact_sha256": item.sha256,
                    "state": ArtifactState.NOMINAL_ONLY.value,
                    "synthetic": True,
                    "physical_measurements_present": False,
                    "execution_authorized": False,
                }
                for item in self.nominal_artifact_hashes
            ],
            "calibration_evidence": self.calibration.to_dict(),
            **_zero_authority_document(),
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if (
            canonical_record_sha256(self._document_unvalidated())
            != self._sealed_sha256
        ):
            raise SyntheticAuthorizationError(
                "synthetic calibration projection changed after construction"
            )

    @property
    def projection_sha256(self) -> str:
        self.validate()
        return canonical_record_sha256(self._document_unvalidated())

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document_unvalidated()

    def assert_matches_source(self, source: StaticPhase1SyntheticClosure) -> None:
        self.validate()
        snapshot = _snapshot_static_closure(source)
        if snapshot.closure_hash != self.source_closure_sha256:
            raise SyntheticAuthorizationError(
                "static Phase-1 source closure hash changed"
            )
        expected = _projection_from_snapshot(snapshot, capability=self.capability)
        if expected._document_unvalidated() != self._document_unvalidated():
            raise SyntheticAuthorizationError(
                "static Phase-1 source differs from the projection"
            )


def _projection_from_snapshot(
    source: StaticPhase1SyntheticClosure,
    *,
    capability: SimulatedContactCapability,
) -> SyntheticCalibrationProjection:
    device = _device_for_capability(capability)
    artifact_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
    artifacts = {artifact.artifact_id: artifact for artifact in source.artifacts}
    context_hashes = dict(source.context_hashes)
    nominal = tuple(
        NamedSha256(artifact_id, artifacts[artifact_id].content_hash)
        for artifact_id in artifact_ids
    )
    bindings = tuple(
        CalibrationArtifactBinding(
            artifact_id=artifact_id,
            artifact_sha256=artifacts[artifact_id].content_hash,
            dependency_hashes=tuple(
                NamedSha256(parent_id, artifacts[parent_id].content_hash)
                for parent_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                    artifact_id
                ].prerequisites
            ),
            context_hashes=tuple(
                NamedSha256(context_id, context_hashes[context_id])
                for context_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                    artifact_id
                ].context_dependencies
            ),
        )
        for artifact_id in artifact_ids
    )
    return SyntheticCalibrationProjection(
        capability=capability,
        source_closure_sha256=source.closure_hash,
        source_context_hashes=tuple(
            NamedSha256(name, digest) for name, digest in source.context_hashes
        ),
        nominal_artifact_hashes=nominal,
        calibration=CalibrationClosureEvidence(
            capability=capability,
            graph_id=STATIC_OVERHEAD_PHASE1_GRAPH.graph_id,
            graph_sha256=STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
            artifacts=bindings,
        ),
    )


def project_static_phase1_synthetic_closure(
    source: StaticPhase1SyntheticClosure,
    *,
    capability: SimulatedContactCapability,
) -> SyntheticCalibrationProjection:
    """Project a verified nominal closure without promoting its authority."""

    snapshot = _snapshot_static_closure(source)
    projection = _projection_from_snapshot(snapshot, capability=capability)
    projection.assert_matches_source(snapshot)
    return projection


@dataclass(frozen=True, slots=True)
class SyntheticEmulatorIdentity:
    """Exact configuration and logical-session identity of one emulator."""

    emulator_id: str
    configuration_sha256: str
    session_id: str
    schema: str = SYNTHETIC_EMULATOR_IDENTITY_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            canonical_record_sha256(self._document_unvalidated()),
        )

    def _validate_unsealed(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != SYNTHETIC_EMULATOR_IDENTITY_SCHEMA
        ):
            raise SyntheticAuthorizationError(
                "unsupported synthetic emulator identity schema"
            )
        _text(self.emulator_id, "emulator_id")
        _sha256(self.configuration_sha256, "configuration_sha256")
        _text(self.session_id, "session_id")

    def _document_unvalidated(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "emulator_id": self.emulator_id,
            "configuration_sha256": self.configuration_sha256,
            "session_id": self.session_id,
            **_zero_authority_document(),
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if (
            canonical_record_sha256(self._document_unvalidated())
            != self._sealed_sha256
        ):
            raise SyntheticAuthorizationError(
                "synthetic emulator identity changed after construction"
            )

    @property
    def identity_sha256(self) -> str:
        self.validate()
        return canonical_record_sha256(self._document_unvalidated())

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document_unvalidated()


def _controller_from_emulator(
    emulator: SyntheticEmulatorIdentity,
) -> ControllerSessionEvidence:
    return ControllerSessionEvidence(
        arm_hardware_id="synthetic-no-hardware-roarm-m3-pro",
        controller_hardware_id=emulator.emulator_id,
        firmware_build_id=(
            f"synthetic-emulator-config-{emulator.configuration_sha256[:16]}"
        ),
        firmware_sha256=emulator.configuration_sha256,
        connection_session_id=emulator.session_id,
        persistent_port_id="synthetic-no-persistent-port",
        transport_descriptor_sha256=emulator.identity_sha256,
    )


def _build_release_from_snapshot(build_snapshot_sha256: str) -> BuildReleaseIdentity:
    manifest_sha256 = canonical_record_sha256(
        {
            "schema": "rocell.zero_authority.synthetic_manifest_binding.v1",
            "build_snapshot_sha256": build_snapshot_sha256,
        }
    )
    release_receipt_sha256 = canonical_record_sha256(
        {
            "schema": "rocell.zero_authority.synthetic_release_receipt.v1",
            "build_snapshot_sha256": build_snapshot_sha256,
            "manifest_sha256": manifest_sha256,
            "scope": EvidenceOnlyReleaseScope.SIMULATION_EVIDENCE_ONLY.value,
        }
    )
    return BuildReleaseIdentity(
        active_build_id=f"synthetic-build-{build_snapshot_sha256[:16]}",
        build_snapshot_sha256=build_snapshot_sha256,
        manifest_id="synthetic-manifest-derived-from-build-snapshot",
        manifest_sha256=manifest_sha256,
        release_receipt_id="synthetic-evidence-only-release-receipt",
        release_receipt_sha256=release_receipt_sha256,
        scope=EvidenceOnlyReleaseScope.SIMULATION_EVIDENCE_ONLY,
    )


def _interlock_source_id(channel: InterlockChannel) -> str:
    return f"synthetic-{channel.value}-source-v1"


def _interlock_raw_sha256(
    *,
    authorization_seed_sha256: str,
    channel: InterlockChannel,
    sequence: int,
    captured_monotonic: float,
) -> str:
    return canonical_record_sha256(
        {
            "schema": "rocell.zero_authority.synthetic_interlock_raw.v1",
            "authorization_seed_sha256": authorization_seed_sha256,
            "channel": channel.value,
            "source_id": _interlock_source_id(channel),
            "sequence": sequence,
            "captured_monotonic": captured_monotonic,
            "state": InterlockEvidenceState.PASS.value,
            "synthetic": True,
        }
    )


def _interlocks(
    *,
    authorization_seed_sha256: str,
    sequence: int,
    captured_monotonic: float,
) -> InterlockEvidenceBundle:
    return InterlockEvidenceBundle(
        channels=tuple(
            InterlockChannelEvidence(
                channel=channel,
                source_id=_interlock_source_id(channel),
                sequence=sequence,
                captured_monotonic=captured_monotonic,
                raw_sha256=_interlock_raw_sha256(
                    authorization_seed_sha256=authorization_seed_sha256,
                    channel=channel,
                    sequence=sequence,
                    captured_monotonic=captured_monotonic,
                ),
                state=InterlockEvidenceState.PASS,
            )
            for channel in InterlockChannel
        )
    )


def _authorization_seed(
    *,
    calibration: SyntheticCalibrationProjection,
    ordered_physical_occurrence_ids: tuple[str, ...],
    ordered_commands: tuple[SimulationTrajectoryCommand, ...],
    collision_report_sha256: str,
    device_safety_context_sha256: str,
    build_snapshot_sha256: str,
    plan_sha256: str,
    emulator: SyntheticEmulatorIdentity,
) -> str:
    return canonical_record_sha256(
        {
            "schema": "rocell.zero_authority.synthetic_authorization_seed.v1",
            "calibration_projection_sha256": calibration.projection_sha256,
            "ordered_physical_occurrence_ids": list(
                ordered_physical_occurrence_ids
            ),
            "ordered_command_hashes": [
                command.command_sha256 for command in ordered_commands
            ],
            "collision_report_sha256": collision_report_sha256,
            "device_safety_context_sha256": device_safety_context_sha256,
            "build_snapshot_sha256": build_snapshot_sha256,
            "plan_sha256": plan_sha256,
            "emulator_identity_sha256": emulator.identity_sha256,
        }
    )


def _snapshot_commands(
    commands: object,
) -> tuple[SimulationTrajectoryCommand, ...]:
    if type(commands) is not tuple:
        raise TypeError("ordered_commands must be exactly tuple")
    if not 1 <= len(commands) <= _MAX_COMMANDS:
        raise SyntheticAuthorizationError(
            "ordered_commands is empty or exceeds its count limit"
        )
    result: list[SimulationTrajectoryCommand] = []
    for command in commands:
        if type(command) is not SimulationTrajectoryCommand:
            raise SyntheticAuthorizationError(
                "ordered_commands contains a substituted command type"
            )
        try:
            copied = SimulationTrajectoryCommand(
                command_occurrence_id=command.command_occurrence_id,
                action_occurrence_id=command.action_occurrence_id,
                primitive=command.primitive,
                target_state_sha256=command.target_state_sha256,
                constraint_set_sha256=command.constraint_set_sha256,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            raise SyntheticAuthorizationError("simulation command is invalid") from exc
        if copied != command or copied.command_sha256 != command.command_sha256:
            raise SyntheticAuthorizationError(
                "simulation command changed while snapshotting"
            )
        result.append(copied)
    return tuple(result)


def _physical_occurrences(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError("ordered_physical_occurrence_ids must be exactly tuple")
    if not 1 <= len(value) <= _MAX_PHYSICAL_OCCURRENCES:
        raise SyntheticAuthorizationError(
            "ordered physical occurrences are empty or exceed their count limit"
        )
    result = tuple(
        _sha256(item, f"ordered_physical_occurrence_ids[{index}]")
        for index, item in enumerate(value)
    )
    if len(set(result)) != len(result):
        raise SyntheticAuthorizationError(
            "ordered physical occurrence IDs must be unique"
        )
    return result


@dataclass(frozen=True, slots=True)
class SyntheticAuthorizationBundle:
    """AuthorizationEvidence plus the nominal/synthetic bindings it omits."""

    calibration: SyntheticCalibrationProjection
    emulator: SyntheticEmulatorIdentity
    ordered_physical_occurrence_ids: tuple[str, ...]
    ordered_commands: tuple[SimulationTrajectoryCommand, ...]
    collision_report_sha256: str
    device_safety_context_sha256: str
    build_snapshot_sha256: str
    plan_sha256: str
    authorization_seed_sha256: str
    evidence: AuthorizationEvidence
    schema: str = SYNTHETIC_AUTHORIZATION_BUNDLE_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            canonical_record_sha256(self._document_unvalidated()),
        )

    def _validate_unsealed(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != SYNTHETIC_AUTHORIZATION_BUNDLE_SCHEMA
        ):
            raise SyntheticAuthorizationError(
                "unsupported synthetic authorization bundle schema"
            )
        if type(self.calibration) is not SyntheticCalibrationProjection:
            raise SyntheticAuthorizationError(
                "calibration must be exactly SyntheticCalibrationProjection"
            )
        self.calibration.validate()
        if type(self.emulator) is not SyntheticEmulatorIdentity:
            raise SyntheticAuthorizationError(
                "emulator must be exactly SyntheticEmulatorIdentity"
            )
        self.emulator.validate()
        occurrences = _physical_occurrences(self.ordered_physical_occurrence_ids)
        commands = _snapshot_commands(self.ordered_commands)
        collision_hash = _sha256(
            self.collision_report_sha256, "collision_report_sha256"
        )
        device_hash = _sha256(
            self.device_safety_context_sha256,
            "device_safety_context_sha256",
        )
        build_hash = _sha256(self.build_snapshot_sha256, "build_snapshot_sha256")
        plan_hash = _sha256(self.plan_sha256, "plan_sha256")
        expected_seed = _authorization_seed(
            calibration=self.calibration,
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=commands,
            collision_report_sha256=collision_hash,
            device_safety_context_sha256=device_hash,
            build_snapshot_sha256=build_hash,
            plan_sha256=plan_hash,
            emulator=self.emulator,
        )
        if _sha256(
            self.authorization_seed_sha256, "authorization_seed_sha256"
        ) != expected_seed:
            raise SyntheticAuthorizationError("authorization seed binding drifted")
        if type(self.evidence) is not AuthorizationEvidence:
            raise SyntheticAuthorizationError(
                "evidence must be exactly AuthorizationEvidence"
            )
        try:
            self.evidence.__post_init__()
        except (TypeError, ValueError, RuntimeError) as exc:
            raise SyntheticAuthorizationError(
                "authorization-v2 evidence is invalid"
            ) from exc
        expected = _build_authorization_evidence(
            calibration=self.calibration,
            emulator=self.emulator,
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=commands,
            collision_report_sha256=collision_hash,
            device_safety_context_sha256=device_hash,
            build_snapshot_sha256=build_hash,
            plan_sha256=plan_hash,
            authorization_seed_sha256=expected_seed,
        )
        if self.evidence != expected or self.evidence.to_dict() != expected.to_dict():
            raise SyntheticAuthorizationError(
                "authorization-v2 evidence drifted from deterministic inputs"
            )

    def _document_unvalidated(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "calibration_projection": self.calibration.to_dict(),
            "emulator": self.emulator.to_dict(),
            "ordered_physical_occurrence_ids": list(
                self.ordered_physical_occurrence_ids
            ),
            "ordered_command_hashes": [
                command.command_sha256 for command in self.ordered_commands
            ],
            "collision_report_sha256": self.collision_report_sha256,
            "device_safety_context_sha256": self.device_safety_context_sha256,
            "build_snapshot_sha256": self.build_snapshot_sha256,
            "plan_sha256": self.plan_sha256,
            "authorization_seed_sha256": self.authorization_seed_sha256,
            "authorization_evidence": self.evidence.to_dict(),
            **_zero_authority_document(),
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if (
            canonical_record_sha256(self._document_unvalidated())
            != self._sealed_sha256
        ):
            raise SyntheticAuthorizationError(
                "synthetic authorization bundle changed after construction"
            )

    @property
    def bundle_sha256(self) -> str:
        self.validate()
        return canonical_record_sha256(self._document_unvalidated())

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document_unvalidated()


def _build_authorization_evidence(
    *,
    calibration: SyntheticCalibrationProjection,
    emulator: SyntheticEmulatorIdentity,
    ordered_physical_occurrence_ids: tuple[str, ...],
    ordered_commands: tuple[SimulationTrajectoryCommand, ...],
    collision_report_sha256: str,
    device_safety_context_sha256: str,
    build_snapshot_sha256: str,
    plan_sha256: str,
    authorization_seed_sha256: str,
) -> AuthorizationEvidence:
    return AuthorizationEvidence(
        capability=calibration.capability,
        controller=_controller_from_emulator(emulator),
        build_release=_build_release_from_snapshot(build_snapshot_sha256),
        calibration=calibration.calibration,
        collision=CollisionTrajectoryEvidence(
            report_sha256=collision_report_sha256,
            cleared_trajectory_sha256=trajectory_sequence_sha256(ordered_commands),
            state=CollisionClearanceState.CLEAR_FOR_SIMULATION,
        ),
        device_state_sha256=device_safety_context_sha256,
        interlocks=_interlocks(
            authorization_seed_sha256=authorization_seed_sha256,
            sequence=0,
            captured_monotonic=_BASE_MONOTONIC,
        ),
        operator_arm=OperatorArmEvidence(
            operator_id="synthetic-deterministic-operator",
            nonce_sha256=canonical_record_sha256(
                {
                    "schema": "rocell.zero_authority.synthetic_operator_nonce.v1",
                    "authorization_seed_sha256": authorization_seed_sha256,
                }
            ),
            armed_at_monotonic=_OPERATOR_ARMED_AT,
            expires_at_monotonic=_OPERATOR_EXPIRES_AT,
        ),
        plan_sha256=plan_sha256,
        ordered_action_occurrence_ids=ordered_physical_occurrence_ids,
        ordered_commands=ordered_commands,
    )


def build_synthetic_authorization_evidence(
    *,
    calibration: SyntheticCalibrationProjection,
    ordered_physical_occurrence_ids: tuple[str, ...],
    ordered_commands: tuple[SimulationTrajectoryCommand, ...],
    collision_report_sha256: str,
    device_safety_context_sha256: str,
    build_snapshot_sha256: str,
    plan_sha256: str,
    emulator: SyntheticEmulatorIdentity,
) -> SyntheticAuthorizationBundle:
    """Build deterministic authorization-v2 evidence with no physical effect."""

    if type(calibration) is not SyntheticCalibrationProjection:
        raise TypeError("calibration must be exactly SyntheticCalibrationProjection")
    calibration.validate()
    if type(emulator) is not SyntheticEmulatorIdentity:
        raise TypeError("emulator must be exactly SyntheticEmulatorIdentity")
    emulator.validate()
    occurrences = _physical_occurrences(ordered_physical_occurrence_ids)
    commands = _snapshot_commands(ordered_commands)
    collision_hash = _sha256(collision_report_sha256, "collision_report_sha256")
    device_hash = _sha256(
        device_safety_context_sha256, "device_safety_context_sha256"
    )
    build_hash = _sha256(build_snapshot_sha256, "build_snapshot_sha256")
    plan_hash = _sha256(plan_sha256, "plan_sha256")
    seed = _authorization_seed(
        calibration=calibration,
        ordered_physical_occurrence_ids=occurrences,
        ordered_commands=commands,
        collision_report_sha256=collision_hash,
        device_safety_context_sha256=device_hash,
        build_snapshot_sha256=build_hash,
        plan_sha256=plan_hash,
        emulator=emulator,
    )
    evidence = _build_authorization_evidence(
        calibration=calibration,
        emulator=emulator,
        ordered_physical_occurrence_ids=occurrences,
        ordered_commands=commands,
        collision_report_sha256=collision_hash,
        device_safety_context_sha256=device_hash,
        build_snapshot_sha256=build_hash,
        plan_sha256=plan_hash,
        authorization_seed_sha256=seed,
    )
    return SyntheticAuthorizationBundle(
        calibration=calibration,
        emulator=emulator,
        ordered_physical_occurrence_ids=occurrences,
        ordered_commands=commands,
        collision_report_sha256=collision_hash,
        device_safety_context_sha256=device_hash,
        build_snapshot_sha256=build_hash,
        plan_sha256=plan_hash,
        authorization_seed_sha256=seed,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class SyntheticContinuitySample:
    """One deterministic, strictly newer continuity sample for one command."""

    command_ordinal: int
    now_monotonic: float
    authorization_seed_sha256: str
    continuity: AuthorizationContinuityEvidence
    schema: str = SYNTHETIC_CONTINUITY_SAMPLE_SCHEMA

    def __post_init__(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != SYNTHETIC_CONTINUITY_SAMPLE_SCHEMA
        ):
            raise SyntheticAuthorizationError(
                "unsupported synthetic continuity sample schema"
            )
        if (
            type(self.command_ordinal) is not int
            or not 0 <= self.command_ordinal < _MAX_COMMANDS
        ):
            raise SyntheticAuthorizationError(
                "command_ordinal must be a bounded nonnegative integer"
            )
        if type(self.now_monotonic) is not float:
            raise TypeError("now_monotonic must be exactly float")
        seed = _sha256(
            self.authorization_seed_sha256, "authorization_seed_sha256"
        )
        if type(self.continuity) is not AuthorizationContinuityEvidence:
            raise TypeError(
                "continuity must be exactly AuthorizationContinuityEvidence"
            )
        try:
            self.continuity.__post_init__()
        except (TypeError, ValueError, RuntimeError) as exc:
            raise SyntheticAuthorizationError("continuity evidence is invalid") from exc
        expected_sequence = self.command_ordinal + 1
        expected_captured = _BASE_MONOTONIC + expected_sequence * _INTERLOCK_TICK_S
        if self.now_monotonic != expected_captured + _CONSUMPTION_OFFSET_S:
            raise SyntheticAuthorizationError(
                "continuity consumption time does not match its dense ordinal"
            )
        for channel in self.continuity.interlocks.channels:
            if (
                channel.sequence != expected_sequence
                or channel.captured_monotonic != expected_captured
                or channel.source_id != _interlock_source_id(channel.channel)
                or channel.state is not InterlockEvidenceState.PASS
                or channel.captured_monotonic >= self.now_monotonic
                or channel.raw_sha256
                != _interlock_raw_sha256(
                    authorization_seed_sha256=seed,
                    channel=channel.channel,
                    sequence=expected_sequence,
                    captured_monotonic=expected_captured,
                )
            ):
                raise SyntheticAuthorizationError(
                    "continuity interlocks are not the exact advancing sample"
                )

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        return {
            "schema": self.schema,
            "command_ordinal": self.command_ordinal,
            "now_monotonic": self.now_monotonic,
            "authorization_seed_sha256": self.authorization_seed_sha256,
            "interlocks": self.continuity.interlocks.to_dict(),
            **_zero_authority_document(),
        }


class SyntheticInterlockContinuity:
    """One-way source of fresh interlocks for an exact authorization bundle."""

    __slots__ = ("_bundle", "_cursor", "_lock")

    def __init__(self, bundle: SyntheticAuthorizationBundle) -> None:
        if type(bundle) is not SyntheticAuthorizationBundle:
            raise TypeError("bundle must be exactly SyntheticAuthorizationBundle")
        bundle.validate()
        self._bundle = bundle
        self._cursor = 0
        self._lock = threading.Lock()

    @property
    def next_ordinal(self) -> int | None:
        with self._lock:
            if self._cursor == len(self._bundle.ordered_commands):
                return None
            return self._cursor

    @property
    def remaining_samples(self) -> int:
        with self._lock:
            return len(self._bundle.ordered_commands) - self._cursor

    @property
    def zero_authority(self) -> bool:
        return True

    def next_sample(self) -> SyntheticContinuitySample:
        """Return the next source-stable, sequence/time/raw-distinct sample."""

        with self._lock:
            return self._next_sample_locked()

    def __call__(
        self, binding: object, relative_ordinal: int
    ) -> tuple[AuthorizationContinuityEvidence, float]:
        """Act as ``AuthorizationV2MissionCursor``'s continuity supplier.

        Importing the application-layer binding here would invert the runtime
        dependency.  The two primitive fields used for correlation are checked
        explicitly instead.  This callable supplies evidence only; it is not a
        permit and has no command-emission method.
        """

        if type(relative_ordinal) is not int or relative_ordinal < 0:
            raise SyntheticAuthorizationError(
                "relative_ordinal must be a nonnegative integer"
            )
        with self._lock:
            if relative_ordinal != self._cursor:
                raise SyntheticAuthorizationError(
                    "continuity request skipped, duplicated, or reordered an ordinal"
                )
            if self._cursor >= len(self._bundle.ordered_commands):
                raise SyntheticAuthorizationError(
                    "synthetic interlock continuity is exhausted"
                )
            expected = self._bundle.ordered_commands[self._cursor]
            if (
                getattr(binding, "simulation_command", None) != expected
                or getattr(binding, "action_occurrence_sha256", None)
                != expected.action_occurrence_id
            ):
                raise SyntheticAuthorizationError(
                    "continuity request binding differs from the authorized command"
                )
            sample = self._next_sample_locked()
            return sample.continuity, sample.now_monotonic

    def _next_sample_locked(self) -> SyntheticContinuitySample:
        self._bundle.validate()
        if self._cursor >= len(self._bundle.ordered_commands):
            raise SyntheticAuthorizationError(
                "synthetic interlock continuity is exhausted"
            )
        ordinal = self._cursor
        sequence = ordinal + 1
        captured = _BASE_MONOTONIC + sequence * _INTERLOCK_TICK_S
        now = captured + _CONSUMPTION_OFFSET_S
        continuity = continuity_from_authorization(
            self._bundle.evidence,
            interlocks=_interlocks(
                authorization_seed_sha256=(
                    self._bundle.authorization_seed_sha256
                ),
                sequence=sequence,
                captured_monotonic=captured,
            ),
        )
        sample = SyntheticContinuitySample(
            command_ordinal=ordinal,
            now_monotonic=now,
            authorization_seed_sha256=(
                self._bundle.authorization_seed_sha256
            ),
            continuity=continuity,
        )
        self._cursor += 1
        return sample


__all__ = [
    "SYNTHETIC_AUTHORIZATION_BUNDLE_SCHEMA",
    "SYNTHETIC_CALIBRATION_PROJECTION_SCHEMA",
    "SYNTHETIC_CONTINUITY_SAMPLE_SCHEMA",
    "SYNTHETIC_EMULATOR_IDENTITY_SCHEMA",
    "SYNTHETIC_INTERLOCK_MAX_AGE_S",
    "SYNTHETIC_ISSUANCE_MONOTONIC",
    "SYNTHETIC_PERMIT_TTL_S",
    "SyntheticAuthorizationBundle",
    "SyntheticAuthorizationError",
    "SyntheticCalibrationProjection",
    "SyntheticContinuitySample",
    "SyntheticEmulatorIdentity",
    "SyntheticInterlockContinuity",
    "build_synthetic_authorization_evidence",
    "project_static_phase1_synthetic_closure",
]
