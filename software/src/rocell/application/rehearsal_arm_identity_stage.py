"""Explicit stage-9 rehearsal, never a physical arm identity qualification.

Evaluation reads the fixed arm profile and calls the existing inventory APIs
with closed, in-memory fixtures. Verification only reparses retained reports
and recomputes predicates; it does not load files, enumerate, or replay probes.
The caller owns authentication of source/binding/evidence hashes and publication.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from rocell.arm.connection import ArmConnectionProfile
from rocell.application.physical_device_inventory import (
    DeviceInventoryBatch,
    InventoryAuthority,
    InventoryDeviceClass,
    InventorySource,
    NormalizedDeviceCandidate,
    PhysicalDeviceInventoryReport,
    RawSerialPortObservation,
)


SCHEMA = "rocell.rehearsal_arm_identity_stage.v1"
EVALUATOR_ID = "SUBSTANTIVE_SYNTHETIC_ARM_IDENTITY_V1"
MAX_EVIDENCE_BYTES = 96 * 1024
_PROFILE = "software/config/arm_connection.json"
_HEX = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_MODEL = "Waveshare RoArm-M3 Pro"
_SOURCE = InventorySource.INJECTED_SERIAL_ENUMERATOR
_AUTHORITY = {
    "composition": "HARDWARE_INCAPABLE_REHEARSAL",
    "physical_authority": False,
    "hardware_accessed": False,
    "serial_port_opened": False,
    "serial_bytes_written": 0,
    "camera_opened": False,
    "arm_identity_qualified": False,
    "firmware_qualified": False,
    "driver_qualified": False,
    "feedback_authorized": False,
    "motion_authorized": False,
    "contact_authorized": False,
    "stage_advance_authority": False,
    "physical_release_effect": "NONE",
}
_PROVENANCE = {
    "inventory_input": "CLOSED_IN_MEMORY_SYNTHETIC_METADATA_NOT_HOST_INVENTORY",
    "model_input": "SYNTHETIC_CHASSIS_LABEL_NOT_INFERRED_FROM_USB_OR_COM",
    "static_registration_role": "EXACT_PREDECESSOR_DEPENDENCY_NOT_REEVALUATED",
    "captured_at_unix_ns_role": "FIXED_SYNTHETIC_ZERO_NOT_OBSERVATION_TIME",
    "driver_service_role": "RAW_INTERFACE_METADATA_NOT_VERIFIED_DRIVER_SERVICE",
    "location_role": "RAW_TOPOLOGY_METADATA_NOT_NORMALIZED_CANDIDATE_IDENTITY",
    "received_pro_arm_identity": "PHYSICAL_EVIDENCE_PENDING",
    "firmware_identity": "PHYSICAL_EVIDENCE_PENDING",
    "boot_reset_behavior": "PHYSICAL_EVIDENCE_PENDING",
    "driver_identity_and_version": "PHYSICAL_EVIDENCE_PENDING",
    "power_state": "NOT_OBSERVED_NO_ENERGY_ACTION",
}
_PERMANENT_BLOCKERS = {
    "CAMERA_CANDIDATE_NOT_OBSERVED",
    "INVENTORY_ONLY_NOT_DEVICE_QUALIFICATION",
    "CAMERA_STREAM_NOT_OPENED_BY_DESIGN",
    "CAMERA_USB3_TOPOLOGY_REQUIRES_SEPARATE_EVIDENCE",
    "SERIAL_PORT_NOT_OPENED_BY_DESIGN",
    "ROARM_IDENTITY_REQUIRES_SEPARATE_EVIDENCE",
}


class RehearsalArmIdentityError(ValueError):
    """Invalid, oversized, inconsistent or incorrectly bound stage evidence."""


def _object(value: object, keys: set[str] | None = None) -> dict[str, Any]:
    if type(value) is not dict or (keys is not None and set(value) != keys):
        raise RehearsalArmIdentityError("object has missing or unknown fields")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise RehearsalArmIdentityError("expected a lowercase SHA-256 digest")
    return value


def _tree(value: object, depth: int = 0) -> None:
    if depth > 20:
        raise RehearsalArmIdentityError("JSON nesting exceeds the bound")
    if type(value) is dict:
        if len(value) > 64 or any(type(k) is not str or len(k) > 128 for k in value):
            raise RehearsalArmIdentityError("invalid object key/count")
        for item in value.values():
            _tree(item, depth + 1)
    elif type(value) is list:
        if len(value) > 64:
            raise RehearsalArmIdentityError("array exceeds the bound")
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is str:
        if len(value) > MAX_EVIDENCE_BYTES:
            raise RehearsalArmIdentityError("string exceeds the bound")
    elif type(value) is int:
        if abs(value) > (1 << 63) - 1:
            raise RehearsalArmIdentityError("integer exceeds the bound")
    elif type(value) is float:
        if not math.isfinite(value):
            raise RehearsalArmIdentityError("nonfinite number")
    elif value is not None and type(value) is not bool:
        raise RehearsalArmIdentityError("non-JSON value")


def _canonical(value: object) -> bytes:
    _tree(value)
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RehearsalArmIdentityError("invalid JSON encoding") from exc
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise RehearsalArmIdentityError("evidence exceeds 96 KiB")
    return raw


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _same(left: object, right: object, label: str) -> None:
    # Strict canonical comparison does not conflate false/0 or true/1.
    if _canonical(left) != _canonical(right):
        raise RehearsalArmIdentityError(f"{label} mismatch")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            raise RehearsalArmIdentityError("duplicate JSON key")
        result[key] = item
    return result


def _reject_constant(value: str) -> None:
    raise RehearsalArmIdentityError("nonfinite JSON constant")


def _decode(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        raise RehearsalArmIdentityError("expected nonempty bounded JSON bytes")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=_reject_constant,
        )
        _tree(value)
        return _object(value)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise RehearsalArmIdentityError("invalid bounded stage JSON") from exc


@dataclass(frozen=True, slots=True)
class RehearsalArmIdentityBinding:
    workspace_source_sha256: str
    catalog_sha256: str
    cell_id: str
    session_id: str
    operator_id: str
    predecessor_receipt_sha256: str
    predecessor_assessment_sha256: str
    predecessor_review_sha256: str
    static_registration_evidence_sha256: str
    stage: str = "arm_identity"

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if key in {"cell_id", "session_id", "operator_id"}:
                if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
                    raise RehearsalArmIdentityError(f"invalid {key}")
            elif key == "stage":
                if type(value) is not str or value != "arm_identity":
                    raise RehearsalArmIdentityError("unsupported stage")
            else:
                _digest(value)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RehearsalArmIdentityEvidence:
    """Immutable canonical data; construction alone is not trusted admission."""

    _payload: bytes

    @property
    def outcome(self) -> str:
        return str(self.to_dict()["outcome"])

    @property
    def checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.to_dict()["checks"])

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def canonical_bytes(self) -> bytes:
        return self._payload

    def to_dict(self) -> dict[str, Any]:
        return _decode(self._payload)


def _nominal_raw() -> RawSerialPortObservation:
    # Deliberately fictional identities/COM names; never a hardware allowlist.
    return RawSerialPortObservation(
        port_name="COM42",
        description="INCAPABLE fixture USB bridge",
        hwid="USB VID:PID=1234:5678 SER=INCAPABLE-ARM-001",
        vid="1234",
        pid="5678",
        serial_number="INCAPABLE-ARM-001",
        location="INCAPABLE-USB-ROOT.PORT-1",
        manufacturer="INCAPABLE fixture",
        product="INCAPABLE fixture bridge",
        interface="INCAPABLE interface A",
    )


def _selection_baseline() -> dict[str, Any]:
    raw = _nominal_raw()
    candidate = NormalizedDeviceCandidate(
        InventoryDeviceClass.SERIAL,
        _SOURCE,
        raw.description or "",
        "1234",
        "5678",
        raw.serial_number,
        raw.hwid,
        ("usb-unit:1234:5678:INCAPABLE-ARM-001",),
        raw.port_name,
        raw.manufacturer,
        raw.product,
        raw.interface,
        (),
    )
    return {
        "candidate": candidate.to_dict(),
        "candidate_sha256": candidate.candidate_sha256,
        "raw_location": raw.location,
        "raw_interface": raw.interface,
        "modeled_chassis_label": _MODEL,
        "role": "SYNTHETIC_PRESELECTED_SNAPSHOT_NOT_PHYSICAL_SELECTION",
    }


def _scenarios() -> dict[str, dict[str, Any]]:
    raw = _nominal_raw()
    specifications = {
        "nominal": ((raw,), _MODEL, ()),
        "wrong_model": (
            (raw,),
            "Waveshare RoArm-M3 S",
            ("MODELED_CHASSIS_MODEL_MISMATCH",),
        ),
        "missing_device": ((), _MODEL, ("EXACTLY_ONE_CANDIDATE_REQUIRED",)),
        "missing_unit_serial": (
            (replace(raw, serial_number=None, hwid="USB VID:PID=1234:5678"),),
            _MODEL,
            ("PERSISTENT_IDENTITY_INCOMPLETE",),
        ),
        "duplicate_identity": (
            (raw, replace(raw, port_name="COM43")),
            _MODEL,
            ("PERSISTENT_IDENTITY_DUPLICATED",),
        ),
        "stale_alias": (
            (replace(raw, port_name="COM44"),),
            _MODEL,
            ("EPHEMERAL_ALIAS_CHANGED",),
        ),
        "changed_topology": (
            (replace(raw, location="INCAPABLE-USB-ROOT.PORT-2"),),
            _MODEL,
            ("RAW_TOPOLOGY_CHANGED",),
        ),
        "changed_interface": (
            (replace(raw, interface="INCAPABLE interface B"),),
            _MODEL,
            ("RAW_INTERFACE_METADATA_CHANGED",),
        ),
        "changed_usb_identity": (
            (
                replace(
                    raw, vid="abcd", hwid="USB VID:PID=abcd:5678 SER=INCAPABLE-ARM-001"
                ),
            ),
            _MODEL,
            ("PERSISTENT_IDENTITY_CHANGED",),
        ),
        "unexpected_output": (
            ({"unexpected_observation": True},),
            _MODEL,
            ("INVENTORY_OUTPUT_REJECTED",),
        ),
    }
    return {
        name: {
            "injected_payload": [
                asdict(row) if type(row) is RawSerialPortObservation else row
                for row in rows
            ],
            "modeled_chassis_label": model,
            "expected_reason_codes": list(reasons),
        }
        for name, (rows, model, reasons) in specifications.items()
    }


class _ClosedEnumerator:
    """Only instantiated internally; holds immutable fixture values, no OS API."""

    def __init__(self, specification: dict[str, Any]) -> None:
        self._rows = tuple(
            RawSerialPortObservation(**row) if "port_name" in row else dict(row)
            for row in specification["injected_payload"]
        )

    def enumerate_serial_ports(self) -> tuple[RawSerialPortObservation, ...]:
        # The single malformed fixture intentionally tests the API's type guard.
        return self._rows  # type: ignore[return-value]


def _empty_camera() -> DeviceInventoryBatch:
    # A synthetic empty batch lets the real composer preserve camera holds.
    return DeviceInventoryBatch(
        InventoryDeviceClass.CAMERA, InventorySource.WINDOWS_PNP, (), (), True
    )


def _candidate(value: object) -> NormalizedDeviceCandidate:
    obj = _object(
        value,
        {
            "device_class",
            "source",
            "display_name",
            "usb_identity",
            "os_instance_id",
            "persistent_ids",
            "ephemeral_locator_observation",
            "manufacturer",
            "product",
            "driver_service",
            "identity_blockers",
            "selection_performed",
            "qualified",
        },
    )
    usb = _object(obj["usb_identity"], {"vid", "pid", "unit_serial"})
    if (
        type(obj["persistent_ids"]) is not list
        or type(obj["identity_blockers"]) is not list
    ):
        raise RehearsalArmIdentityError("candidate identifiers/blockers must be arrays")
    model = NormalizedDeviceCandidate(
        InventoryDeviceClass.SERIAL,
        _SOURCE,
        obj["display_name"],
        usb["vid"],
        usb["pid"],
        usb["unit_serial"],
        obj["os_instance_id"],
        tuple(obj["persistent_ids"]),
        obj["ephemeral_locator_observation"],
        obj["manufacturer"],
        obj["product"],
        obj["driver_service"],
        tuple(obj["identity_blockers"]),
    )
    _same(obj, model.to_dict(), "normalized candidate")
    return model


def _inventory_report(value: object) -> PhysicalDeviceInventoryReport:
    obj = _object(
        value,
        {
            "schema",
            "purpose",
            "platform_system",
            "captured_at_unix_ns",
            "camera_inventory",
            "serial_inventory",
            "blockers",
            "authority",
            "report_sha256",
        },
    )
    serial = _object(
        obj["serial_inventory"],
        {
            "schema",
            "device_class",
            "source",
            "collection_complete",
            "collection_blockers",
            "candidates",
            "boundary",
        },
    )
    if type(serial["candidates"]) is not list or len(serial["candidates"]) > 2:
        raise RehearsalArmIdentityError("retained fixture candidate count exceeds two")
    if (
        type(serial["collection_blockers"]) is not list
        or type(obj["blockers"]) is not list
    ):
        raise RehearsalArmIdentityError("report blockers must be arrays")
    batch = DeviceInventoryBatch(
        InventoryDeviceClass.SERIAL,
        _SOURCE,
        tuple(_candidate(row) for row in serial["candidates"]),
        tuple(serial["collection_blockers"]),
        serial["collection_complete"],
    )
    _same(serial, batch.to_dict(), "serial batch")
    report = PhysicalDeviceInventoryReport(
        "Windows",
        0,
        _empty_camera(),
        batch,
        tuple(obj["blockers"]),
        InventoryAuthority(),
    )
    _same(obj, report.to_dict(), "composed inventory report")
    return report


def _expected_inventory_blockers(batch: DeviceInventoryBatch) -> list[str]:
    # Pure retained consistency, not a call to the collection/composer APIs.
    blockers = _PERMANENT_BLOCKERS | set(batch.collection_blockers)
    blockers.add(
        "SERIAL_SELECTION_NOT_PERFORMED_BY_DESIGN"
        if batch.candidates
        else "SERIAL_CANDIDATE_NOT_OBSERVED"
    )
    if len(batch.candidates) > 1:
        blockers.add("SERIAL_CANDIDATE_SELECTION_UNRESOLVED")
    if any(row.identity_blockers for row in batch.candidates):
        blockers.add("SERIAL_IDENTITY_INCOMPLETE")
    identifiers = [pid for row in batch.candidates for pid in row.persistent_ids]
    if len(set(identifiers)) != len(identifiers):
        blockers.add("SERIAL_PERSISTENT_ID_AMBIGUOUS")
    return sorted(blockers)


def _fixture_candidates(specification: dict[str, Any]) -> list[dict[str, object]]:
    """Independent pure oracle for the closed fixture fields, not enumeration.

    All fixture VID/PID fields are explicit and consistent with HWID. The one
    missing-serial fixture intentionally has no embedded serial fallback. Do
    not generalize this into a second OS-metadata parser or physical selector.
    """
    candidates = []
    for fields in specification["injected_payload"]:
        raw = RawSerialPortObservation(**fields)
        vid, pid = raw.vid, raw.pid
        # This oracle has only explicit string IDs in its closed fixtures. Do
        # not infer a missing identifier or coerce an unexpected provider type.
        if type(vid) is not str or type(pid) is not str:
            raise RehearsalArmIdentityError("closed fixture VID/PID must be strings")
        persistent_ids = (
            (f"usb-unit:{vid}:{pid}:{raw.serial_number}",)
            if raw.serial_number is not None
            else ()
        )
        blockers = (
            ()
            if raw.serial_number is not None
            else ("SERIAL_UNIT_SERIAL_MISSING", "SERIAL_PERSISTENT_SELECTOR_MISSING")
        )
        candidates.append(
            NormalizedDeviceCandidate(
                InventoryDeviceClass.SERIAL,
                _SOURCE,
                raw.description or "",
                vid,
                pid,
                raw.serial_number,
                raw.hwid,
                persistent_ids,
                raw.port_name,
                raw.manufacturer,
                raw.product,
                raw.interface,
                blockers,
            )
        )
    return [row.to_dict() for row in sorted(candidates, key=lambda item: item.sort_key)]


def _selection_reasons(
    report: PhysicalDeviceInventoryReport | None,
    specification: dict[str, Any],
    baseline: dict[str, Any],
) -> list[str]:
    reasons = set()
    if specification["modeled_chassis_label"] != baseline["modeled_chassis_label"]:
        reasons.add("MODELED_CHASSIS_MODEL_MISMATCH")
    if report is None:
        reasons.add("INVENTORY_OUTPUT_REJECTED")
        return sorted(reasons)
    batch = report.serial_inventory
    if not batch.collection_complete:
        reasons.add("INVENTORY_COLLECTION_INCOMPLETE")
    if len(batch.candidates) != 1:
        reasons.add("EXACTLY_ONE_CANDIDATE_REQUIRED")
    if any(row.identity_blockers or not row.persistent_ids for row in batch.candidates):
        reasons.add("PERSISTENT_IDENTITY_INCOMPLETE")
    identifiers = [pid for row in batch.candidates for pid in row.persistent_ids]
    if len(set(identifiers)) != len(identifiers):
        reasons.add("PERSISTENT_IDENTITY_DUPLICATED")
    if len(batch.candidates) == 1:
        candidate = batch.candidates[0]
        selected = baseline["candidate"]
        if list(candidate.persistent_ids) != selected["persistent_ids"]:
            reasons.add("PERSISTENT_IDENTITY_CHANGED")
        if candidate.os_instance_id != selected["os_instance_id"]:
            reasons.add("OS_INSTANCE_METADATA_CHANGED")
        if candidate.ephemeral_locator != selected["ephemeral_locator_observation"]:
            reasons.add("EPHEMERAL_ALIAS_CHANGED")
        if candidate.candidate_sha256 != baseline["candidate_sha256"]:
            reasons.add("SELECTED_CANDIDATE_SNAPSHOT_CHANGED")
    rows = specification["injected_payload"]
    if len(rows) == 1 and "port_name" in rows[0]:
        if rows[0]["location"] != baseline["raw_location"]:
            reasons.add("RAW_TOPOLOGY_CHANGED")
        if rows[0]["interface"] != baseline["raw_interface"]:
            reasons.add("RAW_INTERFACE_METADATA_CHANGED")
    return sorted(reasons)


def _profile_check(value: object) -> tuple[bool, dict[str, Any]]:
    obj = _object(
        value,
        {
            "profile_path",
            "profile_utf8",
            "profile_file_sha256",
            "loader_outcome",
            "loaded_profile",
            "error",
        },
    )
    _same(obj["profile_path"], _PROFILE, "fixed profile path")
    if type(obj["profile_utf8"]) is not str:
        raise RehearsalArmIdentityError("profile source must be UTF-8 text")
    raw = obj["profile_utf8"].encode("utf-8")
    _same(
        obj["profile_file_sha256"],
        hashlib.sha256(raw).hexdigest(),
        "profile bytes hash",
    )
    document = _decode(raw)
    known = {
        "schema_version",
        "profile_id",
        "model",
        "transport",
        "port",
        "baud",
        "wire_format",
        "transmit_terminator",
        "accepted_receive_terminators",
        "rts",
        "dtr",
        "read_timeout_s",
        "write_timeout_s",
        "blind_retry",
        "auto_connect",
        "auto_initialize",
        "exclusive_owner_required",
        "identity",
        "live_access_gate",
    }
    identity = document.get("identity")
    policy = (
        set(document) == known
        and type(document.get("schema_version")) is int
        and document["schema_version"] == 1
        and document.get("model") == _MODEL
        and document.get("transport") == "usb_serial"
        and document.get("port") is None
        and type(document.get("baud")) is int
        and document["baud"] == 115200
        and document.get("wire_format") == "newline_terminated_json"
        and document.get("transmit_terminator") == "LF"
        and document.get("accepted_receive_terminators") == ["LF", "CRLF"]
        and all(
            document.get(key) is False
            for key in ("rts", "dtr", "blind_retry", "auto_connect", "auto_initialize")
        )
        and document.get("exclusive_owner_required") is True
        and type(identity) is dict
        and _canonical(identity)
        == _canonical(
            {
                "controller_usb_identity": None,
                "arm_serial_number": None,
                "firmware_revision": None,
                "state": "OPEN_BLOCKING",
            }
        )
        and type(document.get("live_access_gate")) is str
        and bool(document["live_access_gate"])
    )
    if obj["loader_outcome"] == "LOADED":
        _same(obj["error"], None, "successful profile error")
        identity = _object(document.get("identity"))
        expected = ArmConnectionProfile(
            document["profile_id"],
            document["model"],
            document["port"],
            document["baud"],
            document["read_timeout_s"],
            document["write_timeout_s"],
            identity["controller_usb_identity"],
            identity["arm_serial_number"],
            identity["firmware_revision"],
            identity["state"],
            document["auto_connect"],
            document["auto_initialize"],
            document["rts"],
            document["dtr"],
        ).to_dict()
        _same(obj["loaded_profile"], expected, "loaded profile/source relationship")
        policy = policy and expected["commissioned"] is False
    elif obj["loader_outcome"] == "REJECTED":
        _same(obj["loaded_profile"], None, "rejected profile result")
        error = _object(obj["error"], {"type", "message"})
        _same(
            error["type"], "ArmConnectionConfigurationError", "profile rejection class"
        )
        if type(error["message"]) is not str or not 0 < len(error["message"]) <= 2048:
            raise RehearsalArmIdentityError("invalid bounded loader diagnostic")
        policy = False
    else:
        raise RehearsalArmIdentityError("unknown loader outcome")
    return policy, {
        "profile_file_sha256": obj["profile_file_sha256"],
        "loader_outcome": obj["loader_outcome"],
        "model": document.get("model"),
        "configured_port": document.get("port"),
        "baud": document.get("baud"),
        "reason_codes": [] if policy else ["NOMINAL_PROFILE_POLICY_NOT_SATISFIED"],
    }


def _check(
    check_id: str, kind: str, passed: bool, observed: object, meaning: str
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "check_kind": kind,
        "passed": passed,
        "observed": observed,
        "meaning": meaning,
    }


def _derive(
    reports: object, binding: RehearsalArmIdentityBinding
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    obj = _object(reports, {"profile", "selection_baseline", "scenarios"})
    baseline = _selection_baseline()
    _same(obj["selection_baseline"], baseline, "fixed synthetic selection baseline")
    specifications = _scenarios()
    scenarios = _object(obj["scenarios"], set(specifications))
    policy, observed = _profile_check(obj["profile"])
    checks = [
        _check(
            "profile_policy",
            "NOMINAL",
            policy,
            observed,
            "reports.profile: actual fixed loader; Pro/115200, no configured live identity, no open/init/RTS/DTR/retry.",
        )
    ]
    for name, specification in specifications.items():
        row = _object(
            scenarios[name],
            {"specification", "provider_outcome", "inventory_report", "error"},
        )
        _same(row["specification"], specification, "closed fixture input")
        report = None
        consistent = True
        if row["provider_outcome"] == "RETURNED":
            _same(row["error"], None, "returned inventory error")
            report = _inventory_report(row["inventory_report"])
            consistent = list(report.blockers) == _expected_inventory_blockers(
                report.serial_inventory
            )
            if name == "unexpected_output":
                consistent = False
            else:
                consistent = consistent and _canonical(
                    [
                        candidate.to_dict()
                        for candidate in report.serial_inventory.candidates
                    ]
                ) == _canonical(_fixture_candidates(specification))
        elif row["provider_outcome"] == "REJECTED":
            _same(row["inventory_report"], None, "rejected inventory result")
            error = _object(row["error"], {"type", "message"})
            _same(
                error["type"],
                "PhysicalDeviceInventoryError",
                "inventory rejection type",
            )
            if (
                type(error["message"]) is not str
                or not 0 < len(error["message"]) <= 2048
            ):
                raise RehearsalArmIdentityError("invalid bounded inventory diagnostic")
        else:
            raise RehearsalArmIdentityError("unknown inventory outcome")
        reasons = _selection_reasons(report, specification, baseline)
        nominal = name == "nominal"
        passed = consistent and (
            not reasons
            if nominal
            else bool(reasons)
            and set(specification["expected_reason_codes"]).issubset(reasons)
        )
        # Unexpected parser failure cannot count as successful rejection of a
        # different fault (e.g. wrong model must retain a valid inventory report).
        passed = passed and (
            report is None if name == "unexpected_output" else report is not None
        )
        checks.append(
            _check(
                "nominal_inventory" if nominal else f"reject_{name}",
                "NOMINAL" if nominal else "EXPECTED_FAULT",
                passed,
                {
                    "selection_outcome": (
                        "MATCHED_SYNTHETIC_SNAPSHOT" if not reasons else "BLOCKED"
                    ),
                    "reason_codes": reasons,
                    "inventory_consistent": consistent,
                    "candidate_count": (
                        len(report.serial_inventory.candidates) if report else None
                    ),
                    "report_sha256": _hash(row),
                },
                f"reports.scenarios.{name}: "
                + (
                    "exact synthetic identity/alias/topology snapshot match only."
                    if nominal
                    else "expected fault must be rejected; this is not nominal readiness."
                ),
            )
        )
    checks.append(
        _check(
            "physical_identity_held",
            "INVARIANT",
            True,
            {
                "received_pro_identity": "PENDING",
                "firmware": "PENDING",
                "driver": "PENDING",
                "physical_authority": False,
            },
            "No received arm, firmware, boot/reset or driver qualification is derived from USB/COM metadata.",
        )
    )
    inputs = {
        "arm_profile_file_sha256": obj["profile"]["profile_file_sha256"],
        "arm_profile_report_sha256": _hash(obj["profile"]),
        "synthetic_selection_sha256": _hash(baseline),
        "synthetic_scenario_inputs_sha256": _hash(specifications),
        "synthetic_scenario_reports_sha256": _hash(scenarios),
        "static_registration_evidence_sha256": binding.static_registration_evidence_sha256,
        "predecessor_receipt_sha256": binding.predecessor_receipt_sha256,
        "predecessor_assessment_sha256": binding.predecessor_assessment_sha256,
        "predecessor_review_sha256": binding.predecessor_review_sha256,
        "camera_settings_epoch": "NOT_APPLICABLE_DEPENDENCY_ONLY",
        "physical_controller_identity": "NOT_ACQUIRED",
        "installed_firmware_identity": "NOT_ACQUIRED",
        "installed_driver_identity": "NOT_ACQUIRED",
    }
    return checks, inputs


def _outcomes(checks: list[dict[str, Any]]) -> dict[str, str]:
    nominal = all(row["passed"] for row in checks if row["check_kind"] == "NOMINAL")
    negative = all(
        row["passed"] for row in checks if row["check_kind"] == "EXPECTED_FAULT"
    )
    return {
        "nominal_outcome": "NOMINAL_CHECKS_PASSED" if nominal else "BLOCKED",
        "negative_checks_outcome": (
            "EXPECTED_FAULTS_REJECTED" if negative else "BLOCKED"
        ),
        "outcome": (
            "REHEARSAL_CHECKS_PASSED"
            if all(row["passed"] for row in checks)
            else "BLOCKED"
        ),
    }


def verify_rehearsal_arm_identity_evidence(
    payload: bytes,
    *,
    expected_binding: RehearsalArmIdentityBinding,
    expected_evidence_sha256: str | None = None,
    expected_evaluator_source_sha256: str | None = None,
) -> RehearsalArmIdentityEvidence:
    """Pure retained verification, with no file/provider/evaluator calls.

    Omitted expected hashes mean structural consistency only, NOT trusted
    admission. M1 integration must supply both hashes from authenticated receipts
    and independently verify the prerequisite lineage and current source/catalog.
    """
    if type(expected_binding) is not RehearsalArmIdentityBinding:
        raise RehearsalArmIdentityError(
            "expected binding must be the exact typed contract"
        )
    expected_binding.__post_init__()
    try:
        document = _decode(payload)
        _object(
            document,
            {
                "schema",
                "binding",
                "evaluator",
                "provenance",
                "reports",
                "report_hashes",
                "selected_inputs",
                "selected_inputs_sha256",
                "checks",
                "nominal_outcome",
                "negative_checks_outcome",
                "outcome",
                "authority",
            },
        )
        _same(document["schema"], SCHEMA, "schema")
        _same(document["binding"], expected_binding.to_dict(), "expected binding")
        _same(document["authority"], _AUTHORITY, "zero authority")
        _same(document["provenance"], _PROVENANCE, "provenance")
        evaluator = _object(document["evaluator"], {"id", "source_file_sha256"})
        _same(evaluator["id"], EVALUATOR_ID, "evaluator identity")
        _digest(evaluator["source_file_sha256"])
        if expected_evaluator_source_sha256 is not None:
            _same(
                evaluator["source_file_sha256"],
                _digest(expected_evaluator_source_sha256),
                "evaluator source",
            )
        canonical = _canonical(document)
        if expected_evidence_sha256 is not None:
            _same(
                hashlib.sha256(canonical).hexdigest(),
                _digest(expected_evidence_sha256),
                "retained evidence hash",
            )
        reports = _object(document["reports"])
        _same(
            document["report_hashes"],
            {key: _hash(value) for key, value in reports.items()},
            "report hashes",
        )
        checks, inputs = _derive(reports, expected_binding)
        _same(document["checks"], checks, "derived checks")
        _same(document["selected_inputs"], inputs, "selected input manifest")
        _same(document["selected_inputs_sha256"], _hash(inputs), "input manifest hash")
        for key, value in _outcomes(checks).items():
            _same(document[key], value, f"derived {key}")
        return RehearsalArmIdentityEvidence(canonical)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, RehearsalArmIdentityError):
            raise
        raise RehearsalArmIdentityError(
            "retained arm identity report is invalid"
        ) from exc


def _read_fixed(root: Path, relative: str) -> bytes:
    path = root / relative
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part.lstat(), "st_file_attributes", 0) & 0x400:
            raise RehearsalArmIdentityError(
                "fixed input contains link/reparse component"
            )
        if part == root:
            break
    with path.open("rb") as stream:
        raw = stream.read(MAX_EVIDENCE_BYTES + 1)
    if not 0 < len(raw) <= MAX_EVIDENCE_BYTES:
        raise RehearsalArmIdentityError("fixed input exceeds bounded read")
    return raw


def evaluate_rehearsal_arm_identity_stage(
    workspace: Path,
    binding: RehearsalArmIdentityBinding,
) -> RehearsalArmIdentityEvidence:
    """Explicit closed-fixture evaluation; no device/provider/path selection API.

    This function cannot publish, advance a stage, authorize serial access, or
    make an energy change. It uses no clock: inventory timestamps are explicitly
    fictional zero. Source/input change during evaluation fails closed.
    """
    from rocell.arm.connection import (
        ArmConnectionConfigurationError,
        load_arm_connection_profile,
    )
    from rocell.application.physical_device_inventory import (
        PhysicalDeviceInventoryError,
        compose_physical_device_inventory_report,
        inventory_serial_ports_from_provider,
    )

    if type(binding) is not RehearsalArmIdentityBinding:
        raise RehearsalArmIdentityError("binding must be the exact typed contract")
    binding.__post_init__()
    root = Path(workspace).resolve(strict=True)
    evaluator_bytes = _read_fixed(Path(__file__).parent, Path(__file__).name)
    evaluator_hash = hashlib.sha256(evaluator_bytes).hexdigest()
    raw = _read_fixed(root, _PROFILE)
    # Strict bounded parse occurs before the existing filesystem loader runs.
    _decode(raw)
    profile: dict[str, Any] = {
        "profile_path": _PROFILE,
        "profile_utf8": raw.decode("utf-8"),
        "profile_file_sha256": hashlib.sha256(raw).hexdigest(),
    }
    try:
        loaded = load_arm_connection_profile(root)
        profile.update(
            loader_outcome="LOADED", loaded_profile=loaded.to_dict(), error=None
        )
    except ArmConnectionConfigurationError as exc:
        profile.update(
            loader_outcome="REJECTED",
            loaded_profile=None,
            error={
                "type": "ArmConnectionConfigurationError",
                "message": str(exc)[:2048],
            },
        )
    scenarios: dict[str, Any] = {}
    for name, specification in _scenarios().items():
        row: dict[str, Any] = {"specification": specification}
        try:
            batch = inventory_serial_ports_from_provider(
                _ClosedEnumerator(specification)
            )
            report = compose_physical_device_inventory_report(
                platform_system="Windows",
                captured_at_unix_ns=0,
                camera_inventory=_empty_camera(),
                serial_inventory=batch,
            )
            row.update(
                provider_outcome="RETURNED",
                inventory_report=report.to_dict(),
                error=None,
            )
        except PhysicalDeviceInventoryError as exc:
            row.update(
                provider_outcome="REJECTED",
                inventory_report=None,
                error={
                    "type": "PhysicalDeviceInventoryError",
                    "message": str(exc)[:2048],
                },
            )
        scenarios[name] = row
    reports = {
        "profile": profile,
        "selection_baseline": _selection_baseline(),
        "scenarios": scenarios,
    }
    checks, inputs = _derive(reports, binding)
    document = {
        "schema": SCHEMA,
        "binding": binding.to_dict(),
        "evaluator": {"id": EVALUATOR_ID, "source_file_sha256": evaluator_hash},
        "provenance": dict(_PROVENANCE),
        "reports": reports,
        "report_hashes": {key: _hash(value) for key, value in reports.items()},
        "selected_inputs": inputs,
        "selected_inputs_sha256": _hash(inputs),
        "checks": checks,
        **_outcomes(checks),
        "authority": dict(_AUTHORITY),
    }
    if _read_fixed(root, _PROFILE) != raw:
        raise RehearsalArmIdentityError("profile changed during evaluation")
    if _read_fixed(Path(__file__).parent, Path(__file__).name) != evaluator_bytes:
        raise RehearsalArmIdentityError("evaluator source changed during evaluation")
    payload = _canonical(document)
    return verify_rehearsal_arm_identity_evidence(
        payload,
        expected_binding=binding,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        expected_evaluator_source_sha256=evaluator_hash,
    )


__all__ = [
    "SCHEMA",
    "EVALUATOR_ID",
    "MAX_EVIDENCE_BYTES",
    "RehearsalArmIdentityError",
    "RehearsalArmIdentityBinding",
    "RehearsalArmIdentityEvidence",
    "evaluate_rehearsal_arm_identity_stage",
    "verify_rehearsal_arm_identity_evidence",
]
