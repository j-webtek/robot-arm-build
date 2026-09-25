"""Readable, redacted native pipe buffers for the probe diagnostic exporter.

Native originals legitimately contain bounded base64 pipe observations. Decode
those BEFORE credential sanitization; split only after whole-text redaction so
neither encoding nor a part boundary can conceal a credential. Exact safe UTF-8
round-trips. Malformed JSON/binary/control bytes are explicitly transformed;
the enclosing exporter labels changed diagnostic hashes. Original M1 files stay
untouched. This codec never reads a path or constructs an executable object.
"""

import base64
import json
from typing import Any

from .physical_camera_identity_export import _copy, _redact
from .wizard_diagnostic_export import _redact_text
from rocell.providers.windows.native_camera_activation_observations import read_buffer
from rocell.providers.windows.native_camera_protocol import digest

MARKER = "$rocell_probe_wire_text_v1"
BUFFER_KEYS = {
    "base64",
    "retained_bytes",
    "retained_sha256",
    "omitted_from_observed_buffer",
}
MAX_WIRE_BYTES = 256 * 1024
CHUNK_CHARS = 16 * 1024


def _need(ok):
    if not ok:
        raise ValueError("CAMERA_PROBE_WIRE_EXPORT_INVALID")


def _clean_wire(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="backslashreplace")
    text = "".join(
        c if ord(c) >= 32 or c in "\r\n\t" else f"\\u{ord(c):04x}" for c in text
    )
    lines = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(line)
                # The private copy imposes depth/node/type limits before walking.
                parsed = _copy(parsed, maximum=MAX_WIRE_BYTES)
                clean = _redact(parsed)
                if clean != parsed:
                    line = json.dumps(clean, sort_keys=True, ensure_ascii=True) + "\n"
            except (ValueError, TypeError, RecursionError):
                line = "[UNPARSEABLE_JSON_WITHHELD; original pipe bytes remain in M1]\n"
        lines.append(line)
    return _redact_text("".join(lines))


def project_native_buffers(document: Any) -> Any:
    """Prepare ordinary readable JSON; no opaque pipe bytes are exported."""
    budget = [100_000]

    def visit(value, depth):
        budget[0] -= 1
        _need(budget[0] >= 0 and depth <= 32)
        if type(value) is dict:
            _need(MARKER not in value)
            if set(value) == BUFFER_KEYS:
                raw = read_buffer(value, MAX_WIRE_BYTES)
                text = _clean_wire(raw)
                payload = text.encode("utf-8")
                _need(len(payload) <= 6 * MAX_WIRE_BYTES)
                return {
                    MARKER: dict(
                        text_parts=[
                            text[i : i + CHUNK_CHARS]
                            for i in range(0, len(text), CHUNK_CHARS)
                        ],
                        retained_bytes=len(payload),
                        retained_sha256=digest(payload),
                        omitted_from_observed_buffer=value[
                            "omitted_from_observed_buffer"
                        ],
                    )
                }
            return {key: visit(child, depth + 1) for key, child in value.items()}
        if type(value) is list:
            return [visit(child, depth + 1) for child in value]
        return value

    return visit(document, 0)


def restore_native_buffers(document: Any) -> Any:
    """Reconstruct diagnostic buffers only, possibly redacted/transformed."""

    def visit(value):
        if type(value) is dict:
            if MARKER in value:
                _need(set(value) == {MARKER})
                row = value[MARKER]
                _need(
                    type(row) is dict
                    and set(row)
                    == {
                        "text_parts",
                        "retained_bytes",
                        "retained_sha256",
                        "omitted_from_observed_buffer",
                    }
                )
                parts = row["text_parts"]
                _need(
                    type(parts) is list
                    and len(parts) <= 6 * MAX_WIRE_BYTES // CHUNK_CHARS + 1
                    and all(
                        type(part) is str and len(part) <= CHUNK_CHARS for part in parts
                    )
                )
                text = "".join(parts)
                payload = text.encode("utf-8")
                _need(
                    type(row["retained_bytes"]) is int
                    and len(payload) == row["retained_bytes"]
                    and len(payload) <= 6 * MAX_WIRE_BYTES
                    and digest(payload) == row["retained_sha256"]
                    and type(row["omitted_from_observed_buffer"]) is int
                    and 0 <= row["omitted_from_observed_buffer"] < 2**63
                    and _redact_text(text) == text
                )
                return {
                    "base64": base64.b64encode(payload).decode("ascii"),
                    **{key: row[key] for key in BUFFER_KEYS - {"base64"}},
                }
            return {key: visit(child) for key, child in value.items()}
        if type(value) is list:
            return [visit(child) for child in value]
        return value

    # Enforce document bounds before recursive reconstruction.
    return visit(_copy(document, maximum=4 * 1024 * 1024))
