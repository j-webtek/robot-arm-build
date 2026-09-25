"""Complete cached stage-4 metadata exports, never media or original-store reads.

The caller owns subject verification and current-source checks. This boundary
checks closed cache/role shapes and exact canonical payload hashes, then lifts
JSON containers into a content-addressed table. Bounded ordinary JSON parts
avoid both excessive nesting and a one-cycle/one-attachment size assumption.
Credential redaction happens with the original field names *before* lifting.
No encoded/compressed opaque payload hides content from the existing sanitizer.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from threading import Event
from time import monotonic_ns
from typing import Any, Mapping

from .wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    MAX_EXPORT_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_NODES,
    WizardDiagnosticExporter,
    _json_bytes,
    sanitize_diagnostic_record,
)

DIAGNOSTICS_SCHEMA = "rocell.wizard_camera_identity_diagnostics.v1"
EXPORT_SCHEMA = "rocell.camera_identity_metadata_export.v1"
PART_SCHEMA = "rocell.camera_identity_metadata_part.v1"
ROLE_BYTES = {
    "metadata": 896 * 1024,
    "helper": 240 * 1024,
    "receipt": 32 * 1024,
    "assessment": 16 * 1024,
    "review": 16 * 1024,
}
MAX_INPUT_BYTES = 5 * sum(ROLE_BYTES.values()) + 128 * 1024
MAX_INPUT_NODES = 200_000
MAX_INPUT_DEPTH = 32
MAX_DURATION_NS = 120_000_000_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LAUNCH = re.compile(r"wizard-[0-9a-f]{32}\Z")
_IDENTITY = re.compile(r"cameraidentity-[0-9a-f]{32}\Z")
_REF = "$camera_identity_node"
_FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "native_release_allowed": False,
    "device_io_performed": False,
}
_STATES = {
    "INCOMPLETE",
    "ASSESSMENT_RETAINED_NOT_COMMITTED",
    "REVIEW_PENDING",
    "REVIEW_RETAINED_NOT_COMMITTED",
    "REVIEWED_BLOCKED",
}
_RETENTION = {
    "COLLECTED_NOT_M1_RETAINED",
    "M1_PUBLISHED_READBACK_PENDING",
    "M1_FULL_BYTES_READ_BACK",
}
_MEANING = (
    "Complete supplied camera-identity metadata only; no original media, M1 "
    "readback, live device identity or physical qualification. Redacted subjects "
    "are not reconstructible as their original evidence bytes."
)


class CameraIdentityMetadataExportError(ValueError):
    """Closed metadata, capacity or pre-write cancellation refusal."""


def _require(ok: bool, code: str = "CAMERA_IDENTITY_EXPORT_INVALID") -> None:
    if not ok:
        raise CameraIdentityMetadataExportError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _copy(value: Any, *, maximum: int = MAX_INPUT_BYTES) -> Any:
    """Private cached-metadata limits, not widened IPC/export limits."""
    remaining = [MAX_INPUT_NODES]

    def visit(item: Any, depth: int) -> Any:
        remaining[0] -= 1
        _require(remaining[0] >= 0 and depth <= MAX_INPUT_DEPTH)
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _require(-(2**63) <= item < 2**63)
            return item
        if type(item) is float:
            _require(math.isfinite(item))
            return item
        if type(item) is str:
            _require(
                len(item) <= 65536
                and not any(ord(c) < 32 and c not in "\n\r\t" for c in item)
            )
            return item
        if type(item) is list:
            return [visit(child, depth + 1) for child in item]
        _require(type(item) is dict)
        _require(
            all(
                type(key) is str
                and 0 < len(key) <= 128
                and not any(ord(c) < 32 for c in key)
                for key in item
            )
        )
        return {key: visit(child, depth + 1) for key, child in item.items()}

    try:
        result = visit(value, 0)
        _require(len(_canonical(result)) <= maximum, "CAMERA_IDENTITY_EXPORT_CAPACITY")
        return result
    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
        UnicodeError,
    ) as error:
        if isinstance(error, CameraIdentityMetadataExportError):
            raise
        raise CameraIdentityMetadataExportError(
            "CAMERA_IDENTITY_EXPORT_INVALID"
        ) from error


def _record(
    record: Any, role: str, identity_id: str, *, attempt: bool, original_bytes: bool
) -> None:
    expected = {"document", "evidence_sha256", "retention", "reference"}
    _require(
        type(record) is dict
        and set(record) == expected | ({"label"} if attempt else set())
    )
    _require(type(record["document"]) is dict and _digest(record["evidence_sha256"]))
    payload = _canonical(record["document"])
    _require(
        0 < len(payload) <= (ROLE_BYTES[role] if original_bytes else MAX_INPUT_BYTES),
        "CAMERA_IDENTITY_EXPORT_CAPACITY",
    )
    _require(
        not original_bytes
        or hashlib.sha256(payload).hexdigest() == record["evidence_sha256"],
        "CAMERA_IDENTITY_EXPORT_SUBJECT_HASH",
    )
    _require(type(record["retention"]) is str and record["retention"] in _RETENTION)
    _require(attempt or record["retention"] == "M1_FULL_BYTES_READ_BACK")
    reference = record["reference"]
    if reference is not None:
        _require(
            type(reference) is dict
            and set(reference)
            == {
                "evidence_id",
                "stage",
                "package_sha256",
                "manifest_sha256",
                "payload_sha256",
                "payload_bytes",
            }
            and type(reference["evidence_id"]) is str
            and all(
                _digest(reference[key])
                for key in ("package_sha256", "manifest_sha256", "payload_sha256")
            )
            and reference.get("stage") == "camera_identity"
            and reference.get("payload_sha256") == record["evidence_sha256"]
            and type(reference.get("payload_bytes")) is int
            and 0 < reference["payload_bytes"] <= ROLE_BYTES[role]
            and (not original_bytes or reference["payload_bytes"] == len(payload))
        )
        _require(record["retention"] != "COLLECTED_NOT_M1_RETAINED")
    else:
        _require(record["retention"] == "COLLECTED_NOT_M1_RETAINED")
    if attempt:
        _require(record["label"] == f"camera-identity-{role}-v1:{identity_id}")


def _input(diagnostics: Any, *, original_bytes: bool = True) -> dict[str, Any]:
    value = _copy(diagnostics)
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "source_sha256",
            "launch_session_id",
            "original_context",
            "publication",
            "stage_states",
            "cycles",
            "attempt",
            "meaning",
            *_FLAGS,
        }
    )
    _require(
        value["schema"] == DIAGNOSTICS_SCHEMA
        and _digest(value["source_sha256"])
        and type(value["launch_session_id"]) is str
        and _LAUNCH.fullmatch(value["launch_session_id"]) is not None
        and all(value[key] is False for key in _FLAGS)
    )
    _require(
        all(
            type(value[key]) is dict
            for key in ("original_context", "publication", "stage_states")
        )
        and type(value["meaning"]) is str
    )
    cycles = value["cycles"]
    _require(type(cycles) is list and len(cycles) <= 4)
    identities: set[str] = set()
    for index, cycle in enumerate(cycles, 1):
        _require(
            type(cycle) is dict
            and set(cycle) == {"identity_id", "sequence", "state", *ROLE_BYTES}
        )
        identity_id = cycle["identity_id"]
        _require(
            type(identity_id) is str
            and _IDENTITY.fullmatch(identity_id) is not None
            and identity_id not in identities
            and type(cycle["sequence"]) is int
            and cycle["sequence"] == index
            and type(cycle["state"]) is str
            and cycle["state"] in _STATES
        )
        identities.add(identity_id)
        present = tuple(role for role in ROLE_BYTES if cycle[role] is not None)
        _require(present == tuple(ROLE_BYTES)[: len(present)])
        expected_counts = {
            "INCOMPLETE": {0, 1, 2, 3},
            "ASSESSMENT_RETAINED_NOT_COMMITTED": {4},
            "REVIEW_PENDING": {4},
            "REVIEW_RETAINED_NOT_COMMITTED": {5},
            "REVIEWED_BLOCKED": {5},
        }
        _require(len(present) in expected_counts[cycle["state"]])
        for role in ROLE_BYTES:
            if cycle[role] is not None:
                _record(
                    cycle[role],
                    role,
                    identity_id,
                    attempt=False,
                    original_bytes=original_bytes,
                )
    attempt = value["attempt"]
    if attempt is not None:
        _require(
            type(attempt) is dict
            and set(attempt) == {"action_id", "identity_id", "records"}
        )
        _require(
            type(attempt["identity_id"]) is str
            and _IDENTITY.fullmatch(attempt["identity_id"]) is not None
            and type(attempt["action_id"]) is str
            and 0 < len(attempt["action_id"]) <= 96
            and type(attempt["records"]) is dict
            and set(attempt["records"]) <= set(ROLE_BYTES)
        )
        for role, record in attempt["records"].items():
            _record(
                record,
                role,
                attempt["identity_id"],
                attempt=True,
                original_bytes=original_bytes,
            )
    return value


def _redact(value: Any) -> Any:
    """Use the existing sanitizer's exact key/text rules before removing depth."""
    secret_keys: dict[str, bool] = {}

    def visit(item: Any) -> Any:
        if type(item) is dict:
            result = {}
            for key, child in item.items():
                if key not in secret_keys:
                    secret_keys[key] = (
                        sanitize_diagnostic_record({key: None})[key] == "[REDACTED]"
                    )
                result[key] = "[REDACTED]" if secret_keys[key] else visit(child)
            return result
        if type(item) is list:
            return [visit(child) for child in item]
        return sanitize_diagnostic_record(item, maximum_bytes=MAX_ATTACHMENT_BYTES)

    return visit(value)


