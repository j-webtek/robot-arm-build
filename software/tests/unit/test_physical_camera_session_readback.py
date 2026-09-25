"""Bounded original restart readback; pure scope models plus isolated real M1.

No device/native/process calls. Pure tests model only storage ownership and
manifest observations; the actual Windows test verifies the original package,
header, immutable bytes and lease path without passing a physical stage.
"""

from contextlib import contextmanager, nullcontext
from dataclasses import replace
import os
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import pytest

import rocell.application.physical_camera_session as module
from rocell.application.physical_camera_prerequisites import (
    collect_physical_camera_prerequisites,
)
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from test_physical_camera_prerequisites import workspace
from test_physical_camera_session import (
    session_fixture,
    SOURCE,
    SESSION,
    LAUNCH,
    CELL,
    perform,
)

HEADER = "b" * 64


@pytest.fixture(autouse=True)
def no_devices(monkeypatch):
    import subprocess

    def denied(*args, **kwargs):
        pytest.fail("original requirements readback accessed a device/process")

    monkeypatch.setattr(subprocess, "Popen", denied)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, denied)


def generate(workspace, **changes):
    kwargs = dict(source_sha256=SOURCE, session_id=SESSION, launch_session_id=LAUNCH)
    kwargs.update(changes)
    return collect_physical_camera_prerequisites(
        workspace,
        **kwargs,
        cancellation=threading.Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )


def read(owner, *, expected_header_sha256=HEADER, **kwargs):
    return owner.read_original_prerequisites(
        expected_header_sha256=expected_header_sha256,
        cancellation=kwargs.pop("cancellation", threading.Event()),
        progress=kwargs.pop("progress", lambda _: None),
        **kwargs,
    )


@pytest.fixture
def model(workspace, monkeypatch):
    artifact, owner = generate(workspace), session_fixture(workspace)
    state = dict(
        manifests={},
        payloads={},
        references=[],
        verification_calls=0,
        reads=0,
        enters=0,
        exits=0,
        audit=0,
        source=SOURCE,
        now=100,
        after_change=None,
        exit_failure=False,
    )

    def add(
        payload,
        *,
        label=module.PREREQUISITE_LABEL,
        stage=STAGE_ORDER[0],
        media="application/json",
    ):
        index = len(state["references"]) + 1
        package_hash = f"{index:064x}"
        raw_manifest = canonical({"label": label, "media_type": media})
        ref = EvidenceReference(
            "evidence-" + package_hash,
            stage,
            package_hash,
            digest(raw_manifest),
            digest(payload),
            len(payload),
        )
        state["references"].append(ref)
        state["manifests"][ref.evidence_id] = raw_manifest
        state["payloads"][ref.evidence_id] = payload
        return ref

    add(artifact.payload)
    state["add"] = add

    def snapshot():
        return SimpleNamespace(
            header=SimpleNamespace(header_sha256=HEADER),
            head=SimpleNamespace(head_sha256="c" * 64),
            # This prerequisite-only model has no later-stage journal suffix.
            committed_events=(),
            evidence=tuple(state["references"]),
            stages=tuple(
                SimpleNamespace(
                    to_dict=lambda stage=stage, i=i: {
                        "stage": stage.value,
                        "state": "WAITING_OPERATOR" if i == 0 else "PENDING",
                        "last_event_sequence": 0 if i == 0 else None,
                        "evidence_ids": [],
                    }
                )
                for i, stage in enumerate(STAGE_ORDER)
            ),
        )

    def verification(_):
        state["verification_calls"] += 1
        value = SimpleNamespace(
            session_header_sha256=HEADER,
            session_head_sha256="c" * 64,
            evidence_inventory_sha256=canonical_sha256(
                [ref.to_dict() for ref in state["references"]]
            ),
            attempt_head_sha256="d" * 64,
            quarantine_head_sha256="e" * 64,
            challenge_sha256="f" * 64,
        )
        if state["verification_calls"] > 1 and state["after_change"]:
            setattr(value, state["after_change"], "9" * 64)
        value.to_dict = lambda: {
            "session": {
                "header_sha256": value.session_header_sha256,
                "head_sha256": value.session_head_sha256,
                "evidence_inventory_sha256": value.evidence_inventory_sha256,
            },
            "effects_allowed_by_m1_storage": True,
            "challenge_sha256": value.challenge_sha256,
        }
        return value

    tx = object.__new__(module.M1PhysicalCameraTransaction)
    tx._session = SimpleNamespace(directory=workspace / "modeled-original")
    tx.snapshot = snapshot

    def audit(*, include_family=False):
        assert type(include_family) is bool
        state["audit"] += 1
        return {}  # MODELED empty record family, not original campaign evidence.

    def payload_read(ref):
        assert ref in state["references"]
        state["reads"] += 1
        return state["payloads"][ref.evidence_id]

    tx._audit_records, tx.read_stage_evidence = audit, payload_read

    @contextmanager
    def modeled_readback(*, camera_scope):
        # This fixture models storage, inventories and leases deliberately. The
        # real batch scope is covered separately with fresh NTFS originals; do
        # not relabel this adaptation as persistence/performance evidence.
        assert type(camera_scope) is bool
        yield tx.snapshot(), (
            tx.read_camera_evidence if camera_scope else tx.read_stage_evidence
        )

    tx._original_evidence_readback = modeled_readback
    state["transaction"] = tx
    monkeypatch.setattr(
        module.M1PhysicalCameraTransaction,
        "held_leases",
        property(
            lambda _: (
                LeaseSpec(LeaseLevel.CELL, CELL),
                LeaseSpec(LeaseLevel.SESSION, SESSION),
            )
        ),
    )

    @contextmanager
    def transaction(*args, **kwargs):
        state["enters"] += 1
        try:
            yield tx
        finally:
            state["exits"] += 1
            if state["exit_failure"]:
                raise RuntimeError("modeled lease cleanup failure")

    store = object.__new__(module.M1PhysicalCameraPersistence)
    store.stage_transaction, store.verification = transaction, verification
    owner._store = store
    owner._cached.update(
        status="REFRESHED_STORAGE_ONLY", verification={"model": "INCAPABLE_STORAGE"}
    )
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(module, "_directory_guard", lambda _: nullcontext())
    monkeypatch.setattr(
        module,
        "read_bounded_regular_file",
        lambda path, **kwargs: state["manifests"][path.parent.name],
    )
    return owner, artifact, state


