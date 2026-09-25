"""Full-window, bounded offline decoding; no device access or motion authority.

The legacy capture summary intentionally stops at 256 records. This separate
derived schema processes all retained complete lines without altering that wire
contract. Memory stays bounded by originals, 512 read windows and one decoded
record; display samples are independently limited. The default is 65,536 bytes;
versioned campaign callers explicitly opt into at most 98,304 bytes. Malformed
tiny lines therefore cannot create unbounded work.
"""

from bisect import bisect_right
from hashlib import sha256
import json
import math

from .telemetry_stream import decode_telemetry_line


def complete_frame_interval(raw, read_windows, *, maximum_bytes=65536):
    """Identify a bounded complete-line interval without deleting original bytes.

    Only a leading JSON-looking fragment or lone frame delimiter, and a trailing
    object prefix without LF can be outside the analysis interval. An object
    that starts at byte zero is never skipped, even if malformed. Interior
    lines are never filtered. Host acquisition bounds are retained unchanged.
    This accounts for stream attachment boundaries, not device freshness.
    """
    _validate(raw, read_windows, maximum_bytes=maximum_bytes)
    if read_windows is None:
        raise ValueError('Explicit host read windows required')
    start, end = 0, len(raw)
    first = raw.find(b'\n')
    last = raw.rfind(b'\n')
    if first>=0:
        prefix = raw[:first+1].strip()
        numeric_tail = False
        key_tail = False
        comma_tail = False
        colon_tail = False
        if first+1 <= 2048 and prefix.startswith(b':'):
            # Attachment exactly after a field's closing quote loses its key.
            # Validate a numeric value and known numeric remainder solely to
            # identify an unobserved boundary, never to reconstruct a sample.
            try:
                pairs = json.loads(b'{"_lost_key"'+prefix,
                                   object_pairs_hook=lambda pairs: pairs)
                known = {'_lost_key','x','y','z','tit','b','s','e','t','r','g',
                         'tB','tS','tE','tT','tR','tG'}
                colon_tail = (type(pairs) is list and bool(pairs)
                    and all(type(p) is tuple and len(p) == 2 for p in pairs)
                    and len({p[0] for p in pairs}) == len(pairs)
                    and all(k in known and type(v) in (int,float) and math.isfinite(v)
                            for k,v in pairs))
            except (ValueError, UnicodeError, TypeError, OverflowError):
                pass
        if first+1 <= 2048 and prefix.startswith(b','):
            # A connection may attach exactly between numeric fields. Validate
            # only this first-line remainder; never discard interior damage or
            # synthesize a pose from an incomplete report. Keep original bytes.
            try:
                pairs = json.loads(b'{'+prefix[1:], object_pairs_hook=lambda pairs: pairs)
                known = {'x','y','z','tit','b','s','e','t','r','g',
                         'tB','tS','tE','tT','tR','tG'}
                comma_tail = (type(pairs) is list and bool(pairs)
                    and all(type(p) is tuple and len(p) == 2 for p in pairs)
                    and len({p[0] for p in pairs}) == len(pairs)
                    and all(k in known and type(v) in (int,float) and math.isfinite(v)
                            for k,v in pairs))
            except (ValueError, UnicodeError, TypeError, OverflowError):
                pass
        if first+1 <= 2048 and b'":' in prefix and not prefix.startswith((b'{', b'"')):
            # Stream attachment can split a field name, e.g. R":20} is the
            # tail of "tR":20}. Accept only a suffix of a known numeric field
            # and a parseable remaining object. This first fragment remains
            # explicitly unobserved; no interior line is removed or repaired.
            head, tail = prefix.split(b'":', 1)
            keys = ('x','y','z','tit','b','s','e','t','r','g','tB','tS','tE','tT','tR','tG')
            for key in keys:
                if head and key.encode().endswith(head):
                    try:
                        fields = json.loads(b'{"'+key.encode()+b'":'+tail)
                        key_tail = (type(fields) is dict and bool(fields)
                            and set(fields) <= set(keys)
                            and all(type(v) in (int,float) for v in fields.values()))
                    except (ValueError, UnicodeError):
                        pass
                    if key_tail:
                        break
        if first+1<=2048 and prefix and prefix[0] in b'0123456789-+.' and b',' in prefix:
            # A read can begin in a numeric token (including a truncated leading
            # zero). Recognize only a remaining object tail of known numeric
            # telemetry fields; never scan ahead past another newline.
            head,tail = prefix.split(b',',1)
            try:
                fields = json.loads(b'{'+tail)
                numeric_tail = (all(c in b'0123456789eE+-.' for c in head)
                    and type(fields) is dict and bool(fields)
                    and set(fields)<=set(('x','y','z','tit','b','s','e','t','r','g',
                                         'tB','tS','tE','tT','tR','tG'))
                    and all(type(v) in (int,float) for v in fields.values()))
            except (ValueError,UnicodeError):
                pass
        # A capture can start exactly at the prior packet's LF (or CRLF).
        # Account for only this delimiter as a boundary: never skip whitespace,
        # multiple empty records, or an empty record inside the captured stream.
        if raw[:first+1] in (b'\n', b'\r\n'):
            start = first+1
        elif (not prefix.startswith(b'{') and (prefix.startswith(b'"') or numeric_tail or key_tail or comma_tail or colon_tail)
                and prefix.endswith(b'}') and first+1<=2048):
            start = first+1
        suffix = raw[last+1:]
        if suffix and len(suffix)<=2048 and suffix.lstrip().startswith(b'{'):
            end = last+1
    selected = raw[start:end]
    windows = []
    for left,right,begin,finish in read_windows:
        a,b = max(left,start), min(right,end)
        if a<b:
            windows.append([a-start,b-start,begin,finish])
    # Original offsets plus hashes make the excluded fragments independently
    # inspectable in the raw retained capture. Their content is not called valid.
    framing = {'schema':'rocell.complete_frame_interval.v1',
        'original_sha256':sha256(raw).hexdigest(),'original_bytes':len(raw),
        'analysis_range':[start,end],'analysis_sha256':sha256(selected).hexdigest(),
        'unobserved_prefix_range':[0,start] if start else None,
        'unobserved_suffix_range':[end,len(raw)] if end<len(raw) else None,
        'sample_freshness_verified':False,'physical_authority':False}
    _validate(selected, windows, maximum_bytes=maximum_bytes)
    return selected, windows, framing


