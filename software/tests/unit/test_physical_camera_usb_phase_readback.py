"""New original BASELINE grammar with explicitly MODELED unit/OS facts.

Actual immutable codecs and real complete V2 histories; the default storage
seam is modeled. No native helper, CIM, device, or process is executed.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_usb_phase as codec
from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_readback as usb_reader
from rocell.application import physical_camera_usb_trial_readback as trial
from rocell.application.physical_camera_usb_phase_readback import (
    verify_usb_phase_workflow,
)
from rocell.application.physical_camera_selection import (
    selection_from_enrollment_snapshot,
)
from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    _parse_evidence_reference,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.physical_usb_identity_campaign import (
    usb_identity_phase_operation,
)
from rocell.application.physical_usb_trial_boot import build_usb_trial_boot_intent
from rocell.application import usb_identity_stage_policy as policy_module
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_usb_trial_readback import (
    ready,
    declare,
    change_last_event,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    initial_epoch,
    identity_subjects,
    identity_inputs,
    refresh_read,
    LAUNCH,
    SOURCE,
)

PHASE_ID = "usbphase-" + "2" * 32


@pytest.fixture(autouse=True)
def empty_campaigns(ready, monkeypatch):
    monkeypatch.setattr(usb_reader, "read_original_usb_campaigns", lambda *a, **k: ())


def fresh_enrollment(source=SOURCE, launch=LAUNCH):
    """Call the real metadata owner using modeled packets and fresh operation IDs."""
    owners = identity_inputs(source=source, launch=launch, return_owners=True)
    owner = owners["native_camera"]
    old = owner.export_snapshot()
    generic = WizardDeviceSelection("physical", launch, source)
    generic.ingest(
        old["generic_review"]["inventory_report"],
        operation_id="phase-generic-inventory",
    )
    generic.review(
        generic.choices("CAMERA")[0]["value"], "CAMERA", "phase-generic-reviewer"
    )
    owner.ingest_inventory(
        old["inventory_packet"],
        operation_id="phase-native-inventory",
        generic_review=generic.reviewed_candidate("CAMERA"),
    )
    choice = owner.choices()[0]["value"]
    owner.retain_identity(
        choice, old["identity_packet"], operation_id="phase-native-identity"
    )
    return owner.review(choice, "phase-endpoint-reviewer")


def phase_subjects(case, *, stop="reviewed", actual_original=None):
    """Real codecs; optional real transactions, always MODELED physical facts.

    ``actual_original`` is an authentic v9 readback supplied by the isolated
    NTFS fixture. In that mode no journal event is manufactured or rewritten.
    """
    owner, prerequisites, state = case
    if actual_original is None:
        plan, predecessor = declare(case)
        original = refresh_read(case)
    else:
        from rocell.application.physical_camera_usb_qualification import (
            UsbQualificationPlan,
        )

        original = actual_original
        plan = UsbQualificationPlan(
            canonical(original["usb_qualification_trial"]["plan"]["document"])
        )
    trial_row = original["usb_qualification_trial"]
    plan_ref = _parse_evidence_reference(trial_row["plan"]["reference"])
    now = trial_row["declaration_event"]["occurred_at_ns"] + 100
    refs, subjects = {}, {}
    made = SimpleNamespace(
        case=case,
        plan=plan,
        plan_ref=plan_ref,
        original=original,
        refs=refs,
        subjects=subjects,
        phase_id=PHASE_ID,
        now=now,
    )

    def advance(name, status, evidence):
        made.now += 100
        state["advance"](
            status,
            codec.usb_phase_event(name, PHASE_ID),
            evidence,
            stage=STAGE_ORDER[3],
        )
        if actual_original is None:
            change_last_event(state, occurred_at_ns=made.now)
        else:
            state["events"] = state["snapshot"]().committed_events
            made.now = state["events"][-1].occurred_at_ns
        return state["events"][-1]

    def retain(role, subject):
        raw = subject if type(subject) is bytes else subject.payload
        subjects[role] = subject
        refs[role] = state["add"](
            raw, label=codec.usb_phase_label(role, PHASE_ID), stage=STAGE_ORDER[3]
        )
        return refs[role]

    made.advance, made.retain = advance, retain
    advance("ENTERED", V2StageState.BLOCKED, (plan_ref,))
    if stop == "entered":
        return made
    start = advance("PREPARATION_REQUESTED", V2StageState.WAITING_OPERATOR, (plan_ref,))
    made.start = start
    if stop == "started":
        return made
    enrollment = fresh_enrollment(owner.descriptor()["source_sha256"], LAUNCH)
    retain("enrollment", canonical(enrollment))
    if stop == "enrollment":
        return made
    bound = plan.to_dict()["binding"]
    selected = selection_from_enrollment_snapshot(
        enrollment, source_sha256=bound["source_sha256"], launch_session_id=LAUNCH
    )
    runtime = registration.usb_identity_runtime_candidate(
        Path(owner.descriptor()["workspace"]), source_sha256=bound["source_sha256"]
    )
    policy = policy_module.usb_identity_stage_policy()
    operation = usb_identity_phase_operation(
        plan=plan,
        phase="BASELINE",
        operation_id=PHASE_ID,
        predecessor_sha256=None,
        selection=selected,
        runtime=runtime,
        policy=policy,
    )
    rd = runtime.to_dict()
    file_report = dict(
        schema="rocell.usb_identity_runtime_file_check.v1",
        runtime_registration_sha256=runtime.sha256,
        source_sha256=bound["source_sha256"],
        status="FILES_MATCHED",
        files=[
            dict(path=p, sha256=h, bytes=1)
            for p, h, _ in (
                *registration.FIXED_SOURCE_PINS,
                (
                    registration.BUILD_RECORD_PATH,
                    registration.BUILD_RECORD_SHA256,
                    32768,
                ),
                (rd["helper"]["path"], rd["helper"]["sha256"], 1048576),
            )
        ],
        physical_authority=False,
        hardware_qualified=False,
    )
    documents = (
        enrollment["generic_review"]["inventory_report"],
        enrollment["inventory_packet"],
        enrollment["identity_packet"],
    )
    ids = (
        enrollment["generic_review"]["operation_id"],
        enrollment["view"]["inventory_operation_id"],
        enrollment["view"]["identity"]["operation_id"],
    )
    ledger = dict(
        schema="rocell.usb_phase_metadata_acquisition_ledger.v1",
        source_sha256=bound["source_sha256"],
        session_id=bound["session_id"],
        launch_session_id=LAUNCH,
        trial_id=bound["trial_id"],
        phase_id=PHASE_ID,
        phase_started_at_utc_ns=start.occurred_at_ns,
        entries=[
            dict(
                role=role,
                action_id=action,
                operation_id=operation_id,
                started_at_utc_ns=made.now + i * 10 + 1,
                finished_at_utc_ns=made.now + i * 10 + 2,
                published_at_utc_ns=made.now + i * 10 + 3,
                document_sha256=digest(canonical(document)),
                result_sha256=digest(canonical({"modeled_result": i})),
                completion_logged=True,
            )
            for i, ((role, action), operation_id, document) in enumerate(
                zip(codec._ACQUISITIONS, ids, documents)
            )
        ],
    )
    args = dict(
        plan=plan,
        plan_reference=plan_ref,
        phase_start_event=start,
        phase_id=PHASE_ID,
        enrollment=canonical(enrollment),
        enrollment_reference=refs["enrollment"],
        acquisition_ledger=ledger,
        operation=operation,
        runtime_report=file_report,
        prepared_at_utc_ns=made.now + 50,
        operator_id="phase-operator",
    )
    made.preparation_args, made.runtime, made.operation, made.selection = (
        args,
        runtime,
        operation,
        selected,
    )
    retain("preparation", codec.build_usb_trial_baseline_preparation(**args))
    if stop == "preparation":
        return made
    advance(
        "PREPARED",
        V2StageState.REVIEW_PENDING,
        (refs["enrollment"], refs["preparation"]),
    )
    if stop == "prepared":
        return made
    policy_review = policy_module.UsbIdentityPolicyReview(
        canonical(
            dict(
                schema=policy_module.REVIEW_SCHEMA,
                **{
                    key: bound[key]
                    for key in (
                        "source_sha256",
                        "cell_id",
                        "session_id",
                        "header_sha256",
                    )
                },
                operator_id="phase-operator",
                reviewer_id="phase-reviewer",
                reviewed_at_utc_ns=made.now + 1,
                policy=policy.to_dict(),
                policy_sha256=policy.sha256,
                purpose="REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
                **policy_module._FLAGS
            )
        )
    )
    retain("policy_review", policy_review)
    if stop == "policy_review":
        return made
    sd = selected.identity_document
    runtime_review = registration.review_usb_identity_runtime(
        runtime,
        selection_sha256=selected.sha256,
        native_identity_sha256=sd["native_identity_sha256"],
        endpoint_sha256=sd["endpoint_sha256"],
        device_instance_id_sha256=digest(
            sd["metadata_review"]["observed_instance_id"].encode()
        ),
        operation_sha256=operation.sha256,
        operator_id="phase-operator",
        reviewer_id="phase-reviewer",
        launch_session_id=LAUNCH,
        reviewed_at_ns=made.now + 2,
    )
    retain("runtime_review", runtime_review)
    if stop == "runtime_review":
        return made
    review = runtime_review.to_dict()
    identity = policy_module.UsbIdentityAdmissionIdentity(
        canonical(
            dict(
                schema=policy_module.IDENTITY_SCHEMA,
                **{
                    key: bound[key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                },
                stage_policy_sha256=policy.sha256,
                policy_review_sha256=policy_review.sha256,
                runtime_review_sha256=runtime_review.sha256,
                runtime_registration_sha256=runtime.sha256,
                original_subjects=[
                    dict(
                        role=name,
                        reference=refs[role].to_dict(),
                        document_sha256=refs[role].payload_sha256,
                    )
                    for name, role in (
                        ("metadata", "enrollment"),
                        ("policy_review", "policy_review"),
                        ("runtime_review", "runtime_review"),
                    )
                ],
                **{
                    key: review[key]
                    for key in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                        "device_instance_id_sha256",
                        "operation_sha256",
                    )
                }
            )
        )
    )
    retain("identity", identity)
    if stop == "identity":
        return made
    retain(
        "boot_request",
        build_usb_trial_boot_intent(
            plan=plan,
            plan_reference=plan_ref,
            phase_start_event=start,
            phase_id=PHASE_ID,
            launch_session_id=LAUNCH,
        ),
    )
    if stop == "boot_request":
        return made
    advance("REVIEWED", V2StageState.BLOCKED, refs.values())
    return made


@pytest.mark.parametrize(
    "stop,status",
    [
        ("entered", "ENTERED"),
        ("started", "PREPARATION_REQUESTED"),
        ("enrollment", "INCOMPLETE"),
        ("preparation", "INCOMPLETE"),
        ("prepared", "PREPARED"),
        ("policy_review", "INCOMPLETE"),
        ("runtime_review", "INCOMPLETE"),
        ("identity", "INCOMPLETE"),
        ("boot_request", "INCOMPLETE"),
        ("reviewed", "REVIEWED"),
    ],
)
def test_genuine_original_prefix_and_each_partial_role(ready, stop, status):
    made = phase_subjects(ready, stop=stop)
    result = refresh_read(ready)
    assert result["schema"] == session.SOURCE_WORKFLOW_USB_PHASE_SCHEMA
    assert result["usb_qualification_trial"] == made.original["usb_qualification_trial"]
    assert result["usb_qualification_baseline"]["state"] == status
    for role, ref in made.refs.items():
        record = result["usb_qualification_baseline"][role]
        assert canonical(record["document"]) == (
            made.subjects[role]
            if type(made.subjects[role]) is bytes
            else made.subjects[role].payload
        )
        assert record["reference"] == ref.to_dict()
    assert session._decode_cached_source_workflow(canonical(result)) == result
    assert all(
        row.state is V2StageState.PENDING for row in ready[2]["snapshot"]().stages[4:]
    )


def test_preparation_exact_ledger_inert_and_detached(ready, monkeypatch):
    made = phase_subjects(ready, stop="prepared")
    artifact = made.subjects["preparation"]

    def forbidden(*a, **k):
        pytest.fail("pure preparation replayed acquisition or filesystem work")

    monkeypatch.setattr(Path, "open", forbidden)
    args = made.preparation_args
    assert (
        codec.verify_usb_trial_baseline_preparation(
            artifact.payload,
            expected_sha256=artifact.sha256,
            **{
                key: args[key]
                for key in (
                    "plan",
                    "plan_reference",
                    "phase_start_event",
                    "phase_id",
                    "enrollment",
                    "enrollment_reference",
                )
            }
        )
        == artifact
    )
    assert len(artifact.payload) <= 128 * 1024
    d = artifact.to_dict()
    d["acquisition_ledger"]["entries"][0]["completion_logged"] = False
    with pytest.raises(ValueError):
        codec.UsbTrialBaselinePreparation(canonical(d))
    assert (
        artifact.to_dict()["acquisition_ledger"]["entries"][0]["completion_logged"]
        is True
    )


def test_partial_runtime_review_rejects_rehashed_other_launch(ready):
    made = phase_subjects(ready, stop="runtime_review")
    state = ready[2]
    old = made.refs["runtime_review"]
    document = made.subjects["runtime_review"].to_dict()
    document["launch_session_id"] = "wizard-" + "8" * 32
    changed = registration.UsbIdentityRuntimeReview(canonical(document))
    state["references"].remove(old)
    state["add"](
        changed.payload,
        label=codec.usb_phase_label("runtime_review", PHASE_ID),
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(session.PhysicalCameraSessionError, match="USB_PHASE"):
        refresh_read(ready)


def test_v10_does_not_relax_public_v9_or_unknown_original_roles(ready, monkeypatch):
    made = phase_subjects(ready, stop="prepared")
    captures = []
    verifier = session._verify_original_source_roles

    def capture(*args, **kwargs):
        captures.append(args)
        return verifier(*args, **kwargs)

    monkeypatch.setattr(session, "_verify_original_source_roles", capture)
    refresh_read(ready)
    args = captures[-1]
    with pytest.raises(session.PhysicalCameraSessionError):
        trial.verify_usb_qualification_trial_workflow(
            *args[:12], args[13], original_campaigns=args[12]
        )
    # Even a complete valid v10 does not admit an arbitrary extra stage4 role.
    ready[2]["add"](
        made.subjects["preparation"].payload,
        label="camera-usb-trial-baseline-unreviewed-extra-v1:" + PHASE_ID,
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)


@pytest.mark.parametrize("fault", ["event", "citations", "stage-pass"])
def test_rehashed_phase_events_keep_closed_original_order(ready, fault):
    phase_subjects(ready, stop="prepared")
    event = ready[2]["events"][-1]
    changes = (
        {"detail_code": "UNREVIEWED_USB_PHASE_EVENT"}
        if fault == "event"
        else (
            {"evidence": event.evidence[:1]}
            if fault == "citations"
            else {"state": V2StageState.PASS}
        )
    )
    change_last_event(ready[2], **changes)
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)
