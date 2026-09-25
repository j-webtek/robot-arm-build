"""Received service + actual codecs/design, modeled M1/physical observations.

No native/device/OS inventory or hardware qualification occurs. Original-store
scopes and completion logging are explicitly modeled; separate reader tests use
actual NTFS. Inbox cases use actual bounded test files, not camera acquisitions.
"""

from copy import deepcopy
from pathlib import Path
from threading import Event
import json

import pytest

from rocell.application import physical_received_camera_service as module
from rocell.application import physical_received_camera_submission as codec
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_static_camera_onboarding_service import (
    static_service,
    collect,
    review as static_review,
    BEGIN,
)
from test_physical_source_qualification_service import modeled
from test_physical_camera_intake_setup import setup_flow
from test_physical_source_qualification_readback import source_model
from test_physical_camera_intake_session import intake_model, read
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_session import SOURCE

RAW = b"MODELED PURCHASE AND MEASUREMENT ORIGINAL; NOT RECEIVED HARDWARE.\n"
PNG = b"\x89PNG\r\n\x1a\nMODELED OPAQUE TEST ORIGINAL; NOT A CAMERA IMAGE."


def run(
    service,
    action,
    values=None,
    *,
    publish=True,
    cancellation=None,
    context=None,
    progress=None,
    export_parent=None
):
    """Model the exact completion handoff; not an Arrival or real event-log test."""
    result = service.perform(
        action,
        values or {"file_only": True},
        expected_context_sha256=(
            service.context_sha256() if context is None else context
        ),
        cancellation=cancellation or Event(),
        progress=progress or (lambda _: None),
        **({"export_parent": export_parent} if export_parent is not None else {}),
    )
    service.validate_publication(result)
    if publish:
        service.setup.publication_completed("modeled-completion-log")
        service.publication_completed("modeled-completion-log")
    return result


@pytest.fixture
def received(static_service, monkeypatch):
    static, state = static_service
    collect(static)
    static_review(static)
    run(static, BEGIN)
    service = module.PhysicalReceivedCameraService(static.setup)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    service.observe_setup()
    return service, state


def start(service, mode="BLANK", **kwargs):
    return run(service, module.START, {"file_only": True, "mode": mode}, **kwargs)


def record_values(row, *, observed=False):
    value = {"INT-003": "17.5", "INT-004": "18.5", "INT-005": "0"}.get(
        row["record_id"],
        (
            "1"
            if row["unit"] in {"mm", "g"}
            else "MODELED observation, not received hardware"
        ),
    )
    return dict(
        file_only=True,
        record_id=row["record_id"],
        observation_status="OBSERVED" if observed else "UNKNOWN",
        observed_value=value if observed else "Hardware not received; no measurement.",
        method="Explicit modeled fixture, no hardware inspected.",
        evidence_note="Test-only observation; no physical qualification.",
        operator_id="receipt-operator",
    )


def fill(service, *, observed=False):
    for row in service.view()["draft"]["rows"]:
        run(service, module.RECORD, record_values(row, observed=observed))


def submit(service, **kwargs):
    return run(
        service,
        module.SUBMIT,
        {
            "file_only": True,
            "operator_id": "receipt-operator",
            "inspection_state": "UNKNOWN",
        },
        **kwargs,
    )


def review(service, **kwargs):
    return run(
        service,
        module.REVIEW,
        {
            "file_only": True,
            "reviewer_id": "receipt-reviewer",
            "decision": "ACKNOWLEDGE_EXACT",
        },
        **kwargs,
    )


def observed_submission_values(service):
    run(service, module.DISCOVER)
    (service.inbox.root / "modeled-purchase.txt").write_bytes(RAW)
    (service.inbox.root / "modeled-image.png").write_bytes(PNG)
    run(service, module.DISCOVER)
    choices = {
        row["basename"]: row["choice_id"] for row in service.inbox.view()["files"]
    }
    return dict(
        file_only=True,
        operator_id="receipt-operator",
        inspection_state="RECORDED",
        inspection_observed_now=True,
        observed_manufacturer="Arducam",
        observed_product_id="B0477",
        observed_camera_serial="MODELED-TEST-ONLY",
        observed_lens_focal_length_mm="16",
        body_condition="ACCEPTABLE",
        lens_condition="ACCEPTABLE",
        connector_condition="ACCEPTABLE",
        identity_label_legible=True,
        purchase_record_matches=True,
        package_contents_complete=True,
        inspection_uncertain=False,
        purchase_choice=choices["modeled-purchase.txt"],
        inspection_image_choice=choices["modeled-image.png"],
        **{
            "attachment_" + row["record_id"]: choices["modeled-purchase.txt"]
            for row in service.view()["draft"]["rows"]
        },
    )


