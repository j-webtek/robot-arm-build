"""Pure progressive records over modeled, genuinely typed V2 audit snapshots.

The prerequisite helper reads the actual four controlled requirement files with
only the broad source fingerprint modeled. Snapshot storage/qualification and
stage outcomes below are closed test data, not an actual M1 or hardware run.
"""

from dataclasses import replace
import ctypes
import hashlib
import json
from pathlib import Path
from threading import Event
import time
from unittest.mock import patch

import pytest

from rocell.application import physical_configuration_epochs as module
from rocell.application import physical_camera_prerequisites as prerequisites_module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER

SOURCE = "a" * 64
SESSION = "physical-camera-" + "1" * 32
CELL = "wizard-physical-camera-" + "2" * 16
LAUNCH = "wizard-" + "3" * 32
WORKSPACE = Path(__file__).resolve().parents[3]


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def reference(stage, payload=b"MODELED UNASSESSED REFERENCE", *, salt="fixture"):
    payload_hash = hashlib.sha256(payload).hexdigest()
    package = hashlib.sha256(
        canonical({"stage": stage.value, "payload": payload_hash, "salt": salt})
    ).hexdigest()
    return EvidenceReference(
        "evidence-" + package,
        stage,
        package,
        hashlib.sha256(("MODELED_MANIFEST:" + package).encode()).hexdigest(),
        payload_hash,
        len(payload),
    )


def typed_snapshot(prerequisites, *, boundary_index=0, extra=()):
    header = v2.V2SessionHeader.build(
        session_id=SESSION,
        cell_id=CELL,
        created_at_ns=1,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        publication_durability=v2.PORTABLE_UNQUALIFIED,
        durability_qualification_sha256="0" * 64,
    )
    refs = [
        reference(STAGE_ORDER[0], prerequisites.payload, salt="original-prerequisite"),
        *extra,
    ]
    events = []
    states = [v2.V2StageState.PENDING for _ in STAGE_ORDER]
    sequences = [None for _ in STAGE_ORDER]
    ids = [[] for _ in STAGE_ORDER]

    def append(stage_index, state, evidence=()):
        event = v2.V2JournalEvent.build(
            header=header,
            sequence=len(events),
            stage=STAGE_ORDER[stage_index],
            previous_state=states[stage_index],
            state=state,
            occurred_at_ns=len(events) + 2,
            previous_event_sha256=events[-1].event_sha256 if events else "0" * 64,
            evidence=evidence,
            detail_code="MODELED_TEST_STAGE",
        )
        v2._apply_transition(states, event)
        sequences[stage_index] = event.sequence
        ids[stage_index].extend(v.evidence_id for v in evidence)
        events.append(event)

    for index in range(boundary_index + 1):
        append(index, v2.V2StageState.WAITING_OPERATOR)
        if index < boundary_index:
            ref = reference(STAGE_ORDER[index], salt=f"modeled-stage-{index}")
            refs.append(ref)
            append(index, v2.V2StageState.REVIEW_PENDING, (ref,))
            append(index, v2.V2StageState.PASS, (ref,))
    result = v2.V2SessionSnapshot(
        header,
        tuple(
            v2.V2StageSnapshot(stage, states[i], sequences[i], tuple(ids[i]))
            for i, stage in enumerate(STAGE_ORDER)
        ),
        tuple(events),
        (),
        tuple(sorted(refs, key=lambda v: v.evidence_id)),
        v2.V2CommittedHead.build(header, events),
        v2._derive_next_action(states),
    )
    return result


def epoch_fixture():
    """Actual requirements + modeled typed original wait-state + actual vector."""
    with patch.object(prerequisites_module, "source_fingerprint", lambda _: SOURCE):
        prerequisites = prerequisites_module.collect_physical_camera_prerequisites(
            WORKSPACE,
            source_sha256=SOURCE,
            session_id=SESSION,
            launch_session_id=LAUNCH,
            cancellation=Event(),
            deadline_ns=time.monotonic_ns() + 30_000_000_000,
        )
    snapshot = typed_snapshot(prerequisites)
    return (
        prerequisites,
        snapshot,
        module.build_physical_configuration_epochs(prerequisites, snapshot),
    )


@pytest.fixture(scope="module")
def initial():
    return epoch_fixture()


def verify(artifact, prerequisites, snapshot, **kwargs):
    return module.verify_physical_configuration_epochs(
        artifact.payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=kwargs.pop("expected_sha256", artifact.sha256),
        **kwargs,
    )


