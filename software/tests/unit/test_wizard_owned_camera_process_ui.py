"""Cached process presentation only; no child, camera, artifact or M1 I/O."""

import pytest

from test_arrival_wizard_arm_power_ui import terminal
from test_arrival_wizard_device_selection_ui import browser as action_browser
from test_arrival_wizard_reopen_ui import ReopenService, browser, commissioning
from test_arrival_wizard_terminal import action, dispatched, run


def summary():
    """Display fixture, not evidence of a child execution or dataset commit."""
    return {
        "schema": "rocell.rehearsal_owned_camera_summary.v1",
        "status": "RETAINED_COMPLETE_REHEARSAL",
        "evidence_sha256": "a" * 64,
        "binding": {
            "session_id": "session-fixture",
            "attempt_id": "attempt-fixture",
            "source_sha256": "b" * 64,
            "permit_sha256": "c" * 64,
            "operation_sha256": "d" * 64,
            "selected_identity_sha256": "e" * 64,
            "settings_epoch": "f" * 64,
        },
        "process": {
            "status": "SUCCEEDED",
            "created": True,
            "resumed": True,
            "tree_exit_confirmed": True,
            "cleanup_errors": [],
            "cleanup_error_count": 0,
            "cleanup_errors_omitted": 0,
            "primary_error": None,
            "returncode": 0,
            "stdout_bytes": 2400,
            "stderr_bytes": 0,
            "request_sha256": "1" * 64,
        },
        "native": {
            "receipt_valid": True,
            "status": "OK",
            "cleanup_confirmed": True,
            "counts": {
                "source_activation_attempts": 1,
                "source_opened": 1,
                "source_shutdown_attempts": 1,
                "control_set_attempts": 0,
                "samples_received": 2,
                "frames_written": 2,
            },
            "frame_count": 2,
        },
        "capture": {
            "metadata_binding_valid": True,
            "manifest_sha256": "2" * 64,
            "plan_sha256": "3" * 64,
            "envelope_sha256": "4" * 64,
            "source_contract_sha256": "5" * 64,
            "frames": 2,
            "logical_bytes": 79_847_424,
        },
        "blockers": [],
        "device_cleanup_proven": False,
        "physical_authority": False,
        "qualified": False,
        "meaning": "Source-derived incapable fixture; no received camera evidence.",
    }


def projection(value):
    result = commissioning()
    result["camera_process"] = value
    return result


def render(value):
    displayed = projection(value)
    result = browser(displayed)
    console = terminal(displayed)
    assert result["status"] == "Local service connected"
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert result["controls"] == browser(commissioning())["controls"]
    return result["text"], console


def test_complete_rehearsal_keeps_process_native_and_content_claims_separate():
    page, console = render(summary())
    for output in (page, console):
        assert "Contained camera-process rehearsal" in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "Actual child-process containment and cleanup" in output
        assert "Synthetic native receipt and cleanup" in output
        assert "Retained frame metadata references" in output
        assert "not physical camera frames" in output
        assert "Process exit is not physical device cleanup" in output
        assert "Metadata binding is not file-content verification" in output
        assert "This card does not load a preview" in output
        assert "No automatic discovery, replay, process restart" in output
        for digest in "abcdef12345":
            assert digest * 64 in output
        assert "79847424" in output
        assert "session-fixture" in output and "attempt-fixture" in output
    assert "RETAINED COMPLETE REHEARSAL" in page
    assert "RETAINED_COMPLETE_REHEARSAL" in console


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_successful_native_receipt_does_not_hide_failed_process(status):
    value = summary()
    value["status"] = "RETAINED_INCOMPLETE_REHEARSAL"
    value["process"].update(status=status, primary_error="CHILD_HELD", returncode=1)
    value["blockers"] = ["OWNED_PROCESS_NOT_COMPLETE"]
    page, console = render(value)
    for output in (page, console):
        assert (
            "An OK receipt cannot override a failed, cancelled or timed-out process"
            in output
        )
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "RETAINED COMPLETE REHEARSAL" not in output
        assert "RETAINED_COMPLETE_REHEARSAL" not in output
    assert status.replace("_", " ") in page and status in console


def test_process_cleanup_and_omitted_errors_remain_visible_and_bounded():
    value = summary()
    value["status"] = "RETAINED_INCOMPLETE_REHEARSAL"
    value["process"].update(
        status="FAILED",
        tree_exit_confirmed=False,
        cleanup_errors=["CLEANUP_EXCEPTION:OSError", "CLOSE_FAILED:job"] * 8,
        cleanup_error_count=19,
        cleanup_errors_omitted=3,
        primary_error="PROCESS_CLEANUP_UNCERTAIN",
        returncode=None,
    )
    value["native"]["cleanup_confirmed"] = False
    page, console = render(value)
    assert "cleanup errors omitted" in page and '"cleanup_errors_omitted": 3' in console
    assert "19" in page and "19" in console
    assert "PROCESS CLEANUP UNCERTAIN" in page
    assert "PROCESS_CLEANUP_UNCERTAIN" in console
    assert "CLEANUP_EXCEPTION:OSError" in page and "CLOSE_FAILED:job" in console


