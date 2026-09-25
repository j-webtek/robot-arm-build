"""Fresh original reads without cached snapshots or hardware effects.

V2 cases use actual temporary files. M1 cases use actual qualified NTFS storage
and the existing explicitly modeled zero-I/O intent fixture, never a device
permit, process, provider or consumed campaign.
"""

from dataclasses import replace
import os

import pytest

from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Error
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.physical_onboarding_quarantine import (
    PhysicalOnboardingQuarantineLedger,
)
from test_physical_onboarding_m1 import _binding, _runtime, _unguarded_ledgers


def portable(tmp_path):
    return v2.PhysicalOnboardingV2Session.create(
        tmp_path,
        session_id="session-1",
        cell_id="cell-a",
        source_binding_sha256="a" * 64,
        created_at_ns=1_000,
    )


def count_loads(monkeypatch):
    original = v2.load_physical_onboarding_v2_session
    calls = []

    def counted(directory):
        calls.append(directory)
        return original(directory)

    monkeypatch.setattr(v2, "load_physical_onboarding_v2_session", counted)
    return calls


def test_open_with_snapshot_and_legacy_open_each_load_once(tmp_path, monkeypatch):
    original = portable(tmp_path)
    expected = original.snapshot()
    calls = count_loads(monkeypatch)
    opened, snapshot = v2.PhysicalOnboardingV2Session.open_with_snapshot(
        original.directory
    )
    assert calls == [original.directory]
    assert opened == original and snapshot == expected
    calls.clear()
    assert v2.PhysicalOnboardingV2Session.open(original.directory) == original
    assert calls == [original.directory]


def test_returned_snapshot_does_not_cache_later_original_reads(tmp_path, monkeypatch):
    original = portable(tmp_path)
    opened, before = v2.PhysicalOnboardingV2Session.open_with_snapshot(
        original.directory
    )
    changed = original.commit_stage_state(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        v2.V2StageState.WAITING_OPERATOR,
        occurred_at_ns=1_001,
        detail_code="WAITING_FOR_OPERATOR",
        expected_head_sha256=before.head.head_sha256,
    )
    calls = count_loads(monkeypatch)
    current = opened.snapshot()
    assert calls == [original.directory]
    assert current == changed and current != before
    assert before.head.event_count == 0 and current.head.event_count == 1


@pytest.mark.parametrize("method", ["open", "open_with_snapshot"])
@pytest.mark.parametrize("target", ["header.json", f"journal/{v2._HEAD_FILENAME}"])
def test_malformed_originals_are_not_hidden_by_open_snapshot(tmp_path, method, target):
    original = portable(tmp_path)
    # Deliberately corrupt only this isolated test original.
    path = original.directory / target
    path.write_bytes(b"{malformed original}")
    with pytest.raises(v2.PhysicalOnboardingV2Error):
        getattr(v2.PhysicalOnboardingV2Session, method)(original.directory)


@pytest.mark.parametrize("method", ["open", "open_with_snapshot"])
def test_publication_mismatch_is_still_refused(tmp_path, method):
    original = portable(tmp_path)
    # Model an incompatible publisher, never used for a write or M1 admission.
    publication = v2.PortableSessionPublication()
    object.__setattr__(publication, "effectful_durability_qualified", True)
    object.__setattr__(publication, "durability_qualification_sha256", "b" * 64)
    with pytest.raises(v2.PhysicalOnboardingV2Error, match="provenance"):
        getattr(v2.PhysicalOnboardingV2Session, method)(
            original.directory, publication=publication
        )


@pytest.mark.parametrize("method", ["open", "open_with_snapshot"])
def test_invalid_publication_and_non_directory_still_refused(tmp_path, method):
    original = portable(tmp_path)
    with pytest.raises(TypeError, match="publication"):
        getattr(v2.PhysicalOnboardingV2Session, method)(
            original.directory, publication=object()
        )
    with pytest.raises(v2.PhysicalOnboardingV2Error):
        getattr(v2.PhysicalOnboardingV2Session, method)(
            original.directory / "header.json"
        )


