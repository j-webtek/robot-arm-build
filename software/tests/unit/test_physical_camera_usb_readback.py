"""Full original typed histories with modeled file/device facts, no query.

The scope fixture models the ledger/filesystem seam only. Production codecs,
full immutable V2 snapshots and the closed original-prefix reader are real.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_baseline as codec
from rocell.application import physical_camera_usb_readback as reader
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.physical_camera_selection import PhysicalCameraSelection
from rocell.application.physical_usb_identity_campaign import usb_identity_operation
from rocell.application import usb_identity_stage_policy as policy_module
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_camera_identity_readback import (
    identity_ready,
    identity_subjects,
    identity_inputs,
    received_ready,
    received_subjects,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    refresh_read,
)

USB_ID = "usbidentity-" + "a" * 32


def usb_code(phase):
    return "CAMERA_USB_" + phase + "_" + USB_ID[12:].upper()


def baseline_subjects(case, *, phase="ready", metadata=None):
    """Actual codec objects from a clearly modeled full original v7 history."""
    owner, _, state = case
    metadata = metadata or identity_subjects(case, **identity_inputs())
    state["advance"](
        V2StageState.WAITING_OPERATOR,
        usb_code("INSPECTION_STARTED"),
        metadata.refs.values(),
        stage=STAGE_ORDER[3],
    )
    refs, subjects = {}, {}
    result = SimpleNamespace(case=case, metadata=metadata, refs=refs, subjects=subjects)
    if phase == "started":
        return result
    binding = dict(
        usb_id=USB_ID,
        source_sha256=owner.descriptor()["source_sha256"],
        cell_id=owner.descriptor()["cell_id"],
        session_id=owner.descriptor()["session_id"],
        header_sha256=state["header"].header_sha256,
        origin_launch_id=owner.descriptor()["launch_id"],
        collection_launch_id=metadata.subjects["metadata"].to_dict()["binding"][
            "collection_launch_id"
        ],
        operator_id="usb-operator",
        metadata={
            role: metadata.subjects[role].sha256 for role in codec.METADATA_ROLES
        },
    )
    selected = PhysicalCameraSelection(
        canonical(metadata.subjects["metadata"].to_dict()["selection"]["document"])
    )
    runtime = registration.usb_identity_runtime_candidate(
        Path(owner.descriptor()["workspace"]), source_sha256=binding["source_sha256"]
    )
    policy = policy_module.usb_identity_stage_policy()
    operation = usb_identity_operation(
        cell_id=binding["cell_id"],
        session_id=binding["session_id"],
        selection=selected,
        runtime=runtime,
        policy=policy,
    )
    rd = runtime.to_dict()
    file_report = dict(
        schema="rocell.usb_identity_runtime_file_check.v1",
        runtime_registration_sha256=runtime.sha256,
        source_sha256=binding["source_sha256"],
        status="FILES_MATCHED",
        files=[
            dict(path=p, sha256=h, bytes=1)
            for p, h, _ in [
                *registration.FIXED_SOURCE_PINS,
                (
                    registration.BUILD_RECORD_PATH,
                    registration.BUILD_RECORD_SHA256,
                    32768,
                ),
                (rd["helper"]["path"], rd["helper"]["sha256"], 1048576),
            ]
        ],
        physical_authority=False,
        hardware_qualified=False,
    )

    def retain(role, artifact):
        subjects[role] = artifact
        refs[role] = state["add"](
            artifact.payload,
            label="camera-usb-" + role.replace("_", "-") + "-v1:" + USB_ID,
            stage=STAGE_ORDER[3],
        )

    retain(
        "inspection",
        codec.build_usb_baseline_inspection(
            binding=binding,
            policy=policy,
            operation=operation,
            runtime_report=file_report,
            collected_at_ns=20000,
        ),
    )
    if phase == "inspection":
        return result
    state["advance"](
        V2StageState.REVIEW_PENDING,
        usb_code("INSPECTED"),
        [refs["inspection"]],
        stage=STAGE_ORDER[3],
    )
    if phase == "inspected":
        return result
    review = policy_module.UsbIdentityPolicyReview(
        canonical(
            dict(
                schema=policy_module.REVIEW_SCHEMA,
                **{
                    key: binding[key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                        "operator_id",
                    )
                },
                policy=policy.to_dict(),
                policy_sha256=policy.sha256,
                reviewer_id="usb-reviewer",
                reviewed_at_utc_ns=20001,
                purpose="REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
                **policy_module._FLAGS,
            )
        )
    )
    retain("policy_review", review)
    if phase == "policy-review":
        return result
    sd = selected.identity_document
    review = registration.review_usb_identity_runtime(
        runtime,
        selection_sha256=selected.sha256,
        native_identity_sha256=sd["native_identity_sha256"],
        endpoint_sha256=sd["endpoint_sha256"],
        device_instance_id_sha256=digest(
            sd["metadata_review"]["observed_instance_id"].encode()
        ),
        operation_sha256=operation.sha256,
        operator_id=binding["operator_id"],
        reviewer_id="usb-reviewer",
        launch_session_id=binding["collection_launch_id"],
        reviewed_at_ns=20001,
    )
    retain("runtime_review", review)
    if phase == "runtime-review":
        return result
    review_data = review.to_dict()
    original_subjects = []
    for role in ("metadata", "policy_review", "runtime_review"):
        original_subjects.append(
            dict(
                role=role,
                reference=(metadata.refs if role == "metadata" else refs)[
                    role
                ].to_dict(),
                document_sha256=(metadata.subjects if role == "metadata" else subjects)[
                    role
                ].sha256,
            )
        )
    identity = policy_module.UsbIdentityAdmissionIdentity(
        canonical(
            dict(
                schema=policy_module.IDENTITY_SCHEMA,
                **{
                    key: binding[key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                },
                stage_policy_sha256=policy.sha256,
                policy_review_sha256=subjects["policy_review"].sha256,
                runtime_review_sha256=review.sha256,
                runtime_registration_sha256=runtime.sha256,
                original_subjects=original_subjects,
                **{
                    key: review_data[key]
                    for key in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                        "device_instance_id_sha256",
                        "operation_sha256",
                    )
                },
            )
        )
    )
    retain("identity", identity)
    if phase == "identity":
        return result
    state["advance"](
        V2StageState.BLOCKED, usb_code("REVIEWED"), refs.values(), stage=STAGE_ORDER[3]
    )
    if phase == "reviewed":
        return result
    state["advance"](
        V2StageState.WAITING_OPERATOR,
        usb_code("QUERY_REQUESTED"),
        refs.values(),
        stage=STAGE_ORDER[3],
    )
    return result


def modeled_clean_held_evidence(prepared):
    """Pure modeled no-query native cancellation plus complete owner receipt.

    These are constructed fixture observations, not an executed child or a
    physical USB observation. The real strict native/owned codecs derive HELD.
    """
    from rocell.providers.windows import usb_identity_protocol as protocol
    from rocell.providers.windows import owned_usb_identity_evidence as owned

    request = prepared.request
    rq = request.to_dict()
    native = protocol.UsbIdentityObservation(
        canonical(
            dict(
                schema=protocol.OBSERVATION_SCHEMA,
                request_sha256=request.request_sha256,
                requested_endpoint=rq["endpoint"],
                expected_device_instance_id=rq["expected_device_instance_id"],
                outcome="HELD",
                pre_mapping=None,
                post_mapping=None,
                device_descriptor=None,
                languages=None,
                serial_descriptors=[],
                link=None,
                accounting=dict.fromkeys(protocol._ACCOUNTING, 0),
                calls=[],
                error=dict(code="CANCELLED", domain="CONTRACT", native_code=0),
                elapsed_ms=0,
            )
        )
    )
    ready = protocol.UsbIdentityReady(
        canonical(
            dict(
                schema=protocol.READY_SCHEMA,
                request_sha256=request.request_sha256,
                child_pid=31415,
                challenge="1" * 64,
            )
        )
    )
    ready_wire = ready.payload + b"\n"
    release = protocol.usb_identity_release(request, ready)
    result = canonical(
        dict(
            schema=protocol.RESULT_SCHEMA,
            request_sha256=request.request_sha256,
            child_pid=31415,
            challenge_sha256=ready.challenge_sha256,
            permit_sha256=rq["permit_sha256"],
            native_receipt=native.to_dict(),
        )
    )
    process = dict(
        owned.PROCESS_DEFAULTS,
        created=True,
        resumed=True,
        tree_exited=True,
        returncode=1,
        pid=31415,
        written=len(request.wire()) + len(release),
        peak_processes=1,
        stdout_eof=True,
        stderr_eof=True,
    )
    return owned.retain_owned_usb_identity_run(
        dict(
            schema=owned.SCHEMA,
            preparation=prepared.to_dict(),
            preparation_sha256=prepared.sha256,
            provenance="PHYSICAL_USB_QUERY",
            original_deadline_ns=25000000100,
            started_monotonic_ns=100,
            finished_monotonic_ns=200,
            started_utc_ns=30000,
            finished_utc_ns=30001,
            scope_checks=[
                dict(
                    boundary=name, started_ns=110 + i, finished_ns=110 + i, passed=True
                )
                for i, name in enumerate(owned.BOUNDARIES)
            ],
            owner_constructed=True,
            process=process,
            stdout=owned.stream_record(ready_wire + result, complete=True),
            stderr=owned.stream_record(b"", complete=True),
            ready_length=len(ready_wire),
            release_wire=owned.stream_record(release, complete=True),
            release_write_attempted=True,
            release_check_passed=True,
            release_delivery_confirmed=True,
            result_validated=True,
            primary_error=None,
            cleanup_errors=[],
            status="HELD",
            physical_authority=False,
            hardware_qualified=False,
            retries=0,
        )
    )


def retain_modeled_known_campaign(made, *, phase="retained"):
    """Modeled ledger seam with actual permit/worker/subject codecs; no M1 run."""
    from dataclasses import asdict
    from rocell.application import cell_commissioning_coordinator as core
    from rocell.application.physical_onboarding_attempts import AttemptState
    from rocell.application.physical_onboarding_durability import canonical_sha256
    from rocell.application.physical_usb_identity_campaign import (
        PhysicalUsbIdentityCampaign,
        UsbIdentityOperation,
    )
    from test_physical_camera_coordinator import admission

    case = made.case
    owner, _, state = case
    snapshot = state["snapshot"]()
    identity = made.subjects["identity"]
    inspection = made.subjects["inspection"]
    campaign = PhysicalUsbIdentityCampaign(
        UsbIdentityOperation(canonical(inspection.to_dict()["operation"])),
        identity=identity,
        review=made.subjects["runtime_review"],
    )
    facts = dict(
        stage_policy=inspection.to_dict()["policy"],
        hazard_assessment=dict(modeled=True),
        configuration_epochs=[dict(domain=i, modeled=True) for i in range(8)],
        selected_identity=identity.to_dict(),
    )
    base = asdict(admission())
    base.update(
        cell_id=owner.descriptor()["cell_id"],
        session_id=owner.descriptor()["session_id"],
        stage=STAGE_ORDER[3],
        stage_state=V2StageState.WAITING_OPERATOR,
        stage_revision=len(snapshot.committed_events),
        journal_head_sha256=snapshot.head.head_sha256,
        evidence_inventory_sha256=canonical_sha256(
            [ref.to_dict() for ref in snapshot.evidence]
        ),
        selected_identity_sha256=identity.sha256,
        hazard_assessment_sha256=digest(canonical(facts["hazard_assessment"])),
        configuration_epoch_hashes=tuple(
            digest(canonical(doc)) for doc in facts["configuration_epochs"]
        ),
    )
    admitted = core.UsbIdentityAdmissionSnapshot(
        **base, usb_query_policy_sha256=policy_module.usb_identity_stage_policy().sha256
    )
    permit = core.ExactOperationPermit(
        "attempt-" + "8" * 32,
        core.RegisteredActionRequest(
            base["cell_id"],
            base["session_id"],
            campaign.registration().action_id,
            "MODELED-original-query",
            admitted.challenge_sha256,
        ),
        admitted,
        campaign.registration(),
        100,
        30000000100,
        "9" * 64,
    )
    execution = modeled_clean_held_evidence(campaign.preparation_for_permit(permit))
    assert execution.bounded_effect_summary()["current_complete"]
    receipt = core.WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        campaign.worker_executable_sha256,
        identity.sha256,
        core.EffectCertainty.CONFIRMED,
        True,
        core.ObservedPowerState.UNKNOWN,
        0,
        0,
        0,
        0,
        0,
        len(execution.payload),
        (execution.sha256,),
        campaign.composition,
    )
    result = core.AttemptResult(
        permit.attempt_id,
        AttemptState.SEALED_KNOWN,
        permit.permit_sha256,
        (),
        receipt,
        False,
        campaign.composition,
    )
    reference = dict(
        schema="rocell.usb_identity_campaign_reference.v1",
        cell_id=base["cell_id"],
        session_id=base["session_id"],
        attempt_id=permit.attempt_id,
        permit_sha256=permit.permit_sha256,
        evidence_sha256=execution.sha256,
        payload_bytes=len(execution.payload),
        label="physical-native-usb-identity",
    )
    original = dict(
        permit=asdict(permit),
        result=asdict(result),
        admission_evidence=facts,
        evidence=execution.to_dict(),
        evidence_sha256=execution.sha256,
        reference=reference,
        retention="M1_FULL_BYTES_READ_BACK",
    )
    # Modeled only here; actual NTFS test obtains this event from the audited
    # cell-global journal, never from an action payload or a worker callback.
    event = dict(
        attempt_id=permit.attempt_id,
        operation_binding_sha256=permit.permit_sha256,
        state="SEALED_KNOWN",
    )
    made.original_campaigns = (
        __import__("json").loads(canonical(dict(original=original, event=event))),
    )
    made.subjects["execution"] = execution
    if phase == "campaign":
        return made
    made.refs["execution"] = state["add"](
        execution.payload,
        label="camera-usb-execution-v1:" + USB_ID,
        stage=STAGE_ORDER[3],
    )
    if phase == "execution":
        return made
    outcome = codec.build_usb_baseline_outcome(
        inspection=inspection,
        identity=identity,
        execution_reference=made.refs["execution"],
        campaign_original=original,
        recorded_at_ns=30002,
    )
    made.subjects["outcome"] = outcome
    made.refs["outcome"] = state["add"](
        outcome.payload, label="camera-usb-outcome-v1:" + USB_ID, stage=STAGE_ORDER[3]
    )
    if phase == "retained":
        state["advance"](
            V2StageState.BLOCKED,
            usb_code("QUERY_RETAINED"),
            made.refs.values(),
            stage=STAGE_ORDER[3],
        )
    return made


@pytest.fixture
def usb_ready(identity_ready, monkeypatch):
    # Only the modeled fixture has no real coordinator ledger. Actual NTFS
    # cases separately exercise the unpatched family audit/extraction.
    monkeypatch.setattr(reader, "read_original_usb_campaigns", lambda *args: ())
    return identity_ready


@pytest.mark.parametrize(
    "phase,status",
    [
        ("started", "INCOMPLETE"),
        ("inspection", "INCOMPLETE"),
        ("inspected", "REVIEW_PENDING"),
        ("policy-review", "INCOMPLETE"),
        ("runtime-review", "INCOMPLETE"),
        ("identity", "INCOMPLETE"),
        ("reviewed", "INCOMPLETE"),
        ("ready", "READY_TO_QUERY"),
    ],
)
def test_exact_original_partial_prefix(usb_ready, phase, status):
    made = baseline_subjects(usb_ready, phase=phase)
    observed = refresh_read(usb_ready)
    assert observed["schema"] == session.SOURCE_WORKFLOW_USB_SCHEMA
    baseline = observed["usb_baseline"]
    assert baseline["state"] == status
    assert baseline["original_campaign"] is None
    assert baseline["campaign_event"] is None
    for role in codec.USB_ROLE_BYTES:
        if role in made.subjects:
            assert baseline[role]["document"] == made.subjects[role].to_dict()
            assert baseline[role]["evidence_sha256"] == made.subjects[role].sha256
        else:
            assert baseline[role] is None
    assert all(
        row.state is V2StageState.PENDING
        for row in usb_ready[2]["snapshot"]().stages[4:]
    )
    assert usb_ready[0].retained_source_workflow() == observed
    observed["usb_baseline"]["state"] = "FORGED"
    assert usb_ready[0].retained_source_workflow()["usb_baseline"]["state"] == status


@pytest.mark.parametrize(
    "fault",
    [
        "unknown-label",
        "unknown-event",
        "wrong-stage",
        "skip-role",
        "second-id",
        "fake-pass",
    ],
)
def test_closed_usb_role_event_domain(usb_ready, fault):
    made = baseline_subjects(usb_ready, phase="ready")
    state = usb_ready[2]
    if fault in {"unknown-label", "wrong-stage", "second-id"}:
        state["add"](
            made.subjects["inspection"].payload,
            label=(
                "camera-usb-secret-v1:" + USB_ID
                if fault == "unknown-label"
                else "camera-usb-inspection-v1:"
                + ("usbidentity-" + "b" * 32 if fault == "second-id" else USB_ID)
            ),
            stage=STAGE_ORDER[4] if fault == "wrong-stage" else STAGE_ORDER[3],
        )
    elif fault == "skip-role":
        state["references"].remove(made.refs["policy_review"])
    else:
        state["advance"](
            V2StageState.PASS if fault == "fake-pass" else V2StageState.BLOCKED,
            (
                "CAMERA_USB_QUERY_PASSED_" + "A" * 32
                if fault == "fake-pass"
                else "UNEXPECTED_USB_EVENT"
            ),
            (),
            stage=STAGE_ORDER[3],
        )
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(usb_ready)


def test_inspection_canonical_detached_and_closed(usb_ready, monkeypatch):
    made = baseline_subjects(usb_ready, phase="inspection")
    inspection = made.subjects["inspection"]
    document = inspection.to_dict()
    document["policy"]["revision"] = 99
    assert inspection.to_dict()["policy"]["revision"] != 99

    def denied(*args, **kwargs):
        pytest.fail("pure restoration performed I/O")

    monkeypatch.setattr(Path, "open", denied)
    restored = codec.UsbBaselineInspection(inspection.payload)
    assert restored.sha256 == inspection.sha256
    for change in (
        lambda d: d.update(extra=True),
        lambda d: d.update(physical_authority=True),
        lambda d: d["runtime_report"]["files"][0].update(sha256="f" * 64),
    ):
        doc = inspection.to_dict()
        change(doc)
        with pytest.raises(ValueError):
            codec.UsbBaselineInspection(canonical(doc))
    with pytest.raises(ValueError):
        codec.UsbBaselineInspection(inspection.payload + b"\n")


def test_public_v7_does_not_ignore_usb_suffix(usb_ready, monkeypatch):
    from rocell.application.physical_camera_identity_readback import (
        verify_camera_identity_workflow,
    )

    baseline_subjects(usb_ready)
    captured = []
    original = session._verify_original_source_roles

    def capture(*args, **kwargs):
        captured.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(session, "_verify_original_source_roles", capture)
    assert refresh_read(usb_ready)["schema"] == session.SOURCE_WORKFLOW_USB_SCHEMA
    with pytest.raises(session.PhysicalCameraSessionError):
        verify_camera_identity_workflow(*captured[-1][:11])


@pytest.mark.parametrize(
    "prefix",
    [
        "WORKSPACE_SOURCES_",
        "STATIC_CAMERA_CONTRACT_COLLECTED_",
        "CAMERA_RECEIPT_COLLECTION_SUBMITTED_",
        "CAMERA_IDENTITY_METADATA_COLLECTED_",
    ],
)
def test_extension_still_rejects_changed_actual_prefix(usb_ready, prefix):
    baseline_subjects(usb_ready)
    state = usb_ready[2]
    index = next(
        i
        for i, event in enumerate(state["events"])
        if event.detail_code.startswith(prefix)
    )
    state["events"][index] = replace(
        state["events"][index], detail_code="UNOWNED_PREDECESSOR_EVENT"
    )
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(usb_ready)


@pytest.mark.parametrize("role", tuple(codec.USB_ROLE_BYTES))
def test_usb_role_caps_checked_before_decode(usb_ready, role):
    baseline_subjects(usb_ready, phase="started")
    usb_ready[2]["add"](
        b" " * (codec.USB_ROLE_BYTES[role] + 1),
        label="camera-usb-" + role.replace("_", "-") + "-v1:" + USB_ID,
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(
        session.PhysicalCameraSessionError, match="READBACK_LIMIT|USB_ROLE"
    ):
        refresh_read(usb_ready)


@pytest.mark.parametrize("phase", ["campaign", "execution", "outcome", "retained"])
def test_known_held_campaign_transfer_requires_original_join(
    usb_ready, monkeypatch, phase
):
    made = retain_modeled_known_campaign(baseline_subjects(usb_ready), phase=phase)
    monkeypatch.setattr(
        reader, "read_original_usb_campaigns", lambda *args: made.original_campaigns
    )
    workflow = refresh_read(usb_ready)
    baseline = workflow["usb_baseline"]
    assert baseline["state"] == (
        "RETAINED_BLOCKED" if phase == "retained" else "ORIGINAL_CAMPAIGN_HELD"
    )
    assert baseline["original_campaign"] == made.original_campaigns[0]["original"]
    if baseline["outcome"]:
        assert baseline["outcome"]["document"]["outcome"] == "HELD"
        assert baseline["outcome"]["document"]["stage_pass"] is False
        from test_physical_camera_identity_readback import structure

        raw = canonical(workflow)
        nodes, depth = structure(workflow)
        assert session._decode_cached_source_workflow(raw) == workflow
        assert len(raw) <= session.MAX_USB_WORKFLOW_BYTES and depth <= 16
        print(
            f"v8 complete modeled HELD originals: {len(raw)} bytes, {nodes} nodes, depth {depth}"
        )
    monkeypatch.setattr(reader, "read_original_usb_campaigns", lambda *args: ())
    if phase != "campaign":
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(usb_ready)


@pytest.mark.parametrize(
    "fault", ["permit-head", "original-identity", "execution-hash", "reference-attempt"]
)
def test_original_campaign_cannot_be_substituted(usb_ready, monkeypatch, fault):
    from dataclasses import asdict
    from rocell.application.commissioning_usb_identity_persistence import (
        decode_physical_usb_identity_permit,
    )

    made = retain_modeled_known_campaign(baseline_subjects(usb_ready))
    originals = deepcopy(made.original_campaigns)
    original = originals[0]["original"]
    if fault == "permit-head":
        permit = decode_physical_usb_identity_permit(original["permit"])
        changed = replace(permit.admission, journal_head_sha256="f" * 64)
        permit = replace(
            permit,
            admission=changed,
            request=replace(
                permit.request, expected_challenge_sha256=changed.challenge_sha256
            ),
        )
        original["permit"] = asdict(permit)
    elif fault == "original-identity":
        original["admission_evidence"]["selected_identity"]["header_sha256"] = "f" * 64
    elif fault == "execution-hash":
        original["evidence_sha256"] = "f" * 64
    else:
        original["reference"]["attempt_id"] = "attempt-" + "f" * 32
    monkeypatch.setattr(reader, "read_original_usb_campaigns", lambda *args: originals)
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(usb_ready)


def test_actual_ntfs_usb_prefix_uncertain_original_and_restart(workspace, monkeypatch):
    """Real M1 ledger/leases/original bytes, explicitly modeled failure worker.

    All earlier receipt/isolation/metadata facts and the fixed file inspection
    are modeled test inputs. No process or physical provider is ever invoked.
    """
    import os
    import time
    from threading import Event

    if os.name != "nt":
        pytest.skip("Actual NTFS ownership required")
    from test_physical_camera_identity_readback import (
        actual_identity_entry,
        actual_transaction_state,
    )
    from test_physical_camera_session import perform, session_fixture, SOURCE, SESSION
    from test_physical_camera_intake_session import read
    from test_physical_usb_identity_dispatch_m1 import failure_evidence
    from test_commissioning_usb_identity import usb_facts
    from rocell.application import physical_usb_identity_dispatch as dispatch
    from rocell.application.physical_usb_identity_campaign import (
        PhysicalUsbIdentityCampaign,
        UsbIdentityOperation,
    )
    from rocell.application.commissioning_usb_identity_persistence import (
        M1PhysicalUsbIdentityPersistence,
        PhysicalUsbIdentityAdmissionFacts,
    )
    from rocell.providers.windows import owned_usb_identity_runner as runner_module

    case = actual_identity_entry(
        workspace, monkeypatch, include_configuration_epochs=True
    )
    owner, _, state = case
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        state.update(
            actual_transaction_state(tx), events=tx.snapshot().committed_events
        )
        metadata = identity_subjects(case, **identity_inputs())
        made = baseline_subjects(case, metadata=metadata)
    perform(owner, "refresh")
    original = read(owner, state["header"].header_sha256)
    assert original["usb_baseline"]["state"] == "READY_TO_QUERY"
    policy = policy_module.usb_identity_stage_policy()
    identity = made.subjects["identity"]
    campaign = PhysicalUsbIdentityCampaign(
        UsbIdentityOperation(
            canonical(made.subjects["inspection"].to_dict()["operation"])
        ),
        identity=identity,
        review=made.subjects["runtime_review"],
    )

    def facts(request, snapshot):
        modeled = usb_facts()
        return PhysicalUsbIdentityAdmissionFacts(
            modeled.hazard_assessment_document,
            modeled.configuration_epoch_documents,
            identity.to_dict(),
            stage_policy=policy,
        )

    adapter = M1PhysicalUsbIdentityPersistence(
        owner._store._runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=policy,
        expected_usb_query_policy_sha256=policy.sha256,
        admission_facts=facts,
    )
    calls = []

    class ModelRunner:
        def __init__(self, prepared, *, permit, authorization, application_guard):
            self.prepared, self.permit, self.authorization, self.guard = (
                prepared,
                permit,
                authorization,
                application_guard,
            )

        def run(self, *, cancellation, deadline_ns):
            calls.append("ENTERED")
            started, utc = time.monotonic_ns(), time.time_ns()
            self.guard()
            self.authorization.acknowledge(self.permit)
            a = time.monotonic_ns()
            self.authorization.revalidate(self.permit)
            b = time.monotonic_ns()
            evidence = failure_evidence(
                self.prepared,
                deadline_ns=deadline_ns,
                checks=[
                    dict(boundary="PRE_PIN", started_ns=a, finished_ns=b, passed=True)
                ],
                started_ns=started,
                started_utc_ns=utc,
                process_created=True,
            )
            calls.append(evidence)
            return evidence

    monkeypatch.setattr(runner_module, "OwnedUsbIdentityRunner", ModelRunner)
    monkeypatch.setattr(dispatch, "source_fingerprint", lambda _: SOURCE)
    from rocell.application.cell_commissioning_coordinator import (
        CommissioningCoordinatorError,
        PhysicalUsbIdentityCoordinator,
    )
    from rocell.application.commissioning_usb_identity_persistence import (
        M1PhysicalUsbIdentityTransaction,
    )

    errors = []
    timings = []

    def timed(cls, name):
        original = getattr(cls, name)

        def measured(*args, **kwargs):
            start = time.monotonic_ns()
            try:
                return original(*args, **kwargs)
            finally:
                timings.append((name, (time.monotonic_ns() - start) / 1e9))

        monkeypatch.setattr(cls, name, measured)

    for cls, names in (
        (PhysicalUsbIdentityCoordinator, ("prepare", "execute")),
        (
            M1PhysicalUsbIdentityTransaction,
            ("read_admission", "begin_intent", "consume_permit"),
        ),
    ):
        for name in names:
            timed(cls, name)
    original_error = CommissioningCoordinatorError.__init__

    def retain_error(self, message):
        errors.append(message)
        original_error(self, message)

    monkeypatch.setattr(CommissioningCoordinatorError, "__init__", retain_error)
    query = dispatch.PhysicalUsbIdentityDispatchOwner(
        adapter, campaign, revalidate_context=lambda: None
    )
    try:
        result = query.perform(
            request_key="original-v8-incapable-model", cancellation=Event()
        )
    except Exception:
        # Full-history filesystem work can exhaust the original 5s dispatch
        # slack before worker entry. Preserve the genuine sealed original;
        # this is not a successful worker/evidence-retention claim or retry.
        assert not calls
        assert (
            "full bounded campaign no longer fits the consumed permit/envelope"
            in errors
        )
        terminal = query.retained_diagnostics()["original"]["result"]
        assert (
            terminal["state"] == "SEALED_UNCERTAIN" and terminal["quarantine_latched"]
        )
        print("Observed pre-worker hold:", errors)
    else:
        assert (
            result["attempt_state"] == "SEALED_UNCERTAIN"
            and result["quarantine_latched"]
        )
        assert len(calls) == 2
    print("Actual USB original timings:", timings)
    fresh = session_fixture(workspace)
    perform(fresh, "refresh")
    restored = read(fresh, state["header"].header_sha256)
    baseline = restored["usb_baseline"]
    assert baseline["state"] == "ORIGINAL_CAMPAIGN_HELD"
    assert baseline["execution"] is None and baseline["outcome"] is None
    assert canonical(baseline["original_campaign"]) == canonical(
        query.retained_diagnostics()["original"]
    )
    if calls:
        assert canonical(baseline["original_campaign"]["evidence"]) == calls[1].payload
    else:
        assert baseline["original_campaign"]["evidence"] is None
        assert baseline["original_campaign"]["reference"] is None
    assert baseline["original_campaign"]["result"]["receipt"] is None
    assert baseline["campaign_event"]["state"] == "SEALED_UNCERTAIN"
    assert all(row["state"] == "PENDING" for row in fresh.view()["stages"][4:])
    assert len(calls) in (0, 2) and fresh._store._runtime.verify(SESSION).quarantined
    assert (
        len(calls) == 2
    ), "Original query did not reach its modeled consumed worker within unchanged limits"
