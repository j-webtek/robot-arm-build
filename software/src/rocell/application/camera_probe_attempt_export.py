"""Complete cached probe-attempt diagnostics in ordinary, bounded JSON parts.

This is a separate family from file-only preparation exports. It retains failed
admission and native readback without pretending that unknown effect counts are
zero. Only the export operation is device-inert. No device/store is read here,
and decoded reports cannot restore an owner, session, permit or retry.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from time import monotonic_ns
from typing import Any

from .physical_camera_identity_export import _copy, _redact, _flatten, _expand, _parts
from .camera_probe_wire_export import project_native_buffers, restore_native_buffers
from .wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    MAX_EXPORT_BYTES,
    MAX_MANIFEST_BYTES,
    WizardDiagnosticExporter,
    _json_bytes,
    sanitize_diagnostic_record,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest

SCHEMA = "rocell.camera_probe_attempt_export.v1"
DIAGNOSTICS_SCHEMA = "rocell.camera_probe_attempt_diagnostics.v1"
PART_SCHEMA = "rocell.camera_probe_attempt_part.v1"
MAX_INPUT_BYTES = 4 * 1024 * 1024
TIMEOUT_NS = 120_000_000_000
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
)


@dataclass(frozen=True, slots=True)
class _AttemptExportProfile:
    snapshot_schema: str
    diagnostics_schema: str
    part_schema: str
    name_prefix: str


# Closed diagnostic families share byte accounting/redaction, never authority.
# Existing probe entry points keep their exact schema and attachment names.
_PROBE = _AttemptExportProfile(
    SCHEMA, DIAGNOSTICS_SCHEMA, PART_SCHEMA, "camera-probe-attempt"
)
_CONFIGURATION = _AttemptExportProfile(
    "rocell.camera_configuration_attempt_export.v1",
    "rocell.camera_configuration_attempt_diagnostics.v1",
    "rocell.camera_configuration_attempt_part.v1",
    "camera-configuration-attempt",
)


class CameraProbeAttemptExportError(ValueError):
    pass


def _need(ok):
    if not ok:
        raise CameraProbeAttemptExportError(
            "CAMERA_PROBE_ATTEMPT_EXPORT_INVALID_OR_OVER_CAPACITY"
        )


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _input(value, profile=_PROBE):
    _need(profile is _PROBE or profile is _CONFIGURATION)
    value = _copy(value, maximum=MAX_INPUT_BYTES)
    _need(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "source_sha256",
            "launch_session_id",
            "queue",
            "admission",
            "dispatch",
            "completion",
            "physical_authority",
            "hardware_qualified",
            "meaning",
        }
    )
    _need(
        value["schema"] == profile.diagnostics_schema and _hash(value["source_sha256"])
    )
    _need(
        type(value["launch_session_id"]) is str
        and re.fullmatch(r"wizard-[0-9a-f]{32}", value["launch_session_id"]) is not None
    )
    _need(value["physical_authority"] is value["hardware_qualified"] is False)
    _need(value["queue"] is not None or value["admission"] is not None)
    for role in ("queue", "admission", "dispatch", "completion"):
        _need(value[role] is None or type(value[role]) is dict)
    # Diagnostic shape only: failures may have no permit, receipt or counters.
    # Do not semantically validate partial records as if they were successful.
    if value["queue"] is not None:
        queue = value["queue"]
        _need(
            set(queue) == {"operation_id", "context_sha256", "claimed"}
            and type(queue["operation_id"]) is str
            and re.fullmatch(r"operation-[0-9a-f]{32}", queue["operation_id"])
            is not None
            and _hash(queue["context_sha256"])
            and type(queue["claimed"]) is bool
        )
    if value["admission"] is not None:
        _need(
            value["admission"].get("physical_authority") is False
            and value["admission"].get("hardware_qualified") is False
            and value["admission"].get("automatic_retry_allowed") is False
        )
    return value


def prepare_probe_attempt_export(diagnostics):
    """Check full retention/reconstruction capacity before creating any folder."""
    return _prepare_attempt_export(diagnostics, profile=_PROBE)


def _prepare_attempt_export(diagnostics, *, profile):
    original = _input(project_native_buffers(diagnostics), profile)
    cleaned = _redact(original)
    root, nodes = _flatten(cleaned)
    attachments = _parts(
        nodes, root, part_schema=profile.part_schema, name_prefix=profile.name_prefix
    )
    reconstructed = restore_native_buffers(cleaned)
    original_hash = digest(canonical(diagnostics))
    exported_hash = digest(canonical(reconstructed))
    preserved = original_hash == exported_hash
    snapshot = dict(
        schema=profile.snapshot_schema,
        session_id=original["launch_session_id"],
        mode="PHYSICAL_DIAGNOSTIC",
        source_binding_sha256=original["source_sha256"],
        original_diagnostics_sha256=original_hash,
        exported_diagnostics_sha256=exported_hash,
        original_bytes_preserved=preserved,
        credential_redaction_applied=not preserved,
        root_sha256=root,
        node_count=len(nodes),
        parts=[
            dict(attachment="attachment-" + name, bytes=len(raw), sha256=digest(raw))
            for name, raw in attachments.items()
        ],
        meaning="Cached attempt diagnostics, not a restorable connection or retry. device_io_performed describes this export only; native effects and unknown counts remain in the attempt. Redacted data is not the original evidence named by its hashes.",
        **_FLAGS,
    )
    _need(sanitize_diagnostic_record(snapshot) == snapshot)
    _need(
        sum(map(len, attachments.values()))
        + len(_json_bytes(snapshot))
        + MAX_MANIFEST_BYTES
        + 16 * 1024
        <= MAX_EXPORT_BYTES
    )
    _need(
        _restore_attempt_export(snapshot, attachments, profile=profile) == reconstructed
    )
    return snapshot, attachments


def restore_probe_attempt_export(snapshot, attachments):
    """Decode a diagnostic copy only; no live admission class is constructed."""
    return _restore_attempt_export(snapshot, attachments, profile=_PROBE)


def _restore_attempt_export(snapshot, attachments, *, profile):
    _need(profile is _PROBE or profile is _CONFIGURATION)
    value = _copy(snapshot, maximum=256 * 1024)
    _need(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "session_id",
            "mode",
            "source_binding_sha256",
            "original_diagnostics_sha256",
            "exported_diagnostics_sha256",
            "original_bytes_preserved",
            "credential_redaction_applied",
            "root_sha256",
            "node_count",
            "parts",
            "meaning",
            *_FLAGS,
        }
    )
    _need(
        value["schema"] == profile.snapshot_schema
        and value["mode"] == "PHYSICAL_DIAGNOSTIC"
        and all(value[key] is False for key in _FLAGS)
    )
    _need(type(value["parts"]) is list and 1 <= len(value["parts"]) <= MAX_ATTACHMENTS)
    _need(type(attachments) is dict and len(attachments) == len(value["parts"]))
    nodes: dict[str, Any] = {}
    used, total = set(), 0

    def pairs(items):
        result = {}
        for key, child in items:
            _need(key not in result)
            result[key] = child
        return result

    for index, row in enumerate(value["parts"], 1):
        name = f"{profile.name_prefix}-part-{index:02d}.json"
        _need(
            type(row) is dict
            and set(row) == {"attachment", "bytes", "sha256"}
            and row["attachment"] == "attachment-" + name
            and type(row["bytes"]) is int
        )
        raw = attachments.get(name)
        _need(
            type(raw) is bytes
            and 0 < len(raw) <= MAX_ATTACHMENT_BYTES
            and len(raw) == row["bytes"]
            and digest(raw) == row["sha256"]
        )
        total += len(raw)
        _need(total <= MAX_EXPORT_BYTES)
        part = json.loads(raw.decode("ascii"), object_pairs_hook=pairs)
        _need(
            _json_bytes(part) == raw
            and type(part) is dict
            and set(part)
            == {"schema", "part_index", "part_count", "root_sha256", "nodes", *_FLAGS}
        )
        _need(
            part["schema"] == profile.part_schema
            and type(part["part_index"]) is int
            and part["part_index"] == index
            and type(part["part_count"]) is int
            and part["part_count"] == len(value["parts"])
            and part["root_sha256"] == value["root_sha256"]
            and all(part[key] is False for key in _FLAGS)
            and type(part["nodes"]) is dict
            and not set(nodes).intersection(part["nodes"])
        )
        nodes.update(part["nodes"])
        used.add(name)
    _need(
        used == set(attachments)
        and type(value["node_count"]) is int
        and len(nodes) == value["node_count"]
    )
    projected = _expand(value["root_sha256"], nodes, maximum=MAX_INPUT_BYTES)
    _need(_redact(projected) == projected)
    restored = restore_native_buffers(projected)
    _need(
        restored["launch_session_id"] == value["session_id"]
        and restored["source_sha256"] == value["source_binding_sha256"]
        and digest(canonical(restored)) == value["exported_diagnostics_sha256"]
    )
    _need(
        type(value["original_bytes_preserved"]) is bool
        and value["credential_redaction_applied"]
        is (not value["original_bytes_preserved"])
        and _hash(value["original_diagnostics_sha256"])
        and (
            value["original_diagnostics_sha256"] == value["exported_diagnostics_sha256"]
        )
        is value["original_bytes_preserved"]
    )
    if value["original_bytes_preserved"]:
        _input(project_native_buffers(restored), profile)
    return restored


def export_probe_attempt(
    diagnostics, *, export_parent: Path, cancellation: Event, deadline_ns: int
):
    return _export_attempt(
        diagnostics,
        export_parent=export_parent,
        cancellation=cancellation,
        deadline_ns=deadline_ns,
        profile=_PROBE,
    )


def _export_attempt(
    diagnostics,
    *,
    export_parent: Path,
    cancellation: Event,
    deadline_ns: int,
    profile: _AttemptExportProfile,
):
    _need(profile is _PROBE or profile is _CONFIGURATION)
    now = monotonic_ns()
    _need(
        type(cancellation) is Event
        and type(deadline_ns) is int
        and now < deadline_ns <= now + TIMEOUT_NS
    )

    def check():
        _need(not cancellation.is_set() and monotonic_ns() < deadline_ns)

    check()
    snapshot, attachments = _prepare_attempt_export(diagnostics, profile=profile)
    check()
    exporter = WizardDiagnosticExporter(export_parent)
    exporter.prepare(create=True)
    check()
    return exporter.export(snapshot, [], attachments=attachments)
