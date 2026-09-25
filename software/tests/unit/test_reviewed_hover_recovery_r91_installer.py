"""The r91 installer prepares offline and refuses unsupported reset."""
from pathlib import Path
import importlib.util
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deploy_r91_hover_recovery.py"
JOURNAL = ROOT / "private-backups/controller-20260918-session1/app-r91-deployment-events.jsonl"


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("r91_recovery_deploy", SCRIPT)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path.pop(0)


def test_prepare_exact_image_and_refuse_unsupported_reset(monkeypatch):
    deploy = module()
    existing = JOURNAL.read_bytes() if JOURNAL.exists() else None
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: False if path == JOURNAL
                        else original_exists(path))
    prepared = deploy.prepare(ROOT)
    assert len(prepared["image"]) == 1073440
    assert prepared["release_sha256"] == deploy.R91_RELEASE_SHA
    assert prepared["journal"] == JOURNAL
    with pytest.raises(ValueError, match="Physical support"):
        deploy.install(ROOT, prepared, supported_for_reset=False)
    if existing is None:
        assert not original_exists(JOURNAL)
    else:
        assert JOURNAL.read_bytes() == existing
