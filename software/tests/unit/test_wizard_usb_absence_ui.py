"""Actual original codecs/renderers, explicitly MODELED storage/physical facts.

No production helper, CIM or USB API runs. A separate finite Node fake-DOM
subprocess renders retained values; it is not native hardware execution.
Public genuine-M1 five-action acceptance is independently owned by its lane.
"""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event
import time

import pytest

from rocell.application import physical_usb_absence_service as absence
from rocell.application import physical_usb_identity_service as service
from rocell.application import physical_camera_usb_absence_readback as reader
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_usb_identity_export import (
    prepare_usb_identity_diagnostics_export,
)
from rocell.application.wizard_actions import WizardError, ACTION_BY_ID
from rocell.providers.windows import usb_presence_registration as registration
from rocell.providers.windows.usb_identity_protocol import canonical
from rocell.ui.terminal import _UsbQualificationDisplay
from test_physical_camera_usb_absence_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    nominal_original,
    absence_subjects,
    presence_result,
    refresh_read,
    change_last_event,
)
from test_physical_camera_intake_setup import setup_flow
from test_wizard_usb_qualification_ui import (
    view_for,
    complete_setup,
    prerequisite_summary,
)
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_usb_observed_projection import forbid_native_execution


def files(runtime, **kwargs):
    return dict(
        schema=registration.INSPECTION_SCHEMA,
        runtime_registration_sha256=runtime.sha256,
        source_sha256=runtime.to_dict()["source_sha256"],
        status="FILES_MATCHED",
        files=[
            dict(path=p, sha256=h, bytes=n)
            for p, h, n in (
                *registration.FIXED_SOURCE_PINS,
                (
                    registration.BUILD_RECORD_PATH,
                    registration.BUILD_RECORD_SHA256,
                    registration.BUILD_RECORD_BYTES,
                ),
                (
                    registration.HELPER_PATH,
                    registration.HELPER_SHA256,
                    registration.HELPER_BYTES,
                ),
            )
        ],
        physical_authority=False,
        hardware_qualified=False,
        device_io_performed=False,
    )


def adopt(setup, workflow):
    setup._adopt_source_workflow(workflow)
    setup._publication = dict(status="CURRENT", operation_id="MODELED-original-log")
    owner = service.PhysicalUsbIdentityService(setup)
    owner.observe_setup()
    return owner


def snapshot(owner, complete_setup):
    view = view_for(complete_setup)
    bound = owner._context()
    setup = view["physical_camera_setup"]
    setup["session"]["binding"].update(
        session_id=bound["session_id"],
        cell_id=bound["cell_id"],
        launch_id=bound["origin_launch_id"],
    )
    setup["session"]["verification"]["session"].update(
        session_id=bound["session_id"], header_sha256=bound["header_sha256"]
    )
    setup["session"]["verification"]["cell"]["cell_id"] = bound["cell_id"]
    setup["prerequisites"]["evidence_sha256"] = bound["prerequisites_sha256"]
    setup["session"]["stages"][3]["state"] = owner._stages["camera_identity"]
    view["usb_qualification"] = owner.qualification_view()
    return view


def check_rendered(view):
    _UsbQualificationDisplay._validate(view["usb_qualification"], view)
    before = canonical(view)
    texts = render_snapshot(view)
    assert all("USB_QUALIFICATION_NOT_VERIFIED" not in t for t in texts)
    assert canonical(view) == before
    return texts


