"""Execution-shaped, zero-authority onboarding contract for fake providers.

This module rehearses the *shape* of the future physical commissioning runner
without sharing an enable switch with it.  Every accepted provider is the exact
module-issued deterministic fake type and every result owns an immutable
zero-release authority record.  The provider protocols intentionally contain
no motion, contact, or generic serial-write method.  The only arm exchange they
expose is one identity-bound, feedback-only ``T=105`` request.

The exact-type and module-token checks are structural Python safeguards, not a
security sandbox: Python process introspection can bypass them.  Any future
physical validation process must additionally run under OS-enforced denial of
camera, USB, serial, and network-device access until separately reviewed live
adapters and explicit physical authority exist.

The ordered workflow is deliberately conservative:

1. inspect the received camera label/receipt;
2. enumerate it and bind a persistent OS selection key;
3. apply and read back one exact capture configuration;
4. flush buffered frames and prove fresh, monotonic captures;
5. reopen the selected device and re-prove identity/configuration;
6. acquire receipts for a retained-install calibration dataset;
7. inspect arm identity while arm power is reported off;
8. collect procedure-shaped (not physically proven) safety evidence;
9. bind the exact safety receipt into a synthetic zero-command power event; and
10. create one in-memory controller session, prove its synthetic input buffer
    empty, and bind that complete chain into exactly one ``T=105``/``T=1051``
    exchange.

Failures stop at their boundary and always attempt cleanup.  This is a contract
test seam: future live adapters can implement analogous protocols in a separate
physical package only after explicit safety review.  They cannot be passed to
this runner because its metadata validator accepts fake providers exclusively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Protocol, final, runtime_checkable


PHYSICAL_SHAPED_ONBOARDING_CONTRACT = "rocell.physical_shaped_onboarding.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODULE_FAKE_PROVIDER_TOKEN = object()


class PhysicalShapedOnboardingError(ValueError):
    """A provider result or workflow invariant failed closed."""


class FakeProviderBoundaryError(RuntimeError):
    """A deterministic fake provider failed at an injected boundary."""

    def __init__(self, boundary: "FakeBoundary") -> None:
        self.boundary = boundary
        super().__init__(f"injected fake-provider fault at {boundary.value}")


def _text(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value:
        raise PhysicalShapedOnboardingError(f"{label} must be non-empty text")
    if value != value.strip():
        raise PhysicalShapedOnboardingError(
            f"{label} must not have surrounding whitespace"
        )
    if len(value) > maximum:
        raise PhysicalShapedOnboardingError(
            f"{label} exceeds {maximum} characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise PhysicalShapedOnboardingError(f"{label} contains a control character")
    return value


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = (1 << 63) - 1,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PhysicalShapedOnboardingError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise PhysicalShapedOnboardingError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PhysicalShapedOnboardingError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _immutable_bytes(value: object, label: str, *, maximum: int = 65_536) -> bytes:
    """Accept retained protocol evidence only as bounded immutable bytes."""

    if type(value) is not bytes:
        raise PhysicalShapedOnboardingError(f"{label} must be immutable bytes")
    if not value:
        raise PhysicalShapedOnboardingError(f"{label} must not be empty")
    if len(value) > maximum:
        raise PhysicalShapedOnboardingError(
            f"{label} exceeds {maximum} retained bytes"
        )
    return value


def _finite_number(value: object, label: str) -> float:
    """Parse a JSON numeric field without accepting booleans or NaN/Inf."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PhysicalShapedOnboardingError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PhysicalShapedOnboardingError(f"{label} must be finite")
    return parsed


def _safe_error_text(value: object, *, fallback: str, maximum: int) -> str:
    """Bound arbitrary provider exception text so failure reporting cannot fail."""

    try:
        rendered = str(value)
    except Exception:
        rendered = fallback
    rendered = "".join(
        character if 32 <= ord(character) != 127 else "?"
        for character in rendered
    ).strip()
    if not rendered:
        rendered = fallback
    return rendered[:maximum]


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _unique_text_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise PhysicalShapedOnboardingError(f"{label} must be an immutable tuple")
    parsed = tuple(_text(item, f"{label} item") for item in value)
    if len(parsed) != len(set(parsed)):
        raise PhysicalShapedOnboardingError(f"{label} contains a duplicate")
    return parsed


class FakeBoundary(str, Enum):
    """Every callable boundary in the fake provider surface."""

    CAMERA_RECEIPT = "CAMERA_RECEIPT"
    CAMERA_INVENTORY = "CAMERA_INVENTORY"
    CAMERA_OPEN = "CAMERA_OPEN"
    CAMERA_APPLY_CONFIGURATION = "CAMERA_APPLY_CONFIGURATION"
    CAMERA_READBACK = "CAMERA_READBACK"
    CAMERA_FLUSH = "CAMERA_FLUSH"
    CAMERA_CAPTURE = "CAMERA_CAPTURE"
    CAMERA_REOPEN = "CAMERA_REOPEN"
    CALIBRATION_ACQUISITION = "CALIBRATION_ACQUISITION"
    ARM_IDENTITY_OFF = "ARM_IDENTITY_OFF"
    SAFETY_EVIDENCE = "SAFETY_EVIDENCE"
    POWER_EVENT = "POWER_EVENT"
    CONTROLLER_SESSION = "CONTROLLER_SESSION"
    INPUT_BUFFER_EMPTY = "INPUT_BUFFER_EMPTY"
    T105_FEEDBACK = "T105_FEEDBACK"
    ACCOUNTING = "ACCOUNTING"
    CLEANUP = "CLEANUP"


class OnboardingStage(str, Enum):
    """Ordered diagnostic stages; cleanup is reported independently."""

    CAMERA_RECEIPT = "CAMERA_RECEIPT"
    CAMERA_INVENTORY_SELECTION = "CAMERA_INVENTORY_SELECTION"
    CAMERA_MODE_CONTROL = "CAMERA_MODE_CONTROL"
    CAMERA_BUFFER_FRESHNESS = "CAMERA_BUFFER_FRESHNESS"
    CAMERA_RECONNECT_IDENTITY = "CAMERA_RECONNECT_IDENTITY"
    RETAINED_INSTALL_CALIBRATION_ACQUISITION = (
        "RETAINED_INSTALL_CALIBRATION_ACQUISITION"
    )
    ARM_IDENTITY_WHILE_OFF = "ARM_IDENTITY_WHILE_OFF"
    SAFETY_EVIDENCE = "SAFETY_EVIDENCE"
    POWER_EVENT_OBSERVATION = "POWER_EVENT_OBSERVATION"
    SINGLE_T105_FEEDBACK = "SINGLE_T105_FEEDBACK"


ORDERED_ONBOARDING_STAGES = tuple(OnboardingStage)


class StageStatus(str, Enum):
    PASSED = "PASSED"
    FAILED_CLOSED = "FAILED_CLOSED"


class WorkflowStatus(str, Enum):
    COMPLETE = "SIMULATED_PROVIDER_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED"
    FAILED = "SIMULATED_PROVIDER_WORKFLOW_FAILED_CLOSED"
    CLEANUP_UNCONFIRMED = "SIMULATED_PROVIDER_WORKFLOW_FAILED_CLEANUP_UNCONFIRMED"


class OnboardingErrorPhase(str, Enum):
    """Boundary at which a structured failure was observed."""

    WORKFLOW = "WORKFLOW"
    CLEANUP = "CLEANUP"
    POST_RUN_ACCOUNTING = "POST_RUN_ACCOUNTING"


@dataclass(frozen=True, slots=True)
class OnboardingErrorRecord:
    """Stable failure evidence retained even when later reporting also fails."""

    phase: OnboardingErrorPhase
    detail_code: str
    exception_type: str
    message: str
    stage: OnboardingStage | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.phase, OnboardingErrorPhase):
            raise PhysicalShapedOnboardingError("error phase is unsupported")
        if self.stage is not None and not isinstance(self.stage, OnboardingStage):
            raise PhysicalShapedOnboardingError("error stage is unsupported")
        if self.phase is OnboardingErrorPhase.WORKFLOW and self.stage is None:
            raise PhysicalShapedOnboardingError(
                "workflow error records require an onboarding stage"
            )
        if self.phase is not OnboardingErrorPhase.WORKFLOW and self.stage is not None:
            raise PhysicalShapedOnboardingError(
                "cleanup/accounting error records cannot claim a workflow stage"
            )
        object.__setattr__(
            self,
            "detail_code",
            _text(self.detail_code, "error detail_code", maximum=128),
        )
        object.__setattr__(
            self,
            "exception_type",
            _text(self.exception_type, "exception_type", maximum=128),
        )
        object.__setattr__(
            self,
            "message",
            _text(self.message, "error message", maximum=512),
        )


@dataclass(frozen=True, slots=True)
class UntrustedSyntheticSequenceStamp:
    """Deterministic ordering witness with explicitly zero physical-time value.

    The nonce is an unkeyed content digest and the timestamp is a logical test
    value.  They detect accidental/substitution errors inside this fake runner;
    neither authenticates hardware nor establishes real elapsed time.
    """

    run_id: str
    purpose: str
    chain_ordinal: int
    logical_ns: int
    predecessor_sha256: str
    nonce: str
    evidence_origin: str = field(default="UNTRUSTED_SYNTHETIC_SEQUENCE", init=False)
    physical_time_valid: bool = field(default=False, init=False)
    cryptographic_authentication: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "stamp run_id"))
        object.__setattr__(
            self, "purpose", _text(self.purpose, "stamp purpose", maximum=64)
        )
        object.__setattr__(
            self,
            "chain_ordinal",
            _integer(self.chain_ordinal, "stamp chain_ordinal", minimum=1, maximum=64),
        )
        object.__setattr__(
            self,
            "logical_ns",
            _integer(self.logical_ns, "stamp logical_ns", minimum=1),
        )
        object.__setattr__(
            self,
            "predecessor_sha256",
            _digest(self.predecessor_sha256, "stamp predecessor_sha256"),
        )
        object.__setattr__(self, "nonce", _digest(self.nonce, "stamp nonce"))
        expected_logical_ns = _TAIL_LOGICAL_EPOCH_NS + self.chain_ordinal * 1_000
        if self.logical_ns != expected_logical_ns:
            raise PhysicalShapedOnboardingError(
                "synthetic sequence stamp logical_ns mismatch"
            )
        expected_nonce = _canonical_digest(
            {
                "contract": PHYSICAL_SHAPED_ONBOARDING_CONTRACT,
                "warning": "UNTRUSTED_SYNTHETIC_NOT_PHYSICAL_TIME_OR_AUTHENTICATION",
                "run_id": self.run_id,
                "purpose": self.purpose,
                "chain_ordinal": self.chain_ordinal,
                "logical_ns": self.logical_ns,
                "predecessor_sha256": self.predecessor_sha256,
            }
        )
        if self.nonce != expected_nonce:
            raise PhysicalShapedOnboardingError(
                "synthetic sequence stamp nonce mismatch"
            )

    @property
    def stamp_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "purpose": self.purpose,
                "chain_ordinal": self.chain_ordinal,
                "logical_ns": self.logical_ns,
                "predecessor_sha256": self.predecessor_sha256,
                "nonce": self.nonce,
                "evidence_origin": self.evidence_origin,
                "physical_time_valid": self.physical_time_valid,
                "cryptographic_authentication": self.cryptographic_authentication,
            }
        )


_TAIL_LOGICAL_EPOCH_NS = 9_000_000_000


def _synthetic_tail_stamp(
    run_id: str,
    purpose: str,
    chain_ordinal: int,
    predecessor_sha256: str,
) -> UntrustedSyntheticSequenceStamp:
    """Issue the one deterministic, untrusted stamp for a tail-chain link."""

    logical_ns = _TAIL_LOGICAL_EPOCH_NS + chain_ordinal * 1_000
    nonce = _canonical_digest(
        {
            "contract": PHYSICAL_SHAPED_ONBOARDING_CONTRACT,
            "warning": "UNTRUSTED_SYNTHETIC_NOT_PHYSICAL_TIME_OR_AUTHENTICATION",
            "run_id": run_id,
            "purpose": purpose,
            "chain_ordinal": chain_ordinal,
            "logical_ns": logical_ns,
            "predecessor_sha256": predecessor_sha256,
        }
    )
    return UntrustedSyntheticSequenceStamp(
        run_id=run_id,
        purpose=purpose,
        chain_ordinal=chain_ordinal,
        logical_ns=logical_ns,
        predecessor_sha256=predecessor_sha256,
        nonce=nonce,
    )


def _synthetic_tail_identifier(
    run_id: str, purpose: str, predecessor_sha256: str
) -> str:
    """Return a deterministic fake identifier bound to one predecessor."""

    suffix = _canonical_digest(
        {
            "contract": PHYSICAL_SHAPED_ONBOARDING_CONTRACT,
            "run_id": run_id,
            "purpose": purpose,
            "predecessor_sha256": predecessor_sha256,
        }
    )[:20]
    return f"synthetic-{purpose.lower().replace('_', '-')}-{suffix}"


@dataclass(frozen=True, slots=True)
class SyntheticZeroReleaseAuthority:
    """Authority fields are constants and therefore cannot express release."""

    execution_environment: str = field(
        default="EXPLICIT_FAKE_PROVIDER", init=False
    )
    hardware_accessed: bool = field(default=False, init=False)
    live_capture_performed: bool = field(default=False, init=False)
    hardware_commands_generated: int = field(default=0, init=False)
    t104_motion_commands_generated: int = field(default=0, init=False)
    robot_motion_authority: bool = field(default=False, init=False)
    contact_authority: bool = field(default=False, init=False)
    physical_calibration_authority: bool = field(default=False, init=False)
    physical_release_effect: str = field(default="NONE", init=False)


@dataclass(frozen=True, slots=True)
class FakeProviderDescriptor:
    """Identity accepted by this runner; provider kind is not configurable."""

    run_id: str
    provider_id: str
    provider_kind: str = field(default="EXPLICIT_FAKE", init=False)
    authority: SyntheticZeroReleaseAuthority = field(
        default_factory=SyntheticZeroReleaseAuthority, init=False
    )
    contract: str = field(
        default=PHYSICAL_SHAPED_ONBOARDING_CONTRACT, init=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))


