"""Closed small display projection; parsing never authenticates a proposal."""

from copy import deepcopy
from dataclasses import asdict
import re

from .camera_operating_proposal import REFERENCE_MODE, VARIANCE_MODE
from .camera_operating_proposal_wizard import ACTION, SCHEMA, MAX_ATTEMPTS, MEANING
from rocell.providers.windows.camera_worker_client import (
    NativeCameraMode,
    CameraWorkerError,
)

FLAGS = (
    "physical_authority",
    "hardware_qualified",
    "approved_operating_policy",
    "original_stage_record_retained",
    "connected",
)
FIELDS = {
    "schema",
    "source_sha256",
    "launch_session_id",
    "current_operation_id",
    "proposal",
    "attempted",
    "maximum_attempts",
    "action_id",
    "state",
    "meaning",
    *FLAGS,
}


def validate_proposal_projection(value, *, source_sha256, launch_session_id):
    """Return detached data or None. Unknown fields/claims are never rendered."""

    def sha(item):
        return (
            type(item) is str
            and re.fullmatch(r"[0-9a-f]{64}", item)
            and item != "0" * 64
        )

    try:
        if not (
            type(value) is dict
            and set(value) == FIELDS
            and value["schema"] == SCHEMA
            and value["action_id"] == ACTION
            and sha(value["source_sha256"])
            and value["source_sha256"] == source_sha256
            and value["launch_session_id"] == launch_session_id
            and type(launch_session_id) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", launch_session_id)
            and all(value[k] is False for k in FLAGS)
            and type(value["attempted"]) is int
            and 0 <= value["attempted"] <= MAX_ATTEMPTS
            and type(value["maximum_attempts"]) is int
            and value["maximum_attempts"] == MAX_ATTEMPTS
            and value["meaning"] == MEANING
        ):
            return None
        current = value["state"] == "LOGGED_DRAFT_NOT_APPROVED"
        if value["state"] not in {
            "LOGGED_DRAFT_NOT_APPROVED",
            "NOT_STARTED",
            "PENDING_PUBLICATION",
            "HISTORICAL_HELD",
        }:
            return None
        if (value["state"] == "NOT_STARTED") != (value["attempted"] == 0):
            return None
        if not current:
            return (
                deepcopy(value)
                if value["proposal"] is None and value["current_operation_id"] is None
                else None
            )
        if type(value["current_operation_id"]) is not str or not re.fullmatch(
            r"operation-[0-9a-f]{32}", value["current_operation_id"]
        ):
            return None
        proposal = value["proposal"]
        if type(proposal) is not dict or set(proposal) != {
            "proposal_sha256",
            "policy_kind",
            "target_mode",
            "settings_epoch",
        }:
            return None
        if not sha(proposal["proposal_sha256"]) or not sha(proposal["settings_epoch"]):
            return None
        raw = proposal["target_mode"]
        if type(raw) is not dict or set(raw) != set(asdict(REFERENCE_MODE)):
            return None
        mode = NativeCameraMode(**raw)
        if not (
            mode.same_format(REFERENCE_MODE)
            and proposal["policy_kind"] == "REFERENCE_9_FPS_PROPOSAL"
            or mode.same_format(VARIANCE_MODE)
            and proposal["policy_kind"] == "EXPLICIT_8_FPS_VARIANCE_PROPOSAL"
        ):
            return None
        return deepcopy(value)
    except (ValueError, TypeError, KeyError, CameraWorkerError):
        return None
