"""Genuine NTFS M1→ConsumedScope→fixed incapable Job/pipe child→original bytes.

Original prerequisite and review subjects are explicitly modeled fixtures.
The separately linked child has no Windows USB adapter. No production USB
executable, native inventory, camera or serial provider is invoked here.
"""

from dataclasses import replace
import json
from threading import Event

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CampaignEvidence,
    ObservedPowerState,
    PHYSICAL_USB_IDENTITY_COMPOSITION,
    PhysicalUsbIdentityCoordinator,
    RetainedCampaignExecution,
    RetainedUncertainCampaignExecution,
    WorkerReceipt,
)
from rocell.application.commissioning_usb_identity_persistence import (
    M1PhysicalUsbIdentityPersistence,
    PhysicalUsbIdentityAdmissionFacts,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows.owned_usb_identity_runner import (
    IncapableUsbIdentityRunner,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import (
    UsbIdentityAdmissionRequest,
    canonical,
)
from rocell.providers.windows.usb_identity_registration import (
    prepare_incapable_usb_identity,
)
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.safety.effects import EffectCertainty

from test_commissioning_usb_identity import (
    WINDOWS,
    POLICY,
    SOURCE,
    CELL,
    SESSION,
    STAGE,
    actual_usb_fixture,
    actual_request,
    usb_facts,
)
from test_owned_usb_identity_runner import usb_fixture


@WINDOWS
@pytest.mark.parametrize(
    "history", [(0, 0), (64, 3)], ids=["fresh", "retained-history"]
)
def test_real_consumed_m1_scope_runs_only_fixed_incapable_owned_child(
    tmp_path, monkeypatch, history
):
    def denied(*args, **kwargs):
        pytest.fail("actual M1 test attempted a physical provider")

    monkeypatch.setattr(runner_module.OwnedUsbIdentityRunner, "__init__", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)
    monkeypatch.setattr(runner_module, "source_fingerprint", lambda workspace: SOURCE)
    runtime, camera, _ = actual_usb_fixture(tmp_path)
    reference_count, prior_campaigns = history
    if reference_count:
        # Seed a fresh store, never a copied acceptance store. These originals
        # model storage volume only; they are not measurements or stage reviews.
        with camera.stage_transaction(
            SESSION,
            expected_challenge_sha256=camera.verification(SESSION).challenge_sha256,
        ) as tx:
            snapshot = tx.snapshot()
            for index in range(reference_count - len(snapshot.evidence)):
                tx.store_evidence(
                    STAGE,
                    canonical(
                        {
                            "provenance": "MODELED_STORAGE_COST_ONLY",
                            "index": index,
                            "padding": "x" * 2048,
                        }
                    ),
                    label=f"modeled retained history {index}",
                    media_type="application/json",
                    captured_at_ns=4000 + index,
                    # Each publication checks this head and its own fresh store
                    # state. File-only evidence does not advance the journal.
                    expected_head_sha256=snapshot.head.head_sha256,
                )
            assert len(tx.snapshot().evidence) == reference_count
    case = usb_fixture(
        cell_id=CELL,
        session_id=SESSION,
        header_sha256=runtime.session_snapshot(SESSION).header.header_sha256,
    )
    # The helper's modeled scope/permit is not admitted. Only its immutable
    # runtime/review/identity/request template feed real production builders.
    case.scope.close_scope()
    registration = case.permit.registration

    def facts(request, snapshot):
        previous = usb_facts()
        return PhysicalUsbIdentityAdmissionFacts(
            previous.hazard_assessment_document,
            previous.configuration_epoch_documents,
            case.identity.to_dict(),
            stage_policy=POLICY,
        )

    adapter = M1PhysicalUsbIdentityPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=POLICY,
        expected_usb_query_policy_sha256=POLICY.sha256,
        admission_facts=facts,
    )
    retained = []

    class IncapableComposition:
        composition = PHYSICAL_USB_IDENTITY_COMPOSITION
        worker_executable_sha256 = registration.worker_executable_sha256

        def run_scoped_campaign(
            self, permit, *, deadline_ns, cancellation, authorization
        ):
            doc = case.request.to_dict()
            doc.update(attempt_id=permit.attempt_id, permit_sha256=permit.permit_sha256)
            request = UsbIdentityAdmissionRequest(canonical(doc))
            prepared = prepare_incapable_usb_identity(
                case.runtime,
                review=case.review,
                expected_review_sha256=case.review.sha256,
                identity=case.identity,
                request=request,
            )
            assert (
                prepared.registration.executable.path.name
                == "rocell_usb_identity_entry_tests.exe"
            )
            runner = IncapableUsbIdentityRunner(
                prepared,
                permit=permit,
                authorization=authorization,
                application_guard=lambda: None,
            )
            evidence = runner.run(cancellation=cancellation, deadline_ns=deadline_ns)
            retained.append((evidence, authorization, prepared))
            item = CampaignEvidence(
                evidence.to_dict()["schema"],
                "incapable-owned-usb-original",
                evidence.payload,
            )
            effect = evidence.bounded_effect_summary()
            counts = effect["actual_counts"]
            if counts is None:
                return RetainedUncertainCampaignExecution(
                    (item,), ("USB_ACCOUNTING_UNAVAILABLE",)
                )
            known = (
                effect["current_complete"]
                and effect["process_cleanup_confirmed"]
                and effect["usb_cleanup_confirmed"]
            )
            return RetainedCampaignExecution(
                WorkerReceipt(
                    permit.attempt_id,
                    permit.permit_sha256,
                    self.worker_executable_sha256,
                    case.identity.sha256,
                    EffectCertainty.CONFIRMED if known else EffectCertainty.UNCERTAIN,
                    bool(known),
                    ObservedPowerState.UNKNOWN,
                    counts["hub_open_attempts"],
                    counts["api_calls"]
                    - counts["hub_open_attempts"]
                    - counts["close_attempts"],
                    0,
                    0,
                    counts["close_attempts"],
                    len(item.payload),
                    (item.payload_sha256,),
                    self.composition,
                ),
                (item,),
            )

    worker = IncapableComposition()
    core = PhysicalUsbIdentityCoordinator(
        persistence=adapter,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
        scoped_campaign_actions=(registration.action_id,),
        usb_query_policy_sha256=POLICY.sha256,
    )
    for index in range(prior_campaigns):
        prior_permit = core.prepare(
            actual_request(adapter, key=f"incapable-owned-history-{index}")
        )
        prior_result = core.execute(prior_permit)
        assert prior_result.state is AttemptState.SEALED_KNOWN, prior_result
        assert len(retained) == index + 1
    previous_retained_count = len(retained)
    request = actual_request(adapter, key="real-owned-incapable-once")
    permit = core.prepare(request)
    result = core.execute(permit)
    assert len(retained) == previous_retained_count + 1, result
    evidence, authorization, prepared = retained[-1]
    # Always read originals before reporting a lifecycle/timing failure.
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        original = tx.read_campaign_evidence(permit.attempt_id)[0]
        assert original.payload == evidence.payload
        assert (
            tx.read_campaign_admission_evidence(permit.attempt_id)["selected_identity"]
            == case.identity.to_dict()
        )
    restored = OwnedUsbIdentityRunEvidence(original.payload)
    assert result.state is AttemptState.SEALED_KNOWN, (result, restored.safe_summary())
    doc = restored.to_dict()
    assert doc["provenance"] == "INCAPABLE_USB_QUERY"
    assert restored.observation.to_dict()["outcome"] == "OBSERVED"
    assert restored.process_cleanup_confirmed and restored.usb_cleanup_confirmed
    assert restored.actual_counts["api_calls"] == 65
    assert (
        restored.actual_counts["hub_open_successes"]
        == restored.actual_counts["close_successes"]
        == 5
    )
    assert len(doc["scope_checks"]) == 5 and all(
        row["passed"] for row in doc["scope_checks"]
    )
    assert (
        doc["process"]["created"]
        and doc["process"]["resumed"]
        and doc["process"]["tree_exited"]
    )
    assert doc["process"]["peak_processes"] == 1
    assert doc["release_delivery_confirmed"] and len(original.payload) <= 128 * 1024
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert result.receipt.writes == result.receipt.frames == 0
    assert result.receipt.reads == 55
    events = runtime._attempts.snapshot().events
    assert len(events) == 5 * (prior_campaigns + 1)
    final_events = events[-5:]
    print(
        json.dumps(
            {
                "checkpoint": "ACTUAL_M1_INCAPABLE_OWNED_USB_READBACK",
                "attempt_id": permit.attempt_id,
                "evidence_sha256": restored.sha256,
                "evidence_bytes": len(original.payload),
                "original_deadline_ns": doc["original_deadline_ns"],
                "started_monotonic_ns": doc["started_monotonic_ns"],
                "finished_monotonic_ns": doc["finished_monotonic_ns"],
                "runner_elapsed_ns": doc["finished_monotonic_ns"]
                - doc["started_monotonic_ns"],
                "runner_finish_deadline_margin_ns": doc["original_deadline_ns"]
                - doc["finished_monotonic_ns"],
                "peak_processes": doc["process"]["peak_processes"],
                "scope_check_elapsed_ns": [
                    row["finished_ns"] - row["started_ns"]
                    for row in doc["scope_checks"]
                ],
                "armed_to_sealed_utc_interval_ns": final_events[-1].occurred_at_ns
                - final_events[1].occurred_at_ns,
                "native_modeled_elapsed_ms": restored.observation.to_dict()[
                    "elapsed_ms"
                ],
                "physical_authority": False,
                "modeled_history_reference_count": reference_count,
                "prior_incapable_campaigns": prior_campaigns,
            },
            sort_keys=True,
        )
    )
    with pytest.raises(Exception):
        authorization.revalidate(permit)
    assert core.execute(permit) == result
    assert len(retained) == previous_retained_count + 1
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx._audit_records() == {}
