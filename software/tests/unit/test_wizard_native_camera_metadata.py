"""Metadata packet fixtures; no subprocess, host enumeration or device access."""

from __future__ import annotations

import builtins
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application import wizard_native_camera_metadata as metadata
from rocell.providers.windows import camera_worker_client as camera


def nominal():
    provider = metadata.RehearsalNativeCameraMetadataProvider()
    packet = provider.inventory()
    _, typed = metadata.validate_native_packet(
        packet, kind="inventory", **provider.descriptor()
    )
    return provider, packet, typed.candidates[0]


@pytest.mark.parametrize("scenario", sorted(metadata.SCENARIOS))
def test_closed_scenarios_use_actual_parsers_and_no_authority(scenario):
    provider = metadata.RehearsalNativeCameraMetadataProvider(scenario)
    packet, inventory = metadata.validate_native_packet(
        provider.inventory(), kind="inventory", **provider.descriptor()
    )
    assert packet["provenance"] == "INCAPABLE_FIXTURE"
    assert not any(inventory.counts.values())
    assert not inventory.modes and not inventory.controls and not inventory.frames
    selected = inventory.candidates[0]
    full, identity = metadata.validate_native_packet(
        provider.identity(selected),
        kind="identity",
        expected_endpoint=selected.symbolic_link,
        **provider.descriptor(),
    )
    assert full["receipt"]["physical_authority"] is False
    assert not identity.physical_authority
    if scenario == "missing-mapping":
        assert not identity.exact_endpoint_observed and identity.device is None
        assert identity.devnode.error.native_code == 433
    elif scenario == "wrong-device":
        assert identity.exact_endpoint_observed
        assert (
            identity.device.instance_id.value
            != r"USB\VID_FFFE&PID_0001\SYNTHETIC-CAMERA-A"
        )
    else:
        assert identity.exact_endpoint_observed
        assert (
            identity.device.instance_id.value
            == r"USB\VID_FFFE&PID_0001\SYNTHETIC-CAMERA-A"
        )
        assert (
            identity.device.container_id.value == "11111111-2222-3333-4444-555555555555"
        )
    if scenario == "duplicate-name":
        first, second = inventory.candidates
        assert first.friendly_name == second.friendly_name
        assert first.symbolic_link != second.symbolic_link
        _, other = metadata.validate_native_packet(
            provider.identity(second),
            kind="identity",
            expected_endpoint=second.symbolic_link,
            **provider.descriptor(),
        )
        assert other.endpoint_sha256 != identity.endpoint_sha256


