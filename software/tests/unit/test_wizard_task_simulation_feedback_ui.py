"""Task outcomes are diagnostic interpretation, not worker or motion authority.

Run the actual renderer with a finite DOM and service-summary-shaped fixtures.
No solver, camera, serial port, device inventory or worker is launched here.
"""

from copy import deepcopy
import json
import shutil
import subprocess

import pytest

from test_arrival_wizard_device_selection_ui import _HARNESS, WORKSPACE
from test_wizard_camera_next_step_ui import fresh


GAPS = "PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS"
PASS = "PASS_SIMULATION_ONLY_WITH_PHYSICAL_HOLDS"
FAIL = "FAIL_SIMULATION_ONLY"
UNINTERPRETED = "Simulation outcome is unavailable or inconsistent."
PENDING = "Simulation has not completed; no feasibility result is inferred."


def operation(report_status=GAPS):
    failed = report_status == FAIL
    return {
        "operation_id": "operation-" + "a" * 32,
        "action_id": "simulate_task",
        "status": "FAILED" if failed else "SUCCEEDED",
        "message": "Diagnostic worker finished",
        "steps": [
            {
                "name": "simulate_task",
                "exit_code": 1 if failed else 0,
                "report_status": report_status,
            }
        ],
    }


def render(item, *, page="tasks", refresh=False):
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node runtime unavailable")
    # Read only the attached tree, and distinguish immediately visible text
    # from evidence inside closed disclosures. A raw JSON detail is not a warning.
    harness = _HARNESS.replace(
        "if(input.prepare){",
        "if(input.refresh)await find('#refresh-button').onclick(); if(input.prepare){",
    ).replace(
        "process.stdout.write(JSON.stringify({requests,text:",
        """const warnings=[];
  const walk=(node,visible=true)=>{
    visible=visible && !node.hidden;
    if(node.className.split(' ').includes('task-simulation-feedback'))
      warnings.push({text:treeText(node),visible});
    for(const child of node.children)walk(child,visible && (node.tagName!=='DETAILS' || node.open || child.tagName==='SUMMARY'));
  };
  walk(find('#page-content'));
  process.stdout.write(JSON.stringify({requests,warnings,text:""",
    )
    view = fresh([])
    view["operations"] = [item] if item is not None else []
    before = deepcopy(view)
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": (
                    WORKSPACE / "software/src/rocell/ui/static/app.js"
                ).read_text(encoding="utf-8"),
                "snapshot": view,
                "page": page,
                "refresh": refresh,
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    result_page = json.loads(result.stdout)
    assert result_page["status"] == "Local service connected", result_page["error"]
    assert result_page["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None}
    ] * (2 if refresh else 1)
    assert result_page["dialogOpen"] is False and view == before
    return result_page


@pytest.mark.parametrize(
    "status,meaning",
    [
        (GAPS, "Simulation completed with unresolved reachability checks."),
        (
            PASS,
            "Sampled nominal IK checks converged; the complete path is not qualified.",
        ),
        (FAIL, "Required simulation checks failed."),
    ],
)
@pytest.mark.parametrize("page", ["tasks", "diagnostics"])
def test_visible_outcome_is_distinct_from_process_success(status, meaning, page):
    item = operation(status)
    result = render(item, page=page)
    assert len(result["warnings"]) == 1
    warning = result["warnings"][0]
    assert warning["visible"] and meaning in warning["text"]
    assert "Worker status: " + item["status"] in result["text"]
    assert "not permission to move" in warning["text"]
    assert "Load the full retained result" in warning["text"]


def malformed_cases():
    for field in ("steps",):
        item = operation()
        del item[field]
        yield item
    for steps in (None, {}, [], [None], ["simulate_task"], [["simulate_task"]]):
        yield {**operation(), "steps": steps}
    item = operation()
    item["steps"].append(deepcopy(item["steps"][0]))
    yield item
    for field, invalid in (
        ("name", "camera_rehearsal"),
        ("name", None),
        ("report_status", "PASS"),
        ("report_status", None),
        ("report_status", True),
        ("report_status", {"status": GAPS}),
        ("exit_code", "0"),
        ("exit_code", False),
        ("exit_code", None),
        ("exit_code", 0.5),
        ("exit_code", 1),
    ):
        item = operation()
        item["steps"][0][field] = invalid
        yield item
    for status, worker_status, exit_code in (
        (FAIL, "SUCCEEDED", 0),
        (PASS, "FAILED", 1),
    ):
        item = operation(status)
        item["status"] = worker_status
        item["steps"][0]["exit_code"] = exit_code
        yield item


@pytest.mark.parametrize("item", list(malformed_cases()))
def test_missing_ambiguous_or_inconsistent_summary_is_not_optimistic(item):
    result = render(item)
    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["visible"]
    assert UNINTERPRETED in result["warnings"][0]["text"]
    assert "Sampled nominal IK checks converged" not in result["warnings"][0]["text"]


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING", "CANCELLED", "TIMED_OUT"])
def test_unfinished_or_interrupted_worker_cannot_publish_feasibility(status):
    item = operation(PASS)
    item["status"] = status
    result = render(item)
    assert PENDING in result["warnings"][0]["text"]
    assert "Sampled nominal IK checks converged" not in result["warnings"][0]["text"]


@pytest.mark.parametrize("action", ["plan_task", "camera_rehearsal", "arm_rehearsal"])
def test_foreign_action_does_not_inherit_task_interpretation(action):
    item = operation()
    item["action_id"] = action
    result = render(item)
    assert result["warnings"] == []
    assert "Worker status:" not in result["text"]


def test_task_page_discloses_legacy_camera_model_even_without_an_operation():
    result = render(None)
    assert "locked legacy arm-mounted-camera calibration graph" in result["text"]
    assert (
        "has not yet been migrated to the selected static overhead camera"
        in result["text"]
    )
    assert "do not validate overhead-camera calibration" in result["text"]
    assert result["warnings"] == []


def test_explicit_read_only_refresh_preserves_the_warning_without_result_fetch():
    result = render(operation(), refresh=True)
    assert len(result["warnings"]) == 1
    assert "unresolved reachability checks" in result["warnings"][0]["text"]
