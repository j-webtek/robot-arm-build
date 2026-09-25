"""Original-shaped metadata fixtures; no device/provider or process runs."""

from copy import deepcopy

import pytest

from test_physical_camera_selection import physical_enrollment
from test_windows_camera_driver_metadata import driver_fixture
from test_windows_camera_identity import unavailable
from test_wizard_native_camera_enrollment import SOURCE, SESSION
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.native_camera_activation_expectation import (
    CameraActivationExpectation,
)
from rocell.application.camera_activation_expectation import expectation_from_enrollment


def enrollment(*, missing=None):
    original = physical_enrollment().export_snapshot()
    packet = deepcopy(original["identity_packet"])
    previous = packet["receipt"]
    fresh = driver_fixture()
    fresh["requested_endpoint"] = previous["requested_endpoint"]
    fresh["mapping"]["interface_path"] = previous["mapping"]["interface_path"]
    for field in ("instance_id", "container_id"):
        fresh["device"][field] = previous["device"][field]
    if missing is not None:
        fresh["driver"][missing] = unavailable()
    packet["receipt"] = fresh
    model = WizardNativeCameraEnrollment(
        "physical",
        SESSION,
        SOURCE,
        {key: packet[key] for key in ("provenance", "helper_sha256")},
    )
    model.ingest_inventory(
        original["inventory_packet"],
        operation_id="inventory-driver-test",
        generic_review=original["generic_review"],
    )
    choice = model.choices()[0]["value"]
    model.retain_identity(choice, packet, operation_id="identity-driver-test")
    model.review(choice, "driver-test-reviewer")
    return model


def build(model):
    return expectation_from_enrollment(
        model, source_sha256=SOURCE, launch_session_id=SESSION
    )


def test_actual_selection_and_metadata_readers_preserve_originals():
    model = enrollment()
    before = model.export_snapshot()
    value = build(model)
    data = value.to_dict()
    assert model.export_snapshot() == before
    assert (
        data["original_identity_sha256"]
        == before["view"]["identity"]["identity_sha256"]
    )
    assert data["driver_provider"] == "MODELED provider é 😀"
    assert data["driver_inf"] == "modeled.inf"
    assert value.sha256 == digest(value.payload)
    assert value.payload == canonical(data) and value.payload.isascii()
    assert not hasattr(value, "physical_authority")


def test_legacy_metadata_is_not_upgraded_to_driver_observations():
    with pytest.raises(ValueError, match="ORIGINAL_DRIVER_METADATA_REQUIRED"):
        build(physical_enrollment())


@pytest.mark.parametrize("field", ["provider", "service", "version", "inf_path"])
def test_unavailable_driver_property_has_no_parent_fallback(field):
    with pytest.raises(ValueError, match="PROPERTY_UNAVAILABLE"):
        build(enrollment(missing=field))


@pytest.mark.parametrize(
    "source,launch", [("c" * 64, SESSION), (SOURCE, "another-launch")]
)
def test_stale_context_is_not_relabelled(source, launch):
    with pytest.raises(ValueError):
        expectation_from_enrollment(
            enrollment(), source_sha256=source, launch_session_id=launch
        )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("schema", "legacy"),
        ("original_identity_sha256", "0" * 64),
        ("endpoint", ""),
        ("instance_id", "x" * 1025),
        ("driver_provider", "😀" * 513),
        ("driver_service", "bad\n"),
        ("driver_inf", "\ud800"),
        ("container_id", "00000000-0000-0000-0000-000000000000"),
        ("location_paths_json", '{"path_01":"wrong"}'),
        ("location_paths_json", '{"path_00":"same","path_01":"same"}'),
    ],
)
def test_closed_native_compatible_expectation_rejects_invalid_values(field, bad):
    data = build(enrollment()).to_dict()
    data[field] = bad
    with pytest.raises(ValueError):
        CameraActivationExpectation(canonical(data))


def test_noncanonical_and_extra_fields_are_not_admitted():
    value = build(enrollment())
    with pytest.raises(ValueError):
        CameraActivationExpectation(value.payload + b" ")
    data = value.to_dict()
    data["allow_hardware"] = True
    with pytest.raises(ValueError):
        CameraActivationExpectation(canonical(data))
