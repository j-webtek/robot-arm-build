"""Bounded, reconstructible probe-setup diagnostics; no live-store/device reads.

Uses the established diagnostic tree encoding and ordinary sanitized JSON parts.
The probe family has its own schema/role checks. Restoring these diagnostics
cannot create a current enrollment, original-store authentication or permission.
"""

from pathlib import Path
import json
import re
from threading import Event
from time import monotonic_ns
from typing import Any

from .camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
)
from .camera_probe_setup_service import ACTIONS
from .physical_camera_identity_export import _copy, _redact, _flatten, _expand, _parts
from .wizard_diagnostic_export import (
    MAX_EXPORT_BYTES,
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    MAX_MANIFEST_BYTES,
    WizardDiagnosticExporter,
    _json_bytes,
    sanitize_diagnostic_record,
)
from .physical_onboarding import _parse_evidence_reference, STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest

DIAGNOSTICS_SCHEMA = "rocell.camera_probe_setup_diagnostics.v1"
SCHEMA = "rocell.camera_probe_setup_export.v1"
PART_SCHEMA = "rocell.camera_probe_setup_part.v1"
MAX_INPUT_BYTES = 7 * 1024 * 1024
TIMEOUT_NS = 120_000_000_000
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
)


class CameraProbeExportError(ValueError):
    pass


def _need(ok):
    if not ok:
        raise CameraProbeExportError("CAMERA_PROBE_EXPORT_INVALID_OR_OVER_CAPACITY")


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _record(record, kind):
    _need(
        type(record) is dict
        and set(record) == {"document", "reference", "evidence_sha256", "retention"}
    )
    raw = canonical(record["document"])
    subject = (
        CameraProbePreparation(raw)
        if kind == "preparation"
        else CameraProbePreparationReview(raw)
    )
    _need(subject.sha256 == record["evidence_sha256"])
    _need(
        record["retention"]
        in {
            "COLLECTED_NOT_M1_RETAINED",
            "M1_PUBLICATION_UNCONFIRMED",
            "M1_PUBLISHED_READBACK_PENDING",
            "M1_FULL_BYTES_READ_BACK",
        }
    )
    if record["reference"] is not None:
        ref = _parse_evidence_reference(record["reference"])
        _need(
            ref.stage is STAGE_ORDER[4]
            and ref.payload_sha256 == subject.sha256
            and ref.payload_bytes == len(raw)
        )
    else:
        _need(
            record["retention"]
            in {"COLLECTED_NOT_M1_RETAINED", "M1_PUBLICATION_UNCONFIRMED"}
        )


def _input(value):
    value = _copy(value, maximum=MAX_INPUT_BYTES)
    _need(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "source_sha256",
            "launch_session_id",
            "publication",
            "original",
            "attempts",
            "queues",
            "physical_authority",
            "hardware_qualified",
            "connected",
            "meaning",
        }
    )
    _need(value["schema"] == DIAGNOSTICS_SCHEMA and _hash(value["source_sha256"]))
    _need(
        type(value["launch_session_id"]) is str
        and re.fullmatch(r"wizard-[0-9a-f]{32}", value["launch_session_id"]) is not None
    )
    _need(
        all(
            value[key] is False
            for key in ("physical_authority", "hardware_qualified", "connected")
        )
    )
    _need(
        type(value["publication"]) is dict
        and set(value["publication"]) == {"status", "operation_id"}
        and value["publication"]["status"]
        in {"NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"}
    )
    original = value["original"]
    if original is not None:
        _need(
            type(original) is dict
            and set(original) == {"state", "preparation", "review", "events", "meaning"}
        )
        _need(
            original["state"]
            in {"INCOMPLETE", "PREPARED_REVIEW_REQUIRED", "REVIEWED_FOR_ADMISSION"}
        )
        _need(type(original["events"]) is list and len(original["events"]) <= 2)
        _record(original["preparation"], "preparation")
        if original["review"] is not None:
            _record(original["review"], "review")
    for name in ("attempts", "queues"):
        _need(type(value[name]) is dict and set(value[name]) <= ACTIONS)
    for action, attempt in value["attempts"].items():
        _need(
            type(attempt) is dict
            and set(attempt) == {"action_id", "record", "events", "software", "status"}
            and attempt["action_id"] == action
        )
        _need(
            type(attempt["events"]) is list
            and len(attempt["events"]) <= 1
            and type(attempt["software"]) is dict
            and set(attempt["software"]) <= {"probe", "capture"}
        )
        _need(
            attempt["status"]
            in {
                "ORIGINAL_READ_PENDING",
                "RECORD_COLLECTED",
                "COMMIT_UNCONFIRMED",
                "COMMITTED_READBACK_PENDING",
                "ORIGINAL_READ_BACK",
            }
        )
        if attempt["record"] is not None:
            _record(
                attempt["record"],
                "preparation" if action.endswith("_prepare") else "review",
            )
    for queue in value["queues"].values():
        _need(
            type(queue) is dict
            and set(queue) == {"context_sha256", "operation_id", "claimed"}
            and _hash(queue["context_sha256"])
            and type(queue["claimed"]) is bool
            and type(queue["operation_id"]) is str
        )
    return value


