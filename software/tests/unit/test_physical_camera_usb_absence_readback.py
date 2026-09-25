"""Full original v11 grammar with explicitly MODELED storage and OS facts.

Every value is reconstructed by production codecs. No process/device/CIM API
is executed; this fixture does not assert actual M1 or physical qualification.
"""

from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from pathlib import Path
import time

import pytest

from rocell.application import physical_camera_usb_absence as codec
from rocell.application import physical_camera_usb_absence_readback as reader
from rocell.application.physical_camera_usb_absence_constants import (
    USB_ABSENCE_ROLE_BYTES,
    USB_ABSENCE_STATES,
    usb_absence_event,
    usb_absence_label,
)
from rocell.application.physical_usb_presence_binding import (
    build_usb_presence_phase_binding,
)
from rocell.application.physical_usb_presence_campaign import usb_presence_operation
from rocell.application.physical_usb_presence_phase import (
    build_usb_presence_operator_event,
)
from rocell.application import physical_usb_absence_boot as boot
from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy
from rocell.providers.windows import usb_presence_registration as registration
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.providers.windows import usb_identity_protocol as wire
from rocell.providers.windows.host_boot_observation import (
    HostBootRequest,
    HostBootObservation,
)
from rocell.providers.windows.usb_presence_review import review_usb_presence_runtime
from test_physical_camera_usb_phase_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    phase_subjects,
    refresh_read,
    session,
    STAGE_ORDER,
    V2StageState,
    canonical,
    digest,
    LAUNCH,
    change_last_event,
)
import test_physical_camera_usb_phase_readback as baseline_fixture
import test_physical_camera_usb_phase_results as baseline_results
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_physical_usb_presence_binding import observed_native

PHASE = "usbphase-" + "e" * 32


def presence_result(made, *, unknown=False, stop="retained", outcome="ABSENT"):
    """Pure modeled attempt/facts; genuine strict permit and owned-result codecs."""
    from rocell.application import cell_commissioning_coordinator as core
    from rocell.application.physical_onboarding_attempts import AttemptState
    from rocell.application.physical_onboarding_durability import canonical_sha256
    from rocell.application.commissioning_camera_persistence import (
        physical_camera_source_binding,
    )
    from rocell.application.physical_usb_presence_campaign import (
        PhysicalUsbPresenceCampaign,
    )
    from rocell.application.physical_usb_presence_phase import (
        build_usb_presence_qualification_phase,
    )
    from rocell.providers.windows import owned_usb_presence_evidence as evidence
    from test_physical_camera_coordinator import admission
    from test_physical_usb_presence_dispatch import modeled_owned_presence

    snapshot = made.case[2]["snapshot"]()
    b = made.binding.to_dict()["binding"]
    review = made.subjects["runtime_review"]
    campaign = PhysicalUsbPresenceCampaign(made.subjects["operation"], review=review)
    facts = dict(
        stage_policy=usb_presence_stage_policy().to_dict(),
        hazard_assessment={"MODELED_ONLY": True},
        configuration_epochs=[{"MODELED_UNOBSERVED_DOMAIN": i} for i in range(8)],
        selected_identity=made.binding.to_dict(),
        runtime_review=review.to_dict(),
        runtime_review_reference=made.refs["runtime_review"].to_dict(),
        runtime_review_event=snapshot.committed_events[-2].to_dict(),
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
        source_binding_sha256=physical_camera_source_binding(b["source_sha256"]),
        selected_identity_sha256=made.binding.sha256,
        hazard_assessment_sha256=digest(canonical(facts["hazard_assessment"])),
        configuration_epoch_hashes=tuple(
            digest(canonical(x)) for x in facts["configuration_epochs"]
        ),
    )
    admitted = core.UsbPresenceAdmissionSnapshot(
        **values,
        usb_presence_policy_sha256=usb_presence_stage_policy().sha256,
        phase_binding_sha256=made.binding.sha256,
        runtime_review_sha256=review.sha256,
    )
    permit = core.ExactOperationPermit(
        "attempt-" + "7" * 32,
        core.RegisteredActionRequest(
            b["cell_id"],
            b["session_id"],
            campaign.registration().action_id,
            "MODELED-absence-query",
            admitted.challenge_sha256,
        ),
        admitted,
        campaign.registration(),
        100,
        30_000_000_100,
        "6" * 64,
    )
    prepared = campaign.preparation_for_permit(permit)
    checks = [
        dict(
            boundary=name,
            started_ns=200 + i * 10,
            finished_ns=201 + i * 10,
            passed=True,
        )
        for i, name in enumerate(evidence.BOUNDARIES)
    ]
    run = modeled_owned_presence(
        prepared,
        deadline_ns=25_000_000_100,
        checks=checks,
        started_ns=101,
        started_utc_ns=made.now + 1,
        finished_ns=1000,
        finished_utc_ns=made.now + 400_000_000,
        missing_result=unknown,
        outcome=outcome,
    )
    status = AttemptState.SEALED_UNCERTAIN if unknown else AttemptState.SEALED_KNOWN
    receipt = (
        None
        if unknown
        else core.WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            campaign.worker_executable_sha256,
            made.binding.sha256,
            core.EffectCertainty.CONFIRMED,
            True,
            core.ObservedPowerState.UNKNOWN,
            0,
            0,
            1 if outcome == "HELD" else 4,
            0,
            0,
            len(run.payload),
            (run.sha256,),
            campaign.composition,
        )
    )
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
            schema="rocell.usb_presence_campaign_reference.v1",
            cell_id=b["cell_id"],
            session_id=b["session_id"],
            attempt_id=permit.attempt_id,
            permit_sha256=permit.permit_sha256,
            evidence_sha256=run.sha256,
            payload_bytes=len(run.payload),
            label="physical-native-usb-presence",
        ),
        retention="M1_FULL_BYTES_READ_BACK",
    )
    import json

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
        return made
    made.retain("execution", run)
    if stop == "execution":
        return made
    made.now += 500_000_000
    source_roles = {
        "operation": "operation",
        "operator_event": "operator_event",
        "owned_presence_run": "execution",
        "host_boot": "host_boot",
    }
    phase = build_usb_presence_qualification_phase(
        original_baseline=made.original_baseline,
        context=dict(
            launch_session_id=LAUNCH,
            operation_id=PHASE,
            operator_id=made.subjects["operator_event"].to_dict()["operator_id"],
            started_at_utc_ns=made.start.occurred_at_ns,
            finished_at_utc_ns=made.now,
        ),
        sources={k: made.subjects[v].payload for k, v in source_roles.items()},
        references={k: made.refs[v] for k, v in source_roles.items()},
    )
    made.retain("phase_record", phase)
    if stop != "phase_record":
        made.advance("RETAINED", V2StageState.BLOCKED, made.refs.values())
    return made


