"""Actual renderer, finite DOM: disclosure is navigation, never device consent.

The harness inspects the currently attached tree rather than stale nodes from
previous renders. Native <details> visibility is modeled for presentation only.
"""

from copy import deepcopy
import json
import shutil
import subprocess

import pytest

from test_arrival_wizard_device_selection_ui import _HARNESS, WORKSPACE
from test_wizard_camera_next_step_ui import fresh, offered


SECTIONS = ("camera-unavailable-actions", "camera-detailed-records")


def render(actions, *, steps=(), submit=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node runtime unavailable")
    harness = (
        _HARNESS.replace(
            "function find(id)",
            """function attached(id) {
  const walk=node=>node.id===id?node:node.children.map(walk).find(Boolean);
  return walk(find('#page-content'));
}
function find(id)""",
        )
        .replace(
            "global.document={querySelector:find,",
            "global.document={getElementById:attached,querySelector:find,",
        )
        .replace("focus(){}", "focus(){document.activeElement=this;}")
    )
    harness = harness.replace(
        "if(input.prepare){",
        """const observations=[];
  const retainedSections=new Map(input.sections.map(id=>[id,attached(id)]));
  function observe() {
    const forms=[],sections=[];
    const walk=(node,visible=true)=>{
      visible=visible && !node.hidden;
      if(node.id?.startsWith('camera-action-')) {
        const form=node.children.find(child=>child.tagName==='FORM');
        const button=form.children.find(child=>child.type==='submit');
        forms.push({id:node.id,visible,disabled:button.disabled});
      }
      if(input.sections.includes(node.id))sections.push({id:node.id,open:!!node.open});
      for(const child of node.children)walk(child,visible && (node.tagName!=='DETAILS' || node.open || child.tagName==='SUMMARY'));
    };
    walk(find('#page-content'));
    observations.push({forms,sections,focus:document.activeElement?.id||null,
      focusAttached:!!document.activeElement?.id && attached(document.activeElement.id)===document.activeElement});
  }
  observe();
  for(const step of input.steps||[]) {
    if(step.open!==undefined) {
      const box=attached(step.id); if(!box)throw new Error('Missing disclosure');
      box.open=step.open;
      if(step.deliverToggle!==false)box.listeners.toggle?.();
      if(step.focus)attached(step.id+'-summary').focus();
    }
    if(step.page)find('#navigation').listeners.click({target:{closest:()=>({dataset:{page:step.page}})}});
    if(step.staleToggle){
      const stale=retainedSections.get(step.staleToggle);
      stale.open=false;stale.listeners.toggle?.();
    }
    if(step.refresh)await find('#refresh-button').onclick();
    observe();
  }
  if(input.submit){
    const box=attached('camera-action-'+input.submit);
    await box.children.find(child=>child.tagName==='FORM').listeners.submit({preventDefault(){}});
    observe();
  }
  if(input.prepare){""",
    ).replace(
        "JSON.stringify({requests,text:", "JSON.stringify({requests,observations,text:"
    )
    view = fresh(actions)
    before = deepcopy(view)
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            dict(
                script=(WORKSPACE / "software/src/rocell/ui/static/app.js").read_text(
                    encoding="utf-8"
                ),
                snapshot=view,
                page="camera",
                sections=SECTIONS,
                steps=steps,
                submit=submit,
            )
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    page = json.loads(result.stdout)
    assert page["status"] == "Local service connected", page["error"]
    assert view == before
    return page


def only_reads(page, count=1):
    assert (
        page["requests"]
        == [{"path": "/api/view", "method": "GET", "body": None}] * count
    )
    assert page["dialogOpen"] is False


def test_six_available_forms_precede_seventy_three_collapsed_explanations():
    actions = [offered(f"available_{n}") for n in range(6)]
    actions += [
        dict(
            offered(f"blocked_{n}", enabled=False),
            blocked_reasons=[f"Hold-{n}: physical release is not qualified"],
        )
        for n in range(73)
    ]
    page = render(actions)
    only_reads(page)
    initial = page["observations"][0]
    assert len(initial["forms"]) == 79
    assert sum(row["visible"] for row in initial["forms"]) == 6
    assert sum(row["disabled"] for row in initial["forms"]) == 73
    assert initial["sections"] == [dict(id=id, open=False) for id in SECTIONS]
    assert "Unavailable camera actions (73)" in page["text"]
    assert (
        page["text"].index("Form: available_0")
        < page["text"].index("Form: blocked_0")
        < page["text"].index("Static-camera design and received-unit onboarding")
    )
    assert all(
        f"Hold-{n}: physical release is not qualified" in page["text"]
        for n in range(73)
    )


@pytest.mark.parametrize("section", SECTIONS)
@pytest.mark.parametrize("deliver_toggle", [True, False])
def test_expansion_survives_navigation_even_before_queued_toggle(
    section, deliver_toggle
):
    page = render(
        [offered("available"), offered("held", enabled=False)],
        steps=[
            dict(id=section, open=True, deliverToggle=deliver_toggle),
            dict(page="arm"),
            dict(page="camera"),
        ],
    )
    only_reads(page)
    final = page["observations"][-1]
    assert next(row for row in final["sections"] if row["id"] == section)["open"]
    assert sum(row["visible"] for row in final["forms"]) == (
        2 if section == SECTIONS[0] else 1
    )
    assert final["forms"][-1]["disabled"] is True


@pytest.mark.parametrize("section", SECTIONS)
def test_explicit_refresh_preserves_expansion_and_summary_focus(section):
    page = render(
        [offered("held", enabled=False)],
        steps=[dict(id=section, open=True, focus=True), dict(refresh=True)],
    )
    only_reads(page, 2)
    final = page["observations"][-1]
    assert next(row for row in final["sections"] if row["id"] == section)["open"]
    assert final["focus"] == section + "-summary"
    assert final["focusAttached"] is True


def test_closing_a_section_is_retained_without_changing_server_eligibility():
    page = render(
        [offered("held", enabled=False)],
        steps=[
            dict(id=SECTIONS[0], open=True),
            dict(id=SECTIONS[0], open=False),
            dict(refresh=True),
        ],
    )
    only_reads(page, 2)
    assert page["observations"][-1]["forms"] == [
        dict(id="camera-action-held", visible=False, disabled=True)
    ]


def test_detached_toggle_event_cannot_overwrite_the_current_expansion_choice():
    page = render(
        [offered("held", enabled=False)],
        steps=[
            dict(id=SECTIONS[0], open=True),
            dict(page="arm"),
            dict(staleToggle=SECTIONS[0]),
            dict(page="camera"),
        ],
    )
    only_reads(page)
    assert page["observations"][-1]["sections"][0]["open"] is True


@pytest.mark.parametrize("enabled", [False, None, "true", 1, {}, []])
def test_non_boolean_eligibility_stays_disabled_even_on_direct_submit(enabled):
    page = render([offered("held", enabled=enabled)], submit="held")
    only_reads(page)
    assert page["observations"][0]["forms"] == [
        dict(id="camera-action-held", visible=False, disabled=True)
    ]


def test_missing_eligibility_does_not_offer_a_preview():
    action = offered("held")
    del action["enabled"]
    page = render([action], submit="held")
    only_reads(page)
    assert page["observations"][0]["forms"][0]["disabled"] is True


@pytest.mark.parametrize(
    "action_id", ["physical_intake_record", "physical_received_camera_draft_record"]
)
def test_current_draft_hold_remains_unavailable_even_if_catalog_offers_form(action_id):
    page = render([offered(action_id)], submit=action_id)
    only_reads(page)
    assert page["observations"][0]["forms"] == [
        dict(id="camera-action-" + action_id, visible=False, disabled=True)
    ]
    assert "Current source-bound intake questions are unavailable" in page["text"]


def test_eligible_explicit_submit_still_requires_a_server_ticket():
    page = render([offered("available")], submit="available")
    assert page["requests"] == [
        dict(path="/api/view", method="GET", body=None),
        dict(
            path="/api/prepare",
            method="POST",
            body=dict(action_id="available", input={}, expected_revision=7),
        ),
    ]
    assert page["dialogOpen"] is True
    assert not any(row["path"] == "/api/execute" for row in page["requests"])
