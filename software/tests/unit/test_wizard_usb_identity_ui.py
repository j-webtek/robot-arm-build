"""Real renderers, explicitly modeled cached USB data; no device or process query.

Node only runs the app's finite fake DOM. Terminal uses cached GET only.
Actual service/codec joins are exercised separately when the producer is ready.
"""

from copy import deepcopy

import pytest

from rocell.ui.terminal import _UsbIdentityDisplay
from test_arrival_wizard_device_selection_ui import MetadataService, selection
from test_wizard_physical_camera_setup_ui import complete_setup, prerequisite_summary
from test_wizard_physical_camera_restart_ui import version_two
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered
from test_arrival_wizard_service import make_service


def modeled_view(complete_setup, *, state="observed"):
    setup = version_two(complete_setup)
    for index, row in enumerate(setup["session"]["stages"]):
        row["state"] = "PASS" if index < 3 else "BLOCKED" if index == 3 else "PENDING"
    b, q = setup["session"]["binding"], setup["session"]["verification"]
    source, launch = setup["source_sha256"], setup["launch_session_id"]
    view = MetadataService(selection()).view()
    view.update(
        mode="physical",
        session_id=launch,
        source_binding_sha256=source,
        physical_camera_setup=setup,
    )
    inspection = dict(
        evidence_sha256="1" * 64,
        operator_id="query_operator",
        collection_launch_id=launch,
        policy_sha256="2" * 64,
        operation_sha256="3" * 64,
        runtime_registration_sha256="4" * 64,
        helper_sha256="5" * 64,
        files_verified=20,
        target=dict(
            selection_sha256="6" * 64,
            native_identity_sha256="7" * 64,
            endpoint_sha256="8" * 64,
            symbolic_link="MODELED_endpoint_with_underscores",
            device_instance_id="MODELED_instance_with_underscores",
        ),
    )
    review = dict(
        policy_review_sha256="a" * 64,
        runtime_review_sha256="b" * 64,
        identity_sha256="c" * 64,
        reviewer_id="query_reviewer",
        review_launch_id=launch,
    )
    counts = dict(
        api_calls=13,
        hub_open_attempts=1,
        hub_open_successes=1,
        ioctl_attempts=11,
        ioctl_successes=11,
        descriptor_requests=3,
        close_attempts=1,
        close_successes=1,
        peak_open_handles=1,
        remaining_open_handles=0,
        returned_bytes=2048,
    )
    execution = dict(
        schema="rocell.owned_usb_identity_run_summary.v1",
        evidence_sha256="d" * 64,
        preparation_sha256="e" * 64,
        status="OBSERVED",
        provenance="INCAPABLE_USB_QUERY",
        released=True,
        no_attempt=False,
        counter_coverage="NATIVE_RECEIPT",
        actual_counts=counts,
        process_cleanup_confirmed=True,
        usb_cleanup_confirmed=True,
        error=None,
        cleanup_errors=[],
        physical_authority=False,
        hardware_qualified=False,
        retries=0,
    )
    observation = dict(
        outcome="OBSERVED",
        serial_values=["MODELED_serial_001"],
        vid="1234",
        pid="5678",
        bcd_usb=768,
        i_serial_number=3,
        physical_usb_instance_id="MODELED_USB_instance",
        host_controller_instance_id="MODELED_host_controller",
        hub_port=1,
        ex_speed=2,
        ex_v2_available=True,
        operating_at_superspeed=True,
        operating_at_superspeed_plus=False,
    )
    card = dict(
        schema="rocell.wizard_usb_identity.v1",
        source_sha256=source,
        launch_session_id=launch,
        original_context=dict(
            source_sha256=source,
            session_id=b["session_id"],
            cell_id=b["cell_id"],
            origin_launch_id=b["launch_id"],
            header_sha256=q["session"]["header_sha256"],
            prerequisites_sha256=setup["prerequisites"]["evidence_sha256"],
        ),
        publication=dict(status="CURRENT", operation_id="operation-modeled-usb"),
        status="OBSERVED_UNQUALIFIED",
        stage_states={
            row["stage"]: row["state"] for row in setup["session"]["stages"][:4]
        },
        usb_id="usbidentity-" + "1" * 32,
        inspection=inspection,
        review=review,
        execution=execution,
        observation=observation,
        next_action=None,
        export_receipt=None,
        physical_authority=False,
        hardware_qualified=False,
        camera_capture_authorized=False,
        arm_access_authorized=False,
        meaning="One original USB baseline query; not reconnect/reboot qualification, camera capture or arm authority.",
    )
    if state == "ready":
        card.update(
            status="READY_TO_QUERY",
            execution=None,
            observation=None,
            next_action="physical_usb_identity_collect",
        )
        card["stage_states"]["camera_identity"] = setup["session"]["stages"][3][
            "state"
        ] = "WAITING_OPERATOR"
    elif state == "unknown":
        execution.update(
            status="CLEANUP_UNCERTAIN",
            counter_coverage="NOT_REPORTED",
            actual_counts=None,
            usb_cleanup_confirmed=False,
            error="USB_RESULT_UNAVAILABLE",
        )
        card.update(status="HELD", observation=None)
    elif state == "no_attempt":
        execution.update(
            status="CANCELLED",
            counter_coverage="NO_PROCESS_CREATED",
            no_attempt=True,
            released=False,
            usb_cleanup_confirmed=False,
            error="CANCELLED",
            actual_counts=dict.fromkeys(counts, 0),
        )
        card.update(status="HELD", observation=None)
    view["usb_identity"] = card
    view["actions"] = [
        offered("physical_usb_identity_collect", enabled=state == "ready"),
        offered("physical_usb_identity_export"),
    ]
    return view


