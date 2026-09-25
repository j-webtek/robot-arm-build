"""File-only entry over real V2 storage and one genuine NTFS M1 transaction.

The predecessor payloads below are explicitly synthetic storage fixtures, NOT
the application's authenticated original identity chain. They exercise journal,
publication and lease contracts cheaply. The separate public NTFS acceptance
test constructs and authenticates the complete original through the wizard.
No camera, serial port, native helper or other child process is executed.
"""

from copy import deepcopy
from dataclasses import replace
import hashlib

import pytest

from rocell.application.commissioning_camera_persistence import (
    M1CommissioningPersistenceError,
    physical_camera_source_binding,
)
from rocell.application.physical_camera_mode_entry import (
    CameraModeEntryError,
    HASH_FIELDS,
    build_camera_mode_entry,
    camera_mode_entry_event,
    camera_mode_entry_label,
)
from rocell.application.physical_camera_mode_entry_layout import (
    verify_camera_mode_entry_layout,
)
from rocell.application.physical_camera_usb_complete_constants import usb_complete_event
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import (
    PhysicalOnboardingV2Error,
    PhysicalOnboardingV2Session,
    V2StageState,
    V2UncommittedSuffixError,
)
from test_commissioning_camera_persistence import (
    CELL,
    SESSION,
    SOURCE,
    WINDOWS,
    forbid_device_and_process_calls,
    runtime_and_adapter,
)
from test_physical_onboarding_v2 import _FailHeadPublication, _tree_bytes


def predecessor(owner):
    """Create real journal transitions from labeled, incapable fixture bytes."""
    when = 2001
    for stage in STAGE_ORDER[:4]:
        owner.commit_stage_state(
            stage,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=when,
            detail_code="MODELED_STORAGE_ONLY",
            expected_head_sha256=owner.snapshot().head.head_sha256,
        )
        when += 1
        reference = owner.store_evidence(
            stage,
            b"MODELED storage predecessor; no original identity or hardware proof",
            label="MODELED storage contract only",
            media_type="text/plain",
            captured_at_ns=when,
            expected_head_sha256=owner.snapshot().head.head_sha256,
        )
        for state in (V2StageState.REVIEW_PENDING, V2StageState.PASS):
            owner.commit_stage_state(
                stage,
                state,
                occurred_at_ns=when,
                detail_code=(
                    usb_complete_event("REVIEWED", "usbseries-" + "1" * 32)
                    if stage is STAGE_ORDER[3] and state is V2StageState.PASS
                    else "MODELED_STORAGE_ONLY"
                ),
                evidence=(reference,),
                expected_head_sha256=owner.snapshot().head.head_sha256,
            )
            when += 1
    return owner.snapshot()


def entry_for(snapshot, **binding_changes):
    binding = dict(
        **{key: "a" * 64 for key in HASH_FIELDS},
        cell_id=CELL,
        session_id=SESSION,
        origin_launch_id="wizard-" + "1" * 32,
        entry_launch_id="wizard-" + "2" * 32,
    )
    binding.update(
        source_sha256=SOURCE,
        header_sha256=snapshot.header.header_sha256,
        complete_review_event_sha256=snapshot.committed_events[-1].event_sha256,
    )
    binding.update(binding_changes)
    return build_camera_mode_entry(
        entry_id="cameramode-" + "3" * 32,
        binding=binding,
        operator_id="MODELED storage operator",
        recorded_at_utc_ns=10000,
    )


@pytest.fixture
def stored(tmp_path):
    session = PhysicalOnboardingV2Session.create(
        tmp_path,
        session_id=SESSION,
        cell_id=CELL,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        created_at_ns=2000,
    )
    before = predecessor(session)
    return session, before, entry_for(before)


def retain(session, before, entry, **changes):
    values = dict(
        label=camera_mode_entry_label(entry.to_dict()["entry_id"]),
        media_type="application/json",
        captured_at_ns=10001,
        expected_head_sha256=before.head.head_sha256,
    )
    values.update(changes)
    return session._store_pending_stage_entry_evidence(
        STAGE_ORDER[4], entry.payload, **values
    )


def open_entry(owner, before, entry, reference):
    return owner.commit_stage_state(
        STAGE_ORDER[4],
        V2StageState.WAITING_OPERATOR,
        occurred_at_ns=10002,
        detail_code=camera_mode_entry_event(entry.to_dict()["entry_id"]),
        expected_head_sha256=before.head.head_sha256,
        evidence=(reference,),
    )


