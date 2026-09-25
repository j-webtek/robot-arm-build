"""Stage-12 wiring using actual incapable campaigns and isolated audited inputs.

The record dictionaries and session snapshots below stand for the caller's
already-completed M1 audit. They are NOT disk durability, lease qualification,
received-arm identity, or physical power evidence. A small Windows-only qualified
evidence-package roundtrip checks receipt serialization, not stage-12 admission;
root's real-store progression covers the complete workflow separately. No host
inventory or native serial is used.
"""

from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import arm_feedback_rehearsal_campaign as campaign
from rocell.application import arrival_wizard_service as arrival
from rocell.application import cell_commissioning_coordinator as core
from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application import commissioning_rehearsal_service as service_module
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.rehearsal_feedback_binding import (
    RehearsalFeedbackBinding,
    ReviewedFeedbackPredecessor,
)
from rocell.application.rehearsal_feedback_stage import (
    feedback_evaluation,
    feedback_plan,
    feedback_power_dependencies,
)
from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.providers.windows import arm_feedback_worker as arm
from test_arm_feedback_rehearsal_campaign import components


WORKSPACE = Path(__file__).resolve().parents[3]
STAGE = STAGE_ORDER[11]
ACTION = "rehearsal_arm_feedback_campaign"


def plain(value):
    """Match ordinary canonical JSON's enum/tuple conversion, without files."""
    return json.loads(json.dumps(value))


@pytest.fixture(autouse=True)
def no_native_backend(monkeypatch):
    from rocell.application import physical_device_inventory as inventory

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Stage integration must not enumerate hardware or use native serial"
        )

    monkeypatch.setattr(arm.WindowsPySerialBackend, "require_available", forbidden)
    monkeypatch.setattr(arm.WindowsPySerialBackend, "create_closed", forbidden)
    for name in (
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
        "inventory_serial_ports_with_pyserial",
    ):
        monkeypatch.setattr(inventory, name, forbidden)


def actual_campaign():
    """Run the real coordinator/worker against the sealed memory-only backend."""
    _, store, initial_worker, clock, _ = components()
    initial_plan = initial_worker.plan
    binding = RehearsalFeedbackBinding(
        initial_plan.source_sha256,
        "b" * 64,
        store.snapshot.cell_id,
        store.snapshot.session_id,
        store.envelope.operator_id,
        tuple(
            ReviewedFeedbackPredecessor(
                stage.value,
                (
                    initial_plan.controller.identity_receipt_sha256
                    if index == 0
                    else str(index + 1) * 64
                ),
                "c" * 64,
                "d" * 64,
                "e" * 64,
            )
            for index, stage in enumerate(STAGE_ORDER[8:11])
        ),
        initial_plan.controller,
    )
    plan = feedback_plan(binding)
    worker = campaign.ArmFeedbackRehearsalCampaign(
        plan,
        worker_executable_sha256=hashlib.sha256(
            Path(campaign.__file__).read_bytes()
        ).hexdigest(),
        monotonic_ns=clock,
        wait=clock.wait,
    )
    registration = worker.registration()
    store.envelope = replace(
        store.envelope,
        operation_sha256=registration.operation_sha256,
        observer_id=plan.final_power_observation.observer_id,
        **feedback_power_dependencies(binding),
    )
    coordinator = core.CellCommissioningCoordinator(
        persistence=store,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
        monotonic_ns=clock,
    )
    request = core.RegisteredActionRequest(
        binding.cell_id,
        binding.session_id,
        registration.action_id,
        "stage-integration-request",
        store.snapshot.challenge_sha256,
    )
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, result.reason_codes
    artifact = worker.evidence
    assert artifact is not None
    evaluated = feedback_evaluation(binding, artifact)
    document = {
        "schema": "rocell.rehearsal_feedback_receipt.v1",
        "operator_id": binding.operator_id,
        "evaluation": evaluated.to_dict(),
        "evaluation_sha256": evaluated.evidence_sha256,
        "attempt_result": plain(asdict(result)),
        "retained_campaign_sha256": artifact.evidence_sha256,
    }
    records = {
        "result": {
            "kind": "CAMPAIGN_RESULT",
            "data": {"result": document["attempt_result"]},
        },
        "reservation": {
            "kind": "EXACT_REQUEST_RESERVED",
            "data": {
                "attempt_id": permit.attempt_id,
                "permit": plain(asdict(permit)),
            },
        },
        "raw": {
            "kind": "CAMPAIGN_EVIDENCE",
            "data": {
                "attempt_id": permit.attempt_id,
                "permit_sha256": permit.permit_sha256,
                "evidence": [
                    {
                        "schema": blob.schema,
                        "label": blob.label,
                        "payload_bytes": len(blob.payload),
                        "payload_sha256": blob.payload_sha256,
                        "payload_base64": base64.b64encode(blob.payload).decode(
                            "ascii"
                        ),
                    }
                    for blob in store.evidence[permit.attempt_id]
                ],
            },
        },
    }
    return SimpleNamespace(
        binding=binding,
        coordinator=coordinator,
        store=store,
        worker=worker,
        permit=permit,
        result=result,
        artifact=artifact,
        evaluated=evaluated,
        document=document,
        records=records,
        snapshot=SimpleNamespace(
            header=SimpleNamespace(
                cell_id=binding.cell_id, session_id=binding.session_id
            )
        ),
    )


