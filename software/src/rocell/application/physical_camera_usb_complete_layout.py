"""V14 structural suffix checks, not original/store acceptance.

The eventual original reader must first authenticate every V2 file and complete
campaign family, and must separately reconstruct all four heterogeneous phases
and the series/assessment/review. This module checks only the closed layout on
the supplied full snapshot. Its return value is not a stage admission receipt.
It never creates a historical snapshot or changes a stored schema/head.
"""

from dataclasses import dataclass
from typing import Any

from rocell.application.physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from rocell.application.physical_onboarding_v2 import (
    V2CommittedHead,
    V2JournalEvent,
    V2SessionSnapshot,
    V2StageState,
    _parse_event,
)
from rocell.application.physical_camera_usb_reboot_constants import usb_reboot_event
from rocell.providers.windows.usb_identity_protocol import canonical, digest

# Pure shared components; none authenticates storage or grants device access.
from .physical_camera_usb_complete_constants import (
    MAX_USB_COMPLETE_EVENTS,
    USB_COMPLETE_EVENT,
    USB_COMPLETE_ROLE_BYTES,
    usb_complete_event,
)
from .physical_usb_complete_series import (
    CompleteUsbSeries,
    CompleteUsbAssessment,
    CompleteUsbReview,
    REVIEW_ELIGIBLE,
)


class CompleteUsbLayoutError(ValueError):
    """Invalid suffix structure; does not expose original private subjects."""


def _need(ok: bool) -> None:
    if not ok:
        raise CompleteUsbLayoutError("USB_COMPLETE_ORIGINAL_LAYOUT_INVALID")


@dataclass(frozen=True, slots=True)
class CompleteUsbRoleRecord:
    role: str
    reference: EvidenceReference
    payload: bytes


@dataclass(frozen=True, slots=True)
class CompleteUsbSuffixLayout:
    series_id: str
    prefix_event_count: int
    events: tuple[V2JournalEvent, ...]
    records: tuple[CompleteUsbRoleRecord, ...]

    # No cached workflow or layout object authenticates original storage.
    @property
    def original_store_authenticated(self) -> bool:
        return False


def verify_complete_usb_suffix_layout(
    snapshot: V2SessionSnapshot,
    packages: dict[str, Any],
    *,
    expected_header_sha256: str,
    expected_binding: dict[str, str],
    predecessor_phase_id: str,
    predecessor_reference: EvidenceReference,
    predecessor_finished_at_utc_ns: int,
) -> CompleteUsbSuffixLayout:
    """Closed public v14 layout: later-stage records remain rejected."""
    return _verify_complete_usb_prefix_layout(
        snapshot,
        packages,
        expected_header_sha256=expected_header_sha256,
        expected_binding=expected_binding,
        predecessor_phase_id=predecessor_phase_id,
        predecessor_reference=predecessor_reference,
        predecessor_finished_at_utc_ns=predecessor_finished_at_utc_ns,
    )


