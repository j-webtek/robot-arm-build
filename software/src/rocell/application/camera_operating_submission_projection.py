"""Closed display-only submission projection; no storage or device authority."""

from copy import deepcopy
import re

from .camera_operating_submission import MAX_BYTES
from .camera_operating_submission_wizard import ACTION, MAX_ATTEMPTS
from .physical_onboarding import _parse_evidence_reference, STAGE_ORDER

FLAGS = (
    "stage_passed",
    "approved_operating_policy",
    "connected",
    "physical_authority",
    "hardware_qualified",
)
FIELDS = {
    "schema",
    "source_sha256",
    "launch_session_id",
    "action_id",
    "state",
    "publication",
    "original_stage_authenticated",
    "submission_id",
    "submission_sha256",
    "proposal_sha256",
    "assessment_sha256",
    "reference",
    "retention",
    "capture_requests",
    "attempted",
    "maximum_attempts",
    "review_required",
    "pixel_check_semantics",
    "meaning",
    *FLAGS,
}
MEANING = "A saved submission is unreviewed historical evidence. Original authentication does not restore a connection, prove current pixels, qualify calibration or enable the arm."


def validate_submission_projection(value, *, source_sha256, launch_session_id):
    """Return detached data or None; malformed/unknown claims are withheld."""

    def sha(x):
        return type(x) is str and re.fullmatch(r"[0-9a-f]{64}", x) and x != "0" * 64

    try:
        if not (
            type(value) is dict
            and set(value) == FIELDS
            and value["schema"] == "rocell.wizard_camera_operating_submission.v1"
            and value["action_id"] == ACTION
            and sha(value["source_sha256"])
            and value["source_sha256"] == source_sha256
            and value["launch_session_id"] == launch_session_id
            and type(launch_session_id) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", launch_session_id)
            and all(value[k] is False for k in FLAGS)
            and value["review_required"] is True
            and type(value["original_stage_authenticated"]) is bool
            and type(value["attempted"]) is int
            and 0 <= value["attempted"] <= MAX_ATTEMPTS
            and type(value["maximum_attempts"]) is int
            and value["maximum_attempts"] == MAX_ATTEMPTS
            and value["pixel_check_semantics"]
            == "HISTORICAL_READ_NOT_CURRENT_FILE_VERIFICATION"
            and value["meaning"] == MEANING
        ):
            return None
        publication = value["publication"]
        if not (
            type(publication) is dict
            and set(publication) == {"status", "operation_id"}
            and publication["status"]
            in {"NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD"}
            and (
                publication["operation_id"] is None
                or (
                    type(publication["operation_id"]) is str
                    and re.fullmatch(
                        r"operation-[0-9a-f]{32}", publication["operation_id"]
                    )
                )
            )
            and (
                publication["status"] != "CURRENT"
                or publication["operation_id"] is not None
            )
        ):
            return None
        original = value["state"] in {"INCOMPLETE", "SUBMITTED_REVIEW_REQUIRED"}
        if value["original_stage_authenticated"] != original or value["state"] not in {
            "NOT_STARTED",
            "RUNNING",
            "AWAITING_COMPLETION_LOG",
            "HISTORICAL_HELD",
            "RETAINED_UNREVIEWED",
            "INCOMPLETE",
            "SUBMITTED_REVIEW_REQUIRED",
        }:
            return None
        if not original and value["attempted"] == 0 and value["state"] != "NOT_STARTED":
            return None
        if value["submission_id"] is None:
            return (
                deepcopy(value)
                if (
                    not original
                    and value["state"] in {"NOT_STARTED", "RUNNING", "HISTORICAL_HELD"}
                    and (value["state"] != "NOT_STARTED" or value["attempted"] == 0)
                    and all(
                        value[k] is None
                        for k in (
                            "submission_sha256",
                            "proposal_sha256",
                            "assessment_sha256",
                            "reference",
                            "retention",
                        )
                    )
                    and value["capture_requests"] == []
                )
                else None
            )
        if (
            value["state"] == "NOT_STARTED"
            or type(value["submission_id"]) is not str
            or not re.fullmatch(r"cameraoperating-[0-9a-f]{32}", value["submission_id"])
            or not all(
                sha(value[k])
                for k in ("submission_sha256", "proposal_sha256", "assessment_sha256")
            )
        ):
            return None
        requests = value["capture_requests"]
        if not (
            type(requests) is list
            and len(requests) == 2
            and all(
                type(k) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", k)
                for k in requests
            )
            and len(set(requests)) == 2
        ):
            return None
        retention = value["retention"]
        if retention not in {
            "COLLECTED_NOT_M1_RETAINED",
            "M1_PUBLICATION_UNCONFIRMED",
            "M1_PUBLISHED_READBACK_PENDING",
            "M1_FULL_BYTES_READ_BACK",
        }:
            return None
        if value["reference"] is None:
            return (
                deepcopy(value)
                if not original
                and retention
                in {"COLLECTED_NOT_M1_RETAINED", "M1_PUBLICATION_UNCONFIRMED"}
                else None
            )
        reference = value["reference"]
        if not (
            type(reference) is dict
            and type(reference.get("payload_bytes")) is int
            and all(
                sha(reference.get(k))
                for k in ("package_sha256", "manifest_sha256", "payload_sha256")
            )
        ):
            return None
        ref = _parse_evidence_reference(reference)
        if (
            ref.stage is not STAGE_ORDER[4]
            or ref.payload_sha256 != value["submission_sha256"]
            or not 0 < ref.payload_bytes <= MAX_BYTES
            or retention
            not in {"M1_PUBLISHED_READBACK_PENDING", "M1_FULL_BYTES_READ_BACK"}
            or original
            and retention != "M1_FULL_BYTES_READ_BACK"
        ):
            return None
        return deepcopy(value)
    except (ValueError, TypeError, KeyError):
        return None