def prepare_probe_setup_export(diagnostics):
    """Capacity and reconstruction checks happen before any export writes."""
    original = _input(diagnostics)
    cleaned = _redact(original)
    root, nodes = _flatten(cleaned)
    attachments = _parts(
        nodes, root, part_schema=PART_SCHEMA, name_prefix="camera-probe-setup"
    )
    preserved = original == cleaned
    snapshot = dict(
        schema=SCHEMA,
        session_id=original["launch_session_id"],
        mode="PHYSICAL_DIAGNOSTIC",
        source_binding_sha256=original["source_sha256"],
        source_identity=dict(source_sha256=original["source_sha256"]),
        original_diagnostics_sha256=digest(canonical(original)),
        exported_diagnostics_sha256=digest(canonical(cleaned)),
        original_bytes_preserved=preserved,
        credential_redaction_applied=not preserved,
        root_sha256=root,
        node_count=len(nodes),
        parts=[
            dict(attachment="attachment-" + name, bytes=len(raw), sha256=digest(raw))
            for name, raw in attachments.items()
        ],
        meaning="Diagnostic reconstruction only. Redacted data is not the original evidence named by its hashes. No current enrollment, admission or replay can be restored.",
        **_FLAGS,
    )
    _need(sanitize_diagnostic_record(snapshot) == snapshot)
    _need(
        sum(len(raw) for raw in attachments.values())
        + len(_json_bytes(snapshot))
        + MAX_MANIFEST_BYTES
        + 16 * 1024
        <= MAX_EXPORT_BYTES
    )
    _need(restore_probe_setup_export(snapshot, attachments) == cleaned)
    return snapshot, attachments


def restore_probe_setup_export(snapshot, attachments):
    """Verify complete diagnostic bytes, never authenticate a hardware session."""
    value = _copy(snapshot, maximum=256 * 1024)
    _need(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "session_id",
            "mode",
            "source_binding_sha256",
            "source_identity",
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
    _need(value["schema"] == SCHEMA and all(value[key] is False for key in _FLAGS))
    _need(type(value["parts"]) is list and 1 <= len(value["parts"]) <= MAX_ATTACHMENTS)
    _need(type(attachments) is dict and len(attachments) == len(value["parts"]))
    nodes: dict[str, Any] = {}
    used: set[str] = set()
    total = 0

    def pairs(items):
        result = {}
        for key, child in items:
            _need(key not in result)
            result[key] = child
        return result

    for index, row in enumerate(value["parts"], 1):
        name = f"camera-probe-setup-part-{index:02d}.json"
        _need(
            type(row) is dict
            and set(row) == {"attachment", "bytes", "sha256"}
            and row["attachment"] == "attachment-" + name
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
            part["schema"] == PART_SCHEMA
            and type(part["part_index"]) is int
            and part["part_index"] == index
            and type(part["part_count"]) is int
            and part["part_count"] == len(value["parts"])
            and part["root_sha256"] == value["root_sha256"]
        )
        _need(
            all(part[key] is False for key in _FLAGS)
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
    restored = _expand(value["root_sha256"], nodes, maximum=MAX_INPUT_BYTES)
    _need(
        value["mode"] == "PHYSICAL_DIAGNOSTIC"
        and value["session_id"] == restored["launch_session_id"]
        and value["source_binding_sha256"] == restored["source_sha256"]
        and value["source_identity"] == {"source_sha256": restored["source_sha256"]}
        and _redact(restored) == restored
    )
    _need(digest(canonical(restored)) == value["exported_diagnostics_sha256"])
    _need(
        type(value["original_bytes_preserved"]) is bool
        and value["credential_redaction_applied"]
        is (not value["original_bytes_preserved"])
    )
    _need(
        _hash(value["original_diagnostics_sha256"])
        and (
            value["original_diagnostics_sha256"] == value["exported_diagnostics_sha256"]
        )
        is value["original_bytes_preserved"]
    )
    if value["original_bytes_preserved"]:
        _input(restored)
    return restored


def export_probe_setup(
    diagnostics, *, export_parent: Path, cancellation: Event, deadline_ns: int
):
    """Explicit export to the existing assigned folder; never read live devices."""
    now = monotonic_ns()
    _need(
        type(cancellation) is Event
        and type(deadline_ns) is int
        and now < deadline_ns <= now + TIMEOUT_NS
    )

    def check():
        _need(not cancellation.is_set() and monotonic_ns() < deadline_ns)

    check()
    snapshot, attachments = prepare_probe_setup_export(diagnostics)
    check()
    exporter = WizardDiagnosticExporter(export_parent)
    exporter.prepare(create=True)
    check()
    return exporter.export(snapshot, [], attachments=attachments)
