"""Pure v16 subjects/layout with explicitly modeled software and old history.

The entry fixture cannot pass predecessor authentication. No original store,
software file verification, native process, camera or arm is accessed here.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import camera_probe_preparation as subject
from rocell.application.camera_probe_preparation_layout import (
    verify_camera_probe_preparation_layout,
)
from rocell.application.camera_activation_runtime_policy import (
    reviewed_activation_runtime_candidate,
    REVIEW_SCHEMA,
)
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_mode_entry_layout import (
    _camera_mode_entry_extension,
    verify_camera_mode_entry_layout,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import (
    V2CommittedHead,
    V2JournalEvent,
    V2StageSnapshot,
    V2StageState as S,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_camera_mode_entry_layout import case, entry, binding, reference, no_effects
from test_camera_activation_service_handoff import service_enrollment, LAUNCH, SOURCE
from test_camera_probe_preparation_readback import prepared_subject, current_enrollment
from test_physical_camera_identity_readback import identity_inputs


def preparation_for(case, workspace):
    service = PhysicalCameraAcquisitionService(
        workspace, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
    )
    enrollment = service_enrollment()
    plan = service.preview_activation_plan("probe", enrollment)
    plan.update(cell_id=case.binding["cell_id"], session_id=case.binding["session_id"])
    software = {}
    for purpose in ("probe", "capture"):
        runtime = reviewed_activation_runtime_candidate(
            workspace, purpose=purpose, source_sha256=SOURCE
        )
        software[purpose] = dict(
            schema=REVIEW_SCHEMA,
            status="REVIEWED_SOFTWARE_MATCHED",
            purpose=purpose,
            runtime_registration_sha256=runtime.registration_sha256,
            catalog_sha256=runtime.to_dict()["catalog_sha256"],
            source_sha256=SOURCE,
            files_checked=26,
            bytes_read=123456,
            read_calls=53,
            elapsed_ns=1_000_000,
            original_context_authenticated=False,
            physical_authority=False,
            connected=False,
            hardware_qualified=False,
            device_operations=0,
        )
    return subject.build_camera_probe_preparation(
        preparation_id="cameraprobe-" + "1" * 32,
        entry_sha256=case.entry.sha256,
        entry_event_sha256=case.snapshot.committed_events[-1].event_sha256,
        plan=plan,
        enrollment=enrollment.export_snapshot(),
        software=software,
        operator_id="MODELED preparer",
        prepared_at_utc_ns=70,
    )


def attach(case, preparation, *, events=2, review=True):
    refs, packages = list(case.snapshot.evidence), {}
    records = [("preparation", preparation)]
    if review:
        records.append(
            (
                "review",
                subject.build_camera_probe_preparation_review(
                    preparation, reviewer_id="MODELED reviewer", reviewed_at_utc_ns=90
                ),
            )
        )
    for kind, item in records:
        ref = reference(item.payload, kind, STAGE_ORDER[4])
        refs.append(ref)
        packages[ref.evidence_id] = dict(
            kind=kind,
            preparation_id=item.to_dict()["preparation_id"],
            record=dict(
                document=item.to_dict(),
                evidence_sha256=item.sha256,
                reference=ref.to_dict(),
                retention="M1_FULL_BYTES_READ_BACK",
            ),
        )
    journal = list(case.snapshot.committed_events)
    prep_ref = refs[-2] if review else refs[-1]
    for number in range(events):
        previous = journal[-1]
        cited = (
            (prep_ref,)
            if number == 0
            else tuple(sorted(refs[-2:], key=lambda ref: ref.evidence_id))
        )
        journal.append(
            V2JournalEvent.build(
                header=case.snapshot.header,
                sequence=len(journal),
                stage=STAGE_ORDER[4],
                previous_state=previous.state,
                state=S.BLOCKED if number == 0 else S.WAITING_OPERATOR,
                occurred_at_ns=80 if number == 0 else 100,
                previous_event_sha256=previous.event_sha256,
                evidence=cited,
                detail_code=subject.camera_probe_event(
                    "PREPARED" if number == 0 else "REVIEWED",
                    preparation.to_dict()["preparation_id"],
                ),
            )
        )
    stages = list(case.snapshot.stages)
    ids = tuple(
        ref.evidence_id
        for event in journal
        if event.stage is STAGE_ORDER[4]
        for ref in event.evidence
    )
    stages[4] = V2StageSnapshot(
        STAGE_ORDER[4], journal[-1].state, journal[-1].sequence, ids
    )
    snapshot = replace(
        case.snapshot,
        evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
        stages=tuple(stages),
        committed_events=tuple(journal),
        head=V2CommittedHead.build(case.snapshot.header, tuple(journal)),
    )
    return snapshot, packages


def test_preparation_and_review_reverify_without_restoring_live_enrollment(
    case, tmp_path
):
    prep = preparation_for(case, tmp_path)
    assert subject.CameraProbePreparation(prep.payload).sha256 == prep.sha256
    data = prep.to_dict()
    data["connected"] = True
    assert prep.to_dict()["connected"] is False
    review = subject.build_camera_probe_preparation_review(
        prep, reviewer_id="MODELED reviewer", reviewed_at_utc_ns=90
    )
    assert review.to_dict()["preparation_sha256"] == prep.sha256
    with pytest.raises(ValueError):
        subject.build_camera_probe_preparation_review(
            prep, reviewer_id="r", reviewed_at_utc_ns=69
        )


def test_full_supported_inventory_uses_a_separate_record_budget(case, tmp_path):
    from rocell.providers.windows.owned_worker_process import decode_owned_json

    original = {
        "camera_mode_entry": {
            "entry": {"evidence_sha256": case.entry.sha256},
            "events": [case.snapshot.committed_events[-1].to_dict()],
        }
    }
    bound = dict(
        workspace=str(tmp_path),
        directory=str(tmp_path / "software/runs/physical-camera-acquisition" / LAUNCH),
        source_sha256=SOURCE,
        cell_id=case.binding["cell_id"],
        session_id=case.binding["session_id"],
    )
    previous = identity_inputs(source=SOURCE, launch=LAUNCH, maximum_inventory=True)[
        "enrollment"
    ]
    prep = prepared_subject(original, bound, previous=previous)
    assert (
        len(prep.to_dict()["enrollment"]["inventory_packet"]["receipt"]["devices"])
        == 64
    )
    assert subject.CameraProbePreparation(prep.payload).payload == prep.payload
    with pytest.raises(ValueError, match="IPC_STRUCTURE_LIMIT"):
        decode_owned_json(prep.payload, maximum=subject.MAX_PREPARATION_BYTES)


def test_current_context_join_uses_the_actual_metadata_schema(case, tmp_path):
    from rocell.application.camera_probe_preparation_readback import (
        _verify_current_subject_context,
    )
    from rocell.application.physical_camera_mode_entry import (
        SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
    )

    previous = identity_inputs(source=SOURCE, launch=LAUNCH)["enrollment"]
    original = {
        "schema": SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
        "camera_mode_entry": {
            "state": "ENTERED",
            "entry": {"evidence_sha256": case.entry.sha256},
            "events": [case.snapshot.committed_events[-1].to_dict()],
        },
        "usb_qualification_reboot": {"enrollment": {"document": previous}},
    }
    bound = dict(
        workspace=str(tmp_path),
        directory=str(tmp_path / "software/runs/physical-camera-acquisition" / LAUNCH),
        source_sha256=SOURCE,
        cell_id=case.binding["cell_id"],
        session_id=case.binding["session_id"],
    )
    prep = prepared_subject(original, bound, previous=previous)
    # Only independent context consistency is tested here; this modeled prefix
    # is intentionally insufficient for the full original-history verifier.
    _verify_current_subject_context(original, SimpleNamespace(preparation=prep), bound)


@pytest.mark.parametrize(
    "payload",
    [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b"[]", b"\xff", b"{} trailing"],
)
def test_record_decoder_rejects_malformed_json(payload):
    with pytest.raises(ValueError):
        subject.CameraProbePreparation(payload)


def test_record_parser_has_finite_byte_node_and_depth_limits():
    too_many = canonical({"x": [0] * subject.MAX_PREPARATION_NODES})
    too_deep = (
        b'{"x":' * (subject.MAX_PREPARATION_DEPTH + 1)
        + b"0"
        + b"}" * (subject.MAX_PREPARATION_DEPTH + 1)
    )
    for payload in (too_many, too_deep, b" " * (subject.MAX_PREPARATION_BYTES + 1)):
        with pytest.raises(ValueError):
            subject.CameraProbePreparation(payload)


def test_modeled_fresh_collection_preserves_observed_driver_fields():
    previous = service_enrollment().export_snapshot()
    previous["identity_packet"]["receipt"]["driver"]["provider"][
        "value"
    ] = "MODELED previously accepted provider"
    # Reissue through the real owner with explicitly modeled packets; never
    # mutate a retained original or infer that this fixture was OS-observed.
    current = current_enrollment(previous, source=SOURCE).export_snapshot()
    assert (
        current["identity_packet"]["receipt"]["driver"]["provider"]
        == previous["identity_packet"]["receipt"]["driver"]["provider"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "authority",
        "identity",
        "purpose",
        "runtime",
        "missing-software",
        "software-runtime",
        "software-source",
        "software-count",
        "software-effect",
        "timestamp",
        "operator",
    ],
)
def test_preparation_refuses_self_inconsistent_or_permission_claiming_subject(
    case, tmp_path, fault
):
    prep = preparation_for(case, tmp_path)
    data = prep.to_dict()
    if fault == "extra":
        data["approved"] = True
    elif fault == "authority":
        data["native_release_allowed"] = True
    elif fault == "identity":
        data["enrollment"]["binding_artifact"]["binding_sha256"] = "e" * 64
    elif fault == "purpose":
        data["plan"]["purpose"] = "capture"
    elif fault == "runtime":
        data["plan"]["runtime"]["helper"]["sha256"] = "e" * 64
    elif fault == "missing-software":
        data["software"].pop("capture")
    elif fault == "software-runtime":
        data["software"]["probe"]["runtime_registration_sha256"] = "e" * 64
    elif fault == "software-source":
        data["software"]["capture"]["source_sha256"] = "e" * 64
    elif fault == "software-count":
        data["software"]["probe"]["files_checked"] = True
    elif fault == "software-effect":
        data["software"]["probe"]["device_operations"] = 1
    elif fault == "timestamp":
        data["prepared_at_utc_ns"] = True
    else:
        data["operator_id"] = "../bad\noperator"
    with pytest.raises(ValueError):
        subject.CameraProbePreparation(canonical(data))


@pytest.mark.parametrize(
    "events,review,state",
    [
        (0, False, "INCOMPLETE"),
        (1, False, "PREPARED_REVIEW_REQUIRED"),
        (1, True, "INCOMPLETE"),
        (2, True, "REVIEWED_FOR_ADMISSION"),
    ],
)
def test_complete_snapshot_suffix_never_changes_predecessor_or_grants_authority(
    case, tmp_path, events, review, state
):
    prep = preparation_for(case, tmp_path)
    snapshot, packages = attach(case, prep, events=events, review=review)
    before = deepcopy(snapshot)
    layout = verify_camera_probe_preparation_layout(snapshot, case.record, packages)
    assert layout.state == state and layout.original_store_authenticated is False
    assert snapshot == before
    ids, count = _camera_mode_entry_extension(snapshot, layout)
    assert ids == frozenset((case.ref.evidence_id, *packages)) and count == events + 1
    assert all(row.state is S.PENDING for row in snapshot.stages[5:])
    with pytest.raises(ValueError):
        verify_camera_mode_entry_layout(
            snapshot,
            case.record,
            expected_entry_id=case.entry.to_dict()["entry_id"],
            expected_binding=case.binding,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "missing-role",
        "alias",
        "duplicate",
        "unreviewed",
        "future",
        "entry-hash",
        "event",
        "row",
        "forged-layout",
    ],
)
def test_suffix_mismatch_cannot_supply_a_predecessor_allowance(case, tmp_path, fault):
    prep = preparation_for(case, tmp_path)
    snapshot, packages = attach(case, prep)
    if fault == "missing-role":
        packages = {k: v for k, v in packages.items() if v["kind"] == "review"}
    elif fault == "alias":
        packages["alias"] = packages.pop(next(iter(packages)))
    elif fault == "duplicate":
        packages["extra"] = deepcopy(next(iter(packages.values())))
    elif fault == "unreviewed":
        snapshot, packages = attach(case, prep, events=0, review=True)
    elif fault == "future":
        extra = reference(b"unexpected stage 6", "future", STAGE_ORDER[5])
        snapshot = replace(snapshot, evidence=(*snapshot.evidence, extra))
    elif fault == "entry-hash":
        data = prep.to_dict()
        data["entry_sha256"] = "e" * 64
        snapshot, packages = attach(
            case, subject.CameraProbePreparation(canonical(data))
        )
    elif fault == "event":
        snapshot = replace(snapshot, committed_events=snapshot.committed_events[:-1])
    elif fault == "row":
        snapshot = replace(snapshot, stages=case.snapshot.stages)
    else:
        layout = verify_camera_probe_preparation_layout(snapshot, case.record, packages)
        with pytest.raises(ValueError):
            _camera_mode_entry_extension(snapshot, replace(layout, state="PASS"))
        return
    with pytest.raises(ValueError):
        verify_camera_probe_preparation_layout(snapshot, case.record, packages)
