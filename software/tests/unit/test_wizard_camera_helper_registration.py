"""Pure fixed-catalog registration: no helper process or filesystem inspection."""

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

import rocell.application.wizard_camera_helper_inspection as inspection_module
import rocell.application.wizard_camera_helper_registration as module
from rocell.application.wizard_camera_helper_inspection import (
    rehearsal_camera_helper_inspection,
)
from rocell.application.wizard_camera_helper_registration import (
    CameraHelperRegistrationError,
    ReviewedCameraHelperRegistration,
    WizardCameraHelperRegistration,
)
from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record


SOURCE = "a" * 64
SESSION = "wizard-helper-fixture"


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def fixture(scenario="nominal", *, source=SOURCE):
    return rehearsal_camera_helper_inspection(source_sha256=source, scenario=scenario)


def model():
    return WizardCameraHelperRegistration("rehearsal", SESSION, SOURCE)


def inspected(scenario="nominal"):
    state = model()
    report = fixture(scenario)
    result = state.ingest(
        report, operation_id="inspect-operation", operator_id="operator-a"
    )
    return state, report, result


def registered():
    state, report, _ = inspected()
    result = state.review("reviewer-b", operation_id="review-operation")
    return state, report, result


def reseal(report):
    report["inspection_sha256"] = hashlib.sha256(
        canonical(
            {key: value for key, value in report.items() if key != "inspection_sha256"}
        )
    ).hexdigest()
    return report


