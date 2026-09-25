"""Explicit original terminal/no-artifact readback, never an empty success.

Pure boundary cases model the storage methods. The separate NTFS case retains
a genuine consumed-attempt failure with an explicitly modeled worker exception;
it invokes no process, CIM or device operation.
"""

from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_usb_presence_persistence as persistence
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import owned_usb_presence_runner as runner
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceEvidenceError,
)
from test_physical_usb_presence_dispatch import (
    composition,
    workspace,
    forbid_process_devices,
    WINDOWS,
    SESSION,
    assert_strict_json,
)

ATTEMPT = "attempt-" + "a" * 32


@pytest.mark.parametrize(
    "state",
    [
        AttemptState.SEALED_UNCERTAIN,
        AttemptState.ABORTED_PRE_EFFECT,
        AttemptState.SEALED_KNOWN,
    ],
)
@pytest.mark.parametrize("with_receipt", [False, True])
def test_pure_missing_artifact_requires_audited_failure_without_receipt(
    state, with_receipt
):
    calls = []
    tx = SimpleNamespace(
        _check_scope=lambda: calls.append("scope"),
        read_campaign_result=lambda attempt: SimpleNamespace(
            state=state, receipt=object() if with_receipt else None
        ),
        _audit_records=lambda: {},
    )
    read = persistence.M1PhysicalUsbPresenceTransaction.read_optional_campaign_evidence
    if state is not AttemptState.SEALED_KNOWN and not with_receipt:
        assert read(tx, ATTEMPT) == () and calls == ["scope", "scope"]
    else:
        with pytest.raises(persistence.M1CommissioningPersistenceError):
            read(tx, ATTEMPT)


@pytest.mark.parametrize("fault", ["terminal", "audit", "artifact"])
def test_pure_optional_reader_never_swallows_integrity_failures(fault):
    def fail(*args):
        raise ValueError("MODELED_" + fault)

    tx = SimpleNamespace(
        _check_scope=lambda: None,
        read_campaign_result=lambda attempt: SimpleNamespace(
            state=AttemptState.SEALED_UNCERTAIN, receipt=None
        ),
        _audit_records=lambda: {f"evidence-{ATTEMPT}-retained.json": {}},
        read_campaign_evidence=lambda attempt: ("exact-verified-artifact",),
    )
    setattr(
        tx,
        {
            "terminal": "read_campaign_result",
            "audit": "_audit_records",
            "artifact": "read_campaign_evidence",
        }[fault],
        fail,
    )
    with pytest.raises(ValueError, match="MODELED_" + fault):
        persistence.M1PhysicalUsbPresenceTransaction.read_optional_campaign_evidence(
            tx, ATTEMPT
        )


@WINDOWS
def test_actual_worker_failure_without_artifact_preserves_original_reason(
    workspace, monkeypatch
):
    case = composition(workspace, monkeypatch)

    def fail_model(self, *, cancellation, deadline_ns):
        self.scope.acknowledge(self.permit)
        raise OwnedUsbPresenceEvidenceError("MODELED_FINALIZATION_FAILURE")

    monkeypatch.setattr(runner.OwnedUsbPresenceRunner, "run", fail_model)
    pending = case.owner.perform(
        request_key="MODELED-no-artifact-terminal", cancellation=Event()
    )
    original = case.owner.retained_diagnostics()["original"]
    assert original["result"]["state"] == "SEALED_UNCERTAIN"
    assert original["result"]["quarantine_latched"] is True
    assert "OwnedUsbPresenceEvidenceError" in original["result"]["reason_codes"]
    assert original["result"]["receipt"] is None
    assert original["evidence"] is original["evidence_sha256"] is None
    assert original["retention"] == "M1_TERMINAL_READ_BACK_NO_EVIDENCE"
    assert case.owner.retained_diagnostics()["collected"] is None
    assert not case.calls  # No complete modeled owned evidence was produced.
    assert_strict_json(pending)
    case.owner.validate_publication(pending)
    case.owner.publication_completed("MODELED-terminal-only-log")
    assert case.owner.view()["phase"] == "CURRENT"
    permit = original["permit"]
    with case.store.stage_transaction(
        SESSION,
        expected_challenge_sha256=case.store.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_optional_campaign_evidence(permit["attempt_id"]) == ()
        # The generic API must still reject missing artifacts, not hide damage.
        with pytest.raises(persistence.M1CommissioningPersistenceError):
            tx.read_campaign_evidence(permit["attempt_id"])
    with pytest.raises(ValueError, match="ALREADY_USED"):
        case.owner.perform(request_key="not-a-retry", cancellation=Event())
