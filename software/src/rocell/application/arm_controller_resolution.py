"""Exact metadata-only callback for the arm worker; never an open permission.

Generic serial inventory is deliberately weak: its HWID is not a Windows PnP
instance and its interface description is not a driver service. This join
requires separately observed native fields and never fills gaps from a review.
The existing physical worker hold remains in force before this callback runs.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from threading import Event, RLock
import time
from typing import Any, Callable, cast

from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    UsbDriverIdentity,
)
from rocell.application.physical_device_inventory import (
    DeviceInventoryBatch,
    InventoryDeviceClass,
    InventorySource,
    NormalizedDeviceCandidate,
)
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackCampaignResult,
    ArmFeedbackOutcome,
    ArmFeedbackWorkerError,
    ReviewedControllerBinding,
)


SNAPSHOT_SCHEMA = "rocell.arm_controller_metadata_snapshot.v1"
RESOLUTION_SCHEMA = "rocell.arm_controller_metadata_resolution.v1"
MAX_CANDIDATES = 128
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_RESOLUTION_BYTES = 32 * 1024
TRACE_SCHEMA = "rocell.arm_controller_resolution_trace.v1"
TRACE_SUMMARY_SCHEMA = "rocell.arm_controller_resolution_trace_summary.v1"
MAX_TRACE_BYTES = 16 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_NATIVE_FIELDS = (
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
TRACE_ERROR_CODES = frozenset(
    {
        "REVIEWED_CONTROLLER_CHANGED",
        "CONTROLLER_RESOLUTION_CANCELLED",
        "CONTROLLER_RESOLUTION_DEADLINE_OR_CLOCK",
        "CONTROLLER_METADATA_NOT_FRESH",
        "CONTROLLER_METADATA_HELD",
        "INVALID_CONTROLLER_METADATA",
        "CONTROLLER_METADATA_BYTE_LIMIT",
        "CONTROLLER_METADATA_ACQUISITION_FAILED",
        "CONTROLLER_RESOLUTION_INTERRUPTED",
        "CM_PROPERTY_STRING_INVALID",
        "CM_PROPERTY_TYPE_OR_SIZE_INVALID",
        "CM_LIST_INVALID",
        "CM_LIST_AMBIGUOUS_OR_OVER_LIMIT",
        "CM_LIST_CHANGED",
    }
)
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
_HEX = re.compile(r"[0-9a-f]{4}\Z")
_LIMITATIONS = (
    "METADATA_SNAPSHOT_NOT_ATOMIC_COM_TO_HANDLE_BINDING",
    "GENERIC_UNIT_SERIAL_NOT_USB_DESCRIPTOR_VERIFICATION",
    "ARM_MODEL_FIRMWARE_BOOT_AND_POWER_NOT_OBSERVED",
    "PHYSICAL_BACKEND_AND_RELEASE_REMAIN_HELD",
)


class ControllerResolutionError(ArmFeedbackWorkerError):
    """Safe fixed error codes cross the existing worker callback boundary."""


def _require(condition: bool, code: str = "INVALID_CONTROLLER_METADATA") -> None:
    if not condition:
        raise ControllerResolutionError(code, "metadata-only controller check refused")


def _text(value: Any, *, maximum: int = 512, optional: bool = False) -> None:
    if value is None and optional:
        return
    try:
        size = len(value.encode("utf-8")) if type(value) is str else maximum + 1
    except UnicodeError as error:
        raise ControllerResolutionError(
            "INVALID_CONTROLLER_METADATA", "invalid Unicode metadata"
        ) from error
    _require(
        type(value) is str
        and bool(value)
        and value.strip() == value
        and size <= maximum
        and all(ord(c) >= 32 and ord(c) != 127 for c in value)
    )


def _observed_text(value: str | None) -> str:
    _text(value)
    return cast(str, value)


def _codes(values: Any) -> None:
    _require(type(values) is tuple and len(values) <= 32)
    _require(
        all(type(v) is str and _CODE.fullmatch(v) is not None for v in values)
        and len(set(values)) == len(values)
    )


def _json(value: Any, maximum: int) -> bytes:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ControllerResolutionError(
            "INVALID_CONTROLLER_METADATA", "bounded metadata encoding refused"
        ) from error
    _require(len(payload) <= maximum, "CONTROLLER_METADATA_BYTE_LIMIT")
    return payload


def _hash(value: Any, maximum: int = MAX_SNAPSHOT_BYTES) -> str:
    return hashlib.sha256(_json(value, maximum)).hexdigest()


def _object(value: Any, fields: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields)
    return cast(dict[str, Any], value)


def _owned_document(value: Any, maximum: int) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in pairs:
            _require(key not in result, "NATIVE_ARM_DUPLICATE_FIELD")
            result[key] = child
        return result

    if type(value) is bytes:
        _require(0 < len(value) <= maximum)
        value = json.loads(value, object_pairs_hook=unique)
    nodes = 0

    def own(child: Any, depth: int = 0) -> Any:
        nonlocal nodes
        nodes += 1
        _require(nodes <= 20000 and depth <= 12)
        if child is None or type(child) is bool:
            return child
        if type(child) is int:
            _require(-(2**63) <= child <= 2**63 - 1)
            return child
        if type(child) is str:
            _require(len(child.encode("utf-8")) <= 2048)
            return child
        if type(child) is list:
            _require(len(child) <= 128)
            return [own(v, depth + 1) for v in child]
        _require(type(child) is dict and len(child) <= 64)
        _require(all(type(k) is str for k in child))
        return {own(k, depth + 1): own(v, depth + 1) for k, v in child.items()}

    result = own(value)
    _require(type(result) is dict)
    _json(result, maximum)
    return cast(dict[str, Any], result)


def _array(value: Any, maximum: int) -> list[Any]:
    _require(type(value) is list and len(value) <= maximum)
    return cast(list[Any], value)


def _snapshot_candidate(value: Any) -> NormalizedDeviceCandidate:
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
    candidate = NormalizedDeviceCandidate(
        device_class=InventoryDeviceClass(obj["device_class"]),
        source=InventorySource(obj["source"]),
        display_name=obj["display_name"],
        vid=usb["vid"],
        pid=usb["pid"],
        unit_serial=usb["unit_serial"],
        os_instance_id=obj["os_instance_id"],
        persistent_ids=tuple(_array(obj["persistent_ids"], 8)),
        ephemeral_locator=obj["ephemeral_locator_observation"],
        manufacturer=obj["manufacturer"],
        product=obj["product"],
        driver_service=obj["driver_service"],
        identity_blockers=tuple(_array(obj["identity_blockers"], 32)),
    )
    _require(
        _json(obj, MAX_SNAPSHOT_BYTES) == _json(candidate.to_dict(), MAX_SNAPSHOT_BYTES)
    )
    return candidate


def decode_controller_snapshot(value: object, mode: str) -> ControllerMetadataSnapshot:
    """Single strict snapshot decoder shared by wizard IPC and owned evidence.

    Incomplete collections remain valid observations, not accepted identities.
    This function never imports a provider or reads files or devices.
    """
    try:
        _require(type(mode) is str and mode in {"physical", "rehearsal"})
        if type(value) is ControllerMetadataSnapshot:
            value = value.payload()
        obj = _owned_document(value, MAX_SNAPSHOT_BYTES)
        _object(
            obj,
            {
                "schema",
                "origin",
                "native_source",
                "serial_inventory",
                "native_observations",
                "started_monotonic_ns",
                "finished_monotonic_ns",
                "collection_blockers",
                "physical_authority",
            },
        )
        _require(
            obj["schema"] == SNAPSHOT_SCHEMA and obj["physical_authority"] is False
        )
        raw_batch = _object(
            obj["serial_inventory"],
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
        batch = DeviceInventoryBatch(
            InventoryDeviceClass(raw_batch["device_class"]),
            InventorySource(raw_batch["source"]),
            tuple(_snapshot_candidate(v) for v in _array(raw_batch["candidates"], 128)),
            tuple(_array(raw_batch["collection_blockers"], 32)),
            raw_batch["collection_complete"],
            schema=raw_batch["schema"],
        )
        _require(
            _json(raw_batch, MAX_SNAPSHOT_BYTES)
            == _json(batch.to_dict(), MAX_SNAPSHOT_BYTES)
        )
        native = []
        for raw in _array(obj["native_observations"], 128):
            row = _object(raw, {*_NATIVE_FIELDS, "blockers"})
            native.append(
                ControllerNativeMetadata(
                    **{k: row[k] for k in _NATIVE_FIELDS},
                    blockers=tuple(_array(row["blockers"], 32)),
                )
            )
        snapshot = ControllerMetadataSnapshot(
            batch,
            tuple(native),
            EvidenceOrigin(obj["origin"]),
            obj["native_source"],
            obj["started_monotonic_ns"],
            obj["finished_monotonic_ns"],
            tuple(_array(obj["collection_blockers"], 32)),
        )
        _require(
            snapshot.origin
            is (
                EvidenceOrigin.PHYSICAL_OBSERVATION
                if mode == "physical"
                else EvidenceOrigin.SYNTHETIC_REHEARSAL
            ),
            "NATIVE_ARM_PROVENANCE_MISMATCH",
        )
        _require(
            snapshot.finished_monotonic_ns - snapshot.started_monotonic_ns
            < 10_000_000_000,
            "NATIVE_ARM_COLLECTION_DURATION_EXCEEDED",
        )
        _require(_json(obj, MAX_SNAPSHOT_BYTES) == snapshot.payload())
        return snapshot
    except ControllerResolutionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
        RecursionError,
        UnicodeError,
    ) as error:
        raise ControllerResolutionError(
            "INVALID_CONTROLLER_METADATA", "snapshot decoding refused"
        ) from error


@dataclass(frozen=True, slots=True)
class ControllerNativeMetadata:
    """Native interface/node observations, including explicit unavailable data.

    Unit serial is deliberately absent: the current Windows COM property set
    does not establish a USB string descriptor. The independent generic batch
    retains that metadata claim with its own provenance.
    """

    persistent_port_path: str
    persistent_instance_id: str | None
    port_name: str | None
    vid: str | None
    pid: str | None
    driver_provider: str | None
    driver_service: str | None
    driver_version: str | None
    driver_inf: str | None
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.persistent_port_path)
        _require(
            self.persistent_port_path.startswith("\\\\?\\")
            and len(self.persistent_port_path) >= 16,
            "NATIVE_INTERFACE_PATH_REQUIRED",
        )
        for field in (
            "persistent_instance_id",
            "port_name",
            "driver_provider",
            "driver_service",
            "driver_version",
            "driver_inf",
        ):
            _text(getattr(self, field), optional=True)
        for value in (self.vid, self.pid):
            _require(
                value is None
                or type(value) is str
                and _HEX.fullmatch(value) is not None
            )
        _codes(self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_batch(batch: DeviceInventoryBatch) -> None:
    _require(type(batch) is DeviceInventoryBatch)
    _require(batch.device_class is InventoryDeviceClass.SERIAL)
    _require(
        type(batch.candidates) is tuple and len(batch.candidates) <= MAX_CANDIDATES
    )
    _codes(batch.collection_blockers)
    for item in batch.candidates:
        _require(type(item) is NormalizedDeviceCandidate)
        _codes(item.identity_blockers)
        # Reconstruct the existing contract but reject any normalization drift.
        restored = NormalizedDeviceCandidate(**asdict(item))
        _require(restored == item)
    _require(DeviceInventoryBatch(**asdict_without_candidates(batch)) == batch)


def asdict_without_candidates(batch: DeviceInventoryBatch) -> dict[str, Any]:
    """Keep the original closed nested types while rechecking their container."""
    return {
        "device_class": batch.device_class,
        "source": batch.source,
        "candidates": batch.candidates,
        "collection_blockers": batch.collection_blockers,
        "collection_complete": batch.collection_complete,
        "schema": batch.schema,
        "device_ports_opened": batch.device_ports_opened,
        "selection_performed": batch.selection_performed,
    }


@dataclass(frozen=True, slots=True)
class ControllerMetadataSnapshot:
    serial_inventory: DeviceInventoryBatch
    native_observations: tuple[ControllerNativeMetadata, ...]
    origin: EvidenceOrigin
    native_source: str
    started_monotonic_ns: int
    finished_monotonic_ns: int
    collection_blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_batch(self.serial_inventory)
        _require(type(self.origin) is EvidenceOrigin)
        _require(
            (
                self.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
                and self.native_source == "INJECTED_CM_METADATA"
                and self.serial_inventory.source
                is InventorySource.INJECTED_SERIAL_ENUMERATOR
            )
            or (
                self.origin is EvidenceOrigin.PHYSICAL_OBSERVATION
                and self.native_source == "WINDOWS_CM_METADATA"
                and self.serial_inventory.source is InventorySource.PYSERIAL_LIST_PORTS
            ),
            "CONTROLLER_METADATA_PROVENANCE_MISMATCH",
        )
        _require(
            type(self.native_observations) is tuple
            and len(self.native_observations) <= MAX_CANDIDATES
        )
        for item in self.native_observations:
            _require(type(item) is ControllerNativeMetadata)
            item.__post_init__()
        for value in (self.started_monotonic_ns, self.finished_monotonic_ns):
            _require(type(value) is int and 0 < value <= 2**63 - 1)
        _require(self.started_monotonic_ns <= self.finished_monotonic_ns)
        _codes(self.collection_blockers)
        self.payload()

    def payload(self) -> bytes:
        return _json(
            {
                "schema": SNAPSHOT_SCHEMA,
                "origin": self.origin.value,
                "native_source": self.native_source,
                "serial_inventory": self.serial_inventory.to_dict(),
                "native_observations": [v.to_dict() for v in self.native_observations],
                "started_monotonic_ns": self.started_monotonic_ns,
                "finished_monotonic_ns": self.finished_monotonic_ns,
                "collection_blockers": self.collection_blockers,
                "physical_authority": False,
            },
            MAX_SNAPSHOT_BYTES,
        )

    @property
    def snapshot_sha256(self) -> str:
        return hashlib.sha256(self.payload()).hexdigest()


def _binding(binding: ReviewedControllerBinding) -> ReviewedControllerBinding:
    _require(
        type(binding) is ReviewedControllerBinding, "EXACT_REVIEWED_CONTROLLER_REQUIRED"
    )
    _require(type(binding.identity) is RoArmUsbSerialIdentity)
    _require(type(binding.identity.driver) is UsbDriverIdentity)
    identity = binding.identity
    restored = RoArmUsbSerialIdentity(
        identity.vid,
        identity.pid,
        identity.unit_serial,
        identity.persistent_instance_id,
        identity.persistent_port_path,
        identity.port_name,
        UsbDriverIdentity(**identity.driver.to_dict()),
    )
    _require(restored == identity, "REVIEWED_CONTROLLER_CHANGED")
    return ReviewedControllerBinding(
        restored,
        binding.identity_receipt_sha256,
        binding.arm_model_receipt_sha256,
        binding.installed_firmware_evidence_sha256,
        binding.boot_policy_evidence_sha256,
        binding.serial_profile_sha256,
        binding.origin,
    )


@dataclass(frozen=True, slots=True)
class ControllerResolution:
    """Small immutable comparison, not a persistent binding or stage receipt."""

    payload: bytes
    identity: RoArmUsbSerialIdentity | None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return {
            key: value[key]
            for key in (
                "schema",
                "status",
                "reviewed_binding_sha256",
                "snapshot_sha256",
                "serial_inventory_sha256",
                "native_source",
                "origin",
                "generic_candidate_sha256",
                "native_observation_sha256",
                "observed_identity_sha256",
                "blockers",
                "limitations",
                "physical_authority",
                "arm_connected",
                "qualified",
            )
        } | {"resolution_sha256": self.sha256}


def resolve_controller_metadata(
    reviewed: ReviewedControllerBinding, snapshot: ControllerMetadataSnapshot
) -> ControllerResolution:
    """Pure persistent-pair selection; COM and USB fields are comparisons only."""
    binding = _binding(reviewed)
    _require(type(snapshot) is ControllerMetadataSnapshot)
    snapshot.__post_init__()
    expected = binding.identity
    blockers: list[str] = []
    if snapshot.origin is not binding.origin:
        blockers.append("CONTROLLER_METADATA_PROVENANCE_MISMATCH")
    if (
        snapshot.collection_blockers
        or not snapshot.serial_inventory.collection_complete
    ):
        blockers.append("CONTROLLER_METADATA_COLLECTION_INCOMPLETE")
    # Never choose one duplicate using ordering, display names, COM or USB IDs.
    related = [
        v
        for v in snapshot.native_observations
        if v.persistent_instance_id == expected.persistent_instance_id
        or v.persistent_port_path == expected.persistent_port_path
    ]
    selected = related[0] if len(related) == 1 else None
    if not related:
        blockers.append("REVIEWED_NATIVE_INTERFACE_NOT_PRESENT")
    elif len(related) != 1:
        blockers.append("NATIVE_INTERFACE_IDENTITY_AMBIGUOUS")
    if selected is not None:
        if (
            selected.persistent_instance_id != expected.persistent_instance_id
            or selected.persistent_port_path != expected.persistent_port_path
        ):
            blockers.append("NATIVE_PERSISTENT_MAPPING_CHANGED")
        if selected.blockers:
            blockers.append("NATIVE_PROPERTIES_INCOMPLETE")
        if any(
            getattr(selected, k) is None
            for k in (
                "persistent_instance_id",
                "port_name",
                "vid",
                "pid",
                "driver_provider",
                "driver_service",
                "driver_version",
                "driver_inf",
            )
        ):
            blockers.append("REQUIRED_NATIVE_PROPERTY_UNOBSERVED")
        if selected.port_name != expected.port_name:
            blockers.append("NATIVE_COM_MAPPING_CHANGED")
        if (selected.vid, selected.pid) != (expected.vid, expected.pid):
            blockers.append("NATIVE_USB_METADATA_CHANGED")
        if (
            sum(v.port_name == expected.port_name for v in snapshot.native_observations)
            != 1
        ):
            blockers.append("NATIVE_COM_MAPPING_AMBIGUOUS")
    candidates = [
        v
        for v in snapshot.serial_inventory.candidates
        if (v.vid, v.pid, v.unit_serial)
        == (expected.vid, expected.pid, expected.unit_serial)
    ]
    candidate = candidates[0] if len(candidates) == 1 else None
    if not candidates:
        blockers.append("GENERIC_USB_UNIT_NOT_PRESENT")
    elif len(candidates) != 1:
        blockers.append("GENERIC_USB_UNIT_AMBIGUOUS")
    if candidate is not None:
        if candidate.identity_blockers:
            blockers.append("GENERIC_IDENTITY_BLOCKED")
        if candidate.ephemeral_locator != expected.port_name:
            blockers.append("GENERIC_COM_MAPPING_CHANGED")
        if (
            sum(
                v.ephemeral_locator == expected.port_name
                for v in snapshot.serial_inventory.candidates
            )
            != 1
        ):
            blockers.append("GENERIC_COM_MAPPING_AMBIGUOUS")
    observed: RoArmUsbSerialIdentity | None = None
    if not blockers and selected is not None and candidate is not None:
        assert all(
            type(v) is str
            for v in (
                selected.vid,
                selected.pid,
                selected.persistent_instance_id,
                selected.port_name,
                candidate.unit_serial,
                selected.driver_provider,
                selected.driver_service,
                selected.driver_version,
                selected.driver_inf,
            )
        )
        # Only actual snapshot fields populate the callback identity. The type's
        # nominal product/controller constants are not observed model/firmware.
        observed = RoArmUsbSerialIdentity(
            _observed_text(selected.vid),
            _observed_text(selected.pid),
            _observed_text(candidate.unit_serial),
            _observed_text(selected.persistent_instance_id),
            selected.persistent_port_path,
            _observed_text(selected.port_name),
            UsbDriverIdentity(
                _observed_text(selected.driver_provider),
                _observed_text(selected.driver_service),
                _observed_text(selected.driver_version),
                _observed_text(selected.driver_inf),
            ),
        )
        if observed != expected:
            blockers.append("CONTROLLER_DRIVER_OR_IDENTITY_CHANGED")
            observed = None
    payload = _json(
        {
            "schema": RESOLUTION_SCHEMA,
            "status": "MATCHED_METADATA_ONLY" if observed is not None else "HELD",
            "reviewed_binding_sha256": binding.binding_sha256,
            "snapshot_sha256": snapshot.snapshot_sha256,
            "serial_inventory_sha256": snapshot.serial_inventory.batch_sha256,
            "native_source": snapshot.native_source,
            "origin": snapshot.origin.value,
            "generic_candidate_sha256": (
                None if candidate is None else candidate.candidate_sha256
            ),
            "native_observation_sha256": (
                None if selected is None else _hash(selected.to_dict())
            ),
            "observed_identity_sha256": (
                None if observed is None else observed.identity_sha256
            ),
            "generic_metadata": None if candidate is None else candidate.to_dict(),
            "native_metadata": None if selected is None else selected.to_dict(),
            "unit_serial_origin": "GENERIC_SERIAL_INVENTORY_NOT_USB_DESCRIPTOR",
            "blockers": sorted(set(blockers)),
            "limitations": _LIMITATIONS,
            "physical_authority": False,
            "arm_connected": False,
            "qualified": False,
        },
        MAX_RESOLUTION_BYTES,
    )
    return ControllerResolution(payload, observed)


def _trace_status(attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return "NOT_ATTEMPTED"
    if any(row["status"] == "HELD" for row in attempts):
        return "HELD"
    return "PRE_WRITE_MATCHED" if len(attempts) == 2 else "PRE_OPEN_MATCHED"


def _trace_document(value: Any) -> dict[str, Any]:
    obj = _owned_document(value, MAX_TRACE_BYTES)
    _object(
        obj,
        {
            "schema",
            "reviewed_binding_sha256",
            "origin",
            "deadline_monotonic_ns",
            "attempts",
            "physical_authority",
            "arm_connected",
            "qualified",
            "limitations",
        },
    )
    _require(obj["schema"] == TRACE_SCHEMA)
    _require(
        type(obj["reviewed_binding_sha256"]) is str
        and _SHA.fullmatch(obj["reviewed_binding_sha256"]) is not None
    )
    _require(obj["origin"] in {v.value for v in EvidenceOrigin})
    _require(
        type(obj["deadline_monotonic_ns"]) is int
        and 0 < obj["deadline_monotonic_ns"] <= 2**63 - 1
    )
    _require(
        all(
            obj[k] is False
            for k in ("physical_authority", "arm_connected", "qualified")
        )
    )
    _require(obj["limitations"] == list(_LIMITATIONS))
    for index, row in enumerate(_array(obj["attempts"], 2)):
        _object(
            row,
            {
                "phase",
                "status",
                "started_monotonic_ns",
                "finished_monotonic_ns",
                "snapshot",
                "snapshot_sha256",
                "resolution",
                "resolution_sha256",
                "error_code",
            },
        )
        _require(row["phase"] == ("PRE_OPEN", "PRE_WRITE")[index])
        _require(row["status"] in {"MATCHED_METADATA_ONLY", "HELD"})
        for key in ("started_monotonic_ns", "finished_monotonic_ns"):
            _require(
                row[key] is None or type(row[key]) is int and 0 < row[key] <= 2**63 - 1
            )
        for name in ("snapshot", "resolution"):
            raw, digest = row[name], row[name + "_sha256"]
            if raw is None:
                _require(digest is None)
            else:
                _require(
                    type(raw) is dict and type(digest) is str and _hash(raw) == digest
                )
        _require(row["resolution"] is None or row["snapshot"] is not None)
        if row["status"] == "MATCHED_METADATA_ONLY":
            _require(
                row["snapshot"] is not None
                and row["resolution"] is not None
                and row["error_code"] is None
            )
        else:
            _require(
                type(row["error_code"]) is str
                and row["error_code"] in TRACE_ERROR_CODES
            )
    return obj


@dataclass(frozen=True, slots=True)
class ControllerResolutionTrace:
    """Complete immutable observations, including rejected late acquisitions."""

    payload: bytes

    def __post_init__(self) -> None:
        _require(type(self.payload) is bytes)
        try:
            obj = _trace_document(self.payload)
            _require(self.payload == _json(obj, MAX_TRACE_BYTES))
        except ControllerResolutionError:
            raise
        except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as error:
            raise ControllerResolutionError(
                "INVALID_CONTROLLER_METADATA", "trace decoding refused"
            ) from error

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        obj = self.to_dict()
        return {
            "schema": TRACE_SUMMARY_SCHEMA,
            "trace_sha256": self.sha256,
            "reviewed_binding_sha256": obj["reviewed_binding_sha256"],
            "origin": obj["origin"],
            "attempt_count": len(obj["attempts"]),
            "status": _trace_status(obj["attempts"]),
            "attempts": [
                {
                    k: row[k]
                    for k in (
                        "phase",
                        "status",
                        "snapshot_sha256",
                        "resolution_sha256",
                        "error_code",
                    )
                }
                for row in obj["attempts"]
            ],
            "physical_authority": False,
            "arm_connected": False,
            "qualified": False,
            "limitations": list(_LIMITATIONS),
        }


def verify_controller_resolution_trace(
    value: bytes | ControllerResolutionTrace,
    *,
    reviewed: ReviewedControllerBinding,
    expected_deadline_ns: int,
    expected_trace_sha256: str,
    expected_result: ArmFeedbackCampaignResult | None = None,
) -> ControllerResolutionTrace:
    """Recheck retained comparisons/counters only; no acquisition, clock or I/O."""
    binding = _binding(reviewed)
    _require(type(value) in {bytes, ControllerResolutionTrace})
    trace = ControllerResolutionTrace(
        value if isinstance(value, bytes) else value.payload
    )
    _require(
        type(expected_trace_sha256) is str and trace.sha256 == expected_trace_sha256
    )
    _require(
        type(expected_deadline_ns) is int and 0 < expected_deadline_ns <= 2**63 - 1
    )
    obj = trace.to_dict()
    _require(
        obj["reviewed_binding_sha256"] == binding.binding_sha256
        and obj["origin"] == binding.origin.value
        and obj["deadline_monotonic_ns"] == expected_deadline_ns
    )
    mode = (
        "rehearsal"
        if binding.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
        else "physical"
    )
    for row in obj["attempts"]:
        snapshot = None
        if row["snapshot"] is not None:
            snapshot = decode_controller_snapshot(row["snapshot"], mode)
            _require(snapshot.snapshot_sha256 == row["snapshot_sha256"])
        if row["resolution"] is not None:
            assert snapshot is not None
            resolution = resolve_controller_metadata(binding, snapshot)
            _require(
                resolution.sha256 == row["resolution_sha256"]
                and resolution.payload == _json(row["resolution"], MAX_RESOLUTION_BYTES)
            )
        if row["status"] == "MATCHED_METADATA_ONLY":
            assert snapshot is not None
            _require(row["resolution"]["status"] == "MATCHED_METADATA_ONLY")
            start, end = row["started_monotonic_ns"], row["finished_monotonic_ns"]
            _require(
                type(start) is int
                and type(end) is int
                and 0
                < start
                <= snapshot.started_monotonic_ns
                <= snapshot.finished_monotonic_ns
                <= end
                < expected_deadline_ns
            )
        if row["error_code"] == "CONTROLLER_METADATA_HELD":
            _require(
                row["resolution"] is not None and row["resolution"]["status"] == "HELD"
            )
    if len(obj["attempts"]) == 2:
        first, second = obj["attempts"]
        if second["started_monotonic_ns"] is not None:
            _require(
                first["finished_monotonic_ns"] is not None
                and first["finished_monotonic_ns"] <= second["started_monotonic_ns"]
            )
    if expected_result is not None:
        _require(type(expected_result) is ArmFeedbackCampaignResult)
        _require(expected_result.origin is binding.origin)
        attempts = obj["attempts"]
        counts = expected_result.api_counts
        _require(
            type(counts.identity_checks) is int
            and len(attempts) == counts.identity_checks
        )
        _require(len(attempts) < 2 or attempts[0]["status"] == "MATCHED_METADATA_ONLY")
        if counts.open_attempts:
            _require(
                bool(attempts) and attempts[0]["status"] == "MATCHED_METADATA_ONLY"
            )
        if expected_result.opened_monotonic_ns is not None:
            _require(
                bool(attempts)
                and attempts[0]["finished_monotonic_ns"] is not None
                and attempts[0]["finished_monotonic_ns"]
                <= expected_result.opened_monotonic_ns
            )
        if counts.write_attempts:
            _require(
                len(attempts) == 2 and attempts[1]["status"] == "MATCHED_METADATA_ONLY"
            )
        if len(attempts) == 2:
            _require(counts.opens_confirmed == 1)
            if attempts[1]["started_monotonic_ns"] is not None:
                _require(
                    expected_result.opened_monotonic_ns is not None
                    and expected_result.opened_monotonic_ns
                    <= attempts[1]["started_monotonic_ns"]
                )
            if expected_result.feedback_receipt is not None:
                _require(
                    attempts[1]["finished_monotonic_ns"] is not None
                    and attempts[1]["finished_monotonic_ns"]
                    <= expected_result.feedback_receipt.timing.request_write_started_monotonic_ns
                )
        if expected_result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC:
            _require(_trace_status(attempts) == "PRE_WRITE_MATCHED")
        for row in attempts:
            start, end = row["started_monotonic_ns"], row["finished_monotonic_ns"]
            if row["error_code"] != "CONTROLLER_RESOLUTION_DEADLINE_OR_CLOCK":
                if start is not None and end is not None:
                    _require(0 <= end - start <= expected_result.elapsed_ns)
                if end is not None and expected_result.closed_monotonic_ns is not None:
                    _require(end <= expected_result.closed_monotonic_ns)
        if attempts and attempts[-1]["status"] == "HELD":
            _require(
                expected_result.outcome is not ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
            )
            _require(expected_result.primary_error is not None)
            assert expected_result.primary_error is not None
            _require(
                expected_result.primary_error.phase
                == (
                    "IDENTITY_BEFORE_OPEN"
                    if len(attempts) == 1
                    else "IDENTITY_BEFORE_WRITE"
                )
            )
            if attempts[-1]["error_code"] not in {
                "CONTROLLER_METADATA_ACQUISITION_FAILED",
                "CONTROLLER_RESOLUTION_INTERRUPTED",
            }:
                _require(
                    expected_result.primary_error.code == attempts[-1]["error_code"]
                )
    return trace


class ExplicitArmControllerResolver:
    """Drop-in worker callback; at most two fresh acquisitions, no implicit I/O.

    The supplied acquisition function is trusted internal code, not a browser
    field or authority grant. Deadline checks cannot interrupt a stalled native
    call: the eventual physical process supervisor remains separately required.
    """

    def __init__(
        self,
        reviewed: ReviewedControllerBinding,
        acquire_snapshot: Callable[[], ControllerMetadataSnapshot],
        *,
        deadline_ns: int,
        cancellation: Event,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._reviewed = _binding(reviewed)
        self._binding_bytes = _json(self._reviewed.to_dict(), MAX_RESOLUTION_BYTES)
        _require(callable(acquire_snapshot) and callable(monotonic_ns))
        _require(type(cancellation) is Event)
        _require(type(deadline_ns) is int and 0 < deadline_ns <= 2**63 - 1)
        self._acquire, self._clock = acquire_snapshot, monotonic_ns
        self._deadline, self._cancellation = deadline_ns, cancellation
        self._calls, self._last_now = 0, 0
        self._latest: ControllerResolution | None = None
        self._attempts: list[dict[str, Any]] = []
        self._observed_now: int | None = None
        self._lock = RLock()

    def retained_trace(self) -> ControllerResolutionTrace:
        with self._lock:
            return ControllerResolutionTrace(
                _json(
                    {
                        "schema": TRACE_SCHEMA,
                        "reviewed_binding_sha256": self._reviewed.binding_sha256,
                        "origin": self._reviewed.origin.value,
                        "deadline_monotonic_ns": self._deadline,
                        "attempts": self._attempts,
                        "physical_authority": False,
                        "arm_connected": False,
                        "qualified": False,
                        "limitations": _LIMITATIONS,
                    },
                    MAX_TRACE_BYTES,
                )
            )

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "acquisition_attempts": self._calls,
                "latest": None if self._latest is None else self._latest.safe_summary(),
                "hardware_accessed_by_status": False,
                "physical_authority": False,
                "arm_connected": False,
                "qualified": False,
            }

    def _checkpoint(self) -> int:
        self._observed_now = None
        _require(not self._cancellation.is_set(), "CONTROLLER_RESOLUTION_CANCELLED")
        now = self._clock()
        self._observed_now = now if type(now) is int and 0 < now <= 2**63 - 1 else None
        _require(
            type(now) is int and 0 < now and self._last_now <= now < self._deadline,
            "CONTROLLER_RESOLUTION_DEADLINE_OR_CLOCK",
        )
        self._last_now = now
        return now

    def __call__(self, expected: RoArmUsbSerialIdentity, /) -> RoArmUsbSerialIdentity:
        with self._lock:
            _require(self._calls < 2, "CONTROLLER_RESOLUTION_CALL_LIMIT")
            self._calls += 1
            self._latest = None
            self._observed_now = None
            row: dict[str, Any] = {
                "phase": ("PRE_OPEN", "PRE_WRITE")[self._calls - 1],
                "status": "HELD",
                "started_monotonic_ns": None,
                "finished_monotonic_ns": None,
                "snapshot": None,
                "snapshot_sha256": None,
                "resolution": None,
                "resolution_sha256": None,
                "error_code": None,
            }
            try:
                return self._resolve_attempt(expected, row)
            except BaseException as error:
                code = getattr(error, "code", None)
                row["error_code"] = (
                    code
                    if type(code) is str and code in TRACE_ERROR_CODES
                    else (
                        "CONTROLLER_METADATA_ACQUISITION_FAILED"
                        if isinstance(error, Exception)
                        else "CONTROLLER_RESOLUTION_INTERRUPTED"
                    )
                )
                row["status"] = "HELD"
                raise
            finally:
                row["finished_monotonic_ns"] = self._observed_now
                self._attempts.append(row)

    def _resolve_attempt(
        self, expected: RoArmUsbSerialIdentity, row: dict[str, Any]
    ) -> RoArmUsbSerialIdentity:
        _require(
            type(expected) is RoArmUsbSerialIdentity
            and expected == self._reviewed.identity,
            "REVIEWED_CONTROLLER_CHANGED",
        )
        _require(
            _json(self._reviewed.to_dict(), MAX_RESOLUTION_BYTES)
            == self._binding_bytes,
            "REVIEWED_CONTROLLER_CHANGED",
        )
        before = self._checkpoint()
        row["started_monotonic_ns"] = before
        self._observed_now = None
        snapshot = self._acquire()
        _require(type(snapshot) is ControllerMetadataSnapshot)
        # Detach before the post-acquisition checkpoint: a late or cancelled
        # observation remains evidence even though no identity is delivered.
        snapshot = decode_controller_snapshot(
            snapshot,
            (
                "rehearsal"
                if self._reviewed.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
                else "physical"
            ),
        )
        row["snapshot"] = json.loads(snapshot.payload())
        row["snapshot_sha256"] = snapshot.snapshot_sha256
        after = self._checkpoint()
        _require(type(snapshot) is ControllerMetadataSnapshot)
        _require(
            before
            <= snapshot.started_monotonic_ns
            <= snapshot.finished_monotonic_ns
            <= after,
            "CONTROLLER_METADATA_NOT_FRESH",
        )
        self._observed_now = None
        result = resolve_controller_metadata(self._reviewed, snapshot)
        self._latest = result
        row["resolution"] = result.to_dict()
        row["resolution_sha256"] = result.sha256
        self._checkpoint()
        _require(expected == self._reviewed.identity, "REVIEWED_CONTROLLER_CHANGED")
        _require(result.identity is not None, "CONTROLLER_METADATA_HELD")
        assert result.identity is not None
        row["status"] = "MATCHED_METADATA_ONLY"
        row["finished_monotonic_ns"] = self._observed_now
        # Refuse before the worker may open/write if complete retention
        # would overflow; never trim a snapshot to manufacture success.
        _json({"attempts": self._attempts + [row]}, MAX_TRACE_BYTES - 1024)
        return deepcopy(result.identity)
