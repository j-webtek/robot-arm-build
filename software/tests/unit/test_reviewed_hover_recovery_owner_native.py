"""Fixed five-leg recovery owner in a fake bus; no hardware access."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("hover-recovery") / "owner.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_recovery_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return target


def test_five_export_gated_legs(native):
    result = subprocess.run([str(native), "success"], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["source", "prewrite", "stale", "delivery",
                                  "wrong_endpoint", "evidence", "timeout",
                                  "hash", "expired"])
@pytest.mark.parametrize("leg", range(1, 6))
def test_every_leg_fault_stops_without_extra_write(native, mode, leg):
    result = subprocess.run([str(native), mode, str(leg)], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, f"{mode} leg {leg}: {result.stderr}"
