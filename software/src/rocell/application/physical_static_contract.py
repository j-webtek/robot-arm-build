"""Original stage-2 design inputs, not installed-camera qualification.

Only explicit collection reads files. Immutable records independently reparse
the retained originals with the same strict loaders used by physical onboarding.
The caller's original M1 boundary authenticates the source review and entry event;
hashes carried inside a document are not their own authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from threading import Event
import time
from typing import Any, Callable

from .physical_camera_prerequisites import PhysicalCameraPrerequisites
from .physical_onboarding_durability import read_bounded_regular_file
from .physical_source_preflight import _checked
from .physical_source_qualification import (
    SourceQualificationReceipt,
    assess_source_qualification,
)
from .physical_source_stage_evidence import (
    WorkspaceSourceReceipt,
    _pins,
    verify_workspace_source_receipt,
)
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.vision.camera_profile import parse_camera_profile_json
from rocell.workcell.camera_architecture import parse_camera_architecture_plan_json
from rocell.workcell.static_camera_support import parse_static_camera_support_json

RECEIPT_SCHEMA = "rocell.static_camera_contract_receipt.v1"
ASSESSMENT_SCHEMA = "rocell.static_camera_contract_assessment.v1"
REVIEW_SCHEMA = "rocell.static_camera_contract_review.v1"
RECEIPT_LABEL = "static-camera-contract-receipt-v1"
ASSESSMENT_LABEL = "static-camera-contract-assessment-v1"
REVIEW_LABEL = "static-camera-contract-review-v1"
MAX_RECEIPT_BYTES = 256 * 1024
MAX_ASSESSMENT_BYTES = MAX_REVIEW_BYTES = 32 * 1024
MAX_SUMMARY_BYTES = 24 * 1024
MAX_SOURCE_FILE_BYTES = 64 * 1024
MAX_SOURCE_TOTAL_BYTES = 128 * 1024
MAX_COLLECTION_DURATION_NS = 30_000_000_000
ARCHITECTURE_PATH = "software/config/camera_architecture_plan.json"
PROFILE_PATH = "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
SUPPORT_PATH = "hardware/static_overhead_camera/config/support_design.json"
LOCKED_SOURCES = (
    ("workcell_layout", "active-project/RoCell_v0_3/config/workcell_layout.json"),
    (
        "robot_reach_screening",
        "active-project/RoCell_v0_3/config/robot_reach_screening.json",
    ),
    ("camera_architecture_plan", ARCHITECTURE_PATH),
    ("purchased_camera_profile", PROFILE_PATH),
)
FIXED_PATHS = tuple(sorted((SUPPORT_PATH, *(path for _, path in LOCKED_SOURCES))))
CHECK_IDS = (
    "base_software_ready",
    "readiness_and_architecture_select_static_primary",
    "architecture_has_zero_physical_authority",
    "secondary_camera_unselected",
    "automatic_camera_fallback_disabled",
    "camera_profile_has_zero_live_authority",
    "profile_and_support_identity_match",
    "profile_and_support_native_mode_match",
    "architecture_and_support_board_match",
    "architecture_and_support_required_view_match",
    "architecture_file_matches_source_binding",
    "camera_profile_file_matches_source_binding",
    "support_design_file_matches_source_binding",
    "support_locks_architecture_bytes",
    "support_locks_camera_profile_bytes",
    "every_support_dependency_matches_source_binding",
    "physical_qualification_holds_retained",
)
FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "device_io_performed": False,
    "native_runtime_released": False,
}
HAZARD_IDS = ["HZ-007", "HZ-010"]
MEANING = (
    "Strict static-camera design inputs only. Published lens/mode, nominal board "
    "and planned support geometry are not received measurements. Installation, "
    "identity, optical, load, collision and native-runtime qualification remain open."
)
_BINDING_KEYS = {
    "contract_id",
    "source_sha256",
    "cell_id",
    "session_id",
    "header_sha256",
    "origin_launch_id",
    "collection_launch_id",
    "operator_id",
    "prerequisites_sha256",
    "source_qualification",
    "static_request_event_sha256",
    "store_directory",
}


class StaticCameraContractError(ValueError):
    def __init__(self, code: str = "STATIC_CAMERA_CONTRACT_INVALID", *, receipt=None):
        self.code, self.receipt = code, receipt
        super().__init__(code)


def _require(value: bool, code: str = "STATIC_CAMERA_CONTRACT_INVALID") -> None:
    if not value:
        raise StaticCameraContractError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return value


def _same(left: Any, right: Any) -> None:
    _require(_canonical(left) == _canonical(right))


def _sha(value: Any) -> None:
    _require(
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def _identifier(value: Any, pattern: str) -> None:
    _require(type(value) is str and re.fullmatch(pattern, value) is not None)


def _actor(value: Any) -> None:
    _identifier(value, r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


def _binding(value: Any) -> dict[str, Any]:
    data = _exact(value, _BINDING_KEYS)
    for key in (
        "source_sha256",
        "header_sha256",
        "prerequisites_sha256",
        "static_request_event_sha256",
    ):
        _sha(data[key])
    for key, pattern in (
        ("contract_id", r"staticcontract-[0-9a-f]{32}"),
        ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
        ("session_id", r"physical-camera-[0-9a-f]{32}"),
        ("origin_launch_id", r"wizard-[0-9a-f]{32}"),
        ("collection_launch_id", r"wizard-[0-9a-f]{32}"),
    ):
        _identifier(data[key], pattern)
    _actor(data["operator_id"])
    for value in _exact(
        data["source_qualification"], {"receipt", "assessment", "review"}
    ).values():
        _sha(value)
    directory = data["store_directory"]
    _require(type(directory) is str and len(directory) <= 4096)
    path = Path(directory)
    _require(
        path.is_absolute()
        and str(path) == directory
        and path != path.parent
        and ".." not in path.parts
        and not directory.startswith(("\\\\", "//"))
        and not any(":" in part for part in path.parts[1:])
    )
    return data


def _load(payload: bytes, maximum: int) -> dict[str, Any]:
    _require(type(payload) is bytes and 0 < len(payload) <= maximum)

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def bad(value):
        raise StaticCameraContractError()

    try:
        data = json.loads(payload, object_pairs_hook=pairs, parse_constant=bad)
        _require(type(data) is dict and _canonical(data) == payload)
        stack, nodes = [(data, 0)], 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            _require(nodes <= 16384 and depth <= 16)
            if type(value) is dict:
                stack.extend((item, depth + 1) for item in value.values())
            elif type(value) is list:
                stack.extend((item, depth + 1) for item in value)
            elif type(value) is float:
                _require(math.isfinite(value))
        return data
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise StaticCameraContractError() from error


def _common(data: Any, schema: str, keys: set[str]) -> dict[str, Any]:
    _exact(data, {"schema", "binding", "hazard_ids", "meaning", *FLAGS, *keys})
    _require(
        data["schema"] == schema
        and data["hazard_ids"] == HAZARD_IDS
        and data["meaning"] == MEANING
        and all(data[k] is False for k in FLAGS)
    )
    return _binding(data["binding"])


def _derived(files: Any, software: dict[str, Any]) -> dict[str, Any]:
    """Reproduce the existing controller's 17 checks from original bytes only."""
    _require(type(files) is list and len(files) == len(FIXED_PATHS))
    originals: dict[str, bytes] = {}
    for row, path in zip(files, FIXED_PATHS):
        _exact(row, {"relative_path", "bytes", "sha256", "utf8"})
        _require(row["relative_path"] == path and type(row["utf8"]) is str)
        raw = row["utf8"].encode("utf-8")
        _require(
            type(row["bytes"]) is int
            and row["bytes"] == len(raw)
            and 0 < len(raw) <= MAX_SOURCE_FILE_BYTES
        )
        _require(row["sha256"] == _hash(raw))
        originals[path] = raw
    _require(sum(map(len, originals.values())) <= MAX_SOURCE_TOTAL_BYTES)
    try:
        architecture = parse_camera_architecture_plan_json(
            originals[ARCHITECTURE_PATH],
            source_path=Path(software["host_readiness"]["workspace"])
            / ARCHITECTURE_PATH,
        )
        profile = parse_camera_profile_json(originals[PROFILE_PATH])
        support = parse_static_camera_support_json(
            originals[SUPPORT_PATH],
            source_hashes={path: _hash(originals[path]) for _, path in LOCKED_SOURCES},
        )
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise StaticCameraContractError("STATIC_DESIGN_SOURCE_INVALID") from error
    bound = {row["relative_path"]: row["sha256"] for row in software["source_files"]}
    host = software["host_readiness"]
    matching = [
        mode
        for mode in profile.published_modes
        if (mode.width_px, mode.height_px, mode.maximum_fps, mode.pixel_format)
        == support.native_mode
    ]
    mode = matching[0] if len(matching) == 1 else None
    locks = {
        key: support.source_sha256[key] == bound.get(path)
        for key, path in LOCKED_SOURCES
    }
    values = (
        host["readiness"]["base_software_ready"],
        host["build"]["static_camera_plan_selected"]
        and architecture.overhead_route_selected,
        architecture.zero_physical_authority,
        not architecture.secondary_selected,
        not architecture.automatic_fallback_allowed,
        not profile.live_ready and not any(profile.authority.values()),
        support.camera_model == f"{profile.manufacturer} {profile.model}"
        and support.sensor == profile.sensor,
        mode is not None,
        architecture.board_size_mm == support.board_size_mm[:2],
        architecture.provisional_required_coverage_mm == support.required_view_mm,
        bound.get(ARCHITECTURE_PATH) == architecture.source_sha256,
        bound.get(PROFILE_PATH) == profile.source_file_sha256,
        bound.get(SUPPORT_PATH) == support.content_sha256,
        support.source_sha256["camera_architecture_plan"] == architecture.source_sha256,
        support.source_sha256["purchased_camera_profile"] == profile.source_file_sha256,
        all(locks.values()),
        bool(
            architecture.open_blockers
            and profile.open_blockers
            and support.open_blockers
        ),
    )
    return {
        "checks": [
            {"check_id": name, "passed": passed}
            for name, passed in zip(CHECK_IDS, values)
        ],
        "design": {
            "camera_model": support.camera_model,
            "sensor": support.sensor,
            "lens_mount": profile.lens_mount,
            "focal_length_mm": profile.focal_length_mm,
            "board_size_mm": list(support.board_size_mm),
            "required_view_mm": list(support.required_view_mm),
            "nominal_entrance_pupil_z_mm": support.nominal_entrance_pupil_z_mm,
            "published_mode": (
                None
                if mode is None
                else {
                    "host_bus": mode.host_bus,
                    "width_px": mode.width_px,
                    "height_px": mode.height_px,
                    "maximum_fps": mode.maximum_fps,
                    "pixel_format": mode.pixel_format,
                    "evidence_state": mode.evidence_state,
                }
            ),
            "value_provenance": "DESIGN_NOT_MEASURED",
        },
        "blockers": {
            "architecture": list(architecture.open_blockers),
            "profile": list(profile.open_blockers),
            "support": list(support.open_blockers),
        },
        "support_source_binding_checks": locks,
        "screening_metrics": {
            name: getattr(support.metrics, name)
            for name in (
                "minimum_height_view_margin_width_mm",
                "minimum_height_view_margin_depth_mm",
                "minimum_post_radial_clearance_mm",
                "minimum_overhead_vertical_clearance_mm",
            )
        },
    }


