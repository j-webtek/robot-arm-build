"""Ordinary in-tab drafts, dependent selections and explicit preview boundaries.

Runs the full shipped renderer with an attached-tree DOM and modeled HTTP calls.
No camera, serial provider, physical action or real application worker is used.
"""

from copy import deepcopy
import json
import shutil
import subprocess

import pytest

from rocell.application.wizard_actions import ACTIONS
from test_arrival_wizard_device_selection_ui import _HARNESS, WORKSPACE
from test_arrival_wizard_service import make_service
from test_wizard_camera_next_step_ui import fresh
from test_wizard_physical_intake_ui import bound_notebook, top, view_for


def action(name="record_note"):
    return next(item for item in ACTIONS if item.action_id == name).view(
        mode="rehearsal", busy=False
    )


def view(*actions):
    value = fresh(list(actions or [action()]))
    value.update(
        state_epoch=0,
        source_binding_sha256="a" * 64,
        cell_id="draft-cell",
        session_id="draft-session",
    )
    return value


def render(snapshot=None, *, page="diagnostics", steps=(), during_prepare=None):
    assert shutil.which("node"), "Node required for form draft verification"
    snapshot = view() if snapshot is None else snapshot
    before = deepcopy(snapshot)
    harness = (
        _HARNESS.replace(
            "append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}",
            "append(...items){for(const item of items)item.parentElement=this;this.children.push(...items);} replaceChildren(...items){for(const child of this.children)child.parentElement=null;this.children=[];this.append(...items);}",
        )
        .replace(
            "function find(id)",
            """function matching(predicate){
  const walk=node=>predicate(node)?node:node.children.map(walk).find(Boolean);
  return walk(find('#page-content'));
}
function attached(id){return matching(node=>node.id===id);}
const observations=[],saved=new Map(),storage=[],ranges=[];let interval;
function find(id)""",
        )
        .replace(
            "global.document={querySelector:find,",
            "global.document={getElementById:attached,createElementNS:(_,tag)=>new Element(tag),querySelector:find,",
        )
        .replace(
            "focus(){}",
            "focus(){document.activeElement=this;} scrollIntoView(){} setSelectionRange(start,end,direction){if(this.type==='number')throw Error('Number caret unsupported');this.selectionStart=start;this.selectionEnd=end;ranges.push({id:this.id,start,end,direction});}",
        )
        .replace(
            "setItem(){},getItem(){return null;}",
            "setItem(key,value){storage.push([key,value]);},getItem(){return null;}",
        )
        .replace(
            "global.setInterval=()=>1;",
            "global.setInterval=fn=>{interval=fn;return 1;};",
        )
        .replace(
            "if(path==='/api/view')return",
            "if(path==='/api/view'&&input.failView)throw Error('Modeled service loss');if(path==='/api/view')return",
        )
        .replace(
            "if(path==='/api/prepare')return",
            """if(path==='/api/prepare'&&input.during_prepare){
    const change=input.during_prepare;input.during_prepare=null;
    if(change.cancel)await find('#cancel-action').onclick();
    if(change.view){input.snapshot=change.view;await find('#refresh-button').onclick();}
  }
  if(path.startsWith('/api/images/'))return{ok:true,blob:async()=>new Blob(['MODELED IMAGE RERENDER ONLY'])};
  if(path==='/api/prepare')return""",
        )
        .replace(
            "if(input.prepare){",
            """const contentText=node=>[node.textContent,...node.children.map(contentText)].join('\\n');
  function observe(){
    const controls=[],messages=[];
    const walk=node=>{
      if(node.id?.startsWith('field-'))controls.push({id:node.id,value:node.value,checked:!!node.checked,disabled:!!node.disabled,maxLength:node.maxLength});
      if(node.className.includes('form-draft-message'))messages.push(node.textContent);
      node.children.forEach(walk);
    };walk(find('#page-content'));
    observations.push({controls,messages,text:contentText(find('#page-content')),focused:document.activeElement?.id,
      draftNotice:find('#draft-notice').textContent,status:find('#connection-status').textContent,
      error:find('#error-banner').textContent,dialogOpen:!!find('#action-dialog').open});
  }
  observe();
  for(const step of input.steps){
    if(step.edit){const field=attached(step.edit);if(!field)throw Error('Missing field '+step.edit);field.focus();
      if(step.checked!==undefined)field.checked=step.checked;else field.value=step.value;
      field.selectionStart=step.start??null;field.selectionEnd=step.end??null;field.selectionDirection='forward';
      await field.listeners[field.tagName==='SELECT'?'change':'input']?.();}
    if(step.save)saved.set(step.save,attached(step.save));
    if(step.stale){const field=saved.get(step.stale);field.value=step.value;await field.listeners.input?.();}
    if(step.page)find('#navigation').listeners.click({target:{closest:()=>({dataset:{page:step.page}})}});
    if(Object.hasOwn(step,'failView'))input.failView=step.failView;
    if(step.view)input.snapshot=step.view;
    if(step.refresh)await find('#refresh-button').onclick();
    if(step.poll){interval();await new Promise(resolve=>setTimeout(resolve,0));}
    if(step.button){const button=matching(node=>node.tagName==='BUTTON'&&node.textContent===step.button);if(!button)throw Error('Missing button');if(!button.disabled)await button.listeners.click();}
    if(step.submit){const box=attached(step.submit);await box.children.find(node=>node.tagName==='FORM').listeners.submit({preventDefault(){}});}
    if(step.cancel)await find('#cancel-action').onclick();
    if(step.execute)await find('#execute-action').onclick();
    observe();
  }
  if(input.prepare){""",
        )
        .replace(
            "JSON.stringify({requests,text:",
            "JSON.stringify({requests,observations,storage,ranges,text:",
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
                during_prepare=during_prepare,
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
    assert snapshot == before
    assert all(
        key in {"rocell-session", "rocell-csrf"} for key, _ in rendered["storage"]
    )
    return rendered


NOTE = "field-record_note-note"


def field(page, id=NOTE, observation=-1):
    return next(
        row for row in page["observations"][observation]["controls"] if row["id"] == id
    )


def read_only(page):
    assert all(row["method"] == "GET" for row in page["requests"])


def test_note_survives_navigation_and_explicit_refresh_without_storage_or_submission():
    page = render(
        steps=[
            dict(edit=NOTE, value="Unsaved investigation — <literal>"),
            dict(page="activity"),
            dict(page="diagnostics"),
            dict(refresh=True),
        ]
    )
    assert field(page)["value"] == "Unsaved investigation — <literal>"
    assert "Ordinary draft restored" in page["text"]
    read_only(page)


def test_focus_and_text_selection_are_restored_only_on_same_page():
    page = render(
        steps=[
            dict(edit=NOTE, value="working draft", start=2, end=7),
            dict(refresh=True),
            dict(page="activity"),
        ]
    )
    assert page["observations"][2]["focused"] == NOTE
    assert page["ranges"] == [dict(id=NOTE, start=2, end=7, direction="forward")]
    assert page["observations"][3].get("focused") != NOTE
    read_only(page)


def test_number_focus_survives_refresh_without_invalid_selection_api():
    id = "field-rehearsal_camera_settings-brightness_offset"
    page = render(
        view(action("rehearsal_camera_settings")),
        page="commissioning",
        steps=[dict(edit=id, value="12", start=1, end=1), dict(refresh=True)],
    )
    assert field(page, id)["value"] == "12"
    assert page["observations"][-1]["focused"] == id and page["ranges"] == []
    read_only(page)


@pytest.mark.parametrize(
    "key,value",
    [
        ("state_epoch", 1),
        ("session_id", "new"),
        ("cell_id", "new"),
        ("mode", "physical"),
        ("source_binding_sha256", "b" * 64),
    ],
)
def test_context_change_clears_even_while_typing_and_does_not_resurrect(key, value):
    initial = view()
    changed = dict(initial, **{key: value})
    page = render(
        initial,
        steps=[
            dict(edit=NOTE, value="old-context"),
            dict(view=changed, poll=True),
            dict(view=initial, refresh=True),
        ],
    )
    assert field(page)["value"] == ""
    assert field(page, observation=2)["value"] == ""
    assert not page["observations"][-1]["dialogOpen"]
    read_only(page)


@pytest.mark.parametrize("value", [None, True, -1, "0", 0.5])
def test_missing_or_malformed_context_disables_reuse_without_disabling_ordinary_form(
    value,
):
    snapshot = dict(view(), state_epoch=value)
    page = render(
        snapshot, steps=[dict(edit=NOTE, value="not retained"), dict(refresh=True)]
    )
    assert field(page)["value"] == "" and field(page)["disabled"] is False
    read_only(page)


@pytest.mark.parametrize(
    "change",
    ["disabled", "removed", "duplicate", "default", "label", "type", "max_length"],
)
def test_action_contract_changes_clear_drafts_even_if_epoch_did_not_advance(change):
    initial = view()
    changed = deepcopy(initial)
    changed["revision"] += 1
    if change == "disabled":
        changed["actions"][0]["enabled"] = False
    elif change == "removed":
        changed["actions"] = []
    elif change == "duplicate":
        changed["actions"] *= 2
    elif change == "type":
        changed["actions"][0]["fields"][0]["type"] = "text"
    elif change == "max_length":
        changed["actions"][0]["fields"][0]["max_length"] = 100
    elif change == "default":
        changed["actions"][0]["fields"][0]["default"] = "new default"
    else:
        changed["actions"][0]["label"] = "Changed purpose"
    page = render(
        initial,
        steps=[
            dict(edit=NOTE, value="old contract"),
            dict(view=changed, poll=True),
            dict(view=initial, refresh=True),
        ],
    )
    assert field(page)["value"] == ""
    read_only(page)


def test_poll_prunes_offpage_draft_when_another_page_is_being_edited():
    initial = view(action(), action("plan_task"))
    changed = deepcopy(initial)
    changed["actions"][0]["enabled"] = False
    changed["revision"] += 1
    page = render(
        initial,
        steps=[
            dict(edit=NOTE, value="old note"),
            dict(page="tasks"),
            dict(edit="field-plan_task-text", value="test"),
            dict(view=changed, poll=True),
            dict(view=initial, poll=True),
            dict(page="diagnostics"),
        ],
    )
    assert field(page)["value"] == ""
    read_only(page)


def test_late_input_from_detached_form_cannot_rebind_old_text_to_new_context():
    initial = view()
    changed = dict(initial, state_epoch=1)
    page = render(
        initial,
        steps=[
            dict(edit=NOTE, value="old"),
            dict(save=NOTE),
            dict(view=changed, refresh=True),
            dict(stale=NOTE, value="late old event"),
            dict(refresh=True),
        ],
    )
    assert field(page)["value"] == ""
    read_only(page)


def test_service_loss_clears_drafts_disables_forms_and_invalidates_preview():
    page = render(
        steps=[
            dict(edit=NOTE, value="note"),
            dict(submit="diagnostics-action-record_note"),
            dict(failView=True, refresh=True),
            dict(execute=True),
            dict(failView=False, refresh=True),
        ]
    )
    assert page["observations"][3]["status"] == "Service unavailable"
    assert field(page, observation=3)["disabled"] is True
    assert field(page)["value"] == "" and field(page)["disabled"] is False
    assert not any(row["path"] == "/api/execute" for row in page["requests"])


def test_image_triggered_rerender_keeps_ordinary_camera_draft_but_not_identity_label():
    proposal = action("physical_camera_operating_proposal")
    proposal.update(enabled=True, blocked_reasons=[])
    initial = view(proposal)
    changed = deepcopy(initial)
    changed["camera"] = dict(
        image_id="synthetic-frame", provenance="SYNTHETIC_TEST_IMAGE"
    )
    rationale = "field-physical_camera_operating_proposal-rationale"
    operator = "field-physical_camera_operating_proposal-operator_id"
    page = render(
        initial,
        page="camera",
        steps=[
            dict(edit=operator, value="current-operator"),
            dict(edit=rationale, value="manual focus investigation", start=0, end=6),
            dict(view=changed, poll=True),
        ],
    )
    assert field(page, rationale)["value"] == "manual focus investigation"
    assert field(page, operator)["value"] == ""
    assert page["observations"][-1]["focused"] == rationale
    assert any(row["path"] == "/api/images/synthetic-frame" for row in page["requests"])
    read_only(page)


def test_target_selection_is_never_restored_and_text_waits_for_explicit_matching_restore():
    initial = view(action("plan_task"))
    target = "field-plan_task-device"
    text = "field-plan_task-text"
    page = render(
        initial,
        page="tasks",
        steps=[
            dict(edit=target, value="phone"),
            dict(edit=text, value="phone draft"),
            dict(refresh=True),
            dict(edit=target, value="phone"),
            dict(button="Restore ordinary draft"),
        ],
    )
    assert (
        field(page, target, 3)["value"] == "keyboard"
        and field(page, text, 3)["value"] == "hello"
    )
    assert field(page, text, 4)["value"] == "hello"
    assert field(page, text)["value"] == "phone draft"
    read_only(page)


def test_changed_options_remove_held_draft_even_when_old_selection_is_reintroduced():
    initial = view(action("plan_task"))
    changed = deepcopy(initial)
    changed["actions"][0]["fields"][0]["options"][1][
        "label"
    ] = "Different target interpretation"
    page = render(
        initial,
        page="tasks",
        steps=[
            dict(edit="field-plan_task-text", value="old"),
            dict(view=changed, refresh=True),
            dict(view=initial, refresh=True),
        ],
    )
    assert field(page, "field-plan_task-text")["value"] == "hello"
    read_only(page)


def test_real_intake_question_change_never_attaches_old_observation_to_another_question(
    bound_notebook,
):
    setup, notebook = bound_notebook
    snapshot = view_for(setup, top(notebook), notebook)
    snapshot.update(state_epoch=0, source_binding_sha256="a" * 64)
    selector = "field-physical_intake_record-record_id"
    observed = "field-physical_intake_record-observed_value"
    page = render(
        snapshot,
        page="camera",
        steps=[
            dict(edit=selector, value="INT-005"),
            dict(edit=observed, value="123 measured"),
            dict(edit=selector, value="INT-006"),
            dict(edit=selector, value="INT-005"),
            dict(button="Restore ordinary draft"),
        ],
    )
    assert field(page, observed, 3)["value"] == ""
    assert field(page, observed, 4)["value"] == ""
    assert field(page, observed)["value"] == "123 measured"
    assert "Choose Restore ordinary draft" in page["observations"][4]["text"]
    read_only(page)


def test_confirmations_and_identity_fields_are_not_reused():
    candidate = action("review_camera_candidate")
    candidate["fields"][0]["options"] = [
        dict(value="test-choice", label="Test metadata only")
    ]
    page = render(
        view(candidate),
        page="camera",
        steps=[
            dict(edit="field-review_camera_candidate-choice_id", value="test-choice"),
            dict(edit="field-review_camera_candidate-reviewer_id", value="reviewer"),
            dict(edit="field-review_camera_candidate-metadata_only", checked=True),
            dict(refresh=True),
        ],
    )
    assert field(page, "field-review_camera_candidate-choice_id")["value"] == ""
    assert field(page, "field-review_camera_candidate-reviewer_id")["value"] == ""
    assert (
        field(page, "field-review_camera_candidate-metadata_only")["checked"] is False
    )
    read_only(page)


def test_reset_clears_ordinary_values_and_does_not_prepare():
    page = render(
        steps=[
            dict(edit=NOTE, value="discard me"),
            dict(button="Reset form to service defaults"),
            dict(refresh=True),
        ]
    )
    assert field(page)["value"] == ""
    read_only(page)


def test_execution_clears_drafts_and_never_replays_after_refresh():
    page = render(
        steps=[
            dict(edit=NOTE, value="submit once"),
            dict(submit="diagnostics-action-record_note"),
            dict(execute=True),
            dict(refresh=True),
        ]
    )
    assert field(page)["value"] == ""
    assert len([row for row in page["requests"] if row["path"] == "/api/execute"]) == 1
    assert next(row for row in page["requests"] if row["path"] == "/api/prepare")[
        "body"
    ]["input"] == {"note": "submit once"}


def test_cancel_keeps_ordinary_draft_but_never_the_ticket():
    page = render(
        steps=[
            dict(edit=NOTE, value="keep this"),
            dict(submit="diagnostics-action-record_note"),
            dict(cancel=True),
            dict(execute=True),
            dict(refresh=True),
        ]
    )
    assert field(page)["value"] == "keep this"
    assert not page["dialogOpen"] and not any(
        row["path"] == "/api/execute" for row in page["requests"]
    )


@pytest.mark.parametrize("change", ["context", "contract", "cancel"])
def test_late_preparation_cannot_reopen_an_invalidated_preview(change):
    initial = view()
    changed = deepcopy(initial)
    if change == "context":
        changed["state_epoch"] += 1
    if change == "contract":
        changed["actions"][0]["fields"][0]["max_length"] = 100
    page = render(
        initial,
        during_prepare={"cancel": True} if change == "cancel" else {"view": changed},
        steps=[
            dict(edit=NOTE, value="old preparation"),
            dict(submit="diagnostics-action-record_note"),
            dict(execute=True),
        ],
    )
    assert (
        not page["dialogOpen"]
        and "changed or the preview was cancelled" in page["error"]
    )
    assert not any(row["path"] == "/api/execute" for row in page["requests"])


def test_progress_poll_does_not_upgrade_the_old_forms_displayed_revision():
    initial = view()
    changed = dict(initial, revision=initial["revision"] + 1)
    page = render(
        initial,
        steps=[
            dict(edit=NOTE, value="draft"),
            dict(view=changed, poll=True),
            dict(submit="diagnostics-action-record_note"),
        ],
    )
    body = next(
        row["body"] for row in page["requests"] if row["path"] == "/api/prepare"
    )
    assert body["expected_revision"] == initial["revision"]
    assert body["input"] == {"note": "draft"}


def test_oversized_draft_is_not_silently_truncated_or_saved():
    page = render(steps=[dict(edit=NOTE, value="x" * 2001), dict(refresh=True)])
    assert field(page)["value"] == "" and field(page)["maxLength"] == 2000
    assert "not kept" in page["observations"][1]["text"]
    read_only(page)


def test_fresh_page_has_no_prior_drafts_and_real_service_context_allows_note_draft(
    make_service,
):
    service, runner, _ = make_service()
    page = render(
        service.view(),
        steps=[dict(edit=NOTE, value="temporary test note"), dict(refresh=True)],
    )
    assert field(page)["value"] == "temporary test note" and not runner.calls
    assert field(render(service.view()))["value"] == ""
    read_only(page)


@pytest.mark.parametrize(
    "name,field_name,draft",
    [
        ("movement_campaign_preview", "plan_json", '{"draft":true}'),
        ("movement_campaign_simulate", "board_transform_json", "null "),
        ("movement_campaign_preview", "clearance_mm", "7.5"),
        ("rehearsal_camera_campaign", "frame_count", "2"),
        ("rehearsal_owned_camera_campaign", "frame_count", "3"),
        ("simulate_task", "text", "hi"),
    ],
)
def test_other_reviewed_ordinary_fields_use_the_same_context_bound_behavior(
    name, field_name, draft
):
    definition = action(name)
    id = f"field-{name}-{field_name}"
    page = render(
        view(definition),
        page=definition["section"],
        steps=[dict(edit=id, value=draft), dict(refresh=True)],
    )
    assert field(page, id)["value"] == draft
    read_only(page)


def test_declaration_does_not_opt_unknown_fields_or_identity_into_draft_reuse():
    definition = action()
    definition["fields"].append(
        dict(name="opaque_choice", type="text", default="", label="Explicit choice")
    )
    page = render(
        view(definition),
        steps=[
            dict(edit=NOTE, value="note"),
            dict(edit="field-record_note-opaque_choice", value="not-restored"),
            dict(refresh=True),
        ],
    )
    assert field(page)["value"] == "note"
    assert field(page, "field-record_note-opaque_choice")["value"] == ""
    read_only(page)


def test_editable_preview_offers_only_named_local_forms_and_no_executable_service():
    import runpy

    preview = runpy.run_path(str(WORKSPACE / "software/scripts/camera_ui_preview.py"))
    snapshot, _ = preview["example_view"]("drafts")
    assert {item["action_id"] for item in snapshot["actions"] if item["enabled"]} == {
        "record_note",
        "plan_task",
        "simulate_task",
        "rehearsal_camera_settings",
        "movement_campaign_preview",
        "movement_campaign_simulate",
    }
    assert snapshot["physical_authority"] is False and snapshot["operations"] == []
