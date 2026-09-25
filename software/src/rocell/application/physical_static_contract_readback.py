"""Original stage-2 subjects and exact journal suffix; never collection/replay.

Design acceptance does not grant camera runtime release or claim installation
measurements. All retained subjects are read by the camera session owner under
its original stage-only storage leases before this pure verifier is called.
"""

from __future__ import annotations

import re
from typing import Any

from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState
from .physical_source_qualification_readback import (
    STATIC_CAMERA_EVENT,
    _verify_qualification_prefix,
)
from rocell.providers.windows.native_camera_protocol import canonical

STATIC_CONTRACT_EVENT = re.compile(
    r"STATIC_CAMERA_CONTRACT_(COLLECTED|REVIEWED_PASS|REVIEWED_BLOCKED)_([0-9A-F]{32})"
)
CAMERA_RECEIPT_EVENT = re.compile(r"CAMERA_RECEIPT_REQUESTED_([0-9A-F]{32})")


def verify_static_contract_workflow(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    intake_packages: dict[str, dict[str, Any]],
    qualification_packages: dict[str, dict[str, Any]],
    qualification_originals: dict[str, bytes],
    static_packages: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Verify one stage-owned cycle after the complete original v4 prefix.

    No caller verifier/approval callback or fabricated earlier snapshot is
    accepted. Partial originals remain distinct from committed stage verdicts.
    """
    return _verify_static_contract_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        prefix_event_count=None,
    )


def _verify_static_contract_prefix(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    intake_packages: dict[str, dict[str, Any]],
    qualification_packages: dict[str, dict[str, Any]],
    qualification_originals: dict[str, bytes],
    static_packages: dict[str, dict[str, Any]],
    *,
    prefix_event_count: int | None,
    camera_identity_extension: bool = False,
    usb_identity_extension: bool = False,
    usb_trial_extension: bool = False,
    usb_phase_extension: bool = False,
    usb_absence_extension: bool = False,
    usb_reconnect_extension: bool = False,
    usb_reboot_extension: bool = False,
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
) -> dict[str, Any]:
    """Authenticate the actual full audit, optionally through original stage-3 entry.

    The sole private v6 caller separately verifies every received-camera suffix
    event and package. No earlier snapshot, inventory or head is substituted.
    """
    from .physical_camera_session import (
        PhysicalCameraSessionError,
        SOURCE_WORKFLOW_STATIC_SCHEMA,
        _require,
    )
    from .physical_camera_prerequisites import verify_physical_camera_prerequisites
    from .physical_source_qualification import SourceQualificationReceipt
    from .physical_static_contract import (
        StaticCameraContractReceipt,
        verify_static_camera_contract_receipt,
        verify_static_camera_contract_assessment,
        verify_static_camera_contract_review,
    )

    state_error = "CAMERA_SESSION_STATIC_CONTRACT_STATE"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, state_error)
    chain_error = "CAMERA_SESSION_STATIC_CONTRACT_CHAIN"
    role_error = "CAMERA_SESSION_STATIC_CONTRACT_ROLE"
    _require(type(snapshot) is V2SessionSnapshot, chain_error)
    entries = [
        (index, event)
        for index, event in enumerate(snapshot.committed_events)
        if STATIC_CAMERA_EVENT.fullmatch(event.detail_code)
    ]
    _require(len(entries) == 1, state_error)
    entry_index, entry = entries[0]
    original = _verify_qualification_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        prefix_event_count=entry_index + 1,
        received_camera_extension=prefix_event_count is not None,
        camera_identity_extension=camera_identity_extension,
        usb_identity_extension=usb_identity_extension,
        usb_trial_extension=usb_trial_extension,
        usb_phase_extension=usb_phase_extension,
        usb_absence_extension=usb_absence_extension,
        usb_reconnect_extension=usb_reconnect_extension,
        usb_reboot_extension=usb_reboot_extension,
        usb_complete_extension=usb_complete_extension,
        camera_mode_entry=camera_mode_entry,
    )
    _require(
        original["state"] == "PASS"
        and original["static_camera_request"] == entry.to_dict()
        and original["qualification_cycles"][-1]["state"] == "REVIEWED_PASS",
        state_error,
    )
    _require(
        not camera_identity_extension or prefix_event_count is not None, state_error
    )
    _require(not usb_identity_extension or camera_identity_extension, state_error)
    _require(not usb_trial_extension or usb_identity_extension, state_error)
    _require(not usb_phase_extension or usb_trial_extension, state_error)
    _require(
        type(usb_complete_extension) is bool
        and (not usb_complete_extension or usb_reboot_extension)
        and type(usb_reboot_extension) is bool
        and (not usb_reboot_extension or usb_reconnect_extension),
        state_error,
    )
    _require(
        type(usb_reconnect_extension) is bool
        and (not usb_reconnect_extension or usb_absence_extension),
        state_error,
    )
    _require(
        type(usb_absence_extension) is bool
        and (not usb_absence_extension or usb_phase_extension),
        state_error,
    )
    if prefix_event_count is not None:
        _require(
            type(prefix_event_count) is int
            and prefix_event_count == entry_index + 4
            and 0
            <= len(snapshot.committed_events) - prefix_event_count - mode_event_count
            <= (
                (
                    (
                        (65 if usb_complete_extension else 62)
                        if usb_reboot_extension
                        else (55 if usb_reconnect_extension else 48)
                    )
                    if usb_absence_extension
                    else (
                        38
                        if usb_phase_extension
                        else (30 if usb_trial_extension else 28)
                    )
                )
                if usb_identity_extension
                else (23 if camera_identity_extension else 12)
            ),
            state_error,
        )
    suffix = snapshot.committed_events[entry_index + 1 : prefix_event_count]
    _require(len(suffix) <= 3, state_error)
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
    contract_ids = {package["contract_id"] for package in static_packages.values()}
    _require(len(contract_ids) == 1, role_error)
    contract_id = next(iter(contract_ids))
    _require(
        type(contract_id) is str
        and re.fullmatch(r"staticcontract-[0-9a-f]{32}", contract_id) is not None,
        role_error,
    )
    records: dict[str, dict[str, Any]] = {}
    for package in static_packages.values():
        kind, record = package["kind"], package["record"]
        _require(
            kind in {"receipt", "assessment", "review"}
            and kind not in records
            and record["reference"]["stage"] == STAGE_ORDER[1].value
            and inventory.get(record["reference"]["evidence_id"])
            == record["reference"],
            role_error,
        )
        records[kind] = record
    present = tuple(
        role for role in ("receipt", "assessment", "review") if role in records
    )
    _require(
        present == ("receipt", "assessment", "review")[: len(present)], chain_error
    )
    _require("receipt" in records, chain_error)
    receipt = assessment = review = None
    try:
        prerequisites = verify_physical_camera_prerequisites(
            canonical(roles["prerequisites"]["document"]),
            expected_source_sha256=bound["source_sha256"],
            expected_session_id=bound["session_id"],
            expected_launch_session_id=bound["launch_id"],
            expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
        )
        source_cycle = original["qualification_cycles"][-1]
        source_receipt = SourceQualificationReceipt(
            canonical(source_cycle["receipt"]["document"])
        )
        wire = canonical(records["receipt"]["document"])
        retained_binding = StaticCameraContractReceipt(wire).to_dict()["binding"]
        expected_binding = {
            "contract_id": contract_id,
            "source_sha256": bound["source_sha256"],
            "cell_id": bound["cell_id"],
            "session_id": bound["session_id"],
            "header_sha256": expected_header_sha256,
            "origin_launch_id": bound["launch_id"],
            "collection_launch_id": retained_binding["collection_launch_id"],
            "operator_id": retained_binding["operator_id"],
            "prerequisites_sha256": prerequisites.evidence_sha256,
            "source_qualification": {
                role: source_cycle[role]["evidence_sha256"]
                for role in ("receipt", "assessment", "review")
            },
            "static_request_event_sha256": entry.event_sha256,
            "store_directory": bound["directory"],
        }
        receipt = verify_static_camera_contract_receipt(
            wire,
            prerequisites=prerequisites,
            source_qualification=source_receipt,
            expected_binding=expected_binding,
            expected_receipt_sha256=records["receipt"]["evidence_sha256"],
        )
        if "assessment" in records:
            assessment = verify_static_camera_contract_assessment(
                canonical(records["assessment"]["document"]),
                receipt=receipt,
                expected_assessment_sha256=records["assessment"]["evidence_sha256"],
            )
        if "review" in records:
            _require(assessment is not None, chain_error)
            assert assessment is not None
            review = verify_static_camera_contract_review(
                canonical(records["review"]["document"]),
                receipt=receipt,
                assessment=assessment,
                expected_review_sha256=records["review"]["evidence_sha256"],
            )
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise PhysicalCameraSessionError(chain_error) from error

    def matches(event, state, code, refs, *, stage=STAGE_ORDER[1]):
        _require(
            event.stage is stage
            and event.state is state
            and event.detail_code == code
            and [ref.to_dict() for ref in event.evidence]
            == sorted(refs, key=lambda ref: ref["evidence_id"]),
            state_error,
        )

    contract_suffix = contract_id.removeprefix("staticcontract-").upper()
    state = "INCOMPLETE" if assessment is None else "ASSESSMENT_RETAINED_NOT_COMMITTED"
    camera_request = None
    if not suffix:
        _require(review is None, state_error)
        _require(snapshot.stages[1].state is V2StageState.WAITING_OPERATOR, state_error)
    else:
        _require(assessment is not None, chain_error)
        subjects = [records[role]["reference"] for role in ("receipt", "assessment")]
        matches(
            suffix[0],
            V2StageState.REVIEW_PENDING,
            "STATIC_CAMERA_CONTRACT_COLLECTED_" + contract_suffix,
            subjects,
        )
        state = "REVIEW_PENDING" if review is None else "REVIEW_RETAINED_NOT_COMMITTED"
        if len(suffix) >= 2:
            _require(review is not None, chain_error)
            assert review is not None
            verdict = review.to_dict()["verdict"]
            _require(verdict in {"PASS", "BLOCKED"}, chain_error)
            matches(
                suffix[1],
                V2StageState(verdict),
                "STATIC_CAMERA_CONTRACT_REVIEWED_" + verdict + "_" + contract_suffix,
                subjects + [records["review"]["reference"]],
            )
            state = "REVIEWED_" + verdict
        _require(
            snapshot.stages[1].state is suffix[min(1, len(suffix) - 1)].state,
            state_error,
        )
        if len(suffix) == 3:
            _require(state == "REVIEWED_PASS", state_error)
            matches(
                suffix[2],
                V2StageState.WAITING_OPERATOR,
                "CAMERA_RECEIPT_REQUESTED_" + contract_suffix,
                [],
                stage=STAGE_ORDER[2],
            )
            camera_request = suffix[2]
    if prefix_event_count is None:
        _require(
            snapshot.stages[2].state
            is (
                V2StageState.WAITING_OPERATOR
                if camera_request
                else V2StageState.PENDING
            )
            and not snapshot.stages[2].evidence_ids
            and all(
                item.state is V2StageState.PENDING and not item.evidence_ids
                for item in snapshot.stages[3:]
            ),
            state_error,
        )
    else:
        _require(camera_request is not None and state == "REVIEWED_PASS", state_error)
    return {
        **original,
        "schema": SOURCE_WORKFLOW_STATIC_SCHEMA,
        "static_contract": {
            "contract_id": contract_id,
            "state": state,
            **{role: records.get(role) for role in ("receipt", "assessment", "review")},
        },
        "camera_receipt_request": (
            None if camera_request is None else camera_request.to_dict()
        ),
    }
