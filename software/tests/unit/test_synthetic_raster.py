from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
import json
import math
from pathlib import Path

import pytest

from rocell.models.frames import FrameMismatchError, Point3Mm, Transform
from rocell.simulation import load_rc03_nominal_scene, load_simulation_scenario
from rocell.simulation.synthetic_raster import (
    SyntheticCaptureTiming,
    SyntheticOverviewRasterRenderer,
    SyntheticRasterBackendUnavailable,
    SyntheticRasterConfig,
    SyntheticRasterResourceLimitError,
    SyntheticRasterValidationError,
)
from rocell.vision.apriltag_codebook import (
    DEFAULT_APRILTAG_36H11_CODEBOOK,
)
from rocell.vision.camera import FramePacket, TimestampQuality


WORKSPACE = Path(__file__).resolve().parents[3]
RC03_ROOT = WORKSPACE / "active-project" / "RoCell_v0_3"
TAG_ASSETS = RC03_ROOT / "fiducials"


def _renderer(
    *,
    config: SyntheticRasterConfig | None = None,
) -> SyntheticOverviewRasterRenderer:
    scenario = load_simulation_scenario(WORKSPACE)
    scene = load_rc03_nominal_scene(
        RC03_ROOT,
        assumed_tag_plane_z_mm=scenario.assumed_tag_plane_z_mm,
        station_proxy_height_mm=scenario.station_proxy_height_mm,
    )
    return SyntheticOverviewRasterRenderer(
        scene=scene,
        camera=scenario.overview.camera,
        camera_T_board=scenario.overview.camera_T_board,
        tag_asset_root=TAG_ASSETS,
        config=config or SyntheticRasterConfig(),
    )


def _decode(frame: FramePacket):  # type: ignore[no-untyped-def]
    Image = pytest.importorskip("PIL.Image")
    image = Image.open(BytesIO(frame.jpeg_bytes)).convert("L")
    image.load()
    return image


def _tag_cell_center(tag, row: int, column: int) -> Point3Mm:  # type: ignore[no-untyped-def]
    half = tag.detection_edge_mm / 2.0
    cell = tag.detection_edge_mm / 8.0
    local_x = -half + (column + 0.5) * cell
    local_y = half - (row + 0.5) * cell
    cosine = math.cos(tag.yaw_rad)
    sine = math.sin(tag.yaw_rad)
    return Point3Mm(
        tag.center.frame,
        tag.center.x + cosine * local_x - sine * local_y,
        tag.center.y + sine * local_x + cosine * local_y,
        tag.center.z,
    )


def _sample_board_point(renderer, image, point: Point3Mm) -> int:  # type: ignore[no-untyped-def]
    projected = renderer.camera.project(renderer.camera_T_board.transform_point(point))
    assert projected.in_bounds
    xy = (int(math.floor(projected.u_px + 0.5)), int(math.floor(projected.v_px + 0.5)))
    return int(image.getpixel(xy))


def test_released_codebook_is_immutable_content_addressed_and_oriented() -> None:
    codebook = DEFAULT_APRILTAG_36H11_CODEBOOK
    assert codebook.family == "tag36h11"
    assert codebook.tag_ids == (0, 1, 2, 3, 4, 5)
    assert codebook.pattern(0)[1] == (0, 0, 0, 1, 0, 0, 0, 0)
    assert codebook.marked_corner_order == "TL_TR_BR_BL"
    assert codebook.marked_top_direction == "+LOCAL_Y"
    assert len(codebook.codebook_sha256) == 64
    assert len(codebook.codewords) == 6
    with pytest.raises(FrozenInstanceError):
        codebook.family = "other"  # type: ignore[misc]


