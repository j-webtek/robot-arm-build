"""Strict, read-only validation for the static overhead camera support candidate.

The source document is deliberately a zero-authority engineering contract.  It
lets simulation and design-review code share one geometry and optical model.
It records the user-confirmed purchased catalog configuration but cannot verify
the received unit or release a cut list, installation, robot motion, or contact.
Exact safety-significant values and wording are treated as a versioned interface;
a real design change requires a new schema or an intentional update to this
validator and its mutation tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence


STATIC_CAMERA_SUPPORT_SCHEMA = "rocell.static_overhead_camera_support.v1"
DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN = Path(
    "hardware/static_overhead_camera/config/support_design.json"
)
MAX_STATIC_CAMERA_SUPPORT_BYTES = 128 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "design_id",
        "revision_date",
        "state",
        "authority",
        "source_locks",
        "external_sources",
        "coordinate_frame",
        "board",
        "required_view",
        "robot_screening",
        "support",
        "optical_candidate",
        "open_blockers",
    }
)

_SOURCE_LOCKS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "workcell_layout": (
            "active-project/RoCell_v0_3/config/workcell_layout.json",
            "e84db9aa7b88db442f042c6f546196e350c822a2e7609cb4b652b3da535df2e1",
        ),
        "robot_reach_screening": (
            "active-project/RoCell_v0_3/config/robot_reach_screening.json",
            "348fccf9be88fc32299ab10fce14e764869422191a43963631e4f5f0ccb9e53b",
        ),
        "camera_architecture_plan": (
            "software/config/camera_architecture_plan.json",
            "e5414dc7295ab8a4c9c1e7e813bedf38e336755b73b9fad9431572da6e1913bf",
        ),
        "purchased_camera_profile": (
            "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
            "c15264f866d81b99cc1155171e21d3416d3a1fa7a244b5ae97642cc989f2e024",
        ),
    }
)
_EXTERNAL_SOURCES = MappingProxyType(
    {
        "camera_product": (
            "https://www.arducam.com/arducam-20mp-usb-3-0-camera-module-with-16mm-c-mount-lens-b0477.html",
            "PUBLISHED_SPECIFICATION_UNQUALIFIED",
        ),
        "camera_datasheet": (
            "https://www.arducam.com/downloads/datasheet/B0477_20MP_IMX283_USB3.0_Camera_Datasheet.pdf",
            "PUBLISHED_SPECIFICATION_UNQUALIFIED",
        ),
    }
)

_AUTHORITY_NOTE = (
    "This additive contract records the user-confirmed purchased camera catalog "
    "configuration and supports geometry and optical screening only. It does "
    "not verify the received unit or release cut lengths, fabrication, "
    "installation, robot power, motion, descent, or contact."
)
_ROBOT_WARNING = (
    "The assumed base axis and vendor envelope are screening inputs only. They "
    "do not prove the installed base transform, full-body swept volume, IK, "
    "payload, cable, lighting, or collision clearance."
)
_SUPPORT_BASE_WARNING = (
    "The compact front post axes have only a radial point screen. They do not "
    "authorize a low rail, foot, brace, anchor, or other volume extending "
    "rearward toward the board or into the robot swept volume."
)
_OPEN_BLOCKERS = (
    "measure the installed robot base axis and complete full-body swept-volume, IK, payload, cable, lighting, and collision studies",
    "select and proof the common metal U-frame, bench anchoring, 3-2-1 locators, clamps, 4040 joints, braces, fasteners, and anti-tip restraint",
    "derive exact cut lengths only after measuring the received board, bench, robot installation, extrusion hardware, camera case, and entrance-pupil offset",
    "obtain or measure the exact B0477 metal-case mount drawing and prove positive retention with non-bottoming fasteners",
    "physically verify that the included 16 mm lens focuses and locks at the nominal 1 m working distance",
    "resolve the published 49 degree horizontal and 38 degree vertical FOV inconsistency with the native 3:2 frame, then measure usable FOV, distortion, crop, corner illumination, depth of field, glare, and tag pixels at the exact locked settings",
    "record persistent USB descriptors and prove exact 5472x3648 at 9 fps YUY2 USB 3.0 mode after reopen and reboot",
    "model and physically prove clearance for the portal, camera, booms, braces, fasteners, cable, strain relief, and lighting through every approved route",
    "keep every rear-open base and outrigger at or forward of y=-100 mm or use independently qualified bench anchors; any longitudinal base rail entering y>=0 remains open blocking collision geometry",
    "perform load, tip, stiffness, vibration, settling, cable-pull, bump, remove-reinstall, thermal, and 24-hour drift qualification",
    "commission intrinsics, the static eye-to-hand extrinsic, support witness, visibility atlas, and independent held-out end-to-end validation",
    "generate a superseding controlled build freeze before fabrication, installation, powered motion, descent, or contact",
)


class StaticCameraSupportError(ValueError):
    """The static camera support document is unsafe or incompatible."""


@dataclass(frozen=True)
class StaticCameraSupportMetrics:
    """Geometry derived from the locked candidate, in millimetres and pixels."""

    nominal_coverage_width_mm: float
    nominal_coverage_depth_mm: float
    published_nominal_coverage_depth_mm: float
    minimum_height_coverage_width_mm: float
    minimum_height_coverage_depth_mm: float
    aspect_conservative_vertical_fov_deg: float
    nominal_horizontal_pixels_per_mm: float
    nominal_vertical_pixels_per_mm: float
    nominal_conservative_pixels_per_mm: float
    nominal_tag_width_pixels: float
    nominal_view_margin_width_mm: float
    nominal_view_margin_depth_mm: float
    minimum_height_view_margin_width_mm: float
    minimum_height_view_margin_depth_mm: float
    minimum_post_axis_distance_mm: float
    minimum_post_radial_clearance_mm: float
    minimum_overhead_vertical_clearance_mm: float


@dataclass(frozen=True)
class StaticCameraSupportDesign:
    """Validated immutable view of the screening candidate."""

    path: Path
    content_sha256: str
    design_id: str
    revision_date: date
    state: str
    board_size_mm: tuple[float, float, float]
    required_view_mm: tuple[float, float]
    assumed_base_axis_xy_mm: tuple[float, float]
    post_axis_xy_mm: tuple[tuple[float, float], tuple[float, float]]
    camera_axis_xy_mm: tuple[float, float]
    nominal_entrance_pupil_z_mm: float
    qualification_adjustment_z_mm: tuple[float, float]
    lowest_static_hardware_z_mm: float
    camera_model: str
    sensor: str
    native_mode: tuple[int, int, float, str]
    field_of_view_deg: tuple[float, float, float]
    source_sha256: Mapping[str, str]
    open_blockers: tuple[str, ...]
    metrics: StaticCameraSupportMetrics


def _reject_json_constant(value: str) -> None:
    raise StaticCameraSupportError(
        f"static camera support contains invalid JSON constant {value!r}"
    )


def _object_without_duplicate_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StaticCameraSupportError(
                f"static camera support contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StaticCameraSupportError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    raise StaticCameraSupportError(
        f"{label} fields differ; missing={missing}, unknown={unknown}"
    )


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StaticCameraSupportError(f"{label} must be a non-empty string")
    return value


def _exact_string(value: object, expected: str, label: str) -> str:
    observed = _string(value, label)
    if observed != expected:
        raise StaticCameraSupportError(f"{label} must be {expected!r}")
    return observed


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise StaticCameraSupportError(f"{label} must be boolean")
    return value


def _number(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StaticCameraSupportError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise StaticCameraSupportError(f"{label} must be finite")
    if not minimum <= result <= maximum:
        raise StaticCameraSupportError(
            f"{label} must be in [{minimum}, {maximum}], got {result}"
        )
    return result


def _integer(
    value: object,
    label: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StaticCameraSupportError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise StaticCameraSupportError(
            f"{label} must be in [{minimum}, {maximum}], got {value}"
        )
    return value


def _exact_number(
    value: object,
    expected: float,
    label: str,
    *,
    minimum: float = -100_000.0,
    maximum: float = 100_000.0,
) -> float:
    observed = _number(value, label, minimum=minimum, maximum=maximum)
    if observed != expected:
        raise StaticCameraSupportError(f"{label} must be {expected}, got {observed}")
    return observed


def _pair(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise StaticCameraSupportError(f"{label} must be a two-number array")
    return (
        _number(value[0], f"{label}[0]", minimum=minimum, maximum=maximum),
        _number(value[1], f"{label}[1]", minimum=minimum, maximum=maximum),
    )


def _require_exact_pair(
    observed: tuple[float, float], expected: tuple[float, float], label: str
) -> None:
    if observed != expected:
        raise StaticCameraSupportError(f"{label} must be {expected}, got {observed}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_contained(root: Path, relative_path: str, label: str) -> Path:
    parsed = PurePosixPath(relative_path)
    if parsed.is_absolute() or ".." in parsed.parts or "." in parsed.parts:
        raise StaticCameraSupportError(f"{label} must be a normalized relative path")
    candidate = (root / Path(*parsed.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise StaticCameraSupportError(f"{label} escapes the workspace") from exc
    return candidate


def _coverage(distance_mm: float, field_of_view_deg: float) -> float:
    return 2.0 * distance_mm * math.tan(math.radians(field_of_view_deg / 2.0))


def _read_document(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StaticCameraSupportError(
            f"cannot read static camera support document {path}: {exc}"
        ) from exc
    return _parse_document(raw), raw


def _parse_document(raw: bytes) -> Mapping[str, Any]:
    if type(raw) is not bytes or not raw:
        raise StaticCameraSupportError("static camera support document is empty")
    if len(raw) > MAX_STATIC_CAMERA_SUPPORT_BYTES:
        raise StaticCameraSupportError("static camera support document is too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StaticCameraSupportError(
            "static camera support document must be UTF-8"
        ) from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise StaticCameraSupportError(
            f"invalid static camera support JSON: {exc}"
        ) from exc
    return _mapping(decoded, "root")


def _validate_sources(root: Path, document: Mapping[str, Any]) -> Mapping[str, str]:
    hashes: dict[str, str] = {}
    for source_id, (relative_path, _) in _SOURCE_LOCKS.items():
        source_path = _resolve_contained(
            root, relative_path, f"source_locks.{source_id}.path"
        )
        if not source_path.is_file():
            raise StaticCameraSupportError(f"locked source is missing: {relative_path}")
        hashes[relative_path] = _sha256_file(source_path)
    return _validate_source_hashes(document, hashes)


def _validate_source_hashes(
    document: Mapping[str, Any], hashes: Mapping[str, str]
) -> Mapping[str, str]:
    if set(hashes) != {path for path, _ in _SOURCE_LOCKS.values()}:
        raise StaticCameraSupportError("locked source hash inventory differs")
    locks = _mapping(document.get("source_locks"), "source_locks")
    _exact_fields(locks, frozenset(_SOURCE_LOCKS), "source_locks")
    verified: dict[str, str] = {}
    for source_id, (expected_path, canonical_digest) in _SOURCE_LOCKS.items():
        lock = _mapping(locks.get(source_id), f"source_locks.{source_id}")
        _exact_fields(lock, frozenset({"path", "sha256"}), f"source_locks.{source_id}")
        relative_path = _exact_string(
            lock.get("path"), expected_path, f"source_locks.{source_id}.path"
        )
        expected_digest = _exact_string(
            lock.get("sha256"), canonical_digest, f"source_locks.{source_id}.sha256"
        )
        if not _SHA256.fullmatch(expected_digest):
            raise StaticCameraSupportError(
                f"source_locks.{source_id}.sha256 must be a lowercase SHA-256 digest"
            )
        actual_digest = hashes[relative_path]
        if actual_digest != expected_digest:
            raise StaticCameraSupportError(
                f"locked source digest mismatch for {relative_path}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        verified[source_id] = actual_digest

    external = _mapping(document.get("external_sources"), "external_sources")
    _exact_fields(external, frozenset(_EXTERNAL_SOURCES), "external_sources")
    for source_id, (expected_url, expected_state) in _EXTERNAL_SOURCES.items():
        source = _mapping(external.get(source_id), f"external_sources.{source_id}")
        _exact_fields(
            source,
            frozenset({"url", "qualification_state"}),
            f"external_sources.{source_id}",
        )
        _exact_string(
            source.get("url"), expected_url, f"external_sources.{source_id}.url"
        )
        _exact_string(
            source.get("qualification_state"),
            expected_state,
            f"external_sources.{source_id}.qualification_state",
        )
    return MappingProxyType(verified)


def _validate_authority(document: Mapping[str, Any]) -> None:
    authority = _mapping(document.get("authority"), "authority")
    _exact_fields(
        authority,
        frozenset(
            {
                "engineering_screening_authority",
                "simulation_authority",
                "fabrication_authority",
                "physical_installation_authority",
                "powered_motion_authority",
                "contact_authority",
                "note",
            }
        ),
        "authority",
    )
    for field in ("engineering_screening_authority", "simulation_authority"):
        if not _boolean(authority.get(field), f"authority.{field}"):
            raise StaticCameraSupportError(f"authority.{field} must remain true")
    for field in (
        "fabrication_authority",
        "physical_installation_authority",
        "powered_motion_authority",
        "contact_authority",
    ):
        if _boolean(authority.get(field), f"authority.{field}"):
            raise StaticCameraSupportError(f"authority.{field} must remain false")
    _exact_string(authority.get("note"), _AUTHORITY_NOTE, "authority.note")


def _validate_coordinate_frame(document: Mapping[str, Any]) -> None:
    frame = _mapping(document.get("coordinate_frame"), "coordinate_frame")
    _exact_fields(
        frame, frozenset({"frame_id", "origin", "axes", "units"}), "coordinate_frame"
    )
    _exact_string(frame.get("frame_id"), "B", "coordinate_frame.frame_id")
    _exact_string(
        frame.get("origin"),
        "front-left corner of board top surface",
        "coordinate_frame.origin",
    )
    _exact_string(frame.get("units"), "mm", "coordinate_frame.units")
    axes = _mapping(frame.get("axes"), "coordinate_frame.axes")
    _exact_fields(axes, frozenset({"+x", "+y", "+z"}), "coordinate_frame.axes")
    _exact_string(axes.get("+x"), "right", "coordinate_frame.axes.+x")
    _exact_string(axes.get("+y"), "rear/toward arm", "coordinate_frame.axes.+y")
    _exact_string(axes.get("+z"), "up", "coordinate_frame.axes.+z")


def _validate_board_and_view(
    document: Mapping[str, Any],
) -> tuple[tuple[float, float, float], tuple[float, float], float]:
    board = _mapping(document.get("board"), "board")
    _exact_fields(
        board,
        frozenset({"width_mm", "depth_mm", "thickness_mm", "tag_plane_z_mm"}),
        "board",
    )
    board_size = (
        _exact_number(board.get("width_mm"), 610.0, "board.width_mm", minimum=1.0),
        _exact_number(board.get("depth_mm"), 457.0, "board.depth_mm", minimum=1.0),
        _exact_number(
            board.get("thickness_mm"), 18.0, "board.thickness_mm", minimum=1.0
        ),
    )
    tag_plane_z = _exact_number(
        board.get("tag_plane_z_mm"), 0.0, "board.tag_plane_z_mm"
    )
    view = _mapping(document.get("required_view"), "required_view")
    _exact_fields(
        view,
        frozenset({"width_mm", "depth_mm", "margin_each_board_edge_mm", "state"}),
        "required_view",
    )
    required = (
        _exact_number(
            view.get("width_mm"), 670.0, "required_view.width_mm", minimum=1.0
        ),
        _exact_number(
            view.get("depth_mm"), 517.0, "required_view.depth_mm", minimum=1.0
        ),
    )
    margin = _exact_number(
        view.get("margin_each_board_edge_mm"),
        30.0,
        "required_view.margin_each_board_edge_mm",
        minimum=0.0,
    )
    if required != (board_size[0] + 2.0 * margin, board_size[1] + 2.0 * margin):
        raise StaticCameraSupportError(
            "required_view must equal board width/depth plus two edge margins"
        )
    _exact_string(
        view.get("state"),
        "PROVISIONAL_SCREENING_ENVELOPE_NOT_ACCEPTANCE_TOLERANCE",
        "required_view.state",
    )
    return board_size, required, tag_plane_z


def _validate_robot_screening(
    document: Mapping[str, Any],
) -> tuple[tuple[float, float], float, float, float, float]:
    robot = _mapping(document.get("robot_screening"), "robot_screening")
    _exact_fields(
        robot,
        frozenset(
            {
                "state",
                "assumed_base_axis_xy_mm",
                "vendor_published_radius_mm",
                "vendor_published_vertical_workspace_mm",
                "radial_screening_margin_mm",
                "vertical_screening_margin_mm",
                "warning",
            }
        ),
        "robot_screening",
    )
    _exact_string(
        robot.get("state"),
        "ASSUMED_ONLY_NOT_COLLISION_OR_REACH_PROOF",
        "robot_screening.state",
    )
    axis = _pair(
        robot.get("assumed_base_axis_xy_mm"),
        "robot_screening.assumed_base_axis_xy_mm",
        minimum=-10_000.0,
        maximum=10_000.0,
    )
    _require_exact_pair(axis, (305.0, 457.0), "robot_screening.assumed_base_axis_xy_mm")
    radius = _exact_number(
        robot.get("vendor_published_radius_mm"),
        560.0,
        "robot_screening.vendor_published_radius_mm",
        minimum=1.0,
    )
    vertical = _exact_number(
        robot.get("vendor_published_vertical_workspace_mm"),
        798.0,
        "robot_screening.vendor_published_vertical_workspace_mm",
        minimum=1.0,
    )
    radial_margin = _exact_number(
        robot.get("radial_screening_margin_mm"),
        50.0,
        "robot_screening.radial_screening_margin_mm",
        minimum=0.0,
    )
    vertical_margin = _exact_number(
        robot.get("vertical_screening_margin_mm"),
        100.0,
        "robot_screening.vertical_screening_margin_mm",
        minimum=0.0,
    )
    _exact_string(robot.get("warning"), _ROBOT_WARNING, "robot_screening.warning")
    return axis, radius, vertical, radial_margin, vertical_margin


def _validate_support(
    document: Mapping[str, Any],
) -> tuple[
    tuple[tuple[float, float], tuple[float, float]],
    tuple[float, float],
    float,
    tuple[float, float],
    float,
]:
    support = _mapping(document.get("support"), "support")
    _exact_fields(
        support,
        frozenset(
            {
                "topology",
                "relationship_to_board",
                "board_location",
                "structural_profiles",
                "base_constraint",
                "post_axis_xy_mm",
                "camera_axis_xy_mm",
                "nominal_entrance_pupil_z_mm",
                "qualification_adjustment_z_mm",
                "lowest_static_hardware_z_mm",
                "exact_cut_lengths_mm",
                "cut_lengths_state",
                "state",
            }
        ),
        "support",
    )
    _exact_string(
        support.get("topology"),
        "front_portal_on_common_metal_u_frame",
        "support.topology",
    )
    _exact_string(
        support.get("relationship_to_board"),
        "The portal and board share one positively located metal U-frame; the camera support is not carried by the plywood board alone.",
        "support.relationship_to_board",
    )
    location = _mapping(support.get("board_location"), "support.board_location")
    _exact_fields(
        location,
        frozenset({"method", "new_v0_3_board_holes_allowed"}),
        "support.board_location",
    )
    _exact_string(
        location.get("method"),
        "3-2-1 board-edge location and reversible clamping",
        "support.board_location.method",
    )
    if _boolean(
        location.get("new_v0_3_board_holes_allowed"),
        "support.board_location.new_v0_3_board_holes_allowed",
    ):
        raise StaticCameraSupportError(
            "the v0.3 board may not receive new support holes"
        )
    profiles = _mapping(
        support.get("structural_profiles"), "support.structural_profiles"
    )
    _exact_fields(
        profiles,
        frozenset({"uprights", "crossbar", "overhead_booms"}),
        "support.structural_profiles",
    )
    _exact_string(
        profiles.get("uprights"), "4040 aluminum extrusion", "support uprights"
    )
    _exact_string(
        profiles.get("crossbar"), "4040 aluminum extrusion", "support crossbar"
    )
    _exact_string(
        profiles.get("overhead_booms"),
        "two braced metal booms",
        "support overhead booms",
    )
    base_constraint = _mapping(
        support.get("base_constraint"), "support.base_constraint"
    )
    _exact_fields(
        base_constraint,
        frozenset(
            {
                "allowed_strategy",
                "low_side_rails_running_rearward_beside_board_allowed",
                "longitudinal_base_rail_entering_y_greater_or_equal_0_state",
                "warning",
            }
        ),
        "support.base_constraint",
    )
    _exact_string(
        base_constraint.get("allowed_strategy"),
        "rear-open base and outriggers stay at or forward of y=-100 mm, or use independently qualified bench anchors",
        "support.base_constraint.allowed_strategy",
    )
    if _boolean(
        base_constraint.get("low_side_rails_running_rearward_beside_board_allowed"),
        "support.base_constraint.low_side_rails_running_rearward_beside_board_allowed",
    ):
        raise StaticCameraSupportError(
            "low side rails may not run rearward beside the board"
        )
    _exact_string(
        base_constraint.get(
            "longitudinal_base_rail_entering_y_greater_or_equal_0_state"
        ),
        "OPEN_BLOCKING_COLLISION_GEOMETRY",
        "support.base_constraint.longitudinal_base_rail_entering_y_greater_or_equal_0_state",
    )
    _exact_string(
        base_constraint.get("warning"),
        _SUPPORT_BASE_WARNING,
        "support.base_constraint.warning",
    )
    raw_posts = support.get("post_axis_xy_mm")
    if not isinstance(raw_posts, list) or len(raw_posts) != 2:
        raise StaticCameraSupportError(
            "support.post_axis_xy_mm must contain two points"
        )
    posts = (
        _pair(
            raw_posts[0], "support.post_axis_xy_mm[0]", minimum=-10_000, maximum=10_000
        ),
        _pair(
            raw_posts[1], "support.post_axis_xy_mm[1]", minimum=-10_000, maximum=10_000
        ),
    )
    camera_axis = _pair(
        support.get("camera_axis_xy_mm"),
        "support.camera_axis_xy_mm",
        minimum=-10_000,
        maximum=10_000,
    )
    nominal_z = _number(
        support.get("nominal_entrance_pupil_z_mm"),
        "support.nominal_entrance_pupil_z_mm",
        minimum=1.0,
        maximum=10_000.0,
    )
    adjustment = _pair(
        support.get("qualification_adjustment_z_mm"),
        "support.qualification_adjustment_z_mm",
        minimum=1.0,
        maximum=10_000.0,
    )
    if adjustment[0] > nominal_z or nominal_z > adjustment[1]:
        raise StaticCameraSupportError(
            "nominal entrance-pupil z must lie within the qualification adjustment"
        )
    lowest_z = _number(
        support.get("lowest_static_hardware_z_mm"),
        "support.lowest_static_hardware_z_mm",
        minimum=1.0,
        maximum=10_000.0,
    )
    if support.get("exact_cut_lengths_mm") is not None:
        raise StaticCameraSupportError(
            "support.exact_cut_lengths_mm must remain null until physical measurement"
        )
    _exact_string(
        support.get("cut_lengths_state"),
        "CANDIDATE_ONLY_EXACT_LENGTHS_OPEN_BLOCKING",
        "support.cut_lengths_state",
    )
    _exact_string(
        support.get("state"),
        "CONCEPT_GEOMETRY_ONLY_NOT_RELEASED_FOR_FABRICATION_OR_INSTALLATION",
        "support.state",
    )
    return posts, camera_axis, nominal_z, adjustment, lowest_z


def _validate_optical_candidate(
    document: Mapping[str, Any],
) -> tuple[int, int, float, str, float, float, float, float]:
    optical = _mapping(document.get("optical_candidate"), "optical_candidate")
    _exact_fields(
        optical,
        frozenset(
            {
                "selection_state",
                "camera",
                "lens",
                "published_field_of_view",
                "screening_field_of_view_policy",
                "tag_width_mm",
                "qualification_inputs",
            }
        ),
        "optical_candidate",
    )
    _exact_string(
        optical.get("selection_state"),
        "PURCHASED_PENDING_RECEIPT_INSPECTION",
        "optical_candidate.selection_state",
    )
    camera = _mapping(optical.get("camera"), "optical_candidate.camera")
    _exact_fields(
        camera,
        frozenset(
            {
                "manufacturer",
                "model",
                "sensor",
                "sensor_megapixels",
                "sensor_format",
                "shutter",
                "interface",
                "native_width_px",
                "native_height_px",
                "native_fps",
                "native_pixel_format",
                "native_aspect",
                "capture_policy",
                "case",
                "included_usb_cable_length_m",
                "lens_mount",
            }
        ),
        "optical_candidate.camera",
    )
    _exact_string(camera.get("manufacturer"), "Arducam", "camera.manufacturer")
    _exact_string(camera.get("model"), "B0477", "camera.model")
    _exact_string(camera.get("sensor"), "Sony IMX283", "camera.sensor")
    _exact_number(
        camera.get("sensor_megapixels"), 20.0, "camera.sensor_megapixels", minimum=1.0
    )
    _exact_string(camera.get("sensor_format"), "1-inch", "camera.sensor_format")
    _exact_string(camera.get("shutter"), "rolling", "camera.shutter")
    _exact_string(camera.get("interface"), "USB 3.0 UVC", "camera.interface")
    width_px = _integer(
        camera.get("native_width_px"),
        "camera.native_width_px",
        minimum=1,
        maximum=100_000,
    )
    height_px = _integer(
        camera.get("native_height_px"),
        "camera.native_height_px",
        minimum=1,
        maximum=100_000,
    )
    fps = _number(
        camera.get("native_fps"), "camera.native_fps", minimum=0.1, maximum=1_000
    )
    pixel_format = _string(
        camera.get("native_pixel_format"), "camera.native_pixel_format"
    )
    if (width_px, height_px, fps, pixel_format) != (5472, 3648, 9.0, "YUY2"):
        raise StaticCameraSupportError(
            "camera must use the exact full-resolution 5472x3648 at 9 fps YUY2 mode"
        )
    if width_px * 2 != height_px * 3:
        raise StaticCameraSupportError(
            "B0477 native mode must retain its exact 3:2 aspect"
        )
    _exact_string(camera.get("native_aspect"), "3:2", "camera.native_aspect")
    _exact_string(
        camera.get("capture_policy"),
        "full native frame without crop or rescale",
        "camera.capture_policy",
    )
    _exact_string(camera.get("case"), "included metal case", "camera.case")
    _exact_number(
        camera.get("included_usb_cable_length_m"),
        1.0,
        "camera.included_usb_cable_length_m",
        minimum=0.1,
    )
    specified_mount = (
        "C-mount per supplier detailed specification; delivered C/CS "
        "configuration unverified"
    )
    camera_mount = _exact_string(
        camera.get("lens_mount"), specified_mount, "camera.lens_mount"
    )

    lens = _mapping(optical.get("lens"), "optical_candidate.lens")
    _exact_fields(
        lens,
        frozenset(
            {
                "supply_relationship",
                "focal_length_mm",
                "mount",
                "designed_sensor_format",
                "focus",
                "aperture",
            }
        ),
        "optical_candidate.lens",
    )
    _exact_string(lens.get("supply_relationship"), "included with B0477", "lens supply")
    _exact_number(
        lens.get("focal_length_mm"), 16.0, "lens.focal_length_mm", minimum=0.1
    )
    lens_mount = _string(lens.get("mount"), "lens.mount")
    if lens_mount != camera_mount:
        raise StaticCameraSupportError("camera and lens mounts do not match")
    _exact_string(lens_mount, specified_mount, "lens.mount")
    lens_format = _string(
        lens.get("designed_sensor_format"), "lens.designed_sensor_format"
    )
    if lens_format != camera.get("sensor_format"):
        raise StaticCameraSupportError(
            "camera sensor and lens image formats do not match"
        )
    _exact_string(lens_format, "1-inch", "lens.designed_sensor_format")
    _exact_string(lens.get("focus"), "manual adjustable", "lens.focus")
    _exact_string(lens.get("aperture"), "manual adjustable", "lens.aperture")

    fov = _mapping(
        optical.get("published_field_of_view"),
        "optical_candidate.published_field_of_view",
    )
    _exact_fields(
        fov,
        frozenset(
            {"horizontal_deg", "vertical_deg", "diagonal_deg", "calculation_model"}
        ),
        "optical_candidate.published_field_of_view",
    )
    horizontal = _number(
        fov.get("horizontal_deg"),
        "field_of_view.horizontal_deg",
        minimum=1.0,
        maximum=179.0,
    )
    vertical = _number(
        fov.get("vertical_deg"),
        "field_of_view.vertical_deg",
        minimum=1.0,
        maximum=179.0,
    )
    diagonal = _number(
        fov.get("diagonal_deg"),
        "field_of_view.diagonal_deg",
        minimum=1.0,
        maximum=179.0,
    )
    _exact_string(
        fov.get("calculation_model"),
        "centered perpendicular pinhole screening from entrance pupil to tag plane",
        "field_of_view.calculation_model",
    )
    fov_policy = _mapping(
        optical.get("screening_field_of_view_policy"),
        "optical_candidate.screening_field_of_view_policy",
    )
    _exact_fields(
        fov_policy,
        frozenset({"vertical_rule", "reason", "state"}),
        "optical_candidate.screening_field_of_view_policy",
    )
    _exact_string(
        fov_policy.get("vertical_rule"),
        "use the lesser of published vertical FOV and the vertical FOV derived from horizontal FOV plus the full-frame native aspect",
        "screening_field_of_view_policy.vertical_rule",
    )
    _exact_string(
        fov_policy.get("reason"),
        "The published 49 degree horizontal and 38 degree vertical FOV pair is not geometrically consistent with the full-frame native 3:2 aspect under an ideal centered rectilinear pinhole model.",
        "screening_field_of_view_policy.reason",
    )
    _exact_string(
        fov_policy.get("state"),
        "ASPECT_CONSERVATIVE_UNTIL_MEASURED_USABLE_FOV",
        "screening_field_of_view_policy.state",
    )
    tag_width = _exact_number(
        optical.get("tag_width_mm"), 40.0, "optical_candidate.tag_width_mm", minimum=1.0
    )
    inputs = _mapping(
        optical.get("qualification_inputs"), "optical_candidate.qualification_inputs"
    )
    _exact_fields(
        inputs,
        frozenset(
            {
                "minimum_focus_at_nominal_1m_verified",
                "exact_case_mount_drawing_verified",
                "persistent_usb_descriptors_verified",
                "measured_usable_field_of_view_verified",
            }
        ),
        "optical_candidate.qualification_inputs",
    )
    for field in inputs:
        if inputs[field] is not None:
            raise StaticCameraSupportError(
                f"qualification input {field} must remain null until physical evidence exists"
            )
    return (
        width_px,
        height_px,
        fps,
        pixel_format,
        horizontal,
        vertical,
        diagonal,
        tag_width,
    )


def _validate_open_blockers(document: Mapping[str, Any]) -> tuple[str, ...]:
    value = document.get("open_blockers")
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise StaticCameraSupportError("open_blockers must be an array of strings")
    blockers = tuple(value)
    if blockers != _OPEN_BLOCKERS:
        raise StaticCameraSupportError(
            "open_blockers must retain every canonical physical qualification hold"
        )
    return blockers


def load_static_camera_support_design(
    workspace_root: Path,
    design_path: Path | None = None,
) -> StaticCameraSupportDesign:
    """Load, verify, and calculate the zero-authority support candidate.

    ``workspace_root`` is also the containment boundary for the design and its
    locked local sources.  External manufacturer references are identity-pinned
    URLs only; their claims remain explicitly unqualified until received
    hardware is measured.
    """

    root = workspace_root.resolve()
    selected = (
        (root / DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN)
        if design_path is None
        else design_path.resolve()
    )
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise StaticCameraSupportError(
            "support design path escapes the workspace"
        ) from exc
    document, raw = _read_document(selected)
    # Keep the historical loader's actual file checks; the pure parser reuses
    # the same fixed-lock validation with already observed original hashes.
    verified = _validate_sources(root, document)
    return parse_static_camera_support_json(
        raw,
        source_hashes={path: verified[key] for key, (path, _) in _SOURCE_LOCKS.items()},
        source_path=selected,
    )


def parse_static_camera_support_json(
    raw: bytes,
    *,
    source_hashes: Mapping[str, str],
    source_path: Path = DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN,
) -> StaticCameraSupportDesign:
    """Validate retained design bytes and the exact four original source hashes.

    This pure parser does not read paths. The caller must hash the original
    dependency bytes independently; file loading remains in the existing API.
    """
    document = _parse_document(raw)
    _exact_fields(document, _ROOT_FIELDS, "root")
    _exact_string(document.get("schema"), STATIC_CAMERA_SUPPORT_SCHEMA, "schema")
    if (
        _integer(document.get("schema_version"), "schema_version", minimum=1, maximum=1)
        != 1
    ):
        raise StaticCameraSupportError("schema_version must be 1")
    design_id = _exact_string(
        document.get("design_id"),
        "ROCELL-STATIC-CAMERA-SUPPORT-CANDIDATE-001",
        "design_id",
    )
    revision_text = _exact_string(
        document.get("revision_date"), "2026-09-05", "revision_date"
    )
    try:
        revision_date = date.fromisoformat(revision_text)
    except ValueError as exc:
        raise StaticCameraSupportError("revision_date must be an ISO date") from exc
    state = _exact_string(
        document.get("state"),
        "SCREENING_CANDIDATE_PHYSICAL_QUALIFICATION_OPEN",
        "state",
    )
    _validate_authority(document)
    sources = _validate_source_hashes(document, source_hashes)
    _validate_coordinate_frame(document)
    board_size, required_view, tag_plane_z = _validate_board_and_view(document)
    base_axis, radius, vertical, radial_margin, vertical_margin = (
        _validate_robot_screening(document)
    )
    posts, camera_axis, nominal_z, adjustment, lowest_z = _validate_support(document)
    (
        width_px,
        height_px,
        fps,
        pixel_format,
        horizontal_fov,
        vertical_fov,
        diagonal_fov,
        tag_width,
    ) = _validate_optical_candidate(document)
    blockers = _validate_open_blockers(document)

    nominal_distance = nominal_z - tag_plane_z
    minimum_distance = adjustment[0] - tag_plane_z
    if nominal_distance <= 0.0 or minimum_distance <= 0.0:
        raise StaticCameraSupportError(
            "camera entrance pupil must remain above the tag plane"
        )
    # The marketing H/V pair cannot both describe the native 3:2 frame under
    # this screening model.  Derive V from H and native aspect, then take the
    # lesser vertical angle until usable FOV is physically measured.
    aspect_vertical_fov = math.degrees(
        2.0
        * math.atan(math.tan(math.radians(horizontal_fov / 2.0)) * height_px / width_px)
    )
    conservative_vertical_fov = min(vertical_fov, aspect_vertical_fov)
    nominal_width = _coverage(nominal_distance, horizontal_fov)
    published_nominal_depth = _coverage(nominal_distance, vertical_fov)
    nominal_depth = _coverage(nominal_distance, conservative_vertical_fov)
    minimum_width = _coverage(minimum_distance, horizontal_fov)
    minimum_depth = _coverage(minimum_distance, conservative_vertical_fov)
    if minimum_width < required_view[0] or minimum_depth < required_view[1]:
        raise StaticCameraSupportError(
            "published FOV has a required-view coverage shortfall at the minimum qualification height"
        )

    post_distances = tuple(math.dist(post, base_axis) for post in posts)
    minimum_post_distance = min(post_distances)
    post_clearance = minimum_post_distance - (radius + radial_margin)
    if post_clearance < 0.0:
        raise StaticCameraSupportError(
            "a portal post lies inside the vendor radius plus screening margin"
        )
    vertical_clearance = lowest_z - (vertical + vertical_margin)
    if vertical_clearance < 0.0:
        raise StaticCameraSupportError(
            "lowest static hardware is below the vendor vertical workspace plus screening margin"
        )

    # Lock exact candidate coordinates only after the general safety screens so
    # those independently calculated guards cannot be replaced by exact-value
    # comparison alone.
    _require_exact_pair(posts[0], (-60.0, -100.0), "support.post_axis_xy_mm[0]")
    _require_exact_pair(posts[1], (670.0, -100.0), "support.post_axis_xy_mm[1]")
    _require_exact_pair(camera_axis, (305.0, 228.5), "support.camera_axis_xy_mm")
    if nominal_z != 1000.0:
        raise StaticCameraSupportError(
            "support.nominal_entrance_pupil_z_mm must be 1000.0"
        )
    _require_exact_pair(
        adjustment, (950.0, 1050.0), "support.qualification_adjustment_z_mm"
    )
    if lowest_z != 920.0:
        raise StaticCameraSupportError(
            "support.lowest_static_hardware_z_mm must be 920.0"
        )
    if (horizontal_fov, vertical_fov, diagonal_fov) != (49.0, 38.0, 60.0):
        raise StaticCameraSupportError(
            "published candidate FOV must be 49x38x60 degrees"
        )
    horizontal_density = width_px / nominal_width
    # Coverage must use the smaller, aspect-consistent vertical angle so that
    # the required board envelope cannot pass on an internally inconsistent
    # marketing FOV pair.  Sampling is the opposite bound: use the larger
    # published vertical coverage because it produces fewer pixels/mm and is
    # therefore the safe estimate for small tags and phone targets.
    vertical_density = height_px / published_nominal_depth
    conservative_density = min(horizontal_density, vertical_density)
    metrics = StaticCameraSupportMetrics(
        nominal_coverage_width_mm=nominal_width,
        nominal_coverage_depth_mm=nominal_depth,
        published_nominal_coverage_depth_mm=published_nominal_depth,
        minimum_height_coverage_width_mm=minimum_width,
        minimum_height_coverage_depth_mm=minimum_depth,
        aspect_conservative_vertical_fov_deg=conservative_vertical_fov,
        nominal_horizontal_pixels_per_mm=horizontal_density,
        nominal_vertical_pixels_per_mm=vertical_density,
        nominal_conservative_pixels_per_mm=conservative_density,
        nominal_tag_width_pixels=tag_width * conservative_density,
        nominal_view_margin_width_mm=nominal_width - required_view[0],
        nominal_view_margin_depth_mm=nominal_depth - required_view[1],
        minimum_height_view_margin_width_mm=minimum_width - required_view[0],
        minimum_height_view_margin_depth_mm=minimum_depth - required_view[1],
        minimum_post_axis_distance_mm=minimum_post_distance,
        minimum_post_radial_clearance_mm=post_clearance,
        minimum_overhead_vertical_clearance_mm=vertical_clearance,
    )
    return StaticCameraSupportDesign(
        path=source_path,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        design_id=design_id,
        revision_date=revision_date,
        state=state,
        board_size_mm=board_size,
        required_view_mm=required_view,
        assumed_base_axis_xy_mm=base_axis,
        post_axis_xy_mm=posts,
        camera_axis_xy_mm=camera_axis,
        nominal_entrance_pupil_z_mm=nominal_z,
        qualification_adjustment_z_mm=adjustment,
        lowest_static_hardware_z_mm=lowest_z,
        camera_model="Arducam B0477",
        sensor="Sony IMX283",
        native_mode=(width_px, height_px, fps, pixel_format),
        field_of_view_deg=(horizontal_fov, vertical_fov, diagonal_fov),
        source_sha256=sources,
        open_blockers=blockers,
        metrics=metrics,
    )


__all__ = [
    "DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN",
    "MAX_STATIC_CAMERA_SUPPORT_BYTES",
    "STATIC_CAMERA_SUPPORT_SCHEMA",
    "StaticCameraSupportDesign",
    "StaticCameraSupportError",
    "StaticCameraSupportMetrics",
    "load_static_camera_support_design",
    "parse_static_camera_support_json",
]
