"""Real Setup/USB owner action composition over MODELED storage and metadata.

Begin, acquisition routing, Prepare and Review run their production methods and
original codecs. Storage leases/publication and file observations are models;
this does not claim public NTFS durability or received hardware qualification.
"""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event
import time

from rocell.application import physical_usb_identity_service as service
from rocell.application import physical_usb_reboot_service as reboot
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from test_physical_camera_usb_reboot_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    no_devices,
    complete_v12,
)
from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_usb_absence_readback import change_last_event
from test_physical_usb_identity_service import modeled_files
from test_usb_reconnect_service_composed import fresh_owners
from test_wizard_usb_absence_ui import adopt


NEW_LAUNCH = "wizard-" + "e" * 32


def test_actual_new_launch_begin_metadata_prepare_review(
    ready, setup_flow, monkeypatch
):
    prior = complete_v12(ready, monkeypatch)
    setup, _, state = setup_flow
    setup.launch_id = NEW_LAUNCH
    owner = adopt(setup, prior.original)
    native, helper = fresh_owners(owner)
    state["now"] = time.monotonic_ns()
    monkeypatch.setattr(service, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(service, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(reboot, "inspect_usb_identity_runtime", modeled_files)
    monkeypatch.setattr(
        reboot,
        "inspect_usb_identity_stage_policy",
        lambda _: usb_identity_stage_policy(),
    )
    last = [max(time.time_ns(), prior.now)]

    def ordered_utc():
        last[0] += 1_000
        return last[0]

    monkeypatch.setattr(reboot, "time_ns", ordered_utc)
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
    preserved = dict(state["payloads"])

    def action(action_id, values):
        assert (
            owner.blocked_reason(action_id, native_camera=native, helper=helper) is None
        )
        result = owner.perform(
            action_id,
            values,
            native_camera=native,
            helper=helper,
            expected_context_sha256=owner.context_sha256(
                native_camera=native, helper=helper
            ),
            cancellation=Event(),
            progress=lambda _: None,
        )
        ArrivalWizardService._validate_usb_identity_result(action_id, result)
        report = result["steps"][0]["report"]
        assert report["usb_query_attempted"] is False and report["execution"] is None
        assert owner.qualification_view()["reboot"] is None  # Still unpublished.
        assert owner._reboot.predecessor is not None  # History survives PENDING.
        assert all(
            owner.blocked_reason(a, native_camera=native, helper=helper)
            for a in reboot.ACTIONS
        )  # History is not action permission.
        owner.validate_publication(result)
        setup.publication_completed("MODELED-reboot-completion-" + action_id)
        owner.publication_completed("MODELED-reboot-completion-" + action_id)
        assert preserved.items() <= state["payloads"].items()

    action(
        reboot.BEGIN,
        dict(
            operator_id="MODELED reboot operator",
            file_only=True,
            confirm_host_restarted=True,
        ),
    )
    assert owner.qualification_view()["reboot"]["state"] == "PREPARATION_REQUESTED"
    raw = native.export_snapshot()
    for action_id, operation_id, document in (
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
    ):
        token = owner.acquisition_started(action_id, operation_id, ordered_utc())
        owner.acquisition_published(
            token,
            finished_at_ns=ordered_utc(),
            document=document,
            result_sha256=digest(
                canonical({"MODELED_COMPLETED_LOG_RESULT": operation_id})
            ),
        )
    ledger = deepcopy(owner._reboot.ledger)
    assert len(ledger["entries"]) == 3
    owner.invalidate()
    assert owner.qualification_view()["next_action"] == "physical_camera_refresh"
    # Explicit successful Refresh publication is modeled; do not silently renew
    # the interval or manufacture new acquisition IDs while adopting originals.
    setup._publication = dict(status="CURRENT", operation_id="MODELED-refresh-log")
    owner.observe_setup()
    assert owner._reboot.ledger == ledger
    action(reboot.PREPARE, dict(operator_id="MODELED reboot operator", file_only=True))
    action(
        reboot.REVIEW,
        dict(
            reviewer_id="MODELED independent reviewer",
            confirm_policy_review=True,
            confirm_runtime_review=True,
            confirm_exact_target=True,
            confirm_boot_metadata=True,
        ),
    )
    phase = owner.qualification_view()["reboot"]
    assert phase["state"] == "REVIEWED"
    assert owner.qualification_view()["next_action"] == reboot.BOOT_COLLECT
    current = owner.retained_diagnostics()["qualification_reboot"]
    assert (
        current["operation"]["document"]
        == current["preparation"]["document"]["operation"]
    )
    assert len(current["events"][-1]["evidence"]) == 8
    assert all(
        current[role] is None
        for role in ("host_boot", "execution", "phase_record", "original_campaign")
    )