def republish_original(service, state):
    """Explicit modeled readback/log; never collection or repair."""
    setup = service.setup
    setup.session.refresh(cancellation=Event(), progress=lambda _: None)
    original = read(setup.session, state["header"].header_sha256)
    setup._adopt_source_workflow(original)
    setup._publication = {
        "status": "CURRENT",
        "operation_id": "modeled-original-readback-log",
    }
    service.observe_setup()
    return original


def test_unknown_then_explicit_revision_modeled_receipt_pass_and_identity(received):
    service, state = received
    original_source = service.setup.original_source_workflow()["review"]
    before = len(state["references"]), len(state["events"])
    assert service.view()["next_action"] == module.START
    start(service)
    assert service.view()["draft"]["coverage"] == dict(
        total=16, observed=0, unknown=0, unrecorded=16
    )
    fill(service)
    assert before == (len(state["references"]), len(state["events"]))
    draft = service.view()["draft"]
    submit(service)
    first = service.setup.original_source_workflow()["received_camera_cycles"][0]
    assert first["state"] == "REVIEW_PENDING"
    assert first["assessment"]["document"]["verdict"] == "BLOCKED"
    assert service.view()["draft"] is None
    assert first["notebook"]["evidence_sha256"] == draft["snapshot_sha256"]
    review(service)
    assert service.view()["status"] == "REVIEWED_BLOCKED"
    first = service.setup.original_source_workflow()["received_camera_cycles"][0]
    start(service, "REVISE_LAST")
    revised = service.view()["draft"]
    assert revised["rows"] == first["notebook"]["document"]["rows"]
    assert revised["previous_sha256"] == first["notebook"]["evidence_sha256"]
    assert (
        service.view()["draft_origin_notebook_sha256"]
        == first["notebook"]["evidence_sha256"]
    )
    fill(service, observed=True)
    values = observed_submission_values(service)
    run(service, module.SUBMIT, values)
    latest = service.setup.original_source_workflow()["received_camera_cycles"][-1]
    assert latest["assessment"]["document"]["verdict"] == "PASS"
    assert latest["state"] == "REVIEW_PENDING"
    assert len(latest["originals"]) == 2
    assert service.view()["stage_states"][STAGE_ORDER[3].value] == "PENDING"
    review(service)
    assert service.view()["status"] == "REVIEWED_PASS"
    assert service.view()["next_action"] == module.IDENTITY
    run(service, module.IDENTITY)
    assert (
        state["events"][-1].stage is STAGE_ORDER[3] and not state["events"][-1].evidence
    )
    assert service.view()["stage_states"][STAGE_ORDER[3].value] == "WAITING_OPERATOR"
    assert service.view()["next_action"] is None
    assert service.setup.original_source_workflow()["review"] == original_source
    history = service.retained_diagnostics()
    assert (
        len(history["cycles"]) == 2
        and RAW not in canonical(history)
        and PNG not in canonical(history)
    )
    for flag in module._FLAGS:
        assert service.view()[flag] is False


def test_draft_pending_exact_publication_and_cached_views_are_inert(
    received, monkeypatch
):
    service, state = received
    result = start(service, publish=False)
    assert (
        service.view()["draft"] is None
        and service.view()["publication"]["status"] == "PENDING"
    )
    altered = deepcopy(result)
    altered["steps"][0]["report"]["draft_sha256"] = "f" * 64
    with pytest.raises(WizardError):
        service.validate_publication(altered)
    service.setup.publication_completed("modeled-log")
    service.publication_completed("modeled-log")
    before = (
        state["reads"],
        state["enters"],
        len(state["references"]),
        len(state["events"]),
    )
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: pytest.fail("view source I/O")
    )
    service.view()["draft"]["rows"].clear()
    for action in module.ACTIONS:
        service.fields(action)
        service.blocked_reason(action)
    service.context_sha256()
    assert len(service.view()["draft"]["rows"]) == 16
    assert before == (
        state["reads"],
        state["enters"],
        len(state["references"]),
        len(state["events"]),
    )


