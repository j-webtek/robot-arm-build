"""Real public envelopes/routing with explicitly modeled cached subjects.

These are software-only contract tests, not authenticated original storage or
received hardware. No production helper, host observer or device call runs.
"""

from copy import deepcopy
from dataclasses import replace
from threading import RLock
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_reboot_service as reboot
from rocell.application.physical_usb_identity_service import PhysicalUsbIdentityService
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_actions import (
    ACTIONS,
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.providers.windows.usb_identity_protocol import canonical
from test_arrival_wizard_service import make_service, _ticket
from test_usb_observed_projection import forbid_native_execution


FORMS = {
    reboot.BEGIN: ("operator_id", "file_only", "confirm_host_restarted"),
    reboot.PREPARE: ("operator_id", "file_only"),
    reboot.REVIEW: (
        "reviewer_id",
        "confirm_policy_review",
        "confirm_runtime_review",
        "confirm_exact_target",
        "confirm_boot_metadata",
    ),
    reboot.BOOT_COLLECT: ("confirm_host_boot", "confirm_no_capture_or_arm"),
    reboot.COLLECT: ("confirm_usb_query", "confirm_no_capture_or_arm"),
}
TIMEOUTS = dict(zip(FORMS, (120, 180, 120, 180, 180)))


def definition(action):
    owner = object.__new__(PhysicalUsbIdentityService)
    owner._reboot = reboot._UsbTrialReboot(owner)
    return replace(ACTION_BY_ID[action], fields=owner.fields(action))


def values(action):
    return {
        field["name"]: True if field["type"] == "checkbox" else "MODELED label"
        for field in definition(action).fields
    }


@pytest.mark.parametrize("action", FORMS)
def test_closed_catalog_forms_and_false_defaults(action):
    item = definition(action)
    assert sum(a.action_id == action for a in ACTIONS) == 1
    assert item.mode == "physical" and item.worker == "physical_usb_identity"
    assert item.timeout_s == TIMEOUTS[action]
    assert tuple(f["name"] for f in item.fields) == FORMS[action]
    assert all(f["required"] is True for f in item.fields)
    for field in item.fields:
        if field["type"] == "checkbox":
            assert field["default"] is False
        else:
            assert field["default"] == "" and field["max_length"] == 64
    assert validate_action_input(item, values(action)) == values(action)
    assert not item.view(mode="rehearsal", busy=False)["enabled"]
    assert not item.view(mode="physical", busy=True)["enabled"]
    for extra in ("phase_id", "launch_id", "target", "permit", "argv", "deadline_ns"):
        with pytest.raises(WizardError):
            validate_action_input(item, dict(values(action), **{extra: "caller"}))


def boot_summary(state="BOOT_RETAINED", restart_status="BOOT_RETAINED"):
    return dict(
        schema="rocell.wizard_usb_reboot_boot_summary.v1",
        original_state=state,
        restart_status=restart_status,
        status="OBSERVED_HOST_BOOT",
        origin="MODELED_CONTRACT_ONLY",
        physical_authority=False,
        hardware_qualified=False,
        device_io_performed=False,
    )


def produced(action, coverage="NO_DEVICE_IO", opens=0, boot=None):
    owner = object.__new__(PhysicalUsbIdentityService)
    owner._baseline = owner._attempt = None
    owner._summaries = lambda: (None, None, None, None)
    owner._context = lambda: None
    owner.qualification_view = lambda: {
        "schema": "rocell.wizard_usb_qualification.v5",
        "reboot": None,
    }
    summary = dict(
        schema="rocell.owned_usb_identity_run_summary.v1",
        status="HELD",
        physical_authority=False,
        hardware_qualified=False,
        counter_coverage=coverage,
        actual_counts=None if opens is None else dict(hub_open_attempts=opens),
        no_attempt=coverage == "NO_PROCESS_CREATED",
    )
    evidence = SimpleNamespace(safe_summary=lambda: deepcopy(summary), observation=None)
    owner._reboot = SimpleNamespace(
        execution=lambda: evidence if action == reboot.COLLECT else None,
        boot_summary=lambda: deepcopy(boot),
        query_attempted=action == reboot.COLLECT,
    )
    result = owner._result(action)
    assert owner._pending_action == action
    assert owner._pending_result == canonical(result)
    assert owner._publication == dict(status="PENDING", operation_id=None)
    return owner, result


def validate(result):
    owner = object.__new__(ArrivalWizardService)
    return owner._validated_result(result["action_id"], result)


@pytest.mark.parametrize("action", tuple(FORMS)[:-1])
def test_real_file_and_boot_result_never_claims_usb(action):
    _, result = produced(action, boot=boot_summary())
    assert validate(result) == result
    report = result["steps"][0]["report"]
    assert report["meaning"] == reboot.MEANING
    assert report["qualification"]["schema"] == "rocell.wizard_usb_qualification.v5"
    assert report["usb_query_attempted"] is False and report["execution"] is None
    for key, bad in (("usb_query_attempted", True), ("execution", {})):
        changed = deepcopy(result)
        changed["steps"][0]["report"][key] = bad
        with pytest.raises(WizardError):
            validate(changed)
    for opens in (True, 1, None):
        changed = deepcopy(result)
        changed["device_open_count"] = opens
        with pytest.raises(WizardError):
            validate(changed)


@pytest.mark.parametrize("state", ("BOOT_RETAINED", "BOOT_HELD", "BOOT_UNCERTAIN"))
def test_original_boot_terminal_is_separate_from_restart_classifier(state):
    # A late Stop can retain clean source bytes but original BOOT_HELD. Never
    # turn that terminal into success or require relabeling source provenance.
    _, result = produced(reboot.BOOT_COLLECT, boot=boot_summary(state))
    assert validate(result) == result
    for key, bad in (
        ("original_state", "PASS"),
        ("restart_status", True),
        ("schema", "rocell.wizard_usb_reconnect_boot_summary.v1"),
        ("device_io_performed", True),
        ("physical_authority", True),
        ("hardware_qualified", True),
    ):
        changed = deepcopy(result)
        changed["steps"][0]["report"]["host_boot"][key] = bad
        with pytest.raises(WizardError):
            validate(changed)


@pytest.mark.parametrize(
    "coverage,opens",
    (
        ("NATIVE_RECEIPT", 3),
        ("NO_PROCESS_CREATED", 0),
        ("NOT_REPORTED", None),
    ),
)
def test_query_exact_literal_counts_and_no_fake_missing_artifact(coverage, opens):
    _, result = produced(reboot.COLLECT, coverage, opens)
    assert validate(result) == result
    assert result["device_open_count"] is opens
    for key, bad in (("execution", None), ("usb_query_attempted", False)):
        changed = deepcopy(result)
        changed["steps"][0]["report"][key] = bad
        with pytest.raises(WizardError):
            validate(changed)
    changed = deepcopy(result)
    changed["device_open_count"] = 0 if opens is None else None
    with pytest.raises(WizardError):
        validate(changed)
    if opens is not None:
        changed = deepcopy(result)
        changed["device_open_count"] = 1
        changed["steps"][0]["report"]["execution"]["actual_counts"][
            "hub_open_attempts"
        ] = True
        with pytest.raises(WizardError):
            validate(changed)


def test_exact_pending_query_publication_reaches_original_dispatch_only_after_log():
    owner, result = produced(reboot.COLLECT, "NOT_REPORTED", None)
    owner._lock = RLock()
    calls = []
    pending = {"MODELED_DISPATCH": "exact_original_unknown"}
    owner._dispatch_result = pending
    owner._dispatch = SimpleNamespace(
        validate_publication=lambda value: calls.append(("validate", value)),
        publication_completed=lambda op: calls.append(("complete", op)),
    )
    changed = deepcopy(result)
    changed["counter_coverage"] = "NO_PROCESS_CREATED"
    with pytest.raises(WizardError):
        owner.validate_publication(changed)
    assert not calls
    owner.validate_publication(result)
    assert calls == [("validate", pending)]
    assert owner._publication["status"] == "PENDING"
    owner.publication_completed("MODELED-durable-completion")
    assert calls[-1] == ("complete", "MODELED-durable-completion")
    assert owner._publication == dict(
        status="CURRENT", operation_id="MODELED-durable-completion"
    )


class Subject:
    def __init__(self, name):
        self.reboot = self.reconnect = self.attempt = None
        self.name, self.calls = name, []
        self.token = {"MODELED": name}

    def acquisition_started(self, *args):
        self.calls.append("start")
        return self.token

    def acquisition_published(self, *args, **kwargs):
        self.calls.append("publish")


def routed_owner():
    owner = object.__new__(PhysicalUsbIdentityService)
    owner._lock = RLock()
    owner._trial, owner._reconnect, owner._reboot = map(
        Subject, ("baseline", "reconnect", "reboot")
    )
    return owner


@pytest.mark.parametrize("kind", ("retained", "attempted"))
def test_reboot_is_exclusive_even_before_first_role_and_never_falls_back(kind):
    owner = routed_owner()
    owner._reconnect.reconnect = {"historical": True}
    setattr(owner._reboot, "reboot" if kind == "retained" else "attempt", {})
    routed = owner.acquisition_started("inventory_devices", "op", 1)
    assert routed == dict(phase="AFTER_REBOOT", token=owner._reboot.token)
    owner.acquisition_published(
        routed, finished_at_ns=2, document={}, result_sha256="a" * 64
    )
    assert owner._reboot.calls == ["start", "publish"]
    assert not owner._reconnect.calls and not owner._trial.calls
    owner._reboot.token = None
    assert owner.acquisition_started("inventory_devices", "op", 1) is None
    for wrong in (
        None,
        {},
        dict(phase="BASELINE", token={}),
        dict(phase="AFTER_RECONNECT", token={}),
        dict(phase="AFTER_REBOOT", token={}, extra=True),
    ):
        owner.acquisition_published(
            wrong, finished_at_ns=2, document={}, result_sha256="a" * 64
        )
    assert owner._reboot.calls == ["start", "publish", "start"]
    assert not owner._reconnect.calls and not owner._trial.calls


def test_token_issued_before_reboot_begin_cannot_publish_to_new_phase():
    owner = routed_owner()
    owner._reconnect.reconnect = {}
    token = owner.acquisition_started("inventory_devices", "op", 1)
    owner._reboot.attempt = {}
    owner.acquisition_published(
        token, finished_at_ns=2, document={}, result_sha256="a" * 64
    )
    assert owner._reconnect.calls == ["start"]
    assert not owner._reboot.calls and not owner._trial.calls


def test_startup_registers_all_actions_held_without_effects(make_service):
    for mode in ("physical", "rehearsal"):
        arrival, worker, _ = make_service(mode=mode)
        before = arrival.view()
        for action in FORMS:
            row = next(a for a in before["actions"] if a["action_id"] == action)
            assert not row["enabled"] and row["blocked_reasons"]
        assert not worker.calls
        assert arrival._usb_identity._reboot.reboot is None
        assert arrival._usb_identity._reboot.attempt is None
        assert arrival._usb_identity.retained_diagnostics() is None


@pytest.mark.parametrize("action", FORMS)
def test_exact_preview_is_file_or_explicit_bounded_effect(
    make_service, monkeypatch, action
):
    arrival, worker, _ = make_service(mode="physical")
    owner = arrival._usb_identity
    # Eligibility is deliberately modeled only for this inert ticket-text test.
    monkeypatch.setattr(owner, "blocked_reason", lambda *a, **k: None)
    monkeypatch.setattr(owner, "context_sha256", lambda **k: "c" * 64)
    original = owner.qualification_view
    monkeypatch.setattr(
        owner,
        "qualification_view",
        lambda: {
            **original(),
            "reboot": {"preparation": {"operator_id": "MODELED operator"}},
        },
    )
    ticket = _ticket(arrival, action, values(action))
    text = " ".join(ticket["effects"])
    if action in {reboot.BEGIN, reboot.PREPARE, reboot.REVIEW}:
        assert "File-only" in text
    elif action == reboot.BOOT_COLLECT:
        assert "different boot" in text and "No Windows restart" in text
    else:
        assert "20-second" in text and "Unknown counts remain unknown" in text
    assert ticket["physical_authority"] is False and not worker.calls
    if action == reboot.REVIEW:
        with pytest.raises(WizardError) as error:
            _ticket(
                arrival, action, dict(values(action), reviewer_id="modeled operator")
            )
        assert error.value.code == "REVIEWER_MUST_DIFFER"