def test_initial_all_eight_domains_retain_order_and_explicit_unknowns(initial):
    prerequisites, snapshot, artifact = initial
    assert verify(artifact, prerequisites, snapshot).payload == artifact.payload
    value = artifact.to_dict()
    assert [v["epoch_id"] for v in value["entries"]] == list(module._EXPECTED_EPOCH_IDS)
    assert value["coverage"] == {
        "total_bindings": 32,
        "retained": 0,
        "missing_predecessors": 0,
        "missing_current_outputs": 0,
        "pending_current_outputs": 4,
        "pending_future_outputs": 28,
    }
    assert value["boundary"] == {"stage": "workspace_sources", "phase": "BEFORE_STAGE"}
    assert all(v["status"] == "UNOBSERVED" for v in value["entries"])
    assert all(v is False for k, v in value.items() if k in module._FLAGS)
    assert b"\n" not in artifact.payload and len(artifact.payload) < 16 * 1024
    assert all(
        v["status"] == "UNMEASURED" for v in prerequisites.safe_summary()["epochs"]
    )


@pytest.mark.parametrize("boundary_index", range(15))
@pytest.mark.parametrize("phase", ["BEFORE_STAGE", "AFTER_STAGE"])
def test_actual_owner_boundaries_rederive_missing_vs_pending(
    initial, boundary_index, phase
):
    prerequisites = initial[0]
    snapshot = typed_snapshot(prerequisites, boundary_index=boundary_index)
    result = module.build_physical_configuration_epochs(
        prerequisites, snapshot, boundary=phase
    )
    for entry in result.to_dict()["entries"]:
        for row in entry["bindings"]:
            owner = STAGE_ORDER.index(
                module.BINDING_OWNER_STAGES[module.EpochBindingName(row["binding_id"])]
            )
            expected = (
                "MISSING_PREDECESSOR"
                if owner < boundary_index
                else (
                    "PENDING_FUTURE_OUTPUT"
                    if owner > boundary_index
                    else (
                        "PENDING_CURRENT_OUTPUT"
                        if phase == "BEFORE_STAGE"
                        else "MISSING_CURRENT_OUTPUT"
                    )
                )
            )
            assert row["status"] == expected
    assert verify(result, prerequisites, snapshot).payload == result.payload


def test_first_camera_probe_does_not_require_its_own_or_later_outputs(initial):
    prerequisites = initial[0]
    snapshot = typed_snapshot(prerequisites, boundary_index=4)
    artifact = module.build_physical_configuration_epochs(prerequisites, snapshot)
    rows = {
        v["binding_id"]: v for e in artifact.to_dict()["entries"] for v in e["bindings"]
    }
    assert (
        rows["camera_receipt"]["status"]
        == rows["camera_identity"]["status"]
        == "MISSING_PREDECESSOR"
    )
    assert rows["camera_mode_controls"]["status"] == "PENDING_CURRENT_OUTPUT"
    assert (
        rows["support_witnesses"]["status"]
        == rows["tag_map"]["status"]
        == "PENDING_FUTURE_OUTPUT"
    )
    assert rows["firmware_identity"]["owner_stage"] == "feedback_only_connection"
    assert artifact.safe_summary()["admission_allowed"] is False


def test_typed_reference_present_is_still_unassessed(initial):
    prerequisites = initial[0]
    ref = reference(STAGE_ORDER[0], b"MODELED SOURCE BINDING BYTES, NOT QUALIFIED")
    snapshot = typed_snapshot(prerequisites, extra=(ref,))
    binding = module.EpochEvidenceBinding(
        module.EpochBindingName.SOURCE_BINDING, (ref,)
    )
    artifact = module.build_physical_configuration_epochs(
        prerequisites, snapshot, evidence_bindings=(binding,)
    )
    row = artifact.to_dict()["entries"][0]["bindings"][1]
    assert row["status"] == "RETAINED_REFERENCE_UNASSESSED" and row["evidence"] == [
        ref.to_dict()
    ]
    assert artifact.to_dict()["entries"][0]["status"] == "PARTIALLY_REFERENCED"
    assert (
        verify(artifact, prerequisites, snapshot).safe_summary()["qualified"] is False
    )


def test_later_inventory_and_committed_head_verify_original_without_old_snapshot(
    initial,
):
    prerequisites, original, artifact = initial
    # Retain the vector itself and later source-role records, then commit a real
    # legal typed REVIEW_PENDING event. The original head remains its prefix.
    vector_ref = reference(STAGE_ORDER[0], artifact.payload, salt="epoch-vector")
    later_ref = reference(STAGE_ORDER[0], b"MODELED LATER SOURCE ASSESSMENT")
    event = v2.V2JournalEvent.build(
        header=original.header,
        sequence=1,
        stage=STAGE_ORDER[0],
        previous_state=v2.V2StageState.WAITING_OPERATOR,
        state=v2.V2StageState.REVIEW_PENDING,
        occurred_at_ns=3,
        previous_event_sha256=original.committed_events[-1].event_sha256,
        evidence=(later_ref,),
        detail_code="MODELED_LATER_REVIEW",
    )
    events = original.committed_events + (event,)
    states = [v2.V2StageState.REVIEW_PENDING] + [v2.V2StageState.PENDING] * 14
    current = replace(
        original,
        evidence=tuple(
            sorted(
                (*original.evidence, vector_ref, later_ref), key=lambda v: v.evidence_id
            )
        ),
        committed_events=events,
        head=v2.V2CommittedHead.build(original.header, events),
        stages=(
            v2.V2StageSnapshot(STAGE_ORDER[0], states[0], 1, (later_ref.evidence_id,)),
            *original.stages[1:],
        ),
        next_action=v2._derive_next_action(states),
    )
    assert current.head != original.head
    assert verify(artifact, prerequisites, current).payload == artifact.payload


