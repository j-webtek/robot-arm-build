"""Progressive original-evidence dependencies, never admission or acceptance.

An output of the current/future stage cannot be required before its producer
runs. This record describes that ordering; it waives no earlier hazard,
isolation, firmware or runtime qualification. References are unassessed even
when present. Append-only successor/invalidation workflows are not implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any

from .commissioning_camera_persistence import physical_camera_source_binding
from .configuration_epochs import _EXPECTED_EPOCH_IDS, _EXPECTED_INVALIDATES_FROM_STAGE
from .physical_camera_prerequisites import PhysicalCameraPrerequisites
from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from . import physical_onboarding_v2 as v2

SCHEMA = "rocell.physical_configuration_epochs.v1"
SUMMARY_SCHEMA = "rocell.physical_configuration_epochs_summary.v1"
EVIDENCE_LABEL = "physical-configuration-epochs-v1"
MAX_RECORD_BYTES = 64 * 1024
MAX_INVENTORY_REFERENCES = 32
MAX_INVENTORY_BYTES = 4 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FLAGS = {
    "physical_authority": False,
    "qualified": False,
    "canonical_stage_pass": False,
    "admission_allowed": False,
    "device_io_performed": False,
}
MEANING = (
    "Progressive dependency record only. Retained references are not qualified evidence. "
    "Pending current or future outputs waive no earlier hazard, isolation, firmware, "
    "runtime or stage prerequisite. Audited stage validators must interpret original "
    "bytes before consumption. No physical facts or permits are created; successor "
    "and invalidation workflows are not implemented."
)


class PhysicalConfigurationEpochError(ValueError):
    def __init__(self, code: str = "INVALID_CONFIGURATION_RECORD") -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str = "INVALID_CONFIGURATION_RECORD") -> None:
    if not condition:
        raise PhysicalConfigurationEpochError(code)


class EpochBindingName(str, Enum):
    BUILD_SNAPSHOT = "build_snapshot"
    SOURCE_BINDING = "source_binding"
    DEPENDENCY_RECEIPT = "dependency_receipt"
    PROVIDER_HASHES = "provider_hashes"
    CAMERA_RECEIPT = "camera_receipt"
    CAMERA_IDENTITY = "camera_identity"
    CAMERA_MODE_CONTROLS = "camera_mode_controls"
    SUPPORT_WITNESSES = "support_witnesses"
    BOARD_MEASUREMENT = "board_measurement"
    TAG_MAP = "tag_map"
    BENCH_IDENTITY = "bench_identity"
    BOARD_RESEAT_TEST = "board_reseat_test"
    ARM_IDENTITY = "arm_identity"
    CONTROLLER_IDENTITY = "controller_identity"
    FIRMWARE_IDENTITY = "firmware_identity"
    TOOL_IDENTITY = "tool_identity"
    POWER_TOPOLOGY = "power_topology"
    CUTOFF_TEST = "cutoff_test"
    CONTAINMENT_REVIEW = "containment_review"
    DISCHARGE_TEST = "discharge_test"
    KEYBOARD_IDENTITY = "keyboard_identity"
    KEYBOARD_POSE = "keyboard_pose"
    KEYBOARD_TARGET_MAP = "keyboard_target_map"
    PHONE_IDENTITY = "phone_identity"
    PHONE_POSE = "phone_pose"
    SCREEN_HOMOGRAPHY = "screen_homography"
    PHONE_TARGET_MAP = "phone_target_map"
    UI_STATE = "ui_state"
    INSTALLED_OBJECT_INVENTORY = "installed_object_inventory"
    COLLISION_GEOMETRY = "collision_geometry"
    STARTUP_SWEEP = "startup_sweep"
    EMPTY_CELL_WITNESS = "empty_cell_witness"


# These are producer boundaries, not permission to postpone safety prerequisites.
_OWNER_INDEX = (
    0,
    0,
    0,
    0,
    2,
    3,
    4,
    7,
    2,
    7,
    2,
    7,
    8,
    11,
    11,
    12,
    9,
    9,
    9,
    9,
    12,
    12,
    12,
    12,
    12,
    12,
    12,
    12,
    9,
    13,
    10,
    9,
)
BINDING_OWNER_STAGES = MappingProxyType(
    {
        key: STAGE_ORDER[index]
        for key, index in zip(EpochBindingName, _OWNER_INDEX, strict=True)
    }
)
_EPOCH_BINDINGS = (
    tuple(list(EpochBindingName)[0:4]),
    tuple(list(EpochBindingName)[4:8]),
    tuple(list(EpochBindingName)[8:12]),
    tuple(list(EpochBindingName)[12:16]),
    tuple(list(EpochBindingName)[16:20]),
    tuple(list(EpochBindingName)[20:23]),
    tuple(list(EpochBindingName)[23:28]),
    tuple(list(EpochBindingName)[28:32]),
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return value


def _digest(value: Any) -> None:
    _require(type(value) is str and _SHA.fullmatch(value) is not None)


def _reference(value: EvidenceReference) -> EvidenceReference:
    _require(type(value) is EvidenceReference, "EXACT_EVIDENCE_REFERENCE_REQUIRED")
    restored = _parse_evidence_reference(value.to_dict())
    _require(_canonical(restored.to_dict()) == _canonical(value.to_dict()))
    return restored


@dataclass(frozen=True, slots=True)
class EpochEvidenceBinding:
    binding: EpochBindingName
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require(type(self.binding) is EpochBindingName, "CLOSED_BINDING_NAME_REQUIRED")
        _require(type(self.evidence) is tuple and 1 <= len(self.evidence) <= 4)
        rows = tuple(_reference(v) for v in self.evidence)
        _require(len({v.evidence_id for v in rows}) == len(rows))
        _require(
            all(v.stage is BINDING_OWNER_STAGES[self.binding] for v in rows),
            "EVIDENCE_OWNER_STAGE_MISMATCH",
        )
        _require(tuple(sorted(rows, key=lambda v: v.evidence_id)) == rows)


def _inventory(references: Any) -> tuple[EvidenceReference, ...]:
    _require(
        type(references) is tuple and len(references) <= MAX_INVENTORY_REFERENCES,
        "INVENTORY_LIMIT",
    )
    rows = tuple(_reference(v) for v in references)
    _require(
        sum(v.payload_bytes for v in rows) <= MAX_INVENTORY_BYTES, "INVENTORY_LIMIT"
    )
    _require(len({v.evidence_id for v in rows}) == len(rows))
    _require(tuple(sorted(rows, key=lambda v: v.evidence_id)) == rows)
    return rows


def _snapshot(
    snapshot: v2.V2SessionSnapshot,
    *,
    static_contract_extension: bool = False,
    received_camera_extension: bool = False,
    camera_identity_extension: bool = False,
    usb_identity_extension: bool = False,
    usb_trial_extension: bool = False,
    usb_phase_extension: bool = False,
    usb_absence_extension: bool = False,
    usb_reconnect_extension: bool = False,
    usb_reboot_extension: bool = False,
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
) -> None:
    """Pure revalidation of typed supplied audit data; never opens an M1 store."""
    _require(type(snapshot) is v2.V2SessionSnapshot, "EXACT_V2_SNAPSHOT_REQUIRED")
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_ids, _ = _camera_mode_entry_extension(snapshot, camera_mode_entry)
    _require(
        camera_mode_entry is None or usb_complete_extension is True, "INVENTORY_LIMIT"
    )
    _require(
        type(snapshot.header) is v2.V2SessionHeader
        and type(snapshot.head) is v2.V2CommittedHead
    )
    header = v2._parse_header(snapshot.header.to_dict())
    _require(header.mode == "PHYSICAL_DIAGNOSTIC", "PHYSICAL_CAMERA_DOMAIN_REQUIRED")
    _require(
        type(snapshot.committed_events) is tuple
        and len(snapshot.committed_events) <= v2.MAX_JOURNAL_EVENTS
    )
    _require(
        type(snapshot.uncommitted_events) is tuple and not snapshot.uncommitted_events,
        "RECONCILIATION_REQUIRED",
    )
    _require(
        not camera_identity_extension or received_camera_extension, "INVENTORY_LIMIT"
    )
    _require(not usb_identity_extension or camera_identity_extension, "INVENTORY_LIMIT")
    _require(not usb_trial_extension or usb_identity_extension, "INVENTORY_LIMIT")
    _require(not usb_phase_extension or usb_trial_extension, "INVENTORY_LIMIT")
    _require(
        type(usb_absence_extension) is bool
        and (not usb_absence_extension or usb_phase_extension),
        "INVENTORY_LIMIT",
    )
    _require(
        type(usb_reconnect_extension) is bool
        and (not usb_reconnect_extension or usb_absence_extension),
        "INVENTORY_LIMIT",
    )
    _require(
        type(usb_complete_extension) is bool
        and (not usb_complete_extension or usb_reboot_extension)
        and type(usb_reboot_extension) is bool
        and (not usb_reboot_extension or usb_reconnect_extension),
        "INVENTORY_LIMIT",
    )
    if static_contract_extension or received_camera_extension:
        # Only original-reader restoration may carry the closed stage-2
        # extension. Original epoch creation and the public v1 verifier keep
        # their unchanged 32-reference domain. Validate the whole real audit;
        # never manufacture a source-only stage snapshot or earlier head.
        _require(
            type(snapshot.evidence) is tuple
            and len(snapshot.evidence) - len(mode_ids)
            <= (
                (
                    (
                        (
                            (185 if usb_complete_extension else 182)
                            if usb_reboot_extension
                            else (
                                171
                                if usb_reconnect_extension
                                else (160 if usb_absence_extension else 151)
                            )
                        )
                        if usb_phase_extension
                        else (142 if usb_trial_extension else 141)
                    )
                    if usb_identity_extension
                    else 135
                )
                if camera_identity_extension
                else (115 if received_camera_extension else 35)
            ),
            "INVENTORY_LIMIT",
        )
        rows = tuple(_reference(ref) for ref in snapshot.evidence)
        source = tuple(ref for ref in rows if ref.stage is STAGE_ORDER[0])
        static = tuple(ref for ref in rows if ref.stage is STAGE_ORDER[1])
        received = tuple(ref for ref in rows if ref.stage is STAGE_ORDER[2])
        identity = tuple(ref for ref in rows if ref.stage is STAGE_ORDER[3])
        _inventory(source)
        _require(
            len(rows)
            == len(source) + len(static) + len(received) + len(identity) + len(mode_ids)
            and len(static) <= 3
            and sum(ref.payload_bytes for ref in static) <= 320 * 1024
            and len(received) <= (80 if received_camera_extension else 0)
            and sum(ref.payload_bytes for ref in received)
            <= (4 * (4 * 1024 * 1024 + 384 * 1024) if received_camera_extension else 0)
            and len(identity)
            <= (
                (
                    (
                        (70 if usb_complete_extension else 67)
                        if usb_reboot_extension
                        else (56 if usb_reconnect_extension else 45)
                    )
                    if usb_absence_extension
                    else (
                        36
                        if usb_phase_extension
                        else (27 if usb_trial_extension else 26)
                    )
                )
                if usb_identity_extension
                else (20 if camera_identity_extension else 0)
            )
            and sum(ref.payload_bytes for ref in identity)
            <= (
                (
                    4 * 1200
                    + 300
                    + (16 if usb_trial_extension else 0)
                    + (1136 if usb_phase_extension else 0)
                    + (264 if usb_absence_extension else 0)
                    + (1224 if usb_reconnect_extension else 0)
                    + (1224 if usb_reboot_extension else 0)
                    + (56 if usb_complete_extension else 0)
                )
                * 1024
                if usb_identity_extension
                else (4 * 1200 * 1024 if camera_identity_extension else 0)
            ),
            "INVENTORY_LIMIT",
        )
        _require(
            len({ref.evidence_id for ref in rows}) == len(rows)
            and tuple(sorted(rows, key=lambda ref: ref.evidence_id)) == rows,
            "INVENTORY_LIMIT",
        )
    else:
        rows = _inventory(snapshot.evidence)
    inventory = {ref.evidence_id: ref for ref in rows}
    states = [v2.V2StageState.PENDING for _ in STAGE_ORDER]
    sequences: list[int | None] = [None for _ in STAGE_ORDER]
    evidence_ids: list[list[str]] = [[] for _ in STAGE_ORDER]
    previous, timestamp = "0" * 64, header.created_at_ns - 1
    for index, original in enumerate(snapshot.committed_events):
        _require(type(original) is v2.V2JournalEvent)
        event = v2._parse_event(original.to_dict())
        _require(
            event.sequence == index
            and event.previous_event_sha256 == previous
            and event.session_id == header.session_id
            and event.session_header_sha256 == header.header_sha256
            and event.occurred_at_ns > timestamp,
            "SNAPSHOT_EVENT_CHAIN",
        )
        _require(
            all(
                v.evidence_id in inventory
                and _canonical(v.to_dict())
                == _canonical(inventory[v.evidence_id].to_dict())
                for v in event.evidence
            ),
            "SNAPSHOT_EVIDENCE_CHAIN",
        )
        v2._apply_transition(states, event)
        stage_index = STAGE_ORDER.index(event.stage)
        sequences[stage_index] = index
        evidence_ids[stage_index].extend(v.evidence_id for v in event.evidence)
        if event.state is v2.V2StageState.INVALIDATED:
            for offset in range(stage_index, len(STAGE_ORDER)):
                if states[offset] not in {
                    v2.V2StageState.INCIDENT_HOLD,
                    v2.V2StageState.SIDE_EFFECT_UNCERTAIN,
                }:
                    sequences[offset] = index
        previous, timestamp = event.event_sha256, event.occurred_at_ns
    expected = tuple(
        v2.V2StageSnapshot(stage, states[i], sequences[i], tuple(evidence_ids[i]))
        for i, stage in enumerate(STAGE_ORDER)
    )
    _require(
        type(snapshot.stages) is tuple
        and len(snapshot.stages) == 15
        and all(type(v) is v2.V2StageSnapshot for v in snapshot.stages)
    )
    _require(
        _canonical([v.to_dict() for v in expected])
        == _canonical([v.to_dict() for v in snapshot.stages]),
        "SNAPSHOT_STAGE_CHAIN",
    )
    _require(
        v2.V2CommittedHead.build(header, snapshot.committed_events).to_dict()
        == v2._parse_head(snapshot.head.to_dict()).to_dict(),
        "SNAPSHOT_HEAD_CHAIN",
    )
    _require(
        type(snapshot.next_action) is v2.V2NextAction
        and _canonical(snapshot.next_action.to_dict())
        == _canonical(v2._derive_next_action(states).to_dict())
    )


def _binding(
    prerequisites: PhysicalCameraPrerequisites, snapshot: v2.V2SessionSnapshot
) -> dict[str, Any]:
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites,
        "EXACT_PREREQUISITES_REQUIRED",
    )
    original = PhysicalCameraPrerequisites(prerequisites.payload).to_dict()
    bound = original["binding"]
    header = snapshot.header
    _require(
        header.session_id == bound["session_id"]
        and header.source_binding_sha256
        == physical_camera_source_binding(bound["source_sha256"]),
        "ORIGINAL_CONTEXT_MISMATCH",
    )
    _require(
        re.fullmatch(r"physical-camera-[0-9a-f]{32}", header.session_id) is not None
        and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", header.cell_id)
        is not None,
        "PHYSICAL_CAMERA_DOMAIN_REQUIRED",
    )
    sources = {row["role"]: row for row in original["source_files"]}
    policy = json.loads(sources["epoch_policy"]["payload_utf8"])
    catalog = json.loads(sources["stage_catalog"]["payload_utf8"])
    _require([v["stage"] for v in catalog["stages"]] == [v.value for v in STAGE_ORDER])
    _require([v["id"] for v in policy["epochs"]] == list(_EXPECTED_EPOCH_IDS))
    for definition, expected in zip(policy["epochs"], _EPOCH_BINDINGS, strict=True):
        _require(
            definition["required_bindings"] == [v.value for v in expected],
            "POLICY_BINDINGS_CHANGED",
        )
    return {
        "source_sha256": bound["source_sha256"],
        "source_binding_sha256": header.source_binding_sha256,
        "session_id": header.session_id,
        "cell_id": header.cell_id,
        "origin_launch_id": bound["launch_session_id"],
        "session_header_sha256": header.header_sha256,
        "prerequisites_sha256": prerequisites.evidence_sha256,
        "epoch_policy_sha256": sources["epoch_policy"]["sha256"],
        "stage_catalog_sha256": sources["stage_catalog"]["sha256"],
    }


def _entries(
    bindings: tuple[EpochEvidenceBinding, ...],
    boundary_stage: PhysicalOnboardingStage,
    boundary: str,
) -> list[dict[str, Any]]:
    _require(type(bindings) is tuple and len(bindings) <= 32)
    _require(
        type(boundary_stage) is PhysicalOnboardingStage
        and type(boundary) is str
        and boundary in {"BEFORE_STAGE", "AFTER_STAGE"}
    )
    supplied: dict[EpochBindingName, tuple[EvidenceReference, ...]] = {}
    for item in bindings:
        _require(type(item) is EpochEvidenceBinding)
        item.__post_init__()
        _require(item.binding not in supplied, "DUPLICATE_BINDING")
        supplied[item.binding] = item.evidence
    index = STAGE_ORDER.index(boundary_stage)
    entries = []
    for epoch, names in zip(_EXPECTED_EPOCH_IDS, _EPOCH_BINDINGS, strict=True):
        rows = []
        for name in names:
            owner = BINDING_OWNER_STAGES[name]
            owner_index = STAGE_ORDER.index(owner)
            position = (
                "PREDECESSOR"
                if owner_index < index
                else "CURRENT_STAGE" if owner_index == index else "FUTURE_STAGE"
            )
            refs = supplied.get(name, ())
            _require(not refs or owner_index <= index, "FUTURE_EVIDENCE_REFUSED")
            status = (
                "RETAINED_REFERENCE_UNASSESSED"
                if refs
                else (
                    "MISSING_PREDECESSOR"
                    if owner_index < index
                    else (
                        "PENDING_FUTURE_OUTPUT"
                        if owner_index > index
                        else (
                            "MISSING_CURRENT_OUTPUT"
                            if boundary == "AFTER_STAGE"
                            else "PENDING_CURRENT_OUTPUT"
                        )
                    )
                )
            )
            rows.append(
                {
                    "binding_id": name.value,
                    "owner_stage": owner.value,
                    "relative_position": position,
                    "status": status,
                    "evidence": [v.to_dict() for v in refs],
                }
            )
        count = sum(bool(v["evidence"]) for v in rows)
        entries.append(
            {
                "epoch_id": epoch,
                "invalidates_from_stage": _EXPECTED_INVALIDATES_FROM_STAGE[epoch].value,
                "status": (
                    "UNOBSERVED"
                    if not count
                    else (
                        "REFERENCES_RETAINED_UNASSESSED"
                        if count == len(rows)
                        else "PARTIALLY_REFERENCED"
                    )
                ),
                "bindings": rows,
            }
        )
    return entries


def _coverage(entries: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [row["status"] for entry in entries for row in entry["bindings"]]
    return {
        "total_bindings": 32,
        **{
            key: statuses.count(status)
            for key, status in (
                ("retained", "RETAINED_REFERENCE_UNASSESSED"),
                ("missing_predecessors", "MISSING_PREDECESSOR"),
                ("missing_current_outputs", "MISSING_CURRENT_OUTPUT"),
                ("pending_current_outputs", "PENDING_CURRENT_OUTPUT"),
                ("pending_future_outputs", "PENDING_FUTURE_OUTPUT"),
            )
        },
    }


def _decode(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_RECORD_BYTES,
        "RECORD_BYTE_LIMIT",
    )

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            _require(key not in result, "DUPLICATE_FIELD")
            result[key] = value
        return result

    try:
        obj = json.loads(payload.decode("ascii"), object_pairs_hook=unique)
        _exact(
            obj,
            {
                "schema",
                "binding",
                "original_snapshot",
                "boundary",
                "entries",
                "coverage",
                "meaning",
                *_FLAGS,
            },
        )
        _require(
            obj["schema"] == SCHEMA
            and obj["meaning"] == MEANING
            and all(obj[k] is False for k in _FLAGS)
        )
        bound = _exact(
            obj["binding"],
            {
                "source_sha256",
                "source_binding_sha256",
                "session_id",
                "cell_id",
                "origin_launch_id",
                "session_header_sha256",
                "prerequisites_sha256",
                "epoch_policy_sha256",
                "stage_catalog_sha256",
            },
        )
        for name, value in bound.items():
            if name.endswith("sha256"):
                _digest(value)
            else:
                _require(
                    type(value) is str
                    and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", value)
                    is not None
                )
        _require(
            bound["source_binding_sha256"]
            == physical_camera_source_binding(bound["source_sha256"])
            and re.fullmatch(r"physical-camera-[0-9a-f]{32}", bound["session_id"])
            is not None
            and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", bound["cell_id"])
            is not None,
            "PHYSICAL_CAMERA_DOMAIN_REQUIRED",
        )
        original = _exact(
            obj["original_snapshot"],
            {"head", "evidence_inventory", "evidence_inventory_sha256"},
        )
        head = v2._parse_head(original["head"])
        _require(
            head.session_id == bound["session_id"]
            and head.session_header_sha256 == bound["session_header_sha256"]
        )
        _require(type(original["evidence_inventory"]) is list)
        refs = _inventory(
            tuple(_parse_evidence_reference(v) for v in original["evidence_inventory"])
        )
        _require(
            _hash(original["evidence_inventory"])
            == original["evidence_inventory_sha256"]
        )
        _exact(obj["boundary"], {"stage", "phase"})
        stage, phase = (
            PhysicalOnboardingStage(obj["boundary"]["stage"]),
            obj["boundary"]["phase"],
        )
        _require(
            all(STAGE_ORDER.index(v.stage) <= STAGE_ORDER.index(stage) for v in refs),
            "FUTURE_EVIDENCE_REFUSED",
        )
        _require(type(obj["entries"]) is list and len(obj["entries"]) == 8)
        supplied = []
        inventory = {v.evidence_id: v.to_dict() for v in refs}
        for entry in obj["entries"]:
            _exact(entry, {"epoch_id", "invalidates_from_stage", "status", "bindings"})
            _require(type(entry["bindings"]) is list and len(entry["bindings"]) <= 5)
            for row in entry["bindings"]:
                _exact(
                    row,
                    {
                        "binding_id",
                        "owner_stage",
                        "relative_position",
                        "status",
                        "evidence",
                    },
                )
                _require(type(row["evidence"]) is list and len(row["evidence"]) <= 4)
                if row["evidence"]:
                    owned = tuple(_parse_evidence_reference(v) for v in row["evidence"])
                    _require(
                        all(
                            v.evidence_id in inventory
                            and _canonical(v.to_dict())
                            == _canonical(inventory[v.evidence_id])
                            for v in owned
                        ),
                        "EVIDENCE_NOT_IN_ORIGINAL_INVENTORY",
                    )
                    supplied.append(
                        EpochEvidenceBinding(EpochBindingName(row["binding_id"]), owned)
                    )
        expected = _entries(tuple(supplied), stage, phase)
        _require(
            _canonical(obj["entries"]) == _canonical(expected),
            "DEPENDENCY_PROJECTION_CHANGED",
        )
        _require(_canonical(obj["coverage"]) == _canonical(_coverage(expected)))
        _require(_canonical(obj) == payload, "NONCANONICAL_RECORD")
        return obj
    except PhysicalConfigurationEpochError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        OverflowError,
    ) as error:
        raise PhysicalConfigurationEpochError() from error


@dataclass(frozen=True, slots=True)
class PhysicalConfigurationEpochs:
    payload: bytes

    def __post_init__(self) -> None:
        _decode(self.payload)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        obj = self.to_dict()
        original = obj["original_snapshot"]
        return {
            "schema": SUMMARY_SCHEMA,
            "record_sha256": self.sha256,
            "binding": obj["binding"],
            "boundary": obj["boundary"],
            "original_snapshot": {
                "head_sha256": original["head"]["head_sha256"],
                "event_count": original["head"]["event_count"],
                "evidence_inventory_sha256": original["evidence_inventory_sha256"],
                "reference_count": len(original["evidence_inventory"]),
            },
            "entries": [
                {
                    **{
                        k: entry[k]
                        for k in ("epoch_id", "invalidates_from_stage", "status")
                    },
                    "bindings": [
                        {
                            **{
                                k: row[k]
                                for k in (
                                    "binding_id",
                                    "owner_stage",
                                    "relative_position",
                                    "status",
                                )
                            },
                            "evidence_count": len(row["evidence"]),
                            "payload_sha256s": [
                                v["payload_sha256"] for v in row["evidence"]
                            ],
                        }
                        for row in entry["bindings"]
                    ],
                }
                for entry in obj["entries"]
            ],
            "coverage": obj["coverage"],
            **_FLAGS,
            "meaning": MEANING,
        }


def build_physical_configuration_epochs(
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    *,
    evidence_bindings: tuple[EpochEvidenceBinding, ...] = (),
    boundary_stage: PhysicalOnboardingStage | None = None,
    boundary: str = "BEFORE_STAGE",
) -> PhysicalConfigurationEpochs:
    try:
        _snapshot(snapshot)
        bound = _binding(prerequisites, snapshot)
        stage = snapshot.next_action.stage if boundary_stage is None else boundary_stage
        _require(
            type(stage) is PhysicalOnboardingStage
            and stage is snapshot.next_action.stage,
            "EXACT_CURRENT_BOUNDARY_REQUIRED",
        )
        assert stage is not None
        entries = _entries(evidence_bindings, stage, boundary)
        inventory = [v.to_dict() for v in snapshot.evidence]
        result = PhysicalConfigurationEpochs(
            _canonical(
                {
                    "schema": SCHEMA,
                    "binding": bound,
                    "original_snapshot": {
                        "head": snapshot.head.to_dict(),
                        "evidence_inventory": inventory,
                        "evidence_inventory_sha256": _hash(inventory),
                    },
                    "boundary": {"stage": stage.value, "phase": boundary},
                    "entries": entries,
                    "coverage": _coverage(entries),
                    **_FLAGS,
                    "meaning": MEANING,
                }
            )
        )
        return result
    except PhysicalConfigurationEpochError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise PhysicalConfigurationEpochError() from error


def verify_physical_configuration_epochs(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Verify original committed prefix and reference subset, without replay/IO.

    Evidence manifests' collection chronology and semantic purpose are outside
    this reference-only component. The supplied snapshot and expected hash must
    come from the service's original-store audit, never a browser hash map.
    """
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=False,
    )


