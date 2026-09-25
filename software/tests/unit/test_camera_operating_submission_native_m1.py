"""Real M1 rejection of a modeled submission without original native inputs.

The storage test deliberately models stage/native content. This proves that the
narrow writer alone cannot promote that content through the new native reader.
It is a negative NTFS test, not the outstanding three-attempt success acceptance.
"""

import pytest

from rocell.application.camera_operating_submission_native import (
    verify_operating_submission_native_inputs,
)
from rocell.application.camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
)
from rocell.application.physical_camera_mode_entry import CameraModeEntry
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_submission_persistence import (
    ready_store,
    stage,
    fresh_store,
    write,
    WINDOWS,
    seed,
    M1CommissioningPersistenceError,
    forbid_device_and_process_calls,
)

pytestmark = WINDOWS


def test_real_retained_compound_does_not_invent_its_missing_native_originals(
    tmp_path, seed
):
    runtime, adapter, subject, waiting = ready_store(tmp_path, seed)
    with stage(adapter) as tx:
        reference = write(tx, subject, waiting.head.head_sha256)
    with stage(fresh_store(runtime)) as tx:
        before = tx.snapshot()
        records = canonical(tx._audit_records(include_family=True))
        binding = subject.to_dict()["binding"]
        subjects = {}
        for name, key, cls in (
            ("entry", "entry_sha256", CameraModeEntry),
            ("preparation", "probe_preparation_sha256", CameraProbePreparation),
            ("review", "probe_review_sha256", CameraProbePreparationReview),
        ):
            refs = [
                ref for ref in before.evidence if ref.payload_sha256 == binding[key]
            ]
            assert len(refs) == 1
            subjects[name] = cls(tx.read_stage_evidence(refs[0]))
        assert tx.read_stage_evidence(reference) == subject.payload
        # Exact real scope, packages and campaign audit; the fictional attempt
        # from the modeled assessment must not be supplied by launch memory.
        with pytest.raises(
            M1CommissioningPersistenceError,
            match="retained campaign permit is missing or ambiguous",
        ):
            verify_operating_submission_native_inputs(
                tx,
                submission=subject,
                expected_binding=binding,
                **subjects,
                creation_workflow_sha256=digest(b"MODELED creation workflow"),
                purchase_profile_payload=b"MODELED unused purchase input",
            )
        assert tx.snapshot() == before
        assert canonical(tx._audit_records(include_family=True)) == records
        assert not subject.to_dict()["stage_passed"]
