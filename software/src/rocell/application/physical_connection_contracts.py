"""Provider-neutral contracts for safe workcell connection onboarding.

This module is intentionally narrower than a general hardware abstraction.  It
describes the evidence needed to prove that the selected B0477 camera and the
RoArm-M3 Pro controller are the devices connected to the host.  The arm seam
can inspect an *unpowered* USB identity and perform one feedback-only T=105
exchange; it has no raw-write, T=104, motion, torque, or contact operation.

The concrete providers in this file are deterministic fakes.  They let the
orchestrator and receipt validation be developed before hardware arrives.  A
future physical provider must implement the same small protocols and return
the same hash-bound receipts without weakening any identity or freshness gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Mapping, Protocol, Sequence, runtime_checkable

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from rocell.arm.feedback_wire import FeedbackWireError, validate_feedback_response_line
from rocell.arm.protocol import encode_line, feedback_request


HOST_DEPENDENCY_RECEIPT_SCHEMA = "rocell.host_dependency_receipt.v1"
B0477_DISCOVERY_RECEIPT_SCHEMA = "rocell.b0477_discovery_receipt.v1"
B0477_CONFIGURATION_RECEIPT_SCHEMA = "rocell.b0477_configuration_receipt.v1"
B0477_FLUSH_RECEIPT_SCHEMA = "rocell.b0477_flush_receipt.v1"
B0477_FRAME_RECEIPT_SCHEMA = "rocell.b0477_fresh_frame_receipt.v1"
B0477_REOPEN_RECEIPT_SCHEMA = "rocell.b0477_reopen_receipt.v1"
B0477_CLOSE_RECEIPT_SCHEMA = "rocell.b0477_close_receipt.v1"
CAPTURED_FRAME_SCHEMA = "rocell.captured_onboarding_frame.v1"
ROARM_UNPOWERED_IDENTITY_RECEIPT_SCHEMA = (
    "rocell.roarm_unpowered_usb_serial_identity_receipt.v1"
)
ROARM_T105_RECEIPT_SCHEMA = "rocell.roarm_single_t105_feedback_receipt.v1"

MAX_TEXT_CHARS = 512
MAX_DEPENDENCIES = 128
MAX_ENUMERATED_CAMERAS = 32
MAX_USB_HOPS = 16
# A full 5472x3648 YUY2 frame is about 40 MiB.  Onboarding evidence must be
# explicitly encoded before entering this immutable carrier; silently calling
# a smaller blob a native YUY2 frame would make calibration evidence ambiguous.
MAX_IMMUTABLE_FRAME_BYTES = 32 * 1024 * 1024
MIN_FEEDBACK_LINE_BYTES = 10
MAX_FEEDBACK_LINE_BYTES = 65_536
REQUIRED_B0477_WIDTH_PX = 5472
REQUIRED_B0477_HEIGHT_PX = 3648
REQUIRED_B0477_FPS_NUMERATOR = 9
REQUIRED_B0477_FPS_DENOMINATOR = 1
REQUIRED_B0477_FOURCC = "YUY2"
REQUIRED_ARM_BAUDRATE = 115200

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_USB_ID_RE = re.compile(r"[0-9a-f]{4}\Z")
_WINDOWS_CAMERA_ORDINAL_RE = re.compile(r"(?:camera|index)\s*[:#]?\s*\d+\Z", re.I)
_WINDOWS_COM_RE = re.compile(r"COM\d+\Z", re.I)
_LINUX_VIDEO_ORDINAL_RE = re.compile(r"/dev/video\d+\Z")


class PhysicalConnectionContractError(ValueError):
    """A request, observation, or receipt violates a safe connection contract."""


class FakeConnectionBoundaryError(RuntimeError):
    """A deterministic fake was asked to cross its zero-hardware boundary."""


class EvidenceOrigin(str, Enum):
    """Provenance class carried by every provider descriptor."""

    SYNTHETIC_REHEARSAL = "SYNTHETIC_REHEARSAL"
    PHYSICAL_OBSERVATION = "PHYSICAL_OBSERVATION"


class FrameTimingBasis(str, Enum):
    """Meaning of the first timestamp retained with a captured frame."""

    HOST_BRACKET = "HOST_BRACKET"
    DEVICE_EXPOSURE = "DEVICE_EXPOSURE"


class RetainedFrameEncoding(str, Enum):
    """Bounded evidence encodings; native 20 MP YUY2 is intentionally absent."""

    JPEG = "JPEG"
    PNG = "PNG"
    SYNTHETIC_CANONICAL_JSON = "SYNTHETIC_CANONICAL_JSON"


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalConnectionContractError(
            "connection evidence cannot be canonicalized"
        ) from exc


def canonical_sha256(value: object) -> str:
    """Return the canonical semantic digest used by all connection records."""

    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text(value: object, label: str, *, maximum: int = MAX_TEXT_CHARS) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PhysicalConnectionContractError(
            f"{label} must be non-empty, trimmed, bounded text"
        )
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PhysicalConnectionContractError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _bounded_int(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = (1 << 63) - 1,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise PhysicalConnectionContractError(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _finite_number(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PhysicalConnectionContractError(f"{label} must be finite numeric data")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < minimum or parsed > maximum:
        raise PhysicalConnectionContractError(
            f"{label} must be finite and within [{minimum}, {maximum}]"
        )
    return parsed


def _strict_tuple(
    value: object,
    item_type: type,
    label: str,
    *,
    minimum: int = 1,
    maximum: int,
) -> tuple:
    if not isinstance(value, tuple):
        raise PhysicalConnectionContractError(f"{label} must be an immutable tuple")
    if not minimum <= len(value) <= maximum:
        raise PhysicalConnectionContractError(
            f"{label} must contain between {minimum} and {maximum} items"
        )
    if any(not isinstance(item, item_type) for item in value):
        raise PhysicalConnectionContractError(
            f"{label} contains an item of the wrong type"
        )
    return value


def _persistent_selector(value: object, label: str) -> str:
    selector = _text(value, label)
    # Numeric camera indices, COM names, and /dev/video ordinals are discovery
    # conveniences, not persistent identities.  They may be retained as
    # observations elsewhere but can never select commissioned hardware.
    if (
        selector.isdigit()
        or _WINDOWS_CAMERA_ORDINAL_RE.fullmatch(selector) is not None
        or _WINDOWS_COM_RE.fullmatch(selector) is not None
        or _LINUX_VIDEO_ORDINAL_RE.fullmatch(selector) is not None
    ):
        raise PhysicalConnectionContractError(
            f"{label} must be a persistent OS identity, not a numeric/COM device ordinal"
        )
    if len(selector) < 8:
        raise PhysicalConnectionContractError(f"{label} is too short to be persistent")
    return selector


def _version_specifier(value: object, label: str) -> str:
    """Validate and retain one canonical-input PEP 440 version constraint."""

    parsed = _text(value, label, maximum=96)
    try:
        SpecifierSet(parsed)
    except InvalidSpecifier as exc:
        raise PhysicalConnectionContractError(
            f"{label} must be a valid PEP 440 version specifier"
        ) from exc
    return parsed


def _installed_version(value: object, label: str) -> str:
    """Reject ambiguous provider versions before they enter bound evidence."""

    parsed = _text(value, label, maximum=96)
    try:
        Version(parsed)
    except InvalidVersion as exc:
        raise PhysicalConnectionContractError(
            f"{label} must be a valid PEP 440 version"
        ) from exc
    return parsed


def _dependency_requirement_satisfied(
    requirement: DependencyRequirement,
    observation: DependencyObservation,
) -> bool:
    """Return whether an observation is present and inside its declared range."""

    if not observation.available:
        return False
    # DependencyObservation and DependencyRequirement validate these strings at
    # construction, so this comparison is deterministic and cannot silently
    # reinterpret an invalid provider value as a passing version.
    assert observation.installed_version is not None
    return Version(observation.installed_version) in SpecifierSet(
        requirement.version_specifier
    )


@dataclass(frozen=True, slots=True)
class ConnectionProviderDescriptor:
    """Identity and authority class for a provider implementation."""

    provider_id: str
    implementation_version: str
    evidence_origin: EvidenceOrigin
    hardware_capable: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))
        object.__setattr__(
            self,
            "implementation_version",
            _text(self.implementation_version, "implementation_version", maximum=96),
        )
        if not isinstance(self.evidence_origin, EvidenceOrigin):
            raise PhysicalConnectionContractError(
                "evidence_origin must be an EvidenceOrigin"
            )
        if not isinstance(self.hardware_capable, bool):
            raise PhysicalConnectionContractError("hardware_capable must be boolean")
        if (
            self.evidence_origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
            and self.hardware_capable
        ):
            raise PhysicalConnectionContractError(
                "a synthetic provider cannot claim hardware capability"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "implementation_version": self.implementation_version,
            "evidence_origin": self.evidence_origin.value,
            "hardware_capable": self.hardware_capable,
        }

    @property
    def descriptor_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


FAKE_PROVIDER_DESCRIPTOR = ConnectionProviderDescriptor(
    provider_id="rocell-deterministic-physical-connection-fake",
    implementation_version="1",
    evidence_origin=EvidenceOrigin.SYNTHETIC_REHEARSAL,
    hardware_capable=False,
)


@dataclass(frozen=True, slots=True, order=True)
class DependencyRequirement:
    name: str
    version_specifier: str
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "dependency.name", maximum=96))
        object.__setattr__(
            self,
            "version_specifier",
            _version_specifier(
                self.version_specifier, "dependency.version_specifier"
            ),
        )
        if not isinstance(self.required, bool):
            raise PhysicalConnectionContractError("dependency.required must be boolean")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version_specifier": self.version_specifier,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class DependencyObservation:
    name: str
    installed_version: str | None
    artifact_path: str | None
    artifact_sha256: str | None
    available: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "dependency.name", maximum=96))
        if not isinstance(self.available, bool):
            raise PhysicalConnectionContractError("dependency.available must be boolean")
        values = (self.installed_version, self.artifact_path, self.artifact_sha256)
        if self.available:
            if any(value is None for value in values):
                raise PhysicalConnectionContractError(
                    "available dependency observations require version, path, and digest"
                )
            object.__setattr__(
                self,
                "installed_version",
                _installed_version(
                    self.installed_version, "dependency.installed_version"
                ),
            )
            object.__setattr__(
                self,
                "artifact_path",
                _text(self.artifact_path, "dependency.artifact_path"),
            )
            object.__setattr__(
                self,
                "artifact_sha256",
                _digest(self.artifact_sha256, "dependency.artifact_sha256"),
            )
        elif any(value is not None for value in values):
            raise PhysicalConnectionContractError(
                "unavailable dependency observations must retain null details"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "installed_version": self.installed_version,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "available": self.available,
        }


@dataclass(frozen=True, slots=True)
class HostIdentity:
    host_id: str
    os_name: str
    os_release: str
    architecture: str
    python_implementation: str
    python_version: str
    python_executable: str
    python_executable_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "host_id",
            "os_name",
            "os_release",
            "architecture",
            "python_implementation",
            "python_version",
            "python_executable",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "python_executable_sha256",
            _digest(self.python_executable_sha256, "python_executable_sha256"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in (
                "host_id",
                "os_name",
                "os_release",
                "architecture",
                "python_implementation",
                "python_version",
                "python_executable",
                "python_executable_sha256",
            )
        }


@dataclass(frozen=True, slots=True)
class HostDependencyRequest:
    run_id: str
    source_tree_sha256: str
    requirements: tuple[DependencyRequirement, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "source_tree_sha256",
            _digest(self.source_tree_sha256, "source_tree_sha256"),
        )
        requirements = _strict_tuple(
            self.requirements,
            DependencyRequirement,
            "requirements",
            maximum=MAX_DEPENDENCIES,
        )
        if tuple(sorted(requirements)) != requirements:
            raise PhysicalConnectionContractError("requirements must be sorted")
        names = [item.name.casefold() for item in requirements]
        if len(names) != len(set(names)):
            raise PhysicalConnectionContractError("requirements contain duplicate names")

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "source_tree_sha256": self.source_tree_sha256,
                "requirements": [item.to_dict() for item in self.requirements],
            }
        )


@dataclass(frozen=True, slots=True)
class HostDependencyReceipt:
    run_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    source_tree_sha256: str
    host: HostIdentity
    requirements: tuple[DependencyRequirement, ...]
    observations: tuple[DependencyObservation, ...]
    observed_monotonic_ns: int
    all_required_available: bool
    schema: str = field(default=HOST_DEPENDENCY_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        for name in ("provider_descriptor_sha256", "request_sha256", "source_tree_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.host, HostIdentity):
            raise PhysicalConnectionContractError("host must be HostIdentity")
        requirements = _strict_tuple(
            self.requirements,
            DependencyRequirement,
            "requirements",
            maximum=MAX_DEPENDENCIES,
        )
        observations = _strict_tuple(
            self.observations,
            DependencyObservation,
            "observations",
            maximum=MAX_DEPENDENCIES,
        )
        requirement_names = tuple(item.name for item in requirements)
        observation_names = tuple(item.name for item in observations)
        if requirement_names != observation_names:
            raise PhysicalConnectionContractError(
                "dependency observations must exactly match requirement order and fields"
            )
        expected_available = all(
            _dependency_requirement_satisfied(requirement, observation)
            or not requirement.required
            for requirement, observation in zip(requirements, observations)
        )
        if type(self.all_required_available) is not bool or (
            self.all_required_available != expected_available
        ):
            raise PhysicalConnectionContractError(
                "all_required_available does not match dependency observations"
            )
        object.__setattr__(
            self,
            "observed_monotonic_ns",
            _bounded_int(self.observed_monotonic_ns, "observed_monotonic_ns", minimum=1),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "source_tree_sha256": self.source_tree_sha256,
            "host": self.host.to_dict(),
            "requirements": [item.to_dict() for item in self.requirements],
            "observations": [item.to_dict() for item in self.observations],
            "observed_monotonic_ns": self.observed_monotonic_ns,
            "all_required_available": self.all_required_available,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class UsbDriverIdentity:
    provider: str
    service: str
    version: str
    package_or_inf_path: str

    def __post_init__(self) -> None:
        for name in ("provider", "service", "version", "package_or_inf_path"):
            object.__setattr__(self, name, _text(getattr(self, name), f"driver.{name}"))

    def to_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "service": self.service,
            "version": self.version,
            "package_or_inf_path": self.package_or_inf_path,
        }


@dataclass(frozen=True, slots=True)
class Usb3Topology:
    host_controller_instance_id: str
    hub_instance_path: tuple[str, ...]
    port_chain: tuple[int, ...]
    negotiated_speed_mbps: int
    negotiated_generation: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "host_controller_instance_id",
            _persistent_selector(
                self.host_controller_instance_id, "host_controller_instance_id"
            ),
        )
        if not isinstance(self.hub_instance_path, tuple) or not (
            1 <= len(self.hub_instance_path) <= MAX_USB_HOPS
        ):
            raise PhysicalConnectionContractError(
                "hub_instance_path must be a bounded non-empty tuple"
            )
        object.__setattr__(
            self,
            "hub_instance_path",
            tuple(
                _persistent_selector(item, "hub_instance_path item")
                for item in self.hub_instance_path
            ),
        )
        if not isinstance(self.port_chain, tuple) or len(self.port_chain) != len(
            self.hub_instance_path
        ):
            raise PhysicalConnectionContractError(
                "port_chain must contain exactly one port number per USB hop"
            )
        object.__setattr__(
            self,
            "port_chain",
            tuple(
                _bounded_int(item, "USB port number", minimum=1, maximum=255)
                for item in self.port_chain
            ),
        )
        object.__setattr__(
            self,
            "negotiated_speed_mbps",
            _bounded_int(
                self.negotiated_speed_mbps,
                "negotiated_speed_mbps",
                minimum=5_000,
                maximum=80_000,
            ),
        )
        generation = _text(
            self.negotiated_generation, "negotiated_generation", maximum=48
        )
        if not generation.startswith("USB_3"):
            raise PhysicalConnectionContractError(
                "B0477 onboarding requires an observed USB 3.x topology"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "host_controller_instance_id": self.host_controller_instance_id,
            "hub_instance_path": list(self.hub_instance_path),
            "port_chain": list(self.port_chain),
            "negotiated_speed_mbps": self.negotiated_speed_mbps,
            "negotiated_generation": self.negotiated_generation,
        }


@dataclass(frozen=True, slots=True)
class B0477UvcIdentity:
    """Complete persistent identity for one selected camera unit."""

    vid: str
    pid: str
    unit_serial: str
    persistent_os_path: str
    device_instance_id: str
    driver: UsbDriverIdentity
    topology: Usb3Topology
    manufacturer: str = field(default="Arducam", init=False)
    model: str = field(default="B0477", init=False)
    sensor: str = field(default="Sony IMX283", init=False)

    def __post_init__(self) -> None:
        for name in ("vid", "pid"):
            value = getattr(self, name)
            if not isinstance(value, str) or _USB_ID_RE.fullmatch(value) is None:
                raise PhysicalConnectionContractError(
                    f"{name} must be exactly four lowercase hexadecimal digits"
                )
        object.__setattr__(
            self, "unit_serial", _text(self.unit_serial, "unit_serial", maximum=128)
        )
        object.__setattr__(
            self,
            "persistent_os_path",
            _persistent_selector(self.persistent_os_path, "persistent_os_path"),
        )
        object.__setattr__(
            self,
            "device_instance_id",
            _persistent_selector(self.device_instance_id, "device_instance_id"),
        )
        if not isinstance(self.driver, UsbDriverIdentity):
            raise PhysicalConnectionContractError("driver must be UsbDriverIdentity")
        if not isinstance(self.topology, Usb3Topology):
            raise PhysicalConnectionContractError("topology must be Usb3Topology")

    def to_dict(self) -> dict[str, object]:
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sensor": self.sensor,
            "vid": self.vid,
            "pid": self.pid,
            "unit_serial": self.unit_serial,
            "persistent_os_path": self.persistent_os_path,
            "device_instance_id": self.device_instance_id,
            "driver": self.driver.to_dict(),
            "topology": self.topology.to_dict(),
        }

    @property
    def identity_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class B0477DiscoveryRequest:
    run_id: str
    expected_identity: B0477UvcIdentity

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.expected_identity, B0477UvcIdentity):
            raise PhysicalConnectionContractError(
                "expected_identity must be B0477UvcIdentity"
            )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "expected_identity_sha256": self.expected_identity.identity_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class B0477DiscoveryReceipt:
    run_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    observed_monotonic_ns: int
    devices: tuple[B0477UvcIdentity, ...]
    selected_identity_sha256: str
    selected_persistent_os_path: str
    ordinal_fallback_used: bool
    schema: str = field(default=B0477_DISCOVERY_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        for name in ("provider_descriptor_sha256", "request_sha256", "selected_identity_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "observed_monotonic_ns",
            _bounded_int(self.observed_monotonic_ns, "observed_monotonic_ns", minimum=1),
        )
        devices = _strict_tuple(
            self.devices,
            B0477UvcIdentity,
            "devices",
            maximum=MAX_ENUMERATED_CAMERAS,
        )
        digests = tuple(item.identity_sha256 for item in devices)
        if len(digests) != len(set(digests)):
            raise PhysicalConnectionContractError("camera inventory contains duplicates")
        if digests.count(self.selected_identity_sha256) != 1:
            raise PhysicalConnectionContractError(
                "selected camera digest must identify exactly one enumerated B0477"
            )
        selected = devices[digests.index(self.selected_identity_sha256)]
        persistent_path = _persistent_selector(
            self.selected_persistent_os_path, "selected_persistent_os_path"
        )
        if persistent_path != selected.persistent_os_path:
            raise PhysicalConnectionContractError(
                "selected camera path does not match the hash-selected identity"
            )
        if type(self.ordinal_fallback_used) is not bool or self.ordinal_fallback_used:
            raise PhysicalConnectionContractError(
                "numeric camera-index fallback is prohibited"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "observed_monotonic_ns": self.observed_monotonic_ns,
            "devices": [item.to_dict() for item in self.devices],
            "selected_identity_sha256": self.selected_identity_sha256,
            "selected_persistent_os_path": self.selected_persistent_os_path,
            "ordinal_fallback_used": self.ordinal_fallback_used,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class B0477NativeMode:
    """The single native full-resolution mode accepted for calibration."""

    width_px: int = field(default=REQUIRED_B0477_WIDTH_PX, init=False)
    height_px: int = field(default=REQUIRED_B0477_HEIGHT_PX, init=False)
    fps_numerator: int = field(default=REQUIRED_B0477_FPS_NUMERATOR, init=False)
    fps_denominator: int = field(default=REQUIRED_B0477_FPS_DENOMINATOR, init=False)
    fourcc: str = field(default=REQUIRED_B0477_FOURCC, init=False)
    host_bus: str = field(default="USB_3_X", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "fps_numerator": self.fps_numerator,
            "fps_denominator": self.fps_denominator,
            "fourcc": self.fourcc,
            "host_bus": self.host_bus,
        }


@dataclass(frozen=True, slots=True)
class B0477ManualControls:
    exposure_us: float
    gain_relative: float
    white_balance_kelvin: float
    exposure_mode: str = field(default="MANUAL", init=False)
    gain_mode: str = field(default="MANUAL", init=False)
    white_balance_mode: str = field(default="MANUAL", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "exposure_us",
            _finite_number(
                self.exposure_us, "exposure_us", minimum=1.0, maximum=1_000_000.0
            ),
        )
        object.__setattr__(
            self,
            "gain_relative",
            _finite_number(
                self.gain_relative, "gain_relative", minimum=0.0, maximum=1_000.0
            ),
        )
        object.__setattr__(
            self,
            "white_balance_kelvin",
            _finite_number(
                self.white_balance_kelvin,
                "white_balance_kelvin",
                minimum=1_000.0,
                maximum=20_000.0,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "exposure_mode": self.exposure_mode,
            "exposure_us": self.exposure_us,
            "gain_mode": self.gain_mode,
            "gain_relative": self.gain_relative,
            "white_balance_mode": self.white_balance_mode,
            "white_balance_kelvin": self.white_balance_kelvin,
        }


@dataclass(frozen=True, slots=True)
class B0477ExactConfiguration:
    controls: B0477ManualControls
    mode: B0477NativeMode = field(default_factory=B0477NativeMode, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.controls, B0477ManualControls):
            raise PhysicalConnectionContractError(
                "controls must be B0477ManualControls"
            )

    def to_dict(self) -> dict[str, object]:
        return {"mode": self.mode.to_dict(), "controls": self.controls.to_dict()}

    @property
    def configuration_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class CameraSessionReceipt:
    run_id: str
    session_id: str
    provider_descriptor_sha256: str
    camera_identity_sha256: str
    persistent_os_path: str
    session_ordinal: int
    opened_monotonic_ns: int

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("provider_descriptor_sha256", "camera_identity_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "persistent_os_path",
            _persistent_selector(self.persistent_os_path, "persistent_os_path"),
        )
        object.__setattr__(
            self,
            "session_ordinal",
            _bounded_int(self.session_ordinal, "session_ordinal", minimum=1),
        )
        object.__setattr__(
            self,
            "opened_monotonic_ns",
            _bounded_int(self.opened_monotonic_ns, "opened_monotonic_ns", minimum=1),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "camera_identity_sha256": self.camera_identity_sha256,
            "persistent_os_path": self.persistent_os_path,
            "session_ordinal": self.session_ordinal,
            "opened_monotonic_ns": self.opened_monotonic_ns,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class CameraOpenRequest:
    run_id: str
    discovery_receipt_sha256: str
    identity: B0477UvcIdentity

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "discovery_receipt_sha256",
            _digest(self.discovery_receipt_sha256, "discovery_receipt_sha256"),
        )
        if not isinstance(self.identity, B0477UvcIdentity):
            raise PhysicalConnectionContractError("identity must be B0477UvcIdentity")


@dataclass(frozen=True, slots=True)
class CameraConfigurationRequest:
    run_id: str
    session_receipt_sha256: str
    camera_identity_sha256: str
    session_id: str
    desired: B0477ExactConfiguration

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        for name in ("session_receipt_sha256", "camera_identity_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.desired, B0477ExactConfiguration):
            raise PhysicalConnectionContractError(
                "desired must be B0477ExactConfiguration"
            )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "session_receipt_sha256": self.session_receipt_sha256,
                "camera_identity_sha256": self.camera_identity_sha256,
                "session_id": self.session_id,
                "desired_configuration_sha256": self.desired.configuration_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class CameraConfigurationReceipt:
    run_id: str
    session_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    camera_identity_sha256: str
    requested_configuration_sha256: str
    observed: B0477ExactConfiguration
    readback_monotonic_ns: int
    fallback_negotiated: bool
    schema: str = field(default=B0477_CONFIGURATION_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "provider_descriptor_sha256",
            "request_sha256",
            "camera_identity_sha256",
            "requested_configuration_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.observed, B0477ExactConfiguration):
            raise PhysicalConnectionContractError(
                "observed must be B0477ExactConfiguration"
            )
        if self.observed.configuration_sha256 != self.requested_configuration_sha256:
            raise PhysicalConnectionContractError(
                "camera configuration readback differs from the exact request"
            )
        object.__setattr__(
            self,
            "readback_monotonic_ns",
            _bounded_int(self.readback_monotonic_ns, "readback_monotonic_ns", minimum=1),
        )
        if type(self.fallback_negotiated) is not bool or self.fallback_negotiated:
            raise PhysicalConnectionContractError(
                "camera mode/control fallback is prohibited"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "camera_identity_sha256": self.camera_identity_sha256,
            "requested_configuration_sha256": self.requested_configuration_sha256,
            "observed": self.observed.to_dict(),
            "readback_monotonic_ns": self.readback_monotonic_ns,
            "fallback_negotiated": self.fallback_negotiated,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class CameraFlushRequest:
    run_id: str
    session_id: str
    configuration_receipt_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(
            self,
            "configuration_receipt_sha256",
            _digest(self.configuration_receipt_sha256, "configuration_receipt_sha256"),
        )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "session_id": self.session_id,
                "configuration_receipt_sha256": self.configuration_receipt_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class CameraFlushReceipt:
    run_id: str
    session_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    configuration_receipt_sha256: str
    flush_started_monotonic_ns: int
    flush_completed_monotonic_ns: int
    discarded_frame_count: int
    last_discarded_sequence: int
    buffer_empty_after: bool
    schema: str = field(default=B0477_FLUSH_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "provider_descriptor_sha256",
            "request_sha256",
            "configuration_receipt_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        start = _bounded_int(
            self.flush_started_monotonic_ns, "flush_started_monotonic_ns", minimum=1
        )
        end = _bounded_int(
            self.flush_completed_monotonic_ns, "flush_completed_monotonic_ns", minimum=1
        )
        if end < start:
            raise PhysicalConnectionContractError("flush timestamps are not monotonic")
        object.__setattr__(
            self,
            "discarded_frame_count",
            _bounded_int(
                self.discarded_frame_count,
                "discarded_frame_count",
                minimum=1,
                maximum=1_000_000,
            ),
        )
        object.__setattr__(
            self,
            "last_discarded_sequence",
            _bounded_int(self.last_discarded_sequence, "last_discarded_sequence"),
        )
        if type(self.buffer_empty_after) is not bool or not self.buffer_empty_after:
            raise PhysicalConnectionContractError(
                "camera buffer must be observed empty after the onboarding flush"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "configuration_receipt_sha256": self.configuration_receipt_sha256,
            "flush_started_monotonic_ns": self.flush_started_monotonic_ns,
            "flush_completed_monotonic_ns": self.flush_completed_monotonic_ns,
            "discarded_frame_count": self.discarded_frame_count,
            "last_discarded_sequence": self.last_discarded_sequence,
            "buffer_empty_after": self.buffer_empty_after,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class FreshFrameRequest:
    run_id: str
    session_id: str
    flush_receipt_sha256: str
    configuration_sha256: str
    minimum_sequence_exclusive: int
    requested_monotonic_ns: int
    maximum_latency_ns: int

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("flush_receipt_sha256", "configuration_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "minimum_sequence_exclusive",
            _bounded_int(self.minimum_sequence_exclusive, "minimum_sequence_exclusive"),
        )
        object.__setattr__(
            self,
            "requested_monotonic_ns",
            _bounded_int(self.requested_monotonic_ns, "requested_monotonic_ns", minimum=1),
        )
        object.__setattr__(
            self,
            "maximum_latency_ns",
            _bounded_int(
                self.maximum_latency_ns,
                "maximum_latency_ns",
                minimum=1,
                maximum=60_000_000_000,
            ),
        )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "session_id": self.session_id,
                "flush_receipt_sha256": self.flush_receipt_sha256,
                "configuration_sha256": self.configuration_sha256,
                "minimum_sequence_exclusive": self.minimum_sequence_exclusive,
                "requested_monotonic_ns": self.requested_monotonic_ns,
                "maximum_latency_ns": self.maximum_latency_ns,
            }
        )


@dataclass(frozen=True, slots=True)
class FreshFrameReceipt:
    run_id: str
    session_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    flush_receipt_sha256: str
    configuration_sha256: str
    sequence: int
    capture_started_monotonic_ns: int
    delivered_monotonic_ns: int
    timing_basis: FrameTimingBasis
    device_exposure_proof_sha256: str | None
    retained_encoding: RetainedFrameEncoding
    payload_bytes: int
    payload_sha256: str
    schema: str = field(default=B0477_FRAME_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "provider_descriptor_sha256",
            "request_sha256",
            "flush_receipt_sha256",
            "configuration_sha256",
            "payload_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(self, "sequence", _bounded_int(self.sequence, "sequence"))
        started = _bounded_int(
            self.capture_started_monotonic_ns,
            "capture_started_monotonic_ns",
            minimum=1,
        )
        delivered = _bounded_int(
            self.delivered_monotonic_ns, "delivered_monotonic_ns", minimum=1
        )
        if delivered < started:
            raise PhysicalConnectionContractError("frame timestamps are not monotonic")
        if not isinstance(self.timing_basis, FrameTimingBasis):
            raise PhysicalConnectionContractError(
                "timing_basis must be FrameTimingBasis"
            )
        if self.timing_basis is FrameTimingBasis.HOST_BRACKET:
            if self.device_exposure_proof_sha256 is not None:
                raise PhysicalConnectionContractError(
                    "HOST_BRACKET timing cannot claim device exposure proof"
                )
        elif self.device_exposure_proof_sha256 is None:
            raise PhysicalConnectionContractError(
                "DEVICE_EXPOSURE timing requires a device proof digest"
            )
        else:
            object.__setattr__(
                self,
                "device_exposure_proof_sha256",
                _digest(
                    self.device_exposure_proof_sha256,
                    "device_exposure_proof_sha256",
                ),
            )
        if not isinstance(self.retained_encoding, RetainedFrameEncoding):
            raise PhysicalConnectionContractError(
                "retained_encoding must be RetainedFrameEncoding"
            )
        object.__setattr__(
            self,
            "payload_bytes",
            _bounded_int(
                self.payload_bytes,
                "payload_bytes",
                minimum=1,
                maximum=MAX_IMMUTABLE_FRAME_BYTES,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "flush_receipt_sha256": self.flush_receipt_sha256,
            "configuration_sha256": self.configuration_sha256,
            "sequence": self.sequence,
            "capture_started_monotonic_ns": self.capture_started_monotonic_ns,
            "delivered_monotonic_ns": self.delivered_monotonic_ns,
            "timing_basis": self.timing_basis.value,
            "device_exposure_proof_sha256": self.device_exposure_proof_sha256,
            "retained_encoding": self.retained_encoding.value,
            "payload_bytes": self.payload_bytes,
            "payload_sha256": self.payload_sha256,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """A fresh-frame receipt carried with the exact immutable evidence bytes.

    The negotiated camera input remains full-resolution YUY2.  The bytes here
    are a separately identified bounded evidence encoding, never an implicit
    claim that a native 20 MP YUY2 buffer fits below the 32 MiB limit.
    """

    receipt: FreshFrameReceipt
    payload: bytes
    schema: str = field(default=CAPTURED_FRAME_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, FreshFrameReceipt):
            raise PhysicalConnectionContractError(
                "receipt must be FreshFrameReceipt"
            )
        if not isinstance(self.payload, bytes):
            raise PhysicalConnectionContractError("payload must be immutable bytes")
        if not 1 <= len(self.payload) <= MAX_IMMUTABLE_FRAME_BYTES:
            raise PhysicalConnectionContractError(
                "captured frame payload exceeds the 32 MiB evidence bound"
            )
        if len(self.payload) != self.receipt.payload_bytes:
            raise PhysicalConnectionContractError(
                "captured frame length does not match its fresh-frame receipt"
            )
        if _bytes_sha256(self.payload) != self.receipt.payload_sha256:
            raise PhysicalConnectionContractError(
                "captured frame bytes do not match their receipt digest"
            )

    @property
    def carrier_sha256(self) -> str:
        return canonical_sha256(
            {
                "schema": self.schema,
                "receipt_sha256": self.receipt.receipt_sha256,
                "payload_sha256": self.receipt.payload_sha256,
                "payload_bytes": self.receipt.payload_bytes,
            }
        )


@dataclass(frozen=True, slots=True)
class CameraCloseRequest:
    """Request cleanup for one exact camera session, never by device ordinal."""

    run_id: str
    session: CameraSessionReceipt
    reason: str
    requested_monotonic_ns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.session, CameraSessionReceipt):
            raise PhysicalConnectionContractError(
                "session must be CameraSessionReceipt"
            )
        if self.session.run_id != self.run_id:
            raise PhysicalConnectionContractError("camera close run binding mismatch")
        object.__setattr__(self, "reason", _text(self.reason, "reason", maximum=160))
        object.__setattr__(
            self,
            "requested_monotonic_ns",
            _bounded_int(
                self.requested_monotonic_ns,
                "requested_monotonic_ns",
                minimum=1,
            ),
        )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "session_receipt_sha256": self.session.receipt_sha256,
                "reason": self.reason,
                "requested_monotonic_ns": self.requested_monotonic_ns,
            }
        )


@dataclass(frozen=True, slots=True)
class CameraCloseReceipt:
    """Idempotent close outcome with an honest underlying-attempt indicator."""

    run_id: str
    session_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    session_receipt_sha256: str
    close_attempted: bool
    close_succeeded: bool
    was_already_closed: bool
    close_started_monotonic_ns: int
    close_completed_monotonic_ns: int
    failure_code: str | None
    schema: str = field(default=B0477_CLOSE_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "provider_descriptor_sha256",
            "request_sha256",
            "session_receipt_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        for name in ("close_attempted", "close_succeeded", "was_already_closed"):
            if type(getattr(self, name)) is not bool:
                raise PhysicalConnectionContractError(f"{name} must be boolean")
        started = _bounded_int(
            self.close_started_monotonic_ns,
            "close_started_monotonic_ns",
            minimum=1,
        )
        completed = _bounded_int(
            self.close_completed_monotonic_ns,
            "close_completed_monotonic_ns",
            minimum=1,
        )
        if completed < started:
            raise PhysicalConnectionContractError(
                "camera close timestamps are not monotonic"
            )
        if self.was_already_closed:
            if self.close_attempted or not self.close_succeeded:
                raise PhysicalConnectionContractError(
                    "idempotent already-closed result must succeed without another close attempt"
                )
        elif not self.close_attempted:
            raise PhysicalConnectionContractError(
                "an open session cannot close without an underlying close attempt"
            )
        if self.close_succeeded:
            if self.failure_code is not None:
                raise PhysicalConnectionContractError(
                    "successful camera close cannot carry a failure code"
                )
        else:
            if self.was_already_closed or self.failure_code is None:
                raise PhysicalConnectionContractError(
                    "failed camera close requires a bounded failure code"
                )
            object.__setattr__(
                self,
                "failure_code",
                _text(self.failure_code, "failure_code", maximum=96),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "session_receipt_sha256": self.session_receipt_sha256,
            "close_attempted": self.close_attempted,
            "close_succeeded": self.close_succeeded,
            "was_already_closed": self.was_already_closed,
            "close_started_monotonic_ns": self.close_started_monotonic_ns,
            "close_completed_monotonic_ns": self.close_completed_monotonic_ns,
            "failure_code": self.failure_code,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class CameraReopenRequest:
    run_id: str
    previous_session: CameraSessionReceipt
    expected_identity: B0477UvcIdentity
    expected_configuration: B0477ExactConfiguration

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.previous_session, CameraSessionReceipt):
            raise PhysicalConnectionContractError(
                "previous_session must be CameraSessionReceipt"
            )
        if not isinstance(self.expected_identity, B0477UvcIdentity):
            raise PhysicalConnectionContractError(
                "expected_identity must be B0477UvcIdentity"
            )
        if not isinstance(self.expected_configuration, B0477ExactConfiguration):
            raise PhysicalConnectionContractError(
                "expected_configuration must be B0477ExactConfiguration"
            )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "previous_session_receipt_sha256": self.previous_session.receipt_sha256,
                "expected_identity_sha256": self.expected_identity.identity_sha256,
                "expected_configuration_sha256": (
                    self.expected_configuration.configuration_sha256
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class CameraReopenReceipt:
    run_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    previous_session_id: str
    close_receipt: CameraCloseReceipt
    reopened_session: CameraSessionReceipt
    reopened_identity: B0477UvcIdentity
    configuration_readback: CameraConfigurationReceipt
    schema: str = field(default=B0477_REOPEN_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "previous_session_id",
            _text(self.previous_session_id, "previous_session_id"),
        )
        for name in ("provider_descriptor_sha256", "request_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.close_receipt, CameraCloseReceipt):
            raise PhysicalConnectionContractError(
                "close_receipt must be CameraCloseReceipt"
            )
        if (
            self.close_receipt.run_id != self.run_id
            or self.close_receipt.session_id != self.previous_session_id
            or not self.close_receipt.close_succeeded
        ):
            raise PhysicalConnectionContractError(
                "reopen requires a successful close receipt for the previous session"
            )
        if not isinstance(self.reopened_session, CameraSessionReceipt):
            raise PhysicalConnectionContractError(
                "reopened_session must be CameraSessionReceipt"
            )
        if not isinstance(self.reopened_identity, B0477UvcIdentity):
            raise PhysicalConnectionContractError(
                "reopened_identity must be B0477UvcIdentity"
            )
        if not isinstance(self.configuration_readback, CameraConfigurationReceipt):
            raise PhysicalConnectionContractError(
                "configuration_readback must be CameraConfigurationReceipt"
            )
        if self.reopened_session.session_id == self.previous_session_id:
            raise PhysicalConnectionContractError("reopen must create a new session")
        if (
            self.reopened_session.opened_monotonic_ns
            <= self.close_receipt.close_completed_monotonic_ns
        ):
            raise PhysicalConnectionContractError(
                "reopened session must begin after the previous session closed"
            )
        if (
            self.reopened_session.camera_identity_sha256
            != self.reopened_identity.identity_sha256
        ):
            raise PhysicalConnectionContractError(
                "reopened camera session is not bound to its observed identity"
            )
        if self.configuration_readback.session_id != self.reopened_session.session_id:
            raise PhysicalConnectionContractError(
                "reopen configuration readback is from a different session"
            )
        if (
            self.configuration_readback.camera_identity_sha256
            != self.reopened_identity.identity_sha256
        ):
            raise PhysicalConnectionContractError(
                "reopen configuration is from a different camera identity"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "previous_session_id": self.previous_session_id,
            "close_receipt": self.close_receipt.to_dict(),
            "reopened_session": self.reopened_session.to_dict(),
            "reopened_identity": self.reopened_identity.to_dict(),
            "configuration_readback": self.configuration_readback.to_dict(),
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class RoArmUsbSerialIdentity:
    """Persistent controller identity; ``port_name`` is never the selector."""

    vid: str
    pid: str
    unit_serial: str
    persistent_instance_id: str
    persistent_port_path: str
    port_name: str
    driver: UsbDriverIdentity
    manufacturer: str = field(default="Waveshare", init=False)
    product: str = field(default="RoArm-M3 Pro", init=False)
    controller: str = field(default="ESP32", init=False)
    baudrate: int = field(default=REQUIRED_ARM_BAUDRATE, init=False)
    rts: bool = field(default=False, init=False)
    dtr: bool = field(default=False, init=False)
    flow_control: str = field(default="NONE", init=False)

    def __post_init__(self) -> None:
        for name in ("vid", "pid"):
            value = getattr(self, name)
            if not isinstance(value, str) or _USB_ID_RE.fullmatch(value) is None:
                raise PhysicalConnectionContractError(
                    f"{name} must be exactly four lowercase hexadecimal digits"
                )
        object.__setattr__(
            self, "unit_serial", _text(self.unit_serial, "unit_serial", maximum=128)
        )
        for name in ("persistent_instance_id", "persistent_port_path"):
            object.__setattr__(
                self, name, _persistent_selector(getattr(self, name), name)
            )
        object.__setattr__(
            self, "port_name", _text(self.port_name, "port_name", maximum=128)
        )
        if not isinstance(self.driver, UsbDriverIdentity):
            raise PhysicalConnectionContractError("driver must be UsbDriverIdentity")

    def to_dict(self) -> dict[str, object]:
        return {
            "manufacturer": self.manufacturer,
            "product": self.product,
            "controller": self.controller,
            "vid": self.vid,
            "pid": self.pid,
            "unit_serial": self.unit_serial,
            "persistent_instance_id": self.persistent_instance_id,
            "persistent_port_path": self.persistent_port_path,
            "port_name": self.port_name,
            "driver": self.driver.to_dict(),
            "baudrate": self.baudrate,
            "rts": self.rts,
            "dtr": self.dtr,
            "flow_control": self.flow_control,
        }

    @property
    def identity_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class UnpoweredArmIdentityRequest:
    run_id: str
    expected_identity: RoArmUsbSerialIdentity
    power_off_attestation_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.expected_identity, RoArmUsbSerialIdentity):
            raise PhysicalConnectionContractError(
                "expected_identity must be RoArmUsbSerialIdentity"
            )
        object.__setattr__(
            self,
            "power_off_attestation_sha256",
            _digest(self.power_off_attestation_sha256, "power_off_attestation_sha256"),
        )

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "expected_identity_sha256": self.expected_identity.identity_sha256,
                "power_off_attestation_sha256": self.power_off_attestation_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class UnpoweredArmIdentityReceipt:
    run_id: str
    provider_descriptor_sha256: str
    request_sha256: str
    power_off_attestation_sha256: str
    observed_identity: RoArmUsbSerialIdentity
    observed_monotonic_ns: int
    serial_port_opened: bool
    bytes_read: int
    bytes_written: int
    schema: str = field(
        default=ROARM_UNPOWERED_IDENTITY_RECEIPT_SCHEMA, init=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        for name in (
            "provider_descriptor_sha256",
            "request_sha256",
            "power_off_attestation_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.observed_identity, RoArmUsbSerialIdentity):
            raise PhysicalConnectionContractError(
                "observed_identity must be RoArmUsbSerialIdentity"
            )
        object.__setattr__(
            self,
            "observed_monotonic_ns",
            _bounded_int(self.observed_monotonic_ns, "observed_monotonic_ns", minimum=1),
        )
        if type(self.serial_port_opened) is not bool or self.serial_port_opened:
            raise PhysicalConnectionContractError(
                "unpowered arm identity inspection must not open the serial port"
            )
        if self.bytes_read != 0 or self.bytes_written != 0:
            raise PhysicalConnectionContractError(
                "unpowered arm identity inspection must perform no serial I/O"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_sha256": self.request_sha256,
            "power_off_attestation_sha256": self.power_off_attestation_sha256,
            "observed_identity": self.observed_identity.to_dict(),
            "observed_monotonic_ns": self.observed_monotonic_ns,
            "serial_port_opened": self.serial_port_opened,
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class SingleT105FeedbackRequest:
    run_id: str
    arm_identity_receipt_sha256: str
    arm_identity_sha256: str
    power_event_observation_sha256: str
    safety_permit_sha256: str
    controller_session_id: str
    requested_monotonic_ns: int
    maximum_line_bytes: int = MAX_FEEDBACK_LINE_BYTES

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "controller_session_id",
            _text(self.controller_session_id, "controller_session_id"),
        )
        for name in (
            "arm_identity_receipt_sha256",
            "arm_identity_sha256",
            "power_event_observation_sha256",
            "safety_permit_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "requested_monotonic_ns",
            _bounded_int(self.requested_monotonic_ns, "requested_monotonic_ns", minimum=1),
        )
        object.__setattr__(
            self,
            "maximum_line_bytes",
            _bounded_int(
                self.maximum_line_bytes,
                "maximum_line_bytes",
                minimum=64,
                maximum=MAX_FEEDBACK_LINE_BYTES,
            ),
        )

    @property
    def request_context_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "arm_identity_receipt_sha256": self.arm_identity_receipt_sha256,
                "arm_identity_sha256": self.arm_identity_sha256,
                "power_event_observation_sha256": self.power_event_observation_sha256,
                "safety_permit_sha256": self.safety_permit_sha256,
                "controller_session_id": self.controller_session_id,
                "requested_monotonic_ns": self.requested_monotonic_ns,
                "maximum_line_bytes": self.maximum_line_bytes,
                "request_type": "T=105",
            }
        )


@dataclass(frozen=True, slots=True)
class T105TransactionTiming:
    port_opened_monotonic_ns: int
    pre_request_buffer_observed_monotonic_ns: int
    request_write_started_monotonic_ns: int
    request_write_completed_monotonic_ns: int
    first_response_byte_monotonic_ns: int
    response_completed_monotonic_ns: int
    port_closed_monotonic_ns: int

    def __post_init__(self) -> None:
        names = (
            "port_opened_monotonic_ns",
            "pre_request_buffer_observed_monotonic_ns",
            "request_write_started_monotonic_ns",
            "request_write_completed_monotonic_ns",
            "first_response_byte_monotonic_ns",
            "response_completed_monotonic_ns",
            "port_closed_monotonic_ns",
        )
        values = tuple(
            _bounded_int(getattr(self, name), name, minimum=1) for name in names
        )
        if values != tuple(sorted(values)):
            raise PhysicalConnectionContractError(
                "T=105 transaction timestamps must be monotonically ordered"
            )

    def to_dict(self) -> dict[str, int]:
        return {
            name: getattr(self, name)
            for name in (
                "port_opened_monotonic_ns",
                "pre_request_buffer_observed_monotonic_ns",
                "request_write_started_monotonic_ns",
                "request_write_completed_monotonic_ns",
                "first_response_byte_monotonic_ns",
                "response_completed_monotonic_ns",
                "port_closed_monotonic_ns",
            )
        }


@dataclass(frozen=True, slots=True)
class SingleT105FeedbackReceipt:
    """Lossless evidence for exactly one feedback-only controller exchange."""

    run_id: str
    provider_descriptor_sha256: str
    request_context_sha256: str
    arm_identity_sha256: str
    controller_session_id: str
    timing: T105TransactionTiming
    pre_request_bytes_waiting: int
    post_response_bytes_waiting: int
    request_bytes: bytes
    response_bytes: bytes
    request_bytes_sha256: str
    response_bytes_sha256: str
    parsed_response_sha256: str
    write_attempts: int
    feedback_query_count: int
    retry_count: int
    t104_motion_count: int
    connection_closed: bool
    schema: str = field(default=ROARM_T105_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "controller_session_id",
            _text(self.controller_session_id, "controller_session_id"),
        )
        for name in (
            "provider_descriptor_sha256",
            "request_context_sha256",
            "arm_identity_sha256",
            "request_bytes_sha256",
            "response_bytes_sha256",
            "parsed_response_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.timing, T105TransactionTiming):
            raise PhysicalConnectionContractError(
                "timing must be T105TransactionTiming"
            )
        for name in ("pre_request_bytes_waiting", "post_response_bytes_waiting"):
            if _bounded_int(getattr(self, name), name, maximum=MAX_FEEDBACK_LINE_BYTES) != 0:
                raise PhysicalConnectionContractError(
                    "T=105 feedback cannot be correlated with buffered bytes present"
                )
        if not isinstance(self.request_bytes, bytes):
            raise PhysicalConnectionContractError("request_bytes must be immutable bytes")
        if not isinstance(self.response_bytes, bytes):
            raise PhysicalConnectionContractError("response_bytes must be immutable bytes")
        if self.request_bytes != encode_line(feedback_request()):
            raise PhysicalConnectionContractError(
                "feedback receipt request bytes must be exactly one T=105 line"
            )
        if not MIN_FEEDBACK_LINE_BYTES <= len(self.response_bytes) <= MAX_FEEDBACK_LINE_BYTES:
            raise PhysicalConnectionContractError(
                "T=1051 response line length is outside the retained-evidence bound"
            )
        if self.request_bytes_sha256 != _bytes_sha256(self.request_bytes):
            raise PhysicalConnectionContractError(
                "request_bytes_sha256 does not bind request_bytes"
            )
        if self.response_bytes_sha256 != _bytes_sha256(self.response_bytes):
            raise PhysicalConnectionContractError(
                "response_bytes_sha256 does not bind response_bytes"
            )
        try:
            parsed = validate_feedback_response_line(
                self.response_bytes, max_line_bytes=MAX_FEEDBACK_LINE_BYTES
            )
        except FeedbackWireError as exc:
            raise PhysicalConnectionContractError(
                f"response_bytes are not a valid T=1051 line: {exc}"
            ) from exc
        if self.parsed_response_sha256 != canonical_sha256(parsed):
            raise PhysicalConnectionContractError(
                "parsed_response_sha256 does not bind the lossless decoded response"
            )
        exact_counts = {
            "write_attempts": (self.write_attempts, 1),
            "feedback_query_count": (self.feedback_query_count, 1),
            "retry_count": (self.retry_count, 0),
            "t104_motion_count": (self.t104_motion_count, 0),
        }
        for name, (actual, expected) in exact_counts.items():
            if type(actual) is not int or actual != expected:
                raise PhysicalConnectionContractError(
                    f"{name} must be exactly {expected}"
                )
        if type(self.connection_closed) is not bool or not self.connection_closed:
            raise PhysicalConnectionContractError(
                "feedback-only serial connection must be closed in the receipt"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "request_context_sha256": self.request_context_sha256,
            "arm_identity_sha256": self.arm_identity_sha256,
            "controller_session_id": self.controller_session_id,
            "timing": self.timing.to_dict(),
            "pre_request_bytes_waiting": self.pre_request_bytes_waiting,
            "post_response_bytes_waiting": self.post_response_bytes_waiting,
            "request_bytes_hex": self.request_bytes.hex(),
            "response_bytes_hex": self.response_bytes.hex(),
            "request_bytes_sha256": self.request_bytes_sha256,
            "response_bytes_sha256": self.response_bytes_sha256,
            "parsed_response_sha256": self.parsed_response_sha256,
            "write_attempts": self.write_attempts,
            "feedback_query_count": self.feedback_query_count,
            "retry_count": self.retry_count,
            "t104_motion_count": self.t104_motion_count,
            "connection_closed": self.connection_closed,
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@runtime_checkable
class HostDependencyProvider(Protocol):
    @property
    def descriptor(self) -> ConnectionProviderDescriptor: ...

    def inspect_host_dependencies(
        self, request: HostDependencyRequest
    ) -> HostDependencyReceipt: ...


@runtime_checkable
class B0477ConnectionProvider(Protocol):
    """Narrow camera onboarding seam with no numeric-selector opening API."""

    @property
    def descriptor(self) -> ConnectionProviderDescriptor: ...

    def discover_exact_b0477(
        self, request: B0477DiscoveryRequest
    ) -> B0477DiscoveryReceipt: ...

    def open_selected_b0477(self, request: CameraOpenRequest) -> CameraSessionReceipt: ...

    def configure_exact_b0477(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt: ...

    def flush_b0477_buffers(self, request: CameraFlushRequest) -> CameraFlushReceipt: ...

    def capture_fresh_b0477_frame(
        self, request: FreshFrameRequest
    ) -> CapturedFrame: ...

    def close_selected_b0477(
        self, request: CameraCloseRequest
    ) -> CameraCloseReceipt: ...

    def reopen_exact_b0477(
        self, request: CameraReopenRequest
    ) -> CameraReopenReceipt: ...


@runtime_checkable
class FeedbackOnlyRoArmConnectionProvider(Protocol):
    """Arm connection seam: unpowered identity plus one T=105 transaction only."""

    @property
    def descriptor(self) -> ConnectionProviderDescriptor: ...

    def inspect_unpowered_usb_identity(
        self, request: UnpoweredArmIdentityRequest
    ) -> UnpoweredArmIdentityReceipt: ...

    def acquire_single_t105_feedback(
        self, request: SingleT105FeedbackRequest
    ) -> SingleT105FeedbackReceipt: ...


def _require_fake_descriptor(descriptor: ConnectionProviderDescriptor) -> None:
    if descriptor != FAKE_PROVIDER_DESCRIPTOR:
        raise FakeConnectionBoundaryError(
            "deterministic providers require the immutable synthetic descriptor"
        )


class DeterministicFakeHostDependencyProvider:
    """Zero-I/O provider for host-receipt orchestration tests."""

    descriptor = FAKE_PROVIDER_DESCRIPTOR

    def __init__(
        self,
        host: HostIdentity,
        observations: Mapping[str, DependencyObservation],
        *,
        first_monotonic_ns: int = 1_000_000,
    ) -> None:
        if not isinstance(host, HostIdentity):
            raise PhysicalConnectionContractError("host must be HostIdentity")
        self._host = host
        self._observations = dict(observations)
        self._clock = _bounded_int(first_monotonic_ns, "first_monotonic_ns", minimum=1)

    def inspect_host_dependencies(
        self, request: HostDependencyRequest
    ) -> HostDependencyReceipt:
        _require_fake_descriptor(self.descriptor)
        if not isinstance(request, HostDependencyRequest):
            raise PhysicalConnectionContractError(
                "request must be HostDependencyRequest"
            )
        names = tuple(item.name for item in request.requirements)
        if set(self._observations) != set(names):
            raise FakeConnectionBoundaryError(
                "fake observations must exactly cover the dependency request"
            )
        observations = tuple(self._observations[name] for name in names)
        if any(item.name != name for name, item in zip(names, observations)):
            raise FakeConnectionBoundaryError(
                "fake dependency observation keys do not bind their records"
            )
        all_available = all(
            _dependency_requirement_satisfied(requirement, observation)
            or not requirement.required
            for requirement, observation in zip(request.requirements, observations)
        )
        receipt = HostDependencyReceipt(
            run_id=request.run_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            source_tree_sha256=request.source_tree_sha256,
            host=self._host,
            requirements=request.requirements,
            observations=observations,
            observed_monotonic_ns=self._clock,
            all_required_available=all_available,
        )
        self._clock += 1
        return receipt


class DeterministicFakeB0477ConnectionProvider:
    """Stateful zero-I/O camera provider exercising discovery through reopen."""

    descriptor = FAKE_PROVIDER_DESCRIPTOR

    def __init__(
        self,
        identity: B0477UvcIdentity,
        *,
        first_monotonic_ns: int = 2_000_000,
    ) -> None:
        if not isinstance(identity, B0477UvcIdentity):
            raise PhysicalConnectionContractError("identity must be B0477UvcIdentity")
        self._identity = identity
        self._clock = _bounded_int(first_monotonic_ns, "first_monotonic_ns", minimum=1)
        self._session: CameraSessionReceipt | None = None
        self._configuration: B0477ExactConfiguration | None = None
        self._configuration_receipt: CameraConfigurationReceipt | None = None
        self._flush_receipt: CameraFlushReceipt | None = None
        self._session_ordinal = 0
        self._sequence = 0
        self._closed_session_ids: set[str] = set()

    def _tick(self) -> int:
        value = self._clock
        self._clock += 1
        return value

    def discover_exact_b0477(
        self, request: B0477DiscoveryRequest
    ) -> B0477DiscoveryReceipt:
        _require_fake_descriptor(self.descriptor)
        if request.expected_identity != self._identity:
            raise FakeConnectionBoundaryError(
                "observed camera does not exactly match expected persistent identity"
            )
        return B0477DiscoveryReceipt(
            run_id=request.run_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            observed_monotonic_ns=self._tick(),
            devices=(self._identity,),
            selected_identity_sha256=self._identity.identity_sha256,
            selected_persistent_os_path=self._identity.persistent_os_path,
            ordinal_fallback_used=False,
        )

    def open_selected_b0477(self, request: CameraOpenRequest) -> CameraSessionReceipt:
        _require_fake_descriptor(self.descriptor)
        if self._session is not None:
            raise FakeConnectionBoundaryError("camera session is already open")
        if request.identity != self._identity:
            raise FakeConnectionBoundaryError("camera open identity mismatch")
        self._session_ordinal += 1
        self._session = CameraSessionReceipt(
            run_id=request.run_id,
            session_id=f"{request.run_id}-camera-session-{self._session_ordinal}",
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            camera_identity_sha256=self._identity.identity_sha256,
            persistent_os_path=self._identity.persistent_os_path,
            session_ordinal=self._session_ordinal,
            opened_monotonic_ns=self._tick(),
        )
        return self._session

    def _require_session(self, run_id: str, session_id: str) -> CameraSessionReceipt:
        if self._session is None:
            raise FakeConnectionBoundaryError("no fake camera session is open")
        if self._session.run_id != run_id or self._session.session_id != session_id:
            raise FakeConnectionBoundaryError("camera session binding mismatch")
        return self._session

    def configure_exact_b0477(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt:
        self._require_session(request.run_id, request.session_id)
        if request.camera_identity_sha256 != self._identity.identity_sha256:
            raise FakeConnectionBoundaryError("camera configuration identity mismatch")
        self._configuration = request.desired
        self._configuration_receipt = CameraConfigurationReceipt(
            run_id=request.run_id,
            session_id=request.session_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            camera_identity_sha256=self._identity.identity_sha256,
            requested_configuration_sha256=request.desired.configuration_sha256,
            observed=request.desired,
            readback_monotonic_ns=self._tick(),
            fallback_negotiated=False,
        )
        self._flush_receipt = None
        return self._configuration_receipt

    def flush_b0477_buffers(self, request: CameraFlushRequest) -> CameraFlushReceipt:
        self._require_session(request.run_id, request.session_id)
        if self._configuration_receipt is None:
            raise FakeConnectionBoundaryError("camera must be configured before flush")
        if request.configuration_receipt_sha256 != (
            self._configuration_receipt.receipt_sha256
        ):
            raise FakeConnectionBoundaryError("flush configuration binding mismatch")
        start = self._tick()
        self._sequence += 4
        self._flush_receipt = CameraFlushReceipt(
            run_id=request.run_id,
            session_id=request.session_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            configuration_receipt_sha256=request.configuration_receipt_sha256,
            flush_started_monotonic_ns=start,
            flush_completed_monotonic_ns=self._tick(),
            discarded_frame_count=4,
            last_discarded_sequence=self._sequence,
            buffer_empty_after=True,
        )
        return self._flush_receipt

    def capture_fresh_b0477_frame(
        self, request: FreshFrameRequest
    ) -> CapturedFrame:
        self._require_session(request.run_id, request.session_id)
        if self._configuration is None or self._flush_receipt is None:
            raise FakeConnectionBoundaryError(
                "camera must be configured and flushed before fresh capture"
            )
        if request.flush_receipt_sha256 != self._flush_receipt.receipt_sha256:
            raise FakeConnectionBoundaryError("fresh-frame flush binding mismatch")
        if request.configuration_sha256 != self._configuration.configuration_sha256:
            raise FakeConnectionBoundaryError("fresh-frame configuration mismatch")
        self._sequence = max(self._sequence + 1, request.minimum_sequence_exclusive + 1)
        capture_started = max(self._tick(), request.requested_monotonic_ns)
        delivered = capture_started + 1
        if delivered - request.requested_monotonic_ns > request.maximum_latency_ns:
            raise FakeConnectionBoundaryError("fake frame exceeds requested latency bound")
        payload = _canonical_bytes(
            {
                "synthetic": True,
                "session_id": request.session_id,
                "sequence": self._sequence,
                "configuration_sha256": request.configuration_sha256,
            }
        )
        self._clock = max(self._clock, delivered + 1)
        receipt = FreshFrameReceipt(
            run_id=request.run_id,
            session_id=request.session_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            flush_receipt_sha256=request.flush_receipt_sha256,
            configuration_sha256=request.configuration_sha256,
            sequence=self._sequence,
            capture_started_monotonic_ns=capture_started,
            delivered_monotonic_ns=delivered,
            timing_basis=FrameTimingBasis.HOST_BRACKET,
            device_exposure_proof_sha256=None,
            retained_encoding=RetainedFrameEncoding.SYNTHETIC_CANONICAL_JSON,
            payload_bytes=len(payload),
            payload_sha256=_bytes_sha256(payload),
        )
        return CapturedFrame(receipt=receipt, payload=payload)

    def close_selected_b0477(
        self, request: CameraCloseRequest
    ) -> CameraCloseReceipt:
        _require_fake_descriptor(self.descriptor)
        if not isinstance(request, CameraCloseRequest):
            raise PhysicalConnectionContractError(
                "request must be CameraCloseRequest"
            )
        already_closed = request.session.session_id in self._closed_session_ids
        if not already_closed:
            if self._session != request.session:
                raise FakeConnectionBoundaryError("camera close session mismatch")
            close_attempted = True
            self._session = None
            self._configuration = None
            self._configuration_receipt = None
            self._flush_receipt = None
            self._closed_session_ids.add(request.session.session_id)
        else:
            close_attempted = False
        started = max(self._tick(), request.requested_monotonic_ns)
        completed = started + 1
        self._clock = max(self._clock, completed + 1)
        return CameraCloseReceipt(
            run_id=request.run_id,
            session_id=request.session.session_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            session_receipt_sha256=request.session.receipt_sha256,
            close_attempted=close_attempted,
            close_succeeded=True,
            was_already_closed=already_closed,
            close_started_monotonic_ns=started,
            close_completed_monotonic_ns=completed,
            failure_code=None,
        )

    def reopen_exact_b0477(
        self, request: CameraReopenRequest
    ) -> CameraReopenReceipt:
        if self._session is None or request.previous_session != self._session:
            raise FakeConnectionBoundaryError("camera reopen session mismatch")
        if request.expected_identity != self._identity:
            raise FakeConnectionBoundaryError("camera identity drifted on reopen")
        if self._configuration != request.expected_configuration:
            raise FakeConnectionBoundaryError("camera configuration drifted before reopen")
        previous = self._session
        close_receipt = self.close_selected_b0477(
            CameraCloseRequest(
                run_id=request.run_id,
                session=previous,
                reason="REOPEN_EXACT_IDENTITY_AND_CONFIGURATION",
                requested_monotonic_ns=self._clock,
            )
        )
        # Reopen immediately reapplies the exact requested configuration; the
        # prior session's state is retained in the request and close receipt.
        self._configuration = request.expected_configuration
        self._session_ordinal += 1
        reopened = CameraSessionReceipt(
            run_id=request.run_id,
            session_id=f"{request.run_id}-camera-session-{self._session_ordinal}",
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            camera_identity_sha256=self._identity.identity_sha256,
            persistent_os_path=self._identity.persistent_os_path,
            session_ordinal=self._session_ordinal,
            opened_monotonic_ns=self._tick(),
        )
        self._session = reopened
        config_request = CameraConfigurationRequest(
            run_id=request.run_id,
            session_receipt_sha256=reopened.receipt_sha256,
            camera_identity_sha256=self._identity.identity_sha256,
            session_id=reopened.session_id,
            desired=request.expected_configuration,
        )
        config = self.configure_exact_b0477(config_request)
        return CameraReopenReceipt(
            run_id=request.run_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            previous_session_id=previous.session_id,
            close_receipt=close_receipt,
            reopened_session=reopened,
            reopened_identity=self._identity,
            configuration_readback=config,
        )


class DeterministicFakeRoArmConnectionProvider:
    """Zero-I/O RoArm provider with a lifetime limit of one feedback query."""

    descriptor = FAKE_PROVIDER_DESCRIPTOR

    def __init__(
        self,
        identity: RoArmUsbSerialIdentity,
        response_bytes: bytes,
        *,
        first_monotonic_ns: int = 3_000_000,
        pre_request_bytes_waiting: int = 0,
        post_response_bytes_waiting: int = 0,
    ) -> None:
        if not isinstance(identity, RoArmUsbSerialIdentity):
            raise PhysicalConnectionContractError(
                "identity must be RoArmUsbSerialIdentity"
            )
        if not isinstance(response_bytes, bytes):
            raise PhysicalConnectionContractError("response_bytes must be bytes")
        self._identity = identity
        self._response_bytes = response_bytes
        self._clock = _bounded_int(first_monotonic_ns, "first_monotonic_ns", minimum=1)
        self._pre_waiting = _bounded_int(
            pre_request_bytes_waiting,
            "pre_request_bytes_waiting",
            maximum=MAX_FEEDBACK_LINE_BYTES,
        )
        self._post_waiting = _bounded_int(
            post_response_bytes_waiting,
            "post_response_bytes_waiting",
            maximum=MAX_FEEDBACK_LINE_BYTES,
        )
        self._identity_receipt: UnpoweredArmIdentityReceipt | None = None
        self._feedback_attempted = False

    def inspect_unpowered_usb_identity(
        self, request: UnpoweredArmIdentityRequest
    ) -> UnpoweredArmIdentityReceipt:
        _require_fake_descriptor(self.descriptor)
        if request.expected_identity != self._identity:
            raise FakeConnectionBoundaryError(
                "observed arm does not exactly match expected persistent identity"
            )
        receipt = UnpoweredArmIdentityReceipt(
            run_id=request.run_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_sha256=request.request_sha256,
            power_off_attestation_sha256=request.power_off_attestation_sha256,
            observed_identity=self._identity,
            observed_monotonic_ns=self._clock,
            serial_port_opened=False,
            bytes_read=0,
            bytes_written=0,
        )
        self._clock += 1
        self._identity_receipt = receipt
        return receipt

    def acquire_single_t105_feedback(
        self, request: SingleT105FeedbackRequest
    ) -> SingleT105FeedbackReceipt:
        _require_fake_descriptor(self.descriptor)
        if self._feedback_attempted:
            raise FakeConnectionBoundaryError(
                "the one-shot T=105 transaction was already attempted; retry prohibited"
            )
        # Mark attempted before any validation that conceptually follows port
        # ownership.  A malformed response cannot be turned into an auto-retry.
        self._feedback_attempted = True
        if self._identity_receipt is None:
            raise FakeConnectionBoundaryError(
                "unpowered arm identity must be inspected before feedback"
            )
        if request.arm_identity_receipt_sha256 != self._identity_receipt.receipt_sha256:
            raise FakeConnectionBoundaryError("arm identity receipt binding mismatch")
        if request.arm_identity_sha256 != self._identity.identity_sha256:
            raise FakeConnectionBoundaryError("arm identity digest mismatch")
        start = max(self._clock, request.requested_monotonic_ns)
        timing = T105TransactionTiming(*(start + offset for offset in range(7)))
        self._clock = start + 7
        request_bytes = encode_line(feedback_request())
        try:
            parsed = validate_feedback_response_line(
                self._response_bytes,
                max_line_bytes=request.maximum_line_bytes,
            )
        except FeedbackWireError as exc:
            raise FakeConnectionBoundaryError(
                f"deterministic T=1051 response is invalid: {exc}"
            ) from exc
        return SingleT105FeedbackReceipt(
            run_id=request.run_id,
            provider_descriptor_sha256=self.descriptor.descriptor_sha256,
            request_context_sha256=request.request_context_sha256,
            arm_identity_sha256=self._identity.identity_sha256,
            controller_session_id=request.controller_session_id,
            timing=timing,
            pre_request_bytes_waiting=self._pre_waiting,
            post_response_bytes_waiting=self._post_waiting,
            request_bytes=request_bytes,
            response_bytes=self._response_bytes,
            request_bytes_sha256=_bytes_sha256(request_bytes),
            response_bytes_sha256=_bytes_sha256(self._response_bytes),
            parsed_response_sha256=canonical_sha256(parsed),
            write_attempts=1,
            feedback_query_count=1,
            retry_count=0,
            t104_motion_count=0,
            connection_closed=True,
        )


__all__ = [
    "B0477_CLOSE_RECEIPT_SCHEMA",
    "B0477_CONFIGURATION_RECEIPT_SCHEMA",
    "B0477_DISCOVERY_RECEIPT_SCHEMA",
    "B0477_FLUSH_RECEIPT_SCHEMA",
    "B0477_FRAME_RECEIPT_SCHEMA",
    "B0477_REOPEN_RECEIPT_SCHEMA",
    "CAPTURED_FRAME_SCHEMA",
    "HOST_DEPENDENCY_RECEIPT_SCHEMA",
    "ROARM_T105_RECEIPT_SCHEMA",
    "ROARM_UNPOWERED_IDENTITY_RECEIPT_SCHEMA",
    "B0477ConnectionProvider",
    "B0477DiscoveryReceipt",
    "B0477DiscoveryRequest",
    "B0477ExactConfiguration",
    "B0477ManualControls",
    "B0477NativeMode",
    "B0477UvcIdentity",
    "CameraCloseReceipt",
    "CameraCloseRequest",
    "CameraConfigurationReceipt",
    "CameraConfigurationRequest",
    "CameraFlushReceipt",
    "CameraFlushRequest",
    "CameraOpenRequest",
    "CameraReopenReceipt",
    "CameraReopenRequest",
    "CameraSessionReceipt",
    "CapturedFrame",
    "ConnectionProviderDescriptor",
    "DependencyObservation",
    "DependencyRequirement",
    "DeterministicFakeB0477ConnectionProvider",
    "DeterministicFakeHostDependencyProvider",
    "DeterministicFakeRoArmConnectionProvider",
    "EvidenceOrigin",
    "FAKE_PROVIDER_DESCRIPTOR",
    "FakeConnectionBoundaryError",
    "FeedbackOnlyRoArmConnectionProvider",
    "FrameTimingBasis",
    "FreshFrameReceipt",
    "FreshFrameRequest",
    "HostDependencyProvider",
    "HostDependencyReceipt",
    "HostDependencyRequest",
    "HostIdentity",
    "MAX_FEEDBACK_LINE_BYTES",
    "MAX_IMMUTABLE_FRAME_BYTES",
    "PhysicalConnectionContractError",
    "RoArmUsbSerialIdentity",
    "RetainedFrameEncoding",
    "SingleT105FeedbackReceipt",
    "SingleT105FeedbackRequest",
    "T105TransactionTiming",
    "UnpoweredArmIdentityReceipt",
    "UnpoweredArmIdentityRequest",
    "Usb3Topology",
    "UsbDriverIdentity",
    "canonical_sha256",
]