@pytest.mark.parametrize("fault", ["stop", "source", "context", "file-only", "mode"])
def test_draft_preflight_failure_has_no_original_mutation(received, fault):
    service, state = received
    event, expected = Event(), service.context_sha256()
    values = {"file_only": True, "mode": "BLANK"}
    if fault == "stop":
        event.set()
    elif fault == "source":
        state["source"] = "f" * 64
    elif fault == "context":
        expected = "f" * 64
    elif fault == "file-only":
        values["file_only"] = False
    else:
        values["mode"] = "AUTOMATIC"
    before = len(state["references"]), len(state["events"]), state["enters"]
    with pytest.raises((WizardError, ValueError)):
        run(service, module.START, values, context=expected, cancellation=event)
    assert before == (len(state["references"]), len(state["events"]), state["enters"])
    assert service.view()["draft"] is None


@pytest.mark.parametrize(
    "extra",
    [
        {"operator_id": "../operator"},
        {"inspection_state": "RECORDED"},
        {"inspection_state": "UNKNOWN", "inspection_observed_now": True},
        {"inspection_state": "UNKNOWN", "observed_manufacturer": "Arducam"},
        {"inspection_state": "UNKNOWN", "observed_lens_focal_length_mm": "16"},
        {"inspection_state": "UNKNOWN", "body_condition": "ACCEPTABLE"},
        {"inspection_state": "UNKNOWN", "identity_label_legible": True},
        {"attachment_INT-003": "unpublished"},
    ],
)
def test_invalid_submit_fields_do_not_append_originals(received, extra):
    service, state = received
    start(service)
    fill(service)
    before = len(state["references"]), len(state["events"]), state["enters"]
    values = {
        "file_only": True,
        "operator_id": "receipt-operator",
        "inspection_state": "UNKNOWN",
        **extra,
    }
    with pytest.raises((WizardError, ValueError)):
        run(service, module.SUBMIT, values)
    assert before == (len(state["references"]), len(state["events"]), state["enters"])


def test_observed_row_requires_original_before_store(received):
    service, state = received
    start(service)
    row = service.view()["draft"]["rows"][0]
    run(service, module.RECORD, record_values(row, observed=True))
    before = len(state["references"]), len(state["events"])
    with pytest.raises(WizardError, match="OBSERVED"):
        submit(service)
    assert before == (len(state["references"]), len(state["events"]))


def test_stale_typed_draft_launch_is_not_rebound_at_submission(received):
    service, state = received
    start(service)
    fill(service)
    # A genuine immutable notebook from a different launch is still not the
    # current server-owned draft, even with a freshly computed request context.
    service._draft = service._draft.revise_for_launch(
        launch_session_id="wizard-other-launch"
    )
    before = len(state["references"]), len(state["events"]), state["enters"]
    with pytest.raises((WizardError, ValueError)):
        submit(service)
    assert before == (len(state["references"]), len(state["events"]), state["enters"])


def test_same_reviewer_is_refused_before_append(received):
    service, state = received
    start(service)
    fill(service)
    submit(service)
    before = len(state["references"]), len(state["events"])
    with pytest.raises(codec.ReceivedCameraSubmissionError):
        run(
            service,
            module.REVIEW,
            {
                "file_only": True,
                "reviewer_id": "RECEIPT-OPERATOR",
                "decision": "ACKNOWLEDGE_EXACT",
            },
        )
    assert before == (len(state["references"]), len(state["events"]))
    review(service)
    assert service.view()["status"] == "REVIEWED_BLOCKED"


