"""Pure reboot boot scopes over MODELED originals; never a collector release.

These tests exercise real immutable codecs with in-memory report bytes. No
original store, lease, process, CIM query, USB or camera operation is performed.
"""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess

import pytest

from rocell.application import physical_usb_reboot_boot as m
from rocell.providers.windows import host_boot_observation as host
from test_physical_camera_usb_reboot_preparation import prepared_case
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_reboot_phase import predecessor, _modeled_boot, _utc_text
from test_physical_usb_presence_binding import reference


@pytest.fixture(autouse=True)
def no_process_or_devices(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Pure reboot boot scope attempted process, CIM or device access")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)
    monkeypatch.setattr(host.LocalCimHostBootExecutor, "execute", denied)


def journal(intent, ref, *, time, **changes):
    i = intent.to_dict()
    event = m.V2JournalEvent(
        i["binding"]["session_id"],
        i["binding"]["header_sha256"],
        i["phase_start_event"]["sequence"] + 3,
        m.STAGE_ORDER[3],
        m.V2StageState.BLOCKED,
        m.V2StageState.WAITING_OPERATOR,
        time,
        "a" * 64,
        (ref,),
        m.usb_reboot_event("BOOT_REQUESTED", i["phase_id"]),
        "0" * 64,
    )
    event = replace(event, **changes)
    return m._parse_event(
        replace(event, event_sha256=m.digest(m.canonical(event.core_dict()))).to_dict()
    )


@pytest.fixture
def boot_case(prepared_case, monkeypatch):
    # The predecessor fixtures use this facade with an incapable in-memory
    # executor. Block even that facade only after fixture construction; native
    # process/CIM entry points remain blocked throughout all fixture setup.
    monkeypatch.setattr(
        host.WindowsHostBootObserver,
        "observe",
        lambda *a, **k: pytest.fail("Pure boot scope constructed an observer"),
    )
    c = prepared_case
    ref = reference(c.prepared.payload, "MODELED-reboot-preparation-boot-test")
    inputs = dict(
        preparation=c.prepared,
        preparation_reference=ref,
        reconnect=c.args["reconnect"],
        reconnect_reference=c.args["reconnect_reference"],
    )
    intent = m.build_usb_reboot_boot_intent(**inputs)
    request_ref = reference(intent.payload, "MODELED-reboot-boot-intent")
    requested = journal(intent, request_ref, time=c.args["prepared_at_utc_ns"] + 1)
    return SimpleNamespace(
        prepared=c,
        inputs=inputs,
        intent=intent,
        request_ref=request_ref,
        requested=requested,
        previous_boot=host.HostBootObservation(
            c.args["reconnect_sources"]["host_boot"]
        ),
    )


def report(
    c,
    *,
    epoch=None,
    origin="WINDOWS_LOCAL_CIM",
    host_change=False,
    cleanup_uncertain=False,
    context_changes=None
):
    i = c.intent.to_dict()
    context = dict(c.prepared.subject.context)
    if context_changes:
        context.update(context_changes)
    # The fixture builder observes 3 microseconds after this new Begin.
    # It retains the observer's own independent monotonic epoch (1..2).
    assert c.requested.occurred_at_ns <= context["started_at_utc_ns"] + 3000
    return _modeled_boot(
        c.prepared.args["original_baseline"]["plan"],
        context,
        boot_epoch=i["phase_started_at_utc_ns"] if epoch is None else epoch,
        origin=origin,
        host_change=host_change,
        cleanup_uncertain=cleanup_uncertain,
    )


def classify(c, observation, **changes):
    args = dict(
        intent=c.intent,
        expected_sha256=observation.sha256,
        requested_event=c.requested,
        reconnect_boot=c.previous_boot,
    )
    args.update(changes)
    return m.classify_usb_reboot_boot_observation(observation, **args)


def test_intent_is_exact_bounded_detached_and_not_executable(boot_case, monkeypatch):
    c = boot_case
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("Pure intent opened file")
    )
    checked = m.verify_usb_reboot_boot_intent(
        c.intent.payload,
        expected_sha256=c.intent.sha256,
        **c.inputs,
    )
    assert checked.payload == c.intent.payload
    assert len(checked.payload) <= m.MAX_INTENT_BYTES
    assert all(checked.to_dict()[key] is False for key in m._FLAGS)
    d = checked.to_dict()
    assert (
        d["reconnect_finished_at_utc_ns"]
        == c.inputs["reconnect"].to_dict()["context"]["finished_at_utc_ns"]
    )
    assert d["reconnect_host_boot"]["sha256"] == c.previous_boot.sha256
    d["budget"]["process_run_ms"] = 1
    assert checked.to_dict()["budget"]["process_run_ms"] == 10000
    with pytest.raises(FrozenInstanceError):
        checked.payload = b"{}"
    summary = checked.safe_summary()
    assert summary["status"] == "DECLARED_BOOT_SCOPE_NOT_EXECUTABLE"
    assert summary["required_relation"] == "SAME_HOST_DIFFERENT_BOOT"
    assert all(summary[key] is False for key in m._FLAGS)
    assert len(m.canonical(summary)) < 2048
    assert "machine_uuid" not in m.canonical(summary).decode()