@dataclass(frozen=True, slots=True)
class CameraIdentity:
    manufacturer: str
    model: str
    sensor: str
    lens: str
    unit_serial: str
    persistent_selection_key: str

    def __post_init__(self) -> None:
        for name in (
            "manufacturer",
            "model",
            "sensor",
            "lens",
            "unit_serial",
            "persistent_selection_key",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

    @property
    def identity_sha256(self) -> str:
        return _canonical_digest(
            {
                "manufacturer": self.manufacturer,
                "model": self.model,
                "sensor": self.sensor,
                "lens": self.lens,
                "unit_serial": self.unit_serial,
                "persistent_selection_key": self.persistent_selection_key,
            }
        )


@dataclass(frozen=True, slots=True)
class CameraMode:
    width_px: int
    height_px: int
    fps_numerator: int
    fps_denominator: int
    pixel_format: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "width_px", _integer(self.width_px, "width_px", minimum=1, maximum=16_384)
        )
        object.__setattr__(
            self,
            "height_px",
            _integer(self.height_px, "height_px", minimum=1, maximum=16_384),
        )
        object.__setattr__(
            self,
            "fps_numerator",
            _integer(self.fps_numerator, "fps_numerator", minimum=1, maximum=1_000),
        )
        object.__setattr__(
            self,
            "fps_denominator",
            _integer(self.fps_denominator, "fps_denominator", minimum=1, maximum=1_000),
        )
        object.__setattr__(
            self, "pixel_format", _text(self.pixel_format, "pixel_format", maximum=32)
        )


@dataclass(frozen=True, slots=True, order=True)
class CameraControlSetting:
    name: str
    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "control name", maximum=64))
        object.__setattr__(
            self,
            "value",
            _integer(self.value, f"control {self.name} value", maximum=1_000_000_000),
        )


@dataclass(frozen=True, slots=True)
class ExactCameraConfiguration:
    mode: CameraMode
    controls: tuple[CameraControlSetting, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mode, CameraMode):
            raise PhysicalShapedOnboardingError("mode must be CameraMode")
        if not isinstance(self.controls, tuple) or not self.controls:
            raise PhysicalShapedOnboardingError(
                "controls must be a non-empty immutable tuple"
            )
        if any(not isinstance(item, CameraControlSetting) for item in self.controls):
            raise PhysicalShapedOnboardingError(
                "controls must contain CameraControlSetting records"
            )
        if tuple(sorted(self.controls)) != self.controls:
            raise PhysicalShapedOnboardingError("controls must be sorted by name/value")
        names = tuple(item.name for item in self.controls)
        if len(names) != len(set(names)):
            raise PhysicalShapedOnboardingError("controls contains a duplicate name")

    @property
    def configuration_sha256(self) -> str:
        return _canonical_digest(
            {
                "mode": {
                    "width_px": self.mode.width_px,
                    "height_px": self.mode.height_px,
                    "fps_numerator": self.mode.fps_numerator,
                    "fps_denominator": self.mode.fps_denominator,
                    "pixel_format": self.mode.pixel_format,
                },
                "controls": [
                    {"name": item.name, "value": item.value}
                    for item in self.controls
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class ArmIdentityExpectation:
    product: str
    controller: str
    protocol_family: str

    def __post_init__(self) -> None:
        for name in ("product", "controller", "protocol_family"):
            object.__setattr__(self, name, _text(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class PhysicalShapedOnboardingRequest:
    """Expected values are test inputs, never physical commissioning evidence."""

    run_id: str
    expected_camera: CameraIdentity
    exact_camera_configuration: ExactCameraConfiguration
    retained_install_id: str
    calibration_frame_count: int
    calibration_training_frame_count: int
    calibration_held_out_frame_count: int
    freshness_frame_count: int
    expected_arm: ArmIdentityExpectation

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.expected_camera, CameraIdentity):
            raise PhysicalShapedOnboardingError(
                "expected_camera must be CameraIdentity"
            )
        if not isinstance(self.exact_camera_configuration, ExactCameraConfiguration):
            raise PhysicalShapedOnboardingError(
                "exact_camera_configuration must be ExactCameraConfiguration"
            )
        object.__setattr__(
            self,
            "retained_install_id",
            _text(self.retained_install_id, "retained_install_id"),
        )
        object.__setattr__(
            self,
            "calibration_frame_count",
            _integer(
                self.calibration_frame_count,
                "calibration_frame_count",
                minimum=3,
                maximum=10_000,
            ),
        )
        object.__setattr__(
            self,
            "calibration_training_frame_count",
            _integer(
                self.calibration_training_frame_count,
                "calibration_training_frame_count",
                minimum=2,
                maximum=9_999,
            ),
        )
        object.__setattr__(
            self,
            "calibration_held_out_frame_count",
            _integer(
                self.calibration_held_out_frame_count,
                "calibration_held_out_frame_count",
                minimum=1,
                maximum=9_998,
            ),
        )
        if (
            self.calibration_training_frame_count
            + self.calibration_held_out_frame_count
            != self.calibration_frame_count
        ):
            raise PhysicalShapedOnboardingError(
                "calibration training/held-out counts must sum to the frame count"
            )
        object.__setattr__(
            self,
            "freshness_frame_count",
            _integer(
                self.freshness_frame_count,
                "freshness_frame_count",
                minimum=2,
                maximum=32,
            ),
        )
        if not isinstance(self.expected_arm, ArmIdentityExpectation):
            raise PhysicalShapedOnboardingError(
                "expected_arm must be ArmIdentityExpectation"
            )


@dataclass(frozen=True, slots=True)
class CameraReceiptRequest:
    run_id: str
    expected_identity_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "expected_identity_sha256",
            _digest(self.expected_identity_sha256, "expected_identity_sha256"),
        )


@dataclass(frozen=True, slots=True)
class CameraReceiptObservation:
    run_id: str
    identity: CameraIdentity
    label_image_sha256: str
    packaging_record_sha256: str
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)
    physical_receipt_verified: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.identity, CameraIdentity):
            raise PhysicalShapedOnboardingError("identity must be CameraIdentity")
        object.__setattr__(
            self,
            "label_image_sha256",
            _digest(self.label_image_sha256, "label_image_sha256"),
        )
        object.__setattr__(
            self,
            "packaging_record_sha256",
            _digest(self.packaging_record_sha256, "packaging_record_sha256"),
        )


@dataclass(frozen=True, slots=True)
class CameraInventoryRequest:
    run_id: str
    persistent_selection_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "persistent_selection_key",
            _text(self.persistent_selection_key, "persistent_selection_key"),
        )


@dataclass(frozen=True, slots=True)
class CameraInventoryObservation:
    run_id: str
    discovered_keys: tuple[str, ...]
    selected_key: str
    selected_identity_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "discovered_keys",
            _unique_text_tuple(self.discovered_keys, "discovered_keys"),
        )
        object.__setattr__(self, "selected_key", _text(self.selected_key, "selected_key"))
        object.__setattr__(
            self,
            "selected_identity_sha256",
            _digest(self.selected_identity_sha256, "selected_identity_sha256"),
        )


@dataclass(frozen=True, slots=True)
class CameraSessionReceipt:
    run_id: str
    session_id: str
    persistent_selection_key: str
    identity_sha256: str

    def __post_init__(self) -> None:
        for name in ("run_id", "session_id", "persistent_selection_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self, "identity_sha256", _digest(self.identity_sha256, "identity_sha256")
        )


@dataclass(frozen=True, slots=True)
class CameraConfigurationRequest:
    run_id: str
    session_id: str
    configuration: ExactCameraConfiguration

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        if not isinstance(self.configuration, ExactCameraConfiguration):
            raise PhysicalShapedOnboardingError(
                "configuration must be ExactCameraConfiguration"
            )


@dataclass(frozen=True, slots=True)
class CameraConfigurationReceipt:
    run_id: str
    session_id: str
    configuration: ExactCameraConfiguration
    requested_configuration_sha256: str
    fallback_negotiated: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        if not isinstance(self.configuration, ExactCameraConfiguration):
            raise PhysicalShapedOnboardingError(
                "configuration must be ExactCameraConfiguration"
            )
        object.__setattr__(
            self,
            "requested_configuration_sha256",
            _digest(
                self.requested_configuration_sha256,
                "requested_configuration_sha256",
            ),
        )
        if not isinstance(self.fallback_negotiated, bool):
            raise PhysicalShapedOnboardingError("fallback_negotiated must be boolean")


@dataclass(frozen=True, slots=True)
class CaptureBufferRequest:
    run_id: str
    session_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))


@dataclass(frozen=True, slots=True)
class BufferFlushReceipt:
    run_id: str
    session_id: str
    discarded_frame_count: int
    last_discarded_sequence: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(
            self,
            "discarded_frame_count",
            _integer(
                self.discarded_frame_count,
                "discarded_frame_count",
                minimum=1,
                maximum=1_000_000,
            ),
        )
        object.__setattr__(
            self,
            "last_discarded_sequence",
            _integer(self.last_discarded_sequence, "last_discarded_sequence"),
        )


@dataclass(frozen=True, slots=True)
class FreshFrameRequest:
    run_id: str
    session_id: str
    minimum_sequence_exclusive: int
    configuration_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(
            self,
            "minimum_sequence_exclusive",
            _integer(self.minimum_sequence_exclusive, "minimum_sequence_exclusive"),
        )
        object.__setattr__(
            self,
            "configuration_sha256",
            _digest(self.configuration_sha256, "configuration_sha256"),
        )


@dataclass(frozen=True, slots=True)
class FreshFrameReceipt:
    run_id: str
    session_id: str
    sequence: int
    monotonic_ns: int
    configuration_sha256: str
    payload_sha256: str
    payload_bytes: int
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(self, "sequence", _integer(self.sequence, "sequence"))
        object.__setattr__(
            self, "monotonic_ns", _integer(self.monotonic_ns, "monotonic_ns", minimum=1)
        )
        object.__setattr__(
            self,
            "configuration_sha256",
            _digest(self.configuration_sha256, "configuration_sha256"),
        )
        object.__setattr__(
            self, "payload_sha256", _digest(self.payload_sha256, "payload_sha256")
        )
        object.__setattr__(
            self,
            "payload_bytes",
            _integer(self.payload_bytes, "payload_bytes", minimum=1, maximum=256_000_000),
        )


@dataclass(frozen=True, slots=True)
class CameraReopenRequest:
    run_id: str
    previous_session_id: str
    persistent_selection_key: str
    expected_configuration_sha256: str

    def __post_init__(self) -> None:
        for name in ("run_id", "previous_session_id", "persistent_selection_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "expected_configuration_sha256",
            _digest(
                self.expected_configuration_sha256,
                "expected_configuration_sha256",
            ),
        )


@dataclass(frozen=True, slots=True)
class CameraReconnectReceipt:
    run_id: str
    previous_session_id: str
    reopened_session: CameraSessionReceipt
    configuration_readback: CameraConfigurationReceipt

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "previous_session_id",
            _text(self.previous_session_id, "previous_session_id"),
        )
        if not isinstance(self.reopened_session, CameraSessionReceipt):
            raise PhysicalShapedOnboardingError(
                "reopened_session must be CameraSessionReceipt"
            )
        if not isinstance(self.configuration_readback, CameraConfigurationReceipt):
            raise PhysicalShapedOnboardingError(
                "configuration_readback must be CameraConfigurationReceipt"
            )


@dataclass(frozen=True, slots=True)
class CalibrationAcquisitionRequest:
    run_id: str
    camera_session_id: str
    retained_install_id: str
    camera_identity_sha256: str
    configuration_sha256: str
    required_frame_count: int
    training_frame_count: int
    held_out_frame_count: int

    def __post_init__(self) -> None:
        for name in ("run_id", "camera_session_id", "retained_install_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("camera_identity_sha256", "configuration_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "required_frame_count",
            _integer(self.required_frame_count, "required_frame_count", minimum=3),
        )
        object.__setattr__(
            self,
            "training_frame_count",
            _integer(self.training_frame_count, "training_frame_count", minimum=2),
        )
        object.__setattr__(
            self,
            "held_out_frame_count",
            _integer(self.held_out_frame_count, "held_out_frame_count", minimum=1),
        )
        if self.training_frame_count + self.held_out_frame_count != self.required_frame_count:
            raise PhysicalShapedOnboardingError(
                "calibration acquisition split must cover every required frame"
            )


