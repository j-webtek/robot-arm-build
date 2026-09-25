"""Pure source-report pointers, not original storage or qualification evidence."""

from copy import deepcopy

import pytest

from rocell.application.wizard_diagnostic_export import (
    sanitize_diagnostic_record,
    WizardDiagnosticExportError,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from test_arrival_wizard_service import make_service


@pytest.mark.parametrize("entry_state", [None, "INCOMPLETE", "ENTERED"])
def test_source_report_points_to_separate_full_subjects_without_mutating_them(
    make_service, entry_state
):
    app, _, _ = make_service(mode="physical")
    setup = app._physical_camera_setup
    nested = {"MODELED": True}
    for _ in range(15):
        nested = {"nested": nested}
    # Deliberately over-deep modeled campaign fields demonstrate why the
    # source summary cannot duplicate whole domain bundles. No reader runs.
    original = {"receipt": {"document": {"MODELED": True}}}
    for family, id_key in (
        ("usb_qualification_reconnect", "phase_id"),
        ("usb_qualification_reboot", "phase_id"),
        ("usb_qualification_complete", "series_id"),
    ):
        original[family] = {
            id_key: "MODELED-not-an-original",
            "state": "MODELED-not-qualification",
            "original_campaign": deepcopy(nested),
        }
    if entry_state:
        original["camera_mode_entry"] = {
            "state": entry_state,
            "entry": {"evidence_sha256": "a" * 64, "document": deepcopy(nested)},
        }
    setup._source_workflow = deepcopy(original)
    with pytest.raises(WizardDiagnosticExportError):
        sanitize_diagnostic_record(original)
    result = setup.retained_source_diagnostics()
    assert sanitize_diagnostic_record(result) == result
    assert setup._source_workflow == original
    for family in (
        "usb_qualification_reconnect",
        "usb_qualification_reboot",
        "usb_qualification_complete",
    ):
        assert family not in result["original"]
        assert result[family + "_sha256"] == digest(canonical(original[family]))
    assert result["usb_separate_metadata_export_required"] is True
    if entry_state:
        assert "camera_mode_entry" not in result["original"]
        assert result["camera_mode_entry_sha256"] == digest(
            canonical(original["camera_mode_entry"])
        )
        assert result["camera_mode_entry_summary"] == {
            "state": entry_state,
            "entry_sha256": "a" * 64,
            "attachment": "attachment-camera-mode-entry.json",
        }


def test_general_export_retains_bounded_usb_coverage_and_explicit_full_bundle_link(
    make_service, monkeypatch
):
    app, runner, _ = make_service(mode="physical")
    # Supplied cached display is MODELED, not an original or qualification.
    value = app._usb_qualification_view()
    value["plan"] = {"plan_sha256": "a" * 64}
    for phase in ("baseline", "absence", "reconnect", "reboot"):
        value[phase] = {
            "phase_id": "MODELED-" + phase,
            "state": "RETAINED_BLOCKED",
            "phase_record": {"phase_sha256": "b" * 64},
            "MODELED_repeated_display": ["large display details"] * 2000,
        }
    value["complete"] = {
        "series_id": "usbseries-" + "1" * 32,
        "state": "REVIEWED_PASS",
        "series_sha256": "c" * 64,
        "assessment_sha256": "d" * 64,
        "review_sha256": "e" * 64,
        "assessment": {"MODELED_NOT_AN_ORIGINAL": ["details"] * 2000},
    }
    original = deepcopy(value)
    monkeypatch.setattr(app, "_usb_qualification_view", lambda: deepcopy(value))
    pointer = app._usb_qualification_export_pointer()
    assert sanitize_diagnostic_record(pointer) == pointer
    assert len(canonical(pointer)) < 8192
    assert pointer["original_documents_included"] is False
    assert pointer["separate_metadata_export_required"] is True
    assert pointer["required_action"] == "physical_usb_identity_export"
    assert pointer["complete"]["review_sha256"] == "e" * 64
    assert "assessment" not in pointer["complete"]
    assert all(p["phase_sha256"] == "b" * 64 for p in pointer["phases"].values())
    assert value == original and not runner.calls
