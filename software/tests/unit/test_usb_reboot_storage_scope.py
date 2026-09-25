"""Actual Setup gates over explicitly MODELED typed-reader/adapter boundaries.

No original M1, lease, process, CIM or device operation is performed. Typed
received constructors and predecessor authentication are modeled here to isolate
Setup state/deadline/publication logic; full original codecs have separate tests.
"""

from copy import deepcopy
from threading import Event

import pytest

from rocell.application import physical_camera_setup_service as setup
from rocell.application import physical_camera_usb_reboot as reboot
from rocell.application import physical_camera_usb_reconnect as reconnect
from rocell.application import physical_received_camera_submission as received
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.usb_identity_protocol import canonical
from test_usb_phase_storage_deadline import (
    BusyProbe,
    modeled_scope,
    scope,
    START,
    SECOND,
)

NEW_LAUNCH = "wizard-" + "1" * 32
OLD_LAUNCH = "wizard-" + "2" * 32
V12 = "rocell.physical_camera_source_workflow_readback.v12"
V13 = "rocell.physical_camera_source_workflow_readback.v13"
OTHER_SCOPES = (
    "qualification",
    "static_contract",
    "received_camera",
    "camera_identity",
    "usb_identity",
    "usb_trial",
    "usb_phase",
    "usb_absence",
    "usb_reconnect",
)


@pytest.mark.parametrize(
    "delta", [1, 120 * SECOND, 120 * SECOND + 1, 180 * SECOND, 180 * SECOND + 1]
)
def test_reboot_retains_unchanged_180_second_outer_ceiling(monkeypatch, delta):
    owner = object.__new__(setup.PhysicalCameraSetupService)
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError) as caught:
        with scope(owner, "usb_reboot_transaction", Event(), START + delta):
            pytest.fail("Busy scope entered")
    assert caught.value.code == (
        "CAMERA_SETUP_BUSY"
        if delta <= 180 * SECOND
        else "INTAKE_STORAGE_CONTEXT_INVALID"
    )
    assert probe.calls == int(delta <= 180 * SECOND)


@pytest.mark.parametrize(
    "deadline", [None, True, False, START, START - 1, float(START + SECOND)]
)
def test_deadline_wrong_types_or_expiry_refuse_before_lock(monkeypatch, deadline):
    owner = object.__new__(setup.PhysicalCameraSetupService)
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError) as caught:
        with scope(owner, "usb_reboot_transaction", Event(), deadline):
            pytest.fail("Invalid deadline entered")
    assert caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID" and probe.calls == 0


@pytest.mark.parametrize("other", OTHER_SCOPES)
@pytest.mark.parametrize("value", [True, 0, None, ""])
def test_every_other_authority_is_exactly_false_for_new_reboot(
    monkeypatch, other, value
):
    owner = object.__new__(setup.PhysicalCameraSetupService)
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup, "monotonic_ns", lambda: START)
    options = dict(qualification=False, usb_reboot=True)
    options[other] = value
    with pytest.raises(WizardError) as caught:
        with owner._source_transaction(
            cancellation=Event(),
            progress=lambda _: None,
            deadline_ns=START + SECOND,
            **options
        ):
            pytest.fail("Mixed or falsey-untyped authority entered")
    assert caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID" and probe.calls == 0


@pytest.mark.parametrize("value", [0, 1, None, "", "True"])
def test_new_authority_flag_itself_is_exact_bool(monkeypatch, value):
    owner = object.__new__(setup.PhysicalCameraSetupService)
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError) as caught:
        with owner._source_transaction(
            cancellation=Event(),
            progress=lambda _: None,
            deadline_ns=START + SECOND,
            qualification=False,
            usb_reboot=value,
        ):
            pytest.fail("Untyped reboot authority entered")
    assert caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID" and probe.calls == 0


