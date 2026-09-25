"""Original v12 AFTER_RECONNECT suffix over the complete real v11 audit.

Only the authentic original reader supplies these bytes and complete sibling
campaign records. No diagnostic cache, partial request or new app launch can
authorize a replay. Every historical inventory exclusion is an exact v12 role.
"""

from __future__ import annotations

from typing import Any

from .physical_camera_usb_reconnect_constants import (
    SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA,
    USB_RECONNECT_ROLE_BYTES,
    USB_RECONNECT_EVENT,
    MAX_USB_RECONNECT_EVENTS,
    usb_reconnect_event,
)
from .physical_camera_usb_reconnect import (
    original_usb_reconnect_predecessor,
    verify_usb_reconnect_preparation,
)
from .physical_camera_usb_absence_readback import _verify_usb_absence_prefix
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState, V2CommittedHead
from .physical_onboarding_durability import canonical_sha256
from .physical_usb_reconnect_phase import (
    UsbReconnectOperatorEvent,
    build_usb_reconnect_operator_event,
    verify_usb_reconnect_qualification_phase,
)
from .physical_usb_reconnect_boot import (
    verify_usb_reconnect_boot_intent,
    verify_usb_reconnect_boot_observation,
    _terminal,
)
from .physical_usb_identity_campaign import (
    UsbIdentityOperation,
    PhysicalUsbIdentityCampaign,
    verify_usb_identity_campaign_evidence,
)
from .usb_identity_stage_policy import (
    UsbIdentityPolicyReview,
    UsbIdentityAdmissionIdentity,
)
from .commissioning_usb_identity_persistence import (
    decode_physical_usb_identity_permit,
    _verify_admission_evidence,
)
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_identity_registration import UsbIdentityRuntimeReview
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.host_boot_observation import HostBootObservation


def verify_usb_reconnect_workflow(
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
    absence_packages,
    reconnect_packages,
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
) -> dict[str, Any]:
    """Authenticate the one closed reconnect suffix against the actual full audit."""
    return _verify_usb_reconnect_prefix(
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
        absence_packages,
        reconnect_packages,
        original_campaigns=original_campaigns,
        original_presence_campaigns=original_presence_campaigns,
    )