def test_nominal_report_join_and_lower_new_monotonic_epoch(boot_case, monkeypatch):
    c = boot_case
    current = report(c)
    old_bytes = (c.inputs["reconnect"].payload, c.previous_boot.payload)
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("Pure join opened file")
    )
    assert (
        current.to_dict()["execution"]["started_monotonic_ns"]
        < c.previous_boot.to_dict()["execution"]["started_monotonic_ns"]
    )
    assert (
        m.verify_usb_reboot_boot_observation(
            current.payload,
            intent=c.intent,
            expected_sha256=current.sha256,
            requested_event=c.requested,
        ).payload
        == current.payload
    )
    assert classify(c, current) == "BOOT_RETAINED"
    assert old_bytes == (c.inputs["reconnect"].payload, c.previous_boot.payload)
    assert current.to_dict()["physical_authority"] is False


def test_strong_restart_interval_has_exact_equality_boundaries(boot_case):
    c = boot_case
    i = c.intent.to_dict()
    lower, upper = i["reconnect_finished_at_utc_ns"], i["phase_started_at_utc_ns"]
    for endpoint in (lower, upper):
        assert endpoint % 1000 == 0
        assert host._utc_ns(_utc_text(endpoint)) == endpoint
    for epoch, expected in (
        (lower - 1000, "BOOT_HELD"),
        (lower, "BOOT_HELD"),
        (lower + 1000, "BOOT_RETAINED"),
        (upper, "BOOT_RETAINED"),
        (upper + 1000, "BOOT_HELD"),
    ):
        observation = report(c, epoch=epoch)
        assert classify(c, observation) == expected, (epoch, expected)


def test_same_boot_other_host_and_injected_origin_are_held(boot_case):
    c = boot_case
    same_boot = host._utc_ns(
        c.previous_boot.to_dict()["response"]["last_boot_up_time_utc"]
    )
    for changes in (
        dict(epoch=same_boot),
        dict(host_change=True),
        dict(origin="INJECTED_CIM_EXECUTOR"),
    ):
        observation = report(c, **changes)
        assert classify(c, observation) == "BOOT_HELD", changes


def test_unknown_cleanup_dominates_bad_boot_relation(boot_case):
    c = boot_case
    for changes in (
        {},
        dict(host_change=True),
        dict(epoch=c.intent.to_dict()["phase_started_at_utc_ns"] + 1000),
    ):
        observation = report(c, cleanup_uncertain=True, **changes)
        assert classify(c, observation) == "BOOT_UNCERTAIN"
        assert observation.to_dict()["execution"]["cleanup_errors"]


def test_closed_intent_refuses_policy_budget_aliases_and_authority(boot_case):
    c = boot_case
    for key in m._FLAGS:
        for value in (True, 0):
            d = c.intent.to_dict()
            d[key] = value
            with pytest.raises(
                m.UsbRebootBootError, match="REBOOT_BOOT_POLICY_CHANGED"
            ):
                m.UsbRebootBootIntent(m.canonical(d))
    for key, value in (
        ("process_run_ms", 10001),
        ("admission_window_ms", 30001),
        ("cleanup_ms", 2001),
        ("process_run_ms", True),
    ):
        d = c.intent.to_dict()
        d["budget"][key] = value
        with pytest.raises(m.UsbRebootBootError, match="REBOOT_BOOT_POLICY_CHANGED"):
            m.UsbRebootBootIntent(m.canonical(d))
    d = c.intent.to_dict()
    d["unexpected"] = "no extension fields"
    with pytest.raises(m.UsbRebootBootError, match="INVALID_REBOOT_BOOT_INTENT"):
        m.UsbRebootBootIntent(m.canonical(d))
    with pytest.raises(m.UsbRebootBootError):
        m.UsbRebootBootIntent(c.intent.payload + b"\n")


def test_rehashed_intent_claims_do_not_replace_independent_inputs(boot_case):
    c = boot_case
    for key, value in (
        ("operation_sha256", "a" * 64),
        ("baseline_sha256", "a" * 64),
        (
            "reconnect_finished_at_utc_ns",
            c.intent.to_dict()["reconnect_finished_at_utc_ns"] + 1000,
        ),
    ):
        d = c.intent.to_dict()
        d[key] = value
        changed = m.UsbRebootBootIntent(m.canonical(d))
        with pytest.raises(
            m.UsbRebootBootError, match="REBOOT_BOOT_INTENT_RECONSTRUCTION_MISMATCH"
        ):
            m.verify_usb_reboot_boot_intent(
                changed, expected_sha256=changed.sha256, **c.inputs
            )
    changed_ref = reference(
        c.inputs["preparation"].payload, "MODELED-aliased-preparation"
    )
    with pytest.raises(
        m.UsbRebootBootError, match="REBOOT_BOOT_INTENT_RECONSTRUCTION_MISMATCH"
    ):
        m.verify_usb_reboot_boot_intent(
            c.intent,
            expected_sha256=c.intent.sha256,
            **dict(c.inputs, preparation_reference=changed_ref),
        )


