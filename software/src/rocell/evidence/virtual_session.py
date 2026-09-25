"""Atomic recording, strict verification, and recomputation of virtual runs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from rocell.application.virtual_session import (
    VirtualSessionReport,
    run_default_virtual_session,
)
from rocell.application.virtual_pixel_vision import (
    VirtualPixelVisionError,
    virtual_pixel_vision_attempt_ledger_from_dict,
)
from rocell.models.actions import ActionPlan
from rocell.simulation.virtual_workcell import (
    VirtualFaultKind,
    VirtualFaultScript,
    VirtualFaultTrigger,
)
from rocell.typing import compile_development_text
from rocell.typing.development_profiles import (
    development_keyboard_profile,
    development_phone_profile,
)


MANIFEST_SCHEMA = "rocell.virtual_session_manifest.v2"
LEGACY_MANIFEST_SCHEMA = "rocell.virtual_session_manifest.v1"
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_PACKAGE_BYTES = 16 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECORD_ID = re.compile(r"^virtual-([0-9a-f]{24})$")
_LEGACY_ARTIFACT_ROLES: tuple[tuple[str, str], ...] = (
    ("action-plan.json", "SEMANTIC_ACTION_PLAN"),
    ("scenario.json", "LOCKED_VIRTUAL_SCENARIO"),
    ("trajectory.json", "CANONICAL_TRAJECTORY_DIAGNOSTIC"),
    ("events.json", "VIRTUAL_EVENT_LEDGER"),
    ("report.json", "VIRTUAL_SESSION_REPORT"),
)
_ARTIFACT_ROLES: tuple[tuple[str, str], ...] = (
    ("action-plan.json", "SEMANTIC_ACTION_PLAN"),
    ("scenario.json", "LOCKED_VIRTUAL_SCENARIO"),
    ("trajectory.json", "CANONICAL_TRAJECTORY_DIAGNOSTIC"),
    ("events.json", "VIRTUAL_EVENT_LEDGER"),
    ("vision.json", "PIXEL_VISION_ATTEMPT_LEDGER"),
    ("report.json", "VIRTUAL_SESSION_REPORT"),
)
_EXPECTED_FILES = frozenset({name for name, _ in _ARTIFACT_ROLES} | {"manifest.json"})
_LEGACY_EXPECTED_FILES = frozenset(
    {name for name, _ in _LEGACY_ARTIFACT_ROLES} | {"manifest.json"}
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "record_id",
        "report_hash",
        "artifact_count",
        "total_artifact_bytes",
        "artifacts",
        "complete",
        "manifest_written_last",
        "simulation_only",
        "hardware_commands_generated",
        "physical_release_effect",
        "package_hash",
    }
)


class VirtualSessionEvidenceError(ValueError):
    """A session record is incomplete, unsafe, oversized, or inconsistent."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VirtualSessionEvidenceError(
            f"evidence is not canonical JSON: {exc}"
        ) from exc


