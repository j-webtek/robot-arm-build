from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import inspect
from pathlib import Path

import pytest

from rocell.simulation import load_rc03_nominal_scene, load_simulation_scenario
from rocell.simulation.synthetic_raster import (
    SyntheticOverviewRasterRenderer,
    SyntheticRasterConfig,
)
from rocell.vision import (
    AprilTag36h11PixelDetector,
    AprilTagPatternCodebook,
    AprilTagPixelDetectorConfiguration,
    AprilTagPixelDetectorError,
    DEFAULT_APRILTAG_36H11_CODEBOOK,
    FramePacket,
    PixelDecodeError,
    PixelDetectorResourceLimitError,
    TimestampQuality,
    detect_apriltag36h11_pixels,
)


WORKSPACE = Path(__file__).resolve().parents[3]
RC03_ROOT = WORKSPACE / "active-project" / "RoCell_v0_3"
TAG_ASSETS = RC03_ROOT / "fiducials"


def _configuration(**changes: object) -> AprilTagPixelDetectorConfiguration:
    return replace(
        AprilTagPixelDetectorConfiguration(host_clock="test.monotonic"),
        **changes,
    )


def _detector(
    **changes: object,
) -> AprilTag36h11PixelDetector:
    return AprilTag36h11PixelDetector(
        configuration=_configuration(**changes),
        codebook=DEFAULT_APRILTAG_36H11_CODEBOOK,
    )


def _frame(jpeg: bytes, width: int, height: int, *, capture_id: str = "pixels-1") -> FramePacket:
    return FramePacket(
        capture_id=capture_id,
        jpeg_bytes=jpeg,
        width_px=width,
        height_px=height,
        source_sequence=1,
        source_timestamp_ns=100,
        source_clock="test.camera",
        host_request_ns=90,
        host_first_byte_ns=105,
        host_complete_ns=110,
        settings_hash="a" * 64,
        timestamp_quality=TimestampQuality.DEVICE_EXPOSURE,
        freshness_token="sequence:1",
        freshness_basis="device_sequence",
    )


def _jpeg(image: object) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG", quality=100, subsampling=0)  # type: ignore[attr-defined]
    return output.getvalue()


def _tag_frame(
    tag_id: int,
    *,
    rotations_cw: int = 0,
    flipped_payload_cell: tuple[int, int] | None = None,
    black_value: int = 0,
    white_value: int = 255,
) -> FramePacket:
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    cell_px = 16
    tile_cells = 10
    tile_px = cell_px * tile_cells
    tile = Image.new("L", (tile_px, tile_px), white_value)
    draw = ImageDraw.Draw(tile)
    pattern = [list(row) for row in DEFAULT_APRILTAG_36H11_CODEBOOK.pattern(tag_id)]
    if flipped_payload_cell is not None:
        row, column = flipped_payload_cell
        pattern[row][column] = 1 - pattern[row][column]
    for row in range(8):
        for column in range(8):
            if pattern[row][column] == 0:
                x0 = (column + 1) * cell_px
                y0 = (row + 1) * cell_px
                draw.rectangle(
                    (x0, y0, x0 + cell_px - 1, y0 + cell_px - 1),
                    fill=black_value,
                )
    for _ in range(rotations_cw % 4):
        tile = tile.transpose(Image.Transpose.ROTATE_270)
    canvas = Image.new("L", (240, 224), white_value)
    canvas.paste(tile, (40, 32))
    return _frame(_jpeg(canvas), 240, 224, capture_id=f"tag-{tag_id}-r{rotations_cw}")


def _minimal_structural_jpeg(width: int, height: int) -> bytes:
    """Pass FramePacket's structural parser but intentionally fail pixel decode."""

    sof_payload = (
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x01\x01\x11\x00"
    )
    return (
        b"\xff\xd8\xff\xc0"
        + (len(sof_payload) + 2).to_bytes(2, "big")
        + sof_payload
        + b"\xff\xd9"
    )