@pytest.mark.parametrize("missing", ["process", "native", "capture"])
def test_incomplete_summary_can_honestly_retain_missing_component(missing):
    value = summary()
    value["status"] = "RETAINED_INCOMPLETE_REHEARSAL"
    value[missing] = None
    page, console = render(value)
    assert "CAMERA PROCESS NOT VERIFIED" not in page
    assert "CAMERA_PROCESS_NOT_VERIFIED" not in console
    assert "MISSING" in page and "MISSING" in console


def test_incomplete_zero_frame_metadata_is_explicitly_held_not_discarded():
    value = summary()
    value["status"] = "RETAINED_INCOMPLETE_REHEARSAL"
    value["capture"].update(frames=0, logical_bytes=0, metadata_binding_valid=False)
    value["blockers"] = ["CAPTURE_METADATA_BINDING_UNVERIFIED"]
    page, console = render(value)
    assert "CAMERA PROCESS NOT VERIFIED" not in page
    assert "CAMERA_PROCESS_NOT_VERIFIED" not in console
    assert "CAPTURE_METADATA_BINDING_UNVERIFIED" in page
    assert "CAPTURE_METADATA_BINDING_UNVERIFIED" in console


def test_display_text_is_plain_data_not_markup_or_a_new_action():
    value = summary()
    value["meaning"] = '<img src="camera" onerror="dispatch()"> incapable fixture'
    page, console = render(value)
    for output in (page, console):
        assert value["meaning"] in output


@pytest.mark.parametrize("page", ["camera", "arm", "overview"])
def test_process_card_does_not_replace_camera_or_arm_connection_status(page):
    snapshot = ReopenService(projection(summary())).view()
    result = action_browser({}, page, snapshot=snapshot)
    assert "Contained camera-process rehearsal" not in result["text"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]


@pytest.mark.parametrize("value", [None, "absent", [], {}, False])
def test_absent_or_invalid_summary_never_looks_like_completed_capture(value):
    page, console = render(value)
    if value is None:
        assert "Contained camera-process rehearsal" not in page
        assert "Contained camera-process rehearsal" not in console
    else:
        assert "CAMERA PROCESS NOT VERIFIED" in page
        assert "CAMERA_PROCESS_NOT_VERIFIED" in console


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema",), "unreviewed"),
        (("status",), "CAMERA_CONNECTED"),
        (("physical_authority",), True),
        (("qualified",), True),
        (("device_cleanup_proven",), True),
        (("evidence_sha256",), "A" * 64),
        (("meaning",), "x" * 513),
        (("meaning",), "é" * 257),
        (("meaning",), "bad\x1b[2J"),
        (("binding", "session_id"), "x" * 97),
        (("binding", "attempt_id"), "C:/raw path"),
        (("binding", "settings_epoch"), None),
        (("process", "status"), "READY"),
        (("process", "created"), 1),
        (("process", "created"), False),
        (("process", "tree_exit_confirmed"), False),
        (("process", "cleanup_error_count"), 1),
        (("process", "cleanup_errors_omitted"), True),
        (("process", "cleanup_errors"), ["FAILED"] * 17),
        (("process", "primary_error"), "x" * 129),
        (("process", "stdout_bytes"), 32769),
        (("process", "stderr_bytes"), 8193),
        (("process", "returncode"), 2**53),
        (("process", "request_sha256"), "m" * 64),
        (("native", "receipt_valid"), "true"),
        (("native", "status"), "CONNECTED"),
        (("native", "frame_count"), 33),
        (("native", "counts", "source_opened"), 2),
        (("native", "counts", "control_set_attempts"), 7),
        (("native", "counts", "samples_received"), 100001),
        (("native", "counts", "frames_written"), 33),
        (("capture", "frames"), 0),
        (("capture", "frames"), 3),
        (("capture", "metadata_binding_valid"), False),
        (("capture", "logical_bytes"), 2**53),
        (("capture", "manifest_sha256"), None),
        (("blockers",), ["STILL_HELD"]),
        (("blockers",), ["FAILED"] * 17),
    ],
)
def test_inconsistent_or_oversized_summary_is_not_presented_as_verified(
    path, replacement
):
    value = summary()
    item = value
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = replacement
    page, console = render(value)
    assert "CAMERA PROCESS NOT VERIFIED" in page
    assert "CAMERA_PROCESS_NOT_VERIFIED" in console
    assert "RETAINED COMPLETE REHEARSAL" not in page
    assert "RETAINED_COMPLETE_REHEARSAL" not in console


