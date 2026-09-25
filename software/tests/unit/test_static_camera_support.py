from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
from typing import Any, Callable

import pytest

from rocell.workcell import (
    StaticCameraSupportError,
    load_static_camera_support_design,
)


WORKSPACE = Path(__file__).resolve().parents[3]
DESIGN_RELATIVE_PATH = Path(
    "hardware/static_overhead_camera/config/support_design.json"
)
DESIGN_PATH = WORKSPACE / DESIGN_RELATIVE_PATH
SOURCE_PATHS = (
    Path("active-project/RoCell_v0_3/config/workcell_layout.json"),
    Path("active-project/RoCell_v0_3/config/robot_reach_screening.json"),
    Path("software/config/camera_architecture_plan.json"),
    Path("software/config/camera_profiles/arducam_b0477_imx283_16mm.json"),
)


def _document() -> dict[str, Any]:
    value = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sandbox(tmp_path: Path) -> Path:
    for relative_path in (*SOURCE_PATHS, DESIGN_RELATIVE_PATH):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORKSPACE / relative_path, destination)
    return tmp_path / DESIGN_RELATIVE_PATH


def _mutated_design(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None]
) -> Path:
    path = _sandbox(tmp_path)
    document = copy.deepcopy(_document())
    mutate(document)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def test_loads_candidate_read_only_and_computes_conservative_geometry() -> None:
    before = DESIGN_PATH.read_bytes()
    document = _document()

    design = load_static_camera_support_design(WORKSPACE)

    assert DESIGN_PATH.read_bytes() == before
    assert design.path == DESIGN_PATH.resolve()
    assert design.content_sha256 == hashlib.sha256(before).hexdigest()
    assert design.design_id == "ROCELL-STATIC-CAMERA-SUPPORT-CANDIDATE-001"
    assert design.board_size_mm == (610.0, 457.0, 18.0)
    assert design.required_view_mm == (670.0, 517.0)
    assert design.assumed_base_axis_xy_mm == (305.0, 457.0)
    assert design.post_axis_xy_mm == ((-60.0, -100.0), (670.0, -100.0))
    assert design.camera_axis_xy_mm == (305.0, 228.5)
    assert design.qualification_adjustment_z_mm == (950.0, 1050.0)
    assert design.lowest_static_hardware_z_mm == 920.0
    assert design.camera_model == "Arducam B0477"
    assert design.sensor == "Sony IMX283"
    assert design.native_mode == (5472, 3648, 9.0, "YUY2")
    assert design.field_of_view_deg == (49.0, 38.0, 60.0)
    assert design.source_sha256["purchased_camera_profile"] == (
        "c15264f866d81b99cc1155171e21d3416d3a1fa7a244b5ae97642cc989f2e024"
    )
    assert len(design.open_blockers) == 12
    assert (
        document["optical_candidate"]["selection_state"]
        == "PURCHASED_PENDING_RECEIPT_INSPECTION"
    )
    assert document["optical_candidate"]["qualification_inputs"] == {
        "minimum_focus_at_nominal_1m_verified": None,
        "exact_case_mount_drawing_verified": None,
        "persistent_usb_descriptors_verified": None,
        "measured_usable_field_of_view_verified": None,
    }
    assert document["optical_candidate"]["camera"]["lens_mount"] == (
        "C-mount per supplier detailed specification; delivered C/CS configuration "
        "unverified"
    )
    assert (
        document["optical_candidate"]["lens"]["mount"]
        == document["optical_candidate"]["camera"]["lens_mount"]
    )

    metrics = design.metrics
    assert metrics.nominal_coverage_width_mm == pytest.approx(911.453, abs=0.001)
    assert metrics.published_nominal_coverage_depth_mm == pytest.approx(
        688.655, abs=0.001
    )
    assert metrics.aspect_conservative_vertical_fov_deg == pytest.approx(
        33.7994, abs=0.0001
    )
    assert metrics.nominal_coverage_depth_mm == pytest.approx(607.635, abs=0.001)
    assert metrics.minimum_height_coverage_width_mm == pytest.approx(
        865.880, abs=0.001
    )
    assert metrics.minimum_height_coverage_depth_mm == pytest.approx(
        577.253, abs=0.001
    )
    assert metrics.nominal_conservative_pixels_per_mm == pytest.approx(
        5.29728, abs=0.00001
    )
    assert metrics.nominal_tag_width_pixels == pytest.approx(211.891, abs=0.001)
    assert metrics.minimum_post_axis_distance_mm == pytest.approx(665.938, abs=0.001)
    assert metrics.minimum_post_radial_clearance_mm == pytest.approx(55.938, abs=0.001)
    assert metrics.minimum_overhead_vertical_clearance_mm == 22.0
    assert metrics.minimum_height_view_margin_width_mm > 0.0
    assert metrics.minimum_height_view_margin_depth_mm > 0.0


