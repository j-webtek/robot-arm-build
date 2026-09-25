"""Pending camera M1 sessions, actual NTFS storage and no device/process calls."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import os
import threading
from typing import Any

import pytest

import rocell.application.physical_camera_session as module
from rocell.application.physical_camera_session import (
    PhysicalCameraSession,
    PhysicalCameraSessionError,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

SOURCE = "a" * 64
LAUNCH = "wizard-" + "1" * 32
CELL = "wizard-physical-camera-" + "b" * 16
SESSION = "physical-camera-" + "c" * 32
WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="actual qualified Windows/NTFS storage"
)


@pytest.fixture(autouse=True)
def no_device_or_process(monkeypatch: pytest.MonkeyPatch):
    import subprocess

    def denied(*args: Any, **kwargs: Any):
        pytest.fail(
            "camera session storage must not execute a process or access devices"
        )

    monkeypatch.setattr(subprocess, "Popen", denied)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, denied)


def session_fixture(tmp_path: Path) -> PhysicalCameraSession:
    """Inert source-fixed owner; caller explicitly creates software if desired."""
    return PhysicalCameraSession(
        tmp_path,
        tmp_path / "software/runs/physical-camera-acquisition" / LAUNCH,
        launch_id=LAUNCH,
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
    )


def actual_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "software").mkdir()
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)
    return session_fixture(tmp_path)


def perform(
    owner: PhysicalCameraSession, name="initialize", *, cancellation=None, progress=None
):
    return getattr(owner, name)(
        cancellation=cancellation or threading.Event(),
        progress=progress or (lambda _: None),
    )


def assert_view_flags(view):
    assert set(view) == {
        "schema",
        "binding",
        "status",
        "operation",
        "verification",
        "stages",
        "error",
        "partial_store_possible",
        "initialize_attempted",
        "physical_authority",
        "device_io_performed",
        "hardware_qualified",
        "replay_allowed",
    }
    assert view["schema"] == "rocell.physical_camera_session_view.v1"
    for name in (
        "physical_authority",
        "device_io_performed",
        "hardware_qualified",
        "replay_allowed",
    ):
        assert view[name] is False


def test_constructor_and_cached_views_are_inert_detached_and_entirely_unstarted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def denied(*args: Any, **kwargs: Any):
        pytest.fail("constructor or cached view performed filesystem/source activity")

    with monkeypatch.context() as patch:
        for method in (
            "open",
            "stat",
            "lstat",
            "mkdir",
            "resolve",
            "exists",
            "iterdir",
        ):
            patch.setattr(Path, method, denied)
        patch.setattr(module, "source_fingerprint", denied)
        owner = session_fixture(tmp_path)
        view = owner.view()
        assert_view_flags(view)
        assert view["status"] == "NOT_INITIALIZED" and view["operation"] is None
        assert view["verification"] is None and view["stages"] is None
        assert view["initialize_attempted"] is False
        assert owner.retained_verification() is None
        view["binding"]["source_sha256"] = "f" * 64
        descriptor = owner.descriptor()
        descriptor["directory"] = "other"
        assert owner.descriptor()["source_sha256"] == SOURCE
        assert owner.descriptor()["directory"] != "other"


@pytest.mark.parametrize("value", [True, False, 0, -1, 2**63, "later", 1.5])
def test_refresh_rejects_invalid_parent_deadline_before_claiming_owner(tmp_path, value):
    owner = session_fixture(tmp_path)
    before = owner.view()
    with pytest.raises(PhysicalCameraSessionError, match="READBACK_DEADLINE_INVALID"):
        owner.refresh(
            cancellation=threading.Event(), progress=lambda _: None, deadline_ns=value
        )
    assert owner.view() == before


@pytest.mark.parametrize("parent", [100, 1000, 10**15])
def test_refresh_parent_only_shortens_existing_budget(tmp_path, monkeypatch, parent):
    owner = session_fixture(tmp_path)
    times = iter([100, min(parent, 100 + module.DIAGNOSTIC_TIMEOUT_NS)])
    monkeypatch.setattr(module, "monotonic_ns", lambda: next(times))

    def denied(*args, **kwargs):
        pytest.fail("expired refresh reached source/storage I/O")

    monkeypatch.setattr(module, "source_fingerprint", denied)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "open", denied)
    with pytest.raises(PhysicalCameraSessionError, match="TIMED_OUT"):
        owner.refresh(
            cancellation=threading.Event(), progress=lambda _: None, deadline_ns=parent
        )
    assert owner.view()["status"] == "HELD"
    assert owner._store is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "0" * 64),
        ("source_sha256", True),
        ("launch_id", "launch"),
        ("cell_id", "wizard-rehearsal-" + "b" * 16),
        ("session_id", "rehearsal-" + "c" * 32),
        ("directory", Path("C:\\")),
        ("directory", Path("relative")),
        ("directory", Path(r"\\server\share\folder")),
        ("directory", Path(r"C:\somewhere\different")),
    ],
)
def test_exact_server_directory_source_and_camera_namespace_required(
    tmp_path: Path, field: str, value: Any
):
    selected = session_fixture(tmp_path).descriptor()
    selected["workspace"], selected["directory"] = Path(selected["workspace"]), Path(
        selected["directory"]
    )
    selected[field] = value
    with pytest.raises((ValueError, RuntimeError)):
        PhysicalCameraSession(**selected)


@pytest.mark.parametrize("phase", ["before", "first-progress"])
def test_stop_before_store_creation_is_one_use_and_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
):
    owner = session_fixture(tmp_path)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)
    monkeypatch.setattr(
        PhysicalOnboardingM1Runtime,
        "initialize",
        lambda *a, **k: pytest.fail("cancelled initialize reached M1"),
    )
    event = threading.Event()
    if phase == "before":
        event.set()
    with pytest.raises(PhysicalCameraSessionError, match="CANCELLED"):
        perform(owner, cancellation=event, progress=lambda _: event.set())
    view = owner.view()
    assert view["status"] == "HELD" and view["initialize_attempted"] is True
    assert view["partial_store_possible"] is False
    assert not Path(owner.descriptor()["directory"]).exists()
    with pytest.raises(PhysicalCameraSessionError, match="ALREADY_ATTEMPTED"):
        perform(owner)


def test_source_drift_refused_before_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = session_fixture(tmp_path)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: "f" * 64)
    with pytest.raises(PhysicalCameraSessionError, match="SOURCE_CHANGED"):
        perform(owner)
    assert owner.view()["error"] == {
        "code": "CAMERA_SESSION_SOURCE_CHANGED",
        "type": "PhysicalCameraSessionError",
    }
    assert not Path(owner.descriptor()["directory"]).exists()


def test_public_error_class_cannot_emit_arbitrary_callback_private_codes(
    tmp_path, monkeypatch
):
    owner = session_fixture(tmp_path)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)

    def progress(_: str):
        raise PhysicalCameraSessionError("private token=fixture")

    with pytest.raises(
        PhysicalCameraSessionError, match="CAMERA_SESSION_STORAGE_FAILED"
    ):
        perform(owner, progress=progress)
    assert owner.view()["error"] == {
        "code": "CAMERA_SESSION_STORAGE_FAILED",
        "type": "PhysicalCameraSessionError",
    }
    assert "token" not in str(owner.view())


def test_original_120s_deadline_is_not_refreshed_by_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = session_fixture(tmp_path)
    now = [100]
    monkeypatch.setattr(module, "monotonic_ns", lambda: now[0])
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)

    def progress(_: str):
        now[0] += module.DIAGNOSTIC_TIMEOUT_NS

    with pytest.raises(PhysicalCameraSessionError, match="TIMED_OUT"):
        perform(owner, progress=progress)
    assert not Path(owner.descriptor()["directory"]).exists()
    assert owner.view()["partial_store_possible"] is False


def test_concurrent_action_is_denied_without_overwriting_running_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = session_fixture(tmp_path)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)
    entered, released, cancellation = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )

    def progress(_: str):
        entered.set()
        assert released.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            perform, owner, cancellation=cancellation, progress=progress
        )
        assert entered.wait(5)
        assert owner.view()["status"] == "RUNNING"
        with pytest.raises(PhysicalCameraSessionError, match="OPERATION_ACTIVE"):
            perform(owner, "refresh")
        assert owner.view()["operation"] == "INITIALIZE"
        cancellation.set()
        released.set()
        with pytest.raises(PhysicalCameraSessionError, match="CANCELLED"):
            future.result(5)
    assert not Path(owner.descriptor()["directory"]).exists()


def test_arbitrary_error_messages_and_class_names_do_not_escape_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = session_fixture(tmp_path)
    monkeypatch.setattr(module, "source_fingerprint", lambda *a: SOURCE)
    unsafe = type("PrivateEndpoint" * 200, (Exception,), {})

    def fail(_: str):
        raise unsafe("secret-token=do-not-render")

    with pytest.raises(PhysicalCameraSessionError):
        perform(owner, progress=fail)
    assert owner.view()["error"] == {
        "code": "CAMERA_SESSION_STORAGE_FAILED",
        "type": "Exception",
    }
    assert "secret-token" not in str(owner.view())


def test_facts_remain_denied_and_stage_access_needs_current_open(tmp_path: Path):
    owner = session_fixture(tmp_path)
    with pytest.raises(
        M1CommissioningPersistenceError, match="TRUSTED_CAMERA_ADMISSION_FACTS_REQUIRED"
    ):
        module._denied_facts(None, None)
    with pytest.raises(PhysicalCameraSessionError, match="CURRENT_OPEN_REQUIRED"):
        with owner.stage_transaction(expected_challenge_sha256="a" * 64):
            pytest.fail("unopened session exposed stage transaction")


@WINDOWS
def test_actual_initialize_pending_stage_scope_refresh_and_original_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = actual_fixture(tmp_path, monkeypatch)
    initial = perform(owner)
    assert_view_flags(initial)
    assert initial["status"] == "STORAGE_READY_PENDING"
    assert [row["stage"] for row in initial["stages"]] == [
        stage.value for stage in STAGE_ORDER
    ]
    assert all(
        row["state"] == "PENDING"
        and not row["evidence_ids"]
        and row["last_event_sequence"] is None
        for row in initial["stages"]
    )
    verification = initial["verification"]
    assert verification["qualification"]["qualified_windows_ntfs"] is True
    assert verification["attempt_ledger"]["event_count"] == 0
    assert verification["quarantine"]["event_count"] == 0
    assert verification["authority"]["device_io_authorized"] is False
    assert owner.retained_verification()["stages"] == initial["stages"]
    store = owner._store
    assert type(store) is M1PhysicalCameraPersistence
    leases = (
        LeaseSpec(LeaseLevel.CELL, CELL),
        LeaseSpec(LeaseLevel.SESSION, SESSION),
        LeaseSpec(LeaseLevel.CAMERA, CELL),
    )
    with store.transaction(leases) as tx:
        with pytest.raises(
            M1CommissioningPersistenceError,
            match="TRUSTED_CAMERA_ADMISSION_FACTS_REQUIRED",
        ):
            tx.read_admission(
                RegisteredActionRequest(CELL, SESSION, "no-camera", "never", "a" * 64)
            )
    # No fake predecessor PASS is created to obtain this stage-only scope.
    with owner.stage_transaction(
        expected_challenge_sha256=store.verification(SESSION).challenge_sha256
    ) as tx:
        assert type(tx) is M1PhysicalCameraTransaction
        assert tx.held_leases == leases[:2]
        assert not tx._audit_records()
        snapshot = tx.snapshot()
        assert not snapshot.committed_events and not snapshot.evidence
        with pytest.raises(M1CommissioningPersistenceError, match="admission policy"):
            tx.read_admission(
                RegisteredActionRequest(CELL, SESSION, "no-camera", "never", "a" * 64)
            )
    assert owner.view()["status"] == "HELD"
    assert owner.view()["error"]["code"] == "CAMERA_SESSION_REFRESH_REQUIRED"
    with pytest.raises(M1CommissioningPersistenceError, match="scope"):
        tx.snapshot()
    refreshed = perform(owner, "refresh")
    assert refreshed["status"] == "REFRESHED_STORAGE_ONLY"
    assert refreshed["stages"] == initial["stages"]
    assert refreshed["verification"]["attempt_ledger"] == verification["attempt_ledger"]
    assert refreshed["verification"]["session"] == verification["session"]
    # An inert fresh owner uses exactly the original assigned path and source.
    fresh = session_fixture(tmp_path)
    assert fresh.view()["status"] == "NOT_INITIALIZED"
    reopened = perform(fresh, "refresh")
    assert reopened["stages"] == initial["stages"]
    with pytest.raises(PhysicalCameraSessionError, match="ALREADY_ATTEMPTED"):
        perform(fresh)
    assert reopened["initialize_attempted"] is False
    assert fresh.retained_verification()["binding"] == owner.descriptor()


@WINDOWS
def test_existing_path_never_overwritten_and_refresh_never_initializes_missing_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = actual_fixture(tmp_path, monkeypatch)
    target = Path(owner.descriptor()["directory"])
    target.mkdir(parents=True)
    sentinel = target / "operator-existing.txt"
    sentinel.write_bytes(b"preserve this original path")
    monkeypatch.setattr(
        PhysicalOnboardingM1Runtime,
        "initialize",
        lambda *a, **k: pytest.fail("existing store reinitialized"),
    )
    with pytest.raises(PhysicalCameraSessionError):
        perform(owner)
    assert sentinel.read_bytes() == b"preserve this original path"
    assert owner.view()["partial_store_possible"] is True
    with pytest.raises(PhysicalCameraSessionError):
        perform(owner, "refresh")
    assert set(p.name for p in target.iterdir()) == {sentinel.name}


@WINDOWS
@pytest.mark.parametrize("fault", ["cancel", "source", "deadline", "create-session"])
def test_partial_initialized_cell_is_preserved_no_automatic_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
):
    owner = actual_fixture(tmp_path, monkeypatch)
    original = PhysicalOnboardingM1Runtime.initialize
    count = []
    cancellation = threading.Event()
    now = [100]
    if fault == "deadline":
        monkeypatch.setattr(module, "monotonic_ns", lambda: now[0])

    def initialize(*args: Any, **kwargs: Any):
        runtime = original(*args, **kwargs)
        count.append(runtime)
        if fault == "cancel":
            cancellation.set()
        elif fault == "source":
            monkeypatch.setattr(module, "source_fingerprint", lambda *a: "f" * 64)
        elif fault == "deadline":
            now[0] += module.DIAGNOSTIC_TIMEOUT_NS
        return runtime

    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "initialize", initialize)
    if fault == "create-session":
        monkeypatch.setattr(
            PhysicalOnboardingM1Runtime,
            "create_session",
            lambda *a, **k: (_ for _ in ()).throw(
                OSError("session publication fixture")
            ),
        )
    with pytest.raises(PhysicalCameraSessionError):
        perform(owner, cancellation=cancellation)
    assert len(count) == 1
    target = Path(owner.descriptor()["directory"])
    assert (target / "durability-anchor.json").is_file()
    assert (target / "cells").is_dir()
    assert (
        owner.view()["status"] == "HELD"
        and owner.view()["partial_store_possible"] is True
    )
    assert owner.retained_verification() is None
    with pytest.raises(PhysicalCameraSessionError, match="ALREADY_ATTEMPTED"):
        perform(owner)
    assert len(count) == 1


@WINDOWS
@pytest.mark.parametrize("fault", ["cancel", "source", "progress-error"])
def test_late_hold_preserves_full_verified_history_without_current_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
):
    owner = actual_fixture(tmp_path, monkeypatch)
    cancellation = threading.Event()

    def progress(message: str):
        if message.startswith("Original camera-only store verified"):
            if fault == "cancel":
                cancellation.set()
            elif fault == "source":
                monkeypatch.setattr(module, "source_fingerprint", lambda *a: "f" * 64)
            else:
                raise ValueError("private callback failure")

    with pytest.raises(PhysicalCameraSessionError):
        perform(owner, cancellation=cancellation, progress=progress)
    assert owner.view()["status"] == "HELD"
    assert owner.view()["verification"] is None and owner.view()["stages"] is None
    historical = owner.retained_verification()
    assert set(historical) == {"binding", "verification", "stages"}
    assert historical["verification"]["attempt_ledger"]["event_count"] == 0
    assert all(row["state"] == "PENDING" for row in historical["stages"])
    historical["stages"][0]["state"] = "PASS"
    assert owner.retained_verification()["stages"][0]["state"] == "PENDING"


@WINDOWS
def test_refresh_audits_camera_record_corruption_without_repair_or_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = actual_fixture(tmp_path, monkeypatch)
    initialized = perform(owner)
    key = initialized["verification"]["cell"]["cell_key_sha256"]
    record_root = (
        Path(owner.descriptor()["directory"])
        / "cells"
        / ("cell-" + key)
        / "physical-camera-records"
    )
    record_root.mkdir()
    unexpected = record_root / "unfinished-record.json"
    unexpected.write_bytes(b'{"partial":true}')
    with pytest.raises(PhysicalCameraSessionError):
        perform(owner, "refresh")
    assert unexpected.read_bytes() == b'{"partial":true}'
    assert owner.view()["status"] == "HELD"
    assert owner.retained_verification()["verification"] == initialized["verification"]


@WINDOWS
def test_post_lease_changed_head_cannot_mix_old_stages_with_new_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    owner = actual_fixture(tmp_path, monkeypatch)
    original = M1PhysicalCameraPersistence.verification
    seen = []

    def verification(store, session_id):
        result = original(store, session_id)
        seen.append(result)
        return (
            result if len(seen) == 1 else replace(result, session_head_sha256="f" * 64)
        )

    monkeypatch.setattr(M1PhysicalCameraPersistence, "verification", verification)
    with pytest.raises(PhysicalCameraSessionError, match="CHANGED_AFTER_AUDIT"):
        perform(owner)
    assert len(seen) == 2
    assert owner.retained_verification() is None
    assert owner.view()["status"] == "HELD"
