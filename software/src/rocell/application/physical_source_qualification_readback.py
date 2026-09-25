"""Closed original-journal successor grammar; no collection, mutation or replay.

Called only after the camera session reader verifies all original packages and
the immutable source-v1 subjects. A source qualification never changes those
historical verdicts or supplies a camera/arm runtime release credential.
"""

from __future__ import annotations

import re
from typing import Any

from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_durability import canonical_sha256
from .physical_onboarding_v2 import (
    V2CommittedHead,
    V2SessionSnapshot,
    V2StageState,
    _apply_transition,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest


MAX_QUALIFICATION_CYCLES = 8
QUALIFICATION_EVENT = re.compile(
    r"WORKSPACE_SOURCE_QUALIFICATION_(STARTED|ASSESSED|REVIEWED_PASS|"
    r"REVIEWED_BLOCKED)_([0-9A-F]{32})"
)
STATIC_CAMERA_EVENT = re.compile(r"STATIC_CAMERA_CONTRACT_REQUESTED_([0-9A-F]{32})")


def verify_qualification_workflow(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    intake_packages: dict[str, dict[str, Any]],
    qualification_packages: dict[str, dict[str, Any]],
    qualification_originals: dict[str, bytes],
) -> dict[str, Any]:
    """Verify the exact v4 terminal grammar, including all later-stage holds."""
    return _verify_qualification_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        prefix_event_count=None,
    )


