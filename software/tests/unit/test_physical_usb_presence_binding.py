"""Pure bindings; all original references and physical observations MODELED.

No native process, USB, CIM or original store is accessed. Positive records are
constructed through the actual full descriptor/trace/owned evidence codecs.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event
import builtins
import io
import os
import subprocess
import time

import pytest

from rocell.application import physical_usb_presence_binding as m
from rocell.application import physical_camera_usb_qualification as qualification
from rocell.application import physical_onboarding_v2 as v2
from rocell.providers.windows import usb_identity_protocol as usb
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.providers.windows import host_boot_observation as host
from test_physical_camera_usb_qualification import (
    prerequisites,
    workspace,
    plan_fixture,
    reference,
    usb_native_enrollment,
)
from test_physical_camera_usb_readback import modeled_clean_held_evidence
from test_owned_usb_identity_runner import usb_fixture
from test_usb_identity_protocol import reaccount
from test_host_boot_observation import (
    request as boot_request,
    execution,
    FakeExecutor,
    WALL,
)


@pytest.fixture(autouse=True)
def no_process_or_device(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("pure binding test attempted a native process or device")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)


def observed_native(request, *, physical_instance=None):
    """MODELED complete one-hop USB3 descriptor/trace; no native executable."""
    rq = request.to_dict()
    physical = physical_instance or r"USB\VID_1234&PID_5678\MODELED-ONLY"
    hub, interface, key = r"USB\ROOT_HUB30\MODELED", r"\\?\MODELED-HUB", "MODELED-KEY"
    device = bytearray(18)
    device[:2] = b"\x12\x01"
    device[2:4] = (0x300).to_bytes(2, "little")
    device[7] = 64
    device[8:10] = (0x1234).to_bytes(2, "little")
    device[10:12] = (0x5678).to_bytes(2, "little")
    device[16:18] = b"\x03\x01"
    ex = bytearray(35)
    ex[0:4] = (1).to_bytes(4, "little")
    ex[4:22] = device
    ex[23] = 3
    ex[31:35] = (1).to_bytes(4, "little")
    exv2 = b"".join(x.to_bytes(4, "little") for x in (1, 16, 7, 3))
    language = b"\x04\x03\x09\x04"
    serial_text = "MODELED-ONLY"
    serial = bytes((2 + len(serial_text) * 2, 3)) + serial_text.encode("utf-16-le")
    calls = []

    def call(
        phase,
        operation,
        *,
        token=None,
        target=None,
        port=None,
        text=None,
        number=None,
        raw=None,
        descriptor=None,
        language_id=None,
    ):
        descriptor_op = operation in {
            "DEVICE_DESCRIPTOR",
            "LANGUAGE_DESCRIPTOR",
            "SERIAL_DESCRIPTOR",
        }
        returned = (
            (len(raw) + (12 if descriptor_op else 0))
            if raw is not None
            else (len(text.encode()) + 1 if text else 0)
        )
        calls.append(
            dict(
                sequence=len(calls) + 1,
                phase=phase,
                operation=operation,
                handle_id=token,
                target_id=target,
                connection_index=port,
                requested_bytes=max(128, returned),
                returned_bytes=returned,
                status="OK",
                error_domain="NONE",
                error_code=0,
                observed_text=text,
                observed_number=number,
                descriptor_index=(descriptor or 0) if descriptor_op else None,
                language_id=(language_id or 0) if descriptor_op else None,
                returned_raw_hex=None if raw is None else raw.hex(),
            )
        )

    def mapping_trace(phase, token):
        call(phase, "MAP_ENDPOINT", text=rq["endpoint"], number=1)
        call(phase, "DEVICE_ID", target=1, text=rq["expected_device_instance_id"])
        call(phase, "PARENT", target=1, number=2)
        call(phase, "HUB_INTERFACE", target=2)
        call(phase, "PARENT", target=2, number=3)
        call(phase, "HUB_INTERFACE", target=3, text=interface)
        call(phase, "DEVICE_ID", target=3, text=hub)
        call(phase, "DRIVER_KEY_PROPERTY", target=2, text=key)
        call(phase, "DEVICE_ID", target=2, text=physical)
        call(phase, "OPEN_HUB", target=3, token=token)
        call(phase, "HUB_INFORMATION", token=token, number=1)
        call(phase, "CONNECTION_EX", token=token, port=1, raw=ex)
        call(phase, "CONNECTION_DRIVER_KEY", token=token, port=1, text=key)
        call("CLEANUP", "CLOSE_HUB", token=token)
        call(phase, "PARENT", target=3, number=4)
        call(phase, "HUB_INTERFACE", target=4)
        call(phase, "HOST_CONTROLLER_PROPERTY", target=4, text=r"\\?\MODELED-HOST")
        call(phase, "DEVICE_ID", target=4, text=r"PCI\MODELED-HOST")

    mapping_trace("PRE", 1)
    call("OBSERVE", "OPEN_HUB", token=2, target=3)
    call("OBSERVE", "CONNECTION_EX", token=2, port=1, raw=ex)
    call("OBSERVE", "CONNECTION_EX_V2", token=2, port=1, raw=exv2)
    call("OBSERVE", "DEVICE_DESCRIPTOR", token=2, port=1, raw=device)
    call("OBSERVE", "LANGUAGE_DESCRIPTOR", token=2, port=1, raw=language)
    call(
        "OBSERVE",
        "SERIAL_DESCRIPTOR",
        token=2,
        port=1,
        raw=serial,
        descriptor=3,
        language_id=0x409,
    )
    call("CLEANUP", "CLOSE_HUB", token=2)
    mapping_trace("POST", 3)
    mapping = dict(
        returned_endpoint=rq["endpoint"],
        endpoint_instance_id=rq["expected_device_instance_id"],
        physical_usb_instance_id=physical,
        physical_driver_key=key,
        host_controller_instance_id=r"PCI\MODELED-HOST",
        hops=[
            dict(
                hub_instance_id=hub,
                hub_interface_path=interface,
                connection_index=1,
                downstream_driver_key=key,
            )
        ],
    )
    value = dict(
        schema=usb.OBSERVATION_SCHEMA,
        request_sha256=request.request_sha256,
        requested_endpoint=rq["endpoint"],
        expected_device_instance_id=rq["expected_device_instance_id"],
        outcome="OBSERVED",
        pre_mapping=mapping,
        post_mapping=deepcopy(mapping),
        device_descriptor=dict(
            raw_hex=device.hex(),
            vid="1234",
            pid="5678",
            bcd_usb=0x300,
            i_serial_number=3,
        ),
        languages=dict(raw_hex=language.hex(), language_ids=[0x409]),
        serial_descriptors=[
            dict(raw_hex=serial.hex(), language_id=0x409, value=serial_text)
        ],
        link=dict(
            connection_status=1,
            ex_speed=3,
            ex_v2_available=True,
            supported_usb_protocols=7,
            ex_raw_hex=ex.hex(),
            ex_v2_raw_hex=exv2.hex(),
            **dict(zip(usb._LINK_FLAGS, (True, True, False, False))),
        ),
        accounting=dict.fromkeys(usb._ACCOUNTING, 0),
        calls=calls,
        error=None,
        elapsed_ms=1,
    )
    reaccount(value)
    return usb.parse_usb_identity_observation(usb.canonical(value), request=request)


def presence_fixture(prerequisites, *, physical_instance=None):
    """Actual pure codecs; original refs and every physical observation MODELED."""
    plan = plan_fixture(prerequisites, mode="PHYSICAL")[0]
    p = plan.to_dict()["binding"]
    launch, operation = "wizard-presence-baseline", "operation-presence-baseline"
    native = usb_native_enrollment(p["source_sha256"], launch)
    _, selection, _ = qualification._native(
        plan, dict(launch_session_id=launch), usb.canonical(native)
    )
    case = usb_fixture(
        incapable=False,
        source_sha256=p["source_sha256"],
        selection_sha256=selection.sha256,
        native_identity_sha256=native["view"]["identity"]["identity_sha256"],
        cell_id=p["cell_id"],
        session_id=p["session_id"],
        header_sha256=p["header_sha256"],
        launch_session_id=launch,
        operation_sha256=usb.digest(operation.encode()),
    )
    observation = observed_native(case.request, physical_instance=physical_instance)
    raw = modeled_clean_held_evidence(case.prepared).to_dict()
    ready_wire = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)[
        : raw["ready_length"]
    ]
    ready = usb.UsbIdentityReady(ready_wire.rstrip(b"\n"))
    result = dict(
        schema=usb.RESULT_SCHEMA,
        request_sha256=case.request.request_sha256,
        child_pid=31415,
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=case.request.to_dict()["permit_sha256"],
        native_receipt=observation.to_dict(),
    )
    raw["process"]["returncode"] = 0
    raw.update(
        status="OBSERVED",
        started_utc_ns=WALL + 2000,
        finished_utc_ns=WALL + 3000,
        stdout=owned.stream_record(ready_wire + usb.canonical(result), complete=True),
    )
    run = owned.OwnedUsbIdentityRunEvidence(usb.canonical(raw))
    req = boot_request(
        source_sha256=p["source_sha256"],
        session_id=p["session_id"],
        trial_id=p["trial_id"],
        phase="BASELINE",
        launch_session_id=launch,
        operation_id=operation,
    )
    ex = execution(req, wall=WALL + 4000)
    ex = replace(
        ex,
        command={**ex.command, "process_model": host.PROCESS_MODEL},
        ownership=dict(
            schema=host.OWNERSHIP_SCHEMA,
            accounting_complete=True,
            pid=31415,
            peak_processes=1,
            peak_handles=12,
            handles_remaining=0,
            pins_remaining=0,
            unclosed_handles_remaining=0,
            stdin_pending=False,
            cleanup_deadline_ns=ex.finished_monotonic_ns + 1_000_000_000,
        ),
    )
    boot = (
        host.WindowsHostBootObserver(FakeExecutor(ex))
        .observe(
            req,
            cancellation=Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: None,
        )
        .to_dict()
    )
    # Explicit constructed physical-shaped test data, never application promotion.
    boot["origin"] = "WINDOWS_LOCAL_CIM"
    boot = host.HostBootObservation(usb.canonical(boot))
    sources = dict(
        native_enrollment=usb.canonical(native),
        owned_usb_run=run.payload,
        host_boot=boot.payload,
    )
    refs = {
        key: reference(payload, "MODELED-" + key) for key, payload in sources.items()
    }
    baseline = qualification.build_usb_qualification_phase(
        plan,
        phase="BASELINE",
        predecessor=None,
        context=dict(
            launch_session_id=launch,
            operation_id=operation,
            operator_id="MODELED-operator",
            started_at_utc_ns=WALL,
            finished_at_utc_ns=WALL + 10000,
        ),
        sources=sources,
        references=refs,
    )
    plan_ref = reference(plan.payload, "MODELED-plan")
    event = v2.V2JournalEvent(
        session_id=p["session_id"],
        session_header_sha256=p["header_sha256"],
        sequence=40,
        stage=m._STAGE,
        previous_state=v2.V2StageState.WAITING_OPERATOR,
        state=v2.V2StageState.REVIEW_PENDING,
        occurred_at_ns=3000,
        previous_event_sha256="a" * 64,
        evidence=(plan_ref,),
        detail_code="CAMERA_USB_QUALIFICATION_DECLARED_" + p["trial_id"][9:].upper(),
        event_sha256="0" * 64,
    )
    event = replace(event, event_sha256=v2._stable_hash(event.core_dict()))
    return dict(
        plan=plan,
        plan_reference=plan_ref,
        declaration_event=event,
        baseline=baseline,
        baseline_reference=reference(baseline.payload, "MODELED-baseline"),
        baseline_sources=sources,
    )


@pytest.fixture
def original(prerequisites):
    return presence_fixture(prerequisites)


def test_complete_original_join_and_detached_bounded_summary(original):
    result = m.build_usb_presence_phase_binding(**original)
    assert len(result.payload) <= m.MAX_BYTES
    data = result.to_dict()
    assert data["binding"] == original["plan"].to_dict()["binding"]
    assert (
        data["target"]["physical_usb_instance_id"]
        == r"USB\VID_1234&PID_5678\MODELED-ONLY"
    )
    assert data["phase"] == "RECONNECT_ABSENCE" and data["ordinal"] == 1
    assert all(data[key] is False for key in m.FLAGS)
    assert (
        m.verify_usb_presence_phase_binding(
            result.payload, expected_sha256=result.sha256, **original
        )
        == result
    )
    data["target"]["physical_usb_instance_id"] = "FORGED"
    assert result.to_dict()["target"]["physical_usb_instance_id"] != "FORGED"
    summary = result.safe_summary()
    assert "target" not in summary and summary["phase_binding_sha256"] == result.sha256
    with pytest.raises(FrozenInstanceError):
        result.payload = b"{}"
    print(
        f"MODELED binding {len(result.payload)} bytes; summary {len(usb.canonical(summary))} bytes"
    )


def rebuilt(original, sources):
    result = dict(original)
    result["baseline_sources"] = sources
    data = original["baseline"].to_dict()
    result["baseline"] = qualification.build_usb_qualification_phase(
        original["plan"],
        phase="BASELINE",
        predecessor=None,
        context=data["context"],
        sources=sources,
        references={
            key: reference(raw, "changed-" + key) for key, raw in sources.items()
        },
    )
    result["baseline_reference"] = reference(
        result["baseline"].payload, "changed-baseline"
    )
    return result


def test_closed_canonical_binding_and_zero_authority(original):
    binding = m.build_usb_presence_phase_binding(**original)
    for field in m._TOP:
        data = binding.to_dict()
        del data[field]
        with pytest.raises(ValueError):
            m.UsbPresencePhaseBinding(usb.canonical(data))
    for field in m.FLAGS:
        for value in (True, 0, None):
            data = binding.to_dict()
            data[field] = value
            with pytest.raises(ValueError):
                m.UsbPresencePhaseBinding(usb.canonical(data))
    for payload in (
        binding.payload + b"\n",
        b" " + binding.payload,
        b"{}",
        b'{"schema":1,"schema":2}',
        b'{"schema":NaN}',
        b"[" * 30,
        b" " * (m.MAX_BYTES + 1),
        None,
        {},
        binding,
    ):
        with pytest.raises(ValueError):
            m.UsbPresencePhaseBinding(payload)
    for path, value in (
        (("ordinal",), True),
        (("ordinal",), 2),
        (("phase",), "BASELINE"),
        (("extra",), False),
        (("not_before_utc_ns",), 1),
        (("target", "extra"), "ignored"),
        (("target", "physical_usb_instance_id_sha256"), "a" * 64),
        (("binding", "trial_id"), "usbtrial-arbitrary"),
    ):
        data = binding.to_dict()
        row = data
        for key in path[:-1]:
            row = row[key]
        row[path[-1]] = value
        with pytest.raises(ValueError):
            m.UsbPresencePhaseBinding(usb.canonical(data))


def test_independent_originals_refuse_rehashed_target_or_subject_substitution(original):
    binding = m.build_usb_presence_phase_binding(**original)
    for fault in ("target", "source", "prior-attempt", "baseline-hash"):
        data = binding.to_dict()
        if fault == "target":
            target = r"USB\VID_1234&PID_5678\OTHER-PHYSICAL-UNIT"
            data["target"].update(
                physical_usb_instance_id=target,
                physical_usb_instance_id_sha256=usb.digest(target.encode()),
            )
        elif fault == "source":
            data["binding"]["source_sha256"] = "f" * 64
        elif fault == "prior-attempt":
            data["baseline_execution"]["attempt_id"] = "other-attempt"
        else:
            data["baseline"]["sha256"] = "f" * 64
            data["baseline"]["reference"]["payload_sha256"] = "f" * 64
        payload = usb.canonical(data)
        m.UsbPresencePhaseBinding(
            payload
        )  # Syntax does not claim original authenticity.
        with pytest.raises(m.UsbPresenceBindingError):
            m.verify_usb_presence_phase_binding(
                payload, expected_sha256=usb.digest(payload), **original
            )
    with pytest.raises(ValueError):
        m.verify_usb_presence_phase_binding(
            binding.payload, expected_sha256="f" * 64, **original
        )
    for role in m.ROLES:
        modified = {**original["baseline_sources"], role: b"{}"}
        with pytest.raises(ValueError):
            m.build_usb_presence_phase_binding(
                **{**original, "baseline_sources": modified}
            )


def test_declaration_must_be_exact_committed_convention_and_precede_baseline(original):
    for changes in (
        dict(detail_code="CAMERA_USB_QUALIFICATION_DECLARED_" + "F" * 32),
        dict(detail_code="CAMERA_USB_QUALIFICATION_REQUESTED_" + "1" * 32),
        dict(session_id="other-session"),
        dict(session_header_sha256="f" * 64),
        dict(sequence=0),
        dict(stage=qualification.PhysicalOnboardingStage.CAMERA_RECEIPT),
        dict(previous_state=v2.V2StageState.BLOCKED),
        dict(state=v2.V2StageState.PASS),
        dict(evidence=()),
        dict(evidence=(original["baseline_reference"],)),
        dict(occurred_at_ns=1),
        dict(occurred_at_ns=WALL + 1),
    ):
        event = replace(original["declaration_event"], **changes)
        event = replace(event, event_sha256=v2._stable_hash(event.core_dict()))
        with pytest.raises(ValueError):
            m.build_usb_presence_phase_binding(
                **{**original, "declaration_event": event}
            )
    stale = replace(original["declaration_event"], occurred_at_ns=4000)
    with pytest.raises(ValueError):
        m.build_usb_presence_phase_binding(**{**original, "declaration_event": stale})


def test_reference_roles_types_and_complete_baseline_are_not_caller_claims(original):
    for key in ("plan_reference", "baseline_reference"):
        old = original[key]
        for changed in (
            old.to_dict(),
            replace(old, payload_sha256="f" * 64),
            replace(old, payload_bytes=old.payload_bytes + 1),
            replace(old, stage=qualification.PhysicalOnboardingStage.CAMERA_RECEIPT),
        ):
            with pytest.raises(ValueError):
                m.build_usb_presence_phase_binding(**{**original, key: changed})
    for key in ("plan", "baseline"):
        forged = object.__new__(type(original[key]))
        object.__setattr__(forged, "payload", b"{}")
        with pytest.raises(ValueError):
            m.build_usb_presence_phase_binding(**{**original, key: forged})
        with pytest.raises(ValueError):
            m.build_usb_presence_phase_binding(
                **{**original, key: original[key].to_dict()}
            )
    data = original["baseline"].to_dict()
    data["values"]["physical_usb_instance"]["sha256"] = "f" * 64
    with pytest.raises(ValueError):
        m.build_usb_presence_phase_binding(
            **{
                **original,
                "baseline": qualification.UsbQualificationPhase(usb.canonical(data)),
            }
        )
    for sources in ({}, {**original["baseline_sources"], "endpoint_inventory": b"{}"}):
        with pytest.raises(ValueError):
            m.build_usb_presence_phase_binding(
                **{**original, "baseline_sources": sources}
            )
    with pytest.raises(TypeError):
        m.build_usb_presence_phase_binding(**original, target_instance_id="USB\\FORGED")


def test_old_v1_or_injected_boot_never_becomes_current_physical_ownership(original):
    for kind in ("legacy-v1", "injected"):
        boot = host.HostBootObservation(
            original["baseline_sources"]["host_boot"]
        ).to_dict()
        if kind == "legacy-v1":
            boot["schema"] = host.SCHEMA
            del boot["command"]["process_model"]
            del boot["execution"]["ownership"]
            boot["command_sha256"] = usb.digest(usb.canonical(boot["command"]))
        else:
            boot["origin"] = "INJECTED_CIM_EXECUTOR"
        legacy = host.HostBootObservation(usb.canonical(boot))
        changed = rebuilt(
            original, {**original["baseline_sources"], "host_boot": legacy.payload}
        )
        assert changed["baseline"].to_dict()["status"] == "OBSERVATIONS_RETAINED"
        with pytest.raises(
            m.UsbPresenceBindingError, match="CURRENT_OWNED_HOST_BOOT_REQUIRED"
        ):
            m.build_usb_presence_phase_binding(**changed)


def test_endpoint_mi_child_is_not_a_physical_presence_target(prerequisites):
    original = presence_fixture(
        prerequisites, physical_instance=r"USB\VID_1234&PID_5678&MI_00\MODELED-ENDPOINT"
    )
    assert original["baseline"].to_dict()["status"] == "OBSERVATIONS_RETAINED"
    with pytest.raises(ValueError):
        m.build_usb_presence_phase_binding(**original)


def test_held_standalone_run_and_modeled_plan_do_not_become_a_physical_baseline(
    original,
):
    run = owned.OwnedUsbIdentityRunEvidence(
        original["baseline_sources"]["owned_usb_run"]
    )
    held = modeled_clean_held_evidence(run.preparation).to_dict()
    held.update(started_utc_ns=WALL + 2000, finished_utc_ns=WALL + 3000)
    held_run = owned.OwnedUsbIdentityRunEvidence(usb.canonical(held))
    changed = rebuilt(
        original, {**original["baseline_sources"], "owned_usb_run": held_run.payload}
    )
    assert changed["baseline"].to_dict()["status"] == "HELD"
    with pytest.raises(m.UsbPresenceBindingError, match="COMPLETE_BASELINE_REQUIRED"):
        m.build_usb_presence_phase_binding(**changed)
    with pytest.raises(m.UsbPresenceBindingError, match="EXACT_SUBJECT_TYPES_REQUIRED"):
        m.build_usb_presence_phase_binding(**{**original, "baseline": run})
    plan = original["plan"].to_dict()
    plan["mode"] = "MODELED"
    with pytest.raises(m.UsbPresenceBindingError, match="PHYSICAL_PLAN_REQUIRED"):
        m.build_usb_presence_phase_binding(
            **{
                **original,
                "plan": qualification.UsbQualificationPlan(usb.canonical(plan)),
            }
        )


def test_reconstruction_encoding_and_summary_do_not_read_or_acquire(
    original, monkeypatch
):
    binding = m.build_usb_presence_phase_binding(**original)

    def denied(*args, **kwargs):
        pytest.fail("pure binding accessed a file, process, clock or device")

    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (Path, ("open", "read_bytes", "stat", "lstat", "mkdir", "resolve")),
            (os, ("open", "listdir", "scandir", "stat", "lstat")),
            (subprocess, ("Popen", "run")),
            (time, ("monotonic", "monotonic_ns", "time", "time_ns")),
        ):
            for name in names:
                guard.setattr(owner, name, denied)
        restored = m.verify_usb_presence_phase_binding(
            binding.payload, expected_sha256=binding.sha256, **original
        )
        assert restored.payload == binding.payload
        assert restored.safe_summary() == binding.safe_summary()
