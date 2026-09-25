"""Read-only timing summary for a retained full-history test checkpoint.

This is a developer diagnostic, not the original-store/export verifier. It
never imports providers, opens devices, reruns attempts, or writes a report.
Nested inclusive durations overlap; their sums are NOT exclusive CPU costs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any


MAX_CHECKPOINT_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 4096
TRACE_SCHEMA = "rocell.test_camera_admission_timing_trace.v1"
TIMING_SEMANTICS = "INCLUSIVE_NESTED_SPANS_DO_NOT_SUM_AS_EXCLUSIVE"


class TimingSummaryError(ValueError):
    """Malformed or unavailable observations, never a failed hardware verdict."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise TimingSummaryError(message)


def _integer(value: Any, name: str) -> int:
    _need(type(value) is int and 0 <= value < 2**63, f"Invalid {name} integer.")
    return value


def _label(value: Any, name: str, limit: int) -> str:
    _need(
        type(value) is str
        and 1 <= len(value) <= limit
        and re.fullmatch(r"[A-Za-z0-9_.-]+", value) is not None,
        f"Invalid {name} label.",
    )
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in result, "Duplicate JSON field.")
        result[key] = value
    return result


def summarize_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Aggregate bounded diagnostic observations; do not authenticate inputs.

    In-progress and dropped spans remain visible. No deadline pass, exclusive
    cost, feasibility, or physical permission is inferred from any duration.
    """
    _need(type(checkpoint) is dict, "Checkpoint must be an object.")
    source = checkpoint.get("executing_source_sha256")
    _need(
        type(source) is str and re.fullmatch(r"[0-9a-f]{64}", source) is not None,
        "Checkpoint source fingerprint is missing or malformed.",
    )
    trace = checkpoint.get("admission_timing_trace")
    if type(trace) is not dict:
        raise TimingSummaryError("No admission timing trace in this checkpoint.")
    _need(trace.get("schema") == TRACE_SCHEMA, "Unsupported timing schema.")
    _need(
        trace.get("timing_semantics") == TIMING_SEMANTICS,
        "Only inclusive nested timing observations are supported.",
    )
    limit = _integer(trace.get("max_entries"), "entry cap")
    _need(1 <= limit <= MAX_ENTRIES, "Timing entry cap is outside its bound.")
    entries = trace.get("entries")
    if type(entries) is not list or len(entries) > limit:
        raise TimingSummaryError("Invalid timing entries.")
    counts = {
        name: _integer(trace.get(name), name)
        for name in (
            "retained_entries",
            "started_spans",
            "finished_spans",
            "unfinished_spans",
            "dropped_entries",
            "observer_errors",
        )
    }
    _need(
        counts["retained_entries"] == len(entries)
        and counts["started_spans"] == len(entries) + counts["dropped_entries"]
        and counts["started_spans"]
        == counts["finished_spans"] + counts["unfinished_spans"],
        "Inconsistent trace counts.",
    )
    active_action = trace.get("current_action")
    if active_action is not None:
        _label(active_action, "current action", 128)
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    previous_sequence = 0
    retained_finished = 0
    for entry in entries:
        _need(type(entry) is dict, "Timing entry must be an object.")
        action = _label(entry.get("action_id"), "action", 128)
        function = _label(entry.get("function"), "function", 160)
        sequence = _integer(entry.get("sequence"), "sequence")
        _need(
            previous_sequence < sequence <= counts["started_spans"],
            "Non-increasing or out-of-range timing sequence.",
        )
        previous_sequence = sequence
        _integer(entry.get("thread_id"), "thread")
        start = _integer(entry.get("started_ns"), "start")
        outcome = entry.get("outcome")
        _need(
            outcome in ("RETURNED", "RAISED", "IN_PROGRESS"),
            "Unknown timing outcome.",
        )
        duration = entry.get("duration_ns")
        if outcome == "IN_PROGRESS":
            _need(
                entry.get("finished_ns") is None and duration is None,
                "Unfinished span must not claim an end time.",
            )
        else:
            end = _integer(entry.get("finished_ns"), "end")
            duration = _integer(duration, "duration")
            _need(end >= start and duration == end - start, "Invalid span duration.")
            retained_finished += 1
        row = groups.setdefault(
            (action, function),
            dict(
                action_id=action,
                function=function,
                retained_spans=0,
                returned=0,
                raised=0,
                in_progress=0,
                inclusive_completed_total_ns=0,
                inclusive_completed_max_ns=None,
            ),
        )
        row["retained_spans"] += 1
        row[
            {"RETURNED": "returned", "RAISED": "raised", "IN_PROGRESS": "in_progress"}[
                outcome
            ]
        ] += 1
        if duration is not None:
            row["inclusive_completed_total_ns"] += duration
            prior_max = row["inclusive_completed_max_ns"]
            row["inclusive_completed_max_ns"] = (
                duration if prior_max is None else max(prior_max, duration)
            )
    _need(
        retained_finished <= counts["finished_spans"]
        and len(entries) - retained_finished <= counts["unfinished_spans"],
        "Entry outcomes disagree with the trace counts.",
    )
    return dict(
        schema="rocell.camera_admission_timing_summary.v1",
        status="UNAUTHENTICATED_TEST_TIMING_DIAGNOSTIC",
        reported_source_sha256=source,
        timing_semantics=TIMING_SEMANTICS,
        counts=counts,
        current_action=active_action,
        observations_complete=(
            not counts["dropped_entries"]
            and not counts["unfinished_spans"]
            and not counts["observer_errors"]
            and active_action is None
        ),
        groups=[groups[key] for key in sorted(groups)],
        original_or_export_verified=False,
        admission_pass_inferred=False,
        physical_authority=False,
        hardware_qualified=False,
        meaning=(
            "Read-only aggregation of reported test timings, not authenticated "
            "original evidence. Inclusive totals overlap and must not be summed "
            "as exclusive costs. Tracing adds overhead. Failures remain failures."
        ),
    )


def read_checkpoint(path: Path) -> dict[str, Any]:
    """Bound the local diagnostic input and reject ambiguous JSON field names."""
    info = path.lstat()
    _need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        "Checkpoint must be a regular file, not a link or reparse point.",
    )
    _need(info.st_size <= MAX_CHECKPOINT_BYTES, "Checkpoint exceeds the byte limit.")
    with path.open("rb") as stream:
        payload = stream.read(MAX_CHECKPOINT_BYTES + 1)
    _need(
        len(payload) <= MAX_CHECKPOINT_BYTES, "Checkpoint grew beyond its byte limit."
    )
    try:
        data = json.loads(payload, object_pairs_hook=_unique_object)
    except TimingSummaryError:
        raise
    except (ValueError, RecursionError) as error:
        # Python also raises ValueError when an integer exceeds its conversion
        # limit. Keep that limit intact and report the same bounded input error.
        raise TimingSummaryError("Invalid checkpoint JSON.") from error
    return summarize_checkpoint(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args(argv)
    try:
        report = read_checkpoint(args.checkpoint)
    except (OSError, TimingSummaryError) as error:
        print(f"Timing summary unavailable: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
