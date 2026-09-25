"""Injected metadata + actual incapable arm worker, never native enumeration."""

from dataclasses import replace
import ctypes
import json
from threading import Event

import pytest

from rocell.application import arm_controller_resolution as resolution
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.physical_device_inventory import (
    DeviceInventoryBatch,
    InventoryDeviceClass,
    InventorySource,
    RawSerialPortObservation,
    inventory_serial_ports_from_provider,
)
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackOutcome,
    ArmFeedbackWorker,
)
from rocell.providers.windows.arm_nonpurging_adapter import NonPurgingArmFeedbackBackend
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32SerialApi,
    NATIVE_HOLD,
)
from test_arm_feedback_worker import Clock, _request


PATH = r"\\?\usb#vid_ffff&pid_0002#SYNTHETIC-NOT-PHYSICAL#{86e0d1e0-8089-11d0-9ce4-08003e301f73}"


@pytest.fixture(autouse=True)
def forbid_hardware(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No native DLL, OS enumeration or serial endpoint allowed")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    from rocell.application import physical_device_inventory

    monkeypatch.setattr(
        physical_device_inventory, "inventory_serial_ports_with_pyserial", forbidden
    )


def request(clock=None, *, origin=EvidenceOrigin.SYNTHETIC_REHEARSAL):
    clock = Clock() if clock is None else clock
    original = _request(clock, origin=origin)
    identity = replace(original.controller.identity, persistent_port_path=PATH)
    return replace(
        original,
        controller=replace(original.controller, identity=identity),
        feedback=replace(
            original.feedback, arm_identity_sha256=identity.identity_sha256
        ),
    )


def batch(*, rows=None):
    if rows is None:
        identity = request().controller.identity
        rows = [
            RawSerialPortObservation(
                port_name=identity.port_name,
                hwid="USB VID:PID=ffff:0002 SER=" + identity.unit_serial,
                vid=identity.vid,
                pid=identity.pid,
                serial_number=identity.unit_serial,
                interface="GENERIC_INTERFACE_LABEL_NOT_DRIVER_SERVICE",
            )
        ]

    class Provider:
        def enumerate_serial_ports(self):
            return rows

    return inventory_serial_ports_from_provider(Provider())


def native():
    identity = request().controller.identity
    return resolution.ControllerNativeMetadata(
        PATH,
        identity.persistent_instance_id,
        identity.port_name,
        identity.vid,
        identity.pid,
        identity.driver.provider,
        identity.driver.service,
        identity.driver.version,
        identity.driver.package_or_inf_path,
    )


def snapshot(*, generic=None, observations=None, start=10, finish=11, blockers=()):
    return resolution.ControllerMetadataSnapshot(
        batch() if generic is None else generic,
        (native(),) if observations is None else observations,
        EvidenceOrigin.SYNTHETIC_REHEARSAL,
        "INJECTED_CM_METADATA",
        start,
        finish,
        blockers,
    )


def resolve(value=None):
    return resolution.resolve_controller_metadata(
        request().controller, snapshot() if value is None else value
    )


def test_actual_existing_inventory_matches_only_separate_native_fields():
    report = resolve()
    assert report.identity == request().controller.identity
    doc = report.to_dict()
    assert doc["status"] == "MATCHED_METADATA_ONLY"
    assert (
        doc["generic_metadata"]["driver_service"]
        == "GENERIC_INTERFACE_LABEL_NOT_DRIVER_SERVICE"
    )
    assert doc["native_metadata"]["driver_service"] == "synthetic"
    assert doc["generic_metadata"]["manufacturer"] is None
    assert doc["generic_metadata"]["product"] is None
    assert doc["unit_serial_origin"] == "GENERIC_SERIAL_INVENTORY_NOT_USB_DESCRIPTOR"
    assert (
        doc["physical_authority"] is doc["qualified"] is doc["arm_connected"] is False
    )
    assert doc["blockers"] == [] and len(doc["limitations"]) == 4
    assert len(report.payload) < resolution.MAX_RESOLUTION_BYTES
    safe = json.dumps(report.safe_summary())
    assert (
        PATH not in safe and "COM404" not in safe and "synthetic-driver.inf" not in safe
    )
    changed = report.to_dict()
    changed["qualified"] = True
    assert report.to_dict()["qualified"] is False


@pytest.mark.parametrize(
    "field",
    [
        "persistent_instance_id",
        "port_name",
        "vid",
        "pid",
        "driver_provider",
        "driver_service",
        "driver_version",
        "driver_inf",
    ],
)
def test_missing_native_fields_are_not_filled_from_reviewed_identity(field):
    value = snapshot(observations=(replace(native(), **{field: None}),))
    report = resolve(value)
    assert report.identity is None and report.to_dict()["status"] == "HELD"
    assert report.to_dict()["native_metadata"][field] is None
    assert "REQUIRED_NATIVE_PROPERTY_UNOBSERVED" in report.to_dict()["blockers"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("persistent_instance_id", "USB\\VID_FFFF&PID_0002\\OTHER"),
        ("persistent_port_path", PATH + "-other"),
        ("port_name", "COM405"),
        ("vid", "1234"),
        ("pid", "5678"),
        ("driver_provider", "OTHER"),
        ("driver_service", "other"),
        ("driver_version", "2.0"),
        ("driver_inf", "other.inf"),
    ],
)
def test_exact_mapping_or_driver_drift_cannot_return_reviewed_object(field, value):
    report = resolve(snapshot(observations=(replace(native(), **{field: value}),)))
    assert report.identity is None and report.to_dict()["status"] == "HELD"


