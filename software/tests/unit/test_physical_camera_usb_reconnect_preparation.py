"""Pure reconnect preparation; observations, references and log entries MODELED.

Actual closed enrollment/phase codecs are exercised. No original-store trust,
native process, CIM, USB, camera or arm observation is claimed by these tests.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import builtins
import io
import json
import os
import subprocess

import pytest

from rocell.application import physical_camera_usb_reconnect as m
from rocell.application import physical_onboarding_v2 as journal
from rocell.application import physical_usb_identity_campaign as campaign
from rocell.application.physical_camera_selection import (
    selection_from_enrollment_snapshot,
)
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
    verify_native_camera_enrollment_snapshot,
)
from rocell.arm.serial_transport import SerialTransport
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.owned_usb_identity_runner import OwnedUsbIdentityRunner
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from test_physical_received_camera import prerequisites, workspace
from test_physical_camera_usb_qualification import reference
from test_physical_usb_reconnect_phase import reconnect_fixture


@pytest.fixture(autouse=True)
def no_production_acquisition(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure reconnect preparation attempted production acquisition")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(host, "_system_powershell", forbidden)
    monkeypatch.setattr(host, "_native_owner", forbidden)
    monkeypatch.setattr(OwnedUsbIdentityRunner, "run", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)


def runtime_report(runtime):
    """Same fixed-roster modeled report as the baseline preparation fixture.

    This is not an inspection: literal pinned names/hashes are fixture inputs.
    The preparation codec must still reject any different roster or runtime.
    """
    data = runtime.to_dict()
    return dict(
        schema="rocell.usb_identity_runtime_file_check.v1",
        runtime_registration_sha256=runtime.sha256,
        source_sha256=data["source_sha256"],
        status="FILES_MATCHED",
        files=[
            {"path": path, "sha256": sha, "bytes": 1}
            for path, sha, _ in (
                *registration.FIXED_SOURCE_PINS,
                (
                    registration.BUILD_RECORD_PATH,
                    registration.BUILD_RECORD_SHA256,
                    32768,
                ),
                (data["helper"]["path"], data["helper"]["sha256"], 1048576),
            )
        ],
        physical_authority=False,
        hardware_qualified=False,
    )


def enrollment_subjects(native):
    return (
        native["generic_review"]["inventory_report"],
        native["inventory_packet"],
        native["identity_packet"],
    ), (
        native["generic_review"]["operation_id"],
        native["view"]["inventory_operation_id"],
        native["view"]["identity"]["operation_id"],
    )


def preparation_inputs(
    *,
    original_baseline,
    absence,
    absence_sources,
    operator_event,
    operation,
    enrollment
):
    plan = original_baseline["plan"]
    binding, report = plan.to_dict()["binding"], operator_event.to_dict()
    phase_id = report["phase_id"]
    absence_ref = reference(absence.payload, "MODELED-reconnect-absence")
    start = journal.V2JournalEvent(
        session_id=binding["session_id"],
        session_header_sha256=binding["header_sha256"],
        sequence=80,
        stage=m._STAGE,
        previous_state=journal.V2StageState.BLOCKED,
        state=journal.V2StageState.WAITING_OPERATOR,
        occurred_at_ns=report["phase_started_at_utc_ns"],
        previous_event_sha256="a" * 64,
        evidence=(absence_ref,),
        detail_code=m.usb_reconnect_event("PREPARATION_REQUESTED", phase_id),
        event_sha256="0" * 64,
    )
    start = replace(start, event_sha256=journal._stable_hash(start.core_dict()))
    native = json.loads(enrollment)
    documents, ids = enrollment_subjects(native)
    now = report["reported_at_utc_ns"]
    ledger = dict(
        schema="rocell.usb_phase_metadata_acquisition_ledger.v1",
        source_sha256=binding["source_sha256"],
        session_id=binding["session_id"],
        launch_session_id=report["launch_session_id"],
        trial_id=binding["trial_id"],
        phase_id=phase_id,
        phase_started_at_utc_ns=start.occurred_at_ns,
        entries=[
            dict(
                role=role,
                action_id=action,
                operation_id=operation_id,
                started_at_utc_ns=now + index * 10 + 1,
                finished_at_utc_ns=now + index * 10 + 2,
                published_at_utc_ns=now + index * 10 + 3,
                document_sha256=digest(canonical(document)),
                result_sha256=digest(canonical({"MODELED_COMPLETED_RESULT": index})),
                completion_logged=True,
            )
            for index, ((role, action), document, operation_id) in enumerate(
                zip(m._ACQUISITIONS, documents, ids)
            )
        ],
    )
    runtime = registration.UsbIdentityRuntimeRegistration(
        canonical(operation.to_dict()["runtime"])
    )
    return dict(
        original_baseline=original_baseline,
        absence=absence,
        absence_sources=absence_sources,
        absence_reference=absence_ref,
        phase_start_event=start,
        phase_id=phase_id,
        operator_event=operator_event,
        operator_event_reference=reference(
            operator_event.payload, "MODELED-reconnect-report"
        ),
        enrollment=enrollment,
        enrollment_reference=reference(enrollment, "MODELED-reconnect-enrollment"),
        acquisition_ledger=ledger,
        operation=operation,
        runtime_report=runtime_report(runtime),
        prepared_at_utc_ns=now + 100,
        operator_id=report["operator_id"],
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
    return m.verify_usb_reconnect_preparation(
        prepared.payload, expected_sha256=prepared.sha256, **originals
    )


def changed(document, path, value):
    result = deepcopy(document)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return result


def refused(label, function):
    try:
        function()
    except ValueError:
        return
    pytest.fail("Malformed reconnect preparation accepted: " + label)


def reissue_enrollment(native, ids):
    """Actual owners issue modeled metadata with explicit different operation IDs."""
    provenance = native["view"]["provenance"]
    generic = WizardDeviceSelection(
        provenance["mode"], provenance["session_id"], provenance["source_sha256"]
    )
    generic.ingest(native["generic_review"]["inventory_report"], operation_id=ids[0])
    generic.review(generic.choices("CAMERA")[0]["value"], "CAMERA", "MODELED-reviewer")
    owner = WizardNativeCameraEnrollment(
        provenance["mode"],
        provenance["session_id"],
        provenance["source_sha256"],
        {
            "provenance": provenance["provider_provenance"],
            "helper_sha256": provenance["helper_sha256"],
        },
    )
    owner.ingest_inventory(
        native["inventory_packet"],
        operation_id=ids[1],
        generic_review=generic.reviewed_candidate("CAMERA"),
    )
    choice = owner.choices()[0]["value"]
    owner.retain_identity(choice, native["identity_packet"], operation_id=ids[2])
    owner.review(choice, "MODELED-endpoint-reviewer")
    return owner.export_snapshot()


def replace_enrollment(args, native):
    """Bind every affected argument, so a rejection is not just a stale hash."""
    result = deepcopy(args)
    raw = canonical(native)
    documents, ids = enrollment_subjects(native)
    result.update(
        enrollment=raw,
        enrollment_reference=reference(raw, "MODELED-reconnect-enrollment"),
    )
    for row, document, operation_id in zip(
        result["acquisition_ledger"]["entries"], documents, ids
    ):
        row.update(
            document_sha256=digest(canonical(document)), operation_id=operation_id
        )
    plan = args["original_baseline"]["plan"]
    selection = selection_from_enrollment_snapshot(
        native,
        source_sha256=plan.to_dict()["binding"]["source_sha256"],
        launch_session_id=args["acquisition_ledger"]["launch_session_id"],
    )
    result["operation"] = campaign.usb_identity_phase_operation(
        plan=plan,
        phase="AFTER_RECONNECT",
        operation_id=args["phase_id"],
        predecessor_sha256=args["absence"].sha256,
        selection=selection,
        runtime=registration.UsbIdentityRuntimeRegistration(
            canonical(args["operation"].to_dict()["runtime"])
        ),
        policy=campaign.usb_identity_stage_policy(),
    )
    return result


@pytest.fixture
def prepared_case(prerequisites):
    subject = reconnect_fixture(prerequisites)
    args = preparation_inputs(
        original_baseline=subject.original_baseline,
        absence=subject.absence,
        absence_sources=subject.absence_sources,
        operator_event=subject.event,
        operation=subject.operation,
        enrollment=subject.sources["native_enrollment"],
    )
    return args, m.build_usb_reconnect_preparation(**args)


def test_complete_current_logged_preparation_is_detached_bounded_and_inert(
    prepared_case, monkeypatch
):
    args, prepared = prepared_case

    def no_files(*unused, **ignored):
        pytest.fail("Pure preparation accessed a file or device handle")

    # Fixture setup reads source prerequisites. Building/reconstructing the
    # resulting pure subjects must not read even those files again.
    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", no_files)
        guard.setattr(io, "open", no_files)
        guard.setattr(os, "open", no_files)
        rebuilt = m.build_usb_reconnect_preparation(**args)
        checked = verify(prepared, args)
    assert rebuilt.payload == checked.payload == prepared.payload
    assert prepared.sha256 == digest(prepared.payload)
    assert len(prepared.payload) <= m.USB_RECONNECT_ROLE_BYTES["preparation"]
    data = prepared.to_dict()
    assert data["meaning"] == m.MEANING
    assert all(data[name] is False for name in m.FLAGS)
    assert data["absence_sha256"] == args["absence"].sha256
    assert data["operation_sha256"] == args["operation"].sha256
    documents, ids = enrollment_subjects(json.loads(args["enrollment"]))
    assert len(set(ids)) == 3
    report_time = data["operator_event"]["reported_at_utc_ns"]
    assert report_time > data["phase_start_event"]["occurred_at_ns"]
    for row, document, operation_id in zip(
        data["acquisition_ledger"]["entries"], documents, ids
    ):
        assert row["started_at_utc_ns"] > report_time
        assert row["completion_logged"] is True
        assert row["document_sha256"] == digest(canonical(document))
        assert row["operation_id"] == operation_id
    with pytest.raises(FrozenInstanceError):
        prepared.payload = b"changed"
    data["acquisition_ledger"]["entries"][0]["document_sha256"] = "f" * 64
    assert prepared.to_dict() != data
    # Exact original verification never replaces opaque choice IDs or packets.
    checked_native = verify_native_camera_enrollment_snapshot(
        json.loads(args["enrollment"]),
        source_sha256=data["acquisition_ledger"]["source_sha256"],
        launch_session_id=data["acquisition_ledger"]["launch_session_id"],
    )
    assert canonical(checked_native) == args["enrollment"]


def test_closed_ledger_refuses_old_unlogged_reordered_or_impossible_acquisitions(
    prepared_case,
):
    _, prepared = prepared_case
    data = prepared.to_dict()
    path = ("acquisition_ledger",)
    entry = (*path, "entries")
    start = data["phase_start_event"]["occurred_at_ns"]
    report = data["operator_event"]["reported_at_utc_ns"]
    entries = data["acquisition_ledger"]["entries"]
    changes = [
        ("pre-Begin", (*entry, 0, "started_at_utc_ns"), start - 1),
        ("pre-report", (*entry, 0, "started_at_utc_ns"), report - 1),
        ("wrong-source", (*path, "source_sha256"), "f" * 64),
        ("wrong-session", (*path, "session_id"), "MODELED-other-original"),
        ("old-launch", (*path, "launch_session_id"), "MODELED-old-launch"),
        ("wrong-trial", (*path, "trial_id"), "usbtrial-" + "f" * 32),
        ("wrong-phase", (*path, "phase_id"), "usbphase-" + "f" * 32),
        ("retimestamped-start", (*path, "phase_started_at_utc_ns"), start + 1),
        ("unlogged", (*entry, 1, "completion_logged"), False),
        ("Boolean-not-integer", (*entry, 0, "started_at_utc_ns"), True),
        ("integer-not-logged", (*entry, 0, "completion_logged"), 1),
        ("reordered", entry, list(reversed(entries))),
        ("missing-acquisition", entry, entries[:2]),
        ("extra-acquisition", entry, [*entries, entries[0]]),
        ("wrong-action", (*entry, 1, "action_id"), "inventory_devices"),
        ("wrong-role", (*entry, 1, "role"), "GENERIC_INVENTORY"),
        ("same-ID", (*entry, 1, "operation_id"), entries[0]["operation_id"]),
        ("phase-ID-alias", (*entry, 1, "operation_id"), data["phase_id"]),
        (
            "overlapping-acquisitions",
            (*entry, 1, "started_at_utc_ns"),
            entries[0]["published_at_utc_ns"] - 1,
        ),
        ("finished-before-start", (*entry, 0, "finished_at_utc_ns"), report),
        ("publication-before-finish", (*entry, 0, "published_at_utc_ns"), report),
        (
            "publication-after-preparation",
            (*entry, 2, "published_at_utc_ns"),
            data["prepared_at_utc_ns"] + 1,
        ),
        ("malformed-result-hash", (*entry, 2, "result_sha256"), "unknown"),
        ("uppercase-document-hash", (*entry, 2, "document_sha256"), "A" * 64),
        ("caller-authority", (*path, "physical_authority"), True),
        ("caller-query", (*entry, 0, "query"), "caller-provided query"),
    ]
    for label, where, value in changes:
        raw = canonical(changed(data, where, value))
        refused(label, lambda: m.UsbReconnectPreparation(raw))


def test_preparation_refuses_aliased_refs_bad_runtime_and_forged_authority(
    prepared_case,
):
    _, prepared = prepared_case
    data = prepared.to_dict()
    mutations = [
        ("unknown-field", ("unexpected",), False),
        ("wrong-meaning", ("meaning",), "CAMERA_CAPTURE_ALLOWED"),
        ("wrong-source-files", ("runtime_report", "source_sha256"), "f" * 64),
        ("wrong-runtime", ("runtime_report", "runtime_registration_sha256"), "f" * 64),
        ("unverified-files", ("runtime_report", "status"), "NOT_INSPECTED"),
        (
            "file-row-removed",
            ("runtime_report", "files"),
            data["runtime_report"]["files"][:-1],
        ),
        (
            "file-row-reordered",
            ("runtime_report", "files"),
            list(reversed(data["runtime_report"]["files"])),
        ),
        ("wrong-helper-bytes", ("runtime_report", "files", -1, "sha256"), "f" * 64),
        ("zero-size", ("runtime_report", "files", 0, "bytes"), 0),
        ("Boolean-size", ("runtime_report", "files", 0, "bytes"), True),
        ("oversized-helper", ("runtime_report", "files", -1, "bytes"), 1048577),
        ("wrong-operation-hash", ("operation_sha256",), "f" * 64),
        ("operator-mismatch", ("operator_id",), "MODELED-other-operator"),
        ("plan-ref-hash", ("plan_reference", "payload_sha256"), "f" * 64),
        ("absence-ref-hash", ("absence_reference", "payload_sha256"), "f" * 64),
        ("report-ref-size", ("operator_event_reference", "payload_bytes"), 1),
        ("enrollment-ref-hash", ("enrollment_reference", "payload_sha256"), "f" * 64),
        (
            "ref-alias",
            ("enrollment_reference", "evidence_id"),
            data["plan_reference"]["evidence_id"],
        ),
        ("ref-stage", ("enrollment_reference", "stage"), "camera_receipt"),
    ]
    for flag in m.FLAGS:
        mutations.extend((flag, (flag,), value) for value in (True, 0, None))
    for label, path, value in mutations:
        raw = canonical(changed(data, path, value))
        refused(label, lambda: m.UsbReconnectPreparation(raw))


def test_rehashed_ledger_documents_and_operation_ids_require_exact_originals(
    prepared_case,
):
    args, prepared = prepared_case
    data = prepared.to_dict()
    for index in range(3):
        for key, replacement in (
            ("document_sha256", digest(canonical({"MODELED_WRONG_DOCUMENT": index}))),
            ("operation_id", "MODELED-unrelated-operation-" + str(index)),
        ):
            altered = changed(
                data, ("acquisition_ledger", "entries", index, key), replacement
            )
            # Closed canonical syntax alone can carry an unsupported assertion.
            checked = m.UsbReconnectPreparation(canonical(altered))
            assert checked.sha256 != prepared.sha256
            refused("rehashed-" + key, lambda: verify(checked, args))
    refused(
        "wrong-external-hash",
        lambda: m.verify_usb_reconnect_preparation(
            prepared.payload,
            expected_sha256="f" * 64,
            **{
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
            },
        ),
    )


def test_retimestamped_baseline_acquisitions_cannot_become_reconnect(prepared_case):
    args, _ = prepared_case
    native = json.loads(args["enrollment"])
    _, current_ids = enrollment_subjects(native)
    _, baseline_ids = enrollment_subjects(
        json.loads(args["original_baseline"]["baseline_sources"]["native_enrollment"])
    )
    assert set(current_ids).isdisjoint(baseline_ids)
    # Each altered input is rebuilt by the actual enrollment/selection/operation
    # producers. All hashes, source/launch bindings and ledger times match.
    forbidden_ids = [
        *enumerate(baseline_ids),
        (0, args["original_baseline"]["baseline"].to_dict()["context"]["operation_id"]),
        (1, args["absence"].to_dict()["context"]["operation_id"]),
    ]
    for index, previous_id in forbidden_ids:
        ids = list(current_ids)
        ids[index] = previous_id
        recycled = replace_enrollment(args, reissue_enrollment(native, ids))
        assert all(
            row["started_at_utc_ns"]
            > args["operator_event"].to_dict()["reported_at_utc_ns"]
            for row in recycled["acquisition_ledger"]["entries"]
        )
        refused(
            "old-baseline-or-predecessor-ID",
            lambda: m.build_usb_reconnect_preparation(**recycled),
        )


def test_independently_supplied_references_events_and_enrollment_cannot_be_substituted(
    prepared_case,
):
    args, prepared = prepared_case
    for name in (
        "absence_reference",
        "operator_event_reference",
        "enrollment_reference",
    ):
        ref = args[name]
        # Even a syntactically valid reference to identical bytes is a different
        # supplied original subject and cannot replace the retained reference.
        altered = replace(
            ref, evidence_id="evidence-" + "f" * 64, package_sha256="f" * 64
        )
        refused(
            "different-original-" + name,
            lambda: verify(prepared, args, **{name: altered}),
        )
    event = args["phase_start_event"]
    event = replace(event, previous_event_sha256="f" * 64)
    event = replace(event, event_sha256=journal._stable_hash(event.core_dict()))
    refused(
        "different-original-event",
        lambda: verify(prepared, args, phase_start_event=event),
    )
    sources = dict(args["absence_sources"])
    sources["host_boot"] += b" "
    refused(
        "different-absence-original",
        lambda: verify(prepared, args, absence_sources=sources),
    )
    refused(
        "untyped-absence",
        lambda: verify(prepared, args, absence=args["absence"].to_dict()),
    )
    native = json.loads(args["enrollment"])
    _, ids = enrollment_subjects(native)
    other = reissue_enrollment(native, ids)
    selection_mismatch = replace_enrollment(args, other)
    selection_mismatch["operation"] = args["operation"]
    refused(
        "different-selection",
        lambda: m.build_usb_reconnect_preparation(**selection_mismatch),
    )
    wrong_launch = deepcopy(native)
    wrong_launch["view"]["provenance"]["session_id"] = "MODELED-old-launch"
    raw = canonical(wrong_launch)
    swapped = dict(
        args,
        enrollment=raw,
        enrollment_reference=reference(raw, "MODELED-other-native"),
    )
    refused(
        "old-launch-enrollment", lambda: m.build_usb_reconnect_preparation(**swapped)
    )
