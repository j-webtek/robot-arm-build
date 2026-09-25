"""Crash-aware, zero-hardware runtime for physical-onboarding M1.

This module joins the V2 session store, qualified Windows publication,
cell-global attempt/quarantine ledgers, and canonical leases.  It intentionally
exposes no camera, serial, power, permit, worker, motion, descent, or contact
operation.  Its public mutations are limited to storage initialization, V2
session creation, evidence-only startup recovery, and namespace-isolated
rehearsal storage transactions. Rehearsal journal/ledger mutations do not grant
physical authority or make a device interface available.

The durable qualification anchor is stable for the life of the deployment
root.  Every process also runs a fresh on-volume self-test; the adapter accepts
the fresh report only when all safety-relevant fields match the anchor.  This
lets append-only ledger headers retain a stable qualification hash without
mistaking an old receipt for a current startup check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Any, Iterable, Iterator, Mapping

from rocell.application.physical_onboarding import STAGE_PLAN_SHA256
from rocell.application.physical_onboarding_attempts import (
    AttemptEvent,
    AttemptLedgerSnapshot,
    PhysicalOnboardingAttemptError,
    PhysicalOnboardingAttemptLedger,
)
from rocell.application.physical_onboarding_durability import (
    MAX_QUALIFICATION_REPORT_BYTES,
    DurabilityQualificationReport,
    PhysicalOnboardingDurabilityError,
    PublicationMode,
    canonical_bytes,
    canonical_sha256,
    contained_path,
    load_durability_qualification_report,
    publish_bytes,
    read_bounded_regular_file,
    require_effect_durability,
    run_on_volume_startup_self_test,
    safe_root,
)
from rocell.application.physical_onboarding_leases import (
    HeldLeaseSet,
    LeaseLevel,
    LeaseOwnerState,
    LeaseSpec,
    OnboardingLeaseManager,
)
from rocell.application.physical_onboarding_quarantine import (
    CellQuarantinedError,
    PhysicalOnboardingQuarantineError,
    PhysicalOnboardingQuarantineLedger,
    QuarantineLedgerSnapshot,
    StartupRecoveryReport,
    recover_physical_onboarding_startup,
)
from rocell.application.physical_onboarding_storage import (
    QualifiedWindowsOnboardingPublication,
)
from rocell.application.physical_onboarding_v2 import (
    PhysicalOnboardingV2Session,
    V2SessionSnapshot,
)


M1_RUNTIME_SCHEMA = "rocell.physical_onboarding_m1_runtime.v1"
M1_CELL_SCHEMA = "rocell.physical_onboarding_m1_cell.v1"
DURABILITY_ANCHOR_FILENAME = "durability-anchor.json"
M1_STATUS = "M1_STORAGE_READY_ZERO_HARDWARE_AUTHORITY"
M1_QUARANTINED_STATUS = "M1_INTEGRITY_VALID_CELL_QUARANTINED"
M1_RECONCILIATION_STATUS = "M1_INTEGRITY_VALID_RECONCILIATION_REQUIRED"

_ZERO_SHA256 = "0" * 64
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_CELL_FIELDS = frozenset(
    {
        "schema",
        "cell_id",
        "cell_key_sha256",
        "source_binding_sha256",
        "stage_plan_sha256",
        "durability_qualification_sha256",
        "attempt_ledger_id",
        "quarantine_ledger_id",
        "created_at_ns",
        "runtime_activation",
        "device_io_authorized",
        "robot_power_authorized",
        "motion_authorized",
        "contact_authorized",
        "automatic_effect_replay_allowed",
        "physical_release_effect",
        "cell_sha256",
    }
)


class PhysicalOnboardingM1Error(RuntimeError):
    """The M1 store is malformed, stale, unqualified, or lock-inconsistent."""


def _digest(value: object, label: str, *, allow_zero: bool = False) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PhysicalOnboardingM1Error(f"{label} must be lowercase SHA-256")
    if not allow_zero and value == _ZERO_SHA256:
        raise PhysicalOnboardingM1Error(f"{label} cannot be the zero digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise PhysicalOnboardingM1Error(f"{label} is not a bounded identifier")
    if value.split(".", 1)[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        raise PhysicalOnboardingM1Error(f"{label} is a reserved Windows name")
    return value


def _timestamp(value: object, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > 2**63 - 1
    ):
        raise PhysicalOnboardingM1Error(f"{label} must be positive nanoseconds")
    return value


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingM1Error(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _read_canonical_object(path: Path, label: str, *, maximum: int) -> dict[str, Any]:
    try:
        payload = read_bounded_regular_file(
            path,
            maximum_bytes=maximum,
            label=label,
        )
    except (OSError, PhysicalOnboardingDurabilityError) as exc:
        raise PhysicalOnboardingM1Error(f"cannot read {label}") from exc
    if not payload or len(payload) > maximum:
        raise PhysicalOnboardingM1Error(f"{label} exceeds its byte bound")
    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=_strict_object,
            parse_float=lambda token: (_ for _ in ()).throw(
                PhysicalOnboardingM1Error(f"{label} contains a float")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                PhysicalOnboardingM1Error(
                    f"{label} contains nonfinite constant {token!r}"
                )
            ),
        )
    except PhysicalOnboardingM1Error:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingM1Error(f"{label} is not strict JSON") from exc
    if (
        not isinstance(value, dict)
        or canonical_bytes(value, maximum_bytes=maximum) != payload
    ):
        raise PhysicalOnboardingM1Error(f"{label} is not canonical JSON")
    return value


def _stable_qualification_identity(
    report: DurabilityQualificationReport,
) -> tuple[object, ...]:
    return (
        report.source_binding_sha256,
        report.root_sha256,
        report.platform,
        report.filesystem,
        report.volume_identity,
        report.adapter_id,
        tuple((check.check_id, check.passed) for check in report.checks),
        report.qualified_for_effects,
    )


@dataclass(frozen=True, slots=True)
class M1CellDescriptor:
    cell_id: str
    cell_key_sha256: str
    source_binding_sha256: str
    durability_qualification_sha256: str
    attempt_ledger_id: str
    quarantine_ledger_id: str
    created_at_ns: int
    cell_sha256: str

    def core_dict(self) -> dict[str, object]:
        return {
            "schema": M1_CELL_SCHEMA,
            "cell_id": self.cell_id,
            "cell_key_sha256": self.cell_key_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "stage_plan_sha256": STAGE_PLAN_SHA256,
            "durability_qualification_sha256": self.durability_qualification_sha256,
            "attempt_ledger_id": self.attempt_ledger_id,
            "quarantine_ledger_id": self.quarantine_ledger_id,
            "created_at_ns": self.created_at_ns,
            "runtime_activation": False,
            "device_io_authorized": False,
            "robot_power_authorized": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "automatic_effect_replay_allowed": False,
            "physical_release_effect": "NONE",
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "cell_sha256": self.cell_sha256}

    @classmethod
    def build(
        cls,
        *,
        cell_id: str,
        source_binding_sha256: str,
        durability_qualification_sha256: str,
        created_at_ns: int,
    ) -> "M1CellDescriptor":
        selected_cell = _identifier(cell_id, "cell_id")
        source = _digest(source_binding_sha256, "source_binding_sha256")
        qualification = _digest(
            durability_qualification_sha256,
            "durability_qualification_sha256",
        )
        created = _timestamp(created_at_ns, "created_at_ns")
        key = hashlib.sha256(selected_cell.encode("utf-8")).hexdigest()
        provisional = cls(
            cell_id=selected_cell,
            cell_key_sha256=key,
            source_binding_sha256=source,
            durability_qualification_sha256=qualification,
            attempt_ledger_id=f"attempts-{key[:32]}",
            quarantine_ledger_id=f"quarantine-{key[:32]}",
            created_at_ns=created,
            cell_sha256=_ZERO_SHA256,
        )
        return cls(
            cell_id=provisional.cell_id,
            cell_key_sha256=provisional.cell_key_sha256,
            source_binding_sha256=provisional.source_binding_sha256,
            durability_qualification_sha256=(
                provisional.durability_qualification_sha256
            ),
            attempt_ledger_id=provisional.attempt_ledger_id,
            quarantine_ledger_id=provisional.quarantine_ledger_id,
            created_at_ns=provisional.created_at_ns,
            cell_sha256=canonical_sha256(provisional.core_dict()),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M1CellDescriptor":
        if set(value) != _CELL_FIELDS or value.get("schema") != M1_CELL_SCHEMA:
            raise PhysicalOnboardingM1Error("cell descriptor fields or schema differ")
        if (
            value["stage_plan_sha256"] != STAGE_PLAN_SHA256
            or value["runtime_activation"] is not False
            or value["device_io_authorized"] is not False
            or value["robot_power_authorized"] is not False
            or value["motion_authorized"] is not False
            or value["contact_authorized"] is not False
            or value["automatic_effect_replay_allowed"] is not False
            or value["physical_release_effect"] != "NONE"
        ):
            raise PhysicalOnboardingM1Error(
                "cell descriptor exceeds zero authority or changed stage plan"
            )
        descriptor = cls(
            cell_id=_identifier(value["cell_id"], "cell_id"),
            cell_key_sha256=_digest(value["cell_key_sha256"], "cell_key_sha256"),
            source_binding_sha256=_digest(
                value["source_binding_sha256"], "source_binding_sha256"
            ),
            durability_qualification_sha256=_digest(
                value["durability_qualification_sha256"],
                "durability_qualification_sha256",
            ),
            attempt_ledger_id=_identifier(
                value["attempt_ledger_id"], "attempt_ledger_id"
            ),
            quarantine_ledger_id=_identifier(
                value["quarantine_ledger_id"], "quarantine_ledger_id"
            ),
            created_at_ns=_timestamp(value["created_at_ns"], "created_at_ns"),
            cell_sha256=_digest(value["cell_sha256"], "cell_sha256"),
        )
        expected = cls.build(
            cell_id=descriptor.cell_id,
            source_binding_sha256=descriptor.source_binding_sha256,
            durability_qualification_sha256=(
                descriptor.durability_qualification_sha256
            ),
            created_at_ns=descriptor.created_at_ns,
        )
        if descriptor != expected:
            raise PhysicalOnboardingM1Error("cell descriptor hash or identity mismatch")
        return descriptor


@dataclass(slots=True)
class _LeaseMutationGuard:
    """Adapter callback proving an acquired lease set still owns its metadata."""

    held: HeldLeaseSet | None = None

    def activate(
        self,
        held: HeldLeaseSet,
        *,
        expected_specs: tuple[LeaseSpec, ...],
        source_binding_sha256: str,
    ) -> None:
        if self.held is not None:
            raise PhysicalOnboardingM1Error("a mutation lease set is already active")
        if not isinstance(held, HeldLeaseSet) or held.closed:
            raise PhysicalOnboardingM1Error("mutation requires live leases")
        source = _digest(source_binding_sha256, "mutation lease source binding")
        owners = held.owners
        if len(owners) != len(expected_specs) or any(
            owner.level is not spec.level
            or owner.resource_id != spec.resource_id
            or owner.resource_sha256 != spec.resource_sha256
            or owner.source_binding_sha256 != source
            or owner.state is not LeaseOwnerState.ACTIVE
            for owner, spec in zip(owners, expected_specs)
        ):
            raise PhysicalOnboardingM1Error(
                "mutation lease set does not match the exact required resources"
            )
        self.held = held

    def deactivate(self) -> None:
        self.held = None

    def __call__(self) -> None:
        held = self.held
        if held is None or held.closed:
            raise PhysicalOnboardingM1Error("qualified publication has no live leases")
        # The complete state challenge was evaluated by acquire().  During a
        # multi-file commit that state intentionally changes, so subsequent
        # adapter guards recheck owner metadata without pretending the original
        # state hash should remain current.
        held.recheck_challenge(lambda: held.expected_challenge_sha256)


@dataclass(frozen=True, slots=True)
class M1RuntimeVerification:
    cell: M1CellDescriptor
    qualification_anchor_sha256: str
    startup_qualification_sha256: str
    attempt_head_sha256: str
    attempt_event_count: int
    unresolved_attempt_ids: tuple[str, ...]
    uncertain_attempt_ids: tuple[str, ...]
    quarantine_head_sha256: str
    quarantine_count: int
    quarantined: bool
    session_id: str | None
    session_header_sha256: str
    session_head_sha256: str
    session_reconciliation_required: bool
    active_lease_owners: tuple[str, ...]
    evidence_inventory_sha256: str
    challenge_sha256: str

    @property
    def effects_allowed(self) -> bool:
        return (
            not self.quarantined
            and not self.unresolved_attempt_ids
            and not self.uncertain_attempt_ids
            and not self.session_reconciliation_required
            and not self.active_lease_owners
        )

    def to_dict(self) -> dict[str, object]:
        if self.effects_allowed:
            status = M1_STATUS
        elif self.quarantined:
            status = M1_QUARANTINED_STATUS
        else:
            status = M1_RECONCILIATION_STATUS
        return {
            "schema": M1_RUNTIME_SCHEMA,
            "status": status,
            "runtime_activation": False,
            "cell": self.cell.to_dict(),
            "qualification": {
                "anchor_sha256": self.qualification_anchor_sha256,
                "startup_report_sha256": self.startup_qualification_sha256,
                "qualified_windows_ntfs": True,
            },
            "attempt_ledger": {
                "head_sha256": self.attempt_head_sha256,
                "event_count": self.attempt_event_count,
                "unresolved_attempt_ids": list(self.unresolved_attempt_ids),
                "uncertain_attempt_ids": list(self.uncertain_attempt_ids),
            },
            "quarantine": {
                "head_sha256": self.quarantine_head_sha256,
                "event_count": self.quarantine_count,
                "latched": self.quarantined,
                "clearing_supported": False,
            },
            "session": {
                "session_id": self.session_id,
                "header_sha256": self.session_header_sha256,
                "head_sha256": self.session_head_sha256,
                "evidence_inventory_sha256": self.evidence_inventory_sha256,
                "reconciliation_required": self.session_reconciliation_required,
            },
            "leases": {
                "active_or_stale_owners": list(self.active_lease_owners),
                "reconciliation_required": bool(self.active_lease_owners),
            },
            "challenge_sha256": self.challenge_sha256,
            "effects_allowed_by_m1_storage": self.effects_allowed,
            "effect_methods_exposed": False,
            "operation_effect": {
                "os_device_metadata_reads": 0,
                "device_opens": 0,
                "camera_frames_captured": 0,
                "serial_transactions": 0,
                "robot_power_operations": 0,
                "robot_commands_sent": 0,
            },
            "authority": {
                "diagnostic_only": True,
                "device_io_authorized": False,
                "robot_power_authorized": False,
                "motion_authorized": False,
                "descent_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }


@dataclass(slots=True)
class PhysicalOnboardingM1Runtime:
    """Lease-owning M1 facade with an intentionally zero-hardware public API."""

    deployment_root: Path
    source_binding_sha256: str
    cell: M1CellDescriptor
    qualification_anchor: DurabilityQualificationReport
    startup_report: DurabilityQualificationReport
    _guard: _LeaseMutationGuard = field(repr=False)
    _publication: QualifiedWindowsOnboardingPublication = field(repr=False)
    _leases: OnboardingLeaseManager = field(repr=False)
    _attempts: PhysicalOnboardingAttemptLedger = field(repr=False)
    _quarantine: PhysicalOnboardingQuarantineLedger = field(repr=False)

    @classmethod
    def initialize(
        cls,
        deployment_root: Path,
        *,
        source_binding_sha256: str,
        cell_id: str,
        created_at_ns: int | None = None,
    ) -> "PhysicalOnboardingM1Runtime":
        """Explicitly initialize stable storage; never inspect or open a device."""

        root = safe_root(deployment_root, label="M1 deployment root")
        source = _digest(source_binding_sha256, "source_binding_sha256")
        selected_cell = _identifier(cell_id, "cell_id")
        created = _timestamp(
            time.time_ns() if created_at_ns is None else created_at_ns,
            "created_at_ns",
        )
        anchor_path = contained_path(
            root, DURABILITY_ANCHOR_FILENAME, label="durability anchor"
        )
        if os.path.lexists(anchor_path):
            anchor = load_durability_qualification_report(anchor_path)
            require_effect_durability(anchor, root=root, source_binding_sha256=source)
            startup = run_on_volume_startup_self_test(
                root,
                source_binding_sha256=source,
                checked_at_ns=max(time.time_ns(), anchor.checked_at_ns),
            )
        else:
            anchor = run_on_volume_startup_self_test(
                root,
                source_binding_sha256=source,
                checked_at_ns=created,
            )
            require_effect_durability(anchor, root=root, source_binding_sha256=source)
            publish_bytes(
                root,
                DURABILITY_ANCHOR_FILENAME,
                canonical_bytes(
                    anchor.to_dict(), maximum_bytes=MAX_QUALIFICATION_REPORT_BYTES
                ),
                mode=PublicationMode.IMMUTABLE,
                maximum_bytes=MAX_QUALIFICATION_REPORT_BYTES,
            )
            startup = anchor
        cls._require_matching_reports(anchor, startup)

        cells_root = contained_path(root, "cells", label="M1 cells root")
        try:
            cells_root.mkdir(exist_ok=True)
        except OSError as exc:
            raise PhysicalOnboardingM1Error("cannot create M1 cells root") from exc
        cells_root = safe_root(cells_root, label="M1 cells root")

        descriptor = M1CellDescriptor.build(
            cell_id=selected_cell,
            source_binding_sha256=source,
            durability_qualification_sha256=anchor.report_sha256,
            created_at_ns=created,
        )
        cell_root = contained_path(
            cells_root,
            f"cell-{descriptor.cell_key_sha256}",
            label="M1 cell root",
        )
        if not os.path.lexists(cell_root):
            cls._initialize_cell(root, cells_root, descriptor, anchor, startup)
        return cls.open(
            root,
            source_binding_sha256=source,
            cell_id=selected_cell,
        )

    @classmethod
    def open(
        cls,
        deployment_root: Path,
        *,
        source_binding_sha256: str,
        cell_id: str,
    ) -> "PhysicalOnboardingM1Runtime":
        """Requalify this startup and strictly open one existing cell."""

        root = safe_root(deployment_root, label="M1 deployment root")
        source = _digest(source_binding_sha256, "source_binding_sha256")
        selected_cell = _identifier(cell_id, "cell_id")
        anchor_path = contained_path(
            root, DURABILITY_ANCHOR_FILENAME, label="durability anchor"
        )
        anchor = load_durability_qualification_report(anchor_path)
        require_effect_durability(anchor, root=root, source_binding_sha256=source)
        startup = run_on_volume_startup_self_test(
            root,
            source_binding_sha256=source,
            checked_at_ns=max(time.time_ns(), anchor.checked_at_ns),
        )
        cls._require_matching_reports(anchor, startup)
        descriptor = cls._load_cell(root, selected_cell, source, anchor.report_sha256)
        guard = _LeaseMutationGuard()
        publication = QualifiedWindowsOnboardingPublication(
            deployment_root=root,
            source_binding_sha256=source,
            qualification_anchor=anchor,
            startup_report=startup,
            mutation_guard=guard,
        )
        lease_manager = OnboardingLeaseManager(
            root,
            source,
            OnboardingLeaseManager.new_launch_nonce(),
            startup,
        )
        cell_root = cls._cell_root(root, descriptor)
        attempts = PhysicalOnboardingAttemptLedger.open(
            cell_root / "attempts",
            publication,
            expected_cell_id=descriptor.cell_id,
        )
        quarantine = PhysicalOnboardingQuarantineLedger.open(
            cell_root / "quarantine",
            publication,
            expected_cell_id=descriptor.cell_id,
        )
        runtime = cls(
            deployment_root=root,
            source_binding_sha256=source,
            cell=descriptor,
            qualification_anchor=anchor,
            startup_report=startup,
            _guard=guard,
            _publication=publication,
            _leases=lease_manager,
            _attempts=attempts,
            _quarantine=quarantine,
        )
        runtime.verify()
        return runtime

    @staticmethod
    def _require_matching_reports(
        anchor: DurabilityQualificationReport,
        startup: DurabilityQualificationReport,
    ) -> None:
        if _stable_qualification_identity(anchor) != _stable_qualification_identity(
            startup
        ):
            raise PhysicalOnboardingM1Error(
                "fresh startup qualification differs from the stable anchor"
            )
        if startup.checked_at_ns < anchor.checked_at_ns:
            raise PhysicalOnboardingM1Error(
                "fresh startup qualification predates the stable anchor"
            )

    @staticmethod
    def _cell_root(root: Path, descriptor: M1CellDescriptor) -> Path:
        cells_root = safe_root(root / "cells", label="M1 cells root")
        return contained_path(
            cells_root,
            f"cell-{descriptor.cell_key_sha256}",
            label="M1 cell root",
        )

    @classmethod
    def _load_cell(
        cls,
        root: Path,
        cell_id: str,
        source_binding_sha256: str,
        qualification_sha256: str,
    ) -> M1CellDescriptor:
        key = hashlib.sha256(cell_id.encode("utf-8")).hexdigest()
        cells_root = safe_root(root / "cells", label="M1 cells root")
        cell_root = safe_root(
            contained_path(cells_root, f"cell-{key}", label="M1 cell root"),
            label="M1 cell root",
        )
        descriptor = M1CellDescriptor.from_dict(
            _read_canonical_object(
                cell_root / "cell.json", "M1 cell descriptor", maximum=64 * 1024
            )
        )
        if (
            descriptor.cell_id != cell_id
            or descriptor.cell_key_sha256 != key
            or descriptor.source_binding_sha256 != source_binding_sha256
            or descriptor.durability_qualification_sha256 != qualification_sha256
        ):
            raise PhysicalOnboardingM1Error(
                "M1 cell belongs to another identity, source, or qualification"
            )
        return descriptor

    @classmethod
    def _initialize_cell(
        cls,
        root: Path,
        cells_root: Path,
        descriptor: M1CellDescriptor,
        anchor: DurabilityQualificationReport,
        startup: DurabilityQualificationReport,
    ) -> None:
        guard = _LeaseMutationGuard()
        publication = QualifiedWindowsOnboardingPublication(
            deployment_root=root,
            source_binding_sha256=descriptor.source_binding_sha256,
            qualification_anchor=anchor,
            startup_report=startup,
            mutation_guard=guard,
        )
        manager = OnboardingLeaseManager(
            root,
            descriptor.source_binding_sha256,
            OnboardingLeaseManager.new_launch_nonce(),
            startup,
        )
        final_root = contained_path(
            cells_root,
            f"cell-{descriptor.cell_key_sha256}",
            label="M1 cell root",
        )
        challenge = cls._bootstrap_challenge(root, descriptor)
        specs = (LeaseSpec(LeaseLevel.CELL, descriptor.cell_id),)
        held = manager.acquire(
            specs,
            operation="INITIALIZE_M1_CELL",
            expected_challenge_sha256=challenge,
            challenge_callback=lambda: cls._bootstrap_challenge(root, descriptor),
            effectful=False,
        )
        temporary = contained_path(
            cells_root,
            f".partial-cell-{descriptor.cell_key_sha256}-{secrets.token_hex(16)}",
            label="partial M1 cell root",
        )
        guard.activate(
            held,
            expected_specs=specs,
            source_binding_sha256=descriptor.source_binding_sha256,
        )
        try:
            if os.path.lexists(final_root):
                raise PhysicalOnboardingM1Error("M1 cell concurrently appeared")
            temporary.mkdir(exist_ok=False)
            publication.write_new_file(
                temporary / "cell.json", canonical_bytes(descriptor.to_dict())
            )
            PhysicalOnboardingAttemptLedger.create(
                temporary / "attempts",
                publication,
                ledger_id=descriptor.attempt_ledger_id,
                cell_id=descriptor.cell_id,
                created_at_ns=descriptor.created_at_ns + 1,
            )
            PhysicalOnboardingQuarantineLedger.create(
                temporary / "quarantine",
                publication,
                ledger_id=descriptor.quarantine_ledger_id,
                cell_id=descriptor.cell_id,
                created_at_ns=descriptor.created_at_ns + 2,
            )
            publication.publish_new_directory(temporary, final_root)
            publication.sync_directory(cells_root)
        except Exception:
            cls._cleanup_partial_cell(temporary)
            raise
        finally:
            guard.deactivate()
            held.close()

    @staticmethod
    def _cleanup_partial_cell(root: Path) -> None:
        if not os.path.lexists(root) or root.is_symlink():
            return
        try:
            for ledger_name in ("attempts", "quarantine"):
                ledger = root / ledger_name
                events = ledger / "events"
                for filename in ("header.json", "head.json"):
                    path = ledger / filename
                    if path.is_file() and not path.is_symlink():
                        path.unlink()
                if events.is_dir() and not events.is_symlink():
                    events.rmdir()
                if ledger.is_dir() and not ledger.is_symlink():
                    ledger.rmdir()
            descriptor = root / "cell.json"
            if descriptor.is_file() and not descriptor.is_symlink():
                descriptor.unlink()
            root.rmdir()
        except OSError:
            # Unexpected contents are retained as reconciliation evidence.
            pass

    @staticmethod
    def _bootstrap_challenge(root: Path, descriptor: M1CellDescriptor) -> str:
        final = root / "cells" / f"cell-{descriptor.cell_key_sha256}"
        return canonical_sha256(
            {
                "operation": "INITIALIZE_M1_CELL",
                "cell_sha256": descriptor.cell_sha256,
                "destination_absent": not os.path.lexists(final),
                "source_binding_sha256": descriptor.source_binding_sha256,
                "durability_qualification_sha256": (
                    descriptor.durability_qualification_sha256
                ),
            }
        )

    def _session_path(self, session_id: str) -> Path:
        selected = _identifier(session_id, "session_id")
        return contained_path(
            self.deployment_root,
            f"onboarding-{selected}",
            label="V2 session root",
        )

    def _open_session(self, session_id: str) -> PhysicalOnboardingV2Session:
        selected = _identifier(session_id, "session_id")
        session = PhysicalOnboardingV2Session.open(
            safe_root(self._session_path(selected), label="V2 session root"),
            publication=self._publication,
        )
        header = session.snapshot().header
        if (
            header.session_id != selected
            or header.cell_id != self.cell.cell_id
            or header.source_binding_sha256 != self.source_binding_sha256
            or header.durability_qualification_sha256
            != self.qualification_anchor.report_sha256
        ):
            raise PhysicalOnboardingM1Error(
                "V2 session does not belong to this M1 runtime"
            )
        return session

    def _open_session_with_snapshot(
        self, session_id: str
    ) -> tuple[PhysicalOnboardingV2Session, V2SessionSnapshot]:
        """One fresh original read with the same exact runtime header joins.

        This result belongs only to this observation; it is not retained or
        reused across global-ledger and selected-session verification passes.
        """
        selected = _identifier(session_id, "session_id")
        session, snapshot = PhysicalOnboardingV2Session.open_with_snapshot(
            safe_root(self._session_path(selected), label="V2 session root"),
            publication=self._publication,
        )
        header = snapshot.header
        if (
            header.session_id != selected
            or header.cell_id != self.cell.cell_id
            or header.source_binding_sha256 != self.source_binding_sha256
            or header.durability_qualification_sha256
            != self.qualification_anchor.report_sha256
        ):
            raise PhysicalOnboardingM1Error(
                "V2 session does not belong to this M1 runtime"
            )
        return session, snapshot

    def create_session(
        self,
        session_id: str,
        *,
        created_at_ns: int | None = None,
        mode: str = "PHYSICAL_DIAGNOSTIC",
        workspace_source_sha256: str | None = None,
    ) -> M1RuntimeVerification:
        """Create one locked V2 session; no stage, attempt, or device action occurs."""

        selected = _identifier(session_id, "session_id")
        if type(mode) is not str or mode not in {"PHYSICAL_DIAGNOSTIC", "REHEARSAL"}:
            raise PhysicalOnboardingM1Error("unsupported M1 session mode")
        if mode == "REHEARSAL":
            from rocell.application.commissioning_m1_persistence import (
                rehearsal_source_binding,
            )

            if (
                workspace_source_sha256 is None
                or rehearsal_source_binding(workspace_source_sha256)
                != self.source_binding_sha256
            ):
                raise PhysicalOnboardingM1Error(
                    "rehearsal session requires its domain-separated workspace source"
                )
            if (
                re.fullmatch(r"wizard-rehearsal-[0-9a-f]{16}", self.cell.cell_id)
                is None
                or re.fullmatch(r"rehearsal-[0-9a-f]{32}", selected) is None
            ):
                raise PhysicalOnboardingM1Error(
                    "rehearsal session namespace is invalid"
                )
        # Reserve the new application domain without changing legacy physical
        # header serialization or accepting a rehearsal source as physical.
        if self.cell.cell_id.startswith(
            "wizard-physical-diagnostic-"
        ) or selected.startswith("physical-diagnostic-"):
            from rocell.application.commissioning_physical_persistence import (
                physical_diagnostic_source_binding,
            )

            if (
                mode != "PHYSICAL_DIAGNOSTIC"
                or re.fullmatch(
                    r"wizard-physical-diagnostic-[0-9a-f]{16}", self.cell.cell_id
                )
                is None
                or re.fullmatch(r"physical-diagnostic-[0-9a-f]{32}", selected) is None
                or workspace_source_sha256 is None
                or physical_diagnostic_source_binding(workspace_source_sha256)
                != self.source_binding_sha256
            ):
                raise PhysicalOnboardingM1Error(
                    "physical diagnostic session requires its separate namespace/source"
                )
        if self.cell.cell_id.startswith(
            "wizard-physical-camera-"
        ) or selected.startswith("physical-camera-"):
            from .commissioning_camera_persistence import physical_camera_source_binding

            if (
                mode != "PHYSICAL_DIAGNOSTIC"
                or re.fullmatch(
                    r"wizard-physical-camera-[0-9a-f]{16}", self.cell.cell_id
                )
                is None
                or re.fullmatch(r"physical-camera-[0-9a-f]{32}", selected) is None
                or workspace_source_sha256 is None
                or physical_camera_source_binding(workspace_source_sha256)
                != self.source_binding_sha256
            ):
                raise PhysicalOnboardingM1Error(
                    "camera acquisition session requires its separate namespace/source"
                )
        created = _timestamp(
            time.time_ns() if created_at_ns is None else created_at_ns,
            "created_at_ns",
        )
        # A new session must not provide a navigation path around unresolved
        # global evidence or a permanent quarantine latch.
        self._quarantine.assert_effects_allowed(self._attempts)
        expected = self._challenge_for_absent_session(selected)
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
        )
        held = self._leases.acquire(
            specs,
            operation="CREATE_V2_SESSION",
            expected_challenge_sha256=expected,
            challenge_callback=lambda: self._challenge_for_absent_session(selected),
            effectful=False,
        )
        self._guard.activate(
            held,
            expected_specs=specs,
            source_binding_sha256=self.source_binding_sha256,
        )
        try:
            # Re-evaluate admission while CELL is owned.  The pre-lock check is
            # useful for a quick diagnostic, but it cannot authorize creation:
            # another process may have committed unresolved or quarantined
            # evidence immediately before this process acquired the lease.
            self._quarantine.assert_effects_allowed(self._attempts)
            PhysicalOnboardingV2Session.create(
                self.deployment_root,
                session_id=selected,
                cell_id=self.cell.cell_id,
                source_binding_sha256=self.source_binding_sha256,
                created_at_ns=created,
                publication=self._publication,
                mode=mode,
            )
        finally:
            self._guard.deactivate()
            held.close()
        return self.verify(selected)

    def session_snapshot(self, session_id: str) -> V2SessionSnapshot:
        """Read a verified session projection without exposing mutable stores."""
        self.verify(session_id)
        return self._open_session(session_id).snapshot()

    @contextmanager
    def rehearsal_transaction(
        self,
        session_id: str,
        *,
        device_levels: tuple[LeaseLevel, ...] = (),
        expected_challenge_sha256: str | None = None,
    ) -> Iterator[Any]:
        """Own qualified OS leases around zero-hardware rehearsal storage only.

        The returned narrow transaction exposes no device/worker/executor API.
        It cannot be used with an existing physical-diagnostic session merely
        by renaming its directory or supplying rehearsal-looking UI metadata.
        """
        from rocell.application.commissioning_m1_persistence import (
            M1RehearsalTransaction,
        )

        selected = _identifier(session_id, "session_id")
        # Read the immutable session binding here. Full global verification is
        # immediately below and repeated after OS lease acquisition.
        snapshot = self._open_session(selected).snapshot()
        if (
            snapshot.header.mode != "REHEARSAL"
            or re.fullmatch(r"wizard-rehearsal-[0-9a-f]{16}", self.cell.cell_id) is None
        ):
            raise PhysicalOnboardingM1Error(
                "only explicit isolated REHEARSAL sessions admit this transaction"
            )
        if (
            type(device_levels) is not tuple
            or any(not isinstance(level, LeaseLevel) for level in device_levels)
            or device_levels
            not in {
                (),
                (LeaseLevel.CAMERA,),
                (LeaseLevel.ARM_CONTROLLER,),
                (LeaseLevel.CAMERA, LeaseLevel.ARM_CONTROLLER),
            }
        ):
            raise PhysicalOnboardingM1Error(
                "rehearsal device leases must be exact and ordered"
            )
        before = self.verify(selected)
        expected = (
            before.challenge_sha256
            if expected_challenge_sha256 is None
            else _digest(expected_challenge_sha256, "rehearsal challenge")
        )
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
            *(LeaseSpec(level, self.cell.cell_id) for level in device_levels),
        )
        held = self._leases.acquire(
            specs,
            operation="M1_REHEARSAL_TRANSACTION",
            expected_challenge_sha256=expected,
            challenge_callback=lambda: self.verify(selected).challenge_sha256,
            effectful=True,
        )
        transaction = None
        try:
            self._guard.activate(
                held,
                expected_specs=specs,
                source_binding_sha256=self.source_binding_sha256,
            )
            transaction = M1RehearsalTransaction(
                session=self._open_session(selected),
                attempts=self._attempts,
                quarantine=self._quarantine,
                publication=self._publication,
                cell_root=self._cell_root(self.deployment_root, self.cell),
                guard=self._guard,
                held=held,
                specs=specs,
                verification=lambda: self.verify(selected),
            )
            yield transaction
        finally:
            if transaction is not None:
                transaction.close_scope()
            self._guard.deactivate()
            held.close()

    @contextmanager
    def physical_diagnostic_transaction(
        self,
        session_id: str,
        *,
        expected_challenge_sha256: str | None = None,
    ) -> Iterator[Any]:
        """Own CELL→SESSION leases for the distinct physical NO_DEVICE_IO domain.

        This storage boundary neither owns device leases nor exposes device
        activation. Its immutable session/source may not be relabeled rehearsal.
        """
        from rocell.application.commissioning_physical_persistence import (
            M1PhysicalDiagnosticTransaction,
        )

        selected = _identifier(session_id, "session_id")
        snapshot = self._open_session(selected).snapshot()
        if (
            snapshot.header.mode != "PHYSICAL_DIAGNOSTIC"
            or re.fullmatch(
                r"wizard-physical-diagnostic-[0-9a-f]{16}", self.cell.cell_id
            )
            is None
            or re.fullmatch(r"physical-diagnostic-[0-9a-f]{32}", selected) is None
        ):
            raise PhysicalOnboardingM1Error(
                "only separate PHYSICAL_DIAGNOSTIC sessions admit this transaction"
            )
        before = self.verify(selected)
        expected = (
            before.challenge_sha256
            if expected_challenge_sha256 is None
            else _digest(expected_challenge_sha256, "physical diagnostic challenge")
        )
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
        )
        held = self._leases.acquire(
            specs,
            operation="M1_PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO",
            expected_challenge_sha256=expected,
            challenge_callback=lambda: self.verify(selected).challenge_sha256,
            effectful=True,
        )
        transaction = None
        try:
            self._guard.activate(
                held,
                expected_specs=specs,
                source_binding_sha256=self.source_binding_sha256,
            )
            transaction = M1PhysicalDiagnosticTransaction(
                session=self._open_session(selected),
                attempts=self._attempts,
                quarantine=self._quarantine,
                publication=self._publication,
                cell_root=self._cell_root(self.deployment_root, self.cell),
                guard=self._guard,
                held=held,
                specs=specs,
                verification=lambda: self.verify(selected),
            )
            yield transaction
        finally:
            if transaction is not None:
                transaction.close_scope()
            self._guard.deactivate()
            held.close()

    @contextmanager
    def physical_camera_transaction(
        self,
        session_id: str,
        *,
        device_levels: tuple[LeaseLevel, ...] = (),
        expected_challenge_sha256: str | None = None,
    ) -> Iterator[Any]:
        """Camera-only qualified storage ownership; never native qualification.

        Empty device levels are for stage/evidence storage. Acquisition requires
        the CAMERA lease as well. Neither form accepts an ARM_CONTROLLER lease.
        The existing source-only and rehearsal transactions remain separate.
        """
        from .commissioning_camera_persistence import M1PhysicalCameraTransaction

        selected = _identifier(session_id, "session_id")
        snapshot = self._open_session(selected).snapshot()
        if (
            snapshot.header.mode != "PHYSICAL_DIAGNOSTIC"
            or re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", self.cell.cell_id)
            is None
            or re.fullmatch(r"physical-camera-[0-9a-f]{32}", selected) is None
            or type(device_levels) is not tuple
            or device_levels not in ((), (LeaseLevel.CAMERA,))
            or any(type(level) is not LeaseLevel for level in device_levels)
        ):
            raise PhysicalOnboardingM1Error("exact camera-only domain/leases required")
        before = self.verify(selected)
        expected = (
            before.challenge_sha256
            if expected_challenge_sha256 is None
            else _digest(expected_challenge_sha256, "physical camera challenge")
        )
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
            *(LeaseSpec(level, self.cell.cell_id) for level in device_levels),
        )
        held = self._leases.acquire(
            specs,
            operation="M1_PHYSICAL_CAMERA_ACQUISITION",
            expected_challenge_sha256=expected,
            challenge_callback=lambda: self.verify(selected).challenge_sha256,
            effectful=True,
        )
        transaction = None
        try:
            self._guard.activate(
                held,
                expected_specs=specs,
                source_binding_sha256=self.source_binding_sha256,
            )
            transaction = M1PhysicalCameraTransaction(
                session=self._open_session(selected),
                attempts=self._attempts,
                quarantine=self._quarantine,
                publication=self._publication,
                cell_root=self._cell_root(self.deployment_root, self.cell),
                guard=self._guard,
                held=held,
                specs=specs,
                verification=lambda: self.verify(selected),
                _fresh_snapshot_verification=lambda: self._verify_with_snapshot(
                    selected
                ),
            )
            yield transaction
        finally:
            if transaction is not None:
                transaction.close_scope()
            self._guard.deactivate()
            held.close()

    @contextmanager
    def physical_usb_identity_transaction(
        self,
        session_id: str,
        *,
        device_levels: tuple[LeaseLevel, ...] = (),
        expected_challenge_sha256: str | None = None,
    ) -> Iterator[Any]:
        """Purpose-specific USB records under the original camera M1 ownership.

        Stage-only scopes read originals; query scopes additionally own CAMERA.
        This entry point does not approve facts, consume a permit or open a hub.
        """
        from .commissioning_usb_identity_persistence import (
            M1PhysicalUsbIdentityTransaction,
        )

        selected = _identifier(session_id, "session_id")
        _, snapshot = self._open_session_with_snapshot(selected)
        if (
            snapshot.header.mode != "PHYSICAL_DIAGNOSTIC"
            or re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", self.cell.cell_id)
            is None
            or re.fullmatch(r"physical-camera-[0-9a-f]{32}", selected) is None
            or type(device_levels) is not tuple
            or device_levels not in ((), (LeaseLevel.CAMERA,))
            or any(type(level) is not LeaseLevel for level in device_levels)
        ):
            raise PhysicalOnboardingM1Error(
                "exact USB camera-family domain/leases required"
            )
        before = self.verify(selected)
        expected = (
            before.challenge_sha256
            if expected_challenge_sha256 is None
            else _digest(expected_challenge_sha256, "physical USB challenge")
        )
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
            *(LeaseSpec(level, self.cell.cell_id) for level in device_levels),
        )
        held = self._leases.acquire(
            specs,
            operation="M1_PHYSICAL_USB_IDENTITY",
            expected_challenge_sha256=expected,
            challenge_callback=lambda: self.verify(selected).challenge_sha256,
            effectful=True,
        )
        transaction = None
        try:
            self._guard.activate(
                held,
                expected_specs=specs,
                source_binding_sha256=self.source_binding_sha256,
            )
            # Reopen freshly under the acquired leases. The returned session
            # carries no cached snapshot; both transaction constructors still
            # perform their own current original checks below.
            session, _ = self._open_session_with_snapshot(selected)
            transaction = M1PhysicalUsbIdentityTransaction(
                session=session,
                attempts=self._attempts,
                quarantine=self._quarantine,
                publication=self._publication,
                cell_root=self._cell_root(self.deployment_root, self.cell),
                guard=self._guard,
                held=held,
                specs=specs,
                verification=lambda: self.verify(selected),
                _fresh_snapshot_verification=lambda: self._verify_with_snapshot(
                    selected
                ),
            )
            yield transaction
        finally:
            if transaction is not None:
                transaction.close_scope()
            self._guard.deactivate()
            held.close()

    @contextmanager
    def physical_usb_presence_transaction(
        self,
        session_id: str,
        *,
        device_levels: tuple[LeaseLevel, ...] = (),
        expected_challenge_sha256: str | None = None,
    ) -> Iterator[Any]:
        """Separate presence records under original camera-family M1 ownership.

        This acquires storage leases, not an observation permit. No alternate
        endpoint, worker, ARM lease or automatic retry is accepted here.
        """
        from .commissioning_usb_presence_persistence import (
            M1PhysicalUsbPresenceTransaction,
        )

        selected = _identifier(session_id, "session_id")
        snapshot = self._open_session(selected).snapshot()
        if (
            snapshot.header.mode != "PHYSICAL_DIAGNOSTIC"
            or re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", self.cell.cell_id)
            is None
            or re.fullmatch(r"physical-camera-[0-9a-f]{32}", selected) is None
            or type(device_levels) is not tuple
            or device_levels not in ((), (LeaseLevel.CAMERA,))
            or any(type(level) is not LeaseLevel for level in device_levels)
        ):
            raise PhysicalOnboardingM1Error(
                "exact USB presence camera-family leases required"
            )
        before = self.verify(selected)
        expected = (
            before.challenge_sha256
            if expected_challenge_sha256 is None
            else _digest(expected_challenge_sha256, "physical USB presence challenge")
        )
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
            *(LeaseSpec(level, self.cell.cell_id) for level in device_levels),
        )
        held = self._leases.acquire(
            specs,
            operation="M1_PHYSICAL_USB_PRESENCE",
            expected_challenge_sha256=expected,
            challenge_callback=lambda: self.verify(selected).challenge_sha256,
            effectful=True,
        )
        transaction = None
        try:
            self._guard.activate(
                held,
                expected_specs=specs,
                source_binding_sha256=self.source_binding_sha256,
            )
            transaction = M1PhysicalUsbPresenceTransaction(
                session=self._open_session(selected),
                attempts=self._attempts,
                quarantine=self._quarantine,
                publication=self._publication,
                cell_root=self._cell_root(self.deployment_root, self.cell),
                guard=self._guard,
                held=held,
                specs=specs,
                verification=lambda: self.verify(selected),
            )
            yield transaction
        finally:
            if transaction is not None:
                transaction.close_scope()
            self._guard.deactivate()
            held.close()

    def recover_startup(
        self,
        session_id: str,
        *,
        occurred_at_ns: int | None = None,
    ) -> tuple[StartupRecoveryReport, M1RuntimeVerification]:
        """Seal committed unresolved evidence; never replay its operation."""

        selected = _identifier(session_id, "session_id")
        occurred = _timestamp(
            time.time_ns() if occurred_at_ns is None else occurred_at_ns,
            "occurred_at_ns",
        )
        before = self.verify(selected)
        self._require_recovery_session(selected)
        specs = (
            LeaseSpec(LeaseLevel.CELL, self.cell.cell_id),
            LeaseSpec(LeaseLevel.SESSION, selected),
        )
        held = self._leases.acquire(
            specs,
            operation="RECOVER_M1_STARTUP",
            expected_challenge_sha256=before.challenge_sha256,
            challenge_callback=lambda: self.verify(selected).challenge_sha256,
            effectful=False,
        )
        self._guard.activate(
            held,
            expected_specs=specs,
            source_binding_sha256=self.source_binding_sha256,
        )
        try:
            # Recovery mutates a cell-global ledger, but the attempt itself is
            # session-bound.  Recheck under CELL ownership so a caller cannot
            # name session B, hold B's lease, and recover session A's attempt.
            self._require_recovery_session(selected)
            report = recover_physical_onboarding_startup(
                self._attempts,
                self._quarantine,
                occurred_at_ns=occurred,
            )
        finally:
            self._guard.deactivate()
            held.close()
        return report, self.verify(selected)

    def _require_recovery_session(self, session_id: str) -> None:
        attempts, quarantine = self._global_snapshots()
        pending: list[AttemptEvent] = list(attempts.unresolved_events)
        pending.extend(
            event
            for event in attempts.uncertain_events
            if quarantine.event_for_attempt(event.attempt_id) is None
        )
        wrong_sessions = sorted(
            {event.session_id for event in pending if event.session_id != session_id}
        )
        if wrong_sessions:
            raise PhysicalOnboardingM1Error(
                "startup recovery requires the lease for the attempt's exact "
                f"session; requested={session_id!r}, required={wrong_sessions!r}"
            )

    def _challenge_for_absent_session(self, session_id: str) -> str:
        path = self._session_path(session_id)
        if os.path.lexists(path):
            raise PhysicalOnboardingM1Error("V2 session already exists")
        attempts, quarantine = self._global_snapshots()
        return self._challenge_document(
            attempts,
            quarantine,
            session_id=session_id,
            session=None,
        )["challenge_sha256"]

    def _global_snapshots(
        self,
    ) -> tuple[AttemptLedgerSnapshot, QuarantineLedgerSnapshot]:
        # Double-collect append-only heads.  Matching nonzero hashes prove the
        # exact cross-validated pair was stable across the observation window
        # (coordinated local rollback remains outside M1's threat model).
        last_transient: Exception | None = None
        for _ in range(4):
            try:
                first_attempts, first_quarantine = self._quarantine.verified_snapshots(
                    self._attempts
                )
                attempts, quarantine = self._quarantine.verified_snapshots(
                    self._attempts
                )
            except (
                PhysicalOnboardingAttemptError,
                PhysicalOnboardingQuarantineError,
            ) as exc:
                # A writer can advance the attempt head between the attempt and
                # quarantine reads, briefly making an otherwise valid pair look
                # incomplete.  Retry only the read; never retry a mutation.
                last_transient = exc
                continue
            if (
                first_attempts.head_sha256 == attempts.head_sha256
                and first_quarantine.head_sha256 == quarantine.head_sha256
            ):
                self._validate_global_bindings(attempts, quarantine)
                return attempts, quarantine
        raise PhysicalOnboardingM1Error(
            "cell-global ledgers changed continuously during verification"
        ) from last_transient

    def _validate_global_bindings(
        self,
        attempts: AttemptLedgerSnapshot,
        quarantine: QuarantineLedgerSnapshot,
    ) -> None:
        if (
            attempts.ledger_id != self.cell.attempt_ledger_id
            or quarantine.ledger_id != self.cell.quarantine_ledger_id
            or attempts.cell_id != self.cell.cell_id
            or quarantine.cell_id != self.cell.cell_id
            or attempts.durability_qualification_sha256
            != self.qualification_anchor.report_sha256
        ):
            raise PhysicalOnboardingM1Error(
                "cell-global ledgers do not match the immutable cell descriptor"
            )

        sessions: dict[str, V2SessionSnapshot] = {}
        for event in attempts.events:
            if (
                event.source_binding_sha256 != self.source_binding_sha256
                or event.stage_plan_sha256 != STAGE_PLAN_SHA256
            ):
                raise PhysicalOnboardingM1Error(
                    "attempt provenance differs from the active source or stage plan"
                )
            if event.session_id not in sessions:
                _, sessions[event.session_id] = self._open_session_with_snapshot(
                    event.session_id
                )
            session = sessions[event.session_id]
            if event.intent_at_ns < session.header.created_at_ns:
                raise PhysicalOnboardingM1Error(
                    "attempt intent predates its bound V2 session"
                )

        # An unresolved/uncertain attempt is the state on which startup and
        # admission decisions act.  Its latest binding must still describe the
        # current committed session/evidence state; historical terminal
        # attempts may legitimately precede later reviewed session mutations.
        for event in (*attempts.unresolved_events, *attempts.uncertain_events):
            session = sessions[event.session_id]
            evidence_hash = canonical_sha256(
                [item.to_dict() for item in session.evidence]
            )
            if (
                event.session_journal_head_sha256 != session.head.head_sha256
                or event.evidence_inventory_sha256 != evidence_hash
            ):
                raise PhysicalOnboardingM1Error(
                    "active attempt no longer binds the current V2 session state"
                )

    def _challenge_document(
        self,
        attempts: AttemptLedgerSnapshot,
        quarantine: QuarantineLedgerSnapshot,
        *,
        session_id: str | None,
        session: V2SessionSnapshot | None,
    ) -> dict[str, Any]:
        evidence_hash = (
            _ZERO_SHA256
            if session is None
            else canonical_sha256([item.to_dict() for item in session.evidence])
        )
        core: dict[str, object] = {
            "schema": "rocell.physical_onboarding_m1_challenge.v1",
            "cell_id": self.cell.cell_id,
            "cell_sha256": self.cell.cell_sha256,
            "session_id": session_id,
            "session_header_sha256": (
                _ZERO_SHA256 if session is None else session.header.header_sha256
            ),
            "session_head_sha256": (
                _ZERO_SHA256 if session is None else session.head.head_sha256
            ),
            "evidence_inventory_sha256": evidence_hash,
            "attempt_head_sha256": attempts.head_sha256,
            "quarantine_head_sha256": quarantine.head_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "stage_plan_sha256": STAGE_PLAN_SHA256,
            "durability_qualification_sha256": (
                self.qualification_anchor.report_sha256
            ),
            "runtime_activation": False,
            "physical_authority": False,
        }
        return {**core, "challenge_sha256": canonical_sha256(core)}

    def verify(self, session_id: str | None = None) -> M1RuntimeVerification:
        """Verify all requested durable state and return zero-I/O status."""

        return self._verify_with_snapshot(session_id)[1]

    def _verify_with_snapshot(
        self, session_id: str | None = None
    ) -> tuple[V2SessionSnapshot | None, M1RuntimeVerification]:
        """One fresh verification and its exact selected original observation.

        The global/sibling audit and selected-session read remain independent.
        This pair is local to this call, never cached between admission boundaries.
        """

        attempts, quarantine = self._global_snapshots()
        selected_session_id: str | None = None
        session: V2SessionSnapshot | None = None
        if session_id is not None:
            selected_session_id = _identifier(session_id, "session_id")
            _, session = self._open_session_with_snapshot(selected_session_id)
        lease_specs = [LeaseSpec(LeaseLevel.CELL, self.cell.cell_id)]
        if selected_session_id is not None:
            lease_specs.append(LeaseSpec(LeaseLevel.SESSION, selected_session_id))
        active_lease_owners = tuple(
            f"{spec.level.name}:{spec.resource_id}:{owner.owner_sha256}"
            for spec in lease_specs
            if (owner := self._leases.prior_owner(spec)) is not None
            and owner.state is LeaseOwnerState.ACTIVE
        )
        challenge = self._challenge_document(
            attempts,
            quarantine,
            session_id=selected_session_id,
            session=session,
        )
        evidence_hash = challenge["evidence_inventory_sha256"]
        assert isinstance(evidence_hash, str)
        quarantined = quarantine.latched
        verified = M1RuntimeVerification(
            cell=self.cell,
            qualification_anchor_sha256=self.qualification_anchor.report_sha256,
            startup_qualification_sha256=self.startup_report.report_sha256,
            attempt_head_sha256=attempts.head_sha256,
            attempt_event_count=len(attempts.events),
            unresolved_attempt_ids=tuple(
                event.attempt_id for event in attempts.unresolved_events
            ),
            uncertain_attempt_ids=tuple(
                event.attempt_id for event in attempts.uncertain_events
            ),
            quarantine_head_sha256=quarantine.head_sha256,
            quarantine_count=len(quarantine.events),
            quarantined=quarantined,
            session_id=selected_session_id,
            session_header_sha256=(
                _ZERO_SHA256 if session is None else session.header.header_sha256
            ),
            session_head_sha256=(
                _ZERO_SHA256 if session is None else session.head.head_sha256
            ),
            session_reconciliation_required=(
                False if session is None else session.reconciliation_required
            ),
            active_lease_owners=active_lease_owners,
            evidence_inventory_sha256=evidence_hash,
            challenge_sha256=challenge["challenge_sha256"],
        )
        return session, verified


__all__ = [
    "DURABILITY_ANCHOR_FILENAME",
    "M1_CELL_SCHEMA",
    "M1_QUARANTINED_STATUS",
    "M1_RECONCILIATION_STATUS",
    "M1_RUNTIME_SCHEMA",
    "M1_STATUS",
    "M1CellDescriptor",
    "M1RuntimeVerification",
    "PhysicalOnboardingM1Error",
    "PhysicalOnboardingM1Runtime",
]
