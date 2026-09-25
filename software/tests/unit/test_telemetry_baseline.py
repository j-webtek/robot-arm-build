"""Deterministic pose-variation tests; no devices, files or process dispatch."""

import json

import pytest

from rocell.arm.telemetry_baseline import analyze_pose_variation
from test_telemetry_stream import POSE


def line(**changes):
    return json.dumps({**POSE, **changes}).encode() + b"\n"


def test_known_variation_and_missing_optional_fields():
    report = analyze_pose_variation(line(x=1) + line(x=3))
    stats = report["axes"]["x"]["statistics"]
    assert stats == {"minimum": 1, "maximum": 3, "mean": 2,
                     "peak_to_peak": 2, "population_stddev": 1, "unique_reported_values": 2}
    assert report["axes"]["x"]["units"] == "mm"
    assert report["axes"]["b"]["units"] == "rad"
    assert report["optional_field_sample_counts"]["v"] == 0
    assert report["sample_rate_hz"] is report["settling_time_s"] is None


def test_constant_values_are_not_accuracy_or_stationarity_proof():
    report = analyze_pose_variation(line() * 3)
    assert report["axes"]["x"]["statistics"]["peak_to_peak"] == 0
    assert report["stationarity_verified"] is report["measurement_accuracy_verified"] is False
    assert report["sample_freshness_verified"] is report["physical_authority"] is False


def test_rejected_partial_and_incomplete_lines_are_accounted_for():
    raw = b'prefix}\n' + b'{"T":1051}\n' + line() + b'{"T":'
    report = analyze_pose_variation(raw)
    assert report["complete_pose_samples"] == 1
    assert report["rejected_lines"] == report["incomplete_telemetry_lines"] == 1
    assert report["tail"]["end"] - report["tail"]["start"] == 5
    assert report["axes"]["x"]["statistics"]["population_stddev"] is None


def test_empty_and_capacity_limits():
    report = analyze_pose_variation(b'')
    assert report["complete_pose_samples"] == 0
    assert report["axes"]["x"]["statistics"] is None
    with pytest.raises(ValueError): analyze_pose_variation(b'x' * 65537)


def test_record_cap_does_not_claim_full_coverage():
    report = analyze_pose_variation(line() * 270)
    assert report["complete_pose_samples"] == 256
    assert report["record_limit_reached"] is True
    assert report["tail"]["kind"] == "RECORD_LIMIT_UNPARSED"


def test_extreme_numbers_do_not_emit_nonfinite_statistics():
    report = analyze_pose_variation(line(x=1e308) + line(x=-1e308))
    assert report["axes"]["x"]["statistics"] is None
    json.dumps(report, allow_nan=False)
