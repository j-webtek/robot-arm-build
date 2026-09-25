"""Small reconnect service invariants with modeled owner/transaction boundaries.

No filesystem, native owner, child process, CIM, USB, camera or arm action runs.
Actual original storage and public action acceptance live in separate tests.
"""

from threading import RLock
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_reconnect_service as reconnect
from rocell.application.physical_usb_identity_service import PhysicalUsbIdentityService
from rocell.application.physical_onboarding_v2 import V2JournalEvent, V2StageState
from rocell.application.wizard_actions import WizardError


PHASE_ID = "usbphase-" + "1" * 32


def test_committed_original_is_cached_before_a_later_guard_failure():
    phase = reconnect._UsbTrialReconnect(SimpleNamespace())
    phase.attempt = {"phase_id": PHASE_ID, "records": {}}
    calls = []

    def snapshot():
        calls.append("snapshot")
        assert calls == ["snapshot"], "No duplicate post-commit original scan"
        return SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64))

    def commit(stage, state, **kwargs):
        calls.append("commit")
        assert stage is reconnect.STAGE
        assert state is V2StageState.WAITING_OPERATOR
        assert kwargs["expected_head_sha256"] == "a" * 64
        event = V2JournalEvent.build(
            header=SimpleNamespace(
                session_id="MODELED-session", header_sha256="b" * 64
            ),
            sequence=1,
            stage=stage,
            previous_state=V2StageState.BLOCKED,
            state=state,
            occurred_at_ns=kwargs["occurred_at_ns"],
            previous_event_sha256="a" * 64,
            evidence=kwargs["evidence"],
            detail_code=kwargs["detail_code"],
        )
        return SimpleNamespace(committed_events=(event,))

    tx = SimpleNamespace(snapshot=snapshot, commit_stage_state=commit)
    with pytest.raises(RuntimeError, match="MODELED_LATE_SOURCE_GUARD"):
        original = phase._commit(
            tx, "PREPARATION_REQUESTED", V2StageState.WAITING_OPERATOR, PHASE_ID, []
        )
        assert phase.attempt["events"] == [original.to_dict()]
        raise RuntimeError("MODELED_LATE_SOURCE_GUARD")
    diagnostics = phase.diagnostics({})
    assert diagnostics["qualification_reconnect"] is None
    assert diagnostics["qualification_reconnect_attempt"]["events"] == [
        original.to_dict()
    ]
    assert calls == ["snapshot", "commit"]
    assert phase.reconnect is None and not phase.query_attempted
    diagnostics["qualification_reconnect_attempt"]["events"].clear()
    assert phase.attempt["events"] == [original.to_dict()]


def test_failed_commit_cannot_invent_a_cached_committed_event():
    phase = reconnect._UsbTrialReconnect(SimpleNamespace())
    phase.attempt = {"phase_id": PHASE_ID, "records": {}}

    def fail(*args, **kwargs):
        raise RuntimeError("MODELED_COMMIT_READBACK_FAILED")

    tx = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64)),
        commit_stage_state=fail,
    )
    with pytest.raises(RuntimeError, match="MODELED_COMMIT_READBACK_FAILED"):
        phase._commit(
            tx, "PREPARATION_REQUESTED", V2StageState.WAITING_OPERATOR, PHASE_ID, []
        )
    assert "events" not in phase.attempt


def test_acquisition_facade_routes_one_active_phase_and_drops_late_tokens():
    calls = []

    def subject(name):
        return SimpleNamespace(
            reconnect=None,
            acquisition_started=lambda *args: calls.append((name, "started", args))
            or {"operation_id": args[1]},
            acquisition_published=lambda token, **kwargs: calls.append(
                (name, "published", token, kwargs)
            ),
        )

    owner = SimpleNamespace(_lock=RLock(), _trial=subject("baseline"))
    owner._reconnect = subject("reconnect")
    start = PhysicalUsbIdentityService.acquisition_started
    publish = PhysicalUsbIdentityService.acquisition_published
    old_token = start(owner, "inventory_devices", "MODELED-before", 100)
    assert old_token["phase"] == "BASELINE"
    owner._reconnect.reconnect = {"phase_id": PHASE_ID}
    fresh_token = start(owner, "inventory_devices", "MODELED-after", 200)
    assert fresh_token["phase"] == "AFTER_RECONNECT"
    values = dict(
        finished_at_ns=300, document={"MODELED": True}, result_sha256="c" * 64
    )
    publish(owner, old_token, **values)
    assert len(calls) == 2
    publish(owner, fresh_token, **values)
    assert calls[-1] == ("reconnect", "published", fresh_token["token"], values)
    for malformed in (None, {}, {**fresh_token, "extra": True}):
        publish(owner, malformed, **values)
    assert len(calls) == 3
    owner._reconnect.acquisition_started = lambda *args: None
    assert start(owner, "inventory_devices", "MODELED-denied", 400) is None
    assert len(calls) == 3, "An active reconnect refusal must not fall back to baseline"


@pytest.mark.parametrize(
    "state,campaign,campaign_event",
    [
        ("ORIGINAL_CAMPAIGN_HELD", None, None),
        ("RETAINED_BLOCKED", None, None),
        ("QUERY_REQUESTED", {"MODELED": "original attempt"}, None),
        ("QUERY_REQUESTED", None, {"MODELED": "original event"}),
    ],
)
def test_refreshed_original_attempt_refuses_before_dispatch_construction(
    state, campaign, campaign_event, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("No new operation, persistence or dispatcher is permitted")

    for name in (
        "UsbIdentityOperation",
        "PhysicalUsbIdentityCampaign",
        "M1PhysicalUsbIdentityPersistence",
        "PhysicalUsbIdentityDispatchOwner",
    ):
        monkeypatch.setattr(reconnect, name, forbidden)
    phase = reconnect._UsbTrialReconnect(SimpleNamespace())
    workflow = {
        "usb_qualification_reconnect": {
            "state": state,
            "original_campaign": campaign,
            "original_campaign_event": campaign_event,
        }
    }
    with pytest.raises(WizardError) as raised:
        phase._collect_usb(workflow, None, None, forbidden, None)
    assert raised.value.code == "USB_RECONNECT_ORIGINAL_ATTEMPT_EXISTS"
    assert not phase.query_attempted
