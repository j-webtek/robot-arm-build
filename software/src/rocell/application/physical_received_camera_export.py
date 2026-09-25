"""Complete, bounded received-camera metadata copies, without original media.

The caller supplies an already verified service cache. This module neither reads
M1 nor requalifies that cache. Each complete cycle (and optional draft/attempt)
has its own ordinary diagnostic attachment. Closed nested documents are lifted
and deduplicated so the existing exporter limits need not be widened. Exact
canonical JSON originals can be reconstructed unless credential redaction is
explicitly recorded. Hashes are integrity observations, not authentication.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from threading import Event
from time import monotonic_ns
from typing import Any

from .wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    WizardDiagnosticExporter,
    _json_bytes,
    sanitize_diagnostic_record,
)

DIAGNOSTICS_SCHEMA = "rocell.wizard_received_camera_diagnostics.v1"
EXPORT_SCHEMA = "rocell.received_camera_metadata_export.v1"
FAMILY_SCHEMA = "rocell.received_camera_metadata_family.v1"
MAX_INPUT_BYTES = 3 * 1024 * 1024
MAX_FAMILY_BYTES = 512 * 1024
MAX_INPUT_NODES = 65536
MAX_DURATION_NS = 120_000_000_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LAUNCH = re.compile(r"wizard-[0-9a-f]{32}\Z")
_RECEIPT = re.compile(r"receivedcamera-[0-9a-f]{32}\Z")
_REFERENCE = "$received_camera_document"
_LIFT = frozenset(
    {"document", "notebook", "foundation", "inspection", "inspection_assessment"}
)
_ROLES = frozenset({"notebook", "submission", "assessment", "review"})
_FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "canonical_stage_pass": False,
    "device_io_performed": False,
}
_SERVICE_FLAGS = {
    "physical_authority",
    "hardware_qualified",
    "native_release_allowed",
    "device_io_performed",
}
_MEANING = (
    "Complete supplied historical metadata, not an original-media copy, M1 "
    "readback, stage acceptance or physical qualification. Canonical originals "
    "are reconstructable only where original_bytes_preserved is true."
)


class ReceivedCameraMetadataExportError(ValueError):
    """A bounded input, reconstruction or pre-write cancellation refusal."""


def _require(condition: bool, code: str = "RECEIVED_CAMERA_EXPORT_INVALID") -> None:
    if not condition:
        raise ReceivedCameraMetadataExportError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bounded_copy(value: Any, *, maximum_bytes: int = MAX_INPUT_BYTES) -> Any:
    """Private metadata bound; deliberately does not change any IPC limit."""
    budget = [MAX_INPUT_NODES]

    def visit(item: Any, depth: int) -> Any:
        budget[0] -= 1
        _require(budget[0] >= 0 and depth <= 20)
        if item is None or type(item) in {bool, int, float, str}:
            if type(item) is str:
                _require(len(item) <= 65536)
            return item
        if type(item) is list:
            return [visit(child, depth + 1) for child in item]
        _require(type(item) is dict)
        _require(
            all(type(key) is str and 0 < len(key) <= 128 for key in item)
            and _REFERENCE not in item
        )
        return {key: visit(child, depth + 1) for key, child in item.items()}

    try:
        result = visit(value, 0)
        _require(len(_canonical(result)) <= maximum_bytes)
        return result
    except (TypeError, OverflowError, RecursionError, ValueError) as error:
        if isinstance(error, ReceivedCameraMetadataExportError):
            raise
        raise ReceivedCameraMetadataExportError(
            "RECEIVED_CAMERA_EXPORT_INVALID"
        ) from error


def _flatten(value: Any) -> tuple[Any, dict[str, Any]]:
    documents: dict[str, Any] = {}

    def visit(item: Any) -> Any:
        if type(item) is list:
            return [visit(child) for child in item]
        if type(item) is not dict:
            return item
        result = {}
        for key, child in item.items():
            if key in _LIFT and type(child) is dict:
                digest = _sha(child)
                documents[digest] = visit(child)
                result[key] = {_REFERENCE: digest}
            else:
                result[key] = visit(child)
        return result

    return visit(value), documents


def _expand(root: Any, documents: dict[str, Any], *, verify_hashes: bool) -> Any:
    used: set[str] = set()
    active: set[str] = set()
    budget = [MAX_INPUT_NODES]

    def visit(item: Any, depth: int = 0) -> Any:
        budget[0] -= 1
        _require(budget[0] >= 0 and depth <= 20)
        if type(item) is list:
            return [visit(child, depth + 1) for child in item]
        if type(item) is not dict:
            return item
        if _REFERENCE in item:
            digest = item[_REFERENCE]
            _require(
                set(item) == {_REFERENCE}
                and type(digest) is str
                and _SHA.fullmatch(digest) is not None
                and digest in documents
                and digest not in active
            )
            used.add(digest)
            active.add(digest)
            expanded = visit(documents[digest], depth)
            active.remove(digest)
            _require(not verify_hashes or _sha(expanded) == digest)
            return expanded
        return {key: visit(child, depth + 1) for key, child in item.items()}

    result = visit(root)
    _require(used == set(documents))
    _require(len(_canonical(result)) <= MAX_FAMILY_BYTES)
    return result


def _family(name: str, value: dict[str, Any]) -> dict[str, Any]:
    original = _bounded_copy(value, maximum_bytes=MAX_FAMILY_BYTES)
    root, documents = _flatten(original)
    # Sanitize after lifting to keep original nesting out of the generic limit.
    # Re-key changed documents by their *sanitized* content, never by old hashes.
    cleaned = sanitize_diagnostic_record(
        {"root": root, "documents": documents}, maximum_bytes=MAX_ATTACHMENT_BYTES
    )
    restored = _expand(cleaned["root"], cleaned["documents"], verify_hashes=False)
    root, documents = _flatten(restored)
    preserved = restored == original
    packet = dict(
        schema=FAMILY_SCHEMA,
        family=name,
        original_family_sha256=_sha(original),
        restored_family_sha256=_sha(restored),
        original_bytes_preserved=preserved,
        credential_redaction_applied=not preserved,
        root=root,
        documents=documents,
        meaning=_MEANING,
        **_FLAGS,
    )
    final = sanitize_diagnostic_record(packet, maximum_bytes=MAX_ATTACHMENT_BYTES)
    _require(final == packet, "RECEIVED_CAMERA_EXPORT_REDACTION_UNSTABLE")
    restore_received_camera_family(packet)
    return packet


def restore_received_camera_family(
    value: dict[str, Any], *, expected_original_family_sha256: str | None = None
) -> dict[str, Any]:
    """Pure exact reconstruction of an exported family (possibly redacted).

    No original subject verifier should accept redacted bytes as the retained
    originals. The packet flags and both hashes keep that distinction explicit.
    """
    _require(type(value) is dict)
    _require(
        set(value)
        == {
            "schema",
            "family",
            "original_family_sha256",
            "restored_family_sha256",
            "original_bytes_preserved",
            "credential_redaction_applied",
            "root",
            "documents",
            "meaning",
            *_FLAGS,
        }
        and value["schema"] == FAMILY_SCHEMA
        and value["meaning"] == _MEANING
        and all(value[key] is False for key in _FLAGS)
        and type(value["documents"]) is dict
        and len(value["documents"]) <= 64
        and type(value["original_bytes_preserved"]) is bool
        and type(value["credential_redaction_applied"]) is bool
        and value["credential_redaction_applied"]
        is not value["original_bytes_preserved"]
    )
    for key in ("original_family_sha256", "restored_family_sha256"):
        _require(type(value[key]) is str and _SHA.fullmatch(value[key]) is not None)
    _require(
        value["family"]
        in {"cycle-01", "cycle-02", "cycle-03", "cycle-04", "draft", "attempt"}
        and (
            expected_original_family_sha256 is None
            or value["original_family_sha256"] == expected_original_family_sha256
        )
    )
    _require(len(_canonical(value)) <= MAX_ATTACHMENT_BYTES)
    result = _expand(value["root"], value["documents"], verify_hashes=True)
    _require(type(result) is dict and _sha(result) == value["restored_family_sha256"])
    _require(
        (value["original_family_sha256"] == value["restored_family_sha256"])
        is value["original_bytes_preserved"]
    )
    return result


def _input(diagnostics: dict[str, Any]) -> dict[str, Any]:
    value = _bounded_copy(diagnostics)
    _require(type(value) is dict and value.get("schema") == DIAGNOSTICS_SCHEMA)
    required = {
        "schema",
        "original_context",
        "publication",
        "stage_states",
        "cycles",
        "draft",
        "draft_origin_notebook_sha256",
        "attempt",
        "camera_identity_request",
        "meaning",
        *_SERVICE_FLAGS,
    }
    # The service has additional fixed false declarations; none grant authority.
    extra_flags = {
        "canonical_stage_pass",
        "installation_qualified",
        "native_runtime_released",
        "measurement_truth_verified",
        "authenticated_operator_identity",
        "attachment_bytes_verified",
    }
    _require(required <= set(value) <= required | extra_flags | {"failed_draft"})
    _require(
        all(
            value[key] is False
            for key in (_SERVICE_FLAGS | extra_flags)
            if key in value
        )
    )
    cycles = value["cycles"]
    _require(type(cycles) is list and len(cycles) <= 4)
    identities: set[str] = set()
    for index, cycle in enumerate(cycles, 1):
        _require(
            type(cycle) is dict
            and set(cycle) == {"receipt_id", "sequence", "state", "originals", *_ROLES}
        )
        _require(
            type(cycle["receipt_id"]) is str
            and _RECEIPT.fullmatch(cycle["receipt_id"]) is not None
        )
        _require(
            type(cycle["sequence"]) is int
            and cycle["sequence"] == index
            and cycle["receipt_id"] not in identities
        )
        identities.add(cycle["receipt_id"])
        _require(type(cycle["originals"]) is list and len(cycle["originals"]) <= 16)
        for original in cycle["originals"]:
            _require(
                type(original) is dict
                and set(original)
                == {
                    "label",
                    "index",
                    "media_type",
                    "evidence_sha256",
                    "retention",
                    "reference",
                }
            )
        for role in _ROLES:
            record = cycle[role]
            _require(
                record is None
                or (
                    type(record) is dict
                    and set(record)
                    == {"document", "evidence_sha256", "retention", "reference"}
                )
            )
    for key in ("draft", "failed_draft", "attempt"):
        _require(value.get(key) is None or type(value[key]) is dict)
    if value.get("failed_draft") is not None:
        _require(
            set(value["failed_draft"]) == {"document", "draft_origin_notebook_sha256"}
        )
    if value["attempt"] is not None:
        attempt = value["attempt"]
        _require(set(attempt) == {"action_id", "receipt_id", "records"})
        _require(type(attempt["records"]) is dict and len(attempt["records"]) <= 20)
        for role, record in attempt["records"].items():
            original = re.fullmatch(r"original_(?:0[0-9]|1[0-5])", role) is not None
            _require(role in _ROLES or original)
            _require(type(record) is dict)
            required_record = {"reference", "retention", "evidence_sha256", "label"}
            _require(
                set(record) == required_record | (set() if original else {"document"})
            )
    return value


def export_received_camera_metadata(
    diagnostics: dict[str, Any],
    *,
    export_parent: Path,
    source_sha256: str,
    launch_id: str,
    cancellation: Event,
    deadline_ns: int,
) -> dict[str, Any]:
    """Explicit export of all supplied families; never re-read inputs or media.

    The original context may be historical. ``source_sha256``/``launch_id`` name
    this export's caller context, not rewritten receipt bindings. The caller
    performs source checks. A completed exporter receipt survives a late Stop.
    """
    _require(type(source_sha256) is str and _SHA.fullmatch(source_sha256) is not None)
    _require(type(launch_id) is str and _LAUNCH.fullmatch(launch_id) is not None)
    now = monotonic_ns()
    _require(type(deadline_ns) is int and now < deadline_ns <= now + MAX_DURATION_NS)

    def check() -> None:
        _require(not cancellation.is_set(), "RECEIVED_CAMERA_EXPORT_CANCELLED")
        _require(monotonic_ns() < deadline_ns, "RECEIVED_CAMERA_EXPORT_TIMED_OUT")

    check()
    value = _input(diagnostics)
    families = [
        (f"cycle-{index:02d}", cycle) for index, cycle in enumerate(value["cycles"], 1)
    ]
    if value["draft"] is not None or value.get("failed_draft") is not None:
        families.append(
            (
                "draft",
                {
                    key: value.get(key)
                    for key in ("draft", "draft_origin_notebook_sha256", "failed_draft")
                },
            )
        )
    if value["attempt"] is not None:
        families.append(("attempt", value["attempt"]))
    attachments: dict[str, bytes] = {}
    index_rows = []
    for name, family in families:
        check()
        packet = _family(name, family)
        filename = f"received-camera-{name}.json"
        attachments[filename] = _json_bytes(packet)
        index_rows.append(
            {
                key: packet[key]
                for key in (
                    "family",
                    "original_family_sha256",
                    "restored_family_sha256",
                    "original_bytes_preserved",
                    "credential_redaction_applied",
                )
            }
            | {"attachment": "attachment-" + filename}
        )
    metadata = {
        key: item
        for key, item in value.items()
        if key
        not in {
            "cycles",
            "draft",
            "draft_origin_notebook_sha256",
            "failed_draft",
            "attempt",
        }
    }
    # Include a draft-origin-only value even when there is no draft family.
    metadata["draft_origin_notebook_sha256"] = value["draft_origin_notebook_sha256"]
    clean_metadata = sanitize_diagnostic_record(metadata)
    snapshot = dict(
        schema=EXPORT_SCHEMA,
        session_id=launch_id,
        mode="PHYSICAL_DIAGNOSTIC",
        source_binding_sha256=source_sha256,
        source_identity={"source_sha256": source_sha256},
        original=clean_metadata,
        original_field_names=sorted(value),
        original_metadata_sha256=_sha(metadata),
        exported_metadata_sha256=_sha(clean_metadata),
        metadata_bytes_preserved=clean_metadata == metadata,
        metadata_credential_redaction_applied=clean_metadata != metadata,
        families=index_rows,
        original_diagnostics_sha256=_sha(value),
        meaning=_MEANING,
        **_FLAGS,
    )
    # Include the final wrapper in the unchanged snapshot sanitizer budget,
    # before any directory creation, and require stable second-pass redaction.
    _require(
        sanitize_diagnostic_record(snapshot) == snapshot,
        "RECEIVED_CAMERA_EXPORT_REDACTION_UNSTABLE",
    )
    check()
    exporter = WizardDiagnosticExporter(export_parent)
    exporter.prepare(create=True)
    check()
    # No post-success deadline check: a durable export remains useful when a
    # late Stop/source change prevents current publication in the caller.
    return exporter.export(snapshot, [], attachments=attachments)