@pytest.mark.parametrize(
    "extra",
    [
        native(),
        replace(native(), persistent_port_path=PATH + "-alias"),
        replace(
            native(),
            persistent_instance_id="USB\\OTHER",
            persistent_port_path=PATH + "-other",
        ),
    ],
)
def test_duplicate_persistent_identity_or_com_mapping_is_not_selected_by_order(extra):
    for rows in ((native(), extra), (extra, native())):
        report = resolve(snapshot(observations=rows))
        assert report.identity is None
        assert any("AMBIGUOUS" in code for code in report.to_dict()["blockers"])


@pytest.mark.parametrize("same_unit", [False, True])
def test_duplicate_generic_usb_unit_or_com_mapping_is_held(same_unit):
    first = batch().candidates[0]
    other = (
        replace(first, ephemeral_locator="COM405")
        if same_unit
        else replace(first, unit_serial="OTHER")
    )
    generic = replace(
        batch(), candidates=tuple(sorted((first, other), key=lambda v: v.sort_key))
    )
    assert resolve(snapshot(generic=generic)).identity is None


def test_empty_incomplete_and_blocked_collections_cannot_resolve():
    values = [
        snapshot(observations=()),
        snapshot(generic=batch(rows=[])),
        snapshot(blockers=("NATIVE_INTERFACE_LIST_CHANGED_DURING_ACQUISITION",)),
        snapshot(
            generic=replace(
                batch(),
                collection_complete=False,
                collection_blockers=("ENUMERATION_FAILED",),
            )
        ),
        snapshot(
            observations=(
                replace(native(), blockers=("NATIVE_UNOBSERVED_DRIVER_INF",)),
            )
        ),
    ]
    assert all(resolve(value).identity is None for value in values)


def test_no_usb_serial_or_conflicting_hwid_is_held_not_inferred_from_native_path():
    generic = batch(
        rows=[RawSerialPortObservation(port_name="COM404", vid="ffff", pid="0002")]
    )
    assert resolve(snapshot(generic=generic)).identity is None
    generic = batch(
        rows=[
            RawSerialPortObservation(
                port_name="COM404",
                vid="ffff",
                pid="0002",
                serial_number="SYNTHETIC-NOT-PHYSICAL",
                hwid="USB VID:PID=ffff:0002 SER=CONFLICT",
            )
        ]
    )
    assert (
        "GENERIC_IDENTITY_BLOCKED"
        in resolve(snapshot(generic=generic)).to_dict()["blockers"]
    )


@pytest.mark.parametrize("value", [True, 1, "", " x", "x\n", "é" * 257, "\ud800"])
def test_native_text_is_strict_and_bounded(value):
    with pytest.raises((resolution.ControllerResolutionError, UnicodeError)):
        replace(native(), driver_provider=value)


@pytest.mark.parametrize(
    "value", ["COM1", "12", "/dev/ttyUSB0", "usb-unit:ffff:0002:SERIAL"]
)
def test_generic_labels_are_not_native_interface_paths(value):
    with pytest.raises(resolution.ControllerResolutionError):
        replace(native(), persistent_port_path=value)


def test_snapshot_bounds_and_origins_are_exact():
    for kwargs in (
        {"observations": tuple(native() for _ in range(129))},
        {"start": True},
        {"start": 15, "finish": 14},
        {"blockers": ("BAD",) * 33},
    ):
        with pytest.raises(resolution.ControllerResolutionError):
            snapshot(**kwargs)
    with pytest.raises(resolution.ControllerResolutionError):
        replace(snapshot(), native_source="WINDOWS_CM_METADATA")
    report = resolution.resolve_controller_metadata(
        request(origin=EvidenceOrigin.PHYSICAL_OBSERVATION).controller, snapshot()
    )
    assert report.identity is None
    assert "CONTROLLER_METADATA_PROVENANCE_MISMATCH" in report.to_dict()["blockers"]


def test_even_mutated_frozen_inputs_are_rechecked():
    value = snapshot()
    object.__setattr__(value.native_observations[0], "vid", True)
    with pytest.raises(resolution.ControllerResolutionError):
        resolve(value)
    value = snapshot()
    object.__setattr__(
        value.serial_inventory.candidates[0], "driver_service", " untrimmed"
    )
    with pytest.raises(resolution.ControllerResolutionError):
        resolve(value)


def callback(*, clock=None, cancel=None, acquire=None):
    clock = Clock() if clock is None else clock
    cancel = Event() if cancel is None else cancel
    calls = []

    def provider():
        calls.append("snapshot")
        return snapshot(start=clock(), finish=clock()) if acquire is None else acquire()

    resolver = resolution.ExplicitArmControllerResolver(
        request(clock).controller,
        provider,
        deadline_ns=clock.value + 10_000_000_000,
        cancellation=cancel,
        monotonic_ns=clock,
    )
    return resolver, clock, cancel, calls