def modeled_observed(prepared):
    """Construct complete raw descriptors plus declared ownership, no launch."""
    raw = baseline_results.modeled_clean_held_evidence(prepared).to_dict()
    ready_wire = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)[
        : raw["ready_length"]
    ]
    ready = wire.UsbIdentityReady(ready_wire.rstrip(b"\n"))
    result = dict(
        schema=wire.RESULT_SCHEMA,
        request_sha256=prepared.request.request_sha256,
        child_pid=31415,
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=prepared.request.to_dict()["permit_sha256"],
        native_receipt=observed_native(prepared.request).to_dict(),
    )
    raw["process"]["returncode"] = 0
    raw.update(
        status="OBSERVED",
        stdout=owned.stream_record(ready_wire + canonical(result), complete=True),
    )
    return owned.OwnedUsbIdentityRunEvidence(canonical(raw))


def nominal_original(case, monkeypatch):
    monkeypatch.setattr(baseline_fixture, "fresh_enrollment", usb_native_enrollment)
    made = phase_subjects(case)
    baseline_results.phase_boot(made, monkeypatch)
    old = baseline_results.modeled_clean_held_evidence

    # Capture the fixed no-process skeleton before replacing only this test helper.
    def observed(prepared):
        with monkeypatch.context() as local:
            local.setattr(baseline_results, "modeled_clean_held_evidence", old)
            return modeled_observed(prepared)

    monkeypatch.setattr(baseline_results, "modeled_clean_held_evidence", observed)
    baseline_results.phase_query(made, monkeypatch)
    # Receipt counters describe the explicit modeled native trace, not zero effects.
    counts = made.subjects["execution"].bounded_effect_summary()["actual_counts"]
    receipt = made.campaign_originals[0]["original"]["result"]["receipt"]
    receipt.update(
        opens=counts["hub_open_attempts"],
        reads=counts["api_calls"]
        - counts["hub_open_attempts"]
        - counts["close_attempts"],
        closes=counts["close_attempts"],
    )
    made.original = refresh_read(case)
    assert (
        made.original["usb_qualification_baseline"]["phase_record"]["document"][
            "status"
        ]
        == "OBSERVATIONS_RETAINED"
    )
    codec.original_usb_absence_baseline(made.original)
    return made