def test_report_requires_exact_phase_launch_hash_and_requested_event(boot_case):
    c = boot_case
    current = report(c)
    for context in (
        dict(operation_id="usbphase-" + "a" * 32),
        dict(launch_session_id="wizard-MODELED-old-launch"),
    ):
        wrong = report(c, context_changes=context)
        with pytest.raises(
            m.UsbRebootBootError, match="REBOOT_BOOT_OBSERVATION_INTENT_MISMATCH"
        ):
            classify(c, wrong)
    with pytest.raises(
        m.UsbRebootBootError, match="REBOOT_BOOT_OBSERVATION_INTENT_MISMATCH"
    ):
        classify(c, current, expected_sha256="a" * 64)
    for changes in (
        dict(
            detail_code=m.usb_reboot_event(
                "QUERY_REQUESTED", c.intent.to_dict()["phase_id"]
            )
        ),
        dict(stage=m.STAGE_ORDER[2]),
        dict(session_id="MODELED-wrong-session"),
        dict(
            state=m.V2StageState.BLOCKED, previous_state=m.V2StageState.WAITING_OPERATOR
        ),
    ):
        wrong_event = journal(
            c.intent, c.request_ref, time=c.requested.occurred_at_ns, **changes
        )
        with pytest.raises(
            m.UsbRebootBootError, match="REBOOT_BOOT_ORIGINAL_EVENT_MISMATCH"
        ):
            classify(c, current, requested_event=wrong_event)


def test_report_cannot_precede_request_or_preparation(boot_case):
    c = boot_case
    observation = report(c)
    for time in (
        c.intent.to_dict()["prepared_at_utc_ns"] - 1,
        observation.to_dict()["execution"]["started_utc_ns"] + 1,
    ):
        wrong = journal(c.intent, c.request_ref, time=time)
        with pytest.raises(
            m.UsbRebootBootError, match="REBOOT_BOOT_OBSERVATION_INTENT_MISMATCH"
        ):
            classify(c, observation, requested_event=wrong)


def test_old_boot_is_independent_exact_original_not_a_comparison_hint(boot_case):
    c = boot_case
    observation = report(c)
    baseline_boot = host.HostBootObservation(
        c.prepared.args["original_baseline"]["baseline_sources"]["host_boot"]
    )
    assert baseline_boot.sha256 != c.previous_boot.sha256
    with pytest.raises(ValueError):
        classify(c, observation, reconnect_boot=baseline_boot)
    with pytest.raises(m.UsbRebootBootError, match="EXACT_RECONNECT_BOOT_REQUIRED"):
        classify(c, observation, reconnect_boot=c.previous_boot.to_dict())
    intent = c.intent.to_dict()
    intent["preparation"]["reference"]["evidence_id"] = intent["reconnect_host_boot"][
        "reference"
    ]["evidence_id"]
    intent["preparation"]["reference"]["package_sha256"] = intent[
        "reconnect_host_boot"
    ]["reference"]["package_sha256"]
    with pytest.raises(
        m.UsbRebootBootError, match="DISTINCT_REBOOT_BOOT_ORIGINALS_REQUIRED"
    ):
        m.UsbRebootBootIntent(m.canonical(intent))


def test_requested_event_requires_original_header_and_one_exact_payload(boot_case):
    c = boot_case
    observation = report(c)
    wrong_header = journal(
        c.intent,
        c.request_ref,
        time=c.requested.occurred_at_ns,
        session_header_sha256="b" * 64,
    )
    with pytest.raises(
        m.UsbRebootBootError, match="REBOOT_BOOT_ORIGINAL_EVENT_MISMATCH"
    ):
        classify(c, observation, requested_event=wrong_header)
    wrong_ref = reference(
        b'{"MODELED":"different original"}', "MODELED-wrong-boot-request"
    )
    for refs in (
        (),
        tuple(sorted((c.request_ref, wrong_ref), key=lambda ref: ref.evidence_id)),
    ):
        event = journal(
            c.intent, c.request_ref, time=c.requested.occurred_at_ns, evidence=refs
        )
        with pytest.raises(
            m.UsbRebootBootError, match="EXACT_REBOOT_BOOT_INTENT_REFERENCE_REQUIRED"
        ):
            classify(c, observation, requested_event=event)
    wrong_payload = journal(c.intent, wrong_ref, time=c.requested.occurred_at_ns)
    with pytest.raises(
        m.qualification.UsbQualificationError, match="ORIGINAL_BYTES_REFERENCE_MISMATCH"
    ):
        classify(c, observation, requested_event=wrong_payload)
