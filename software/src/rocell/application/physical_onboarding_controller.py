"""Safe controller for the non-device portion of physical onboarding.

The persistent journal in :mod:`rocell.application.physical_onboarding` is a
low-level evidence primitive.  This module deliberately exposes a much
narrower application API:

* sessions can only be created or opened below the session root selected by
  the controlled onboarding policy;
* the only stages this controller can complete are the two read-only source
  and camera-contract checks;
* every later stage can advance no further than ``WAITING_OPERATOR``; and
* recording evidence never changes a stage to ``PASS``.

No device backend is imported here.  In particular, this module does not
enumerate USB devices, import OpenCV or pyserial, open a camera or serial port,
apply robot power, or issue a robot command.  The explicit zero counters in
every status document make that authority ceiling machine-checkable.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Mapping

from rocell.application.physical_host_readiness import (
    PhysicalHostReadinessReport,
    assess_physical_host_readiness,
)
from rocell.application.physical_onboarding import (
    MAX_EVIDENCE_BYTES,
    STAGE_ORDER,
    EvidenceReference,
    PhysicalOnboardingSession,
    PhysicalOnboardingSnapshot,
    PhysicalOnboardingStage,
    StageState,
)
from rocell.application.physical_onboarding_policy import (
    PhysicalOnboardingPolicy,
    PhysicalOnboardingSourceBinding,
    bind_physical_onboarding_sources,
)
from rocell.application.physical_onboarding_foundation import (
    PhysicalOnboardingFoundationError,
    load_physical_onboarding_foundation,
)
from rocell.rc03 import BuildSnapshot


PHYSICAL_ONBOARDING_CONTROLLER_SCHEMA = "rocell.physical_onboarding_controller.v1"
PHYSICAL_ONBOARDING_CHALLENGE_SCHEMA = (
    "rocell.physical_onboarding_precondition_challenge.v1"
)
PHYSICAL_ONBOARDING_PREVIEW_SCHEMA = "rocell.physical_onboarding_action_preview.v1"
PHYSICAL_ONBOARDING_EXECUTION_SCHEMA = (
    "rocell.physical_onboarding_controller_execution.v1"
)

_ZERO_DIGEST = "0" * 64
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PORTABLE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)
_AUTO_STAGES = frozenset(
    {
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT,
    }
)
_CAMERA_ARCHITECTURE_RELATIVE = Path(
    "software/config/camera_architecture_plan.json"
)
_CAMERA_PROFILE_RELATIVE = Path(
    "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
)
_STATIC_CAMERA_SUPPORT_RELATIVE = Path(
    "hardware/static_overhead_camera/config/support_design.json"
)
_STATIC_CAMERA_LOCKED_SOURCES = (
    (
        "workcell_layout",
        "active-project/RoCell_v0_3/config/workcell_layout.json",
    ),
    (
        "robot_reach_screening",
        "active-project/RoCell_v0_3/config/robot_reach_screening.json",
    ),
    ("camera_architecture_plan", _CAMERA_ARCHITECTURE_RELATIVE.as_posix()),
    ("purchased_camera_profile", _CAMERA_PROFILE_RELATIVE.as_posix()),
)


class PhysicalOnboardingControllerError(ValueError):
    """A controller request is malformed, stale, or exceeds its authority."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingControllerError(
            f"controller value is not canonical JSON: {exc}"
        ) from exc


