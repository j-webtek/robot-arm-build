"""Full v13 readback with MODELED storage, boot and USB observations.

The real complete journal, original-role and immutable subject verifiers run.
No process, CIM, device, real M1 lease, or physical qualification is claimed.
"""

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from rocell.application import physical_camera_usb_reboot as codec
from rocell.application import physical_camera_usb_reboot_readback as reader
from rocell.application import physical_usb_reboot_boot as boot
from rocell.application import cell_commissioning_coordinator as core
from rocell.application import usb_identity_stage_policy as policy_module
from rocell.application import physical_camera_usb_absence_readback as absence_reader
from rocell.application.physical_camera_usb_reboot_constants import (
    USB_REBOOT_ROLE_BYTES,
    USB_REBOOT_STATES,
    SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
    usb_reboot_label,
    usb_reboot_event,
)
from rocell.application.physical_camera_selection import (
    selection_from_enrollment_snapshot,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.physical_usb_identity_campaign import (
    usb_identity_phase_operation,
    PhysicalUsbIdentityCampaign,
)
from rocell.application.physical_usb_reboot_phase import (
    build_usb_reboot_operator_event,
    build_usb_reboot_qualification_phase,
)
from rocell.application.physical_received_camera_submission import (
    ReceivedCameraSubmission,
    ReceivedCameraSubmissionAssessment,
    ReceivedCameraSubmissionReview,
)
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.host_boot_observation import HostBootObservation, _utc_ns
from test_physical_camera_usb_reconnect_readback import (
    ready,
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
    change_last_event,
)
import test_physical_camera_usb_reconnect_readback as reconnect_fixture
import test_physical_received_camera_readback as received_fixture
from test_physical_camera_usb_reboot_preparation import preparation_inputs
from test_physical_camera_usb_reconnect_preparation import reissue_enrollment
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_physical_usb_reconnect_phase import modeled_reconnect_run
from test_physical_usb_reboot_phase import _modeled_boot
from test_physical_camera_coordinator import admission

PHASE = "usbphase-" + "1" * 32
REBOOT_LAUNCH = "wizard-MODELED-reboot-reader"
ACTOR = "MODELED-reboot-operator"


@pytest.fixture
def identity_ready(received_ready, monkeypatch):
    # Select matching MODEL serial before the receipt is retained. Never rewrite
    # any prior notebook, source, receipt, reference, or committed bytes.
    original = received_fixture.modeled_receipt

    def receipt(*args, **kwargs):
        notebook, assessment, inspection, other = original(*args, **kwargs)
        return (
            notebook,
            assessment,
            replace(inspection, observed_camera_serial="MODELED-ONLY"),
            other,
        )

    monkeypatch.setattr(received_fixture, "modeled_receipt", receipt)
    received_ready[2]["received_subjects"] = received_fixture.received_subjects(
        received_ready,
        observed=True,
        identity=True,
    )
    return received_ready


def received_trio(case, workflow):
    cycle = workflow["received_camera_cycles"][-1]
    return {
        role: cls(canonical(cycle[role]["document"]), case[1])
        for role, cls in (
            ("submission", ReceivedCameraSubmission),
            ("assessment", ReceivedCameraSubmissionAssessment),
            ("review", ReceivedCameraSubmissionReview),
        )
    }


def complete_v12(case, monkeypatch):
    prior = reconnect_fixture.reconnect_subjects(case, monkeypatch)
    reconnect_fixture.reconnect_boot(prior, monkeypatch)
    reconnect_fixture.reconnect_query(prior)
    # The earlier readback fixture's counter fields are intentionally modeled.
    # Build the exact nominal receipt required by the reboot predecessor adapter,
    # before this test treats its newly constructed v12 as the frozen predecessor.
    run = prior.subjects["execution"]
    counts = run.actual_counts
    receipt = prior.campaign_originals[0]["original"]["result"]["receipt"]
    receipt.update(
        opens=counts["hub_open_attempts"],
        reads=counts["api_calls"]
        - counts["hub_open_attempts"]
        - counts["close_attempts"],
        writes=0,
        frames=0,
        closes=counts["close_attempts"],
    )
    prior.original = refresh_read(case)
    assert (
        prior.subjects["phase_record"].to_dict()["status"]
        == "RECONNECT_OBSERVATIONS_RETAINED"
    )
    codec.original_usb_reboot_predecessor(
        prior.original, received=received_trio(case, prior.original)
    )
    return prior


def reboot_subjects(case, monkeypatch, *, stop="reviewed", checkpoint=None):
    prior = complete_v12(case, monkeypatch)
    workflow = prior.original
    original = codec.original_usb_reboot_predecessor(
        workflow, received=received_trio(case, workflow)
    )
    made = SimpleNamespace(
        case=case,
        prior=prior,
        original=workflow,
        predecessor=original,
        plan=original["original_baseline"]["plan"],
        refs={},
        subjects={},
        now=(prior.now // 1000 + 1) * 1000 + 1_000_000,
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
            usb_reboot_event(kind, PHASE),
            tuple(sorted(refs, key=lambda r: r.evidence_id)),
            stage=STAGE_ORDER[3],
        )
        change_last_event(state, occurred_at_ns=made.now)
        return state["events"][-1]

    def retain(role, value):
        raw = value if type(value) is bytes else value.payload
        made.subjects[role] = value
        made.refs[role] = state["add"](
            raw, label=usb_reboot_label(role, PHASE), stage=STAGE_ORDER[3]
        )
        return made.refs[role]

    made.advance, made.retain = advance, retain
    monkeypatch.setattr(
        absence_reader,
        "read_original_usb_absence_campaigns",
        lambda *a, **k: {
            "identity": prior.prior.baseline.campaign_originals
            + prior.campaign_originals
            + made.campaign_originals,
            "presence": prior.prior.campaign_originals,
        },
    )
    made.start = advance(
        "PREPARATION_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        (original["reconnect_reference"],),
    )
    if capture("started"):
        return made
    operator = build_usb_reboot_operator_event(
        plan=made.plan,
        reconnect=original["reconnect"],
        phase_id=PHASE,
        launch_session_id=REBOOT_LAUNCH,
        operator_id=ACTOR,
        phase_started_at_utc_ns=made.start.occurred_at_ns,
        reported_at_utc_ns=made.now + 1,
    )
    retain("operator_event", operator)
    if capture("operator_event"):
        return made
    b = made.plan.to_dict()["binding"]
    native = usb_native_enrollment(
        b["source_sha256"], REBOOT_LAUNCH, suffix="MODELED-readback-reconnect"
    )
    native = reissue_enrollment(
        native,
        (
            "MODELED-reboot-generic",
            "MODELED-reboot-inventory",
            "MODELED-reboot-identity",
        ),
    )
    retain("enrollment", canonical(native))
    if capture("enrollment"):
        return made
    selected = selection_from_enrollment_snapshot(
        native, source_sha256=b["source_sha256"], launch_session_id=REBOOT_LAUNCH
    )
    runtime = registration.usb_identity_runtime_candidate(
        Path(case[0].descriptor()["workspace"]), source_sha256=b["source_sha256"]
    )
    policy = policy_module.usb_identity_stage_policy()
    operation = usb_identity_phase_operation(
        plan=made.plan,
        phase="AFTER_REBOOT",
        operation_id=PHASE,
        predecessor_sha256=original["reconnect"].sha256,
        selection=selected,
        runtime=runtime,
        policy=policy,
    )
    subject = SimpleNamespace(
        **original,
        event=operator,
        operation=operation,
        sources={"native_enrollment": canonical(native)},
        references={
            "operator_event": made.refs["operator_event"],
            "native_enrollment": made.refs["enrollment"],
        },
    )
    args = preparation_inputs(None, subject=subject)
    args.update(phase_start_event=made.start)
    preparation = codec.build_usb_reboot_preparation(**args)
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
                reviewer_id="MODELED-reboot-reviewer",
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
        reviewer_id="MODELED-reboot-reviewer",
        launch_session_id=REBOOT_LAUNCH,
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
        boot.build_usb_reboot_boot_intent(
            preparation=preparation,
            preparation_reference=made.refs["preparation"],
            reconnect=original["reconnect"],
            reconnect_reference=original["reconnect_reference"],
        ),
    )
    if capture("boot_request"):
        return made
    advance("REVIEWED", V2StageState.BLOCKED, made.refs.values())
    capture("reviewed")
    return made


def reboot_boot(
    made, monkeypatch, *, kind="observed", retain_only=False, terminal=None
):
    requested = made.advance(
        "BOOT_REQUESTED", V2StageState.WAITING_OPERATOR, (made.refs["boot_request"],)
    )
    if kind == "requested":
        return
    context = dict(
        operation_id=PHASE,
        launch_session_id=REBOOT_LAUNCH,
        operator_id=ACTOR,
        started_at_utc_ns=made.start.occurred_at_ns,
        finished_at_utc_ns=made.now + 10_000,
    )
    # Match the original request time without modifying any predecessor bytes.
    report_context = dict(context, started_at_utc_ns=made.now)
    epoch = made.start.occurred_at_ns // 1000 * 1000
    if kind == "same_boot":
        epoch = _utc_ns(
            json.loads(made.predecessor["reconnect_sources"]["host_boot"])["response"][
                "last_boot_up_time_utc"
            ]
        )
    report = _modeled_boot(
        made.plan,
        report_context,
        boot_epoch=epoch,
        origin="WINDOWS_LOCAL_CIM",
        host_change=False,
        cleanup_uncertain=kind == "uncertain",
    )
    made.retain("host_boot", report)
    made.now = report.to_dict()["execution"]["finished_utc_ns"]
    if not retain_only:
        name = terminal or boot.classify_usb_reboot_boot_observation(
            report,
            intent=made.subjects["boot_request"],
            expected_sha256=report.sha256,
            requested_event=requested,
            reconnect_boot=HostBootObservation(
                made.predecessor["reconnect_sources"]["host_boot"]
            ),
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


def reboot_query(made, *, stop="retained", unknown=False):
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
        "attempt-" + "b" * 32,
        core.RegisteredActionRequest(
            b["cell_id"],
            b["session_id"],
            campaign.registration().action_id,
            "MODELED-reboot-query",
            admitted.challenge_sha256,
        ),
        admitted,
        campaign.registration(),
        100,
        30_000_000_100,
        "b" * 64,
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
            counts["hub_open_attempts"],
            counts["api_calls"]
            - counts["hub_open_attempts"]
            - counts["close_attempts"],
            0,
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
    phase = build_usb_reboot_qualification_phase(
        **made.predecessor,
        permit=permit,
        context=dict(
            launch_session_id=REBOOT_LAUNCH,
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


def test_full_original_reboot_suffix(ready, monkeypatch):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch)
    reboot_query(made)
    workflow = refresh_read(ready)
    row = workflow["usb_qualification_reboot"]
    assert workflow["schema"] == SOURCE_WORKFLOW_USB_REBOOT_SCHEMA
    assert row["state"] == "RETAINED_BLOCKED"
    assert row["phase_record"]["document"]["status"] == "REBOOT_OBSERVATIONS_RETAINED"
    assert len(row["events"]) == 7 and len(made.refs) == 11
    for key in (
        "usb_qualification_baseline",
        "usb_qualification_absence",
        "usb_qualification_reconnect",
    ):
        assert workflow[key] == made.original[key]
    for role, ref in made.refs.items():
        assert row[role]["reference"] == ref.to_dict()
        assert digest(canonical(row[role]["document"])) == ref.payload_sha256
    assert session._decode_cached_source_workflow(canonical(workflow)) == workflow
    assert all(
        s.state is V2StageState.PENDING for s in ready[2]["snapshot"]().stages[4:]
    )


def test_every_preparation_write_boundary_is_retained_without_replay(
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
        row = result["usb_qualification_reboot"]
        assert row["state"] == expected[name], name
        assert {role for role in USB_REBOOT_ROLE_BYTES if row[role]} == set(made.refs)
        assert row["original_campaign"] is None
        assert (
            result["usb_qualification_reconnect"]
            == made.original["usb_qualification_reconnect"]
        )
        seen.append(name)

    reboot_subjects(ready, monkeypatch, checkpoint=checkpoint)
    assert seen == list(expected)


@pytest.mark.parametrize(
    "kind,terminal,expected",
    [
        ("requested", None, "BOOT_REQUESTED"),
        ("observed", "BOOT_HELD", "BOOT_HELD"),
        ("same_boot", None, "BOOT_HELD"),
        ("uncertain", None, "BOOT_UNCERTAIN"),
        ("uncertain", "BOOT_HELD", None),
    ],
)
def test_boot_pending_conservative_hold_and_uncertainty(
    ready, monkeypatch, kind, terminal, expected
):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch, kind=kind, terminal=terminal)
    if expected is None:
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(ready)
        return
    row = refresh_read(ready)["usb_qualification_reboot"]
    assert row["state"] == expected
    assert row["execution"] is None and row["original_campaign"] is None
    if expected in {"BOOT_HELD", "BOOT_UNCERTAIN"}:
        reboot_query(made, stop="requested")
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(ready)


@pytest.mark.parametrize("unknown", [False, True])
def test_query_and_original_campaign_without_stage_transfer(
    ready, monkeypatch, unknown
):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch)
    reboot_query(made, stop="campaign", unknown=unknown)
    row = refresh_read(ready)["usb_qualification_reboot"]
    assert row["state"] == "ORIGINAL_CAMPAIGN_HELD"
    assert row["original_campaign"] == made.campaign_originals[0]["original"]
    assert row["execution"] is None and row["phase_record"] is None
    if unknown:
        assert row["original_campaign"]["result"]["receipt"] is None
        assert row["original_campaign"]["result"]["quarantine_latched"] is True
    saved = made.campaign_originals
    made.campaign_originals = ()
    assert refresh_read(ready)["usb_qualification_reboot"]["state"] == "QUERY_REQUESTED"
    made.campaign_originals = saved


def test_uncommitted_boot_and_terminal_transfer_roles_stay_incomplete(
    ready, monkeypatch
):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch, retain_only=True)
    row = refresh_read(ready)["usb_qualification_reboot"]
    assert row["state"] == "INCOMPLETE" and row["host_boot"] is not None
    made.advance(
        "BOOT_RETAINED",
        V2StageState.BLOCKED,
        (made.refs["boot_request"], made.refs["host_boot"]),
    )
    reboot_query(made, stop="phase_record")
    row = refresh_read(ready)["usb_qualification_reboot"]
    assert row["state"] == "ORIGINAL_CAMPAIGN_HELD"
    assert row["execution"] is not None and row["phase_record"] is not None
    assert len(row["events"]) == 6
    made.advance("RETAINED", V2StageState.BLOCKED, made.refs.values())
    assert (
        refresh_read(ready)["usb_qualification_reboot"]["state"] == "RETAINED_BLOCKED"
    )


def test_unknown_original_without_any_worker_bytes_is_retained(ready, monkeypatch):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch)
    reboot_query(made, stop="campaign", unknown=True)
    original = made.campaign_originals[0]["original"]
    original.update(
        evidence=None,
        evidence_sha256=None,
        reference=None,
        retention="M1_TERMINAL_READ_BACK_NO_EVIDENCE",
    )
    row = refresh_read(ready)["usb_qualification_reboot"]
    assert row["state"] == "ORIGINAL_CAMPAIGN_HELD"
    assert row["original_campaign"] == original
    assert row["original_campaign"]["result"]["receipt"] is None
    assert row["execution"] is None and row["phase_record"] is None


