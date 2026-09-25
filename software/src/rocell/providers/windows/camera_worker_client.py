"""Bounded, identity-bound IPC to the Windows Media Foundation camera helper.

Construction/import is inert. Inventory is an explicit metadata-only action;
probe/capture require an external coordinator to authorize the exact immutable
request. This module does not issue permits or qualify physical operation.

The helper owns one source for one finite campaign. Native pixels travel only
in bounded newly-created binary files; stdout contains a small JSON receipt.
An absent/invalid receipt after dispatch is uncertain, never an implicit retry.
Media timestamps and host QPC values are not sensor/exposure timestamps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading
from typing import Callable, Generic, Mapping, NoReturn, Protocol, TypeVar, cast


PROTOCOL_SCHEMA = "rocell.windows_camera.v1"
LEGACY_IDENTITY_PROTOCOL_SCHEMA = "rocell.windows_camera_identity.v1"
IDENTITY_PROTOCOL_SCHEMA = "rocell.windows_camera_identity.v2"
MAX_IPC_BYTES = 256 * 1024
MAX_FRAME_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_FRAMES = 32
_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
_CONTROLS = frozenset(
    {"exposure", "gain", "white_balance", "brightness", "contrast", "saturation"}
)


class CameraWorkerError(RuntimeError):
    """A failed boundary, retaining whether physical effects are unresolved."""

    def __init__(self, code: str, detail: str, *, effect_uncertain: bool = False):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.effect_uncertain = effect_uncertain


def _fail(detail: str) -> NoReturn:
    raise CameraWorkerError("INVALID_CAMERA_CONTRACT", detail)


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        _fail(f"{name} must be an integer in [{low}, {high}]")
    return cast(int, value)


def _text(value: object, name: str, limit: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        _fail(f"{name} must be bounded nonempty text without control characters")
    return str(value)


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        _fail(f"{name} must be lowercase SHA-256")
    return str(value)


def _closed(value: object, names: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != names:
        _fail(f"{name} has missing or unknown fields")
    return value


def _items(value: object, maximum: int, name: str) -> list:
    if not isinstance(value, list) or len(value) > maximum:
        _fail(f"{name} must be a bounded array")
    return value


def _bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        _fail(f"{name} must be Boolean")
    return bool(value)


@dataclass(frozen=True)
class CameraEndpointBinding:
    """An already reviewed binding; an endpoint hash alone is not unit identity."""

    symbolic_link: str
    endpoint_sha256: str
    binding_sha256: str

    def __post_init__(self) -> None:
        _text(self.symbolic_link, "symbolic_link")
        _sha(self.endpoint_sha256, "endpoint_sha256")
        _sha(self.binding_sha256, "binding_sha256")
        if (
            hashlib.sha256(self.symbolic_link.encode("utf-8")).hexdigest()
            != self.endpoint_sha256
        ):
            _fail("endpoint hash does not bind the exact opaque symbolic link")


@dataclass(frozen=True)
class NativeCameraMode:
    width: int
    height: int
    fps_numerator: int
    fps_denominator: int
    subtype: str = "YUY2"
    stride_bytes: int | None = None

    def __post_init__(self) -> None:
        _integer(self.width, "width", 1, 16384)
        _integer(self.height, "height", 1, 16384)
        _integer(self.fps_numerator, "fps_numerator", 1, 1_000_000)
        _integer(self.fps_denominator, "fps_denominator", 1, 1_000_000)
        _text(self.subtype, "subtype", 64)
        if self.stride_bytes is not None:
            _integer(self.stride_bytes, "stride_bytes", -1_048_576, 1_048_576)
            if not self.stride_bytes:
                _fail("stride cannot be zero")

    def same_format(self, other: NativeCameraMode) -> bool:
        # Rational equality allows a driver to simplify 60000/1000 to 60/1.
        return (self.width, self.height, self.subtype) == (
            other.width,
            other.height,
            other.subtype,
        ) and self.fps_numerator * other.fps_denominator == other.fps_numerator * self.fps_denominator


@dataclass(frozen=True)
class CameraControlSetting:
    control_id: str
    value: int
    mode: str = "manual"

    def __post_init__(self) -> None:
        if self.control_id not in _CONTROLS or self.mode not in {"auto", "manual"}:
            _fail(
                "unsupported control identifier or mode; lens focus/aperture are manual"
            )
        _integer(self.value, "control value", -(2**31), 2**31 - 1)


@dataclass(frozen=True)
class CameraCampaignBudget:
    duration_ms: int = 10_000
    max_frames: int = 1
    max_frame_bytes: int = MAX_FRAME_BYTES
    max_total_bytes: int = 256 * 1024 * 1024

    def __post_init__(self) -> None:
        _integer(self.duration_ms, "duration_ms", 100, 300_000)
        _integer(self.max_frames, "max_frames", 1, MAX_FRAMES)
        _integer(self.max_frame_bytes, "max_frame_bytes", 1, MAX_FRAME_BYTES)
        _integer(self.max_total_bytes, "max_total_bytes", 1, MAX_TOTAL_BYTES)
        if self.max_frame_bytes > self.max_total_bytes:
            _fail("one-frame budget exceeds total budget")


@dataclass(frozen=True)
class CameraActivationRequest:
    """Exact internal request consumed by the qualified external coordinator.

    There is deliberately no `authorized` Boolean or frontend permit field.
    The authorizer must throw on stale/missing authority before returning.
    """

    campaign_id: str
    source_sha256: str
    operation: str
    binding: CameraEndpointBinding
    mode: NativeCameraMode | None
    controls: tuple[CameraControlSetting, ...]
    budget: CameraCampaignBudget
    helper_sha256: str
    arguments_sha256: str
    output_directory: str | None


@dataclass(frozen=True)
class PreparedCameraCampaign:
    """Filesystem-inert request snapshot, not executable authority.

    There is intentionally no public dispatch method accepting this object.
    An external coordinator can review ``request`` and compare the request
    subsequently supplied to the mandatory probe/capture authorizer. Arguments
    contain a private endpoint/path and are not a browser command interface.
    """

    request: CameraActivationRequest
    arguments: tuple[str, ...]


_CameraInput = TypeVar("_CameraInput")


def _snapshot_camera_input(value: object, expected: type[_CameraInput]) -> _CameraInput:
    """Copy and revalidate even frozen objects; reject subclasses/forged fields."""
    if type(value) is not expected or set(vars(value)) != {
        field.name for field in fields(expected)  # type: ignore[arg-type]
    }:
        _fail(f"exact {expected.__name__} input required")
    try:
        # All accepted inputs have scalar fields. No mutable nested object from
        # a caller is shared with an authorization or prepared request.
        return replace(value)  # type: ignore[type-var, return-value]
    except CameraWorkerError:
        raise
    except (TypeError, ValueError, AttributeError) as exc:
        raise CameraWorkerError(
            "INVALID_CAMERA_CONTRACT", f"invalid {expected.__name__} input"
        ) from exc


def _camera_plan_path(value: Path, name: str) -> Path:
    """Lexical validation only: do not stat, resolve, open or create a path."""
    path = Path(value)
    _text(str(path), name, 32_768)
    if not path.is_absolute() or ".." in path.parts:
        _fail(f"{name} must be an absolute path without parent traversal")
    return path


def _argument_sha256(arguments: tuple[str, ...]) -> str:
    return hashlib.sha256(
        json.dumps(arguments, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class CameraActivationAuthorizer(Protocol):
    def __call__(self, request: CameraActivationRequest) -> None:
        """Consume exact one-use authority, or raise without opening hardware."""


@dataclass(frozen=True)
class NativeProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes = b""
    timed_out: bool = False
    output_limit_exceeded: bool = False


class NativeProcessRunner(Protocol):
    def __call__(
        self,
        arguments: tuple[str, ...],
        timeout_seconds: float,
        output_limit_bytes: int,
    ) -> NativeProcessResult:
        """Run without a shell, applying deadline and combined stdout/stderr cap."""


def bounded_subprocess_runner(
    arguments: tuple[str, ...], timeout_seconds: float, output_limit_bytes: int
) -> NativeProcessResult:
    """Hard process deadline also bounds wedged driver open/shutdown calls.

    Process death cannot certify source cleanup: callers mark such outcomes
    uncertain. Pipe readers retain a shared finite byte budget, not communicate's
    unbounded allocation. No child window, inherited input or shell is used.
    """
    process = subprocess.Popen(
        arguments,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
    chunks = [bytearray(), bytearray()]
    guard = threading.Lock()
    overflow = threading.Event()

    def drain(index: int, pipe: object) -> None:
        try:
            while True:
                block = pipe.read(4096)  # type: ignore[attr-defined]
                if not block:
                    break
                with guard:
                    remaining = output_limit_bytes - sum(len(c) for c in chunks)
                    chunks[index].extend(block[: max(remaining, 0)])
                    if len(block) > remaining:
                        overflow.set()
                        process.kill()
                        break
        finally:
            pipe.close()  # type: ignore[attr-defined]

    readers = [
        threading.Thread(target=drain, args=(0, process.stdout), daemon=True),
        threading.Thread(target=drain, args=(1, process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(timeout=5)
    for reader in readers:
        reader.join(timeout=2)
    if any(reader.is_alive() for reader in readers):
        timed_out = True
    return NativeProcessResult(
        process.returncode,
        bytes(chunks[0]),
        bytes(chunks[1]),
        timed_out,
        overflow.is_set(),
    )


@dataclass(frozen=True)
class CameraCandidate:
    symbolic_link: str
    friendly_name: str

    @property
    def endpoint_sha256(self) -> str:
        return hashlib.sha256(self.symbolic_link.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NativeFrameMetadata:
    """Native wire observations only: no file was opened and no hash invented."""

    filename: str
    length_bytes: int
    stride_bytes: int
    row0_offset_bytes: int
    host_sequence: int
    media_timestamp_100ns: int
    host_arrival_qpc: int
    qpc_frequency: int
    discontinuity: bool | None


@dataclass(frozen=True)
class NativeFrameArtifact:
    filename: str
    length_bytes: int
    stride_bytes: int
    row0_offset_bytes: int
    host_sequence: int
    media_timestamp_100ns: int
    host_arrival_qpc: int
    qpc_frequency: int
    discontinuity: bool | None
    sha256: str


@dataclass(frozen=True)
class NativeControlObservation:
    control_id: str
    minimum: int
    maximum: int
    step: int
    default: int
    capability_flags: int
    value: int
    flags: int
    unit: str


@dataclass(frozen=True)
class NativeCameraReceipt:
    operation: str
    status: str
    reason_code: str | None
    selected_endpoint: str | None
    candidates: tuple[CameraCandidate, ...]
    modes: tuple[NativeCameraMode, ...]
    requested_mode: NativeCameraMode | None
    observed_mode: NativeCameraMode | None
    controls: tuple[NativeControlObservation, ...]
    frames: tuple[NativeFrameArtifact, ...]
    counts: Mapping[str, int]
    cleanup_confirmed: bool
    limitations: tuple[str, ...]

    @property
    def effect_uncertain(self) -> bool:
        """Failed shutdown is a hold, not evidence that camera ownership ceased."""
        return (
            self.counts["source_activation_attempts"] > 0 and not self.cleanup_confirmed
        )


@dataclass(frozen=True)
class NativeCameraReceiptMetadata:
    """Strict native receipt metadata, not verified sample bytes or device release.

    Frames intentionally have no SHA-256 field. The explicit artifact validator
    reparses original raw wire against the exact request before reading files.
    """

    operation: str
    status: str
    reason_code: str | None
    selected_endpoint: str | None
    candidates: tuple[CameraCandidate, ...]
    modes: tuple[NativeCameraMode, ...]
    requested_mode: NativeCameraMode | None
    observed_mode: NativeCameraMode | None
    controls: tuple[NativeControlObservation, ...]
    frames: tuple[NativeFrameMetadata, ...]
    counts: Mapping[str, int]
    cleanup_confirmed: bool
    limitations: tuple[str, ...]

    @property
    def effect_uncertain(self) -> bool:
        return (
            self.counts["source_activation_attempts"] > 0 and not self.cleanup_confirmed
        )


def _materialize_receipt(
    metadata: NativeCameraReceiptMetadata,
    output: tuple[CameraCampaignBudget, Path | None] | None,
) -> NativeCameraReceipt:
    """File-validation half of the legacy parser; never used by pure reopen."""
    frames = []
    for frame in metadata.frames:
        assert output is not None and output[1] is not None
        file = output[1] / frame.filename
        _plain_path(file, directory=False)
        if file.stat().st_size != frame.length_bytes:
            _fail("native frame size disagrees with receipt")
        # A growing input cannot turn a bounded frame check into an unbounded
        # read. Dataset ingestion subsequently rechecks retained sample bytes.
        digest = hashlib.sha256()
        remaining = frame.length_bytes
        with file.open("rb") as handle:
            while remaining:
                block = handle.read(min(1024 * 1024, remaining))
                if not block:
                    _fail("native frame size changed while hashing")
                digest.update(block)
                remaining -= len(block)
            if handle.read(1):
                _fail("native frame size changed while hashing")
        frames.append(NativeFrameArtifact(**asdict(frame), sha256=digest.hexdigest()))
    if metadata.status == "OK" and metadata.operation == "capture":
        assert output is not None and output[1] is not None
        if {path.name for path in output[1].iterdir()} != {f.filename for f in frames}:
            _fail("unreported artifacts in camera output directory")
    return NativeCameraReceipt(
        metadata.operation,
        metadata.status,
        metadata.reason_code,
        metadata.selected_endpoint,
        metadata.candidates,
        metadata.modes,
        metadata.requested_mode,
        metadata.observed_mode,
        metadata.controls,
        tuple(frames),
        metadata.counts,
        metadata.cleanup_confirmed,
        metadata.limitations,
    )


def validate_capture_artifacts(
    value: object, *, request: CameraActivationRequest
) -> NativeCameraReceipt:
    """Explicit bounded file check; raw wire and the original request are required.

    This does not open a camera, publish a dataset or qualify hardware. A caller
    cannot substitute a hand-built metadata object for original receipt wire.
    Parent ownership of the assigned directory and subsequent ingest verification
    remain necessary; these hashes alone are not commissioning authority.
    """
    request = _snapshot_camera_input(request, CameraActivationRequest)
    if request.operation != "capture":
        _fail("artifact validation requires an exact capture request")
    if type(request.campaign_id) is not str or not _ID.fullmatch(request.campaign_id):
        _fail("campaign_id must be a bounded identifier")
    for name in ("source_sha256", "helper_sha256", "arguments_sha256"):
        _sha(getattr(request, name), name)
    binding = _snapshot_camera_input(request.binding, CameraEndpointBinding)
    mode = _snapshot_camera_input(request.mode, NativeCameraMode)
    budget = _snapshot_camera_input(request.budget, CameraCampaignBudget)
    if mode.subtype != "YUY2" or mode.width % 2:
        _fail("capture currently supports native even-width YUY2 only")
    if mode.width * mode.height * 2 > budget.max_frame_bytes:
        _fail("requested packed frame already exceeds one-frame budget")
    if type(request.controls) is not tuple or len(request.controls) > len(_CONTROLS):
        _fail("controls must be an immutable bounded tuple")
    controls = tuple(
        _snapshot_camera_input(item, CameraControlSetting) for item in request.controls
    )
    if len({item.control_id for item in controls}) != len(controls):
        _fail("duplicate control settings")
    if type(request.output_directory) is not str:
        _fail("capture requires an assigned output directory")
    directory = _camera_plan_path(Path(request.output_directory), "output path")
    metadata = WindowsCameraWorkerClient._parse_receipt_metadata(
        value, "capture", binding, mode, (budget, directory), controls
    )
    if mode.stride_bytes is not None and (
        (
            metadata.observed_mode is not None
            and metadata.observed_mode.stride_bytes != mode.stride_bytes
        )
        or any(frame.stride_bytes != mode.stride_bytes for frame in metadata.frames)
    ):
        _fail("captured sample stride differs from the exact artifact request")
    return _materialize_receipt(metadata, (budget, directory))


def _parse_mode(value: object) -> NativeCameraMode:
    item = _closed(
        value,
        {
            "width",
            "height",
            "fps_numerator",
            "fps_denominator",
            "subtype",
            "stride_bytes",
        },
        "mode",
    )
    return NativeCameraMode(**item)


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON field")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    _fail(f"nonfinite JSON value {value}")


def _validate_metadata_sink(sink: Callable[[bytes], None] | None) -> None:
    if sink is not None and not callable(sink):
        _fail("metadata wire receipt sink must be callable")


def _retain_metadata_wire(value: dict, sink: Callable[[bytes], None] | None) -> None:
    """Retain exact decoded fields, not reconstructed cleanup observations.

    Canonicalization changes whitespace/key order only. The immutable bounded
    bytes are delivered after parsing and exit consistency; sink failure fails
    this call, never returns success or retries the metadata query.
    """
    if sink is not None:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(payload) > MAX_IPC_BYTES:
            _fail("canonical metadata wire receipt exceeds IPC budget")
        sink(payload)


def parse_camera_inventory_receipt(value: object) -> NativeCameraReceipt:
    """Pure metadata-only branch of the native-v1 strict receipt parser.

    No client is constructed and no path, runner or device is accessed. Wire
    callers must first enforce their JSON byte/nesting bounds. Activation,
    modes, controls and sample artifacts are forbidden in inventory receipts.
    """
    return WindowsCameraWorkerClient._parse_receipt(
        value, "inventory", None, None, None, ()
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _plain_path(path: Path, *, directory: bool) -> None:
    if not path.is_absolute():
        _fail("helper and output paths must be absolute")
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(
            info, "st_file_attributes", 0
        ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
            _fail("helper/output paths cannot traverse reparse points or symlinks")
    if directory and not path.is_dir():
        _fail("output directory must exist")
    if not directory and not path.is_file():
        _fail("helper/frame must be a regular file")


_IdentityValue = TypeVar("_IdentityValue")
_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_IDENTITY_REASONS = frozenset(
    {
        "NONE",
        "NOT_REQUESTED",
        "API_FAILURE",
        "WRONG_PROPERTY_TYPE",
        "MALFORMED_VALUE",
        "BYTE_LIMIT",
        "CANCELLED",
        "DEADLINE",
        "CLOCK_CHANGED",
        "CALL_LIMIT",
    }
)
_CHAIN_ENDS = frozenset(
    {
        "NOT_REQUESTED",
        "REACHED_OBSERVED_ROOT",
        "PARENT_UNAVAILABLE",
        "PARENT_CYCLE",
        "DEPTH_LIMIT",
        "CANCELLED",
        "DEADLINE",
        "CLOCK_CHANGED",
        "CALL_LIMIT",
    }
)


@dataclass(frozen=True)
class NativeIdentityError:
    reason: str
    domain: str
    native_code: int


@dataclass(frozen=True)
class NativeIdentityObservation(Generic[_IdentityValue]):
    availability: str
    value: _IdentityValue | None
    error: NativeIdentityError

    @property
    def observed(self) -> bool:
        return self.availability == "OBSERVED"


@dataclass(frozen=True)
class NativeWindowsNodeMetadata:
    devnode: int
    instance_id: NativeIdentityObservation[str]
    container_id: NativeIdentityObservation[str]
    location_paths: NativeIdentityObservation[tuple[str, ...]]


@dataclass(frozen=True)
class NativeWindowsDriverMetadata:
    """Reported installed-driver properties of the exact endpoint devnode only."""

    devnode: int
    provider: NativeIdentityObservation[str]
    service: NativeIdentityObservation[str]
    version: NativeIdentityObservation[str]
    inf_path: NativeIdentityObservation[str]


@dataclass(frozen=True)
class NativeCameraIdentityReceipt:
    """OS metadata only. Exact mapping still is not unique-unit qualification."""

    requested_endpoint: str
    endpoint_sha256: str
    devnode: NativeIdentityObservation[int]
    interface_path: NativeIdentityObservation[str]
    cleanup_errors: tuple[NativeIdentityError, ...]
    device: NativeWindowsNodeMetadata | None
    parents: tuple[NativeWindowsNodeMetadata, ...]
    observed_root: NativeIdentityObservation[int]
    chain_end: str
    chain_error: NativeIdentityError
    api_calls: int
    observed_property_bytes: int
    limits: Mapping[str, int]
    # Historical v1 has no driver data. Never synthesize an unavailable OS
    # observation or silently replace the original legacy receipt schema.
    driver: NativeWindowsDriverMetadata | None = None
    protocol_schema: str = LEGACY_IDENTITY_PROTOCOL_SCHEMA

    @property
    def exact_endpoint_observed(self) -> bool:
        """String equality only; no same-name or case-normalizing fallback."""
        return (
            self.devnode.observed
            and self.interface_path.observed
            and self.interface_path.value == self.requested_endpoint
            and not self.cleanup_errors
        )

    @property
    def physical_authority(self) -> bool:
        return False


def _identity_error(value: object) -> NativeIdentityError:
    item = _closed(value, {"reason", "domain", "native_code"}, "identity error")
    reason, domain = item["reason"], item["domain"]
    if not isinstance(reason, str) or reason not in _IDENTITY_REASONS:
        _fail("unregistered identity unavailable reason")
    if not isinstance(domain, str) or domain not in {
        "NONE",
        "WIN32",
        "CONFIGURATION_MANAGER",
        "CONTRACT",
    }:
        _fail("unregistered identity error domain")
    code = _integer(item["native_code"], "native error code", 0, 2**32 - 1)
    if reason in {"NONE", "NOT_REQUESTED"}:
        if domain != "NONE" or code != 0:
            _fail("absent identity error contains native failure data")
    elif reason == "API_FAILURE":
        if domain not in {"WIN32", "CONFIGURATION_MANAGER"}:
            _fail("identity API failure lost its native error domain")
    elif domain != "CONTRACT" or code != 0:
        _fail("identity contract error cannot masquerade as an OS result")
    return NativeIdentityError(reason, domain, code)


def _identity_observation(
    value: object, decode: Callable[[object], _IdentityValue]
) -> NativeIdentityObservation[_IdentityValue]:
    item = _closed(value, {"availability", "value", "error"}, "identity observation")
    error = _identity_error(item["error"])
    if item["availability"] == "OBSERVED":
        if error.reason != "NONE" or item["value"] is None:
            _fail("observed identity value is missing or unavailable")
        return NativeIdentityObservation("OBSERVED", decode(item["value"]), error)
    if (
        item["availability"] != "UNAVAILABLE"
        or item["value"] is not None
        or error.reason == "NONE"
    ):
        _fail("unavailable identity observation contains an invented value")
    return NativeIdentityObservation("UNAVAILABLE", None, error)


def _metadata_text(value: object) -> str:
    text = _text(value, "Windows metadata text", 4096)
    if len(text.encode("utf-16-le")) // 2 > 1024:
        _fail("Windows metadata string exceeds its UTF-16 budget")
    return text


def _metadata_guid(value: object) -> str:
    if not isinstance(value, str) or _GUID.fullmatch(value) is None:
        _fail("container ID must be an observed canonical GUID")
    return str(value)


def _metadata_paths(value: object) -> tuple[str, ...]:
    return tuple(_metadata_text(path) for path in _items(value, 16, "location paths"))


def _metadata_node(value: object) -> NativeWindowsNodeMetadata:
    item = _closed(
        value,
        {"devnode", "instance_id", "container_id", "location_paths"},
        "Windows metadata node",
    )
    return NativeWindowsNodeMetadata(
        _integer(item["devnode"], "devnode", 0, 2**32 - 1),
        _identity_observation(item["instance_id"], _metadata_text),
        _identity_observation(item["container_id"], _metadata_guid),
        _identity_observation(item["location_paths"], _metadata_paths),
    )


def _metadata_driver(value: object) -> NativeWindowsDriverMetadata:
    item = _closed(
        value,
        {"devnode", "provider", "service", "version", "inf_path"},
        "endpoint driver metadata",
    )
    return NativeWindowsDriverMetadata(
        _integer(item["devnode"], "driver devnode", 0, 2**32 - 1),
        _identity_observation(item["provider"], _metadata_text),
        _identity_observation(item["service"], _metadata_text),
        _identity_observation(item["version"], _metadata_text),
        _identity_observation(item["inf_path"], _metadata_text),
    )


def parse_camera_identity_receipt(
    value: object, *, expected_endpoint: str, duration_ms: int, max_parent_nodes: int
) -> NativeCameraIdentityReceipt:
    """Strict versioned receipt parser shared by injected/native identity tests."""
    _text(expected_endpoint, "expected endpoint")
    _integer(duration_ms, "duration_ms", 100, 30_000)
    _integer(max_parent_nodes, "max_parent_nodes", 0, 16)
    if not isinstance(value, dict) or value.get("schema") not in (
        LEGACY_IDENTITY_PROTOCOL_SCHEMA,
        IDENTITY_PROTOCOL_SCHEMA,
    ):
        _fail("wrong identity receipt version")
    schema = value["schema"]
    root = _closed(
        value,
        {
            "schema",
            "status",
            "requested_endpoint",
            "mapping",
            "device",
            "parents",
            "observed_root",
            "chain_end",
            "chain_error",
            "api_calls",
            "observed_property_bytes",
            "limits",
            "provenance",
            "camera_activation_count",
            "physical_authority",
        }
        | ({"driver"} if schema == IDENTITY_PROTOCOL_SCHEMA else set()),
        "camera identity receipt",
    )
    if (
        root["status"] != "METADATA_ONLY"
        or root["provenance"] != "WINDOWS_SETUPAPI_CONFIGURATION_MANAGER_METADATA"
    ):
        _fail("wrong identity receipt version, status or provenance")
    if (
        root["physical_authority"] is not False
        or type(root["camera_activation_count"]) is not int
        or root["camera_activation_count"] != 0
    ):
        raise CameraWorkerError(
            "CAMERA_IDENTITY_AUTHORITY_VIOLATION",
            "metadata receipt reports unexpected camera authority/effects",
            effect_uncertain=True,
        )
    if root["requested_endpoint"] != expected_endpoint:
        _fail("identity result belongs to another opaque endpoint")
    expected_limits = {
        "max_parent_nodes": max_parent_nodes,
        "max_property_bytes": 16 * 1024,
        "max_total_property_bytes": 128 * 1024,
        "max_instance_chars": 1024,
        "max_location_paths": 16,
        "duration_ms": duration_ms,
    }
    limits = _closed(root["limits"], set(expected_limits), "identity limits")
    for key, expected in expected_limits.items():
        if type(limits[key]) is not int or limits[key] != expected:
            _fail("identity worker changed an approved metadata budget")
    mapping = _closed(
        root["mapping"],
        {"devnode", "interface_path", "cleanup_errors"},
        "endpoint mapping",
    )
    devnode = _identity_observation(
        mapping["devnode"], lambda v: _integer(v, "devnode", 0, 2**32 - 1)
    )
    interface_path = _identity_observation(
        mapping["interface_path"], lambda v: _text(v, "observed interface path")
    )
    if devnode.observed != interface_path.observed:
        _fail("identity mapping observed only half of its endpoint/devnode pair")
    cleanup = tuple(
        _identity_error(error)
        for error in _items(mapping["cleanup_errors"], 2, "metadata cleanup errors")
    )
    if any(
        error.reason != "API_FAILURE" or error.domain != "WIN32" for error in cleanup
    ):
        _fail("metadata cleanup errors are not observed SetupAPI failures")
    device = None if root["device"] is None else _metadata_node(root["device"])
    driver = (
        _metadata_driver(root["driver"])
        if schema == IDENTITY_PROTOCOL_SCHEMA and root["driver"] is not None
        else None
    )
    if schema == IDENTITY_PROTOCOL_SCHEMA and (
        (driver is None) != (device is None)
        or (driver is not None and driver.devnode != devnode.value)
    ):
        _fail("driver metadata is detached from the exact endpoint device")
    parents = tuple(
        _metadata_node(node)
        for node in _items(root["parents"], max_parent_nodes, "parent chain")
    )
    observed_root = _identity_observation(
        root["observed_root"], lambda v: _integer(v, "root devnode", 0, 2**32 - 1)
    )
    chain_end = root["chain_end"]
    if not isinstance(chain_end, str) or chain_end not in _CHAIN_ENDS:
        _fail("unregistered identity chain termination")
    chain_error = _identity_error(root["chain_error"])
    api_calls = _integer(root["api_calls"], "identity API-seam calls", 0, 128)
    property_bytes = _integer(
        root["observed_property_bytes"], "observed property bytes", 0, 128 * 1024
    )
    if not devnode.observed and (
        device is not None or parents or observed_root.observed
    ):
        _fail("unmapped endpoint contains invented node observations")
    if device is not None and device.devnode != devnode.value:
        _fail("device metadata differs from the mapped endpoint node")
    if parents and device is None:
        _fail("parent chain is detached from its selected device")
    nodes = ([] if device is None else [device]) + list(parents)
    if len({node.devnode for node in nodes}) != len(nodes):
        _fail("identity parent chain repeats a devnode")
    minimum_node_calls = 1 + sum(
        1
        + int(node.container_id.error.reason != "BYTE_LIMIT")
        + int(node.location_paths.error.reason != "BYTE_LIMIT")
        for node in nodes
    )
    driver_fields = (
        (driver.provider, driver.service, driver.version, driver.inf_path)
        if driver is not None
        else ()
    )
    minimum_node_calls += sum(
        item.error.reason not in {"NOT_REQUESTED", "BYTE_LIMIT"}
        for item in driver_fields
    )
    if driver_fields:
        unrequested = False
        for item in driver_fields:
            if item.error.reason == "NOT_REQUESTED":
                unrequested = True
            elif unrequested:
                _fail("driver queries skipped an earlier fixed property")
        if (
            unrequested
            and interface_path.value == expected_endpoint
            and not cleanup
            and chain_end
            not in {"CANCELLED", "DEADLINE", "CLOCK_CHANGED", "CALL_LIMIT"}
        ):
            _fail("completed exact endpoint query omitted driver properties")
        if any(item.error.reason != "NOT_REQUESTED" for item in driver_fields) and (
            interface_path.value != expected_endpoint or cleanup
        ):
            _fail("driver query ran without a clean exact endpoint mapping")
    if nodes and api_calls < minimum_node_calls:
        _fail("identity node observations exceed API-seam accounting")
    if devnode.observed and api_calls == 0:
        _fail("observed mapping has no metadata API invocation")
    # Accepted raw bytes include malformed properties too, so only a lower
    # bound can be derived from the successfully decoded GUID/MULTI_SZ values.
    minimum_property_bytes = sum(
        (16 if node.container_id.observed else 0)
        + (
            max(
                4,
                2
                + sum(
                    len(path.encode("utf-16-le")) + 2
                    for path in node.location_paths.value or ()
                ),
            )
            if node.location_paths.observed
            else 0
        )
        for node in nodes
    )
    minimum_property_bytes += sum(
        len(item.value.encode("utf-16-le")) + 2
        for item in driver_fields
        if item.observed and item.value is not None
    )
    if property_bytes < minimum_property_bytes:
        _fail("observed properties exceed accepted raw byte accounting")
    if chain_end == "NOT_REQUESTED" and (
        devnode.observed or chain_error.reason != "NOT_REQUESTED"
    ):
        _fail(
            "unrequested parent chain contains completed mapping or invented termination"
        )
    if chain_end == "REACHED_OBSERVED_ROOT":
        if (
            not nodes
            or not observed_root.observed
            or nodes[-1].devnode != observed_root.value
            or chain_error.reason not in {"NONE", "NOT_REQUESTED"}
        ):
            _fail("parent chain did not reach the independently observed root")
    if (
        chain_end in {"CANCELLED", "DEADLINE", "CLOCK_CHANGED", "CALL_LIMIT"}
        and chain_error.reason != chain_end
    ):
        _fail("interrupted identity query lost its exact termination reason")
    if chain_end == "DEPTH_LIMIT" and (
        device is None
        or len(parents) != max_parent_nodes
        or chain_error.reason != "NOT_REQUESTED"
    ):
        _fail("parent-depth stop does not match the requested bound")
    if chain_end == "PARENT_CYCLE" and chain_error.reason != "MALFORMED_VALUE":
        _fail("parent-cycle result lacks its retained error")
    if chain_end == "PARENT_UNAVAILABLE" and chain_error.reason == "NONE":
        _fail("missing parent was reported without an unavailable reason")
    from types import MappingProxyType

    return NativeCameraIdentityReceipt(
        expected_endpoint,
        hashlib.sha256(expected_endpoint.encode("utf-8")).hexdigest(),
        devnode,
        interface_path,
        cleanup,
        device,
        parents,
        observed_root,
        chain_end,
        chain_error,
        api_calls,
        property_bytes,
        MappingProxyType(dict(limits)),
        driver,
        schema,
    )


class WindowsCameraWorkerClient:
    """One invocation per operation. No discovery, hash reads or I/O on init."""

    def __init__(
        self,
        native_executable: Path,
        expected_sha256: str,
        *,
        runner: NativeProcessRunner = bounded_subprocess_runner,
    ) -> None:
        self.native_executable = Path(native_executable)
        self.expected_sha256 = _sha(expected_sha256, "helper_sha256")
        self.runner = runner

    def _registered_arguments(
        self, operation: str, extra: tuple[str, ...]
    ) -> tuple[str, ...]:
        try:
            _plain_path(self.native_executable, directory=False)
            if _hash_file(self.native_executable) != self.expected_sha256:
                raise CameraWorkerError(
                    "CAMERA_HELPER_HASH_MISMATCH",
                    "helper differs from registered build",
                )
        except OSError as exc:
            raise CameraWorkerError(
                "CAMERA_HELPER_UNAVAILABLE",
                "registered native helper is missing or unreadable",
            ) from exc
        return (str(self.native_executable), operation, *extra)

    def enumerate_metadata(
        self,
        *,
        duration_ms: int = 5000,
        wire_receipt_sink: Callable[[bytes], None] | None = None,
    ) -> NativeCameraReceipt:
        """Explicit MF enumeration only; never ActivateObject/mode probing."""
        _integer(duration_ms, "duration_ms", 100, 30_000)
        _validate_metadata_sink(wire_receipt_sink)
        arguments = self._registered_arguments(
            "inventory", ("--max-ms", str(duration_ms))
        )
        return self._invoke(
            arguments, duration_ms, None, None, None, (), wire_receipt_sink
        )

    def resolve_identity_metadata(
        self,
        candidate: CameraCandidate,
        *,
        duration_ms: int = 5000,
        max_parent_nodes: int = 8,
        wire_receipt_sink: Callable[[bytes], None] | None = None,
    ) -> NativeCameraIdentityReceipt:
        """Explicit SetupAPI/CM metadata query for an enumerated candidate.

        This separate receipt version does not open a camera. It precedes a
        reviewed unit binding and never manufactures a serial/USB speed. Call
        only after explicit operator metadata action, never page/status refresh.
        """
        if not isinstance(candidate, CameraCandidate):
            _fail("identity lookup requires a server-resolved camera candidate")
        endpoint = _text(candidate.symbolic_link, "candidate endpoint")
        _integer(duration_ms, "identity duration_ms", 100, 30_000)
        _integer(max_parent_nodes, "max_parent_nodes", 0, 16)
        _validate_metadata_sink(wire_receipt_sink)
        arguments = self._registered_arguments(
            "identity",
            (
                "--endpoint",
                endpoint,
                "--max-ms",
                str(duration_ms),
                "--max-parents",
                str(max_parent_nodes),
            ),
        )
        try:
            result = self.runner(arguments, duration_ms / 1000 + 5, MAX_IPC_BYTES)
            if result.timed_out or result.output_limit_exceeded:
                raise CameraWorkerError(
                    (
                        "CAMERA_IDENTITY_TIMEOUT"
                        if result.timed_out
                        else "CAMERA_IPC_LIMIT"
                    ),
                    "metadata query did not return a bounded receipt; no automatic retry",
                )
            if len(result.stdout) + len(result.stderr) > MAX_IPC_BYTES:
                _fail("identity result exceeded IPC byte budget")
            raw = json.loads(
                result.stdout.decode("utf-8"),
                object_pairs_hook=_no_duplicate_keys,
                parse_constant=_reject_nonfinite,
            )
            receipt = parse_camera_identity_receipt(
                raw,
                expected_endpoint=endpoint,
                duration_ms=duration_ms,
                max_parent_nodes=max_parent_nodes,
            )
            if result.returncode != 0:
                _fail("identity worker exit disagrees with metadata receipt")
            _retain_metadata_wire(raw, wire_receipt_sink)
            return receipt
        except CameraWorkerError:
            raise
        except Exception as exc:
            raise CameraWorkerError(
                "CAMERA_IDENTITY_RECEIPT_INVALID",
                "native identity query failed or returned invalid bounded metadata",
            ) from exc

    def prepare_probe(
        self,
        binding: CameraEndpointBinding,
        *,
        source_sha256: str,
        campaign_id: str,
        budget: CameraCampaignBudget,
    ) -> PreparedCameraCampaign:
        """Plan exact mode/control inspection without I/O or authorization."""
        return self._prepare_campaign(
            "probe", binding, source_sha256, campaign_id, budget, None, (), None
        )

    def prepare_capture(
        self,
        binding: CameraEndpointBinding,
        mode: NativeCameraMode,
        output_directory: Path,
        *,
        source_sha256: str,
        campaign_id: str,
        budget: CameraCampaignBudget,
        controls: tuple[CameraControlSetting, ...] = (),
    ) -> PreparedCameraCampaign:
        """Plan a finite burst; helper/output existence is checked only on execution.

        The caller assigns a fresh absolute output path. Preparation neither
        reserves that path nor promises its availability or sufficient space.
        """
        return self._prepare_campaign(
            "capture",
            binding,
            source_sha256,
            campaign_id,
            budget,
            mode,
            controls,
            output_directory,
        )

    def probe(
        self,
        binding: CameraEndpointBinding,
        *,
        source_sha256: str,
        campaign_id: str,
        budget: CameraCampaignBudget,
        authorize: CameraActivationAuthorizer,
    ) -> NativeCameraReceipt:
        """Activate once to inspect native modes/controls, then release source."""
        return self._campaign(
            self.prepare_probe(
                binding,
                source_sha256=source_sha256,
                campaign_id=campaign_id,
                budget=budget,
            ),
            authorize,
        )

    def capture(
        self,
        binding: CameraEndpointBinding,
        mode: NativeCameraMode,
        output_directory: Path,
        *,
        source_sha256: str,
        campaign_id: str,
        budget: CameraCampaignBudget,
        authorize: CameraActivationAuthorizer,
        controls: tuple[CameraControlSetting, ...] = (),
    ) -> NativeCameraReceipt:
        """Finite native YUY2 frame burst; not a perpetual preview service."""
        return self._campaign(
            self.prepare_capture(
                binding,
                mode,
                output_directory,
                source_sha256=source_sha256,
                campaign_id=campaign_id,
                budget=budget,
                controls=controls,
            ),
            authorize,
        )

    def _prepare_campaign(
        self,
        operation: str,
        binding: CameraEndpointBinding,
        source_sha256: str,
        campaign_id: str,
        budget: CameraCampaignBudget,
        mode: NativeCameraMode | None,
        controls: tuple[CameraControlSetting, ...],
        output_directory: Path | None,
    ) -> PreparedCameraCampaign:
        """Single pure request/argument builder for planning and execution."""
        _sha(source_sha256, "source_sha256")
        if type(campaign_id) is not str or not _ID.fullmatch(campaign_id):
            _fail("campaign_id must be a bounded identifier")
        binding = _snapshot_camera_input(binding, CameraEndpointBinding)
        budget = _snapshot_camera_input(budget, CameraCampaignBudget)
        if type(controls) is not tuple or len(controls) > len(_CONTROLS):
            _fail("controls must be an immutable bounded tuple")
        controls = tuple(
            _snapshot_camera_input(item, CameraControlSetting) for item in controls
        )
        if len({c.control_id for c in controls}) != len(controls):
            _fail("duplicate control settings")
        executable = _camera_plan_path(self.native_executable, "helper path")
        helper_sha256 = _sha(self.expected_sha256, "helper_sha256")
        if operation == "probe":
            if mode is not None or controls or output_directory is not None:
                _fail("probe cannot request a mode, controls or output directory")
        elif operation == "capture":
            mode = _snapshot_camera_input(mode, NativeCameraMode)
            if mode.subtype != "YUY2" or mode.width % 2:
                _fail("capture currently supports native even-width YUY2 only")
            if mode.width * mode.height * 2 > budget.max_frame_bytes:
                _fail("requested packed frame already exceeds one-frame budget")
            if output_directory is None:
                _fail("capture requires an assigned output directory")
            output_directory = _camera_plan_path(output_directory, "output path")
        else:
            _fail("only probe/capture campaigns can be prepared")
        extra: tuple[str, ...] = (
            "--endpoint",
            binding.symbolic_link,
            "--max-ms",
            str(budget.duration_ms),
        )
        if mode is not None:
            extra += (
                "--width",
                str(mode.width),
                "--height",
                str(mode.height),
                "--fps-n",
                str(mode.fps_numerator),
                "--fps-d",
                str(mode.fps_denominator),
                "--frames",
                str(budget.max_frames),
                "--frame-bytes",
                str(budget.max_frame_bytes),
                "--total-bytes",
                str(budget.max_total_bytes),
                "--output",
                str(output_directory),
            )
            if controls:
                extra += (
                    "--controls",
                    ";".join(f"{c.control_id},{c.value},{c.mode}" for c in controls),
                )
        arguments = (str(executable), operation, *extra)
        request = CameraActivationRequest(
            campaign_id,
            source_sha256,
            operation,
            binding,
            mode,
            controls,
            budget,
            helper_sha256,
            _argument_sha256(arguments),
            str(output_directory) if output_directory is not None else None,
        )
        return PreparedCameraCampaign(request, arguments)

    def _campaign(
        self, plan: PreparedCameraCampaign, authorize: CameraActivationAuthorizer
    ) -> NativeCameraReceipt:
        """Internal only: plan anew, preflight, then consume exact authority once."""
        if not callable(authorize):
            raise CameraWorkerError(
                "CAMERA_AUTHORIZATION_REQUIRED",
                "qualified coordinator authorizer required",
            )
        request = plan.request
        directory = (
            Path(request.output_directory)
            if request.output_directory is not None
            else None
        )
        if directory is not None:
            _plain_path(directory, directory=True)
            if any(directory.iterdir()):
                _fail("capture requires a new empty output directory; never overwrite")
            if shutil.disk_usage(directory).free < request.budget.max_total_bytes:
                _fail("free disk cannot accommodate the approved camera byte budget")
        arguments = self._registered_arguments(request.operation, plan.arguments[2:])
        if (
            arguments != plan.arguments
            or self.expected_sha256 != request.helper_sha256
            or _argument_sha256(arguments) != request.arguments_sha256
        ):
            _fail("registered helper/arguments changed after preparation")
        # Save a value snapshot, not references to nested frozen objects: Python
        # callbacks can deliberately bypass dataclass immutability. Such a
        # mutation must not change receipt validation after consuming authority.
        reviewed = asdict(request)
        # The caller consumes exact authority here. Denial means zero dispatches.
        authorize(request)
        _snapshot_camera_input(request, CameraActivationRequest)
        if asdict(request) != reviewed:
            _fail("authorization changed the exact prepared camera request")
        # Equal-looking dictionaries or subclasses must not replace typed
        # nested inputs. Rebuilding is pure and also catches registration
        # mutation inside the external callback before any runner invocation.
        checked = self._prepare_campaign(
            request.operation,
            request.binding,
            request.source_sha256,
            request.campaign_id,
            request.budget,
            request.mode,
            request.controls,
            directory,
        )
        if checked.arguments != arguments or checked.request != request:
            _fail("authorization changed the exact prepared camera request")
        return self._invoke(
            arguments,
            request.budget.duration_ms,
            request.binding,
            request.mode,
            (request.budget, directory),
            request.controls,
        )

    def _invoke(
        self,
        arguments: tuple[str, ...],
        duration_ms: int,
        binding: CameraEndpointBinding | None,
        requested_mode: NativeCameraMode | None,
        output: tuple[CameraCampaignBudget, Path | None] | None,
        requested_controls: tuple[CameraControlSetting, ...],
        wire_receipt_sink: Callable[[bytes], None] | None = None,
    ) -> NativeCameraReceipt:
        activation = arguments[1] != "inventory"
        try:
            result = self.runner(arguments, duration_ms / 1000 + 5, MAX_IPC_BYTES)
            if result.timed_out or result.output_limit_exceeded:
                raise CameraWorkerError(
                    (
                        "CAMERA_WORKER_DEADLINE"
                        if result.timed_out
                        else "CAMERA_IPC_LIMIT"
                    ),
                    "worker did not return a bounded cleanup receipt",
                    effect_uncertain=activation,
                )
            if len(result.stdout) + len(result.stderr) > MAX_IPC_BYTES:
                _fail("worker output exceeded IPC bound")
            raw = json.loads(
                result.stdout.decode("utf-8"),
                object_pairs_hook=_no_duplicate_keys,
                parse_constant=_reject_nonfinite,
            )
            receipt = self._parse_receipt(
                raw, arguments[1], binding, requested_mode, output, requested_controls
            )
            if (receipt.status == "OK") != (result.returncode == 0):
                _fail("process exit disagrees with receipt status")
            if wire_receipt_sink is not None:
                if arguments[1] != "inventory":
                    _fail("wire sink is reserved for explicit metadata inventory")
                _retain_metadata_wire(raw, wire_receipt_sink)
            return receipt
        except CameraWorkerError as exc:
            if activation:
                exc.effect_uncertain = True
            raise
        except Exception as exc:
            raise CameraWorkerError(
                "CAMERA_WORKER_RECEIPT_INVALID",
                "worker failed or returned invalid evidence; no automatic retry",
                effect_uncertain=activation,
            ) from exc

    @staticmethod
    def _parse_receipt(
        value: object,
        operation: str,
        binding: CameraEndpointBinding | None,
        requested_mode: NativeCameraMode | None,
        output: tuple[CameraCampaignBudget, Path | None] | None,
        requested_controls: tuple[CameraControlSetting, ...],
    ) -> NativeCameraReceipt:
        metadata = WindowsCameraWorkerClient._parse_receipt_metadata(
            value, operation, binding, requested_mode, output, requested_controls
        )
        return _materialize_receipt(metadata, output)

    @staticmethod
    def _parse_receipt_metadata(
        value: object,
        operation: str,
        binding: CameraEndpointBinding | None,
        requested_mode: NativeCameraMode | None,
        output: tuple[CameraCampaignBudget, Path | None] | None,
        requested_controls: tuple[CameraControlSetting, ...],
    ) -> NativeCameraReceiptMetadata:
        """Parse all native wire claims without reading an output path or frame."""
        root = _closed(
            value,
            {
                "schema",
                "operation",
                "status",
                "reason_code",
                "selected_endpoint",
                "devices",
                "modes",
                "requested_mode",
                "observed_mode",
                "controls",
                "frames",
                "counts",
                "cleanup",
                "limitations",
            },
            "receipt",
        )
        if (
            root["schema"] != PROTOCOL_SCHEMA
            or root["operation"] != operation
            or root["status"] not in {"OK", "FAILED"}
        ):
            _fail("wrong schema, operation, or status")
        reason = root["reason_code"]
        if reason is not None:
            _text(reason, "reason_code", 96)
        if (root["status"] == "OK") != (reason is None):
            _fail("status and reason disagree")
        endpoint = root["selected_endpoint"]
        if endpoint != (binding.symbolic_link if binding else None):
            _fail("worker selected a different endpoint")
        candidates = []
        for item in _items(root["devices"], 64, "devices"):
            item = _closed(item, {"symbolic_link", "friendly_name"}, "device")
            candidates.append(
                CameraCandidate(
                    _text(item["symbolic_link"], "symbolic_link"),
                    _text(item["friendly_name"], "friendly_name", 1024),
                )
            )
        if len({c.symbolic_link for c in candidates}) != len(candidates):
            _fail("ambiguous duplicate endpoint")
        modes = tuple(_parse_mode(m) for m in _items(root["modes"], 128, "modes"))
        sent = (
            None
            if root["requested_mode"] is None
            else _parse_mode(root["requested_mode"])
        )
        observed = (
            None
            if root["observed_mode"] is None
            else _parse_mode(root["observed_mode"])
        )
        if (sent is None) != (requested_mode is None) or (
            sent and requested_mode and not sent.same_format(requested_mode)
        ):
            _fail("requested format does not match dispatched campaign")
        if root["status"] == "OK" and requested_mode is not None:
            if observed is None or not observed.same_format(requested_mode):
                _fail("negotiated media format differs from requested format")
            if not any(m.same_format(observed) for m in modes):
                _fail("selected format was not enumerated as native")
        counts = _closed(
            root["counts"],
            {
                "source_activation_attempts",
                "source_opened",
                "control_set_attempts",
                "samples_received",
                "frames_written",
                "source_shutdown_attempts",
            },
            "counts",
        )
        for key, count in counts.items():
            _integer(count, key, 0, 100_000)
        if operation == "inventory" and any(counts.values()):
            raise CameraWorkerError(
                "INVALID_CAMERA_CONTRACT",
                "metadata inventory reports device effects",
                effect_uncertain=True,
            )
        for key in (
            "source_activation_attempts",
            "source_opened",
            "source_shutdown_attempts",
        ):
            if counts[key] > 1:
                _fail("multiple activation/shutdown attempts")
        if counts["source_opened"] > counts["source_activation_attempts"] or counts[
            "control_set_attempts"
        ] > len(requested_controls):
            _fail("unexpected device effect counts")
        if counts["source_shutdown_attempts"] > counts["source_activation_attempts"]:
            _fail("shutdown count exceeds activation attempts")
        if counts["source_opened"] and not any(
            candidate.symbolic_link == endpoint for candidate in candidates
        ):
            _fail("opened endpoint was absent from the worker inventory")
        cleanup = _closed(
            root["cleanup"],
            {
                "source_shutdown_hr",
                "source_released",
                "mf_shutdown_hr",
                "com_uninitialized",
            },
            "cleanup",
        )
        for key in ("source_shutdown_hr", "mf_shutdown_hr"):
            if cleanup[key] is not None:
                _integer(cleanup[key], key, -(2**31), 2**31 - 1)
        # Validate both fields even for a failed receipt. Short-circuiting the
        # validators would let malformed COM evidence hide behind release=False.
        source_released = _bool(cleanup["source_released"], "source_released")
        com_uninitialized = _bool(cleanup["com_uninitialized"], "com_uninitialized")
        confirmed = (
            source_released
            and com_uninitialized
            and cleanup["mf_shutdown_hr"] == 0
            and (
                counts["source_activation_attempts"] == 0
                or (
                    counts["source_shutdown_attempts"] == 1
                    and cleanup["source_shutdown_hr"] == 0
                )
            )
        )
        if root["status"] == "OK" and not confirmed:
            _fail("successful operation lacks confirmed cleanup")
        if operation == "inventory":
            if (
                any(counts.values())
                or modes
                or observed
                or root["controls"]
                or root["frames"]
            ):
                raise CameraWorkerError(
                    "INVALID_CAMERA_CONTRACT",
                    "metadata inventory reports activation/capture effects",
                    effect_uncertain=any(counts.values()),
                )
        elif root["status"] == "OK" and (
            counts["source_opened"] != 1 or counts["source_activation_attempts"] != 1
        ):
            _fail("successful probe/capture lacks one source open")
        if operation == "probe" and (
            counts["control_set_attempts"]
            or counts["samples_received"]
            or counts["frames_written"]
        ):
            _fail("probe cannot change controls or request frames")
        if root["status"] == "OK" and counts["control_set_attempts"] != len(
            requested_controls
        ):
            _fail("successful campaign did not account for every control write")
        controls = []
        for item in _items(root["controls"], 6, "controls"):
            item = _closed(
                item,
                {
                    "control_id",
                    "minimum",
                    "maximum",
                    "step",
                    "default",
                    "capability_flags",
                    "value",
                    "flags",
                    "unit",
                },
                "control",
            )
            if item["control_id"] not in _CONTROLS:
                _fail("unknown control observation")
            for key in ("minimum", "maximum", "default", "value"):
                _integer(item[key], key, -(2**31), 2**31 - 1)
            _integer(item["step"], "step", 1, 2**31 - 1)
            _integer(item["capability_flags"], "capability_flags", 1, 3)
            _integer(item["flags"], "flags", 1, 3)
            _text(item["unit"], "unit", 64)
            if (
                not item["minimum"] <= item["default"] <= item["maximum"]
                or not item["minimum"] <= item["value"] <= item["maximum"]
            ):
                _fail("control range/readback is inconsistent")
            controls.append(NativeControlObservation(**item))
        if len({c.control_id for c in controls}) != len(controls):
            _fail("duplicate control observation")
        if root["status"] == "OK":
            for requested in requested_controls:
                actual = next(
                    (c for c in controls if c.control_id == requested.control_id), None
                )
                expected_flag = 1 if requested.mode == "auto" else 2
                if (
                    actual is None
                    or actual.flags != expected_flag
                    or (requested.mode == "manual" and actual.value != requested.value)
                ):
                    _fail("requested control did not read back exactly")
        frames: list[NativeFrameMetadata] = []
        total = 0
        for item in _items(root["frames"], MAX_FRAMES, "frames"):
            item = _closed(
                item,
                {
                    "filename",
                    "length_bytes",
                    "stride_bytes",
                    "row0_offset_bytes",
                    "host_sequence",
                    "media_timestamp_100ns",
                    "host_arrival_qpc",
                    "qpc_frequency",
                    "discontinuity",
                },
                "frame",
            )
            if output is None or output[1] is None or observed is None:
                _fail("unrequested frame artifact")
            budget, directory = output
            if item["filename"] != f"frame-{len(frames):06d}.yuy2":
                _fail("unexpected/traversing frame filename")
            length = _integer(
                item["length_bytes"], "length_bytes", 1, budget.max_frame_bytes
            )
            stride = _integer(
                item["stride_bytes"], "stride_bytes", -1_048_576, 1_048_576
            )
            offset = _integer(
                item["row0_offset_bytes"], "row0_offset_bytes", 0, length - 1
            )
            last = offset + stride * (observed.height - 1)
            if (
                abs(stride) < observed.width * 2
                or min(offset, last) < 0
                or max(offset, last) + observed.width * 2 > length
            ):
                _fail("invalid sample stride/row bounds")
            if _integer(
                item["host_sequence"], "host_sequence", 0, MAX_FRAMES - 1
            ) != len(frames):
                _fail("host sequence discontinuity")
            _integer(
                item["media_timestamp_100ns"],
                "media_timestamp_100ns",
                -(2**63),
                2**63 - 1,
            )
            _integer(item["host_arrival_qpc"], "host_arrival_qpc", 0, 2**63 - 1)
            _integer(item["qpc_frequency"], "qpc_frequency", 1, 2**63 - 1)
            if item["discontinuity"] is not None:
                _bool(item["discontinuity"], "discontinuity")
            total += length
            if total > budget.max_total_bytes or len(frames) >= budget.max_frames:
                _fail("capture exceeded campaign budget")
            frames.append(NativeFrameMetadata(**item))
        if counts["frames_written"] != len(frames) or counts["samples_received"] < len(
            frames
        ):
            _fail("frame artifact accounting mismatch")
        if root["status"] == "OK" and operation == "capture":
            assert output is not None and output[1] is not None
            if len(frames) != output[0].max_frames:
                _fail("successful capture returned fewer frames than requested")
            if counts["samples_received"] != len(frames):
                _fail("successful bounded burst has unaccounted samples")
        limitations = tuple(
            _text(x, "limitation", 128)
            for x in _items(root["limitations"], 24, "limitations")
        )
        from types import MappingProxyType

        return NativeCameraReceiptMetadata(
            operation,
            root["status"],
            reason,
            endpoint,
            tuple(candidates),
            modes,
            sent,
            observed,
            tuple(controls),
            tuple(frames),
            MappingProxyType(dict(counts)),
            confirmed,
            limitations,
        )
