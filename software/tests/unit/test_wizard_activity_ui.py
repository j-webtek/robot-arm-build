"""Retained launch history through the actual renderer; no hardware providers.

The finite DOM checks attached result rows and exact read-only requests. One
service integration fixture produces real note records in a temporary log root.
Neither browsing history nor loading a result may prepare or replay an action.
"""

from copy import deepcopy
import json
import shutil
import subprocess

import pytest

from rocell.application.wizard_actions import ACTIONS
from test_arrival_wizard_device_selection_ui import _HARNESS, WORKSPACE
from test_arrival_wizard_service import _run, make_service
from test_wizard_camera_next_step_ui import fresh


def operation(index=0, **overrides):
    value = dict(
        operation_id=f"op-{index}",
        action_id="camera_rehearsal",
        label=f"Example diagnostic {index}",
        status="SUCCEEDED",
        result_retention="FULL_JSON_RETAINED",
        completion_log_persisted=True,
    )
    value.update(overrides)
    return value


def view(operations=()):
    snapshot = fresh([action.view(mode="rehearsal", busy=False) for action in ACTIONS])
    snapshot.update(
        operations=list(operations),
        exports=dict(directory="assigned-exports", items=[]),
    )
    return snapshot


def render(snapshot, *, steps=(), results=None, page="activity", during_load=None):
    assert shutil.which("node"), "Node is required for Activity UI acceptance"
    before = deepcopy(snapshot)
    harness = (
        _HARNESS.replace(
            "function find(id)",
            """function matching(predicate){
  const walk=node=>predicate(node)?node:node.children.map(walk).find(Boolean);
  return walk(find('#page-content'));
}
function attached(id){return matching(node=>node.id===id);}
const observations=[],saved=new Map();
function find(id)""",
        )
        .replace(
            "global.document={querySelector:find,",
            "global.document={getElementById:attached,createElementNS:(_,tag)=>new Element(tag),querySelector:find,",
        )
        .replace(
            "focus(){}", "focus(){document.activeElement=this;} scrollIntoView(){}"
        )
        .replace(
            "throw new Error('Unexpected request: '+path);",
            """if(path.startsWith('/api/operations/')){
    if(input.during_load){input.snapshot=input.during_load;input.during_load=null;await find('#refresh-button').onclick();}
    const result=input.results?.[decodeURIComponent(path.slice('/api/operations/'.length))];
    if(result?.http_error)return{ok:false,status:404,json:async()=>({error:{message:'Operation unavailable in this launch'}})};
    if(!result)throw Error('No modeled result');
    return{ok:true,json:async()=>result};
  }
  throw new Error('Unexpected request: '+path);""",
        )
        .replace(
            "if(input.prepare){",
            """const contentText=node=>[node.textContent,...node.children.map(contentText)].join('\\n');
  function observe(){
    const rows=[],buttons=[];
    const walk=node=>{
      if(node['data-history-operation'])rows.push({id:node['data-history-operation'],text:contentText(node)});
      if(node['data-load-operation'])buttons.push({id:node['data-load-operation'],disabled:!!node.disabled,label:node.textContent});
      node.children.forEach(walk);
    };walk(find('#page-content'));
    observations.push({rows,buttons,text:contentText(find('#page-content')),page:find('#page-title').textContent,
      status:attached('activity-results-status')?.textContent,query:attached('activity-search')?.value,
      error:find('#error-banner').textContent});
  }
  observe();
  for(const step of input.steps){
    if(step.field){const field=attached(step.field);field.value=step.value;await field.listeners[step.field==='activity-search'?'input':'change']();}
    if(step.button){const button=matching(node=>node.tagName==='BUTTON'&&node.textContent===step.button);if(!button)throw Error('Missing button');if(!button.disabled)await button.listeners.click();}
    if(step.save)saved.set(step.save,matching(node=>node['data-load-operation']===step.save));
    if(step.view){input.snapshot=step.view;await find('#refresh-button').onclick();}
    if(step.page)find('#navigation').listeners.click({target:{closest:()=>({dataset:{page:step.page}})}});
    if(step.load){const button=matching(node=>node['data-load-operation']===step.load);if(!button)throw Error('Missing load');if(!button.disabled)await button.listeners.click();}
    if(step.stale)await saved.get(step.stale).listeners.click();
    observe();
  }
  if(input.prepare){""",
        )
        .replace(
            "JSON.stringify({requests,text:",
            "JSON.stringify({requests,observations,text:",
        )
    )
    result = subprocess.run(
        [shutil.which("node"), "-e", harness],
        input=json.dumps(
            dict(
                script=(WORKSPACE / "software/src/rocell/ui/static/app.js").read_text(
                    encoding="utf-8"
                ),
                snapshot=snapshot,
                page=page,
                steps=steps,
                results=results or {},
                during_load=during_load,
            )
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    assert rendered["status"] == "Local service connected", rendered["error"]
    assert snapshot == before and rendered["dialogOpen"] is False
    assert all(
        row["method"] == "GET" and row["body"] is None for row in rendered["requests"]
    )
    return rendered


def result_reads(page):
    return [row["path"] for row in page["requests"] if row["path"] != "/api/view"]


def test_all_32_retained_summaries_are_reachable_without_loading_any():
    page = render(
        view(operation(index) for index in range(32)),
        steps=[dict(button="Older results")] * 3,
    )
    ids = [row["id"] for state in page["observations"] for row in state["rows"]]
    assert ids == [f"op-{index}" for index in reversed(range(32))]
    assert "page 4 of 4" in page["observations"][-1]["status"]
    assert not result_reads(page)


def test_recent_activity_links_to_the_complete_retained_history():
    page = render(
        view(operation(index) for index in range(13)),
        page="overview",
        steps=[dict(button="Review all 13 retained operations")],
    )
    assert len(page["observations"][0]["rows"]) == 6
    assert len(page["observations"][1]["rows"]) == 8
    assert page["observations"][1]["page"] == "Activity & results"
    assert not result_reads(page)


def test_search_component_and_status_filters_do_not_load_results():
    camera = operation(
        0,
        status="FAILED",
        error=dict(code="FOCUS_HELD", remediation="Review lens evidence"),
    )
    arm = operation(1, action_id="record_note", status="TIMED_OUT")
    page = render(
        view([camera, arm]),
        steps=[
            dict(field="activity-search", value="lens evidence"),
            dict(field="activity-section", value="diagnostics"),
            dict(button="Clear activity filters"),
            dict(field="activity-status", value="TIMED_OUT"),
        ],
    )
    assert [row["id"] for row in page["observations"][1]["rows"]] == ["op-0"]
    assert page["observations"][2]["rows"] == []
    assert len(page["observations"][3]["rows"]) == 2
    assert [row["id"] for row in page["observations"][4]["rows"]] == ["op-1"]
    assert not result_reads(page)


@pytest.mark.parametrize(
    "status,meaning",
    [
        ("QUEUED", "Queued by the service"),
        ("PENDING", "Pending; completion"),
        ("RUNNING", "Running according"),
        ("CANCEL_REQUESTED", "Cancellation requested, not confirmed"),
        ("CANCELLED", "not proof of a robot stop"),
        ("TIMED_OUT", "effects and cleanup may be uncertain"),
        ("UNCERTAIN", "do not replay"),
        ("FAILED", "Do not automatically retry"),
        ("SUCCEEDED", "worker success is not hardware qualification"),
        ("constructor", "status is unavailable or unsupported"),
    ],
)
def test_status_meanings_never_promote_worker_outcomes_to_hardware_readiness(
    status, meaning
):
    page = render(view([operation(status=status)]))
    assert meaning in page["text"] and not result_reads(page)


def test_log_failure_and_omissions_are_visible_and_filterable():
    failed_log = operation(
        0,
        status="FAILED",
        completion_log_persisted=False,
        result_retention="FULL_JSON_RETAINED_COMPLETION_LOG_FAILED",
        action_outcome_before_log_failure="SUCCEEDED",
    )
    omitted = operation(1, result_retention="OMITTED_OLDER_THAN_LAST_EIGHT_RESULTS")
    page = render(
        view([failed_log, omitted, operation(2)]),
        steps=[dict(field="activity-status", value="attention")],
    )
    assert len(page["observations"][-1]["rows"]) == 2
    assert "action may already have taken effect" in page["text"]
    assert "a new export cannot recreate omitted data" in page["text"]
    assert not result_reads(page)


def test_load_is_an_explicit_single_read_and_navigation_retains_matching_cache():
    op = operation()
    page = render(
        view([op]),
        results={"op-0": dict(op, result={"unique_payload": "retained-only"})},
        steps=[
            dict(load="op-0"),
            dict(page="diagnostics"),
            dict(page="activity"),
        ],
    )
    assert result_reads(page) == ["/api/operations/op-0"]
    assert "retained-only" in page["text"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("result_retention", "OMITTED_OLDER_THAN_LAST_EIGHT_RESULTS"),
        ("result_sha256", "b" * 64),
        ("completion_log_persisted", False),
        ("status", "FAILED"),
    ],
)
def test_cache_is_not_displayed_after_retention_or_summary_changes(field, value):
    op = operation()
    changed = dict(op, **{field: value})
    page = render(
        view([op]),
        results={"op-0": dict(op, result={"unique_payload": "old-cache-payload"})},
        steps=[dict(load="op-0"), dict(view=view([changed]))],
    )
    assert "old-cache-payload" in page["observations"][1]["text"]
    assert "old-cache-payload" not in page["observations"][-1]["text"]
    assert result_reads(page) == ["/api/operations/op-0"]


@pytest.mark.parametrize("change", ["removed", "duplicate", "new_session", "retention"])
def test_detached_result_button_rechecks_current_launch_and_summary(change):
    initial = view([operation()])
    changed = deepcopy(initial)
    if change == "removed":
        changed["operations"] = []
    if change == "duplicate":
        changed["operations"] *= 2
    if change == "new_session":
        changed["session_id"] = "different-launch"
    if change == "retention":
        changed["operations"][0][
            "result_retention"
        ] = "OMITTED_OLDER_THAN_LAST_EIGHT_RESULTS"
    page = render(
        initial, steps=[dict(save="op-0"), dict(view=changed), dict(stale="op-0")]
    )
    assert "changed" in page["error"] and not result_reads(page)


def test_late_result_from_replaced_launch_is_not_cached_or_presented():
    initial = view([operation()])
    changed = dict(initial, session_id="replacement-launch")
    page = render(
        initial,
        results={"op-0": dict(operation(), result={"payload": "stale-full-data"})},
        during_load=changed,
        steps=[dict(load="op-0"), dict(page="activity")],
    )
    assert "changed while loading" in page["error"]
    assert "stale-full-data" not in page["text"]
    assert result_reads(page) == ["/api/operations/op-0"]


@pytest.mark.parametrize(
    "overrides", [dict(operation_id="another-op"), dict(action_id="record_note")]
)
def test_mismatched_result_identity_is_rejected_without_retry(overrides):
    full = dict(operation(), result={"payload": "mismatched-data"}, **overrides)
    page = render(
        view([operation()]), results={"op-0": full}, steps=[dict(load="op-0")]
    )
    assert "does not match" in page["error"]
    assert "mismatched-data" not in page["text"]
    assert result_reads(page) == ["/api/operations/op-0"]


def test_missing_result_reports_recovery_without_retry():
    page = render(
        view([operation()]),
        results={"op-0": dict(http_error=True)},
        steps=[dict(load="op-0")],
    )
    assert "unavailable in this launch" in page["error"]
    assert result_reads(page) == ["/api/operations/op-0"]


@pytest.mark.parametrize("operations", [None, "broken", [operation()] * 257])
def test_unsupported_history_is_not_silently_truncated(operations):
    snapshot = view()
    snapshot["operations"] = operations
    page = render(snapshot)
    assert "No entries are silently omitted" in page["text"]
    assert not result_reads(page)


def test_duplicate_and_malformed_entries_cannot_load_a_record():
    page = render(view([operation(), operation(), None, operation(2, action_id=None)]))
    assert all(row["disabled"] for row in page["observations"][0]["buttons"])
    assert "Unsupported operation summary" in page["text"]
    assert not result_reads(page)


def test_unknown_historical_action_remains_inspectable_without_inventing_component():
    page = render(
        view([operation(action_id="retired_action")]),
        steps=[dict(field="activity-section", value="unmapped")],
    )
    assert len(page["observations"][-1]["rows"]) == 1
    assert page["observations"][-1]["buttons"][0]["disabled"] is False
    assert not result_reads(page)


def test_empty_filters_paging_preferences_and_exports_navigation_are_read_only():
    page = render(
        view(),
        steps=[dict(button="Review diagnostics & exports"), dict(page="activity")],
    )
    assert "No operations are retained" in page["text"]
    assert page["observations"][1]["page"] == "Diagnostics & exports"
    assert "assigned-exports" in page["text"] and not result_reads(page)
    page = render(
        view(operation(index) for index in range(12)),
        steps=[
            dict(button="Older results"),
            dict(page="controls"),
            dict(page="activity"),
        ],
    )
    assert "page 2 of 2" in page["observations"][-1]["status"]
    assert not result_reads(page)


def test_real_service_history_beyond_six_and_result_rotation_is_visible(make_service):
    service, runner, _ = make_service()
    produced = [
        _run(service, "record_note", {"note": f"Hardware-free UI fixture {index}"})
        for index in range(35)
    ]
    snapshot = service.view()
    oldest = produced[3]["operation_id"]
    page = render(
        snapshot,
        results={oldest: service.operation(oldest)},
        steps=[dict(button="Older results")] * 3 + [dict(load=oldest)],
    )
    assert len(snapshot["operations"]) == 32
    assert produced[0]["operation_id"] not in {
        row["operation_id"] for row in snapshot["operations"]
    }
    assert (
        service.operation(oldest)["result_retention"]
        == "OMITTED_OLDER_THAN_LAST_EIGHT_RESULTS"
    )
    assert "Full result is no longer retained" in page["text"]
    assert result_reads(page) == [f"/api/operations/{oldest}"]
    assert not runner.calls and service.view() == snapshot


def test_preview_history_is_fictional_and_all_actions_are_disabled():
    import runpy

    preview = runpy.run_path(str(WORKSPACE / "software/scripts/camera_ui_preview.py"))
    snapshot, _ = preview["example_view"]("activity")
    records = preview["example_activity"]()
    assert len(snapshot["operations"]) == len(records) == 17
    assert all(action["enabled"] is False for action in snapshot["actions"])
    assert {row["operation_id"] for row in snapshot["operations"]} == set(records)
    assert snapshot["physical_authority"] is False


def test_unknown_status_filter_and_active_filter_are_distinct():
    snapshot = view(
        [operation(0, status="RUNNING"), operation(1, status="UNRECOGNIZED")]
    )
    page = render(
        snapshot,
        steps=[
            dict(field="activity-status", value="active"),
            dict(field="activity-status", value="unknown"),
        ],
    )
    assert [row["id"] for row in page["observations"][1]["rows"]] == ["op-0"]
    assert [row["id"] for row in page["observations"][2]["rows"]] == ["op-1"]
    assert not result_reads(page)


def test_object_history_and_page_clamping_never_hide_available_rows():
    snapshot = view([operation(index) for index in range(12)])
    snapshot["operations"] = {
        row["operation_id"]: row for row in snapshot["operations"]
    }
    page = render(
        snapshot, steps=[dict(button="Older results"), dict(view=view([operation(0)]))]
    )
    assert "page 1 of 1" in page["observations"][-1]["status"]
    assert [row["id"] for row in page["observations"][-1]["rows"]] == ["op-0"]
    assert not result_reads(page)


@pytest.mark.parametrize(
    "field", ["session_id", "cell_id", "source_binding_sha256", "mode"]
)
def test_previous_context_cache_is_not_restored(field):
    initial = view([operation()])
    changed = dict(initial, **{field: "different-context"})
    page = render(
        initial,
        results={
            "op-0": dict(operation(), result={"payload": "previous-context-data"})
        },
        steps=[dict(load="op-0"), dict(view=changed)],
    )
    assert "previous-context-data" not in page["observations"][-1]["text"]
    assert result_reads(page) == ["/api/operations/op-0"]
