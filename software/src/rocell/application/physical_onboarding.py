"""Persistent, zero-motion core for physical workcell onboarding.

This module is intentionally an orchestration and evidence boundary, not a
hardware driver.  It records the canonical fifteen-stage first-power-on plan,
derives exactly one next action, and makes restart behavior conservative.  No
API in this module can write a controller command, authorize motion, authorize
contact, or silently replay an acquisition after a process restart.

The durable representation has three parts:

* an immutable, content-bound ``header.json``;
* append-only, hash-chained stage events; and
* content-addressed evidence packages whose ``manifest.json`` is written last.

All JSON owned by this module is strict and canonical.  Load rejects duplicate
keys, floats, unknown fields, non-canonical bytes, symlinks, unexpected paths,
oversized resources, broken event chains, and evidence hash drift.  A stage
left in ``ACQUIRING`` is never retried by resume; its sole next action is manual
reconciliation.  ``SIDE_EFFECT_UNCERTAIN`` is terminal for the session.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from rocell.application.first_power_on_onboarding import (
    STAGE_ORDER as REHEARSAL_STAGE_ORDER,
)


SESSION_HEADER_SCHEMA = "rocell.physical_onboarding_header.v1"
SESSION_EVENT_SCHEMA = "rocell.physical_onboarding_event.v1"
SESSION_HIGH_WATER_SCHEMA = "rocell.physical_onboarding_high_water.v1"
EVIDENCE_MANIFEST_SCHEMA = "rocell.physical_onboarding_evidence_manifest.v1"

MAX_JSON_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_EVIDENCE_BYTES = 512 * 1024 * 1024
MAX_EVIDENCE_ITEMS = 512
MAX_EVENT_EVIDENCE_ITEMS = 32
MAX_JOURNAL_EVENTS = 512

_ZERO_DIGEST = "0" * 64
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_DETAIL_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_MEDIA_TYPE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,63}/"
    r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,63}$"
)
_EVENT_FILENAME = re.compile(r"^event-([0-9]{6})\.json$")
_EVIDENCE_DIRECTORY = re.compile(r"^evidence-([0-9a-f]{64})$")
_HIGH_WATER_FILENAME = "high-water.json"


class PhysicalOnboardingError(ValueError):
    """The onboarding session is malformed, unsafe, or transition-invalid."""


class PhysicalOnboardingStage(str, Enum):
    """Exact physical counterpart of the canonical fifteen-stage rehearsal."""

    WORKSPACE_SOURCES = "workspace_sources"
    STATIC_CAMERA_CONTRACT = "static_camera_contract"
    CAMERA_RECEIPT = "camera_receipt"
    CAMERA_IDENTITY = "camera_identity"
    CAMERA_MODE_CONTROLS = "camera_mode_controls"
    CAMERA_FRAME_FRESHNESS = "camera_frame_freshness"
    OPTICS_INTRINSICS = "optics_intrinsics"
    STATIC_REGISTRATION = "static_registration"
    ARM_IDENTITY = "arm_identity"
    POWER_SAFETY = "power_safety"
    POWER_ON_OBSERVATION = "power_on_observation"
    FEEDBACK_ONLY_CONNECTION = "feedback_only_connection"
    REFERENCE_FRAME_CALIBRATION = "reference_frame_calibration"
    NONCONTACT_ACCEPTANCE = "noncontact_acceptance"
    PHYSICAL_HANDOFF = "physical_handoff"


STAGE_ORDER = tuple(PhysicalOnboardingStage)
if tuple(stage.value for stage in STAGE_ORDER) != tuple(
    stage.value for stage in REHEARSAL_STAGE_ORDER
):
    raise RuntimeError("physical onboarding stage order differs from rehearsal")


class StageState(str, Enum):
    """Persistent or conservatively derived state of one onboarding stage."""

    PENDING = "PENDING"
    WAITING_OPERATOR = "WAITING_OPERATOR"
    ACQUIRING = "ACQUIRING"
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    INVALIDATED = "INVALIDATED"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    COMPLETE_DIAGNOSTIC = "COMPLETE_DIAGNOSTIC"


_ACTION_CODES = {
    PhysicalOnboardingStage.WORKSPACE_SOURCES: "VERIFY_CONTROLLED_WORKSPACE",
    PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT: (
        "VERIFY_STATIC_CAMERA_CONTRACT"
    ),
    PhysicalOnboardingStage.CAMERA_RECEIPT: "RECORD_CAMERA_RECEIPT",
    PhysicalOnboardingStage.CAMERA_IDENTITY: "DISCOVER_CAMERA_IDENTITY",
    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS: "QUALIFY_CAMERA_CONFIGURATION",
    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS: "PROVE_CAMERA_FRESHNESS",
    PhysicalOnboardingStage.OPTICS_INTRINSICS: "QUALIFY_OPTICS_INTRINSICS",
    PhysicalOnboardingStage.STATIC_REGISTRATION: "REGISTER_STATIC_CAMERA",
    PhysicalOnboardingStage.ARM_IDENTITY: "DISCOVER_ARM_IDENTITY_POWER_OFF",
    PhysicalOnboardingStage.POWER_SAFETY: "REVIEW_POWER_SAFETY",
    PhysicalOnboardingStage.POWER_ON_OBSERVATION: "OBSERVE_FIRST_POWER_ON",
    PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION: (
        "QUALIFY_SINGLE_FEEDBACK_CONNECTION"
    ),
    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION: (
        "ACQUIRE_REFERENCE_FRAME_EVIDENCE"
    ),
    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE: (
        "ACQUIRE_NONCONTACT_ACCEPTANCE_EVIDENCE"
    ),
    PhysicalOnboardingStage.PHYSICAL_HANDOFF: "ASSEMBLE_DIAGNOSTIC_HANDOFF",
}
STAGE_ACTION_CODES: Mapping[PhysicalOnboardingStage, str] = MappingProxyType(
    _ACTION_CODES
)

_PREREQUISITES = {
    stage: (() if index == 0 else (STAGE_ORDER[index - 1],))
    for index, stage in enumerate(STAGE_ORDER)
}
STAGE_PREREQUISITES: Mapping[
    PhysicalOnboardingStage, tuple[PhysicalOnboardingStage, ...]
] = MappingProxyType(_PREREQUISITES)


def _compact_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingError(f"value is not JSON-safe: {exc}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise PhysicalOnboardingError("canonical JSON exceeds the resource limit")
    return payload


def _canonical_bytes(value: object) -> bytes:
    try:
        payload = (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingError(f"value is not canonical JSON: {exc}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise PhysicalOnboardingError("canonical JSON exceeds the resource limit")
    return payload


def _stable_hash(value: object) -> str:
    return hashlib.sha256(_compact_bytes(value)).hexdigest()


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PhysicalOnboardingError(f"nonfinite JSON number {value!r}")
    raise PhysicalOnboardingError("onboarding JSON must not contain floats")


def _reject_constant(value: str) -> None:
    raise PhysicalOnboardingError(f"nonfinite JSON constant {value!r}")


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise PhysicalOnboardingError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PhysicalOnboardingError(f"{label} must be a JSON object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PhysicalOnboardingError(f"{label} must be a JSON array")
    return value


def _text(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PhysicalOnboardingError(f"{label} must be non-empty trimmed text")
    if len(value) > maximum:
        raise PhysicalOnboardingError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise PhysicalOnboardingError(f"{label} contains a control character")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise PhysicalOnboardingError(f"{label} must be a bounded identifier")
    if value in {".", ".."}:
        raise PhysicalOnboardingError(f"{label} must not be a path segment")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PhysicalOnboardingError(f"{label} must be lowercase SHA-256")
    return value


def _positive_integer(value: object, label: str, *, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > maximum
    ):
        raise PhysicalOnboardingError(f"{label} must be a bounded positive integer")
    return value


def _nonnegative_integer(value: object, label: str, *, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > maximum
    ):
        raise PhysicalOnboardingError(
            f"{label} must be a bounded nonnegative integer"
        )
    return value


def _detail_code(value: object) -> str:
    if not isinstance(value, str) or _DETAIL_CODE.fullmatch(value) is None:
        raise PhysicalOnboardingError("detail_code must be a bounded uppercase code")
    return value


def _read_canonical_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise PhysicalOnboardingError(f"{label} must be a regular file")
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_JSON_BYTES + 1)
    except OSError as exc:
        raise PhysicalOnboardingError(f"cannot read {label}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise PhysicalOnboardingError(f"{label} exceeds the JSON resource limit")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingError(f"{label} is not strict JSON") from exc
    if not isinstance(document, dict):
        raise PhysicalOnboardingError(f"{label} must contain a JSON object")
    if _canonical_bytes(document) != payload:
        raise PhysicalOnboardingError(f"{label} is not canonical JSON")
    return document, payload


def _reject_symlink_chain(path: Path, label: str) -> None:
    selected = Path(os.path.abspath(path))
    existing: list[Path] = []
    cursor = selected
    while True:
        if os.path.lexists(cursor):
            existing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    for component in existing:
        if component.is_symlink():
            raise PhysicalOnboardingError(f"{label} contains a symlink")


def _safe_existing_directory(path: Path, label: str) -> Path:
    _reject_symlink_chain(path, label)
    selected = Path(path).resolve()
    if not selected.is_dir():
        raise PhysicalOnboardingError(f"{label} is not an existing directory")
    return selected


def _contained_child(root: Path, name: str, label: str) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise PhysicalOnboardingError(f"{label} is not a plain path segment")
    child = root / name
    if child.resolve(strict=False).parent != root:
        raise PhysicalOnboardingError(f"{label} escapes its root")
    return child


def _write_new(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise PhysicalOnboardingError(f"cannot create immutable file {path.name}") from exc


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if os.name == "nt":
            return
        raise PhysicalOnboardingError(
            f"cannot open directory for durability sync: {path.name}"
        ) from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if os.name != "nt":
            raise PhysicalOnboardingError(
                f"cannot durability-sync directory: {path.name}"
            ) from exc
    finally:
        os.close(descriptor)


_PLAN_CORE = {
    "ordered_stages": [stage.value for stage in STAGE_ORDER],
    "prerequisites": {
        stage.value: [item.value for item in STAGE_PREREQUISITES[stage]]
        for stage in STAGE_ORDER
    },
    "action_codes": {
        stage.value: STAGE_ACTION_CODES[stage] for stage in STAGE_ORDER
    },
    "diagnostic_only": True,
    "automatic_effect_replay_allowed": False,
    "motion_authorized": False,
    "contact_authorized": False,
    "physical_release_effect": "NONE",
}
STAGE_PLAN_SHA256 = _stable_hash(_PLAN_CORE)


@dataclass(frozen=True, slots=True)
class DiagnosticCapability:
    """Permanent authority ceiling of this module and all its snapshots."""

    scope: str = "DIAGNOSTIC_ONLY"
    diagnostic_observation_allowed: bool = True
    automatic_effect_replay_allowed: bool = False
    motion_authorized: bool = False
    contact_authorized: bool = False
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        if (
            self.scope != "DIAGNOSTIC_ONLY"
            or self.diagnostic_observation_allowed is not True
            or self.automatic_effect_replay_allowed is not False
            or self.motion_authorized is not False
            or self.contact_authorized is not False
            or self.physical_release_effect != "NONE"
        ):
            raise PhysicalOnboardingError(
                "physical onboarding capability cannot exceed diagnostic authority"
            )


DIAGNOSTIC_CAPABILITY = DiagnosticCapability()


@dataclass(frozen=True, slots=True)
class OnboardingSessionHeader:
    """Immutable identity and source binding for one commissioning attempt."""

    session_id: str
    cell_id: str
    created_at_ns: int
    source_binding_sha256: str
    header_sha256: str
    schema: str = SESSION_HEADER_SCHEMA

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "session_id": self.session_id,
            "cell_id": self.cell_id,
            "created_at_ns": self.created_at_ns,
            "source_binding_sha256": self.source_binding_sha256,
            "stage_plan_sha256": STAGE_PLAN_SHA256,
            "ordered_stages": [stage.value for stage in STAGE_ORDER],
            "diagnostic_only": True,
            "automatic_effect_replay_allowed": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "header_sha256": self.header_sha256}

    @classmethod
    def build(
        cls,
        *,
        session_id: str,
        cell_id: str,
        created_at_ns: int,
        source_binding_sha256: str,
    ) -> "OnboardingSessionHeader":
        _identifier(session_id, "session_id")
        _identifier(cell_id, "cell_id")
        _positive_integer(created_at_ns, "created_at_ns", maximum=2**63 - 1)
        _digest(source_binding_sha256, "source_binding_sha256")
        provisional = cls(
            session_id=session_id,
            cell_id=cell_id,
            created_at_ns=created_at_ns,
            source_binding_sha256=source_binding_sha256,
            header_sha256=_ZERO_DIGEST,
        )
        return cls(
            session_id=session_id,
            cell_id=cell_id,
            created_at_ns=created_at_ns,
            source_binding_sha256=source_binding_sha256,
            header_sha256=_stable_hash(provisional.core_dict()),
        )


_HEADER_FIELDS = frozenset(
    {
        "schema",
        "session_id",
        "cell_id",
        "created_at_ns",
        "source_binding_sha256",
        "stage_plan_sha256",
        "ordered_stages",
        "diagnostic_only",
        "automatic_effect_replay_allowed",
        "motion_authorized",
        "contact_authorized",
        "physical_release_effect",
        "header_sha256",
    }
)


def _parse_header(value: object) -> OnboardingSessionHeader:
    document = _mapping(value, "session header")
    _exact_fields(document, _HEADER_FIELDS, "session header")
    if document["schema"] != SESSION_HEADER_SCHEMA:
        raise PhysicalOnboardingError("unsupported session-header schema")
    if document["stage_plan_sha256"] != STAGE_PLAN_SHA256:
        raise PhysicalOnboardingError("session header stage plan has drifted")
    if document["ordered_stages"] != [stage.value for stage in STAGE_ORDER]:
        raise PhysicalOnboardingError("session header stage order is invalid")
    if (
        document["diagnostic_only"] is not True
        or document["automatic_effect_replay_allowed"] is not False
        or document["motion_authorized"] is not False
        or document["contact_authorized"] is not False
        or document["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingError("session header exceeds diagnostic authority")
    header = OnboardingSessionHeader(
        schema=document["schema"],
        session_id=_identifier(document["session_id"], "session_id"),
        cell_id=_identifier(document["cell_id"], "cell_id"),
        created_at_ns=_positive_integer(
            document["created_at_ns"], "created_at_ns", maximum=2**63 - 1
        ),
        source_binding_sha256=_digest(
            document["source_binding_sha256"], "source_binding_sha256"
        ),
        header_sha256=_digest(document["header_sha256"], "header_sha256"),
    )
    if header.header_sha256 != _stable_hash(header.core_dict()):
        raise PhysicalOnboardingError("session header hash mismatch")
    return header


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Content-bound reference safe to place in a stage event."""

    evidence_id: str
    stage: PhysicalOnboardingStage
    package_sha256: str
    manifest_sha256: str
    payload_sha256: str
    payload_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "stage": self.stage.value,
            "package_sha256": self.package_sha256,
            "manifest_sha256": self.manifest_sha256,
            "payload_sha256": self.payload_sha256,
            "payload_bytes": self.payload_bytes,
        }


