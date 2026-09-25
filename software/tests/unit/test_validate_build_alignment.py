from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


WORKSPACE = Path(__file__).resolve().parents[3]
TOOL_PATH = WORKSPACE / "software/tools/validate_build_alignment.py"


def test_release_validator_tracks_the_six_artifact_simulation_bundle() -> None:
    """Keep the independent build check synchronized with runtime bundle v006."""

    spec = importlib.util.spec_from_file_location(
        "validate_build_alignment_test",
        TOOL_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.SIMULATION_BUNDLE_ARTIFACT_PATHS[
        "virtual_commissioning_profile"
    ] == "software/config/virtual_commissioning_profile.json"
    assert len(module.SIMULATION_BUNDLE_ARTIFACT_PATHS) == 6


def test_current_freeze_passes_alignment_with_physical_holds_preserved() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL_PATH)],
        cwd=WORKSPACE,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED"
    assert report["contact_enabled"] is False
    assert report["errors"] == []
    assert "PHYSICAL_GATES_INCOMPLETE" in report["blockers"]

