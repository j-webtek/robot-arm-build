"""Load retained camera/support originals into the ARM-070 binding contract.

The adapter performs bounded file reads and content/lineage validation only.
It does not collect evidence, open a camera, approve a review, advance an epoch,
or grant hardware authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .camera_support_optics_epoch_intake_v1 import (
    REQUIRED_BINDINGS,
    BindingReviewDisposition,
    CameraSupportBindingV1,
)
from .installed_controller_qualification_v1 import EvidenceOrigin
from .physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
    contained_path,
    read_bounded_regular_file,
    safe_root,
)


REVIEW_SCHEMA = "rocell.camera_support_original_owner_ai_review.v1"
RECEIPT_SCHEMA = "rocell.camera_support_binding_adapter_receipt.v1"
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_REVIEW_BYTES = 128 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")


class CameraSupportBindingAdapterError(ValueError):
    """A retained original or its owner-AI review is unsafe or inconsistent."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CameraSupportBindingAdapterError(
            "camera/support review is not canonical JSON") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_json(raw: bytes) -> dict[str, Any]:
    def no_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CameraSupportBindingAdapterError(
                    f"duplicate owner-AI review field {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=no_duplicates,
            parse_constant=lambda item: (_ for _ in ()).throw(
                CameraSupportBindingAdapterError(
                    f"nonfinite review constant {item!r}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CameraSupportBindingAdapterError(
            "owner-AI review must be UTF-8 JSON") from exc
    if type(value) is not dict:
        raise CameraSupportBindingAdapterError(
            "owner-AI review must be a JSON object")
    return value


def _positive(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CameraSupportBindingAdapterError(
            f"{label} must be a positive integer")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise CameraSupportBindingAdapterError(
            f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CameraSupportBindingAdapterError(
            f"{label} must be a SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class CameraSupportOriginalReviewV1:
    review_id: str
    binding_id: str
    evidence_relative_path: str
    evidence_sha256: str
    measured_monotonic_ns: int
    valid_until_monotonic_ns: int
    owner_ai_reviewer_id: str
    limitations: tuple[str, ...]
    schema: str = REVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REVIEW_SCHEMA:
            raise CameraSupportBindingAdapterError("unsupported review schema")
        _identifier(self.review_id, "review_id")
        _identifier(self.owner_ai_reviewer_id, "owner_ai_reviewer_id")
        if self.binding_id not in REQUIRED_BINDINGS:
            raise CameraSupportBindingAdapterError("unknown binding_id")
        if (not isinstance(self.evidence_relative_path, str)
                or not self.evidence_relative_path):
            raise CameraSupportBindingAdapterError(
                "evidence_relative_path must be nonempty")
        _digest(self.evidence_sha256, "evidence_sha256")
        measured = _positive(self.measured_monotonic_ns, "measured_monotonic_ns")
        valid_until = _positive(
            self.valid_until_monotonic_ns, "valid_until_monotonic_ns")
        if valid_until <= measured:
            raise CameraSupportBindingAdapterError(
                "review validity window is invalid")
        if not isinstance(self.limitations, (list, tuple)):
            raise CameraSupportBindingAdapterError(
                "review limitations must be a sequence")
        limitations = tuple(self.limitations)
        if (not limitations or len(limitations) > 16
                or any(not isinstance(item, str) or not item or len(item) > 512
                       for item in limitations)):
            raise CameraSupportBindingAdapterError(
                "review limitations must be bounded nonempty strings")
        object.__setattr__(self, "limitations", limitations)

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "OWNER_AI_ACCEPTED_PHYSICAL_RETAINED_ORIGINAL",
            "review_id": self.review_id,
            "binding_id": self.binding_id,
            "evidence_relative_path": self.evidence_relative_path,
            "evidence_sha256": self.evidence_sha256,
            "measured_monotonic_ns": self.measured_monotonic_ns,
            "valid_until_monotonic_ns": self.valid_until_monotonic_ns,
            "evidence_origin": "PHYSICAL_RETAINED_ORIGINALS",
            "review_disposition": "OWNER_AI_ACCEPTED",
            "owner_ai_reviewer_id": self.owner_ai_reviewer_id,
            "limitations": list(self.limitations),
            "human_review_claimed": False,
            "external_independence_claimed": False,
            "camera_open_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def review_sha256(self) -> str:
        return _sha256(_canonical(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "review_sha256": self.review_sha256}


@dataclass(frozen=True, slots=True)
class CameraSupportBindingAdapterReceiptV1:
    evidence_root_sha256: str
    evidence_relative_path: str
    evidence_file_sha256: str
    review_relative_path: str
    review_file_sha256: str
    review: CameraSupportOriginalReviewV1
    binding: CameraSupportBindingV1
    schema: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RECEIPT_SCHEMA:
            raise CameraSupportBindingAdapterError("unsupported receipt schema")
        for field in (
            "evidence_root_sha256", "evidence_file_sha256", "review_file_sha256",
        ):
            _digest(getattr(self, field), field)
        if not self.evidence_relative_path or not self.review_relative_path:
            raise CameraSupportBindingAdapterError(
                "receipt paths must be nonempty")
        if self.evidence_relative_path != self.review.evidence_relative_path:
            raise CameraSupportBindingAdapterError(
                "receipt and review evidence paths differ")
        if self.evidence_file_sha256 != self.review.evidence_sha256:
            raise CameraSupportBindingAdapterError(
                "receipt and review evidence hashes differ")
        if self.review.binding_id != self.binding.binding_id:
            raise CameraSupportBindingAdapterError(
                "review and binding identities differ")
        if self.review.evidence_sha256 != self.binding.evidence_sha256:
            raise CameraSupportBindingAdapterError(
                "review and binding evidence differ")
        if self.review.review_sha256 != self.binding.owner_ai_review_sha256:
            raise CameraSupportBindingAdapterError(
                "review and binding review hashes differ")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "BOUND_FOR_ARM070_INTAKE",
            "evidence_root_sha256": self.evidence_root_sha256,
            "evidence_relative_path": self.evidence_relative_path,
            "evidence_file_sha256": self.evidence_file_sha256,
            "review_relative_path": self.review_relative_path,
            "review_file_sha256": self.review_file_sha256,
            "owner_ai_review_sha256": self.review.review_sha256,
            "binding": self.binding.to_dict(),
            "epoch_advanced": False,
            "camera_open_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _sha256(_canonical(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "receipt_sha256": self.receipt_sha256}


def parse_camera_support_original_review_v1(
    document: Mapping[str, Any],
) -> CameraSupportOriginalReviewV1:
    if type(document) is not dict:
        raise CameraSupportBindingAdapterError("review must be a plain object")
    sample = CameraSupportOriginalReviewV1(
        review_id="sample", binding_id=REQUIRED_BINDINGS[0],
        evidence_relative_path="sample.bin", evidence_sha256="0" * 64,
        measured_monotonic_ns=1, valid_until_monotonic_ns=2,
        owner_ai_reviewer_id="sample", limitations=("sample",),
    ).to_dict()
    if set(document) != set(sample):
        raise CameraSupportBindingAdapterError(
            "review fields differ from the closed contract")
    constants = {
        "status": "OWNER_AI_ACCEPTED_PHYSICAL_RETAINED_ORIGINAL",
        "evidence_origin": "PHYSICAL_RETAINED_ORIGINALS",
        "review_disposition": "OWNER_AI_ACCEPTED",
        "human_review_claimed": False,
        "external_independence_claimed": False,
        "camera_open_authorized": False,
        "controller_start_authorized": False,
        "transport_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
    }
    if any(document.get(key) != value for key, value in constants.items()):
        raise CameraSupportBindingAdapterError(
            "review provenance, disposition, or authority differs")
    if type(document["limitations"]) is not list:
        raise CameraSupportBindingAdapterError(
            "review limitations must be a JSON array")
    review = CameraSupportOriginalReviewV1(
        review_id=document["review_id"],
        binding_id=document["binding_id"],
        evidence_relative_path=document["evidence_relative_path"],
        evidence_sha256=document["evidence_sha256"],
        measured_monotonic_ns=document["measured_monotonic_ns"],
        valid_until_monotonic_ns=document["valid_until_monotonic_ns"],
        owner_ai_reviewer_id=document["owner_ai_reviewer_id"],
        limitations=tuple(document["limitations"]), schema=document["schema"],
    )
    if document["review_sha256"] != review.review_sha256:
        raise CameraSupportBindingAdapterError("review hash differs")
    return review


def load_camera_support_binding_v1(
    evidence_root: Path, *, review_relative_path: str,
) -> CameraSupportBindingAdapterReceiptV1:
    """Load one already-retained original and its accepted owner-AI review."""
    try:
        root = safe_root(evidence_root, label="camera/support evidence root")
        review_path = contained_path(
            root, review_relative_path, label="camera/support review path")
        review_raw = read_bounded_regular_file(
            review_path, maximum_bytes=MAX_REVIEW_BYTES,
            label="camera/support owner-AI review")
        review = parse_camera_support_original_review_v1(_strict_json(review_raw))
        evidence_path = contained_path(
            root, review.evidence_relative_path,
            label="camera/support evidence path")
        evidence_raw = read_bounded_regular_file(
            evidence_path, maximum_bytes=MAX_EVIDENCE_BYTES,
            label="camera/support retained original")
    except PhysicalOnboardingDurabilityError as exc:
        raise CameraSupportBindingAdapterError(str(exc)) from exc
    evidence_sha256 = _sha256(evidence_raw)
    if evidence_sha256 != review.evidence_sha256:
        raise CameraSupportBindingAdapterError(
            "retained original differs from the accepted review")
    binding = CameraSupportBindingV1(
        binding_id=review.binding_id,
        evidence_sha256=evidence_sha256,
        owner_ai_review_sha256=review.review_sha256,
        measured_monotonic_ns=review.measured_monotonic_ns,
        valid_until_monotonic_ns=review.valid_until_monotonic_ns,
        evidence_origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
        review_disposition=BindingReviewDisposition.OWNER_AI_ACCEPTED,
    )
    return CameraSupportBindingAdapterReceiptV1(
        evidence_root_sha256=_sha256(str(root).encode("utf-8")),
        evidence_relative_path=review.evidence_relative_path,
        evidence_file_sha256=evidence_sha256,
        review_relative_path=review_relative_path,
        review_file_sha256=_sha256(review_raw),
        review=review,
        binding=binding,
    )


def load_camera_support_bindings_v1(
    evidence_root: Path, *, review_relative_paths: Sequence[str],
) -> tuple[CameraSupportBindingAdapterReceiptV1, ...]:
    receipts = tuple(load_camera_support_binding_v1(
        evidence_root, review_relative_path=path)
        for path in review_relative_paths)
    ids = tuple(item.binding.binding_id for item in receipts)
    if ids != REQUIRED_BINDINGS:
        raise CameraSupportBindingAdapterError(
            "review files must cover all four bindings in canonical order")
    return receipts


__all__ = [
    "MAX_EVIDENCE_BYTES", "MAX_REVIEW_BYTES", "RECEIPT_SCHEMA", "REVIEW_SCHEMA",
    "CameraSupportBindingAdapterError", "CameraSupportBindingAdapterReceiptV1",
    "CameraSupportOriginalReviewV1", "load_camera_support_binding_v1",
    "load_camera_support_bindings_v1", "parse_camera_support_original_review_v1",
]