def _verify_complete_usb_prefix_layout(
    snapshot: V2SessionSnapshot,
    packages: dict[str, Any],
    *,
    expected_header_sha256: str,
    expected_binding: dict[str, str],
    predecessor_phase_id: str,
    predecessor_reference: EvidenceReference,
    predecessor_finished_at_utc_ns: int,
    camera_mode_entry=None,
) -> CompleteUsbSuffixLayout:
    """Check file/event membership; the owner still verifies their meaning.

    Packages use the existing original reader's kind/series_id/record shape.
    All inventory not in this exact suffix belongs to the real v13 predecessor
    and must be passed unchanged to that predecessor's complete original audit.
    This function cannot accept an export, a supplied PASS flag or an exclusion
    list that could hide extra original files.
    """
    try:
        from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

        mode_ids, mode_events = _camera_mode_entry_extension(
            snapshot, camera_mode_entry
        )
        _need(
            type(snapshot) is V2SessionSnapshot
            and type(snapshot.committed_events) is tuple
            and not snapshot.uncommitted_events
            and type(snapshot.evidence) is tuple
            and snapshot.header.header_sha256 == expected_header_sha256
            and type(packages) is dict
            and len(packages) <= len(USB_COMPLETE_ROLE_BYTES)
            and type(predecessor_reference) is EvidenceReference
            and predecessor_reference.stage is STAGE_ORDER[3]
            and type(predecessor_finished_at_utc_ns) is int
            and 0 < predecessor_finished_at_utc_ns < 2**63
            and type(expected_binding) is dict
        )
        # Reject forged in-memory event/hash pairs as well as unknown suffix
        # names. Full replay/state validation remains the V2 original loader's job.
        for event in snapshot.committed_events:
            _need(
                type(event) is V2JournalEvent and _parse_event(event.to_dict()) == event
            )
        _need(
            snapshot.head
            == V2CommittedHead.build(snapshot.header, snapshot.committed_events)
        )
        starts = [
            (index, event)
            for index, event in enumerate(snapshot.committed_events)
            if event.detail_code.startswith("CAMERA_USB_COMPLETE_")
        ]
        _need(1 <= len(starts) <= MAX_USB_COMPLETE_EVENTS)
        index, first = starts[0]
        matched = USB_COMPLETE_EVENT.fullmatch(first.detail_code)
        _need(
            matched is not None and matched[1] == "ASSESSMENT_REQUESTED" and index > 0
        )
        assert matched is not None
        series_id = "usbseries-" + matched[2].lower()
        end = len(snapshot.committed_events) - mode_events
        events = snapshot.committed_events[index:end]
        _need(len(events) == len(starts))
        previous = snapshot.committed_events[index - 1]
        _need(
            previous.detail_code == usb_reboot_event("RETAINED", predecessor_phase_id)
            and previous.stage is STAGE_ORDER[3]
            and previous.state is V2StageState.BLOCKED
            and predecessor_reference in previous.evidence
            and first.occurred_at_ns >= previous.occurred_at_ns
            and first.occurred_at_ns > predecessor_finished_at_utc_ns
        )
        inventory = {ref.evidence_id: ref for ref in snapshot.evidence}
        _need(
            len(inventory) == len(snapshot.evidence)
            and inventory.get(predecessor_reference.evidence_id)
            == predecessor_reference
            and set(packages) <= set(inventory)
            and mode_ids.isdisjoint(packages)
            and predecessor_reference.evidence_id not in packages
            and not any(
                ref.evidence_id in packages
                for event in snapshot.committed_events[:index]
                for ref in event.evidence
            )
        )
        records = {}
        documents = {}
        classes = dict(
            series=CompleteUsbSeries,
            assessment=CompleteUsbAssessment,
            review=CompleteUsbReview,
        )
        for evidence_id, package in packages.items():
            _need(
                type(package) is dict
                and set(package) == {"kind", "series_id", "record"}
                and package["series_id"] == series_id
                and type(package["kind"]) is str
                and package["kind"] in USB_COMPLETE_ROLE_BYTES
                and package["kind"] not in records
            )
            role, record = package["kind"], package["record"]
            _need(
                type(record) is dict
                and set(record)
                == {"document", "evidence_sha256", "reference", "retention"}
                and record["retention"] == "M1_FULL_BYTES_READ_BACK"
            )
            reference = _parse_evidence_reference(record["reference"])
            raw = canonical(record["document"])
            _need(
                reference == inventory[evidence_id]
                and reference.stage is STAGE_ORDER[3]
                and 0 < len(raw) <= USB_COMPLETE_ROLE_BYTES[role]
                and len(raw) == reference.payload_bytes
                and digest(raw) == reference.payload_sha256 == record["evidence_sha256"]
            )
            document = classes[role](raw).to_dict()
            _need(
                document["series_id"] == series_id
                and document["binding"] == expected_binding
            )
            records[role] = CompleteUsbRoleRecord(role, reference, raw)
            documents[role] = document
        order = tuple(USB_COMPLETE_ROLE_BYTES)
        _need(tuple(role for role in order if role in records) == order[: len(records)])
        # A partial write is readable only in the operation which could have
        # produced it. Review bytes cannot appear before assessment retention.
        minimum, maximum = ((0, 2), (2, 3), (3, 3))[len(events) - 1]
        _need(minimum <= len(records) <= maximum)
        if "assessment" in documents:
            _need(
                documents["assessment"]["series_sha256"]
                == digest(records["series"].payload)
                and documents["assessment"]["plan_sha256"]
                == documents["series"]["plan_sha256"]
            )
        if "review" in documents:
            review = documents["review"]
            _need(
                review["series_sha256"] == digest(records["series"].payload)
                and review["assessment_sha256"] == digest(records["assessment"].payload)
                and review["plan_sha256"] == documents["series"]["plan_sha256"]
                and review["reviewed_at_utc_ns"] >= events[1].occurred_at_ns
            )

        def citations(names):
            return tuple(
                sorted(
                    (records[name].reference for name in names),
                    key=lambda ref: ref.evidence_id,
                )
            )

        expected = [
            (
                "ASSESSMENT_REQUESTED",
                V2StageState.WAITING_OPERATOR,
                (predecessor_reference,),
            )
        ]
        if len(events) >= 2:
            expected.append(
                (
                    "ASSESSMENT_RETAINED",
                    V2StageState.REVIEW_PENDING,
                    citations(order[:2]),
                )
            )
        if len(events) == 3:
            review = documents["review"]
            # This only agrees with the encoded claim. The owner's independent
            # complete-series reconstruction must prove that claim before PASS.
            state = (
                V2StageState.PASS
                if review["verdict"] == REVIEW_ELIGIBLE
                else V2StageState.BLOCKED
            )
            expected.append(("REVIEWED", state, citations(order)))
            _need(events[-1].occurred_at_ns >= review["reviewed_at_utc_ns"])
        previous_state = V2StageState.BLOCKED
        previous_time = previous.occurred_at_ns
        previous_hash = previous.event_sha256
        for offset, (event, (kind, state, refs)) in enumerate(zip(events, expected)):
            _need(
                event.sequence == index + offset
                and event.session_id == snapshot.header.session_id
                and event.session_header_sha256 == expected_header_sha256
                and event.previous_event_sha256 == previous_hash
                and event.occurred_at_ns >= previous_time
                and event.stage is STAGE_ORDER[3]
                and event.previous_state is previous_state
                and event.state is state
                and event.evidence == refs
                and event.detail_code == usb_complete_event(kind, series_id)
            )
            previous_state, previous_time, previous_hash = (
                state,
                event.occurred_at_ns,
                event.event_sha256,
            )
        _need(
            len(snapshot.stages) == len(STAGE_ORDER)
            and tuple(row.stage for row in snapshot.stages) == STAGE_ORDER
            and snapshot.stages[3].state is events[-1].state
            and all(
                row.state is V2StageState.PENDING and not row.evidence_ids
                for row in snapshot.stages[4 if camera_mode_entry is None else 5 :]
            )
        )
        return CompleteUsbSuffixLayout(
            series_id,
            index,
            events,
            tuple(records[role] for role in order if role in records),
        )
    except CompleteUsbLayoutError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as exc:
        raise CompleteUsbLayoutError("USB_COMPLETE_ORIGINAL_LAYOUT_INVALID") from exc