def _validate(raw, read_windows, *, maximum_bytes=65536):
    # Historical callers retain the 64 KiB contract; versioned campaigns opt in.
    if type(maximum_bytes) is not int or maximum_bytes not in (65536,81920,98304,524288,540672):
        raise ValueError("Unsupported bounded decoder capacity")
    if type(raw) is not bytes or len(raw) > maximum_bytes:
        raise ValueError("Expected original bytes within decoder capacity")
    if read_windows is None:
        return None
    if type(read_windows) is not list or len(read_windows) > (4096 if maximum_bytes in (524288,540672) else 512):
        raise ValueError("Expected at most 512 read windows")
    offset = last_time = 0
    windows = []
    for row in read_windows:
        if type(row) is not list or len(row) != 4 or any(type(v) is not int for v in row):
            raise ValueError("Read windows must contain four integers")
        start, end, begin, finish = row
        if not (start == offset <= end <= len(raw) and end-start <= 256
                and 0 < begin <= finish and last_time <= begin):
            raise ValueError("Read window coverage or ordering invalid")
        offset, last_time = end, finish
        if end > start:
            windows.append(tuple(row))
    if offset != len(raw):
        raise ValueError("Read windows must cover every retained byte")
    return windows


def iter_window_records(raw: bytes, read_windows=None, *, maximum_bytes=65536):
    """Yield complete-line records with host acquisition bounds, never device time.

    Validation precedes the first record. Empty reads contribute no frame bytes.
    A split frame spans its first contributing read start through its last read
    finish. Shared reads deliberately produce shared (not interpolated) bounds.
    """
    windows = _validate(raw, read_windows, maximum_bytes=maximum_bytes)
    ends = [row[1] for row in windows] if windows is not None else None
    start = 0
    while True:
        newline = raw.find(b"\n", start)
        if newline < 0:
            return
        end = newline + 1
        record = decode_telemetry_line(raw, start, end)
        if windows is not None:
            first = bisect_right(ends, start)
            last = bisect_right(ends, end - 1)
            record["host_acquisition_bounds_ns"] = [windows[first][2], windows[last][3]]
        else:
            record["host_acquisition_bounds_ns"] = None
        yield record
        start = end


def analyze_window_coverage(raw: bytes, read_windows=None, *, display_limit=8, maximum_bytes=65536):
    """Summarize all lines while retaining only a small display preview.

    COMPLETE_LINES_ACCOUNTED means parsing coverage, not valid telemetry or a
    complete physical observation. Any final unterminated bytes remain explicit.
    The first rejected line is only a possible partial prefix, not proven one.
    """
    if type(display_limit) is not int or not 0 <= display_limit <= 8:
        raise ValueError("Display limit must be an integer from zero through eight")
    counts = {"POSE_TELEMETRY": 0, "INCOMPLETE_TELEMETRY": 0, "REJECTED_LINE": 0}
    display, latest, first_rejected, processed = [], None, None, 0
    for index, record in enumerate(iter_window_records(raw, read_windows, maximum_bytes=maximum_bytes)):
        counts[record["kind"]] += 1
        processed = record["end"]
        if index == 0 and record["kind"] == "REJECTED_LINE":
            first_rejected = [record["start"], record["end"]]
        if record["kind"] == "POSE_TELEMETRY":
            latest = record
        if len(display) < display_limit:
            display.append(record)
    return {
        "schema": "rocell.telemetry_window_coverage.v1",
        "basis": "OFFLINE_REANALYSIS_OF_RETAINED_BYTES",
        "raw_sha256": sha256(raw).hexdigest(), "retained_bytes": len(raw),
        "processed_complete_line_bytes": processed, "counts": counts,
        "status": "UNTERMINATED_SUFFIX" if processed < len(raw) else "COMPLETE_LINES_ACCOUNTED",
        "unprocessed_range": [processed, len(raw)] if processed < len(raw) else None,
        "possible_partial_prefix_range": first_rejected,
        "display_records": display, "display_truncated": sum(counts.values()) > len(display),
        "latest_pose_record": latest,
        "timing_basis": "HOST_READ_ACQUISITION_BOUNDS" if read_windows is not None else "UNTIMED",
        "sample_freshness_verified": False, "physical_authority": False,
        "motion_authorized": False,
    }
