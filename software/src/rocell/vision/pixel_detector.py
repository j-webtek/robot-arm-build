"""Independent, bounded AprilTag pixel detection for released RC03 tags.

The detector accepts exactly three sources of information: an immutable
``FramePacket``, an immutable detector configuration, and an explicit released
tag codebook.  It has no scene, tag-map, planned target, expected corner, or
ground-truth observation input.  JPEG decoding is lazy and optional through
Pillow; candidate location, projective sampling, rotation recovery, and
Hamming-policy decisions are implemented here without OpenCV.

This is deliberately a small, deterministic pre-hardware detector, not a claim
of parity with the upstream AprilTag library.  It is suitable for the bounded
synthetic commissioning images and for exercising the real byte-to-record
boundary.  Physical qualification still requires measured image campaigns.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Iterable, Sequence, TypeVar

from .apriltag_codebook import AprilTagPatternCodebook
from .camera import FramePacket
from .detections import (
    AprilTagDetection,
    AprilTagDetectionBatch,
    DetectorIdentity,
    FrameCaptureBinding,
    PixelCorner,
    TagReference,
    VisionRecordError,
    _finite,
    _identifier,
    _integer,
)


PIXEL_DETECTOR_ID = "rocell.apriltag36h11.pixel"
PIXEL_DETECTOR_VERSION = "1.0.0"
PIXEL_DETECTOR_CONTRACT = "rocell.apriltag36h11_pixel_detector.v1"
RELEASED_TAG_IDS = (0, 1, 2, 3, 4, 5)

DEFAULT_MAXIMUM_JPEG_BYTES = 16 * 1024 * 1024
DEFAULT_MAXIMUM_IMAGE_PIXELS = 12_000_000
DEFAULT_MAXIMUM_RUNS = 300_000
DEFAULT_MAXIMUM_COMPONENT_RUNS = 20_000
DEFAULT_MAXIMUM_HULL_VERTICES = 2_048


class AprilTagPixelDetectorError(VisionRecordError):
    """A pixel frame, detector configuration, or candidate failed closed."""


class PixelDecoderUnavailableError(AprilTagPixelDetectorError):
    """The optional Pillow JPEG backend is not installed."""


class PixelDecodeError(AprilTagPixelDetectorError):
    """JPEG bytes could not be decoded exactly as their frame metadata claims."""


class PixelDetectorResourceLimitError(AprilTagPixelDetectorError):
    """A byte, pixel, run, component, hull, or candidate limit was exceeded."""


def _canonical_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AprilTagPixelDetectorError(
            f"pixel-detector definition is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class AprilTagPixelDetectorConfiguration:
    """All policy and resource inputs that can affect a detection batch."""

    host_clock: str
    maximum_jpeg_bytes: int = DEFAULT_MAXIMUM_JPEG_BYTES
    maximum_image_pixels: int = DEFAULT_MAXIMUM_IMAGE_PIXELS
    maximum_runs: int = DEFAULT_MAXIMUM_RUNS
    maximum_component_runs: int = DEFAULT_MAXIMUM_COMPONENT_RUNS
    maximum_hull_vertices: int = DEFAULT_MAXIMUM_HULL_VERTICES
    maximum_candidates: int = 64
    minimum_component_pixels: int = 64
    minimum_tag_edge_px: float = 12.0
    maximum_aspect_ratio: float = 4.0
    minimum_component_fill_fraction: float = 0.08
    maximum_component_fill_fraction: float = 0.95
    maximum_dark_fraction: float = 0.80
    otsu_threshold_offset: int = 0
    sampling_grid_width: int = 3
    sampling_spread_cell: float = 0.20
    maximum_hamming: int = 1
    maximum_reported_hamming: int = 5
    maximum_border_errors: int = 0
    minimum_decision_margin: float = 8.0
    contract: str = PIXEL_DETECTOR_CONTRACT

    def __post_init__(self) -> None:
        object.__setattr__(self, "host_clock", _identifier(self.host_clock, "host_clock"))
        for name, minimum, maximum in (
            ("maximum_jpeg_bytes", 1, 128 * 1024 * 1024),
            ("maximum_image_pixels", 1, 100_000_000),
            ("maximum_runs", 1, 2_000_000),
            ("maximum_component_runs", 1, 500_000),
            ("maximum_hull_vertices", 4, 100_000),
            ("maximum_candidates", 1, 256),
            ("minimum_component_pixels", 4, 100_000_000),
            ("maximum_hamming", 0, 5),
            ("maximum_reported_hamming", 0, 5),
            ("maximum_border_errors", 0, 28),
        ):
            object.__setattr__(
                self,
                name,
                _integer(getattr(self, name), name, minimum=minimum, maximum=maximum),
            )
        if self.maximum_component_runs > self.maximum_runs:
            raise AprilTagPixelDetectorError(
                "maximum_component_runs cannot exceed maximum_runs"
            )
        if self.maximum_hamming > self.maximum_reported_hamming:
            raise AprilTagPixelDetectorError(
                "maximum_hamming cannot exceed maximum_reported_hamming"
            )
        if (
            isinstance(self.sampling_grid_width, bool)
            or not isinstance(self.sampling_grid_width, int)
            or self.sampling_grid_width not in (1, 3, 5)
        ):
            raise AprilTagPixelDetectorError(
                "sampling_grid_width must be one of 1, 3, or 5"
            )
        if (
            isinstance(self.otsu_threshold_offset, bool)
            or not isinstance(self.otsu_threshold_offset, int)
            or not -64 <= self.otsu_threshold_offset <= 64
        ):
            raise AprilTagPixelDetectorError(
                "otsu_threshold_offset must be an integer within [-64, 64]"
            )
        for name, float_minimum, float_maximum in (
            ("minimum_tag_edge_px", 4.0, 100_000.0),
            ("maximum_aspect_ratio", 1.0, 100.0),
            ("minimum_component_fill_fraction", 0.001, 0.999),
            ("maximum_component_fill_fraction", 0.001, 0.999),
            ("maximum_dark_fraction", 0.001, 0.999),
            ("sampling_spread_cell", 0.0, 0.45),
            ("minimum_decision_margin", 0.0, 127.5),
        ):
            object.__setattr__(
                self,
                name,
                _finite(
                    getattr(self, name),
                    name,
                    minimum=float_minimum,
                    maximum=float_maximum,
                ),
            )
        if self.minimum_component_fill_fraction >= self.maximum_component_fill_fraction:
            raise AprilTagPixelDetectorError(
                "component fill interval must be strictly increasing"
            )
        if self.contract != PIXEL_DETECTOR_CONTRACT:
            raise AprilTagPixelDetectorError(
                f"contract must equal {PIXEL_DETECTOR_CONTRACT!r}"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract,
            "host_clock": self.host_clock,
            "resources": {
                "maximum_jpeg_bytes": self.maximum_jpeg_bytes,
                "maximum_image_pixels": self.maximum_image_pixels,
                "maximum_runs": self.maximum_runs,
                "maximum_component_runs": self.maximum_component_runs,
                "maximum_hull_vertices": self.maximum_hull_vertices,
                "maximum_candidates": self.maximum_candidates,
                "minimum_component_pixels": self.minimum_component_pixels,
            },
            "candidate_policy": {
                "minimum_tag_edge_px": self.minimum_tag_edge_px,
                "maximum_aspect_ratio": self.maximum_aspect_ratio,
                "minimum_component_fill_fraction": self.minimum_component_fill_fraction,
                "maximum_component_fill_fraction": self.maximum_component_fill_fraction,
                "maximum_dark_fraction": self.maximum_dark_fraction,
                "otsu_threshold_offset": self.otsu_threshold_offset,
            },
            "sampling_policy": {
                "sampling_grid_width": self.sampling_grid_width,
                "sampling_spread_cell": self.sampling_spread_cell,
            },
            "decode_policy": {
                "maximum_hamming": self.maximum_hamming,
                "maximum_reported_hamming": self.maximum_reported_hamming,
                "maximum_border_errors": self.maximum_border_errors,
                "minimum_decision_margin": self.minimum_decision_margin,
            },
        }

    def configuration_sha256(self, codebook: AprilTagPatternCodebook) -> str:
        if not isinstance(codebook, AprilTagPatternCodebook):
            raise TypeError("codebook must be an AprilTagPatternCodebook")
        return _canonical_hash(
            {
                "configuration": self.to_dict(),
                "codebook_sha256": codebook.codebook_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class _GrayImage:
    width: int
    height: int
    pixels: bytes

    def value(self, x: int, y: int) -> int:
        return self.pixels[y * self.width + x]


def _decode_jpeg(
    frame: FramePacket,
    configuration: AprilTagPixelDetectorConfiguration,
) -> _GrayImage:
    """Lazily import Pillow and return an immutable 8-bit grayscale image."""

    if len(frame.jpeg_bytes) > configuration.maximum_jpeg_bytes:
        raise PixelDetectorResourceLimitError(
            f"JPEG exceeds {configuration.maximum_jpeg_bytes} bytes"
        )
    pixel_count = frame.width_px * frame.height_px
    if pixel_count > configuration.maximum_image_pixels:
        raise PixelDetectorResourceLimitError(
            f"frame exceeds {configuration.maximum_image_pixels} pixels"
        )
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - exercised without vision extra
        raise PixelDecoderUnavailableError(
            "Pillow is required for AprilTag JPEG pixel detection"
        ) from exc

    try:
        with Image.open(BytesIO(frame.jpeg_bytes)) as encoded:
            if encoded.format != "JPEG":
                raise PixelDecodeError("FramePacket bytes did not decode as JPEG")
            if encoded.size != (frame.width_px, frame.height_px):
                raise PixelDecodeError(
                    "decoded JPEG dimensions differ from FramePacket metadata"
                )
            encoded.load()
            gray = encoded.convert("L")
            pixels = gray.tobytes()
    except PixelDecodeError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise PixelDecodeError(f"JPEG pixel decode failed: {exc}") from exc
    if len(pixels) != pixel_count:
        raise PixelDecodeError("decoded grayscale byte count is inconsistent")
    return _GrayImage(frame.width_px, frame.height_px, pixels)


def _otsu_threshold(pixels: bytes) -> int | None:
    histogram = [0] * 256
    for value in pixels:
        histogram[value] += 1
    populated = [index for index, count in enumerate(histogram) if count]
    if len(populated) < 2:
        return None
    total = len(pixels)
    weighted_total = sum(index * count for index, count in enumerate(histogram))
    background_weight = 0
    background_sum = 0
    best_threshold = populated[0]
    best_variance = -1.0
    for threshold in range(255):
        count = histogram[threshold]
        background_weight += count
        background_sum += threshold * count
        if background_weight == 0:
            continue
        foreground_weight = total - background_weight
        if foreground_weight == 0:
            break
        background_mean = background_sum / background_weight
        foreground_mean = (weighted_total - background_sum) / foreground_weight
        between_variance = (
            background_weight
            * foreground_weight
            * (background_mean - foreground_mean) ** 2
        )
        if between_variance > best_variance:
            best_variance = between_variance
            best_threshold = threshold
    return best_threshold


@dataclass(frozen=True, slots=True)
class _Run:
    y: int
    x0: int
    x1: int
    label: int

    @property
    def area(self) -> int:
        return self.x1 - self.x0 + 1


def _find(parent: list[int], label: int) -> int:
    root = label
    while parent[root] != root:
        root = parent[root]
    while parent[label] != label:
        next_label = parent[label]
        parent[label] = root
        label = next_label
    return root


def _union(parent: list[int], first: int, second: int) -> None:
    first_root = _find(parent, first)
    second_root = _find(parent, second)
    if first_root == second_root:
        return
    # Always select the smaller label so grouping is stable across runs.
    if first_root < second_root:
        parent[second_root] = first_root
    else:
        parent[first_root] = second_root


def _connected_dark_components(
    image: _GrayImage,
    threshold: int,
    configuration: AprilTagPixelDetectorConfiguration,
) -> tuple[tuple[_Run, ...], ...]:
    runs: list[_Run] = []
    parent: list[int] = []
    previous: list[_Run] = []
    dark_pixels = 0
    width = image.width
    for y in range(image.height):
        row_offset = y * width
        current: list[_Run] = []
        x = 0
        while x < width:
            while x < width and image.pixels[row_offset + x] > threshold:
                x += 1
            if x >= width:
                break
            x0 = x
            while x + 1 < width and image.pixels[row_offset + x + 1] <= threshold:
                x += 1
            x1 = x
            label = len(parent)
            if label >= configuration.maximum_runs:
                raise PixelDetectorResourceLimitError(
                    f"dark run count exceeds {configuration.maximum_runs}"
                )
            parent.append(label)
            run = _Run(y, x0, x1, label)
            current.append(run)
            runs.append(run)
            dark_pixels += run.area
            x += 1

        previous_index = 0
        for run in current:
            while (
                previous_index < len(previous)
                and previous[previous_index].x1 < run.x0 - 1
            ):
                previous_index += 1
            overlap_index = previous_index
            while (
                overlap_index < len(previous)
                and previous[overlap_index].x0 <= run.x1 + 1
            ):
                _union(parent, run.label, previous[overlap_index].label)
                overlap_index += 1
        previous = current

    if dark_pixels > len(image.pixels) * configuration.maximum_dark_fraction:
        raise AprilTagPixelDetectorError(
            "dark-pixel fraction exceeds the configured candidate policy"
        )
    grouped: dict[int, list[_Run]] = {}
    for run in runs:
        grouped.setdefault(_find(parent, run.label), []).append(run)
    return tuple(tuple(grouped[root]) for root in sorted(grouped))


_Point = tuple[float, float]


def _cross(origin: _Point, first: _Point, second: _Point) -> float:
    return (first[0] - origin[0]) * (second[1] - origin[1]) - (
        first[1] - origin[1]
    ) * (second[0] - origin[0])


def _convex_hull(points: Iterable[_Point]) -> tuple[_Point, ...]:
    unique = sorted(set(points))
    if len(unique) < 4:
        return ()
    lower: list[_Point] = []
    for point in unique:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper: list[_Point] = []
    for point in reversed(unique):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1] + upper[:-1])


def _line_distance(point: _Point, start: _Point, end: _Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    return abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]) / length


def _rdp_open(points: Sequence[_Point], epsilon: float) -> tuple[_Point, ...]:
    if len(points) <= 2:
        return tuple(points)
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        start_index, end_index = stack.pop()
        furthest_index: int | None = None
        furthest_distance = epsilon
        for index in range(start_index + 1, end_index):
            distance = _line_distance(
                points[index], points[start_index], points[end_index]
            )
            if distance > furthest_distance:
                furthest_distance = distance
                furthest_index = index
        if furthest_index is not None:
            keep.add(furthest_index)
            stack.append((start_index, furthest_index))
            stack.append((furthest_index, end_index))
    return tuple(points[index] for index in sorted(keep))


def _polygon_twice_area(points: Sequence[_Point]) -> float:
    return sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(points, tuple(points[1:]) + (points[0],))
    )


def _four_hull_vertices(hull: tuple[_Point, ...], edge_scale: float) -> tuple[_Point, ...]:
    if len(hull) == 4:
        return hull
    left_index = min(range(len(hull)), key=lambda index: (hull[index][0], hull[index][1]))
    right_index = max(range(len(hull)), key=lambda index: (hull[index][0], hull[index][1]))
    if left_index > right_index:
        left_index, right_index = right_index, left_index
    first_chain = hull[left_index : right_index + 1]
    second_chain = hull[right_index:] + hull[: left_index + 1]
    best: tuple[float, tuple[_Point, ...]] | None = None
    for fraction in (0.0025, 0.005, 0.01, 0.02, 0.04, 0.08, 0.12):
        epsilon = max(0.25, edge_scale * fraction)
        first = _rdp_open(first_chain, epsilon)
        second = _rdp_open(second_chain, epsilon)
        simplified = first[:-1] + second[:-1]
        if len(simplified) == 4:
            candidate = (abs(_polygon_twice_area(simplified)), simplified)
            if best is None or candidate > best:
                best = candidate

    # Bounded maximum-area evaluation handles raster stair steps, and also
    # corrects the endpoint bias introduced when the leftmost or rightmost
    # hull coordinate lies along an oblique edge rather than at a true corner.
    # RDP candidates remain in the comparison because downsampling a long hull
    # can otherwise skip a real corner.
    sampled = hull
    if len(sampled) > 32:
        indices = tuple(
            min(len(sampled) - 1, (index * len(sampled)) // 32)
            for index in range(32)
        )
        sampled = tuple(sampled[index] for index in dict.fromkeys(indices))
    for combination in itertools.combinations(sampled, 4):
        area = abs(_polygon_twice_area(combination))
        candidate = (area, combination)
        if best is None or candidate > best:
            best = candidate
    return () if best is None else best[1]


def _image_order_corners(points: tuple[_Point, ...]) -> tuple[_Point, _Point, _Point, _Point]:
    """Assign four geometric vertices to image TL, TR, BR, BL roles."""

    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    scale_x = max(max_x - min_x, 1e-12)
    scale_y = max(max_y - min_y, 1e-12)
    ideals = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    best: tuple[float, tuple[_Point, ...]] | None = None
    for permutation in itertools.permutations(points):
        if _polygon_twice_area(permutation) <= 1e-9:
            continue
        score = sum(
            ((point[0] - min_x) / scale_x - ideal[0]) ** 2
            + ((point[1] - min_y) / scale_y - ideal[1]) ** 2
            for point, ideal in zip(permutation, ideals)
        )
        candidate = (score, permutation)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise AprilTagPixelDetectorError("candidate quad corner ordering is ambiguous")
    result = best[1]
    return result[0], result[1], result[2], result[3]


def _component_quad(
    runs: tuple[_Run, ...],
    image: _GrayImage,
    configuration: AprilTagPixelDetectorConfiguration,
) -> tuple[_Point, _Point, _Point, _Point] | None:
    area = sum(run.area for run in runs)
    if area < configuration.minimum_component_pixels:
        return None
    if len(runs) > configuration.maximum_component_runs:
        raise PixelDetectorResourceLimitError(
            "candidate component exceeds maximum_component_runs"
        )
    x0 = min(run.x0 for run in runs)
    x1 = max(run.x1 for run in runs)
    y0 = min(run.y for run in runs)
    y1 = max(run.y for run in runs)
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    if min(width, height) < configuration.minimum_tag_edge_px:
        return None
    aspect = max(width, height) / min(width, height)
    if aspect > configuration.maximum_aspect_ratio:
        return None
    fill = area / (width * height)
    if not (
        configuration.minimum_component_fill_fraction
        <= fill
        <= configuration.maximum_component_fill_fraction
    ):
        return None
    # A complete AprilTag requires visible quiet space around the black border.
    if x0 <= 0 or y0 <= 0 or x1 >= image.width - 1 or y1 >= image.height - 1:
        return None
    boundary_points: list[_Point] = []
    for run in runs:
        boundary_points.extend(
            (
                (run.x0 - 0.5, run.y - 0.5),
                (run.x1 + 0.5, run.y - 0.5),
                (run.x1 + 0.5, run.y + 0.5),
                (run.x0 - 0.5, run.y + 0.5),
            )
        )
    hull = _convex_hull(boundary_points)
    if len(hull) < 4:
        return None
    if len(hull) > configuration.maximum_hull_vertices:
        raise PixelDetectorResourceLimitError(
            "candidate hull exceeds maximum_hull_vertices"
        )
    quad = _four_hull_vertices(hull, float(min(width, height)))
    if len(quad) != 4:
        return None
    ordered = _image_order_corners(quad)
    edges = tuple(
        math.hypot(
            ordered[(index + 1) % 4][0] - ordered[index][0],
            ordered[(index + 1) % 4][1] - ordered[index][1],
        )
        for index in range(4)
    )
    if min(edges) < configuration.minimum_tag_edge_px:
        return None
    return ordered


def _project_unit_square(
    corners: tuple[_Point, _Point, _Point, _Point],
    u: float,
    v: float,
) -> _Point:
    """Map unit-square coordinates through the four-corner homography."""

    top_left, top_right, bottom_right, bottom_left = corners
    dx1 = top_right[0] - bottom_right[0]
    dx2 = bottom_left[0] - bottom_right[0]
    dx3 = (
        top_left[0]
        - top_right[0]
        + bottom_right[0]
        - bottom_left[0]
    )
    dy1 = top_right[1] - bottom_right[1]
    dy2 = bottom_left[1] - bottom_right[1]
    dy3 = (
        top_left[1]
        - top_right[1]
        + bottom_right[1]
        - bottom_left[1]
    )
    denominator = dx1 * dy2 - dx2 * dy1
    if abs(dx3) <= 1e-12 and abs(dy3) <= 1e-12:
        projective_x = 0.0
        projective_y = 0.0
    else:
        if abs(denominator) <= 1e-12:
            raise AprilTagPixelDetectorError("candidate homography is singular")
        projective_x = (dx3 * dy2 - dx2 * dy3) / denominator
        projective_y = (dx1 * dy3 - dx3 * dy1) / denominator
    a = top_right[0] - top_left[0] + projective_x * top_right[0]
    b = bottom_left[0] - top_left[0] + projective_y * bottom_left[0]
    c = top_left[0]
    d = top_right[1] - top_left[1] + projective_x * top_right[1]
    e = bottom_left[1] - top_left[1] + projective_y * bottom_left[1]
    f = top_left[1]
    scale = projective_x * u + projective_y * v + 1.0
    if abs(scale) <= 1e-12:
        raise AprilTagPixelDetectorError("candidate homography projects to infinity")
    return ((a * u + b * v + c) / scale, (d * u + e * v + f) / scale)


def _bilinear(image: _GrayImage, x: float, y: float) -> float:
    x = min(max(x, 0.0), image.width - 1.0)
    y = min(max(y, 0.0), image.height - 1.0)
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = min(x0 + 1, image.width - 1)
    y1 = min(y0 + 1, image.height - 1)
    x_weight = x - x0
    y_weight = y - y0
    top = image.value(x0, y0) * (1.0 - x_weight) + image.value(x1, y0) * x_weight
    bottom = image.value(x0, y1) * (1.0 - x_weight) + image.value(x1, y1) * x_weight
    return top * (1.0 - y_weight) + bottom * y_weight


def _sample_cells(
    image: _GrayImage,
    corners: tuple[_Point, _Point, _Point, _Point],
    configuration: AprilTagPixelDetectorConfiguration,
) -> tuple[tuple[float, ...], ...]:
    width = configuration.sampling_grid_width
    offsets: tuple[float, ...]
    if width == 1:
        offsets = (0.0,)
    else:
        spread = configuration.sampling_spread_cell
        offsets = tuple(
            -spread + (2.0 * spread * index / (width - 1))
            for index in range(width)
        )
    rows: list[tuple[float, ...]] = []
    for row in range(8):
        values: list[float] = []
        for column in range(8):
            samples = sorted(
                _bilinear(
                    image,
                    *_project_unit_square(
                        corners,
                        (column + 0.5 + x_offset) / 8.0,
                        (row + 0.5 + y_offset) / 8.0,
                    ),
                )
                for y_offset in offsets
                for x_offset in offsets
            )
            values.append(samples[len(samples) // 2])
        rows.append(tuple(values))
    return tuple(rows)


def _two_cluster_threshold(values: Sequence[float]) -> tuple[float, float] | None:
    low = min(values)
    high = max(values)
    if high - low <= 1e-9:
        return None
    for _ in range(12):
        threshold = (low + high) / 2.0
        low_values = [value for value in values if value <= threshold]
        high_values = [value for value in values if value > threshold]
        if not low_values or not high_values:
            return None
        next_low = sum(low_values) / len(low_values)
        next_high = sum(high_values) / len(high_values)
        if abs(next_low - low) + abs(next_high - high) <= 1e-9:
            low, high = next_low, next_high
            break
        low, high = next_low, next_high
    return (low + high) / 2.0, high - low


GridValue = TypeVar("GridValue")


def _rotate_grid_cw(
    grid: tuple[tuple[GridValue, ...], ...]
) -> tuple[tuple[GridValue, ...], ...]:
    return tuple(
        tuple(grid[len(grid) - 1 - column][row] for column in range(len(grid)))
        for row in range(len(grid))
    )


def _rotated_grid(
    grid: tuple[tuple[GridValue, ...], ...], rotations_cw: int
) -> tuple[tuple[GridValue, ...], ...]:
    result = grid
    for _ in range(rotations_cw % 4):
        result = _rotate_grid_cw(result)
    return result


def _payload_hamming(
    observed: tuple[tuple[int, ...], ...],
    expected: tuple[tuple[int, ...], ...],
) -> int:
    return sum(
        observed[row][column] != expected[row][column]
        for row in range(1, 7)
        for column in range(1, 7)
    )


def _border_errors(grid: tuple[tuple[int, ...], ...]) -> int:
    return sum(
        grid[row][column] != 0
        for row in range(8)
        for column in range(8)
        if row in (0, 7) or column in (0, 7)
    )


def _canonical_corners(
    corners: tuple[_Point, _Point, _Point, _Point],
    correction_rotations_cw: int,
) -> tuple[_Point, _Point, _Point, _Point]:
    rotation = correction_rotations_cw % 4
    if rotation == 0:
        return corners
    rotated = corners[-rotation:] + corners[:-rotation]
    return rotated[0], rotated[1], rotated[2], rotated[3]


def _decision_margin(
    canonical_samples: tuple[tuple[float, ...], ...],
    pattern: tuple[tuple[int, ...], ...],
    threshold: float,
) -> float:
    black = [
        canonical_samples[row][column]
        for row in range(8)
        for column in range(8)
        if pattern[row][column] == 0
    ]
    white = [
        canonical_samples[row][column]
        for row in range(8)
        for column in range(8)
        if pattern[row][column] == 1
    ]
    if not black or not white:
        return 0.0
    black_mean = sum(black) / len(black)
    white_mean = sum(white) / len(white)
    return max(0.0, min(threshold - black_mean, white_mean - threshold))


def _decode_candidate(
    image: _GrayImage,
    corners: tuple[_Point, _Point, _Point, _Point],
    configuration: AprilTagPixelDetectorConfiguration,
    codebook: AprilTagPatternCodebook,
) -> AprilTagDetection | None:
    samples = _sample_cells(image, corners, configuration)
    clustered = _two_cluster_threshold(tuple(value for row in samples for value in row))
    if clustered is None:
        return None
    threshold, _contrast = clustered
    observed = tuple(
        tuple(1 if value > threshold else 0 for value in row) for row in samples
    )
    candidates: list[tuple[int, int, int]] = []
    for correction in range(4):
        canonical = _rotated_grid(observed, correction)
        for tag_id in codebook.tag_ids:
            candidates.append(
                (
                    _payload_hamming(canonical, codebook.pattern(tag_id)),
                    tag_id,
                    correction,
                )
            )
    candidates.sort()
    best_hamming, best_tag_id, correction = candidates[0]
    equally_good = tuple(
        candidate for candidate in candidates if candidate[0] == best_hamming
    )
    if len(equally_good) != 1:
        # Without a unique family/id/orientation, returning canonical corners
        # would create false pose evidence.  Ignore the candidate fail closed.
        return None
    if best_hamming > configuration.maximum_reported_hamming:
        return None

    canonical_observed = _rotated_grid(observed, correction)
    canonical_samples = _rotated_grid(samples, correction)
    pattern = codebook.pattern(best_tag_id)
    border_errors = _border_errors(canonical_observed)
    margin = _decision_margin(canonical_samples, pattern, threshold)
    reasons: list[str] = []
    if border_errors > configuration.maximum_border_errors:
        reasons.append("black_border_policy")
    if best_hamming > configuration.maximum_hamming:
        reasons.append("hamming_policy")
    if margin < configuration.minimum_decision_margin:
        reasons.append("decision_margin_policy")
    rejection_reason = "+".join(reasons) if reasons else None
    marked_corners = _canonical_corners(corners, correction)
    return AprilTagDetection(
        tag=TagReference(codebook.family, best_tag_id),
        corners_px=tuple(PixelCorner(x, y) for x, y in marked_corners),  # type: ignore[arg-type]
        decision_margin=margin,
        hamming=best_hamming,
        rejection_reason=rejection_reason,
    )


def _implementation_sha256() -> str:
    try:
        payload = Path(__file__).read_bytes()
    except OSError as exc:
        raise AprilTagPixelDetectorError(
            f"cannot bind pixel-detector implementation bytes: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class AprilTag36h11PixelDetector:
    """Stateless service producing canonical detection records from JPEG pixels."""

    configuration: AprilTagPixelDetectorConfiguration
    codebook: AprilTagPatternCodebook

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, AprilTagPixelDetectorConfiguration):
            raise TypeError(
                "configuration must be an AprilTagPixelDetectorConfiguration"
            )
        if not isinstance(self.codebook, AprilTagPatternCodebook):
            raise TypeError("codebook must be an AprilTagPatternCodebook")
        if self.codebook.family != "tag36h11":
            raise AprilTagPixelDetectorError("detector supports only tag36h11")
        if self.codebook.tag_ids != RELEASED_TAG_IDS:
            raise AprilTagPixelDetectorError(
                f"detector codebook ids must equal {RELEASED_TAG_IDS}"
            )

    @property
    def detector_identity(self) -> DetectorIdentity:
        return DetectorIdentity(
            detector_id=PIXEL_DETECTOR_ID,
            version=PIXEL_DETECTOR_VERSION,
            configuration_sha256=self.configuration.configuration_sha256(
                self.codebook
            ),
            implementation_sha256=_implementation_sha256(),
        )

    def detect(self, frame: FramePacket) -> AprilTagDetectionBatch:
        """Decode ``frame`` without any scene or expected-observation input."""

        if not isinstance(frame, FramePacket):
            raise TypeError("frame must be a FramePacket")
        image = _decode_jpeg(frame, self.configuration)
        otsu = _otsu_threshold(image.pixels)
        detections: list[AprilTagDetection] = []
        if otsu is not None:
            threshold = min(
                255,
                max(0, otsu + self.configuration.otsu_threshold_offset),
            )
            components = _connected_dark_components(
                image, threshold, self.configuration
            )
            quads: list[tuple[_Point, _Point, _Point, _Point]] = []
            for component in components:
                quad = _component_quad(component, image, self.configuration)
                if quad is not None:
                    quads.append(quad)
                    if len(quads) > self.configuration.maximum_candidates:
                        raise PixelDetectorResourceLimitError(
                            f"candidate count exceeds {self.configuration.maximum_candidates}"
                        )
            quads.sort(
                key=lambda corners: tuple(
                    coordinate for point in corners for coordinate in point
                )
            )
            for quad in quads:
                detection = _decode_candidate(
                    image, quad, self.configuration, self.codebook
                )
                if detection is not None:
                    detections.append(detection)
        try:
            return AprilTagDetectionBatch(
                frame=FrameCaptureBinding.from_frame_packet(
                    frame, host_clock=self.configuration.host_clock
                ),
                detector=self.detector_identity,
                detections=tuple(detections),
            )
        except VisionRecordError as exc:
            raise AprilTagPixelDetectorError(
                f"detector output failed record validation: {exc}"
            ) from exc


def detect_apriltag36h11_pixels(
    frame: FramePacket,
    *,
    configuration: AprilTagPixelDetectorConfiguration,
    codebook: AprilTagPatternCodebook,
) -> AprilTagDetectionBatch:
    """Functional entry point with the same restricted input boundary."""

    return AprilTag36h11PixelDetector(configuration, codebook).detect(frame)


__all__ = [
    "AprilTag36h11PixelDetector",
    "AprilTagPixelDetectorConfiguration",
    "AprilTagPixelDetectorError",
    "PIXEL_DETECTOR_CONTRACT",
    "PIXEL_DETECTOR_ID",
    "PIXEL_DETECTOR_VERSION",
    "PixelDecodeError",
    "PixelDecoderUnavailableError",
    "PixelDetectorResourceLimitError",
    "RELEASED_TAG_IDS",
    "detect_apriltag36h11_pixels",
]
