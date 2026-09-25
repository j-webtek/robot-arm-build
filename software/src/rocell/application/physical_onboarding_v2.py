"""Additive V2 persistence for physical-onboarding reviewed state.

This module deliberately does not replace :mod:`physical_onboarding`.  The
existing V1 format remains readable through :func:`open_onboarding_session`,
but is exposed through a verify/export-only wrapper.  New V2 sessions keep
reviewed stage state separate from effect attempts: ``ACQUIRING`` is neither a
V2 enum value nor a writable/parsible V2 journal state.

The default publication adapter provides logical crash detection for tests and
non-effectful development.  It does *not* claim Windows power-loss durability.
A qualified adapter and the canonical leases can be injected by the later
cell-coordinator layer without changing the schemas in this file.

No camera, serial, power, motion, or contact backend is imported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
    read_bounded_regular_file,
)
from rocell.application.physical_onboarding import (
    EVIDENCE_MANIFEST_SCHEMA,
    MAX_EVIDENCE_BYTES,
    MAX_EVIDENCE_ITEMS,
    MAX_EVENT_EVIDENCE_ITEMS,
    MAX_JOURNAL_EVENTS,
    MAX_JSON_BYTES,
    MAX_TOTAL_EVIDENCE_BYTES,
    SESSION_HEADER_SCHEMA as LEGACY_V1_HEADER_SCHEMA,
    STAGE_ACTION_CODES,
    STAGE_ORDER,
    STAGE_PLAN_SHA256,
    STAGE_PREREQUISITES,
    EvidenceReference,
    PhysicalOnboardingStage,
    load_physical_onboarding_session,
)


SESSION_HEADER_SCHEMA_V2 = "rocell.physical_onboarding_header.v2"
SESSION_EVENT_SCHEMA_V2 = "rocell.physical_onboarding_event.v2"
SESSION_HEAD_SCHEMA_V2 = "rocell.physical_onboarding_head.v2"
SESSION_VERIFICATION_SCHEMA_V2 = "rocell.physical_onboarding_verification.v2"
LEGACY_VERIFICATION_SCHEMA = "rocell.physical_onboarding_legacy_verification.v1"

LEGACY_V1_READ_ONLY = "LEGACY_V1_READ_ONLY"
V2_UNCOMMITTED_SUFFIX = "V2_UNCOMMITTED_SUFFIX"
PORTABLE_UNQUALIFIED = "PORTABLE_UNQUALIFIED"
WINDOWS_NTFS_QUALIFIED = "WINDOWS_NTFS_QUALIFIED"

_ZERO_DIGEST = "0" * 64
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DETAIL_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_MEDIA_TYPE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,63}/" r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,63}$"
)
_EVENT_FILENAME = re.compile(r"^event-([0-9]{6})\.json$")
_EVIDENCE_DIRECTORY = re.compile(r"^evidence-([0-9a-f]{64})$")
_HEAD_FILENAME = "head.json"
_MAX_EXPORT_BYTES = 8 * 1024 * 1024


class PhysicalOnboardingV2Error(ValueError):
    """The V2 store or requested transition is invalid or unsafe."""


class LegacyV1ReadOnlyError(PhysicalOnboardingV2Error):
    """A mutation was attempted through a legacy compatibility wrapper."""


class V2UncommittedSuffixError(PhysicalOnboardingV2Error):
    """A mutation was attempted while an uncommitted event suffix exists."""


class V2StageState(str, Enum):
    """Reviewed stage dispositions; effect progress lives in another ledger."""

    PENDING = "PENDING"
    WAITING_OPERATOR = "WAITING_OPERATOR"
    REVIEW_PENDING = "REVIEW_PENDING"
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    INVALIDATED = "INVALIDATED"
    INCIDENT_HOLD = "INCIDENT_HOLD"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    COMPLETE_DIAGNOSTIC = "COMPLETE_DIAGNOSTIC"


if len(STAGE_ORDER) != 15 or len(set(STAGE_ORDER)) != 15:
    raise RuntimeError("V2 requires the exact canonical fifteen-stage plan")


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
        raise PhysicalOnboardingV2Error(f"value is not JSON-safe: {exc}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise PhysicalOnboardingV2Error("canonical JSON exceeds the resource limit")
    return payload


def _canonical_bytes(value: object, *, maximum: int = MAX_JSON_BYTES) -> bytes:
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
        raise PhysicalOnboardingV2Error(f"value is not canonical JSON: {exc}") from exc
    if len(payload) > maximum:
        raise PhysicalOnboardingV2Error("canonical JSON exceeds the resource limit")
    return payload


def _stable_hash(value: object) -> str:
    return hashlib.sha256(_compact_bytes(value)).hexdigest()


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingV2Error(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PhysicalOnboardingV2Error(f"nonfinite JSON number {value!r}")
    raise PhysicalOnboardingV2Error("V2 onboarding JSON must not contain floats")


def _reject_constant(value: str) -> None:
    raise PhysicalOnboardingV2Error(f"nonfinite JSON constant {value!r}")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PhysicalOnboardingV2Error(f"{label} must be a JSON object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PhysicalOnboardingV2Error(f"{label} must be a JSON array")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise PhysicalOnboardingV2Error(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise PhysicalOnboardingV2Error(
            f"{label} must be a bounded portable identifier"
        )
    if value in {".", ".."} or value.endswith((".", " ")):
        raise PhysicalOnboardingV2Error(f"{label} is not a safe path identifier")
    if value.split(".", 1)[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        raise PhysicalOnboardingV2Error(f"{label} is a reserved filename")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PhysicalOnboardingV2Error(f"{label} must be lowercase SHA-256")
    return value


def _bounded_int(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise PhysicalOnboardingV2Error(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PhysicalOnboardingV2Error(f"{label} must be non-empty trimmed text")
    if len(value) > maximum or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise PhysicalOnboardingV2Error(f"{label} is not bounded printable text")
    return value


def _detail_code(value: object) -> str:
    if not isinstance(value, str) or _DETAIL_CODE.fullmatch(value) is None:
        raise PhysicalOnboardingV2Error("detail_code must be a bounded uppercase code")
    return value


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _reject_link_chain(path: Path, label: str) -> None:
    cursor = Path(os.path.abspath(path))
    while True:
        # One fresh observation per component, including missing-path ancestors.
        # Never cache between calls or combine link/attribute observations taken
        # at different times. Original-file handle/hardlink checks stay separate.
        try:
            observed = cursor.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise PhysicalOnboardingV2Error(
                f"{label} path component could not be inspected"
            ) from exc
        else:
            if stat.S_ISLNK(observed.st_mode) or (
                getattr(observed, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ):
                raise PhysicalOnboardingV2Error(
                    f"{label} contains a link or reparse point"
                )
        if cursor.parent == cursor:
            return
        cursor = cursor.parent


def _safe_directory(path: Path, label: str) -> Path:
    _reject_link_chain(path, label)
    try:
        selected = Path(path).resolve(strict=True)
    except OSError as exc:
        raise PhysicalOnboardingV2Error(f"{label} is unavailable") from exc
    if not selected.is_dir():
        raise PhysicalOnboardingV2Error(f"{label} is not a directory")
    return selected


def _contained_child(root: Path, name: str, label: str) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise PhysicalOnboardingV2Error(f"{label} is not a plain path segment")
    child = root / name
    if child.resolve(strict=False).parent != root:
        raise PhysicalOnboardingV2Error(f"{label} escapes its root")
    return child


def _read_canonical_json(
    path: Path, label: str, *, maximum: int = MAX_JSON_BYTES
) -> tuple[dict[str, Any], bytes]:
    _reject_link_chain(path, label)
    try:
        payload = read_bounded_regular_file(
            path,
            maximum_bytes=maximum,
            label=label,
        )
    except (OSError, PhysicalOnboardingDurabilityError) as exc:
        raise PhysicalOnboardingV2Error(f"cannot read {label}") from exc
    try:
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except PhysicalOnboardingV2Error:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PhysicalOnboardingV2Error(f"{label} is not strict JSON") from exc
    document = _mapping(parsed, label)
    if _canonical_bytes(document, maximum=maximum) != payload:
        raise PhysicalOnboardingV2Error(f"{label} is not canonical JSON")
    return dict(document), payload


def _bounded_scandir(path: Path, *, maximum_entries: int, label: str) -> list[Any]:
    """Enumerate at most ``maximum_entries`` without materializing overflow."""

    entries: list[Any] = []
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                if len(entries) >= maximum_entries:
                    raise PhysicalOnboardingV2Error(f"{label} exceeds the entry limit")
                entries.append(entry)
    except PhysicalOnboardingV2Error:
        raise
    except OSError as exc:
        raise PhysicalOnboardingV2Error(f"cannot enumerate {label}") from exc
    return entries


@runtime_checkable
class SessionPublicationProtocol(Protocol):
    """Publication seam; implementations must never silently overwrite records."""

    @property
    def effectful_durability_qualified(self) -> bool: ...

    @property
    def durability_qualification_sha256(self) -> str: ...

    def write_new_file(self, path: Path, payload: bytes) -> None: ...

    def replace_file(self, path: Path, payload: bytes) -> None: ...

    def publish_new_directory(self, source: Path, destination: Path) -> None: ...

    def sync_directory(self, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class PortableSessionPublication:
    """Logical publication only; deliberately unqualified for physical effects."""

    effectful_durability_qualified: bool = field(default=False, init=False)
    durability_qualification_sha256: str = field(default=_ZERO_DIGEST, init=False)

    def write_new_file(self, path: Path, payload: bytes) -> None:
        try:
            with path.open("xb") as stream:
                written = stream.write(payload)
                if written != len(payload):
                    raise OSError("short write")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise PhysicalOnboardingV2Error(
                f"cannot publish immutable file {path.name}"
            ) from exc

    def replace_file(self, path: Path, payload: bytes) -> None:
        temporary = path.parent / f".partial-{path.name}-{secrets.token_hex(8)}"
        try:
            self.write_new_file(temporary, payload)
            os.replace(temporary, path)
        except OSError as exc:
            raise PhysicalOnboardingV2Error(f"cannot replace {path.name}") from exc
        finally:
            try:
                if temporary.is_file() and not temporary.is_symlink():
                    temporary.unlink()
            except OSError:
                pass

    def publish_new_directory(self, source: Path, destination: Path) -> None:
        if os.path.lexists(destination):
            raise PhysicalOnboardingV2Error(
                f"immutable directory already exists: {destination.name}"
            )
        try:
            source.rename(destination)
        except OSError as exc:
            raise PhysicalOnboardingV2Error(
                f"cannot publish immutable directory {destination.name}"
            ) from exc

    def sync_directory(self, path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError:
            if os.name == "nt":
                return
            raise
        try:
            os.fsync(descriptor)
        except OSError:
            if os.name != "nt":
                raise
        finally:
            os.close(descriptor)


PORTABLE_SESSION_PUBLICATION = PortableSessionPublication()


def _validate_publication_provenance(mode: object, qualification: object) -> None:
    """Keep durable and portable V2 stores structurally non-interchangeable."""

    if not isinstance(mode, str):
        raise PhysicalOnboardingV2Error("publication_durability must be text")
    selected = _digest(qualification, "durability_qualification_sha256")
    if mode == PORTABLE_UNQUALIFIED:
        if selected != _ZERO_DIGEST:
            raise PhysicalOnboardingV2Error(
                "portable V2 publication must use the zero qualification hash"
            )
        return
    if mode == WINDOWS_NTFS_QUALIFIED:
        if selected == _ZERO_DIGEST:
            raise PhysicalOnboardingV2Error(
                "qualified V2 publication requires a nonzero qualification hash"
            )
        return
    raise PhysicalOnboardingV2Error("unsupported V2 publication durability mode")


def _publication_provenance(
    publication: SessionPublicationProtocol,
) -> tuple[str, str]:
    qualified = publication.effectful_durability_qualified
    if not isinstance(qualified, bool):
        raise PhysicalOnboardingV2Error(
            "publication durability disposition must be boolean"
        )
    qualification = _digest(
        publication.durability_qualification_sha256,
        "publication durability qualification",
    )
    mode = WINDOWS_NTFS_QUALIFIED if qualified else PORTABLE_UNQUALIFIED
    _validate_publication_provenance(mode, qualification)
    return mode, qualification


@dataclass(frozen=True, slots=True)
class V2SessionHeader:
    session_id: str
    cell_id: str
    created_at_ns: int
    source_binding_sha256: str
    publication_durability: str
    durability_qualification_sha256: str
    header_sha256: str
    schema: str = SESSION_HEADER_SCHEMA_V2
    # Compatible value extension: the existing physical default serializes
    # exactly as before. Rehearsal is explicit, immutable, and namespace-bound.
    mode: str = "PHYSICAL_DIAGNOSTIC"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "session_id": self.session_id,
            "cell_id": self.cell_id,
            "mode": self.mode,
            "created_at_ns": self.created_at_ns,
            "source_binding_sha256": self.source_binding_sha256,
            "publication_durability": self.publication_durability,
            "durability_qualification_sha256": self.durability_qualification_sha256,
            "stage_plan_sha256": STAGE_PLAN_SHA256,
            "ordered_stages": [stage.value for stage in STAGE_ORDER],
            "diagnostic_only": True,
            "automatic_effect_replay_allowed": False,
            "device_io_authorized": False,
            "robot_power_authorized": False,
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
        publication_durability: str,
        durability_qualification_sha256: str,
        mode: str = "PHYSICAL_DIAGNOSTIC",
    ) -> "V2SessionHeader":
        session = _identifier(session_id, "session_id")
        cell = _identifier(cell_id, "cell_id")
        _validate_session_mode(mode, cell, session)
        created = _bounded_int(
            created_at_ns, "created_at_ns", minimum=1, maximum=2**63 - 1
        )
        source = _digest(source_binding_sha256, "source_binding_sha256")
        qualification = _digest(
            durability_qualification_sha256, "durability_qualification_sha256"
        )
        _validate_publication_provenance(publication_durability, qualification)
        provisional = cls(
            session,
            cell,
            created,
            source,
            publication_durability,
            qualification,
            _ZERO_DIGEST,
            mode=mode,
        )
        return cls(
            session,
            cell,
            created,
            source,
            publication_durability,
            qualification,
            _stable_hash(provisional.core_dict()),
            mode=mode,
        )


_HEADER_FIELDS = frozenset(
    {
        "schema",
        "session_id",
        "cell_id",
        "mode",
        "created_at_ns",
        "source_binding_sha256",
        "publication_durability",
        "durability_qualification_sha256",
        "stage_plan_sha256",
        "ordered_stages",
        "diagnostic_only",
        "automatic_effect_replay_allowed",
        "device_io_authorized",
        "robot_power_authorized",
        "motion_authorized",
        "contact_authorized",
        "physical_release_effect",
        "header_sha256",
    }
)


def _validate_session_mode(mode: object, cell_id: str, session_id: str) -> None:
    if type(mode) is not str or mode not in {"PHYSICAL_DIAGNOSTIC", "REHEARSAL"}:
        raise PhysicalOnboardingV2Error("unsupported V2 session mode")
    if mode == "REHEARSAL" and (
        type(cell_id) is not str
        or type(session_id) is not str
        or re.fullmatch(r"wizard-rehearsal-[0-9a-f]{16}", cell_id) is None
        or re.fullmatch(r"rehearsal-[0-9a-f]{32}", session_id) is None
    ):
        raise PhysicalOnboardingV2Error(
            "rehearsal V2 sessions require their isolated namespace"
        )


def _parse_header(value: object) -> V2SessionHeader:
    document = _mapping(value, "V2 session header")
    _exact_fields(document, _HEADER_FIELDS, "V2 session header")
    if document["schema"] != SESSION_HEADER_SCHEMA_V2:
        raise PhysicalOnboardingV2Error("unsupported V2 session-header schema")
    _validate_session_mode(
        document["mode"], document["cell_id"], document["session_id"]
    )
    if document["stage_plan_sha256"] != STAGE_PLAN_SHA256 or document[
        "ordered_stages"
    ] != [stage.value for stage in STAGE_ORDER]:
        raise PhysicalOnboardingV2Error(
            "V2 session does not bind the canonical stage plan"
        )
    if (
        document["diagnostic_only"] is not True
        or document["automatic_effect_replay_allowed"] is not False
        or document["device_io_authorized"] is not False
        or document["robot_power_authorized"] is not False
        or document["motion_authorized"] is not False
        or document["contact_authorized"] is not False
        or document["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingV2Error("V2 session header exceeds zero authority")
    publication_durability = _text(
        document["publication_durability"],
        "publication_durability",
        maximum=64,
    )
    qualification = _digest(
        document["durability_qualification_sha256"],
        "durability_qualification_sha256",
    )
    _validate_publication_provenance(publication_durability, qualification)
    header = V2SessionHeader(
        session_id=_identifier(document["session_id"], "session_id"),
        cell_id=_identifier(document["cell_id"], "cell_id"),
        created_at_ns=_bounded_int(
            document["created_at_ns"], "created_at_ns", minimum=1, maximum=2**63 - 1
        ),
        source_binding_sha256=_digest(
            document["source_binding_sha256"], "source_binding_sha256"
        ),
        publication_durability=publication_durability,
        durability_qualification_sha256=qualification,
        header_sha256=_digest(document["header_sha256"], "header_sha256"),
        schema=document["schema"],
        mode=document["mode"],
    )
    if header.header_sha256 != _stable_hash(header.core_dict()):
        raise PhysicalOnboardingV2Error("V2 session header hash mismatch")
    return header


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


def _parse_evidence_reference(value: object) -> EvidenceReference:
    document = _mapping(value, "V2 event evidence reference")
    _exact_fields(document, _EVIDENCE_REFERENCE_FIELDS, "V2 event evidence reference")
    try:
        stage = PhysicalOnboardingStage(document["stage"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingV2Error("evidence reference stage is invalid") from exc
    package = _digest(document["package_sha256"], "package_sha256")
    if document["evidence_id"] != f"evidence-{package}":
        raise PhysicalOnboardingV2Error("evidence_id is not content-addressed")
    return EvidenceReference(
        evidence_id=document["evidence_id"],
        stage=stage,
        package_sha256=package,
        manifest_sha256=_digest(document["manifest_sha256"], "manifest_sha256"),
        payload_sha256=_digest(document["payload_sha256"], "payload_sha256"),
        payload_bytes=_bounded_int(
            document["payload_bytes"],
            "payload_bytes",
            minimum=1,
            maximum=MAX_EVIDENCE_BYTES,
        ),
    )


def _hash_file(path: Path, *, maximum: int) -> tuple[str, int]:
    _reject_link_chain(path, "evidence payload")
    try:
        payload = read_bounded_regular_file(
            path,
            maximum_bytes=maximum,
            label="evidence payload",
        )
    except (OSError, PhysicalOnboardingDurabilityError) as exc:
        raise PhysicalOnboardingV2Error("cannot read evidence payload") from exc
    if not payload:
        raise PhysicalOnboardingV2Error("evidence payload must not be empty")
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _evidence_core(
    *,
    header: V2SessionHeader,
    stage: PhysicalOnboardingStage,
    label: str,
    media_type: str,
    captured_at_ns: int,
    payload_sha256: str,
    payload_bytes: int,
) -> dict[str, Any]:
    # The existing ordinary evidence package remains canonical in V2.  Its
    # immutable session-header binding distinguishes V1 and V2 ownership.
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


def _verify_evidence_directory(
    directory: Path, header: V2SessionHeader
) -> EvidenceReference:
    _reject_link_chain(directory, "evidence package")
    if not directory.is_dir():
        raise PhysicalOnboardingV2Error("evidence package must be a real directory")
    match = _EVIDENCE_DIRECTORY.fullmatch(directory.name)
    if match is None:
        raise PhysicalOnboardingV2Error("evidence package name is invalid")
    entries = _bounded_scandir(directory, maximum_entries=2, label="evidence package")
    if {entry.name for entry in entries} != {"payload.bin", "manifest.json"}:
        raise PhysicalOnboardingV2Error("evidence package file set is not exact")
    if any(
        entry.is_symlink() or not entry.is_file(follow_symlinks=False)
        for entry in entries
    ):
        raise PhysicalOnboardingV2Error("evidence package contains an unsafe entry")

    manifest, manifest_payload = _read_canonical_json(
        directory / "manifest.json", "evidence manifest"
    )
    _exact_fields(manifest, _EVIDENCE_MANIFEST_FIELDS, "evidence manifest")
    if manifest["schema"] != EVIDENCE_MANIFEST_SCHEMA:
        raise PhysicalOnboardingV2Error("unsupported evidence-manifest schema")
    if (
        manifest["manifest_written_last"] is not True
        or manifest["diagnostic_only"] is not True
        or manifest["automatic_effect_replay_allowed"] is not False
        or manifest["motion_authorized"] is not False
        or manifest["contact_authorized"] is not False
        or manifest["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingV2Error("evidence manifest exceeds zero authority")
    if (
        manifest["session_id"] != header.session_id
        or manifest["session_header_sha256"] != header.header_sha256
    ):
        raise PhysicalOnboardingV2Error("evidence belongs to another session")
    if manifest["payload_filename"] != "payload.bin":
        raise PhysicalOnboardingV2Error("evidence payload filename is invalid")
    try:
        stage = PhysicalOnboardingStage(manifest["stage"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingV2Error("evidence stage is invalid") from exc
    _text(manifest["label"], "evidence label", maximum=128)
    media_type = _text(manifest["media_type"], "evidence media_type", maximum=129)
    if _MEDIA_TYPE.fullmatch(media_type) is None:
        raise PhysicalOnboardingV2Error("evidence media_type is invalid")
    _bounded_int(
        manifest["captured_at_ns"],
        "captured_at_ns",
        minimum=1,
        maximum=2**63 - 1,
    )
    expected_payload_hash = _digest(manifest["payload_sha256"], "payload_sha256")
    expected_payload_bytes = _bounded_int(
        manifest["payload_bytes"],
        "payload_bytes",
        minimum=1,
        maximum=MAX_EVIDENCE_BYTES,
    )
    payload_hash, payload_bytes = _hash_file(
        directory / "payload.bin", maximum=MAX_EVIDENCE_BYTES
    )
    if payload_hash != expected_payload_hash or payload_bytes != expected_payload_bytes:
        raise PhysicalOnboardingV2Error("evidence payload hash or size mismatch")
    package = _digest(manifest["package_sha256"], "package_sha256")
    core = dict(manifest)
    del core["evidence_id"]
    del core["package_sha256"]
    if _stable_hash(core) != package:
        raise PhysicalOnboardingV2Error("evidence package hash mismatch")
    evidence_id = manifest["evidence_id"]
    if evidence_id != f"evidence-{package}" or directory.name != evidence_id:
        raise PhysicalOnboardingV2Error("evidence directory is not content-addressed")
    return EvidenceReference(
        evidence_id=evidence_id,
        stage=stage,
        package_sha256=package,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        payload_sha256=payload_hash,
        payload_bytes=payload_bytes,
    )


@dataclass(frozen=True, slots=True)
class V2JournalEvent:
    session_id: str
    session_header_sha256: str
    sequence: int
    stage: PhysicalOnboardingStage
    previous_state: V2StageState
    state: V2StageState
    occurred_at_ns: int
    previous_event_sha256: str
    evidence: tuple[EvidenceReference, ...]
    detail_code: str
    event_sha256: str
    schema: str = SESSION_EVENT_SCHEMA_V2

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
            "attempt_progress_recorded_in_stage_state": False,
            "automatic_effect_replay_allowed": False,
            "device_io_authorized": False,
            "robot_power_authorized": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "event_sha256": self.event_sha256}

    @classmethod
    def build(
        cls,
        *,
        header: V2SessionHeader,
        sequence: int,
        stage: PhysicalOnboardingStage,
        previous_state: V2StageState,
        state: V2StageState,
        occurred_at_ns: int,
        previous_event_sha256: str,
        evidence: tuple[EvidenceReference, ...],
        detail_code: str,
    ) -> "V2JournalEvent":
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
        "attempt_progress_recorded_in_stage_state",
        "automatic_effect_replay_allowed",
        "device_io_authorized",
        "robot_power_authorized",
        "motion_authorized",
        "contact_authorized",
        "physical_release_effect",
        "event_sha256",
    }
)


def _parse_state(value: object, label: str) -> V2StageState:
    if value == "ACQUIRING":
        raise PhysicalOnboardingV2Error("ACQUIRING is forbidden in V2 stage journals")
    try:
        return V2StageState(value)
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingV2Error(f"{label} is not a V2 stage state") from exc


def _parse_event(value: object) -> V2JournalEvent:
    document = _mapping(value, "V2 journal event")
    _exact_fields(document, _EVENT_FIELDS, "V2 journal event")
    if document["schema"] != SESSION_EVENT_SCHEMA_V2:
        raise PhysicalOnboardingV2Error("unsupported V2 journal-event schema")
    if (
        document["attempt_progress_recorded_in_stage_state"] is not False
        or document["automatic_effect_replay_allowed"] is not False
        or document["device_io_authorized"] is not False
        or document["robot_power_authorized"] is not False
        or document["motion_authorized"] is not False
        or document["contact_authorized"] is not False
        or document["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingV2Error("V2 journal event exceeds zero authority")
    try:
        stage = PhysicalOnboardingStage(document["stage"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingV2Error("V2 journal event stage is invalid") from exc
    raw_evidence = _array(document["evidence"], "V2 event evidence")
    if len(raw_evidence) > MAX_EVENT_EVIDENCE_ITEMS:
        raise PhysicalOnboardingV2Error("V2 event references too much evidence")
    evidence = tuple(_parse_evidence_reference(item) for item in raw_evidence)
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise PhysicalOnboardingV2Error("V2 event repeats an evidence reference")
    event = V2JournalEvent(
        session_id=_identifier(document["session_id"], "event session_id"),
        session_header_sha256=_digest(
            document["session_header_sha256"], "session_header_sha256"
        ),
        sequence=_bounded_int(
            document["sequence"],
            "event sequence",
            minimum=0,
            maximum=MAX_JOURNAL_EVENTS - 1,
        ),
        stage=stage,
        previous_state=_parse_state(document["previous_state"], "previous_state"),
        state=_parse_state(document["state"], "state"),
        occurred_at_ns=_bounded_int(
            document["occurred_at_ns"], "occurred_at_ns", minimum=1, maximum=2**63 - 1
        ),
        previous_event_sha256=_digest(
            document["previous_event_sha256"], "previous_event_sha256"
        ),
        evidence=evidence,
        detail_code=_detail_code(document["detail_code"]),
        event_sha256=_digest(document["event_sha256"], "event_sha256"),
        schema=document["schema"],
    )
    if event.event_sha256 != _stable_hash(event.core_dict()):
        raise PhysicalOnboardingV2Error("V2 journal event hash mismatch")
    return event


@dataclass(frozen=True, slots=True)
class V2CommittedHead:
    session_id: str
    session_header_sha256: str
    event_count: int
    committed_sequence: int | None
    committed_stage: PhysicalOnboardingStage | None
    committed_state: V2StageState | None
    committed_event_sha256: str
    committed_event_time_ns: int | None
    head_sha256: str
    schema: str = SESSION_HEAD_SCHEMA_V2

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "session_id": self.session_id,
            "session_header_sha256": self.session_header_sha256,
            "event_count": self.event_count,
            "committed_sequence": self.committed_sequence,
            "committed_stage": (
                None if self.committed_stage is None else self.committed_stage.value
            ),
            "committed_state": (
                None if self.committed_state is None else self.committed_state.value
            ),
            "committed_event_sha256": self.committed_event_sha256,
            "committed_event_time_ns": self.committed_event_time_ns,
            "automatic_effect_replay_allowed": False,
            "device_io_authorized": False,
            "robot_power_authorized": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "head_sha256": self.head_sha256}

    @classmethod
    def build(
        cls, header: V2SessionHeader, events: Sequence[V2JournalEvent]
    ) -> "V2CommittedHead":
        if len(events) > MAX_JOURNAL_EVENTS:
            raise PhysicalOnboardingV2Error("cannot anchor an oversized V2 journal")
        tail = None if not events else events[-1]
        provisional = cls(
            session_id=header.session_id,
            session_header_sha256=header.header_sha256,
            event_count=len(events),
            committed_sequence=None if tail is None else tail.sequence,
            committed_stage=None if tail is None else tail.stage,
            committed_state=None if tail is None else tail.state,
            committed_event_sha256=_ZERO_DIGEST if tail is None else tail.event_sha256,
            committed_event_time_ns=None if tail is None else tail.occurred_at_ns,
            head_sha256=_ZERO_DIGEST,
        )
        return cls(
            session_id=provisional.session_id,
            session_header_sha256=provisional.session_header_sha256,
            event_count=provisional.event_count,
            committed_sequence=provisional.committed_sequence,
            committed_stage=provisional.committed_stage,
            committed_state=provisional.committed_state,
            committed_event_sha256=provisional.committed_event_sha256,
            committed_event_time_ns=provisional.committed_event_time_ns,
            head_sha256=_stable_hash(provisional.core_dict()),
        )


_HEAD_FIELDS = frozenset(
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
        "automatic_effect_replay_allowed",
        "device_io_authorized",
        "robot_power_authorized",
        "motion_authorized",
        "contact_authorized",
        "physical_release_effect",
        "head_sha256",
    }
)


def _parse_head(value: object) -> V2CommittedHead:
    document = _mapping(value, "V2 committed head")
    _exact_fields(document, _HEAD_FIELDS, "V2 committed head")
    if document["schema"] != SESSION_HEAD_SCHEMA_V2:
        raise PhysicalOnboardingV2Error("unsupported V2 committed-head schema")
    if (
        document["automatic_effect_replay_allowed"] is not False
        or document["device_io_authorized"] is not False
        or document["robot_power_authorized"] is not False
        or document["motion_authorized"] is not False
        or document["contact_authorized"] is not False
        or document["physical_release_effect"] != "NONE"
    ):
        raise PhysicalOnboardingV2Error("V2 committed head exceeds zero authority")
    count = _bounded_int(
        document["event_count"],
        "head event_count",
        minimum=0,
        maximum=MAX_JOURNAL_EVENTS,
    )
    if count == 0:
        if (
            document["committed_sequence"] is not None
            or document["committed_stage"] is not None
            or document["committed_state"] is not None
            or document["committed_event_sha256"] != _ZERO_DIGEST
            or document["committed_event_time_ns"] is not None
        ):
            raise PhysicalOnboardingV2Error("empty V2 committed head is inconsistent")
        sequence = None
        stage = None
        state = None
        event_time = None
    else:
        sequence = _bounded_int(
            document["committed_sequence"],
            "committed_sequence",
            minimum=0,
            maximum=MAX_JOURNAL_EVENTS - 1,
        )
        if sequence != count - 1:
            raise PhysicalOnboardingV2Error(
                "V2 committed-head sequence is inconsistent"
            )
        try:
            stage = PhysicalOnboardingStage(document["committed_stage"])
        except (TypeError, ValueError) as exc:
            raise PhysicalOnboardingV2Error("committed_stage is invalid") from exc
        state = _parse_state(document["committed_state"], "committed_state")
        event_time = _bounded_int(
            document["committed_event_time_ns"],
            "committed_event_time_ns",
            minimum=1,
            maximum=2**63 - 1,
        )
    head = V2CommittedHead(
        session_id=_identifier(document["session_id"], "head session_id"),
        session_header_sha256=_digest(
            document["session_header_sha256"], "head session_header_sha256"
        ),
        event_count=count,
        committed_sequence=sequence,
        committed_stage=stage,
        committed_state=state,
        committed_event_sha256=_digest(
            document["committed_event_sha256"], "committed_event_sha256"
        ),
        committed_event_time_ns=event_time,
        head_sha256=_digest(document["head_sha256"], "head_sha256"),
        schema=document["schema"],
    )
    if head.head_sha256 != _stable_hash(head.core_dict()):
        raise PhysicalOnboardingV2Error("V2 committed-head hash mismatch")
    return head


_ALLOWED_TRANSITIONS: Mapping[V2StageState, frozenset[V2StageState]] = MappingProxyType(
    {
        V2StageState.PENDING: frozenset(
            {
                V2StageState.WAITING_OPERATOR,
                V2StageState.BLOCKED,
                V2StageState.INCIDENT_HOLD,
            }
        ),
        V2StageState.WAITING_OPERATOR: frozenset(
            {
                V2StageState.REVIEW_PENDING,
                V2StageState.BLOCKED,
                V2StageState.INCIDENT_HOLD,
                V2StageState.SIDE_EFFECT_UNCERTAIN,
            }
        ),
        V2StageState.REVIEW_PENDING: frozenset(
            {
                V2StageState.PASS,
                V2StageState.BLOCKED,
                V2StageState.INCIDENT_HOLD,
                V2StageState.SIDE_EFFECT_UNCERTAIN,
                V2StageState.COMPLETE_DIAGNOSTIC,
            }
        ),
        V2StageState.PASS: frozenset(
            {V2StageState.INVALIDATED, V2StageState.INCIDENT_HOLD}
        ),
        V2StageState.BLOCKED: frozenset(
            {V2StageState.WAITING_OPERATOR, V2StageState.INCIDENT_HOLD}
        ),
        V2StageState.INVALIDATED: frozenset(
            {
                V2StageState.WAITING_OPERATOR,
                V2StageState.BLOCKED,
                V2StageState.INCIDENT_HOLD,
            }
        ),
        V2StageState.INCIDENT_HOLD: frozenset(),
        V2StageState.SIDE_EFFECT_UNCERTAIN: frozenset(),
        V2StageState.COMPLETE_DIAGNOSTIC: frozenset(
            {V2StageState.INVALIDATED, V2StageState.INCIDENT_HOLD}
        ),
    }
)


def _first_incomplete(states: Sequence[V2StageState]) -> PhysicalOnboardingStage | None:
    for stage, state in zip(STAGE_ORDER, states):
        if state not in {V2StageState.PASS, V2StageState.COMPLETE_DIAGNOSTIC}:
            return stage
    return None


def _validate_transition(
    states: Sequence[V2StageState],
    *,
    stage: PhysicalOnboardingStage,
    previous_state: V2StageState,
    state: V2StageState,
    evidence: Sequence[EvidenceReference],
) -> None:
    index = STAGE_ORDER.index(stage)
    if states[index] is not previous_state:
        raise PhysicalOnboardingV2Error(
            "V2 event previous_state differs from committed derived state"
        )
    if state not in _ALLOWED_TRANSITIONS[previous_state]:
        raise PhysicalOnboardingV2Error(
            f"invalid V2 onboarding transition {previous_state.value}->{state.value}"
        )
    if state is V2StageState.INVALIDATED:
        if previous_state not in {
            V2StageState.PASS,
            V2StageState.COMPLETE_DIAGNOSTIC,
        }:
            raise PhysicalOnboardingV2Error(
                "only completed V2 evidence can be invalidated"
            )
    elif (
        previous_state
        in {
            V2StageState.PASS,
            V2StageState.COMPLETE_DIAGNOSTIC,
        }
        and state is V2StageState.INCIDENT_HOLD
    ):
        # An incident may hold a previously completed stage without pretending
        # that its historical PASS was erased.
        pass
    else:
        active = _first_incomplete(states)
        if active is not stage:
            raise PhysicalOnboardingV2Error(
                f"stage {stage.value} cannot run before "
                f"{active.value if active is not None else 'completion'}"
            )
        for prerequisite in STAGE_PREREQUISITES[stage]:
            prerequisite_state = states[STAGE_ORDER.index(prerequisite)]
            if prerequisite_state not in {
                V2StageState.PASS,
                V2StageState.COMPLETE_DIAGNOSTIC,
            }:
                raise PhysicalOnboardingV2Error(
                    f"stage prerequisite is not satisfied: {prerequisite.value}"
                )
    if state is V2StageState.COMPLETE_DIAGNOSTIC:
        if stage is not PhysicalOnboardingStage.PHYSICAL_HANDOFF:
            raise PhysicalOnboardingV2Error(
                "COMPLETE_DIAGNOSTIC is reserved for physical_handoff"
            )
    elif (
        stage is PhysicalOnboardingStage.PHYSICAL_HANDOFF and state is V2StageState.PASS
    ):
        raise PhysicalOnboardingV2Error(
            "physical_handoff must end as COMPLETE_DIAGNOSTIC, not PASS"
        )
    if (
        state
        in {
            V2StageState.REVIEW_PENDING,
            V2StageState.PASS,
            V2StageState.COMPLETE_DIAGNOSTIC,
        }
        and not evidence
    ):
        raise PhysicalOnboardingV2Error(f"{state.value} requires retained evidence")
    if any(item.stage is not stage for item in evidence):
        raise PhysicalOnboardingV2Error("V2 event evidence belongs to another stage")


def _apply_transition(states: list[V2StageState], event: V2JournalEvent) -> None:
    _validate_transition(
        states,
        stage=event.stage,
        previous_state=event.previous_state,
        state=event.state,
        evidence=event.evidence,
    )
    index = STAGE_ORDER.index(event.stage)
    if event.state is V2StageState.INVALIDATED:
        for downstream in range(index, len(states)):
            if states[downstream] not in {
                V2StageState.INCIDENT_HOLD,
                V2StageState.SIDE_EFFECT_UNCERTAIN,
            }:
                states[downstream] = V2StageState.INVALIDATED
    else:
        states[index] = event.state


@dataclass(frozen=True, slots=True)
class V2StageSnapshot:
    stage: PhysicalOnboardingStage
    state: V2StageState
    last_event_sequence: int | None
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "state": self.state.value,
            "last_event_sequence": self.last_event_sequence,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class V2NextAction:
    code: str
    stage: PhysicalOnboardingStage | None
    stage_state: V2StageState | None
    operator_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": None if self.stage is None else self.stage.value,
            "stage_state": None if self.stage_state is None else self.stage_state.value,
            "operator_required": self.operator_required,
            "diagnostic_only": True,
            "automatic_effect_replay_allowed": False,
            "device_io_authorized": False,
            "robot_power_authorized": False,
            "motion_authorized": False,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
        }


def _derive_next_action(states: Sequence[V2StageState]) -> V2NextAction:
    stage = _first_incomplete(states)
    if stage is None:
        return V2NextAction("NO_ACTION_DIAGNOSTIC_COMPLETE", None, None, False)
    state = states[STAGE_ORDER.index(stage)]
    base = STAGE_ACTION_CODES[stage]
    if state is V2StageState.PENDING:
        code, operator = f"START_{base}", False
    elif state is V2StageState.WAITING_OPERATOR:
        code, operator = f"AWAIT_OPERATOR_{base}", True
    elif state is V2StageState.REVIEW_PENDING:
        code, operator = f"REVIEW_{base}", True
    elif state is V2StageState.BLOCKED:
        code, operator = f"RESOLVE_BLOCK_{base}", True
    elif state is V2StageState.INVALIDATED:
        code, operator = f"REOPEN_INVALIDATED_{base}", True
    elif state is V2StageState.INCIDENT_HOLD:
        code, operator = "INCIDENT_HOLD_READ_ONLY", True
    elif state is V2StageState.SIDE_EFFECT_UNCERTAIN:
        code, operator = "SIDE_EFFECT_UNCERTAIN_RECONCILIATION_ONLY", True
    else:  # pragma: no cover - completed states are skipped
        raise PhysicalOnboardingV2Error("cannot derive a V2 next action")
    return V2NextAction(code, stage, state, operator)


@dataclass(frozen=True, slots=True)
class V2SessionSnapshot:
    header: V2SessionHeader
    stages: tuple[V2StageSnapshot, ...]
    committed_events: tuple[V2JournalEvent, ...]
    uncommitted_events: tuple[V2JournalEvent, ...]
    evidence: tuple[EvidenceReference, ...]
    head: V2CommittedHead
    next_action: V2NextAction

    @property
    def reconciliation_required(self) -> bool:
        return bool(self.uncommitted_events)

    @property
    def mutation_allowed(self) -> bool:
        return not self.reconciliation_required

    @property
    def diagnostic_complete(self) -> bool:
        return (
            self.stages[-1].state is V2StageState.COMPLETE_DIAGNOSTIC
            and not self.reconciliation_required
        )

    def state_for(self, stage: PhysicalOnboardingStage) -> V2StageState:
        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        return self.stages[STAGE_ORDER.index(stage)].state

    def to_verification_dict(self) -> dict[str, Any]:
        return {
            "schema": SESSION_VERIFICATION_SCHEMA_V2,
            "session_schema": SESSION_HEADER_SCHEMA_V2,
            "read_only": self.reconciliation_required,
            "read_only_reason": (
                V2_UNCOMMITTED_SUFFIX if self.reconciliation_required else None
            ),
            "verified_committed_prefix": True,
            "reconciliation_required": self.reconciliation_required,
            "header": self.header.to_dict(),
            "head": self.head.to_dict(),
            "committed_events": [item.to_dict() for item in self.committed_events],
            "uncommitted_suffix": [item.to_dict() for item in self.uncommitted_events],
            "evidence": [item.to_dict() for item in self.evidence],
            "stages": [item.to_dict() for item in self.stages],
            "next_action": self.next_action.to_dict(),
            "diagnostic_complete": self.diagnostic_complete,
            "authority": {
                "device_io_authorized": False,
                "robot_power_authorized": False,
                "motion_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }


def _enumerate_evidence(
    root: Path, header: V2SessionHeader
) -> dict[str, EvidenceReference]:
    _reject_link_chain(root, "V2 evidence root")
    if not root.is_dir():
        raise PhysicalOnboardingV2Error("V2 evidence root must be a real directory")
    entries = _bounded_scandir(
        root,
        maximum_entries=MAX_EVIDENCE_ITEMS,
        label="V2 evidence root",
    )
    result: dict[str, EvidenceReference] = {}
    total = 0
    for entry in entries:
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            raise PhysicalOnboardingV2Error("V2 evidence root contains an unsafe entry")
        reference = _verify_evidence_directory(Path(entry.path), header)
        if reference.evidence_id in result:
            raise PhysicalOnboardingV2Error("duplicate V2 evidence identity")
        total += reference.payload_bytes
        if total > MAX_TOTAL_EVIDENCE_BYTES:
            raise PhysicalOnboardingV2Error("V2 session evidence exceeds total quota")
        result[reference.evidence_id] = reference
    return result


def _event_paths(journal_root: Path) -> list[tuple[int, Path]]:
    _reject_link_chain(journal_root, "V2 journal root")
    if not journal_root.is_dir():
        raise PhysicalOnboardingV2Error("V2 journal root must be a real directory")
    entries = _bounded_scandir(
        journal_root,
        maximum_entries=MAX_JOURNAL_EVENTS + 1,
        label="V2 journal root",
    )
    paths: list[tuple[int, Path]] = []
    head_seen = False
    for entry in entries:
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            raise PhysicalOnboardingV2Error("V2 journal contains an unsafe entry")
        if entry.name == _HEAD_FILENAME:
            if head_seen:
                raise PhysicalOnboardingV2Error("V2 journal contains duplicate heads")
            head_seen = True
            continue
        match = _EVENT_FILENAME.fullmatch(entry.name)
        if match is None:
            raise PhysicalOnboardingV2Error("V2 journal contains an unknown filename")
        paths.append((int(match.group(1)), Path(entry.path)))
    if not head_seen:
        raise PhysicalOnboardingV2Error("V2 committed head is missing")
    paths.sort(key=lambda item: item[0])
    if [sequence for sequence, _ in paths] != list(range(len(paths))):
        raise PhysicalOnboardingV2Error("V2 journal sequence is not contiguous")
    return paths


def load_physical_onboarding_v2_session(directory: Path) -> V2SessionSnapshot:
    """Verify the committed prefix and separately report any durable suffix."""

    root = _safe_directory(directory, "V2 onboarding session")
    entries = _bounded_scandir(
        root,
        maximum_entries=3,
        label="V2 onboarding session",
    )
    if {entry.name for entry in entries} != {"header.json", "journal", "evidence"}:
        raise PhysicalOnboardingV2Error("V2 onboarding session entry set is not exact")
    by_name = {entry.name: entry for entry in entries}
    if (
        by_name["header.json"].is_symlink()
        or not by_name["header.json"].is_file(follow_symlinks=False)
        or by_name["journal"].is_symlink()
        or not by_name["journal"].is_dir(follow_symlinks=False)
        or by_name["evidence"].is_symlink()
        or not by_name["evidence"].is_dir(follow_symlinks=False)
    ):
        raise PhysicalOnboardingV2Error("V2 session contains a link or wrong type")
    header_document, _ = _read_canonical_json(root / "header.json", "V2 session header")
    header = _parse_header(header_document)
    if root.name != f"onboarding-{header.session_id}":
        raise PhysicalOnboardingV2Error("V2 directory does not bind session_id")
    evidence_by_id = _enumerate_evidence(root / "evidence", header)
    head_document, _ = _read_canonical_json(
        root / "journal" / _HEAD_FILENAME, "V2 committed head"
    )
    head = _parse_head(head_document)
    if (
        head.session_id != header.session_id
        or head.session_header_sha256 != header.header_sha256
    ):
        raise PhysicalOnboardingV2Error("V2 head belongs to another session")
    paths = _event_paths(root / "journal")
    if len(paths) < head.event_count:
        raise PhysicalOnboardingV2Error("V2 committed event suffix was deleted")

    states = [V2StageState.PENDING for _ in STAGE_ORDER]
    previous_hash = _ZERO_DIGEST
    previous_time = header.created_at_ns - 1
    parsed: list[V2JournalEvent] = []
    committed_states: list[V2StageState] | None = None
    for sequence, path in paths:
        document, _ = _read_canonical_json(path, f"V2 journal event {sequence}")
        event = _parse_event(document)
        if event.sequence != sequence:
            raise PhysicalOnboardingV2Error("V2 event filename and sequence disagree")
        if (
            event.session_id != header.session_id
            or event.session_header_sha256 != header.header_sha256
        ):
            raise PhysicalOnboardingV2Error("V2 event belongs to another session")
        if event.previous_event_sha256 != previous_hash:
            raise PhysicalOnboardingV2Error("V2 journal event hash chain is broken")
        if event.occurred_at_ns <= previous_time:
            raise PhysicalOnboardingV2Error("V2 event time is not strictly increasing")
        for reference in event.evidence:
            if evidence_by_id.get(reference.evidence_id) != reference:
                raise PhysicalOnboardingV2Error(
                    "V2 event evidence does not match retained evidence"
                )
        _apply_transition(states, event)
        parsed.append(event)
        previous_hash = event.event_sha256
        previous_time = event.occurred_at_ns
        if len(parsed) == head.event_count:
            committed_states = list(states)
    if head.event_count == 0:
        committed_states = [V2StageState.PENDING for _ in STAGE_ORDER]
    assert committed_states is not None
    committed = tuple(parsed[: head.event_count])
    expected_head = V2CommittedHead.build(header, committed)
    if head.to_dict() != expected_head.to_dict():
        raise PhysicalOnboardingV2Error(
            "V2 committed head differs from its event prefix"
        )
    suffix = tuple(parsed[head.event_count :])

    latest_sequences: list[int | None] = [None for _ in STAGE_ORDER]
    evidence_ids: list[list[str]] = [[] for _ in STAGE_ORDER]
    replay_states = [V2StageState.PENDING for _ in STAGE_ORDER]
    for event in committed:
        _apply_transition(replay_states, event)
        index = STAGE_ORDER.index(event.stage)
        latest_sequences[index] = event.sequence
        evidence_ids[index].extend(item.evidence_id for item in event.evidence)
        if event.state is V2StageState.INVALIDATED:
            for downstream in range(index, len(STAGE_ORDER)):
                if replay_states[downstream] not in {
                    V2StageState.INCIDENT_HOLD,
                    V2StageState.SIDE_EFFECT_UNCERTAIN,
                }:
                    latest_sequences[downstream] = event.sequence
    if replay_states != committed_states:
        raise PhysicalOnboardingV2Error("V2 committed state reconstruction differs")
    stages = tuple(
        V2StageSnapshot(
            stage=stage,
            state=replay_states[index],
            last_event_sequence=latest_sequences[index],
            evidence_ids=tuple(evidence_ids[index]),
        )
        for index, stage in enumerate(STAGE_ORDER)
    )
    return V2SessionSnapshot(
        header=header,
        stages=stages,
        committed_events=committed,
        uncommitted_events=suffix,
        evidence=tuple(evidence_by_id[key] for key in sorted(evidence_by_id)),
        head=head,
        next_action=_derive_next_action(replay_states),
    )


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingV2Session:
    """V2 session handle; callers must supply canonical leases around mutation."""

    directory: Path
    publication: SessionPublicationProtocol = PORTABLE_SESSION_PUBLICATION

    def __post_init__(self) -> None:
        if not isinstance(self.publication, SessionPublicationProtocol):
            raise TypeError("publication must implement SessionPublicationProtocol")

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        session_id: str,
        cell_id: str,
        source_binding_sha256: str,
        created_at_ns: int,
        publication: SessionPublicationProtocol = PORTABLE_SESSION_PUBLICATION,
        mode: str = "PHYSICAL_DIAGNOSTIC",
    ) -> "PhysicalOnboardingV2Session":
        session_root = _safe_directory(root, "V2 onboarding root")
        if not isinstance(publication, SessionPublicationProtocol):
            raise TypeError("publication must implement SessionPublicationProtocol")
        publication_mode, qualification_sha256 = _publication_provenance(publication)
        header = V2SessionHeader.build(
            session_id=session_id,
            cell_id=cell_id,
            source_binding_sha256=source_binding_sha256,
            created_at_ns=created_at_ns,
            publication_durability=publication_mode,
            durability_qualification_sha256=qualification_sha256,
            mode=mode,
        )
        destination = _contained_child(
            session_root, f"onboarding-{header.session_id}", "V2 session directory"
        )
        if os.path.lexists(destination):
            raise PhysicalOnboardingV2Error(
                "immutable onboarding session already exists"
            )
        temporary = _contained_child(
            session_root,
            f".partial-v2-onboarding-{header.session_id}-{secrets.token_hex(8)}",
            "partial V2 session directory",
        )
        try:
            temporary.mkdir(exist_ok=False)
            (temporary / "journal").mkdir(exist_ok=False)
            (temporary / "evidence").mkdir(exist_ok=False)
            publication.write_new_file(
                temporary / "header.json", _canonical_bytes(header.to_dict())
            )
            publication.write_new_file(
                temporary / "journal" / _HEAD_FILENAME,
                _canonical_bytes(V2CommittedHead.build(header, ()).to_dict()),
            )
            publication.sync_directory(temporary / "journal")
            publication.sync_directory(temporary / "evidence")
            publication.sync_directory(temporary)
            publication.publish_new_directory(temporary, destination)
            publication.sync_directory(session_root)
        except Exception:
            if temporary.is_dir() and not _is_link_or_reparse(temporary):
                shutil.rmtree(temporary)
            raise
        session = cls(destination, publication)
        session._require_matching_publication(session.snapshot())
        return session

    @classmethod
    def open(
        cls,
        directory: Path,
        *,
        publication: SessionPublicationProtocol = PORTABLE_SESSION_PUBLICATION,
    ) -> "PhysicalOnboardingV2Session":
        session, _ = cls.open_with_snapshot(directory, publication=publication)
        return session

    @classmethod
    def open_with_snapshot(
        cls,
        directory: Path,
        *,
        publication: SessionPublicationProtocol = PORTABLE_SESSION_PUBLICATION,
    ) -> tuple["PhysicalOnboardingV2Session", V2SessionSnapshot]:
        """Return this open's fresh verified snapshot without a second load.

        Nothing is cached on the session. Later snapshot calls still read and
        authenticate the complete original journal and evidence inventory.
        """
        session = cls(_safe_directory(directory, "V2 onboarding session"), publication)
        snapshot = session.snapshot()
        session._require_matching_publication(snapshot)
        return session, snapshot

    @property
    def schema(self) -> str:
        return SESSION_HEADER_SCHEMA_V2

    @property
    def read_only(self) -> bool:
        return self.snapshot().reconciliation_required

    def snapshot(self) -> V2SessionSnapshot:
        snapshot = load_physical_onboarding_v2_session(self.directory)
        self._require_matching_publication(snapshot)
        return snapshot

    def verify(self) -> V2SessionSnapshot:
        return self.snapshot()

    def export_document(self) -> dict[str, Any]:
        """Return a verified, zero-authority representation without writing."""

        snapshot = self.snapshot()
        self._require_matching_publication(snapshot)
        return snapshot.to_verification_dict()

    def export_bytes(self) -> bytes:
        return _canonical_bytes(self.export_document(), maximum=_MAX_EXPORT_BYTES)

    def _require_matching_publication(self, snapshot: V2SessionSnapshot) -> None:
        mode, qualification = _publication_provenance(self.publication)
        if (
            snapshot.header.publication_durability != mode
            or snapshot.header.durability_qualification_sha256 != qualification
        ):
            raise PhysicalOnboardingV2Error(
                "V2 session publication provenance does not match its publisher"
            )

    def _require_mutable_snapshot(self) -> V2SessionSnapshot:
        snapshot = self.snapshot()
        self._require_matching_publication(snapshot)
        if snapshot.reconciliation_required:
            raise V2UncommittedSuffixError(
                f"{V2_UNCOMMITTED_SUFFIX}: reconciliation required before mutation"
            )
        return snapshot

    def store_evidence(
        self,
        stage: PhysicalOnboardingStage,
        payload: bytes,
        *,
        label: str,
        media_type: str,
        captured_at_ns: int,
        expected_head_sha256: str,
    ) -> EvidenceReference:
        """Retain ordinary evidence only after its stage has been opened."""
        return self._store_evidence(
            stage,
            payload,
            label=label,
            media_type=media_type,
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
            pending_entry=False,
        )

    def _store_pending_stage_entry_evidence(
        self,
        stage: PhysicalOnboardingStage,
        payload: bytes,
        *,
        label: str,
        media_type: str,
        captured_at_ns: int,
        expected_head_sha256: str,
    ) -> EvidenceReference:
        """Private file-only primitive for an owner's validated entry record.

        The owner must validate the closed entry document and original reviewed
        predecessor under its stage lease. Retain before the opening event so
        that event can reference the exact immutable package. An interrupted
        entry remains retained but incomplete; this call cannot replay it,
        commit a stage, qualify evidence or authorize a device operation.
        """
        return self._store_evidence(
            stage,
            payload,
            label=label,
            media_type=media_type,
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
            pending_entry=True,
        )

    def _store_camera_probe_review_evidence(
        self,
        payload: bytes,
        *,
        label: str,
        captured_at_ns: int,
        expected_head_sha256: str,
    ) -> EvidenceReference:
        """Private primitive after the M1 owner verifies the exact preparation.

        Only stage five's blocked review can use this branch. This neither
        changes a journal state nor broadens ordinary store_evidence admission.
        """
        return self._store_evidence(
            STAGE_ORDER[4],
            payload,
            label=label,
            media_type="application/json",
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
            pending_entry=False,
            blocked_camera_review=True,
        )

    def _store_evidence(
        self,
        stage: PhysicalOnboardingStage,
        payload: bytes,
        *,
        label: str,
        media_type: str,
        captured_at_ns: int,
        expected_head_sha256: str,
        pending_entry: bool,
        blocked_camera_review: bool = False,
    ) -> EvidenceReference:
        # Both paths share identical bounded, immutable publication and fresh
        # head checks. Only their pre-publication stage conditions differ.
        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        if type(payload) is not bytes or not payload:
            raise PhysicalOnboardingV2Error("evidence payload must be non-empty bytes")
        if len(payload) > MAX_EVIDENCE_BYTES:
            raise PhysicalOnboardingV2Error(
                "evidence payload exceeds the resource limit"
            )
        selected_label = _text(label, "evidence label", maximum=128)
        selected_media_type = _text(media_type, "media_type", maximum=129)
        if _MEDIA_TYPE.fullmatch(selected_media_type) is None:
            raise PhysicalOnboardingV2Error("media_type is invalid")
        captured = _bounded_int(
            captured_at_ns, "captured_at_ns", minimum=1, maximum=2**63 - 1
        )
        expected = _digest(expected_head_sha256, "expected_head_sha256")
        snapshot = self._require_mutable_snapshot()
        if snapshot.head.head_sha256 != expected:
            raise PhysicalOnboardingV2Error("V2 committed head is stale")
        if pending_entry:
            index = STAGE_ORDER.index(stage)
            if (
                snapshot.next_action.stage is not stage
                or snapshot.next_action.stage_state is not V2StageState.PENDING
                or any(
                    row.state is not V2StageState.PENDING
                    or row.evidence_ids
                    or row.last_event_sequence is not None
                    for row in snapshot.stages[index:]
                )
                or any(ref.stage in STAGE_ORDER[index:] for ref in snapshot.evidence)
            ):
                raise PhysicalOnboardingV2Error(
                    "V2 entry requires the empty next pending stage"
                )
            _validate_transition(
                [row.state for row in snapshot.stages],
                stage=stage,
                previous_state=V2StageState.PENDING,
                state=V2StageState.WAITING_OPERATOR,
                evidence=(),
            )
        elif blocked_camera_review:
            if (
                stage is not STAGE_ORDER[4]
                or snapshot.next_action.stage is not stage
                or snapshot.next_action.stage_state is not V2StageState.BLOCKED
            ):
                raise PhysicalOnboardingV2Error(
                    "Camera probe review requires the blocked camera mode stage"
                )
        elif (
            snapshot.next_action.stage is not stage
            or snapshot.next_action.stage_state
            not in {
                V2StageState.WAITING_OPERATOR,
                V2StageState.REVIEW_PENDING,
            }
        ):
            raise PhysicalOnboardingV2Error(
                "V2 evidence may be stored only for the active reviewed stage"
            )
        payload_hash = hashlib.sha256(payload).hexdigest()
        core = _evidence_core(
            header=snapshot.header,
            stage=stage,
            label=selected_label,
            media_type=selected_media_type,
            captured_at_ns=captured,
            payload_sha256=payload_hash,
            payload_bytes=len(payload),
        )
        package_hash = _stable_hash(core)
        evidence_id = f"evidence-{package_hash}"
        manifest = {
            **core,
            "evidence_id": evidence_id,
            "package_sha256": package_hash,
        }
        evidence_root = self.directory / "evidence"
        destination = _contained_child(
            evidence_root, evidence_id, "V2 evidence package"
        )
        if os.path.lexists(destination):
            raise PhysicalOnboardingV2Error("immutable evidence package already exists")
        temporary = _contained_child(
            evidence_root,
            f".partial-{evidence_id}-{secrets.token_hex(8)}",
            "partial V2 evidence package",
        )
        try:
            temporary.mkdir(exist_ok=False)
            self.publication.write_new_file(temporary / "payload.bin", payload)
            # The manifest remains the last file published inside the package.
            self.publication.write_new_file(
                temporary / "manifest.json", _canonical_bytes(manifest)
            )
            self.publication.sync_directory(temporary)
            self.publication.publish_new_directory(temporary, destination)
            self.publication.sync_directory(evidence_root)
        except Exception:
            if temporary.is_dir() and not _is_link_or_reparse(temporary):
                shutil.rmtree(temporary)
            raise
        reference = _verify_evidence_directory(destination, snapshot.header)
        # The journal head cannot change without a caller violating the required
        # session lease. Detect that violation instead of silently succeeding.
        rechecked = self._require_mutable_snapshot()
        if rechecked.head.head_sha256 != expected:
            raise PhysicalOnboardingV2Error(
                "V2 committed head changed while evidence was being published"
            )
        return reference

    def commit_stage_state(
        self,
        stage: PhysicalOnboardingStage,
        state: V2StageState,
        *,
        occurred_at_ns: int,
        detail_code: str,
        expected_head_sha256: str,
        evidence: Sequence[EvidenceReference] = (),
    ) -> V2SessionSnapshot:
        if not isinstance(stage, PhysicalOnboardingStage):
            raise TypeError("stage must be PhysicalOnboardingStage")
        if state == "ACQUIRING":
            raise PhysicalOnboardingV2Error(
                "ACQUIRING is forbidden in V2 stage journals"
            )
        if not isinstance(state, V2StageState):
            raise TypeError("state must be V2StageState")
        occurred = _bounded_int(
            occurred_at_ns, "occurred_at_ns", minimum=1, maximum=2**63 - 1
        )
        code = _detail_code(detail_code)
        expected = _digest(expected_head_sha256, "expected_head_sha256")
        if isinstance(evidence, (str, bytes)):
            raise PhysicalOnboardingV2Error("evidence must be a reference sequence")
        retained = tuple(evidence)
        if len(retained) > MAX_EVENT_EVIDENCE_ITEMS:
            raise PhysicalOnboardingV2Error("V2 event references too much evidence")
        if any(not isinstance(item, EvidenceReference) for item in retained):
            raise TypeError("evidence must contain EvidenceReference values")
        if len({item.evidence_id for item in retained}) != len(retained):
            raise PhysicalOnboardingV2Error("V2 event repeats an evidence reference")

        current = self._require_mutable_snapshot()
        if current.head.head_sha256 != expected:
            raise PhysicalOnboardingV2Error("V2 committed head is stale")
        if len(current.committed_events) >= MAX_JOURNAL_EVENTS:
            raise PhysicalOnboardingV2Error("V2 journal has reached its event limit")
        previous_time = (
            current.header.created_at_ns
            if not current.committed_events
            else current.committed_events[-1].occurred_at_ns
        )
        if occurred <= previous_time:
            raise PhysicalOnboardingV2Error("V2 event time must be strictly increasing")
        evidence_by_id = {item.evidence_id: item for item in current.evidence}
        for reference in retained:
            if evidence_by_id.get(reference.evidence_id) != reference:
                raise PhysicalOnboardingV2Error(
                    "V2 event references unverified evidence"
                )
        states = [item.state for item in current.stages]
        previous_state = states[STAGE_ORDER.index(stage)]
        _validate_transition(
            states,
            stage=stage,
            previous_state=previous_state,
            state=state,
            evidence=retained,
        )
        sequence = len(current.committed_events)
        previous_hash = (
            _ZERO_DIGEST
            if not current.committed_events
            else current.committed_events[-1].event_sha256
        )
        event = V2JournalEvent.build(
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
        event_path = _contained_child(
            self.directory / "journal",
            f"event-{sequence:06d}.json",
            "V2 journal event",
        )
        self.publication.write_new_file(event_path, _canonical_bytes(event.to_dict()))
        self.publication.sync_directory(self.directory / "journal")
        next_head = V2CommittedHead.build(
            current.header, (*current.committed_events, event)
        )
        self.publication.replace_file(
            self.directory / "journal" / _HEAD_FILENAME,
            _canonical_bytes(next_head.to_dict()),
        )
        self.publication.sync_directory(self.directory / "journal")
        return self.snapshot()

    def invalidate_from(
        self,
        stage: PhysicalOnboardingStage,
        *,
        occurred_at_ns: int,
        detail_code: str,
        expected_head_sha256: str,
        evidence: Sequence[EvidenceReference] = (),
    ) -> V2SessionSnapshot:
        return self.commit_stage_state(
            stage,
            V2StageState.INVALIDATED,
            occurred_at_ns=occurred_at_ns,
            detail_code=detail_code,
            expected_head_sha256=expected_head_sha256,
            evidence=evidence,
        )


@dataclass(frozen=True, slots=True)
class LegacyV1ReadOnlySession:
    """Strict V1 verification compatibility with no mutation surface."""

    directory: Path

    def __post_init__(self) -> None:
        load_physical_onboarding_session(self.directory)

    @property
    def schema(self) -> str:
        return LEGACY_V1_HEADER_SCHEMA

    @property
    def read_only(self) -> bool:
        return True

    def snapshot(self) -> Any:
        return load_physical_onboarding_session(self.directory)

    def verify(self) -> Any:
        return self.snapshot()

    def export_document(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        high_water, _ = _read_canonical_json(
            self.directory / "journal" / "high-water.json",
            "legacy V1 high-water",
        )
        action = snapshot.next_action
        return {
            "schema": LEGACY_VERIFICATION_SCHEMA,
            "session_schema": LEGACY_V1_HEADER_SCHEMA,
            "read_only": True,
            "read_only_reason": LEGACY_V1_READ_ONLY,
            "verified": True,
            "header": snapshot.header.to_dict(),
            "high_water": high_water,
            "events": [item.to_dict() for item in snapshot.events],
            "evidence": [item.to_dict() for item in snapshot.evidence],
            "stages": [
                {
                    "stage": item.stage.value,
                    "state": item.state.value,
                    "last_event_sequence": item.last_event_sequence,
                    "evidence_ids": list(item.evidence_ids),
                }
                for item in snapshot.stages
            ],
            "next_action": {
                "code": action.code,
                "stage": None if action.stage is None else action.stage.value,
                "stage_state": (
                    None if action.stage_state is None else action.stage_state.value
                ),
                "operator_required": action.operator_required,
            },
            "authority": {
                "device_io_authorized": False,
                "robot_power_authorized": False,
                "motion_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }

    def export_bytes(self) -> bytes:
        return _canonical_bytes(self.export_document(), maximum=_MAX_EXPORT_BYTES)

    @staticmethod
    def _reject_mutation() -> None:
        raise LegacyV1ReadOnlyError(
            f"{LEGACY_V1_READ_ONLY}: legacy sessions are verify/export-only"
        )

    def store_evidence(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._reject_mutation()

    def commit_stage_state(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._reject_mutation()

    def invalidate_from(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._reject_mutation()

    def reconcile(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._reject_mutation()


CompatibleOnboardingSession = PhysicalOnboardingV2Session | LegacyV1ReadOnlySession


def open_onboarding_session(
    directory: Path,
    *,
    publication: SessionPublicationProtocol = PORTABLE_SESSION_PUBLICATION,
) -> CompatibleOnboardingSession:
    """Dispatch by immutable header schema; V1 is always read-only here."""

    root = _safe_directory(directory, "physical onboarding session")
    header, _ = _read_canonical_json(root / "header.json", "session header")
    schema = header.get("schema")
    if schema == SESSION_HEADER_SCHEMA_V2:
        return PhysicalOnboardingV2Session.open(root, publication=publication)
    if schema == LEGACY_V1_HEADER_SCHEMA:
        return LegacyV1ReadOnlySession(root)
    raise PhysicalOnboardingV2Error(
        f"unsupported physical onboarding schema {schema!r}"
    )


def verify_onboarding_session(directory: Path) -> dict[str, Any]:
    """Zero-I/O schema-dispatched verification representation."""

    return open_onboarding_session(directory).export_document()


__all__ = [
    "LEGACY_V1_READ_ONLY",
    "LEGACY_V1_HEADER_SCHEMA",
    "PORTABLE_SESSION_PUBLICATION",
    "PORTABLE_UNQUALIFIED",
    "SESSION_EVENT_SCHEMA_V2",
    "SESSION_HEADER_SCHEMA_V2",
    "SESSION_HEAD_SCHEMA_V2",
    "SESSION_VERIFICATION_SCHEMA_V2",
    "V2_UNCOMMITTED_SUFFIX",
    "WINDOWS_NTFS_QUALIFIED",
    "CompatibleOnboardingSession",
    "LegacyV1ReadOnlyError",
    "LegacyV1ReadOnlySession",
    "PhysicalOnboardingV2Error",
    "PhysicalOnboardingV2Session",
    "PortableSessionPublication",
    "SessionPublicationProtocol",
    "V2CommittedHead",
    "V2JournalEvent",
    "V2NextAction",
    "V2SessionHeader",
    "V2SessionSnapshot",
    "V2StageSnapshot",
    "V2StageState",
    "V2UncommittedSuffixError",
    "load_physical_onboarding_v2_session",
    "open_onboarding_session",
    "verify_onboarding_session",
]
