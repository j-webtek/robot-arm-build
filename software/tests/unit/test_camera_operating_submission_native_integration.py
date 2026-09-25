"""Three actual M1 native attempts, synthetic pixels and fresh original reading.

Stage-prefix semantics, admission facts, source identity and runtime approval
are explicitly MODELED. The real dispatcher, coordinator, native protocol parser,
accounting, M1/NTFS storage, stage-submission service and native reader run unchanged. The incapable
owner cannot create a process or access hardware. This is not full-history or
physical acceptance, and it does not add a production test/override interface.
"""

from dataclasses import asdict
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from time import monotonic

import pytest

from rocell.application import camera_operating_submission_native as reader
from rocell.application import camera_operating_submission_service as stage_service
from rocell.application.camera_activation_campaign_contract import (
    ACTION_IDS,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from rocell.application.camera_activation_runtime_policy import (
    reviewed_activation_runtime_candidate,
)
from rocell.application.camera_configuration_admission import (
    SEALED_EPOCH_SCHEMA,
    SEALED_HAZARD_SCHEMA,
)
from rocell.application.camera_configuration_original_scope import (
    _selected_probe_records_sha256,
)
from rocell.application.camera_operating_evidence_preflight import (
    CameraReadbackSubject,
    assess_camera_operating_evidence,
)
from rocell.application.camera_operating_original_assessment import _native
from rocell.application.camera_operating_pixels import (
    verify_sealed_operating_capture_pixels,
)
from rocell.application.camera_operating_proposal import build_camera_operating_proposal
from rocell.application.camera_operating_stage_requirements import (
    RETENTION_HOLD,
    project_operating_requirements,
)
from rocell.application.camera_operating_submission import (
    CameraOperatingSubmission,
    SOURCE_WORKFLOW_OPERATING_SCHEMA,
)
from rocell.application.camera_probe_admission import (
    HAZARD_SCHEMA as PROBE_HAZARD_SCHEMA,
)
from rocell.application.camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
    SOURCE_WORKFLOW_PROBE_SCHEMA,
)
from rocell.application.physical_onboarding_v2 import V2StageState as S
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.physical_camera_configuration import (
    derive_physical_camera_capabilities,
    stage_physical_camera_configuration,
    compare_physical_camera_readback,
)
from rocell.application.physical_camera_dispatch import PhysicalCameraDispatchOwner
from rocell.application.physical_camera_mode_entry import CameraModeEntry
from rocell.application.physical_camera_selection import PhysicalCameraSelection
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    NativeCameraMode,
)
from rocell.providers.windows.native_camera_activation_expectation import (
    CameraActivationExpectation,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_submission_persistence import (
    ready_store,
    stage,
    fresh_store,
    seed,
    WINDOWS,
    SOURCE,
    forbid_device_and_process_calls,
)
from test_native_camera_activation_supervisor import no_physical_owner
from test_physical_camera_dispatch import RecordingSink
import test_camera_activation_dispatch_handoff as native_fixture

pytestmark = WINDOWS
FRAME_BYTES = 5472 * 3648 * 2


def read_subjects(tx, binding):
    result = {}
    for name, key, cls in (
        ("entry", "entry_sha256", CameraModeEntry),
        ("preparation", "probe_preparation_sha256", CameraProbePreparation),
        ("review", "probe_review_sha256", CameraProbePreparationReview),
    ):
        refs = [r for r in tx.snapshot().evidence if r.payload_sha256 == binding[key]]
        assert len(refs) == 1
        result[name] = cls(tx.read_stage_evidence(refs[0]))
    return result


def original_request(tx, key, action):
    records = tx._audit_records(include_family=True)
    attempt = reader._resolve_request(records, key)
    return _native(tx, attempt, action)


def test_three_original_attempts_reopen_and_preserve_historical_pixel_verdict(
    tmp_path, monkeypatch, seed, record_property
):
    # Unlike a storage-only fixture, an actual dispatcher must assign its native
    # output inside this exact M1 deployment. Exercise that guard unchanged.
    runtime, base, placeholder, waiting = ready_store(
        tmp_path, seed, native_output_in_store=True
    )
    binding = placeholder.to_dict()["binding"]
    with stage(base) as tx:
        subjects = read_subjects(tx, binding)

        def record_for(subject):
            refs = [
                r for r in tx.snapshot().evidence if r.payload_sha256 == subject.sha256
            ]
            assert len(refs) == 1
            return dict(
                document=subject.to_dict(),
                evidence_sha256=subject.sha256,
                reference=refs[0].to_dict(),
                retention="M1_FULL_BYTES_READ_BACK",
            )

        # Only the preceding full-stage semantic projection is modeled; its
        # selected stage subjects below are read from the actual original store.
        original_workflow = dict(
            schema=SOURCE_WORKFLOW_PROBE_SCHEMA,
            camera_mode_entry=dict(entry=record_for(subjects["entry"])),
            camera_probe_preparation=dict(
                state="REVIEWED_FOR_ADMISSION",
                preparation=record_for(subjects["preparation"]),
                review=record_for(subjects["review"]),
                events=[e.to_dict() for e in waiting.committed_events[-2:]],
            ),
        )
    prep = subjects["preparation"].to_dict()
    plan = prep["plan"]
    workflow_sha = digest(canonical(original_workflow))
    context = dict(
        schema="rocell.camera_probe_original_scope_summary.v1",
        source_sha256=SOURCE,
        launch_session_id=plan["launch_session_id"],
        session_id=binding["session_id"],
        cell_id=binding["cell_id"],
        header_sha256=binding["header_sha256"],
        journal_head_sha256=binding["journal_head_sha256"],
        original_workflow_sha256=workflow_sha,
        preparation_sha256=subjects["preparation"].sha256,
        review_sha256=subjects["review"].sha256,
        authenticated_at_read=True,
        currentness_requires_revalidation=True,
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        meaning="Original setup was authenticated under CAMERA ownership. This cached summary cannot authorize device access or restore the in-process guard.",
    )
    epochs = tuple({"MODELED_stage_epoch": i} for i in range(8))
    admissions = {}

    def facts(tx, request, snapshot):
        # This single seam supplies modeled stage/physical facts, never permits,
        # native results or any replacements for the reader under test.
        return admissions[request.request_key]

    adapter = M1PhysicalCameraPersistence(
        runtime, workspace_source_sha256=SOURCE, scoped_admission_facts=facts
    )
    raw_fixture = native_fixture.result_fixture

    def full_metadata(purpose):
        first, second, raw = raw_fixture(purpose)
        mode = asdict(NativeCameraMode(5472, 3648, 8, 1, stride_bytes=10944))
        raw["native_receipt"]["modes"] = [mode]
        if purpose == "capture":
            raw["native_receipt"].update(requested_mode=mode, observed_mode=mode)
            raw["native_receipt"]["frames"][0].update(
                length_bytes=FRAME_BYTES, stride_bytes=10944
            )
        return first, second, raw

    monkeypatch.setattr(native_fixture, "result_fixture", full_metadata)
    monkeypatch.setattr(
        native_fixture, "PIXELS", b"\x40\x80\x80\x80" * (FRAME_BYTES // 4)
    )
    owners = []

    def dispatch(worker, key, settings=None):
        # Install returns a list filled lazily at execution, so keep that exact
        # list until the owner has run, then collect its incapable owner once.
        local = native_fixture.install_owner(
            tmp_path,
            monkeypatch,
            purpose=worker.plan()["purpose"],
            pixels=worker.plan()["purpose"] == "capture",
        )
        owner = PhysicalCameraDispatchOwner(
            adapter, worker, revalidate_context=lambda: None
        )
        result = owner.perform(
            request_key=key,
            sink=RecordingSink(),
            enrollment=None,
            cancellation=Event(),
            settings_epoch=settings,
        )
        owners.extend(local)
        assert result["status"] == "SUCCEEDED" and len(local) == 1 and local[0].cleaned

    probe_key = "MODELED-submission-probe"
    probe_worker = PhysicalCameraActivationCampaign.from_plan(plan)
    admissions[probe_key] = PhysicalCameraAdmissionFacts(
        dict(
            schema=PROBE_HAZARD_SCHEMA,
            plan_sha256=digest(canonical(plan)),
            request_key=probe_key,
            original_context=context,
        ),
        epochs,
        plan["selection"],
    )
    dispatch(probe_worker, probe_key)
    with stage(adapter) as tx:
        probe_permit, probe, _ = original_request(tx, probe_key, ACTION_IDS["probe"])
        capabilities = derive_physical_camera_capabilities(
            probe.evidence,
            expected_preparation=probe.preparation,
            expected_evidence_sha256=probe.expected_evidence_sha256,
            expected_supervision_sha256=probe.expected_supervision_sha256,
            expected_source_sha256=SOURCE,
        )
        settings = stage_physical_camera_configuration(
            capabilities,
            capabilities.view()["modes"][0]["choice_id"],
            (),
            expected_capabilities_sha256=capabilities.capabilities_sha256,
            expected_source_sha256=SOURCE,
            expected_session_id=binding["session_id"],
            expected_selected_identity_sha256=plan["selected_identity_sha256"],
        )
        probe_records_sha = _selected_probe_records_sha256(
            tx._audit_records(include_family=True), probe_permit.attempt_id
        )
    probe_refs = dict(
        attempt_id=probe_permit.attempt_id,
        request_key=probe_key,
        permit_sha256=probe_permit.permit_sha256,
        operation_sha256=probe_permit.registration.operation_sha256,
        evidence_sha256=probe.expected_evidence_sha256,
        supervision_sha256=probe.expected_supervision_sha256,
        preparation_sha256=probe.preparation.preparation_sha256,
    )
    capture_plan = PhysicalCameraActivationCampaign(
        Path(plan["workspace"]),
        Path(plan["assigned_parent_directory"]),
        source_sha256=SOURCE,
        cell_id=binding["cell_id"],
        session_id=binding["session_id"],
        selection=PhysicalCameraSelection(canonical(plan["selection"])),
        expectation=CameraActivationExpectation(canonical(plan["expectation"])),
        runtime=reviewed_activation_runtime_candidate(
            tmp_path, purpose="capture", source_sha256=SOURCE
        ),
        mode=settings.mode,
        controls=settings.controls,
        budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
        configuration_verification=True,
        sealed_configuration_capture=True,
    ).plan()
    capture_keys = ("MODELED-submission-capture-0", "MODELED-submission-capture-1")
    for key in capture_keys:
        capture_context = dict(
            schema="rocell.camera_configuration_original_scope_summary.v2",
            original_setup=context,
            probe=probe_refs,
            probe_records_sha256=probe_records_sha,
            capabilities_sha256=capabilities.capabilities_sha256,
            settings_epoch=settings.settings_epoch,
            plan_sha256=digest(canonical(capture_plan)),
            request_key=key,
            currentness_requires_revalidation=True,
            physical_authority=False,
            hardware_qualified=False,
            connected=False,
        )
        capture_epochs = tuple(
            dict(
                schema=SEALED_EPOCH_SCHEMA,
                original_setup_epoch=item,
                settings_epoch=settings.settings_epoch,
                capabilities_sha256=capabilities.capabilities_sha256,
                original_probe_records_sha256=probe_records_sha,
                applied=False,
                physical_configuration_qualified=False,
            )
            for item in epochs
        )
        admissions[key] = PhysicalCameraAdmissionFacts(
            dict(
                schema=SEALED_HAZARD_SCHEMA,
                request_key=key,
                action_id=SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
                settings=settings.to_dict(),
                capabilities_sha256=capabilities.capabilities_sha256,
                plan_sha256=digest(canonical(capture_plan)),
                original_context=capture_context,
                **{
                    k: capture_plan[k]
                    for k in (
                        "source_sha256",
                        "cell_id",
                        "session_id",
                        "launch_session_id",
                        "selected_identity_sha256",
                        "native_budget",
                    )
                },
            ),
            capture_epochs,
            plan["selection"],
        )
        dispatch(
            PhysicalCameraActivationCampaign.from_plan(capture_plan),
            key,
            settings.settings_epoch,
        )

    raw_profile = (
        Path(__file__).resolve().parents[3]
        / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    ).read_bytes()
    assigned_profile = (
        tmp_path / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    )
    assigned_profile.parent.mkdir(parents=True, exist_ok=True)
    assigned_profile.write_bytes(raw_profile)
    entry = subjects["entry"]
    proposal = build_camera_operating_proposal(
        proposal_id="modepolicy-" + "5" * 32,
        operator_id="MODELED native test",
        recorded_at_utc_ns=10009,
        rationale="Exercise real original native reconstruction with modeled stage semantics.",
        variance_rationale="Unreviewed modeled 8 fps variance.",
        entry_payload=entry.payload,
        expected_entry_id=entry.to_dict()["entry_id"],
        expected_entry_binding=entry.to_dict()["binding"],
        purchase_profile_payload=raw_profile,
        expected_purchase_profile_sha256=digest(raw_profile),
        configuration_payload=settings.payload,
        expected_settings_epoch=settings.settings_epoch,
    )
    with stage(adapter) as tx:
        selected, pixels, captures, paths = [], [], [], []
        for key in capture_keys:
            permit, native, checksum = original_request(
                tx, key, SEALED_CONFIGURATION_CAPTURE_ACTION_ID
            )
            selected.append(
                dict(
                    request_key=key,
                    attempt_id=permit.attempt_id,
                    permit_sha256=permit.permit_sha256,
                    capture_checksum_sha256=checksum.sha256,
                )
            )
            readback = compare_physical_camera_readback(
                settings,
                native.evidence,
                expected_preparation=native.preparation,
                expected_capture_evidence_sha256=native.expected_evidence_sha256,
                expected_supervision_sha256=native.expected_supervision_sha256,
                expected_settings_epoch=settings.settings_epoch,
            )
            captures.append(
                CameraReadbackSubject(
                    native, readback.payload, readback.readback_sha256
                )
            )
            pixels.append(
                verify_sealed_operating_capture_pixels(
                    native,
                    checksum=checksum,
                    request_key=key,
                    assigned_parent=plan["assigned_parent_directory"],
                    settings_epoch=settings.settings_epoch,
                    cancelled=lambda: False,
                )
            )
            paths.append(
                Path(native.preparation.camera_plan.request.output_directory)
                / "frame-000000.yuy2"
            )
        assert all(p["content_verified_at_read"] for p in pixels)
        preflight = assess_camera_operating_evidence(
            proposal_payload=proposal.payload,
            expected_proposal_sha256=proposal.sha256,
            entry_payload=entry.payload,
            expected_entry_id=entry.to_dict()["entry_id"],
            expected_entry_binding=entry.to_dict()["binding"],
            purchase_profile_payload=raw_profile,
            expected_purchase_profile_sha256=digest(raw_profile),
            capabilities_payload=capabilities.payload,
            expected_capabilities_sha256=capabilities.capabilities_sha256,
            configuration_payload=settings.payload,
            expected_settings_epoch=settings.settings_epoch,
            probe=probe,
            captures=tuple(captures),
        )
        report = json.loads(seed["assessment_payload"])
        unresolved = [
            k
            for k in preflight.to_dict()["owner_obligations"]
            if k
            not in (
                "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED",
                "PIXEL_FILES_NOT_VERIFIED",
            )
        ] + [RETENTION_HOLD]
        binding["original_records_sha256"] = digest(
            canonical(tx._audit_records(include_family=True))
        )
        report.update(
            session_id=binding["session_id"],
            header_sha256=binding["header_sha256"],
            journal_head_sha256=binding["journal_head_sha256"],
            original_records_sha256=binding["original_records_sha256"],
            proposal_sha256=proposal.sha256,
            captures=selected,
            pixel_checks=pixels,
            preflight=preflight.to_dict(),
            preflight_sha256=preflight.sha256,
            unresolved_checks=unresolved,
            stage_requirements=project_operating_requirements(
                unresolved, preflight.to_dict()["failed_checks"]
            ),
        )
        attempt_row = {}

        def modeled_prefix_with_actual_native(owner, **kwargs):
            kwargs["check"]()
            snapshot = owner.snapshot()
            if snapshot.head == waiting.head:
                return snapshot, deepcopy(original_workflow)
            record = attempt_row["record"]
            # Mirror the native half of the full reader unchanged; only the old
            # stage-prefix verification/projection is the explicitly modeled seam.
            joined = reader.verify_operating_submission_native_inputs(
                owner,
                submission=CameraOperatingSubmission(canonical(record["document"])),
                expected_binding=binding,
                **subjects,
                creation_workflow_sha256=workflow_sha,
                purchase_profile_payload=raw_profile,
            )
            return snapshot, dict(
                **{k: v for k, v in original_workflow.items() if k != "schema"},
                schema=SOURCE_WORKFLOW_OPERATING_SCHEMA,
                camera_operating_submission=dict(
                    state="SUBMITTED_REVIEW_REQUIRED",
                    submission=deepcopy(record),
                    events=[snapshot.committed_events[-1].to_dict()],
                    native_inputs=joined,
                ),
            )

        monkeypatch.setattr(
            stage_service,
            "_read_original_evidence_under_lease",
            modeled_prefix_with_actual_native,
        )
        stage_started = monotonic()
        saved_workflow = stage_service._retain_in_stage_transaction(
            tx,
            bound=dict(workspace=str(tmp_path), source_sha256=SOURCE),
            expected_header_sha256=waiting.header.header_sha256,
            expected_workflow_payload=canonical(original_workflow),
            proposal_payload=proposal.payload,
            report=report,
            operator_id="MODELED native test",
            attempt=attempt_row,
            check=lambda **_: None,
            progress=lambda _: None,
        )
        record_property(
            "stage_submission_seconds", round(monotonic() - stage_started, 6)
        )
        assert (
            saved_workflow["camera_operating_submission"]["state"]
            == "SUBMITTED_REVIEW_REQUIRED"
        )
        assert tx.snapshot().stages[4].state is S.REVIEW_PENDING
        assert attempt_row["commit"] == "COMMITTED_ORIGINAL_READ_BACK"
        matches = [
            r
            for r in tx.snapshot().evidence
            if r.payload_sha256 == attempt_row["record"]["evidence_sha256"]
        ]
        assert len(matches) == 1
        reference = matches[0]
    assert len(owners) == 3
    # The saved verdict remains historical if today's pixels change. The fresh
    # native reader must authenticate prior checksums, not rehash this file.
    with paths[0].open("r+b") as stream:
        stream.write(b"\x41")
    with stage(fresh_store(runtime)) as tx:
        before = tx.snapshot()
        stored = CameraOperatingSubmission(tx.read_stage_evidence(reference))
        reopened_subjects = read_subjects(tx, binding)
        result = reader.verify_operating_submission_native_inputs(
            tx,
            submission=stored,
            expected_binding=binding,
            **reopened_subjects,
            creation_workflow_sha256=workflow_sha,
            purchase_profile_payload=raw_profile,
        )
        assert result["preflight_sha256"] == preflight.sha256
        assert (
            result["pixel_check_semantics"]
            == "HISTORICAL_READ_NOT_CURRENT_FILE_VERIFICATION"
        )
        assert not result["connected"] and not result["original_stage_authenticated"]
        assert tx.snapshot() == before
        saved_records = tx._audit_records(include_family=True)
        common = dict(
            submission=stored,
            expected_binding=binding,
            **reopened_subjects,
            creation_workflow_sha256=workflow_sha,
            purchase_profile_payload=raw_profile,
        )
        with pytest.raises(ValueError, match="ORIGINAL_BINDING"):
            reader.verify_operating_submission_native_inputs(
                tx,
                **{
                    **common,
                    "expected_binding": {**binding, "source_sha256": "f" * 64},
                },
            )
        with pytest.raises(ValueError, match="ORIGINAL_SETUP_CONTEXT"):
            reader.verify_operating_submission_native_inputs(
                tx, **{**common, "creation_workflow_sha256": "f" * 64}
            )
        # Fault injection at the returned-facts boundary, not edits to originals:
        # the independently reconstructed context and epochs must catch a
        # substituted value even if an upstream returned dictionary is altered.
        admission_read = M1PhysicalCameraTransaction.read_campaign_admission_evidence
        for fault, error in (
            ("context", "ORIGINAL_CAPTURE_ORIGINAL_CONTEXT"),
            ("epoch", "ORIGINAL_CAPTURE_EPOCHS"),
        ):

            def changed_facts(owner, attempt_id):
                facts = deepcopy(admission_read(owner, attempt_id))
                if attempt_id == selected[0]["attempt_id"]:
                    if fault == "context":
                        facts["hazard_assessment"]["original_context"][
                            "probe_records_sha256"
                        ] = ("f" * 64)
                    else:
                        facts["configuration_epochs"][0][
                            "original_probe_records_sha256"
                        ] = ("f" * 64)
                return facts

            with monkeypatch.context() as patch:
                patch.setattr(
                    M1PhysicalCameraTransaction,
                    "read_campaign_admission_evidence",
                    changed_facts,
                )
                with pytest.raises(ValueError, match=error):
                    reader.verify_operating_submission_native_inputs(tx, **common)
            assert tx.snapshot() == before
            assert tx._audit_records(include_family=True) == saved_records
        changed = stored.to_dict()
        changed["assessment"]["pixel_checks"][1]["native_frame_sha256"] = "f" * 64
        changed["assessment_sha256"] = digest(canonical(changed["assessment"]))
        with pytest.raises(ValueError, match="ORIGINAL_PIXEL_HASH"):
            reader.verify_operating_submission_native_inputs(
                tx,
                submission=CameraOperatingSubmission(canonical(changed)),
                expected_binding=binding,
                **reopened_subjects,
                creation_workflow_sha256=workflow_sha,
                purchase_profile_payload=raw_profile,
            )
        assert tx.snapshot() == before
    assert len(owners) == 3 and all(owner.cleaned for owner in owners)
