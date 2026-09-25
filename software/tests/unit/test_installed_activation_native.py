"""Installed native codec interop, using two fixed incapable test helpers only.

The helpers serialize MODELED device observations. Real pipe/PID/EOF behavior
does not imply a camera open, image delivery or received-hardware qualification.
"""

import hashlib
import os
from pathlib import Path
import queue
import subprocess
import threading
import pytest

from rocell.providers.windows.native_camera_activation_protocol import (
    activation_release,
    parse_owned_activation_result,
)
from rocell.providers.windows.native_camera_protocol import parse_native_camera_ready
from test_native_camera_activation_protocol import request

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / "software/native/windows_camera/activation_v2"
PINS = {
    "probe": "a76552b19d0f337ce92fadb0edeca634ee9a5bc55fd0c156bf4a70ad4a3aa70c",
    "capture": "778c2603780d6dd9db4fafb239b7ae45ee7ed8f10acb83f85f56d1751ece217c",
}
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Windows incapable native helper"
)


def test_exact_native_serializer_extraction_cannot_drift():
    source = (ROOT / "software/native/windows_camera/identity_metadata.cpp").read_text(
        encoding="utf-8"
    )
    extracted = (DRAFT / "identity_serialization_incapable.cpp").read_text(
        encoding="utf-8"
    )
    validation = source[
        source.index("bool valid_text(") : source.index("std::uint16_t u16(")
    ]
    serialization = source[source.index("namespace {\nconst char* reason_name(") :]
    assert validation in extracted
    assert extracted.endswith(serialization)
    assert "#include <windows.h>" not in extracted
    assert "WindowsIdentityMetadataApi::" not in extracted
    assert "resolve_identity_metadata(" not in extracted


@pytest.mark.parametrize("build_kind", ["probe", "capture"])
@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "scenario",
    [
        "ok",
        "driver-changed",
        "query-threw",
        "late-return",
        "not-started",
        "cleanup-failed",
    ],
)
def test_actual_native_v2_result_roundtrip_is_hardware_incapable(
    tmp_path, build_kind, purpose, scenario
):
    CHILD = (
        ROOT
        / f"software/native/windows_camera/build-owned-activation-{build_kind}/Release/rocell_activation_result_tests.exe"
    )
    CHILD_SHA256 = PINS[build_kind]
    assert hashlib.sha256(CHILD.read_bytes()).hexdigest() == CHILD_SHA256
    req = request(purpose)
    process = subprocess.Popen(
        [str(CHILD), "--" + purpose, scenario, "--request-sha256", req.request_sha256],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    first = queue.Queue(maxsize=1)
    reader = threading.Thread(
        target=lambda: first.put(process.stdout.readline(1025)), daemon=True
    )
    try:
        process.stdin.write(req.wire())
        process.stdin.flush()
        reader.start()
        initial = first.get(timeout=7)
        reader.join(timeout=1)
        assert not reader.is_alive()
        ready = parse_native_camera_ready(
            initial,
            expected_request_sha256=req.request_sha256,
            expected_child_pid=process.pid,
        )
        output, error = process.communicate(
            activation_release(req, ready, expected_child_pid=process.pid), timeout=7
        )
        assert error == b"" and len(output) <= 256 * 1024
        assert process.returncode == (0 if scenario == "ok" else 1)
        result = parse_owned_activation_result(
            output,
            request=req,
            ready=ready,
            expected_child_pid=process.pid,
            returncode=process.returncode,
        )
        assert result.receipt.operation == purpose
        assert result.receipt.status == ("OK" if scenario == "ok" else "FAILED")
        assert (
            result.to_dict()["activation_identity"]["expected_identity_sha256"]
            == req.expectation.sha256
        )
        if scenario == "driver-changed":
            assert (
                result.activation.comparison == "DRIVER_CHANGED"
                and result.activation.independently_matches is False
            )
        if scenario == "query-threw":
            assert (
                result.activation.resolution_attempted
                and result.activation.metadata is None
            )
        if scenario == "late-return":
            assert (
                result.activation.metadata is not None
                and result.activation.comparison is None
            )
        if scenario == "cleanup-failed":
            assert (
                not result.receipt.cleanup_confirmed and result.receipt.effect_uncertain
            )
        if scenario not in {"ok", "cleanup-failed"}:
            assert result.receipt.counts["source_activation_attempts"] == 0
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        if reader.ident is not None:
            reader.join(timeout=1)
        assert not reader.is_alive()
        assert hashlib.sha256(CHILD.read_bytes()).hexdigest() == CHILD_SHA256
        assert not list(tmp_path.iterdir())
