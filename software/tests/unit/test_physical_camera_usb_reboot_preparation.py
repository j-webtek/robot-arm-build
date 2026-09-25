"""Pure reboot preparation/data joins over explicitly MODELED original facts.

No original-store authenticity, process, CIM, USB or hardware result is claimed.
The completion ledger and owner projection are modeled; actual codecs rebuild
every supplied observed subject, independent permit and derived comparison.
"""

from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError, replace
import builtins
import io
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_usb_reboot as m
from rocell.application import physical_camera_usb_reboot_constants as constants
from rocell.application import physical_onboarding_v2 as journal
from rocell.application import physical_usb_identity_campaign as campaign
from rocell.application import physical_usb_reboot_phase as phase
from rocell.application.cell_commissioning_coordinator import (
    AttemptResult,
    ObservedPowerState,
    WorkerReceipt,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.owned_usb_identity_runner import OwnedUsbIdentityRunner
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.safety.effects import EffectCertainty
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_presence_binding import reference
from test_physical_usb_reboot_phase import predecessor, reboot_fixture
from test_physical_camera_usb_reconnect_preparation import (
    enrollment_subjects,
    runtime_report,
    reissue_enrollment,
)
from test_usb_reconnect_phase_adversarial import modeled_owner_projection


@pytest.fixture(autouse=True)
def no_native_or_process(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Pure reboot preparation attempted acquisition")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)
    monkeypatch.setattr(OwnedUsbIdentityRunner, "run", denied)


def preparation_inputs(predecessor, *, subject=None):
    """Reusable full build kwargs; all observations and ledger facts MODELED."""
    subject = reboot_fixture(predecessor) if subject is None else subject
    report = subject.event.to_dict()
    binding = subject.original_baseline["plan"].to_dict()["binding"]
    start = journal.V2JournalEvent(
        session_id=binding["session_id"],
        session_header_sha256=binding["header_sha256"],
        sequence=100,
        stage=m._STAGE,
        previous_state=journal.V2StageState.BLOCKED,
        state=journal.V2StageState.WAITING_OPERATOR,
        occurred_at_ns=report["phase_started_at_utc_ns"],
        previous_event_sha256="a" * 64,
        evidence=(subject.reconnect_reference,),
        detail_code=constants.usb_reboot_event(
            "PREPARATION_REQUESTED", report["phase_id"]
        ),
        event_sha256="0" * 64,
    )
    start = replace(start, event_sha256=journal._stable_hash(start.core_dict()))
    documents, ids = enrollment_subjects(
        json.loads(subject.sources["native_enrollment"])
    )
    now = report["reported_at_utc_ns"]
    ledger = dict(
        schema="rocell.usb_phase_metadata_acquisition_ledger.v1",
        source_sha256=binding["source_sha256"],
        session_id=binding["session_id"],
        launch_session_id=report["launch_session_id"],
        trial_id=binding["trial_id"],
        phase_id=report["phase_id"],
        phase_started_at_utc_ns=start.occurred_at_ns,
        entries=[
            dict(
                role=role,
                action_id=action,
                operation_id=op_id,
                started_at_utc_ns=now + i * 10 + 1,
                finished_at_utc_ns=now + i * 10 + 2,
                published_at_utc_ns=now + i * 10 + 3,
                document_sha256=digest(canonical(document)),
                result_sha256=digest(canonical({"MODELED_COMPLETION_RESULT": i})),
                completion_logged=True,
            )
            for i, ((role, action), document, op_id) in enumerate(
                zip(m._ACQUISITIONS, documents, ids)
            )
        ],
    )
    runtime = registration.UsbIdentityRuntimeRegistration(
        canonical(subject.operation.to_dict()["runtime"])
    )
    return dict(
        **{
            key: getattr(subject, key)
            for key in (
                "original_baseline",
                "received",
                "absence",
                "absence_reference",
                "absence_sources",
                "reconnect",
                "reconnect_reference",
                "reconnect_sources",
                "reconnect_permit",
            )
        },
        phase_start_event=start,
        phase_id=report["phase_id"],
        operator_event=subject.event,
        operator_event_reference=subject.references["operator_event"],
        enrollment=subject.sources["native_enrollment"],
        enrollment_reference=subject.references["native_enrollment"],
        acquisition_ledger=ledger,
        operation=subject.operation,
        runtime_report=runtime_report(runtime),
        prepared_at_utc_ns=now + 100,
        operator_id=report["operator_id"],
    )


@pytest.fixture
def prepared_case(predecessor):
    subject = reboot_fixture(predecessor)
    args = preparation_inputs(predecessor, subject=subject)
    return SimpleNamespace(
        subject=subject, args=args, prepared=m.build_usb_reboot_preparation(**args)
    )


def verify(prepared, args, **changes):
    originals = {
        key: value
        for key, value in args.items()
        if key
        not in {
            "acquisition_ledger",
            "operation",
            "runtime_report",
            "prepared_at_utc_ns",
            "operator_id",
        }
    }
    originals.update(changes)
    return m.verify_usb_reboot_preparation(
        prepared.payload, expected_sha256=prepared.sha256, **originals
    )


def test_exact_preparation_is_inert_and_binds_full_originals(
    prepared_case, monkeypatch
):
    def denied(*args, **kwargs):
        pytest.fail("Pure preparation opened a file")

    for target, attr in ((builtins, "open"), (io, "open"), (Path, "open")):
        monkeypatch.setattr(target, attr, denied)
    made, args = prepared_case.prepared, prepared_case.args
    assert verify(made, args).payload == made.payload
    d = made.to_dict()
    assert d["schema"] == "rocell.usb_reboot_preparation.v1"
    assert d["baseline_sha256"] == args["original_baseline"]["baseline"].sha256
    assert d["reconnect_reference"] == args["reconnect_reference"].to_dict()
    assert d["phase_start_event"]["evidence"] == [d["reconnect_reference"]]
    assert len(made.payload) <= 128 * 1024
    assert all(d[key] is False for key in m.FLAGS)
    assert len(canonical(made.safe_summary())) <= 16 * 1024
    with pytest.raises(FrozenInstanceError):
        made.payload = b"{}"
    d["operator_id"] = "not-original"
    assert made.to_dict()["operator_id"] == args["operator_id"]


def test_constants_close_exact_eleven_roles_and_seven_event_path():
    assert len(constants.USB_REBOOT_ROLE_BYTES) == 11
    assert sum(constants.USB_REBOOT_ROLE_BYTES.values()) == 1224 * 1024
    assert constants.MAX_USB_REBOOT_EVENTS == 7
    phase_id = "usbphase-" + "f" * 32
    for role in constants.USB_REBOOT_ROLE_BYTES:
        assert constants.USB_REBOOT_LABEL.fullmatch(
            constants.usb_reboot_label(role, phase_id)
        )
    for kind in constants.USB_REBOOT_EVENTS:
        assert constants.USB_REBOOT_EVENT.fullmatch(
            constants.usb_reboot_event(kind, phase_id)
        )
    for kind, value in (("PASS", phase_id), ("RETAINED", "wrong"), (True, phase_id)):
        with pytest.raises(ValueError):
            constants.usb_reboot_event(kind, value)


def test_ledger_requires_three_exact_current_publications(prepared_case):
    args = prepared_case.args
    mutations = [
        ((), "source_sha256", "0" * 64),
        ((), "launch_session_id", "old-launch"),
        ((), "phase_id", "usbphase-" + "a" * 32),
        (("entries", 0), "completion_logged", False),
        (("entries", 1), "action_id", "native_camera_identity"),
        (("entries", 2), "document_sha256", "1" * 64),
        (
            ("entries", 0),
            "started_at_utc_ns",
            args["phase_start_event"].occurred_at_ns - 1,
        ),
        (("entries", 2), "published_at_utc_ns", args["prepared_at_utc_ns"] + 1),
        (("entries", 0), "result_sha256", "bad"),
        (("entries", 1), "operation_id", args["phase_id"]),
        (("entries", 0), "completion_logged", 1),
    ]
    for path, key, value in mutations:
        ledger = deepcopy(args["acquisition_ledger"])
        target = ledger
        for part in path:
            target = target[part]
        target[key] = value
        with pytest.raises(m.UsbRebootPreparationError):
            m.build_usb_reboot_preparation(**dict(args, acquisition_ledger=ledger))
    for entries in (
        [],
        args["acquisition_ledger"]["entries"][:2],
        list(reversed(args["acquisition_ledger"]["entries"])),
    ):
        with pytest.raises(m.UsbRebootPreparationError):
            m.build_usb_reboot_preparation(
                **dict(
                    args,
                    acquisition_ledger=dict(
                        args["acquisition_ledger"], entries=entries
                    ),
                )
            )


def test_exact_start_report_references_source_and_wire(prepared_case):
    made, args = prepared_case.prepared, prepared_case.args
    for changes in (
        dict(session_id="another-session"),
        dict(session_header_sha256="0" * 64),
        dict(occurred_at_ns=args["phase_start_event"].occurred_at_ns + 1),
        dict(evidence=(args["absence_reference"],)),
        dict(
            detail_code="CAMERA_USB_TRIAL_RECONNECT_PREPARATION_REQUESTED_" + "F" * 32
        ),
    ):
        start = replace(args["phase_start_event"], **changes)
        start = replace(start, event_sha256=journal._stable_hash(start.core_dict()))
        with pytest.raises(m.UsbRebootPreparationError):
            m.build_usb_reboot_preparation(**dict(args, phase_start_event=start))
    for key in (
        "enrollment_reference",
        "operator_event_reference",
        "reconnect_reference",
        "absence_reference",
    ):
        ref = replace(args[key], payload_sha256="0" * 64)
        with pytest.raises(m.UsbRebootPreparationError):
            verify(made, args, **{key: ref})
    for key in m.FLAGS:
        changed = made.to_dict()
        changed[key] = 0
        with pytest.raises(m.UsbRebootPreparationError):
            m.UsbRebootPreparation(canonical(changed))
    for payload in (made.payload + b"\n", b"[]", b"x" * (128 * 1024 + 1)):
        with pytest.raises(m.UsbRebootPreparationError):
            m.UsbRebootPreparation(payload)


def test_file_roster_and_independent_permit_cannot_be_substituted(prepared_case):
    args = prepared_case.args
    for key, value in (
        ("status", "MATCHED"),
        ("source_sha256", "0" * 64),
        ("physical_authority", True),
    ):
        with pytest.raises(m.UsbRebootPreparationError):
            m.build_usb_reboot_preparation(
                **dict(
                    args, runtime_report=dict(args["runtime_report"], **{key: value})
                )
            )
    for key, value in (
        ("sha256", "0" * 64),
        ("bytes", 0),
        ("bytes", True),
        ("path", "arbitrary-helper.exe"),
    ):
        report = deepcopy(args["runtime_report"])
        report["files"][0][key] = value
        with pytest.raises(m.UsbRebootPreparationError):
            m.build_usb_reboot_preparation(**dict(args, runtime_report=report))
    for permit in (None, prepared_case.subject.permit):
        with pytest.raises(m.UsbRebootPreparationError):
            m.build_usb_reboot_preparation(**dict(args, reconnect_permit=permit))


def test_reissued_old_metadata_ids_cannot_become_new_publications(prepared_case):
    args = prepared_case.args
    native = json.loads(args["enrollment"])
    _, current_ids = enrollment_subjects(native)
    prior = [
        json.loads(args["original_baseline"]["baseline_sources"]["native_enrollment"]),
        json.loads(args["reconnect_sources"]["native_enrollment"]),
    ]
    for historical in prior:
        _, ids = enrollment_subjects(historical)
        for index, old_id in enumerate(ids):
            changed_ids = list(current_ids)
            changed_ids[index] = old_id
            new_native = reissue_enrollment(native, changed_ids)
            enrollment = canonical(new_native)
            documents, fresh_ids = enrollment_subjects(new_native)
            ledger = deepcopy(args["acquisition_ledger"])
            for row, doc, fresh_id in zip(ledger["entries"], documents, fresh_ids):
                row.update(
                    document_sha256=digest(canonical(doc)), operation_id=fresh_id
                )
            binding = args["original_baseline"]["plan"].to_dict()["binding"]
            selection = m.selection_from_enrollment_snapshot(
                new_native,
                source_sha256=binding["source_sha256"],
                launch_session_id=ledger["launch_session_id"],
            )
            operation = campaign.usb_identity_phase_operation(
                plan=args["original_baseline"]["plan"],
                phase="AFTER_REBOOT",
                operation_id=args["phase_id"],
                predecessor_sha256=args["reconnect"].sha256,
                selection=selection,
                runtime=registration.UsbIdentityRuntimeRegistration(
                    canonical(args["operation"].to_dict()["runtime"])
                ),
                policy=campaign.usb_identity_stage_policy(),
            )
            with pytest.raises(m.UsbRebootPreparationError):
                m.build_usb_reboot_preparation(
                    **dict(
                        args,
                        enrollment=enrollment,
                        enrollment_reference=reference(
                            enrollment, "MODELED-reboot-reissued-enrollment"
                        ),
                        acquisition_ledger=ledger,
                        operation=operation,
                    )
                )


def modeled_v12(predecessor):
    """Owner-shaped data, NOT an original reader or journal-authenticated v12.

    The five reconnect phase source subjects are exact actual-codec fixtures.
    Additional stage packages and admission-log membership are explicitly
    modeled, because this adapter's caller is responsible for authenticating
    that surrounding store before calling it.
    """
    workflow = modeled_owner_projection(predecessor.seed)
    workflow["schema"] = "rocell.physical_camera_source_workflow_readback.v12"
    reconnect = predecessor.reconnect
    refs = {row["role"]: row["reference"] for row in reconnect.to_dict()["records"]}

    def record(payload, ref):
        return dict(
            document=json.loads(payload),
            evidence_sha256=digest(payload),
            reference=ref.to_dict() if hasattr(ref, "to_dict") else ref,
            retention="M1_FULL_BYTES_READ_BACK",
        )

    phase_row = dict(
        phase="AFTER_RECONNECT",
        state="RETAINED_BLOCKED",
        phase_id=reconnect.to_dict()["context"]["operation_id"],
    )
    for source, stored in (
        ("operation", "operation"),
        ("operator_event", "operator_event"),
        ("native_enrollment", "enrollment"),
        ("owned_usb_run", "execution"),
        ("host_boot", "host_boot"),
    ):
        phase_row[stored] = record(predecessor.seed.sources[source], refs[source])
    phase_row["phase_record"] = record(
        reconnect.payload, reference(reconnect.payload, "MODELED-adapter-reconnect")
    )
    for role in m.USB_RECONNECT_ROLE_BYTES:
        if role not in phase_row:
            payload = canonical({"MODELED_PREVIOUS_OWNER_PACKAGE": role})
            phase_row[role] = record(
                payload, reference(payload, "MODELED-adapter-" + role)
            )
    run, permit = predecessor.seed.run, predecessor.seed.permit
    counts = run.bounded_effect_summary()["actual_counts"]
    receipt = WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        permit.registration.worker_executable_sha256,
        permit.admission.selected_identity_sha256,
        EffectCertainty.CONFIRMED,
        True,
        ObservedPowerState.UNKNOWN,
        counts["hub_open_attempts"],
        counts["api_calls"] - counts["hub_open_attempts"] - counts["close_attempts"],
        0,
        0,
        counts["close_attempts"],
        len(run.payload),
        (run.sha256,),
        predecessor.seed.campaign.composition,
    )
    result = AttemptResult(
        permit.attempt_id,
        AttemptState.SEALED_KNOWN,
        permit.permit_sha256,
        (),
        receipt,
        False,
        receipt.composition,
    )
    phase_row["original_campaign"] = json.loads(
        canonical(
            dict(
                permit=asdict(permit),
                result=asdict(result),
                admission_evidence={"MODELED_ONLY": True},
                evidence=run.to_dict(),
                evidence_sha256=run.sha256,
                reference=dict(
                    schema="rocell.usb_identity_campaign_reference.v1",
                    cell_id=permit.request.cell_id,
                    session_id=permit.request.session_id,
                    attempt_id=permit.attempt_id,
                    permit_sha256=permit.permit_sha256,
                    evidence_sha256=run.sha256,
                    payload_bytes=len(run.payload),
                    label="physical-native-usb-identity",
                ),
                retention="M1_FULL_BYTES_READ_BACK",
            )
        )
    )
    workflow["usb_qualification_reconnect"] = phase_row
    return workflow


def test_owner_adapter_reconstructs_complete_v12_without_files(
    predecessor, monkeypatch
):
    original = modeled_v12(predecessor)
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("adapter read a file")
    )
    args = m.original_usb_reboot_predecessor(original, received=predecessor.received)
    assert len(args) == 9
    assert args["reconnect"].payload == predecessor.reconnect.payload
    assert args["reconnect_sources"] == predecessor.seed.sources
    assert args["reconnect_permit"] == predecessor.seed.permit
    assert (
        phase.verify_usb_reboot_predecessor(**args).payload
        == predecessor.reconnect.payload
    )


