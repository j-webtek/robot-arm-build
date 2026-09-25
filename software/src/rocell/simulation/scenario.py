"""Typed runtime parameters for the frozen, hardware-free simulation.

The hardware profile contains both identity evidence and numerical scenario
inputs.  :mod:`rocell.simulation.profile` projects the former; this module
projects the latter so application code never reparses nested JSON through
``Any`` or embeds placemat-specific constants in the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from rocell.geometry import (
    JointPosition,
    JointPositionUnit,
    RigidTransform,
    Rotation3,
    Vec3,
)
from rocell.models.frames import Transform

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
from .camera import PinholeCameraModel


@dataclass(frozen=True, slots=True)
class IkDiagnosticPolicy:
    """Bounded sampling and solver effort for non-authoritative IK checks."""

    sampling_policy: str
    maximum_samples: int
    max_attempts: int
    max_iterations_per_attempt: int

    def __post_init__(self) -> None:
        expected = "PARK_AND_CONTACT_FIRST_THEN_STRATIFIED_UNIQUE_MAX"
        if self.sampling_policy != expected:
            raise SimulationSourceError(f"IK sampling policy must be {expected}")
        for name in (
            "maximum_samples",
            "max_attempts",
            "max_iterations_per_attempt",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SimulationSourceError(f"{name} must be a positive integer")
        if self.max_attempts < 2:
            raise SimulationSourceError("max_attempts must be at least two")


@dataclass(frozen=True, slots=True)
class ToolTipPathPolicy:
    """Placemat-frame heights and clearance values for nominal path building."""

    clearance_above_highest_obstacle_mm: float
    segment_clearance_mm: float
    hover_height_mm: float
    approach_height_mm: float
    contact_overtravel_mm: float
    park_xy_board_mm: tuple[float, float]

    def __post_init__(self) -> None:
        if self.hover_height_mm <= self.approach_height_mm:
            raise SimulationSourceError("Hover height must exceed approach height")


@dataclass(frozen=True, slots=True)
class VirtualToolCase:
    """One explicit hand_tcp-to-tip sensitivity offset."""

    case_id: str
    hand_tcp_to_tip_z_mm: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", identifier(self.case_id, "tool case id"))
        if self.hand_tcp_to_tip_z_mm > 0.0:
            raise SimulationSourceError("Virtual tool offsets must be zero or along hand_tcp -Z")


@dataclass(frozen=True, slots=True)
class SyntheticOverviewScenario:
    """Versioned fixed-camera fixture used only to test the vision pipeline."""

    scenario_id: str
    camera: PinholeCameraModel
    camera_T_board: Transform
    scenario_is_arm_mounted_camera: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", identifier(self.scenario_id, "scenario id"))
        if not isinstance(self.camera, PinholeCameraModel):
            raise TypeError("camera must be a PinholeCameraModel")
        if not isinstance(self.camera_T_board, Transform):
            raise TypeError("camera_T_board must be a Transform")
        if self.camera_T_board.from_frame != "board":
            raise SimulationSourceError("Synthetic overview must observe the board frame")
        if self.scenario_is_arm_mounted_camera is not False:
            raise SimulationSourceError(
                "The fixed overview fixture must never claim to be the arm-mounted camera"
            )


@dataclass(frozen=True, slots=True)
class SimulationScenario:
    """All typed numerical inputs required by one nominal simulation run."""

    source_profile_path: Path
    source_profile_sha256: str
    board_frame: str
    assumed_tag_plane_z_mm: float
    station_proxy_height_mm: float
    workcell_layout_path: Path
    apriltag_map_path: Path
    target_profile_path: Path
    model_path: Path
    model_sha256: str
    board_T_world: RigidTransform
    board_T_world_state: str
    tool_case_id: str
    hand_tcp_to_tip_z_mm: float
    tool_cases: tuple[VirtualToolCase, ...]
    controller_joint_intersection_rad: Mapping[str, tuple[float, float]]
    controller_gripper_intersection_rad: tuple[float, float]
    ready_arm_joint_positions_rad: Mapping[str, JointPosition]
    fixed_gripper_position: JointPosition
    path_policy: ToolTipPathPolicy
    ik_policy: IkDiagnosticPolicy
    overview: SyntheticOverviewScenario

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "board_T_world_state",
            identifier(self.board_T_world_state, "board_T_world state"),
        )
        object.__setattr__(self, "board_frame", identifier(self.board_frame, "board frame"))
        if self.board_frame != "board":
            raise SimulationSourceError("The RC03 simulation board frame must be 'board'")
        object.__setattr__(
            self,
            "assumed_tag_plane_z_mm",
            finite(self.assumed_tag_plane_z_mm, "assumed tag plane z"),
        )
        object.__setattr__(
            self,
            "station_proxy_height_mm",
            positive(self.station_proxy_height_mm, "station proxy height"),
        )
        if self.assumed_tag_plane_z_mm < 0.0:
            raise SimulationSourceError("Assumed tag plane Z cannot be below the board top")
        object.__setattr__(self, "tool_case_id", identifier(self.tool_case_id, "tool case id"))
        if self.board_T_world.parent_frame != "board" or self.board_T_world.child_frame != "world":
            raise SimulationSourceError("Nominal transform must be board_T_world")
        if self.hand_tcp_to_tip_z_mm > 0.0:
            raise SimulationSourceError("Tool tip must lie on hand_tcp -Z or at hand_tcp")
        cases = tuple(self.tool_cases)
        if len({case.case_id for case in cases}) != len(cases):
            raise SimulationSourceError("Virtual tool case IDs must be unique")
        if self.tool_case_id not in {case.case_id for case in cases}:
            raise SimulationSourceError("Selected virtual tool case is missing")
        object.__setattr__(self, "tool_cases", cases)
        expected_joints = {
            "base_link_to_link1",
            "link1_to_link2",
            "link2_to_link3",
            "link3_to_link4",
            "link4_to_link5",
        }
        ranges = dict(self.controller_joint_intersection_rad)
        if set(ranges) != expected_joints:
            raise SimulationSourceError("Controller intersection must cover all five arm joints")
        for name, bounds in ranges.items():
            if len(bounds) != 2 or bounds[0] >= bounds[1]:
                raise SimulationSourceError(f"Controller intersection for {name} is invalid")
        object.__setattr__(self, "controller_joint_intersection_rad", MappingProxyType(ranges))
        ready_arm = dict(self.ready_arm_joint_positions_rad)
        if set(ready_arm) != expected_joints:
            raise SimulationSourceError("Ready pose must cover exactly all five arm joints")
        for name, position in ready_arm.items():
            if (
                not isinstance(position, JointPosition)
                or position.unit is not JointPositionUnit.RADIAN
            ):
                raise SimulationSourceError(f"Ready pose for {name} must use typed radians")
            lower, upper = ranges[name]
            if not lower <= position.value <= upper:
                raise SimulationSourceError(
                    f"Ready pose for {name} leaves the controller/URDF intersection"
                )
        object.__setattr__(self, "ready_arm_joint_positions_rad", MappingProxyType(ready_arm))
        gripper_bounds = tuple(
            finite(value, f"controller gripper intersection[{index}]")
            for index, value in enumerate(self.controller_gripper_intersection_rad)
        )
        if len(gripper_bounds) != 2 or gripper_bounds[0] >= gripper_bounds[1]:
            raise SimulationSourceError("Controller gripper intersection is invalid")
        if gripper_bounds[0] < 0.0 or gripper_bounds[1] > 1.5:
            raise SimulationSourceError(
                "Controller gripper intersection leaves the pinned URDF [0.0, 1.5] range"
            )
        object.__setattr__(self, "controller_gripper_intersection_rad", gripper_bounds)
        if (
            not isinstance(self.fixed_gripper_position, JointPosition)
            or self.fixed_gripper_position.unit is not JointPositionUnit.RADIAN
        ):
            raise SimulationSourceError("Fixed gripper position must be typed in radians")
        if not gripper_bounds[0] <= self.fixed_gripper_position.value <= gripper_bounds[1]:
            raise SimulationSourceError(
                "Fixed gripper position leaves the controller/URDF gripper intersection"
            )


def _int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SimulationSourceError(f"{name} must be an integer")
    return value


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise SimulationSourceError(f"{name} must be boolean")
    return value


def _float_tuple(value: object, length: int, name: str) -> tuple[float, ...]:
    return tuple(finite(item, f"{name}[{index}]") for index, item in enumerate(sequence(value, length, name)))


def load_simulation_scenario(
    workspace: Path,
    *,
    profile_path: Path | None = None,
) -> SimulationScenario:
    """Load strict numerical scenario inputs from the controlled profile."""

    root = Path(workspace).resolve()
    selected = (
        Path(profile_path).resolve()
        if profile_path is not None
        else source_path(root, "software/config/simulation_hardware_profile.json")
    )
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise SimulationSourceError("Simulation profile must be beneath the workspace") from exc

    document = load_json_object(selected)
    return _scenario_from_document(root, selected, document)


def _scenario_from_document(
    root: Path,
    selected: Path,
    document: Mapping[str, Any],
    *,
    overview_scenario: SyntheticOverviewScenario | None = None,
) -> SimulationScenario:
    """Shared numerical projection, not a hardware-profile/authority loader.

    The legacy file loader supplies its own camera document. The explicitly
    versioned static context supplies independently source-bound B0477 optics,
    so it never parses or inherits the old camera/holder selection. That owner
    must bind the complete descriptor, geometry and optical inputs before this
    private projection is used. Public context revalidation remains mandatory.
    """
    if document.get("schema") != "rocell.simulation_hardware_profile.v1":
        raise SimulationSourceError("Unsupported simulation hardware profile schema")
    if document.get("simulation_only") is not True or document.get("live_hardware_access_allowed") is not False:
        raise SimulationSourceError("Runtime scenario must remain simulation-only")

    robot = mapping(document.get("robot"), "profile.robot")
    binding = mapping(document.get("binding"), "profile.binding")
    workcell_layout_path = source_path(
        root,
        identifier(binding.get("workcell_layout"), "binding.workcell_layout"),
    )
    apriltag_map_path = source_path(
        root,
        identifier(binding.get("apriltag_map"), "binding.apriltag_map"),
    )
    target_profile_path = source_path(
        root,
        identifier(binding.get("nominal_target_profiles"), "binding.nominal_target_profiles"),
    )
    if workcell_layout_path.parents[1] != apriltag_map_path.parents[1]:
        raise SimulationSourceError("Layout and AprilTag map must share one RC03 root")
    model = mapping(robot.get("official_model"), "profile.robot.official_model")
    model_path = source_path(
        root,
        identifier(model.get("local_kinematic_projection"), "local model path"),
    )
    model_sha256 = identifier(model.get("local_kinematic_projection_sha256"), "model sha256").lower()
    if sha256_file(model_path) != model_sha256:
        raise SimulationSourceError("Pinned local RoArm kinematic projection hash mismatch")

    nominal = mapping(robot.get("nominal_board_T_robot_world"), "nominal board transform")
    translation = _float_tuple(nominal.get("translation_mm"), 3, "board_T_world translation")
    rotation = _float_tuple(nominal.get("rotation_row_major"), 9, "board_T_world rotation")
    board_T_world = RigidTransform(
        parent_frame=identifier(nominal.get("to_frame"), "board_T_world to frame"),
        child_frame=identifier(nominal.get("from_frame"), "board_T_world from frame"),
        rotation=Rotation3(rotation),
        translation_mm=Vec3(*translation),
    )

    defaults = mapping(document.get("simulation_defaults"), "simulation defaults")
    board_frame = identifier(defaults.get("board_frame"), "simulation board frame")
    assumed_tag_plane_z_mm = finite(defaults.get("tag_plane_z_mm"), "tag plane z")
    station_proxy_height_mm = positive(
        defaults.get("station_proxy_height_mm"),
        "station proxy height",
    )
    tool_case_id = identifier(defaults.get("tool_case_id"), "default tool case")
    raw_tool_cases = robot.get("virtual_tool_sensitivity_cases")
    if not isinstance(raw_tool_cases, list) or not raw_tool_cases:
        raise SimulationSourceError("virtual tool cases must be a non-empty array")
    selected_tool = None
    tool_cases: list[VirtualToolCase] = []
    for index, raw_case in enumerate(raw_tool_cases):
        case = mapping(raw_case, f"virtual tool case {index}")
        case_translation = _float_tuple(
            case.get("hand_tcp_T_tip_translation_mm"),
            3,
            f"virtual tool case {index} translation",
        )
        if case_translation[0] != 0.0 or case_translation[1] != 0.0:
            raise SimulationSourceError("Current IK supports only hand_tcp -Z tool offsets")
        tool_cases.append(
            VirtualToolCase(
                identifier(case.get("case_id"), f"virtual tool case {index} id"),
                case_translation[2],
            )
        )
        if case.get("case_id") == tool_case_id:
            if selected_tool is not None:
                raise SimulationSourceError(f"Duplicate default tool case {tool_case_id!r}")
            selected_tool = case
    if selected_tool is None:
        raise SimulationSourceError(f"Default tool case {tool_case_id!r} is missing")
    tool_translation = _float_tuple(
        selected_tool.get("hand_tcp_T_tip_translation_mm"),
        3,
        "tool translation",
    )
    if tool_translation[0] != 0.0 or tool_translation[1] != 0.0:
        raise SimulationSourceError("Current IK supports only a hand_tcp -Z tool offset")

    bridge = mapping(robot.get("controller_model_bridge"), "controller model bridge")
    raw_intersection = mapping(
        bridge.get("provisional_simulation_joint_intersection_rad"),
        "controller joint intersection",
    )
    logical_to_urdf = {
        "base": "base_link_to_link1",
        "shoulder": "link1_to_link2",
        "elbow": "link2_to_link3",
        "wrist": "link3_to_link4",
        "roll": "link4_to_link5",
    }
    if set(raw_intersection) != {*logical_to_urdf, "gripper_model"}:
        raise SimulationSourceError(
            "Controller intersection must cover exactly five arm joints and gripper_model"
        )
    controller_intersection: dict[str, tuple[float, float]] = {}
    for logical_name, urdf_name in logical_to_urdf.items():
        values = _float_tuple(
            raw_intersection.get(logical_name),
            2,
            f"{logical_name} range",
        )
        controller_intersection[urdf_name] = (values[0], values[1])
    gripper_intersection_values = _float_tuple(
        raw_intersection.get("gripper_model"),
        2,
        "gripper_model range",
    )
    controller_gripper_intersection = (
        gripper_intersection_values[0],
        gripper_intersection_values[1],
    )

    joint_order = tuple(
        identifier(value, f"robot.joint_order[{index}]")
        for index, value in enumerate(sequence(robot.get("joint_order"), 6, "robot joint order"))
    )
    expected_joint_order = (
        "base_link_to_link1",
        "link1_to_link2",
        "link2_to_link3",
        "link3_to_link4",
        "link4_to_link5",
        "link5_to_gripper_link",
    )
    if joint_order != expected_joint_order:
        raise SimulationSourceError("robot.joint_order changed from the six-joint contract")
    ready = _float_tuple(robot.get("ready_joint_positions_rad"), 6, "ready joint positions")
    ready_arm = {
        name: JointPosition.radians(value)
        for name, value in zip(expected_joint_order[:5], ready[:5])
    }
    path = mapping(defaults.get("tool_tip_path"), "simulation_defaults.tool_tip_path")
    park = _float_tuple(path.get("park_xy_board_mm"), 2, "park point")
    path_policy = ToolTipPathPolicy(
        clearance_above_highest_obstacle_mm=positive(
            path.get("clearance_above_highest_obstacle_mm"), "transit clearance"
        ),
        segment_clearance_mm=positive(path.get("segment_clearance_mm"), "segment clearance"),
        hover_height_mm=positive(path.get("hover_height_mm"), "hover height"),
        approach_height_mm=positive(path.get("approach_height_mm"), "approach height"),
        contact_overtravel_mm=positive(path.get("contact_overtravel_mm"), "contact overtravel"),
        park_xy_board_mm=(park[0], park[1]),
    )

    ik = mapping(defaults.get("ik_diagnostic"), "simulation_defaults.ik_diagnostic")
    ik_policy = IkDiagnosticPolicy(
        sampling_policy=identifier(ik.get("sampling_policy"), "IK sampling policy"),
        maximum_samples=_int(ik.get("maximum_samples"), "IK maximum samples"),
        max_attempts=_int(ik.get("max_attempts"), "IK max attempts"),
        max_iterations_per_attempt=_int(
            ik.get("max_iterations_per_attempt"), "IK max iterations"
        ),
    )

    if overview_scenario is None:
        camera = mapping(document.get("camera"), "profile.camera")
        stream = mapping(camera.get("simulation_stream"), "camera.simulation_stream")
        width = _int(stream.get("width_px"), "camera width")
        height = _int(stream.get("height_px"), "camera height")
        fps = _int(stream.get("fps"), "camera fps")
        if width <= 0 or height <= 0 or fps <= 0:
            raise SimulationSourceError("Camera dimensions and fps must be positive")
        overview = mapping(camera.get("synthetic_overview_fixture"), "synthetic overview")
        intrinsics = mapping(overview.get("intrinsics"), "synthetic overview intrinsics")
        matrix = _float_tuple(
            overview.get("camera_T_board_row_major"),
            16,
            "synthetic overview transform",
        )
        overview_to_frame = identifier(overview.get("to_frame"), "overview to frame")
        overview_scenario = SyntheticOverviewScenario(
            scenario_id=identifier(overview.get("scenario_id"), "overview scenario id"),
            camera=PinholeCameraModel(
                width_px=width,
                height_px=height,
                fx_px=positive(intrinsics.get("fx_px"), "overview fx"),
                fy_px=positive(intrinsics.get("fy_px"), "overview fy"),
                cx_px=finite(intrinsics.get("cx_px"), "overview cx"),
                cy_px=finite(intrinsics.get("cy_px"), "overview cy"),
                optical_frame=overview_to_frame,
            ),
            camera_T_board=Transform(
                to_frame=overview_to_frame,
                from_frame=identifier(overview.get("from_frame"), "overview from frame"),
                matrix=matrix,
            ),
            scenario_is_arm_mounted_camera=_bool(
                overview.get("scenario_is_arm_mounted_camera"),
                "scenario_is_arm_mounted_camera",
            ),
        )

    return SimulationScenario(
        source_profile_path=selected,
        source_profile_sha256=sha256_file(selected),
        board_frame=board_frame,
        assumed_tag_plane_z_mm=assumed_tag_plane_z_mm,
        station_proxy_height_mm=station_proxy_height_mm,
        workcell_layout_path=workcell_layout_path,
        apriltag_map_path=apriltag_map_path,
        target_profile_path=target_profile_path,
        model_path=model_path,
        model_sha256=model_sha256,
        board_T_world=board_T_world,
        board_T_world_state=identifier(nominal.get("state"), "board_T_world state"),
        tool_case_id=tool_case_id,
        hand_tcp_to_tip_z_mm=tool_translation[2],
        tool_cases=tuple(tool_cases),
        controller_joint_intersection_rad=controller_intersection,
        controller_gripper_intersection_rad=controller_gripper_intersection,
        ready_arm_joint_positions_rad=ready_arm,
        fixed_gripper_position=JointPosition.radians(ready[5]),
        path_policy=path_policy,
        ik_policy=ik_policy,
        overview=overview_scenario,
    )
