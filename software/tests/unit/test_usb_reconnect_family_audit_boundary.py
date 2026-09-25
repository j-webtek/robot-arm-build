"""Audit-call boundaries only: modeled ledgers, no M1 or provider execution."""

from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
)
from rocell.application.commissioning_usb_identity_persistence import RECORD_SCHEMA
from rocell.application.physical_camera_session import PhysicalCameraSessionError
from rocell.application.physical_camera_usb_absence_readback import (
    read_original_usb_absence_campaigns,
)
from test_physical_usb_identity_campaign import campaign, permit_for


def audit_fixture(monkeypatch, count, *, changed_attempts=False, audit_error=False):
    original = replace(permit_for(campaign()), nonce="9" * 64)
    records, events = {}, {}
    for i in range(count):
        permit = replace(
            original,
            attempt_id="attempt-" + f"{i:032x}",
            request=replace(original.request, request_key=f"MODELED-family-{i}"),
        )
        event = SimpleNamespace(state=SimpleNamespace(value="INTENT"))
        event.to_dict = lambda p=permit: {"attempt_id": p.attempt_id, "state": "INTENT"}
        events[permit.attempt_id] = event
        records[f"request-MODELED-{i}.json"] = {
            "schema": RECORD_SCHEMA,
            "data": {"permit": asdict(permit), "admission_evidence": {}},
        }
    before = SimpleNamespace(latest_event=events.get)
    calls = []

    def snapshot():
        calls.append("attempts")
        return object() if changed_attempts and calls.count("attempts") > 1 else before

    def audit(self, *, include_family=False):
        calls.append(("full_audit", include_family))
        if audit_error:
            raise RuntimeError("MODELED sibling corruption; never filtered away")
        return records

    monkeypatch.setattr(
        M1PhysicalCameraTransaction, "_check_scope", lambda self: calls.append("scope")
    )
    monkeypatch.setattr(
        M1PhysicalCameraTransaction,
        "held_leases",
        property(lambda self: ("MODELED_CELL", "MODELED_SESSION")),
    )
    monkeypatch.setattr(M1PhysicalCameraTransaction, "_audit_records", audit)
    tx = object.__new__(M1PhysicalCameraTransaction)
    tx._attempts = SimpleNamespace(snapshot=snapshot)
    return tx, original.request.session_id, calls


def test_v12_three_descriptor_limit_preserves_complete_sibling_audit(monkeypatch):
    tx, session, calls = audit_fixture(monkeypatch, 3)
    value = read_original_usb_absence_campaigns(
        tx, session, _usb_reconnect_extension=True
    )
    assert len(value["identity"]) == 3 and value["presence"] == ()
    assert calls == ["scope", ("full_audit", True), "attempts", "attempts", "scope"]
    with pytest.raises(PhysicalCameraSessionError):
        read_original_usb_absence_campaigns(tx, session)


def test_fourth_descriptor_attempt_rejected_even_in_new_version(monkeypatch):
    tx, session, _ = audit_fixture(monkeypatch, 4)
    with pytest.raises(PhysicalCameraSessionError):
        read_original_usb_absence_campaigns(tx, session, _usb_reconnect_extension=True)


def test_changed_global_attempt_view_rejected_after_read(monkeypatch):
    tx, session, _ = audit_fixture(monkeypatch, 1, changed_attempts=True)
    with pytest.raises(PhysicalCameraSessionError):
        read_original_usb_absence_campaigns(tx, session, _usb_reconnect_extension=True)


def test_sibling_audit_failure_is_not_filtered_by_selected_session(monkeypatch):
    tx, session, _ = audit_fixture(monkeypatch, 1, audit_error=True)
    with pytest.raises(RuntimeError, match="sibling corruption"):
        read_original_usb_absence_campaigns(tx, session, _usb_reconnect_extension=True)