def test_pure_original_document_is_detached_and_no_stage_effect_is_exposed(model):
    owner, artifact, state = model
    result = read(owner)
    assert result == {
        "document": artifact.to_dict(),
        "evidence_sha256": artifact.evidence_sha256,
        "retention": "M1_FULL_BYTES_READ_BACK",
        "reference": state["references"][0].to_dict(),
    }
    assert state["enters"] == state["exits"] == state["reads"] == state["audit"] == 1
    assert state["verification_calls"] == 2
    result["document"]["physical_authority"] = True
    assert owner.retained_prerequisites()["document"]["physical_authority"] is False
    owner.retained_prerequisites()["reference"]["payload_bytes"] = 1
    assert owner.retained_prerequisites()["reference"]["payload_bytes"] == len(
        artifact.payload
    )
    assert owner.view()["status"] == "REFRESHED_STORAGE_ONLY"
    assert (
        owner.view()["physical_authority"]
        is owner.view()["hardware_qualified"]
        is False
    )


@pytest.mark.parametrize("kind", ["none", "other-label", "other-stage"])
def test_genuinely_absent_requirements_are_not_substituted_from_other_documents(
    model, kind
):
    owner, _, state = model
    state["references"].clear()
    if kind == "other-label":
        state["add"](b"{}", label="unrelated diagnostic")
    elif kind == "other-stage":
        state["add"](b"{}", stage=STAGE_ORDER[1])
    assert read(owner) is None
    assert state["reads"] == 0 and owner.retained_prerequisites() is None