def test_reader_rejects_foreign_roles_events_aliases_and_sibling_campaigns(
    ready, monkeypatch
):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch)
    reboot_query(made)
    captured = []
    original_verify = reader.verify_usb_reboot_workflow

    def capture(*args, **kwargs):
        captured.append((args, kwargs))
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(reader, "verify_usb_reboot_workflow", capture)
    refresh_read(ready)
    args, kwargs = captured[-1]
    baseline = deepcopy(args[-1])

    def rejects(*, packages=None, snapshot=None, campaigns=None):
        modified = list(args)
        modified[-1] = baseline if packages is None else packages
        if snapshot is not None:
            modified[1] = snapshot
        options = dict(kwargs)
        if campaigns is not None:
            options["original_campaigns"] = campaigns
        with pytest.raises(session.PhysicalCameraSessionError):
            original_verify(*modified, **options)

    packages = deepcopy(baseline)
    next(iter(packages.values()))["kind"] = "unknown"
    rejects(packages=packages)
    packages = deepcopy(baseline)
    key = next(iter(packages))
    packages[key]["record"]["evidence_sha256"] = "0" * 64
    rejects(packages=packages)
    packages = deepcopy(baseline)
    next(iter(packages.values()))["phase_id"] = "usbphase-" + "9" * 32
    rejects(packages=packages)
    packages = deepcopy(baseline)
    packages["unexpected-original"] = deepcopy(next(iter(packages.values())))
    rejects(packages=packages)
    campaigns = kwargs["original_campaigns"]
    rejects(campaigns=campaigns + (campaigns[-1],))
    rejects(campaigns=campaigns[:-1])
    snapshot = args[1]
    changed = replace(snapshot.committed_events[-1], detail_code="UNKNOWN_REBOOT_EVENT")
    rejects(
        snapshot=replace(
            snapshot, committed_events=snapshot.committed_events[:-1] + (changed,)
        )
    )
    # Public v12 cannot silently consume the new namespace/inventory.
    with pytest.raises(session.PhysicalCameraSessionError):
        reconnect_fixture.reader.verify_usb_reconnect_workflow(
            *args[:-1],
            **kwargs,
        )
