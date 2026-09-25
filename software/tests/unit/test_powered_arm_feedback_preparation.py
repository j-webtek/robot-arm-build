"""Join real public startup records to fixture identity/reviews, no device I/O."""

import hashlib
import json
from pathlib import Path
import time

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.powered_arm_feedback_contract import (
    PoweredFeedbackIntent,
    SCHEMA,
    PURPOSE,
    LIMITS,
)
from rocell.application.powered_arm_feedback_preparation import prepare_powered_feedback
from test_wizard_native_arm_integration import setup, action
from test_wizard_passive_arm_setup import ready
from test_wizard_powered_arm_setup import ACTION, VALUES


def inputs(setup):
    service, _, _, _ = ready(setup)
    native = _canonical(service._native_arm_report)
    generic = service._device_selection.reviewed_candidate("SERIAL")
    operation = action(service, ACTION, **VALUES)
    receipt = operation["result"]["steps"][0]["report"]
    path = Path(receipt["path"])
    startup = json.loads(path.read_bytes())
    originals = dict(
        native_original=native,
        runtime_original=b"fixture runtime; not qualified",
        serial_profile_original=b"fixture profile; not reviewed",
        protocol_review_original=b"fixture protocol source",
        firmware_review_original=b"fixture review; not authenticated",
    )
    from rocell.application.powered_feedback_firmware_review import create_review

    originals["firmware_review_original"] = create_review(
        session_id=service.session_id,
        source_sha256=service.source_sha256,
        operator_id="fixture-operator",
        history_original=b"SYNTHETIC operator unchanged-delivery report",
        protocol_review_original=originals["protocol_review_original"],
    )
    mapping = {
        "native_original": "native_identity_original_sha256",
        "runtime_original": "runtime_sha256",
        "serial_profile_original": "serial_profile_sha256",
        "protocol_review_original": "protocol_review_sha256",
        "firmware_review_original": "firmware_compatibility_review_sha256",
    }
    refs = {
        mapping[name]: hashlib.sha256(raw).hexdigest()
        for name, raw in originals.items()
    }
    refs.update(
        source_sha256=service.source_sha256,
        powered_startup_original_sha256=receipt["sha256"],
    )
    body = dict(
        schema=SCHEMA,
        purpose=PURPOSE,
        mode="physical",
        session_id=service.session_id,
        attempt_id="operation-" + "b" * 32,
        references=refs,
        limits=dict(LIMITS),
        startup_recorded_monotonic_ns=startup["recorded_monotonic_ns"],
        parent_deadline_monotonic_ns=time.monotonic_ns() + 20_000_000_000,
    )
    return dict(
        intent=PoweredFeedbackIntent(_canonical(body)),
        root=path.parent,
        startup_operation_id=operation["operation_id"],
        current_source_sha256=service.source_sha256,
        generic_review=generic,
        now_monotonic_ns=time.monotonic_ns(),
        **originals,
    )


def test_public_originals_associate_but_do_not_authenticate_reviews(setup):
    values = inputs(setup)
    prepared = prepare_powered_feedback(**values)
    assert prepared.intent.outbound_line == b'{"T":105}\n'
    assert (
        dict(prepared.originals)["native_identity_original_sha256"]
        == values["native_original"]
    )
    assert prepared.summary()["physical_dispatch_available"] is False
    assert prepared.summary()["firmware_review_authenticated"] is False
    assert prepared.summary()["runtime_qualified"] is False
    assert dict(prepared.originals)["generic_review_original"] == _canonical(
        values["generic_review"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("firmware_review_original", None),
        ("protocol_review_original", b"changed"),
        ("current_source_sha256", "f" * 64),
        ("startup_operation_id", "../escape"),
    ],
)
def test_missing_changed_or_foreign_originals_rejected(setup, field, value):
    values = inputs(setup)
    values[field] = value
    with pytest.raises(ValueError):
        prepare_powered_feedback(**values)


def test_preparation_cannot_renew_startup_timestamp(setup):
    values = inputs(setup)
    body = values["intent"].to_dict()
    body["startup_recorded_monotonic_ns"] += 1
    values["intent"] = PoweredFeedbackIntent(_canonical(body))
    values["now_monotonic_ns"] += 1
    with pytest.raises(ValueError, match="startup context"):
        prepare_powered_feedback(**values)


def test_stale_setup_is_not_recovered_as_current(setup):
    values = inputs(setup)
    values["now_monotonic_ns"] += 301_000_000_000
    with pytest.raises(ValueError, match="stale"):
        prepare_powered_feedback(**values)


def test_changed_full_generic_review_invalidates_native_association(setup):
    values = inputs(setup)
    values["generic_review"] = {}
    with pytest.raises((ValueError, KeyError)):
        prepare_powered_feedback(**values)