@pytest.mark.parametrize(
    "fault",
    ["duplicate", "malformed", "wrong-schema", "media", "oversize", "manifest-hash"],
)
def test_ambiguous_or_malformed_matching_document_holds_without_recollection(
    model, fault
):
    owner, artifact, state = model
    if fault == "duplicate":
        state["add"](artifact.payload)
    else:
        state["references"].clear()
        if fault == "malformed":
            state["add"](b"{not-json")
        elif fault == "wrong-schema":
            state["add"](canonical({"schema": "unrelated"}))
        elif fault == "media":
            state["add"](artifact.payload, media="text/plain")
        elif fault == "oversize":
            state["add"](b"x" * (module.MAX_PREREQUISITE_BYTES + 1))
        else:
            ref = state["add"](artifact.payload)
            state["manifests"][ref.evidence_id] += b" "
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner)
    assert owner.view()["status"] == "HELD" and owner._store is None
    if fault == "duplicate":
        assert owner.retained_prerequisites()["document"] == artifact.to_dict()
    else:
        assert owner.retained_prerequisites() is None


@pytest.mark.parametrize("change", ["source_sha256", "session_id", "launch_session_id"])
def test_original_payload_source_session_and_origin_are_not_rebound(
    model, workspace, change
):
    owner, _, state = model
    value = "f" * 64 if change == "source_sha256" else "different-origin"
    # For source mismatch, source collector must still observe its own bound
    # source, so mutate an already valid full document and re-encode instead.
    data = generate(workspace).to_dict()
    data["binding"][change] = value
    state["references"].clear()
    state["add"](canonical(data))
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner)
    assert owner._store is None and owner.retained_prerequisites() is None


@pytest.mark.parametrize(
    "fault", ["header", "cancel", "source", "deadline", "count", "bytes", "no-open"]
)
def test_pre_read_holds_do_not_load_payloads(model, fault):
    owner, _, state = model
    kwargs = {}
    if fault == "header":
        kwargs["expected_header_sha256"] = "f" * 64
    elif fault == "cancel":
        kwargs["cancellation"] = threading.Event()
        kwargs["cancellation"].set()
    elif fault == "source":
        state["source"] = "f" * 64
    elif fault == "deadline":
        kwargs["deadline_ns"] = state["now"]
    elif fault == "count":
        state["references"] *= module.MAX_READBACK_STAGE_REFERENCES + 1
    elif fault == "bytes":
        state["references"][0] = replace(
            state["references"][0], payload_bytes=module.MAX_READBACK_STAGE_BYTES + 1
        )
    else:
        owner._store = None
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, **kwargs)
    assert state["reads"] == 0 and owner._store is None


@pytest.mark.parametrize(
    "fault",
    [
        "stop",
        "source",
        "deadline",
        "progress",
        "guard-exit",
        "lease-exit",
        "post-header",
        "post-head",
        "post-inventory",
        "post-attempt",
        "post-quarantine",
    ],
)
def test_verified_bytes_survive_late_failure_but_current_projection_is_held(
    model, fault, monkeypatch
):
    owner, artifact, state = model
    cancellation = threading.Event()
    if fault == "lease-exit":
        state["exit_failure"] = True
    if fault == "guard-exit":

        @contextmanager
        def failed_guard(_):
            yield
            raise RuntimeError("modeled directory guard cleanup failure")

        monkeypatch.setattr(module, "_directory_guard", failed_guard)
    after_fields = {
        "post-header": "session_header_sha256",
        "post-head": "session_head_sha256",
        "post-inventory": "evidence_inventory_sha256",
        "post-attempt": "attempt_head_sha256",
        "post-quarantine": "quarantine_head_sha256",
    }
    state["after_change"] = after_fields.get(fault)

    def progress(message):
        if "finished" not in message:
            return
        if fault == "stop":
            cancellation.set()
        elif fault == "source":
            state["source"] = "f" * 64
        elif fault == "deadline":
            state["now"] += module.DIAGNOSTIC_TIMEOUT_NS
        elif fault == "progress":
            raise RuntimeError("private callback error")

    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, cancellation=cancellation, progress=progress)
    assert owner.retained_prerequisites()["document"] == artifact.to_dict()
    assert owner.view()["status"] == "HELD" and owner.view()["verification"] is None
    assert owner._store is None and state["reads"] == 1


