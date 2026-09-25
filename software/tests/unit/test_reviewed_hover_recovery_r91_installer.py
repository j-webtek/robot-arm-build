"""The r91 installer prepares offline and refuses unsupported reset."""
from pathlib import Path
import importlib.util
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deploy_r91_hover_recovery.py"


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("r91_recovery_deploy", SCRIPT)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path.pop(0)


def test_prepare_exact_image_and_refuse_unsupported_reset():
    deploy = module()
    prepared = deploy.prepare(ROOT)
    assert len(prepared["image"]) == 1073440
    assert prepared["release_sha256"] == deploy.R91_RELEASE_SHA
    assert not prepared["journal"].exists()
    with pytest.raises(ValueError, match="Physical support"):
        deploy.install(ROOT, prepared, supported_for_reset=False)
    assert not prepared["journal"].exists()