@pytest.mark.parametrize("state", ["observed", "ready", "unknown", "no_attempt"])
def test_cached_original_values_counts_and_cleanup_are_truthful(complete_setup, state):
    view = modeled_view(complete_setup, state=state)
    assert (
        _UsbIdentityDisplay.validate(view["usb_identity"], view) == view["usb_identity"]
    )
    before = deepcopy(view)
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert "query_operator" in text and "MODELED_endpoint_with_underscores" in text
        assert "not reconnect/reboot qualification" in text
        assert "new app launch is not a reboot" in text
        if state == "observed":
            assert "MODELED_serial_001" in text and "INCAPABLE / MODELED" in text
        elif state == "unknown":
            assert "NOT REPORTED / UNKNOWN" in text
            assert "Do not retry or assume the device is closed" in text
        elif state == "no_attempt":
            assert "restarting the app does not renew its budget" in text
    assert view == before


def test_current_next_step_navigation_uses_actual_eligibility_only(complete_setup):
    view = modeled_view(complete_setup, state="ready")
    page = render(view, "physical_usb_identity_collect")
    assert page["navigations"] == ["camera-action-physical_usb_identity_collect"]
    assert page["links"][0]["href"] == "#camera-action-physical_usb_identity_collect"
    view["actions"][0]["enabled"] = False
    assert not any(
        row["id"] == "physical_usb_identity_collect" for row in render(view)["links"]
    )


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_pending_withholds_original_values_and_history_does_not_rebind(
    complete_setup, publication
):
    view = modeled_view(complete_setup)
    card = view["usb_identity"]
    card.update(status="HISTORICAL_HELD", next_action=None)
    card["publication"] = dict(status=publication, operation_id=None)
    if publication == "PENDING":
        card.update(inspection=None, review=None, execution=None, observation=None)
    else:
        view["source_binding_sha256"] = "f" * 64
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert (
            "USB publication pending" if publication == "PENDING" else "HISTORICAL ONLY"
        ) in text
        if publication == "PENDING":
            assert "MODELED_serial_001" not in text


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(physical_authority=True),
        lambda c: c.update(camera_capture_authorized=True),
        lambda c: c.update(source_sha256="f" * 64),
        lambda c: c["original_context"].update(header_sha256="f" * 64),
        lambda c: c["execution"].update(actual_counts=None),
        lambda c: c["execution"].update(no_attempt=True),
        lambda c: c["execution"].update(usb_cleanup_confirmed=False),
        lambda c: c["execution"]["actual_counts"].update(hub_open_attempts=True),
        lambda c: c["execution"]["actual_counts"].update(hub_open_attempts=33),
        lambda c: c["execution"].update(retries=1),
        lambda c: c["observation"].update(ex_v2_available=False),
        lambda c: c["observation"].update(speed_mbps=5000),
        lambda c: c["observation"].update(serial_values=["x"] * 5),
        lambda c: c.update(review=None),
        lambda c: c["review"].update(reviewer_id="query_operator"),
        lambda c: c["inspection"].update(files_verified=21),
    ],
)
def test_malformed_projection_is_withheld_in_both_renderers(complete_setup, change):
    view = modeled_view(complete_setup)
    change(view["usb_identity"])
    assert _UsbIdentityDisplay.validate(view["usb_identity"], view) is None
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" in text
        assert "MODELED_serial_001" not in text


