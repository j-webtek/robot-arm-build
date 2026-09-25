"""Parent-side validation of the draft pre-activation result section.

This is one component of the v2 result reader, not an owned-result
authenticator. That reader must bind REQUEST/READY/permit/child, validate the
unchanged native acquisition body and enforce the process deadline separately.
No child Boolean substitutes for comparing the independently expected unit.
"""

from dataclasses import dataclass
import json
from typing import Any

from rocell.providers.windows.camera_worker_client import (
    IDENTITY_PROTOCOL_SCHEMA,
    NativeCameraIdentityReceipt,
    parse_camera_identity_receipt,
)
from .native_camera_activation_expectation import CameraActivationExpectation

SCHEMA = "rocell.camera_pre_activation_identity.v1"
FIELDS = {
    "schema",
    "expected_identity_sha256",
    "original_identity_sha256",
    "native_started_ms",
    "native_deadline_ms",
    "attempted",
    "resolution_attempted",
    "resolution_returned",
    "activation_callback_entered",
    "observation_started_ms",
    "observation_returned_ms",
    "comparison",
    "metadata",
}
COMPARISONS = {
    "MATCH",
    "INVALID_EXPECTATION",
    "ENDPOINT_CHANGED",
    "MAPPING_UNAVAILABLE",
    "MAPPING_CHANGED",
    "METADATA_CLEANUP_UNCONFIRMED",
    "DEVICE_UNAVAILABLE",
    "DRIVER_UNAVAILABLE",
    "DETACHED_DEVICE_OR_DRIVER",
    "INCOMPLETE_OBSERVATION",
    "INSTANCE_CHANGED",
    "CONTAINER_CHANGED",
    "LOCATION_CHANGED",
    "DRIVER_CHANGED",
}
FLAGS = (
    "attempted",
    "resolution_attempted",
    "resolution_returned",
    "activation_callback_entered",
)


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def tick(value: Any) -> bool:
    return type(value) is int and 0 <= value < 2**64


def comparison_for(expected, observed: NativeCameraIdentityReceipt) -> str:
    """Recompute the native comparison order from strictly parsed observations."""
    if not observed.devnode.observed or not observed.interface_path.observed:
        return "MAPPING_UNAVAILABLE"
    if observed.interface_path.value != expected["endpoint"]:
        return "MAPPING_CHANGED"
    if observed.cleanup_errors:
        return "METADATA_CLEANUP_UNCONFIRMED"
    device, driver = observed.device, observed.driver
    if device is None:
        return "DEVICE_UNAVAILABLE"
    if driver is None:
        return "DRIVER_UNAVAILABLE"
    if not (
        observed.chain_end == "REACHED_OBSERVED_ROOT"
        and observed.observed_root.observed
        and observed.parents
        and observed.parents[-1].devnode == observed.observed_root.value
        and all(
            field.observed
            for field in (
                device.instance_id,
                device.container_id,
                device.location_paths,
                driver.provider,
                driver.service,
                driver.version,
                driver.inf_path,
            )
        )
    ):
        return "INCOMPLETE_OBSERVATION"
    if device.instance_id.value != expected["instance_id"]:
        return "INSTANCE_CHANGED"
    if device.container_id.value != expected["container_id"]:
        return "CONTAINER_CHANGED"
    if device.location_paths.value != tuple(
        json.loads(expected["location_paths_json"]).values()
    ):
        return "LOCATION_CHANGED"
    if not (
        driver.provider.value == expected["driver_provider"]
        and driver.service.value == expected["driver_service"]
        and driver.version.value == expected["driver_version"]
        and driver.inf_path.value == expected["driver_inf"]
    ):
        return "DRIVER_CHANGED"
    return "MATCH"


@dataclass(frozen=True)
class ActivationObservation:
    attempted: bool
    resolution_attempted: bool
    resolution_returned: bool
    activation_callback_entered: bool
    comparison: str | None
    independently_matches: bool | None
    metadata: NativeCameraIdentityReceipt | None


def validate_activation_observation(
    raw: Any,
    expected: CameraActivationExpectation,
    *,
    source_activation_attempts: int,
    source_opened: int,
    native_status: str,
) -> ActivationObservation:
    """Validate actual supplied observations; missing facts remain missing."""
    need(type(expected) is CameraActivationExpectation, "ACTIVATION_EXPECTATION_TYPE")
    expected = CameraActivationExpectation(expected.payload)
    data = expected.to_dict()
    need(type(raw) is dict and set(raw) == FIELDS, "ACTIVATION_OBSERVATION_FIELDS")
    need(
        raw["schema"] == SCHEMA
        and raw["expected_identity_sha256"] == expected.sha256
        and raw["original_identity_sha256"] == data["original_identity_sha256"],
        "ACTIVATION_OBSERVATION_BINDING",
    )
    need(all(type(raw[key]) is bool for key in FLAGS), "ACTIVATION_OBSERVATION_FLAGS")
    need(
        type(source_activation_attempts) is int
        and source_activation_attempts in (0, 1)
        and type(source_opened) is int
        and 0 <= source_opened <= source_activation_attempts
        and type(native_status) is str
        and native_status in {"OK", "FAILED"},
        "ACTIVATION_NATIVE_COUNTS",
    )
    started, deadline = raw["native_started_ms"], raw["native_deadline_ms"]
    before, after = raw["observation_started_ms"], raw["observation_returned_ms"]
    need(
        tick(started) and tick(deadline) and deadline - started == 5000,
        "ACTIVATION_ORIGINAL_DEADLINE",
    )
    attempted, resolving, returned, callback = (raw[key] for key in FLAGS)
    comparison = raw["comparison"]
    need(
        comparison is None or type(comparison) is str and comparison in COMPARISONS,
        "ACTIVATION_COMPARISON_CODE",
    )
    need(not resolving or attempted, "ACTIVATION_RESOLUTION_WITHOUT_ATTEMPT")
    need(not returned or resolving, "ACTIVATION_RETURN_WITHOUT_RESOLUTION")
    need(
        (
            (tick(before) and started <= before <= deadline - 100)
            if resolving
            else before is None
        ),
        "ACTIVATION_OBSERVATION_START",
    )
    need(
        after is None or returned and tick(after) and before <= after < deadline,
        "ACTIVATION_OBSERVATION_RETURN",
    )
    need((raw["metadata"] is not None) == returned, "ACTIVATION_METADATA_PRESENCE")
    need(
        comparison is None or after is not None, "ACTIVATION_COMPARISON_WITHOUT_RETURN"
    )
    observed, matched = None, None
    if returned:
        observed = parse_camera_identity_receipt(
            raw["metadata"],
            expected_endpoint=data["endpoint"],
            duration_ms=deadline - before,
            max_parent_nodes=16,
        )
        need(
            observed.protocol_schema == IDENTITY_PROTOCOL_SCHEMA,
            "ACTIVATION_LEGACY_METADATA",
        )
        independently_compared = comparison_for(data, observed)
        matched = independently_compared == "MATCH"
        if comparison is not None:
            need(
                comparison == independently_compared,
                "ACTIVATION_COMPARISON_CONTRADICTED",
            )
    need(
        not callback or comparison == "MATCH" and matched is True,
        "ACTIVATION_CALLBACK_WITHOUT_MATCH",
    )
    need(
        source_activation_attempts == 0 or callback,
        "ACTIVATION_WITHOUT_CHECKED_CALLBACK",
    )
    need(
        native_status != "OK" or callback and source_opened == 1,
        "ACTIVATION_SUCCESS_WITHOUT_OPEN",
    )
    return ActivationObservation(
        attempted, resolving, returned, callback, comparison, matched, observed
    )
