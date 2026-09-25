"""Join the real public setup producer to exact request and one-use persistence."""

import json
from pathlib import Path
import time

import pytest

from rocell.application.passive_arm_preparation import prepare_attempt
from rocell.application.passive_arm_attempt_store import inspect_attempt
from test_wizard_passive_arm_setup import ready, ACTION, VALUES
from test_wizard_native_arm_integration import setup, action


def prepared_inputs(setup):
    service, runner, _, directory = ready(setup)
    result = action(service, ACTION, **VALUES)
    assert result["status"] == "SUCCEEDED", result
    receipt = result["result"]["steps"][0]["report"]
    return (
        service,
        runner,
        dict(
            root=Path(receipt["path"]).parent,
            setup_operation_id=result["operation_id"],
            expected_setup_sha256=receipt["sha256"],
            session_id=service.session_id,
            source_sha256=service.source_sha256,
            attempt_id="operation-" + "b" * 32,
            registration={"test_only": "NOT A REGISTERED PHYSICAL WORKER"},
            deadline_ns=time.monotonic_ns() + 30_000_000_000,
            now_monotonic_ns=time.monotonic_ns(),
        ),
    )


def test_public_setup_becomes_exact_unconsumed_request(setup):
    service, runner, values = prepared_inputs(setup)
    calls = list(runner.calls)
    result = prepare_attempt(**values)
    request = result.request.to_dict()
    assert request["mode"] == "physical"
    assert request["launch_id"] == service.session_id
    assert request["limits"]["maximum_outbound_bytes"] == 0
    assert result.request.summary()["physical_dispatch_available"] is False
    assert runner.calls == calls
    before = inspect_attempt(values["root"], values["attempt_id"])
    assert before["status"] == "PREPARED_NOT_REPLAYABLE"
    result.journal.consume(now_monotonic_ns=time.monotonic_ns())
    assert (
        inspect_attempt(values["root"], values["attempt_id"])["status"]
        == "OUTCOME_UNKNOWN_NO_REPLAY"
    )
    with pytest.raises(ValueError, match="already consumed"):
        result.journal.consume(now_monotonic_ns=time.monotonic_ns())


@pytest.mark.parametrize(
    "field,value",
    [
        ("session_id", "wizard-" + "d" * 32),
        ("source_sha256", "c" * 64),
        ("expected_setup_sha256", "c" * 64),
        ("setup_operation_id", "../arbitrary"),
    ],
)
def test_foreign_or_changed_setup_fails_before_journal(setup, field, value):
    _, _, values = prepared_inputs(setup)
    values[field] = value
    with pytest.raises(ValueError):
        prepare_attempt(**values)
    assert (
        inspect_attempt(values["root"], values["attempt_id"])["status"] == "NO_ATTEMPT"
    )


def test_setup_timestamp_is_not_renewed_during_preparation(setup):
    _, _, values = prepared_inputs(setup)
    values["now_monotonic_ns"] += 301_000_000_000
    values["deadline_ns"] = values["now_monotonic_ns"] + 30_000_000_000
    with pytest.raises(ValueError, match="association held"):
        prepare_attempt(**values)
    assert (
        inspect_attempt(values["root"], values["attempt_id"])["status"] == "NO_ATTEMPT"
    )


def test_not_enough_cleanup_time_prevents_intent(setup):
    _, _, values = prepared_inputs(setup)
    values["deadline_ns"] = values["now_monotonic_ns"] + 6_000_000_000
    with pytest.raises(ValueError):
        prepare_attempt(**values)
    assert (
        inspect_attempt(values["root"], values["attempt_id"])["status"] == "NO_ATTEMPT"
    )


def test_preserves_operator_time_and_unknown_measurement(setup):
    _, _, values = prepared_inputs(setup)
    result = prepare_attempt(**values)
    stored = json.loads(
        (
            values["root"]
            / (values["setup_operation_id"] + "-passive-setup-original.json")
        ).read_bytes()
    )
    evidence = json.loads(result.evidence.payload)
    assert evidence["setup_confirmed_monotonic_ns"] == stored["recorded_monotonic_ns"]
    assert evidence["facts"]["measured_isolation"] == "NOT_ESTABLISHED"