def _canonical_sha256(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingControllerError(
            f"controller value is not hashable canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _portable_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _PORTABLE_IDENTIFIER.fullmatch(value) is None:
        raise PhysicalOnboardingControllerError(
            f"{label} must be 1..64 portable characters: letters, digits, '.', '_', '-'"
        )
    # Windows treats the portion before the first dot as the device name.
    if value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise PhysicalOnboardingControllerError(f"{label} is a reserved filename")
    if value.endswith((".", " ")):
        raise PhysicalOnboardingControllerError(
            f"{label} must not end in a dot or space"
        )
    return value


def _reject_symlink_chain(path: Path, label: str) -> None:
    cursor = Path(os.path.abspath(path))
    while True:
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise PhysicalOnboardingControllerError(f"{label} contains a symlink")
        if cursor.parent == cursor:
            return
        cursor = cursor.parent


def _workspace_root(workspace: Path) -> Path:
    _reject_symlink_chain(workspace, "workspace")
    try:
        root = Path(workspace).resolve(strict=True)
    except OSError as exc:
        raise PhysicalOnboardingControllerError("workspace is unavailable") from exc
    if not root.is_dir():
        raise PhysicalOnboardingControllerError("workspace must be a directory")
    return root


def _ensure_policy_session_root(
    workspace: Path, policy: PhysicalOnboardingPolicy
) -> Path:
    """Create only the policy-selected parent and verify it after creation."""

    root = _workspace_root(workspace)
    selected = policy.session_root(root)
    try:
        selected.relative_to(root)
    except ValueError as exc:  # defensive; policy.session_root already checks this
        raise PhysicalOnboardingControllerError(
            "physical onboarding session root escapes the workspace"
        ) from exc
    _reject_symlink_chain(selected, "physical onboarding session root")
    try:
        selected.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PhysicalOnboardingControllerError(
            "could not create the controlled physical onboarding session root"
        ) from exc
    _reject_symlink_chain(selected, "physical onboarding session root")
    try:
        resolved = selected.resolve(strict=True)
    except OSError as exc:
        raise PhysicalOnboardingControllerError(
            "physical onboarding session root is unavailable"
        ) from exc
    if not resolved.is_dir() or resolved != selected:
        raise PhysicalOnboardingControllerError(
            "physical onboarding session root is not the controlled directory"
        )
    return resolved


def _session_directory(root: Path, session_id: str) -> Path:
    identifier = _portable_identifier(session_id, "session_id")
    selected = root / f"onboarding-{identifier}"
    if selected.resolve(strict=False).parent != root:
        raise PhysicalOnboardingControllerError("session directory escapes its root")
    return selected


def _time_ns() -> int:
    """Single clock seam used by tests; production always calls time.time_ns."""

    return time.time_ns()


def _clock_after(previous_ns: int | None, label: str) -> int:
    current = _time_ns()
    if isinstance(current, bool) or not isinstance(current, int) or current <= 0:
        raise PhysicalOnboardingControllerError(f"{label} clock is invalid")
    if current > 2**63 - 1:
        raise PhysicalOnboardingControllerError(f"{label} clock exceeds the limit")
    if previous_ns is not None and current <= previous_ns:
        # Do not synthesize previous+1.  Such a value would hide a host clock
        # regression in permanent commissioning evidence.
        raise PhysicalOnboardingControllerError(
            f"{label} clock did not advance; possible clock rollback"
        )
    return current


def _last_persistent_timestamp(snapshot: PhysicalOnboardingSnapshot) -> int:
    if snapshot.events:
        return snapshot.events[-1].occurred_at_ns
    return snapshot.header.created_at_ns


@dataclass(frozen=True, slots=True)
class ZeroAuthorityEffectCounters:
    """Physical effects this controller is structurally unable to perform."""

    device_enumerations: int = 0
    device_opens: int = 0
    camera_frames_captured: int = 0
    serial_transactions: int = 0
    robot_power_operations: int = 0
    robot_commands: int = 0
    motion_commands: int = 0
    contact_commands: int = 0

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or value != 0
            for value in (
                self.device_enumerations,
                self.device_opens,
                self.camera_frames_captured,
                self.serial_transactions,
                self.robot_power_operations,
                self.robot_commands,
                self.motion_commands,
                self.contact_commands,
            )
        ):
            raise PhysicalOnboardingControllerError(
                "non-device onboarding effect counters must remain zero"
            )

    def to_dict(self) -> dict[str, int]:
        return {
            "device_enumerations": 0,
            "device_opens": 0,
            "camera_frames_captured": 0,
            "serial_transactions": 0,
            "robot_power_operations": 0,
            "robot_commands": 0,
            "motion_commands": 0,
            "contact_commands": 0,
        }


ZERO_AUTHORITY_EFFECT_COUNTERS = ZeroAuthorityEffectCounters()


def _stage_dict(snapshot: PhysicalOnboardingSnapshot) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage.value,
            "state": item.state.value,
            "last_event_sequence": item.last_event_sequence,
            "evidence_ids": list(item.evidence_ids),
        }
        for item in snapshot.stages
    ]