def absence_subjects(
    case, monkeypatch, *, stop="prepared", terminal=None, uncertain=False
):
    """Reusable exact full history, with modeled storage and physical observations."""
    base = nominal_original(case, monkeypatch)
    original_baseline = codec.original_usb_absence_baseline(base.original)
    binding = build_usb_presence_phase_binding(**original_baseline)
    runtime = registration.usb_presence_runtime_candidate(
        Path(case[0].descriptor()["workspace"]),
        source_sha256=case[0].descriptor()["source_sha256"],
    )
    made = SimpleNamespace(
        case=case,
        baseline=base,
        original_baseline=original_baseline,
        binding=binding,
        runtime=runtime,
        refs={},
        subjects={},
        now=base.now + 1000,
    )
    state = case[2]

    def advance(kind, stage, refs):
        made.now += 1000
        state["advance"](
            stage,
            usb_absence_event(
                kind, PHASE, trial_id=base.plan.to_dict()["binding"]["trial_id"]
            ),
            tuple(sorted(refs, key=lambda r: r.evidence_id)),
            stage=STAGE_ORDER[3],
        )
        change_last_event(state, occurred_at_ns=made.now)
        return state["events"][-1]

    def retain(role, value):
        raw = value if type(value) is bytes else value.payload
        made.subjects[role] = value
        made.refs[role] = state["add"](
            raw, label=usb_absence_label(role, PHASE), stage=STAGE_ORDER[3]
        )
        return made.refs[role]

    made.advance, made.retain = advance, retain
    made.start = advance(
        "PREPARATION_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        (original_baseline["baseline_reference"],),
    )
    monkeypatch.setattr(
        reader,
        "read_original_usb_absence_campaigns",
        lambda *a, **k: {
            "identity": base.campaign_originals,
            "presence": getattr(made, "campaign_originals", ()),
        },
    )
    if stop == "started":
        return made
    operation = usb_presence_operation(
        phase_binding=binding,
        runtime=runtime,
        policy=usb_presence_stage_policy(),
        operation_id=PHASE,
        launch_session_id=LAUNCH,
        request_nonce="f" * 64,
    )
    retain("operation", operation)
    if stop == "operation":
        return made
    operator = build_usb_presence_operator_event(
        phase_binding=binding,
        phase_id=PHASE,
        launch_session_id=LAUNCH,
        operator_id="MODELED-absence-operator",
        phase_started_at_utc_ns=made.start.occurred_at_ns,
        reported_at_utc_ns=made.now + 1,
    )
    retain("operator_event", operator)
    made.args = dict(
        operation=operation,
        operation_reference=made.refs["operation"],
        operator_event=operator,
        operator_event_reference=made.refs["operator_event"],
        phase_start_event=made.start,
        original_baseline=original_baseline,
    )
    report = dict(
        schema=registration.INSPECTION_SCHEMA,
        runtime_registration_sha256=runtime.sha256,
        source_sha256=operation.to_dict()["source_sha256"],
        status="FILES_MATCHED",
        files=[
            dict(path=p, sha256=h, bytes=n)
            for p, h, n in (
                *registration.FIXED_SOURCE_PINS,
                (
                    registration.BUILD_RECORD_PATH,
                    registration.BUILD_RECORD_SHA256,
                    registration.BUILD_RECORD_BYTES,
                ),
                (
                    registration.HELPER_PATH,
                    registration.HELPER_SHA256,
                    registration.HELPER_BYTES,
                ),
            )
        ],
        **codec.FLAGS,
    )
    retain(
        "preparation",
        codec.build_usb_absence_preparation(
            **made.args, runtime_report=report, prepared_at_utc_ns=made.now + 10
        ),
    )
    retain("boot_intent", boot.build_usb_absence_boot_intent(**made.args))
    if stop == "uncommitted":
        return made
    advance("PREPARED", V2StageState.REVIEW_PENDING, made.refs.values())
    if stop == "prepared":
        return made
    retain(
        "boot_review",
        boot.review_usb_absence_boot_intent(
            made.subjects["boot_intent"],
            reviewer_id="MODELED-independent",
            launch_session_id=LAUNCH,
            reviewed_at_ns=made.now + 1,
        ),
    )
    advance(
        "BOOT_REVIEWED",
        V2StageState.BLOCKED,
        (made.refs["boot_intent"], made.refs["boot_review"]),
    )
    if stop == "reviewed":
        return made
    requested = advance(
        "BOOT_REQUESTED", V2StageState.WAITING_OPERATOR, (made.refs["boot_intent"],)
    )
    if stop == "requested":
        return made
    import test_physical_usb_trial_boot as boot_fixture

    monkeypatch.setattr(boot_fixture, "WALL", made.now + 1)
    b = base.plan.to_dict()["binding"]
    request = HostBootRequest(
        b["source_sha256"],
        b["session_id"],
        LAUNCH,
        PHASE,
        b["trial_id"],
        "RECONNECT_ABSENCE",
        time.monotonic_ns() + 29_000_000_000,
    )
    raw = boot_fixture.owned_report(
        request, fault="unknown" if uncertain else None
    ).to_dict()
    raw["origin"] = "WINDOWS_LOCAL_CIM"  # Explicit model, no physical acquisition.
    host = HostBootObservation(canonical(raw))
    retain("host_boot", host)
    made.now = max(made.now, host.to_dict()["execution"]["finished_utc_ns"])
    actual = boot._terminal(
        host, HostBootObservation(original_baseline["baseline_sources"]["host_boot"])
    )
    kind = terminal or actual
    advance(
        kind,
        (
            V2StageState.SIDE_EFFECT_UNCERTAIN
            if kind == "BOOT_UNCERTAIN"
            else V2StageState.BLOCKED
        ),
        (made.refs["boot_intent"], made.refs["host_boot"]),
    )
    if stop == "boot":
        return made
    assert kind == "BOOT_RETAINED"
    advance(
        "PRESENCE_REVIEW_REQUESTED", V2StageState.WAITING_OPERATOR, made.refs.values()
    )
    if stop == "presence_requested":
        return made
    advance("PRESENCE_REVIEW_PREPARED", V2StageState.REVIEW_PENDING, made.refs.values())
    if stop == "presence":
        return made
    review = review_usb_presence_runtime(
        runtime,
        phase_binding=binding,
        policy=usb_presence_stage_policy(),
        operation_sha256=operation.sha256,
        operator_id=operator.to_dict()["operator_id"],
        reviewer_id="MODELED-presence-reviewer",
        launch_session_id=LAUNCH,
        reviewed_at_ns=made.now + 1,
    )
    retain("runtime_review", review)
    advance("RUNTIME_REVIEWED", V2StageState.BLOCKED, (made.refs["runtime_review"],))
    if stop == "runtime":
        return made
    advance(
        "QUERY_REQUESTED", V2StageState.WAITING_OPERATOR, (made.refs["runtime_review"],)
    )
    return made