def _receipt(payload: bytes) -> dict[str, Any]:
    data = _load(payload, MAX_RECEIPT_BYTES)
    binding = _common(
        data,
        RECEIPT_SCHEMA,
        {
            "status",
            "software_receipt",
            "source_files",
            "collection",
            "checks",
            "design",
            "blockers",
            "support_source_binding_checks",
            "screening_metrics",
        },
    )
    _require(data["status"] == "DESIGN_INPUTS_COLLECTED")
    software = WorkspaceSourceReceipt(_canonical(data["software_receipt"])).to_dict()
    for key in (
        "source_sha256",
        "session_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
    ):
        _same(software["binding"][key], binding[key])
    collection = _exact(
        data["collection"],
        {
            "started_monotonic_ns",
            "finished_monotonic_ns",
            "recorded_at_ns",
            "deadline_monotonic_ns",
            "before_source_sha256",
            "after_source_sha256",
        },
    )
    for key in (
        "started_monotonic_ns",
        "finished_monotonic_ns",
        "recorded_at_ns",
        "deadline_monotonic_ns",
    ):
        _require(type(collection[key]) is int and 0 < collection[key] < 2**63)
    _require(
        collection["started_monotonic_ns"]
        <= collection["finished_monotonic_ns"]
        < collection["deadline_monotonic_ns"]
        <= collection["started_monotonic_ns"] + MAX_COLLECTION_DURATION_NS
    )
    _require(
        collection["before_source_sha256"]
        == collection["after_source_sha256"]
        == binding["source_sha256"]
    )
    for key, value in _derived(data["source_files"], software).items():
        _same(data[key], value)
    return data


