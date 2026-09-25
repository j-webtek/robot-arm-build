"""Offline pose-variation statistics, never physical calibration or approval.

Analyze original bytes rather than accepting caller-provided sample counts.
Telemetry alone cannot establish that an arm was stationary: that is separate
operator evidence. Identical readings may reflect quantization or stale data.
"""

import math
import statistics

from .telemetry_stream import TelemetryStream, POSE_FIELDS, OPTIONAL_FIELDS


def analyze_pose_variation(raw: bytes) -> dict:
    parser = TelemetryStream()
    parser.feed(raw)
    capture = parser.finish()
    rows = [r["fields"] for r in capture["records"] if r["kind"] == "POSE_TELEMETRY"]
    axes = {}
    for field in sorted(POSE_FIELDS):
        values = [float(row[field]) for row in rows]
        units = "mm" if field in {"x", "y", "z"} else "rad"
        if not values:
            axes[field] = {"units": units, "count": 0, "statistics": None}
            continue
        try:
            # Center before averaging avoids overflow from summing large
            # absolute coordinates; reject unrepresentable derived quantities.
            first = values[0]
            offsets = [value - first for value in values]
            mean = first + statistics.fmean(offsets)
            spread = max(values) - min(values)
            deviation = statistics.pstdev(values) if len(values) > 1 else None
            derived = [mean, spread] + ([] if deviation is None else [deviation])
            if not all(math.isfinite(v) for v in derived):
                raise ValueError("Derived numeric range exceeded")
            stats = {"minimum": min(values), "maximum": max(values), "mean": mean,
                     "peak_to_peak": spread, "population_stddev": deviation,
                     "unique_reported_values": len(set(values))}
        except (OverflowError, ValueError):
            stats = None
        axes[field] = {"units": units, "count": len(values), "statistics": stats}
    return {
        "schema": "rocell.pose_variation_analysis.v1",
        "basis": "RETAINED_UNSOLICITED_TELEMETRY_VALUES",
        "raw_sha256": capture["raw"]["sha256"], "raw_bytes": len(raw),
        "complete_pose_samples": len(rows),
        "parsed_records": len(capture["records"]),
        "rejected_lines": sum(r["kind"] == "REJECTED_LINE" for r in capture["records"]),
        "incomplete_telemetry_lines": sum(r["kind"] == "INCOMPLETE_TELEMETRY" for r in capture["records"]),
        "tail": capture["tail"], "record_limit_reached": capture["record_limit_reached"],
        "axes": axes,
        "optional_field_sample_counts": {key: sum(key in row for row in rows) for key in sorted(OPTIONAL_FIELDS)},
        "stationarity_verified": False, "measurement_accuracy_verified": False,
        "sample_freshness_verified": False, "physical_authority": False,
        "sample_rate_hz": None, "settling_time_s": None,
        "limitations": [
            "No per-read or device timestamps: cadence, latency and settling cannot be measured.",
            "No target command: tracking error and overshoot are not defined.",
            "Reported spread is not physical accuracy, sensor resolution or a safe tolerance.",
            "Identical frames may reflect quantization, buffering or genuinely steady pose.",
            "Statistics cover parsed complete poses only; retained tail and rejected lines are excluded.",
        ],
    }
