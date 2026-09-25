"""r91 preflight accepts archived evidence and performs at most a public GET."""
from pathlib import Path
import importlib.util
import json
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/preflight_r91_hover_recovery_install.py"


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("r91_install_preflight", SCRIPT)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path.pop(0)


def test_local_evidence_is_valid_without_device_access(monkeypatch):
    preflight = module()
    monkeypatch.setattr(preflight, "get", lambda *_: (_ for _ in ()).throw(
        AssertionError("Network must not be reached")))
    report = preflight.preflight(ROOT)
    assert report["status"] == "LOCAL_EVIDENCE_VERIFIED_NOT_AUTHORIZED"
    assert not report["current_device_checked"]
    assert not report["deployment_authorized"]


def test_read_only_device_identity_and_wrong_release(monkeypatch):
    preflight = module()
    calls = []
    caps = dict(schema="rocell.reviewed_hover_capabilities.v1",
                boot_id="ab" * 16, live_release_available=True,
                motion_authorized=False, maximum_legs=16,
                stamped_release_sha256=preflight.R90_RELEASE_SHA)

    def get(address, path, limit):
        calls.append((address, path, limit))
        return 200, json.dumps(caps).encode("ascii")

    monkeypatch.setattr(preflight, "get", get)
    report = preflight.preflight(ROOT, "192.168.0.225")
    assert report["status"] == "READ_ONLY_DEVICE_IDENTITY_VERIFIED_NOT_AUTHORIZED"
    assert calls == [("192.168.0.225", "/rocell/reviewed-hover/capabilities", 512)]
    assert report["predecessor_live_readback_verified_now"] is False
    caps["stamped_release_sha256"] = "34" * 32
    with pytest.raises(ValueError, match="release/boot differs"):
        preflight.preflight(ROOT, "192.168.0.225")
