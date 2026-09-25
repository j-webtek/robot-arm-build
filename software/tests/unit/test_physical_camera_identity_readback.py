"""Original identity metadata retention, with explicitly modeled unit facts.

All device and child entrypoints are forbidden. The modeled-scope lane uses
actual immutable V2 histories and production subject codecs, not approval
callbacks. The separate NTFS case uses actual original storage and restart.
"""

from dataclasses import replace
from copy import deepcopy
from threading import Event
from types import SimpleNamespace
import os
import time
from pathlib import Path

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_received_camera_readback import (
    received_ready,
    received_subjects,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    refresh_read,
    initial_epoch,
)
from test_physical_camera_session import SOURCE, LAUNCH

IDENTITY = "cameraidentity-" + "1" * 32
SECOND = "cameraidentity-" + "2" * 32


def label(role, identity_id=IDENTITY):
    return f"camera-identity-{role}-v1:{identity_id}"


def code(phase, identity_id=IDENTITY):
    return "CAMERA_IDENTITY_METADATA_" + phase + "_" + identity_id[15:].upper()


def identity_inputs(
    *,
    source=SOURCE,
    launch=LAUNCH,
    scenario="nominal",
    maximum_inventory=False,
    return_owners=False,
    enrollment_helper_sha256=None,
):
    """Explicitly modeled physical-shaped metadata, real pure owners/codecs.

    Fixed-pin observations below are modeled records, not inspection results
    obtained on this machine. No helper is run, registered for dispatch, or
    qualified; the existing strict registry only validates retained data.
    """
    from rocell.application import wizard_camera_helper_inspection as inspector
    from rocell.application.wizard_camera_helper_registration import (
        WizardCameraHelperRegistration,
    )
    from rocell.application.wizard_native_camera_enrollment import (
        WizardNativeCameraEnrollment,
    )
    from rocell.application.wizard_native_camera_metadata import (
        RehearsalNativeCameraMetadataProvider,
    )
    from rocell.application.physical_camera_selection import (
        selection_from_enrollment_snapshot,
    )
    from test_wizard_native_camera_enrollment import generic_review
    from rocell.application.wizard_device_selection import _candidate, _batch
    from rocell.application.physical_device_inventory import (
        compose_physical_device_inventory_report,
    )

    rows = [
        dict(
            expected,
            observed_sha256=expected["expected_sha256"],
            bytes=pin[3],
            status="MATCHED",
        )
        for expected, pin in zip(inspector._expected_rows("physical"), inspector._PINS)
    ]
    inspected = inspector._report("physical", source, rows)
    helper = WizardCameraHelperRegistration("physical", launch, source)
    helper.ingest(inspected, operation_id="modeled-inspection", operator_id="inspector")
    helper.review("helper-reviewer", operation_id="modeled-helper-review")
    producer = RehearsalNativeCameraMetadataProvider(scenario)
    descriptor = {
        "provenance": "WINDOWS_NATIVE_METADATA",
        "helper_sha256": enrollment_helper_sha256 or inspected["helper_sha256"],
    }
    enrollment = WizardNativeCameraEnrollment("physical", launch, source, descriptor)
    inventory = producer.inventory()
    inventory.update(descriptor)
    if maximum_inventory:
        first = inventory["receipt"]["devices"][0]
        inventory["receipt"]["devices"] = [first] + [
            {**first, "symbolic_link": first["symbolic_link"] + f"-modeled-{index}"}
            for index in range(1, 64)
        ]

    def many_candidates(report):
        if not maximum_inventory:
            return
        first = report["camera_inventory"]["candidates"][0]
        rows = [first]
        for index in range(1, 128):
            row = deepcopy(first)
            row["usb_identity"]["unit_serial"] += f"-MODELED-{index}"
            row["os_instance_id"] += f"-MODELED-{index}"
            row["persistent_ids"] = [
                value + f"-MODELED-{index}" for value in row["persistent_ids"]
            ]
            rows.append(row)
        report["camera_inventory"]["candidates"] = sorted(
            rows, key=lambda row: _candidate(row).sort_key
        )
        composed = compose_physical_device_inventory_report(
            platform_system=report["platform_system"],
            captured_at_unix_ns=report["captured_at_unix_ns"],
            camera_inventory=_batch(report["camera_inventory"]),
            serial_inventory=_batch(report["serial_inventory"]),
        ).to_dict()
        report.clear()
        report.update(composed)

    enrollment.ingest_inventory(
        inventory,
        operation_id="modeled-inventory",
        generic_review=generic_review(
            mode="physical", source=source, session=launch, mutate=many_candidates
        ),
    )
    token = enrollment.choices()[0]["value"]
    identity = producer.identity(enrollment.candidate(token))
    identity.update(descriptor)
    enrollment.retain_identity(token, identity, operation_id="modeled-identity")
    enrollment.review(token, "endpoint-reviewer")
    snapshot = enrollment.export_snapshot()
    selection = selection_from_enrollment_snapshot(
        snapshot, source_sha256=source, launch_session_id=launch
    )
    if return_owners:
        return {"native_camera": enrollment, "helper": helper}
    return dict(
        enrollment=snapshot,
        selection=(
            None
            if selection is None
            else {"document": selection.identity_document, "sha256": selection.sha256}
        ),
        helper_report=helper.export_snapshot(),
    )


