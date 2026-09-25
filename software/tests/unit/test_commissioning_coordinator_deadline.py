"""Controlled-clock intent/consume costs never extend exact campaign authority."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CellCommissioningCoordinator,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from test_commissioning_coordinator import _components
from test_arm_feedback_rehearsal_campaign import components


@pytest.mark.parametrize(
    "retained", [False, True], ids=["legacy-core", "actual-incapable-arm"]
)
@pytest.mark.parametrize("slow_boundary", ["begin_intent", "consume_permit"])
def test_slow_durable_boundary_leaves_no_full_window_so_worker_never_dispatches(
    retained,
    slow_boundary,
):
    coordinator, store, worker, clock, request = (
        components() if retained else _components(serial=True)
    )
    permit = coordinator.prepare(request)
    original = getattr(store, slow_boundary)
    budget_ns = permit.registration.budget.timeout_ms * 1_000_000
    late_but_unexpired = permit.expires_at_ns - budget_ns + 1

    def delayed(*args, **kwargs):
        original(*args, **kwargs)
        setattr(clock, "value" if retained else "now", late_but_unexpired)

    setattr(store, slow_boundary, delayed)
    result = coordinator.execute(permit)
    assert late_but_unexpired < permit.expires_at_ns
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched is True
    assert result.receipt is None
    assert "EFFECT_ARMED" in store.trace
    assert "SEALED_KNOWN" not in store.trace
    if retained:
        assert worker.status()["consumed"] is False
        assert worker.request is None and worker.evidence is None
        assert "EXACT_ARMED_AUTHORIZATION" not in store.trace
        assert not store.evidence
    else:
        assert worker.calls == 0
    # The existing result is returned; neither renewal nor retry is introduced.
    assert coordinator.execute(permit) is result
    assert store.trace.count("EFFECT_ARMED") == 1


def _long_camera_components():
    original, store, worker, clock, request = _components()
    prior_registration = original.prepare(request).registration
    registration = replace(
        prior_registration,
        budget=replace(prior_registration.budget, timeout_ms=60000),
    )
    coordinator = CellCommissioningCoordinator(
        persistence=store,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        monotonic_ns=clock,
    )
    return coordinator, store, worker, clock, request


def test_no_envelope_camera_budget_can_outlive_its_dispatch_permit():
    coordinator, store, worker, clock, request = _long_camera_components()
    permit = coordinator.prepare(request)
    original = worker.run_campaign

    def capture(exact, *, deadline_ns, cancellation):
        assert exact.envelope is None
        assert clock.now < exact.expires_at_ns < deadline_ns
        assert deadline_ns - clock.now == 60_000_000_000
        # Dispatch was valid. A 31-second capture is still inside the exact
        # independent 60-second budget despite the 30-second ticket TTL.
        clock.now = exact.expires_at_ns + 1_000_000_000
        return original(exact, deadline_ns=deadline_ns, cancellation=cancellation)

    worker.run_campaign = capture
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.quarantine_latched is False
    assert worker.calls == 1
    assert coordinator.execute(permit) is result
    assert store.trace.count("EFFECT_ARMED") == 1


def test_no_envelope_camera_still_requires_valid_permit_at_dispatch():
    coordinator, store, worker, clock, request = _long_camera_components()
    permit = coordinator.prepare(request)
    original = store.consume_permit

    def slow_consume(exact):
        original(exact)
        clock.now = exact.expires_at_ns

    store.consume_permit = slow_consume
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched is True
    assert worker.calls == 0
    assert "SEALED_KNOWN" not in store.trace
