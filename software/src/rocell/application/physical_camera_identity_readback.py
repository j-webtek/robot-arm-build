"""Closed original stage-4 metadata history; no enumeration, replay or release.

The camera session supplies original bytes read under its real leases. This
pure reader verifies full prior stage history and every exact metadata subject,
but never treats a metadata acknowledgement as complete identity qualification.
"""

from __future__ import annotations

import re
from typing import Any

from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState
from .physical_received_camera_readback import (
    CAMERA_IDENTITY_EVENT,
    _verify_received_camera_prefix,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest

CAMERA_IDENTITY_METADATA_EVENT = re.compile(
    r"CAMERA_IDENTITY_METADATA_(STARTED|COLLECTED|REVIEWED_BLOCKED)_([0-9A-F]{32})"
)


def verify_camera_identity_workflow(
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
) -> dict[str, Any]:
    return _verify_camera_identity_prefix(
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
        prefix_event_count=None,
        usb_evidence_ids=frozenset(),
    )


def _verify_camera_identity_prefix(
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
    *,
    prefix_event_count: int | None,
    usb_evidence_ids: frozenset[str],
    trial_evidence_ids: frozenset[str] = frozenset(),
    usb_trial_extension: bool = False,
    usb_phase_evidence_ids: frozenset[str] = frozenset(),
    usb_phase_extension: bool = False,
    usb_absence_evidence_ids: frozenset[str] = frozenset(),
    usb_absence_extension: bool = False,
    usb_reconnect_extension: bool = False,
    usb_reboot_extension: bool = False,
    usb_reboot_evidence_ids: frozenset[str] = frozenset(),
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
    usb_complete_evidence_ids: frozenset[str] = frozenset(),
    usb_reconnect_evidence_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    from .physical_camera_session import (
        PhysicalCameraSessionError,
        SOURCE_WORKFLOW_IDENTITY_SCHEMA,
        MAX_CAMERA_IDENTITY_CYCLES,
        IDENTITY_ROLE_BYTES,
        _require,
    )
    from .physical_camera_prerequisites import verify_physical_camera_prerequisites
    from .physical_received_camera_submission import ReceivedCameraSubmission
    from .physical_camera_identity_submission import (
        verify_camera_identity_metadata,
        verify_camera_identity_helper,
        verify_camera_identity_receipt,
        verify_camera_identity_assessment,
        verify_camera_identity_review,
    )

    state_error = "CAMERA_SESSION_CAMERA_IDENTITY_STATE"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, state_error)
    chain_error = "CAMERA_SESSION_CAMERA_IDENTITY_CHAIN"
    role_error = "CAMERA_SESSION_CAMERA_IDENTITY_ROLE"
    _require(type(snapshot) is V2SessionSnapshot, chain_error)
    _require(
        type(usb_trial_extension) is bool
        and type(trial_evidence_ids) is frozenset
        and len(trial_evidence_ids) <= 1
        and (usb_trial_extension or not trial_evidence_ids)
        and (not usb_trial_extension or prefix_event_count is not None)
        and trial_evidence_ids.isdisjoint(usb_evidence_ids),
        chain_error,
    )
    _require(
        type(usb_phase_extension) is bool
        and type(usb_phase_evidence_ids) is frozenset
        and len(usb_phase_evidence_ids) <= 9
        and (usb_phase_extension or not usb_phase_evidence_ids)
        and (not usb_phase_extension or usb_trial_extension)
        and usb_phase_evidence_ids.isdisjoint(usb_evidence_ids | trial_evidence_ids),
        chain_error,
    )
    _require(
        type(usb_evidence_ids) is frozenset
        and len(usb_evidence_ids) <= 6
        and (prefix_event_count is not None or not usb_evidence_ids),
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
            | usb_evidence_ids
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
        and usb_absence_evidence_ids.isdisjoint(
            usb_evidence_ids | trial_evidence_ids | usb_phase_evidence_ids
        ),
        chain_error,
    )
    _require(
        type(usb_reconnect_evidence_ids) is frozenset
        and len(usb_reconnect_evidence_ids) <= 11
        and (usb_reconnect_extension or not usb_reconnect_evidence_ids)
        and usb_reconnect_evidence_ids.isdisjoint(
            usb_absence_evidence_ids
            | usb_phase_evidence_ids
            | trial_evidence_ids
            | usb_evidence_ids
        ),
        chain_error,
    )
    if prefix_event_count is not None:
        _require(
            type(prefix_event_count) is int
            and 0 < prefix_event_count < len(snapshot.committed_events)
            and len(snapshot.committed_events) - prefix_event_count - mode_event_count
            <= (
                (
                    (42 if usb_complete_extension else 39)
                    if usb_reboot_extension
                    else (32 if usb_reconnect_extension else 25)
                )
                if usb_absence_extension
                else (15 if usb_phase_extension else (7 if usb_trial_extension else 5))
            ),
            state_error,
        )
    entries = [
        (index, event)
        for index, event in enumerate(snapshot.committed_events)
        if CAMERA_IDENTITY_EVENT.fullmatch(event.detail_code)
    ]
    _require(len(entries) == 1, state_error)
    entry_index, entry = entries[0]
    original = _verify_received_camera_prefix(
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
        prefix_event_count=entry_index + 1,
        usb_identity_extension=prefix_event_count is not None,
        usb_trial_extension=usb_trial_extension,
        usb_phase_extension=usb_phase_extension,
        usb_absence_extension=usb_absence_extension,
        usb_reconnect_extension=usb_reconnect_extension,
        usb_reboot_extension=usb_reboot_extension,
        usb_complete_extension=usb_complete_extension,
        camera_mode_entry=camera_mode_entry,
    )
    _require(
        original["received_camera_cycles"][-1]["state"] == "REVIEWED_PASS"
        and original["camera_identity_request"] == entry.to_dict(),
        state_error,
    )
    events = snapshot.committed_events[entry_index + 1 : prefix_event_count]
    _require(len(events) <= 11, state_error)
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
    package_ids = {row["identity_id"] for row in identity_packages.values()}
    starts = {
        "cameraidentity-" + match[2].lower()
        for event in events
        if (match := CAMERA_IDENTITY_METADATA_EVENT.fullmatch(event.detail_code))
        and match[1] == "STARTED"
    }
    first = package_ids - starts
    _require(len(first) == 1, role_error)
    first_id = next(iter(first))
    _require(
        type(first_id) is str
        and re.fullmatch(r"cameraidentity-[0-9a-f]{32}", first_id) is not None,
        role_error,
    )
    cycles: list[tuple[str, list[Any]]] = [(first_id, [])]
    for event in events:
        match = CAMERA_IDENTITY_METADATA_EVENT.fullmatch(event.detail_code)
        _require(match is not None, state_error)
        assert match is not None
        phase, suffix = match.groups()
        identity_id = "cameraidentity-" + suffix.lower()
        if phase == "STARTED":
            _require(
                identity_id not in {row[0] for row in cycles}
                and bool(cycles[-1][1])
                and cycles[-1][1][-1].detail_code.startswith(
                    "CAMERA_IDENTITY_METADATA_REVIEWED_BLOCKED_"
                ),
                state_error,
            )
            cycles.append((identity_id, [event]))
        else:
            _require(identity_id == cycles[-1][0], state_error)
            prior = cycles[-1][1]
            offset = 0 if len(cycles) == 1 else 1
            _require(
                (phase == "COLLECTED" and len(prior) == offset)
                or (
                    phase == "REVIEWED_BLOCKED"
                    and len(prior) == offset + 1
                    and prior[-1].detail_code.startswith(
                        "CAMERA_IDENTITY_METADATA_COLLECTED_"
                    )
                ),
                state_error,
            )
            prior.append(event)
    _require(
        1 <= len(cycles) <= MAX_CAMERA_IDENTITY_CYCLES
        and package_ids <= {row[0] for row in cycles},
        role_error,
    )
    _require(
        set(identity_packages)
        == {
            ref.evidence_id
            for ref in snapshot.evidence
            if ref.stage is STAGE_ORDER[3]
            and ref.evidence_id
            not in usb_evidence_ids
            | trial_evidence_ids
            | usb_phase_evidence_ids
            | usb_absence_evidence_ids
            | usb_reconnect_evidence_ids
            | usb_reboot_evidence_ids
            | usb_complete_evidence_ids
            | mode_evidence_ids
        },
        role_error,
    )
    for key, package in identity_packages.items():
        record = package["record"]
        ref = record["reference"]
        _require(
            set(package) == {"kind", "identity_id", "record"}
            and set(record) == {"document", "evidence_sha256", "retention", "reference"}
            and key == ref["evidence_id"]
            and inventory.get(key) == ref
            and ref["stage"] == STAGE_ORDER[3].value
            and record["retention"] == "M1_FULL_BYTES_READ_BACK"
            and package["kind"] in IDENTITY_ROLE_BYTES,
            role_error,
        )
        wire = canonical(record["document"])
        _require(
            len(wire) == ref["payload_bytes"]
            and 0 < len(wire) <= IDENTITY_ROLE_BYTES[package["kind"]]
            and digest(wire) == ref["payload_sha256"] == record["evidence_sha256"],
            chain_error,
        )

    def matches(event, state, code, refs):
        _require(
            event.stage is STAGE_ORDER[3]
            and event.state is state
            and event.detail_code == code
            and [ref.to_dict() for ref in event.evidence]
            == sorted(refs, key=lambda row: row["evidence_id"]),
            state_error,
        )

    prerequisites = verify_physical_camera_prerequisites(
        canonical(roles["prerequisites"]["document"]),
        expected_source_sha256=bound["source_sha256"],
        expected_session_id=bound["session_id"],
        expected_launch_session_id=bound["launch_id"],
        expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
    )
    received = original["received_camera_cycles"][-1]
    received_submission = ReceivedCameraSubmission(
        canonical(received["submission"]["document"]), prerequisites
    )
    verified = []
    predecessor = previous_records = None
    order = tuple(IDENTITY_ROLE_BYTES)
    for sequence, (identity_id, cycle_events) in enumerate(cycles, 1):
        records: dict[str, dict[str, Any]] = {}
        for package in identity_packages.values():
            if package["identity_id"] == identity_id:
                kind = package["kind"]
                _require(kind not in records, role_error)
                records[kind] = package["record"]
        present = tuple(role for role in order if role in records)
        _require(
            present == order[: len(present)]
            and (sequence != 1 or "metadata" in records),
            chain_error,
        )
        suffix = identity_id[15:].upper()
        if sequence > 1:
            _require(
                predecessor is not None and previous_records is not None, chain_error
            )
            assert previous_records is not None
            matches(
                cycle_events[0],
                V2StageState.WAITING_OPERATOR,
                "CAMERA_IDENTITY_METADATA_STARTED_" + suffix,
                [previous_records[role]["reference"] for role in order],
            )
            body = cycle_events[1:]
        else:
            body = cycle_events
        metadata = helper = receipt = assessment = review = None
        try:
            if "metadata" in records:
                record = records["metadata"]
                metadata = verify_camera_identity_metadata(
                    canonical(record["document"]),
                    expected_sha256=record["evidence_sha256"],
                )
                supplied = metadata.to_dict()["binding"]
                expected_binding = {
                    "identity_id": identity_id,
                    "source_sha256": bound["source_sha256"],
                    "cell_id": bound["cell_id"],
                    "session_id": bound["session_id"],
                    "header_sha256": expected_header_sha256,
                    "origin_launch_id": bound["launch_id"],
                    "collection_launch_id": supplied["collection_launch_id"],
                    "operator_id": supplied["operator_id"],
                    "prerequisites_sha256": prerequisites.evidence_sha256,
                    "received_camera": {
                        role: received[role]["evidence_sha256"]
                        for role in ("submission", "assessment", "review")
                    },
                    "identity_request_event_sha256": entry.event_sha256,
                }
                _require(
                    supplied == expected_binding
                    and metadata.to_dict()["sequence"] == sequence,
                    chain_error,
                )
            if "helper" in records:
                helper = verify_camera_identity_helper(
                    canonical(records["helper"]["document"]),
                    expected_binding=expected_binding,
                    expected_sha256=records["helper"]["evidence_sha256"],
                )
                _require(helper.to_dict()["sequence"] == sequence, chain_error)
                assert metadata is not None
                _require(
                    metadata.to_dict()["enrollment"]["view"]["provenance"][
                        "helper_sha256"
                    ]
                    == helper.to_dict()["helper_report"]["registration_artifact"][
                        "payload"
                    ]["helper_sha256"],
                    chain_error,
                )
            if "receipt" in records:
                receipt = verify_camera_identity_receipt(
                    canonical(records["receipt"]["document"]),
                    prerequisites=prerequisites,
                    metadata=metadata,
                    helper=helper,
                    received_submission=received_submission,
                    predecessor=predecessor,
                    expected_sha256=records["receipt"]["evidence_sha256"],
                )
                document = receipt.to_dict()
                _require(
                    document["binding"] == expected_binding
                    and document["sequence"] == sequence,
                    chain_error,
                )
                for role in ("metadata", "helper"):
                    _require(
                        document[role + "_reference"] == records[role]["reference"]
                        and document[role + "_sha256"]
                        == records[role]["evidence_sha256"],
                        chain_error,
                    )
            if "assessment" in records:
                assessment = verify_camera_identity_assessment(
                    canonical(records["assessment"]["document"]),
                    receipt=receipt,
                    metadata=metadata,
                    helper=helper,
                    received_submission=received_submission,
                    expected_sha256=records["assessment"]["evidence_sha256"],
                )
                _require(
                    assessment.to_dict()["binding"] == expected_binding
                    and assessment.to_dict()["verdict"] == "BLOCKED",
                    chain_error,
                )
            if "review" in records:
                review = verify_camera_identity_review(
                    canonical(records["review"]["document"]),
                    receipt=receipt,
                    assessment=assessment,
                    expected_sha256=records["review"]["evidence_sha256"],
                )
                _require(
                    review.to_dict()["binding"] == expected_binding
                    and review.to_dict()["verdict"] == "BLOCKED",
                    chain_error,
                )
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise PhysicalCameraSessionError(chain_error) from error
        state = (
            "INCOMPLETE" if assessment is None else "ASSESSMENT_RETAINED_NOT_COMMITTED"
        )
        _require(len(body) <= 2, state_error)
        if not body:
            _require(review is None, state_error)
        else:
            _require(assessment is not None, chain_error)
            refs = [records[role]["reference"] for role in order[:-1]]
            matches(
                body[0],
                V2StageState.REVIEW_PENDING,
                "CAMERA_IDENTITY_METADATA_COLLECTED_" + suffix,
                refs,
            )
            state = (
                "REVIEW_PENDING" if review is None else "REVIEW_RETAINED_NOT_COMMITTED"
            )
            if len(body) == 2:
                _require(review is not None, chain_error)
                matches(
                    body[1],
                    V2StageState.BLOCKED,
                    "CAMERA_IDENTITY_METADATA_REVIEWED_BLOCKED_" + suffix,
                    [*refs, records["review"]["reference"]],
                )
                state = "REVIEWED_BLOCKED"
        if sequence < len(cycles):
            _require(state == "REVIEWED_BLOCKED", state_error)
        verified.append(
            {
                "identity_id": identity_id,
                "sequence": sequence,
                "state": state,
                **{role: records.get(role) for role in order},
            }
        )
        predecessor = None if review is None else (receipt, assessment, review)
        previous_records = records
    final_events = cycles[-1][1]
    _require(
        (
            prefix_event_count is not None
            or snapshot.stages[3].state
            is (
                final_events[-1].state
                if final_events
                else V2StageState.WAITING_OPERATOR
            )
        )
        and all(
            row.state is V2StageState.PENDING and not row.evidence_ids
            for row in snapshot.stages[4 if camera_mode_entry is None else 5 :]
        ),
        state_error,
    )
    return {
        **original,
        "schema": SOURCE_WORKFLOW_IDENTITY_SCHEMA,
        "camera_identity_cycles": verified,
    }