def test_full_original_preparation_readback_and_canonical_cache(ready, monkeypatch):
    made = absence_subjects(ready, monkeypatch)
    result = refresh_read(ready)
    row = result["usb_qualification_absence"]
    assert result["schema"].endswith(".v11") and row["state"] == "PREPARED"
    assert (
        canonical(row["preparation"]["document"])
        == made.subjects["preparation"].payload
    )
    assert session._decode_cached_source_workflow(canonical(result)) == result
    assert all(
        s.state is V2StageState.PENDING for s in ready[2]["snapshot"]().stages[4:]
    )


@pytest.mark.parametrize(
    "stop,expected",
    [
        ("started", "PREPARATION_REQUESTED"),
        ("operation", "INCOMPLETE"),
        ("uncommitted", "INCOMPLETE"),
        ("reviewed", "BOOT_REVIEWED"),
        ("requested", "BOOT_REQUESTED"),
        ("presence_requested", "PRESENCE_REVIEW_REQUESTED"),
        ("runtime", "RUNTIME_REVIEWED"),
        ("query", "QUERY_REQUESTED"),
    ],
)
def test_partial_and_pending_originals_remain_distinct(
    ready, monkeypatch, stop, expected
):
    absence_subjects(ready, monkeypatch, stop=stop)
    assert refresh_read(ready)["usb_qualification_absence"]["state"] == expected


def test_clean_boot_may_be_conservatively_held_after_lost_currentness(
    ready, monkeypatch
):
    absence_subjects(ready, monkeypatch, stop="boot", terminal="BOOT_HELD")
    row = refresh_read(ready)["usb_qualification_absence"]
    assert (
        row["state"] == "BOOT_HELD"
        and row["host_boot"]["document"]["status"] == "OBSERVED_HOST_BOOT"
    )


def test_uncertain_boot_cannot_be_downgraded_to_nonquarantined_hold(ready, monkeypatch):
    absence_subjects(
        ready, monkeypatch, stop="boot", terminal="BOOT_HELD", uncertain=True
    )
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)


