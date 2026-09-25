"""Full v11-shaped absence caches, explicitly MODELED and never hardware proof.

The exporter authenticates supplied bytes, not original M1 storage or device
truth. Public service/original-store tests separately supply genuine readback.
"""

from copy import deepcopy
from pathlib import Path

import pytest

from rocell.application import physical_usb_identity_export as module
from rocell.application.physical_camera_usb_absence_constants import (
    MAX_USB_ABSENCE_EVENTS,
    USB_ABSENCE_ROLE_BYTES,
    USB_ABSENCE_STATES,
)
from rocell.application.wizard_diagnostic_export import verify_export
from test_physical_usb_identity_export import exported, prepare, read_receipt, record
from test_usb_trial_baseline_export import phase_cache


def absence_cache(state="RETAINED_BLOCKED"):
    """Retain a complete modeled cache, including nonterminal effect bytes."""
    cache = phase_cache()
    evidence = dict(
        meaning="MODELED_PRESENCE_OWNER",
        native_outcome=None,
        actual_counts=dict(
            api_calls=None,
            device_handle_opens=None,
            configuration_writes=None,
            frames=None,
        ),
        cleanup_confirmed=False,
    )
    cache.update(
        schema=module.DIAGNOSTICS_V4_SCHEMA,
        qualification_absence=dict(
            phase_id="usbphase-" + "4" * 32,
            phase="RECONNECT_ABSENCE",
            state=state,
            events=[dict(meaning="MODELED_ABSENCE_EVENT", state=state)],
            original_campaign=dict(
                evidence=evidence,
                evidence_sha256=module._hash(evidence),
                result=dict(state="SEALED_UNCERTAIN", quarantine_latched=True),
            ),
            original_campaign_event=dict(meaning="MODELED_TERMINAL_EVENT"),
            **{
                role: record(dict(meaning="MODELED_ABSENCE_ROLE", role=role))
                for role in USB_ABSENCE_ROLE_BYTES
            },
        ),
        qualification_absence_attempt=dict(
            state="HELD",
            boot=dict(state="BOOT_REQUESTED", host_boot=None),
            dispatch=dict(phase="ORIGINAL_READBACK_PENDING", used=True),
            records=dict(partial=record(dict(meaning="MODELED_UNCOMMITTED_REPORT"))),
        ),
    )
    return cache


@pytest.mark.parametrize("state", sorted(USB_ABSENCE_STATES))
def test_all_absence_states_preserve_nine_roles_originals_and_unknowns(state):
    value = absence_cache(state)
    before = deepcopy(value)
    snapshot, parts = prepare(value)
    assert snapshot["schema"] == module.EXPORT_V4_SCHEMA
    assert snapshot["summary"]["qualification_absence_state"] == state
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == before == value
    covered = {row["path"] for row in snapshot["coverage"]}
    assert {
        "/qualification_absence/" + role for role in USB_ABSENCE_ROLE_BYTES
    } <= covered
    assert "/qualification_absence/original_campaign" in covered
    assert "/qualification_absence_attempt/records/partial" in covered
    assert snapshot["original_bytes_preserved"] is True
    assert all(snapshot[key] is False for key in module._FLAGS)
    # Unknown counts must not be rendered or restored as invented zero effects.
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    counts = restored["qualification_absence"]["original_campaign"]["evidence"][
        "actual_counts"
    ]
    assert all(value is None for value in counts.values())
    assert restored["qualification_baseline"] == before["qualification_baseline"]
    assert restored["qualification_attempt"] == before["qualification_attempt"]


def test_failed_begin_without_original_absence_retains_full_attempt():
    value = absence_cache()
    value["qualification_absence"] = None
    snapshot, parts = prepare(value)
    assert snapshot["summary"]["qualification_absence_state"] is None
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value
    assert "/qualification_absence_attempt/records/partial" in {
        row["path"] for row in snapshot["coverage"]
    }


def test_pending_original_with_null_roles_and_no_live_attempt_is_exportable():
    value = absence_cache("PREPARATION_REQUESTED")
    phase = value["qualification_absence"]
    for key in (
        *USB_ABSENCE_ROLE_BYTES,
        "original_campaign",
        "original_campaign_event",
    ):
        phase[key] = None
    value["qualification_absence_attempt"] = None
    snapshot, parts = prepare(value)
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value
    assert snapshot["summary"]["qualification_absence_sha256"] is None


def test_complete_ten_event_roster_and_interrupted_review_request_are_preserved():
    # The exporter preserves supplied records rather than authenticating event
    # grammar. The original reader independently checks the REQUESTED/PREPARED
    # pair required by the unchanged V2 stage transition table.
    assert MAX_USB_ABSENCE_EVENTS == 10
    assert "PRESENCE_REVIEW_REQUESTED" in USB_ABSENCE_STATES
    value = absence_cache()
    value["qualification_absence"]["events"] = [
        dict(sequence=index, meaning="MODELED_ABSENCE_EVENT")
        for index in range(1, MAX_USB_ABSENCE_EVENTS + 1)
    ]
    snapshot, parts = prepare(value)
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value
    value["qualification_absence"]["state"] = "PRESENCE_REVIEW_REQUESTED"
    value["qualification_absence"]["events"] = value["qualification_absence"]["events"][
        :6
    ]
    for role in ("runtime_review", "execution", "phase_record"):
        value["qualification_absence"][role] = None
    value["qualification_absence"]["original_campaign"] = None
    value["qualification_absence"]["original_campaign_event"] = None
    snapshot, parts = prepare(value)
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == value


