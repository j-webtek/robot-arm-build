"""Full v12 history with MODELED storage, acquisition and campaign facts.

The actual source/role/phase codecs and full typed journal reader run. No M1
ownership qualification, provider, subprocess, CIM or USB device is executed.
"""

from dataclasses import asdict, replace
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import json
import time

import pytest

from rocell.application import physical_camera_usb_reconnect as codec
from rocell.application import physical_camera_usb_reconnect_readback as reader
from rocell.application import physical_camera_usb_absence_readback as absence_reader
from rocell.application import physical_usb_reconnect_boot as boot
from rocell.application import usb_identity_stage_policy as policy_module
from rocell.application import cell_commissioning_coordinator as core
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.physical_camera_usb_reconnect_constants import (
    USB_RECONNECT_ROLE_BYTES,
    USB_RECONNECT_STATES,
    SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA,
    usb_reconnect_event,
    usb_reconnect_label,
)
from rocell.application.physical_camera_selection import (
    selection_from_enrollment_snapshot,
)
from rocell.application.physical_usb_identity_campaign import (
    usb_identity_phase_operation,
    PhysicalUsbIdentityCampaign,
)
from rocell.application.physical_usb_reconnect_phase import (
    build_usb_reconnect_operator_event,
    build_usb_reconnect_qualification_phase,
)
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.host_boot_observation import (
    HostBootRequest,
    HostBootObservation,
)
from test_physical_camera_usb_absence_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    refresh_read,
    session,
    STAGE_ORDER,
    V2StageState,
    canonical,
    digest,
    LAUNCH,
    change_last_event,
    absence_subjects,
    presence_result,
)
from test_physical_camera_usb_reconnect_preparation import (
    preparation_inputs,
    reissue_enrollment,
)
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_physical_usb_reconnect_phase import modeled_reconnect_run
from test_physical_camera_coordinator import admission

PHASE = "usbphase-" + "f" * 32
ACTOR = "MODELED-reconnect-operator"


