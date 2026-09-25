"""Versioned camera metadata using incapable packets/runners, never native APIs."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from rocell.providers.windows.camera_worker_client import (
    CameraCandidate,
    CameraWorkerError,
    IDENTITY_PROTOCOL_SCHEMA,
    LEGACY_IDENTITY_PROTOCOL_SCHEMA,
)
from test_windows_camera_identity import (
    ENDPOINT,
    FixtureRunner,
    client,
    fixture,
    observed,
    parse,
    unavailable,
)


def driver_fixture():
    """Explicitly modeled observations, not received-camera or driver approval."""
    packet = fixture()
    packet.update(
        schema=IDENTITY_PROTOCOL_SCHEMA,
        driver={
            "devnode": 1,
            "provider": observed("MODELED provider é 😀"),
            "service": observed("MODELED service"),
            "version": observed("1.2.3.4"),
            "inf_path": observed("modeled.inf"),
        },
        api_calls=13,
        observed_property_bytes=512,
    )
    return packet


def test_v2_independent_typed_driver_fields_do_not_create_serial_usb_or_authority():
    result = parse(driver_fixture())
    assert result.protocol_schema == IDENTITY_PROTOCOL_SCHEMA
    assert result.exact_endpoint_observed
    assert result.driver.devnode == result.device.devnode == result.devnode.value
    assert result.driver.provider.value == "MODELED provider é 😀"
    assert result.driver.service.value == "MODELED service"
    assert result.driver.version.value == "1.2.3.4"
    assert result.driver.inf_path.value == "modeled.inf"
    assert not result.physical_authority
    assert not hasattr(result.driver, "qualified")
    assert not hasattr(result, "serial_number") and not hasattr(result, "usb_speed")
    with pytest.raises(FrozenInstanceError):
        result.driver.version = observed("replaced")


def test_legacy_v1_remains_exact_and_driver_not_retained():
    data = fixture()
    original = json.dumps(data, sort_keys=True).encode()
    digest = hashlib.sha256(original).hexdigest()
    result = parse(data)
    assert result.driver is None
    assert result.protocol_schema == LEGACY_IDENTITY_PROTOCOL_SCHEMA
    assert json.dumps(data, sort_keys=True).encode() == original
    assert (
        hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest() == digest
    )
    data["driver"] = None
    with pytest.raises(CameraWorkerError):
        parse(data)


@pytest.mark.parametrize("field", ["provider", "service", "version", "inf_path"])
def test_missing_field_retains_native_error_without_parent_fallback(field):
    data = driver_fixture()
    data["driver"][field] = unavailable()
    result = parse(data)
    assert getattr(result.driver, field).value is None
    assert getattr(result.driver, field).error.native_code == 13
    assert result.parents[0].devnode == 2
    for other in {"provider", "service", "version", "inf_path"} - {field}:
        assert getattr(result.driver, other).observed


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("driver"),
        lambda d: d.update(driver=None),
        lambda d: d.update(schema="rocell.windows_camera_identity.v3"),
        lambda d: d["driver"].update(devnode=2),
        lambda d: d["driver"].update(devnode=True),
        lambda d: d["driver"].update(serial_number="guessed"),
        lambda d: d["driver"].pop("provider"),
        lambda d: d["parents"][0].update(driver=d["driver"]),
        lambda d: d["driver"]["provider"].update(value=""),
        lambda d: d["driver"]["provider"].update(value="x\0suffix"),
        lambda d: d["driver"]["provider"].update(value="x\nline"),
        lambda d: d["driver"]["provider"].update(value="x" * 1025),
        lambda d: d["driver"]["provider"].update(value="😀" * 513),
        lambda d: d["driver"]["provider"].update(value=[]),
        lambda d: d["driver"]["provider"].update(availability="UNAVAILABLE"),
        lambda d: d["driver"].update(provider=unavailable("NOT_REQUESTED", "NONE", 0)),
        lambda d: d.update(api_calls=7),
        lambda d: d.update(observed_property_bytes=128),
        lambda d: d["mapping"]["interface_path"].update(value="wrong-endpoint"),
        lambda d: d["mapping"].update(
            cleanup_errors=[
                {"reason": "API_FAILURE", "domain": "WIN32", "native_code": 5}
            ]
        ),
    ],
)
def test_v2_closed_binding_types_progression_and_accounting(mutate):
    data = driver_fixture()
    mutate(data)
    with pytest.raises(CameraWorkerError):
        parse(data)


@pytest.mark.parametrize(
    "reason", ["CANCELLED", "DEADLINE", "CLOCK_CHANGED", "CALL_LIMIT"]
)
def test_partial_driver_query_preserves_completed_observations(reason):
    data = driver_fixture()
    data.update(
        parents=[],
        observed_root=unavailable("NOT_REQUESTED", "NONE", 0),
        chain_end=reason,
        chain_error={"reason": reason, "domain": "CONTRACT", "native_code": 0},
        api_calls=6,
    )
    data["driver"].update(
        version=unavailable("NOT_REQUESTED", "NONE", 0),
        inf_path=unavailable("NOT_REQUESTED", "NONE", 0),
    )
    result = parse(data)
    assert result.driver.provider.observed and result.driver.service.observed
    assert not result.driver.version.observed
    assert result.chain_end == reason and result.api_calls == 6


def test_unmapped_v2_has_no_driver_and_no_fabricated_observations():
    data = driver_fixture()
    data.update(
        device=None,
        driver=None,
        parents=[],
        observed_root=unavailable("NOT_REQUESTED", "NONE", 0),
        chain_end="NOT_REQUESTED",
        api_calls=1,
        observed_property_bytes=0,
    )
    data["mapping"] = {
        "devnode": unavailable("API_FAILURE", "WIN32", 433),
        "interface_path": unavailable("NOT_REQUESTED", "NONE", 0),
        "cleanup_errors": [],
    }
    result = parse(data)
    assert result.driver is None and not result.exact_endpoint_observed


@pytest.mark.parametrize("packet", [fixture, driver_fixture])
def test_actual_client_and_wire_sink_preserve_both_versions(tmp_path, packet):
    value = packet()
    original = deepcopy(value)
    runner = FixtureRunner(value)
    sink = []
    result = client(tmp_path, runner).resolve_identity_metadata(
        CameraCandidate(ENDPOINT, "MODELED camera"),
        wire_receipt_sink=sink.append,
    )
    assert len(runner.calls) == len(sink) == 1
    assert json.loads(sink[0]) == original == value
    assert result.protocol_schema == value["schema"]
    assert (result.driver is None) == (
        value["schema"] == LEGACY_IDENTITY_PROTOCOL_SCHEMA
    )


@pytest.mark.parametrize("missing_provider", [False, True])
def test_v2_actual_enrollment_selection_join_preserves_packet_not_qualification(
    monkeypatch, missing_provider
):
    """Modeled physical-shaped packets through the real pure enrollment join."""
    from pathlib import Path
    import subprocess

    from rocell.application.physical_camera_selection import selection_from_enrollment
    from rocell.application.wizard_native_camera_enrollment import (
        WizardNativeCameraEnrollment,
    )
    from rocell.application.wizard_native_camera_metadata import (
        RehearsalNativeCameraMetadataProvider,
    )
    from test_wizard_native_camera_enrollment import SOURCE, SESSION, generic_review

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "pure enrollment must not perform file/process/device work"
        )

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    fixture_provider = RehearsalNativeCameraMetadataProvider("nominal")
    inventory = fixture_provider.inventory()
    candidate = CameraCandidate(**inventory["receipt"]["devices"][0])
    identity = fixture_provider.identity(candidate)
    identity["receipt"].update(
        schema=IDENTITY_PROTOCOL_SCHEMA,
        driver=driver_fixture()["driver"],
        api_calls=identity["receipt"]["api_calls"] + 4,
        observed_property_bytes=identity["receipt"]["observed_property_bytes"] + 512,
    )
    identity["receipt"]["driver"]["devnode"] = identity["receipt"]["device"]["devnode"]
    if missing_provider:
        identity["receipt"]["driver"]["provider"] = unavailable()
    descriptor = {"provenance": "WINDOWS_NATIVE_METADATA", "helper_sha256": "b" * 64}
    for packet in (inventory, identity):
        packet.update(descriptor)
    model = WizardNativeCameraEnrollment("physical", SESSION, SOURCE, descriptor)
    model.ingest_inventory(
        inventory,
        operation_id="modeled-inventory",
        generic_review=generic_review(mode="physical"),
    )
    choice = model.choices()[0]["value"]
    model.retain_identity(choice, identity, operation_id="modeled-driver-identity")
    model.review(choice, "modeled-independent-reviewer")
    original = deepcopy(identity)
    selection = selection_from_enrollment(
        model, source_sha256=SOURCE, launch_session_id=SESSION
    )
    packet_hash = hashlib.sha256(
        json.dumps(
            identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    assert selection.identity_document["native_identity_sha256"] == packet_hash
    assert identity == original
    assert selection.identity_document["qualified"] is False
    assert selection.identity_document["physical_authority"] is False
    assert (
        "CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED"
        in selection.identity_document["metadata_review"]["blockers"]
    )
