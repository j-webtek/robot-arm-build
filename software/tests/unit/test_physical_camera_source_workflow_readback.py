"""Closed original-stage-one readback, with explicit incapable storage models.

The modeled scope exercises production role/codec/readback logic without an OS
device, process or provider. The separate NTFS case uses only an isolated store.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import platform
from types import SimpleNamespace
import threading
import time

import pytest

from rocell.application import physical_camera_session as module
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_session_readback import (
    HEADER,
    model,
    no_devices,
    workspace,
)
from test_physical_camera_session import (
    CELL,
    LAUNCH,
    SESSION,
    SOURCE,
    perform,
    session_fixture,
)

WORKSPACE = Path(__file__).resolve().parents[3]


def collect_chain(prerequisites, header, monkeypatch):
    """Real fixed-file source collector; broad fingerprint explicitly modeled."""
    from rocell.application import physical_source_stage_evidence as source

    monkeypatch.setattr(source, "source_fingerprint", lambda _: SOURCE)
    # Keep host selection modeled too: uncached platform queries on Windows
    # may launch `ver`. This fixture qualifies source bytes, not this host.
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "release", lambda: "MODELED_NOT_OBSERVED")
    receipt = source.collect_workspace_source_receipt(
        WORKSPACE,
        prerequisites=prerequisites,
        source_sha256=SOURCE,
        session_id=SESSION,
        origin_launch_id=LAUNCH,
        collection_launch_id="wizard-" + "2" * 32,
        header_sha256=header,
        operator_id="source-operator",
        cancellation=threading.Event(),
    )
    assessment = source.assess_workspace_source_receipt(receipt)
    review = source.review_workspace_source_assessment(
        receipt,
        assessment,
        reviewer_id="source-reviewer",
        review_launch_id="wizard-" + "3" * 32,
    )
    return {"receipt": receipt, "assessment": assessment, "review": review}


def read(owner, **kwargs):
    return owner.read_original_source_workflow(
        expected_header_sha256=kwargs.pop("expected_header_sha256", HEADER),
        cancellation=kwargs.pop("cancellation", threading.Event()),
        progress=kwargs.pop("progress", lambda _: None),
        **kwargs,
    )


@pytest.fixture
def workflow(model):
    """Extend the existing isolated scope model; do not replace pure codecs."""
    owner, prerequisites, state = model
    state.update(stage_state="WAITING_OPERATOR", committed_ids=[], next_state="PENDING")
    original = owner._store.stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with original(*args, **kwargs) as tx:
            old_snapshot = tx.snapshot

            def snapshot():
                result = old_snapshot()
                result.stages = tuple(
                    SimpleNamespace(
                        to_dict=lambda i=i, stage=stage: {
                            "stage": stage.value,
                            "state": (
                                state["stage_state"]
                                if i == 0
                                else state["next_state"] if i == 1 else "PENDING"
                            ),
                            "last_event_sequence": None if i else 0,
                            "evidence_ids": (
                                list(state["committed_ids"]) if i == 0 else []
                            ),
                        }
                    )
                    for i, stage in enumerate(STAGE_ORDER)
                )
                return result

            tx.snapshot = snapshot
            try:
                yield tx
            finally:
                tx.snapshot = old_snapshot

    owner._store.stage_transaction = scope
    return owner, prerequisites, state


@pytest.fixture
def chain(workflow, monkeypatch):
    owner, prerequisites, state = workflow
    artifacts = collect_chain(prerequisites, HEADER, monkeypatch)
    references = {
        role: state["add"](artifact.payload, label=f"workspace-source-{role}-v1")
        for role, artifact in artifacts.items()
    }
    state["stage_state"] = "BLOCKED"
    state["committed_ids"] = [
        reference.evidence_id for reference in references.values()
    ]
    return owner, prerequisites, state, artifacts, references


def test_new_reader_performs_one_scope_and_preserves_legacy_record_shape(workflow):
    owner, prerequisites, state = workflow
    result = read(owner)
    assert result["schema"] == module.SOURCE_WORKFLOW_SCHEMA
    assert result["binding"] == owner.descriptor()
    assert result["session_header_sha256"] == HEADER
    assert result["stage"] == "workspace_sources"
    assert result["state"] == "WAITING_OPERATOR"
    assert result["receipt"] is result["assessment"] is result["review"] is None
    assert result["prerequisites"] == owner.retained_prerequisites()
    assert canonical(result["prerequisites"]["document"]) == prerequisites.payload
    assert state["enters"] == state["exits"] == state["reads"] == 1
    assert state["verification_calls"] == 2
    assert (
        result["evidence_inventory_sha256"]
        == owner.view()["verification"]["session"]["evidence_inventory_sha256"]
    )
    assert result["physical_authority"] is result["device_io_performed"] is False
    result["prerequisites"]["document"]["physical_authority"] = True
    assert (
        owner.retained_source_workflow()["prerequisites"]["document"][
            "physical_authority"
        ]
        is False
    )
    copy = owner.retained_source_workflow()
    copy["binding"]["source_sha256"] = "f" * 64
    assert owner.retained_source_workflow()["binding"]["source_sha256"] == SOURCE


@pytest.mark.parametrize("stage_state", ["PENDING", "WAITING_OPERATOR"])
def test_empty_initial_or_prepublication_inventory_is_retained_as_empty(
    workflow, stage_state
):
    owner, _, state = workflow
    state["references"].clear()
    state["stage_state"] = stage_state
    result = read(owner)
    assert all(
        result[role] is None
        for role in ("prerequisites", "receipt", "assessment", "review")
    )
    assert result["state"] == stage_state
    assert state["reads"] == 0 and owner.retained_prerequisites() is None


@pytest.mark.parametrize(
    "fault", ["unknown-label", "wrong-stage", "duplicate", "media", "manifest-hash"]
)
def test_closed_inventory_rejects_unknown_or_conflicting_role(workflow, fault):
    owner, prerequisites, state = workflow
    if fault == "unknown-label":
        state["add"](b"{}", label="unreviewed-source-note")
    elif fault == "wrong-stage":
        state["add"](prerequisites.payload, stage=STAGE_ORDER[1])
    elif fault == "duplicate":
        state["add"](prerequisites.payload)
    else:
        state["references"].clear()
        ref = state["add"](
            prerequisites.payload,
            media="text/plain" if fault == "media" else "application/json",
        )
        if fault == "manifest-hash":
            state["manifests"][ref.evidence_id] += b" "
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner)
    assert owner.view()["status"] == "HELD"
    assert owner._store is None
    assert owner.retained_source_workflow() is None


@pytest.mark.parametrize("role", ["receipt", "assessment", "review"])
def test_unrelated_json_cannot_masquerade_as_typed_role(workflow, role):
    owner, _, state = workflow
    state["add"](
        canonical({"schema": "not-source-evidence"}),
        label=f"workspace-source-{role}-v1",
    )
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner)
    assert owner.retained_source_workflow() is None
    assert owner._store is None


@pytest.mark.parametrize(
    "stage_state",
    [
        "PENDING",
        "REVIEW_PENDING",
        "BLOCKED",
        "PASS",
        "INCIDENT_HOLD",
        "SIDE_EFFECT_UNCERTAIN",
    ],
)
def test_prerequisite_document_alone_cannot_imply_assessment_review_or_pass(
    workflow, stage_state
):
    owner, _, state = workflow
    state["stage_state"] = stage_state
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_STATE"):
        read(owner)
    assert owner.retained_source_workflow() is None


def test_downstream_stage_change_is_outside_closed_source_only_workflow(workflow):
    owner, _, state = workflow
    state["next_state"] = "WAITING_OPERATOR"
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_STATE"):
        read(owner)


@pytest.mark.parametrize(
    "fault", ["stop", "source", "deadline", "lease-exit", "post-inventory"]
)
def test_verified_chain_retained_before_late_failure_is_historical_only(
    workflow, fault
):
    owner, prerequisites, state = workflow
    cancellation = threading.Event()
    if fault == "lease-exit":
        state["exit_failure"] = True
    if fault == "post-inventory":
        state["after_change"] = "evidence_inventory_sha256"

    def progress(message):
        if "finished" not in message:
            return
        if fault == "stop":
            cancellation.set()
        elif fault == "source":
            state["source"] = "f" * 64
        elif fault == "deadline":
            state["now"] += module.DIAGNOSTIC_TIMEOUT_NS

    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, cancellation=cancellation, progress=progress)
    retained = owner.retained_source_workflow()
    assert retained["prerequisites"]["document"] == prerequisites.to_dict()
    assert retained["state"] == "WAITING_OPERATOR"
    assert owner.view()["status"] == "HELD" and owner._store is None


@pytest.mark.parametrize("fault", ["count", "bytes", "cancel", "source", "header"])
def test_preflight_inventory_and_context_holds_precede_payload_reads(workflow, fault):
    owner, _, state = workflow
    values = {}
    if fault == "count":
        state["references"] *= module.MAX_READBACK_STAGE_REFERENCES + 1
    elif fault == "bytes":
        state["references"][0] = replace(
            state["references"][0], payload_bytes=module.MAX_READBACK_STAGE_BYTES + 1
        )
    elif fault == "cancel":
        values["cancellation"] = threading.Event()
        values["cancellation"].set()
    elif fault == "source":
        state["source"] = "f" * 64
    else:
        values["expected_header_sha256"] = "f" * 64
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, **values)
    assert state["reads"] == 0


def test_inert_retained_getter_does_not_consume_a_second_read_scope(workflow):
    owner, _, state = workflow
    expected = read(owner)
    before = deepcopy(
        {key: state[key] for key in ("enters", "reads", "verification_calls", "audit")}
    )
    for _ in range(5):
        assert owner.retained_source_workflow() == expected
        assert owner.retained_prerequisites() == expected["prerequisites"]
    assert before == {key: state[key] for key in before}


@pytest.mark.parametrize(
    "stage_state,role_count",
    [
        ("WAITING_OPERATOR", 1),
        ("WAITING_OPERATOR", 2),
        ("REVIEW_PENDING", 2),
        ("REVIEW_PENDING", 3),
        ("BLOCKED", 3),
    ],
)
def test_exact_partial_and_reviewed_chain_retains_original_commit_separately(
    chain, stage_state, role_count
):
    owner, prerequisites, state, artifacts, references = chain
    included = tuple(artifacts)[:role_count]
    keep = {
        state["references"][0].evidence_id,
        *(references[role].evidence_id for role in included),
    }
    state["references"][:] = [
        ref for ref in state["references"] if ref.evidence_id in keep
    ]
    state["stage_state"] = stage_state
    state["committed_ids"] = (
        []
        if stage_state == "WAITING_OPERATOR"
        else [
            references[role].evidence_id
            for role in (
                included if stage_state == "BLOCKED" else ("receipt", "assessment")
            )
        ]
    )
    result = read(owner)
    assert result["state"] == stage_state
    for role in artifacts:
        if role not in included:
            assert result[role] is None
            continue
        assert result[role]["document"] == artifacts[role].to_dict()
        assert result[role]["evidence_sha256"] == artifacts[role].sha256
        assert result[role]["reference"] == references[role].to_dict()
    assert result["prerequisites"]["document"] == prerequisites.to_dict()
    assert state["reads"] == 1 + role_count
    assert state["enters"] == state["exits"] == 1
    assert owner.view()["stages"][0]["state"] == stage_state


@pytest.mark.parametrize("role", ["receipt", "assessment", "review"])
def test_a_second_valid_occurrence_is_not_a_replacement_for_original_role(chain, role):
    owner, _, state, artifacts, _ = chain
    state["add"](artifacts[role].payload, label=f"workspace-source-{role}-v1")
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_ROLE"):
        read(owner)
    assert owner.retained_source_workflow() is None


@pytest.mark.parametrize("role", ["receipt", "assessment", "review"])
def test_missing_role_cannot_be_hidden_by_other_valid_subject_documents(chain, role):
    owner, _, state, _, references = chain
    state["references"][:] = [
        ref for ref in state["references"] if ref != references[role]
    ]
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner)
    assert owner._store is None and owner.retained_source_workflow() is None


@pytest.mark.parametrize("role", ["receipt", "assessment", "review"])
def test_rehashed_wrong_source_in_full_typed_role_is_denied(chain, role):
    owner, _, state, artifacts, references = chain
    value = artifacts[role].to_dict()
    value["binding"]["source_sha256"] = "f" * 64
    old = references[role]
    raw = canonical(value)
    replacement = replace(old, payload_sha256=digest(raw), payload_bytes=len(raw))
    state["references"][state["references"].index(old)] = replacement
    state["payloads"][old.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_CHAIN"):
        read(owner)
    assert owner.retained_source_workflow() is None


@pytest.mark.parametrize(
    "role,field",
    [
        ("assessment", "receipt_sha256"),
        ("review", "receipt_sha256"),
        ("review", "assessment_sha256"),
    ],
)
def test_rehashed_assessment_or_review_cannot_change_original_subject(
    chain, role, field
):
    owner, _, state, artifacts, references = chain
    value = artifacts[role].to_dict()
    value[field] = "f" * 64
    raw = canonical(value)
    old = references[role]
    state["references"][state["references"].index(old)] = replace(
        old, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][old.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_CHAIN"):
        read(owner)
    assert owner.retained_source_workflow() is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("header_sha256", "f" * 64),
        ("prerequisites_sha256", "f" * 64),
        ("session_id", "physical-camera-" + "f" * 32),
        ("origin_launch_id", "wizard-" + "f" * 32),
    ],
)
def test_rehashed_receipt_cannot_rebind_original_store_or_requirements(
    chain, field, value
):
    owner, _, state, artifacts, references = chain
    data = artifacts["receipt"].to_dict()
    data["binding"][field] = value
    raw = canonical(data)
    old = references["receipt"]
    state["references"][state["references"].index(old)] = replace(
        old, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][old.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_CHAIN"):
        read(owner)
    assert owner.retained_source_workflow() is None


@pytest.mark.parametrize(
    "state_name,missing",
    [
        ("REVIEW_PENDING", "receipt"),
        ("REVIEW_PENDING", "assessment"),
        ("BLOCKED", "review"),
    ],
)
def test_saved_record_does_not_imply_its_committed_review_reference(
    chain, state_name, missing
):
    owner, _, state, _, refs = chain
    state["stage_state"] = state_name
    state["committed_ids"].remove(refs[missing].evidence_id)
    with pytest.raises(module.PhysicalCameraSessionError, match="WORKFLOW_STATE"):
        read(owner)


def test_full_chain_pure_restore_cannot_rerun_source_collector(chain, monkeypatch):
    from rocell.application import physical_source_stage_evidence as source

    owner, _, _, artifacts, _ = chain

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Original readback must not collect or assess new source observations"
        )

    monkeypatch.setattr(source, "collect_workspace_source_receipt", forbidden)
    result = read(owner)
    assert result["receipt"]["document"] == artifacts["receipt"].to_dict()
    assert result["state"] == "BLOCKED"


@pytest.mark.skipif(os.name != "nt", reason="isolated actual Windows NTFS store")
def test_actual_original_store_source_review_chain_reopens_without_mutation(
    workspace, monkeypatch
):
    from test_physical_camera_session_readback import generate
    from rocell.application.physical_onboarding_v2 import V2StageState

    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    original = session_fixture(workspace)
    initial = perform(original)
    header = initial["verification"]["session"]["header_sha256"]
    artifacts = collect_chain(prerequisites, header, monkeypatch)
    with original.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:
        snapshot = tx.commit_stage_state(
            STAGE_ORDER[0],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time.time_ns(),
            detail_code="ISOLATED_SOURCE_REVIEW_WAITING",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        refs = {}
        for role, artifact in {"prerequisites": prerequisites, **artifacts}.items():
            label = (
                module.PREREQUISITE_LABEL
                if role == "prerequisites"
                else f"workspace-source-{role}-v1"
            )
            # Store review only after REVIEW_PENDING, matching the real workflow.
            if role == "review":
                snapshot = tx.commit_stage_state(
                    STAGE_ORDER[0],
                    V2StageState.REVIEW_PENDING,
                    occurred_at_ns=time.time_ns(),
                    detail_code="ISOLATED_SOURCE_REVIEW_PENDING",
                    expected_head_sha256=tx.snapshot().head.head_sha256,
                    evidence=(refs["receipt"], refs["assessment"]),
                )
            refs[role] = tx.store_evidence(
                STAGE_ORDER[0],
                artifact.payload,
                label=label,
                media_type="application/json",
                captured_at_ns=time.time_ns(),
                expected_head_sha256=snapshot.head.head_sha256,
            )
        tx.commit_stage_state(
            STAGE_ORDER[0],
            V2StageState.BLOCKED,
            occurred_at_ns=time.time_ns(),
            detail_code="ISOLATED_SOURCE_REVIEW_BLOCKED",
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=(refs["receipt"], refs["assessment"], refs["review"]),
        )
    reopened = session_fixture(workspace)
    before = perform(reopened, "refresh")
    result = read(reopened, expected_header_sha256=header)
    assert result["state"] == "BLOCKED"
    assert result["binding"]["cell_id"] == CELL
    for role, artifact in {"prerequisites": prerequisites, **artifacts}.items():
        assert canonical(result[role]["document"]) == artifact.payload
        assert result[role]["reference"] == refs[role].to_dict()
    after = reopened.view()
    assert after["verification"]["session"] == before["verification"]["session"]
    assert (
        after["verification"]["attempt_ledger"]
        == before["verification"]["attempt_ledger"]
    )
    assert after["verification"]["quarantine"] == before["verification"]["quarantine"]
    assert after["stages"] == before["stages"]
    assert all(stage["state"] == "PENDING" for stage in after["stages"][1:])
