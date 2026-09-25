"""Inert, session-local review of strictly reconstructed inventory metadata.

Opaque choices identify only one retained inventory occurrence. They are not
device locators, persistent bindings, connection permits or qualifications.
The caller must bind the inventory action to its trusted source/session before
ingest: a matching report hash establishes consistency, not authentication.
"""

from __future__ import annotations

import json
import re
from threading import RLock
from typing import Any
from uuid import uuid4

from .physical_device_inventory import (
    DeviceInventoryBatch,
    InventoryAuthority,
    InventoryDeviceClass,
    InventorySource,
    MAX_DEVICE_CANDIDATES,
    NormalizedDeviceCandidate,
    PhysicalDeviceInventoryReport,
    compose_physical_device_inventory_report,
)

DEVICE_SELECTION_SCHEMA = "rocell.wizard_device_selection.v1"
MAX_INVENTORY_BYTES = 128 * 1024
MAX_IDENTITY_BLOCKERS = 32
_FOLLOWUP_REQUIREMENTS = (
    "VERIFY_RECEIVED_MODEL_AND_UNIT",
    "RESOLVE_UNIQUE_IDENTITY_AND_NATIVE_PREOPEN_RECHECK",
    "QUALIFY_NATIVE_BACKEND_AND_CONNECTION_CONTRACT",
    "COMPLETE_CANONICAL_STAGE_AND_PHYSICAL_RELEASE_GATES",
)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CLASS_NAMES = ("CAMERA", "SERIAL")


