"""Descriptor cleanup capacity with an in-memory peer; no process or USB I/O.

The real supervisor, admission checks, wire parsers and immutable evidence run.
Only process/native observations, file inspection and the workspace hash are
modeled. This is not actual Job, M1, native-helper or physical qualification.
"""

from copy import deepcopy
from types import SimpleNamespace
import os
import subprocess
import time

import pytest

from rocell.providers.windows import owned_usb_identity_runner as runner
from rocell.providers.windows import owned_usb_identity_evidence as evidence_module
from rocell.providers.windows import owned_worker_process as shared
from test_owned_usb_identity_runner import usb_fixture
from test_usb_reconnect_runner_model import ModeledObservedPipe


DERIVED = (
    "CLEANUP_DEADLINE_EXCEEDED",
    "PROCESS_RESOURCES_RETAINED",
    "PROCESS_TREE_EXIT_UNCONFIRMED",
    "UNRESOLVED_OWNER_ALREADY_RETAINED",
)


@pytest.fixture
def modeled_cleanup(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Cleanup-capacity tests cannot start native helpers or processes")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(runner, "_new_owner", forbidden)
    monkeypatch.setattr(runner, "inspect_usb_identity_runtime", lambda *a, **k: None)
    monkeypatch.setattr(runner, "source_fingerprint", lambda _: "a" * 64)
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)
    case = usb_fixture()
    clock = SimpleNamespace(now=time.monotonic_ns(), wall=time.time_ns())
    origin = clock.now
    monkeypatch.setattr(
        runner,
        "time",
        SimpleNamespace(
            monotonic_ns=lambda: clock.now,
            time_ns=lambda: clock.wall + clock.now - origin,
        ),
    )
    revalidate = case.transaction.revalidate_consumed_permit

    def checked(permit):
        revalidate(permit)
        clock.now += 100_000_000

    monkeypatch.setattr(case.transaction, "revalidate_consumed_permit", checked)

    def run(receipt, *, derived=False, malformed_result=False, raised=None):
        sentinel = object()

        class Peer(ModeledObservedPipe):
            def send_final_input(self, wire, *, check):
                super().send_final_input(wire, check=check)
                if malformed_result:
                    self.stdout = self.stdout.split(b"\n", 1)[0] + b"\nBROKEN_RESULT"

            def cleanup(self, deadline_ns):
                super().cleanup(deadline_ns)
                if derived:
                    clock.now = deadline_ns + 1
                    self.pins.append(object())
                    self.tree_exited = False
                    # Model a conflicting retained owner only after dispatch;
                    # the pre-dispatch one-owner gate remains exercised.
                    shared._UNRESOLVED_BACKEND = sentinel
                if raised is not None:
                    raise raised
                return receipt

        peer = Peer(case.prepared, case.cancellation)
        monkeypatch.setattr(runner, "_new_owner", lambda: peer)
        supervisor = runner.IncapableUsbIdentityRunner(
            case.prepared,
            permit=case.permit,
            authorization=case.scope,
            application_guard=lambda: None,
        )
        evidence = supervisor.run(
            cancellation=case.cancellation, deadline_ns=case.deadline_ns
        )
        return SimpleNamespace(
            case=case,
            peer=peer,
            supervisor=supervisor,
            evidence=evidence,
            sentinel=sentinel,
        )

    return run


def assert_preserved(made, *, known=True):
    d = made.evidence.to_dict()
    assert made.supervisor.retained_evidence.payload == made.evidence.payload
    assert evidence_module.stream_bytes(d["stdout"], 66 * 1024) == made.peer.stdout
    assert evidence_module.stream_bytes(d["stderr"], 4 * 1024) == made.peer.stderr
    assert len(made.evidence.payload) <= 128 * 1024
    assert d["physical_authority"] is False and d["hardware_qualified"] is False
    assert made.peer.cleanup_calls == made.peer.record["releases"] == 1
    assert made.case.transaction.acks == 1
    assert made.evidence.status == "CLEANUP_UNCERTAIN"
    effect = made.evidence.bounded_effect_summary()
    assert not effect["process_cleanup_confirmed"] and not effect["current_complete"]
    if known:
        native = made.evidence.observation.to_dict()
        assert effect["actual_counts"] == native["accounting"]
        assert effect["actual_counts"]["hub_open_attempts"] == 3
        assert effect["usb_cleanup_confirmed"] is True
        assert made.case.transaction.checks == 5
    else:
        assert effect["actual_counts"] is None and not effect["no_attempt"]
        assert made.evidence.observation is None
    return d