@dataclass(frozen=True, slots=True)
class CalibrationAcquisitionReceipt:
    run_id: str
    camera_session_id: str
    retained_install_id: str
    camera_identity_sha256: str
    configuration_sha256: str
    frame_receipt_sha256s: tuple[str, ...]
    training_frame_receipt_sha256s: tuple[str, ...]
    held_out_frame_receipt_sha256s: tuple[str, ...]
    mount_witness_sha256: str
    lighting_witness_sha256: str
    focus_lock_witness_sha256: str
    aperture_lock_witness_sha256: str
    cable_route_witness_sha256: str
    dataset_sha256: str
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)
    physical_calibration_valid: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("run_id", "camera_session_id", "retained_install_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "camera_identity_sha256",
            "configuration_sha256",
            "mount_witness_sha256",
            "lighting_witness_sha256",
            "focus_lock_witness_sha256",
            "aperture_lock_witness_sha256",
            "cable_route_witness_sha256",
            "dataset_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.frame_receipt_sha256s, tuple):
            raise PhysicalShapedOnboardingError(
                "frame_receipt_sha256s must be an immutable tuple"
            )
        parsed = tuple(
            _digest(item, "frame_receipt_sha256")
            for item in self.frame_receipt_sha256s
        )
        if len(parsed) != len(set(parsed)):
            raise PhysicalShapedOnboardingError(
                "frame_receipt_sha256s contains a duplicate"
            )
        object.__setattr__(self, "frame_receipt_sha256s", parsed)
        for name in (
            "training_frame_receipt_sha256s",
            "held_out_frame_receipt_sha256s",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise PhysicalShapedOnboardingError(
                    f"{name} must be an immutable tuple"
                )
            normalized = tuple(_digest(item, name) for item in value)
            if len(normalized) != len(set(normalized)):
                raise PhysicalShapedOnboardingError(f"{name} contains a duplicate")
            object.__setattr__(self, name, normalized)
        if (
            self.training_frame_receipt_sha256s
            + self.held_out_frame_receipt_sha256s
            != self.frame_receipt_sha256s
        ):
            raise PhysicalShapedOnboardingError(
                "training and held-out receipts must be an exact precommitted split"
            )


@dataclass(frozen=True, slots=True)
class ArmIdentityRequest:
    run_id: str
    expected_product: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self, "expected_product", _text(self.expected_product, "expected_product")
        )


@dataclass(frozen=True, slots=True)
class ArmIdentityObservation:
    run_id: str
    product: str
    controller: str
    protocol_family: str
    unit_serial: str
    arm_power_observed_off: bool
    identity_sha256: str
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        for name in (
            "run_id",
            "product",
            "controller",
            "protocol_family",
            "unit_serial",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if not isinstance(self.arm_power_observed_off, bool):
            raise PhysicalShapedOnboardingError(
                "arm_power_observed_off must be boolean"
            )
        object.__setattr__(
            self, "identity_sha256", _digest(self.identity_sha256, "identity_sha256")
        )


@dataclass(frozen=True, slots=True)
class SafetyEvidenceRequest:
    run_id: str
    arm_identity_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )


@dataclass(frozen=True, slots=True)
class SafetyEvidenceObservation:
    run_id: str
    arm_identity_sha256: str
    documented_checks: tuple[str, ...]
    operator_present_in_simulation: bool
    sequence_stamp: UntrustedSyntheticSequenceStamp
    physical_safety_validated: bool = field(default=False, init=False)
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )
        object.__setattr__(
            self,
            "documented_checks",
            _unique_text_tuple(self.documented_checks, "documented_checks"),
        )
        if not isinstance(self.operator_present_in_simulation, bool):
            raise PhysicalShapedOnboardingError(
                "operator_present_in_simulation must be boolean"
            )
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "safety sequence_stamp must be UntrustedSyntheticSequenceStamp"
            )

    @property
    def observation_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "documented_checks": list(self.documented_checks),
                "operator_present_in_simulation": self.operator_present_in_simulation,
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
                "physical_safety_validated": self.physical_safety_validated,
                "evidence_origin": self.evidence_origin,
            }
        )


@dataclass(frozen=True, slots=True)
class PowerEventRequest:
    run_id: str
    arm_identity_sha256: str
    required_safety_checks: tuple[str, ...]
    safety_observation_sha256: str
    sequence_stamp: UntrustedSyntheticSequenceStamp

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )
        object.__setattr__(
            self,
            "required_safety_checks",
            _unique_text_tuple(self.required_safety_checks, "required_safety_checks"),
        )
        object.__setattr__(
            self,
            "safety_observation_sha256",
            _digest(self.safety_observation_sha256, "safety_observation_sha256"),
        )
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "power-event request sequence_stamp is invalid"
            )

    @property
    def request_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "required_safety_checks": list(self.required_safety_checks),
                "safety_observation_sha256": self.safety_observation_sha256,
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class PowerEventObservation:
    run_id: str
    arm_identity_sha256: str
    safety_observation_sha256: str
    power_event_request_sha256: str
    event_id: str
    observation_code: str
    commands_issued: int
    unexpected_motion_observed: bool
    sequence_stamp: UntrustedSyntheticSequenceStamp
    physical_power_applied: bool = field(default=False, init=False)
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        for name in ("run_id", "event_id", "observation_code"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )
        for name in (
            "safety_observation_sha256",
            "power_event_request_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "commands_issued",
            _integer(self.commands_issued, "commands_issued", maximum=0),
        )
        if not isinstance(self.unexpected_motion_observed, bool):
            raise PhysicalShapedOnboardingError(
                "unexpected_motion_observed must be boolean"
            )
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "power-event observation sequence_stamp is invalid"
            )

    @property
    def observation_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "safety_observation_sha256": self.safety_observation_sha256,
                "power_event_request_sha256": self.power_event_request_sha256,
                "event_id": self.event_id,
                "observation_code": self.observation_code,
                "commands_issued": self.commands_issued,
                "unexpected_motion_observed": self.unexpected_motion_observed,
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
                "physical_power_applied": self.physical_power_applied,
                "evidence_origin": self.evidence_origin,
            }
        )


@dataclass(frozen=True, slots=True)
class SyntheticControllerSessionRequest:
    """Request for an in-memory controller identity, never a device connection."""

    run_id: str
    arm_identity_sha256: str
    power_event_observation_sha256: str
    sequence_stamp: UntrustedSyntheticSequenceStamp

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        for name in ("arm_identity_sha256", "power_event_observation_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "controller-session request sequence_stamp is invalid"
            )

    @property
    def request_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "power_event_observation_sha256": (
                    self.power_event_observation_sha256
                ),
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class SyntheticControllerSessionIdentity:
    """Identity of the fake in-memory feedback session.

    ``physical_controller_connected`` is constructor-fixed false.  This record
    cannot be used as evidence that USB, serial, Wi-Fi, or the ESP32 was opened.
    """

    run_id: str
    session_id: str
    arm_identity_sha256: str
    power_event_observation_sha256: str
    controller_session_request_sha256: str
    sequence_stamp: UntrustedSyntheticSequenceStamp
    transport_kind: str = field(default="SYNTHETIC_IN_MEMORY_NO_DEVICE", init=False)
    physical_controller_connected: bool = field(default=False, init=False)
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        for name in (
            "arm_identity_sha256",
            "power_event_observation_sha256",
            "controller_session_request_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "controller-session identity sequence_stamp is invalid"
            )

    @property
    def identity_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "session_id": self.session_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "power_event_observation_sha256": (
                    self.power_event_observation_sha256
                ),
                "controller_session_request_sha256": (
                    self.controller_session_request_sha256
                ),
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
                "transport_kind": self.transport_kind,
                "physical_controller_connected": self.physical_controller_connected,
                "evidence_origin": self.evidence_origin,
            }
        )


@dataclass(frozen=True, slots=True)
class InputBufferEmptyRequest:
    """Request for a fake pre-query input-buffer observation."""

    run_id: str
    arm_identity_sha256: str
    power_event_observation_sha256: str
    controller_session_id: str
    controller_session_identity_sha256: str
    sequence_stamp: UntrustedSyntheticSequenceStamp

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "controller_session_id",
            _text(self.controller_session_id, "controller_session_id"),
        )
        for name in (
            "arm_identity_sha256",
            "power_event_observation_sha256",
            "controller_session_identity_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "input-buffer request sequence_stamp is invalid"
            )

    @property
    def request_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "power_event_observation_sha256": (
                    self.power_event_observation_sha256
                ),
                "controller_session_id": self.controller_session_id,
                "controller_session_identity_sha256": (
                    self.controller_session_identity_sha256
                ),
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class InputBufferEmptyObservation:
    """Explicit fake buffer state captured immediately before the T=105 query."""

    run_id: str
    arm_identity_sha256: str
    power_event_observation_sha256: str
    controller_session_id: str
    controller_session_identity_sha256: str
    input_buffer_request_sha256: str
    bytes_waiting: int
    buffer_empty: bool
    sequence_stamp: UntrustedSyntheticSequenceStamp
    physical_input_buffer_observed: bool = field(default=False, init=False)
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "controller_session_id",
            _text(self.controller_session_id, "controller_session_id"),
        )
        for name in (
            "arm_identity_sha256",
            "power_event_observation_sha256",
            "controller_session_identity_sha256",
            "input_buffer_request_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "bytes_waiting",
            _integer(self.bytes_waiting, "bytes_waiting", maximum=16_777_216),
        )
        if not isinstance(self.buffer_empty, bool):
            raise PhysicalShapedOnboardingError("buffer_empty must be boolean")
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "input-buffer observation sequence_stamp is invalid"
            )

    @property
    def observation_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "power_event_observation_sha256": (
                    self.power_event_observation_sha256
                ),
                "controller_session_id": self.controller_session_id,
                "controller_session_identity_sha256": (
                    self.controller_session_identity_sha256
                ),
                "input_buffer_request_sha256": self.input_buffer_request_sha256,
                "bytes_waiting": self.bytes_waiting,
                "buffer_empty": self.buffer_empty,
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
                "physical_input_buffer_observed": (
                    self.physical_input_buffer_observed
                ),
                "evidence_origin": self.evidence_origin,
            }
        )


@dataclass(frozen=True, slots=True)
class T105FeedbackRequest:
    run_id: str
    arm_identity_sha256: str
    power_event_observation_sha256: str
    controller_session_id: str
    controller_session_identity_sha256: str
    input_buffer_observation_sha256: str
    sequence_stamp: UntrustedSyntheticSequenceStamp
    request_type: str = field(default="T=105", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )
        object.__setattr__(
            self,
            "controller_session_id",
            _text(self.controller_session_id, "controller_session_id"),
        )
        for name in (
            "power_event_observation_sha256",
            "controller_session_identity_sha256",
            "input_buffer_observation_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "T=105 request sequence_stamp is invalid"
            )

    @property
    def request_context_sha256(self) -> str:
        return _canonical_digest(
            {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "power_event_observation_sha256": (
                    self.power_event_observation_sha256
                ),
                "controller_session_id": self.controller_session_id,
                "controller_session_identity_sha256": (
                    self.controller_session_identity_sha256
                ),
                "input_buffer_observation_sha256": (
                    self.input_buffer_observation_sha256
                ),
                "sequence_stamp_sha256": self.sequence_stamp.stamp_sha256,
                "request_type": self.request_type,
            }
        )


@dataclass(frozen=True, slots=True)
class ParsedT1051Feedback:
    """Typed interpretation of the exact retained ``T=1051`` JSON response."""

    arm_identity_sha256: str
    x: float
    y: float
    z: float
    b: float
    s: float
    e: float
    t: float
    tor_b: int
    tor_s: int
    tor_e: int
    tor_h: int
    response_type: str = field(default="T=1051", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )
        for name in ("x", "y", "z", "b", "s", "e", "t"):
            object.__setattr__(
                self,
                name,
                _finite_number(getattr(self, name), f"T=1051 {name}"),
            )
        for name in ("tor_b", "tor_s", "tor_e", "tor_h"):
            object.__setattr__(
                self,
                name,
                _integer(
                    getattr(self, name),
                    f"T=1051 {name}",
                    minimum=-(1 << 31),
                    maximum=(1 << 31) - 1,
                ),
            )

    @property
    def canonical_content(self) -> dict[str, object]:
        """Return the only content covered by ``typed_feedback_sha256``."""

        return {
            "response_type": self.response_type,
            "arm_identity_sha256": self.arm_identity_sha256,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "b": self.b,
            "s": self.s,
            "e": self.e,
            "t": self.t,
            "torB": self.tor_b,
            "torS": self.tor_s,
            "torE": self.tor_e,
            "torH": self.tor_h,
        }


_T1051_RESPONSE_KEYS = frozenset(
    {"T", "x", "y", "z", "b", "s", "e", "t", "torB", "torS", "torE", "torH"}
)


def _parse_t1051_response(
    response_bytes: bytes, arm_identity_sha256: str
) -> ParsedT1051Feedback:
    """Strictly parse one newline-terminated response and reject duplicate keys."""

    retained = _immutable_bytes(response_bytes, "T=1051 response_bytes")
    if not retained.endswith(b"\n") or b"\n" in retained[:-1] or b"\r" in retained:
        raise PhysicalShapedOnboardingError(
            "T=1051 response must be exactly one LF-terminated JSON record"
        )
    try:
        text = retained[:-1].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PhysicalShapedOnboardingError(
            "T=1051 response must be strict UTF-8"
        ) from exc

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for key, value in pairs:
            if key in parsed:
                raise PhysicalShapedOnboardingError(
                    f"T=1051 response contains duplicate key {key}"
                )
            parsed[key] = value
        return parsed

    try:
        payload = json.loads(text, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, PhysicalShapedOnboardingError) as exc:
        if isinstance(exc, PhysicalShapedOnboardingError):
            raise
        raise PhysicalShapedOnboardingError(
            "T=1051 response is not valid JSON"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != _T1051_RESPONSE_KEYS:
        raise PhysicalShapedOnboardingError(
            "T=1051 response fields do not match the exact feedback schema"
        )
    if type(payload["T"]) is not int or payload["T"] != 1051:
        raise PhysicalShapedOnboardingError("T=1051 response type mismatch")

    return ParsedT1051Feedback(
        arm_identity_sha256=arm_identity_sha256,
        x=_finite_number(payload["x"], "T=1051 x"),
        y=_finite_number(payload["y"], "T=1051 y"),
        z=_finite_number(payload["z"], "T=1051 z"),
        b=_finite_number(payload["b"], "T=1051 b"),
        s=_finite_number(payload["s"], "T=1051 s"),
        e=_finite_number(payload["e"], "T=1051 e"),
        t=_finite_number(payload["t"], "T=1051 t"),
        tor_b=_integer(
            payload["torB"], "T=1051 torB", minimum=-(1 << 31), maximum=(1 << 31) - 1
        ),
        tor_s=_integer(
            payload["torS"], "T=1051 torS", minimum=-(1 << 31), maximum=(1 << 31) - 1
        ),
        tor_e=_integer(
            payload["torE"], "T=1051 torE", minimum=-(1 << 31), maximum=(1 << 31) - 1
        ),
        tor_h=_integer(
            payload["torH"], "T=1051 torH", minimum=-(1 << 31), maximum=(1 << 31) - 1
        ),
    )


@dataclass(frozen=True, slots=True)
class T105FeedbackReceipt:
    run_id: str
    arm_identity_sha256: str
    response_type: str
    feedback_query_ordinal: int
    power_event_observation_sha256: str
    controller_session_id: str
    controller_session_identity_sha256: str
    input_buffer_observation_sha256: str
    feedback_request_context_sha256: str
    sequence_stamp: UntrustedSyntheticSequenceStamp
    request_bytes: bytes
    response_bytes: bytes
    typed_feedback: ParsedT1051Feedback
    request_bytes_sha256: str
    response_bytes_sha256: str
    typed_feedback_sha256: str
    t104_motion_count: int
    evidence_origin: str = field(default="SYNTHETIC_FAKE", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "arm_identity_sha256",
            _digest(self.arm_identity_sha256, "arm_identity_sha256"),
        )
        object.__setattr__(
            self, "response_type", _text(self.response_type, "response_type")
        )
        object.__setattr__(
            self,
            "feedback_query_ordinal",
            _integer(
                self.feedback_query_ordinal,
                "feedback_query_ordinal",
                minimum=1,
            ),
        )
        object.__setattr__(
            self,
            "controller_session_id",
            _text(self.controller_session_id, "controller_session_id"),
        )
        for name in (
            "power_event_observation_sha256",
            "controller_session_identity_sha256",
            "input_buffer_observation_sha256",
            "feedback_request_context_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.sequence_stamp, UntrustedSyntheticSequenceStamp):
            raise PhysicalShapedOnboardingError(
                "T=105 receipt sequence_stamp is invalid"
            )
        object.__setattr__(
            self,
            "request_bytes",
            _immutable_bytes(self.request_bytes, "T=105 request_bytes"),
        )
        object.__setattr__(
            self,
            "response_bytes",
            _immutable_bytes(self.response_bytes, "T=1051 response_bytes"),
        )
        if not isinstance(self.typed_feedback, ParsedT1051Feedback):
            raise PhysicalShapedOnboardingError(
                "typed_feedback must be ParsedT1051Feedback"
            )
        for name in (
            "request_bytes_sha256",
            "response_bytes_sha256",
            "typed_feedback_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "t104_motion_count",
            _integer(self.t104_motion_count, "t104_motion_count", maximum=0),
        )
        if self.request_bytes_sha256 != hashlib.sha256(self.request_bytes).hexdigest():
            raise PhysicalShapedOnboardingError(
                "request_bytes_sha256 does not bind retained request_bytes"
            )
        if self.response_bytes_sha256 != hashlib.sha256(self.response_bytes).hexdigest():
            raise PhysicalShapedOnboardingError(
                "response_bytes_sha256 does not bind retained response_bytes"
            )
        parsed = _parse_t1051_response(
            self.response_bytes, self.arm_identity_sha256
        )
        if parsed != self.typed_feedback:
            raise PhysicalShapedOnboardingError(
                "typed_feedback does not match retained response_bytes"
            )
        if self.response_type != self.typed_feedback.response_type:
            raise PhysicalShapedOnboardingError(
                "response_type does not match typed_feedback"
            )
        if self.typed_feedback_sha256 != _canonical_digest(
            self.typed_feedback.canonical_content
        ):
            raise PhysicalShapedOnboardingError(
                "typed_feedback_sha256 does not bind parsed feedback content"
            )


@dataclass(frozen=True, slots=True)
class CleanupRequest:
    run_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))


