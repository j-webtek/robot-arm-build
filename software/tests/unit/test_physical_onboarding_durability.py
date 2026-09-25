from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

import pytest

from rocell.application import physical_onboarding_durability as durability_module
from rocell.application.physical_onboarding_durability import (
    DurabilityCheckpoint,
    DurabilityQualificationError,
    DurableCommittedLedger,
    LedgerRecoveryState,
    PhysicalOnboardingDurabilityError,
    PublicationMode,
    ZERO_SHA256,
    canonical_bytes,
    load_durability_qualification_report,
    parse_durability_qualification_report,
    publish_bytes,
    require_effect_durability,
    run_on_volume_startup_self_test,
)
from rocell.application.physical_onboarding_leases import (
    windows_lockfileex_self_test,
)


SOURCE = "a" * 64


class InjectedStop(RuntimeError):
    pass


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "durability"
    root.mkdir()
    return root.resolve()


def test_immutable_and_replace_publication_are_exact(tmp_path: Path) -> None:
    root = _root(tmp_path)
    published = publish_bytes(
        root, "head.bin", b"first", mode=PublicationMode.IMMUTABLE
    )
    assert published.read_bytes() == b"first"

    with pytest.raises(PhysicalOnboardingDurabilityError, match="already exists"):
        publish_bytes(root, "head.bin", b"other", mode=PublicationMode.IMMUTABLE)

    publish_bytes(root, "head.bin", b"second", mode=PublicationMode.REPLACE)
    assert published.read_bytes() == b"second"
    assert published.stat().st_nlink == 1


@pytest.mark.skipif(os.name != "nt", reason="native sharing semantics are Windows-only")
def test_native_read_handle_allows_same_volume_replacement(tmp_path: Path) -> None:
    root = _root(tmp_path)
    published = publish_bytes(
        root, "head.bin", b"first", mode=PublicationMode.IMMUTABLE
    )
    handle = durability_module._windows_open_regular_read_handle(
        published,
        maximum_bytes=64,
        label="replacement-sharing probe",
    )
    try:
        publish_bytes(root, "head.bin", b"second", mode=PublicationMode.REPLACE)
    finally:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        assert close(handle)
    assert published.read_bytes() == b"second"


@pytest.mark.parametrize(
    "relative",
    [
        Path("../escape.bin"),
        Path("nested/../../escape.bin"),
        Path("."),
        Path("C:/escape.bin"),
    ],
)
def test_publication_rejects_traversal_and_absolute_paths(
    tmp_path: Path, relative: Path
) -> None:
    root = _root(tmp_path)
    with pytest.raises(PhysicalOnboardingDurabilityError, match="safe|escapes"):
        publish_bytes(root, relative, b"x", mode=PublicationMode.IMMUTABLE)


def test_publication_rejects_hard_linked_destination(tmp_path: Path) -> None:
    root = _root(tmp_path)
    first = root / "first.bin"
    first.write_bytes(b"first")
    second = root / "second.bin"
    try:
        os.link(first, second)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    with pytest.raises(PhysicalOnboardingDurabilityError, match="hard-linked"):
        publish_bytes(root, "second.bin", b"replacement", mode=PublicationMode.REPLACE)


def test_committed_ledger_round_trip_and_independent_head(tmp_path: Path) -> None:
    root = _root(tmp_path)
    ledger = DurableCommittedLedger.create(
        root,
        ledger_id="attempts-CELL-A",
        source_binding_sha256=SOURCE,
        qualification_sha256=ZERO_SHA256,
        created_at_ns=100,
    )
    empty = ledger.inspect()
    assert empty.recovery_state is LedgerRecoveryState.CLEAN
    assert empty.committed_records == ()

    first = ledger.append(
        "INTENT_DURABLE", {"attempt_id": "attempt-1"}, recorded_at_ns=101
    )
    second = ledger.append(
        "EFFECT_ARMED", {"attempt_id": "attempt-1"}, recorded_at_ns=102
    )
    assert [item.record_kind for item in second.committed_records] == [
        "INTENT_DURABLE",
        "EFFECT_ARMED",
    ]
    assert second.committed_records[1].previous_record_sha256 == (
        first.committed_records[0].record_sha256
    )
    head = json.loads((ledger.directory / "head.json").read_text(encoding="ascii"))
    assert head["event_count"] == 2
    assert head["committed_record_sha256"] == second.committed_records[-1].record_sha256