@pytest.mark.parametrize("fault", ["assessment-store", "refresh", "lease-exit"])
def test_partial_retention_survives_no_replay_and_explicit_original_restart(
    received, monkeypatch, fault
):
    service, state = received
    start(service)
    fill(service)
    draft_sha = service.view()["draft"]["snapshot_sha256"]
    original = service._retain

    def fail(tx, payload, role, receipt_id, **kwargs):
        if fault == "assessment-store" and role == "assessment":
            raise RuntimeError("modeled assessment store failure")
        return original(tx, payload, role, receipt_id, **kwargs)

    monkeypatch.setattr(service, "_retain", fail)
    if fault == "refresh":
        state["refresh_error"] = True
    elif fault == "lease-exit":
        state["exit_failure"] = True
    with pytest.raises((WizardError, ValueError, RuntimeError)):
        submit(service)
    retained = service.retained_diagnostics()
    assert retained["attempt"]["records"]["notebook"]["evidence_sha256"] == draft_sha
    assert (
        retained["attempt"]["records"]["submission"]["retention"]
        == "M1_FULL_BYTES_READ_BACK"
    )
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.blocked_reason(module.SUBMIT)
    state["refresh_error"] = state["exit_failure"] = False
    original_workflow = republish_original(service, state)
    # Same-instance refresh must retire the now-original submitted notebook;
    # otherwise the old draft masks the actual REVIEW_PENDING/partial state.
    assert service.view()["draft"] is None
    assert service.view()["status"] == (
        "INCOMPLETE_HELD" if fault == "assessment-store" else "REVIEW_PENDING"
    )
    assert service.view()["next_action"] == (
        None if fault == "assessment-store" else module.REVIEW
    )
    fresh = module.PhysicalReceivedCameraService(service.setup)
    before = state["reads"], state["enters"], len(state["events"])
    fresh.observe_setup()
    assert before == (state["reads"], state["enters"], len(state["events"]))
    assert fresh.view()["collection"]["notebook"]["evidence_sha256"] == draft_sha
    assert original_workflow["received_camera_cycles"][0]["state"] == (
        "INCOMPLETE" if fault == "assessment-store" else "REVIEW_PENDING"
    )
    assert fresh.blocked_reason(module.SUBMIT)


def test_new_service_adopts_exact_frozen_subjects_not_editable_draft(received):
    service, state = received
    start(service)
    fill(service)
    submit(service)
    review(service)
    expected = service.setup.original_source_workflow()["received_camera_cycles"][-1]
    fresh = module.PhysicalReceivedCameraService(service.setup)
    before = state["reads"], state["enters"], len(state["events"])
    fresh.observe_setup()
    current = fresh.view()
    assert current["draft"] is None and current["status"] == "REVIEWED_BLOCKED"
    assert (
        current["collection"]["notebook"]["document"]
        == expected["notebook"]["document"]
    )
    assert current["collection"]["inspection"] is None
    assert before == (state["reads"], state["enters"], len(state["events"]))
    assert (
        fresh.retained_diagnostics()["cycles"]
        == service.retained_diagnostics()["cycles"]
    )


def test_changed_review_original_is_refused_before_review_retention(received):
    service, state = received
    start(service)
    fill(service)
    submit(service)
    original = service.setup.original_source_workflow()["received_camera_cycles"][-1]
    state["payloads"][original["notebook"]["reference"]["evidence_id"]] += b" "
    before = len(state["references"]), len(state["events"])
    with pytest.raises((WizardError, ValueError, RuntimeError)):
        review(service)
    assert before == (len(state["references"]), len(state["events"]))


@pytest.mark.parametrize("fault", ["stop", "source", "context"])
def test_submit_final_pre_scope_changes_hold_before_any_original_write(received, fault):
    service, state = received
    start(service)
    fill(service)
    event = Event()
    before = len(state["references"]), len(state["events"])

    def change(message):
        if message.startswith("Retaining and rereading"):
            if fault == "stop":
                event.set()
            elif fault == "source":
                state["source"] = "f" * 64
            else:
                service.setup._source_workflow["session_head_sha256"] = "f" * 64

    with pytest.raises((WizardError, ValueError, RuntimeError)):
        submit(service, cancellation=event, progress=change)
    assert before == (len(state["references"]), len(state["events"]))
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.retained_diagnostics()["attempt"]["records"] == {}