def _project_quad(
    corners: tuple[tuple[float, float], ...], u: float, v: float
) -> tuple[float, float]:
    """Independent test renderer for one planar projective quadrilateral."""

    top_left, top_right, bottom_right, bottom_left = corners
    dx1 = top_right[0] - bottom_right[0]
    dx2 = bottom_left[0] - bottom_right[0]
    dx3 = top_left[0] - top_right[0] + bottom_right[0] - bottom_left[0]
    dy1 = top_right[1] - bottom_right[1]
    dy2 = bottom_left[1] - bottom_right[1]
    dy3 = top_left[1] - top_right[1] + bottom_right[1] - bottom_left[1]
    denominator = dx1 * dy2 - dx2 * dy1
    projective_x = 0.0 if dx3 == dy3 == 0.0 else (dx3 * dy2 - dx2 * dy3) / denominator
    projective_y = 0.0 if dx3 == dy3 == 0.0 else (dx1 * dy3 - dx3 * dy1) / denominator
    a = top_right[0] - top_left[0] + projective_x * top_right[0]
    b = bottom_left[0] - top_left[0] + projective_y * bottom_left[0]
    d = top_right[1] - top_left[1] + projective_x * top_right[1]
    e = bottom_left[1] - top_left[1] + projective_y * bottom_left[1]
    scale = projective_x * u + projective_y * v + 1.0
    return (
        (a * u + b * v + top_left[0]) / scale,
        (d * u + e * v + top_left[1]) / scale,
    )


def _perspective_tag_frame(
    tag_id: int,
) -> tuple[FramePacket, tuple[tuple[float, float], ...]]:
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    corners = ((52.0, 42.0), (212.0, 28.0), (194.0, 194.0), (35.0, 174.0))
    image = Image.new("L", (260, 224), 245)
    draw = ImageDraw.Draw(image)
    pattern = DEFAULT_APRILTAG_36H11_CODEBOOK.pattern(tag_id)
    for row in range(8):
        for column in range(8):
            if pattern[row][column] != 0:
                continue
            polygon = tuple(
                _project_quad(corners, u, v)
                for u, v in (
                    (column / 8.0, row / 8.0),
                    ((column + 1) / 8.0, row / 8.0),
                    ((column + 1) / 8.0, (row + 1) / 8.0),
                    (column / 8.0, (row + 1) / 8.0),
                )
            )
            draw.polygon(polygon, fill=5)
    return _frame(_jpeg(image), 260, 224, capture_id=f"perspective-{tag_id}"), corners


