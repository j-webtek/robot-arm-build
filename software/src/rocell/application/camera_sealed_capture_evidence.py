"""Versioned checksum-bearing collection, separate from the native v2 pair.

Structural codecs only. The exact settings-capture permit and original store
must independently bind this collection before receipt/terminal publication.
Legacy pair readers continue rejecting this type and its versioned final index.
"""

from dataclasses import dataclass
import base64
from typing import Mapping, Any

from .camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
    validate_camera_activation_evidence,
)
from .camera_activation_evidence_parts import (
    CameraEvidenceRecord,
    encode_camera_evidence_parts,
    inspect_camera_evidence_parts,
    index_name,
    INDEX_KIND as NATIVE_INDEX_KIND,
    _binding,
)
from .camera_capture_checksum import (
    CameraCaptureChecksum,
    MAX_BYTES,
    SCHEMA,
    verify_capture_checksum,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest, _require

MAX_SEALED_CAPTURE_BYTES = MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES + MAX_BYTES
PART_KIND = "CAMERA_CAPTURE_CHECKSUM_PART_V1"
INDEX_KIND = "CAMERA_CONFIGURATION_CAPTURE_EVIDENCE_INDEX_V2"
MAX_PARTS = 26  # Existing 24 native parts, one checksum part and final index.
_PART_FIELDS = {
    "attempt_id",
    "permit_sha256",
    "schema",
    "payload_bytes",
    "payload_sha256",
    "payload_base64",
}
_DESCRIPTOR_FIELDS = {"schema", "payload_bytes", "payload_sha256", "part"}


@dataclass(frozen=True, slots=True)
class SealedCameraCaptureEvidence:
    """Sealable data, not proof it has been retained or terminally sealed."""

    native: tuple[CameraActivationArtifact, ...]
    checksum: CameraCaptureChecksum

    def __post_init__(self):
        _require(type(self.checksum) is CameraCaptureChecksum, "EXACT_CAPTURE_CHECKSUM")
        # The verifier below independently decodes the exact native pair and
        # rebuilds every checksum binding. Repeating that decode here adds no
        # independent input or check, especially during complete-history audits.
        verify_capture_checksum(
            self.checksum.payload,
            evidence=self.native,
            expected_request_key=self.checksum.to_dict()["request_key"],
            expected_sha256=self.checksum.sha256,
        )
        _require(
            self.payload_bytes <= MAX_SEALED_CAPTURE_BYTES, "SEALED_CAPTURE_BYTE_LIMIT"
        )

    @property
    def payload_bytes(self):
        return sum(len(item.payload) for item in self.native) + len(
            self.checksum.payload
        )

    @property
    def evidence_sha256s(self):
        return (*[item.payload_sha256 for item in self.native], self.checksum.sha256)


def checksum_part_name(attempt_id):
    index_name(attempt_id)  # Reuse the closed original attempt identifier grammar.
    return f"receipt-{attempt_id}-camera_activation_checksum_a.json"


def encode_sealed_capture_parts(evidence: SealedCameraCaptureEvidence):
    _require(
        type(evidence) is SealedCameraCaptureEvidence, "EXACT_SEALED_CAPTURE_EVIDENCE"
    )
    evidence.__post_init__()
    native_records = encode_camera_evidence_parts(evidence.native)
    native_index = native_records[-1].data()
    attempt, permit = native_index["attempt_id"], native_index["permit_sha256"]
    part = checksum_part_name(attempt)
    descriptor = dict(
        schema=SCHEMA,
        payload_bytes=len(evidence.checksum.payload),
        payload_sha256=evidence.checksum.sha256,
        part=part,
    )
    checksum_record = CameraEvidenceRecord(
        part,
        PART_KIND,
        canonical(
            dict(
                attempt_id=attempt,
                permit_sha256=permit,
                **{key: value for key, value in descriptor.items() if key != "part"},
                payload_base64=base64.b64encode(evidence.checksum.payload).decode(
                    "ascii"
                ),
            )
        ),
    )
    final = CameraEvidenceRecord(
        index_name(attempt),
        INDEX_KIND,
        canonical(
            dict(
                attempt_id=attempt,
                permit_sha256=permit,
                native_evidence=native_index["evidence"],
                checksum=descriptor,
            )
        ),
    )
    # Do not write an old v2 index and then replace it. All immutable parts are
    # published once; the distinct final index binds the complete new collection.
    return (*native_records[:-1], checksum_record, final)


@dataclass(frozen=True, slots=True)
class SealedCaptureParts:
    complete: bool
    part_count: int
    artifacts: SealedCameraCaptureEvidence | None


def inspect_sealed_capture_parts(
    records: Mapping[str, dict[str, Any]],
    *,
    expected_attempt_id,
    expected_permit_sha256,
) -> SealedCaptureParts:
    """Validate every supplied part, including incomplete publication, without I/O.

    The original M1 caller must supply the complete attempt subset and audit the
    unchanged full family/ledger. Decomposing the native index below only reuses a
    pure part codec; it does not construct a past store, journal or permission.
    """
    _binding(expected_attempt_id, expected_permit_sha256)
    _require(
        isinstance(records, Mapping) and len(records) <= MAX_PARTS,
        "SEALED_CAPTURE_RECORD_LIMIT",
    )
    final_name = index_name(expected_attempt_id)
    checksum_name = checksum_part_name(expected_attempt_id)
    final, checksum, native_parts = None, None, {}
    for filename, record in records.items():
        _require(
            type(record) is dict and type(record.get("data")) is dict,
            "SEALED_CAPTURE_ENVELOPE",
        )
        data = record["data"]
        _require(
            data.get("attempt_id") == expected_attempt_id
            and data.get("permit_sha256") == expected_permit_sha256,
            "SEALED_CAPTURE_ORIGINAL_BINDING",
        )
        if filename == final_name:
            _require(
                record.get("kind") == INDEX_KIND
                and set(data)
                == {"attempt_id", "permit_sha256", "native_evidence", "checksum"},
                "SEALED_CAPTURE_INDEX",
            )
            final = data
        elif filename == checksum_name:
            _require(
                record.get("kind") == PART_KIND and set(data) == _PART_FIELDS,
                "SEALED_CAPTURE_CHECKSUM_PART",
            )
            _require(
                data["schema"] == SCHEMA
                and type(data["payload_bytes"]) is int
                and 0 < data["payload_bytes"] <= MAX_BYTES,
                "SEALED_CAPTURE_CHECKSUM_LIMIT",
            )
            encoded = data["payload_base64"]
            _require(
                type(encoded) is str and len(encoded) <= 4 * ((MAX_BYTES + 2) // 3),
                "SEALED_CAPTURE_BASE64_LIMIT",
            )
            try:
                payload = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as error:
                raise ValueError("SEALED_CAPTURE_BASE64") from error
            _require(
                len(payload) == data["payload_bytes"]
                and digest(payload) == data["payload_sha256"]
                and base64.b64encode(payload).decode("ascii") == encoded,
                "SEALED_CAPTURE_CHECKSUM_HASH",
            )
            checksum = CameraCaptureChecksum(payload)
        else:
            # No unvalidated leftovers: the existing pure native-part decoder
            # rejects unknown kinds, duplicate roles, wrong names and extra parts.
            native_parts[filename] = record
    if final is not None:
        _require(checksum is not None, "SEALED_CAPTURE_CHECKSUM_MISSING")
        assert checksum is not None
        descriptor = final["checksum"]
        _require(
            type(descriptor) is dict and set(descriptor) == _DESCRIPTOR_FIELDS,
            "SEALED_CAPTURE_CHECKSUM_DESCRIPTOR",
        )
        _require(
            descriptor
            == dict(
                schema=SCHEMA,
                payload_bytes=len(checksum.payload),
                payload_sha256=checksum.sha256,
                part=checksum_name,
            ),
            "SEALED_CAPTURE_CHECKSUM_DESCRIPTOR_BINDING",
        )
        # Only an in-memory descriptor adapter for the unchanged native codec.
        # This value is never published or presented as an authenticated original.
        native_parts[final_name] = dict(
            kind=NATIVE_INDEX_KIND,
            data=dict(
                attempt_id=expected_attempt_id,
                permit_sha256=expected_permit_sha256,
                evidence=final["native_evidence"],
            ),
        )
    native = inspect_camera_evidence_parts(
        native_parts,
        expected_attempt_id=expected_attempt_id,
        expected_permit_sha256=expected_permit_sha256,
    )
    count = native.part_count + int(checksum is not None)
    if final is None:
        return SealedCaptureParts(False, count, None)
    _require(
        native.complete and native.artifacts is not None,
        "SEALED_CAPTURE_NATIVE_INCOMPLETE",
    )
    assert checksum is not None and native.artifacts is not None
    return SealedCaptureParts(
        True, count, SealedCameraCaptureEvidence(native.artifacts, checksum)
    )