@pytest.fixture
def real_runtime(tmp_path):
    if os.name != "nt":
        pytest.skip("actual qualified M1 storage requires Windows NTFS")
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    return runtime


def add_modeled_zero_io_intent(runtime):
    attempts, quarantine = _unguarded_ledgers(runtime)
    attempts.begin_attempt(
        _binding(runtime, attempt_id="attempt-1", intent_at_ns=3_000), quarantine
    )


def test_m1_helper_loads_once_and_checks_real_original_header(
    real_runtime, monkeypatch
):
    calls = count_loads(monkeypatch)
    session, snapshot = real_runtime._open_session_with_snapshot("session-1")
    assert calls == [session.directory]
    assert snapshot.header.session_id == "session-1"
    assert snapshot.header.cell_id == real_runtime.cell.cell_id
    assert snapshot.header.source_binding_sha256 == real_runtime.source_binding_sha256
    assert (
        snapshot.header.durability_qualification_sha256
        == real_runtime.qualification_anchor.report_sha256
    )


def test_m1_verify_keeps_two_fresh_passes_and_double_global_heads(
    real_runtime, monkeypatch
):
    add_modeled_zero_io_intent(real_runtime)
    calls = count_loads(monkeypatch)
    pairs = []
    original = PhysicalOnboardingQuarantineLedger.verified_snapshots

    def counted(ledger, attempts):
        pairs.append(ledger)
        return original(ledger, attempts)

    monkeypatch.setattr(
        PhysicalOnboardingQuarantineLedger, "verified_snapshots", counted
    )
    verified = real_runtime.verify("session-1")
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert len(pairs) == 2
    assert verified.unresolved_attempt_ids == ("attempt-1",)
    assert verified.effects_allowed is False


@pytest.mark.parametrize("changed", ["cell", "source", "qualification"])
def test_m1_new_helper_rejects_runtime_header_mismatch(real_runtime, changed):
    if changed == "cell":
        other = replace(real_runtime, cell=replace(real_runtime.cell, cell_id="cell-b"))
    elif changed == "source":
        other = replace(real_runtime, source_binding_sha256="b" * 64)
    else:
        # Model a different, internally valid report; this never becomes a
        # publisher or authorizes an effect. The original header must reject it.
        core = real_runtime.qualification_anchor.core_dict()
        core["checked_at_ns"] += 1
        other = replace(
            real_runtime,
            qualification_anchor=replace(
                real_runtime.qualification_anchor,
                checked_at_ns=core["checked_at_ns"],
                report_sha256=canonical_sha256(core),
            ),
        )
    with pytest.raises(PhysicalOnboardingM1Error, match="does not belong"):
        other._open_session_with_snapshot("session-1")


def test_m1_new_helper_rejects_other_requested_session(real_runtime, monkeypatch):
    directory = real_runtime._session_path("session-1")
    monkeypatch.setattr(
        type(real_runtime), "_session_path", lambda self, selected: directory
    )
    with pytest.raises(PhysicalOnboardingM1Error, match="does not belong"):
        real_runtime._open_session_with_snapshot("session-2")


def test_second_m1_observation_does_not_reuse_first_valid_snapshot(
    real_runtime, monkeypatch
):
    add_modeled_zero_io_intent(real_runtime)
    original = v2.load_physical_onboarding_v2_session
    calls = []

    def changed_between_observations(directory):
        calls.append(directory)
        if len(calls) == 2:
            # Deliberate isolated corruption between independent full reads.
            (directory / "header.json").write_bytes(b"{changed after first read}")
        return original(directory)

    monkeypatch.setattr(
        v2, "load_physical_onboarding_v2_session", changed_between_observations
    )
    with pytest.raises(v2.PhysicalOnboardingV2Error):
        real_runtime.verify("session-1")
    assert len(calls) == 2