def _flatten(value: Any) -> tuple[str, dict[str, Any]]:
    nodes: dict[str, Any] = {}

    def visit(item: Any) -> Any:
        if type(item) is dict:
            node = {
                "kind": "object",
                "values": [[key, visit(child)] for key, child in sorted(item.items())],
            }
        elif type(item) is list:
            node = {"kind": "array", "values": [visit(child) for child in item]}
        else:
            return item
        digest = _sha(node)
        nodes[digest] = node
        return {_REF: digest}

    root = visit(value)
    return root[_REF], nodes


def _expand(
    root: str, nodes: dict[str, Any], *, maximum: int = MAX_INPUT_BYTES
) -> dict[str, Any]:
    _require(
        _digest(root) and type(nodes) is dict and 1 <= len(nodes) <= MAX_INPUT_NODES
    )
    for digest, node in nodes.items():
        _require(
            _digest(digest)
            and type(node) is dict
            and set(node) == {"kind", "values"}
            and type(node["kind"]) is str
            and node["kind"] in {"object", "array"}
            and type(node["values"]) is list
            and _sha(node) == digest
        )
    used: set[str] = set()
    active: set[str] = set()
    remaining = [MAX_INPUT_NODES]

    def visit(item: Any, depth: int) -> Any:
        remaining[0] -= 1
        _require(remaining[0] >= 0 and depth <= MAX_INPUT_DEPTH)
        if type(item) is dict:
            _require(set(item) == {_REF} and _digest(item[_REF]))
            digest = item[_REF]
            _require(digest in nodes and digest not in active)
            used.add(digest)
            active.add(digest)
            node = nodes[digest]
            if node["kind"] == "array":
                result: Any = [visit(child, depth + 1) for child in node["values"]]
            else:
                result = {}
                for pair in node["values"]:
                    _require(
                        type(pair) is list
                        and len(pair) == 2
                        and type(pair[0]) is str
                        and pair[0] not in result
                    )
                    result[pair[0]] = visit(pair[1], depth + 1)
                _require(list(result) == sorted(result))
            active.remove(digest)
            return result
        _require(type(item) is not list)
        return item

    result = visit({_REF: root}, 0)
    _require(used == set(nodes) and type(result) is dict)
    return _copy(result, maximum=maximum)


