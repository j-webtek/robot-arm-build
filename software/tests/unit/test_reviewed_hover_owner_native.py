"""Offline native owner: one-use, fresh feedback, and export-gated progression."""
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
    target = tmp_path_factory.mktemp("reviewed-hover-owner") / "owner.exe"
    result = subprocess.run(
        [compiler, "-std=c++17", "-O2",
         str(ROOT / "firmware/diagnostics/test_reviewed_hover_owner.cpp"),
         "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return target


def test_full_campaign_has_sixteen_bound_records(native):
    result = subprocess.run([str(native), "success"], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    records = [bytes.fromhex(line) for line in result.stdout.splitlines()]
    assert len(records) == 16
    assert all(len(raw) == 1163 for raw in records)
    assert all(raw[:10] == b"RCHOVERR01" for raw in records)
    assert all(raw[10:26] == b"\xab" * 16 for raw in records)
    assert all(raw[26:58] == bytes(range(1, 33)) for raw in records)
    assert [raw[58] for raw in records] == list(range(1, 17))
    assert [raw[59] for raw in records] == [1, 2, 1, 0, 4, 5, 4, 3] * 2


@pytest.mark.parametrize("mode", ["delivery", "wrong_endpoint", "evidence",
                                  "source", "prewrite", "stale", "timeout",
                                  "hash", "expired"])
@pytest.mark.parametrize("leg", range(1, 17))
def test_faults_stop_on_affected_leg_without_retry(native, mode, leg):
    result = subprocess.run([str(native), mode, str(leg)], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, f"{mode} leg {leg}: {result.stderr}"