def _summary(value: dict[str, Any]) -> dict[str, Any]:
    _require(len(_canonical(value)) <= MAX_SUMMARY_BYTES)
    return value


@dataclass(frozen=True, slots=True)
class StaticCameraContractReceipt:
    payload: bytes

    def __post_init__(self):
        _receipt(self.payload)

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _receipt(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.static_camera_contract_receipt_summary.v1",
                **{
                    key: data[key]
                    for key in ("binding", "status", "checks", "design", "blockers")
                },
                "receipt_sha256": self.sha256,
                "source_file_count": len(data["source_files"]),
                "source_bytes": sum(row["bytes"] for row in data["source_files"]),
                **FLAGS,
            }
        )


def _assessment_document(receipt: StaticCameraContractReceipt) -> dict[str, Any]:
    data = receipt.to_dict()
    missing = [row["check_id"] for row in data["checks"] if not row["passed"]]
    return {
        "schema": ASSESSMENT_SCHEMA,
        "binding": data["binding"],
        "status": "ASSESSED",
        "receipt_sha256": receipt.sha256,
        "checks": data["checks"],
        "verdict": "BLOCKED" if missing else "PASS",
        "missing_requirements": missing,
        "hazard_ids": HAZARD_IDS,
        "meaning": MEANING,
        **FLAGS,
    }


