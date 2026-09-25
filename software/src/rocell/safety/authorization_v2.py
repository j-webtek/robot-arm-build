"""Hash-bound, ordered authorization rehearsal with zero hardware authority.

This module is intentionally isolated from the live arm transport.  It models
the evidence and ordering rules that a future physical authorization boundary
must satisfy, but it cannot approve a RoArm goal, emit a wire message, or enable
the firmware's ``T=104`` command.  The only consumable object returned here is
an ordered *simulation* cursor.

The older preflight path represents several facts as booleans and its motion
permit treats approved goal hashes as an unordered multiset.  Neither property
is strong enough for contact work.  This additive foundation instead binds:

* exact arm/controller, firmware, connection-session, and persistent-port IDs;
* exact build, manifest, and evidence-only release-receipt identities;
* the capability-specific static-camera calibration dependency closure;
* a collision report to the exact ordered simulated trajectory;
* device state, operator-arm nonce, and plan hashes;
* source/sequence/time/raw hashes for every interlock channel; and
* ordered action occurrences and ordered simulated command occurrences.

All public evidence classes are immutable value records, not attestations.  The
module revalidates them when issuing a cursor so bypassing a dataclass
constructor cannot manufacture an accepted record.  The issued cursor has a
module-owned constructor seal and snapshots primitive values instead of
retaining caller-owned evidence objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import threading
from types import MappingProxyType
from typing import Any, Mapping, NoReturn, cast

from rocell.calibration.artifacts import ArtifactState
from rocell.calibration.registry import CalibrationRegistry
from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_GRAPH,
)


AUTHORIZATION_V2_SCHEMA = "rocell.zero_authority.authorization_context.v2"
CALIBRATION_CLOSURE_SCHEMA = "rocell.zero_authority.calibration_closure.v2"
TRAJECTORY_SEQUENCE_SCHEMA = "rocell.zero_authority.trajectory_sequence.v2"
SIMULATION_PERMIT_SCHEMA = "rocell.zero_authority.ordered_permit.v2"
SIMULATION_RECEIPT_SCHEMA = "rocell.zero_authority.command_receipt.v2"
ZERO_AUTHORITY = "SIMULATION_ONLY_NO_PHYSICAL_RELEASE"

_SHA256_LENGTH = 64
_MAX_TEXT_LENGTH = 512
_MAX_ACTIONS = 4_096
_MAX_COMMANDS = 65_536
_MAX_CALIBRATION_ARTIFACTS = 128
_MAX_CANONICAL_DEPTH = 32
_MAX_CANONICAL_NODES = 200_000
_MAX_CANONICAL_COLLECTION = 65_536
_MAX_SAFE_INTEGER = (1 << 53) - 1
_MAX_MONOTONIC_S = 1.0e12
_MAX_OPERATOR_ARM_WINDOW_S = 60.0
_MAX_PERMIT_TTL_S = 30.0
_MAX_INTERLOCK_AGE_S = 5.0
_STATIC_PHASE1_GRAPH_CONTEXT_ID = "static_phase1_requirement_graph"
_REQUIRED_INTERLOCK_CHANNELS: tuple["InterlockChannel", ...]


class AuthorizationV2Error(RuntimeError):
    """An evidence record or ordered simulation authorization failed closed."""


class SimulatedContactCapability(str, Enum):
    """Capabilities that exist only inside this zero-authority rehearsal."""

    KEYBOARD = "simulate_keyboard_contact"
    PHONE = "simulate_phone_contact"


class EvidenceOnlyReleaseScope(str, Enum):
    """The sole release scope accepted by this non-physical foundation."""

    SIMULATION_EVIDENCE_ONLY = "SIMULATION_EVIDENCE_ONLY"


class CollisionClearanceState(str, Enum):
    """Typed collision result; deliberately not interchangeable with ``bool``."""

    CLEAR_FOR_SIMULATION = "CLEAR_FOR_SIMULATION"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class InterlockChannel(str, Enum):
    ESTOP_CHAIN = "estop_chain"
    BOARD_ANTI_SHIFT = "board_anti_shift"
    GRAVITY_CONTAINMENT = "gravity_containment"
    CONTACT_GUARD = "contact_guard"


_REQUIRED_INTERLOCK_CHANNELS = (
    InterlockChannel.ESTOP_CHAIN,
    InterlockChannel.BOARD_ANTI_SHIFT,
    InterlockChannel.GRAVITY_CONTAINMENT,
    InterlockChannel.CONTACT_GUARD,
)


class InterlockEvidenceState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SimulationPrimitive(str, Enum):
    """Semantic simulation primitives with no firmware/wire representation."""

    TRANSIT = "SIMULATED_TRANSIT"
    MOVE_ABOVE = "SIMULATED_MOVE_ABOVE"
    DESCEND_PRECONTACT = "SIMULATED_DESCEND_PRECONTACT"
    CONTACT_INTENT = "SIMULATED_CONTACT_INTENT"
    RETRACT = "SIMULATED_RETRACT"
    PARK = "SIMULATED_PARK"


def _bounded_text(value: object, name: str, *, minimum: int = 1) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if value != value.strip() or not minimum <= len(value) <= _MAX_TEXT_LENGTH:
        raise AuthorizationV2Error(
            f"{name} must be trimmed and {minimum}..{_MAX_TEXT_LENGTH} characters"
        )
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise AuthorizationV2Error(f"{name} cannot contain control characters")
    return value


def _sha256(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AuthorizationV2Error(
            f"{name} must be exactly 64 lowercase hexadecimal characters"
        )
    return value


def _finite_nonnegative(value: object, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a non-boolean number")
    numeric = cast(int | float, value)
    # Bound integers before float conversion so an adversarial giant integer
    # cannot raise OverflowError outside a fail-closed validation path.
    if type(numeric) is int and not 0 <= numeric <= int(_MAX_MONOTONIC_S):
        raise AuthorizationV2Error(
            f"{name} must be finite, non-negative, and bounded"
        )
    result = float(numeric)
    if not math.isfinite(result) or not 0.0 <= result <= _MAX_MONOTONIC_S:
        raise AuthorizationV2Error(
            f"{name} must be finite, non-negative, and bounded"
        )
    # Remove the otherwise distinct JSON spelling of negative zero.
    return 0.0 if result == 0.0 else result


def _bounded_sequence(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be a non-boolean integer")
    if not 0 <= value <= _MAX_SAFE_INTEGER:
        raise AuthorizationV2Error(f"{name} is outside the bounded integer range")
    return value


def _require_exact_type(value: object, expected: type[Any], name: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be exactly {expected.__name__}")


def _validate_canonical_json(value: object) -> None:
    """Validate a bounded JSON tree before using it as hash material."""

    nodes = 0

    def visit(item: object, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_CANONICAL_NODES:
            raise AuthorizationV2Error("canonical JSON exceeds its node limit")
        if depth > _MAX_CANONICAL_DEPTH:
            raise AuthorizationV2Error("canonical JSON exceeds its nesting limit")
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            if not -_MAX_SAFE_INTEGER <= item <= _MAX_SAFE_INTEGER:
                raise AuthorizationV2Error(
                    "canonical JSON integer is outside the exact range"
                )
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise AuthorizationV2Error("canonical JSON float must be finite")
            return
        if type(item) is str:
            if len(item) > _MAX_TEXT_LENGTH:
                raise AuthorizationV2Error("canonical JSON string exceeds its limit")
            return
        if type(item) in (list, tuple):
            sequence = cast(list[object] | tuple[object, ...], item)
            if len(sequence) > _MAX_CANONICAL_COLLECTION:
                raise AuthorizationV2Error("canonical JSON array exceeds its limit")
            for child in sequence:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            if len(item) > _MAX_CANONICAL_COLLECTION:
                raise AuthorizationV2Error("canonical JSON object exceeds its limit")
            for key, child in item.items():
                if type(key) is not str or len(key) > _MAX_TEXT_LENGTH:
                    raise AuthorizationV2Error(
                        "canonical JSON object keys must be bounded strings"
                    )
                visit(child, depth + 1)
            return
        raise AuthorizationV2Error(
            f"unsupported canonical JSON value type: {type(item).__name__}"
        )

    visit(value, 0)


def canonical_record_sha256(record: Mapping[str, Any]) -> str:
    """Hash one bounded JSON record using one deterministic representation."""

    if type(record) is not dict:
        raise TypeError("record must be exactly dict")
    _validate_canonical_json(record)
    try:
        encoded = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # defensive parity with validation
        raise AuthorizationV2Error("record is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class NamedSha256:
    name: str
    sha256: str

    def __post_init__(self) -> None:
        _validate_named_hash(self)

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "sha256": self.sha256}


def _validate_named_hash(value: NamedSha256) -> None:
    _require_exact_type(value, NamedSha256, "named hash")
    _bounded_text(value.name, "named hash name")
    _sha256(value.sha256, "named hash sha256")


@dataclass(frozen=True, slots=True)
class ControllerSessionEvidence:
    """Exact installed controller plus one connection-session identity."""

    arm_hardware_id: str
    controller_hardware_id: str
    firmware_build_id: str
    firmware_sha256: str
    connection_session_id: str
    persistent_port_id: str
    transport_descriptor_sha256: str

    def __post_init__(self) -> None:
        _validate_controller(self)

    def to_dict(self) -> dict[str, str]:
        return {
            "arm_hardware_id": self.arm_hardware_id,
            "controller_hardware_id": self.controller_hardware_id,
            "firmware_build_id": self.firmware_build_id,
            "firmware_sha256": self.firmware_sha256,
            "connection_session_id": self.connection_session_id,
            "persistent_port_id": self.persistent_port_id,
            "transport_descriptor_sha256": self.transport_descriptor_sha256,
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_controller(value: ControllerSessionEvidence) -> None:
    _require_exact_type(value, ControllerSessionEvidence, "controller session evidence")
    for name in (
        "arm_hardware_id",
        "controller_hardware_id",
        "firmware_build_id",
        "connection_session_id",
        "persistent_port_id",
    ):
        _bounded_text(getattr(value, name), name)
    _sha256(value.firmware_sha256, "firmware_sha256")
    _sha256(value.transport_descriptor_sha256, "transport_descriptor_sha256")


@dataclass(frozen=True, slots=True)
class BuildReleaseIdentity:
    """Exact build/release receipt identity, explicitly evidence-only."""

    active_build_id: str
    build_snapshot_sha256: str
    manifest_id: str
    manifest_sha256: str
    release_receipt_id: str
    release_receipt_sha256: str
    scope: EvidenceOnlyReleaseScope

    def __post_init__(self) -> None:
        _validate_build_release(self)

    def to_dict(self) -> dict[str, str]:
        return {
            "active_build_id": self.active_build_id,
            "build_snapshot_sha256": self.build_snapshot_sha256,
            "manifest_id": self.manifest_id,
            "manifest_sha256": self.manifest_sha256,
            "release_receipt_id": self.release_receipt_id,
            "release_receipt_sha256": self.release_receipt_sha256,
            "scope": self.scope.value,
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_build_release(value: BuildReleaseIdentity) -> None:
    _require_exact_type(value, BuildReleaseIdentity, "build/release identity")
    for name in ("active_build_id", "manifest_id", "release_receipt_id"):
        _bounded_text(getattr(value, name), name)
    for name in (
        "build_snapshot_sha256",
        "manifest_sha256",
        "release_receipt_sha256",
    ):
        _sha256(getattr(value, name), name)
    if type(value.scope) is not EvidenceOnlyReleaseScope:
        raise TypeError("scope must be EvidenceOnlyReleaseScope")
    if value.scope is not EvidenceOnlyReleaseScope.SIMULATION_EVIDENCE_ONLY:
        raise AuthorizationV2Error("only simulation evidence scope is supported")


@dataclass(frozen=True, slots=True)
class CalibrationArtifactBinding:
    """One calibration artifact and its exact graph-edge hash bindings."""

    artifact_id: str
    artifact_sha256: str
    dependency_hashes: tuple[NamedSha256, ...]
    context_hashes: tuple[NamedSha256, ...]

    def __post_init__(self) -> None:
        _validate_calibration_artifact(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_sha256": self.artifact_sha256,
            "dependency_hashes": [item.to_dict() for item in self.dependency_hashes],
            "context_hashes": [item.to_dict() for item in self.context_hashes],
        }


def _validate_named_hash_tuple(value: tuple[NamedSha256, ...], name: str) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be tuple")
    if len(value) > _MAX_CALIBRATION_ARTIFACTS:
        raise AuthorizationV2Error(f"{name} exceeds its item limit")
    for item in value:
        _validate_named_hash(item)
    names = tuple(item.name for item in value)
    if len(names) != len(set(names)):
        raise AuthorizationV2Error(f"{name} cannot contain duplicate names")


def _validate_calibration_artifact(value: CalibrationArtifactBinding) -> None:
    _require_exact_type(value, CalibrationArtifactBinding, "calibration artifact binding")
    _bounded_text(value.artifact_id, "artifact_id")
    _sha256(value.artifact_sha256, "artifact_sha256")
    _validate_named_hash_tuple(value.dependency_hashes, "dependency_hashes")
    _validate_named_hash_tuple(value.context_hashes, "context_hashes")


KEYBOARD_REQUIRED_ARTIFACT_IDS = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(
    "keyboard"
)
PHONE_REQUIRED_ARTIFACT_IDS = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("phone")


def _device_for_capability(capability: SimulatedContactCapability) -> str:
    if capability is SimulatedContactCapability.KEYBOARD:
        return "keyboard"
    if capability is SimulatedContactCapability.PHONE:
        return "phone"
    raise AuthorizationV2Error("unsupported simulated contact capability")


@dataclass(frozen=True, slots=True)
class CalibrationClosureEvidence:
    """Complete capability-specific static Phase-1 artifact closure."""

    capability: SimulatedContactCapability
    graph_id: str
    graph_sha256: str
    artifacts: tuple[CalibrationArtifactBinding, ...]

    def __post_init__(self) -> None:
        _validate_calibration_closure(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_CLOSURE_SCHEMA,
            "authority": ZERO_AUTHORITY,
            "capability": self.capability.value,
            "graph_id": self.graph_id,
            "graph_sha256": self.graph_sha256,
            "artifacts": [item.to_dict() for item in self.artifacts],
        }

    @property
    def closure_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def calibration_closure_from_registry(
    registry: CalibrationRegistry,
    *,
    capability: SimulatedContactCapability,
    context_hashes: Mapping[str, str],
    manifest_id: str,
    active_build_id: str,
) -> CalibrationClosureEvidence:
    """Resolve an exact zero-authority closure from a filesystem registry.

    This adapter avoids accepting a caller-authored :class:`CalibrationResolution`
    or a manually assembled set of otherwise plausible hashes.  It asks the
    registry to revalidate every required artifact, then independently checks
    exact graph parent/context fields before snapshotting the artifact hashes.

    The result remains simulation evidence.  The registry uses unkeyed local
    hashes, so a future physical authorizer must additionally establish trusted
    storage or a signed external monotonic anchor; this function does not turn
    a writable filesystem into an attestation source.
    """

    if type(registry) is not CalibrationRegistry:
        raise TypeError("registry must be exactly CalibrationRegistry")
    if type(capability) is not SimulatedContactCapability:
        raise TypeError("capability must be SimulatedContactCapability")
    if not isinstance(context_hashes, Mapping):
        raise TypeError("context_hashes must be a mapping")
    manifest = _bounded_text(manifest_id, "manifest_id")
    active_build = _bounded_text(active_build_id, "active_build_id")

    device = _device_for_capability(capability)
    artifact_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
    required_context_ids = tuple(
        sorted(
            {
                context_id
                for artifact_id in artifact_ids
                for context_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                    artifact_id
                ].context_dependencies
            }
        )
    )
    if set(context_hashes) != set(required_context_ids):
        raise AuthorizationV2Error(
            f"{device} registry context must match its exact requirement set"
        )
    normalized_context: dict[str, str] = {}
    for context_id in required_context_ids:
        _bounded_text(context_id, "context dependency ID")
        normalized_context[context_id] = _sha256(
            context_hashes[context_id], f"context hash {context_id}"
        )

    assessment_context = {
        _STATIC_PHASE1_GRAPH_CONTEXT_ID: STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        **normalized_context,
    }
    resolution = registry.resolve(
        artifact_ids,
        assessment_context,
        manifest_id=manifest,
        active_build_id=active_build,
    )
    if set(resolution.assessments) != set(artifact_ids) or not resolution.all_valid:
        raise AuthorizationV2Error(
            f"{device} registry calibration closure is missing, stale, or non-valid"
        )

    loaded = {}
    for artifact_id in artifact_ids:
        artifact = registry.get_current(artifact_id)
        if artifact is None:
            raise AuthorizationV2Error(
                f"registry lost required calibration artifact {artifact_id}"
            )
        assessment = resolution.assessments[artifact_id]
        if (
            artifact.state is not ArtifactState.VALID
            or assessment.artifact_hash != artifact.content_hash
        ):
            raise AuthorizationV2Error(
                f"registry assessment changed for calibration artifact {artifact_id}"
            )
        loaded[artifact_id] = artifact

    bindings: list[CalibrationArtifactBinding] = []
    for artifact_id in artifact_ids:
        artifact = loaded[artifact_id]
        requirement = STATIC_OVERHEAD_PHASE1_GRAPH.requirements[artifact_id]
        expected_parents = {
            parent_id: loaded[parent_id].content_hash
            for parent_id in requirement.prerequisites
        }
        expected_dependencies = {
            _STATIC_PHASE1_GRAPH_CONTEXT_ID: STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
            **{
                context_id: normalized_context[context_id]
                for context_id in requirement.context_dependencies
            },
        }
        if dict(artifact.parent_artifact_hashes) != expected_parents:
            raise AuthorizationV2Error(
                f"{artifact_id} registry parents differ from the exact graph"
            )
        if dict(artifact.dependency_hashes) != expected_dependencies:
            raise AuthorizationV2Error(
                f"{artifact_id} registry contexts differ from the exact graph"
            )
        bindings.append(
            CalibrationArtifactBinding(
                artifact_id=artifact_id,
                artifact_sha256=artifact.content_hash,
                dependency_hashes=tuple(
                    NamedSha256(parent_id, expected_parents[parent_id])
                    for parent_id in requirement.prerequisites
                ),
                context_hashes=tuple(
                    NamedSha256(context_id, normalized_context[context_id])
                    for context_id in requirement.context_dependencies
                ),
            )
        )

    return CalibrationClosureEvidence(
        capability=capability,
        graph_id=STATIC_OVERHEAD_PHASE1_GRAPH.graph_id,
        graph_sha256=STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        artifacts=tuple(bindings),
    )


def _validate_calibration_closure(value: CalibrationClosureEvidence) -> None:
    _require_exact_type(value, CalibrationClosureEvidence, "calibration closure")
    if type(value.capability) is not SimulatedContactCapability:
        raise TypeError("calibration capability must be SimulatedContactCapability")
    if value.graph_id != STATIC_OVERHEAD_PHASE1_GRAPH.graph_id:
        raise AuthorizationV2Error("calibration graph identity mismatch")
    _sha256(value.graph_sha256, "calibration graph sha256")
    if value.graph_sha256 != STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash:
        raise AuthorizationV2Error("calibration graph hash mismatch")
    if type(value.artifacts) is not tuple:
        raise TypeError("calibration artifacts must be tuple")
    if not value.artifacts or len(value.artifacts) > _MAX_CALIBRATION_ARTIFACTS:
        raise AuthorizationV2Error("calibration artifacts are empty or exceed their limit")
    for artifact in value.artifacts:
        _validate_calibration_artifact(artifact)

    device = _device_for_capability(value.capability)
    expected_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
    actual_ids = tuple(artifact.artifact_id for artifact in value.artifacts)
    if actual_ids != expected_ids:
        raise AuthorizationV2Error(
            f"{device} calibration closure must match the exact ordered requirement set"
        )

    artifacts_by_id = {artifact.artifact_id: artifact for artifact in value.artifacts}
    observed_context_hashes: dict[str, str] = {}
    for artifact in value.artifacts:
        requirement = STATIC_OVERHEAD_PHASE1_GRAPH.requirements[artifact.artifact_id]
        dependency_names = tuple(item.name for item in artifact.dependency_hashes)
        if dependency_names != requirement.prerequisites:
            raise AuthorizationV2Error(
                f"{artifact.artifact_id} dependency IDs do not match the graph"
            )
        for dependency in artifact.dependency_hashes:
            if dependency.sha256 != artifacts_by_id[dependency.name].artifact_sha256:
                raise AuthorizationV2Error(
                    f"{artifact.artifact_id} dependency hash mismatch for {dependency.name}"
                )

        context_names = tuple(item.name for item in artifact.context_hashes)
        if context_names != requirement.context_dependencies:
            raise AuthorizationV2Error(
                f"{artifact.artifact_id} context IDs do not match the graph"
            )
        for context in artifact.context_hashes:
            prior = observed_context_hashes.setdefault(context.name, context.sha256)
            if prior != context.sha256:
                raise AuthorizationV2Error(
                    f"context hash is inconsistent for {context.name}"
                )


@dataclass(frozen=True, slots=True)
class CollisionTrajectoryEvidence:
    """Collision result bound to one exact simulated trajectory sequence."""

    report_sha256: str
    cleared_trajectory_sha256: str
    state: CollisionClearanceState

    def __post_init__(self) -> None:
        _validate_collision(self)

    def to_dict(self) -> dict[str, str]:
        return {
            "report_sha256": self.report_sha256,
            "cleared_trajectory_sha256": self.cleared_trajectory_sha256,
            "state": self.state.value,
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_collision(value: CollisionTrajectoryEvidence) -> None:
    _require_exact_type(value, CollisionTrajectoryEvidence, "collision evidence")
    _sha256(value.report_sha256, "collision report sha256")
    _sha256(value.cleared_trajectory_sha256, "cleared trajectory sha256")
    if type(value.state) is not CollisionClearanceState:
        raise TypeError("collision state must be CollisionClearanceState")


@dataclass(frozen=True, slots=True)
class InterlockChannelEvidence:
    """One raw-source-bound interlock sample."""

    channel: InterlockChannel
    source_id: str
    sequence: int
    captured_monotonic: float
    raw_sha256: str
    state: InterlockEvidenceState

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "captured_monotonic",
            _finite_nonnegative(self.captured_monotonic, "captured_monotonic"),
        )
        _validate_interlock_channel(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel.value,
            "source_id": self.source_id,
            "sequence": self.sequence,
            "captured_monotonic": self.captured_monotonic,
            "raw_sha256": self.raw_sha256,
            "state": self.state.value,
        }


def _validate_interlock_channel(value: InterlockChannelEvidence) -> None:
    _require_exact_type(value, InterlockChannelEvidence, "interlock channel evidence")
    if type(value.channel) is not InterlockChannel:
        raise TypeError("interlock channel must be InterlockChannel")
    _bounded_text(value.source_id, "interlock source_id")
    _bounded_sequence(value.sequence, "interlock sequence")
    _finite_nonnegative(value.captured_monotonic, "captured_monotonic")
    _sha256(value.raw_sha256, "interlock raw_sha256")
    if type(value.state) is not InterlockEvidenceState:
        raise TypeError("interlock state must be InterlockEvidenceState")


@dataclass(frozen=True, slots=True)
class InterlockEvidenceBundle:
    channels: tuple[InterlockChannelEvidence, ...]

    def __post_init__(self) -> None:
        _validate_interlock_bundle(self)

    def to_dict(self) -> dict[str, Any]:
        return {"channels": [channel.to_dict() for channel in self.channels]}

    @property
    def evidence_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_interlock_bundle(value: InterlockEvidenceBundle) -> None:
    _require_exact_type(value, InterlockEvidenceBundle, "interlock evidence bundle")
    if type(value.channels) is not tuple:
        raise TypeError("interlock channels must be tuple")
    for channel in value.channels:
        _validate_interlock_channel(channel)
    actual = tuple(channel.channel for channel in value.channels)
    if actual != _REQUIRED_INTERLOCK_CHANNELS:
        raise AuthorizationV2Error(
            "interlock bundle must contain every required channel in canonical order"
        )


@dataclass(frozen=True, slots=True)
class OperatorArmEvidence:
    """One operator-arm gesture, nonce-bound and short lived."""

    operator_id: str
    nonce_sha256: str
    armed_at_monotonic: float
    expires_at_monotonic: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "armed_at_monotonic",
            _finite_nonnegative(self.armed_at_monotonic, "armed_at_monotonic"),
        )
        object.__setattr__(
            self,
            "expires_at_monotonic",
            _finite_nonnegative(self.expires_at_monotonic, "expires_at_monotonic"),
        )
        _validate_operator_arm(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "nonce_sha256": self.nonce_sha256,
            "armed_at_monotonic": self.armed_at_monotonic,
            "expires_at_monotonic": self.expires_at_monotonic,
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_operator_arm(value: OperatorArmEvidence) -> None:
    _require_exact_type(value, OperatorArmEvidence, "operator-arm evidence")
    _bounded_text(value.operator_id, "operator_id")
    _sha256(value.nonce_sha256, "operator nonce sha256")
    armed = _finite_nonnegative(value.armed_at_monotonic, "armed_at_monotonic")
    expires = _finite_nonnegative(value.expires_at_monotonic, "expires_at_monotonic")
    if expires <= armed:
        raise AuthorizationV2Error("operator-arm expiry must follow its arm time")
    if expires - armed > _MAX_OPERATOR_ARM_WINDOW_S:
        raise AuthorizationV2Error("operator-arm window exceeds its safety bound")


@dataclass(frozen=True, slots=True)
class SimulationTrajectoryCommand:
    """Hashable semantic command that cannot become a RoArm wire command."""

    command_occurrence_id: str
    action_occurrence_id: str
    primitive: SimulationPrimitive
    target_state_sha256: str
    constraint_set_sha256: str

    def __post_init__(self) -> None:
        _validate_simulation_command(self)

    def to_dict(self) -> dict[str, str]:
        return {
            "command_occurrence_id": self.command_occurrence_id,
            "action_occurrence_id": self.action_occurrence_id,
            "primitive": self.primitive.value,
            "target_state_sha256": self.target_state_sha256,
            "constraint_set_sha256": self.constraint_set_sha256,
        }

    @property
    def command_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_simulation_command(value: SimulationTrajectoryCommand) -> None:
    _require_exact_type(value, SimulationTrajectoryCommand, "simulation command")
    _sha256(value.command_occurrence_id, "command occurrence ID")
    _sha256(value.action_occurrence_id, "action occurrence ID")
    if type(value.primitive) is not SimulationPrimitive:
        raise TypeError("primitive must be SimulationPrimitive")
    _sha256(value.target_state_sha256, "target state sha256")
    _sha256(value.constraint_set_sha256, "constraint set sha256")


def trajectory_sequence_sha256(
    commands: tuple[SimulationTrajectoryCommand, ...],
) -> str:
    """Hash an ordered trajectory; command order is part of the digest."""

    if type(commands) is not tuple:
        raise TypeError("commands must be tuple")
    if not commands or len(commands) > _MAX_COMMANDS:
        raise AuthorizationV2Error("commands are empty or exceed their limit")
    for command in commands:
        _validate_simulation_command(command)
    return canonical_record_sha256(
        {
            "schema": TRAJECTORY_SEQUENCE_SCHEMA,
            "ordered_command_hashes": [
                command.command_sha256 for command in commands
            ],
        }
    )


@dataclass(frozen=True, slots=True)
class AuthorizationEvidence:
    """Immutable raw input to the zero-authority issuance function."""

    capability: SimulatedContactCapability
    controller: ControllerSessionEvidence
    build_release: BuildReleaseIdentity
    calibration: CalibrationClosureEvidence
    collision: CollisionTrajectoryEvidence
    device_state_sha256: str
    interlocks: InterlockEvidenceBundle
    operator_arm: OperatorArmEvidence
    plan_sha256: str
    ordered_action_occurrence_ids: tuple[str, ...]
    ordered_commands: tuple[SimulationTrajectoryCommand, ...]

    def __post_init__(self) -> None:
        _validate_authorization_evidence(self)

    @property
    def ordered_trajectory_command_hashes(self) -> tuple[str, ...]:
        return tuple(command.command_sha256 for command in self.ordered_commands)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": AUTHORIZATION_V2_SCHEMA,
            "authority": ZERO_AUTHORITY,
            "capability": self.capability.value,
            "controller": self.controller.to_dict(),
            "build_release": self.build_release.to_dict(),
            "calibration": self.calibration.to_dict(),
            "collision": self.collision.to_dict(),
            "device_state_sha256": self.device_state_sha256,
            "interlocks": self.interlocks.to_dict(),
            "operator_arm": self.operator_arm.to_dict(),
            "plan_sha256": self.plan_sha256,
            "ordered_action_occurrence_ids": list(
                self.ordered_action_occurrence_ids
            ),
            "ordered_trajectory_command_hashes": list(
                self.ordered_trajectory_command_hashes
            ),
        }

    @property
    def context_sha256(self) -> str:
        return canonical_record_sha256(self.to_dict())


def _validate_authorization_evidence(value: AuthorizationEvidence) -> None:
    _require_exact_type(value, AuthorizationEvidence, "authorization evidence")
    if type(value.capability) is not SimulatedContactCapability:
        raise TypeError("capability must be SimulatedContactCapability")
    _validate_controller(value.controller)
    _validate_build_release(value.build_release)
    _validate_calibration_closure(value.calibration)
    _validate_collision(value.collision)
    _sha256(value.device_state_sha256, "device state sha256")
    _validate_interlock_bundle(value.interlocks)
    _validate_operator_arm(value.operator_arm)
    _sha256(value.plan_sha256, "plan sha256")
    if value.calibration.capability is not value.capability:
        raise AuthorizationV2Error("calibration capability does not match authorization")

    if type(value.ordered_action_occurrence_ids) is not tuple:
        raise TypeError("ordered action occurrence IDs must be tuple")
    actions = value.ordered_action_occurrence_ids
    if not actions or len(actions) > _MAX_ACTIONS:
        raise AuthorizationV2Error("action occurrences are empty or exceed their limit")
    for occurrence_id in actions:
        _sha256(occurrence_id, "action occurrence ID")
    if len(actions) != len(set(actions)):
        raise AuthorizationV2Error("action occurrence IDs must be unique")

    if type(value.ordered_commands) is not tuple:
        raise TypeError("ordered commands must be tuple")
    commands = value.ordered_commands
    if not commands or len(commands) > _MAX_COMMANDS:
        raise AuthorizationV2Error("ordered commands are empty or exceed their limit")
    for command in commands:
        _validate_simulation_command(command)
    command_ids = tuple(command.command_occurrence_id for command in commands)
    if len(command_ids) != len(set(command_ids)):
        raise AuthorizationV2Error("command occurrence IDs must be unique")

    grouped_actions: list[str] = []
    last_action: str | None = None
    closed_actions: set[str] = set()
    for command in commands:
        action = command.action_occurrence_id
        if action != last_action:
            if action in closed_actions:
                raise AuthorizationV2Error(
                    "commands for an action occurrence must be contiguous"
                )
            if last_action is not None:
                closed_actions.add(last_action)
            grouped_actions.append(action)
            last_action = action
    if tuple(grouped_actions) != actions:
        raise AuthorizationV2Error(
            "command action grouping must exactly match ordered action occurrences"
        )

    calculated_trajectory = trajectory_sequence_sha256(commands)
    if value.collision.cleared_trajectory_sha256 != calculated_trajectory:
        raise AuthorizationV2Error(
            "collision evidence is not bound to the ordered trajectory"
        )
    if value.collision.state is not CollisionClearanceState.CLEAR_FOR_SIMULATION:
        raise AuthorizationV2Error("collision evidence is not clear for simulation")


@dataclass(frozen=True, slots=True)
class AuthorizationContinuityEvidence:
    """Fresh, consumption-time bindings checked before each cursor advance."""

    controller: ControllerSessionEvidence
    build_release: BuildReleaseIdentity
    calibration_closure_sha256: str
    collision_report_sha256: str
    trajectory_sha256: str
    device_state_sha256: str
    interlocks: InterlockEvidenceBundle
    operator_nonce_sha256: str
    plan_sha256: str

    def __post_init__(self) -> None:
        _validate_continuity(self)


def _validate_continuity(value: AuthorizationContinuityEvidence) -> None:
    _require_exact_type(value, AuthorizationContinuityEvidence, "continuity evidence")
    _validate_controller(value.controller)
    _validate_build_release(value.build_release)
    for name in (
        "calibration_closure_sha256",
        "collision_report_sha256",
        "trajectory_sha256",
        "device_state_sha256",
        "operator_nonce_sha256",
        "plan_sha256",
    ):
        _sha256(getattr(value, name), name)
    _validate_interlock_bundle(value.interlocks)


def continuity_from_authorization(
    evidence: AuthorizationEvidence,
    *,
    interlocks: InterlockEvidenceBundle | None = None,
) -> AuthorizationContinuityEvidence:
    """Project the immutable issuance bindings into a consumption-time record."""

    _validate_authorization_evidence(evidence)
    return AuthorizationContinuityEvidence(
        controller=evidence.controller,
        build_release=evidence.build_release,
        calibration_closure_sha256=evidence.calibration.closure_sha256,
        collision_report_sha256=evidence.collision.report_sha256,
        trajectory_sha256=evidence.collision.cleared_trajectory_sha256,
        device_state_sha256=evidence.device_state_sha256,
        interlocks=evidence.interlocks if interlocks is None else interlocks,
        operator_nonce_sha256=evidence.operator_arm.nonce_sha256,
        plan_sha256=evidence.plan_sha256,
    )


@dataclass(frozen=True, slots=True)
class _ExpectedCommand:
    ordinal: int
    action_occurrence_id: str
    command_sha256: str


_PERMIT_ISSUER = object()
_RECEIPT_ISSUER = object()


@dataclass(frozen=True, slots=True)
class SimulationCommandReceipt:
    """Proof of one cursor advance; deliberately contains no command payload."""

    _issuer: object = field(default=None, init=False, repr=False, compare=False)
    permit_id: str
    context_sha256: str
    ordinal: int
    action_occurrence_id: str
    command_sha256: str
    consumed_at_monotonic: float
    authority: str = ZERO_AUTHORITY
    schema: str = SIMULATION_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if self._issuer is not _RECEIPT_ISSUER:
            raise AuthorizationV2Error(
                "simulation command receipts may only be issued by the cursor"
            )
        if self.schema != SIMULATION_RECEIPT_SCHEMA:
            raise AuthorizationV2Error("unsupported simulation receipt schema")
        if self.authority != ZERO_AUTHORITY:
            raise AuthorizationV2Error("simulation receipt authority changed")
        _sha256(self.permit_id, "receipt permit_id")
        _sha256(self.context_sha256, "receipt context_sha256")
        _bounded_sequence(self.ordinal, "receipt ordinal")
        _sha256(self.action_occurrence_id, "receipt action occurrence ID")
        _sha256(self.command_sha256, "receipt command_sha256")
        object.__setattr__(
            self,
            "consumed_at_monotonic",
            _finite_nonnegative(
                self.consumed_at_monotonic, "receipt consumed_at_monotonic"
            ),
        )

    @classmethod
    def _issued(
        cls,
        *,
        permit_id: str,
        context_sha256: str,
        ordinal: int,
        action_occurrence_id: str,
        command_sha256: str,
        consumed_at_monotonic: float,
    ) -> "SimulationCommandReceipt":
        """Construct internally without exposing the issuer seal to callers."""

        receipt = object.__new__(cls)
        for name, value in (
            ("_issuer", _RECEIPT_ISSUER),
            ("permit_id", permit_id),
            ("context_sha256", context_sha256),
            ("ordinal", ordinal),
            ("action_occurrence_id", action_occurrence_id),
            ("command_sha256", command_sha256),
            ("consumed_at_monotonic", consumed_at_monotonic),
            ("authority", ZERO_AUTHORITY),
            ("schema", SIMULATION_RECEIPT_SCHEMA),
        ):
            object.__setattr__(receipt, name, value)
        receipt.__post_init__()
        return receipt

    def to_dict(self) -> dict[str, Any]:
        # Revalidate on emission so even deliberate object.__setattr__ bypass
        # of the frozen dataclass cannot serialize an authoritative-looking
        # altered receipt.
        self.__post_init__()
        return {
            "schema": self.schema,
            "authority": self.authority,
            "permit_id": self.permit_id,
            "context_sha256": self.context_sha256,
            "ordinal": self.ordinal,
            "action_occurrence_id": self.action_occurrence_id,
            "command_sha256": self.command_sha256,
            "consumed_at_monotonic": self.consumed_at_monotonic,
            "live_transport_authorized": False,
            "hardware_commands_generated": 0,
        }


class OrderedSimulationPermit:
    """Thread-safe, one-way cursor over exact simulated commands.

    This class intentionally has no ``__call__``, ``allows``, ``to_message``,
    or goal payload API.  Consequently it cannot satisfy the live transport's
    permit interface and cannot expose a command that could be encoded as
    ``T=104``.
    """

    __slots__ = (
        "_bound_build_sha256",
        "_bound_calibration_sha256",
        "_bound_collision_report_sha256",
        "_bound_controller_sha256",
        "_bound_device_state_sha256",
        "_bound_interlock_sources",
        "_initial_interlock_samples",
        "_bound_operator_nonce_sha256",
        "_bound_plan_sha256",
        "_bound_trajectory_sha256",
        "_complete",
        "_context_sha256",
        "_cursor",
        "_expected_commands",
        "_expires_at_monotonic",
        "_interlock_max_age_s",
        "_issued_at_monotonic",
        "_last_interlock_sequences",
        "_last_interlock_raw_hashes",
        "_last_interlock_timestamps",
        "_lock",
        "_permit_id",
        "_revoked",
        "_sealed",
    )

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AuthorizationV2Error(
                "ordered simulation permit state is internally sealed"
            )
        object.__setattr__(self, name, value)

    def __init__(
        self,
        *,
        _issuer: object,
        evidence: AuthorizationEvidence,
        issued_at_monotonic: float,
        expires_at_monotonic: float,
        interlock_max_age_s: float,
    ) -> None:
        if _issuer is not _PERMIT_ISSUER:
            raise AuthorizationV2Error(
                "ordered simulation permits may only be issued by the validator"
            )
        _validate_authorization_evidence(evidence)
        issued = _finite_nonnegative(issued_at_monotonic, "issued_at_monotonic")
        expires = _finite_nonnegative(expires_at_monotonic, "expires_at_monotonic")
        max_age = _finite_nonnegative(interlock_max_age_s, "interlock_max_age_s")
        if expires <= issued or max_age <= 0.0:
            raise AuthorizationV2Error("permit timing bounds are invalid")

        context_sha256 = evidence.context_sha256
        expected = tuple(
            _ExpectedCommand(index, command.action_occurrence_id, command.command_sha256)
            for index, command in enumerate(evidence.ordered_commands)
        )
        permit_id = canonical_record_sha256(
            {
                "schema": SIMULATION_PERMIT_SCHEMA,
                "authority": ZERO_AUTHORITY,
                "context_sha256": context_sha256,
                "issued_at_monotonic": issued,
                "expires_at_monotonic": expires,
            }
        )

        # Snapshot primitive hashes and IDs.  Never retain caller-owned evidence
        # objects as the source of future authorization decisions.
        self._context_sha256 = context_sha256
        self._permit_id = permit_id
        self._issued_at_monotonic = issued
        self._expires_at_monotonic = expires
        self._interlock_max_age_s = max_age
        self._bound_controller_sha256 = evidence.controller.evidence_sha256
        self._bound_build_sha256 = evidence.build_release.evidence_sha256
        self._bound_calibration_sha256 = evidence.calibration.closure_sha256
        self._bound_collision_report_sha256 = evidence.collision.report_sha256
        self._bound_trajectory_sha256 = evidence.collision.cleared_trajectory_sha256
        self._bound_device_state_sha256 = evidence.device_state_sha256
        self._bound_operator_nonce_sha256 = evidence.operator_arm.nonce_sha256
        self._bound_plan_sha256 = evidence.plan_sha256
        self._bound_interlock_sources = tuple(
            (channel.channel, channel.source_id)
            for channel in evidence.interlocks.channels
        )
        self._initial_interlock_samples = MappingProxyType(
            {
                channel.channel: (
                    channel.sequence,
                    channel.captured_monotonic,
                    channel.raw_sha256,
                )
                for channel in evidence.interlocks.channels
            }
        )
        self._last_interlock_sequences = MappingProxyType(
            {channel.channel: None for channel in evidence.interlocks.channels}
        )
        self._last_interlock_timestamps = MappingProxyType(
            {channel.channel: None for channel in evidence.interlocks.channels}
        )
        self._last_interlock_raw_hashes = MappingProxyType(
            {channel.channel: None for channel in evidence.interlocks.channels}
        )
        self._expected_commands = expected
        self._cursor = 0
        self._revoked = False
        self._complete = False
        self._lock = threading.Lock()
        object.__setattr__(self, "_sealed", True)

    def __copy__(self) -> NoReturn:
        raise AuthorizationV2Error("ordered simulation permits cannot be copied")

    def __deepcopy__(self, memo: object) -> NoReturn:
        del memo
        raise AuthorizationV2Error("ordered simulation permits cannot be copied")

    def __reduce_ex__(self, protocol: object) -> NoReturn:
        del protocol
        raise AuthorizationV2Error("ordered simulation permits cannot be serialized")

    @property
    def permit_id(self) -> str:
        return self._permit_id

    @property
    def context_sha256(self) -> str:
        return self._context_sha256

    @property
    def authority(self) -> str:
        return ZERO_AUTHORITY

    @property
    def revoked(self) -> bool:
        with self._lock:
            return self._revoked

    @property
    def complete(self) -> bool:
        with self._lock:
            return self._complete

    @property
    def next_ordinal(self) -> int | None:
        with self._lock:
            return None if self._complete else self._cursor

    @property
    def remaining_commands(self) -> int:
        with self._lock:
            return len(self._expected_commands) - self._cursor

    @property
    def can_authorize_live_transport(self) -> bool:
        return False

    def revoke(self) -> None:
        with self._lock:
            object.__setattr__(self, "_revoked", True)

    def _deny(self, detail: str) -> NoReturn:
        object.__setattr__(self, "_revoked", True)
        raise AuthorizationV2Error(detail)

    def _check_interlocks(
        self,
        bundle: InterlockEvidenceBundle,
        *,
        now_monotonic: float,
    ) -> tuple[tuple[InterlockChannel, int, float], ...]:
        sources = tuple(
            (channel.channel, channel.source_id) for channel in bundle.channels
        )
        if sources != self._bound_interlock_sources:
            self._deny("interlock source identity drifted")
        accepted: list[tuple[InterlockChannel, int, float]] = []
        for channel in bundle.channels:
            if channel.state is not InterlockEvidenceState.PASS:
                self._deny(f"interlock {channel.channel.value} is not PASS")
            age = now_monotonic - channel.captured_monotonic
            if age < 0.0 or age > self._interlock_max_age_s:
                self._deny(f"interlock {channel.channel.value} is stale or future-dated")
            last_sequence = self._last_interlock_sequences[channel.channel]
            last_timestamp = self._last_interlock_timestamps[channel.channel]
            last_raw_sha256 = self._last_interlock_raw_hashes[channel.channel]
            if last_sequence is None:
                baseline_sequence, baseline_timestamp, baseline_raw_sha256 = (
                    self._initial_interlock_samples[channel.channel]
                )
                if channel.sequence < baseline_sequence:
                    self._deny(
                        f"interlock {channel.channel.value} sequence rolled back"
                    )
                if channel.captured_monotonic < baseline_timestamp:
                    self._deny(
                        f"interlock {channel.channel.value} timestamp rolled back"
                    )
                if channel.sequence == baseline_sequence and (
                    channel.captured_monotonic != baseline_timestamp
                    or channel.raw_sha256 != baseline_raw_sha256
                ):
                    self._deny(
                        f"interlock {channel.channel.value} reused a sequence with changed evidence"
                    )
                if channel.sequence > baseline_sequence and (
                    channel.captured_monotonic <= baseline_timestamp
                    or channel.raw_sha256 == baseline_raw_sha256
                ):
                    self._deny(
                        f"interlock {channel.channel.value} did not provide a new raw sample"
                    )
            else:
                if last_timestamp is None or last_raw_sha256 is None:
                    self._deny("internal interlock cursor state is inconsistent")
                if channel.sequence <= last_sequence:
                    self._deny(
                        f"interlock {channel.channel.value} sequence did not advance"
                    )
                if channel.captured_monotonic <= last_timestamp:
                    self._deny(
                        f"interlock {channel.channel.value} timestamp did not advance"
                    )
                if channel.raw_sha256 == last_raw_sha256:
                    self._deny(
                        f"interlock {channel.channel.value} raw evidence was replayed"
                    )
            accepted.append(
                (channel.channel, channel.sequence, channel.captured_monotonic)
            )
        return tuple(accepted)

    def consume_next(
        self,
        *,
        ordinal: int,
        action_occurrence_id: str,
        command: SimulationTrajectoryCommand,
        continuity: AuthorizationContinuityEvidence,
        now_monotonic: float,
    ) -> SimulationCommandReceipt:
        """Atomically consume only the next exact semantic simulation command.

        ``now_monotonic`` is caller-supplied for deterministic simulation.  A
        future physical authorization service must replace it with a trusted
        clock read inside an isolated authority process; this API is therefore
        intentionally not promotable to live hardware.
        """

        with self._lock:
            if self._revoked:
                raise AuthorizationV2Error("ordered simulation permit is revoked")
            if self._complete:
                raise AuthorizationV2Error("ordered simulation permit is exhausted")
            try:
                now = _finite_nonnegative(now_monotonic, "now_monotonic")
                _bounded_sequence(ordinal, "ordinal")
                _sha256(action_occurrence_id, "action occurrence ID")
                _validate_simulation_command(command)
                _validate_continuity(continuity)
            except (
                AuthorizationV2Error,
                TypeError,
                AttributeError,
                OverflowError,
            ) as exc:
                self._deny(f"invalid consumption evidence: {exc}")

            if now >= self._expires_at_monotonic:
                self._deny("ordered simulation permit expired")
            if continuity.controller.evidence_sha256 != self._bound_controller_sha256:
                self._deny("controller, connection session, or port identity drifted")
            if continuity.build_release.evidence_sha256 != self._bound_build_sha256:
                self._deny("build/release identity drifted")
            if continuity.calibration_closure_sha256 != self._bound_calibration_sha256:
                self._deny("calibration closure drifted")
            if continuity.collision_report_sha256 != self._bound_collision_report_sha256:
                self._deny("collision report drifted")
            if continuity.trajectory_sha256 != self._bound_trajectory_sha256:
                self._deny("collision-cleared trajectory drifted")
            if continuity.device_state_sha256 != self._bound_device_state_sha256:
                self._deny("device state drifted")
            if continuity.operator_nonce_sha256 != self._bound_operator_nonce_sha256:
                self._deny("operator-arm nonce drifted")
            if continuity.plan_sha256 != self._bound_plan_sha256:
                self._deny("plan hash drifted")

            accepted_interlocks = self._check_interlocks(
                continuity.interlocks, now_monotonic=now
            )
            expected = self._expected_commands[self._cursor]
            if ordinal != expected.ordinal:
                self._deny("command ordinal was skipped, duplicated, or reordered")
            if action_occurrence_id != expected.action_occurrence_id:
                self._deny("action occurrence was skipped, duplicated, or reordered")
            if command.action_occurrence_id != action_occurrence_id:
                self._deny("command is bound to a different action occurrence")
            if command.command_sha256 != expected.command_sha256:
                self._deny("simulation command was mutated or reordered")

            sequences: dict[InterlockChannel, int | None] = dict(
                self._last_interlock_sequences
            )
            timestamps: dict[InterlockChannel, float | None] = dict(
                self._last_interlock_timestamps
            )
            raw_hashes: dict[InterlockChannel, str | None] = dict(
                self._last_interlock_raw_hashes
            )
            for channel, sequence, timestamp in accepted_interlocks:
                sequences[channel] = sequence
                timestamps[channel] = timestamp
            for channel_evidence in continuity.interlocks.channels:
                raw_hashes[channel_evidence.channel] = channel_evidence.raw_sha256
            object.__setattr__(
                self, "_last_interlock_sequences", MappingProxyType(sequences)
            )
            object.__setattr__(
                self, "_last_interlock_timestamps", MappingProxyType(timestamps)
            )
            object.__setattr__(
                self, "_last_interlock_raw_hashes", MappingProxyType(raw_hashes)
            )
            object.__setattr__(self, "_cursor", self._cursor + 1)
            if self._cursor == len(self._expected_commands):
                object.__setattr__(self, "_complete", True)
            return SimulationCommandReceipt._issued(
                permit_id=self._permit_id,
                context_sha256=self._context_sha256,
                ordinal=ordinal,
                action_occurrence_id=action_occurrence_id,
                command_sha256=command.command_sha256,
                consumed_at_monotonic=now,
            )


def _validate_fresh_passing_interlocks(
    bundle: InterlockEvidenceBundle,
    *,
    now_monotonic: float,
    max_age_s: float,
) -> None:
    for channel in bundle.channels:
        if channel.state is not InterlockEvidenceState.PASS:
            raise AuthorizationV2Error(
                f"interlock {channel.channel.value} is not PASS at issuance"
            )
        age = now_monotonic - channel.captured_monotonic
        if age < 0.0 or age > max_age_s:
            raise AuthorizationV2Error(
                f"interlock {channel.channel.value} is stale or future-dated at issuance"
            )


def issue_ordered_simulation_permit(
    evidence: AuthorizationEvidence,
    *,
    ttl_s: float,
    now_monotonic: float,
    interlock_max_age_s: float = 0.5,
) -> OrderedSimulationPermit:
    """Validate all evidence and issue a non-live ordered cursor.

    The returned cursor is intentionally incompatible with the live RoArm
    transport.  Issuance does not release hardware power, motion, or contact.
    Its explicit time is a deterministic test input, not a trusted-clock
    attestation; physical promotion requires an isolated service-owned clock.
    """

    _validate_authorization_evidence(evidence)
    now = _finite_nonnegative(now_monotonic, "now_monotonic")
    ttl = _finite_nonnegative(ttl_s, "ttl_s")
    max_age = _finite_nonnegative(interlock_max_age_s, "interlock_max_age_s")
    if ttl <= 0.0 or max_age <= 0.0:
        raise AuthorizationV2Error("ttl_s and interlock_max_age_s must be positive")
    if ttl > _MAX_PERMIT_TTL_S:
        raise AuthorizationV2Error("ttl_s exceeds the zero-authority safety bound")
    if max_age > _MAX_INTERLOCK_AGE_S:
        raise AuthorizationV2Error(
            "interlock_max_age_s exceeds the zero-authority safety bound"
        )
    if now < evidence.operator_arm.armed_at_monotonic:
        raise AuthorizationV2Error("operator-arm evidence is future-dated")
    if now >= evidence.operator_arm.expires_at_monotonic:
        raise AuthorizationV2Error("operator-arm evidence expired before issuance")
    _validate_fresh_passing_interlocks(
        evidence.interlocks, now_monotonic=now, max_age_s=max_age
    )
    expires = min(now + ttl, evidence.operator_arm.expires_at_monotonic)
    if expires <= now:
        raise AuthorizationV2Error("permit has no positive lifetime")
    return OrderedSimulationPermit(
        _issuer=_PERMIT_ISSUER,
        evidence=evidence,
        issued_at_monotonic=now,
        expires_at_monotonic=expires,
        interlock_max_age_s=max_age,
    )


__all__ = [
    "AUTHORIZATION_V2_SCHEMA",
    "CALIBRATION_CLOSURE_SCHEMA",
    "KEYBOARD_REQUIRED_ARTIFACT_IDS",
    "PHONE_REQUIRED_ARTIFACT_IDS",
    "SIMULATION_PERMIT_SCHEMA",
    "SIMULATION_RECEIPT_SCHEMA",
    "TRAJECTORY_SEQUENCE_SCHEMA",
    "ZERO_AUTHORITY",
    "AuthorizationContinuityEvidence",
    "AuthorizationEvidence",
    "AuthorizationV2Error",
    "BuildReleaseIdentity",
    "CalibrationArtifactBinding",
    "CalibrationClosureEvidence",
    "CollisionClearanceState",
    "CollisionTrajectoryEvidence",
    "ControllerSessionEvidence",
    "EvidenceOnlyReleaseScope",
    "InterlockChannel",
    "InterlockChannelEvidence",
    "InterlockEvidenceBundle",
    "InterlockEvidenceState",
    "NamedSha256",
    "OperatorArmEvidence",
    "OrderedSimulationPermit",
    "SimulatedContactCapability",
    "SimulationCommandReceipt",
    "SimulationPrimitive",
    "SimulationTrajectoryCommand",
    "calibration_closure_from_registry",
    "canonical_record_sha256",
    "continuity_from_authorization",
    "issue_ordered_simulation_permit",
    "trajectory_sequence_sha256",
]
