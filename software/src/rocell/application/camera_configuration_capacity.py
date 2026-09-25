"""Read-only headroom for one stage-5 settings capture, never disk reservation.

Account separately for native output, its ingested byte copy, preview and bridge
metadata, private native output and the remaining original campaign records.
Actual dataset publication independently checks its existing limits again.
"""

import os
import shutil
from typing import Any

from .camera_activation_campaign_contract import (
    CONFIGURATION_CAPTURE_ACTION_ID,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from .camera_capture_dataset import MAX_JSON_BYTES
from .camera_probe_capacity import (
    DISK_RESERVE_BYTES,
    PRIVATE_OUTPUT_HEADROOM_BYTES,
    _record_headroom,
)
from .commissioning_camera_persistence import M1PhysicalCameraTransaction
from .cell_commissioning_coordinator import RegisteredActionRequest
from .physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    CONFIGURATION_PLAN_SCHEMA,
    SEALED_CONFIGURATION_PLAN_SCHEMA,
)
from .physical_camera_capture_workflow import MAX_PREVIEW_BYTES
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2SessionSnapshot
from .windows_camera_capture_ingest import MAX_CONTRACT_BYTES
from .wizard_diagnostic_coordinator import require_regular_path
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.native_camera_protocol import canonical, digest

SCHEMA = "rocell.camera_configuration_capacity_observation.v1"
SEALED_SCHEMA = "rocell.camera_configuration_capacity_observation.v2"
# Dataset capture-plan/manifest and ingest source-contract/receipt, respectively.
METADATA_BYTES = 2 * MAX_JSON_BYTES + 2 * MAX_CONTRACT_BYTES


class CameraConfigurationCapacityError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CameraConfigurationCapacityError(code)


def configuration_output_budget(plan: dict[str, Any]) -> dict[str, int]:
    """Pure exact-plan validation and worst-case output sizes, not file I/O."""
    campaign = PhysicalCameraActivationCampaign.from_plan(plan)
    _need(
        (plan["schema"], campaign.registration().action_id)
        in (
            (CONFIGURATION_PLAN_SCHEMA, CONFIGURATION_CAPTURE_ACTION_ID),
            (SEALED_CONFIGURATION_PLAN_SCHEMA, SEALED_CONFIGURATION_CAPTURE_ACTION_ID),
        ),
        "CONFIGURATION_CAPACITY_EXACT_PROFILE_REQUIRED",
    )
    raw = plan["native_budget"]["max_total_bytes"]
    return dict(
        raw_frame_bytes=raw,
        ingested_frame_bytes=raw,
        preview_bytes=MAX_PREVIEW_BYTES,
        metadata_bytes=METADATA_BYTES,
        private_output_bytes=PRIVATE_OUTPUT_HEADROOM_BYTES,
    )


def observe_configuration_capacity(
    transaction: M1PhysicalCameraTransaction,
    *,
    plan: dict[str, Any],
    request_key: str,
) -> dict[str, Any]:
    """Check this original store's volume without making any output directory.

    The full output allowance remains required at subsequent checks; unverified
    or partially written files never earn capacity credit. This conservative
    floor can hold a nearly full volume after effects. It is not a guarantee or
    reservation of space, and it never authorizes deletion or automatic retry.
    """
    _need(
        type(transaction) is M1PhysicalCameraTransaction,
        "CONFIGURATION_CAPACITY_EXACT_TRANSACTION",
    )
    transaction._check_scope()
    snapshot = transaction.snapshot()
    return _capacity_from_current_records(
        transaction,
        plan=plan,
        request_key=request_key,
        snapshot=snapshot,
        records=transaction._audit_records(include_family=True),
    )


def _capacity_from_current_records(
    transaction: M1PhysicalCameraTransaction,
    *,
    plan: dict[str, Any],
    request_key: str,
    snapshot: V2SessionSnapshot,
    records: dict[str, Any],
) -> dict[str, Any]:
    """Same-call arithmetic and disk observation, not original authentication.

    The public observer above and original configuration guard supply their
    freshly audited records. Never retain/reuse this input across a boundary.
    Keeping this helper separate avoids re-reading the full ledger merely to
    calculate byte totals immediately after authenticating those same bytes.
    """
    _need(
        type(transaction) is M1PhysicalCameraTransaction
        and type(snapshot) is V2SessionSnapshot,
        "CONFIGURATION_CAPACITY_EXACT_TRANSACTION",
    )
    transaction._check_scope()
    budgets = configuration_output_budget(plan)
    sealed = plan["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA
    action_id = (
        SEALED_CONFIGURATION_CAPTURE_ACTION_ID
        if sealed
        else CONFIGURATION_CAPTURE_ACTION_ID
    )
    root = transaction._session.directory.parent
    output = root / "native-camera-output"
    _need(
        transaction.held_leases
        == (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
            LeaseSpec(LeaseLevel.CAMERA, snapshot.header.cell_id),
        )
        and plan["cell_id"] == snapshot.header.cell_id
        and plan["session_id"] == snapshot.header.session_id
        and plan["assigned_parent_directory"] == str(output),
        "CONFIGURATION_CAPACITY_ORIGINAL_CONTEXT",
    )
    RegisteredActionRequest(
        plan["cell_id"],
        plan["session_id"],
        action_id,
        request_key,
        digest(canonical(plan)),
    )
    headroom = _record_headroom(records, request_key, action_id=action_id)
    with _directory_guard(require_regular_path(root, directory=True)):
        if os.path.lexists(output):
            require_regular_path(output, directory=True)
            with _directory_guard(output):
                available = shutil.disk_usage(output).free
        else:
            available = shutil.disk_usage(root).free
    required = (
        DISK_RESERVE_BYTES + sum(budgets.values()) + headroom["remaining_record_bytes"]
    )
    _need(
        type(available) is int and required <= available < 2**63,
        "CONFIGURATION_CAPTURE_DISK_CAPACITY",
    )
    transaction._check_scope()
    return dict(
        schema=SEALED_SCHEMA if sealed else SCHEMA,
        plan_sha256=digest(canonical(plan)),
        request_key=request_key,
        assigned_output_parent=str(output),
        measured_free_bytes=available,
        required_free_bytes=required,
        disk_reserve_bytes=DISK_RESERVE_BYTES,
        output_budget=budgets,
        record_headroom=headroom,
        existing_output_credit_bytes=0,
        capacity_reserved=False,
        physical_authority=False,
        hardware_qualified=False,
        meaning="Observed conservative full-output headroom. Raw/ingested copies and metadata are included; partial output is not credited. Disk space is not reserved and current dataset limits remain enforced.",
    )
