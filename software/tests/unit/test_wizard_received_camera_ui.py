"""Real received codecs/service caches; modeled M1/physical facts, no devices.

The browser harness executes the actual app.js with one GET and no mutation.
All observation text and positive hardware-shaped facts are explicit fixtures.
"""

from copy import deepcopy
from pathlib import Path

import pytest

from rocell.application import physical_received_camera_service as received_module
from rocell.application.physical_static_camera_onboarding_service import (
    PhysicalStaticCameraOnboardingService,
)
from rocell.application.physical_source_qualification_service import (
    PhysicalSourceQualificationService,
)
from test_physical_received_camera_service import (
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    start,
    fill,
    submit,
    review,
    run,
    observed_submission_values,
)
from test_wizard_workspace_source_ui import snapshot, render_snapshot
from test_wizard_physical_camera_setup_ui import modeled_storage
from rocell.ui.terminal import _ReceivedCameraDisplay
from test_wizard_camera_next_step_ui import render as render_navigation, offered
from test_physical_received_camera_service import record_values


ERROR = "RECEIVED_CAMERA_NOT_VERIFIED"


@pytest.fixture(autouse=True)
def complete_modeled_storage_projection(received):
    """Supply the full modeled M1 view, retaining every real codec fixture hash."""
    service, state = received
    previous = state["store"].verification
    template = modeled_storage(service.setup.session)["session"]["verification"]

    def verification(session):
        report = previous(session)
        original = report.to_dict()
        full = deepcopy(template)
        full["session"].update(original["session"])
        full["challenge_sha256"] = original["challenge_sha256"]
        report.to_dict = lambda: deepcopy(full)
        return report

    state["store"].verification = verification
    from threading import Event

    service.setup.session.refresh(cancellation=Event(), progress=lambda _: None)


def producer_view(service):
    """Use actual compact adapters; no fabricated successful stage projection."""
    view = snapshot(service.setup.view())
    source = PhysicalSourceQualificationService(service.setup)
    design = PhysicalStaticCameraOnboardingService(service.setup)
    source.observe_setup()
    design.observe_setup()
    view.update(
        source_reassessment=source.view(),
        static_camera_onboarding=design.view(),
        received_camera_onboarding=service.view(),
    )
    return view


def render_received(view):
    before = deepcopy(view)
    assert (
        _ReceivedCameraDisplay.validate(view["received_camera_onboarding"], view)
        == view["received_camera_onboarding"]
    )
    browser, terminal = render_snapshot(view)
    assert view == before
    assert ERROR not in browser, browser[
        browser.index("Received camera and passive") :
    ][:2200]
    assert ERROR not in terminal
    return browser, terminal


@pytest.mark.parametrize("observed", [False, True])
def test_actual_service_complete_subject_and_metadata_export(received, observed):
    service, state = received
    render_received(producer_view(service))
    start(service)
    render_received(producer_view(service))
    fill(service, observed=observed)
    before = deepcopy(state["payloads"])
    if observed:
        run(service, received_module.SUBMIT, observed_submission_values(service))
    else:
        submit(service)
    waiting = producer_view(service)
    text, _ = render_received(waiting)
    assert (
        "Receipt completeness assessment: " + ("PASS" if observed else "BLOCKED")
        in text
    )
    review(service)
    if observed:
        run(service, received_module.IDENTITY)
    reviewed = producer_view(service)
    text, _ = render_received(reviewed)
    assert ("Stage 3 receipt accepted only" in text) is observed
    assert "INT-005" in text
    assert all(state["payloads"][key] == value for key, value in before.items())
    run(
        service,
        received_module.EXPORT,
        export_parent=Path(service.setup.session.descriptor()["workspace"])
        / "software"
        / "runs"
        / "wizard-exports",
    )
    exported = producer_view(service)
    text, _ = render_received(exported)
    assert "Separate received metadata export" in text
    assert (
        exported["received_camera_onboarding"]["metadata_export"]["provenance"][
            "source_binding_sha256"
        ]
        == state["source"]
    )


@pytest.mark.parametrize(
    "fault", ["source", "authority", "extra", "coverage", "context", "publication"]
)
def test_malformed_received_draft_withheld(received, fault):
    service, _ = received
    start(service)
    view = producer_view(service)
    value = view["received_camera_onboarding"]
    if fault == "source":
        value["source_sha256"] = "f" * 64
    elif fault == "authority":
        value["hardware_qualified"] = True
    elif fault == "extra":
        value["draft"]["raw_media"] = "must_not_render"
    elif fault == "coverage":
        value["draft"]["coverage"]["observed"] = 16
    elif fault == "context":
        value["original_context"]["header_sha256"] = "f" * 64
    else:
        value["publication"]["status"] = "PENDING"
    browser, _ = render_snapshot(view)
    assert _ReceivedCameraDisplay.validate(value, view) is None
    assert ERROR in browser
    assert "must_not_render" not in browser


def test_pending_and_historical_actual_candidates_not_current(received):
    service, _ = received
    start(service, publish=False)
    text, _ = render_received(producer_view(service))
    assert "Publication pending: draft, original collection" in text
    service.invalidate()
    text, _ = render_received(producer_view(service))
    assert "HISTORICAL ONLY" in text


def test_literal_operator_notes_and_navigation_only(received):
    service, _ = received
    start(service)
    values = record_values(service.view()["draft"]["rows"][0])
    values.update(
        observed_value="unknown_value_<script>not_code</script>",
        method="method_with_underscores",
        evidence_note="evidence_note_exact",
        operator_id="operator_label",
    )
    run(service, received_module.RECORD, values)
    view = producer_view(service)
    text, _ = render_received(view)
    for field in ("observed_value", "method", "evidence_note", "operator_id"):
        assert values[field] in text
    view["actions"] = [offered(received_module.RECORD)]
    view["actions"][0]["fields"] = list(service.fields(received_module.RECORD))
    page = render_navigation(view, received_module.RECORD)
    assert [row["kind"] for row in page["navigations"]] == ["scroll", "focus"]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    view["actions"][0]["enabled"] = False
    page = render_navigation(view)
    assert received_module.RECORD not in [row["id"] for row in page["links"]]


def test_exact_unknown_blank_form_exception_does_not_relax_operator(received):
    from dataclasses import replace
    from rocell.application.wizard_actions import (
        ACTION_BY_ID,
        validate_action_input,
        WizardError,
    )

    service, _ = received
    action = replace(
        ACTION_BY_ID[received_module.SUBMIT],
        fields=tuple(service.fields(received_module.SUBMIT)),
    )
    values = validate_action_input(
        action, {"file_only": True, "operator_id": "submit-operator"}
    )
    assert values["inspection_state"] == "UNKNOWN"
    assert values["inspection_uncertain"] == "UNCERTAIN"
    assert values["observed_manufacturer"] == ""
    assert not any(
        values[f["name"]]
        for f in action.fields
        if f["type"] == "checkbox" and f["name"] != "file_only"
    )
    for change in (
        {"operator_id": ""},
        {"observed_manufacturer": " "},
        {"observed_product_id": False},
    ):
        with pytest.raises(WizardError):
            validate_action_input(
                action, {"file_only": True, "operator_id": "submit-operator", **change}
            )
