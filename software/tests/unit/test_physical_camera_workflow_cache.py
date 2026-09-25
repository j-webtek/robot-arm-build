"""Full original source/epoch/eight-intake cache is not worker IPC.

Real file-derived source subjects and all pure codecs are exercised with typed
original V2 history. Only M1 filesystem ownership is modeled; no public store,
hardware, native helper or process is touched.
"""

from dataclasses import replace
import threading

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_configuration_epochs as epochs
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_intake_submission import (
    assess_physical_intake_submission,
    review_physical_intake_submission,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import (
    decode_owned_json,
    OwnedWorkerError,
)
from test_physical_camera_intake_session import (
    intake_model,
    read,
    start,
    submission,
    label,
    code,
    RAW,
)
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_session import LAUNCH


def node_count(value):
    if type(value) is dict:
        return 1 + sum(
            node_count(key) + node_count(item) for key, item in value.items()
        )
    if type(value) is list:
        return 1 + sum(node_count(item) for item in value)
    return 1


@pytest.fixture
def full_history(intake_model):
    owner, prerequisites, state = intake_model
    # This is the genuine fixture's creation prefix, not a reader reconstruction.
    # It is built before constructing the original epoch record, whose verifier
    # then authenticates it against the later full original audited history.
    current = state["snapshot"]()
    first = current.committed_events[0]
    stages = tuple(
        v2.V2StageSnapshot(
            stage,
            v2.V2StageState.WAITING_OPERATOR if i == 0 else v2.V2StageState.PENDING,
            0 if i == 0 else None,
            (),
        )
        for i, stage in enumerate(STAGE_ORDER)
    )
    creation = v2.V2SessionSnapshot(
        current.header,
        stages,
        (first,),
        (),
        (state["references"][0],),
        v2.V2CommittedHead.build(current.header, (first,)),
        v2._derive_next_action([item.state for item in stages]),
    )
    vector = epochs.build_physical_configuration_epochs(
        prerequisites, creation, evidence_bindings=()
    )
    state["add"](vector.payload, label=module.CONFIGURATION_EPOCH_LABEL)
    previous = previous_refs = raw_ref = None
    for sequence in range(1, 9):
        collection = "intake-" + f"{sequence:032x}"
        start(state, collection, previous_refs)
        if raw_ref is None:
            raw_ref = state["add"](
                RAW, label=label("original", collection), media="text/plain"
            )
        item = submission(
            prerequisites,
            current.header.header_sha256,
            raw_ref,
            state["references"],
            collection=collection,
            predecessor=previous,
        )
        assessment = assess_physical_intake_submission(item)
        records = {"submission": item, "assessment": assessment}
        refs = {
            role: state["add"](artifact.payload, label=label(role, collection))
            for role, artifact in records.items()
        }
        state["advance"](
            v2.V2StageState.REVIEW_PENDING,
            code("SUBMITTED", collection),
            [raw_ref, *refs.values()],
        )
        review = review_physical_intake_submission(
            item,
            assessment,
            reviewer_id="intake-reviewer",
            review_launch_id=LAUNCH,
            reviewed_at_ns=item.to_dict()["submitted_at_ns"] + 500,
            decision="ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
        )
        refs["review"] = state["add"](review.payload, label=label("review", collection))
        state["advance"](
            v2.V2StageState.BLOCKED,
            code("REVIEWED", collection),
            [raw_ref, *refs.values()],
        )
        previous, previous_refs = item, refs
    return owner, state, vector


def test_full_actual_codec_history_survives_cache_and_owned_ipc_stays_closed(
    full_history,
):
    owner, state, vector = full_history
    result = read(owner, state["header"].header_sha256)
    payload = canonical(result)
    assert len(state["snapshot"]().evidence) == 30
    assert len(result["intake_collections"]) == 8
    assert node_count(result) > 4096
    assert node_count(result) <= module.MAX_SOURCE_WORKFLOW_CACHE_NODES
    assert canonical(result["configuration_epochs"]["document"]) == vector.payload
    assert owner.retained_source_workflow() == result
    assert digest(canonical(owner.retained_source_workflow())) == digest(payload)
    with pytest.raises(OwnedWorkerError, match="IPC_STRUCTURE_LIMIT"):
        decode_owned_json(payload, maximum=module.MAX_SOURCE_WORKFLOW_BYTES)
    detached = owner.retained_source_workflow()
    detached["intake_collections"][-1]["submission"]["document"][
        "operator_id"
    ] = "changed"
    assert canonical(owner.retained_source_workflow()) == payload
    assert RAW not in payload


@pytest.mark.parametrize("fault", ["lease-exit", "late-stop", "late-source"])
def test_full_verified_cache_survives_late_failure_without_current_publication(
    full_history, fault
):
    owner, state, _ = full_history
    cancellation = threading.Event()
    if fault == "lease-exit":
        state["exit_failure"] = True

    def progress(message):
        if "finished" in message:
            if fault == "late-stop":
                cancellation.set()
            if fault == "late-source":
                state["source"] = "f" * 64

    with pytest.raises(module.PhysicalCameraSessionError):
        read(
            owner,
            state["header"].header_sha256,
            cancellation=cancellation,
            progress=progress,
        )
    retained = owner.retained_source_workflow()
    assert retained["configuration_epochs"] is not None
    assert len(retained["intake_collections"]) == 8 and node_count(retained) > 4096
    assert owner.view()["status"] == "HELD" and owner._store is None
    assert RAW not in canonical(retained)


@pytest.mark.parametrize(
    "fault",
    [
        "bytes",
        "nodes",
        "depth",
        "duplicate",
        "nonfinite",
        "noncanonical",
        "root",
        "schema",
    ],
)
def test_private_cache_copy_has_its_own_explicit_strict_bounds(fault):
    value = {"schema": module.SOURCE_WORKFLOW_INTAKE_SCHEMA}
    if fault == "bytes":
        payload = b" " * (module.MAX_SOURCE_WORKFLOW_BYTES + 1)
    elif fault == "duplicate":
        payload = b'{"schema":"one","schema":"two"}'
    elif fault == "nonfinite":
        payload = b'{"schema":"rocell.physical_camera_source_workflow_readback.v3","value":1e999}'
    else:
        if fault == "nodes":
            value["items"] = [None] * module.MAX_SOURCE_WORKFLOW_CACHE_NODES
        if fault == "depth":
            nested = value
            for _ in range(module.MAX_SOURCE_WORKFLOW_CACHE_DEPTH + 1):
                nested["child"] = {}
                nested = nested["child"]
        if fault == "root":
            value = []
        if fault == "schema":
            value["schema"] = "other"
        payload = canonical(value) + (b" " if fault == "noncanonical" else b"")
    with pytest.raises(module.PhysicalCameraSessionError):
        module._decode_cached_source_workflow(payload)
