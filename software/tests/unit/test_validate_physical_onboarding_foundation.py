from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


WORKSPACE = Path(__file__).resolve().parents[3]
TOOL_PATH = (
    WORKSPACE / "software/tools/validate_physical_onboarding_foundation.py"
)


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_physical_onboarding_foundation_test",
        TOOL_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _foundation(**overrides: Any) -> SimpleNamespace:
    fields: dict[str, object] = {
        "foundation_id": "ROCELL-PHYSICAL-ONBOARDING-FOUNDATION-TEST",
        "source_sha256": "a" * 64,
        "runtime_activation": False,
        "zero_physical_authority": True,
        "contracts": ("authority", "hazards", "stages"),
        "open_implementation_gates": (
            "windows_durability_adapter_not_implemented",
            "effectful_runtime_not_implemented",
        ),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_human_summary_is_concise_and_explicitly_zero_authority(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = _load_tool()
    monkeypatch.setattr(tool, "_load_foundation", lambda _workspace: _foundation())

    assert tool.main(()) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.splitlines() == [
        "PHYSICAL_ONBOARDING_FOUNDATION_VALID_ZERO_AUTHORITY",
        "foundation: ROCELL-PHYSICAL-ONBOARDING-FOUNDATION-TEST",
        f"source sha256: {'a' * 64}",
        "validated contracts: 3",
        "runtime activation: false; physical authority: false; "
        "open implementation gates: 2",
    ]


def test_json_summary_is_deterministic_and_reports_no_hardware_access(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = _load_tool()
    monkeypatch.setattr(tool, "_load_foundation", lambda _workspace: _foundation())

    assert tool.main(("--json",)) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report == {
        "schema": "rocell.physical_onboarding_foundation_validation.v1",
        "result": "VALID_ZERO_AUTHORITY_FOUNDATION",
        "foundation_id": "ROCELL-PHYSICAL-ONBOARDING-FOUNDATION-TEST",
        "foundation_sha256": "a" * 64,
        "runtime_activation": False,
        "physical_authority": False,
        "physical_release_effect": "NONE",
        "hardware_access_attempted": False,
        "validated_contract_count": 3,
        "open_implementation_gate_count": 2,
        "open_implementation_gates": [
            "windows_durability_adapter_not_implemented",
            "effectful_runtime_not_implemented",
        ],
    }
    assert captured.out == json.dumps(report, indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"runtime_activation": True}, "runtime_activation must remain false"),
        ({"zero_physical_authority": False}, "zero physical authority"),
        ({"source_sha256": "not-a-digest"}, "lowercase SHA-256"),
    ],
)
def test_unsafe_or_malformed_aggregate_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    override: dict[str, object],
    message: str,
) -> None:
    tool = _load_tool()
    monkeypatch.setattr(
        tool,
        "_load_foundation",
        lambda _workspace: _foundation(**override),
    )

    assert tool.main(()) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("PHYSICAL_ONBOARDING_FOUNDATION_INVALID: ")
    assert message in captured.err


def test_json_failure_remains_structured_and_zero_authority(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = _load_tool()

    def fail(_workspace: Path) -> SimpleNamespace:
        raise ValueError("controlled contract hash mismatch")

    monkeypatch.setattr(tool, "_load_foundation", fail)

    assert tool.main(("--json",)) == 2

    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["result"] == "INVALID"
    assert report["error"] == "controlled contract hash mismatch"
    assert report["physical_authority"] is False
    assert report["hardware_access_attempted"] is False
    assert report["physical_release_effect"] == "NONE"
