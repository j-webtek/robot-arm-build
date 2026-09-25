from __future__ import annotations

from pathlib import Path

from rocell.application.context import load_simulation_context
from rocell.application.reach_optimizer import default_reach_study_inputs
from rocell.application.virtual_calibrations import resolve_virtual_calibrations
from rocell.calibration import ordered_requirement_closure
from rocell.typing import compile_development_text


WORKSPACE = Path(__file__).resolve().parents[3]


def test_virtual_keyboard_closure_is_complete_but_never_physical() -> None:
    context = load_simulation_context(
        WORKSPACE,
        WORKSPACE / "software/config/system_manifest.json",
    )
    plan = compile_development_text("keyboard", "aa")
    study = default_reach_study_inputs(context)[0]

    closure = resolve_virtual_calibrations(context, plan, study)
    document = closure.to_dict()

    assert closure.ordered == ordered_requirement_closure(plan.required_calibrations)
    assert tuple(row.artifact_id for row in closure.surrogates) == closure.ordered
    assert document["all_virtual_requirements_resolved"] is True
    assert document["physical_calibration_ready"] is False
    assert document["physical_release_effect"] == "NONE"
    assert set(document["physical_blockers"]) == set(closure.ordered)
    assert len(closure.closure_hash) == 64
    assert all(
        row["resolution"] == "VIRTUAL_SURROGATE"
        and row["physical_artifact_valid"] is False
        for row in document["surrogates"]
    )


def test_virtual_phone_closure_uses_device_specific_surrogates() -> None:
    context = load_simulation_context(
        WORKSPACE,
        WORKSPACE / "software/config/system_manifest.json",
    )
    plan = compile_development_text("phone", "a")
    study = default_reach_study_inputs(context)[0]

    closure = resolve_virtual_calibrations(context, plan, study)
    rows = {row.artifact_id: row for row in closure.surrogates}

    assert "phone_screen" in rows
    assert "phone_tcp" in rows
    assert "phone_ui_observer" in rows
    assert "keyboard_pose" not in rows
    assert dict(rows["phone_tcp"].source_bindings)["tool_length_mm"] == (
        f"{study.phone_tool_length_mm:.17g}"
    )