def test_descriptor_and_construction_and_fixture_actions_are_inert(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("metadata construction/fixture accessed filesystem or process")

    native = camera.WindowsCameraWorkerClient(
        tmp_path / "absent.exe", "e" * 64, runner=forbidden
    )
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        for name in (
            "open",
            "stat",
            "lstat",
            "exists",
            "is_file",
            "is_dir",
            "resolve",
            "iterdir",
        ):
            patch.setattr(Path, name, forbidden)
        patch.setattr(camera.subprocess, "Popen", forbidden)
        provider = metadata.NativeCameraMetadataProvider(native)
        descriptor = provider.descriptor()
        assert descriptor is provider.descriptor()
        for scenario in metadata.SCENARIOS:
            fixture = metadata.RehearsalNativeCameraMetadataProvider(scenario)
            assert (
                fixture.descriptor()["helper_sha256"] == metadata.FIXTURE_HELPER_SHA256
            )
            packet = fixture.inventory()
            _, typed = metadata.validate_native_packet(
                packet, kind="inventory", **fixture.descriptor()
            )
            fixture.identity(typed.candidates[0])
    with pytest.raises(TypeError):
        descriptor["helper_sha256"] = "a" * 64


@pytest.mark.parametrize(
    "field,changed",
    [
        ("schema", "wrong"),
        ("kind", "identity"),
        ("provenance", "WINDOWS_NATIVE_METADATA"),
        ("helper_sha256", "f" * 64),
        ("extra", True),
    ],
)
def test_provider_context_and_exact_packet_fields_bound(field, changed):
    provider, packet, _ = nominal()
    packet[field] = changed
    with pytest.raises(metadata.NativeCameraMetadataError):
        metadata.validate_native_packet(
            packet, kind="inventory", **provider.descriptor()
        )


@pytest.mark.parametrize(
    "fault",
    [
        "activation",
        "boolean_count",
        "mode",
        "controls",
        "frames",
        "requested",
        "unknown_cleanup",
        "nonboolean_cleanup",
    ],
)
def test_inventory_strict_parser_rejects_nonmetadata_or_malformed_receipts(fault):
    provider, packet, _ = nominal()
    receipt = packet["receipt"]
    if fault == "activation":
        receipt["counts"]["source_activation_attempts"] = 1
    elif fault == "boolean_count":
        receipt["counts"]["source_opened"] = False
    elif fault == "mode":
        receipt["modes"] = [asdict(camera.NativeCameraMode(4, 2, 9, 1))]
    elif fault == "requested":
        receipt["requested_mode"] = asdict(camera.NativeCameraMode(4, 2, 9, 1))
    elif fault in {"controls", "frames"}:
        receipt[fault] = [{}]
    elif fault == "unknown_cleanup":
        receipt["cleanup"]["invented"] = 0
    else:
        receipt["cleanup"]["source_released"] = 1
    with pytest.raises(camera.CameraWorkerError):
        metadata.validate_native_packet(
            packet, kind="inventory", **provider.descriptor()
        )


@pytest.mark.parametrize(
    "fault",
    [
        "endpoint",
        "duration",
        "parents",
        "authority",
        "counter",
        "counter_bool",
        "invented_serial",
    ],
)
def test_identity_strict_parser_rejects_context_effect_or_schema_drift(fault):
    provider, _, selected = nominal()
    packet = provider.identity(selected)
    receipt = packet["receipt"]
    if fault == "endpoint":
        receipt["requested_endpoint"] = "another-opaque-endpoint"
    elif fault == "duration":
        receipt["limits"]["duration_ms"] = 5001
    elif fault == "parents":
        receipt["limits"]["max_parent_nodes"] = 9
    elif fault == "authority":
        receipt["physical_authority"] = True
    elif fault in {"counter", "counter_bool"}:
        receipt["camera_activation_count"] = 1 if fault == "counter" else False
    else:
        receipt["device"]["serial_number"] = "inferred-from-friendly-label"
    with pytest.raises(camera.CameraWorkerError):
        metadata.validate_native_packet(
            packet,
            kind="identity",
            expected_endpoint=selected.symbolic_link,
            **provider.descriptor(),
        )


@pytest.mark.parametrize(
    "fault",
    [
        "depth",
        "cycle",
        "wide",
        "large_text",
        "total_bytes",
        "float",
        "huge_int",
        "tuple",
        "bad_unicode",
    ],
)
def test_packet_budgets_reject_before_protocol_parser(fault, monkeypatch):
    provider, packet, _ = nominal()
    if fault in {"depth", "cycle"}:
        value = []
        if fault == "cycle":
            value.append(value)
        else:
            for _ in range(17):
                value = [value]
        packet["receipt"] = value
    elif fault == "wide":
        packet["receipt"] = [None] * 129
    elif fault == "large_text":
        packet["receipt"] = "x" * (16 * 1024 + 1)
    elif fault == "total_bytes":
        packet["receipt"] = ["x" * (16 * 1024)] * 17
    elif fault == "float":
        packet["receipt"] = float("nan")
    elif fault == "huge_int":
        packet["receipt"] = 2**63
    elif fault == "tuple":
        packet["receipt"] = ()
    else:
        packet["receipt"] = "\ud800"

    def forbidden(*args, **kwargs):
        pytest.fail("unsafe packet reached native protocol parser")

    monkeypatch.setattr(metadata, "parse_camera_inventory_receipt", forbidden)
    with pytest.raises(metadata.NativeCameraMetadataError):
        metadata.validate_native_packet(
            packet, kind="inventory", **provider.descriptor()
        )


def test_canonical_result_owns_containers_and_cannot_mutate_original():
    provider, packet, selected = nominal()
    owned, typed = metadata.validate_native_packet(
        packet, kind="inventory", **provider.descriptor()
    )
    packet["receipt"]["devices"][0]["friendly_name"] = "input changed"
    assert owned["receipt"]["devices"][0]["friendly_name"] == selected.friendly_name
    owned["receipt"]["counts"]["source_opened"] = 1
    # The parser must not share its count dictionary with returned mutable JSON.
    assert typed.counts["source_opened"] == 0
    identity, checked = metadata.validate_native_packet(
        provider.identity(selected),
        kind="identity",
        expected_endpoint=selected.symbolic_link,
        **provider.descriptor(),
    )
    identity["receipt"]["limits"]["duration_ms"] = 99
    assert checked.limits["duration_ms"] == 5000


class IncapableRunner:
    """Returns fixture bytes; no process launch even when called by real client."""

    def __init__(self, *, failed_inventory=False):
        self.provider, self.inventory_packet, self.selected = nominal()
        self.failed_inventory = failed_inventory
        self.calls = []
        self.exit_override = None

    def __call__(self, arguments, timeout, byte_limit):
        self.calls.append((arguments, timeout, byte_limit))
        assert arguments[1] in {"inventory", "identity"}
        if arguments[1] == "inventory":
            receipt = self.inventory_packet["receipt"]
            if self.failed_inventory:
                receipt["status"] = "FAILED"
                receipt["reason_code"] = "INCAPABLE_FAILED_CLEANUP"
                receipt["cleanup"].update(
                    mf_shutdown_hr=-2147467259, com_uninitialized=False
                )
        else:
            receipt = self.provider.identity(self.selected)["receipt"]
        code = 1 if receipt.get("status") == "FAILED" else 0
        return camera.NativeProcessResult(
            code if self.exit_override is None else self.exit_override,
            json.dumps(receipt).encode(),
        )


def native_client(tmp_path, runner):
    path = tmp_path / "incapable-never-run.exe"
    path.write_bytes(b"INCAPABLE metadata fixture bytes")
    return camera.WindowsCameraWorkerClient(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), runner=runner
    )


