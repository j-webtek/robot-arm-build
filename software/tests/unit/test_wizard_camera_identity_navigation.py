"""Existing forms only: actual stage-3 service, modeled physical/M1 facts."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application import physical_received_camera_service as received_module
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_native_camera_metadata import (
    RehearsalNativeCameraMetadataProvider,
)
from test_wizard_native_camera_enrollment import generic_review
from test_wizard_camera_helper_registration_ui import helper_view
from test_wizard_received_camera_ui import (
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    complete_modeled_storage_projection,
    producer_view,
    start,
    fill,
    run,
    review,
    observed_submission_values,
)
from test_wizard_camera_next_step_ui import offered
from test_arrival_wizard_device_selection_ui import _HARNESS


WORKSPACE = Path(__file__).resolve().parents[3]


def render(view, click=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node unavailable")
    harness = _HARNESS.replace(
        "const input=JSON.parse", "const navigations=[];const input=JSON.parse"
    )
    harness = harness.replace(
        "focus(){}",
        "focus(){if(this.id?.includes('-action-'))navigations.push(this.id);} scrollIntoView(){}",
    )
    harness = harness.replace(
        "global.document={querySelector:find,",
        "global.document={getElementById:id=>nodes.find(node=>node.id===id),querySelector:find,",
    )
    harness = harness.replace(
        "if(input.prepare){",
        "if(input.click){const link=nodes.find(node=>node['data-action-target']===input.click);if(!link)throw new Error('Missing link');await link.listeners.click({preventDefault(){}});} if(input.prepare){",
    )
    harness = harness.replace(
        "JSON.stringify({requests,text:",
        "JSON.stringify({requests,navigations,links:nodes.filter(node=>node['data-action-target']).map(node=>({id:node['data-action-target'],href:node.href})),page:find('#page-title').textContent,text:",
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
    value = json.loads(result.stdout)
    assert value["status"] == "Local service connected", value["error"]
    assert value["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert not value["dialogOpen"] and view == before
    assert not any(row["checked"] for row in value["controls"])
    return value


@pytest.fixture
def identity_wait(received, complete_modeled_storage_projection):
    service, state = received
    start(service)
    fill(service, observed=True)
    run(service, received_module.SUBMIT, observed_submission_values(service))
    review(service)
    run(service, received_module.IDENTITY)
    view = producer_view(service)
    assert (
        view["received_camera_onboarding"]["stage_states"]["camera_identity"]
        == "WAITING_OPERATOR"
    )
    names = [
        "review_camera_candidate",
        "camera_helper_inspect",
        "camera_helper_review",
        "native_camera_inventory",
        "native_camera_identity",
        "native_camera_review",
        "physical_camera_refresh",
    ]
    view["actions"] = [
        offered("inventory_devices", section="arm"),
        *[offered(name) for name in names],
    ]
    return service, state, view


def test_actual_waiting_receipt_guides_existing_metadata_chain_and_cross_page_only(
    identity_wait,
):
    service, state, view = identity_wait
    source, launch = view["source_binding_sha256"], view["session_id"]
    generic = WizardDeviceSelection("physical", launch, source)
    descriptor = {"provenance": "WINDOWS_NATIVE_METADATA", "helper_sha256": "b" * 64}
    native = WizardNativeCameraEnrollment("physical", launch, source, descriptor)
    view["device_selection"] = generic.view()
    view["native_camera_enrollment"] = native.view()

    def helper(status):
        value = helper_view(status, mode="physical")
        value["provenance"].update(session_id=launch, source_sha256=source)
        view["camera_helper_registration"] = value

    def expected(action):
        page = render(view)
        assert [row["id"] for row in page["links"]] == [action]
        assert "Original camera identity stage is waiting" in page["text"]

    helper("NO_INSPECTION")
    expected("inventory_devices")
    page = render(view, "inventory_devices")
    assert page["page"] == "Arm"
    assert page["navigations"] == ["arm-action-inventory_devices"]
    assert page["links"][0]["href"] == "#arm-action-inventory_devices"

    original = generic_review(mode="physical", source=source, session=launch)
    generic.ingest(original["inventory_report"], operation_id="generic-operation")
    view["device_selection"] = generic.view()
    expected("review_camera_candidate")
    generic.review(generic.choices("CAMERA")[0]["value"], "CAMERA", "reviewer")
    view["device_selection"] = generic.view()
    expected("camera_helper_inspect")
    helper("INSPECTION_RETAINED")
    expected("camera_helper_review")
    helper("METADATA_HELPER_REGISTERED")
    expected("native_camera_inventory")

    provider = RehearsalNativeCameraMetadataProvider("nominal")
    packet = provider.inventory()
    packet.update(descriptor)
    native.ingest_inventory(
        packet,
        operation_id="native-inventory",
        generic_review=generic.reviewed_candidate("CAMERA"),
    )
    view["native_camera_enrollment"] = native.view()
    expected("native_camera_identity")
    token = native.choices()[0]["value"]
    packet = provider.identity(native.candidate(token))
    packet.update(descriptor)
    native.retain_identity(token, packet, operation_id="native-identity")
    view["native_camera_enrollment"] = native.view()
    expected("native_camera_review")
    native.review(token, "native-reviewer")
    view["native_camera_enrollment"] = native.view()
    service.setup.invalidate()
    service.invalidate()
    held = producer_view(service)
    view["physical_camera_setup"] = held["physical_camera_setup"]
    view["received_camera_onboarding"] = held["received_camera_onboarding"]
    expected("physical_camera_refresh")
    page = render(view, "physical_camera_refresh")
    assert page["navigations"] == ["camera-action-physical_camera_refresh"]
    assert "Intermediate refreshes are unnecessary" in page["text"]


def test_server_eligibility_and_current_context_guard_navigation_without_autochoice(
    identity_wait,
):
    _, _, view = identity_wait
    view["device_selection"] = WizardDeviceSelection(
        "physical", view["session_id"], view["source_binding_sha256"]
    ).view()
    for change in (
        "disabled",
        "duplicate",
        "wrong-section",
        "wrong-source",
        "wrong-launch",
    ):
        current = deepcopy(view)
        action = current["actions"][0]
        if change == "disabled":
            action["enabled"] = False
        elif change == "duplicate":
            current["actions"].append(deepcopy(action))
        elif change == "wrong-section":
            action["section"] = "camera"
        elif change == "wrong-source":
            current["received_camera_onboarding"]["source_sha256"] = "f" * 64
        else:
            current["received_camera_onboarding"]["launch_session_id"] = "other-launch"
        page = render(current)
        assert "inventory_devices" not in [row["id"] for row in page["links"]]
        assert page["navigations"] == []
