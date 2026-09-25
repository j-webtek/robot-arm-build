"""Compact retained resolution summaries only; no worker/native execution."""

from copy import deepcopy
import ctypes
from pathlib import Path
import subprocess

import pytest

from rocell.ui.terminal import _arm_process, _arm_resolution, _TerminalWizard
from test_arrival_wizard_terminal import Service
from test_wizard_owned_arm_feedback_ui import render as _render, summary


LIMITATIONS = [
    "METADATA_SNAPSHOT_NOT_ATOMIC_COM_TO_HANDLE_BINDING",
    "GENERIC_UNIT_SERIAL_NOT_USB_DESCRIPTOR_VERIFICATION",
    "ARM_MODEL_FIRMWARE_BOOT_AND_POWER_NOT_OBSERVED",
    "PHYSICAL_BACKEND_AND_RELEASE_REMAIN_HELD",
]


def render(value):
    original = subprocess.run

    def utf8(*args, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        return original(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "run", utf8)
        return _render(value)


def projection(attempts=2):
    value = summary()
    value["schema"] = "rocell.arm_owned_evidence_summary.v2"
    value["resolution"] = {
        "schema": "rocell.arm_controller_resolution_trace_summary.v1",
        "trace_sha256": "1" * 64,
        "reviewed_binding_sha256": value["native"]["controller_binding_sha256"],
        "origin": "SYNTHETIC_REHEARSAL",
        "attempt_count": attempts,
        "attempts": [
            {
                "phase": phase,
                "status": "MATCHED_METADATA_ONLY",
                "snapshot_sha256": str(i + 2) * 64,
                "resolution_sha256": str(i + 4) * 64,
                "error_code": None,
            }
            for i, phase in enumerate(("PRE_OPEN", "PRE_WRITE")[:attempts])
        ],
        "status": ("NOT_ATTEMPTED", "PRE_OPEN_MATCHED", "PRE_WRITE_MATCHED")[attempts],
        "physical_authority": False,
        "arm_connected": False,
        "qualified": False,
        "limitations": deepcopy(LIMITATIONS),
    }
    if attempts < 2:
        value["feedback"]["status"] = (
            "BLOCKED_PRE_OPEN" if not attempts else "FAILED_UNCERTAIN"
        )
        value["native"]["worker_status"] = value["feedback"]["status"]
    return value


def panel(text):
    return text.split("Controller metadata checks before open and before write", 1)[
        1
    ].split("Modeled serial feedback validity", 1)[0]


def test_historical_v1_is_not_rewritten_or_treated_as_current_trace():
    value = summary()
    original = deepcopy(value)
    assert _arm_process(value) == value
    for output in render(value):
        text = panel(output)
        assert "NOT_RETAINED" in text and "historical record format" in text
        assert "Do not infer these checks ran or replay" in text
        assert "Acquisition snapshot:" not in text
        assert "ARM_PROCESS_NOT_VERIFIED" not in output
    assert value == original and "resolution" not in value


def test_current_format_missing_trace_is_not_historical_or_a_match():
    value = projection()
    value.update(status="INCOMPLETE", resolution=None)
    value["blockers"] = ["CONTROLLER_RESOLUTION_EVIDENCE_UNAVAILABLE"]
    assert _arm_process(value) == value
    for output in render(value):
        text = panel(output)
        assert "NOT_RETAINED" in text and "current-format result" in text
        assert "historical record format" not in text
        assert "Missing trace is not a metadata match" in text
        assert "ARM_PROCESS_NOT_VERIFIED" not in output


@pytest.mark.parametrize("attempts", [0, 1, 2])
def test_each_retained_boundary_and_absence_is_reported_separately(attempts):
    value = projection(attempts)
    original = deepcopy(value)
    assert _arm_resolution(value["resolution"], value) == value["resolution"]
    assert _arm_process(value) == value
    for output in render(value):
        text = panel(output)
        assert "SYNTHETIC ONLY" in text
        assert "PRE_OPEN — before serial open" in text
        assert "PRE_WRITE — before the one feedback request" in text
        assert text.count("Acquisition snapshot: RETAINED") == attempts
        assert text.count("Metadata comparison report: RETAINED") == attempts
        assert text.count("Boundary result: MATCHED_METADATA_ONLY") == attempts
        assert text.count("NOT_ATTEMPTED: no boundary attempt") == 2 - attempts
        assert f"Trace status: {value['resolution']['status']}" in text
        assert value["resolution"]["trace_sha256"] in text
        assert "not an independent successful acquisition or match" in text
        assert "Physical backend and release remain held" in text
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
    assert value == original


@pytest.mark.parametrize(
    "snapshot,comparison", [(False, False), (True, False), (True, True)]
)
def test_boundary_hold_separates_snapshot_report_retention_from_verdict(
    snapshot, comparison
):
    value = projection()
    trace = value["resolution"]
    trace["status"] = "HELD"
    row = trace["attempts"][1]
    row.update(status="HELD", error_code="CONTROLLER_METADATA_HELD")
    if not snapshot:
        row["snapshot_sha256"] = None
    if not comparison:
        row["resolution_sha256"] = None
    assert _arm_process(value) == value
    for output in render(value):
        text = panel(output).split("PRE_WRITE —", 1)[1]
        assert (
            "Acquisition snapshot: " + ("RETAINED" if snapshot else "NOT_RETAINED")
            in text
        )
        assert (
            "Metadata comparison report: "
            + ("RETAINED" if comparison else "NOT_RETAINED")
            in text
        )
        assert "Boundary result: HELD" in text and "CONTROLLER_METADATA_HELD" in text
        assert "acquisition failed" not in text.lower()
        assert "Boundary result: MATCHED_METADATA_ONLY" not in text


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(schema="rocell.arm_owned_evidence_summary.v3"),
        lambda v: v.update(resolution=None),
        lambda v: v["resolution"].update(extra="RAW_SENTINEL"),
        lambda v: v["resolution"].update(schema="unknown"),
        lambda v: v["resolution"].update(attempt_count=True),
        lambda v: v["resolution"].update(attempt_count=3),
        lambda v: v["resolution"].update(attempt_count=1),
        lambda v: v["resolution"].update(status="PASS"),
        lambda v: v["resolution"].update(status="PRE_OPEN_MATCHED"),
        lambda v: v["resolution"].update(origin="PHYSICAL_OBSERVATION"),
        lambda v: v["resolution"].update(physical_authority=True),
        lambda v: v["resolution"].update(arm_connected=True),
        lambda v: v["resolution"].update(qualified=0),
        lambda v: v["resolution"].update(trace_sha256="g" * 64),
        lambda v: v["resolution"].update(reviewed_binding_sha256="0" * 64),
        lambda v: v["resolution"].update(limitations=[]),
        lambda v: v["resolution"]["attempts"][0].update(phase="PRE_WRITE"),
        lambda v: v["resolution"]["attempts"][1].update(phase="PRE_OPEN"),
        lambda v: v["resolution"]["attempts"][0].update(
            status="HELD", error_code="CONTROLLER_METADATA_HELD"
        ),
        lambda v: v["resolution"]["attempts"][1].update(snapshot_sha256=None),
        lambda v: v["resolution"]["attempts"][1].update(resolution_sha256=None),
        lambda v: v["resolution"]["attempts"][1].update(error_code="CM_LIST_CHANGED"),
        lambda v: v["resolution"]["attempts"][1].update(
            status="HELD", error_code="RAW_SENTINEL"
        ),
        lambda v: v["resolution"]["attempts"][1].update(
            error_code={"raw": "RAW_SENTINEL"}
        ),
        lambda v: v["resolution"]["attempts"][1].update(raw_port="RAW_SENTINEL"),
    ],
)
def test_malformed_or_unbound_trace_is_withheld_without_raw_fallback(change):
    value = projection()
    change(value)
    assert _arm_process(value) is None
    for output in render(value):
        assert "ARM PROCESS NOT VERIFIED" in output.replace("_", " ")
        assert "RAW_SENTINEL" not in output
        assert "Trace status:" not in output


