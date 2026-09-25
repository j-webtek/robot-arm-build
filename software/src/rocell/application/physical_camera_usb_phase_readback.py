"""Additive original v10 BASELINE grammar over the complete real camera audit.

No historical baseline is relabeled, no unknown request is replayed, and no
saved reference authenticates itself. The session owner supplies original
package bytes and a complete camera-family campaign audit under its leases.
"""

from __future__ import annotations

from typing import Any

from .physical_camera_usb_phase import (
    USB_PHASE_EVENT,
    USB_PHASE_ROLE_BYTES,
    UsbTrialBaselinePreparation,
    verify_usb_trial_baseline_preparation,
    usb_phase_event,
)
from .physical_camera_usb_trial_readback import _verify_usb_qualification_trial_prefix
from .physical_camera_usb_qualification import (
    UsbQualificationPlan,
    verify_usb_qualification_phase,
)
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState, V2CommittedHead
from .physical_onboarding_durability import canonical_sha256
from .physical_usb_identity_campaign import (
    UsbIdentityOperation,
    PhysicalUsbIdentityCampaign,
    verify_usb_identity_campaign_evidence,
)
from .usb_identity_stage_policy import (
    UsbIdentityPolicyReview,
    UsbIdentityAdmissionIdentity,
)
from .physical_usb_trial_boot import (
    verify_usb_trial_boot_intent,
    verify_usb_trial_boot_observation,
    _terminal,
)
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.usb_identity_registration import UsbIdentityRuntimeReview
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)


def verify_usb_phase_workflow(
    bound,
    snapshot: V2SessionSnapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    phase_packages,
    *,
    original_campaigns=(),
) -> dict[str, Any]:
    return _verify_usb_phase_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        received_packages,
        received_originals,
        identity_packages,
        usb_packages,
        trial_packages,
        phase_packages,
        original_campaigns=original_campaigns,
    )


