"""Nominal RC03 scene import and conservative axis-aligned clearance checks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from rocell.models.frames import FrameMismatchError, Point3Mm

from ._validation import (
    SimulationSourceError,
    finite,
    identifier,
    load_json_object,
    mapping,
    positive,
    sequence,
    sha256_file,
    source_path,
)
from .profile import SimulationProfileStatus


class SceneImportError(SimulationSourceError):
    """The controlled RC03 geometry cannot form a coherent nominal scene."""


DEFAULT_SIMULATED_TAG_PLANE_Z_MM = 0.3


@dataclass(frozen=True, slots=True)
class AabbMm:
    """Closed axis-aligned box in one labelled millimetre frame."""

    obstacle_id: str
    frame: str
    minimum: Point3Mm
    maximum: Point3Mm
    kind: str
    source: str
    conservative_proxy: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "obstacle_id", identifier(self.obstacle_id, "obstacle id"))
        object.__setattr__(self, "frame", identifier(self.frame, "obstacle frame"))
        object.__setattr__(self, "kind", identifier(self.kind, "obstacle kind"))
        object.__setattr__(self, "source", identifier(self.source, "obstacle source"))
        if self.minimum.frame != self.frame or self.maximum.frame != self.frame:
            raise FrameMismatchError("AABB endpoints must use the AABB frame")
        if any(
            low > high
            for low, high in zip(
                (self.minimum.x, self.minimum.y, self.minimum.z),
                (self.maximum.x, self.maximum.y, self.maximum.z),
            )
        ):
            raise ValueError("AABB minimum cannot exceed maximum")
        if not isinstance(self.conservative_proxy, bool):
            raise TypeError("conservative_proxy must be bool")

    @classmethod
    def from_bounds(
        cls,
        obstacle_id: str,
        frame: str,
        minimum_xyz_mm: tuple[float, float, float],
        maximum_xyz_mm: tuple[float, float, float],
        *,
        kind: str,
        source: str,
        conservative_proxy: bool = False,
    ) -> "AabbMm":
        return cls(
            obstacle_id=obstacle_id,
            frame=frame,
            minimum=Point3Mm(frame, *minimum_xyz_mm),
            maximum=Point3Mm(frame, *maximum_xyz_mm),
            kind=kind,
            source=source,
            conservative_proxy=conservative_proxy,
        )

    def expanded(self, clearance_mm: float) -> "AabbMm":
        clearance = finite(clearance_mm, "clearance_mm")
        if clearance < 0.0:
            raise ValueError("clearance_mm cannot be negative")
        return AabbMm.from_bounds(
            self.obstacle_id,
            self.frame,
            (
                self.minimum.x - clearance,
                self.minimum.y - clearance,
                self.minimum.z - clearance,
            ),
            (
                self.maximum.x + clearance,
                self.maximum.y + clearance,
                self.maximum.z + clearance,
            ),
            kind=self.kind,
            source=self.source,
            conservative_proxy=self.conservative_proxy,
        )

    def contains(self, point: Point3Mm, *, clearance_mm: float = 0.0) -> bool:
        if point.frame != self.frame:
            raise FrameMismatchError(f"Point is in {point.frame}, expected {self.frame}")
        clearance = finite(clearance_mm, "clearance_mm")
        if clearance < 0.0:
            raise ValueError("clearance_mm cannot be negative")
        box = self.expanded(clearance) if clearance else self
        return (
            box.minimum.x <= point.x <= box.maximum.x
            and box.minimum.y <= point.y <= box.maximum.y
            and box.minimum.z <= point.z <= box.maximum.z
        )

    def point_distance_mm(self, point: Point3Mm) -> float:
        if point.frame != self.frame:
            raise FrameMismatchError(f"Point is in {point.frame}, expected {self.frame}")
        delta = (
            max(self.minimum.x - point.x, 0.0, point.x - self.maximum.x),
            max(self.minimum.y - point.y, 0.0, point.y - self.maximum.y),
            max(self.minimum.z - point.z, 0.0, point.z - self.maximum.z),
        )
        return math.sqrt(sum(value * value for value in delta))

    def intersects_segment(
        self,
        start: Point3Mm,
        end: Point3Mm,
        *,
        clearance_mm: float = 0.0,
    ) -> bool:
        """Conservative swept-point test using a clearance-expanded box."""

        if start.frame != self.frame or end.frame != self.frame:
            raise FrameMismatchError(f"Segment endpoints must be in {self.frame}")
        clearance = finite(clearance_mm, "clearance_mm")
        if clearance < 0.0:
            raise ValueError("clearance_mm cannot be negative")
        box = self.expanded(clearance) if clearance else self
        low = (box.minimum.x, box.minimum.y, box.minimum.z)
        high = (box.maximum.x, box.maximum.y, box.maximum.z)
        origin = (start.x, start.y, start.z)
        direction = (end.x - start.x, end.y - start.y, end.z - start.z)
        t_min = 0.0
        t_max = 1.0
        for axis in range(3):
            if abs(direction[axis]) <= 1e-15:
                if origin[axis] < low[axis] or origin[axis] > high[axis]:
                    return False
                continue
            inverse = 1.0 / direction[axis]
            entry = (low[axis] - origin[axis]) * inverse
            exit_ = (high[axis] - origin[axis]) * inverse
            if entry > exit_:
                entry, exit_ = exit_, entry
            t_min = max(t_min, entry)
            t_max = min(t_max, exit_)
            if t_min > t_max:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "obstacle_id": self.obstacle_id,
            "frame": self.frame,
            "minimum_mm": [self.minimum.x, self.minimum.y, self.minimum.z],
            "maximum_mm": [self.maximum.x, self.maximum.y, self.maximum.z],
            "kind": self.kind,
            "source": self.source,
            "conservative_proxy": self.conservative_proxy,
        }


@dataclass(frozen=True, slots=True)
class NominalDevice:
    device_id: str
    envelope: AabbMm
    interaction_plane_z_mm: float
    interaction_plane_state: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_id", identifier(self.device_id, "device id"))
        object.__setattr__(
            self,
            "interaction_plane_z_mm",
            finite(self.interaction_plane_z_mm, "interaction plane z"),
        )
        object.__setattr__(
            self,
            "interaction_plane_state",
            identifier(self.interaction_plane_state, "interaction plane state"),
        )
        if self.device_id != self.envelope.obstacle_id:
            raise ValueError("Device id and envelope id must match")

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "envelope": self.envelope.to_dict(),
            "interaction_plane_z_mm": self.interaction_plane_z_mm,
            "interaction_plane_state": self.interaction_plane_state,
            "physical_contact_coordinate": False,
        }


@dataclass(frozen=True, slots=True)
class NominalCalibrationTarget:
    """A labelled nominal point used for calibration, never a device obstacle.

    The RC03 layout stores the replaceable TCP puck beside the keyboard and
    phone under ``devices``.  Giving it a separate type prevents downstream
    code from accidentally treating a point datum as a size-bearing device.
    """

    target_id: str
    center: Point3Mm
    replaceable_part: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", identifier(self.target_id, "target id"))
        object.__setattr__(
            self,
            "replaceable_part",
            identifier(self.replaceable_part, "calibration target replaceable part"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "frame": self.center.frame,
            "center_mm": [self.center.x, self.center.y, self.center.z],
            "replaceable_part": self.replaceable_part,
            "coordinate_state": "nominal_simulation_geometry",
            "physical_contact_coordinate": False,
        }


@dataclass(frozen=True, slots=True)
class PlanarFiducial:
    name: str
    tag_id: int
    family: str
    role: str
    center: Point3Mm
    detection_edge_mm: float
    tile_edge_mm: float
    yaw_rad: float
    coordinate_source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", identifier(self.name, "fiducial name"))
        if isinstance(self.tag_id, bool) or not isinstance(self.tag_id, int) or self.tag_id < 0:
            raise ValueError("tag_id must be a non-negative integer")
        object.__setattr__(self, "family", identifier(self.family, "fiducial family"))
        object.__setattr__(self, "role", identifier(self.role, "fiducial role"))
        object.__setattr__(
            self, "detection_edge_mm", positive(self.detection_edge_mm, "detection edge")
        )
        object.__setattr__(self, "tile_edge_mm", positive(self.tile_edge_mm, "tile edge"))
        if self.tile_edge_mm < self.detection_edge_mm:
            raise ValueError("Fiducial tile edge cannot be smaller than its detection edge")
        object.__setattr__(self, "yaw_rad", finite(self.yaw_rad, "fiducial yaw"))
        object.__setattr__(
            self,
            "coordinate_source",
            identifier(self.coordinate_source, "fiducial coordinate source"),
        )

    def corners(self) -> tuple[Point3Mm, Point3Mm, Point3Mm, Point3Mm]:
        """Return marked-top-left, top-right, bottom-right, bottom-left corners."""

        half = self.detection_edge_mm / 2.0
        cosine = math.cos(self.yaw_rad)
        sine = math.sin(self.yaw_rad)
        corners: list[Point3Mm] = []
        for local_x, local_y in (
            (-half, half),
            (half, half),
            (half, -half),
            (-half, -half),
        ):
            x = self.center.x + cosine * local_x - sine * local_y
            y = self.center.y + sine * local_x + cosine * local_y
            corners.append(Point3Mm(self.center.frame, x, y, self.center.z))
        return corners[0], corners[1], corners[2], corners[3]

    def tile_corners(self) -> tuple[Point3Mm, Point3Mm, Point3Mm, Point3Mm]:
        """Return physical tile corners in the same marked-edge order."""

        half = self.tile_edge_mm / 2.0
        cosine = math.cos(self.yaw_rad)
        sine = math.sin(self.yaw_rad)
        points = tuple(
            Point3Mm(
                self.center.frame,
                self.center.x + cosine * local_x - sine * local_y,
                self.center.y + sine * local_x + cosine * local_y,
                self.center.z,
            )
            for local_x, local_y in (
                (-half, half),
                (half, half),
                (half, -half),
                (-half, -half),
            )
        )
        return points[0], points[1], points[2], points[3]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tag_id": self.tag_id,
            "family": self.family,
            "role": self.role,
            "center_board_mm": [self.center.x, self.center.y, self.center.z],
            "detection_edge_mm": self.detection_edge_mm,
            "tile_edge_mm": self.tile_edge_mm,
            "yaw_rad": self.yaw_rad,
            "coordinate_source": self.coordinate_source,
        }


@dataclass(frozen=True, slots=True)
class ClearanceCheck:
    frame: str
    clearance_mm: float
    colliding_obstacle_ids: tuple[str, ...]
    checked_obstacle_ids: tuple[str, ...]
    method: str

    @property
    def clear(self) -> bool:
        return not self.colliding_obstacle_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "clearance_mm": self.clearance_mm,
            "clear": self.clear,
            "colliding_obstacle_ids": list(self.colliding_obstacle_ids),
            "checked_obstacle_ids": list(self.checked_obstacle_ids),
            "method": self.method,
            "physical_authority": False,
        }


@dataclass(frozen=True, slots=True)
class NominalWorkcellScene:
    """Immutable nominal placemat projection for simulation-only clearance work."""

    design_revision: str
    board_frame: str
    board: AabbMm
    devices: Mapping[str, NominalDevice]
    tcp_calibration_target: NominalCalibrationTarget
    obstacles: tuple[AabbMm, ...]
    fiducials: tuple[PlanarFiducial, ...]
    source_hashes: Mapping[str, str]
    assumptions: tuple[str, ...]
    arm_clamp_rear_edge_x_range_mm: tuple[float, float]
    status: SimulationProfileStatus = SimulationProfileStatus.ASSUMED_GOOD_FOR_SIMULATION_ONLY

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "design_revision", identifier(self.design_revision, "design revision")
        )
        object.__setattr__(self, "board_frame", identifier(self.board_frame, "board frame"))
        if self.board.frame != self.board_frame:
            raise FrameMismatchError("Board AABB must use board_frame")
        devices = dict(self.devices)
        if any(name != device.device_id for name, device in devices.items()):
            raise ValueError("Device mapping keys must match device ids")
        if any(device.envelope.frame != self.board_frame for device in devices.values()):
            raise FrameMismatchError("Every device must use board_frame")
        object.__setattr__(self, "devices", MappingProxyType(devices))
        if self.tcp_calibration_target.center.frame != self.board_frame:
            raise FrameMismatchError("TCP calibration target must use board_frame")
        obstacles = tuple(self.obstacles)
        ids = [obstacle.obstacle_id for obstacle in obstacles]
        if len(ids) != len(set(ids)):
            raise ValueError("Obstacle ids must be unique")
        if any(obstacle.frame != self.board_frame for obstacle in obstacles):
            raise FrameMismatchError("Every obstacle must use board_frame")
        object.__setattr__(self, "obstacles", obstacles)
        fiducials = tuple(self.fiducials)
        if len({tag.name for tag in fiducials}) != len(fiducials):
            raise ValueError("Fiducial names must be unique")
        if len({tag.tag_id for tag in fiducials}) != len(fiducials):
            raise ValueError("Fiducial ids must be unique")
        if any(tag.center.frame != self.board_frame for tag in fiducials):
            raise FrameMismatchError("Every fiducial must use board_frame")
        object.__setattr__(self, "fiducials", fiducials)
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(self.source_hashes)))
        object.__setattr__(
            self,
            "assumptions",
            tuple(identifier(value, "scene assumption") for value in self.assumptions),
        )
        clamp_range = tuple(
            finite(value, "arm clamp x range")
            for value in self.arm_clamp_rear_edge_x_range_mm
        )
        if len(clamp_range) != 2 or clamp_range[0] >= clamp_range[1]:
            raise ValueError("Arm clamp x range must be an increasing pair")
        object.__setattr__(self, "arm_clamp_rear_edge_x_range_mm", clamp_range)

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def can_release_physical_gates(self) -> bool:
        return False

    def _selected_obstacles(self, ignored: Iterable[str]) -> tuple[AabbMm, ...]:
        ignored_ids = set(ignored)
        return tuple(
            obstacle for obstacle in self.obstacles if obstacle.obstacle_id not in ignored_ids
        )

    def check_point_clearance(
        self,
        point: Point3Mm,
        *,
        clearance_mm: float = 0.0,
        ignored_obstacle_ids: Iterable[str] = (),
    ) -> ClearanceCheck:
        clearance = finite(clearance_mm, "clearance_mm")
        if clearance < 0.0:
            raise ValueError("clearance_mm cannot be negative")
        selected = self._selected_obstacles(ignored_obstacle_ids)
        collisions = tuple(
            obstacle.obstacle_id
            for obstacle in selected
            if obstacle.point_distance_mm(point) <= clearance
        )
        return ClearanceCheck(
            self.board_frame,
            clearance,
            collisions,
            tuple(obstacle.obstacle_id for obstacle in selected),
            "euclidean_point_to_aabb",
        )

    def check_segment_clearance(
        self,
        start: Point3Mm,
        end: Point3Mm,
        *,
        clearance_mm: float = 0.0,
        ignored_obstacle_ids: Iterable[str] = (),
    ) -> ClearanceCheck:
        clearance = finite(clearance_mm, "clearance_mm")
        if clearance < 0.0:
            raise ValueError("clearance_mm cannot be negative")
        selected = self._selected_obstacles(ignored_obstacle_ids)
        collisions = tuple(
            obstacle.obstacle_id
            for obstacle in selected
            if obstacle.intersects_segment(start, end, clearance_mm=clearance)
        )
        return ClearanceCheck(
            self.board_frame,
            clearance,
            collisions,
            tuple(obstacle.obstacle_id for obstacle in selected),
            "segment_vs_clearance_expanded_aabb_conservative",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.nominal_workcell_scene.v1",
            "status": self.status.value,
            "simulation_only": True,
            "can_release_physical_gates": False,
            "design_revision": self.design_revision,
            "board_frame": self.board_frame,
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "board": self.board.to_dict(),
            "devices": {
                name: device.to_dict() for name, device in sorted(self.devices.items())
            },
            "tcp_calibration_target": self.tcp_calibration_target.to_dict(),
            "obstacles": [obstacle.to_dict() for obstacle in self.obstacles],
            "fiducials": [tag.to_dict() for tag in self.fiducials],
            "arm_clamp_rear_edge_x_range_mm": list(self.arm_clamp_rear_edge_x_range_mm),
            "assumptions": list(self.assumptions),
        }


def _xy(value: object, name: str) -> tuple[float, float]:
    values = sequence(value, 2, name)
    return finite(values[0], f"{name}[0]"), finite(values[1], f"{name}[1]")


def _xyz_size(value: object, name: str) -> tuple[float, float, float]:
    values = sequence(value, 3, name)
    return (
        positive(values[0], f"{name}[0]"),
        positive(values[1], f"{name}[1]"),
        positive(values[2], f"{name}[2]"),
    )


def _device(
    frame: str,
    device_id: str,
    document: Mapping[str, Any],
) -> NominalDevice:
    origin_x, origin_y = _xy(document.get("nominal_origin_xy"), f"devices.{device_id}.origin")
    width, depth, height = _xyz_size(
        document.get("nominal_size", document.get("configured_size")),
        f"devices.{device_id}.size",
    )
    support_z = finite(document.get("support_plane_z"), f"devices.{device_id}.support_plane_z")
    if device_id == "phone":
        interaction_z = finite(
            document.get("nominal_screen_plane_z"), "devices.phone.nominal_screen_plane_z"
        )
        state = "NOMINAL_SCREEN_PLANE_NOT_MEASURED_CONTACT_COORDINATE"
    else:
        interaction_z = support_z + height
        state = "NOMINAL_ENVELOPE_TOP_NOT_MEASURED_KEY_CONTACT_COORDINATE"
    envelope = AabbMm.from_bounds(
        device_id,
        frame,
        (origin_x, origin_y, support_z),
        (origin_x + width, origin_y + depth, support_z + height),
        kind="device_nominal_envelope",
        source="config/workcell_layout.json:devices",
        conservative_proxy=True,
    )
    return NominalDevice(device_id, envelope, interaction_z, state)


def load_rc03_nominal_scene(
    rc03_root: Path,
    *,
    assumed_tag_plane_z_mm: float = DEFAULT_SIMULATED_TAG_PLANE_Z_MM,
    station_proxy_height_mm: float = 35.0,
) -> NominalWorkcellScene:
    """Load hash-linked nominal board, device, station, and fiducial geometry.

    The two numeric defaults fill fields the physical package intentionally
    leaves unmeasured.  Both are recorded in ``scene.assumptions`` and neither
    can be used to release a physical gate.
    """

    root = rc03_root.resolve()
    layout_path = source_path(root, "config/workcell_layout.json")
    tags_path = source_path(root, "fiducials/apriltag_map.json")
    layout_hash = sha256_file(layout_path)
    layout = load_json_object(layout_path)
    tag_map = load_json_object(tags_path)
    if tag_map.get("layout_sha256") != layout_hash:
        raise SceneImportError("AprilTag map is not linked to the current workcell layout hash")
    design_revision = identifier(layout.get("release_revision"), "layout release revision")
    if tag_map.get("design_revision") != design_revision:
        raise SceneImportError("Workcell layout and AprilTag map revisions disagree")
    if layout.get("units") != "mm":
        raise SceneImportError("Workcell layout units must be mm")
    expected_axes = {"+x": "right", "+y": "rear/toward arm", "+z": "up"}
    if layout.get("axes") != expected_axes or tag_map.get("board_axes") != expected_axes:
        raise SceneImportError("RC03 board-axis contract does not match the simulation frame")

    frame = "board"
    board_doc = mapping(layout.get("board"), "layout.board")
    board_width = positive(board_doc.get("width"), "board width")
    board_depth = positive(board_doc.get("depth"), "board depth")
    board_thickness = positive(board_doc.get("thickness"), "board thickness")
    board_top = finite(board_doc.get("top_surface_z"), "board top surface z")
    board_bottom = finite(board_doc.get("bottom_surface_z"), "board bottom surface z")
    if abs((board_top - board_bottom) - board_thickness) > 1e-9:
        raise SceneImportError("Board thickness and top/bottom surfaces disagree")
    board = AabbMm.from_bounds(
        "board_solid",
        frame,
        (0.0, 0.0, board_bottom),
        (board_width, board_depth, board_top),
        kind="controlled_board_geometry",
        source="config/workcell_layout.json:board",
    )

    devices_doc = mapping(layout.get("devices"), "layout.devices")
    if set(devices_doc) != {"keyboard", "phone", "tcp_target"}:
        raise SceneImportError(
            "RC03 nominal scene must declare exactly keyboard, phone, and tcp_target"
        )
    devices = {
        name: _device(frame, name, mapping(devices_doc.get(name), f"devices.{name}"))
        for name in ("keyboard", "phone")
    }
    tcp_target_doc = mapping(devices_doc.get("tcp_target"), "devices.tcp_target")
    if set(tcp_target_doc) != {"center_xy", "target_plane_z", "replaceable_part"}:
        raise SceneImportError("RC03 tcp_target fields differ from the controlled contract")
    tcp_target_x, tcp_target_y = _xy(
        tcp_target_doc.get("center_xy"), "devices.tcp_target.center_xy"
    )
    tcp_calibration_target = NominalCalibrationTarget(
        target_id="tcp_target",
        center=Point3Mm(
            frame,
            tcp_target_x,
            tcp_target_y,
            finite(tcp_target_doc.get("target_plane_z"), "devices.tcp_target.target_plane_z"),
        ),
        replaceable_part=identifier(
            tcp_target_doc.get("replaceable_part"),
            "devices.tcp_target.replaceable_part",
        ),
    )
    station_height = positive(station_proxy_height_mm, "station_proxy_height_mm")
    obstacles: list[AabbMm] = [board]
    obstacles.extend(device.envelope for device in devices.values())
    stations = mapping(layout.get("stations"), "layout.stations")
    for station_id in sorted(stations):
        station = mapping(stations[station_id], f"stations.{station_id}")
        x, y = _xy(station.get("origin_xy"), f"stations.{station_id}.origin_xy")
        width, depth = _xy(
            station.get("outer_envelope"), f"stations.{station_id}.outer_envelope"
        )
        if width <= 0.0 or depth <= 0.0:
            raise SceneImportError(f"Station {station_id} envelope must be positive")
        installed_z = finite(station.get("installed_z"), f"stations.{station_id}.installed_z")
        obstacles.append(
            AabbMm.from_bounds(
                f"station:{station_id}",
                frame,
                (x, y, installed_z),
                (x + width, y + depth, installed_z + station_height),
                kind="station_outer_envelope_height_proxy",
                source="config/workcell_layout.json:stations",
                conservative_proxy=True,
            )
        )

    tag_plane_assumption = finite(assumed_tag_plane_z_mm, "assumed_tag_plane_z_mm")
    family = identifier(tag_map.get("family"), "tag family")
    map_edge = positive(tag_map.get("detection_edge_mm"), "tag detection edge")
    tile_edge = positive(tag_map.get("tile_size_mm"), "tag tile edge")
    tags_doc = mapping(tag_map.get("tags"), "tag_map.tags")
    ids_doc = mapping(tag_map.get("ids"), "tag_map.ids")
    if set(ids_doc) != set(tags_doc):
        raise SceneImportError(
            "AprilTag top-level ids and tag records contain different names"
        )
    for name in sorted(tags_doc):
        tag_id = mapping(tags_doc[name], f"tag_map.tags.{name}").get("id")
        top_level_id = ids_doc[name]
        if isinstance(tag_id, bool) or not isinstance(tag_id, int) or tag_id < 0:
            raise SceneImportError(f"Tag {name} id must be a non-negative integer")
        if (
            isinstance(top_level_id, bool)
            or not isinstance(top_level_id, int)
            or top_level_id < 0
        ):
            raise SceneImportError(
                f"Top-level tag {name} id must be a non-negative integer"
            )
        if top_level_id != tag_id:
            raise SceneImportError(
                f"Tag {name} id disagrees with the top-level identity map"
            )
    layout_direct_document = mapping(layout.get("direct_tags"), "layout.direct_tags")
    if finite(
        layout_direct_document.get("detection_edge_mm"), "layout direct-tag detection edge"
    ) != map_edge:
        raise SceneImportError("Layout and AprilTag map detection-edge sizes disagree")
    if finite(layout_direct_document.get("tile_size_mm"), "layout direct-tag tile size") != finite(
        tag_map.get("tile_size_mm"), "tag-map tile size"
    ):
        raise SceneImportError("Layout and AprilTag map tile sizes disagree")
    if tag_map.get("coordinate_source") != "nominal_layout":
        raise SceneImportError("Nominal scene requires the nominal_layout tag coordinate source")
    layout_direct = mapping(
        layout_direct_document.get("tags"),
        "layout.direct_tags.tags",
    )
    if set(tags_doc) != set(layout_direct):
        raise SceneImportError("Layout and AprilTag map contain different tag names")
    fiducials: list[PlanarFiducial] = []
    used_assumed_tag_z = False
    def tag_sort_key(name: str) -> tuple[int, str]:
        tag_id = mapping(tags_doc[name], f"tag_map.tags.{name}").get("id")
        if isinstance(tag_id, bool) or not isinstance(tag_id, int) or tag_id < 0:
            raise SceneImportError(f"Tag {name} id must be a non-negative integer")
        return tag_id, name

    for name in sorted(tags_doc, key=tag_sort_key):
        tag = mapping(tags_doc[name], f"tag_map.tags.{name}")
        layout_tag = mapping(layout_direct[name], f"layout.direct_tags.tags.{name}")
        tag_id = tag.get("id")
        if isinstance(tag_id, bool) or not isinstance(tag_id, int) or tag_id < 0:
            raise SceneImportError(f"Tag {name} id must be a non-negative integer")
        if layout_tag.get("id") != tag_id:
            raise SceneImportError(f"Tag {name} id disagrees between sources")
        if tag.get("coordinate_source") != tag_map.get("coordinate_source"):
            raise SceneImportError(f"Tag {name} coordinate source disagrees with its map")
        center_xy = _xy(
            tag.get("nominal_detection_center_xy_mm"),
            f"tag_map.tags.{name}.nominal_detection_center_xy_mm",
        )
        layout_center = _xy(
            layout_tag.get("detection_center_xy"),
            f"layout.direct_tags.tags.{name}.detection_center_xy",
        )
        if center_xy != layout_center:
            raise SceneImportError(f"Tag {name} center disagrees between sources")
        tag_tile_origin = _xy(
            tag.get("tile_origin_xy_mm"),
            f"tag_map.tags.{name}.tile_origin_xy_mm",
        )
        layout_tile_origin = _xy(
            layout_tag.get("tile_origin_xy"),
            f"layout.direct_tags.tags.{name}.tile_origin_xy",
        )
        expected_tile_origin = (
            center_xy[0] - tile_edge / 2.0,
            center_xy[1] - tile_edge / 2.0,
        )
        if tag_tile_origin != layout_tile_origin or tag_tile_origin != expected_tile_origin:
            raise SceneImportError(f"Tag {name} tile origin is inconsistent with its centre")
        center_xyz = sequence(
            tag.get("detection_center_xyz_mm"),
            3,
            f"tag_map.tags.{name}.detection_center_xyz_mm",
        )
        if finite(center_xyz[0], f"tag {name} x") != center_xy[0] or finite(
            center_xyz[1], f"tag {name} y"
        ) != center_xy[1]:
            raise SceneImportError(f"Tag {name} XYZ and nominal XY disagree")
        if center_xyz[2] is None:
            center_z = tag_plane_assumption
            used_assumed_tag_z = True
        else:
            center_z = finite(center_xyz[2], f"tag {name} z")
        yaw_deg = finite(tag.get("expected_yaw_deg_in_board_frame"), f"tag {name} yaw")
        if yaw_deg != finite(
            layout_tag.get("expected_yaw_deg_in_board_frame"), f"layout tag {name} yaw"
        ):
            raise SceneImportError(f"Tag {name} yaw disagrees between sources")
        fiducials.append(
            PlanarFiducial(
                name=name,
                tag_id=tag_id,
                family=family,
                role=identifier(tag.get("role"), f"tag {name} role"),
                center=Point3Mm(frame, center_xy[0], center_xy[1], center_z),
                detection_edge_mm=map_edge,
                tile_edge_mm=tile_edge,
                yaw_rad=math.radians(yaw_deg),
                coordinate_source=identifier(
                    tag.get("coordinate_source"), f"tag {name} coordinate source"
                ),
            )
        )

    assumptions = [
        "All imported RC03 board, station, device, and fiducial values are nominal simulation geometry, not measured installation evidence.",
        f"Station outer envelopes are conservatively extruded to {station_height:g} mm because controlled solid heights are not available to this proxy model.",
        "Keyboard and phone AABBs are nominal device envelopes; their surfaces are not calibrated contact coordinates.",
        "AABB checks omit robot-link meshes, fasteners, cables, flexible tools, and dynamic uncertainty unless modeled separately.",
    ]
    if used_assumed_tag_z:
        assumptions.append(
            f"Null direct-tag plane Z values are represented as {tag_plane_assumption:g} mm for simulation only."
        )
    clamp_zone = mapping(layout.get("arm_clamp_zone"), "layout.arm_clamp_zone")
    clamp_range = _xy(
        clamp_zone.get("rear_edge_x_range"),
        "layout.arm_clamp_zone.rear_edge_x_range",
    )
    return NominalWorkcellScene(
        design_revision=design_revision,
        board_frame=frame,
        board=board,
        devices=devices,
        tcp_calibration_target=tcp_calibration_target,
        obstacles=tuple(obstacles),
        fiducials=tuple(fiducials),
        source_hashes={
            "config/workcell_layout.json": layout_hash,
            "fiducials/apriltag_map.json": sha256_file(tags_path),
        },
        assumptions=tuple(assumptions),
        arm_clamp_rear_edge_x_range_mm=clamp_range,
    )
