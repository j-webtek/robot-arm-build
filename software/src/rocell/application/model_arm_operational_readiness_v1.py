"""Cross-lane operational-readiness gate for model-originated arm actions.

This gate composes retained AI/arm evidence without opening a camera, serial
endpoint, or controller.  It is deliberately fail closed: a structurally
aligned wire contract is reported separately from the physical qualifications
needed for one model-originated action.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .camera_support_optics_epoch_intake_v1 import REQUIRED_BINDINGS


SCHEMA = "rocell.model_arm_operational_readiness.v1"
SOURCE_PATHS = (
    "software/config/model_arm_conformance_profile_v1.json",
    "software/ai/eval/arm067_r97_owner_ai_review_acceptance.json",
    "software/ai/eval/arm069_owner_epoch_partial_assessment.json",
    "software/ai/eval/arm070_camera_support_optics_readiness.json",
    "software/ai/eval/arm065_r97_runtime_transition_assessment.json",
)
STAGE_IDS = (
    "wire_contract",
    "qualified_perception",
    "camera_support_optics",
    "measured_configuration_epoch",
    "measured_planner_calibration",
    "installed_controller_runtime",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ModelArmOperationalReadinessError(ValueError):
    """Retained evidence is malformed, altered, or mutually inconsistent."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ModelArmOperationalReadinessError(
            "operational-readiness value is not canonical JSON") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelArmOperationalReadinessError(f"{label} must be an object")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ModelArmOperationalReadinessError(f"{label} must be boolean")
    return value


def _verified_report_hash(
    report: Mapping[str, Any], field: str, label: str,
) -> str:
    claimed = report.get(field)
    if not isinstance(claimed, str) or _SHA256.fullmatch(claimed) is None:
        raise ModelArmOperationalReadinessError(
            f"{label} has no valid {field}")
    unsigned = {key: value for key, value in report.items() if key != field}
    if _sha256(_canonical(unsigned)) != claimed:
        raise ModelArmOperationalReadinessError(
            f"{label} content hash is invalid")
    return claimed


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelArmOperationalReadinessError(
            f"cannot load retained source {path}") from exc
    return _mapping(value, str(path))


def _stage(
    stage_id: str, *, ready: bool, evidence_sha256: str,
    blockers: Sequence[str], next_dependency: str | None,
) -> dict[str, Any]:
    unique = tuple(dict.fromkeys(blockers))
    if ready == bool(unique):
        raise ModelArmOperationalReadinessError(
            f"{stage_id} readiness contradicts its blockers")
    if ready != (next_dependency is None):
        raise ModelArmOperationalReadinessError(
            f"{stage_id} readiness contradicts its next dependency")
    return {
        "stage_id": stage_id,
        "status": "READY" if ready else "BLOCKED",
        "evidence_sha256": evidence_sha256,
        "blockers": list(unique),
        "next_dependency": next_dependency,
    }