def test_owner_adapter_refuses_partial_unknown_quarantined_or_swapped_originals(
    predecessor,
):
    original = modeled_v12(predecessor)
    vectors = [
        (("schema",), "rocell.physical_camera_source_workflow_readback.v11"),
        (("usb_qualification_reconnect", "state"), "ORIGINAL_CAMPAIGN_HELD"),
        (
            ("usb_qualification_reconnect", "original_campaign", "result", "state"),
            "SEALED_UNCERTAIN",
        ),
        (
            (
                "usb_qualification_reconnect",
                "original_campaign",
                "result",
                "quarantine_latched",
            ),
            True,
        ),
        (
            ("usb_qualification_reconnect", "original_campaign", "result", "receipt"),
            None,
        ),
        (
            (
                "usb_qualification_reconnect",
                "original_campaign",
                "result",
                "receipt",
                "reads",
            ),
            0,
        ),
        (
            (
                "usb_qualification_reconnect",
                "original_campaign",
                "result",
                "receipt",
                "writes",
            ),
            1,
        ),
        (
            (
                "usb_qualification_reconnect",
                "original_campaign",
                "result",
                "receipt",
                "cleanup_confirmed",
            ),
            1,
        ),
        (
            (
                "usb_qualification_reconnect",
                "original_campaign",
                "permit",
                "attempt_id",
            ),
            "attempt-" + "a" * 32,
        ),
        (
            ("usb_qualification_reconnect", "original_campaign", "evidence_sha256"),
            "0" * 64,
        ),
        (
            (
                "usb_qualification_reconnect",
                "original_campaign",
                "reference",
                "payload_bytes",
            ),
            1,
        ),
        (("usb_qualification_reconnect", "execution", "retention"), "CACHED_ONLY"),
        (
            (
                "usb_qualification_reconnect",
                "operation",
                "reference",
                "manifest_sha256",
            ),
            "0" * 64,
        ),
    ]
    for path, value in vectors:
        changed = deepcopy(original)
        target = changed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        with pytest.raises(
            m.UsbRebootPreparationError, match="USB_REBOOT_PREDECESSOR_INVALID"
        ):
            m.original_usb_reboot_predecessor(changed, received=predecessor.received)
