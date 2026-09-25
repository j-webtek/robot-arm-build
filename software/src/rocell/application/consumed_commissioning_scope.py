"""Scoped acknowledgement plus repeat read-only checks of one consumed attempt.

Only the coordinator creates this object after durable EFFECT_ARMED under its
original leases. It issues no permit and launches no process. Revalidation is
separate from the transaction's one-use acknowledgement; neither refreshes TTL.
"""

from __future__ import annotations

from dataclasses import asdict
from threading import Event, Lock
from typing import Callable, cast

from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
    CommissioningTransaction,
    ExactOperationPermit,
)
from rocell.application.physical_onboarding_attempts import canonical_json_bytes
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec


class ConsumedCommissioningScope:
    """One acknowledgement, at most eight checks, invalid outside worker scope.

    This is an internal coordinator capability, not an authorization serializer
    or a browser API. The real transaction independently checks committed armed
    evidence, lease ownership and current immutable facts on every revalidation.
    Retaining this object across a return, exception or restart does not retain
    authority. Caller-visible permit projections never expose the stored object.
    """

    def __init__(
        self,
        permit: ExactOperationPermit,
        *,
        transaction: CommissioningTransaction,
        deadline_ns: int,
        cancellation: Event,
        monotonic_ns: Callable[[], int],
    ) -> None:
        if type(permit) is not ExactOperationPermit or not isinstance(
            cancellation, Event
        ):
            raise CommissioningCoordinatorError("exact consumed scope inputs required")
        if (
            type(deadline_ns) is not int
            or not permit.issued_at_ns < deadline_ns <= permit.expires_at_ns
            or (
                permit.envelope is not None
                and deadline_ns > permit.envelope.expires_at_ns
            )
            or not callable(monotonic_ns)
            or not callable(getattr(transaction, "revalidate_consumed_permit", None))
        ):
            raise CommissioningCoordinatorError(
                "consumed scope needs original bounded lifetime and revalidation"
            )
        self._permit = permit
        self._bytes = canonical_json_bytes(asdict(permit))
        self._transaction = transaction
        self._deadline = deadline_ns
        self._cancel = cancellation
        self._clock = monotonic_ns
        self._active = True
        self._failed = False
        self._completion_failure: BaseException | None = None
        self._ack_attempted = self._acknowledged = False
        self._checks = 0
        self._last_now = -1
        self._lock = Lock()
        self._leases = (
            LeaseSpec(LeaseLevel.CELL, permit.request.cell_id),
            LeaseSpec(LeaseLevel.SESSION, permit.request.session_id),
            *(
                LeaseSpec(level, permit.request.cell_id)
                for level in permit.registration.resources
            ),
        )

    def _require_live(self, exact: ExactOperationPermit) -> None:
        if (
            not self._active
            or self._failed
            or type(exact) is not ExactOperationPermit
            or canonical_json_bytes(asdict(exact)) != self._bytes
            or canonical_json_bytes(asdict(self._permit)) != self._bytes
            or self._transaction.held_leases != self._leases
            or self._cancel.is_set()
        ):
            raise CommissioningCoordinatorError(
                "consumed scope binding/lease/liveness refused"
            )
        now = self._clock()
        if (
            type(now) is not int
            or now < self._last_now
            or not self._permit.issued_at_ns <= now < self._deadline
        ):
            raise CommissioningCoordinatorError(
                "consumed scope original deadline expired or clock regressed"
            )
        self._last_now = now

    def _enter(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise CommissioningCoordinatorError(
                "consumed scope concurrent/reentrant use refused"
            )

    def acknowledge(self, exact: ExactOperationPermit) -> None:
        """One read-verified acknowledgement; no second consumption or retry."""
        self._enter()
        try:
            self._require_live(exact)
            if self._ack_attempted:
                raise CommissioningCoordinatorError(
                    "consumed scope acknowledgement already attempted"
                )
            self._ack_attempted = True
            acknowledgement = cast(
                Callable[[ExactOperationPermit], object],
                self._transaction.assert_consumed_permit,
            )(exact)
            if acknowledgement is not None:
                raise CommissioningCoordinatorError(
                    "consumed acknowledgement must return None"
                )
            self._require_live(exact)
            self._acknowledged = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._lock.release()

    def revalidate(self, exact: ExactOperationPermit) -> None:
        """Check current committed authority without issuing/renewing a permit."""
        self._enter()
        try:
            self._require_live(exact)
            if not self._acknowledged or self._checks >= 8:
                raise CommissioningCoordinatorError(
                    "consumed revalidation requires acknowledgement and remaining check budget"
                )
            self._checks += 1
            revalidation = cast(
                Callable[[ExactOperationPermit], object],
                self._transaction.revalidate_consumed_permit,
            )(exact)
            if revalidation is not None:
                raise CommissioningCoordinatorError(
                    "consumed revalidation must return None"
                )
            self._require_live(exact)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._lock.release()

    def require_completed_checks(self) -> None:
        """Coordinator checks before accepting the worker's retained evidence."""
        self._enter()
        try:
            if self._completion_failure is not None:
                raise self._completion_failure
            self._require_live(self._permit)
            if not self._acknowledged or not self._checks:
                raise CommissioningCoordinatorError(
                    "scoped worker omitted acknowledgement or live revalidation"
                )
        finally:
            self._lock.release()

    def reject_completed_context(self, failure: BaseException) -> None:
        """Revoke and hand a final error back while the worker returns evidence.

        This refusal-only channel cannot grant or renew permission. In particular,
        a late KeyboardInterrupt can be propagated by the core *after* retaining
        returned diagnostics and sealing uncertainty, rather than losing either.
        The exception remains process-local and is never a serialized credential.
        """
        self._enter()
        try:
            if (
                not isinstance(failure, BaseException)
                or not self._active
                or not self._acknowledged
                or self._completion_failure is not None
            ):
                raise CommissioningCoordinatorError(
                    "completion rejection requires one active acknowledged scope"
                )
            self._completion_failure = failure
            self._failed = True
            self._active = False
        finally:
            self._lock.release()

    def close_scope(self) -> None:
        # Revocation is immediate even if a callback is still running; its
        # mandatory post-call liveness check observes this closure.
        self._active = False
