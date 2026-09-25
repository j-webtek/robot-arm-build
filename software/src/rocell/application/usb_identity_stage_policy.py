"""Closed stage-4 amendment and identity subjects; inert, not device permission.

Only the separate USB coordinator interprets this successor. Historical stage
catalog readers and camera capture permits keep their existing meaning. These
codecs validate bytes; the application must authenticate their original M1
references before deriving admission facts from them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .physical_onboarding import PhysicalOnboardingStage, _parse_evidence_reference
from .physical_onboarding_stage_catalog import load_physical_onboarding_stage_catalog
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest

POLICY_SCHEMA = "rocell.usb_identity_stage_policy.v1"
IDENTITY_SCHEMA = "rocell.usb_identity_admission_identity.v1"
REVIEW_SCHEMA = "rocell.usb_identity_stage_policy_review.v1"
POLICY_ACTION = "physical-native-usb-identity"
POLICY_COMPOSITION = "PHYSICAL_DIAGNOSTIC_USB_IDENTITY"
CATALOG_SHA256 = "5cfd61200815afcf1c3568e9eb312d8d2ae9176a85d446930b29322a962ddd3a"
STAGE_ORDER_SHA256 = "b42056193766d48d13e94ec11f9697c03bb989acb578c8437d565af6801a3746"
MAX_POLICY_BYTES = 8 * 1024
MAX_IDENTITY_BYTES = 12 * 1024
MAX_REVIEW_BYTES = 8 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
    motion_authorized=False,
    contact_authorized=False,
)


class UsbIdentityPolicyError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise UsbIdentityPolicyError(code)


def _sha(value: Any) -> None:
    _require(type(value) is str and bool(_SHA.fullmatch(value)), "INVALID_SHA256")


def _read(payload: bytes, maximum: int) -> dict[str, Any]:
    _require(type(payload) is bytes, "EXACT_BYTES_REQUIRED")
    try:
        document = decode_owned_json(payload, maximum=maximum)
        _require(canonical(document) == payload, "CANONICAL_PAYLOAD_REQUIRED")
        return document
    except UsbIdentityPolicyError:
        raise
    except (ValueError, TypeError, RecursionError) as exc:
        raise UsbIdentityPolicyError("INVALID_POLICY_PAYLOAD") from exc


def _policy_document() -> dict[str, Any]:
    # Return a new object each time: callers cannot mutate the executable rule.
    return dict(
        schema=POLICY_SCHEMA,
        policy_id="ROCELL-STAGE4-USB-IDENTITY-001",
        revision=1,
        meaning="EXACT_QUERY_ADMISSION_AMENDMENT_NOT_QUALIFICATION",
        base_catalog_schema="rocell.physical_onboarding_stage_catalog.v2",
        base_catalog_revision=3,
        base_catalog_sha256=CATALOG_SHA256,
        canonical_stage_order_sha256=STAGE_ORDER_SHA256,
        stage=PhysicalOnboardingStage.CAMERA_IDENTITY.value,
        composition=POLICY_COMPOSITION,
        action_id=POLICY_ACTION,
        effect_class="BOUNDED_CAMERA_CAMPAIGN",
        leases=["CELL", "SESSION", "CAMERA"],
        budget=dict(
            timeout_ms=25000,
            maximum_output_bytes=128 * 1024,
            maximum_opens=32,
            maximum_reads=128,
            maximum_writes=0,
            maximum_frames=0,
            maximum_closes=32,
        ),
        query_scope="SELECTED_CAMERA_USB_DESCRIPTORS_AND_PARENT_MAPPING_ONLY",
        original_review_required=True,
        durable_consumed_permit_required=True,
        retained_owned_execution_required=True,
        automatic_retry_allowed=False,
        historical_catalog_modified=False,
        **_FLAGS,
    )


@dataclass(frozen=True, slots=True)
class UsbIdentityStagePolicy:
    payload: bytes

    def __post_init__(self) -> None:
        document = _read(self.payload, MAX_POLICY_BYTES)
        # Canonical bytes, not Python equality (which equates True and 1).
        _require(
            self.payload == canonical(_policy_document()), "EXACT_USB_POLICY_REQUIRED"
        )
        _require(document["schema"] == POLICY_SCHEMA, "EXACT_USB_POLICY_REQUIRED")

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _read(self.payload, MAX_POLICY_BYTES)


def usb_identity_stage_policy() -> UsbIdentityStagePolicy:
    """Pure fixed subject for inspection. Does not inspect or approve a build."""
    return UsbIdentityStagePolicy(canonical(_policy_document()))


def inspect_usb_identity_stage_policy(workspace: Path) -> UsbIdentityStagePolicy:
    """Explicit bounded file inspection; never a USB/device operation."""
    catalog = load_physical_onboarding_stage_catalog(workspace)
    _require(
        catalog.source_sha256 == CATALOG_SHA256
        and catalog.canonical_stage_order_sha256 == STAGE_ORDER_SHA256,
        "USB_POLICY_BASE_CATALOG_CHANGED",
    )
    return usb_identity_stage_policy()


_IDENTITY_HASHES = frozenset(
    (
        "source_sha256",
        "header_sha256",
        "stage_policy_sha256",
        "policy_review_sha256",
        "runtime_review_sha256",
        "runtime_registration_sha256",
        "selection_sha256",
        "native_identity_sha256",
        "endpoint_sha256",
        "device_instance_id_sha256",
        "operation_sha256",
    )
)


def _context(document: dict[str, Any]) -> None:
    for key, pattern in (
        ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
        ("session_id", r"physical-camera-[0-9a-f]{32}"),
    ):
        _require(
            type(document[key]) is str
            and re.fullmatch(pattern, document[key]) is not None,
            "EXACT_ORIGINAL_CAMERA_CONTEXT_REQUIRED",
        )


@dataclass(frozen=True, slots=True)
class UsbIdentityAdmissionIdentity:
    """Review-bound selection, not a claim that the camera is qualified.

    The three original subjects must be read back and semantically joined by
    the service. A syntactically valid reference alone authenticates nothing.
    """

    payload: bytes

    def __post_init__(self) -> None:
        document = _read(self.payload, MAX_IDENTITY_BYTES)
        _require(
            set(document)
            == {
                "schema",
                "cell_id",
                "session_id",
                "original_subjects",
                *_IDENTITY_HASHES,
            },
            "EXACT_IDENTITY_FIELDS_REQUIRED",
        )
        _require(
            document["schema"] == IDENTITY_SCHEMA, "EXACT_IDENTITY_SCHEMA_REQUIRED"
        )
        _context(document)
        for key in _IDENTITY_HASHES:
            _sha(document[key])
        _require(
            document["stage_policy_sha256"] == usb_identity_stage_policy().sha256,
            "USB_POLICY_IDENTITY_MISMATCH",
        )
        subjects = document["original_subjects"]
        _require(
            type(subjects) is list and len(subjects) == 3, "ORIGINAL_SUBJECTS_REQUIRED"
        )
        for role, item in zip(
            ("metadata", "policy_review", "runtime_review"), subjects
        ):
            _require(
                type(item) is dict
                and set(item) == {"role", "reference", "document_sha256"}
                and item["role"] == role,
                "EXACT_ORIGINAL_SUBJECT_ROLE_REQUIRED",
            )
            _sha(item["document_sha256"])
            try:
                reference = _parse_evidence_reference(item["reference"])
            except ValueError as exc:
                raise UsbIdentityPolicyError("INVALID_ORIGINAL_REFERENCE") from exc
            _require(
                reference.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
                and reference.payload_sha256 == item["document_sha256"],
                "ORIGINAL_SUBJECT_REFERENCE_MISMATCH",
            )
            if role != "metadata":
                _require(
                    item["document_sha256"] == document[f"{role}_sha256"],
                    "ORIGINAL_REVIEW_REFERENCE_MISMATCH",
                )
        _require(
            len({item["reference"]["evidence_id"] for item in subjects}) == 3,
            "DISTINCT_ORIGINAL_SUBJECTS_REQUIRED",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _read(self.payload, MAX_IDENTITY_BYTES)


@dataclass(frozen=True, slots=True)
class UsbIdentityPolicyReview:
    """Exact reviewed amendment and original context; not a physical grant."""

    payload: bytes

    def __post_init__(self) -> None:
        document = _read(self.payload, MAX_REVIEW_BYTES)
        _require(
            set(document)
            == {
                "schema",
                "cell_id",
                "session_id",
                "source_sha256",
                "header_sha256",
                "policy",
                "policy_sha256",
                "operator_id",
                "reviewer_id",
                "reviewed_at_utc_ns",
                "purpose",
                *_FLAGS,
            },
            "EXACT_POLICY_REVIEW_FIELDS_REQUIRED",
        )
        _require(
            document["schema"] == REVIEW_SCHEMA, "EXACT_POLICY_REVIEW_SCHEMA_REQUIRED"
        )
        _context(document)
        for key in ("source_sha256", "header_sha256", "policy_sha256"):
            _sha(document[key])
        policy = UsbIdentityStagePolicy(canonical(document["policy"]))
        _require(
            policy.sha256 == document["policy_sha256"], "REVIEW_POLICY_HASH_MISMATCH"
        )
        for key in ("operator_id", "reviewer_id"):
            value = document[key]
            _require(
                type(value) is str
                and 1 <= len(value) <= 96
                and value == value.strip()
                and all(32 <= ord(c) != 127 for c in value),
                "EXACT_REVIEWER_LABEL_REQUIRED",
            )
        _require(
            document["operator_id"].casefold() != document["reviewer_id"].casefold(),
            "DISTINCT_REVIEW_LABEL_REQUIRED",
        )
        _require(
            type(document["reviewed_at_utc_ns"]) is int
            and 0 < document["reviewed_at_utc_ns"] < 2**63,
            "EXACT_REVIEW_TIME_REQUIRED",
        )
        _require(
            document["purpose"] == "REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
            "EXACT_REVIEW_PURPOSE_REQUIRED",
        )
        _require(
            all(document[k] is False for k in _FLAGS), "REVIEW_CANNOT_GRANT_AUTHORITY"
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _read(self.payload, MAX_REVIEW_BYTES)
