"""One-lease scope tests; actual M1 uses new isolated NTFS stores, no devices."""

from contextlib import contextmanager
from dataclasses import replace
import hashlib
from types import SimpleNamespace
import threading
import time

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignRegistration,
    CellCommissioningCoordinator,
    CommissioningCoordinatorError,
    INCAPABLE_COMPOSITION,
    ObservedPowerState,
    RegisteredActionRequest,
    WorkerReceipt,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistence,
    M1RehearsalTransaction,
    RehearsalAdmissionFacts,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.scoped_rehearsal_dispatch import (
    ACTION_ID,
    ACTION_IDS,
    ScopedRehearsalDispatch,
    ScopedRehearsalDispatchError,
)
from rocell.safety.effects import EffectCertainty, EffectClass
from test_commissioning_m1_persistence import CELL, SESSION, SOURCE, FIRST, _runtime
from test_commissioning_coordinator import _components


LEASES = (
    LeaseSpec(LeaseLevel.CELL, CELL),
    LeaseSpec(LeaseLevel.SESSION, SESSION),
    LeaseSpec(LeaseLevel.ARM_CONTROLLER, CELL),
)
REQUEST = RegisteredActionRequest(CELL, SESSION, ACTION_ID, "scoped-request", "a" * 64)


@pytest.fixture(params=sorted(ACTION_IDS))
def action_request(request):
    """Both exact production action IDs; this selects no worker or device."""
    return replace(REQUEST, action_id=request.param)


def fixture_store(*, fail_exit=False):
    """Exact classes with explicit no-OS bodies for context mechanics only."""
    store = object.__new__(M1CommissioningPersistence)
    transaction = object.__new__(M1RehearsalTransaction)
    transaction._active = True
    transaction._held = SimpleNamespace(
        closed=False,
        owners=tuple(
            SimpleNamespace(level=x.level, resource_id=x.resource_id) for x in LEASES
        ),
    )
    transaction._guard = lambda: None
    transaction._specs = LEASES
    counts = {"enter": 0, "exit": 0, "read": 0}

    def read(request):
        counts["read"] += 1
        return request

    transaction.read_admission = read
    transaction.read_envelope = lambda request: None

    @contextmanager
    def context(leases):
        assert leases == LEASES
        counts["enter"] += 1
        try:
            yield transaction
        finally:
            counts["exit"] += 1
            transaction.close_scope()
            transaction._held.closed = True
            if fail_exit:
                raise OSError("fixture lease close failed")

    store.transaction = context
    return store, transaction, counts


def test_inert_construction_status_then_one_real_context_for_two_core_contexts(
    action_request,
):
    store, real, counts = fixture_store()
    window = ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    )
    assert counts == {"enter": 0, "exit": 0, "read": 0}
    assert not window.status()["entered"]
    with window:
        assert window.preflight_transaction is real
        actual = replace(action_request, expected_challenge_sha256="b" * 64)
        window.bind_request(actual)
        with window.transaction(LEASES) as first:
            assert first.read_admission(actual) == actual
            assert first.read_envelope(actual) is None
            assert first.held_leases == LEASES
        assert counts["exit"] == 0
        with pytest.raises(ScopedRehearsalDispatchError, match="ENDED"):
            first.read_admission(actual)
        with window.transaction(LEASES) as second:
            second.read_admission(actual)
        assert counts == {"enter": 1, "exit": 1, "read": 2}
        assert window.status()["closed"]
    assert counts["exit"] == 1
    with pytest.raises(ScopedRehearsalDispatchError):
        window.__enter__()


