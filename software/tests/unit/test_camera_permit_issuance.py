"""First-issuance clock contracts: incapable workers, no I/O or TTL increase."""

from contextlib import contextmanager
from dataclasses import replace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
    MAX_PERMIT_TTL_NS,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from test_physical_camera_coordinator import components
from test_usb_identity_permit_issuance import delayed_first_read


@pytest.mark.parametrize("read_delay", [6_000_000_000, 31_000_000_000])
def test_first_camera_issuance_follows_read_without_increasing_ttl(
    monkeypatch, read_delay
):
    core, store, worker, request = components()
    clock = delayed_first_read(core, store, monkeypatch, read_delay)
    before = clock.now
    permit = core.prepare(request)
    assert permit.issued_at_ns == before + read_delay == clock.now
    assert (
        permit.expires_at_ns - permit.issued_at_ns
        == MAX_PERMIT_TTL_NS
        == 30_000_000_000
    )
    assert permit.registration.budget.timeout_ms == 20000 and permit.envelope is None
    assert worker.calls == 0 and not store.attempts
    assert core.execute(permit).state is AttemptState.SEALED_KNOWN
    assert worker.calls == 1


def test_camera_first_issuance_waits_for_successful_lease_cleanup(monkeypatch):
    core, store, worker, request = components()
    clock = delayed_first_read(core, store, monkeypatch, 6_000_000_000)
    transaction = store.transaction
    releases = []

    @contextmanager
    def delayed(leases):
        with transaction(leases) as tx:
            yield tx
        if not releases:
            clock.now += 6_000_000_000
        releases.append(clock.now)

    monkeypatch.setattr(store, "transaction", delayed)
    permit = core.prepare(request)
    assert permit.issued_at_ns == releases[0] == clock.now
    assert worker.calls == 0 and not store.attempts
    assert core.execute(permit).state is AttemptState.SEALED_KNOWN


def test_camera_prepare_cleanup_failure_issues_nothing(monkeypatch):
    core, store, worker, request = components()
    transaction = store.transaction

    @contextmanager
    def failed(leases):
        with transaction(leases) as tx:
            yield tx
        raise OSError("MODELED_RELEASE_FAILURE")

    monkeypatch.setattr(store, "transaction", failed)
    for _ in range(2):
        with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
            core.prepare(request)
    assert not core._permits and not core._prepared_requests
    assert not store.attempts and worker.calls == 0


def test_camera_repeated_prepare_does_not_renew_expired_permit(monkeypatch):
    core, store, worker, request = components()
    clock = delayed_first_read(core, store, monkeypatch, 6_000_000_000)
    permit = core.prepare(request)
    clock.now = permit.expires_at_ns + 1
    assert core.prepare(request) is permit
    with pytest.raises(CommissioningCoordinatorError, match="expired"):
        core.execute(permit)
    assert not store.attempts and worker.calls == 0


def test_camera_changed_snapshot_after_prepare_is_still_rejected(monkeypatch):
    core, store, worker, request = components()
    transaction = store.transaction

    @contextmanager
    def changed(leases):
        with transaction(leases) as tx:
            yield tx
        store.snapshot = replace(store.snapshot, source_binding_sha256="8" * 64)

    monkeypatch.setattr(store, "transaction", changed)
    permit = core.prepare(request)
    with pytest.raises(CommissioningCoordinatorError, match="stale"):
        core.execute(permit)
    assert not store.attempts and worker.calls == 0


def test_camera_expiry_during_second_admission_cannot_write_intent(monkeypatch):
    core, store, worker, request = components()
    clock = delayed_first_read(core, store, monkeypatch, 0)
    permit = core.prepare(request)
    read = store.read_admission

    def delayed(request):
        value = read(request)
        clock.now = permit.expires_at_ns
        return value

    monkeypatch.setattr(store, "read_admission", delayed)
    with pytest.raises(CommissioningCoordinatorError, match="expired"):
        core.execute(permit)
    assert not store.attempts and worker.calls == 0


def test_camera_slow_consumption_still_requires_full_registered_lifetime(monkeypatch):
    core, store, worker, request = components()
    clock = delayed_first_read(core, store, monkeypatch, 0)
    permit = core.prepare(request)
    consume = store.consume_permit

    def delayed(value):
        consume(value)
        clock.now += 11_000_000_000

    monkeypatch.setattr(store, "consume_permit", delayed)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.receipt is None and worker.calls == 0
    assert permit.expires_at_ns - permit.issued_at_ns == 30_000_000_000
