"""Structured fail-closed checks for each runtime capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from rocell.calibration.artifacts import CalibrationResolution
from rocell.rc03.build_snapshot import BuildSnapshot, Capability, assess_capability

from .faults import FaultCode
from .interlocks import HealthState, InterlockSnapshot


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    arm_connected: bool = False
    feedback_fresh: bool = False
    camera_live: bool = False
    camera_qualified: bool = False
    path_clear: bool = False
    device_verified: bool = False
    operator_armed: bool = False


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    check_id: str
    passed: bool
    fault_code: FaultCode | None
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or not self.check_id.strip():
            raise ValueError("check_id must be a non-empty string")
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be bool")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("preflight detail must be a non-empty string")
        if self.passed and self.fault_code is not None:
            raise ValueError("A passed preflight check cannot retain a fault code")
        if not self.passed and not isinstance(self.fault_code, FaultCode):
            raise ValueError("A failed preflight check must identify a fault code")


_PREFLIGHT_ISSUER = object()


@dataclass(frozen=True, slots=True)
class PreflightReport:
    _issuer: object = field(repr=False, compare=False)
    capability: Capability
    snapshot_hash: str
    plan_hash: str
    checks: tuple[PreflightCheck, ...]

    def __post_init__(self) -> None:
        if self._issuer is not _PREFLIGHT_ISSUER:
            raise ValueError("Preflight reports may only be issued by evaluate_preflight")
        if not isinstance(self.capability, Capability):
            raise TypeError("capability must be Capability")
        for name in ("snapshot_hash", "plan_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        checks = tuple(self.checks)
        if not checks:
            raise ValueError("A preflight report must contain at least one check")
        if any(not isinstance(check, PreflightCheck) for check in checks):
            raise TypeError("checks must contain PreflightCheck values")
        check_ids = tuple(check.check_id for check in checks)
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("Preflight check IDs must be unique")
        object.__setattr__(self, "checks", checks)

    @classmethod
    def _issue(
        cls,
        capability: Capability,
        snapshot_hash: str,
        plan_hash: str,
        checks: tuple[PreflightCheck, ...],
    ) -> "PreflightReport":
        """Create an evaluation result through the sole module-owned issuer."""

        return cls(_PREFLIGHT_ISSUER, capability, snapshot_hash, plan_hash, checks)

    @property
    def allowed(self) -> bool:
        # ``checks`` is structurally non-empty, but retain the explicit guard so
        # this property can never acquire vacuous-true semantics after refactors.
        return bool(self.checks) and all(check.passed for check in self.checks)

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(check.detail for check in self.checks if not check.passed)


def _check(check_id: str, passed: bool, fault: FaultCode, detail: str) -> PreflightCheck:
    return PreflightCheck(check_id, passed, None if passed else fault, detail)


def evaluate_preflight(
    capability: Capability,
    snapshot: BuildSnapshot,
    *,
    plan_hash: str,
    calibrations: CalibrationResolution | None = None,
    interlocks: InterlockSnapshot | None = None,
    runtime: RuntimeStatus | None = None,
    now_monotonic: float | None = None,
    interlock_max_age_s: float = 0.5,
) -> PreflightReport:
    capability_assessment = assess_capability(snapshot, capability)
    checks: list[PreflightCheck] = [
        _check(
            "build_capability",
            capability_assessment.allowed,
            FaultCode.CAPABILITY_DENIED,
            "PASS" if capability_assessment.allowed else ";".join(capability_assessment.reasons),
        )
    ]

    if capability in (Capability.DIGITAL_PLAN, Capability.SIMULATED_DRY_RUN):
        return PreflightReport._issue(
            capability, snapshot.snapshot_hash, plan_hash, tuple(checks)
        )

    runtime = runtime or RuntimeStatus()
    if capability is Capability.CAMERA_CAPTURE:
        checks.append(
            _check("camera_live", runtime.camera_live, FaultCode.CAMERA_UNAVAILABLE, "camera is not live")
        )
        checks.append(
            _check(
                "camera_qualified",
                runtime.camera_qualified,
                FaultCode.CAMERA_UNQUALIFIED,
                "camera identity/settings are not qualified",
            )
        )
        return PreflightReport._issue(
            capability, snapshot.snapshot_hash, plan_hash, tuple(checks)
        )

    interlocks = interlocks or InterlockSnapshot.unknown(captured_monotonic=0.0)
    fresh = interlocks.is_fresh(now=now_monotonic, max_age_s=interlock_max_age_s)
    checks.extend(
        (
            _check("interlock_fresh", fresh, FaultCode.INTERLOCK_STALE, "interlock snapshot is stale"),
            _check(
                "estop_chain",
                interlocks.estop_chain is HealthState.PASS,
                FaultCode.ESTOP_CHAIN_UNHEALTHY,
                "physical E-stop chain is not PASS",
            ),
            _check(
                "board_anti_shift",
                interlocks.board_anti_shift is HealthState.PASS,
                FaultCode.BOARD_ANTI_SHIFT_UNHEALTHY,
                "board anti-shift protection is not PASS",
            ),
            _check(
                "gravity_containment",
                interlocks.gravity_containment is HealthState.PASS,
                FaultCode.GRAVITY_CONTAINMENT_UNHEALTHY,
                "gravity-safe power-loss protection is not PASS",
            ),
            _check(
                "arm_connected",
                runtime.arm_connected,
                FaultCode.ARM_NOT_CONNECTED,
                "arm transport is not connected",
            ),
        )
    )

    if capability in (
        Capability.EMPTY_CELL_MOTION,
        Capability.KEYBOARD_CONTACT,
        Capability.PHONE_CONTACT,
    ):
        checks.extend(
            (
                _check(
                    "feedback_fresh",
                    runtime.feedback_fresh,
                    FaultCode.ARM_FEEDBACK_STALE,
                    "arm feedback is not fresh",
                ),
                _check(
                    "camera_live",
                    runtime.camera_live,
                    FaultCode.CAMERA_UNAVAILABLE,
                    "camera is not live",
                ),
                _check(
                    "camera_qualified",
                    runtime.camera_qualified,
                    FaultCode.CAMERA_UNQUALIFIED,
                    "camera is not qualified",
                ),
                _check(
                    "path_clear",
                    runtime.path_clear,
                    FaultCode.PATH_NOT_CLEARED,
                    "planned path is not cleared",
                ),
                _check(
                    "operator_armed",
                    runtime.operator_armed,
                    FaultCode.OPERATOR_NOT_ARMED,
                    "operator has not explicitly armed this run",
                ),
            )
        )

    if capability in (
        Capability.EMPTY_CELL_MOTION,
        Capability.KEYBOARD_CONTACT,
        Capability.PHONE_CONTACT,
    ):
        calibration_valid = calibrations is not None and calibrations.all_valid
        if calibration_valid:
            detail = "PASS"
        elif calibrations is None:
            detail = "required calibration resolution is missing"
        elif not calibrations.assessments:
            detail = "required calibration resolution contains no artifacts"
        else:
            detail = ";".join(calibrations.reasons) or (
                "required calibration resolution contains an invalid artifact"
            )
        checks.append(
            _check(
                "calibrations",
                calibration_valid,
                FaultCode.CALIBRATION_INVALID,
                detail,
            )
        )

    if capability in (Capability.KEYBOARD_CONTACT, Capability.PHONE_CONTACT):
        checks.append(
            _check(
                "contact_guard",
                interlocks.contact_guard is HealthState.PASS,
                FaultCode.CONTACT_GUARD_UNHEALTHY,
                "contact guard is not PASS",
            )
        )
        checks.append(
            _check(
                "device_verified",
                runtime.device_verified,
                FaultCode.DEVICE_NOT_VERIFIED,
                "device/profile state is not verified",
            )
        )
    return PreflightReport._issue(
        capability, snapshot.snapshot_hash, plan_hash, tuple(checks)
    )
