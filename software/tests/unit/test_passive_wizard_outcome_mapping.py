"""Operator-facing outcomes remain distinct from command readiness."""

from dataclasses import replace
import json

from rocell.application.wizard_passive_arm_coordinator import PassiveCoordinatorOutcome
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.passive_native_wire import encode_result
from test_passive_native_wire import fixture
from test_wizard_native_arm_metadata import no_host_access


def outcome():
    wire, child = fixture()
    parsed = json.loads(encode_result(child, wire))
    process = OwnedWorkerResult(
        "SUCCEEDED",
        None,
        (),
        wire["request_sha256"],
        wire["attempt_id"],
        True,
        True,
        True,
        0,
        1,
        1,
        1,
        1,
        b"",
        b"",
        parsed,
    )
    return PassiveCoordinatorOutcome(process, "a" * 64, None)


def test_real_held_observation_is_reported_as_software_hold():
    result = outcome().wizard_publication()
    assert result["status"] == "FAILED"
    assert result["code"] == "PASSIVE_NATIVE_RELEASE_HELD"
    assert "arm fault" in result["message"]
    assert result["physical_authority"] is False


def test_native_publication_fits_actual_wizard_depth_budget():
    from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record

    value = outcome()
    publication = value.wizard_publication()
    # Use the surrounding operation envelope, not only the inner summary.
    sanitized = sanitize_diagnostic_record(
        {"result": publication}, maximum_bytes=1024 * 1024
    )
    assert sanitized["result"]["code"] == "PASSIVE_NATIVE_RELEASE_HELD"
    assert "parsed_result" not in value.summary()["process"]
    assert value.process.parsed_result is not None


def test_uncertain_process_cleanup_takes_precedence():
    value = outcome()
    value = replace(value, process=replace(value.process, tree_exit_confirmed=False))
    assert value.wizard_publication()["code"] == "PASSIVE_PROCESS_CLEANUP_UNKNOWN"


def test_failed_persistence_takes_precedence_over_child_success():
    value = replace(outcome(), outcome_sha256=None, persistence_error="OSError")
    assert value.wizard_publication()["code"] == "PASSIVE_OUTCOME_PERSISTENCE_FAILED"


def test_cancellation_keeps_its_distinct_status():
    value = outcome()
    value = replace(
        value, process=replace(value.process, status="CANCELLED", parsed_result=None)
    )
    assert value.wizard_publication()["status"] == "CANCELLED"


def test_success_wording_is_observation_only_not_command_readiness():
    value = outcome()
    # Model the supervisor's already-validated success summary for this pure
    # presentation test only. This is not an accepted physical wire result.
    observation = value.process.parsed_result["child_result"]["observation"]
    observation["lifecycle"]["primary_error"] = None
    observation["summary"].update(status="OBSERVED_CLOSED", holds=[])
    result = value.wizard_publication()
    assert result["status"] == "SUCCEEDED"
    assert result["code"] == "PASSIVE_OBSERVATION_COMPLETED"
    assert result["physical_authority"] is False
    assert result["steps"][0]["report"]["connected"] is False
    assert "not connected for commands" in result["message"]
