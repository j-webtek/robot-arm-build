"""Exact additive trial exports; fixtures are modeled, never stage evidence."""

from copy import deepcopy

import pytest

from rocell.application import physical_usb_identity_export as module
from rocell.application.wizard_diagnostic_export import verify_export
from test_physical_usb_identity_export import (
    diagnostics,
    exported,
    prepare,
    read_receipt,
    record,
)


def trial_cache(state="PLAN_DECLARED"):
    value = diagnostics()
    value["schema"] = module.DIAGNOSTICS_V2_SCHEMA
    value["qualification_trial"] = dict(
        trial_id="usbtrial-" + "2" * 32,
        state=state,
        request_event={"meaning": "MODELED_ORIGINAL_REQUEST"},
        declaration_event=(
            {"meaning": "MODELED_ORIGINAL_DECLARATION"}
            if state == "PLAN_DECLARED"
            else None
        ),
        plan=(
            record(
                {
                    "schema": "MODELED_PLAN",
                    "cable_label": "bench cable",
                    "authority": False,
                }
            )
            if state != "INCOMPLETE"
            else None
        ),
    )
    return value


@pytest.mark.parametrize(
    "state", ["INCOMPLETE", "PLAN_RETAINED_NOT_COMMITTED", "PLAN_DECLARED"]
)
def test_v2_preserves_every_trial_state_and_full_original_records(tmp_path, state):
    value = trial_cache(state)
    before = deepcopy(value)
    receipt = exported(value, tmp_path / "exports")
    from pathlib import Path

    assert verify_export(Path(receipt["path"]))["valid"]
    snapshot, parts = read_receipt(receipt)
    assert snapshot["schema"] == module.EXPORT_V2_SCHEMA
    assert snapshot["summary"]["qualification_state"] == state
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == before == value
    assert snapshot["original_bytes_preserved"]
    assert receipt["physical_authority"] == "NONE"
    if state != "INCOMPLETE":
        assert any(
            row["path"] == "/qualification_trial/plan" for row in snapshot["coverage"]
        )


@pytest.mark.parametrize("version", [1, 2])
def test_export_schema_cannot_relabel_the_reconstructed_version(version):
    value = diagnostics() if version == 1 else trial_cache()
    snapshot, parts = prepare(value)
    snapshot["schema"] = (
        module.EXPORT_V2_SCHEMA if version == 1 else module.EXPORT_SCHEMA
    )
    with pytest.raises(
        module.UsbIdentityExportError, match="USB_EXPORT_SCHEMA_MISMATCH"
    ):
        module.restore_usb_identity_diagnostics(snapshot, parts)


def test_v1_does_not_accept_silent_trial_extension():
    value = trial_cache()
    value["schema"] = module.DIAGNOSTICS_SCHEMA
    with pytest.raises(module.UsbIdentityExportError):
        prepare(value)


@pytest.mark.parametrize(
    "key,value",
    [
        ("trial_id", "wrong-prefix"),
        ("state", "PASS"),
        ("request_event", None),
        ("plan", []),
        ("declaration_event", False),
    ],
)
def test_closed_trial_fields_reject_coercions(key, value):
    cache = trial_cache()
    cache["qualification_trial"][key] = value
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


def test_complete_trial_document_is_redacted_without_false_original_claim():
    value = trial_cache()
    value["qualification_trial"]["plan"] = record(
        {"password": "MODEL_SECRET", "note": "test"}
    )
    snapshot, parts = prepare(value)
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    assert (
        restored["qualification_trial"]["plan"]["document"]["password"] == "[REDACTED]"
    )
    assert snapshot["original_bytes_preserved"] is False
    assert snapshot["credential_redaction_applied"] is True


def test_unmodified_v1_format_still_has_no_trial_fields():
    snapshot, parts = prepare(diagnostics())
    assert snapshot["schema"] == module.EXPORT_SCHEMA
    assert "qualification_state" not in snapshot["summary"]
    assert "qualification_trial" not in module.restore_usb_identity_diagnostics(
        snapshot, parts
    )