_EVIDENCE_REFERENCE_FIELDS = frozenset(
    {
        "evidence_id",
        "stage",
        "package_sha256",
        "manifest_sha256",
        "payload_sha256",
        "payload_bytes",
    }
)


def _parse_evidence_reference(value: object) -> EvidenceReference:
    document = _mapping(value, "event evidence reference")
    _exact_fields(document, _EVIDENCE_REFERENCE_FIELDS, "event evidence reference")
    try:
        stage = PhysicalOnboardingStage(document["stage"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingError("evidence reference stage is invalid") from exc
    package_sha256 = _digest(document["package_sha256"], "package_sha256")
    evidence_id = document["evidence_id"]
    if evidence_id != f"evidence-{package_sha256}":
        raise PhysicalOnboardingError("evidence_id is not content-addressed")
    return EvidenceReference(
        evidence_id=evidence_id,
        stage=stage,
        package_sha256=package_sha256,
        manifest_sha256=_digest(document["manifest_sha256"], "manifest_sha256"),
        payload_sha256=_digest(document["payload_sha256"], "payload_sha256"),
        payload_bytes=_positive_integer(
            document["payload_bytes"],
            "payload_bytes",
            maximum=MAX_EVIDENCE_BYTES,
        ),
    )


_EVIDENCE_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "evidence_id",
        "package_sha256",
        "session_id",
        "session_header_sha256",
        "stage",
        "label",
        "media_type",
        "captured_at_ns",
        "payload_filename",
        "payload_sha256",
        "payload_bytes",
        "manifest_written_last",
        "diagnostic_only",
        "automatic_effect_replay_allowed",
        "motion_authorized",
        "contact_authorized",
        "physical_release_effect",
    }
)