@pytest.mark.parametrize("failed_inventory", [False, True])
def test_actual_client_to_bridge_preserves_full_wire_cleanup(
    tmp_path, failed_inventory
):
    # WINDOWS_NATIVE_METADATA describes the adapter protocol. This injected
    # runner is incapable and provides no received-hardware qualification.
    runner = IncapableRunner(failed_inventory=failed_inventory)
    client = native_client(tmp_path, runner)
    provider = metadata.NativeCameraMetadataProvider(client)
    packet = provider.inventory()
    assert packet["receipt"] == runner.inventory_packet["receipt"]
    assert packet["receipt"]["cleanup"]["source_shutdown_hr"] is None
    if failed_inventory:
        assert packet["receipt"]["cleanup"]["mf_shutdown_hr"] == -2147467259
        assert packet["receipt"]["cleanup"]["com_uninitialized"] is False
    identity_packet = provider.identity(runner.selected)
    assert (
        identity_packet["receipt"]
        == runner.provider.identity(runner.selected)["receipt"]
    )
    assert [call[0][1] for call in runner.calls] == ["inventory", "identity"]
    assert all(call[1:] == (10.0, camera.MAX_IPC_BYTES) for call in runner.calls)
    assert runner.calls[1][0][-2:] == ("--max-parents", "8")