def _deep_freeze(value: Any) -> Any:
    """Detach and recursively freeze one verified JSON value."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _deep_freeze(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(child) for child in value)
    return value


def _deep_thaw(value: Any) -> Any:
    """Return a detached JSON-compatible copy of a recursively frozen value."""

    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_deep_thaw(child) for child in value]
    return value


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VirtualSessionEvidenceError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_ARTIFACT_BYTES + 1)
    except OSError as exc:
        raise VirtualSessionEvidenceError(f"cannot read evidence file {path}") from exc
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise VirtualSessionEvidenceError(
            f"evidence file exceeds {MAX_ARTIFACT_BYTES} bytes: {path.name}"
        )

    def parse_finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise VirtualSessionEvidenceError(
                f"nonfinite JSON number {value!r} in {path.name}"
            )
        return parsed

    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=parse_finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(
                VirtualSessionEvidenceError(
                    f"nonfinite JSON constant {value!r} in {path.name}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VirtualSessionEvidenceError(
            f"invalid strict JSON in {path.name}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise VirtualSessionEvidenceError(f"{path.name} must contain a JSON object")
    if _canonical_bytes(document) != payload:
        raise VirtualSessionEvidenceError(
            f"evidence file is not canonical JSON: {path.name}"
        )
    return document, payload


def _contained_directory(path: Path) -> Path:
    selected = Path(path)
    if selected.is_symlink():
        raise VirtualSessionEvidenceError("evidence root must not be a symlink")
    root = selected.resolve()
    if not root.is_dir():
        raise VirtualSessionEvidenceError(f"evidence root is missing: {root}")
    return root


def _write_new(path: Path, payload: bytes) -> None:
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise VirtualSessionEvidenceError(
            f"evidence artifact exceeds {MAX_ARTIFACT_BYTES} bytes: {path.name}"
        )
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise VirtualSessionEvidenceError(f"cannot write evidence file {path}") from exc


@dataclass(frozen=True, slots=True)
class VirtualSessionRecord:
    record_id: str
    directory: Path
    manifest_path: Path
    manifest_sha256: str
    report_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "directory": str(self.directory),
            "manifest": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
            "report_hash": self.report_hash,
        }


@dataclass(frozen=True, slots=True)
class VerifiedVirtualSessionRecord:
    manifest_path: Path
    manifest_sha256: str
    report_hash: str
    package_hash: str
    documents: Mapping[str, Mapping[str, Any]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "documents",
            MappingProxyType(
                {name: _deep_freeze(value) for name, value in self.documents.items()}
            ),
        )

    def document(self, name: str) -> Mapping[str, Any]:
        try:
            return self.documents[name]
        except KeyError as exc:
            raise VirtualSessionEvidenceError(
                f"verified package has no artifact {name!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class VirtualSessionReplayReport:
    manifest_sha256: str
    recorded_report_hash: str
    recomputed_report_hash: str
    identical: bool
    recomputed_status: str

    @property
    def status(self) -> str:
        return "REPLAY_IDENTICAL" if self.identical else "REPLAY_DIVERGED"

    def to_dict(self) -> dict[str, Any]:
        value = {
            "schema": "rocell.virtual_session_replay.v1",
            "status": self.status,
            "manifest_sha256": self.manifest_sha256,
            "recorded_report_hash": self.recorded_report_hash,
            "recomputed_report_hash": self.recomputed_report_hash,
            "recomputed_status": self.recomputed_status,
            "identical": self.identical,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }
        return {**value, "replay_hash": _stable_hash(value)}


def _artifact_documents(report: VirtualSessionReport) -> dict[str, dict[str, Any]]:
    return {
        "action-plan.json": report.plan.to_dict(),
        "scenario.json": {
            "schema": "rocell.virtual_session_scenario_evidence.v1",
            "scenario": report.scenario.to_dict(),
            "study_input": report.study_input.to_dict(),
            "trajectory_policy": report.trajectory.policy.to_dict(),
            "physical_release_effect": "NONE",
        },
        "trajectory.json": {
            **report.trajectory.to_dict(),
            "report_hash": report.trajectory.report_hash,
        },
        "events.json": {
            **report.ledger.to_dict(),
            "ledger_hash": report.ledger.ledger_hash,
        },
        "vision.json": dict(report.vision_document),
        "report.json": report.to_dict(),
    }


def record_virtual_session(
    report: VirtualSessionReport,
    evidence_root: Path,
) -> VirtualSessionRecord:
    """Write a complete record atomically; ``manifest.json`` is written last."""

    if not isinstance(report, VirtualSessionReport):
        raise TypeError("report must be a VirtualSessionReport")
    root = _contained_directory(evidence_root)
    record_id = f"virtual-{report.report_hash[:24]}"
    destination = root / record_id
    if os.path.lexists(destination):
        raise VirtualSessionEvidenceError(
            f"immutable evidence record already exists: {record_id}"
        )
    temporary = root / f".partial-{record_id}-{secrets.token_hex(8)}"
    documents = _artifact_documents(report)
    try:
        temporary.mkdir(exist_ok=False)
        manifest_rows: list[dict[str, Any]] = []
        total_bytes = 0
        for filename, role in _ARTIFACT_ROLES:
            payload = _canonical_bytes(documents[filename])
            total_bytes += len(payload)
            if total_bytes > MAX_PACKAGE_BYTES:
                raise VirtualSessionEvidenceError(
                    f"evidence package exceeds {MAX_PACKAGE_BYTES} bytes"
                )
            _write_new(temporary / filename, payload)
            manifest_rows.append(
                {
                    "path": filename,
                    "role": role,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            )
        core: dict[str, Any] = {
            "schema": MANIFEST_SCHEMA,
            "record_id": record_id,
            "report_hash": report.report_hash,
            "artifact_count": len(manifest_rows),
            "total_artifact_bytes": total_bytes,
            "artifacts": manifest_rows,
            "complete": True,
            "manifest_written_last": True,
            "simulation_only": True,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }
        manifest = {**core, "package_hash": _stable_hash(core)}
        manifest_payload = _canonical_bytes(manifest)
        _write_new(temporary / "manifest.json", manifest_payload)
        try:
            temporary.replace(destination)
        except OSError as exc:
            raise VirtualSessionEvidenceError(
                f"cannot atomically finalize evidence record {record_id}"
            ) from exc
    except Exception:
        if temporary.is_dir():
            shutil.rmtree(temporary)
        raise
    manifest_path = destination / "manifest.json"
    return VirtualSessionRecord(
        record_id=record_id,
        directory=destination,
        manifest_path=manifest_path,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        report_hash=report.report_hash,
    )


def _positive_integer(value: object, label: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise VirtualSessionEvidenceError(f"{label} must be a bounded integer")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise VirtualSessionEvidenceError(f"{label} must be lowercase SHA-256")
    return value


def _document_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise VirtualSessionEvidenceError(f"{label} must be a JSON object")
    return value


def _validate_artifact_correlations(
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    """Bind split artifacts and zero-authority claims to the hashed report."""

    report = documents["report.json"]
    legacy_report_fields = {
        "schema",
        "status",
        "pipeline_completed",
        "outcome_verified",
        "virtual_model_complete",
        "bootstrap_hash",
        "scenario",
        "study_input",
        "action_plan",
        "plan_hash",
        "requested_text",
        "virtual_calibrations",
        "trajectory",
        "execution_token",
        "event_ledger",
        "arm_plant",
        "device_plant",
        "outcome_observer",
        "outcome",
        "fault_script",
        "lifecycle_history",
        "ended_at_park",
        "fault_reason",
        "model_and_physical_holds",
        "authority",
        "report_hash",
    }
    report_schema = report.get("schema")
    if report_schema == "rocell.virtual_session_report.v2":
        expected_report_fields = legacy_report_fields
        if "vision.json" in documents:
            raise VirtualSessionEvidenceError(
                "legacy report cannot carry a pixel-vision artifact"
            )
    elif report_schema == "rocell.virtual_session_report.v3":
        expected_report_fields = legacy_report_fields | {
            "pixel_vision_completed",
            "pixel_vision",
        }
        if "vision.json" not in documents:
            raise VirtualSessionEvidenceError(
                "schema-v3 report requires a pixel-vision artifact"
            )
    else:
        raise VirtualSessionEvidenceError("recorded report schema is invalid")
    if set(report) != expected_report_fields:
        raise VirtualSessionEvidenceError("recorded report fields are not exact")

    action_plan = documents["action-plan.json"]
    if set(action_plan) != {
        "schema",
        "device",
        "device_profile",
        "requested_text_sha256",
        "actions",
        "required_calibrations",
    }:
        raise VirtualSessionEvidenceError("action-plan artifact fields are not exact")
    if action_plan != report.get("action_plan"):
        raise VirtualSessionEvidenceError("action-plan artifact differs from report")
    if _stable_hash(dict(action_plan)) != _digest(
        report.get("plan_hash"), "recorded plan hash"
    ):
        raise VirtualSessionEvidenceError("recorded action-plan hash mismatch")

    scenario = documents["scenario.json"]
    if set(scenario) != {
        "schema",
        "scenario",
        "study_input",
        "trajectory_policy",
        "physical_release_effect",
    }:
        raise VirtualSessionEvidenceError("scenario artifact fields are not exact")
    if (
        scenario.get("schema") != "rocell.virtual_session_scenario_evidence.v1"
        or scenario.get("physical_release_effect") != "NONE"
        or scenario.get("scenario") != report.get("scenario")
        or scenario.get("study_input") != report.get("study_input")
    ):
        raise VirtualSessionEvidenceError("scenario artifact differs from report")

    trajectory = documents["trajectory.json"]
    if set(trajectory) != {
        "schema",
        "status",
        "scope",
        "simulation_only",
        "execution_authorized",
        "hardware_accessed",
        "hardware_commands_generated",
        "physical_release_effect",
        "source_provenance",
        "policy",
        "study_input",
        "device",
        "route_target_ids",
        "route_target_count",
        "route_tool_length_mm",
        "effective_park_xy_board_mm",
        "transit_plane_z_mm",
        "geometry",
        "phase_waypoint_counts_final_round",
        "required_motion_phases_present",
        "search",
        "supported_diagnostics",
        "unsupported_diagnostics",
        "limitations",
        "report_hash",
    }:
        raise VirtualSessionEvidenceError("trajectory artifact fields are not exact")
    trajectory_hash = _digest(
        trajectory.get("report_hash"), "recorded trajectory hash"
    )
    trajectory_core = dict(trajectory)
    del trajectory_core["report_hash"]
    if _stable_hash(trajectory_core) != trajectory_hash:
        raise VirtualSessionEvidenceError("recorded trajectory hash mismatch")
    report_trajectory = _document_mapping(
        report.get("trajectory"), "report trajectory summary"
    )
    trajectory_policy = _document_mapping(
        trajectory.get("policy"), "trajectory policy"
    )
    policy_hash = _digest(
        trajectory_policy.get("policy_hash"), "recorded trajectory-policy hash"
    )
    policy_core = dict(trajectory_policy)
    del policy_core["policy_hash"]
    if _stable_hash(policy_core) != policy_hash:
        raise VirtualSessionEvidenceError("recorded trajectory-policy hash mismatch")
    search = _document_mapping(trajectory.get("search"), "trajectory search")
    rounds = search.get("rounds")
    route_target_ids = trajectory.get("route_target_ids")
    if not isinstance(rounds, list) or not isinstance(route_target_ids, list):
        raise VirtualSessionEvidenceError("trajectory route/search collections are invalid")
    route_target_count = _positive_integer(
        trajectory.get("route_target_count"),
        "trajectory route-target count",
        maximum=1_000_000,
    )
    if route_target_count != len(route_target_ids):
        raise VirtualSessionEvidenceError("trajectory route-target count is invalid")
    if rounds:
        final_round = _document_mapping(rounds[-1], "trajectory final round")
        final_waypoints = final_round.get("waypoints")
        if not isinstance(final_waypoints, list):
            raise VirtualSessionEvidenceError("trajectory final waypoints are invalid")
        final_waypoint_count = _positive_integer(
            final_round.get("waypoint_count"),
            "trajectory final-waypoint count",
            maximum=1_000_000,
        )
        if final_waypoint_count != len(final_waypoints):
            raise VirtualSessionEvidenceError("trajectory final-waypoint count is invalid")
        all_final_waypoints_accepted = final_round.get("all_waypoints_accepted")
        if not isinstance(all_final_waypoints_accepted, bool):
            raise VirtualSessionEvidenceError(
                "trajectory final acceptance state is invalid"
            )
    else:
        final_waypoint_count = 0
        all_final_waypoints_accepted = False
    total_ik_solves = _positive_integer(
        search.get("total_ik_solves"),
        "trajectory total IK solves",
        maximum=1_000_000_000,
    )
    expected_trajectory_summary = {
        "report_hash": trajectory_hash,
        "status": trajectory.get("status"),
        "route_target_count": route_target_count,
        "final_waypoint_count": final_waypoint_count,
        "total_ik_solves": total_ik_solves,
        "all_final_waypoints_accepted": all_final_waypoints_accepted,
    }
    if (
        dict(report_trajectory) != expected_trajectory_summary
        or scenario.get("trajectory_policy") != policy_core
    ):
        raise VirtualSessionEvidenceError("trajectory artifact differs from report")

    events = documents["events.json"]
    if set(events) != {
        "schema",
        "token_hash",
        "sealed",
        "maximum_events",
        "event_count",
        "virtual_commands_executed",
        "hardware_commands_generated",
        "events",
        "authority",
        "ledger_hash",
    }:
        raise VirtualSessionEvidenceError("event-ledger artifact fields are not exact")
    ledger_hash = _digest(events.get("ledger_hash"), "recorded ledger hash")
    events_core = dict(events)
    del events_core["ledger_hash"]
    if _stable_hash(events_core) != ledger_hash:
        raise VirtualSessionEvidenceError("recorded event-ledger hash mismatch")
    if events != report.get("event_ledger"):
        raise VirtualSessionEvidenceError("event-ledger artifact differs from report")

    vision = documents["vision.json"]
    if set(vision) != {
        "schema",
        "service_definition_sha256",
        "sealed",
        "maximum_attempts",
        "attempt_count",
        "passed_attempt_count",
        "all_attempts_passed",
        "attempts",
        "input_separation",
        "fixed_overview_fixture",
        "arm_mounted_camera_simulated",
        "robot_frame_correction_applied",
        "authority",
        "ledger_hash",
    }:
        raise VirtualSessionEvidenceError("pixel-vision artifact fields are not exact")
    if vision.get("schema") != "rocell.virtual_pixel_vision_attempt_ledger.v1":
        raise VirtualSessionEvidenceError("pixel-vision artifact schema is invalid")
    try:
        decoded_vision = virtual_pixel_vision_attempt_ledger_from_dict(vision)
    except (TypeError, VirtualPixelVisionError) as exc:
        raise VirtualSessionEvidenceError(
            f"pixel-vision artifact cannot be decoded: {exc}"
        ) from exc
    if decoded_vision.to_dict() != dict(vision):
        raise VirtualSessionEvidenceError(
            "pixel-vision artifact is not canonical normalized evidence"
        )
    vision_hash = _digest(vision.get("ledger_hash"), "pixel-vision ledger hash")
    vision_core = dict(vision)
    del vision_core["ledger_hash"]
    if _stable_hash(vision_core) != vision_hash:
        raise VirtualSessionEvidenceError("pixel-vision ledger hash mismatch")
    attempts = vision.get("attempts")
    if not isinstance(attempts, list):
        raise VirtualSessionEvidenceError("pixel-vision attempts must be an array")
    attempt_count = _positive_integer(
        vision.get("attempt_count"),
        "pixel-vision attempt count",
        maximum=8,
    )
    passed_attempt_count = _positive_integer(
        vision.get("passed_attempt_count"),
        "pixel-vision passed-attempt count",
        maximum=attempt_count,
    )
    if attempt_count != len(attempts):
        raise VirtualSessionEvidenceError("pixel-vision attempt count differs")
    all_attempts_passed = vision.get("all_attempts_passed")
    if not isinstance(all_attempts_passed, bool):
        raise VirtualSessionEvidenceError(
            "pixel-vision all-attempt state must be boolean"
        )
    expected_all_passed = attempt_count > 0 and passed_attempt_count == attempt_count
    if all_attempts_passed is not expected_all_passed:
        raise VirtualSessionEvidenceError(
            "pixel-vision all-attempt state is inconsistent"
        )
    vision_summary = _document_mapping(
        report.get("pixel_vision"), "report pixel-vision summary"
    )
    expected_vision_summary = {
        "ledger_hash": vision_hash,
        "service_definition_sha256": vision.get("service_definition_sha256"),
        "sealed": vision.get("sealed"),
        "attempt_count": attempt_count,
        "passed_attempt_count": passed_attempt_count,
        "all_attempts_passed": all_attempts_passed,
        "fixed_overview_fixture": vision.get("fixed_overview_fixture"),
        "arm_mounted_camera_simulated": vision.get(
            "arm_mounted_camera_simulated"
        ),
        "robot_frame_correction_applied": vision.get(
            "robot_frame_correction_applied"
        ),
    }
    if dict(vision_summary) != expected_vision_summary:
        raise VirtualSessionEvidenceError(
            "pixel-vision artifact differs from report summary"
        )
    action_values = action_plan.get("actions")
    if not isinstance(action_values, list):
        raise VirtualSessionEvidenceError("action-plan actions must be an array")
    expected_vision_attempts = sum(
        isinstance(action, dict)
        and action.get("type") in {"press_key", "tap_phone_target"}
        for action in action_values
    )
    expected_vision_completed = (
        vision.get("sealed") is True
        and expected_all_passed
        and attempt_count == expected_vision_attempts
        and expected_vision_attempts > 0
    )
    if (
        vision.get("sealed") is not True
        or vision.get("fixed_overview_fixture") is not True
        or vision.get("arm_mounted_camera_simulated") is not False
        or vision.get("robot_frame_correction_applied") is not False
        or report.get("pixel_vision_completed") is not expected_vision_completed
    ):
        raise VirtualSessionEvidenceError(
            "pixel-vision scope/completion declaration is invalid"
        )
    raw_events = events.get("events")
    if not isinstance(raw_events, list):
        raise VirtualSessionEvidenceError("event-ledger events must be an array")
    camera_events = [
        item
        for item in raw_events
        if isinstance(item, dict)
        and item.get("component") == "camera"
        and item.get("operation") == "observe"
    ]
    if len(camera_events) != attempt_count:
        raise VirtualSessionEvidenceError(
            "pixel-vision attempts differ from camera observation events"
        )
    for attempt, event in zip(attempts, camera_events):
        if not isinstance(attempt, dict):
            raise VirtualSessionEvidenceError("pixel-vision attempt is malformed")
        result = attempt.get("result")
        if not isinstance(result, dict):
            raise VirtualSessionEvidenceError("pixel-vision result is malformed")
        expected_status = "PASS" if result.get("status") == "PASS" else "FAULT"
        if (
            attempt.get("action_index") != event.get("action_index")
            or attempt.get("target_id") != event.get("target_id")
            or attempt.get("waypoint_sequence") != event.get("waypoint_sequence")
            or event.get("status") != expected_status
        ):
            raise VirtualSessionEvidenceError(
                "pixel-vision attempt differs from camera observation event"
            )

    requested_text = _document_mapping(
        report.get("requested_text"), "requested-text evidence"
    )
    outcome = _document_mapping(report.get("outcome"), "outcome evidence")
    device = _document_mapping(report.get("device_plant"), "device evidence")
    observer = _document_mapping(
        report.get("outcome_observer"),
        "outcome-observer evidence",
    )
    if (
        requested_text.get("plaintext_serialized") is not False
        or outcome.get("raw_output_serialized") is not False
        or device.get("raw_output_serialized") is not False
        or observer.get("raw_output_serialized") is not False
    ):
        raise VirtualSessionEvidenceError(
            "recorded session must not serialize plaintext or raw device output"
        )

    if set(observer) != {
        "schema",
        "observer_id",
        "definition_hash",
        "result_count",
        "result_hashes",
        "action_indices",
        "dispositions",
        "accepted_activation_count",
        "output_sha256",
        "output_length",
        "maximum_results",
        "maximum_output_codepoints",
        "raw_output_serialized",
        "input_contract",
        "authority",
    }:
        raise VirtualSessionEvidenceError("outcome-observer fields are not exact")
    observer_authority = _document_mapping(
        observer.get("authority"),
        "outcome-observer authority",
    )
    expected_observer_authority = {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
        "live_motion_authorized": False,
        "contact_authorized": False,
    }
    if (
        observer.get("schema") != "rocell.virtual_text_outcome_snapshot.v1"
        or observer.get("input_contract") != "CONTACT_RESULT_ONLY"
        or dict(observer_authority) != expected_observer_authority
        or not isinstance(observer.get("observer_id"), str)
        or not observer.get("observer_id")
    ):
        raise VirtualSessionEvidenceError("outcome-observer contract is invalid")
    maximum_results = _positive_integer(
        observer.get("maximum_results"),
        "outcome-observer maximum results",
        maximum=100_000,
    )
    maximum_output = _positive_integer(
        observer.get("maximum_output_codepoints"),
        "outcome-observer maximum output",
        maximum=1_000_000,
    )
    if maximum_results < 1 or maximum_output < 1:
        raise VirtualSessionEvidenceError("outcome-observer bounds must be positive")
    expected_definition_hash = _stable_hash(
        {
            "schema": "rocell.virtual_text_outcome_observer_definition.v1",
            "observer_id": observer["observer_id"],
            "maximum_results": maximum_results,
            "maximum_output_codepoints": maximum_output,
            "input_contract": "CONTACT_RESULT_ONLY",
            "authority": expected_observer_authority,
        }
    )
    if _digest(
        observer.get("definition_hash"),
        "outcome-observer definition hash",
    ) != expected_definition_hash:
        raise VirtualSessionEvidenceError(
            "outcome-observer definition hash is invalid"
        )
    result_hashes = observer.get("result_hashes")
    action_indices = observer.get("action_indices")
    dispositions = observer.get("dispositions")
    if not all(isinstance(value, list) for value in (
        result_hashes,
        action_indices,
        dispositions,
    )):
        raise VirtualSessionEvidenceError("outcome-observer sequences are invalid")
    assert isinstance(result_hashes, list)
    assert isinstance(action_indices, list)
    assert isinstance(dispositions, list)
    result_count = _positive_integer(
        observer.get("result_count"),
        "outcome-observer result count",
        maximum=maximum_results,
    )
    if not result_count == len(result_hashes) == len(action_indices) == len(dispositions):
        raise VirtualSessionEvidenceError("outcome-observer sequence counts differ")
    parsed_result_hashes = [
        _digest(value, "observed contact-result hash") for value in result_hashes
    ]
    if len(parsed_result_hashes) != len(set(parsed_result_hashes)):
        raise VirtualSessionEvidenceError(
            "outcome-observer contains a duplicate contact result"
        )
    parsed_action_indices = [
        _positive_integer(value, "observed action index", maximum=1_000_000_000)
        for value in action_indices
    ]
    if any(
        current <= previous
        for previous, current in zip(parsed_action_indices, parsed_action_indices[1:])
    ):
        raise VirtualSessionEvidenceError(
            "outcome-observer action indices are not strictly increasing"
        )
    allowed_dispositions = {
        "ACCEPTED",
        "MISSED_CONTACT",
        "OUTSIDE_REGION",
        "AMBIGUOUS_REGION",
        "DEPTH_OUT_OF_RANGE",
        "NORMAL_OUT_OF_RANGE",
        "DWELL_OUT_OF_RANGE",
        "CONTACT_POLICY_REJECTED",
        "DEVICE_NOT_FOCUSED",
        "WRONG_UI_STATE",
    }
    if any(value not in allowed_dispositions for value in dispositions):
        raise VirtualSessionEvidenceError(
            "outcome-observer contains an unsupported disposition"
        )
    output_hash = _digest(
        observer.get("output_sha256"),
        "outcome-observer output hash",
    )
    output_length = _positive_integer(
        observer.get("output_length"),
        "outcome-observer output length",
        maximum=maximum_output,
    )
    accepted_count = _positive_integer(
        observer.get("accepted_activation_count"),
        "outcome-observer accepted activation count",
        maximum=maximum_output,
    )
    if accepted_count != output_length:
        raise VirtualSessionEvidenceError(
            "outcome-observer activation/output lengths differ"
        )

    requested_hash = _digest(
        requested_text.get("sha256"),
        "requested-text hash",
    )
    requested_length = _positive_integer(
        requested_text.get("normalized_codepoint_length"),
        "requested-text length",
        maximum=1_000_000,
    )
    observed_matches = output_hash == requested_hash and output_length == requested_length
    declared_matches = outcome.get("matches")
    if (
        outcome.get("expected_sha256") != requested_hash
        or outcome.get("expected_length") != requested_length
        or outcome.get("observed_sha256") != output_hash
        or outcome.get("observed_length") != output_length
        or not isinstance(declared_matches, bool)
        or report.get("outcome_verified") is not declared_matches
        or (declared_matches and not observed_matches)
        or device.get("output_sha256") != output_hash
        or device.get("output_length") != output_length
        or device.get("accepted_contact_count") != accepted_count
        or device.get("attempted_contact_count") != result_count
        or device.get("contact_result_hashes") != parsed_result_hashes
        or device.get("last_contact_result_hash")
        != (parsed_result_hashes[-1] if parsed_result_hashes else None)
    ):
        raise VirtualSessionEvidenceError(
            "device, observer, requested text, and outcome evidence differ"
        )
    authority = _document_mapping(report.get("authority"), "report authority")
    if (
        authority.get("simulation_only") is not True
        or authority.get("execution_authorized") is not False
        or authority.get("hardware_accessed") is not False
        or authority.get("hardware_commands_generated") != 0
        or authority.get("physical_release_effect") != "NONE"
        or authority.get("can_release_physical_gates") is not False
    ):
        raise VirtualSessionEvidenceError("recorded report has nonzero authority")

    # Decode the complete final fault-script value during verification so
    # unknown fields or inconsistent consumed/unconsumed state cannot survive
    # until replay.
    _fault_script_from_report(report)


def _validate_legacy_artifact_correlations(
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    """Retain strict hash/correlation verification for schema-v2 history.

    Legacy packages predate the pixel artifact and are never promoted to the
    current model.  They remain byte-verifiable historical records; replaying
    them with current software is expected to diverge because the current
    session has an additional mandatory pixel boundary.
    """

    report = documents["report.json"]
    expected_report_fields = {
        "schema",
        "status",
        "pipeline_completed",
        "outcome_verified",
        "virtual_model_complete",
        "bootstrap_hash",
        "scenario",
        "study_input",
        "action_plan",
        "plan_hash",
        "requested_text",
        "virtual_calibrations",
        "trajectory",
        "execution_token",
        "event_ledger",
        "arm_plant",
        "device_plant",
        "outcome_observer",
        "outcome",
        "fault_script",
        "lifecycle_history",
        "ended_at_park",
        "fault_reason",
        "model_and_physical_holds",
        "authority",
        "report_hash",
    }
    if (
        report.get("schema") != "rocell.virtual_session_report.v2"
        or set(report) != expected_report_fields
    ):
        raise VirtualSessionEvidenceError(
            "legacy recorded report schema/fields are invalid"
        )
    action_plan = documents["action-plan.json"]
    if action_plan != report.get("action_plan"):
        raise VirtualSessionEvidenceError(
            "legacy action-plan artifact differs from report"
        )
    if _stable_hash(dict(action_plan)) != _digest(
        report.get("plan_hash"), "legacy plan hash"
    ):
        raise VirtualSessionEvidenceError("legacy action-plan hash mismatch")
    scenario = documents["scenario.json"]
    if (
        scenario.get("scenario") != report.get("scenario")
        or scenario.get("study_input") != report.get("study_input")
        or scenario.get("physical_release_effect") != "NONE"
    ):
        raise VirtualSessionEvidenceError("legacy scenario artifact differs")
    trajectory = documents["trajectory.json"]
    trajectory_hash = _digest(
        trajectory.get("report_hash"), "legacy trajectory hash"
    )
    trajectory_core = dict(trajectory)
    del trajectory_core["report_hash"]
    report_trajectory = _document_mapping(
        report.get("trajectory"), "legacy report trajectory"
    )
    if (
        _stable_hash(trajectory_core) != trajectory_hash
        or report_trajectory.get("report_hash") != trajectory_hash
    ):
        raise VirtualSessionEvidenceError("legacy trajectory hash/correlation mismatch")
    events = documents["events.json"]
    events_hash = _digest(events.get("ledger_hash"), "legacy event-ledger hash")
    events_core = dict(events)
    del events_core["ledger_hash"]
    if _stable_hash(events_core) != events_hash or events != report.get("event_ledger"):
        raise VirtualSessionEvidenceError("legacy event-ledger hash/correlation mismatch")
    authority = _document_mapping(report.get("authority"), "legacy report authority")
    if (
        authority.get("simulation_only") is not True
        or authority.get("execution_authorized") is not False
        or authority.get("hardware_accessed") is not False
        or authority.get("hardware_commands_generated") != 0
        or authority.get("physical_release_effect") != "NONE"
        or authority.get("can_release_physical_gates") is not False
    ):
        raise VirtualSessionEvidenceError("legacy report has nonzero authority")
    _fault_script_from_report(report)


def verify_virtual_session_record(manifest_path: Path) -> VerifiedVirtualSessionRecord:
    """Strictly verify bytes, names, counts, hashes, and report/package identity."""

    requested = Path(manifest_path)
    if requested.is_symlink() or requested.parent.is_symlink():
        raise VirtualSessionEvidenceError(
            "manifest and evidence directory must not be symlinks"
        )
    try:
        selected = requested.resolve(strict=True)
    except OSError as exc:
        raise VirtualSessionEvidenceError(
            "manifest path must name an existing manifest.json"
        ) from exc
    if selected.name != "manifest.json" or not selected.is_file():
        raise VirtualSessionEvidenceError("manifest path must name an existing manifest.json")
    directory = selected.parent
    try:
        entries = tuple(directory.iterdir())
    except OSError as exc:
        raise VirtualSessionEvidenceError(
            f"cannot inspect evidence directory {directory}"
        ) from exc
    actual_names = {path.name for path in entries if path.is_file()}
    unsafe_entries = [
        path.name for path in entries if path.is_symlink() or not path.is_file()
    ]
    if actual_names == _EXPECTED_FILES:
        artifact_roles = _ARTIFACT_ROLES
        expected_manifest_schema = MANIFEST_SCHEMA
    elif actual_names == _LEGACY_EXPECTED_FILES:
        artifact_roles = _LEGACY_ARTIFACT_ROLES
        expected_manifest_schema = LEGACY_MANIFEST_SCHEMA
    else:
        artifact_roles = ()
        expected_manifest_schema = ""
    if not artifact_roles or unsafe_entries:
        raise VirtualSessionEvidenceError(
            "evidence directory is not exact; "
            f"files={sorted(actual_names)}, other={sorted(unsafe_entries)}"
        )
    manifest, manifest_payload = _read_json(selected)
    if set(manifest) != _MANIFEST_FIELDS:
        raise VirtualSessionEvidenceError("manifest fields are not exact")
    if (
        manifest.get("schema") != expected_manifest_schema
        or manifest.get("complete") is not True
        or manifest.get("manifest_written_last") is not True
        or manifest.get("simulation_only") is not True
        or manifest.get("physical_release_effect") != "NONE"
    ):
        raise VirtualSessionEvidenceError("manifest schema, completeness, or authority is invalid")
    if _positive_integer(
        manifest.get("hardware_commands_generated"),
        "manifest hardware-command count",
        maximum=0,
    ) != 0:
        raise VirtualSessionEvidenceError("manifest authority is invalid")
    record_id = manifest.get("record_id")
    if (
        not isinstance(record_id, str)
        or _RECORD_ID.fullmatch(record_id) is None
        or directory.name != record_id
    ):
        raise VirtualSessionEvidenceError("manifest record identity/path is invalid")
    package_hash = _digest(manifest.get("package_hash"), "package hash")
    core = dict(manifest)
    del core["package_hash"]
    if _stable_hash(core) != package_hash:
        raise VirtualSessionEvidenceError("manifest package hash mismatch")
    raw_rows = manifest.get("artifacts")
    artifact_count = _positive_integer(
        manifest.get("artifact_count"),
        "manifest artifact count",
        maximum=len(artifact_roles),
    )
    declared_total = _positive_integer(
        manifest.get("total_artifact_bytes"),
        "manifest total artifact bytes",
        maximum=MAX_PACKAGE_BYTES,
    )
    if (
        not isinstance(raw_rows, list)
        or len(raw_rows) != len(artifact_roles)
        or artifact_count != len(artifact_roles)
    ):
        raise VirtualSessionEvidenceError("manifest artifact list is not exact")
    expected_roles = dict(artifact_roles)
    documents: dict[str, Mapping[str, Any]] = {}
    total = 0
    seen: set[str] = set()
    for row in raw_rows:
        if not isinstance(row, dict) or set(row) != {"path", "role", "sha256", "bytes"}:
            raise VirtualSessionEvidenceError("manifest artifact row is malformed")
        name = row.get("path")
        if not isinstance(name, str):
            raise VirtualSessionEvidenceError("manifest artifact path must be a string")
        if Path(name).name != name or Path(name).is_absolute():
            raise VirtualSessionEvidenceError("manifest artifact path must be a plain filename")
        if name not in expected_roles or name in seen:
            raise VirtualSessionEvidenceError("manifest artifact path is unknown or duplicated")
        seen.add(name)
        if row.get("role") != expected_roles[name]:
            raise VirtualSessionEvidenceError(f"artifact role mismatch for {name}")
        expected_bytes = _positive_integer(
            row.get("bytes"), f"{name} bytes", maximum=MAX_ARTIFACT_BYTES
        )
        expected_hash = _digest(row.get("sha256"), f"{name} hash")
        artifact_path = directory / name
        try:
            resolved_artifact = artifact_path.resolve(strict=True)
        except OSError as exc:
            raise VirtualSessionEvidenceError(
                f"cannot resolve evidence artifact {name}"
            ) from exc
        if artifact_path.is_symlink() or resolved_artifact.parent != directory:
            raise VirtualSessionEvidenceError(
                f"evidence artifact escapes its record directory: {name}"
            )
        document, payload = _read_json(resolved_artifact)
        if len(payload) != expected_bytes or hashlib.sha256(payload).hexdigest() != expected_hash:
            raise VirtualSessionEvidenceError(f"artifact byte/hash mismatch for {name}")
        total += len(payload)
        if total > MAX_PACKAGE_BYTES:
            raise VirtualSessionEvidenceError(
                f"evidence package exceeds {MAX_PACKAGE_BYTES} bytes"
            )
        documents[name] = document
    if seen != set(expected_roles):
        raise VirtualSessionEvidenceError("manifest artifact set is incomplete")
    if total != declared_total or total > MAX_PACKAGE_BYTES:
        raise VirtualSessionEvidenceError("manifest total byte count is invalid")
    report = documents["report.json"]
    recorded_hash = _digest(report.get("report_hash"), "recorded report hash")
    report_core = dict(report)
    del report_core["report_hash"]
    if _stable_hash(report_core) != recorded_hash or manifest.get("report_hash") != recorded_hash:
        raise VirtualSessionEvidenceError("recorded report hash mismatch")
    if record_id != f"virtual-{recorded_hash[:24]}":
        raise VirtualSessionEvidenceError("record directory is not derived from report hash")

    if expected_manifest_schema == LEGACY_MANIFEST_SCHEMA:
        _validate_legacy_artifact_correlations(documents)
    else:
        _validate_artifact_correlations(documents)
    return VerifiedVirtualSessionRecord(
        manifest_path=selected,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        report_hash=recorded_hash,
        package_hash=package_hash,
        documents=documents,
    )


def _reconstruct_text(plan: Mapping[str, Any]) -> tuple[str, str]:
    device = plan.get("device")
    profile_id = plan.get("device_profile")
    actions = plan.get("actions")
    if device not in {"keyboard", "phone"} or not isinstance(profile_id, str):
        raise VirtualSessionEvidenceError("recorded action plan device/profile is invalid")
    if not isinstance(actions, list):
        raise VirtualSessionEvidenceError("recorded action plan actions must be a list")
    if device == "keyboard":
        keyboard_profile = development_keyboard_profile()
        selected_profile_id = keyboard_profile.profile_id
        inverse: dict[str, str] = {}
        for character, targets in keyboard_profile.character_keys.items():
            if len(targets) != 1 or targets[0] in inverse:
                raise VirtualSessionEvidenceError("keyboard replay mapping is ambiguous")
            inverse[targets[0]] = character
        text = ""
        for action in actions:
            if not isinstance(action, dict) or set(action) != {"type", "key"}:
                raise VirtualSessionEvidenceError("recorded keyboard action is malformed")
            if action.get("type") != "press_key" or action.get("key") not in inverse:
                raise VirtualSessionEvidenceError("recorded keyboard target is unsupported")
            text += inverse[str(action["key"])]
    else:
        phone = development_phone_profile()
        selected_profile_id = phone.profile_id
        inverse = {}
        for character, spec in phone.character_targets.items():
            if spec.target_id in inverse:
                raise VirtualSessionEvidenceError("phone replay mapping is ambiguous")
            inverse[spec.target_id] = character
        characters: list[str] = []
        for action in actions:
            if not isinstance(action, dict) or not isinstance(action.get("type"), str):
                raise VirtualSessionEvidenceError("recorded phone action is malformed")
            if action["type"] == "verify_phone_state":
                continue
            target = action.get("target")
            if action["type"] != "tap_phone_target" or target not in inverse:
                raise VirtualSessionEvidenceError("recorded phone target is unsupported")
            characters.append(inverse[str(target)])
        text = "".join(characters)
    if selected_profile_id != profile_id:
        raise VirtualSessionEvidenceError("recorded semantic profile identity changed")
    compiled: ActionPlan = compile_development_text(device, text)
    if compiled.to_dict() != dict(plan):
        raise VirtualSessionEvidenceError("recorded action plan does not recompile identically")
    return device, text


def _fault_script_from_report(report: Mapping[str, Any]) -> VirtualFaultScript:
    raw = report.get("fault_script")
    if not isinstance(raw, dict):
        raise VirtualSessionEvidenceError("recorded fault script is missing")
    if set(raw) != {
        "schema",
        "script_id",
        "definition_hash",
        "trigger_count",
        "triggers",
        "consumed_trigger_ids",
        "unconsumed_trigger_ids",
        "authority",
    }:
        raise VirtualSessionEvidenceError("recorded fault script fields are not exact")
    script_id = raw.get("script_id")
    triggers = raw.get("triggers")
    consumed = raw.get("consumed_trigger_ids")
    if (
        not isinstance(script_id, str)
        or not isinstance(triggers, list)
        or not isinstance(consumed, list)
    ):
        raise VirtualSessionEvidenceError("recorded fault script definition is malformed")
    parsed: list[VirtualFaultTrigger] = []
    for item in triggers:
        if not isinstance(item, dict) or set(item) != {
            "trigger_id",
            "kind",
            "component",
            "operation",
            "occurrence",
            "action_index",
            "target_id",
            "waypoint_sequence",
            "parameter",
        }:
            raise VirtualSessionEvidenceError("recorded fault trigger is malformed")
        try:
            parsed.append(
                VirtualFaultTrigger(
                    trigger_id=item["trigger_id"],
                    kind=VirtualFaultKind(item["kind"]),
                    component=item["component"],
                    operation=item["operation"],
                    occurrence=item["occurrence"],
                    action_index=item.get("action_index"),
                    target_id=item.get("target_id"),
                    waypoint_sequence=item.get("waypoint_sequence"),
                    parameter=item.get("parameter"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise VirtualSessionEvidenceError(
                f"recorded fault trigger cannot be decoded: {exc}"
            ) from exc
    try:
        final_script = VirtualFaultScript(
            script_id,
            tuple(parsed),
            frozenset(consumed),
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise VirtualSessionEvidenceError(
            f"recorded fault script cannot be decoded: {exc}"
        ) from exc
    if final_script.to_dict() != raw:
        raise VirtualSessionEvidenceError("recorded fault script state/hash mismatch")
    # Replay begins with the same definition in its unconsumed state; the
    # deterministic run must reproduce the recorded final consumption state.
    return VirtualFaultScript(script_id, tuple(parsed))


def replay_virtual_session(
    workspace: Path,
    manifest_path: Path,
    *,
    runtime_path: Path | None = None,
) -> VirtualSessionReplayReport:
    """Verify a record, rerun the full planner/executor, and compare all bytes."""

    verified = verify_virtual_session_record(manifest_path)
    action_plan = _deep_thaw(verified.document("action-plan.json"))
    device, text = _reconstruct_text(action_plan)
    recorded_report = _deep_thaw(verified.document("report.json"))
    script = _fault_script_from_report(recorded_report)
    recomputed = run_default_virtual_session(
        Path(workspace),
        device,
        text,
        runtime_path=runtime_path,
        fault_script=script,
    )
    recomputed_documents = _artifact_documents(recomputed)
    compared_roles = tuple(
        (name, role)
        for name, role in _ARTIFACT_ROLES
        if name in verified.documents
    )
    recorded_documents = {
        name: _deep_thaw(verified.document(name)) for name, _ in compared_roles
    }
    identical = all(
        _canonical_bytes(recomputed_documents[name])
        == _canonical_bytes(recorded_documents[name])
        for name, _ in compared_roles
    )
    return VirtualSessionReplayReport(
        manifest_sha256=verified.manifest_sha256,
        recorded_report_hash=verified.report_hash,
        recomputed_report_hash=recomputed.report_hash,
        identical=identical,
        recomputed_status=recomputed.status,
    )


__all__ = [
    "MANIFEST_SCHEMA",
    "LEGACY_MANIFEST_SCHEMA",
    "MAX_ARTIFACT_BYTES",
    "MAX_PACKAGE_BYTES",
    "VerifiedVirtualSessionRecord",
    "VirtualSessionEvidenceError",
    "VirtualSessionRecord",
    "VirtualSessionReplayReport",
    "record_virtual_session",
    "replay_virtual_session",
    "verify_virtual_session_record",
]