def test_terminal_display_has_no_metadata_or_file_acquisition(monkeypatch):
    from rocell.application.arm_controller_resolution import (
        ExplicitArmControllerResolver,
    )

    def denied(*_a, **_k):
        pytest.fail("Cached trace display attempted acquisition or file/process I/O")

    output = []
    wizard = _TerminalWizard(
        Service([]), lambda _: "quit", output.append, lambda _: None
    )
    with monkeypatch.context() as guard:
        for name in ("open", "stat", "read_bytes", "read_text"):
            guard.setattr(Path, name, denied)
        guard.setattr(subprocess, "Popen", denied)
        guard.setattr(ExplicitArmControllerResolver, "__call__", denied)
        wizard.show_arm_process(projection())
    assert any("PRE_WRITE_MATCHED" in str(line) for line in output)


@pytest.mark.parametrize(
    "scenario,legacy,attempts,status",
    [
        ("nominal", False, 2, "PRE_WRITE_MATCHED"),
        ("identity-change-preopen", False, 1, "HELD"),
        ("identity-change", False, 2, "HELD"),
        ("malformed-metadata", False, 1, "HELD"),
        ("nominal", True, None, None),
    ],
)
def test_real_incapable_resolver_worker_codec_to_both_cached_renderers(
    monkeypatch, scenario, legacy, attempts, status
):
    """Actual CM codec/resolver/worker; memory API and modeled process fields."""
    from test_arm_owned_evidence import owned_fixture

    def denied(*_a, **_k):
        pytest.fail("Pure producer crosscheck attempted a DLL or real process")

    with monkeypatch.context() as guard:
        guard.setattr(ctypes, "WinDLL", denied, raising=False)
        guard.setattr(subprocess, "Popen", denied)
        fixture = owned_fixture(legacy=legacy, metadata_scenario=scenario)
        value = fixture[9].safe_summary()
    original = deepcopy(value)
    assert _arm_process(value) == value
    assert value["physical_authority"] is False
    assert value["arm_connected"] is False
    assert value["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    if legacy:
        assert value["schema"] == "rocell.arm_owned_evidence_summary.v1"
        assert "resolution" not in value
    else:
        assert value["schema"] == "rocell.arm_owned_evidence_summary.v2"
        trace = value["resolution"]
        assert trace["attempt_count"] == attempts and trace["status"] == status
        assert (
            trace["reviewed_binding_sha256"]
            == value["native"]["controller_binding_sha256"]
        )
        assert fixture[2].api_counts.write_attempts == int(scenario == "nominal")
    # The shared fake-DOM harness requires exactly one GET /api/view, unchanged
    # controls, and no prepare/execute; it never constructs an application.
    for output in render(value):
        assert "ARM PROCESS NOT VERIFIED" not in output.replace("_", " ")
        text = panel(output)
        if legacy:
            assert "historical record format" in text and "NOT_RETAINED" in text
        else:
            assert f"Trace status: {status}" in text
            assert trace["trace_sha256"] in text and "SYNTHETIC ONLY" in text
            for row in trace["attempts"]:
                assert f"Boundary result: {row['status']}" in text
                for key in ("snapshot_sha256", "resolution_sha256", "error_code"):
                    if row[key] is not None:
                        assert row[key] in text
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "None proves physical de-energization" in output
    assert value == original
