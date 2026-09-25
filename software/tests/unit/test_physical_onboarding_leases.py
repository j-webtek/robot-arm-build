from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
from typing import Any

import pytest

from rocell.application import physical_onboarding_leases as leases_module
from rocell.application.physical_onboarding_durability import (
    run_on_volume_startup_self_test,
)
from rocell.application.physical_onboarding_leases import (
    LEASE_RECONCILIATION_RECEIPT_SCHEMA,
    LeaseBusyError,
    LeaseChallengeError,
    LeaseLevel,
    LeaseOrderError,
    LeaseOwnerMetadata,
    LeaseOwnerState,
    LeaseReconciliationError,
    LeaseSpec,
    OnboardingLeaseManager,
    PhysicalOnboardingLeaseError,
    StaleLeaseOwnerError,
    windows_lockfileex_self_test,
)


SOURCE = "a" * 64
CHALLENGE = "b" * 64
NONCE = "c" * 64


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "leases"
    root.mkdir()
    return root.resolve()


def _manager(root: Path, *, qualified: bool = False) -> OnboardingLeaseManager:
    report = None
    if qualified:
        report = run_on_volume_startup_self_test(
            root,
            source_binding_sha256=SOURCE,
            lease_probe=windows_lockfileex_self_test,
            checked_at_ns=1_000,
        )
    return OnboardingLeaseManager(root, SOURCE, NONCE, report)


def _cell_session() -> tuple[LeaseSpec, LeaseSpec]:
    return (
        LeaseSpec(LeaseLevel.CELL, "CELL-A"),
        LeaseSpec(LeaseLevel.SESSION, "arrival-001"),
    )


def _leave_stale_active_owner(
    manager: OnboardingLeaseManager,
    spec: LeaseSpec,
    *,
    acquired_at_ns: int = 2_000,
) -> LeaseOwnerMetadata:
    held = manager.acquire(
        [spec],
        operation="CRASH_SIMULATION",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=acquired_at_ns,
    )
    owner = held.owners[0]
    held._leases[0].lock.release()
    held._closed = True
    return owner


def _holder_process(
    root_text: str,
    ready: Any,
    release: Any,
    result: Any,
) -> None:
    try:
        root = Path(root_text)
        manager = OnboardingLeaseManager(root, SOURCE, "d" * 64, None)
        held = manager.acquire(
            [LeaseSpec(LeaseLevel.CELL, "CELL-RACE")],
            operation="PROCESS_RACE",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=False,
            acquired_at_ns=2_000,
        )
        result.put("ACQUIRED")
        ready.set()
        release.wait(15)
        held.close(released_at_ns=3_000)
        result.put("RELEASED")
    except BaseException as exc:
        result.put(f"ERROR:{type(exc).__name__}:{exc}")
        ready.set()


def test_exact_order_and_effectful_cell_session_prefix(tmp_path: Path) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    cell, session = _cell_session()
    camera = LeaseSpec(LeaseLevel.CAMERA, "B0477-001")
    arm = LeaseSpec(LeaseLevel.ARM_CONTROLLER, "ROARM-001")

    for invalid in (
        (session, cell),
        (cell, cell),
        (cell, arm, camera),
    ):
        with pytest.raises(LeaseOrderError, match="ordered|unique"):
            manager.acquire(
                invalid,
                operation="ORDER_TEST",
                expected_challenge_sha256=CHALLENGE,
                challenge_callback=lambda: CHALLENGE,
                effectful=False,
            )

    with pytest.raises(LeaseOrderError, match="begin CELL -> SESSION"):
        manager.acquire(
            (cell, camera),
            operation="ORDER_TEST",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=True,
        )


