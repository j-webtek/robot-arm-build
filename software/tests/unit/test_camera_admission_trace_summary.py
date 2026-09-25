"""Read-only diagnostic aggregation; no hardware or original-store admission."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from camera_admission_timing_trace import CameraAdmissionTimingTrace


SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts/summarize_camera_admission_trace.py"
)
SPEC = importlib.util.spec_from_file_location("camera_trace_summary", SCRIPT)
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


def checkpoint():
    rows = []
    # The outer interval includes the inner one: totals are deliberately not
    # presented as additive/exclusive costs or percentages of wall time.
    for number, (label, start, end, outcome) in enumerate(
        [("outer", 100, 150, "RETURNED"), ("inner", 110, 140, "RAISED")], 1
    ):
        rows.append(
            dict(
                action_id="physical_camera_probe",
                function=label,
                sequence=number,
                thread_id=1,
                started_ns=start,
                finished_ns=end,
                duration_ns=end - start,
                outcome=outcome,
            )
        )
    return dict(
        executing_source_sha256="a" * 64,
        admission_timing_trace=dict(
            schema=summary.TRACE_SCHEMA,
            timing_semantics=summary.TIMING_SEMANTICS,
            max_entries=4096,
            retained_entries=2,
            started_spans=2,
            finished_spans=2,
            unfinished_spans=0,
            dropped_entries=0,
            observer_errors=0,
            current_action=None,
            entries=rows,
        ),
    )


def test_inclusive_groups_are_deterministic_read_only_and_never_a_pass():
    original = checkpoint()
    before = deepcopy(original)
    result = summary.summarize_checkpoint(original)
    assert original == before
    assert result["observations_complete"] is True
    assert result["original_or_export_verified"] is False
    assert result["admission_pass_inferred"] is result["physical_authority"] is False
    inner, outer = result["groups"]
    assert inner["raised"] == 1 and outer["returned"] == 1
    assert inner["inclusive_completed_total_ns"] == 30
    assert outer["inclusive_completed_total_ns"] == 50
    assert "DO_NOT_SUM_AS_EXCLUSIVE" in result["timing_semantics"]


def test_actual_observer_snapshot_uses_the_same_summary_contract():
    trace = CameraAdmissionTimingTrace()
    with trace.action("physical_camera_probe"):
        assert trace.wrap(lambda: "unchanged", "actual_observer")() == "unchanged"
    result = summary.summarize_checkpoint(
        dict(executing_source_sha256="a" * 64, admission_timing_trace=trace.snapshot())
    )
    assert result["observations_complete"] is True
    assert result["counts"]["finished_spans"] == 1
    assert result["groups"][0]["returned"] == 1
    assert result["groups"][0]["inclusive_completed_total_ns"] >= 0


def test_dropped_error_and_unfinished_observations_remain_explicit():
    data = checkpoint()
    trace = data["admission_timing_trace"]
    trace.update(
        started_spans=3, unfinished_spans=1, dropped_entries=1, observer_errors=1
    )
    trace["entries"][1].update(
        outcome="IN_PROGRESS", finished_ns=None, duration_ns=None
    )
    trace["current_action"] = "physical_camera_probe"
    result = summary.summarize_checkpoint(data)
    assert result["observations_complete"] is False
    assert result["groups"][0]["inclusive_completed_max_ns"] is None
    assert result["groups"][0]["in_progress"] == 1
    assert result["counts"]["dropped_entries"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "unsupported"),
        ("timing_semantics", "exclusive"),
        ("max_entries", 4097),
        ("max_entries", True),
        ("retained_entries", 1),
        ("finished_spans", 3),
        ("dropped_entries", -1),
        ("observer_errors", 1.5),
        ("entries", {}),
        ("current_action", "control\ncharacters"),
    ],
)
def test_invalid_trace_rejected(field, value):
    data = checkpoint()
    data["admission_timing_trace"][field] = value
    with pytest.raises(summary.TimingSummaryError):
        summary.summarize_checkpoint(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence", 1),
        ("thread_id", True),
        ("started_ns", -1),
        ("duration_ns", 29),
        ("finished_ns", None),
        ("outcome", "SUCCESS"),
        ("outcome", "IN_PROGRESS"),
        ("action_id", ""),
        ("function", "x" * 161),
    ],
)
def test_invalid_span_rejected(field, value):
    data = checkpoint()
    data["admission_timing_trace"]["entries"][1][field] = value
    with pytest.raises(summary.TimingSummaryError):
        summary.summarize_checkpoint(data)


@pytest.mark.parametrize("data", [None, [], {}, {"executing_source_sha256": "a" * 64}])
def test_missing_trace_or_source_not_interpreted_as_no_failure(data):
    with pytest.raises(summary.TimingSummaryError):
        summary.summarize_checkpoint(data)


def test_cli_reads_without_changing_input_or_creating_output(tmp_path, capsys):
    target = tmp_path / "checkpoint.json"
    payload = json.dumps(checkpoint()).encode()
    target.write_bytes(payload)
    assert summary.main([str(target)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNAUTHENTICATED_TEST_TIMING_DIAGNOSTIC"
    assert target.read_bytes() == payload
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("payload", [b'{"a":1,"a":2}', b"not-json", b"[]", b"\xff"])
def test_bad_json_is_a_diagnostic_error(tmp_path, capsys, payload):
    target = tmp_path / "invalid.json"
    target.write_bytes(payload)
    assert summary.main([str(target)]) == 2
    assert not capsys.readouterr().out
    assert target.read_bytes() == payload


def test_size_limit_and_nonfile_are_rejected(tmp_path, monkeypatch):
    target = tmp_path / "large.json"
    target.write_bytes(b"0123456789")
    monkeypatch.setattr(summary, "MAX_CHECKPOINT_BYTES", 9)
    with pytest.raises(summary.TimingSummaryError, match="byte limit"):
        summary.read_checkpoint(target)
    with pytest.raises(summary.TimingSummaryError, match="regular file"):
        summary.read_checkpoint(tmp_path)


def test_oversized_json_integer_returns_diagnostic_without_changing_python_limit(
    tmp_path, capsys
):
    limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
    if not 0 < limit < summary.MAX_CHECKPOINT_BYTES - 32:
        pytest.skip("A bounded Python integer-conversion limit is not configured.")
    target = tmp_path / "integer-limit.json"
    payload = b'{"oversized":' + b"9" * (limit + 1) + b"}"
    target.write_bytes(payload)
    assert summary.main([str(target)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Invalid checkpoint JSON" in captured.err
    assert "Traceback" not in captured.err
    assert sys.get_int_max_str_digits() == limit
    assert target.read_bytes() == payload