def _adversarial_tag_frame(tag_id: int, degradation: str) -> FramePacket:
    """Create degraded pixels without giving the detector renderer metadata."""

    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    ImageFilter = pytest.importorskip("PIL.ImageFilter")
    source = Image.open(BytesIO(_tag_frame(tag_id).jpeg_bytes)).convert("L")

    if degradation == "blur":
        changed = source.filter(ImageFilter.GaussianBlur(radius=5.0))
    elif degradation == "glare":
        changed = source.copy()
        # The diagonal saturated band crosses border and payload cells.
        ImageDraw.Draw(changed).polygon(
            ((58, 25), (91, 25), (192, 201), (159, 201)), fill=255
        )
    elif degradation == "low-contrast":
        changed = source.point(lambda value: 112 + (value * 30 // 255))
    elif degradation == "deterministic-noise":
        changed = source.copy()
        pixels = changed.load()
        for ordinal in range(1_400):
            # Co-prime modular walks make the corruption reproducible and
            # cover the complete image without using production randomness.
            x = (ordinal * 73 + 19) % changed.width
            y = (ordinal * 97 + 31) % changed.height
            pixels[x, y] = 0 if ordinal % 2 else 255
    elif degradation == "border-clipped":
        changed = Image.new("L", source.size, 255)
        # Move most of the tag outside the frame while retaining a plausible
        # high-contrast quadrilateral fragment at the image boundary.
        changed.paste(source.crop((40, 32, 200, 192)), (-112, 28))
    else:  # pragma: no cover - helper is only called with the cases below.
        raise AssertionError(f"unsupported degradation: {degradation}")

    return _frame(
        _jpeg(changed),
        changed.width,
        changed.height,
        capture_id=f"adversarial-{tag_id}-{degradation}",
    )


def _overview_renderer(
    *, config: SyntheticRasterConfig | None = None
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


def test_api_accepts_only_frame_configuration_and_explicit_codebook() -> None:
    method_parameters = tuple(inspect.signature(AprilTag36h11PixelDetector.detect).parameters)
    function_parameters = inspect.signature(detect_apriltag36h11_pixels).parameters
    assert method_parameters == ("self", "frame")
    assert tuple(function_parameters) == ("frame", "configuration", "codebook")
    assert function_parameters["configuration"].kind is inspect.Parameter.KEYWORD_ONLY
    assert function_parameters["codebook"].kind is inspect.Parameter.KEYWORD_ONLY


def test_detects_all_released_tags_from_independent_renderer_jpeg() -> None:
    rendered = _overview_renderer().render(sequence=7)
    batch = _detector().detect(rendered.frame_packet)

    assert tuple(detection.tag.tag_id for detection in batch.detections) == (0, 1, 2, 3, 4, 5)
    assert all(detection.hamming == 0 for detection in batch.detections)
    assert all(detection.detector_accepted for detection in batch.detections)
    assert batch.frame.jpeg_sha256 == rendered.frame_packet.sha256
    assert batch.frame.capture_id == rendered.frame_packet.capture_id
    assert batch.detector.configuration_sha256 == _configuration().configuration_sha256(
        DEFAULT_APRILTAG_36H11_CODEBOOK
    )
    assert len(batch.detector.implementation_sha256) == 64
    assert batch.to_dict()["authority"] == {
        "physical_authority": "NONE",
        "physical_commands_generated": 0,
        "can_authorize_motion": False,
        "can_release_physical_gates": False,
    }

    # Occlusion changes pixels/configuration only.  The detector is not given
    # the renderer wrapper or its occluded-tag selection.
    occluded_frame = _overview_renderer(
        config=SyntheticRasterConfig(occluded_tag_ids=(4,))
    ).render().frame_packet
    occluded = _detector().detect(occluded_frame)
    assert tuple(detection.tag.tag_id for detection in occluded.detections) == (0, 1, 2, 3, 5)


@pytest.mark.parametrize("rotations_cw", (0, 1, 2, 3))
def test_rotation_decode_returns_marked_tag_tl_tr_br_bl(rotations_cw: int) -> None:
    frame = _tag_frame(3, rotations_cw=rotations_cw)
    batch = _detector().detect(frame)
    assert len(batch.detections) == 1
    detection = batch.detections[0]
    assert detection.tag.tag_id == 3
    assert detection.hamming == 0
    assert detection.detector_accepted

    # Marker boundary before rotation, including the canvas paste offset.  The
    # expected sequence follows the physically marked tag corners, not the
    # image's geometric top-left after rotation.
    tile_size_minus_one = 159.0
    marked = [(15.5, 15.5), (143.5, 15.5), (143.5, 143.5), (15.5, 143.5)]
    for _ in range(rotations_cw):
        marked = [(tile_size_minus_one - y, x) for x, y in marked]
    expected = [(x + 40.0, y + 32.0) for x, y in marked]
    actual = [(corner.x_px, corner.y_px) for corner in detection.corners_px]
    for observed, wanted in zip(actual, expected):
        assert observed == pytest.approx(wanted, abs=1.1)


def test_perspective_sampling_decodes_without_expected_corner_input() -> None:
    frame, rendered_corners = _perspective_tag_frame(5)
    detection = _detector().detect(frame).detections
    assert len(detection) == 1
    assert detection[0].tag.tag_id == 5
    assert detection[0].hamming == 0
    assert detection[0].detector_accepted
    for observed, rendered in zip(detection[0].corners_px, rendered_corners):
        assert (observed.x_px, observed.y_px) == pytest.approx(rendered, abs=2.5)


@pytest.mark.parametrize(
    "degradation",
    ("blur", "glare", "low-contrast", "deterministic-noise", "border-clipped"),
)
def test_adversarial_pixels_never_become_a_wrong_accepted_identity(
    degradation: str,
) -> None:
    """A degraded known tag may be rejected, but never accepted as another tag."""

    expected_tag_id = 2
    detections = _detector().detect(
        _adversarial_tag_frame(expected_tag_id, degradation)
    ).detections
    accepted = tuple(item for item in detections if item.detector_accepted)

    assert len(accepted) <= 1
    assert all(item.tag.tag_id == expected_tag_id for item in accepted)
    assert all(item.hamming <= _configuration().maximum_hamming for item in accepted)


def test_hamming_and_margin_policies_emit_explicit_rejection() -> None:
    frame = _tag_frame(0, flipped_payload_cell=(2, 2))
    accepted = _detector(maximum_hamming=1).detect(frame).detections
    assert len(accepted) == 1
    assert accepted[0].tag.tag_id == 0
    assert accepted[0].hamming == 1
    assert accepted[0].detector_accepted

    rejected = _detector(maximum_hamming=0).detect(frame).detections
    assert len(rejected) == 1
    assert rejected[0].tag.tag_id == 0
    assert rejected[0].hamming == 1
    assert rejected[0].rejection_reason == "hamming_policy"

    low_margin = _detector(minimum_decision_margin=60.0).detect(
        _tag_frame(1, black_value=80, white_value=180)
    ).detections
    assert len(low_margin) == 1
    assert low_margin[0].rejection_reason == "decision_margin_policy"


def test_blank_malformed_and_oversized_inputs_fail_closed() -> None:
    Image = pytest.importorskip("PIL.Image")
    blank = Image.new("L", (160, 120), 255)
    blank_frame = _frame(_jpeg(blank), 160, 120, capture_id="blank")
    assert _detector().detect(blank_frame).detections == ()

    malformed = _frame(
        _minimal_structural_jpeg(160, 120),
        160,
        120,
        capture_id="structural-only",
    )
    with pytest.raises(PixelDecodeError, match="decode"):
        _detector().detect(malformed)
    with pytest.raises(PixelDetectorResourceLimitError, match="JPEG"):
        _detector(maximum_jpeg_bytes=len(blank_frame.jpeg_bytes) - 1).detect(blank_frame)
    with pytest.raises(PixelDetectorResourceLimitError, match="pixels"):
        _detector(maximum_image_pixels=160 * 120 - 1).detect(blank_frame)

    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    black = Image.new("L", (160, 120), 0)
    ImageDraw.Draw(black).rectangle((0, 0, 15, 119), fill=255)
    black_frame = _frame(_jpeg(black), 160, 120, capture_id="black")
    with pytest.raises(AprilTagPixelDetectorError, match="dark-pixel fraction"):
        _detector().detect(black_frame)


def test_configuration_is_strict_and_codebook_content_is_hash_bound() -> None:
    with pytest.raises(AprilTagPixelDetectorError, match="sampling_grid_width"):
        AprilTagPixelDetectorConfiguration(
            host_clock="test.monotonic", sampling_grid_width=True  # type: ignore[arg-type]
        )
    with pytest.raises(AprilTagPixelDetectorError, match="cannot exceed"):
        AprilTagPixelDetectorConfiguration(
            host_clock="test.monotonic",
            maximum_hamming=2,
            maximum_reported_hamming=1,
        )

    changed_patterns = list(DEFAULT_APRILTAG_36H11_CODEBOOK.patterns)
    tag_id, grid = changed_patterns[0]
    rows = [list(row) for row in grid]
    rows[2][2] = 1 - rows[2][2]
    changed_patterns[0] = (tag_id, tuple(tuple(row) for row in rows))
    changed_codebook = AprilTagPatternCodebook(
        family="tag36h11", patterns=tuple(changed_patterns)
    )
    configuration = _configuration()
    assert changed_codebook.codebook_sha256 != DEFAULT_APRILTAG_36H11_CODEBOOK.codebook_sha256
    assert configuration.configuration_sha256(changed_codebook) != configuration.configuration_sha256(
        DEFAULT_APRILTAG_36H11_CODEBOOK
    )
