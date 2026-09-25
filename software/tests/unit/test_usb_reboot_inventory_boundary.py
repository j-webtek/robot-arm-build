"""Real v13 facts and Collect transfer with explicitly modeled persistence.

The original reader, service, admission facts, independent permit codec and
final phase codec run. M1 leases/campaign execution are modeled in memory here;
there is no native child, CIM, USB, camera, arm or original-session reopening.
Actual NTFS/public acceptance independently verifies the real persistence join.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_reboot_service as reboot
from rocell.application import physical_usb_identity_service as service
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.commissioning_usb_identity_persistence import (
    decode_physical_usb_identity_permit,
    _verify_admission_evidence,
)
from rocell.application.physical_onboarding_durability import (
    canonical_bytes,
    canonical_sha256,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_usb_identity_campaign import (
    PhysicalUsbIdentityCampaign,
)
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.usb_identity_protocol import canonical, digest

from test_physical_camera_usb_reboot_readback import (
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
    reboot_subjects,
    reboot_boot,
    reboot_query,
    change_last_event,
    REBOOT_LAUNCH,
)
from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_usb_qualification import reference
from test_physical_usb_reconnect_phase import modeled_reconnect_run
from test_wizard_usb_absence_ui import adopt


def test_exact_original_inventory_facts_and_complete_collect_transfer(
    ready, setup_flow, monkeypatch
):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch)
    reboot_query(made, stop="requested")
    workflow = refresh_read(ready)
    state = ready[2]
    current = state["snapshot"]()
    owner = adopt(setup_flow[0], workflow)
    owner.launch_id = REBOOT_LAUNCH
    phase = reboot._UsbTrialReboot(owner)
    phase.adopt(workflow)
    campaign = PhysicalUsbIdentityCampaign(
        made.operation,
        identity=made.subjects["identity"],
        review=made.subjects["runtime_review"],
    )
    request = RegisteredActionRequest(
        workflow["binding"]["cell_id"],
        workflow["binding"]["session_id"],
        campaign.registration().action_id,
        "MODELED-no-reservation",
        "f" * 64,
    )
    checked = []
    guard = lambda: checked.append("current-boundary")
    facts = phase._facts_provider(workflow, ready[1], campaign, guard)
    rows = [ref.to_dict() for ref in current.evidence]
    # This is the exact original-domain serialization contract, including LF.
    assert canonical_bytes(rows) == canonical(rows) + b"\n"
    assert workflow["evidence_inventory_sha256"] == canonical_sha256(rows)
    assert workflow["evidence_inventory_sha256"] != digest(canonical(rows))
    original_facts = facts(request, current).retained_documents()
    assert original_facts["selected_identity"] == campaign.identity.to_dict()
    assert original_facts["hazard_assessment"]["energy_envelope"] is None
    reviewed_ids = {
        ref["evidence_id"]
        for ref in original_facts["hazard_assessment"]["reviewed_originals"]
    }
    unselected = next(
        ref for ref in current.evidence if ref.evidence_id not in reviewed_ids
    )
    extra = reference(
        canonical({"MODELED": "unreviewed extra"}), "unreviewed-reboot-extra"
    )
    changed_cases = (
        (*current.evidence, extra),
        tuple(
            replace(ref, manifest_sha256="f" * 64) if ref is unselected else ref
            for ref in current.evidence
        ),
        tuple(ref for ref in current.evidence if ref is not unselected),
    )
    for evidence in changed_cases:
        changed = replace(
            current, evidence=tuple(sorted(evidence, key=lambda r: r.evidence_id))
        )
        assert (
            changed.head == current.head
            and changed.committed_events == current.committed_events
        )
        with pytest.raises(WizardError) as raised:
            facts(request, changed)
        assert raised.value.code == "USB_REBOOT_CURRENT_INVENTORY_CHANGED"

    # Reuse the peer's deterministic typed permit/report factory WITHOUT
    # committing a second query request. This only manufactures test evidence;
    # it is not a permit-restoration or original-store trust mechanism.
    advance = made.advance
    made.advance = lambda *args, **kwargs: None
    reboot_query(made, stop="campaign")
    made.advance = advance
    template = deepcopy(made.campaign_originals[0])
    made.campaign_originals = ()
    # A narrow exact-type shell represents only the modeled runtime identity;
    # the real runtime's lease/process/persistence methods are never invoked.
    runtime = object.__new__(PhysicalOnboardingM1Runtime)
    runtime.source_binding_sha256 = physical_camera_source_binding(owner.source_sha256)
    monkeypatch.setattr(owner.setup.session._store, "_runtime", runtime, raising=False)
    calls = []
    original_scope = state["store"].stage_transaction

    class ModelPersistence:
        def __init__(self, supplied, **kwargs):
            assert supplied is runtime
            self.facts = kwargs["admission_facts"]
            assert (
                kwargs["expected_usb_query_policy_sha256"]
                == kwargs["stage_policy"].sha256
            )

        def verification(self, session_id):
            assert session_id == request.session_id
            return SimpleNamespace(challenge_sha256="c" * 64)

        @contextmanager
        def stage_transaction(self, session_id, *, expected_challenge_sha256):
            assert (
                session_id == request.session_id
                and expected_challenge_sha256 == "c" * 64
            )
            with original_scope() as tx:
                tx.store_evidence = lambda stage, payload, **kw: state["add"](
                    payload, label=kw["label"], media=kw["media_type"], stage=stage
                )

                def commit(stage, status, **kw):
                    state["advance"](
                        status, kw["detail_code"], kw["evidence"], stage=stage
                    )
                    change_last_event(state, occurred_at_ns=kw["occurred_at_ns"])
                    return tx.snapshot()

                tx.commit_stage_state = commit
                yield tx

    class ModelDispatch:
        def __init__(self, persistence, supplied, *, revalidate_context):
            assert supplied.operation.sha256 == campaign.operation.sha256
            self.persistence, self.campaign, self.original = persistence, supplied, None

        def perform(self, *, request_key, cancellation):
            assert (
                request_key
                == "usb-reboot-" + workflow["usb_qualification_reboot"]["phase_id"]
            )
            # Fresh callback re-evaluation is retained at both modeled admission
            # boundaries. No fact cache crosses either boundary.
            first = self.persistence.facts(
                request, state["snapshot"]()
            ).retained_documents()
            calls.append("fresh-prepare-facts")
            second = self.persistence.facts(
                request, state["snapshot"]()
            ).retained_documents()
            calls.append("fresh-execute-facts")
            assert first == second == original_facts
            retained = deepcopy(template)
            old = decode_physical_usb_identity_permit(retained["original"]["permit"])
            admission = replace(
                old.admission,
                hazard_assessment_sha256=digest(canonical(first["hazard_assessment"])),
                configuration_epoch_hashes=tuple(
                    digest(canonical(row)) for row in first["configuration_epochs"]
                ),
            )
            permit = replace(
                old,
                admission=admission,
                request=replace(
                    old.request,
                    request_key=request_key,
                    expected_challenge_sha256=admission.challenge_sha256,
                ),
            )
            _verify_admission_evidence(first, admission)
            run = modeled_reconnect_run(
                self.campaign.preparation_for_permit(permit), utc=made.now + 1
            )
            original = retained["original"]
            original.update(
                permit=asdict(permit),
                admission_evidence=first,
                evidence=run.to_dict(),
                evidence_sha256=run.sha256,
            )
            original["result"]["permit_sha256"] = permit.permit_sha256
            original["result"]["receipt"].update(
                permit_sha256=permit.permit_sha256,
                evidence_sha256s=[run.sha256],
                output_bytes=len(run.payload),
            )
            original["reference"].update(
                permit_sha256=permit.permit_sha256,
                evidence_sha256=run.sha256,
                payload_bytes=len(run.payload),
            )
            retained["event"]["operation_binding_sha256"] = permit.permit_sha256
            retained = json.loads(canonical(retained))
            made.campaign_originals = (retained,)
            self.original = retained["original"]
            calls.append("modeled-known-original")
            return {"MODELED_DISPATCH_COMPLETED": True}

        def retained_diagnostics(self):
            return dict(dispatch={"MODELED": True}, original=deepcopy(self.original))

    monkeypatch.setattr(reboot, "M1PhysicalUsbIdentityPersistence", ModelPersistence)
    monkeypatch.setattr(reboot, "PhysicalUsbIdentityDispatchOwner", ModelDispatch)
    phase.attempt = dict(
        action_id=reboot.COLLECT,
        phase_id=workflow["usb_qualification_reboot"]["phase_id"],
        records={},
    )
    phase._collect_usb(workflow, ready[1], made.predecessor, guard, None)
    assert calls == [
        "fresh-prepare-facts",
        "fresh-execute-facts",
        "modeled-known-original",
    ]
    assert phase.query_attempted
    assert set(phase.attempt["records"]) == {"execution", "phase_record"}
    assert all(
        row["retention"] == "M1_FULL_BYTES_READ_BACK"
        for row in phase.attempt["records"].values()
    )
    assert len(phase.attempt["events"][-1]["evidence"]) == 11
    final = refresh_read(ready)
    row = final["usb_qualification_reboot"]
    assert row["state"] == "RETAINED_BLOCKED" and len(row["events"]) == 7
    assert row["original_campaign"]["admission_evidence"] == original_facts
    assert (
        row["execution"]["evidence_sha256"]
        == phase.attempt["records"]["execution"]["evidence_sha256"]
    )
    assert final["usb_qualification_baseline"] == workflow["usb_qualification_baseline"]
    assert final["usb_qualification_absence"] == workflow["usb_qualification_absence"]
    assert (
        final["usb_qualification_reconnect"] == workflow["usb_qualification_reconnect"]
    )
