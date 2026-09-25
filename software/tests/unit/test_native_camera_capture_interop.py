"""Real Python/Win32/C++ capture admission, using only a pinned incapable child.

This substitutes a fixed *test* registration, not a physical provider approval.
The child has no camera, MF, COM or frame-writing code. No native result is faked.
"""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import threading
import time

import pytest

from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess
from rocell.providers.windows.native_camera_parent_admission import (
    NativeCameraParentHandshake,
)
from rocell.providers.windows.native_camera_protocol import canonical
from rocell.providers.windows.owned_worker_process import PinnedWorkerFile
from test_native_camera_capture_protocol import capture_prepared
from test_native_camera_admission_interop import poll_until

WORKSPACE = Path(__file__).resolve().parents[3]
CHILD = (
    WORKSPACE
    / "software/native/windows_camera/build-owned-capture/Release/rocell_camera_capture_admission_entry_tests.exe"
)
CHILD_SHA256 = "16315844fa922eb9f0708c13ada643fd6cfc5338a0c3495294c6bb2d0b70b1b9"
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not CHILD.is_file(),
    reason="Requires the separately compiled incapable capture admission child",
)


@pytest.mark.parametrize(
    "fault", ["none", "slow-check", "deny-release", "wrong-pid", "wrong-permit"]
)
def test_actual_capture_entry_through_owned_windows_process(tmp_path, fault):
    assert hashlib.sha256(CHILD.read_bytes()).hexdigest() == CHILD_SHA256
    prepared = capture_prepared(tmp_path)
    registration = replace(
        prepared.registration,
        worker_id="incapable-native-capture-entry",
        executable=PinnedWorkerFile(CHILD, CHILD_SHA256, 1024 * 1024),
        package_files=(
            PinnedWorkerFile(
                WORKSPACE
                / "software/native/windows_camera/owned_capture_build_manifest.json",
                "b6b60e92b1f95487be7c9230ddade77827b64a30063377b2f41a66d526eda2a5",
                128 * 1024,
            ),
        ),
        composition="INCAPABLE_PROCESS_FIXTURE",
        result_schema="rocell.native_camera_capture_admission_only_test.v1",
    )
    registration.working_directory.mkdir()
    cancellation, checked = threading.Event(), []

    def current(exact):
        assert exact.payload == prepared.payload and exact is not prepared
        checked.append(exact.preparation_sha256)
        if len(checked) == 2:
            if fault == "deny-release":
                raise ValueError("TEST_CONSUMED_SCOPE_CHANGED")
            if fault == "slow-check":
                cancellation.wait(3)

    parent = NativeCameraParentHandshake(
        prepared, cancellation=cancellation, revalidate_consumed_permit=current
    )
    owner = WindowsOwnedProcess()
    deadline = time.monotonic_ns() + 20_000_000_000
    try:
        owner.pin(registration)
        wire = parent.begin(deadline_ns=deadline)
        owner.start(
            registration, wire, check=parent.check_start_boundary, keep_stdin_open=True
        )
        poll_until(
            owner,
            registration,
            lambda _: b"\n" in owner.stdout and not owner.pending,
            deadline,
        )
        ready, extra = owner.stdout.split(b"\n", 1)
        assert extra == b"" and owner.written == len(wire)
        if fault == "wrong-pid":
            with pytest.raises(ValueError, match="OWNED_CHILD_BINDING"):
                parent.accept_ready(ready + b"\n", owned_child_pid=owner.pid + 1)
            assert len(checked) == 1
            return
        release = parent.accept_ready(ready + b"\n", owned_child_pid=owner.pid)
        if fault == "deny-release":
            with pytest.raises(ValueError, match="TEST_CONSUMED_SCOPE_CHANGED"):
                owner.send_final_input(release, check=parent.check_release)
            assert owner.written == len(wire) and len(checked) == 2
            return
        if fault == "wrong-permit":
            value = json.loads(release)
            value["permit_sha256"] = "0" * 64
            release = canonical(value) + b"\n"
        owner.send_final_input(release, check=parent.check_release)
        poll_until(owner, registration, lambda ended: ended, deadline)
        assert len(checked) == 2 and owner.written == len(wire) + len(release)
        output = owner.stdout.split(b"\n", 1)[1]
        if fault == "wrong-permit":
            assert owner.returncode != 0 and b'"admitted":true' not in output
            return
        result = json.loads(output)
        assert owner.returncode == 0 and result["admitted"] is True
        assert result["schema"] == "rocell.native_camera_capture_admission_only_test.v1"
        assert result["device_effects"] == 0 and result["child_pid"] == owner.pid
        assert result["request_sha256"] == prepared.admission_request.request_sha256
        # A real successful admission handshake is still NOT a native capture.
        with pytest.raises(ValueError, match="RESULT_SCHEMA"):
            parent.accept_result(output, returncode=0)
    finally:
        assert owner.cleanup(min(deadline, time.monotonic_ns() + 2_000_000_000)) == ()
        assert not owner.created or owner.tree_exited
        assert not owner.handles and not owner.pins
        assert not prepared.admission_request.configuration.output_directory.exists()
