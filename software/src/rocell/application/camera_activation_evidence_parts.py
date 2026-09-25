"""Pure bounded part/index codec for original camera-v2 diagnostic storage.

No publication, filesystem access or authority is supplied here. The M1 adapter
must provide the complete original record set under its leases and bind this
data to the full original permit/campaign, not just trust self-consistent hashes.
Each raw part is at most 64 KiB; the existing record and family quotas stay intact.
"""

import base64
from dataclasses import dataclass
import re
from typing import Any, Mapping

from .camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    ROLES,
    ROLE_LIMITS,
    ROLE_SCHEMAS,
    validate_camera_activation_evidence,
)
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    _require,
    _sha,
)

PART_BYTES = 64 * 1024
PART_KIND = "CAMERA_ACTIVATION_EVIDENCE_PART_V2"
INDEX_KIND = "CAMERA_ACTIVATION_EVIDENCE_INDEX_V2"
_ATTEMPT = re.compile(r"attempt-[0-9a-f]{32}\Z")
_PART_FIELDS = {
    "attempt_id",
    "permit_sha256",
    "role",
    "part_index",
    "part_count",
    "artifact_bytes",
    "artifact_sha256",
    "payload_bytes",
    "payload_sha256",
    "payload_base64",
}
_DESCRIPTOR_FIELDS = {
    "role",
    "schema",
    "label",
    "payload_bytes",
    "payload_sha256",
    "parts",
}


def _binding(attempt_id: str, permit_sha256: str) -> None:
    _require(
        type(attempt_id) is str and bool(_ATTEMPT.fullmatch(attempt_id)),
        "CAMERA_PART_ATTEMPT_ID",
    )
    _sha(permit_sha256)
    _require(permit_sha256 != "0" * 64, "CAMERA_PART_PERMIT_HASH")


def part_name(attempt_id: str, role: str, index: int) -> str:
    _require(
        type(attempt_id) is str and bool(_ATTEMPT.fullmatch(attempt_id)),
        "CAMERA_PART_ATTEMPT_ID",
    )
    _require(
        type(role) is str
        and role in ROLES
        and type(index) is int
        and 0 <= index < ROLE_LIMITS[role] // PART_BYTES,
        "CAMERA_PART_NAME",
    )
    # Letter suffixes already fit the existing finite coordinator filename
    # grammar. No new path grammar, extension, user filename or directory is used.
    return f"receipt-{attempt_id}-camera_activation_{role}_{chr(97 + index)}.json"


def index_name(attempt_id: str) -> str:
    _require(
        type(attempt_id) is str and bool(_ATTEMPT.fullmatch(attempt_id)),
        "CAMERA_PART_ATTEMPT_ID",
    )
    return f"evidence-{attempt_id}-retained.json"


@dataclass(frozen=True, slots=True)
class CameraEvidenceRecord:
    filename: str
    kind: str
    data_payload: bytes

    def data(self) -> dict[str, Any]:
        from rocell.providers.windows.owned_worker_process import decode_owned_json

        return decode_owned_json(self.data_payload, maximum=96 * 1024)


@dataclass(frozen=True, slots=True)
class CameraEvidenceParts:
    """An absent final index is incomplete, even if all declared parts are present."""

    complete: bool
    part_count: int
    artifacts: tuple[CameraActivationArtifact, ...] | None


def encode_camera_evidence_parts(
    artifacts: tuple[CameraActivationArtifact, ...],
) -> tuple[CameraEvidenceRecord, ...]:
    checked = validate_camera_activation_evidence(artifacts)
    request = checked.prepared.admission_request.to_dict()
    attempt, permit = request["attempt_id"], request["permit_sha256"]
    _binding(attempt, permit)
    records, descriptors = [], []
    for artifact in artifacts:
        count = (len(artifact.payload) + PART_BYTES - 1) // PART_BYTES
        names = []
        for index in range(count):
            raw = artifact.payload[index * PART_BYTES : (index + 1) * PART_BYTES]
            filename = part_name(attempt, artifact.role, index)
            names.append(filename)
            data = dict(
                attempt_id=attempt,
                permit_sha256=permit,
                role=artifact.role,
                part_index=index,
                part_count=count,
                artifact_bytes=len(artifact.payload),
                artifact_sha256=artifact.payload_sha256,
                payload_bytes=len(raw),
                payload_sha256=digest(raw),
                payload_base64=base64.b64encode(raw).decode("ascii"),
            )
            records.append(CameraEvidenceRecord(filename, PART_KIND, canonical(data)))
        descriptors.append(
            dict(
                role=artifact.role,
                schema=artifact.schema,
                label=artifact.label,
                payload_bytes=len(artifact.payload),
                payload_sha256=artifact.payload_sha256,
                parts=names,
            )
        )
    # Publication order is part of the API: all parts, then the final index.
    records.append(
        CameraEvidenceRecord(
            index_name(attempt),
            INDEX_KIND,
            canonical(
                dict(
                    attempt_id=attempt,
                    permit_sha256=permit,
                    evidence=descriptors,
                )
            ),
        )
    )
    return tuple(records)