@pytest.mark.parametrize("kind", [None, [], {}, True, "invented"])
def test_closed_event_inputs_fail_with_valueerror(kind):
    with pytest.raises(ValueError):
        usb_absence_event(kind, PHASE)


def test_role_budget_and_state_contract_are_bounded():
    assert (
        len(USB_ABSENCE_ROLE_BYTES) == 9
        and sum(USB_ABSENCE_ROLE_BYTES.values()) == 264 * 1024
    )
    assert len(USB_ABSENCE_STATES) == 14


@pytest.mark.parametrize("unknown", [False, True])
def test_full_presence_original_campaign_and_stage_transfer(
    ready, monkeypatch, unknown
):
    made = absence_subjects(ready, monkeypatch, stop="query")
    presence_result(made, unknown=unknown)
    workflow = refresh_read(ready)
    row = workflow["usb_qualification_absence"]
    assert row["original_campaign"] == made.campaign_originals[0]["original"]
    assert row["original_campaign_event"] == made.campaign_originals[0]["event"]
    assert row["state"] == ("ORIGINAL_CAMPAIGN_HELD" if unknown else "RETAINED_BLOCKED")
    if unknown:
        assert (
            row["execution"] is None
            and row["original_campaign"]["result"]["receipt"] is None
        )
    else:
        assert len(row["events"]) == 10 and all(row[r] for r in USB_ABSENCE_ROLE_BYTES)
        assert (
            row["phase_record"]["document"]["status"] == "ABSENCE_OBSERVATIONS_RETAINED"
        )
    assert session._decode_cached_source_workflow(canonical(workflow)) == workflow


def test_absence_does_not_relax_public_v10_or_authenticate_unknown_roles(
    ready, monkeypatch
):
    from rocell.application.physical_camera_usb_phase_readback import (
        verify_usb_phase_workflow,
    )

    made = absence_subjects(ready, monkeypatch)
    captured = []
    verify = session._verify_original_source_roles

    def capture(*args, **kwargs):
        captured.append(args)
        return verify(*args, **kwargs)

    monkeypatch.setattr(session, "_verify_original_source_roles", capture)
    refresh_read(ready)
    args = captured[-1]
    with pytest.raises(session.PhysicalCameraSessionError):
        verify_usb_phase_workflow(
            *args[:12], args[13], args[14], original_campaigns=args[12]
        )
    original_event = ready[2]["events"][-1]
    for change in (
        {"detail_code": "UNREVIEWED_ABSENCE_EVENT"},
        {"evidence": ()},
        {"state": V2StageState.PASS},
    ):
        change_last_event(ready[2], **change)
        with pytest.raises(session.PhysicalCameraSessionError):
            refresh_read(ready)
        ready[2]["events"][-1] = original_event
    ready[2]["add"](
        made.subjects["preparation"].payload,
        label="camera-usb-absence-unknown-v1:" + PHASE,
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)


def test_preparation_bytes_only_reconstruction_cannot_change_subjects(
    ready, monkeypatch
):
    from dataclasses import FrozenInstanceError

    made = absence_subjects(ready, monkeypatch)
    artifact = made.subjects["preparation"]

    def forbidden(*a, **k):
        pytest.fail("Pure absence codec opened filesystem")

    monkeypatch.setattr(Path, "open", forbidden)
    assert (
        codec.verify_usb_absence_preparation(
            artifact.payload, expected_sha256=artifact.sha256, **made.args
        )
        == artifact
    )
    with pytest.raises(FrozenInstanceError):
        artifact.payload = b"changed"
    for key, value in (
        ("physical_authority", True),
        ("phase_id", "usbphase-" + "a" * 32),
        ("prepared_at_utc_ns", True),
        ("operation_sha256", "0" * 64),
        ("operator_id", "different"),
    ):
        d = artifact.to_dict()
        d[key] = value
        raw = canonical(d)
        with pytest.raises(ValueError):
            codec.verify_usb_absence_preparation(
                raw, expected_sha256=digest(raw), **made.args
            )
    for value in (None, True, "A" * 64, "0" * 63):
        with pytest.raises(ValueError):
            codec.verify_usb_absence_preparation(
                artifact.payload, expected_sha256=value, **made.args
            )
    changed = artifact.to_dict()
    changed["runtime_report"]["files"][0]["bytes"] += 1
    with pytest.raises(ValueError):
        codec.UsbAbsencePreparation(canonical(changed))
    assert artifact.to_dict()["physical_authority"] is False
