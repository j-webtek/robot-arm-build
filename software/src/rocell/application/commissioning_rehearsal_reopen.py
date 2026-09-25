"""Explicit, fail-closed reopening of existing incapable REHEARSAL sessions.

Discovery reads bounded metadata only. Opening requalifies the original M1
volume and audits committed state under the existing CELL/SESSION lease. No
session is created, no request/permit is reconstructed for use, and no attempt
is dispatched, replayed, repaired or cleared. Returned review state is bound to
one exact journal/evidence challenge, not a durable approval capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, NoReturn

from rocell.application.cell_commissioning_coordinator import INCAPABLE_COMPOSITION
from rocell.application.commissioning_m1_persistence import (
    FactsProvider,
    M1CommissioningPersistence,
    rehearsal_source_binding,
)
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    STAGE_ORDER,
)
from rocell.application.physical_onboarding_durability import (
    read_bounded_regular_file,
    safe_root,
)
from rocell.application.physical_onboarding_m1 import (
    M1CellDescriptor,
    M1RuntimeVerification,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_v2 import (
    V2CommittedHead,
    V2SessionHeader,
    V2SessionSnapshot,
    V2StageState,
    _parse_header,
)
from rocell.application.wizard_diagnostic_export import _directory_guard


MAX_ROOTS = 4
MAX_STORES_PER_ROOT = 32
MAX_STORE_ENTRIES = 128
MAX_METADATA_BYTES = 64 * 1024
MAX_EVIDENCE_ITEMS = 128
MAX_EVIDENCE_BYTES = 128 * 1024
MAX_STORE_FILES = 2048
MAX_STORE_BYTES = 32 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED_STAGES = set(STAGE_ORDER[:14])
_CAMERA = set(STAGE_ORDER[4:6])
_OPTICS = set(STAGE_ORDER[6:8])
_ARM_IDENTITY = PhysicalOnboardingStage.ARM_IDENTITY
_POWER = set(STAGE_ORDER[9:11])
_FEEDBACK = PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
_REFERENCE = PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION
_NONCONTACT = PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
_EVALUATED_SCHEMAS = {
    **{stage: "rocell.rehearsal_optics_receipt.v1" for stage in _OPTICS},
    _ARM_IDENTITY: "rocell.rehearsal_arm_identity_receipt.v1",
    **{stage: "rocell.rehearsal_power_receipt.v1" for stage in _POWER},
    _FEEDBACK: "rocell.rehearsal_feedback_receipt.v1",
    _REFERENCE: "rocell.rehearsal_reference_receipt.v1",
    _NONCONTACT: "rocell.rehearsal_noncontact_receipt.v1",
}
_OWNED_FEEDBACK_SCHEMA = "rocell.rehearsal_owned_feedback_receipt.v1"
_ALL_EVALUATED_SCHEMAS = set(_EVALUATED_SCHEMAS.values()) | {_OWNED_FEEDBACK_SCHEMA}


def _evaluated_schemas(stage: PhysicalOnboardingStage) -> set[str]:
    values = {_EVALUATED_SCHEMAS[stage]} if stage in _EVALUATED_SCHEMAS else set()
    return values | ({_OWNED_FEEDBACK_SCHEMA} if stage is _FEEDBACK else set())


_EVALUATED_OPEN_SCHEMAS = {
    **{stage: "rocell.rehearsal_optics_stage_open.v1" for stage in _OPTICS},
    _ARM_IDENTITY: "rocell.rehearsal_arm_identity_stage_open.v1",
    **{stage: "rocell.rehearsal_power_stage_open.v1" for stage in _POWER},
    _FEEDBACK: "rocell.rehearsal_feedback_stage_open.v1",
    _REFERENCE: "rocell.rehearsal_reference_stage_open.v1",
    _NONCONTACT: "rocell.rehearsal_noncontact_stage_open.v1",
}
_COMMON = {
    "schema",
    "composition",
    "stage",
    "session_id",
    "cell_id",
    "workspace_source_sha256",
    "operator_id",
    "catalog_sha256",
    "physical_observation",
}
_MODE = {
    "width": 5472,
    "height": 3648,
    "fps_numerator": 9,
    "fps_denominator": 1,
    "pixel_format": "YUY2",
}
_PROBE_RECEIPT_SCHEMA = "rocell.rehearsal_camera_probe_receipt.v1"
_CONFIGURATION_RECEIPT_SCHEMA = "rocell.rehearsal_camera_configuration_receipt.v1"
_CAMERA_AUX_SCHEMAS = {_PROBE_RECEIPT_SCHEMA, _CONFIGURATION_RECEIPT_SCHEMA}


class RehearsalReopenError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise RehearsalReopenError(code, message)


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            _fail("CORRUPT_METADATA", "Duplicate JSON field in retained evidence.")
        result[key] = value
    return result


def _document(
    path: Path, *, maximum: int, newline: bool, pretty: bool = False
) -> tuple[dict[str, Any], bytes]:
    payload = read_bounded_regular_file(path, maximum_bytes=maximum)
    value = json.loads(payload.decode("ascii"), object_pairs_hook=_pairs)
    canonical = (
        json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        ).encode("ascii")
        if pretty
        else _json(value)
    )
    if type(value) is not dict or canonical + (b"\n" if newline else b"") != payload:
        _fail("CORRUPT_METADATA", "Retained JSON is not a canonical object.")
    return value, payload


def _entries(path: Path, maximum: int) -> list[Path]:
    safe_root(path, label="rehearsal directory")
    result = list(islice(path.iterdir(), maximum + 1))
    if len(result) > maximum:
        _fail("DISCOVERY_LIMIT", "Directory exceeds the bounded entry budget.")
    return sorted(result, key=lambda item: item.name)


def _regular(path: Path) -> os.stat_result:
    value = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_nlink != 1
        or getattr(value, "st_file_attributes", 0) & 0x400
    ):
        _fail(
            "UNSAFE_PATH", "Retained file is a link, reparse point or nonregular file."
        )
    return value


@dataclass(frozen=True)
class KnownRehearsalRoot:
    root_id: str
    directory: Path

    def __post_init__(self) -> None:
        if type(self.root_id) is not str or not _ID.fullmatch(self.root_id):
            _fail("INVALID_REGISTRY", "Root ID must be a bounded identifier.")
        selected = Path(self.directory)
        if (
            not selected.is_absolute()
            or selected == Path(selected.anchor)
            or ".." in selected.parts
            or str(selected).startswith(("\\\\", "//"))
        ):
            _fail("INVALID_REGISTRY", "Assign an absolute local non-root directory.")
        object.__setattr__(self, "directory", selected)


@dataclass(frozen=True)
class ReopenHoldReason:
    code: str
    message: str
    remediation: str = (
        "Inspect/export retained state. Do not reset, repair or replay it."
    )


@dataclass(frozen=True)
class RehearsalStoreChoice:
    choice_id: str
    root_id: str
    directory: Path
    cell_id: str
    session_id: str
    session_header_sha256: str
    discovery_sha256: str
    source_matches: bool
    status: str = "DISCOVERED_NOT_OPENED"


@dataclass(frozen=True)
class RehearsalDiscovery:
    choices: tuple[RehearsalStoreChoice, ...] = ()
    issues: tuple[ReopenHoldReason, ...] = ()
    storage_qualified: bool = False
    physical_authority: bool = False


@dataclass(frozen=True)
class VerifiedRehearsalEvidence:
    reference: EvidenceReference
    payload: bytes
    captured_at_ns: int

    def document(self) -> dict[str, Any]:
        """A fresh display copy; retained bytes/reference stay immutable."""
        return json.loads(self.payload)


@dataclass(frozen=True)
class RestoredRehearsalState:
    directory: Path
    cell_id: str
    session_id: str
    stage: PhysicalOnboardingStage | None
    stage_state: V2StageState | None
    disposition: str
    receipt: VerifiedRehearsalEvidence | None
    assessment: VerifiedRehearsalEvidence | None
    selected_camera: VerifiedRehearsalEvidence | None
    operator_id: str | None
    camera_settings: VerifiedRehearsalEvidence | None
    latest_capture: VerifiedRehearsalEvidence | None
    stage_evidence: tuple[VerifiedRehearsalEvidence, ...]
    journal_head_sha256: str
    evidence_inventory_sha256: str
    challenge_sha256: str
    session_header_sha256: str
    physical_authority: bool = False
    automatic_replay_allowed: bool = False

    @property
    def receipt_reference(self) -> EvidenceReference | None:
        return self.receipt.reference if self.receipt else None

    @property
    def assessment_reference(self) -> EvidenceReference | None:
        return self.assessment.reference if self.assessment else None


@dataclass(frozen=True)
class RehearsalReopenResult:
    status: str
    reasons: tuple[ReopenHoldReason, ...] = ()
    restored: RestoredRehearsalState | None = None
    store: M1CommissioningPersistence | None = field(default=None, repr=False)
    snapshot: V2SessionSnapshot | None = None
    verification: M1RuntimeVerification | None = None
    physical_authority: bool = False
    automatic_replay_allowed: bool = False


def _store_header(
    root: KnownRehearsalRoot, directory: Path, source: str
) -> RehearsalStoreChoice:
    if directory.parent != root.directory or not _ID.fullmatch(directory.name):
        _fail(
            "UNSAFE_PATH", "Store is not an immediate named child of its assigned root."
        )
    entries = _entries(directory, MAX_STORE_ENTRIES)
    sessions = [item for item in entries if item.name.startswith("onboarding-")]
    cells = _entries(directory / "cells", 2)
    if len(sessions) != 1 or len(cells) != 1:
        _fail(
            "AMBIGUOUS_STORE",
            "This reopen slice requires exactly one original cell/session per store.",
        )
    session = safe_root(sessions[0], label="rehearsal session")
    cell = safe_root(cells[0], label="rehearsal cell")
    header_raw, header_bytes = _document(
        session / "header.json", maximum=MAX_METADATA_BYTES, newline=True, pretty=True
    )
    header = _parse_header(header_raw)
    descriptor_raw, descriptor_bytes = _document(
        cell / "cell.json", maximum=MAX_METADATA_BYTES, newline=True
    )
    descriptor = M1CellDescriptor.from_dict(descriptor_raw)
    if (
        header.mode != "REHEARSAL"
        or header.cell_id != descriptor.cell_id
        or header.source_binding_sha256 != descriptor.source_binding_sha256
        or header.durability_qualification_sha256
        != descriptor.durability_qualification_sha256
        or session.name != "onboarding-" + header.session_id
        or cell.name != "cell-" + descriptor.cell_key_sha256
    ):
        _fail(
            "HEADER_BINDING_MISMATCH",
            "Store is not the exact immutable REHEARSAL cell/session.",
        )
    identity = directory.stat(follow_symlinks=False)
    anchor = read_bounded_regular_file(
        directory / "durability-anchor.json", maximum_bytes=MAX_METADATA_BYTES
    )
    discovery = _hash(
        {
            "root_id": root.root_id,
            "directory": str(directory),
            "identity": [identity.st_dev, identity.st_ino],
            "header": hashlib.sha256(header_bytes).hexdigest(),
            "cell": hashlib.sha256(descriptor_bytes).hexdigest(),
            "anchor": hashlib.sha256(anchor).hexdigest(),
        }
    )
    return RehearsalStoreChoice(
        "reopen-" + _hash([root.root_id, directory.name])[:32],
        root.root_id,
        directory,
        header.cell_id,
        header.session_id,
        header.header_sha256,
        discovery,
        header.source_binding_sha256 == rehearsal_source_binding(source),
    )


def _preflight_store(directory: Path) -> None:
    """Bound the existing M1 readers before they inspect this selected store."""
    pending = [(directory, 0)]
    files = total = entry_count = 0
    while pending:
        folder, depth = pending.pop()
        if depth > 5:
            _fail("STORE_RESOURCE_LIMIT", "Retained store exceeds the supported depth.")
        for path in _entries(folder, MAX_STORE_FILES):
            entry_count += 1
            if entry_count > MAX_STORE_FILES:
                _fail(
                    "STORE_RESOURCE_LIMIT",
                    "Retained store exceeds the total file/directory entry budget.",
                )
            # Binary fixtures have their own strict, content-verified format and
            # much larger native payload budget. Never feed those files through
            # the small M1 metadata reader; association is checked separately.
            if depth == 0 and re.fullmatch(r"binary-fixture-[0-9a-f]{32}", path.name):
                safe_root(path, label="retained binary fixture")
                continue
            if path.name.startswith(".partial"):
                _fail(
                    "ORPHAN_PARTIAL_OUTPUT",
                    "A partial output remains in the original store.",
                )
            metadata = path.stat(follow_symlinks=False)
            if getattr(metadata, "st_file_attributes", 0) & 0x400 or stat.S_ISLNK(
                metadata.st_mode
            ):
                _fail("UNSAFE_PATH", "Retained store contains a link/reparse point.")
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((path, depth + 1))
            else:
                metadata = _regular(path)
                files += 1
                total += metadata.st_size
                if (
                    files > MAX_STORE_FILES
                    or total > MAX_STORE_BYTES
                    or metadata.st_size > 1024 * 1024
                ):
                    _fail(
                        "STORE_RESOURCE_LIMIT",
                        "Retained store exceeds the bounded reopen byte/file budget.",
                    )


def _exact(value: dict[str, Any], names: set[str]) -> None:
    if set(value) != names:
        _fail(
            "EVIDENCE_SCHEMA_MISMATCH",
            "Unknown or missing fields in retained rehearsal evidence.",
        )


def _settings(document: dict[str, Any]) -> None:
    _exact(document, {"brightness_offset", "exposure_policy", "mode"})
    offset = document["brightness_offset"]
    if (
        type(offset) is not int
        or not -64 <= offset <= 64
        or document["exposure_policy"] != "SYNTHETIC_LUMA_OFFSET_NOT_DRIVER_CONTROL"
        or document["mode"] != _MODE
        or any(
            type(document["mode"][key]) is not type(value)
            for key, value in _MODE.items()
        )
    ):
        _fail(
            "SETTINGS_BINDING_MISMATCH",
            "Retained synthetic settings are not the registered exact mode.",
        )


def _read_evidence(
    directory: Path, snapshot: V2SessionSnapshot, source: str, catalog: str
) -> dict[str, VerifiedRehearsalEvidence]:
    if len(snapshot.evidence) > MAX_EVIDENCE_ITEMS:
        _fail(
            "EVIDENCE_RESOURCE_LIMIT", "Too many retained rehearsal evidence packages."
        )
    result = {}
    total = 0
    for reference in snapshot.evidence:
        total += reference.payload_bytes
        if (
            reference.payload_bytes > MAX_EVIDENCE_BYTES
            or total > 8 * MAX_EVIDENCE_BYTES
        ):
            _fail(
                "EVIDENCE_RESOURCE_LIMIT",
                "Retained rehearsal evidence exceeds its reconstruction byte budget.",
            )
        package = (
            directory
            / ("onboarding-" + snapshot.header.session_id)
            / "evidence"
            / reference.evidence_id
        )
        document, payload = _document(
            package / "payload.bin", maximum=MAX_EVIDENCE_BYTES, newline=False
        )
        manifest, _ = _document(
            package / "manifest.json",
            maximum=MAX_METADATA_BYTES,
            newline=True,
            pretty=True,
        )
        if (
            hashlib.sha256(payload).hexdigest() != reference.payload_sha256
            or len(payload) != reference.payload_bytes
        ):
            _fail("EVIDENCE_CHANGED", "Evidence bytes changed after M1 verification.")
        if (
            document.get("composition") != INCAPABLE_COMPOSITION
            or document.get("session_id") != snapshot.header.session_id
            or document.get("stage") != reference.stage.value
            or reference.stage not in _SUPPORTED_STAGES
        ):
            _fail(
                "EVIDENCE_BINDING_MISMATCH",
                "Retained evidence has another source/session/stage/composition.",
            )
        schema = document.get("schema")
        if (
            schema
            in {
                "rocell.rehearsal_stage_receipt.v1",
                "rocell.rehearsal_camera_stage_open.v1",
                "rocell.rehearsal_camera_settings.v1",
            }
            | _ALL_EVALUATED_SCHEMAS
            | set(_EVALUATED_OPEN_SCHEMAS.values())
            | _CAMERA_AUX_SCHEMAS
        ):
            fields = set(_COMMON)
            if schema == "rocell.rehearsal_stage_receipt.v1":
                if reference.stage not in set(STAGE_ORDER[:4]):
                    _fail(
                        "EVIDENCE_BINDING_MISMATCH",
                        "A prerequisite fixture cannot replace a substantive later-stage receipt.",
                    )
                fields.add("fixture")
                if reference.stage is PhysicalOnboardingStage.CAMERA_IDENTITY:
                    fields.add("candidate")
                if document.get("fixture") != "SOURCE_BOUND_SYNTHETIC_PREREQUISITES":
                    _fail("EVIDENCE_SCHEMA_MISMATCH", "Unknown prerequisite fixture.")
            elif schema in _CAMERA_AUX_SCHEMAS:
                if reference.stage is not STAGE_ORDER[4]:
                    _fail(
                        "CAMERA_CONFIGURATION_STAGE_MISMATCH",
                        "Probe and staged configuration belong only to the first camera stage.",
                    )
                fields |= (
                    {"plan", "attempt_result", "retained_probe_sha256", "probe"}
                    if schema == _PROBE_RECEIPT_SCHEMA
                    else {
                        "probe_evidence_sha256",
                        "configuration",
                        "electronic_settings_epoch",
                        "synthetic_settings_epoch",
                        "effective_settings_epoch",
                    }
                )
            elif schema in _ALL_EVALUATED_SCHEMAS | set(
                _EVALUATED_OPEN_SCHEMAS.values()
            ):
                if schema not in _evaluated_schemas(reference.stage) | {
                    _EVALUATED_OPEN_SCHEMAS.get(reference.stage)
                }:
                    _fail(
                        "EVIDENCE_BINDING_MISMATCH",
                        "Evaluated-stage evidence belongs to another stage.",
                    )
                if schema in _ALL_EVALUATED_SCHEMAS:
                    fields |= {"evaluation", "evaluation_sha256"}
                    if reference.stage is _FEEDBACK:
                        fields |= {"attempt_result", "retained_campaign_sha256"}
                        if schema == _OWNED_FEEDBACK_SCHEMA:
                            fields |= {
                                "scenario",
                                "campaign_directory",
                                "arm_feedback_process",
                            }
            elif reference.stage not in _CAMERA:
                _fail(
                    "EVIDENCE_BINDING_MISMATCH",
                    "Camera lifecycle metadata belongs to another stage.",
                )
            if schema == "rocell.rehearsal_camera_settings.v1":
                if reference.stage is not STAGE_ORDER[4]:
                    _fail(
                        "SETTINGS_BINDING_MISMATCH",
                        "Settings may be staged only in the first camera campaign stage.",
                    )
                fields |= {"settings", "settings_epoch"}
                _settings(document["settings"])
                if document["settings_epoch"] != _hash(document["settings"]):
                    _fail(
                        "SETTINGS_BINDING_MISMATCH",
                        "Settings epoch does not match its exact settings.",
                    )
            _exact(document, fields)
            if (
                document["cell_id"] != snapshot.header.cell_id
                or document["catalog_sha256"] != catalog
            ):
                _fail(
                    "CATALOG_OR_CELL_DRIFT",
                    "Retained receipt differs from the current catalog/cell.",
                )
        elif schema in {
            "rocell.rehearsal_camera_campaign.v1",
            "rocell.rehearsal_camera_campaign.v2",
        }:
            fields = {
                "schema",
                "composition",
                "session_id",
                "stage",
                "operator_id",
                "workspace_source_sha256",
                "plan",
                "attempt_result",
                "physical_observation",
            }
            if schema.endswith(".v2"):
                fields.add("capture_dataset")
            if (
                document.get("plan", {}).get("process_backend")
                == "OWNED_INCAPABLE_CAMERA_PROCESS"
            ):
                if not schema.endswith(".v2"):
                    _fail(
                        "OWNED_CAMERA_SCHEMA_MISMATCH",
                        "Owned camera evidence requires the binary v2 receipt.",
                    )
                fields |= {"retained_campaign_sha256", "camera_process"}
                if "electronic_configuration" in document["plan"]:
                    fields.add("camera_readback")
            _exact(document, fields)
            if (
                reference.stage not in _CAMERA
                or document["attempt_result"].get("state") != "SEALED_KNOWN"
            ):
                _fail(
                    "CAMPAIGN_NOT_SEALED",
                    "A retained camera receipt is not sealed-known.",
                )
        elif schema == "rocell.rehearsal_assessment.v1":
            _exact(
                document,
                {
                    "schema",
                    "composition",
                    "session_id",
                    "stage",
                    "source_binding_sha256",
                    "pre_assessment_head_sha256",
                    "receipt_sha256",
                    "receipt_evidence_id",
                    "outcome",
                    "reason_codes",
                    "meaning",
                    "assessment_sha256",
                },
            )
            core = {
                key: value
                for key, value in document.items()
                if key != "assessment_sha256"
            }
            if (
                document["assessment_sha256"] != _hash(core)
                or document["source_binding_sha256"]
                != snapshot.header.source_binding_sha256
            ):
                _fail(
                    "ASSESSMENT_BINDING_MISMATCH",
                    "Assessment source/self hash differs.",
                )
        elif schema == "rocell.rehearsal_review.v1":
            _exact(
                document,
                {
                    "schema",
                    "composition",
                    "session_id",
                    "stage",
                    "assessment_sha256",
                    "reviewed_head_sha256",
                    "reviewer_id",
                    "operator_id",
                    "decision",
                    "physical_release_effect",
                },
            )
            if (
                document["decision"] != "ACCEPT_EXACT_ASSESSMENT"
                or document["physical_release_effect"] != "NONE"
                or type(document["reviewer_id"]) is not str
                or not _ACTOR.fullmatch(document["reviewer_id"])
                or document["reviewer_id"] == document["operator_id"]
            ):
                _fail(
                    "REVIEW_BINDING_MISMATCH",
                    "Retained review is not a distinct exact synthetic review.",
                )
        else:
            _fail(
                "UNKNOWN_REHEARSAL_EVIDENCE",
                "Unknown retained evidence schema; no approval reconstructed.",
            )
        if "workspace_source_sha256" in document and (
            document["workspace_source_sha256"] != source
            or document.get("physical_observation") is not False
        ):
            _fail(
                "SOURCE_DRIFT",
                "Evidence does not bind the current incapable workspace source.",
            )
        if "operator_id" in document and (
            type(document["operator_id"]) is not str
            or not _ACTOR.fullmatch(document["operator_id"])
        ):
            _fail(
                "OPERATOR_BINDING_MISMATCH",
                "Retained operator is not an exact bounded identifier.",
            )
        result[reference.evidence_id] = VerifiedRehearsalEvidence(
            reference, payload, manifest["captured_at_ns"]
        )
    return result


def _verify_camera_probe_receipt(
    document: dict[str, Any],
    source: str,
    records: dict[str, dict[str, Any]],
    *,
    directory: Path | None = None,
) -> Any:
    """Join one retained probe to its already-audited consumed M1 campaign.

    Caller owns the original CELL/SESSION leases and ``tx._audit_records()``.
    The only filesystem read is the bounded fixed child-script source pin.
    No executable worker, camera probe or process is reconstructed for use.
    """
    from dataclasses import asdict
    from rocell.application.cell_commissioning_coordinator import (
        CampaignBudget,
        CampaignRegistration,
        CommissioningMode,
        MAX_RETAINED_CAMPAIGN_BYTES,
        ObservedPowerState,
        WorkerReceipt,
    )
    from rocell.application.commissioning_m1_persistence import (
        M1RehearsalTransaction,
        _decode_permit,
    )
    from rocell.application.physical_onboarding_leases import LeaseLevel
    from rocell.application.rehearsal_camera_probe_evidence import (
        verify_rehearsal_camera_probe_evidence,
    )
    from rocell.providers.windows.owned_camera_codec import (
        CAMERA_FIXTURE_PATH,
        FRAME_BYTES,
    )
    from rocell.safety.effects import EffectCertainty, EffectClass

    _exact(
        document, _COMMON | {"plan", "attempt_result", "retained_probe_sha256", "probe"}
    )
    _exact(
        document["plan"],
        {
            "composition",
            "process_backend",
            "selected_camera",
            "fault",
            "native_duration_ms",
            "process_timeout_ms",
            "process_cleanup_timeout_ms",
            "stdout_bytes",
            "stderr_bytes",
            "frames_requested",
            "control_writes_requested",
            "artifact_qualification",
        },
    )
    expected_plan = {
        "composition": INCAPABLE_COMPOSITION,
        "process_backend": "OWNED_INCAPABLE_CAMERA_PROBE",
        "selected_camera": {
            "candidate_id": "synthetic-b0477",
            "provenance": "SYNTHETIC_NOT_ENUMERATED",
            "model": "B0477",
            "unit_id": "SYNTHETIC-UNIT-A",
            "endpoint": "incapable-fixture-only",
        },
        "fault": "none",
        "native_duration_ms": 5000,
        "process_timeout_ms": 10000,
        "process_cleanup_timeout_ms": 2000,
        "stdout_bytes": 32768,
        "stderr_bytes": 8192,
        "frames_requested": 0,
        "control_writes_requested": 0,
        "artifact_qualification": "DIAGNOSTIC_ONLY_NOT_PHYSICAL_QUALIFICATION",
    }
    if (
        document["schema"] != _PROBE_RECEIPT_SCHEMA
        or document["composition"] != INCAPABLE_COMPOSITION
        or document["stage"] != STAGE_ORDER[4].value
        or document["workspace_source_sha256"] != source
        or document["physical_observation"] is not False
        or type(document["operator_id"]) is not str
        or _ACTOR.fullmatch(document["operator_id"]) is None
        or _json(document["plan"]) != _json(expected_plan)
    ):
        _fail(
            "CAMERA_PROBE_PLAN_MISMATCH",
            "Probe is not the exact source-bound closed incapable plan.",
        )
    result = document["attempt_result"]
    if type(result) is not dict or result.get("state") != "SEALED_KNOWN":
        _fail(
            "CAMERA_PROBE_NOT_KNOWN",
            "Probe auxiliary evidence requires an already-known retained campaign.",
        )
    attempt = result["attempt_id"]
    grouped = {
        kind: [
            record
            for record in records.values()
            if record["kind"] == kind and record["data"].get("attempt_id") == attempt
        ]
        for kind in (
            "EXACT_REQUEST_RESERVED",
            "CAMPAIGN_RESULT",
            "CAMPAIGN_EVIDENCE",
            "CAMPAIGN_RECEIPT",
        )
    }
    if any(
        len(grouped[kind]) != (2 if kind == "CAMPAIGN_RECEIPT" else 1)
        for kind in grouped
    ):
        _fail(
            "CAMERA_PROBE_RECORD_MISMATCH",
            "One exact reservation/result/blob and both lifecycle receipts are required.",
        )
    lifecycle = grouped["CAMPAIGN_RECEIPT"]
    if (
        {r["data"].get("state") for r in lifecycle}
        != {"EFFECT_OBSERVED", "CLEANUP_CONFIRMED"}
        or _json(grouped["CAMPAIGN_RESULT"][0]["data"].get("result")) != _json(result)
        or any(
            _json(r["data"].get("receipt")) != _json(result.get("receipt"))
            for r in lifecycle
        )
    ):
        _fail(
            "CAMERA_PROBE_RECORD_MISMATCH",
            "Probe result and lifecycle receipts differ.",
        )
    permit = _decode_permit(grouped["EXACT_REQUEST_RESERVED"][0]["data"]["permit"])
    worker_sha = hashlib.sha256(
        read_bounded_regular_file(CAMERA_FIXTURE_PATH, maximum_bytes=1024 * 1024)
    ).hexdigest()
    registration = CampaignRegistration(
        "rehearsal-owned-camera-probe",
        STAGE_ORDER[4],
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        "incapable-owned-camera-probe",
        worker_sha,
        _hash(expected_plan),
        (LeaseLevel.CAMERA,),
        CampaignBudget(60000, MAX_RETAINED_CAMPAIGN_BYTES, 1, 0, 0, 0, 1),
    )
    if (
        permit.registration != registration
        or permit.attempt_id != attempt
        or permit.admission.cell_id != document["cell_id"]
        or permit.request.session_id != document["session_id"]
        or permit.admission.mode is not CommissioningMode.REHEARSAL
        or permit.admission.source_binding_sha256 != rehearsal_source_binding(source)
        or permit.admission.selected_identity_sha256
        != _hash(expected_plan["selected_camera"])
        or permit.admission.stage_state is not V2StageState.WAITING_OPERATOR
        or permit.admission.quarantine_latched
        or permit.admission.unresolved_attempts
        or permit.admission.open_blocker_ids
        or permit.envelope is not None
        or result.get("composition") != INCAPABLE_COMPOSITION
        or result.get("physical_authority") != "NONE"
        or result.get("reason_codes") != []
        or result.get("quarantine_latched") is not False
        or result.get("permit_sha256") != permit.permit_sha256
        or any(
            r["data"].get("permit_sha256") != permit.permit_sha256
            for group in grouped.values()
            for r in group
        )
    ):
        _fail(
            "CAMERA_PROBE_PERMIT_MISMATCH",
            "Probe differs from its exact source/session/identity/registration permit.",
        )
    blobs = M1RehearsalTransaction._decode_campaign_evidence(
        permit, grouped["CAMPAIGN_EVIDENCE"][0]
    )
    if (
        len(blobs) != 1
        or blobs[0].schema != "rocell.rehearsal_camera_probe_evidence.v1"
        or blobs[0].label != "owned-camera-probe"
        or blobs[0].payload_sha256 != document["retained_probe_sha256"]
    ):
        _fail(
            "CAMERA_PROBE_BLOB_MISMATCH",
            "Probe does not select its exact complete retained blob.",
        )
    receipt = M1RehearsalTransaction._decode_receipt(result["receipt"])
    M1RehearsalTransaction._match_campaign_evidence(receipt, blobs)
    artifact = verify_rehearsal_camera_probe_evidence(
        blobs[0].payload,
        {
            "session_id": document["session_id"],
            "attempt_id": attempt,
            "source_sha256": source,
            "permit_sha256": permit.permit_sha256,
            "operation_sha256": registration.operation_sha256,
            "selected_identity_sha256": permit.admission.selected_identity_sha256,
        },
    )
    expected_receipt = WorkerReceipt(
        attempt,
        permit.permit_sha256,
        worker_sha,
        permit.admission.selected_identity_sha256,
        EffectCertainty.CONFIRMED,
        True,
        ObservedPowerState.UNKNOWN,
        1,
        0,
        0,
        0,
        1,
        len(blobs[0].payload),
        (blobs[0].payload_sha256,),
    )
    view, full = artifact.view(), artifact.to_dict()
    request = full["activation_request"]
    working_directory = Path(full["owned_payload"]["working_directory"])
    if (
        view["status"] != "COMPLETE_PROBE_REHEARSAL"
        or _json(document["probe"]) != _json(view)
        or _json(asdict(receipt)) != _json(asdict(expected_receipt))
        or request["helper_sha256"] != worker_sha
        or working_directory.name != "camera-probe-" + attempt
        or (
            directory is not None
            and working_directory != directory / ("camera-probe-" + attempt)
        )
        or _json(request["budget"])
        != _json(
            {
                "duration_ms": 5000,
                "max_frames": 1,
                "max_frame_bytes": FRAME_BYTES,
                "max_total_bytes": FRAME_BYTES,
            }
        )
    ):
        _fail(
            "CAMERA_PROBE_RESULT_MISMATCH",
            "Retained probe cannot support the exact known auxiliary receipt.",
        )
    return artifact


def _verify_camera_configuration_context(
    evidence: dict[str, VerifiedRehearsalEvidence],
    records: dict[str, dict[str, Any]],
    source: str,
    session_id: str,
    *,
    directory: Path | None = None,
) -> tuple[Any, Any, Any, Any]:
    """Verify unique auxiliary probe/configuration receipts without replay.

    Inputs come from the caller's current verified M1 evidence inventory and
    record audit. A complete probe may exist without a staged configuration;
    neither is a replacement for a camera stage's capture receipt/assessment.
    """
    from rocell.application.camera_configuration import verify_camera_configuration
    from rocell.application.wizard_camera_configuration import (
        effective_camera_settings_epoch,
    )

    probes = [
        item
        for item in evidence.values()
        if item.document()["schema"] == _PROBE_RECEIPT_SCHEMA
    ]
    configs = [
        item
        for item in evidence.values()
        if item.document()["schema"] == _CONFIGURATION_RECEIPT_SCHEMA
    ]
    reserved = [
        r
        for r in records.values()
        if r["kind"] == "EXACT_REQUEST_RESERVED"
        and r["data"]["permit"]["request"]["session_id"] == session_id
        and r["data"]["permit"]["registration"]["action_id"]
        == "rehearsal-owned-camera-probe"
    ]
    if not probes and not configs and not reserved:
        return None, None, None, None
    if len(probes) != 1 or len(configs) > 1 or len(reserved) != 1:
        _fail(
            "CAMERA_CONFIGURATION_AUX_MISSING",
            "The exact probe auxiliary receipt is missing, duplicated or orphaned; never replay it.",
        )
    probe_item = probes[0]
    probe_doc = probe_item.document()
    probe = _verify_camera_probe_receipt(
        probe_doc, source, records, directory=directory
    )
    openings = [
        item
        for item in evidence.values()
        if item.reference.stage is STAGE_ORDER[4]
        and item.document()["schema"] == "rocell.rehearsal_camera_stage_open.v1"
    ]
    if (
        len(openings) != 1
        or probe_doc["session_id"] != session_id
        or probe_item.reference.stage is not STAGE_ORDER[4]
        or probe_item.captured_at_ns <= openings[0].captured_at_ns
        or probe_doc["operator_id"] != openings[0].document()["operator_id"]
        or probe_doc["cell_id"] != openings[0].document()["cell_id"]
        or probe_doc["catalog_sha256"] != openings[0].document()["catalog_sha256"]
    ):
        _fail(
            "CAMERA_PROBE_OPENING_MISMATCH",
            "Probe does not follow the exact retained stage-five opening/operator.",
        )
    if not configs:
        return probe_doc, probe, None, None
    item, doc = configs[0], configs[0].document()
    _exact(
        doc,
        _COMMON
        | {
            "probe_evidence_sha256",
            "configuration",
            "electronic_settings_epoch",
            "synthetic_settings_epoch",
            "effective_settings_epoch",
        },
    )
    settings = [
        e
        for e in evidence.values()
        if e.document()["schema"] == "rocell.rehearsal_camera_settings.v1"
    ]
    if len(settings) != 1:
        _fail(
            "CAMERA_CONFIGURATION_SETTINGS_MISSING",
            "Configuration requires the one exact synthetic settings receipt.",
        )
    settings_doc = settings[0].document()
    _settings(settings_doc["settings"])
    configuration = verify_camera_configuration(
        _json(doc["configuration"]), expected_capabilities=probe.capabilities()
    )
    if (
        doc["schema"] != _CONFIGURATION_RECEIPT_SCHEMA
        or any(doc[key] != probe_doc[key] for key in _COMMON - {"schema"})
        or item.reference.stage is not STAGE_ORDER[4]
        or item.captured_at_ns
        <= max(probe_item.captured_at_ns, settings[0].captured_at_ns)
        or doc["probe_evidence_sha256"] != probe.evidence_sha256
        or doc["electronic_settings_epoch"] != configuration.settings_epoch
        or doc["synthetic_settings_epoch"] != settings_doc["settings_epoch"]
        or any(settings_doc[key] != probe_doc[key] for key in _COMMON - {"schema"})
        or settings[0].captured_at_ns <= openings[0].captured_at_ns
        or settings_doc["settings_epoch"] != _hash(settings_doc["settings"])
        or doc["effective_settings_epoch"]
        != effective_camera_settings_epoch(
            settings_doc["settings_epoch"], configuration
        )
    ):
        _fail(
            "CAMERA_CONFIGURATION_BINDING_MISMATCH",
            "Staged configuration differs from its exact source/session/probe/brightness binding.",
        )
    from rocell.application.camera_rehearsal_campaign import MODE

    if not configuration.mode.same_format(MODE):
        _fail(
            "CAMERA_CONFIGURATION_MODE_MISMATCH",
            "The closed placemat process supports only its exact modeled full-resolution format.",
        )
    for camera in evidence.values():
        camera_doc = camera.document()
        if camera_doc["schema"].startswith("rocell.rehearsal_camera_campaign.") and (
            camera.captured_at_ns <= item.captured_at_ns
            or camera_doc["plan"].get("process_backend")
            != "OWNED_INCAPABLE_CAMERA_PROCESS"
            or _json(camera_doc["plan"].get("electronic_configuration"))
            != _json(configuration.to_dict())
            or camera_doc["plan"].get("probe_evidence_sha256") != probe.evidence_sha256
        ):
            _fail(
                "CAMERA_CONFIGURATION_DOWNGRADE",
                "A probed session cannot retain an earlier, unconfigured or fallback capture.",
            )
    return probe_doc, probe, doc, configuration


def _verify_owned_camera_campaign(
    document: dict[str, Any],
    source: str,
    records: dict[str, dict[str, Any]],
    *,
    evidence: dict[str, VerifiedRehearsalEvidence] | None = None,
) -> Any:
    """Join only already-audited M1 records, never recreate an executable worker.

    Call under the current original-store CELL/SESSION leases after
    ``tx._audit_records()``. That audit verifies the attempt ledger and immutable
    record publication. This independent join requires the owned-camera blob
    even though legacy camera campaigns did not retain one. The only source
    read here is the bounded fixed incapable child script, for its current pin.
    Dataset content verification remains the caller's next explicit read step.
    """
    from dataclasses import asdict
    from rocell.application.cell_commissioning_coordinator import (
        CampaignBudget,
        CampaignRegistration,
        CommissioningMode,
        MAX_RETAINED_CAMPAIGN_BYTES,
        ObservedPowerState,
        WorkerReceipt,
    )
    from rocell.application.commissioning_m1_persistence import (
        M1RehearsalTransaction,
        _decode_permit,
    )
    from rocell.application.owned_camera_rehearsal_campaign import ACTION_ID, WORKER_ID
    from rocell.application.physical_onboarding_leases import LeaseLevel
    from rocell.application.rehearsal_owned_camera_evidence import (
        SCHEMA as EVIDENCE_SCHEMA,
        verify_owned_camera_evidence,
    )
    from rocell.providers.windows.owned_camera_runner import CAMERA_FIXTURE_PATH
    from rocell.safety.effects import EffectCertainty, EffectClass

    plan = document["plan"]
    configured = "electronic_configuration" in plan
    probe_reserved = any(
        record["kind"] == "EXACT_REQUEST_RESERVED"
        and record["data"]["permit"]["request"]["session_id"] == document["session_id"]
        and record["data"]["permit"]["registration"]["action_id"]
        == "rehearsal-owned-camera-probe"
        for record in records.values()
    )
    configuration = None
    configuration_doc = None
    if configured or probe_reserved:
        if evidence is None:
            _fail(
                "CAMERA_CONFIGURATION_CONTEXT_MISSING",
                "Configured capture requires the actual retained auxiliary evidence inventory.",
            )
        _, probe, configuration_doc, configuration = (
            _verify_camera_configuration_context(
                evidence, records, source, document["session_id"]
            )
        )
        if not configured or probe is None or configuration is None:
            _fail(
                "CAMERA_CONFIGURATION_DOWNGRADE",
                "A probed session cannot use an unstaged or fallback capture.",
            )
        if (
            _json(plan["electronic_configuration"]) != _json(configuration.to_dict())
            or plan.get("probe_evidence_sha256") != probe.evidence_sha256
            or plan.get("effective_settings_epoch")
            != configuration_doc["effective_settings_epoch"]
            or plan.get("settings_epoch")
            != configuration_doc["synthetic_settings_epoch"]
        ):
            _fail(
                "CAMERA_CONFIGURATION_BINDING_MISMATCH",
                "Capture plan does not use the exact staged electronic and synthetic settings.",
            )
    writes = 0 if configuration is None else len(configuration.controls)
    effective_epoch = plan.get("effective_settings_epoch", plan.get("settings_epoch"))
    _exact(
        document,
        {
            "schema",
            "composition",
            "session_id",
            "stage",
            "operator_id",
            "workspace_source_sha256",
            "plan",
            "attempt_result",
            "physical_observation",
            "capture_dataset",
            "retained_campaign_sha256",
            "camera_process",
        }
        | ({"camera_readback"} if configured else set()),
    )
    plan = document["plan"]
    _exact(
        plan,
        {
            "composition",
            "process_backend",
            "selected_camera",
            "mode",
            "frame_count",
            "fault",
            "settings",
            "settings_epoch",
            "native_frame_bytes_generated",
            "binary_artifact_budget_bytes",
            "artifact_qualification",
            "process_timeout_ms",
            "process_cleanup_timeout_ms",
            "native_duration_ms",
            "stdout_bytes",
            "stderr_bytes",
        }
        | (
            {
                "electronic_configuration",
                "probe_evidence_sha256",
                "effective_settings_epoch",
            }
            if configured
            else set()
        ),
    )
    count = plan["frame_count"]
    _settings(plan["settings"])
    if (
        document["schema"] != "rocell.rehearsal_camera_campaign.v2"
        or document["composition"] != INCAPABLE_COMPOSITION
        or document["physical_observation"] is not False
        or document["workspace_source_sha256"] != source
        or document["stage"] not in {item.value for item in _CAMERA}
        or type(document["operator_id"]) is not str
        or _ACTOR.fullmatch(document["operator_id"]) is None
        or plan["composition"] != INCAPABLE_COMPOSITION
        or plan["process_backend"] != "OWNED_INCAPABLE_CAMERA_PROCESS"
        or type(count) is not int
        or not 1 <= count <= 4
        or plan["fault"] != "none"
        or _json(plan["mode"]) != _json(_MODE)
        or plan["native_frame_bytes_generated"] is not True
        or plan["artifact_qualification"] != "DIAGNOSTIC_ONLY_NOT_M1_QUALIFIED"
        or plan["settings_epoch"] != _hash(plan["settings"])
        or _json(
            {
                key: plan[key]
                for key in (
                    "process_timeout_ms",
                    "process_cleanup_timeout_ms",
                    "native_duration_ms",
                    "stdout_bytes",
                    "stderr_bytes",
                )
            }
        )
        != _json(
            {
                "process_timeout_ms": 25000,
                "process_cleanup_timeout_ms": 2000,
                "native_duration_ms": 20000,
                "stdout_bytes": 32768,
                "stderr_bytes": 8192,
            }
        )
        or type(plan["binary_artifact_budget_bytes"]) is not int
        or plan["binary_artifact_budget_bytes"]
        != (2 * 39923712 + 4990464) * count + 128 * 1024 * 1024
        or plan["selected_camera"]
        != {
            "candidate_id": "synthetic-b0477",
            "provenance": "SYNTHETIC_NOT_ENUMERATED",
            "model": "B0477",
            "unit_id": "SYNTHETIC-UNIT-A",
            "endpoint": "incapable-fixture-only",
        }
    ):
        _fail(
            "OWNED_CAMERA_PLAN_MISMATCH",
            "Owned camera plan is not the exact closed source-bound rehearsal.",
        )
    result = document["attempt_result"]
    if type(result) is not dict or result.get("state") != "SEALED_KNOWN":
        _fail(
            "OWNED_CAMERA_ATTEMPT_NOT_KNOWN",
            "Owned camera review requires the exact known retained attempt.",
        )
    attempt_id = result["attempt_id"]
    matching = [
        record
        for record in records.values()
        if record["kind"] == "CAMPAIGN_RESULT"
        and record["data"].get("attempt_id") == attempt_id
    ]
    reserved = [
        record
        for record in records.values()
        if record["kind"] == "EXACT_REQUEST_RESERVED"
        and record["data"].get("attempt_id") == attempt_id
    ]
    retained = [
        record
        for record in records.values()
        if record["kind"] == "CAMPAIGN_EVIDENCE"
        and record["data"].get("attempt_id") == attempt_id
    ]
    lifecycle = [
        record
        for record in records.values()
        if record["kind"] == "CAMPAIGN_RECEIPT"
        and record["data"].get("attempt_id") == attempt_id
    ]
    if (
        len(matching) != 1
        or len(reserved) != 1
        or len(retained) != 1
        or len(lifecycle) != 2
        or {item["data"].get("state") for item in lifecycle}
        != {"EFFECT_OBSERVED", "CLEANUP_CONFIRMED"}
        or _json(matching[0]["data"].get("result")) != _json(result)
        or any(
            _json(item["data"].get("receipt")) != _json(result.get("receipt"))
            for item in lifecycle
        )
    ):
        _fail(
            "OWNED_CAMERA_RECORD_MISMATCH",
            "One exact reservation/result/blob and both matching lifecycle receipts are required.",
        )
    permit = _decode_permit(reserved[0]["data"]["permit"])
    worker_sha = hashlib.sha256(
        read_bounded_regular_file(CAMERA_FIXTURE_PATH, maximum_bytes=1024 * 1024)
    ).hexdigest()
    registration = CampaignRegistration(
        ACTION_ID,
        PhysicalOnboardingStage(document["stage"]),
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        WORKER_ID,
        worker_sha,
        _hash(plan),
        (LeaseLevel.CAMERA,),
        CampaignBudget(60000, MAX_RETAINED_CAMPAIGN_BYTES, 1, count, writes, count, 1),
    )
    if (
        permit.registration != registration
        or permit.attempt_id != attempt_id
        or permit.request.session_id != document["session_id"]
        or permit.admission.mode is not CommissioningMode.REHEARSAL
        or permit.admission.source_binding_sha256 != rehearsal_source_binding(source)
        or permit.admission.selected_identity_sha256 != _hash(plan["selected_camera"])
        or permit.admission.stage_state is not V2StageState.WAITING_OPERATOR
        or permit.admission.quarantine_latched
        or permit.admission.unresolved_attempts
        or permit.admission.open_blocker_ids
        or permit.envelope is not None
        or result.get("permit_sha256") != permit.permit_sha256
        or result.get("composition") != INCAPABLE_COMPOSITION
        or result.get("physical_authority") != "NONE"
        or result.get("reason_codes") != []
        or result.get("quarantine_latched") is not False
        or any(
            record["data"].get("permit_sha256") != permit.permit_sha256
            for record in [*matching, *reserved, *retained, *lifecycle]
        )
    ):
        _fail(
            "OWNED_CAMERA_PERMIT_MISMATCH",
            "Owned camera records differ from the exact rehearsal source/identity/registration permit.",
        )
    blobs = M1RehearsalTransaction._decode_campaign_evidence(permit, retained[0])
    if (
        len(blobs) != 1
        or blobs[0].schema != EVIDENCE_SCHEMA
        or blobs[0].label != "owned-camera-campaign"
        or blobs[0].payload_sha256 != document["retained_campaign_sha256"]
    ):
        _fail(
            "OWNED_CAMERA_EVIDENCE_MISMATCH",
            "The stage does not select its single exact retained owned-camera blob.",
        )
    decoded = M1RehearsalTransaction._decode_receipt(result["receipt"])
    M1RehearsalTransaction._match_campaign_evidence(decoded, blobs)
    verified = verify_owned_camera_evidence(
        blobs[0].payload,
        {
            "session_id": document["session_id"],
            "attempt_id": attempt_id,
            "source_sha256": source,
            "permit_sha256": permit.permit_sha256,
            "operation_sha256": registration.operation_sha256,
            "selected_identity_sha256": permit.admission.selected_identity_sha256,
            "settings_epoch": effective_epoch,
        },
    )
    view, full = verified.view(), verified.to_dict()
    expected_receipt = WorkerReceipt(
        attempt_id,
        permit.permit_sha256,
        worker_sha,
        permit.admission.selected_identity_sha256,
        EffectCertainty.CONFIRMED,
        True,
        ObservedPowerState.UNKNOWN,
        1,
        count,
        writes,
        count,
        1,
        len(blobs[0].payload),
        (blobs[0].payload_sha256,),
    )
    if (
        view["status"] != "RETAINED_COMPLETE_REHEARSAL"
        or _json(view) != _json(document["camera_process"])
        or _json(full["capture"]) != _json(document["capture_dataset"])
        or _json(asdict(decoded)) != _json(asdict(expected_receipt))
        or full["activation_request"]["helper_sha256"] != worker_sha
        or full["activation_request"]["budget"]["duration_ms"]
        != plan["native_duration_ms"]
        or full["activation_request"]["budget"]["max_frames"] != count
        or full["activation_request"]["binding"]["symbolic_link"]
        != plan["selected_camera"]["endpoint"]
    ):
        _fail(
            "OWNED_CAMERA_RESULT_MISMATCH",
            "The exact retained process/native/capture evidence does not prove this complete rehearsal receipt.",
        )
    if configuration is not None:
        from rocell.application.camera_configuration import compare_camera_readback
        from rocell.application.rehearsal_owned_camera_evidence import _native, _request

        request = _request(full["activation_request"], full["binding"])
        native = _native(full["native_receipt"], request)
        readback = compare_camera_readback(
            configuration, native, expected_settings_epoch=configuration.settings_epoch
        )
        if (
            _json(full["activation_request"]["controls"])
            != _json([asdict(item) for item in configuration.controls])
            or readback["status"] != "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
            or _json(document["camera_readback"]) != _json(readback)
        ):
            _fail(
                "CAMERA_READBACK_MISMATCH",
                "Retained capture does not prove the exact configured control request and readback.",
            )
    return verified


def _verify_camera_receipt(
    directory: Path,
    receipt: VerifiedRehearsalEvidence,
    source: str,
    settings: VerifiedRehearsalEvidence | None,
    *,
    records: dict[str, dict[str, Any]] | None = None,
    evidence: dict[str, VerifiedRehearsalEvidence] | None = None,
) -> Path:
    """Recheck the retained bridge and bytes, never implicitly publish preview."""
    from rocell.application.windows_camera_capture_ingest import (
        verify_windows_capture_ingest,
    )
    from rocell.application.camera_capture_dataset import verify_capture_dataset

    document = receipt.document()
    if document["schema"] != "rocell.rehearsal_camera_campaign.v2" or settings is None:
        _fail(
            "CAMERA_REVIEW_NOT_RECONSTRUCTABLE",
            "Camera review requires the versioned binary receipt and retained settings.",
        )
    plan = document["plan"]
    owned = plan.get("process_backend") == "OWNED_INCAPABLE_CAMERA_PROCESS"
    configured = "electronic_configuration" in plan
    if records is not None:
        owned_attempt = any(
            record["kind"] == "EXACT_REQUEST_RESERVED"
            and record["data"].get("attempt_id")
            == document["attempt_result"]["attempt_id"]
            and record["data"]
            .get("permit", {})
            .get("registration", {})
            .get("action_id")
            == "rehearsal-owned-camera-campaign"
            for record in records.values()
        )
        if owned_attempt != owned:
            _fail(
                "OWNED_CAMERA_BACKEND_MISMATCH",
                "Retained plan backend differs from its audited campaign registration.",
            )
        if not owned and any(
            record["kind"] == "EXACT_REQUEST_RESERVED"
            and record["data"]["permit"]["request"]["session_id"]
            == document["session_id"]
            and record["data"]["permit"]["registration"]["action_id"]
            == "rehearsal-owned-camera-probe"
            for record in records.values()
        ):
            _fail(
                "CAMERA_CONFIGURATION_DOWNGRADE",
                "A probed session cannot fall back to an in-process capture.",
            )
    if owned:
        if records is None:
            _fail(
                "OWNED_CAMERA_RECORDS_MISSING",
                "Owned camera reconstruction requires audited M1 records; no replay.",
            )
        _verify_owned_camera_campaign(document, source, records, evidence=evidence)
    _exact(
        plan,
        {
            "composition",
            "selected_camera",
            "mode",
            "frame_count",
            "fault",
            "settings",
            "settings_epoch",
            "native_frame_bytes_generated",
            "binary_artifact_budget_bytes",
            "artifact_qualification",
        }
        | (
            {
                "process_backend",
                "process_timeout_ms",
                "process_cleanup_timeout_ms",
                "native_duration_ms",
                "stdout_bytes",
                "stderr_bytes",
            }
            if owned
            else set()
        )
        | (
            {
                "electronic_configuration",
                "probe_evidence_sha256",
                "effective_settings_epoch",
            }
            if configured
            else set()
        ),
    )
    count = plan["frame_count"]
    settings_document = settings.document()
    if (
        type(count) is not int
        or not 1 <= count <= 4
        or plan["fault"] != "none"
        or plan["composition"] != INCAPABLE_COMPOSITION
        or plan["mode"] != _MODE
        or plan["native_frame_bytes_generated"] is not True
        or plan["artifact_qualification"] != "DIAGNOSTIC_ONLY_NOT_M1_QUALIFIED"
        or type(plan["binary_artifact_budget_bytes"]) is not int
        or plan["binary_artifact_budget_bytes"]
        != (2 * 39_923_712 + (4_990_464 if owned else 0)) * count + 128 * 1024 * 1024
        or plan["settings"] != settings_document["settings"]
        or plan["settings_epoch"] != settings_document["settings_epoch"]
        or settings.captured_at_ns >= receipt.captured_at_ns
    ):
        _fail(
            "CAMERA_SETTINGS_OR_PLAN_DRIFT",
            "Retained camera plan does not bind its exact pre-campaign settings/budget.",
        )
    bridge = document["capture_dataset"]
    if type(bridge) is not dict:
        _fail(
            "CAMERA_DATASET_MISSING",
            "No retained binary dataset accompanies this camera receipt.",
        )
    path = Path(bridge["dataset"]["path"])
    try:
        relative = path.relative_to(directory)
    except ValueError:
        _fail(
            "CAMERA_DATASET_OUTSIDE_STORE",
            "Dataset path is outside its original assigned store.",
        )
    parts = relative.parts
    if (
        len(parts) != 4
        or not re.fullmatch(r"binary-fixture-[0-9a-f]{32}", parts[0])
        or parts[1] != "datasets"
        or not re.fullmatch(r"ingest-[0-9a-f]{32}", parts[2])
        or not re.fullmatch(r"capture-[0-9a-f]{32}", parts[3])
        or Path(bridge["envelope_path"]) != path.parent / "ingest-receipt.json"
    ):
        _fail(
            "CAMERA_DATASET_OUTSIDE_STORE",
            "Dataset/envelope path is not the exact retained fixture layout.",
        )
    bounded = verify_capture_dataset(
        path,
        tier="metadata",
        expected_manifest_sha256=bridge["dataset"]["manifest_sha256"],
    )
    if (
        bounded.frames != count
        or bounded.plan.layout.sample_bytes(bounded.plan.binding.observed_mode)
        != 39_923_712
        or bounded.logical_bytes > count * (39_923_712 + 4 * 1024 * 1024)
    ):
        _fail(
            "CAMERA_DATASET_RESOURCE_LIMIT",
            "Retained dataset exceeds the registered campaign's frame/byte budget.",
        )
    verified = verify_windows_capture_ingest(
        bridge,
        expected_source_sha256=source,
        expected_settings_epoch=plan.get(
            "effective_settings_epoch", plan["settings_epoch"]
        ),
        expected_campaign_id=document["attempt_result"]["attempt_id"],
        expected_endpoint_sha256=hashlib.sha256(b"incapable-fixture-only").hexdigest(),
    )
    if (
        verified.frames != count
        or not verified.content_verified
        or verified.physical_authority
    ):
        _fail(
            "CAMERA_DATASET_BINDING_MISMATCH",
            "Verified diagnostic dataset differs from its exact campaign.",
        )
    return directory / parts[0]


def _reviewed_stage_evidence(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    stage: PhysicalOnboardingStage,
) -> tuple[
    VerifiedRehearsalEvidence, VerifiedRehearsalEvidence, VerifiedRehearsalEvidence
]:
    """Select the unique committed PASS and its exact receipt/assessment/review.

    These are trusted references from a verified M1 snapshot, never browser
    hashes. Callers additionally verify their stage-specific technical results.
    A hash named predecessor_assessment_sha256 covers the full canonical
    assessment payload, not just its embedded assessment self-hash field.
    """
    matches = [
        event
        for event in snapshot.committed_events
        if event.stage is stage and event.state is V2StageState.PASS
    ]
    if len(matches) != 1 or len(matches[0].evidence) != 3:
        _fail(
            "REHEARSAL_PREREQUISITE_MISSING",
            "Exactly one reviewed predecessor PASS is required.",
        )
    event = matches[0]
    receipt, assessment, review = [evidence[ref.evidence_id] for ref in event.evidence]
    r, a, v = receipt.document(), assessment.document(), review.document()
    if (
        event.detail_code != "REHEARSAL_ASSESSMENT_REVIEWED"
        or any(
            item.reference.stage is not stage for item in (receipt, assessment, review)
        )
        or a.get("schema") != "rocell.rehearsal_assessment.v1"
        or v.get("schema") != "rocell.rehearsal_review.v1"
        or a["outcome"] != "PASS"
        or a["receipt_evidence_id"] != receipt.reference.evidence_id
        or a["receipt_sha256"] != _hash(r)
        or v["assessment_sha256"] != a["assessment_sha256"]
        or v["operator_id"] != r["operator_id"]
        or v["reviewer_id"] == r["operator_id"]
        or v["decision"] != "ACCEPT_EXACT_ASSESSMENT"
    ):
        _fail(
            "REHEARSAL_PREREQUISITE_MISMATCH",
            "Reviewed predecessor does not bind exact retained evidence.",
        )
    return receipt, assessment, review


def _optics_binding(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    stage: PhysicalOnboardingStage,
    operator: str,
    source: str,
    catalog: str,
) -> tuple[Any, VerifiedRehearsalEvidence]:
    """Derive dependencies from committed PASS events, never caller hashes.

    Reads only the already verified snapshot/retained documents. Stage 8 also
    re-verifies its stage-7 predecessor; no detector or assessment is rerun.
    """
    from rocell.application.rehearsal_optics_stages import RehearsalOpticsBinding

    if stage not in _OPTICS:
        _fail(
            "OPTICS_STAGE_MISMATCH",
            "Only stages seven and eight have optics dependencies.",
        )
    predecessor_stage = STAGE_ORDER[STAGE_ORDER.index(stage) - 1]
    predecessor, _, review = _reviewed_stage_evidence(
        snapshot, evidence, predecessor_stage
    )
    identity, _, _ = _reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[3])
    camera, _, _ = _reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[5])
    settings = [
        item
        for item in evidence.values()
        if item.document()["schema"] == "rocell.rehearsal_camera_settings.v1"
    ]
    if len(settings) != 1:
        _fail(
            "OPTICS_SETTINGS_MISSING",
            "Exactly one retained camera settings document is required.",
        )
    settings_doc, camera_doc = settings[0].document(), camera.document()
    selected = identity.document()["candidate"]
    if (
        camera_doc["schema"] != "rocell.rehearsal_camera_campaign.v2"
        or camera_doc["plan"]["selected_camera"] != selected
        or camera_doc["plan"]["settings"] != settings_doc["settings"]
        or camera_doc["plan"]["settings_epoch"] != settings_doc["settings_epoch"]
        or not camera_doc.get("capture_dataset")
    ):
        _fail(
            "OPTICS_CAMERA_DEPENDENCY_MISMATCH",
            "Stage-six camera/settings/dataset dependencies differ.",
        )
    if predecessor_stage in _OPTICS:
        prior = _verify_optics_receipt(snapshot, evidence, predecessor, source, catalog)
        if prior.outcome != "REHEARSAL_CHECKS_PASSED":
            _fail(
                "OPTICS_PREDECESSOR_BLOCKED",
                "Stage-eight cannot use a failed stage-seven report.",
            )
    return (
        RehearsalOpticsBinding(
            source,
            catalog,
            snapshot.header.cell_id,
            snapshot.header.session_id,
            operator,
            stage.value,
            _hash(predecessor.document()),
            _hash(review.document()),
            _hash(selected),
            settings_doc["settings_epoch"],
            camera_doc["capture_dataset"]["dataset"]["manifest_sha256"],
        ),
        camera,
    )


def _verify_optics_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
) -> Any:
    from rocell.application import rehearsal_optics_stages as optics

    document = receipt.document()
    expected, _ = _optics_binding(
        snapshot,
        evidence,
        receipt.reference.stage,
        document["operator_id"],
        source,
        catalog,
    )
    # Outer M1 JSON uses ASCII escapes. Restore the evaluator's independently
    # specified canonical UTF-8 representation before checking its whole digest.
    payload = json.dumps(
        document["evaluation"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    trusted_source = hashlib.sha256(Path(optics.__file__).read_bytes()).hexdigest()
    return optics.verify_rehearsal_optics_evidence(
        payload,
        expected_binding=expected,
        expected_evidence_sha256=document["evaluation_sha256"],
        expected_evaluator_source_sha256=trusted_source,
    )


def _arm_identity_binding(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    operator: str,
    source: str,
    catalog: str,
) -> tuple[Any, VerifiedRehearsalEvidence]:
    from rocell.application.rehearsal_arm_identity_stage import (
        RehearsalArmIdentityBinding,
    )

    prior, assessment, review = _reviewed_stage_evidence(
        snapshot, evidence, STAGE_ORDER[7]
    )
    registration = _verify_optics_receipt(snapshot, evidence, prior, source, catalog)
    if registration.outcome != "REHEARSAL_CHECKS_PASSED":
        _fail(
            "ARM_IDENTITY_PREDECESSOR_BLOCKED",
            "Arm identity requires the exact reviewed registration report.",
        )
    camera, _, _ = _reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[5])
    return (
        RehearsalArmIdentityBinding(
            workspace_source_sha256=source,
            catalog_sha256=catalog,
            cell_id=snapshot.header.cell_id,
            session_id=snapshot.header.session_id,
            operator_id=operator,
            predecessor_receipt_sha256=_hash(prior.document()),
            predecessor_assessment_sha256=_hash(assessment.document()),
            predecessor_review_sha256=_hash(review.document()),
            static_registration_evidence_sha256=registration.evidence_sha256,
            stage=_ARM_IDENTITY.value,
        ),
        camera,
    )


def _power_binding(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    stage: PhysicalOnboardingStage,
    operator: str,
    source: str,
    catalog: str,
) -> tuple[Any, VerifiedRehearsalEvidence]:
    from rocell.application.rehearsal_power_stages import RehearsalPowerBinding

    if stage not in _POWER:
        _fail(
            "POWER_STAGE_MISMATCH",
            "Only stages ten and eleven have power rehearsal dependencies.",
        )
    predecessor_stage = STAGE_ORDER[STAGE_ORDER.index(stage) - 1]
    prior, assessment, review = _reviewed_stage_evidence(
        snapshot, evidence, predecessor_stage
    )
    arm, _, _ = _reviewed_stage_evidence(snapshot, evidence, _ARM_IDENTITY)
    arm_result = _verify_arm_identity_receipt(snapshot, evidence, arm, source, catalog)
    if arm_result.outcome != "REHEARSAL_CHECKS_PASSED":
        _fail(
            "POWER_ARM_IDENTITY_BLOCKED",
            "The exact arm-identity rehearsal checks did not pass.",
        )
    if predecessor_stage in _POWER:
        previous_power = _verify_power_receipt(
            snapshot, evidence, prior, source, catalog
        )
        if previous_power.outcome != "REHEARSAL_CHECKS_PASSED":
            _fail(
                "POWER_PREDECESSOR_BLOCKED",
                "Startup rehearsal requires the reviewed power-safety report.",
            )
    camera, _, _ = _reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[5])
    return (
        RehearsalPowerBinding(
            workspace_source_sha256=source,
            catalog_sha256=catalog,
            cell_id=snapshot.header.cell_id,
            session_id=snapshot.header.session_id,
            operator_id=operator,
            stage=stage.value,
            predecessor_receipt_sha256=_hash(prior.document()),
            predecessor_assessment_sha256=_hash(assessment.document()),
            predecessor_review_sha256=_hash(review.document()),
            arm_identity_evidence_sha256=arm_result.evidence_sha256,
        ),
        camera,
    )


def _evaluation_payload(document: dict[str, Any]) -> bytes:
    """Recover the evaluator's UTF-8 representation from M1's ASCII container."""
    return json.dumps(
        document["evaluation"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _feedback_binding(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    operator: str,
    source: str,
    catalog: str,
) -> tuple[Any, VerifiedRehearsalEvidence]:
    """Require each exact reviewed identity/power report before serial planning.

    This function reads only already-audited retained metadata and uses the pure
    predecessor verifiers. It neither opens a controller nor replays an evaluator.
    The stage-six camera dataset is returned for the caller's existing integrity
    check, preserving the upstream optics/board dependency chain.
    """
    from rocell.application.rehearsal_feedback_binding import (
        RehearsalFeedbackBinding,
        ReviewedFeedbackPredecessor,
        controller_from_verified_arm_identity,
    )

    predecessors = []
    controller = None
    for stage in STAGE_ORDER[8:11]:
        receipt, assessment, review = _reviewed_stage_evidence(
            snapshot, evidence, stage
        )
        evaluated = _verify_evaluated_receipt(
            snapshot, evidence, receipt, source, catalog
        )
        if evaluated.outcome != "REHEARSAL_CHECKS_PASSED":
            _fail(
                "FEEDBACK_PREDECESSOR_BLOCKED",
                "Exact identity and both power reports must pass before the incapable serial campaign.",
            )
        predecessors.append(
            ReviewedFeedbackPredecessor(
                stage.value,
                _hash(receipt.document()),
                _hash(assessment.document()),
                _hash(review.document()),
                evaluated.evidence_sha256,
            )
        )
        if stage is _ARM_IDENTITY:
            controller = controller_from_verified_arm_identity(
                evaluated.to_dict(),
                identity_receipt_sha256=predecessors[-1].receipt_sha256,
            )
    camera, _, _ = _reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[5])
    if controller is None:
        _fail(
            "FEEDBACK_IDENTITY_MISSING", "No reviewed incapable controller was derived."
        )
    return (
        RehearsalFeedbackBinding(
            source,
            catalog,
            snapshot.header.cell_id,
            snapshot.header.session_id,
            operator,
            tuple(predecessors),
            controller,
        ),
        camera,
    )


def _verify_arm_identity_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
) -> Any:
    from rocell.application import rehearsal_arm_identity_stage as identity

    if receipt.reference.stage is not _ARM_IDENTITY:
        _fail(
            "ARM_IDENTITY_STAGE_MISMATCH",
            "Arm identity evidence belongs to another stage.",
        )
    document = receipt.document()
    expected, _ = _arm_identity_binding(
        snapshot, evidence, document["operator_id"], source, catalog
    )
    return identity.verify_rehearsal_arm_identity_evidence(
        _evaluation_payload(document),
        expected_binding=expected,
        expected_evidence_sha256=document["evaluation_sha256"],
        expected_evaluator_source_sha256=hashlib.sha256(
            Path(identity.__file__).read_bytes()
        ).hexdigest(),
    )


def _verify_power_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
) -> Any:
    from rocell.application import rehearsal_power_stages as power

    document = receipt.document()
    expected, _ = _power_binding(
        snapshot,
        evidence,
        receipt.reference.stage,
        document["operator_id"],
        source,
        catalog,
    )
    return power.verify_rehearsal_power_evidence(
        _evaluation_payload(document),
        expected_binding=expected,
        expected_evidence_sha256=document["evaluation_sha256"],
        expected_evaluator_source_sha256=hashlib.sha256(
            Path(power.__file__).read_bytes()
        ).hexdigest(),
    )


def _verify_feedback_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
    records: dict[str, dict[str, Any]],
    *,
    directory: Path | None = None,
) -> Any:
    """Bind stage assessment to the audited consumed permit and complete bytes.

    The caller supplies records only after the M1 ledger/record audit under its
    original leases. Parsing a retained permit here never makes it redeemable.
    No serial/observer worker, evaluator or hardware discovery is replayed.
    """
    from rocell.application import arm_feedback_rehearsal_campaign as campaign
    from rocell.application.commissioning_m1_persistence import (
        M1RehearsalTransaction,
        _decode_permit,
    )
    from rocell.application.rehearsal_feedback_stage import (
        feedback_plan,
        feedback_power_dependencies,
        feedback_evaluation,
    )

    document = receipt.document()
    owned = document.get("schema") == _OWNED_FEEDBACK_SCHEMA
    if owned and (
        directory is None
        or document.get("campaign_directory") != str(directory / "owned-arm-feedback")
    ):
        _fail(
            "FEEDBACK_ASSIGNED_DIRECTORY_MISMATCH",
            "The contained feedback campaign must retain the exact server-assigned original store directory.",
        )
    binding, _ = _feedback_binding(
        snapshot, evidence, document["operator_id"], source, catalog
    )
    result = document["attempt_result"]
    if type(result) is not dict or result.get("state") != "SEALED_KNOWN":
        _fail(
            "FEEDBACK_ATTEMPT_NOT_KNOWN",
            "Feedback assessment requires an audited known campaign, not a status flag.",
        )
    attempt_id = result["attempt_id"]
    matches = [
        record
        for record in records.values()
        if record["kind"] == "CAMPAIGN_RESULT"
        and record["data"].get("result") == result
    ]
    reserved = [
        record
        for record in records.values()
        if record["kind"] == "EXACT_REQUEST_RESERVED"
        and record["data"].get("attempt_id") == attempt_id
    ]
    retained = [
        record
        for record in records.values()
        if record["kind"] == "CAMPAIGN_EVIDENCE"
        and record["data"].get("attempt_id") == attempt_id
    ]
    if len(matches) != 1 or len(reserved) != 1 or len(retained) != 1:
        _fail(
            "FEEDBACK_CAMPAIGN_RECORD_MISMATCH",
            "One exact audited result, reservation and complete retained evidence record are required.",
        )
    permit = _decode_permit(reserved[0]["data"]["permit"])
    blobs = M1RehearsalTransaction._decode_campaign_evidence(permit, retained[0])
    if (
        len(blobs) != 1
        or blobs[0].payload_sha256 != document["retained_campaign_sha256"]
    ):
        _fail(
            "FEEDBACK_RETAINED_BYTES_MISMATCH",
            "Stage receipt does not select the single exact retained campaign blob.",
        )
    if owned:
        # Choose only from the original retained IPC version, then independently
        # verify the entire operation/request/permit below. Never reinterpret an
        # old generic fixture as having undergone the new native-metadata checks.
        from rocell.application.rehearsal_feedback_binding import (
            owned_metadata_feedback_binding,
        )
        from rocell.providers.windows.arm_owned_protocol import REQUEST_SCHEMA

        owned_document = campaign._decode(blobs[0].payload)
        operation = owned_document.get("operation")
        if (
            type(operation) is dict
            and operation.get("ipc_request_schema") == REQUEST_SCHEMA
        ):
            binding = owned_metadata_feedback_binding(binding)
    plan = feedback_plan(binding)
    expected_registration = None
    if not owned:
        worker_sha = hashlib.sha256(Path(campaign.__file__).read_bytes()).hexdigest()
        expected_registration = campaign.ArmFeedbackRehearsalCampaign(
            plan, worker_executable_sha256=worker_sha
        ).registration()
    if (
        (not owned and permit.registration != expected_registration)
        or permit.admission.cell_id != snapshot.header.cell_id
        or permit.admission.session_id != snapshot.header.session_id
        or permit.admission.selected_identity_sha256
        != binding.controller.identity.identity_sha256
        or permit.admission.source_binding_sha256 != rehearsal_source_binding(source)
        or permit.envelope is None
        or permit.envelope.operator_id != binding.operator_id
        or permit.envelope.observer_id != plan.final_power_observation.observer_id
        or any(
            getattr(permit.envelope, field) != digest
            for field, digest in feedback_power_dependencies(binding).items()
        )
    ):
        _fail(
            "FEEDBACK_ADMISSION_BINDING_MISMATCH",
            "Retained feedback admission differs from its exact reviewed source/controller/power inputs.",
        )
    M1RehearsalTransaction._match_campaign_evidence(
        M1RehearsalTransaction._decode_receipt(result["receipt"]), blobs
    )
    if owned:
        from rocell.application.owned_arm_feedback_rehearsal_campaign import (
            verify_retained_owned_arm_feedback_campaign,
        )

        assert directory is not None
        # Verify the original permit and its exact retained runtime, never
        # manufacture a memory-only registration or rebuild/execute a package.
        verified: Any = verify_retained_owned_arm_feedback_campaign(
            blobs[0].payload,
            expected_plan=plan,
            expected_permit=permit,
            expected_evidence_sha256=blobs[0].payload_sha256,
            expected_directory=directory / "owned-arm-feedback",
        )
        if (
            verified.to_dict()["scenario"] != document["scenario"]
            or verified.process_summary() != document["arm_feedback_process"]
        ):
            _fail(
                "FEEDBACK_PROCESS_CHANGED",
                "The cached scenario/process report differs from exact retained evidence.",
            )
    else:
        verified = campaign.verify_retained_arm_feedback_campaign(
            blobs[0].payload,
            expected_plan=plan,
            expected_permit=permit,
            expected_evidence_sha256=blobs[0].payload_sha256,
        )
    evaluated = feedback_evaluation(binding, verified)
    if (
        evaluated.evidence_sha256 != document["evaluation_sha256"]
        or evaluated.to_dict() != document["evaluation"]
    ):
        _fail(
            "FEEDBACK_EVALUATION_CHANGED",
            "The stage report differs from the independently derived retained serial evidence.",
        )
    return evaluated


def _reference_binding(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    operator: str,
    source: str,
    catalog: str,
    records: dict[str, dict[str, Any]],
    source_context: dict[str, Any],
    *,
    directory: Path | None = None,
) -> tuple[Any, VerifiedRehearsalEvidence]:
    """Bind numeric fixtures to exact reviewed dependencies, not caller hashes.

    The audited stage-12 campaign includes separate synthetic final-power
    evidence. Its feedback values are never converted into FK joint inputs.
    The returned camera receipt still requires the caller's binary integrity
    check; it is a dependency and does not supply numerical correspondence data.
    """
    from rocell.application.rehearsal_reference_binding import (
        RehearsalReferenceBinding,
        ReviewedReferencePredecessor,
    )

    predecessors = []
    feedback_document = feedback_report = None
    for stage in (STAGE_ORDER[6], STAGE_ORDER[7], _FEEDBACK):
        receipt, assessment, review = _reviewed_stage_evidence(
            snapshot, evidence, stage
        )
        evaluated = _verify_evaluated_receipt(
            snapshot,
            evidence,
            receipt,
            source,
            catalog,
            records=records,
            directory=directory,
        )
        if evaluated.outcome != "REHEARSAL_CHECKS_PASSED":
            _fail(
                "REFERENCE_PREDECESSOR_BLOCKED",
                "Each exact reviewed reference dependency must pass.",
            )
        predecessors.append(
            ReviewedReferencePredecessor(
                stage.value,
                _hash(receipt.document()),
                _hash(assessment.document()),
                _hash(review.document()),
                evaluated.evidence_sha256,
            )
        )
        if stage is _FEEDBACK:
            feedback_document, feedback_report = receipt.document(), evaluated.to_dict()
    if feedback_document is None or feedback_report is None:
        _fail(
            "REFERENCE_FEEDBACK_MISSING",
            "The exact reviewed feedback campaign is required.",
        )
    observation = feedback_report["final_power_observation"]
    if (
        type(observation) is not dict
        or observation.get("observed_power_state") != "DEENERGIZED"
        or observation.get("physical_observation") is not False
    ):
        _fail(
            "REFERENCE_FINAL_POWER_MISSING",
            "Separate synthetic final-power evidence is required; serial close is insufficient.",
        )
    camera, _, _ = _reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[5])
    summary = feedback_report["safe_summary"]
    return (
        RehearsalReferenceBinding(
            workspace_source_sha256=source,
            catalog_sha256=catalog,
            cell_id=snapshot.header.cell_id,
            session_id=snapshot.header.session_id,
            operator_id=operator,
            predecessors=tuple(predecessors),
            camera_capture_receipt_sha256=_hash(camera.document()),
            feedback_binding_sha256=feedback_report["selected_inputs_sha256"],
            campaign_context_binding_sha256=summary["binding_sha256"],
            retained_campaign_sha256=feedback_document["retained_campaign_sha256"],
            feedback_inner_evidence_sha256=observation["feedback_evidence_sha256"],
            feedback_request_sha256=summary["request_sha256"],
            controller_binding_sha256=summary["controller_binding_sha256"],
            final_power_observation_sha256=observation["observation_sha256"],
            source_context_json=_json(source_context),
        ),
        camera,
    )


def _verify_reference_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
    records: dict[str, dict[str, Any]],
    workspace: Path,
    *,
    directory: Path | None = None,
) -> Any:
    from rocell.application import rehearsal_reference_stage as reference

    document = receipt.document()
    expected, _ = _reference_binding(
        snapshot,
        evidence,
        document["operator_id"],
        source,
        catalog,
        records,
        reference.read_reference_source_context(workspace),
        directory=directory,
    )
    return reference.verify_rehearsal_reference_evidence(
        _evaluation_payload(document),
        expected_binding=expected,
        expected_evidence_sha256=document["evaluation_sha256"],
        expected_evaluator_source_sha256=hashlib.sha256(
            Path(reference.__file__).read_bytes()
        ).hexdigest(),
    )


def _noncontact_binding(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    operator: str,
    source: str,
    catalog: str,
    records: dict[str, dict[str, Any]],
    source_context: bytes,
    *,
    reference_workspace: Path,
    directory: Path | None = None,
) -> tuple[Any, VerifiedRehearsalEvidence]:
    """Join the original reviewed reference result to NC-01, without replay.

    Stage thirteen's operator and all reviewed camera/feedback/power inputs are
    reconstructed independently. The new operator belongs only to stage
    fourteen. Full predecessor hashes cover original canonical documents, not
    their embedded self-hashes. Callers must still verify returned camera bytes:
    the service does that in its guarded context; reopen does it in the existing
    bounded camera loop. No numeric fit, simulator or renderer is rerun here.
    """
    from rocell.application import rehearsal_reference_stage as reference
    from rocell.application.rehearsal_noncontact_binding import (
        RehearsalNoncontactBinding,
    )

    receipt, assessment, review = _reviewed_stage_evidence(
        snapshot, evidence, _REFERENCE
    )
    document = receipt.document()
    if document.get("schema") != _EVALUATED_SCHEMAS[_REFERENCE]:
        _fail(
            "NONCONTACT_PREDECESSOR_MISMATCH",
            "Noncontact readiness requires the exact reviewed reference receipt.",
        )
    original, camera = _reference_binding(
        snapshot,
        evidence,
        document["operator_id"],
        source,
        catalog,
        records,
        reference.read_reference_source_context(reference_workspace),
        directory=directory,
    )
    evaluated = reference.verify_rehearsal_reference_evidence(
        _evaluation_payload(document),
        expected_binding=original,
        expected_evidence_sha256=document["evaluation_sha256"],
        expected_evaluator_source_sha256=hashlib.sha256(
            read_bounded_regular_file(
                Path(reference.__file__), maximum_bytes=1024 * 1024
            )
        ).hexdigest(),
    )
    if evaluated.outcome != "REHEARSAL_CHECKS_PASSED":
        _fail(
            "NONCONTACT_PREDECESSOR_BLOCKED",
            "The exact retained reference diagnostic must pass before NC-01.",
        )
    return (
        RehearsalNoncontactBinding(
            reference_binding=original,
            operator_id=operator,
            predecessor_receipt_sha256=_hash(document),
            predecessor_assessment_sha256=_hash(assessment.document()),
            predecessor_review_sha256=_hash(review.document()),
            reference_evidence_sha256=evaluated.evidence_sha256,
            source_context_json=source_context,
        ),
        camera,
    )


def _verify_noncontact_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
    records: dict[str, dict[str, Any]],
    workspace: Path,
    *,
    directory: Path | None = None,
) -> Any:
    """Verify retained readiness/gap algebra at an explicit source-read boundary."""
    from rocell.application import rehearsal_noncontact_stage as noncontact

    document = receipt.document()
    expected, _ = _noncontact_binding(
        snapshot,
        evidence,
        document["operator_id"],
        source,
        catalog,
        records,
        noncontact.read_noncontact_source_context(workspace),
        reference_workspace=workspace,
        directory=directory,
    )
    return noncontact.verify_rehearsal_noncontact_evidence(
        _evaluation_payload(document),
        expected_binding=expected,
        expected_evidence_sha256=document["evaluation_sha256"],
        expected_evaluator_source_sha256=hashlib.sha256(
            read_bounded_regular_file(
                Path(noncontact.__file__), maximum_bytes=1024 * 1024
            )
        ).hexdigest(),
    )


def _verify_evaluated_receipt(
    snapshot: V2SessionSnapshot,
    evidence: dict[str, VerifiedRehearsalEvidence],
    receipt: VerifiedRehearsalEvidence,
    source: str,
    catalog: str,
    *,
    records: dict[str, dict[str, Any]] | None = None,
    reference_workspace: Path | None = None,
    directory: Path | None = None,
) -> Any:
    stage = receipt.reference.stage
    if receipt.document().get("schema") not in _evaluated_schemas(stage):
        _fail(
            "RECEIPT_SCHEMA_MISMATCH",
            "An evaluator receipt cannot substitute for another stage.",
        )
    if stage in _OPTICS:
        return _verify_optics_receipt(snapshot, evidence, receipt, source, catalog)
    if stage is _ARM_IDENTITY:
        return _verify_arm_identity_receipt(
            snapshot, evidence, receipt, source, catalog
        )
    if stage in _POWER:
        return _verify_power_receipt(snapshot, evidence, receipt, source, catalog)
    if stage is _FEEDBACK:
        if records is None:
            _fail(
                "FEEDBACK_RECORDS_MISSING",
                "Audited coordinator evidence is required; no serial replay is permitted.",
            )
        return _verify_feedback_receipt(
            snapshot, evidence, receipt, source, catalog, records, directory=directory
        )
    if stage is _REFERENCE:
        if records is None or reference_workspace is None:
            _fail(
                "REFERENCE_CONTEXT_MISSING",
                "Audited campaign records and a server-assigned source workspace are required.",
            )
        return _verify_reference_receipt(
            snapshot,
            evidence,
            receipt,
            source,
            catalog,
            records,
            reference_workspace,
            directory=directory,
        )
    if stage is _NONCONTACT:
        if records is None or reference_workspace is None:
            _fail(
                "NONCONTACT_CONTEXT_MISSING",
                "Audited predecessor records and the server-assigned source workspace are required; no diagnostic replay is permitted.",
            )
        return _verify_noncontact_receipt(
            snapshot,
            evidence,
            receipt,
            source,
            catalog,
            records,
            reference_workspace,
            directory=directory,
        )
    _fail("UNEVALUATED_STAGE", "No registered retained evaluator for this stage.")


def _evaluation_reason_prefix(stage: PhysicalOnboardingStage) -> str:
    if stage in _OPTICS:
        return "OPTICS_CHECK_FAILED:"
    if stage is _ARM_IDENTITY:
        return "ARM_IDENTITY_CHECK_FAILED:"
    if stage in _POWER:
        return "POWER_CHECK_FAILED:"
    if stage is _FEEDBACK:
        return "FEEDBACK_CHECK_FAILED:"
    if stage is _REFERENCE:
        return "REFERENCE_CHECK_FAILED:"
    if stage is _NONCONTACT:
        return "NONCONTACT_CHECK_FAILED:"
    _fail("UNEVALUATED_STAGE", "No registered assessment predicate for this stage.")


def _verify_owned_feedback_directory(
    directory: Path, receipts: list[VerifiedRehearsalEvidence]
) -> None:
    """Observe the bounded original child cwd; never repair or retry an orphan."""
    retained = [
        item
        for item in receipts
        if item.document().get("schema") == _OWNED_FEEDBACK_SCHEMA
    ]
    root = directory / "owned-arm-feedback"
    present = root in _entries(directory, MAX_STORE_ENTRIES)
    if present and not retained:
        _fail(
            "ORPHAN_OWNED_ARM_DIRECTORY",
            "Owned feedback preparation exists without its exact retained stage receipt. Inspect/export the original store; do not rebuild or replay it.",
        )
    if retained and not present:
        _fail(
            "OWNED_ARM_DIRECTORY_MISSING",
            "The retained owned feedback directory is missing.",
        )
    if not retained:
        return
    if len(retained) != 1:
        _fail(
            "OWNED_ARM_DIRECTORY_MISMATCH",
            "One exact owned feedback receipt is required.",
        )
    attempt = retained[0].document()["attempt_result"]["attempt_id"]
    if type(attempt) is not str or _ID.fullmatch(attempt) is None:
        _fail(
            "OWNED_ARM_DIRECTORY_MISMATCH",
            "The retained attempt identifier is invalid.",
        )
    safe_root(root, label="retained owned arm directory")
    child = root / ("owned-arm-" + attempt)
    if set(_entries(root, 2)) != {child}:
        _fail(
            "OWNED_ARM_DIRECTORY_MISMATCH",
            "Only the exact original attempt working directory may be reopened.",
        )
    safe_root(child, label="retained incapable arm child directory")
    if _entries(child, 1):
        _fail(
            "OWNED_ARM_DIRECTORY_NOT_EMPTY",
            "The incapable arm child unexpectedly retained files. Do not clean, repair or replay it.",
        )


def _reconstruct(
    directory: Path,
    snapshot: V2SessionSnapshot,
    verification: M1RuntimeVerification,
    source: str,
    catalog: str,
    records: dict[str, dict[str, Any]],
    reference_workspace: Path | None = None,
) -> RestoredRehearsalState:
    evidence = _read_evidence(directory, snapshot, source, catalog)
    probe_document, probe, configuration_document, configuration = (
        _verify_camera_configuration_context(
            evidence,
            records,
            source,
            snapshot.header.session_id,
            directory=directory,
        )
    )
    referenced: set[str] = set()
    selected = latest_capture = None
    current_receipt = current_assessment = None
    opened: dict[PhysicalOnboardingStage, int] = {}
    current = snapshot.next_action.stage
    for index, event in enumerate(snapshot.committed_events):
        previous_head = V2CommittedHead.build(
            snapshot.header, snapshot.committed_events[:index]
        ).head_sha256
        refs = [evidence[item.evidence_id] for item in event.evidence]
        referenced.update(item.reference.evidence_id for item in refs)
        if (
            event.detail_code == "REHEARSAL_STAGE_OPENED"
            and event.state is V2StageState.WAITING_OPERATOR
            and not refs
        ):
            opened[event.stage] = event.occurred_at_ns
            continue
        if event.detail_code not in {
            "REHEARSAL_ASSESSMENT_READY",
            "REHEARSAL_ASSESSMENT_REVIEWED",
        }:
            _fail(
                "UNSUPPORTED_JOURNAL_EVENT",
                "Retained journal requires an unimplemented reconciliation path.",
            )
        required = 2 if event.state is V2StageState.REVIEW_PENDING else 3
        if len(refs) != required:
            _fail(
                "REVIEW_BINDING_MISMATCH",
                "Review event does not retain exact receipt/assessment/review references.",
            )
        receipt, assessment = refs[:2]
        receipt_doc, assessment_doc = receipt.document(), assessment.document()
        expected_schemas = (
            {
                "rocell.rehearsal_camera_campaign.v1",
                "rocell.rehearsal_camera_campaign.v2",
            }
            if event.stage in _CAMERA
            else (
                _evaluated_schemas(event.stage)
                if event.stage in _EVALUATED_SCHEMAS
                else {"rocell.rehearsal_stage_receipt.v1"}
            )
        )
        if receipt_doc.get("schema") not in expected_schemas:
            _fail(
                "RECEIPT_SCHEMA_MISMATCH",
                "Assessment references a document that is not this stage's receipt.",
            )
        if (
            assessment_doc.get("schema") != "rocell.rehearsal_assessment.v1"
            or assessment_doc["receipt_evidence_id"] != receipt.reference.evidence_id
            or assessment_doc["receipt_sha256"] != _hash(receipt_doc)
        ):
            _fail(
                "ASSESSMENT_BINDING_MISMATCH",
                "Assessment does not bind the exact retained receipt.",
            )
        reasons = (
            ["SYNTHETIC_CAMERA_MODEL_MISMATCH"]
            if event.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
            and receipt_doc.get("candidate", {}).get("model") != "B0477"
            else []
        )
        if event.stage in _EVALUATED_SCHEMAS:
            evaluated = _verify_evaluated_receipt(
                snapshot,
                evidence,
                receipt,
                source,
                catalog,
                records=records,
                directory=directory,
                **(
                    {"reference_workspace": reference_workspace}
                    if event.stage in {_REFERENCE, _NONCONTACT}
                    else {}
                ),
            )
            reasons = [
                _evaluation_reason_prefix(event.stage) + row["check_id"]
                for row in evaluated.checks
                if not row["passed"]
            ]
        if assessment_doc["reason_codes"] != reasons or assessment_doc["outcome"] != (
            "BLOCKED" if reasons else "PASS"
        ):
            _fail(
                "ASSESSMENT_PREDICATE_MISMATCH",
                "Retained assessment differs from the registered pure predicate.",
            )
        if event.state is V2StageState.REVIEW_PENDING:
            if (
                event.detail_code != "REHEARSAL_ASSESSMENT_READY"
                or assessment_doc["pre_assessment_head_sha256"] != previous_head
            ):
                _fail(
                    "STALE_ASSESSMENT",
                    "Assessment was not bound to the exact preceding journal head.",
                )
            if event.stage is current:
                current_receipt, current_assessment = receipt, assessment
        else:
            review = refs[2].document()
            if (
                event.state.value != assessment_doc["outcome"]
                or event.detail_code != "REHEARSAL_ASSESSMENT_REVIEWED"
                or review.get("schema") != "rocell.rehearsal_review.v1"
                or review["reviewed_head_sha256"] != previous_head
                or review["assessment_sha256"] != assessment_doc["assessment_sha256"]
                or review["operator_id"] != receipt_doc["operator_id"]
                or index == 0
                or snapshot.committed_events[index - 1].evidence != event.evidence[:2]
            ):
                _fail(
                    "REVIEW_BINDING_MISMATCH",
                    "Review does not bind the exact preceding assessment/head/operator.",
                )
            if event.stage is current:
                current_receipt = current_assessment = None
            if (
                event.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
                and event.state is V2StageState.PASS
            ):
                selected = receipt
        if receipt_doc.get("schema", "").startswith(
            "rocell.rehearsal_camera_campaign."
        ):
            latest_capture = receipt

    waiting = snapshot.next_action.stage_state is V2StageState.WAITING_OPERATOR
    settings = stage_open = None
    stage_operators: dict[PhysicalOnboardingStage, VerifiedRehearsalEvidence] = {}
    unreferenced_receipts = []
    for item in sorted(
        evidence.values(),
        key=lambda item: (item.captured_at_ns, item.reference.evidence_id),
    ):
        document = item.document()
        schema = document["schema"]
        if (
            schema
            in {
                "rocell.rehearsal_camera_stage_open.v1",
                "rocell.rehearsal_camera_settings.v1",
            }
            | set(_EVALUATED_OPEN_SCHEMAS.values())
            | _CAMERA_AUX_SCHEMAS
        ):
            if (
                item.reference.stage not in opened
                or item.captured_at_ns <= opened[item.reference.stage]
            ):
                _fail(
                    "ORPHAN_EVIDENCE",
                    "Lifecycle metadata is not bound to an opened stage.",
                )
            if schema.endswith("stage_open.v1") and item.reference.stage is current:
                stage_open = item
            if schema.endswith("stage_open.v1"):
                if item.reference.stage in stage_operators:
                    _fail(
                        "AMBIGUOUS_OPERATOR",
                        "Multiple stage operator records require reconciliation.",
                    )
                stage_operators[item.reference.stage] = item
            elif schema.endswith("settings.v1"):
                opening = stage_operators.get(item.reference.stage)
                if (
                    opening is None
                    or opening.document()["operator_id"] != document["operator_id"]
                ):
                    _fail(
                        "OPERATOR_BINDING_MISMATCH",
                        "Settings operator differs from its retained camera-stage opening.",
                    )
                settings = item
            continue
        if schema.startswith("rocell.rehearsal_camera_campaign."):
            result = document["attempt_result"]
            matches = [
                record
                for record in records.values()
                if record["kind"] == "CAMPAIGN_RESULT"
                and record["data"].get("result") == result
            ]
            if len(matches) != 1:
                _fail(
                    "CAMPAIGN_RESULT_MISMATCH",
                    "Camera stage receipt does not match one audited committed campaign result.",
                )
            latest_capture = item
        if item.reference.evidence_id not in referenced:
            if (
                waiting
                and item.reference.stage is current
                and current in opened
                and item.captured_at_ns > opened[current]
                and schema
                in {
                    "rocell.rehearsal_stage_receipt.v1",
                    "rocell.rehearsal_camera_campaign.v1",
                    "rocell.rehearsal_camera_campaign.v2",
                }
                | _ALL_EVALUATED_SCHEMAS
            ):
                unreferenced_receipts.append(item)
            else:
                _fail(
                    "ORPHAN_EVIDENCE",
                    "Retained evidence has no exact current receipt or committed event association.",
                )
    if len(unreferenced_receipts) > 1:
        _fail(
            "AMBIGUOUS_RECEIPT",
            "Multiple current-stage receipts require explicit reconciliation.",
        )
    if waiting:
        if current is None:
            _fail("STAGE_STATE_MISMATCH", "Waiting state has no exact current stage.")
        current_receipt = unreferenced_receipts[0] if unreferenced_receipts else None
        current_assessment = None
        if current_receipt is None:
            if current in _EVALUATED_SCHEMAS and current is not _FEEDBACK:
                _fail(
                    (
                        "OPTICS_RECEIPT_MISSING"
                        if current in _OPTICS
                        else "EVALUATION_RECEIPT_MISSING"
                    ),
                    "A synthetic evaluation opened without a retained result. Inspect/export; never rerun it during reopen.",
                )
            if any(
                record["kind"] == "EXACT_REQUEST_RESERVED"
                and record["data"]["permit"]["admission"]["stage"] == current.value
                and not (
                    probe_document is not None
                    and record["data"]["permit"]["registration"]["action_id"]
                    == "rehearsal-owned-camera-probe"
                    and record["data"]["attempt_id"]
                    == probe_document["attempt_result"]["attempt_id"]
                )
                for record in records.values()
            ):
                _fail(
                    "CAMPAIGN_RECEIPT_MISSING",
                    "A prior campaign exists without its stage receipt; never replay it.",
                )
    operator = (
        current_receipt.document()["operator_id"]
        if current_receipt
        else stage_open.document()["operator_id"] if stage_open else None
    )
    if selected:
        candidate = selected.document()["candidate"]
        _exact(
            candidate, {"candidate_id", "provenance", "model", "unit_id", "endpoint"}
        )
        if candidate != {
            "candidate_id": "synthetic-b0477",
            "provenance": "SYNTHETIC_NOT_ENUMERATED",
            "model": "B0477",
            "unit_id": "SYNTHETIC-UNIT-A",
            "endpoint": "incapable-fixture-only",
        }:
            _fail(
                "CAMERA_SELECTION_MISMATCH",
                "Reviewed identity is not the registered synthetic candidate.",
            )
    camera_receipts = [
        item
        for item in evidence.values()
        if item.document()["schema"].startswith("rocell.rehearsal_camera_campaign.")
    ]
    if len(camera_receipts) > 2:
        _fail(
            "CAMERA_DATASET_RESOURCE_LIMIT",
            "This reopen slice verifies at most the two original camera campaigns.",
        )
    fixture_roots = set()
    for item in camera_receipts:
        opening = stage_operators.get(item.reference.stage)
        if (
            opening is not None
            and opening.document()["operator_id"] != item.document()["operator_id"]
        ):
            _fail(
                "OPERATOR_BINDING_MISMATCH",
                "Camera receipt operator differs from its retained stage opening.",
            )
        if (
            selected is None
            or item.document()["plan"]["selected_camera"]
            != selected.document()["candidate"]
        ):
            _fail(
                "CAMERA_SELECTION_MISMATCH",
                "Camera campaign differs from the reviewed synthetic candidate.",
            )
        fixture_roots.add(
            _verify_camera_receipt(
                directory, item, source, settings, records=records, evidence=evidence
            )
        )
    evaluated_receipts = [
        item
        for item in evidence.values()
        if item.document()["schema"] in _ALL_EVALUATED_SCHEMAS
    ]
    if len(evaluated_receipts) > len(_EVALUATED_SCHEMAS) or len(
        {item.reference.stage for item in evaluated_receipts}
    ) != len(evaluated_receipts):
        _fail(
            "EVALUATION_RESOURCE_LIMIT",
            "This slice retains at most one evaluation per registered stage.",
        )
    for item in evaluated_receipts:
        opening = stage_operators.get(item.reference.stage)
        if (
            opening is None
            or opening.document()["operator_id"] != item.document()["operator_id"]
            or opening.captured_at_ns >= item.captured_at_ns
        ):
            _fail(
                (
                    "OPTICS_OPERATOR_MISMATCH"
                    if item.reference.stage in _OPTICS
                    else "EVALUATION_OPERATOR_MISMATCH"
                ),
                "The evaluated result does not follow its exact stage opening/operator.",
            )
        _verify_evaluated_receipt(
            snapshot,
            evidence,
            item,
            source,
            catalog,
            records=records,
            directory=directory,
            **(
                {"reference_workspace": reference_workspace}
                if item.reference.stage in {_REFERENCE, _NONCONTACT}
                else {}
            ),
        )
    actual_fixtures = {
        path
        for path in _entries(directory, MAX_STORE_ENTRIES)
        if path.name.startswith("binary-fixture-")
    }
    if actual_fixtures != fixture_roots:
        _fail(
            "ORPHAN_CAMERA_ARTIFACT",
            "A retained binary fixture has no exact verified stage receipt.",
        )
    expected_probe_directories = (
        {directory / ("camera-probe-" + probe_document["attempt_result"]["attempt_id"])}
        if probe_document is not None
        else set()
    )
    actual_probe_directories = {
        path
        for path in _entries(directory, MAX_STORE_ENTRIES)
        if path.name.startswith("camera-probe-")
    }
    if actual_probe_directories != expected_probe_directories:
        _fail(
            "ORPHAN_CAMERA_PROBE_DIRECTORY",
            "Only the exact retained probe's original working directory may be reopened.",
        )
    for path in expected_probe_directories:
        safe_root(path, label="retained incapable probe directory")
        if _entries(path, 1):
            _fail(
                "CAMERA_PROBE_DIRECTORY_NOT_EMPTY",
                "Capability probe unexpectedly retained files; do not replay or repair it.",
            )
    _verify_owned_feedback_directory(directory, evaluated_receipts)
    disposition = (
        "REVIEW_PENDING"
        if current_assessment
        else (
            "RECEIPT_READY"
            if current_receipt
            else "WAITING_NO_RECEIPT" if waiting else "DUE_STAGE"
        )
    )
    return RestoredRehearsalState(
        directory,
        snapshot.header.cell_id,
        snapshot.header.session_id,
        current,
        snapshot.next_action.stage_state,
        disposition,
        current_receipt,
        current_assessment,
        selected,
        operator,
        settings,
        latest_capture,
        tuple(evidence.values()),
        snapshot.head.head_sha256,
        verification.evidence_inventory_sha256,
        verification.challenge_sha256,
        snapshot.header.header_sha256,
    )


class RehearsalReopenRegistry:
    """Server-assigned roots only; browser inputs are opaque choice IDs/hashes."""

    def __init__(
        self,
        roots: tuple[KnownRehearsalRoot, ...],
        *,
        workspace_source_sha256: str,
        catalog_sha256: str,
        reference_workspace: Path | None = None,
    ) -> None:
        if (
            type(roots) is not tuple
            or not 1 <= len(roots) <= MAX_ROOTS
            or any(type(root) is not KnownRehearsalRoot for root in roots)
            or len({root.root_id for root in roots}) != len(roots)
            or len({root.directory for root in roots}) != len(roots)
        ):
            _fail(
                "INVALID_REGISTRY",
                "Supply unique typed server-assigned roots within the limit.",
            )
        for value in (workspace_source_sha256, catalog_sha256):
            if type(value) is not str or not _HASH.fullmatch(value):
                _fail(
                    "INVALID_REGISTRY",
                    "Source and catalog bindings must be exact SHA-256 values.",
                )
        self.roots, self.source, self.catalog = (
            roots,
            workspace_source_sha256,
            catalog_sha256,
        )
        self._discovery = RehearsalDiscovery()
        # This path is assigned by the service, never reconstructed from a store
        # or accepted from the browser. Construction performs no filesystem I/O.
        self.reference_workspace = reference_workspace
        self._lock = threading.RLock()

    def view(self) -> RehearsalDiscovery:
        return self._discovery

    def discover(self) -> RehearsalDiscovery:
        choices, issues = [], []
        with self._lock:
            for root in self.roots:
                try:
                    if not root.directory.exists():
                        issues.append(
                            ReopenHoldReason(
                                "ROOT_NOT_CREATED",
                                f"Assigned root {root.root_id} does not yet exist.",
                            )
                        )
                        continue
                    with _directory_guard(root.directory):
                        entries = _entries(root.directory, MAX_STORES_PER_ROOT)
                        for directory in entries:
                            try:
                                choices.append(
                                    _store_header(root, directory, self.source)
                                )
                            except Exception as error:
                                issues.append(
                                    _reason(
                                        error,
                                        location=f"{root.root_id}/{directory.name}",
                                    )
                                )
                except Exception as error:
                    issues.append(_reason(error, location=root.root_id))
            self._discovery = RehearsalDiscovery(tuple(choices), tuple(issues))
            return self._discovery

    def open(
        self,
        choice_id: str,
        *,
        expected_discovery_sha256: str,
        admission_facts: FactsProvider,
    ) -> RehearsalReopenResult:
        """Explicit qualification/lease I/O; never create a replacement session."""
        with self._lock:
            choice = next(
                (
                    item
                    for item in self._discovery.choices
                    if item.choice_id == choice_id
                ),
                None,
            )
            if choice is None or type(choice_id) is not str:
                return RehearsalReopenResult(
                    "READ_ONLY_HOLD",
                    (
                        ReopenHoldReason(
                            "UNKNOWN_CHOICE",
                            "Select a currently discovered server-issued store ID.",
                        ),
                    ),
                )
            try:
                root = next(
                    item for item in self.roots if item.root_id == choice.root_id
                )
                # Requalification owns M1 leases and replaces their child-file
                # pointers. Windows ReplaceFileW requires directory write
                # sharing; keep ancestry delete/rename denied while M1 applies
                # its own path, lease and challenge/content validation.
                with _directory_guard(
                    choice.directory, allow_directory_write_sharing=True
                ):
                    fresh = _store_header(root, choice.directory, self.source)
                    if (
                        fresh != choice
                        or expected_discovery_sha256 != fresh.discovery_sha256
                    ):
                        _fail(
                            "STALE_DISCOVERY",
                            "Store identity/header changed since explicit selection.",
                        )
                    if not fresh.source_matches:
                        _fail(
                            "SOURCE_DRIFT",
                            "The original store belongs to another workspace source; no conversion is permitted.",
                        )
                    _preflight_store(choice.directory)
                    runtime = PhysicalOnboardingM1Runtime.open(
                        choice.directory,
                        source_binding_sha256=rehearsal_source_binding(self.source),
                        cell_id=choice.cell_id,
                    )
                    adapter = M1CommissioningPersistence(
                        runtime,
                        workspace_source_sha256=self.source,
                        admission_facts=admission_facts,
                    )
                    verification = adapter.verification(choice.session_id)
                    if verification.quarantined:
                        _fail(
                            "CELL_QUARANTINED",
                            "The retained rehearsal cell is quarantined.",
                        )
                    if (
                        verification.unresolved_attempt_ids
                        or verification.uncertain_attempt_ids
                    ):
                        _fail(
                            "UNRESOLVED_ATTEMPTS",
                            "Retained attempts are unresolved or uncertain; nothing is replayed.",
                        )
                    if (
                        verification.session_reconciliation_required
                        or verification.active_lease_owners
                    ):
                        _fail(
                            "RECONCILIATION_REQUIRED",
                            "An uncommitted suffix or active/stale lease requires reconciliation.",
                        )
                    with adapter.stage_transaction(
                        choice.session_id,
                        expected_challenge_sha256=verification.challenge_sha256,
                    ) as tx:
                        snapshot = tx.snapshot()
                        if (
                            snapshot.header.header_sha256
                            != choice.session_header_sha256
                        ):
                            _fail(
                                "HEADER_BINDING_MISMATCH",
                                "The selected immutable session header changed.",
                            )
                        # Existing adapter audit validates persistent attempt/result
                        # bindings. Its permit records are inspected, never returned
                        # as capabilities and never sent to a coordinator/worker.
                        records = tx._audit_records()
                        restored = _reconstruct(
                            choice.directory,
                            snapshot,
                            verification,
                            self.source,
                            self.catalog,
                            records,
                            self.reference_workspace,
                        )
                        if (
                            tx.verification().challenge_sha256
                            != verification.challenge_sha256
                        ):
                            _fail(
                                "STATE_CHANGED",
                                "Evidence/head changed during reconstruction.",
                            )
                    after = adapter.verification(choice.session_id)
                    if after.challenge_sha256 != verification.challenge_sha256:
                        _fail(
                            "STATE_CHANGED",
                            "Evidence/head changed before reopen completed.",
                        )
                    return RehearsalReopenResult(
                        "OPENED",
                        restored=restored,
                        store=adapter,
                        snapshot=snapshot,
                        verification=after,
                    )
            except Exception as error:
                return RehearsalReopenResult("READ_ONLY_HOLD", (_reason(error),))


def _reason(error: Exception, *, location: str = "selected store") -> ReopenHoldReason:
    if isinstance(error, RehearsalReopenError):
        return ReopenHoldReason(error.code, f"{location}: {error}")
    # The underlying qualified readers retain the precise corruption/lease/
    # qualification failure. Bound the diagnostic; never reinterpret it as PASS.
    message = str(error).replace("\n", " ").replace("\r", " ")[:400]
    return ReopenHoldReason(
        "STORE_VERIFICATION_FAILED", f"{location}: {type(error).__name__}: {message}"
    )