def configure(c, monkeypatch, *, schema=V13, state="PREPARED"):
    c.owner.launch_id = NEW_LAUNCH
    c.workflow["schema"] = schema
    row = c.workflow["received_camera_cycles"][-1]
    c.typed_reads, c.adapter_calls, c.adapter_error = [], [], None
    classes = {}
    for role, name in (
        ("submission", "ReceivedCameraSubmission"),
        ("assessment", "ReceivedCameraSubmissionAssessment"),
        ("review", "ReceivedCameraSubmissionReview"),
    ):
        row[role] = {"document": {"MODELED_RECEIVED_ROLE": role}}

        def initializer(self, payload, prerequisites, *, role=role):
            assert payload == canonical(row[role]["document"])
            self.payload, self.prerequisites = payload, prerequisites
            c.typed_reads.append(role)

        cls = type("Modeled" + name, (), {"__init__": initializer})
        classes[role] = cls
        monkeypatch.setattr(received, name, cls)

    def adapter(workflow, *, received, version):
        c.adapter_calls.append(version)
        assert workflow["schema"] == version
        assert set(received) == set(classes)
        assert all(type(received[role]) is cls for role, cls in classes.items())
        if c.adapter_error:
            raise ValueError(c.adapter_error)
        return {"MODELED_AUTHENTICATED_PREDECESSOR": True}

    monkeypatch.setattr(
        reboot,
        "original_usb_reboot_predecessor",
        lambda workflow, *, received: adapter(workflow, received=received, version=V12),
    )
    monkeypatch.setattr(
        reboot,
        "original_usb_reboot_predecessor_v13",
        lambda workflow, *, received: adapter(workflow, received=received, version=V13),
    )
    c.workflow["usb_qualification_reconnect"] = dict(
        state="RETAINED_BLOCKED",
        phase="AFTER_RECONNECT",
        operator_event={"document": {"launch_session_id": OLD_LAUNCH}},
    )
    phase = dict(
        state=state,
        phase="AFTER_REBOOT",
        original_campaign=None,
        original_campaign_event=None,
        operator_event={"document": {"launch_session_id": NEW_LAUNCH}},
    )
    if schema == V13:
        c.workflow["usb_qualification_reboot"] = phase
    else:
        c.workflow.pop("usb_qualification_reboot", None)
    return phase


def enter(c):
    return scope(
        c.owner, "usb_reboot_transaction", c.cancellation, START + 180 * SECOND
    )


def refused(c, code="USB_REBOOT_ORIGINAL_REQUIRED"):
    with pytest.raises(WizardError) as caught:
        with enter(c):
            pytest.fail("Ineligible original entered")
    assert caught.value.code == code and not c.calls
    assert not c.owner._operation_lock.locked()


def test_v12_complete_historical_predecessor_is_only_new_launch_begin(
    modeled_scope, monkeypatch
):
    c = modeled_scope
    configure(c, monkeypatch, schema=V12)
    original = deepcopy(c.workflow)
    with enter(c):
        assert c.owner._publication["status"] == "HISTORICAL_HELD"
        c.clock[0] = START + 121 * SECOND
    assert c.adapter_calls == [V12] and c.typed_reads == [
        "submission",
        "assessment",
        "review",
    ]
    assert c.workflow == original  # Earlier reconnect was not migrated to new launch.
    assert [row[0] for row in c.calls] == ["refresh", "read", "adopt"]
    assert c.calls[1][1]["deadline_ns"] == START + 180 * SECOND
    assert c.owner._publication["status"] == "PENDING"


@pytest.mark.parametrize(
    "fault", ["same_launch", "reboot_already_present", "incomplete_predecessor"]
)
def test_v12_begin_denies_same_launch_or_failed_independent_adapter(
    modeled_scope, monkeypatch, fault
):
    c = modeled_scope
    configure(c, monkeypatch, schema=V12)
    if fault == "same_launch":
        c.workflow["usb_qualification_reconnect"]["operator_event"]["document"][
            "launch_session_id"
        ] = NEW_LAUNCH
    elif fault == "reboot_already_present":
        c.workflow["usb_qualification_reboot"] = {}
    else:
        c.adapter_error = "MODELED incomplete or nonclean reconnect original"
    refused(c)
    assert c.adapter_calls == [V12]


@pytest.mark.parametrize(
    "state,allowed",
    [
        ("PREPARATION_REQUESTED", True),
        ("PREPARED", True),
        ("REVIEWED", True),
        ("BOOT_RETAINED", True),
        ("BOOT_REQUESTED", False),
        ("BOOT_HELD", False),
        ("BOOT_UNCERTAIN", False),
        ("QUERY_REQUESTED", False),
        ("RETAINED_BLOCKED", False),
        ("INCOMPLETE", False),
        ("ORIGINAL_CAMPAIGN_HELD", False),
    ],
)
def test_v13_only_exact_unused_current_boundaries_enter(
    modeled_scope, monkeypatch, state, allowed
):
    c = modeled_scope
    configure(c, monkeypatch, state=state)
    if allowed:
        with enter(c):
            c.clock[0] = START + 121 * SECOND
        assert c.owner._publication["status"] == "PENDING"
        assert [row[0] for row in c.calls] == ["refresh", "read", "adopt"]
        assert c.calls[1][1]["deadline_ns"] == START + 180 * SECOND
    else:
        refused(c)
    assert c.adapter_calls == [V13]


