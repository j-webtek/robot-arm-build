"""Fast original-handoff boundaries with explicitly MODELED authentication.

The full reader, store and clock are replaced in this file only. These tests
cannot establish predecessor truth, filesystem ownership or hardware readiness.
The companion composition test runs the real complete original reader.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import camera_probe_original_scope as m
from rocell.application import physical_camera_session as session
from rocell.application.camera_probe_preparation import (
    SOURCE_WORKFLOW_PROBE_SCHEMA,
    CameraProbePreparationReview,
)
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from rocell.application.physical_onboarding_v2 import V2SessionHeader
from test_camera_mode_entry_layout import case, entry, binding
from test_camera_probe_preparation import preparation_for, attach
from test_physical_camera_session_readback import no_devices
from test_commissioning_camera_persistence import WINDOWS
from test_camera_mode_entry_persistence import predecessor
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import (
    V2StageState,
    PhysicalOnboardingV2Error,
)


@pytest.fixture
def modeled(case, tmp_path, monkeypatch):
    prep = preparation_for(case, tmp_path)
    snapshot, packages = attach(case, prep)
    plan = prep.to_dict()["plan"]
    old_header = snapshot.header
    # The prefix remains deliberately synthetic. Only the handoff's checks
    # after the modeled reader are exercised in this fast lane.
    header = V2SessionHeader.build(
        session_id=old_header.session_id,
        cell_id=old_header.cell_id,
        created_at_ns=old_header.created_at_ns,
        source_binding_sha256=m.physical_camera_source_binding(plan["source_sha256"]),
        publication_durability="PORTABLE_UNQUALIFIED",
        durability_qualification_sha256="0" * 64,
    )
    snapshot = replace(snapshot, header=header)
    records = {row["kind"]: row["record"] for row in packages.values()}
    review = CameraProbePreparationReview(m.canonical(records["review"]["document"]))
    c = SimpleNamespace(
        now=100,
        source=plan["source_sha256"],
        snapshot=snapshot,
        leases=m._leases(header.cell_id, header.session_id),
        active=True,
        audits=0,
        reads=0,
        guard_calls=0,
        guard_result=None,
        on_guard=lambda: None,
        workflow=dict(
            schema=SOURCE_WORKFLOW_PROBE_SCHEMA,
            camera_probe_preparation=dict(state="REVIEWED_FOR_ADMISSION", **records),
        ),
    )
    tx = object.__new__(m.M1PhysicalCameraTransaction)
    tx._session = SimpleNamespace(
        directory=Path(plan["assigned_parent_directory"]).parent / header.session_id
    )

    def scope():
        if not c.active:
            raise ValueError("MODELED_SCOPE_CLOSED")

    def audit(*, include_family=False):
        assert type(include_family) is bool
        scope()
        c.audits += 1
        return {}  # MODELED empty record family, matching the actual API shape.

    tx._check_scope = scope
    tx.snapshot = lambda: c.snapshot
    tx._audit_records = audit
    c.real_held_leases = type(tx).held_leases
    monkeypatch.setattr(type(tx), "held_leases", property(lambda _: c.leases))
    monkeypatch.setattr(m, "monotonic_ns", lambda: c.now)
    monkeypatch.setattr(m, "source_fingerprint", lambda _: c.source)

    def read(transaction, **kwargs):
        assert transaction is tx
        assert kwargs["camera_scope"] is kwargs["strict_workflow"] is True
        assert kwargs["bound"]["directory"] == str(tx._session.directory.parent)
        kwargs["check"](source=True)
        c.reads += 1
        return c.snapshot, deepcopy(c.workflow)

    def guard():
        c.guard_calls += 1
        c.on_guard()
        return c.guard_result

    monkeypatch.setattr(session, "_read_original_evidence_in_scope", read)
    c.tx = tx
    c.kwargs = dict(
        workspace=tmp_path,
        source_sha256=c.source,
        launch_session_id=plan["launch_session_id"],
        expected_header_sha256=header.header_sha256,
        expected_preparation_sha256=prep.sha256,
        expected_review_sha256=review.sha256,
        cancellation=Event(),
        deadline_ns=100 + m.MAX_CONTEXT_NS,
        validate_current_context=guard,
    )
    c.request = RegisteredActionRequest(
        header.cell_id,
        header.session_id,
        m.ACTION_IDS["probe"],
        "modeled-request",
        "f" * 64,
    )
    c.read = lambda **changes: m.read_camera_probe_originals(tx, **(c.kwargs | changes))
    return c


def test_cached_summary_is_detached_and_not_permission(modeled, monkeypatch):
    c = modeled
    handle = c.read()
    summary = handle.summary()
    assert summary["authenticated_at_read"] is True
    assert summary["currentness_requires_revalidation"] is True
    assert all(
        summary[name] is False
        for name in ("physical_authority", "hardware_qualified", "connected")
    )
    summary["source_sha256"] = "changed"
    monkeypatch.setattr(
        m, "source_fingerprint", lambda _: pytest.fail("display performed source I/O")
    )
    assert handle.summary()["source_sha256"] == c.source
    with pytest.raises(m.CameraProbeOriginalScopeError, match="RESTORE_FORBIDDEN"):
        replace(handle, _read_provenance=object())
    with pytest.raises(TypeError):
        m.VerifiedCameraProbeOriginal(**summary)


def test_reuse_audits_actual_scope_and_snapshot_without_full_semantic_replay(modeled):
    c = modeled
    handle = c.read()
    for _ in range(3):
        handle.assert_current(c.tx, c.request, c.snapshot)
    assert c.reads == 1
    assert c.audits == 3
    assert c.guard_calls >= 6


@pytest.mark.parametrize("value", [None, "", "g" * 64, "A" * 64, 1, True])
def test_invalid_comparison_hash_is_not_accepted(modeled, value):
    with pytest.raises(m.CameraProbeOriginalScopeError, match="HASH_REQUIRED"):
        modeled.read(expected_review_sha256=value)
    assert modeled.reads == 0


@pytest.mark.parametrize("value", [None, True, 100, -1, 300_000_000_101])
def test_original_operation_deadline_cannot_be_renewed(modeled, value):
    with pytest.raises(
        m.CameraProbeOriginalScopeError, match="BOUNDED_CONTEXT_REQUIRED"
    ):
        modeled.read(deadline_ns=value)
    assert modeled.reads == 0


@pytest.mark.parametrize(
    "role",
    ["expected_header_sha256", "expected_preparation_sha256", "expected_review_sha256"],
)
def test_valid_but_changed_hash_is_refused(modeled, role):
    with pytest.raises(m.CameraProbeOriginalScopeError):
        modeled.read(**{role: "9" * 64})


@pytest.mark.parametrize("kind", ["expiry", "clock_regression", "source"])
def test_shared_reader_source_checkpoint_honors_the_original_read_budget(modeled, kind):
    c = modeled

    def change():
        if c.guard_calls != 2:
            return
        if kind == "expiry":
            c.now = 100 + m.MAX_ORIGINAL_READ_NS
        elif kind == "clock_regression":
            c.now = 99
        else:
            c.source = "9" * 64

    c.on_guard = change
    with pytest.raises(m.CameraProbeOriginalScopeError):
        c.read()
    assert c.reads == 0


@pytest.mark.parametrize("kind", ["old_schema", "unreviewed", "other_launch"])
def test_only_this_launchs_reviewed_v16_history_can_produce_a_handoff(modeled, kind):
    c = modeled
    changes = {}
    if kind == "old_schema":
        c.workflow["schema"] = "rocell.MODELED-old-schema.v1"
    elif kind == "unreviewed":
        c.workflow["camera_probe_preparation"]["state"] = "PREPARED_REVIEW_REQUIRED"
    else:
        changes["launch_session_id"] = "wizard-" + "9" * 32
    with pytest.raises(m.CameraProbeOriginalScopeError):
        c.read(**changes)


@pytest.mark.parametrize("value", [True, False, {}, "approved"])
def test_current_context_callback_must_succeed_without_an_approval_value(
    modeled, value
):
    modeled.guard_result = value
    with pytest.raises(m.CameraProbeOriginalScopeError, match="CONTEXT_CHANGED"):
        modeled.read()
    assert modeled.reads == 0


def test_directory_is_derived_from_scoped_store_not_browser_input(modeled):
    modeled.tx._session.directory = modeled.kwargs["workspace"] / "other" / "session"
    with pytest.raises(session.PhysicalCameraSessionError):
        modeled.read()
    assert modeled.reads == 0


def test_authenticated_handoff_cannot_move_to_a_cloned_store(modeled):
    c = modeled
    handle = c.read()
    # Even identical IDs, header and evidence hashes do not own another path.
    c.tx._session.directory = (
        c.kwargs["workspace"] / "clone" / c.snapshot.header.session_id
    )
    with pytest.raises(m.CameraProbeOriginalScopeError, match="DIRECTORY_CHANGED"):
        handle.assert_current(c.tx, c.request, c.snapshot)
    assert c.reads == 1


@pytest.mark.parametrize("kind", ["stage_only", "extra", "reordered"])
def test_factory_requires_exact_camera_leases(modeled, kind):
    c = modeled
    if kind == "stage_only":
        c.leases = c.leases[:2]
    elif kind == "extra":
        c.leases += (c.leases[-1],)
    else:
        c.leases = tuple(reversed(c.leases))
    with pytest.raises(m.CameraProbeOriginalScopeError, match="STORE_CHANGED"):
        c.read()
    assert c.reads == 0


@pytest.mark.parametrize(
    "kind",
    ["stop", "expiry", "clock_regression", "source", "guard", "closed", "leases"],
)
def test_reuse_rechecks_live_context(modeled, kind):
    c = modeled
    handle = c.read()
    if kind == "stop":
        c.kwargs["cancellation"].set()
    elif kind == "expiry":
        c.now = c.kwargs["deadline_ns"]
    elif kind == "clock_regression":
        c.now -= 1
    elif kind == "source":
        c.source = "9" * 64
    elif kind == "guard":
        c.guard_result = True
    elif kind == "closed":
        c.active = False
    else:
        c.leases = c.leases[:2]
    with pytest.raises(ValueError):
        handle.assert_current(c.tx, c.request, c.snapshot)


@WINDOWS
def test_real_m1_reuse_detects_added_packages_and_changed_original_bytes(
    modeled, monkeypatch
):
    """Real NTFS/leases; ONLY the full semantic reader is deliberately modeled.

    The synthetic journal is never claimed to pass the real original verifier.
    No facts provider is allowed to run and no execution permit is requested.
    """
    c = modeled
    monkeypatch.setattr(
        m.M1PhysicalCameraTransaction, "held_leases", c.real_held_leases
    )
    assigned = c.tx._session.directory.parent
    assigned.mkdir(parents=True)
    runtime = PhysicalOnboardingM1Runtime.initialize(
        assigned,
        source_binding_sha256=m.physical_camera_source_binding(c.source),
        cell_id=c.request.cell_id,
        created_at_ns=1000,
    )
    runtime.create_session(
        c.request.session_id,
        created_at_ns=2000,
        mode="PHYSICAL_DIAGNOSTIC",
        workspace_source_sha256=c.source,
    )
    adapter = M1PhysicalCameraPersistence(
        runtime,
        workspace_source_sha256=c.source,
        admission_facts=lambda *a: pytest.fail(
            "read-only handoff requested device admission"
        ),
    )
    with adapter.stage_transaction(
        c.request.session_id,
        expected_challenge_sha256=adapter.verification(
            c.request.session_id
        ).challenge_sha256,
    ) as tx:
        predecessor(tx)
        tx.commit_stage_state(
            STAGE_ORDER[4],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=10001,
            detail_code="MODELED_ORIGINAL_SCOPE_STORAGE_ONLY",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        reference = tx.store_evidence(
            STAGE_ORDER[4],
            b"MODELED original, not hardware evidence",
            label="MODELED scope reuse payload",
            media_type="text/plain",
            captured_at_ns=10002,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        original = tx.snapshot()
    c.kwargs["expected_header_sha256"] = original.header.header_sha256

    def modeled_semantic_reader(tx, **kwargs):
        assert kwargs["camera_scope"] is kwargs["strict_workflow"] is True
        return tx.snapshot(), deepcopy(c.workflow)

    monkeypatch.setattr(
        session, "_read_original_evidence_in_scope", modeled_semantic_reader
    )
    with adapter.transaction(c.leases) as tx:
        handle = m.read_camera_probe_originals(tx, **c.kwargs)
        handle.assert_current(tx, c.request, original)
        assert (
            tx.read_camera_evidence(reference)
            == b"MODELED original, not hardware evidence"
        )
        with pytest.raises(M1CommissioningPersistenceError, match="stage-only"):
            tx.read_stage_evidence(reference)
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        handle.assert_current(tx, c.request, original)

    # A separately committed immutable package changes the real inventory even
    # without changing the visible stage, head, entry or preparation hashes.
    with adapter.stage_transaction(
        c.request.session_id,
        expected_challenge_sha256=adapter.verification(
            c.request.session_id
        ).challenge_sha256,
    ) as tx:
        tx.store_evidence(
            STAGE_ORDER[4],
            b"MODELED later package",
            label="MODELED changed inventory",
            media_type="text/plain",
            captured_at_ns=10003,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    with adapter.transaction(c.leases) as tx:
        with pytest.raises(m.CameraProbeOriginalScopeError, match="SNAPSHOT_CHANGED"):
            handle.assert_current(tx, c.request, original)
        current = tx.snapshot()
        fresh_modeled_handle = m.read_camera_probe_originals(tx, **c.kwargs)
        fresh_modeled_handle.assert_current(tx, c.request, current)

        # Corrupt only this disposable pytest fixture's payload. The actual M1
        # snapshot must re-read immutable bytes instead of trusting saved hashes.
        payload_path = (
            tx._session.directory / "evidence" / reference.evidence_id / "payload.bin"
        )
        payload_path.write_bytes(b"CORRUPTED modeled original")
        with pytest.raises(PhysicalOnboardingV2Error):
            fresh_modeled_handle.assert_current(tx, c.request, current)


@pytest.mark.parametrize("field", ["cell_id", "session_id", "action_id"])
def test_reuse_cannot_switch_action_or_session(modeled, field):
    c = modeled
    handle = c.read()
    with pytest.raises(m.CameraProbeOriginalScopeError, match="REQUEST_CHANGED"):
        handle.assert_current(
            c.tx, replace(c.request, **{field: "different"}), c.snapshot
        )


@pytest.mark.parametrize("field", ["head", "evidence", "uncommitted_events"])
def test_snapshot_comparison_includes_history_and_full_inventory(modeled, field):
    c = modeled
    handle = c.read()
    if field == "head":
        changed = replace(c.snapshot.head, head_sha256="9" * 64)
    elif field == "evidence":
        changed = c.snapshot.evidence[:-1]
    else:
        changed = (c.snapshot.committed_events[-1],)
    c.snapshot = replace(c.snapshot, **{field: changed})
    with pytest.raises(m.CameraProbeOriginalScopeError, match="SNAPSHOT_CHANGED"):
        handle.assert_current(c.tx, c.request, c.snapshot)


def test_supplied_snapshot_cannot_hide_changed_store(modeled):
    c = modeled
    handle = c.read()
    original = c.snapshot
    c.snapshot = replace(original, evidence=original.evidence[:-1])
    with pytest.raises(m.CameraProbeOriginalScopeError, match="SNAPSHOT_CHANGED"):
        handle.assert_current(c.tx, c.request, original)


@pytest.mark.parametrize("kind", ["source", "stop", "closed", "leases"])
def test_context_change_during_final_guard_is_refused(modeled, kind):
    c = modeled
    handle = c.read()
    calls = 0

    def change():
        nonlocal calls
        calls += 1
        if calls != 2:
            return
        if kind == "source":
            c.source = "9" * 64
        elif kind == "stop":
            c.kwargs["cancellation"].set()
        elif kind == "closed":
            c.active = False
        else:
            c.leases = c.leases[:2]

    c.on_guard = change
    with pytest.raises(ValueError):
        handle.assert_current(c.tx, c.request, c.snapshot)
