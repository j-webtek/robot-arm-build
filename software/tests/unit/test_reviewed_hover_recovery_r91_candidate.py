"""The live host pin must match the independently reviewed offline image."""
from pathlib import Path
import importlib.util

from rocell.application.reviewed_hover_recovery_live_host import (
    R91_APP_SHA, R91_RELEASE_SHA,
)


ROOT = Path(__file__).resolve().parents[2]


def test_r91_review_matches_live_host_pin():
    script = ROOT / "scripts/review_r91_hover_recovery_candidate.py"
    spec = importlib.util.spec_from_file_location("r91_recovery_review", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    review = module.review(ROOT)
    assert review["status"] == "COMPILED_ROUTE_PRESENT_NOT_DEPLOYED"
    assert review["app_sha256"] == R91_APP_SHA
    assert review["release_sha256"] == R91_RELEASE_SHA
    assert review["r90_route_absent"]
    assert review["firmware_uploaded"] is False
