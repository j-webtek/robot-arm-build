"""Explicit identity lookup uses incapable fixtures, never OS/device queries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rocell.providers.windows.camera_worker_client import (
    CameraCandidate,
    CameraWorkerError,
    NativeProcessResult,
    WindowsCameraWorkerClient,
    parse_camera_identity_receipt,
)


ENDPOINT = r"\\?\fixture#camera-identity#OPAQUE"
GUID = "12345678-9abc-def0-0102-030405060708"


def observed(value):
    return {
        "availability": "OBSERVED",
        "value": value,
        "error": {"reason": "NONE", "domain": "NONE", "native_code": 0},
    }


def unavailable(reason="API_FAILURE", domain="CONFIGURATION_MANAGER", code=13):
    return {
        "availability": "UNAVAILABLE",
        "value": None,
        "error": {"reason": reason, "domain": domain, "native_code": code},
    }


def node(identifier: int):
    return {
        "devnode": identifier,
        "instance_id": observed(f"UNINTERPRETED-FIXTURE-{identifier}"),
        "container_id": observed(GUID),
        "location_paths": observed(["FIXTURE-PORT-PATH"]),
    }


def fixture():
    return {
        "schema": "rocell.windows_camera_identity.v1",
        "status": "METADATA_ONLY",
        "requested_endpoint": ENDPOINT,
        "mapping": {
            "devnode": observed(1),
            "interface_path": observed(ENDPOINT),
            "cleanup_errors": [],
        },
        "device": node(1),
        "parents": [node(2)],
        "observed_root": observed(2),
        "chain_end": "REACHED_OBSERVED_ROOT",
        "chain_error": {"reason": "NOT_REQUESTED", "domain": "NONE", "native_code": 0},
        "api_calls": 9,
        "observed_property_bytes": 128,
        "limits": {
            "max_parent_nodes": 8,
            "max_property_bytes": 16384,
            "max_total_property_bytes": 131072,
            "max_instance_chars": 1024,
            "max_location_paths": 16,
            "duration_ms": 5000,
        },
        "provenance": "WINDOWS_SETUPAPI_CONFIGURATION_MANAGER_METADATA",
        "camera_activation_count": 0,
        "physical_authority": False,
    }


def parse(value):
    return parse_camera_identity_receipt(
        value, expected_endpoint=ENDPOINT, duration_ms=5000, max_parent_nodes=8
    )


class FixtureRunner:
    def __init__(self, receipt=None):
        self.receipt = fixture() if receipt is None else receipt
        self.calls = []
        self.raw = None
        self.timed_out = False
        self.output_limit_exceeded = False
        self.returncode = 0

    def __call__(self, arguments, timeout, limit):
        self.calls.append((arguments, timeout, limit))
        return NativeProcessResult(
            self.returncode,
            self.raw if self.raw is not None else json.dumps(self.receipt).encode(),
            timed_out=self.timed_out,
            output_limit_exceeded=self.output_limit_exceeded,
        )


def client(tmp_path: Path, runner: FixtureRunner):
    path = tmp_path / "incapable-helper.exe"
    path.write_bytes(b"fixture only; never executed")
    return WindowsCameraWorkerClient(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), runner=runner
    )


def test_identity_is_separate_explicit_metadata_action(tmp_path: Path):
    runner = FixtureRunner()
    provider = client(tmp_path, runner)
    assert not runner.calls
    result = provider.resolve_identity_metadata(
        CameraCandidate(ENDPOINT, "fixture camera")
    )
    assert result.exact_endpoint_observed and not result.physical_authority
    assert result.endpoint_sha256 == hashlib.sha256(ENDPOINT.encode()).hexdigest()
    assert result.device.instance_id.value == "UNINTERPRETED-FIXTURE-1"
    assert result.device.container_id.value == GUID
    assert result.parents[0].devnode == 2
    assert runner.calls[0][0][1:] == (
        "identity",
        "--endpoint",
        ENDPOINT,
        "--max-ms",
        "5000",
        "--max-parents",
        "8",
    )
    assert runner.calls[0][1] == 10
    assert not hasattr(result.device, "serial_number") and not hasattr(
        result.device, "usb_speed"
    )


def test_changed_native_interface_path_is_not_normalized_to_exact_match():
    data = fixture()
    data["mapping"]["interface_path"] = observed(ENDPOINT.lower())
    result = parse(data)
    assert result.interface_path.value == ENDPOINT.lower()
    assert not result.exact_endpoint_observed


def test_missing_properties_remain_typed_unavailable():
    data = fixture()
    data["device"]["container_id"] = unavailable()
    data["device"]["location_paths"] = unavailable("BYTE_LIMIT", "CONTRACT", 0)
    result = parse(data)
    assert not result.device.container_id.observed
    assert result.device.container_id.value is None
    assert result.device.container_id.error.native_code == 13
    assert result.device.location_paths.error.reason == "BYTE_LIMIT"


def test_empty_location_list_and_zero_guid_are_observed_not_unique_identity():
    data = fixture()
    data["device"]["location_paths"] = observed([])
    data["device"]["container_id"] = observed("00000000-0000-0000-0000-000000000000")
    result = parse(data)
    assert (
        result.device.location_paths.observed
        and result.device.location_paths.value == ()
    )
    assert result.device.container_id.observed and not result.physical_authority


def test_removed_endpoint_is_not_replaced_by_same_name_or_parent():
    data = fixture()
    data.update(
        device=None,
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
    assert result.device is None and not result.exact_endpoint_observed
    assert (
        result.devnode.error.domain == "WIN32"
        and result.devnode.error.native_code == 433
    )


def test_metadata_handle_cleanup_error_prevents_exact_mapping_success():
    data = fixture()
    data["mapping"]["cleanup_errors"] = [
        {"reason": "API_FAILURE", "domain": "WIN32", "native_code": 5}
    ]
    result = parse(data)
    assert (
        not result.exact_endpoint_observed and result.cleanup_errors[0].native_code == 5
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="rocell.windows_camera.v1"),
        lambda d: d.update(serial_number="invented"),
        lambda d: d.update(usb_speed="USB3"),
        lambda d: d.update(requested_endpoint="other-endpoint"),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(camera_activation_count=1),
        lambda d: d.update(camera_activation_count=False),
        lambda d: d.update(api_calls=0),
        lambda d: d.update(api_calls=True),
        lambda d: d.update(observed_property_bytes=131073),
        lambda d: d.update(observed_property_bytes=0),
        lambda d: d.update(chain_end="ASSUMED_ROOT"),
        lambda d: d.update(chain_end="NOT_REQUESTED"),
        lambda d: d["chain_error"].update(domain=[]),
        lambda d: d["observed_root"].update(value=999),
        lambda d: d["parents"][0].update(devnode=1),
        lambda d: d["device"].update(devnode=99),
        lambda d: d["device"].update(serial_number="guessed-from-instance-id"),
        lambda d: d["device"]["instance_id"].update(value="bad\x00identifier"),
        lambda d: d["device"]["container_id"].update(value="not-a-guid"),
        lambda d: d["device"]["container_id"].update(availability="UNAVAILABLE"),
        lambda d: d["device"]["container_id"]["error"].update(
            reason="API_FAILURE", domain="CONFIGURATION_MANAGER", native_code=13
        ),
        lambda d: d["device"]["location_paths"].update(value=["path"] * 17),
        lambda d: d["limits"].update(duration_ms=5001),
        lambda d: d["limits"].update(max_parent_nodes=True),
        lambda d: d["mapping"].update(interface_path=unavailable()),
        lambda d: d.update(provenance="INFERRED_FROM_FRIENDLY_NAME"),
    ],
)
def test_identity_receipt_is_closed_typed_and_request_bound(mutate):
    data = fixture()
    mutate(data)
    with pytest.raises(CameraWorkerError):
        parse(data)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "malformed",
        "nonfinite",
        "too_large",
        "timed_out",
        "output_limit",
        "failed_exit",
    ],
)
def test_identity_ipc_failure_does_not_retry_or_claim_camera_cleanup(
    tmp_path: Path, fault: str
):
    runner = FixtureRunner()
    if fault == "duplicate":
        runner.raw = json.dumps(fixture()).encode()[:-1] + b',"status":"METADATA_ONLY"}'
    elif fault == "malformed":
        runner.raw = b"not JSON"
    elif fault == "nonfinite":
        runner.raw = b'{"metadata":NaN}'
    elif fault == "too_large":
        runner.raw = b"x" * (256 * 1024 + 1)
    elif fault == "timed_out":
        runner.timed_out = True
    elif fault == "output_limit":
        runner.output_limit_exceeded = True
    else:
        runner.returncode = 1
    with pytest.raises(CameraWorkerError) as error:
        client(tmp_path, runner).resolve_identity_metadata(
            CameraCandidate(ENDPOINT, "fixture")
        )
    assert len(runner.calls) == 1
    assert (
        not error.value.effect_uncertain
    )  # A metadata deadline is not a camera-open campaign.


def test_identity_authority_violation_is_explicit(tmp_path: Path):
    data = fixture()
    data["camera_activation_count"] = 1
    runner = FixtureRunner(data)
    with pytest.raises(CameraWorkerError) as error:
        client(tmp_path, runner).resolve_identity_metadata(
            CameraCandidate(ENDPOINT, "fixture")
        )
    assert error.value.effect_uncertain


def test_identity_limits_rejected_before_dispatch(tmp_path: Path):
    runner = FixtureRunner()
    provider = client(tmp_path, runner)
    with pytest.raises(CameraWorkerError):
        provider.resolve_identity_metadata(
            CameraCandidate(ENDPOINT, "fixture"), max_parent_nodes=17
        )
    with pytest.raises(CameraWorkerError):
        provider.resolve_identity_metadata(
            CameraCandidate(ENDPOINT, "fixture"), duration_ms=True
        )
    assert runner.calls == []


def test_identity_helper_registration_is_still_enforced(tmp_path: Path):
    runner = FixtureRunner()
    provider = client(tmp_path, runner)
    provider.native_executable.write_bytes(b"substituted")
    with pytest.raises(CameraWorkerError, match="HASH_MISMATCH"):
        provider.resolve_identity_metadata(CameraCandidate(ENDPOINT, "fixture"))
    assert not runner.calls