def test_renderer_produces_deterministic_real_jpeg_without_detection_truth() -> None:
    renderer = _renderer()
    first = renderer.render(sequence=0)
    repeated = renderer.render(sequence=0)
    next_sequence = renderer.render(sequence=1)

    assert isinstance(first.frame_packet, FramePacket)
    assert first.frame_packet.jpeg_bytes[:2] == b"\xff\xd8"
    assert first.frame_packet.jpeg_bytes[-2:] == b"\xff\xd9"
    assert first.frame_packet.jpeg_bytes == repeated.frame_packet.jpeg_bytes
    assert first.render_hash == repeated.render_hash
    # Sequence is provenance only; the fixed scene pixels remain identical.
    assert first.frame_packet.jpeg_bytes == next_sequence.frame_packet.jpeg_bytes
    assert first.frame_packet.capture_id != next_sequence.frame_packet.capture_id
    assert first.frame_packet.settings_hash == first.renderer_definition_sha256
    assert first.renderer_config_sha256 == renderer.config.config_sha256
    assert len(first.source_bundle_sha256) == 64
    assert _decode(first.frame_packet).mode == "L"

    document = first.to_dict()
    serialized = json.dumps(document, sort_keys=True)
    assert document["embedded_detection_truth"] is False
    assert document["detector_input_contract"] == "FRAME_PACKET_JPEG_BYTES_ONLY"
    assert document["authority"]["hardware_commands_generated"] == 0  # type: ignore[index]
    assert "tag_id" not in serialized
    assert "corners" not in serialized
    assert "jpeg_bytes" not in serialized


def test_all_six_projected_patterns_are_encoded_in_pixels_with_marked_orientation() -> None:
    renderer = _renderer()
    rendered = renderer.render()
    image = _decode(rendered.frame_packet)
    codebook = DEFAULT_APRILTAG_36H11_CODEBOOK

    for tag in renderer.scene.fiducials:
        grid = codebook.pattern(tag.tag_id)
        for row in range(8):
            for column in range(8):
                gray = _sample_board_point(
                    renderer,
                    image,
                    _tag_cell_center(tag, row, column),
                )
                if grid[row][column] == 0:
                    assert gray < 50
                else:
                    assert gray > 220

        # The 55 mm tile supplies white quiet margin outside the 40 mm marker.
        quiet_local_x = tag.detection_edge_mm / 2.0 + 2.0
        cosine = math.cos(tag.yaw_rad)
        sine = math.sin(tag.yaw_rad)
        quiet_point = Point3Mm(
            tag.center.frame,
            tag.center.x + cosine * quiet_local_x,
            tag.center.y + sine * quiet_local_x,
            tag.center.z,
        )
        assert _sample_board_point(renderer, image, quiet_point) > 220


def test_tag_loss_is_a_hashed_pixel_change_not_detector_metadata() -> None:
    complete_renderer = _renderer()
    occluded_renderer = _renderer(config=SyntheticRasterConfig(occluded_tag_ids=(4,)))
    complete = complete_renderer.render()
    occluded = occluded_renderer.render()
    assert complete.frame_packet.sha256 != occluded.frame_packet.sha256
    assert complete.renderer_config_sha256 != occluded.renderer_config_sha256
    assert complete.renderer_definition_sha256 != occluded.renderer_definition_sha256

    tag = next(tag for tag in occluded_renderer.scene.fiducials if tag.tag_id == 4)
    complete_image = _decode(complete.frame_packet)
    occluded_image = _decode(occluded.frame_packet)
    black_cell_center = _tag_cell_center(tag, 0, 0)
    assert _sample_board_point(complete_renderer, complete_image, black_cell_center) < 50
    assert _sample_board_point(occluded_renderer, occluded_image, black_cell_center) > 150

    # The output provenance contains only hashes, never the selected truth ID.
    assert "occluded_tag_ids" not in json.dumps(occluded.to_dict(), sort_keys=True)


def test_renderer_validates_frame_contract_and_resource_bounds() -> None:
    renderer = _renderer()
    with pytest.raises(FrameMismatchError, match="output frame"):
        SyntheticOverviewRasterRenderer(
            scene=renderer.scene,
            camera=renderer.camera,
            camera_T_board=Transform.identity(renderer.scene.board_frame),
            tag_asset_root=TAG_ASSETS,
        )
    with pytest.raises(SyntheticRasterResourceLimitError, match="JPEG"):
        _renderer(config=SyntheticRasterConfig(maximum_jpeg_bytes=1024)).render()
    with pytest.raises(ValueError, match="not in the scene"):
        _renderer(config=SyntheticRasterConfig(occluded_tag_ids=(9,)))


