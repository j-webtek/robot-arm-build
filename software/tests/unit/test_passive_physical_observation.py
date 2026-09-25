"""Held physical-entry tests: physical-shaped fixtures, no native DLL access."""

import hashlib
import json
from threading import Event
import time

import pytest

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.application.passive_arm_identity import PassiveControllerSelection
from rocell.providers.windows.passive_serial_binding import PassiveSerialBinding
from rocell.providers.windows.passive_serial_api import WindowsPassiveSerialApi
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32SerialApi,
    NATIVE_HOLD,
)
from rocell.providers.windows.passive_serial_observation import observe_physical
from test_arm_bench_qualification_contract import document
from test_wizard_native_arm_metadata import (
    correlate,
    generic_review,
    snapshot,
    no_host_access,
    SESSION,
)


def inputs():
    review = generic_review("physical")
    original = correlate(review=review, mode="physical")
    binding = PassiveSerialBinding(PassiveControllerSelection(_canonical(original)))
    request = document()
    request.update(
        mode="physical",
        launch_id=SESSION,
        parent_deadline_monotonic_ns=time.monotonic_ns() + 30_000_000_000,
    )
    request["references"]["native_metadata_review_sha256"] = hashlib.sha256(
        binding.selection.payload
    ).hexdigest()
    fresh = snapshot(mode="physical")
    start = time.monotonic_ns()
    fresh["started_monotonic_ns"] = start
    # Windows' clock can return the same tick for this instantaneous fixture.
    # Do not invent a future completion timestamp by adding a nanosecond.
    fresh["finished_monotonic_ns"] = start
    return (
        PassiveBenchRequest(_canonical(request)),
        binding,
        WindowsPassiveSerialApi("COM91"),
        Event(),
        dict(
            fresh_snapshot=fresh,
            generic_review=review,
            collection_not_before_ns=start,
            metadata_operation_id="operation-new-passive-check",
        ),
    )


def test_exact_physical_entry_stops_at_native_hold_with_no_open_claim():
    request, binding, api, cancellation, values = inputs()
    result = observe_physical(request, binding, api, cancellation, **values)
    assert result["result"]["open_state"] == "FAILED"
    assert result["result"]["close_state"] == "NOT_REQUIRED"
    assert result["result"]["outbound_bytes"] == 0
    assert result["lifecycle"]["primary_error"]["code"] == NATIVE_HOLD
    assert result["lifecycle"]["actual_effect_counts"]["device_opens"] == 0
    assert result["physical_authority"] is result["connected"] is False
    assert result["identity_recheck"]["status"] == "METADATA_RECHECK_MATCHED"


def test_cancellation_before_open_does_not_consume_native_api():
    request, binding, api, cancellation, values = inputs()
    cancellation.set()
    result = observe_physical(request, binding, api, cancellation, **values)
    assert result["result"]["open_state"] == "NOT_ATTEMPTED"
    assert result["lifecycle"]["open_consumed"] is False


def test_wrong_selected_report_rejected_before_lifecycle():
    request, binding, api, cancellation, values = inputs()
    body = request.to_dict()
    body["references"]["native_metadata_review_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="selection mismatch"):
        observe_physical(
            PassiveBenchRequest(_canonical(body)), binding, api, cancellation, **values
        )


def test_changed_native_driver_rejected_before_lifecycle():
    request, binding, api, cancellation, values = inputs()
    values["fresh_snapshot"]["native_observations"][0]["driver_version"] = "changed"
    with pytest.raises(ValueError, match="identity recheck held"):
        observe_physical(request, binding, api, cancellation, **values)


def test_memory_api_cannot_be_promoted_to_physical_observation():
    request, binding, _, cancellation, values = inputs()
    with pytest.raises(ValueError, match="Exact physical"):
        observe_physical(
            request, binding, IncapableWin32SerialApi(), cancellation, **values
        )
