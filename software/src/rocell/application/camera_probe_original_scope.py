"""Read-only original probe handoff under exact CAMERA ownership.

The full original audit happens before issuing a short-lived execution permit.
Later admission reads compare its immutable session snapshot with the actual
leased store, plus the current application guard. This object is neither a
permit nor a live enrollment, and there is deliberately no restore/import API.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from threading import Event
from time import monotonic_ns
from typing import Any, Callable

from .cell_commissioning_coordinator import RegisteredActionRequest
from .commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState
from .camera_probe_preparation import (
    SOURCE_WORKFLOW_PROBE_SCHEMA,
    CameraProbePreparation,
    CameraProbePreparationReview,
)
from .camera_activation_campaign_contract import ACTION_IDS
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import canonical, digest

MAX_CONTEXT_NS = 300_000_000_000
MAX_ORIGINAL_READ_NS = 180_000_000_000
_ORIGINAL_READ = object()


class CameraProbeOriginalScopeError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CameraProbeOriginalScopeError(code)


def _leases(cell_id: str, session_id: str) -> tuple[LeaseSpec, ...]:
    return (
        LeaseSpec(LeaseLevel.CELL, cell_id),
        LeaseSpec(LeaseLevel.SESSION, session_id),
        LeaseSpec(LeaseLevel.CAMERA, cell_id),
    )


@dataclass(frozen=True, slots=True)
class VerifiedCameraProbeOriginal:
    """In-process original-read provenance, not hardware or hazard qualification.

    Only the reader below produces the private provenance marker. Serialized
    summaries cannot create this object; the caller still needs substantive
    operator-condition/capacity admission and the core's one-use permit.
    """

    _snapshot: V2SessionSnapshot = field(repr=False)
    _workflow: bytes = field(repr=False)
    _binding: bytes = field(repr=False)
    _preparation: CameraProbePreparation = field(repr=False)
    _review: CameraProbePreparationReview = field(repr=False)
    _workspace: Path = field(repr=False)
    _source_sha256: str
    _launch_id: str
    _cancellation: Event = field(repr=False)
    _read_completed_at_ns: int
    _deadline_ns: int
    _validate_current_context: Callable[[], object] = field(repr=False)
    _read_provenance: object = field(repr=False)

    def __post_init__(self) -> None:
        _need(
            self._read_provenance is _ORIGINAL_READ,
            "CAMERA_PROBE_ORIGINAL_RESTORE_FORBIDDEN",
        )

    def summary(self) -> dict[str, Any]:
        """Cached display only; no currentness claim and no filesystem access."""
        return dict(
            schema="rocell.camera_probe_original_scope_summary.v1",
            source_sha256=self._source_sha256,
            launch_session_id=self._launch_id,
            session_id=self._snapshot.header.session_id,
            cell_id=self._snapshot.header.cell_id,
            header_sha256=self._snapshot.header.header_sha256,
            journal_head_sha256=self._snapshot.head.head_sha256,
            original_workflow_sha256=digest(self._workflow),
            preparation_sha256=self._preparation.sha256,
            review_sha256=self._review.sha256,
            authenticated_at_read=True,
            currentness_requires_revalidation=True,
            physical_authority=False,
            hardware_qualified=False,
            connected=False,
            meaning="Original setup was authenticated under CAMERA ownership. This cached summary cannot authorize device access or restore the in-process guard.",
        )

    def _check_context(self) -> None:
        _need(
            self._read_provenance is _ORIGINAL_READ,
            "CAMERA_PROBE_ORIGINAL_RESTORE_FORBIDDEN",
        )
        self._check_time()
        _need(
            self._validate_current_context() is None,
            "CAMERA_PROBE_ORIGINAL_CONTEXT_CHANGED",
        )
        _need(
            source_fingerprint(self._workspace) == self._source_sha256,
            "CAMERA_PROBE_ORIGINAL_SOURCE_CHANGED",
        )
        self._check_time()

    def _check_time(self) -> None:
        now = monotonic_ns()
        _need(
            type(now) is int
            and self._read_completed_at_ns <= now < self._deadline_ns
            and not self._cancellation.is_set(),
            "CAMERA_PROBE_ORIGINAL_CONTEXT_EXPIRED",
        )

    def assert_current(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> None:
        self._read_current_records(transaction, request, snapshot)

    def _read_current_records(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> dict[str, dict[str, Any]]:
        """Cheap semantic reuse only after actual M1 inventory/record validation.

        The core owns changing attempt/quarantine heads. No stage/package may
        change from the authenticated snapshot, even when its visible stage name
        or preparation hash looks unchanged. No transaction is opened here.
        Returned records are read data for immediate same-call computations,
        never cached admission or proof that a later boundary is current.
        """
        self._check_context()
        _need(
            type(transaction) is M1PhysicalCameraTransaction,
            "CAMERA_PROBE_EXACT_TRANSACTION_REQUIRED",
        )
        transaction._check_scope()
        _need(
            str(transaction._session.directory.parent)
            == json.loads(self._binding)["directory"],
            "CAMERA_PROBE_ORIGINAL_DIRECTORY_CHANGED",
        )
        _need(
            transaction.held_leases
            == _leases(self._snapshot.header.cell_id, self._snapshot.header.session_id),
            "CAMERA_PROBE_EXACT_LEASES_REQUIRED",
        )
        _need(
            type(request) is RegisteredActionRequest
            and request.cell_id == self._snapshot.header.cell_id
            and request.session_id == self._snapshot.header.session_id
            and request.action_id == ACTION_IDS["probe"],
            "CAMERA_PROBE_ORIGINAL_REQUEST_CHANGED",
        )
        # The original reader audited all semantic predecessors. Fresh M1
        # snapshots recheck immutable manifests/payload hashes; exact equality
        # allows reusing that semantic result without rereading old hardware.
        # Capacity consumers need the complete family (USB plus camera), since
        # its aggregate storage quotas are shared. The audit already validates
        # every domain; this only retains its full, freshly read return value.
        records = transaction._audit_records(include_family=True)
        _need(
            type(snapshot) is V2SessionSnapshot
            and snapshot == transaction.snapshot() == self._snapshot,
            "CAMERA_PROBE_ORIGINAL_SNAPSHOT_CHANGED",
        )
        self._check_context()
        transaction._check_scope()
        _need(
            transaction.held_leases
            == _leases(self._snapshot.header.cell_id, self._snapshot.header.session_id),
            "CAMERA_PROBE_EXACT_LEASES_REQUIRED",
        )
        return records


def read_camera_probe_originals(
    transaction: M1PhysicalCameraTransaction,
    *,
    workspace: Path,
    source_sha256: str,
    launch_session_id: str,
    expected_header_sha256: str,
    expected_preparation_sha256: str,
    expected_review_sha256: str,
    cancellation: Event,
    deadline_ns: int,
    validate_current_context: Callable[[], object],
) -> VerifiedCameraProbeOriginal:
    """Authenticate the same full originals on the caller's exact camera lease.

    Input hashes are comparisons, never proof. The assigned directory is derived
    from the actual scoped store, not supplied by browser input or a saved plan.
    Nothing probes a camera, starts a process, writes evidence or changes a stage.
    """
    from .physical_camera_session import (
        PhysicalCameraSession,
        _read_original_evidence_in_scope,
    )

    started = monotonic_ns()
    _need(
        type(transaction) is M1PhysicalCameraTransaction
        and isinstance(workspace, Path),
        "CAMERA_PROBE_EXACT_TRANSACTION_REQUIRED",
    )
    _need(
        type(cancellation) is Event
        and callable(validate_current_context)
        and type(deadline_ns) is int
        and started < deadline_ns <= started + MAX_CONTEXT_NS,
        "CAMERA_PROBE_ORIGINAL_BOUNDED_CONTEXT_REQUIRED",
    )
    for value in (
        source_sha256,
        expected_header_sha256,
        expected_preparation_sha256,
        expected_review_sha256,
    ):
        _need(
            type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "CAMERA_PROBE_ORIGINAL_HASH_REQUIRED",
        )
    _need(
        type(launch_session_id) is str
        and re.fullmatch(r"wizard-[0-9a-f]{32}", launch_session_id) is not None,
        "CAMERA_PROBE_ORIGINAL_LAUNCH_REQUIRED",
    )
    read_deadline = min(deadline_ns, started + MAX_ORIGINAL_READ_NS)
    last_now = started

    def check(*, source: bool = False) -> None:
        nonlocal last_now
        transaction._check_scope()
        now = monotonic_ns()
        _need(
            type(now) is int and now >= last_now, "CAMERA_PROBE_ORIGINAL_CLOCK_INVALID"
        )
        last_now = now
        _need(
            not cancellation.is_set() and now < read_deadline,
            "CAMERA_PROBE_ORIGINAL_READ_INTERRUPTED",
        )
        _need(
            validate_current_context() is None, "CAMERA_PROBE_ORIGINAL_CONTEXT_CHANGED"
        )
        # The shared reader requests source checks between original packages.
        # Honor that contract without opening another transaction or extending
        # the caller's deadline while hashing the application files.
        if source:
            _need(
                source_fingerprint(workspace) == source_sha256,
                "CAMERA_PROBE_ORIGINAL_SOURCE_CHANGED",
            )
            checked_at = monotonic_ns()
            _need(
                type(checked_at) is int and checked_at >= last_now,
                "CAMERA_PROBE_ORIGINAL_CLOCK_INVALID",
            )
            last_now = checked_at
            _need(
                not cancellation.is_set() and checked_at < read_deadline,
                "CAMERA_PROBE_ORIGINAL_READ_INTERRUPTED",
            )

    check()
    _need(
        source_fingerprint(workspace) == source_sha256,
        "CAMERA_PROBE_ORIGINAL_SOURCE_CHANGED",
    )
    before = transaction.snapshot()
    _need(
        type(before) is V2SessionSnapshot
        and transaction.held_leases
        == _leases(before.header.cell_id, before.header.session_id)
        and before.header.header_sha256 == expected_header_sha256
        and before.header.source_binding_sha256
        == physical_camera_source_binding(source_sha256),
        "CAMERA_PROBE_ORIGINAL_STORE_CHANGED",
    )
    directory = transaction._session.directory.parent
    binding = PhysicalCameraSession(
        workspace,
        directory,
        launch_id=directory.name,
        source_sha256=source_sha256,
        cell_id=before.header.cell_id,
        session_id=before.header.session_id,
    ).descriptor()
    snapshot, workflow = _read_original_evidence_in_scope(
        transaction,
        bound=binding,
        expected_header_sha256=expected_header_sha256,
        strict_workflow=True,
        check=check,
        camera_scope=True,
    )
    check()
    _need(
        type(workflow) is dict
        and workflow.get("schema") == SOURCE_WORKFLOW_PROBE_SCHEMA,
        "CAMERA_PROBE_REVIEWED_ORIGINAL_REQUIRED",
    )
    assert workflow is not None
    row = workflow["camera_probe_preparation"]
    _need(
        row["state"] == "REVIEWED_FOR_ADMISSION" and row["review"] is not None,
        "CAMERA_PROBE_REVIEWED_ORIGINAL_REQUIRED",
    )
    preparation = CameraProbePreparation(canonical(row["preparation"]["document"]))
    review = CameraProbePreparationReview(canonical(row["review"]["document"]))
    plan = preparation.to_dict()["plan"]
    _need(
        preparation.sha256 == expected_preparation_sha256
        and review.sha256 == expected_review_sha256
        and review.to_dict()["preparation_sha256"] == preparation.sha256
        and plan["launch_session_id"] == launch_session_id
        and all(
            snapshot.state_for(stage) is V2StageState.PASS for stage in STAGE_ORDER[:4]
        )
        and snapshot.next_action.stage is STAGE_ORDER[4]
        and snapshot.next_action.stage_state is V2StageState.WAITING_OPERATOR,
        "CAMERA_PROBE_ORIGINAL_REVIEW_CHANGED",
    )
    _need(
        transaction.snapshot() == snapshot == before,
        "CAMERA_PROBE_ORIGINAL_SNAPSHOT_CHANGED",
    )
    _need(
        source_fingerprint(workspace) == source_sha256,
        "CAMERA_PROBE_ORIGINAL_SOURCE_CHANGED",
    )
    check()
    return VerifiedCameraProbeOriginal(
        snapshot,
        canonical(workflow),
        canonical(binding),
        preparation,
        review,
        workspace,
        source_sha256,
        launch_session_id,
        cancellation,
        last_now,
        deadline_ns,
        validate_current_context,
        _ORIGINAL_READ,
    )