def _evidence_core(
    *,
    header: OnboardingSessionHeader,
    stage: PhysicalOnboardingStage,
    label: str,
    media_type: str,
    captured_at_ns: int,
    payload_sha256: str,
    payload_bytes: int,
) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_MANIFEST_SCHEMA,
        "session_id": header.session_id,
        "session_header_sha256": header.header_sha256,
        "stage": stage.value,
        "label": label,
        "media_type": media_type,
        "captured_at_ns": captured_at_ns,
        "payload_filename": "payload.bin",
        "payload_sha256": payload_sha256,
        "payload_bytes": payload_bytes,
        "manifest_written_last": True,
        "diagnostic_only": True,
        "automatic_effect_replay_allowed": False,
        "motion_authorized": False,
        "contact_authorized": False,
        "physical_release_effect": "NONE",
    }


def _hash_file(path: Path, *, maximum: int) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise PhysicalOnboardingError("evidence payload must be a regular file")
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise PhysicalOnboardingError(
                        "evidence payload exceeds the resource limit"
                    )
                digest.update(chunk)
    except OSError as exc:
        raise PhysicalOnboardingError("cannot read evidence payload") from exc
    if total == 0:
        raise PhysicalOnboardingError("evidence payload must not be empty")
    return digest.hexdigest(), total


