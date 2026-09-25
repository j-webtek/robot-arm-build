from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading

import pytest

from rocell.application.mission_journal import (
    ActionJournalState,
    ActionOccurrence,
    JournalRecoveryDisposition,
    MissionJournalError,
    ZeroAuthorityMissionJournal,
    load_mission_journal,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _occurrence(*, ordinal: int = 2, key: str = "t") -> ActionOccurrence:
    return ActionOccurrence.from_action_document(
        mission_id="keyboard-test-001",
        plan_sha256=_digest("plan"),
        action_ordinal=ordinal,
        action={"kind": "PRESS_KEY", "target": f"key_{key}"},
    )


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "journals"
    root.mkdir()
    return root


def test_occurrence_is_stable_and_binds_plan_ordinal_and_action() -> None:
    first = _occurrence()
    replay = _occurrence()

    assert first == replay
    assert first.occurrence_id.startswith("occ-")
    assert len(first.occurrence_id) == 36
    assert first.occurrence_hash == replay.occurrence_hash
    assert _occurrence(ordinal=3).occurrence_id != first.occurrence_id
    assert _occurrence(key="e").occurrence_id != first.occurrence_id


def test_journal_contract_is_intentionally_exported() -> None:
    import rocell.application as application

    assert application.ZeroAuthorityMissionJournal is ZeroAuthorityMissionJournal
    assert application.ActionOccurrence is ActionOccurrence
    assert application.load_mission_journal is load_mission_journal
    assert (
        application.MISSION_JOURNAL_HIGH_WATER_SCHEMA
        == "rocell.zero_authority_mission_journal_high_water.v1"
    )


def test_new_journal_atomically_commits_intent_with_zero_authority(
    tmp_path: Path,
) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    snapshot = journal.snapshot()
    document = snapshot.to_dict()

    assert snapshot.current_state is ActionJournalState.INTENT_COMMITTED
    assert snapshot.contact_may_have_occurred is False
    assert snapshot.contact_submission_permitted is False
    assert snapshot.automatic_contact_retry_permitted is False
    assert snapshot.recovery_disposition is (
        JournalRecoveryDisposition.PRE_CONTACT_WORK_MAY_RESUME
    )
    assert document["simulation_only"] is True
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["physical_release_effect"] == "NONE"
    assert sorted(path.name for path in journal.directory.iterdir()) == [
        "event-000000.json",
        "header.json",
        "high-water.json",
    ]


def test_complete_action_chain_is_hash_chained_and_restart_stable(
    tmp_path: Path,
) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    journal.commit_contact_boundary(
        event_time_ns=120, command_sha256=_digest("contact-command")
    )
    journal.confirm_outcome(event_time_ns=130, outcome_sha256=_digest("outcome"))
    journal.confirm_retracted(
        event_time_ns=140, feedback_sha256=_digest("retracted")
    )
    completed = journal.confirm_parked(
        event_time_ns=150, feedback_sha256=_digest("parked")
    )

    reopened = ZeroAuthorityMissionJournal.open(journal.directory).snapshot()
    assert reopened == completed
    assert reopened.current_state is ActionJournalState.PARKED
    assert reopened.contact_may_have_occurred is True
    assert reopened.contact_submission_permitted is False
    assert reopened.recovery_disposition is (
        JournalRecoveryDisposition.COMPLETE_NO_ACTION
    )
    assert [event.sequence for event in reopened.events] == list(range(6))
    assert all(
        event.previous_event_sha256
        == ("0" * 64 if index == 0 else reopened.events[index - 1].event_sha256)
        for index, event in enumerate(reopened.events)
    )


@pytest.mark.parametrize(
    ("stop_after", "expected_recovery", "contact_possible"),
    (
        (
            ActionJournalState.INTENT_COMMITTED,
            JournalRecoveryDisposition.PRE_CONTACT_WORK_MAY_RESUME,
            False,
        ),
        (
            ActionJournalState.PRE_CONTACT,
            JournalRecoveryDisposition.PRE_CONTACT_WORK_MAY_RESUME,
            False,
        ),
        (
            ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            JournalRecoveryDisposition.CONTACT_RETRY_FORBIDDEN_OUTCOME_UNCERTAIN,
            True,
        ),
        (
            ActionJournalState.OUTCOME_CONFIRMED,
            JournalRecoveryDisposition.RETRACT_ONLY_AFTER_INDEPENDENT_REVIEW,
            True,
        ),
        (
            ActionJournalState.RETRACTED,
            JournalRecoveryDisposition.PARK_ONLY_AFTER_INDEPENDENT_REVIEW,
            True,
        ),
        (
            ActionJournalState.PARKED,
            JournalRecoveryDisposition.COMPLETE_NO_ACTION,
            True,
        ),
    ),
)
def test_restart_at_every_action_boundary_is_conservative(
    tmp_path: Path,
    stop_after: ActionJournalState,
    expected_recovery: JournalRecoveryDisposition,
    contact_possible: bool,
) -> None:
    root = tmp_path / stop_after.value.lower()
    root.mkdir()
    journal = ZeroAuthorityMissionJournal.create(
        root, _occurrence(), created_at_ns=100
    )
    transitions = (
        (
            ActionJournalState.PRE_CONTACT,
            lambda: journal.commit_pre_contact(
                event_time_ns=110, route_sha256=_digest("route")
            ),
        ),
        (
            ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            lambda: journal.commit_contact_boundary(
                event_time_ns=120, command_sha256=_digest("command")
            ),
        ),
        (
            ActionJournalState.OUTCOME_CONFIRMED,
            lambda: journal.confirm_outcome(
                event_time_ns=130, outcome_sha256=_digest("outcome")
            ),
        ),
        (
            ActionJournalState.RETRACTED,
            lambda: journal.confirm_retracted(
                event_time_ns=140, feedback_sha256=_digest("retract")
            ),
        ),
        (
            ActionJournalState.PARKED,
            lambda: journal.confirm_parked(
                event_time_ns=150, feedback_sha256=_digest("park")
            ),
        ),
    )
    for state, transition in transitions:
        if stop_after is ActionJournalState.INTENT_COMMITTED:
            break
        transition()
        if state is stop_after:
            break

    restarted = load_mission_journal(journal.directory)
    assert restarted.current_state is stop_after
    assert restarted.recovery_disposition is expected_recovery
    assert restarted.contact_may_have_occurred is contact_possible
    assert restarted.automatic_contact_retry_permitted is False


def test_restart_at_contact_boundary_forbids_retry_and_marks_uncertain(
    tmp_path: Path,
) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    contact_boundary = journal.commit_contact_boundary(
        event_time_ns=120, command_sha256=_digest("contact-command")
    )

    assert contact_boundary.current_state is (
        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
    )
    assert contact_boundary.contact_may_have_occurred is True
    assert contact_boundary.contact_submission_permitted is False
    assert contact_boundary.automatic_contact_retry_permitted is False
    assert contact_boundary.recovery_disposition is (
        JournalRecoveryDisposition.CONTACT_RETRY_FORBIDDEN_OUTCOME_UNCERTAIN
    )

    reopened = ZeroAuthorityMissionJournal.open(journal.directory)
    uncertain = reopened.mark_outcome_uncertain(
        event_time_ns=130,
        detail_code="PROCESS_LOST_AFTER_CONTACT_BOUNDARY",
    )
    assert uncertain.current_state is ActionJournalState.OUTCOME_UNCERTAIN
    assert uncertain.automatic_contact_retry_permitted is False
    with pytest.raises(MissionJournalError, match="invalid journal transition"):
        reopened.commit_pre_contact(
            event_time_ns=140,
            route_sha256=_digest("retry-route"),
        )


def test_fault_after_contact_boundary_must_be_outcome_uncertain(tmp_path: Path) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    journal.commit_contact_boundary(
        event_time_ns=120, command_sha256=_digest("contact-command")
    )

    with pytest.raises(MissionJournalError, match="invalid journal transition"):
        journal.mark_faulted(
            event_time_ns=130,
            detail_code="CONTACT_RESULT_MISSING",
        )


def test_contact_boundary_cannot_be_committed_twice(tmp_path: Path) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    journal.commit_contact_boundary(
        event_time_ns=120, command_sha256=_digest("contact-command")
    )

    with pytest.raises(MissionJournalError, match="not permitted"):
        journal.commit_contact_boundary(
            event_time_ns=130,
            command_sha256=_digest("contact-command"),
        )


def test_transitions_require_monotonic_time_and_named_evidence(tmp_path: Path) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    with pytest.raises(MissionJournalError, match="strictly increase"):
        journal.commit_pre_contact(event_time_ns=100, route_sha256=_digest("route"))
    with pytest.raises(MissionJournalError, match="requires evidence"):
        journal.commit_transition(
            ActionJournalState.PRE_CONTACT,
            event_time_ns=110,
            evidence_sha256=None,
            detail_code="PRE_CONTACT_EVIDENCE_COMMITTED",
        )


def test_precontact_fault_is_terminal_and_does_not_imply_contact(tmp_path: Path) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    faulted = journal.mark_faulted(
        event_time_ns=110,
        detail_code="LOCALIZATION_REJECTED",
        evidence_sha256=_digest("localization"),
    )
    assert faulted.current_state is ActionJournalState.FAULTED
    assert faulted.contact_may_have_occurred is False
    assert faulted.recovery_disposition is (
        JournalRecoveryDisposition.MANUAL_REVIEW_REQUIRED
    )
    with pytest.raises(MissionJournalError, match="invalid journal transition"):
        journal.commit_pre_contact(event_time_ns=120, route_sha256=_digest("route"))


def test_creation_is_no_overwrite_and_one_occurrence_has_one_journal(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    occurrence = _occurrence()
    ZeroAuthorityMissionJournal.create(root, occurrence, created_at_ns=100)

    with pytest.raises(MissionJournalError, match="already exists"):
        ZeroAuthorityMissionJournal.create(root, occurrence, created_at_ns=101)


def test_tampered_event_and_unknown_file_fail_strict_reconstruction(
    tmp_path: Path,
) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    event_path = journal.directory / "event-000001.json"
    document = json.loads(event_path.read_text(encoding="utf-8"))
    document["detail_code"] = "TAMPERED"
    event_path.write_bytes(
        (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    with pytest.raises(MissionJournalError, match="event_sha256"):
        load_mission_journal(journal.directory)

    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    clean = ZeroAuthorityMissionJournal.create(
        clean_root, _occurrence(key="e"), created_at_ns=200
    )
    (clean.directory / "notes.txt").write_text("not allowed", encoding="utf-8")
    with pytest.raises(MissionJournalError, match="unexpected journal entry"):
        load_mission_journal(clean.directory)


def test_unknown_json_fields_and_noncanonical_bytes_fail(tmp_path: Path) -> None:
    root = _root(tmp_path)
    journal = ZeroAuthorityMissionJournal.create(
        root, _occurrence(), created_at_ns=100
    )
    header_path = journal.directory / "header.json"
    header = json.loads(header_path.read_text(encoding="utf-8"))
    header["unexpected"] = True
    header_path.write_bytes(
        (json.dumps(header, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    with pytest.raises(MissionJournalError, match="fields differ"):
        load_mission_journal(journal.directory)


def test_symlinked_journal_entry_is_rejected_when_supported(tmp_path: Path) -> None:
    root = _root(tmp_path)
    journal = ZeroAuthorityMissionJournal.create(
        root, _occurrence(), created_at_ns=100
    )
    target = tmp_path / "outside.json"
    target.write_text("{}\n", encoding="utf-8")
    link = journal.directory / "event-000001.json"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(MissionJournalError, match="non-file journal entry"):
        load_mission_journal(journal.directory)


def test_concurrent_writers_cannot_publish_two_events_at_one_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import rocell.application.mission_journal as journal_module

    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    first = ZeroAuthorityMissionJournal.open(journal.directory)
    second = ZeroAuthorityMissionJournal.open(journal.directory)
    barrier = threading.Barrier(2)
    original_link = os.link

    def racing_link(source: object, destination: object, *args: object, **kwargs: object) -> None:
        barrier.wait(timeout=5)
        original_link(source, destination, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(journal_module.os, "link", racing_link)
    successes: list[object] = []
    failures: list[BaseException] = []

    def advance(handle: ZeroAuthorityMissionJournal, evidence: str) -> None:
        try:
            successes.append(
                handle.commit_pre_contact(event_time_ns=110, route_sha256=evidence)
            )
        except BaseException as exc:  # capture the thread result for the assertion
            failures.append(exc)

    threads = (
        threading.Thread(target=advance, args=(first, _digest("route-a"))),
        threading.Thread(target=advance, args=(second, _digest("route-b"))),
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], MissionJournalError)
    snapshot = load_mission_journal(journal.directory)
    assert snapshot.current_state is ActionJournalState.PRE_CONTACT
    assert len(snapshot.events) == 2


@pytest.mark.parametrize("first_deleted_sequence", range(6))
def test_deleting_any_committed_terminal_suffix_fails_closed(
    tmp_path: Path,
    first_deleted_sequence: int,
) -> None:
    """A lost contact tail must never reconstruct as contact-permitted."""

    root = tmp_path / f"suffix-{first_deleted_sequence}"
    root.mkdir()
    journal = ZeroAuthorityMissionJournal.create(
        root,
        _occurrence(ordinal=first_deleted_sequence),
        created_at_ns=100,
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    journal.commit_contact_boundary(
        event_time_ns=120,
        command_sha256=_digest("contact-command"),
    )
    journal.confirm_outcome(event_time_ns=130, outcome_sha256=_digest("outcome"))
    journal.confirm_retracted(event_time_ns=140, feedback_sha256=_digest("retracted"))
    journal.confirm_parked(event_time_ns=150, feedback_sha256=_digest("parked"))

    for sequence in range(first_deleted_sequence, 6):
        (journal.directory / f"event-{sequence:06d}.json").unlink()

    with pytest.raises(
        MissionJournalError,
        match="high-water|no committed intent|sequence is not contiguous",
    ):
        load_mission_journal(journal.directory)


def test_missing_high_water_record_fails_closed(tmp_path: Path) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    (journal.directory / "high-water.json").unlink()

    with pytest.raises(MissionJournalError, match="high-water record is missing"):
        load_mission_journal(journal.directory)


@pytest.mark.parametrize("filename", ["event-000002.json", "high-water.json"])
def test_truncated_contact_tail_or_high_water_fails_closed(
    tmp_path: Path,
    filename: str,
) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    journal.commit_contact_boundary(
        event_time_ns=120,
        command_sha256=_digest("contact-command"),
    )
    path = journal.directory / filename
    path.write_bytes(path.read_bytes()[:32])

    with pytest.raises(MissionJournalError, match="invalid strict JSON"):
        load_mission_journal(journal.directory)


def test_contact_boundary_directory_sync_failure_before_head_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_journal as journal_module

    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))

    def fail_sync(_path: Path) -> None:
        raise MissionJournalError("injected directory sync failure")

    monkeypatch.setattr(journal_module, "_fsync_directory", fail_sync)
    with pytest.raises(MissionJournalError, match="injected directory sync failure"):
        journal.commit_contact_boundary(
            event_time_ns=120,
            command_sha256=_digest("contact-command"),
        )

    # The event link exists but the old high-water record cannot silently ignore
    # it and reconstruct the earlier contact-permitted state.
    with pytest.raises(MissionJournalError, match="high-water"):
        load_mission_journal(journal.directory)


def test_contact_boundary_failure_after_head_advance_never_regains_permission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_journal as journal_module

    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))
    sync_count = 0

    def fail_second_sync(_path: Path) -> None:
        nonlocal sync_count
        sync_count += 1
        if sync_count == 2:
            raise MissionJournalError("injected final directory sync failure")

    monkeypatch.setattr(journal_module, "_fsync_directory", fail_second_sync)
    with pytest.raises(MissionJournalError, match="final directory sync failure"):
        journal.commit_contact_boundary(
            event_time_ns=120,
            command_sha256=_digest("contact-command"),
        )

    restarted = load_mission_journal(journal.directory)
    assert restarted.current_state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
    assert restarted.contact_may_have_occurred is True
    assert restarted.contact_submission_permitted is False
    assert restarted.automatic_contact_retry_permitted is False


def test_append_syncs_event_before_and_high_water_after_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_journal as journal_module

    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )
    operations: list[str] = []
    original_replace = os.replace

    def observe_sync(path: Path) -> None:
        assert path == journal.directory
        operations.append("directory-fsync")

    def observe_replace(source: object, destination: object) -> None:
        operations.append("high-water-replace")
        original_replace(source, destination)  # type: ignore[arg-type]

    monkeypatch.setattr(journal_module, "_fsync_directory", observe_sync)
    monkeypatch.setattr(journal_module.os, "replace", observe_replace)
    journal.commit_pre_contact(event_time_ns=110, route_sha256=_digest("route"))

    assert operations == [
        "directory-fsync",
        "high-water-replace",
        "directory-fsync",
    ]


def test_fixed_transition_state_rejects_mismatched_detail_code(
    tmp_path: Path,
) -> None:
    journal = ZeroAuthorityMissionJournal.create(
        _root(tmp_path), _occurrence(), created_at_ns=100
    )

    with pytest.raises(MissionJournalError, match="requires detail_code"):
        journal.commit_transition(
            ActionJournalState.PRE_CONTACT,
            event_time_ns=110,
            evidence_sha256=_digest("not-route-evidence"),
            detail_code="PARK_CONFIRMED",
        )
    assert journal.snapshot().current_state is ActionJournalState.INTENT_COMMITTED
