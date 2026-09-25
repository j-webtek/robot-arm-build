"""Actual incapable packet producers; no OS inventory or native endpoint calls."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from rocell.application.physical_connection_contracts import canonical_sha256
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory
from rocell.application.wizard_native_camera_metadata import (
    RehearsalNativeCameraMetadataProvider,
)
from rocell.application.wizard_native_camera_enrollment import (
    NativeCameraEnrollmentError,
    WizardNativeCameraEnrollment,
)
import rocell.application.wizard_native_camera_enrollment as module


SOURCE = "a" * 64
SESSION = "wizard-native-fixture"


def generic_review(
    scenario="nominal", *, mode="rehearsal", source=SOURCE, session=SESSION, mutate=None
):
    report = rehearsal_device_inventory(scenario)
    if mode == "physical":
        report["serial_inventory"]["source"] = "PYSERIAL_LIST_PORTS"
        for item in report["serial_inventory"]["candidates"]:
            item["source"] = "PYSERIAL_LIST_PORTS"
    if mutate is not None:
        mutate(report)
    report["report_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    selection = WizardDeviceSelection(mode, session, source)
    selection.ingest(report, operation_id="generic-operation")
    selection.review(
        selection.choices("CAMERA")[0]["value"], "CAMERA", "generic-reviewer"
    )
    return selection.reviewed_candidate("CAMERA")


def setup(scenario="nominal", *, generic=None):
    provider = RehearsalNativeCameraMetadataProvider(scenario)
    model = WizardNativeCameraEnrollment(
        "rehearsal", SESSION, SOURCE, provider.descriptor()
    )
    model.ingest_inventory(
        provider.inventory(),
        operation_id="inventory-operation",
        generic_review=generic or generic_review(),
    )
    token = model.choices()[0]["value"]
    return model, provider, token


def identified(scenario="nominal", *, generic=None):
    model, provider, token = setup(scenario, generic=generic)
    model.retain_identity(
        token,
        provider.identity(model.candidate(token)),
        operation_id="identity-operation",
    )
    return model, provider, token


def assert_no_authority(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {
                "physical_authority",
                "connected",
                "qualified",
                "persistent_binding",
            }:
                assert child is False
            assert_no_authority(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_authority(child)


def test_actual_nominal_join_issues_only_prospective_endpoint_metadata_binding():
    model, _, token = identified()
    assert model.binding() is None  # Identity observation is not review.
    full = model.review(token, "endpoint-reviewer")
    view = full["view"]
    assert view["status"] == "ENDPOINT_METADATA_REVIEWED"
    assert view["identity"]["blockers"] == []
    assert all(
        view["identity"][key] is True
        for key in (
            "exact_endpoint_observed",
            "generic_device_match",
            "container_match",
        )
    )
    assert "CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED" in view["blockers"]
    assert "CAMERA_USB3_TOPOLOGY_NOT_OBSERVED" in view["blockers"]
    assert "PHYSICAL_STAGE_GATES_REMAIN_HELD" in view["blockers"]
    artifact = full["binding_artifact"]
    assert artifact["binding_sha256"] == canonical_sha256(artifact["payload"])
    binding = model.binding()
    assert binding is not None
    assert binding.binding_sha256 == view["review"]["binding_sha256"]
    assert (
        binding.endpoint_sha256
        == hashlib.sha256(binding.symbolic_link.encode()).hexdigest()
    )
    payload = artifact["payload"]
    assert payload["generic_review_sha256"] == canonical_sha256(full["generic_review"])
    assert payload["inventory_sha256"] == canonical_sha256(full["inventory_packet"])
    assert payload["identity_sha256"] == canonical_sha256(full["identity_packet"])
    assert payload["source_sha256"] == SOURCE and payload["session_id"] == SESSION
    assert payload["observed_container_id"] == "11111111-2222-3333-4444-555555555555"
    assert model.review(token, "endpoint-reviewer") == full
    assert_no_authority(full)
    assert "symbolic_link" not in json.dumps(view)
    assert "incapable://" not in json.dumps(view)


@pytest.mark.parametrize("scenario", ["missing-mapping", "wrong-device"])
def test_actual_unavailable_or_wrong_mapping_can_be_acknowledged_but_never_bound(
    scenario,
):
    model, _, token = identified(scenario)
    full = model.review(token, "reviewer")
    assert full["view"]["status"] == "REVIEW_HELD"
    assert full["view"]["identity"]["blockers"]
    assert full["view"]["review"]["binding_sha256"] is None
    assert full["binding_artifact"] is None and model.binding() is None
    assert full["identity_packet"]["receipt"]["status"] == "METADATA_ONLY"
    assert_no_authority(full)


@pytest.mark.parametrize("scenario", ["missing-identity", "duplicate-identity"])
def test_generic_missing_or_duplicate_unit_identity_remains_held(scenario):
    model, _, token = identified(generic=generic_review(scenario))
    result = model.review(token, "reviewer")
    assert result["view"]["identity"]["exact_endpoint_observed"] is True
    assert result["view"]["identity"]["blockers"]
    assert model.binding() is None
    assert result["view"]["status"] == "REVIEW_HELD"


def test_duplicate_friendly_names_are_not_identity_and_second_endpoint_mismatches():
    model, provider, first = setup("duplicate-name")
    candidates = model.view()["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["friendly_name"] == candidates[1]["friendly_name"]
    assert candidates[0]["endpoint_sha256"] != candidates[1]["endpoint_sha256"]
    model.retain_identity(
        first, provider.identity(model.candidate(first)), operation_id="identity-first"
    )
    model.review(first, "reviewer")
    assert model.binding() is not None
    second = candidates[1]["choice_id"]
    model.retain_identity(
        second,
        provider.identity(model.candidate(second)),
        operation_id="identity-second",
    )
    assert model.binding() is None
    model.review(second, "reviewer")
    assert model.view()["status"] == "REVIEW_HELD"


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "wrong"),
        (("kind",), "identity"),
        (("provenance",), "WINDOWS_NATIVE_METADATA"),
        (("helper_sha256",), "b" * 64),
        (("receipt", "operation"), "capture"),
        (("receipt", "counts", "source_opened"), 1),
        (("receipt", "selected_endpoint"), "invented"),
        (("receipt", "extra"), True),
    ],
)
def test_forged_inventory_packet_never_issues_choices(path, value):
    model, provider, _ = setup()
    packet = provider.inventory()
    target = packet
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(NativeCameraEnrollmentError):
        model.ingest_inventory(
            packet, operation_id="replacement", generic_review=generic_review()
        )
    assert model.choices() == [] and model.binding() is None
    assert model.view()["status"] == "INVALIDATED"


@pytest.mark.parametrize(
    "path,value",
    [
        (("helper_sha256",), "b" * 64),
        (("kind",), "inventory"),
        (("receipt", "requested_endpoint"), "incapable://different"),
        (("receipt", "physical_authority"), 0),
        (("receipt", "camera_activation_count"), 1),
        (("receipt", "limits", "duration_ms"), 5001),
        (("receipt", "limits", "max_parent_nodes"), 9),
        (("receipt", "extra"), True),
    ],
)
def test_forged_identity_packet_clears_old_review_but_preserves_inventory(path, value):
    model, provider, token = identified()
    model.review(token, "reviewer")
    packet = provider.identity(model.candidate(token))
    target = packet
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(NativeCameraEnrollmentError) as caught:
        model.retain_identity(token, packet, operation_id="replacement")
    assert caught.value.code == "NATIVE_PACKET_INVALID"
    assert model.view()["identity"] is None and model.view()["review"] is None
    assert model.view()["status"] == "ENDPOINT_CHOICES_AVAILABLE"
    assert model.choices()[0]["value"] == token
    assert model.binding() is None


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "session",
        "mode",
        "candidate-hash",
        "reviewer",
        "flags",
        "unknown",
        "report-hash",
        "operation",
    ],
)
def test_generic_review_must_exactly_match_current_session_contract(change):
    generic = generic_review()
    if change in {"source", "session", "mode"}:
        field = {"source": "source_sha256", "session": "session_id", "mode": "mode"}[
            change
        ]
        generic["provenance"][field] = {
            "source": "b" * 64,
            "session": "another-session",
            "mode": "physical",
        }[change]
    elif change == "candidate-hash":
        generic["candidate"]["candidate_sha256"] = "b" * 64
    elif change == "reviewer":
        generic["review"]["reviewer_id"] = ""
    elif change == "flags":
        generic["persistent_binding"] = True
    elif change == "unknown":
        generic["extra"] = "field"
    elif change == "report-hash":
        generic["report_sha256"] = "b" * 64
    else:
        generic["review"]["operation_id"] = "another-operation"
    provider = RehearsalNativeCameraMetadataProvider()
    model = WizardNativeCameraEnrollment(
        "rehearsal", SESSION, SOURCE, provider.descriptor()
    )
    with pytest.raises(NativeCameraEnrollmentError):
        model.ingest_inventory(
            provider.inventory(), operation_id="op", generic_review=generic
        )
    assert model.choices() == []


@pytest.mark.parametrize(
    "container", [None, "not-a-guid", "{AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE}"]
)
def test_generic_container_missing_malformed_or_wrong_remains_held(container):
    def mutate(report):
        ids = report["camera_inventory"]["candidates"][0]["persistent_ids"]
        ids[:] = [value for value in ids if not value.startswith("windows-container:")]
        if container is not None:
            ids.append("windows-container:" + container)
        ids.sort()

    model, _, token = identified(generic=generic_review(mutate=mutate))
    model.review(token, "reviewer")
    assert model.view()["identity"]["container_match"] is False
    assert model.binding() is None


def test_guid_canonicalization_does_not_invent_instance_case_or_endpoint_equality():
    def mutate(report):
        candidate = report["camera_inventory"]["candidates"][0]
        candidate["os_instance_id"] = candidate["os_instance_id"].lower()

    model, _, token = identified(generic=generic_review(mutate=mutate))
    model.review(token, "reviewer")
    assert model.view()["identity"]["container_match"] is True
    assert model.view()["identity"]["generic_device_match"] is False
    assert model.binding() is None


def test_staged_copy_and_partial_invalidations_do_not_publish_or_corrupt_original():
    model, _, token = identified()
    before = model.export_snapshot()
    staged = model.staged_copy()
    assert staged._lock is not model._lock
    staged.review(token, "reviewer")
    assert staged.binding() is not None and model.binding() is None
    assert model.export_snapshot() == before
    staged.invalidate_review("REVIEW_DISPATCHED")
    assert staged.view()["status"] == "IDENTITY_RETAINED"
    assert staged.view()["invalidation_reason"] == "REVIEW_DISPATCHED"
    staged.invalidate_identity("IDENTITY_DISPATCHED")
    assert staged.view()["status"] == "ENDPOINT_CHOICES_AVAILABLE"
    assert staged.choices() == model.choices()
    staged.invalidate("GENERIC_REVIEW_CHANGED")
    view = staged.view()
    assert view["status"] == "INVALIDATED" and view["candidates"] == []
    for field in (
        "inventory_sha256",
        "inventory_operation_id",
        "generic_candidate_sha256",
        "generic_report_sha256",
        "generic_operation_id",
        "identity",
        "review",
    ):
        assert view[field] is None
    assert model.export_snapshot() == before


def test_all_returned_data_are_detached_and_binding_is_new_frozen_value():
    model, _, token = identified()
    first = model.review(token, "reviewer")
    saved = deepcopy(first)
    first["binding_artifact"]["payload"]["reviewer_id"] = "changed"
    first["generic_review"]["candidate"]["identity_blockers"].clear()
    first["identity_packet"]["receipt"]["device"]["instance_id"]["value"] = "changed"
    first["view"]["identity"]["blockers"].append("CHANGED")
    assert model.export_snapshot() == saved
    assert model.binding() is not model.binding()
    assert asdict(model.binding()) == asdict(model.binding())
    assert model.candidate(token) is not model.candidate(token)


@pytest.mark.parametrize("scope", ["inventory", "identity", "review"])
def test_failed_full_result_retention_rolls_back_successful_looking_state(
    monkeypatch, scope
):
    model, provider, token = identified()
    model.review(token, "reviewer")
    original = module.MAX_REPORT_BYTES
    monkeypatch.setattr(module, "MAX_REPORT_BYTES", 32)
    with pytest.raises(NativeCameraEnrollmentError):
        if scope == "inventory":
            model.ingest_inventory(
                provider.inventory(),
                operation_id="new",
                generic_review=generic_review(),
            )
        elif scope == "identity":
            model.retain_identity(
                token, provider.identity(model.candidate(token)), operation_id="new"
            )
        else:
            model.review(token, "new-reviewer")
    monkeypatch.setattr(module, "MAX_REPORT_BYTES", original)
    assert model.binding() is None and model.view()["review"] is None
    if scope == "inventory":
        assert model.choices() == []
    elif scope == "identity":
        assert model.view()["identity"] is None
    else:
        assert model.view()["identity"] is not None


def test_missing_provider_is_inert_and_never_discovers_a_helper():
    model = WizardNativeCameraEnrollment("physical", SESSION, SOURCE)
    assert model.view()["status"] == "PROVIDER_UNAVAILABLE"
    assert model.view()["provenance"]["helper_sha256"] is None
    assert model.choices() == [] and model.binding() is None
    assert "NATIVE_METADATA_PROVIDER_NOT_CONFIGURED" in model.view()["blockers"]
    assert_no_authority(model.export_snapshot())


def test_descriptor_is_copied_and_must_match_mode():
    provider = RehearsalNativeCameraMetadataProvider()
    descriptor = dict(provider.descriptor())
    model = WizardNativeCameraEnrollment(
        "rehearsal", SESSION, SOURCE, MappingProxyType(descriptor)
    )
    descriptor["helper_sha256"] = "b" * 64
    assert (
        model.view()["provenance"]["helper_sha256"]
        == provider.descriptor()["helper_sha256"]
    )
    for bad in (
        {"provenance": "WINDOWS_NATIVE_METADATA", "helper_sha256": SOURCE},
        {"provenance": "INCAPABLE_FIXTURE", "helper_sha256": "invalid"},
        {**descriptor, "extra": True},
    ):
        with pytest.raises(NativeCameraEnrollmentError):
            WizardNativeCameraEnrollment("rehearsal", SESSION, SOURCE, bad)


def test_constructor_view_review_accessor_and_all_enrollment_methods_are_io_inert(
    monkeypatch,
):
    from rocell.providers.windows import camera_worker_client as client
    from rocell.application import physical_device_inventory as inventory

    provider = RehearsalNativeCameraMetadataProvider()
    generic = generic_review()
    inventory_packet = provider.inventory()
    candidate = module.CameraCandidate(
        "incapable://camera-metadata/SYNTHETIC-CAMERA-A", "INCAPABLE SYNTHETIC CAMERA"
    )
    identity_packet = provider.identity(candidate)

    def forbidden(*args, **kwargs):
        pytest.fail("Enrollment attempted native/provider or filesystem work")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(inventory, "inventory_windows_pnp_cameras", forbidden)
    monkeypatch.setattr(client.subprocess, "run", forbidden)
    monkeypatch.setattr(provider, "inventory", forbidden)
    monkeypatch.setattr(provider, "identity", forbidden)
    model = WizardNativeCameraEnrollment(
        "rehearsal", SESSION, SOURCE, provider.descriptor()
    )
    assert model.view()["status"] == "NO_INVENTORY"
    model.ingest_inventory(
        inventory_packet, operation_id="inventory", generic_review=generic
    )
    token = model.choices()[0]["value"]
    model.preview(token)
    model.retain_identity(token, identity_packet, operation_id="identity")
    model.review(token, "reviewer")
    assert model.staged_copy().export_snapshot() == model.export_snapshot()
    model.invalidate("STOPPED")


def test_changed_review_provenance_changes_digest_without_rerunning_identity():
    model, _, token = identified()
    first = model.review(token, "one")["binding_artifact"]["binding_sha256"]
    second = model.review(token, "two")["binding_artifact"]["binding_sha256"]
    assert first != second


def test_wrong_choice_cannot_reuse_identity_and_new_inventory_retires_tokens():
    model, provider, token = identified("duplicate-name")
    second = model.choices()[1]["value"]
    with pytest.raises(NativeCameraEnrollmentError):
        model.review(second, "reviewer")
    assert model.binding() is None
    model.ingest_inventory(
        provider.inventory(), operation_id="new", generic_review=generic_review()
    )
    with pytest.raises(NativeCameraEnrollmentError):
        model.candidate(token)
    for raw in (
        "0",
        "COM42",
        "incapable://camera-metadata/SYNTHETIC-CAMERA-A",
        [],
        None,
    ):
        with pytest.raises(NativeCameraEnrollmentError):
            model.candidate(raw)
