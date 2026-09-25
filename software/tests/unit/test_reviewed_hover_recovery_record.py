"""Native recovery evidence must satisfy the independent host verifier."""
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.reviewed_hover_recovery_admission import (
    recovery_manifest, validate_recovery_manifest,
)
from rocell.application.reviewed_hover_recovery_record import assess_recovery_leg


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def records(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("recovery-records") / "owner.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_recovery_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    output = subprocess.run([str(target), "records"], capture_output=True,
                            text=True, timeout=10)
    assert output.returncode == 0, output.stderr
    raw = [bytes.fromhex(line) for line in output.stdout.splitlines()]
    assert len(raw) == 5
    return raw


def bound(records):
    digest = bytes.fromhex(validate_recovery_manifest(recovery_manifest()))
    return [raw[:26] + digest + raw[58:] for raw in records]


def test_native_five_leg_records_verify_in_order(records):
    previous = None
    for leg, raw in enumerate(bound(records), 1):
        previous = assess_recovery_leg(raw, boot="ab" * 16, leg=leg,
                                       previous=previous)
        assert previous["pose_id"] == recovery_manifest()["pose_ids"][leg - 1]
        assert previous["status"] == "REVIEWED_HOVER_LEG_VERIFIED"


def test_recovery_binding_and_endpoint_mutations_rejected(records):
    first = bound(records)[0]
    with pytest.raises(ValueError):
        assess_recovery_leg(records[0], boot="ab" * 16, leg=1)
    with pytest.raises(ValueError):
        assess_recovery_leg(first, boot="cd" * 16, leg=1)
    for offset in (58, 59, 60, 65, 71, 87):
        altered = bytearray(first)
        altered[offset] ^= 1
        with pytest.raises(ValueError):
            assess_recovery_leg(bytes(altered), boot="ab" * 16, leg=1)