@dataclass(frozen=True, slots=True)
class CleanupReceipt:
    run_id: str
    cleanup_ordinal: int
    open_sessions_remaining: int
    pending_operations_remaining: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "cleanup_ordinal",
            _integer(self.cleanup_ordinal, "cleanup_ordinal", minimum=1),
        )
        object.__setattr__(
            self,
            "open_sessions_remaining",
            _integer(self.open_sessions_remaining, "open_sessions_remaining"),
        )
        object.__setattr__(
            self,
            "pending_operations_remaining",
            _integer(self.pending_operations_remaining, "pending_operations_remaining"),
        )


@dataclass(frozen=True, slots=True)
class FakeProviderAccounting:
    run_id: str
    operation_trace: tuple[str, ...]
    synthetic_camera_captures: int
    synthetic_feedback_requests: int
    synthetic_t104_motion_requests: int
    cleanup_attempts: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.operation_trace, tuple):
            raise PhysicalShapedOnboardingError(
                "operation_trace must be an immutable tuple"
            )
        object.__setattr__(
            self,
            "operation_trace",
            tuple(_text(item, "operation trace item") for item in self.operation_trace),
        )
        for name in (
            "synthetic_camera_captures",
            "synthetic_feedback_requests",
            "synthetic_t104_motion_requests",
            "cleanup_attempts",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name))