def test_legacy_export_without_usb_wrapper_still_renders(complete_setup):
    view = modeled_view(complete_setup)
    del view["usb_identity"]
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text


def test_actual_standard_export_receipt_and_general_pointer_render(
    complete_setup, tmp_path
):
    from pathlib import Path
    from threading import Event
    from time import monotonic_ns
    from types import SimpleNamespace
    from rocell.application.arrival_wizard_service import ArrivalWizardService
    from rocell.application.physical_usb_identity_export import (
        export_usb_identity_diagnostics,
    )
    from rocell.application.wizard_diagnostic_export import verify_export
    from test_physical_usb_identity_export import diagnostics

    view = modeled_view(complete_setup)
    card = view["usb_identity"]
    original = diagnostics()
    original.update(
        source_sha256=card["source_sha256"], launch_session_id=card["launch_session_id"]
    )
    receipt = export_usb_identity_diagnostics(
        original,
        export_parent=tmp_path / "exports",
        source_sha256=card["source_sha256"],
        launch_id=card["launch_session_id"],
        cancellation=Event(),
        deadline_ns=monotonic_ns() + 60_000_000_000,
    )
    assert verify_export(Path(receipt["path"]))["valid"]
    card["export_receipt"] = receipt
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert receipt["manifest_sha256"] in text
    view["usb_identity"] = ArrivalWizardService._usb_identity_export_pointer(
        SimpleNamespace(_usb_identity_view=lambda: deepcopy(card))
    )
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert "General export coverage only" in text
        assert "MODELED_serial_001" in text


def test_actual_fresh_arrival_service_projection_and_explicit_forms_are_inert(
    make_service, monkeypatch
):
    from rocell.application import physical_usb_identity_service as usb

    service, runner, _ = make_service(mode="physical")
    monkeypatch.setattr(
        usb,
        "inspect_usb_identity_runtime",
        lambda *a, **kw: pytest.fail("file inspection from view"),
    )
    monkeypatch.setattr(
        usb,
        "PhysicalUsbIdentityDispatchOwner",
        lambda *a, **kw: pytest.fail("dispatcher from view"),
    )
    view = service.view()
    assert view["usb_identity"]["status"] == "NOT_STARTED"
    assert (
        _UsbIdentityDisplay.validate(view["usb_identity"], view) == view["usb_identity"]
    )
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
    catalog = {a["action_id"]: a for a in view["actions"]}
    for action in usb.ACTIONS:
        assert catalog[action]["fields"] == list(service._usb_identity.fields(action))
        assert all(
            f.get("default") is False
            for f in catalog[action]["fields"]
            if f["type"] == "checkbox"
        )
    assert not runner.calls


def test_actual_no_process_owned_evidence_summary_renders_without_device_queries(
    complete_setup, monkeypatch
):
    from rocell.application.physical_usb_identity_service import _observation
    from rocell.providers.windows import owned_usb_identity_runner as module
    from test_owned_usb_identity_runner import usb_fixture, run_case

    view = modeled_view(complete_setup, state="no_attempt")
    card = view["usb_identity"]
    case = usb_fixture(source_sha256=card["source_sha256"], fail_at=1)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: card["source_sha256"])
    monkeypatch.setattr(
        module, "_new_owner", lambda: pytest.fail("owner after refused scope")
    )
    _, evidence = run_case(case)
    assert evidence.no_attempt
    card.update(execution=evidence.safe_summary(), observation=_observation(evidence))
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert "INCAPABLE / MODELED" in text


def test_usb_printable_ascii_labels_preserve_spaces_and_reject_casefold_same(
    complete_setup,
):
    view = modeled_view(complete_setup)
    view["usb_identity"]["inspection"]["operator_id"] = "Actual operator label"
    view["usb_identity"]["review"]["reviewer_id"] = "Other reviewer label"
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert "Actual operator label" in text and "Other reviewer label" in text
    view["usb_identity"]["review"]["reviewer_id"] = "ACTUAL OPERATOR LABEL"
    for text in render_snapshot(view):
        assert "USB_IDENTITY_NOT_VERIFIED" in text
