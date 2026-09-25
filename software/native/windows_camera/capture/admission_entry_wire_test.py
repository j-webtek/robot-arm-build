"""Bounded pipe interop with one exact *incapable* capture-entry executable.

No native camera helper, COM/MF implementation, device inventory or frames are
involved. This stdlib harness is not the application's owned-process admission.
"""

import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time


EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "build-owned-capture/Release/rocell_camera_capture_admission_entry_tests.exe"
)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def request_for(directory, fault):
    endpoint = "incapable-fixture-only-\u00e9"
    configuration = {
        "width": 5472,
        "height": 3648,
        "fps_numerator": 9,
        "fps_denominator": 1,
        "subtype": "YUY2",
        "frame_count": 1,
        "max_frame_bytes": 39_923_712,
        "max_total_bytes": 39_923_712,
        "output_directory": str(
            directory
            / ("wrong-directory" if fault == "wrong-directory" else "capture-attempt-1")
        ),
        "controls": "brightness,-3,manual;gain,0,auto",
        "requested_stride_bytes": "-10944",
    }
    data = {
        "schema": "rocell.native_camera_capture_admission_request.v1",
        "attempt_id": "attempt-1",
        "session_id": "incapable-session-1",
        "source_sha256": "a" * 64,
        "operation_sha256": "b" * 64,
        "selected_identity_sha256": "c" * 64,
        "endpoint": endpoint,
        "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
        "helper_sha256": "d" * 64,
        "runtime_registration_sha256": "e" * 64,
        "camera_request_sha256": "f" * 64,
        "permit_sha256": "1" * 64,
        "native_duration_ms": 5000,
        "admission_timeout_ms": 5000,
        "capture_json": canonical(configuration).decode("ascii"),
    }
    if fault == "probe-schema":
        data.pop("capture_json")
        data.update(
            schema="rocell.native_camera_admission_request.v1",
            admission_timeout_ms=2000,
        )
    return data


def run_case(child, fault):
    with tempfile.TemporaryDirectory(prefix="incapable-capture-entry-") as directory:
        data = request_for(Path(directory), fault)
        wire = canonical(data)
        request_hash = hashlib.sha256(wire).hexdigest()
        process = subprocess.Popen(
            [str(child), "--owned-capture", "--request-sha256", request_hash],
            cwd=directory,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        first = queue.Queue(maxsize=1)
        reader = threading.Thread(
            target=lambda: first.put(process.stdout.readline(1025)), daemon=True
        )
        try:
            process.stdin.write(wire + b"\n")
            process.stdin.flush()
            reader.start()
            line = first.get(timeout=6)
            reader.join(timeout=1)
            assert not reader.is_alive() and len(line) <= 1024
            if fault in {"probe-schema", "wrong-directory"}:
                assert line == b""
                _, error = process.communicate(timeout=2)
                expected = (
                    b"CAPTURE_FIELD_SET"
                    if fault == "probe-schema"
                    else b"CAPTURE_ASSIGNED_LEAF"
                )
                assert process.returncode == 2 and expected in error
                return
            ready = json.loads(line)
            assert ready["schema"] == "rocell.native_camera_admission_ready.v1"
            assert ready["child_pid"] == process.pid
            assert ready["request_sha256"] == request_hash
            challenge_hash = hashlib.sha256(
                ready["challenge"].encode("ascii")
            ).hexdigest()
            release = (
                canonical(
                    {
                        "schema": "rocell.native_camera_admission_release.v1",
                        "request_sha256": request_hash,
                        "child_pid": process.pid,
                        "challenge_sha256": challenge_hash,
                        "permit_sha256": (
                            "2" * 64
                            if fault == "wrong-permit"
                            else data["permit_sha256"]
                        ),
                    }
                )
                + b"\n"
            )
            if fault == "late-release":
                # No grant is written. Actual child must exit on its original
                # five-second clock while stdin remains open.
                process.wait(timeout=7)
                output, error = process.communicate(timeout=2)
                assert (
                    process.returncode == 2 and b"CAPTURE_ADMISSION_DEADLINE" in error
                )
            elif fault == "missing-eof":
                process.stdin.write(release)
                process.stdin.flush()
                process.wait(timeout=7)
                output, error = process.communicate(timeout=2)
                assert (
                    process.returncode == 2 and b"CAPTURE_ADMISSION_DEADLINE" in error
                )
            else:
                if fault == "delayed-nominal":
                    time.sleep(3)
                output, error = process.communicate(
                    release + (b"extra" if fault == "trailing" else b""), timeout=7
                )
                if fault in {"nominal", "delayed-nominal"}:
                    assert process.returncode == 0 and error == b""
                    result = json.loads(output)
                    assert result == {
                        "schema": "rocell.native_camera_capture_admission_only_test.v1",
                        "admitted": True,
                        "child_pid": process.pid,
                        "device_effects": 0,
                        "request_sha256": request_hash,
                        "challenge_sha256": challenge_hash,
                    }
                else:
                    assert process.returncode == 2 and output == b""
            assert len(output) <= 4096 and len(error) <= 4096
            assert not list(
                Path(directory).iterdir()
            )  # no output directory or frame was made
        finally:
            if process.poll() is None:
                process.kill()  # exactly this fixed incapable child, no device stop claim
            process.wait(timeout=2)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            if reader.ident is not None:
                reader.join(timeout=1)


def main():
    assert len(sys.argv) == 2 and Path(sys.argv[1]).resolve() == EXPECTED
    for fault in (
        "nominal",
        "delayed-nominal",
        "wrong-permit",
        "trailing",
        "probe-schema",
        "wrong-directory",
        "late-release",
        "missing-eof",
    ):
        run_case(EXPECTED, fault)
    print("8 incapable capture pipe cases passed; camera calls=0; files produced=0")


if __name__ == "__main__":
    main()
