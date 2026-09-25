"""Strict original-shaped USB bytes through the actual cached projections.

Every host/device/process observation and storage reference is MODELED. The
real parsers, preparation, review, phase, and service projection execute; no
native helper, CIM observer, device, admission, or original store is run.
Node is used only by the finite existing fake-DOM renderer.
"""

from copy import deepcopy
from dataclasses import replace
from threading import RLock
from types import SimpleNamespace
import json
import time

import pytest

from rocell.application.physical_usb_identity_service import (
    PhysicalUsbIdentityService,
    _observation,
)
from rocell.application.physical_usb_trial_service import _UsbTrialBaseline
from rocell.application.physical_usb_identity_campaign import (
    PhysicalUsbIdentityCampaign,
)
from rocell.application.physical_camera_usb_qualification import (
    build_usb_qualification_phase,
)
from rocell.providers.windows import usb_identity_protocol as usb
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.ui.terminal import _UsbIdentityDisplay, _UsbQualificationDisplay
from test_arrival_usb_phase_ntfs_nominal import modeled_observed_evidence
from test_physical_camera_usb_phase_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    phase_subjects,
    refresh_read,
    LAUNCH,
)
from test_physical_camera_usb_phase_results import phase_boot
from test_physical_usb_identity_phase_operation import phase_permit
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_wizard_usb_qualification_ui import (
    view_for,
    complete_setup,
    prerequisite_summary,
)
from test_wizard_workspace_source_ui import render_snapshot


def _record(subject, reference):
    return dict(
        document=subject.to_dict(),
        evidence_sha256=subject.sha256,
        reference=reference.to_dict(),
        retention="M1_FULL_BYTES_READ_BACK",
    )


@pytest.fixture(autouse=True)
def forbid_native_execution(monkeypatch):
    from rocell.providers.windows import host_boot_observation as host
    from rocell.providers.windows.owned_usb_identity_runner import (
        OwnedUsbIdentityRunner,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

    def denied(*args, **kwargs):
        pytest.fail("projection test attempted native metadata, CIM or USB execution")

    monkeypatch.setattr(host, "_native_owner", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(OwnedUsbIdentityRunner, "run", denied)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, denied)


@pytest.fixture(params=[2, 3], ids=["raw-ex2-v2-operating-usb3", "nominal-raw-ex3"])
def observed_projection(ready, complete_setup, monkeypatch, request):
    import test_physical_camera_usb_phase_readback as phase_fixture

    # Actual enrollment/review owners with explicitly modeled USB/driver v2
    # packets, replacing the prefix helper's generic camera metadata fixture.
    monkeypatch.setattr(phase_fixture, "fresh_enrollment", usb_native_enrollment)
    made = phase_subjects(ready)
    phase_boot(made, monkeypatch)
    retained = refresh_read(ready)
    campaign = PhysicalUsbIdentityCampaign(
        made.operation,
        identity=made.subjects["identity"],
        review=made.subjects["runtime_review"],
    )
    started, utc = time.monotonic_ns(), time.time_ns()
    permit = replace(
        phase_permit(campaign),
        issued_at_ns=started,
        expires_at_ns=started + 30_000_000_000,
    )
    prepared = campaign.preparation_for_permit(permit)
    checks = [
        dict(
            boundary=name,
            started_ns=time.monotonic_ns(),
            finished_ns=time.monotonic_ns(),
            passed=True,
        )
        for name in owned.BOUNDARIES
    ]
    evidence = modeled_observed_evidence(
        prepared,
        deadline=started + 25_000_000_000,
        started=started,
        utc=utc,
        checks=checks,
    )
    if request.param == 2:
        # A second strict modeled packet keeps independent V2 SuperSpeed
        # operation while EX reports 2. Change every original EX call byte,
        # not just a compact value, then re-parse the complete owned result.
        raw = evidence.to_dict()
        wire = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)
        packet = json.loads(wire[raw["ready_length"] :])
        native = packet["native_receipt"]

        def ex2(value):
            data = bytearray.fromhex(value)
            data[23] = 2
            return data.hex()

        native["link"].update(ex_speed=2, ex_raw_hex=ex2(native["link"]["ex_raw_hex"]))
        for call in native["calls"]:
            if call["operation"] == "CONNECTION_EX":
                call["returned_raw_hex"] = ex2(call["returned_raw_hex"])
        raw["stdout"] = owned.stream_record(
            wire[: raw["ready_length"]] + usb.canonical(packet), complete=True
        )
        evidence = owned.OwnedUsbIdentityRunEvidence(usb.canonical(raw))
        assert evidence.status == "OBSERVED"
    made.retain("execution", evidence)
    sources = {
        name: (
            made.subjects[role]
            if type(made.subjects[role]) is bytes
            else made.subjects[role].payload
        )
        for name, role in (
            ("native_enrollment", "enrollment"),
            ("owned_usb_run", "execution"),
            ("host_boot", "host_boot"),
        )
    }
    phase = build_usb_qualification_phase(
        made.plan,
        phase="BASELINE",
        predecessor=None,
        context=dict(
            launch_session_id=LAUNCH,
            operation_id=made.phase_id,
            operator_id="phase-operator",
            started_at_utc_ns=made.start.occurred_at_ns,
            finished_at_utc_ns=max(time.time_ns(), made.now + 10000),
        ),
        sources=sources,
        references={
            name: made.refs[role]
            for name, role in (
                ("native_enrollment", "enrollment"),
                ("owned_usb_run", "execution"),
                ("host_boot", "host_boot"),
            )
        },
    )
    made.retain("phase_record", phase)
    # Explicitly modeled final cache state, not an original-store acceptance.
    # Its underlying preparation, execution, boot and phase are actual typed
    # producer bytes; the separate NTFS suite proves original admission.
    baseline = retained["usb_qualification_baseline"]
    baseline.update(
        state="RETAINED_BLOCKED",
        execution=_record(evidence, made.refs["execution"]),
        phase_record=_record(phase, made.refs["phase_record"]),
    )
    bound = made.plan.to_dict()["binding"]
    context = {
        key: bound[key]
        for key in (
            "source_sha256",
            "session_id",
            "cell_id",
            "origin_launch_id",
            "header_sha256",
            "prerequisites_sha256",
        )
    }
    owner = SimpleNamespace(
        _lock=RLock(),
        _publication=dict(status="CURRENT", operation_id="modeled-completion-log"),
        _qualification_trial=retained["usb_qualification_trial"],
        _context=lambda: deepcopy(context),
        _export_receipt=None,
        source_sha256=bound["source_sha256"],
        launch_id=LAUNCH,
        setup=SimpleNamespace(view=lambda: dict(publication=dict(status="CURRENT"))),
    )
    owner._trial = _UsbTrialBaseline(owner)
    owner._trial.adopt(retained)
    from rocell.application.physical_usb_absence_service import _UsbTrialAbsence

    owner._absence = _UsbTrialAbsence(owner)
    # Run both actual service layers, including strict byte rehydration. No
    # replacement _observation, execution_summary or qualification projection.
    card = PhysicalUsbIdentityService.qualification_view(owner)
    view = view_for(complete_setup)
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
    setup["session"]["stages"][3]["state"] = "BLOCKED"
    view["usb_qualification"] = card
    # The standalone legacy card gets the same genuine compact observation;
    # no old numeric-Vendor-ID fixture can mask a protocol mismatch.
    view["usb_identity"].update(
        execution=evidence.safe_summary(), observation=_observation(evidence)
    )
    return view, evidence, phase, owner, request.param


