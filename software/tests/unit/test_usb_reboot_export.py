"""Full v13-shaped cached exports; observations/owner projections are MODELED.

The actual exporter/restorer runs; original-store authentication and successful
physical qualification are intentionally not claimed by a diagnostic copy.
"""

from copy import deepcopy
from pathlib import Path

import pytest

from rocell.application import physical_usb_identity_export as m
from rocell.application.physical_camera_usb_reboot_constants import (
    MAX_USB_REBOOT_EVENTS,
    USB_REBOOT_ROLE_BYTES,
    USB_REBOOT_STATES,
)
from rocell.application.wizard_diagnostic_export import verify_export
from test_physical_usb_identity_export import exported, prepare, read_receipt, record
from test_usb_reconnect_export import reconnect_cache


def reboot_cache(state="RETAINED_BLOCKED"):
    value = reconnect_cache()
    evidence = dict(
        meaning="MODELED_REBOOT_EFFECTS",
        status="FAILED",
        counter_coverage="NOT_REPORTED",
        actual_counts=None,
    )
    value.update(
        schema=m.DIAGNOSTICS_V6_SCHEMA,
        qualification_reboot=dict(
            phase_id="usbphase-" + "6" * 32,
            phase="AFTER_REBOOT",
            state=state,
            events=[dict(meaning="MODELED_REBOOT_EVENT", state=state)],
            original_campaign=dict(
                evidence=evidence,
                evidence_sha256=m._hash(evidence),
                result=dict(state="SEALED_UNCERTAIN", quarantine_latched=True),
            ),
            original_campaign_event=dict(meaning="MODELED_REBOOT_TERMINAL"),
            **{
                role: record(dict(meaning="MODELED_REBOOT_ROLE", role=role))
                for role in USB_REBOOT_ROLE_BYTES
            },
        ),
        qualification_reboot_attempt=dict(
            state="HELD",
            records={"uncommitted": record(dict(meaning="MODELED_PARTIAL_WRITE"))},
            boot=dict(state="REQUESTED", host_boot=None),
            dispatch=dict(phase="ORIGINAL_READBACK_PENDING", used=True),
        ),
    )
    return value


@pytest.mark.parametrize("state", USB_REBOOT_STATES)
def test_all_states_export_complete_prefix_roles_attempts_and_unknowns(state):
    value = reboot_cache(state)
    original = deepcopy(value)
    report, parts = prepare(value)
    assert report["schema"] == m.EXPORT_V6_SCHEMA
    assert report["summary"]["qualification_reboot_state"] == state
    assert m.restore_usb_identity_diagnostics(report, parts) == original == value
    paths = {r["path"] for r in report["coverage"]}
    assert {"/qualification_reboot/" + r for r in USB_REBOOT_ROLE_BYTES} <= paths
    assert "/qualification_reboot/original_campaign" in paths
    assert "/qualification_reboot_attempt/records/uncommitted" in paths
    assert (
        value["qualification_reboot"]["original_campaign"]["evidence"]["actual_counts"]
        is None
    )
    assert report["original_bytes_preserved"] is True
    assert all(report[k] is False for k in m._FLAGS)


def test_requested_partial_and_missing_native_result_are_exportable():
    value = reboot_cache("PREPARATION_REQUESTED")
    phase = value["qualification_reboot"]
    for role in USB_REBOOT_ROLE_BYTES:
        phase[role] = None
    phase["original_campaign"].update(evidence=None, evidence_sha256=None)
    value["qualification_reboot_attempt"] = None
    report, parts = prepare(value)
    assert m.restore_usb_identity_diagnostics(report, parts) == value
    assert report["summary"]["qualification_reboot_sha256"] is None
    phase["events"] = [dict(sequence=i) for i in range(MAX_USB_REBOOT_EVENTS)]
    report, parts = prepare(value)
    assert m.restore_usb_identity_diagnostics(report, parts) == value


def test_failed_begin_without_original_suffix_keeps_diagnostics():
    value = reboot_cache()
    value["qualification_reboot"] = None
    report, parts = prepare(value)
    assert m.restore_usb_identity_diagnostics(report, parts) == value
    assert report["summary"]["qualification_reboot_phase_id"] is None


@pytest.mark.parametrize("role", USB_REBOOT_ROLE_BYTES)
def test_no_role_can_disappear_or_change_its_subject_hash(role):
    missing = reboot_cache()
    del missing["qualification_reboot"][role]
    with pytest.raises(m.UsbIdentityExportError):
        prepare(missing)
    changed = reboot_cache()
    changed["qualification_reboot"][role]["document"]["unexpected"] = True
    with pytest.raises(m.UsbIdentityExportError, match="SUBJECT_HASH"):
        prepare(changed)


@pytest.mark.parametrize(
    "key,bad",
    [
        ("phase_id", True),
        ("phase_id", "usbphase-wrong"),
        ("phase", "BASELINE"),
        ("phase", "AFTER_RECONNECT"),
        ("state", "PASS"),
        ("state", {}),
        ("events", []),
        ("events", [True]),
        ("events", [{}] * 8),
        ("operator_event", False),
        ("enrollment", []),
        ("identity", 0),
        ("original_campaign", []),
        ("original_campaign_event", False),
    ],
)
def test_v6_shape_is_closed_without_coercion(key, bad):
    value = reboot_cache()
    value["qualification_reboot"][key] = bad
    with pytest.raises(m.UsbIdentityExportError):
        prepare(value)


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_reboot_cannot_be_smuggled_into_legacy_envelope(version):
    value = reboot_cache()
    value["schema"] = f"rocell.wizard_usb_identity_diagnostics.v{version}"
    with pytest.raises(m.UsbIdentityExportError):
        prepare(value)
    report, parts = prepare(reboot_cache())
    report["schema"] = f"rocell.usb_identity_diagnostic_export.v{version}"
    with pytest.raises(m.UsbIdentityExportError):
        m.restore_usb_identity_diagnostics(report, parts)


def test_actual_export_uses_assigned_parent_and_round_trips_every_field(tmp_path):
    value = reboot_cache("BOOT_UNCERTAIN")
    receipt = exported(value, tmp_path / "assigned-folder")
    directory = Path(receipt["path"])
    assert directory.parent == tmp_path / "assigned-folder"
    assert verify_export(directory)["valid"]
    report, parts = read_receipt(receipt)
    assert m.restore_usb_identity_diagnostics(report, parts) == value
    assert receipt["physical_authority"] == "NONE"
    assert m.MAX_INPUT_BYTES == 6 * 1024 * 1024
    assert m.MAX_INPUT_DEPTH == 40 and m.MAX_INPUT_NODES == 200_000