def _verify_physical_configuration_epochs_after_static(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private original-reader join for source32 + three stage-2 subjects.

    The caller also verifies every static label, codec and journal event. This
    verifier still authenticates the complete real current journal/inventory
    and the unchanged original epoch prefix, bounds, binding and references.
    """
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
    )


def _verify_physical_configuration_epochs(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
    static_contract_extension: bool,
    received_camera_extension: bool = False,
    camera_identity_extension: bool = False,
    usb_identity_extension: bool = False,
    usb_trial_extension: bool = False,
    usb_phase_extension: bool = False,
    usb_absence_extension: bool = False,
    usb_reconnect_extension: bool = False,
    usb_reboot_extension: bool = False,
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
) -> PhysicalConfigurationEpochs:
    try:
        result = PhysicalConfigurationEpochs(payload)
        _digest(expected_sha256)
        _require(result.sha256 == expected_sha256, "RECORD_HASH_MISMATCH")
        _snapshot(
            snapshot,
            static_contract_extension=static_contract_extension,
            received_camera_extension=received_camera_extension,
            camera_identity_extension=camera_identity_extension,
            usb_identity_extension=usb_identity_extension,
            usb_trial_extension=usb_trial_extension,
            usb_phase_extension=usb_phase_extension,
            usb_absence_extension=usb_absence_extension,
            usb_reconnect_extension=usb_reconnect_extension,
            usb_reboot_extension=usb_reboot_extension,
            usb_complete_extension=usb_complete_extension,
            camera_mode_entry=camera_mode_entry,
        )
        obj = result.to_dict()
        _require(
            obj["binding"] == _binding(prerequisites, snapshot),
            "ORIGINAL_CONTEXT_MISMATCH",
        )
        original = obj["original_snapshot"]
        count = original["head"]["event_count"]
        _require(count <= len(snapshot.committed_events), "ORIGINAL_PREFIX_MISSING")
        _require(
            _canonical(
                v2.V2CommittedHead.build(
                    snapshot.header, snapshot.committed_events[:count]
                ).to_dict()
            )
            == _canonical(original["head"]),
            "ORIGINAL_PREFIX_MISMATCH",
        )
        states = [v2.V2StageState.PENDING for _ in STAGE_ORDER]
        for event in snapshot.committed_events[:count]:
            v2._apply_transition(states, event)
        _require(
            v2._derive_next_action(states).stage
            is PhysicalOnboardingStage(obj["boundary"]["stage"]),
            "ORIGINAL_BOUNDARY_MISMATCH",
        )
        inventory = {v.evidence_id: v.to_dict() for v in snapshot.evidence}
        _require(
            all(
                v["evidence_id"] in inventory
                and _canonical(v) == _canonical(inventory[v["evidence_id"]])
                for v in original["evidence_inventory"]
            ),
            "ORIGINAL_INVENTORY_MISSING_OR_CHANGED",
        )
        return result
    except PhysicalConfigurationEpochError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise PhysicalConfigurationEpochError() from error


def _verify_physical_configuration_epochs_after_received_camera(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v6 join; the original reader authenticates all stage-owned roles.

    The full real snapshot is verified, while the original vector retains its
    unchanged source32 creation inventory and committed-prefix requirements.
    """
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
    )