def test_strict_observed_original_to_service_and_both_renderers(observed_projection):
    view, evidence, phase, owner, ex_speed = observed_projection
    raw_before = evidence.payload
    native = evidence.observation.to_dict()
    for mapping in (native["pre_mapping"], native["post_mapping"]):
        assert all(
            "connection_index" in hop and "port" not in hop for hop in mapping["hops"]
        )
        assert mapping["hops"][0]["connection_index"] == 1
    assert all(
        "connection_index" in call and "port" not in call for call in native["calls"]
    )
    assert {c["phase"] for c in native["calls"]} == {
        "PRE",
        "OBSERVE",
        "POST",
        "CLEANUP",
    }
    assert native["device_descriptor"]["vid"] == "1234"
    assert native["device_descriptor"]["pid"] == "5678"
    assert native["device_descriptor"]["bcd_usb"] == 0x0300
    assert native["link"]["ex_speed"] == ex_speed
    assert native["link"]["ex_v2_available"] is True
    assert native["link"]["operating_superspeed_or_higher"] is True
    assert native["link"]["operating_superspeed_plus_or_higher"] is False
    assert bytes.fromhex(native["link"]["ex_v2_raw_hex"])[12:16] == b"\x03\0\0\0"
    assert phase.to_dict()["status"] == "OBSERVATIONS_RETAINED"
    compact = _observation(evidence)
    assert (
        compact["hub_port"] == 1
        and compact["vid"] == "1234"
        and compact["pid"] == "5678"
    )
    assert compact["operating_at_superspeed"] is True
    assert compact["operating_at_superspeed_plus"] is False
    assert compact["ex_speed"] == ex_speed
    assert view["usb_qualification"]["baseline"]["observation"] == compact
    assert owner._trial.execution().payload == raw_before
    _UsbQualificationDisplay._validate(view["usb_qualification"], view)
    _UsbIdentityDisplay._validate(view["usb_identity"], view)
    before = deepcopy(view)
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert "1234" in text and "5678" in text and "MODELED-ONLY" in text
        assert "OBSERVED" in text and "PHYSICAL USB QUERY" in text.replace("_", " ")
    assert view == before and evidence.payload == raw_before
    assert all(
        view["usb_qualification"][key] is False
        for key in (
            "physical_authority",
            "hardware_qualified",
            "camera_capture_authorized",
            "arm_access_authorized",
        )
    )


def test_renderers_reject_noncanonical_vid_pid_without_coercion(observed_projection):
    view, evidence, _, _, _ = observed_projection
    for key in ("vid", "pid"):
        for bad in (4660, True, "ABCD", "123", "12345", "0x12", "12g4"):
            changed = deepcopy(view)
            changed["usb_qualification"]["baseline"]["observation"][key] = bad
            changed["usb_identity"]["observation"][key] = bad
            assert (
                _UsbQualificationDisplay.validate(changed["usb_qualification"], changed)
                is None
            )
            assert (
                _UsbIdentityDisplay.validate(changed["usb_identity"], changed) is None
            )
            for text in render_snapshot(changed):
                assert "USB_QUALIFICATION_NOT_VERIFIED" in text
                assert "USB_IDENTITY_NOT_VERIFIED" in text
    assert _observation(evidence)["vid"] == "1234"