@pytest.mark.parametrize("redact", [False, True])
def test_failed_unlogged_candidate_survives_refresh_until_explicit_metadata_export(
    received, redact
):
    from rocell.application.physical_received_camera_export import (
        restore_received_camera_family,
    )
    from rocell.application.wizard_diagnostic_export import verify_export

    service, state = received
    start(service)
    original_draft = service.view()["draft"]
    row = original_draft["rows"][0]
    values = record_values(row)
    if redact:
        values["evidence_note"] = (
            "Modeled credential example password=example_secret; no real credentials."
        )
    result = run(service, module.RECORD, values, publish=False)
    failed_sha = result["steps"][0]["report"]["draft_sha256"]
    before = len(state["references"]), len(state["events"])
    service.invalidate()  # Explicit modeled completion-log/late-Stop failure.
    failed = deepcopy(service.retained_diagnostics()["failed_draft"])
    assert digest(canonical(failed["document"])) == failed_sha
    service.observe_setup()  # Existing original setup is still independently current.
    assert service.retained_diagnostics()["failed_draft"] == failed
    assert service.view()["draft"] == original_draft
    for action in (module.START, module.RECORD, module.SUBMIT):
        assert service.blocked_reason(action)
    with pytest.raises(WizardError):
        run(service, module.RECORD, values)
    assert before == (len(state["references"]), len(state["events"]))
    parent = service.workspace / "assigned-received-metadata-export"
    exported = run(service, module.EXPORT, export_parent=parent)
    receipt = exported["steps"][0]["report"]["metadata_export"]
    directory = Path(receipt["path"])
    assert verify_export(directory)["valid"]
    packet = json.loads(
        (directory / "attachment-received-camera-draft.json").read_bytes()
    )
    restored = restore_received_camera_family(packet)
    assert packet["credential_redaction_applied"] is redact
    assert packet["original_bytes_preserved"] is (not redact)
    original_family = {
        "draft": {
            key: value
            for key, value in original_draft.items()
            if key != "snapshot_sha256"
        },
        "draft_origin_notebook_sha256": None,
        "failed_draft": failed,
    }
    assert packet["original_family_sha256"] == digest(canonical(original_family))
    if redact:
        assert "example_secret" not in json.dumps(restored)
        assert (
            restored["failed_draft"]["document"]["rows"][0]["observation"][
                "observed_value"
            ]
            == values["observed_value"]
        )
    else:
        assert restored["failed_draft"] == failed
    # The saved bundle covers the exact original subject ID. Redacted metadata
    # remains explicitly diagnostic, not a byte-identical private backup.
    assert service.blocked_reason(module.RECORD) is None
    run(service, module.RECORD, record_values(row))
    assert service.retained_diagnostics()["failed_draft"] == failed


@pytest.mark.parametrize("fault", ["stop", "source"])
def test_failed_computed_draft_is_retained_before_returned_result(
    received, monkeypatch, fault
):
    service, state = received
    event = Event()
    original = service._check

    def late(cancellation, deadline, **kwargs):
        if service._pending_draft is not None:
            if fault == "stop":
                event.set()
            else:
                state["source"] = "f" * 64
        return original(cancellation, deadline, **kwargs)

    monkeypatch.setattr(service, "_check", late)
    before = len(state["references"]), len(state["events"])
    with pytest.raises(WizardError):
        start(service, cancellation=event)
    failed = service.retained_diagnostics()["failed_draft"]
    assert failed["document"]["coverage"]["unrecorded"] == 16
    assert service.view()["draft"] is None
    assert before == (len(state["references"]), len(state["events"]))


def test_direct_setup_observation_does_not_publish_unlogged_pending_draft(received):
    service, state = received
    result = start(service, publish=False)
    expected = result["steps"][0]["report"]["draft_sha256"]
    before = state["reads"], state["enters"], len(state["events"])
    service.observe_setup()
    current = service.view()
    assert current["draft"] is None
    assert current["next_action"] == module.EXPORT
    assert (
        digest(canonical(service.retained_diagnostics()["failed_draft"]["document"]))
        == expected
    )
    assert service.blocked_reason(module.START)
    assert before == (state["reads"], state["enters"], len(state["events"]))