@pytest.fixture
def file_service(ready, setup_flow, monkeypatch, request):
    stop = getattr(request, "param", None)
    made = (
        nominal_original(ready, monkeypatch)
        if stop is None
        else absence_subjects(ready, monkeypatch, stop=stop)
    )
    workflow = made.original if stop is None else refresh_read(ready)
    setup, _, state = setup_flow
    assert setup.session is ready[0]
    state["now"] = time.monotonic_ns()
    monkeypatch.setattr(service, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(service, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(absence, "inspect_usb_presence_runtime", files)
    from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy

    monkeypatch.setattr(
        absence,
        "inspect_usb_presence_stage_policy",
        lambda _: usb_presence_stage_policy(),
    )
    monkeypatch.setattr(
        reader,
        "read_original_usb_absence_campaigns",
        lambda *a, **k: dict(
            identity=(made if stop is None else made.baseline).campaign_originals,
            presence=(),
        ),
    )
    original = state["store"].stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with original(*args, **kwargs) as tx:
            tx.store_evidence = lambda stage, payload, **kw: state["add"](
                payload, label=kw["label"], media=kw["media_type"], stage=stage
            )

            def commit(stage, status, **kw):
                state["advance"](status, kw["detail_code"], kw["evidence"], stage=stage)
                change_last_event(state, occurred_at_ns=kw["occurred_at_ns"])
                return tx.snapshot()

            tx.commit_stage_state = commit
            yield tx

    monkeypatch.setattr(state["store"], "stage_transaction", scope)
    return adopt(setup, workflow), state, made


def run(owner, action, *, publish=True):
    values = {
        f["name"]: (
            True
            if f["type"] == "checkbox"
            else (
                "MODELED-reviewer" if f["name"] == "reviewer_id" else "MODELED-operator"
            )
        )
        for f in owner.fields(action)
    }
    result = owner.perform(
        action,
        values,
        expected_context_sha256=owner.context_sha256(),
        cancellation=Event(),
        progress=lambda _: None,
    )
    ArrivalWizardService._validate_usb_absence_result(action, result)
    owner.validate_publication(result)
    if publish:
        owner.setup.publication_completed("MODELED-absence-log")
        owner.publication_completed("MODELED-absence-log")
    return result


def test_actual_service_begin_review_pending_publication_export(
    file_service, complete_setup
):
    owner, state, made = file_service
    assert owner.blocked_reason(absence.BEGIN) is None
    assert owner.qualification_view()["next_action"] == absence.BEGIN
    before = dict(state["payloads"])
    result = run(owner, absence.BEGIN, publish=False)
    assert result["presence_query_attempted"] is False
    assert owner.qualification_view()["absence"] is None
    assert owner.qualification_view()["publication"]["status"] == "PENDING"
    owner.setup.publication_completed("MODELED-completion")
    owner.publication_completed("MODELED-completion")
    assert before.items() <= state["payloads"].items()
    assert owner.qualification_view()["absence"]["state"] == "PREPARED"
    check_rendered(snapshot(owner, complete_setup))
    run(owner, absence.BOOT_REVIEW)
    card = owner.qualification_view()
    assert card["absence"]["state"] == "BOOT_REVIEWED"
    assert card["next_action"] == absence.BOOT_COLLECT
    check_rendered(snapshot(owner, complete_setup))
    diagnostic = owner.retained_diagnostics()
    assert diagnostic["schema"].endswith(".v4")
    assert diagnostic["qualification_absence"]["boot_review"] is not None
    prepare_usb_identity_diagnostics_export(
        diagnostic, source_sha256=owner.source_sha256, launch_id=owner.launch_id
    )
    assert owner.blocked_reason(absence.BEGIN)


@pytest.mark.parametrize(
    "stop",
    [
        "started",
        "operation",
        "uncommitted",
        "prepared",
        "reviewed",
        "requested",
        "boot",
        "presence_requested",
        "presence",
        "runtime",
        "query",
    ],
)
def test_actual_reader_prefixes_both_cached_renderers(
    ready, setup_flow, complete_setup, monkeypatch, stop
):
    made = absence_subjects(ready, monkeypatch, stop=stop)
    workflow = refresh_read(ready)
    owner = adopt(setup_flow[0], workflow)
    view = snapshot(owner, complete_setup)
    check_rendered(view)
    if stop in {
        "started",
        "operation",
        "uncommitted",
        "requested",
        "boot",
        "presence_requested",
        "query",
    }:
        assert view["usb_qualification"]["next_action"] == service.EXPORT
    owner.invalidate()
    held = snapshot(owner, complete_setup)
    assert held["usb_qualification"]["status"] == "HISTORICAL_HELD"
    check_rendered(held)


@pytest.mark.parametrize("unknown", [False, True])
def test_strict_presence_original_projection_and_unknowns(
    ready, setup_flow, complete_setup, monkeypatch, unknown
):
    made = absence_subjects(ready, monkeypatch, stop="query")
    presence_result(made, unknown=unknown)
    workflow = refresh_read(ready)
    owner = adopt(setup_flow[0], workflow)
    view = snapshot(owner, complete_setup)
    texts = check_rendered(view)
    execution = view["usb_qualification"]["absence"]["execution"]
    assert execution["counter_coverage"] == (
        "NOT_REPORTED" if unknown else "NATIVE_RECEIPT"
    )
    if unknown:
        assert execution["actual_counts"] is None
        assert all("UNKNOWN" in t for t in texts)
    else:
        assert execution["actual_counts"] == dict(
            api_calls=4, device_handle_opens=0, configuration_writes=0, frames=0
        )
        assert all("ABSENT" in t for t in texts)
        assert all("RECONNECT_ABSENCE: RETAINED_BLOCKED" in t for t in texts)
        assert all("RECONNECT_ABSENCE: NOT ACQUIRED" not in t for t in texts)
        for path, bad in (
            (("target", "physical_device_id"), "USB\\VID_FFFF&PID_FFFF"),
            (("execution", "actual_counts", "api_calls"), True),
            (("observation", "provider"), "CALLER_CLAIM"),
            (("host_boot", "last_boot_up_time_utc"), "2026-01-01T00:00:00.0000000Z"),
            (("physical_authority",), True),
        ):
            broken = deepcopy(view)
            subject = broken["usb_qualification"]["absence"]
            for key in path[:-1]:
                subject = subject[key]
            subject[path[-1]] = bad
            assert (
                _UsbQualificationDisplay.validate(broken["usb_qualification"], broken)
                is None
            )
            assert all(
                "USB_QUALIFICATION_NOT_VERIFIED" in t for t in render_snapshot(broken)
            )
    owner._absence.query_attempted = True
    result = owner._absence.result(absence.COLLECT)
    ArrivalWizardService._validate_usb_absence_result(absence.COLLECT, result)
    bad = deepcopy(result)
    bad["presence_api_call_count"] = 0 if unknown else 3
    with pytest.raises(WizardError):
        ArrivalWizardService._validate_usb_absence_result(absence.COLLECT, bad)


@pytest.mark.parametrize("action", sorted(absence.ACTIONS))
def test_actions_remain_explicit_and_closed(file_service, action):
    owner, _, _ = file_service
    fields = owner.fields(action)
    assert fields and all(
        f["default"] is False for f in fields if f["type"] == "checkbox"
    )
    assert not any(
        f["name"] in {"target", "path", "endpoint", "bytes", "base64"} for f in fields
    )
    assert ACTION_BY_ID[action].worker == "physical_usb_identity"
    assert ACTION_BY_ID[action].timeout_s <= 180


def test_stop_source_and_exact_context_refuse_file_action(file_service):
    owner, state, _ = file_service
    values = {
        f["name"]: True if f["type"] == "checkbox" else "MODELED-operator"
        for f in owner.fields(absence.BEGIN)
    }
    before = dict(state["payloads"])
    cancellation = Event()
    cancellation.set()
    with pytest.raises(WizardError):
        owner.perform(
            absence.BEGIN,
            values,
            expected_context_sha256=owner.context_sha256(),
            cancellation=cancellation,
            progress=lambda _: None,
        )
    assert state["payloads"] == before

    with pytest.raises(WizardError):
        owner.perform(
            absence.BEGIN,
            values,
            expected_context_sha256="0" * 64,
            cancellation=Event(),
            progress=lambda _: None,
        )
    assert state["payloads"] == before


@pytest.mark.parametrize("file_service", ["presence"], indirect=True)
def test_service_final_review_keeps_separate_query_and_exact_original(
    file_service, complete_setup
):
    owner, state, made = file_service
    result = run(owner, absence.RUNTIME_REVIEW)
    assert result["presence_query_attempted"] is False
    assert owner.qualification_view()["next_action"] == absence.COLLECT
    current = owner.setup.original_source_workflow()["usb_qualification_absence"]
    assert current["state"] == "RUNTIME_REVIEWED"
    assert current["execution"] is None
    assert current["events"][-1]["evidence"] == [current["runtime_review"]["reference"]]
    check_rendered(snapshot(owner, complete_setup))


@pytest.mark.parametrize("file_service", ["query"], indirect=True)
def test_actual_full_original_facts_callback_double_read_seal(file_service):
    from dataclasses import replace
    from types import SimpleNamespace
    from rocell.application.physical_usb_presence_campaign import (
        PhysicalUsbPresenceCampaign,
    )
    from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy

    owner, state, made = file_service
    workflow = owner.setup.original_source_workflow()
    campaign = PhysicalUsbPresenceCampaign(
        made.subjects["operation"], review=made.subjects["runtime_review"]
    )
    facts = owner._absence._facts(
        workflow,
        owner.setup.current_prerequisite_artifact(),
        campaign,
        usb_presence_stage_policy(),
        lambda: None,
    )
    b = workflow["binding"]
    request = SimpleNamespace(
        cell_id=b["cell_id"],
        session_id=b["session_id"],
        action_id="physical-native-usb-presence",
    )
    actual = state["snapshot"]()
    result = facts(request, actual)
    assert result.runtime_review.sha256 == made.subjects["runtime_review"].sha256
    assert (
        result.runtime_review_event.event_sha256
        == actual.committed_events[-2].event_sha256
    )
    with pytest.raises(WizardError):
        facts(request, replace(actual, evidence=actual.evidence[:-1]))
    extra = replace(actual.evidence[-1], evidence_id="unreviewed-extra-package")
    with pytest.raises(WizardError):
        facts(request, replace(actual, evidence=(*actual.evidence, extra)))


def test_failed_file_inspection_keeps_started_original_and_cannot_resume(
    file_service, monkeypatch
):
    owner, state, _ = file_service

    def fail(*args, **kwargs):
        raise RuntimeError("MODELED fixed-file inspection failed")

    monkeypatch.setattr(absence, "inspect_usb_presence_runtime", fail)
    with pytest.raises(RuntimeError):
        run(owner, absence.BEGIN)
    assert owner.qualification_view()["publication"]["status"] == "HISTORICAL_HELD"
    # An exception does not silently refresh/promote the shared original cache.
    # The successful original commit is retained immediately for export; a
    # later explicit original readback reconstructs the request-only prefix.
    original = owner.setup.session.retained_source_workflow()
    assert "usb_qualification_absence" not in original
    attempt = owner.retained_diagnostics()["qualification_absence_attempt"]
    assert len(attempt["events"]) == 1
    assert attempt["events"][0]["detail_code"].startswith(
        "CAMERA_USB_TRIAL_ABSENCE_PREPARATION_REQUESTED_"
    )
    prepare_usb_identity_diagnostics_export(
        owner.retained_diagnostics(),
        source_sha256=owner.source_sha256,
        launch_id=owner.launch_id,
    )
    assert (
        owner.retained_diagnostics()["qualification_absence_attempt"]["records"] == {}
    )
    assert owner.blocked_reason(absence.BEGIN)


@pytest.mark.parametrize(
    "state,campaign,event",
    [
        ("ORIGINAL_CAMPAIGN_HELD", None, None),
        ("RETAINED_BLOCKED", None, None),
        ("QUERY_REQUESTED", {}, None),
        ("QUERY_REQUESTED", None, {}),
    ],
)
def test_refreshed_original_attempt_is_refused_before_dispatch(
    monkeypatch, state, campaign, event
):
    from types import SimpleNamespace

    def forbidden(*args, **kwargs):
        pytest.fail("a second dispatcher was constructed")

    monkeypatch.setattr(absence, "PhysicalUsbPresenceDispatchOwner", forbidden)
    helper = absence._UsbTrialAbsence(SimpleNamespace())
    workflow = dict(
        usb_qualification_absence=dict(
            state=state, original_campaign=campaign, original_campaign_event=event
        )
    )
    with pytest.raises(WizardError) as caught:
        helper._collect(workflow, None, None, lambda: None, Event())
    assert caught.value.code == "ABSENCE_ORIGINAL_ATTEMPT_ALREADY_RETAINED"
    assert helper.query_attempted is False and helper.dispatch is None