def reconnect_subjects(case, monkeypatch, *, stop="reviewed", checkpoint=None):
    prior = absence_subjects(case, monkeypatch, stop="query")
    presence_result(prior)
    workflow = refresh_read(case)
    original = codec.original_usb_reconnect_predecessor(workflow)
    made = SimpleNamespace(
        case=case,
        prior=prior,
        original=workflow,
        predecessor=original,
        plan=original["original_baseline"]["plan"],
        refs={},
        subjects={},
        now=prior.now + 1000,
        campaign_originals=(),
    )
    state = case[2]

    def capture(name):
        if checkpoint is not None:
            checkpoint(name, made)
        return name == stop

    def advance(kind, stage, refs):
        made.now += 1000
        state["advance"](
            stage,
            usb_reconnect_event(kind, PHASE),
            tuple(sorted(refs, key=lambda r: r.evidence_id)),
            stage=STAGE_ORDER[3],
        )
        change_last_event(state, occurred_at_ns=made.now)
        return state["events"][-1]

    def retain(role, value):
        raw = value if type(value) is bytes else value.payload
        made.subjects[role] = value
        made.refs[role] = state["add"](
            raw, label=usb_reconnect_label(role, PHASE), stage=STAGE_ORDER[3]
        )
        return made.refs[role]

    made.advance, made.retain = advance, retain
    monkeypatch.setattr(
        absence_reader,
        "read_original_usb_absence_campaigns",
        lambda *a, **k: {
            "identity": prior.baseline.campaign_originals + made.campaign_originals,
            "presence": prior.campaign_originals,
        },
    )
    made.start = advance(
        "PREPARATION_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        (original["absence_reference"],),
    )
    if capture("started"):
        return made
    operator = build_usb_reconnect_operator_event(
        plan=made.plan,
        absence=original["absence"],
        phase_id=PHASE,
        launch_session_id=LAUNCH,
        operator_id=ACTOR,
        phase_started_at_utc_ns=made.start.occurred_at_ns,
        reported_at_utc_ns=made.now + 1,
    )
    retain("operator_event", operator)
    if capture("operator_event"):
        return made
    b = made.plan.to_dict()["binding"]
    native = usb_native_enrollment(
        b["source_sha256"], LAUNCH, suffix="MODELED-readback-reconnect"
    )
    native = reissue_enrollment(
        native,
        (
            "MODELED-reconnect-generic",
            "MODELED-reconnect-inventory",
            "MODELED-reconnect-identity",
        ),
    )
    retain("enrollment", canonical(native))
    if capture("enrollment"):
        return made
    selected = selection_from_enrollment_snapshot(
        native, source_sha256=b["source_sha256"], launch_session_id=LAUNCH
    )
    runtime = registration.usb_identity_runtime_candidate(
        Path(case[0].descriptor()["workspace"]), source_sha256=b["source_sha256"]
    )
    policy = policy_module.usb_identity_stage_policy()
    operation = usb_identity_phase_operation(
        plan=made.plan,
        phase="AFTER_RECONNECT",
        operation_id=PHASE,
        predecessor_sha256=original["absence"].sha256,
        selection=selected,
        runtime=runtime,
        policy=policy,
    )
    args = preparation_inputs(
        original_baseline=original["original_baseline"],
        absence=original["absence"],
        absence_sources=original["absence_sources"],
        operator_event=operator,
        operation=operation,
        enrollment=canonical(native),
    )
    args.update(
        absence_reference=original["absence_reference"],
        phase_start_event=made.start,
        operator_event_reference=made.refs["operator_event"],
        enrollment_reference=made.refs["enrollment"],
    )
    preparation = codec.build_usb_reconnect_preparation(**args)
    made.operation, made.runtime, made.selection = operation, runtime, selected
    retain("preparation", preparation)
    if capture("preparation"):
        return made
    retain("operation", operation)
    if capture("operation"):
        return made
    advance("PREPARED", V2StageState.REVIEW_PENDING, made.refs.values())
    if capture("prepared"):
        return made
    policy_review = policy_module.UsbIdentityPolicyReview(
        canonical(
            dict(
                schema=policy_module.REVIEW_SCHEMA,
                **{
                    k: b[k]
                    for k in ("source_sha256", "cell_id", "session_id", "header_sha256")
                },
                operator_id=ACTOR,
                reviewer_id="MODELED-reconnect-reviewer",
                reviewed_at_utc_ns=made.now + 1,
                policy=policy.to_dict(),
                policy_sha256=policy.sha256,
                purpose="REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
                **policy_module._FLAGS,
            )
        )
    )
    retain("policy_review", policy_review)
    if capture("policy_review"):
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
        operator_id=ACTOR,
        reviewer_id="MODELED-reconnect-reviewer",
        launch_session_id=LAUNCH,
        reviewed_at_ns=made.now + 2,
    )
    retain("runtime_review", runtime_review)
    if capture("runtime_review"):
        return made
    rd = runtime_review.to_dict()
    identity = policy_module.UsbIdentityAdmissionIdentity(
        canonical(
            dict(
                schema=policy_module.IDENTITY_SCHEMA,
                **{
                    k: b[k]
                    for k in ("cell_id", "session_id", "source_sha256", "header_sha256")
                },
                stage_policy_sha256=policy.sha256,
                policy_review_sha256=policy_review.sha256,
                runtime_review_sha256=runtime_review.sha256,
                runtime_registration_sha256=runtime.sha256,
                original_subjects=[
                    dict(
                        role=name,
                        reference=made.refs[role].to_dict(),
                        document_sha256=made.refs[role].payload_sha256,
                    )
                    for name, role in (
                        ("metadata", "enrollment"),
                        ("policy_review", "policy_review"),
                        ("runtime_review", "runtime_review"),
                    )
                ],
                **{
                    k: rd[k]
                    for k in (
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
    if capture("identity"):
        return made
    retain(
        "boot_request",
        boot.build_usb_reconnect_boot_intent(
            preparation=preparation, preparation_reference=made.refs["preparation"]
        ),
    )
    if capture("boot_request"):
        return made
    advance("REVIEWED", V2StageState.BLOCKED, made.refs.values())
    capture("reviewed")
    return made


def reconnect_boot(
    made, monkeypatch, *, kind="observed", retain_only=False, terminal=None
):
    import test_physical_usb_trial_boot as boot_fixture

    made.advance(
        "BOOT_REQUESTED", V2StageState.WAITING_OPERATOR, (made.refs["boot_request"],)
    )
    if kind == "requested":
        return
    b = made.plan.to_dict()["binding"]
    monkeypatch.setattr(boot_fixture, "WALL", made.now + 1)
    request = HostBootRequest(
        b["source_sha256"],
        b["session_id"],
        LAUNCH,
        PHASE,
        b["trial_id"],
        "AFTER_RECONNECT",
        time.monotonic_ns() + 29_000_000_000,
    )
    raw = boot_fixture.owned_report(
        request, fault="unknown" if kind == "uncertain" else None
    ).to_dict()
    raw["origin"] = "WINDOWS_LOCAL_CIM"  # Physical-shaped MODEL, never executed CIM.
    report = HostBootObservation(canonical(raw))
    made.retain("host_boot", report)
    made.now = max(made.now, report.to_dict()["execution"]["finished_utc_ns"])
    if not retain_only:
        name = terminal or boot._terminal(
            report,
            HostBootObservation(made.predecessor["absence_sources"]["host_boot"]),
        )
        made.advance(
            name,
            (
                V2StageState.SIDE_EFFECT_UNCERTAIN
                if name == "BOOT_UNCERTAIN"
                else V2StageState.BLOCKED
            ),
            (made.refs["boot_request"], made.refs["host_boot"]),
        )


def reconnect_query(made, *, stop="retained", unknown=False):
    made.advance(
        "QUERY_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        (made.refs["identity"], made.refs["boot_request"], made.refs["host_boot"]),
    )
    if stop == "requested":
        return
    snapshot = made.case[2]["snapshot"]()
    b = made.plan.to_dict()["binding"]
    identity = made.subjects["identity"]
    campaign = PhysicalUsbIdentityCampaign(
        made.operation, identity=identity, review=made.subjects["runtime_review"]
    )
    facts = dict(
        stage_policy=policy_module.usb_identity_stage_policy().to_dict(),
        hazard_assessment={"MODELED_ONLY": True},
        configuration_epochs=[{"MODELED_DOMAIN": i} for i in range(8)],
        selected_identity=identity.to_dict(),
    )
    values = asdict(admission())
    values.update(
        cell_id=b["cell_id"],
        session_id=b["session_id"],
        stage=STAGE_ORDER[3],
        stage_state=V2StageState.WAITING_OPERATOR,
        stage_revision=len(snapshot.committed_events),
        journal_head_sha256=snapshot.head.head_sha256,
        evidence_inventory_sha256=canonical_sha256(
            [r.to_dict() for r in snapshot.evidence]
        ),
        selected_identity_sha256=identity.sha256,
        hazard_assessment_sha256=digest(canonical(facts["hazard_assessment"])),
        configuration_epoch_hashes=tuple(
            digest(canonical(x)) for x in facts["configuration_epochs"]
        ),
    )
    admitted = core.UsbIdentityAdmissionSnapshot(
        **values,
        usb_query_policy_sha256=policy_module.usb_identity_stage_policy().sha256,
    )
    permit = core.ExactOperationPermit(
        "attempt-" + "8" * 32,
        core.RegisteredActionRequest(
            b["cell_id"],
            b["session_id"],
            campaign.registration().action_id,
            "MODELED-reconnect-query",
            admitted.challenge_sha256,
        ),
        admitted,
        campaign.registration(),
        100,
        30_000_000_100,
        "9" * 64,
    )
    run = modeled_reconnect_run(
        campaign.preparation_for_permit(permit), utc=made.now + 1
    )
    counts = run.actual_counts
    receipt = (
        None
        if unknown
        else core.WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            campaign.worker_executable_sha256,
            identity.sha256,
            core.EffectCertainty.CONFIRMED,
            True,
            core.ObservedPowerState.UNKNOWN,
            0,
            counts["hub_open_attempts"],
            counts["api_calls"]
            - counts["hub_open_attempts"]
            - counts["close_attempts"],
            0,
            counts["close_attempts"],
            len(run.payload),
            (run.sha256,),
            campaign.composition,
        )
    )
    status = AttemptState.SEALED_UNCERTAIN if unknown else AttemptState.SEALED_KNOWN
    result = core.AttemptResult(
        permit.attempt_id,
        status,
        permit.permit_sha256,
        ("MODELED_UNKNOWN",) if unknown else (),
        receipt,
        unknown,
        campaign.composition,
    )
    original = dict(
        permit=asdict(permit),
        result=asdict(result),
        admission_evidence=facts,
        evidence=run.to_dict(),
        evidence_sha256=run.sha256,
        reference=dict(
            schema="rocell.usb_identity_campaign_reference.v1",
            cell_id=b["cell_id"],
            session_id=b["session_id"],
            attempt_id=permit.attempt_id,
            permit_sha256=permit.permit_sha256,
            evidence_sha256=run.sha256,
            payload_bytes=len(run.payload),
            label="physical-native-usb-identity",
        ),
        retention="M1_FULL_BYTES_READ_BACK",
    )
    made.campaign_originals = (
        json.loads(
            canonical(
                dict(
                    original=original,
                    event=dict(
                        attempt_id=permit.attempt_id,
                        operation_binding_sha256=permit.permit_sha256,
                        state=status.value,
                    ),
                )
            )
        ),
    )
    if unknown or stop == "campaign":
        return
    made.retain("execution", run)
    if stop == "execution":
        return
    made.now += 5000
    role_map = {
        "operation": "operation",
        "operator_event": "operator_event",
        "native_enrollment": "enrollment",
        "owned_usb_run": "execution",
        "host_boot": "host_boot",
    }
    source = lambda role: (
        made.subjects[role]
        if type(made.subjects[role]) is bytes
        else made.subjects[role].payload
    )
    phase = build_usb_reconnect_qualification_phase(
        original_baseline=made.predecessor["original_baseline"],
        absence=made.predecessor["absence"],
        absence_sources=made.predecessor["absence_sources"],
        permit=permit,
        context=dict(
            launch_session_id=LAUNCH,
            operation_id=PHASE,
            operator_id=ACTOR,
            started_at_utc_ns=made.start.occurred_at_ns,
            finished_at_utc_ns=made.now,
        ),
        sources={k: source(v) for k, v in role_map.items()},
        references={k: made.refs[v] for k, v in role_map.items()},
    )
    made.retain("phase_record", phase)
    if stop != "phase_record":
        made.advance("RETAINED", V2StageState.BLOCKED, made.refs.values())


def test_full_reconnect_original_chain(ready, monkeypatch):
    made = reconnect_subjects(ready, monkeypatch)
    reconnect_boot(made, monkeypatch)
    reconnect_query(made)
    workflow = refresh_read(ready)
    row = workflow["usb_qualification_reconnect"]
    assert workflow["schema"] == SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA
    assert row["state"] == "RETAINED_BLOCKED"
    assert len(row["events"]) == 7
    assert (
        len(made.refs) == 11 and sum(USB_RECONNECT_ROLE_BYTES.values()) == 1224 * 1024
    )
    assert (
        workflow["usb_qualification_absence"]
        == made.original["usb_qualification_absence"]
    )
    assert (
        workflow["usb_qualification_baseline"]
        == made.original["usb_qualification_baseline"]
    )
    for role, ref in made.refs.items():
        assert row[role]["reference"] == ref.to_dict()
        assert digest(canonical(row[role]["document"])) == ref.payload_sha256
    assert session._decode_cached_source_workflow(canonical(workflow)) == workflow
    assert all(
        s.state is V2StageState.PENDING for s in ready[2]["snapshot"]().stages[4:]
    )


def test_every_preparation_write_boundary_is_retained_without_completion(
    ready, monkeypatch
):
    expected = {
        "started": "INCOMPLETE",
        "operator_event": "PREPARATION_REQUESTED",
        "enrollment": "INCOMPLETE",
        "preparation": "INCOMPLETE",
        "operation": "INCOMPLETE",
        "prepared": "PREPARED",
        "policy_review": "INCOMPLETE",
        "runtime_review": "INCOMPLETE",
        "identity": "INCOMPLETE",
        "boot_request": "INCOMPLETE",
        "reviewed": "REVIEWED",
    }
    seen = []

    def checkpoint(name, made):
        result = refresh_read(ready)
        row = result["usb_qualification_reconnect"]
        assert row["state"] == expected[name], name
        assert len(row["events"]) <= 3
        assert {r for r in USB_RECONNECT_ROLE_BYTES if row[r]} == set(made.refs)
        assert row["original_campaign"] is None
        assert session._decode_cached_source_workflow(canonical(result)) == result
        seen.append(name)

    reconnect_subjects(ready, monkeypatch, checkpoint=checkpoint)
    assert seen == list(expected)


@pytest.mark.parametrize(
    "kind,terminal,expected",
    [
        ("requested", None, "BOOT_REQUESTED"),
        ("observed", "BOOT_HELD", "BOOT_HELD"),
        ("uncertain", None, "BOOT_UNCERTAIN"),
        ("uncertain", "BOOT_HELD", None),
    ],
)
def test_original_boot_pending_conservative_hold_and_uncertainty(
    ready, monkeypatch, kind, terminal, expected
):
    made = reconnect_subjects(ready, monkeypatch)
    reconnect_boot(made, monkeypatch, kind=kind, terminal=terminal)
    if expected is None:
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(ready)
        return
    row = refresh_read(ready)["usb_qualification_reconnect"]
    assert row["state"] == expected and row["execution"] is None
    assert row["original_campaign"] is None
    if expected == "BOOT_HELD":
        assert row["host_boot"]["document"]["status"] == "OBSERVED_HOST_BOOT"
        reconnect_query(made, stop="requested")
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(ready)


@pytest.mark.parametrize("unknown", [False, True])
def test_query_pending_and_campaign_originals_never_invent_stage_transfer(
    ready, monkeypatch, unknown
):
    made = reconnect_subjects(ready, monkeypatch)
    reconnect_boot(made, monkeypatch)
    reconnect_query(made, stop="campaign", unknown=unknown)
    row = refresh_read(ready)["usb_qualification_reconnect"]
    assert row["state"] == "ORIGINAL_CAMPAIGN_HELD"
    assert row["original_campaign"] == made.campaign_originals[0]["original"]
    assert row["execution"] is None and row["phase_record"] is None
    if unknown:
        assert row["original_campaign"]["result"]["receipt"] is None
        assert row["original_campaign"]["result"]["quarantine_latched"] is True
    saved = made.campaign_originals
    made.campaign_originals = ()
    assert (
        refresh_read(ready)["usb_qualification_reconnect"]["state"] == "QUERY_REQUESTED"
    )
    made.campaign_originals = saved


def _captured_reconnect_call(args, *, campaigns=None, packages=None, snapshot=None):
    return reader.verify_usb_reconnect_workflow(
        args[0],
        args[1] if snapshot is None else snapshot,
        *args[2:12],
        args[13],
        args[14],
        args[15],
        args[17] if packages is None else packages,
        original_campaigns=args[12] if campaigns is None else campaigns,
        original_presence_campaigns=args[16],
    )


def test_v12_does_not_relax_public_v11_or_ignore_sibling_roles_and_events(
    ready, monkeypatch
):
    made = reconnect_subjects(ready, monkeypatch)
    captured = []
    original_verify = session._verify_original_source_roles

    def capture(*args, **kwargs):
        captured.append(args)
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(session, "_verify_original_source_roles", capture)
    refresh_read(ready)
    args = captured[-1]
    with pytest.raises(session.PhysicalCameraSessionError):
        absence_reader.verify_usb_absence_workflow(
            *args[:12],
            args[13],
            args[14],
            args[15],
            original_campaigns=args[12],
            original_presence_campaigns=args[16],
        )
    extra = replace(args[1].evidence[-1], evidence_id="e" * 64)
    with pytest.raises(session.PhysicalCameraSessionError):
        _captured_reconnect_call(
            args, snapshot=replace(args[1], evidence=args[1].evidence + (extra,))
        )
    for key in ("phase_id", "kind"):
        packages = deepcopy(args[17])
        packages[next(iter(packages))][key] = "invented"
        with pytest.raises(session.PhysicalCameraSessionError):
            _captured_reconnect_call(args, packages=packages)
    duplicate_family = args[12] + args[12]
    with pytest.raises(session.PhysicalCameraSessionError):
        _captured_reconnect_call(args, campaigns=duplicate_family)
    original_event = ready[2]["events"][-1]
    for changes in (
        {"detail_code": "UNREVIEWED_RECONNECT_EVENT"},
        {"evidence": ()},
        {"state": V2StageState.PASS},
    ):
        change_last_event(ready[2], **changes)
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(ready)
        ready[2]["events"][-1] = original_event
    ready[2]["add"](
        made.subjects["preparation"].payload,
        label="camera-usb-trial-reconnect-unknown-v1:" + PHASE,
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)


@pytest.mark.parametrize("value", [None, [], {}, True, "unknown"])
def test_cycle_free_closed_helpers_reject_untyped_kinds(value):
    with pytest.raises(ValueError):
        usb_reconnect_event(value, PHASE)
    with pytest.raises(ValueError):
        usb_reconnect_label(value, PHASE)


def test_exact_additive_role_and_state_caps():
    from rocell.application.physical_camera_usb_phase import USB_PHASE_ROLE_BYTES

    assert len(USB_RECONNECT_ROLE_BYTES) == 11 and len(USB_RECONNECT_STATES) == 11
    assert (
        sum(USB_RECONNECT_ROLE_BYTES.values())
        == sum(USB_PHASE_ROLE_BYTES.values()) + 88 * 1024
    )
    assert tuple(USB_RECONNECT_ROLE_BYTES)[2:4] == ("preparation", "operation")
