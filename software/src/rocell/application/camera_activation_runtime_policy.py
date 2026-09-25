"""Reviewed software pins for the v2 camera diagnostic runtime.

This is a read-only software gate, not hardware qualification or dispatch.
Candidates remain inert. The original application's guard must call verification
in the same current admission context; replaying the returned report cannot
authorize an operation. The owned process separately pins executable/build bytes.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import threading
import time
from typing import Any

from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from rocell.providers.windows.native_camera_activation_registration import (
    NativeCameraActivationRuntime,
    build_record_relative_path,
    create_activation_runtime,
    helper_relative_path,
)
from rocell.providers.windows.native_camera_capture_protocol import local_capture_path
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import decode_owned_json

POLICY_SCHEMA = "rocell.reviewed_camera_activation_software_policy.v2"
REVIEW_SCHEMA = "rocell.camera_activation_software_observation.v2"
MAX_NATIVE_READ_BYTES = 16 * 1024 * 1024
MAX_NATIVE_READ_CALLS = 160
MAX_CHECK_NS = 10_000_000_000
_NATIVE_PREFIX = "software/native/windows_camera/"
_NATIVE_INPUTS = (
    "activation_v2/camera_activation_entry.cpp",
    "activation_v2/camera_activation_entry.h",
    "activation_v2/camera_activation_gate_tests.cpp",
    "activation_v2/camera_activation_gate.h",
    "activation_v2/camera_activation_identity_tests.cpp",
    "activation_v2/camera_activation_identity.h",
    "activation_v2/camera_activation_launch_tests.cpp",
    "activation_v2/camera_activation_launch.h",
    "activation_v2/camera_activation_protocol_tests.cpp",
    "activation_v2/camera_activation_protocol.cpp",
    "activation_v2/camera_activation_protocol.h",
    "activation_v2/camera_activation_result_tests.cpp",
    "activation_v2/camera_activation_result.cpp",
    "activation_v2/camera_worker.cpp",
    "activation_v2/CMakeLists.txt",
    "activation_v2/identity_serialization_incapable.cpp",
    "admission_protocol.cpp",
    "admission_protocol.h",
    "camera_cleanup_tests.cpp",
    "camera_cleanup.h",
    "capture_admission_protocol.cpp",
    "capture_admission_protocol.h",
    "identity_metadata.cpp",
    "identity_metadata.h",
)
# Reviewed against the installed source, compiler output and incapable tests.
# Never learn these pins from an operator-supplied manifest, path or report.
_PINS = {
    "probe": {
        "helper": "ce097ad0257a1c4a4d026dbaa90582840496b00389e72642069947b4e530aaf5",
        "record": "fa394a0b159333811631168e87dd710dfff95a8a648a274a5589b52cf06996ac",
    },
    "capture": {
        "helper": "cb4711db2b8756212bc33d2ec597415b19eab4893bafff70b7b41b23bd6e0e0c",
        "record": "030b80371820c9556968735cabf161bbe9b264be9e0408cd47b598872cbe83f0",
    },
}


class CameraActivationSoftwareError(ValueError):
    def __init__(self, code: str, *, relative_path: str | None = None):
        self.code = code
        # A closed workspace-relative software path, not raw device/pipe data.
        self.relative_path = relative_path
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CameraActivationSoftwareError(code)


def _catalog() -> bytes:
    return canonical(
        dict(
            schema=POLICY_SCHEMA,
            builds=_PINS,
            native_inputs=list(_NATIVE_INPUTS),
            allowed_scope="EXACT_SCOPED_DIAGNOSTIC_PROBE_OR_CAPTURE",
            requires_current_original_context=True,
            prior_hardware_qualification_required=False,
            arm_operations_allowed=False,
            motion_or_contact_allowed=False,
        )
    )


def reviewed_activation_runtime_candidate(
    workspace: Path, *, purpose: str, source_sha256: str
) -> NativeCameraActivationRuntime:
    """Create an inert fixed-pin candidate; no filesystem or device inspection."""
    _require(
        type(purpose) is str and purpose in _PINS, "REVIEWED_CAMERA_PURPOSE_REQUIRED"
    )
    _require(isinstance(workspace, Path), "SERVER_OWNED_RUNTIME_WORKSPACE_REQUIRED")
    workspace = local_capture_path(str(workspace))
    return create_activation_runtime(
        workspace,
        purpose=purpose,
        source_sha256=source_sha256,
        catalog_sha256=digest(_catalog()),
        helper_sha256=_PINS[purpose]["helper"],
        build_record_sha256=_PINS[purpose]["record"],
    )


def _stamp(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def verify_reviewed_activation_runtime(
    runtime: NativeCameraActivationRuntime,
    *,
    cancellation: threading.Event,
    deadline_ns: int,
) -> dict[str, Any]:
    """Check a reviewed build now, within both local and original time limits.

    The caller provides its ORIGINAL deadline, not a renewed hardware allowance.
    Native reads have separate 16 MiB / 160-call caps; existing application source
    checks retain their own 128 MiB bounds. Synchronous filesystem calls cannot be
    forcibly interrupted, so lateness is checked after calls, never called success.
    This is a point-in-time observation, not the process owner's pinned window.
    """
    _require(
        type(runtime) is NativeCameraActivationRuntime, "EXACT_V2_RUNTIME_REQUIRED"
    )
    _require(
        isinstance(cancellation, threading.Event), "EXACT_RUNTIME_CANCELLATION_REQUIRED"
    )
    started = time.monotonic_ns()
    _require(
        type(deadline_ns) is int and deadline_ns > started,
        "RUNTIME_ORIGINAL_DEADLINE_REQUIRED",
    )
    deadline = min(deadline_ns, started + MAX_CHECK_NS)
    original = runtime.payload
    runtime = NativeCameraActivationRuntime(original)
    data = runtime.to_dict()
    workspace, purpose = Path(data["workspace"]), data["purpose"]
    expected = reviewed_activation_runtime_candidate(
        workspace, purpose=purpose, source_sha256=data["source_sha256"]
    )
    _require(original == expected.payload, "UNREVIEWED_CAMERA_RUNTIME")
    catalog = _catalog()
    files_checked = total_bytes = read_calls = 0
    last_now = started

    def current() -> None:
        nonlocal last_now
        now = time.monotonic_ns()
        _require(not cancellation.is_set(), "RUNTIME_CHECK_CANCELLED")
        _require(last_now <= now < deadline, "RUNTIME_CHECK_EXPIRED_OR_CLOCK_REGRESSED")
        last_now = now
        _require(_catalog() == catalog, "RUNTIME_SOFTWARE_POLICY_CHANGED")

    def application_source() -> None:
        current()
        try:
            observed = source_fingerprint(workspace)
        except Exception as error:
            raise CameraActivationSoftwareError(
                "RUNTIME_APPLICATION_SOURCE_UNAVAILABLE"
            ) from error
        current()
        _require(
            observed == data["source_sha256"], "RUNTIME_APPLICATION_SOURCE_CHANGED"
        )

    def read(
        relative: str, expected_sha: str, maximum: int, length: int | None = None
    ) -> bytes:
        nonlocal files_checked, total_bytes, read_calls
        current()
        _require(
            re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None,
            "RUNTIME_EXPECTED_DIGEST",
        )
        # All relative names come from the closed catalog, never a manifest path.
        try:
            path = require_regular_path(workspace / relative, directory=False)
            before = path.stat()
            _require(0 < before.st_size <= maximum, "RUNTIME_FILE_SIZE_LIMIT")
            if length is not None:
                _require(before.st_size == length, "RUNTIME_FILE_LENGTH_MISMATCH")
            chunks = []
            observed_bytes = 0
            with path.open("rb") as stream:
                _require(
                    _stamp(os.fstat(stream.fileno())) == _stamp(before),
                    "RUNTIME_FILE_CHANGED",
                )
                while True:
                    current()
                    _require(
                        read_calls < MAX_NATIVE_READ_CALLS, "RUNTIME_READ_CALL_LIMIT"
                    )
                    read_calls += 1
                    chunk = stream.read(min(128 * 1024, maximum - observed_bytes + 1))
                    current()
                    if not chunk:
                        break
                    observed_bytes += len(chunk)
                    total_bytes += len(chunk)
                    _require(
                        observed_bytes <= maximum
                        and total_bytes <= MAX_NATIVE_READ_BYTES,
                        "RUNTIME_READ_BYTE_LIMIT",
                    )
                    chunks.append(chunk)
                _require(
                    _stamp(os.fstat(stream.fileno())) == _stamp(before),
                    "RUNTIME_FILE_CHANGED",
                )
            current()
            after = require_regular_path(path, directory=False).stat()
            _require(
                _stamp(after) == _stamp(before) and observed_bytes == before.st_size,
                "RUNTIME_FILE_CHANGED",
            )
        except CameraActivationSoftwareError as error:
            raise CameraActivationSoftwareError(
                error.code, relative_path=relative
            ) from error
        except Exception as error:
            raise CameraActivationSoftwareError(
                "RUNTIME_FILE_UNAVAILABLE_OR_UNSAFE", relative_path=relative
            ) from error
        raw = b"".join(chunks)
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            raise CameraActivationSoftwareError(
                "RUNTIME_FILE_HASH_MISMATCH", relative_path=relative
            )
        files_checked += 1
        return raw

    application_source()
    raw = read(
        build_record_relative_path(purpose), _PINS[purpose]["record"], 128 * 1024
    )
    manifest = decode_owned_json(raw, maximum=128 * 1024)
    _require(
        manifest["schema"] == "rocell.windows_camera_activation_build.v2"
        and manifest["purpose"] == purpose
        and manifest["launch_flag"] == "--owned-" + purpose + "-v2"
        and manifest["request_schema"] == data["request_schema"]
        and manifest["result_schema"] == data["result_schema"]
        and manifest["status"] == "COMPILED_INCAPABLE_TESTS_PASSED"
        and all(
            manifest[key] is False
            for key in (
                "native_helper_executed",
                "hardware_or_metadata_access_performed",
                "hardware_qualified",
                "physical_authority",
                "runtime_dispatch_enabled",
            )
        ),
        "RUNTIME_REVIEWED_BUILD_CONTRACT",
    )
    sources = manifest["source_files"]
    _require(
        type(sources) is dict and set(sources) == set(_NATIVE_INPUTS),
        "RUNTIME_NATIVE_INPUT_SET",
    )
    helper_relative = helper_relative_path(purpose)
    rows = [
        row
        for row in manifest["artifacts"]
        if _NATIVE_PREFIX + row["path"] == helper_relative
    ]
    _require(
        len(rows) == 1
        and rows[0]["sha256"] == _PINS[purpose]["helper"]
        and rows[0]["executed"] is False,
        "RUNTIME_NATIVE_ARTIFACT_CONTRACT",
    )
    length = rows[0]["length_bytes"]
    _require(
        type(length) is int and 0 < length <= 8 * 1024 * 1024,
        "RUNTIME_NATIVE_ARTIFACT_LENGTH",
    )
    read(helper_relative, _PINS[purpose]["helper"], 8 * 1024 * 1024, length)
    for name in _NATIVE_INPUTS:
        read(_NATIVE_PREFIX + name, sources[name], 128 * 1024)
    application_source()
    current()
    return dict(
        schema=REVIEW_SCHEMA,
        status="REVIEWED_SOFTWARE_MATCHED",
        purpose=purpose,
        runtime_registration_sha256=runtime.registration_sha256,
        catalog_sha256=digest(catalog),
        source_sha256=data["source_sha256"],
        files_checked=files_checked,
        bytes_read=total_bytes,
        read_calls=read_calls,
        elapsed_ns=last_now - started,
        original_context_authenticated=False,
        physical_authority=False,
        connected=False,
        hardware_qualified=False,
        device_operations=0,
    )
