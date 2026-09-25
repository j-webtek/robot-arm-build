"""Qualified physical-diagnostic storage, with device I/O independently held.

This is not a renamed rehearsal adapter. It uses a separate source domain,
immutable PHYSICAL_DIAGNOSTIC session header and record codec. Its current
closed composition admits source/document preflight only: no device leases,
energization envelopes, opens, reads, writes, frames or observed power state.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import re
from typing import Any, TYPE_CHECKING

from rocell.application.cell_commissioning_coordinator import (
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    ExactOperationPermit,
    RegisteredActionRequest,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    _HASH,
    _M1AdmissionFacts,
    _M1CoordinatorTransaction,
    _PHYSICAL_NO_IO_DOMAIN,
    _decode_domain_permit,
    _sha256,
)
from rocell.application.physical_onboarding_attempts import canonical_json_bytes
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2SessionSnapshot

if TYPE_CHECKING:
    from rocell.application.physical_onboarding_m1 import (
        M1RuntimeVerification,
        PhysicalOnboardingM1Runtime,
    )


PHYSICAL_DIAGNOSTIC_SOURCE_SCHEMA = "rocell.physical_diagnostic_source.v1"
PHYSICAL_DIAGNOSTIC_RECORD_SCHEMA = _PHYSICAL_NO_IO_DOMAIN.record_schema


def physical_diagnostic_source_binding(workspace_source_sha256: str) -> str:
    """Bind actual selected source bytes to this NO_DEVICE_IO storage domain."""
    if (
        type(workspace_source_sha256) is not str
        or _HASH.fullmatch(workspace_source_sha256) is None
        or workspace_source_sha256 == "0" * 64
    ):
        raise M1CommissioningPersistenceError(
            "workspace source must be a nonzero SHA-256"
        )
    return _sha256(
        canonical_json_bytes(
            {
                "schema": PHYSICAL_DIAGNOSTIC_SOURCE_SCHEMA,
                "composition": PHYSICAL_DIAGNOSTIC_COMPOSITION,
                "workspace_source_sha256": workspace_source_sha256,
            }
        )
    )


def decode_physical_diagnostic_permit(value: object) -> ExactOperationPermit:
    """Strict audited-data reconstruction only; never redeem on restart."""
    return _decode_domain_permit(value, _PHYSICAL_NO_IO_DOMAIN)


@dataclass(frozen=True, slots=True)
class PhysicalDiagnosticAdmissionFacts(_M1AdmissionFacts):
    """Source/evidence-derived server facts, not browser-authored proof hashes."""

    def __post_init__(self) -> None:
        # Explicit base call works with dataclass(slots=True) on Python 3.10.
        _M1AdmissionFacts.__post_init__(self)
        if self.envelope is not None:
            raise M1CommissioningPersistenceError(
                "NO_DEVICE_IO physical preflight cannot admit an energy envelope"
            )


PhysicalDiagnosticFactsProvider = Callable[
    [RegisteredActionRequest, V2SessionSnapshot], PhysicalDiagnosticAdmissionFacts
]


class M1PhysicalDiagnosticTransaction(_M1CoordinatorTransaction):
    """M1-owned CELL→SESSION transaction; no raw mutable stores are public."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            **kwargs,
            domain=_PHYSICAL_NO_IO_DOMAIN,
            facts_type=PhysicalDiagnosticAdmissionFacts,
        )
        if self.held_leases != (
            LeaseSpec(LeaseLevel.CELL, self.snapshot().header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, self.snapshot().header.session_id),
        ):
            raise M1CommissioningPersistenceError(
                "physical preflight accepts CELL and SESSION storage leases only"
            )


class M1PhysicalDiagnosticPersistence:
    """Concrete qualified persistence for physical-source preflight, not devices."""

    composition = PHYSICAL_DIAGNOSTIC_COMPOSITION

    def __init__(
        self,
        runtime: "PhysicalOnboardingM1Runtime",
        *,
        workspace_source_sha256: str,
        admission_facts: PhysicalDiagnosticFactsProvider,
    ) -> None:
        from rocell.application.physical_onboarding_m1 import (
            PhysicalOnboardingM1Runtime,
        )

        if (
            type(runtime) is not PhysicalOnboardingM1Runtime
            or re.fullmatch(_PHYSICAL_NO_IO_DOMAIN.cell_pattern, runtime.cell.cell_id)
            is None
            or runtime.source_binding_sha256
            != physical_diagnostic_source_binding(workspace_source_sha256)
        ):
            raise M1CommissioningPersistenceError(
                "physical preflight requires its separate actual M1 source/cell domain"
            )
        if not callable(admission_facts):
            raise M1CommissioningPersistenceError(
                "server-pinned physical admission facts callback is required"
            )
        self._runtime, self._admission_facts = runtime, admission_facts

    def snapshot(self, session_id: str) -> V2SessionSnapshot:
        if (
            type(session_id) is not str
            or re.fullmatch(_PHYSICAL_NO_IO_DOMAIN.session_pattern, session_id) is None
        ):
            raise M1CommissioningPersistenceError(
                "wrong physical diagnostic session namespace"
            )
        snapshot = self._runtime.session_snapshot(session_id)
        if snapshot.header.mode != "PHYSICAL_DIAGNOSTIC":
            raise M1CommissioningPersistenceError(
                "rehearsal sessions cannot become physical diagnostics"
            )
        return snapshot

    def verification(self, session_id: str) -> "M1RuntimeVerification":
        self.snapshot(session_id)
        return self._runtime.verify(session_id)

    @contextmanager
    def stage_transaction(
        self, session_id: str, *, expected_challenge_sha256: str
    ) -> Iterator[M1PhysicalDiagnosticTransaction]:
        with self._runtime.physical_diagnostic_transaction(
            session_id, expected_challenge_sha256=expected_challenge_sha256
        ) as transaction:
            transaction._audit_records()
            yield transaction

    @contextmanager
    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[M1PhysicalDiagnosticTransaction]:
        if (
            type(leases) is not tuple
            or len(leases) != 2
            or any(type(spec) is not LeaseSpec for spec in leases)
            or leases[0] != LeaseSpec(LeaseLevel.CELL, self._runtime.cell.cell_id)
            or leases[1].level is not LeaseLevel.SESSION
        ):
            raise M1CommissioningPersistenceError(
                "physical diagnostic coordinator accepts exact CELL→SESSION leases only"
            )
        with self._runtime.physical_diagnostic_transaction(
            leases[1].resource_id
        ) as transaction:
            if transaction.held_leases != leases:
                raise M1CommissioningPersistenceError(
                    "actual physical lease set differs"
                )
            transaction._facts_provider = self._admission_facts
            yield transaction
