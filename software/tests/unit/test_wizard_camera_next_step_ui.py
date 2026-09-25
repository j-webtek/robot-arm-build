"""Navigation-only next steps from the current server action catalog.

Actual app.js runs in a finite fake DOM; no browser, device, service mutation,
form submission, selection or preview is performed by these navigation tests.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_arrival_wizard_device_selection_ui import _HARNESS, MetadataService, selection
from test_arrival_wizard_terminal import action
from test_wizard_physical_camera_setup_ui import complete_setup, prerequisite_summary
from test_wizard_static_camera_onboarding_ui import fixture

WORKSPACE = Path(__file__).resolve().parents[3]


def offered(name, *, enabled=True, section="camera"):
    value = action(name)
    value.update(section=section, enabled=enabled, label="Form: " + name)
    return value


def render(view, click=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node unavailable")
    harness = _HARNESS.replace(
        "const input=JSON.parse", "const navigations=[];const input=JSON.parse"
    )
    harness = harness.replace(
        "focus(){}",
        "focus(){if(this.id?.startsWith('camera-action-'))navigations.push({kind:'focus',id:this.id});} scrollIntoView(){if(this.id?.startsWith('camera-action-'))navigations.push({kind:'scroll',id:this.id});}",
    )
    harness = harness.replace(
        "global.document={querySelector:find,",
        "global.document={getElementById:id=>nodes.find(node=>node.id===id),querySelector:find,",
    )
    harness = harness.replace(
        "if(input.prepare){",
        "if(input.click){const link=nodes.find(node=>node['data-action-target']===input.click);if(!link)throw new Error('Missing navigation link');await link.listeners.click({preventDefault(){}});} if(input.prepare){",
    )
    harness = harness.replace(
        "JSON.stringify({requests,text:",
        "JSON.stringify({requests,navigations,links:nodes.filter(node=>node['data-action-target']).map(node=>({id:node['data-action-target'],href:node.href})),cards:nodes.filter(node=>node.id?.startsWith('camera-action-')).map(node=>node.id),text:",
    )
    before = deepcopy(view)
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": (
                    WORKSPACE / "software/src/rocell/ui/static/app.js"
                ).read_text(encoding="utf-8"),
                "snapshot": view,
                "page": "camera",
                "click": click,
            }
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
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["dialogOpen"] is False and view == before
    assert page["text"].index("Camera — next explicit step") < page["text"].index(
        "Retained camera image"
    )
    return page


def fresh(actions):
    view = MetadataService(selection()).view()
    view["actions"] = actions
    return view


@pytest.mark.parametrize(
    "clicked", [None, "physical_camera_initialize", "physical_camera_discover"]
)
def test_fresh_setup_keeps_new_and_original_explicit_alternatives(clicked):
    view = fresh(
        [
            offered("physical_camera_initialize"),
            offered("physical_camera_discover"),
            offered("physical_camera_reopen", enabled=False),
        ]
    )
    page = render(view, clicked)
    assert [row["id"] for row in page["links"]] == [
        "physical_camera_initialize",
        "physical_camera_discover",
    ]
    assert "Neither option is selected automatically" in page["text"]
    assert page["navigations"] == (
        []
        if clicked is None
        else [
            {"kind": "scroll", "id": "camera-action-" + clicked},
            {"kind": "focus", "id": "camera-action-" + clicked},
        ]
    )
    assert all(not row["checked"] and row["value"] == "" for row in page["controls"])


def test_discovered_original_has_navigation_not_automatic_choice():
    view = fresh(
        [
            offered(name)
            for name in (
                "physical_camera_initialize",
                "physical_camera_discover",
                "physical_camera_reopen",
            )
        ]
    )
    page = render(view, "physical_camera_reopen")
    assert "physical_camera_reopen" in [row["id"] for row in page["links"]]
    assert "No choice is preselected here" in page["text"]


def test_reopen_navigation_preserves_placeholder_and_unchecked_consent():
    reopen = offered("physical_camera_reopen")
    reopen["fields"] = [
        {
            "name": "choice_id",
            "type": "select",
            "required": True,
            "options": [
                {"value": "reopen-" + "a" * 32, "label": "Original one"},
                {"value": "reopen-" + "b" * 32, "label": "Original two"},
            ],
        },
        {"name": "file_only", "type": "checkbox", "required": True, "default": False},
    ]
    page = render(fresh([reopen]), "physical_camera_reopen")
    selector = next(row for row in page["controls"] if row["tag"] == "SELECT")
    assert selector["value"] == "" and selector["options"][0]["selected"] is True
    assert not any(row["selected"] for row in selector["options"][1:])
    assert not any(row["checked"] for row in page["controls"])


@pytest.mark.parametrize("enabled", [False, None, "true", 1])
def test_not_explicitly_server_enabled_has_no_active_link(enabled):
    page = render(fresh([offered("physical_camera_initialize", enabled=enabled)]))
    assert page["links"] == [] and page["navigations"] == []
    assert "No next onboarding action is currently eligible" in page["text"]


def test_duplicate_unknown_or_wrong_section_actions_do_not_create_links():
    page = render(
        fresh(
            [
                offered("physical_camera_initialize"),
                offered("physical_camera_initialize"),
                offered("physical_camera_capture"),
                offered("physical_static_contract_collect", section="arm"),
            ]
        )
    )
    assert page["links"] == []


@pytest.mark.parametrize("enabled", [True, False])
def test_cached_next_step_must_also_be_server_eligible(complete_setup, enabled):
    view = fixture(complete_setup)
    view["static_camera_onboarding"]["next_action"] = "physical_camera_receipt_begin"
    view["actions"] = [
        offered("physical_camera_receipt_begin", enabled=enabled),
        offered("physical_camera_refresh"),
    ]
    page = render(view, "physical_camera_receipt_begin" if enabled else None)
    assert (
        "physical_camera_receipt_begin" in [row["id"] for row in page["links"]]
    ) is enabled
    assert "physical_camera_refresh" in [row["id"] for row in page["links"]]
    assert (
        "The published original workflow identifies this next step" in page["text"]
        if enabled
        else "No next onboarding action is currently eligible" in page["text"]
    )


def test_stale_cached_claim_is_not_presented_as_verified_next_step(complete_setup):
    view = fixture(complete_setup)
    view["static_camera_onboarding"]["next_action"] = "physical_camera_receipt_begin"
    view["static_camera_onboarding"]["source_sha256"] = "f" * 64
    view["actions"] = [offered("physical_camera_receipt_begin")]
    page = render(view)
    assert (
        "The published original workflow identifies this next step" not in page["text"]
    )
    assert "The server currently offers this onboarding form" in page["text"]
    assert page["links"][0]["id"] == "physical_camera_receipt_begin"


def test_navigation_targets_existing_cards_and_preserves_all_diagnostics():
    page = render(
        fresh([offered("physical_camera_prerequisites")]),
        "physical_camera_prerequisites",
    )
    for link in page["links"]:
        assert link["href"].removeprefix("#") in page["cards"]
    for title in (
        "Static-camera design and received-unit onboarding",
        "Camera actions",
        "Retained camera image",
    ):
        assert title in page["text"]