def test_effectful_acquisition_requires_qualified_windows_durability(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    with pytest.raises(PhysicalOnboardingLeaseError, match="qualified durability"):
        manager.acquire(
            _cell_session(),
            operation="CAMERA_OPEN",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=True,
        )


@pytest.mark.skipif(
    os.name != "nt", reason="physical effects qualify only on Windows NTFS"
)
def test_effectful_ordered_owner_metadata_and_clean_reverse_release(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root, qualified=True)
    specs = (*_cell_session(), LeaseSpec(LeaseLevel.CAMERA, "B0477-001"))
    callback_observations: list[tuple[LeaseOwnerState, ...]] = []

    def challenge() -> str:
        callback_observations.append(
            tuple(manager.prior_owner(item).state for item in specs)  # type: ignore[union-attr]
        )
        return CHALLENGE

    held = manager.acquire(
        specs,
        operation="CAMERA_OPEN",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=challenge,
        effectful=True,
        acquired_at_ns=2_000,
    )
    assert callback_observations == [
        (LeaseOwnerState.ACTIVE, LeaseOwnerState.ACTIVE, LeaseOwnerState.ACTIVE)
    ]
    assert [item.level for item in held.owners] == [
        LeaseLevel.CELL,
        LeaseLevel.SESSION,
        LeaseLevel.CAMERA,
    ]
    assert all(item.pid == os.getpid() for item in held.owners)
    assert all(item.process_start_identity for item in held.owners)
    assert all(item.launch_nonce == NONCE for item in held.owners)
    assert all(item.operation == "CAMERA_OPEN" for item in held.owners)

    held.close(released_at_ns=3_000)
    assert held.closed is True
    assert all(manager.prior_owner(item).state is LeaseOwnerState.RELEASED for item in specs)  # type: ignore[union-attr]


def test_challenge_is_rechecked_after_all_locks_and_stale_challenge_releases(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    specs = _cell_session()
    calls = 0

    def stale() -> str:
        nonlocal calls
        calls += 1
        assert all(manager.prior_owner(item).state is LeaseOwnerState.ACTIVE for item in specs)  # type: ignore[union-attr]
        return "f" * 64

    with pytest.raises(LeaseChallengeError, match="changed"):
        manager.acquire(
            specs,
            operation="REVIEW_COMMIT",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=stale,
            effectful=False,
            acquired_at_ns=2_000,
        )
    assert calls == 1
    assert all(manager.prior_owner(item).state is LeaseOwnerState.RELEASED for item in specs)  # type: ignore[union-attr]


def test_nonblocking_busy_does_not_replace_current_owner(tmp_path: Path) -> None:
    root = _root(tmp_path)
    first = _manager(root)
    second = OnboardingLeaseManager(root, SOURCE, "d" * 64, None)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-A")
    held = first.acquire(
        [spec],
        operation="FIRST_WRITER",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=2_000,
    )
    owner_before = first.prior_owner(spec)
    with pytest.raises(LeaseBusyError, match="busy"):
        second.acquire(
            [spec],
            operation="SECOND_WRITER",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=False,
            acquired_at_ns=2_100,
        )
    assert first.prior_owner(spec) == owner_before
    held.close(released_at_ns=3_000)


@pytest.mark.skipif(os.name != "nt", reason="Win32 handle lifetime is Windows-only")
def test_owner_read_failure_does_not_leak_newly_acquired_lock(tmp_path: Path) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-READ-FAILURE")
    _, owner_path = manager._paths(spec)
    owner_path.write_bytes(b"not-json")

    with pytest.raises(PhysicalOnboardingLeaseError, match="strict JSON"):
        manager.acquire(
            [spec],
            operation="OWNER_READ_FAILURE",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=False,
            acquired_at_ns=2_000,
        )

    owner_path.unlink()
    held = manager.acquire(
        [spec],
        operation="AFTER_READ_FAILURE",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=3_000,
    )
    held.close(released_at_ns=4_000)


def test_free_os_lock_with_active_owner_is_not_stolen_using_pid(tmp_path: Path) -> None:
    root = _root(tmp_path)
    first = _manager(root)
    second = OnboardingLeaseManager(root, SOURCE, "d" * 64, None)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-STALE")
    held = first.acquire(
        [spec],
        operation="CRASH_SIMULATION",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=2_000,
    )
    # Model process death: the OS releases the handle but ACTIVE metadata stays.
    held._leases[0].lock.release()
    held._closed = True

    with pytest.raises(StaleLeaseOwnerError, match="pid-only takeover is forbidden"):
        second.acquire(
            [spec],
            operation="TAKEOVER_ATTEMPT",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=False,
            acquired_at_ns=2_100,
        )
    assert second.prior_owner(spec).state is LeaseOwnerState.ACTIVE  # type: ignore[union-attr]


def test_reviewed_reconciliation_marks_abandoned_and_allows_owner_chain(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-RECONCILE")
    active = _leave_stale_active_owner(manager, spec)

    abandoned = manager.reconcile_stale_owner(
        spec,
        expected_active_owner_sha256=active.owner_sha256,
        reviewed_reconciliation_sha256="d" * 64,
        reconciled_at_ns=3_000,
    )

    assert abandoned.state is LeaseOwnerState.ABANDONED
    assert abandoned.released_at_ns is None
    assert abandoned.previous_owner_sha256 == active.owner_sha256
    assert manager.prior_owner(spec) == abandoned
    receipt_path = manager._reconciliation_receipt_path(spec, active.owner_sha256)
    receipt = json.loads(receipt_path.read_text(encoding="ascii"))
    assert receipt["schema"] == LEASE_RECONCILIATION_RECEIPT_SCHEMA
    assert receipt["active_owner_sha256"] == active.owner_sha256
    assert receipt["abandoned_owner_sha256"] == abandoned.owner_sha256
    assert receipt["reviewed_reconciliation_sha256"] == "d" * 64
    assert receipt["reconciled_at_ns"] == 3_000

    next_manager = OnboardingLeaseManager(root, SOURCE, "e" * 64, None)
    held = next_manager.acquire(
        [spec],
        operation="AFTER_RECONCILIATION",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=4_000,
    )
    assert held.owners[0].previous_owner_sha256 == abandoned.owner_sha256
    held.close(released_at_ns=5_000)


def test_reconciliation_rejects_busy_and_exact_evidence_mismatches(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-RECONCILE-GUARDS")
    held = manager.acquire(
        [spec],
        operation="LIVE_OWNER",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=2_000,
    )
    active = held.owners[0]
    contender = OnboardingLeaseManager(root, SOURCE, "d" * 64, None)
    with pytest.raises(LeaseBusyError, match="busy"):
        contender.reconcile_stale_owner(
            spec,
            expected_active_owner_sha256=active.owner_sha256,
            reviewed_reconciliation_sha256="e" * 64,
            reconciled_at_ns=3_000,
        )
    assert not contender._reconciliation_receipt_path(
        spec, active.owner_sha256
    ).exists()

    held._leases[0].lock.release()
    held._closed = True
    with pytest.raises(LeaseReconciliationError, match="nonzero"):
        contender.reconcile_stale_owner(
            spec,
            expected_active_owner_sha256=active.owner_sha256,
            reviewed_reconciliation_sha256="0" * 64,
            reconciled_at_ns=3_000,
        )
    with pytest.raises(LeaseReconciliationError, match="hash differs"):
        contender.reconcile_stale_owner(
            spec,
            expected_active_owner_sha256="f" * 64,
            reviewed_reconciliation_sha256="e" * 64,
            reconciled_at_ns=3_000,
        )
    wrong_source = OnboardingLeaseManager(root, "f" * 64, "e" * 64, None)
    with pytest.raises(LeaseReconciliationError, match="source binding"):
        wrong_source.reconcile_stale_owner(
            spec,
            expected_active_owner_sha256=active.owner_sha256,
            reviewed_reconciliation_sha256="e" * 64,
            reconciled_at_ns=3_000,
        )

    abandoned = contender.reconcile_stale_owner(
        spec,
        expected_active_owner_sha256=active.owner_sha256,
        reviewed_reconciliation_sha256="e" * 64,
        reconciled_at_ns=3_000,
    )
    assert abandoned.state is LeaseOwnerState.ABANDONED


def test_receipt_first_stop_retries_exactly_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-RECONCILE-RETRY")
    active = _leave_stale_active_owner(manager, spec)
    original_publish = leases_module.publish_canonical_json
    stopped = False

    class InjectedReconciliationStop(RuntimeError):
        pass

    def publish_then_stop(*args: Any, **kwargs: Any) -> Path:
        nonlocal stopped
        result = original_publish(*args, **kwargs)
        relative_path = str(args[1])
        if not stopped and ".reconciliation-" in relative_path:
            stopped = True
            raise InjectedReconciliationStop()
        return result

    monkeypatch.setattr(leases_module, "publish_canonical_json", publish_then_stop)
    with pytest.raises(InjectedReconciliationStop):
        manager.reconcile_stale_owner(
            spec,
            expected_active_owner_sha256=active.owner_sha256,
            reviewed_reconciliation_sha256="d" * 64,
            reconciled_at_ns=3_000,
        )
    assert manager.prior_owner(spec) == active
    assert manager._reconciliation_receipt_path(spec, active.owner_sha256).is_file()

    with pytest.raises(LeaseReconciliationError, match="receipt differs"):
        manager.reconcile_stale_owner(
            spec,
            expected_active_owner_sha256=active.owner_sha256,
            reviewed_reconciliation_sha256="e" * 64,
            reconciled_at_ns=3_000,
        )
    assert manager.prior_owner(spec) == active

    abandoned = manager.reconcile_stale_owner(
        spec,
        expected_active_owner_sha256=active.owner_sha256,
        reviewed_reconciliation_sha256="d" * 64,
        reconciled_at_ns=3_000,
    )
    retried = manager.reconcile_stale_owner(
        spec,
        expected_active_owner_sha256=active.owner_sha256,
        reviewed_reconciliation_sha256="d" * 64,
        reconciled_at_ns=3_000,
    )
    assert retried == abandoned
    assert retried.state is LeaseOwnerState.ABANDONED


def test_clean_release_allows_new_owner_and_chains_metadata(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-REUSE")
    first = _manager(root)
    held = first.acquire(
        [spec],
        operation="FIRST_WRITER",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=2_000,
    )
    held.close(released_at_ns=3_000)
    released = first.prior_owner(spec)
    assert released is not None

    second = OnboardingLeaseManager(root, SOURCE, "d" * 64, None)
    acquired = second.acquire(
        [spec],
        operation="SECOND_WRITER",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=4_000,
    )
    assert acquired.owners[0].previous_owner_sha256 == released.owner_sha256
    acquired.close(released_at_ns=5_000)


def test_reuse_rejects_prior_owner_copied_from_another_resource(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    source_spec = LeaseSpec(LeaseLevel.CELL, "CELL-SOURCE")
    target_spec = LeaseSpec(LeaseLevel.CELL, "CELL-TARGET")
    held = manager.acquire(
        [source_spec],
        operation="SOURCE_OWNER",
        expected_challenge_sha256=CHALLENGE,
        challenge_callback=lambda: CHALLENGE,
        effectful=False,
        acquired_at_ns=2_000,
    )
    held.close(released_at_ns=3_000)
    _, source_owner_path = manager._paths(source_spec)
    _, target_owner_path = manager._paths(target_spec)
    source_owner_path.rename(target_owner_path)

    with pytest.raises(PhysicalOnboardingLeaseError, match="exact resource"):
        manager.acquire(
            [target_spec],
            operation="MUST_NOT_REUSE",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=False,
            acquired_at_ns=4_000,
        )


def test_abandoned_owner_cannot_be_reused_without_exact_receipt(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    manager = _manager(root)
    spec = LeaseSpec(LeaseLevel.CELL, "CELL-MISSING-RECEIPT")
    active = _leave_stale_active_owner(manager, spec)
    manager.reconcile_stale_owner(
        spec,
        expected_active_owner_sha256=active.owner_sha256,
        reviewed_reconciliation_sha256="d" * 64,
        reconciled_at_ns=3_000,
    )
    manager._reconciliation_receipt_path(spec, active.owner_sha256).unlink()

    with pytest.raises(LeaseReconciliationError, match="receipt"):
        manager.prior_owner(spec)
    with pytest.raises(LeaseReconciliationError, match="receipt"):
        manager.acquire(
            [spec],
            operation="MUST_NOT_REUSE",
            expected_challenge_sha256=CHALLENGE,
            challenge_callback=lambda: CHALLENGE,
            effectful=False,
            acquired_at_ns=4_000,
        )


def test_two_process_race_has_one_owner_and_one_bounded_busy(tmp_path: Path) -> None:
    root = _root(tmp_path)
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    result = context.Queue()
    process = context.Process(
        target=_holder_process,
        args=(str(root), ready, release, result),
    )
    process.start()
    try:
        assert ready.wait(15), "holder process did not reach acquisition boundary"
        assert result.get(timeout=5) == "ACQUIRED"
        contender = OnboardingLeaseManager(root, SOURCE, "e" * 64, None)
        with pytest.raises(LeaseBusyError, match="busy"):
            contender.acquire(
                [LeaseSpec(LeaseLevel.CELL, "CELL-RACE")],
                operation="CONTENDER",
                expected_challenge_sha256=CHALLENGE,
                challenge_callback=lambda: CHALLENGE,
                effectful=False,
                acquired_at_ns=2_500,
            )
        release.set()
        assert result.get(timeout=5) == "RELEASED"
    finally:
        release.set()
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0