def identity_subjects(
    case,
    *,
    enrollment,
    selection,
    helper_report,
    identity_id=IDENTITY,
    sequence=1,
    predecessor=None,
    previous_refs=None,
    phase="reviewed",
    observation=None,
):
    """Production codecs and storage adapters; input snapshots are modeled only."""
    from rocell.application import physical_camera_identity_submission as codec

    owner, prerequisites, state = case
    if predecessor is not None:
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            code("STARTED", identity_id),
            [previous_refs[role] for role in module.IDENTITY_ROLE_BYTES],
            stage=STAGE_ORDER[3],
        )
    if phase == "started":
        return SimpleNamespace(subjects={}, refs={}, predecessor=predecessor)
    received = state["received_subjects"]
    native_view = (
        enrollment.export_snapshot()["view"]
        if hasattr(enrollment, "export_snapshot")
        else enrollment["view"]
    )
    launch = native_view["provenance"]["session_id"]
    binding = {
        "identity_id": identity_id,
        "source_sha256": SOURCE,
        "cell_id": owner.descriptor()["cell_id"],
        "session_id": owner.descriptor()["session_id"],
        "header_sha256": state["header"].header_sha256,
        "origin_launch_id": owner.descriptor()["launch_id"],
        "collection_launch_id": launch,
        "operator_id": "identity-operator",
        "prerequisites_sha256": prerequisites.evidence_sha256,
        "received_camera": {
            role: received.subjects[role].sha256
            for role in ("submission", "assessment", "review")
        },
        "identity_request_event_sha256": next(
            event.event_sha256
            for event in state["events"]
            if event.detail_code.startswith("CAMERA_IDENTITY_REQUESTED_")
        ),
    }
    collected_at = (
        10000
        if predecessor is None
        else predecessor[2].to_dict()["reviewed_at_ns"] + 100
    )
    subjects, refs = {}, {}

    def retain(role, artifact):
        subjects[role] = artifact
        refs[role] = state["add"](
            artifact.payload, label=label(role, identity_id), stage=STAGE_ORDER[3]
        )

    metadata = codec.build_camera_identity_metadata(
        binding, sequence, enrollment, selection, collected_at
    )
    retain("metadata", metadata)
    if phase == "metadata":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    helper = codec.build_camera_identity_helper(
        binding, sequence, helper_report, collected_at
    )
    retain("helper", helper)
    if phase == "helper":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    receipt = codec.build_camera_identity_receipt(
        prerequisites,
        metadata=metadata,
        helper=helper,
        received_submission=received.subjects["submission"],
        metadata_reference=refs["metadata"],
        helper_reference=refs["helper"],
        observation=observation
        or {
            "record_id": "INT-018",
            "state": "UNKNOWN",
            "value": "No received USB identity is claimed.",
            "method": "Modeled metadata only.",
            "evidence_note": "No device was queried or opened.",
        },
        submitted_at_ns=collected_at + 1,
        predecessor=predecessor,
    )
    retain("receipt", receipt)
    if phase == "receipt":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    assessment = codec.assess_camera_identity(
        receipt,
        metadata=metadata,
        helper=helper,
        received_submission=received.subjects["submission"],
    )
    retain("assessment", assessment)
    if phase == "assessment":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    state["advance"](
        v2.V2StageState.REVIEW_PENDING,
        code("COLLECTED", identity_id),
        refs.values(),
        stage=STAGE_ORDER[3],
    )
    if phase == "review-pending":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    review = codec.review_camera_identity(
        receipt,
        assessment,
        decision="ACKNOWLEDGE_EXACT",
        reviewer_id="identity-reviewer",
        review_launch_id=launch,
        reviewed_at_ns=collected_at + 2,
    )
    retain("review", review)
    if phase == "reviewed":
        state["advance"](
            v2.V2StageState.BLOCKED,
            code("REVIEWED_BLOCKED", identity_id),
            refs.values(),
            stage=STAGE_ORDER[3],
        )
    return SimpleNamespace(
        subjects=subjects, refs=refs, predecessor=(receipt, assessment, review)
    )


