"""Pure powered intent constraints; no port, process or native API access."""

import pytest

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.application.powered_arm_feedback_contract import (
    PoweredFeedbackIntent,
    SCHEMA,
    PURPOSE,
    LIMITS,
    REFERENCE_NAMES,
)


def document():
    return dict(
        schema=SCHEMA,
        purpose=PURPOSE,
        mode="physical",
        session_id="wizard-" + "a" * 32,
        attempt_id="operation-" + "b" * 32,
        references={key: "c" * 64 for key in REFERENCE_NAMES},
        startup_recorded_monotonic_ns=1_000_000_000,
        parent_deadline_monotonic_ns=20_000_000_000,
        limits=dict(LIMITS),
    )


def test_fixed_query_is_not_a_passive_or_motion_request():
    value = PoweredFeedbackIntent(_canonical(document()))
    value.require_time_available(2_000_000_000)
    assert value.outbound_line == b'{"T":105}\n'
    assert value.summary()["physical_dispatch_available"] is False
    assert value.summary()["references_verified"] is False
    with pytest.raises(ValueError):
        PassiveBenchRequest(value.payload)


@pytest.mark.parametrize(
    "key,value",
    [
        ("maximum_write_attempts", 2),
        ("maximum_open_attempts", 2),
        ("retries", 1),
        ("maximum_outbound_bytes", 100),
        ("cleanup_timeout_ms", 0),
        ("maximum_write_attempts", True),
    ],
)
def test_limits_cannot_be_extended_or_boolean_coerced(key, value):
    doc = document()
    doc["limits"][key] = value
    with pytest.raises(ValueError):
        PoweredFeedbackIntent(_canonical(doc))


@pytest.mark.parametrize(
    "field", ["command", "port", "physical_authority", "torque", "home"]
)
def test_no_raw_command_path_or_permission_field(field):
    doc = document()
    doc[field] = True
    with pytest.raises(ValueError):
        PoweredFeedbackIntent(_canonical(doc))


@pytest.mark.parametrize("now", [True, 0, 14_000_000_000, 302_000_000_000])
def test_stale_future_or_insufficient_lifetime_is_rejected(now):
    intent = PoweredFeedbackIntent(_canonical(document()))
    with pytest.raises(ValueError):
        intent.require_time_available(now)


def test_powered_original_and_firmware_review_are_distinct_required_references():
    doc = document()
    doc["references"].pop("firmware_compatibility_review_sha256")
    with pytest.raises(ValueError):
        PoweredFeedbackIntent(_canonical(doc))
    doc = document()
    doc["references"]["powered_startup_original_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        PoweredFeedbackIntent(_canonical(doc))