@dataclass(frozen=True, slots=True)
class StaticCameraContractAssessment:
    payload: bytes

    def __post_init__(self):
        data = _load(self.payload, MAX_ASSESSMENT_BYTES)
        _common(
            data,
            ASSESSMENT_SCHEMA,
            {"status", "receipt_sha256", "checks", "verdict", "missing_requirements"},
        )
        _require(data["status"] == "ASSESSED")
        _sha(data["receipt_sha256"])
        _require(type(data["checks"]) is list and len(data["checks"]) == len(CHECK_IDS))
        for row, name in zip(data["checks"], CHECK_IDS):
            _exact(row, {"check_id", "passed"})
            _require(row["check_id"] == name and type(row["passed"]) is bool)
        missing = [row["check_id"] for row in data["checks"] if not row["passed"]]
        _same(data["missing_requirements"], missing)
        _require(data["verdict"] == ("BLOCKED" if missing else "PASS"))

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_ASSESSMENT_BYTES)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.static_camera_contract_assessment_summary.v1",
                **{
                    key: value
                    for key, value in data.items()
                    if key not in {"schema", "hazard_ids", "meaning"}
                },
                "assessment_sha256": self.sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class StaticCameraContractReview:
    payload: bytes

    def __post_init__(self):
        data = _load(self.payload, MAX_REVIEW_BYTES)
        binding = _common(
            data,
            REVIEW_SCHEMA,
            {
                "status",
                "receipt_sha256",
                "assessment_sha256",
                "verdict",
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_ns",
                "procedure_complete",
            },
        )
        _require(
            data["status"] == "REVIEW_RECORDED" and data["procedure_complete"] is True
        )
        _sha(data["receipt_sha256"])
        _sha(data["assessment_sha256"])
        _actor(data["reviewer_id"])
        _require(data["reviewer_id"].casefold() != binding["operator_id"].casefold())
        _identifier(data["review_launch_id"], r"wizard-[0-9a-f]{32}")
        _require(
            type(data["reviewed_at_ns"]) is int and 0 < data["reviewed_at_ns"] < 2**63
        )
        _require(data["verdict"] in {"PASS", "BLOCKED"})

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REVIEW_BYTES)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.static_camera_contract_review_summary.v1",
                **{
                    key: value
                    for key, value in data.items()
                    if key not in {"schema", "hazard_ids", "meaning"}
                },
                "review_sha256": self.sha256,
            }
        )


def _payload(value: Any, kind: type) -> bytes:
    _require(type(value) in {bytes, kind})
    return value if type(value) is bytes else value.payload