@pytest.mark.parametrize("change", ["missing", "unknown"])
def test_rejects_root_schema_drift(tmp_path: Path, change: str) -> None:
    def mutate(document: dict[str, Any]) -> None:
        if change == "missing":
            del document["open_blockers"]
        else:
            document["silent_extension"] = True

    path = _mutated_design(tmp_path, mutate)
    with pytest.raises(StaticCameraSupportError, match="fields differ"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = _sandbox(tmp_path)
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"schema_version": 1,',
        '"schema_version": 1,\n  "schema_version": 1,',
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(StaticCameraSupportError, match="duplicate key"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_unknown_nested_key(tmp_path: Path) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["support"]["board_location"].update(
            {"uncontrolled_fastener": "yes"}
        ),
    )
    with pytest.raises(StaticCameraSupportError, match="unknown"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_nonfinite_json_number(tmp_path: Path) -> None:
    path = _sandbox(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        '"nominal_entrance_pupil_z_mm": 1000.0',
        '"nominal_entrance_pupil_z_mm": NaN',
        1,
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(StaticCameraSupportError, match="invalid JSON constant"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_out_of_range_geometry(tmp_path: Path) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["support"].update(
            {"nominal_entrance_pupil_z_mm": -1.0}
        ),
    )
    with pytest.raises(StaticCameraSupportError, match="must be in"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_design_path_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(StaticCameraSupportError, match="escapes the workspace"):
        load_static_camera_support_design(tmp_path, DESIGN_PATH)


@pytest.mark.parametrize("mutation", ["path", "declared_digest", "actual_bytes"])
def test_rejects_source_path_or_digest_drift(tmp_path: Path, mutation: str) -> None:
    path = _sandbox(tmp_path)
    document = _document()
    if mutation == "path":
        document["source_locks"]["workcell_layout"]["path"] = (
            "active-project/RoCell_v0_3/config/parameters.json"
        )
    elif mutation == "declared_digest":
        document["source_locks"]["workcell_layout"]["sha256"] = "0" * 64
    else:
        source = tmp_path / SOURCE_PATHS[0]
        source.write_bytes(source.read_bytes() + b"\n")
    path.write_text(
        json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )

    with pytest.raises(StaticCameraSupportError, match="path|sha256|digest mismatch"):
        load_static_camera_support_design(tmp_path, path)


@pytest.mark.parametrize(
    "field",
    [
        "fabrication_authority",
        "physical_installation_authority",
        "powered_motion_authority",
        "contact_authority",
    ],
)
def test_rejects_any_physical_or_robot_authority(tmp_path: Path, field: str) -> None:
    path = _mutated_design(
        tmp_path, lambda document: document["authority"].update({field: True})
    )
    with pytest.raises(StaticCameraSupportError, match="must remain false"):
        load_static_camera_support_design(tmp_path, path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frame_id", "Wv"),
        ("origin", "board center"),
        ("units", "inches"),
    ],
)
def test_rejects_wrong_board_source_frame(
    tmp_path: Path, field: str, value: str
) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["coordinate_frame"].update({field: value}),
    )
    with pytest.raises(StaticCameraSupportError, match="coordinate_frame"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_field_of_view_coverage_shortfall(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["optical_candidate"]["published_field_of_view"].update(
            {"horizontal_deg": 20.0, "vertical_deg": 20.0}
        )

    path = _mutated_design(tmp_path, mutate)
    with pytest.raises(StaticCameraSupportError, match="coverage shortfall"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_post_inside_radius_plus_margin(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["support"]["post_axis_xy_mm"][0] = [305.0, -100.0]

    path = _mutated_design(tmp_path, mutate)
    with pytest.raises(StaticCameraSupportError, match="post lies inside"):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_overhead_hardware_below_vertical_margin(tmp_path: Path) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["support"].update(
            {"lowest_static_hardware_z_mm": 897.0}
        ),
    )
    with pytest.raises(StaticCameraSupportError, match="below the vendor vertical"):
        load_static_camera_support_design(tmp_path, path)


@pytest.mark.parametrize(
    ("path_parts", "value", "message"),
    [
        (("lens", "mount"), "M12", "mounts do not match"),
        (("lens", "designed_sensor_format"), "1/2.3-inch", "formats do not match"),
    ],
)
def test_rejects_camera_lens_mismatch(
    tmp_path: Path,
    path_parts: tuple[str, str],
    value: str,
    message: str,
) -> None:
    group, field = path_parts
    path = _mutated_design(
        tmp_path,
        lambda document: document["optical_candidate"][group].update(
            {field: value}
        ),
    )
    with pytest.raises(StaticCameraSupportError, match=message):
        load_static_camera_support_design(tmp_path, path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("interface", "USB 2.0 UVC"),
        ("native_width_px", 3840),
        ("native_height_px", 2160),
        ("native_fps", 10.0),
        ("native_pixel_format", "MJPG"),
        ("native_aspect", "16:9"),
        ("capture_policy", "center crop"),
    ],
)
def test_rejects_noncanonical_full_native_usb3_mode(
    tmp_path: Path, field: str, value: object
) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["optical_candidate"]["camera"].update(
            {field: value}
        ),
    )
    with pytest.raises(StaticCameraSupportError):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_missing_physical_blocker(tmp_path: Path) -> None:
    path = _mutated_design(
        tmp_path, lambda document: document["open_blockers"].pop()
    )
    with pytest.raises(StaticCameraSupportError, match="every canonical"):
        load_static_camera_support_design(tmp_path, path)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        (
            "board_location",
            "new_v0_3_board_holes_allowed",
            True,
            "may not receive new support holes",
        ),
        (
            "base_constraint",
            "low_side_rails_running_rearward_beside_board_allowed",
            True,
            "low side rails may not run rearward",
        ),
    ],
)
def test_rejects_unsafe_board_or_base_route(
    tmp_path: Path, section: str, field: str, value: object, message: str
) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["support"][section].update({field: value}),
    )
    with pytest.raises(StaticCameraSupportError, match=message):
        load_static_camera_support_design(tmp_path, path)