def assess_model_arm_operational_readiness_v1(
    *,
    conformance: Mapping[str, Any],
    owner_review_acceptance: Mapping[str, Any],
    configuration_epoch: Mapping[str, Any],
    camera_support: Mapping[str, Any],
    controller_runtime: Mapping[str, Any],
    source_artifacts: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Compose one content-bound, zero-authority operational blocker map."""

    conformance = _mapping(conformance, "conformance profile")
    owner_review_acceptance = _mapping(
        owner_review_acceptance, "owner review acceptance")
    configuration_epoch = _mapping(
        configuration_epoch, "configuration epoch assessment")
    camera_support = _mapping(camera_support, "camera/support assessment")
    controller_runtime = _mapping(
        controller_runtime, "controller runtime assessment")

    if conformance.get("schema") != "rocell.model_arm_conformance_profile.v1":
        raise ModelArmOperationalReadinessError(
            "unexpected model/arm conformance schema")
    conformance_sha256 = _sha256(_canonical(conformance))
    owner_acceptance_sha256 = _verified_report_hash(
        owner_review_acceptance, "acceptance_sha256", "owner review acceptance")
    epoch_sha256 = _verified_report_hash(
        configuration_epoch, "assessment_sha256", "configuration epoch")
    camera_sha256 = _verified_report_hash(
        camera_support, "assessment_sha256", "camera/support assessment")
    controller_sha256 = _verified_report_hash(
        controller_runtime, "assessment_sha256", "controller runtime")

    reviewed = _mapping(conformance.get("reviewed_sources"), "reviewed_sources")
    result = _mapping(conformance.get("current_result"), "current_result")
    contract_ready = (
        result.get("contract_alignment") == "ALIGNED"
        and result.get("simulation_result") == "AI_BYTES_REACH_ARM_GATE"
    )
    ai_qualified = _boolean(
        reviewed.get("ai_qualification_installed"),
        "ai_qualification_installed",
    )
    camera_ready = _boolean(
        camera_support.get("component_admission_ready"),
        "component_admission_ready",
    )
    epoch_ready = _boolean(
        configuration_epoch.get("epoch_bound_build_proposal_ready"),
        "epoch_bound_build_proposal_ready",
    )
    controller_ready = _boolean(
        controller_runtime.get("installation_intake_ready"),
        "installation_intake_ready",
    )
    owner_governance_ready = (
        owner_review_acceptance.get("status")
        == "OWNER_ACCEPTED_AI_REVIEW_GOVERNANCE_OVERRIDE"
        and owner_review_acceptance.get(
            "ready_for_owner_governed_configuration_epoch_intake") is True
        and owner_review_acceptance.get("human_review_required") is False
        and owner_review_acceptance.get("external_independence_claimed") is False
        and owner_review_acceptance.get("owner_governance_override") is True
    )
    controller_ready = controller_ready and owner_governance_ready
    planner_ready = result.get("planner_result") == "READY_FOR_MEASURED_PLANNING"

    epoch_rows = configuration_epoch.get("component_assessments")
    if not isinstance(epoch_rows, list):
        raise ModelArmOperationalReadinessError(
            "configuration component assessments are invalid")
    epoch_camera = next(
        (row for row in epoch_rows
         if isinstance(row, Mapping)
         and row.get("component_id") == "camera_support_optics"),
        None,
    )
    if epoch_camera is None:
        raise ModelArmOperationalReadinessError(
            "configuration epoch omits camera_support_optics")
    epoch_missing = tuple(epoch_camera.get("missing_binding_ids", ()))
    camera_missing = tuple(camera_support.get("missing_binding_ids", ()))
    if epoch_missing != REQUIRED_BINDINGS or camera_missing != REQUIRED_BINDINGS:
        raise ModelArmOperationalReadinessError(
            "camera/support missing-binding lineage differs")

    stages = (
        _stage(
            "wire_contract", ready=contract_ready,
            evidence_sha256=conformance_sha256,
            blockers=() if contract_ready else ("WIRE_CONTRACT_NOT_ALIGNED",),
            next_dependency=None if contract_ready else "ALIGN_V2_PRODUCER_CONSUMER",
        ),
        _stage(
            "qualified_perception", ready=ai_qualified,
            evidence_sha256=conformance_sha256,
            blockers=() if ai_qualified else ("AI_QUALIFICATION_NOT_INSTALLED",),
            next_dependency=(None if ai_qualified else
                             "QUALIFIED_LOCALIZATION_AND_PRECISION_ADAPTER"),
        ),
        _stage(
            "camera_support_optics", ready=camera_ready,
            evidence_sha256=camera_sha256,
            blockers=() if camera_ready else tuple(
                f"RETAINED_ORIGINAL_MISSING:{item}" for item in camera_missing),
            next_dependency=(None if camera_ready else
                             "FOUR_RETAINED_CAMERA_SUPPORT_ORIGINALS"),
        ),
        _stage(
            "measured_configuration_epoch", ready=epoch_ready,
            evidence_sha256=epoch_sha256,
            blockers=() if epoch_ready else tuple(
                f"CONFIGURATION_COMPONENT_MISSING:{item}"
                for item in configuration_epoch.get("missing_component_ids", ())
            ),
            next_dependency=(None if epoch_ready else
                             "COMPLETE_MEASURED_CONFIGURATION_EPOCH"),
        ),
        _stage(
            "measured_planner_calibration", ready=planner_ready,
            evidence_sha256=conformance_sha256,
            blockers=() if planner_ready else (
                str(result.get("planner_result", "PLANNER_STATUS_MISSING")),),
            next_dependency=(None if planner_ready else
                             "COMMISSION_REQUIRED_CALIBRATIONS"),
        ),
        _stage(
            "installed_controller_runtime", ready=controller_ready,
            evidence_sha256=_sha256(_canonical({
                "controller_runtime_assessment_sha256": controller_sha256,
                "owner_review_acceptance_sha256": owner_acceptance_sha256,
            })),
            blockers=() if controller_ready else tuple(dict.fromkeys((
                *(str(item) for item in controller_runtime.get("blockers", ())
                  if item != "R97_INDEPENDENT_REVIEW_DECISION_MISSING"),
                *(() if owner_governance_ready else
                  ("OWNER_GOVERNANCE_ACCEPTANCE_MISSING",)),
            ))),
            next_dependency=(None if controller_ready else
                             "ATTEST_RUNTIME_PASS_FEEDBACK_AND_BIND_MEASURED_EPOCH"),
        ),
    )
    if tuple(item["stage_id"] for item in stages) != STAGE_IDS:
        raise AssertionError("operational stage order changed")
    ready = all(item["status"] == "READY" for item in stages)

    sources = []
    for item in source_artifacts:
        item = _mapping(item, "source artifact")
        path = item.get("path")
        digest = item.get("sha256")
        if (not isinstance(path, str) or not path
                or not isinstance(digest, str)
                or _SHA256.fullmatch(digest) is None):
            raise ModelArmOperationalReadinessError(
                "source artifact identity is invalid")
        sources.append({"path": path, "sha256": digest})
    if tuple(item["path"] for item in sources) != SOURCE_PATHS:
        raise ModelArmOperationalReadinessError("source artifact set differs")

    unsigned: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "READY_FOR_SINGLE_ACTION_REVIEW" if ready else "BLOCKED",
        "source_artifacts": sources,
        "stage_assessments": list(stages),
        "ready_stage_ids": [
            item["stage_id"] for item in stages if item["status"] == "READY"],
        "blocked_stage_ids": [
            item["stage_id"] for item in stages if item["status"] == "BLOCKED"],
        "single_action_review_ready": ready,
        "production_dispatch_allowed": False,
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "camera_open_authorized": False,
        "controller_start_authorized": False,
        "movement_authorized": False,
        "physical_authority": False,
    }
    return {**unsigned, "readiness_sha256": _sha256(_canonical(unsigned))}


def build_model_arm_operational_readiness_v1(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    loaded = []
    sources = []
    for relative in SOURCE_PATHS:
        path = root / relative
        raw = path.read_bytes()
        loaded.append(_load_json(path))
        sources.append({"path": relative, "sha256": _sha256(raw)})
    return assess_model_arm_operational_readiness_v1(
        conformance=loaded[0],
        owner_review_acceptance=loaded[1],
        configuration_epoch=loaded[2],
        camera_support=loaded[3],
        controller_runtime=loaded[4],
        source_artifacts=sources,
    )


__all__ = [
    "SCHEMA", "SOURCE_PATHS", "STAGE_IDS",
    "ModelArmOperationalReadinessError",
    "assess_model_arm_operational_readiness_v1",
    "build_model_arm_operational_readiness_v1",
]