def _verify_evidence_directory(
    directory: Path, header: OnboardingSessionHeader
) -> EvidenceReference:
    if directory.is_symlink() or not directory.is_dir():
        raise PhysicalOnboardingError("evidence package must be a real directory")
    match = _EVIDENCE_DIRECTORY.fullmatch(directory.name)
    if match is None:
        raise PhysicalOnboardingError("evidence package name is invalid")
    try:
        entries = list(os.scandir(directory))
    except OSError as exc:
        raise PhysicalOnboardingError("cannot enumerate evidence package") from exc
    if {entry.name for entry in entries} != {"payload.bin", "manifest.json"}:
        raise PhysicalOnboardingError("evidence package file set is not exact")
    if any(entry.is_symlink() or not entry.is_file(follow_symlinks=False) for entry in entries):
        raise PhysicalOnboardingError("evidence package contains a non-file or symlink")

    manifest, manifest_payload = _read_canonical_json(
        directory / "manifest.json", "evidence manifest"
    )
    _exact_fields(manifest, _EVIDENCE_MANIFEST_FIELDS, "evidence manifest")
    if manifest["schema"] != EVIDENCE_MANIFEST_SCHEMA:
        raise PhysicalOnboardingError("unsupported evidence-manifest schema")
    if (
        manifest["manifest_written_last"] is not True
        or manifest["diagnostic_only"] is not True
        or manifest["automatic_effect_replay_allowed"] is not False
        or manifest["motion_authorized"] is not False
        or manifest["contact_authorized"] is not False
        or manifest["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingError("evidence manifest exceeds diagnostic authority")
    if (
        manifest["session_id"] != header.session_id
        or manifest["session_header_sha256"] != header.header_sha256
    ):
        raise PhysicalOnboardingError("evidence belongs to another session")
    if manifest["payload_filename"] != "payload.bin":
        raise PhysicalOnboardingError("evidence payload filename is invalid")
    try:
        stage = PhysicalOnboardingStage(manifest["stage"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingError("evidence stage is invalid") from exc
    _text(manifest["label"], "evidence label", maximum=128)
    media_type = _text(manifest["media_type"], "evidence media_type", maximum=129)
    if _MEDIA_TYPE.fullmatch(media_type) is None:
        raise PhysicalOnboardingError("evidence media_type is invalid")
    _positive_integer(
        manifest["captured_at_ns"], "captured_at_ns", maximum=2**63 - 1
    )
    expected_payload_hash = _digest(
        manifest["payload_sha256"], "evidence payload_sha256"
    )
    expected_payload_bytes = _positive_integer(
        manifest["payload_bytes"],
        "evidence payload_bytes",
        maximum=MAX_EVIDENCE_BYTES,
    )
    payload_hash, payload_bytes = _hash_file(
        directory / "payload.bin", maximum=MAX_EVIDENCE_BYTES
    )
    if (
        payload_hash != expected_payload_hash
        or payload_bytes != expected_payload_bytes
    ):
        raise PhysicalOnboardingError("evidence payload hash or size mismatch")
    package_sha256 = _digest(manifest["package_sha256"], "package_sha256")
    core = dict(manifest)
    del core["evidence_id"]
    del core["package_sha256"]
    if _stable_hash(core) != package_sha256:
        raise PhysicalOnboardingError("evidence package hash mismatch")
    evidence_id = manifest["evidence_id"]
    if (
        evidence_id != f"evidence-{package_sha256}"
        or directory.name != evidence_id
        or match.group(1) != package_sha256
    ):
        raise PhysicalOnboardingError("evidence directory is not content-addressed")
    return EvidenceReference(
        evidence_id=evidence_id,
        stage=stage,
        package_sha256=package_sha256,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        payload_sha256=payload_hash,
        payload_bytes=payload_bytes,
    )


@dataclass(frozen=True, slots=True)
class OnboardingJournalEvent:
    """One immutable, hash-chained onboarding state transition."""

    session_id: str
    session_header_sha256: str
    sequence: int
    stage: PhysicalOnboardingStage
    previous_state: StageState
    state: StageState
    occurred_at_ns: int
    previous_event_sha256: str
    evidence: tuple[EvidenceReference, ...]
    detail_code: str
    event_sha256: str
    schema: str = SESSION_EVENT_SCHEMA

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "session_id": self.session_id,
            "session_header_sha256": self.session_header_sha256,
            "sequence": self.sequence,
            "stage": self.stage.value,
            "previous_state": self.previous_state.value,
            "state": self.state.value,
            "occurred_at_ns": self.occurred_at_ns,
            "previous_event_sha256": self.previous_event_sha256,
            "evidence": [item.to_dict() for item in self.evidence],
            "detail_code": self.detail_code,
            "diagnostic_only": True,
            "automatic_effect_replay_allowed": False,
            "motion_commands_authorized": 0,
            "contact_commands_authorized": 0,
            "physical_release_effect": "NONE",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "event_sha256": self.event_sha256}

    @classmethod
    def build(
        cls,
        *,
        header: OnboardingSessionHeader,
        sequence: int,
        stage: PhysicalOnboardingStage,
        previous_state: StageState,
        state: StageState,
        occurred_at_ns: int,
        previous_event_sha256: str,
        evidence: tuple[EvidenceReference, ...],
        detail_code: str,
    ) -> "OnboardingJournalEvent":
        provisional = cls(
            session_id=header.session_id,
            session_header_sha256=header.header_sha256,
            sequence=sequence,
            stage=stage,
            previous_state=previous_state,
            state=state,
            occurred_at_ns=occurred_at_ns,
            previous_event_sha256=previous_event_sha256,
            evidence=evidence,
            detail_code=detail_code,
            event_sha256=_ZERO_DIGEST,
        )
        return cls(
            session_id=provisional.session_id,
            session_header_sha256=provisional.session_header_sha256,
            sequence=provisional.sequence,
            stage=provisional.stage,
            previous_state=provisional.previous_state,
            state=provisional.state,
            occurred_at_ns=provisional.occurred_at_ns,
            previous_event_sha256=provisional.previous_event_sha256,
            evidence=provisional.evidence,
            detail_code=provisional.detail_code,
            event_sha256=_stable_hash(provisional.core_dict()),
        )


_EVENT_FIELDS = frozenset(
    {
        "schema",
        "session_id",
        "session_header_sha256",
        "sequence",
        "stage",
        "previous_state",
        "state",
        "occurred_at_ns",
        "previous_event_sha256",
        "evidence",
        "detail_code",
        "diagnostic_only",
        "automatic_effect_replay_allowed",
        "motion_commands_authorized",
        "contact_commands_authorized",
        "physical_release_effect",
        "event_sha256",
    }
)


def _parse_event(value: object) -> OnboardingJournalEvent:
    document = _mapping(value, "journal event")
    _exact_fields(document, _EVENT_FIELDS, "journal event")
    if document["schema"] != SESSION_EVENT_SCHEMA:
        raise PhysicalOnboardingError("unsupported journal-event schema")
    if (
        document["diagnostic_only"] is not True
        or document["automatic_effect_replay_allowed"] is not False
        or document["motion_commands_authorized"] != 0
        or isinstance(document["motion_commands_authorized"], bool)
        or document["contact_commands_authorized"] != 0
        or isinstance(document["contact_commands_authorized"], bool)
        or document["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingError("journal event exceeds diagnostic authority")
    try:
        stage = PhysicalOnboardingStage(document["stage"])
        previous_state = StageState(document["previous_state"])
        state = StageState(document["state"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingError("journal event stage or state is invalid") from exc
    raw_evidence = _array(document["evidence"], "journal event evidence")
    if len(raw_evidence) > MAX_EVENT_EVIDENCE_ITEMS:
        raise PhysicalOnboardingError("journal event references too much evidence")
    evidence = tuple(_parse_evidence_reference(item) for item in raw_evidence)
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise PhysicalOnboardingError("journal event repeats an evidence reference")
    event = OnboardingJournalEvent(
        schema=document["schema"],
        session_id=_identifier(document["session_id"], "event session_id"),
        session_header_sha256=_digest(
            document["session_header_sha256"], "event session_header_sha256"
        ),
        sequence=_nonnegative_integer(
            document["sequence"], "event sequence", maximum=MAX_JOURNAL_EVENTS - 1
        ),
        stage=stage,
        previous_state=previous_state,
        state=state,
        occurred_at_ns=_positive_integer(
            document["occurred_at_ns"], "event occurred_at_ns", maximum=2**63 - 1
        ),
        previous_event_sha256=_digest(
            document["previous_event_sha256"], "previous_event_sha256"
        ),
        evidence=evidence,
        detail_code=_detail_code(document["detail_code"]),
        event_sha256=_digest(document["event_sha256"], "event_sha256"),
    )
    if event.event_sha256 != _stable_hash(event.core_dict()):
        raise PhysicalOnboardingError("journal event hash mismatch")
    return event


_HIGH_WATER_FIELDS = frozenset(
    {
        "schema",
        "session_id",
        "session_header_sha256",
        "event_count",
        "committed_sequence",
        "committed_stage",
        "committed_state",
        "committed_event_sha256",
        "committed_event_time_ns",
        "side_effect_uncertain_ever_committed",
        "uncertain_event_sequence",
        "uncertain_event_sha256",
        "diagnostic_only",
        "automatic_effect_replay_allowed",
        "motion_commands_authorized",
        "contact_commands_authorized",
        "physical_release_effect",
        "high_water_sha256",
    }
)


def _high_water_document(
    header: OnboardingSessionHeader,
    events: Sequence[OnboardingJournalEvent],
) -> dict[str, Any]:
    if len(events) > MAX_JOURNAL_EVENTS:
        raise PhysicalOnboardingError("cannot anchor an oversized journal")
    tail = None if not events else events[-1]
    uncertain = next(
        (
            event
            for event in events
            if event.state is StageState.SIDE_EFFECT_UNCERTAIN
        ),
        None,
    )
    core: dict[str, Any] = {
        "schema": SESSION_HIGH_WATER_SCHEMA,
        "session_id": header.session_id,
        "session_header_sha256": header.header_sha256,
        "event_count": len(events),
        "committed_sequence": None if tail is None else tail.sequence,
        "committed_stage": None if tail is None else tail.stage.value,
        "committed_state": None if tail is None else tail.state.value,
        "committed_event_sha256": (
            _ZERO_DIGEST if tail is None else tail.event_sha256
        ),
        "committed_event_time_ns": None if tail is None else tail.occurred_at_ns,
        "side_effect_uncertain_ever_committed": uncertain is not None,
        "uncertain_event_sequence": None if uncertain is None else uncertain.sequence,
        "uncertain_event_sha256": (
            None if uncertain is None else uncertain.event_sha256
        ),
        "diagnostic_only": True,
        "automatic_effect_replay_allowed": False,
        "motion_commands_authorized": 0,
        "contact_commands_authorized": 0,
        "physical_release_effect": "NONE",
    }
    return {**core, "high_water_sha256": _stable_hash(core)}


def _parse_high_water(value: object) -> dict[str, Any]:
    document = _mapping(value, "journal high-water record")
    _exact_fields(document, _HIGH_WATER_FIELDS, "journal high-water record")
    if document["schema"] != SESSION_HIGH_WATER_SCHEMA:
        raise PhysicalOnboardingError("unsupported journal high-water schema")
    if (
        document["diagnostic_only"] is not True
        or document["automatic_effect_replay_allowed"] is not False
        or document["motion_commands_authorized"] != 0
        or isinstance(document["motion_commands_authorized"], bool)
        or document["contact_commands_authorized"] != 0
        or isinstance(document["contact_commands_authorized"], bool)
        or document["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingError(
            "journal high-water record exceeds diagnostic authority"
        )
    _identifier(document["session_id"], "high-water session_id")
    _digest(
        document["session_header_sha256"], "high-water session_header_sha256"
    )
    event_count = _nonnegative_integer(
        document["event_count"], "high-water event_count", maximum=MAX_JOURNAL_EVENTS
    )
    committed_hash = _digest(
        document["committed_event_sha256"], "high-water committed_event_sha256"
    )
    if event_count == 0:
        if (
            document["committed_sequence"] is not None
            or document["committed_stage"] is not None
            or document["committed_state"] is not None
            or committed_hash != _ZERO_DIGEST
            or document["committed_event_time_ns"] is not None
        ):
            raise PhysicalOnboardingError("empty journal high-water tail is inconsistent")
    else:
        sequence = _nonnegative_integer(
            document["committed_sequence"],
            "high-water committed_sequence",
            maximum=MAX_JOURNAL_EVENTS - 1,
        )
        if sequence != event_count - 1:
            raise PhysicalOnboardingError("journal high-water sequence is inconsistent")
        try:
            PhysicalOnboardingStage(document["committed_stage"])
            StageState(document["committed_state"])
        except (TypeError, ValueError) as exc:
            raise PhysicalOnboardingError(
                "journal high-water stage or state is invalid"
            ) from exc
        if committed_hash == _ZERO_DIGEST:
            raise PhysicalOnboardingError("nonempty journal has a zero tail hash")
        _positive_integer(
            document["committed_event_time_ns"],
            "high-water committed_event_time_ns",
            maximum=2**63 - 1,
        )
    uncertainty = document["side_effect_uncertain_ever_committed"]
    if not isinstance(uncertainty, bool):
        raise PhysicalOnboardingError(
            "side_effect_uncertain_ever_committed must be boolean"
        )
    if uncertainty:
        _nonnegative_integer(
            document["uncertain_event_sequence"],
            "uncertain_event_sequence",
            maximum=MAX_JOURNAL_EVENTS - 1,
        )
        _digest(document["uncertain_event_sha256"], "uncertain_event_sha256")
    elif (
        document["uncertain_event_sequence"] is not None
        or document["uncertain_event_sha256"] is not None
    ):
        raise PhysicalOnboardingError(
            "journal high-water uncertainty fields are inconsistent"
        )
    high_water_sha256 = _digest(
        document["high_water_sha256"], "high_water_sha256"
    )
    core = dict(document)
    del core["high_water_sha256"]
    if _stable_hash(core) != high_water_sha256:
        raise PhysicalOnboardingError("journal high-water hash mismatch")
    return dict(document)


def _validate_high_water(
    high_water: Mapping[str, Any],
    *,
    header: OnboardingSessionHeader,
    events: Sequence[OnboardingJournalEvent],
) -> None:
    if (
        high_water["session_id"] != header.session_id
        or high_water["session_header_sha256"] != header.header_sha256
    ):
        raise PhysicalOnboardingError("journal high-water session binding mismatch")
    if high_water["event_count"] != len(events):
        raise PhysicalOnboardingError(
            "journal event suffix differs from its durable high-water record"
        )
    tail = None if not events else events[-1]
    if tail is None:
        if high_water != _parse_high_water(_high_water_document(header, ())):
            raise PhysicalOnboardingError("empty journal high-water record has drifted")
    elif (
        high_water["committed_sequence"] != tail.sequence
        or high_water["committed_stage"] != tail.stage.value
        or high_water["committed_state"] != tail.state.value
        or high_water["committed_event_sha256"] != tail.event_sha256
        or high_water["committed_event_time_ns"] != tail.occurred_at_ns
    ):
        raise PhysicalOnboardingError("journal tail differs from high-water record")
    uncertain_events = tuple(
        event
        for event in events
        if event.state is StageState.SIDE_EFFECT_UNCERTAIN
    )
    if len(uncertain_events) > 1:
        raise PhysicalOnboardingError("journal contains multiple uncertainty events")
    uncertain = None if not uncertain_events else uncertain_events[0]
    if high_water["side_effect_uncertain_ever_committed"] is not (
        uncertain is not None
    ):
        raise PhysicalOnboardingError("journal uncertainty high-water bit differs")
    if uncertain is not None and (
        high_water["uncertain_event_sequence"] != uncertain.sequence
        or high_water["uncertain_event_sha256"] != uncertain.event_sha256
    ):
        raise PhysicalOnboardingError(
            "journal uncertainty event differs from high-water record"
        )


@dataclass(frozen=True, slots=True)
class StageSnapshot:
    stage: PhysicalOnboardingStage
    state: StageState
    last_event_sequence: int | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NextOnboardingAction:
    """The sole safe workflow action exposed for the current snapshot."""

    code: str
    stage: PhysicalOnboardingStage | None
    stage_state: StageState | None
    operator_required: bool
    diagnostic_only: bool = True
    automatic_effect_replay_allowed: bool = False
    motion_authorized: bool = False
    contact_authorized: bool = False
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        _text(self.code, "next-action code", maximum=192)
        if self.stage is None:
            if self.stage_state is not None:
                raise PhysicalOnboardingError(
                    "a stage-less next action cannot claim stage state"
                )
        elif not isinstance(self.stage, PhysicalOnboardingStage) or not isinstance(
            self.stage_state, StageState
        ):
            raise PhysicalOnboardingError(
                "next-action stage and state must be typed together"
            )
        if not isinstance(self.operator_required, bool):
            raise PhysicalOnboardingError("operator_required must be boolean")
        if (
            self.diagnostic_only is not True
            or self.automatic_effect_replay_allowed is not False
            or self.motion_authorized is not False
            or self.contact_authorized is not False
            or self.physical_release_effect != "NONE"
        ):
            raise PhysicalOnboardingError(
                "next action cannot exceed diagnostic authority"
            )


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingSnapshot:
    """Immutable verified view derived solely from header, evidence, and events."""

    header: OnboardingSessionHeader
    stages: tuple[StageSnapshot, ...]
    events: tuple[OnboardingJournalEvent, ...]
    evidence: tuple[EvidenceReference, ...]
    high_water_sha256: str
    next_action: NextOnboardingAction
    capability: DiagnosticCapability = DIAGNOSTIC_CAPABILITY

    def state_for(self, stage: PhysicalOnboardingStage) -> StageState:
        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        return self.stages[STAGE_ORDER.index(stage)].state

    @property
    def diagnostic_complete(self) -> bool:
        return (
            self.state_for(PhysicalOnboardingStage.PHYSICAL_HANDOFF)
            is StageState.COMPLETE_DIAGNOSTIC
        )


_ALLOWED_TRANSITIONS: Mapping[StageState, frozenset[StageState]] = MappingProxyType(
    {
        StageState.PENDING: frozenset(
            {StageState.WAITING_OPERATOR, StageState.ACQUIRING, StageState.BLOCKED}
        ),
        StageState.WAITING_OPERATOR: frozenset(
            {
                StageState.ACQUIRING,
                StageState.PASS,
                StageState.BLOCKED,
                StageState.COMPLETE_DIAGNOSTIC,
            }
        ),
        StageState.ACQUIRING: frozenset(
            {
                StageState.PASS,
                StageState.BLOCKED,
                StageState.SIDE_EFFECT_UNCERTAIN,
                StageState.COMPLETE_DIAGNOSTIC,
            }
        ),
        StageState.PASS: frozenset({StageState.INVALIDATED}),
        StageState.BLOCKED: frozenset(
            {StageState.WAITING_OPERATOR, StageState.ACQUIRING}
        ),
        StageState.INVALIDATED: frozenset(
            {StageState.WAITING_OPERATOR, StageState.ACQUIRING, StageState.BLOCKED}
        ),
        StageState.SIDE_EFFECT_UNCERTAIN: frozenset(),
        StageState.COMPLETE_DIAGNOSTIC: frozenset({StageState.INVALIDATED}),
    }
)


def _first_incomplete(states: Sequence[StageState]) -> PhysicalOnboardingStage | None:
    for stage, state in zip(STAGE_ORDER, states):
        if state not in {StageState.PASS, StageState.COMPLETE_DIAGNOSTIC}:
            return stage
    return None


def _validate_transition(
    states: Sequence[StageState],
    *,
    stage: PhysicalOnboardingStage,
    previous_state: StageState,
    state: StageState,
    evidence: Sequence[EvidenceReference],
) -> None:
    index = STAGE_ORDER.index(stage)
    if states[index] is not previous_state:
        raise PhysicalOnboardingError("event previous_state differs from derived state")
    if state not in _ALLOWED_TRANSITIONS[previous_state]:
        raise PhysicalOnboardingError(
            f"invalid onboarding transition {previous_state.value}->{state.value}"
        )
    if state is StageState.INVALIDATED:
        if previous_state not in {StageState.PASS, StageState.COMPLETE_DIAGNOSTIC}:
            raise PhysicalOnboardingError("only completed evidence can be invalidated")
    else:
        active = _first_incomplete(states)
        if active is not stage:
            raise PhysicalOnboardingError(
                f"stage {stage.value} cannot run before {active.value if active else 'completion'}"
            )
        for prerequisite in STAGE_PREREQUISITES[stage]:
            prerequisite_state = states[STAGE_ORDER.index(prerequisite)]
            if prerequisite_state not in {
                StageState.PASS,
                StageState.COMPLETE_DIAGNOSTIC,
            }:
                raise PhysicalOnboardingError(
                    f"stage prerequisite is not satisfied: {prerequisite.value}"
                )
    if state is StageState.COMPLETE_DIAGNOSTIC:
        if stage is not PhysicalOnboardingStage.PHYSICAL_HANDOFF:
            raise PhysicalOnboardingError(
                "COMPLETE_DIAGNOSTIC is reserved for physical_handoff"
            )
    elif stage is PhysicalOnboardingStage.PHYSICAL_HANDOFF and state is StageState.PASS:
        raise PhysicalOnboardingError(
            "physical_handoff must end as COMPLETE_DIAGNOSTIC, not PASS"
        )
    if state in {StageState.PASS, StageState.COMPLETE_DIAGNOSTIC} and not evidence:
        raise PhysicalOnboardingError(f"{state.value} requires retained evidence")
    if any(item.stage is not stage for item in evidence):
        raise PhysicalOnboardingError("event evidence belongs to another stage")


def _apply_transition(
    states: list[StageState], event: OnboardingJournalEvent
) -> None:
    _validate_transition(
        states,
        stage=event.stage,
        previous_state=event.previous_state,
        state=event.state,
        evidence=event.evidence,
    )
    index = STAGE_ORDER.index(event.stage)
    if event.state is StageState.INVALIDATED:
        for downstream in range(index, len(states)):
            # Invalidation cannot erase uncertainty.  A stage whose diagnostic
            # operation may have produced an external effect remains terminal
            # even when an earlier dependency also becomes stale.
            if states[downstream] is not StageState.SIDE_EFFECT_UNCERTAIN:
                states[downstream] = StageState.INVALIDATED
    else:
        states[index] = event.state


def _derive_next_action(states: Sequence[StageState]) -> NextOnboardingAction:
    stage = _first_incomplete(states)
    if stage is None:
        return NextOnboardingAction(
            code="NO_ACTION_DIAGNOSTIC_COMPLETE",
            stage=None,
            stage_state=None,
            operator_required=False,
        )
    state = states[STAGE_ORDER.index(stage)]
    base = STAGE_ACTION_CODES[stage]
    if state is StageState.PENDING:
        code = f"START_{base}"
        operator_required = False
    elif state is StageState.WAITING_OPERATOR:
        code = f"AWAIT_OPERATOR_{base}"
        operator_required = True
    elif state is StageState.ACQUIRING:
        # This is the restart rule: resumption exposes reconciliation, never a
        # second invocation of the operation that may already have happened.
        code = f"RECONCILE_IN_FLIGHT_{base}"
        operator_required = True
    elif state is StageState.BLOCKED:
        code = f"RESOLVE_BLOCK_{base}"
        operator_required = True
    elif state is StageState.INVALIDATED:
        code = f"REACQUIRE_INVALIDATED_{base}"
        operator_required = True
    elif state is StageState.SIDE_EFFECT_UNCERTAIN:
        code = "MANUAL_REVIEW_SIDE_EFFECT_UNCERTAIN"
        operator_required = True
    else:  # pragma: no cover - _first_incomplete excludes completed states
        raise PhysicalOnboardingError("cannot derive a next action")
    return NextOnboardingAction(
        code=code,
        stage=stage,
        stage_state=state,
        operator_required=operator_required,
    )


def _enumerate_evidence(
    evidence_root: Path, header: OnboardingSessionHeader
) -> dict[str, EvidenceReference]:
    if evidence_root.is_symlink() or not evidence_root.is_dir():
        raise PhysicalOnboardingError("evidence root must be a real directory")
    try:
        entries = list(os.scandir(evidence_root))
    except OSError as exc:
        raise PhysicalOnboardingError("cannot enumerate evidence root") from exc
    if len(entries) > MAX_EVIDENCE_ITEMS:
        raise PhysicalOnboardingError("session contains too many evidence packages")
    verified: dict[str, EvidenceReference] = {}
    total_bytes = 0
    for entry in entries:
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            raise PhysicalOnboardingError("evidence root contains an unexpected entry")
        reference = _verify_evidence_directory(Path(entry.path), header)
        if reference.evidence_id in verified:
            raise PhysicalOnboardingError("session contains duplicate evidence identity")
        total_bytes += reference.payload_bytes
        if total_bytes > MAX_TOTAL_EVIDENCE_BYTES:
            raise PhysicalOnboardingError("session evidence exceeds the total size limit")
        verified[reference.evidence_id] = reference
    return verified


def _enumerate_events(
    journal_root: Path,
    *,
    header: OnboardingSessionHeader,
    evidence: Mapping[str, EvidenceReference],
) -> tuple[tuple[OnboardingJournalEvent, ...], str]:
    if journal_root.is_symlink() or not journal_root.is_dir():
        raise PhysicalOnboardingError("journal root must be a real directory")
    try:
        entries = list(os.scandir(journal_root))
    except OSError as exc:
        raise PhysicalOnboardingError("cannot enumerate journal root") from exc
    if len(entries) > MAX_JOURNAL_EVENTS + 1:
        raise PhysicalOnboardingError("session journal exceeds the event limit")
    paths: list[tuple[int, Path]] = []
    high_water_seen = False
    for entry in entries:
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            raise PhysicalOnboardingError("journal contains an unexpected entry")
        if entry.name == _HIGH_WATER_FILENAME:
            if high_water_seen:
                raise PhysicalOnboardingError(
                    "journal contains duplicate high-water records"
                )
            high_water_seen = True
            continue
        match = _EVENT_FILENAME.fullmatch(entry.name)
        if match is None:
            raise PhysicalOnboardingError("journal contains an unknown filename")
        paths.append((int(match.group(1)), Path(entry.path)))
    if not high_water_seen:
        raise PhysicalOnboardingError("journal high-water record is missing")
    paths.sort(key=lambda item: item[0])
    if [sequence for sequence, _ in paths] != list(range(len(paths))):
        raise PhysicalOnboardingError("journal sequence is not contiguous")

    states = [StageState.PENDING for _ in STAGE_ORDER]
    previous_hash = _ZERO_DIGEST
    previous_time = header.created_at_ns - 1
    parsed: list[OnboardingJournalEvent] = []
    for sequence, path in paths:
        document, _ = _read_canonical_json(path, f"journal event {sequence}")
        event = _parse_event(document)
        if event.sequence != sequence:
            raise PhysicalOnboardingError("event filename and sequence disagree")
        if (
            event.session_id != header.session_id
            or event.session_header_sha256 != header.header_sha256
        ):
            raise PhysicalOnboardingError("journal event belongs to another session")
        if event.previous_event_sha256 != previous_hash:
            raise PhysicalOnboardingError("journal event hash chain is broken")
        if event.occurred_at_ns <= previous_time:
            raise PhysicalOnboardingError("journal event time is not strictly increasing")
        for reference in event.evidence:
            if evidence.get(reference.evidence_id) != reference:
                raise PhysicalOnboardingError(
                    "journal event evidence does not match retained evidence"
                )
        _apply_transition(states, event)
        parsed.append(event)
        previous_hash = event.event_sha256
        previous_time = event.occurred_at_ns
    immutable_events = tuple(parsed)
    high_water_document, _ = _read_canonical_json(
        journal_root / _HIGH_WATER_FILENAME, "journal high-water record"
    )
    high_water = _parse_high_water(high_water_document)
    _validate_high_water(high_water, header=header, events=immutable_events)
    return immutable_events, high_water["high_water_sha256"]


def load_physical_onboarding_session(directory: Path) -> PhysicalOnboardingSnapshot:
    """Verify a complete session without invoking or replaying any effect."""

    root = _safe_existing_directory(directory, "onboarding session")
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise PhysicalOnboardingError("cannot enumerate onboarding session") from exc
    if {entry.name for entry in entries} != {"header.json", "journal", "evidence"}:
        raise PhysicalOnboardingError("onboarding session entry set is not exact")
    by_name = {entry.name: entry for entry in entries}
    if (
        by_name["header.json"].is_symlink()
        or not by_name["header.json"].is_file(follow_symlinks=False)
        or by_name["journal"].is_symlink()
        or not by_name["journal"].is_dir(follow_symlinks=False)
        or by_name["evidence"].is_symlink()
        or not by_name["evidence"].is_dir(follow_symlinks=False)
    ):
        raise PhysicalOnboardingError("onboarding session contains a symlink or wrong type")

    header_document, _ = _read_canonical_json(root / "header.json", "session header")
    header = _parse_header(header_document)
    if root.name != f"onboarding-{header.session_id}":
        raise PhysicalOnboardingError("session directory does not bind session_id")
    evidence_by_id = _enumerate_evidence(root / "evidence", header)
    events, high_water_sha256 = _enumerate_events(
        root / "journal", header=header, evidence=evidence_by_id
    )

    states = [StageState.PENDING for _ in STAGE_ORDER]
    latest_sequences: list[int | None] = [None for _ in STAGE_ORDER]
    evidence_ids: list[list[str]] = [[] for _ in STAGE_ORDER]
    for event in events:
        _apply_transition(states, event)
        index = STAGE_ORDER.index(event.stage)
        latest_sequences[index] = event.sequence
        evidence_ids[index].extend(item.evidence_id for item in event.evidence)
        if event.state is StageState.INVALIDATED:
            for downstream in range(index, len(STAGE_ORDER)):
                if states[downstream] is not StageState.SIDE_EFFECT_UNCERTAIN:
                    latest_sequences[downstream] = event.sequence

    stage_snapshots = tuple(
        StageSnapshot(
            stage=stage,
            state=states[index],
            last_event_sequence=latest_sequences[index],
            evidence_ids=tuple(evidence_ids[index]),
        )
        for index, stage in enumerate(STAGE_ORDER)
    )
    return PhysicalOnboardingSnapshot(
        header=header,
        stages=stage_snapshots,
        events=events,
        evidence=tuple(evidence_by_id[key] for key in sorted(evidence_by_id)),
        high_water_sha256=high_water_sha256,
        next_action=_derive_next_action(states),
    )


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingSession:
    """Append-only session handle with no hardware or authority methods."""

    directory: Path

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        session_id: str,
        cell_id: str,
        source_binding_sha256: str,
        created_at_ns: int,
    ) -> "PhysicalOnboardingSession":
        session_root = _safe_existing_directory(root, "onboarding root")
        header = OnboardingSessionHeader.build(
            session_id=session_id,
            cell_id=cell_id,
            source_binding_sha256=source_binding_sha256,
            created_at_ns=created_at_ns,
        )
        destination = _contained_child(
            session_root, f"onboarding-{header.session_id}", "session directory"
        )
        if os.path.lexists(destination):
            raise PhysicalOnboardingError("immutable onboarding session already exists")
        temporary = _contained_child(
            session_root,
            f".partial-onboarding-{header.session_id}-{secrets.token_hex(8)}",
            "partial session directory",
        )
        try:
            temporary.mkdir(exist_ok=False)
            (temporary / "journal").mkdir(exist_ok=False)
            (temporary / "evidence").mkdir(exist_ok=False)
            _write_new(temporary / "header.json", _canonical_bytes(header.to_dict()))
            _write_new(
                temporary / "journal" / _HIGH_WATER_FILENAME,
                _canonical_bytes(_high_water_document(header, ())),
            )
            _fsync_directory(temporary / "journal")
            _fsync_directory(temporary / "evidence")
            _fsync_directory(temporary)
            try:
                temporary.rename(destination)
            except OSError as exc:
                raise PhysicalOnboardingError(
                    "cannot atomically publish onboarding session"
                ) from exc
            _fsync_directory(session_root)
        except Exception:
            if temporary.is_dir() and not temporary.is_symlink():
                shutil.rmtree(temporary)
            raise
        session = cls(destination)
        session.snapshot()
        return session

    @classmethod
    def open(cls, directory: Path) -> "PhysicalOnboardingSession":
        session = cls(_safe_existing_directory(directory, "onboarding session"))
        session.snapshot()
        return session

    def snapshot(self) -> PhysicalOnboardingSnapshot:
        return load_physical_onboarding_session(self.directory)

    def store_evidence(
        self,
        stage: PhysicalOnboardingStage,
        payload: bytes,
        *,
        label: str,
        media_type: str,
        captured_at_ns: int,
    ) -> EvidenceReference:
        """Persist bounded evidence; the manifest is created after the payload."""

        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        if type(payload) is not bytes or not payload:
            raise PhysicalOnboardingError("evidence payload must be non-empty bytes")
        if len(payload) > MAX_EVIDENCE_BYTES:
            raise PhysicalOnboardingError("evidence payload exceeds the resource limit")
        evidence_label = _text(label, "evidence label", maximum=128)
        selected_media_type = _text(media_type, "media_type", maximum=129)
        if _MEDIA_TYPE.fullmatch(selected_media_type) is None:
            raise PhysicalOnboardingError("media_type is invalid")
        captured = _positive_integer(
            captured_at_ns, "captured_at_ns", maximum=2**63 - 1
        )
        snapshot = self.snapshot()
        if snapshot.next_action.stage is not stage:
            raise PhysicalOnboardingError("evidence may be stored only for the active stage")
        if snapshot.next_action.stage_state is StageState.SIDE_EFFECT_UNCERTAIN:
            raise PhysicalOnboardingError(
                "uncertain side effects forbid automatic evidence reacquisition"
            )
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        core = _evidence_core(
            header=snapshot.header,
            stage=stage,
            label=evidence_label,
            media_type=selected_media_type,
            captured_at_ns=captured,
            payload_sha256=payload_sha256,
            payload_bytes=len(payload),
        )
        package_sha256 = _stable_hash(core)
        evidence_id = f"evidence-{package_sha256}"
        manifest = {
            **core,
            "evidence_id": evidence_id,
            "package_sha256": package_sha256,
        }
        evidence_root = self.directory / "evidence"
        destination = _contained_child(evidence_root, evidence_id, "evidence package")
        if os.path.lexists(destination):
            raise PhysicalOnboardingError("immutable evidence package already exists")
        temporary = _contained_child(
            evidence_root,
            f".partial-{evidence_id}-{secrets.token_hex(8)}",
            "partial evidence package",
        )
        try:
            temporary.mkdir(exist_ok=False)
            _write_new(temporary / "payload.bin", payload)
            # This must remain the final file creation in the package.
            _write_new(temporary / "manifest.json", _canonical_bytes(manifest))
            _fsync_directory(temporary)
            if os.path.lexists(destination):
                raise PhysicalOnboardingError("immutable evidence package already exists")
            try:
                temporary.rename(destination)
            except OSError as exc:
                raise PhysicalOnboardingError(
                    "cannot atomically publish evidence package"
                ) from exc
            _fsync_directory(evidence_root)
        except Exception:
            if temporary.is_dir() and not temporary.is_symlink():
                shutil.rmtree(temporary)
            raise
        reference = _verify_evidence_directory(destination, snapshot.header)
        self.snapshot()
        return reference

    def commit_stage_state(
        self,
        stage: PhysicalOnboardingStage,
        state: StageState,
        *,
        occurred_at_ns: int,
        detail_code: str,
        evidence: Sequence[EvidenceReference] = (),
    ) -> PhysicalOnboardingSnapshot:
        """Append one stage transition after verifying the complete session."""

        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        if not isinstance(state, StageState):
            raise TypeError("state must be StageState")
        occurred = _positive_integer(
            occurred_at_ns, "occurred_at_ns", maximum=2**63 - 1
        )
        code = _detail_code(detail_code)
        if isinstance(evidence, (str, bytes)):
            raise PhysicalOnboardingError("evidence must be a reference sequence")
        retained = tuple(evidence)
        if len(retained) > MAX_EVENT_EVIDENCE_ITEMS:
            raise PhysicalOnboardingError("event references too much evidence")
        if any(not isinstance(item, EvidenceReference) for item in retained):
            raise TypeError("evidence must contain EvidenceReference values")
        if len({item.evidence_id for item in retained}) != len(retained):
            raise PhysicalOnboardingError("event repeats an evidence reference")

        current = self.snapshot()
        if len(current.events) >= MAX_JOURNAL_EVENTS:
            raise PhysicalOnboardingError("session journal has reached its event limit")
        if current.events and occurred <= current.events[-1].occurred_at_ns:
            raise PhysicalOnboardingError("event time must be strictly increasing")
        if occurred < current.header.created_at_ns:
            raise PhysicalOnboardingError("event time precedes session creation")
        evidence_by_id = {item.evidence_id: item for item in current.evidence}
        for reference in retained:
            if evidence_by_id.get(reference.evidence_id) != reference:
                raise PhysicalOnboardingError("event references unverified evidence")

        states = [item.state for item in current.stages]
        previous_state = states[STAGE_ORDER.index(stage)]
        _validate_transition(
            states,
            stage=stage,
            previous_state=previous_state,
            state=state,
            evidence=retained,
        )
        sequence = len(current.events)
        previous_hash = (
            _ZERO_DIGEST if not current.events else current.events[-1].event_sha256
        )
        event = OnboardingJournalEvent.build(
            header=current.header,
            sequence=sequence,
            stage=stage,
            previous_state=previous_state,
            state=state,
            occurred_at_ns=occurred,
            previous_event_sha256=previous_hash,
            evidence=retained,
            detail_code=code,
        )
        journal_root = self.directory / "journal"
        target = _contained_child(
            journal_root, f"event-{sequence:06d}.json", "journal event"
        )
        if os.path.lexists(target):
            raise PhysicalOnboardingError("immutable journal event already exists")
        onboarding_root = _safe_existing_directory(
            self.directory.parent, "onboarding root"
        )
        event_temporary = _contained_child(
            onboarding_root,
            f".partial-{current.header.session_id}-event-{sequence:06d}-"
            f"{secrets.token_hex(8)}",
            "partial journal event",
        )
        high_water_temporary = _contained_child(
            onboarding_root,
            f".partial-{current.header.session_id}-high-water-{sequence:06d}-"
            f"{secrets.token_hex(8)}",
            "partial journal high-water record",
        )
        next_high_water = _high_water_document(
            current.header, (*current.events, event)
        )
        try:
            _write_new(event_temporary, _canonical_bytes(event.to_dict()))
            _write_new(high_water_temporary, _canonical_bytes(next_high_water))
            try:
                os.link(event_temporary, target)
            except OSError as exc:
                raise PhysicalOnboardingError(
                    "cannot atomically append immutable journal event"
                ) from exc
            # Publish the immutable event first and advance the tail commitment
            # only after it is durable.  A crash between these operations leaves
            # a detectable mismatch and therefore cannot replay an old state.
            _fsync_directory(journal_root)
            try:
                os.replace(
                    high_water_temporary,
                    journal_root / _HIGH_WATER_FILENAME,
                )
            except OSError as exc:
                raise PhysicalOnboardingError(
                    "cannot atomically advance journal high-water record"
                ) from exc
            _fsync_directory(journal_root)
        finally:
            for temporary in (event_temporary, high_water_temporary):
                try:
                    if temporary.is_file() and not temporary.is_symlink():
                        temporary.unlink()
                except OSError:
                    pass
        return self.snapshot()

    def invalidate_from(
        self,
        stage: PhysicalOnboardingStage,
        *,
        occurred_at_ns: int,
        detail_code: str,
        evidence: Sequence[EvidenceReference] = (),
    ) -> PhysicalOnboardingSnapshot:
        """Invalidate one completed stage and every dependent downstream stage."""

        return self.commit_stage_state(
            stage,
            StageState.INVALIDATED,
            occurred_at_ns=occurred_at_ns,
            detail_code=detail_code,
            evidence=evidence,
        )