def test_rejects_premature_cut_lengths(tmp_path: Path) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["support"].update(
            {"exact_cut_lengths_mm": [1000.0, 1000.0]}
        ),
    )
    with pytest.raises(StaticCameraSupportError, match="must remain null"):
        load_static_camera_support_design(tmp_path, path)


@pytest.mark.parametrize(
    "field",
    [
        "minimum_focus_at_nominal_1m_verified",
        "exact_case_mount_drawing_verified",
        "persistent_usb_descriptors_verified",
        "measured_usable_field_of_view_verified",
    ],
)
def test_rejects_unsubstantiated_physical_qualification(
    tmp_path: Path, field: str
) -> None:
    path = _mutated_design(
        tmp_path,
        lambda document: document["optical_candidate"][
            "qualification_inputs"
        ].update({field: True}),
    )
    with pytest.raises(StaticCameraSupportError, match="must remain null"):
        load_static_camera_support_design(tmp_path, path)


def test_source_digest_view_is_immutable() -> None:
    design = load_static_camera_support_design(WORKSPACE)
    with pytest.raises(TypeError):
        design.source_sha256["workcell_layout"] = "0" * 64  # type: ignore[index]


def test_metrics_match_independent_pinhole_calculation() -> None:
    metrics = load_static_camera_support_design(WORKSPACE).metrics
    expected_width = 2.0 * 1000.0 * math.tan(math.radians(49.0 / 2.0))
    aspect_vertical = math.degrees(
        2.0 * math.atan(math.tan(math.radians(49.0 / 2.0)) * 3648.0 / 5472.0)
    )
    expected_depth = 2.0 * 1000.0 * math.tan(
        math.radians(aspect_vertical / 2.0)
    )
    assert metrics.nominal_coverage_width_mm == pytest.approx(expected_width)
    assert metrics.nominal_coverage_depth_mm == pytest.approx(expected_depth)
    expected_published_depth = 2.0 * 1000.0 * math.tan(math.radians(38.0 / 2.0))
    expected_worst_density = min(
        5472.0 / expected_width,
        3648.0 / expected_published_depth,
    )
    assert metrics.nominal_conservative_pixels_per_mm == pytest.approx(
        expected_worst_density
    )
    assert metrics.nominal_tag_width_pixels == pytest.approx(
        40.0 * expected_worst_density
    )
