"""Exact outer storage deadlines; all storage/clock callbacks are modeled.

No original M1, process, boot metadata or device is acquired. These tests isolate
the actual Setup scope guard and service deadline forwarding; separate actual
public tests exercise the original store and independent inner admissions.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import Event, Lock, RLock
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application import physical_usb_trial_service as phase_module
from rocell.application.wizard_actions import WizardError


SECOND = 1_000_000_000
START = 100 * SECOND
LEGACY_SCOPES = (
    "intake_transaction",
    "qualification_transaction",
    "received_camera_transaction",
    "identity_transaction",
    "usb_identity_transaction",
    "usb_qualification_transaction",
    "static_contract_transaction",
    "_source_transaction",
)


def scope(owner, name, cancellation, deadline):
    kwargs = dict(
        cancellation=cancellation, progress=lambda _: None, deadline_ns=deadline
    )
    if name == "_source_transaction":
        kwargs["qualification"] = False
    return getattr(owner, name)(**kwargs)


class BusyProbe:
    def __init__(self):
        self.calls = 0

    def acquire(self, *, blocking):
        assert blocking is False
        self.calls += 1
        return False


@pytest.mark.parametrize("name", (*LEGACY_SCOPES, "usb_phase_transaction"))
@pytest.mark.parametrize(
    "delta", [1, 120 * SECOND, 120 * SECOND + 1, 180 * SECOND, 180 * SECOND + 1]
)
def test_only_explicit_usb_phase_scope_has_180_second_hard_ceiling(
    monkeypatch, name, delta
):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: START)
    cap = (180 if name == "usb_phase_transaction" else 120) * SECOND
    with pytest.raises(WizardError) as caught:
        with scope(owner, name, Event(), START + delta):
            pytest.fail("Busy probe must not enter a storage body")
    assert caught.value.code == (
        "CAMERA_SETUP_BUSY" if delta <= cap else "INTAKE_STORAGE_CONTEXT_INVALID"
    )
    assert probe.calls == int(delta <= cap)


@pytest.mark.parametrize(
    "deadline", [None, True, START, START - 1, float(START + SECOND)]
)
def test_usb_phase_rejects_expired_or_non_integer_deadlines_before_lock(
    monkeypatch, deadline
):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError) as caught:
        with scope(owner, "usb_phase_transaction", Event(), deadline):
            pytest.fail("Invalid deadline entered a storage body")
    assert caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID" and probe.calls == 0


@pytest.mark.parametrize(
    "other",
    [
        "qualification",
        "static_contract",
        "received_camera",
        "camera_identity",
        "usb_identity",
        "usb_trial",
    ],
)
def test_mixed_private_scope_flags_cannot_extend_a_legacy_deadline(monkeypatch, other):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: START)
    options = dict(qualification=False, usb_phase=True)
    options[other] = True
    with pytest.raises(WizardError) as caught:
        with owner._source_transaction(
            cancellation=Event(),
            progress=lambda _: None,
            deadline_ns=START + 121 * SECOND,
            **options,
        ):
            pytest.fail("Mixed scope bypassed legacy cap")
    assert caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID" and probe.calls == 0


@pytest.fixture
def modeled_scope(monkeypatch):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    clock, calls = [START], []
    cancellation = Event()
    binding = {"session_id": "modeled-original"}
    verification = dict(
        effects_allowed_by_m1_storage=True,
        session=dict(header_sha256="h", head_sha256="j", evidence_inventory_sha256="e"),
    )
    workflow = dict(
        schema="rocell.physical_camera_source_workflow_readback.v9",
        binding=binding,
        session_header_sha256="h",
        session_head_sha256="j",
        evidence_inventory_sha256="e",
        state="PASS",
        prerequisites={},
        receipt={},
        assessment={},
        review={},
        static_contract={"state": "REVIEWED_PASS"},
        received_camera_cycles=[{"state": "REVIEWED_PASS"}],
        camera_identity_request={},
        camera_identity_cycles=[{"state": "REVIEWED_BLOCKED"}],
        usb_qualification_trial={"state": "PLAN_DECLARED"},
        configuration_epochs={},
    )
    owner.workspace, owner.source_sha256, owner.mode = (
        Path("MODELED_NO_IO"),
        "a" * 64,
        "physical",
    )
    owner._lock, owner._operation_lock = RLock(), Lock()
    owner._publication, owner._source_workflow = {
        "status": "CURRENT",
        "operation_id": None,
    }, workflow
    owner.session = SimpleNamespace(
        descriptor=lambda: deepcopy(binding),
        view=lambda: dict(
            verification=deepcopy(verification), stages=[{"state": "PASS"}]
        ),
    )
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: clock[0])
    monkeypatch.setattr(setup_impl, "source_fingerprint", lambda _: owner.source_sha256)
    owner._source_artifacts = lambda _: (object(), {"review": object()})
    owner.invalidate = lambda: owner._publication.update(status="HISTORICAL_HELD")
    owner._adopt_source_workflow = lambda value: calls.append(
        ("adopt", deepcopy(value))
    )
    owner.session.refresh = lambda **kwargs: calls.append(("refresh", kwargs))
    owner.session.read_original_source_workflow = lambda **kwargs: (
        calls.append(("read", kwargs)) or deepcopy(workflow)
    )
    return SimpleNamespace(
        owner=owner,
        clock=clock,
        calls=calls,
        cancellation=cancellation,
        workflow=workflow,
    )


def test_original_180_second_deadline_survives_post_120_second_body_and_readback(
    modeled_scope,
):
    c = modeled_scope
    original_deadline = START + 180 * SECOND
    with scope(c.owner, "usb_phase_transaction", c.cancellation, original_deadline):
        assert c.owner._publication["status"] == "HISTORICAL_HELD"
        c.clock[0] = START + 121 * SECOND
    assert c.owner._publication["status"] == "PENDING"
    assert [x[0] for x in c.calls] == ["refresh", "read", "adopt"]
    assert c.calls[1][1]["deadline_ns"] == original_deadline
    assert not c.owner._operation_lock.locked()


def test_precancelled_usb_phase_never_enters_storage_body(modeled_scope):
    c = modeled_scope
    c.cancellation.set()
    with pytest.raises(WizardError) as caught:
        with scope(
            c.owner, "usb_phase_transaction", c.cancellation, START + 180 * SECOND
        ):
            pytest.fail("Cancelled scope entered its body")
    assert caught.value.code == "INTAKE_STORAGE_INTERRUPTED"
    assert not c.calls and not c.owner._operation_lock.locked()


@pytest.mark.parametrize("moment", ["body", "refresh", "readback"])
@pytest.mark.parametrize("fault", ["cancel", "deadline"])
def test_cancel_or_original_deadline_at_each_late_boundary_never_publishes_current(
    modeled_scope, moment, fault
):
    c = modeled_scope
    deadline = START + 180 * SECOND

    def interrupt():
        if fault == "cancel":
            c.cancellation.set()
        else:
            c.clock[0] = deadline

    if moment != "body":
        name = "refresh" if moment == "refresh" else "read_original_source_workflow"
        original = getattr(c.owner.session, name)

        def wrapped(**kwargs):
            result = original(**kwargs)
            interrupt()
            return result

        setattr(c.owner.session, name, wrapped)
    with pytest.raises(WizardError) as caught:
        with scope(c.owner, "usb_phase_transaction", c.cancellation, deadline):
            c.clock[0] = START + 121 * SECOND
            if moment == "body":
                interrupt()
    assert caught.value.code == "INTAKE_STORAGE_INTERRUPTED"
    assert c.owner._publication["status"] == "HISTORICAL_HELD"
    assert not c.owner._operation_lock.locked()
    assert all(row[1]["deadline_ns"] == deadline for row in c.calls if row[0] == "read")


@pytest.mark.parametrize("seconds", [120, 180])
def test_phase_service_forwards_original_action_deadline_without_a_new_window(
    monkeypatch, seconds
):
    marker = RuntimeError("MODELED_SCOPE_ENTRY_ONLY")
    observed = []

    @contextmanager
    def storage(**kwargs):
        observed.append(kwargs["deadline_ns"])
        raise marker
        yield  # pragma: no cover - this test never enters original storage.

    setup = SimpleNamespace(
        session=SimpleNamespace(descriptor=lambda: {}),
        original_source_workflow=lambda: {
            "usb_qualification_trial": {"plan": {"document": {}}}
        },
        usb_phase_transaction=storage,
        invalidate=lambda: None,
    )
    owner = SimpleNamespace(
        setup=setup,
        _lock=RLock(),
        _attempted=set(),
        _generation=0,
        _attempt_key=lambda *args: "modeled-action-key",
        invalidate=lambda: None,
    )
    monkeypatch.setattr(phase_module, "UsbQualificationPlan", lambda _: object())
    trial = phase_module._UsbTrialBaseline(owner)
    deadline = START + seconds * SECOND
    with pytest.raises(RuntimeError) as caught:
        trial.perform(
            phase_module.PHASE_COLLECT if seconds == 180 else phase_module.BEGIN,
            {},
            cancellation=Event(),
            progress=lambda _: None,
            deadline=deadline,
            native_camera=None,
            helper=None,
        )
    assert caught.value is marker and observed == [deadline]
