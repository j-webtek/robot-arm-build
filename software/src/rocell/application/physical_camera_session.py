"""Explicit pending camera-only M1 storage, without device admission or replay.

Construction/status are inert. Initialization exclusively creates one assigned
store; refresh reopens only that original path and audits its existing records.
The bounded diagnostic checks Stop/source/time around synchronous storage calls;
it cannot forcibly interrupt an OS filesystem call or qualify native hardware.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
import json
import math
import os
import re
import threading
from time import monotonic_ns
from typing import Any, Callable, Iterator

from .cell_commissioning_coordinator import RegisteredActionRequest
from .commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
    physical_camera_source_binding,
)
from .commissioning_m1_persistence import M1CommissioningPersistenceError
from .physical_camera_prerequisites import (
    MAX_EVIDENCE_BYTES as MAX_PREREQUISITE_BYTES,
    verify_physical_camera_prerequisites,
)
from .physical_onboarding import EvidenceReference, STAGE_ORDER
from .physical_onboarding_durability import canonical_sha256, read_bounded_regular_file
from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState
from .physical_camera_usb_baseline import USB_ROLE_BYTES, USB_LABEL, USB_EVENT
from .physical_camera_usb_trial_readback import (
    TRIAL_PLAN_BYTES,
    TRIAL_LABEL,
    TRIAL_EVENT,
)
from .physical_camera_usb_phase import (
    USB_PHASE_ROLE_BYTES,
    USB_PHASE_LABEL,
    USB_PHASE_EVENT,
)
from .physical_camera_usb_absence_constants import (
    SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
    USB_ABSENCE_ROLE_BYTES,
    USB_ABSENCE_LABEL,
    USB_ABSENCE_EVENT,
    USB_ABSENCE_PRESENCE_EVENT,
)
from .physical_camera_usb_reconnect_constants import (
    SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA,
    USB_RECONNECT_ROLE_BYTES,
    USB_RECONNECT_LABEL,
    USB_RECONNECT_EVENT,
)
from .physical_camera_usb_reboot_constants import (
    SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
    USB_REBOOT_ROLE_BYTES,
    USB_REBOOT_LABEL,
    USB_REBOOT_EVENT,
)
from .physical_camera_usb_complete_constants import (
    SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
    USB_COMPLETE_ROLE_BYTES,
    USB_COMPLETE_LABEL,
    USB_COMPLETE_EVENT,
)
from .physical_camera_mode_entry import (
    SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
    MAX_ENTRY_BYTES as MAX_MODE_ENTRY_BYTES,
    CAMERA_MODE_ENTRY_LABEL,
    CAMERA_MODE_ENTRY_EVENT,
)
from .camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
    MAX_PREPARATION_BYTES,
    MAX_PREPARATION_NODES,
    MAX_REVIEW_BYTES,
    PREPARATION_LABEL,
    REVIEW_LABEL,
    SOURCE_WORKFLOW_PROBE_SCHEMA,
)
from .camera_operating_submission import (
    CameraOperatingSubmission,
    LABEL as OPERATING_SUBMISSION_LABEL,
    MAX_BYTES as MAX_OPERATING_SUBMISSION_BYTES,
    SOURCE_WORKFLOW_OPERATING_SCHEMA,
)
from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.native_camera_capture_protocol import local_capture_path
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import decode_owned_json

VIEW_SCHEMA = "rocell.physical_camera_session_view.v1"
DIAGNOSTIC_TIMEOUT_NS = 120_000_000_000
MAX_VERIFICATION_BYTES = 96 * 1024
MAX_PREREQUISITE_RECORD_BYTES = 128 * 1024
MAX_READBACK_STAGE_REFERENCES = 32
MAX_READBACK_STAGE_BYTES = 4 * 1024 * 1024
PREREQUISITE_LABEL = "camera-prerequisites-requirements-only"
SOURCE_WORKFLOW_SCHEMA = "rocell.physical_camera_source_workflow_readback.v1"
SOURCE_WORKFLOW_EPOCH_SCHEMA = "rocell.physical_camera_source_workflow_readback.v2"
SOURCE_WORKFLOW_INTAKE_SCHEMA = "rocell.physical_camera_source_workflow_readback.v3"
SOURCE_WORKFLOW_QUALIFICATION_SCHEMA = (
    "rocell.physical_camera_source_workflow_readback.v4"
)
SOURCE_WORKFLOW_STATIC_SCHEMA = "rocell.physical_camera_source_workflow_readback.v5"
SOURCE_WORKFLOW_RECEIVED_SCHEMA = "rocell.physical_camera_source_workflow_readback.v6"
SOURCE_WORKFLOW_IDENTITY_SCHEMA = "rocell.physical_camera_source_workflow_readback.v7"
SOURCE_WORKFLOW_USB_SCHEMA = "rocell.physical_camera_source_workflow_readback.v8"
SOURCE_WORKFLOW_USB_TRIAL_SCHEMA = "rocell.physical_camera_source_workflow_readback.v9"
SOURCE_WORKFLOW_USB_PHASE_SCHEMA = "rocell.physical_camera_source_workflow_readback.v10"
MAX_CAMERA_IDENTITY_CYCLES = 4
IDENTITY_ROLE_BYTES = {
    "metadata": 896 * 1024,
    "helper": 240 * 1024,
    "receipt": 32 * 1024,
    "assessment": 16 * 1024,
    "review": 16 * 1024,
}
MAX_IDENTITY_STAGE_REFERENCES = 20
MAX_IDENTITY_STAGE_BYTES = MAX_CAMERA_IDENTITY_CYCLES * sum(
    IDENTITY_ROLE_BYTES.values()
)
MAX_STATIC_STAGE_REFERENCES = 3
STATIC_ROLE_BYTES = {
    "receipt": 256 * 1024,
    "assessment": 32 * 1024,
    "review": 32 * 1024,
}
MAX_STATIC_STAGE_BYTES = sum(STATIC_ROLE_BYTES.values())
MAX_RECEIVED_CAMERA_CYCLES = 4
RECEIVED_ROLE_BYTES = {
    "notebook": 64 * 1024,
    "submission": 128 * 1024,
    "assessment": 160 * 1024,
    "review": 32 * 1024,
}
MAX_RECEIVED_MEDIA_BYTES = 4 * 1024 * 1024
MAX_RECEIVED_STAGE_REFERENCES = MAX_RECEIVED_CAMERA_CYCLES * 20
MAX_RECEIVED_STAGE_BYTES = MAX_RECEIVED_CAMERA_CYCLES * (
    MAX_RECEIVED_MEDIA_BYTES + sum(RECEIVED_ROLE_BYTES.values())
)
CONFIGURATION_EPOCH_LABEL = "physical-configuration-epochs-v1"
MAX_INTAKE_COLLECTIONS = 8
_INTAKE_LABEL = re.compile(
    r"physical-intake-(original|submission|assessment|review)-v1:"
    r"(intake-[0-9a-f]{32})(?::(0[0-9]|1[0-5]))?"
)
_INTAKE_EVENT = re.compile(
    r"PHYSICAL_INTAKE_(STARTED|SUBMITTED|REVIEWED)_([0-9A-F]{32})"
)
_QUALIFICATION_LABEL = re.compile(
    r"workspace-source-(isolation-original|qualification-receipt|"
    r"qualification-assessment|qualification-review)-v1:(sourcequal-[0-9a-f]{32})"
)
_STATIC_CONTRACT_LABEL = re.compile(
    r"static-camera-contract-(receipt|assessment|review)-v1:(staticcontract-[0-9a-f]{32})"
)
_RECEIVED_CAMERA_LABEL = re.compile(
    r"received-camera-(notebook|original|submission|assessment|review)-v1:"
    r"(receivedcamera-[0-9a-f]{32})(?::(0[0-9]|1[0-5]))?"
)
_CAMERA_IDENTITY_LABEL = re.compile(
    r"camera-identity-(metadata|helper|receipt|assessment|review)-v1:"
    r"(cameraidentity-[0-9a-f]{32})"
)
_INTAKE_MEDIA = frozenset(
    {"image/png", "image/jpeg", "application/pdf", "text/plain", "application/json"}
)
MAX_SOURCE_WORKFLOW_BYTES = MAX_READBACK_STAGE_BYTES + 64 * 1024
MAX_STATIC_WORKFLOW_BYTES = MAX_SOURCE_WORKFLOW_BYTES + MAX_STATIC_STAGE_BYTES
MAX_RECEIVED_WORKFLOW_BYTES = (
    MAX_STATIC_WORKFLOW_BYTES
    + MAX_RECEIVED_CAMERA_CYCLES * sum(RECEIVED_ROLE_BYTES.values())
    + 64 * 1024
)
MAX_IDENTITY_WORKFLOW_BYTES = (
    MAX_RECEIVED_WORKFLOW_BYTES + MAX_IDENTITY_STAGE_BYTES + 64 * 1024
)
# v8 additionally retains six stage roles and one independently audited USB
# campaign: its 1 MiB reservation plus a bounded 128 KiB native execution.
MAX_USB_WORKFLOW_BYTES = (
    MAX_IDENTITY_WORKFLOW_BYTES + sum(USB_ROLE_BYTES.values()) + 1280 * 1024
)
MAX_USB_TRIAL_WORKFLOW_BYTES = MAX_USB_WORKFLOW_BYTES + 32 * 1024
MAX_USB_PHASE_WORKFLOW_BYTES = (
    MAX_USB_TRIAL_WORKFLOW_BYTES + sum(USB_PHASE_ROLE_BYTES.values()) + 1280 * 1024
)
MAX_USB_ABSENCE_WORKFLOW_BYTES = (
    MAX_USB_PHASE_WORKFLOW_BYTES + sum(USB_ABSENCE_ROLE_BYTES.values()) + 1280 * 1024
)
MAX_USB_RECONNECT_WORKFLOW_BYTES = (
    MAX_USB_ABSENCE_WORKFLOW_BYTES
    + sum(USB_RECONNECT_ROLE_BYTES.values())
    + 1280 * 1024
)
MAX_USB_REBOOT_WORKFLOW_BYTES = (
    MAX_USB_RECONNECT_WORKFLOW_BYTES + sum(USB_REBOOT_ROLE_BYTES.values()) + 1280 * 1024
)
# Three bounded documents plus wrappers and three events (six cited references).
# There is no additional campaign copy. Every old version keeps its original cap.
MAX_USB_COMPLETE_WORKFLOW_BYTES = (
    MAX_USB_REBOOT_WORKFLOW_BYTES + sum(USB_COMPLETE_ROLE_BYTES.values()) + 16 * 1024
)
# One 16 KiB entry, its original wrapper and one event. No campaign is copied.
MAX_CAMERA_MODE_WORKFLOW_BYTES = (
    MAX_USB_COMPLETE_WORKFLOW_BYTES + MAX_MODE_ENTRY_BYTES + 8 * 1024
)
MAX_CAMERA_PROBE_WORKFLOW_BYTES = (
    MAX_CAMERA_MODE_WORKFLOW_BYTES
    + MAX_PREPARATION_BYTES
    + MAX_REVIEW_BYTES
    + 16 * 1024
)
MAX_CAMERA_OPERATING_WORKFLOW_BYTES = (
    MAX_CAMERA_PROBE_WORKFLOW_BYTES + MAX_OPERATING_SUBMISSION_BYTES + 16 * 1024
)
_SOURCE_WORKFLOW_BYTE_LIMITS = {
    SOURCE_WORKFLOW_SCHEMA: MAX_SOURCE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_EPOCH_SCHEMA: MAX_SOURCE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_INTAKE_SCHEMA: MAX_SOURCE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_QUALIFICATION_SCHEMA: MAX_SOURCE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_STATIC_SCHEMA: MAX_STATIC_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_RECEIVED_SCHEMA: MAX_RECEIVED_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_IDENTITY_SCHEMA: MAX_IDENTITY_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_SCHEMA: MAX_USB_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_TRIAL_SCHEMA: MAX_USB_TRIAL_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_PHASE_SCHEMA: MAX_USB_PHASE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA: MAX_USB_ABSENCE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA: MAX_USB_RECONNECT_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_REBOOT_SCHEMA: MAX_USB_REBOOT_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA: MAX_USB_COMPLETE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA: MAX_CAMERA_MODE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_PROBE_SCHEMA: MAX_CAMERA_PROBE_WORKFLOW_BYTES,
    SOURCE_WORKFLOW_OPERATING_SCHEMA: MAX_CAMERA_OPERATING_WORKFLOW_BYTES,
}
MAX_SOURCE_WORKFLOW_CACHE_NODES = 65_536
MAX_SOURCE_WORKFLOW_CACHE_DEPTH = 16
# Four separately bounded metadata roles can each retain a 32,000-node
# enrollment, in addition to the unchanged v6 history. The actual maximal
# candidate-count fixture is 76,854 nodes. Only the verified v7 history copy
# receives this aggregate ceiling; original role/IPC/legacy limits stay fixed.
MAX_IDENTITY_WORKFLOW_CACHE_NODES = 262_144
SOURCE_WORKFLOW_LABELS = {
    PREREQUISITE_LABEL: "prerequisites",
    "workspace-source-receipt-v1": "receipt",
    "workspace-source-assessment-v1": "assessment",
    "workspace-source-review-v1": "review",
    CONFIGURATION_EPOCH_LABEL: "configuration_epochs",
}
_BINDING_KEYS = {
    "workspace",
    "directory",
    "launch_id",
    "source_sha256",
    "cell_id",
    "session_id",
}
_ERROR_CODES = frozenset(
    {
        "CAMERA_SESSION_USB_ABSENCE_INVALID",
        "CAMERA_SESSION_USB_RECONNECT_INVALID",
        "CAMERA_SESSION_USB_REBOOT_INVALID",
        "CAMERA_SESSION_USB_COMPLETE_INVALID",
        "CAMERA_MODE_ORIGINAL_INVALID",
        "CAMERA_SESSION_USB_ABSENCE_CAMPAIGN",
        "CAMERA_SESSION_USB_TRIAL_INVALID",
        "CAMERA_SESSION_USB_PHASE_INVALID",
        "EXACT_CAMERA_SESSION_PATHS_REQUIRED",
        "EXACT_CAMERA_LAUNCH_REQUIRED",
        "EXACT_CAMERA_CELL_REQUIRED",
        "EXACT_CAMERA_SESSION_REQUIRED",
        "EXACT_ASSIGNED_CAMERA_SESSION_DIRECTORY_REQUIRED",
        "EXACT_CAMERA_TRANSACTION_REQUIRED",
        "NEW_CAMERA_SESSION_MUST_BE_ENTIRELY_PENDING",
        "NEW_CAMERA_SESSION_STORAGE_HELD",
        "CAMERA_SESSION_BINDING_CHANGED",
        "CAMERA_SESSION_CANCELLATION_PROGRESS_REQUIRED",
        "CAMERA_SESSION_OPERATION_ACTIVE",
        "CAMERA_SESSION_INITIALIZE_ALREADY_ATTEMPTED",
        "CAMERA_SESSION_CLOCK_INVALID",
        "CAMERA_SESSION_CANCELLED",
        "CAMERA_SESSION_TIMED_OUT",
        "CAMERA_SESSION_SOURCE_CHANGED",
        "CAMERA_SESSION_WINDOWS_NTFS_REQUIRED",
        "CAMERA_SESSION_ORIGINAL_STORE_MISMATCH",
        "CAMERA_SESSION_CHANGED_AFTER_AUDIT",
        "CAMERA_SESSION_VERIFICATION_BYTE_LIMIT",
        "CAMERA_SESSION_STORAGE_FAILED",
        "CAMERA_SESSION_REFRESH_REQUIRED",
        "CAMERA_SESSION_CURRENT_OPEN_REQUIRED",
        "CAMERA_SESSION_STAGE_SCOPE_FAILED",
        "CAMERA_SESSION_EXPECTED_HEADER_REQUIRED",
        "CAMERA_SESSION_HEADER_CHANGED",
        "CAMERA_SESSION_READBACK_DEADLINE_INVALID",
        "CAMERA_SESSION_READBACK_LIMIT",
        "CAMERA_SESSION_PREREQUISITES_AMBIGUOUS",
        "CAMERA_SESSION_PREREQUISITES_MALFORMED",
        "CAMERA_SESSION_READBACK_FAILED",
        "CAMERA_SESSION_USB_ROLE",
        "CAMERA_SESSION_USB_CHAIN",
        "CAMERA_SESSION_USB_STATE",
        "CAMERA_SESSION_USB_CAMPAIGN",
        "CAMERA_SESSION_SOURCE_WORKFLOW_ROLE",
        "CAMERA_SESSION_SOURCE_WORKFLOW_CHAIN",
        "CAMERA_SESSION_SOURCE_WORKFLOW_STATE",
        "CAMERA_SESSION_CONFIGURATION_EPOCHS_INVALID",
        "CAMERA_SESSION_INTAKE_ROLE",
        "CAMERA_SESSION_INTAKE_CHAIN",
        "CAMERA_SESSION_INTAKE_STATE",
        "CAMERA_SESSION_SOURCE_QUALIFICATION_ROLE",
        "CAMERA_SESSION_SOURCE_QUALIFICATION_CHAIN",
        "CAMERA_SESSION_SOURCE_QUALIFICATION_STATE",
        "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID",
        "CAMERA_SESSION_STATIC_CONTRACT_ROLE",
        "CAMERA_SESSION_STATIC_CONTRACT_CHAIN",
        "CAMERA_SESSION_STATIC_CONTRACT_STATE",
        "CAMERA_SESSION_RECEIVED_CAMERA_ROLE",
        "CAMERA_SESSION_RECEIVED_CAMERA_CHAIN",
        "CAMERA_SESSION_RECEIVED_CAMERA_STATE",
        "CAMERA_SESSION_CAMERA_IDENTITY_ROLE",
        "CAMERA_SESSION_CAMERA_IDENTITY_CHAIN",
        "CAMERA_SESSION_CAMERA_IDENTITY_STATE",
    }
)


class PhysicalCameraSessionError(RuntimeError):
    """Fixed public code; original exceptions remain private chained diagnostics."""

    def __init__(self, code: str) -> None:
        # Even a progress callback raising this exact public class cannot turn
        # the UI error field into an arbitrary private message channel.
        self.code = (
            code
            if type(code) is str and code in _ERROR_CODES
            else "CAMERA_SESSION_STORAGE_FAILED"
        )
        super().__init__(self.code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PhysicalCameraSessionError(code)


def _decode_cached_source_workflow(payload: bytes) -> dict[str, Any]:
    """Detach our verified full-history cache, not an owned-worker IPC packet.

    The original reader has already verified every role, reference and journal
    subject. This private copy boundary permits the full bounded history while
    preserving strict JSON/structure limits; it grants no trust to new input and
    deliberately does not change the process protocol's 4096-node ceiling.
    """
    value = _decode_cached_json_document(
        payload, maximum=MAX_CAMERA_OPERATING_WORKFLOW_BYTES, identity_history=True
    )
    _require(
        value.get("schema")
        in {
            SOURCE_WORKFLOW_SCHEMA,
            SOURCE_WORKFLOW_EPOCH_SCHEMA,
            SOURCE_WORKFLOW_INTAKE_SCHEMA,
            SOURCE_WORKFLOW_QUALIFICATION_SCHEMA,
            SOURCE_WORKFLOW_STATIC_SCHEMA,
            SOURCE_WORKFLOW_RECEIVED_SCHEMA,
            SOURCE_WORKFLOW_IDENTITY_SCHEMA,
            SOURCE_WORKFLOW_USB_SCHEMA,
            SOURCE_WORKFLOW_USB_TRIAL_SCHEMA,
            SOURCE_WORKFLOW_USB_PHASE_SCHEMA,
            SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
            SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA,
            SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
            SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
            SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
            SOURCE_WORKFLOW_PROBE_SCHEMA,
            SOURCE_WORKFLOW_OPERATING_SCHEMA,
        },
        "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID",
    )
    _require(
        len(payload) <= _SOURCE_WORKFLOW_BYTE_LIMITS[value["schema"]],
        "CAMERA_SESSION_READBACK_LIMIT",
    )
    return value


def _decode_cached_json_document(
    payload: bytes, *, maximum: int, identity_history: bool = False
) -> dict[str, Any]:
    """Strict private original-document copy; never a relaxed process decoder."""
    _require(
        type(payload) is bytes and 0 < len(payload) <= maximum,
        "CAMERA_SESSION_READBACK_LIMIT",
    )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID")
            result[key] = value
        return result

    def bad_constant(_: str) -> Any:
        raise PhysicalCameraSessionError("CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID")

    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=pairs,
            parse_constant=bad_constant,
        )
        _require(type(value) is dict, "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID")
        maximum_nodes = (
            MAX_IDENTITY_WORKFLOW_CACHE_NODES
            if identity_history
            and value.get("schema")
            in {
                SOURCE_WORKFLOW_IDENTITY_SCHEMA,
                SOURCE_WORKFLOW_USB_SCHEMA,
                SOURCE_WORKFLOW_USB_TRIAL_SCHEMA,
                SOURCE_WORKFLOW_USB_PHASE_SCHEMA,
                SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
                SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA,
                SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
                SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
            }
            else MAX_SOURCE_WORKFLOW_CACHE_NODES
        )
        maximum_depth = MAX_SOURCE_WORKFLOW_CACHE_DEPTH
        if identity_history and value.get("schema") in (
            SOURCE_WORKFLOW_PROBE_SCHEMA,
            SOURCE_WORKFLOW_OPERATING_SCHEMA,
        ):
            # The new compound record has an enrollment's own bounded tree.
            # Older schemas and owned-worker IPC keep their existing limits.
            maximum_nodes = (
                MAX_IDENTITY_WORKFLOW_CACHE_NODES + MAX_PREPARATION_NODES + 4096
            )
            maximum_depth = 32
            if value.get("schema") == SOURCE_WORKFLOW_OPERATING_SCHEMA:
                # The one bounded submission adds at most 8192 metadata nodes;
                # neither historical versions nor worker IPC gain this allowance.
                maximum_nodes += 8192
        pending = [(value, 0)]
        nodes = 0
        while pending:
            item, depth = pending.pop()
            nodes += 1
            _require(
                nodes <= maximum_nodes and depth <= maximum_depth,
                "CAMERA_SESSION_READBACK_LIMIT",
            )
            if type(item) is dict:
                for key, child in item.items():
                    pending.extend(((key, depth + 1), (child, depth + 1)))
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
            elif type(item) is float:
                _require(
                    math.isfinite(item), "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID"
                )
            else:
                _require(
                    item is None or type(item) in {str, int, bool},
                    "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID",
                )
        _require(
            canonical(value) == payload, "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID"
        )
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise PhysicalCameraSessionError(
            "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID"
        ) from error


def _error_report(error: BaseException, default: str) -> dict[str, str]:
    # Never put an arbitrary exception message or dynamic class name in the UI.
    if type(error) is PhysicalCameraSessionError:
        return {"code": error.code, "type": "PhysicalCameraSessionError"}
    kind = next(
        (
            name
            for category, name in (
                (OSError, "OSError"),
                (ValueError, "ValueError"),
                (RuntimeError, "RuntimeError"),
                (KeyboardInterrupt, "KeyboardInterrupt"),
                (SystemExit, "SystemExit"),
            )
            if isinstance(error, category)
        ),
        "Exception",
    )
    return {"code": default, "type": kind}


def _denied_facts(
    request: RegisteredActionRequest, snapshot: V2SessionSnapshot
) -> PhysicalCameraAdmissionFacts:
    # A selected endpoint, storage qualification, or PENDING journal is not a
    # hazard review/eight-epoch vector. Never fabricate the missing documents.
    raise M1CommissioningPersistenceError("TRUSTED_CAMERA_ADMISSION_FACTS_REQUIRED")


def _verify_intake_collections(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    packages: dict[str, dict[str, Any]],
    *,
    prefix_event_count: int | None = None,
) -> list[dict[str, Any]]:
    """Authenticate append-only packages against the original committed events.

    A raw file or a saved review is not a committed submission/review. The
    original source trio remains BLOCKED even while a supplementary cycle is
    waiting for an operator. No missing suffix is constructed or replayed.
    """
    from .physical_intake_submission import (
        verify_physical_intake_assessment,
        verify_physical_intake_review,
        verify_physical_intake_submission,
    )

    _require(
        type(snapshot) is V2SessionSnapshot
        and not snapshot.uncommitted_events
        and all(
            role in roles
            for role in ("prerequisites", "receipt", "assessment", "review")
        ),
        "CAMERA_SESSION_INTAKE_CHAIN",
    )
    if prefix_event_count is not None:
        _require(
            type(prefix_event_count) is int
            and 4 <= prefix_event_count < len(snapshot.committed_events),
            "CAMERA_SESSION_INTAKE_STATE",
        )
    events = snapshot.committed_events[:prefix_event_count]
    _require(
        4 <= len(events) <= 3 + 3 * MAX_INTAKE_COLLECTIONS,
        "CAMERA_SESSION_INTAKE_STATE",
    )
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}

    def event_matches(
        event: Any,
        state: V2StageState,
        code: str,
        references: list[dict[str, Any]],
        *,
        ordered: bool = True,
    ) -> None:
        actual = [ref.to_dict() for ref in event.evidence]
        expected = sorted(references, key=lambda ref: ref["evidence_id"])
        _require(
            event.stage is STAGE_ORDER[0]
            and event.state is state
            and event.detail_code == code
            and len({ref["evidence_id"] for ref in actual}) == len(actual)
            and (
                actual
                if ordered
                else sorted(actual, key=lambda ref: ref["evidence_id"])
            )
            == expected
            and all(inventory.get(ref["evidence_id"]) == ref for ref in actual),
            "CAMERA_SESSION_INTAKE_STATE",
        )

    original_subjects = [
        roles[role]["reference"] for role in ("receipt", "assessment", "review")
    ]
    for event, state, code, refs in zip(
        events[:3],
        (
            V2StageState.WAITING_OPERATOR,
            V2StageState.REVIEW_PENDING,
            V2StageState.BLOCKED,
        ),
        (
            "CAMERA_PREREQUISITES_REQUESTED",
            "WORKSPACE_SOURCES_ASSESSMENT_SAVED",
            "WORKSPACE_SOURCES_REVIEWED_BLOCKED",
        ),
        ([], original_subjects[:2], original_subjects),
    ):
        event_matches(event, state, code, refs, ordered=False)

    # Group by explicit START, including an empty partially started collection.
    cycles: list[tuple[str, list[Any]]] = []
    for event in events[3:]:
        match = _INTAKE_EVENT.fullmatch(event.detail_code)
        _require(match is not None, "CAMERA_SESSION_INTAKE_STATE")
        assert match is not None
        phase, suffix = match.groups()
        collection_id = "intake-" + suffix.lower()
        if phase == "STARTED":
            _require(
                collection_id not in {item[0] for item in cycles}
                and (not cycles or len(cycles[-1][1]) == 3),
                "CAMERA_SESSION_INTAKE_STATE",
            )
            cycles.append((collection_id, []))
        _require(
            bool(cycles)
            and cycles[-1][0] == collection_id
            and len(cycles[-1][1]) < 3
            and phase == ("STARTED", "SUBMITTED", "REVIEWED")[len(cycles[-1][1])],
            "CAMERA_SESSION_INTAKE_STATE",
        )
        cycles[-1][1].append(event)
    _require(len(cycles) <= MAX_INTAKE_COLLECTIONS, "CAMERA_SESSION_INTAKE_STATE")
    _require(
        all(
            package["collection_id"] in {item[0] for item in cycles}
            for package in packages.values()
        ),
        "CAMERA_SESSION_INTAKE_ROLE",
    )
    prerequisites = verify_physical_camera_prerequisites(
        canonical(roles["prerequisites"]["document"]),
        expected_source_sha256=bound["source_sha256"],
        expected_session_id=bound["session_id"],
        expected_launch_session_id=bound["launch_id"],
        expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
    )
    result: list[dict[str, Any]] = []
    predecessor = None
    previous_subjects = original_subjects
    available_originals: dict[str, dict[str, Any]] = {}
    for sequence, (collection_id, cycle) in enumerate(cycles, start=1):
        suffix = collection_id.removeprefix("intake-").upper()
        event_matches(
            cycle[0],
            V2StageState.WAITING_OPERATOR,
            "PHYSICAL_INTAKE_STARTED_" + suffix,
            previous_subjects,
        )
        local = [
            package
            for package in packages.values()
            if package["collection_id"] == collection_id
        ]
        records: dict[str, dict[str, Any]] = {}
        originals: dict[str, dict[str, Any]] = {}
        for package in local:
            kind, record = package["kind"], package["record"]
            if kind == "original":
                originals[record["reference"]["evidence_id"]] = record
            else:
                _require(kind not in records, "CAMERA_SESSION_INTAKE_ROLE")
                records[kind] = record
        indices = sorted(record["index"] for record in originals.values())
        _require(indices == list(range(len(indices))), "CAMERA_SESSION_INTAKE_ROLE")
        present = tuple(
            role for role in ("submission", "assessment", "review") if role in records
        )
        _require(
            present == ("submission", "assessment", "review")[: len(present)],
            "CAMERA_SESSION_INTAKE_CHAIN",
        )
        available_originals.update(originals)
        selected = sorted(
            originals.values(), key=lambda record: record["reference"]["evidence_id"]
        )
        submission = assessment = None
        try:
            if "submission" in records:
                record = records["submission"]
                submission = verify_physical_intake_submission(
                    canonical(record["document"]),
                    prerequisites=prerequisites,
                    # The legacy intake codec owns only stage-1 originals.
                    # Its 32-reference domain stays unchanged after v5 adds
                    # separate stage-2 packages. All references above still
                    # join the complete real snapshot and journal inventory.
                    evidence_inventory=tuple(
                        ref for ref in snapshot.evidence if ref.stage is STAGE_ORDER[0]
                    ),
                    expected_source_sha256=bound["source_sha256"],
                    expected_session_id=bound["session_id"],
                    expected_cell_id=bound["cell_id"],
                    expected_origin_launch_id=bound["launch_id"],
                    expected_header_sha256=expected_header_sha256,
                    expected_submission_sha256=record["evidence_sha256"],
                    predecessor=predecessor,
                )
                document = submission.to_dict()
                _require(
                    document["collection_id"] == collection_id
                    and document["sequence"] == sequence,
                    "CAMERA_SESSION_INTAKE_CHAIN",
                )
                selected = []
                for attachment in document["attachments"]:
                    ref = attachment["reference"]
                    raw_record = available_originals.get(ref["evidence_id"])
                    _require(
                        raw_record is not None
                        and raw_record["reference"] == ref
                        and raw_record["media_type"] == attachment["media_type"],
                        "CAMERA_SESSION_INTAKE_CHAIN",
                    )
                    assert raw_record is not None
                    selected.append(raw_record)
                _require(
                    set(originals)
                    <= {record["reference"]["evidence_id"] for record in selected},
                    "CAMERA_SESSION_INTAKE_CHAIN",
                )
            if "assessment" in records:
                assert submission is not None
                assessment = verify_physical_intake_assessment(
                    canonical(records["assessment"]["document"]),
                    submission=submission,
                    expected_assessment_sha256=records["assessment"]["evidence_sha256"],
                )
            if "review" in records:
                assert submission is not None and assessment is not None
                verify_physical_intake_review(
                    canonical(records["review"]["document"]),
                    submission=submission,
                    assessment=assessment,
                    expected_review_sha256=records["review"]["evidence_sha256"],
                )
        except (ValueError, TypeError, KeyError) as error:
            raise PhysicalCameraSessionError("CAMERA_SESSION_INTAKE_CHAIN") from error
        collection_state = "INCOMPLETE"
        if len(cycle) >= 2:
            _require(assessment is not None, "CAMERA_SESSION_INTAKE_CHAIN")
            cited = [record["reference"] for record in selected] + [
                records[role]["reference"] for role in ("submission", "assessment")
            ]
            event_matches(
                cycle[1],
                V2StageState.REVIEW_PENDING,
                "PHYSICAL_INTAKE_SUBMITTED_" + suffix,
                cited,
            )
            collection_state = "REVIEW_PENDING"
            if "review" in records:
                collection_state = "REVIEW_RETAINED_NOT_COMMITTED"
            if len(cycle) == 3:
                _require("review" in records, "CAMERA_SESSION_INTAKE_CHAIN")
                event_matches(
                    cycle[2],
                    V2StageState.BLOCKED,
                    "PHYSICAL_INTAKE_REVIEWED_" + suffix,
                    cited + [records["review"]["reference"]],
                )
                collection_state = "REVIEWED_BLOCKED"
        else:
            _require("review" not in records, "CAMERA_SESSION_INTAKE_STATE")
        result.append(
            {
                "collection_id": collection_id,
                "state": collection_state,
                "attachments": selected,
                **{
                    role: records.get(role)
                    for role in ("submission", "assessment", "review")
                },
            }
        )
        if len(cycle) == 3:
            predecessor = submission
            previous_subjects = [
                records[role]["reference"]
                for role in ("submission", "assessment", "review")
            ]
    if prefix_event_count is None:
        _require(
            snapshot.stages[0].state is events[-1].state, "CAMERA_SESSION_INTAKE_STATE"
        )
    return result


def _verify_original_source_roles(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    intake_packages: dict[str, dict[str, Any]] | None = None,
    qualification_packages: dict[str, dict[str, Any]] | None = None,
    qualification_originals: dict[str, bytes] | None = None,
    static_packages: dict[str, dict[str, Any]] | None = None,
    received_packages: dict[str, dict[str, Any]] | None = None,
    received_originals: dict[str, bytes] | None = None,
    identity_packages: dict[str, dict[str, Any]] | None = None,
    usb_packages: dict[str, dict[str, Any]] | None = None,
    original_usb_campaigns: tuple[dict[str, Any], ...] = (),
    trial_packages: dict[str, dict[str, Any]] | None = None,
    phase_packages: dict[str, dict[str, Any]] | None = None,
    absence_packages: dict[str, dict[str, Any]] | None = None,
    original_presence_campaigns: tuple[dict[str, Any], ...] = (),
    reconnect_packages: dict[str, dict[str, Any]] | None = None,
    reboot_packages: dict[str, dict[str, Any]] | None = None,
    complete_packages: dict[str, dict[str, Any]] | None = None,
    mode_entry_packages: dict[str, dict[str, Any]] | None = None,
    probe_packages: dict[str, dict[str, Any]] | None = None,
    operating_packages: dict[str, dict[str, Any]] | None = None,
    operating_transaction: M1PhysicalCameraTransaction | None = None,
) -> dict[str, Any]:
    """Exact original subjects; v17 additionally reads native originals in scope."""
    from .physical_source_stage_evidence import (
        verify_workspace_source_assessment,
        verify_workspace_source_receipt,
        verify_workspace_source_review,
    )

    order = ("prerequisites", "receipt", "assessment", "review")
    present = tuple(role for role in order if role in roles)
    _require(present == order[: len(present)], "CAMERA_SESSION_SOURCE_WORKFLOW_CHAIN")
    mode_layout = None
    has_operating = bool(operating_packages) or any(
        event.detail_code.startswith("CAMERA_OPERATING_SUBMITTED_")
        for event in snapshot.committed_events
    )
    has_probe = bool(probe_packages) or any(
        event.detail_code.startswith("CAMERA_PROBE_")
        for event in snapshot.committed_events
    )
    if has_operating:
        from .camera_operating_submission_readback import (
            read_camera_operating_submission_layout,
        )

        mode_layout = read_camera_operating_submission_layout(
            snapshot, mode_entry_packages, probe_packages, operating_packages
        )
    elif has_probe:
        from .camera_probe_preparation_readback import (
            read_camera_probe_preparation_layout,
        )

        mode_layout = read_camera_probe_preparation_layout(
            snapshot, mode_entry_packages, probe_packages
        )
    elif mode_entry_packages or any(
        event.detail_code.startswith("CAMERA_MODE_ENTRY_")
        for event in snapshot.committed_events
    ):
        from .physical_camera_mode_entry_readback import read_camera_mode_entry_layout

        mode_layout = read_camera_mode_entry_layout(snapshot, mode_entry_packages)
    try:
        prerequisites = (
            None
            if "prerequisites" not in roles
            else verify_physical_camera_prerequisites(
                canonical(roles["prerequisites"]["document"]),
                expected_source_sha256=bound["source_sha256"],
                expected_session_id=bound["session_id"],
                expected_launch_session_id=bound["launch_id"],
                expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
            )
        )
        receipt = None
        assessment = None
        if "receipt" in roles:
            assert prerequisites is not None
            receipt = verify_workspace_source_receipt(
                canonical(roles["receipt"]["document"]),
                prerequisites=prerequisites,
                expected_source_sha256=bound["source_sha256"],
                expected_session_id=bound["session_id"],
                expected_origin_launch_id=bound["launch_id"],
                expected_header_sha256=expected_header_sha256,
                expected_receipt_sha256=roles["receipt"]["evidence_sha256"],
            )
        if "assessment" in roles:
            assert receipt is not None
            assessment = verify_workspace_source_assessment(
                canonical(roles["assessment"]["document"]),
                receipt=receipt,
                expected_assessment_sha256=roles["assessment"]["evidence_sha256"],
            )
        if "review" in roles:
            assert receipt is not None and assessment is not None
            verify_workspace_source_review(
                canonical(roles["review"]["document"]),
                receipt=receipt,
                assessment=assessment,
                expected_review_sha256=roles["review"]["evidence_sha256"],
            )
        if "configuration_epochs" in roles:
            # This is a separate original dependency record, not another
            # source assessment or a replacement for missing observations.
            # Its verifier authenticates the creation head/inventory against
            # this later audited snapshot without rebuilding an old snapshot.
            from .physical_configuration_epochs import (
                _verify_physical_configuration_epochs_after_usb_absence,
                _verify_physical_configuration_epochs_after_usb_reconnect,
                _verify_physical_configuration_epochs_after_usb_reboot,
                _verify_physical_configuration_epochs_after_usb_complete,
                _verify_physical_configuration_epochs_after_camera_mode_entry,
                _verify_physical_configuration_epochs_after_usb_phase,
                _verify_physical_configuration_epochs_after_usb_trial,
                _verify_physical_configuration_epochs_after_usb_identity,
                _verify_physical_configuration_epochs_after_camera_identity,
                _verify_physical_configuration_epochs_after_received_camera,
                _verify_physical_configuration_epochs_after_static,
                verify_physical_configuration_epochs,
            )

            _require(
                prerequisites is not None,
                "CAMERA_SESSION_CONFIGURATION_EPOCHS_INVALID",
            )
            assert prerequisites is not None
            record = roles["configuration_epochs"]
            verify_epochs = (
                _verify_physical_configuration_epochs_after_camera_identity
                if identity_packages
                or any(
                    event.detail_code.startswith("CAMERA_IDENTITY_METADATA_")
                    for event in getattr(snapshot, "committed_events", ())
                )
                else (
                    _verify_physical_configuration_epochs_after_received_camera
                    if received_packages
                    else (
                        _verify_physical_configuration_epochs_after_static
                        if static_packages
                        else verify_physical_configuration_epochs
                    )
                )
            )
            if usb_packages or any(
                USB_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = _verify_physical_configuration_epochs_after_usb_identity
            if trial_packages or any(
                TRIAL_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = _verify_physical_configuration_epochs_after_usb_trial
            if phase_packages or any(
                USB_PHASE_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = _verify_physical_configuration_epochs_after_usb_phase
            if absence_packages or any(
                USB_ABSENCE_EVENT.fullmatch(event.detail_code)
                or USB_ABSENCE_PRESENCE_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = _verify_physical_configuration_epochs_after_usb_absence
            if reconnect_packages or any(
                USB_RECONNECT_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = (
                    _verify_physical_configuration_epochs_after_usb_reconnect
                )
            if reboot_packages or any(
                USB_REBOOT_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = _verify_physical_configuration_epochs_after_usb_reboot
            if complete_packages or any(
                USB_COMPLETE_EVENT.fullmatch(event.detail_code)
                for event in getattr(snapshot, "committed_events", ())
            ):
                verify_epochs = _verify_physical_configuration_epochs_after_usb_complete
            if mode_layout is not None:
                epochs = _verify_physical_configuration_epochs_after_camera_mode_entry(
                    canonical(record["document"]),
                    camera_mode_entry=mode_layout,
                    prerequisites=prerequisites,
                    snapshot=snapshot,
                    expected_sha256=record["evidence_sha256"],
                )
            else:
                epochs = verify_epochs(
                    canonical(record["document"]),
                    prerequisites=prerequisites,
                    snapshot=snapshot,
                    expected_sha256=record["evidence_sha256"],
                )
            epoch_document = epochs.to_dict()
            _require(
                epoch_document["boundary"]
                == {"stage": "workspace_sources", "phase": "BEFORE_STAGE"}
                and epoch_document["coverage"]["retained"] == 0
                and epoch_document["original_snapshot"]["evidence_inventory"]
                == [roles["prerequisites"]["reference"]],
                "CAMERA_SESSION_CONFIGURATION_EPOCHS_INVALID",
            )
    except (ValueError, TypeError, KeyError) as error:
        raise PhysicalCameraSessionError(
            "CAMERA_SESSION_SOURCE_WORKFLOW_CHAIN"
        ) from error
    if mode_layout is not None:
        from .physical_camera_mode_entry_readback import (
            verify_camera_mode_entry_workflow,
        )

        from .camera_probe_preparation_readback import (
            verify_camera_probe_preparation_workflow,
        )
        from .camera_operating_submission_readback import (
            verify_camera_operating_submission_workflow,
        )

        verifier = (
            verify_camera_operating_submission_workflow
            if has_operating
            else (
                verify_camera_probe_preparation_workflow
                if has_probe
                else verify_camera_mode_entry_workflow
            )
        )
        extra = (
            (probe_packages or {}, operating_packages or {})
            if has_operating
            else ((probe_packages or {},) if has_probe else ())
        )
        original_owner = {"transaction": operating_transaction} if has_operating else {}
        if has_operating:
            _require(
                type(operating_transaction) is M1PhysicalCameraTransaction,
                "CAMERA_OPERATING_ORIGINAL_TRANSACTION_REQUIRED",
            )
        return verifier(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            phase_packages or {},
            absence_packages or {},
            reconnect_packages or {},
            reboot_packages or {},
            complete_packages or {},
            mode_entry_packages or {},
            *extra,
            original_campaigns=original_usb_campaigns,
            original_presence_campaigns=original_presence_campaigns,
            **original_owner,
        )
    if complete_packages or any(
        event.detail_code.startswith("CAMERA_USB_COMPLETE_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_complete_readback import verify_usb_complete_workflow

        return verify_usb_complete_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            phase_packages or {},
            absence_packages or {},
            reconnect_packages or {},
            reboot_packages or {},
            complete_packages or {},
            original_campaigns=original_usb_campaigns,
            original_presence_campaigns=original_presence_campaigns,
        )
    if reboot_packages or any(
        event.detail_code.startswith("CAMERA_USB_TRIAL_REBOOT_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_reboot_readback import (
            verify_usb_reboot_workflow,
        )

        return verify_usb_reboot_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            phase_packages or {},
            absence_packages or {},
            reconnect_packages or {},
            reboot_packages or {},
            original_campaigns=original_usb_campaigns,
            original_presence_campaigns=original_presence_campaigns,
        )
    if reconnect_packages or any(
        event.detail_code.startswith("CAMERA_USB_TRIAL_RECONNECT_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_reconnect_readback import (
            verify_usb_reconnect_workflow,
        )

        return verify_usb_reconnect_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            phase_packages or {},
            absence_packages or {},
            reconnect_packages or {},
            original_campaigns=original_usb_campaigns,
            original_presence_campaigns=original_presence_campaigns,
        )
    if absence_packages or any(
        event.detail_code.startswith("CAMERA_USB_TRIAL_ABSENCE_")
        or event.detail_code.startswith("CAMERA_USB_PRESENCE_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_absence_readback import verify_usb_absence_workflow

        return verify_usb_absence_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            phase_packages or {},
            absence_packages or {},
            original_campaigns=original_usb_campaigns,
            original_presence_campaigns=original_presence_campaigns,
        )
    if phase_packages or any(
        event.detail_code.startswith("CAMERA_USB_TRIAL_BASELINE_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_phase_readback import verify_usb_phase_workflow

        return verify_usb_phase_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            phase_packages or {},
            original_campaigns=original_usb_campaigns,
        )
    if trial_packages or any(
        event.detail_code.startswith("CAMERA_USB_QUALIFICATION_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_trial_readback import (
            verify_usb_qualification_trial_workflow,
        )

        return verify_usb_qualification_trial_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            trial_packages or {},
            original_campaigns=original_usb_campaigns,
        )
    if usb_packages or any(
        event.detail_code.startswith("CAMERA_USB_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_usb_readback import verify_usb_baseline_workflow

        return verify_usb_baseline_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
            usb_packages or {},
            original_campaigns=original_usb_campaigns,
        )
    _require(not original_usb_campaigns, "CAMERA_SESSION_USB_CAMPAIGN")
    if identity_packages or any(
        event.detail_code.startswith("CAMERA_IDENTITY_METADATA_")
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_camera_identity_readback import verify_camera_identity_workflow

        return verify_camera_identity_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
            identity_packages or {},
        )
    if received_packages or any(
        event.detail_code.startswith(
            ("CAMERA_RECEIPT_COLLECTION_", "CAMERA_IDENTITY_REQUESTED_")
        )
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_received_camera_readback import verify_received_camera_workflow

        return verify_received_camera_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
            received_packages or {},
            received_originals or {},
        )
    if static_packages or any(
        event.detail_code.startswith(
            (
                "STATIC_CAMERA_CONTRACT_COLLECTED_",
                "STATIC_CAMERA_CONTRACT_REVIEWED_",
                "CAMERA_RECEIPT_REQUESTED_",
            )
        )
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_static_contract_readback import verify_static_contract_workflow

        return verify_static_contract_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
            static_packages or {},
        )
    if qualification_packages or any(
        event.detail_code.startswith(
            ("WORKSPACE_SOURCE_QUALIFICATION_", "STATIC_CAMERA_CONTRACT_REQUESTED_")
        )
        for event in getattr(snapshot, "committed_events", ())
    ):
        from .physical_source_qualification_readback import (
            verify_qualification_workflow,
        )

        return verify_qualification_workflow(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages or {},
            qualification_packages or {},
            qualification_originals or {},
        )
    stages = [item.to_dict() for item in snapshot.stages]
    _require(
        [item.get("stage") for item in stages] == [stage.value for stage in STAGE_ORDER]
        and all(
            item.get("state") == "PENDING" and not item.get("evidence_ids")
            for item in stages[1:]
        ),
        "CAMERA_SESSION_SOURCE_WORKFLOW_STATE",
    )
    state = stages[0]["state"]
    has_intake = bool(intake_packages) or any(
        _INTAKE_EVENT.fullmatch(event.detail_code)
        for event in getattr(snapshot, "committed_events", ())
    )
    collections = (
        _verify_intake_collections(
            bound, snapshot, expected_header_sha256, roles, intake_packages or {}
        )
        if has_intake
        else None
    )
    _require(
        has_intake
        or (state == "PENDING" and not present)
        or (state == "WAITING_OPERATOR" and "review" not in roles)
        or (state == "REVIEW_PENDING" and "assessment" in roles)
        or (state == "BLOCKED" and "review" in roles),
        "CAMERA_SESSION_SOURCE_WORKFLOW_STATE",
    )
    committed = set(stages[0]["evidence_ids"])
    retained = {record["reference"]["evidence_id"] for record in roles.values()}
    if has_intake:
        retained.update((intake_packages or {}).keys())
    _require(committed <= retained, "CAMERA_SESSION_SOURCE_WORKFLOW_STATE")
    if state in {"REVIEW_PENDING", "BLOCKED"}:
        required = {
            roles[role]["reference"]["evidence_id"]
            for role in ("receipt", "assessment")
        }
        if state == "BLOCKED":
            required.add(roles["review"]["reference"]["evidence_id"])
        _require(required <= committed, "CAMERA_SESSION_SOURCE_WORKFLOW_STATE")
    result = {
        "schema": (
            SOURCE_WORKFLOW_EPOCH_SCHEMA
            if "configuration_epochs" in roles
            else SOURCE_WORKFLOW_SCHEMA
        ),
        "binding": bound,
        "session_header_sha256": expected_header_sha256,
        "session_head_sha256": snapshot.head.head_sha256,
        "evidence_inventory_sha256": canonical_sha256(
            [item.to_dict() for item in snapshot.evidence]
        ),
        "stage": STAGE_ORDER[0].value,
        "state": state,
        **{role: roles.get(role) for role in order},
        "physical_authority": False,
        "device_io_performed": False,
    }
    # The exact legacy v1 shape is retained when the new record is absent.
    # Neither restoring v1 nor observing a missing vector creates one.
    if "configuration_epochs" in roles:
        result["configuration_epochs"] = roles["configuration_epochs"]
    if collections is not None:
        result.update(
            schema=SOURCE_WORKFLOW_INTAKE_SCHEMA,
            original_source_state="BLOCKED",
            intake_collections=collections,
        )
    return result


def _read_original_evidence_under_lease(
    transaction: M1PhysicalCameraTransaction,
    *,
    bound: dict[str, Any],
    expected_header_sha256: str,
    strict_workflow: bool,
    check: Callable[..., None],
    retain_prerequisite: Callable[[bytes], None] | None = None,
    retain_workflow: Callable[[bytes], None] | None = None,
) -> tuple[V2SessionSnapshot, dict[str, Any] | None]:
    """Existing stage-only reader; camera ownership is not accepted here."""
    return _read_original_evidence_in_scope(
        transaction,
        bound=bound,
        expected_header_sha256=expected_header_sha256,
        strict_workflow=strict_workflow,
        check=check,
        retain_prerequisite=retain_prerequisite,
        retain_workflow=retain_workflow,
        camera_scope=False,
    )


def _read_original_evidence_in_scope(
    transaction: M1PhysicalCameraTransaction,
    *,
    bound: dict[str, Any],
    expected_header_sha256: str,
    strict_workflow: bool,
    check: Callable[..., None],
    retain_prerequisite: Callable[[bytes], None] | None = None,
    retain_workflow: Callable[[bytes], None] | None = None,
    camera_scope: bool,
) -> tuple[V2SessionSnapshot, dict[str, Any] | None]:
    """Authenticate a read-only batch before returning any current workflow.

    Source, Stop and deadline callbacks still run between individual packages.
    The persistence scope checks every package and brackets the complete semantic
    read with fresh inventories/record families; it never caches across calls.
    """
    _require(
        type(camera_scope) is bool and (not camera_scope or strict_workflow is True),
        "EXACT_CAMERA_TRANSACTION_REQUIRED",
    )
    required: tuple[LeaseSpec, ...] = (
        LeaseSpec(LeaseLevel.CELL, bound["cell_id"]),
        LeaseSpec(LeaseLevel.SESSION, bound["session_id"]),
    )
    if camera_scope:
        required += (LeaseSpec(LeaseLevel.CAMERA, bound["cell_id"]),)
    _require(
        type(transaction) is M1PhysicalCameraTransaction
        and transaction.held_leases == required,
        "EXACT_CAMERA_TRANSACTION_REQUIRED",
    )
    with transaction._original_evidence_readback(camera_scope=camera_scope) as readback:
        result = _read_original_evidence_from_batch(
            transaction,
            bound=bound,
            expected_header_sha256=expected_header_sha256,
            strict_workflow=strict_workflow,
            check=check,
            retain_prerequisite=retain_prerequisite,
            retain_workflow=retain_workflow,
            camera_scope=camera_scope,
            readback=readback,
        )
    # Closing storage audits take time: a Stop, source change or expired deadline
    # during those audits must still withhold the current workflow from callers.
    check(source=True)
    return result


def _read_original_evidence_from_batch(
    transaction: M1PhysicalCameraTransaction,
    *,
    bound: dict[str, Any],
    expected_header_sha256: str,
    strict_workflow: bool,
    check: Callable[..., None],
    retain_prerequisite: Callable[[bytes], None] | None,
    retain_workflow: Callable[[bytes], None] | None,
    camera_scope: bool,
    readback: tuple[V2SessionSnapshot, Callable[[EvidenceReference], bytes]],
) -> tuple[V2SessionSnapshot, dict[str, Any] | None]:
    """One original reader shared by Refresh and the fixed reboot collector.

    Runs on one exact caller-held lease set; never acquires a nested transaction.
    Retention sinks receive verified bytes only and cannot supply authentication.
    Every manifest, payload, event and sibling campaign is still read/audited.
    """
    result: dict[str, Any] | None = None
    roles: dict[str, dict[str, Any]] = {}
    intake_packages: dict[str, dict[str, Any]] = {}
    qualification_packages: dict[str, dict[str, Any]] = {}
    qualification_originals: dict[str, bytes] = {}
    static_packages: dict[str, dict[str, Any]] = {}
    received_packages: dict[str, dict[str, Any]] = {}
    received_originals: dict[str, bytes] = {}
    identity_packages: dict[str, dict[str, Any]] = {}
    usb_packages: dict[str, dict[str, Any]] = {}
    trial_packages: dict[str, dict[str, Any]] = {}
    phase_packages: dict[str, dict[str, Any]] = {}
    absence_packages: dict[str, dict[str, Any]] = {}
    reconnect_packages: dict[str, dict[str, Any]] = {}
    reboot_packages: dict[str, dict[str, Any]] = {}
    complete_packages: dict[str, dict[str, Any]] = {}
    mode_entry_packages: dict[str, dict[str, Any]] = {}
    probe_packages: dict[str, dict[str, Any]] = {}
    operating_packages: dict[str, dict[str, Any]] = {}
    _require(
        type(camera_scope) is bool and (not camera_scope or strict_workflow is True),
        "EXACT_CAMERA_TRANSACTION_REQUIRED",
    )
    required_leases: tuple[LeaseSpec, ...] = (
        LeaseSpec(LeaseLevel.CELL, bound["cell_id"]),
        LeaseSpec(LeaseLevel.SESSION, bound["session_id"]),
    )
    if camera_scope:
        required_leases += (LeaseSpec(LeaseLevel.CAMERA, bound["cell_id"]),)
    _require(
        type(transaction) is M1PhysicalCameraTransaction
        and transaction.held_leases == required_leases,
        "EXACT_CAMERA_TRANSACTION_REQUIRED",
    )
    snapshot, read_original = readback
    _require(
        snapshot.header.header_sha256 == expected_header_sha256,
        "CAMERA_SESSION_HEADER_CHANGED",
    )
    has_complete_events = any(
        event.detail_code.startswith("CAMERA_USB_COMPLETE_")
        for event in snapshot.committed_events
    )
    has_reboot_events = any(
        event.detail_code.startswith("CAMERA_USB_TRIAL_REBOOT_")
        for event in snapshot.committed_events
    )
    has_reconnect_events = any(
        event.detail_code.startswith("CAMERA_USB_TRIAL_RECONNECT_")
        for event in snapshot.committed_events
    )
    references = tuple(
        item
        for item in snapshot.evidence
        if strict_workflow or item.stage is STAGE_ORDER[0]
    )
    # Preserve the exact original source-stage budget. Versioned
    # stage-2 subjects have their own closed three-document budget;
    # no other-stage package is interpreted by this reader.
    source_references = tuple(
        item for item in references if item.stage is STAGE_ORDER[0]
    )
    static_references = tuple(
        item for item in references if item.stage is STAGE_ORDER[1]
    )
    received_references = tuple(
        item for item in references if item.stage is STAGE_ORDER[2]
    )
    identity_references = tuple(
        item for item in references if item.stage is STAGE_ORDER[3]
    )
    mode_references = tuple(item for item in references if item.stage is STAGE_ORDER[4])
    _require(
        len(mode_references) <= 4
        and sum(item.payload_bytes for item in mode_references)
        <= MAX_MODE_ENTRY_BYTES
        + MAX_PREPARATION_BYTES
        + MAX_REVIEW_BYTES
        + MAX_OPERATING_SUBMISSION_BYTES,
        "CAMERA_SESSION_READBACK_LIMIT",
    )
    _require(
        len(source_references) <= MAX_READBACK_STAGE_REFERENCES
        and sum(item.payload_bytes for item in source_references)
        <= MAX_READBACK_STAGE_BYTES,
        "CAMERA_SESSION_READBACK_LIMIT",
    )
    _require(
        len(static_references) <= MAX_STATIC_STAGE_REFERENCES
        and sum(item.payload_bytes for item in static_references)
        <= MAX_STATIC_STAGE_BYTES,
        "CAMERA_SESSION_READBACK_LIMIT",
    )
    _require(
        len(received_references) <= MAX_RECEIVED_STAGE_REFERENCES
        and sum(item.payload_bytes for item in received_references)
        <= MAX_RECEIVED_STAGE_BYTES,
        "CAMERA_SESSION_READBACK_LIMIT",
    )
    _require(
        len(references)
        == len(source_references)
        + len(static_references)
        + len(received_references)
        + len(identity_references)
        + len(mode_references),
        "CAMERA_SESSION_SOURCE_WORKFLOW_ROLE",
    )
    _require(
        len(identity_references)
        <= MAX_IDENTITY_STAGE_REFERENCES
        + 25
        + (len(USB_RECONNECT_ROLE_BYTES) if has_reconnect_events else 0)
        + (len(USB_REBOOT_ROLE_BYTES) if has_reboot_events else 0)
        + (len(USB_COMPLETE_ROLE_BYTES) if has_complete_events else 0)
        and sum(item.payload_bytes for item in identity_references)
        <= MAX_IDENTITY_STAGE_BYTES
        + sum(USB_ROLE_BYTES.values())
        + TRIAL_PLAN_BYTES
        + sum(USB_PHASE_ROLE_BYTES.values())
        + sum(USB_ABSENCE_ROLE_BYTES.values())
        + (sum(USB_RECONNECT_ROLE_BYTES.values()) if has_reconnect_events else 0)
        + (sum(USB_REBOOT_ROLE_BYTES.values()) if has_reboot_events else 0)
        + (sum(USB_COMPLETE_ROLE_BYTES.values()) if has_complete_events else 0),
        "CAMERA_SESSION_READBACK_LIMIT",
    )
    for reference in references:
        check()
        package = transaction._session.directory / "evidence" / reference.evidence_id
        with _directory_guard(package):
            raw_manifest = read_bounded_regular_file(
                package / "manifest.json",
                maximum_bytes=16 * 1024,
                label="original prerequisite manifest",
            )
            _require(
                digest(raw_manifest) == reference.manifest_sha256,
                "CAMERA_SESSION_PREREQUISITES_MALFORMED",
            )
            manifest = decode_owned_json(raw_manifest, maximum=16 * 1024)
            label = manifest.get("label")
            operating_label = (
                OPERATING_SUBMISSION_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            if operating_label is not None:
                _require(
                    reference.stage is STAGE_ORDER[4]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= MAX_OPERATING_SUBMISSION_BYTES
                    and not operating_packages,
                    "CAMERA_OPERATING_ORIGINAL_PACKAGE_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_OPERATING_ORIGINAL_PACKAGE_INVALID",
                )
                operating_subject = CameraOperatingSubmission(raw)
                _require(
                    operating_subject.to_dict()["submission_id"] == operating_label[1],
                    "CAMERA_OPERATING_ORIGINAL_PACKAGE_INVALID",
                )
                operating_packages[reference.evidence_id] = dict(
                    submission_id=operating_label[1],
                    record=dict(
                        document=operating_subject.to_dict(),
                        evidence_sha256=reference.payload_sha256,
                        reference=reference.to_dict(),
                        retention="M1_FULL_BYTES_READ_BACK",
                    ),
                )
                del raw
                check(source=True)
                continue
            # Each new stage-5 role has an independent cap and closed codec.
            # This does not grant a blanket allowance to additional evidence.
            probe_kind = None
            probe_label = None
            if type(label) is str and strict_workflow:
                for kind, pattern in (
                    ("preparation", PREPARATION_LABEL),
                    ("review", REVIEW_LABEL),
                ):
                    match = pattern.fullmatch(label)
                    if match is not None:
                        probe_kind, probe_label = kind, match
                        break
            if probe_kind is not None and probe_label is not None:
                maximum = (
                    MAX_PREPARATION_BYTES
                    if probe_kind == "preparation"
                    else MAX_REVIEW_BYTES
                )
                _require(
                    reference.stage is STAGE_ORDER[4]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum
                    and not any(
                        item["kind"] == probe_kind for item in probe_packages.values()
                    ),
                    "CAMERA_PROBE_PREPARATION_ORIGINAL_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_PROBE_PREPARATION_ORIGINAL_INVALID",
                )
                subject = (
                    CameraProbePreparation(raw)
                    if probe_kind == "preparation"
                    else CameraProbePreparationReview(raw)
                )
                probe_packages[reference.evidence_id] = dict(
                    kind=probe_kind,
                    preparation_id=probe_label[1],
                    record=dict(
                        document=subject.to_dict(),
                        evidence_sha256=reference.payload_sha256,
                        reference=reference.to_dict(),
                        retention="M1_FULL_BYTES_READ_BACK",
                    ),
                )
                del raw
                check(source=True)
                continue
            mode_label = (
                CAMERA_MODE_ENTRY_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            if mode_label is not None:
                _require(
                    reference.stage is STAGE_ORDER[4]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= MAX_MODE_ENTRY_BYTES,
                    "CAMERA_MODE_ORIGINAL_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_MODE_ORIGINAL_INVALID",
                )
                mode_entry_packages[reference.evidence_id] = dict(
                    entry_id=mode_label[1],
                    record=dict(
                        document=_decode_cached_json_document(
                            raw, maximum=MAX_MODE_ENTRY_BYTES
                        ),
                        evidence_sha256=reference.payload_sha256,
                        reference=reference.to_dict(),
                        retention="M1_FULL_BYTES_READ_BACK",
                    ),
                )
                del raw
                check(source=True)
                continue
            role = SOURCE_WORKFLOW_LABELS.get(label) if type(label) is str else None
            intake_label = (
                _INTAKE_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            qualification_label = (
                _QUALIFICATION_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            static_label = (
                _STATIC_CONTRACT_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            received_label = (
                _RECEIVED_CAMERA_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            identity_label = (
                _CAMERA_IDENTITY_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            usb_label = (
                USB_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            trial_label = (
                TRIAL_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            phase_label = (
                USB_PHASE_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            absence_label = (
                USB_ABSENCE_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            complete_label = (
                USB_COMPLETE_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            if complete_label is not None:
                kind, series_id = complete_label.groups()
                maximum = USB_COMPLETE_ROLE_BYTES[kind]
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_USB_COMPLETE_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_COMPLETE_INVALID",
                )
                complete_packages[reference.evidence_id] = dict(
                    kind=kind,
                    series_id=series_id,
                    record=dict(
                        document=_decode_cached_json_document(raw, maximum=maximum),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            reboot_label = (
                USB_REBOOT_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            if reboot_label is not None:
                kind, phase_id = reboot_label.groups()
                kind = kind.replace("-", "_")
                maximum = USB_REBOOT_ROLE_BYTES[kind]
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_USB_REBOOT_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_REBOOT_INVALID",
                )
                reboot_packages[reference.evidence_id] = dict(
                    kind=kind,
                    phase_id=phase_id,
                    record=dict(
                        document=_decode_cached_json_document(raw, maximum=maximum),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            reconnect_label = (
                USB_RECONNECT_LABEL.fullmatch(label)
                if type(label) is str and strict_workflow
                else None
            )
            if reconnect_label is not None:
                kind, phase_id = reconnect_label.groups()
                kind = kind.replace("-", "_")
                maximum = USB_RECONNECT_ROLE_BYTES[kind]
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_USB_RECONNECT_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_RECONNECT_INVALID",
                )
                reconnect_packages[reference.evidence_id] = dict(
                    kind=kind,
                    phase_id=phase_id,
                    record=dict(
                        document=_decode_cached_json_document(raw, maximum=maximum),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            if absence_label is not None:
                kind, phase_id = absence_label.groups()
                kind = kind.replace("-", "_")
                maximum = USB_ABSENCE_ROLE_BYTES[kind]
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_USB_ABSENCE_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_ABSENCE_INVALID",
                )
                absence_packages[reference.evidence_id] = dict(
                    kind=kind,
                    phase_id=phase_id,
                    record=dict(
                        document=_decode_cached_json_document(raw, maximum=maximum),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            if phase_label is not None:
                kind, phase_id = phase_label.groups()
                kind = kind.replace("-", "_")
                maximum = USB_PHASE_ROLE_BYTES[kind]
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_USB_PHASE_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_PHASE_INVALID",
                )
                phase_packages[reference.evidence_id] = dict(
                    kind=kind,
                    phase_id=phase_id,
                    record=dict(
                        document=_decode_cached_json_document(raw, maximum=maximum),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            if trial_label is not None:
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= TRIAL_PLAN_BYTES,
                    "CAMERA_SESSION_USB_TRIAL_INVALID",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_TRIAL_INVALID",
                )
                trial_packages[reference.evidence_id] = dict(
                    trial_id=trial_label[1],
                    record=dict(
                        document=_decode_cached_json_document(
                            raw, maximum=TRIAL_PLAN_BYTES
                        ),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            if usb_label is not None:
                kind, usb_id = usb_label.groups()
                kind = kind.replace("-", "_")
                maximum = USB_ROLE_BYTES[kind]
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json"
                    and 0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_USB_ROLE",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_USB_CHAIN",
                )
                usb_packages[reference.evidence_id] = dict(
                    kind=kind,
                    usb_id=usb_id,
                    record=dict(
                        document=_decode_cached_json_document(raw, maximum=maximum),
                        evidence_sha256=reference.payload_sha256,
                        retention="M1_FULL_BYTES_READ_BACK",
                        reference=reference.to_dict(),
                    ),
                )
                del raw
                check(source=True)
                continue
            if identity_label is not None:
                kind, identity_id = identity_label.groups()
                _require(
                    reference.stage is STAGE_ORDER[3]
                    and manifest.get("media_type") == "application/json",
                    "CAMERA_SESSION_CAMERA_IDENTITY_ROLE",
                )
                maximum = IDENTITY_ROLE_BYTES[kind]
                _require(
                    0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_READBACK_LIMIT",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_CAMERA_IDENTITY_CHAIN",
                )
                identity_packages[reference.evidence_id] = {
                    "kind": kind,
                    "identity_id": identity_id,
                    "record": {
                        "document": _decode_cached_json_document(raw, maximum=maximum),
                        "evidence_sha256": reference.payload_sha256,
                        "retention": "M1_FULL_BYTES_READ_BACK",
                        "reference": reference.to_dict(),
                    },
                }
                del raw
                check(source=True)
                continue
            if received_label is not None:
                kind, receipt_id, index = received_label.groups()
                original = kind == "original"
                media_type = manifest.get("media_type")
                _require(
                    reference.stage is STAGE_ORDER[2]
                    and original == (index is not None)
                    and media_type in _INTAKE_MEDIA
                    and (original or media_type == "application/json"),
                    "CAMERA_SESSION_RECEIVED_CAMERA_ROLE",
                )
                maximum = 2 * 1024 * 1024 if original else RECEIVED_ROLE_BYTES[kind]
                _require(
                    0 < reference.payload_bytes <= maximum,
                    "CAMERA_SESSION_READBACK_LIMIT",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_RECEIVED_CAMERA_CHAIN",
                )
                received_record: dict[str, Any] = {
                    "evidence_sha256": reference.payload_sha256,
                    "retention": "M1_FULL_BYTES_READ_BACK",
                    "reference": reference.to_dict(),
                }
                if original:
                    received_originals[reference.evidence_id] = raw
                    received_record.update(
                        label=label, index=int(index), media_type=media_type
                    )
                else:
                    received_record["document"] = _decode_cached_json_document(
                        raw, maximum=maximum
                    )
                received_packages[reference.evidence_id] = {
                    "kind": kind,
                    "receipt_id": receipt_id,
                    "record": received_record,
                }
                del raw
                check(source=True)
                continue
            if static_label is not None:
                kind, contract_id = static_label.groups()
                _require(
                    reference.stage is STAGE_ORDER[1]
                    and manifest.get("media_type") == "application/json",
                    "CAMERA_SESSION_STATIC_CONTRACT_ROLE",
                )
                _require(
                    0 < reference.payload_bytes <= STATIC_ROLE_BYTES[kind],
                    "CAMERA_SESSION_READBACK_LIMIT",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_STATIC_CONTRACT_CHAIN",
                )
                static_packages[reference.evidence_id] = {
                    "kind": kind,
                    "contract_id": contract_id,
                    "record": {
                        "document": _decode_cached_json_document(
                            raw, maximum=STATIC_ROLE_BYTES[kind]
                        ),
                        "evidence_sha256": reference.payload_sha256,
                        "retention": "M1_FULL_BYTES_READ_BACK",
                        "reference": reference.to_dict(),
                    },
                }
                del raw
                check(source=True)
                continue
            _require(
                reference.stage is STAGE_ORDER[0],
                "CAMERA_SESSION_SOURCE_WORKFLOW_ROLE",
            )
            if qualification_label is not None:
                kind, qualification_id = qualification_label.groups()
                original = kind == "isolation-original"
                media_type = manifest.get("media_type")
                _require(
                    media_type in _INTAKE_MEDIA
                    and (original or media_type == "application/json"),
                    "CAMERA_SESSION_SOURCE_QUALIFICATION_ROLE",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_SOURCE_QUALIFICATION_CHAIN",
                )
                qualification_record: dict[str, Any] = {
                    "evidence_sha256": reference.payload_sha256,
                    "retention": "M1_FULL_BYTES_READ_BACK",
                    "reference": reference.to_dict(),
                }
                if original:
                    _require(
                        0 < len(raw) <= 2 * 1024 * 1024,
                        "CAMERA_SESSION_READBACK_LIMIT",
                    )
                    qualification_originals[reference.evidence_id] = raw
                    qualification_record.update(label=label, media_type=media_type)
                else:
                    qualification_record["document"] = _decode_cached_json_document(
                        raw, maximum=MAX_READBACK_STAGE_BYTES
                    )
                qualification_packages[reference.evidence_id] = {
                    "kind": (
                        "isolation_original"
                        if original
                        else kind.removeprefix("qualification-")
                    ),
                    "qualification_id": qualification_id,
                    "record": qualification_record,
                }
                del raw
                check(source=True)
                continue
            if intake_label is not None:
                kind, collection_id, index = intake_label.groups()
                _require(
                    (kind == "original") == (index is not None),
                    "CAMERA_SESSION_INTAKE_ROLE",
                )
                media_type = manifest.get("media_type")
                _require(
                    media_type in _INTAKE_MEDIA
                    and (kind == "original" or media_type == "application/json"),
                    "CAMERA_SESSION_INTAKE_ROLE",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_INTAKE_CHAIN",
                )
                # The original binary is read and checked under the
                # exact M1 scope but never copied into cached JSON.
                record: dict[str, Any] = {
                    "evidence_sha256": reference.payload_sha256,
                    "retention": "M1_FULL_BYTES_READ_BACK",
                    "reference": reference.to_dict(),
                }
                if kind == "original":
                    record.update(label=label, index=int(index), media_type=media_type)
                else:
                    record["document"] = decode_owned_json(
                        raw, maximum=MAX_READBACK_STAGE_BYTES
                    )
                intake_packages[reference.evidence_id] = {
                    "kind": kind,
                    "collection_id": collection_id,
                    "record": record,
                }
                del raw
                check(source=True)
                continue
            if strict_workflow:
                _require(
                    role is not None and role not in roles,
                    "CAMERA_SESSION_SOURCE_WORKFLOW_ROLE",
                )
                assert role is not None
            elif manifest.get("label") != PREREQUISITE_LABEL:
                continue
            if strict_workflow and role != "prerequisites":
                assert role is not None
                _require(
                    manifest.get("media_type") == "application/json",
                    "CAMERA_SESSION_SOURCE_WORKFLOW_ROLE",
                )
                raw = read_original(reference)
                _require(
                    digest(raw) == reference.payload_sha256
                    and len(raw) == reference.payload_bytes,
                    "CAMERA_SESSION_SOURCE_WORKFLOW_CHAIN",
                )
                roles[role] = {
                    "document": decode_owned_json(
                        raw, maximum=MAX_READBACK_STAGE_BYTES
                    ),
                    "evidence_sha256": reference.payload_sha256,
                    "retention": "M1_FULL_BYTES_READ_BACK",
                    "reference": reference.to_dict(),
                }
                check(source=True)
                continue
            _require(result is None, "CAMERA_SESSION_PREREQUISITES_AMBIGUOUS")
            _require(
                manifest.get("media_type") == "application/json"
                and reference.payload_bytes <= MAX_PREREQUISITE_BYTES,
                "CAMERA_SESSION_PREREQUISITES_MALFORMED",
            )
            raw = read_original(reference)
            artifact = verify_physical_camera_prerequisites(
                raw,
                expected_source_sha256=bound["source_sha256"],
                expected_session_id=bound["session_id"],
                expected_launch_session_id=bound["launch_id"],
                expected_evidence_sha256=reference.payload_sha256,
            )
            result = {
                "document": artifact.to_dict(),
                "evidence_sha256": artifact.evidence_sha256,
                "retention": "M1_FULL_BYTES_READ_BACK",
                "reference": reference.to_dict(),
            }
            if strict_workflow:
                roles["prerequisites"] = result
            retained_bytes = canonical(result)
            _require(
                len(retained_bytes) <= MAX_PREREQUISITE_RECORD_BYTES,
                "CAMERA_SESSION_READBACK_LIMIT",
            )
            # Preserve complete verified bytes before a later Stop,
            # source/coherence check, callback or guard exit fails.
            if retain_prerequisite is not None:
                retain_prerequisite(retained_bytes)
        check(source=True)
    if strict_workflow:
        _require(
            len(identity_packages) <= MAX_IDENTITY_STAGE_REFERENCES
            and sum(
                item["record"]["reference"]["payload_bytes"]
                for item in identity_packages.values()
            )
            <= MAX_IDENTITY_STAGE_BYTES
            and len(usb_packages) <= 6
            and sum(
                item["record"]["reference"]["payload_bytes"]
                for item in usb_packages.values()
            )
            <= sum(USB_ROLE_BYTES.values())
            and len(trial_packages) <= 1
            and len(phase_packages) <= 9
            and len(absence_packages) <= 9
            and len(reconnect_packages) <= len(USB_RECONNECT_ROLE_BYTES)
            and len(reboot_packages) <= len(USB_REBOOT_ROLE_BYTES)
            and len(complete_packages) <= len(USB_COMPLETE_ROLE_BYTES)
            and len(mode_entry_packages) <= 1
            and len(probe_packages) <= 2,
            "CAMERA_SESSION_READBACK_LIMIT",
        )
        from .physical_camera_usb_readback import (
            read_original_usb_campaigns,
        )

        has_absence = bool(absence_packages) or any(
            event.detail_code.startswith("CAMERA_USB_TRIAL_ABSENCE_")
            or event.detail_code.startswith("CAMERA_USB_PRESENCE_")
            for event in snapshot.committed_events
        )
        if has_absence or has_reconnect_events:
            from .physical_camera_usb_absence_readback import (
                read_original_usb_absence_campaigns,
            )

            family = read_original_usb_absence_campaigns(
                transaction,
                bound["session_id"],
                _usb_reconnect_extension=has_reconnect_events,
                _usb_reboot_extension=has_reboot_events,
            )
        original_usb_campaigns = (
            family["identity"]
            if has_absence
            else (
                read_original_usb_campaigns(
                    transaction, bound["session_id"], allow_trial_phase=True
                )
                if phase_packages
                or any(
                    USB_PHASE_EVENT.fullmatch(event.detail_code)
                    for event in snapshot.committed_events
                )
                else (
                    read_original_usb_campaigns(transaction, bound["session_id"])
                    if usb_packages
                    or any(
                        event.detail_code.startswith("CAMERA_USB_")
                        for event in snapshot.committed_events
                    )
                    else ()
                )
            )
        )
        result = _verify_original_source_roles(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages,
            qualification_packages,
            qualification_originals,
            static_packages,
            received_packages,
            received_originals,
            identity_packages,
            usb_packages,
            original_usb_campaigns,
            trial_packages,
            phase_packages,
            absence_packages,
            family["presence"] if has_absence else (),
            reconnect_packages,
            reboot_packages,
            complete_packages,
            mode_entry_packages,
            probe_packages,
            operating_packages,
            transaction,
        )
        retained_workflow = canonical(result)
        _require(
            len(retained_workflow) <= _SOURCE_WORKFLOW_BYTE_LIMITS[result["schema"]],
            "CAMERA_SESSION_READBACK_LIMIT",
        )
        _decode_cached_source_workflow(retained_workflow)
        if retain_workflow is not None:
            retain_workflow(retained_workflow)
    transaction._audit_records()
    check()
    return snapshot, result


def read_usb_reboot_boot_originals(
    tx: M1PhysicalCameraTransaction,
    *,
    workspace: Path,
    source_sha256: str,
    launch_session_id: str,
    expected_header_sha256: str,
    cancellation: threading.Event,
    deadline_ns: int,
) -> tuple[V2SessionSnapshot, dict[str, Any], dict[str, Any]]:
    """Authenticate the whole original on the collector's already-held lease.

    The original directory supplies its historical launch. The current launch
    must match the separate reboot report, never replace the old binding. No
    callback, cached projection, synthetic head or nested transaction is used.
    """
    from .physical_camera_usb_reboot import original_usb_reboot_predecessor_v13
    from .physical_received_camera_submission import (
        ReceivedCameraSubmission,
        ReceivedCameraSubmissionAssessment,
        ReceivedCameraSubmissionReview,
    )

    error = "CAMERA_SESSION_USB_REBOOT_INVALID"
    _require(type(tx) is M1PhysicalCameraTransaction, error)
    _require(
        isinstance(cancellation, threading.Event)
        and isinstance(workspace, Path)
        and type(launch_session_id) is str
        and re.fullmatch(r"wizard-[0-9a-f]{32}", launch_session_id) is not None,
        error,
    )
    started = monotonic_ns()
    _require(
        type(deadline_ns) is int and started < deadline_ns <= started + 180_000_000_000,
        error,
    )
    last_now = started

    def check(*, source: bool = False) -> None:
        nonlocal last_now
        tx._check_scope()
        _require(not cancellation.is_set(), "CAMERA_SESSION_CANCELLED")
        now = monotonic_ns()
        _require(type(now) is int and now >= last_now, "CAMERA_SESSION_CLOCK_INVALID")
        last_now = now
        _require(now < deadline_ns, "CAMERA_SESSION_TIMED_OUT")
        if source:
            _require(
                source_fingerprint(workspace) == source_sha256,
                "CAMERA_SESSION_SOURCE_CHANGED",
            )
            check()

    check(source=True)
    before = tx.snapshot()
    _require(
        before.header.header_sha256 == expected_header_sha256
        and before.header.source_binding_sha256
        == physical_camera_source_binding(source_sha256),
        error,
    )
    directory = tx._session.directory.parent
    # Construction validates the exact assigned path and identifiers; it is inert.
    bound = PhysicalCameraSession(
        workspace,
        directory,
        launch_id=directory.name,
        source_sha256=source_sha256,
        cell_id=before.header.cell_id,
        session_id=before.header.session_id,
    ).descriptor()
    snapshot, workflow = _read_original_evidence_under_lease(
        tx,
        bound=bound,
        expected_header_sha256=expected_header_sha256,
        strict_workflow=True,
        check=check,
    )
    _require(
        type(workflow) is dict
        and workflow.get("schema") == SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
        error,
    )
    assert isinstance(workflow, dict)
    phase = workflow["usb_qualification_reboot"]
    _require(
        phase["state"] == "REVIEWED"
        and phase["operator_event"]["document"]["launch_session_id"]
        == launch_session_id
        and phase["original_campaign"] is None
        and phase["original_campaign_event"] is None,
        error,
    )
    record = workflow["prerequisites"]
    prerequisites = verify_physical_camera_prerequisites(
        canonical(record["document"]),
        expected_source_sha256=source_sha256,
        expected_session_id=bound["session_id"],
        expected_launch_session_id=bound["launch_id"],
        expected_evidence_sha256=record["evidence_sha256"],
    )
    row = workflow["received_camera_cycles"][-1]
    received = {
        role: cls(canonical(row[role]["document"]), prerequisites)
        for role, cls in (
            ("submission", ReceivedCameraSubmission),
            ("assessment", ReceivedCameraSubmissionAssessment),
            ("review", ReceivedCameraSubmissionReview),
        )
    }
    predecessor = original_usb_reboot_predecessor_v13(workflow, received=received)
    check(source=True)
    _require(tx.snapshot() == snapshot == before, "CAMERA_SESSION_CHANGED_AFTER_AUDIT")
    check()
    return snapshot, workflow, predecessor


class PhysicalCameraSession:
    """One assigned original store; no caller-supplied facts, workers or paths.

    Initialization is one-use, including pre-creation cancellation. Explicit
    refresh may inspect the original partial store but never repairs, initializes
    a missing suffix, replays a campaign, clears quarantine or passes a stage.
    """

    def __init__(
        self,
        workspace: Path,
        directory: Path,
        *,
        launch_id: str,
        source_sha256: str,
        cell_id: str,
        session_id: str,
    ) -> None:
        _require(
            isinstance(workspace, Path) and isinstance(directory, Path),
            "EXACT_CAMERA_SESSION_PATHS_REQUIRED",
        )
        workspace, directory = local_capture_path(str(workspace)), local_capture_path(
            str(directory)
        )
        _require(
            type(launch_id) is str
            and bool(re.fullmatch(r"wizard-[0-9a-f]{32}", launch_id)),
            "EXACT_CAMERA_LAUNCH_REQUIRED",
        )
        _require(
            type(cell_id) is str
            and bool(re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", cell_id)),
            "EXACT_CAMERA_CELL_REQUIRED",
        )
        _require(
            type(session_id) is str
            and bool(re.fullmatch(r"physical-camera-[0-9a-f]{32}", session_id)),
            "EXACT_CAMERA_SESSION_REQUIRED",
        )
        physical_camera_source_binding(source_sha256)
        _require(
            str(directory)
            == str(workspace / "software/runs/physical-camera-acquisition" / launch_id),
            "EXACT_ASSIGNED_CAMERA_SESSION_DIRECTORY_REQUIRED",
        )
        self._binding = canonical(
            {
                "workspace": str(workspace),
                "directory": str(directory),
                "launch_id": launch_id,
                "source_sha256": source_sha256,
                "cell_id": cell_id,
                "session_id": session_id,
            }
        )
        self._state_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._initialize_closed = False
        self._store: M1PhysicalCameraPersistence | None = None
        self._retained: bytes | None = None
        self._retained_prerequisite_record: bytes | None = None
        self._retained_source_workflow: bytes | None = None
        self._cached: dict[str, Any] = {
            "schema": VIEW_SCHEMA,
            "binding": self.descriptor(),
            "status": "NOT_INITIALIZED",
            "operation": None,
            "verification": None,
            "stages": None,
            "error": None,
            "partial_store_possible": False,
            "initialize_attempted": False,
            "physical_authority": False,
            "device_io_performed": False,
            "hardware_qualified": False,
            "replay_allowed": False,
        }

    def descriptor(self) -> dict[str, Any]:
        data = decode_owned_json(self._binding, maximum=16 * 1024)
        _require(set(data) == _BINDING_KEYS, "CAMERA_SESSION_BINDING_CHANGED")
        return data

    def view(self) -> dict[str, Any]:
        with self._state_lock:
            return decode_owned_json(
                canonical(self._cached), maximum=MAX_VERIFICATION_BYTES + 16 * 1024
            )

    def retained_verification(self) -> dict[str, Any] | None:
        """Historical read-verified summary, never promoted after a late hold."""
        with self._state_lock:
            return (
                None
                if self._retained is None
                else decode_owned_json(self._retained, maximum=MAX_VERIFICATION_BYTES)
            )

    def initialize(
        self, *, cancellation: threading.Event, progress: Callable[[str], None]
    ) -> dict[str, Any]:
        return self._perform("INITIALIZE", cancellation=cancellation, progress=progress)

    def retained_prerequisites(self) -> dict[str, Any] | None:
        """Historical fully verified bytes, not a current-context admission."""
        with self._state_lock:
            return (
                None
                if self._retained_prerequisite_record is None
                else decode_owned_json(
                    self._retained_prerequisite_record,
                    maximum=MAX_PREREQUISITE_RECORD_BYTES,
                )
            )

    def read_original_prerequisites(
        self,
        *,
        expected_header_sha256: str,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int | None = None,
    ) -> dict[str, Any] | None:
        """Legacy prerequisite-only read; unrelated documents remain ignored.

        New source-workflow callers must use read_original_source_workflow for
        closed role/subject/state verification, then use its prerequisites field.
        Neither entry point opens nested or redundant stage transactions.
        """
        return self._read_original_evidence(
            expected_header_sha256=expected_header_sha256,
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            strict_workflow=False,
        )

    def retained_source_workflow(self) -> dict[str, Any] | None:
        """Detached historical verified chain; not current publication authority."""
        with self._state_lock:
            return (
                None
                if self._retained_source_workflow is None
                else _decode_cached_source_workflow(self._retained_source_workflow)
            )

    def read_original_source_workflow(
        self,
        *,
        expected_header_sha256: str,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int | None = None,
    ) -> dict[str, Any]:
        """Audit original source roles and optional initial configuration record.

        Absence preserves the historical v1 result exactly. A present record
        produces v2 with its full original bytes/reference, never a synthesized
        vector, new stage acceptance or admission facts.
        """
        result = self._read_original_evidence(
            expected_header_sha256=expected_header_sha256,
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            strict_workflow=True,
        )
        assert result is not None
        return result

    def _read_original_evidence(
        self,
        *,
        expected_header_sha256: str,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int | None,
        strict_workflow: bool,
    ) -> dict[str, Any] | None:
        """Shared bounded original readback after an explicit successful open.

        The registry's independently selected immutable header is mandatory.
        No stage mutation, collection, file creation or replay occurs. A caller
        deadline can shorten, but never renew, this operation's 120s budget.
        """
        _require(
            type(expected_header_sha256) is str
            and re.fullmatch(r"[0-9a-f]{64}", expected_header_sha256) is not None
            and expected_header_sha256 != "0" * 64,
            "CAMERA_SESSION_EXPECTED_HEADER_REQUIRED",
        )
        _require(
            isinstance(cancellation, threading.Event) and callable(progress),
            "CAMERA_SESSION_CANCELLATION_PROGRESS_REQUIRED",
        )
        _require(
            deadline_ns is None
            or (type(deadline_ns) is int and 0 < deadline_ns < 2**63),
            "CAMERA_SESSION_READBACK_DEADLINE_INVALID",
        )
        _require(
            self._operation_lock.acquire(blocking=False),
            "CAMERA_SESSION_OPERATION_ACTIVE",
        )
        try:
            started = monotonic_ns()
            _require(
                type(started) is int and 0 <= started < 2**63 - DIAGNOSTIC_TIMEOUT_NS,
                "CAMERA_SESSION_CLOCK_INVALID",
            )
            deadline = min(
                started + DIAGNOSTIC_TIMEOUT_NS,
                (
                    deadline_ns
                    if deadline_ns is not None
                    else started + DIAGNOSTIC_TIMEOUT_NS
                ),
            )
            last_now = started
            original_binding, bound = self._binding, self.descriptor()
            with self._state_lock:
                store = self._store
                _require(
                    type(store) is M1PhysicalCameraPersistence,
                    "CAMERA_SESSION_CURRENT_OPEN_REQUIRED",
                )
                self._store = None
                self._cached.update(
                    status="RUNNING",
                    operation="REFRESH",
                    verification=None,
                    stages=None,
                    error=None,
                )

            def check(*, source: bool = False) -> None:
                nonlocal last_now
                _require(
                    self._binding == original_binding, "CAMERA_SESSION_BINDING_CHANGED"
                )
                _require(not cancellation.is_set(), "CAMERA_SESSION_CANCELLED")
                now = monotonic_ns()
                _require(
                    type(now) is int and now >= last_now, "CAMERA_SESSION_CLOCK_INVALID"
                )
                last_now = now
                _require(now < deadline, "CAMERA_SESSION_TIMED_OUT")
                if source:
                    _require(
                        source_fingerprint(Path(bound["workspace"]))
                        == bound["source_sha256"],
                        "CAMERA_SESSION_SOURCE_CHANGED",
                    )
                    check()

            check(source=True)
            progress(
                "Reading original camera requirements under stage-only storage leases; no evidence is recollected."
            )
            check(source=True)
            assert store is not None
            before = store.verification(bound["session_id"])
            check()
            _require(
                before.session_header_sha256 == expected_header_sha256,
                "CAMERA_SESSION_HEADER_CHANGED",
            )

            def retain_prerequisite(payload):
                with self._state_lock:
                    self._retained_prerequisite_record = payload

            def retain_workflow(payload):
                with self._state_lock:
                    self._retained_source_workflow = payload

            with store.stage_transaction(
                bound["session_id"], expected_challenge_sha256=before.challenge_sha256
            ) as transaction:
                snapshot, result = _read_original_evidence_under_lease(
                    transaction,
                    bound=bound,
                    expected_header_sha256=expected_header_sha256,
                    strict_workflow=strict_workflow,
                    check=check,
                    retain_prerequisite=retain_prerequisite,
                    retain_workflow=retain_workflow,
                )
            check()
            verified = store.verification(bound["session_id"])
            _require(
                verified.session_header_sha256 == expected_header_sha256,
                "CAMERA_SESSION_HEADER_CHANGED",
            )
            _require(
                verified.session_head_sha256 == snapshot.head.head_sha256
                and verified.evidence_inventory_sha256
                == canonical_sha256([item.to_dict() for item in snapshot.evidence])
                and verified.attempt_head_sha256 == before.attempt_head_sha256
                and verified.quarantine_head_sha256 == before.quarantine_head_sha256,
                "CAMERA_SESSION_CHANGED_AFTER_AUDIT",
            )
            candidate = {
                "binding": bound,
                "verification": verified.to_dict(),
                "stages": [item.to_dict() for item in snapshot.stages],
            }
            summary_bytes = canonical(candidate)
            _require(
                len(summary_bytes) <= MAX_VERIFICATION_BYTES,
                "CAMERA_SESSION_VERIFICATION_BYTE_LIMIT",
            )
            with self._state_lock:
                self._retained = summary_bytes
            check(source=True)
            progress(
                "Original requirements readback finished; historical metadata remains unqualified and no stage was passed."
            )
            check(source=True)
            with self._state_lock:
                check()
                self._store = store
                self._cached.update(
                    status="REFRESHED_STORAGE_ONLY",
                    operation="REFRESH",
                    verification=candidate["verification"],
                    stages=candidate["stages"],
                    error=None,
                )
            return result
        except BaseException as error:
            with self._state_lock:
                self._store = None
                self._cached.update(
                    status="HELD",
                    verification=None,
                    stages=None,
                    error=_error_report(error, "CAMERA_SESSION_READBACK_FAILED"),
                )
            if (
                isinstance(error, (KeyboardInterrupt, SystemExit))
                or type(error) is PhysicalCameraSessionError
            ):
                raise
            raise PhysicalCameraSessionError(
                "CAMERA_SESSION_READBACK_FAILED"
            ) from error
        finally:
            self._operation_lock.release()

    def refresh(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int | None = None,
    ) -> dict[str, Any]:
        return self._perform(
            "REFRESH",
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
        )

    def _perform(
        self,
        operation: str,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int | None = None,
    ) -> dict[str, Any]:
        _require(
            isinstance(cancellation, threading.Event) and callable(progress),
            "CAMERA_SESSION_CANCELLATION_PROGRESS_REQUIRED",
        )
        _require(
            deadline_ns is None
            or (type(deadline_ns) is int and 0 < deadline_ns < 2**63),
            "CAMERA_SESSION_READBACK_DEADLINE_INVALID",
        )
        _require(
            self._operation_lock.acquire(blocking=False),
            "CAMERA_SESSION_OPERATION_ACTIVE",
        )
        entered = False
        try:
            with self._state_lock:
                if operation == "INITIALIZE":
                    _require(
                        not self._initialize_closed,
                        "CAMERA_SESSION_INITIALIZE_ALREADY_ATTEMPTED",
                    )
                    self._cached["initialize_attempted"] = True
                # A refresh targets an existing/partial original store. It must
                # never be followed by implicit reinitialization of that path.
                self._initialize_closed = True
                self._store = None
                self._cached.update(
                    status="RUNNING",
                    operation=operation,
                    verification=None,
                    stages=None,
                    error=None,
                )
                if operation == "REFRESH":
                    self._cached["partial_store_possible"] = True
                entered = True
            started = monotonic_ns()
            _require(
                type(started) is int and 0 <= started < 2**63 - DIAGNOSTIC_TIMEOUT_NS,
                "CAMERA_SESSION_CLOCK_INVALID",
            )
            # A parent file-only operation may shorten this refresh. Its
            # original limit is never extended and no device permit is involved.
            deadline = min(
                started + DIAGNOSTIC_TIMEOUT_NS,
                (
                    deadline_ns
                    if deadline_ns is not None
                    else started + DIAGNOSTIC_TIMEOUT_NS
                ),
            )
            last_now = started
            original_binding = self._binding
            bound = self.descriptor()
            workspace, directory = Path(bound["workspace"]), Path(bound["directory"])

            def check(*, source: bool = False) -> None:
                nonlocal last_now
                _require(
                    self._binding == original_binding, "CAMERA_SESSION_BINDING_CHANGED"
                )
                _require(not cancellation.is_set(), "CAMERA_SESSION_CANCELLED")
                now = monotonic_ns()
                _require(
                    type(now) is int and now >= last_now, "CAMERA_SESSION_CLOCK_INVALID"
                )
                last_now = now
                _require(now < deadline, "CAMERA_SESSION_TIMED_OUT")
                if source:
                    _require(
                        source_fingerprint(workspace) == bound["source_sha256"],
                        "CAMERA_SESSION_SOURCE_CHANGED",
                    )
                    # Slow source reads do not renew or hide the original clock.
                    check()

            check(source=True)
            _require(os.name == "nt", "CAMERA_SESSION_WINDOWS_NTFS_REQUIRED")
            progress(
                "Qualifying camera-only diagnostic storage; no device is queried."
                if operation == "INITIALIZE"
                else "Reopening and auditing the original camera-only diagnostic store; no operation is replayed."
            )
            check(source=True)
            software = require_regular_path(workspace / "software", directory=True)
            with ExitStack() as guards:
                # This explicit M1 compatibility mode denies directory deletion
                # and rename while permitting its qualified pointer replacement.
                guards.enter_context(
                    _directory_guard(software, allow_directory_write_sharing=True)
                )
                for path in (software / "runs", directory.parent, directory):
                    check()
                    if operation == "INITIALIZE":
                        if path == directory:
                            with self._state_lock:
                                self._cached["partial_store_possible"] = True
                            path.mkdir(exist_ok=False)
                        elif not os.path.lexists(path):
                            path.mkdir(exist_ok=False)
                    require_regular_path(path, directory=True)
                    guards.enter_context(
                        _directory_guard(path, allow_directory_write_sharing=True)
                    )
                    check()
                check(source=True)
                if operation == "INITIALIZE":
                    runtime = PhysicalOnboardingM1Runtime.initialize(
                        directory,
                        source_binding_sha256=physical_camera_source_binding(
                            bound["source_sha256"]
                        ),
                        cell_id=bound["cell_id"],
                    )
                    check(source=True)
                    runtime.create_session(
                        bound["session_id"],
                        mode="PHYSICAL_DIAGNOSTIC",
                        workspace_source_sha256=bound["source_sha256"],
                    )
                else:
                    runtime = PhysicalOnboardingM1Runtime.open(
                        directory,
                        source_binding_sha256=physical_camera_source_binding(
                            bound["source_sha256"]
                        ),
                        cell_id=bound["cell_id"],
                    )
                check(source=True)
                store = M1PhysicalCameraPersistence(
                    runtime,
                    workspace_source_sha256=bound["source_sha256"],
                    admission_facts=_denied_facts,
                )
                before = store.verification(bound["session_id"])
                check()
                # Auditing the camera records is essential: runtime.verify alone
                # validates the V2/global ledgers, not each camera receipt blob.
                with store.stage_transaction(
                    bound["session_id"],
                    expected_challenge_sha256=before.challenge_sha256,
                ) as transaction:
                    snapshot = transaction.snapshot()
                    records = transaction._audit_records()
                    check()
                    _require(
                        snapshot.header.mode == "PHYSICAL_DIAGNOSTIC"
                        and snapshot.header.cell_id == bound["cell_id"]
                        and snapshot.header.session_id == bound["session_id"],
                        "CAMERA_SESSION_ORIGINAL_STORE_MISMATCH",
                    )
                    if operation == "INITIALIZE":
                        _require(
                            tuple(item.stage for item in snapshot.stages) == STAGE_ORDER
                            and all(
                                item.state is V2StageState.PENDING
                                for item in snapshot.stages
                            )
                            and not snapshot.committed_events
                            and not snapshot.uncommitted_events
                            and not snapshot.evidence
                            and not records
                            and before.attempt_event_count == 0
                            and before.quarantine_count == 0,
                            "NEW_CAMERA_SESSION_MUST_BE_ENTIRELY_PENDING",
                        )
                # No current store/view is exposed until the actual lease exits.
                check()
                verified = store.verification(bound["session_id"])
                _require(
                    verified.session_header_sha256 == snapshot.header.header_sha256
                    and verified.session_head_sha256 == snapshot.head.head_sha256
                    and verified.evidence_inventory_sha256
                    == canonical_sha256([item.to_dict() for item in snapshot.evidence])
                    and verified.attempt_head_sha256 == before.attempt_head_sha256
                    and verified.quarantine_head_sha256
                    == before.quarantine_head_sha256,
                    "CAMERA_SESSION_CHANGED_AFTER_AUDIT",
                )
                if operation == "INITIALIZE":
                    _require(
                        verified.effects_allowed, "NEW_CAMERA_SESSION_STORAGE_HELD"
                    )
                candidate = {
                    "binding": bound,
                    "verification": verified.to_dict(),
                    "stages": [item.to_dict() for item in snapshot.stages],
                }
                payload = canonical(candidate)
                _require(
                    len(payload) <= MAX_VERIFICATION_BYTES,
                    "CAMERA_SESSION_VERIFICATION_BYTE_LIMIT",
                )
                # Preserve the fully observed historical summary even if a late
                # Stop/source check/progress callback/guard exit refuses current.
                with self._state_lock:
                    self._retained = payload
                check(source=True)
                progress(
                    "Original camera-only store verified. Physical stages are not automatically passed."
                )
                check(source=True)
            check(source=True)
            with self._state_lock:
                check()
                self._store = store
                self._cached.update(
                    status=(
                        "STORAGE_READY_PENDING"
                        if operation == "INITIALIZE"
                        else "REFRESHED_STORAGE_ONLY"
                    ),
                    verification=candidate["verification"],
                    stages=candidate["stages"],
                    error=None,
                )
            return self.view()
        except BaseException as error:
            if entered:
                with self._state_lock:
                    self._store = None
                    self._cached.update(
                        status="HELD",
                        verification=None,
                        stages=None,
                        error=_error_report(error, "CAMERA_SESSION_STORAGE_FAILED"),
                    )
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            if type(error) is PhysicalCameraSessionError:
                raise
            raise PhysicalCameraSessionError("CAMERA_SESSION_STORAGE_FAILED") from error
        finally:
            self._operation_lock.release()

    @contextmanager
    def stage_transaction(
        self, *, expected_challenge_sha256: str
    ) -> Iterator[M1PhysicalCameraTransaction]:
        """Internal stage-storage seam; no facts or camera authorization provided.

        The exact persistence audits records and verifies the supplied challenge
        under real leases. Callers must explicitly refresh after scope exit;
        this cached projection cannot assume the stage remained unchanged.
        """
        _require(
            self._operation_lock.acquire(blocking=False),
            "CAMERA_SESSION_OPERATION_ACTIVE",
        )
        report = {
            "code": "CAMERA_SESSION_REFRESH_REQUIRED",
            "type": "PhysicalCameraSessionError",
        }
        try:
            with self._state_lock:
                store = self._store
                _require(
                    type(store) is M1PhysicalCameraPersistence,
                    "CAMERA_SESSION_CURRENT_OPEN_REQUIRED",
                )
            bound = self.descriptor()
            _require(
                source_fingerprint(Path(bound["workspace"])) == bound["source_sha256"],
                "CAMERA_SESSION_SOURCE_CHANGED",
            )
            assert store is not None
            with store.stage_transaction(
                bound["session_id"], expected_challenge_sha256=expected_challenge_sha256
            ) as transaction:
                _require(
                    type(transaction) is M1PhysicalCameraTransaction,
                    "EXACT_CAMERA_TRANSACTION_REQUIRED",
                )
                yield transaction
        except BaseException as error:
            report = _error_report(error, "CAMERA_SESSION_STAGE_SCOPE_FAILED")
            raise
        finally:
            with self._state_lock:
                self._store = None
                self._cached.update(
                    status="HELD",
                    verification=None,
                    stages=None,
                    error=report,
                )
            self._operation_lock.release()
