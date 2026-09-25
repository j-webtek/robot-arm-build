"""Pure metadata-selection bridge from UTF-8 enrollment to ASCII M1 identity.

No device is selected by name, index or lookup here. An exact current enrollment
supplies the opaque endpoint and its original review hash. The new domain binds
that unchanged review into one canonical ASCII identity document; it does not
upgrade metadata review into received-unit qualification or activation authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
    _container_ids,
    _generic_review,
    _UNRELATED_IDENTITY_HOLDS,
    verify_native_camera_enrollment_snapshot,
)
from rocell.application.wizard_native_camera_metadata import validate_native_packet
from rocell.providers.windows.camera_worker_client import (
    CameraEndpointBinding,
    CameraWorkerError,
    NativeCameraIdentityReceipt,
    NativeCameraReceipt,
)

SCHEMA = "rocell.physical_camera_selection.v1"
MAX_SELECTION_BYTES = 64 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FLAGS = {"connected", "qualified", "persistent_binding", "physical_authority"}
_REVIEW_FIELDS = {
    "schema",
    "status",
    "mode",
    "session_id",
    "source_sha256",
    "provider",
    "generic_review_sha256",
    "generic_candidate_sha256",
    "generic_report_sha256",
    "generic_operation_id",
    "inventory_sha256",
    "inventory_operation_id",
    "identity_sha256",
    "identity_operation_id",
    "choice_id",
    "reviewer_id",
    "symbolic_link",
    "endpoint_sha256",
    "observed_instance_id",
    "observed_container_id",
    "blockers",
    *_FLAGS,
}
_FIELDS = {
    "schema",
    "status",
    "mode",
    "source_sha256",
    "launch_session_id",
    "symbolic_link",
    "endpoint_sha256",
    "metadata_review_binding_sha256",
    "generic_candidate_sha256",
    "generic_report_sha256",
    "generic_review_sha256",
    "native_inventory_sha256",
    "native_identity_sha256",
    "metadata_review",
    *_FLAGS,
}
_VIEW_FIELDS = {
    "schema",
    "status",
    "provenance",
    "inventory_sha256",
    "inventory_operation_id",
    "generic_candidate_sha256",
    "generic_report_sha256",
    "generic_operation_id",
    "candidates",
    "identity",
    "review",
    "blockers",
    "invalidation_reason",
    *_FLAGS,
}


class PhysicalCameraSelectionError(ValueError):
    """Fixed public error without raw endpoint/provider exception text."""

    def __init__(self, code: str = "INVALID_PHYSICAL_CAMERA_SELECTION") -> None:
        self.code = code
        super().__init__("Exact current physical camera metadata review is required.")


def _require(value: bool, code: str = "INVALID_PHYSICAL_CAMERA_SELECTION") -> None:
    if not value:
        raise PhysicalCameraSelectionError(code)


def _canonical(value: Any, *, ascii: bool = True) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=ascii,
        allow_nan=False,
    ).encode("ascii" if ascii else "utf-8")


def _hash(value: Any, *, ascii: bool = True) -> str:
    return hashlib.sha256(_canonical(value, ascii=ascii)).hexdigest()


def _sha(value: Any) -> None:
    _require(type(value) is str and _SHA.fullmatch(value) is not None)


def _text(value: Any, maximum: int = 128) -> None:
    _require(type(value) is str and bool(value))
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise PhysicalCameraSelectionError() from None
    _require(
        len(encoded) <= maximum and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return value


def _validate(document: Any) -> dict[str, Any]:
    data = _exact(document, _FIELDS)
    _require(
        data["schema"] == SCHEMA
        and data["mode"] == "physical"
        and data["status"] == "REVIEWED_ENDPOINT_METADATA_ONLY"
    )
    _text(data["launch_session_id"])
    for key in _FLAGS:
        _require(data[key] is False)
    for key in _FIELDS:
        if key.endswith("sha256"):
            _sha(data[key])
    _text(data["symbolic_link"], 4096)
    review = _exact(data["metadata_review"], _REVIEW_FIELDS)
    _require(
        review["schema"] == "rocell.wizard_camera_endpoint_binding.v1"
        and review["mode"] == "physical"
        and review["status"] == "REVIEWED_ENDPOINT_METADATA_ONLY"
        and review["session_id"] == data["launch_session_id"]
        and review["source_sha256"] == data["source_sha256"]
    )
    provider = _exact(review["provider"], {"provenance", "helper_sha256"})
    _require(provider["provenance"] == "WINDOWS_NATIVE_METADATA")
    _sha(provider["helper_sha256"])
    for key in _FLAGS:
        _require(review[key] is False)
    for key in _REVIEW_FIELDS:
        if key.endswith("sha256"):
            _sha(review[key])
    for key in (
        "generic_operation_id",
        "inventory_operation_id",
        "identity_operation_id",
        "choice_id",
        "reviewer_id",
    ):
        _text(review[key])
    _text(review["observed_instance_id"], 4096)
    _require(
        type(review["observed_container_id"]) is str
        and re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            review["observed_container_id"],
        )
        is not None
    )
    holds = review["blockers"]
    _require(type(holds) is list and 1 <= len(holds) <= 32)
    for hold in holds:
        _text(hold)
        _require(re.fullmatch(r"[A-Z][A-Z0-9_]*", hold) is not None)
    _require(
        holds == sorted(set(holds))
        and {
            "CAMERA_NOT_CONNECTED",
            "CAMERA_NOT_QUALIFIED",
            "PHYSICAL_STAGE_GATES_REMAIN_HELD",
        }
        <= set(holds)
    )
    for original, selected in (
        ("symbolic_link", "symbolic_link"),
        ("endpoint_sha256", "endpoint_sha256"),
        ("generic_candidate_sha256", "generic_candidate_sha256"),
        ("generic_report_sha256", "generic_report_sha256"),
        ("generic_review_sha256", "generic_review_sha256"),
        ("inventory_sha256", "native_inventory_sha256"),
        ("identity_sha256", "native_identity_sha256"),
    ):
        _require(review[original] == data[selected])
    _require(
        _hash(review, ascii=False) == data["metadata_review_binding_sha256"],
        "ORIGINAL_METADATA_REVIEW_HASH_MISMATCH",
    )
    CameraEndpointBinding(
        data["symbolic_link"],
        data["endpoint_sha256"],
        data["metadata_review_binding_sha256"],
    )
    return data


def _decode(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 1 <= len(payload) <= MAX_SELECTION_BYTES,
        "SELECTION_BYTE_LIMIT",
    )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_SELECTION_FIELD")
            result[key] = value
        return result

    try:
        document = json.loads(payload.decode("ascii"), object_pairs_hook=pairs)
        _require(_canonical(document) == payload, "NONCANONICAL_SELECTION")
        return _validate(document)
    except PhysicalCameraSelectionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        UnicodeError,
        CameraWorkerError,
    ):
        raise PhysicalCameraSelectionError() from None


@dataclass(frozen=True, slots=True)
class PhysicalCameraSelection:
    """Immutable ASCII identity; direct restoration is not origin authentication."""

    payload: bytes

    def __post_init__(self) -> None:
        _decode(self.payload)

    @property
    def identity_document(self) -> dict[str, Any]:
        return _decode(self.payload)

    @property
    def sha256(self) -> str:
        _decode(self.payload)
        return hashlib.sha256(self.payload).hexdigest()

    @property
    def binding(self) -> CameraEndpointBinding:
        document = self.identity_document
        return CameraEndpointBinding(
            document["symbolic_link"], document["endpoint_sha256"], self.sha256
        )

    def safe_summary(self) -> dict[str, Any]:
        document = self.identity_document
        return {
            "endpoint_sha256": document["endpoint_sha256"],
            "identity_sha256": self.sha256,
            "metadata_review_binding_sha256": document[
                "metadata_review_binding_sha256"
            ],
            "generic_candidate_sha256": document["generic_candidate_sha256"],
        }


def selection_from_enrollment(
    enrollment: WizardNativeCameraEnrollment,
    *,
    source_sha256: str,
    launch_session_id: str,
) -> PhysicalCameraSelection:
    """Snapshot current reviewed metadata; never choose or review a candidate.

    The staged copy gives one coherent point-in-time view. The caller must bind
    it to its operation and recheck current enrollment before later admission.
    """
    _require(
        type(enrollment) is WizardNativeCameraEnrollment, "EXACT_ENROLLMENT_REQUIRED"
    )
    _sha(source_sha256)
    _text(launch_session_id)
    try:
        snapshot_owner = enrollment.staged_copy()
        snapshot = snapshot_owner.export_snapshot()
        selected = selection_from_enrollment_snapshot(
            snapshot,
            source_sha256=source_sha256,
            launch_session_id=launch_session_id,
        )
        _require(selected is not None, "ENDPOINT_REVIEW_REQUIRED")
        assert selected is not None
        current = snapshot_owner.binding()
        review = selected.identity_document["metadata_review"]
        _require(
            type(current) is CameraEndpointBinding
            and current.symbolic_link == selected.binding.symbolic_link
            and current.endpoint_sha256 == selected.binding.endpoint_sha256
            and current.binding_sha256 == _hash(review, ascii=False),
            "ENROLLMENT_BINDING_MISMATCH",
        )
        return selected
    except PhysicalCameraSelectionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise PhysicalCameraSelectionError() from None


def selection_from_enrollment_snapshot(
    snapshot: object, *, source_sha256: str, launch_session_id: str
) -> PhysicalCameraSelection | None:
    """Verify retained physical metadata; held reviews have no selection.

    This pure conversion does not restore live enrollment or establish current
    attachment. Original source/launch and all old eligibility checks remain
    mandatory. A caller retaining held evidence must not treat None as a choice.
    """
    _sha(source_sha256)
    _text(launch_session_id)
    try:
        snapshot = _exact(
            verify_native_camera_enrollment_snapshot(
                snapshot,
                source_sha256=source_sha256,
                launch_session_id=launch_session_id,
            ),
            {
                "schema",
                "view",
                "generic_review",
                "inventory_packet",
                "identity_packet",
                "binding_artifact",
            },
        )
        provenance = snapshot["view"]["provenance"]
        _require(
            provenance["mode"] == "physical",
            "ENROLLMENT_SOURCE_SESSION_DOMAIN_MISMATCH",
        )
        if snapshot["view"]["status"] == "REVIEW_HELD":
            return None
        _require(
            snapshot["schema"] == "rocell.wizard_native_camera_enrollment_report.v1"
        )
        view = _exact(snapshot["view"], _VIEW_FIELDS)
        _require(
            view["schema"] == "rocell.wizard_native_camera_enrollment.v1"
            and view["status"] == "ENDPOINT_METADATA_REVIEWED"
            and view["invalidation_reason"] is None,
            "ENDPOINT_REVIEW_REQUIRED",
        )
        provenance = _exact(
            view["provenance"],
            {
                "mode",
                "session_id",
                "source_sha256",
                "provider_provenance",
                "helper_sha256",
                "scope",
            },
        )
        _require(
            provenance["mode"] == "physical"
            and provenance["session_id"] == launch_session_id
            and provenance["source_sha256"] == source_sha256
            and provenance["provider_provenance"] == "WINDOWS_NATIVE_METADATA"
            and provenance["scope"] == "NATIVE_ENDPOINT_METADATA_ONLY",
            "ENROLLMENT_SOURCE_SESSION_DOMAIN_MISMATCH",
        )
        for flag in _FLAGS:
            _require(view[flag] is False)
        artifact = _exact(snapshot["binding_artifact"], {"payload", "binding_sha256"})
        review = _exact(artifact["payload"], _REVIEW_FIELDS)
        _require(
            _hash(review, ascii=False) == artifact["binding_sha256"],
            "ORIGINAL_METADATA_REVIEW_HASH_MISMATCH",
        )
        current = CameraEndpointBinding(
            review["symbolic_link"],
            review["endpoint_sha256"],
            artifact["binding_sha256"],
        )
        _require(type(current) is CameraEndpointBinding and current is not None)
        assert current is not None
        _require(
            current.symbolic_link == review["symbolic_link"]
            and current.endpoint_sha256 == review["endpoint_sha256"]
            and current.binding_sha256 == artifact["binding_sha256"],
            "ENROLLMENT_BINDING_MISMATCH",
        )
        identity = _exact(
            view["identity"],
            {
                "choice_id",
                "endpoint_sha256",
                "identity_sha256",
                "operation_id",
                "exact_endpoint_observed",
                "generic_device_match",
                "container_match",
                "blockers",
            },
        )
        acknowledged = _exact(
            view["review"],
            {
                "choice_id",
                "reviewer_id",
                "binding_sha256",
                "status",
                "physical_authority",
            },
        )
        _require(
            acknowledged["status"] == "REVIEWED_ENDPOINT_METADATA_ONLY"
            and acknowledged["physical_authority"] is False
            and acknowledged["choice_id"]
            == identity["choice_id"]
            == review["choice_id"]
            and acknowledged["reviewer_id"] == review["reviewer_id"]
            and acknowledged["binding_sha256"] == artifact["binding_sha256"]
            and identity["endpoint_sha256"] == current.endpoint_sha256
            and identity["identity_sha256"] == review["identity_sha256"]
            and identity["operation_id"] == review["identity_operation_id"]
            and identity["blockers"] == []
            and all(
                identity[field] is True
                for field in (
                    "exact_endpoint_observed",
                    "generic_device_match",
                    "container_match",
                )
            )
        )
        generic = _generic_review(
            snapshot["generic_review"], "physical", launch_session_id, source_sha256
        )
        containers, identity_holds = _container_ids(generic)
        _require(
            containers == {review["observed_container_id"]}
            and not identity_holds
            and not (
                set(generic["candidate"]["identity_blockers"])
                - _UNRELATED_IDENTITY_HOLDS
            )
        )
        for name, hash_key in (
            ("generic_review", "generic_review_sha256"),
            ("inventory_packet", "inventory_sha256"),
            ("identity_packet", "identity_sha256"),
        ):
            _require(
                _hash(snapshot[name], ascii=False) == review[hash_key],
                "ENROLLMENT_EVIDENCE_HASH_MISMATCH",
            )
        _require(
            generic["candidate"]["candidate_sha256"]
            == view["generic_candidate_sha256"]
            == review["generic_candidate_sha256"]
            and generic["report_sha256"]
            == view["generic_report_sha256"]
            == review["generic_report_sha256"]
            and generic["operation_id"]
            == view["generic_operation_id"]
            == review["generic_operation_id"]
            and view["inventory_sha256"] == review["inventory_sha256"]
            and view["inventory_operation_id"] == review["inventory_operation_id"]
            and view["blockers"] == review["blockers"]
        )
        descriptor = review["provider"]
        _require(
            descriptor
            == {
                "provenance": provenance["provider_provenance"],
                "helper_sha256": provenance["helper_sha256"],
            }
        )
        _, inventory = validate_native_packet(
            snapshot["inventory_packet"], kind="inventory", **descriptor
        )
        _, observed = validate_native_packet(
            snapshot["identity_packet"],
            kind="identity",
            expected_endpoint=current.symbolic_link,
            **descriptor,
        )
        _require(
            type(inventory) is NativeCameraReceipt
            and type(observed) is NativeCameraIdentityReceipt
        )
        assert isinstance(inventory, NativeCameraReceipt)
        assert isinstance(observed, NativeCameraIdentityReceipt)
        candidates = view["candidates"]
        _require(type(candidates) is list and 1 <= len(candidates) <= 128)
        for candidate in candidates:
            _exact(candidate, {"choice_id", "friendly_name", "endpoint_sha256"})
            _text(candidate["choice_id"])
            _text(candidate["friendly_name"], 1024)
            _sha(candidate["endpoint_sha256"])
        _require(
            len({c["choice_id"] for c in candidates}) == len(candidates)
            and sum(
                c["choice_id"] == review["choice_id"]
                and c["endpoint_sha256"] == current.endpoint_sha256
                for c in candidates
            )
            == 1
        )
        _require(
            sum(c.symbolic_link == current.symbolic_link for c in inventory.candidates)
            == 1
        )
        _require(
            observed.exact_endpoint_observed
            and observed.device is not None
            and observed.device.instance_id.observed
            and observed.device.instance_id.value
            == review["observed_instance_id"]
            == generic["candidate_record"]["os_instance_id"]
            and observed.device.container_id.observed
            and observed.device.container_id.value == review["observed_container_id"]
        )
        selected = {
            "schema": SCHEMA,
            "status": "REVIEWED_ENDPOINT_METADATA_ONLY",
            "mode": "physical",
            "source_sha256": source_sha256,
            "launch_session_id": launch_session_id,
            "symbolic_link": current.symbolic_link,
            "endpoint_sha256": current.endpoint_sha256,
            "metadata_review_binding_sha256": artifact["binding_sha256"],
            "generic_candidate_sha256": review["generic_candidate_sha256"],
            "generic_report_sha256": review["generic_report_sha256"],
            "generic_review_sha256": review["generic_review_sha256"],
            "native_inventory_sha256": review["inventory_sha256"],
            "native_identity_sha256": review["identity_sha256"],
            "metadata_review": review,
            **{flag: False for flag in _FLAGS},
        }
        return PhysicalCameraSelection(_canonical(selected))
    except PhysicalCameraSelectionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        CameraWorkerError,
    ):
        raise PhysicalCameraSelectionError() from None
