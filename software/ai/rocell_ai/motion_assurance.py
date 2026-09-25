"""Zero-write assurance bundle for one model-authored coordinate proposal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from rocell.application.model_motion_bridge import compile_mapping
from rocell.models import ModelMotionProposal

from .scene_observation import SHA256_PATTERN, canonical_hash


SCHEMA = "rocell.ai_model_motion_assurance_bundle.v0"
STAGES = (
    "model_proposal_validation",
    "named_target_resolution",
    "coordinate_frame_conversion",
    "physical_calibration",
    "inverse_kinematics",
    "route_screening",
    "safety_admission",
    "command_encoding",
    "outcome_verification",
)


def _unique_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            raise ValueError(f"duplicate model motion proposal field {key!r}")
        result[key] = item
    return result


def load(path: Path) -> object:
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite JSON constant {value!r}")),
    )


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema", "candidate", "assurance", "bundle_sha256"}:
        raise ValueError("model motion assurance bundle has invalid fields")
    if value.get("schema") != SCHEMA:
        raise ValueError("unsupported model motion assurance schema")
    candidate = value["candidate"]
    assurance = value["assurance"]
    if not isinstance(candidate, dict) or not isinstance(assurance, dict):
        raise ValueError("model motion assurance bundle needs candidate and assurance objects")
    if (candidate.get("controller_commands") != []
            or type(candidate.get("hardware_commands_generated")) is not int
            or candidate["hardware_commands_generated"] != 0
            or candidate.get("hardware_access") is not False
            or candidate.get("physical_authority") is not False):
        raise ValueError("model motion candidate must remain zero-write and unauthorized")
    candidate_core = {key: item for key, item in candidate.items() if key != "candidate_sha256"}
    if candidate.get("candidate_sha256") != canonical_hash(candidate_core):
        raise ValueError("model motion candidate hash mismatch")
    required_assurance = {
        "proposal_id", "proposal_sha256", "candidate_sha256", "target_catalog_sha256",
        "source", "disposition", "stages", "counts", "physical_execution_authorized",
    }
    if set(assurance) != required_assurance:
        raise ValueError("model motion assurance has invalid fields")
    if not isinstance(assurance["proposal_id"], str) or not assurance["proposal_id"].strip():
        raise ValueError("model motion assurance proposal_id is required")
    for key in ("proposal_sha256", "candidate_sha256", "target_catalog_sha256"):
        if not isinstance(assurance[key], str) or SHA256_PATTERN.fullmatch(assurance[key]) is None:
            raise ValueError(f"invalid model motion assurance {key}")
    if assurance["candidate_sha256"] != candidate["candidate_sha256"]:
        raise ValueError("model motion assurance candidate binding mismatch")
    if assurance["proposal_id"] != candidate.get("proposal_id"):
        raise ValueError("model motion assurance proposal id mismatch")
    if assurance["proposal_sha256"] != candidate["proposal_sha256"]:
        raise ValueError("model motion assurance proposal binding mismatch")
    if assurance["target_catalog_sha256"] != candidate["target_catalog_sha256"]:
        raise ValueError("model motion assurance catalog binding mismatch")
    if assurance["source"] != candidate["source"]:
        raise ValueError("model motion assurance source binding mismatch")
    if assurance["disposition"] != "BLOCKED_BEFORE_CALIBRATED_PLANNING":
        raise ValueError("invalid model motion assurance disposition")
    stages = assurance["stages"]
    if not isinstance(stages, list) or [row.get("stage") for row in stages] != list(STAGES):
        raise ValueError("model motion assurance stages are incomplete or out of order")
    for index, row in enumerate(stages):
        expected = "passed" if index < 3 else "blocked" if index == 3 else "not_run"
        if not isinstance(row, dict) or set(row) != {"stage", "status", "artifact_sha256", "reason"}:
            raise ValueError("model motion assurance stage has invalid fields")
        if row["status"] != expected:
            raise ValueError("model motion assurance stage crossed its first blocker")
        if expected == "passed" and (
            not isinstance(row["artifact_sha256"], str)
            or SHA256_PATTERN.fullmatch(row["artifact_sha256"]) is None
            or row["reason"] is not None
        ):
            raise ValueError("passed model motion assurance stage lacks valid lineage")
        if expected == "blocked" and row["reason"] != "commissioned_physical_calibration_missing":
            raise ValueError("model motion assurance must block at physical calibration")
        if expected == "not_run" and row["reason"] != "upstream_blocked":
            raise ValueError("downstream model motion assurance stage must remain not_run")
    counts = assurance["counts"]
    if (not isinstance(counts, dict) or set(counts) != {"permits", "commands", "writes", "retries"}
            or any(type(count) is not int or count != 0 for count in counts.values())
            or assurance["physical_execution_authorized"] is not False):
        raise ValueError("model motion assurance must preserve zero effects")
    core = {key: item for key, item in value.items() if key != "bundle_sha256"}
    if value.get("bundle_sha256") != canonical_hash(core):
        raise ValueError("model motion assurance bundle hash mismatch")
    return value


def build(value: object, *, workspace: Path, minimum_confidence: float = 0.9) -> dict[str, Any]:
    proposal = ModelMotionProposal.from_mapping(value)
    candidate = compile_mapping(value, workspace=workspace, minimum_confidence=minimum_confidence)
    assurance = {
        "proposal_id": proposal.proposal_id,
        "proposal_sha256": candidate["proposal_sha256"],
        "candidate_sha256": candidate["candidate_sha256"],
        "target_catalog_sha256": candidate["target_catalog_sha256"],
        "source": candidate["source"],
        "disposition": "BLOCKED_BEFORE_CALIBRATED_PLANNING",
        "stages": [
            {"stage": "model_proposal_validation", "status": "passed", "artifact_sha256": candidate["proposal_sha256"], "reason": None},
            {"stage": "named_target_resolution", "status": "passed", "artifact_sha256": candidate["target_catalog_sha256"], "reason": None},
            {"stage": "coordinate_frame_conversion", "status": "passed", "artifact_sha256": candidate["candidate_sha256"], "reason": None},
            {"stage": "physical_calibration", "status": "blocked", "artifact_sha256": None, "reason": "commissioned_physical_calibration_missing"},
            *[
                {"stage": stage, "status": "not_run", "artifact_sha256": None, "reason": "upstream_blocked"}
                for stage in STAGES[4:]
            ],
        ],
        "counts": {"permits": 0, "commands": 0, "writes": 0, "retries": 0},
        "physical_execution_authorized": False,
    }
    core = {"schema": SCHEMA, "candidate": candidate, "assurance": assurance}
    return validate({**core, "bundle_sha256": canonical_hash(core)})
