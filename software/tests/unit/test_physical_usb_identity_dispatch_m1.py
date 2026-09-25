"""Real original NTFS + production USB owner/campaign, modeled runner only.

Prerequisites, native metadata and original review references are explicitly
modeled fixture facts. The exact runner seam returns strict failure evidence
after actual consumed-M1 acknowledgement/revalidation; no process/device runs.
Completion-log handoff is modeled explicitly, not claimed as an Arrival log.
"""

from dataclasses import asdict
from pathlib import Path
from threading import Event
import subprocess
import time

import pytest

from rocell.application import physical_usb_identity_dispatch as dispatch
from rocell.application.physical_usb_identity_campaign import (
    PhysicalUsbIdentityCampaign,
)
from rocell.application.commissioning_usb_identity_persistence import (
    M1PhysicalUsbIdentityPersistence,
    M1PhysicalUsbIdentityTransaction,
    PhysicalUsbIdentityAdmissionFacts,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.usb_identity_stage_policy import UsbIdentityAdmissionIdentity
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows.owned_usb_identity_evidence import (
    PROCESS_DEFAULTS,
    SCHEMA,
    retain_owned_usb_identity_run,
    stream_record,
)
from rocell.providers.windows.usb_identity_protocol import canonical
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

from test_commissioning_usb_identity import (
    WINDOWS,
    POLICY,
    CELL,
    SESSION,
    SOURCE,
    actual_usb_fixture,
    usb_facts,
)
from test_physical_usb_identity_campaign import inputs


pytestmark = WINDOWS
WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def forbid_effects(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("modeled application integration invoked a process/device")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(runner_module, "_new_owner", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)


def failure_evidence(
    prepared, *, deadline_ns, checks, started_ns, started_utc_ns, process_created
):
    """Constructed model of pre-owner refusal or unaccounted process failure."""
    process = dict(PROCESS_DEFAULTS)
    if process_created:
        process.update(
            created=True,
            resumed=True,
            tree_exited=True,
            returncode=1,
            pid=31415,
            peak_processes=1,
            stdout_eof=True,
            stderr_eof=True,
        )
    return retain_owned_usb_identity_run(
        dict(
            schema=SCHEMA,
            preparation=prepared.to_dict(),
            preparation_sha256=prepared.sha256,
            provenance="PHYSICAL_USB_QUERY",
            original_deadline_ns=deadline_ns,
            started_monotonic_ns=started_ns,
            finished_monotonic_ns=time.monotonic_ns(),
            started_utc_ns=started_utc_ns,
            finished_utc_ns=time.time_ns(),
            scope_checks=checks,
            owner_constructed=process_created,
            process=process,
            stdout=stream_record(b"", complete=True),
            stderr=stream_record(
                b"modeled incomplete child diagnostics" if process_created else b"",
                complete=True,
            ),
            ready_length=0,
            release_wire=stream_record(b"", complete=True),
            release_write_attempted=False,
            release_check_passed=False,
            release_delivery_confirmed=False,
            result_validated=False,
            primary_error=(
                "MODELED_PROCESS_FAILURE"
                if process_created
                else "MODELED_PRE_OWNER_REFUSAL"
            ),
            cleanup_errors=[],
            status="FAILED",
            physical_authority=False,
            hardware_qualified=False,
            retries=0,
        )
    )


def composition(tmp_path, monkeypatch, *, process_created=False, guard=lambda: None):
    runtime, _, _ = actual_usb_fixture(tmp_path)
    operation, identity, review = inputs(WORKSPACE)
    document = identity.to_dict()
    document["header_sha256"] = runtime.session_snapshot(SESSION).header.header_sha256
    identity = UsbIdentityAdmissionIdentity(canonical(document))
    campaign = PhysicalUsbIdentityCampaign(operation, identity=identity, review=review)

    def facts(request, snapshot):
        old = usb_facts()
        return PhysicalUsbIdentityAdmissionFacts(
            old.hazard_assessment_document,
            old.configuration_epoch_documents,
            identity.to_dict(),
            stage_policy=POLICY,
        )

    adapter = M1PhysicalUsbIdentityPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=POLICY,
        expected_usb_query_policy_sha256=POLICY.sha256,
        admission_facts=facts,
    )
    calls = []

    class ModelRunner:
        def __init__(self, prepared, *, permit, authorization, application_guard):
            self.prepared, self.permit, self.authorization, self.guard = (
                prepared,
                permit,
                authorization,
                application_guard,
            )

        def run(self, *, cancellation, deadline_ns):
            started, utc = time.monotonic_ns(), time.time_ns()
            assert self.guard() is None and not cancellation.is_set()
            self.authorization.acknowledge(self.permit)
            check_started = time.monotonic_ns()
            self.authorization.revalidate(self.permit)
            check_finished = time.monotonic_ns()
            evidence = failure_evidence(
                self.prepared,
                deadline_ns=deadline_ns,
                checks=[
                    dict(
                        boundary="PRE_PIN",
                        started_ns=check_started,
                        finished_ns=check_finished,
                        passed=True,
                    )
                ],
                started_ns=started,
                started_utc_ns=utc,
                process_created=process_created,
            )
            calls.append((self.permit, evidence, self.authorization))
            return evidence

    monkeypatch.setattr(runner_module, "OwnedUsbIdentityRunner", ModelRunner)
    monkeypatch.setattr(dispatch, "source_fingerprint", lambda workspace: SOURCE)
    owner = dispatch.PhysicalUsbIdentityDispatchOwner(
        adapter, campaign, revalidate_context=guard
    )
    return runtime, adapter, owner, campaign, calls


@pytest.mark.parametrize("process_created", [False, True])
def test_actual_owner_retains_original_failure_then_exact_pending_publication(
    tmp_path, monkeypatch, process_created
):
    runtime, adapter, owner, campaign, calls = composition(
        tmp_path, monkeypatch, process_created=process_created
    )
    assert (
        not runtime._attempts.snapshot().events
        and owner.view()["phase"] == "NOT_STARTED"
    )
    result = owner.perform(request_key="one-original-usb-query", cancellation=Event())
    assert result["status"] == "HELD" and result["attempt_state"] == "SEALED_UNCERTAIN"
    assert result["pending_completion_log"] is True and result["quarantine_latched"]
    assert len(calls) == 1 and owner.view()["phase"] == "PENDING_COMPLETION_LOG"
    permit, evidence, authority = calls[0]
    assert runtime.verify(SESSION).quarantined
    original = owner.retained_diagnostics()["original"]
    assert canonical(original["evidence"]) == evidence.payload
    assert original["evidence_sha256"] == evidence.sha256
    assert (
        original["admission_evidence"]["selected_identity"]
        == campaign.identity.to_dict()
    )
    assert original["reference"] == result["reference"]
    assert set(original["reference"]) == {
        "schema",
        "cell_id",
        "session_id",
        "attempt_id",
        "permit_sha256",
        "evidence_sha256",
        "payload_bytes",
        "label",
    }
    assert original["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert owner.view()["readback_scope"] == "EXITED"
    receipt = original["result"]["receipt"]
    if process_created:
        assert receipt is None and evidence.actual_counts is None
        assert "USB_ACCOUNTING_UNAVAILABLE" in result["reason_codes"]
    else:
        assert evidence.no_attempt and receipt["opens"] == receipt["reads"] == 0
        assert receipt["final_power_state"] == "UNKNOWN"
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert len(tx.held_leases) == 2
        assert (
            tx.read_campaign_evidence(permit.attempt_id)[0].payload == evidence.payload
        )
        assert (
            tx.read_campaign_result(permit.attempt_id).state
            is AttemptState.SEALED_UNCERTAIN
        )
        assert all(
            ref.payload_sha256 != evidence.sha256 for ref in tx.snapshot().evidence
        )
    with pytest.raises(Exception):
        authority.revalidate(permit)
    changed = dict(result, status="OBSERVED")
    with pytest.raises(dispatch.PhysicalUsbIdentityDispatchError):
        owner.validate_publication(changed)
    owner.validate_publication(result)
    owner.publication_completed("modeled-original-completion-log")
    assert owner.view()["phase"] == "CURRENT"
    assert owner.view()["physical_authority"] is False
    original["evidence"]["status"] = "OBSERVED"
    assert owner.retained_diagnostics()["original"]["evidence"]["status"] == "FAILED"
    with pytest.raises(dispatch.PhysicalUsbIdentityDispatchError, match="ALREADY_USED"):
        owner.perform(request_key="different-key", cancellation=Event())
    owner.invalidate()
    assert owner.view()["phase"] == "HISTORICAL_HELD"
    assert (
        owner.retained_diagnostics()["original"]["evidence_sha256"] == evidence.sha256
    )
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ["stop", "guard", "source"])
def test_actual_owner_stale_preflight_creates_no_attempt_and_does_not_retry(
    tmp_path, monkeypatch, fault
):
    def guard():
        if fault == "guard":
            raise ValueError("MODELED_CONTEXT_CHANGED")

    runtime, adapter, owner, campaign, calls = composition(
        tmp_path, monkeypatch, guard=guard
    )
    cancellation = Event()
    if fault == "stop":
        cancellation.set()
    if fault == "source":
        monkeypatch.setattr(dispatch, "source_fingerprint", lambda workspace: "f" * 64)
    with pytest.raises(ValueError):
        owner.perform(request_key="held-preflight", cancellation=cancellation)
    assert runtime._attempts.snapshot().events == () and calls == []
    assert owner.view()["phase"] == "FAILED_NO_REPLAY"
    assert owner.retained_diagnostics()["original"] is None
    with pytest.raises(dispatch.PhysicalUsbIdentityDispatchError, match="ALREADY_USED"):
        owner.perform(request_key="no-replay", cancellation=Event())


def test_actual_owner_readback_failure_cannot_publish_but_original_m1_bytes_survive(
    tmp_path, monkeypatch
):
    runtime, adapter, owner, campaign, calls = composition(
        tmp_path, monkeypatch, process_created=True
    )

    def refused(self, attempt_id):
        raise ValueError("MODELED_ORIGINAL_READBACK_FAILURE")

    with monkeypatch.context() as scoped:
        scoped.setattr(
            M1PhysicalUsbIdentityTransaction, "read_campaign_evidence", refused
        )
        with pytest.raises(ValueError, match="MODELED_ORIGINAL_READBACK_FAILURE"):
            owner.perform(request_key="lost-readback", cancellation=Event())
    assert owner.view()["phase"] == "FAILED_NO_REPLAY" and len(calls) == 1
    permit, evidence, _ = calls[0]
    partial = owner.retained_diagnostics()["original"]
    assert canonical(partial["permit"]) == canonical(asdict(permit))
    assert partial["result"]["attempt_id"] == permit.attempt_id
    assert partial["result"]["state"] == "SEALED_UNCERTAIN"
    assert (
        partial["admission_evidence"]["selected_identity"]
        == campaign.identity.to_dict()
    )
    assert partial["retention"] == "M1_TERMINAL_READ_BACK_EVIDENCE_PENDING"
    assert (
        partial["evidence"]
        is partial["reference"]
        is partial["evidence_sha256"]
        is None
    )
    assert owner.view()["readback_scope"] == "EXIT_OR_FINAL_VALIDATION_UNCONFIRMED"
    assert owner.view()["error_code"] == "USB_DISPATCH_FAILED"
    with pytest.raises(dispatch.PhysicalUsbIdentityDispatchError):
        owner.publication_completed("must-not-publish")
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert (
            tx.read_campaign_evidence(permit.attempt_id)[0].payload == evidence.payload
        )
        assert tx.read_campaign_result(permit.attempt_id).receipt is None
