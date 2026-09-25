"""Stage-12 cached display only: no serial, coordinator, storage or power I/O."""

import pytest

from test_arrival_wizard_arm_power_ui import report, terminal
from test_arrival_wizard_reopen_ui import browser, commissioning


def safe_summary():
    return {
        "schema": "rocell.rehearsal_arm_feedback_summary.v1",
        "binding_sha256": "1" * 64,
        "source_sha256": "2" * 64,
        "request_sha256": "3" * 64,
        "controller_binding_sha256": "4" * 64,
        "worker_outcome": "SUCCEEDED_DIAGNOSTIC",
        "technical_response_valid": True,
        "feedback_receipt_valid": True,
        "serial_cleanup_confirmed": True,
        "effect_uncertain": False,
        "api_counts": {
            "object_creations": 1,
            "identity_checks": 2,
            "open_attempts": 1,
            "opens_confirmed": 1,
            "unexpected_open_objects": 0,
            "write_attempts": 1,
            "writes_confirmed": 1,
            "write_bytes_confirmed": 10,
            "read_attempts": 2,
            "read_bytes_retained": 180,
            "close_attempts": 1,
            "closes_confirmed": 1,
        },
        "primary_error": None,
        "cleanup_errors": [],
        "wire": {
            "response": {"sha256": "5" * 64, "retained_bytes": 180},
            "unexpected": {
                "sha256": "6" * 64,
                "retained_bytes": 0,
                "unretained_bytes": 0,
            },
        },
        "timing": {
            "opened_monotonic_ns": 9223372036854000000,
            "closed_monotonic_ns": 9223372036854000500,
            "elapsed_ns": 500,
            "basis": "HOST_READ_COMPLETION_NOT_DEVICE_TIMESTAMP",
            "transaction_timing_available": True,
        },
        "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
        "physical_authority": False,
        "arm_connected": False,
        "installed_firmware_proven_by_packet": False,
    }


def observation(state="DEENERGIZED"):
    return {
        "schema": "rocell.synthetic_final_power_observation.v1",
        "origin": "SYNTHETIC_REHEARSAL",
        "observation_kind": "INDEPENDENT_POST_CAMPAIGN_FIXTURE",
        "observer_id": "synthetic-observer-a",
        "observed_power_state": state,
        "observed_after_worker": True,
        "permit_sha256": "7" * 64,
        "feedback_evidence_sha256": "8" * 64,
        "observation_sha256": "9" * 64,
        "physical_observation": False,
        "serial_close_used_to_infer_power": False,
    }


def projection():
    value = commissioning()
    feedback = report("feedback_only_connection")
    feedback["meaning"] = "Retained incapable one-shot feedback; no physical release."
    feedback["safe_summary"] = safe_summary()
    feedback["final_power_observation"] = None
    value["arm_feedback_evaluation"] = feedback
    return value


def render(value):
    result = browser(value)
    console = terminal(value)
    assert result["status"] == "Local service connected"
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert result["controls"] == browser(commissioning())["controls"]
    return result["text"], console


def test_valid_packet_and_failed_cleanup_are_separate_and_never_imply_power_off():
    value = projection()
    summary = value["arm_feedback_evaluation"]["safe_summary"]
    summary.update(
        worker_outcome="FAILED_UNCERTAIN",
        serial_cleanup_confirmed=False,
        feedback_receipt_valid=False,
        effect_uncertain=True,
    )
    summary["api_counts"]["closes_confirmed"] = 0
    summary["cleanup_errors"] = [
        {"code": "SERIAL_CLOSE_FAILED", "phase": "CLOSING", "error_type": "OSError"}
    ]
    page, console = render(value)
    assert "VALID SYNTHETIC RESPONSE" in page and "VALID_SYNTHETIC_RESPONSE" in console
    assert (
        "SERIAL CLEANUP NOT CONFIRMED" in page
        and "SERIAL_CLEANUP_NOT_CONFIRMED" in console
    )
    assert (
        "FINAL POWER OBSERVATION MISSING" in page
        and "FINAL_POWER_OBSERVATION_MISSING" in console
    )
    for output in (page, console):
        assert "Technical response" in output and "Serial cleanup" in output
        assert "Packet validity can be true even when close/cleanup failed" in output
        assert "not a DC disconnect" in output
        assert "Independent synthetic final-power observation" in output
        assert "firmware qualification" in output


