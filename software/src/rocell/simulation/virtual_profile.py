"""Strict loading for the locked virtual-commissioning sensitivity profile.

The profile records one previously screened pre-hardware hypothesis so virtual
sessions do not rerun the multi-minute layout search.  It remains an unmeasured
simulation overlay with permanently zero physical authority.  Loading validates
the exact locked bytes, reconstructs the typed :class:`ReachStudyInput`, and
re-derives its solver transform through the pinned URDF instead of trusting the
serialized matrices independently.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Protocol

from rocell.geometry import RigidTransform
from rocell.models.frames import Point3Mm, Transform

from ._validation import SimulationSourceError, finite, identifier, mapping, sequence

if TYPE_CHECKING:
    from rocell.application.reach_optimizer import ReachStudyInput


VIRTUAL_COMMISSIONING_PROFILE_SCHEMA = "rocell.virtual_commissioning_profile.v1"
VIRTUAL_COMMISSIONING_PROFILE_STATUS = "UNMEASURED_SENSITIVITY_OVERLAY"
DEFAULT_VIRTUAL_COMMISSIONING_PROFILE = (
    "software/config/virtual_commissioning_profile.json"
)
MAX_VIRTUAL_COMMISSIONING_PROFILE_BYTES = 65_536

_PROFILE_ID = "ROCELL-VIRTUAL-COMMISSIONING-RANK1-001"
_STUDY_INPUT_ID = "reach-944d7463f4c67905"
_LAYOUT_REPORT_HASH = (
    "3b65e3bca509f7c7e1583e5801e189639ab9e40cbf30827b71794752cd7259b4"
)
_MISSION_COVERAGE_HASH = (
    "c67ac5d2cece745077ac631304b80f51a19c981edd107812ffa716673fbf2cd4"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOLERANCE = 1e-9


class VirtualCommissioningProfileError(SimulationSourceError):
    """The locked virtual profile is malformed, stale, or over-authoritative."""


class _BundleArtifact(Protocol):
    path: Path
    sha256: str


class _BundleLock(Protocol):
    bundle_id: str

    def artifact(self, artifact_id: str) -> _BundleArtifact: ...


class _Snapshot(Protocol):
    manifest_id: str
    design_revision: str


class _Scenario(Protocol):
    model_path: Path
    model_sha256: str
    board_T_world: RigidTransform


class _Board(Protocol):
    @property
    def minimum(self) -> Point3Mm: ...

    @property
    def maximum(self) -> Point3Mm: ...


class _Scene(Protocol):
    board: _Board
    arm_clamp_rear_edge_x_range_mm: tuple[float, float]


class VirtualProfileContext(Protocol):
    snapshot: _Snapshot
    bundle_lock: _BundleLock
    scenario: _Scenario
    scene: _Scene


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise VirtualCommissioningProfileError(
            f"{label} fields differ; missing={missing}, extra={extra}"
        )


def _digest(value: object, label: str) -> str:
    result = identifier(value, label).lower()
    if _SHA256.fullmatch(result) is None:
        raise VirtualCommissioningProfileError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return result


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VirtualCommissioningProfileError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise VirtualCommissioningProfileError(
        f"Nonfinite JSON constant {value!r} is not allowed"
    )


def _read_locked_document(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    """Capture, hash, and decode one bounded exact byte snapshot."""

    expected = _digest(expected_sha256, "virtual profile expected sha256")
    source = Path(path).resolve()
    chunks: list[bytes] = []
    byte_count = 0
    try:
        with source.open("rb") as stream:
            while True:
                remaining_with_sentinel = (
                    MAX_VIRTUAL_COMMISSIONING_PROFILE_BYTES - byte_count + 1
                )
                chunk = stream.read(min(16_384, remaining_with_sentinel))
                if not chunk:
                    break
                byte_count += len(chunk)
                if byte_count > MAX_VIRTUAL_COMMISSIONING_PROFILE_BYTES:
                    raise VirtualCommissioningProfileError(
                        "Virtual commissioning profile exceeds its byte limit"
                    )
                chunks.append(chunk)
    except OSError as exc:
        raise VirtualCommissioningProfileError(
            f"Cannot read locked virtual profile {source}"
        ) from exc
    payload = b"".join(chunks)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise VirtualCommissioningProfileError(
            "Virtual commissioning profile byte hash mismatch"
        )
    try:
        decoded = payload.decode("utf-8")
        value = json.loads(
            decoded,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VirtualCommissioningProfileError(
            "Virtual commissioning profile is not strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise VirtualCommissioningProfileError(
            "Virtual commissioning profile must contain one JSON object"
        )
    return value, actual


def _transform(
    value: object,
    *,
    parent_frame: str,
    child_frame: str,
    label: str,
) -> RigidTransform:
    raw = sequence(value, 16, f"{label} matrix")
    matrix_values = tuple(finite(item, f"{label} matrix element") for item in raw)
    try:
        return RigidTransform.from_transform(
            Transform(parent_frame, child_frame, matrix_values)
        )
    except (TypeError, ValueError) as exc:
        raise VirtualCommissioningProfileError(
            f"{label} is not a valid rigid transform: {exc}"
        ) from exc


def _decode_study_input(value: object) -> ReachStudyInput:
    # Keep this application-layer dependency out of module import time.  The
    # application context imports ``rocell.simulation`` while it is itself
    # being initialized, so an eager reverse import would create a cycle.
    from rocell.application.reach_optimizer import ReachStudyInput

    study = mapping(value, "virtual profile study_input")
    _exact_keys(
        study,
        {
            "study_input_id",
            "physical_placement_input",
            "derived_solver_transform",
            "route_tool_lengths_mm",
            "canonical_context_modified",
            "physical_release_effect",
        },
        "virtual profile study_input",
    )
    if study.get("canonical_context_modified") is not False:
        raise VirtualCommissioningProfileError(
            "Virtual study input cannot modify the canonical context"
        )
    if study.get("physical_release_effect") != "NONE":
        raise VirtualCommissioningProfileError(
            "Virtual study input cannot affect physical release"
        )

    placement = mapping(
        study.get("physical_placement_input"),
        "virtual profile physical placement",
    )
    _exact_keys(
        placement,
        {
            "transform",
            "ru_frame",
            "rear_clamp_contact_x_board_mm",
            "clamp_to_base_axis_x_mm",
            "base_axis_x_board_mm",
            "rear_edge_to_base_axis_y_mm",
            "base_link_z_board_mm",
            "base_yaw_board_rad",
            "matrix_row_major",
        },
        "virtual profile physical placement",
    )
    if placement.get("transform") != "B_T_Ru" or placement.get("ru_frame") != "base_link":
        raise VirtualCommissioningProfileError(
            "Virtual physical placement must be B_T_Ru for base_link"
        )

    derived = mapping(
        study.get("derived_solver_transform"),
        "virtual profile derived solver transform",
    )
    _exact_keys(
        derived,
        {"transform", "wv_frame", "derivation", "matrix_row_major"},
        "virtual profile derived solver transform",
    )
    if (
        derived.get("transform") != "B_T_Wv"
        or derived.get("wv_frame") != "world"
        or derived.get("derivation") != "B_T_Ru * inverse(Wv_T_Ru)"
    ):
        raise VirtualCommissioningProfileError(
            "Virtual solver transform lost its B_T_Wv derivation contract"
        )

    tools = mapping(study.get("route_tool_lengths_mm"), "virtual route tool lengths")
    _exact_keys(tools, {"keyboard", "phone"}, "virtual route tool lengths")
    result = ReachStudyInput(
        rear_clamp_contact_x_board_mm=finite(
            placement.get("rear_clamp_contact_x_board_mm"),
            "rear clamp contact X",
        ),
        clamp_to_base_axis_x_mm=finite(
            placement.get("clamp_to_base_axis_x_mm"),
            "clamp-to-axis X",
        ),
        base_axis_x_board_mm=finite(
            placement.get("base_axis_x_board_mm"),
            "base axis X",
        ),
        rear_edge_to_base_axis_y_mm=finite(
            placement.get("rear_edge_to_base_axis_y_mm"),
            "rear-edge-to-axis Y",
        ),
        base_link_z_board_mm=finite(
            placement.get("base_link_z_board_mm"),
            "base-link Z",
        ),
        base_yaw_board_rad=finite(
            placement.get("base_yaw_board_rad"),
            "base yaw",
        ),
        keyboard_tool_length_mm=finite(tools.get("keyboard"), "keyboard tool length"),
        phone_tool_length_mm=finite(tools.get("phone"), "phone tool length"),
        board_T_base_link=_transform(
            placement.get("matrix_row_major"),
            parent_frame="board",
            child_frame="base_link",
            label="B_T_Ru",
        ),
        board_T_vendor_world=_transform(
            derived.get("matrix_row_major"),
            parent_frame="board",
            child_frame="world",
            label="B_T_Wv",
        ),
    )
    declared_id = identifier(study.get("study_input_id"), "study input id")
    if declared_id != result.study_input_id:
        raise VirtualCommissioningProfileError(
            "Virtual study_input_id does not match its content-derived identity"
        )
    if result.study_input_id != _STUDY_INPUT_ID:
        raise VirtualCommissioningProfileError(
            "Virtual profile selected an unexpected rank-1 study input"
        )
    return result


@dataclass(frozen=True, slots=True)
class VirtualCommissioningProfile:
    """Typed, source-bound rank-1 overlay for zero-authority virtual sessions."""

    profile_id: str
    system_manifest_id: str
    design_revision: str
    simulation_bundle_id: str
    source_layout_report_hash: str
    source_mission_route_coverage_hash: str
    study_input: ReachStudyInput
    park_probe_id: str
    park_point_board: Point3Mm
    source_path: Path
    source_sha256: str
    schema: str = VIRTUAL_COMMISSIONING_PROFILE_SCHEMA
    status: str = VIRTUAL_COMMISSIONING_PROFILE_STATUS
    simulation_only: bool = True
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        from rocell.application.reach_optimizer import ReachStudyInput

        for name in (
            "profile_id",
            "system_manifest_id",
            "design_revision",
            "simulation_bundle_id",
            "park_probe_id",
        ):
            object.__setattr__(self, name, identifier(getattr(self, name), name))
        object.__setattr__(
            self,
            "source_layout_report_hash",
            _digest(self.source_layout_report_hash, "source layout report hash"),
        )
        object.__setattr__(
            self,
            "source_mission_route_coverage_hash",
            _digest(
                self.source_mission_route_coverage_hash,
                "source mission-route coverage hash",
            ),
        )
        object.__setattr__(self, "source_sha256", _digest(self.source_sha256, "source sha256"))
        object.__setattr__(self, "source_path", Path(self.source_path).resolve())
        if not isinstance(self.study_input, ReachStudyInput):
            raise TypeError("study_input must be a ReachStudyInput")
        if not isinstance(self.park_point_board, Point3Mm):
            raise TypeError("park_point_board must be a Point3Mm")
        if self.park_point_board.frame != "board":
            raise VirtualCommissioningProfileError("Park probe must use the board frame")
        if (
            self.schema != VIRTUAL_COMMISSIONING_PROFILE_SCHEMA
            or self.status != VIRTUAL_COMMISSIONING_PROFILE_STATUS
            or self.simulation_only is not True
            or self.physical_release_effect != "NONE"
        ):
            raise VirtualCommissioningProfileError(
                "Virtual profile authority or schema changed"
            )

    @property
    def can_authorize_hardware(self) -> bool:
        return False


def _decode_profile(
    document: Mapping[str, Any],
    *,
    source_path: Path,
    source_sha256: str,
) -> VirtualCommissioningProfile:
    _exact_keys(
        document,
        {
            "schema",
            "schema_version",
            "profile_id",
            "status",
            "simulation_only",
            "physical_release_effect",
            "binding",
            "selection",
            "study_input",
            "park_probe",
            "authority",
        },
        "virtual commissioning profile",
    )
    if document.get("schema") != VIRTUAL_COMMISSIONING_PROFILE_SCHEMA:
        raise VirtualCommissioningProfileError("Unsupported virtual profile schema")
    version = document.get("schema_version")
    if isinstance(version, bool) or version != 1:
        raise VirtualCommissioningProfileError("Unsupported virtual profile schema_version")
    if (
        document.get("profile_id") != _PROFILE_ID
        or document.get("status") != VIRTUAL_COMMISSIONING_PROFILE_STATUS
        or document.get("simulation_only") is not True
        or document.get("physical_release_effect") != "NONE"
    ):
        raise VirtualCommissioningProfileError(
            "Virtual profile identity, status, or authority changed"
        )

    binding = mapping(document.get("binding"), "virtual profile binding")
    _exact_keys(
        binding,
        {"system_manifest_id", "design_revision", "simulation_bundle_id"},
        "virtual profile binding",
    )
    selection = mapping(document.get("selection"), "virtual profile selection")
    _exact_keys(
        selection,
        {
            "rank",
            "classification",
            "source_layout_report_hash",
            "source_mission_route_coverage_hash",
            "interpretation",
        },
        "virtual profile selection",
    )
    rank = selection.get("rank")
    if isinstance(rank, bool) or rank != 1:
        raise VirtualCommissioningProfileError("Virtual profile must retain rank 1")
    if selection.get("classification") != VIRTUAL_COMMISSIONING_PROFILE_STATUS:
        raise VirtualCommissioningProfileError(
            "Virtual profile selection lost its unmeasured classification"
        )
    source_layout_hash = _digest(
        selection.get("source_layout_report_hash"),
        "source layout report hash",
    )
    source_coverage_hash = _digest(
        selection.get("source_mission_route_coverage_hash"),
        "source mission-route coverage hash",
    )
    if source_layout_hash != _LAYOUT_REPORT_HASH or source_coverage_hash != _MISSION_COVERAGE_HASH:
        raise VirtualCommissioningProfileError(
            "Virtual profile source report identities changed"
        )
    identifier(selection.get("interpretation"), "virtual profile interpretation")

    park = mapping(document.get("park_probe"), "virtual profile park probe")
    _exact_keys(
        park,
        {
            "park_probe_id",
            "frame",
            "point_mm",
            "classification",
            "canonical_context_modified",
        },
        "virtual profile park probe",
    )
    if (
        park.get("frame") != "board"
        or park.get("classification") != VIRTUAL_COMMISSIONING_PROFILE_STATUS
        or park.get("canonical_context_modified") is not False
    ):
        raise VirtualCommissioningProfileError(
            "Virtual park probe frame, classification, or authority changed"
        )
    point = sequence(park.get("point_mm"), 3, "virtual park point")

    authority = mapping(document.get("authority"), "virtual profile authority")
    _exact_keys(
        authority,
        {
            "simulation_only",
            "physical_release_effect",
            "live_hardware_access_allowed",
            "hardware_commands_generated",
            "can_promote_calibrations",
        },
        "virtual profile authority",
    )
    if dict(authority) != {
        "simulation_only": True,
        "physical_release_effect": "NONE",
        "live_hardware_access_allowed": False,
        "hardware_commands_generated": 0,
        "can_promote_calibrations": False,
    }:
        raise VirtualCommissioningProfileError(
            "Virtual profile must retain permanent zero authority"
        )

    return VirtualCommissioningProfile(
        profile_id=identifier(document.get("profile_id"), "profile id"),
        system_manifest_id=identifier(
            binding.get("system_manifest_id"),
            "binding system manifest id",
        ),
        design_revision=identifier(binding.get("design_revision"), "binding design revision"),
        simulation_bundle_id=identifier(
            binding.get("simulation_bundle_id"),
            "binding simulation bundle id",
        ),
        source_layout_report_hash=source_layout_hash,
        source_mission_route_coverage_hash=source_coverage_hash,
        study_input=_decode_study_input(document.get("study_input")),
        park_probe_id=identifier(park.get("park_probe_id"), "park probe id"),
        park_point_board=Point3Mm(
            "board",
            finite(point[0], "park x"),
            finite(point[1], "park y"),
            finite(point[2], "park z"),
        ),
        source_path=source_path,
        source_sha256=source_sha256,
    )


def validate_virtual_commissioning_profile(
    profile: VirtualCommissioningProfile,
    context: VirtualProfileContext,
) -> None:
    """Recheck the typed overlay against the current locked context and URDF."""

    # See ``_decode_study_input``: importing the pinned-model service lazily
    # keeps the public simulation package safe to import from application code.
    from rocell.application._pinned_model import PinnedModelLoadError, load_pinned_urdf

    if not isinstance(profile, VirtualCommissioningProfile):
        raise TypeError("profile must be a VirtualCommissioningProfile")
    snapshot = context.snapshot
    bundle = context.bundle_lock
    scenario = context.scenario
    scene = context.scene
    if profile.profile_id != _PROFILE_ID:
        raise VirtualCommissioningProfileError("Unexpected virtual profile identity")
    if (
        profile.system_manifest_id != snapshot.manifest_id
        or profile.design_revision != snapshot.design_revision
        or profile.simulation_bundle_id != bundle.bundle_id
    ):
        raise VirtualCommissioningProfileError(
            "Virtual profile binding differs from the locked context"
        )
    if (
        profile.source_layout_report_hash != _LAYOUT_REPORT_HASH
        or profile.source_mission_route_coverage_hash != _MISSION_COVERAGE_HASH
    ):
        raise VirtualCommissioningProfileError(
            "Virtual profile source report identities changed"
        )
    study = profile.study_input
    if study.study_input_id != _STUDY_INPUT_ID:
        raise VirtualCommissioningProfileError("Unexpected virtual rank-1 study input")

    board_rear_y = scene.board.maximum.y
    clamp_lower, clamp_upper = scene.arm_clamp_rear_edge_x_range_mm
    expected_x = study.rear_clamp_contact_x_board_mm + study.clamp_to_base_axis_x_mm
    translation = study.board_T_base_link.translation_mm
    if not clamp_lower <= study.rear_clamp_contact_x_board_mm <= clamp_upper:
        raise VirtualCommissioningProfileError("Virtual clamp contact X leaves the RC03 zone")
    if not -100.0 <= study.clamp_to_base_axis_x_mm <= 100.0:
        raise VirtualCommissioningProfileError("Virtual clamp-to-axis X leaves its envelope")
    if not 0.0 <= study.rear_edge_to_base_axis_y_mm <= 100.0:
        raise VirtualCommissioningProfileError("Virtual rear-axis Y leaves its envelope")
    if not (
        math.isclose(study.base_axis_x_board_mm, expected_x, abs_tol=_TOLERANCE)
        and math.isclose(translation.x, expected_x, abs_tol=_TOLERANCE)
        and math.isclose(
            translation.y,
            board_rear_y + study.rear_edge_to_base_axis_y_mm,
            abs_tol=_TOLERANCE,
        )
        and math.isclose(translation.z, study.base_link_z_board_mm, abs_tol=_TOLERANCE)
    ):
        raise VirtualCommissioningProfileError(
            "Virtual scalar placement fields disagree with B_T_Ru"
        )
    expected_rotation = RigidTransform.from_rpy_translation_mm(
        "board",
        "base_link",
        translation_mm=translation,
        yaw_rad=study.base_yaw_board_rad,
    ).rotation
    if not study.board_T_base_link.rotation.almost_equal(expected_rotation):
        raise VirtualCommissioningProfileError("Virtual B_T_Ru disagrees with its planar yaw")

    try:
        loaded_model = load_pinned_urdf(scenario.model_path, scenario.model_sha256)
    except PinnedModelLoadError as exc:
        raise VirtualCommissioningProfileError(
            f"Could not load pinned URDF for virtual profile validation: {exc}"
        ) from exc
    fixed = loaded_model.model.joint("world_to_base_link")
    if fixed.joint_type != "fixed" or fixed.parent_link != "world" or fixed.child_link != "base_link":
        raise VirtualCommissioningProfileError("Pinned URDF lost Wv_T_Ru")
    vendor_world_T_base_link = fixed.transform_at(None)
    derived = study.board_T_base_link.compose(vendor_world_T_base_link.inverse())
    if not derived.almost_equal(study.board_T_vendor_world):
        raise VirtualCommissioningProfileError(
            "Virtual B_T_Wv does not equal B_T_Ru * inverse(Wv_T_Ru)"
        )
    canonical_board_T_base = scenario.board_T_world.compose(vendor_world_T_base_link)
    canonical_yaw = math.atan2(
        canonical_board_T_base.rotation.matrix[3],
        canonical_board_T_base.rotation.matrix[0],
    )
    yaw_delta = math.atan2(
        math.sin(study.base_yaw_board_rad - canonical_yaw),
        math.cos(study.base_yaw_board_rad - canonical_yaw),
    )
    if abs(yaw_delta) > math.radians(15.0) + 1e-12:
        raise VirtualCommissioningProfileError("Virtual base yaw leaves the +/-15 degree study envelope")
    if not math.isclose(
        study.base_link_z_board_mm,
        canonical_board_T_base.translation_mm.z,
        abs_tol=_TOLERANCE,
    ):
        raise VirtualCommissioningProfileError("Virtual base Z left the pinned study assumption")
    for label, length in (
        ("keyboard", study.keyboard_tool_length_mm),
        ("phone", study.phone_tool_length_mm),
    ):
        if not 0.0 <= length <= 150.0:
            raise VirtualCommissioningProfileError(
                f"Virtual {label} tool length leaves [0, 150] mm"
            )
    park = profile.park_point_board
    if not (
        scene.board.minimum.x <= park.x <= scene.board.maximum.x
        and scene.board.minimum.y <= park.y <= scene.board.maximum.y
        and park.z > scene.board.maximum.z
    ):
        raise VirtualCommissioningProfileError("Virtual park probe leaves the board volume")


def load_virtual_commissioning_profile(
    context: VirtualProfileContext,
) -> VirtualCommissioningProfile:
    """Load the one exact profile artifact selected by the verified bundle."""

    try:
        artifact = context.bundle_lock.artifact("virtual_commissioning_profile")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise VirtualCommissioningProfileError(
            "Locked context does not contain a virtual commissioning profile"
        ) from exc
    document, actual_sha256 = _read_locked_document(artifact.path, artifact.sha256)
    profile = _decode_profile(
        document,
        source_path=artifact.path,
        source_sha256=actual_sha256,
    )
    validate_virtual_commissioning_profile(profile, context)
    return profile


__all__ = [
    "DEFAULT_VIRTUAL_COMMISSIONING_PROFILE",
    "MAX_VIRTUAL_COMMISSIONING_PROFILE_BYTES",
    "VIRTUAL_COMMISSIONING_PROFILE_SCHEMA",
    "VIRTUAL_COMMISSIONING_PROFILE_STATUS",
    "VirtualCommissioningProfile",
    "VirtualCommissioningProfileError",
    "VirtualProfileContext",
    "load_virtual_commissioning_profile",
    "validate_virtual_commissioning_profile",
]
