"""Modeled clocks, no I/O: first USB issuance is not predated or renewed."""

from contextlib import contextmanager
from dataclasses import replace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    MAX_PERMIT_TTL_NS,
    USB_IDENTITY_MINIMUM_WINDOW_NS,
    CommissioningCoordinatorError,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from test_commissioning_coordinator import Clock
from test_commissioning_usb_identity import protocol_components
from test_physical_camera_coordinator import components as camera_components


def delayed_first_read(core, store, monkeypatch, delay_ns):
    clock = Clock()
    core._clock = clock
    original = store.read_admission
    calls = []

    def read(request):
        if not calls:
            clock.now += delay_ns
        calls.append(request)
        return original(request)

    monkeypatch.setattr(store, "read_admission", read)
    return clock


@pytest.mark.parametrize("read_delay", [6_000_000_000, 31_000_000_000])
def test_first_usb_permit_issued_after_leased_read_without_lifetime_increase(
    monkeypatch, read_delay
):
    core, store, worker, request = protocol_components()
    clock = delayed_first_read(core, store, monkeypatch, read_delay)
    before = clock.now
    permit = core.prepare(request)
    assert permit.issued_at_ns == before + read_delay == clock.now
    assert (
        permit.expires_at_ns - permit.issued_at_ns
        == MAX_PERMIT_TTL_NS
        == 30_000_000_000
    )
    assert permit.registration.budget.timeout_ms == 25000
    assert not store.attempts and worker.calls == 0
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN and worker.calls == 1


def test_repeated_prepare_never_refreshes_issued_usb_permit(monkeypatch):
    core, store, worker, request = protocol_components()
    clock = delayed_first_read(core, store, monkeypatch, 6_000_000_000)
    permit = core.prepare(request)
    clock.now = permit.expires_at_ns + 1
    repeated = core.prepare(request)
    assert repeated is permit
    with pytest.raises(CommissioningCoordinatorError):
        core.execute(repeated)
    assert worker.calls == 0 and not store.attempts


def test_slow_consumption_still_refuses_incomplete_prepared_lifecycle(monkeypatch):
    core, store, worker, request = protocol_components()
    clock = delayed_first_read(core, store, monkeypatch, 6_000_000_000)
    permit = core.prepare(request)
    original = store.consume_permit

    def consume(value):
        original(value)
        clock.now += 11_000_000_000

    monkeypatch.setattr(store, "consume_permit", consume)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.receipt is None and worker.calls == 0
    assert permit.expires_at_ns - permit.issued_at_ns == MAX_PERMIT_TTL_NS


@pytest.mark.parametrize("delay_s", [0, 4, 6, 9])
def test_usb_deadline_is_clipped_not_renewed_and_preserves_fixed_ceiling(
    monkeypatch, delay_s
):
    core, store, worker, request = protocol_components()
    clock = delayed_first_read(core, store, monkeypatch, 0)
    permit = core.prepare(request)
    consume = store.consume_permit
    run = worker.run_scoped_campaign
    deadlines = []

    def delayed_consume(value):
        consume(value)
        clock.now += delay_s * 1_000_000_000

    def run_campaign(value, **kwargs):
        deadlines.append(kwargs["deadline_ns"])
        return run(value, **kwargs)

    monkeypatch.setattr(store, "consume_permit", delayed_consume)
    monkeypatch.setattr(worker, "run_scoped_campaign", run_campaign)
    assert core.execute(permit).state is AttemptState.SEALED_KNOWN
    assert worker.calls == 1
    assert deadlines == [min(clock.now + 25_000_000_000, permit.expires_at_ns)]
    assert deadlines[0] - clock.now >= USB_IDENTITY_MINIMUM_WINDOW_NS
    assert permit.expires_at_ns - permit.issued_at_ns == 30_000_000_000
    assert permit.registration.budget.timeout_ms == 25000


def test_usb_minimum_matches_closed_preparation_lifetime():
    from rocell.providers.windows.usb_identity_registration import REQUIRED_LIFETIME_NS

    assert USB_IDENTITY_MINIMUM_WINDOW_NS == REQUIRED_LIFETIME_NS == 20_000_000_000


def test_camera_first_issuance_uses_the_same_post_prepare_clock(monkeypatch):
    core, store, worker, request = camera_components()
    clock = delayed_first_read(core, store, monkeypatch, 6_000_000_000)
    before = clock.now
    permit = core.prepare(request)
    assert permit.issued_at_ns == clock.now == before + 6_000_000_000
    assert permit.expires_at_ns == permit.issued_at_ns + MAX_PERMIT_TTL_NS
    assert worker.calls == 0


def test_first_usb_issuance_follows_successful_prepare_lease_cleanup(monkeypatch):
    core, store, worker, request = protocol_components()
    clock = delayed_first_read(core, store, monkeypatch, 6_000_000_000)
    original = store.transaction
    releases = []

    @contextmanager
    def transaction(leases):
        with original(leases) as tx:
            yield tx
        if not releases:
            clock.now += 6_000_000_000
        releases.append(clock.now)

    monkeypatch.setattr(store, "transaction", transaction)
    permit = core.prepare(request)
    assert permit.issued_at_ns == releases[0] == clock.now
    assert permit.expires_at_ns - permit.issued_at_ns == MAX_PERMIT_TTL_NS
    assert core.execute(permit).state is AttemptState.SEALED_KNOWN
    assert worker.calls == 1


def test_prepare_cleanup_failure_cannot_issue_or_cache_usb_permit(monkeypatch):
    core, store, worker, request = protocol_components()
    original = store.transaction

    @contextmanager
    def transaction(leases):
        with original(leases) as tx:
            yield tx
        raise OSError("modeled lease release failure")

    monkeypatch.setattr(store, "transaction", transaction)
    with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
        core.prepare(request)
    assert not core._permits and not core._prepared_requests
    assert worker.calls == 0 and not store.attempts
    with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
        core.prepare(request)


def test_source_change_during_prepare_cleanup_is_rejected_before_intent(monkeypatch):
    core, store, worker, request = protocol_components()
    original = store.transaction

    @contextmanager
    def transaction(leases):
        with original(leases) as tx:
            yield tx
        store.snapshot = replace(store.snapshot, source_binding_sha256="e" * 64)

    monkeypatch.setattr(store, "transaction", transaction)
    permit = core.prepare(request)
    with pytest.raises(CommissioningCoordinatorError, match="stale"):
        core.execute(permit)
    assert not store.attempts and worker.calls == 0
