"""Join closed native-v1 receipts to diagnostic datasets, without activation.

The caller owns the pre-capture request and registration. This bridge performs
only regular-file I/O, independently rechecks bytes/bindings, and never invokes
an authorizer, native helper, camera, serial device, or coordinator. A known
retention result is not M1 power-loss qualification or hardware acceptance.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, fields, is_dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import time
from typing import Any, BinaryIO, cast
import uuid

from rocell.application.camera_capture_dataset import (
    CameraCaptureDatasetStore,
    CameraDatasetCancelled,
    CaptureBinding,
    CapturePlan,
    DatasetQuotas,
    DatasetReceipt,
    DatasetVerification,
    DeviceIdentity,
    FramePlan,
    NativeFrameInput,
    PreviewInput,
    PreviewTransform,
    SampleLayout,
    SampleTiming,
    VideoMode,
    verify_capture_dataset,
)
from rocell.application.physical_onboarding_durability import safe_root
from rocell.application.wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.camera_worker_client import (
    PROTOCOL_SCHEMA,
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraCandidate,
    CameraControlSetting,
    CameraEndpointBinding,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeControlObservation,
    NativeFrameArtifact,
)


SCHEMA = "rocell.windows_camera_capture_ingest.v1"
CONTRACT_SCHEMA = "rocell.windows_camera_capture_ingest_plan.v1"
COLOR_POLICY = "BT601_LIMITED_DIAGNOSTIC_POLICY_NOT_OBSERVED"
RESAMPLE_POLICY = "NEAREST_PIXEL_CENTER_CLOCKWISE_ROTATION"
DOMAINS = frozenset({"PHYSICAL_UNVERIFIED", "INCAPABLE_NATIVE_FIXTURE"})
MAX_CONTRACT_BYTES = 256 * 1024
BLOCK_BYTES = 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_COUNTS = {
    "source_activation_attempts",
    "source_opened",
    "control_set_attempts",
    "samples_received",
    "frames_written",
    "source_shutdown_attempts",
}
_CONTROL_IDS = {
    "exposure",
    "gain",
    "white_balance",
    "brightness",
    "contrast",
    "saturation",
}
_NATIVE_FIELDS = {
    CameraActivationRequest: {
        "campaign_id",
        "source_sha256",
        "operation",
        "binding",
        "mode",
        "controls",
        "budget",
        "helper_sha256",
        "arguments_sha256",
        "output_directory",
    },
    NativeCameraReceipt: {
        "operation",
        "status",
        "reason_code",
        "selected_endpoint",
        "candidates",
        "modes",
        "requested_mode",
        "observed_mode",
        "controls",
        "frames",
        "counts",
        "cleanup_confirmed",
        "limitations",
    },
    NativeFrameArtifact: {
        "filename",
        "length_bytes",
        "stride_bytes",
        "row0_offset_bytes",
        "host_sequence",
        "media_timestamp_100ns",
        "host_arrival_qpc",
        "qpc_frequency",
        "discontinuity",
        "sha256",
    },
}


class CameraCaptureIngestError(ValueError):
    """Ingestion failed; original/partial artifacts are retained, never retried."""


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise CameraCaptureIngestError(detail)


def _integer(value: object, low: int, high: int, label: str) -> int:
    _require(type(value) is int and low <= value <= high, f"Invalid {label}")  # type: ignore[operator]
    return cast(int, value)


def _sha(value: object, label: str) -> None:
    _require(type(value) is str and _SHA.fullmatch(value) is not None, f"Invalid {label}")  # type: ignore[arg-type]


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, Mapping):
        _require(all(type(key) is str for key in value), "Non-string contract key")
        return {key: _plain(item) for key, item in value.items()}
    if type(value) in {tuple, list}:
        return [_plain(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    _require(
        value is None or type(value) in {str, int, bool}, "Non-JSON contract value"
    )
    return value


def _json(value: object) -> bytes:
    payload = (
        json.dumps(
            _plain(value),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    _require(
        len(payload) <= MAX_CONTRACT_BYTES, "Ingest contract exceeds metadata budget"
    )
    return payload


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def activation_request_sha256(request: CameraActivationRequest) -> str:
    """Pure canonical digest to pin the server-owned request before capture."""
    _validate_request(request)
    return _digest(request)


def _local_path(path: object, label: str) -> Path:
    _require(isinstance(path, Path), f"{label} must be an assigned Path")
    assert isinstance(path, Path)
    _require(
        path.is_absolute()
        and path != Path(path.anchor)
        and ".." not in path.parts
        and not str(path).startswith(("\\\\", "//")),
        f"{label} must be absolute/local/non-root",
    )
    return path


def _validate_request(request: CameraActivationRequest) -> None:
    _require(
        all(
            {field.name for field in fields(kind)} == expected
            for kind, expected in _NATIVE_FIELDS.items()
        ),
        "Native dataclass contract changed without a reviewed ingest version",
    )
    _require(
        type(request) is CameraActivationRequest,
        "Expected exact native activation request type",
    )
    _require(
        request.operation == "capture" and type(request.mode) is NativeCameraMode,
        "Only an explicitly requested native capture can be ingested",
    )
    _require(
        type(request.binding) is CameraEndpointBinding
        and type(request.budget) is CameraCampaignBudget,
        "Native request binding/budget types changed",
    )
    CameraEndpointBinding(**asdict(request.binding))
    CameraCampaignBudget(**asdict(request.budget))
    assert request.mode is not None
    NativeCameraMode(**asdict(request.mode))
    _require(request.mode.subtype == "YUY2", "Only native YUY2 is supported")
    _require(
        type(request.controls) is tuple and len(request.controls) <= 6,
        "Invalid requested control batch",
    )
    for control in request.controls:
        _require(type(control) is CameraControlSetting, "Untyped requested control")
        CameraControlSetting(**asdict(control))
    _require(
        len({control.control_id for control in request.controls})
        == len(request.controls),
        "Duplicate requested control",
    )
    for label in ("source_sha256", "helper_sha256", "arguments_sha256"):
        _sha(getattr(request, label), label)
    _require(
        type(request.campaign_id) is str
        and _ID.fullmatch(request.campaign_id) is not None,
        "Invalid campaign identifier",
    )
    output_directory = request.output_directory
    if type(output_directory) is not str or not output_directory:
        raise CameraCaptureIngestError("Capture directory missing")
    _local_path(Path(output_directory), "Capture directory")


@dataclass(frozen=True)
class NativeCaptureIngestPlan:
    native_protocol_schema: str
    activation_request_sha256: str
    capture_directory: Path
    dataset_root: Path
    source_sha256: str
    settings_epoch: str
    domain: str
    frames: tuple[FramePlan, ...]
    quotas: DatasetQuotas
    retention_timeout_ms: int

    def __post_init__(self) -> None:
        # NativeCameraReceipt has no schema member; explicitly pin its current
        # protocol at this adapter boundary instead of silently widening v1.
        _require(
            self.native_protocol_schema
            == PROTOCOL_SCHEMA
            == "rocell.windows_camera.v1",
            "Unreviewed native receipt protocol version",
        )
        _sha(self.activation_request_sha256, "request digest")
        _sha(self.source_sha256, "source digest")
        _local_path(self.capture_directory, "Capture directory")
        _local_path(self.dataset_root, "Dataset root")
        _require(
            not self.dataset_root.is_relative_to(self.capture_directory)
            and not self.capture_directory.is_relative_to(self.dataset_root),
            "Capture inputs and dataset outputs must have separate assigned roots",
        )
        _require(
            type(self.settings_epoch) is str
            and _ID.fullmatch(self.settings_epoch) is not None,
            "Invalid settings epoch",
        )
        _require(
            type(self.domain) is str and self.domain in DOMAINS,
            "Ingest domain cannot claim qualified hardware",
        )
        _require(
            type(self.frames) is tuple
            and 1 <= len(self.frames) <= 32
            and all(type(frame) is FramePlan for frame in self.frames),
            "Preassigned frame plans required",
        )
        _require(type(self.quotas) is DatasetQuotas, "Typed artifact quotas required")
        DatasetQuotas(**asdict(self.quotas))
        _integer(self.retention_timeout_ms, 100, 300_000, "retention time budget")
        _require(
            sum(frame.preview is not None for frame in self.frames) <= 1,
            "Only one bounded latest-frame preview is retained",
        )
        _require(
            not any(frame.preview is not None for frame in self.frames[:-1]),
            "Preview may be attached only to the final planned frame",
        )


def prepare_windows_camera_ingest(
    request: CameraActivationRequest,
    *,
    capture_directory: Path,
    dataset_root: Path,
    source_sha256: str,
    settings_epoch: str,
    domain: str,
    frames: tuple[FramePlan, ...],
    quotas: DatasetQuotas | None = None,
    retention_timeout_ms: int = 120_000,
) -> NativeCaptureIngestPlan:
    """Pure planning. Binary budgets are separate from coordinator JSON budgets."""
    result = NativeCaptureIngestPlan(
        PROTOCOL_SCHEMA,
        activation_request_sha256(request),
        capture_directory,
        dataset_root,
        source_sha256,
        settings_epoch,
        domain,
        frames,
        DatasetQuotas(**asdict(quotas)) if quotas is not None else DatasetQuotas(),
        retention_timeout_ms,
    )
    _require(
        str(result.capture_directory) == request.output_directory,
        "Assigned capture path differs from the exact request",
    )
    _require(
        result.source_sha256 == request.source_sha256,
        "Source differs from the exact request",
    )
    _require(
        len(frames) == request.budget.max_frames,
        "Planned frame count differs from request",
    )
    return result


@dataclass(frozen=True)
class DerivedCameraPreview:
    frame_id: str
    native_sha256: str
    png_sha256: str
    transform: PreviewTransform
    png_bytes: bytes
    color_policy: str = COLOR_POLICY
    resample_policy: str = RESAMPLE_POLICY

    def to_dict(self) -> dict[str, Any]:
        return {
            field.name: _plain(getattr(self, field.name))
            for field in fields(self)
            if field.name != "png_bytes"
        }


@dataclass(frozen=True)
class NativeCaptureIngestReceipt:
    dataset: DatasetReceipt
    verification: DatasetVerification
    latest_preview: DerivedCameraPreview | None
    envelope_path: Path
    envelope_sha256: str
    source_contract_sha256: str
    domain: str
    physical_authority: bool = False
    m1_qualified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": "CONTENT_VERIFIED_DIAGNOSTIC_ONLY",
            "domain": self.domain,
            "dataset": _plain(self.dataset),
            "verification": _plain(self.verification),
            "latest_preview": (
                self.latest_preview.to_dict() if self.latest_preview else None
            ),
            "envelope_path": str(self.envelope_path),
            "envelope_sha256": self.envelope_sha256,
            "source_contract_sha256": self.source_contract_sha256,
            "physical_authority": False,
            "m1_qualified": False,
            "received_hardware_accepted": False,
            "native_power_loss_qualification": "NOT_RUN",
        }


def _bounded_record(value: object) -> dict[str, Any]:
    """Snapshot ordinary decoded metadata before trusting nested fields.

    The caller's hashes are trusted M1 references, not browser input. Bounds
    still apply to that record and to parsed disk documents before comparison.
    """
    remaining_nodes = 8192
    remaining_text = MAX_CONTRACT_BYTES

    def copy(item: Any, depth: int = 0) -> Any:
        nonlocal remaining_nodes, remaining_text
        remaining_nodes -= 1
        _require(remaining_nodes >= 0 and depth <= 24, "Metadata nesting/node budget")
        if isinstance(item, Mapping):
            _require(len(item) <= 4096, "Metadata mapping budget")
            result = {}
            for key, child in item.items():
                _require(type(key) is str, "Non-string metadata key")
                copied_key = copy(key, depth + 1)
                _require(copied_key not in result, "Duplicate metadata key")
                result[copied_key] = copy(child, depth + 1)
            return result
        if type(item) is list:
            _require(len(item) <= 4096, "Metadata list budget")
            return [copy(child, depth + 1) for child in item]
        if type(item) is str:
            remaining_text -= len(item)
            _require(remaining_text >= 0, "Metadata text budget")
        else:
            _require(item is None or type(item) in {int, bool}, "Non-JSON metadata")
            if type(item) is int:
                _require(abs(item) <= 2**64 - 1, "Metadata integer budget")
        return item

    result = copy(value)
    _require(type(result) is dict, "Expected serialized ingest receipt object")
    _json(result)
    return cast(dict[str, Any], result)


def _exact_record(value: Any, names: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == names, f"Invalid {label} schema")
    return cast(dict[str, Any], value)


def _retained_document(
    path: Path, expected_sha256: str, handles: ExitStack
) -> dict[str, Any]:
    """Keep provenance handles read-locked through the inner dataset check."""
    _sha(expected_sha256, "retained document digest")
    length = _integer(
        path.stat(follow_symlinks=False).st_size,
        1,
        MAX_CONTRACT_BYTES,
        "retained metadata size",
    )
    stream = handles.enter_context(_locked_file(path, length))
    payload = stream.read(length + 1)
    _require(
        len(payload) == length
        and hashlib.sha256(payload).hexdigest() == expected_sha256,
        "Retained ingest provenance length/hash mismatch",
    )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "Duplicate retained metadata field")
            result[key] = value
        return result

    try:
        value = _bounded_record(
            json.loads(payload.decode("ascii"), object_pairs_hook=pairs)
        )
        _require(_json(value) == payload, "Noncanonical retained ingest metadata")
        return value
    except (UnicodeError, RecursionError) as error:
        raise CameraCaptureIngestError("Invalid retained ingest metadata") from error


def _retained_ingest_inventory(ingest_root: Path, dataset_name: str) -> None:
    """A pending sentinel or any unrecognized entry prevents acceptance.

    Inspect at most four entries, including the first over-budget entry. In
    particular, a fully flushed final envelope is not a commit while its
    pending marker remains. Call only while the directory guard is held.
    """
    expected = {"source-contract.json", "ingest-receipt.json", dataset_name}
    observed: set[str] = set()
    with os.scandir(ingest_root) as entries:
        for entry in entries:
            _require(
                len(observed) < 3 and entry.name in expected,
                "Incomplete or unexpected retained ingest directory inventory",
            )
            observed.add(entry.name)
    _require(observed == expected, "Incomplete retained ingest directory inventory")


def verify_windows_capture_ingest(
    receipt: Mapping[str, Any],
    *,
    expected_source_sha256: str,
    expected_settings_epoch: str,
    expected_campaign_id: str,
    expected_endpoint_sha256: str,
) -> DatasetVerification:
    """Reverify a trusted retained ingest reference, never activate or repair.

    Pass an M1-retained ``NativeCaptureIngestReceipt.to_dict()`` value, not
    frontend-provided paths/hashes. The caller additionally owns containment in
    its selected session store. Native input files are not needed: provenance
    documents and every retained dataset sample are checked without rereading
    the original capture directory. This is diagnostic content verification,
    not freshness acceptance, physical qualification, or M1 crash durability.
    """
    _sha(expected_source_sha256, "expected source digest")
    _sha(expected_endpoint_sha256, "expected endpoint digest")
    for value, label in (
        (expected_settings_epoch, "expected settings epoch"),
        (expected_campaign_id, "expected campaign identifier"),
    ):
        _require(
            type(value) is str and _ID.fullmatch(value) is not None,
            f"Invalid {label}",
        )
    expected = _exact_record(
        _bounded_record(receipt),
        {
            "schema",
            "status",
            "domain",
            "dataset",
            "verification",
            "latest_preview",
            "envelope_path",
            "envelope_sha256",
            "source_contract_sha256",
            "physical_authority",
            "m1_qualified",
            "received_hardware_accepted",
            "native_power_loss_qualification",
        },
        "retained ingest receipt",
    )
    _require(
        expected["schema"] == SCHEMA
        and expected["status"] == "CONTENT_VERIFIED_DIAGNOSTIC_ONLY"
        and type(expected["domain"]) is str
        and expected["domain"] in DOMAINS
        and expected["physical_authority"] is False
        and expected["m1_qualified"] is False
        and expected["received_hardware_accepted"] is False
        and expected["native_power_loss_qualification"] == "NOT_RUN",
        "Retained receipt cannot claim qualified hardware",
    )
    dataset = _exact_record(
        expected["dataset"],
        {field.name for field in fields(DatasetReceipt)},
        "retained dataset reference",
    )
    for path_value in (expected["envelope_path"], dataset["path"]):
        _require(type(path_value) is str, "Retained artifact path must be text")
    envelope_path = _local_path(Path(expected["envelope_path"]), "Ingest envelope")
    dataset_path = _local_path(Path(dataset["path"]), "Retained dataset")
    ingest_root = envelope_path.parent
    _require(
        envelope_path.name == "ingest-receipt.json"
        and re.fullmatch(r"ingest-[0-9a-f]{32}", ingest_root.name) is not None
        and dataset_path.parent == ingest_root
        and re.fullmatch(r"capture-[0-9a-f]{32}", dataset_path.name) is not None,
        "Retained envelope/dataset path relationship mismatch",
    )
    _sha(expected["envelope_sha256"], "expected envelope digest")
    _sha(expected["source_contract_sha256"], "expected source contract digest")
    _sha(dataset["manifest_sha256"], "expected dataset manifest digest")
    _sha(dataset["plan_sha256"], "expected dataset plan digest")
    safe_root(ingest_root, label="retained ingest directory")
    safe_root(ingest_root.parent, label="retained dataset output root")
    safe_root(dataset_path, label="retained inner dataset directory")
    with _directory_guard(ingest_root.parent), _directory_guard(
        ingest_root
    ), _directory_guard(dataset_path), ExitStack() as handles:
        _retained_ingest_inventory(ingest_root, dataset_path.name)
        envelope = _retained_document(
            envelope_path, expected["envelope_sha256"], handles
        )
        shared = set(expected) - {"envelope_path", "envelope_sha256"}
        _exact_record(
            envelope,
            shared | {"activation_request_sha256", "native_receipt_sha256"},
            "retained ingest envelope",
        )
        _require(
            _json({key: envelope[key] for key in shared})
            == _json({key: expected[key] for key in shared}),
            "Retained envelope differs from its trusted receipt",
        )
        source = _retained_document(
            ingest_root / "source-contract.json",
            expected["source_contract_sha256"],
            handles,
        )
        _exact_record(
            source,
            {
                "schema",
                "plan",
                "activation_request",
                "native_receipt",
                "native_receipt_sha256",
                "capture_plan",
                "timing_conversion",
                "media_conversion",
                "color_policy",
                "resample_policy",
                "physical_authority",
                "m1_qualified",
            },
            "retained source contract",
        )
        _require(
            source["schema"] == CONTRACT_SCHEMA
            and source["physical_authority"] is False
            and source["m1_qualified"] is False
            and source["timing_conversion"]
            == "QPC_POINT_FLOOR_CEIL_NS_NOT_CAPTURE_INTERVAL_OR_WALL_TIME"
            and source["media_conversion"] == "EXACT_100NS_TO_NS_NOT_SENSOR_EXPOSURE"
            and source["color_policy"] == COLOR_POLICY
            and source["resample_policy"] == RESAMPLE_POLICY,
            "Retained source contract provenance changed",
        )
        plan = _exact_record(
            source["plan"],
            {field.name for field in fields(NativeCaptureIngestPlan)},
            "retained ingest plan",
        )
        request = _exact_record(
            source["activation_request"],
            _NATIVE_FIELDS[CameraActivationRequest],
            "retained activation request",
        )
        endpoint = _exact_record(
            request["binding"],
            {field.name for field in fields(CameraEndpointBinding)},
            "retained endpoint binding",
        )
        binding = CameraEndpointBinding(**endpoint)
        native = _exact_record(
            source["native_receipt"],
            _NATIVE_FIELDS[NativeCameraReceipt],
            "retained native receipt",
        )
        _require(
            plan["native_protocol_schema"]
            == PROTOCOL_SCHEMA
            == "rocell.windows_camera.v1"
            and plan["domain"] == expected["domain"]
            and plan["dataset_root"] == str(ingest_root.parent)
            and plan["capture_directory"] == request["output_directory"]
            and plan["source_sha256"]
            == request["source_sha256"]
            == expected_source_sha256
            and plan["settings_epoch"] == expected_settings_epoch
            and request["campaign_id"] == expected_campaign_id
            and request["operation"] == "capture"
            and binding.endpoint_sha256 == expected_endpoint_sha256
            and native["selected_endpoint"] == binding.symbolic_link
            and native["operation"] == "capture"
            and native["status"] == "OK"
            and native["reason_code"] is None
            and native["cleanup_confirmed"] is True
            and _digest(request)
            == plan["activation_request_sha256"]
            == envelope["activation_request_sha256"]
            and _digest(native)
            == source["native_receipt_sha256"]
            == envelope["native_receipt_sha256"],
            "Retained source/request/identity binding mismatch",
        )
        # Keep the plan's expected hash checked as well as the manifest's own
        # reference. This handle also denies replacement during content reads.
        _retained_document(
            dataset_path / "capture-plan.json", dataset["plan_sha256"], handles
        )
        verification = verify_capture_dataset(
            dataset_path, expected_manifest_sha256=dataset["manifest_sha256"]
        )
        actual = verification.plan.binding
        synthetic = expected["domain"] == "INCAPABLE_NATIVE_FIXTURE"
        _require(
            verification.content_verified
            and verification.requested_mode_matches
            and verification.physical_authority is False
            and verification.m1_qualified is False
            and actual.source_sha256 == expected_source_sha256
            and actual.settings_epoch == expected_settings_epoch
            and actual.campaign_id == expected_campaign_id
            and actual.device.persistent_id
            == "endpoint-sha256:" + expected_endpoint_sha256
            and actual.provenance
            == ("SYNTHETIC" if synthetic else "PHYSICAL_UNVERIFIED")
            and actual.device.backend
            == ("SYNTHETIC" if synthetic else "WINDOWS_MEDIA_FOUNDATION")
            and _json(_plain(verification)) == _json(expected["verification"])
            and _json(_plain(verification.plan)) == _json(source["capture_plan"])
            and verification.frames == dataset["frames"]
            and verification.logical_bytes == dataset["logical_bytes"]
            and dataset["physical_authority"] is False,
            "Retained dataset differs from its exact campaign/content binding",
        )
        _retained_ingest_inventory(ingest_root, dataset_path.name)
        return verification


def render_yuy2_preview(
    read_row: Callable[[int], bytes],
    *,
    mode: VideoMode,
    transform: PreviewTransform,
    cancelled: Callable[[], bool] = lambda: False,
) -> bytes:
    """PNG from actual active YUY2 rows, using bounded nearest-neighbor sampling.

    read_row accepts a logical top-down row index and returns exactly width*2
    bytes. Padding/bottom-up offsets belong to the source accessor. At most one
    source row and one output RGB image (<=2048² pixels) are held; no native-frame
    join occurs. Color interpretation is an explicit diagnostic policy because
    native-v1 does not report observed matrix/range. Rotation is clockwise.
    """
    import numpy as np
    from numpy.typing import NDArray
    from PIL import Image

    _require(
        type(mode) is VideoMode and type(transform) is PreviewTransform,
        "Typed preview mode/transform required",
    )
    mode = VideoMode(**asdict(mode))
    transform = PreviewTransform(**asdict(transform))
    transform.validate_for(mode)
    _require(transform.encoding == "PNG", "Bridge previews use bounded PNG only")

    def check() -> None:
        result = cancelled()
        _require(type(result) is bool, "Cancellation callback must return bool")
        if result:
            raise CameraDatasetCancelled("Preview cancelled before publication")

    check()
    rotation = transform.rotation_degrees
    rotated_width, rotated_height = transform.crop_width, transform.crop_height
    if rotation in {90, 270}:
        rotated_width, rotated_height = rotated_height, rotated_width
    xmap: NDArray[np.int64] = (
        (2 * np.arange(transform.output_width) + 1)
        * rotated_width
        // (2 * transform.output_width)
    )
    ymap: NDArray[np.int64] = (
        (2 * np.arange(transform.output_height) + 1)
        * rotated_height
        // (2 * transform.output_height)
    )
    rgb: NDArray[np.uint8] = np.empty(
        (transform.output_height, transform.output_width, 3), dtype=np.uint8
    )

    def pixels(row_index: int, positions: Any) -> Any:
        check()
        raw = read_row(row_index)
        _require(
            type(raw) is bytes and len(raw) == mode.width * 2,
            "Preview row length/type mismatch",
        )
        row = np.frombuffer(raw, dtype=np.uint8)
        x = positions + transform.crop_x
        c = row[2 * x].astype(np.int32) - 16
        d = row[4 * (x // 2) + 1].astype(np.int32) - 128
        e = row[4 * (x // 2) + 3].astype(np.int32) - 128
        # Microsoft YUY2 byte order and BT.601 studio-range conversion. This is
        # a chosen rendering policy, not observed colorimetry or calibration.
        return np.stack(
            (
                np.clip((298 * c + 409 * e + 128) >> 8, 0, 255),
                np.clip((298 * c - 100 * d - 208 * e + 128) >> 8, 0, 255),
                np.clip((298 * c + 516 * d + 128) >> 8, 0, 255),
            ),
            axis=1,
        ).astype(np.uint8)

    if rotation in {0, 180}:
        for y, source_y in enumerate(ymap):
            positions = xmap if rotation == 0 else transform.crop_width - 1 - xmap
            sy = source_y if rotation == 0 else transform.crop_height - 1 - source_y
            rgb[y, :, :] = pixels(int(sy) + transform.crop_y, positions)
    else:
        for x, source_x in enumerate(xmap):
            positions = ymap if rotation == 90 else transform.crop_width - 1 - ymap
            sy = transform.crop_height - 1 - source_x if rotation == 90 else source_x
            rgb[:, x, :] = pixels(int(sy) + transform.crop_y, positions)
    check()

    class BoundedBuffer(io.BytesIO):
        def write(self, payload: Any) -> int:
            _require(
                self.tell() + len(payload) <= transform.maximum_bytes,
                "Derived PNG exceeds approved byte budget",
            )
            return super().write(payload)

    encoded = BoundedBuffer()
    Image.fromarray(rgb).save(encoded, format="PNG", optimize=False)
    check()
    return encoded.getvalue()


def _video(mode: NativeCameraMode) -> VideoMode:
    _require(type(mode) is NativeCameraMode, "Untyped native mode")
    NativeCameraMode(**asdict(mode))
    divisor = math.gcd(mode.fps_numerator, mode.fps_denominator)
    return VideoMode(
        mode.width,
        mode.height,
        mode.fps_numerator // divisor,
        mode.fps_denominator // divisor,
        mode.subtype,
    )


def _validate_receipt(
    request: CameraActivationRequest,
    receipt: NativeCameraReceipt,
    plan: NativeCaptureIngestPlan,
) -> tuple[CapturePlan, tuple[SampleTiming, ...]]:
    _require(
        type(receipt) is NativeCameraReceipt,
        "Expected typed validated native-v1 receipt",
    )
    _require(
        type(receipt.limitations) is tuple
        and len(receipt.limitations) <= 24
        and all(
            type(item) is str and 1 <= len(item) <= 128 for item in receipt.limitations
        ),
        "Invalid native limitation observations",
    )
    _require(
        receipt.operation == "capture"
        and receipt.status == "OK"
        and receipt.reason_code is None
        and receipt.cleanup_confirmed is True,
        "Failed/uncertain capture cannot be ingested as complete",
    )
    _require(
        receipt.selected_endpoint == request.binding.symbolic_link,
        "Exact camera endpoint mismatch",
    )
    _require(
        type(receipt.candidates) is tuple and 1 <= len(receipt.candidates) <= 64,
        "Missing/bounded candidate observations required",
    )
    _require(
        all(type(candidate) is CameraCandidate for candidate in receipt.candidates),
        "Untyped candidate",
    )
    _require(
        sum(
            candidate.symbolic_link == receipt.selected_endpoint
            for candidate in receipt.candidates
        )
        == 1,
        "Selected endpoint was not observed exactly once",
    )
    assert request.mode is not None
    _require(
        type(receipt.requested_mode) is NativeCameraMode
        and type(receipt.observed_mode) is NativeCameraMode,
        "Requested and observed native modes are required",
    )
    assert receipt.requested_mode is not None and receipt.observed_mode is not None
    _require(
        request.mode.same_format(receipt.requested_mode)
        and request.mode.same_format(receipt.observed_mode),
        "Requested/observed mode drift",
    )
    _require(
        type(receipt.modes) is tuple
        and 1 <= len(receipt.modes) <= 128
        and all(type(mode) is NativeCameraMode for mode in receipt.modes),
        "Invalid observed mode inventory",
    )
    _require(
        any(receipt.observed_mode.same_format(mode) for mode in receipt.modes),
        "Actual mode was absent from native mode inventory",
    )
    observed, requested = _video(receipt.observed_mode), _video(request.mode)
    count = len(plan.frames)
    expected_counts = {
        "source_activation_attempts": 1,
        "source_opened": 1,
        "source_shutdown_attempts": 1,
        "control_set_attempts": len(request.controls),
        "samples_received": count,
        "frames_written": count,
    }
    _require(
        isinstance(receipt.counts, Mapping) and set(receipt.counts) == _COUNTS,
        "Native effect accounting schema changed",
    )
    _require(
        all(
            type(receipt.counts[key]) is int and receipt.counts[key] == value
            for key, value in expected_counts.items()
        ),
        "Native capture budget/accounting mismatch",
    )
    _require(
        type(receipt.controls) is tuple
        and len(receipt.controls) <= 6
        and all(
            type(control) is NativeControlObservation for control in receipt.controls
        ),
        "Invalid control readback receipt",
    )
    controls = {control.control_id: control for control in receipt.controls}
    _require(len(controls) == len(receipt.controls), "Duplicate native control")
    for control in controls.values():
        _require(control.control_id in _CONTROL_IDS, "Unregistered native control")
        for name in ("minimum", "maximum", "default", "value"):
            _integer(getattr(control, name), -(2**31), 2**31 - 1, "control readback")
        _integer(control.step, 1, 2**31 - 1, "control step")
        _integer(control.flags, 1, 3, "control flags")
        _integer(control.capability_flags, 1, 3, "control capabilities")
        _require(
            control.minimum <= control.value <= control.maximum
            and control.minimum <= control.default <= control.maximum,
            "Invalid control range",
        )
    for setting in request.controls:
        actual = controls.get(setting.control_id)
        _require(
            actual is not None
            and actual.flags == (1 if setting.mode == "auto" else 2)
            and (setting.mode == "auto" or actual.value == setting.value),
            "Control readback drift",
        )
    _require(
        type(receipt.frames) is tuple
        and len(receipt.frames) == count == request.budget.max_frames,
        "Native frame count differs from preassigned capture",
    )
    timings: list[SampleTiming] = []
    layout: SampleLayout | None = None
    previous_qpc = -1
    frequency = None
    total = 0
    for index, frame in enumerate(receipt.frames):
        _require(
            type(frame) is NativeFrameArtifact
            and frame.filename == f"frame-{index:06d}.yuy2",
            "Unexpected native file name/order",
        )
        _sha(frame.sha256, "native sample digest")
        _integer(
            frame.length_bytes, 1, request.budget.max_frame_bytes, "native file length"
        )
        _integer(frame.stride_bytes, -1_048_576, 1_048_576, "native stride")
        candidate_layout = SampleLayout(
            abs(frame.stride_bytes),
            "TOP_DOWN" if frame.stride_bytes > 0 else "BOTTOM_UP",
        )
        _require(
            frame.length_bytes == candidate_layout.sample_bytes(observed),
            "Native-v1 dataset requires exact stride*height bytes; no buffer trimming/padding invention",
        )
        expected_origin = (
            0
            if frame.stride_bytes > 0
            else abs(frame.stride_bytes) * (observed.height - 1)
        )
        _require(
            type(frame.row0_offset_bytes) is int
            and frame.row0_offset_bytes == expected_origin,
            "Unsupported native row origin; no inferred reordering",
        )
        _require(
            layout is None or layout == candidate_layout,
            "Sample layouts changed during capture",
        )
        layout = candidate_layout
        _require(
            receipt.observed_mode.stride_bytes is None
            or receipt.observed_mode.stride_bytes == frame.stride_bytes,
            "Observed mode/sample stride mismatch",
        )
        _require(
            type(frame.host_sequence) is int and frame.host_sequence == index,
            "Host sample sequence mismatch",
        )
        _integer(frame.host_arrival_qpc, 0, 2**63 - 1, "host arrival QPC")
        _integer(frame.qpc_frequency, 1, 2**63 - 1, "QPC frequency")
        _require(
            frame.host_arrival_qpc >= previous_qpc
            and (frequency is None or frequency == frame.qpc_frequency),
            "Host QPC order/frequency changed",
        )
        previous_qpc, frequency = frame.host_arrival_qpc, frame.qpc_frequency
        _require(
            frame.discontinuity is None or type(frame.discontinuity) is bool,
            "Invalid discontinuity observation",
        )
        _require(
            frame.discontinuity is not True,
            "Discontinuous samples require explicit review, not normal ingestion",
        )
        # Dataset v1 cannot represent negative media times. Refuse rather than
        # silently rebasing them or replacing them with a host/wall-clock time.
        _integer(
            frame.media_timestamp_100ns,
            0,
            (2**63 - 1) // 100,
            "representable media time",
        )
        numerator = frame.host_arrival_qpc * 1_000_000_000
        start, end = (
            numerator // frame.qpc_frequency,
            (numerator + frame.qpc_frequency - 1) // frame.qpc_frequency,
        )
        timings.append(
            SampleTiming(
                index,
                start,
                end,
                frame.media_timestamp_100ns * 100,
                (
                    "SYNTHETIC_SAMPLE_TIME"
                    if plan.domain == "INCAPABLE_NATIVE_FIXTURE"
                    else "MEDIA_SAMPLE_TIME"
                ),
            )
        )
        total += frame.length_bytes
        _require(
            total <= request.budget.max_total_bytes,
            "Native payload exceeds exact activation artifact budget",
        )
    assert layout is not None
    planned_maximum = total + sum(
        frame.preview.maximum_bytes if frame.preview else 0 for frame in plan.frames
    )
    _require(
        count <= plan.quotas.frames
        and all(
            frame.length_bytes <= plan.quotas.frame_bytes for frame in receipt.frames
        )
        and planned_maximum <= plan.quotas.total_bytes,
        "Capture exceeds preassigned artifact quotas",
    )
    _require(
        sum(
            math.ceil(frame.length_bytes / plan.quotas.chunk_bytes)
            + (
                math.ceil(frame_plan.preview.maximum_bytes / plan.quotas.chunk_bytes)
                if frame_plan.preview
                else 0
            )
            for frame, frame_plan in zip(receipt.frames, plan.frames)
        )
        <= 4096,
        "Capture exceeds chunk-reference budget",
    )
    binding = CaptureBinding(
        (
            "SYNTHETIC"
            if plan.domain == "INCAPABLE_NATIVE_FIXTURE"
            else "PHYSICAL_UNVERIFIED"
        ),
        plan.source_sha256,
        request.campaign_id,
        plan.settings_epoch,
        # This is an endpoint-reference digest, NOT a unit serial/container ID.
        DeviceIdentity(
            (
                "SYNTHETIC"
                if plan.domain == "INCAPABLE_NATIVE_FIXTURE"
                else "WINDOWS_MEDIA_FOUNDATION"
            ),
            "endpoint-sha256:" + request.binding.endpoint_sha256,
        ),
        requested,
        observed,
    )
    return CapturePlan(binding, layout, plan.frames), tuple(timings)


def _file_stat(path: Path, length: int) -> os.stat_result:
    result = path.stat(follow_symlinks=False)
    _require(
        stat.S_ISREG(result.st_mode)
        and not getattr(result, "st_file_attributes", 0) & 0x400
        and result.st_nlink == 1
        and result.st_size == length,
        "Native input is not its single-link bounded regular file",
    )
    return result


@contextmanager
def _locked_file(path: Path, length: int) -> Iterator[BinaryIO]:
    """Own one regular-file handle; on Windows deny concurrent writes/deletes."""
    before = _file_stat(path, length)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # Construct this prefix only for a checked absolute local regular file;
        # it permits long artifact paths, not caller-supplied device paths.
        handle = kernel.CreateFileW(
            "\\\\?\\" + str(path), 0x80000000, 0x1, None, 3, 0x00200000, None
        )
        if handle == wintypes.HANDLE(-1).value:
            raise OSError(
                ctypes.get_last_error(), "Cannot lock native regular input file"
            )
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    else:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        opened = os.fstat(stream.fileno())
        _require(
            (opened.st_dev, opened.st_ino, opened.st_size)
            == (before.st_dev, before.st_ino, before.st_size)
            and opened.st_nlink == 1
            and stat.S_ISREG(opened.st_mode),
            "Native file changed while opening",
        )
        yield stream
        after = _file_stat(path, length)
        _require(
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
            "Native input changed during ingestion",
        )


def _blocks(
    stream: BinaryIO, frame: NativeFrameArtifact, cancelled: Callable[[], bool]
) -> Iterator[bytes]:
    stream.seek(0)
    digest = hashlib.sha256()
    remaining = frame.length_bytes
    while remaining:
        if cancelled():
            raise CameraDatasetCancelled("Native file retention cancelled")
        block = stream.read(min(BLOCK_BYTES, remaining))
        _require(bool(block), "Native file truncated during ingestion")
        digest.update(block)
        remaining -= len(block)
        yield block
    _require(
        stream.read(1) == b"" and digest.hexdigest() == frame.sha256,
        "Native file length/hash changed after validated receipt",
    )


def _new_json(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _inventory(directory: Path, receipt: NativeCameraReceipt) -> None:
    from itertools import islice

    names = [path.name for path in islice(directory.iterdir(), 33)]
    _require(
        len(names) == len(receipt.frames)
        and set(names) == {frame.filename for frame in receipt.frames},
        "Capture directory has missing/unreported input files",
    )


def ingest_windows_capture(
    request: CameraActivationRequest,
    receipt: NativeCameraReceipt,
    *,
    plan: NativeCaptureIngestPlan,
    cancelled: Callable[[], bool] = lambda: False,
) -> NativeCaptureIngestReceipt:
    """Retain existing samples, derive one preview, and verify diagnostic bytes.

    No failed/uncertain capture is made successful by this adapter. Binary I/O
    quotas in plan/request are distinct from the coordinator's receipt-JSON
    output budget. Publication failures retain inputs and incomplete outputs.
    """
    _require(type(plan) is NativeCaptureIngestPlan, "Prepared ingest plan required")
    # Recheck nested frozen objects and exact request after queueing/capture.
    plan.__post_init__()
    _require(
        activation_request_sha256(request) == plan.activation_request_sha256,
        "Activation request changed after ingest preparation",
    )
    _require(
        request.source_sha256 == plan.source_sha256
        and request.output_directory == str(plan.capture_directory),
        "Source/capture directory binding mismatch",
    )
    capture_plan, timings = _validate_receipt(request, receipt, plan)
    deadline = time.monotonic_ns() + plan.retention_timeout_ms * 1_000_000

    def stopped() -> bool:
        value = cancelled()
        _require(type(value) is bool, "Cancellation callback must return bool")
        _require(
            time.monotonic_ns() <= deadline,
            "Retention deadline exceeded; no automatic retry",
        )
        return value

    if stopped():
        raise CameraDatasetCancelled("Cancelled before capture ingestion")
    capture_directory = safe_root(plan.capture_directory, label="native capture input")
    dataset_root = safe_root(plan.dataset_root, label="assigned dataset output")
    planned_bytes = sum(
        frame.length_bytes + (item.preview.maximum_bytes if item.preview else 0)
        for frame, item in zip(receipt.frames, plan.frames)
    )
    _require(
        shutil.disk_usage(dataset_root).free
        >= planned_bytes
        + 4 * 1024 * 1024
        + 2 * MAX_CONTRACT_BYTES
        + plan.quotas.disk_reserve_bytes,
        "Insufficient disk budget for dataset and bridge metadata",
    )
    source_contract = {
        "schema": CONTRACT_SCHEMA,
        "plan": _plain(plan),
        "activation_request": _plain(request),
        "native_receipt": _plain(receipt),
        "native_receipt_sha256": _digest(receipt),
        "capture_plan": _plain(capture_plan),
        "timing_conversion": "QPC_POINT_FLOOR_CEIL_NS_NOT_CAPTURE_INTERVAL_OR_WALL_TIME",
        "media_conversion": "EXACT_100NS_TO_NS_NOT_SENSOR_EXPOSURE",
        "color_policy": COLOR_POLICY,
        "resample_policy": RESAMPLE_POLICY,
        "physical_authority": False,
        "m1_qualified": False,
    }
    source_bytes = _json(source_contract)
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    latest: DerivedCameraPreview | None = None
    with _directory_guard(capture_directory), _directory_guard(
        dataset_root
    ), ExitStack() as handles:
        _inventory(capture_directory, receipt)
        streams = [
            handles.enter_context(
                _locked_file(capture_directory / frame.filename, frame.length_bytes)
            )
            for frame in receipt.frames
        ]
        # Verify every original digest before creating any dataset. Locked handles
        # remain owned through preview generation and manifest-last publication.
        for stream, frame in zip(streams, receipt.frames):
            for _ in _blocks(stream, frame, stopped):
                pass
        if stopped():
            raise CameraDatasetCancelled("Cancelled before ingest output creation")
        ingest_directory = dataset_root / ("ingest-" + uuid.uuid4().hex)
        ingest_directory.mkdir(exist_ok=False)
        with _directory_guard(ingest_directory):
            _new_json(ingest_directory / "source-contract.json", source_bytes)

            def frames() -> Iterator[NativeFrameInput]:
                nonlocal latest
                for frame_plan, native, stream, timing in zip(
                    plan.frames, receipt.frames, streams, timings
                ):
                    preview = None
                    if frame_plan.preview is not None:

                        def read_row(y: int) -> bytes:
                            _integer(
                                y,
                                0,
                                capture_plan.binding.observed_mode.height - 1,
                                "preview row",
                            )
                            stream.seek(
                                native.row0_offset_bytes + y * native.stride_bytes
                            )
                            return stream.read(
                                capture_plan.binding.observed_mode.width * 2
                            )

                        png = render_yuy2_preview(
                            read_row,
                            mode=capture_plan.binding.observed_mode,
                            transform=frame_plan.preview,
                            cancelled=stopped,
                        )
                        latest = DerivedCameraPreview(
                            frame_plan.frame_id,
                            native.sha256,
                            hashlib.sha256(png).hexdigest(),
                            frame_plan.preview,
                            png,
                        )
                        preview = PreviewInput(
                            native.sha256,
                            (
                                png[offset : offset + BLOCK_BYTES]
                                for offset in range(0, len(png), BLOCK_BYTES)
                            ),
                        )
                    yield NativeFrameInput(
                        frame_plan.frame_id,
                        timing,
                        _blocks(stream, native, stopped),
                        preview,
                    )

            dataset = CameraCaptureDatasetStore(
                ingest_directory, quotas=plan.quotas
            ).publish(capture_plan, frames(), cancelled=stopped)
            _inventory(capture_directory, receipt)
            if stopped():
                raise CameraDatasetCancelled(
                    "Cancelled after dataset publication; no ingest completion receipt"
                )
            verification = verify_capture_dataset(
                dataset.path,
                expected_manifest_sha256=dataset.manifest_sha256,
                expected_binding=capture_plan.binding,
            )
            _require(
                verification.content_verified
                and verification.requested_mode_matches
                and not verification.physical_authority
                and not verification.m1_qualified,
                "Dataset failed exact unqualified-content verification",
            )
            # Finish input handle/metadata checks before the final completion
            # receipt. Closing files is not proof of camera shutdown.
            handles.close()
            _inventory(capture_directory, receipt)
            envelope = {
                "schema": SCHEMA,
                "status": "CONTENT_VERIFIED_DIAGNOSTIC_ONLY",
                "domain": plan.domain,
                "source_contract_sha256": source_sha,
                "activation_request_sha256": plan.activation_request_sha256,
                "native_receipt_sha256": _digest(receipt),
                "dataset": _plain(dataset),
                "verification": _plain(verification),
                "latest_preview": latest.to_dict() if latest else None,
                "physical_authority": False,
                "m1_qualified": False,
                "received_hardware_accepted": False,
                "native_power_loss_qualification": "NOT_RUN",
            }
            payload = _json(envelope)
            pending = ingest_directory / "ingest-receipt.pending"
            final = ingest_directory / "ingest-receipt.json"
            _new_json(pending, payload)
            if stopped():
                raise CameraDatasetCancelled(
                    "Cancelled before ingest receipt commitment"
                )
            # Keep the sentinel through the exclusive final write and final
            # cancellation check. Retained verification rejects it, including
            # when complete-looking bytes survived a flush failure. Hardlink
            # publication is incompatible with Windows' directory rename pin.
            _new_json(final, payload)
            if stopped():
                raise CameraDatasetCancelled(
                    "Cancelled before ingest receipt commitment"
                )
            pending.unlink()
            return NativeCaptureIngestReceipt(
                dataset,
                verification,
                latest,
                final,
                hashlib.sha256(payload).hexdigest(),
                source_sha,
                plan.domain,
            )