@pytest.mark.parametrize("deadline", [None, 120_000_000_101, 1000])
def test_external_deadline_cannot_renew_original_120s_budget(model, deadline):
    owner, _, state = model

    def progress(message):
        state["now"] = 100 + module.DIAGNOSTIC_TIMEOUT_NS if deadline != 1000 else 1000

    with pytest.raises(module.PhysicalCameraSessionError, match="TIMED_OUT"):
        read(owner, deadline_ns=deadline, progress=progress)
    assert state["reads"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_header_sha256", None),
        ("expected_header_sha256", "0" * 64),
        ("expected_header_sha256", "B" * 64),
        ("deadline_ns", True),
        ("deadline_ns", -1),
    ],
)
def test_header_and_deadline_inputs_fail_before_any_scope_or_payload_read(
    model, field, value
):
    owner, _, state = model
    before = owner.view()
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, **{field: value})
    assert owner.view() == before
    assert state["enters"] == state["reads"] == state["verification_calls"] == 0


def test_camera_device_lease_scope_is_not_a_stage_readback_scope(model, monkeypatch):
    owner, _, state = model
    monkeypatch.setattr(
        module.M1PhysicalCameraTransaction,
        "held_leases",
        property(
            lambda _: (
                LeaseSpec(LeaseLevel.CELL, CELL),
                LeaseSpec(LeaseLevel.SESSION, SESSION),
                LeaseSpec(LeaseLevel.CAMERA, CELL),
            )
        ),
    )
    with pytest.raises(
        module.PhysicalCameraSessionError, match="EXACT_CAMERA_TRANSACTION_REQUIRED"
    ):
        read(owner)
    assert state["reads"] == 0 and owner._store is None


@pytest.mark.parametrize("fault", ["stop", "source", "deadline"])
def test_context_change_during_closing_batch_audit_withholds_workflow(
    model, monkeypatch, fault
):
    owner, artifact, state = model
    cancellation = threading.Event()
    transaction = state["transaction"]
    original_batch = transaction._original_evidence_readback

    @contextmanager
    def modeled_closing_change(**kwargs):
        with original_batch(**kwargs) as batch:
            yield batch
        # Model a context change while the closing storage audit runs, after
        # semantic validation. Actual NTFS mutation checks live in batch tests.
        if fault == "stop":
            cancellation.set()
        elif fault == "source":
            state["source"] = "f" * 64
        else:
            state["now"] += module.DIAGNOSTIC_TIMEOUT_NS

    monkeypatch.setattr(
        transaction, "_original_evidence_readback", modeled_closing_change
    )
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, cancellation=cancellation)
    assert owner.view()["status"] == "HELD" and owner._store is None
    assert owner.retained_prerequisites()["document"] == artifact.to_dict()


@pytest.mark.skipif(os.name != "nt", reason="actual Windows NTFS original store")
def test_actual_new_owner_reopens_and_reads_original_bytes_without_mutating_stages(
    workspace, monkeypatch
):
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    artifact = generate(workspace)
    original = session_fixture(workspace)
    initial = perform(original)
    header = initial["verification"]["session"]["header_sha256"]
    with original.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:
        snapshot = tx.commit_stage_state(
            STAGE_ORDER[0],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time.time_ns(),
            detail_code="RESTART_READBACK_TEST_WAITING",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        ref = tx.store_evidence(
            STAGE_ORDER[0],
            artifact.payload,
            label=module.PREREQUISITE_LABEL,
            media_type="application/json",
            captured_at_ns=time.time_ns(),
            expected_head_sha256=snapshot.head.head_sha256,
        )
    reopened = session_fixture(workspace)
    before = perform(reopened, "refresh")
    expected_inventory = before["verification"]["session"]["evidence_inventory_sha256"]
    assert reopened.retained_prerequisites() is None
    result = read(reopened, expected_header_sha256=header)
    assert result["reference"] == ref.to_dict()
    assert canonical(result["document"]) == artifact.payload
    after = reopened.view()
    assert after["stages"] == before["stages"]
    assert after["verification"]["session"] == before["verification"]["session"]
    assert (
        after["verification"]["session"]["evidence_inventory_sha256"]
        == expected_inventory
    )
    assert (
        after["verification"]["attempt_ledger"]
        == before["verification"]["attempt_ledger"]
    )
    assert after["verification"]["quarantine"] == before["verification"]["quarantine"]
    assert after["stages"][0]["state"] == "WAITING_OPERATOR"
    assert all(row["state"] == "PENDING" for row in after["stages"][1:])
