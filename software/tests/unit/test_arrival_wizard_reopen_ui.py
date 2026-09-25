"""Pure DOM and terminal tests: no browser, hardware or M1 activation."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

from test_arrival_wizard_terminal import Service, action, dispatched, run


WORKSPACE = Path(__file__).resolve().parents[3]
CHOICE_ID = "reopen-opaque_choice-verbatim"
DISCOVERY_HASH = "b" * 64


def commissioning() -> dict[str, Any]:
    return {
        "status": "NOT_STARTED",
        "session_origin": "NEW_THIS_LAUNCH",
        "directory": "C:/assigned/new-launch",
        "cell_id": "new-cell",
        "session_id": "new-session",
        "stage_state": None,
        "assessment": None,
        "discovery": {
            "status": "DISCOVERED",
            "storage_qualified": False,
            "choices": [
                {
                    "choice_id": CHOICE_ID,
                    "directory": "C:/assigned/prior-launch",
                    "session_id": "prior_session_verbatim",
                    "cell_id": "prior_cell",
                    "session_header_sha256": "a" * 64,
                    "discovery_sha256": DISCOVERY_HASH,
                    "source_matches": True,
                    "status": "DISCOVERED_NOT_OPENED",
                }
            ],
            "issues": [],
            "unexpected_large_record": {"sentinel": "NEVER_GENERIC_FACTS"},
        },
        "reopen_result": None,
    }


def reopen_action() -> dict[str, Any]:
    selected = action(
        "rehearsal_reopen",
        fields=[
            {
                "name": "choice_id",
                "label": "Original rehearsal store",
                "type": "select",
                "required": True,
                "options": [{"value": CHOICE_ID, "label": "Original session"}],
            }
        ],
    )
    selected.update(
        section="commissioning",
        description="Requalifies storage and acquires/releases original-session leases.",
    )
    return selected


class ReopenService(Service):
    def __init__(self, projection: dict[str, Any]) -> None:
        super().__init__([action("rehearsal_discover"), reopen_action()])
        self.projection = projection

    def view(self) -> dict[str, Any]:
        result = super().view()
        result["commissioning_rehearsal"] = deepcopy(self.projection)
        return result


_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = [], ids = new Map(), requests = [];
class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.textContent = '';
    this.listeners = {}; this.hidden = false; this.value = ''; this.className = '';
    this.classList = {add() {}, toggle() {}}; nodes.push(this); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  focus() {} showModal() { this.open = true; } close() { this.open = false; }
  reportValidity() { return true; }
}
function find(id) { if (!ids.has(id)) ids.set(id, new Element('div')); return ids.get(id); }
global.document = {querySelector:find, querySelectorAll:()=>[],
  createElement:tag=>new Element(tag), createElementNS:(ns,tag)=>new Element(tag),
  createTextNode:text=>{const node=new Element('text');node.textContent=text;return node;},
  createDocumentFragment:()=>new Element('fragment'), activeElement:null, hidden:false};
global.location = {hash:'#session=fixture&csrf=fixture',pathname:'/'};
global.history = {replaceState(){}}; global.sessionStorage = {setItem(){},getItem(){return null;}};
global.setInterval = ()=>1;
global.fetch = async (path, options) => {
  requests.push({path, method:options.method || 'GET', body:options.body ? JSON.parse(options.body) : null});
  if (path === '/api/view') return {ok:true,json:async()=>input.snapshot};
  if (path === '/api/prepare') return {ok:true,json:async()=>({ticket_id:'ticket-1',label:'Open original rehearsal',
    effects:['Requalify storage; acquire/release original-session leases'],warnings:['No replay or hardware authority']})};
  if (path === '/api/execute') return {ok:true,json:async()=>({operation_id:'operation-1',status:'QUEUED'})};
  throw new Error('Unexpected fetch: '+path);
};
(async()=>{
  vm.runInThisContext(input.script);
  await new Promise(resolve=>setTimeout(resolve,20));
  find('#navigation').listeners.click({target:{closest:()=>({dataset:{page:'commissioning'}})}});
  if (input.prepare) {
    const selector = nodes.find(node=>node.id==='field-rehearsal_reopen-choice_id');
    selector.value=input.choice;
    const form = nodes.find(node=>node.tagName==='FORM' && node.children.some(child=>child.textContent==='rehearsal reopen'));
    await form.listeners.submit({preventDefault(){}});
  }
  if (input.execute) await find('#execute-action').onclick();
  if (input.cancel) find('#cancel-action').onclick();
  const treeText=node=>[node.textContent,...node.children.map(treeText)].join('\n');
  process.stdout.write(JSON.stringify({requests, text:treeText(find('#page-content')),
    allText:nodes.map(node=>node.textContent).join('\n'), status:find('#connection-status').textContent,
    error:find('#error-banner').textContent, dialogOpen:find('#action-dialog').open || false,
    controls:nodes.filter(node=>['BUTTON','INPUT','SELECT','TEXTAREA'].includes(node.tagName))
      .map(node=>({tag:node.tagName,id:node.id || null,label:node.textContent})),
    choiceValues:nodes.filter(node=>node.tagName==='OPTION').map(node=>node.value)}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
"""