def _node_count(value: Any) -> int:
    children = (
        value.values() if type(value) is dict else value if type(value) is list else ()
    )
    return 1 + sum(_node_count(child) for child in children)


def _parts(
    nodes: dict[str, Any],
    root: str,
    *,
    part_schema: str = PART_SCHEMA,
    name_prefix: str = "camera-identity",
) -> dict[str, bytes]:
    # Registered diagnostic families reuse only bounded tree encoding, not the
    # identity family's role grammar or approval semantics. Limits stay exact.
    _require(
        (part_schema, name_prefix)
        in {
            (PART_SCHEMA, "camera-identity"),
            ("rocell.camera_probe_setup_part.v1", "camera-probe-setup"),
            ("rocell.camera_probe_attempt_part.v1", "camera-probe-attempt"),
            (
                "rocell.camera_configuration_attempt_part.v1",
                "camera-configuration-attempt",
            ),
        }
    )
    # Conservative per-entry size includes extra indentation in the part
    # wrapper. The final bytes and generic sanitizer are still checked exactly.
    groups: list[dict[str, Any]] = []
    totals: list[tuple[int, int]] = []
    entries = []
    for digest, node in nodes.items():
        raw = _json_bytes({digest: node})
        cost, items = len(raw) + 4 * raw.count(b"\n") + 128, _node_count(node)
        _require(
            cost < MAX_ATTACHMENT_BYTES - 4096 and items < MAX_NODES - 64,
            "CAMERA_IDENTITY_EXPORT_CAPACITY",
        )
        entries.append((cost, digest, items, node))
    # Largest first avoids wasting almost a whole part after a near-limit
    # metadata subject. Digest is a deterministic tie break, not caller order.
    for cost, digest, items, node in sorted(entries, key=lambda row: (-row[0], row[1])):
        slot = next(
            (
                index
                for index, (size, count) in enumerate(totals)
                if size + cost <= MAX_ATTACHMENT_BYTES - 4096
                and count + items <= MAX_NODES - 64
            ),
            None,
        )
        if slot is None:
            _require(len(groups) < MAX_ATTACHMENTS, "CAMERA_IDENTITY_EXPORT_CAPACITY")
            slot = len(groups)
            groups.append({})
            totals.append((0, 0))
        groups[slot][digest] = node
        size, count = totals[slot]
        totals[slot] = size + cost, count + items
    attachments = {}
    for index, group in enumerate(groups, 1):
        packet = {
            "schema": part_schema,
            "part_index": index,
            "part_count": len(groups),
            "root_sha256": root,
            "nodes": group,
            **_FLAGS,
        }
        _require(
            sanitize_diagnostic_record(packet, maximum_bytes=MAX_ATTACHMENT_BYTES)
            == packet,
            "CAMERA_IDENTITY_EXPORT_REDACTION_UNSTABLE",
        )
        attachments[f"{name_prefix}-part-{index:02d}.json"] = _json_bytes(packet)
    return attachments


