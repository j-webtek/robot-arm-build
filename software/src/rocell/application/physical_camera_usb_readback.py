"""Closed baseline USB suffix over the complete, original camera M1 history.

All inputs are original bytes supplied by the scoped session reader. No query,
stage transition, replay, or inferred qualification occurs during readback.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState, V2CommittedHead
from .physical_onboarding_durability import canonical_sha256
from .physical_camera_identity_readback import _verify_camera_identity_prefix
from .physical_camera_usb_baseline import (
    USB_EVENT,
    USB_ROLE_BYTES,
    METADATA_ROLES,
    UsbBaselineInspection,
    UsbBaselineOutcome,
    build_usb_baseline_outcome,
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
from rocell.providers.windows.usb_identity_registration import UsbIdentityRuntimeReview
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest


def read_original_usb_campaigns(
    transaction: Any, session_id: str, *, allow_trial_phase: bool = False
) -> tuple[dict[str, Any], ...]:
    """Use one real camera-family audit under the existing stage-only leases.

    The audit already checks every original record against the complete global
    attempt ledger. We retain a pre-terminal attempt as such, never as a result.
    """
    from .commissioning_camera_persistence import M1PhysicalCameraTransaction
    from .commissioning_m1_persistence import _M1CoordinatorTransaction
    from .commissioning_usb_identity_persistence import (
        RECORD_SCHEMA,
        decode_physical_usb_identity_permit,
    )
    from .physical_camera_session import _require

    error = "CAMERA_SESSION_USB_CAMPAIGN"
    _require(type(allow_trial_phase) is bool, error)
    _require(type(transaction) is M1PhysicalCameraTransaction, error)
    transaction._check_scope()
    leases = transaction.held_leases
    records = transaction._audit_records(include_family=True)
    attempts = transaction._attempts.snapshot()
    result = []
    for name, record in records.items():
        if record["schema"] != RECORD_SCHEMA or not name.startswith("request-"):
            continue
        data = record["data"]
        permit = decode_physical_usb_identity_permit(data["permit"])
        if permit.request.session_id != session_id:
            continue
        latest = attempts.latest_event(permit.attempt_id)
        _require(latest is not None, error)
        assert latest is not None
        terminal = records.get(
            f"result-{permit.attempt_id}-{latest.state.value.lower()}.json"
        )
        saved = None if terminal is None else terminal["data"]["result"]
        if saved is not None:
            _require(saved["state"] == latest.state.value, error)
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
                else "M1_TERMINAL_READ_BACK_EVIDENCE_PENDING"
            ),
        )
        artifact_record = records.get(f"evidence-{permit.attempt_id}-retained.json")
        if artifact_record is not None:
            artifacts = _M1CoordinatorTransaction._decode_campaign_evidence(
                permit, artifact_record
            )
            _require(len(artifacts) == 1, error)
            artifact = artifacts[0]
            evidence = OwnedUsbIdentityRunEvidence(artifact.payload)
            _require(
                artifact.label == "physical-native-usb-identity"
                and artifact.schema == evidence.to_dict()["schema"],
                error,
            )
            original.update(
                evidence=evidence.to_dict(),
                evidence_sha256=evidence.sha256,
                reference=dict(
                    schema="rocell.usb_identity_campaign_reference.v1",
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
        result.append(dict(original=original, event=latest.to_dict()))
    _require(
        len(result) <= (2 if allow_trial_phase else 1)
        and transaction._attempts.snapshot() == attempts
        and transaction.held_leases == leases,
        error,
    )
    transaction._check_scope()
    # Dataclass permits contain tuples and str-enums internally; the cached
    # workflow stays a detached JSON document like every older version.
    return tuple(json.loads(canonical(row)) for row in result)


def verify_usb_baseline_workflow(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    intake_packages: dict[str, dict[str, Any]],
    qualification_packages: dict[str, dict[str, Any]],
    qualification_originals: dict[str, bytes],
    static_packages: dict[str, dict[str, Any]],
    received_packages: dict[str, dict[str, Any]],
    received_originals: dict[str, bytes],
    identity_packages: dict[str, dict[str, Any]],
    usb_packages: dict[str, dict[str, Any]],
    *,
    original_campaigns: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    return _verify_usb_baseline_prefix(
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
        original_campaigns=original_campaigns,
        prefix_event_count=None,
        trial_evidence_ids=frozenset(),
    )


def _verify_usb_baseline_prefix(
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
    *,
    original_campaigns,
    prefix_event_count,
    trial_evidence_ids,
    usb_phase_evidence_ids=frozenset(),
    usb_phase_extension=False,
    usb_absence_evidence_ids=frozenset(),
    usb_absence_extension=False,
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
        SOURCE_WORKFLOW_USB_SCHEMA,
    )
    from .commissioning_usb_identity_persistence import (
        decode_physical_usb_identity_permit,
        _verify_admission_evidence,
    )

    state_error, chain_error, role_error = (
        "CAMERA_SESSION_USB_STATE",
        "CAMERA_SESSION_USB_CHAIN",
        "CAMERA_SESSION_USB_ROLE",
    )
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, state_error)
    _require(
        type(snapshot) is V2SessionSnapshot
        and type(original_campaigns) is tuple
        and len(original_campaigns) <= 1,
        chain_error,
    )
    _require(
        type(usb_phase_extension) is bool
        and type(usb_phase_evidence_ids) is frozenset
        and len(usb_phase_evidence_ids) <= 9
        and (usb_phase_extension or not usb_phase_evidence_ids)
        and (not usb_phase_extension or prefix_event_count is not None)
        and usb_phase_evidence_ids.isdisjoint(trial_evidence_ids),
        chain_error,
    )
    _require(
        type(trial_evidence_ids) is frozenset
        and len(trial_evidence_ids) <= 1
        and (prefix_event_count is not None or not trial_evidence_ids),
        chain_error,
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
            | usb_phase_evidence_ids
            | trial_evidence_ids
        ),
        chain_error,
    )
    _require(
        type(usb_reconnect_extension) is bool
        and (not usb_reconnect_extension or usb_absence_extension),
        chain_error,
    )
    _require(
        type(usb_absence_extension) is bool
        and type(usb_absence_evidence_ids) is frozenset
        and len(usb_absence_evidence_ids) <= 9
        and (usb_absence_extension or not usb_absence_evidence_ids)
        and (not usb_absence_extension or usb_phase_extension)
        and (not usb_absence_extension or prefix_event_count is not None)
        and usb_absence_evidence_ids.isdisjoint(
            trial_evidence_ids | usb_phase_evidence_ids
        ),
        chain_error,
    )
    _require(
        type(usb_reconnect_evidence_ids) is frozenset
        and len(usb_reconnect_evidence_ids) <= 11
        and (usb_reconnect_extension or not usb_reconnect_evidence_ids)
        and usb_reconnect_evidence_ids.isdisjoint(
            usb_absence_evidence_ids | usb_phase_evidence_ids | trial_evidence_ids
        ),
        chain_error,
    )
    if prefix_event_count is not None:
        _require(
            type(prefix_event_count) is int
            and 0 < prefix_event_count < len(snapshot.committed_events)
            and len(snapshot.committed_events) - prefix_event_count - mode_event_count
            <= (
                (37 if usb_complete_extension else 34)
                if usb_reboot_extension
                else (
                    27
                    if usb_reconnect_extension
                    else (
                        20
                        if usb_absence_extension
                        else (10 if usb_phase_extension else 2)
                    )
                )
            ),
            state_error,
        )
    starts = [
        (i, event)
        for i, event in enumerate(snapshot.committed_events)
        if event.detail_code.startswith("CAMERA_USB_INSPECTION_STARTED_")
    ]
    _require(len(starts) == 1, state_error)
    index, start = starts[0]
    match = USB_EVENT.fullmatch(start.detail_code)
    _require(match is not None, state_error)
    assert match is not None
    suffix = match[2]
    usb_id = "usbidentity-" + suffix.lower()
    order = tuple(USB_ROLE_BYTES)
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
    _require(
        len(usb_packages) <= 6
        and set(usb_packages).isdisjoint(identity_packages)
        and set(usb_packages) | set(identity_packages)
        == {
            ref.evidence_id
            for ref in snapshot.evidence
            if ref.stage is STAGE_ORDER[3]
            and ref.evidence_id
            not in trial_evidence_ids
            | usb_phase_evidence_ids
            | usb_absence_evidence_ids
            | usb_reconnect_evidence_ids
            | usb_reboot_evidence_ids
            | usb_complete_evidence_ids
            | mode_evidence_ids
        },
        role_error,
    )
    records: dict[str, Any] = {}
    for key, package in usb_packages.items():
        _require(
            type(package) is dict
            and set(package) == {"kind", "usb_id", "record"}
            and package["usb_id"] == usb_id
            and package["kind"] in order
            and package["kind"] not in records,
            role_error,
        )
        record, kind = package["record"], package["kind"]
        _require(
            type(record) is dict
            and set(record) == {"document", "evidence_sha256", "reference", "retention"}
            and record["retention"] == "M1_FULL_BYTES_READ_BACK"
            and inventory.get(key) == record["reference"],
            role_error,
        )
        raw = canonical(record["document"])
        _require(
            0 < len(raw) <= USB_ROLE_BYTES[kind]
            and len(raw) == record["reference"]["payload_bytes"]
            and digest(raw)
            == record["evidence_sha256"]
            == record["reference"]["payload_sha256"],
            chain_error,
        )
        records[kind] = record
    _require(
        tuple(role for role in order if role in records) == order[: len(records)],
        chain_error,
    )
    # The final v8 reader owns every extension reference/event. The private
    # prefix still receives the complete real snapshot and authenticates all
    # preceding source/static/received/metadata originals without changing head.
    original = _verify_camera_identity_prefix(
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
        prefix_event_count=index,
        usb_evidence_ids=frozenset(usb_packages),
        trial_evidence_ids=trial_evidence_ids,
        usb_trial_extension=prefix_event_count is not None,
        usb_phase_evidence_ids=usb_phase_evidence_ids,
        usb_phase_extension=usb_phase_extension,
        usb_absence_evidence_ids=usb_absence_evidence_ids,
        usb_absence_extension=usb_absence_extension,
        usb_reconnect_extension=usb_reconnect_extension,
        usb_reboot_extension=usb_reboot_extension,
        usb_reconnect_evidence_ids=usb_reconnect_evidence_ids,
        usb_reboot_evidence_ids=usb_reboot_evidence_ids,
        usb_complete_extension=usb_complete_extension,
        camera_mode_entry=camera_mode_entry,
        usb_complete_evidence_ids=usb_complete_evidence_ids,
    )
    latest = original["camera_identity_cycles"][-1]
    _require(latest["state"] == "REVIEWED_BLOCKED", state_error)
    events = snapshot.committed_events[index:prefix_event_count]
    _require(1 <= len(events) <= 5, state_error)
    codes = (
        "INSPECTION_STARTED",
        "INSPECTED",
        "REVIEWED",
        "QUERY_REQUESTED",
        "QUERY_RETAINED",
    )
    states = (
        V2StageState.WAITING_OPERATOR,
        V2StageState.REVIEW_PENDING,
        V2StageState.BLOCKED,
        V2StageState.WAITING_OPERATOR,
        V2StageState.BLOCKED,
    )
    for number, event in enumerate(events):
        if number == 0:
            refs = [latest[role]["reference"] for role in METADATA_ROLES]
        else:
            count = (1, 4, 4, 6)[number - 1]
            _require(len(records) >= count, state_error)
            refs = [records[role]["reference"] for role in order[:count]]
        _require(
            event.stage is STAGE_ORDER[3]
            and event.state is states[number]
            and event.detail_code == "CAMERA_USB_" + codes[number] + "_" + suffix
            and [ref.to_dict() for ref in event.evidence]
            == sorted(refs, key=lambda ref: ref["evidence_id"]),
            state_error,
        )
    _require(
        (len(events) > 1 or len(records) <= 1)
        and (len(events) >= 4 or len(records) <= 4)
        and (
            prefix_event_count is not None
            or snapshot.stages[3].state is events[-1].state
        )
        and all(
            row.state is V2StageState.PENDING and not row.evidence_ids
            for row in snapshot.stages[4 if camera_mode_entry is None else 5 :]
        ),
        state_error,
    )
    inspection = identity = runtime_review = campaign = None
    expected_binding = None
    try:
        if "inspection" in records:
            inspection = UsbBaselineInspection(
                canonical(records["inspection"]["document"])
            )
            data = inspection.to_dict()
            binding = data["binding"]
            expected_binding = dict(
                usb_id=usb_id,
                source_sha256=bound["source_sha256"],
                cell_id=bound["cell_id"],
                session_id=bound["session_id"],
                header_sha256=expected_header_sha256,
                origin_launch_id=bound["launch_id"],
                collection_launch_id=binding["collection_launch_id"],
                operator_id=binding["operator_id"],
                metadata={
                    role: latest[role]["evidence_sha256"] for role in METADATA_ROLES
                },
            )
            selected = latest["metadata"]["document"]["selection"]
            _require(
                binding == expected_binding
                and selected is not None
                and data["operation"]["selection"] == selected["document"]
                and data["operation"]["workspace"] == bound["workspace"],
                chain_error,
            )
        if "policy_review" in records:
            assert inspection is not None and expected_binding is not None
            review = UsbIdentityPolicyReview(
                canonical(records["policy_review"]["document"])
            ).to_dict()
            _require(
                all(
                    review[key] == expected_binding[key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                        "operator_id",
                    )
                )
                and review["policy"] == inspection.to_dict()["policy"]
                and review["reviewed_at_utc_ns"]
                >= inspection.to_dict()["collected_at_ns"],
                chain_error,
            )
        if "runtime_review" in records:
            runtime_review = UsbIdentityRuntimeReview(
                canonical(records["runtime_review"]["document"])
            )
            assert inspection is not None and expected_binding is not None
            rd = runtime_review.to_dict()
            op = inspection.to_dict()["operation"]
            sd = op["selection"]
            _require(
                rd["operator_id"] == expected_binding["operator_id"]
                and rd["reviewer_id"]
                == records["policy_review"]["document"]["reviewer_id"]
                and rd["reviewed_at_ns"] >= inspection.to_dict()["collected_at_ns"]
                and rd["source_sha256"] == expected_binding["source_sha256"]
                and rd["runtime_registration_sha256"]
                == inspection.to_dict()["runtime_report"]["runtime_registration_sha256"]
                and rd["operation_sha256"] == inspection.to_dict()["operation_sha256"]
                and rd["selection_sha256"] == digest(canonical(sd))
                and rd["native_identity_sha256"] == sd["native_identity_sha256"]
                and rd["endpoint_sha256"] == sd["endpoint_sha256"]
                and rd["device_instance_id_sha256"]
                == digest(
                    sd["metadata_review"]["observed_instance_id"].encode("utf-8")
                ),
                chain_error,
            )
        if "identity" in records:
            identity = UsbIdentityAdmissionIdentity(
                canonical(records["identity"]["document"])
            )
            assert inspection is not None and runtime_review is not None
            idd = identity.to_dict()
            _require(
                all(
                    idd[key] == inspection.to_dict()["binding"][key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                ),
                chain_error,
            )
            expected_subjects = []
            for role in ("metadata", "policy_review", "runtime_review"):
                item = latest[role] if role == "metadata" else records[role]
                expected_subjects.append(
                    dict(
                        role=role,
                        reference=item["reference"],
                        document_sha256=item["evidence_sha256"],
                    )
                )
            _require(
                idd["original_subjects"] == expected_subjects
                and idd["policy_review_sha256"]
                == records["policy_review"]["evidence_sha256"],
                chain_error,
            )
            campaign = PhysicalUsbIdentityCampaign(
                UsbIdentityOperation(canonical(inspection.to_dict()["operation"])),
                identity=identity,
                review=runtime_review,
            )
        audited = event_document = None
        if original_campaigns:
            _require(len(events) >= 4 and campaign is not None, state_error)
            assert campaign is not None and identity is not None
            row = original_campaigns[0]
            _require(set(row) == {"original", "event"}, chain_error)
            audited, event_document = row["original"], row["event"]
            permit = decode_physical_usb_identity_permit(audited["permit"])
            campaign.preparation_for_permit(permit)
            transfer_ids = {
                records[role]["reference"]["evidence_id"]
                for role in ("execution", "outcome")
                if role in records
            }
            query_inventory = [
                ref.to_dict()
                for ref in snapshot.evidence
                if ref.evidence_id
                not in transfer_ids
                | trial_evidence_ids
                | usb_phase_evidence_ids
                | usb_absence_evidence_ids
                | usb_reconnect_evidence_ids
                | usb_reboot_evidence_ids
                | usb_complete_evidence_ids
                | mode_evidence_ids
            ]
            _require(
                permit.admission.journal_head_sha256
                == V2CommittedHead.build(
                    snapshot.header, snapshot.committed_events[: index + 4]
                ).head_sha256
                and permit.admission.stage_revision == index + 4
                and permit.admission.evidence_inventory_sha256
                == canonical_sha256(query_inventory)
                and permit.admission.stage_state is V2StageState.WAITING_OPERATOR,
                chain_error,
            )
            _verify_admission_evidence(audited["admission_evidence"], permit.admission)
            _require(
                audited["admission_evidence"]["selected_identity"] == identity.to_dict()
                and event_document["attempt_id"] == permit.attempt_id
                and event_document["operation_binding_sha256"] == permit.permit_sha256,
                chain_error,
            )
            if audited["evidence"] is not None:
                verified = verify_usb_identity_campaign_evidence(
                    OwnedUsbIdentityRunEvidence(canonical(audited["evidence"])),
                    campaign=campaign,
                    permit=permit,
                    expected_evidence_sha256=audited["evidence_sha256"],
                )
                if (
                    audited["result"] is not None
                    and audited["result"]["receipt"] is not None
                ):
                    _require(
                        audited["result"]["receipt"]["evidence_sha256s"]
                        == [verified.sha256]
                        and audited["result"]["receipt"]["output_bytes"]
                        == len(verified.payload),
                        chain_error,
                    )
        if "execution" in records:
            _require(
                audited is not None
                and audited["evidence"] == records["execution"]["document"]
                and audited["evidence_sha256"]
                == records["execution"]["evidence_sha256"]
                and audited["result"] is not None
                and audited["result"]["state"] == "SEALED_KNOWN",
                chain_error,
            )
        if "outcome" in records:
            assert (
                inspection is not None and identity is not None and audited is not None
            )
            outcome = UsbBaselineOutcome(canonical(records["outcome"]["document"]))
            expected = build_usb_baseline_outcome(
                inspection=inspection,
                identity=identity,
                execution_reference=_parse_evidence_reference(
                    records["execution"]["reference"]
                ),
                campaign_original=audited,
                recorded_at_ns=outcome.to_dict()["recorded_at_ns"],
            )
            _require(outcome.payload == expected.payload, chain_error)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise PhysicalCameraSessionError(chain_error) from error
    state = "INCOMPLETE"
    if len(events) == 2 and len(records) == 1:
        state = "REVIEW_PENDING"
    if len(events) == 4:
        state = "READY_TO_QUERY" if not original_campaigns else "ORIGINAL_CAMPAIGN_HELD"
    if len(events) == 5:
        state = "RETAINED_BLOCKED"
    return {
        **original,
        "schema": SOURCE_WORKFLOW_USB_SCHEMA,
        "usb_baseline": dict(
            usb_id=usb_id,
            state=state,
            **{role: records.get(role) for role in order},
            query_event=events[3].to_dict() if len(events) >= 4 else None,
            original_campaign=audited,
            campaign_event=event_document,
        ),
    }
