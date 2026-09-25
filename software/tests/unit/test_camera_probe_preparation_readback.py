"""Full original v16 composition using MODELED storage and device observations.

Every historical subject verifier runs on the unchanged journal. This is not
received-hardware evidence, actual M1 storage qualification or device admission.
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import camera_probe_preparation_readback as reader
from rocell.application import physical_camera_mode_entry_readback as mode_reader
from rocell.application.camera_activation_runtime_policy import (
    REVIEW_SCHEMA,
    reviewed_activation_runtime_candidate,
)
from rocell.application.camera_probe_preparation import (
    SOURCE_WORKFLOW_PROBE_SCHEMA,
    build_camera_probe_preparation,
    build_camera_probe_preparation_review,
    camera_probe_event,
    camera_probe_label,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.physical_camera_mode_entry import (
    build_camera_mode_entry,
    camera_mode_entry_event,
    camera_mode_entry_label,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState as S
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_camera_mode_entry_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    complete_subjects,
    refresh_read,
    change_last_event,
    ENTRY_LAUNCH,
    ENTRY_ID,
)
from test_windows_camera_driver_metadata import driver_fixture


PROBE_LAUNCH = "wizard-" + "8" * 32


def current_enrollment(previous, *, source, launch=PROBE_LAUNCH):
    """Produce fresh modeled metadata, never relabel the retained snapshot."""
    packet = deepcopy(previous["identity_packet"])
    before = packet["receipt"]
    fresh = driver_fixture()
    fresh["requested_endpoint"] = before["requested_endpoint"]
    fresh["mapping"]["interface_path"] = before["mapping"]["interface_path"]
    fresh["device"] = deepcopy(before["device"])
    if before.get("driver") is not None:
        for key in ("provider", "service", "version", "inf_path"):
            if before["driver"][key]["availability"] == "OBSERVED":
                fresh["driver"][key] = deepcopy(before["driver"][key])
    packet["receipt"] = fresh
    generic = WizardDeviceSelection("physical", launch, source)
    generic.ingest(
        previous["generic_review"]["inventory_report"],
        operation_id="MODELED-probe-generic-inventory",
    )
    generic.review(
        generic.choices("CAMERA")[0]["value"], "CAMERA", "MODELED-probe-reviewer"
    )
    owner = WizardNativeCameraEnrollment(
        "physical",
        launch,
        source,
        {key: packet[key] for key in ("provenance", "helper_sha256")},
    )
    owner.ingest_inventory(
        previous["inventory_packet"],
        operation_id="MODELED-probe-native-inventory",
        generic_review=generic.reviewed_candidate("CAMERA"),
    )
    choice = owner.choices()[0]["value"]
    owner.retain_identity(choice, packet, operation_id="MODELED-probe-native-identity")
    owner.review(choice, "MODELED-probe-reviewer")
    return owner


def prepared_subject(original, bound, *, previous=None, return_enrollment=False):
    workspace, source = Path(bound["workspace"]), bound["source_sha256"]
    enrollment = current_enrollment(
        previous or original["usb_qualification_reboot"]["enrollment"]["document"],
        source=source,
    )
    runtime = reviewed_activation_runtime_candidate(
        workspace, purpose="probe", source_sha256=source
    )
    plan = PhysicalCameraActivationCampaign.from_enrollment(
        workspace,
        Path(bound["directory"]) / "native-camera-output",
        enrollment=enrollment,
        launch_session_id=PROBE_LAUNCH,
        source_sha256=source,
        cell_id=bound["cell_id"],
        session_id=bound["session_id"],
        runtime=runtime,
    ).plan()
    software = {}
    for purpose in ("probe", "capture"):
        candidate = reviewed_activation_runtime_candidate(
            workspace, purpose=purpose, source_sha256=source
        )
        software[purpose] = dict(
            schema=REVIEW_SCHEMA,
            status="REVIEWED_SOFTWARE_MATCHED",
            purpose=purpose,
            runtime_registration_sha256=candidate.registration_sha256,
            catalog_sha256=candidate.to_dict()["catalog_sha256"],
            source_sha256=source,
            files_checked=26,
            bytes_read=123456,
            read_calls=53,
            elapsed_ns=1_000_000,
            original_context_authenticated=False,
            physical_authority=False,
            connected=False,
            hardware_qualified=False,
            device_operations=0,
        )
    entry = original["camera_mode_entry"]
    preparation = build_camera_probe_preparation(
        preparation_id="cameraprobe-" + "2" * 32,
        entry_sha256=entry["entry"]["evidence_sha256"],
        entry_event_sha256=entry["events"][0]["event_sha256"],
        plan=plan,
        enrollment=enrollment.export_snapshot(),
        software=software,
        operator_id="MODELED-probe-preparer",
        prepared_at_utc_ns=entry["events"][0]["occurred_at_ns"] + 1,
    )
    return (preparation, enrollment) if return_enrollment else preparation


def enter(case, monkeypatch):
    complete_subjects(case, monkeypatch)
    original = refresh_read(case)
    state = case[2]
    now = state["snapshot"]().committed_events[-1].occurred_at_ns + 1
    entry = build_camera_mode_entry(
        entry_id=ENTRY_ID,
        binding=mode_reader.camera_mode_entry_binding(
            original, entry_launch_id=ENTRY_LAUNCH
        ),
        operator_id="MODELED-operator",
        recorded_at_utc_ns=now,
    )
    ref = state["add"](
        entry.payload, label=camera_mode_entry_label(ENTRY_ID), stage=STAGE_ORDER[4]
    )
    state["advance"](
        S.WAITING_OPERATOR,
        camera_mode_entry_event(ENTRY_ID),
        (ref,),
        stage=STAGE_ORDER[4],
    )
    change_last_event(state, occurred_at_ns=now + 1)
    return refresh_read(case)


def prepare_reviewed(case, monkeypatch, *, return_enrollment=False):
    """Append real v16 subjects to the full MODELED immutable history."""
    entered = enter(case, monkeypatch)
    bound, state = case[0].descriptor(), case[2]
    prep, enrollment = prepared_subject(entered, bound, return_enrollment=True)
    now = prep.to_dict()["prepared_at_utc_ns"]
    prep_ref = state["add"](
        prep.payload,
        label=camera_probe_label("preparation", prep.to_dict()["preparation_id"]),
        stage=STAGE_ORDER[4],
    )
    state["advance"](
        S.BLOCKED,
        camera_probe_event("PREPARED", prep.to_dict()["preparation_id"]),
        (prep_ref,),
        stage=STAGE_ORDER[4],
    )
    change_last_event(state, occurred_at_ns=now + 1)
    review = build_camera_probe_preparation_review(
        prep, reviewer_id="MODELED-probe-reviewer", reviewed_at_utc_ns=now + 2
    )
    review_ref = state["add"](
        review.payload,
        label=camera_probe_label("review", prep.to_dict()["preparation_id"]),
        stage=STAGE_ORDER[4],
    )
    refs = tuple(sorted((prep_ref, review_ref), key=lambda ref: ref.evidence_id))
    state["advance"](
        S.WAITING_OPERATOR,
        camera_probe_event("REVIEWED", prep.to_dict()["preparation_id"]),
        refs,
        stage=STAGE_ORDER[4],
    )
    change_last_event(state, occurred_at_ns=now + 3)
    return (
        (entered, prep, review, enrollment)
        if return_enrollment
        else (entered, prep, review)
    )


def test_full_original_predecessor_is_reverified_on_the_same_complete_snapshot(
    ready, monkeypatch
):
    entered, prep, review = prepare_reviewed(ready, monkeypatch)
    bound, state = ready[0].descriptor(), ready[2]

    captured, verify = [], reader._verify_camera_mode_entry_prefix
    original_calls, verify_original = [], session._verify_original_source_roles

    def capture(*args, **kwargs):
        captured.append((args, kwargs))
        return verify(*args, **kwargs)

    monkeypatch.setattr(reader, "_verify_camera_mode_entry_prefix", capture)

    def capture_original(*args, **kwargs):
        original_calls.append((args, kwargs))
        return verify_original(*args, **kwargs)

    monkeypatch.setattr(session, "_verify_original_source_roles", capture_original)
    before = deepcopy(state["snapshot"]())
    workflow = refresh_read(ready)
    assert workflow["schema"] == SOURCE_WORKFLOW_PROBE_SCHEMA
    row = workflow["camera_probe_preparation"]
    assert row["state"] == "REVIEWED_FOR_ADMISSION"
    assert row["preparation"]["document"] == prep.to_dict()
    assert row["review"]["document"] == review.to_dict()
    assert state["snapshot"]() == before == captured[-1][0][1]
    changing_envelope = {
        "schema",
        "session_head_sha256",
        "evidence_inventory_sha256",
        "camera_probe_preparation",
    }
    assert workflow["session_head_sha256"] == before.head.head_sha256
    assert workflow["evidence_inventory_sha256"] == session.canonical_sha256(
        [ref.to_dict() for ref in before.evidence]
    )
    assert {
        key: value for key, value in workflow.items() if key not in changing_envelope
    } == {key: value for key, value in entered.items() if key not in changing_envelope}
    assert session._decode_cached_source_workflow(canonical(workflow)) == workflow
    args, kwargs = captured[-1]
    # The old public layout cannot ignore the appended inventory or journal.
    with pytest.raises(ValueError):
        mode_reader.read_camera_mode_entry_layout(
            before,
            {
                args[-1].mode_entry.reference.evidence_id: dict(
                    entry_id=ENTRY_ID, record=entered["camera_mode_entry"]["entry"]
                )
            },
        )
    # Initial prerequisites are verified by Session before the suffix reader.
    # Exercise that actual entrypoint, not an inner helper that receives roles
    # which its caller has already authenticated.
    root_args, root_kwargs = original_calls[-1]
    broken = list(root_args)
    broken[3] = deepcopy(broken[3])
    broken[3]["prerequisites"]["document"]["source_sha256"] = "e" * 64
    with pytest.raises(
        session.PhysicalCameraSessionError, match="CAMERA_SESSION_SOURCE_WORKFLOW_CHAIN"
    ):
        verify_original(*broken, **root_kwargs)
    # Independent context comparisons are distinct from shape validation. These
    # mutations intentionally model a faulty owner, not valid original inputs.
    for fault in (
        "workspace",
        "source_sha256",
        "cell_id",
        "session_id",
        "assigned_parent_directory",
        "entry_sha256",
        "entry_event_sha256",
    ):
        data = prep.to_dict()
        target = data if fault.startswith("entry_") else data["plan"]
        target[fault] = "MODELED changed context"
        modeled_layout = SimpleNamespace(
            preparation=SimpleNamespace(to_dict=lambda: deepcopy(data))
        )
        with pytest.raises(reader.CameraProbeOriginalError):
            reader._verify_current_subject_context(entered, modeled_layout, bound)
    reused = deepcopy(entered)
    reused["MODELED_reused_operation"] = {
        "inventory_operation_id": "MODELED-probe-native-inventory"
    }
    with pytest.raises(reader.CameraProbeOriginalError):
        reader._verify_current_subject_context(reused, args[-1], bound)
