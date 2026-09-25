"""Exact reviewed reference lineage for the zero-authority NC-01 gap report."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from .rehearsal_reference_binding import RehearsalReferenceBinding

SCHEMA = "rocell.rehearsal_noncontact_binding.v1"
SOURCE_SCHEMA = "rocell.rehearsal_noncontact_sources.v1"
MAX_SOURCE_CONTEXT_BYTES = 32 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value: object) -> str:
    if type(value) is not str or not _HASH.fullmatch(value) or value == "0" * 64:
        raise ValueError("An exact nonzero SHA-256 is required")
    return value


@dataclass(frozen=True, slots=True)
class RehearsalNoncontactBinding:
    reference_binding: RehearsalReferenceBinding
    operator_id: str
    predecessor_receipt_sha256: str
    predecessor_assessment_sha256: str
    predecessor_review_sha256: str
    reference_evidence_sha256: str
    source_context_json: bytes
    _reference_payload: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.reference_binding) is not RehearsalReferenceBinding:
            raise ValueError(
                "The exact independently reviewed reference binding is required"
            )
        self.reference_binding.__post_init__()
        reference = canonical(self.reference_binding.to_dict())
        if hasattr(self, "_reference_payload") and self._reference_payload != reference:
            raise ValueError("The original reference binding changed")
        object.__setattr__(self, "_reference_payload", reference)
        if type(self.operator_id) is not str or not _ACTOR.fullmatch(self.operator_id):
            raise ValueError("A bounded diagnostic operator is required")
        for name in (
            "predecessor_receipt_sha256",
            "predecessor_assessment_sha256",
            "predecessor_review_sha256",
            "reference_evidence_sha256",
        ):
            digest(getattr(self, name))
        if type(self.source_context_json) is not bytes or not (
            0 < len(self.source_context_json) <= MAX_SOURCE_CONTEXT_BYTES
        ):
            raise ValueError("A bounded immutable NC-01 source snapshot is required")
        context = json.loads(self.source_context_json)
        if (
            type(context) is not dict
            or set(context)
            != {
                "schema",
                "reference_source_context_sha256",
                "historical_context",
                "scene",
                "accuracy_policy_utf8",
                "accuracy_policy_sha256",
                "dependency_source_sha256s",
            }
            or context["schema"] != SOURCE_SCHEMA
            or canonical(context) != self.source_context_json
        ):
            raise ValueError(
                "The NC-01 source snapshot schema/canonical encoding changed"
            )
        if (
            context["reference_source_context_sha256"]
            != hashlib.sha256(self.reference_binding.source_context_json).hexdigest()
        ):
            raise ValueError("NC-01 and the reviewed reference source context differ")
        if type(context["accuracy_policy_utf8"]) is not str or hashlib.sha256(
            context["accuracy_policy_utf8"].encode("utf-8")
        ).hexdigest() != digest(context["accuracy_policy_sha256"]):
            raise ValueError("The retained policy byte hash differs")
        if (
            type(context["historical_context"]) is not dict
            or type(context["scene"]) is not dict
        ):
            raise ValueError(
                "Complete historical context and scene inputs are required"
            )
        dependencies = context["dependency_source_sha256s"]
        if type(dependencies) is not dict or not 1 <= len(dependencies) <= 16:
            raise ValueError("The closed implementation source identities are required")
        for key, value in dependencies.items():
            if type(key) is not str or not 0 < len(key) <= 128:
                raise ValueError("Invalid implementation source name")
            digest(value)

    @property
    def workspace_source_sha256(self) -> str:
        return json.loads(self._reference_payload)["workspace_source_sha256"]

    @property
    def catalog_sha256(self) -> str:
        return json.loads(self._reference_payload)["catalog_sha256"]

    @property
    def cell_id(self) -> str:
        return json.loads(self._reference_payload)["cell_id"]

    @property
    def session_id(self) -> str:
        return json.loads(self._reference_payload)["session_id"]

    @property
    def source_context(self) -> dict[str, Any]:
        return json.loads(self.source_context_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "stage": "noncontact_acceptance",
            "reference_binding": json.loads(self._reference_payload),
            "operator_id": self.operator_id,
            "predecessor_receipt_sha256": self.predecessor_receipt_sha256,
            "predecessor_assessment_sha256": self.predecessor_assessment_sha256,
            "predecessor_review_sha256": self.predecessor_review_sha256,
            "reference_evidence_sha256": self.reference_evidence_sha256,
            "source_context": self.source_context,
            "composition": "HARDWARE_INCAPABLE_REHEARSAL",
            "physical_authority": False,
        }

    @property
    def binding_sha256(self) -> str:
        return hashlib.sha256(canonical(self.to_dict())).hexdigest()
