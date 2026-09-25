"""Cached terminal rendering and forms, using actual service/codec producers.

The service fixtures model M1/physical facts explicitly. Rendering itself uses
no service calls, files, native APIs, ticket preparation or device effects.
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.ui.terminal import _ReceivedCameraDisplay, _TerminalWizard, _Back
from rocell.application.physical_received_camera_fields import received_camera_fields
from rocell.application.arrival_wizard_service import ArrivalWizardService
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
    record_values,
    module,
)
import test_wizard_received_camera_ui as producer


@pytest.fixture
def shown(received):
    producer.complete_modeled_storage_projection.__wrapped__(received)
    return received


def terminal(value, view=None):
    output = []

    def forbidden(*args, **kwargs):
        raise AssertionError("rendering must not access service/input/sleep")

    wizard = _TerminalWizard(
        SimpleNamespace(__getattr__=forbidden), forbidden, output.append, forbidden
    )
    before = deepcopy(value)
    wizard.show_received_camera(value, view or {})
    assert value == before
    return "\n".join(output)


def render(service):
    view = producer.producer_view(service)
    # Use the raising private entry in positive tests for an actionable trace.
    assert (
        _ReceivedCameraDisplay._validate(view["received_camera_onboarding"], view)
        is view["received_camera_onboarding"]
    )
    text = terminal(view["received_camera_onboarding"], view)
    assert "RECEIVED_CAMERA_NOT_VERIFIED" not in text
    return text, view


@pytest.mark.parametrize("observed", [False, True])
def test_actual_service_all_original_rows_review_identity_and_export(shown, observed):
    service, state = shown
    render(service)
    start(service)
    text, _ = render(service)
    assert "Editable draft" in text
    fill(service, observed=observed)
    if observed:
        run(service, module.SUBMIT, observed_submission_values(service))
    else:
        submit(service)
    text, waiting = render(service)
    assert (
        "Receipt completeness assessment: " + ("PASS" if observed else "BLOCKED")
        in text
    )
    assert all(record in text for record in _ReceivedCameraDisplay.RECORDS)
    for row in waiting["received_camera_onboarding"]["collection"]["notebook"][
        "document"
    ]["rows"]:
        for key in ("observed_value", "method", "evidence_note", "operator_id"):
            assert row["observation"][key] in text
    review(service)
    text, _ = render(service)
    assert "Reviewer label: receipt-reviewer" in text
    if observed:
        assert (
            "Stage 3 receipt accepted only" in text
            and "Stage 4 remains PENDING" in text
        )
        run(service, module.IDENTITY)
        text, _ = render(service)
        assert (
            "Stage 4 identity was explicitly requested and remains WAITING_OPERATOR"
            in text
        )
        assert "MODELED-TEST-ONLY" in text and "B0477" in text
    else:
        assert "Stage 3 receipt accepted only" not in text
        assert "Structured inspection UNKNOWN" in text
    run(
        service,
        module.EXPORT,
        export_parent=service.workspace / "software" / "runs" / "wizard-exports",
    )
    before = len(state["events"]), len(state["references"]), state["enters"]
    text, view = render(service)
    assert "Separate received metadata export" in text
    assert before == (len(state["events"]), len(state["references"]), state["enters"])
    pointer = ArrivalWizardService._received_camera_export_pointer(
        SimpleNamespace(_received_camera_view=service.view)
    )
    text = terminal(pointer)
    assert (
        "RECEIVED METADATA POINTER ONLY" in text
        and "Original retained notebook" not in text
    )
    assert "physical_received_camera_export" in text
    assert pointer["original_received_documents_included"] is False


def test_actual_draft_context_tampering_is_withheld_and_no_raw_leak(shown):
    service, _ = shown
    start(service)
    original = producer.producer_view(service)
    changes = (
        lambda p: p.update(source_sha256="f" * 64),
        lambda p: p.update(hardware_qualified=True),
        lambda p: p["draft"].update(raw_media="MUST_NOT_RENDER"),
        lambda p: p["draft"]["coverage"].update(observed=16),
        lambda p: p["original_context"].update(header_sha256="f" * 64),
        lambda p: p["publication"].update(status="PENDING"),
        lambda p: p["stage_states"].update(camera_receipt="PASS"),
        lambda p: p["draft"]["rows"][0].update(measurement="MUST_NOT_RENDER"),
    )
    for change in changes:
        view = deepcopy(original)
        change(view["received_camera_onboarding"])
        text = terminal(view["received_camera_onboarding"], view)
        assert "RECEIVED_CAMERA_NOT_VERIFIED" in text
        assert "MUST_NOT_RENDER" not in text


def test_actual_roles_exact_subject_and_authority_tampering_is_withheld(shown):
    service, _ = shown
    start(service)
    fill(service, observed=True)
    run(service, module.SUBMIT, observed_submission_values(service))
    review(service)
    _, original = render(service)
    for path, value in (
        (("review", "assessment_sha256"), "f" * 64),
        (("assessment", "foundation", "flatness_acceptance"), "PASS"),
        (("inspection", "authority", "power_authorized"), True),
        (("notebook", "reference", "stage"), "workspace_sources"),
        (("review", "reviewer_id"), "RECEIPT-OPERATOR"),
        (("submission", "binding", "static_contract", "review"), "f" * 64),
    ):
        view = deepcopy(original)
        item = view["received_camera_onboarding"]["collection"]
        for key in path[:-1]:
            item = item[key]
        item[path[-1]] = value
        assert "RECEIVED_CAMERA_NOT_VERIFIED" in terminal(
            view["received_camera_onboarding"], view
        )


def test_pending_historical_and_literal_text_stay_separate(shown):
    service, _ = shown
    start(service, publish=False)
    text, _ = render(service)
    assert "Publication pending: draft, original collection" in text
    assert "Editable draft" not in text
    service.invalidate()
    text, _ = render(service)
    assert "HISTORICAL ONLY" in text
    # Use another already supported real draft transaction only after the failed
    # candidate is exported; no publication call is invented to clear the hold.
    run(
        service,
        module.EXPORT,
        export_parent=service.workspace / "software" / "runs" / "wizard-exports",
    )
    service.observe_setup()
    start(service)
    values = record_values(service.view()["draft"]["rows"][0])
    values.update(
        observed_value="unknown_value_<script>not_code</script>",
        method="literal_method_with_underscores",
        evidence_note="not_a_file",
        operator_id="operator_label",
    )
    run(service, module.RECORD, values)
    text, _ = render(service)
    assert values["observed_value"] in text and values["method"] in text
    service.invalidate()
    text, _ = render(service)
    assert "HISTORICAL ONLY" in text and "Next explicit action" not in text


def wizard_for_inputs(answers):
    output, prompts = [], []
    iterator = iter(answers)

    def ask(prompt):
        prompts.append(prompt)
        return next(iterator)

    def forbidden(*args, **kwargs):
        raise AssertionError("gather is not ticket preparation or execution")

    service = SimpleNamespace(prepare_action=forbidden, execute_action=forbidden)
    return _TerminalWizard(service, ask, output.append, forbidden), output, prompts


def test_exact_33_field_unknown_form_no_automatic_original_or_model_choice():
    fields = list(
        received_camera_fields(
            module.SUBMIT,
            notebook=None,
            choices=[
                {"value": "intake-file-" + "1" * 32, "label": "Explicit modeled choice"}
            ],
        )
    )
    assert len(fields) == 33
    answers = ["yes", "operator"] + [""] * 31
    wizard, output, prompts = wizard_for_inputs(answers)
    values = wizard.gather({"action_id": module.SUBMIT, "fields": fields})
    assert len(values) == len(prompts) == 33
    assert values["inspection_state"] == "UNKNOWN"
    assert values["inspection_uncertain"] == "UNCERTAIN"
    assert (
        values["body_condition"]
        == values["lens_condition"]
        == values["connector_condition"]
        == "UNCERTAIN"
    )
    assert all(
        values[name] == ""
        for name in _ReceivedCameraDisplay.SUBMIT_FIELDS
        if name.startswith("attachment_")
        or name
        in (
            "purchase_choice",
            "inspection_image_choice",
            "observed_manufacturer",
            "observed_product_id",
            "observed_camera_serial",
            "observed_lens_focal_length_mm",
        )
    )
    assert not any(
        values[field["name"]]
        for field in fields
        if field["type"] == "checkbox" and field["name"] != "file_only"
    )
    assert "Explicit modeled choice" in "\n".join(output)


@pytest.mark.parametrize(
    "fault", ["other_action", "extra", "missing", "reorder", "raw_field"]
)
def test_larger_form_allowance_is_only_exact_received_submit_roster(fault):
    fields = list(received_camera_fields(module.SUBMIT, notebook=None, choices=[]))
    action = {"action_id": module.SUBMIT, "fields": fields}
    if fault == "other_action":
        action["action_id"] = "anything_else"
    elif fault == "extra":
        fields.append(dict(name="extra", label="Extra", type="text", required=False))
    elif fault == "missing":
        fields.pop()
    elif fault == "reorder":
        fields[1], fields[2] = fields[2], fields[1]
    else:
        fields[2] = dict(name="path", label="Path", type="text", required=False)
    wizard, _, prompts = wizard_for_inputs([])
    with pytest.raises(ValueError):
        wizard.gather(action)
    assert not prompts


def test_draft_question_context_is_shown_only_for_current_exact_record(shown):
    service, _ = shown
    start(service)
    view = producer.producer_view(service)
    action = {"action_id": module.RECORD, "fields": list(service.fields(module.RECORD))}
    wizard, output, _ = wizard_for_inputs(
        [
            "yes",
            "1",
            "UNKNOWN",
            "Not received",
            "No measurement",
            "No attachment",
            "operator",
        ]
    )
    values = wizard.gather(action, view)
    assert values["record_id"] == "INT-001"
    question = service.view()["draft"]["rows"][0]
    assert question["measurement"] in "\n".join(output)
    assert question["candidate_or_requirement"] in "\n".join(output)
    view["received_camera_onboarding"]["publication"]["status"] = "HISTORICAL_HELD"
    wizard, _, prompts = wizard_for_inputs([])
    with pytest.raises(ValueError, match="unavailable"):
        wizard.gather(action, view)
    assert not prompts


def test_back_still_never_submits_any_action():
    fields = list(received_camera_fields(module.SUBMIT, notebook=None, choices=[]))
    wizard, _, _ = wizard_for_inputs([":back"])
    with pytest.raises(_Back):
        wizard.gather({"action_id": module.SUBMIT, "fields": fields})