@pytest.fixture
def identity_ready(received_ready):
    received_ready[2]["received_subjects"] = received_subjects(
        received_ready,
        observed=True,
        identity=True,
    )
    return received_ready


def test_empty_identity_entry_stays_exact_v6(identity_ready):
    result = refresh_read(identity_ready)
    assert result["schema"] == module.SOURCE_WORKFLOW_RECEIVED_SCHEMA
    assert result["camera_identity_request"] is not None
    assert "camera_identity_cycles" not in result


@pytest.mark.parametrize(
    "phase,status",
    [
        ("metadata", "INCOMPLETE"),
        ("helper", "INCOMPLETE"),
        ("receipt", "INCOMPLETE"),
        ("assessment", "ASSESSMENT_RETAINED_NOT_COMMITTED"),
        ("review-pending", "REVIEW_PENDING"),
        ("review-retained", "REVIEW_RETAINED_NOT_COMMITTED"),
        ("reviewed", "REVIEWED_BLOCKED"),
    ],
)
def test_exact_original_identity_prefix_never_infers_commit(
    identity_ready, monkeypatch, phase, status
):
    made = identity_subjects(identity_ready, **identity_inputs(), phase=phase)
    from rocell.application import physical_camera_identity_submission as codec

    def forbidden(*args, **kwargs):
        pytest.fail("Original readback replayed a metadata collection")

    monkeypatch.setattr(codec, "build_camera_identity_metadata", forbidden)
    monkeypatch.setattr(codec, "build_camera_identity_helper", forbidden)
    result = refresh_read(identity_ready)
    assert result["schema"] == module.SOURCE_WORKFLOW_IDENTITY_SCHEMA
    cycle = result["camera_identity_cycles"][0]
    assert cycle["state"] == status
    assert cycle["identity_id"] == IDENTITY
    assert cycle["sequence"] == 1
    for role in module.IDENTITY_ROLE_BYTES:
        if role in made.subjects:
            assert cycle[role] == {
                "document": made.subjects[role].to_dict(),
                "evidence_sha256": made.subjects[role].sha256,
                "reference": made.refs[role].to_dict(),
                "retention": "M1_FULL_BYTES_READ_BACK",
            }
        else:
            assert cycle[role] is None
    snapshot = identity_ready[2]["snapshot"]()
    assert all(row.state is v2.V2StageState.PENDING for row in snapshot.stages[4:])
    saved = identity_ready[0].retained_source_workflow()
    saved["camera_identity_cycles"][0]["state"] = "CALLER_MUTATION"
    assert identity_ready[0].retained_source_workflow() == result


