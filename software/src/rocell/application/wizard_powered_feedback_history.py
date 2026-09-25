"""Read-only historical powered attempts; no replay, repair or device access."""

from .powered_feedback_attempt_store import collect_attempt

ACTION = "inspect_powered_feedback_history"


def inspect_history(root, attempt_id):
    collected = collect_attempt(root, attempt_id)
    records = [
        {key: value for key, value in record.items() if key != "base64_chunks"}
        for record in collected["records"]
    ]
    found = any(record["status"] == "BYTES_RETAINED" for record in records)
    readable = all(record["status"] != "UNREADABLE" for record in records)
    # SUCCEEDED means inspection returned readable bytes, even if malformed or
    # incomplete. It does not mean the historical operation or device succeeded.
    status = "SUCCEEDED" if found and readable else "FAILED"
    result = {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": ACTION,
        "status": status,
        "steps": [
            {
                "name": "powered_feedback_history",
                "exit_code": 0 if status == "SUCCEEDED" else 1,
                "report": {
                    "status": (
                        "HISTORICAL_BYTES_ONLY" if found else "NO_READABLE_HISTORY"
                    ),
                    "attempt_id": attempt_id,
                    "records": records,
                    "historical_only": True,
                    "chain_verified": False,
                    "connected": False,
                    "replay_allowed": False,
                    "physical_authority": False,
                },
            }
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }
    return result, collected
