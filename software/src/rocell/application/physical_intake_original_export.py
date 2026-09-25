"""Explicit unredacted copies of already-read original intake bytes.

No inbox, device or M1 reads occur here. The server supplies the original,
contextually verified submission and byte tuples under its own readback scope.
This diagnostic copy is not M1 crash-durability or physical qualification.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from threading import Event
from time import monotonic_ns
from typing import Any, Callable
import uuid

from .physical_intake_submission import (
    IntakeAttachment,
    PhysicalIntakeSubmission,
    MAX_ATTACHMENTS,
    MAX_INVENTORY_BYTES,
)
from .physical_onboarding import EvidenceReference
from .physical_onboarding_durability import read_bounded_regular_file
from .wizard_diagnostic_export import (
    _absolute_directory,
    _checked_directory,
    _directory_guard,
    _identity,
)

MANIFEST_SCHEMA = "rocell.physical_intake_original_export.v1"
RECEIPT_SCHEMA = "rocell.physical_intake_original_export_receipt.v1"
MAX_MANIFEST_BYTES = 32 * 1024
MAX_EXPORT_DURATION_NS = 120_000_000_000
PRIVACY_WARNING = (
    "PRIVATE ORIGINALS: attachment bytes and submission text are copied without "
    "redaction. They may contain private material. Review before sharing; "
    "changing or redacting a file changes its original hash."
)
_FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "canonical_stage_pass": False,
    "device_io_performed": False,
}
_CODES = frozenset(
    {
        "PRIVATE_ORIGINALS_APPROVAL_REQUIRED",
        "INVALID_ORIGINAL_EXPORT_INPUT",
        "ORIGINAL_EXPORT_CANCELLED",
        "ORIGINAL_EXPORT_TIMED_OUT",
        "ORIGINAL_EXPORT_CONTEXT_CHANGED",
        "ORIGINAL_EXPORT_IO_FAILED",
        "ORIGINAL_EXPORT_BYTE_MISMATCH",
        "ORIGINAL_EXPORT_NAME_COLLISION",
    }
)


class PhysicalIntakeOriginalExportError(ValueError):
    def __init__(self, code: str, receipt: dict[str, Any] | None = None) -> None:
        self.code = code if code in _CODES else "ORIGINAL_EXPORT_IO_FAILED"
        self.receipt = deepcopy(receipt)
        super().__init__(self.code)


def _require(value: bool, code: str = "INVALID_ORIGINAL_EXPORT_INPUT") -> None:
    if not value:
        raise PhysicalIntakeOriginalExportError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _check(cancellation: Event, deadline_ns: int) -> None:
    _require(not cancellation.is_set(), "ORIGINAL_EXPORT_CANCELLED")
    _require(monotonic_ns() < deadline_ns, "ORIGINAL_EXPORT_TIMED_OUT")


def _write_payload(
    path: Path,
    payload: bytes,
    *,
    cancellation: Event,
    deadline_ns: int,
    on_written: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Exclusive create, bounded writes, exact readback; partial bytes stay put."""
    _check(cancellation, deadline_ns)
    with path.open("xb") as stream:
        for offset in range(0, len(payload), 64 * 1024):
            _check(cancellation, deadline_ns)
            chunk = payload[offset : offset + 64 * 1024]
            _require(stream.write(chunk) == len(chunk), "ORIGINAL_EXPORT_IO_FAILED")
        stream.flush()
        os.fsync(stream.fileno())
    _check(cancellation, deadline_ns)
    retained = read_bounded_regular_file(
        path, maximum_bytes=len(payload), label="private intake export bytes"
    )
    _require(retained == payload, "ORIGINAL_EXPORT_BYTE_MISMATCH")
    if on_written is not None:
        on_written()
    _check(cancellation, deadline_ns)
    return {"name": path.name, "bytes": len(payload), "sha256": _hash(payload)}


