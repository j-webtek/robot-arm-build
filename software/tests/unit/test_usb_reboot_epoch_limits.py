"""Private v13 quota geometry over genuine typed but MODELED V2 snapshots.

The shared prerequisite fixture reads controlled requirements only. No original
M1 audit, lease, process or device is performed and no role is qualified here.
"""

from dataclasses import replace

import pytest

from rocell.application import physical_configuration_epochs as epochs
from rocell.application import physical_camera_usb_reboot_constants as constants
from rocell.application.physical_onboarding import STAGE_ORDER
from test_physical_configuration_epochs import epoch_fixture, reference


@pytest.fixture(scope="module")
def boundary():
    prerequisites, snapshot, artifact = epoch_fixture()
    rows = list(snapshot.evidence)
    for index, count in enumerate((31, 3, 80, 67)):
        rows.extend(
            reference(STAGE_ORDER[index], salt=f"MODELED-v13-{index}-{n}")
            for n in range(count)
        )
    snapshot = replace(
        snapshot, evidence=tuple(sorted(rows, key=lambda ref: ref.evidence_id))
    )
    return prerequisites, snapshot, artifact


def verify(case, snapshot=None):
    prerequisites, current, artifact = case
    return epochs._verify_physical_configuration_epochs_after_usb_reboot(
        artifact.payload,
        prerequisites=prerequisites,
        snapshot=current if snapshot is None else snapshot,
        expected_sha256=artifact.sha256,
    )


def test_private_182_references_and_67_stage4_never_expand_public_creation(boundary):
    prerequisites, snapshot, artifact = boundary
    assert len(snapshot.evidence) == 182
    assert [
        sum(ref.stage is stage for ref in snapshot.evidence)
        for stage in STAGE_ORDER[:4]
    ] == [32, 3, 80, 67]
    assert verify(boundary).payload == artifact.payload
    assert all(
        entry["status"] == "UNOBSERVED" for entry in artifact.to_dict()["entries"]
    )
    for old in (
        epochs.verify_physical_configuration_epochs,
        epochs._verify_physical_configuration_epochs_after_usb_absence,
        epochs._verify_physical_configuration_epochs_after_usb_reconnect,
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
    source_only = replace(
        snapshot,
        evidence=tuple(ref for ref in snapshot.evidence if ref.stage is STAGE_ORDER[0]),
    )
    assert len(source_only.evidence) == 32
    epochs.build_physical_configuration_epochs(prerequisites, source_only)
    extra = reference(STAGE_ORDER[0], salt="MODELED-source-over-public32")
    too_many = replace(
        source_only,
        evidence=tuple(
            sorted((*source_only.evidence, extra), key=lambda ref: ref.evidence_id)
        ),
    )
    with pytest.raises(ValueError):
        epochs.build_physical_configuration_epochs(prerequisites, too_many)


@pytest.mark.parametrize("stage", range(5))
def test_no_extra_total_references_or_later_stage_allowance(boundary, stage):
    snapshot = boundary[1]
    extra = reference(STAGE_ORDER[stage], salt="MODELED-extra-not-an-original")
    changed = replace(
        snapshot,
        evidence=tuple(
            sorted((*snapshot.evidence, extra), key=lambda ref: ref.evidence_id)
        ),
    )
    with pytest.raises(ValueError):
        verify(boundary, changed)


def test_stage4_reference_limit_is_independent_of_total_limit(boundary):
    snapshot = boundary[1]
    original_id = boundary[2].to_dict()["original_snapshot"]["evidence_inventory"][0][
        "evidence_id"
    ]
    removable = next(
        ref
        for ref in snapshot.evidence
        if ref.stage is STAGE_ORDER[0] and ref.evidence_id != original_id
    )
    extra = reference(STAGE_ORDER[3], salt="MODELED-stage4-number68")
    changed = replace(
        snapshot,
        evidence=tuple(
            sorted(
                (*(ref for ref in snapshot.evidence if ref != removable), extra),
                key=lambda ref: ref.evidence_id,
            )
        ),
    )
    assert len(changed.evidence) == 182
    assert sum(ref.stage is STAGE_ORDER[3] for ref in changed.evidence) == 68
    with pytest.raises(ValueError):
        verify(boundary, changed)


def test_stage4_8964_kib_exact_cap_is_additive_without_changing_roles(boundary):
    snapshot = boundary[1]
    cap = (4 * 1200 + 300 + 16 + 1136 + 264 + 1224 + 1224) * 1024
    assert cap == 8964 * 1024
    assert sum(constants.USB_REBOOT_ROLE_BYTES.values()) == 1224 * 1024
    stage4 = [ref for ref in snapshot.evidence if ref.stage is STAGE_ORDER[3]]
    first = stage4[0]
    adjusted = replace(
        first, payload_bytes=cap - sum(ref.payload_bytes for ref in stage4[1:])
    )
    at = replace(
        snapshot,
        evidence=tuple(adjusted if ref == first else ref for ref in snapshot.evidence),
    )
    assert verify(boundary, at).payload == boundary[2].payload
    over = replace(
        at,
        evidence=tuple(
            (
                replace(ref, payload_bytes=ref.payload_bytes + 1)
                if ref == adjusted
                else ref
            )
            for ref in at.evidence
        ),
    )
    with pytest.raises(ValueError):
        verify(boundary, over)


@pytest.mark.parametrize(
    "change", ["head", "header", "stage", "missing-original", "duplicate", "unsorted"]
)
def test_private_extension_still_validates_the_complete_actual_snapshot(
    boundary, change
):
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
            stages=(
                replace(snapshot.stages[0], last_event_sequence=None),
                *snapshot.stages[1:],
            ),
        )
    elif change == "duplicate":
        snapshot = replace(
            snapshot, evidence=(*snapshot.evidence[:-1], snapshot.evidence[0])
        )
    elif change == "unsorted":
        snapshot = replace(snapshot, evidence=tuple(reversed(snapshot.evidence)))
    else:
        original = boundary[2].to_dict()["original_snapshot"]["evidence_inventory"][0][
            "evidence_id"
        ]
        snapshot = replace(
            snapshot,
            evidence=tuple(
                ref for ref in snapshot.evidence if ref.evidence_id != original
            ),
        )
    with pytest.raises(ValueError):
        verify(boundary, snapshot)


@pytest.mark.parametrize("flag", [0, 1, None, ""])
def test_private_flag_requires_exact_bool_and_predecessor_extension(boundary, flag):
    prerequisites, snapshot, artifact = boundary
    kwargs = dict(
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=artifact.sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
        usb_absence_extension=True,
        usb_reconnect_extension=True,
        usb_reboot_extension=flag,
    )
    with pytest.raises(ValueError):
        epochs._verify_physical_configuration_epochs(artifact.payload, **kwargs)
    kwargs.update(usb_reboot_extension=True, usb_reconnect_extension=False)
    with pytest.raises(ValueError):
        epochs._verify_physical_configuration_epochs(artifact.payload, **kwargs)
