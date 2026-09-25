"""Read-only output/record headroom for the fixed v2 probe, never a reservation.

The caller owns the exact CAMERA transaction and current original context. Disk
space can change externally; check again at each admission boundary. No folders,
temporary files, camera sources, processes or images are created here.
"""

import hashlib
import os
from pathlib import Path
import shutil
from typing import Any

from .camera_activation_campaign_contract import (
    ACTION_IDS,
    CONFIGURATION_CAPTURE_ACTION_ID,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from .camera_capture_checksum import MAX_BYTES as MAX_CHECKSUM_BYTES
from .camera_activation_campaign_evidence import ROLE_LIMITS
from .camera_activation_evidence_parts import PART_BYTES
from .commissioning_camera_persistence import M1PhysicalCameraTransaction
from .commissioning_m1_persistence import (
    MAX_RECORD_BYTES,
    MAX_RECORDS,
    MAX_RECORD_TOTAL_BYTES,
)
from .physical_onboarding_attempts import canonical_json_bytes
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2SessionSnapshot
from .wizard_diagnostic_coordinator import require_regular_path
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.native_camera_protocol import canonical, digest

SCHEMA = "rocell.camera_probe_capacity_observation.v1"
DISK_RESERVE_BYTES = 64 * 1024 * 1024
PRIVATE_OUTPUT_HEADROOM_BYTES = 16 * 1024 * 1024
# Bounded base64 parts plus fixed-field envelopes; the five other records are
# request, index, two lifecycle receipts and terminal result. Their existing
# complete record limits remain unchanged.
MAX_PART_RECORDS = sum(
    (limit + PART_BYTES - 1) // PART_BYTES for limit in ROLE_LIMITS.values()
)
PART_RECORD_BOUND = 4 * ((PART_BYTES + 2) // 3) + 4096
CAMPAIGN_RECORD_COUNT = MAX_PART_RECORDS + 5
CAMPAIGN_RECORD_BYTES = MAX_PART_RECORDS * PART_RECORD_BOUND + 5 * MAX_RECORD_BYTES
# The sealed profile replaces (does not append after) the old final index, whose
# complete 1 MiB allowance already covers both versions. Only one checksum part
# is additional. Existing record/family quotas are never increased.
SEALED_CAMPAIGN_RECORD_COUNT = CAMPAIGN_RECORD_COUNT + 1
CHECKSUM_RECORD_BOUND = 4 * ((MAX_CHECKSUM_BYTES + 2) // 3) + 4096
SEALED_CAMPAIGN_RECORD_BYTES = CAMPAIGN_RECORD_BYTES + CHECKSUM_RECORD_BOUND


class CameraProbeCapacityError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CameraProbeCapacityError(code)


def _record_headroom(
    records: dict[str, Any], request_key: str, *, action_id: str = ACTION_IDS["probe"]
) -> dict[str, int]:
    """Account for this request's already-written records without double debit."""
    # Shared arithmetic only. Callers independently validate their exact plan,
    # original namespace and leases; this selector is not admission authority.
    _need(
        action_id
        in {
            ACTION_IDS["probe"],
            CONFIGURATION_CAPTURE_ACTION_ID,
            SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
        },
        "CAMERA_CAPACITY_EXACT_ACTION_REQUIRED",
    )
    name = (
        "request-" + hashlib.sha256(request_key.encode("ascii")).hexdigest() + ".json"
    )
    reserved = records.get(name)
    attempt = None if reserved is None else reserved["data"]["attempt_id"]
    if reserved is not None:
        _need(
            reserved["data"]["request_key"] == request_key
            and reserved["data"]["permit"]["request"]["action_id"] == action_id,
            "CAMERA_PROBE_CAPACITY_REQUEST_CHANGED",
        )
    sizes = {key: len(canonical_json_bytes(record)) for key, record in records.items()}
    owned = {
        key
        for key, record in records.items()
        if attempt is not None and record["data"].get("attempt_id") == attempt
    }
    sealed = action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
    count_bound = SEALED_CAMPAIGN_RECORD_COUNT if sealed else CAMPAIGN_RECORD_COUNT
    byte_bound = SEALED_CAMPAIGN_RECORD_BYTES if sealed else CAMPAIGN_RECORD_BYTES
    remaining_count = max(0, count_bound - len(owned))
    remaining_bytes = max(0, byte_bound - sum(sizes[key] for key in owned))
    _need(
        len(records) + remaining_count <= MAX_RECORDS
        and sum(sizes.values()) + remaining_bytes <= MAX_RECORD_TOTAL_BYTES,
        "CAMERA_PROBE_RECORD_CAPACITY",
    )
    return dict(
        family_records=len(records),
        family_record_bytes=sum(sizes.values()),
        campaign_record_count_bound=count_bound,
        campaign_record_bytes_bound=byte_bound,
        remaining_record_count=remaining_count,
        remaining_record_bytes=remaining_bytes,
    )


def observe_probe_capacity(
    transaction: M1PhysicalCameraTransaction,
    *,
    plan: dict[str, Any],
    request_key: str,
) -> dict[str, Any]:
    """Measure only the authenticated store's fixed output volume and quotas.

    plan is the original factory-validated plan, not a browser pathname. Missing
    output parents are permitted because the campaign creates them in its own
    guarded lifecycle. Existing links/reparse points and non-directories are not.
    """
    _need(
        type(transaction) is M1PhysicalCameraTransaction,
        "CAMERA_PROBE_EXACT_TRANSACTION",
    )
    transaction._check_scope()
    snapshot = transaction.snapshot()
    # Keep the independent observer's original rejection order: a wrong scope,
    # plan or request is rejected before any family-record observation.
    _capacity_context(
        transaction, plan=plan, request_key=request_key, snapshot=snapshot
    )
    return _capacity_from_current_records(
        transaction,
        plan=plan,
        request_key=request_key,
        snapshot=snapshot,
        records=transaction._audit_records(include_family=True),
    )


def _capacity_context(
    transaction: M1PhysicalCameraTransaction,
    *,
    plan: dict[str, Any],
    request_key: str,
    snapshot: V2SessionSnapshot,
) -> Path:
    """Read-only exact scope/plan checks shared by the two observation paths."""
    _need(
        type(transaction) is M1PhysicalCameraTransaction
        and type(snapshot) is V2SessionSnapshot,
        "CAMERA_PROBE_EXACT_TRANSACTION",
    )
    transaction._check_scope()
    root = transaction._session.directory.parent
    _need(
        transaction.held_leases
        == (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
            LeaseSpec(LeaseLevel.CAMERA, snapshot.header.cell_id),
        )
        and plan["purpose"] == "probe"
        and plan["cell_id"] == snapshot.header.cell_id
        and plan["session_id"] == snapshot.header.session_id
        and plan["assigned_parent_directory"] == str(root / "native-camera-output"),
        "CAMERA_PROBE_CAPACITY_CONTEXT",
    )
    # RegisteredActionRequest supplies the same bounded identifier contract.
    from .cell_commissioning_coordinator import RegisteredActionRequest

    RegisteredActionRequest(
        plan["cell_id"],
        plan["session_id"],
        ACTION_IDS["probe"],
        request_key,
        digest(canonical(plan)),
    )
    return root


def _capacity_from_current_records(
    transaction: M1PhysicalCameraTransaction,
    *,
    plan: dict[str, Any],
    request_key: str,
    snapshot: V2SessionSnapshot,
    records: dict[str, Any],
) -> dict[str, Any]:
    """Same-call headroom from audited bytes, never original authentication.

    The independent observer above or original-bound probe callback supplies
    freshly audited full-family records. The callback retains its final full
    original audit after this disk observation, including sibling USB records.
    No input is saved for another admission boundary or used to renew a permit.
    """
    root = _capacity_context(
        transaction, plan=plan, request_key=request_key, snapshot=snapshot
    )
    headroom = _record_headroom(records, request_key)
    output = root / "native-camera-output"
    with _directory_guard(require_regular_path(root, directory=True)):
        if os.path.lexists(output):
            require_regular_path(output, directory=True)
            with _directory_guard(output):
                available = shutil.disk_usage(output).free
        else:
            available = shutil.disk_usage(root).free
    required = (
        DISK_RESERVE_BYTES
        + PRIVATE_OUTPUT_HEADROOM_BYTES
        + headroom["remaining_record_bytes"]
    )
    _need(
        type(available) is int and required <= available < 2**63,
        "CAMERA_PROBE_DISK_CAPACITY",
    )
    transaction._check_scope()
    return dict(
        schema=SCHEMA,
        plan_sha256=digest(canonical(plan)),
        request_key=request_key,
        assigned_output_parent=str(output),
        measured_free_bytes=available,
        required_free_bytes=required,
        disk_reserve_bytes=DISK_RESERVE_BYTES,
        private_output_headroom_bytes=PRIVATE_OUTPUT_HEADROOM_BYTES,
        record_headroom=headroom,
        frame_output_bytes=0,
        capacity_reserved=False,
        physical_authority=False,
        hardware_qualified=False,
        meaning="Read-only current headroom, not allocated space or a device permit. Existing record/part budgets remain enforced by storage.",
    )
