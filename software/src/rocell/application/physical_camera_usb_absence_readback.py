"""Original v11 physical-node ABSENCE suffix over the authentic full v10 audit."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from .physical_camera_usb_absence_constants import (
    SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
    MAX_USB_ABSENCE_EVENTS,
    USB_ABSENCE_ROLE_BYTES,
    USB_ABSENCE_EVENT,
    usb_absence_event,
)
from .physical_camera_usb_absence import (
    original_usb_absence_baseline,
    verify_usb_absence_preparation,
)
from .physical_camera_usb_phase_readback import _verify_usb_phase_prefix
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState, V2CommittedHead
from .physical_onboarding_durability import canonical_sha256
from .physical_usb_presence_binding import build_usb_presence_phase_binding
from .physical_usb_presence_campaign import (
    UsbPresenceOperation,
    PhysicalUsbPresenceCampaign,
    verify_usb_presence_campaign_evidence,
)
from .physical_usb_presence_phase import (
    UsbPresenceOperatorEvent,
    build_usb_presence_operator_event,
    verify_usb_presence_qualification_phase,
)
from .physical_usb_absence_boot import (
    verify_usb_absence_boot_intent,
    verify_usb_absence_boot_review,
    verify_usb_absence_boot_observation,
    _terminal,
)
from .usb_presence_stage_policy import usb_presence_stage_policy
from .commissioning_usb_presence_persistence import (
    decode_physical_usb_presence_permit,
    verify_usb_presence_admission_evidence,
)
from rocell.providers.windows.usb_presence_protocol import canonical, digest
from rocell.providers.windows.usb_presence_registration import (
    UsbPresenceRuntimeRegistration,
)
from rocell.providers.windows.usb_presence_review import (
    UsbPresenceRuntimeReview,
    verify_usb_presence_runtime_review,
)
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
)
from rocell.providers.windows.host_boot_observation import HostBootObservation


def read_original_usb_absence_campaigns(
    transaction: Any,
    session_id: str,
    *,
    _usb_reconnect_extension: bool = False,
    _usb_reboot_extension: bool = False,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """One complete sibling-ledger audit; return old descriptor and new presence records."""
    from .commissioning_camera_persistence import M1PhysicalCameraTransaction
    from .commissioning_m1_persistence import _M1CoordinatorTransaction
    from .commissioning_usb_identity_persistence import (
        RECORD_SCHEMA as IDENTITY_RECORD_SCHEMA,
        decode_physical_usb_identity_permit,
    )
    from .commissioning_usb_presence_persistence import (
        RECORD_SCHEMA as PRESENCE_RECORD_SCHEMA,
    )
    from .physical_camera_session import _require
    from rocell.providers.windows.owned_usb_identity_evidence import (
        OwnedUsbIdentityRunEvidence,
    )

    error = "CAMERA_SESSION_USB_ABSENCE_CAMPAIGN"
    _require(type(_usb_reconnect_extension) is bool, error)
    _require(
        type(_usb_reboot_extension) is bool
        and (not _usb_reboot_extension or _usb_reconnect_extension),
        error,
    )
    _require(type(transaction) is M1PhysicalCameraTransaction, error)
    transaction._check_scope()
    leases = transaction.held_leases
    records = transaction._audit_records(include_family=True)
    attempts = transaction._attempts.snapshot()
    result: dict[str, list[dict[str, Any]]] = {"identity": [], "presence": []}
    for name, record in records.items():
        if not name.startswith("request-") or record["schema"] not in {
            IDENTITY_RECORD_SCHEMA,
            PRESENCE_RECORD_SCHEMA,
        }:
            continue
        presence = record["schema"] == PRESENCE_RECORD_SCHEMA
        decode = (
            decode_physical_usb_presence_permit
            if presence
            else decode_physical_usb_identity_permit
        )
        data = record["data"]
        permit = decode(data["permit"])
        if permit.request.session_id != session_id:
            continue
        latest = attempts.latest_event(permit.attempt_id)
        _require(latest is not None, error)
        assert latest is not None
        terminal = records.get(
            f"result-{permit.attempt_id}-{latest.state.value.lower()}.json"
        )
        saved = None if terminal is None else terminal["data"]["result"]
        _require(saved is None or saved["state"] == latest.state.value, error)
        original = dict(
            permit=asdict(permit),
            result=saved,
            admission_evidence=data["admission_evidence"],
            evidence=None,
            evidence_sha256=None,
            reference=None,
            retention=(
                "M1_ATTEMPT_READ_BACK_TERMINAL_PENDING"
                if saved is None
                else (
                    "M1_TERMINAL_READ_BACK_NO_EVIDENCE"
                    if presence
                    else "M1_TERMINAL_READ_BACK_EVIDENCE_PENDING"
                )
            ),
        )
        artifact_record = records.get(f"evidence-{permit.attempt_id}-retained.json")
        if artifact_record is not None:
            artifacts = _M1CoordinatorTransaction._decode_campaign_evidence(
                permit, artifact_record
            )
            _require(len(artifacts) == 1, error)
            artifact = artifacts[0]
            evidence = (
                OwnedUsbPresenceRunEvidence(artifact.payload)
                if presence
                else OwnedUsbIdentityRunEvidence(artifact.payload)
            )
            kind = "presence" if presence else "identity"
            _require(
                artifact.label == "physical-native-usb-" + kind
                and artifact.schema == evidence.to_dict()["schema"],
                error,
            )
            original.update(
                evidence=evidence.to_dict(),
                evidence_sha256=evidence.sha256,
                reference=dict(
                    schema="rocell.usb_" + kind + "_campaign_reference.v1",
                    cell_id=permit.request.cell_id,
                    session_id=session_id,
                    attempt_id=permit.attempt_id,
                    permit_sha256=permit.permit_sha256,
                    evidence_sha256=evidence.sha256,
                    payload_bytes=len(evidence.payload),
                    label=artifact.label,
                ),
                retention=(
                    "M1_FULL_BYTES_READ_BACK"
                    if saved is not None
                    else "M1_ATTEMPT_READ_BACK_TERMINAL_PENDING"
                ),
            )
        result["presence" if presence else "identity"].append(
            dict(original=original, event=latest.to_dict())
        )
    _require(
        len(result["identity"])
        <= (4 if _usb_reboot_extension else (3 if _usb_reconnect_extension else 2))
        and len(result["presence"]) <= 1
        and transaction._attempts.snapshot() == attempts
        and transaction.held_leases == leases,
        error,
    )
    transaction._check_scope()
    return {
        key: tuple(json.loads(canonical(row)) for row in rows)
        for key, rows in result.items()
    }


def verify_usb_absence_workflow(
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
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
) -> dict[str, Any]:
    return _verify_usb_absence_prefix(
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
        original_campaigns=original_campaigns,
        original_presence_campaigns=original_presence_campaigns,
    )


def _verify_usb_absence_prefix(
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
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
    prefix_event_count=None,
    usb_reconnect_evidence_ids=frozenset(),
    usb_reboot_extension=False,
    usb_reboot_evidence_ids=frozenset(),
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
    usb_complete_evidence_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    from .physical_camera_session import _require, PhysicalCameraSessionError

    error = "CAMERA_SESSION_USB_ABSENCE_INVALID"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, error)
    try:
        _require(
            type(snapshot) is V2SessionSnapshot
            and type(original_presence_campaigns) is tuple
            and len(original_presence_campaigns) <= 1,
            error,
        )
        _require(
            type(usb_reconnect_evidence_ids) is frozenset
            and len(usb_reconnect_evidence_ids) <= 11
            and (prefix_event_count is not None or not usb_reconnect_evidence_ids),
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
            and (not usb_reboot_extension or prefix_event_count is not None)
            and type(usb_reboot_evidence_ids) is frozenset
            and len(usb_reboot_evidence_ids) <= 11
            and (usb_reboot_extension or not usb_reboot_evidence_ids),
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
                <= (
                    17
                    if usb_complete_extension
                    else (14 if usb_reboot_extension else 7)
                ),
                error,
            )
        starts = [
            (i, event)
            for i, event in enumerate(snapshot.committed_events)
            if event.detail_code.startswith(
                "CAMERA_USB_TRIAL_ABSENCE_PREPARATION_REQUESTED_"
            )
        ]
        _require(len(starts) == 1 and len(absence_packages) <= 9, error)
        index, start = starts[0]
        match = USB_ABSENCE_EVENT.fullmatch(start.detail_code)
        _require(match is not None and index > 0, error)
        assert match is not None
        phase_id = "usbphase-" + match[2].lower()
        events = snapshot.committed_events[index:prefix_event_count]
        _require(1 <= len(events) <= MAX_USB_ABSENCE_EVENTS, error)
        order = tuple(USB_ABSENCE_ROLE_BYTES)
        inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
        records = {}
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
        ):
            other_ids.update(packages)
        _require(
            set(absence_packages).isdisjoint(other_ids)
            and usb_reconnect_evidence_ids.isdisjoint(other_ids | set(absence_packages))
            and usb_reboot_evidence_ids.isdisjoint(
                other_ids | set(absence_packages) | usb_reconnect_evidence_ids
            )
            and usb_complete_evidence_ids.isdisjoint(
                other_ids | set(absence_packages) | usb_reconnect_evidence_ids
            )
            and set(inventory)
            == other_ids
            | set(absence_packages)
            | usb_reconnect_evidence_ids
            | usb_reboot_evidence_ids
            | usb_complete_evidence_ids
            | mode_evidence_ids,
            error,
        )
        for key, package in absence_packages.items():
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
                0 < len(raw) <= USB_ABSENCE_ROLE_BYTES[kind]
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
        original = _verify_usb_phase_prefix(
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
            prefix_event_count=index,
            usb_absence_evidence_ids=frozenset(absence_packages),
            usb_reconnect_extension=prefix_event_count is not None,
            usb_reconnect_evidence_ids=usb_reconnect_evidence_ids,
            usb_reboot_extension=usb_reboot_extension,
            usb_reboot_evidence_ids=usb_reboot_evidence_ids,
            usb_complete_extension=usb_complete_extension,
            camera_mode_entry=camera_mode_entry,
            usb_complete_evidence_ids=usb_complete_evidence_ids,
        )
        baseline = original_usb_absence_baseline(original)
        binding = build_usb_presence_phase_binding(**baseline)
        trial_id = binding.to_dict()["binding"]["trial_id"]
        _require(
            phase_id != baseline["baseline"].to_dict()["context"]["operation_id"]
            and start.occurred_at_ns
            >= snapshot.committed_events[index - 1].occurred_at_ns
            and start.occurred_at_ns >= binding.to_dict()["not_before_utc_ns"],
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
            (
                "PREPARATION_REQUESTED",
                V2StageState.WAITING_OPERATOR,
                (baseline["baseline_reference"],),
            )
        ]
        if len(events) >= 2:
            expected.append(("PREPARED", V2StageState.REVIEW_PENDING, refs(order[:4])))
        if len(events) >= 3:
            expected.append(
                (
                    "BOOT_REVIEWED",
                    V2StageState.BLOCKED,
                    refs(("boot_intent", "boot_review")),
                )
            )
        if len(events) >= 4:
            expected.append(
                (
                    "BOOT_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(("boot_intent",)),
                )
            )
        terminal = None
        if len(events) >= 5:
            matched = USB_ABSENCE_EVENT.fullmatch(events[4].detail_code)
            _require(
                matched is not None
                and matched[1] in {"BOOT_RETAINED", "BOOT_HELD", "BOOT_UNCERTAIN"},
                error,
            )
            assert matched is not None
            terminal = matched[1]
            expected.append(
                (
                    terminal,
                    (
                        V2StageState.SIDE_EFFECT_UNCERTAIN
                        if terminal == "BOOT_UNCERTAIN"
                        else V2StageState.BLOCKED
                    ),
                    refs(("boot_intent", "host_boot")),
                )
            )
            _require(terminal == "BOOT_RETAINED" or len(events) == 5, error)
        if len(events) >= 6:
            expected.append(
                (
                    "PRESENCE_REVIEW_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(order[:6]),
                )
            )
        if len(events) >= 7:
            expected.append(
                (
                    "PRESENCE_REVIEW_PREPARED",
                    V2StageState.REVIEW_PENDING,
                    refs(order[:6]),
                )
            )
        if len(events) >= 8:
            expected.append(
                ("RUNTIME_REVIEWED", V2StageState.BLOCKED, refs(("runtime_review",)))
            )
        if len(events) >= 9:
            expected.append(
                (
                    "QUERY_REQUESTED",
                    V2StageState.WAITING_OPERATOR,
                    refs(("runtime_review",)),
                )
            )
        if len(events) == 10:
            expected.append(("RETAINED", V2StageState.BLOCKED, refs(order)))
        previous = V2StageState.BLOCKED
        for event, (name, state, citations) in zip(events, expected):
            _require(
                event.stage is STAGE_ORDER[3]
                and event.previous_state is previous
                and event.state is state
                and event.detail_code
                == usb_absence_event(name, phase_id, trial_id=trial_id)
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
        minimum = (0, 4, 5, 5, 6, 6, 6, 7, 7, 9)[len(events) - 1]
        maximum = (4, 5, 5, 6, 6, 6, 7, 7, 9, 9)[len(events) - 1]
        _require(minimum <= len(records) <= maximum, error)
        operation = operator = preparation = intent = boot = review = campaign = None
        if "operation" in records:
            operation = UsbPresenceOperation(
                canonical(records["operation"]["document"])
            )
            op = operation.to_dict()
            _require(
                op["operation_id"] == phase_id
                and op["phase_binding"] == binding.to_dict()
                and op["workspace"] == bound["workspace"],
                error,
            )
        if "operator_event" in records:
            operator = UsbPresenceOperatorEvent(
                canonical(records["operator_event"]["document"])
            )
            od = operator.to_dict()
            rebuilt = build_usb_presence_operator_event(
                phase_binding=binding,
                phase_id=phase_id,
                launch_session_id=op["launch_session_id"],
                operator_id=od["operator_id"],
                phase_started_at_utc_ns=start.occurred_at_ns,
                reported_at_utc_ns=od["reported_at_utc_ns"],
            )
            _require(rebuilt.payload == operator.payload, error)
        args = None
        if "preparation" in records:
            args = dict(
                operation=operation,
                operation_reference=refs(("operation",))[0],
                operator_event=operator,
                operator_event_reference=refs(("operator_event",))[0],
                phase_start_event=start,
                original_baseline=baseline,
            )
            preparation = verify_usb_absence_preparation(
                canonical(records["preparation"]["document"]),
                expected_sha256=records["preparation"]["evidence_sha256"],
                **args,
            )
        if "boot_intent" in records:
            assert args is not None
            intent = verify_usb_absence_boot_intent(
                canonical(records["boot_intent"]["document"]),
                expected_sha256=records["boot_intent"]["evidence_sha256"],
                **args,
            )
        if len(events) >= 2:
            _require(
                preparation is not None
                and events[1].occurred_at_ns
                >= preparation.to_dict()["prepared_at_utc_ns"],
                error,
            )
        if "boot_review" in records:
            assert intent is not None
            boot_review = verify_usb_absence_boot_review(
                canonical(records["boot_review"]["document"]),
                intent=intent,
                expected_sha256=records["boot_review"]["evidence_sha256"],
            )
            _require(
                boot_review.to_dict()["reviewed_at_ns"] >= events[1].occurred_at_ns,
                error,
            )
            if len(events) >= 3:
                _require(
                    events[2].occurred_at_ns >= boot_review.to_dict()["reviewed_at_ns"],
                    error,
                )
        if "host_boot" in records:
            assert intent is not None
            boot = verify_usb_absence_boot_observation(
                canonical(records["host_boot"]["document"]),
                intent=intent,
                expected_sha256=records["host_boot"]["evidence_sha256"],
                requested_event=events[3],
            )
            if len(events) >= 5:
                derived_terminal = _terminal(
                    boot,
                    HostBootObservation(baseline["baseline_sources"]["host_boot"]),
                )
                _require(
                    (
                        terminal == derived_terminal
                        or (
                            terminal == "BOOT_HELD"
                            and derived_terminal == "BOOT_RETAINED"
                        )
                    )
                    and events[4].occurred_at_ns
                    >= boot.to_dict()["execution"]["finished_utc_ns"],
                    error,
                )
        if "runtime_review" in records:
            assert operation is not None and operator is not None and boot is not None
            review = UsbPresenceRuntimeReview(
                canonical(records["runtime_review"]["document"])
            )
            verify_usb_presence_runtime_review(
                review,
                runtime=UsbPresenceRuntimeRegistration(canonical(op["runtime"])),
                phase_binding=binding,
                policy=usb_presence_stage_policy(),
                operation_sha256=operation.sha256,
                expected_review_sha256=records["runtime_review"]["evidence_sha256"],
            )
            rd = review.to_dict()
            _require(
                rd["operator_id"] == operator.to_dict()["operator_id"]
                and rd["launch_session_id"] == op["launch_session_id"]
                and rd["reviewed_at_ns"] >= events[6].occurred_at_ns,
                error,
            )
            if len(events) >= 8:
                _require(events[7].occurred_at_ns >= rd["reviewed_at_ns"], error)
            campaign = PhysicalUsbPresenceCampaign(operation, review=review)
        audited = ledger_event = None
        if original_presence_campaigns:
            _require(len(events) >= 9 and campaign is not None, error)
            row = original_presence_campaigns[0]
            _require(type(row) is dict and set(row) == {"original", "event"}, error)
            audited, ledger_event = row["original"], row["event"]
            permit = decode_physical_usb_presence_permit(audited["permit"])
            assert campaign is not None
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
                | usb_reconnect_evidence_ids
                | usb_reboot_evidence_ids
                | usb_complete_evidence_ids
                | mode_evidence_ids
            ]
            _require(
                permit.admission.journal_head_sha256
                == V2CommittedHead.build(
                    snapshot.header, snapshot.committed_events[: index + 9]
                ).head_sha256
                and permit.admission.stage_revision == index + 9
                and permit.admission.evidence_inventory_sha256
                == canonical_sha256(query_inventory)
                and permit.admission.stage_state is V2StageState.WAITING_OPERATOR,
                error,
            )
            verify_usb_presence_admission_evidence(
                audited["admission_evidence"], permit.admission, permit=permit
            )
            facts = audited["admission_evidence"]
            _require(
                facts["selected_identity"] == binding.to_dict()
                and facts["runtime_review"] == records["runtime_review"]["document"]
                and facts["runtime_review_reference"]
                == records["runtime_review"]["reference"]
                and facts["runtime_review_event"] == events[7].to_dict()
                and ledger_event["attempt_id"] == permit.attempt_id
                and ledger_event["operation_binding_sha256"] == permit.permit_sha256,
                error,
            )
            if audited["evidence"] is not None:
                run = verify_usb_presence_campaign_evidence(
                    OwnedUsbPresenceRunEvidence(canonical(audited["evidence"])),
                    campaign=campaign,
                    permit=permit,
                    expected_evidence_sha256=audited["evidence_sha256"],
                )
                _require(
                    run.to_dict()["started_utc_ns"] >= events[8].occurred_at_ns
                    and audited["reference"]
                    == dict(
                        schema="rocell.usb_presence_campaign_reference.v1",
                        cell_id=bound["cell_id"],
                        session_id=bound["session_id"],
                        attempt_id=permit.attempt_id,
                        permit_sha256=permit.permit_sha256,
                        evidence_sha256=run.sha256,
                        payload_bytes=len(run.payload),
                        label="physical-native-usb-presence",
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
            assert operator is not None
            d = records["phase_record"]["document"]
            context = d["context"]
            _require(
                context["operation_id"] == phase_id
                and context["launch_session_id"] == op["launch_session_id"]
                and context["operator_id"] == operator.to_dict()["operator_id"]
                and context["started_at_utc_ns"] == start.occurred_at_ns,
                error,
            )
            verify_usb_presence_qualification_phase(
                canonical(d),
                expected_sha256=records["phase_record"]["evidence_sha256"],
                original_baseline=baseline,
                sources={
                    name: canonical(records[role]["document"])
                    for name, role in (
                        ("operation", "operation"),
                        ("operator_event", "operator_event"),
                        ("owned_presence_run", "execution"),
                        ("host_boot", "host_boot"),
                    )
                },
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
                        ("owned_presence_run", "execution"),
                        ("host_boot", "host_boot"),
                    )
                ],
                error,
            )
            if len(events) == 10:
                _require(
                    events[9].occurred_at_ns >= context["finished_at_utc_ns"], error
                )
        outcome = "RETAINED_BLOCKED" if len(events) == 10 else expected[-1][0]
        if len(records) > minimum and len(events) < 10:
            outcome = "INCOMPLETE"
        if audited is not None and len(events) < 10:
            outcome = "ORIGINAL_CAMPAIGN_HELD"
        return {
            **original,
            "schema": SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
            "usb_qualification_absence": dict(
                phase_id=phase_id,
                phase="RECONNECT_ABSENCE",
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
