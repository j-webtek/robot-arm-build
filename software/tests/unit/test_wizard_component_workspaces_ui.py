"""Component navigation and field accessibility against real cached service views.

The browser DOM and HTTP reads are modeled; forms are never submitted here.
The service uses the existing incapable runner and temporary diagnostic roots.
The export case runs only explicit note and file-export service actions.
"""

from copy import deepcopy
import json
import shutil
import subprocess

import pytest

from test_arrival_wizard_device_selection_ui import _HARNESS, WORKSPACE
from test_arrival_wizard_service import _run, make_service


PAGES = ("overview", "commissioning", "camera", "arm", "board", "tasks", "diagnostics")
GUIDES = {
    "arm": "Arm",
    "board": "Board & tests",
    "tasks": "Task rehearsal",
    "diagnostics": "Diagnostics & exports",
}


def render(snapshot, *, page="overview", steps=()):
    """Traverse attached nodes, not old forms retained by a finite DOM harness."""
    assert shutil.which("node"), "Node is required for operator UI acceptance"
    before = deepcopy(snapshot)
    harness = (
        _HARNESS.replace(
            "append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}",
            "append(...items){for(const item of items)item.parentElement=this;this.children.push(...items);} replaceChildren(...items){this.children=[];this.append(...items);}",
        )
        .replace(
            "function find(id)",
            """function walk(node){return [node,...node.children.flatMap(walk)];}
function attached(id){return walk(find('#page-content')).find(node=>node.id===id);}
const observations=[];
function find(id)""",
        )
        .replace(
            "global.document={querySelector:find,",
            "global.document={getElementById:attached,createElementNS:(_,tag)=>new Element(tag),querySelector:find,",
        )
        .replace(
            "focus(){}",
            "focus(){document.activeElement=this;} scrollIntoView(options){this.scrollOptions=options;}",
        )
        .replace(
            "if(input.prepare){",
            """function observe(){
    const all=walk(find('#page-content'));
    const forms=all.filter(node=>node.tagName==='FORM').map(form=>({
      id:form.parentElement.id,name:form['aria-label'],
      fields:walk(form).filter(node=>['INPUT','SELECT','TEXTAREA'].includes(node.tagName)).map(control=>({
        id:control.id,tag:control.tagName,disabled:!!control.disabled,
        labelCount:all.filter(node=>node.tagName==='LABEL'&&node.htmlFor===control.id).length,
        descriptionId:control['aria-describedby']||null,
        descriptionExists:!control['aria-describedby']||!!attached(control['aria-describedby'])
      }))
    }));
    const raw=all.find(node=>node.tagName==='DETAILS'&&node.children.some(child=>child.tagName==='SUMMARY'&&child.textContent==='Read-only service snapshot'));
    observations.push({page:find('#page-title').textContent,
      text:all.map(node=>node.textContent).join('\\n'),forms,
      ids:all.filter(node=>node.id).map(node=>node.id),
      raw:raw?JSON.parse(raw.children.find(node=>node.tagName==='PRE').textContent):null,
      rawMatchesBrowserView:raw?JSON.stringify(JSON.parse(raw.children.find(node=>node.tagName==='PRE').textContent))===JSON.stringify(input.snapshot):false,
      controlsFilter:attached('control-section')?.value,
      activityFilter:attached('activity-section')?.value,
      focusedMain:document.activeElement===find('#main'),
      workspaceScroll:find('#main').scrollOptions||null,
      guideButtons:all.filter(node=>node.tagName==='BUTTON'&&node.parentElement?.parentElement?.id?.endsWith('-workspace-guide')).map(node=>({label:node.textContent,type:node.type}))});
  }
  observe();
  for(const step of input.steps){
    if(step.page)find('#navigation').listeners.click({target:{closest:()=>({dataset:{page:step.page}})}});
    if(step.button){
      const button=walk(find('#page-content')).find(node=>node.tagName==='BUTTON'&&node.textContent===step.button);
      if(!button||button.disabled)throw Error('Navigation button unavailable');
      await (button.onclick||button.listeners.click)();
    }
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
            )
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "Local service connected", output["error"]
    assert not output["error"] and not output["dialogOpen"]
    assert output["requests"] == [dict(path="/api/view", method="GET", body=None)]
    assert snapshot == before
    return output


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_every_current_service_form_and_field_is_named_and_reachable(
    make_service, mode
):
    service, runner, _ = make_service(mode=mode)
    view = service.view()
    output = render(view, steps=[dict(page=page) for page in PAGES[1:]])
    actions = {f"{a['section']}-action-{a['action_id']}": a for a in view["actions"]}
    observed = {}
    for page in output["observations"]:
        assert len(page["ids"]) == len(set(page["ids"])), page["page"]
        for form in page["forms"]:
            # Guided rehearsal may repeat an original component form on a
            # different page. IDs must be unique within each attached page.
            if form["id"] in observed:
                assert observed[form["id"]] == form
            observed[form["id"]] = form
            action = actions[form["id"]]
            assert form["name"] == action["label"]
            expected_fields = {
                f"field-{action['action_id']}-{f['name']}": f for f in action["fields"]
            }
            assert {f["id"] for f in form["fields"]} == set(expected_fields)
            for field in form["fields"]:
                assert field["labelCount"] == 1 and field["descriptionExists"]
                if expected_fields[field["id"]].get("help"):
                    assert field["descriptionId"] == field["id"] + "-help"
                if not action["enabled"]:
                    assert field["disabled"]
    assert set(observed) == set(actions)
    # Developers can inspect every public view record even when a specialized
    # visual summary intentionally omits unverified or unsupported fields.
    assert output["observations"][-1]["raw"] == view
    assert not runner.calls
    assert all(
        stage["state"] == "PHYSICAL_PENDING" for stage in service.view()["stages"]
    )


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
@pytest.mark.parametrize("section,label", GUIDES.items())
def test_component_shortcuts_filter_current_directories_without_dispatch(
    make_service, mode, section, label
):
    service, runner, _ = make_service(mode=mode)
    view = service.view()
    output = render(
        view,
        page=section,
        steps=[
            dict(button=f"Browse {label} controls"),
            dict(page=section),
            dict(button=f"Review {label} results"),
        ],
    )
    first, controls, _, activity = output["observations"]
    entries = [a for a in view["actions"] if a["section"] == section]
    assert f"{len(entries)} registered forms" in first["text"]
    assert (
        f"{sum(a['enabled'] for a in entries)} offered by the current service"
        in first["text"]
    )
    assert all(button["type"] == "button" for button in first["guideButtons"])
    assert controls["controlsFilter"] == section
    assert activity["activityFilter"] == section
    assert controls["focusedMain"] and activity["focusedMain"]
    assert (
        controls["workspaceScroll"] == activity["workspaceScroll"] == {"block": "start"}
    )
    assert (
        f"{sum(a['enabled'] for a in entries)} offered among these matches"
        in controls["text"]
    )
    assert not runner.calls


@pytest.mark.parametrize("section", ["arm", "board", "tasks"])
def test_export_shortcut_does_not_export(make_service, section):
    service, runner, _ = make_service()
    output = render(service.view(), page=section, steps=[dict(button="Go to exports")])
    assert output["observations"][-1]["page"] == "Diagnostics & exports"
    assert service.view()["exports"]["items"] == [] and not runner.calls


@pytest.mark.parametrize("section", GUIDES)
def test_invalid_catalog_never_claims_available_counts(make_service, section):
    service, _, _ = make_service()
    view = service.view()
    view["actions"].append(deepcopy(view["actions"][0]))
    output = render(view, page=section)
    assert "Current form counts unavailable" in output["text"]
    assert "offered by the current service" not in output["text"]


def test_operator_guide_preserves_exact_export_and_recovery_records(make_service):
    service, runner, _ = make_service()
    _run(service, "record_note", {"note": "UI only: inspect_then_export <literal>"})
    operation = _run(service, "export_logs")
    assert operation["status"] == "SUCCEEDED"
    view = service.view()
    output = render(view, page="diagnostics")
    assert view["exports"]["items"]
    assert output["observations"][0]["rawMatchesBrowserView"]
    assert set(output["observations"][0]["raw"]) == set(view)
    for required in [
        view["exports"]["directory"],
        "General logs and dedicated original/attempt exports are separate",
        "Never replay an action to repair its log",
        "not prove zero effects",
    ]:
        assert required in output["text"]
    assert not runner.calls


def test_task_and_board_boundaries_remain_explicit(make_service):
    service, _, _ = make_service()
    board = render(service.view(), page="board")["text"]
    task = render(service.view(), page="tasks")["text"]
    assert "drawing, not a camera measurement" in board
    assert "legacy arm-mounted-camera calibration" in task
    assert "physical typing/tapping are not released" in task
    assert "worker's success status" in task


def test_physical_arm_diagnostic_forms_remain_visible_but_held_without_setup(
    make_service,
):
    service, runner, _ = make_service(mode="physical")
    view = service.view()
    page = render(view, page="arm")
    names = {
        "run_passive_arm_connection",
        "capture_powered_arm_telemetry",
        "run_powered_arm_feedback",
    }
    for action in view["actions"]:
        if action["action_id"] in names:
            assert not action["enabled"] and action["blocked_reasons"]
            assert action["label"] in page["text"]
    assert "General Connect and motion remain held" in page["text"]
    assert "Physical arm connection is not yet available" not in page["text"]
    assert "Even a zero-write read may reset the controller" in page["text"]
    assert not runner.calls
