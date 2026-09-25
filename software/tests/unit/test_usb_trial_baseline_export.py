"""Additive full phase exports: cached modeled data, never hardware proof."""

from copy import deepcopy
from pathlib import Path

import pytest

from rocell.application import physical_usb_identity_export as module
from rocell.application.wizard_diagnostic_export import verify_export
from test_physical_usb_identity_export import exported, prepare, read_receipt, record
from test_usb_qualification_export import trial_cache


STATES = (
    "ENTERED",
    "PREPARATION_REQUESTED",
    "PREPARED",
    "REVIEWED",
    "BOOT_REQUESTED",
    "BOOT_RETAINED",
    "BOOT_HELD",
    "BOOT_UNCERTAIN",
    "QUERY_REQUESTED",
    "ORIGINAL_CAMPAIGN_HELD",
    "RETAINED_BLOCKED",
    "INCOMPLETE",
)
ROLES = (
    "enrollment",
    "preparation",
    "policy_review",
    "runtime_review",
    "identity",
    "boot_request",
    "host_boot",
    "execution",
    "phase_record",
)


def phase_cache(state="RETAINED_BLOCKED"):
    cache = trial_cache()
    cache.update(
        schema=module.DIAGNOSTICS_V3_SCHEMA,
        qualification_baseline=dict(
            phase_id="usbphase-" + "3" * 32,
            phase="BASELINE",
            state=state,
            events=[dict(meaning="MODELED_V2_EVENT", phase=state)],
            original_campaign=dict(
                evidence=dict(meaning="MODELED_OWNED_RUN", result="HELD"),
                evidence_sha256=module._hash(
                    dict(meaning="MODELED_OWNED_RUN", result="HELD")
                ),
                result=None,
            ),
            original_campaign_event=dict(meaning="MODELED_INTENT_NOT_TERMINAL"),
            **{role: record(dict(meaning="MODELED_ROLE", role=role)) for role in ROLES},
        ),
        qualification_attempt=dict(
            state="HELD",
            acquisition_ledger=[dict(meaning="MODELED_TIMING")],
            boot=dict(state="REQUESTED", host_boot=None),
            records=dict(partial=record(dict(meaning="MODELED_UNCOMMITTED_BYTES"))),
        ),
    )
    return cache


@pytest.mark.parametrize("state", STATES)
def test_all_closed_states_preserve_full_bytes_and_nonterminal_campaign(state):
    value = phase_cache(state)
    before = deepcopy(value)
    snapshot, parts = prepare(value)
    assert snapshot["schema"] == module.EXPORT_V3_SCHEMA
    assert snapshot["summary"]["qualification_baseline_state"] == state
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == before == value
    covered = {row["path"] for row in snapshot["coverage"]}
    assert {"/qualification_baseline/" + role for role in ROLES} <= covered
    assert "/qualification_baseline/original_campaign" in covered
    assert "/qualification_attempt/records/partial" in covered
    assert snapshot["original_bytes_preserved"] is True
    assert snapshot["physical_authority"] is False


def test_partial_attempt_without_original_phase_is_not_dropped():
    value = phase_cache()
    value["qualification_baseline"] = None
    snapshot, parts = prepare(value)
    assert snapshot["summary"]["qualification_baseline_state"] is None
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value


def test_actual_export_manifest_and_reconstruction(tmp_path):
    value = phase_cache("BOOT_UNCERTAIN")
    receipt = exported(value, tmp_path / "assigned-exports")
    assert Path(receipt["path"]).parent == tmp_path / "assigned-exports"
    assert verify_export(Path(receipt["path"]))["valid"]
    snapshot, parts = read_receipt(receipt)
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value
    assert receipt["physical_authority"] == "NONE"


@pytest.mark.parametrize(
    "key,value",
    [
        ("phase_id", "wrong"),
        ("phase_id", True),
        ("phase", "AFTER_RECONNECT"),
        ("state", "PASS"),
        ("state", True),
        ("state", []),
        ("state", {}),
        ("events", []),
        ("events", [False]),
        ("events", [{}] * 9),
        ("host_boot", False),
        ("phase_record", []),
        ("original_campaign", 0),
        ("original_campaign_event", False),
    ],
)
def test_closed_phase_shape_refuses_coercion(key, value):
    cache = phase_cache()
    cache["qualification_baseline"][key] = value
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize("value", [None, True, [], {}])
def test_nontext_schema_refuses_without_unhashable_key_error(value):
    cache = phase_cache()
    cache["schema"] = value
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_diagnostics_cannot_hide_added_phase_fields(version):
    cache = phase_cache()
    cache["schema"] = (
        module.DIAGNOSTICS_SCHEMA if version == 1 else module.DIAGNOSTICS_V2_SCHEMA
    )
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize("schema", [module.EXPORT_SCHEMA, module.EXPORT_V2_SCHEMA])
def test_phase_export_cannot_be_relabelled_as_legacy(schema):
    snapshot, parts = prepare(phase_cache())
    snapshot["schema"] = schema
    with pytest.raises(
        module.UsbIdentityExportError, match="USB_EXPORT_SCHEMA_MISMATCH"
    ):
        module.restore_usb_identity_diagnostics(snapshot, parts)


def test_full_phase_subject_hash_is_checked_before_export():
    cache = phase_cache()
    cache["qualification_baseline"]["host_boot"]["document"]["changed"] = True
    with pytest.raises(module.UsbIdentityExportError, match="USB_EXPORT_SUBJECT_HASH"):
        prepare(cache)


def test_redaction_explicitly_loses_original_byte_claim_not_phase_records():
    cache = phase_cache()
    cache["qualification_baseline"]["host_boot"] = record(
        dict(password="MODELED_SECRET", meaning="MODELED_PRIVATE_REPORT")
    )
    snapshot, parts = prepare(cache)
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    assert (
        restored["qualification_baseline"]["host_boot"]["document"]["password"]
        == "[REDACTED]"
    )
    assert restored["qualification_baseline"]["state"] == "RETAINED_BLOCKED"
    assert snapshot["original_bytes_preserved"] is False
    assert snapshot["credential_redaction_applied"] is True
