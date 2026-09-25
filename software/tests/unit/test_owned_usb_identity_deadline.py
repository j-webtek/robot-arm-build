"""Shortened original USB windows: incapable child and explicitly modeled faults.

The real child case uses only the separately linked fixed fake adapter. Scope
facts/global source identity are modeled; real Job, pipe, pin and cleanup APIs
remain exercised. No physical USB, camera, CIM or inventory API is invoked.
"""

from dataclasses import asdict, replace
import os
import time
from types import SimpleNamespace

import pytest

from rocell.application.consumed_commissioning_scope import ConsumedCommissioningScope
from rocell.application import physical_usb_identity_campaign as campaign_module
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows import owned_worker_process as shared
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
    verify_owned_usb_identity_run_evidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical
from test_owned_usb_identity_runner import (
    modeled_workspace_source,
    modeled_owner,
    run_case,
    usb_fixture,
)
from test_physical_usb_identity_campaign import campaign, permit_for
from test_physical_camera_usb_readback import modeled_clean_held_evidence


def clipped_scope(case, clock=time.monotonic_ns):
    """Same original permit and transaction, shorter one-use scope only."""
    case.deadline_ns = case.permit.issued_at_ns + 24_000_000_000
    case.scope = ConsumedCommissioningScope(
        case.permit,
        transaction=case.transaction,
        deadline_ns=case.deadline_ns,
        cancellation=case.cancellation,
        monotonic_ns=clock,
    )


@pytest.mark.skipif(os.name != "nt", reason="real Windows incapable Job/pipe owner")
def test_actual_incapable_child_with_24_second_original_window():
    assert shared._UNRESOLVED_BACKEND is None
    case = usb_fixture()
    original_permit = canonical(asdict(case.permit))
    clipped_scope(case)
    assert case.prepared.required_lifetime_ns == 20_000_000_000
    assert case.permit.expires_at_ns - case.permit.issued_at_ns == 30_000_000_000
    assert usb_identity_stage_policy().to_dict()["budget"]["timeout_ms"] == 25000

    runner, evidence = run_case(case)
    data = evidence.to_dict()
    assert evidence.status == "OBSERVED", data
    assert data["original_deadline_ns"] == case.deadline_ns
    assert data["finished_monotonic_ns"] < case.deadline_ns
    assert canonical(asdict(case.permit)) == original_permit
    assert evidence.preparation.payload == case.prepared.payload
    assert evidence.preparation.request.to_dict()["native_duration_ms"] == 10000
    assert data["provenance"] == "INCAPABLE_USB_QUERY"
    assert case.transaction.acks == 1 and case.transaction.checks == 5
    assert data["process"]["peak_processes"] == 1
    assert evidence.actual_counts["api_calls"] == 65
    assert evidence.actual_counts["hub_open_attempts"] == 5
    assert evidence.actual_counts["close_attempts"] == 5
    assert evidence.process_cleanup_confirmed and evidence.usb_cleanup_confirmed
    assert (
        verify_owned_usb_identity_run_evidence(
            evidence,
            expected_preparation_sha256=case.prepared.sha256,
            expected_evidence_sha256=evidence.sha256,
        ).payload
        == runner.retained_evidence.payload
    )
    assert shared._UNRESOLVED_BACKEND is None


def test_slow_post_pin_consumes_short_window_before_process_start(monkeypatch):
    case = usb_fixture()
    clock = [time.monotonic_ns()]
    clipped_scope(case, lambda: clock[0])
    monkeypatch.setattr(
        runner_module,
        "time",
        SimpleNamespace(monotonic_ns=lambda: clock[0], time_ns=time.time_ns),
    )
    owner = modeled_owner(case, monkeypatch, "malformed-result")
    monkeypatch.setattr(
        owner, "start", lambda *a, **k: pytest.fail("depleted window started child")
    )
    revalidate = case.transaction.revalidate_consumed_permit

    def slow_post_pin(permit):
        revalidate(permit)
        if case.transaction.checks == 2:
            clock[0] += 5_000_000_000

    monkeypatch.setattr(case.transaction, "revalidate_consumed_permit", slow_post_pin)
    runner, evidence = run_case(case)
    data = evidence.to_dict()
    assert evidence.error == "FULL_USB_LIFETIME_DOES_NOT_FIT"
    assert evidence.no_attempt and not evidence.released
    assert case.transaction.acks == 1 and case.transaction.checks == 2
    assert [row["boundary"] for row in data["scope_checks"]] == ["PRE_PIN", "POST_PIN"]
    assert all(row["passed"] for row in data["scope_checks"])
    assert data["owner_constructed"] and not data["process"]["created"]
    assert not data["release_write_attempted"]
    assert evidence.actual_counts["api_calls"] == 0
    assert owner.cleanup_calls == 1 and not owner.pins
    assert data["original_deadline_ns"] == case.deadline_ns
    assert runner.retained_evidence.payload == evidence.payload
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        runner.run(cancellation=case.cancellation, deadline_ns=case.deadline_ns)


@pytest.mark.parametrize("duration", [24_000_000_000, 25_000_000_000])
def test_independent_campaign_verifier_accepts_bounded_short_or_full_window(duration):
    c = campaign()
    permit = replace(permit_for(c), expires_at_ns=30_000_000_001)
    prepared = c.preparation_for_permit(permit)
    document = modeled_clean_held_evidence(prepared).to_dict()
    document["original_deadline_ns"] = document["started_monotonic_ns"] + duration
    evidence = OwnedUsbIdentityRunEvidence(canonical(document))
    verified = campaign_module.verify_usb_identity_campaign_evidence(
        evidence, campaign=c, permit=permit, expected_evidence_sha256=evidence.sha256
    )
    assert verified.payload == evidence.payload
    assert verified.status == "HELD"  # Constructed cancellation, not device success.


@pytest.mark.parametrize("fault", ["expiry", "campaign-cap", "issued-boundary"])
def test_independent_campaign_verifier_rejects_rehashed_deadline_outside_permit(fault):
    c = campaign()
    permit = replace(permit_for(c), issued_at_ns=1000, expires_at_ns=30_000_001_000)
    prepared = c.preparation_for_permit(permit)
    document = modeled_clean_held_evidence(prepared).to_dict()
    if fault == "issued-boundary":
        # Failed evidence legitimately keeps times on either side of a hold;
        # the original-context verifier must still refuse an out-of-permit
        # deadline independently of the inner native parser/status.
        document["original_deadline_ns"] = permit.issued_at_ns
    elif fault == "expiry":
        document["original_deadline_ns"] = permit.expires_at_ns + 1
    else:
        document["original_deadline_ns"] = (
            document["started_monotonic_ns"] + 25_000_000_001
        )
    evidence = OwnedUsbIdentityRunEvidence(canonical(document))
    with pytest.raises(ValueError):
        campaign_module.verify_usb_identity_campaign_evidence(
            evidence,
            campaign=c,
            permit=permit,
            expected_evidence_sha256=evidence.sha256,
        )