@runtime_checkable
class CameraDiagnosticProvider(Protocol):
    """Camera operations needed for onboarding; no generic device access."""

    @property
    def descriptor(self) -> FakeProviderDescriptor: ...

    def inspect_camera_receipt(
        self, request: CameraReceiptRequest
    ) -> CameraReceiptObservation: ...

    def enumerate_cameras(
        self, request: CameraInventoryRequest
    ) -> CameraInventoryObservation: ...

    def open_selected_camera(
        self, request: CameraInventoryRequest
    ) -> CameraSessionReceipt: ...

    def apply_exact_configuration(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt: ...

    def read_configuration(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt: ...

    def flush_capture_buffers(
        self, request: CaptureBufferRequest
    ) -> BufferFlushReceipt: ...

    def capture_fresh_frame(self, request: FreshFrameRequest) -> FreshFrameReceipt: ...

    def reopen_selected_camera(
        self, request: CameraReopenRequest
    ) -> CameraReconnectReceipt: ...


@runtime_checkable
class CalibrationAcquisitionProvider(Protocol):
    @property
    def descriptor(self) -> FakeProviderDescriptor: ...

    def acquire_retained_install_calibration(
        self, request: CalibrationAcquisitionRequest
    ) -> CalibrationAcquisitionReceipt: ...


@runtime_checkable
class FeedbackOnlyArmDiagnosticProvider(Protocol):
    """Arm seam intentionally exposes identity and T=105 only, never T=104."""

    @property
    def descriptor(self) -> FakeProviderDescriptor: ...

    def inspect_arm_identity_while_off(
        self, request: ArmIdentityRequest
    ) -> ArmIdentityObservation: ...

    def open_synthetic_feedback_session(
        self, request: SyntheticControllerSessionRequest
    ) -> SyntheticControllerSessionIdentity: ...

    def observe_t105_input_buffer_empty(
        self, request: InputBufferEmptyRequest
    ) -> InputBufferEmptyObservation: ...

    def acquire_single_t105_feedback(
        self, request: T105FeedbackRequest
    ) -> T105FeedbackReceipt: ...


@runtime_checkable
class SafetyObservationProvider(Protocol):
    @property
    def descriptor(self) -> FakeProviderDescriptor: ...

    def collect_safety_evidence(
        self, request: SafetyEvidenceRequest
    ) -> SafetyEvidenceObservation: ...

    def observe_power_event(
        self, request: PowerEventRequest
    ) -> PowerEventObservation: ...


@runtime_checkable
class FakeLifecycleAuditProvider(Protocol):
    @property
    def descriptor(self) -> FakeProviderDescriptor: ...

    def snapshot_accounting(self) -> FakeProviderAccounting: ...

    def cleanup(self, request: CleanupRequest) -> CleanupReceipt: ...


@dataclass(frozen=True, slots=True)
class PhysicalShapedFakeProviders:
    camera: CameraDiagnosticProvider
    calibration: CalibrationAcquisitionProvider
    arm: FeedbackOnlyArmDiagnosticProvider
    safety: SafetyObservationProvider
    lifecycle: FakeLifecycleAuditProvider

    def __post_init__(self) -> None:
        """Accept one exact module-issued fake, never duck-typed live adapters.

        This is defense in depth against accidental adapter injection.  It does
        not replace OS process isolation because Python reflection can mutate
        process-local objects.
        """

        checks: tuple[tuple[object, type[object], str], ...] = (
            (self.camera, CameraDiagnosticProvider, "camera"),
            (self.calibration, CalibrationAcquisitionProvider, "calibration"),
            (self.arm, FeedbackOnlyArmDiagnosticProvider, "arm"),
            (self.safety, SafetyObservationProvider, "safety"),
            (self.lifecycle, FakeLifecycleAuditProvider, "lifecycle"),
        )
        for provider, protocol_type, label in checks:
            if not isinstance(provider, protocol_type):
                raise PhysicalShapedOnboardingError(
                    f"{label} provider does not implement its diagnostic protocol"
                )
            provider_type = globals().get("DeterministicFakeOnboardingProvider")
            if provider_type is None or type(provider) is not provider_type:
                raise PhysicalShapedOnboardingError(
                    f"{label} provider must be the exact deterministic fake type"
                )
            if (
                getattr(provider, "_module_fake_provider_token", None)
                is not _MODULE_FAKE_PROVIDER_TOKEN
            ):
                raise PhysicalShapedOnboardingError(
                    f"{label} provider was not issued by the module fake factory"
                )
        if any(
            provider is not self.camera
            for provider in (
                self.calibration,
                self.arm,
                self.safety,
                self.lifecycle,
            )
        ):
            raise PhysicalShapedOnboardingError(
                "all fake provider roles must reference one issued provider instance"
            )


@dataclass(frozen=True, slots=True)
class OnboardingStageResult:
    stage: OnboardingStage
    status: StageStatus
    detail_code: str
    evidence_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.stage, OnboardingStage):
            raise PhysicalShapedOnboardingError("stage is unsupported")
        if not isinstance(self.status, StageStatus):
            raise PhysicalShapedOnboardingError("stage status is unsupported")
        object.__setattr__(
            self, "detail_code", _text(self.detail_code, "detail_code", maximum=128)
        )
        if not isinstance(self.evidence_sha256s, tuple):
            raise PhysicalShapedOnboardingError(
                "evidence_sha256s must be an immutable tuple"
            )
        object.__setattr__(
            self,
            "evidence_sha256s",
            tuple(_digest(item, "evidence_sha256") for item in self.evidence_sha256s),
        )


@dataclass(frozen=True, slots=True)
class PhysicalShapedOnboardingResult:
    run_id: str
    status: WorkflowStatus
    stages: tuple[OnboardingStageResult, ...]
    cleanup: CleanupReceipt | None
    cleanup_error_code: str | None
    primary_error: OnboardingErrorRecord | None
    cleanup_errors: tuple[OnboardingErrorRecord, ...]
    post_run_accounting_errors: tuple[OnboardingErrorRecord, ...]
    accounting: FakeProviderAccounting
    authority: SyntheticZeroReleaseAuthority = field(
        default_factory=SyntheticZeroReleaseAuthority, init=False
    )
    physical_onboarding_completed: bool = field(default=False, init=False)
    physical_calibration_valid: bool = field(default=False, init=False)
    physical_release_effect: str = field(default="NONE", init=False)
    contract: str = field(
        default=PHYSICAL_SHAPED_ONBOARDING_CONTRACT, init=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id"))
        if not isinstance(self.status, WorkflowStatus):
            raise PhysicalShapedOnboardingError("workflow status is unsupported")
        if not isinstance(self.stages, tuple):
            raise PhysicalShapedOnboardingError("stages must be an immutable tuple")
        if any(not isinstance(item, OnboardingStageResult) for item in self.stages):
            raise PhysicalShapedOnboardingError(
                "stages must contain OnboardingStageResult records"
            )
        observed = tuple(item.stage for item in self.stages)
        if observed != ORDERED_ONBOARDING_STAGES[: len(observed)]:
            raise PhysicalShapedOnboardingError(
                "stages must be an exact prefix of the ordered workflow"
            )
        failures = tuple(
            item for item in self.stages if item.status is StageStatus.FAILED_CLOSED
        )
        if len(failures) > 1 or (failures and failures[0] is not self.stages[-1]):
            raise PhysicalShapedOnboardingError(
                "a failed stage must be the single terminal stage"
            )
        if self.status is WorkflowStatus.COMPLETE:
            if observed != ORDERED_ONBOARDING_STAGES or failures:
                raise PhysicalShapedOnboardingError(
                    "complete status requires every ordered stage to pass"
                )
        if self.cleanup is not None and not isinstance(self.cleanup, CleanupReceipt):
            raise PhysicalShapedOnboardingError("cleanup must be CleanupReceipt or None")
        if self.cleanup_error_code is not None:
            object.__setattr__(
                self,
                "cleanup_error_code",
                _text(self.cleanup_error_code, "cleanup_error_code", maximum=128),
            )
        if self.primary_error is not None:
            if not isinstance(self.primary_error, OnboardingErrorRecord):
                raise PhysicalShapedOnboardingError(
                    "primary_error must be OnboardingErrorRecord or None"
                )
            if self.primary_error.phase is not OnboardingErrorPhase.WORKFLOW:
                raise PhysicalShapedOnboardingError(
                    "primary_error must have WORKFLOW phase"
                )
        for field_name, expected_phase in (
            ("cleanup_errors", OnboardingErrorPhase.CLEANUP),
            (
                "post_run_accounting_errors",
                OnboardingErrorPhase.POST_RUN_ACCOUNTING,
            ),
        ):
            records = getattr(self, field_name)
            if not isinstance(records, tuple) or any(
                not isinstance(item, OnboardingErrorRecord) for item in records
            ):
                raise PhysicalShapedOnboardingError(
                    f"{field_name} must be an immutable tuple of error records"
                )
            if any(item.phase is not expected_phase for item in records):
                raise PhysicalShapedOnboardingError(
                    f"{field_name} contains an error from the wrong phase"
                )
        if failures:
            if self.primary_error is None:
                raise PhysicalShapedOnboardingError(
                    "failed workflow stage requires a structured primary_error"
                )
            if (
                failures[0].stage is not self.primary_error.stage
                or failures[0].detail_code != self.primary_error.detail_code
            ):
                raise PhysicalShapedOnboardingError(
                    "failed workflow stage must match primary_error"
                )
        elif self.primary_error is not None:
            raise PhysicalShapedOnboardingError(
                "primary_error requires a failed workflow stage"
            )
        expected_cleanup_error_code = (
            self.cleanup_errors[0].detail_code if self.cleanup_errors else None
        )
        if self.cleanup_error_code != expected_cleanup_error_code:
            raise PhysicalShapedOnboardingError(
                "cleanup_error_code must mirror the first structured cleanup error"
            )
        if not isinstance(self.accounting, FakeProviderAccounting):
            raise PhysicalShapedOnboardingError(
                "accounting must be FakeProviderAccounting"
            )
        if self.accounting.run_id != self.run_id:
            raise PhysicalShapedOnboardingError("accounting run_id mismatch")
        if self.cleanup is not None and self.cleanup.run_id != self.run_id:
            raise PhysicalShapedOnboardingError("cleanup run_id mismatch")
        if self.status is WorkflowStatus.COMPLETE:
            if (
                self.primary_error is not None
                or self.cleanup_errors
                or self.post_run_accounting_errors
            ):
                raise PhysicalShapedOnboardingError(
                    "complete status cannot contain structured errors"
                )
            if self.cleanup is None or self.cleanup_error_code is not None:
                raise PhysicalShapedOnboardingError(
                    "complete status requires confirmed cleanup"
                )
            if (
                self.cleanup.open_sessions_remaining != 0
                or self.cleanup.pending_operations_remaining != 0
            ):
                raise PhysicalShapedOnboardingError(
                    "complete status requires no remaining provider resources"
                )
            if self.accounting.synthetic_feedback_requests != 1:
                raise PhysicalShapedOnboardingError(
                    "complete status requires exactly one T=105 request"
                )
            if self.accounting.synthetic_t104_motion_requests != 0:
                raise PhysicalShapedOnboardingError(
                    "complete status requires zero T=104 motion requests"
                )
            if self.accounting.cleanup_attempts != 1:
                raise PhysicalShapedOnboardingError(
                    "complete status requires exactly one cleanup attempt"
                )
        if self.status is WorkflowStatus.CLEANUP_UNCONFIRMED and (
            self.cleanup is not None or not self.cleanup_errors
        ):
            raise PhysicalShapedOnboardingError(
                "cleanup-unconfirmed status requires a cleanup error and no receipt"
            )
        if self.status is WorkflowStatus.FAILED and (
            self.cleanup_errors
            or (self.primary_error is None and not self.post_run_accounting_errors)
        ):
            raise PhysicalShapedOnboardingError(
                "failed status requires a workflow/accounting error and confirmed cleanup"
            )

    @property
    def zero_physical_authority(self) -> bool:
        return (
            not self.authority.hardware_accessed
            and not self.authority.live_capture_performed
            and self.authority.hardware_commands_generated == 0
            and self.authority.t104_motion_commands_generated == 0
            and self.accounting.synthetic_t104_motion_requests == 0
            and not self.authority.robot_motion_authority
            and not self.authority.contact_authority
            and not self.authority.physical_calibration_authority
            and self.physical_release_effect == "NONE"
        )


_REQUIRED_SAFETY_CHECKS = (
    "CLEARANCE_SWEEP_PROCEDURE_DOCUMENTED",
    "ESTOP_PATH_DOCUMENTED",
    "GRAVITY_RESPONSE_PROCEDURE_DOCUMENTED",
    "OPERATOR_STOP_ROLE_DOCUMENTED",
    "POWER_CUT_PATH_DOCUMENTED",
)


def default_physical_shaped_onboarding_request(
    *, run_id: str = "fake-b0477-roarm-onboarding-001"
) -> PhysicalShapedOnboardingRequest:
    """Return deterministic B0477/RoArm expectations for contract testing.

    The control values are normalized rehearsal values, not claimed UVC driver
    IDs or approved physical settings.  A future live adapter must map and
    validate real device controls separately.
    """

    return PhysicalShapedOnboardingRequest(
        run_id=run_id,
        expected_camera=CameraIdentity(
            manufacturer="Arducam",
            model="B0477",
            sensor="Sony IMX283",
            lens="included nominal 16 mm C-mount lens",
            unit_serial="SYNTHETIC-B0477-0001",
            persistent_selection_key="synthetic-usb3/arducam-b0477-0001",
        ),
        exact_camera_configuration=ExactCameraConfiguration(
            mode=CameraMode(5472, 3648, 9, 1, "YUY2"),
            controls=(
                CameraControlSetting("analog_gain_x100", 100),
                CameraControlSetting("auto_exposure", 0),
                CameraControlSetting("auto_white_balance", 0),
                CameraControlSetting("exposure_time_us", 8_000),
                CameraControlSetting("white_balance_temperature_k", 5_000),
            ),
        ),
        retained_install_id="synthetic-retained-overhead-install-001",
        calibration_frame_count=32,
        calibration_training_frame_count=24,
        calibration_held_out_frame_count=8,
        freshness_frame_count=3,
        expected_arm=ArmIdentityExpectation(
            product="Waveshare RoArm-M3 Pro",
            controller="ESP32",
            protocol_family="Waveshare JSON command protocol",
        ),
    )


def _evidence_digest(record: object) -> str:
    """Hash a typed record's stable repr for local ordering evidence."""

    return hashlib.sha256(repr(record).encode("utf-8")).hexdigest()


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise PhysicalShapedOnboardingError(detail)


def _validate_descriptors(
    providers: PhysicalShapedFakeProviders, request: PhysicalShapedOnboardingRequest
) -> None:
    descriptors = (
        providers.camera.descriptor,
        providers.calibration.descriptor,
        providers.arm.descriptor,
        providers.safety.descriptor,
        providers.lifecycle.descriptor,
    )
    for descriptor in descriptors:
        _require(
            isinstance(descriptor, FakeProviderDescriptor),
            "provider descriptor must be FakeProviderDescriptor",
        )
        _require(descriptor.run_id == request.run_id, "provider run_id mismatch")
        _require(
            descriptor.provider_kind == "EXPLICIT_FAKE",
            "only EXPLICIT_FAKE providers are accepted",
        )
        _require(
            descriptor.authority == SyntheticZeroReleaseAuthority(),
            "provider authority must be the immutable zero-release record",
        )


def _passed(
    stage: OnboardingStage, detail_code: str, *records: object
) -> OnboardingStageResult:
    return OnboardingStageResult(
        stage=stage,
        status=StageStatus.PASSED,
        detail_code=detail_code,
        evidence_sha256s=tuple(_evidence_digest(record) for record in records),
    )


def _failure_code(error: Exception) -> str:
    if type(error) is FakeProviderBoundaryError:
        return f"FAKE_BOUNDARY_{error.boundary.value}_FAILED"
    if isinstance(error, PhysicalShapedOnboardingError):
        return "PROVIDER_RESULT_INVARIANT_FAILED"
    return "UNEXPECTED_PROVIDER_EXCEPTION"


def _error_record(
    phase: OnboardingErrorPhase,
    error: Exception,
    *,
    stage: OnboardingStage | None = None,
) -> OnboardingErrorRecord:
    """Convert even hostile exception text into a bounded structured record."""

    error_type = _safe_error_text(
        type(error).__name__, fallback="Exception", maximum=128
    )
    return OnboardingErrorRecord(
        phase=phase,
        detail_code=_failure_code(error),
        exception_type=error_type,
        message=_safe_error_text(error, fallback=error_type, maximum=512),
        stage=stage,
    )


def _invariant_error(detail: str) -> PhysicalShapedOnboardingError:
    """Build one independently reportable provider-result invariant error."""

    return PhysicalShapedOnboardingError(detail)


def run_physical_shaped_fake_onboarding(
    request: PhysicalShapedOnboardingRequest,
    providers: PhysicalShapedFakeProviders,
) -> PhysicalShapedOnboardingResult:
    """Run the ordered provider contract and always attempt cleanup.

    This function cannot accept physical authority: descriptor validation is
    performed before any diagnostic operation, protocols omit motion/contact,
    and the final accounting gate requires zero simulated T=104 requests.
    """

    if not isinstance(request, PhysicalShapedOnboardingRequest):
        raise PhysicalShapedOnboardingError(
            "request must be PhysicalShapedOnboardingRequest"
        )
    if not isinstance(providers, PhysicalShapedFakeProviders):
        raise PhysicalShapedOnboardingError(
            "providers must be PhysicalShapedFakeProviders"
        )

    stages: list[OnboardingStageResult] = []
    current_stage = OnboardingStage.CAMERA_RECEIPT
    primary_error_record: OnboardingErrorRecord | None = None
    cleanup_receipt: CleanupReceipt | None = None
    cleanup_errors: list[OnboardingErrorRecord] = []
    post_run_accounting_errors: list[OnboardingErrorRecord] = []
    pre_cleanup_accounting: FakeProviderAccounting | None = None

    try:
        _validate_descriptors(providers, request)

        receipt = providers.camera.inspect_camera_receipt(
            CameraReceiptRequest(request.run_id, request.expected_camera.identity_sha256)
        )
        _require(receipt.run_id == request.run_id, "camera receipt run_id mismatch")
        _require(receipt.identity == request.expected_camera, "camera receipt identity mismatch")
        _require(
            not receipt.physical_receipt_verified,
            "fake receipt cannot claim physical verification",
        )
        stages.append(_passed(current_stage, "SYNTHETIC_CAMERA_RECEIPT_BOUND", receipt))

        current_stage = OnboardingStage.CAMERA_INVENTORY_SELECTION
        inventory_request = CameraInventoryRequest(
            request.run_id, request.expected_camera.persistent_selection_key
        )
        inventory = providers.camera.enumerate_cameras(inventory_request)
        _require(inventory.run_id == request.run_id, "inventory run_id mismatch")
        _require(
            inventory.discovered_keys.count(inventory.selected_key) == 1,
            "selected camera must occur exactly once in inventory",
        )
        _require(
            inventory.selected_key == request.expected_camera.persistent_selection_key,
            "persistent camera selection mismatch",
        )
        _require(
            inventory.selected_identity_sha256
            == request.expected_camera.identity_sha256,
            "inventory camera identity mismatch",
        )
        session = providers.camera.open_selected_camera(inventory_request)
        _require(session.run_id == request.run_id, "camera session run_id mismatch")
        _require(
            session.persistent_selection_key == inventory.selected_key,
            "opened camera selection mismatch",
        )
        _require(
            session.identity_sha256 == request.expected_camera.identity_sha256,
            "opened camera identity mismatch",
        )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_OS_INVENTORY_AND_PERSISTENT_SELECTION_BOUND",
                inventory,
                session,
            )
        )

        current_stage = OnboardingStage.CAMERA_MODE_CONTROL
        configuration_request = CameraConfigurationRequest(
            request.run_id, session.session_id, request.exact_camera_configuration
        )
        applied = providers.camera.apply_exact_configuration(configuration_request)
        readback = providers.camera.read_configuration(configuration_request)
        for label, observation in (("apply", applied), ("readback", readback)):
            _require(observation.run_id == request.run_id, f"{label} run_id mismatch")
            _require(
                observation.session_id == session.session_id,
                f"{label} session mismatch",
            )
            _require(
                observation.configuration == request.exact_camera_configuration,
                f"{label} camera configuration mismatch",
            )
            _require(
                observation.requested_configuration_sha256
                == request.exact_camera_configuration.configuration_sha256,
                f"{label} configuration digest mismatch",
            )
            _require(
                not observation.fallback_negotiated,
                f"{label} negotiated an unapproved fallback",
            )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_EXACT_MODE_CONTROLS_APPLIED_AND_READ_BACK",
                applied,
                readback,
            )
        )

        current_stage = OnboardingStage.CAMERA_BUFFER_FRESHNESS
        flush = providers.camera.flush_capture_buffers(
            CaptureBufferRequest(request.run_id, session.session_id)
        )
        _require(flush.run_id == request.run_id, "flush run_id mismatch")
        _require(flush.session_id == session.session_id, "flush session mismatch")
        frames: list[FreshFrameReceipt] = []
        minimum_sequence = flush.last_discarded_sequence
        previous_time = 0
        for _ in range(request.freshness_frame_count):
            frame = providers.camera.capture_fresh_frame(
                FreshFrameRequest(
                    request.run_id,
                    session.session_id,
                    minimum_sequence,
                    request.exact_camera_configuration.configuration_sha256,
                )
            )
            _require(frame.run_id == request.run_id, "frame run_id mismatch")
            _require(frame.session_id == session.session_id, "frame session mismatch")
            _require(frame.sequence > minimum_sequence, "frame sequence is stale")
            _require(frame.monotonic_ns > previous_time, "frame time is not monotonic")
            _require(
                frame.configuration_sha256
                == request.exact_camera_configuration.configuration_sha256,
                "frame configuration mismatch",
            )
            frames.append(frame)
            minimum_sequence = frame.sequence
            previous_time = frame.monotonic_ns
        _require(
            len({frame.payload_sha256 for frame in frames}) == len(frames),
            "fresh frame payloads must be distinct",
        )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_CAPTURE_BUFFER_FLUSHED_AND_FRESHNESS_PROVED",
                flush,
                *frames,
            )
        )

        current_stage = OnboardingStage.CAMERA_RECONNECT_IDENTITY
        reconnect = providers.camera.reopen_selected_camera(
            CameraReopenRequest(
                request.run_id,
                session.session_id,
                request.expected_camera.persistent_selection_key,
                request.exact_camera_configuration.configuration_sha256,
            )
        )
        reopened = reconnect.reopened_session
        reopened_configuration = reconnect.configuration_readback
        _require(reconnect.run_id == request.run_id, "reconnect run_id mismatch")
        _require(
            reconnect.previous_session_id == session.session_id,
            "reconnect previous-session mismatch",
        )
        _require(
            reopened.run_id == request.run_id,
            "reopened session run_id mismatch",
        )
        _require(
            reopened.session_id != session.session_id,
            "reopen must create a new camera session",
        )
        _require(
            reopened.persistent_selection_key
            == request.expected_camera.persistent_selection_key,
            "reopened selection key mismatch",
        )
        _require(
            reopened.identity_sha256 == request.expected_camera.identity_sha256,
            "reopened identity mismatch",
        )
        _require(
            reopened_configuration.run_id == request.run_id,
            "reopened configuration run_id mismatch",
        )
        _require(
            reopened_configuration.session_id == reopened.session_id,
            "reopened configuration session mismatch",
        )
        _require(
            reopened_configuration.configuration
            == request.exact_camera_configuration,
            "reopened configuration mismatch",
        )
        _require(
            reopened_configuration.requested_configuration_sha256
            == request.exact_camera_configuration.configuration_sha256,
            "reopened requested-configuration digest mismatch",
        )
        _require(
            not reopened_configuration.fallback_negotiated,
            "reopened camera negotiated an unapproved fallback",
        )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_REOPEN_IDENTITY_AND_CONFIGURATION_REPROVED",
                reconnect,
            )
        )

        current_stage = OnboardingStage.RETAINED_INSTALL_CALIBRATION_ACQUISITION
        calibration = providers.calibration.acquire_retained_install_calibration(
            CalibrationAcquisitionRequest(
                request.run_id,
                reopened.session_id,
                request.retained_install_id,
                request.expected_camera.identity_sha256,
                request.exact_camera_configuration.configuration_sha256,
                request.calibration_frame_count,
                request.calibration_training_frame_count,
                request.calibration_held_out_frame_count,
            )
        )
        _require(calibration.run_id == request.run_id, "calibration run_id mismatch")
        _require(
            calibration.camera_session_id == reopened.session_id,
            "calibration camera session mismatch",
        )
        _require(
            calibration.retained_install_id == request.retained_install_id,
            "calibration retained-install mismatch",
        )
        _require(
            calibration.camera_identity_sha256
            == request.expected_camera.identity_sha256,
            "calibration camera identity mismatch",
        )
        _require(
            calibration.configuration_sha256
            == request.exact_camera_configuration.configuration_sha256,
            "calibration configuration mismatch",
        )
        _require(
            len(calibration.frame_receipt_sha256s)
            == request.calibration_frame_count,
            "calibration frame receipt count mismatch",
        )
        _require(
            len(calibration.training_frame_receipt_sha256s)
            == request.calibration_training_frame_count,
            "calibration training receipt count mismatch",
        )
        _require(
            len(calibration.held_out_frame_receipt_sha256s)
            == request.calibration_held_out_frame_count,
            "calibration held-out receipt count mismatch",
        )
        _require(
            not calibration.physical_calibration_valid,
            "synthetic acquisition cannot validate a physical calibration",
        )
        expected_dataset = _canonical_digest(
            {
                "run_id": request.run_id,
                "session_id": reopened.session_id,
                "retained_install_id": request.retained_install_id,
                "camera_identity_sha256": request.expected_camera.identity_sha256,
                "configuration_sha256": request.exact_camera_configuration.configuration_sha256,
                "frame_receipt_sha256s": list(calibration.frame_receipt_sha256s),
                "training_frame_receipt_sha256s": list(
                    calibration.training_frame_receipt_sha256s
                ),
                "held_out_frame_receipt_sha256s": list(
                    calibration.held_out_frame_receipt_sha256s
                ),
                "mount_witness_sha256": calibration.mount_witness_sha256,
                "lighting_witness_sha256": calibration.lighting_witness_sha256,
                "focus_lock_witness_sha256": (
                    calibration.focus_lock_witness_sha256
                ),
                "aperture_lock_witness_sha256": (
                    calibration.aperture_lock_witness_sha256
                ),
                "cable_route_witness_sha256": (
                    calibration.cable_route_witness_sha256
                ),
            }
        )
        _require(
            calibration.dataset_sha256 == expected_dataset,
            "calibration dataset digest mismatch",
        )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_RETAINED_INSTALL_ACQUISITION_RECEIPTS_BOUND",
                calibration,
            )
        )

        current_stage = OnboardingStage.ARM_IDENTITY_WHILE_OFF
        arm_identity = providers.arm.inspect_arm_identity_while_off(
            ArmIdentityRequest(request.run_id, request.expected_arm.product)
        )
        _require(arm_identity.run_id == request.run_id, "arm identity run_id mismatch")
        _require(
            arm_identity.product == request.expected_arm.product,
            "arm product mismatch",
        )
        _require(
            arm_identity.controller == request.expected_arm.controller,
            "arm controller mismatch",
        )
        _require(
            arm_identity.protocol_family == request.expected_arm.protocol_family,
            "arm protocol family mismatch",
        )
        _require(
            arm_identity.arm_power_observed_off,
            "arm identity inspection must report arm power off",
        )
        expected_arm_identity = _canonical_digest(
            {
                "product": arm_identity.product,
                "controller": arm_identity.controller,
                "protocol_family": arm_identity.protocol_family,
                "unit_serial": arm_identity.unit_serial,
            }
        )
        _require(
            arm_identity.identity_sha256 == expected_arm_identity,
            "arm identity digest mismatch",
        )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_ARM_IDENTITY_INSPECTED_WITH_POWER_REPORTED_OFF",
                arm_identity,
            )
        )

        current_stage = OnboardingStage.SAFETY_EVIDENCE
        safety = providers.safety.collect_safety_evidence(
            SafetyEvidenceRequest(request.run_id, arm_identity.identity_sha256)
        )
        _require(safety.run_id == request.run_id, "safety evidence run_id mismatch")
        _require(
            safety.arm_identity_sha256 == arm_identity.identity_sha256,
            "safety evidence arm identity mismatch",
        )
        _require(
            safety.documented_checks == _REQUIRED_SAFETY_CHECKS,
            "safety evidence checklist mismatch",
        )
        _require(
            safety.operator_present_in_simulation,
            "synthetic operator role must be present",
        )
        _require(
            not safety.physical_safety_validated,
            "synthetic evidence cannot validate physical safety",
        )
        expected_safety_stamp = _synthetic_tail_stamp(
            request.run_id,
            "SAFETY_OBSERVATION",
            1,
            arm_identity.identity_sha256,
        )
        _require(
            safety.sequence_stamp == expected_safety_stamp,
            "safety observation sequence stamp mismatch",
        )
        safety_observation_sha256 = safety.observation_sha256
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_SAFETY_PROCEDURE_SCHEMA_COMPLETE_NOT_PHYSICALLY_VALIDATED",
                safety,
            )
        )

        current_stage = OnboardingStage.POWER_EVENT_OBSERVATION
        power_event_request = PowerEventRequest(
            run_id=request.run_id,
            arm_identity_sha256=arm_identity.identity_sha256,
            required_safety_checks=_REQUIRED_SAFETY_CHECKS,
            safety_observation_sha256=safety_observation_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "POWER_EVENT_REQUEST",
                2,
                safety_observation_sha256,
            ),
        )
        power_event_request_sha256 = power_event_request.request_sha256
        power_event = providers.safety.observe_power_event(power_event_request)
        _require(
            safety.observation_sha256 == safety_observation_sha256,
            "safety observation was mutated after validation",
        )
        _require(
            power_event_request
            == PowerEventRequest(
                run_id=request.run_id,
                arm_identity_sha256=arm_identity.identity_sha256,
                required_safety_checks=_REQUIRED_SAFETY_CHECKS,
                safety_observation_sha256=safety_observation_sha256,
                sequence_stamp=_synthetic_tail_stamp(
                    request.run_id,
                    "POWER_EVENT_REQUEST",
                    2,
                    safety_observation_sha256,
                ),
            ),
            "power event request was mutated by provider",
        )
        _require(power_event.run_id == request.run_id, "power event run_id mismatch")
        _require(
            power_event.arm_identity_sha256 == arm_identity.identity_sha256,
            "power event arm identity mismatch",
        )
        _require(
            power_event.safety_observation_sha256
            == safety_observation_sha256,
            "power event safety-observation binding mismatch",
        )
        _require(
            power_event.power_event_request_sha256
            == power_event_request_sha256,
            "power event request binding mismatch",
        )
        _require(
            power_event.sequence_stamp
            == _synthetic_tail_stamp(
                request.run_id,
                "POWER_EVENT_OBSERVATION",
                3,
                power_event_request_sha256,
            ),
            "power event observation sequence stamp mismatch",
        )
        _require(
            power_event.event_id
            == _synthetic_tail_identifier(
                request.run_id,
                "POWER_EVENT",
                power_event_request_sha256,
            ),
            "power event identifier mismatch",
        )
        _require(
            power_event.observation_code
            == "NO_COMMAND_NO_UNEXPECTED_MOTION_IN_FAKE_MODEL",
            "power event observation code mismatch",
        )
        _require(power_event.commands_issued == 0, "power event issued a command")
        _require(
            not power_event.unexpected_motion_observed,
            "synthetic power event reported unexpected motion",
        )
        _require(
            not power_event.physical_power_applied,
            "fake provider cannot claim physical power application",
        )
        stages.append(
            _passed(
                current_stage,
                "SYNTHETIC_POWER_EVENT_OBSERVED_WITH_ZERO_COMMANDS",
                power_event_request,
                power_event,
            )
        )

        current_stage = OnboardingStage.SINGLE_T105_FEEDBACK
        power_event_observation_sha256 = power_event.observation_sha256
        controller_request = SyntheticControllerSessionRequest(
            run_id=request.run_id,
            arm_identity_sha256=arm_identity.identity_sha256,
            power_event_observation_sha256=power_event_observation_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "CONTROLLER_SESSION_REQUEST",
                4,
                power_event_observation_sha256,
            ),
        )
        controller_request_sha256 = controller_request.request_sha256
        controller_session = providers.arm.open_synthetic_feedback_session(
            controller_request
        )
        _require(
            power_event.observation_sha256 == power_event_observation_sha256,
            "power event was mutated after validation",
        )
        _require(
            controller_request
            == SyntheticControllerSessionRequest(
                run_id=request.run_id,
                arm_identity_sha256=arm_identity.identity_sha256,
                power_event_observation_sha256=power_event_observation_sha256,
                sequence_stamp=_synthetic_tail_stamp(
                    request.run_id,
                    "CONTROLLER_SESSION_REQUEST",
                    4,
                    power_event_observation_sha256,
                ),
            ),
            "controller session request was mutated by provider",
        )
        _require(
            controller_session.run_id == request.run_id,
            "controller session run_id mismatch",
        )
        _require(
            controller_session.arm_identity_sha256 == arm_identity.identity_sha256,
            "controller session arm identity mismatch",
        )
        _require(
            controller_session.power_event_observation_sha256
            == power_event_observation_sha256,
            "controller session power-event binding mismatch",
        )
        _require(
            controller_session.controller_session_request_sha256
            == controller_request_sha256,
            "controller session request binding mismatch",
        )
        _require(
            controller_session.sequence_stamp
            == _synthetic_tail_stamp(
                request.run_id,
                "CONTROLLER_SESSION_IDENTITY",
                5,
                controller_request_sha256,
            ),
            "controller session identity sequence stamp mismatch",
        )
        _require(
            controller_session.session_id
            == _synthetic_tail_identifier(
                request.run_id,
                "CONTROLLER_FEEDBACK_SESSION",
                power_event_observation_sha256,
            ),
            "controller session identifier mismatch",
        )
        _require(
            controller_session.transport_kind == "SYNTHETIC_IN_MEMORY_NO_DEVICE",
            "controller session transport kind mismatch",
        )
        _require(
            not controller_session.physical_controller_connected,
            "fake controller session cannot claim a physical connection",
        )
        controller_session_identity_sha256 = controller_session.identity_sha256

        input_buffer_request = InputBufferEmptyRequest(
            run_id=request.run_id,
            arm_identity_sha256=arm_identity.identity_sha256,
            power_event_observation_sha256=power_event_observation_sha256,
            controller_session_id=controller_session.session_id,
            controller_session_identity_sha256=controller_session_identity_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "INPUT_BUFFER_EMPTY_REQUEST",
                6,
                controller_session_identity_sha256,
            ),
        )
        input_buffer_request_sha256 = input_buffer_request.request_sha256
        input_buffer = providers.arm.observe_t105_input_buffer_empty(
            input_buffer_request
        )
        _require(
            controller_session.identity_sha256
            == controller_session_identity_sha256,
            "controller session identity was mutated after validation",
        )
        _require(
            input_buffer_request
            == InputBufferEmptyRequest(
                run_id=request.run_id,
                arm_identity_sha256=arm_identity.identity_sha256,
                power_event_observation_sha256=power_event_observation_sha256,
                controller_session_id=controller_session.session_id,
                controller_session_identity_sha256=(
                    controller_session_identity_sha256
                ),
                sequence_stamp=_synthetic_tail_stamp(
                    request.run_id,
                    "INPUT_BUFFER_EMPTY_REQUEST",
                    6,
                    controller_session_identity_sha256,
                ),
            ),
            "input-buffer request was mutated by provider",
        )
        _require(input_buffer.run_id == request.run_id, "input buffer run_id mismatch")
        _require(
            input_buffer.arm_identity_sha256 == arm_identity.identity_sha256,
            "input buffer arm identity mismatch",
        )
        _require(
            input_buffer.power_event_observation_sha256
            == power_event_observation_sha256,
            "input buffer power-event binding mismatch",
        )
        _require(
            input_buffer.controller_session_id == controller_session.session_id,
            "input buffer controller session mismatch",
        )
        _require(
            input_buffer.controller_session_identity_sha256
            == controller_session_identity_sha256,
            "input buffer controller identity binding mismatch",
        )
        _require(
            input_buffer.input_buffer_request_sha256
            == input_buffer_request_sha256,
            "input buffer request binding mismatch",
        )
        _require(
            input_buffer.sequence_stamp
            == _synthetic_tail_stamp(
                request.run_id,
                "INPUT_BUFFER_EMPTY_OBSERVATION",
                7,
                input_buffer_request_sha256,
            ),
            "input buffer observation sequence stamp mismatch",
        )
        _require(
            input_buffer.bytes_waiting == 0 and input_buffer.buffer_empty,
            "pre-query synthetic input buffer is not empty",
        )
        _require(
            not input_buffer.physical_input_buffer_observed,
            "fake input-buffer observation cannot claim physical evidence",
        )
        input_buffer_observation_sha256 = input_buffer.observation_sha256

        feedback_request = T105FeedbackRequest(
            run_id=request.run_id,
            arm_identity_sha256=arm_identity.identity_sha256,
            power_event_observation_sha256=power_event_observation_sha256,
            controller_session_id=controller_session.session_id,
            controller_session_identity_sha256=controller_session_identity_sha256,
            input_buffer_observation_sha256=input_buffer_observation_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "T105_FEEDBACK_REQUEST",
                8,
                input_buffer_observation_sha256,
            ),
        )
        feedback_request_context_sha256 = feedback_request.request_context_sha256
        feedback = providers.arm.acquire_single_t105_feedback(feedback_request)
        _require(
            safety.observation_sha256 == safety_observation_sha256,
            "safety observation was mutated before feedback validation",
        )
        _require(
            input_buffer.observation_sha256 == input_buffer_observation_sha256,
            "input-buffer observation was mutated after validation",
        )
        _require(
            power_event.observation_sha256 == power_event_observation_sha256,
            "power event was mutated before feedback validation",
        )
        _require(
            controller_session.identity_sha256
            == controller_session_identity_sha256,
            "controller session identity was mutated before feedback validation",
        )
        _require(
            feedback_request
            == T105FeedbackRequest(
                run_id=request.run_id,
                arm_identity_sha256=arm_identity.identity_sha256,
                power_event_observation_sha256=power_event_observation_sha256,
                controller_session_id=controller_session.session_id,
                controller_session_identity_sha256=(
                    controller_session_identity_sha256
                ),
                input_buffer_observation_sha256=(
                    input_buffer_observation_sha256
                ),
                sequence_stamp=_synthetic_tail_stamp(
                    request.run_id,
                    "T105_FEEDBACK_REQUEST",
                    8,
                    input_buffer_observation_sha256,
                ),
            ),
            "T=105 feedback request was mutated by provider",
        )
        _require(feedback.run_id == request.run_id, "feedback run_id mismatch")
        _require(
            feedback.arm_identity_sha256 == arm_identity.identity_sha256,
            "feedback arm identity mismatch",
        )
        _require(
            feedback.power_event_observation_sha256
            == power_event_observation_sha256,
            "feedback power-event binding mismatch",
        )
        _require(
            feedback.controller_session_id == controller_session.session_id,
            "feedback controller session mismatch",
        )
        _require(
            feedback.controller_session_identity_sha256
            == controller_session_identity_sha256,
            "feedback controller identity binding mismatch",
        )
        _require(
            feedback.input_buffer_observation_sha256
            == input_buffer_observation_sha256,
            "feedback input-buffer binding mismatch",
        )
        _require(
            feedback.feedback_request_context_sha256
            == feedback_request_context_sha256,
            "feedback request-context binding mismatch",
        )
        _require(
            feedback.sequence_stamp
            == _synthetic_tail_stamp(
                request.run_id,
                "T105_FEEDBACK_RECEIPT",
                9,
                feedback_request_context_sha256,
            ),
            "feedback receipt sequence stamp mismatch",
        )
        _require(feedback.response_type == "T=1051", "feedback response type mismatch")
        exact_t105_request = b'{"T":105}\n'
        _require(
            feedback.request_bytes == exact_t105_request,
            "retained feedback request is not the exact T=105 query",
        )
        _require(
            feedback.request_bytes_sha256
            == hashlib.sha256(feedback.request_bytes).hexdigest(),
            "feedback request digest does not bind retained request bytes",
        )
        _require(
            feedback.response_bytes_sha256
            == hashlib.sha256(feedback.response_bytes).hexdigest(),
            "feedback response digest does not bind retained response bytes",
        )
        parsed_feedback = _parse_t1051_response(
            feedback.response_bytes, arm_identity.identity_sha256
        )
        _require(
            feedback.typed_feedback == parsed_feedback,
            "typed feedback does not match retained response bytes",
        )
        _require(
            feedback.typed_feedback.arm_identity_sha256
            == arm_identity.identity_sha256,
            "typed feedback arm identity mismatch",
        )
        _require(
            feedback.typed_feedback_sha256
            == _canonical_digest(feedback.typed_feedback.canonical_content),
            "typed feedback digest does not bind parsed content",
        )
        _require(
            feedback.feedback_query_ordinal == 1,
            "exactly one T=105 feedback query is permitted",
        )
        _require(feedback.t104_motion_count == 0, "T=104 motion count must remain zero")
        pre_cleanup_accounting = providers.lifecycle.snapshot_accounting()
        _require(
            isinstance(pre_cleanup_accounting, FakeProviderAccounting),
            "provider pre-cleanup accounting type mismatch",
        )
        _require(
            pre_cleanup_accounting.run_id == request.run_id,
            "provider pre-cleanup accounting run_id mismatch",
        )
        _require(
            pre_cleanup_accounting.synthetic_feedback_requests == 1,
            "provider accounting must contain exactly one T=105 request",
        )
        _require(
            pre_cleanup_accounting.synthetic_t104_motion_requests == 0,
            "provider accounting must contain zero T=104 requests",
        )
        stages.append(
            _passed(
                current_stage,
                "ONE_IDENTITY_BOUND_SYNTHETIC_T105_FEEDBACK_ACQUIRED",
                controller_request,
                controller_session,
                input_buffer_request,
                input_buffer,
                feedback_request,
                feedback,
                pre_cleanup_accounting,
            )
        )
    except Exception as exc:  # cleanup must run for every provider failure shape
        primary_error_record = _error_record(
            OnboardingErrorPhase.WORKFLOW, exc, stage=current_stage
        )
        stages.append(
            OnboardingStageResult(
                stage=current_stage,
                status=StageStatus.FAILED_CLOSED,
                detail_code=primary_error_record.detail_code,
                evidence_sha256s=(),
            )
        )
    finally:
        try:
            cleanup_candidate = providers.lifecycle.cleanup(
                CleanupRequest(request.run_id)
            )
        except Exception as exc:  # preserve the original stage failure as well
            cleanup_errors.append(
                _error_record(OnboardingErrorPhase.CLEANUP, exc)
            )
        else:
            if type(cleanup_candidate) is not CleanupReceipt:
                cleanup_errors.append(
                    _error_record(
                        OnboardingErrorPhase.CLEANUP,
                        _invariant_error("cleanup receipt type mismatch"),
                    )
                )
            else:
                cleanup_invariants = (
                    (
                        cleanup_candidate.run_id == request.run_id,
                        "cleanup run_id mismatch",
                    ),
                    (
                        cleanup_candidate.cleanup_ordinal == 1,
                        "cleanup must occur once",
                    ),
                    (
                        cleanup_candidate.open_sessions_remaining == 0,
                        "cleanup left an open camera session",
                    ),
                    (
                        cleanup_candidate.pending_operations_remaining == 0,
                        "cleanup left a pending operation",
                    ),
                )
                for valid, detail in cleanup_invariants:
                    if not valid:
                        cleanup_errors.append(
                            _error_record(
                                OnboardingErrorPhase.CLEANUP,
                                _invariant_error(detail),
                            )
                        )
                if not cleanup_errors:
                    cleanup_receipt = cleanup_candidate

    try:
        accounting_candidate = providers.lifecycle.snapshot_accounting()
    except Exception as exc:
        post_run_accounting_errors.append(
            _error_record(OnboardingErrorPhase.POST_RUN_ACCOUNTING, exc)
        )
        accounting_candidate = None

    if type(accounting_candidate) is FakeProviderAccounting:
        accounting = accounting_candidate
        accounting_invariants = (
            (
                accounting_candidate.run_id == request.run_id,
                "post-run accounting run_id mismatch",
            ),
            (
                accounting_candidate.synthetic_t104_motion_requests == 0,
                "post-run accounting reported a T=104 motion request",
            ),
            (
                accounting_candidate.cleanup_attempts == 1,
                "post-run accounting must report exactly one cleanup attempt",
            ),
        )
        for valid, detail in accounting_invariants:
            if not valid:
                post_run_accounting_errors.append(
                    _error_record(
                        OnboardingErrorPhase.POST_RUN_ACCOUNTING,
                        _invariant_error(detail),
                    )
                )
        feedback_stage_passed = any(
            item.stage is OnboardingStage.SINGLE_T105_FEEDBACK
            and item.status is StageStatus.PASSED
            for item in stages
        )
        if (
            feedback_stage_passed
            and accounting_candidate.synthetic_feedback_requests != 1
        ):
            post_run_accounting_errors.append(
                _error_record(
                    OnboardingErrorPhase.POST_RUN_ACCOUNTING,
                    _invariant_error(
                        "post-run accounting must retain exactly one T=105 request"
                    ),
                )
            )
        if accounting_candidate.run_id != request.run_id:
            # The bad run ID is retained in the structured error; normalize the
            # result envelope so reporting the provider violation cannot throw.
            accounting = FakeProviderAccounting(
                request.run_id,
                accounting_candidate.operation_trace,
                accounting_candidate.synthetic_camera_captures,
                accounting_candidate.synthetic_feedback_requests,
                accounting_candidate.synthetic_t104_motion_requests,
                accounting_candidate.cleanup_attempts,
            )
    else:
        if accounting_candidate is not None:
            post_run_accounting_errors.append(
                _error_record(
                    OnboardingErrorPhase.POST_RUN_ACCOUNTING,
                    _invariant_error("post-run accounting type mismatch"),
                )
            )
        if pre_cleanup_accounting is None:
            accounting = FakeProviderAccounting(request.run_id, (), 0, 0, 0, 1)
        else:
            accounting = FakeProviderAccounting(
                request.run_id,
                pre_cleanup_accounting.operation_trace,
                pre_cleanup_accounting.synthetic_camera_captures,
                pre_cleanup_accounting.synthetic_feedback_requests,
                pre_cleanup_accounting.synthetic_t104_motion_requests,
                1,
            )

    if cleanup_errors:
        status = WorkflowStatus.CLEANUP_UNCONFIRMED
    elif primary_error_record is not None or post_run_accounting_errors:
        status = WorkflowStatus.FAILED
    else:
        status = WorkflowStatus.COMPLETE

    return PhysicalShapedOnboardingResult(
        run_id=request.run_id,
        status=status,
        stages=tuple(stages),
        cleanup=cleanup_receipt,
        cleanup_error_code=(
            cleanup_errors[0].detail_code if cleanup_errors else None
        ),
        primary_error=primary_error_record,
        cleanup_errors=tuple(cleanup_errors),
        post_run_accounting_errors=tuple(post_run_accounting_errors),
        accounting=accounting,
    )


