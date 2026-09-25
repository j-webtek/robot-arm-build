"""Python/Win32/C++ handshake interop using the separately built incapable child.

This exercises the *production admission entry* and real bounded owned pipes.
It deliberately does not use the real helper registration, M1, or any device
code. The child links no camera/MF/COM implementation and reports no native
camera receipt; passing cannot qualify or dispatch a physical provider.
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
from test_native_camera_parent_admission import preparation


ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / "software" / "native" / "windows_camera"
CHILD = NATIVE / "build-owned" / "Release" / "rocell_camera_admission_entry_tests.exe"
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not CHILD.is_file(),
    reason="Requires separately compiled incapable admission-entry target on Windows",
)


def pin(path):
    return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())


def poll_until(owner, registration, predicate, deadline):
    waiting = threading.Event()
    while time.monotonic_ns() < deadline:
        ended = owner.poll(registration.budget)
        if predicate(ended):
            return
        assert not ended, (owner.returncode, owner.stdout, owner.stderr)
        waiting.wait(0.005)
    pytest.fail("Bounded incapable admission child timed out")


@pytest.mark.parametrize(
    "fault",
    ["none", "wrong-pid", "cancel-before-release", "wrong-permit", "extra-input"],
)
def test_actual_cpp_entry_over_two_phase_owned_pipe(tmp_path, fault):
    prepared = preparation(tmp_path)
    # Explicitly different, separately pinned *test* executable. This is not a
    # physical-registration admission test or a substitute coordinator permit.
    registration = replace(
        prepared.registration,
        worker_id="incapable-native-admission-entry",
        executable=pin(CHILD),
        package_files=tuple(
            pin(NATIVE / name)
            for name in (
                "admission_entry_tests.cpp",
                "admission_entry.cpp",
                "admission_protocol.cpp",
            )
        ),
        composition="INCAPABLE_PROCESS_FIXTURE",
    )
    registration.working_directory.mkdir()
    cancellation, validations = threading.Event(), []

    def current_permit(exact):
        assert exact.payload == prepared.payload
        validations.append(exact.preparation_sha256)

    parent = NativeCameraParentHandshake(
        prepared,
        cancellation=cancellation,
        revalidate_consumed_permit=current_permit,
    )
    owner = WindowsOwnedProcess()
    deadline = time.monotonic_ns() + 15_000_000_000
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
        ready_line, before_release = owner.stdout.split(b"\n", 1)
        assert before_release == b"" and owner.written == len(wire)
        if fault == "wrong-pid":
            with pytest.raises(ValueError, match="OWNED_CHILD_BINDING"):
                parent.accept_ready(ready_line + b"\n", owned_child_pid=owner.pid + 1)
            assert len(validations) == 1
            return
        release = parent.accept_ready(ready_line + b"\n", owned_child_pid=owner.pid)
        if fault == "cancel-before-release":
            cancellation.set()
            with pytest.raises(ValueError, match="CANCELLED"):
                owner.send_final_input(release, check=parent.check_release)
            assert owner.written == len(wire) and len(validations) == 1
            return
        if fault == "wrong-permit":
            changed = json.loads(release)
            changed["permit_sha256"] = "0" * 64
            release = canonical(changed) + b"\n"
        if fault == "extra-input":
            release += b"x"
        owner.send_final_input(release, check=parent.check_release)
        poll_until(owner, registration, lambda ended: ended, deadline)
        assert len(validations) == 2
        assert owner.written == len(wire) + len(release)
        result_bytes = owner.stdout.split(b"\n", 1)[1]
        if fault != "none":
            assert owner.returncode != 0
            assert b'"admitted":true' not in result_bytes
            return
        result = json.loads(result_bytes)
        assert owner.returncode == 0
        assert result["schema"] == "rocell.native_camera_admission_only_test.v1"
        assert result["request_sha256"] == prepared.admission_request.request_sha256
        assert result["child_pid"] == owner.pid
        assert result["admitted"] is True and result["device_effects"] == 0
        assert result["challenge_sha256"] == json.loads(release)["challenge_sha256"]
        # Admission-only completion cannot masquerade as a native camera test.
        with pytest.raises(ValueError, match="RESULT_SCHEMA"):
            parent.accept_result(result_bytes, returncode=0)
    finally:
        assert owner.cleanup(min(deadline, time.monotonic_ns() + 2_000_000_000)) == ()
        assert (
            (not owner.created or owner.tree_exited)
            and not owner.handles
            and not owner.pins
        )