def _coverage(
    original: dict[str, Any], cleaned: dict[str, Any]
) -> list[dict[str, Any]]:
    result = []
    pairs = [
        (f"cycle-{index:02d}", row["identity_id"], row, cleaned["cycles"][index - 1])
        for index, row in enumerate(original["cycles"], 1)
    ]
    if original["attempt"] is not None:
        pairs.append(
            (
                "attempt",
                original["attempt"]["identity_id"],
                original["attempt"]["records"],
                cleaned["attempt"]["records"],
            )
        )
    for family, identity_id, before, after in pairs:
        for role in ROLE_BYTES:
            if before.get(role) is not None:
                document = before[role]["document"]
                exported = after[role]["document"]
                result.append(
                    dict(
                        family=family,
                        identity_id=identity_id,
                        role=role,
                        evidence_sha256=before[role]["evidence_sha256"],
                        original_document_sha256=_sha(document),
                        exported_document_sha256=_sha(exported),
                        original_bytes_preserved=document == exported,
                        credential_redaction_applied=document != exported,
                    )
                )
    return result


def prepare_camera_identity_metadata_export(
    diagnostics: dict[str, Any],
    *,
    source_sha256: str,
    launch_id: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Pure full-cache preflight. Capacity failure precedes any export writes."""
    _require(
        _digest(source_sha256)
        and type(launch_id) is str
        and _LAUNCH.fullmatch(launch_id) is not None
    )
    original = _input(diagnostics)
    cleaned = _redact(original)
    root, nodes = _flatten(cleaned)
    attachments = _parts(nodes, root)
    preserved = original == cleaned
    snapshot = dict(
        schema=EXPORT_SCHEMA,
        session_id=launch_id,
        mode="PHYSICAL_DIAGNOSTIC",
        source_binding_sha256=source_sha256,
        source_identity={"source_sha256": source_sha256},
        original_diagnostics_sha256=_sha(original),
        exported_diagnostics_sha256=_sha(cleaned),
        original_bytes_preserved=preserved,
        credential_redaction_applied=not preserved,
        reconstruction_status=(
            "ORIGINAL_BYTES_RECONSTRUCTIBLE"
            if preserved
            else "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
        ),
        root_sha256=root,
        node_count=len(nodes),
        cycle_count=len(original["cycles"]),
        attempt_included=original["attempt"] is not None,
        coverage=_coverage(original, cleaned),
        parts=[
            {
                "attachment": "attachment-" + name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for name, raw in attachments.items()
        ],
        meaning=_MEANING,
        **_FLAGS,
    )
    _require(
        sanitize_diagnostic_record(snapshot) == snapshot,
        "CAMERA_IDENTITY_EXPORT_REDACTION_UNSTABLE",
    )
    _require(
        sum(len(raw) for raw in attachments.values())
        + len(_json_bytes(snapshot))
        + MAX_MANIFEST_BYTES
        + 16 * 1024
        <= MAX_EXPORT_BYTES,
        "CAMERA_IDENTITY_EXPORT_CAPACITY",
    )
    restored = restore_camera_identity_metadata(snapshot, attachments)
    _require(restored == cleaned)
    return snapshot, attachments


def restore_camera_identity_metadata(
    snapshot: dict[str, Any],
    attachments: Mapping[str, bytes],
    *,
    expected_original_diagnostics_sha256: str | None = None,
) -> dict[str, Any]:
    """Pure reconstruction; consult status/coverage before using original hashes.

    Redacted input returns the complete *redacted* cache, explicitly not original
    evidence. This verifies hashes and structure, never the original M1 subjects.
    """
    value = _copy(snapshot, maximum=256 * 1024)
    expected = {
        "schema",
        "session_id",
        "mode",
        "source_binding_sha256",
        "source_identity",
        "original_diagnostics_sha256",
        "exported_diagnostics_sha256",
        "original_bytes_preserved",
        "credential_redaction_applied",
        "reconstruction_status",
        "root_sha256",
        "node_count",
        "cycle_count",
        "attempt_included",
        "coverage",
        "parts",
        "meaning",
        *_FLAGS,
    }
    _require(
        type(value) is dict
        and set(value) == expected
        and value["schema"] == EXPORT_SCHEMA
        and value["meaning"] == _MEANING
        and all(value[key] is False for key in _FLAGS)
    )
    _require(
        value["mode"] == "PHYSICAL_DIAGNOSTIC"
        and type(value["session_id"]) is str
        and _LAUNCH.fullmatch(value["session_id"]) is not None
        and value["source_identity"]
        == {"source_sha256": value["source_binding_sha256"]}
    )
    for key in (
        "original_diagnostics_sha256",
        "exported_diagnostics_sha256",
        "root_sha256",
        "source_binding_sha256",
    ):
        _require(_digest(value[key]))
    preserved = value["original_bytes_preserved"]
    _require(
        type(preserved) is bool
        and value["credential_redaction_applied"] is not preserved
        and type(value["credential_redaction_applied"]) is bool
        and value["reconstruction_status"]
        == (
            "ORIGINAL_BYTES_RECONSTRUCTIBLE"
            if preserved
            else "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
        )
        and (
            value["original_diagnostics_sha256"] == value["exported_diagnostics_sha256"]
        )
        is preserved
        and (
            expected_original_diagnostics_sha256 is None
            or expected_original_diagnostics_sha256
            == value["original_diagnostics_sha256"]
        )
    )
    _require(
        type(value["parts"]) is list
        and 1 <= len(value["parts"]) <= MAX_ATTACHMENTS
        and isinstance(attachments, Mapping)
        and len(attachments) == len(value["parts"])
    )
    names = [
        f"camera-identity-part-{index:02d}.json"
        for index in range(1, len(value["parts"]) + 1)
    ]
    _require(set(attachments) in (set(names), {"attachment-" + name for name in names}))
    prefixed = names[0] not in attachments
    nodes: dict[str, Any] = {}
    for index, (name, row) in enumerate(zip(names, value["parts"]), 1):
        _require(
            type(row) is dict
            and set(row) == {"attachment", "bytes", "sha256"}
            and row["attachment"] == "attachment-" + name
        )
        raw = attachments[("attachment-" if prefixed else "") + name]
        _require(
            type(raw) is bytes
            and 0 < len(raw) <= MAX_ATTACHMENT_BYTES
            and type(row["bytes"]) is int
            and len(raw) == row["bytes"]
            and hashlib.sha256(raw).hexdigest() == row["sha256"]
        )
        try:
            packet = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise CameraIdentityMetadataExportError(
                "CAMERA_IDENTITY_EXPORT_INVALID"
            ) from error
        _require(_json_bytes(packet) == raw)
        _require(
            type(packet) is dict
            and set(packet)
            == {"schema", "part_index", "part_count", "root_sha256", "nodes", *_FLAGS}
            and packet["schema"] == PART_SCHEMA
            and type(packet["part_index"]) is int
            and packet["part_index"] == index
            and type(packet["part_count"]) is int
            and packet["part_count"] == len(names)
            and packet["root_sha256"] == value["root_sha256"]
            and all(packet[key] is False for key in _FLAGS)
            and type(packet["nodes"]) is dict
            and not set(nodes).intersection(packet["nodes"])
        )
        _require(
            sanitize_diagnostic_record(packet, maximum_bytes=MAX_ATTACHMENT_BYTES)
            == packet
        )
        nodes.update(packet["nodes"])
    _require(type(value["node_count"]) is int and len(nodes) == value["node_count"])
    result = _expand(value["root_sha256"], nodes)
    _require(_sha(result) == value["exported_diagnostics_sha256"])
    # Redaction cannot hide a malformed or omitted cache role. References still
    # identify original bytes; only their document byte-equality check is absent.
    _input(result, original_bytes=preserved)
    _require(
        result.get("schema") == DIAGNOSTICS_SCHEMA
        and type(result.get("cycles")) is list
        and len(result["cycles"]) <= 4
        and "attempt" in result
        and all(result.get(key) is False for key in _FLAGS)
    )
    _require(
        type(value["cycle_count"]) is int
        and len(result["cycles"]) == value["cycle_count"]
        and type(value["attempt_included"]) is bool
        and (result["attempt"] is not None) is value["attempt_included"]
    )
    # Retained original role hashes survive redaction. The reconstructed document
    # hash is separately checked and cannot be relabeled as original evidence.
    observed = _coverage(result, result)
    _require(
        type(value["coverage"]) is list and len(value["coverage"]) == len(observed)
    )
    for row, current in zip(value["coverage"], observed):
        _require(type(row) is dict and set(row) == set(current))
        for key in (
            "family",
            "identity_id",
            "role",
            "evidence_sha256",
            "exported_document_sha256",
        ):
            _require(row[key] == current[key])
        _require(
            _digest(row["original_document_sha256"])
            and row["original_document_sha256"] == row["evidence_sha256"]
            and type(row["original_bytes_preserved"]) is bool
            and type(row["credential_redaction_applied"]) is bool
            and row["credential_redaction_applied"]
            is not row["original_bytes_preserved"]
            and (row["original_document_sha256"] == row["exported_document_sha256"])
            is row["original_bytes_preserved"]
        )
    return result


def export_camera_identity_metadata(
    diagnostics: dict[str, Any],
    *,
    export_parent: Path,
    source_sha256: str,
    launch_id: str,
    cancellation: Event,
    deadline_ns: int,
) -> dict[str, Any]:
    """Explicit metadata-only export; completed receipt survives a late Stop."""
    now = monotonic_ns()
    _require(type(deadline_ns) is int and now < deadline_ns <= now + MAX_DURATION_NS)

    def check() -> None:
        _require(not cancellation.is_set(), "CAMERA_IDENTITY_EXPORT_CANCELLED")
        _require(monotonic_ns() < deadline_ns, "CAMERA_IDENTITY_EXPORT_TIMED_OUT")

    check()
    snapshot, attachments = prepare_camera_identity_metadata_export(
        diagnostics, source_sha256=source_sha256, launch_id=launch_id
    )
    check()
    exporter = WizardDiagnosticExporter(export_parent)
    exporter.prepare(create=True)
    check()
    return exporter.export(snapshot, [], attachments=attachments)