def test_actual_files_keep_assigned_parent_and_restore_complete_cache(tmp_path):
    value = absence_cache("BOOT_UNCERTAIN")
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
        ("phase", "BASELINE"),
        ("phase", "AFTER_RECONNECT"),
        ("state", "PASS"),
        ("state", True),
        ("state", []),
        ("state", {}),
        ("events", []),
        ("events", [False]),
        ("events", [{}] * (MAX_USB_ABSENCE_EVENTS + 1)),
        ("operation", False),
        ("operator_event", []),
        ("preparation", 0),
        ("boot_intent", False),
        ("boot_review", []),
        ("host_boot", 1),
        ("runtime_review", False),
        ("execution", []),
        ("phase_record", 0),
        ("original_campaign", []),
        ("original_campaign_event", False),
    ],
)
def test_absence_shape_refuses_wrong_phase_state_and_implicit_coercion(key, value):
    cache = absence_cache()
    cache["qualification_absence"][key] = value
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize("role", list(USB_ABSENCE_ROLE_BYTES))
def test_no_absence_role_can_disappear_from_closed_cache(role):
    cache = absence_cache()
    del cache["qualification_absence"][role]
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize(
    "key", ["qualification_absence", "qualification_absence_attempt"]
)
@pytest.mark.parametrize("value", [False, [], 0, "hidden"])
def test_top_level_absence_records_require_explicit_dict_or_null(key, value):
    cache = absence_cache()
    cache[key] = value
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize(
    "schema",
    [
        module.DIAGNOSTICS_SCHEMA,
        module.DIAGNOSTICS_V2_SCHEMA,
        module.DIAGNOSTICS_V3_SCHEMA,
    ],
)
def test_absence_cannot_be_hidden_in_legacy_diagnostic_version(schema):
    cache = absence_cache()
    cache["schema"] = schema
    with pytest.raises(module.UsbIdentityExportError):
        prepare(cache)


@pytest.mark.parametrize(
    "schema", [module.EXPORT_SCHEMA, module.EXPORT_V2_SCHEMA, module.EXPORT_V3_SCHEMA]
)
def test_absence_bundle_cannot_be_relabelled_as_an_older_export(schema):
    snapshot, parts = prepare(absence_cache())
    snapshot["schema"] = schema
    with pytest.raises(
        module.UsbIdentityExportError, match="USB_EXPORT_SCHEMA_MISMATCH"
    ):
        module.restore_usb_identity_diagnostics(snapshot, parts)


@pytest.mark.parametrize("role", list(USB_ABSENCE_ROLE_BYTES))
def test_every_absence_subject_hash_is_checked_before_writing(role):
    cache = absence_cache()
    cache["qualification_absence"][role]["document"]["changed"] = True
    with pytest.raises(module.UsbIdentityExportError, match="USB_EXPORT_SUBJECT_HASH"):
        prepare(cache)


def test_partial_attempt_bytes_are_also_hash_checked():
    cache = absence_cache()
    cache["qualification_absence_attempt"]["records"]["partial"]["document"][
        "changed"
    ] = True
    with pytest.raises(module.UsbIdentityExportError, match="USB_EXPORT_SUBJECT_HASH"):
        prepare(cache)


def test_redaction_keeps_all_roles_but_withholds_original_byte_claim():
    cache = absence_cache()
    cache["qualification_absence"]["operator_event"] = record(
        dict(password="MODELED_SECRET", meaning="MODELED_PRIVATE_OPERATOR_REPORT")
    )
    snapshot, parts = prepare(cache)
    restored = module.restore_usb_identity_diagnostics(snapshot, parts)
    assert (
        restored["qualification_absence"]["operator_event"]["document"]["password"]
        == "[REDACTED]"
    )
    assert restored["qualification_absence"]["state"] == "RETAINED_BLOCKED"
    assert snapshot["original_bytes_preserved"] is False
    assert snapshot["credential_redaction_applied"] is True
    assert set(restored["qualification_absence"]) == set(cache["qualification_absence"])


def test_summary_is_derived_from_exact_exported_cache_not_editable_authority():
    snapshot, parts = prepare(absence_cache("BOOT_HELD"))
    snapshot["summary"]["qualification_absence_state"] = "RETAINED_BLOCKED"
    with pytest.raises(module.UsbIdentityExportError):
        module.restore_usb_identity_diagnostics(snapshot, parts)


def test_role_budget_sized_diagnostics_fit_existing_export_limits():
    """Model near-cap subjects; not a claim that arbitrary 6MiB inputs fit."""
    cache = absence_cache()
    for role, maximum in USB_ABSENCE_ROLE_BYTES.items():
        # Short distinct text values keep both the parser's string cap and the
        # fixed role byte cap visible while exercising multi-part graph packing.
        rows = [
            f"{role}-{index:04d}-" + "x" * 900
            for index in range((maximum - 512) // 950)
        ]
        document = dict(meaning="MODELED_NEAR_CAP_ROLE", role=role, rows=rows)
        assert len(module._canonical(document)) < maximum
        cache["qualification_absence"][role] = record(document)
    snapshot, parts = prepare(cache)
    assert len(parts) <= module.MAX_ATTACHMENTS
    assert all(len(raw) <= module.MAX_ATTACHMENT_BYTES for raw in parts.values())
    assert module.restore_usb_identity_diagnostics(snapshot, parts) == cache