def assert_no_activation(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {
                "physical_authority",
                "connected",
                "qualified",
                "probe_allowed",
                "capture_allowed",
                "camera_activation_allowed",
                "driver_qualified",
                "trusted_release",
                "historical_full_build_match",
            }:
                assert child is False
            assert_no_activation(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_activation(child)


def test_actual_nominal_inspection_is_not_automatically_registered():
    state, original, result = inspected()
    assert result["inspection_report"] == original
    assert result["view"]["status"] == "INSPECTION_RETAINED"
    assert result["registration_artifact"] is None
    assert state.registration() is None
    assert state.view()["review"] is None
    preview = state.preview()
    assert preview["inspection"]["eligible_for_metadata_registration"] is True
    assert preview["inspection"]["inspection_provenance"] == "INCAPABLE_FIXTURE"
    assert preview["inspection"]["helper_sha256"] == original["helper_sha256"]
    assert preview["allowed_operations"] == ["inventory", "identity"]
    assert "CLIENT_CHANGED_SINCE_BUILD_RECORD" in preview["blockers"]
    assert_no_activation(result)
    assert_no_activation(preview)


def test_review_binds_exact_source_catalog_actors_operations_and_full_inspection():
    state, original, result = registered()
    artifact = state.registration()
    assert isinstance(artifact, ReviewedCameraHelperRegistration)
    payload = artifact.payload
    assert payload["schema"] == "rocell.wizard_camera_helper_registration_artifact.v1"
    assert payload["status"] == "METADATA_ONLY_REGISTERED"
    assert payload["mode"] == "rehearsal"
    assert payload["session_id"] == SESSION
    assert payload["source_sha256"] == SOURCE
    for key in ("catalog_id", "catalog_sha256", "helper_sha256", "inspection_sha256"):
        assert payload[key] == original[key]
    assert artifact.inspection == original
    assert payload["inspection_operation_id"] == "inspect-operation"
    assert payload["inspection_operator_id"] == "operator-a"
    assert payload["review_operation_id"] == "review-operation"
    assert payload["reviewer_id"] == "reviewer-b"
    assert payload["distinct_operator_labels"] is True
    assert payload["trust_scope"] == "DEVELOPMENT_METADATA_ONLY_NOT_TRUSTED_RELEASE"
    assert (
        artifact.registration_sha256 == hashlib.sha256(canonical(payload)).hexdigest()
    )
    assert result["registration_artifact"] == artifact.to_dict()
    assert result["inspection_report"] == original
    assert result["view"]["status"] == "METADATA_HELPER_REGISTERED"
    assert (
        result["view"]["review"]["registration_sha256"] == artifact.registration_sha256
    )
    assert result == state.export_snapshot()
    assert_no_activation(result)


def test_actual_full_helper_result_survives_diagnostic_boundary_without_redaction():
    _, original, report = registered()
    envelope = {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": "camera_helper_review",
        "status": "SUCCEEDED",
        "steps": [{"name": "camera_helper_review", "exit_code": 0, "report": report}],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }
    clean = sanitize_diagnostic_record(envelope, maximum_bytes=1024 * 1024)
    assert clean == envelope
    assert clean["steps"][0]["report"]["inspection_report"] == original
    assert len(canonical(report)) < module.MAX_REPORT_BYTES
    assert len(json.dumps(envelope, indent=2).encode("utf-8")) < 1024 * 1024


@pytest.mark.parametrize(
    "scenario,status",
    [("missing-helper", "MISSING_FILES"), ("hash-drift", "HASH_DRIFT")],
)
def test_actual_held_inspections_can_be_acknowledged_but_not_registered(
    scenario, status
):
    state, original, _ = inspected(scenario)
    assert state.preview()["inspection"]["eligible_for_metadata_registration"] is False
    result = state.review("reviewer-b", operation_id="review-operation")
    assert result["view"]["status"] == "REVIEW_HELD"
    assert result["view"]["inspection"]["inspection_status"] == status
    assert result["view"]["inspection"]["helper_sha256"] is None
    assert result["view"]["review"]["status"] == "ACKNOWLEDGED_BUT_HELD"
    assert result["view"]["review"]["registration_sha256"] is None
    assert result["inspection_report"] == original
    assert status in result["view"]["blockers"]
    assert state.registration() is None
    assert_no_activation(result)


def test_unreadable_observation_remains_reviewable_without_fabricated_file_hash():
    report = fixture()
    report["files"][0].update(
        status="UNSAFE_OR_UNREADABLE", observed_sha256=None, bytes=None
    )
    report.update(
        inspection_status="UNSAFE_OR_UNREADABLE",
        metadata_eligible=False,
        blockers=["UNSAFE_OR_UNREADABLE"],
    )
    reseal(report)
    state = model()
    state.ingest(report, operation_id="inspection", operator_id="operator-a")
    result = state.review("reviewer-b", operation_id="review")
    assert result["view"]["status"] == "REVIEW_HELD"
    assert result["view"]["inspection"]["helper_sha256"] is None
    assert result["inspection_report"]["files"][0]["observed_sha256"] is None
    assert state.registration() is None


def test_held_eligibility_cannot_be_upgraded_by_rehashing_client_fields():
    report = fixture("missing-helper")
    report.update(
        metadata_eligible=True,
        inspection_status="MATCHED_METADATA_CATALOG",
        blockers=[],
    )
    reseal(report)
    state = model()
    with pytest.raises(CameraHelperRegistrationError):
        state.ingest(report, operation_id="inspection", operator_id="operator-a")
    assert state.registration() is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", "forged.v1"),
        ("source_sha256", "b" * 64),
        ("catalog_id", "different-catalog"),
        ("catalog_sha256", "b" * 64),
        ("helper_sha256", "b" * 64),
        ("inspection_provenance", "WORKSPACE_FILE_INSPECTION"),
        ("mode", "physical"),
        ("metadata_eligible", 1),
        ("physical_authority", True),
        ("camera_activation_allowed", True),
        ("driver_qualified", True),
        ("trusted_release", True),
        ("historical_full_build_match", True),
        ("allowed_operations", ["inventory", "identity", "capture"]),
        ("inspection_status", "MATCHED_AND_PHYSICAL_READY"),
        ("unexpected_field", False),
    ],
)
def test_rehashed_forged_report_is_rejected_and_old_registration_cleared(key, value):
    state, _, _ = registered()
    report = fixture()
    report[key] = value
    reseal(report)
    with pytest.raises(CameraHelperRegistrationError) as error:
        state.ingest(report, operation_id="new-inspection", operator_id="operator-a")
    assert error.value.code == "INSPECTION_INVALID"
    assert state.registration() is None
    assert state.view()["status"] == "INVALIDATED"
    assert state.view()["inspection"] is None
    assert state.view()["review"] is None


def test_bad_digest_missing_field_and_changed_file_bytes_do_not_verify():
    for change in (
        lambda value: value.update(inspection_sha256="0" * 64),
        lambda value: value.pop("files"),
        lambda value: value["files"][0].update(observed_sha256="b" * 64),
        lambda value: value["files"][0].update(status="MISSING"),
    ):
        state = model()
        report = fixture()
        change(report)
        with pytest.raises(CameraHelperRegistrationError):
            state.ingest(report, operation_id="inspection", operator_id="operator-a")
        assert state.registration() is None
        assert state.view()["status"] == "INVALIDATED"