def layout(snapshot, entry, reference):
    return verify_camera_mode_entry_layout(
        snapshot,
        dict(
            document=entry.to_dict(),
            evidence_sha256=entry.sha256,
            reference=reference.to_dict(),
            retention="M1_FULL_BYTES_READ_BACK",
        ),
        expected_entry_id=entry.to_dict()["entry_id"],
        expected_binding=entry.to_dict()["binding"],
    )


def test_real_v2_preserves_generic_guard_and_exact_partial_then_entered_layout(stored):
    session, before, entry = stored
    original = _tree_bytes(session.directory)
    with pytest.raises(PhysicalOnboardingV2Error, match="active reviewed stage"):
        session.store_evidence(
            STAGE_ORDER[4],
            entry.payload,
            label=camera_mode_entry_label(entry.to_dict()["entry_id"]),
            media_type="application/json",
            captured_at_ns=10001,
            expected_head_sha256=before.head.head_sha256,
        )
    assert _tree_bytes(session.directory) == original
    reference = retain(session, before, entry)
    partial = session.snapshot()
    assert partial.head == before.head
    assert layout(partial, entry, reference).state == "INCOMPLETE"
    with pytest.raises(PhysicalOnboardingV2Error, match="empty next pending stage"):
        retain(session, before, entry)
    entered = open_entry(session, before, entry, reference)
    assert layout(entered, entry, reference).state == "ENTERED"
    assert len(entered.committed_events) == len(before.committed_events) + 1
    # Every preexisting immutable payload/header/event is still byte-identical.
    after = _tree_bytes(session.directory)
    assert all(
        after[name] == payload
        for name, payload in original.items()
        if name != "journal/head.json"
    )
    reopened = PhysicalOnboardingV2Session(session.directory).snapshot()
    assert reopened == entered
    assert not reopened.header.to_dict()["device_io_authorized"]


@pytest.mark.parametrize(
    "changes",
    [
        dict(expected_head_sha256="f" * 64),
        dict(captured_at_ns=True),
        dict(captured_at_ns=0),
        dict(captured_at_ns=2**63),
        dict(label="bad\nlabel"),
        dict(media_type="not a media type"),
    ],
)
def test_real_v2_invalid_retention_inputs_cannot_publish(stored, changes):
    session, before, entry = stored
    original = _tree_bytes(session.directory)
    with pytest.raises(PhysicalOnboardingV2Error):
        retain(session, before, entry, **changes)
    assert _tree_bytes(session.directory) == original


@pytest.mark.parametrize("state", [V2StageState.WAITING_OPERATOR, V2StageState.BLOCKED])
def test_entry_refuses_an_already_changed_stage(stored, state):
    session, before, entry = stored
    changed = session.commit_stage_state(
        STAGE_ORDER[4],
        state,
        occurred_at_ns=9999,
        detail_code="MODELED_INTERVENING_EVENT",
        expected_head_sha256=before.head.head_sha256,
    )
    original = _tree_bytes(session.directory)
    with pytest.raises(PhysicalOnboardingV2Error, match="empty next pending stage"):
        retain(session, changed, entry)
    assert _tree_bytes(session.directory) == original


def test_entry_cannot_skip_pending_predecessors(tmp_path):
    session = PhysicalOnboardingV2Session.create(
        tmp_path,
        session_id=SESSION,
        cell_id=CELL,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        created_at_ns=2000,
    )
    original = _tree_bytes(session.directory)
    with pytest.raises(PhysicalOnboardingV2Error, match="empty next pending stage"):
        session._store_pending_stage_entry_evidence(
            STAGE_ORDER[4],
            b"MODELED incapable entry",
            label="MODELED entry",
            media_type="text/plain",
            captured_at_ns=10001,
            expected_head_sha256=session.snapshot().head.head_sha256,
        )
    assert _tree_bytes(session.directory) == original


def test_failed_opening_head_retains_original_entry_and_requires_reconciliation(stored):
    session, before, entry = stored
    reference = retain(session, before, entry)
    session = replace(session, publication=_FailHeadPublication())
    with pytest.raises(RuntimeError, match="head publication failure"):
        open_entry(session, before, entry, reference)
    observed = session.snapshot()
    assert observed.reconciliation_required and observed.head == before.head
    assert observed.uncommitted_events[0].evidence == (reference,)
    path = session.directory / "evidence" / reference.evidence_id / "payload.bin"
    assert path.read_bytes() == entry.payload
    with pytest.raises(V2UncommittedSuffixError):
        retain(session, before, entry)


