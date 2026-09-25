"""Full original-prefix routing with MODELED storage and a modeled native seam.

The full prior stage codecs run unchanged. Only the new native-submission join
is replaced explicitly here, so this is NOT three-attempt M1/native acceptance.
No device, capture permission, stage approval or original history is fabricated
in production by this fixture.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from rocell.application import camera_operating_submission_readback as reader
from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_complete_readback as complete
from rocell.application.camera_operating_submission import (
    SOURCE_WORKFLOW_OPERATING_SCHEMA,
    build_camera_operating_submission,
    camera_operating_submission_label,
    camera_operating_submission_event,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.physical_onboarding_v2 import V2StageState as S
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_submission import seed
from test_camera_probe_preparation_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    prepare_reviewed,
    refresh_read,
    change_last_event,
)


@pytest.mark.parametrize("packages", [None, [], {}, {"a": {}}, {"a": {}, "b": {}}])
def test_unknown_submission_package_has_no_prefix_or_native_fallback(packages):
    with pytest.raises(ValueError):
        reader.read_camera_operating_submission_layout(None, packages, {}, packages)


def test_creation_envelope_uses_journal_inventory_encoding_without_changing_input():
    # Isolate this pure re-projection after modeled layout authentication. The
    # journal adds a newline; native IPC does not. Those digests must not mix.
    def reference(name):
        return SimpleNamespace(evidence_id=name, to_dict=lambda: {"id": name})

    snapshot = SimpleNamespace(evidence=(reference("old"), reference("submission")))
    layout = SimpleNamespace(
        reference=snapshot.evidence[1],
        submission=SimpleNamespace(
            to_dict=lambda: {"binding": {"journal_head_sha256": "a" * 64}}
        ),
    )
    original = {
        "session_head_sha256": "current",
        "evidence_inventory_sha256": "current",
        "unchanged": "subject",
    }
    saved = deepcopy(original)
    projected = reader._creation_workflow(original, snapshot, layout)
    assert projected["session_head_sha256"] == "a" * 64
    assert projected["evidence_inventory_sha256"] == canonical_sha256([{"id": "old"}])
    assert projected["evidence_inventory_sha256"] != digest(canonical([{"id": "old"}]))
    assert original == saved and projected["unchanged"] == "subject"


def test_complete_prefix_same_snapshot_creation_digest_and_native_failure(
    ready, monkeypatch, seed
):
    _, preparation, review = prepare_reviewed(ready, monkeypatch)
    original = refresh_read(ready)
    original_bytes = canonical(original)
    bound, state = ready[0].descriptor(), ready[2]
    before = state["snapshot"]()
    entry = original["camera_mode_entry"]["entry"]
    proposal = json.loads(seed["proposal_payload"])
    proposal["entry_binding"] = deepcopy(entry["document"]["binding"])
    proposal["subjects"]["entry_sha256"] = entry["evidence_sha256"]
    for key in ("source_sha256", "session_id"):
        proposal["probe_binding"][key] = proposal["entry_binding"][key]
    report = json.loads(seed["assessment_payload"])
    report["proposal_sha256"] = digest(canonical(proposal))
    report["preflight"]["proposal_sha256"] = report["proposal_sha256"]
    report["preflight_sha256"] = digest(canonical(report["preflight"]))
    report.update(
        session_id=before.header.session_id,
        header_sha256=before.header.header_sha256,
        journal_head_sha256=before.head.head_sha256,
        original_records_sha256=digest(canonical({})),
    )
    binding = dict(
        **{
            k: proposal["entry_binding"][k]
            for k in ("source_sha256", "cell_id", "session_id", "header_sha256")
        },
        entry_sha256=entry["evidence_sha256"],
        probe_preparation_sha256=preparation.sha256,
        probe_review_sha256=review.sha256,
        journal_head_sha256=before.head.head_sha256,
        original_records_sha256=report["original_records_sha256"],
    )
    now = max(
        before.committed_events[-1].occurred_at_ns + 1, seed["recorded_at_utc_ns"]
    )
    subject = build_camera_operating_submission(
        submission_id=seed["submission_id"],
        operator_id=seed["operator_id"],
        recorded_at_utc_ns=now,
        binding=binding,
        proposal_payload=canonical(proposal),
        assessment_payload=canonical(report),
    )
    reference = state["add"](
        subject.payload,
        label=camera_operating_submission_label(seed["submission_id"]),
        stage=STAGE_ORDER[4],
    )
    profile = "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    target = Path(bound["workspace"]) / profile
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[3] / profile, target)
    calls, snapshots = [], []
    old_prefix = complete._verify_usb_complete_prefix

    def prefix(*args, **kwargs):
        snapshots.append(args[1])
        return old_prefix(*args, **kwargs)

    def modeled_native(transaction, **kwargs):
        # Explicit seam: the synthetic new assessment has no native originals.
        # Independently check the arguments supplied AFTER full prefix verification.
        assert transaction is state["transaction"]
        assert kwargs["expected_binding"] == binding
        assert kwargs["creation_workflow_sha256"] == digest(original_bytes)
        assert kwargs["entry"].payload == canonical(entry["document"])
        assert kwargs["preparation"] == preparation and kwargs["review"] == review
        assert kwargs["purchase_profile_payload"] == target.read_bytes()
        calls.append(kwargs)
        return {"MODELED_NATIVE_SEAM_NOT_ORIGINAL_PROOF": True}

    monkeypatch.setattr(complete, "_verify_usb_complete_prefix", prefix)
    monkeypatch.setattr(
        reader, "verify_operating_submission_native_inputs", modeled_native
    )
    partial = refresh_read(ready)
    assert partial["schema"] == SOURCE_WORKFLOW_OPERATING_SCHEMA
    assert partial["camera_operating_submission"]["state"] == "INCOMPLETE"
    assert state["snapshot"]().stages[4].state is S.WAITING_OPERATOR
    assert snapshots[-1] == state["snapshot"]()
    # Model the normal journal suffix separately; no resumed production action.
    state["advance"](
        S.REVIEW_PENDING,
        camera_operating_submission_event(seed["submission_id"]),
        (reference,),
        stage=STAGE_ORDER[4],
    )
    change_last_event(state, occurred_at_ns=now + 1)
    committed = refresh_read(ready)
    assert snapshots[-1] == state["snapshot"]()
    assert len(calls) == 2
    row = committed["camera_operating_submission"]
    assert row["state"] == "SUBMITTED_REVIEW_REQUIRED"
    assert row["submission"]["document"] == subject.to_dict()
    assert (
        row["stage_passed"]
        is row["approved_operating_policy"]
        is row["connected"]
        is False
    )
    assert all(stage.state is S.PENDING for stage in state["snapshot"]().stages[5:])
    assert session._decode_cached_source_workflow(canonical(committed)) == committed
    assert canonical(original) == original_bytes

    def failed_native(*args, **kwargs):
        raise ValueError("MODELED_NATIVE_ORIGINAL_MISSING")

    monkeypatch.setattr(
        reader, "verify_operating_submission_native_inputs", failed_native
    )
    snapshot = state["snapshot"]()
    with pytest.raises(
        session.PhysicalCameraSessionError, match="CAMERA_SESSION_READBACK_FAILED"
    ) as failure:
        refresh_read(ready)
    assert str(failure.value.__cause__) == "MODELED_NATIVE_ORIGINAL_MISSING"
    assert state["snapshot"]() == snapshot
    assert ready[0].view()["status"] == "HELD" and ready[0]._store is None
