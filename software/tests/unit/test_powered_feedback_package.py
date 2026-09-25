"""Real isolated subprocess tests, restricted to memory-only entry modes."""

import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from rocell.providers.windows import powered_feedback_package as package


def run_child(tmp_path, mode="check-imports", digest=None, payload=b"", isolated=True):
    path = package.prepare(tmp_path)
    return subprocess.run(
        [
            str(Path(getattr(sys, "_base_executable", sys.executable))),
            *(["-I", "-S"] if isolated else []),
            str(package.CHILD),
            str(path),
            digest or hashlib.sha256(path.read_bytes()).hexdigest(),
            mode,
        ],
        cwd=tmp_path,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )


def test_deterministic_package_excludes_wizard_bootstrap():
    raw = package.expected_archive()
    assert raw == package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert (
            "rocell/application/powered_feedback_child_claim.py" in archive.namelist()
        )
        assert "rocell/application/arrival_wizard_service.py" not in archive.namelist()
        assert b"application bootstrap" in archive.read("rocell/__init__.py")


def test_isolated_imports(tmp_path):
    result = run_child(tmp_path)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads(result.stdout)
    assert report["status"] == "IMPORTS_OK_NOT_HARDWARE_TESTED"
    assert report["native_dispatch_available"] is report["connected"] is False


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("nominal", "SUCCEEDED"),
        ("stale-input", "FAILED"),
        ("incomplete-reply", "FAILED"),
        ("short-write", "FAILED"),
        ("cleanup-unknown", "FAILED"),
    ],
)
def test_rehearsal_in_isolated_process(tmp_path, scenario, status):
    payload = dict(
        session_id="wizard-" + "a" * 32,
        operation_id="operation-" + "b" * 32,
        source_sha256="c" * 64,
        scenario=scenario,
    )
    result = run_child(tmp_path, mode="rehearse", payload=json.dumps(payload).encode())
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads(result.stdout)
    assert report["completion"]["status"] == status
    original = base64.b64decode(report["original_base64"], validate=True)
    assert (
        hashlib.sha256(original).hexdigest()
        == report["completion"]["steps"][0]["report"]["original_sha256"]
    )
    assert json.loads(original)["origin"] == "SYNTHETIC_REHEARSAL"
    assert not list(tmp_path.glob("*-powered-feedback-*.json"))


@pytest.mark.parametrize(
    "kwargs,code",
    [({"digest": "f" * 64}, 4), ({"mode": "observe"}, 5), ({"isolated": False}, 2)],
)
def test_bootstrap_rejections(tmp_path, kwargs, code):
    result = run_child(tmp_path, **kwargs)
    assert result.returncode == code
    assert result.stdout == b""


def test_arbitrary_command_handoff_rejected(tmp_path):
    result = run_child(tmp_path, mode="rehearse", payload=b'{"command":{"T":100}}')
    assert result.returncode != 0
    assert result.stdout == b""
    assert b"Exact powered rehearsal handoff required" in result.stderr
