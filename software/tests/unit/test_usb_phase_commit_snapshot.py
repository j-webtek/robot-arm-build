"""Transaction-local commit projection; no files, processes or devices.

The actual V2/M1 post-sync readback contract is covered by their persistence
tests. This isolates the service's consumption of that returned snapshot.
"""

from types import SimpleNamespace

import pytest

from rocell.application.physical_usb_trial_service import _UsbTrialBaseline, STAGE
from rocell.application.physical_camera_usb_phase import usb_phase_event
from rocell.application.physical_onboarding_v2 import V2StageState


def test_commit_uses_the_returned_post_sync_snapshot_without_duplicate_read():
    calls = []
    committed = object()
    before = SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64))
    after = SimpleNamespace(committed_events=[committed])
    refs = [SimpleNamespace(evidence_id="second"), SimpleNamespace(evidence_id="first")]

    def snapshot():
        calls.append("snapshot")
        assert calls == ["snapshot"], "No redundant full post-commit snapshot"
        return before

    def commit(stage, state, **kwargs):
        calls.append("commit")
        assert stage is STAGE and state is V2StageState.WAITING_OPERATOR
        assert kwargs["expected_head_sha256"] == before.head.head_sha256
        assert kwargs["detail_code"] == usb_phase_event(
            "PREPARATION_REQUESTED", "usbphase-" + "1" * 32
        )
        assert kwargs["evidence"] == tuple(reversed(refs))
        assert type(kwargs["occurred_at_ns"]) is int and kwargs["occurred_at_ns"] > 0
        return after

    tx = SimpleNamespace(snapshot=snapshot, commit_stage_state=commit)
    assert (
        _UsbTrialBaseline._commit(
            tx,
            "PREPARATION_REQUESTED",
            V2StageState.WAITING_OPERATOR,
            "usbphase-" + "1" * 32,
            refs,
        )
        is committed
    )
    assert calls == ["snapshot", "commit"]


def test_failed_commit_is_not_replaced_by_another_snapshot():
    calls = []

    def snapshot():
        calls.append("snapshot")
        return SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64))

    def commit(*args, **kwargs):
        calls.append("commit")
        raise RuntimeError("MODELED_POST_SYNC_READBACK_FAILURE")

    with pytest.raises(RuntimeError, match="MODELED_POST_SYNC_READBACK_FAILURE"):
        _UsbTrialBaseline._commit(
            SimpleNamespace(snapshot=snapshot, commit_stage_state=commit),
            "PREPARATION_REQUESTED",
            V2StageState.WAITING_OPERATOR,
            "usbphase-" + "1" * 32,
            [],
        )
    assert calls == ["snapshot", "commit"]