class DeviceSelectionError(ValueError):
    """A fixed public error code; provider details are not reflected here."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise DeviceSelectionError(code, message)


def _text(value: object, *, maximum: int = 128) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        _fail("INVALID_INPUT", "Expected bounded nonempty text without controls.")
    assert isinstance(value, str)
    try:
        if len(value.encode("utf-8")) > maximum:
            _fail("INVALID_INPUT", "Text exceeds its UTF-8 byte limit.")
    except UnicodeError as exc:
        raise DeviceSelectionError("INVALID_INPUT", "Text is not valid UTF-8.") from exc
    return value


def _identifier(value: object) -> str:
    result = _text(value)
    if _IDENTIFIER.fullmatch(result) is None:
        _fail("INVALID_INPUT", "Expected a bounded session or operation identifier.")
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _bounded_document(value: object) -> bytes:
    # Validate before JSON encoding so cycles, giant containers, non-JSON values
    # and pathological depth cannot allocate an unbounded serialized snapshot.
    remaining_nodes = 12_000
    remaining_text = MAX_INVENTORY_BYTES

    def visit(item: object, depth: int) -> object:
        nonlocal remaining_nodes, remaining_text
        remaining_nodes -= 1
        if remaining_nodes < 0 or depth > 8:
            _fail("REPORT_LIMIT", "Inventory exceeds the bounded structure limit.")
        if type(item) is dict:
            if len(item) > 32:
                _fail("REPORT_LIMIT", "Inventory object has too many fields.")
            copied = {}
            for key, child in item.items():
                if type(key) is not str or len(key) > 128:
                    _fail("REPORT_INVALID", "Inventory field names are invalid.")
                visit(key, depth + 1)
                copied[key] = visit(child, depth + 1)
            return copied
        elif type(item) is list:
            if len(item) > MAX_DEVICE_CANDIDATES:
                _fail("REPORT_LIMIT", "Inventory array exceeds its item limit.")
            return [visit(child, depth + 1) for child in item]
        elif type(item) is str:
            if len(item) > 2048:
                _fail("REPORT_LIMIT", "Inventory text exceeds its byte limit.")
            size = len(item.encode("utf-8"))
            remaining_text -= size
            if size > 2048 or remaining_text < 0:
                _fail("REPORT_LIMIT", "Inventory text exceeds its byte limit.")
        elif item is None or type(item) is bool:
            return item
        elif type(item) is int and 0 <= item <= (1 << 63) - 1:
            return item
        else:
            _fail("REPORT_INVALID", "Inventory contains a non-JSON or invalid value.")
        return item

    # Copy while bounding. Both the retained bytes and typed model are then
    # built from our owned snapshot, never a second read of caller-owned data.
    payload = _canonical(visit(value, 0))
    if len(payload) > MAX_INVENTORY_BYTES:
        _fail("REPORT_LIMIT", "Inventory exceeds the 128 KiB canonical byte limit.")
    return payload


def _object(value: object, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        _fail("REPORT_INVALID", "Inventory has missing or unknown fields.")
    assert isinstance(value, dict)
    return value


def _array(value: object, maximum: int = MAX_DEVICE_CANDIDATES) -> list[Any]:
    if type(value) is not list or len(value) > maximum:
        _fail("REPORT_INVALID", "Inventory array shape is invalid.")
    assert isinstance(value, list)
    return value


def _same(actual: object, expected: object) -> None:
    # Canonical byte comparison also distinguishes False from 0, unlike Python
    # dict equality. Normalization by a typed constructor cannot hide drift.
    if _canonical(actual) != _canonical(expected):
        _fail("REPORT_INVALID", "Inventory does not match its strict typed form.")


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
        identity_blockers=tuple(
            _array(obj["identity_blockers"], MAX_IDENTITY_BLOCKERS)
        ),
    )
    _same(obj, candidate.to_dict())
    return candidate


def _batch(value: object) -> DeviceInventoryBatch:
    obj = _object(
        value,
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
    batch = DeviceInventoryBatch(
        device_class=InventoryDeviceClass(obj["device_class"]),
        source=InventorySource(obj["source"]),
        candidates=tuple(_candidate(row) for row in _array(obj["candidates"])),
        collection_blockers=tuple(_array(obj["collection_blockers"], 64)),
        collection_complete=obj["collection_complete"],
        schema=obj["schema"],
    )
    _same(obj, batch.to_dict())
    if not batch.collection_complete:
        _fail("INVENTORY_INCOMPLETE", "Incomplete inventory cannot issue choices.")
    return batch


def _reconstruct(value: object, mode: str) -> PhysicalDeviceInventoryReport:
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
    report = PhysicalDeviceInventoryReport(
        platform_system=obj["platform_system"],
        captured_at_unix_ns=obj["captured_at_unix_ns"],
        camera_inventory=_batch(obj["camera_inventory"]),
        serial_inventory=_batch(obj["serial_inventory"]),
        blockers=tuple(_array(obj["blockers"], 64)),
        authority=InventoryAuthority(),
        schema=obj["schema"],
        purpose=obj["purpose"],
    )
    _same(obj, report.to_dict())
    expected_source = (
        InventorySource.PYSERIAL_LIST_PORTS
        if mode == "physical"
        else InventorySource.INJECTED_SERIAL_ENUMERATOR
    )
    if report.serial_inventory.source is not expected_source:
        _fail("INVENTORY_SOURCE_MISMATCH", "Serial inventory source differs from mode.")
    # The public pure composer derives aggregate blockers from actual batches.
    # No collector, provider or OS query is called by this module.
    composed = compose_physical_device_inventory_report(
        platform_system=report.platform_system,
        captured_at_unix_ns=report.captured_at_unix_ns,
        camera_inventory=report.camera_inventory,
        serial_inventory=report.serial_inventory,
    )
    _same(report.to_dict(), composed.to_dict())
    return report


def _identity_blockers(
    candidate: NormalizedDeviceCandidate, peers: tuple[NormalizedDeviceCandidate, ...]
) -> list[str]:
    """Conservatively flag occurrence ambiguity without editing source evidence."""
    prefix = candidate.device_class.value
    blockers = set(candidate.identity_blockers)
    for absent, suffix in (
        (candidate.vid is None, "VID_MISSING"),
        (candidate.pid is None, "PID_MISSING"),
        (candidate.unit_serial is None, "UNIT_SERIAL_MISSING"),
        (candidate.os_instance_id is None, "OS_INSTANCE_ID_MISSING"),
        (not candidate.persistent_ids, "PERSISTENT_SELECTOR_MISSING"),
    ):
        if absent:
            blockers.add(f"{prefix}_{suffix}")
    if sum(item.candidate_sha256 == candidate.candidate_sha256 for item in peers) > 1:
        blockers.add(f"{prefix}_DUPLICATE_METADATA_OCCURRENCE")
    if any(
        sum(identity in item.persistent_ids for item in peers) > 1
        for identity in candidate.persistent_ids
    ):
        blockers.add(f"{prefix}_PERSISTENT_ID_AMBIGUOUS")
    usb = (candidate.vid, candidate.pid, candidate.unit_serial)
    if (
        all(value is not None for value in usb)
        and sum((item.vid, item.pid, item.unit_serial) == usb for item in peers) > 1
    ):
        blockers.add(f"{prefix}_USB_UNIT_IDENTITY_AMBIGUOUS")
    for field, suffix in (
        ("os_instance_id", "OS_INSTANCE_ID_AMBIGUOUS"),
        ("ephemeral_locator", "EPHEMERAL_LOCATOR_AMBIGUOUS"),
    ):
        value = getattr(candidate, field)
        if (
            value is not None
            and sum(getattr(item, field) == value for item in peers) > 1
        ):
            blockers.add(f"{prefix}_{suffix}")
    if len(blockers) > MAX_IDENTITY_BLOCKERS:
        _fail("REPORT_LIMIT", "Candidate identity blockers exceed the display bound.")
    return sorted(blockers)


class WizardDeviceSelection:
    """One in-memory metadata snapshot, no implicit selection and no disk I/O."""

    def __init__(self, mode: str, session_id: str, source_sha256: str) -> None:
        if type(mode) is not str or mode not in {"rehearsal", "physical"}:
            _fail("INVALID_MODE", "Mode must be rehearsal or physical.")
        self._mode = mode
        self._session_id = _identifier(session_id)
        self._source_sha256 = _text(source_sha256)
        if _SHA256.fullmatch(self._source_sha256) is None:
            _fail("INVALID_INPUT", "Source binding must be a lowercase SHA-256.")
        self._lock = RLock()
        self._report: PhysicalDeviceInventoryReport | None = None
        self._payload: bytes | None = None
        self._operation_id: str | None = None
        self._choices: dict[str, tuple[NormalizedDeviceCandidate, list[str]]] = {}
        self._reviews: dict[str, dict[str, Any]] = {}
        self._invalidation_reason: str | None = None
        self._generation = 0

    def staged_copy(self) -> WizardDeviceSelection:
        """Detach mutable state for caller-controlled durable publication.

        The caller can validate and retain/log the staged result before making
        it visible. This method does not persist, publish or authorize anything.
        """
        with self._lock:
            staged = WizardDeviceSelection(
                self._mode, self._session_id, self._source_sha256
            )
            staged._report = self._report  # Frozen typed values and bytes are shared.
            staged._payload = self._payload
            staged._operation_id = self._operation_id
            staged._choices = {
                token: (candidate, list(blockers))
                for token, (candidate, blockers) in self._choices.items()
            }
            staged._reviews = json.loads(_canonical(self._reviews))
            staged._invalidation_reason = self._invalidation_reason
            staged._generation = self._generation
            return staged

    def invalidate(self, reason: str) -> None:
        reason = _text(reason, maximum=512)
        with self._lock:
            self._report = None
            self._payload = None
            self._operation_id = None
            self._choices.clear()
            self._reviews.clear()
            self._invalidation_reason = reason
            self._generation += 1

    def ingest(self, report: dict[str, Any], *, operation_id: str) -> None:
        with self._lock:
            # A failed replacement must not leave old tokens looking current.
            self.invalidate("INVENTORY_REPLACEMENT_NOT_VERIFIED")
            try:
                checked_operation = _identifier(operation_id)
                payload = _bounded_document(report)
                model = _reconstruct(json.loads(payload), self._mode)
                choices: dict[str, tuple[NormalizedDeviceCandidate, list[str]]] = {}
                for batch in (model.camera_inventory, model.serial_inventory):
                    for candidate in batch.candidates:
                        # Generation prevents a repeated random value from
                        # resurrecting a token after an explicit reset.
                        choice = f"choice-{self._generation:x}-{uuid4().hex}"
                        if choice in choices:
                            _fail("CHOICE_COLLISION", "Could not issue unique choices.")
                        choices[choice] = (
                            candidate,
                            _identity_blockers(candidate, batch.candidates),
                        )
            except DeviceSelectionError:
                raise
            except (
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                UnicodeError,
                RuntimeError,
            ) as exc:
                raise DeviceSelectionError(
                    "REPORT_INVALID", "Inventory violates the strict metadata contract."
                ) from exc
            self._payload = payload
            self._report = model
            self._operation_id = checked_operation
            self._choices = choices
            self._invalidation_reason = None

    @staticmethod
    def _class(device_class: str) -> str:
        if type(device_class) is not str or device_class not in _CLASS_NAMES:
            _fail("INVALID_DEVICE_CLASS", "Device class must be CAMERA or SERIAL.")
        return device_class

    def _lookup(
        self, choice_id: str, device_class: str
    ) -> tuple[NormalizedDeviceCandidate, list[str]]:
        selected_class = self._class(device_class)
        if (
            type(choice_id) is not str
            or len(choice_id) > 128
            or choice_id not in self._choices
        ):
            _fail(
                "STALE_OR_UNKNOWN_CHOICE",
                "Refresh inventory and review a current choice.",
            )
        candidate, blockers = self._choices[choice_id]
        if candidate.device_class.value != selected_class:
            _fail(
                "CHOICE_CLASS_MISMATCH", "Choice belongs to a different device class."
            )
        return candidate, blockers

    def _summary(
        self, choice_id: str, candidate: NormalizedDeviceCandidate, blockers: list[str]
    ) -> dict[str, Any]:
        return {
            "choice_id": choice_id,
            "display_name": candidate.display_name,
            "vid": candidate.vid,
            "pid": candidate.pid,
            "unit_serial": candidate.unit_serial,
            "source": candidate.source.value,
            "identity_blockers": list(blockers),
            "candidate_sha256": candidate.candidate_sha256,
        }

    def choices(self, device_class: str) -> list[dict[str, str]]:
        selected_class = self._class(device_class)
        with self._lock:
            result: list[dict[str, str]] = []
            for choice, (candidate, _) in self._choices.items():
                if candidate.device_class.value == selected_class:
                    label = candidate.display_name
                    if len(label) > 128:
                        label = label[:125] + "..."
                    # The occurrence number distinguishes duplicates without
                    # implying that either has a unique persistent identity.
                    result.append(
                        {
                            "value": choice,
                            "label": f"{len(result) + 1}. {label} — metadata only",
                        }
                    )
            return result

    def preview(self, choice_id: str, device_class: str) -> dict[str, Any]:
        with self._lock:
            candidate, blockers = self._lookup(choice_id, device_class)
            assert self._report is not None
            return {
                "schema": "rocell.wizard_device_candidate_preview.v1",
                "device_class": device_class,
                "candidate": self._summary(choice_id, candidate, blockers),
                "candidate_record": candidate.to_dict(),
                "provenance": self._provenance(),
                "report_sha256": self._report.report_sha256,
                "operation_id": self._operation_id,
                "meaning": "Review acknowledges observed metadata for investigation; it does not bind, connect or qualify a device.",
                "followup_requirements": list(_FOLLOWUP_REQUIREMENTS),
                "physical_authority": False,
                "connected": False,
                "qualified": False,
                "persistent_binding": False,
            }

    def review(
        self, choice_id: str, device_class: str, reviewer_id: str
    ) -> dict[str, Any]:
        reviewer_id = _text(reviewer_id)
        with self._lock:
            candidate, _ = self._lookup(choice_id, device_class)
            assert self._report is not None and self._payload is not None
            review = {
                "choice_id": choice_id,
                "candidate_sha256": candidate.candidate_sha256,
                "reviewer_id": reviewer_id,
                "report_sha256": self._report.report_sha256,
                "operation_id": self._operation_id,
                "status": "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION",
                "connected": False,
                "qualified": False,
                "persistent_binding": False,
                "physical_authority": False,
                "followup_requirements": list(_FOLLOWUP_REQUIREMENTS),
            }
            self._reviews[device_class] = review
            # Full original metadata is returned only by this explicit action,
            # never by view(). Consumers must keep its privacy/export scope.
            return {
                **self.preview(choice_id, device_class),
                "schema": "rocell.wizard_device_candidate_review.v1",
                "review": json.loads(_canonical(review)),
                "inventory_report": json.loads(self._payload),
            }

    def reviewed_candidate(self, device_class: str) -> dict[str, Any] | None:
        """Read the current exact acknowledgement without issuing another one."""
        device_class = self._class(device_class)
        with self._lock:
            review = self._reviews.get(device_class)
            if review is None:
                return None
            assert self._payload is not None
            return {
                **self.preview(review["choice_id"], device_class),
                "schema": "rocell.wizard_device_candidate_review.v1",
                "review": json.loads(_canonical(review)),
                "inventory_report": json.loads(self._payload),
            }

    def _provenance(self) -> dict[str, Any]:
        return {
            "mode": self._mode,
            "session_id": self._session_id,
            "source_sha256": self._source_sha256,
            "platform_system": (
                None if self._report is None else self._report.platform_system
            ),
            "captured_at_unix_ns": (
                None if self._report is None else self._report.captured_at_unix_ns
            ),
            "scope": "METADATA_SNAPSHOT_ONLY",
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            status = (
                "INVALIDATED"
                if self._invalidation_reason is not None
                else (
                    "NO_INVENTORY"
                    if self._report is None
                    else (
                        "METADATA_REVIEW_RECORDED"
                        if self._reviews
                        else "METADATA_CANDIDATES_AVAILABLE"
                    )
                )
            )
            return {
                "schema": DEVICE_SELECTION_SCHEMA,
                "status": status,
                "provenance": self._provenance(),
                "report_sha256": (
                    None if self._report is None else self._report.report_sha256
                ),
                "operation_id": self._operation_id,
                "devices": {
                    device_class: {
                        "candidates": [
                            self._summary(choice, candidate, blockers)
                            for choice, (candidate, blockers) in self._choices.items()
                            if candidate.device_class.value == device_class
                        ],
                        "review": json.loads(
                            _canonical(self._reviews.get(device_class))
                        ),
                    }
                    for device_class in _CLASS_NAMES
                },
                "physical_authority": False,
                "connected": False,
                "qualified": False,
                "persistent_binding": False,
                "invalidation_reason": self._invalidation_reason,
            }