def test_lost_submit_completion_refresh_retires_submitted_draft_and_allows_review(
    received,
):
    service, state = received
    start(service)
    fill(service)
    original_draft = deepcopy(service.view()["draft"])
    submit(service, publish=False)
    before = len(state["references"]), len(state["events"])
    # Explicit modeled outer completion-log failure after original commit.
    service.setup.invalidate()
    service.invalidate()
    workflow = republish_original(service, state)
    current = service.view()
    assert current["draft"] is None
    assert current["status"] == "REVIEW_PENDING"
    assert current["next_action"] == module.REVIEW
    assert service.blocked_reason(module.REVIEW) is None
    assert service.blocked_reason(module.SUBMIT)
    assert before == (len(state["references"]), len(state["events"]))
    assert (
        workflow["received_camera_cycles"][-1]["notebook"]["evidence_sha256"]
        == original_draft["snapshot_sha256"]
    )
    review(service)
    assert service.view()["status"] == "REVIEWED_BLOCKED"
    assert service.view()["next_action"] == module.START
    start(service, "REVISE_LAST")
    assert service.view()["draft"]["rows"] == original_draft["rows"]
    assert (
        service.view()["draft_origin_notebook_sha256"]
        == original_draft["snapshot_sha256"]
    )


@pytest.mark.parametrize("retained_notebook", [False, True])
def test_failed_submit_retires_only_notebook_actually_retained_in_new_cycle(
    received, monkeypatch, retained_notebook
):
    service, state = received
    start(service)
    fill(service)
    original_draft = deepcopy(service.view()["draft"])
    original = service._retain

    def fail(tx, payload, role, receipt_id, **kwargs):
        if role == ("submission" if retained_notebook else "notebook"):
            raise RuntimeError("modeled original retention interruption")
        return original(tx, payload, role, receipt_id, **kwargs)

    monkeypatch.setattr(service, "_retain", fail)
    with pytest.raises(RuntimeError, match="retention interruption"):
        submit(service)
    before = len(state["references"]), len(state["events"])
    workflow = republish_original(service, state)
    current = service.view()
    assert current["draft"] == (None if retained_notebook else original_draft)
    if retained_notebook:
        assert current["status"] == "INCOMPLETE_HELD"
        assert (
            workflow["received_camera_cycles"][-1]["notebook"]["evidence_sha256"]
            == original_draft["snapshot_sha256"]
        )
        assert service.blocked_reason(module.RECORD)
        assert service.blocked_reason(module.START)
    else:
        assert workflow["schema"].endswith(".v5")
    assert service.blocked_reason(module.SUBMIT)
    republish_original(service, state)
    assert before == (len(state["references"]), len(state["events"]))


def test_blank_successor_identical_to_prior_notebook_survives_until_new_submission(
    received,
):
    service, state = received
    start(service, "BLANK")
    blank = deepcopy(service.view()["draft"])
    submit(service)
    review(service)
    first = service.setup.original_source_workflow()["received_camera_cycles"][-1]
    assert first["state"] == "REVIEWED_BLOCKED"
    assert first["notebook"]["evidence_sha256"] == blank["snapshot_sha256"]
    start(service, "BLANK")
    successor = deepcopy(service.view()["draft"])
    assert successor == blank  # No timestamps/default observations in a blank notebook.
    before = len(state["references"]), len(state["events"])
    service.observe_setup()
    republish_original(service, state)
    assert service.view()["draft"] == successor
    assert service.view()["status"] == "DRAFT"
    assert service.view()["next_action"] == module.RECORD
    assert before == (len(state["references"]), len(state["events"]))
    # Identical bytes become a different original only after this new cycle
    # actually retains them under its own label/reference and commits subjects.
    submit(service, publish=False)
    service.setup.invalidate()
    service.invalidate()
    workflow = republish_original(service, state)
    latest = workflow["received_camera_cycles"][-1]
    assert latest["receipt_id"] != first["receipt_id"]
    assert latest["notebook"]["reference"] != first["notebook"]["reference"]
    assert latest["notebook"]["evidence_sha256"] == first["notebook"]["evidence_sha256"]
    assert service.view()["draft"] is None
    assert service.view()["status"] == "REVIEW_PENDING"
    assert service.view()["next_action"] == module.REVIEW
