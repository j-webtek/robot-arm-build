"""Closed v16 probe-preparation suffix on the complete original snapshot.

Structural validation is not authentication. The original reader must still
authenticate every v15 predecessor on this same snapshot, then compare current
preparation dependencies. No synthetic past snapshot or arbitrary-ID allowance
is accepted by predecessor readers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
    MAX_PREPARATION_BYTES,
    MAX_REVIEW_BYTES,
    camera_probe_event,
)
from .physical_camera_mode_entry import CameraModeEntry, camera_mode_entry_event
from .physical_camera_mode_entry_layout import (
    CameraModeEntryLayout,
    _verify_camera_mode_entry_prefix_layout,
)
from .physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState, V2JournalEvent
from rocell.providers.windows.native_camera_protocol import canonical, digest


class CameraProbeLayoutError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_PROBE_PREPARATION_LAYOUT_INVALID")


def _need(ok: bool) -> None:
    if not ok:
        raise CameraProbeLayoutError()


def _record(package, kind):
    _need(
        type(package) is dict
        and set(package) == {"kind", "preparation_id", "record"}
        and package["kind"] == kind
    )
    record = package["record"]
    _need(
        type(record) is dict
        and set(record) == {"document", "reference", "evidence_sha256", "retention"}
    )
    _need(record["retention"] == "M1_FULL_BYTES_READ_BACK")
    raw = canonical(record["document"])
    maximum, cls = (
        (MAX_PREPARATION_BYTES, CameraProbePreparation)
        if kind == "preparation"
        else (MAX_REVIEW_BYTES, CameraProbePreparationReview)
    )
    _need(0 < len(raw) <= maximum)
    subject = cls(raw)
    reference = _parse_evidence_reference(record["reference"])
    _need(
        subject.to_dict()["preparation_id"] == package["preparation_id"]
        and reference.stage is STAGE_ORDER[4]
        and reference.payload_bytes == len(raw)
        and reference.payload_sha256 == record["evidence_sha256"] == digest(raw)
    )
    return subject, reference


def _verify_probe_suffix(snapshot, entry_record, packages, *, operating_record=None):
    """Internal complete suffix check; does not call the mode prefix reader."""
    try:
        _need(type(snapshot) is V2SessionSnapshot and not snapshot.uncommitted_events)
        _need(type(packages) is dict and 1 <= len(packages) <= 2)
        subjects, references = {}, {}
        inventory = {ref.evidence_id: ref for ref in snapshot.evidence}
        _need(len(inventory) == len(snapshot.evidence))
        for evidence_id, package in packages.items():
            _need(
                type(package) is dict
                and package.get("kind") in {"preparation", "review"}
            )
            kind = package["kind"]
            _need(kind not in subjects)
            subject, reference = _record(package, kind)
            _need(
                evidence_id == reference.evidence_id
                and inventory.get(evidence_id) == reference
            )
            subjects[kind], references[kind] = subject, reference
        _need("preparation" in subjects)
        prep = subjects["preparation"].to_dict()
        entry = CameraModeEntry(canonical(entry_record["document"]))
        entry_ref = _parse_evidence_reference(entry_record["reference"])
        ed = entry.to_dict()
        plan = prep["plan"]
        _need(
            prep["entry_sha256"] == entry.sha256
            and plan["source_sha256"] == ed["binding"]["source_sha256"]
            and plan["cell_id"] == snapshot.header.cell_id == ed["binding"]["cell_id"]
            and plan["session_id"]
            == snapshot.header.session_id
            == ed["binding"]["session_id"]
        )
        starts = [
            (i, event)
            for i, event in enumerate(snapshot.committed_events)
            if event.event_sha256 == prep["entry_event_sha256"]
        ]
        _need(len(starts) == 1)
        index, opening = starts[0]
        _need(
            opening.stage is STAGE_ORDER[4]
            and opening.state is V2StageState.WAITING_OPERATOR
            and opening.previous_state is V2StageState.PENDING
            and opening.detail_code == camera_mode_entry_event(ed["entry_id"])
            and opening.evidence == (entry_ref,)
            and prep["prepared_at_utc_ns"] >= opening.occurred_at_ns
        )
        operating = None
        if operating_record is not None:
            from .camera_operating_submission_layout import _verify_operating_suffix

            operating = _verify_operating_suffix(
                snapshot, entry_record, packages, operating_record
            )
        later_events = () if operating is None else operating["events"]
        events = snapshot.committed_events[
            index + 1 : len(snapshot.committed_events) - len(later_events)
        ]
        _need(len(events) <= 2)
        if "review" in subjects:
            review = subjects["review"].to_dict()
            _need(
                len(events) >= 1
                and review["preparation_id"] == prep["preparation_id"]
                and review["preparation_sha256"] == subjects["preparation"].sha256
                and review["reviewed_at_utc_ns"] >= events[0].occurred_at_ns
            )
        if len(events) == 2:
            _need("review" in subjects)
        previous = opening
        for number, event in enumerate(events):
            kinds = ("preparation",) if number == 0 else ("preparation", "review")
            cited = tuple(
                sorted(
                    (references[kind] for kind in kinds),
                    key=lambda ref: ref.evidence_id,
                )
            )
            when = (
                prep["prepared_at_utc_ns"]
                if number == 0
                else subjects["review"].to_dict()["reviewed_at_utc_ns"]
            )
            _need(
                type(event) is V2JournalEvent
                and event.sequence == previous.sequence + 1
                and event.previous_event_sha256 == previous.event_sha256
                and event.session_id == snapshot.header.session_id
                and event.session_header_sha256 == snapshot.header.header_sha256
                and event.stage is STAGE_ORDER[4]
                and event.previous_state is previous.state
                and event.state
                is (
                    V2StageState.BLOCKED
                    if number == 0
                    else V2StageState.WAITING_OPERATOR
                )
                and event.occurred_at_ns >= max(when, previous.occurred_at_ns)
                and event.detail_code
                == camera_probe_event(
                    "PREPARED" if number == 0 else "REVIEWED", prep["preparation_id"]
                )
                and event.evidence == cited
            )
            previous = event
        row = snapshot.stages[4]
        # V2 rows retain chronological citations, including repeated references.
        # They are not a sorted/deduplicated inventory of evidence packages.
        cited_ids = (
            entry_ref.evidence_id,
            *(ref.evidence_id for event in events for ref in event.evidence),
            *(ref.evidence_id for event in later_events for ref in event.evidence),
        )
        final = later_events[-1] if later_events else previous
        _need(
            row.stage is STAGE_ORDER[4]
            and row.state is final.state
            and row.last_event_sequence == final.sequence
            and row.evidence_ids == cited_ids
            and not any(
                reference in event.evidence
                for reference in references.values()
                for event in snapshot.committed_events[: index + 1]
            )
        )
        state = (
            "REVIEWED_FOR_ADMISSION"
            if len(events) == 2
            else (
                "PREPARED_REVIEW_REQUIRED"
                if len(events) == 1 and "review" not in subjects
                else "INCOMPLETE"
            )
        )
        return dict(
            subjects=subjects,
            references=references,
            evidence_ids=frozenset(packages),
            events=events,
            state=state,
            operating=operating,
        )
    except CameraProbeLayoutError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as error:
        raise CameraProbeLayoutError() from error


@dataclass(frozen=True, slots=True)
class CameraProbePreparationLayout:
    mode_entry: CameraModeEntryLayout
    preparation: CameraProbePreparation
    preparation_reference: EvidenceReference
    review: CameraProbePreparationReview | None
    review_reference: EvidenceReference | None
    events: tuple[V2JournalEvent, ...]
    state: str

    @property
    def original_store_authenticated(self) -> bool:
        return False


def verify_camera_probe_preparation_layout(
    snapshot, entry_record, packages
) -> CameraProbePreparationLayout:
    """Closed public v16 layout; later operating submissions are not allowed."""
    return _verify_camera_probe_preparation_prefix_layout(
        snapshot, entry_record, packages
    )


def _verify_camera_probe_preparation_prefix_layout(
    snapshot, entry_record, packages, *, operating_record=None
) -> CameraProbePreparationLayout:
    suffix = _verify_probe_suffix(
        snapshot, entry_record, packages, operating_record=operating_record
    )
    ed = entry_record["document"]
    entry = _verify_camera_mode_entry_prefix_layout(
        snapshot,
        entry_record,
        expected_entry_id=ed["entry_id"],
        expected_binding=ed["binding"],
        probe_packages=packages,
        operating_record=operating_record,
    )
    _need(entry.state == "ENTERED")
    return CameraProbePreparationLayout(
        entry,
        suffix["subjects"]["preparation"],
        suffix["references"]["preparation"],
        suffix["subjects"].get("review"),
        suffix["references"].get("review"),
        suffix["events"],
        suffix["state"],
    )


def _original_record(subject, reference):
    return dict(
        document=subject.to_dict(),
        evidence_sha256=subject.sha256,
        reference=reference.to_dict(),
        retention="M1_FULL_BYTES_READ_BACK",
    )


def _camera_probe_preparation_extension(snapshot, layout):
    """Revalidate the complete immutable value before any predecessor allowance."""
    _need(type(layout) is CameraProbePreparationLayout)
    entry_record = _original_record(
        layout.mode_entry.entry, layout.mode_entry.reference
    )
    packages = {}
    for kind, subject, reference in (
        ("preparation", layout.preparation, layout.preparation_reference),
        ("review", layout.review, layout.review_reference),
    ):
        _need((subject is None) == (reference is None))
        if subject is not None:
            packages[reference.evidence_id] = dict(
                kind=kind,
                preparation_id=subject.to_dict()["preparation_id"],
                record=_original_record(subject, reference),
            )
    checked = verify_camera_probe_preparation_layout(snapshot, entry_record, packages)
    _need(checked == layout)
    return frozenset((layout.mode_entry.reference.evidence_id, *packages)), len(
        layout.mode_entry.events
    ) + len(layout.events)