def inspect_camera_evidence_parts(
    records: Mapping[str, dict[str, Any]],
    *,
    expected_attempt_id: str,
    expected_permit_sha256: str,
) -> CameraEvidenceParts:
    """Inspect complete envelopes or an incomplete original publication.

    Input is the complete camera-specific subset for this attempt, selected by
    the full family audit, not caller-selected arbitrary paths or a filtered
    attempt ledger. Original envelope/domain hashes are the M1 reader's duty.
    """
    _binding(expected_attempt_id, expected_permit_sha256)
    _require(
        isinstance(records, Mapping) and len(records) <= 25, "CAMERA_PART_RECORD_COUNT"
    )
    parts: dict[str, tuple[dict[str, Any], bytes]] = {}
    groups: dict[str, tuple[int, int, str]] = {}
    final = None
    for filename, record in records.items():
        _require(
            type(record) is dict and type(record.get("data")) is dict,
            "CAMERA_PART_ENVELOPE",
        )
        data = record["data"]
        _require(
            data.get("attempt_id") == expected_attempt_id
            and data.get("permit_sha256") == expected_permit_sha256,
            "CAMERA_PART_ORIGINAL_BINDING",
        )
        if record.get("kind") == INDEX_KIND:
            _require(
                filename == index_name(expected_attempt_id)
                and final is None
                and set(data) == {"attempt_id", "permit_sha256", "evidence"},
                "CAMERA_INDEX_ENVELOPE",
            )
            final = data
            continue
        _require(
            record.get("kind") == PART_KIND and set(data) == _PART_FIELDS,
            "CAMERA_PART_FIELDS",
        )
        role, index, count, total = (
            data[key] for key in ("role", "part_index", "part_count", "artifact_bytes")
        )
        _require(type(role) is str and role in ROLES, "CAMERA_PART_ROLE")
        _require(
            type(total) is int
            and 0 < total <= ROLE_LIMITS[role]
            and type(count) is int
            and count == (total + PART_BYTES - 1) // PART_BYTES,
            "CAMERA_PART_ARTIFACT_LIMIT",
        )
        _require(
            type(index) is int
            and 0 <= index < count
            and filename == part_name(expected_attempt_id, role, index),
            "CAMERA_PART_FILENAME",
        )
        _sha(data["artifact_sha256"])
        group = total, count, data["artifact_sha256"]
        _require(
            role not in groups or groups[role] == group, "CAMERA_PART_GROUP_MISMATCH"
        )
        groups[role] = group
        encoded = data["payload_base64"]
        _require(
            type(encoded) is str and len(encoded) <= 4 * ((PART_BYTES + 2) // 3),
            "CAMERA_PART_BASE64_LIMIT",
        )
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as error:
            raise ValueError("CAMERA_PART_BASE64") from error
        expected_length = min(PART_BYTES, total - index * PART_BYTES)
        _require(
            type(data["payload_bytes"]) is int
            and data["payload_bytes"] == len(raw) == expected_length
            and digest(raw) == data["payload_sha256"]
            and base64.b64encode(raw).decode("ascii") == encoded,
            "CAMERA_PART_PAYLOAD_BINDING",
        )
        parts[filename] = data, raw
    if final is None:
        return CameraEvidenceParts(False, len(parts), None)
    descriptors = final["evidence"]
    _require(type(descriptors) is list and len(descriptors) == 2, "CAMERA_INDEX_PAIR")
    artifacts, consumed = [], set()
    for role, descriptor in zip(ROLES, descriptors):
        _require(
            type(descriptor) is dict
            and set(descriptor) == _DESCRIPTOR_FIELDS
            and descriptor["role"] == role
            and descriptor["schema"] == ROLE_SCHEMAS[role]
            and descriptor["label"] == "camera-activation-" + role + "-v2",
            "CAMERA_INDEX_DESCRIPTOR",
        )
        size = descriptor["payload_bytes"]
        _require(
            type(size) is int and 0 < size <= ROLE_LIMITS[role],
            "CAMERA_INDEX_ARTIFACT_LIMIT",
        )
        count = (size + PART_BYTES - 1) // PART_BYTES
        names = [part_name(expected_attempt_id, role, n) for n in range(count)]
        _require(
            descriptor["parts"] == names and all(name in parts for name in names),
            "CAMERA_INDEX_PARTS_MISSING_OR_CHANGED",
        )
        _require(
            groups.get(role) == (size, count, descriptor["payload_sha256"]),
            "CAMERA_INDEX_GROUP_MISMATCH",
        )
        payload = b"".join(parts[name][1] for name in names)
        _require(
            len(payload) == size and digest(payload) == descriptor["payload_sha256"],
            "CAMERA_INDEX_ARTIFACT_HASH",
        )
        artifacts.append(CameraActivationArtifact(role, payload))
        consumed.update(names)
    _require(consumed == set(parts), "CAMERA_INDEX_EXTRA_PARTS")
    pair = tuple(artifacts)
    checked = validate_camera_activation_evidence(pair)
    request = checked.prepared.admission_request.to_dict()
    _require(
        request["attempt_id"] == expected_attempt_id
        and request["permit_sha256"] == expected_permit_sha256,
        "CAMERA_REASSEMBLED_ORIGINAL_BINDING",
    )
    return CameraEvidenceParts(True, len(parts), pair)
