import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[2] / "scripts/consolidate_bidirectional_pair_evidence.py"
    spec = importlib.util.spec_from_file_location("bidirectional_pair_evidence", path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_forward_repeat_reads_raw_campaign(module):
    exports = Path(__file__).resolve().parents[2] / "runs/wizard-exports"
    audit, digest = module._load_forward_repeat(
        exports, "wizard-20260920T192427176078Z-ee1c1fb42de14a4698cfc1f3c1c8ee7c")
    assert audit["actual"] == [2387, 1730]
    assert audit["signed_error"] == [-1, 1]
    assert len(digest) == 64


def test_forward_repeat_rejects_changed_endpoint(module, monkeypatch):
    exports = Path(__file__).resolve().parents[2] / "runs/wizard-exports"
    original = module._read
    def altered(root, ident, name):
        value, digest = original(root, ident, name)
        if name == "attachment-next-validation-terminal-review.json":
            value["actual"][0] += 1
        return value, digest
    monkeypatch.setattr(module, "_read", altered)
    with pytest.raises(ValueError):
        module._load_forward_repeat(
            exports, "wizard-20260920T192427176078Z-ee1c1fb42de14a4698cfc1f3c1c8ee7c")
