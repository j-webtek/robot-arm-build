"""Pure, staged review of native camera endpoint metadata, never activation.

The service supplies trusted source-bound packets and the current generic
review. Hash agreement proves internal consistency, not origin or unit identity.
An endpoint binding is prospective metadata; all physical holds remain in force.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
from threading import RLock
from typing import Any
from uuid import uuid4

from rocell.providers.windows.camera_worker_client import (
    CameraCandidate,
    CameraEndpointBinding,
    CameraWorkerError,
    NativeCameraIdentityReceipt,
    NativeCameraReceipt,
)
from .wizard_device_selection import DeviceSelectionError, WizardDeviceSelection
from .wizard_native_camera_metadata import (
    NativeCameraMetadataError,
    validate_native_packet,
)

SCHEMA = "rocell.wizard_native_camera_enrollment.v1"
MAX_REPORT_BYTES = 768 * 1024
MAX_GENERIC_REVIEW_BYTES = 256 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_BASELINE_HOLDS = frozenset(
    {
        "CAMERA_NOT_CONNECTED",
        "CAMERA_NOT_QUALIFIED",
        "CAMERA_USB3_SPEED_NOT_VERIFIED",
        "CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED",
        "CAMERA_USB3_TOPOLOGY_NOT_OBSERVED",
        "CAMERA_RECEIVED_MODEL_AND_UNIT_NOT_VERIFIED",
        "NATIVE_BACKEND_QUALIFICATION_REQUIRED",
        "PHYSICAL_STAGE_GATES_REMAIN_HELD",
    }
)
_UNRELATED_IDENTITY_HOLDS = frozenset(
    {
        "CAMERA_USB3_TOPOLOGY_REQUIRES_SEPARATE_EVIDENCE",
        "CAMERA_USB3_SPEED_NOT_VERIFIED",
        "CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED",
        "CAMERA_USB3_TOPOLOGY_NOT_OBSERVED",
        "CAMERA_STREAM_NOT_OPENED_BY_DESIGN",
        "CAMERA_NOT_CONNECTED",
        "CAMERA_NOT_QUALIFIED",
    }
)


class NativeCameraEnrollmentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise NativeCameraEnrollmentError(code, message)


def _text(value: object, maximum: int = 128) -> str:
    _require(
        type(value) is str and bool(value) and len(value) <= maximum,
        "INVALID_INPUT",
        "Expected bounded nonempty text.",
    )
    assert isinstance(value, str)
    try:
        valid = value == value.strip() and len(value.encode("utf-8")) <= maximum
    except UnicodeError:
        valid = False
    _require(
        valid and not any(ord(c) < 32 or ord(c) == 127 for c in value),
        "INVALID_INPUT",
        "Text must be bounded UTF-8 without controls.",
    )
    return value


def _bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _hash(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _owned(value: object, maximum: int) -> dict[str, Any]:
    nodes = 0
    total_text = 0

    def copy(item: object, depth: int) -> Any:
        nonlocal nodes, total_text
        nodes += 1
        _require(
            depth <= 24 and nodes <= 32_000,
            "REPORT_LIMIT",
            "Metadata structure exceeds its bound.",
        )
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _require(
                -(1 << 63) <= item < (1 << 63),
                "INVALID_INPUT",
                "Metadata integer exceeds its bound.",
            )
            return item
        if type(item) is str:
            _require(
                len(item) <= 16_384, "REPORT_LIMIT", "Metadata text exceeds its bound."
            )
            try:
                count = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise NativeCameraEnrollmentError(
                    "INVALID_INPUT", "Metadata text is not UTF-8."
                ) from exc
            total_text += count
            _require(
                count <= 16_384 and total_text <= maximum,
                "REPORT_LIMIT",
                "Metadata text exceeds its byte bound.",
            )
            return item
        if type(item) is dict:
            _require(
                len(item) <= 128
                and all(type(k) is str and len(k) <= 128 for k in item),
                "INVALID_INPUT",
                "Metadata fields are invalid.",
            )
            return {copy(k, depth + 1): copy(v, depth + 1) for k, v in item.items()}
        if type(item) is list:
            _require(
                len(item) <= 128, "REPORT_LIMIT", "Metadata array exceeds its bound."
            )
            return [copy(child, depth + 1) for child in item]
        raise NativeCameraEnrollmentError(
            "INVALID_INPUT", "Metadata must contain only plain JSON."
        )

    try:
        result = copy(value, 0)
    except RuntimeError as exc:
        raise NativeCameraEnrollmentError(
            "INVALID_INPUT", "Metadata changed while being copied."
        ) from exc
    _require(
        type(result) is dict and len(_bytes(result)) <= maximum,
        "REPORT_LIMIT",
        "Complete metadata report exceeds its byte bound.",
    )
    return result


def _generic_review(
    value: object, mode: str, session: str, source: str
) -> dict[str, Any]:
    """Reconstruct the existing public preview contract without issuing a review."""
    owned = _owned(value, MAX_GENERIC_REVIEW_BYTES)
    try:
        inventory = owned["inventory_report"]
        original_review = owned["review"]
        original_choice = _text(original_review["choice_id"])
        reviewer = _text(original_review["reviewer_id"])
        operation = _text(owned["operation_id"])
        temporary = WizardDeviceSelection(mode, session, source)
        temporary.ingest(inventory, operation_id=operation)
        candidate_hash = _hash(owned["candidate_record"])
        matches = [
            row
            for row in temporary.view()["devices"]["CAMERA"]["candidates"]
            if row["candidate_sha256"] == candidate_hash
        ]
        _require(
            bool(matches),
            "GENERIC_REVIEW_INVALID",
            "Reviewed camera is absent from the exact generic inventory.",
        )
        expected = temporary.preview(matches[0]["choice_id"], "CAMERA")
        expected["candidate"]["choice_id"] = original_choice
        expected["schema"] = "rocell.wizard_device_candidate_review.v1"
        expected["inventory_report"] = inventory
        expected["review"] = {
            "choice_id": original_choice,
            "candidate_sha256": candidate_hash,
            "reviewer_id": reviewer,
            "report_sha256": expected["report_sha256"],
            "operation_id": operation,
            "status": "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION",
            "connected": False,
            "qualified": False,
            "persistent_binding": False,
            "physical_authority": False,
            "followup_requirements": expected["followup_requirements"],
        }
        _require(
            _bytes(owned) == _bytes(expected),
            "GENERIC_REVIEW_INVALID",
            "Generic review does not match its source/session/candidate contract.",
        )
        _require(
            expected["provenance"]["platform_system"] == "Windows",
            "GENERIC_PLATFORM_MISMATCH",
            "Windows native enrollment requires Windows camera metadata.",
        )
        return owned
    except NativeCameraEnrollmentError:
        raise
    except (DeviceSelectionError, ValueError, TypeError, KeyError) as exc:
        raise NativeCameraEnrollmentError(
            "GENERIC_REVIEW_INVALID", "Generic camera review is invalid or incomplete."
        ) from exc


def _container_ids(generic: dict[str, Any]) -> tuple[set[str], set[str]]:
    values: set[str] = set()
    blockers: set[str] = set()
    for identity in generic["candidate_record"]["persistent_ids"]:
        if identity.startswith("windows-container:"):
            value = identity[len("windows-container:") :]
            if value.startswith("{") and value.endswith("}"):
                value = value[1:-1]
            value = value.lower()
            if _GUID.fullmatch(value) is None:
                blockers.add("GENERIC_CONTAINER_ID_MALFORMED")
            else:
                values.add(value)
    if not values:
        blockers.add("GENERIC_CONTAINER_ID_MISSING")
    elif len(values) != 1:
        blockers.add("GENERIC_CONTAINER_ID_AMBIGUOUS")
    return values, blockers


def verify_native_camera_enrollment_snapshot(
    snapshot: object, *, source_sha256: str, launch_session_id: str
) -> dict[str, Any]:
    """Recompute one complete retained review without restoring a live owner.

    Both an exact mapping and an acknowledged held mapping are evidence. This
    verifies consistency and the caller's source/launch binding, not provenance
    authentication, present attachment, persistent identity or device authority.
    Original opaque choices and operation IDs remain unchanged. Temporary
    generic-review choices never appear in the returned detached document.
    """
    owned = _owned(snapshot, MAX_REPORT_BYTES)
    try:
        _require(
            set(owned)
            == {
                "schema",
                "view",
                "generic_review",
                "inventory_packet",
                "identity_packet",
                "binding_artifact",
            }
            and owned["schema"] == "rocell.wizard_native_camera_enrollment_report.v1",
            "ENROLLMENT_SNAPSHOT_INVALID",
            "Expected the complete original enrollment snapshot.",
        )
        view = owned["view"]
        provenance = view["provenance"]
        _require(
            provenance["source_sha256"] == source_sha256
            and provenance["session_id"] == launch_session_id
            and view["status"] in {"ENDPOINT_METADATA_REVIEWED", "REVIEW_HELD"}
            and view["invalidation_reason"] is None,
            "ENROLLMENT_CONTEXT_INVALID",
            "A complete reviewed snapshot in its original source/launch is required.",
        )
        owner = WizardNativeCameraEnrollment(
            provenance["mode"],
            launch_session_id,
            source_sha256,
            {
                "provenance": provenance["provider_provenance"],
                "helper_sha256": provenance["helper_sha256"],
            },
        )
        generic = _generic_review(
            owned["generic_review"],
            provenance["mode"],
            launch_session_id,
            source_sha256,
        )
        inventory_packet, inventory = owner._packet(
            owned["inventory_packet"], "inventory"
        )
        _require(
            type(inventory) is NativeCameraReceipt
            and inventory.operation == "inventory"
            and inventory.status == "OK"
            and inventory.cleanup_confirmed,
            "NATIVE_INVENTORY_INCOMPLETE",
            "Retained inventory requires confirmed metadata cleanup.",
        )
        assert isinstance(inventory, NativeCameraReceipt)
        rows = view["candidates"]
        _require(
            type(rows) is list
            and 1 <= len(rows) <= 128
            and len(rows) == len(inventory.candidates),
            "ENROLLMENT_CHOICES_INVALID",
            "Retained choices must cover the exact ordered inventory.",
        )
        choices: dict[str, CameraCandidate] = {}
        generations = set()
        for row, candidate in zip(rows, inventory.candidates):
            token = _text(row["choice_id"])
            match = re.fullmatch(r"endpoint-([1-9a-f][0-9a-f]*)-[0-9a-f]{32}", token)
            _require(
                match is not None
                and token not in choices
                and _bytes(row)
                == _bytes(
                    {
                        "choice_id": token,
                        "friendly_name": candidate.friendly_name,
                        "endpoint_sha256": candidate.endpoint_sha256,
                    }
                ),
                "ENROLLMENT_CHOICES_INVALID",
                "Opaque choices differ from their original inventory occurrences.",
            )
            assert match is not None
            generations.add(match.group(1))
            choices[token] = CameraCandidate(
                candidate.symbolic_link, candidate.friendly_name
            )
        _require(
            len(generations) == 1,
            "ENROLLMENT_CHOICES_INVALID",
            "Retained choices mix inventory generations.",
        )
        # Verifier-only seed after the actual packet and generic validators.
        # Do not issue new endpoint tokens or expose this owner to the caller.
        owner._generic = _bytes(generic)
        owner._inventory = _bytes(inventory_packet)
        owner._inventory_operation = _text(view["inventory_operation_id"])
        owner._choices = choices
        identity, review = view["identity"], view["review"]
        owner.retain_identity(
            identity["choice_id"],
            owned["identity_packet"],
            operation_id=identity["operation_id"],
        )
        rebuilt = owner.review(review["choice_id"], review["reviewer_id"])
        _require(
            _bytes(rebuilt) == _bytes(owned),
            "ENROLLMENT_SNAPSHOT_MISMATCH",
            "Retained metadata, matches, review and hashes do not recompute exactly.",
        )
        return owned
    except NativeCameraEnrollmentError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise NativeCameraEnrollmentError(
            "ENROLLMENT_SNAPSHOT_INVALID", "Complete retained enrollment is invalid."
        ) from exc


class WizardNativeCameraEnrollment:
    def __init__(
        self,
        mode: str,
        session_id: str,
        source_sha256: str,
        provider_descriptor: Mapping[str, str] | None = None,
    ) -> None:
        # Reuse the generic constructor's strict source/session/mode contract.
        try:
            WizardDeviceSelection(mode, session_id, source_sha256)
        except DeviceSelectionError as exc:
            raise NativeCameraEnrollmentError(exc.code, str(exc)) from exc
        self._mode, self._session, self._source = mode, session_id, source_sha256
        self._descriptor: dict[str, str] | None = None
        if provider_descriptor is not None:
            _require(
                isinstance(provider_descriptor, Mapping)
                and set(provider_descriptor) == {"provenance", "helper_sha256"},
                "PROVIDER_INVALID",
                "Provider descriptor fields are invalid.",
            )
            descriptor = dict(provider_descriptor)
            expected = (
                "INCAPABLE_FIXTURE"
                if mode == "rehearsal"
                else "WINDOWS_NATIVE_METADATA"
            )
            _require(
                descriptor["provenance"] == expected
                and type(descriptor["provenance"]) is str
                and type(descriptor["helper_sha256"]) is str
                and _SHA.fullmatch(descriptor["helper_sha256"]) is not None,
                "PROVIDER_INVALID",
                "Provider descriptor differs from the selected mode.",
            )
            self._descriptor = descriptor
        self._lock = RLock()
        self._generation = 0
        self._generic: bytes | None = None
        self._inventory: bytes | None = None
        self._inventory_operation: str | None = None
        self._choices: dict[str, CameraCandidate] = {}
        self._identity_packet: bytes | None = None
        self._identity: bytes | None = None
        self._review: bytes | None = None
        self._artifact: bytes | None = None
        self._reason: str | None = None

    def staged_copy(self) -> WizardNativeCameraEnrollment:
        with self._lock:
            copied = WizardNativeCameraEnrollment(
                self._mode, self._session, self._source, self._descriptor
            )
            for name in (
                "_generation",
                "_generic",
                "_inventory",
                "_inventory_operation",
                "_identity_packet",
                "_identity",
                "_review",
                "_artifact",
                "_reason",
            ):
                setattr(copied, name, getattr(self, name))
            copied._choices = {
                key: CameraCandidate(value.symbolic_link, value.friendly_name)
                for key, value in self._choices.items()
            }
            return copied

    def invalidate(self, reason: str) -> None:
        reason = _text(reason, 512)
        with self._lock:
            self._generic = self._inventory = None
            self._inventory_operation = None
            self._choices.clear()
            self._identity_packet = self._identity = self._review = self._artifact = (
                None
            )
            self._reason = reason
            self._generation += 1

    def invalidate_identity(self, reason: str) -> None:
        reason = _text(reason, 512)
        with self._lock:
            self._identity_packet = self._identity = self._review = self._artifact = (
                None
            )
            self._reason = reason

    def invalidate_review(self, reason: str) -> None:
        reason = _text(reason, 512)
        with self._lock:
            self._review = self._artifact = None
            self._reason = reason

    def _packet(
        self, packet: object, kind: str, endpoint: str | None = None
    ) -> tuple[dict[str, Any], NativeCameraReceipt | NativeCameraIdentityReceipt]:
        _require(
            self._descriptor is not None,
            "PROVIDER_UNAVAILABLE",
            "No native metadata provider is configured; no endpoint operation is available.",
        )
        assert self._descriptor is not None
        try:
            return validate_native_packet(
                packet, kind=kind, **self._descriptor, expected_endpoint=endpoint
            )
        except (
            CameraWorkerError,
            NativeCameraMetadataError,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
        ) as exc:
            raise NativeCameraEnrollmentError(
                "NATIVE_PACKET_INVALID",
                "Native metadata packet differs from its exact provider/endpoint contract.",
            ) from exc

    def ingest_inventory(
        self,
        packet: dict[str, Any],
        *,
        operation_id: str,
        generic_review: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            self.invalidate("NATIVE_INVENTORY_REPLACEMENT_NOT_VERIFIED")
            generic = _generic_review(
                generic_review, self._mode, self._session, self._source
            )
            operation = _text(operation_id)
            owned, receipt = self._packet(packet, "inventory")
            _require(
                type(receipt) is NativeCameraReceipt
                and receipt.operation == "inventory"
                and receipt.status == "OK"
                and receipt.cleanup_confirmed,
                "NATIVE_INVENTORY_INCOMPLETE",
                "Native inventory did not complete with confirmed metadata cleanup.",
            )
            assert isinstance(receipt, NativeCameraReceipt)
            choices: dict[str, CameraCandidate] = {}
            for candidate in receipt.candidates:
                token = f"endpoint-{self._generation:x}-{uuid4().hex}"
                _require(
                    token not in choices,
                    "CHOICE_COLLISION",
                    "Could not issue distinct endpoint choices.",
                )
                choices[token] = CameraCandidate(
                    candidate.symbolic_link, candidate.friendly_name
                )
            self._generic, self._inventory = _bytes(generic), _bytes(owned)
            self._inventory_operation, self._choices = operation, choices
            self._reason = None
            return self._finish_mutation("inventory")

    def candidate(self, choice_id: str) -> CameraCandidate:
        with self._lock:
            _require(
                type(choice_id) is str
                and len(choice_id) <= 128
                and choice_id in self._choices,
                "STALE_OR_UNKNOWN_CHOICE",
                "Refresh native inventory and choose an exact current endpoint.",
            )
            value = self._choices[choice_id]
            return CameraCandidate(value.symbolic_link, value.friendly_name)

    def choices(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                {
                    "value": key,
                    "label": f"{index + 1}. {value.friendly_name[:125]}{'...' if len(value.friendly_name) > 125 else ''} — endpoint metadata",
                }
                for index, (key, value) in enumerate(self._choices.items())
            ]

    def preview(self, choice_id: str) -> dict[str, Any]:
        with self._lock:
            candidate = self.candidate(choice_id)
            return {
                "schema": "rocell.wizard_native_camera_endpoint_preview.v1",
                "choice_id": choice_id,
                "friendly_name": candidate.friendly_name,
                "endpoint_sha256": candidate.endpoint_sha256,
                "inventory_sha256": (
                    None
                    if self._inventory is None
                    else hashlib.sha256(self._inventory).hexdigest()
                ),
                "inventory_operation_id": self._inventory_operation,
                "provenance": self._provenance(),
                "blockers": self.view()["blockers"],
                "meaning": "Exact endpoint metadata only; no connection, persistent unit binding or qualification.",
                "connected": False,
                "qualified": False,
                "persistent_binding": False,
                "physical_authority": False,
            }

    def retain_identity(
        self, choice_id: str, packet: dict[str, Any], *, operation_id: str
    ) -> dict[str, Any]:
        with self._lock:
            self.invalidate_identity("NATIVE_IDENTITY_REPLACEMENT_NOT_VERIFIED")
            candidate = self.candidate(choice_id)
            operation = _text(operation_id)
            owned, receipt = self._packet(packet, "identity", candidate.symbolic_link)
            _require(
                type(receipt) is NativeCameraIdentityReceipt,
                "NATIVE_PACKET_INVALID",
                "Expected one exact native identity receipt.",
            )
            assert (
                isinstance(receipt, NativeCameraIdentityReceipt)
                and self._generic is not None
            )
            generic = json.loads(self._generic)
            containers, blockers = _container_ids(generic)
            blockers.update(
                set(generic["candidate"]["identity_blockers"])
                - _UNRELATED_IDENTITY_HOLDS
            )
            exact = receipt.exact_endpoint_observed
            device = receipt.device
            device_match = bool(
                device is not None
                and device.instance_id.observed
                and device.instance_id.value
                == generic["candidate_record"]["os_instance_id"]
            )
            container_match = bool(
                device is not None
                and device.container_id.observed
                and len(containers) == 1
                and device.container_id.value in containers
            )
            if not exact:
                blockers.add("NATIVE_EXACT_ENDPOINT_NOT_OBSERVED")
            if not device_match:
                blockers.add("NATIVE_GENERIC_DEVICE_INSTANCE_MISMATCH")
            if not container_match:
                blockers.add("NATIVE_GENERIC_CONTAINER_MISMATCH")
            if (
                sum(
                    c.endpoint_sha256 == candidate.endpoint_sha256
                    for c in self._choices.values()
                )
                != 1
            ):
                blockers.add("NATIVE_ENDPOINT_OCCURRENCE_AMBIGUOUS")
            _require(
                len(blockers) <= 32,
                "REPORT_LIMIT",
                "Identity blockers exceed the display bound.",
            )
            self._identity_packet = _bytes(owned)
            self._identity = _bytes(
                {
                    "choice_id": choice_id,
                    "endpoint_sha256": candidate.endpoint_sha256,
                    "identity_sha256": hashlib.sha256(
                        self._identity_packet
                    ).hexdigest(),
                    "operation_id": operation,
                    "exact_endpoint_observed": exact,
                    "generic_device_match": device_match,
                    "container_match": container_match,
                    "blockers": sorted(blockers),
                }
            )
            self._reason = None
            return self._finish_mutation("identity")

    def review(self, choice_id: str, reviewer_id: str) -> dict[str, Any]:
        with self._lock:
            self.invalidate_review("NATIVE_ENDPOINT_REVIEW_NOT_VERIFIED")
            candidate = self.candidate(choice_id)
            reviewer = _text(reviewer_id)
            _require(
                self._identity is not None,
                "IDENTITY_NOT_RETAINED",
                "Retain exact native identity metadata before reviewing this endpoint.",
            )
            assert (
                self._identity is not None
                and self._generic is not None
                and self._inventory is not None
            )
            identity = json.loads(self._identity)
            _require(
                identity["choice_id"] == choice_id
                and identity["endpoint_sha256"] == candidate.endpoint_sha256,
                "IDENTITY_CHOICE_MISMATCH",
                "Retained identity belongs to a different endpoint choice.",
            )
            generic = json.loads(self._generic)
            accepted = (
                identity["exact_endpoint_observed"]
                and identity["generic_device_match"]
                and identity["container_match"]
                and not identity["blockers"]
            )
            binding_hash = None
            if accepted:
                payload = {
                    "schema": "rocell.wizard_camera_endpoint_binding.v1",
                    "status": "REVIEWED_ENDPOINT_METADATA_ONLY",
                    "mode": self._mode,
                    "session_id": self._session,
                    "source_sha256": self._source,
                    "provider": dict(self._descriptor or {}),
                    "generic_review_sha256": hashlib.sha256(self._generic).hexdigest(),
                    "generic_candidate_sha256": generic["candidate"][
                        "candidate_sha256"
                    ],
                    "generic_report_sha256": generic["report_sha256"],
                    "generic_operation_id": generic["operation_id"],
                    "inventory_sha256": hashlib.sha256(self._inventory).hexdigest(),
                    "inventory_operation_id": self._inventory_operation,
                    "identity_sha256": identity["identity_sha256"],
                    "identity_operation_id": identity["operation_id"],
                    "choice_id": choice_id,
                    "reviewer_id": reviewer,
                    "symbolic_link": candidate.symbolic_link,
                    "endpoint_sha256": candidate.endpoint_sha256,
                    "observed_instance_id": generic["candidate_record"][
                        "os_instance_id"
                    ],
                    "observed_container_id": next(iter(_container_ids(generic)[0])),
                    "blockers": self._blockers(),
                    "connected": False,
                    "qualified": False,
                    "persistent_binding": False,
                    "physical_authority": False,
                }
                binding_hash = _hash(payload)
                # Reuse the native client's exact symbolic-link/hash type;
                # possession of this value does not satisfy its authorizer.
                CameraEndpointBinding(
                    candidate.symbolic_link, candidate.endpoint_sha256, binding_hash
                )
                self._artifact = _bytes(
                    {"payload": payload, "binding_sha256": binding_hash}
                )
            self._review = _bytes(
                {
                    "choice_id": choice_id,
                    "reviewer_id": reviewer,
                    "binding_sha256": binding_hash,
                    "status": (
                        "REVIEWED_ENDPOINT_METADATA_ONLY"
                        if accepted
                        else "METADATA_ACKNOWLEDGED_BUT_HELD"
                    ),
                    "physical_authority": False,
                }
            )
            self._reason = None
            return self._finish_mutation("review")

    def binding(self) -> CameraEndpointBinding | None:
        with self._lock:
            if self._artifact is None:
                return None
            artifact = json.loads(self._artifact)
            payload = artifact["payload"]
            return CameraEndpointBinding(
                payload["symbolic_link"],
                payload["endpoint_sha256"],
                artifact["binding_sha256"],
            )

    def _provenance(self) -> dict[str, Any]:
        return {
            "mode": self._mode,
            "session_id": self._session,
            "source_sha256": self._source,
            "provider_provenance": (
                None if self._descriptor is None else self._descriptor["provenance"]
            ),
            "helper_sha256": (
                None if self._descriptor is None else self._descriptor["helper_sha256"]
            ),
            "scope": "NATIVE_ENDPOINT_METADATA_ONLY",
        }

    def _blockers(self) -> list[str]:
        blockers = set(_BASELINE_HOLDS)
        if self._descriptor is None:
            blockers.add("NATIVE_METADATA_PROVIDER_NOT_CONFIGURED")
        if self._generic is not None:
            generic = json.loads(self._generic)
            blockers.update(
                code
                for code in generic["inventory_report"]["blockers"]
                if code.startswith("CAMERA_")
                or code == "INVENTORY_ONLY_NOT_DEVICE_QUALIFICATION"
            )
            blockers.update(generic["candidate"]["identity_blockers"])
        if self._identity is not None:
            blockers.update(json.loads(self._identity)["blockers"])
        _require(
            len(blockers) <= 32,
            "REPORT_LIMIT",
            "Enrollment blockers exceed the display bound.",
        )
        return sorted(blockers)

    def view(self) -> dict[str, Any]:
        with self._lock:
            generic = None if self._generic is None else json.loads(self._generic)
            review = None if self._review is None else json.loads(self._review)
            status = (
                "PROVIDER_UNAVAILABLE"
                if self._descriptor is None
                else (
                    "INVALIDATED"
                    if self._inventory is None and self._reason is not None
                    else (
                        "NO_INVENTORY"
                        if self._inventory is None
                        else (
                            "ENDPOINT_METADATA_REVIEWED"
                            if review is not None and self._artifact is not None
                            else (
                                "REVIEW_HELD"
                                if review is not None
                                else (
                                    "IDENTITY_RETAINED"
                                    if self._identity is not None
                                    else "ENDPOINT_CHOICES_AVAILABLE"
                                )
                            )
                        )
                    )
                )
            )
            return {
                "schema": SCHEMA,
                "status": status,
                "provenance": self._provenance(),
                "inventory_sha256": (
                    None
                    if self._inventory is None
                    else hashlib.sha256(self._inventory).hexdigest()
                ),
                "inventory_operation_id": self._inventory_operation,
                "generic_candidate_sha256": (
                    None
                    if generic is None
                    else generic["candidate"]["candidate_sha256"]
                ),
                "generic_report_sha256": (
                    None if generic is None else generic["report_sha256"]
                ),
                "generic_operation_id": (
                    None if generic is None else generic["operation_id"]
                ),
                "candidates": [
                    {
                        "choice_id": token,
                        "friendly_name": c.friendly_name,
                        "endpoint_sha256": c.endpoint_sha256,
                    }
                    for token, c in self._choices.items()
                ],
                "identity": (
                    None if self._identity is None else json.loads(self._identity)
                ),
                "review": review,
                "blockers": self._blockers(),
                "connected": False,
                "qualified": False,
                "persistent_binding": False,
                "physical_authority": False,
                "invalidation_reason": self._reason,
            }

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return _owned(
                {
                    "schema": "rocell.wizard_native_camera_enrollment_report.v1",
                    "view": self.view(),
                    "generic_review": (
                        None if self._generic is None else json.loads(self._generic)
                    ),
                    "inventory_packet": (
                        None if self._inventory is None else json.loads(self._inventory)
                    ),
                    "identity_packet": (
                        None
                        if self._identity_packet is None
                        else json.loads(self._identity_packet)
                    ),
                    "binding_artifact": (
                        None if self._artifact is None else json.loads(self._artifact)
                    ),
                },
                MAX_REPORT_BYTES,
            )

    def _finish_mutation(self, scope: str) -> dict[str, Any]:
        # A result that cannot be retained must not leave a successful-looking
        # local state even if a caller is not using the staged-copy workflow.
        try:
            return self.export_snapshot()
        except NativeCameraEnrollmentError:
            if scope == "inventory":
                self.invalidate("NATIVE_INVENTORY_RESULT_NOT_RETAINED")
            elif scope == "identity":
                self.invalidate_identity("NATIVE_IDENTITY_RESULT_NOT_RETAINED")
            else:
                self.invalidate_review("NATIVE_REVIEW_RESULT_NOT_RETAINED")
            raise