def browser(projection: dict[str, Any], **options: Any) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime unavailable")
    snapshot = ReopenService(projection).view()
    snapshot.update(camera={}, arm={}, stages=[], operations=[])
    payload = {
        "script": (WORKSPACE / "software/src/rocell/ui/static/app.js").read_text(
            encoding="utf-8"
        ),
        "snapshot": snapshot,
        **options,
    }
    result = subprocess.run(
        [node, "-e", _HARNESS],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_browser_discovery_projection_is_safe_and_navigation_has_no_actions() -> None:
    projection = commissioning()
    projection["discovery"]["issues"] = [
        {
            "code": "SOURCE_DRIFT",
            "message": "<img src=x onerror=alert(1)>",
            "remediation": "Inspect, do not convert.",
        }
    ]
    result = browser(projection)
    assert result["status"] == "Local service connected", result
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert CHOICE_ID in result["allText"]
    assert DISCOVERY_HASH in result["allText"]
    assert "<img src=x onerror=alert(1)>" in result["allText"]
    assert "NEVER_GENERIC_FACTS" not in result["allText"]
    assert "Opening is a separate" in result["allText"]
    assert CHOICE_ID in result["choiceValues"]


def test_browser_exact_choice_preview_cancel_and_execute_are_separate() -> None:
    canceled = browser(commissioning(), prepare=True, choice=CHOICE_ID, cancel=True)
    assert [item["path"] for item in canceled["requests"]] == [
        "/api/view",
        "/api/prepare",
    ]
    assert canceled["requests"][1]["body"] == {
        "action_id": "rehearsal_reopen",
        "input": {"choice_id": CHOICE_ID},
        "expected_revision": 7,
    }
    assert canceled["dialogOpen"] is False
    confirmed = browser(commissioning(), prepare=True, choice=CHOICE_ID, execute=True)
    assert [
        item for item in confirmed["requests"] if item["path"] == "/api/execute"
    ] == [{"path": "/api/execute", "method": "POST", "body": {"ticket_id": "ticket-1"}}]


@pytest.mark.parametrize("status", ["OPENED", "READ_ONLY_HOLD"])
def test_browser_and_terminal_distinguish_retained_review_and_hold(status: str) -> None:
    projection = commissioning()
    projection.update(
        session_origin="REOPENED_EXISTING",
        stage_state="REVIEW_PENDING",
        reopen_result={
            "status": status,
            "original_session_reopened": status == "OPENED",
            "disposition": "REVIEW_PENDING",
            "operator_id": "operator-a",
            "reasons": [
                {
                    "code": "HELD_SOURCE",
                    "message": "Retain original evidence",
                    "remediation": "Do not replay",
                }
            ],
        },
    )
    rendered = browser(projection)
    service = ReopenService(projection)
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0
    combined = rendered["allText"] + "\n".join(output)
    assert (
        "fresh, distinct reviewer" in combined
        if status == "OPENED"
        else "held read-only" in combined
    )
    assert "Retain original evidence" in combined
    assert not dispatched(service, "prepare") and not dispatched(service, "execute")


def test_terminal_opaque_selection_is_verbatim_and_requires_exact_confirmation() -> (
    None
):
    service = ReopenService(commissioning())
    run(service, ["rehearsal_reopen", "1", "no", "quit"])
    assert dispatched(service, "prepare") == [
        ("prepare", "rehearsal_reopen", {"choice_id": CHOICE_ID}, 7)
    ]
    assert not dispatched(service, "execute")
    empty = ReopenService(commissioning())
    run(empty, ["rehearsal_reopen", "", "quit"])
    assert not dispatched(empty, "prepare")


def test_historic_reopen_disposition_does_not_override_current_stage() -> None:
    projection = commissioning()
    projection.update(
        stage_state="PENDING",
        reopen_result={
            "status": "OPENED",
            "disposition": "REVIEW_PENDING",
            "reasons": [],
        },
    )
    rendered = browser(projection)
    _, output, _ = run(ReopenService(projection), ["quit"])
    assert "awaits a fresh, distinct reviewer" not in rendered["allText"]
    assert "awaits a fresh, distinct reviewer" not in "\n".join(output)
    projection["reopen_result"]["disposition"] = "WAITING_NO_RECEIPT"
    rendered = browser(projection)
    _, output, _ = run(ReopenService(projection), ["quit"])
    assert "At reopening, this stage was waiting" in rendered["allText"]
    assert "At reopening, this stage was waiting" in "\n".join(output)


@pytest.mark.parametrize("value", [None, {}, {"choices": [None], "issues": [None]}])
def test_missing_discovery_or_nullable_result_never_dispatches(value: Any) -> None:
    projection = commissioning()
    projection["discovery"] = value
    result = browser(projection)
    assert result["status"] == "Local service connected"
    assert len(result["requests"]) == 1
