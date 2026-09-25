"""Explicit, bounded native camera metadata packets; never activation authority.

The production adapter invokes only the existing metadata methods. Its caller
must supply an independently reviewed runtime client; no historical helper is
located or trusted implicitly. Fixture packets have incapable provenance even
though their inner wire schemas exercise the actual Windows receipt parsers.
"""

from __future__ import annotations

import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from rocell.providers.windows.camera_worker_client import (
    CameraCandidate,
    NativeCameraIdentityReceipt,
    NativeCameraReceipt,
    WindowsCameraWorkerClient,
    parse_camera_identity_receipt,
    parse_camera_inventory_receipt,
)


PACKET_SCHEMA = "rocell.wizard_native_camera_packet.v1"
MAX_PACKET_BYTES = 256 * 1024
METADATA_DURATION_MS = 5000
METADATA_MAX_PARENTS = 8
FIXTURE_HELPER_SHA256 = hashlib.sha256(
    b"rocell.closed.incapable.native-camera-metadata-fixtures.v1"
).hexdigest()
SCENARIOS = frozenset({"nominal", "missing-mapping", "wrong-device", "duplicate-name"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PROVENANCES = frozenset({"INCAPABLE_FIXTURE", "WINDOWS_NATIVE_METADATA"})
_ENDPOINT = "incapable://camera-metadata/SYNTHETIC-CAMERA-A"
_SECOND_ENDPOINT = "incapable://camera-metadata/SYNTHETIC-CAMERA-B"
_INSTANCE = r"USB\VID_FFFE&PID_0001\SYNTHETIC-CAMERA-A"
_CONTAINER = "11111111-2222-3333-4444-555555555555"


class NativeCameraMetadataError(ValueError):
    """Invalid/unavailable metadata is a hold, never permission to open a camera."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise NativeCameraMetadataError(reason)


def _hash(value: object) -> str:
    _require(
        type(value) is str and _SHA.fullmatch(value) is not None, "Invalid helper hash"
    )
    return str(value)


def _owned_packet(value: object) -> dict[str, Any]:
    """Bound before encoding; own all containers and reject cycles/large values."""
    nodes, text_bytes = 0, 0

    def own(item: object, depth: int) -> Any:
        nonlocal nodes, text_bytes
        nodes += 1
        _require(depth <= 16 and nodes <= 4096, "Metadata nesting/node budget exceeded")
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _require(-(2**63) <= item <= 2**63 - 1, "Metadata integer out of bounds")
            return item
        if type(item) is str:
            try:
                length = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise NativeCameraMetadataError("Invalid metadata Unicode") from exc
            text_bytes += length
            _require(
                length <= 16 * 1024 and text_bytes <= MAX_PACKET_BYTES,
                "Metadata text budget exceeded",
            )
            return item
        if type(item) is list:
            _require(len(item) <= 128, "Metadata array budget exceeded")
            return [own(child, depth + 1) for child in item]
        if type(item) is dict:
            _require(len(item) <= 128, "Metadata field budget exceeded")
            _require(
                all(type(key) is str and len(key) <= 128 for key in item),
                "Invalid metadata field name",
            )
            return {
                own(key, depth + 1): own(child, depth + 1)
                for key, child in item.items()
            }
        raise NativeCameraMetadataError("Metadata must contain only plain JSON types")

    result = own(value, 0)
    _require(type(result) is dict, "Metadata packet must be an object")
    payload = json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    _require(len(payload) <= MAX_PACKET_BYTES, "Metadata packet byte budget exceeded")
    return json.loads(payload)


def validate_native_packet(
    packet: object,
    *,
    kind: str,
    provenance: str,
    helper_sha256: str,
    expected_endpoint: str | None = None,
) -> tuple[dict[str, Any], NativeCameraReceipt | NativeCameraIdentityReceipt]:
    """Pure validation against independently supplied provider/endpoint context.

    Returns a canonical-owned packet and the existing typed receipt. This
    verifies protocol/accounting, not hardware origin, unit identity acceptance,
    driver qualification, firmware, camera connection or physical authority.
    """
    _require(
        type(kind) is str and kind in {"inventory", "identity"}, "Unknown metadata kind"
    )
    _require(
        type(provenance) is str and provenance in _PROVENANCES,
        "Unknown metadata provenance",
    )
    _hash(helper_sha256)
    value = _owned_packet(packet)
    _require(
        set(value) == {"schema", "kind", "provenance", "helper_sha256", "receipt"},
        "Metadata packet fields differ from v1",
    )
    _require(
        value["schema"] == PACKET_SCHEMA
        and value["kind"] == kind
        and value["provenance"] == provenance
        and value["helper_sha256"] == helper_sha256,
        "Metadata packet differs from expected provider context",
    )
    if kind == "inventory":
        _require(expected_endpoint is None, "Inventory cannot select an endpoint")
        receipt: NativeCameraReceipt | NativeCameraIdentityReceipt = (
            parse_camera_inventory_receipt(value["receipt"])
        )
    else:
        _require(
            type(expected_endpoint) is str and bool(expected_endpoint),
            "Identity requires an exact server-owned endpoint",
        )
        receipt = parse_camera_identity_receipt(
            value["receipt"],
            expected_endpoint=str(expected_endpoint),
            duration_ms=METADATA_DURATION_MS,
            max_parent_nodes=METADATA_MAX_PARENTS,
        )
    return value, receipt


def _candidate(candidate: CameraCandidate) -> CameraCandidate:
    _require(
        type(candidate) is CameraCandidate, "Exact server-owned candidate required"
    )
    _require(
        type(candidate.symbolic_link) is str
        and 0 < len(candidate.symbolic_link.encode("utf-8")) <= 4096
        and not any(
            ord(char) < 32 or ord(char) == 127 for char in candidate.symbolic_link
        ),
        "Invalid opaque endpoint",
    )
    _require(
        type(candidate.friendly_name) is str
        and 0 < len(candidate.friendly_name.encode("utf-8")) <= 1024,
        "Invalid candidate display label",
    )
    return CameraCandidate(candidate.symbolic_link, candidate.friendly_name)


def _packet(kind: str, descriptor: Mapping[str, str], receipt: dict) -> dict:
    return {"schema": PACKET_SCHEMA, "kind": kind, **descriptor, "receipt": receipt}


class NativeCameraMetadataProvider:
    """Native metadata only; injection is not a reviewed runtime registration."""

    def __init__(self, client: WindowsCameraWorkerClient):
        _require(
            type(client) is WindowsCameraWorkerClient, "Exact native client required"
        )
        self._client = client
        self._descriptor = MappingProxyType(
            {
                "provenance": "WINDOWS_NATIVE_METADATA",
                "helper_sha256": _hash(client.expected_sha256),
            }
        )
        # Cache declared registration, without resolving/stat'ing its path.
        self._registration = (
            str(client.native_executable),
            client.expected_sha256,
        )
        self._runner = client.runner

    def descriptor(self) -> Mapping[str, str]:
        """Inert cached metadata descriptor; not a hardware qualification claim."""
        return self._descriptor

    def _unchanged(self) -> None:
        _require(
            self._registration
            == (
                str(self._client.native_executable),
                self._client.expected_sha256,
            )
            and self._runner is self._client.runner,
            "Native metadata registration changed; explicit new review required",
        )

    def _result(
        self, kind: str, wire: list[bytes], typed: object, endpoint: str | None = None
    ) -> dict:
        self._unchanged()
        _require(
            len(wire) == 1
            and type(wire[0]) is bytes
            and len(wire[0]) <= MAX_PACKET_BYTES,
            "Missing/invalid exact metadata wire receipt",
        )
        packet, checked = validate_native_packet(
            _packet(kind, self._descriptor, json.loads(wire[0])),
            kind=kind,
            provenance=self._descriptor["provenance"],
            helper_sha256=self._descriptor["helper_sha256"],
            expected_endpoint=endpoint,
        )
        _require(checked == typed, "Typed/native wire metadata receipts disagree")
        return packet

    def inventory(self) -> dict:
        self._unchanged()
        wire: list[bytes] = []
        typed = self._client.enumerate_metadata(
            duration_ms=METADATA_DURATION_MS, wire_receipt_sink=wire.append
        )
        return self._result("inventory", wire, typed)

    def identity(self, candidate: CameraCandidate) -> dict:
        selected = _candidate(candidate)
        self._unchanged()
        wire: list[bytes] = []
        typed = self._client.resolve_identity_metadata(
            selected,
            duration_ms=METADATA_DURATION_MS,
            max_parent_nodes=METADATA_MAX_PARENTS,
            wire_receipt_sink=wire.append,
        )
        return self._result("identity", wire, typed, selected.symbolic_link)


def _observed(value: object) -> dict:
    return {
        "availability": "OBSERVED",
        "value": value,
        "error": {"reason": "NONE", "domain": "NONE", "native_code": 0},
    }


def _unavailable(*, missing: bool = False) -> dict:
    return {
        "availability": "UNAVAILABLE",
        "value": None,
        "error": {
            "reason": "API_FAILURE" if missing else "NOT_REQUESTED",
            "domain": "WIN32" if missing else "NONE",
            "native_code": 433 if missing else 0,
        },
    }


class RehearsalNativeCameraMetadataProvider:
    """Four closed incapable scenarios; no files, processes, OS or devices."""

    def __init__(self, scenario: str = "nominal"):
        _require(
            type(scenario) is str and scenario in SCENARIOS, "Unknown fixture scenario"
        )
        self._scenario = scenario
        self._descriptor = MappingProxyType(
            {
                "provenance": "INCAPABLE_FIXTURE",
                "helper_sha256": FIXTURE_HELPER_SHA256,
            }
        )

    def descriptor(self) -> Mapping[str, str]:
        return self._descriptor

    def _candidates(self) -> tuple[CameraCandidate, ...]:
        candidates: tuple[CameraCandidate, ...] = (
            CameraCandidate(_ENDPOINT, "INCAPABLE SYNTHETIC CAMERA"),
        )
        if self._scenario == "duplicate-name":
            candidates += (
                CameraCandidate(_SECOND_ENDPOINT, candidates[0].friendly_name),
            )
        return candidates

    def inventory(self) -> dict:
        receipt: dict[str, Any] = {
            "schema": "rocell.windows_camera.v1",
            "operation": "inventory",
            "status": "OK",
            "reason_code": None,
            "selected_endpoint": None,
            "devices": [
                {"symbolic_link": c.symbolic_link, "friendly_name": c.friendly_name}
                for c in self._candidates()
            ],
            "modes": [],
            "requested_mode": None,
            "observed_mode": None,
            "controls": [],
            "frames": [],
            "counts": {
                name: 0
                for name in (
                    "source_activation_attempts",
                    "source_opened",
                    "control_set_attempts",
                    "samples_received",
                    "frames_written",
                    "source_shutdown_attempts",
                )
            },
            "cleanup": {
                "source_shutdown_hr": None,
                "source_released": True,
                "mf_shutdown_hr": 0,
                "com_uninitialized": True,
            },
            "limitations": ["INCAPABLE FIXTURE; NO OS OR HARDWARE OBSERVATION"],
        }
        return validate_native_packet(
            _packet("inventory", self._descriptor, receipt),
            kind="inventory",
            **self._descriptor,
        )[0]

    def identity(self, candidate: CameraCandidate) -> dict:
        selected = _candidate(candidate)
        _require(
            selected in self._candidates(),
            "Candidate is absent from this closed fixture",
        )
        missing = self._scenario == "missing-mapping"
        second = selected.symbolic_link == _SECOND_ENDPOINT
        instance = _INSTANCE
        container = _CONTAINER
        if self._scenario == "wrong-device" or second:
            instance = r"USB\VID_FFFE&PID_0002\SYNTHETIC-CAMERA-B"
            container = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        receipt: dict[str, Any] = {
            "schema": "rocell.windows_camera_identity.v1",
            "status": "METADATA_ONLY",
            "requested_endpoint": selected.symbolic_link,
            "mapping": {
                "devnode": _unavailable(missing=True) if missing else _observed(1),
                "interface_path": (
                    _unavailable() if missing else _observed(selected.symbolic_link)
                ),
                "cleanup_errors": [],
            },
            "device": (
                None
                if missing
                else {
                    "devnode": 1,
                    "instance_id": _observed(instance),
                    "container_id": _observed(container),
                    "location_paths": _observed(["INCAPABLE-LOCATION-PATH-A"]),
                }
            ),
            "parents": [],
            "observed_root": _unavailable() if missing else _observed(1),
            "chain_end": "NOT_REQUESTED" if missing else "REACHED_OBSERVED_ROOT",
            "chain_error": {
                "reason": "NOT_REQUESTED",
                "domain": "NONE",
                "native_code": 0,
            },
            "api_calls": 1 if missing else 4,
            "observed_property_bytes": 0 if missing else 128,
            "limits": {
                "max_parent_nodes": 8,
                "max_property_bytes": 16384,
                "max_total_property_bytes": 131072,
                "max_instance_chars": 1024,
                "max_location_paths": 16,
                "duration_ms": 5000,
            },
            "provenance": "WINDOWS_SETUPAPI_CONFIGURATION_MANAGER_METADATA",
            "camera_activation_count": 0,
            "physical_authority": False,
        }
        return validate_native_packet(
            _packet("identity", self._descriptor, receipt),
            kind="identity",
            expected_endpoint=selected.symbolic_link,
            **self._descriptor,
        )[0]
