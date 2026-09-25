import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def reader():
    path = Path(__file__).resolve().parents[2] / "scripts/compare_reverse_validation.py"
    spec = importlib.util.spec_from_file_location("reverse_validation_comparison", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fault", [None, "variant", "usable", "source", "endpoint", "model", "conditioning"])
def test_real_reverse_candidate_provenance(reader, monkeypatch, fault):
    exports = Path(__file__).resolve().parents[2] / "runs/wizard-exports"
    original = reader._read

    def altered(root, ident, name):
        value, digest = original(root, ident, name)
        if name == "attachment-next-validation-terminal-review.json":
            if fault == "variant":
                value["variant"] = "reverse_control"
            if fault == "usable":
                value["terminal_measurement_usable"] = False
            if fault == "source":
                value["source_result"] = value["source_run"]
            if fault == "endpoint":
                value["actual"][0] += 1
        if name == "attachment-next-validation-predictions.json" and fault == "model":
            value["campaign"] = "different"
        if name == "attachment-smoke-run.json" and fault == "conditioning":
            value["legs"][0]["assessment"]["continuation_eligible"] = False
        return value, digest

    monkeypatch.setattr(reader, "_read", altered)
    args = (
        exports,
        "wizard-20260920T194129776533Z-1ccfcdad8018415ca0080be94a67ff85",
        "reverse_candidate",
    )
    if fault:
        with pytest.raises((ValueError, FileNotFoundError)):
            reader.load_trial(*args)
    else:
        audit, _, model = reader.load_trial(*args)
        assert audit["actual"] == [2387, 1728]
        assert audit["signed_error"] == [-1, -1]
        assert model["sha256"] == "963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5"
