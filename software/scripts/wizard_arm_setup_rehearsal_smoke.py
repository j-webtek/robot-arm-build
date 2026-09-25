"""Exercise eleven stages, optionally through fourteen, with original-store restarts.

Only new rehearsal/log/export records are created. No host device inventory,
camera or serial endpoint, energy action, robot motion or contact is used.
Source must stay fixed for the complete multi-minute run. With --serve the final
reopened startup assessment awaits an explicit browser review; without it, the
public API reviews it. Exports are diagnostic reports, not physical authority.
With --feedback, also run the actual memory-only arm worker and reopen its
retained stage-twelve assessment. --serve then waits for that browser review.
With --owned-feedback (implies --feedback), select the separate contained
incapable arm child instead. No physical port, power or fallback is enabled.
With --reference (implies --feedback), also exercise nominal reference fitting,
full evidence export and receipt/assessment reopening. No installed calibration
or physical reference bootstrap is acquired by this rehearsal.
With --noncontact (implies --reference and --feedback), retain and reopen the
NC-01 gap report. It must end at noncontact BLOCKED, not handoff acceptance.
That finite full-workflow mode requires an exact --expected-source-sha256 and
cannot be combined with --serve or --verify-completed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.ui.server import create_wizard_server, run_wizard_server
from wizard_optics_rehearsal_smoke import export
from wizard_noncontact_smoke import action, replay_guards, require_frozen_source


def verify_resolution_export(
    service: ArrivalWizardService, *, full_trace: bool
) -> None:
    """Check the assigned diagnostic attachment, not device/M1 qualification."""
    from rocell.application.arm_controller_resolution import ControllerResolutionTrace

    folder = Path(service.view()["exports"]["items"][-1]["path"])
    document = json.loads(
        (folder / "attachment-owned-arm-connection.json").read_bytes()
    )
    assert document["original_bytes_preserved"] is True
    diagnostic = document["diagnostics"]
    summary = service.view()["commissioning_rehearsal"]["arm_feedback_process"]
    assert diagnostic["arm_feedback_process"] == summary
    trace = diagnostic["controller_resolution"]
    assert trace["trace_sha256"] == summary["resolution"]["trace_sha256"]
    if full_trace:
        assert trace["status"] == "RETAINED"
        raw = json.dumps(
            trace["trace"], sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        retained = ControllerResolutionTrace(raw)
        assert (
            retained.sha256 == hashlib.sha256(raw).hexdigest() == trace["trace_sha256"]
        )
        assert retained.safe_summary() == summary["resolution"]
    else:
        assert trace["status"] == "FULL_TRACE_NOT_RESTORED_USE_ORIGINAL_M1"
        assert trace["trace"] is None
    print(
        "verified controller-resolution export",
        folder,
        trace["status"],
        trace["trace_sha256"],
        flush=True,
    )


def run_owned_feedback(service: ArrivalWizardService) -> None:
    """Attempt once; retain an ordinary diagnostic export on a reported failure.

    Exporting does not retry the campaign, repair the original store or turn
    incomplete evidence into an assessment. An export failure must not hide
    the original campaign exception.
    """
    try:
        action(service, "rehearsal_owned_arm_feedback_campaign", scenario="nominal")
    except Exception as original:
        if (
            getattr(original, "failure_export_attempted", False) is True
            or getattr(original, "further_actions_prohibited", False) is True
        ):
            raise
        try:
            export(service)
        except Exception as export_error:
            print(
                "Failure diagnostics export also failed:",
                type(export_error).__name__,
                flush=True,
            )
        raise


def review(service: ArrivalWizardService, reviewer: str = "arm-setup-reviewer") -> None:
    action(service, "rehearsal_review", reviewer_id=reviewer, accept_assessment=True)


def reopen_original(service: ArrivalWizardService, before: dict) -> None:
    unused = Path(service.view()["commissioning_rehearsal"]["directory"])
    action(service, "rehearsal_discover")
    choices = service.view()["commissioning_rehearsal"]["discovery"]["choices"]
    selected = next(c for c in choices if c["session_id"] == before["session_id"])
    assert selected["source_matches"] is True
    action(service, "rehearsal_reopen", choice_id=selected["choice_id"])
    after = service.view()["commissioning_rehearsal"]
    for key in (
        "session_id",
        "cell_id",
        "directory",
        "journal_head_sha256",
        "assessment",
        "stage",
        "stage_state",
        "arm_identity_evaluation",
        "power_evaluation",
        "arm_feedback_evaluation",
        "arm_feedback_process",
        "reference_evaluation",
    ):
        assert after[key] == before[key], key
    assert not unused.exists()
    assert service.view()["camera"]["image_id"] is None
    assert all(row["state"] == "PHYSICAL_PENDING" for row in service.view()["stages"])


def collect_assess(service: ArrivalWizardService, index: int) -> None:
    current = service.view()["commissioning_rehearsal"]
    assert current["stage"] == STAGE_ORDER[index].value
    action(service, "rehearsal_collect", operator_id="arm-setup-operator")
    if index == 4:
        action(service, "rehearsal_camera_settings", brightness_offset=0)
    if index in (4, 5):
        action(service, "rehearsal_camera_campaign", frame_count=1, fault="none")
    action(service, "rehearsal_assess")
    current = service.view()["commissioning_rehearsal"]
    assert current["assessment"]["outcome"] == "PASS", current["assessment"]
    assert current["physical_authority"] is False


def verify_completed(
    workspace: Path, session_id: str, *, reference: bool = False
) -> None:
    """Reopen one explicitly selected completed store with replay forbidden.

    This developer-only check creates a new diagnostic log/export, not a new
    rehearsal. Fail-fast method guards prove reconstruction does not rerun
    the camera/arm workers or upstream synthetic evaluators.
    """
    service = ArrivalWizardService(workspace)
    try:
        print("source", service.source_sha256, flush=True)
        with replay_guards():
            action(service, "rehearsal_discover")
            choices = service.view()["commissioning_rehearsal"]["discovery"]["choices"]
            choice = next(c for c in choices if c["session_id"] == session_id)
            assert choice["source_matches"] is True, "Never rebase an old source"
            action(service, "rehearsal_reopen", choice_id=choice["choice_id"])
            current = service.view()["commissioning_rehearsal"]
            assert current["session_id"] == session_id
            count = 13 if reference else 12
            assert [row["state"] for row in current["stages"][:count]] == [
                "PASS"
            ] * count
            assert current["stage"] == STAGE_ORDER[count].value
            assert current["attempt_event_count"] == 15
            assert (
                current["arm_feedback_evaluation"]["outcome"]
                == "REHEARSAL_CHECKS_PASSED"
            )
            assert all(
                row["state"] == "PHYSICAL_PENDING" for row in service.view()["stages"]
            )
            if reference:
                assert (
                    current["reference_evaluation"]["outcome"]
                    == "REHEARSAL_CHECKS_PASSED"
                )
            export(service)
            print(
                f"Completed {count}-stage original store verified with replay forbidden",
                flush=True,
            )
    finally:
        service.shutdown()


def run_reference_stage(
    workspace: Path,
    source: str,
    service: ArrivalWizardService,
    *,
    serve: bool,
    noncontact: bool = False,
) -> None:
    """Retain, reopen and review stage13 without changing the original source."""
    if noncontact and serve:
        raise ValueError(
            "Noncontact smoke is finite and cannot wait for browser review"
        )
    current_service = service
    try:
        action(current_service, "rehearsal_collect", operator_id="reference-operator")
        before = current_service.view()["commissioning_rehearsal"]
        assert before["stage"] == "reference_frame_calibration"
        assert before["stage_state"] == "WAITING_OPERATOR"
        assert before["reference_evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
        assert before["attempt_event_count"] == 15  # Pure math adds no device attempt.
        export(current_service)  # Full report is still in this launch's results.
        current_service.shutdown()
        current_service = ArrivalWizardService(workspace)
        assert (
            current_service.source_sha256 == source
        ), "Never migrate a source-bound store"
        reopen_original(current_service, before)
        action(current_service, "rehearsal_assess")
        before = current_service.view()["commissioning_rehearsal"]
        assert before["stage_state"] == "REVIEW_PENDING"
        assert before["assessment"]["outcome"] == "PASS"
        export(current_service)
        current_service.shutdown()
        current_service = ArrivalWizardService(workspace)
        assert (
            current_service.source_sha256 == source
        ), "Never migrate a source-bound store"
        reopen_original(current_service, before)
        if serve:
            print(
                "Original stage-thirteen reference assessment awaits fresh browser review",
                flush=True,
            )
            server = create_wizard_server(current_service)
            print("Browser QA:", server.launch_url, flush=True)
            run_wizard_server(server)
            return
        review(current_service, "reference-reopen-reviewer")
        current = current_service.view()["commissioning_rehearsal"]
        assert [row["state"] for row in current["stages"][:13]] == ["PASS"] * 13
        assert current["stage"] == "noncontact_acceptance"
        assert current["attempt_event_count"] == 15
        assert all(
            row["state"] == "PHYSICAL_PENDING"
            for row in current_service.view()["stages"]
        )
        export(current_service)
        print(
            "Thirteen rehearsal stages reviewed; physical calibration and later stages held",
            flush=True,
        )
    finally:
        current_service.shutdown()
    # The noninteractive path has completed stage 13. Verify its original
    # retained store only after releasing the final launch; all evaluators,
    # package builders and both feedback workers are forbidden during reopen.
    # The --serve branch returned above and must never infer browser approval.
    verify_completed(workspace, current["session_id"], reference=True)
    if noncontact:
        from wizard_noncontact_smoke import run_noncontact_stage

        run_noncontact_stage(workspace, source, current)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--feedback", action="store_true")
    parser.add_argument("--owned-feedback", action="store_true")
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--noncontact", action="store_true")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--verify-completed", metavar="SESSION_ID")
    args = parser.parse_args(argv)
    if args.noncontact and (args.serve or args.verify_completed):
        parser.error("--noncontact cannot combine with --serve or --verify-completed")
    if args.noncontact and not args.expected_source_sha256:
        parser.error("--noncontact requires --expected-source-sha256")
    args.reference = args.reference or args.noncontact
    args.feedback = args.feedback or args.reference or args.owned_feedback
    workspace = Path(__file__).resolve().parents[2]
    if args.expected_source_sha256 is not None:
        # Read-only source proof precedes any new log or original-store creation.
        require_frozen_source(workspace, args.expected_source_sha256)
    if args.verify_completed:
        verify_completed(workspace, args.verify_completed, reference=args.reference)
        return
    original = ArrivalWizardService(workspace)
    source = original.source_sha256
    try:
        if args.expected_source_sha256 is not None:
            assert source == args.expected_source_sha256, "Source changed before launch"
        print("source", source, flush=True)
        action(original, "rehearsal_initialize")
        for index in range(8):
            collect_assess(original, index)
            review(original)
        before = original.view()["commissioning_rehearsal"]
        assert before["stage"] == "arm_identity"
        print("original session", before["session_id"], flush=True)
        print("original directory", before["directory"], flush=True)
        export(original)
    finally:
        original.shutdown()

    second = ArrivalWizardService(workspace)
    try:
        assert (
            second.source_sha256 == source
        ), "Source changed; do not migrate the store"
        reopen_original(second, before)
        attempts = second.view()["commissioning_rehearsal"]["attempt_event_count"]
        for index in range(8, 11):
            collect_assess(second, index)
            if index < 10:
                review(second)
        before = second.view()["commissioning_rehearsal"]
        assert before["stage"] == "power_on_observation"
        assert before["stage_state"] == "REVIEW_PENDING"
        assert before["attempt_event_count"] == attempts
        assert before["arm_identity_evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
        assert before["power_evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
        # Eight retained full results fit this phase: export before a later
        # action evicts the identity report from the per-launch memory history.
        export(second)
        print(
            "arm setup evaluation",
            before["power_evaluation"]["evaluation_sha256"],
            flush=True,
        )
    finally:
        second.shutdown()

    final = ArrivalWizardService(workspace)
    try:
        assert final.source_sha256 == source, "Source changed; do not migrate the store"
        reopen_original(final, before)
        if args.serve and not args.feedback:
            print(
                "Original stage-eleven assessment awaits fresh explicit browser review",
                flush=True,
            )
            server = create_wizard_server(final)
            print("Browser QA:", server.launch_url, flush=True)
            run_wizard_server(server)
            return
        review(final, "arm-setup-reopen-reviewer")
        current = final.view()["commissioning_rehearsal"]
        assert [row["state"] for row in current["stages"][:11]] == ["PASS"] * 11
        assert current["stage"] == "feedback_only_connection"
        assert all(row["state"] == "PHYSICAL_PENDING" for row in final.view()["stages"])
        assert next(
            row
            for row in final.view()["actions"]
            if row["action_id"] == "rehearsal_collect"
        )["enabled"]
        if args.feedback:
            action(final, "rehearsal_collect", operator_id="arm-setup-operator")
            # Test continuation from a durable stage opening, with no campaign
            # attempted. Restart never supplies an implicit approval or worker.
            before = final.view()["commissioning_rehearsal"]
            assert before["stage_state"] == "WAITING_OPERATOR"
            assert before["attempt_event_count"] == attempts
            final.shutdown()
            final = ArrivalWizardService(workspace)
            assert (
                final.source_sha256 == source
            ), "Source changed; do not migrate the store"
            reopen_original(final, before)
            if args.owned_feedback:
                run_owned_feedback(final)
            else:
                action(final, "rehearsal_arm_feedback_campaign")
            # The complete private result and stage receipt must survive a
            # different launch before any assessment exists. Only reconstruction
            # is permitted: the one completed exchange cannot be repeated.
            before = final.view()["commissioning_rehearsal"]
            assert before["attempt_event_count"] == attempts + 5
            assert (
                before["arm_feedback_evaluation"]["outcome"]
                == "REHEARSAL_CHECKS_PASSED"
            )
            if args.owned_feedback:
                process = before["arm_feedback_process"]
                assert process["status"] == "COMPLETE_INCAPABLE_EVIDENCE"
                assert process["process"]["status"] == "SUCCEEDED"
                assert process["process"]["tree_exit_confirmed"] is True
                assert process["native"]["native_cleanup_confirmed"] is True
                assert process["schema"] == "rocell.arm_owned_evidence_summary.v2"
                assert process["resolution"]["status"] == "PRE_WRITE_MATCHED"
                assert process["resolution"]["attempt_count"] == 2
                assert (
                    process["final_power_state"]
                    == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
                )
                print("retained owned evidence", process["evidence_sha256"], flush=True)
                # Ordinary history rotation must not discard the complete
                # connection diagnostic attachment before explicit export.
                for index in range(9):
                    action(
                        final,
                        "record_note",
                        note=f"Owned connection export rotation check {index}",
                    )
            export(final)
            if args.owned_feedback:
                verify_resolution_export(final, full_trace=True)
            final.shutdown()
            final = ArrivalWizardService(workspace)
            assert (
                final.source_sha256 == source
            ), "Source changed; do not migrate the store"
            reopen_original(final, before)
            action(final, "rehearsal_assess")
            before = final.view()["commissioning_rehearsal"]
            assert before["stage"] == "feedback_only_connection"
            assert before["stage_state"] == "REVIEW_PENDING"
            assert before["assessment"]["outcome"] == "PASS"
            assert before["attempt_event_count"] == attempts + 5
            assert (
                before["arm_feedback_evaluation"]["safe_summary"][
                    "serial_cleanup_confirmed"
                ]
                is True
            )
            assert (
                before["arm_feedback_evaluation"]["safe_summary"]["final_power_state"]
                == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
            )
        export(final)
        if args.owned_feedback:
            verify_resolution_export(final, full_trace=False)
        print(
            (
                "Stage-twelve assessment retained; fresh browser review remains pending"
                if args.feedback and args.serve and not args.reference
                else "Rehearsal checkpoint retained; physical and later stages held"
            ),
            flush=True,
        )
    finally:
        final.shutdown()

    if args.feedback:
        feedback = ArrivalWizardService(workspace)
        try:
            assert (
                feedback.source_sha256 == source
            ), "Source changed; do not migrate the store"
            reopen_original(feedback, before)
            if args.serve and not args.reference:
                print(
                    "Original stage-twelve feedback assessment awaits fresh explicit browser review",
                    flush=True,
                )
                server = create_wizard_server(feedback)
                print("Browser QA:", server.launch_url, flush=True)
                run_wizard_server(server)
                return
            review(feedback, "feedback-reopen-reviewer")
            current = feedback.view()["commissioning_rehearsal"]
            assert [row["state"] for row in current["stages"][:12]] == ["PASS"] * 12
            assert current["stage"] == "reference_frame_calibration"
            assert current["attempt_event_count"] == attempts + 5
            assert all(
                row["state"] == "PHYSICAL_PENDING" for row in feedback.view()["stages"]
            )
            export(feedback)
            print(
                "Twelve rehearsal stages reviewed; physical and later stages held",
                flush=True,
            )
            if args.reference:
                run_reference_stage(
                    workspace,
                    source,
                    feedback,
                    serve=args.serve,
                    noncontact=args.noncontact,
                )
            elif args.owned_feedback:
                # Explicit historical verification forbids both campaign paths,
                # package rebuilding and worker replay after stage-12 review.
                verify_completed(workspace, current["session_id"])
        finally:
            feedback.shutdown()


if __name__ == "__main__":
    main()
