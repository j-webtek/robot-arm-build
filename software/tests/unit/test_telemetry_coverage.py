"""Offline coverage fixtures; no serial devices or physical authority."""

import json
import pytest

from rocell.arm.telemetry_coverage import analyze_window_coverage, iter_window_records
from rocell.arm.telemetry_stream import TelemetryStream

POSE = {"T":1051, "x":1, "y":2, "z":3, "tit":0,
        "b":0, "s":0, "e":0, "t":0, "r":0, "g":0}
LINE = json.dumps(POSE).encode() + b"\r\n"


def test_display_cap_does_not_limit_full_window_analysis():
    raw = LINE * 300
    result = analyze_window_coverage(raw)
    assert result["counts"]["POSE_TELEMETRY"] == 300
    assert result["processed_complete_line_bytes"] == len(raw)
    assert len(result["display_records"]) == 8
    assert result["latest_pose_record"]["end"] == len(raw)
    assert result["status"] == "COMPLETE_LINES_ACCOUNTED"
    legacy = TelemetryStream(); legacy.feed(raw)
    assert legacy.finish()["pose_sample_count"] == 256
    assert not result["physical_authority"]


def test_prefix_suffix_and_invalid_data_are_accounted_once():
    raw = b'broken}\n' + LINE + b'{"T":1051}\n' + b'\xff\n' + b'{"T"'
    result = analyze_window_coverage(raw)
    assert result["counts"] == {"POSE_TELEMETRY":1,"INCOMPLETE_TELEMETRY":1,"REJECTED_LINE":2}
    assert result["possible_partial_prefix_range"] == [0, 8]
    assert result["unprocessed_range"] == [len(raw)-4, len(raw)]
    rows = list(iter_window_records(raw))
    assert b''.join(raw[r['start']:r['end']] for r in rows) + raw[-4:] == raw


def test_split_and_shared_reads_do_not_invent_sample_times():
    raw = LINE * 2
    split = len(LINE) - 2
    rows = list(iter_window_records(raw, [[0,split,10,20], [split,len(raw),30,40]]))
    assert rows[0]["host_acquisition_bounds_ns"] == [10,40]
    assert rows[1]["host_acquisition_bounds_ns"] == [30,40]
    shared = list(iter_window_records(raw, [[0,len(raw),10,20]]))
    assert shared[0]["host_acquisition_bounds_ns"] == shared[1]["host_acquisition_bounds_ns"]


def test_tiny_lines_are_bounded_and_do_not_expand_output():
    from rocell.providers.windows.owned_worker_process import decode_owned_json
    report = analyze_window_coverage(b'\n' * 65536)
    assert report["counts"]["REJECTED_LINE"] == 65536
    assert report["unprocessed_range"] is None
    assert decode_owned_json(json.dumps(report).encode(), maximum=256*1024) == report


@pytest.mark.parametrize('raw', [b'x'*65537, bytearray(b'\n'), None], ids=['oversize','mutable','none'])
def test_rejects_invalid_originals(raw):
    with pytest.raises(ValueError): analyze_window_coverage(raw)


@pytest.mark.parametrize('windows', [[], [[1,2,10,20]], [[0,2,True,20]],
    [[0,1,20,10]], [[0,1,10,20]], [[0,1,10,20],[1,2,19,30]]])
def test_rejects_missing_or_invalid_timing(windows):
    with pytest.raises(ValueError): analyze_window_coverage(b'\n\n', windows)


def test_empty_and_overlong_inputs():
    assert analyze_window_coverage(b'', [])['counts']['POSE_TELEMETRY'] == 0
    assert analyze_window_coverage(b'x'*65536)['processed_complete_line_bytes'] == 0
    report = analyze_window_coverage(b'x'*5000+b'\n'+LINE, display_limit=0)
    assert report['counts']['REJECTED_LINE'] == 1
    assert report['counts']['POSE_TELEMETRY'] == 1
    assert report['display_records'] == []
