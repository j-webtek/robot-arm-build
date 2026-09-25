"""Pure original baseline subjects; inspection/query results are not stage PASS."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    _parse_evidence_reference,
)
from .physical_usb_identity_campaign import UsbIdentityOperation
from .usb_identity_stage_policy import (
    UsbIdentityStagePolicy,
    UsbIdentityAdmissionIdentity,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    FIXED_SOURCE_PINS,
    BUILD_RECORD_PATH,
    BUILD_RECORD_SHA256,
)

INSPECTION_SCHEMA = "rocell.camera_usb_baseline_inspection.v1"
OUTCOME_SCHEMA = "rocell.camera_usb_baseline_outcome.v1"
USB_ROLE_BYTES = {
    "inspection": 128 * 1024,
    "policy_review": 8 * 1024,
    "runtime_review": 8 * 1024,
    "identity": 12 * 1024,
    "execution": 128 * 1024,
    "outcome": 16 * 1024,
}
USB_LABEL = re.compile(
    r"camera-usb-(inspection|policy-review|runtime-review|identity|execution|outcome)-v1:(usbidentity-[0-9a-f]{32})"
)
USB_EVENT = re.compile(
    r"CAMERA_USB_(INSPECTION_STARTED|INSPECTED|REVIEWED|QUERY_REQUESTED|QUERY_RETAINED)_([0-9A-F]{32})"
)
METADATA_ROLES = ("metadata", "helper", "receipt", "assessment", "review")
FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "camera_capture_authorized": False,
    "arm_access_authorized": False,
    "stage_pass": False,
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class UsbBaselineError(ValueError):
    pass


def _need(value: bool, code: str) -> None:
    if not value:
        raise UsbBaselineError(code)


def _sha(value: Any) -> None:
    _need(
        type(value) is str and bool(_SHA.fullmatch(value)) and value != "0" * 64,
        "USB_BASELINE_HASH",
    )


def _time(value: Any) -> None:
    _need(type(value) is int and 0 < value < 2**63, "USB_BASELINE_TIME")


def _binding(value: Any) -> None:
    _need(
        type(value) is dict
        and set(value)
        == {
            "usb_id",
            "source_sha256",
            "cell_id",
            "session_id",
            "header_sha256",
            "origin_launch_id",
            "collection_launch_id",
            "operator_id",
            "metadata",
        },
        "USB_BASELINE_BINDING",
    )
    for key in ("source_sha256", "header_sha256"):
        _sha(value[key])
    for key, pattern in (
        ("usb_id", r"usbidentity-[0-9a-f]{32}"),
        ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
        ("session_id", r"physical-camera-[0-9a-f]{32}"),
    ):
        _need(
            type(value[key]) is str and re.fullmatch(pattern, value[key]) is not None,
            "USB_BASELINE_CONTEXT",
        )
    for key in ("origin_launch_id", "collection_launch_id"):
        text = value[key]
        _need(
            type(text) is str
            and 1 <= len(text) <= 96
            and text == text.strip()
            and all(32 <= ord(c) < 127 for c in text),
            "USB_BASELINE_LABEL",
        )
    operator = value["operator_id"]
    _need(
        type(operator) is str
        and 1 <= len(operator.encode("utf-8")) <= 96
        and operator == operator.strip()
        and all(ord(c) >= 32 and not 127 <= ord(c) <= 159 for c in operator),
        "USB_BASELINE_LABEL",
    )
    _need(
        type(value["metadata"]) is dict
        and set(value["metadata"]) == set(METADATA_ROLES),
        "USB_BASELINE_METADATA",
    )
    for sha in value["metadata"].values():
        _sha(sha)


def _read(payload: bytes, maximum: int) -> dict[str, Any]:
    _need(type(payload) is bytes, "USB_BASELINE_BYTES")
    value = decode_owned_json(payload, maximum=maximum)
    _need(canonical(value) == payload, "USB_BASELINE_CANONICAL")
    return value


def _flags(value: dict[str, Any]) -> None:
    _need(all(value[key] is False for key in FLAGS), "USB_BASELINE_NO_AUTHORITY")


def _file_report(report: Any, runtime: UsbIdentityRuntimeRegistration) -> None:
    """Validate retained file observations against the fixed roster, without I/O."""
    _need(
        type(report) is dict
        and set(report)
        == {
            "schema",
            "runtime_registration_sha256",
            "source_sha256",
            "status",
            "files",
            "physical_authority",
            "hardware_qualified",
        },
        "USB_BASELINE_FILE_REPORT",
    )
    data = runtime.to_dict()
    _need(
        report["schema"] == "rocell.usb_identity_runtime_file_check.v1"
        and report["runtime_registration_sha256"] == runtime.sha256
        and report["source_sha256"] == data["source_sha256"]
        and report["status"] == "FILES_MATCHED"
        and report["physical_authority"] is False
        and report["hardware_qualified"] is False,
        "USB_BASELINE_FILE_CONTEXT",
    )
    expected = [
        *FIXED_SOURCE_PINS,
        (BUILD_RECORD_PATH, BUILD_RECORD_SHA256, 32 * 1024),
        (data["helper"]["path"], data["helper"]["sha256"], 1024 * 1024),
    ]
    rows = report["files"]
    _need(type(rows) is list and len(rows) == len(expected), "USB_BASELINE_FILE_ROSTER")
    for row, (path, sha, maximum) in zip(rows, expected):
        _need(
            type(row) is dict
            and set(row) == {"path", "sha256", "bytes"}
            and row["path"] == path
            and row["sha256"] == sha
            and type(row["bytes"]) is int
            and 0 < row["bytes"] <= maximum,
            "USB_BASELINE_FILE_ROSTER",
        )


@dataclass(frozen=True, slots=True)
class UsbBaselineInspection:
    payload: bytes

    def __post_init__(self) -> None:
        value = _read(self.payload, USB_ROLE_BYTES["inspection"])
        _need(
            set(value)
            == {
                "schema",
                "binding",
                "policy",
                "policy_sha256",
                "operation",
                "operation_sha256",
                "runtime_report",
                "collected_at_ns",
                "meaning",
                *FLAGS,
            },
            "USB_BASELINE_INSPECTION_FIELDS",
        )
        _need(
            value["schema"] == INSPECTION_SCHEMA
            and value["meaning"] == "FILES_AND_TARGET_ONLY_NOT_QUERY_PERMISSION",
            "USB_BASELINE_SCHEMA",
        )
        _binding(value["binding"])
        _time(value["collected_at_ns"])
        _flags(value)
        policy = UsbIdentityStagePolicy(canonical(value["policy"]))
        operation = UsbIdentityOperation(canonical(value["operation"]))
        op = operation.to_dict()
        _need(
            policy.sha256 == value["policy_sha256"] == op["policy_sha256"]
            and operation.sha256 == value["operation_sha256"]
            and all(
                op[key] == value["binding"][key]
                for key in ("cell_id", "session_id", "source_sha256")
            ),
            "USB_BASELINE_OPERATION_JOIN",
        )
        _file_report(
            value["runtime_report"],
            UsbIdentityRuntimeRegistration(canonical(op["runtime"])),
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _read(self.payload, USB_ROLE_BYTES["inspection"])

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return {
            "schema": "rocell.camera_usb_baseline_inspection_summary.v1",
            "binding": value["binding"],
            "inspection_sha256": self.sha256,
            "policy_sha256": value["policy_sha256"],
            "operation_sha256": value["operation_sha256"],
            "runtime_registration_sha256": value["runtime_report"][
                "runtime_registration_sha256"
            ],
            "file_count": len(value["runtime_report"]["files"]),
            "status": "FILES_MATCHED",
            "meaning": value["meaning"],
            **FLAGS,
        }


def build_usb_baseline_inspection(
    *,
    binding: dict[str, Any],
    policy: UsbIdentityStagePolicy,
    operation: UsbIdentityOperation,
    runtime_report: dict[str, Any],
    collected_at_ns: int,
) -> UsbBaselineInspection:
    _need(
        type(policy) is UsbIdentityStagePolicy
        and type(operation) is UsbIdentityOperation,
        "USB_BASELINE_EXACT_INPUT",
    )
    policy = UsbIdentityStagePolicy(policy.payload)
    operation = UsbIdentityOperation(operation.payload)
    return UsbBaselineInspection(
        canonical(
            {
                "schema": INSPECTION_SCHEMA,
                "binding": binding,
                "policy": policy.to_dict(),
                "policy_sha256": policy.sha256,
                "operation": operation.to_dict(),
                "operation_sha256": operation.sha256,
                "runtime_report": runtime_report,
                "collected_at_ns": collected_at_ns,
                "meaning": "FILES_AND_TARGET_ONLY_NOT_QUERY_PERMISSION",
                **FLAGS,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class UsbBaselineOutcome:
    payload: bytes

    def __post_init__(self) -> None:
        value = _read(self.payload, USB_ROLE_BYTES["outcome"])
        _need(
            set(value)
            == {
                "schema",
                "binding",
                "inspection_sha256",
                "identity_sha256",
                "campaign_reference",
                "execution_reference",
                "result_sha256",
                "admission_evidence_sha256",
                "outcome",
                "recorded_at_ns",
                "meaning",
                *FLAGS,
            },
            "USB_BASELINE_OUTCOME_FIELDS",
        )
        _need(
            value["schema"] == OUTCOME_SCHEMA
            and value["meaning"]
            == "ORIGINAL_QUERY_DIAGNOSTIC_NOT_IDENTITY_QUALIFICATION",
            "USB_BASELINE_SCHEMA",
        )
        _binding(value["binding"])
        _time(value["recorded_at_ns"])
        _flags(value)
        for key in (
            "inspection_sha256",
            "identity_sha256",
            "result_sha256",
            "admission_evidence_sha256",
        ):
            _sha(value[key])
        reference = _parse_evidence_reference(value["execution_reference"])
        _need(
            reference.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
            and 0 < reference.payload_bytes <= USB_ROLE_BYTES["execution"],
            "USB_BASELINE_EXECUTION_REFERENCE",
        )
        campaign = value["campaign_reference"]
        _need(
            type(campaign) is dict
            and set(campaign)
            == {
                "schema",
                "cell_id",
                "session_id",
                "attempt_id",
                "permit_sha256",
                "evidence_sha256",
                "payload_bytes",
                "label",
            },
            "USB_BASELINE_CAMPAIGN_REFERENCE",
        )
        _need(
            campaign["schema"] == "rocell.usb_identity_campaign_reference.v1"
            and campaign["cell_id"] == value["binding"]["cell_id"]
            and campaign["session_id"] == value["binding"]["session_id"]
            and type(campaign["attempt_id"]) is str
            and re.fullmatch(r"attempt-[0-9a-f]{32}", campaign["attempt_id"])
            is not None
            and campaign["label"] == "physical-native-usb-identity"
            and type(campaign["payload_bytes"]) is int
            and campaign["payload_bytes"] == reference.payload_bytes
            and campaign["evidence_sha256"] == reference.payload_sha256,
            "USB_BASELINE_CAMPAIGN_REFERENCE",
        )
        _sha(campaign["permit_sha256"])
        _need(value["outcome"] in {"OBSERVED", "HELD"}, "USB_BASELINE_OUTCOME")

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _read(self.payload, USB_ROLE_BYTES["outcome"])

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return {
            "schema": "rocell.camera_usb_baseline_outcome_summary.v1",
            "binding": value["binding"],
            "outcome_sha256": self.sha256,
            "inspection_sha256": value["inspection_sha256"],
            "identity_sha256": value["identity_sha256"],
            "campaign_reference": value["campaign_reference"],
            "outcome": value["outcome"],
            "meaning": value["meaning"],
            **FLAGS,
        }


def build_usb_baseline_outcome(
    *,
    inspection: UsbBaselineInspection,
    identity: UsbIdentityAdmissionIdentity,
    execution_reference: EvidenceReference,
    campaign_original: dict[str, Any],
    recorded_at_ns: int,
) -> UsbBaselineOutcome:
    _need(
        type(inspection) is UsbBaselineInspection
        and type(identity) is UsbIdentityAdmissionIdentity
        and type(execution_reference) is EvidenceReference,
        "USB_BASELINE_EXACT_INPUT",
    )
    inspection = UsbBaselineInspection(inspection.payload)
    identity = UsbIdentityAdmissionIdentity(identity.payload)
    _need(
        campaign_original["retention"] == "M1_FULL_BYTES_READ_BACK"
        and campaign_original["result"]["state"] == "SEALED_KNOWN",
        "USB_BASELINE_KNOWN_ORIGINAL_REQUIRED",
    )
    evidence = OwnedUsbIdentityRunEvidence(canonical(campaign_original["evidence"]))
    effect = evidence.bounded_effect_summary()
    prepared = evidence.preparation
    request = prepared.request.to_dict()
    original_identity = identity.to_dict()
    inspection_document = inspection.to_dict()
    _need(
        all(
            original_identity[key] == inspection_document["binding"][key]
            for key in ("source_sha256", "cell_id", "session_id", "header_sha256")
        )
        and campaign_original["admission_evidence"]["selected_identity"]
        == original_identity
        and prepared.identity.sha256 == identity.sha256
        and request["operation_sha256"] == inspection_document["operation_sha256"]
        and campaign_original["reference"]["permit_sha256"] == request["permit_sha256"]
        and campaign_original["reference"]["attempt_id"] == request["attempt_id"]
        and campaign_original["result"]["permit_sha256"] == request["permit_sha256"]
        and campaign_original["result"]["attempt_id"] == request["attempt_id"]
        and recorded_at_ns >= evidence.to_dict()["finished_utc_ns"]
        and recorded_at_ns >= inspection_document["collected_at_ns"],
        "USB_BASELINE_ORIGINAL_CONTEXT",
    )
    _need(
        evidence.sha256
        == campaign_original["evidence_sha256"]
        == execution_reference.payload_sha256
        and len(evidence.payload) == execution_reference.payload_bytes
        and effect["current_complete"]
        and effect["process_cleanup_confirmed"]
        and effect["usb_cleanup_confirmed"],
        "USB_BASELINE_ORIGINAL_EXECUTION_JOIN",
    )
    return UsbBaselineOutcome(
        canonical(
            {
                "schema": OUTCOME_SCHEMA,
                "binding": inspection.to_dict()["binding"],
                "inspection_sha256": inspection.sha256,
                "identity_sha256": identity.sha256,
                "campaign_reference": campaign_original["reference"],
                "execution_reference": execution_reference.to_dict(),
                "result_sha256": digest(canonical(campaign_original["result"])),
                "admission_evidence_sha256": digest(
                    canonical(campaign_original["admission_evidence"])
                ),
                "outcome": effect["native_outcome"],
                "recorded_at_ns": recorded_at_ns,
                "meaning": "ORIGINAL_QUERY_DIAGNOSTIC_NOT_IDENTITY_QUALIFICATION",
                **FLAGS,
            }
        )
    )
