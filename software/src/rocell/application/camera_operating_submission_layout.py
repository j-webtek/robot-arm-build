"""Closed v17 submission suffix over the unchanged complete session snapshot.

Structural validation only. The original reader must separately authenticate
every v16 predecessor and the retained native/checksum inputs on this snapshot.
No synthetic past snapshot, arbitrary inventory allowance or stage PASS exists.
"""

from dataclasses import dataclass

from .camera_operating_submission import (
    CameraOperatingSubmission,
    MAX_BYTES,
    camera_operating_submission_event,
)
from .camera_probe_preparation import camera_probe_event
from .camera_probe_preparation_layout import (
    CameraProbePreparationLayout,
    _record,
    _original_record,
    _verify_camera_probe_preparation_prefix_layout,
)
from .physical_camera_mode_entry import CameraModeEntry
from .physical_camera_mode_entry_layout import CameraModeEntryLayout
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
)
from rocell.providers.windows.native_camera_protocol import canonical, digest


class CameraOperatingLayoutError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_OPERATING_SUBMISSION_LAYOUT_INVALID")


def _need(ok: bool) -> None:
    if not ok:
        raise CameraOperatingLayoutError()


def _verify_operating_suffix(snapshot, entry_record, probe_packages, record):
    """Verify only this suffix; never recurse into the predecessor allowance."""
    try:
        _need(type(snapshot) is V2SessionSnapshot and not snapshot.uncommitted_events)
        _need(
            type(record) is dict
            and set(record) == {"document", "reference", "evidence_sha256", "retention"}
        )
        _need(record["retention"] == "M1_FULL_BYTES_READ_BACK")
        raw = canonical(record["document"])
        _need(0 < len(raw) <= MAX_BYTES)
        subject = CameraOperatingSubmission(raw)
        reference = _parse_evidence_reference(record["reference"])
        _need(
            reference.stage is STAGE_ORDER[4]
            and reference.payload_sha256 == record["evidence_sha256"] == digest(raw)
            and reference.payload_bytes == len(raw)
        )
        inventory = {ref.evidence_id: ref for ref in snapshot.evidence}
        _need(
            len(inventory) == len(snapshot.evidence)
            and inventory.get(reference.evidence_id) == reference
        )
        _need(type(probe_packages) is dict and len(probe_packages) == 2)
        subjects, refs = {}, {}
        for evidence_id, package in probe_packages.items():
            _need(
                type(package) is dict
                and package.get("kind") in ("preparation", "review")
            )
            kind = package["kind"]
            _need(kind not in subjects)
            subjects[kind], refs[kind] = _record(package, kind)
            _need(
                evidence_id == refs[kind].evidence_id
                and inventory.get(evidence_id) == refs[kind]
            )
        _need(set(subjects) == {"preparation", "review"})
        preparation, review = subjects["preparation"], subjects["review"]
        prep = preparation.to_dict()
        rd = review.to_dict()
        _need(
            rd["preparation_sha256"] == preparation.sha256
            and rd["preparation_id"] == prep["preparation_id"]
        )
        data = subject.to_dict()
        binding = data["binding"]
        entry = CameraModeEntry(canonical(entry_record["document"]))
        _need(
            binding["entry_sha256"] == entry.sha256 == prep["entry_sha256"]
            and binding["probe_preparation_sha256"] == preparation.sha256
            and binding["probe_review_sha256"] == review.sha256
            and binding["source_sha256"] == prep["plan"]["source_sha256"]
            and binding["cell_id"] == snapshot.header.cell_id
            and binding["session_id"] == snapshot.header.session_id
            and binding["header_sha256"] == snapshot.header.header_sha256
        )
        # Locate the actual reviewed preparation event; a claimed index or a
        # different same-state event is not an eligible creation boundary.
        starts = [
            (i, event)
            for i, event in enumerate(snapshot.committed_events)
            if event.detail_code
            == camera_probe_event("REVIEWED", prep["preparation_id"])
        ]
        _need(len(starts) == 1)
        index, previous = starts[0]
        _need(
            previous.stage is STAGE_ORDER[4]
            and previous.previous_state is V2StageState.BLOCKED
            and previous.state is V2StageState.WAITING_OPERATOR
            and previous.evidence
            == tuple(sorted(refs.values(), key=lambda ref: ref.evidence_id))
            and previous.occurred_at_ns >= rd["reviewed_at_utc_ns"]
            and data["recorded_at_utc_ns"] >= previous.occurred_at_ns
        )
        # Reconstruct only a head digest from actual journal bytes. No reduced
        # SessionSnapshot is constructed or supplied to a predecessor reader.
        creation = V2CommittedHead.build(
            snapshot.header, snapshot.committed_events[: index + 1]
        )
        _need(binding["journal_head_sha256"] == creation.head_sha256)
        events = snapshot.committed_events[index + 1 :]
        _need(len(events) <= 1)
        _need(
            not any(
                reference in event.evidence
                for event in snapshot.committed_events[: index + 1]
            )
        )
        if events:
            event = events[0]
            _need(
                type(event) is V2JournalEvent
                and event.sequence == previous.sequence + 1
                and event.previous_event_sha256 == previous.event_sha256
                and event.session_id == snapshot.header.session_id
                and event.session_header_sha256 == snapshot.header.header_sha256
                and event.stage is STAGE_ORDER[4]
                and event.previous_state is V2StageState.WAITING_OPERATOR
                and event.state is V2StageState.REVIEW_PENDING
                and event.occurred_at_ns >= data["recorded_at_utc_ns"]
                and event.evidence == (reference,)
                and event.detail_code
                == camera_operating_submission_event(data["submission_id"])
            )
        return dict(
            subject=subject,
            reference=reference,
            events=events,
            state="SUBMITTED_REVIEW_REQUIRED" if events else "INCOMPLETE",
        )
    except CameraOperatingLayoutError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as error:
        raise CameraOperatingLayoutError() from error


