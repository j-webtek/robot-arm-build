"""One real rehearsal lease window for preflight, prepare and execute.

No admission snapshot, source proof or energy envelope is cached here. The
existing core and exact M1 transaction perform every fresh read/write. Only the
redundant release/reacquire cycles are removed for the two existing incapable
feedback actions. Worker selection, admission and all original budgets remain
the caller/coordinator's responsibility; this scope cannot switch between lanes.
The second coordinator context releases the real lease before it exits so core
cleanup handling still observes failures after a durable result.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import asdict
import sys
from threading import RLock, get_ident
from typing import Any, Iterator, Literal, cast

from .cell_commissioning_coordinator import (
    CommissioningTransaction,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    RegisteredActionRequest,
)
from .commissioning_m1_persistence import (
    M1CommissioningPersistence,
    M1RehearsalTransaction,
)
from .physical_onboarding_attempts import canonical_json_bytes
from .physical_onboarding_leases import LeaseLevel, LeaseSpec

# Retain the original name for existing owned-lane callers. This is a closed
# source-owned set, not a registration extension point or browser action input.
ACTION_ID = "rehearsal-owned-arm-feedback"
ACTION_IDS = frozenset({"rehearsal-arm-feedback", ACTION_ID})
_FORWARDED = frozenset(
    {
        "begin_intent",
        "consume_permit",
        "assert_consumed_permit",
        "revalidate_consumed_permit",
        "retain_campaign_evidence",
        "transition",
        "retain_result",
        "seal_uncertain",
    }
)


class ScopedRehearsalDispatchError(RuntimeError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ScopedRehearsalDispatchError(code)


def _request_bytes(request: RegisteredActionRequest) -> bytes:
    _require(
        type(request) is RegisteredActionRequest, "EXACT_REHEARSAL_REQUEST_REQUIRED"
    )
    request.__post_init__()
    return canonical_json_bytes(asdict(request))


class _DispatchTransaction:
    """Only the core protocol is forwarded, only during its current context."""

    def __init__(self, window: ScopedRehearsalDispatch, phase: int) -> None:
        self._window, self._phase = window, phase

    def _transaction(self, *, effect: bool = False) -> M1RehearsalTransaction:
        self._window._check_phase(self._phase)
        _require(not effect or self._phase == 2, "PREPARE_CANNOT_MUTATE_M1")
        assert self._window._transaction is not None
        return self._window._transaction

    @property
    def held_leases(self) -> tuple[LeaseSpec, ...]:
        return self._transaction().held_leases

    def read_admission(self, request: RegisteredActionRequest) -> Any:
        self._window._check_request(request)
        return self._transaction().read_admission(request)

    def read_envelope(self, request: RegisteredActionRequest) -> Any:
        self._window._check_request(request)
        return self._transaction().read_envelope(request)

    def __getattr__(self, name: str) -> Any:
        if name not in _FORWARDED:
            raise AttributeError(name)

        def forward(*args: Any, **kwargs: Any) -> Any:
            transaction = self._transaction(effect=True)
            for value in (*args, *kwargs.values()):
                if type(value) is ExactOperationPermit:
                    self._window._check_request(value.request)
            return getattr(transaction, name)(*args, **kwargs)

        return forward


class ScopedRehearsalDispatch:
    """Inert one-use adapter. A bound request gets prepare then execute, once.

    This internal application scope is not a browser-controlled transaction or
    physical persistence facade. Preflight receives the actual M1 object; the
    trusted caller must not retain/use it outside its preflight role. Coordinator
    proxies additionally reject out-of-context, substituted and phase-one writes.
    """

    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        *,
        persistence: M1CommissioningPersistence,
        leases: tuple[LeaseSpec, ...],
        request: RegisteredActionRequest,
    ) -> None:
        _require(
            type(persistence) is M1CommissioningPersistence
            and persistence.composition == INCAPABLE_COMPOSITION,
            "EXACT_REHEARSAL_M1_REQUIRED",
        )
        request_bytes = _request_bytes(request)
        _require(
            request.action_id in ACTION_IDS, "CLOSED_REHEARSAL_FEEDBACK_ACTION_REQUIRED"
        )
        expected = (
            LeaseSpec(LeaseLevel.CELL, request.cell_id),
            LeaseSpec(LeaseLevel.SESSION, request.session_id),
            LeaseSpec(LeaseLevel.ARM_CONTROLLER, request.cell_id),
        )
        _require(
            type(leases) is tuple
            and leases == expected
            and all(type(spec) is LeaseSpec for spec in leases),
            "EXACT_ARM_LEASES_REQUIRED",
        )
        self._persistence, self._leases = persistence, leases
        self._provisional, self._provisional_bytes = request, request_bytes
        self._bound: bytes | None = None
        self._transaction: M1RehearsalTransaction | None = None
        self._stack: ExitStack | None = None
        self._entered = self._closed = self._busy = False
        self._uses = 0
        self._thread: int | None = None
        self._lock = RLock()
        self._cleanup_error: BaseException | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entered": self._entered,
                "closed": self._closed,
                "coordinator_contexts_used": self._uses,
                "bound_request": self._bound is not None,
                "cleanup_uncertain": self._cleanup_error is not None,
                "physical_authority": False,
                "envelope_renewed": False,
            }

    def _live(self) -> None:
        _require(
            self._entered
            and not self._closed
            and self._thread == get_ident()
            and self._transaction is not None,
            "REHEARSAL_WINDOW_NOT_LIVE",
        )
        _require(
            _request_bytes(self._provisional) == self._provisional_bytes,
            "PROVISIONAL_REQUEST_CHANGED",
        )

    def __enter__(self) -> ScopedRehearsalDispatch:
        with self._lock:
            _require(
                not self._entered and not self._closed, "REHEARSAL_WINDOW_ALREADY_USED"
            )
            self._entered, self._thread = True, get_ident()
            self._stack = ExitStack()
            try:
                transaction = self._stack.enter_context(
                    self._persistence.transaction(self._leases)
                )
                _require(
                    type(transaction) is M1RehearsalTransaction
                    and transaction.held_leases == self._leases,
                    "EXACT_M1_TRANSACTION_REQUIRED",
                )
                self._transaction = transaction
                return self
            except BaseException:
                self._close(*sys.exc_info())
                raise

    def _close(self, exc_type: Any = None, exc: Any = None, tb: Any = None) -> None:
        if self._closed:
            return
        self._closed = True
        stack, self._stack = self._stack, None
        self._transaction = None
        if stack is not None:
            try:
                _require(
                    not stack.__exit__(exc_type, exc, tb),
                    "M1_CONTEXT_SUPPRESSED_FAILURE",
                )
            except BaseException as failure:
                # Retain the cleanup cause and never retry/double-close. When
                # this runs in execute's exit the core latches its existing hold.
                self._cleanup_error = failure
                raise

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        with self._lock:
            _require(self._thread == get_ident(), "REHEARSAL_WINDOW_THREAD_CHANGED")
            self._close(exc_type, exc, tb)
        return False

    @property
    def preflight_transaction(self) -> M1RehearsalTransaction:
        with self._lock:
            self._live()
            _require(
                self._uses == 0 and self._bound is None and not self._busy,
                "PREFLIGHT_WINDOW_ENDED",
            )
            assert self._transaction is not None
            return self._transaction

    def bind_request(self, request: RegisteredActionRequest) -> None:
        with self._lock:
            self._live()
            _require(
                self._uses == 0 and self._bound is None and not self._busy,
                "REQUEST_ALREADY_BOUND_OR_DISPATCHED",
            )
            _request_bytes(request)
            before, after = asdict(self._provisional), asdict(request)
            before.pop("expected_challenge_sha256")
            after.pop("expected_challenge_sha256")
            _require(before == after, "BOUND_REQUEST_SUBSTITUTED")
            self._bound = _request_bytes(request)

    def _check_request(self, request: RegisteredActionRequest) -> None:
        self._live()
        _require(
            self._bound is not None and _request_bytes(request) == self._bound,
            "EXACT_BOUND_REQUEST_REQUIRED",
        )

    def _check_phase(self, phase: int) -> None:
        self._live()
        _require(self._busy and self._uses == phase, "COORDINATOR_CONTEXT_ENDED")

    @contextmanager
    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[CommissioningTransaction]:
        with self._lock:
            self._live()
            _require(
                type(leases) is tuple and leases == self._leases,
                "DISPATCH_LEASES_SUBSTITUTED",
            )
            _require(
                self._bound is not None and not self._busy and self._uses < 2,
                "COORDINATOR_CONTEXT_BUDGET_OR_ORDER",
            )
            self._uses += 1
            phase = self._uses
            self._busy = True
        try:
            yield cast(CommissioningTransaction, _DispatchTransaction(self, phase))
        except BaseException:
            with self._lock:
                self._busy = False
                self._close(*sys.exc_info())
            raise
        else:
            with self._lock:
                self._busy = False
                if phase == 2:
                    # Deliberately inside core's _transaction_scope, not deferred
                    # to the outer UI with statement after a known result return.
                    self._close()
