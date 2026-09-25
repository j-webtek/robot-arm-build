import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/recover_r41_after_r42_connect_failure.py"
    spec = importlib.util.spec_from_file_location("r42_prewrite_recovery", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def exact_raw(subject):
    rows = [
        dict(stage="RESERVED", app_sha256=subject.R42_SHA256, offset=65536, bytes=1156992),
        dict(
            stage="STOPPED",
            error_type="FatalError",
            error=(
                "Failed to connect to ESP32: Download mode successfully detected, "
                "but getting no sync reply: the retained transport stopped"
            ),
            retry=False,
        ),
    ]
    return b"\n".join(json.dumps(row, separators=(",", ":")).encode() for row in rows) + b"\n"


def test_only_exact_pinned_prewrite_failure_is_eligible(monkeypatch):
    subject = module()
    raw = exact_raw(subject)
    monkeypatch.setattr(subject, "FAILED_JOURNAL_SHA256", __import__("hashlib").sha256(raw).hexdigest())
    assert len(subject.validate_failure(raw)) == 2
    for changed in (raw + b"{}\n", raw.replace(b'"retry":false', b'"retry":true'),
                    raw.replace(b'"stage":"STOPPED"', b'"stage":"WRITE_ATTEMPT_STARTED"')):
        with pytest.raises(ValueError):
            subject.validate_failure(changed)
