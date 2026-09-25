"""Bounded, manifest-last native camera datasets without camera or M1 authority.

The caller supplies bytes; this module never opens a capture device. An exact
capture plan is published before its samples, with train/holdout assignment
already fixed. Payloads use content-addressed chunks and streaming SHA-256.
Only the final manifest commits a dataset. Interrupted trees are retained for
diagnosis, never repaired, resumed, or accepted as committed datasets.

These are immutable-by-API diagnostic packages, not authenticated observations,
qualified M1 storage, crash-proof publication, or received-hardware acceptance.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import ExitStack
from dataclasses import asdict, dataclass, fields
import hashlib
import io
from itertools import islice
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
from typing import Any
import uuid

from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
    read_bounded_regular_file,
    safe_root,
)
from rocell.application.wizard_diagnostic_export import _directory_guard


SCHEMA = "rocell.camera_capture_dataset.v1"
PLAN_SCHEMA = "rocell.camera_capture_plan.v1"
MAX_FRAME_BYTES = 64 * 1024 * 1024
MAX_DATASET_BYTES = 2 * 1024 * 1024 * 1024
MAX_PREVIEW_BYTES = 4 * 1024 * 1024
MAX_CHUNK_BYTES = 1024 * 1024
MAX_CHUNKS = 4096
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_FRAMES = 32
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_DATASET = re.compile(r"capture-[0-9a-f]{32}\Z")
_PARTITIONS = {"DIAGNOSTIC", "CALIBRATION_TRAIN", "CALIBRATION_HOLDOUT"}
_DECLARATIONS = {
    "physical_authority": False,
    "m1_qualified": False,
    "received_hardware_accepted": False,
    "freshness_qualification": "NOT_EVALUATED",
    "preview_association": "DECLARED_TRANSFORM_NOT_PIXEL_RECOMPUTED",
}


class CameraDatasetError(ValueError):
    """Malformed, incomplete, inconsistent, or unsafe diagnostic dataset."""


class CameraDatasetCancelled(CameraDatasetError):
    """Publication stopped before commitment; partial files are retained."""


def _integer(value: Any, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CameraDatasetError(f"{name} must be an integer in [{minimum}, {maximum}]")


def _text(value: Any, name: str, maximum: int = 1024) -> None:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or any(ord(c) < 32 for c in value)
    ):
        raise CameraDatasetError(
            f"{name} must be bounded nonempty text without controls"
        )


def _identifier(value: Any, name: str) -> None:
    if type(value) is not str or not _ID.fullmatch(value):
        raise CameraDatasetError(f"{name} is not a bounded identifier")


def _digest(value: Any, name: str) -> None:
    if type(value) is not str or not _HASH.fullmatch(value):
        raise CameraDatasetError(f"{name} is not a lowercase SHA-256 digest")


@dataclass(frozen=True)
class VideoMode:
    width: int
    height: int
    fps_numerator: int
    fps_denominator: int
    subtype: str = "YUY2"

    def __post_init__(self) -> None:
        _integer(self.width, "mode width", 2, 8192)
        _integer(self.height, "mode height", 1, 8192)
        _integer(self.fps_numerator, "fps numerator", 1, 1_000_000)
        _integer(self.fps_denominator, "fps denominator", 1, 1_000_000)
        if self.width % 2 or self.subtype != "YUY2":
            raise CameraDatasetError(
                "This initial native dataset format requires even-width YUY2"
            )
        if math.gcd(self.fps_numerator, self.fps_denominator) != 1:
            raise CameraDatasetError("Frame-rate rational must be reduced")


@dataclass(frozen=True)
class SampleLayout:
    stride_bytes: int
    row_order: str = "TOP_DOWN"

    def __post_init__(self) -> None:
        _integer(self.stride_bytes, "stride", 4, MAX_FRAME_BYTES)
        if self.row_order not in {"TOP_DOWN", "BOTTOM_UP"}:
            raise CameraDatasetError("Sample row order must be explicit")

    def sample_bytes(self, mode: VideoMode) -> int:
        if self.stride_bytes < mode.width * 2 or self.stride_bytes % 2:
            raise CameraDatasetError("YUY2 stride must cover each complete packed row")
        size = self.stride_bytes * mode.height
        if size > MAX_FRAME_BYTES:
            raise CameraDatasetError("Padded native frame exceeds its hard byte limit")
        return size


@dataclass(frozen=True)
class DeviceIdentity:
    backend: str
    persistent_id: str
    vid: int | None = None
    pid: int | None = None
    serial: str | None = None

    def __post_init__(self) -> None:
        if self.backend not in {"SYNTHETIC", "WINDOWS_MEDIA_FOUNDATION"}:
            raise CameraDatasetError("Device backend must be explicitly registered")
        _text(self.persistent_id, "persistent device identity")
        for name in ("vid", "pid"):
            value = getattr(self, name)
            if value is not None:
                _integer(value, name, 0, 65535)
        if self.serial is not None:
            _text(self.serial, "observed serial", 256)


@dataclass(frozen=True)
class CaptureBinding:
    provenance: str
    source_sha256: str
    campaign_id: str
    settings_epoch: str
    device: DeviceIdentity
    requested_mode: VideoMode
    observed_mode: VideoMode

    def __post_init__(self) -> None:
        if self.provenance not in {"SYNTHETIC", "PHYSICAL_UNVERIFIED"}:
            raise CameraDatasetError("Dataset cannot claim physical qualification")
        _digest(self.source_sha256, "source binding")
        _identifier(self.campaign_id, "campaign")
        _identifier(self.settings_epoch, "settings epoch")
        if (
            type(self.device) is not DeviceIdentity
            or type(self.requested_mode) is not VideoMode
            or type(self.observed_mode) is not VideoMode
        ):
            raise CameraDatasetError(
                "Binding requires typed device and requested/observed modes"
            )
        if (self.provenance == "SYNTHETIC") != (self.device.backend == "SYNTHETIC"):
            raise CameraDatasetError("Device and dataset provenance disagree")


@dataclass(frozen=True)
class PreviewTransform:
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    output_width: int
    output_height: int
    rotation_degrees: int = 0
    encoding: str = "PNG"
    maximum_bytes: int = MAX_PREVIEW_BYTES

    def __post_init__(self) -> None:
        for name in ("crop_x", "crop_y"):
            _integer(getattr(self, name), name, 0, 8192)
        for name in ("crop_width", "crop_height"):
            _integer(getattr(self, name), name, 1, 8192)
        for name in ("output_width", "output_height"):
            _integer(getattr(self, name), name, 1, 2048)
        if type(self.rotation_degrees) is not int or self.rotation_degrees not in {
            0,
            90,
            180,
            270,
        }:
            raise CameraDatasetError("Preview rotation must be an explicit right angle")
        if self.encoding not in {"PNG", "JPEG"}:
            raise CameraDatasetError("Preview encoding is not registered")
        _integer(self.maximum_bytes, "preview bytes", 1, MAX_PREVIEW_BYTES)

    def validate_for(self, mode: VideoMode) -> None:
        if (
            self.crop_x + self.crop_width > mode.width
            or self.crop_y + self.crop_height > mode.height
        ):
            raise CameraDatasetError("Preview crop exceeds the actual native frame")
        width, height = self.crop_width, self.crop_height
        if self.rotation_degrees in {90, 270}:
            width, height = height, width
        if self.output_width > width or self.output_height > height:
            raise CameraDatasetError("Preview may not upscale native source pixels")
        if self.output_width * height != self.output_height * width:
            raise CameraDatasetError(
                "Preview resize must preserve the rotated crop aspect ratio"
            )


@dataclass(frozen=True)
class FramePlan:
    frame_id: str
    partition: str = "DIAGNOSTIC"
    preview: PreviewTransform | None = None

    def __post_init__(self) -> None:
        _identifier(self.frame_id, "frame")
        if self.partition not in _PARTITIONS:
            raise CameraDatasetError("Frame partition is not registered")
        if self.preview is not None and type(self.preview) is not PreviewTransform:
            raise CameraDatasetError("Preview requires a typed transform")


@dataclass(frozen=True)
class CapturePlan:
    binding: CaptureBinding
    layout: SampleLayout
    frames: tuple[FramePlan, ...]

    def __post_init__(self) -> None:
        if (
            type(self.binding) is not CaptureBinding
            or type(self.layout) is not SampleLayout
        ):
            raise CameraDatasetError("Capture plan requires typed binding/layout")
        if (
            type(self.frames) is not tuple
            or not 1 <= len(self.frames) <= MAX_FRAMES
            or any(type(frame) is not FramePlan for frame in self.frames)
        ):
            raise CameraDatasetError("Capture plan requires 1–32 immutable frame plans")
        if len({frame.frame_id for frame in self.frames}) != len(self.frames):
            raise CameraDatasetError(
                "Frame IDs and partition assignments must be unique"
            )
        partitions = {frame.partition for frame in self.frames} - {"DIAGNOSTIC"}
        if partitions and partitions != {"CALIBRATION_TRAIN", "CALIBRATION_HOLDOUT"}:
            raise CameraDatasetError(
                "Calibration datasets precommit both train and holdout frames"
            )
        self.layout.sample_bytes(self.binding.observed_mode)
        for frame in self.frames:
            if frame.preview:
                frame.preview.validate_for(self.binding.observed_mode)


@dataclass(frozen=True)
class SampleTiming:
    host_sequence: int
    host_arrival_start_ns: int
    host_arrival_end_ns: int
    sample_time_ns: int | None = None
    sample_time_provenance: str = "NOT_AVAILABLE"

    def __post_init__(self) -> None:
        for name in ("host_sequence", "host_arrival_start_ns", "host_arrival_end_ns"):
            _integer(getattr(self, name), name, 0, 2**63 - 1)
        if self.host_arrival_end_ns < self.host_arrival_start_ns:
            raise CameraDatasetError("Host arrival bracket is reversed")
        if self.sample_time_provenance not in {
            "NOT_AVAILABLE",
            "MEDIA_SAMPLE_TIME",
            "SYNTHETIC_SAMPLE_TIME",
        }:
            raise CameraDatasetError(
                "Media timestamps are not sensor exposure timestamps"
            )
        if self.sample_time_ns is None:
            if self.sample_time_provenance != "NOT_AVAILABLE":
                raise CameraDatasetError(
                    "Missing sample time cannot have timing provenance"
                )
        else:
            _integer(self.sample_time_ns, "sample time", 0, 2**63 - 1)
            if self.sample_time_provenance == "NOT_AVAILABLE":
                raise CameraDatasetError("A sample time requires explicit provenance")


@dataclass(frozen=True)
class PreviewInput:
    native_sha256: str
    chunks: Iterable[bytes]


@dataclass(frozen=True)
class NativeFrameInput:
    frame_id: str
    timing: SampleTiming
    chunks: Iterable[bytes]
    preview: PreviewInput | None = None


@dataclass(frozen=True)
class DatasetQuotas:
    chunk_bytes: int = MAX_CHUNK_BYTES
    frames: int = MAX_FRAMES
    frame_bytes: int = MAX_FRAME_BYTES
    total_bytes: int = MAX_DATASET_BYTES
    disk_reserve_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("chunk_bytes", 8, MAX_CHUNK_BYTES),
            ("frames", 1, MAX_FRAMES),
            ("frame_bytes", 1, MAX_FRAME_BYTES),
            ("total_bytes", 1, MAX_DATASET_BYTES),
            ("disk_reserve_bytes", 0, MAX_DATASET_BYTES),
        ):
            _integer(getattr(self, name), name, minimum, maximum)


@dataclass(frozen=True)
class DatasetReceipt:
    path: Path
    manifest_sha256: str
    plan_sha256: str
    frames: int
    logical_bytes: int
    physical_authority: bool = False


@dataclass(frozen=True)
class DatasetVerification:
    path: Path
    manifest_sha256: str
    plan: CapturePlan
    frames: int
    logical_bytes: int
    content_verified: bool
    requested_mode_matches: bool
    physical_authority: bool = False
    m1_qualified: bool = False


def _json(value: Any) -> bytes:
    payload = (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    if len(payload) > MAX_JSON_BYTES:
        raise CameraDatasetError("Dataset metadata exceeds its byte budget")
    return payload


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CameraDatasetError("Duplicate dataset JSON field")
        result[key] = value
    return result


def _document(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        payload = read_bounded_regular_file(path, maximum_bytes=MAX_JSON_BYTES)
        value = json.loads(payload.decode("ascii"), object_pairs_hook=_strict_object)
        if type(value) is not dict or _json(value) != payload:
            raise CameraDatasetError("Dataset metadata is not canonical JSON")
        return value, payload
    except (
        OSError,
        UnicodeError,
        ValueError,
        RecursionError,
        PhysicalOnboardingDurabilityError,
    ) as error:
        raise CameraDatasetError(
            f"Cannot read valid dataset metadata: {path.name}"
        ) from error


def _exact(value: Any, names: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != names:
        raise CameraDatasetError("Unexpected or missing dataset metadata fields")
    return value


def _declarations(value: Any) -> None:
    _exact(value, set(_DECLARATIONS))
    if any(
        type(value[key]) is not type(expected) or value[key] != expected
        for key, expected in _DECLARATIONS.items()
    ):
        raise CameraDatasetError("Dataset declarations must be exactly diagnostic-only")


def _typed(cls: Any, value: Any) -> Any:
    return cls(**_exact(value, {field.name for field in fields(cls)}))


def _decode_plan(document: dict[str, Any]) -> CapturePlan:
    _exact(document, {"schema", "plan", "declarations"})
    _declarations(document["declarations"])
    if document["schema"] != PLAN_SCHEMA:
        raise CameraDatasetError("Plan schema or zero-authority declarations disagree")
    raw = _exact(document["plan"], {"binding", "layout", "frames"})
    binding = _exact(raw["binding"], {field.name for field in fields(CaptureBinding)})
    binding = {
        **binding,
        "device": _typed(DeviceIdentity, binding["device"]),
        "requested_mode": _typed(VideoMode, binding["requested_mode"]),
        "observed_mode": _typed(VideoMode, binding["observed_mode"]),
    }
    if type(raw["frames"]) is not list or not 1 <= len(raw["frames"]) <= MAX_FRAMES:
        raise CameraDatasetError("Invalid planned frame count")
    plans = []
    for frame in raw["frames"]:
        item = _exact(frame, {"frame_id", "partition", "preview"})
        plans.append(
            FramePlan(
                item["frame_id"],
                item["partition"],
                (
                    _typed(PreviewTransform, item["preview"])
                    if item["preview"] is not None
                    else None
                ),
            )
        )
    return CapturePlan(
        CaptureBinding(**binding), _typed(SampleLayout, raw["layout"]), tuple(plans)
    )


def _root(path: Path) -> Path:
    if (
        not path.is_absolute()
        or path == Path(path.anchor)
        or str(path).startswith(("\\\\", "//"))
        or ".." in path.parts
    ):
        raise CameraDatasetError("Assign an absolute local non-root directory")
    try:
        if not path.exists():
            raise CameraDatasetError("Dataset directory must already exist")
        selected = safe_root(path, label="camera dataset directory")
        if not selected.is_dir():
            raise CameraDatasetError("Dataset directory must already exist")
        return selected
    except (OSError, PhysicalOnboardingDurabilityError) as error:
        raise CameraDatasetError("Dataset path is unsafe or unavailable") from error


def _new_file(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _commit_manifest(
    dataset: Path, payload: bytes, cancelled: Callable[[], bool]
) -> None:
    # The pending sentinel makes even complete-looking final bytes invalid on
    # flush failure or cancellation. Exclusive creation prevents overwrite.
    # Use a small second JSON write: Windows' directory rename guard also
    # denies hardlink publication. This is not a power-loss durability claim.
    pending = dataset / "manifest.pending"
    _new_file(pending, payload)
    _cancel(cancelled)
    _new_file(dataset / "manifest.json", payload)
    _cancel(cancelled)
    pending.unlink()


def _cancel(check: Callable[[], bool]) -> None:
    result = check()
    if type(result) is not bool:
        raise CameraDatasetError("Cancellation callback must return a Boolean")
    if result:
        raise CameraDatasetCancelled(
            "Capture publication canceled; any partial tree has no valid commit"
        )


def _preview_header(payload: bytes, specification: PreviewTransform) -> None:
    from PIL import Image

    try:
        with Image.open(io.BytesIO(payload)) as image:
            if image.format != specification.encoding or image.size != (
                specification.output_width,
                specification.output_height,
            ):
                raise CameraDatasetError(
                    "Derived preview format/dimensions disagree with its transform"
                )
            image.verify()
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
    except (OSError, ValueError) as error:
        raise CameraDatasetError(
            "Derived preview is not the declared encoded image"
        ) from error


class CameraCaptureDatasetStore:
    """No I/O at construction/status; publish alone creates a unique child."""

    def __init__(self, root: Path, *, quotas: DatasetQuotas | None = None) -> None:
        self.root = Path(root)
        if not self.root.is_absolute() or self.root == Path(self.root.anchor):
            raise CameraDatasetError("Assign an absolute non-root dataset directory")
        if quotas is not None and type(quotas) is not DatasetQuotas:
            raise CameraDatasetError("Publication quotas must be explicitly typed")
        self.quotas = (
            DatasetQuotas(**asdict(quotas)) if quotas is not None else DatasetQuotas()
        )

    def status(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "schema": SCHEMA,
            "quotas": asdict(self.quotas),
            "hardware_io_available": False,
            **_DECLARATIONS,
        }

    def publish(
        self,
        plan: CapturePlan,
        frames: Iterable[NativeFrameInput],
        *,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> DatasetReceipt:
        if type(plan) is not CapturePlan:
            raise CameraDatasetError("Publication requires a typed capture plan")
        # Reconstruct before use to catch malicious mutation of frozen objects.
        plan_data = asdict(plan)
        plan_data["frames"] = list(plan_data["frames"])
        plan_document = {
            "schema": PLAN_SCHEMA,
            "plan": plan_data,
            "declarations": _DECLARATIONS,
        }
        plan = _decode_plan(plan_document)
        size = plan.layout.sample_bytes(plan.binding.observed_mode)
        maximum = sum(
            size + (frame.preview.maximum_bytes if frame.preview else 0)
            for frame in plan.frames
        )
        references = sum(
            math.ceil(size / self.quotas.chunk_bytes)
            + (
                math.ceil(frame.preview.maximum_bytes / self.quotas.chunk_bytes)
                if frame.preview
                else 0
            )
            for frame in plan.frames
        )
        if (
            len(plan.frames) > self.quotas.frames
            or size > self.quotas.frame_bytes
            or maximum > self.quotas.total_bytes
            or references > MAX_CHUNKS
        ):
            raise CameraDatasetError(
                "Capture plan exceeds its frame, byte, or chunk quota"
            )
        root = _root(self.root)
        _cancel(cancelled)
        if (
            shutil.disk_usage(root).free
            < maximum + 2 * MAX_JSON_BYTES + self.quotas.disk_reserve_bytes
        ):
            raise CameraDatasetError(
                "Insufficient preflight disk budget for the planned capture"
            )
        plan_payload = _json(plan_document)
        plan_sha = hashlib.sha256(plan_payload).hexdigest()
        dataset = root / ("capture-" + uuid.uuid4().hex)
        with _directory_guard(root):
            dataset.mkdir(exist_ok=False)
            with _directory_guard(dataset), ExitStack() as guards:
                chunks_directory = dataset / "chunks"
                chunks_directory.mkdir(exist_ok=False)
                guards.enter_context(_directory_guard(chunks_directory))
                _new_file(dataset / "capture-plan.json", plan_payload)
                chunks: dict[str, int] = {}
                records: list[dict[str, Any]] = []
                logical = 0

                def persist(
                    source: Iterable[bytes], limit: int, *, exact: bool
                ) -> dict[str, Any]:
                    nonlocal logical
                    pending = bytearray()
                    digest = hashlib.sha256()
                    refs: list[str] = []
                    total = 0

                    def chunk(payload: bytes) -> None:
                        # One producer block can expand into thousands of small
                        # chunks. Check every chunk, including deduplicated ones,
                        # so cancellation cannot wait for the whole input block.
                        _cancel(cancelled)
                        digest_text = hashlib.sha256(payload).hexdigest()
                        refs.append(digest_text)
                        if len(refs) > MAX_CHUNKS:
                            raise CameraDatasetError("Sample exceeds reference budget")
                        if digest_text not in chunks:
                            if len(chunks) >= MAX_CHUNKS:
                                raise CameraDatasetError(
                                    "Dataset exceeds content-addressed chunk budget"
                                )
                            _new_file(chunks_directory / f"{digest_text}.bin", payload)
                            chunks[digest_text] = len(payload)

                    for block in source:
                        _cancel(cancelled)
                        if (
                            type(block) is not bytes
                            or not 1 <= len(block) <= MAX_CHUNK_BYTES
                        ):
                            raise CameraDatasetError(
                                "Frame producer must yield nonempty bytes blocks no larger than 1 MiB"
                            )
                        total += len(block)
                        logical += len(block)
                        if total > limit or logical > self.quotas.total_bytes:
                            raise CameraDatasetError(
                                "Stream exceeded its declared sample/dataset budget"
                            )
                        digest.update(block)
                        offset = 0
                        while offset < len(block):
                            count = min(
                                len(block) - offset,
                                self.quotas.chunk_bytes - len(pending),
                            )
                            pending.extend(block[offset : offset + count])
                            offset += count
                            if len(pending) == self.quotas.chunk_bytes:
                                chunk(bytes(pending))
                                pending.clear()
                    _cancel(cancelled)
                    if total == 0 or (exact and total != limit):
                        raise CameraDatasetError(
                            "Stream ended before its exact declared sample length"
                        )
                    if pending:
                        chunk(bytes(pending))
                    return {
                        "bytes": total,
                        "sha256": digest.hexdigest(),
                        "chunks": refs,
                    }

                previous_sequence = previous_arrival = -1
                for index, frame in enumerate(frames):
                    _cancel(cancelled)
                    if index >= len(plan.frames):
                        raise CameraDatasetError(
                            "Frame iterator exceeded its precommitted count"
                        )
                    expected = plan.frames[index]
                    if (
                        type(frame) is not NativeFrameInput
                        or frame.frame_id != expected.frame_id
                        or type(frame.timing) is not SampleTiming
                    ):
                        raise CameraDatasetError(
                            "Frame does not match its precommitted ID/order/timing"
                        )
                    timing = _typed(SampleTiming, asdict(frame.timing))
                    if (
                        timing.host_sequence <= previous_sequence
                        or timing.host_arrival_start_ns < previous_arrival
                    ):
                        raise CameraDatasetError(
                            "Host sequence/arrival order regressed"
                        )
                    if (
                        plan.binding.provenance == "SYNTHETIC"
                        and timing.sample_time_provenance == "MEDIA_SAMPLE_TIME"
                    ) or (
                        plan.binding.provenance == "PHYSICAL_UNVERIFIED"
                        and timing.sample_time_provenance == "SYNTHETIC_SAMPLE_TIME"
                    ):
                        raise CameraDatasetError(
                            "Sample timing provenance disagrees with capture provenance"
                        )
                    previous_sequence, previous_arrival = (
                        timing.host_sequence,
                        timing.host_arrival_start_ns,
                    )
                    native = persist(frame.chunks, size, exact=True)
                    preview = None
                    if (expected.preview is None) != (frame.preview is None):
                        raise CameraDatasetError(
                            "Preview presence differs from its precommitted plan"
                        )
                    if expected.preview is not None and frame.preview is not None:
                        if (
                            type(frame.preview) is not PreviewInput
                            or frame.preview.native_sha256 != native["sha256"]
                        ):
                            raise CameraDatasetError(
                                "Derived preview is linked to different native bytes"
                            )
                        preview = persist(
                            frame.preview.chunks,
                            expected.preview.maximum_bytes,
                            exact=False,
                        )
                        preview["native_sha256"] = native["sha256"]
                        encoded = b"".join(
                            read_bounded_regular_file(
                                chunks_directory / f"{key}.bin",
                                maximum_bytes=self.quotas.chunk_bytes,
                            )
                            for key in preview["chunks"]
                        )
                        _preview_header(encoded, expected.preview)
                    records.append(
                        {
                            "frame_id": expected.frame_id,
                            "partition": expected.partition,
                            "timing": asdict(timing),
                            "native": native,
                            "preview": preview,
                        }
                    )
                if len(records) != len(plan.frames):
                    raise CameraDatasetError(
                        "Frame iterator ended before the precommitted count"
                    )
                _cancel(cancelled)
                manifest = {
                    "schema": SCHEMA,
                    "status": "COMMITTED_DIAGNOSTIC_DATASET",
                    "dataset_id": dataset.name,
                    "plan_sha256": plan_sha,
                    "chunk_bytes": self.quotas.chunk_bytes,
                    "frames": records,
                    "logical_bytes": logical,
                    "chunks": [
                        {"sha256": key, "bytes": size}
                        for key, size in sorted(chunks.items())
                    ],
                    "declarations": _DECLARATIONS,
                }
                payload = _json(manifest)
                _cancel(cancelled)
                _commit_manifest(dataset, payload, cancelled)
                return DatasetReceipt(
                    dataset,
                    hashlib.sha256(payload).hexdigest(),
                    plan_sha,
                    len(records),
                    logical,
                )


def _entries(path: Path, limit: int) -> list[Path]:
    result = list(islice(path.iterdir(), limit + 1))
    if len(result) > limit:
        raise CameraDatasetError("Dataset directory exceeds its bounded file inventory")
    return result


def _inspect(
    dataset: Path, *, content: bool
) -> tuple[DatasetVerification, dict[str, Any]]:
    selected = _root(Path(dataset))
    if not _DATASET.fullmatch(selected.name):
        raise CameraDatasetError("Dataset directory has an unexpected identity")
    try:
        with _directory_guard(selected), ExitStack() as guards:
            if {item.name for item in _entries(selected, 3)} != {
                "manifest.json",
                "capture-plan.json",
                "chunks",
            }:
                raise CameraDatasetError(
                    "Dataset is incomplete or contains unexpected files"
                )
            chunk_root = _root(selected / "chunks")
            guards.enter_context(_directory_guard(chunk_root))
            manifest, payload = _document(selected / "manifest.json")
            plan_doc, plan_payload = _document(selected / "capture-plan.json")
            plan = _decode_plan(plan_doc)
            _exact(
                manifest,
                {
                    "schema",
                    "status",
                    "dataset_id",
                    "plan_sha256",
                    "chunk_bytes",
                    "frames",
                    "logical_bytes",
                    "chunks",
                    "declarations",
                },
            )
            _declarations(manifest["declarations"])
            if (
                manifest["schema"] != SCHEMA
                or manifest["status"] != "COMMITTED_DIAGNOSTIC_DATASET"
                or manifest["dataset_id"] != selected.name
            ):
                raise CameraDatasetError(
                    "Manifest cannot claim a different commit/status/authority"
                )
            if manifest["plan_sha256"] != hashlib.sha256(plan_payload).hexdigest():
                raise CameraDatasetError(
                    "Capture plan digest differs from the committed manifest"
                )
            chunk_size = manifest["chunk_bytes"]
            _integer(chunk_size, "chunk byte limit", 8, MAX_CHUNK_BYTES)
            _integer(
                manifest["logical_bytes"], "logical dataset bytes", 1, MAX_DATASET_BYTES
            )
            entries = manifest["chunks"]
            if type(entries) is not list or not 1 <= len(entries) <= MAX_CHUNKS:
                raise CameraDatasetError(
                    "Manifest chunk registry is unbounded or empty"
                )
            chunks: dict[str, int] = {}
            for item in entries:
                _exact(item, {"sha256", "bytes"})
                _digest(item["sha256"], "chunk")
                _integer(item["bytes"], "chunk size", 1, chunk_size)
                if item["sha256"] in chunks:
                    raise CameraDatasetError("Duplicate content-addressed chunk path")
                chunks[item["sha256"]] = item["bytes"]
            if list(chunks) != sorted(chunks):
                raise CameraDatasetError("Chunk registry must be sorted")
            actual = _entries(chunk_root, MAX_CHUNKS)
            if len(actual) != len(chunks) or {item.name for item in actual} != {
                f"{key}.bin" for key in chunks
            }:
                raise CameraDatasetError(
                    "Unexpected, missing, or duplicate chunk files"
                )
            for path in actual:
                metadata = path.stat(follow_symlinks=False)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
                    or metadata.st_nlink != 1
                    or metadata.st_size != chunks[path.stem]
                ):
                    raise CameraDatasetError(
                        "Chunk file is not the declared single-link regular file"
                    )
            referenced: set[str] = set()
            references = 0
            reserved_bytes = 0

            def check_blob(
                raw: Any, limit: int, *, exact: bool, preview: bool = False
            ) -> bytes | None:
                nonlocal references, reserved_bytes
                _exact(
                    raw,
                    {"bytes", "sha256", "chunks"}
                    | ({"native_sha256"} if preview else set()),
                )
                _integer(raw["bytes"], "sample bytes", 1, limit)
                _digest(raw["sha256"], "sample")
                if exact and raw["bytes"] != limit:
                    raise CameraDatasetError(
                        "Native sample length differs from stride times height"
                    )
                # A bounded manifest total is an untrusted declaration. Reserve
                # every native/preview blob before its first content read, so a
                # false total cannot cause I/O beyond the dataset byte ceiling.
                if reserved_bytes + raw["bytes"] > MAX_DATASET_BYTES:
                    raise CameraDatasetError("Dataset cumulative byte budget exceeded")
                reserved_bytes += raw["bytes"]
                refs = raw["chunks"]
                if type(refs) is not list or len(refs) != math.ceil(
                    raw["bytes"] / chunk_size
                ):
                    raise CameraDatasetError(
                        "Sample chunk sequence has missing or extra entries"
                    )
                references += len(refs)
                if references > MAX_CHUNKS:
                    raise CameraDatasetError("Dataset reference budget exceeded")
                digest = hashlib.sha256()
                image = bytearray() if preview and content else None
                for index, key in enumerate(refs):
                    _digest(key, "sample chunk reference")
                    required = min(chunk_size, raw["bytes"] - index * chunk_size)
                    if key not in chunks or chunks[key] != required:
                        raise CameraDatasetError(
                            "Sample chunk length/order does not match its declared layout"
                        )
                    referenced.add(key)
                    if content:
                        data = read_bounded_regular_file(
                            chunk_root / f"{key}.bin", maximum_bytes=chunk_size
                        )
                        if (
                            len(data) != required
                            or hashlib.sha256(data).hexdigest() != key
                        ):
                            raise CameraDatasetError(
                                "Chunk content digest does not match its address"
                            )
                        digest.update(data)
                        if image is not None:
                            image.extend(data)
                if content and digest.hexdigest() != raw["sha256"]:
                    raise CameraDatasetError("Reconstructed sample digest is wrong")
                return bytes(image) if image is not None else None

            records = manifest["frames"]
            if type(records) is not list or len(records) != len(plan.frames):
                raise CameraDatasetError(
                    "Manifest frame count differs from the precommitted plan"
                )
            logical = 0
            previous_sequence = previous_arrival = -1
            for expected, record in zip(plan.frames, records):
                _exact(record, {"frame_id", "partition", "timing", "native", "preview"})
                if (
                    record["frame_id"] != expected.frame_id
                    or record["partition"] != expected.partition
                ):
                    raise CameraDatasetError(
                        "Frame identity/order/partition changed after planning"
                    )
                timing = _typed(SampleTiming, record["timing"])
                if (
                    timing.host_sequence <= previous_sequence
                    or timing.host_arrival_start_ns < previous_arrival
                ):
                    raise CameraDatasetError("Host sequence/arrival order regressed")
                if (
                    plan.binding.provenance == "SYNTHETIC"
                    and timing.sample_time_provenance == "MEDIA_SAMPLE_TIME"
                ) or (
                    plan.binding.provenance == "PHYSICAL_UNVERIFIED"
                    and timing.sample_time_provenance == "SYNTHETIC_SAMPLE_TIME"
                ):
                    raise CameraDatasetError(
                        "Sample timing provenance disagrees with capture provenance"
                    )
                previous_sequence, previous_arrival = (
                    timing.host_sequence,
                    timing.host_arrival_start_ns,
                )
                native = record["native"]
                check_blob(
                    native,
                    plan.layout.sample_bytes(plan.binding.observed_mode),
                    exact=True,
                )
                logical += native["bytes"]
                preview = record["preview"]
                if (expected.preview is None) != (preview is None):
                    raise CameraDatasetError(
                        "Preview differs from its precommitted plan"
                    )
                if expected.preview is not None:
                    data = check_blob(
                        preview,
                        expected.preview.maximum_bytes,
                        exact=False,
                        preview=True,
                    )
                    if preview["native_sha256"] != native["sha256"]:
                        raise CameraDatasetError(
                            "Preview is linked to different native bytes"
                        )
                    logical += preview["bytes"]
                    if data is not None:
                        _preview_header(data, expected.preview)
            if logical != manifest["logical_bytes"] or referenced != set(chunks):
                raise CameraDatasetError(
                    "Dataset has unreferenced chunks or inconsistent totals"
                )
            return (
                DatasetVerification(
                    selected,
                    hashlib.sha256(payload).hexdigest(),
                    plan,
                    len(records),
                    logical,
                    content,
                    plan.binding.requested_mode == plan.binding.observed_mode,
                ),
                manifest,
            )
    except CameraDatasetError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        PhysicalOnboardingDurabilityError,
    ) as error:
        raise CameraDatasetError(
            "Dataset failed structural/content verification"
        ) from error


def verify_capture_dataset(
    dataset: Path,
    *,
    tier: str = "content",
    expected_manifest_sha256: str | None = None,
    expected_binding: CaptureBinding | None = None,
) -> DatasetVerification:
    """Metadata tier does NOT verify bytes and cannot qualify a capture."""
    if tier not in {"metadata", "content"}:
        raise CameraDatasetError("Select metadata or content verification explicitly")
    verified = _inspect(dataset, content=tier == "content")[0]
    if expected_manifest_sha256 is not None:
        _digest(expected_manifest_sha256, "expected manifest")
        if verified.manifest_sha256 != expected_manifest_sha256:
            raise CameraDatasetError(
                "Dataset differs from the externally retained manifest digest"
            )
    if expected_binding is not None:
        if (
            type(expected_binding) is not CaptureBinding
            or verified.plan.binding != expected_binding
        ):
            raise CameraDatasetError(
                "Dataset does not match the expected device/campaign/source binding"
            )
    return verified


def iter_native_frame(dataset: Path, frame_id: str) -> Iterator[bytes]:
    """Verify then reconstruct one native sample with <=1 MiB yielded blocks.

    Each chunk is rechecked immediately before yielding; callers must consume
    the iterator fully. This is not isolation against a hostile concurrent
    writer, and no verifier authenticates the hardware or capture operator.
    """
    verified, manifest = _inspect(dataset, content=True)
    record = next(
        (record for record in manifest["frames"] if record["frame_id"] == frame_id),
        None,
    )
    if record is None:
        raise CameraDatasetError("Unknown frame ID")
    for key in record["native"]["chunks"]:
        payload = read_bounded_regular_file(
            verified.path / "chunks" / f"{key}.bin",
            maximum_bytes=manifest["chunk_bytes"],
        )
        if hashlib.sha256(payload).hexdigest() != key:
            raise CameraDatasetError("Chunk changed after verification")
        yield payload
