"""The r91 pose-claim reset is one-use and requires physical support."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/reset_r91_after_pose_claim.py"


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("r91_pose_claim_reset", SCRIPT)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path.pop(0)


def test_read_only_preflight_binds_exact_claimed_boot(monkeypatch):
    reset = module()
    caps = dict(boot_id=reset.BOOT,
                stamped_release_sha256=reset.R91_RELEASE_SHA,
                maximum_legs=5)
    monkeypatch.setattr(reset, "get", lambda *_: (200, json.dumps(caps).encode()))
    report = reset.preflight(ROOT, "192.168.0.225")
    assert report["old_boot_id"] == reset.BOOT
    assert report["reset_sent"] is False
    assert report["movement_command_sent"] is False
    caps["boot_id"] = "ab" * 16
    with pytest.raises(ValueError, match="boot changed"):
        reset.preflight(ROOT, "192.168.0.225")


def test_live_flag_without_support_refuses_before_serial(monkeypatch):
    reset = module()
    monkeypatch.setattr(reset, "preflight", lambda *_: dict(old_boot_id=reset.BOOT))
    with pytest.raises(ValueError, match="Physical support"):
        reset.main(["--one-startup-no-motion"])
