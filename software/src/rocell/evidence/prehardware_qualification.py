"""Immutable evidence packages for prehardware qualification campaigns.

The aggregate qualification report intentionally retains child service reports
by digest rather than embedding their potentially large evidence.  This module
records that compact aggregate as a schema-separated, bounded package whose
split artifacts are all correlated back to the canonical report.  Replay first
verifies every package byte and then reruns the locked public qualification
service; no recorded result is trusted as an execution oracle.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
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
from typing import Any, cast

from rocell.application.mission_route_coverage import MissionRouteCoveragePolicy
from rocell.application.prehardware_qualification import (
    PREHARDWARE_QUALIFICATION_SCHEMA,
    PrehardwareQualificationPolicy,
    PrehardwareQualificationReport,
    QualificationCaseResult,
    run_prehardware_qualification,
)


MANIFEST_SCHEMA = "rocell.prehardware_qualification_evidence_manifest.v1"
SOURCE_ARTIFACT_SCHEMA = "rocell.prehardware_qualification_source_evidence.v1"
CASES_ARTIFACT_SCHEMA = "rocell.prehardware_qualification_cases_evidence.v1"
COVERAGE_ARTIFACT_SCHEMA = "rocell.prehardware_qualification_coverage_evidence.v1"
RESOURCES_ARTIFACT_SCHEMA = "rocell.prehardware_qualification_resources_evidence.v1"
REPLAY_SCHEMA = "rocell.prehardware_qualification_replay.v1"

# Qualification reports are compact by design.  These limits leave substantial
# headroom for the standard 17-case report while preventing evidence loading
# from becoming an unbounded JSON or filesystem operation.
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_PACKAGE_BYTES = 8 * 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECORD_ID = re.compile(r"^qualification-([0-9a-f]{24})$")
_ARTIFACT_ROLES: tuple[tuple[str, str], ...] = (
    ("source.json", "QUALIFICATION_SOURCE_SNAPSHOT"),
    ("policy.json", "LOCKED_QUALIFICATION_POLICY"),
    ("cases.json", "ORDERED_QUALIFICATION_CASE_RESULTS"),
    ("coverage.json", "MISSION_ROUTE_COVERAGE_SUMMARY"),
    ("resources.json", "QUALIFICATION_RESOURCES_AND_AUTHORITY"),
    ("report.json", "PREHARDWARE_QUALIFICATION_REPORT"),
)
_EXPECTED_FILES = frozenset(
    {filename for filename, _ in _ARTIFACT_ROLES} | {"manifest.json"}
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "record_id",
        "profile",
        "report_sha256",
        "source_sha256",
        "policy_sha256",
        "case_count",
        "ordered_case_results_sha256",
        "ordered_child_reports_sha256",
        "resource_usage_sha256",
        "artifact_count",
        "total_artifact_bytes",
        "artifacts",
        "complete",
        "manifest_written_last",
        "simulation_only",
        "hardware_commands_generated",
        "physical_release_effect",
        "package_sha256",
    }
)
_REPORT_FIELDS = frozenset(
    {
        "schema",
        "status",
        "profile",
        "campaign_passed",
        "diagnostic_pass",
        "physical_ready",
        "coverage_evaluated",
        "coverage_state",
        "all_mission_routes_accepted",
        "source",
        "policy",
        "case_summary",
        "cases",
        "coverage_summary",
        "resource_usage",
        "final_source_revalidation_passed",
        "physical_holds",
        "limitations",
        "evidence_recording",
        "authority",
        "report_sha256",
    }
)
_POLICY_FIELDS = frozenset(
    {
        "schema",
        "catalog_id",
        "profile",
        "maximum_cases",
        "maximum_session_runs",
        "maximum_total_virtual_commands",
        "maximum_total_camera_captures",
        "maximum_total_legacy_events",
        "includes_full_catalog_coverage",
        "route_policy",
        "selected_cases",
        "selected_case_count",
        "wall_clock_time_is_evidence",
        "policy_sha256",
    }
)
_CASE_RESULT_FIELDS = frozenset(
    {
        "case",
        "observed_status",
        "passed",
        "source_report_sha256",
        "authority_verified",
        "metrics",
        "case_result_sha256",
    }
)
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "jpeg_bytes",
        "image_bytes",
        "raw_output",
        "plaintext",
        "requested_text_value",
        "truth_translation_wv_mm",
        "truth_yaw_board_deg",
        "synthetic_truth_transform",
    }
)


class PrehardwareQualificationEvidenceError(ValueError):
    """A qualification record is incomplete, unsafe, or inconsistent."""


def _stable_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PrehardwareQualificationEvidenceError(
            f"evidence is not finite canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


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
        raise PrehardwareQualificationEvidenceError(
            f"evidence is not canonical JSON: {exc}"
        ) from exc


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _deep_freeze(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(child) for child in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_deep_thaw(child) for child in value]
    return value


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PrehardwareQualificationEvidenceError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_ARTIFACT_BYTES + 1)
    except OSError as exc:
        raise PrehardwareQualificationEvidenceError(
            f"cannot read qualification evidence file {path}"
        ) from exc
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise PrehardwareQualificationEvidenceError(
            f"qualification evidence file exceeds {MAX_ARTIFACT_BYTES} bytes: "
            f"{path.name}"
        )

    def parse_finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise PrehardwareQualificationEvidenceError(
                f"nonfinite JSON number {value!r} in {path.name}"
            )
        return parsed

    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=parse_finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(
                PrehardwareQualificationEvidenceError(
                    f"nonfinite JSON constant {value!r} in {path.name}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrehardwareQualificationEvidenceError(
            f"invalid strict JSON in {path.name}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise PrehardwareQualificationEvidenceError(
            f"{path.name} must contain a JSON object"
        )
    if _canonical_bytes(document) != payload:
        raise PrehardwareQualificationEvidenceError(
            f"qualification evidence file is not canonical JSON: {path.name}"
        )
    return document, payload


def _contained_directory(path: Path) -> Path:
    selected = Path(path)
    if any(candidate.is_symlink() for candidate in (selected, *selected.parents)):
        raise PrehardwareQualificationEvidenceError(
            "qualification evidence root must not be a symlink"
        )
    root = selected.resolve()
    if not root.is_dir():
        raise PrehardwareQualificationEvidenceError(
            f"qualification evidence root is missing: {root}"
        )
    return root


def _write_new(path: Path, payload: bytes) -> None:
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise PrehardwareQualificationEvidenceError(
            f"qualification evidence artifact exceeds {MAX_ARTIFACT_BYTES} "
            f"bytes: {path.name}"
        )
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise PrehardwareQualificationEvidenceError(
            f"cannot write qualification evidence file {path}"
        ) from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PrehardwareQualificationEvidenceError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _bounded_integer(value: object, label: str, *, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise PrehardwareQualificationEvidenceError(
            f"{label} must be a bounded nonnegative integer"
        )
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PrehardwareQualificationEvidenceError(f"{label} must be a JSON object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PrehardwareQualificationEvidenceError(f"{label} must be a JSON array")
    return value


def _validate_zero_authority_and_redaction(value: object) -> None:
    """Reject authority escalation and raw/private payload fields recursively."""

    false_fields = {
        "execution_authorized",
        "hardware_accessed",
        "hardware_access_allowed",
        "live_hardware_access_allowed",
        "live_motion_authorized",
        "physical_camera_accessed",
        "physical_contact_authorized",
        "contact_authorized",
        "can_release_physical_gates",
    }

    def visit(node: object) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                lowered = key.lower()
                if lowered in _FORBIDDEN_PAYLOAD_KEYS:
                    raise PrehardwareQualificationEvidenceError(
                        f"qualification evidence contains forbidden payload {key!r}"
                    )
                if key == "simulation_only" and child is not True:
                    raise PrehardwareQualificationEvidenceError(
                        "qualification evidence lost simulation-only scope"
                    )
                if key in false_fields and child is not False:
                    raise PrehardwareQualificationEvidenceError(
                        f"qualification evidence authority field {key!r} is nonzero"
                    )
                if key == "hardware_commands_generated" and (
                    isinstance(child, bool) or child != 0
                ):
                    raise PrehardwareQualificationEvidenceError(
                        "qualification evidence contains hardware commands"
                    )
                if key == "physical_release_effect" and child != "NONE":
                    raise PrehardwareQualificationEvidenceError(
                        "qualification evidence has a physical release effect"
                    )
                if (
                    key
                    in {
                        "plaintext_serialized",
                        "jpeg_bytes_serialized",
                        "raw_output_serialized",
                        "transform_serialized",
                    }
                    and child is not False
                ):
                    raise PrehardwareQualificationEvidenceError(
                        f"qualification evidence serializes private payload via {key!r}"
                    )
                visit(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)

    visit(value)


@dataclass(frozen=True, slots=True)
class PrehardwareQualificationEvidenceRecord:
    record_id: str
    directory: Path
    manifest_path: Path
    manifest_sha256: str
    report_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.prehardware_qualification_evidence_record.v1",
            "record_id": self.record_id,
            "directory": str(self.directory),
            "manifest": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
            "qualification_report_sha256": self.report_sha256,
            "recorded": True,
            "replay_supported": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }


@dataclass(frozen=True, slots=True)
class VerifiedPrehardwareQualificationEvidence:
    manifest_path: Path
    manifest_sha256: str
    package_sha256: str
    report_sha256: str
    profile: str
    case_count: int
    documents: Mapping[str, Mapping[str, Any]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "documents",
            MappingProxyType(
                {
                    name: _deep_freeze(document)
                    for name, document in self.documents.items()
                }
            ),
        )

    def document(self, name: str) -> Mapping[str, Any]:
        try:
            return self.documents[name]
        except KeyError as exc:
            raise PrehardwareQualificationEvidenceError(
                f"verified qualification package has no artifact {name!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class PrehardwareQualificationReplayReport:
    manifest_sha256: str
    recorded_report_sha256: str
    recomputed_report_sha256: str
    profile: str
    recomputed_status: str
    compared_artifact_count: int
    identical: bool

    def __post_init__(self) -> None:
        _digest(self.manifest_sha256, "replay manifest sha256")
        _digest(self.recorded_report_sha256, "recorded report sha256")
        _digest(self.recomputed_report_sha256, "recomputed report sha256")
        if self.profile not in {"quick", "standard"}:
            raise PrehardwareQualificationEvidenceError(
                "replay profile must be quick or standard"
            )
        if not isinstance(self.recomputed_status, str) or not self.recomputed_status:
            raise PrehardwareQualificationEvidenceError(
                "recomputed replay status must be non-empty"
            )
        _bounded_integer(
            self.compared_artifact_count,
            "compared artifact count",
            maximum=len(_ARTIFACT_ROLES),
        )
        if not isinstance(self.identical, bool):
            raise PrehardwareQualificationEvidenceError(
                "replay identical state must be boolean"
            )

    @property
    def status(self) -> str:
        return (
            "QUALIFICATION_REPLAY_IDENTICAL"
            if self.identical
            else "QUALIFICATION_REPLAY_DIVERGED"
        )

    def to_dict(self) -> dict[str, Any]:
        core = {
            "schema": REPLAY_SCHEMA,
            "status": self.status,
            "profile": self.profile,
            "manifest_sha256": self.manifest_sha256,
            "recorded_report_sha256": self.recorded_report_sha256,
            "recomputed_report_sha256": self.recomputed_report_sha256,
            "recomputed_status": self.recomputed_status,
            "compared_artifact_count": self.compared_artifact_count,
            "identical": self.identical,
            "simulation_only": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "execution_authorized": False,
            "physical_release_effect": "NONE",
        }
        return {**core, "replay_sha256": _stable_hash(core)}


def _artifact_documents(
    report: PrehardwareQualificationReport,
) -> dict[str, dict[str, Any]]:
    # Keep the issued v1 report byte-for-byte unchanged.  Its embedded
    # ``evidence_recording`` value describes the campaign runner itself, which
    # did not write a package while cases were executing.  The outer manifest
    # and ``PrehardwareQualificationEvidenceRecord`` are the authoritative
    # declaration that this later, explicit record/replay operation occurred.
    document = report.to_dict()
    source = cast(dict[str, Any], document["source"])
    policy = cast(dict[str, Any], document["policy"])
    cases = cast(list[dict[str, Any]], document["cases"])
    coverage = cast(dict[str, Any], document["coverage_summary"])
    resources = cast(dict[str, Any], document["resource_usage"])
    case_result_hashes = [item["case_result_sha256"] for item in cases]
    child_report_hashes = [item["source_report_sha256"] for item in cases]
    return {
        "source.json": {
            "schema": SOURCE_ARTIFACT_SCHEMA,
            "source": source,
            "source_sha256": _stable_hash(source),
        },
        "policy.json": policy,
        "cases.json": {
            "schema": CASES_ARTIFACT_SCHEMA,
            "case_summary": document["case_summary"],
            "case_count": len(cases),
            "ordered_case_ids": [item["case"]["case_id"] for item in cases],
            "ordered_case_result_sha256s": case_result_hashes,
            "ordered_child_report_sha256s": child_report_hashes,
            "cases": cases,
        },
        "coverage.json": {
            "schema": COVERAGE_ARTIFACT_SCHEMA,
            "coverage_evaluated": document["coverage_evaluated"],
            "coverage_state": document["coverage_state"],
            "all_mission_routes_accepted": document["all_mission_routes_accepted"],
            "coverage_summary": coverage,
        },
        "resources.json": {
            "schema": RESOURCES_ARTIFACT_SCHEMA,
            "resource_usage": resources,
            "resource_usage_sha256": _stable_hash(resources),
            "physical_holds": document["physical_holds"],
            "final_source_revalidation_passed": document[
                "final_source_revalidation_passed"
            ],
            "physical_ready": document["physical_ready"],
            "authority": document["authority"],
        },
        "report.json": document,
    }


def record_prehardware_qualification(
    report: PrehardwareQualificationReport,
    evidence_root: Path,
) -> PrehardwareQualificationEvidenceRecord:
    """Atomically record one compact qualification package.

    Every artifact is written into a private partial directory.  The manifest
    is written last, and only a complete directory is renamed into its final,
    content-addressed identity.
    """

    if not isinstance(report, PrehardwareQualificationReport):
        raise TypeError("report must be a PrehardwareQualificationReport")
    root = _contained_directory(evidence_root)
    documents = _artifact_documents(report)
    _validate_zero_authority_and_redaction(documents)
    record_id = f"qualification-{report.report_hash[:24]}"
    destination = root / record_id
    if os.path.lexists(destination):
        raise PrehardwareQualificationEvidenceError(
            f"immutable qualification evidence already exists: {record_id}"
        )
    temporary = root / f".partial-{record_id}-{secrets.token_hex(8)}"
    manifest_payload = b""
    try:
        temporary.mkdir(exist_ok=False)
        rows: list[dict[str, Any]] = []
        total_bytes = 0
        for filename, role in _ARTIFACT_ROLES:
            payload = _canonical_bytes(documents[filename])
            total_bytes += len(payload)
            if total_bytes > MAX_PACKAGE_BYTES:
                raise PrehardwareQualificationEvidenceError(
                    f"qualification evidence package exceeds {MAX_PACKAGE_BYTES} bytes"
                )
            _write_new(temporary / filename, payload)
            rows.append(
                {
                    "path": filename,
                    "role": role,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            )
        cases_document = documents["cases.json"]
        source_document = documents["source.json"]
        resources_document = documents["resources.json"]
        core: dict[str, Any] = {
            "schema": MANIFEST_SCHEMA,
            "record_id": record_id,
            "profile": report.profile,
            "report_sha256": report.report_hash,
            "source_sha256": source_document["source_sha256"],
            "policy_sha256": report.policy.policy_hash,
            "case_count": len(report.cases),
            "ordered_case_results_sha256": _stable_hash(
                cases_document["ordered_case_result_sha256s"]
            ),
            "ordered_child_reports_sha256": _stable_hash(
                cases_document["ordered_child_report_sha256s"]
            ),
            "resource_usage_sha256": resources_document["resource_usage_sha256"],
            "artifact_count": len(rows),
            "total_artifact_bytes": total_bytes,
            "artifacts": rows,
            "complete": True,
            "manifest_written_last": True,
            "simulation_only": True,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }
        manifest = {**core, "package_sha256": _stable_hash(core)}
        manifest_payload = _canonical_bytes(manifest)
        _write_new(temporary / "manifest.json", manifest_payload)
        try:
            temporary.replace(destination)
        except OSError as exc:
            raise PrehardwareQualificationEvidenceError(
                f"cannot atomically finalize qualification evidence {record_id}"
            ) from exc
    except Exception:
        if temporary.is_dir():
            shutil.rmtree(temporary)
        raise
    return PrehardwareQualificationEvidenceRecord(
        record_id=record_id,
        directory=destination,
        manifest_path=destination / "manifest.json",
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        report_sha256=report.report_hash,
    )


def _policy_from_document(
    value: Mapping[str, Any],
) -> PrehardwareQualificationPolicy:
    if set(value) != _POLICY_FIELDS:
        raise PrehardwareQualificationEvidenceError(
            "recorded qualification policy fields are not exact"
        )
    route_value = _mapping(value.get("route_policy"), "recorded route policy")
    try:
        route = MissionRouteCoveragePolicy(
            orchestration_chunk_size=cast(
                int, route_value.get("orchestration_chunk_size")
            ),
            maximum_cartesian_step_mm=cast(
                float, route_value.get("maximum_cartesian_step_mm")
            ),
            maximum_joint_step_rad=cast(
                float, route_value.get("maximum_joint_step_rad")
            ),
            minimum_normalized_arm_joint_margin=cast(
                float,
                route_value.get("minimum_normalized_arm_joint_margin"),
            ),
            maximum_refinement_rounds=cast(
                int, route_value.get("maximum_refinement_rounds")
            ),
            maximum_waypoints_per_round=cast(
                int, route_value.get("maximum_waypoints_per_round")
            ),
            maximum_total_ik_solves_per_route=cast(
                int,
                route_value.get("maximum_total_ik_solves_per_route"),
            ),
        )
        policy = PrehardwareQualificationPolicy(
            profile=cast(str, value.get("profile")),
            maximum_cases=cast(int, value.get("maximum_cases")),
            maximum_session_runs=cast(int, value.get("maximum_session_runs")),
            maximum_total_virtual_commands=cast(
                int, value.get("maximum_total_virtual_commands")
            ),
            maximum_total_camera_captures=cast(
                int, value.get("maximum_total_camera_captures")
            ),
            maximum_total_legacy_events=cast(
                int, value.get("maximum_total_legacy_events")
            ),
            route_policy=route,
        )
    except (TypeError, ValueError) as exc:
        raise PrehardwareQualificationEvidenceError(
            f"recorded qualification policy cannot be reconstructed: {exc}"
        ) from exc
    expected = {**policy.to_dict(), "policy_sha256": policy.policy_hash}
    if _deep_thaw(value) != expected:
        raise PrehardwareQualificationEvidenceError(
            "recorded qualification policy differs from its locked definition"
        )
    return policy


def _report_from_documents(
    documents: Mapping[str, Mapping[str, Any]],
) -> PrehardwareQualificationReport:
    report_document = documents["report.json"]
    if (
        set(report_document) != _REPORT_FIELDS
        or report_document.get("schema") != PREHARDWARE_QUALIFICATION_SCHEMA
    ):
        raise PrehardwareQualificationEvidenceError(
            "recorded qualification report schema/fields are invalid"
        )
    recorded_report_hash = _digest(
        report_document.get("report_sha256"),
        "recorded qualification report sha256",
    )
    report_core = dict(report_document)
    del report_core["report_sha256"]
    if _stable_hash(report_core) != recorded_report_hash:
        raise PrehardwareQualificationEvidenceError(
            "recorded qualification report hash is invalid"
        )
    _validate_zero_authority_and_redaction(report_document)

    policy_document = documents["policy.json"]
    policy = _policy_from_document(policy_document)
    if report_document.get("policy") != dict(policy_document):
        raise PrehardwareQualificationEvidenceError(
            "policy artifact differs from qualification report"
        )

    raw_cases = _array(report_document.get("cases"), "recorded qualification cases")
    if len(raw_cases) != len(policy.selected_cases):
        raise PrehardwareQualificationEvidenceError(
            "recorded case count differs from locked policy"
        )
    parsed_cases: list[QualificationCaseResult] = []
    for index, (raw_case, expected_spec) in enumerate(
        zip(raw_cases, policy.selected_cases)
    ):
        case = _mapping(raw_case, f"recorded case {index}")
        if set(case) != _CASE_RESULT_FIELDS:
            raise PrehardwareQualificationEvidenceError(
                f"recorded case {index} fields are not exact"
            )
        if case.get("case") != expected_spec.to_dict():
            raise PrehardwareQualificationEvidenceError(
                f"recorded case {index} differs from the locked case definition"
            )
        metrics = _mapping(case.get("metrics"), f"recorded case {index} metrics")
        try:
            result = QualificationCaseResult(
                spec=expected_spec,
                observed_status=cast(str, case.get("observed_status")),
                passed=cast(bool, case.get("passed")),
                source_report_sha256=cast(str, case.get("source_report_sha256")),
                authority_verified=cast(bool, case.get("authority_verified")),
                metrics=metrics,
            )
        except (TypeError, ValueError) as exc:
            raise PrehardwareQualificationEvidenceError(
                f"recorded case {index} cannot be reconstructed: {exc}"
            ) from exc
        expected_case = {
            **result.to_dict(),
            "case_result_sha256": result.result_hash,
        }
        if dict(case) != expected_case:
            raise PrehardwareQualificationEvidenceError(
                f"recorded case {index} result hash/correlation is invalid"
            )
        parsed_cases.append(result)

    source = _mapping(report_document.get("source"), "recorded qualification source")
    coverage = _mapping(
        report_document.get("coverage_summary"),
        "recorded qualification coverage",
    )
    resources = _mapping(
        report_document.get("resource_usage"),
        "recorded qualification resources",
    )
    physical_holds = _array(
        report_document.get("physical_holds"),
        "recorded physical holds",
    )
    try:
        reconstructed = PrehardwareQualificationReport(
            policy=policy,
            source=source,
            cases=tuple(parsed_cases),
            coverage_summary=coverage,
            resource_usage=resources,
            physical_holds=tuple(physical_holds),
            final_revalidation_passed=cast(
                bool,
                report_document.get("final_source_revalidation_passed"),
            ),
        )
    except (TypeError, ValueError) as exc:
        raise PrehardwareQualificationEvidenceError(
            f"recorded qualification report cannot be reconstructed: {exc}"
        ) from exc
    if reconstructed.to_dict() != dict(report_document):
        raise PrehardwareQualificationEvidenceError(
            "recorded qualification report does not match canonical reconstruction"
        )

    source_artifact = documents["source.json"]
    if set(source_artifact) != {"schema", "source", "source_sha256"} or (
        source_artifact.get("schema") != SOURCE_ARTIFACT_SCHEMA
        or source_artifact.get("source") != dict(source)
        or source_artifact.get("source_sha256") != _stable_hash(source)
    ):
        raise PrehardwareQualificationEvidenceError(
            "qualification source artifact differs from report"
        )

    cases_artifact = documents["cases.json"]
    expected_case_documents = [
        {**case.to_dict(), "case_result_sha256": case.result_hash}
        for case in parsed_cases
    ]
    expected_cases_artifact = {
        "schema": CASES_ARTIFACT_SCHEMA,
        "case_summary": report_document["case_summary"],
        "case_count": len(parsed_cases),
        "ordered_case_ids": [case.spec.case_id for case in parsed_cases],
        "ordered_case_result_sha256s": [case.result_hash for case in parsed_cases],
        "ordered_child_report_sha256s": [
            case.source_report_sha256 for case in parsed_cases
        ],
        "cases": expected_case_documents,
    }
    if dict(cases_artifact) != expected_cases_artifact:
        raise PrehardwareQualificationEvidenceError(
            "qualification cases artifact differs from report"
        )

    coverage_artifact = documents["coverage.json"]
    expected_coverage_artifact = {
        "schema": COVERAGE_ARTIFACT_SCHEMA,
        "coverage_evaluated": report_document["coverage_evaluated"],
        "coverage_state": report_document["coverage_state"],
        "all_mission_routes_accepted": report_document["all_mission_routes_accepted"],
        "coverage_summary": dict(coverage),
    }
    if dict(coverage_artifact) != expected_coverage_artifact:
        raise PrehardwareQualificationEvidenceError(
            "qualification coverage artifact differs from report"
        )

    resources_artifact = documents["resources.json"]
    expected_resources_artifact = {
        "schema": RESOURCES_ARTIFACT_SCHEMA,
        "resource_usage": dict(resources),
        "resource_usage_sha256": _stable_hash(resources),
        "physical_holds": list(reconstructed.physical_holds),
        "final_source_revalidation_passed": (reconstructed.final_revalidation_passed),
        "physical_ready": False,
        "authority": report_document["authority"],
    }
    if dict(resources_artifact) != expected_resources_artifact:
        raise PrehardwareQualificationEvidenceError(
            "qualification resources artifact differs from report"
        )
    return reconstructed


def verify_prehardware_qualification_record(
    manifest_path: Path,
) -> VerifiedPrehardwareQualificationEvidence:
    """Strictly verify names, bytes, hashes, correlations, and authority."""

    requested = Path(manifest_path)
    if any(candidate.is_symlink() for candidate in (requested, *requested.parents)):
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest and record directory must not be symlinks"
        )
    try:
        selected = requested.resolve(strict=True)
    except OSError as exc:
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest path must name an existing manifest.json"
        ) from exc
    if selected.name != "manifest.json" or not selected.is_file():
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest path must name an existing manifest.json"
        )
    directory = selected.parent
    try:
        entries = tuple(directory.iterdir())
    except OSError as exc:
        raise PrehardwareQualificationEvidenceError(
            f"cannot inspect qualification evidence directory {directory}"
        ) from exc
    actual_files = {entry.name for entry in entries if entry.is_file()}
    unsafe_entries = [
        entry.name for entry in entries if entry.is_symlink() or not entry.is_file()
    ]
    if actual_files != _EXPECTED_FILES or unsafe_entries:
        raise PrehardwareQualificationEvidenceError(
            "qualification evidence directory is not exact; "
            f"files={sorted(actual_files)}, other={sorted(unsafe_entries)}"
        )

    manifest, manifest_payload = _read_json(selected)
    if set(manifest) != _MANIFEST_FIELDS:
        raise PrehardwareQualificationEvidenceError(
            "qualification evidence manifest fields are not exact"
        )
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("complete") is not True
        or manifest.get("manifest_written_last") is not True
        or manifest.get("simulation_only") is not True
        or manifest.get("physical_release_effect") != "NONE"
    ):
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest schema, completeness, or authority is invalid"
        )
    if (
        _bounded_integer(
            manifest.get("hardware_commands_generated"),
            "qualification manifest hardware-command count",
            maximum=0,
        )
        != 0
    ):
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest authority is invalid"
        )
    package_sha256 = _digest(
        manifest.get("package_sha256"), "qualification package sha256"
    )
    manifest_core = dict(manifest)
    del manifest_core["package_sha256"]
    if _stable_hash(manifest_core) != package_sha256:
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest package hash mismatch"
        )
    record_id = manifest.get("record_id")
    if (
        not isinstance(record_id, str)
        or _RECORD_ID.fullmatch(record_id) is None
        or directory.name != record_id
    ):
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest record identity/path is invalid"
        )
    profile = manifest.get("profile")
    if profile not in {"quick", "standard"}:
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest profile is invalid"
        )
    report_sha256 = _digest(
        manifest.get("report_sha256"), "qualification manifest report sha256"
    )
    if record_id != f"qualification-{report_sha256[:24]}":
        raise PrehardwareQualificationEvidenceError(
            "qualification record directory is not derived from report hash"
        )

    raw_rows = _array(manifest.get("artifacts"), "manifest artifacts")
    artifact_count = _bounded_integer(
        manifest.get("artifact_count"),
        "manifest artifact count",
        maximum=len(_ARTIFACT_ROLES),
    )
    declared_total = _bounded_integer(
        manifest.get("total_artifact_bytes"),
        "manifest total artifact bytes",
        maximum=MAX_PACKAGE_BYTES,
    )
    if len(raw_rows) != len(_ARTIFACT_ROLES) or artifact_count != len(_ARTIFACT_ROLES):
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest artifact list is not exact"
        )

    documents: dict[str, Mapping[str, Any]] = {}
    total_bytes = 0
    seen: set[str] = set()
    for index, (raw_row, expected) in enumerate(zip(raw_rows, _ARTIFACT_ROLES)):
        row = _mapping(raw_row, f"manifest artifact row {index}")
        if set(row) != {"path", "role", "sha256", "bytes"}:
            raise PrehardwareQualificationEvidenceError(
                f"qualification artifact row {index} is malformed"
            )
        name = row.get("path")
        expected_name, expected_role = expected
        if not isinstance(name, str):
            raise PrehardwareQualificationEvidenceError(
                "qualification artifact path must be text"
            )
        if Path(name).name != name or Path(name).is_absolute():
            raise PrehardwareQualificationEvidenceError(
                "qualification artifact path must be a plain filename"
            )
        if name in seen:
            raise PrehardwareQualificationEvidenceError(
                "qualification manifest contains a duplicate artifact path"
            )
        seen.add(name)
        if name != expected_name or row.get("role") != expected_role:
            raise PrehardwareQualificationEvidenceError(
                "qualification artifact order, path, or role is invalid"
            )
        expected_size = _bounded_integer(
            row.get("bytes"), f"{name} bytes", maximum=MAX_ARTIFACT_BYTES
        )
        expected_sha256 = _digest(row.get("sha256"), f"{name} sha256")
        artifact_path = directory / name
        try:
            resolved_artifact = artifact_path.resolve(strict=True)
        except OSError as exc:
            raise PrehardwareQualificationEvidenceError(
                f"cannot resolve qualification artifact {name}"
            ) from exc
        if artifact_path.is_symlink() or resolved_artifact.parent != directory:
            raise PrehardwareQualificationEvidenceError(
                f"qualification artifact escapes its record directory: {name}"
            )
        document, payload = _read_json(resolved_artifact)
        if (
            len(payload) != expected_size
            or hashlib.sha256(payload).hexdigest() != expected_sha256
        ):
            raise PrehardwareQualificationEvidenceError(
                f"qualification artifact byte/hash mismatch for {name}"
            )
        total_bytes += len(payload)
        if total_bytes > MAX_PACKAGE_BYTES:
            raise PrehardwareQualificationEvidenceError(
                f"qualification package exceeds {MAX_PACKAGE_BYTES} bytes"
            )
        documents[name] = document
    if total_bytes != declared_total:
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest total artifact bytes are invalid"
        )

    reconstructed = _report_from_documents(documents)
    cases_document = documents["cases.json"]
    source_document = documents["source.json"]
    resources_document = documents["resources.json"]
    case_count = _bounded_integer(
        manifest.get("case_count"),
        "qualification manifest case count",
        maximum=24,
    )
    if (
        reconstructed.profile != profile
        or reconstructed.report_hash != report_sha256
        or case_count != len(reconstructed.cases)
        or manifest.get("source_sha256") != source_document.get("source_sha256")
        or manifest.get("policy_sha256") != reconstructed.policy.policy_hash
        or manifest.get("ordered_case_results_sha256")
        != _stable_hash(cases_document.get("ordered_case_result_sha256s"))
        or manifest.get("ordered_child_reports_sha256")
        != _stable_hash(cases_document.get("ordered_child_report_sha256s"))
        or manifest.get("resource_usage_sha256")
        != resources_document.get("resource_usage_sha256")
    ):
        raise PrehardwareQualificationEvidenceError(
            "qualification manifest differs from verified artifact evidence"
        )
    for name in (
        "source_sha256",
        "policy_sha256",
        "ordered_case_results_sha256",
        "ordered_child_reports_sha256",
        "resource_usage_sha256",
    ):
        _digest(manifest.get(name), f"qualification manifest {name}")
    _validate_zero_authority_and_redaction(documents)
    return VerifiedPrehardwareQualificationEvidence(
        manifest_path=selected,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        package_sha256=package_sha256,
        report_sha256=report_sha256,
        profile=cast(str, profile),
        case_count=case_count,
        documents=documents,
    )


QualificationRunner = Callable[..., PrehardwareQualificationReport]


def _replay_prehardware_qualification_with_runner(
    workspace: Path,
    manifest_path: Path,
    *,
    runtime_path: Path | None,
    qualification_runner: QualificationRunner,
) -> PrehardwareQualificationReplayReport:
    """Private deterministic replay seam used by focused tests.

    The public API and CLI never accept a caller-selected runner.  Any injected
    test runner must still return a validated ``PrehardwareQualificationReport``
    whose constructors enforce zero authority throughout its retained evidence.
    """

    if not callable(qualification_runner):
        raise TypeError("qualification_runner must be callable")
    verified = verify_prehardware_qualification_record(manifest_path)
    policy = _policy_from_document(verified.document("policy.json"))
    recomputed = qualification_runner(
        Path(workspace),
        policy=policy,
        runtime_path=runtime_path,
    )
    if not isinstance(recomputed, PrehardwareQualificationReport):
        raise PrehardwareQualificationEvidenceError(
            "qualification replay runner returned an invalid report type"
        )
    recomputed_documents = _artifact_documents(recomputed)
    identical = all(
        _canonical_bytes(recomputed_documents[name])
        == _canonical_bytes(_deep_thaw(verified.document(name)))
        for name, _ in _ARTIFACT_ROLES
    )
    return PrehardwareQualificationReplayReport(
        manifest_sha256=verified.manifest_sha256,
        recorded_report_sha256=verified.report_sha256,
        recomputed_report_sha256=recomputed.report_hash,
        profile=verified.profile,
        recomputed_status=recomputed.status,
        compared_artifact_count=len(_ARTIFACT_ROLES),
        identical=identical,
    )


def replay_prehardware_qualification(
    workspace: Path,
    manifest_path: Path,
    *,
    runtime_path: Path | None = None,
) -> PrehardwareQualificationReplayReport:
    """Verify evidence, rerun the locked campaign, and compare every artifact."""

    return _replay_prehardware_qualification_with_runner(
        workspace,
        manifest_path,
        runtime_path=runtime_path,
        qualification_runner=run_prehardware_qualification,
    )


__all__ = [
    "MANIFEST_SCHEMA",
    "SOURCE_ARTIFACT_SCHEMA",
    "CASES_ARTIFACT_SCHEMA",
    "COVERAGE_ARTIFACT_SCHEMA",
    "RESOURCES_ARTIFACT_SCHEMA",
    "REPLAY_SCHEMA",
    "MAX_ARTIFACT_BYTES",
    "MAX_PACKAGE_BYTES",
    "PrehardwareQualificationEvidenceError",
    "PrehardwareQualificationEvidenceRecord",
    "VerifiedPrehardwareQualificationEvidence",
    "PrehardwareQualificationReplayReport",
    "record_prehardware_qualification",
    "verify_prehardware_qualification_record",
    "replay_prehardware_qualification",
]