@pytest.fixture
def retained(monkeypatch):
    value = actual_campaign()
    calls = []

    def expected_binding(snapshot, evidence, operator, source, catalog):
        calls.append((snapshot, evidence, operator, source, catalog))
        assert operator == value.binding.operator_id
        assert source == value.binding.workspace_source_sha256
        assert catalog == value.binding.catalog_sha256
        return value.binding, None

    monkeypatch.setattr(reopen, "_feedback_binding", expected_binding)
    value.binding_calls = calls
    return value


def verify_retained(value, *, document=None, records=None):
    selected = value.document if document is None else document
    reference = SimpleNamespace(stage=STAGE, evidence_id="feedback-receipt")
    receipt = SimpleNamespace(reference=reference, document=lambda: deepcopy(selected))
    return reopen._verify_evaluated_receipt(
        value.snapshot,
        {},
        receipt,
        value.binding.workspace_source_sha256,
        value.binding.catalog_sha256,
        records=value.records if records is None else records,
    )


def test_actual_retained_campaign_is_verified_without_replaying_worker(
    retained, monkeypatch
):
    before = list(retained.store.trace)

    def forbidden(*args, **kwargs):
        pytest.fail("Retained assessment/reopen verification replayed a worker")

    monkeypatch.setattr(
        campaign.ArmFeedbackRehearsalCampaign, "run_campaign", forbidden
    )
    monkeypatch.setattr(
        campaign.ArmFeedbackRehearsalCampaign, "run_retained_campaign", forbidden
    )
    evaluated = verify_retained(retained)
    assert evaluated.to_dict() == retained.evaluated.to_dict()
    assert evaluated.outcome == "REHEARSAL_CHECKS_PASSED"
    assert retained.store.trace == before
    assert len(retained.binding_calls) == 1


