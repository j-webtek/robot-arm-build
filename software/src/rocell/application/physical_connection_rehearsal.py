"""Deterministic end-to-end rehearsal of the physical connection contracts.

The production connection seams deliberately expose only narrow, evidence-
returning operations.  This module wires those operations together before any
hardware is present.  Every provider constructed here is the deterministic
synthetic provider from :mod:`physical_connection_contracts`; no camera,
serial port, USB device, power rail, motion command, or contact command can be
reached by this rehearsal.

The nominal scenario proves the intended order:

* inspect the host dependency receipt;
* discover the exact persistent B0477 identity;
* open, configure, flush, and retain one fresh synthetic camera frame;
* close/reopen with identity and configuration readback, then final-close;
* inspect the RoArm USB/serial identity while unpowered; and
* perform exactly one synthetic ``T=105`` / ``T=1051`` exchange.

Named fault scenarios stop at the first injected discrepancy and emit a
canonical, hash-bound blocked report.  They are negative rehearsals, not
physical qualification evidence.  In particular, the retry-prohibition case
deliberately makes a second *provider call* after one successful synthetic
exchange and proves that it is rejected before another write is represented.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import re
from typing import Mapping

from rocell.application.physical_connection_contracts import (
    B0477DiscoveryRequest,
    B0477ExactConfiguration,
    B0477ManualControls,
    B0477UvcIdentity,
    CameraCloseReceipt,
    CameraCloseRequest,
    CameraConfigurationReceipt,
    CameraConfigurationRequest,
    CameraFlushRequest,
    CameraOpenRequest,
    CameraReopenRequest,
    CameraSessionReceipt,
    DependencyObservation,
    DependencyRequirement,
    DeterministicFakeB0477ConnectionProvider,
    DeterministicFakeHostDependencyProvider,
    DeterministicFakeRoArmConnectionProvider,
    FAKE_PROVIDER_DESCRIPTOR,
    FakeConnectionBoundaryError,
    FreshFrameRequest,
    HostDependencyRequest,
    HostIdentity,
    PhysicalConnectionContractError,
    RoArmUsbSerialIdentity,
    SingleT105FeedbackRequest,
    UnpoweredArmIdentityRequest,
    Usb3Topology,
    UsbDriverIdentity,
    canonical_sha256,
)


PHYSICAL_CONNECTION_REHEARSAL_SCHEMA = "rocell.physical_connection_rehearsal.v1"
REHEARSAL_STEP_EVIDENCE_SCHEMA = (
    "rocell.physical_connection_rehearsal_step_evidence.v1"
)
DEFAULT_REHEARSAL_RUN_ID = "physical-connection-rehearsal-001"

_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")
_MAX_TEXT_CHARS = 2_048
_MAX_EVIDENCE_JSON_CHARS = 262_144

_NOMINAL_STEP_IDS = (
    "host_dependencies",
    "camera_discovery",
    "camera_open",
    "camera_configuration",
    "camera_flush",
    "camera_fresh_frame",
    "camera_close_reopen",
    "camera_final_close",
    "arm_unpowered_identity",
    "arm_single_t105",
)

_EXPECTED_BLOCK_STEP = {
    "WRONG_CAMERA_IDENTITY": "camera_discovery",
    "WRONG_CAMERA_MODE": "camera_configuration",
    "STALE_CAMERA_FRAME": "camera_fresh_frame",
    "CAMERA_IDENTITY_DRIFT": "camera_close_reopen",
    "CAMERA_CLOSE_FAILURE": "camera_final_close",
    "WRONG_ARM_IDENTITY": "arm_unpowered_identity",
    "DIRTY_ARM_BUFFER": "arm_single_t105",
    "MALFORMED_T1051_RESPONSE": "arm_single_t105",
    "RETRY_PROHIBITION": "arm_retry_prohibition",
}


class PhysicalConnectionRehearsalError(ValueError):
    """A rehearsal input, transition, or canonical report is invalid."""


class RehearsalFault(str, Enum):
    """One deterministic negative connection scenario."""

    NONE = "NONE"
    WRONG_CAMERA_IDENTITY = "WRONG_CAMERA_IDENTITY"
    WRONG_CAMERA_MODE = "WRONG_CAMERA_MODE"
    STALE_CAMERA_FRAME = "STALE_CAMERA_FRAME"
    CAMERA_IDENTITY_DRIFT = "CAMERA_IDENTITY_DRIFT"
    CAMERA_CLOSE_FAILURE = "CAMERA_CLOSE_FAILURE"
    WRONG_ARM_IDENTITY = "WRONG_ARM_IDENTITY"
    DIRTY_ARM_BUFFER = "DIRTY_ARM_BUFFER"
    MALFORMED_T1051_RESPONSE = "MALFORMED_T1051_RESPONSE"
    RETRY_PROHIBITION = "RETRY_PROHIBITION"


class RehearsalOutcome(str, Enum):
    """Terminal result without implying any physical qualification."""

    COMPLETE_SYNTHETIC = "COMPLETE_SYNTHETIC"
    EXPECTED_FAULT_BLOCKED = "EXPECTED_FAULT_BLOCKED"


class RehearsalStepOutcome(str, Enum):
    """Outcome for one ordered, immutable step receipt."""

    PASS = "PASS"
    BLOCKED_EXPECTED = "BLOCKED_EXPECTED"
    CLEANUP_PASS = "CLEANUP_PASS"


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PhysicalConnectionRehearsalError(
            "rehearsal evidence cannot be canonicalized"
        ) from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise PhysicalConnectionRehearsalError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise PhysicalConnectionRehearsalError(f"{label} is invalid")
    return value


def _text(
    value: object, label: str, *, maximum: int = _MAX_TEXT_CHARS
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PhysicalConnectionRehearsalError(
            f"{label} must be non-empty, trimmed, bounded text"
        )
    return value


def _step_input_sha256(value: Mapping[str, object]) -> str:
    """Bind an operation input even when its request type has no hash property."""

    return canonical_sha256(dict(value))


@dataclass(frozen=True, slots=True)
class RehearsalStepReceipt:
    """Canonical wrapper around one provider receipt or one expected block."""

    sequence: int
    step_id: str
    outcome: RehearsalStepOutcome
    provider_role: str
    provider_descriptor_sha256: str
    input_sha256: str
    evidence_sha256: str
    evidence_canonical_json: str

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 1:
            raise PhysicalConnectionRehearsalError("step sequence must be positive")
        object.__setattr__(self, "step_id", _identifier(self.step_id, "step_id"))
        object.__setattr__(
            self, "provider_role", _identifier(self.provider_role, "provider_role")
        )
        if not isinstance(self.outcome, RehearsalStepOutcome):
            raise PhysicalConnectionRehearsalError(
                "step outcome must be RehearsalStepOutcome"
            )
        for name in (
            "provider_descriptor_sha256",
            "input_sha256",
            "evidence_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        canonical = _text(
            self.evidence_canonical_json,
            "evidence_canonical_json",
            maximum=_MAX_EVIDENCE_JSON_CHARS,
        )
        try:
            decoded = json.loads(canonical)
        except json.JSONDecodeError as exc:
            raise PhysicalConnectionRehearsalError(
                "step evidence is not valid JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise PhysicalConnectionRehearsalError(
                "step evidence must decode to an object"
            )
        if _canonical_json(decoded) != canonical:
            raise PhysicalConnectionRehearsalError(
                "step evidence must use canonical JSON serialization"
            )
        if decoded.get("schema") != REHEARSAL_STEP_EVIDENCE_SCHEMA:
            raise PhysicalConnectionRehearsalError(
                "step evidence uses an unsupported schema"
            )
        if _sha256_bytes(canonical.encode("utf-8")) != self.evidence_sha256:
            raise PhysicalConnectionRehearsalError(
                "evidence_sha256 does not bind evidence_canonical_json"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "step_id": self.step_id,
            "outcome": self.outcome.value,
            "provider_role": self.provider_role,
            "provider_descriptor_sha256": self.provider_descriptor_sha256,
            "input_sha256": self.input_sha256,
            "evidence_sha256": self.evidence_sha256,
            "evidence": json.loads(self.evidence_canonical_json),
        }


@dataclass(frozen=True, slots=True)
class SimulationEffectSummary:
    """Synthetic calls represented by the report; never physical effects."""

    camera_open_calls: int
    camera_capture_calls: int
    retained_camera_frames: int
    arm_identity_inspections: int
    t105_provider_calls: int
    t105_wire_attempts: int
    retry_writes: int

    def __post_init__(self) -> None:
        for name in (
            "camera_open_calls",
            "camera_capture_calls",
            "retained_camera_frames",
            "arm_identity_inspections",
            "t105_provider_calls",
            "t105_wire_attempts",
            "retry_writes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise PhysicalConnectionRehearsalError(
                    f"{name} must be a non-negative integer"
                )
        if self.retained_camera_frames > self.camera_capture_calls:
            raise PhysicalConnectionRehearsalError(
                "retained frames cannot exceed synthetic capture calls"
            )
        if self.t105_wire_attempts > self.t105_provider_calls:
            raise PhysicalConnectionRehearsalError(
                "synthetic T=105 wire attempts cannot exceed provider calls"
            )
        if self.retry_writes != 0:
            raise PhysicalConnectionRehearsalError(
                "the connection rehearsal can never represent a retry write"
            )

    def to_dict(self) -> dict[str, int]:
        return {
            name: getattr(self, name)
            for name in (
                "camera_open_calls",
                "camera_capture_calls",
                "retained_camera_frames",
                "arm_identity_inspections",
                "t105_provider_calls",
                "t105_wire_attempts",
                "retry_writes",
            )
        }


@dataclass(frozen=True, slots=True)
class PhysicalConnectionRehearsalReport:
    """Ordered synthetic receipts with permanently zero physical authority."""

    run_id: str
    fault: RehearsalFault
    outcome: RehearsalOutcome
    contract_sha256: str
    provider_role_hashes: tuple[tuple[str, str], ...]
    steps: tuple[RehearsalStepReceipt, ...]
    simulated_effects: SimulationEffectSummary
    schema: str = PHYSICAL_CONNECTION_REHEARSAL_SCHEMA
    simulation_only: bool = field(init=False, default=True)
    hardware_accessed: bool = field(init=False, default=False)
    physical_camera_open_count: int = field(init=False, default=0)
    physical_camera_frame_count: int = field(init=False, default=0)
    physical_serial_open_count: int = field(init=False, default=0)
    physical_serial_write_count: int = field(init=False, default=0)
    physical_power_event_count: int = field(init=False, default=0)
    t104_command_count: int = field(init=False, default=0)
    motion_command_count: int = field(init=False, default=0)
    contact_command_count: int = field(init=False, default=0)
    torque_command_count: int = field(init=False, default=0)
    hardware_presence_authority: bool = field(init=False, default=False)
    live_capture_authority: bool = field(init=False, default=False)
    feedback_connection_authority: bool = field(init=False, default=False)
    robot_motion_authority: bool = field(init=False, default=False)
    contact_authority: bool = field(init=False, default=False)
    physical_qualification: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if self.schema != PHYSICAL_CONNECTION_REHEARSAL_SCHEMA:
            raise PhysicalConnectionRehearsalError(
                "unsupported physical connection rehearsal schema"
            )
        _text(self.run_id, "run_id")
        if not isinstance(self.fault, RehearsalFault):
            raise PhysicalConnectionRehearsalError("fault must be RehearsalFault")
        if not isinstance(self.outcome, RehearsalOutcome):
            raise PhysicalConnectionRehearsalError(
                "outcome must be RehearsalOutcome"
            )
        _digest(self.contract_sha256, "contract_sha256")
        if (
            not isinstance(self.provider_role_hashes, tuple)
            or self.provider_role_hashes
            != tuple(sorted(self.provider_role_hashes, key=lambda item: item[0]))
            or tuple(role for role, _digest_value in self.provider_role_hashes)
            != ("arm", "camera", "host")
        ):
            raise PhysicalConnectionRehearsalError(
                "provider_role_hashes must be the canonical arm/camera/host tuple"
            )
        for role, digest in self.provider_role_hashes:
            _identifier(role, "provider role")
            _digest(digest, f"provider digest for {role}")
            if digest != FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256:
                raise PhysicalConnectionRehearsalError(
                    "the hardware-free rehearsal accepts only the deterministic fake provider"
                )
        if not isinstance(self.steps, tuple) or not self.steps:
            raise PhysicalConnectionRehearsalError("steps must be a non-empty tuple")
        if any(not isinstance(step, RehearsalStepReceipt) for step in self.steps):
            raise PhysicalConnectionRehearsalError("steps contains an invalid item")
        if tuple(step.sequence for step in self.steps) != tuple(
            range(1, len(self.steps) + 1)
        ):
            raise PhysicalConnectionRehearsalError(
                "step sequence numbers must be contiguous and ordered"
            )
        if len({step.step_id for step in self.steps}) != len(self.steps):
            raise PhysicalConnectionRehearsalError("step ids must be unique")
        role_hashes = dict(self.provider_role_hashes)
        for step in self.steps:
            if step.provider_role not in role_hashes:
                raise PhysicalConnectionRehearsalError(
                    "step names an undeclared provider role"
                )
            if step.provider_descriptor_sha256 != role_hashes[step.provider_role]:
                raise PhysicalConnectionRehearsalError(
                    "step provider digest does not match its declared provider role"
                )
        if not isinstance(self.simulated_effects, SimulationEffectSummary):
            raise PhysicalConnectionRehearsalError(
                "simulated_effects must be SimulationEffectSummary"
            )
        blocked = tuple(
            step for step in self.steps if step.outcome is RehearsalStepOutcome.BLOCKED_EXPECTED
        )
        if self.fault is RehearsalFault.NONE:
            if self.outcome is not RehearsalOutcome.COMPLETE_SYNTHETIC:
                raise PhysicalConnectionRehearsalError(
                    "nominal rehearsal must complete synthetically"
                )
            if blocked or tuple(step.step_id for step in self.steps) != _NOMINAL_STEP_IDS:
                raise PhysicalConnectionRehearsalError(
                    "nominal rehearsal must retain the exact successful step lifecycle"
                )
            if any(step.outcome is not RehearsalStepOutcome.PASS for step in self.steps):
                raise PhysicalConnectionRehearsalError(
                    "nominal rehearsal cannot contain cleanup or blocked outcomes"
                )
        else:
            if self.outcome is not RehearsalOutcome.EXPECTED_FAULT_BLOCKED:
                raise PhysicalConnectionRehearsalError(
                    "fault rehearsal must have the expected-blocked outcome"
                )
            if len(blocked) != 1:
                raise PhysicalConnectionRehearsalError(
                    "fault rehearsal must retain exactly one expected block"
                )
            if blocked[0].step_id != _EXPECTED_BLOCK_STEP[self.fault.value]:
                raise PhysicalConnectionRehearsalError(
                    "fault rehearsal blocked at the wrong lifecycle step"
                )
            blocked_index = self.steps.index(blocked[0])
            if any(
                step.outcome is not RehearsalStepOutcome.CLEANUP_PASS
                for step in self.steps[blocked_index + 1 :]
            ):
                raise PhysicalConnectionRehearsalError(
                    "only explicit cleanup receipts may follow an expected block"
                )

    @property
    def rehearsal_passed(self) -> bool:
        """True only for the complete nominal synthetic lifecycle."""

        return (
            self.fault is RehearsalFault.NONE
            and self.outcome is RehearsalOutcome.COMPLETE_SYNTHETIC
        )

    @property
    def expected_fault_blocked(self) -> bool:
        return self.outcome is RehearsalOutcome.EXPECTED_FAULT_BLOCKED

    @property
    def all_physical_effects_zero(self) -> bool:
        return all(
            value == 0
            for value in (
                self.physical_camera_open_count,
                self.physical_camera_frame_count,
                self.physical_serial_open_count,
                self.physical_serial_write_count,
                self.physical_power_event_count,
                self.t104_command_count,
                self.motion_command_count,
                self.contact_command_count,
                self.torque_command_count,
            )
        )

    @property
    def no_forbidden_commands(self) -> bool:
        return (
            self.t104_command_count == 0
            and self.motion_command_count == 0
            and self.contact_command_count == 0
            and self.torque_command_count == 0
            and self.simulated_effects.retry_writes == 0
        )

    def to_dict(self) -> dict[str, object]:
        physical_effects = {
            "camera_open_count": self.physical_camera_open_count,
            "camera_frame_count": self.physical_camera_frame_count,
            "serial_open_count": self.physical_serial_open_count,
            "serial_write_count": self.physical_serial_write_count,
            "power_event_count": self.physical_power_event_count,
            "t104_command_count": self.t104_command_count,
            "motion_command_count": self.motion_command_count,
            "contact_command_count": self.contact_command_count,
            "torque_command_count": self.torque_command_count,
        }
        authority = {
            "hardware_presence": self.hardware_presence_authority,
            "live_capture": self.live_capture_authority,
            "feedback_connection": self.feedback_connection_authority,
            "robot_motion": self.robot_motion_authority,
            "contact": self.contact_authority,
            "physical_qualification": self.physical_qualification,
        }
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "fault": self.fault.value,
            "outcome": self.outcome.value,
            "rehearsal_passed": self.rehearsal_passed,
            "expected_fault_blocked": self.expected_fault_blocked,
            "contract_sha256": self.contract_sha256,
            "provider_descriptor": FAKE_PROVIDER_DESCRIPTOR.to_dict(),
            "provider_descriptor_sha256": (
                FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256
            ),
            "provider_role_hashes": [
                {"role": role, "provider_descriptor_sha256": digest}
                for role, digest in self.provider_role_hashes
            ],
            "steps": [step.to_dict() for step in self.steps],
            "evidence_hashes": [
                {
                    "sequence": step.sequence,
                    "step_id": step.step_id,
                    "evidence_sha256": step.evidence_sha256,
                }
                for step in self.steps
            ],
            "simulated_effects": self.simulated_effects.to_dict(),
            "physical_effects": physical_effects,
            "safety_invariants": {
                "all_physical_effects_zero": self.all_physical_effects_zero,
                "no_t104_motion_contact_or_torque": self.no_forbidden_commands,
                "no_retry_write": self.simulated_effects.retry_writes == 0,
            },
            "simulation_only": self.simulation_only,
            "hardware_accessed": self.hardware_accessed,
            "authority": authority,
        }

    @property
    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def report_sha256(self) -> str:
        return _sha256_bytes(self.canonical_json.encode("utf-8"))


_CONTRACT_PAYLOAD = {
    "schema": PHYSICAL_CONNECTION_REHEARSAL_SCHEMA,
    "provider_descriptor_sha256": FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256,
    "nominal_steps": list(_NOMINAL_STEP_IDS),
    "camera": {
        "manufacturer": "Arducam",
        "model": "B0477",
        "sensor": "Sony IMX283",
        "width_px": 5472,
        "height_px": 3648,
        "fps_numerator": 9,
        "fps_denominator": 1,
        "fourcc": "YUY2",
        "bus": "USB_3_X",
        "persistent_identity_required": True,
        "numeric_ordinal_fallback": False,
    },
    "arm": {
        "product": "RoArm-M3 Pro",
        "controller": "ESP32",
        "baudrate": 115200,
        "rts": False,
        "dtr": False,
        "request": "T=105",
        "response": "T=1051",
        "write_attempts": 1,
        "retry_count": 0,
        "t104_motion_count": 0,
    },
}
REHEARSAL_CONTRACT_SHA256 = canonical_sha256(_CONTRACT_PAYLOAD)


class _FaultingFakeB0477Provider(DeterministicFakeB0477ConnectionProvider):
    """Small deterministic fault shim; it inherits the zero-I/O fake boundary."""

    def __init__(self, identity: B0477UvcIdentity, fault: RehearsalFault) -> None:
        super().__init__(identity)
        self._rehearsal_fault = fault

    def configure_exact_b0477(
        self, request: CameraConfigurationRequest
    ) -> CameraConfigurationReceipt:
        # The base fake can only construct exact valid configurations.  This
        # negative shim represents a provider detecting a mismatched readback
        # and refusing to manufacture a valid receipt for it.
        if self._rehearsal_fault is RehearsalFault.WRONG_CAMERA_MODE:
            raise FakeConnectionBoundaryError(
                "deterministic camera mode readback differs from 5472x3648@9 YUY2"
            )
        return super().configure_exact_b0477(request)

    def close_selected_b0477(
        self, request: CameraCloseRequest
    ) -> CameraCloseReceipt:
        if (
            self._rehearsal_fault is RehearsalFault.CAMERA_CLOSE_FAILURE
            and request.session.session_ordinal == 2
        ):
            started = request.requested_monotonic_ns
            return CameraCloseReceipt(
                run_id=request.run_id,
                session_id=request.session.session_id,
                provider_descriptor_sha256=self.descriptor.descriptor_sha256,
                request_sha256=request.request_sha256,
                session_receipt_sha256=request.session.receipt_sha256,
                close_attempted=True,
                close_succeeded=False,
                was_already_closed=False,
                close_started_monotonic_ns=started,
                close_completed_monotonic_ns=started + 1,
                failure_code="DETERMINISTIC_FINAL_CLOSE_FAILURE",
            )
        return super().close_selected_b0477(request)


def _driver(service: str) -> UsbDriverIdentity:
    return UsbDriverIdentity(
        provider="RoCell Synthetic Driver Vendor",
        service=service,
        version="0.0.synthetic",
        package_or_inf_path=f"synthetic://drivers/{service}/package.inf",
    )


def _camera_identity() -> B0477UvcIdentity:
    return B0477UvcIdentity(
        vid="ffff",
        pid="0477",
        unit_serial="SYNTHETIC-B0477-UNIT-001",
        persistent_os_path="synthetic://pnp/camera/b0477/unit-001",
        device_instance_id="USB\\VID_FFFF&PID_0477\\SYNTHETIC-B0477-UNIT-001",
        driver=_driver("usbvideo"),
        topology=Usb3Topology(
            host_controller_instance_id="PCI\\SYNTHETIC-XHCI-CONTROLLER-001",
            hub_instance_path=("USB\\ROOT_HUB30\\SYNTHETIC-001",),
            port_chain=(3,),
            negotiated_speed_mbps=5_000,
            negotiated_generation="USB_3_2_GEN_1",
        ),
    )


def _arm_identity() -> RoArmUsbSerialIdentity:
    return RoArmUsbSerialIdentity(
        vid="ffff",
        pid="0002",
        unit_serial="SYNTHETIC-ROARM-M3-PRO-001",
        persistent_instance_id="USB\\VID_FFFF&PID_0002\\SYNTHETIC-ROARM-001",
        persistent_port_path="synthetic://ports/roarm/unit-001",
        port_name="COM99",
        driver=_driver("usbser"),
    )


def _feedback_response() -> bytes:
    return (
        b'{"T":1051,"x":120.0,"y":0.0,"z":180.0,"b":0.1,'
        b'"s":0.2,"e":0.3,"t":0.4,"r":0.5,"g":0.6,'
        b'"tB":1,"tS":2,"tE":3,"tT":4,"tR":5,"tG":6,'
        b'"torswitchB":0,"torswitchS":0,"torswitchE":0,'
        b'"torswitchT":0,"torswitchR":0,"torswitchG":0,"v":1200}\n'
    )


def _step(
    steps: list[RehearsalStepReceipt],
    *,
    step_id: str,
    outcome: RehearsalStepOutcome,
    provider_role: str,
    input_sha256: str,
    evidence_kind: str,
    evidence: Mapping[str, object],
) -> None:
    envelope = {
        "schema": REHEARSAL_STEP_EVIDENCE_SCHEMA,
        "evidence_kind": evidence_kind,
        "provider_descriptor_sha256": FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256,
        "payload": dict(evidence),
    }
    canonical = _canonical_json(envelope)
    steps.append(
        RehearsalStepReceipt(
            sequence=len(steps) + 1,
            step_id=step_id,
            outcome=outcome,
            provider_role=provider_role,
            provider_descriptor_sha256=(
                FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256
            ),
            input_sha256=input_sha256,
            evidence_sha256=_sha256_bytes(canonical.encode("utf-8")),
            evidence_canonical_json=canonical,
        )
    )


def _blocked_step(
    steps: list[RehearsalStepReceipt],
    *,
    step_id: str,
    provider_role: str,
    input_sha256: str,
    fault: RehearsalFault,
    error: Exception,
) -> None:
    _step(
        steps,
        step_id=step_id,
        outcome=RehearsalStepOutcome.BLOCKED_EXPECTED,
        provider_role=provider_role,
        input_sha256=input_sha256,
        evidence_kind="expected_fault_block",
        evidence={
            "fault": fault.value,
            "error_type": type(error).__name__,
            "message": _text(str(error), "fault message"),
        },
    )


def _report(
    *,
    run_id: str,
    fault: RehearsalFault,
    steps: list[RehearsalStepReceipt],
    camera_open_calls: int,
    camera_capture_calls: int,
    retained_camera_frames: int,
    arm_identity_inspections: int,
    t105_provider_calls: int,
    t105_wire_attempts: int,
) -> PhysicalConnectionRehearsalReport:
    return PhysicalConnectionRehearsalReport(
        run_id=run_id,
        fault=fault,
        outcome=(
            RehearsalOutcome.COMPLETE_SYNTHETIC
            if fault is RehearsalFault.NONE
            else RehearsalOutcome.EXPECTED_FAULT_BLOCKED
        ),
        contract_sha256=REHEARSAL_CONTRACT_SHA256,
        provider_role_hashes=tuple(
            (role, FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256)
            for role in ("arm", "camera", "host")
        ),
        steps=tuple(steps),
        simulated_effects=SimulationEffectSummary(
            camera_open_calls=camera_open_calls,
            camera_capture_calls=camera_capture_calls,
            retained_camera_frames=retained_camera_frames,
            arm_identity_inspections=arm_identity_inspections,
            t105_provider_calls=t105_provider_calls,
            t105_wire_attempts=t105_wire_attempts,
            retry_writes=0,
        ),
    )


def run_physical_connection_rehearsal(
    *,
    run_id: str = DEFAULT_REHEARSAL_RUN_ID,
    fault: RehearsalFault = RehearsalFault.NONE,
) -> PhysicalConnectionRehearsalReport:
    """Run one deterministic connection lifecycle or named negative scenario.

    The function accepts no providers or device selectors by design.  This
    prevents an apparently harmless test entry point from acquiring physical
    I/O authority later.  Fault reports prove that the corresponding mismatch
    was blocked; only the ``NONE`` scenario has ``rehearsal_passed`` set.
    """

    _text(run_id, "run_id")
    if not isinstance(fault, RehearsalFault):
        raise PhysicalConnectionRehearsalError("fault must be RehearsalFault")

    steps: list[RehearsalStepReceipt] = []
    camera_open_calls = 0
    camera_capture_calls = 0
    retained_camera_frames = 0
    arm_identity_inspections = 0
    t105_provider_calls = 0
    t105_wire_attempts = 0

    requirements = (
        DependencyRequirement("opencv-contrib-python", ">=4.12,<5", True),
        DependencyRequirement("pyserial", ">=3.5,<4", True),
    )
    observations = {
        requirement.name: DependencyObservation(
            name=requirement.name,
            installed_version=(
                "4.12.0+synthetic"
                if requirement.name == "opencv-contrib-python"
                else "3.5.0+synthetic"
            ),
            artifact_path=f"synthetic://packages/{requirement.name}",
            artifact_sha256=_sha256_bytes(requirement.name.encode("utf-8")),
            available=True,
        )
        for requirement in requirements
    }
    host = HostIdentity(
        host_id="SYNTHETIC-HOST-001",
        os_name="Windows",
        os_release="synthetic",
        architecture="AMD64",
        python_implementation="CPython",
        python_version="3.12.synthetic",
        python_executable="synthetic://python/python.exe",
        python_executable_sha256="2" * 64,
    )
    host_provider = DeterministicFakeHostDependencyProvider(host, observations)
    host_request = HostDependencyRequest(run_id, "3" * 64, requirements)
    host_receipt = host_provider.inspect_host_dependencies(host_request)
    _step(
        steps,
        step_id="host_dependencies",
        outcome=RehearsalStepOutcome.PASS,
        provider_role="host",
        input_sha256=host_request.request_sha256,
        evidence_kind="host_dependency_receipt",
        evidence=host_receipt.to_dict(),
    )

    camera_identity = _camera_identity()
    camera_provider = _FaultingFakeB0477Provider(camera_identity, fault)
    camera_session: CameraSessionReceipt | None = None
    active_step = "camera_discovery"
    active_input_sha256 = canonical_sha256(
        {"run_id": run_id, "fault": fault.value, "stage": active_step}
    )
    try:
        expected_camera = (
            replace(camera_identity, unit_serial="SYNTHETIC-WRONG-B0477-UNIT")
            if fault is RehearsalFault.WRONG_CAMERA_IDENTITY
            else camera_identity
        )
        discovery_request = B0477DiscoveryRequest(run_id, expected_camera)
        active_input_sha256 = discovery_request.request_sha256
        discovery = camera_provider.discover_exact_b0477(discovery_request)
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="b0477_discovery_receipt",
            evidence=discovery.to_dict(),
        )

        active_step = "camera_open"
        open_request = CameraOpenRequest(
            run_id, discovery.receipt_sha256, camera_identity
        )
        active_input_sha256 = _step_input_sha256(
            {
                "run_id": run_id,
                "discovery_receipt_sha256": discovery.receipt_sha256,
                "camera_identity_sha256": camera_identity.identity_sha256,
            }
        )
        camera_session = camera_provider.open_selected_b0477(open_request)
        camera_open_calls += 1
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="camera_session_receipt",
            evidence=camera_session.to_dict(),
        )

        desired = B0477ExactConfiguration(
            B0477ManualControls(8_000.0, 1.0, 5_000.0)
        )
        active_step = "camera_configuration"
        configuration_request = CameraConfigurationRequest(
            run_id,
            camera_session.receipt_sha256,
            camera_identity.identity_sha256,
            camera_session.session_id,
            desired,
        )
        active_input_sha256 = configuration_request.request_sha256
        configuration = camera_provider.configure_exact_b0477(configuration_request)
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="b0477_configuration_receipt",
            evidence=configuration.to_dict(),
        )

        active_step = "camera_flush"
        flush_request = CameraFlushRequest(
            run_id,
            camera_session.session_id,
            configuration.receipt_sha256,
        )
        active_input_sha256 = flush_request.request_sha256
        flush = camera_provider.flush_b0477_buffers(flush_request)
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="b0477_flush_receipt",
            evidence=flush.to_dict(),
        )

        active_step = "camera_fresh_frame"
        frame_request = FreshFrameRequest(
            run_id,
            camera_session.session_id,
            flush.receipt_sha256,
            desired.configuration_sha256,
            flush.last_discarded_sequence,
            (
                1
                if fault is RehearsalFault.STALE_CAMERA_FRAME
                else flush.flush_completed_monotonic_ns
            ),
            1 if fault is RehearsalFault.STALE_CAMERA_FRAME else 1_000,
        )
        active_input_sha256 = frame_request.request_sha256
        camera_capture_calls += 1
        captured = camera_provider.capture_fresh_b0477_frame(frame_request)
        retained_camera_frames += 1
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="captured_b0477_frame",
            evidence={
                "carrier_sha256": captured.carrier_sha256,
                "receipt": captured.receipt.to_dict(),
                "payload_bytes": len(captured.payload),
                "payload_sha256": _sha256_bytes(captured.payload),
            },
        )

        active_step = "camera_close_reopen"
        expected_reopen_identity = (
            replace(camera_identity, unit_serial="SYNTHETIC-DRIFTED-B0477-UNIT")
            if fault is RehearsalFault.CAMERA_IDENTITY_DRIFT
            else camera_identity
        )
        reopen_request = CameraReopenRequest(
            run_id,
            camera_session,
            expected_reopen_identity,
            desired,
        )
        active_input_sha256 = reopen_request.request_sha256
        reopen = camera_provider.reopen_exact_b0477(reopen_request)
        camera_open_calls += 1
        camera_session = reopen.reopened_session
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="b0477_close_reopen_receipt",
            evidence=reopen.to_dict(),
        )

        active_step = "camera_final_close"
        final_close_request = CameraCloseRequest(
            run_id,
            camera_session,
            "CONNECTION_REHEARSAL_COMPLETE",
            reopen.configuration_readback.readback_monotonic_ns + 1,
        )
        active_input_sha256 = final_close_request.request_sha256
        final_close = camera_provider.close_selected_b0477(final_close_request)
        _step(
            steps,
            step_id=active_step,
            outcome=(
                RehearsalStepOutcome.PASS
                if final_close.close_succeeded
                else RehearsalStepOutcome.BLOCKED_EXPECTED
            ),
            provider_role="camera",
            input_sha256=active_input_sha256,
            evidence_kind="b0477_final_close_receipt",
            evidence=final_close.to_dict(),
        )
        if not final_close.close_succeeded:
            if fault is not RehearsalFault.CAMERA_CLOSE_FAILURE:
                raise PhysicalConnectionRehearsalError(
                    "unexpected deterministic camera final-close failure"
                )
            return _report(
                run_id=run_id,
                fault=fault,
                steps=steps,
                camera_open_calls=camera_open_calls,
                camera_capture_calls=camera_capture_calls,
                retained_camera_frames=retained_camera_frames,
                arm_identity_inspections=arm_identity_inspections,
                t105_provider_calls=t105_provider_calls,
                t105_wire_attempts=t105_wire_attempts,
            )
        camera_session = None
    except (FakeConnectionBoundaryError, PhysicalConnectionContractError) as exc:
        if fault is RehearsalFault.NONE:
            raise PhysicalConnectionRehearsalError(
                f"nominal connection rehearsal failed at {active_step}: {exc}"
            ) from exc
        _blocked_step(
            steps,
            step_id=active_step,
            provider_role="camera",
            input_sha256=active_input_sha256,
            fault=fault,
            error=exc,
        )
        if camera_session is not None:
            cleanup_request = CameraCloseRequest(
                run_id,
                camera_session,
                "EXPECTED_FAULT_CLEANUP",
                2_100_000,
            )
            cleanup = camera_provider.close_selected_b0477(cleanup_request)
            if not cleanup.close_succeeded:
                raise PhysicalConnectionRehearsalError(
                    "deterministic camera cleanup failed after expected fault"
                )
            _step(
                steps,
                step_id="camera_fault_cleanup",
                outcome=RehearsalStepOutcome.CLEANUP_PASS,
                provider_role="camera",
                input_sha256=cleanup_request.request_sha256,
                evidence_kind="b0477_fault_cleanup_receipt",
                evidence=cleanup.to_dict(),
            )
        return _report(
            run_id=run_id,
            fault=fault,
            steps=steps,
            camera_open_calls=camera_open_calls,
            camera_capture_calls=camera_capture_calls,
            retained_camera_frames=retained_camera_frames,
            arm_identity_inspections=arm_identity_inspections,
            t105_provider_calls=t105_provider_calls,
            t105_wire_attempts=t105_wire_attempts,
        )

    arm_identity = _arm_identity()
    response = (
        b"not-json\n"
        if fault is RehearsalFault.MALFORMED_T1051_RESPONSE
        else _feedback_response()
    )
    arm_provider = DeterministicFakeRoArmConnectionProvider(
        arm_identity,
        response,
        pre_request_bytes_waiting=(
            1 if fault is RehearsalFault.DIRTY_ARM_BUFFER else 0
        ),
    )
    active_step = "arm_unpowered_identity"
    active_input_sha256 = canonical_sha256(
        {"run_id": run_id, "fault": fault.value, "stage": active_step}
    )
    try:
        expected_arm = (
            replace(arm_identity, unit_serial="SYNTHETIC-WRONG-ROARM-UNIT")
            if fault is RehearsalFault.WRONG_ARM_IDENTITY
            else arm_identity
        )
        identity_request = UnpoweredArmIdentityRequest(
            run_id,
            expected_arm,
            canonical_sha256(
                {
                    "run_id": run_id,
                    "attestation": "SYNTHETIC_ARM_POWER_OFF",
                    "physical_effect": "NONE",
                }
            ),
        )
        active_input_sha256 = identity_request.request_sha256
        arm_identity_inspections += 1
        identity_receipt = arm_provider.inspect_unpowered_usb_identity(
            identity_request
        )
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="arm",
            input_sha256=active_input_sha256,
            evidence_kind="roarm_unpowered_identity_receipt",
            evidence=identity_receipt.to_dict(),
        )

        active_step = "arm_single_t105"
        feedback_request = SingleT105FeedbackRequest(
            run_id,
            identity_receipt.receipt_sha256,
            arm_identity.identity_sha256,
            canonical_sha256(
                {"run_id": run_id, "observation": "SYNTHETIC_POWER_EVENT"}
            ),
            canonical_sha256(
                {"run_id": run_id, "permit": "SYNTHETIC_FEEDBACK_ONLY"}
            ),
            f"{run_id}-feedback-session-001",
            3_000_100,
        )
        active_input_sha256 = feedback_request.request_context_sha256
        t105_provider_calls += 1
        t105_wire_attempts += 1
        feedback_receipt = arm_provider.acquire_single_t105_feedback(
            feedback_request
        )
        _step(
            steps,
            step_id=active_step,
            outcome=RehearsalStepOutcome.PASS,
            provider_role="arm",
            input_sha256=active_input_sha256,
            evidence_kind="roarm_single_t105_receipt",
            evidence=feedback_receipt.to_dict(),
        )

        if fault is RehearsalFault.RETRY_PROHIBITION:
            active_step = "arm_retry_prohibition"
            active_input_sha256 = canonical_sha256(
                {
                    "original_request_context_sha256": (
                        feedback_request.request_context_sha256
                    ),
                    "prohibited_provider_call_ordinal": 2,
                    "expected_additional_write_count": 0,
                }
            )
            t105_provider_calls += 1
            try:
                arm_provider.acquire_single_t105_feedback(feedback_request)
            except FakeConnectionBoundaryError as exc:
                _blocked_step(
                    steps,
                    step_id=active_step,
                    provider_role="arm",
                    input_sha256=active_input_sha256,
                    fault=fault,
                    error=exc,
                )
                return _report(
                    run_id=run_id,
                    fault=fault,
                    steps=steps,
                    camera_open_calls=camera_open_calls,
                    camera_capture_calls=camera_capture_calls,
                    retained_camera_frames=retained_camera_frames,
                    arm_identity_inspections=arm_identity_inspections,
                    t105_provider_calls=t105_provider_calls,
                    t105_wire_attempts=t105_wire_attempts,
                )
            raise PhysicalConnectionRehearsalError(
                "deterministic provider unexpectedly allowed a T=105 retry"
            )
    except (FakeConnectionBoundaryError, PhysicalConnectionContractError) as exc:
        if fault is RehearsalFault.NONE:
            raise PhysicalConnectionRehearsalError(
                f"nominal connection rehearsal failed at {active_step}: {exc}"
            ) from exc
        _blocked_step(
            steps,
            step_id=active_step,
            provider_role="arm",
            input_sha256=active_input_sha256,
            fault=fault,
            error=exc,
        )
        return _report(
            run_id=run_id,
            fault=fault,
            steps=steps,
            camera_open_calls=camera_open_calls,
            camera_capture_calls=camera_capture_calls,
            retained_camera_frames=retained_camera_frames,
            arm_identity_inspections=arm_identity_inspections,
            t105_provider_calls=t105_provider_calls,
            t105_wire_attempts=t105_wire_attempts,
        )

    if fault is not RehearsalFault.NONE:
        raise PhysicalConnectionRehearsalError(
            f"fault scenario was not exercised: {fault.value}"
        )
    return _report(
        run_id=run_id,
        fault=fault,
        steps=steps,
        camera_open_calls=camera_open_calls,
        camera_capture_calls=camera_capture_calls,
        retained_camera_frames=retained_camera_frames,
        arm_identity_inspections=arm_identity_inspections,
        t105_provider_calls=t105_provider_calls,
        t105_wire_attempts=t105_wire_attempts,
    )


__all__ = [
    "DEFAULT_REHEARSAL_RUN_ID",
    "PHYSICAL_CONNECTION_REHEARSAL_SCHEMA",
    "REHEARSAL_CONTRACT_SHA256",
    "REHEARSAL_STEP_EVIDENCE_SCHEMA",
    "PhysicalConnectionRehearsalError",
    "PhysicalConnectionRehearsalReport",
    "RehearsalFault",
    "RehearsalOutcome",
    "RehearsalStepOutcome",
    "RehearsalStepReceipt",
    "SimulationEffectSummary",
    "run_physical_connection_rehearsal",
]