@pytest.mark.parametrize(
    "fault",
    [
        "dict",
        "string_name",
        "wrong_stage",
        "not_in_inventory",
        "duplicate",
        "future",
        "mutated",
    ],
)
def test_arbitrary_or_cross_owner_evidence_cannot_become_a_binding(initial, fault):
    prerequisites, snapshot, _ = initial
    ref = snapshot.evidence[0]
    with pytest.raises((module.PhysicalConfigurationEpochError, ValueError)):
        if fault == "dict":
            bindings = {"source_binding": ref.payload_sha256}
        elif fault == "string_name":
            bindings = (module.EpochEvidenceBinding("source_binding", (ref,)),)
        elif fault == "wrong_stage":
            bindings = (
                module.EpochEvidenceBinding(
                    module.EpochBindingName.CAMERA_IDENTITY, (ref,)
                ),
            )
        elif fault == "not_in_inventory":
            bindings = (
                module.EpochEvidenceBinding(
                    module.EpochBindingName.SOURCE_BINDING,
                    (reference(STAGE_ORDER[0], salt="absent"),),
                ),
            )
        elif fault == "duplicate":
            item = module.EpochEvidenceBinding(
                module.EpochBindingName.SOURCE_BINDING, (ref,)
            )
            bindings = (item, item)
        elif fault == "future":
            later = reference(STAGE_ORDER[4])
            snapshot = replace(
                snapshot,
                evidence=tuple(
                    sorted((*snapshot.evidence, later), key=lambda v: v.evidence_id)
                ),
            )
            bindings = (
                module.EpochEvidenceBinding(
                    module.EpochBindingName.CAMERA_MODE_CONTROLS, (later,)
                ),
            )
        else:
            changed = replace(ref, payload_bytes=True)
            bindings = (
                module.EpochEvidenceBinding(
                    module.EpochBindingName.SOURCE_BINDING, (changed,)
                ),
            )
        module.build_physical_configuration_epochs(
            prerequisites, snapshot, evidence_bindings=bindings
        )


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_source",
        "wrong_session",
        "wrong_header",
        "changed_inventory",
        "missing_inventory",
        "fake_next",
        "fake_stage",
        "future_boundary",
        "suffix",
    ],
)
def test_wrong_or_mutated_original_context_is_denied(initial, fault):
    prerequisites, snapshot, artifact = initial
    if fault == "wrong_source":
        snapshot = replace(
            snapshot, header=replace(snapshot.header, source_binding_sha256="b" * 64)
        )
    elif fault == "wrong_session":
        snapshot = replace(
            snapshot,
            header=replace(snapshot.header, session_id="physical-camera-" + "2" * 32),
        )
    elif fault == "wrong_header":
        snapshot = replace(
            snapshot, header=replace(snapshot.header, header_sha256="b" * 64)
        )
    elif fault == "changed_inventory":
        snapshot = replace(
            snapshot, evidence=(replace(snapshot.evidence[0], payload_sha256="c" * 64),)
        )
    elif fault == "missing_inventory":
        snapshot = replace(snapshot, evidence=())
    elif fault == "fake_next":
        snapshot = replace(
            snapshot, next_action=replace(snapshot.next_action, stage=STAGE_ORDER[4])
        )
    elif fault == "fake_stage":
        snapshot = replace(
            snapshot,
            stages=(
                replace(snapshot.stages[0], state=v2.V2StageState.PASS),
                *snapshot.stages[1:],
            ),
        )
    elif fault == "suffix":
        snapshot = replace(snapshot, uncommitted_events=snapshot.committed_events)
    with pytest.raises(module.PhysicalConfigurationEpochError):
        if fault == "future_boundary":
            module.build_physical_configuration_epochs(
                prerequisites, snapshot, boundary_stage=STAGE_ORDER[4]
            )
        else:
            verify(artifact, prerequisites, snapshot)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(qualified=True),
        lambda d: d.update(unknown=True),
        lambda d: d["entries"][0]["bindings"][0].update(status="QUALIFIED"),
        lambda d: d["entries"][0]["bindings"][0].update(
            owner_stage="camera_mode_controls"
        ),
        lambda d: d["entries"].reverse(),
        lambda d: d["coverage"].update(retained=1),
        lambda d: d["boundary"].update(phase="AUTO_ACCEPT"),
        lambda d: d["original_snapshot"].update(evidence_inventory_sha256="0" * 64),
    ],
)
def test_rehashed_projection_forgery_is_rejected(initial, mutate):
    prerequisites, snapshot, artifact = initial
    obj = artifact.to_dict()
    mutate(obj)
    raw = canonical(obj)
    with pytest.raises(module.PhysicalConfigurationEpochError):
        module.verify_physical_configuration_epochs(
            raw,
            prerequisites=prerequisites,
            snapshot=snapshot,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_hash_canonical_bytes_immutability_and_strict_bounds(initial):
    prerequisites, snapshot, artifact = initial
    view = artifact.safe_summary()
    view["entries"].clear()
    assert len(artifact.to_dict()["entries"]) == 8
    with pytest.raises(module.PhysicalConfigurationEpochError):
        verify(artifact, prerequisites, snapshot, expected_sha256="f" * 64)
    for raw in (
        bytearray(artifact.payload),
        artifact.payload + b"\n",
        b'{"schema":"x","schema":"x"}',
        b"x" * (module.MAX_RECORD_BYTES + 1),
    ):
        with pytest.raises(module.PhysicalConfigurationEpochError):
            module.PhysicalConfigurationEpochs(raw)


@pytest.mark.parametrize(
    "changed",
    [
        {"source_sha256": "b" * 64},
        {"source_binding_sha256": "b" * 64},
        {"session_id": "rehearsal-session"},
        {"cell_id": "rehearsal-cell"},
    ],
)
def test_bytes_only_constructor_rejects_intrinsic_domain_contradictions(
    initial, changed
):
    value = initial[2].to_dict()
    value["binding"].update(changed)
    with pytest.raises(module.PhysicalConfigurationEpochError):
        module.PhysicalConfigurationEpochs(canonical(value))


@pytest.mark.parametrize("fault", ["count", "bytes", "future", "duplicate", "ordering"])
def test_inventory_caps_and_future_refs_are_not_waived_by_empty_bindings(
    initial, fault
):
    prerequisites, snapshot, _ = initial
    original = snapshot.evidence[0]
    if fault == "count":
        refs = tuple(reference(STAGE_ORDER[0], salt=str(i)) for i in range(33))
    elif fault == "bytes":
        refs = (replace(original, payload_bytes=module.MAX_INVENTORY_BYTES + 1),)
    elif fault == "future":
        refs = (original, reference(STAGE_ORDER[4]))
    elif fault == "duplicate":
        refs = (original, original)
    else:
        refs = tuple(
            sorted(
                (original, reference(STAGE_ORDER[0])),
                key=lambda v: v.evidence_id,
                reverse=True,
            )
        )
    if fault != "ordering":
        refs = tuple(sorted(refs, key=lambda v: v.evidence_id))
    with pytest.raises(module.PhysicalConfigurationEpochError):
        module.build_physical_configuration_epochs(
            prerequisites, replace(snapshot, evidence=refs)
        )


def test_independently_valid_changed_history_is_not_the_original_prefix(initial):
    prerequisites, snapshot, artifact = initial
    previous = snapshot.committed_events[0]
    event = v2.V2JournalEvent.build(
        header=snapshot.header,
        sequence=0,
        stage=previous.stage,
        previous_state=previous.previous_state,
        state=previous.state,
        occurred_at_ns=previous.occurred_at_ns,
        previous_event_sha256=previous.previous_event_sha256,
        evidence=previous.evidence,
        detail_code="OTHER_MODELED_ORIGINAL",
    )
    changed = replace(
        snapshot,
        committed_events=(event,),
        head=v2.V2CommittedHead.build(snapshot.header, (event,)),
    )
    # This altered chain is internally valid but is not the independent
    # original head retained by the artifact.
    module.build_physical_configuration_epochs(prerequisites, changed)
    with pytest.raises(
        module.PhysicalConfigurationEpochError, match="ORIGINAL_PREFIX_MISMATCH"
    ):
        verify(artifact, prerequisites, changed)


def test_builder_verifier_and_views_perform_no_io_after_inputs_exist(
    initial, monkeypatch
):
    prerequisites, snapshot, artifact = initial

    def forbidden(*args, **kwargs):
        pytest.fail("pure epoch records must not read files, time, M1 or devices")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(time, "monotonic_ns", forbidden)
    assert (
        module.build_physical_configuration_epochs(prerequisites, snapshot).payload
        == artifact.payload
    )
    assert (
        verify(artifact, prerequisites, snapshot).safe_summary()
        == artifact.safe_summary()
    )