@dataclass(frozen=True, slots=True)
class CameraOperatingSubmissionLayout:
    probe: CameraProbePreparationLayout
    submission: CameraOperatingSubmission
    reference: EvidenceReference
    events: tuple[V2JournalEvent, ...]
    state: str

    @property
    def original_store_authenticated(self) -> bool:
        return False


def verify_camera_operating_submission_layout(
    snapshot, entry_record, probe_packages, record
):
    """Validate the exact v17 layout, while all old public layouts stay closed."""
    try:
        suffix = _verify_operating_suffix(
            snapshot, entry_record, probe_packages, record
        )
        probe = _verify_camera_probe_preparation_prefix_layout(
            snapshot,
            entry_record,
            probe_packages,
            operating_record=record,
        )
        _need(probe.state == "REVIEWED_FOR_ADMISSION" and len(probe.events) == 2)
        return CameraOperatingSubmissionLayout(
            probe,
            suffix["subject"],
            suffix["reference"],
            suffix["events"],
            suffix["state"],
        )
    except CameraOperatingLayoutError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as error:
        raise CameraOperatingLayoutError() from error


def _camera_operating_submission_extension(snapshot, layout):
    """Internal, exact revalidation before any predecessor inventory allowance."""
    _need(type(layout) is CameraOperatingSubmissionLayout)
    _need(
        type(layout.probe) is CameraProbePreparationLayout
        and type(layout.submission) is CameraOperatingSubmission
        and type(layout.reference) is EvidenceReference
    )
    _need(type(layout.probe.mode_entry) is CameraModeEntryLayout)
    probe, entry = layout.probe, layout.probe.mode_entry
    _need(probe.review is not None and probe.review_reference is not None)
    packages = {}
    for kind, subject, reference in (
        ("preparation", probe.preparation, probe.preparation_reference),
        ("review", probe.review, probe.review_reference),
    ):
        packages[reference.evidence_id] = dict(
            kind=kind,
            preparation_id=subject.to_dict()["preparation_id"],
            record=_original_record(subject, reference),
        )
    checked = verify_camera_operating_submission_layout(
        snapshot,
        _original_record(entry.entry, entry.reference),
        packages,
        _original_record(layout.submission, layout.reference),
    )
    _need(checked == layout)
    return (
        frozenset(
            (entry.reference.evidence_id, *packages, layout.reference.evidence_id)
        ),
        len(entry.events) + len(probe.events) + len(layout.events),
    )