def _next_action_dict(snapshot: PhysicalOnboardingSnapshot) -> dict[str, object]:
    action = snapshot.next_action
    return {
        "code": action.code,
        "stage": None if action.stage is None else action.stage.value,
        "stage_state": (
            None if action.stage_state is None else action.stage_state.value
        ),
        "operator_required": action.operator_required,
        "diagnostic_only": True,
        "automatic_effect_replay_allowed": False,
        "motion_authorized": False,
        "contact_authorized": False,
        "physical_release_effect": "NONE",
    }


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingControllerStatus:
    """Fully serialized, integrity-verified view with live source-drift state."""

    workspace: Path
    policy: PhysicalOnboardingPolicy
    current_source_binding: PhysicalOnboardingSourceBinding
    snapshot: PhysicalOnboardingSnapshot
    source_binding_current: bool
    effects: ZeroAuthorityEffectCounters = ZERO_AUTHORITY_EFFECT_COUNTERS

    @property
    def journal_head_sha256(self) -> str:
        return (
            _ZERO_DIGEST
            if not self.snapshot.events
            else self.snapshot.events[-1].event_sha256
        )

    @property
    def journal_head_sequence(self) -> int | None:
        return None if not self.snapshot.events else self.snapshot.events[-1].sequence

    @property
    def evidence_inventory_sha256(self) -> str:
        return _canonical_sha256(
            [item.to_dict() for item in self.snapshot.evidence]
        )

    def to_dict(self) -> dict[str, object]:
        header = self.snapshot.header
        capability = self.snapshot.capability
        return {
            "schema": PHYSICAL_ONBOARDING_CONTROLLER_SCHEMA,
            "workspace": str(self.workspace),
            "policy": {
                "policy_id": self.policy.policy_id,
                "policy_relative_path": self.policy.policy_relative_path,
                "policy_file_sha256": self.policy.policy_file_sha256,
                "session_root_relative": self.policy.session_root_relative,
            },
            "session": {
                "directory_name": f"onboarding-{header.session_id}",
                "header": header.to_dict(),
                "source_binding": {
                    "session_sha256": header.source_binding_sha256,
                    "current_sha256": (
                        self.current_source_binding.source_binding_sha256
                    ),
                    "current": self.source_binding_current,
                    "current_document": self.current_source_binding.to_dict(),
                },
            },
            "journal": {
                "event_count": len(self.snapshot.events),
                "head_sequence": self.journal_head_sequence,
                "head_event_sha256": self.journal_head_sha256,
                "high_water_sha256": self.snapshot.high_water_sha256,
                "events": [event.to_dict() for event in self.snapshot.events],
            },
            "evidence": {
                "count": len(self.snapshot.evidence),
                "inventory_sha256": self.evidence_inventory_sha256,
                "items": [item.to_dict() for item in self.snapshot.evidence],
            },
            "stages": _stage_dict(self.snapshot),
            "next_action": _next_action_dict(self.snapshot),
            "diagnostic_complete": self.snapshot.diagnostic_complete,
            "capability": {
                "scope": capability.scope,
                "diagnostic_observation_allowed": (
                    capability.diagnostic_observation_allowed
                ),
                "automatic_effect_replay_allowed": False,
                "motion_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
            "physical_effect_counters": self.effects.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class OnboardingPreconditionChallenge:
    """Digest-bound expected stage, evidence inventory, and journal head."""

    session_id: str
    source_binding_sha256: str
    source_binding_current: bool
    journal_event_count: int
    journal_head_sequence: int | None
    journal_head_sha256: str
    high_water_sha256: str
    evidence_count: int
    evidence_inventory_sha256: str
    stage: PhysicalOnboardingStage | None
    stage_state: StageState | None
    action_code: str
    challenge_sha256: str

    def core_dict(self) -> dict[str, object]:
        return {
            "schema": PHYSICAL_ONBOARDING_CHALLENGE_SCHEMA,
            "session_id": self.session_id,
            "source_binding_sha256": self.source_binding_sha256,
            "source_binding_current": self.source_binding_current,
            "journal_event_count": self.journal_event_count,
            "journal_head_sequence": self.journal_head_sequence,
            "journal_head_sha256": self.journal_head_sha256,
            "high_water_sha256": self.high_water_sha256,
            "evidence_count": self.evidence_count,
            "evidence_inventory_sha256": self.evidence_inventory_sha256,
            "stage": None if self.stage is None else self.stage.value,
            "stage_state": (
                None if self.stage_state is None else self.stage_state.value
            ),
            "action_code": self.action_code,
            "authority": {
                "hardware_accessed": False,
                "robot_power_authorized": False,
                "motion_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "challenge_sha256": self.challenge_sha256}


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingActionPreview:
    """One controller action and the exact state digest required to execute it."""

    operation: str
    executable: bool
    stage: PhysicalOnboardingStage | None
    stage_state: StageState | None
    challenge: OnboardingPreconditionChallenge
    explanation: str
    effects: ZeroAuthorityEffectCounters = ZERO_AUTHORITY_EFFECT_COUNTERS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": PHYSICAL_ONBOARDING_PREVIEW_SCHEMA,
            "operation": self.operation,
            "executable": self.executable,
            "stage": None if self.stage is None else self.stage.value,
            "stage_state": (
                None if self.stage_state is None else self.stage_state.value
            ),
            "explanation": self.explanation,
            "challenge": self.challenge.to_dict(),
            "physical_effect_counters": self.effects.to_dict(),
            "authority": {
                "hardware_accessed": False,
                "robot_power_authorized": False,
                "motion_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingExecution:
    operation: str
    before_challenge_sha256: str
    evidence_id: str | None
    status: PhysicalOnboardingControllerStatus
    effects: ZeroAuthorityEffectCounters = ZERO_AUTHORITY_EFFECT_COUNTERS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": PHYSICAL_ONBOARDING_EXECUTION_SCHEMA,
            "operation": self.operation,
            "before_challenge_sha256": self.before_challenge_sha256,
            "evidence_id": self.evidence_id,
            "status": self.status.to_dict(),
            "physical_effect_counters": self.effects.to_dict(),
        }


def _make_challenge(
    status: PhysicalOnboardingControllerStatus,
) -> OnboardingPreconditionChallenge:
    action = status.snapshot.next_action
    provisional = OnboardingPreconditionChallenge(
        session_id=status.snapshot.header.session_id,
        source_binding_sha256=(
            status.current_source_binding.source_binding_sha256
        ),
        source_binding_current=status.source_binding_current,
        journal_event_count=len(status.snapshot.events),
        journal_head_sequence=status.journal_head_sequence,
        journal_head_sha256=status.journal_head_sha256,
        high_water_sha256=status.snapshot.high_water_sha256,
        evidence_count=len(status.snapshot.evidence),
        evidence_inventory_sha256=status.evidence_inventory_sha256,
        stage=action.stage,
        stage_state=action.stage_state,
        action_code=action.code,
        challenge_sha256=_ZERO_DIGEST,
    )
    return OnboardingPreconditionChallenge(
        session_id=provisional.session_id,
        source_binding_sha256=provisional.source_binding_sha256,
        source_binding_current=provisional.source_binding_current,
        journal_event_count=provisional.journal_event_count,
        journal_head_sequence=provisional.journal_head_sequence,
        journal_head_sha256=provisional.journal_head_sha256,
        high_water_sha256=provisional.high_water_sha256,
        evidence_count=provisional.evidence_count,
        evidence_inventory_sha256=provisional.evidence_inventory_sha256,
        stage=provisional.stage,
        stage_state=provisional.stage_state,
        action_code=provisional.action_code,
        challenge_sha256=_canonical_sha256(provisional.core_dict()),
    )


def _stage_evidence_document(
    *,
    workspace: Path,
    stage: PhysicalOnboardingStage,
    binding: PhysicalOnboardingSourceBinding,
    readiness: PhysicalHostReadinessReport,
) -> tuple[Mapping[str, object], bool, str, str]:
    """Build evidence and the deterministic verdict for a zero-I/O stage."""

    common: dict[str, object] = {
        "schema": "rocell.physical_onboarding_zero_io_evidence.v1",
        "stage": stage.value,
        "verification_mode": "CONTROLLED_FILE_AND_HOST_METADATA_ONLY",
        "source_binding": binding.to_dict(),
        "host_readiness": readiness.to_dict(),
        "physical_effect_counters": ZERO_AUTHORITY_EFFECT_COUNTERS.to_dict(),
        "authority": {
            "hardware_accessed": False,
            "robot_power_authorized": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
        },
    }
    if stage is PhysicalOnboardingStage.WORKSPACE_SOURCES:
        try:
            foundation = load_physical_onboarding_foundation(workspace)
        except PhysicalOnboardingFoundationError as exc:
            # The aggregate reads and validates bounded controlled files only.
            # A malformed/stale contract must leave the stage PENDING; recording
            # a normal-looking workspace receipt would hide the broken trust root.
            raise PhysicalOnboardingControllerError(
                "physical-onboarding foundation failed strict zero-I/O "
                f"validation: {exc}"
            ) from exc
        passed = readiness.base_software_ready and foundation.zero_physical_authority
        common["check"] = {
            "policy_and_all_controlled_sources_hashed": True,
            "foundation_id": foundation.foundation_id,
            "foundation_sha256": foundation.source_sha256,
            "foundation_contract_count": len(foundation.contracts),
            "foundation_contracts": [
                {
                    "id": contract.id,
                    "path": contract.path,
                    "sha256": contract.sha256,
                }
                for contract in foundation.contracts
            ],
            "foundation_runtime_activation": foundation.runtime_activation,
            "foundation_zero_physical_authority": (
                foundation.zero_physical_authority
            ),
            "foundation_open_implementation_gates": list(
                foundation.open_implementation_gates
            ),
            "runtime_fail_closed": readiness.runtime_fail_closed,
            "launcher_present": readiness.launcher_present,
            "bootstrap_script_present": readiness.bootstrap_script_present,
            "base_software_ready": readiness.base_software_ready,
        }
        return (
            common,
            passed,
            "CONTROLLED_WORKSPACE_VERIFIED",
            "CONTROLLED_WORKSPACE_BLOCKED",
        )
    if stage is PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT:
        check, passed = _static_camera_contract_check(
            workspace=workspace,
            binding=binding,
            readiness=readiness,
        )
        common["check"] = check
        return (
            common,
            passed,
            "STATIC_CAMERA_CONTRACT_VERIFIED",
            "STATIC_CAMERA_CONTRACT_BLOCKED",
        )
    raise PhysicalOnboardingControllerError(
        "only zero-I/O onboarding stages have controller-generated evidence"
    )


def _static_camera_contract_check(
    *,
    workspace: Path,
    binding: PhysicalOnboardingSourceBinding,
    readiness: PhysicalHostReadinessReport,
) -> tuple[Mapping[str, object], bool]:
    """Strictly load and cross-bind the selected static-camera planning inputs.

    These imports and loaders read bounded local files only.  They neither
    import an optional camera/serial package nor enumerate or open a device.
    Loading the support design last is intentional: that validator independently
    hashes the architecture, camera profile, layout, and reach-screening inputs.
    """

    from rocell.vision.camera_profile import CameraProfileError, load_camera_profile
    from rocell.workcell.camera_architecture import (
        CameraArchitecturePlanError,
        load_camera_architecture_plan,
    )
    from rocell.workcell.static_camera_support import (
        StaticCameraSupportError,
        load_static_camera_support_design,
    )

    root = _workspace_root(workspace)
    try:
        profile = load_camera_profile(root / _CAMERA_PROFILE_RELATIVE)
        architecture = load_camera_architecture_plan(
            root, _CAMERA_ARCHITECTURE_RELATIVE
        )
        support = load_static_camera_support_design(
            root, root / _STATIC_CAMERA_SUPPORT_RELATIVE
        )
    except (
        CameraProfileError,
        CameraArchitecturePlanError,
        StaticCameraSupportError,
    ) as exc:
        # execute_next computes this verdict before appending ACQUIRING, so an
        # invalid planning input leaves a replayable PENDING stage and no
        # misleading evidence artifact.
        raise PhysicalOnboardingControllerError(
            "static-camera planning sources failed strict zero-I/O validation: "
            f"{exc}"
        ) from exc

    binding_sha256 = {
        source.relative_path: source.sha256 for source in binding.sources
    }
    profile_source_path = (
        profile.source_path.relative_to(root).as_posix()
        if profile.source_path is not None
        else None
    )
    architecture_source_path = architecture.source_path.relative_to(root).as_posix()
    support_source_path = support.path.relative_to(root).as_posix()

    # Select the profile mode by comparing it with the strictly loaded support
    # design.  This prevents the onboarding evidence from manufacturing a mode
    # tuple independently of the two authoritative inputs.
    matching_modes = tuple(
        mode
        for mode in profile.published_modes
        if (
            mode.width_px,
            mode.height_px,
            mode.maximum_fps,
            mode.pixel_format,
        )
        == support.native_mode
    )
    matching_mode = matching_modes[0] if len(matching_modes) == 1 else None

    bound_support_locks = {
        source_id: (
            support.source_sha256.get(source_id)
            == binding_sha256.get(relative_path)
        )
        for source_id, relative_path in _STATIC_CAMERA_LOCKED_SOURCES
    }
    cross_checks = {
        "base_software_ready": readiness.base_software_ready,
        "readiness_and_architecture_select_static_primary": (
            readiness.static_camera_plan_selected
            and architecture.overhead_route_selected
        ),
        "architecture_has_zero_physical_authority": (
            architecture.zero_physical_authority
        ),
        "secondary_camera_unselected": not architecture.secondary_selected,
        "automatic_camera_fallback_disabled": (
            not architecture.automatic_fallback_allowed
        ),
        "camera_profile_has_zero_live_authority": (
            not profile.live_ready and not any(profile.authority.values())
        ),
        "profile_and_support_identity_match": (
            support.camera_model == f"{profile.manufacturer} {profile.model}"
            and support.sensor == profile.sensor
        ),
        "profile_and_support_native_mode_match": matching_mode is not None,
        "architecture_and_support_board_match": (
            architecture.board_size_mm == support.board_size_mm[:2]
        ),
        "architecture_and_support_required_view_match": (
            architecture.provisional_required_coverage_mm
            == support.required_view_mm
        ),
        "architecture_file_matches_source_binding": (
            binding_sha256.get(architecture_source_path)
            == architecture.source_sha256
        ),
        "camera_profile_file_matches_source_binding": (
            profile_source_path is not None
            and binding_sha256.get(profile_source_path)
            == profile.source_file_sha256
        ),
        "support_design_file_matches_source_binding": (
            binding_sha256.get(support_source_path) == support.content_sha256
        ),
        "support_locks_architecture_bytes": (
            support.source_sha256.get("camera_architecture_plan")
            == architecture.source_sha256
        ),
        "support_locks_camera_profile_bytes": (
            support.source_sha256.get("purchased_camera_profile")
            == profile.source_file_sha256
        ),
        "every_support_dependency_matches_source_binding": all(
            bound_support_locks.values()
        ),
        "physical_qualification_holds_retained": bool(
            architecture.open_blockers
            and profile.open_blockers
            and support.open_blockers
        ),
    }
    passed = all(cross_checks.values())
    physical_qualification_complete = not (
        architecture.open_blockers or profile.open_blockers or support.open_blockers
    )
    mode_document: dict[str, object] | None = None
    if matching_mode is not None:
        mode_document = {
            "host_bus": matching_mode.host_bus,
            "width_px": matching_mode.width_px,
            "height_px": matching_mode.height_px,
            "maximum_fps": matching_mode.maximum_fps,
            "pixel_format": matching_mode.pixel_format,
            "evidence_state": matching_mode.evidence_state,
        }

    return (
        {
            "verification_scope": "STRICT_STATIC_CAMERA_PLANNING_INPUTS_ONLY",
            "device_observation_used": False,
            "camera_profile": {
                "source_relative_path": profile_source_path,
                "source_file_sha256": profile.source_file_sha256,
                "canonical_sha256": profile.canonical_sha256,
                "profile_id": profile.profile_id,
                "record_state": profile.record_state,
                "manufacturer": profile.manufacturer,
                "model": profile.model,
                "sensor": profile.sensor,
                "lens_mount": profile.lens_mount,
                "focal_length_mm": profile.focal_length_mm,
                "physical_observation_state": profile.physical_observation_state,
                "usb_observation_state": profile.usb_observation_state,
                "commissioning_state": profile.commissioning_state,
                "live_ready": profile.live_ready,
                "open_blockers": list(profile.open_blockers),
            },
            "architecture": {
                "source_relative_path": architecture_source_path,
                "source_sha256": architecture.source_sha256,
                "plan_id": architecture.plan_id,
                "decision_date": architecture.decision_date,
                "decision_state": architecture.decision_state,
                "primary_architecture": architecture.primary_architecture,
                "primary_optical_frame": architecture.primary_optical_frame,
                "runtime_backend_preference": (
                    architecture.runtime_backend_preference
                ),
                "overhead_route_selected": architecture.overhead_route_selected,
                "overhead_required_for_autonomous_descent": (
                    architecture.overhead_required_for_autonomous_descent
                ),
                "secondary_architecture": architecture.secondary_architecture,
                "secondary_selected": architecture.secondary_selected,
                "automatic_fallback_allowed": (
                    architecture.automatic_fallback_allowed
                ),
                "board_size_mm": list(architecture.board_size_mm),
                "provisional_required_coverage_mm": list(
                    architecture.provisional_required_coverage_mm
                ),
                "zero_physical_authority": architecture.zero_physical_authority,
                "open_blockers": list(architecture.open_blockers),
            },
            "support_design": {
                "source_relative_path": support_source_path,
                "content_sha256": support.content_sha256,
                "design_id": support.design_id,
                "revision_date": support.revision_date.isoformat(),
                "state": support.state,
                "camera_model": support.camera_model,
                "sensor": support.sensor,
                "camera_axis_xy_mm": list(support.camera_axis_xy_mm),
                "nominal_entrance_pupil_z_mm": (
                    support.nominal_entrance_pupil_z_mm
                ),
                "qualification_adjustment_z_mm": list(
                    support.qualification_adjustment_z_mm
                ),
                "required_view_mm": list(support.required_view_mm),
                "native_mode": list(support.native_mode),
                "field_of_view_deg": list(support.field_of_view_deg),
                "screening_metrics": {
                    "minimum_height_view_margin_width_mm": (
                        support.metrics.minimum_height_view_margin_width_mm
                    ),
                    "minimum_height_view_margin_depth_mm": (
                        support.metrics.minimum_height_view_margin_depth_mm
                    ),
                    "minimum_post_radial_clearance_mm": (
                        support.metrics.minimum_post_radial_clearance_mm
                    ),
                    "minimum_overhead_vertical_clearance_mm": (
                        support.metrics.minimum_overhead_vertical_clearance_mm
                    ),
                },
                "source_sha256": dict(support.source_sha256),
                "open_blockers": list(support.open_blockers),
            },
            "selected_published_mode": mode_document,
            "support_source_binding_checks": bound_support_locks,
            "cross_checks": cross_checks,
            "failed_cross_checks": [
                name for name, succeeded in cross_checks.items() if not succeeded
            ],
            "static_camera_plan_selected": (
                readiness.static_camera_plan_selected
            ),
            "physical_freeze_promoted": readiness.static_camera_freeze_promoted,
            "physical_qualification_complete": physical_qualification_complete,
            "physical_release_ready": (
                readiness.static_camera_freeze_promoted
                and physical_qualification_complete
            ),
            "contract_verified_without_device_access": passed,
        },
        passed,
    )


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingController:
    """Policy-rooted facade over one append-only physical onboarding session."""

    workspace: Path
    build_snapshot: BuildSnapshot
    policy: PhysicalOnboardingPolicy
    _session: PhysicalOnboardingSession

    def __post_init__(self) -> None:
        if not isinstance(self.build_snapshot, BuildSnapshot):
            raise TypeError("build_snapshot must be BuildSnapshot")
        root = _workspace_root(self.workspace)
        if root != self.workspace:
            raise PhysicalOnboardingControllerError(
                "controller workspace must be its canonical absolute path"
            )
        current_policy, _ = bind_physical_onboarding_sources(
            root, self.build_snapshot
        )
        if current_policy != self.policy:
            raise PhysicalOnboardingControllerError(
                "controller policy is not the current controlled policy"
            )
        snapshot = self._session.snapshot()
        session_id = _portable_identifier(snapshot.header.session_id, "session_id")
        _portable_identifier(snapshot.header.cell_id, "cell_id")
        session_root = current_policy.session_root(root)
        _reject_symlink_chain(session_root, "physical onboarding session root")
        try:
            resolved_root = session_root.resolve(strict=True)
            actual_directory = self._session.directory.resolve(strict=True)
        except OSError as exc:
            raise PhysicalOnboardingControllerError(
                "controlled physical onboarding session is unavailable"
            ) from exc
        expected_directory = _session_directory(resolved_root, session_id)
        _reject_symlink_chain(actual_directory, "physical onboarding session")
        if actual_directory != expected_directory:
            raise PhysicalOnboardingControllerError(
                "controller session is outside the policy-selected session root"
            )

    @property
    def session_directory(self) -> Path:
        """Canonical location, without exposing the journal mutation primitive."""

        return self._session.directory

    @classmethod
    def create(
        cls,
        workspace: Path,
        build_snapshot: BuildSnapshot,
        *,
        session_id: str,
        cell_id: str,
    ) -> "PhysicalOnboardingController":
        root = _workspace_root(workspace)
        selected_session_id = _portable_identifier(session_id, "session_id")
        selected_cell_id = _portable_identifier(cell_id, "cell_id")
        policy, binding = bind_physical_onboarding_sources(root, build_snapshot)
        session_root = _ensure_policy_session_root(root, policy)
        created_at_ns = _clock_after(None, "session creation")
        session = PhysicalOnboardingSession.create(
            session_root,
            session_id=selected_session_id,
            cell_id=selected_cell_id,
            source_binding_sha256=binding.source_binding_sha256,
            created_at_ns=created_at_ns,
        )
        controller = cls(
            workspace=root,
            build_snapshot=build_snapshot,
            policy=policy,
            _session=session,
        )
        # A concurrent controlled-source edit cannot silently create a session
        # that appears current. The immutable session remains available for
        # audit, but creation reports the drift and performs no stage action.
        controller.verify()
        return controller

    @classmethod
    def open(
        cls,
        workspace: Path,
        build_snapshot: BuildSnapshot,
        *,
        session_id: str,
    ) -> "PhysicalOnboardingController":
        root = _workspace_root(workspace)
        selected_session_id = _portable_identifier(session_id, "session_id")
        policy, _ = bind_physical_onboarding_sources(root, build_snapshot)
        session_root = policy.session_root(root)
        _reject_symlink_chain(session_root, "physical onboarding session root")
        try:
            resolved_root = session_root.resolve(strict=True)
        except OSError as exc:
            raise PhysicalOnboardingControllerError(
                "physical onboarding session root is unavailable"
            ) from exc
        if not resolved_root.is_dir():
            raise PhysicalOnboardingControllerError(
                "physical onboarding session root must be a directory"
            )
        selected = _session_directory(resolved_root, selected_session_id)
        _reject_symlink_chain(selected, "physical onboarding session")
        session = PhysicalOnboardingSession.open(selected)
        if session.snapshot().header.session_id != selected_session_id:
            raise PhysicalOnboardingControllerError("session identity mismatch")
        return cls(
            workspace=root,
            build_snapshot=build_snapshot,
            policy=policy,
            _session=session,
        )

    def status(self) -> PhysicalOnboardingControllerStatus:
        """Verify journal/evidence integrity and compare current controlled sources."""

        snapshot = self._session.snapshot()
        policy, binding = bind_physical_onboarding_sources(
            self.workspace, self.build_snapshot
        )
        if (
            policy.policy_id != self.policy.policy_id
            or policy.session_root_relative != self.policy.session_root_relative
        ):
            raise PhysicalOnboardingControllerError(
                "current onboarding policy identity or session root has drifted"
            )
        return PhysicalOnboardingControllerStatus(
            workspace=self.workspace,
            policy=policy,
            current_source_binding=binding,
            snapshot=snapshot,
            source_binding_current=(
                snapshot.header.source_binding_sha256
                == binding.source_binding_sha256
            ),
        )

    def verify(self) -> PhysicalOnboardingControllerStatus:
        """Return a verified current status or fail closed on source drift."""

        status = self.status()
        if not status.source_binding_current:
            raise PhysicalOnboardingControllerError(
                "controlled source binding drifted after session creation"
            )
        return status

    def expected_challenge(self) -> OnboardingPreconditionChallenge:
        return _make_challenge(self.status())

    def preview_next(self) -> PhysicalOnboardingActionPreview:
        status = self.status()
        challenge = _make_challenge(status)
        action = status.snapshot.next_action
        if not status.source_binding_current:
            return PhysicalOnboardingActionPreview(
                operation="BLOCKED_SOURCE_BINDING_DRIFT",
                executable=False,
                stage=action.stage,
                stage_state=action.stage_state,
                challenge=challenge,
                explanation=(
                    "Controlled sources changed; verify the changes and create a new "
                    "session. No session action was executed."
                ),
            )
        if action.stage is None:
            return PhysicalOnboardingActionPreview(
                operation="NO_ACTION_DIAGNOSTIC_COMPLETE",
                executable=False,
                stage=None,
                stage_state=None,
                challenge=challenge,
                explanation="The diagnostic handoff is already complete.",
            )
        if action.stage_state is StageState.PENDING:
            if action.stage in _AUTO_STAGES:
                operation = "VERIFY_ZERO_IO_STAGE"
                explanation = (
                    "Read and hash controlled files and inspect dependency metadata; "
                    "no device will be enumerated or opened."
                )
            else:
                operation = "MARK_WAITING_OPERATOR"
                explanation = (
                    "Record that the physical stage requires an operator; no device "
                    "operation or PASS decision will occur."
                )
            return PhysicalOnboardingActionPreview(
                operation=operation,
                executable=True,
                stage=action.stage,
                stage_state=action.stage_state,
                challenge=challenge,
                explanation=explanation,
            )
        operation_by_state = {
            StageState.WAITING_OPERATOR: "AWAIT_OPERATOR_EVIDENCE_AND_REVIEW",
            StageState.ACQUIRING: "RECONCILE_IN_FLIGHT_ACTION",
            StageState.BLOCKED: "RESOLVE_RECORDED_BLOCK",
            StageState.INVALIDATED: "REVIEW_INVALIDATED_EVIDENCE",
            StageState.SIDE_EFFECT_UNCERTAIN: "MANUAL_SIDE_EFFECT_RECONCILIATION",
        }
        selected_state = action.stage_state
        if selected_state is None:  # defensive; core pairs stage and state
            raise PhysicalOnboardingControllerError(
                "next action has a stage without a stage state"
            )
        return PhysicalOnboardingActionPreview(
            operation=operation_by_state.get(selected_state, "NO_CONTROLLER_ACTION"),
            executable=False,
            stage=action.stage,
            stage_state=action.stage_state,
            challenge=challenge,
            explanation=(
                "This state requires a separate reviewed assessor; the non-device "
                "controller cannot complete or replay it."
            ),
        )

    def _require_fresh_challenge(self, expected_sha256: str) -> PhysicalOnboardingControllerStatus:
        if not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None:
            raise PhysicalOnboardingControllerError(
                "expected challenge must be a lowercase SHA-256 digest"
            )
        status = self.status()
        actual = _make_challenge(status).challenge_sha256
        if actual != expected_sha256:
            raise PhysicalOnboardingControllerError(
                "onboarding precondition challenge is stale or belongs to another state"
            )
        if not status.source_binding_current:
            raise PhysicalOnboardingControllerError(
                "controlled source binding drifted after session creation"
            )
        return status

    def execute_next(
        self, *, expected_challenge_sha256: str
    ) -> PhysicalOnboardingExecution:
        """Execute one bounded controller action under an exact state challenge."""

        before = self._require_fresh_challenge(expected_challenge_sha256)
        preview = self.preview_next()
        if preview.challenge.challenge_sha256 != expected_challenge_sha256:
            raise PhysicalOnboardingControllerError(
                "onboarding state changed while preparing the action"
            )
        if not preview.executable or preview.stage is None:
            raise PhysicalOnboardingControllerError(
                f"next controller action is not executable: {preview.operation}"
            )
        stage = preview.stage
        if stage not in _AUTO_STAGES:
            timestamp = _clock_after(
                _last_persistent_timestamp(before.snapshot),
                "operator-wait transition",
            )
            self._session.commit_stage_state(
                stage,
                StageState.WAITING_OPERATOR,
                occurred_at_ns=timestamp,
                detail_code="OPERATOR_EVIDENCE_REQUIRED",
            )
            return PhysicalOnboardingExecution(
                operation=preview.operation,
                before_challenge_sha256=expected_challenge_sha256,
                evidence_id=None,
                status=self.status(),
            )

        # Compute the complete read-only verdict before recording ACQUIRING.
        # A parse error therefore leaves the journal replayable PENDING rather
        # than stranding it in an in-flight state.
        readiness = assess_physical_host_readiness(
            self.workspace, self.build_snapshot
        )
        evidence_document, passed, pass_code, block_code = _stage_evidence_document(
            workspace=self.workspace,
            stage=stage,
            binding=before.current_source_binding,
            readiness=readiness,
        )
        payload = _canonical_bytes(evidence_document)
        # Recheck all files and the challenge immediately before the first
        # append. This detects ordinary drift between preview and execution.
        rechecked = self._require_fresh_challenge(expected_challenge_sha256)
        started_at = _clock_after(
            _last_persistent_timestamp(rechecked.snapshot),
            "zero-I/O stage start",
        )
        self._session.commit_stage_state(
            stage,
            StageState.ACQUIRING,
            occurred_at_ns=started_at,
            detail_code="ZERO_IO_VERIFICATION_STARTED",
        )
        captured_at = _clock_after(started_at, "zero-I/O evidence capture")
        evidence = self._session.store_evidence(
            stage,
            payload,
            label=f"{stage.value}-zero-io-verification",
            media_type="application/json",
            captured_at_ns=captured_at,
        )
        completed_at = _clock_after(captured_at, "zero-I/O stage completion")
        self._session.commit_stage_state(
            stage,
            StageState.PASS if passed else StageState.BLOCKED,
            occurred_at_ns=completed_at,
            detail_code=pass_code if passed else block_code,
            evidence=(evidence,),
        )
        return PhysicalOnboardingExecution(
            operation=preview.operation,
            before_challenge_sha256=expected_challenge_sha256,
            evidence_id=evidence.evidence_id,
            status=self.status(),
        )

    def record_evidence_file(
        self,
        *,
        stage: PhysicalOnboardingStage,
        source_path: Path,
        expected_payload_sha256: str,
        captured_at_ns: int,
        label: str,
        media_type: str,
        expected_challenge_sha256: str,
    ) -> EvidenceReference:
        """Copy one caller-hashed workspace file into immutable stage evidence.

        This method intentionally has no corresponding ``approve`` or ``pass``
        operation.  A later physical assessor must interpret the retained bytes.
        """

        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        if stage in _AUTO_STAGES:
            raise PhysicalOnboardingControllerError(
                "zero-I/O stage evidence is generated only by execute_next"
            )
        if (
            not isinstance(expected_payload_sha256, str)
            or _SHA256.fullmatch(expected_payload_sha256) is None
        ):
            raise PhysicalOnboardingControllerError(
                "expected_payload_sha256 must be lowercase SHA-256"
            )
        if (
            isinstance(captured_at_ns, bool)
            or not isinstance(captured_at_ns, int)
            or captured_at_ns <= 0
            or captured_at_ns > 2**63 - 1
        ):
            raise PhysicalOnboardingControllerError(
                "captured_at_ns must be a bounded positive integer"
            )
        status = self._require_fresh_challenge(expected_challenge_sha256)
        action = status.snapshot.next_action
        if action.stage is not stage or action.stage_state is not StageState.WAITING_OPERATOR:
            raise PhysicalOnboardingControllerError(
                "evidence may be recorded only for the active WAITING_OPERATOR stage"
            )
        now = _clock_after(
            _last_persistent_timestamp(status.snapshot),
            "evidence recording",
        )
        if captured_at_ns <= _last_persistent_timestamp(status.snapshot):
            raise PhysicalOnboardingControllerError(
                "evidence timestamp must follow the active-stage journal event"
            )
        if captured_at_ns > now:
            raise PhysicalOnboardingControllerError(
                "evidence timestamp must not be in the future"
            )
        payload = _read_workspace_evidence_file(
            self.workspace,
            Path(source_path),
            expected_payload_sha256=expected_payload_sha256,
        )
        # The file read can take time. Recheck that neither the journal nor the
        # controlled source binding changed before publishing immutable bytes.
        self._require_fresh_challenge(expected_challenge_sha256)
        return self._session.store_evidence(
            stage,
            payload,
            label=label,
            media_type=media_type,
            captured_at_ns=captured_at_ns,
        )

    def record_generated_evidence_document(
        self,
        *,
        stage: PhysicalOnboardingStage,
        document: Mapping[str, object],
        label: str,
        expected_challenge_sha256: str,
    ) -> EvidenceReference:
        """Retain an internal diagnostic report without passing a stage.

        Typed inventory/qualification adapters can use this narrow method to
        archive their own report. It cannot target the two automatically
        assessed source stages and cannot change the current stage state.
        """

        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        if stage in _AUTO_STAGES:
            raise PhysicalOnboardingControllerError(
                "zero-I/O stage evidence is generated only by execute_next"
            )
        if not isinstance(document, Mapping):
            raise PhysicalOnboardingControllerError(
                "generated evidence document must be a mapping"
            )
        status = self._require_fresh_challenge(expected_challenge_sha256)
        action = status.snapshot.next_action
        if action.stage is not stage or action.stage_state is not StageState.WAITING_OPERATOR:
            raise PhysicalOnboardingControllerError(
                "generated evidence may be recorded only for the active "
                "WAITING_OPERATOR stage"
            )
        payload = _canonical_bytes(document)
        captured_at_ns = _clock_after(
            _last_persistent_timestamp(status.snapshot),
            "generated evidence recording",
        )
        self._require_fresh_challenge(expected_challenge_sha256)
        return self._session.store_evidence(
            stage,
            payload,
            label=label,
            media_type="application/json",
            captured_at_ns=captured_at_ns,
        )


def _read_workspace_evidence_file(
    workspace: Path,
    source_path: Path,
    *,
    expected_payload_sha256: str,
) -> bytes:
    root = _workspace_root(workspace)
    selected = source_path if source_path.is_absolute() else root / source_path
    _reject_symlink_chain(selected, "evidence source")
    try:
        resolved = selected.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PhysicalOnboardingControllerError(
            "evidence source is unavailable or outside the workspace"
        ) from exc
    try:
        before = resolved.stat(follow_symlinks=False)
    except OSError as exc:
        raise PhysicalOnboardingControllerError(
            "could not inspect evidence source"
        ) from exc
    if not stat.S_ISREG(before.st_mode):
        raise PhysicalOnboardingControllerError(
            "evidence source must be a regular non-symlink file"
        )
    try:
        with resolved.open("rb") as stream:
            payload = stream.read(MAX_EVIDENCE_BYTES + 1)
    except OSError as exc:
        raise PhysicalOnboardingControllerError(
            "could not read evidence source"
        ) from exc
    if not payload:
        raise PhysicalOnboardingControllerError("evidence source must not be empty")
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise PhysicalOnboardingControllerError(
            "evidence source exceeds the per-item size limit"
        )
    try:
        after = resolved.stat(follow_symlinks=False)
    except OSError as exc:
        raise PhysicalOnboardingControllerError(
            "could not re-inspect evidence source"
        ) from exc
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_mode,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_mode,
    )
    if before_identity != after_identity:
        raise PhysicalOnboardingControllerError(
            "evidence source changed while it was being read"
        )
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_payload_sha256:
        raise PhysicalOnboardingControllerError(
            "evidence source SHA-256 differs from the caller-provided digest"
        )
    return payload


def create_physical_onboarding_controller(
    workspace: Path,
    build_snapshot: BuildSnapshot,
    *,
    session_id: str,
    cell_id: str,
) -> PhysicalOnboardingController:
    return PhysicalOnboardingController.create(
        workspace,
        build_snapshot,
        session_id=session_id,
        cell_id=cell_id,
    )


def open_physical_onboarding_controller(
    workspace: Path,
    build_snapshot: BuildSnapshot,
    *,
    session_id: str,
) -> PhysicalOnboardingController:
    return PhysicalOnboardingController.open(
        workspace,
        build_snapshot,
        session_id=session_id,
    )


__all__ = [
    "PHYSICAL_ONBOARDING_CHALLENGE_SCHEMA",
    "PHYSICAL_ONBOARDING_CONTROLLER_SCHEMA",
    "PHYSICAL_ONBOARDING_EXECUTION_SCHEMA",
    "PHYSICAL_ONBOARDING_PREVIEW_SCHEMA",
    "ZERO_AUTHORITY_EFFECT_COUNTERS",
    "OnboardingPreconditionChallenge",
    "PhysicalOnboardingActionPreview",
    "PhysicalOnboardingController",
    "PhysicalOnboardingControllerError",
    "PhysicalOnboardingControllerStatus",
    "PhysicalOnboardingExecution",
    "ZeroAuthorityEffectCounters",
    "create_physical_onboarding_controller",
    "open_physical_onboarding_controller",
]
