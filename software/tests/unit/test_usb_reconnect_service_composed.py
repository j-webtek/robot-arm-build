"""Real reconnect service/readers with explicitly modeled storage and metadata.

No production helper, host observer, USB runner, camera or arm API is called.
The log publisher and fixed-file observations are models here; the separate
public NTFS acceptance verifies actual Arrival tickets and completion logs.
"""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event
import time

from rocell.application import physical_usb_identity_service as service
from rocell.application import physical_usb_reconnect_service as reconnect
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay

from test_physical_camera_usb_reconnect_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    refresh_read,
    reconnect_subjects,
)
from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_usb_absence_readback import change_last_event
from test_physical_camera_identity_readback import identity_inputs
from test_physical_usb_identity_service import modeled_files
from test_wizard_usb_absence_ui import adopt, snapshot
from test_wizard_usb_qualification_ui import complete_setup, prerequisite_summary
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered
from test_usb_observed_projection import forbid_native_execution


def fresh_owners(owner):
    supplied = identity_inputs(
        source=owner.source_sha256, launch=owner.launch_id, return_owners=True
    )
    native = supplied["native_camera"].export_snapshot()
    p = native["view"]["provenance"]
    generic = WizardDeviceSelection("physical", owner.launch_id, owner.source_sha256)
    generic.ingest(
        native["generic_review"]["inventory_report"],
        operation_id="MODELED-new-reconnect-generic",
    )
    generic.review(
        generic.choices("CAMERA")[0]["value"], "CAMERA", "MODELED generic reviewer"
    )
    current = WizardNativeCameraEnrollment(
        "physical",
        owner.launch_id,
        owner.source_sha256,
        dict(provenance=p["provider_provenance"], helper_sha256=p["helper_sha256"]),
    )
    current.ingest_inventory(
        native["inventory_packet"],
        operation_id="MODELED-new-reconnect-inventory",
        generic_review=generic.reviewed_candidate("CAMERA"),
    )
    choice = current.choices()[0]["value"]
    current.retain_identity(
        choice, native["identity_packet"], operation_id="MODELED-new-reconnect-identity"
    )
    current.review(choice, "MODELED endpoint reviewer")
    return current, supplied["helper"]


def test_actual_prepare_review_and_cached_refresh_navigation(
    ready, setup_flow, complete_setup, monkeypatch
):
    reconnect_subjects(ready, monkeypatch, stop="operator_event")
    workflow = refresh_read(ready)
    setup, _, state = setup_flow
    owner = adopt(setup, workflow)
    native, helper = fresh_owners(owner)
    state["now"] = time.monotonic_ns()
    monkeypatch.setattr(service, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(service, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(reconnect, "inspect_usb_identity_runtime", modeled_files)
    monkeypatch.setattr(
        reconnect,
        "inspect_usb_identity_stage_policy",
        lambda _: usb_identity_stage_policy(),
    )
    last = [time.time_ns()]

    def ordered_utc():
        last[0] = max(time.time_ns(), last[0] + 1)
        return last[0]

    monkeypatch.setattr(reconnect, "time_ns", ordered_utc)
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
    raw = native.export_snapshot()
    acquisitions = (
        (
            "inventory_devices",
            raw["generic_review"]["operation_id"],
            raw["generic_review"]["inventory_report"],
        ),
        (
            "native_camera_inventory",
            raw["view"]["inventory_operation_id"],
            raw["inventory_packet"],
        ),
        (
            "native_camera_identity",
            raw["view"]["identity"]["operation_id"],
            raw["identity_packet"],
        ),
    )
    for action, operation_id, document in acquisitions:
        token = owner.acquisition_started(action, operation_id, ordered_utc())
        owner.acquisition_published(
            token,
            finished_at_ns=ordered_utc(),
            document=document,
            result_sha256=digest(
                canonical({"MODELED_COMPLETED_LOG_RESULT": operation_id})
            ),
        )
    ledger = deepcopy(owner._reconnect.ledger)
    assert len(ledger["entries"]) == 3
    owner.invalidate()
    view = snapshot(owner, complete_setup)
    assert view["usb_qualification"]["next_action"] == "physical_camera_refresh"
    _UsbQualificationDisplay._validate(view["usb_qualification"], view)
    view["actions"] = [offered("physical_camera_refresh"), offered(reconnect.EXPORT)]
    page = render(view, "physical_camera_refresh")
    assert page["navigations"] == ["camera-action-physical_camera_refresh"]
    view["actions"][0]["enabled"] = False
    assert "physical_camera_refresh" not in [r["id"] for r in render(view)["links"]]
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
    # The view can only recommend refresh from this exact unused current-launch
    # cache. These mutations are test-only, never a restoration API.
    for mutation in (
        "old-launch",
        "missing-ledger",
        "attempted-prepare",
        "source-change",
    ):
        phase = owner._reconnect
        old_launch, old_ledger = owner.launch_id, deepcopy(phase.ledger)
        old_attempted, old_source = set(owner._attempted), owner.source_sha256
        if mutation == "old-launch":
            owner.launch_id = "wizard-" + "a" * 32
        elif mutation == "missing-ledger":
            phase.ledger["entries"].pop()
        elif mutation == "attempted-prepare":
            owner._attempted.add(owner._attempt_key(reconnect.PREPARE, workflow))
        else:
            owner.source_sha256 = "f" * 64
        assert owner.qualification_view()["next_action"] == reconnect.EXPORT
        owner.launch_id, phase.ledger = old_launch, old_ledger
        owner._attempted, owner.source_sha256 = old_attempted, old_source
    # Model the successful explicit original Refresh publication. The real
    # public action path and its file/lease authentication are tested separately.
    setup._publication = dict(status="CURRENT", operation_id="MODELED-refresh-log")
    owner.observe_setup()
    assert owner._reconnect.ledger == ledger
    actor = owner._reconnect._report()["operator_id"]
    for action, values in (
        (reconnect.PREPARE, dict(operator_id=actor, file_only=True)),
        (
            reconnect.REVIEW,
            dict(
                reviewer_id="MODELED distinct reviewer",
                confirm_policy_review=True,
                confirm_runtime_review=True,
                confirm_exact_target=True,
                confirm_boot_metadata=True,
            ),
        ),
    ):
        assert owner.blocked_reason(action, native_camera=native, helper=helper) is None
        result = owner.perform(
            action,
            values,
            native_camera=native,
            helper=helper,
            expected_context_sha256=owner.context_sha256(
                native_camera=native, helper=helper
            ),
            cancellation=Event(),
            progress=lambda _: None,
        )
        ArrivalWizardService._validate_usb_identity_result(action, result)
        assert result["steps"][0]["report"]["usb_query_attempted"] is False
        assert result["steps"][0]["report"]["execution"] is None
        assert owner.qualification_view()["reconnect"] is None
        owner.validate_publication(result)
        setup.publication_completed("MODELED-reconnect-completion")
        owner.publication_completed("MODELED-reconnect-completion")
        for text in render_snapshot(snapshot(owner, complete_setup)):
            assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
    phase = owner.qualification_view()["reconnect"]
    assert phase["state"] == "REVIEWED"
    assert owner.qualification_view()["next_action"] == reconnect.BOOT_COLLECT
    originals = owner.retained_diagnostics()["qualification_reconnect"]
    assert (
        originals["operation"]["document"]
        == originals["preparation"]["document"]["operation"]
    )
    assert len(originals["events"][-1]["evidence"]) == 8
    assert all(
        originals[k] is None
        for k in ("host_boot", "execution", "phase_record", "original_campaign")
    )
