"""Physical child packaging: import checks and invalid requests only, never I/O."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from rocell.providers.windows import powered_feedback_native_package as package


def run_child(tmp_path, mode="check-imports", digest=None, payload=b""):
    path = package.prepare(tmp_path)
    return subprocess.run(
        [
            str(Path(getattr(sys, "_base_executable", sys.executable))),
            "-I",
            "-S",
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


def test_closed_archive_has_required_metadata_and_serial_dependencies():
    raw = package.expected_archive()
    assert raw == package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert "serial/tools/list_ports_windows.py" in archive.namelist()
        assert (
            "rocell/providers/windows/powered_feedback_native_wire.py"
            in archive.namelist()
        )
        assert "rocell/application/arrival_wizard_service.py" not in archive.namelist()
        assert "rocell/arm/telemetry_stream.py" in archive.namelist()
        assert "rocell/providers/windows/powered_telemetry_observation.py" in archive.namelist()
        assert "rocell/providers/windows/powered_telemetry_wire.py" in archive.namelist()


def test_import_check_cannot_load_native_dll(tmp_path):
    result = run_child(tmp_path)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads(result.stdout)
    assert report["status"] == "IMPORTS_OK_NOT_HARDWARE_TESTED"
    assert report["native"]["native_api_loaded"] is False
    assert report["connected"] is report["physical_authority"] is False


@pytest.mark.parametrize(
    "payload",
    [b"{}", b"not JSON", b'{"T":105}', b"x" * 65537],
    ids=["empty-envelope", "malformed-json", "raw-command", "oversized"],
)
def test_invalid_wire_rejected_before_claim_or_metadata(tmp_path, payload):
    result = run_child(tmp_path, mode="observe", payload=payload)
    assert result.returncode != 0 and result.stdout == b""
    assert not list(tmp_path.glob("*-powered-feedback-*.json"))


def test_wrong_digest_stops_before_import(tmp_path):
    result = run_child(tmp_path, digest="e" * 64)
    assert result.returncode == 4 and result.stdout == b""
