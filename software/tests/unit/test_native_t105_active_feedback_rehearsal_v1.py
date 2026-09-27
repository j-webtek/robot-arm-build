from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.arm.feedback_wire import FeedbackWireError
from rocell.arm.protocol import encode_line
from rocell.application.native_t102_read_only_endpoint_intake_v1 import (
    parse_native_t102_read_only_endpoint_intake_v1,
)
from rocell.application.native_t105_active_feedback_intake_v1 import (
    build_native_t105_active_feedback_intake_v1,
)
from rocell.application.native_t105_active_feedback_rehearsal_v1 import (
    DeterministicFakeT105Endpoint,
    NativeT105ActiveFeedbackRehearsalError,
    rehearse_native_t105_active_feedback_v1,
)


ROOT = Path(__file__).resolve().parents[2]


def intake():
    document = json.loads((
        ROOT / "ai/eval/arm061_read_only_endpoint_intake.json"
    ).read_text(encoding="utf-8"))
    source = parse_native_t102_read_only_endpoint_intake_v1(document)
    return build_native_t105_active_feedback_intake_v1(
        source,
        passive_qualification_sha256=(
            "ac84722855d43e66e07d512bd60c3d19b2c468c0defe1505303f233bc4148aea"),
        intake_id="arm063-rehearsal", created_utc="2026-09-27T13:00:00Z",
    )


def response(**changes):
    fields = {
        "T": 1051, "x": 1, "y": 2, "z": 3, "tit": 0.1,
        "b": 0.01, "s": 0.02, "e": 0.03, "t": 0.04,
        "r": 0.05, "g": 0.06,
    }
    fields.update(changes)
    return encode_line(fields)


def fake(**changes):
    values = {
        "endpoint_sha256": intake().endpoint.endpoint_sha256,
        "response_line": response(),
    }
    values.update(changes)
    return DeterministicFakeT105Endpoint(**values)


def test_fake_rehearsal_exercises_exact_one_shot_lifecycle():
    endpoint = fake()
    receipt = rehearse_native_t105_active_feedback_v1(intake(), endpoint)
    document = receipt.to_dict()
    assert endpoint.written == b'{"T":105}\n'
    assert (endpoint.open_count, endpoint.write_count, endpoint.read_count,
            endpoint.close_count) == (1, 1, 1, 1)
    assert endpoint.is_open is False
    assert document["status"] == "FAKE_ONE_SHOT_T105_REHEARSAL_PASS"
    assert document["joint_fields"] == {
        "b": .01, "s": .02, "e": .03, "t": .04, "r": .05, "g": .06,
    }
    assert document["movement_command_count"] == 0
    assert document["torque_command_count"] == 0
    assert document["t102_command_count"] == 0
    assert document["automatic_retry_count"] == 0
    assert document["hardware_access"] is False


@pytest.mark.parametrize("changes,error", [
    ({"prebuffered_bytes": 1}, FeedbackWireError),
    ({"short_write": True}, NativeT105ActiveFeedbackRehearsalError),
    ({"response_line": b'{"T":1051}'}, FeedbackWireError),
    ({"response_line": encode_line({"T": 104})}, FeedbackWireError),
    ({"response_line": response(g="bad")}, FeedbackWireError),
    ({"response_line": encode_line({"T": 1051, "b": 0})},
     NativeT105ActiveFeedbackRehearsalError),
])
def test_failure_is_terminal_and_still_closes(changes, error):
    endpoint = fake(**changes)
    with pytest.raises(error):
        rehearse_native_t105_active_feedback_v1(intake(), endpoint)
    assert endpoint.open_count == 1
    assert endpoint.close_count == 1
    assert endpoint.is_open is False
    assert endpoint.write_count <= 1
    assert endpoint.read_count <= 1


def test_crossed_identity_and_arbitrary_transport_reject_before_open():
    endpoint = fake(endpoint_sha256="0" * 64)
    with pytest.raises(NativeT105ActiveFeedbackRehearsalError, match="identity"):
        rehearse_native_t105_active_feedback_v1(intake(), endpoint)
    assert endpoint.open_count == 0
    with pytest.raises(TypeError, match="DeterministicFake"):
        rehearse_native_t105_active_feedback_v1(intake(), object())


def test_fake_runner_has_no_serial_import_or_port_factory():
    source = (ROOT / "src/rocell/application" /
              "native_t105_active_feedback_rehearsal_v1.py").read_text(
                  encoding="utf-8")
    for prohibited in ("import serial", "serial.tools", "list_ports", "comports"):
        assert prohibited not in source