@pytest.mark.parametrize("reviewer", ["operator-a", "OPERATOR-A", "Operator-A"])
def test_different_case_does_not_supply_distinct_operator_label(reviewer):
    state, _, _ = registered()
    with pytest.raises(CameraHelperRegistrationError) as error:
        state.review(reviewer, operation_id="new-review")
    assert error.value.code == "REVIEWER_MUST_DIFFER"
    assert state.registration() is None
    assert state.view()["status"] == "INSPECTION_RETAINED"
    assert state.view()["review"] is None


@pytest.mark.parametrize(
    "reviewer",
    ["", " reviewer-b", "reviewer-b ", "a\nb", "a\x00b", "a" * 129, "\ud800"],
)
def test_malformed_reviewer_clears_prior_review(reviewer):
    state, _, _ = registered()
    with pytest.raises(CameraHelperRegistrationError):
        state.review(reviewer, operation_id="new-review")
    assert state.registration() is None
    assert state.view()["inspection"] is not None


def test_inspection_and_review_need_different_operation_ids():
    state, _, _ = inspected()
    with pytest.raises(CameraHelperRegistrationError) as error:
        state.review("reviewer-b", operation_id="inspect-operation")
    assert error.value.code == "OPERATION_CONFLICT"
    assert state.registration() is None


def test_review_or_preview_without_inspection_is_held():
    state = model()
    for operation in (
        state.preview,
        lambda: state.review("reviewer", operation_id="review"),
    ):
        with pytest.raises(CameraHelperRegistrationError) as error:
            operation()
        assert error.value.code == "INSPECTION_REQUIRED"
    assert state.registration() is None


def test_new_inspection_never_inherits_an_old_review():
    state, _, _ = registered()
    state.ingest(fixture(), operation_id="inspection-2", operator_id="operator-a")
    assert state.view()["status"] == "INSPECTION_RETAINED"
    assert state.view()["review"] is None
    assert state.registration() is None


def test_partial_and_full_invalidation_have_distinct_retention_semantics():
    state, original, _ = registered()
    state.invalidate_review("REVIEW_OPERATION_STARTED")
    assert state.view()["status"] == "INSPECTION_RETAINED"
    assert state.view()["invalidation_reason"] == "REVIEW_OPERATION_STARTED"
    assert state.export_snapshot()["inspection_report"] == original
    assert state.registration() is None
    state.invalidate("WORKSPACE_SOURCE_CHANGED")
    assert state.view()["status"] == "INVALIDATED"
    assert state.view()["inspection"] is None
    assert state.view()["review"] is None
    assert state.export_snapshot()["inspection_report"] is None


def test_staged_copy_can_be_discarded_without_publishing_review_or_invalidation():
    state, _, _ = inspected()
    before = state.export_snapshot()
    staged = state.staged_copy()
    assert staged._lock is not state._lock
    assert staged.export_snapshot() == before
    staged.review("reviewer-b", operation_id="review-operation")
    assert staged.registration() is not None
    assert state.export_snapshot() == before
    state.invalidate("LOG_FAILURE")
    assert staged.registration() is not None
    assert state.registration() is None


def test_inputs_outputs_and_artifact_properties_are_detached():
    state, original, result = registered()
    retained = state.export_snapshot()
    original["files"].clear()
    result["inspection_report"]["files"].clear()
    result["view"]["blockers"].clear()
    artifact = state.registration()
    assert artifact is not None
    artifact.payload["physical_authority"] = True
    artifact.inspection["files"].clear()
    artifact.to_dict()["payload"].clear()
    state.view()["inspection"].clear()
    state.preview()["blockers"].clear()
    assert state.export_snapshot() == retained
    with pytest.raises(FrozenInstanceError):
        artifact._payload_json = b"{}"


def test_artifact_constructor_only_admits_immutable_bounded_canonical_json():
    for bad in (
        bytearray(b"{}"),
        b'{ "x":1}',
        b'{"x":1,"x":1}',
        b"[]",
        b"NaN",
        b"{",
        b" " * (module.MAX_REPORT_BYTES + 1),
    ):
        with pytest.raises(CameraHelperRegistrationError):
            ReviewedCameraHelperRegistration(bad, b"{}")
        with pytest.raises(CameraHelperRegistrationError):
            ReviewedCameraHelperRegistration(b"{}", bad)


