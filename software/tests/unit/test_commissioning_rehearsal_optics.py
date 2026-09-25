"""Substantive stages seven/eight through original Windows M1 stores; no devices."""

from dataclasses import replace
import os
from pathlib import Path
import threading

import pytest

from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application import rehearsal_optics_stages as optics
from rocell.application.wizard_actions import WizardError
from test_commissioning_rehearsal_service import (
    invoke,
    collect,
    assess_review,
    through_identity,
)

WORKSPACE = Path(__file__).resolve().parents[3]
# Real fsync/qualification and two native-sized synthetic datasets per case are
# intentionally multi-minute work. Keep the normal no-device unit lane quick;
# this explicit integration lane still uses the actual original M1 store.
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.name != "nt", reason="Real qualified M1 requires Windows NTFS"
    ),
]


def through_six(root):
    service = CommissioningRehearsalService(
        WORKSPACE, root / "original", source_sha256="a" * 64
    )
    through_identity(service)
    for _ in range(2):
        collect(service)
        campaign = invoke(service, "camera_campaign", frame_count=1, fault="none")
        assert campaign["status"] == "SUCCEEDED", service._receipt
        assess_review(service)
    assert service.view()["stage"] == "optics_intrinsics"
    return service


def reopen(root, name, monkeypatch=None):
    fresh = CommissioningRehearsalService(
        WORKSPACE, root / name, source_sha256="a" * 64
    )
    invoke(fresh, "discover")
    choice = fresh.view()["discovery"]["choices"][0]
    if monkeypatch is None:
        result = invoke(fresh, "reopen", choice_id=choice["choice_id"])
    else:
        from rocell.application import rehearsal_arm_identity_stage as identity
        from rocell.application import rehearsal_power_stages as power
        from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
        from rocell.application.arm_feedback_rehearsal_campaign import (
            ArmFeedbackRehearsalCampaign,
        )

        with monkeypatch.context() as m:
            m.setattr(
                optics,
                "evaluate_rehearsal_optics_stage",
                lambda *a, **k: pytest.fail("reopen replayed evaluator"),
            )
            m.setattr(
                identity,
                "evaluate_rehearsal_arm_identity_stage",
                lambda *a, **k: pytest.fail("reopen replayed identity evaluator"),
            )
            m.setattr(
                power,
                "evaluate_rehearsal_power_stage",
                lambda *a, **k: pytest.fail("reopen replayed power assessor fixtures"),
            )
            m.setattr(
                ArmFeedbackWorker,
                "run",
                lambda *a, **k: pytest.fail("reopen replayed serial worker"),
            )
            m.setattr(
                ArmFeedbackRehearsalCampaign,
                "run_retained_campaign",
                lambda *a, **k: pytest.fail("reopen replayed feedback campaign"),
            )
            result = invoke(fresh, "reopen", choice_id=choice["choice_id"])
    return fresh, result


