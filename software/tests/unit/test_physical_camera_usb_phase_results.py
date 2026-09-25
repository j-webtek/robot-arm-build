"""Full v10 originals, with MODELED host/USB facts and no actual processes."""

from dataclasses import asdict
import json
import time

import pytest

from rocell.application import cell_commissioning_coordinator as core
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.physical_usb_identity_campaign import (
    PhysicalUsbIdentityCampaign,
)
from rocell.application.physical_camera_usb_qualification import (
    build_usb_qualification_phase,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.host_boot_observation import (
    HostBootRequest,
    HostBootObservation,
)
from test_physical_camera_coordinator import admission
from test_physical_camera_usb_readback import modeled_clean_held_evidence
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
    codec,
    session,
    usb_reader,
    policy_module,
    STAGE_ORDER,
    V2StageState,
    canonical,
    digest,
    LAUNCH,
    PHASE_ID,
)


def phase_boot(made, monkeypatch, *, kind="observed", retain_only=False):
    """Physical-shaped origin below is explicitly MODELED, never a promotion."""
    from rocell.application.physical_usb_trial_boot import _terminal
    import test_physical_usb_trial_boot as boot_fixture

    made.advance(
        "BOOT_REQUESTED", V2StageState.WAITING_OPERATOR, (made.refs["boot_request"],)
    )
    bound = made.plan.to_dict()["binding"]
    monkeypatch.setattr(boot_fixture, "WALL", made.now + 1)
    request = HostBootRequest(
        bound["source_sha256"],
        bound["session_id"],
        LAUNCH,
        PHASE_ID,
        bound["trial_id"],
        "BASELINE",
        time.monotonic_ns() + 29_000_000_000,
    )
    report = boot_fixture.owned_report(
        request, fault="unknown" if kind == "uncertain" else None
    )
    if kind == "observed":
        document = report.to_dict()
        document["origin"] = "WINDOWS_LOCAL_CIM"
        report = HostBootObservation(canonical(document))
    made.retain("host_boot", report)
    if not retain_only:
        made.now += 2000
        name = _terminal(report)
        made.advance(
            name,
            (
                V2StageState.SIDE_EFFECT_UNCERTAIN
                if name == "BOOT_UNCERTAIN"
                else V2StageState.BLOCKED
            ),
            (made.refs["boot_request"], made.refs["host_boot"]),
        )
    return report


def phase_query(made, monkeypatch, *, stage="retained", unknown=False):
    """Pure MODELED campaign originals; no live admission or native effects."""
    made.advance(
        "QUERY_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        (made.refs["identity"], made.refs["boot_request"], made.refs["host_boot"]),
    )
    if stage == "requested":
        return
    snapshot = made.case[2]["snapshot"]()
    identity = made.subjects["identity"]
    campaign = PhysicalUsbIdentityCampaign(
        made.operation, identity=identity, review=made.subjects["runtime_review"]
    )
    facts = dict(
        stage_policy=policy_module.usb_identity_stage_policy().to_dict(),
        hazard_assessment={"explicitly_modeled": True},
        configuration_epochs=[{"modeled_domain": i} for i in range(8)],
        selected_identity=identity.to_dict(),
    )
    base = asdict(admission())
    bound = made.plan.to_dict()["binding"]
    base.update(
        cell_id=bound["cell_id"],
        session_id=bound["session_id"],
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
            digest(canonical(row)) for row in facts["configuration_epochs"]
        ),
    )
    admitted = core.UsbIdentityAdmissionSnapshot(
        **base, usb_query_policy_sha256=policy_module.usb_identity_stage_policy().sha256
    )
    permit = core.ExactOperationPermit(
        "attempt-" + "3" * 32,
        core.RegisteredActionRequest(
            bound["cell_id"],
            bound["session_id"],
            campaign.registration().action_id,
            "MODELED-new-trial-query",
            admitted.challenge_sha256,
        ),
        admitted,
        campaign.registration(),
        100,
        30_000_000_100,
        "4" * 64,
    )
    execution = modeled_clean_held_evidence(
        campaign.preparation_for_permit(permit)
    ).to_dict()
    execution.update(started_utc_ns=made.now + 1, finished_utc_ns=made.now + 2)
    run = OwnedUsbIdentityRunEvidence(canonical(execution))
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
            0,
            0,
            0,
            0,
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
            cell_id=bound["cell_id"],
            session_id=bound["session_id"],
            attempt_id=permit.attempt_id,
            permit_sha256=permit.permit_sha256,
            evidence_sha256=run.sha256,
            payload_bytes=len(run.payload),
            label="physical-native-usb-identity",
        ),
        retention="M1_FULL_BYTES_READ_BACK",
    )
    row = json.loads(
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
    )
    made.campaign_originals = (row,)
    monkeypatch.setattr(
        usb_reader,
        "read_original_usb_campaigns",
        lambda *a, **k: made.campaign_originals,
    )
    if unknown or stage == "campaign":
        return
    made.retain("execution", run)
    if stage == "execution":
        return
    made.now += 3000
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
            operation_id=PHASE_ID,
            operator_id="phase-operator",
            started_at_utc_ns=made.start.occurred_at_ns,
            finished_at_utc_ns=made.now,
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
    if stage != "phase_record":
        made.advance("RETAINED", V2StageState.BLOCKED, made.refs.values())