def test_callback_constructor_status_are_inert_and_two_checks_never_reuse_snapshot():
    resolver, clock, _, calls = callback()
    start = clock.value
    assert resolver.status()["latest"] is None
    assert clock.value == start and calls == []
    expected = request(clock).controller.identity
    for _ in range(2):
        observed = resolver(expected)
        assert observed == expected and observed is not expected
    assert calls == ["snapshot", "snapshot"]
    assert resolver.status()["latest"]["physical_authority"] is False
    with pytest.raises(resolution.ControllerResolutionError) as error:
        resolver(expected)
    assert error.value.code == "CONTROLLER_RESOLUTION_CALL_LIMIT" and len(calls) == 2


def test_wrong_expected_identity_cancel_and_deadline_refuse_before_acquisition():
    resolver, clock, cancel, calls = callback()
    with pytest.raises(resolution.ControllerResolutionError):
        resolver(replace(request(clock).controller.identity, port_name="COM405"))
    assert calls == []
    cancel.set()
    with pytest.raises(resolution.ControllerResolutionError):
        resolver(request(clock).controller.identity)
    assert calls == []
    resolver, clock, _, calls = callback()
    clock.value += 11_000_000_000
    with pytest.raises(resolution.ControllerResolutionError):
        resolver(request(clock).controller.identity)
    assert calls == []


def test_cancel_during_acquisition_and_stale_snapshot_never_return_identity():
    clock, cancel = Clock(), Event()

    def acquire():
        result = snapshot(start=clock(), finish=clock())
        cancel.set()
        return result

    resolver, _, _, calls = callback(clock=clock, cancel=cancel, acquire=acquire)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        resolver(request(clock).controller.identity)
    assert error.value.code == "CONTROLLER_RESOLUTION_CANCELLED" and len(calls) == 1
    resolver, clock, _, calls = callback(acquire=snapshot)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        resolver(request(clock).controller.identity)
    assert error.value.code == "CONTROLLER_METADATA_NOT_FRESH" and len(calls) == 1


def test_cancellation_during_pure_resolution_cannot_publish_callback_success(
    monkeypatch,
):
    resolver, clock, cancel, _ = callback()
    actual = resolution.resolve_controller_metadata

    def compare(*args):
        result = actual(*args)
        cancel.set()
        return result

    monkeypatch.setattr(resolution, "resolve_controller_metadata", compare)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        resolver(request(clock).controller.identity)
    assert error.value.code == "CONTROLLER_RESOLUTION_CANCELLED"
    # A retained comparison is not permission or successful callback delivery.
    assert resolver.status()["latest"]["qualified"] is False


@pytest.mark.parametrize("drift_at", [None, 1, 2])
def test_actual_nonpurging_worker_uses_fresh_callback_and_stops_before_open_or_write(
    drift_at,
):
    clock, cancel = Clock(), Event()
    exact = request(clock)
    api = IncapableWin32SerialApi()
    backend = NonPurgingArmFeedbackBackend(exact.controller, api=api)
    count = 0

    def acquire():
        nonlocal count
        count += 1
        observed = (
            native()
            if count != drift_at
            else replace(native(), driver_version="changed")
        )
        return snapshot(observations=(observed,), start=clock(), finish=clock())

    resolver = resolution.ExplicitArmControllerResolver(
        exact.controller,
        acquire,
        deadline_ns=exact.expires_monotonic_ns,
        cancellation=cancel,
        monotonic_ns=clock,
    )
    worker = ArmFeedbackWorker(
        authorizer=lambda _: None,
        identity_resolver=resolver,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(exact, cancellation=cancel)
    if drift_at is None:
        assert result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
        assert result.api_counts.identity_checks == count == 2
        assert result.api_counts.write_attempts == 1
    else:
        assert result.api_counts.write_attempts == 0
        assert result.primary_error.code == "CONTROLLER_METADATA_HELD"
        assert result.api_counts.open_attempts == (0 if drift_at == 1 else 1)
        assert result.api_counts.closes_confirmed == (0 if drift_at == 1 else 1)
    assert api.open_handles == ()
    assert backend.retain_evidence(exact, result).view()["physical_authority"] is False


def test_default_physical_backend_still_holds_before_resolver_or_authorizer():
    clock = Clock()
    exact = request(clock, origin=EvidenceOrigin.PHYSICAL_OBSERVATION)
    backend = NonPurgingArmFeedbackBackend(exact.controller)

    def forbidden(*args):
        pytest.fail("Physical hold must precede metadata callback/authorization")

    worker = ArmFeedbackWorker(
        authorizer=forbidden,
        identity_resolver=forbidden,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(exact)
    assert result.outcome is ArmFeedbackOutcome.BLOCKED_PRE_OPEN
    assert result.primary_error.code == NATIVE_HOLD
    assert result.api_counts.identity_checks == result.api_counts.object_creations == 0