@pytest.mark.parametrize(
    "case",
    [
        "no-bind",
        "wrong-leases",
        "wrong-request",
        "nested",
        "prepare-write",
        "unknown-method",
        "preflight-after-bind",
        "third",
    ],
)
def test_closed_proxy_order_and_binding(case, action_request):
    store, _, counts = fixture_store()
    with ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    ) as window:
        if case == "no-bind":
            with pytest.raises(ScopedRehearsalDispatchError):
                with window.transaction(LEASES):
                    pytest.fail("unbound dispatch")
            return
        window.bind_request(action_request)
        if case == "preflight-after-bind":
            with pytest.raises(ScopedRehearsalDispatchError):
                _ = window.preflight_transaction
        if case == "wrong-leases":
            with pytest.raises(ScopedRehearsalDispatchError):
                with window.transaction(LEASES[:2]):
                    pytest.fail("substituted leases")
        with window.transaction(LEASES) as first:
            if case == "wrong-request":
                with pytest.raises(ScopedRehearsalDispatchError):
                    first.read_admission(replace(action_request, request_key="other"))
            if case == "nested":
                with pytest.raises(ScopedRehearsalDispatchError):
                    with window.transaction(LEASES):
                        pytest.fail("nested dispatch")
            if case == "prepare-write":
                with pytest.raises(ScopedRehearsalDispatchError):
                    first.consume_permit(None)
            if case == "unknown-method":
                with pytest.raises(AttributeError):
                    first.store_evidence
        if case == "third":
            with window.transaction(LEASES):
                pass
            with pytest.raises(ScopedRehearsalDispatchError):
                with window.transaction(LEASES):
                    pytest.fail("third dispatch")
    assert counts["exit"] == 1


@pytest.mark.parametrize("phase", [0, 1, 2])
def test_exception_closes_original_context_once(phase, action_request):
    store, _, counts = fixture_store()
    window = ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    )
    with pytest.raises(ValueError, match="primary"):
        with window:
            if phase == 0:
                raise ValueError("primary")
            window.bind_request(action_request)
            with window.transaction(LEASES):
                if phase == 1:
                    raise ValueError("primary")
            with window.transaction(LEASES):
                raise ValueError("primary")
    assert counts["enter"] == counts["exit"] == 1 and window.status()["closed"]


def test_final_cleanup_exception_escapes_second_context_not_outer_close(action_request):
    store, _, counts = fixture_store(fail_exit=True)
    window = ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    )
    with window:
        window.bind_request(action_request)
        with window.transaction(LEASES):
            pass
        with pytest.raises(OSError, match="lease close failed"):
            with window.transaction(LEASES):
                pass
        assert window.status()["cleanup_uncertain"]
    assert counts["exit"] == 1


def test_wrong_types_actions_request_rebinding_and_threads_are_refused(action_request):
    store, _, _ = fixture_store()
    with pytest.raises(ScopedRehearsalDispatchError):
        ScopedRehearsalDispatch(
            persistence=SimpleNamespace(composition=INCAPABLE_COMPOSITION),
            leases=LEASES,
            request=action_request,
        )
    with pytest.raises(ScopedRehearsalDispatchError):
        ScopedRehearsalDispatch(
            persistence=store,
            leases=LEASES,
            request=replace(action_request, action_id="physical-arm"),
        )
    with ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    ) as window:
        with pytest.raises(ScopedRehearsalDispatchError):
            window.bind_request(replace(action_request, request_key="other"))
        window.bind_request(action_request)
        with pytest.raises(ScopedRehearsalDispatchError):
            window.bind_request(action_request)
        errors = []

        def other_thread():
            try:
                with window.transaction(LEASES):
                    pass
            except ScopedRehearsalDispatchError as error:
                errors.append(error)

        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join(2)
        assert not thread.is_alive() and len(errors) == 1


@pytest.mark.parametrize(
    "action_id",
    [
        "physical-arm",
        "rehearsal-camera-capture",
        "rehearsal-arm-feedback-extra",
        "rehearsal-owned-arm-feedback-extra",
        "REHEARSAL-ARM-FEEDBACK",
    ],
)
def test_closed_allowlist_has_only_two_exact_actions_and_denials_are_inert(action_id):
    assert ACTION_ID == "rehearsal-owned-arm-feedback"
    assert ACTION_IDS == frozenset(
        {"rehearsal-arm-feedback", "rehearsal-owned-arm-feedback"}
    )
    store, _, counts = fixture_store()
    with pytest.raises(
        ScopedRehearsalDispatchError, match="CLOSED_REHEARSAL_FEEDBACK_ACTION_REQUIRED"
    ):
        ScopedRehearsalDispatch(
            persistence=store,
            leases=LEASES,
            request=replace(REQUEST, action_id=action_id),
        )
    assert counts == {"enter": 0, "exit": 0, "read": 0}


