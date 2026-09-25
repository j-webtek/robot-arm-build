"""A failed persistence exit cannot disappear behind a cached worker result.

Only memory fixtures are used. These failures model the coordinator's lease
release seam; they do not perform a real port open or change a known arm seal.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from test_arm_feedback_rehearsal_campaign import components
from test_commissioning_coordinator import _components


def _fail_transaction_exit(store, failure):
    original = store.transaction
    exits = []

    @contextmanager
    def transaction(leases):
        with original(leases) as tx:
            yield tx
        exits.append(failure)
        raise failure

    store.transaction = transaction
    return exits


def _failed_execution(outcome, *, retained=True, failure=None):
    if retained:
        coordinator, store, worker, _, request = components(
            "close-failure" if outcome == "uncertain" else "nominal"
        )
    else:
        coordinator, store, worker, _, request = _components()
        if outcome == "uncertain":
            worker.fault = "raise"
    permit = coordinator.prepare(request)
    if outcome == "aborted":
        coordinator.cancel(permit)
    failure = failure or OSError("fixture private endpoint COM42 release failed")
    exits = _fail_transaction_exit(store, failure)
    with pytest.raises(BaseException) as observed:
        coordinator.execute(permit)
    return coordinator, store, worker, request, permit, failure, exits, observed.value


@pytest.mark.parametrize("outcome", ["known", "aborted", "uncertain"])
@pytest.mark.parametrize("retained", [True, False], ids=["arm", "camera"])
def test_failed_exit_preserves_durable_result_and_reports_safe_error(outcome, retained):
    _, store, worker, _, permit, failure, exits, observed = _failed_execution(
        outcome, retained=retained
    )
    expected = {
        "known": AttemptState.SEALED_KNOWN,
        "aborted": AttemptState.ABORTED_PRE_EFFECT,
        "uncertain": AttemptState.SEALED_UNCERTAIN,
    }[outcome]
    # Failed lease release does not retrofit uncertainty into a known exchange
    # or invent effects in an already-aborted pre-effect result.
    assert store.attempts[permit.attempt_id] is expected
    assert store.results[permit.attempt_id].state is expected
    assert store.trace.count("QUARANTINE_LATCHED") == (outcome == "uncertain")
    assert len(exits) == 1
    if retained and outcome != "aborted":
        assert worker.evidence is not None
        assert store.evidence[permit.attempt_id][0].payload == (
            worker.evidence.canonical_bytes()
        )
    assert isinstance(observed, CommissioningCoordinatorError)
    assert "cleanup" in str(observed).lower()
    assert "COM42" not in str(observed)
    assert observed.__cause__ is failure


@pytest.mark.parametrize("outcome", ["known", "aborted", "uncertain"])
def test_failed_exit_blocks_cached_result_and_new_admission_without_redispatch(outcome):
    coordinator, store, _, request, permit, failure, exits, _ = _failed_execution(
        outcome
    )
    prior_trace = tuple(store.trace)
    prior_result = store.results[permit.attempt_id]
    with pytest.raises(
        CommissioningCoordinatorError, match="cleanup|held"
    ) as duplicate:
        coordinator.execute(permit)
    assert duplicate.value.__cause__ is failure
    assert "COM42" not in str(duplicate.value)
    with pytest.raises(CommissioningCoordinatorError, match="cleanup|held"):
        coordinator.prepare(replace(request, request_key="request-after-release-error"))
    assert tuple(store.trace) == prior_trace
    assert len(exits) == 1  # No lease release retry, worker replay or new scope.
    assert store.results[permit.attempt_id] is prior_result


def test_prepare_exit_failure_holds_without_exposing_a_permit_or_running_worker():
    coordinator, store, worker, _, request = components()
    failure = OSError("fixture private endpoint COM42 prepare release failed")
    exits = _fail_transaction_exit(store, failure)
    with pytest.raises(CommissioningCoordinatorError, match="cleanup|held") as observed:
        coordinator.prepare(request)
    assert observed.value.__cause__ is failure
    assert "COM42" not in str(observed.value)
    prior_trace = tuple(store.trace)
    with pytest.raises(CommissioningCoordinatorError, match="cleanup|held"):
        coordinator.prepare(request)
    assert tuple(store.trace) == prior_trace
    assert not store.attempts and not store.results and not store.evidence
    assert worker.status()["consumed"] is False
    assert len(exits) == 1


@pytest.mark.parametrize("failure_type", [KeyboardInterrupt, SystemExit])
def test_exit_base_exception_is_reraised_but_still_holds_duplicates(failure_type):
    failure = failure_type("fixture termination during lease release")
    coordinator, store, _, _, permit, _, exits, observed = _failed_execution(
        "known", failure=failure
    )
    assert observed is failure
    assert store.attempts[permit.attempt_id] is AttemptState.SEALED_KNOWN
    with pytest.raises(
        CommissioningCoordinatorError, match="cleanup|held"
    ) as duplicate:
        coordinator.execute(permit)
    assert duplicate.value.__cause__ is failure
    assert len(exits) == 1


@pytest.mark.parametrize("scenario", ["nominal", "close-failure"])
def test_clean_exit_keeps_known_and_uncertain_duplicate_idempotency(scenario):
    coordinator, store, _, _, request = components(scenario)
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    prior_trace = tuple(store.trace)
    assert coordinator.execute(permit) is result
    assert tuple(store.trace) == prior_trace
