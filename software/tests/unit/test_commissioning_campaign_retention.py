"""Qualified Windows temporary-store retention; no physical device is accessed."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
from threading import Event
import time

import pytest

from rocell.application import cell_commissioning_coordinator as core
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistence,
    M1CommissioningPersistenceError,
    M1RehearsalTransaction,
    RehearsalAdmissionFacts,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.safety.effects import EffectClass, EffectCertainty
from test_commissioning_m1_persistence import (
    _runtime,
    _records,
    SOURCE,
    CELL,
    SESSION,
    FIRST,
)


WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="requires qualified temporary Windows NTFS store"
)


class RetainedSerialFixture:
    composition = core.INCAPABLE_COMPOSITION
    worker_executable_sha256 = "b" * 64

    def __init__(self, payload=b"private synthetic bytes\x00\xff"):
        self.artifact = core.CampaignEvidence(
            "rocell.retention_fixture.v1", "private-fixture", payload
        )
        self.calls = 0
        self.permit = None

    def run_campaign(self, *args, **kwargs):
        raise AssertionError("retaining fixture must not use legacy worker path")

    def run_retained_campaign(
        self, permit, *, deadline_ns, cancellation, authorize_consumed_permit
    ):
        authorize_consumed_permit(permit)
        self.calls += 1
        self.permit = permit
        return core.RetainedCampaignExecution(
            core.WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                self.worker_executable_sha256,
                permit.admission.selected_identity_sha256,
                EffectCertainty.CONFIRMED,
                True,
                core.ObservedPowerState.DEENERGIZED,
                1,
                1,
                1,
                0,
                1,
                len(self.artifact.payload),
                (self.artifact.payload_sha256,),
            ),
            (self.artifact,),
        )


def setup(tmp_path, *, payload=b"private synthetic bytes\x00\xff"):
    runtime, _ = _runtime(tmp_path)
    worker = RetainedSerialFixture(payload)
    registration = core.CampaignRegistration(
        "retained-serial-fixture",
        FIRST,
        EffectClass.SERIAL_OPEN_OR_WRITE,
        "incapable-retention-fixture",
        worker.worker_executable_sha256,
        "d" * 64,
        (LeaseLevel.ARM_CONTROLLER,),
        core.CampaignBudget(10000, core.MAX_RETAINED_CAMPAIGN_BYTES, 1, 1, 1, 0, 1),
    )
    epochs = tuple({"epoch": i, "source": SOURCE} for i in range(8))
    epoch_hashes = tuple(
        hashlib.sha256(
            json.dumps(v, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for v in epochs
    )
    issued = time.monotonic_ns()
    envelope = core.EnergizationEnvelope(
        "synthetic-envelope",
        registration.operation_sha256,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        core._hash(epoch_hashes),
        "operator",
        "observer",
        issued,
        issued + core.MAX_PERMIT_TTL_NS,
    )

    def facts(request, snapshot):
        return RehearsalAdmissionFacts(
            {"source": SOURCE},
            epochs,
            {"synthetic_controller": "fixture"},
            envelope=envelope,
        )

    adapter = M1CommissioningPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=facts
    )
    request = core.RegisteredActionRequest(
        CELL, SESSION, registration.action_id, "retained-request-one", "a" * 64
    )
    leases = (
        LeaseSpec(LeaseLevel.CELL, CELL),
        LeaseSpec(LeaseLevel.SESSION, SESSION),
        LeaseSpec(LeaseLevel.ARM_CONTROLLER, CELL),
    )
    with adapter.transaction(leases) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    coordinator = core.CellCommissioningCoordinator(
        persistence=adapter,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
    )
    return runtime, adapter, coordinator, worker, request, facts


@WINDOWS
def test_actual_m1_retains_full_blob_before_seal_and_reads_after_restart(tmp_path):
    runtime, adapter, coordinator, worker, request, facts = setup(tmp_path)
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, result.reason_codes
    path = _records(runtime) / f"evidence-{permit.attempt_id}-retained.json"
    assert path.is_file()
    assert len(path.read_bytes()) < 256 * 1024
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_evidence(permit.attempt_id) == (worker.artifact,)
    reopened_runtime = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=runtime.source_binding_sha256,
        cell_id=CELL,
    )
    reopened = M1CommissioningPersistence(
        reopened_runtime, workspace_source_sha256=SOURCE, admission_facts=facts
    )
    with reopened.stage_transaction(
        SESSION,
        expected_challenge_sha256=reopened.verification(SESSION).challenge_sha256,
    ) as tx:
        assert (
            tx.read_campaign_evidence(permit.attempt_id)[0].payload
            == worker.artifact.payload
        )
    fresh_core = core.CellCommissioningCoordinator(
        persistence=reopened,
        registrations=(permit.registration,),
        workers={permit.registration.worker_id: worker},
        retained_campaign_actions=(permit.registration.action_id,),
    )
    with pytest.raises(core.CommissioningCoordinatorError, match="restarted"):
        fresh_core.execute(permit)
    assert worker.calls == 1


@WINDOWS
@pytest.mark.parametrize("tamper", ["missing", "bytes", "count", "extra-field"])
def test_known_serial_audit_requires_immutable_exact_blob(tmp_path, tamper):
    runtime, adapter, coordinator, worker, request, _ = setup(tmp_path)
    permit = coordinator.prepare(request)
    assert coordinator.execute(permit).state is AttemptState.SEALED_KNOWN
    target = _records(runtime) / f"evidence-{permit.attempt_id}-retained.json"
    if tamper == "missing":
        target.unlink()
    else:
        document = json.loads(target.read_bytes())
        if tamper == "bytes":
            document["data"]["evidence"][0]["payload_base64"] = "YWx0ZXJlZA=="
        elif tamper == "count":
            document["data"]["evidence"][0]["payload_bytes"] = False
        else:
            document["data"]["evidence"][0]["unexpected"] = True
        document["record_sha256"] = hashlib.sha256(
            canonical_json_bytes(
                {
                    key: value
                    for key, value in document.items()
                    if key != "record_sha256"
                }
            )
        ).hexdigest()
        target.write_bytes(canonical_json_bytes(document))
    with pytest.raises(M1CommissioningPersistenceError):
        with adapter.stage_transaction(
            SESSION,
            expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
        ):
            pytest.fail(
                "known serial result was admitted without its verified full bytes"
            )
    assert worker.calls == 1


@WINDOWS
def test_full_evidence_publication_failure_seals_uncertain_not_known(
    tmp_path, monkeypatch
):
    _, adapter, coordinator, worker, request, _ = setup(tmp_path)
    permit = coordinator.prepare(request)
    original = M1RehearsalTransaction._write_record

    def fail(self, filename, kind, data):
        if kind == "CAMPAIGN_EVIDENCE":
            raise OSError("injected immutable full-result publication failure")
        return original(self, filename, kind, data)

    monkeypatch.setattr(M1RehearsalTransaction, "_write_record", fail)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert adapter.verification(SESSION).quarantined
    assert worker.calls == 1
    assert coordinator.execute(permit) is result


@WINDOWS
def test_maximum_lossless_payload_stays_under_existing_json_parser_limit(tmp_path):
    runtime, adapter, coordinator, worker, request, _ = setup(
        tmp_path, payload=b"x" * core.MAX_RETAINED_CAMPAIGN_BYTES
    )
    permit = coordinator.prepare(request)
    assert coordinator.execute(permit).state is AttemptState.SEALED_KNOWN
    target = _records(runtime) / f"evidence-{permit.attempt_id}-retained.json"
    assert 170 * 1024 < target.stat().st_size < 256 * 1024
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_evidence(permit.attempt_id) == (worker.artifact,)


@pytest.mark.parametrize(
    "evidence",
    [
        (),
        [],
        (b"raw",),
        tuple(core.CampaignEvidence("s", str(i), bytes([i])) for i in range(5)),
    ],
)
def test_retention_tuple_is_closed_nonempty_and_bounded(evidence):
    with pytest.raises(core.CommissioningCoordinatorError):
        core.validate_campaign_evidence(evidence)


def test_retention_aggregate_and_unique_identity_are_bounded():
    first = core.CampaignEvidence("schema", "first", b"a" * 65537)
    second = core.CampaignEvidence("schema", "second", b"b" * 65537)
    with pytest.raises(core.CommissioningCoordinatorError):
        core.validate_campaign_evidence((first, second))
    with pytest.raises(core.CommissioningCoordinatorError):
        core.validate_campaign_evidence((first, first))
    with pytest.raises(core.CommissioningCoordinatorError):
        core.CampaignEvidence("schema", "x", b"")
    with pytest.raises(core.CommissioningCoordinatorError):
        core.CampaignEvidence(
            "schema", "x", b"x" * (core.MAX_RETAINED_CAMPAIGN_BYTES + 1)
        )
