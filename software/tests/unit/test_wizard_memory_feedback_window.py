"""Service/coordinator memory-lane join, with explicitly modeled M1 I/O.

The service, one-window adapter, coordinator, exact campaign, serial worker and
sealed memory backend are real. M1 qualification/journal methods are replaced
by the existing memory protocol fixture; this is not an NTFS durability proof.
No preserved incident store, port, native process or OS metadata is accessed.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import arm_feedback_rehearsal_campaign as campaign
from rocell.application import cell_commissioning_coordinator as core
from rocell.application import commissioning_rehearsal_service as service_module
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistence,
    M1RehearsalTransaction,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.rehearsal_feedback_binding import (
    RehearsalFeedbackBinding,
    ReviewedFeedbackPredecessor,
)
from rocell.application.scoped_rehearsal_dispatch import ScopedRehearsalDispatch
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows import arm_feedback_worker as arm
from test_arm_feedback_rehearsal_campaign import components
from test_wizard_feedback_stage_integration import StageTransaction


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def forbid_hardware_and_owned_fallback(monkeypatch):
    from rocell.application import owned_arm_feedback_rehearsal_campaign as owned
    from rocell.application import physical_device_inventory as inventory

    def forbidden(*args, **kwargs):
        pytest.fail("Memory feedback must never switch to owned/native/OS inventory")

    monkeypatch.setattr(owned, "prepare_owned_arm_feedback_campaign", forbidden)
    monkeypatch.setattr(arm.WindowsPySerialBackend, "require_available", forbidden)
    monkeypatch.setattr(arm.WindowsPySerialBackend, "create_closed", forbidden)
    for name in (
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
        "inventory_serial_ports_with_pyserial",
    ):
        monkeypatch.setattr(inventory, name, forbidden)


def fixture(tmp_path, monkeypatch, *, fault=None, preflight_delay_ns=0):
    """No-OS transaction bodies inside the adapter's exact M1 type boundary."""
    _, memory, initial_worker, clock, _ = components()
    initial = initial_worker.plan
    binding = RehearsalFeedbackBinding(
        initial.source_sha256,
        "b" * 64,
        memory.snapshot.cell_id,
        memory.snapshot.session_id,
        memory.envelope.operator_id,
        tuple(
            ReviewedFeedbackPredecessor(
                stage.value,
                (
                    initial.controller.identity_receipt_sha256
                    if index == 0
                    else str(index + 1) * 64
                ),
                "c" * 64,
                "d" * 64,
                "e" * 64,
            )
            for index, stage in enumerate(STAGE_ORDER[8:11])
        ),
        initial.controller,
    )
    service = service_module.CommissioningRehearsalService(
        WORKSPACE,
        tmp_path / "never-created-store",
        source_sha256=binding.workspace_source_sha256,
    )
    service.cell_id, service.session_id, service._operator = (
        binding.cell_id,
        binding.session_id,
        binding.operator_id,
    )
    service._cached.update(
        stage=STAGE_ORDER[11].value,
        stage_state="WAITING_OPERATOR",
        challenge_sha256="1" * 64,
    )
    stage = StageTransaction(service)
    stage.current.next_action.stage_state = V2StageState.WAITING_OPERATOR
    monkeypatch.setattr(service, "_transaction", lambda: stage)
    monkeypatch.setattr(service, "_feedback_context", lambda tx: (binding, {}))
    monkeypatch.setattr(service, "_refresh", lambda: None)
    stored = []
    monkeypatch.setattr(
        service,
        "_store_json",
        lambda tx, stage, doc, label: stored.append(deepcopy(doc))
        or SimpleNamespace(evidence_id="modeled-stage-evidence"),
    )
    monkeypatch.setattr(
        service,
        "_facts",
        lambda *args: SimpleNamespace(
            hazard_assessment_document={"fixture": "NOT_PHYSICAL_AUTHORITY"},
            configuration_epoch_documents=tuple({"epoch": index} for index in range(8)),
        ),
    )
    cancellation = Event()
    counts = {"enter": 0, "exit": 0, "read": 0}
    envelopes, workers, coordinators, preflight = [], [], [], []
    leases = (
        LeaseSpec(LeaseLevel.CELL, binding.cell_id),
        LeaseSpec(LeaseLevel.SESSION, binding.session_id),
        LeaseSpec(LeaseLevel.ARM_CONTROLLER, binding.cell_id),
    )
    exact_store = object.__new__(M1CommissioningPersistence)
    exact_tx = object.__new__(M1RehearsalTransaction)
    exact_tx._active = True
    exact_tx._held = SimpleNamespace(
        closed=False,
        owners=tuple(
            SimpleNamespace(level=row.level, resource_id=row.resource_id)
            for row in leases
        ),
    )
    exact_tx._specs = leases
    exact_tx._guard = lambda: None
    exact_tx.verification = lambda: SimpleNamespace(challenge_sha256="1" * 64)

    def read(request):
        counts["read"] += 1
        facts = service._feedback_admission
        assert facts is not None
        if counts["read"] == 1:
            assert facts.envelope is None
            preflight.append(facts)
            clock.value += preflight_delay_ns
            if fault == "stop-preflight":
                cancellation.set()
        memory.snapshot = replace(
            memory.snapshot,
            hazard_assessment_sha256=hashlib.sha256(facts._hazard).hexdigest(),
            configuration_epoch_hashes=tuple(
                hashlib.sha256(payload).hexdigest() for payload in facts._epochs
            ),
            selected_identity_sha256=hashlib.sha256(facts._identity).hexdigest(),
        )
        if counts["read"] == 3 and fault == "source-before-execute":
            memory.snapshot = replace(memory.snapshot, source_binding_sha256="f" * 64)
        return memory.read_admission(request)

    def envelope(request):
        value = service._feedback_admission.envelope
        envelopes.append(value)
        return value

    exact_tx.read_admission = read
    exact_tx.read_envelope = envelope
    for name in (
        "begin_intent",
        "assert_consumed_permit",
        "retain_campaign_evidence",
        "transition",
        "retain_result",
        "seal_uncertain",
    ):
        setattr(exact_tx, name, getattr(memory, name))
    consume = memory.consume_permit

    def armed(permit):
        consume(permit)
        if fault == "late-arm":
            clock.value += 20_000_000_001
        elif fault == "stop-armed":
            cancellation.set()
        elif fault == "arm-write-failure":
            raise OSError("Modeled ambiguous arming publication")

    exact_tx.consume_permit = armed

    @contextmanager
    def transaction(requested_leases):
        assert requested_leases == leases
        counts["enter"] += 1
        assert counts["enter"] == 1, "Service reacquired the dispatch-window leases"
        with memory.transaction(leases):
            try:
                yield exact_tx
            finally:
                counts["exit"] += 1
                exact_tx.close_scope()
                exact_tx._held.closed = True
                if fault == "lease-exit":
                    raise OSError("Modeled lease release uncertainty")

    exact_store.transaction = transaction
    service._store = exact_store
    original_worker = campaign.ArmFeedbackRehearsalCampaign

    def memory_worker(plan, *, worker_executable_sha256):
        value = original_worker(
            plan,
            worker_executable_sha256=worker_executable_sha256,
            monotonic_ns=clock,
            wait=clock.wait,
        )
        workers.append(value)
        return value

    monkeypatch.setattr(campaign, "ArmFeedbackRehearsalCampaign", memory_worker)
    original_coordinator = core.CellCommissioningCoordinator

    def coordinator(**kwargs):
        assert type(kwargs["persistence"]) is ScopedRehearsalDispatch
        assert (
            kwargs["scoped_campaign_actions"] == ()
        )  # Memory callback protocol remains unchanged.
        assert kwargs["retained_campaign_actions"] == ("rehearsal-arm-feedback",)
        assert len(kwargs["workers"]) == len(kwargs["registrations"]) == 1
        assert type(next(iter(kwargs["workers"].values()))) is original_worker
        assert kwargs["registrations"][0].budget.timeout_ms == 10000
        value = original_coordinator(**kwargs, monotonic_ns=clock)
        coordinators.append(value)
        return value

    monkeypatch.setattr(service_module, "CellCommissioningCoordinator", coordinator)
    monkeypatch.setattr(service_module, "time", SimpleNamespace(monotonic_ns=clock))
    return SimpleNamespace(
        service=service,
        binding=binding,
        memory=memory,
        clock=clock,
        counts=counts,
        envelopes=envelopes,
        workers=workers,
        coordinators=coordinators,
        preflight=preflight,
        cancellation=cancellation,
        stored=stored,
        leases=leases,
        exact=exact_store,
    )