@pytest.mark.parametrize("role", tuple(module.IDENTITY_ROLE_BYTES))
def test_each_identity_role_byte_cap_is_enforced_before_decoding(identity_ready, role):
    _, _, state = identity_ready
    state["add"](
        b" " * (module.IDENTITY_ROLE_BYTES[role] + 1),
        label=label(role),
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(module.PhysicalCameraSessionError) as caught:
        refresh_read(identity_ready)
    assert caught.value.code == "CAMERA_SESSION_READBACK_LIMIT"


@pytest.mark.parametrize(
    "fault",
    [
        "unknown-role",
        "wrong-stage",
        "wrong-media",
        "duplicate-key",
        "non-ascii",
        "future-stage",
        "twenty-one",
    ],
)
def test_closed_scanner_rejects_unowned_or_unbounded_originals(identity_ready, fault):
    _, _, state = identity_ready
    name, stage, media, raw = (
        label("metadata"),
        STAGE_ORDER[3],
        "application/json",
        b"{}",
    )
    if fault == "unknown-role":
        name = label("arbitrary")
    elif fault == "wrong-stage":
        stage = STAGE_ORDER[2]
    elif fault == "wrong-media":
        media = "text/plain"
    elif fault == "duplicate-key":
        raw = b'{"schema":1,"schema":2}'
    elif fault == "non-ascii":
        raw = '{"text":"\u00e9"}'.encode("utf-8")
    elif fault == "future-stage":
        stage = STAGE_ORDER[4]
    for _ in range(21 if fault == "twenty-one" else 1):
        state["add"](raw, label=name, stage=stage, media=media)
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(identity_ready)


@pytest.mark.parametrize(
    "phase",
    [
        "started",
        "metadata",
        "assessment",
        "review-pending",
        "review-retained",
        "reviewed",
    ],
)
def test_only_explicit_reviewed_blocked_successor_is_restored(identity_ready, phase):
    inputs = identity_inputs()
    first = identity_subjects(identity_ready, **inputs)
    second = identity_subjects(
        identity_ready,
        **inputs,
        identity_id=SECOND,
        sequence=2,
        predecessor=first.predecessor,
        previous_refs=first.refs,
        phase=phase,
    )
    result = refresh_read(identity_ready)
    cycles = result["camera_identity_cycles"]
    assert [row["identity_id"] for row in cycles] == [IDENTITY, SECOND]
    assert cycles[0]["state"] == "REVIEWED_BLOCKED"
    assert cycles[0]["receipt"]["document"] == first.subjects["receipt"].to_dict()
    if phase == "started":
        assert cycles[1]["state"] == "INCOMPLETE"
        assert all(cycles[1][role] is None for role in module.IDENTITY_ROLE_BYTES)
    else:
        assert (
            cycles[1]["metadata"]["document"] == second.subjects["metadata"].to_dict()
        )


def test_held_native_mapping_is_retained_without_a_selection_or_pass(identity_ready):
    inputs = identity_inputs(scenario="missing-mapping")
    assert inputs["selection"] is None
    made = identity_subjects(identity_ready, **inputs)
    result = refresh_read(identity_ready)
    row = result["camera_identity_cycles"][0]
    assert row["state"] == "REVIEWED_BLOCKED"
    assert row["metadata"]["document"]["selection"] is None
    assert row["metadata"]["document"] == made.subjects["metadata"].to_dict()
    assert row["assessment"]["document"]["verdict"] == "BLOCKED"


def test_rehashed_receipt_reference_must_name_exact_current_original(identity_ready):
    from rocell.application import physical_camera_identity_submission as codec

    _, _, state = identity_ready
    made = identity_subjects(identity_ready, **identity_inputs(), phase="receipt")
    data = made.subjects["receipt"].to_dict()
    data["metadata_reference"]["evidence_id"] = "evidence-" + "f" * 64
    data["metadata_reference"]["package_sha256"] = "f" * 64
    raw = canonical(data)
    # Still a valid typed reference/receipt; only the original reader has the
    # actual package identity against which to reject this substitution.
    codec.verify_camera_identity_receipt(
        raw,
        prerequisites=identity_ready[1],
        metadata=made.subjects["metadata"],
        helper=made.subjects["helper"],
        received_submission=state["received_subjects"].subjects["submission"],
    )
    ref = made.refs["receipt"]
    state["references"][state["references"].index(ref)] = replace(
        ref, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][ref.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(identity_ready)


def test_partial_pair_rejects_genuine_but_different_metadata_helper_provenance(
    identity_ready,
):
    inputs = identity_inputs(enrollment_helper_sha256="f" * 64)
    made = identity_subjects(identity_ready, **inputs, phase="helper")
    assert len(made.subjects) == 2  # No receipt exists to perform the later join.
    assert (
        made.subjects["metadata"].to_dict()["enrollment"]["view"]["provenance"][
            "helper_sha256"
        ]
        == "f" * 64
    )
    with pytest.raises(module.PhysicalCameraSessionError) as caught:
        refresh_read(identity_ready)
    assert caught.value.code == "CAMERA_SESSION_CAMERA_IDENTITY_CHAIN"


@pytest.mark.parametrize(
    "key",
    [
        "source_sha256",
        "cell_id",
        "session_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
        "received_camera",
        "identity_request_event_sha256",
        "identity_id",
    ],
)
def test_rehashed_metadata_cannot_rebind_original_context(identity_ready, key):
    _, _, state = identity_ready
    made = identity_subjects(identity_ready, **identity_inputs(), phase="metadata")
    document = made.subjects["metadata"].to_dict()
    old = document["binding"][key]
    document["binding"][key] = (
        {name: "f" * 64 for name in old}
        if type(old) is dict
        else "f" * 64 if key.endswith("sha256") else old[:-1] + "9"
    )
    raw = canonical(document)
    ref = made.refs["metadata"]
    state["references"][state["references"].index(ref)] = replace(
        ref, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][ref.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(identity_ready)


@pytest.mark.parametrize(
    "fault",
    [
        "missing-metadata",
        "duplicate-helper",
        "extra-id",
        "collected-wrong-refs",
        "collected-wrong-id",
        "review-pass",
        "early-successor",
        "successor-wrong-refs",
        "source-prefix",
        "static-prefix",
        "received-prefix",
        "uncommitted",
        "stage5",
    ],
)
def test_identity_suffix_preserves_full_original_prefix_and_closed_commit_rules(
    identity_ready, fault
):
    _, _, state = identity_ready
    made = identity_subjects(
        identity_ready,
        **identity_inputs(),
        phase="review-pending" if fault == "early-successor" else "reviewed",
    )
    if fault == "missing-metadata":
        state["references"].remove(made.refs["metadata"])
    elif fault in {"duplicate-helper", "extra-id"}:
        state["add"](
            made.subjects["helper"].payload,
            label=label("helper", SECOND if fault == "extra-id" else IDENTITY),
            stage=STAGE_ORDER[3],
        )
    elif fault in {"collected-wrong-refs", "collected-wrong-id", "review-pass"}:
        index = -1 if fault == "review-pass" else -2
        state["events"][index] = replace(
            state["events"][index],
            **(
                {"evidence": (made.refs["receipt"],)}
                if fault == "collected-wrong-refs"
                else (
                    {"detail_code": code("COLLECTED", SECOND)}
                    if fault == "collected-wrong-id"
                    else {
                        "detail_code": code("REVIEWED_PASS"),
                        "state": v2.V2StageState.PASS,
                    }
                )
            ),
        )
    elif fault in {"early-successor", "successor-wrong-refs"}:
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            code("STARTED", SECOND),
            (
                [made.refs["receipt"]]
                if fault == "successor-wrong-refs"
                else made.refs.values()
            ),
            stage=STAGE_ORDER[3],
        )
    elif fault.endswith("prefix"):
        prefix = {
            "source-prefix": "WORKSPACE_SOURCES_",
            "static-prefix": "STATIC_CAMERA_CONTRACT_COLLECTED_",
            "received-prefix": "CAMERA_RECEIPT_COLLECTION_SUBMITTED_",
        }[fault]
        index = next(
            i
            for i, event in enumerate(state["events"])
            if event.detail_code.startswith(prefix)
        )
        state["events"][index] = replace(
            state["events"][index], detail_code="UNKNOWN_PREFIX"
        )
    elif fault == "uncommitted":
        state["uncommitted"] = (state["events"][-1],)
    elif fault == "stage5":
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_MODE_REQUESTED",
            stage=STAGE_ORDER[4],
        )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(identity_ready)


@pytest.mark.parametrize(
    "fault", ["lease-exit", "coherence", "late-stop", "late-source", "late-deadline"]
)
def test_late_identity_readback_failure_retains_exact_historical_subjects(
    identity_ready, monkeypatch, fault
):
    owner, _, state = identity_ready
    made = identity_subjects(identity_ready, **identity_inputs())
    cancellation = Event()
    state["exit_failure"] = fault == "lease-exit"
    if fault == "coherence":
        state["after_change"] = "session_head_sha256"
    if fault.startswith("late-"):
        original = module._verify_original_source_roles

        def fail_after(*args, **kwargs):
            result = original(*args, **kwargs)
            if fault == "late-stop":
                cancellation.set()
            elif fault == "late-source":
                state["source"] = "f" * 64
            else:
                state["now"] += module.DIAGNOSTIC_TIMEOUT_NS
            return result

        monkeypatch.setattr(module, "_verify_original_source_roles", fail_after)
    with pytest.raises((module.PhysicalCameraSessionError, RuntimeError)):
        refresh_read(identity_ready, cancellation=cancellation)
    result = owner.retained_source_workflow()
    assert (
        canonical(result["camera_identity_cycles"][0]["metadata"]["document"])
        == made.subjects["metadata"].payload
    )
    assert owner.view()["status"] == "HELD"


def structure(value):
    pending, nodes, depth = [(value, 0)], 0, 0
    while pending:
        item, level = pending.pop()
        nodes += 1
        depth = max(depth, level)
        if type(item) is dict:
            for key, child in item.items():
                pending.extend(((key, level + 1), (child, level + 1)))
        elif type(item) is list:
            pending.extend((child, level + 1) for child in item)
    return nodes, depth


def test_full_original_135_reference_budget_and_epoch_is_version_owned(
    source_model, monkeypatch
):
    from rocell.application import physical_configuration_epochs as epochs
    from test_physical_static_contract_readback import (
        enter_static,
        actual_static_subjects,
        retain_static,
    )

    original_epoch = initial_epoch(source_model)
    enter_static(source_model, cycles=7, intake=True, early_originals=1)
    _, prerequisites, state = source_model
    assert len(state["references"]) == 32
    static = actual_static_subjects(source_model, monkeypatch)
    retain_static(source_model, static, camera_entry=True)
    state["static_subjects"] = static
    previous = refs = None
    for index in range(4):
        received = received_subjects(
            source_model,
            receipt_id=f"receivedcamera-{index + 80:032x}",
            predecessor=previous,
            previous_refs=refs,
            media_count=16,
            maximum_text=index < 3,
            observed=index == 3,
            identity=index == 3,
        )
        previous, refs = received.predecessor, received.refs
    state["received_subjects"] = received
    assert len(state["references"]) == 115
    previous = refs = None
    inputs = identity_inputs(maximum_inventory=True)
    for index in range(4):
        made = identity_subjects(
            source_model,
            **inputs,
            identity_id=f"cameraidentity-{index + 100:032x}",
            sequence=index + 1,
            predecessor=previous,
            previous_refs=refs,
        )
        previous, refs = made.predecessor, made.refs
    assert len(state["references"]) == 135
    snapshot = state["snapshot"]()
    original_verify = module._verify_original_source_roles

    def measure_verified(*args, **kwargs):
        result = original_verify(*args, **kwargs)
        measured_nodes, measured_depth = structure(result)
        print(
            f"v7 verified before cache: {len(canonical(result))} bytes, depth {measured_depth}, {measured_nodes} nodes"
        )
        return result

    monkeypatch.setattr(module, "_verify_original_source_roles", measure_verified)
    result = refresh_read(source_model)
    assert len(result["camera_identity_cycles"]) == 4
    assert all(
        row["state"] == "REVIEWED_BLOCKED" for row in result["camera_identity_cycles"]
    )
    assert (
        canonical(result["configuration_epochs"]["document"]) == original_epoch.payload
    )
    wire = canonical(result)
    assert module._decode_cached_source_workflow(wire) == result
    assert len(wire) <= module.MAX_IDENTITY_WORKFLOW_BYTES
    nodes, depth = structure(result)
    assert (
        module.MAX_SOURCE_WORKFLOW_CACHE_NODES
        < nodes
        <= module.MAX_IDENTITY_WORKFLOW_CACHE_NODES
    )
    assert depth <= module.MAX_SOURCE_WORKFLOW_CACHE_DEPTH
    # The new aggregate ceiling never applies to older history schema bytes or
    # individual originals, even if the same large nested structure is supplied.
    for schema in (
        module.SOURCE_WORKFLOW_SCHEMA,
        module.SOURCE_WORKFLOW_RECEIVED_SCHEMA,
    ):
        with pytest.raises(module.PhysicalCameraSessionError):
            module._decode_cached_source_workflow(
                canonical({**result, "schema": schema})
            )
    with pytest.raises(module.PhysicalCameraSessionError):
        module._decode_cached_json_document(
            wire, maximum=module.MAX_IDENTITY_WORKFLOW_BYTES
        )
    print(
        f"v7 bounded cache: {len(wire)} bytes, depth {depth}, {nodes} nodes, 135 references"
    )
    for verify in (
        epochs.verify_physical_configuration_epochs,
        epochs._verify_physical_configuration_epochs_after_static,
        epochs._verify_physical_configuration_epochs_after_received_camera,
    ):
        with pytest.raises(epochs.PhysicalConfigurationEpochError):
            verify(
                original_epoch.payload,
                prerequisites=prerequisites,
                snapshot=snapshot,
                expected_sha256=original_epoch.sha256,
            )
    assert (
        epochs._verify_physical_configuration_epochs_after_camera_identity(
            original_epoch.payload,
            prerequisites=prerequisites,
            snapshot=snapshot,
            expected_sha256=original_epoch.sha256,
        ).payload
        == original_epoch.payload
    )
    state["advance"](
        v2.V2StageState.WAITING_OPERATOR,
        code("STARTED", "cameraidentity-" + "f" * 32),
        refs.values(),
        stage=STAGE_ORDER[3],
    )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model)