@pytest.mark.parametrize("record", ["result", "reservation", "raw"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_every_exact_audited_record_is_required_once(retained, record, mutation):
    records = deepcopy(retained.records)
    if mutation == "missing":
        records.pop(record)
    else:
        records["duplicate"] = deepcopy(records[record])
    with pytest.raises(reopen.RehearsalReopenError) as error:
        verify_retained(retained, records=records)
    assert error.value.code == "FEEDBACK_CAMPAIGN_RECORD_MISMATCH"


@pytest.mark.parametrize(
    "field", ["evaluation", "evaluation_sha256", "retained_campaign_sha256"]
)
def test_cached_projection_or_selected_hash_cannot_substitute_for_retained_bytes(
    retained, field
):
    document = deepcopy(retained.document)
    if field == "evaluation":
        document[field]["checks"][0]["passed"] = False
    else:
        document[field] = "0" * 64
    with pytest.raises(reopen.RehearsalReopenError):
        verify_retained(retained, document=document)


@pytest.mark.parametrize("mutation", ["bytes", "hash", "wrong-permit", "empty"])
def test_private_complete_record_tampering_is_rejected(retained, mutation):
    records = deepcopy(retained.records)
    data = records["raw"]["data"]
    if mutation == "bytes":
        data["evidence"][0]["payload_base64"] = "e30="
    elif mutation == "hash":
        data["evidence"][0]["payload_sha256"] = "0" * 64
    elif mutation == "wrong-permit":
        data["permit_sha256"] = "0" * 64
    else:
        data["evidence"] = []
    with pytest.raises(M1CommissioningPersistenceError):
        verify_retained(retained, records=records)


def test_reopen_dispatch_requires_audited_records(retained):
    receipt = SimpleNamespace(
        reference=SimpleNamespace(stage=STAGE),
        document=lambda: retained.document,
    )
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_evaluated_receipt(
            retained.snapshot,
            {},
            receipt,
            retained.binding.workspace_source_sha256,
            retained.binding.catalog_sha256,
        )
    assert error.value.code == "FEEDBACK_RECORDS_MISSING"


@pytest.mark.parametrize(
    "field", ["source", "catalog", "operator", "predecessor", "cell", "session"]
)
def test_retained_permit_cannot_be_rebound_to_different_reviewed_inputs(
    retained, field
):
    original = retained.binding
    if field == "source":
        retained.binding = replace(original, workspace_source_sha256="f" * 64)
    elif field == "catalog":
        retained.binding = replace(original, catalog_sha256="f" * 64)
    elif field == "operator":
        retained.binding = replace(original, operator_id="substituted-operator")
        retained.document["operator_id"] = retained.binding.operator_id
    elif field == "predecessor":
        prior = list(original.predecessors)
        prior[2] = replace(prior[2], review_sha256="f" * 64)
        retained.binding = replace(original, predecessors=tuple(prior))
    else:
        retained.binding = replace(original, **{field + "_id": "substituted"})
    with pytest.raises(reopen.RehearsalReopenError) as error:
        verify_retained(retained)
    assert error.value.code == "FEEDBACK_ADMISSION_BINDING_MISMATCH"


@pytest.fixture
def service(tmp_path):
    value = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "never-created-store", source_sha256="8" * 64
    )
    value._store = object()  # Status/action-gating fixture, not qualified storage.
    value._cached.update(stage=STAGE.value, stage_state="WAITING_OPERATOR")
    value._operator = "operator-1"
    return value


@pytest.mark.parametrize(
    "stage,state,operator,receipt,failed,quarantined,unresolved,allowed",
    [
        (STAGE.value, "WAITING_OPERATOR", "operator-1", None, False, False, [], True),
        (STAGE.value, "PENDING", "operator-1", None, False, False, [], False),
        (STAGE.value, "REVIEW_PENDING", "operator-1", None, False, False, [], False),
        (STAGE.value, "WAITING_OPERATOR", None, None, False, False, [], False),
        (STAGE.value, "WAITING_OPERATOR", "operator-1", {}, False, False, [], False),
        (
            STAGE_ORDER[10].value,
            "WAITING_OPERATOR",
            "operator-1",
            None,
            False,
            False,
            [],
            False,
        ),
        (STAGE.value, "WAITING_OPERATOR", "operator-1", None, True, False, [], False),
        (STAGE.value, "WAITING_OPERATOR", "operator-1", None, False, True, [], False),
        (
            STAGE.value,
            "WAITING_OPERATOR",
            "operator-1",
            None,
            False,
            False,
            ["old-attempt"],
            False,
        ),
    ],
)
def test_feedback_action_requires_due_waiting_stage_and_exact_operator(
    service, stage, state, operator, receipt, failed, quarantined, unresolved, allowed
):
    service._cached.update(
        stage=stage,
        stage_state=state,
        quarantined=quarantined,
        unresolved_attempt_ids=unresolved,
    )
    service._operator, service._receipt, service._failed = operator, receipt, failed
    assert (service.blocked_reason(ACTION) is None) is allowed
    assert not service.directory.exists()


class StageTransaction:
    """No-storage stage transaction for service call ordering only."""

    def __init__(self, service):
        self.commits = []
        self.stored = []
        self.current = SimpleNamespace(
            next_action=SimpleNamespace(stage=STAGE, stage_state=V2StageState.PENDING),
            header=SimpleNamespace(created_at_ns=1, source_binding_sha256="c" * 64),
            head=SimpleNamespace(head_sha256="d" * 64),
            committed_events=(),
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def snapshot(self):
        return self.current

    def store_evidence(self, stage, payload, **kwargs):
        self.stored.append(json.loads(payload))
        return SimpleNamespace(evidence_id="fixture-" + str(len(self.stored)))

    def commit_stage_state(self, stage, state, **kwargs):
        self.commits.append((stage, state, kwargs))
        self.current.next_action.stage_state = state


def test_collect_only_opens_feedback_stage_and_retains_operator(service, monkeypatch):
    tx = StageTransaction(service)
    contexts = []
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(
        service, "_feedback_context", lambda snapshot: contexts.append(snapshot)
    )
    monkeypatch.setattr(
        campaign,
        "ArmFeedbackRehearsalCampaign",
        lambda *a, **k: pytest.fail("Collect constructed/dispatched a serial campaign"),
    )
    service._collect({"operator_id": "operator-a"}, Event())
    assert len(contexts) == len(tx.stored) == len(tx.commits) == 1
    assert tx.stored[0]["schema"] == "rocell.rehearsal_feedback_stage_open.v1"
    assert tx.stored[0]["operator_id"] == "operator-a"
    assert tx.stored[0]["physical_observation"] is False
    assert service._receipt is None and service._assessment is None
    assert tx.commits[0][1] is V2StageState.WAITING_OPERATOR
    assert not service.directory.exists()


def test_stop_before_perform_does_not_mutate_or_dispatch(service, monkeypatch):
    values = service.bind(ACTION, {})
    cancellation = Event()
    cancellation.set()
    monkeypatch.setattr(
        service,
        "_feedback_campaign",
        lambda *a: pytest.fail("Cancelled action dispatched"),
    )
    with pytest.raises(WizardError) as error:
        service.perform(
            ACTION, values, cancellation=cancellation, progress=lambda _: None
        )
    assert error.value.code == "REHEARSAL_CANCELLED_BEFORE_MUTATION"
    assert service._receipt is None
    assert not service.directory.exists()


@pytest.mark.parametrize("stop_preflight", [None, "during-read", "before-envelope"])
def test_service_feedback_envelope_hashes_all_frozen_epochs_with_ledger_newline(
    service, monkeypatch, stop_preflight
):
    """The coordinator hashes the frozen epoch vector with its ledger codec.

    Stage receipt JSON intentionally uses a different codec. Capturing the
    actual service-built facts prevents the former newline mismatch from being
    hidden by the coordinator's otherwise-useful completed-result test proxy.
    """
    completed = actual_campaign()
    tx = StageTransaction(service)
    tx.current.next_action.stage_state = V2StageState.WAITING_OPERATOR
    seed_epochs = tuple(
        {"epoch_index": index, "fixture": {"name": "epoch-" + str(index)}}
        for index in range(8)
    )
    captured = []
    preflight_facts = []
    order = []
    clock = SimpleNamespace(value=1_000_000_000, preflight_finished=None)
    cancellation = Event()
    service._cached["challenge_sha256"] = "1" * 64

    class AdmissionCaptured(Exception):
        pass

    class PreflightTransaction:
        def __enter__(self):
            order.append("preflight-enter")
            return self

        def verification(self):
            return SimpleNamespace(challenge_sha256="1" * 64)

        def read_admission(self, request):
            preflight_facts.append(service._feedback_admission)
            assert service._feedback_admission.envelope is None
            # Advance a virtual 40 seconds without sleeping. This is longer
            # than the envelope's unchanged 30-second issuance window.
            clock.value += 40_000_000_000
            clock.preflight_finished = clock.value
            order.append("preflight-read")
            if stop_preflight == "during-read":
                cancellation.set()
            return SimpleNamespace(challenge_sha256="1" * 64)

        def __exit__(self, *args):
            clock.value += 1
            order.append("preflight-lease-release")
            return False

    class WindowFixture:
        """Model the lifetime seam; separate tests prove the exact M1 adapter."""

        def __init__(self, **kwargs):
            self.preflight_transaction = PreflightTransaction()

        def __enter__(self):
            self.preflight_transaction.__enter__()
            return self

        def __exit__(self, *args):
            return self.preflight_transaction.__exit__(*args)

        def bind_request(self, request):
            assert request.expected_challenge_sha256 == "1" * 64

    class CapturingCoordinator:
        def prepare(self, request):
            order.append("prepare")
            captured.append(service._feedback_admission)
            # This boundary captures actual fresh facts at prepare, but does
            # not reserve a permit or dispatch an additional memory worker.
            raise AdmissionCaptured()

        def execute(self, *args, **kwargs):
            pytest.fail("Admission timing test must not dispatch a worker")

    def create_coordinator(**kwargs):
        assert service._feedback_admission.envelope is None
        assert isinstance(kwargs["persistence"], WindowFixture)
        if stop_preflight == "before-envelope":
            cancellation.set()
        return CapturingCoordinator()

    def monotonic_ns():
        clock.value += 1
        order.append("envelope-time")
        return clock.value

    service._store = SimpleNamespace(transaction=lambda leases: PreflightTransaction())
    from rocell.application import scoped_rehearsal_dispatch

    monkeypatch.setattr(
        scoped_rehearsal_dispatch, "ScopedRehearsalDispatch", WindowFixture
    )
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_feedback_context", lambda _: (completed.binding, {}))
    monkeypatch.setattr(
        service,
        "_facts",
        lambda *args: SimpleNamespace(
            configuration_epoch_documents=seed_epochs,
            hazard_assessment_document={"fixture": "NO_PHYSICAL_AUTHORITY"},
        ),
    )
    monkeypatch.setattr(
        service_module, "CellCommissioningCoordinator", create_coordinator
    )
    # Replace this module's clock reference only; do not alter process-wide
    # time or the actual worker/coordinator fixture's independently owned clock.
    monkeypatch.setattr(
        service_module, "time", SimpleNamespace(monotonic_ns=monotonic_ns)
    )
    if stop_preflight is None:
        with pytest.raises(AdmissionCaptured):
            service._feedback_campaign(cancellation)
        assert len(captured) == 1
        facts = captured[0]
        assert order == [
            "preflight-enter",
            "preflight-read",
            "envelope-time",
            "prepare",
            "preflight-lease-release",
        ]
        assert facts.envelope.issued_at_ns > clock.preflight_finished
        assert (
            facts.envelope.expires_at_ns - facts.envelope.issued_at_ns == 30_000_000_000
        )
    else:
        with pytest.raises(WizardError) as error:
            service._feedback_campaign(cancellation)
        assert "CANCELLED" in error.value.code
        assert captured == []
        assert order == ["preflight-enter", "preflight-read", "preflight-lease-release"]
        facts = preflight_facts[0]
        assert facts.envelope is None
    assert len(preflight_facts) == 1 and preflight_facts[0].envelope is None
    assert facts._epochs == preflight_facts[0]._epochs
    assert facts._hazard == preflight_facts[0]._hazard
    assert facts._identity == preflight_facts[0]._identity
    assert len(facts._epochs) == 8
    frozen_documents = tuple(json.loads(payload) for payload in facts._epochs)
    assert frozen_documents == tuple(
        {
            **document,
            "synthetic_feedback_binding_sha256": completed.binding.binding_sha256,
        }
        for document in seed_epochs
    )
    # This is exactly how M1RehearsalTransaction.read_admission creates the
    # configuration_epoch_hashes snapshot; no mutable input mapping is trusted.
    frozen_epoch_hashes = tuple(
        hashlib.sha256(payload).hexdigest() for payload in facts._epochs
    )
    assert len(set(frozen_epoch_hashes)) == 8
    ledger_payload = canonical_json_bytes(frozen_epoch_hashes)
    assert ledger_payload.endswith(b"\n")
    expected = hashlib.sha256(ledger_payload).hexdigest()
    if stop_preflight is None:
        assert facts.envelope.configuration_epoch_vector_sha256 == expected
    assert expected != service_module._hash(frozen_epoch_hashes)
    # Publication/dispatch did not happen, and the temporary admission cannot
    # become an implicit retry capability after the capture interruption.
    assert not tx.stored and not tx.commits
    assert service._feedback_admission is None
    assert not service.directory.exists()


@pytest.mark.parametrize(
    "stop_boundary", ["after-known-before-projection", "after-projection-publication"]
)
def test_stop_after_known_sealing_never_replays_or_discards_private_evidence(
    service, monkeypatch, stop_boundary, workbench, tmp_path
):
    """Exercise service publication boundaries with a real already-sealed result.

    The coordinator proxy returns that exact prior result, without dispatching a
    second worker. This isolates service cancellation ordering; it is not a new
    fake durability proof or a reusable public permit.
    """
    completed = actual_campaign()
    before = list(completed.store.trace)
    service.cell_id, service.session_id = (
        completed.binding.cell_id,
        completed.binding.session_id,
    )
    service._operator = completed.binding.operator_id
    service._cached["challenge_sha256"] = "1" * 64
    tx = StageTransaction(service)
    tx.current.next_action.stage_state = V2StageState.WAITING_OPERATOR
    tx.verification = lambda: SimpleNamespace(
        challenge_sha256=service._cached["challenge_sha256"]
    )
    tx.read_admission = lambda request: SimpleNamespace(challenge_sha256="1" * 64)
    service._store = SimpleNamespace(transaction=lambda leases: tx)
    cancellation = Event()
    calls = []

    class CompletedCoordinator:
        def prepare(self, request):
            calls.append("prepare")
            return completed.permit

        def execute(self, permit, *, cancellation):
            assert permit is completed.permit
            calls.append("known-result")
            if stop_boundary == "after-known-before-projection":
                cancellation.set()
            return completed.result

    class CompletedWindow:
        """Modeled publication seam, not an alternate M1 admission proof."""

        def __init__(self, **kwargs):
            self.preflight_transaction = tx

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def bind_request(self, request):
            assert request.expected_challenge_sha256 == "1" * 64

    from rocell.application import scoped_rehearsal_dispatch

    monkeypatch.setattr(
        scoped_rehearsal_dispatch, "ScopedRehearsalDispatch", CompletedWindow
    )

    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_feedback_context", lambda _: (completed.binding, {}))
    monkeypatch.setattr(
        service,
        "_facts",
        lambda *a: SimpleNamespace(
            configuration_epoch_documents=tuple({"epoch": i} for i in range(8)),
            hazard_assessment_document={"fixture": "NO_PHYSICAL_AUTHORITY"},
        ),
    )
    monkeypatch.setattr(service, "_refresh", lambda **kwargs: None)
    monkeypatch.setattr(
        service_module,
        "CellCommissioningCoordinator",
        lambda **kwargs: CompletedCoordinator(),
    )
    monkeypatch.setattr(
        campaign, "ArmFeedbackRehearsalCampaign", lambda *a, **k: completed.worker
    )
    original_store = service._store_json

    def store_projection(*args, **kwargs):
        reference = original_store(*args, **kwargs)
        if stop_boundary == "after-projection-publication":
            cancellation.set()
        return reference

    monkeypatch.setattr(service, "_store_json", store_projection)
    values = service.bind(ACTION, {})
    if stop_boundary == "after-known-before-projection":
        with pytest.raises(WizardError) as error:
            service.perform(
                ACTION, values, cancellation=cancellation, progress=lambda _: None
            )
        assert "CANCELLED" in error.value.code
        assert service._receipt is None and not tx.stored
        assert service.view()["status"] == "HELD"
    else:
        result = service.perform(
            ACTION, values, cancellation=cancellation, progress=lambda _: None
        )
        assert result["status"] == "SUCCEEDED"
        assert (
            service._receipt["retained_campaign_sha256"]
            == completed.artifact.evidence_sha256
        )
        assert len(tx.stored) == 1
        # The cache must equal the representation read back by storage, not
        # merely serialize to equal bytes. Do not pre-normalize either side:
        # these are the actual service-created cache and transaction readback.
        assert service._receipt == tx.stored[0]
        assert type(service._receipt["attempt_result"]["reason_codes"]) is list
        assert (
            type(service._receipt["attempt_result"]["receipt"]["evidence_sha256s"])
            is list
        )
        if os.name == "nt":
            from test_commissioning_m1_persistence import _runtime, FIRST, SESSION

            # Tiny real qualified NTFS package roundtrip, with no preceding
            # stage PASS fixtures or camera/serial campaigns. The first open
            # stage retains this as a serialization-test payload only, not as
            # accepted stage-12 evidence. No pre-normalized fixture is supplied:
            # these are the exact bytes/cache produced by the service above.
            _, adapter = _runtime(tmp_path)
            with adapter.stage_transaction(
                SESSION,
                expected_challenge_sha256=adapter.verification(
                    SESSION
                ).challenge_sha256,
            ) as durable_tx:
                stored_reference = original_store(
                    durable_tx,
                    FIRST,
                    service._receipt,
                    "Feedback receipt JSON representation regression only",
                )
            stored_path = (
                tmp_path
                / "isolated-rehearsal"
                / ("onboarding-" + SESSION)
                / "evidence"
                / stored_reference.evidence_id
                / "payload.bin"
            )
            stored_bytes = stored_path.read_bytes()
            assert (
                hashlib.sha256(stored_bytes).hexdigest()
                == stored_reference.payload_sha256
            )
            assert json.loads(stored_bytes) == service._receipt
            assert stored_bytes == service_module._bytes(service._receipt)
            assert (
                adapter.snapshot(SESSION).next_action.stage_state
                is V2StageState.WAITING_OPERATOR
            )
        # Exercise the actual public validation boundary, not only dataclass
        # equality/JSON serialization (both accept str-enum instances). The
        # stricter public sanitizer must accept this server-owned projection.
        public_result = workbench._validated_result(ACTION, result)
        diagnostic = public_result["steps"][1]["report"]
        assert type(diagnostic["attempt_result"]["state"]) is str
        assert type(diagnostic["attempt_result"]["receipt"]["effect_certainty"]) is str
        assert type(diagnostic["attempt_result"]["receipt"]["final_power_state"]) is str
        assert diagnostic["attempt_result"]["state"] == "SEALED_KNOWN"
        assert "payload_base64" not in json.dumps(public_result)
        assert "response_bytes" not in diagnostic
        # Deliver the exact service-produced result through the normal async
        # Arrival API, then export its retained attachment. The public-boundary
        # adapter returns this completed result only; it does not replay M1.
        from rocell.application.wizard_diagnostic_export import verify_export
        from test_arrival_wizard_service import _run

        public_calls = []
        physical_stages = workbench.view()["stages"]

        def completed_result(action, values, *, cancellation, progress):
            assert action == ACTION
            public_calls.append(action)
            return deepcopy(result)

        monkeypatch.setattr(workbench._commissioning, "perform", completed_result)
        delivered = _run(workbench, ACTION)
        assert delivered["status"] == "SUCCEEDED", delivered.get("error")
        assert delivered["result_retention"] == "FULL_JSON_RETAINED"
        assert delivered["result"] == public_result
        exported = _run(workbench, "export_logs")
        assert exported["status"] == "SUCCEEDED", exported.get("error")
        folder = Path(exported["result"]["receipt"]["path"])
        assert verify_export(folder)["valid"]
        attachment = folder / (
            "attachment-result-"
            + delivered["operation_id"].removeprefix("operation-")
            + ".json"
        )
        saved_public = json.loads(attachment.read_bytes())
        assert saved_public == public_result
        assert "payload_base64" not in json.dumps(saved_public)
        assert public_calls == [ACTION]
        assert workbench.view()["stages"] == physical_stages
    assert calls == ["prepare", "known-result"]
    assert completed.store.trace == before
    assert completed.permit.attempt_id in completed.store.evidence
    assert service._feedback_admission is None
    assert service.blocked_reason(ACTION) is not None
    with pytest.raises(WizardError):
        service.bind(ACTION, {})


@pytest.mark.parametrize("corrupt_camera", [False, True])
def test_feedback_context_revalidates_retained_camera_dependency(
    service, monkeypatch, corrupt_camera
):
    snapshot, binding, document = object(), object(), {"retained": "stage-six-capture"}
    transaction = SimpleNamespace(snapshot=lambda: snapshot)
    retained_camera = SimpleNamespace(document=lambda: document)
    evidence = {"camera": retained_camera}
    calls = []
    monkeypatch.setattr(reopen, "_read_evidence", lambda *a: evidence)

    def dependency(current, records, operator, source, catalog):
        assert current is snapshot and records is evidence
        assert operator == service._operator and source == service.source_sha256
        calls.append("reviewed-dependencies")
        return binding, retained_camera

    def capture(value, *, tx):
        assert value is document
        assert tx is transaction
        calls.append("camera-content-and-provenance")
        if corrupt_camera:
            raise ValueError("Retained capture provenance drift")

    monkeypatch.setattr(reopen, "_feedback_binding", dependency)
    monkeypatch.setattr(service, "_verify_capture", capture)
    if corrupt_camera:
        with pytest.raises(ValueError, match="provenance drift"):
            service._feedback_context(transaction)
    else:
        assert service._feedback_context(transaction) == (binding, evidence)
    assert calls == ["reviewed-dependencies", "camera-content-and-provenance"]


def test_changed_cached_feedback_receipt_is_rejected_before_pure_verification(
    service, monkeypatch
):
    tx = StageTransaction(service)
    reference = SimpleNamespace(evidence_id="retained-feedback")
    service._receipt_reference = reference
    service._receipt = {
        "schema": "rocell.rehearsal_feedback_receipt.v1",
        "forged": True,
    }
    saved = SimpleNamespace(
        document=lambda: {"schema": "rocell.rehearsal_feedback_receipt.v1"}
    )
    monkeypatch.setattr(
        service, "_feedback_context", lambda _: (None, {reference.evidence_id: saved})
    )
    monkeypatch.setattr(
        reopen,
        "_verify_evaluated_receipt",
        lambda *a, **k: pytest.fail("Changed cache reached verifier"),
    )
    with pytest.raises(WizardError) as error:
        service._verify_feedback(tx)
    assert error.value.code == "FEEDBACK_RECEIPT_CHANGED"
    assert not tx.commits and not tx.stored


def test_service_assessment_forwards_only_audited_records_and_exact_retained_receipt(
    service, monkeypatch
):
    tx = StageTransaction(service)
    records = {"audited-only-fixture": {}}
    tx._audit_records = lambda: records
    reference = SimpleNamespace(evidence_id="retained-feedback")
    service._receipt_reference = reference
    service._receipt = {"schema": "rocell.rehearsal_feedback_receipt.v1"}
    receipt = SimpleNamespace(document=lambda: deepcopy(service._receipt))
    evidence = {reference.evidence_id: receipt}
    monkeypatch.setattr(service, "_feedback_context", lambda _: (None, evidence))
    marker = object()

    def verify(snapshot, saved, selected, source, catalog, *, records, directory):
        assert snapshot is tx.current and saved is evidence and selected is receipt
        assert records is tx._audit_records()
        assert source == service.source_sha256
        assert directory == service.directory
        return marker

    monkeypatch.setattr(reopen, "_verify_evaluated_receipt", verify)
    assert service._verify_feedback(tx) is marker
    assert not tx.commits and not tx.stored


def test_forged_review_outcome_cannot_override_retained_failed_check(
    service, monkeypatch
):
    tx = StageTransaction(service)
    service._assessment = {"reason_codes": [], "outcome": "PASS"}
    service._assessment_reference = SimpleNamespace(evidence_id="assessment")
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(
        service,
        "_verify_feedback",
        lambda _: SimpleNamespace(
            checks=({"check_id": "serial_cleanup", "passed": False},)
        ),
    )
    with pytest.raises(WizardError) as error:
        service._review(
            {"reviewer_id": "other-reviewer", "accept_assessment": True}, Event()
        )
    assert error.value.code == "FEEDBACK_ASSESSMENT_CHANGED"
    assert not tx.commits and not tx.stored


@pytest.fixture
def workbench(tmp_path, monkeypatch):
    monkeypatch.setattr(arrival, "source_fingerprint", lambda _: "8" * 64)
    value = arrival.ArrivalWizardService(
        WORKSPACE,
        log_directory=tmp_path / "logs",
        export_directory=tmp_path / "exports",
        runner=SimpleNamespace(
            run=lambda *a, **k: pytest.fail("Preview dispatched diagnostic runner")
        ),
    )
    value._commissioning._store = object()
    value._commissioning._operator = "operator-1"
    value._commissioning._cached.update(
        stage=STAGE.value, stage_state="WAITING_OPERATOR"
    )
    yield value
    value.shutdown()


def test_arrival_feedback_preview_is_explicit_memory_only_and_has_no_inputs(workbench):
    action = ACTION_BY_ID[ACTION]
    assert not action.fields
    ticket = workbench.prepare_action(ACTION, {}, workbench.view()["revision"])
    effects = " ".join(ticket["effects"])
    assert "sealed incapable serial backend" in effects
    assert "Never open a physical COM port" in effects
    assert "separate synthetic post-campaign power observation" in effects
    assert ticket["input"] == {}
    assert workbench._executor is None
    assert (
        not workbench.log_directory.exists() and not workbench.export_directory.exists()
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("port", "COM1"),
        ("command", '{"T":105}'),
        ("physical", True),
        ("allow_hardware", True),
        ("scenario", "nominal"),
    ],
)
def test_arrival_feedback_action_rejects_arbitrary_connection_or_bypass_inputs(
    workbench, field, value
):
    with pytest.raises(WizardError):
        workbench.prepare_action(ACTION, {field: value}, workbench.view()["revision"])
    assert workbench._executor is None


def test_actual_observer_through_root_projection_renders_without_serial_data():
    from test_arrival_wizard_feedback_ui import render
    from test_arrival_wizard_reopen_ui import commissioning

    value = actual_campaign()
    projection = commissioning()
    projection["arm_feedback_evaluation"] = value.evaluated.to_dict()
    page, terminal = render(projection)
    for output in (page, terminal):
        assert "Safe serial summary is missing or invalid" not in output
        assert value.artifact.final_power_observation["observation_sha256"] in output
        assert value.artifact.evidence_sha256 in output
        assert "not a measurement of real power" in output
        assert "COM42" not in output
        assert '{"T":105}' not in output
    assert "SYNTHETIC DEENERGIZED OBSERVATION ONLY" in page
    assert "SYNTHETIC_DEENERGIZED_OBSERVATION_ONLY" in terminal
    assert "UNKNOWN REQUIRES SEPARATE OBSERVATION" in page
    assert "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in terminal