def assert_fixed_admission(value):
    assert len(value.workers) == len(value.coordinators) == 1
    assert value.counts == {"enter": 1, "exit": 1, "read": 3}
    assert len(value.envelopes) == 2
    assert value.envelopes[0] is value.envelopes[1]
    envelope = value.envelopes[0]
    assert envelope.expires_at_ns - envelope.issued_at_ns == 30_000_000_000
    assert value.workers[0].registration().budget.timeout_ms == 10000
    assert value.workers[0].registration().action_id == "rehearsal-arm-feedback"
    assert len(value.preflight) == 1 and value.preflight[0].envelope is None
    assert value.service._feedback_admission is None
    assert not value.service.directory.exists()
    assert not value.memory.held_leases


@pytest.mark.parametrize("preflight_delay_ns", [0, 40_000_000_000])
def test_memory_lane_uses_one_window_fresh_reads_and_original_fixed_budgets(
    tmp_path, monkeypatch, preflight_delay_ns
):
    value = fixture(tmp_path, monkeypatch, preflight_delay_ns=preflight_delay_ns)
    value.service._feedback_campaign(value.cancellation)
    assert_fixed_admission(value)
    assert (
        len(value.memory.permits)
        == len(value.memory.results)
        == len(value.memory.evidence)
        == 1
    )
    permit = next(iter(value.memory.permits.values()))
    result = next(iter(value.memory.results.values()))
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.receipt.opens == result.receipt.writes == result.receipt.closes == 1
    worker = value.workers[0]
    assert worker.evidence is not None
    assert (
        worker.evidence.safe_summary()["final_power_state"]
        == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    assert worker.evidence.final_power_observation["physical_observation"] is False
    assert worker.evidence.to_dict()["actual_effect_counts"] == {
        key: 0 for key in worker.evidence.to_dict()["actual_effect_counts"]
    }
    assert value.memory.trace.count("EXACT_ARMED_AUTHORIZATION") == 1
    assert value.memory.trace.count("FULL_EVIDENCE_RETAINED") == 1
    assert (
        value.memory.trace.index("EFFECT_ARMED")
        < value.memory.trace.index("EXACT_ARMED_AUTHORIZATION")
        < value.memory.trace.index("FULL_EVIDENCE_RETAINED")
    )
    assert permit.envelope is value.envelopes[0]
    assert permit.envelope.issued_at_ns > 1_000_000_000 + preflight_delay_ns
    assert permit.expires_at_ns <= permit.envelope.expires_at_ns
    assert len(value.stored) == 1
    assert value.stored[0]["schema"] == "rocell.rehearsal_feedback_receipt.v1"
    assert "arm_feedback_process" not in value.stored[0]
    assert value.service._arm_feedback_process is None
    assert value.service._latest_arm_feedback["outcome"] == "REHEARSAL_CHECKS_PASSED"
    assert value.coordinators[0].execute(permit) is result
    assert len(value.memory.evidence) == 1 and value.counts["enter"] == 1


@pytest.mark.parametrize("fault", ["late-arm", "arm-write-failure"])
def test_post_arm_budget_or_write_failure_retains_uncertainty_without_worker(
    tmp_path, monkeypatch, fault
):
    value = fixture(tmp_path, monkeypatch, fault=fault)
    value.service._feedback_campaign(value.cancellation)
    assert_fixed_admission(value)
    assert len(value.memory.permits) == len(value.memory.results) == 1
    result = next(iter(value.memory.results.values()))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.receipt is None
    assert "WORKER_OR_POST_ARM_PUBLICATION_FAILED" in result.reason_codes
    assert value.workers[0].status()["consumed"] is False
    assert value.workers[0].evidence is None and not value.memory.evidence
    assert not value.memory.authorized and not value.stored
    assert value.service._receipt is None and value.service._latest_arm_feedback is None
    assert value.service._failed is True
    assert (
        value.service.retained_feedback_diagnostics()["attempt_result"]["state"]
        == "SEALED_UNCERTAIN"
    )
    assert value.memory.trace.count("QUARANTINE_LATCHED") == 1
    assert value.memory.trace.count("LEASES_RELEASED") == 1


def test_stop_at_preflight_never_issues_an_envelope_or_permit(tmp_path, monkeypatch):
    value = fixture(tmp_path, monkeypatch, fault="stop-preflight")
    with pytest.raises(WizardError, match="[Cc]ancel|Stop"):
        value.service._feedback_campaign(value.cancellation)
    assert value.counts == {"enter": 1, "exit": 1, "read": 1}
    assert (
        not value.envelopes and not value.memory.permits and not value.memory.attempts
    )
    assert value.workers[0].status()["consumed"] is False
    assert value.service._feedback_admission is None
    assert not value.stored and not value.service.directory.exists()


def test_stop_after_arming_cannot_dispatch_memory_io_or_restore_acceptance(
    tmp_path, monkeypatch
):
    value = fixture(tmp_path, monkeypatch, fault="stop-armed")
    value.service._feedback_campaign(value.cancellation)
    assert_fixed_admission(value)
    result = next(iter(value.memory.results.values()))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    # The already-armed memory worker may return a zero-I/O cancellation record;
    # no acknowledgement or complete M1 campaign-evidence publication follows.
    assert result.receipt.opens == result.receipt.writes == result.receipt.closes == 0
    worker = value.workers[0]
    assert worker.evidence.safe_summary()["worker_outcome"] == "CANCELLED_PRE_OPEN"
    assert all(
        count == 0 for count in worker.evidence.safe_summary()["api_counts"].values()
    )
    assert not value.memory.authorized
    assert not value.memory.evidence and not value.stored
    assert value.service._latest_arm_feedback["outcome"] == "BLOCKED"


def test_fresh_source_change_before_execute_rejects_without_durable_intent(
    tmp_path, monkeypatch
):
    value = fixture(tmp_path, monkeypatch, fault="source-before-execute")
    with pytest.raises(core.CommissioningCoordinatorError):
        value.service._feedback_campaign(value.cancellation)
    assert value.counts == {"enter": 1, "exit": 1, "read": 3}
    assert (
        not value.memory.permits
        and not value.memory.attempts
        and not value.memory.evidence
    )
    assert value.workers[0].status()["consumed"] is False
    assert value.service._feedback_admission is None
    assert not value.stored


def test_memory_late_lease_exit_preserves_historical_evidence_not_current_pass(
    tmp_path, monkeypatch
):
    value = fixture(tmp_path, monkeypatch, fault="lease-exit")
    with pytest.raises(core.CommissioningCoordinatorError, match="cleanup"):
        value.service._feedback_campaign(value.cancellation)
    assert_fixed_admission(value)
    worker = value.workers[0]
    assert worker.evidence is not None
    assert len(value.memory.evidence) == len(value.memory.results) == 1
    # Model journal retained a known result before its context failed; do not
    # rewrite that history or treat it as successful outer cleanup/publication.
    result = next(iter(value.memory.results.values()))
    assert result.state is AttemptState.SEALED_KNOWN
    retained = value.service.retained_feedback_diagnostics()
    assert retained["attempt_result"] is None
    assert retained["m1_retention"] == "UNCONFIRMED_AFTER_EXCEPTION"
    assert retained["coordinator_completion"] == "UNCONFIRMED_EXCEPTION"
    assert retained["retained_campaign_sha256"] == worker.evidence.evidence_sha256
    assert retained["safe_summary"] == worker.evidence.safe_summary()
    assert "arm_feedback_process" not in retained
    assert value.service._receipt is None and value.service._latest_arm_feedback is None
    assert not value.stored
    trace = list(value.memory.trace)
    with pytest.raises(core.CommissioningCoordinatorError, match="cleanup"):
        value.coordinators[0].execute(next(iter(value.memory.permits.values())))
    assert value.memory.trace == trace
