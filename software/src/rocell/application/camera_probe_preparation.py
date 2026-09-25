"""Original-record subjects for the wizard's initial bounded camera probe.

These pure codecs bind current enrollment, the exact operation, and installed
software observations. They cannot authenticate a copied report, perform I/O,
approve a physical stage, or replace original-store admission and current checks.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

from .camera_activation_expectation import expectation_from_enrollment_snapshot
from .camera_activation_runtime_policy import (
    REVIEW_SCHEMA,
    MAX_NATIVE_READ_BYTES,
    MAX_NATIVE_READ_CALLS,
    MAX_CHECK_NS,
    reviewed_activation_runtime_candidate,
)
from .physical_camera_activation_campaign import PhysicalCameraActivationCampaign
from .physical_camera_mode_entry import camera_mode_operator_valid
from .physical_camera_selection import selection_from_enrollment_snapshot
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import decode_owned_json

PREPARATION_SCHEMA = "rocell.camera_probe_preparation.v1"
REVIEW_SCHEMA_ID = "rocell.camera_probe_preparation_review.v1"
SOURCE_WORKFLOW_PROBE_SCHEMA = "rocell.physical_camera_source_workflow_readback.v16"
# ASCII canonical encoding can be larger than the enrollment's UTF-8 report.
# This record's cap is separate from the enrollment and legacy stage-5 caps.
MAX_PREPARATION_BYTES = 3 * 1024 * 1024
MAX_PREPARATION_NODES = 40_000
MAX_PREPARATION_DEPTH = 26
MAX_REVIEW_BYTES = 16 * 1024
PREPARATION_LABEL = re.compile(
    r"camera-probe-preparation-v1:(cameraprobe-[0-9a-f]{32})\Z"
)
REVIEW_LABEL = re.compile(r"camera-probe-review-v1:(cameraprobe-[0-9a-f]{32})\Z")
PROBE_EVENT = re.compile(r"CAMERA_PROBE_(PREPARED|REVIEWED)_([0-9A-F]{32})\Z")
_ID = re.compile(r"cameraprobe-[0-9a-f]{32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "connected": False,
    "native_release_allowed": False,
    "device_io_performed": False,
    "authenticated_operator_identity": False,
}
_SOFTWARE_FIELDS = {
    "schema",
    "status",
    "purpose",
    "runtime_registration_sha256",
    "catalog_sha256",
    "source_sha256",
    "files_checked",
    "bytes_read",
    "read_calls",
    "elapsed_ns",
    "original_context_authenticated",
    "physical_authority",
    "connected",
    "hardware_qualified",
    "device_operations",
}


class CameraProbePreparationError(ValueError):
    def __init__(self, code: str = "CAMERA_PROBE_PREPARATION_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _need(ok: bool, code: str = "CAMERA_PROBE_PREPARATION_INVALID") -> None:
    if not ok:
        raise CameraProbePreparationError(code)


def _sha(value: Any) -> None:
    _need(
        type(value) is str and _HASH.fullmatch(value) is not None and value != "0" * 64
    )


def _identifier(value: Any) -> None:
    _need(type(value) is str and _ID.fullmatch(value) is not None)


def _time(value: Any) -> None:
    _need(type(value) is int and 0 < value < 2**63)


def _software(value: Any, *, workspace: Path, source: str, purpose: str) -> None:
    _need(type(value) is dict and set(value) == _SOFTWARE_FIELDS)
    runtime = reviewed_activation_runtime_candidate(
        workspace, purpose=purpose, source_sha256=source
    )
    registration = runtime.to_dict()
    _need(
        value["schema"] == REVIEW_SCHEMA
        and value["status"] == "REVIEWED_SOFTWARE_MATCHED"
        and value["purpose"] == purpose
        and value["runtime_registration_sha256"] == runtime.registration_sha256
        and value["source_sha256"] == source
        and value["catalog_sha256"] == registration["catalog_sha256"]
        and all(
            value[key] is False
            for key in (
                "original_context_authenticated",
                "physical_authority",
                "connected",
                "hardware_qualified",
            )
        )
        and type(value["device_operations"]) is int
        and value["device_operations"] == 0,
        "CAMERA_PROBE_SOFTWARE_OBSERVATION_MISMATCH",
    )
    for key, low, high in (
        ("files_checked", 26, 26),
        ("bytes_read", 1, MAX_NATIVE_READ_BYTES),
        ("read_calls", 26, MAX_NATIVE_READ_CALLS),
        ("elapsed_ns", 0, MAX_CHECK_NS),
    ):
        _need(
            type(value[key]) is int and low <= value[key] <= high,
            "CAMERA_PROBE_SOFTWARE_OBSERVATION_MISMATCH",
        )


def _decode_preparation(payload: bytes) -> dict[str, Any]:
    try:
        value = _decode_preparation_document(payload)
        _need(
            canonical(value) == payload
            and set(value)
            == {
                "schema",
                "preparation_id",
                "entry_sha256",
                "entry_event_sha256",
                "plan",
                "enrollment",
                "software",
                "operator_id",
                "prepared_at_utc_ns",
                *_FLAGS,
            }
        )
        _need(
            value["schema"] == PREPARATION_SCHEMA
            and all(value[key] is False for key in _FLAGS)
        )
        _identifier(value["preparation_id"])
        _sha(value["entry_sha256"])
        _sha(value["entry_event_sha256"])
        _time(value["prepared_at_utc_ns"])
        _need(camera_mode_operator_valid(value["operator_id"]))
        campaign = PhysicalCameraActivationCampaign.from_plan(value["plan"])
        plan = campaign.plan()
        _need(plan["purpose"] == "probe", "INITIAL_CAMERA_PROBE_REQUIRED")
        workspace, source, launch = (
            Path(plan["workspace"]),
            plan["source_sha256"],
            plan["launch_session_id"],
        )
        verified = verify_native_camera_enrollment_snapshot(
            value["enrollment"], source_sha256=source, launch_session_id=launch
        )
        selected = selection_from_enrollment_snapshot(
            verified, source_sha256=source, launch_session_id=launch
        )
        expectation = expectation_from_enrollment_snapshot(
            verified, source_sha256=source, launch_session_id=launch
        )
        _need(
            selected is not None
            and selected.identity_document == plan["selection"]
            and expectation.to_dict() == plan["expectation"],
            "CAMERA_PROBE_ENROLLMENT_PLAN_MISMATCH",
        )
        installed = reviewed_activation_runtime_candidate(
            workspace, purpose="probe", source_sha256=source
        )
        _need(
            plan["runtime"] == installed.to_dict(),
            "CAMERA_PROBE_INSTALLED_RUNTIME_REQUIRED",
        )
        _need(
            type(value["software"]) is dict
            and set(value["software"]) == {"probe", "capture"}
        )
        for purpose in ("probe", "capture"):
            _software(
                value["software"][purpose],
                workspace=workspace,
                source=source,
                purpose=purpose,
            )
        return value
    except CameraProbePreparationError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
    ) as error:
        raise CameraProbePreparationError() from error


def _decode_preparation_document(payload: bytes) -> dict[str, Any]:
    """Bound the compound record without relaxing the worker IPC decoder.

    Enrollment alone permits 32,000 nodes. Its enclosing plan and observations
    need a separate finite allowance; each nested subject is still validated by
    its existing codec. This parser provides no original-store authentication.
    """
    _need(type(payload) is bytes and 0 < len(payload) <= MAX_PREPARATION_BYTES)

    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result)
            result[key] = value
        return result

    def bad_constant(_):
        raise CameraProbePreparationError()

    value = json.loads(
        payload.decode("ascii"), object_pairs_hook=pairs, parse_constant=bad_constant
    )
    _need(type(value) is dict)
    pending, nodes = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        _need(nodes <= MAX_PREPARATION_NODES and depth <= MAX_PREPARATION_DEPTH)
        if type(item) is dict:
            for key, child in item.items():
                pending.extend(((key, depth + 1), (child, depth + 1)))
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is float:
            _need(math.isfinite(item))
        else:
            _need(item is None or type(item) in {str, int, bool})
    return value


@dataclass(frozen=True, slots=True)
class CameraProbePreparation:
    payload: bytes

    def __post_init__(self) -> None:
        _decode_preparation(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _decode_preparation(self.payload)


def build_camera_probe_preparation(
    *,
    preparation_id: str,
    entry_sha256: str,
    entry_event_sha256: str,
    plan: dict[str, Any],
    enrollment: dict[str, Any],
    software: dict[str, Any],
    operator_id: str,
    prepared_at_utc_ns: int,
) -> CameraProbePreparation:
    """Encode owner-collected observations, not an original-admission decision."""
    return CameraProbePreparation(
        canonical(
            dict(
                schema=PREPARATION_SCHEMA,
                preparation_id=preparation_id,
                entry_sha256=entry_sha256,
                entry_event_sha256=entry_event_sha256,
                plan=plan,
                enrollment=enrollment,
                software=software,
                operator_id=operator_id,
                prepared_at_utc_ns=prepared_at_utc_ns,
                **_FLAGS,
            )
        )
    )


def _decode_review(payload: bytes) -> dict[str, Any]:
    try:
        value = decode_owned_json(payload, maximum=MAX_REVIEW_BYTES)
        _need(
            canonical(value) == payload
            and set(value)
            == {
                "schema",
                "preparation_id",
                "preparation_sha256",
                "reviewer_id",
                "reviewed_at_utc_ns",
                "decision",
                *_FLAGS,
            }
        )
        _need(
            value["schema"] == REVIEW_SCHEMA_ID
            and value["decision"] == "REQUEST_BOUNDED_PROBE"
        )
        _need(all(value[key] is False for key in _FLAGS))
        _identifier(value["preparation_id"])
        _sha(value["preparation_sha256"])
        _time(value["reviewed_at_utc_ns"])
        _need(camera_mode_operator_valid(value["reviewer_id"]))
        return value
    except CameraProbePreparationError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as error:
        raise CameraProbePreparationError() from error


@dataclass(frozen=True, slots=True)
class CameraProbePreparationReview:
    payload: bytes

    def __post_init__(self) -> None:
        _decode_review(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _decode_review(self.payload)


def build_camera_probe_preparation_review(
    preparation: CameraProbePreparation,
    *,
    reviewer_id: str,
    reviewed_at_utc_ns: int,
) -> CameraProbePreparationReview:
    _need(type(preparation) is CameraProbePreparation)
    data = preparation.to_dict()
    _need(
        type(reviewed_at_utc_ns) is int
        and reviewed_at_utc_ns >= data["prepared_at_utc_ns"]
    )
    return CameraProbePreparationReview(
        canonical(
            dict(
                schema=REVIEW_SCHEMA_ID,
                preparation_id=data["preparation_id"],
                preparation_sha256=preparation.sha256,
                reviewer_id=reviewer_id,
                reviewed_at_utc_ns=reviewed_at_utc_ns,
                decision="REQUEST_BOUNDED_PROBE",
                **_FLAGS,
            )
        )
    )


def camera_probe_event(kind: str, preparation_id: str) -> str:
    _need(type(kind) is str and kind in {"PREPARED", "REVIEWED"})
    _identifier(preparation_id)
    return "CAMERA_PROBE_" + kind + "_" + preparation_id[len("cameraprobe-") :].upper()


def camera_probe_label(kind: str, preparation_id: str) -> str:
    _need(type(kind) is str and kind in {"preparation", "review"})
    _identifier(preparation_id)
    return "camera-probe-" + kind + "-v1:" + preparation_id