def test_maximum_admitted_owner_errors_reserve_all_four_derived_slots(modeled_cleanup):
    assert evidence_module.MAX_CLEANUP_ERRORS == 32
    assert evidence_module.MAX_OWNER_CLEANUP_ERRORS == 28
    owner_errors = tuple("MODELED_OWNER_" + str(index) for index in range(28))
    made = modeled_cleanup(owner_errors, derived=True)
    d = assert_preserved(made)
    assert d["cleanup_errors"] == [*owner_errors, *DERIVED]
    assert len(d["cleanup_errors"]) == 32
    assert shared._UNRESOLVED_BACKEND is made.sentinel
    assert made.supervisor._unresolved_owner is made.peer
    assert (
        evidence_module.OwnedUsbIdentityRunEvidence(made.evidence.payload).sha256
        == made.evidence.sha256
    )
    with pytest.raises(ValueError, match="CONSUMED"):
        made.supervisor.run(
            cancellation=made.case.cancellation, deadline_ns=made.case.deadline_ns
        )


@pytest.mark.parametrize("count", [29, 32, 33])
def test_oversized_owner_receipt_is_explicitly_held_without_losing_counts(
    modeled_cleanup, count
):
    made = modeled_cleanup(
        tuple("MODELED_OWNER_" + str(i) for i in range(count)), derived=True
    )
    d = assert_preserved(made)
    assert d["cleanup_errors"] == ["USB_INVALID_CLEANUP_RECEIPT", *DERIVED]
    assert shared._UNRESOLVED_BACKEND is made.sentinel
    assert made.supervisor._unresolved_owner is made.peer


@pytest.mark.parametrize("receipt", [None, [], (True,), ("bad label",), ("x" * 129,)])
def test_malformed_owner_receipt_never_becomes_a_clean_result(modeled_cleanup, receipt):
    made = modeled_cleanup(receipt)
    d = assert_preserved(made)
    assert d["cleanup_errors"] == ["USB_INVALID_CLEANUP_RECEIPT"]
    assert shared._UNRESOLVED_BACKEND is made.peer


@pytest.mark.parametrize("code", ["bad label", "x" * 129])
def test_malformed_cleanup_exception_code_is_closed_and_retained(modeled_cleanup, code):
    made = modeled_cleanup((), raised=runner.OwnedUsbIdentityRunnerError(code))
    d = assert_preserved(made)
    assert d["cleanup_errors"] == ["OwnedUsbIdentityRunnerError"]
    assert shared._UNRESOLVED_BACKEND is made.peer


def test_missing_native_result_remains_unknown_with_cleanup_failure(modeled_cleanup):
    made = modeled_cleanup(("MODELED_CLEANUP_UNCONFIRMED",), malformed_result=True)
    assert_preserved(made, known=False)


def test_historical_32_label_evidence_still_decodes_but_33_does_not(modeled_cleanup):
    made = modeled_cleanup(("MODELED_CLEANUP_UNCONFIRMED",))
    d = assert_preserved(made)
    d["cleanup_errors"] = ["HISTORICAL_" + str(i) for i in range(32)]
    raw = evidence_module.canonical(d)
    assert evidence_module.OwnedUsbIdentityRunEvidence(raw).payload == raw
    changed = deepcopy(d)
    changed["cleanup_errors"].append("TOO_MANY")
    with pytest.raises(ValueError, match="USB_CLEANUP_ERRORS"):
        evidence_module.OwnedUsbIdentityRunEvidence(evidence_module.canonical(changed))