def test_result_bound_failure_rolls_back_authority_shaped_local_state(monkeypatch):
    state, _, _ = inspected()
    with monkeypatch.context() as patch:
        patch.setattr(module, "MAX_REPORT_BYTES", 1)
        with pytest.raises(CameraHelperRegistrationError):
            state.review("reviewer-b", operation_id="review-operation")
    assert state.registration() is None
    assert state.view()["status"] == "INSPECTION_RETAINED"
    assert state.view()["invalidation_reason"] == "HELPER_REVIEW_RESULT_NOT_RETAINED"


def test_no_file_inspection_provider_construction_or_dispatch_in_state_methods(
    monkeypatch,
):
    report = fixture()

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "State methods must not inspect files or dispatch providers"
        )

    with monkeypatch.context() as patch:
        for name in ("inspect_camera_helper", "create_metadata_provider"):
            patch.setattr(inspection_module, name, forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "read_bytes", forbidden)
        patch.setattr(Path, "stat", forbidden)
        state = model()
        assert state.view()["status"] == "NO_INSPECTION"
        assert state.registration() is None
        state.ingest(report, operation_id="inspection", operator_id="operator-a")
        state.preview()
        state.review("reviewer-b", operation_id="review")
        assert state.registration() is not None
        state.staged_copy().export_snapshot()
        state.invalidate_review("QUERY_STARTED")
        state.invalidate("SOURCE_CHANGED")


def test_repeated_exact_review_is_hash_stable_but_different_operation_is_bound():
    state, _, _ = registered()
    first = state.registration()
    assert first is not None
    repeated = state.review("reviewer-b", operation_id="review-operation")
    assert repeated["registration_artifact"] == first.to_dict()
    state.review("reviewer-b", operation_id="review-operation-2")
    assert state.registration().registration_sha256 != first.registration_sha256


def test_physical_mode_rejects_incapable_fixture_without_inspecting_a_file():
    state = WizardCameraHelperRegistration("physical", SESSION, SOURCE)
    with pytest.raises(CameraHelperRegistrationError) as error:
        state.ingest(fixture(), operation_id="inspection", operator_id="operator-a")
    assert error.value.code == "INSPECTION_INVALID"
    assert state.registration() is None


@pytest.mark.parametrize(
    "mode,session,source",
    [
        ("auto", SESSION, SOURCE),
        (True, SESSION, SOURCE),
        ("rehearsal", "../escape", SOURCE),
        ("rehearsal", "", SOURCE),
        ("rehearsal", SESSION, "A" * 64),
        ("rehearsal", SESSION, "a" * 63),
    ],
)
def test_constructor_rejects_bad_binding_inputs(mode, session, source):
    with pytest.raises(CameraHelperRegistrationError):
        WizardCameraHelperRegistration(mode, session, source)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {"value": float("nan")},
        {"value": object()},
        {"value": "x" * 4097},
        {"value": [None] * 129},
    ],
)
def test_non_json_or_unbounded_inspection_never_publishes(bad):
    state = model()
    with pytest.raises(CameraHelperRegistrationError):
        state.ingest(bad, operation_id="inspection", operator_id="operator-a")
    assert state.registration() is None
    assert state.view()["status"] == "INVALIDATED"


def test_verifier_contract_failure_has_fixed_public_error(monkeypatch):
    def failed(*args, **kwargs):
        raise ValueError("C:/private-path with secret provider details")

    patch_report = fixture()
    monkeypatch.setattr(module, "verify_camera_helper_inspection", failed)
    state = model()
    with pytest.raises(CameraHelperRegistrationError) as error:
        state.ingest(patch_report, operation_id="inspection", operator_id="operator-a")
    assert error.value.code == "INSPECTION_INVALID"
    assert "private-path" not in str(error.value)
    assert isinstance(error.value.__cause__, ValueError)


@pytest.mark.parametrize("failure", [KeyboardInterrupt, SystemExit])
def test_baseexception_is_not_swallowed_and_previous_state_is_invalidated(
    monkeypatch, failure
):
    state, _, _ = registered()

    def failed(*args, **kwargs):
        raise failure()

    patch_report = fixture()
    monkeypatch.setattr(module, "verify_camera_helper_inspection", failed)
    with pytest.raises(failure):
        state.ingest(
            patch_report, operation_id="inspection-2", operator_id="operator-a"
        )
    assert state.registration() is None
    assert state.view()["status"] == "INVALIDATED"