@final
class DeterministicFakeOnboardingProvider:
    """Explicit fake implementing every diagnostic protocol for tests/rehearsal.

    It has no method that accepts T=104, a trajectory, a joint target, a pose,
    contact depth, or a raw serial payload.  Its internal counters distinguish
    simulated observations from hardware activity, which always remains zero in
    the immutable descriptor authority.  Construction is reserved to the
    module factory.  That token and exact-type check prevent accidental adapter
    substitution but are not a substitute for OS device-access denial.
    """

    def __init__(
        self,
        request: PhysicalShapedOnboardingRequest,
        *,
        fault_at: FakeBoundary | None = None,
        _issuance_token: object | None = None,
    ) -> None:
        if (
            _issuance_token is not _MODULE_FAKE_PROVIDER_TOKEN
            or type(self) is not DeterministicFakeOnboardingProvider
        ):
            raise PhysicalShapedOnboardingError(
                "deterministic fake providers must be exact instances issued by "
                "build_deterministic_fake_providers"
            )
        if not isinstance(request, PhysicalShapedOnboardingRequest):
            raise PhysicalShapedOnboardingError(
                "request must be PhysicalShapedOnboardingRequest"
            )
        if fault_at is not None and not isinstance(fault_at, FakeBoundary):
            raise PhysicalShapedOnboardingError("fault_at must be FakeBoundary or None")
        self._request = request
        self._module_fake_provider_token = _MODULE_FAKE_PROVIDER_TOKEN
        self._fault_at = fault_at
        self._descriptor = FakeProviderDescriptor(
            request.run_id, "deterministic-fake-onboarding-provider"
        )
        self._trace: list[str] = []
        self._open_sessions: set[str] = set()
        self._configured_sessions: set[str] = set()
        self._frame_sequence = 40
        self._monotonic_ns = 1_000_000_000
        self._capture_count = 0
        self._feedback_count = 0
        self._t104_count = 0
        self._cleanup_attempts = 0
        self._safety_observation: SafetyEvidenceObservation | None = None
        self._power_event_observation: PowerEventObservation | None = None
        self._controller_session: SyntheticControllerSessionIdentity | None = None
        self._input_buffer_observation: InputBufferEmptyObservation | None = None

    @property
    def descriptor(self) -> FakeProviderDescriptor:
        return self._descriptor

    def _enter(self, boundary: FakeBoundary) -> None:
        self._trace.append(boundary.value)
        if self._fault_at is boundary:
            raise FakeProviderBoundaryError(boundary)

    def inspect_camera_receipt(
        self, request: CameraReceiptRequest
    ) -> CameraReceiptObservation:
        self._enter(FakeBoundary.CAMERA_RECEIPT)
        return CameraReceiptObservation(
            request.run_id,
            self._request.expected_camera,
            _canonical_digest({"synthetic_label": request.expected_identity_sha256}),
            _canonical_digest({"synthetic_packaging": self._request.run_id}),
        )

    def enumerate_cameras(
        self, request: CameraInventoryRequest
    ) -> CameraInventoryObservation:
        self._enter(FakeBoundary.CAMERA_INVENTORY)
        return CameraInventoryObservation(
            request.run_id,
            (request.persistent_selection_key,),
            request.persistent_selection_key,
            self._request.expected_camera.identity_sha256,
        )

    def open_selected_camera(
        self, request: CameraInventoryRequest
    ) -> CameraSessionReceipt:
        self._enter(FakeBoundary.CAMERA_OPEN)
        session_id = "synthetic-camera-session-001"
        self._open_sessions.add(session_id)
        return CameraSessionReceipt(
            request.run_id,
            session_id,
            request.persistent_selection_key,
            self._request.expected_camera.identity_sha256,
        )

    def apply_exact_configuration(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt:
        self._enter(FakeBoundary.CAMERA_APPLY_CONFIGURATION)
        if request.session_id not in self._open_sessions:
            raise PhysicalShapedOnboardingError("configuration session is not open")
        self._configured_sessions.add(request.session_id)
        return CameraConfigurationReceipt(
            request.run_id,
            request.session_id,
            request.configuration,
            request.configuration.configuration_sha256,
            False,
        )

    def read_configuration(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt:
        self._enter(FakeBoundary.CAMERA_READBACK)
        if request.session_id not in self._configured_sessions:
            raise PhysicalShapedOnboardingError("configuration was not applied")
        return CameraConfigurationReceipt(
            request.run_id,
            request.session_id,
            request.configuration,
            request.configuration.configuration_sha256,
            False,
        )

    def flush_capture_buffers(
        self, request: CaptureBufferRequest
    ) -> BufferFlushReceipt:
        self._enter(FakeBoundary.CAMERA_FLUSH)
        if request.session_id not in self._configured_sessions:
            raise PhysicalShapedOnboardingError("flush session is not configured")
        self._frame_sequence += 4
        return BufferFlushReceipt(request.run_id, request.session_id, 4, self._frame_sequence)

    def capture_fresh_frame(self, request: FreshFrameRequest) -> FreshFrameReceipt:
        self._enter(FakeBoundary.CAMERA_CAPTURE)
        if request.session_id not in self._configured_sessions:
            raise PhysicalShapedOnboardingError("capture session is not configured")
        self._frame_sequence = max(
            self._frame_sequence + 1, request.minimum_sequence_exclusive + 1
        )
        self._monotonic_ns += 111_111_111
        self._capture_count += 1
        payload_digest = _canonical_digest(
            {
                "run_id": request.run_id,
                "session_id": request.session_id,
                "sequence": self._frame_sequence,
                "configuration_sha256": request.configuration_sha256,
            }
        )
        return FreshFrameReceipt(
            request.run_id,
            request.session_id,
            self._frame_sequence,
            self._monotonic_ns,
            request.configuration_sha256,
            payload_digest,
            5472 * 3648 * 2,
        )

    def reopen_selected_camera(
        self, request: CameraReopenRequest
    ) -> CameraReconnectReceipt:
        self._enter(FakeBoundary.CAMERA_REOPEN)
        if request.previous_session_id not in self._open_sessions:
            raise PhysicalShapedOnboardingError("previous camera session is not open")
        self._open_sessions.remove(request.previous_session_id)
        self._configured_sessions.discard(request.previous_session_id)
        new_session_id = "synthetic-camera-session-002"
        self._open_sessions.add(new_session_id)
        self._configured_sessions.add(new_session_id)
        reopened = CameraSessionReceipt(
            request.run_id,
            new_session_id,
            request.persistent_selection_key,
            self._request.expected_camera.identity_sha256,
        )
        readback = CameraConfigurationReceipt(
            request.run_id,
            new_session_id,
            self._request.exact_camera_configuration,
            request.expected_configuration_sha256,
            False,
        )
        return CameraReconnectReceipt(
            request.run_id, request.previous_session_id, reopened, readback
        )

    def acquire_retained_install_calibration(
        self, request: CalibrationAcquisitionRequest
    ) -> CalibrationAcquisitionReceipt:
        self._enter(FakeBoundary.CALIBRATION_ACQUISITION)
        if request.camera_session_id not in self._configured_sessions:
            raise PhysicalShapedOnboardingError(
                "calibration session is not open and configured"
            )
        frame_hashes = tuple(
            _canonical_digest(
                {
                    "synthetic_calibration_frame": index,
                    "session_id": request.camera_session_id,
                    "retained_install_id": request.retained_install_id,
                }
            )
            for index in range(request.required_frame_count)
        )
        training_frame_hashes = frame_hashes[: request.training_frame_count]
        held_out_frame_hashes = frame_hashes[request.training_frame_count :]
        mount = _canonical_digest(
            {"synthetic_mount_witness": request.retained_install_id}
        )
        lighting = _canonical_digest(
            {"synthetic_lighting_witness": request.retained_install_id}
        )
        focus_lock = _canonical_digest(
            {"synthetic_focus_lock_witness": request.retained_install_id}
        )
        aperture_lock = _canonical_digest(
            {"synthetic_aperture_lock_witness": request.retained_install_id}
        )
        cable_route = _canonical_digest(
            {"synthetic_cable_route_witness": request.retained_install_id}
        )
        dataset = _canonical_digest(
            {
                "run_id": request.run_id,
                "session_id": request.camera_session_id,
                "retained_install_id": request.retained_install_id,
                "camera_identity_sha256": request.camera_identity_sha256,
                "configuration_sha256": request.configuration_sha256,
                "frame_receipt_sha256s": list(frame_hashes),
                "training_frame_receipt_sha256s": list(training_frame_hashes),
                "held_out_frame_receipt_sha256s": list(held_out_frame_hashes),
                "mount_witness_sha256": mount,
                "lighting_witness_sha256": lighting,
                "focus_lock_witness_sha256": focus_lock,
                "aperture_lock_witness_sha256": aperture_lock,
                "cable_route_witness_sha256": cable_route,
            }
        )
        return CalibrationAcquisitionReceipt(
            request.run_id,
            request.camera_session_id,
            request.retained_install_id,
            request.camera_identity_sha256,
            request.configuration_sha256,
            frame_hashes,
            training_frame_hashes,
            held_out_frame_hashes,
            mount,
            lighting,
            focus_lock,
            aperture_lock,
            cable_route,
            dataset,
        )

    def inspect_arm_identity_while_off(
        self, request: ArmIdentityRequest
    ) -> ArmIdentityObservation:
        self._enter(FakeBoundary.ARM_IDENTITY_OFF)
        serial = "SYNTHETIC-ROARM-M3-PRO-0001"
        digest = _canonical_digest(
            {
                "product": self._request.expected_arm.product,
                "controller": self._request.expected_arm.controller,
                "protocol_family": self._request.expected_arm.protocol_family,
                "unit_serial": serial,
            }
        )
        return ArmIdentityObservation(
            request.run_id,
            self._request.expected_arm.product,
            self._request.expected_arm.controller,
            self._request.expected_arm.protocol_family,
            serial,
            True,
            digest,
        )

    def collect_safety_evidence(
        self, request: SafetyEvidenceRequest
    ) -> SafetyEvidenceObservation:
        self._enter(FakeBoundary.SAFETY_EVIDENCE)
        observation = SafetyEvidenceObservation(
            run_id=request.run_id,
            arm_identity_sha256=request.arm_identity_sha256,
            documented_checks=_REQUIRED_SAFETY_CHECKS,
            operator_present_in_simulation=True,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "SAFETY_OBSERVATION",
                1,
                request.arm_identity_sha256,
            ),
        )
        self._safety_observation = observation
        return observation

    def observe_power_event(
        self, request: PowerEventRequest
    ) -> PowerEventObservation:
        self._enter(FakeBoundary.POWER_EVENT)
        if self._safety_observation is None:
            raise PhysicalShapedOnboardingError(
                "power event requires the preceding safety observation"
            )
        expected_request = PowerEventRequest(
            run_id=self._request.run_id,
            arm_identity_sha256=self._safety_observation.arm_identity_sha256,
            required_safety_checks=_REQUIRED_SAFETY_CHECKS,
            safety_observation_sha256=self._safety_observation.observation_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                self._request.run_id,
                "POWER_EVENT_REQUEST",
                2,
                self._safety_observation.observation_sha256,
            ),
        )
        _require(request == expected_request, "power event request chain mismatch")
        observation = PowerEventObservation(
            run_id=request.run_id,
            arm_identity_sha256=request.arm_identity_sha256,
            safety_observation_sha256=request.safety_observation_sha256,
            power_event_request_sha256=request.request_sha256,
            event_id=_synthetic_tail_identifier(
                request.run_id, "POWER_EVENT", request.request_sha256
            ),
            observation_code="NO_COMMAND_NO_UNEXPECTED_MOTION_IN_FAKE_MODEL",
            commands_issued=0,
            unexpected_motion_observed=False,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "POWER_EVENT_OBSERVATION",
                3,
                request.request_sha256,
            ),
        )
        self._power_event_observation = observation
        return observation

    def open_synthetic_feedback_session(
        self, request: SyntheticControllerSessionRequest
    ) -> SyntheticControllerSessionIdentity:
        self._enter(FakeBoundary.CONTROLLER_SESSION)
        if self._power_event_observation is None:
            raise PhysicalShapedOnboardingError(
                "controller session requires the preceding power event"
            )
        power_sha256 = self._power_event_observation.observation_sha256
        expected_request = SyntheticControllerSessionRequest(
            run_id=self._request.run_id,
            arm_identity_sha256=self._power_event_observation.arm_identity_sha256,
            power_event_observation_sha256=power_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                self._request.run_id,
                "CONTROLLER_SESSION_REQUEST",
                4,
                power_sha256,
            ),
        )
        _require(request == expected_request, "controller session request chain mismatch")
        session = SyntheticControllerSessionIdentity(
            run_id=request.run_id,
            session_id=_synthetic_tail_identifier(
                request.run_id,
                "CONTROLLER_FEEDBACK_SESSION",
                power_sha256,
            ),
            arm_identity_sha256=request.arm_identity_sha256,
            power_event_observation_sha256=power_sha256,
            controller_session_request_sha256=request.request_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "CONTROLLER_SESSION_IDENTITY",
                5,
                request.request_sha256,
            ),
        )
        self._controller_session = session
        return session

    def observe_t105_input_buffer_empty(
        self, request: InputBufferEmptyRequest
    ) -> InputBufferEmptyObservation:
        self._enter(FakeBoundary.INPUT_BUFFER_EMPTY)
        if self._power_event_observation is None or self._controller_session is None:
            raise PhysicalShapedOnboardingError(
                "input-buffer observation requires the active controller session"
            )
        power_sha256 = self._power_event_observation.observation_sha256
        session_sha256 = self._controller_session.identity_sha256
        expected_request = InputBufferEmptyRequest(
            run_id=self._request.run_id,
            arm_identity_sha256=self._controller_session.arm_identity_sha256,
            power_event_observation_sha256=power_sha256,
            controller_session_id=self._controller_session.session_id,
            controller_session_identity_sha256=session_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                self._request.run_id,
                "INPUT_BUFFER_EMPTY_REQUEST",
                6,
                session_sha256,
            ),
        )
        _require(request == expected_request, "input-buffer request chain mismatch")
        observation = InputBufferEmptyObservation(
            run_id=request.run_id,
            arm_identity_sha256=request.arm_identity_sha256,
            power_event_observation_sha256=request.power_event_observation_sha256,
            controller_session_id=request.controller_session_id,
            controller_session_identity_sha256=(
                request.controller_session_identity_sha256
            ),
            input_buffer_request_sha256=request.request_sha256,
            bytes_waiting=0,
            buffer_empty=True,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "INPUT_BUFFER_EMPTY_OBSERVATION",
                7,
                request.request_sha256,
            ),
        )
        self._input_buffer_observation = observation
        return observation

    def acquire_single_t105_feedback(
        self, request: T105FeedbackRequest
    ) -> T105FeedbackReceipt:
        self._enter(FakeBoundary.T105_FEEDBACK)
        if (
            self._power_event_observation is None
            or self._controller_session is None
            or self._input_buffer_observation is None
        ):
            raise PhysicalShapedOnboardingError(
                "T=105 requires power, controller-session, and empty-buffer evidence"
            )
        power_sha256 = self._power_event_observation.observation_sha256
        session_sha256 = self._controller_session.identity_sha256
        buffer_sha256 = self._input_buffer_observation.observation_sha256
        expected_request = T105FeedbackRequest(
            run_id=self._request.run_id,
            arm_identity_sha256=self._controller_session.arm_identity_sha256,
            power_event_observation_sha256=power_sha256,
            controller_session_id=self._controller_session.session_id,
            controller_session_identity_sha256=session_sha256,
            input_buffer_observation_sha256=buffer_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                self._request.run_id,
                "T105_FEEDBACK_REQUEST",
                8,
                buffer_sha256,
            ),
        )
        _require(request == expected_request, "T=105 request chain mismatch")
        self._feedback_count += 1
        request_bytes = b'{"T":105}\n'
        response_bytes = (
            b'{"T":1051,"x":0.0,"y":0.0,"z":0.0,"b":0.0,"s":0.0,'
            b'"e":0.0,"t":0.0,"torB":0,"torS":0,"torE":0,"torH":0}\n'
        )
        typed_feedback = _parse_t1051_response(
            response_bytes, request.arm_identity_sha256
        )
        return T105FeedbackReceipt(
            run_id=request.run_id,
            arm_identity_sha256=request.arm_identity_sha256,
            response_type="T=1051",
            feedback_query_ordinal=self._feedback_count,
            power_event_observation_sha256=request.power_event_observation_sha256,
            controller_session_id=request.controller_session_id,
            controller_session_identity_sha256=(
                request.controller_session_identity_sha256
            ),
            input_buffer_observation_sha256=(
                request.input_buffer_observation_sha256
            ),
            feedback_request_context_sha256=request.request_context_sha256,
            sequence_stamp=_synthetic_tail_stamp(
                request.run_id,
                "T105_FEEDBACK_RECEIPT",
                9,
                request.request_context_sha256,
            ),
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            typed_feedback=typed_feedback,
            request_bytes_sha256=hashlib.sha256(request_bytes).hexdigest(),
            response_bytes_sha256=hashlib.sha256(response_bytes).hexdigest(),
            typed_feedback_sha256=_canonical_digest(
                typed_feedback.canonical_content
            ),
            t104_motion_count=self._t104_count,
        )

    def snapshot_accounting(self) -> FakeProviderAccounting:
        self._enter(FakeBoundary.ACCOUNTING)
        return FakeProviderAccounting(
            self._request.run_id,
            tuple(self._trace),
            self._capture_count,
            self._feedback_count,
            self._t104_count,
            self._cleanup_attempts,
        )

    def cleanup(self, request: CleanupRequest) -> CleanupReceipt:
        self._cleanup_attempts += 1
        self._trace.append(FakeBoundary.CLEANUP.value)
        if self._fault_at is FakeBoundary.CLEANUP:
            raise FakeProviderBoundaryError(FakeBoundary.CLEANUP)
        self._open_sessions.clear()
        self._configured_sessions.clear()
        self._safety_observation = None
        self._power_event_observation = None
        self._controller_session = None
        self._input_buffer_observation = None
        return CleanupReceipt(request.run_id, self._cleanup_attempts, 0, 0)


def build_deterministic_fake_providers(
    request: PhysicalShapedOnboardingRequest,
    *,
    fault_at: FakeBoundary | None = None,
) -> tuple[PhysicalShapedFakeProviders, DeterministicFakeOnboardingProvider]:
    """Build the explicitly fake bundle and expose its audit object for tests."""

    provider = DeterministicFakeOnboardingProvider(
        request,
        fault_at=fault_at,
        _issuance_token=_MODULE_FAKE_PROVIDER_TOKEN,
    )
    return (
        PhysicalShapedFakeProviders(
            camera=provider,
            calibration=provider,
            arm=provider,
            safety=provider,
            lifecycle=provider,
        ),
        provider,
    )