@pytest.mark.parametrize("section", [None, "binding", "process", "native", "capture"])
def test_unknown_fields_do_not_leak_into_generic_facts(section):
    value = summary()
    item = value if section is None else value[section]
    item["raw_path"] = "NEVER_RENDER_RAW_CHILD_OUTPUT_OR_PATH"
    page, console = render(value)
    for output in (page, console):
        assert "NEVER_RENDER_RAW_CHILD_OUTPUT_OR_PATH" not in output
    assert "CAMERA PROCESS NOT VERIFIED" in page
    assert "CAMERA_PROCESS_NOT_VERIFIED" in console


def campaign_action():
    entry = action(
        "rehearsal_owned_camera_campaign",
        fields=[
            {
                "name": "frame_count",
                "label": "Frames",
                "type": "number",
                "required": True,
                "min": 1,
                "max": 4,
                "step": 1,
                "default": 1,
            },
            {
                "name": "fault",
                "label": "Fixed fixture fault",
                "type": "select",
                "required": True,
                "default": "none",
                "options": [
                    {"value": value, "label": value}
                    for value in (
                        "none",
                        "identity-mismatch",
                        "cleanup-uncertain",
                        "child-timeout",
                        "malformed-result",
                    )
                ],
            },
        ],
    )
    entry["section"] = "commissioning"
    return entry


def test_generic_campaign_preview_still_requires_separate_exact_execution():
    service = ReopenService(projection(summary()))
    snapshot = service.view()
    snapshot["actions"] = [campaign_action()]
    values = {"frame_count": 2, "fault": "none"}
    options = dict(
        snapshot=snapshot,
        prepare=True,
        action="rehearsal_owned_camera_campaign",
        values=values,
    )
    preview = action_browser({}, "commissioning", **options)
    assert [row["path"] for row in preview["requests"]] == ["/api/view", "/api/prepare"]
    assert preview["requests"][1]["body"]["input"] == values
    assert preview["dialogOpen"]
    executed = action_browser({}, "commissioning", execute=True, **options)
    assert [row["path"] for row in executed["requests"]].count("/api/execute") == 1


@pytest.mark.parametrize("confirmation", ["", "no", "yes to all hardware"])
def test_terminal_campaign_does_not_infer_confirmation(confirmation):
    service = ReopenService(projection(summary()))
    service.actions = [campaign_action()]
    code, _, _ = run(
        service, ["rehearsal_owned_camera_campaign", "2", "none", confirmation, "quit"]
    )
    assert code == 0 and len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")


def test_actual_pure_producer_missing_results_render_as_hold_without_provider_io(
    monkeypatch,
):
    from rocell.application.rehearsal_owned_camera_evidence import (
        retain_owned_camera_evidence,
        verify_owned_camera_evidence,
    )
    from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker

    def forbidden(*args, **kwargs):
        raise AssertionError("Cached evidence retention/display cannot launch a child")

    monkeypatch.setattr(OwnedWindowsWorker, "run", forbidden)
    binding = summary()["binding"]
    evidence = retain_owned_camera_evidence(
        binding=binding,
        activation_request=None,
        process_result=None,
        native_receipt=None,
        capture=None,
        error={
            "code": "CANCELLED_PRE_DISPATCH",
            "message": "No child result was produced.",
        },
    )
    verified = verify_owned_camera_evidence(evidence.payload, binding)
    view = verified.view()
    assert view["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert (
        view["process"] is None and view["native"] is None and view["capture"] is None
    )
    page, console = render(view)
    for output in (page, console):
        assert evidence.evidence_sha256 in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "CALLER_REPORTED_ERROR" in output
    assert "CAMERA PROCESS NOT VERIFIED" not in page
    assert "CAMERA_PROCESS_NOT_VERIFIED" not in console


@pytest.mark.parametrize("count", [1, 4])
def test_actual_typed_nominal_producer_verifier_matches_both_renderers(count):
    from test_rehearsal_owned_camera_evidence import complete_inputs
    from rocell.application.rehearsal_owned_camera_evidence import (
        retain_owned_camera_evidence,
        verify_owned_camera_evidence,
    )

    # Typed full-resolution metadata from the real producer, not an assertion
    # that this presentation test launched a process or generated/verified pixels.
    inputs = complete_inputs(count)
    artifact = retain_owned_camera_evidence(**inputs)
    view = verify_owned_camera_evidence(artifact.payload, inputs["binding"]).view()
    assert view["status"] == "RETAINED_COMPLETE_REHEARSAL" and view["blockers"] == []
    assert view["capture"]["frames"] == count
    page, console = render(view)
    assert "CAMERA PROCESS NOT VERIFIED" not in page
    assert "CAMERA_PROCESS_NOT_VERIFIED" not in console
    for output in (page, console):
        assert artifact.evidence_sha256 in output
        assert view["capture"]["manifest_sha256"] in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "Metadata binding is not file-content verification" in output