@pytest.mark.parametrize("operation", ["inventory", "identity"])
def test_wire_sink_is_immutable_bounded_canonical_and_callback_failure_never_retries(
    tmp_path, operation
):
    runner = IncapableRunner()
    client = native_client(tmp_path, runner)
    seen = []

    def sink(payload):
        assert type(payload) is bytes and len(payload) <= camera.MAX_IPC_BYTES
        assert (
            json.dumps(
                json.loads(payload),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
            == payload
        )
        seen.append(payload)
        raise RuntimeError("incapable retention failure")

    with pytest.raises(camera.CameraWorkerError):
        if operation == "inventory":
            client.enumerate_metadata(wire_receipt_sink=sink)
        else:
            client.resolve_identity_metadata(runner.selected, wire_receipt_sink=sink)
    assert len(seen) == len(runner.calls) == 1


@pytest.mark.parametrize("operation", ["inventory", "identity"])
def test_invalid_exit_never_delivers_wire_receipt(tmp_path, operation):
    runner = IncapableRunner()
    runner.exit_override = 7
    client = native_client(tmp_path, runner)
    seen = []
    with pytest.raises(camera.CameraWorkerError):
        if operation == "inventory":
            client.enumerate_metadata(wire_receipt_sink=seen.append)
        else:
            client.resolve_identity_metadata(
                runner.selected, wire_receipt_sink=seen.append
            )
    assert not seen and len(runner.calls) == 1


@pytest.mark.parametrize("mutation", ["helper", "path", "runner"])
def test_declared_registration_mutation_blocks_metadata_before_dispatch(
    tmp_path, mutation
):
    runner = IncapableRunner()
    client = native_client(tmp_path, runner)
    provider = metadata.NativeCameraMetadataProvider(client)
    descriptor = dict(provider.descriptor())
    if mutation == "helper":
        client.expected_sha256 = "f" * 64
    elif mutation == "path":
        client.native_executable = tmp_path / "replacement.exe"
    else:
        client.runner = lambda *args: pytest.fail("substituted metadata runner invoked")
    with pytest.raises(
        metadata.NativeCameraMetadataError, match="registration changed"
    ):
        provider.inventory()
    assert not runner.calls and provider.descriptor() == descriptor


def test_fixture_rejects_unknown_scenario_and_candidate_without_name_fallback():
    provider, _, selected = nominal()
    with pytest.raises(metadata.NativeCameraMetadataError):
        metadata.RehearsalNativeCameraMetadataProvider("arbitrary")
    with pytest.raises(metadata.NativeCameraMetadataError):
        provider.identity(
            camera.CameraCandidate("unknown-endpoint", selected.friendly_name)
        )


def test_invalid_sink_is_rejected_before_client_filesystem_preflight(tmp_path):
    client = camera.WindowsCameraWorkerClient(tmp_path / "missing.exe", "a" * 64)
    with pytest.raises(camera.CameraWorkerError, match="sink must be callable"):
        client.enumerate_metadata(wire_receipt_sink=False)


def test_failed_cleanup_cannot_hide_malformed_other_cleanup_field():
    provider, packet, _ = nominal()
    packet["receipt"]["status"] = "FAILED"
    packet["receipt"]["reason_code"] = "INCAPABLE_CLEANUP_FAILURE"
    packet["receipt"]["cleanup"].update(source_released=False, com_uninitialized=0)
    with pytest.raises(
        camera.CameraWorkerError, match="com_uninitialized must be Boolean"
    ):
        metadata.validate_native_packet(
            packet, kind="inventory", **provider.descriptor()
        )


def test_registration_guard_uses_runner_identity_not_overloaded_equality(tmp_path):
    runner = IncapableRunner()
    client = native_client(tmp_path, runner)
    provider = metadata.NativeCameraMetadataProvider(client)

    class EqualLookingRunner:
        def __eq__(self, other):
            return True

        def __call__(self, *args):
            pytest.fail("equal-looking substituted runner invoked")

    client.runner = EqualLookingRunner()
    with pytest.raises(
        metadata.NativeCameraMetadataError, match="registration changed"
    ):
        provider.inventory()
    assert not runner.calls