@pytest.mark.parametrize("field", ["action_id", "cell_id", "session_id", "request_key"])
def test_bound_request_cannot_switch_lanes_or_original_context(action_request, field):
    store, _, counts = fixture_store()
    changed = (
        next(value for value in ACTION_IDS if value != action_request.action_id)
        if field == "action_id"
        else "substituted-original"
    )
    other = replace(action_request, **{field: changed})
    with ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    ) as window:
        with pytest.raises(
            ScopedRehearsalDispatchError, match="BOUND_REQUEST_SUBSTITUTED"
        ):
            window.bind_request(other)
        window.bind_request(action_request)
        with window.transaction(LEASES) as transaction:
            with pytest.raises(
                ScopedRehearsalDispatchError, match="EXACT_BOUND_REQUEST_REQUIRED"
            ):
                transaction.read_admission(other)
    assert counts == {"enter": 1, "exit": 1, "read": 0}


@pytest.mark.parametrize(
    "case", ["subclass", "composition", "lease-list", "lease-order"]
)
def test_exact_store_composition_and_lease_contracts_remain_closed(
    case, action_request
):
    store, _, counts = fixture_store()
    leases = LEASES
    if case == "subclass":

        class DerivedPersistence(M1CommissioningPersistence):
            pass

        store = object.__new__(DerivedPersistence)
    elif case == "composition":
        store.composition = "PHYSICAL_DIAGNOSTIC"
    elif case == "lease-list":
        leases = list(LEASES)
    elif case == "lease-order":
        leases = tuple(reversed(LEASES))
    with pytest.raises(ScopedRehearsalDispatchError):
        ScopedRehearsalDispatch(
            persistence=store, leases=leases, request=action_request
        )
    assert counts == {"enter": 0, "exit": 0, "read": 0}


class NoDeviceWorker:
    """Storage lifecycle fixture: no child, serial, camera or physical evidence."""

    composition = INCAPABLE_COMPOSITION
    worker_executable_sha256 = "b" * 64

    def __init__(self):
        self.calls = 0
        self.deadline_ns = None

    def run_campaign(self, permit, *, deadline_ns, cancellation):
        self.calls += 1
        self.deadline_ns = deadline_ns
        assert deadline_ns <= permit.expires_at_ns
        assert deadline_ns <= permit.envelope.expires_at_ns
        return WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED,
            True,
            ObservedPowerState.DEENERGIZED,
            0,
            0,
            0,
            0,
            0,
            0,
            (),
        )