@pytest.mark.parametrize(
    "kind,state",
    [
        ("observed", "BOOT_RETAINED"),
        ("held", "BOOT_HELD"),
        ("uncertain", "BOOT_UNCERTAIN"),
    ],
)
def test_boot_original_terminal_states_do_not_claim_usb_or_replay(
    ready, monkeypatch, kind, state
):
    made = phase_subjects(ready)
    report = phase_boot(made, monkeypatch, kind=kind)
    result = refresh_read(ready)["usb_qualification_baseline"]
    assert result["state"] == state
    assert canonical(result["host_boot"]["document"]) == report.payload
    assert (
        result["execution"] is None
        and result["phase_record"] is None
        and result["original_campaign"] is None
    )


def test_full_original_phase_retains_known_held_query_not_physical_qualification(
    ready, monkeypatch
):
    made = phase_subjects(ready)
    phase_boot(made, monkeypatch)
    phase_query(made, monkeypatch)
    result = refresh_read(ready)
    row = result["usb_qualification_baseline"]
    assert row["state"] == "RETAINED_BLOCKED"
    assert row["phase_record"]["document"]["status"] == "HELD"
    assert row["phase_record"]["document"]["canonical_stage_pass"] is False
    assert row["original_campaign"] == made.campaign_originals[0]["original"]
    assert row["original_campaign_event"] == made.campaign_originals[0]["event"]
    assert canonical(row["execution"]["document"]) == made.subjects["execution"].payload
    assert session._decode_cached_source_workflow(canonical(result)) == result
    assert all(
        r.state is V2StageState.PENDING for r in ready[2]["snapshot"]().stages[4:]
    )


def test_original_unknown_counts_and_no_stage_transfer(ready, monkeypatch):
    made = phase_subjects(ready)
    phase_boot(made, monkeypatch)
    phase_query(made, monkeypatch, unknown=True)
    row = refresh_read(ready)["usb_qualification_baseline"]
    assert row["state"] == "ORIGINAL_CAMPAIGN_HELD"
    assert row["original_campaign"]["result"]["receipt"] is None
    assert row["original_campaign"]["result"]["quarantine_latched"]
    assert row["execution"] is None and row["phase_record"] is None


def test_preparation_rejects_rehashed_stale_unlogged_and_legacy_subjects(ready):
    made = phase_subjects(ready, stop="prepared")
    original = made.subjects["preparation"]
    for fault in (
        "stale",
        "unlogged",
        "packet",
        "operation",
        "launch",
        "source",
        "legacy",
        "actor",
    ):
        d = original.to_dict()
        ledger = d["acquisition_ledger"]
        if fault == "stale":
            ledger["entries"][0]["started_at_utc_ns"] = made.start.occurred_at_ns - 1
        elif fault == "unlogged":
            ledger["entries"][1]["completion_logged"] = False
        elif fault == "packet":
            ledger["entries"][1]["document_sha256"] = "f" * 64
        elif fault == "operation":
            ledger["entries"][2]["operation_id"] = "unrelated-operation"
        elif fault == "launch":
            ledger["launch_session_id"] = "wizard-" + "7" * 32
        elif fault == "source":
            ledger["source_sha256"] = "f" * 64
        elif fault == "actor":
            d["operator_id"] = " actor"
        else:
            d["operation"].pop("qualification_plan")
            d["operation"].pop("phase_binding")
            d["operation"]["schema"] = "rocell.physical_usb_identity_operation.v1"
            d["operation_sha256"] = digest(canonical(d["operation"]))
        raw = canonical(d)
        with pytest.raises(ValueError):
            codec.verify_usb_trial_baseline_preparation(
                raw,
                expected_sha256=digest(raw),
                **{
                    key: made.preparation_args[key]
                    for key in (
                        "plan",
                        "plan_reference",
                        "phase_start_event",
                        "phase_id",
                        "enrollment",
                        "enrollment_reference",
                    )
                },
            )
