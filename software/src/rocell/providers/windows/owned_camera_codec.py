"""One closed incapable camera protocol, not a pluggable process codec registry."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
from typing import Any

from ._owned_camera_fixture import (
    FRAME_BYTES,
    CONFIG_PAYLOAD_SCHEMA,
    CONFIG_REQUEST_SCHEMA,
    CONFIG_RESULT_SCHEMA,
    FIXTURE_CONTROL_UNITS,
    MODE,
    PAYLOAD_SCHEMA,
    PROVENANCE,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    SCENARIOS,
    TEMPLATE_BYTES,
    canonical,
    closed,
    digest,
    fixture_control_observations,
    payload_protocols,
    payload_working_directory,
    require,
    validate_payload,
    validate_control_observations,
)

CAMERA_FIXTURE_PATH = Path(__file__).with_name("_owned_camera_fixture.py")


def validate_camera_registration(registration: Any, request: Any) -> dict[str, Any]:
    """Pure exact membership checks before backend creation or admission."""
    from .owned_worker_process import decode_owned_json

    payload = validate_payload(
        decode_owned_json(request.payload_json, maximum=60 * 1024)
    )
    camera = payload["camera_request"]
    request_schema, result_schema = payload_protocols(payload)
    require(
        registration.worker_id == "incapable-owned-camera"
        and registration.composition == "INCAPABLE_PROCESS_FIXTURE"
        and registration.request_schema == request_schema
        and registration.result_schema == result_schema,
        "CAMERA_CLOSED_PROTOCOL",
    )
    require(
        registration.executable.path
        == Path(getattr(sys, "_base_executable", sys.executable))
        and registration.argv
        == ("-I", "-S", str(CAMERA_FIXTURE_PATH), payload["scenario"]),
        "CAMERA_CLOSED_COMMAND",
    )
    require(
        camera["campaign_id"] == request.attempt_id
        and camera["source_sha256"] == request.source_sha256
        and camera["binding"]["binding_sha256"] == request.selected_identity_sha256,
        "CAMERA_CONTEXT_DRIFT",
    )
    require(
        registration.working_directory == payload_working_directory(payload),
        "CAMERA_OUTPUT_PIN",
    )
    require(
        payload["native_arguments"][0] == str(CAMERA_FIXTURE_PATH),
        "CAMERA_FIXED_SCRIPT",
    )
    require(
        len(registration.package_files) == len(payload["templates"]) + 1,
        "CAMERA_PACKAGE_MEMBERSHIP",
    )
    script, *templates = registration.package_files
    require(
        script.path == CAMERA_FIXTURE_PATH and script.sha256 == camera["helper_sha256"],
        "CAMERA_SCRIPT_PIN",
    )
    actual = [{**asdict(item), "path": str(item.path)} for item in templates]
    require(actual == payload["templates"], "CAMERA_TEMPLATE_PIN")
    budget = registration.budget
    require(
        camera["budget"]["duration_ms"]
        < budget.run_timeout_ms
        <= camera["budget"]["duration_ms"] + 5000,
        "CAMERA_PROCESS_DEADLINE",
    )
    require(
        budget.stdout_bytes + budget.stderr_bytes <= 256 * 1024,
        "CAMERA_COMBINED_PIPE_BUDGET",
    )
    return payload


def validate_camera_result(
    result: Any,
    *,
    payload: dict[str, Any],
    request_sha256: str,
    attempt_id: str,
    returncode: Any,
) -> None:
    """Validate the bound outer envelope; full native parsing remains in client.

    Native failures with valid envelopes remain substantive evidence. A modeled
    wrong endpoint intentionally reaches the client's independent identity check.
    No filesystem reads or native parser activation occur here.
    """
    validate_payload(payload)
    closed(
        result,
        {
            "schema",
            "request_sha256",
            "attempt_id",
            "physical_authority",
            "fixture_result",
        },
    )
    require(
        result["schema"] == payload_protocols(payload)[1]
        and result["request_sha256"] == request_sha256
        and result["attempt_id"] == attempt_id
        and result["physical_authority"] is False,
        "CAMERA_RESULT_BINDING",
    )
    fixture = result["fixture_result"]
    closed(
        fixture,
        {
            "scenario",
            "provenance",
            "camera_request_sha256",
            "template_sha256s",
            "native_receipt",
        },
    )
    require(
        fixture["scenario"] == payload["scenario"]
        and fixture["provenance"] == PROVENANCE
        and fixture["camera_request_sha256"] == digest(payload["camera_request"])
        and fixture["template_sha256s"]
        == [item["sha256"] for item in payload["templates"]],
        "CAMERA_RESULT_CONTEXT",
    )
    native = fixture["native_receipt"]
    closed(
        native,
        {
            "schema",
            "operation",
            "status",
            "reason_code",
            "selected_endpoint",
            "devices",
            "modes",
            "requested_mode",
            "observed_mode",
            "controls",
            "frames",
            "counts",
            "cleanup",
            "limitations",
        },
    )
    require(
        native["schema"] == "rocell.windows_camera.v1"
        and native["operation"] == payload["camera_request"]["operation"]
        and native["status"] in {"OK", "FAILED"}
        and type(returncode) is int
        and returncode == (0 if native["status"] == "OK" else 1),
        "CAMERA_NATIVE_EXIT",
    )
    require(
        type(native["limitations"]) is list and PROVENANCE in native["limitations"],
        "CAMERA_NATIVE_PROVENANCE",
    )
    if payload["schema"] == CONFIG_PAYLOAD_SCHEMA:
        validate_control_observations(native["controls"])
    else:
        require(native["controls"] == [], "CAMERA_LEGACY_HAS_CONTROLS")
