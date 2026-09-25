"""Bounded native arm metadata correlation, never a serial-open binding.

Only the fixed diagnostic child invokes the live collector. This module's
decoding, correlation, summaries and closed fixtures perform no OS/device I/O.
The existing stronger ReviewedControllerBinding is deliberately not created:
USB/COM/driver metadata cannot supply model, firmware, boot or power evidence.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import re
from typing import Any

from rocell.application.arm_controller_resolution import (
    ControllerMetadataSnapshot,
    ControllerNativeMetadata,
    ControllerResolutionError,
    MAX_SNAPSHOT_BYTES,
    SNAPSHOT_SCHEMA,
    decode_controller_snapshot as _decode_controller_snapshot,
)
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.physical_device_inventory import (
    DeviceInventoryBatch,
    InventoryDeviceClass,
    InventorySource,
    NormalizedDeviceCandidate,
)
from rocell.application import wizard_device_selection as selection


REPORT_SCHEMA = "rocell.wizard_native_arm_metadata.v1"
SUMMARY_SCHEMA = "rocell.wizard_native_arm_metadata_summary.v1"
MAX_REPORT_BYTES = 768 * 1024
MAX_SUMMARY_BYTES = 16 * 1024
COLLECTION_TIMEOUT_MS = 10_000
SCENARIOS = frozenset(
    {"nominal", "missing-fields", "duplicate-mapping", "changed-device", "incomplete"}
)
NATIVE_FIELDS = (
    "persistent_port_path",
    "persistent_instance_id",
    "port_name",
    "vid",
    "pid",
    "driver_provider",
    "driver_service",
    "driver_version",
    "driver_inf",
)
BLOCKER_CODES = frozenset(
    {
        "GENERIC_REVIEW_BLOCKED",
        "GENERIC_COLLECTION_INCOMPLETE",
        "NATIVE_COLLECTION_INCOMPLETE",
        "GENERIC_UNIT_NOT_PRESENT",
        "GENERIC_UNIT_AMBIGUOUS",
        "GENERIC_CANDIDATE_CHANGED",
        "GENERIC_PORT_AMBIGUOUS",
        "NATIVE_MAPPING_NOT_PRESENT",
        "NATIVE_MAPPING_AMBIGUOUS",
        "NATIVE_PROPERTIES_INCOMPLETE",
        "NATIVE_REQUIRED_FIELD_MISSING",
        "NATIVE_PORT_AMBIGUOUS",
        "NATIVE_PERSISTENT_PATH_AMBIGUOUS",
        "NATIVE_INSTANCE_AMBIGUOUS",
        "INVALID_COM_METADATA",
    }
)
LIMITATIONS = (
    "METADATA_CORRELATION_NOT_PERSISTENT_OPEN_AUTHORITY",
    "GENERIC_HWID_NOT_NATIVE_PNP_INSTANCE",
    "GENERIC_INTERFACE_DESCRIPTION_NOT_NATIVE_DRIVER_SERVICE",
    "GENERIC_UNIT_SERIAL_NOT_USB_DESCRIPTOR_VERIFICATION",
    "METADATA_SNAPSHOT_NOT_ATOMIC_COM_TO_HANDLE_BINDING",
    "RECEIVED_MODEL_FIRMWARE_BOOT_POWER_AND_DRIVER_QUALIFICATION_PENDING",
    "PHYSICAL_BACKEND_AND_RELEASE_REMAIN_HELD",
)
_FLAGS = {
    "physical_authority": False,
    "connected": False,
    "qualified": False,
    "persistent_binding": False,
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COM = re.compile(r"COM([1-9][0-9]{0,3})\Z")


class NativeArmMetadataError(ValueError):
    """A bounded fixed diagnostic error, never a native exception transcript."""

    def __init__(self, code: str = "NATIVE_ARM_METADATA_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _require(value: bool, code: str = "NATIVE_ARM_METADATA_INVALID") -> None:
    if not value:
        raise NativeArmMetadataError(code)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "NATIVE_ARM_DUPLICATE_FIELD")
        result[key] = value
    return result


def _owned(value: object, maximum: int) -> dict[str, Any]:
    """Reject excessive/recursive/untyped JSON before serialization or trust."""
    if type(value) is bytes:
        _require(0 < len(value) <= maximum, "NATIVE_ARM_METADATA_BYTE_LIMIT")
        try:
            value = json.loads(value, object_pairs_hook=_unique)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise NativeArmMetadataError() from error
    nodes, text_bytes = 0, 0

    def own(item: object, depth: int) -> Any:
        nonlocal nodes, text_bytes
        nodes += 1
        _require(nodes <= 20_000 and depth <= 12, "NATIVE_ARM_METADATA_SHAPE_LIMIT")
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _require(-(2**63) <= item <= 2**63 - 1)
            return item
        if type(item) is str:
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as error:
                raise NativeArmMetadataError() from error
            text_bytes += size
            _require(
                size <= 2048 and text_bytes <= maximum, "NATIVE_ARM_METADATA_BYTE_LIMIT"
            )
            return item
        if type(item) is list:
            _require(len(item) <= 128, "NATIVE_ARM_METADATA_SHAPE_LIMIT")
            return [own(child, depth + 1) for child in item]
        if type(item) is dict:
            _require(len(item) <= 64 and all(type(k) is str for k in item))
            return {own(k, depth + 1): own(v, depth + 1) for k, v in item.items()}
        raise NativeArmMetadataError()

    result = own(value, 0)
    _require(type(result) is dict)
    _require(len(_canonical(result)) <= maximum, "NATIVE_ARM_METADATA_BYTE_LIMIT")
    return result


def _object(value: object, fields: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields)
    assert isinstance(value, dict)
    return value


def _same(actual: object, expected: object) -> None:
    # Canonical equality rejects normalization drift and bool/int substitution.
    _require(_canonical(actual) == _canonical(expected))


def _mode(mode: object) -> str:
    _require(type(mode) is str and mode in {"physical", "rehearsal"})
    return str(mode)


def _digest(value: object) -> str:
    _require(type(value) is str and _SHA.fullmatch(value) is not None)
    return str(value)


def _codes(value: object) -> list[str]:
    _require(type(value) is list and len(value) <= 32)
    assert isinstance(value, list)
    _require(
        all(
            type(v) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", v) is not None
            for v in value
        )
        and len(set(value)) == len(value)
    )
    return value


def _batch(value: object) -> DeviceInventoryBatch:
    obj = _object(
        value,
        {
            "schema",
            "device_class",
            "source",
            "candidates",
            "collection_blockers",
            "collection_complete",
            "boundary",
        },
    )
    _require(type(obj["candidates"]) is list and len(obj["candidates"]) <= 128)
    # Reuse the existing pure generic candidate parser; unlike selection._batch,
    # this decoder retains incomplete collection evidence as a hold, not a loss.
    candidates = tuple(selection._candidate(row) for row in obj["candidates"])
    batch = DeviceInventoryBatch(
        InventoryDeviceClass(obj["device_class"]),
        InventorySource(obj["source"]),
        candidates,
        tuple(_codes(obj["collection_blockers"])),
        obj["collection_complete"],
        schema=obj["schema"],
    )
    _same(obj, batch.to_dict())
    return batch


def decode_controller_snapshot(value: object, mode: str) -> ControllerMetadataSnapshot:
    """Compatibility error domain around the shared strict snapshot decoder."""
    try:
        return _decode_controller_snapshot(value, mode)
    except ControllerResolutionError as error:
        code = (
            error.code
            if error.code
            in {
                "NATIVE_ARM_DUPLICATE_FIELD",
                "NATIVE_ARM_PROVENANCE_MISMATCH",
                "NATIVE_ARM_COLLECTION_DURATION_EXCEEDED",
            }
            else "NATIVE_ARM_METADATA_INVALID"
        )
        raise NativeArmMetadataError(code) from error


def _review(
    value: object, *, mode: str, session_id: str, source_sha256: str
) -> tuple[dict[str, Any], NormalizedDeviceCandidate, list[str]]:
    obj = _owned(value, 256 * 1024)
    _object(
        obj,
        {
            "schema",
            "device_class",
            "candidate",
            "candidate_record",
            "provenance",
            "report_sha256",
            "operation_id",
            "meaning",
            "followup_requirements",
            *set(_FLAGS),
            "review",
            "inventory_report",
        },
    )
    # Original inventory validation is pure and full; no choice tokens are minted.
    selection._bounded_document(obj["inventory_report"])
    original = selection._reconstruct(obj["inventory_report"], mode)
    _require(
        original.platform_system == "Windows", "NATIVE_ARM_WINDOWS_REVIEW_REQUIRED"
    )
    candidate = selection._candidate(obj["candidate_record"])
    _require(
        candidate.device_class is InventoryDeviceClass.SERIAL
        and candidate in original.serial_inventory.candidates
    )
    blockers = selection._identity_blockers(
        candidate, original.serial_inventory.candidates
    )
    ack = _object(
        obj["review"],
        {
            "choice_id",
            "candidate_sha256",
            "reviewer_id",
            "report_sha256",
            "operation_id",
            "status",
            *set(_FLAGS),
            "followup_requirements",
        },
    )
    choice_id = selection._identifier(ack["choice_id"])
    reviewer_id = selection._text(ack["reviewer_id"])
    operation_id = selection._identifier(obj["operation_id"])
    following = list(selection._FOLLOWUP_REQUIREMENTS)
    expected_ack = {
        "choice_id": choice_id,
        "candidate_sha256": candidate.candidate_sha256,
        "reviewer_id": reviewer_id,
        "report_sha256": original.report_sha256,
        "operation_id": operation_id,
        "status": "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION",
        **_FLAGS,
        "followup_requirements": following,
    }
    _same(ack, expected_ack)
    expected = {
        "schema": "rocell.wizard_device_candidate_review.v1",
        "device_class": "SERIAL",
        "candidate": {
            "choice_id": choice_id,
            "display_name": candidate.display_name,
            "vid": candidate.vid,
            "pid": candidate.pid,
            "unit_serial": candidate.unit_serial,
            "source": candidate.source.value,
            "identity_blockers": blockers,
            "candidate_sha256": candidate.candidate_sha256,
        },
        "candidate_record": candidate.to_dict(),
        "provenance": {
            "mode": mode,
            "session_id": session_id,
            "source_sha256": source_sha256,
            "platform_system": "Windows",
            "captured_at_unix_ns": original.captured_at_unix_ns,
            "scope": "METADATA_SNAPSHOT_ONLY",
        },
        "report_sha256": original.report_sha256,
        "operation_id": operation_id,
        "meaning": "Review acknowledges observed metadata for investigation; it does not bind, connect or qualify a device.",
        "followup_requirements": following,
        **_FLAGS,
        "review": expected_ack,
        "inventory_report": original.to_dict(),
    }
    _same(obj, expected)
    return obj, candidate, blockers


def _build_report(
    snapshot: ControllerMetadataSnapshot,
    candidate: NormalizedDeviceCandidate,
    candidate_blockers: list[str],
    acknowledgement: dict[str, Any],
    binding: dict[str, str],
) -> dict[str, Any]:
    blocked: set[str] = set()
    # Structural summary verification must not permit an omitted missing-field
    # blocker to turn an intrinsically incomplete generic identity into a match.
    if candidate_blockers or selection._identity_blockers(candidate, (candidate,)):
        blocked.add("GENERIC_REVIEW_BLOCKED")
    if not snapshot.serial_inventory.collection_complete:
        blocked.add("GENERIC_COLLECTION_INCOMPLETE")
    if snapshot.collection_blockers:
        blocked.add("NATIVE_COLLECTION_INCOMPLETE")
    com = candidate.ephemeral_locator
    matched_com = _COM.fullmatch(com or "")
    if matched_com is None or int(matched_com[1]) > 4096:
        blocked.add("INVALID_COM_METADATA")
    generic = [
        v
        for v in snapshot.serial_inventory.candidates
        if (v.vid, v.pid, v.unit_serial)
        == (candidate.vid, candidate.pid, candidate.unit_serial)
    ]
    if not generic:
        blocked.add("GENERIC_UNIT_NOT_PRESENT")
    elif len(generic) != 1:
        blocked.add("GENERIC_UNIT_AMBIGUOUS")
    elif generic[0].candidate_sha256 != candidate.candidate_sha256:
        blocked.add("GENERIC_CANDIDATE_CHANGED")
    if (
        sum(v.ephemeral_locator == com for v in snapshot.serial_inventory.candidates)
        != 1
    ):
        blocked.add("GENERIC_PORT_AMBIGUOUS")
    # This is an initial metadata correlation, not selection for serial opening.
    # Require the complete observed USB-pair AND COM relation, never COM alone.
    # Unit serial is retained only from the independent generic metadata source.
    native = [
        v
        for v in snapshot.native_observations
        if (v.vid, v.pid, v.port_name) == (candidate.vid, candidate.pid, com)
    ]
    selected = native[0] if len(native) == 1 else None
    if not native:
        blocked.add("NATIVE_MAPPING_NOT_PRESENT")
    elif len(native) != 1:
        blocked.add("NATIVE_MAPPING_AMBIGUOUS")
    native_fields = {key: "NOT_VERIFIED" for key in NATIVE_FIELDS}
    if selected is not None:
        native_fields = {
            key: "MISSING" if getattr(selected, key) is None else "OBSERVED"
            for key in NATIVE_FIELDS
        }
        if selected.blockers:
            blocked.add("NATIVE_PROPERTIES_INCOMPLETE")
        if any(value == "MISSING" for value in native_fields.values()):
            blocked.add("NATIVE_REQUIRED_FIELD_MISSING")
        if sum(v.port_name == com for v in snapshot.native_observations) != 1:
            blocked.add("NATIVE_PORT_AMBIGUOUS")
        if (
            sum(
                v.persistent_port_path == selected.persistent_port_path
                for v in snapshot.native_observations
            )
            != 1
        ):
            blocked.add("NATIVE_PERSISTENT_PATH_AMBIGUOUS")
        if (
            selected.persistent_instance_id is not None
            and sum(
                v.persistent_instance_id == selected.persistent_instance_id
                for v in snapshot.native_observations
            )
            != 1
        ):
            blocked.add("NATIVE_INSTANCE_AMBIGUOUS")
    report = {
        "schema": REPORT_SCHEMA,
        "status": "HELD" if blocked else "METADATA_CORRELATED",
        "binding": binding,
        "provenance": {
            "origin": snapshot.origin.value,
            "native_source": snapshot.native_source,
            "unit_serial_origin": "GENERIC_SERIAL_INVENTORY_NOT_USB_DESCRIPTOR",
        },
        "snapshot": json.loads(snapshot.payload()),
        "snapshot_sha256": snapshot.snapshot_sha256,
        "reviewed_generic_candidate": candidate.to_dict(),
        "reviewed_candidate_blockers": candidate_blockers,
        "generic_review": acknowledgement,
        "counts": {
            "serial_candidates": len(snapshot.serial_inventory.candidates),
            "native_observations": len(snapshot.native_observations),
            "generic_matches": len(generic),
            "native_matches": len(native),
        },
        "native_fields": native_fields,
        "native_observation_sha256": (
            None if selected is None else _hash(selected.to_dict())
        ),
        "blockers": sorted(blocked),
        "limitations": list(LIMITATIONS),
        "effects": {
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
        },
        **_FLAGS,
    }
    report["report_sha256"] = _hash(report)
    return _owned(report, MAX_REPORT_BYTES)


def correlate_native_arm_metadata(
    snapshot: object,
    generic_review: object,
    *,
    mode: str,
    session_id: str,
    source_sha256: str,
    operation_id: str,
) -> dict[str, Any]:
    """Join actual retained metadata; input context must be server-owned/current.

    Original generic review bytes remain in their original artifact. This report
    retains that full document's hash, its exact acknowledgement/candidate, and
    the full new snapshot once. It never promotes generic HWID/interface labels.
    """
    try:
        mode = _mode(mode)
        session_id = selection._identifier(session_id)
        source_sha256 = _digest(source_sha256)
        operation_id = selection._identifier(operation_id)
        checked = decode_controller_snapshot(snapshot, mode)
        review, candidate, blockers = _review(
            generic_review,
            mode=mode,
            session_id=session_id,
            source_sha256=source_sha256,
        )
        binding = {
            "mode": mode,
            "session_id": session_id,
            "source_sha256": source_sha256,
            "operation_id": operation_id,
            "generic_review_sha256": _hash(review),
            "generic_report_sha256": review["report_sha256"],
            "generic_candidate_sha256": candidate.candidate_sha256,
            "generic_inventory_operation_id": review["operation_id"],
        }
        return _build_report(checked, candidate, blockers, review["review"], binding)
    except NativeArmMetadataError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        raise NativeArmMetadataError() from error


def summarize_native_arm_metadata(report: object) -> dict[str, Any]:
    """Pure derived projection, not independent authentication of retained bytes.

    The caller must independently bind report/context hashes before publication.
    Stored generic-review hash references cannot authenticate missing originals.
    """
    try:
        obj = _owned(report, MAX_REPORT_BYTES)
        binding = _object(
            obj.get("binding"),
            {
                "mode",
                "session_id",
                "source_sha256",
                "operation_id",
                "generic_review_sha256",
                "generic_report_sha256",
                "generic_candidate_sha256",
                "generic_inventory_operation_id",
            },
        )
        mode = _mode(binding["mode"])
        for key, value in binding.items():
            if key.endswith("sha256"):
                _digest(value)
            elif key != "mode":
                selection._identifier(value)
        snapshot = decode_controller_snapshot(obj["snapshot"], mode)
        candidate = selection._candidate(obj["reviewed_generic_candidate"])
        _require(candidate.device_class is InventoryDeviceClass.SERIAL)
        expected_source = (
            InventorySource.PYSERIAL_LIST_PORTS
            if mode == "physical"
            else InventorySource.INJECTED_SERIAL_ENUMERATOR
        )
        _require(candidate.source is expected_source)
        blockers = _codes(obj["reviewed_candidate_blockers"])
        ack = _object(
            obj["generic_review"],
            {
                "choice_id",
                "candidate_sha256",
                "reviewer_id",
                "report_sha256",
                "operation_id",
                "status",
                *set(_FLAGS),
                "followup_requirements",
            },
        )
        expected_ack = {
            "choice_id": selection._identifier(ack["choice_id"]),
            "candidate_sha256": candidate.candidate_sha256,
            "reviewer_id": selection._text(ack["reviewer_id"]),
            "report_sha256": binding["generic_report_sha256"],
            "operation_id": binding["generic_inventory_operation_id"],
            "status": "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION",
            **_FLAGS,
            "followup_requirements": list(selection._FOLLOWUP_REQUIREMENTS),
        }
        _same(ack, expected_ack)
        _require(binding["generic_candidate_sha256"] == candidate.candidate_sha256)
        _same(obj, _build_report(snapshot, candidate, blockers, ack, binding))
        summary = {
            key: obj[key]
            for key in (
                "status",
                "binding",
                "provenance",
                "report_sha256",
                "snapshot_sha256",
                "counts",
                "native_fields",
                "blockers",
                *_FLAGS,
            )
        }
        summary["schema"] = SUMMARY_SCHEMA
        return _owned(summary, MAX_SUMMARY_BYTES)
    except NativeArmMetadataError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        raise NativeArmMetadataError() from error


def rehearse_native_arm_metadata_snapshot(scenario: str = "nominal") -> dict[str, Any]:
    """Closed incapable fixture using the real generic fixture/canonical parsers."""
    _require(
        type(scenario) is str and scenario in SCENARIOS, "NATIVE_ARM_UNKNOWN_SCENARIO"
    )
    from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory

    batch = _batch(rehearsal_device_inventory("nominal")["serial_inventory"])
    observed = ControllerNativeMetadata(
        r"\\?\usb#vid_fffe&pid_0002#SYNTHETIC-ARM-A#{86e0d1e0-8089-11d0-9ce4-08003e301f73}",
        r"USB\VID_FFFE&PID_0002\SYNTHETIC-ARM-A",
        "COM91",
        "fffe",
        "0002",
        "SYNTHETIC provider - not received driver",
        "synthetic-serial",
        "0.0.synthetic",
        "synthetic-not-installed.inf",
    )
    rows: tuple[ControllerNativeMetadata, ...] = (observed,)
    collection: tuple[str, ...] = ()
    if scenario == "missing-fields":
        rows = (
            replace(
                observed,
                driver_version=None,
                blockers=("NATIVE_UNOBSERVED_DRIVER_VERSION",),
            ),
        )
    elif scenario == "duplicate-mapping":
        rows = (
            observed,
            replace(
                observed, persistent_port_path=observed.persistent_port_path + "-alias"
            ),
        )
    elif scenario == "changed-device":
        changed = replace(batch.candidates[0], unit_serial="SYNTHETIC-ARM-CHANGED")
        batch = replace(batch, candidates=(changed,))
        rows = (replace(observed, persistent_instance_id=r"USB\SYNTHETIC-ARM-CHANGED"),)
    elif scenario == "incomplete":
        collection = ("NATIVE_INTERFACE_LIST_CHANGED_DURING_ACQUISITION",)
        batch = replace(
            batch,
            collection_complete=False,
            collection_blockers=("SYNTHETIC_ENUMERATION_INCOMPLETE",),
        )
    result = ControllerMetadataSnapshot(
        batch,
        rows,
        EvidenceOrigin.SYNTHETIC_REHEARSAL,
        "INJECTED_CM_METADATA",
        1,
        2,
        collection,  # Deliberate fixture times, not host observation times.
    )
    return json.loads(decode_controller_snapshot(result, "rehearsal").payload())
