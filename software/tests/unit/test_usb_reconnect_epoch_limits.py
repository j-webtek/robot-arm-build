"""Pure v12 quota geometry, not package authenticity or physical observations."""

from dataclasses import replace

import pytest

from rocell.application import physical_configuration_epochs as epochs
from rocell.application.physical_onboarding import STAGE_ORDER
from test_physical_configuration_epochs import epoch_fixture, reference


@pytest.fixture(scope="module")
def boundary():
    prerequisites, snapshot, artifact = epoch_fixture()
    rows = list(snapshot.evidence)
    for index, count in enumerate((31, 3, 80, 56)):
        rows.extend(
            reference(STAGE_ORDER[index], salt=f"MODELED-v12-{index}-{n}")
            for n in range(count)
        )
    snapshot = replace(
        snapshot, evidence=tuple(sorted(rows, key=lambda row: row.evidence_id))
    )
    return prerequisites, snapshot, artifact


def verify(case, snapshot=None):
    prerequisites, current, artifact = case
    return epochs._verify_physical_configuration_epochs_after_usb_reconnect(
        artifact.payload,
        prerequisites=prerequisites,
        snapshot=current if snapshot is None else snapshot,
        expected_sha256=artifact.sha256,
    )


def test_additive_snapshot_has_171_refs_but_original_epoch_creation_stays_32(boundary):
    prerequisites, snapshot, artifact = boundary
    assert len(snapshot.evidence) == 171
    assert verify(boundary).payload == artifact.payload
    for old in (
        epochs.verify_physical_configuration_epochs,
        epochs._verify_physical_configuration_epochs_after_usb_absence,
    ):
        with pytest.raises(ValueError):
            old(
                artifact.payload,
                prerequisites=prerequisites,
                snapshot=snapshot,
                expected_sha256=artifact.sha256,
            )
    with pytest.raises(ValueError):
        epochs.build_physical_configuration_epochs(prerequisites, snapshot)


@pytest.mark.parametrize("stage", range(5))
def test_no_extra_refs_or_later_stage_allowance(boundary, stage):
    snapshot = boundary[1]
    extra = reference(
        STAGE_ORDER[stage], salt="MODELED-extra-not-an-authenticated-role"
    )
    changed = replace(
        snapshot,
        evidence=tuple(
            sorted((*snapshot.evidence, extra), key=lambda row: row.evidence_id)
        ),
    )
    with pytest.raises(ValueError):
        verify(boundary, changed)


def test_stage4_exact_bytecap_is_sum_of_unchanged_role_caps(boundary):
    snapshot = boundary[1]
    stage4 = [r for r in snapshot.evidence if r.stage is STAGE_ORDER[3]]
    cap = (4 * 1200 + 300 + 16 + 1136 + 264 + 1224) * 1024
    first = stage4[0]
    adjusted = replace(
        first, payload_bytes=cap - sum(r.payload_bytes for r in stage4[1:])
    )
    at = replace(
        snapshot,
        evidence=tuple(adjusted if r == first else r for r in snapshot.evidence),
    )
    verify(boundary, at)
    over = replace(
        at,
        evidence=tuple(
            replace(r, payload_bytes=r.payload_bytes + 1) if r == adjusted else r
            for r in at.evidence
        ),
    )
    with pytest.raises(ValueError):
        verify(boundary, over)


@pytest.mark.parametrize("change", ["head", "header", "stage", "missing-original"])
def test_extension_still_checks_actual_complete_snapshot(boundary, change):
    snapshot = boundary[1]
    if change == "head":
        snapshot = replace(snapshot, head=replace(snapshot.head, head_sha256="f" * 64))
    elif change == "header":
        snapshot = replace(
            snapshot, header=replace(snapshot.header, source_binding_sha256="f" * 64)
        )
    elif change == "stage":
        snapshot = replace(
            snapshot,
            stages=tuple(
                replace(s, evidence_ids=()) if i == 0 else s
                for i, s in enumerate(snapshot.stages)
            ),
        )
        # The initial wait has no citations; alter its recorded sequence instead.
        snapshot = replace(
            snapshot,
            stages=(
                replace(snapshot.stages[0], last_event_sequence=None),
                *snapshot.stages[1:],
            ),
        )
    else:
        original_id = boundary[2].to_dict()["original_snapshot"]["evidence_inventory"][
            0
        ]["evidence_id"]
        snapshot = replace(
            snapshot,
            evidence=tuple(
                r for r in snapshot.evidence if r.evidence_id != original_id
            ),
        )
    with pytest.raises(ValueError):
        verify(boundary, snapshot)
