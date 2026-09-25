"""Real M1 stage mutations with explicitly MODELED full-prefix/native seams.

These tests qualify orchestration and failure bookkeeping, not original native
or predecessor authentication. Those readers have separate integration tests.
There is no hardware, process launch, file import endpoint or approval here.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from rocell.application import camera_operating_submission_service as service
from rocell.application.camera_operating_submission import (
    SOURCE_WORKFLOW_OPERATING_SCHEMA,
)
from rocell.application.camera_probe_preparation import SOURCE_WORKFLOW_PROBE_SCHEMA
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState as S
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_submission import seed
from test_camera_operating_submission_persistence import ready_store, stage, fresh_store
from test_commissioning_camera_persistence import (
    WINDOWS,
    forbid_device_and_process_calls,
)
from test_native_camera_activation_supervisor import no_physical_owner

pytestmark = WINDOWS


@pytest.fixture
def modeled_submission(tmp_path, seed, monkeypatch):
    runtime, adapter, subject, waiting = ready_store(tmp_path, seed)
    with stage(adapter) as tx:
        rows = {
            ref.payload_sha256: dict(
                document=json.loads(tx.read_stage_evidence(ref)),
                evidence_sha256=ref.payload_sha256,
                reference=ref.to_dict(),
                retention="M1_FULL_BYTES_READ_BACK",
            )
            for ref in waiting.evidence
            if ref.stage is STAGE_ORDER[4]
        }
    data = subject.to_dict()
    binding = data["binding"]
    original = dict(
        schema=SOURCE_WORKFLOW_PROBE_SCHEMA,
        camera_mode_entry=dict(entry=rows[binding["entry_sha256"]]),
        camera_probe_preparation=dict(
            state="REVIEWED_FOR_ADMISSION",
            preparation=rows[binding["probe_preparation_sha256"]],
            review=rows[binding["probe_review_sha256"]],
            events=[e.to_dict() for e in waiting.committed_events[-2:]],
        ),
    )
    profile = "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    destination = tmp_path / profile
    destination.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[3] / profile, destination)
    calls = []
    attempt = {}

    def prefix(tx, **kwargs):
        # The full prefix is explicitly modeled here, never accepted as such by
        # production. Preserve the actual snapshot/event and exact retained row.
        kwargs["check"]()
        snapshot = tx.snapshot()
        calls.append(("prefix", snapshot))
        if snapshot.head.head_sha256 == waiting.head.head_sha256:
            return snapshot, deepcopy(original)
        return snapshot, dict(
            **{k: v for k, v in original.items() if k != "schema"},
            schema=SOURCE_WORKFLOW_OPERATING_SCHEMA,
            camera_operating_submission=dict(
                state="SUBMITTED_REVIEW_REQUIRED",
                submission=deepcopy(attempt["record"]),
                events=[snapshot.committed_events[-1].to_dict()],
                stage_passed=False,
                approved_operating_policy=False,
                connected=False,
                physical_authority=False,
            ),
        )

    def native(tx, **kwargs):
        calls.append(("MODELED_native", tx.snapshot()))
        assert kwargs["creation_workflow_sha256"] == digest(canonical(original))
        assert kwargs["expected_binding"] == binding
        assert kwargs["submission"].to_dict()["assessment"] == data["assessment"]
        assert kwargs["purchase_profile_payload"] == destination.read_bytes()

    monkeypatch.setattr(service, "_read_original_evidence_under_lease", prefix)
    monkeypatch.setattr(service, "verify_operating_submission_native_inputs", native)
    arguments = dict(
        bound=dict(workspace=str(tmp_path), source_sha256=binding["source_sha256"]),
        expected_header_sha256=waiting.header.header_sha256,
        expected_workflow_payload=canonical(original),
        proposal_payload=canonical(data["proposal"]),
        report=data["assessment"],
        operator_id="MODELED service test",
        attempt=attempt,
        check=lambda **_: None,
        progress=lambda _: None,
    )
    return runtime, adapter, waiting, arguments, calls


def test_one_call_retains_reads_commits_and_fresh_store_does_not_replay(
    modeled_submission,
):
    runtime, adapter, before, arguments, calls = modeled_submission
    with stage(adapter) as tx:
        result = service._retain_in_stage_transaction(tx, **arguments)
        assert tx.snapshot().stages[4].state is S.REVIEW_PENDING
        assert all(s.state is S.PENDING for s in tx.snapshot().stages[5:])
    assert [kind for kind, _ in calls] == ["prefix", "MODELED_native", "prefix"]
    attempt = arguments["attempt"]
    assert attempt["commit"] == "COMMITTED_ORIGINAL_READ_BACK"
    assert attempt["record"]["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert not result["camera_operating_submission"]["approved_operating_policy"]
    assert not result["camera_operating_submission"]["connected"]
    with stage(fresh_store(runtime)) as tx:
        after = tx.snapshot()
        assert len(after.evidence) == len(before.evidence) + 1
        with pytest.raises(WizardError) as error:
            service._retain_in_stage_transaction(tx, **{**arguments, "attempt": {}})
        assert error.value.code == "OPERATING_SUBMISSION_CREATION_HISTORY_CHANGED"
        assert tx.snapshot() == after


@pytest.mark.parametrize("fault", ["history", "native", "stop", "context", "claimed"])
def test_prepublication_holds_do_not_write(modeled_submission, monkeypatch, fault):
    _, adapter, before, arguments, _ = modeled_submission
    if fault == "history":
        arguments["expected_workflow_payload"] = b"{}"
    elif fault == "native":

        def rejected(*args, **kwargs):
            raise ValueError("MODELED native rejection")

        monkeypatch.setattr(
            service, "verify_operating_submission_native_inputs", rejected
        )
    elif fault in ("stop", "context"):

        def interrupted(**kwargs):
            raise WizardError("MODELED_INTERRUPT", fault)

        arguments["check"] = interrupted
    else:
        arguments["attempt"]["already"] = True
    with stage(adapter) as tx:
        with pytest.raises((WizardError, ValueError)):
            service._retain_in_stage_transaction(tx, **arguments)
        assert tx.snapshot() == before


@pytest.mark.parametrize(
    "fault",
    [
        "disk_full",
        "permission",
        "published_no_return",
        "readback",
        "stop_after_write",
        "commit",
        "commit_no_return",
        "final_readback",
    ],
)
def test_failed_boundaries_keep_exact_uncertainty_without_repair(
    modeled_submission, monkeypatch, fault
):
    runtime, adapter, before, arguments, _ = modeled_submission
    store = M1PhysicalCameraTransaction.store_camera_operating_submission
    commit = M1PhysicalCameraTransaction.commit_stage_state
    read = M1PhysicalCameraTransaction.read_stage_evidence
    prefix = service._read_original_evidence_under_lease
    broken = False

    def publication(tx, *args, **kwargs):
        nonlocal broken
        if fault in ("disk_full", "permission"):
            # Storage itself is real; OS failure timing is explicitly injected.
            raise (
                PermissionError("MODELED access denied")
                if fault == "permission"
                else OSError(28, "MODELED disk full")
            )
        reference = store(tx, *args, **kwargs)
        if fault == "published_no_return":
            raise OSError("MODELED lost publication return")
        broken = fault == "stop_after_write"
        return reference

    def readback(tx, reference):
        raw = read(tx, reference)
        return raw + b" " if fault == "readback" else raw

    def committing(tx, *args, **kwargs):
        if fault == "commit":
            raise OSError("MODELED failed journal commit")
        value = commit(tx, *args, **kwargs)
        if fault == "commit_no_return":
            raise OSError("MODELED lost commit return")
        return value

    def final_read(tx, **kwargs):
        value = prefix(tx, **kwargs)
        if fault == "final_readback" and tx.snapshot().head != before.head:
            raise ValueError("MODELED final original read failed")
        return value

    def check(**kwargs):
        if broken:
            raise WizardError(
                "MODELED_STOP_AFTER_WRITE", "Stopped; bytes are not undone."
            )

    monkeypatch.setattr(
        M1PhysicalCameraTransaction, "store_camera_operating_submission", publication
    )
    monkeypatch.setattr(M1PhysicalCameraTransaction, "read_stage_evidence", readback)
    monkeypatch.setattr(M1PhysicalCameraTransaction, "commit_stage_state", committing)
    monkeypatch.setattr(service, "_read_original_evidence_under_lease", final_read)
    arguments["check"] = check
    with stage(adapter) as tx:
        with pytest.raises((OSError, ValueError, WizardError)):
            service._retain_in_stage_transaction(tx, **arguments)
        after = tx.snapshot()
    attempt = arguments["attempt"]
    if fault in ("disk_full", "permission", "published_no_return"):
        assert attempt["record"]["reference"] is None
        assert attempt["record"]["retention"] == "M1_PUBLICATION_UNCONFIRMED"
    elif fault in ("readback", "stop_after_write"):
        assert attempt["record"]["reference"] is not None
        assert attempt["record"]["retention"] == "M1_PUBLISHED_READBACK_PENDING"
    else:
        assert attempt["record"]["retention"] == "M1_FULL_BYTES_READ_BACK"
        assert attempt["commit"] == (
            "COMMITTED_READBACK_PENDING" if fault == "final_readback" else "UNCONFIRMED"
        )
    assert after.stages[4].state is (
        S.REVIEW_PENDING
        if fault in ("commit_no_return", "final_readback")
        else S.WAITING_OPERATOR
    )
    assert len(after.evidence) == len(before.evidence) + (
        fault not in ("disk_full", "permission")
    )
    # Fresh ownership only observes the actual outcome; no implicit repair.
    with stage(fresh_store(runtime)) as tx:
        assert tx.snapshot() == after