def assess_static_camera_contract(
    receipt: StaticCameraContractReceipt,
) -> StaticCameraContractAssessment:
    _require(type(receipt) is StaticCameraContractReceipt)
    return StaticCameraContractAssessment(_canonical(_assessment_document(receipt)))


def verify_static_camera_contract_assessment(
    value: Any, *, receipt: StaticCameraContractReceipt, expected_assessment_sha256: str
) -> StaticCameraContractAssessment:
    result = StaticCameraContractAssessment(
        _payload(value, StaticCameraContractAssessment)
    )
    _require(
        result.sha256 == expected_assessment_sha256
        and result.payload == assess_static_camera_contract(receipt).payload,
        "STATIC_ASSESSMENT_MISMATCH",
    )
    return result


def review_static_camera_contract(
    receipt: StaticCameraContractReceipt,
    assessment: StaticCameraContractAssessment,
    *,
    reviewer_id: str,
    review_launch_id: str,
    reviewed_at_ns: int,
) -> StaticCameraContractReview:
    checked = verify_static_camera_contract_assessment(
        assessment, receipt=receipt, expected_assessment_sha256=assessment.sha256
    )
    _require(
        type(reviewed_at_ns) is int
        and reviewed_at_ns >= receipt.to_dict()["collection"]["recorded_at_ns"]
    )
    return StaticCameraContractReview(
        _canonical(
            {
                "schema": REVIEW_SCHEMA,
                "binding": receipt.to_dict()["binding"],
                "receipt_sha256": receipt.sha256,
                "assessment_sha256": checked.sha256,
                "verdict": checked.to_dict()["verdict"],
                "status": "REVIEW_RECORDED",
                "reviewer_id": reviewer_id,
                "review_launch_id": review_launch_id,
                "reviewed_at_ns": reviewed_at_ns,
                "procedure_complete": True,
                "hazard_ids": HAZARD_IDS,
                "meaning": MEANING,
                **FLAGS,
            }
        )
    )


def verify_static_camera_contract_review(
    value: Any,
    *,
    receipt: StaticCameraContractReceipt,
    assessment: StaticCameraContractAssessment,
    expected_review_sha256: str,
) -> StaticCameraContractReview:
    result = StaticCameraContractReview(_payload(value, StaticCameraContractReview))
    data = result.to_dict()
    expected = review_static_camera_contract(
        receipt,
        assessment,
        **{
            key: data[key]
            for key in ("reviewer_id", "review_launch_id", "reviewed_at_ns")
        },
    )
    _require(
        result.sha256 == expected_review_sha256 and result.payload == expected.payload,
        "STATIC_REVIEW_MISMATCH",
    )
    return result


def _qualified_context(
    binding: dict[str, Any], source_qualification: SourceQualificationReceipt
) -> dict[str, Any]:
    _binding(binding)
    _require(type(source_qualification) is SourceQualificationReceipt)
    source = source_qualification.to_dict()
    for key in (
        "source_sha256",
        "cell_id",
        "session_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
        "store_directory",
    ):
        _same(source["binding"][key], binding[key])
    assessment = assess_source_qualification(source_qualification)
    _require(
        binding["source_qualification"]["receipt"] == source_qualification.sha256
        and binding["source_qualification"]["assessment"] == assessment.sha256
        and assessment.to_dict()["verdict"] == "PASS",
        "STATIC_SOURCE_QUALIFICATION_NOT_PASSED",
    )
    return source["software_receipt"]


def verify_static_camera_contract_receipt(
    value: Any,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    source_qualification: SourceQualificationReceipt,
    expected_binding: dict[str, Any],
    expected_receipt_sha256: str,
) -> StaticCameraContractReceipt:
    result = StaticCameraContractReceipt(_payload(value, StaticCameraContractReceipt))
    _require(result.sha256 == expected_receipt_sha256, "STATIC_RECEIPT_HASH_MISMATCH")
    data = result.to_dict()
    _same(data["binding"], expected_binding)
    software = _qualified_context(expected_binding, source_qualification)
    _same(data["software_receipt"], software)
    original = WorkspaceSourceReceipt(_canonical(software))
    verify_workspace_source_receipt(
        original,
        prerequisites=prerequisites,
        expected_source_sha256=expected_binding["source_sha256"],
        expected_session_id=expected_binding["session_id"],
        expected_origin_launch_id=expected_binding["origin_launch_id"],
        expected_header_sha256=expected_binding["header_sha256"],
        expected_receipt_sha256=original.sha256,
    )
    stage = prerequisites.to_dict()["requirements"]["stages"][1]
    _require(
        stage["stage"] == "static_camera_contract" and stage["hazard_ids"] == HAZARD_IDS
    )
    return result