@pytest.mark.parametrize(
    "fault", ["nominal", "changed-facts", "cancel", "exit-failure", "prepare-only"]
)
def test_actual_m1_one_acquisition_fresh_reads_and_core_cleanup(
    tmp_path, monkeypatch, fault, action_request
):
    # A small real stage-one cell isolates lease/coordinator mechanics. The
    # action label is bound. A simulated manual-energy category requires the
    # same ARM lease and original energy envelope; the fixture performs no
    # effects. This is not canonical stage12 feedback or physical power evidence.
    runtime, store = _runtime(tmp_path)
    epoch = [0]
    envelope = [None]
    store._admission_facts = lambda request, snapshot: RehearsalAdmissionFacts(
        {"source": SOURCE, "incapable_storage_fixture": True},
        tuple({"epoch": index, "revision": epoch[0]} for index in range(8)),
        {"incapable_controller": True},
        envelope=envelope[0],
    )
    worker = NoDeviceWorker()
    registration = CampaignRegistration(
        action_request.action_id,
        FIRST,
        EffectClass.MANUAL_ENERGY_CHANGE,
        "no-device-scope-fixture",
        worker.worker_executable_sha256,
        "d" * 64,
        (LeaseLevel.ARM_CONTROLLER,),
        CampaignBudget(
            20_000 if action_request.action_id == ACTION_ID else 10_000,
            1024,
            0,
            0,
            0,
            0,
            0,
        ),
    )
    counts = {"enter": 0, "exit": 0, "admission": 0}
    timings = []
    actual_context = store.transaction
    actual_read = M1RehearsalTransaction.read_admission

    @contextmanager
    def context(leases):
        counts["enter"] += 1
        started = time.monotonic_ns()
        try:
            with actual_context(leases) as tx:
                timings.append(("context_enter_ns", time.monotonic_ns() - started))
                yield tx
        finally:
            counts["exit"] += 1
        if fault == "exit-failure":
            raise OSError("injected failure after actual lease exit")

    def read(tx, request):
        counts["admission"] += 1
        started = time.monotonic_ns()
        try:
            return actual_read(tx, request)
        finally:
            timings.append(("fresh_admission_ns", time.monotonic_ns() - started))

    monkeypatch.setattr(store, "transaction", context)
    monkeypatch.setattr(M1RehearsalTransaction, "read_admission", read)
    with ScopedRehearsalDispatch(
        persistence=store, leases=LEASES, request=action_request
    ) as window:
        admission = window.preflight_transaction.read_admission(action_request)
        request = replace(
            action_request, expected_challenge_sha256=admission.challenge_sha256
        )
        _, model_store, _, _, _ = _components(serial=True)
        now = time.monotonic_ns()
        envelope[0] = replace(
            model_store.envelope,
            operation_sha256=registration.operation_sha256,
            issued_at_ns=now,
            expires_at_ns=now + 30_000_000_000,
            configuration_epoch_vector_sha256=hashlib.sha256(
                canonical_json_bytes(admission.configuration_epoch_hashes)
            ).hexdigest(),
        )
        window.bind_request(request)
        coordinator = CellCommissioningCoordinator(
            persistence=window,
            registrations=(registration,),
            workers={registration.worker_id: worker},
        )
        permit = coordinator.prepare(request)
        assert counts["enter"] == 1 and counts["exit"] == 0
        assert permit.envelope == envelope[0]
        assert (
            permit.envelope.expires_at_ns - permit.envelope.issued_at_ns
            == 30_000_000_000
        )
        assert permit.expires_at_ns == envelope[0].expires_at_ns
        assert permit.registration.budget.timeout_ms == (
            20_000 if action_request.action_id == ACTION_ID else 10_000
        )
        original_permit = permit
        cancellation = threading.Event()
        if fault == "prepare-only":
            # Outer close owns an abandoned prepare: no armed intent, worker,
            # second core context or automatic execute is synthesized.
            assert worker.calls == 0 and counts["exit"] == 0
            assert window.status()["coordinator_contexts_used"] == 1
        elif fault == "changed-facts":
            epoch[0] += 1
            with pytest.raises(CommissioningCoordinatorError, match="stale source"):
                coordinator.execute(permit, cancellation=cancellation)
            assert worker.calls == 0
        elif fault == "exit-failure":
            with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
                coordinator.execute(permit, cancellation=cancellation)
            assert worker.calls == 1
            with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
                coordinator.execute(permit)
        else:
            if fault == "cancel":
                cancellation.set()
            result = coordinator.execute(permit, cancellation=cancellation)
            assert result.state is (
                AttemptState.ABORTED_PRE_EFFECT
                if fault == "cancel"
                else AttemptState.SEALED_KNOWN
            )
            assert worker.calls == (0 if fault == "cancel" else 1)
            assert coordinator.execute(permit) == result
        assert permit is original_permit and permit.envelope == envelope[0]
        assert window.status()["envelope_renewed"] is False
        if fault != "prepare-only":
            assert window.status()["closed"] and counts["exit"] == 1
    assert counts["enter"] == counts["exit"] == 1
    assert window.status()["closed"]
    assert counts["admission"] == (
        2 if fault == "prepare-only" else 3 if fault == "changed-facts" else 4
    )
    final = runtime.verify(SESSION)
    assert not final.active_lease_owners
    if fault in {"changed-facts", "prepare-only"}:
        assert final.attempt_event_count == 0
    if fault == "exit-failure":
        assert final.attempt_event_count == 5 and not final.quarantined
    print(
        "isolated real M1 scoped timing",
        action_request.action_id,
        fault,
        counts,
        timings,
    )
