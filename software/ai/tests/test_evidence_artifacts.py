import hashlib
from pathlib import Path
import sys

import pytest


AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_committed_artifact_must_exist_and_match(tmp_path):
    artifact = tmp_path / "software/ai/eval/report.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"frozen")
    status = verify_frozen_artifacts(
        tmp_path, {"software/ai/eval/report.json": _sha(b"frozen")}
    )
    assert status[0].bytes_present is True

    artifact.write_bytes(b"changed")
    with pytest.raises(AssertionError, match="SHA256 mismatch"):
        verify_frozen_artifacts(
            tmp_path, {"software/ai/eval/report.json": _sha(b"frozen")}
        )
    artifact.unlink()
    with pytest.raises(AssertionError, match="required repository artifact missing"):
        verify_frozen_artifacts(
            tmp_path, {"software/ai/eval/report.json": _sha(b"frozen")}
        )


def test_ignored_result_bytes_are_explicit_and_verified_when_present(tmp_path):
    relative = "software/ai/results/run/pose_model.pt"
    status = verify_frozen_artifacts(tmp_path, {relative: _sha(b"checkpoint")})
    assert status[0].relative_path == relative
    assert status[0].bytes_present is False

    checkpoint = tmp_path / relative
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"checkpoint")
    assert verify_frozen_artifacts(
        tmp_path, {relative: _sha(b"checkpoint")}
    )[0].bytes_present is True
    checkpoint.write_bytes(b"wrong")
    with pytest.raises(AssertionError, match="SHA256 mismatch"):
        verify_frozen_artifacts(tmp_path, {relative: _sha(b"checkpoint")})


@pytest.mark.parametrize("relative", ["../escape", "/absolute", ""])
def test_unsafe_artifact_paths_are_rejected(tmp_path, relative):
    with pytest.raises(AssertionError, match="unsafe artifact path"):
        verify_frozen_artifacts(tmp_path, {relative: "0" * 64})
