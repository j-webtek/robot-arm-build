"""Bounded, lossless framing of unsolicited RoArm telemetry; no device I/O.

USB reads need not begin or end on a frame boundary. Never search inside a
damaged line for a convenient JSON object: resynchronize only at LF, retain
every accepted byte, and keep invalid lines and unfinished suffixes visible.
These samples cannot satisfy a later T105 request or authorize motion.
"""

from copy import deepcopy
import base64
import hashlib

from .feedback_wire import FeedbackWireError, validate_feedback_response_line

POSE_FIELDS = frozenset({"x", "y", "z", "tit", "b", "s", "e", "t", "r", "g"})
OPTIONAL_FIELDS = frozenset({"v", "tB", "tS", "tE", "tT", "tR", "tG",
    "torswitchB", "torswitchS", "torswitchE", "torswitchT", "torswitchR", "torswitchG"})


def decode_telemetry_line(raw, start, end, *, max_line_bytes=4096):
    """Decode one LF-delimited span; shared by legacy and full-window readers.

    Callers own byte/work limits and line boundaries. Offsets always refer to
    originals, including rejected lines; this function never searches for JSON.
    """
    record = {"start": start, "end": end, "kind": "REJECTED_LINE",
              "reason": None, "fields": None}
    if end - start > max_line_bytes:
        record["reason"] = "OVERLONG_LINE"
        return record
    try:
        fields = validate_feedback_response_line(bytes(raw[start:end]), max_line_bytes=max_line_bytes)
        missing = sorted(POSE_FIELDS - fields.keys())
        record.update(kind="INCOMPLETE_TELEMETRY" if missing else "POSE_TELEMETRY",
                      fields=fields, missing_pose_fields=missing,
                      missing_optional_fields=sorted(OPTIONAL_FIELDS - fields.keys()))
    except FeedbackWireError as error:
        record["reason"] = error.failure.value
    except (RecursionError, OverflowError):
        record["reason"] = "JSON_COMPLEXITY_OR_NUMERIC_RANGE"
    return record


def compact_capture(capture):
    """Bound IPC structure while preserving every byte for full reconstruction.

    Hundreds of repeated field dictionaries can exceed the supervisor's JSON
    node limit. Transfer originals and one latest parsed pose, not all records.
    Consumers independently reframe originals before trusting this summary.
    """
    records = capture["records"]
    poses = [record for record in records if record["kind"] == "POSE_TELEMETRY"]
    result = deepcopy({key: value for key, value in capture.items() if key != "records"})
    result["schema"] = "rocell.unsolicited_telemetry_capture_compact.v1"
    result["parsed_record_count"] = len(records)
    result["rejected_line_count"] = sum(r["kind"] == "REJECTED_LINE" for r in records)
    result["latest_pose_record"] = deepcopy(poses[-1]) if poses else None
    return result


class TelemetryStream:
    """One bounded capture, fed incrementally and sealed explicitly by finish().

    The collector must limit each read to remaining_bytes. Exceeding that
    capacity rejects the entire supplied chunk; it never silently truncates.
    Once the record cap is reached, bytes are still retained but not decoded.
    Original bytes plus record offsets avoid a second copy of every raw line.
    """

    def __init__(self, *, max_bytes=65536, max_line_bytes=4096, max_records=256):
        for name, value, low, high in (
            ("max_bytes", max_bytes, 64, 65536),
            ("max_line_bytes", max_line_bytes, 64, 4096),
            ("max_records", max_records, 1, 256),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"Invalid {name}")
        self._max_bytes, self._max_line, self._max_records = max_bytes, max_line_bytes, max_records
        self._raw = bytearray()
        self._start = self._scan = 0
        self._records = []
        self._finished = False

    @property
    def remaining_bytes(self):
        return self._max_bytes - len(self._raw)

    def feed(self, chunk: bytes):
        if self._finished:
            raise ValueError("Capture already finished")
        if type(chunk) is not bytes or len(chunk) > self.remaining_bytes:
            raise ValueError("Expected bytes within remaining capture capacity")
        self._raw.extend(chunk)
        while len(self._records) < self._max_records:
            newline = self._raw.find(b"\n", self._scan)
            if newline < 0:
                # Do not rescan a long fragmented suffix on each feed.
                self._scan = len(self._raw)
                break
            end = newline + 1
            self._records.append(decode_telemetry_line(
                self._raw, self._start, end, max_line_bytes=self._max_line))
            self._start = self._scan = end

    def finish(self):
        """Return a detached evidence snapshot. Repeated reads are idempotent."""
        self._finished = True
        raw = bytes(self._raw)
        capped = len(self._records) == self._max_records and self._start < len(raw)
        return {
            "schema": "rocell.unsolicited_telemetry_capture.v1",
            "interpretation": "UNSOLICITED_OR_BUFFERED_NOT_QUERY_REPLY",
            "raw": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "base64": base64.b64encode(raw).decode("ascii")},
            "records": deepcopy(self._records),
            "pose_sample_count": sum(r["kind"] == "POSE_TELEMETRY" for r in self._records),
            "tail": {"start": self._start, "end": len(raw),
                     "kind": "RECORD_LIMIT_UNPARSED" if capped else "UNTERMINATED_SUFFIX"},
            "record_limit_reached": capped,
            "byte_capacity_reached": len(raw) == self._max_bytes,
            "sample_freshness_verified": False,
            "query_response_verified": False,
            "motion_authorized": False,
            "physical_authority": False,
        }