def test_optional_backend_failure_is_clear_and_imports_remain_lazy(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import rocell.simulation.synthetic_raster as module

    renderer = _renderer()

    def unavailable():  # type: ignore[no-untyped-def]
        raise SyntheticRasterBackendUnavailable("Pillow intentionally unavailable")

    monkeypatch.setattr(module, "_load_pillow", unavailable)
    with pytest.raises(SyntheticRasterBackendUnavailable, match="Pillow"):
        renderer.render()


def test_partial_scene_is_explicit_and_clipped_by_the_pixel_backend() -> None:
    complete = _renderer()
    narrow_camera = replace(
        complete.camera,
        width_px=complete.camera.width_px // 2,
    )
    strict = SyntheticOverviewRasterRenderer(
        scene=complete.scene,
        camera=narrow_camera,
        camera_T_board=complete.camera_T_board,
        tag_asset_root=TAG_ASSETS,
    )
    with pytest.raises(SyntheticRasterValidationError, match="leaves"):
        strict.render()

    clipped = SyntheticOverviewRasterRenderer(
        scene=complete.scene,
        camera=narrow_camera,
        camera_T_board=complete.camera_T_board,
        tag_asset_root=TAG_ASSETS,
        config=SyntheticRasterConfig(allow_partial_scene=True),
    ).render()
    assert clipped.frame_packet.width_px == narrow_camera.width_px
    assert _decode(clipped.frame_packet).size == (
        narrow_camera.width_px,
        narrow_camera.height_px,
    )


def test_pixel_perturbations_are_bounded_hashed_and_repeatable() -> None:
    clean = _renderer().render(sequence=12)
    config = SyntheticRasterConfig(
        noise_amplitude_gray=3,
        gaussian_blur_radius_px=0.75,
        horizontal_motion_blur_px=2,
    )
    renderer = _renderer(config=config)
    first = renderer.render(sequence=12)
    repeated = renderer.render(sequence=12)
    changed_seed = renderer.render(sequence=13)

    assert first.frame_packet.jpeg_bytes == repeated.frame_packet.jpeg_bytes
    assert first.frame_packet.jpeg_bytes != clean.frame_packet.jpeg_bytes
    assert first.frame_packet.jpeg_bytes != changed_seed.frame_packet.jpeg_bytes
    assert first.renderer_config_sha256 == config.config_sha256
    perturbations = config.to_dict()["pixel_perturbations"]
    assert isinstance(perturbations, dict)
    assert perturbations["deterministic"] is True

    with pytest.raises(SyntheticRasterValidationError, match="noise_amplitude"):
        SyntheticRasterConfig(noise_amplitude_gray=97)
    with pytest.raises(SyntheticRasterValidationError, match="gaussian_blur"):
        SyntheticRasterConfig(gaussian_blur_radius_px=float("nan"))


def test_explicit_synthetic_timing_is_preserved_without_exposure_claim() -> None:
    timing = SyntheticCaptureTiming(
        source_timestamp_ns=1_000_010,
        source_clock="virtual_arm_camera_clock",
        host_request_ns=1_000_000,
        host_first_byte_ns=1_000_020,
        host_complete_ns=1_000_030,
        timestamp_quality=TimestampQuality.SETTLED_BRACKET,
        freshness_token="arm-camera-frame-7",
    )
    frame = _renderer().render(sequence=7, timing=timing).frame_packet
    assert frame.source_timestamp_ns == 1_000_010
    assert frame.source_clock == "virtual_arm_camera_clock"
    assert frame.host_request_ns == 1_000_000
    assert frame.host_complete_ns == 1_000_030
    assert frame.timestamp_quality is TimestampQuality.SETTLED_BRACKET
    assert frame.freshness_token == "arm-camera-frame-7"

    with pytest.raises(SyntheticRasterValidationError, match="DEVICE_EXPOSURE"):
        replace(timing, timestamp_quality=TimestampQuality.DEVICE_EXPOSURE)