def _verify_physical_configuration_epochs_after_camera_identity(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v7 inventory join; the original reader owns all identity semantics."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_identity(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v8 join; final reader authenticates all six exact USB role labels."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_trial(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v9: the final reader owns the sole trial declaration role."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_phase(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v10; final original reader owns every added BASELINE role/event."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_absence(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v11; final reader authenticates the closed ABSENCE suffix."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
        usb_absence_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_reconnect(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v12; the original reader owns every exact suffix role/event."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
        usb_absence_extension=True,
        usb_reconnect_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_reboot(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v13 restoration; public epoch creation limits remain unchanged."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
        usb_absence_extension=True,
        usb_reconnect_extension=True,
        usb_reboot_extension=True,
    )


def _verify_physical_configuration_epochs_after_usb_complete(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
) -> PhysicalConfigurationEpochs:
    """Private v14: only three file-only roles (56 KiB), no extra campaign."""
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
        usb_absence_extension=True,
        usb_reconnect_extension=True,
        usb_reboot_extension=True,
        usb_complete_extension=True,
    )


def _verify_physical_configuration_epochs_after_camera_mode_entry(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    snapshot: v2.V2SessionSnapshot,
    expected_sha256: str,
    camera_mode_entry,
) -> PhysicalConfigurationEpochs:
    """Private v15: a separately revalidated one-record, 16 KiB stage-5 suffix."""
    _require(camera_mode_entry is not None, "CAMERA_MODE_ENTRY_REQUIRED")
    return _verify_physical_configuration_epochs(
        payload,
        prerequisites=prerequisites,
        snapshot=snapshot,
        expected_sha256=expected_sha256,
        static_contract_extension=True,
        received_camera_extension=True,
        camera_identity_extension=True,
        usb_identity_extension=True,
        usb_trial_extension=True,
        usb_phase_extension=True,
        usb_absence_extension=True,
        usb_reconnect_extension=True,
        usb_reboot_extension=True,
        usb_complete_extension=True,
        camera_mode_entry=camera_mode_entry,
    )
