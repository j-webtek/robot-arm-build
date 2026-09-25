"""Immutable calibration artifact and assessment models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_FIELDS = frozenset(
    {
        "schema",
        "artifact_id",
        "version",
        "state",
        "created_utc",
        "manifest_id",
        "active_build_id",
        "dependency_hashes",
        "parent_artifact_hashes",
        "payload",
    }
)


class ArtifactState(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    FAILED_GATE = "FAILED_GATE"
    NOMINAL_ONLY = "NOMINAL_ONLY"
    STALE_DEPENDENCY = "STALE_DEPENDENCY"


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must match {_IDENTIFIER.pattern}")
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        # Canonical serialization below rejects NaN/Infinity.
        json.dumps(value, allow_nan=False)
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Calibration JSON object keys must be strings")
            result[key] = _freeze_json(item)
        return MappingProxyType(result)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError(f"Calibration artifact contains unsupported {type(value).__name__}")


def _hash_mapping(value: object, name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a JSON object")
    return MappingProxyType(
        {
            _identifier(key, f"{name} id"): _sha256(digest, f"{name} hash")
            for key, digest in value.items()
        }
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class CalibrationArtifact:
    artifact_id: str
    version: int
    state: ArtifactState
    created_utc: str
    manifest_id: str
    active_build_id: str
    dependency_hashes: Mapping[str, str]
    parent_artifact_hashes: Mapping[str, str]
    payload: Mapping[str, Any]
    schema: str = "rocell.calibration_artifact.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _identifier(self.artifact_id, "artifact_id"))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        if not isinstance(self.state, ArtifactState):
            object.__setattr__(self, "state", ArtifactState(self.state))
        if not isinstance(self.created_utc, str):
            raise TypeError("created_utc must be an ISO-8601 string")
        try:
            timestamp = datetime.fromisoformat(self.created_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_utc must be a valid ISO-8601 timestamp") from exc
        utc_offset = timestamp.utcoffset()
        if utc_offset is None or utc_offset.total_seconds() != 0:
            raise ValueError("created_utc must include a UTC offset")
        if not isinstance(self.manifest_id, str) or not self.manifest_id:
            raise ValueError("manifest_id must be a non-empty string")
        if not isinstance(self.active_build_id, str) or not self.active_build_id:
            raise ValueError("active_build_id must be a non-empty string")
        dependencies = _hash_mapping(self.dependency_hashes, "dependency")
        parents = _hash_mapping(self.parent_artifact_hashes, "parent artifact")
        if self.artifact_id in parents:
            raise ValueError("A calibration artifact cannot name itself as a parent")
        object.__setattr__(self, "dependency_hashes", dependencies)
        object.__setattr__(self, "parent_artifact_hashes", parents)
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a JSON object")
        object.__setattr__(self, "payload", _freeze_json(self.payload))
        if self.schema != "rocell.calibration_artifact.v1":
            raise ValueError("Unsupported calibration artifact schema")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "artifact_id": self.artifact_id,
            "version": self.version,
            "state": self.state.value,
            "created_utc": self.created_utc,
            "manifest_id": self.manifest_id,
            "active_build_id": self.active_build_id,
            "dependency_hashes": dict(sorted(self.dependency_hashes.items())),
            "parent_artifact_hashes": dict(sorted(self.parent_artifact_hashes.items())),
            "payload": _thaw_json(self.payload),
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "CalibrationArtifact":
        if not isinstance(document, Mapping):
            raise TypeError("Calibration artifact document must be a JSON object")
        actual_fields = frozenset(document)
        if actual_fields != _ARTIFACT_FIELDS:
            missing = tuple(sorted(_ARTIFACT_FIELDS - actual_fields))
            unexpected = tuple(sorted(actual_fields - _ARTIFACT_FIELDS))
            raise ValueError(
                "Calibration artifact fields differ from the exact schema: "
                f"missing={missing}, unexpected={unexpected}"
            )
        return cls(
            schema=document["schema"],
            artifact_id=document["artifact_id"],
            version=document["version"],
            state=document["state"],
            created_utc=document["created_utc"],
            manifest_id=document["manifest_id"],
            active_build_id=document["active_build_id"],
            dependency_hashes=document["dependency_hashes"],
            parent_artifact_hashes=document["parent_artifact_hashes"],
            payload=document["payload"],
        )

    @property
    def content_hash(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactAssessment:
    artifact_id: str
    state: ArtifactState
    artifact_hash: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate assessment evidence at its construction boundary.

        Assessments are accepted by safety code, so they must not be loose
        caller-authored bags of values.  In particular, a ``VALID`` state is
        meaningful only when it names the same well-formed artifact ID used by
        the resolution, carries a real content digest, and has no blockers.
        """

        object.__setattr__(
            self, "artifact_id", _identifier(self.artifact_id, "artifact_id")
        )
        if not isinstance(self.state, ArtifactState):
            object.__setattr__(self, "state", ArtifactState(self.state))

        if self.artifact_hash is None:
            if self.state is not ArtifactState.MISSING:
                raise ValueError(
                    "Only a MISSING artifact assessment may omit artifact_hash"
                )
        else:
            _sha256(self.artifact_hash, "artifact_hash")
            if self.state is ArtifactState.MISSING:
                raise ValueError(
                    "A MISSING artifact assessment cannot carry artifact_hash"
                )

        if not isinstance(self.reasons, (tuple, list)):
            raise TypeError("reasons must be a tuple or list of diagnostic strings")
        reasons = tuple(self.reasons)
        if any(
            not isinstance(reason, str)
            or not reason
            or reason != reason.strip()
            or len(reason) > 512
            for reason in reasons
        ):
            raise ValueError("reasons must contain bounded, trimmed, non-empty text")
        if len(set(reasons)) != len(reasons):
            raise ValueError("reasons cannot contain duplicate diagnostics")
        if self.state is ArtifactState.VALID and reasons:
            raise ValueError("A VALID artifact assessment cannot carry reasons")
        if self.state is not ArtifactState.VALID and not reasons:
            raise ValueError("A non-VALID artifact assessment requires a reason")
        object.__setattr__(self, "reasons", reasons)

    @property
    def valid(self) -> bool:
        return self.state is ArtifactState.VALID and not self.reasons


@dataclass(frozen=True, slots=True)
class CalibrationResolution:
    assessments: Mapping[str, ArtifactAssessment]

    def __post_init__(self) -> None:
        if not isinstance(self.assessments, Mapping):
            raise TypeError("assessments must be a mapping")
        copied: dict[str, ArtifactAssessment] = {}
        for key, assessment in self.assessments.items():
            validated_key = _identifier(key, "assessment key")
            if not isinstance(assessment, ArtifactAssessment):
                raise TypeError("assessments must contain ArtifactAssessment values")
            if assessment.artifact_id != validated_key:
                raise ValueError(
                    "Calibration resolution key must equal assessment artifact_id"
                )
            copied[validated_key] = assessment
        object.__setattr__(
            self,
            "assessments",
            MappingProxyType(dict(sorted(copied.items()))),
        )

    @property
    def all_valid(self) -> bool:
        # An empty resolution proves nothing and must not satisfy motion
        # preflight through Python's otherwise-vacuous ``all([])`` result.
        return bool(self.assessments) and all(
            assessment.valid for assessment in self.assessments.values()
        )

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(
            reason
            for assessment in self.assessments.values()
            for reason in assessment.reasons
        )
