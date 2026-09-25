"""V7 cached diagnostic export; invented observations are never qualification."""

from copy import deepcopy
from pathlib import Path
import pytest

from rocell.application import physical_usb_identity_export as m
from rocell.application.physical_camera_usb_complete_constants import (
    USB_COMPLETE_STATES,
    USB_COMPLETE_ROLE_BYTES,
)
from rocell.application.wizard_diagnostic_export import verify_export
from test_usb_reboot_export import reboot_cache
from test_physical_usb_identity_export import prepare, record, exported, read_receipt


def complete_cache(state="REVIEWED_PASS", role_count=3):
    value = reboot_cache()
    roles = tuple(USB_COMPLETE_ROLE_BYTES)
    value.update(
        schema=m.DIAGNOSTICS_V7_SCHEMA,
        qualification_complete=dict(
            series_id="usbseries-" + "7" * 32,
            state=state,
            events=[dict(meaning="MODELED_REVIEW_EVENT")],
            meaning="MODELED_ONLY_NOT_ORIGINAL_AUTHENTICATION",
            **{
                role: (
                    record(dict(role=role, meaning="MODELED_FILE_ROLE"))
                    if n < role_count
                    else None
                )
                for n, role in enumerate(roles)
            }
        ),
        qualification_complete_attempt=dict(
            action_id="physical_usb_complete_assess",
            series_id="usbseries-" + "7" * 32,
            records={"series": record(dict(meaning="MODELED_PARTIAL_WRITE"))},
            events=[],
        ),
    )
    return value


@pytest.mark.parametrize("state", USB_COMPLETE_STATES)
def test_every_complete_state_preserves_original_roles_and_attempts(state):
    value = complete_cache(state)
    before = deepcopy(value)
    report, parts = prepare(value)
    assert report["schema"] == m.EXPORT_V7_SCHEMA
    assert report["summary"]["qualification_complete_state"] == state
    assert m.restore_usb_identity_diagnostics(report, parts) == before == value
    paths = {row["path"] for row in report["coverage"]}
    assert {
        "/qualification_complete/" + role for role in USB_COMPLETE_ROLE_BYTES
    } <= paths
    assert "/qualification_complete_attempt/records/series" in paths
    assert "/qualification_reboot/original_campaign" in paths
    assert report["original_bytes_preserved"] is True
    assert all(report[flag] is False for flag in m._FLAGS)


@pytest.mark.parametrize("role_count", range(4))
def test_partial_publications_and_original_request_absence_are_exportable(role_count):
    value = complete_cache("INCOMPLETE", role_count)
    for row in (value, {**value, "qualification_complete": None}):
        report, parts = prepare(row)
        assert m.restore_usb_identity_diagnostics(report, parts) == row


@pytest.mark.parametrize(
    "fault",
    [
        "old-schema",
        "extra-role",
        "extra-phase",
        "bad-id",
        "too-many-events",
        "oversize-role",
        "unknown-attempt",
    ],
)
def test_bad_new_envelope_fails_without_dropping_subjects(fault):
    value = complete_cache()
    row = value["qualification_complete"]
    if fault == "old-schema":
        value["schema"] = m.DIAGNOSTICS_V6_SCHEMA
    elif fault == "extra-role":
        row["unexpected"] = record()
    elif fault == "extra-phase":
        row["original_campaign"] = {}
    elif fault == "bad-id":
        row["series_id"] = "usbphase-" + "7" * 32
    elif fault == "too-many-events":
        row["events"] *= 4
    elif fault == "oversize-role":
        row["review"] = record(dict(oversize="x" * (8 * 1024)))
    else:
        value["qualification_complete_attempt"][
            "action_id"
        ] = "physical_usb_reboot_collect"
    with pytest.raises(m.UsbIdentityExportError):
        prepare(value)


def test_actual_unique_export_and_independent_restore(tmp_path):
    value = complete_cache()
    parent = tmp_path / "assigned-export-folder"
    receipt = exported(value, parent)
    assert verify_export(Path(receipt["path"]))["valid"]
    report, parts = read_receipt(receipt)
    assert (
        m.restore_usb_identity_diagnostics(
            report, parts, expected_original_diagnostics_sha256=m._hash(value)
        )
        == value
    )
    assert Path(receipt["path"]).parent == parent
