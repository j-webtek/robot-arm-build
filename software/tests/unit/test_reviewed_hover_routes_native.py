"""Offline exact-route and export-gated owner integration harness."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("source", ["test_reviewed_hover_routes.cpp",
                                     "test_reviewed_hover_signed_route.cpp",
                                     "test_reviewed_hover_recovery_signed_route.cpp"])
def test_native_route_rejects_malformed_and_replayed_requests_and_runs_once(tmp_path, source):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "routes.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics" / source),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    run = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    if source == "test_reviewed_hover_recovery_signed_route.cpp":
        from rocell.application.first_motion_contract import canonical
        from rocell.application.reviewed_hover_recovery_admission import recovery_manifest
        wire = subprocess.run([str(target), "--canonical"], capture_output=True,
                              timeout=10)
        assert wire.returncode == 0
        assert wire.stdout == canonical(recovery_manifest())