def test_successful_serial_cleanup_without_observer_still_has_unknown_final_power():
    page, console = render(projection())
    assert "SERIAL API CLEANUP CONFIRMED" in page
    assert "SERIAL_API_CLEANUP_CONFIRMED" in console
    assert "UNKNOWN REQUIRES SEPARATE OBSERVATION" in page
    assert "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in console
    assert "SYNTHETIC DEENERGIZED OBSERVATION ONLY" not in page
    assert "SYNTHETIC_DEENERGIZED_OBSERVATION_ONLY" not in console


@pytest.mark.parametrize("state", ["DEENERGIZED", "ENERGIZED", "UNKNOWN"])
def test_independent_observation_never_rewrites_worker_power_or_releases_hardware(
    state,
):
    value = projection()
    value["arm_feedback_evaluation"]["final_power_observation"] = observation(state)
    page, console = render(value)
    assert "UNKNOWN REQUIRES SEPARATE OBSERVATION" in page
    assert "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in console
    for output in (page, console):
        assert "synthetic-observer-a" in output
        assert "7" * 64 in output and "8" * 64 in output and "9" * 64 in output
        assert "not a measurement of real power" in output
        assert "does not rewrite the worker's UNKNOWN state" in output
        assert "cannot clear it or authorize another attempt" in output
    if state == "DEENERGIZED":
        assert "SYNTHETIC DEENERGIZED OBSERVATION ONLY" in page
        assert "SYNTHETIC_DEENERGIZED_OBSERVATION_ONLY" in console
    else:
        assert "FINAL POWER OBSERVATION HOLD" in page
        assert "FINAL_POWER_OBSERVATION_HOLD" in console


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema": "unreviewed"},
        {"origin": "PHYSICAL"},
        {"observation_kind": "SERIAL_CLOSE"},
        {"observed_after_worker": False},
        {"serial_close_used_to_infer_power": True},
        {"physical_observation": True},
        {"observed_power_state": "OFF"},
        {"observation_sha256": None},
        {"observer_id": "operator\x1b[2J"},
    ],
)
def test_invalid_observer_summary_cannot_appear_as_deenergized_observation(mutation):
    value = projection()
    observed = observation()
    observed.update(mutation)
    value["arm_feedback_evaluation"]["final_power_observation"] = observed
    page, console = render(value)
    assert "FINAL POWER OBSERVATION NOT VERIFIED" in page
    assert "FINAL_POWER_OBSERVATION_NOT_VERIFIED" in console
    assert "SYNTHETIC DEENERGIZED OBSERVATION ONLY" not in page
    assert "SYNTHETIC_DEENERGIZED_OBSERVATION_ONLY" not in console


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema": "wrong"},
        {"binding_sha256": None},
        {"worker_outcome": "PASS"},
        {"technical_response_valid": "true"},
        {"serial_cleanup_confirmed": 1},
        {"physical_authority": True},
        {"arm_connected": True},
        {"installed_firmware_proven_by_packet": True},
        {"final_power_state": "DEENERGIZED"},
        {"api_counts": {}},
        {"cleanup_errors": [None]},
        {
            "primary_error": {
                "code": "ERROR",
                "phase": "OPEN",
                "error_type": "Error",
                "message": "NEVER_RENDER_RAW_MESSAGE",
            }
        },
        {
            "cleanup_errors": [
                {"code": "CLOSE_FAILED", "phase": "CLOSE", "error_type": "Error"}
            ]
            * 9
        },
    ],
)
def test_invalid_safe_summary_never_infers_packet_or_cleanup_success(mutation):
    value = projection()
    value["arm_feedback_evaluation"]["safe_summary"].update(mutation)
    page, console = render(value)
    for output in (page, console):
        assert "Safe serial summary is missing or invalid" in output
        assert "NEVER_RENDER_RAW_MESSAGE" not in output
    assert (
        "VALID SYNTHETIC RESPONSE" not in page
        and "VALID_SYNTHETIC_RESPONSE" not in console
    )
    assert (
        "SERIAL API CLEANUP CONFIRMED" not in page
        and "SERIAL_API_CLEANUP_CONFIRMED" not in console
    )