def test_lost_publication_acknowledgment_preserves_incomplete_entry(stored):
    session, before, entry = stored

    class LostAcknowledgment(_FailHeadPublication):
        def sync_directory(self, path):
            self.delegate.sync_directory(path)
            if path.name == "evidence":
                raise RuntimeError("MODELED lost publication acknowledgment")

    session = replace(session, publication=LostAcknowledgment())
    with pytest.raises(RuntimeError, match="lost publication acknowledgment"):
        retain(session, before, entry)
    observed = session.snapshot()
    assert observed.head == before.head and not observed.uncommitted_events
    (reference,) = tuple(
        ref for ref in observed.evidence if ref.stage is STAGE_ORDER[4]
    )
    assert layout(observed, entry, reference).state == "INCOMPLETE"
    assert (
        session.directory / "evidence" / reference.evidence_id / "payload.bin"
    ).read_bytes() == entry.payload
    with pytest.raises(PhysicalOnboardingV2Error, match="empty next pending stage"):
        retain(session, before, entry)


@WINDOWS
def test_actual_ntfs_m1_camera_entry_retains_reads_commits_and_never_replays(tmp_path):
    runtime, adapter = runtime_and_adapter(tmp_path, ready=False)
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        before = predecessor(tx)
        entry = entry_for(before)
        # Read immutable session data, not the OS-owned exclusive lease files.
        original = _tree_bytes(tx._session.directory)
        for key, value in (
            ("header_sha256", "f" * 64),
            ("source_sha256", "f" * 64),
            ("cell_id", "wizard-physical-camera-" + "f" * 16),
            ("session_id", "physical-camera-" + "f" * 32),
            ("complete_review_event_sha256", "f" * 64),
        ):
            with pytest.raises(
                M1CommissioningPersistenceError, match="complete-review"
            ):
                tx.store_camera_mode_entry(
                    entry_for(before, **{key: value}).payload,
                    captured_at_ns=10001,
                    expected_head_sha256=before.head.head_sha256,
                )
        for captured in (True, 9999, 2**63):
            with pytest.raises(
                M1CommissioningPersistenceError, match="complete-review"
            ):
                tx.store_camera_mode_entry(
                    entry.payload,
                    captured_at_ns=captured,
                    expected_head_sha256=before.head.head_sha256,
                )
        with pytest.raises(CameraModeEntryError):
            tx.store_camera_mode_entry(
                b'{"arbitrary_pending_evidence":true}',
                captured_at_ns=10001,
                expected_head_sha256=before.head.head_sha256,
            )
        with pytest.raises(PhysicalOnboardingV2Error, match="stale"):
            tx.store_camera_mode_entry(
                entry.payload,
                captured_at_ns=10001,
                expected_head_sha256="f" * 64,
            )
        with pytest.raises(PhysicalOnboardingV2Error, match="active reviewed stage"):
            tx.store_evidence(
                STAGE_ORDER[4],
                entry.payload,
                label="MODELED ordinary evidence remains disallowed",
                media_type="application/json",
                captured_at_ns=10001,
                expected_head_sha256=before.head.head_sha256,
            )
        assert _tree_bytes(tx._session.directory) == original
        reference = tx.store_camera_mode_entry(
            entry.payload,
            captured_at_ns=10001,
            expected_head_sha256=before.head.head_sha256,
        )
        assert tx.read_stage_evidence(reference) == entry.payload
        assert reference.payload_sha256 == hashlib.sha256(entry.payload).hexdigest()
        assert layout(tx.snapshot(), entry, reference).state == "INCOMPLETE"
        with pytest.raises(PhysicalOnboardingV2Error, match="empty next pending stage"):
            tx.store_camera_mode_entry(
                entry.payload,
                captured_at_ns=10001,
                expected_head_sha256=before.head.head_sha256,
            )
        entered = open_entry(tx, before, entry, reference)
        assert layout(entered, entry, reference).state == "ENTERED"
        preserved = deepcopy(entered)
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        tx.store_camera_mode_entry(
            entry.payload,
            captured_at_ns=10001,
            expected_head_sha256=before.head.head_sha256,
        )
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as reopened:
        assert reopened.snapshot() == preserved
        assert reopened.read_stage_evidence(reference) == entry.payload
        with pytest.raises(M1CommissioningPersistenceError, match="complete-review"):
            reopened.store_camera_mode_entry(
                entry.payload,
                captured_at_ns=10001,
                expected_head_sha256=reopened.snapshot().head.head_sha256,
            )
    with adapter.transaction(
        (
            LeaseSpec(LeaseLevel.CELL, CELL),
            LeaseSpec(LeaseLevel.SESSION, SESSION),
            LeaseSpec(LeaseLevel.CAMERA, CELL),
        )
    ) as camera_tx:
        with pytest.raises(M1CommissioningPersistenceError, match="stage-only leases"):
            camera_tx.store_camera_mode_entry(
                entry.payload,
                captured_at_ns=10001,
                expected_head_sha256=preserved.head.head_sha256,
            )