@pytest.mark.parametrize(
    "fault",
    [
        "old_launch",
        "missing_report",
        "missing_report_document",
        "attempt",
        "attempt_event",
        "adapter_failure",
    ],
)
def test_v13_reopen_report_and_original_attempt_guards(
    modeled_scope, monkeypatch, fault
):
    c = modeled_scope
    phase = configure(c, monkeypatch)
    if fault == "old_launch":
        phase["operator_event"]["document"]["launch_session_id"] = OLD_LAUNCH
    if fault == "missing_report":
        phase["operator_event"] = None
    if fault == "missing_report_document":
        phase["operator_event"] = {}
    if fault == "attempt":
        phase["original_campaign"] = {}
    if fault == "attempt_event":
        phase["original_campaign_event"] = {}
    if fault == "adapter_failure":
        c.adapter_error = "MODELED original authentication failed"
    refused(c)
    assert c.adapter_calls == [V13]


@pytest.mark.parametrize("fault", ["source", "cancel", "deadline", "changed_session"])
@pytest.mark.parametrize("moment", ["before", "body", "readback"])
def test_source_stop_identity_and_original_deadline_never_publish_current(
    modeled_scope, monkeypatch, fault, moment
):
    c = modeled_scope
    configure(c, monkeypatch)

    def interrupt():
        if fault == "source":
            monkeypatch.setattr(setup, "source_fingerprint", lambda _: "b" * 64)
        elif fault == "cancel":
            c.cancellation.set()
        elif fault == "deadline":
            c.clock[0] = START + 180 * SECOND
        else:
            c.owner.session = object()

    if moment == "before":
        # The original identity token is captured on entry, so change its
        # descriptor through the existing object rather than replacing it here.
        if fault == "changed_session":
            c.owner.session.descriptor = lambda: {"session_id": "MODELED-other"}
        else:
            interrupt()
    elif moment == "readback":
        original = c.owner.session.read_original_source_workflow

        def read(**kwargs):
            result = original(**kwargs)
            interrupt()
            return result

        c.owner.session.read_original_source_workflow = read
    with pytest.raises(WizardError) as caught:
        with enter(c):
            if moment == "body":
                interrupt()
    expected = {
        "source": "CAMERA_SETUP_SOURCE_CHANGED",
        "cancel": "INTAKE_STORAGE_INTERRUPTED",
        "deadline": (
            "INTAKE_STORAGE_CONTEXT_INVALID"
            if moment == "before"
            else "INTAKE_STORAGE_INTERRUPTED"
        ),
        "changed_session": (
            "INTAKE_ORIGINAL_SOURCE_REVIEW_REQUIRED"
            if moment == "before"
            else "INTAKE_ORIGINAL_STORE_CHANGED"
        ),
    }[fault]
    assert caught.value.code == expected
    assert c.owner._publication["status"] != "PENDING"
    assert not c.owner._operation_lock.locked()
    assert all(
        row[1]["deadline_ns"] == START + 180 * SECOND
        for row in c.calls
        if row[0] == "read"
    )


@pytest.mark.parametrize(
    "schema",
    [
        V13,
        "rocell.physical_camera_source_workflow_readback.v11",
        "rocell.physical_camera_source_workflow_readback.v14",
    ],
)
def test_public_v12_data_adapters_do_not_accept_other_version_labels(schema):
    # Actual adapter version guards, with no patched codec or expensive fixture.
    workflow = {"schema": schema, "usb_qualification_reboot": {"phase": "AFTER_REBOOT"}}
    with pytest.raises(
        reboot.UsbRebootPreparationError, match="USB_REBOOT_PREDECESSOR_INVALID"
    ):
        reboot.original_usb_reboot_predecessor(workflow, received={})
    with pytest.raises(ValueError):
        reconnect.original_usb_reconnect_predecessor_v12(workflow)