def test_v7_cache_aggregate_limit_is_finite_and_depth_stays_unchanged():
    # Private copy-boundary tests, not valid original records or subject approval.
    for value in (
        {
            "schema": module.SOURCE_WORKFLOW_IDENTITY_SCHEMA,
            "items": [None] * module.MAX_IDENTITY_WORKFLOW_CACHE_NODES,
        },
        {
            "schema": module.SOURCE_WORKFLOW_RECEIVED_SCHEMA,
            "items": [None] * module.MAX_SOURCE_WORKFLOW_CACHE_NODES,
        },
    ):
        with pytest.raises(module.PhysicalCameraSessionError):
            module._decode_cached_source_workflow(canonical(value))
    nested = None
    for _ in range(module.MAX_SOURCE_WORKFLOW_CACHE_DEPTH + 1):
        nested = [nested]
    with pytest.raises(module.PhysicalCameraSessionError):
        module._decode_cached_source_workflow(
            canonical(
                {"schema": module.SOURCE_WORKFLOW_IDENTITY_SCHEMA, "nested": nested}
            )
        )


def actual_transaction_state(tx):
    """The fixture API backed by actual M1 writes and exact original readback."""

    def add(payload, *, label, stage=STAGE_ORDER[0], media="application/json"):
        ref = tx.store_evidence(
            stage,
            payload,
            label=label,
            media_type=media,
            captured_at_ns=time.time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        assert tx.read_stage_evidence(ref) == payload
        return ref

    def advance(state, detail, refs=(), *, stage=STAGE_ORDER[0]):
        tx.commit_stage_state(
            stage,
            state,
            occurred_at_ns=time.time_ns(),
            detail_code=detail,
            evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )

    return dict(add=add, advance=advance, snapshot=tx.snapshot)


def actual_identity_entry(
    workspace, monkeypatch, *, include_configuration_epochs=False
):
    """Real isolated source/static/received originals, modeled physical facts.

    No prior test is invoked or replayed. Existing pure fixture builders bind
    newly retained subjects to this exact new store's real header/references.
    """
    from test_physical_camera_session import session_fixture, perform
    from test_physical_camera_session_readback import generate
    from test_physical_camera_source_workflow_readback import collect_chain
    from test_physical_camera_intake_session import SOURCE_CODES
    from test_physical_static_contract_readback import (
        enter_static,
        actual_static_subjects,
        retain_static,
    )
    from rocell.application.physical_configuration_epochs import (
        build_physical_configuration_epochs,
    )

    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    sources = collect_chain(prerequisites, header, monkeypatch)
    with owner.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:
        state = actual_transaction_state(tx)
        add, advance = state["add"], state["advance"]
        state.update(header=tx.snapshot().header, source_artifacts=sources)
        advance(v2.V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
        add(prerequisites.payload, label=module.PREREQUISITE_LABEL)
        if include_configuration_epochs:
            epochs = build_physical_configuration_epochs(
                prerequisites, tx.snapshot(), evidence_bindings=()
            )
            add(epochs.payload, label=module.CONFIGURATION_EPOCH_LABEL)
        refs = {
            role: add(sources[role].payload, label=f"workspace-source-{role}-v1")
            for role in ("receipt", "assessment")
        }
        advance(v2.V2StageState.REVIEW_PENDING, SOURCE_CODES[1], refs.values())
        refs["review"] = add(
            sources["review"].payload, label="workspace-source-review-v1"
        )
        advance(v2.V2StageState.BLOCKED, SOURCE_CODES[2], refs.values())
        state["source_refs"] = refs
        case = owner, prerequisites, state
        enter_static(case)
        state["events"] = tx.snapshot().committed_events
        static = actual_static_subjects(case, monkeypatch)
        retain_static(case, static, camera_entry=True)
        state["static_subjects"] = static
        state["events"] = tx.snapshot().committed_events
        state["received_subjects"] = received_subjects(
            case, observed=True, identity=True
        )
    perform(owner, "refresh")
    return case


@pytest.mark.skipif(os.name != "nt", reason="Actual original NTFS owner required")
def test_actual_ntfs_identity_partial_review_and_explicit_successor_reopen(
    workspace, monkeypatch
):
    """Real immutable storage/restart, explicitly modeled device facts only."""
    from test_physical_camera_session import session_fixture, perform
    from test_physical_camera_intake_session import read
    from rocell.application import physical_camera_identity_submission as codec

    case = actual_identity_entry(workspace, monkeypatch)
    owner, prerequisites, state = case
    header = state["header"].header_sha256
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        state.update(
            actual_transaction_state(tx), events=tx.snapshot().committed_events
        )
        made = identity_subjects(case, **identity_inputs(), phase="assessment")
        expected_head = tx.snapshot().head.head_sha256

    def reopened(expected_state, count=1):
        fresh = session_fixture(workspace)
        current = perform(fresh, "refresh")
        result = read(fresh, header)
        assert result["schema"] == module.SOURCE_WORKFLOW_IDENTITY_SCHEMA
        assert result["session_head_sha256"] == expected_head
        assert len(result["camera_identity_cycles"]) == count
        assert result["camera_identity_cycles"][-1]["state"] == expected_state
        for role, artifact in made.subjects.items():
            assert (
                canonical(result["camera_identity_cycles"][0][role]["document"])
                == artifact.payload
            )
        assert result["original_source_state"] == "BLOCKED"
        assert result["received_camera_cycles"][-1]["state"] == "REVIEWED_PASS"
        assert all(row["state"] == "PENDING" for row in current["stages"][4:])
        return fresh, result

    owner, _ = reopened("ASSESSMENT_RETAINED_NOT_COMMITTED")
    review = codec.review_camera_identity(
        made.subjects["receipt"],
        made.subjects["assessment"],
        decision="ACKNOWLEDGE_EXACT",
        reviewer_id="identity-reviewer",
        review_launch_id=LAUNCH,
        reviewed_at_ns=10002,
    )
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        current = actual_transaction_state(tx)
        current["advance"](
            v2.V2StageState.REVIEW_PENDING,
            code("COLLECTED"),
            made.refs.values(),
            stage=STAGE_ORDER[3],
        )
        made.subjects["review"] = review
        made.refs["review"] = current["add"](
            review.payload, label=label("review"), stage=STAGE_ORDER[3]
        )
        expected_head = tx.snapshot().head.head_sha256
    owner, _ = reopened("REVIEW_RETAINED_NOT_COMMITTED")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        actual_transaction_state(tx)["advance"](
            v2.V2StageState.BLOCKED,
            code("REVIEWED_BLOCKED"),
            made.refs.values(),
            stage=STAGE_ORDER[3],
        )
        expected_head = tx.snapshot().head.head_sha256
    owner, full = reopened("REVIEWED_BLOCKED")
    full_wire = canonical(full)
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        actual_transaction_state(tx)["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            code("STARTED", SECOND),
            made.refs.values(),
            stage=STAGE_ORDER[3],
        )
        expected_head = tx.snapshot().head.head_sha256
    _, partial = reopened("INCOMPLETE", 2)
    assert partial["camera_identity_cycles"][0] == full["camera_identity_cycles"][0]
    assert canonical(full) == full_wire
    assert all(
        partial["camera_identity_cycles"][1][role] is None
        for role in module.IDENTITY_ROLE_BYTES
    )