def test_real_twelve_stage_progression_wait_review_and_pass_reopen(
    tmp_path, monkeypatch
):
    current = through_six(tmp_path)
    events = current.view()["attempt_event_count"]
    collect(current)
    assert current.view()["stage_state"] == "WAITING_OPERATOR"
    assert current.view()["optics_evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
    assert current.view()["optics_evaluation"]["checks"][2]["observed"] == {
        "training": 24,
        "held_out": 8,
    }
    assert current.view()["attempt_event_count"] == events
    assert current.blocked_reason("rehearsal_camera_campaign")
    assert current.blocked_reason("rehearsal_collect")
    current, result = reopen(tmp_path, "unused-wait", monkeypatch)
    assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
    assert current.view()["reopen_result"]["disposition"] == "RECEIPT_READY"
    invoke(current, "assess")
    assert current.view()["assessment"]["outcome"] == "PASS"
    current, result = reopen(tmp_path, "unused-review", monkeypatch)
    assert result["status"] == "SUCCEEDED"
    assert current.view()["stage_state"] == "REVIEW_PENDING"
    with pytest.raises(WizardError, match="differ"):
        invoke(current, "review", reviewer_id="operator-a", accept_assessment=True)
    invoke(current, "review", reviewer_id="reviewer-b", accept_assessment=True)
    assert current.view()["stage"] == "static_registration"
    collect(current)
    assert all(row["passed"] for row in current.view()["optics_evaluation"]["checks"])
    assess_review(current)
    current, result = reopen(tmp_path, "unused-completed", monkeypatch)
    assert result["status"] == "SUCCEEDED"
    assert [row["state"] for row in current.view()["stages"][:8]] == ["PASS"] * 8
    assert current.view()["stage"] == "arm_identity"
    assert current.view()["optics_evaluation"]["stage"] == "static_registration"
    assert current.view()["attempt_event_count"] == events
    assert current.blocked_reason("rehearsal_collect") is None
    assert current.latest_preview() is None
    assert not current._store.snapshot(current.session_id).diagnostic_complete
    assert current.directory == tmp_path / "original"
    assert (
        result["device_open_count"]
        == result["serial_write_count"]
        == result["power_event_count"]
        == 0
    )

    # Continue the same original store. These assessors must not create camera,
    # serial or energy attempts, and reopening must not rerun their fixtures.
    for index, stage in enumerate(
        ("arm_identity", "power_safety", "power_on_observation")
    ):
        assert current.view()["stage"] == stage
        collected = invoke(
            current, "collect", operator_id="operator-a", candidate="synthetic-b0477"
        )
        assert collected["status"] == "SUCCEEDED"
        full_report = collected["steps"][1]["report"]
        assert full_report["binding"]["stage"] == stage
        assert full_report["outcome"] == "REHEARSAL_CHECKS_PASSED"
        assert full_report["authority"]["physical_authority"] is False
        assert {row["check_kind"] for row in full_report["checks"]} >= {
            "NOMINAL",
            "EXPECTED_FAULT",
        }
        assert current.view()["attempt_event_count"] == events
        assert current.blocked_reason("rehearsal_camera_campaign")
        assert current.blocked_reason("rehearsal_collect")
        projection_key = "arm_identity_evaluation" if index == 0 else "power_evaluation"
        projection = current.view()[projection_key]
        assert projection["stage"] == stage
        if index != 1:
            current, result = reopen(tmp_path, "unused-arm-wait-" + stage, monkeypatch)
            assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
            assert current.view()[projection_key] == projection
            assert current.view()["stage_state"] == "WAITING_OPERATOR"
        invoke(current, "assess")
        assert current.view()["assessment"]["outcome"] == "PASS"
        if index == 1:
            # A stop during verification cannot publish a review. Restart then
            # restores the exact assessment and requires another explicit review.
            before_stop = current._store.snapshot(current.session_id)
            cancellation = threading.Event()
            verify = current._verify_arm_setup

            def stopped_verification(*args, **kwargs):
                result = verify(*args, **kwargs)
                cancellation.set()
                return result

            with monkeypatch.context() as m:
                m.setattr(current, "_verify_arm_setup", stopped_verification)
                with pytest.raises(WizardError, match="Stop arrived before"):
                    current.perform(
                        "rehearsal_review",
                        current.bind(
                            "rehearsal_review",
                            {"reviewer_id": "reviewer-b", "accept_assessment": True},
                        ),
                        cancellation=cancellation,
                        progress=lambda _: None,
                    )
            after_stop = current._store.snapshot(current.session_id)
            assert after_stop.head == before_stop.head
            assert after_stop.evidence == before_stop.evidence
            current, result = reopen(tmp_path, "unused-power-review", monkeypatch)
            assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
            assert current.view()["stage_state"] == "REVIEW_PENDING"
            assert current.view()[projection_key] == projection
        with pytest.raises(WizardError, match="differ"):
            invoke(current, "review", reviewer_id="operator-a", accept_assessment=True)
        invoke(current, "review", reviewer_id="reviewer-b", accept_assessment=True)

    current, result = reopen(tmp_path, "unused-eleven-reviewed", monkeypatch)
    assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
    final = current.view()
    assert [row["state"] for row in final["stages"][:11]] == ["PASS"] * 11
    assert all(row["state"] == "PENDING" for row in final["stages"][11:])
    assert final["stage"] == "feedback_only_connection"
    assert final["arm_identity_evaluation"]["stage"] == "arm_identity"
    assert final["power_evaluation"]["stage"] == "power_on_observation"
    assert final["attempt_event_count"] == events
    assert final["physical_authority"] is False
    assert current.blocked_reason("rehearsal_collect") is None
    assert not current._store.snapshot(current.session_id).diagnostic_complete
    assert current.directory == tmp_path / "original"

    # The feedback stage is a coordinator-backed real worker running only its
    # registered memory backend. Opening the stage cannot dispatch that worker.
    collect(current)
    assert current.view()["attempt_event_count"] == events
    assert current.blocked_reason("rehearsal_arm_feedback_campaign") is None
    assert current.blocked_reason("rehearsal_collect")
    current, result = reopen(tmp_path, "unused-feedback-open", monkeypatch)
    assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
    assert current.view()["reopen_result"]["disposition"] == "WAITING_NO_RECEIPT"
    assert current.view()["operator_id"] == "operator-a"
    run = invoke(current, "arm_feedback_campaign")
    assert run["status"] == "SUCCEEDED", current._feedback_diagnostic
    projection = current.view()["arm_feedback_evaluation"]
    assert projection["outcome"] == "REHEARSAL_CHECKS_PASSED"
    assert (
        projection["safe_summary"]["final_power_state"]
        == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    assert projection["safe_summary"]["api_counts"]["write_attempts"] == 1
    assert projection["safe_summary"]["api_counts"]["write_bytes_confirmed"] == 10
    assert (
        projection["final_power_observation"]["observed_power_state"] == "DEENERGIZED"
    )
    assert projection["final_power_observation"]["physical_observation"] is False
    feedback_events = current.view()["attempt_event_count"]
    assert feedback_events == events + 5
    assert current.blocked_reason("rehearsal_arm_feedback_campaign")
    # Safe operation logs deliberately exclude private wire bytes. The M1
    # evidence record retains the complete bounded payload before known sealing.
    diagnostics = run["steps"][1]["report"]
    assert "response_bytes" not in str(diagnostics)
    assert diagnostics["retained_campaign_sha256"]
    current, result = reopen(tmp_path, "unused-feedback-receipt", monkeypatch)
    assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
    assert current.view()["arm_feedback_evaluation"] == projection
    assert current.view()["attempt_event_count"] == feedback_events
    invoke(current, "assess")
    assert current.view()["assessment"]["outcome"] == "PASS"
    current, result = reopen(tmp_path, "unused-feedback-review", monkeypatch)
    assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
    assert current.view()["stage_state"] == "REVIEW_PENDING"
    invoke(current, "review", reviewer_id="reviewer-b", accept_assessment=True)
    current, result = reopen(tmp_path, "unused-twelve-reviewed", monkeypatch)
    assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
    final = current.view()
    assert [row["state"] for row in final["stages"][:12]] == ["PASS"] * 12
    assert final["stage"] == "reference_frame_calibration"
    assert all(row["state"] == "PENDING" for row in final["stages"][12:])
    assert final["attempt_event_count"] == feedback_events
    assert final["physical_authority"] is False
    assert current.blocked_reason("rehearsal_collect")
    assert not current._store.snapshot(current.session_id).diagnostic_complete
    assert current.directory == tmp_path / "original"


def test_failed_actual_nominal_check_is_reviewed_blocked_and_reopens_without_rerun(
    tmp_path, monkeypatch
):
    import rocell.application.b0477_static_vision as vision

    current = through_six(tmp_path)
    collect(current)
    assess_review(current)
    original = vision.run_b0477_static_vision_rehearsal

    def regressed(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.mode is vision.B0477StaticVisionMode.NORMAL:
            return replace(
                result,
                pose_comparison=replace(
                    result.pose_comparison, translation_error_mm=2.0
                ),
                status="REJECTED",
                detail_code="B0477_STATIC_PIXEL_POSE_QUALITY_REJECTED",
            )
        return result

    with monkeypatch.context() as m:
        m.setattr(vision, "run_b0477_static_vision_rehearsal", regressed)
        collect(current)
    invoke(current, "assess")
    assert current.view()["assessment"]["outcome"] == "BLOCKED"
    assert current.view()["assessment"]["reason_codes"] == [
        "OPTICS_CHECK_FAILED:nominal_pose_policy"
    ]
    invoke(current, "review", reviewer_id="reviewer-b", accept_assessment=True)
    assert current.view()["stage_state"] == "BLOCKED"
    fresh, result = reopen(tmp_path, "unused-blocked", monkeypatch)
    assert result["status"] == "SUCCEEDED"
    assert fresh.view()["stage_state"] == "BLOCKED"
    assert fresh.blocked_reason("rehearsal_collect")


@pytest.mark.parametrize("before_probe", [False, True])
def test_cancel_after_evaluation_never_publishes_or_replays_on_reopen(
    tmp_path, monkeypatch, before_probe
):
    current = through_six(tmp_path)
    cancellation = threading.Event()
    original = optics.evaluate_rehearsal_optics_stage

    def stopped(*args, **kwargs):
        report = original(*args, **kwargs)
        cancellation.set()
        return report

    values = current.bind(
        "rehearsal_collect",
        {"operator_id": "operator-a", "candidate": "synthetic-b0477"},
    )
    with monkeypatch.context() as m:
        if before_probe:
            context = current._optics_context

            def stopped_context(*args, **kwargs):
                result = context(*args, **kwargs)
                cancellation.set()
                return result

            m.setattr(current, "_optics_context", stopped_context)
            m.setattr(
                optics,
                "evaluate_rehearsal_optics_stage",
                lambda *a, **k: pytest.fail("Stop must precede the image probe"),
            )
        else:
            m.setattr(optics, "evaluate_rehearsal_optics_stage", stopped)
        with pytest.raises(WizardError, match="No image probe|no result was published"):
            current.perform(
                "rehearsal_collect",
                values,
                cancellation=cancellation,
                progress=lambda _: None,
            )
    assert (
        current._store.snapshot(current.session_id).next_action.stage_state.value
        == "WAITING_OPERATOR"
    )
    assert current._receipt is None
    fresh, result = reopen(tmp_path, "unused-cancelled", monkeypatch)
    assert result["status"] == "FAILED"
    assert fresh._store is None
    assert (
        fresh.view()["reopen_result"]["reasons"][0]["code"] == "OPTICS_RECEIPT_MISSING"
    )


def test_stop_during_assessment_and_review_verification_prevents_publication(
    tmp_path, monkeypatch
):
    current = through_six(tmp_path)
    collect(current)
    for action in ("assess", "review"):
        cancellation = threading.Event()
        original = current._verify_optics

        def stopped_verification(*args, **kwargs):
            result = original(*args, **kwargs)
            cancellation.set()
            return result

        before = current._store.snapshot(current.session_id)
        values = (
            {"reviewer_id": "reviewer-b", "accept_assessment": True}
            if action == "review"
            else {}
        )
        with monkeypatch.context() as m:
            m.setattr(current, "_verify_optics", stopped_verification)
            with pytest.raises(WizardError, match="Stop arrived before"):
                current.perform(
                    "rehearsal_" + action,
                    current.bind("rehearsal_" + action, values),
                    cancellation=cancellation,
                    progress=lambda _: None,
                )
        after = current._store.snapshot(current.session_id)
        assert after.head == before.head
        assert after.evidence == before.evidence
        current, result = reopen(tmp_path, "unused-stop-" + action, monkeypatch)
        assert result["status"] == "SUCCEEDED", current.view()["reopen_result"]
        if action == "assess":
            invoke(current, "assess")
        assert current.view()["stage_state"] == "REVIEW_PENDING"


def test_stage_six_capture_tamper_after_optics_assessment_blocks_review_and_reopen(
    tmp_path,
):
    current = through_six(tmp_path)
    bridge = current.view()["capture_dataset"]
    collect(current)
    invoke(current, "assess")
    path = next((Path(bridge["dataset"]["path"]) / "chunks").glob("*.bin"))
    with path.open("r+b") as stream:
        first = stream.read(1)
        stream.seek(0)
        stream.write(bytes([first[0] ^ 1]))
    with pytest.raises(ValueError):
        invoke(current, "review", reviewer_id="reviewer-b", accept_assessment=True)
    assert (
        current._store.snapshot(current.session_id).next_action.stage_state.value
        == "REVIEW_PENDING"
    )
    fresh, result = reopen(tmp_path, "unused-corrupt-capture")
    assert result["status"] == "FAILED"
    assert fresh._store is None


def test_in_memory_optics_receipt_change_does_not_override_retained_result(tmp_path):
    current = through_six(tmp_path)
    collect(current)
    current._receipt["evaluation"]["outcome"] = "PASS"
    with pytest.raises(WizardError, match="Cached optics receipt"):
        invoke(current, "assess")
    assert current.view()["status"] == "HELD"
    fresh, result = reopen(tmp_path, "unused-intact")
    assert result["status"] == "SUCCEEDED"
    assert fresh._receipt["evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
