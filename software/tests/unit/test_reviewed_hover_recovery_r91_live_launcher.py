"""The pinned live launcher is read-only until explicitly armed."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_r91_recovery_cycle.py"


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("r91_live_launcher", SCRIPT)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path.pop(0)


def capabilities(launcher):
    return dict(schema="rocell.reviewed_hover_recovery_capabilities.v1",
                boot_id=launcher.BOOT, live_release_available=True,
                motion_authorized=False, maximum_legs=5,
                stamped_release_sha256=launcher.R91_RELEASE_SHA)


def test_read_only_preflight_checks_pinned_boot_and_source(monkeypatch):
    launcher = module()
    calls = []

    def get(address, path, limit):
        calls.append((address, path, limit))
        return 200, json.dumps(capabilities(launcher)).encode("ascii")

    monkeypatch.setattr(launcher, "get", get)
    report = launcher.preflight(ROOT, "192.168.0.225")
    assert report["boot_id"] == launcher.BOOT
    assert report["prior_pose_stable"] is True
    assert report["current_source_recheck_required"] is True
    assert report["movement_command_sent"] is False
    assert calls == [("192.168.0.225", "/rocell/recovery-hover/capabilities", 512)]


def test_wrong_boot_and_prior_claim_stop_before_motion(monkeypatch):
    launcher = module()
    caps = capabilities(launcher)
    caps["boot_id"] = "ab" * 16
    monkeypatch.setattr(launcher, "get", lambda *_: (200, json.dumps(caps).encode()))
    with pytest.raises(ValueError, match="boot/release differs"):
        launcher.preflight(ROOT, "192.168.0.225")

    marker = ROOT / "runs/wizard-exports" / f"recovery-hover-live-{launcher.BOOT}.json"
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: True if path == marker
                        else original_exists(path))
    with pytest.raises(ValueError, match="already claimed"):
        launcher.preflight(ROOT, "192.168.0.225")


def test_default_launcher_exports_only_preflight(monkeypatch, capsys):
    launcher = module()
    monkeypatch.setattr(launcher, "preflight", lambda *_: dict(boot_id=launcher.BOOT))
    monkeypatch.setattr(launcher, "load_reviewed_key", lambda *_: (_ for _ in ()).throw(
        AssertionError("Key must not be loaded for read-only mode")))
    launcher.main([])
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "PREFLIGHT_ONLY_NO_MOVEMENT"
