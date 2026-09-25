"""Machine-checkable assurance trace for the current zero-write shadow path."""

from __future__ import annotations

from typing import Any

from .scene_observation import SHA256_PATTERN, canonical_hash
from .shadow_preview import validate as validate_shadow


SCHEMA = "rocell.ai_translation_assurance.v0"
STAGES = (
    "intent_grounding",
    "semantic_compilation",
    "scene_assessment",
    "target_localization",
    "physical_calibration",
    "trajectory_planning",
    "safety_admission",
    "command_encoding",
    "outcome_verification",
)
FIELDS = {
    "schema", "request_id", "shadow_sha256", "disposition", "stages", "counts",
    "physical_execution_authorized", "assurance_sha256",
}


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS or value.get("schema") != SCHEMA:
        raise ValueError("translation assurance has invalid schema or fields")
    if not isinstance(value["request_id"], str) or not value["request_id"].strip():
        raise ValueError("translation assurance request_id is required")
    for key in ("shadow_sha256", "assurance_sha256"):
        if not isinstance(value[key], str) or SHA256_PATTERN.fullmatch(value[key]) is None:
            raise ValueError(f"invalid translation assurance {key}")
    if value["disposition"] not in {"BLOCKED", "COORDINATE_PREVIEW_ONLY"}:
        raise ValueError("invalid translation assurance disposition")
    stages = value["stages"]
    if not isinstance(stages, list) or [row.get("stage") for row in stages] != list(STAGES):
        raise ValueError("translation assurance stages are incomplete or out of order")
    blocked = False
    for row in stages:
        if not isinstance(row, dict) or set(row) != {"stage", "status", "artifact_sha256", "reason"}:
            raise ValueError("translation assurance stage has invalid fields")
        if row["status"] not in {"passed", "blocked", "not_run"}:
            raise ValueError("translation assurance stage has invalid status")
        artifact = row["artifact_sha256"]
        if artifact is not None and (not isinstance(artifact, str) or SHA256_PATTERN.fullmatch(artifact) is None):
            raise ValueError("translation assurance stage has invalid artifact hash")
        if row["status"] == "passed" and (artifact is None or blocked):
            raise ValueError("translation assurance cannot pass a stage after a blocker")
        if row["status"] == "blocked":
            if blocked or not isinstance(row["reason"], str) or not row["reason"]:
                raise ValueError("translation assurance needs exactly one first blocker")
            blocked = True
        elif row["status"] == "not_run":
            if not blocked or row["reason"] != "upstream_blocked":
                raise ValueError("translation assurance not_run must follow a blocker")
        elif row["reason"] is not None:
            raise ValueError("passed translation assurance stage cannot have a reason")
    if not blocked:
        raise ValueError("offline translation assurance must preserve a downstream blocker")
    counts = value["counts"]
    if (not isinstance(counts, dict) or set(counts) != {"permits", "commands", "writes", "retries"}
            or any(type(count) is not int or count != 0 for count in counts.values())
            or value["physical_execution_authorized"] is not False):
        raise ValueError("offline translation assurance must have zero effects and no authority")
    core = {key: item for key, item in value.items() if key != "assurance_sha256"}
    if value["assurance_sha256"] != canonical_hash(core):
        raise ValueError("translation assurance hash mismatch")
    return value


def build(shadow: dict[str, Any]) -> dict[str, Any]:
    shadow = validate_shadow(shadow)
    result = shadow["result"]
    coordinates = result.get("coordinates") if isinstance(result.get("coordinates"), dict) else result
    proposal = result.get("proposal") or (coordinates.get("proposal") if isinstance(coordinates, dict) else None)
    plan = result.get("plan_result") or (coordinates.get("plan_result") if isinstance(coordinates, dict) else None)

    stages: list[dict[str, Any]] = []
    blocker = False

    def add(stage: str, status: str, artifact: str | None = None, reason: str | None = None) -> None:
        nonlocal blocker
        stages.append({"stage": stage, "status": status, "artifact_sha256": artifact, "reason": reason})
        blocker = blocker or status == "blocked"

    if isinstance(proposal, dict) and proposal.get("decision") == "type_text":
        add("intent_grounding", "passed", canonical_hash(proposal))
    else:
        add("intent_grounding", "blocked", reason=(proposal or {}).get("reason", "intent_not_grounded"))
    if blocker:
        add("semantic_compilation", "not_run", reason="upstream_blocked")
    elif isinstance(plan, dict) and plan.get("status") == "accepted":
        add("semantic_compilation", "passed", plan.get("plan_hash"))
    else:
        add("semantic_compilation", "blocked", reason=(plan or {}).get("reason", "semantic_plan_missing"))
    if blocker:
        add("scene_assessment", "not_run", reason="upstream_blocked")
    else:
        add("scene_assessment", "passed", shadow["scene_observation_sha256"])
    if blocker:
        add("target_localization", "not_run", reason="upstream_blocked")
    elif shadow["precision_observation_sha256"] is None:
        add("target_localization", "blocked", reason="precision_observation_missing")
    elif result.get("status") == "coordinate_preview":
        add("target_localization", "passed", shadow["precision_observation_sha256"])
    else:
        add("target_localization", "blocked", reason=result.get("reason", "vision_fusion_rejected"))
    if blocker:
        add("physical_calibration", "not_run", reason="upstream_blocked")
    else:
        add("physical_calibration", "blocked", reason="commissioned_calibration_missing")
    for stage in STAGES[len(stages):]:
        add(stage, "not_run", reason="upstream_blocked")

    core = {
        "schema": SCHEMA,
        "request_id": shadow["request_id"],
        "shadow_sha256": shadow["shadow_sha256"],
        "disposition": "COORDINATE_PREVIEW_ONLY" if result.get("status") == "coordinate_preview" else "BLOCKED",
        "stages": stages,
        "counts": {"permits": 0, "commands": 0, "writes": 0, "retries": 0},
        "physical_execution_authorized": False,
    }
    return validate({**core, "assurance_sha256": canonical_hash(core)})
