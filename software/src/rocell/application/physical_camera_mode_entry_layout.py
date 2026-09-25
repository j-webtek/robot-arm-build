"""Closed stage-5 suffix layout on a full snapshot, not original authentication.

The owner separately authenticates all predecessor roles/campaigns and derives
the exact binding. This check never trims the real snapshot, invents a previous
journal, approves a runtime or creates a camera permit.
"""

from dataclasses import dataclass
from typing import Any

from .physical_camera_mode_entry import (
    CameraModeEntry,
    MAX_ENTRY_BYTES,
    camera_mode_entry_event,
    verify_camera_mode_entry,
)
from .physical_camera_usb_complete_constants import USB_COMPLETE_EVENT
from .physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from .physical_onboarding_v2 import (
    V2CommittedHead,
    V2JournalEvent,
    V2SessionSnapshot,
    V2StageState,
    _parse_event,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest


class CameraModeEntryLayoutError(ValueError):
    pass


def _need(ok: bool) -> None:
    if not ok:
        raise CameraModeEntryLayoutError("CAMERA_MODE_ENTRY_LAYOUT_INVALID")


@dataclass(frozen=True, slots=True)
class CameraModeEntryLayout:
    entry: CameraModeEntry
    reference: EvidenceReference
    prefix_event_count: int
    events: tuple[V2JournalEvent, ...]
    state: str

    @property
    def original_store_authenticated(self) -> bool:
        return False


def _camera_mode_entry_extension(snapshot, layout):
    """Private predecessor allowance for this one revalidated suffix only.

    Older public readers never supply a layout. Internal prefix readers use
    this helper before excluding its one record from a historical inventory.
    Recheck the full snapshot instead of trusting a constructed dataclass or
    accepting an arbitrary set of evidence IDs. Prefix authentication remains
    the original owner's separate responsibility.
    """
    if layout is None:
        return frozenset(), 0
    # v17 is a closed submission suffix, not an arbitrary inventory exemption.
    from .camera_operating_submission_layout import (
        CameraOperatingSubmissionLayout,
        _camera_operating_submission_extension,
    )

    if type(layout) is CameraOperatingSubmissionLayout:
        return _camera_operating_submission_extension(snapshot, layout)
    # The v16 owner can provide one closed, independently revalidated extension.
    # Old public entry points still accept only the original v15 shape below.
    from .camera_probe_preparation_layout import (
        CameraProbePreparationLayout,
        _camera_probe_preparation_extension,
    )

    if type(layout) is CameraProbePreparationLayout:
        return _camera_probe_preparation_extension(snapshot, layout)
    _need(type(layout) is CameraModeEntryLayout)
    document = layout.entry.to_dict()
    record = dict(
        document=document,
        evidence_sha256=layout.entry.sha256,
        reference=layout.reference.to_dict(),
        retention="M1_FULL_BYTES_READ_BACK",
    )
    checked = verify_camera_mode_entry_layout(
        snapshot,
        record,
        expected_entry_id=document["entry_id"],
        expected_binding=document["binding"],
    )
    _need(checked == layout)
    return frozenset((checked.reference.evidence_id,)), len(checked.events)


def verify_camera_mode_entry_layout(
    snapshot: V2SessionSnapshot,
    record: dict[str, Any],
    *,
    expected_entry_id: str,
    expected_binding: dict[str, str],
) -> CameraModeEntryLayout:
    """Closed public v15 layout: rejects any later preparation records/events."""
    return _verify_camera_mode_entry_prefix_layout(
        snapshot,
        record,
        expected_entry_id=expected_entry_id,
        expected_binding=expected_binding,
    )


def _verify_camera_mode_entry_prefix_layout(
    snapshot: V2SessionSnapshot,
    record: dict[str, Any],
    *,
    expected_entry_id: str,
    expected_binding: dict[str, str],
    probe_packages=None,
    operating_record=None,
) -> CameraModeEntryLayout:
    """Verify one retained entry and zero/one committed stage-5 transition.

    A retained record without its transition is an incomplete terminal attempt,
    not a request to repair/continue it. No other stage-5 or future-stage material
    is accepted by this initial suffix. The owner must authenticate its prefix
    on the same full snapshot before using the returned prefix boundary.
    """
    try:
        _need(
            type(snapshot) is V2SessionSnapshot
            and not snapshot.uncommitted_events
            and type(snapshot.committed_events) is tuple
            and type(snapshot.evidence) is tuple
            and type(record) is dict
            and set(record) == {"document", "evidence_sha256", "reference", "retention"}
            and record["retention"] == "M1_FULL_BYTES_READ_BACK"
        )
        raw = canonical(record["document"])
        entry = verify_camera_mode_entry(
            raw,
            expected_entry_id=expected_entry_id,
            expected_binding=expected_binding,
        )
        entry_document = entry.to_dict()
        reference = _parse_evidence_reference(record["reference"])
        _need(
            reference.stage is STAGE_ORDER[4]
            and 0 < len(raw) <= MAX_ENTRY_BYTES
            and reference.payload_bytes == len(raw)
            and reference.payload_sha256 == digest(raw) == record["evidence_sha256"]
        )
        header = snapshot.header
        _need(
            header.header_sha256 == expected_binding["header_sha256"]
            and header.cell_id == expected_binding["cell_id"]
            and header.session_id == expected_binding["session_id"]
        )
        inventory = {ref.evidence_id: ref for ref in snapshot.evidence}
        later_ids: frozenset[str] = frozenset()
        later_events: tuple[V2JournalEvent, ...] = ()
        if probe_packages is not None:
            from .camera_probe_preparation_layout import _verify_probe_suffix

            suffix = _verify_probe_suffix(
                snapshot, record, probe_packages, operating_record=operating_record
            )
            later_ids, later_events = suffix["evidence_ids"], suffix["events"]
            if suffix["operating"] is not None:
                operating = suffix["operating"]
                later_ids = later_ids | frozenset((operating["reference"].evidence_id,))
                later_events = (*later_events, *operating["events"])
        else:
            _need(operating_record is None)
        _need(
            len(inventory) == len(snapshot.evidence)
            and inventory.get(reference.evidence_id) == reference
            and frozenset(
                ref.evidence_id
                for ref in snapshot.evidence
                if ref.stage is STAGE_ORDER[4]
            )
            == frozenset((reference.evidence_id,)) | later_ids
            and not any(ref.stage in STAGE_ORDER[5:] for ref in snapshot.evidence)
        )
        for event in snapshot.committed_events:
            _need(
                type(event) is V2JournalEvent and _parse_event(event.to_dict()) == event
            )
        _need(snapshot.head == V2CommittedHead.build(header, snapshot.committed_events))
        # Locate by the independently expected review hash, not by a claimed
        # prefix length. Require the exact accepted complete-review event shape.
        predecessors = [
            (index, event)
            for index, event in enumerate(snapshot.committed_events)
            if event.event_sha256 == expected_binding["complete_review_event_sha256"]
        ]
        _need(len(predecessors) == 1)
        index, predecessor = predecessors[0]
        match = USB_COMPLETE_EVENT.fullmatch(predecessor.detail_code)
        _need(
            match is not None
            and match[1] == "REVIEWED"
            and predecessor.stage is STAGE_ORDER[3]
            and predecessor.previous_state is V2StageState.REVIEW_PENDING
            and predecessor.state is V2StageState.PASS
            and entry_document["recorded_at_utc_ns"] >= predecessor.occurred_at_ns
        )
        prefix_count = index + 1
        prefix, events = (
            snapshot.committed_events[:prefix_count],
            snapshot.committed_events[
                prefix_count : len(snapshot.committed_events) - len(later_events)
            ],
        )
        _need(
            len(events) <= 1
            and not any(event.stage in STAGE_ORDER[4:] for event in prefix)
            and not any(reference in event.evidence for event in prefix)
        )
        _need(
            len(snapshot.stages) == len(STAGE_ORDER)
            and tuple(row.stage for row in snapshot.stages) == STAGE_ORDER
            and all(row.state is V2StageState.PASS for row in snapshot.stages[:4])
            and all(
                row.state is V2StageState.PENDING
                and not row.evidence_ids
                and row.last_event_sequence is None
                for row in snapshot.stages[5:]
            )
        )
        row = snapshot.stages[4]
        if not events:
            _need(
                row.state is V2StageState.PENDING
                and not row.evidence_ids
                and row.last_event_sequence is None
            )
            state = "INCOMPLETE"
        else:
            event = events[0]
            _need(
                event.sequence == prefix_count
                and event.session_id == header.session_id
                and event.session_header_sha256 == header.header_sha256
                and event.previous_event_sha256 == predecessor.event_sha256
                and event.occurred_at_ns >= entry_document["recorded_at_utc_ns"]
                and event.stage is STAGE_ORDER[4]
                and event.previous_state is V2StageState.PENDING
                and event.state is V2StageState.WAITING_OPERATOR
                and event.evidence == (reference,)
                and event.detail_code == camera_mode_entry_event(expected_entry_id)
                and (
                    probe_packages is not None
                    or (
                        row.state is V2StageState.WAITING_OPERATOR
                        and row.last_event_sequence == event.sequence
                        and row.evidence_ids == (reference.evidence_id,)
                    )
                )
            )
            state = "ENTERED"
        return CameraModeEntryLayout(entry, reference, prefix_count, events, state)
    except CameraModeEntryLayoutError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as exc:
        raise CameraModeEntryLayoutError("CAMERA_MODE_ENTRY_LAYOUT_INVALID") from exc
