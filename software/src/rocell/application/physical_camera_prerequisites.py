"""Retained physical-camera questions and source facts, never acceptance.

Only explicit collection reads files. Constructors, projections and verification
are pure; retained digests need an independently trusted M1/source binding.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
from threading import Event
import time
from typing import Any

from . import configuration_epochs as epoch_contract
from . import physical_onboarding_stage_catalog as stage_contract
from .hardware_intake import INTAKE_HEADER, assess_hardware_intake
from .physical_camera_selection import PhysicalCameraSelection
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
    read_bounded_regular_file,
)
from .physical_source_preflight import PhysicalSourcePreflightReport
from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from rocell.safety import onboarding_hazards as hazard_contract

SCHEMA = "rocell.physical_camera_prerequisites.v1"
SUMMARY_SCHEMA = "rocell.physical_camera_prerequisites_summary.v1"
MAX_EVIDENCE_BYTES = 112 * 1024
MAX_SOURCE_BYTES = 64 * 1024
MAX_COLLECTION_DURATION_NS = 30_000_000_000
SOURCES = (
    ("stage_catalog", "software/config/physical_onboarding_stage_catalog.json"),
    ("hazard_register", "software/config/physical_onboarding_hazards.json"),
    ("epoch_policy", "software/config/configuration_epochs.json"),
    ("intake_template", "hardware/static_overhead_camera/hardware_intake_template.csv"),
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
# Match the original predicates exactly. Repeated source reconstruction scans
# large embedded documents; a fixed character class avoids a Python call per
# character without caching validated documents or changing any byte limit.
_JSON_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_TEMPLATE_CONTROL = re.compile(r"[\x00-\x1f]")
_OBSERVATION_FIELDS = (
    "observed_value",
    "instrument_or_method",
    "observed_at_ns",
    "operator_id",
    "evidence_references",
    "uncertainty_or_limitations",
)
_RECORDS = (
    (
        "ACTUAL_CONTROLLED_SOURCE_EVIDENCE",
        "REVIEWED_ACTUATOR_ISOLATION_OBSERVATION",
        "HZ_012_OWNERSHIP_QUALIFICATION_EVIDENCE",
    ),
    (
        "STRICT_STATIC_CAMERA_CONTRACT_ASSESSMENT",
        "PHYSICAL_INSTALLATION_HOLDS_RETAINED",
    ),
    (
        "CAMERA_RECEIPT_INSPECTION",
        "PASSIVE_WORKCELL_MEASUREMENT_ASSESSMENT",
        "EXACT_RECEIPT_AND_ASSESSMENT_REVIEW",
    ),
    (
        "CURRENT_GENERIC_AND_NATIVE_METADATA",
        "RECEIVED_LABEL_TO_USB_CORRELATION",
        "PERSISTENT_IDENTITY_RECONNECT_REBOOT_EVIDENCE",
        "HOST_PORT_AND_DRIVER_IDENTITY",
    ),
)
_MISSING = (
    "REQUIREMENTS_ARE_NOT_OBSERVATIONS_OR_ACCEPTANCE",
    "DISCONNECTED_REQUIRED_NOT_OBSERVED",
    "HZ_012_QUALIFICATION_EVIDENCE_NOT_ASSESSED",
    "STATIC_CAMERA_CONTRACT_NOT_ASSESSED_BY_THIS_COLLECTION",
    "RECEIVED_CAMERA_AND_PASSIVE_WORKCELL_NOT_MEASURED",
    "RECEIVED_LABEL_TO_USB_CORRELATION_NOT_ASSESSED",
    "PERSISTENT_IDENTITY_STABILITY_NOT_QUALIFIED",
    "ALL_EIGHT_EPOCH_DEPENDENCIES_UNMEASURED",
    "NATIVE_ACTIVATION_AND_PHYSICAL_STAGE_GATES_REMAIN_HELD",
)
_MEANING = (
    "Actual fixed-file requirements and optional retained metadata/source context only. "
    "No intake observation, power isolation, stage acceptance, device qualification or "
    "permission to acquire images is produced. Record and review evidence separately."
)


class PhysicalCameraPrerequisitesError(ValueError):
    def __init__(self, code: str = "PREREQUISITES_INVALID") -> None:
        self.code = code
        super().__init__(
            code
            + ": prerequisite collection or binding is held; inspect retained context without device access."
        )


def _require(value: bool, code: str = "PREREQUISITES_INVALID") -> None:
    if not value:
        raise PhysicalCameraPrerequisitesError(code)


def _sha(value: Any) -> None:
    _require(type(value) is str and _SHA.fullmatch(value) is not None, "INVALID_DIGEST")


def _identifier(value: Any) -> None:
    _require(
        type(value) is str and _ID.fullmatch(value) is not None, "INVALID_IDENTIFIER"
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        _require(key not in result, "DUPLICATE_FIELD")
        result[key] = value
    return result


def _node(value: Any, depth: int = 0) -> None:
    _require(depth <= 16, "DOCUMENT_DEPTH")
    if type(value) is dict:
        _require(len(value) <= 128)
        for key, item in value.items():
            _require(type(key) is str and len(key) <= 128)
            _node(item, depth + 1)
    elif type(value) is list:
        _require(len(value) <= 128)
        for item in value:
            _node(item, depth + 1)
    elif type(value) is str:
        _require(len(value.encode("utf-8")) <= MAX_EVIDENCE_BYTES)
        _require(_JSON_CONTROL.search(value) is None)
    else:
        _require(
            value is None
            or type(value) is bool
            or type(value) is int
            and abs(value) <= 2**63 - 1
        )


def _json(payload: bytes) -> Any:
    value = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    _node(value)
    return value


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys, "DOCUMENT_FIELDS")
    return value


def _template(payload: bytes) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(
        io.StringIO(payload.decode("utf-8"), newline=""), strict=True
    )
    _require(tuple(reader.fieldnames or ()) == INTAKE_HEADER, "INTAKE_HEADER")
    rows = list(reader)
    _require(len(rows) == 55, "INTAKE_CARDINALITY")
    for index, row in enumerate(rows, 1):
        _exact(row, set(INTAKE_HEADER))
        _require(row["record_id"] == f"INT-{index:03d}", "INTAKE_ORDER")
        _require(
            all(
                type(v) is str
                and len(v) <= 4096
                and _TEMPLATE_CONTROL.search(v) is None
                for v in row.values()
            ),
            "INTAKE_FIELDS",
        )
        _require(
            all(
                not row[key]
                for key in ("observed_value", "instrument_or_method", "evidence_path")
            ),
            "TEMPLATE_IS_NOT_OBSERVATIONS",
        )
        _require(
            row["status"]
            in {
                "NOT_CAPTURED",
                "NOT_CREATED",
                "NOT_MEASURED",
                "NOT_RECORDED",
                "NOT_TESTED",
                "OPEN_LIMIT",
            },
            "TEMPLATE_ACCEPTANCE_REFUSED",
        )
    return {row["record_id"]: row for row in rows}


def _source_documents(rows: Any) -> dict[str, Any]:
    _require(type(rows) is list and len(rows) == len(SOURCES), "SOURCE_SET")
    documents = {}
    for row, (role, path) in zip(rows, SOURCES):
        _exact(row, {"role", "relative_path", "bytes", "sha256", "payload_utf8"})
        _require(row["role"] == role and row["relative_path"] == path, "SOURCE_SET")
        _require(type(row["payload_utf8"]) is str)
        raw = row["payload_utf8"].encode("utf-8")
        _require(
            type(row["bytes"]) is int
            and 1 <= len(raw) == row["bytes"] <= MAX_SOURCE_BYTES,
            "SOURCE_BYTE_LIMIT",
        )
        _sha(row["sha256"])
        _require(_hash(raw) == row["sha256"], "SOURCE_HASH")
        documents[role] = _template(raw) if role == "intake_template" else _json(raw)
    return documents


def _requirements(documents: dict[str, Any]) -> dict[str, Any]:
    catalog, hazards, epochs = (
        documents[name] for name in ("stage_catalog", "hazard_register", "epoch_policy")
    )
    _require(
        catalog["schema"] == stage_contract.PHYSICAL_ONBOARDING_STAGE_CATALOG_SCHEMA
        and catalog["runtime_activation"] is False
        and catalog["canonical_stage_order_sha256"]
        == stage_contract.CANONICAL_STAGE_ORDER_SHA256,
        "CATALOG_DOMAIN",
    )
    _require(
        type(catalog["stages"]) is list
        and [row["stage"] for row in catalog["stages"]]
        == [s.value for s in STAGE_ORDER],
        "STAGE_ORDER",
    )
    _require(
        hazards["schema"] == hazard_contract.PHYSICAL_ONBOARDING_HAZARD_REGISTER_SCHEMA
        and hazards["runtime_activation"] is False
        and _canonical(hazards["authority"])
        == _canonical(hazard_contract._EXPECTED_AUTHORITY),
        "HAZARD_AUTHORITY",
    )
    # Reuse the existing pure typed parser, not a second hazard vocabulary.
    parsed_hazards = [
        hazard_contract._parse_hazard(row, index)
        for index, row in enumerate(hazards["hazards"])
    ]
    _require(
        [h.id for h in parsed_hazards] == [f"HZ-{i:03d}" for i in range(1, 17)],
        "HAZARD_SET",
    )
    _require(
        epochs["schema"] == epoch_contract.CONFIGURATION_EPOCH_POLICY_SCHEMA
        and epochs["runtime_activation"] is False
        and _canonical(epochs["authority"])
        == _canonical(epoch_contract._EXPECTED_AUTHORITY),
        "EPOCH_AUTHORITY",
    )
    _require(
        [row["id"] for row in epochs["epochs"]]
        == list(epoch_contract._EXPECTED_EPOCH_IDS),
        "EPOCH_SET",
    )
    epoch_rows = []
    for row in epochs["epochs"]:
        _exact(
            row,
            {
                "id",
                "description",
                "change_triggers",
                "invalidates_from_stage",
                "required_bindings",
            },
        )
        _require(
            row["invalidates_from_stage"]
            == epoch_contract._EXPECTED_INVALIDATES_FROM_STAGE[row["id"]].value,
            "EPOCH_BOUNDARY",
        )
        epoch_rows.append(
            {
                "epoch_id": row["id"],
                "status": "UNMEASURED",
                "value": None,
                **{
                    key: row[key]
                    for key in (
                        "description",
                        "change_triggers",
                        "invalidates_from_stage",
                        "required_bindings",
                    )
                },
            }
        )
    deferred = catalog["deferred_acceptance"]
    _require(
        deferred
        == [
            {
                "record_id": "INT-005",
                "observation_owner_stage": "camera_receipt",
                "observation_requirement": "MEASUREMENT_AND_EVIDENCE_REQUIRED",
                "observation_acceptance_allowed": False,
                "acceptance_owner_stage": "noncontact_acceptance",
                "acceptance_prerequisites": ["TARGET_ACCURACY_BUDGET_CLOSED"],
            }
        ]
        and deferred[0]["observation_acceptance_allowed"] is False,
        "DEFERRED_ACCEPTANCE_CHANGED",
    )
    stage_rows, hazard_ids = [], set()
    for index, (stage, raw) in enumerate(zip(STAGE_ORDER[:4], catalog["stages"][:4])):
        _exact(
            raw,
            {
                "stage",
                "required_effect_classes",
                "actuator_power_requirement",
                "intake_record_ids",
                "owned_artifacts",
                "produced_bundle_components",
                "hazard_banner_ids",
            },
        )
        _require(
            raw["intake_record_ids"]
            == list(stage_contract._EXPECTED_INTAKE_BY_STAGE[stage])
            and raw["required_effect_classes"]
            == [e.value for e in stage_contract._EXPECTED_EFFECTS_BY_STAGE[stage]]
            and raw["hazard_banner_ids"]
            == list(stage_contract._EXPECTED_HAZARDS_BY_STAGE[stage])
            and raw["actuator_power_requirement"] == "DISCONNECTED_REQUIRED",
            "STAGE_SCOPE",
        )
        intake_rows = []
        for record_id in raw["intake_record_ids"]:
            row = documents["intake_template"][record_id]
            intake_rows.append(
                {
                    **{
                        key: row[key]
                        for key in (
                            "record_id",
                            "assembly",
                            "measurement",
                            "unit",
                            "candidate_or_requirement",
                        )
                    },
                    "template_phase": row["stage"],
                    "template_status": row["status"],
                    "template_notes": row["notes"],
                    "required_observation_fields": list(_OBSERVATION_FIELDS),
                    "observation": None,
                    "acceptance": {
                        "status": (
                            "DEFERRED_LIMIT"
                            if record_id == "INT-005"
                            else "NOT_ASSESSED"
                        ),
                        "owner_stage": (
                            "noncontact_acceptance"
                            if record_id == "INT-005"
                            else stage.value
                        ),
                        "prerequisites": (
                            ["TARGET_ACCURACY_BUDGET_CLOSED"]
                            if record_id == "INT-005"
                            else []
                        ),
                        "measurement_required": True,
                    },
                }
            )
        hazard_ids.update(raw["hazard_banner_ids"])
        stage_rows.append(
            {
                "stage": stage.value,
                "status": "REQUIREMENTS_ONLY",
                **{
                    key: raw[key]
                    for key in (
                        "required_effect_classes",
                        "actuator_power_requirement",
                        "owned_artifacts",
                    )
                },
                "hazard_ids": raw["hazard_banner_ids"],
                "intake_rows": intake_rows,
                "required_records": list(_RECORDS[index]),
            }
        )
    return {
        "stages": stage_rows,
        "hazards": [h.to_dict() for h in parsed_hazards if h.id in hazard_ids],
        "epochs": epoch_rows,
    }


def _context(data: dict[str, Any]) -> tuple[Any, Any]:
    selected = data["selection"]
    selection_summary = None
    if selected is not None:
        _exact(selected, {"payload_ascii", "sha256"})
        _require(type(selected["payload_ascii"]) is str)
        value = PhysicalCameraSelection(selected["payload_ascii"].encode("ascii"))
        _require(value.sha256 == selected["sha256"], "SELECTION_HASH")
        _require(
            value.identity_document["source_sha256"] == data["binding"]["source_sha256"]
            and value.identity_document["launch_session_id"]
            == data["binding"]["launch_session_id"],
            "SELECTION_BINDING",
        )
        selection_summary = value.safe_summary()
    preflight = data["source_preflight"]
    preflight_summary = None
    if preflight is not None:
        _exact(preflight, {"payload_ascii", "sha256", "origin"})
        _require(preflight["origin"] == "RETAINED_SEPARATE_SOURCE_ONLY_DIAGNOSTIC")
        _require(type(preflight["payload_ascii"]) is str)
        report = PhysicalSourcePreflightReport(
            preflight["payload_ascii"].encode("ascii")
        )
        _require(report.sha256 == preflight["sha256"], "PREFLIGHT_HASH")
        view = report.safe_summary()
        _require(
            view["binding"]["workspace_source_sha256"]
            == data["binding"]["source_sha256"],
            "PREFLIGHT_SOURCE",
        )
        preflight_summary = {
            "report_sha256": report.sha256,
            "outcome": view["outcome"],
            "origin_session_id": view["binding"]["session_id"],
            "canonical_stage_pass": False,
            "power_state": "UNKNOWN",
        }
    return selection_summary, preflight_summary


def _decode(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 1 <= len(payload) <= MAX_EVIDENCE_BYTES,
        "EVIDENCE_BYTE_LIMIT",
    )
    try:
        data = _exact(
            _json(payload),
            {
                "schema",
                "status",
                "binding",
                "source_observations",
                "source_files",
                "requirements",
                "selection",
                "source_preflight",
                "power_state",
                "canonical_stage_pass",
                "physical_authority",
                "qualified",
                "device_io_performed",
                "meaning",
            },
        )
        _require(_canonical(data) == payload, "NONCANONICAL_DOCUMENT")
        _require(
            data["schema"] == SCHEMA
            and data["status"] == "REQUIREMENTS_RETAINED_NOT_ASSESSED"
            and data["meaning"] == _MEANING
        )
        binding = _exact(
            data["binding"], {"source_sha256", "session_id", "launch_session_id"}
        )
        _sha(binding["source_sha256"])
        _identifier(binding["session_id"])
        _identifier(binding["launch_session_id"])
        _require(
            data["power_state"] == "UNKNOWN"
            and all(
                data[key] is False
                for key in (
                    "canonical_stage_pass",
                    "physical_authority",
                    "qualified",
                    "device_io_performed",
                )
            ),
            "AUTHORITY_REFUSED",
        )
        observations = _exact(
            data["source_observations"],
            {
                "before_source_sha256",
                "after_source_sha256",
                "fixed_source_sha256",
                "consistency_scope",
            },
        )
        _require(
            observations["before_source_sha256"]
            == observations["after_source_sha256"]
            == binding["source_sha256"]
            and observations["consistency_scope"]
            == "BOUNDED_BEFORE_AFTER_NOT_HOSTILE_WRITER_ISOLATION",
            "SOURCE_CHANGED",
        )
        documents = _source_documents(data["source_files"])
        metadata = [
            {key: row[key] for key in ("role", "relative_path", "bytes", "sha256")}
            for row in data["source_files"]
        ]
        _require(
            observations["fixed_source_sha256"] == _hash(_canonical(metadata)),
            "SOURCE_SNAPSHOT_HASH",
        )
        _require(
            _canonical(data["requirements"]) == _canonical(_requirements(documents)),
            "REQUIREMENTS_CHANGED",
        )
        _context(data)
        return data
    except PhysicalCameraPrerequisitesError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise PhysicalCameraPrerequisitesError() from None


@dataclass(frozen=True, slots=True)
class PhysicalCameraPrerequisites:
    payload: bytes

    def __post_init__(self) -> None:
        _decode(self.payload)

    @property
    def evidence_sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = _decode(self.payload)
        selection, preflight = _context(data)
        missing = list(_MISSING)
        missing.append(
            "SOURCE_PREFLIGHT_NOT_SUPPLIED"
            if preflight is None
            else "SOURCE_PREFLIGHT_ONLY_NOT_CANONICAL_ACCEPTANCE"
        )
        if preflight is not None and preflight["outcome"] != "FILE_CHECKS_COHERENT":
            missing.append("SOURCE_PREFLIGHT_HELD")
        missing.append(
            "CURRENT_CAMERA_SELECTION_NOT_SUPPLIED"
            if selection is None
            else "METADATA_SELECTION_ONLY_NOT_RECEIVED_UNIT_QUALIFICATION"
        )
        return {
            "schema": SUMMARY_SCHEMA,
            "status": data["status"],
            "binding": data["binding"],
            "evidence_sha256": self.evidence_sha256,
            "source_files": [
                {key: row[key] for key in ("role", "relative_path", "bytes", "sha256")}
                for row in data["source_files"]
            ],
            **data["requirements"],
            "metadata_selection": selection,
            "source_preflight": preflight,
            "missing_requirements": missing,
            **{
                key: data[key]
                for key in (
                    "power_state",
                    "canonical_stage_pass",
                    "physical_authority",
                    "qualified",
                    "device_io_performed",
                    "meaning",
                )
            },
        }


def verify_physical_camera_prerequisites(
    payload: bytes,
    *,
    expected_source_sha256: str,
    expected_session_id: str,
    expected_launch_session_id: str,
    expected_evidence_sha256: str,
) -> PhysicalCameraPrerequisites:
    for value in (expected_source_sha256, expected_evidence_sha256):
        _sha(value)
    for value in (expected_session_id, expected_launch_session_id):
        _identifier(value)
    result = PhysicalCameraPrerequisites(payload)
    _require(result.evidence_sha256 == expected_evidence_sha256, "EVIDENCE_HASH")
    _require(
        result.to_dict()["binding"]
        == {
            "source_sha256": expected_source_sha256,
            "session_id": expected_session_id,
            "launch_session_id": expected_launch_session_id,
        },
        "EXPECTED_BINDING",
    )
    return result


def collect_physical_camera_prerequisites(
    workspace: Path,
    *,
    source_sha256: str,
    session_id: str,
    launch_session_id: str,
    cancellation: Event,
    deadline_ns: int,
    selection: PhysicalCameraSelection | None = None,
    source_preflight_report: PhysicalSourcePreflightReport | None = None,
    expected_source_preflight_sha256: str | None = None,
) -> PhysicalCameraPrerequisites:
    """Explicit bounded file-only collection; no automatic observation or review."""
    _sha(source_sha256)
    _identifier(session_id)
    _identifier(launch_session_id)
    _require(isinstance(cancellation, Event), "CANCELLATION_REQUIRED")
    now = time.monotonic_ns()
    _require(
        type(deadline_ns) is int
        and 0 < deadline_ns - now <= MAX_COLLECTION_DURATION_NS,
        "DEADLINE_BOUND",
    )

    def check() -> None:
        _require(not cancellation.is_set(), "COLLECTION_CANCELLED")
        _require(time.monotonic_ns() < deadline_ns, "COLLECTION_DEADLINE")

    def snapshot() -> list[dict[str, Any]]:
        result = []
        for role, relative in SOURCES:
            check()
            path = require_regular_path(workspace / relative, directory=False)
            raw = read_bounded_regular_file(path, maximum_bytes=MAX_SOURCE_BYTES)
            check()
            result.append(
                {
                    "role": role,
                    "relative_path": relative,
                    "bytes": len(raw),
                    "sha256": _hash(raw),
                    "payload_utf8": raw.decode("utf-8"),
                }
            )
        return result

    # Type/source joins precede file access; an arbitrary dict cannot impersonate
    # current reviewed enrollment or a retained actual-source report.
    selected = None
    if selection is not None:
        _require(type(selection) is PhysicalCameraSelection, "SELECTION_TYPE")
        selected = {
            "payload_ascii": selection.payload.decode("ascii"),
            "sha256": selection.sha256,
        }
    preflight = None
    if source_preflight_report is None:
        _require(expected_source_preflight_sha256 is None, "PREFLIGHT_REQUIRED")
    else:
        _require(
            type(source_preflight_report) is PhysicalSourcePreflightReport,
            "PREFLIGHT_TYPE",
        )
        _sha(expected_source_preflight_sha256)
        _require(
            source_preflight_report.sha256 == expected_source_preflight_sha256,
            "PREFLIGHT_HASH",
        )
        preflight = {
            "payload_ascii": source_preflight_report.payload.decode("ascii"),
            "sha256": source_preflight_report.sha256,
            "origin": "RETAINED_SEPARATE_SOURCE_ONLY_DIAGNOSTIC",
        }
    binding = {
        "source_sha256": source_sha256,
        "session_id": session_id,
        "launch_session_id": launch_session_id,
    }
    _context({"binding": binding, "selection": selected, "source_preflight": preflight})
    try:
        check()
        before = source_fingerprint(workspace)
        check()
        _require(before == source_sha256, "SOURCE_CHANGED")
        rows = snapshot()
        catalog = stage_contract.load_physical_onboarding_stage_catalog(workspace)
        check()
        hazards = hazard_contract.load_physical_onboarding_hazards(workspace)
        check()
        epochs = epoch_contract.load_configuration_epoch_policy(workspace)
        check()
        intake = assess_hardware_intake(workspace, Path(SOURCES[3][1]))
        check()
        _require(
            [
                catalog.source_sha256,
                hazards.source_sha256,
                epochs.source_sha256,
                intake.template_sha256,
            ]
            == [row["sha256"] for row in rows],
            "VALIDATOR_SOURCE_CHANGED",
        )
        _require(
            not intake.review_ready_record_ids and not intake.evidence_bindings,
            "TEMPLATE_IS_NOT_OBSERVATIONS",
        )
        _require(snapshot() == rows, "SOURCE_FILES_CHANGED")
        after = source_fingerprint(workspace)
        check()
        _require(after == before, "SOURCE_CHANGED")
        data = {
            "schema": SCHEMA,
            "status": "REQUIREMENTS_RETAINED_NOT_ASSESSED",
            "binding": binding,
            "source_observations": {
                "before_source_sha256": before,
                "after_source_sha256": after,
                "fixed_source_sha256": _hash(
                    _canonical(
                        [
                            {
                                key: row[key]
                                for key in ("role", "relative_path", "bytes", "sha256")
                            }
                            for row in rows
                        ]
                    )
                ),
                "consistency_scope": "BOUNDED_BEFORE_AFTER_NOT_HOSTILE_WRITER_ISOLATION",
            },
            "source_files": rows,
            "requirements": _requirements(_source_documents(rows)),
            "selection": selected,
            "source_preflight": preflight,
            "power_state": "UNKNOWN",
            "canonical_stage_pass": False,
            "physical_authority": False,
            "qualified": False,
            "device_io_performed": False,
            "meaning": _MEANING,
        }
        result = PhysicalCameraPrerequisites(_canonical(data))
        check()
        return result
    except PhysicalCameraPrerequisitesError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
        RecursionError,
        PhysicalOnboardingDurabilityError,
    ):
        raise PhysicalCameraPrerequisitesError("COLLECTION_SOURCE_INVALID") from None