def _verify_usb_phase_prefix(
    bound,
    snapshot: V2SessionSnapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    phase_packages,
    *,
    original_campaigns=(),
    prefix_event_count=None,
    usb_absence_evidence_ids=frozenset(),
    usb_reconnect_extension=False,
    usb_reboot_extension: bool = False,
    usb_reboot_evidence_ids: frozenset[str] = frozenset(),
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
    usb_complete_evidence_ids: frozenset[str] = frozenset(),
    usb_reconnect_evidence_ids=frozenset(),
) -> dict[str, Any]:
    from .physical_camera_session import (
        _require,
        PhysicalCameraSessionError,
        SOURCE_WORKFLOW_USB_PHASE_SCHEMA,
    )
    from .commissioning_usb_identity_persistence import (
        decode_physical_usb_identity_permit,
        _verify_admission_evidence,
    )

    error = "CAMERA_SESSION_USB_PHASE_INVALID"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, error)
    try:
        _require(
            type(snapshot) is V2SessionSnapshot
            and type(original_campaigns) is tuple
            and len(original_campaigns) <= 2,
            error,
        )
        _require(
            type(usb_absence_evidence_ids) is frozenset
            and len(usb_absence_evidence_ids) <= 9
            and (prefix_event_count is not None or not usb_absence_evidence_ids),
            error,
        )
        _require(
            type(usb_complete_extension) is bool
            and (not usb_complete_extension or usb_reboot_extension)
            and type(usb_complete_evidence_ids) is frozenset
            and len(usb_complete_evidence_ids) <= 3
            and (usb_complete_extension or not usb_complete_evidence_ids)
            and usb_complete_evidence_ids.isdisjoint(usb_reboot_evidence_ids)
            and type(usb_reboot_extension) is bool
            and (not usb_reboot_extension or usb_reconnect_extension)
            and type(usb_reboot_evidence_ids) is frozenset
            and len(usb_reboot_evidence_ids) <= 11
            and (usb_reboot_extension or not usb_reboot_evidence_ids)
            and usb_reboot_evidence_ids.isdisjoint(
                usb_absence_evidence_ids
                | usb_reconnect_evidence_ids
                | frozenset(phase_packages)
            ),
            error,
        )
        _require(
            type(usb_reconnect_extension) is bool
            and type(usb_reconnect_evidence_ids) is frozenset
            and len(usb_reconnect_evidence_ids) <= 11
            and (usb_reconnect_extension or not usb_reconnect_evidence_ids)
            and (not usb_reconnect_extension or prefix_event_count is not None)
            and usb_reconnect_evidence_ids.isdisjoint(
                usb_absence_evidence_ids | frozenset(phase_packages)
            ),
            error,
        )
        if prefix_event_count is not None:
            _require(
                type(prefix_event_count) is int
                and 0 < prefix_event_count < len(snapshot.committed_events)
                and len(snapshot.committed_events)
                - prefix_event_count
                - mode_event_count
                <= (
                    (27 if usb_complete_extension else 24)
                    if usb_reboot_extension
                    else (17 if usb_reconnect_extension else 10)
                ),
                error,
            )
        starts = [
            (i, e)
            for i, e in enumerate(snapshot.committed_events)
            if e.detail_code.startswith("CAMERA_USB_TRIAL_BASELINE_ENTERED_")
        ]
        _require(len(starts) == 1 and len(phase_packages) <= 9, error)
        index, entry = starts[0]
        match = USB_PHASE_EVENT.fullmatch(entry.detail_code)
        _require(match is not None and index > 0, error)
        assert match is not None
        phase_id = "usbphase-" + match[2].lower()
        events = snapshot.committed_events[index:prefix_event_count]
        _require(1 <= len(events) <= 8, error)
        order = tuple(USB_PHASE_ROLE_BYTES)
        inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
        records = {}
        for key, package in phase_packages.items():
            _require(
                type(package) is dict
                and set(package) == {"kind", "phase_id", "record"}
                and package["phase_id"] == phase_id
                and package["kind"] in order
                and package["kind"] not in records,
                error,
            )
            kind, record = package["kind"], package["record"]
            _require(
                type(record) is dict
                and set(record)
                == {"document", "evidence_sha256", "reference", "retention"}
                and record["retention"] == "M1_FULL_BYTES_READ_BACK"
                and inventory.get(key) == record["reference"],
                error,
            )
            raw = canonical(record["document"])
            _require(
                0 < len(raw) <= USB_PHASE_ROLE_BYTES[kind]
                and len(raw) == record["reference"]["payload_bytes"]
                and digest(raw)
                == record["reference"]["payload_sha256"]
                == record["evidence_sha256"],
                error,
            )
            records[kind] = record
        _require(
            tuple(role for role in order if role in records) == order[: len(records)],
            error,
        )
        # Classify only by the exact independently retained phase operation.
        # Every other reservation must still pass the complete old v8 audit.
        operation_sha = (
            None
            if "preparation" not in records
            else records["preparation"]["document"].get("operation_sha256")
        )
        phase_campaigns: list[dict[str, Any]] = []
        old_campaigns: list[dict[str, Any]] = []
        for row in original_campaigns:
            _require(type(row) is dict and set(row) == {"original", "event"}, error)
            permit = decode_physical_usb_identity_permit(row["original"]["permit"])
            (
                phase_campaigns
                if permit.registration.operation_sha256 == operation_sha
                else old_campaigns
            ).append(row)
        _require(len(phase_campaigns) <= 1 and len(old_campaigns) <= 1, error)
        original = _verify_usb_qualification_trial_prefix(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages,
            qualification_packages,
            qualification_originals,
            static_packages,
            received_packages,
            received_originals,
            identity_packages,
            usb_packages,
            trial_packages,
            original_campaigns=tuple(old_campaigns),
            prefix_event_count=index,
            usb_phase_evidence_ids=frozenset(phase_packages),
            usb_absence_evidence_ids=usb_absence_evidence_ids,
            usb_absence_extension=prefix_event_count is not None,
            usb_reconnect_extension=usb_reconnect_extension,
            usb_reboot_extension=usb_reboot_extension,
            usb_reconnect_evidence_ids=usb_reconnect_evidence_ids,
            usb_reboot_evidence_ids=usb_reboot_evidence_ids,
            usb_complete_extension=usb_complete_extension,
            camera_mode_entry=camera_mode_entry,
            usb_complete_evidence_ids=usb_complete_evidence_ids,
        )
        trial = original["usb_qualification_trial"]
        _require(
            trial["state"] == "PLAN_DECLARED"
            and original.get("configuration_epochs") is not None,
            error,
        )
        plan_record = trial["plan"]
        plan = UsbQualificationPlan(canonical(plan_record["document"]))
        plan_ref = _parse_evidence_reference(plan_record["reference"])
        _require(
            entry.occurred_at_ns >= trial["declaration_event"]["occurred_at_ns"], error
        )

        def refs(names):
            _require(all(name in records for name in names), error)
            return tuple(
                sorted(
                    (
                        _parse_evidence_reference(records[name]["reference"])
                        for name in names
                    ),
                    key=lambda ref: ref.evidence_id,
                )
            )

        expected = [
            ("ENTERED", V2StageState.BLOCKED, (plan_ref,)),
            ("PREPARATION_REQUESTED", V2StageState.WAITING_OPERATOR, (plan_ref,)),
        ]
        if len(events) >= 3:
            expected.append(("PREPARED", V2StageState.REVIEW_PENDING, refs(order[:2])))
        if len(events) >= 4:
            expected.append(("REVIEWED", V2StageState.BLOCKED, refs(order[:6])))
        if len(events) >= 5:
            expected.append(
                (
                    "BOOT_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(("boot_request",)),
                )
            )
        if len(events) >= 6:
            terminal_match = USB_PHASE_EVENT.fullmatch(events[5].detail_code)
            _require(
                terminal_match is not None
                and terminal_match[1]
                in {"BOOT_RETAINED", "BOOT_HELD", "BOOT_UNCERTAIN"},
                error,
            )
            assert terminal_match is not None
            terminal_name = terminal_match[1]
            expected.append(
                (
                    terminal_name,
                    (
                        V2StageState.SIDE_EFFECT_UNCERTAIN
                        if terminal_name == "BOOT_UNCERTAIN"
                        else V2StageState.BLOCKED
                    ),
                    refs(("boot_request", "host_boot")),
                )
            )
            _require(terminal_name == "BOOT_RETAINED" or len(events) == 6, error)
        if len(events) >= 7:
            expected.append(
                (
                    "QUERY_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(("identity", "boot_request", "host_boot")),
                )
            )
        if len(events) == 8:
            expected.append(("RETAINED", V2StageState.BLOCKED, refs(order)))
        previous = V2StageState.REVIEW_PENDING
        for event, (name, state, citations) in zip(events, expected):
            _require(
                event.stage is STAGE_ORDER[3]
                and event.previous_state is previous
                and event.state is state
                and event.detail_code == usb_phase_event(name, phase_id)
                and event.evidence == citations,
                error,
            )
            previous = state
        _require(
            (
                prefix_event_count is not None
                or snapshot.stages[3].state is events[-1].state
            )
            and all(
                row.state is V2StageState.PENDING and not row.evidence_ids
                for row in snapshot.stages[4 if camera_mode_entry is None else 5 :]
            ),
            error,
        )
        # Closed stored-before-commit prefixes. No role can predate its request.
        minimum = (0, 0, 2, 6, 6, 7, 7, 9)[len(events) - 1]
        maximum = (0, 2, 6, 6, 7, 7, 9, 9)[len(events) - 1]
        _require(minimum <= len(records) <= maximum, error)
        preparation = campaign = identity = boot_intent = boot = None
        if "enrollment" in records:
            enrollment = records["enrollment"]["document"]
            verified_enrollment = verify_native_camera_enrollment_snapshot(
                enrollment,
                source_sha256=bound["source_sha256"],
                launch_session_id=enrollment["view"]["provenance"]["session_id"],
            )
            _require(
                verified_enrollment == enrollment
                and enrollment["view"]["provenance"]["mode"] == "physical",
                error,
            )
        if "preparation" in records:
            preparation = verify_usb_trial_baseline_preparation(
                canonical(records["preparation"]["document"]),
                plan=plan,
                plan_reference=plan_ref,
                phase_start_event=events[1],
                phase_id=phase_id,
                enrollment=canonical(records["enrollment"]["document"]),
                enrollment_reference=_parse_evidence_reference(
                    records["enrollment"]["reference"]
                ),
                expected_sha256=records["preparation"]["evidence_sha256"],
            )
            pd = preparation.to_dict()
            _require(pd["operation"]["workspace"] == bound["workspace"], error)
            if len(events) >= 3:
                _require(events[2].occurred_at_ns >= pd["prepared_at_utc_ns"], error)
        if "policy_review" in records:
            assert preparation is not None
            pd = preparation.to_dict()
            policy = UsbIdentityPolicyReview(
                canonical(records["policy_review"]["document"])
            ).to_dict()
            _require(
                all(
                    policy[key] == plan.to_dict()["binding"][key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                )
                and policy["operator_id"] == pd["operator_id"]
                and digest(canonical(policy["policy"]))
                == pd["operation"]["policy_sha256"]
                and policy["reviewed_at_utc_ns"] >= pd["prepared_at_utc_ns"],
                error,
            )
        if "runtime_review" in records:
            assert preparation is not None
            pd = preparation.to_dict()
            runtime_review = UsbIdentityRuntimeReview(
                canonical(records["runtime_review"]["document"])
            )
            rd, sd = runtime_review.to_dict(), pd["operation"]["selection"]
            _require(
                rd["operator_id"] == pd["operator_id"]
                and rd["reviewer_id"]
                == records["policy_review"]["document"]["reviewer_id"]
                and rd["reviewed_at_ns"] >= pd["prepared_at_utc_ns"]
                and rd["launch_session_id"]
                == pd["acquisition_ledger"]["launch_session_id"]
                and rd["source_sha256"] == bound["source_sha256"]
                and rd["runtime_registration_sha256"]
                == pd["runtime_report"]["runtime_registration_sha256"]
                and rd["operation_sha256"] == pd["operation_sha256"]
                and rd["selection_sha256"] == digest(canonical(sd))
                and rd["native_identity_sha256"] == sd["native_identity_sha256"]
                and rd["endpoint_sha256"] == sd["endpoint_sha256"]
                and rd["device_instance_id_sha256"]
                == digest(
                    sd["metadata_review"]["observed_instance_id"].encode("utf-8")
                ),
                error,
            )
        if "identity" in records:
            assert preparation is not None
            identity = UsbIdentityAdmissionIdentity(
                canonical(records["identity"]["document"])
            )
            idd = identity.to_dict()
            _require(
                all(
                    idd[key] == plan.to_dict()["binding"][key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                )
                and idd["policy_review_sha256"]
                == records["policy_review"]["evidence_sha256"]
                and idd["original_subjects"]
                == [
                    dict(
                        role=name,
                        reference=records[role]["reference"],
                        document_sha256=records[role]["evidence_sha256"],
                    )
                    for name, role in (
                        ("metadata", "enrollment"),
                        ("policy_review", "policy_review"),
                        ("runtime_review", "runtime_review"),
                    )
                ],
                error,
            )
            campaign = PhysicalUsbIdentityCampaign(
                UsbIdentityOperation(canonical(preparation.to_dict()["operation"])),
                identity=identity,
                review=runtime_review,
            )
        if "boot_request" in records:
            assert preparation is not None
            boot_intent = verify_usb_trial_boot_intent(
                canonical(records["boot_request"]["document"]),
                plan=plan,
                plan_reference=plan_ref,
                phase_start_event=events[1],
                phase_id=phase_id,
                launch_session_id=preparation.to_dict()["acquisition_ledger"][
                    "launch_session_id"
                ],
                expected_sha256=records["boot_request"]["evidence_sha256"],
            )
        if len(events) >= 4:
            _require(
                events[3].occurred_at_ns
                >= max(
                    records["policy_review"]["document"]["reviewed_at_utc_ns"],
                    records["runtime_review"]["document"]["reviewed_at_ns"],
                ),
                error,
            )
        if "host_boot" in records:
            assert boot_intent is not None
            boot = verify_usb_trial_boot_observation(
                canonical(records["host_boot"]["document"]),
                intent=boot_intent,
                requested_event=events[4],
                expected_sha256=records["host_boot"]["evidence_sha256"],
            )
            if len(events) >= 6:
                _require(
                    events[5].detail_code == usb_phase_event(_terminal(boot), phase_id)
                    and events[5].occurred_at_ns
                    >= boot.to_dict()["execution"]["finished_utc_ns"],
                    error,
                )
        audited = ledger_event = None
        if phase_campaigns:
            _require(
                len(events) >= 7 and campaign is not None and identity is not None,
                error,
            )
            assert campaign is not None and identity is not None
            audited, ledger_event = (
                phase_campaigns[0]["original"],
                phase_campaigns[0]["event"],
            )
            permit = decode_physical_usb_identity_permit(audited["permit"])
            campaign.preparation_for_permit(permit)
            transferred = {
                records[role]["reference"]["evidence_id"]
                for role in ("execution", "phase_record")
                if role in records
            }
            query_inventory = [
                ref.to_dict()
                for ref in snapshot.evidence
                if ref.evidence_id
                not in transferred
                | usb_absence_evidence_ids
                | usb_reconnect_evidence_ids
                | usb_reboot_evidence_ids
                | usb_complete_evidence_ids
                | mode_evidence_ids
            ]
            _require(
                permit.admission.journal_head_sha256
                == V2CommittedHead.build(
                    snapshot.header, snapshot.committed_events[: index + 7]
                ).head_sha256
                and permit.admission.stage_revision == index + 7
                and permit.admission.evidence_inventory_sha256
                == canonical_sha256(query_inventory)
                and permit.admission.stage_state is V2StageState.WAITING_OPERATOR,
                error,
            )
            _verify_admission_evidence(audited["admission_evidence"], permit.admission)
            _require(
                audited["admission_evidence"]["selected_identity"] == identity.to_dict()
                and ledger_event["attempt_id"] == permit.attempt_id
                and ledger_event["operation_binding_sha256"] == permit.permit_sha256,
                error,
            )
            if audited["evidence"] is not None:
                run = verify_usb_identity_campaign_evidence(
                    OwnedUsbIdentityRunEvidence(canonical(audited["evidence"])),
                    campaign=campaign,
                    permit=permit,
                    expected_evidence_sha256=audited["evidence_sha256"],
                )
                _require(
                    run.to_dict()["started_utc_ns"] >= events[6].occurred_at_ns, error
                )
                expected_reference = dict(
                    schema="rocell.usb_identity_campaign_reference.v1",
                    cell_id=bound["cell_id"],
                    session_id=bound["session_id"],
                    attempt_id=permit.attempt_id,
                    permit_sha256=permit.permit_sha256,
                    evidence_sha256=run.sha256,
                    payload_bytes=len(run.payload),
                    label="physical-native-usb-identity",
                )
                _require(audited["reference"] == expected_reference, error)
                if (
                    audited["result"] is not None
                    and audited["result"]["receipt"] is not None
                ):
                    _require(
                        audited["result"]["receipt"]["evidence_sha256s"] == [run.sha256]
                        and audited["result"]["receipt"]["output_bytes"]
                        == len(run.payload),
                        error,
                    )
        if "execution" in records:
            _require(
                audited is not None
                and audited["result"] is not None
                and audited["result"]["state"] == "SEALED_KNOWN"
                and audited["result"]["quarantine_latched"] is False
                and audited["evidence"] == records["execution"]["document"]
                and audited["evidence_sha256"]
                == records["execution"]["evidence_sha256"],
                error,
            )
        if "phase_record" in records:
            assert preparation is not None
            d = records["phase_record"]["document"]
            context = d["context"]
            _require(
                d["phase"] == "BASELINE"
                and d["ordinal"] == 0
                and context["operation_id"] == phase_id
                and context["launch_session_id"]
                == preparation.to_dict()["acquisition_ledger"]["launch_session_id"]
                and context["operator_id"] == preparation.to_dict()["operator_id"]
                and context["started_at_utc_ns"] == events[1].occurred_at_ns,
                error,
            )
            verify_usb_qualification_phase(
                canonical(d),
                plan=plan,
                predecessor=None,
                sources={
                    name: canonical(records[role]["document"])
                    for name, role in (
                        ("native_enrollment", "enrollment"),
                        ("owned_usb_run", "execution"),
                        ("host_boot", "host_boot"),
                    )
                },
                expected_sha256=records["phase_record"]["evidence_sha256"],
            )
            _require(
                d["records"]
                == [
                    dict(
                        role=name,
                        sha256=records[role]["evidence_sha256"],
                        payload_bytes=records[role]["reference"]["payload_bytes"],
                        reference=records[role]["reference"],
                    )
                    for name, role in (
                        ("native_enrollment", "enrollment"),
                        ("owned_usb_run", "execution"),
                        ("host_boot", "host_boot"),
                    )
                ],
                error,
            )
            if len(events) == 8:
                _require(
                    events[7].occurred_at_ns >= context["finished_at_utc_ns"], error
                )
        final_match = USB_PHASE_EVENT.fullmatch(events[-1].detail_code)
        assert final_match is not None
        name = final_match[1]
        outcome = "RETAINED_BLOCKED" if name == "RETAINED" else name
        if len(records) > minimum and len(events) < 8:
            outcome = "INCOMPLETE"
        if audited is not None and len(events) < 8:
            outcome = "ORIGINAL_CAMPAIGN_HELD"
        return {
            **original,
            "schema": SOURCE_WORKFLOW_USB_PHASE_SCHEMA,
            "usb_qualification_baseline": dict(
                phase_id=phase_id,
                phase="BASELINE",
                state=outcome,
                events=[event.to_dict() for event in events],
                **{role: records.get(role) for role in order},
                original_campaign=audited,
                original_campaign_event=ledger_event,
            ),
        }
    except PhysicalCameraSessionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        raise PhysicalCameraSessionError(error) from exc