def test_stop_after_record_publication_is_reconciliation_only_torn_tail(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    ledger = DurableCommittedLedger.create(
        root,
        ledger_id="quarantine-CELL-A",
        source_binding_sha256=SOURCE,
        qualification_sha256=ZERO_SHA256,
        created_at_ns=100,
    )

    def inject(checkpoint: str) -> None:
        if checkpoint == DurabilityCheckpoint.LEDGER_AFTER_RECORD_PUBLISH.value:
            raise InjectedStop()

    with pytest.raises(InjectedStop):
        ledger.append(
            "QUARANTINE_LATCHED",
            {"reason": "SIDE_EFFECT_UNCERTAIN"},
            recorded_at_ns=101,
            fault_injector=inject,
        )

    recovered = DurableCommittedLedger.open(ledger.directory).inspect()
    assert recovered.recovery_state is LedgerRecoveryState.UNCOMMITTED_TAIL
    assert recovered.committed_records == ()
    assert len(recovered.uncommitted_records) == 1
    with pytest.raises(PhysicalOnboardingDurabilityError, match="reconciliation"):
        ledger.append("IGNORED", {"retry": False}, recorded_at_ns=102)


def test_stop_after_head_publication_reloads_as_committed_not_replayed(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    ledger = DurableCommittedLedger.create(
        root,
        ledger_id="attempts-CELL-B",
        source_binding_sha256=SOURCE,
        qualification_sha256=ZERO_SHA256,
        created_at_ns=100,
    )

    def inject(checkpoint: str) -> None:
        if checkpoint == DurabilityCheckpoint.LEDGER_AFTER_HEAD_PUBLISH.value:
            raise InjectedStop()

    with pytest.raises(InjectedStop):
        ledger.append(
            "INTENT_DURABLE",
            {"attempt_id": "attempt-1"},
            recorded_at_ns=101,
            fault_injector=inject,
        )
    recovered = ledger.inspect()
    assert recovered.recovery_state is LedgerRecoveryState.CLEAN
    assert [item.record_kind for item in recovered.committed_records] == [
        "INTENT_DURABLE"
    ]


def test_committed_suffix_deletion_and_head_tamper_fail_closed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    ledger = DurableCommittedLedger.create(
        root,
        ledger_id="attempts-CELL-C",
        source_binding_sha256=SOURCE,
        qualification_sha256=ZERO_SHA256,
        created_at_ns=100,
    )
    ledger.append("INTENT_DURABLE", {"attempt_id": "a"}, recorded_at_ns=101)
    (ledger.directory / "records" / "record-000000.json").unlink()
    with pytest.raises(PhysicalOnboardingDurabilityError, match="suffix is missing"):
        ledger.inspect()

    other = DurableCommittedLedger.create(
        root,
        ledger_id="attempts-CELL-D",
        source_binding_sha256=SOURCE,
        qualification_sha256=ZERO_SHA256,
        created_at_ns=200,
    )
    head_path = other.directory / "head.json"
    head = json.loads(head_path.read_text(encoding="ascii"))
    head["head_sha256"] = "f" * 64
    head_path.write_bytes(
        (
            json.dumps(head, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("ascii")
    )
    with pytest.raises(PhysicalOnboardingDurabilityError, match="head hash"):
        other.inspect()


def test_on_volume_self_test_is_source_and_root_bound(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = run_on_volume_startup_self_test(
        root,
        source_binding_sha256=SOURCE,
        lease_probe=windows_lockfileex_self_test,
        checked_at_ns=1_000,
    )
    if os.name == "nt":
        assert report.platform == "Windows"
        assert report.filesystem == "NTFS"
        assert report.qualified_for_effects is True
        assert all(item.passed for item in report.checks)
        assert (
            require_effect_durability(report, root=root, source_binding_sha256=SOURCE)
            is report
        )
    else:
        assert report.qualified_for_effects is False
        assert all(item.passed is False for item in report.checks)

    with pytest.raises(DurabilityQualificationError, match="absent"):
        require_effect_durability(None, root=root, source_binding_sha256=SOURCE)
    with pytest.raises(DurabilityQualificationError, match="source is stale"):
        require_effect_durability(report, root=root, source_binding_sha256="b" * 64)

    other_root = tmp_path / "other-volume-location"
    other_root.mkdir()
    with pytest.raises(DurabilityQualificationError, match="another root"):
        require_effect_durability(
            report, root=other_root.resolve(), source_binding_sha256=SOURCE
        )


def test_qualification_report_round_trip_is_canonical_and_strict(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    report = run_on_volume_startup_self_test(
        root,
        source_binding_sha256=SOURCE,
        checked_at_ns=1_001,
    )
    payload = canonical_bytes(report.to_dict())
    assert parse_durability_qualification_report(payload) == report
    path = root / "qualification.json"
    path.write_bytes(payload)
    assert load_durability_qualification_report(path) == report

    noncanonical = json.dumps(report.to_dict(), indent=2).encode("ascii")
    with pytest.raises(PhysicalOnboardingDurabilityError, match="canonical"):
        parse_durability_qualification_report(noncanonical)
    duplicate = payload.replace(
        b'"adapter_id":', b'"adapter_id":"forged","adapter_id":', 1
    )
    with pytest.raises(PhysicalOnboardingDurabilityError, match="duplicate"):
        parse_durability_qualification_report(duplicate)


def test_startup_self_test_rejects_caller_authored_lease_probe(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(DurabilityQualificationError, match="custom"):
        run_on_volume_startup_self_test(
            root,
            source_binding_sha256=SOURCE,
            lease_probe=lambda directory: directory.is_dir(),
            checked_at_ns=1_002,
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows volume identity is required")
def test_remote_ntfs_identity_cannot_qualify_effect_durability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(
        durability_module,
        "_windows_volume_identity",
        lambda selected: (
            "NTFS_REMOTE_UNQUALIFIED",
            "X:\\|12345678|drive=REMOTE",
        ),
    )
    report = run_on_volume_startup_self_test(
        root,
        source_binding_sha256=SOURCE,
        checked_at_ns=1_003,
    )
    assert report.filesystem == "NTFS_REMOTE_UNQUALIFIED"
    assert report.qualified_for_effects is False
    with pytest.raises(DurabilityQualificationError, match="unqualified"):
        require_effect_durability(report, root=root, source_binding_sha256=SOURCE)


def test_fault_checkpoint_before_move_does_not_publish_destination(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    seen: list[str] = []

    def inject(checkpoint: str) -> None:
        seen.append(checkpoint)
        if checkpoint == DurabilityCheckpoint.BEFORE_MOVE.value:
            raise InjectedStop()

    with pytest.raises(InjectedStop):
        publish_bytes(
            root,
            "not-published.bin",
            b"payload",
            mode=PublicationMode.IMMUTABLE,
            fault_injector=inject,
        )
    assert not (root / "not-published.bin").exists()
    assert DurabilityCheckpoint.AFTER_TEMP_FLUSH.value in seen
    assert DurabilityCheckpoint.BEFORE_MOVE.value in seen
