"""Validate that software assumptions describe one coherent RC03 placemat.

This module sits between source import and motion planning.  Individual source
loaders prove that their files are well formed; this validator proves that the
semantic typing profiles, target maps, scene geometry, nominal robot placement,
camera identity, and safety authority all agree with each other.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from itertools import combinations
from typing import Any, Iterable

from rocell.models.frames import Point3Mm
from rocell.simulation import (
    AabbMm,
    NominalWorkcellScene,
    PlanarFiducial,
    SimulationHardwareProfile,
    SimulationScenario,
)
from rocell.targets import NominalTargetCatalog, TargetRegion
from rocell.typing import development_keyboard_profile, development_phone_profile


# This pins the complete *synthetic* keyboard/phone target seed, including all
# centres and safe extents.  It is deliberately separate from the source-file
# hash: callers can construct immutable dataclass replacements in memory, and
# those must not inherit the original file's nominal-alignment evidence.
EXPECTED_NOMINAL_TARGET_GEOMETRY_SHA256 = (
    "39cc8b6dd0680a34b11097c8c0e6e77ed6d6af2729883250aaaa24bcc9b4065c"
)


@dataclass(frozen=True, slots=True)
class PlacematAlignmentCheck:
    """One deterministic cross-source assertion."""

    check_id: str
    status: str
    detail: str

    def __post_init__(self) -> None:
        if not self.check_id or not self.check_id.strip():
            raise ValueError("check_id must be a non-empty string")
        if self.status not in {"PASS", "FAIL"}:
            raise ValueError("alignment status must be PASS or FAIL")
        if not self.detail or not self.detail.strip():
            raise ValueError("alignment detail must be a non-empty string")

    def to_dict(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PlacematAlignmentReport:
    """Complete nominal alignment evidence with permanently absent authority."""

    design_revision: str
    checks: tuple[PlacematAlignmentCheck, ...]
    source_hashes: tuple[tuple[str, str], ...]
    schema: str = "rocell.placemat_alignment.v1"

    @property
    def all_checks_pass(self) -> bool:
        return bool(self.checks) and all(check.status == "PASS" for check in self.checks)

    @property
    def status(self) -> str:
        return (
            "PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS"
            if self.all_checks_pass
            else "FAIL_NOMINAL_ALIGNMENT"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "design_revision": self.design_revision,
            "simulation_only": True,
            "required_for_simulation_pass": True,
            "physical_release_effect": "NONE",
            "execution_authorized": False,
            "all_checks_pass": self.all_checks_pass,
            "source_hashes": dict(self.source_hashes),
            "checks": [check.to_dict() for check in self.checks],
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


def _inside_xy(inner: AabbMm, outer: AabbMm) -> bool:
    return (
        outer.minimum.x <= inner.minimum.x <= inner.maximum.x <= outer.maximum.x
        and outer.minimum.y <= inner.minimum.y <= inner.maximum.y <= outer.maximum.y
    )


def _rectangles_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    """Return true only for positive-area XY overlap; touching edges are safe."""

    return not (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )


def _aabb_rectangle(box: AabbMm) -> tuple[float, float, float, float]:
    return (box.minimum.x, box.minimum.y, box.maximum.x, box.maximum.y)


def _tag_tile_rectangle(tag: PlanarFiducial) -> tuple[float, float, float, float]:
    # PlanarFiducial is intentionally accessed through its public tile-corner
    # contract so yawed future layouts remain valid.
    corners = tag.tile_corners()
    xs = tuple(point.x for point in corners)
    ys = tuple(point.y for point in corners)
    return (min(xs), min(ys), max(xs), max(ys))


def _targets_inside_device(
    targets: Iterable[TargetRegion],
    device: AabbMm,
) -> tuple[str, ...]:
    failures: list[str] = []
    envelope = _aabb_rectangle(device)
    for target in targets:
        left, front, right, rear = target.safe_rectangle_board_mm
        if not (
            envelope[0] <= left <= right <= envelope[2]
            and envelope[1] <= front <= rear <= envelope[3]
        ):
            failures.append(target.target_id)
    return tuple(failures)


def _target_geometry_sha256(targets: NominalTargetCatalog) -> str:
    """Fingerprint every target centre and extent, independent of file metadata."""

    payload = {
        "keyboard": {
            target_id: target.to_dict()
            for target_id, target in sorted(targets.keyboard_targets.items())
        },
        "phone": {
            target_id: target.to_dict()
            for target_id, target in sorted(targets.phone_targets.items())
        },
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _same_contract_value(actual: object, expected: object) -> bool:
    """Compare mixed string/numeric geometry fields without coercing identifiers."""

    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and abs(float(actual) - float(expected)) <= 1e-9
        )
    return actual == expected


def _check(check_id: str, passed: bool, success: str, failure: str) -> PlacematAlignmentCheck:
    return PlacematAlignmentCheck(check_id, "PASS" if passed else "FAIL", success if passed else failure)


def validate_placemat_alignment(
    profile: SimulationHardwareProfile,
    scenario: SimulationScenario,
    scene: NominalWorkcellScene,
    targets: NominalTargetCatalog,
) -> PlacematAlignmentReport:
    """Cross-check all nominal software layers before geometric planning."""

    for value, expected, label in (
        (profile, SimulationHardwareProfile, "profile"),
        (scenario, SimulationScenario, "scenario"),
        (scene, NominalWorkcellScene, "scene"),
        (targets, NominalTargetCatalog, "targets"),
    ):
        if not isinstance(value, expected):
            raise TypeError(f"{label} must be {expected.__name__}")

    checks: list[PlacematAlignmentCheck] = []
    checks.append(
        _check(
            "simulation_profile_projection_coherence",
            profile.source_profile_sha256 == scenario.source_profile_sha256,
            "hardware identity and numerical scenario were projected from identical profile bytes",
            "hardware identity and numerical scenario used different simulation-profile bytes",
        )
    )
    revisions = {profile.design_revision, scene.design_revision, targets.design_revision}
    checks.append(
        _check(
            "design_revision_coherence",
            len(revisions) == 1,
            f"profile, scene, and target catalog all use {profile.design_revision}",
            f"cross-source revisions differ: {sorted(revisions)}",
        )
    )

    board = scene.board
    board_contract_ok = (
        board.minimum.x == 0.0
        and board.minimum.y == 0.0
        and board.minimum.z == -18.0
        and board.maximum.x == 610.0
        and board.maximum.y == 457.0
        and board.maximum.z == 0.0
        and scene.board_frame == "board"
        and scenario.board_frame == scene.board_frame
    )
    checks.append(
        _check(
            "board_frame_and_envelope",
            board_contract_ok,
            "board frame is front-left/top with 610 x 457 x 18 mm controlled envelope",
            "board dimensions, origin, axes projection, or top plane differ from RC03-INT-R1",
        )
    )

    outside_devices = tuple(
        name
        for name, device in scene.devices.items()
        if not _inside_xy(device.envelope, board)
    )
    obstacles_by_id = {obstacle.obstacle_id: obstacle for obstacle in scene.obstacles}
    exact_obstacle_ids = {
        "board_solid",
        "keyboard",
        "phone",
        "station:keyboard_left",
        "station:keyboard_right",
        "station:phone_tcp",
    }
    device_proxy_mismatches = tuple(
        name
        for name, device in scene.devices.items()
        if obstacles_by_id.get(name) != device.envelope
    )
    actual_device_bounds = {
        name: (
            device.envelope.minimum.x,
            device.envelope.minimum.y,
            device.envelope.minimum.z,
            device.envelope.maximum.x,
            device.envelope.maximum.y,
            device.envelope.maximum.z,
        )
        for name, device in scene.devices.items()
    }
    expected_device_bounds = {
        "keyboard": (85.0, 85.0, 0.0, 400.0, 232.0, 21.0),
        "phone": (499.2, 84.2, 4.0, 577.1, 248.6, 11.9),
    }
    device_bounds_ok = set(actual_device_bounds) == set(expected_device_bounds) and all(
        all(abs(actual - expected_value) <= 1e-9 for actual, expected_value in zip(
            actual_device_bounds[name], expected_device_bounds[name]
        ))
        for name in expected_device_bounds
    )
    checks.append(
        _check(
            "device_envelopes_on_board",
            not outside_devices
            and not device_proxy_mismatches
            and set(obstacles_by_id) == exact_obstacle_ids
            and obstacles_by_id.get("board_solid") == board
            and device_bounds_ok,
            "device footprints are on-board and exactly match the six scene obstacle proxies",
            (
                "device/scene obstacle contract failed: "
                f"outside={outside_devices}, proxy_mismatches={device_proxy_mismatches}, "
                f"ids={sorted(obstacles_by_id)}, bounds={actual_device_bounds}"
            ),
        )
    )

    stations = tuple(
        obstacle for obstacle in scene.obstacles if obstacle.obstacle_id.startswith("station:")
    )
    outside_stations = tuple(
        station.obstacle_id for station in stations if not _inside_xy(station, board)
    )
    expected_station_bounds = {
        "station:keyboard_left": (
            80.0, 72.0, 0.0, 264.5, 264.0, 35.0
        ),
        "station:keyboard_right": (
            242.5, 72.0, 0.0, 405.0, 264.0, 35.0
        ),
        "station:phone_tcp": (
            411.0, 80.0, 0.0, 597.3, 252.8, 35.0
        ),
    }
    actual_station_bounds = {
        station.obstacle_id: (
            station.minimum.x,
            station.minimum.y,
            station.minimum.z,
            station.maximum.x,
            station.maximum.y,
            station.maximum.z,
        )
        for station in stations
    }
    station_geometry_ok = (
        actual_station_bounds == expected_station_bounds
        and abs(scenario.station_proxy_height_mm - 35.0) <= 1e-9
    )
    keyboard_station_union = (80.0, 72.0, 405.0, 264.0)
    phone_station_rect = (411.0, 80.0, 597.3, 252.8)
    keyboard_station_contains_device = (
        keyboard_station_union[0] <= scene.devices["keyboard"].envelope.minimum.x
        and keyboard_station_union[1] <= scene.devices["keyboard"].envelope.minimum.y
        and scene.devices["keyboard"].envelope.maximum.x <= keyboard_station_union[2]
        and scene.devices["keyboard"].envelope.maximum.y <= keyboard_station_union[3]
    )
    phone_station_contains_device = (
        phone_station_rect[0] <= scene.devices["phone"].envelope.minimum.x
        and phone_station_rect[1] <= scene.devices["phone"].envelope.minimum.y
        and scene.devices["phone"].envelope.maximum.x <= phone_station_rect[2]
        and scene.devices["phone"].envelope.maximum.y <= phone_station_rect[3]
    )
    checks.append(
        _check(
            "station_envelopes_on_board",
            (
                not outside_stations
                and station_geometry_ok
                and keyboard_station_contains_device
                and phone_station_contains_device
            ),
            "three exact RC03 station proxies contain their associated device footprints",
            (
                "station identity/pose/device relationship is invalid; "
                f"outside={outside_stations}, actual={actual_station_bounds}"
            ),
        )
    )

    # The calibration puck is a point datum, not a third interactive device.
    # Pin its identity and nominal point independently so a plausible station
    # proxy cannot hide drift in the TCP calibration contract.
    tcp_target = scene.tcp_calibration_target
    phone_station = obstacles_by_id.get("station:phone_tcp")
    tcp_target_ok = (
        tcp_target.target_id == "tcp_target"
        and tcp_target.center == Point3Mm("board", 441.0, 180.0, 10.5)
        and tcp_target.replaceable_part == "calibration_puck"
        and phone_station is not None
        and phone_station.contains(tcp_target.center)
    )
    checks.append(
        _check(
            "tcp_calibration_target",
            tcp_target_ok,
            "replaceable TCP calibration puck is pinned at board (441, 180, 10.5) mm",
            (
                "TCP calibration target identity, point, part, or phone-station "
                f"containment differs: {tcp_target.to_dict()}"
            ),
        )
    )

    keyboard_rect = _aabb_rectangle(scene.devices["keyboard"].envelope)
    phone_rect = _aabb_rectangle(scene.devices["phone"].envelope)
    checks.append(
        _check(
            "device_footprint_separation",
            not _rectangles_overlap(keyboard_rect, phone_rect),
            "keyboard and phone footprints are disjoint",
            "keyboard and phone footprints overlap",
        )
    )

    tile_rectangles = {tag.name: _tag_tile_rectangle(tag) for tag in scene.fiducials}
    # Exact tag identity and pose matter to board-frame recovery.  Merely
    # keeping six non-overlapping tiles on the board would allow a plausible
    # but wrong nominal map to pass this software-alignment gate.
    expected_fiducials = {
        "T0": (0, "tag36h11", "world", 47.0, 40.0, 0.3, 40.0, 55.0, 0.0, "nominal_layout"),
        "T1": (1, "tag36h11", "world", 440.0, 40.0, 0.3, 40.0, 55.0, 0.0, "nominal_layout"),
        "T2": (2, "tag36h11", "world", 47.0, 410.0, 0.3, 40.0, 55.0, 0.0, "nominal_layout"),
        "T3": (3, "tag36h11", "world", 563.0, 410.0, 0.3, 40.0, 55.0, 0.0, "nominal_layout"),
        "K0": (
            4,
            "tag36h11",
            "station_check",
            324.0,
            309.0,
            0.3,
            40.0,
            55.0,
            0.0,
            "nominal_layout",
        ),
        "P0": (
            5,
            "tag36h11",
            "station_check",
            459.0,
            309.0,
            0.3,
            40.0,
            55.0,
            0.0,
            "nominal_layout",
        ),
    }
    actual_fiducials = {
        tag.name: (
            tag.tag_id,
            tag.family,
            tag.role,
            tag.center.x,
            tag.center.y,
            tag.center.z,
            tag.detection_edge_mm,
            tag.tile_edge_mm,
            tag.yaw_rad,
            tag.coordinate_source,
        )
        for tag in scene.fiducials
    }
    fiducial_pose_mismatches = tuple(
        sorted(
            name
            for name in set(expected_fiducials) | set(actual_fiducials)
            if name not in expected_fiducials
            or name not in actual_fiducials
            or any(
                not _same_contract_value(actual, expected)
                for actual, expected in zip(
                    actual_fiducials.get(name, ()),
                    expected_fiducials.get(name, ()),
                )
            )
        )
    )
    tag_plane_matches_scenario = all(
        tag.center.z == scenario.assumed_tag_plane_z_mm for tag in scene.fiducials
    )
    outside_tiles = tuple(
        name
        for name, rect in tile_rectangles.items()
        if not (
            board.minimum.x <= rect[0] <= rect[2] <= board.maximum.x
            and board.minimum.y <= rect[1] <= rect[3] <= board.maximum.y
        )
    )
    checks.append(
        _check(
            "fiducial_tiles_on_board",
            (
                len(tile_rectangles) == 6
                and not outside_tiles
                and tag_plane_matches_scenario
                and not fiducial_pose_mismatches
            ),
            "all six exact RC03 fiducial identities and poses remain fully on the board",
            (
                "fiducial identity/pose/count/bounds are invalid; "
                f"outside={outside_tiles}, pose_mismatches={fiducial_pose_mismatches}"
            ),
        )
    )

    device_overlaps = tuple(
        f"{tag_name}:{device_name}"
        for tag_name, tag_rect in tile_rectangles.items()
        for device_name, device_rect in (("keyboard", keyboard_rect), ("phone", phone_rect))
        if _rectangles_overlap(tag_rect, device_rect)
    )
    station_overlaps = tuple(
        f"{tag_name}:{station.obstacle_id}"
        for tag_name, tag_rect in tile_rectangles.items()
        for station in stations
        if _rectangles_overlap(tag_rect, _aabb_rectangle(station))
    )
    tag_pair_overlaps = tuple(
        f"{first_name}:{second_name}"
        for (first_name, first_rect), (second_name, second_rect) in combinations(
            tile_rectangles.items(), 2
        )
        if _rectangles_overlap(first_rect, second_rect)
    )
    checks.append(
        _check(
            "fiducial_keepouts",
            not device_overlaps and not station_overlaps and not tag_pair_overlaps,
            "tag tiles are pairwise disjoint and clear nominal device/station footprints",
            (
                "tag keepout overlaps: "
                f"devices={device_overlaps}, stations={station_overlaps}, "
                f"tag_pairs={tag_pair_overlaps}"
            ),
        )
    )

    keyboard_outside = _targets_inside_device(
        targets.keyboard_targets.values(), scene.devices["keyboard"].envelope
    )
    phone_outside = _targets_inside_device(
        targets.phone_targets.values(), scene.devices["phone"].envelope
    )
    target_z_ok = all(
        target.center.z == scene.devices[target.device].interaction_plane_z_mm
        for target in (*targets.keyboard_targets.values(), *targets.phone_targets.values())
    )
    target_pair_overlaps: list[str] = []
    duplicate_target_centres: list[str] = []
    for device, device_targets in (
        ("keyboard", targets.keyboard_targets),
        ("phone", targets.phone_targets),
    ):
        for (first_id, first), (second_id, second) in combinations(
            device_targets.items(), 2
        ):
            if first.center == second.center:
                duplicate_target_centres.append(f"{device}:{first_id}:{second_id}")
            if _rectangles_overlap(
                first.safe_rectangle_board_mm,
                second.safe_rectangle_board_mm,
            ):
                target_pair_overlaps.append(f"{device}:{first_id}:{second_id}")
    expected_target_anchors = {
        ("keyboard", "1"): (107.0, 196.0, 21.0),
        ("keyboard", "A"): (121.3, 154.0, 21.0),
        ("keyboard", "SPACE"): (224.0, 112.0, 21.0),
        ("keyboard", "ENTER"): (335.5, 154.0, 21.0),
        ("phone", "key_q"): (504.3, 142.2, 11.9),
        ("phone", "key_a"): (508.1, 126.2, 11.9),
        ("phone", "key_space"): (538.15, 94.7, 11.9),
        ("phone", "key_enter"): (569.7, 94.7, 11.9),
    }
    anchor_mismatches: list[str] = []
    for (device, target_id), expected_anchor in expected_target_anchors.items():
        mapping = (
            targets.keyboard_targets if device == "keyboard" else targets.phone_targets
        )
        target = mapping.get(target_id)
        if target is None or any(
            abs(actual - wanted) > 1e-9
            for actual, wanted in zip(
                (() if target is None else (target.center.x, target.center.y, target.center.z)),
                expected_anchor,
            )
        ):
            anchor_mismatches.append(f"{device}:{target_id}")
    target_geometry_sha256 = _target_geometry_sha256(targets)
    checks.append(
        _check(
            "target_regions_and_planes",
            (
                not keyboard_outside
                and not phone_outside
                and target_z_ok
                and not duplicate_target_centres
                and not target_pair_overlaps
                and not anchor_mismatches
                and target_geometry_sha256 == EXPECTED_NOMINAL_TARGET_GEOMETRY_SHA256
            ),
            (
                "the complete pinned target seed is in-device, on-plane, uniquely centred, "
                "and pairwise disjoint"
            ),
            (
                "invalid target geometry: "
                f"keyboard_outside={keyboard_outside}, phone_outside={phone_outside}, "
                f"duplicate_centres={duplicate_target_centres}, "
                f"overlaps={target_pair_overlaps}, anchors={anchor_mismatches}, "
                f"geometry_sha256={target_geometry_sha256}"
            ),
        )
    )

    keyboard_profile = development_keyboard_profile()
    phone_profile = development_phone_profile()
    profile_binding_ok = (
        targets.keyboard_semantic_profile_id == keyboard_profile.profile_id
        and targets.phone_semantic_profile_id == phone_profile.profile_id
        and targets.keyboard_semantic_profile_sha256
        == keyboard_profile.semantic_content_sha256
        and targets.phone_semantic_profile_sha256 == phone_profile.semantic_content_sha256
    )
    checks.append(
        _check(
            "semantic_geometry_profile_binding",
            profile_binding_ok,
            "keyboard and phone semantic profile IDs and complete mappings are content-bound",
            "semantic compiler profile IDs or content hashes do not match target-catalog bindings",
        )
    )

    required_keyboard_targets = {
        target_id
        for sequence_ids in keyboard_profile.character_keys.values()
        for target_id in sequence_ids
    }
    required_phone_targets = {
        spec.target_id for spec in phone_profile.character_targets.values()
    }
    missing_keyboard = tuple(sorted(required_keyboard_targets - set(targets.keyboard_targets)))
    missing_phone = tuple(sorted(required_phone_targets - set(targets.phone_targets)))
    extra_keyboard = tuple(sorted(set(targets.keyboard_targets) - required_keyboard_targets))
    extra_phone = tuple(sorted(set(targets.phone_targets) - required_phone_targets))
    checks.append(
        _check(
            "semantic_target_coverage",
            not missing_keyboard and not missing_phone and not extra_keyboard and not extra_phone,
            (
                f"the exact {len(required_keyboard_targets)} keyboard and "
                f"{len(required_phone_targets)} phone semantic target sets resolve"
            ),
            (
                "semantic target set mismatch: "
                f"keyboard_missing={missing_keyboard}, keyboard_extra={extra_keyboard}, "
                f"phone_missing={missing_phone}, phone_extra={extra_phone}"
            ),
        )
    )

    expected_calibrations = {
        "keyboard": {
            "camera_intrinsics",
            "eye_on_arm_extrinsic",
            "measured_tag_map",
            "robot_reference",
            "arm_board",
            "controller_correlation",
            "keyboard_pose",
            "keyboard_tcp",
            "keyboard_outcome_observer",
        },
        "phone": {
            "camera_intrinsics",
            "eye_on_arm_extrinsic",
            "measured_tag_map",
            "robot_reference",
            "arm_board",
            "controller_correlation",
            "phone_screen",
            "phone_tcp",
            "phone_ui_observer",
        },
    }
    calibration_ok = (
        set(keyboard_profile.required_calibrations) == expected_calibrations["keyboard"]
        and set(phone_profile.required_calibrations) == expected_calibrations["phone"]
    )
    checks.append(
        _check(
            "calibration_dependency_contract",
            calibration_ok,
            "plans retain camera, frame-correlation, board, device, route-TCP, and observer dependencies",
            "required keyboard/phone calibration dependency sets changed",
        )
    )

    base = scenario.board_T_world.translation_mm
    clamp_min, clamp_max = scene.arm_clamp_rear_edge_x_range_mm
    expected_board_T_world_rotation = (
        0.0,
        1.0,
        0.0,
        -1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )
    clamp_ok = (
        abs(clamp_min - 225.0) <= 1e-9
        and abs(clamp_max - 385.0) <= 1e-9
        and clamp_min <= base.x <= clamp_max
        and abs(base.x - 305.0) <= 1e-9
        and abs(base.y - 457.0) <= 1e-9
        and abs(base.z) <= 1e-9
        and all(
            abs(actual - expected) <= 1e-9
            for actual, expected in zip(
                scenario.board_T_world.rotation.matrix,
                expected_board_T_world_rotation,
            )
        )
        and scenario.board_T_world_state == "NOMINAL_ONLY_FROM_RC03_REACH_SCREENING"
    )
    checks.append(
        _check(
            "nominal_arm_clamp_placement",
            clamp_ok,
            (
                "exact nominal board_T_world places the base at "
                f"({base.x:g}, {base.y:g}, {base.z:g}) mm on the rear edge inside clamp "
                f"range [{clamp_min:g}, {clamp_max:g}] mm"
            ),
            "nominal robot translation, rotation, state, or rear clamp placement changed",
        )
    )

    park_x, park_y = scenario.path_policy.park_xy_board_mm
    park_in_board = (
        board.minimum.x <= park_x <= board.maximum.x
        and board.minimum.y <= park_y <= board.maximum.y
    )
    park_blocked = any(
        rect[0] <= park_x <= rect[2] and rect[1] <= park_y <= rect[3]
        for rect in (
            keyboard_rect,
            phone_rect,
            *(_aabb_rectangle(station) for station in stations),
            *tile_rectangles.values(),
        )
    )
    checks.append(
        _check(
            "nominal_park_point",
            park_in_board and not park_blocked,
            f"park XY ({park_x:g}, {park_y:g}) mm is on-board and outside placemat keepouts",
            f"park XY ({park_x:g}, {park_y:g}) mm is off-board or inside a keepout",
        )
    )

    camera_contract_ok = (
        profile.camera.model == "IMX335 5MP USB Camera (B)"
        and profile.camera.sku == "26719"
        and profile.camera.interface == "USB 2.0"
        and scenario.overview.scenario_is_arm_mounted_camera is False
    )
    checks.append(
        _check(
            "camera_identity_and_fixture_boundary",
            camera_contract_ok,
            "selected Waveshare IMX335-B USB identity is retained; overview fixture is not eye-on-arm",
            "camera identity or synthetic fixture boundary changed",
        )
    )

    authority_ok = (
        profile.simulation_only
        and not profile.hardware_io_allowed
        and not profile.safe_to_power_robot
        and not profile.contact_enabled
        and not profile.can_release_physical_gates
    )
    checks.append(
        _check(
            "physical_authority_holds",
            authority_ok,
            "simulation cannot power, command, contact, or release physical gates",
            "simulation profile unexpectedly carries physical authority",
        )
    )

    return PlacematAlignmentReport(
        design_revision=profile.design_revision,
        checks=tuple(checks),
        source_hashes=tuple(
            sorted(
                {
                    "simulation_hardware_profile.json": scenario.source_profile_sha256,
                    "nominal_target_profiles.json": targets.content_sha256,
                    "keyboard_semantic_profile": keyboard_profile.semantic_content_sha256,
                    "phone_semantic_profile": phone_profile.semantic_content_sha256,
                    **dict(scene.source_hashes),
                }.items()
            )
        ),
    )
