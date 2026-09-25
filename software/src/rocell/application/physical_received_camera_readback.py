"""Closed original stage-3 journal and package verification; no replay or I/O.

The session reads every original under its exact leases before calling this
verifier. A pure completeness result is never substituted for a committed,
distinct review, and stage-4 entry remains a separate explicit journal event.
"""

from __future__ import annotations

import re
from typing import Any

from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState
from .physical_static_contract_readback import (
    CAMERA_RECEIPT_EVENT,
    _verify_static_contract_prefix,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest

RECEIVED_CAMERA_EVENT = re.compile(
    r"CAMERA_RECEIPT_COLLECTION_(STARTED|SUBMITTED|REVIEWED_PASS|REVIEWED_BLOCKED)_([0-9A-F]{32})"
)
CAMERA_IDENTITY_EVENT = re.compile(r"CAMERA_IDENTITY_REQUESTED_([0-9A-F]{32})")


def verify_received_camera_workflow(
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
) -> dict[str, Any]:
    return _verify_received_camera_prefix(
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
        prefix_event_count=None,
    )


def _verify_received_camera_prefix(
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
    *,
    prefix_event_count: int | None,
    usb_identity_extension: bool = False,
    usb_trial_extension: bool = False,
    usb_phase_extension: bool = False,
    usb_absence_extension: bool = False,
    usb_reconnect_extension: bool = False,
    usb_reboot_extension: bool = False,
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
) -> dict[str, Any]:
    """Verify the real full audit through its original identity-entry prefix.

    The sole v7 caller authenticates every additional stage-4 role/event. The
    public v6 path keeps its exact terminal-stage and inventory restrictions.
    """
    from .physical_camera_session import (
        PhysicalCameraSessionError,
        SOURCE_WORKFLOW_RECEIVED_SCHEMA,
        MAX_RECEIVED_CAMERA_CYCLES,
        MAX_RECEIVED_MEDIA_BYTES,
        RECEIVED_ROLE_BYTES,
        _require,
    )
    from .physical_camera_prerequisites import verify_physical_camera_prerequisites
    from .physical_intake_notebook import PhysicalIntakeNotebook
    from .physical_intake_inbox import _media
    from .physical_received_camera_submission import (
        ReceivedCameraSubmission,
        verify_received_camera_submission,
        verify_received_camera_submission_assessment,
        verify_received_camera_submission_review,
    )
    from .wizard_diagnostic_coordinator import WizardError

    state_error = "CAMERA_SESSION_RECEIVED_CAMERA_STATE"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, state_error)
    chain_error = "CAMERA_SESSION_RECEIVED_CAMERA_CHAIN"
    role_error = "CAMERA_SESSION_RECEIVED_CAMERA_ROLE"
    _require(type(snapshot) is V2SessionSnapshot, chain_error)
    entries = [
        (i, event)
        for i, event in enumerate(snapshot.committed_events)
        if CAMERA_RECEIPT_EVENT.fullmatch(event.detail_code)
    ]
    _require(len(entries) == 1, state_error)
    entry_index, entry = entries[0]
    original = _verify_static_contract_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        prefix_event_count=entry_index + 1,
        camera_identity_extension=prefix_event_count is not None,
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
        original["static_contract"]["state"] == "REVIEWED_PASS"
        and original["camera_receipt_request"] == entry.to_dict(),
        state_error,
    )
    _require(not usb_identity_extension or prefix_event_count is not None, state_error)
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
            and entry_index + 1 < prefix_event_count <= len(snapshot.committed_events)
            and len(snapshot.committed_events) - prefix_event_count - mode_event_count
            <= (
                (
                    (53 if usb_complete_extension else 50)
                    if usb_reboot_extension
                    else (
                        43
                        if usb_reconnect_extension
                        else (36 if usb_absence_extension else 26)
                    )
                )
                if usb_phase_extension
                else (
                    18
                    if usb_trial_extension
                    else (16 if usb_identity_extension else 11)
                )
            )
            and CAMERA_IDENTITY_EVENT.fullmatch(
                snapshot.committed_events[prefix_event_count - 1].detail_code
            )
            is not None,
            state_error,
        )
    events = snapshot.committed_events[entry_index + 1 : prefix_event_count]
    _require(len(events) <= 12, state_error)
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
    _require(len(inventory) == len(snapshot.evidence), chain_error)
    package_ids = {item["receipt_id"] for item in received_packages.values()}
    starts = {
        "receivedcamera-" + match[2].lower()
        for event in events
        if (match := RECEIVED_CAMERA_EVENT.fullmatch(event.detail_code))
        and match[1] == "STARTED"
    }
    first = package_ids - starts
    _require(len(first) == 1, role_error)
    first_id = next(iter(first))
    _require(
        type(first_id) is str
        and re.fullmatch(r"receivedcamera-[0-9a-f]{32}", first_id) is not None,
        role_error,
    )
    cycles: list[tuple[str, list[Any]]] = [(first_id, [])]
    identity_request = None
    for offset, event in enumerate(events):
        identity = CAMERA_IDENTITY_EVENT.fullmatch(event.detail_code)
        if identity:
            _require(
                offset == len(events) - 1
                and len(cycles[-1][1]) in {2, 3}
                and "receivedcamera-" + identity[1].lower() == cycles[-1][0],
                state_error,
            )
            identity_request = event
            continue
        match = RECEIVED_CAMERA_EVENT.fullmatch(event.detail_code)
        _require(match is not None, state_error)
        assert match is not None
        phase, suffix = match.groups()
        receipt_id = "receivedcamera-" + suffix.lower()
        if phase == "STARTED":
            _require(
                receipt_id not in {row[0] for row in cycles}
                and bool(cycles[-1][1])
                and cycles[-1][1][-1].detail_code.startswith(
                    "CAMERA_RECEIPT_COLLECTION_REVIEWED_BLOCKED_"
                ),
                state_error,
            )
            cycles.append((receipt_id, [event]))
        else:
            _require(receipt_id == cycles[-1][0], state_error)
            prior = cycles[-1][1]
            expected_count = 0 if len(cycles) == 1 else 1
            _require(
                (phase == "SUBMITTED" and len(prior) == expected_count)
                or (
                    phase in {"REVIEWED_PASS", "REVIEWED_BLOCKED"}
                    and len(prior) == expected_count + 1
                    and prior[-1].detail_code.startswith(
                        "CAMERA_RECEIPT_COLLECTION_SUBMITTED_"
                    )
                ),
                state_error,
            )
            prior.append(event)
    _require(
        1 <= len(cycles) <= MAX_RECEIVED_CAMERA_CYCLES
        and package_ids <= {row[0] for row in cycles},
        role_error,
    )
    originals = {
        key: item
        for key, item in received_packages.items()
        if item["kind"] == "original"
    }
    _require(set(originals) == set(received_originals), chain_error)
    all_received_refs = {
        ref.evidence_id for ref in snapshot.evidence if ref.stage is STAGE_ORDER[2]
    }
    _require(set(received_packages) == all_received_refs, role_error)
    for key, package in received_packages.items():
        ref = package["record"]["reference"]
        _require(
            key == ref["evidence_id"]
            and ref["stage"] == STAGE_ORDER[2].value
            and inventory.get(key) == ref,
            role_error,
        )

    def matches(event, state, code, refs, *, stage=STAGE_ORDER[2]):
        _require(
            event.stage is stage
            and event.state is state
            and event.detail_code == code
            and [ref.to_dict() for ref in event.evidence]
            == sorted(refs, key=lambda ref: ref["evidence_id"]),
            state_error,
        )

    prerequisites = verify_physical_camera_prerequisites(
        canonical(roles["prerequisites"]["document"]),
        expected_source_sha256=bound["source_sha256"],
        expected_session_id=bound["session_id"],
        expected_launch_session_id=bound["launch_id"],
        expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
    )
    verified = []
    predecessor = None
    previous_records = None
    for sequence, (receipt_id, cycle_events) in enumerate(cycles, 1):
        suffix = receipt_id[15:].upper()
        records: dict[str, dict[str, Any]] = {}
        media: list[dict[str, Any]] = []
        for package in received_packages.values():
            if package["receipt_id"] != receipt_id:
                continue
            kind, record = package["kind"], package["record"]
            _require(kind in {*RECEIVED_ROLE_BYTES, "original"}, role_error)
            if kind == "original":
                media.append(record)
            else:
                _require(kind not in records, role_error)
                records[kind] = record
        media.sort(key=lambda row: row["index"])
        _require(
            [row["index"] for row in media] == list(range(len(media)))
            and len(media) <= 16
            and sum(row["reference"]["payload_bytes"] for row in media)
            <= MAX_RECEIVED_MEDIA_BYTES,
            role_error,
        )
        order = tuple(RECEIVED_ROLE_BYTES)
        present = tuple(role for role in order if role in records)
        _require(
            present == order[: len(present)]
            and (not media or "notebook" in records)
            and (sequence != 1 or "notebook" in records),
            chain_error,
        )
        if sequence > 1:
            _require(
                predecessor is not None and previous_records is not None, chain_error
            )
            assert previous_records is not None
            matches(
                cycle_events[0],
                V2StageState.WAITING_OPERATOR,
                "CAMERA_RECEIPT_COLLECTION_STARTED_" + suffix,
                [
                    previous_records[role]["reference"]
                    for role in ("submission", "assessment", "review")
                ],
            )
            body = cycle_events[1:]
        else:
            body = cycle_events
        notebook = submission = assessment = review = None
        try:
            for record in media:
                ref = record["reference"]
                raw = received_originals[ref["evidence_id"]]
                _require(
                    type(raw) is bytes
                    and 0 < len(raw) <= 2 * 1024 * 1024
                    and len(raw) == ref["payload_bytes"]
                    and digest(raw) == ref["payload_sha256"],
                    chain_error,
                )
                extension = {
                    "text/plain": ".txt",
                    "application/json": ".json",
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "application/pdf": ".pdf",
                }[record["media_type"]]
                _require(
                    _media("original" + extension, raw) == record["media_type"],
                    chain_error,
                )
            if "notebook" in records:
                record = records["notebook"]
                notebook = PhysicalIntakeNotebook.from_payload(
                    canonical(record["document"]),
                    prerequisites=prerequisites,
                    expected_sha256=record["evidence_sha256"],
                )
            if "submission" in records:
                record = records["submission"]
                wire = canonical(record["document"])
                supplied = ReceivedCameraSubmission(wire, prerequisites).to_dict()[
                    "binding"
                ]
                expected_binding = {
                    "receipt_id": receipt_id,
                    "source_sha256": bound["source_sha256"],
                    "cell_id": bound["cell_id"],
                    "session_id": bound["session_id"],
                    "header_sha256": expected_header_sha256,
                    "origin_launch_id": bound["launch_id"],
                    "collection_launch_id": supplied["collection_launch_id"],
                    "operator_id": supplied["operator_id"],
                    "prerequisites_sha256": prerequisites.evidence_sha256,
                    "static_contract": {
                        role: original["static_contract"][role]["evidence_sha256"]
                        for role in ("receipt", "assessment", "review")
                    },
                    "camera_request_event_sha256": entry.event_sha256,
                }
                submission = verify_received_camera_submission(
                    wire,
                    prerequisites=prerequisites,
                    expected_binding=expected_binding,
                    evidence_inventory=snapshot.evidence,
                    expected_submission_sha256=record["evidence_sha256"],
                    predecessor=predecessor,
                )
                document = submission.to_dict()
                _require(
                    notebook is not None
                    and document["sequence"] == sequence
                    and document["notebook"] == notebook.to_dict()
                    and document["notebook_sha256"] == notebook.sha256
                    and document["notebook_reference"]
                    == records["notebook"]["reference"],
                    chain_error,
                )
                selected = {
                    row["reference"]["evidence_id"]: row
                    for row in document["attachments"]
                }
                _require(
                    set(selected) == {row["reference"]["evidence_id"] for row in media},
                    chain_error,
                )
                for row in media:
                    chosen = selected[row["reference"]["evidence_id"]]
                    _require(
                        chosen["reference"] == row["reference"]
                        and chosen["media_type"] == row["media_type"]
                        and _media(
                            chosen["basename"],
                            received_originals[row["reference"]["evidence_id"]],
                        )
                        == row["media_type"],
                        chain_error,
                    )
            if "assessment" in records:
                assert submission is not None
                assessment = verify_received_camera_submission_assessment(
                    canonical(records["assessment"]["document"]),
                    submission=submission,
                    expected_assessment_sha256=records["assessment"]["evidence_sha256"],
                )
            if "review" in records:
                assert submission is not None and assessment is not None
                review = verify_received_camera_submission_review(
                    canonical(records["review"]["document"]),
                    submission=submission,
                    assessment=assessment,
                    expected_review_sha256=records["review"]["evidence_sha256"],
                )
        except (ValueError, TypeError, KeyError, AttributeError, WizardError) as error:
            raise PhysicalCameraSessionError(chain_error) from error
        state = (
            "INCOMPLETE" if assessment is None else "ASSESSMENT_RETAINED_NOT_COMMITTED"
        )
        _require(len(body) <= 2, state_error)
        if not body:
            _require(review is None, state_error)
        else:
            _require(assessment is not None, chain_error)
            subjects = [
                records[role]["reference"]
                for role in ("notebook", "submission", "assessment")
            ]
            subjects.extend(row["reference"] for row in media)
            matches(
                body[0],
                V2StageState.REVIEW_PENDING,
                "CAMERA_RECEIPT_COLLECTION_SUBMITTED_" + suffix,
                subjects,
            )
            state = (
                "REVIEW_PENDING" if review is None else "REVIEW_RETAINED_NOT_COMMITTED"
            )
            if len(body) == 2:
                _require(review is not None, chain_error)
                assert review is not None
                verdict = review.to_dict()["verdict"]
                _require(verdict in {"PASS", "BLOCKED"}, chain_error)
                matches(
                    body[1],
                    V2StageState(verdict),
                    "CAMERA_RECEIPT_COLLECTION_REVIEWED_" + verdict + "_" + suffix,
                    [*subjects, records["review"]["reference"]],
                )
                state = "REVIEWED_" + verdict
        if sequence < len(cycles):
            _require(state == "REVIEWED_BLOCKED", state_error)
        verified.append(
            {
                "receipt_id": receipt_id,
                "sequence": sequence,
                "state": state,
                "originals": media,
                **{role: records.get(role) for role in order},
            }
        )
        previous_records = records
        predecessor = None if review is None else (submission, assessment, review)
    final_events = cycles[-1][1]
    expected_state = (
        final_events[-1].state if final_events else V2StageState.WAITING_OPERATOR
    )
    _require(snapshot.stages[2].state is expected_state, state_error)
    if identity_request is not None:
        _require(verified[-1]["state"] == "REVIEWED_PASS", state_error)
        matches(
            identity_request,
            V2StageState.WAITING_OPERATOR,
            "CAMERA_IDENTITY_REQUESTED_" + cycles[-1][0][15:].upper(),
            [],
            stage=STAGE_ORDER[3],
        )
    if prefix_event_count is None:
        _require(
            snapshot.stages[3].state
            is (
                V2StageState.WAITING_OPERATOR
                if identity_request
                else V2StageState.PENDING
            )
            and not snapshot.stages[3].evidence_ids
            and all(
                row.state is V2StageState.PENDING and not row.evidence_ids
                for row in snapshot.stages[4 if camera_mode_entry is None else 5 :]
            ),
            state_error,
        )
    else:
        _require(
            identity_request is not None and verified[-1]["state"] == "REVIEWED_PASS",
            state_error,
        )
    return {
        **original,
        "schema": SOURCE_WORKFLOW_RECEIVED_SCHEMA,
        "received_camera_cycles": verified,
        "camera_identity_request": (
            None if identity_request is None else identity_request.to_dict()
        ),
    }