def export_physical_intake_originals(
    export_parent: Path,
    *,
    submission: PhysicalIntakeSubmission,
    originals: tuple[tuple[EvidenceReference, str, str, bytes], ...],
    include_private_originals: bool,
    cancellation: Event,
    deadline_ns: int,
) -> dict[str, Any]:
    """Copy only exact supplied originals; parent must already be prepared.

    No contextual authenticity is inferred from caller-owned hashes. The outer
    service must verify the original M1 records before this call, and re-audit
    after leaving its scope before publishing a current receipt.
    """
    receipt: dict[str, Any] | None = None
    try:
        _require(
            include_private_originals is True, "PRIVATE_ORIGINALS_APPROVAL_REQUIRED"
        )
        _require(type(submission) is PhysicalIntakeSubmission)
        subject = PhysicalIntakeSubmission(submission.payload)
        data = subject.to_dict()
        _require(
            type(cancellation) is Event
            and type(deadline_ns) is int
            and 0 < deadline_ns < 2**63
            and deadline_ns - monotonic_ns() <= MAX_EXPORT_DURATION_NS
        )
        _check(cancellation, deadline_ns)
        _require(type(originals) is tuple and len(originals) <= MAX_ATTACHMENTS)
        attachments: list[dict[str, Any]] = []
        payloads: list[bytes] = []
        for original in originals:
            _require(type(original) is tuple and len(original) == 4)
            reference, basename, media_type, payload = original
            descriptor = IntakeAttachment(reference, basename, media_type)
            _require(
                type(payload) is bytes
                and len(payload) == reference.payload_bytes
                and _hash(payload) == reference.payload_sha256,
                "ORIGINAL_EXPORT_BYTE_MISMATCH",
            )
            attachments.append(descriptor.to_dict())
            payloads.append(payload)
        _require(
            _canonical(attachments) == _canonical(data["attachments"]),
            "ORIGINAL_EXPORT_CONTEXT_CHANGED",
        )
        attachment_bytes = sum(len(value) for value in payloads)
        _require(attachment_bytes <= MAX_INVENTORY_BYTES)
        _absolute_directory(export_parent)
        root = _checked_directory(export_parent)
        _check(cancellation, deadline_ns)
        root_identity = _identity(root)
        export_id = "physical-intake-originals-" + uuid.uuid4().hex
        destination = root / export_id
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "status": "INCOMPLETE_OR_HELD",
            "path": str(destination),
            "export_id": export_id,
            "submission_sha256": subject.sha256,
            "collection_id": data["collection_id"],
            "attachment_count": len(attachments),
            "attachment_bytes": attachment_bytes,
            "submission_bytes": len(subject.payload),
            "manifest_bytes": 0,
            "total_bytes": 0,
            "verified_attachment_count": 0,
            "verified_attachment_bytes": 0,
            "submission_written": False,
            "directory_created": False,
            "manifest_written": False,
            "manifest_sha256": None,
            "original_bytes_preserved": False,
            "privacy_warning": PRIVACY_WARNING,
            **_FLAGS,
        }
        with _directory_guard(root):
            _check(cancellation, deadline_ns)
            _require(
                _identity(root) == root_identity, "ORIGINAL_EXPORT_CONTEXT_CHANGED"
            )
            try:
                destination.mkdir(exist_ok=False)
            except FileExistsError as error:
                raise PhysicalIntakeOriginalExportError(
                    "ORIGINAL_EXPORT_NAME_COLLISION"
                ) from error
            receipt["directory_created"] = True
            with _directory_guard(destination):
                destination_identity = _identity(destination)
                rows = []
                for index, (attachment, payload) in enumerate(
                    zip(attachments, payloads, strict=True)
                ):
                    name = f"original-{index:02d}-" + attachment["basename"]
                    record = _write_payload(
                        destination / name,
                        payload,
                        cancellation=cancellation,
                        deadline_ns=deadline_ns,
                    )
                    rows.append(
                        {
                            **record,
                            "reference": attachment["reference"],
                            "original_basename": attachment["basename"],
                            "media_type": attachment["media_type"],
                        }
                    )
                    receipt["verified_attachment_count"] += 1
                    receipt["verified_attachment_bytes"] += len(payload)
                    receipt["total_bytes"] += len(payload)
                submission_file = _write_payload(
                    destination / "submission.json",
                    subject.payload,
                    cancellation=cancellation,
                    deadline_ns=deadline_ns,
                )
                receipt["submission_written"] = True
                receipt["total_bytes"] += len(subject.payload)
                manifest = {
                    "schema": MANIFEST_SCHEMA,
                    "export_id": export_id,
                    "complete": True,
                    "submission_sha256": subject.sha256,
                    "collection_id": data["collection_id"],
                    "binding": data["binding"],
                    "submission_file": submission_file,
                    "attachments": rows,
                    "attachment_count": len(rows),
                    "attachment_bytes": attachment_bytes,
                    "submission_bytes": len(subject.payload),
                    "total_payload_bytes": attachment_bytes + len(subject.payload),
                    "privacy_warning": PRIVACY_WARNING,
                    **_FLAGS,
                    "meaning": "Byte-preserving diagnostic copy of original retained intake subjects. No physical truth, stage acceptance, signature or M1 durability is established.",
                }
                manifest_bytes = _canonical(manifest)
                _require(len(manifest_bytes) <= MAX_MANIFEST_BYTES)
                # Recheck all completed payloads immediately before publishing
                # the manifest. No source filename is consulted or executed.
                for row in [*rows, submission_file]:
                    _check(cancellation, deadline_ns)
                    raw = read_bounded_regular_file(
                        destination / row["name"],
                        maximum_bytes=row["bytes"],
                        label="private intake export recheck",
                    )
                    _require(
                        len(raw) == row["bytes"] and _hash(raw) == row["sha256"],
                        "ORIGINAL_EXPORT_BYTE_MISMATCH",
                    )
                _require(
                    _identity(destination) == destination_identity
                    and _identity(root) == root_identity,
                    "ORIGINAL_EXPORT_CONTEXT_CHANGED",
                )

                def manifest_written() -> None:
                    assert receipt is not None
                    receipt["manifest_written"] = True

                _write_payload(
                    destination / "manifest.json",
                    manifest_bytes,
                    cancellation=cancellation,
                    deadline_ns=deadline_ns,
                    on_written=manifest_written,
                )
                receipt.update(
                    manifest_written=True,
                    manifest_sha256=_hash(manifest_bytes),
                    manifest_bytes=len(manifest_bytes),
                    total_bytes=receipt["total_bytes"] + len(manifest_bytes),
                )
                _check(cancellation, deadline_ns)
                _require(
                    _identity(destination) == destination_identity,
                    "ORIGINAL_EXPORT_CONTEXT_CHANGED",
                )
            _check(cancellation, deadline_ns)
            _require(
                _identity(root) == root_identity, "ORIGINAL_EXPORT_CONTEXT_CHANGED"
            )
        _check(cancellation, deadline_ns)
        receipt.update(
            status="EXPORTED_PRIVATE_ORIGINALS", original_bytes_preserved=True
        )
        return deepcopy(receipt)
    except Exception as error:
        code = (
            error.code
            if type(error) is PhysicalIntakeOriginalExportError
            else "ORIGINAL_EXPORT_IO_FAILED"
        )
        if receipt is not None:
            receipt.update(status="INCOMPLETE_OR_HELD", error_code=code)
        raise PhysicalIntakeOriginalExportError(code, receipt) from error