def collect_static_camera_contract(
    workspace: Path,
    *,
    binding: dict[str, Any],
    source_qualification: SourceQualificationReceipt,
    cancellation: Event,
    progress: Callable[[str], None],
    deadline_ns: int,
) -> StaticCameraContractReceipt:
    """One bounded actual-file observation; never create a store or run a device.

    A complete verified receipt survives late Stop/source/progress/pin-cleanup
    failure on the exception. An incomplete source input is not invented into a
    valid receipt. The service owns retention and original M1 publication.
    """
    result = None
    try:
        binding = _load(_canonical(binding), 16 * 1024)
        software = _qualified_context(binding, source_qualification)
        _require(isinstance(cancellation, Event) and callable(progress))
        started = time.monotonic_ns()
        _require(type(deadline_ns) is int and started < deadline_ns < 2**63)
        deadline = min(deadline_ns, started + MAX_COLLECTION_DURATION_NS)
        last = started

        def check():
            nonlocal last
            now = time.monotonic_ns()
            _require(now >= last, "CLOCK_REGRESSED")
            last = now
            _require(not cancellation.is_set(), "CANCELLED")
            _require(now < deadline, "TIMED_OUT")

        def notify(message):
            check()
            progress(message)
            check()

        def read_files():
            rows = []
            total = 0
            for relative in FIXED_PATHS:
                check()
                raw = read_bounded_regular_file(
                    _checked(root / relative),
                    maximum_bytes=MAX_SOURCE_FILE_BYTES,
                    label="static camera design input",
                )
                check()
                total += len(raw)
                _require(
                    0 < len(raw) and total <= MAX_SOURCE_TOTAL_BYTES,
                    "STATIC_SOURCE_BYTE_LIMIT",
                )
                rows.append(
                    {
                        "relative_path": relative,
                        "bytes": len(raw),
                        "sha256": _hash(raw),
                        "utf8": raw.decode("utf-8"),
                    }
                )
            return rows

        check()
        root = _checked(Path(workspace), directory=True)
        _require(
            str(root) == software["host_readiness"]["workspace"],
            "STATIC_WORKSPACE_MISMATCH",
        )
        notify("Reading exact selected static-camera design files; no device access.")
        _require(source_fingerprint(root) == binding["source_sha256"], "SOURCE_CHANGED")
        check()
        with _pins(root, FIXED_PATHS, check):
            rows = read_files()
            derived = _derived(rows, software)
            check()
            _same(rows, read_files())
            check()
            _require(
                source_fingerprint(root) == binding["source_sha256"], "SOURCE_CHANGED"
            )
            check()
            # Construct before final freshness/publication checks so a late
            # failure preserves complete historical design bytes, never current.
            result = StaticCameraContractReceipt(
                _canonical(
                    {
                        "schema": RECEIPT_SCHEMA,
                        "binding": binding,
                        "status": "DESIGN_INPUTS_COLLECTED",
                        "software_receipt": software,
                        "source_files": rows,
                        **derived,
                        "collection": {
                            "started_monotonic_ns": started,
                            "finished_monotonic_ns": last,
                            "recorded_at_ns": time.time_ns(),
                            "deadline_monotonic_ns": deadline,
                            "before_source_sha256": binding["source_sha256"],
                            "after_source_sha256": binding["source_sha256"],
                        },
                        "hazard_ids": HAZARD_IDS,
                        "meaning": MEANING,
                        **FLAGS,
                    }
                )
            )
            check()
            _require(
                source_fingerprint(root) == binding["source_sha256"], "SOURCE_CHANGED"
            )
            check()
        notify(
            "Static design bytes verified; received installation and native release remain unqualified."
        )
        return result
    except StaticCameraContractError as error:
        raise StaticCameraContractError(error.code, receipt=result) from error
    except (
        ValueError,
        TypeError,
        OSError,
        KeyError,
        RuntimeError,
        OverflowError,
        RecursionError,
    ) as error:
        raise StaticCameraContractError(
            "STATIC_COLLECTION_FAILED", receipt=result
        ) from error