def test_only_whitelisted_safe_fields_render_not_raw_wire_or_generic_check_payloads():
    value = projection()
    feedback = value["arm_feedback_evaluation"]
    for check in feedback["checks"]:
        check["observed"] = {"raw_wire_hex": "NEVER_RENDER_CHECK_BYTES"}
    feedback["provenance"]["raw_packet"] = "NEVER_RENDER_PROVENANCE_BYTES"
    feedback["raw_receipt"] = "NEVER_RENDER_RAW_RECEIPT"
    summary = feedback["safe_summary"]
    summary["raw_serial_bytes"] = "NEVER_RENDER_SUMMARY_BYTES"
    summary["wire"]["response"]["raw_hex"] = "NEVER_RENDER_RESPONSE_HEX"
    summary["port"] = "NEVER_RENDER_RAW_ENDPOINT"
    page, console = render(value)
    for output in (page, console):
        assert "NEVER_RENDER_" not in output
        assert "Simulated serial API counters" in output
        assert "Retained wire hashes and counts" in output
        assert "3" * 64 in output and "5" * 64 in output and "6" * 64 in output
        assert "nominal" in output.lower()


def test_unsafe_absolute_timestamps_are_omitted_and_omission_count_is_not_rounded():
    value = projection()
    summary = value["arm_feedback_evaluation"]["safe_summary"]
    summary["wire"]["unexpected"]["unretained_bytes"] = 2**63 - 1
    page, console = render(value)
    assert "NOT EXACT IN BROWSER" in page and "NOT_EXACT_IN_DISPLAY" in console
    for output in (page, console):
        assert "922337203685" not in output
        assert "Absolute monotonic timestamps stay in retained evidence" in output


@pytest.mark.parametrize(
    "field,value",
    [("elapsed_ns", 2**63 - 1), ("elapsed_ns", True), ("basis", "DEVICE_SAMPLE_CLOCK")],
)
def test_invalid_timing_does_not_appear_as_verified_feedback_summary(field, value):
    data = projection()
    data["arm_feedback_evaluation"]["safe_summary"]["timing"][field] = value
    page, console = render(data)
    assert "Safe serial summary is missing or invalid" in page
    assert "Safe serial summary is missing or invalid" in console


@pytest.mark.parametrize("value", [None, False, [], "invalid"])
def test_missing_or_wrong_projection_never_dispatches_or_crashes(value):
    data = commissioning()
    data["arm_feedback_evaluation"] = value
    page, console = render(data)
    if value is None:
        assert "Retained synthetic feedback campaign" not in page
        assert "Retained synthetic feedback campaign" not in console
    else:
        assert "Safe serial summary is missing or invalid" in page
        assert "Safe serial summary is missing or invalid" in console


@pytest.mark.parametrize(
    "scenario_name",
    ["nominal", "close-failed", "boot-bytes", "short-write", "malformed-response"],
)
def test_actual_worker_lossless_evidence_safe_summary_renders_without_raw_bytes(
    monkeypatch, scenario_name
):
    from rocell.providers.windows import arm_feedback_worker as worker
    from test_rehearsal_arm_feedback_evidence import run as run_incapable, retain

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Presentation tests must not create or open a hardware serial backend"
        )

    monkeypatch.setattr(worker.WindowsPySerialBackend, "require_available", forbidden)
    monkeypatch.setattr(worker.WindowsPySerialBackend, "create_closed", forbidden)
    scenarios = {
        "nominal": worker.IncapableSerialScenario(),
        "close-failed": worker.IncapableSerialScenario(fail_at=("close",)),
        "boot-bytes": worker.IncapableSerialScenario(
            preexisting_bytes=b"secret-boot-UI-test\n"
        ),
        "short-write": worker.IncapableSerialScenario(short_write_count=1),
        "malformed-response": worker.IncapableSerialScenario(
            response_bytes=b"secret-malformed-UI-test\n"
        ),
    }
    request, result, _ = run_incapable(scenarios[scenario_name])
    evidence = retain(request, result)
    value = projection()
    value["arm_feedback_evaluation"]["safe_summary"] = evidence.safe_summary()
    value["arm_feedback_evaluation"]["evaluation_sha256"] = evidence.evidence_sha256
    page, console = render(value)
    for output in (page, console):
        assert "Safe serial summary is missing or invalid" not in output
        assert "Retained wire hashes and counts" in output
        assert evidence.evidence_sha256 in output
        assert "secret-boot-UI-test" not in output
        assert "secret-malformed-UI-test" not in output
        assert '{"T":105}' not in output
        assert "COM404" not in output
    if scenario_name in ("nominal", "close-failed"):
        assert "VALID SYNTHETIC RESPONSE" in page
        assert "VALID_SYNTHETIC_RESPONSE" in console
    if scenario_name == "close-failed":
        assert "SERIAL CLEANUP NOT CONFIRMED" in page
        assert "SERIAL_CLEANUP_NOT_CONFIRMED" in console
    assert "UNKNOWN REQUIRES SEPARATE OBSERVATION" in page
    assert "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in console
