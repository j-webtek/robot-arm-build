"""Incremental wire tests: all fixtures synthetic, with no hardware imports."""

import base64
import hashlib
import json

import pytest

from rocell.arm.telemetry_stream import TelemetryStream

POSE = {"T": 1051, "x": 345, "y": -5, "z": 210, "tit": .03,
        "b": -.01, "s": 0, "e": 1.6, "t": -.007, "r": -.003, "g": 3.14}
LINE = json.dumps(POSE).encode() + b"\r\n"


@pytest.mark.parametrize("fragment", [1, 2, 7, 256, 4096])
def test_fragmentation_preserves_prefix_samples_and_suffix(fragment):
    raw = b'broken-prefix}\r\n' + LINE + LINE + b'{"T":1051'
    parser = TelemetryStream()
    for offset in range(0, len(raw), fragment):
        parser.feed(raw[offset:offset+fragment])
    report = parser.finish()
    assert base64.b64decode(report["raw"]["base64"]) == raw
    assert report["raw"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["pose_sample_count"] == 2
    assert report["records"][0]["kind"] == "REJECTED_LINE"
    assert report["records"][1]["fields"] == POSE
    assert "v" in report["records"][1]["missing_optional_fields"]
    assert "v" not in report["records"][1]["fields"]
    spans = [(r["start"], r["end"]) for r in report["records"]]
    spans.append((report["tail"]["start"], report["tail"]["end"]))
    assert b"".join(raw[a:b] for a,b in spans) == raw
    assert not any(report[k] for k in ("sample_freshness_verified", "query_response_verified", "motion_authorized", "physical_authority"))


@pytest.mark.parametrize("raw", [b'{"T":1051,"x":true}\n', b'{"T":1051,"x":NaN}\n',
    b'{"T":1051,"x":1,"x":2}\n', b'{"T":104}\n', b'\xff\n', b'ets boot\n'])
def test_invalid_line_does_not_contaminate_following_sample(raw):
    parser = TelemetryStream()
    parser.feed(raw + LINE)
    report = parser.finish()
    assert report["records"][0]["kind"] == "REJECTED_LINE"
    assert report["pose_sample_count"] == 1


def test_minimal_feedback_not_complete_pose():
    parser = TelemetryStream()
    parser.feed(b'{"T":1051}\n')
    report = parser.finish()
    assert report["pose_sample_count"] == 0
    assert report["records"][0]["kind"] == "INCOMPLETE_TELEMETRY"


def test_limits_and_seal_do_not_silently_discard_data():
    parser = TelemetryStream(max_bytes=64, max_line_bytes=64, max_records=1)
    parser.feed(b'\n' + b'x'*63)
    with pytest.raises(ValueError):
        parser.feed(b'overflow')
    report = parser.finish()
    assert report["raw"]["bytes"] == 64
    assert report["byte_capacity_reached"] and report["record_limit_reached"]
    assert report["tail"]["kind"] == "RECORD_LIMIT_UNPARSED"
    report["records"].clear()
    assert len(parser.finish()["records"]) == 1
    with pytest.raises(ValueError):
        parser.feed(b'')


def test_overlong_line_resynchronizes_only_at_newline():
    parser = TelemetryStream(max_line_bytes=256)
    parser.feed(b'x'*300 + LINE + LINE)
    report = parser.finish()
    assert report["records"][0]["reason"] == "OVERLONG_LINE"
    assert report["pose_sample_count"] == 1


def test_empty_capture_is_not_a_sample():
    report = TelemetryStream().finish()
    assert report["pose_sample_count"] == 0
    assert report["records"] == []


def test_full_capture_compact_format_fits_supervisor_structure_limit():
    from rocell.arm.telemetry_stream import compact_capture
    from rocell.providers.windows.owned_worker_process import decode_owned_json
    # The received-unit stream hit 256 parsed records; exercise the full byte
    # capacity as well, keeping the supervisor's global limits unchanged.
    parser = TelemetryStream()
    raw = (LINE * 600)[:65536]
    parser.feed(raw)
    report = compact_capture(parser.finish())
    encoded = json.dumps({"capture": report, "read_windows": [
        [index*128, (index+1)*128, 1000+index, 1000+index] for index in range(512)
    ]}).encode()
    assert decode_owned_json(encoded, maximum=256*1024)["capture"] == report
    assert base64.b64decode(report["raw"]["base64"]) == raw
    assert report["pose_sample_count"] == 256
    assert report["latest_pose_record"]["fields"] == POSE
