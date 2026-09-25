"""Closed, explicitly incapable camera-wire child; standard library only.

The process never imports a camera/serial provider. It reads only the exact
parent-pinned GRAY8 templates and writes finite YUY2 files in its assigned cwd.
Shared pure validators below are also used by the parent closed codec. They do
not open files. Physical-looking native counters are modeled, never observed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any

REQUEST_SCHEMA = "rocell.owned_camera_fixture_request.v1"
RESULT_SCHEMA = "rocell.owned_camera_fixture_result.v1"
PAYLOAD_SCHEMA = "rocell.owned_camera_fixture_payload.v1"
CONFIG_REQUEST_SCHEMA = "rocell.owned_camera_fixture_request.v2"
CONFIG_RESULT_SCHEMA = "rocell.owned_camera_fixture_result.v2"
CONFIG_PAYLOAD_SCHEMA = "rocell.owned_camera_fixture_payload.v2"
PROVENANCE = "INCAPABLE_CAMERA_PROCESS_FIXTURE"
SCENARIOS = frozenset(
    {
        "nominal",
        "identity-mismatch",
        "cleanup-uncertain",
        "child-timeout",
        "malformed-result",
        "control-readback-drift",
    }
)
TEMPLATE_WIDTH, TEMPLATE_HEIGHT = 2736, 1824
TEMPLATE_BYTES = 4_990_464
FRAME_BYTES = 39_923_712
MODE = {
    "width": 5472,
    "height": 3648,
    "fps_numerator": 9,
    "fps_denominator": 1,
    "subtype": "YUY2",
    "stride_bytes": 10944,
}
FIXTURE_CONTROL_UNITS = "MODELED_INTEGER_DRIVER_UNITS_NOT_RECEIVED_HARDWARE"
# Closed source-model descriptors, NOT reported properties of the purchased
# camera. Tuple rows are immutable; public observations are always fresh copies.
_CONTROL_RANGES = (
    ("exposure", -13, -1, 1, -6, 3),
    ("gain", 0, 255, 1, 16, 2),
    ("white_balance", 2800, 6500, 100, 4500, 3),
    ("brightness", -64, 64, 1, 0, 2),
    ("contrast", 0, 100, 1, 50, 2),
    ("saturation", 0, 100, 1, 50, 2),
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")


def require(value: bool, code: str) -> None:
    if not value:
        raise ValueError(code)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value: Any, low: int, high: int) -> None:
    require(type(value) is int and low <= value <= high, "CAMERA_INTEGER")


def sha(value: Any) -> None:
    require(type(value) is str and bool(_SHA.fullmatch(value)), "CAMERA_SHA256")


def closed(value: Any, keys: set[str]) -> None:
    require(type(value) is dict and set(value) == keys, "CAMERA_SCHEMA")


def fixture_control_observations() -> tuple[dict[str, Any], ...]:
    """Owned native-shaped model rows; no inventory/activation or cached mutation."""
    return tuple(
        {
            "control_id": name,
            "minimum": low,
            "maximum": high,
            "step": step,
            "default": default,
            "capability_flags": flags,
            "value": default,
            "flags": 2,
            "unit": FIXTURE_CONTROL_UNITS,
        }
        for name, low, high, step, default, flags in _CONTROL_RANGES
    )


def validate_control_settings(controls: Any) -> None:
    require(type(controls) is list and len(controls) <= 6, "CAMERA_CONTROLS")
    descriptors = {row["control_id"]: row for row in fixture_control_observations()}
    seen = set()
    for setting in controls:
        closed(setting, {"control_id", "value", "mode"})
        name = setting["control_id"]
        require(
            type(name) is str and name in descriptors and name not in seen,
            "CAMERA_CONTROL_ID",
        )
        seen.add(name)
        descriptor = descriptors[name]
        integer(setting["value"], descriptor["minimum"], descriptor["maximum"])
        require(
            (setting["value"] - descriptor["minimum"]) % descriptor["step"] == 0,
            "CAMERA_CONTROL_STEP",
        )
        require(
            type(setting["mode"]) is str and setting["mode"] in {"auto", "manual"},
            "CAMERA_CONTROL_MODE",
        )
        flag = 1 if setting["mode"] == "auto" else 2
        require(
            bool(descriptor["capability_flags"] & flag), "CAMERA_CONTROL_CAPABILITY"
        )


def validate_control_observations(observations: Any) -> None:
    """Reject unknown flags/ranges; drift may remain valid but mismatched state."""
    require(
        type(observations) is list and len(observations) == 6, "CAMERA_CONTROL_REPORT"
    )
    for actual, expected in zip(observations, fixture_control_observations()):
        closed(actual, set(expected))
        require(
            all(
                type(actual[key]) is type(expected[key])
                and actual[key] == expected[key]
                for key in expected
                if key not in {"value", "flags"}
            ),
            "CAMERA_CONTROL_DESCRIPTOR_DRIFT",
        )
        integer(actual["value"], expected["minimum"], expected["maximum"])
        require(
            (actual["value"] - expected["minimum"]) % expected["step"] == 0,
            "CAMERA_CONTROL_READBACK_STEP",
        )
        require(
            type(actual["flags"]) is int
            and actual["flags"] in {1, 2}
            and bool(actual["flags"] & expected["capability_flags"]),
            "CAMERA_CONTROL_READBACK_FLAGS",
        )


def fixture_readback(
    controls: list[dict[str, Any]], *, drift: bool = False
) -> list[dict[str, Any]]:
    validate_control_settings(controls)
    observed = list(fixture_control_observations())
    by_name = {row["control_id"]: row for row in observed}
    for setting in controls:
        row = by_name[setting["control_id"]]
        row["flags"] = 1 if setting["mode"] == "auto" else 2
        # Auto readback intentionally need not equal the requested numeric value.
        # This models reported state, not an exposure/white-balance algorithm.
        row["value"] = (
            setting["value"] if setting["mode"] == "manual" else row["default"]
        )
    if drift:
        require(bool(controls), "CAMERA_DRIFT_REQUIRES_REQUESTED_CONTROL")
        setting = controls[0]
        row = by_name[setting["control_id"]]
        if setting["mode"] == "auto":
            row["flags"] = 2
        else:
            row["value"] = (
                row["minimum"]
                if row["value"] != row["minimum"]
                else row["minimum"] + row["step"]
            )
    validate_control_observations(observed)
    return observed


def payload_working_directory(payload: dict[str, Any]) -> Path:
    return assigned_path(
        payload["working_directory"]
        if payload["schema"] == CONFIG_PAYLOAD_SCHEMA
        else payload["camera_request"]["output_directory"]
    )


def payload_protocols(payload: dict[str, Any]) -> tuple[str, str]:
    return (
        (CONFIG_REQUEST_SCHEMA, CONFIG_RESULT_SCHEMA)
        if payload["schema"] == CONFIG_PAYLOAD_SCHEMA
        else (REQUEST_SCHEMA, RESULT_SCHEMA)
    )


def assigned_path(value: Any) -> Path:
    require(
        type(value) is str
        and 0 < len(value) <= 4096
        and not any(ord(c) < 32 or ord(c) == 127 for c in value),
        "CAMERA_PATH",
    )
    path = Path(value)
    require(
        path.is_absolute()
        and path != Path(path.anchor)
        and ".." not in path.parts
        and not value.startswith(("\\\\", "//")),
        "CAMERA_PATH",
    )
    return path


def validate_payload(payload: Any) -> dict[str, Any]:
    """Exact finite fixture contract; no path reads or device effects."""
    require(type(payload) is dict, "CAMERA_SCHEMA")
    configured = payload.get("schema") == CONFIG_PAYLOAD_SCHEMA
    closed(
        payload,
        {
            "schema",
            "provenance",
            "scenario",
            "camera_request",
            "native_arguments",
            "templates",
        }
        | ({"working_directory"} if configured else set()),
    )
    require(
        payload["schema"] in {PAYLOAD_SCHEMA, CONFIG_PAYLOAD_SCHEMA}
        and payload["provenance"] == PROVENANCE
        and type(payload["scenario"]) is str
        and payload["scenario"] in SCENARIOS,
        "CAMERA_FIXTURE_REQUIRED",
    )
    request = payload["camera_request"]
    closed(
        request,
        {
            "campaign_id",
            "source_sha256",
            "operation",
            "binding",
            "mode",
            "controls",
            "budget",
            "helper_sha256",
            "arguments_sha256",
            "output_directory",
        },
    )
    require(
        type(request["campaign_id"]) is str
        and bool(_ID.fullmatch(request["campaign_id"])),
        "CAMERA_CAMPAIGN_ID",
    )
    for key in ("source_sha256", "helper_sha256", "arguments_sha256"):
        sha(request[key])
    require(
        type(request["operation"]) is str
        and request["operation"] in {"probe", "capture"},
        "CAMERA_OPERATION",
    )
    probe = request["operation"] == "probe"
    validate_control_settings(request["controls"])
    require(
        configured == (probe or bool(request["controls"])), "CAMERA_PROTOCOL_OPERATION"
    )
    require(
        payload["scenario"] != "control-readback-drift" or bool(request["controls"]),
        "CAMERA_DRIFT_REQUIRES_REQUESTED_CONTROL",
    )
    if probe:
        require(
            request["mode"] is None
            and request["output_directory"] is None
            and not request["controls"],
            "CAMERA_PROBE_HAS_CAPTURE_FIELDS",
        )
    binding = request["binding"]
    closed(binding, {"symbolic_link", "endpoint_sha256", "binding_sha256"})
    endpoint = binding["symbolic_link"]
    require(
        type(endpoint) is str
        and 0 < len(endpoint.encode("utf-8")) <= 4096
        and not any(ord(c) < 32 or ord(c) == 127 for c in endpoint),
        "CAMERA_ENDPOINT",
    )
    sha(binding["endpoint_sha256"])
    sha(binding["binding_sha256"])
    require(
        hashlib.sha256(endpoint.encode("utf-8")).hexdigest()
        == binding["endpoint_sha256"],
        "CAMERA_ENDPOINT_HASH",
    )
    if not probe:
        closed(request["mode"], set(MODE))
        require(
            all(
                type(request["mode"][key]) is type(value)
                and request["mode"][key] == value
                for key, value in MODE.items()
            ),
            "CAMERA_FIXED_MODE",
        )
    budget = request["budget"]
    closed(budget, {"duration_ms", "max_frames", "max_frame_bytes", "max_total_bytes"})
    integer(budget["duration_ms"], 100, 55_000)
    integer(budget["max_frames"], 1, 1 if probe else 4)
    # Exact raw quotas prevent a broad camera budget from silently widening the
    # closed fixture's disk effects. Retained datasets have a separate budget.
    integer(budget["max_frame_bytes"], FRAME_BYTES, FRAME_BYTES)
    integer(
        budget["max_total_bytes"],
        FRAME_BYTES * budget["max_frames"],
        FRAME_BYTES * budget["max_frames"],
    )
    output = payload_working_directory(payload)
    if not probe:
        require(
            output == assigned_path(request["output_directory"]),
            "CAMERA_OUTPUT_CWD_DRIFT",
        )
    arguments = payload["native_arguments"]
    require(
        type(arguments) is list
        and len(arguments) == (6 if probe else 24 if request["controls"] else 22)
        and all(type(x) is str and len(x) <= 4096 and "\0" not in x for x in arguments),
        "CAMERA_ARGUMENTS",
    )
    assigned_path(arguments[0])
    expected = [
        arguments[0],
        request["operation"],
        "--endpoint",
        endpoint,
        "--max-ms",
        str(budget["duration_ms"]),
    ]
    if not probe:
        expected += [
            "--width",
            "5472",
            "--height",
            "3648",
            "--fps-n",
            "9",
            "--fps-d",
            "1",
            "--frames",
            str(budget["max_frames"]),
            "--frame-bytes",
            str(FRAME_BYTES),
            "--total-bytes",
            str(budget["max_total_bytes"]),
            "--output",
            str(output),
        ]
    if request["controls"]:
        expected += [
            "--controls",
            ";".join(
                f"{row['control_id']},{row['value']},{row['mode']}"
                for row in request["controls"]
            ),
        ]
    require(arguments == expected, "CAMERA_ARGUMENT_DRIFT")
    argv_hash = hashlib.sha256(
        json.dumps(arguments, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    require(argv_hash == request["arguments_sha256"], "CAMERA_ARGUMENT_HASH")
    templates = payload["templates"]
    require(
        type(templates) is list
        and len(templates) == (0 if probe else budget["max_frames"]),
        "CAMERA_TEMPLATES",
    )
    paths = set()
    for template in templates:
        closed(template, {"path", "sha256", "maximum_bytes"})
        path = assigned_path(template["path"])
        require(
            path not in paths and not path.is_relative_to(output),
            "CAMERA_TEMPLATE_PATH",
        )
        paths.add(path)
        sha(template["sha256"])
        integer(template["maximum_bytes"], TEMPLATE_BYTES, TEMPLATE_BYTES)
    return payload


def validate_envelope(request: Any, scenario: str) -> dict[str, Any]:
    closed(
        request,
        {
            "schema",
            "worker_id",
            "attempt_id",
            "session_id",
            "source_sha256",
            "operation_sha256",
            "selected_identity_sha256",
            "expires_at_monotonic_ns",
            "parent_deadline_monotonic_ns",
            "payload",
            "registration_sha256",
            "request_sha256",
        },
    )
    require(
        request["schema"] in {REQUEST_SCHEMA, CONFIG_REQUEST_SCHEMA},
        "CAMERA_REQUEST_SCHEMA",
    )
    for key in (
        "source_sha256",
        "operation_sha256",
        "selected_identity_sha256",
        "registration_sha256",
        "request_sha256",
    ):
        sha(request[key])
    for key in ("worker_id", "attempt_id", "session_id"):
        require(
            type(request[key]) is str
            and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", request[key])),
            "CAMERA_REQUEST_ID",
        )
    integer(request["expires_at_monotonic_ns"], 1, 2**63 - 1)
    integer(
        request["parent_deadline_monotonic_ns"], 1, request["expires_at_monotonic_ns"]
    )
    body = {key: value for key, value in request.items() if key != "request_sha256"}
    require(digest(body) == request["request_sha256"], "CAMERA_REQUEST_HASH")
    payload = validate_payload(request["payload"])
    require(request["schema"] == payload_protocols(payload)[0], "CAMERA_PROTOCOL_PAIR")
    camera = payload["camera_request"]
    require(
        payload["scenario"] == scenario
        and camera["campaign_id"] == request["attempt_id"]
        and camera["source_sha256"] == request["source_sha256"]
        and camera["binding"]["binding_sha256"] == request["selected_identity_sha256"],
        "CAMERA_CONTEXT_DRIFT",
    )
    return payload


def _decode(raw: bytes) -> dict[str, Any]:
    require(0 < len(raw) <= 64 * 1024, "CAMERA_STDIN_LIMIT")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "CAMERA_DUPLICATE_JSON")
            result[key] = value
        return result

    def bad(_: str) -> Any:
        raise ValueError("CAMERA_NONFINITE_JSON")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)
    nodes = 0

    def bounded(item: Any, depth: int = 0) -> None:
        nonlocal nodes
        nodes += 1
        require(nodes <= 4096 and depth <= 16, "CAMERA_JSON_LIMIT")
        if type(item) is dict:
            for key, child in item.items():
                bounded(key, depth + 1)
                bounded(child, depth + 1)
        elif type(item) is list:
            for child in item:
                bounded(child, depth + 1)
        else:
            require(
                item is None or type(item) in {str, int, bool}, "CAMERA_JSON_SCALAR"
            )

    bounded(value)
    return value


def _regular(path: Path, *, directory: bool = False) -> os.stat_result:
    info = path.lstat()
    require(
        not stat.S_ISLNK(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400,
        "CAMERA_REPARSE_PATH",
    )
    require(
        (
            stat.S_ISDIR(info.st_mode)
            if directory
            else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        ),
        "CAMERA_REGULAR_PATH",
    )
    return info


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in SCENARIOS, "CAMERA_CLOSED_SCENARIO")
    scenario = sys.argv[1]
    request = _decode(sys.stdin.buffer.read(64 * 1024 + 1))
    payload = validate_envelope(request, scenario)
    camera = payload["camera_request"]
    output = payload_working_directory(payload)
    require(Path.cwd() == output, "CAMERA_ASSIGNED_CWD")
    require(
        Path(__file__) == Path(payload["native_arguments"][0]), "CAMERA_FIXED_SCRIPT"
    )
    _regular(output, directory=True)
    require(next(output.iterdir(), None) is None, "CAMERA_OUTPUT_NOT_EMPTY")
    deadline = min(
        request["parent_deadline_monotonic_ns"],
        request["expires_at_monotonic_ns"],
        time.monotonic_ns() + camera["budget"]["duration_ms"] * 1_000_000,
    )

    def check() -> None:
        require(time.monotonic_ns() < deadline, "CAMERA_CHILD_DEADLINE")

    # Verify complete limited-range source templates before creating any output.
    # The parent holds their file/ancestor handles until child cleanup completes.
    for template in payload["templates"]:
        check()
        path = Path(template["path"])
        require(_regular(path).st_size == TEMPLATE_BYTES, "CAMERA_TEMPLATE_SIZE")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            remaining = TEMPLATE_BYTES
            while remaining:
                check()
                block = stream.read(min(64 * 1024, remaining))
                require(
                    bool(block) and min(block) >= 16 and max(block) <= 235,
                    "CAMERA_TEMPLATE_LUMA",
                )
                hasher.update(block)
                remaining -= len(block)
            require(not stream.read(1), "CAMERA_TEMPLATE_SIZE")
        require(hasher.hexdigest() == template["sha256"], "CAMERA_TEMPLATE_HASH")
    if scenario == "child-timeout":
        time.sleep(70)  # The finite parent Job deadline must terminate this child.
    if scenario == "malformed-result":
        sys.stdout.write('{"duplicate":1,"duplicate":2}')
        return 0
    configured = payload["schema"] == CONFIG_PAYLOAD_SCHEMA
    # State changes exist only in this process-local model. No UVC/OS controls
    # are touched and electronic settings do not synthesize optical effects.
    controls = (
        fixture_readback(camera["controls"], drift=scenario == "control-readback-drift")
        if configured
        else []
    )
    frames = []
    for index, template in enumerate(payload["templates"]):
        check()
        filename = f"frame-{index:06d}.yuy2"
        # Exclusive creation is intentional. Partial files survive any failure;
        # no deletion/repair/retry is attempted by this worker.
        with Path(template["path"]).open("rb") as source, (output / filename).open(
            "xb"
        ) as target:
            for _ in range(TEMPLATE_HEIGHT):
                check()
                values = source.read(TEMPLATE_WIDTH)
                require(len(values) == TEMPLATE_WIDTH, "CAMERA_TEMPLATE_TRUNCATED")
                row = bytearray(10944)
                row[0::4] = values
                row[2::4] = values
                row[1::2] = b"\x80" * 5472
                require(
                    target.write(row) == len(row) and target.write(row) == len(row),
                    "CAMERA_SHORT_WRITE",
                )
            require(not source.read(1), "CAMERA_TEMPLATE_SIZE")
            target.flush()
            os.fsync(target.fileno())
        check()
        frames.append(
            {
                "filename": filename,
                "length_bytes": FRAME_BYTES,
                "stride_bytes": 10944,
                "row0_offset_bytes": 0,
                "host_sequence": index,
                "media_timestamp_100ns": index * 10_000_000 // 9,
                "host_arrival_qpc": time.perf_counter_ns(),
                "qpc_frequency": 1_000_000_000,
                "discontinuity": False,
            }
        )
    uncertain = scenario == "cleanup-uncertain"
    native = {
        "schema": "rocell.windows_camera.v1",
        "operation": camera["operation"],
        "status": "FAILED" if uncertain else "OK",
        "reason_code": "FIXTURE_SOURCE_SHUTDOWN_UNCONFIRMED" if uncertain else None,
        "selected_endpoint": (
            "incapable-fixture-wrong-endpoint"
            if scenario == "identity-mismatch"
            else camera["binding"]["symbolic_link"]
        ),
        "devices": [
            {
                "symbolic_link": camera["binding"]["symbolic_link"],
                "friendly_name": "Incapable source-derived binary camera fixture",
            }
        ],
        "modes": [MODE],
        "requested_mode": camera["mode"],
        "observed_mode": MODE if camera["operation"] == "capture" else None,
        "controls": controls,
        "frames": frames,
        "counts": {
            "source_activation_attempts": 1,
            "source_opened": 1,
            "control_set_attempts": len(camera["controls"]),
            "samples_received": len(frames),
            "frames_written": len(frames),
            "source_shutdown_attempts": 1,
        },
        "cleanup": {
            "source_shutdown_hr": -2147467259 if uncertain else 0,
            "source_released": not uncertain,
            "mf_shutdown_hr": 0,
            "com_uninitialized": True,
        },
        "limitations": [
            PROVENANCE,
            "ALL_NATIVE_DEVICE_COUNTERS_ARE_MODELED_NO_DEVICE_ACCESSED",
            "MEDIA_TIMESTAMPS_ARE_SYNTHETIC_NOT_SENSOR_OBSERVATIONS",
            "HOST_ARRIVAL_IS_PYTHON_PERF_COUNTER_NS_NOT_RAW_QPC",
            "FIXED_2X_NEAREST_EXPANSION_NOT_NATIVE_OPTICAL_DETAIL",
            "PHYSICAL_CAMERA_AND_DRIVER_QUALIFICATION_HELD",
        ],
    }
    if configured:
        native["limitations"] += [
            FIXTURE_CONTROL_UNITS,
            "MODELED_CONTROL_STATE_ONLY_NOT_OPTICAL_SIMULATION",
            "MODELED_FLAGS_1_AUTO_2_MANUAL_NOT_RECEIVED_CAPABILITIES",
        ]
    result = {
        "schema": payload_protocols(payload)[1],
        "request_sha256": request["request_sha256"],
        "attempt_id": request["attempt_id"],
        "physical_authority": False,
        "fixture_result": {
            "scenario": scenario,
            "provenance": PROVENANCE,
            "camera_request_sha256": digest(camera),
            "template_sha256s": [item["sha256"] for item in payload["templates"]],
            "native_receipt": native,
        },
    }
    wire = canonical(result)
    require(len(wire) <= 32 * 1024, "CAMERA_RESULT_LIMIT")
    check()
    sys.stdout.buffer.write(wire)
    sys.stdout.buffer.flush()
    return 1 if uncertain else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        sys.stderr.write("INCAPABLE_CAMERA_CHILD_FAILED\n")
        raise SystemExit(2)
