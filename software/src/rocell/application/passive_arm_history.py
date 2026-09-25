"""Read-only historical diagnostics through the existing wizard action queue."""

from .passive_arm_diagnostic_checkpoint import recover_attempt

ACTION = "inspect_passive_arm_history"


def inspect_history(root, session_id, current_source):
    """Flatten verified originals to stay inside existing wizard depth quotas.

    Reads only one explicitly named session. The source comparison is historical
    context, not a current identity review, admission or resumption decision.
    """
    paired = recover_attempt(root, session_id)
    intent, outcome = paired["intent"], paired["outcome"]
    retained = outcome["retained"] if outcome else {}
    steps = retained.get("result", {}).get("steps", [])
    original = steps[0].get("report", {}) if steps and type(steps[0]) is dict else {}
    matched = paired["status"] == "HISTORICAL_PAIR_VERIFIED"
    report = dict(
        schema="rocell.passive_arm_history_view.v1",
        session_id=session_id,
        pair_status=paired["status"],
        historical_only=True,
        authenticated=False,
        physical_authority=False,
        connected=False,
        replay_allowed=False,
        operation_id=intent["request"]["attempt_id"],
        historical_source_sha256=intent["request"]["references"]["source_sha256"],
        source_matches_current=intent["request"]["references"]["source_sha256"]
        == current_source,
        intent_sha256=intent["sha256"],
        outcome_sha256=outcome["sha256"] if outcome else None,
        process_status=original.get("process", {}).get("status") if matched else None,
        passive_summary=original.get("passive_summary") if matched else None,
        raw_stdout_base64=original.get("raw_stdout_base64") if matched else None,
        raw_stderr_base64=original.get("raw_stderr_base64") if matched else None,
        message=(
            "Historical file association verified; inspect the original test outcome. This is not hardware qualification."
            if matched
            else "Outcome missing or unbound. Inspect original diagnostics; do not replay the attempt."
        ),
    )
    return dict(
        schema="rocell.wizard_worker_result.v1",
        action_id=ACTION,
        status="SUCCEEDED" if matched else "FAILED",
        steps=[
            dict(
                name="passive_arm_history", exit_code=0 if matched else 1, report=report
            )
        ],
        device_open_count=0,
        serial_write_count=0,
        power_event_count=0,
        motion_command_count=0,
        contact_command_count=0,
        metadata_inventory_performed=False,
        physical_authority=False,
    )