def _verify_qualification_prefix(
    bound: dict[str, Any],
    snapshot: V2SessionSnapshot,
    expected_header_sha256: str,
    roles: dict[str, dict[str, Any]],
    intake_packages: dict[str, dict[str, Any]],
    qualification_packages: dict[str, dict[str, Any]],
    qualification_originals: dict[str, bytes],
    *,
    prefix_event_count: int | None,
    received_camera_extension: bool = False,
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
    """Verify original v4 subjects against the real complete audited snapshot.

    Inputs are server-owned records read under the original stage-only leases;
    this function accepts no parser, success callback or replacement inventory.
    The v5 caller may select only the committed prefix ending at the explicit
    stage-2 entry; it separately verifies the closed at-most-three-event suffix.
    Full-head, transition, inventory and stage-snapshot validation still uses
    every real event. No earlier store, head or stage snapshot is manufactured.
    """
    from .physical_camera_session import (
        PhysicalCameraSessionError,
        SOURCE_WORKFLOW_QUALIFICATION_SCHEMA,
        _require,
        _verify_intake_collections,
    )
    from .physical_camera_prerequisites import verify_physical_camera_prerequisites
    from .physical_intake_inbox import _media
    from .physical_source_stage_evidence import verify_workspace_source_receipt
    from .physical_source_qualification import (
        SourceQualificationReceipt,
        verify_source_qualification_assessment,
        verify_source_qualification_review,
    )

    state_error = "CAMERA_SESSION_SOURCE_QUALIFICATION_STATE"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, state_error)
    chain_error = "CAMERA_SESSION_SOURCE_QUALIFICATION_CHAIN"
    role_error = "CAMERA_SESSION_SOURCE_QUALIFICATION_ROLE"
    _require(
        type(snapshot) is V2SessionSnapshot
        and not snapshot.uncommitted_events
        and snapshot.header.header_sha256 == expected_header_sha256
        and tuple(item.stage for item in snapshot.stages) == STAGE_ORDER
        and all(
            role in roles
            for role in ("prerequisites", "receipt", "assessment", "review")
        ),
        chain_error,
    )
    complete_events = snapshot.committed_events
    maximum = 3 + 24 + 3 * MAX_QUALIFICATION_CYCLES + 1
    suffix_limit = (
        (41 if usb_phase_extension else (33 if usb_trial_extension else 31))
        if usb_identity_extension
        else (
            26
            if camera_identity_extension
            else (15 if received_camera_extension else 3)
        )
    )
    if usb_absence_extension:
        suffix_limit += 10
    if usb_reconnect_extension:
        suffix_limit += 7
    if usb_reboot_extension:
        suffix_limit += 7
    if usb_complete_extension:
        suffix_limit += 3
    suffix_limit += mode_event_count
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
    _require(not camera_identity_extension or received_camera_extension, state_error)
    _require(not usb_identity_extension or camera_identity_extension, state_error)
    _require(not usb_trial_extension or usb_identity_extension, state_error)
    _require(not usb_phase_extension or usb_trial_extension, state_error)
    _require(
        not received_camera_extension or prefix_event_count is not None, state_error
    )
    _require(
        4
        <= len(complete_events)
        <= maximum + (suffix_limit if prefix_event_count else 0),
        state_error,
    )
    if prefix_event_count is not None:
        _require(
            type(prefix_event_count) is int
            and 4 <= prefix_event_count <= len(complete_events)
            and len(complete_events) - prefix_event_count <= suffix_limit,
            state_error,
        )
    events = (
        complete_events
        if prefix_event_count is None
        else complete_events[:prefix_event_count]
    )
    _require(len(events) <= maximum, state_error)
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
    _require(len(inventory) == len(snapshot.evidence), chain_error)
    _require(
        V2CommittedHead.build(snapshot.header, complete_events) == snapshot.head,
        state_error,
    )
    derived = [V2StageState.PENDING for _ in STAGE_ORDER]
    cited: list[list[str]] = [[] for _ in STAGE_ORDER]
    latest: list[int | None] = [None for _ in STAGE_ORDER]
    try:
        for event in complete_events:
            _apply_transition(derived, event)
            index = STAGE_ORDER.index(event.stage)
            cited[index].extend(ref.evidence_id for ref in event.evidence)
            latest[index] = event.sequence
        _require(
            all(
                item.state is derived[index]
                and item.evidence_ids == tuple(cited[index])
                and item.last_event_sequence == latest[index]
                for index, item in enumerate(snapshot.stages)
            ),
            state_error,
        )
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise PhysicalCameraSessionError(state_error) from error

    def matches(event, state, code, refs, *, stage=STAGE_ORDER[0], ordered=True):
        expected = sorted(refs, key=lambda ref: ref["evidence_id"])
        actual = [ref.to_dict() for ref in event.evidence]
        _require(
            event.stage is stage
            and event.state is state
            and event.detail_code == code
            and len({ref["evidence_id"] for ref in actual}) == len(actual)
            and (
                actual
                if ordered
                else sorted(actual, key=lambda ref: ref["evidence_id"])
            )
            == expected
            and all(inventory.get(ref["evidence_id"]) == ref for ref in actual),
            state_error,
        )

    original_subjects = [
        roles[role]["reference"] for role in ("receipt", "assessment", "review")
    ]
    for event, prefix_state, code, refs in zip(
        events[:3],
        (
            V2StageState.WAITING_OPERATOR,
            V2StageState.REVIEW_PENDING,
            V2StageState.BLOCKED,
        ),
        (
            "CAMERA_PREREQUISITES_REQUESTED",
            "WORKSPACE_SOURCES_ASSESSMENT_SAVED",
            "WORKSPACE_SOURCES_REVIEWED_BLOCKED",
        ),
        ([], original_subjects[:2], original_subjects),
    ):
        matches(event, prefix_state, code, refs, ordered=False)
    first = next(
        (
            index
            for index, event in enumerate(events)
            if QUALIFICATION_EVENT.fullmatch(event.detail_code)
        ),
        None,
    )
    _require(first is not None and first >= 3, state_error)
    assert first is not None
    collections = []
    if first > 3:
        collections = _verify_intake_collections(
            bound,
            snapshot,
            expected_header_sha256,
            roles,
            intake_packages,
            prefix_event_count=first,
        )
        _require(collections[-1]["state"] == "REVIEWED_BLOCKED", state_error)
    else:
        _require(not intake_packages, role_error)
    previous_refs = list(original_subjects)
    if collections:
        previous_refs.extend(
            collections[-1][role]["reference"]
            for role in ("submission", "assessment", "review")
        )

    cycles: list[tuple[str, list[Any]]] = []
    static_event = None
    for index, event in enumerate(events[first:], start=first):
        static = STATIC_CAMERA_EVENT.fullmatch(event.detail_code)
        if static is not None:
            _require(
                index == len(events) - 1 and static_event is None and bool(cycles),
                state_error,
            )
            static_event = event
            continue
        match = QUALIFICATION_EVENT.fullmatch(event.detail_code)
        _require(match is not None and static_event is None, state_error)
        assert match is not None
        phase, suffix = match.groups()
        qualification_id = "sourcequal-" + suffix.lower()
        if phase == "STARTED":
            _require(
                qualification_id not in {item[0] for item in cycles}
                and (
                    not cycles
                    or (
                        len(cycles[-1][1]) == 3
                        and cycles[-1][1][-1].state is V2StageState.BLOCKED
                    )
                ),
                state_error,
            )
            cycles.append((qualification_id, []))
        _require(
            bool(cycles)
            and cycles[-1][0] == qualification_id
            and len(cycles[-1][1]) < 3,
            state_error,
        )
        expected = ("STARTED", "ASSESSED", "REVIEWED")[len(cycles[-1][1])]
        _require(
            phase == expected
            or (
                expected == "REVIEWED"
                and phase in {"REVIEWED_PASS", "REVIEWED_BLOCKED"}
            ),
            state_error,
        )
        cycles[-1][1].append(event)
    _require(1 <= len(cycles) <= MAX_QUALIFICATION_CYCLES, state_error)
    _require(
        all(
            package["qualification_id"] in {item[0] for item in cycles}
            for package in qualification_packages.values()
        ),
        role_error,
    )
    originals = {
        package["record"]["reference"]["evidence_id"]: package["record"]
        for package in qualification_packages.values()
        if package["kind"] == "isolation_original"
    }
    _require(set(qualification_originals) == set(originals), chain_error)
    extensions = {
        "text/plain": ".txt",
        "application/json": ".json",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "application/pdf": ".pdf",
    }
    try:
        for evidence_id, original in originals.items():
            payload = qualification_originals[evidence_id]
            ref = original["reference"]
            _require(
                type(payload) is bytes
                and len(payload) == ref["payload_bytes"]
                and digest(payload) == ref["payload_sha256"]
                and original["evidence_sha256"] == ref["payload_sha256"],
                chain_error,
            )
            _require(
                _media("original" + extensions[original["media_type"]], payload)
                == original["media_type"],
                chain_error,
            )
    except (ValueError, KeyError, TypeError) as error:
        raise PhysicalCameraSessionError(chain_error) from error

    prerequisites = verify_physical_camera_prerequisites(
        canonical(roles["prerequisites"]["document"]),
        expected_source_sha256=bound["source_sha256"],
        expected_session_id=bound["session_id"],
        expected_launch_session_id=bound["launch_id"],
        expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
    )
    predecessor_hashes = None
    verified_cycles = []
    for qualification_id, cycle in cycles:
        suffix = qualification_id.removeprefix("sourcequal-").upper()
        matches(
            cycle[0],
            V2StageState.WAITING_OPERATOR,
            "WORKSPACE_SOURCE_QUALIFICATION_STARTED_" + suffix,
            previous_refs,
        )
        records: dict[str, dict[str, Any]] = {}
        for package in qualification_packages.values():
            if package["qualification_id"] != qualification_id:
                continue
            kind, record = package["kind"], package["record"]
            _require(
                kind in {"isolation_original", "receipt", "assessment", "review"}
                and kind not in records,
                role_error,
            )
            _require(
                inventory.get(record["reference"]["evidence_id"])
                == record["reference"],
                chain_error,
            )
            records[kind] = record
        present = tuple(
            role for role in ("receipt", "assessment", "review") if role in records
        )
        _require(
            present == ("receipt", "assessment", "review")[: len(present)], chain_error
        )
        receipt = assessment = review = None
        try:
            if "receipt" in records:
                receipt = SourceQualificationReceipt(
                    canonical(records["receipt"]["document"])
                )
                _require(
                    receipt.sha256 == records["receipt"]["evidence_sha256"], chain_error
                )
                document = receipt.to_dict()
                binding = document["binding"]
                expected_binding = {
                    "qualification_id": qualification_id,
                    "source_sha256": bound["source_sha256"],
                    "cell_id": bound["cell_id"],
                    "session_id": bound["session_id"],
                    "header_sha256": expected_header_sha256,
                    "origin_launch_id": bound["launch_id"],
                    "store_directory": bound["directory"],
                    "prerequisites_sha256": prerequisites.evidence_sha256,
                    "predecessor_source": {
                        role: roles[role]["evidence_sha256"]
                        for role in ("receipt", "assessment", "review")
                    },
                    "predecessor_qualification": predecessor_hashes,
                }
                _require(
                    all(
                        binding.get(key) == value
                        for key, value in expected_binding.items()
                    )
                    and document["ownership_report"]["binding"]["workspace"]
                    == bound["workspace"],
                    chain_error,
                )
                original = records.get("isolation_original")
                if original is not None:
                    _require(
                        _media(
                            document["isolation"]["basename"],
                            qualification_originals[
                                original["reference"]["evidence_id"]
                            ],
                        )
                        == original["media_type"],
                        chain_error,
                    )
                software = document["software_receipt"]
                software_wire = canonical(software)
                verify_workspace_source_receipt(
                    software_wire,
                    prerequisites=prerequisites,
                    expected_source_sha256=bound["source_sha256"],
                    expected_session_id=bound["session_id"],
                    expected_origin_launch_id=bound["launch_id"],
                    expected_header_sha256=expected_header_sha256,
                    expected_receipt_sha256=digest(software_wire),
                )
                _require(
                    all(
                        software["binding"][key] == binding[key]
                        for key in ("operator_id", "collection_launch_id")
                    ),
                    chain_error,
                )
                _require(
                    document["isolation"]["original_reference"]
                    == (None if original is None else original["reference"]),
                    chain_error,
                )
            if "assessment" in records:
                assert receipt is not None
                assessment = verify_source_qualification_assessment(
                    canonical(records["assessment"]["document"]),
                    receipt=receipt,
                    expected_sha256=records["assessment"]["evidence_sha256"],
                )
            if "review" in records:
                assert receipt is not None and assessment is not None
                review = verify_source_qualification_review(
                    canonical(records["review"]["document"]),
                    receipt=receipt,
                    assessment=assessment,
                    expected_sha256=records["review"]["evidence_sha256"],
                )
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise PhysicalCameraSessionError(chain_error) from error
        state = "INCOMPLETE"
        if assessment is not None:
            state = "ASSESSMENT_RETAINED_NOT_COMMITTED"
        if len(cycle) == 1:
            _require(review is None, state_error)
        else:
            _require(receipt is not None and assessment is not None, chain_error)
            subjects = [
                records[role]["reference"] for role in ("receipt", "assessment")
            ]
            if "isolation_original" in records:
                subjects.append(records["isolation_original"]["reference"])
            matches(
                cycle[1],
                V2StageState.REVIEW_PENDING,
                "WORKSPACE_SOURCE_QUALIFICATION_ASSESSED_" + suffix,
                subjects,
            )
            state = (
                "REVIEW_PENDING" if review is None else "REVIEW_RETAINED_NOT_COMMITTED"
            )
            if len(cycle) == 3:
                _require(review is not None, chain_error)
                assert review is not None
                verdict = review.to_dict()["verdict"]
                _require(verdict in {"PASS", "BLOCKED"}, chain_error)
                matches(
                    cycle[2],
                    V2StageState(verdict),
                    "WORKSPACE_SOURCE_QUALIFICATION_REVIEWED_" + verdict + "_" + suffix,
                    subjects + [records["review"]["reference"]],
                )
                state = "REVIEWED_" + verdict
                predecessor_hashes = {
                    role: records[role]["evidence_sha256"]
                    for role in ("receipt", "assessment", "review")
                }
                previous_refs = [
                    records[role]["reference"]
                    for role in ("receipt", "assessment", "review")
                ]
        verified_cycles.append(
            {
                "qualification_id": qualification_id,
                "state": state,
                **{
                    role: records.get(role)
                    for role in (
                        "isolation_original",
                        "receipt",
                        "assessment",
                        "review",
                    )
                },
            }
        )

    if static_event is not None:
        _require(verified_cycles[-1]["state"] == "REVIEWED_PASS", state_error)
        matches(
            static_event,
            V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + cycles[-1][0][11:].upper(),
            [],
            stage=STAGE_ORDER[1],
        )
    _require(snapshot.stages[0].state is cycles[-1][1][-1].state, state_error)
    if prefix_event_count is None:
        _require(
            snapshot.stages[1].state
            is (V2StageState.WAITING_OPERATOR if static_event else V2StageState.PENDING)
            and not snapshot.stages[1].evidence_ids
            and all(
                item.state is V2StageState.PENDING and not item.evidence_ids
                for item in snapshot.stages[2:]
            ),
            state_error,
        )
    else:
        _require(
            static_event is not None
            and static_event is events[-1]
            and verified_cycles[-1]["state"] == "REVIEWED_PASS",
            state_error,
        )
    return {
        "schema": SOURCE_WORKFLOW_QUALIFICATION_SCHEMA,
        "binding": bound,
        "session_header_sha256": expected_header_sha256,
        "session_head_sha256": snapshot.head.head_sha256,
        "evidence_inventory_sha256": canonical_sha256(
            [ref.to_dict() for ref in snapshot.evidence]
        ),
        "stage": STAGE_ORDER[0].value,
        "state": snapshot.stages[0].state.value,
        **{
            role: roles[role]
            for role in ("prerequisites", "receipt", "assessment", "review")
        },
        **(
            {"configuration_epochs": roles["configuration_epochs"]}
            if "configuration_epochs" in roles
            else {}
        ),
        "original_source_state": "BLOCKED",
        "intake_collections": collections,
        "qualification_cycles": verified_cycles,
        "static_camera_request": (
            None if static_event is None else static_event.to_dict()
        ),
        "physical_authority": False,
        "device_io_performed": False,
    }