def _verify_usb_reconnect_prefix(
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
    absence_packages,
    reconnect_packages,
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
    prefix_event_count=None,
    usb_reboot_evidence_ids=frozenset(),
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
    usb_complete_evidence_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Verify a v12 prefix on the real v13 snapshot, never a synthetic old head.

    The sole v13 caller authenticates the separately bounded later suffix. The
    public v12 route still accepts neither later events nor extra inventory.
    """
    from .physical_camera_session import _require, PhysicalCameraSessionError

    error = "CAMERA_SESSION_USB_RECONNECT_INVALID"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, error)
    try:
        _require(
            type(usb_complete_extension) is bool
            and (not usb_complete_extension or prefix_event_count is not None)
            and type(usb_complete_evidence_ids) is frozenset
            and len(usb_complete_evidence_ids) <= 3
            and (usb_complete_extension or not usb_complete_evidence_ids)
            and usb_complete_evidence_ids.isdisjoint(usb_reboot_evidence_ids)
            and type(usb_reboot_evidence_ids) is frozenset
            and len(usb_reboot_evidence_ids) <= 11
            and (prefix_event_count is not None or not usb_reboot_evidence_ids),
            error,
        )
        _require(
            type(snapshot) is V2SessionSnapshot
            and type(original_campaigns) is tuple
            and len(original_campaigns) <= 3
            and type(original_presence_campaigns) is tuple
            and len(original_presence_campaigns) == 1,
            error,
        )
        if prefix_event_count is not None:
            _require(
                type(prefix_event_count) is int
                and 0 < prefix_event_count < len(snapshot.committed_events)
                and 1
                <= len(snapshot.committed_events)
                - prefix_event_count
                - mode_event_count
                <= (10 if usb_complete_extension else 7),
                error,
            )
        starts = [
            (i, event)
            for i, event in enumerate(snapshot.committed_events)
            if event.detail_code.startswith(
                "CAMERA_USB_TRIAL_RECONNECT_PREPARATION_REQUESTED_"
            )
        ]
        _require(len(starts) == 1 and len(reconnect_packages) <= 11, error)
        index, start = starts[0]
        match = USB_RECONNECT_EVENT.fullmatch(start.detail_code)
        _require(match is not None and index > 0, error)
        assert match is not None
        phase_id = "usbphase-" + match[2].lower()
        events = snapshot.committed_events[index:prefix_event_count]
        _require(1 <= len(events) <= MAX_USB_RECONNECT_EVENTS, error)
        order = tuple(USB_RECONNECT_ROLE_BYTES)
        inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
        records: dict[str, dict[str, Any]] = {}
        other_ids = {row["reference"]["evidence_id"] for row in roles.values()}
        for packages in (
            intake_packages,
            qualification_packages,
            static_packages,
            received_packages,
            identity_packages,
            usb_packages,
            trial_packages,
            phase_packages,
            absence_packages,
        ):
            other_ids.update(packages)
        _require(
            set(reconnect_packages).isdisjoint(other_ids)
            and usb_reboot_evidence_ids.isdisjoint(other_ids | set(reconnect_packages))
            and usb_complete_evidence_ids.isdisjoint(
                other_ids | set(reconnect_packages)
            )
            and set(inventory)
            == other_ids
            | set(reconnect_packages)
            | usb_reboot_evidence_ids
            | usb_complete_evidence_ids
            | mode_evidence_ids,
            error,
        )
        for key, package in reconnect_packages.items():
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
            ref = _parse_evidence_reference(record["reference"])
            _require(
                ref.stage is STAGE_ORDER[3]
                and 0 < len(raw) <= USB_RECONNECT_ROLE_BYTES[kind]
                and len(raw) == ref.payload_bytes
                and digest(raw) == ref.payload_sha256 == record["evidence_sha256"],
                error,
            )
            records[kind] = record
        _require(
            tuple(role for role in order if role in records) == order[: len(records)],
            error,
        )

        # Partition only by the exact separately retained reconnect operation.
        # The entire remaining descriptor family still belongs to v11 and must
        # pass its original baseline/legacy campaign verifiers, never disappear.
        operation_sha = (
            None
            if "preparation" not in records
            else records["preparation"]["document"].get("operation_sha256")
        )
        own_campaigns: list[dict[str, Any]] = []
        old_campaigns: list[dict[str, Any]] = []
        for row in original_campaigns:
            _require(type(row) is dict and set(row) == {"original", "event"}, error)
            candidate_permit = decode_physical_usb_identity_permit(
                row["original"]["permit"]
            )
            (
                own_campaigns
                if candidate_permit.registration.operation_sha256 == operation_sha
                else old_campaigns
            ).append(row)
        _require(len(own_campaigns) <= 1 and len(old_campaigns) <= 2, error)
        original = _verify_usb_absence_prefix(
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
            absence_packages,
            original_campaigns=tuple(old_campaigns),
            original_presence_campaigns=original_presence_campaigns,
            prefix_event_count=index,
            usb_reconnect_evidence_ids=frozenset(reconnect_packages),
            usb_reboot_extension=prefix_event_count is not None,
            usb_reboot_evidence_ids=usb_reboot_evidence_ids,
            usb_complete_extension=usb_complete_extension,
            camera_mode_entry=camera_mode_entry,
            usb_complete_evidence_ids=usb_complete_evidence_ids,
        )
        predecessor = original_usb_reconnect_predecessor(original)
        baseline, absence = predecessor["original_baseline"], predecessor["absence"]
        plan, absence_ref = baseline["plan"], predecessor["absence_reference"]
        _require(
            phase_id
            not in {
                baseline["baseline"].to_dict()["context"]["operation_id"],
                absence.to_dict()["context"]["operation_id"],
            }
            and start.occurred_at_ns
            >= snapshot.committed_events[index - 1].occurred_at_ns
            and start.occurred_at_ns
            >= absence.to_dict()["context"]["finished_at_utc_ns"],
            error,
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
            ("PREPARATION_REQUESTED", V2StageState.WAITING_OPERATOR, (absence_ref,))
        ]
        if len(events) >= 2:
            expected.append(("PREPARED", V2StageState.REVIEW_PENDING, refs(order[:4])))
        if len(events) >= 3:
            expected.append(("REVIEWED", V2StageState.BLOCKED, refs(order[:8])))
        if len(events) >= 4:
            expected.append(
                (
                    "BOOT_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(("boot_request",)),
                )
            )
        terminal = None
        if len(events) >= 5:
            terminal_match = USB_RECONNECT_EVENT.fullmatch(events[4].detail_code)
            _require(
                terminal_match is not None
                and terminal_match[1]
                in {"BOOT_RETAINED", "BOOT_HELD", "BOOT_UNCERTAIN"},
                error,
            )
            assert terminal_match is not None
            terminal = terminal_match[1]
            expected.append(
                (
                    terminal,
                    (
                        V2StageState.SIDE_EFFECT_UNCERTAIN
                        if terminal == "BOOT_UNCERTAIN"
                        else V2StageState.BLOCKED
                    ),
                    refs(("boot_request", "host_boot")),
                )
            )
            _require(terminal == "BOOT_RETAINED" or len(events) == 5, error)
        if len(events) >= 6:
            expected.append(
                (
                    "QUERY_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(("identity", "boot_request", "host_boot")),
                )
            )
        if len(events) == 7:
            expected.append(("RETAINED", V2StageState.BLOCKED, refs(order)))
        previous = V2StageState.BLOCKED
        for event, (name, state, citations) in zip(events, expected):
            _require(
                event.stage is STAGE_ORDER[3]
                and event.previous_state is previous
                and event.state is state
                and event.detail_code == usb_reconnect_event(name, phase_id)
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
        minimum = (0, 4, 8, 8, 9, 9, 11)[len(events) - 1]
        maximum = (4, 8, 8, 9, 9, 11, 11)[len(events) - 1]
        _require(minimum <= len(records) <= maximum, error)

        operator = preparation = runtime_review = identity = campaign = intent = (
            boot
        ) = None
        if "operator_event" in records:
            operator = UsbReconnectOperatorEvent(
                canonical(records["operator_event"]["document"])
            )
            od = operator.to_dict()
            rebuilt = build_usb_reconnect_operator_event(
                plan=plan,
                absence=absence,
                phase_id=phase_id,
                launch_session_id=od["launch_session_id"],
                operator_id=od["operator_id"],
                phase_started_at_utc_ns=start.occurred_at_ns,
                reported_at_utc_ns=od["reported_at_utc_ns"],
            )
            _require(rebuilt.payload == operator.payload, error)
        if "enrollment" in records:
            assert operator is not None
            enrollment = records["enrollment"]["document"]
            verified = verify_native_camera_enrollment_snapshot(
                enrollment,
                source_sha256=bound["source_sha256"],
                launch_session_id=operator.to_dict()["launch_session_id"],
            )
            _require(
                verified == enrollment
                and enrollment["view"]["provenance"]["mode"] == "physical",
                error,
            )
        if "preparation" in records:
            assert operator is not None
            preparation = verify_usb_reconnect_preparation(
                canonical(records["preparation"]["document"]),
                expected_sha256=records["preparation"]["evidence_sha256"],
                original_baseline=baseline,
                absence=absence,
                absence_sources=predecessor["absence_sources"],
                absence_reference=absence_ref,
                phase_start_event=start,
                phase_id=phase_id,
                operator_event=operator,
                operator_event_reference=refs(("operator_event",))[0],
                enrollment=canonical(records["enrollment"]["document"]),
                enrollment_reference=refs(("enrollment",))[0],
            )
            pd = preparation.to_dict()
            _require(pd["operation"]["workspace"] == bound["workspace"], error)
            if len(events) >= 2:
                _require(events[1].occurred_at_ns >= pd["prepared_at_utc_ns"], error)
        if "operation" in records:
            assert preparation is not None
            operation = UsbIdentityOperation(
                canonical(records["operation"]["document"])
            )
            _require(
                operation.payload == canonical(preparation.to_dict()["operation"]),
                error,
            )
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
            assert preparation is not None and runtime_review is not None
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
            intent = verify_usb_reconnect_boot_intent(
                canonical(records["boot_request"]["document"]),
                expected_sha256=records["boot_request"]["evidence_sha256"],
                preparation=preparation,
                preparation_reference=refs(("preparation",))[0],
            )
        if len(events) >= 3:
            _require(
                events[2].occurred_at_ns
                >= max(
                    records["policy_review"]["document"]["reviewed_at_utc_ns"],
                    records["runtime_review"]["document"]["reviewed_at_ns"],
                ),
                error,
            )
        if "host_boot" in records:
            assert intent is not None
            boot = verify_usb_reconnect_boot_observation(
                canonical(records["host_boot"]["document"]),
                intent=intent,
                expected_sha256=records["host_boot"]["evidence_sha256"],
                requested_event=events[3],
            )
            if len(events) >= 5:
                derived = _terminal(
                    boot,
                    HostBootObservation(predecessor["absence_sources"]["host_boot"]),
                )
                _require(
                    (
                        terminal == derived
                        or (terminal == "BOOT_HELD" and derived == "BOOT_RETAINED")
                    )
                    and events[4].occurred_at_ns
                    >= boot.to_dict()["execution"]["finished_utc_ns"],
                    error,
                )

        audited = ledger_event = permit = None
        if own_campaigns:
            _require(
                len(events) >= 6 and campaign is not None and identity is not None,
                error,
            )
            assert campaign is not None and identity is not None
            audited, ledger_event = (
                own_campaigns[0]["original"],
                own_campaigns[0]["event"],
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
                | usb_reboot_evidence_ids
                | usb_complete_evidence_ids
                | mode_evidence_ids
            ]
            _require(
                permit.admission.journal_head_sha256
                == V2CommittedHead.build(
                    snapshot.header, snapshot.committed_events[: index + 6]
                ).head_sha256
                and permit.admission.stage_revision == index + 6
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
                    run.to_dict()["started_utc_ns"] >= events[5].occurred_at_ns
                    and audited["reference"]
                    == dict(
                        schema="rocell.usb_identity_campaign_reference.v1",
                        cell_id=bound["cell_id"],
                        session_id=bound["session_id"],
                        attempt_id=permit.attempt_id,
                        permit_sha256=permit.permit_sha256,
                        evidence_sha256=run.sha256,
                        payload_bytes=len(run.payload),
                        label="physical-native-usb-identity",
                    ),
                    error,
                )
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
            assert (
                operator is not None and preparation is not None and permit is not None
            )
            d = records["phase_record"]["document"]
            context = d["context"]
            _require(
                context["operation_id"] == phase_id
                and context["launch_session_id"]
                == operator.to_dict()["launch_session_id"]
                and context["operator_id"] == operator.to_dict()["operator_id"]
                and context["started_at_utc_ns"] == start.occurred_at_ns,
                error,
            )
            phase_sources = dict(
                operation=canonical(records["operation"]["document"]),
                operator_event=canonical(records["operator_event"]["document"]),
                native_enrollment=canonical(records["enrollment"]["document"]),
                owned_usb_run=canonical(records["execution"]["document"]),
                host_boot=canonical(records["host_boot"]["document"]),
            )
            verify_usb_reconnect_qualification_phase(
                canonical(d),
                expected_sha256=records["phase_record"]["evidence_sha256"],
                original_baseline=baseline,
                absence=absence,
                absence_sources=predecessor["absence_sources"],
                permit=permit,
                sources=phase_sources,
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
                        ("operation", "operation"),
                        ("operator_event", "operator_event"),
                        ("native_enrollment", "enrollment"),
                        ("owned_usb_run", "execution"),
                        ("host_boot", "host_boot"),
                    )
                ],
                error,
            )
            if len(events) == 7:
                _require(
                    events[6].occurred_at_ns >= context["finished_at_utc_ns"], error
                )
        outcome = "RETAINED_BLOCKED" if len(events) == 7 else expected[-1][0]
        if len(events) == 1:
            outcome = "PREPARATION_REQUESTED" if len(records) == 1 else "INCOMPLETE"
        elif len(records) > minimum and len(events) < 7:
            outcome = "INCOMPLETE"
        if audited is not None and len(events) < 7:
            outcome = "ORIGINAL_CAMPAIGN_HELD"
        return {
            **original,
            "schema": SOURCE_WORKFLOW_USB_RECONNECT_SCHEMA,
            "usb_qualification_reconnect": dict(
                phase_id=phase_id,
                phase="AFTER_RECONNECT",
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
