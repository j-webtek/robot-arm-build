"""Explicit real-host ownership experiments; never a physical release credential.

The closed child uses real ordered Windows leases. A separate original M1
NO_DEVICE_IO session proves durable consumption and no automatic replay. No
pytest, device provider, serial port or camera helper participates. Historical
reports are pure checked observations, not a portable execution authorization.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
import base64
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
from threading import Event
import time
from typing import Any, cast

from rocell.application.cell_commissioning_coordinator import (
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningCoordinatorError,
    CommissioningPersistence,
    ExactOperationPermit,
    ObservedPowerState,
    PhysicalDiagnosticPreflightCoordinator,
    RegisteredActionRequest,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from rocell.application.commissioning_physical_persistence import (
    M1PhysicalDiagnosticPersistence,
    PhysicalDiagnosticAdmissionFacts,
    decode_physical_diagnostic_permit,
    physical_diagnostic_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_durability import (
    DurabilityQualificationReport,
    PublicationMode,
    canonical_sha256,
    publish_canonical_json,
    run_on_volume_startup_self_test,
    safe_root,
)
from rocell.application.physical_onboarding_leases import (
    LeaseBusyError,
    LeaseLevel,
    LeaseOwnerMetadata,
    LeaseOwnerState,
    LeaseSpec,
    OnboardingLeaseManager,
    PriorOwnerProcessState,
    StaleLeaseOwnerError,
    classify_prior_owner_process,
    process_start_identity,
)
from rocell.application.physical_onboarding_m1 import (
    M1CellDescriptor,
    M1RuntimeVerification,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_diagnostic_coordinator import (
    require_regular_path,
    source_fingerprint,
)
from rocell.application.wizard_diagnostic_export import _directory_guard
from rocell.providers.windows import owned_worker_process as shared_process
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
)
from rocell.safety.effects import EffectCertainty, EffectClass


SCHEMA = "rocell.physical_ownership_qualification.v1"
SUMMARY_SCHEMA = "rocell.physical_ownership_qualification_summary.v1"
MAX_REPORT_BYTES = 128 * 1024
MAX_DURATION_NS = 120_000_000_000
CHILD_PATH = "software/src/rocell/application/_physical_ownership_child.py"
CHECK_IDS = (
    "DURABILITY_LOCKING",
    "ORDERED_CROSS_PROCESS_OWNERSHIP",
    "LIVE_CONTENDER_DENIED",
    "CLEAN_RELEASE_LINEAGE",
    "CRASH_STALE_OWNER_DENIED",
    "INJECTED_PROCESS_START_MISMATCH_DENIED",
    "ORIGINAL_M1_NO_REPLAY",
)
RESIDUALS = (
    "SELECTED_DEVICE_IDENTITY_AFTER_EFFECTFUL_LOCK",
    "RECEIVED_HARDWARE_HZ012_RESIDUAL",
    "NATIVE_RUNTIME_RELEASE_QUALIFICATION",
)
ZERO_EFFECTS = {
    "device_opens": 0,
    "serial_writes": 0,
    "power_events": 0,
    "motion_commands": 0,
    "contact_commands": 0,
}
_MODULES = ("physical_onboarding_durability", "physical_onboarding_leases")
_ACTION = "ownership-no-device-once"
_EVIDENCE_SCHEMA = "rocell.ownership_no_device_attempt.v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class PhysicalOwnershipQualificationError(ValueError):
    """Failure retains the complete bounded historical observation so far."""

    def __init__(self, code: str, report: PhysicalOwnershipQualification | None = None):
        super().__init__(code)
        self.code, self.report = code, report


def _require(ok: bool, code: str = "OWNERSHIP_REPORT_CONTRACT") -> None:
    if not ok:
        raise PhysicalOwnershipQualificationError(code)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object) -> None:
    _require(type(value) is str and bool(_HASH.fullmatch(value)) and value != "0" * 64)


def _path(value: object) -> PureWindowsPath:
    _require(type(value) is str and 3 < len(value) <= 2048)
    path = PureWindowsPath(cast(str, value))
    _require(
        path.is_absolute()
        and not path.drive.startswith("\\")
        and str(path) == value
        and ".." not in path.parts
        and path != PureWindowsPath(path.anchor)
        and not any(":" in part for part in path.parts[1:])
    )
    return path


def _object(value: object, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return cast(dict[str, Any], value)


def _owners(
    rows: object, *, source: str, phase: str, state: LeaseOwnerState
) -> list[LeaseOwnerMetadata]:
    _require(type(rows) is list and len(rows) == 4)
    result = [LeaseOwnerMetadata.from_dict(row) for row in cast(list, rows)]
    for level, owner in zip(LeaseLevel, result):
        _require(
            owner.level is level
            and owner.resource_id == phase + "-" + level.name.lower()
            and owner.source_binding_sha256 == source
            and owner.state is state
        )
    _require(
        len({(row.pid, row.process_start_identity, row.launch_nonce) for row in result})
        == 1
    )
    return result


def _process_complete(value: dict[str, Any], exitcode: int) -> bool:
    _object(
        value,
        {
            "pid",
            "created",
            "resumed",
            "tree_exited",
            "returncode",
            "stdin_bytes",
            "stdout",
            "stderr",
            "stdout_eof",
            "stderr_eof",
            "cleanup_errors",
            "remaining_handles",
            "remaining_pins",
            "pending_input",
        },
    )
    _require(type(value["pid"]) is int and value["pid"] >= 0)
    for key in (
        "created",
        "resumed",
        "tree_exited",
        "stdout_eof",
        "stderr_eof",
        "pending_input",
    ):
        _require(type(value[key]) is bool)
    for key in ("stdin_bytes", "remaining_handles", "remaining_pins"):
        _require(type(value[key]) is int and 0 <= value[key] <= 65536)
    _require(value["returncode"] is None or type(value["returncode"]) is int)
    _require(
        type(value["stdout"]) is str
        and len(value["stdout"].encode("utf-8")) <= 16 * 1024
        and type(value["stderr"]) is str
        and len(value["stderr"].encode("utf-8")) <= 2048
    )
    _require(
        type(value["cleanup_errors"]) is list
        and len(value["cleanup_errors"]) <= 128
        and all(
            type(row) is str and re.fullmatch(r"[A-Za-z0-9_:]{1,128}", row)
            for row in value["cleanup_errors"]
        )
    )
    return (
        all(
            value[key]
            for key in ("created", "resumed", "tree_exited", "stdout_eof", "stderr_eof")
        )
        and value["returncode"] == exitcode
        and not any(
            value[key]
            for key in (
                "cleanup_errors",
                "remaining_handles",
                "remaining_pins",
                "pending_input",
                "stderr",
            )
        )
    )


def _lease_checks(data: dict[str, Any]) -> list[bool]:
    checks = [False] * 5
    source = data["binding"]["source_sha256"]
    experiment = data["lease_experiment"]
    _object(experiment, {"clean", "crash", "pid_mismatch"})
    for phase in ("clean", "crash"):
        row = experiment[phase]
        if row is None:
            continue
        _object(
            row,
            {
                "request",
                "process",
                "held",
                "after_live_denial",
                "live_error",
                "after_exit",
                "reacquired",
                "after_reacquire",
                "stale_error",
                "after_stale_denial",
            },
        )
        request = _object(
            row["request"],
            {
                "schema",
                "source_sha256",
                "module_sha256s",
                "qualification",
                "phase",
                "deadline_ns",
                "directory",
            },
        )
        _require(
            request["schema"] == "rocell.ownership_child_request.v1"
            and request["source_sha256"] == source
            and request["phase"] == phase
            and request["directory"] == data["binding"]["directory"]
            and request["qualification"] == data["durability"]
            and request["module_sha256s"]
            == {
                "physical_onboarding_leases": data["runtime"]["lease_source_sha256"],
                "physical_onboarding_durability": data["runtime"][
                    "durability_source_sha256"
                ],
            }
            and type(request["deadline_ns"]) is int
            and request["deadline_ns"] > 0
        )
        complete = _process_complete(row["process"], 0 if phase == "clean" else 73)
        if complete:
            _require(
                row["process"]["stdin_bytes"]
                == len(_canonical(request))
                + 1
                + len(b"CLEAN_RELEASE\n" if phase == "clean" else b"EXIT_HELD\n")
            )
        if row["held"] is None:
            _require(
                not any(
                    row[key] is not None
                    for key in (
                        "after_live_denial",
                        "live_error",
                        "after_exit",
                        "reacquired",
                        "after_reacquire",
                        "stale_error",
                        "after_stale_denial",
                    )
                )
            )
            continue
        held = _owners(
            row["held"], source=source, phase=phase, state=LeaseOwnerState.ACTIVE
        )
        _require(all(item.previous_owner_sha256 is None for item in held))
        ready = {
            "schema": "rocell.ownership_child_ready.v1",
            "request_sha256": _sha(_canonical(request)),
            "pid": row["process"]["pid"],
            "owners": row["held"],
        }
        _require(
            held[0].pid == row["process"]["pid"]
            and row["process"]["stdout"].startswith(
                (_canonical(ready) + b"\n").decode("ascii")
            )
        )
        live = (
            row["live_error"] == "LeaseBusyError"
            and row["after_live_denial"] == row["held"]
        )
        _require(row["live_error"] in (None, "LeaseBusyError"))
        if row["after_live_denial"] is not None:
            _owners(
                row["after_live_denial"],
                source=source,
                phase=phase,
                state=LeaseOwnerState.ACTIVE,
            )
        if phase == "clean":
            checks[0] = complete and live
            checks[1] = complete and live
            if row["after_exit"] is not None:
                released = _owners(
                    row["after_exit"],
                    source=source,
                    phase=phase,
                    state=LeaseOwnerState.RELEASED,
                )
                _require(
                    all(
                        old.released(
                            released_at_ns=cast(int, new.released_at_ns)
                        ).to_dict()
                        == new.to_dict()
                        for old, new in zip(held, released)
                    )
                )
                expected = (
                    _canonical(ready)
                    + b"\n"
                    + _canonical(
                        {
                            "schema": "rocell.ownership_child_released.v1",
                            "owners": row["after_exit"],
                        }
                    )
                    + b"\n"
                )
                _require(row["process"]["stdout"].encode("ascii") == expected)
                if row["reacquired"] is not None and row["after_reacquire"] is not None:
                    reacquired = _owners(
                        row["reacquired"],
                        source=source,
                        phase=phase,
                        state=LeaseOwnerState.ACTIVE,
                    )
                    final = _owners(
                        row["after_reacquire"],
                        source=source,
                        phase=phase,
                        state=LeaseOwnerState.RELEASED,
                    )
                    _require(
                        all(
                            new.previous_owner_sha256 == old.owner_sha256
                            and new.launch_nonce != old.launch_nonce
                            and (new.pid, new.process_start_identity)
                            != (old.pid, old.process_start_identity)
                            for old, new in zip(released, reacquired)
                        )
                    )
                    _require(
                        all(
                            old.released(
                                released_at_ns=cast(int, new.released_at_ns)
                            ).to_dict()
                            == new.to_dict()
                            for old, new in zip(reacquired, final)
                        )
                    )
                    checks[2] = complete and live
            _require(row["stale_error"] is None and row["after_stale_denial"] is None)
        else:
            _require(
                row["reacquired"] is None
                and row["after_reacquire"] is None
                and row["stale_error"] in (None, "StaleLeaseOwnerError")
            )
            checks[3] = (
                complete
                and live
                and row["after_exit"] == row["held"] == row["after_stale_denial"]
                and row["stale_error"] == "StaleLeaseOwnerError"
                and row["process"]["stdout"].encode("ascii")
                == _canonical(ready) + b"\n"
            )
    row = experiment["pid_mismatch"]
    if row is not None:
        _object(
            row,
            {
                "provenance",
                "observed_pid",
                "observed_process_start",
                "injected_owner",
                "classification",
                "denial",
                "after_denial",
            },
        )
        owner = LeaseOwnerMetadata.from_dict(row["injected_owner"])
        _require(
            row["provenance"] == "CONTROLLED_FAULT_INJECTION"
            and owner.pid == row["observed_pid"]
            and type(row["observed_process_start"]) is str
            and owner.process_start_identity != row["observed_process_start"]
            and owner.resource_id == "pid-mismatch-cell"
            and owner.level is LeaseLevel.CELL
            and owner.state is LeaseOwnerState.ACTIVE
            and owner.source_binding_sha256 == source
        )
        clean = experiment["clean"]
        crash = experiment["crash"]
        _require(
            clean is not None
            and crash is not None
            and clean["reacquired"] is not None
            and crash["held"] is not None
        )
        _require(
            row["observed_pid"] == clean["reacquired"][0]["pid"]
            and row["observed_process_start"]
            == clean["reacquired"][0]["process_start_identity"]
            and owner.process_start_identity
            == crash["held"][0]["process_start_identity"]
        )
        checks[4] = (
            row["classification"] == "PID_REUSED"
            and row["denial"] == "StaleLeaseOwnerError"
            and row["after_denial"] == row["injected_owner"]
        )
    return checks


def _m1_check(data: dict[str, Any]) -> bool:
    row = data["m1_experiment"]
    if row is None:
        return False
    _object(
        row,
        {
            "directory",
            "source_binding_sha256",
            "cell_id",
            "session_id",
            "identity",
            "permit",
            "outcome",
            "evidence",
            "records",
            "verification_before",
            "verification_after",
            "same_owner_cached",
            "old_permit_denied",
            "reused_key_denied",
            "worker_calls",
        },
    )
    _require(
        row["directory"] == str(_path(data["binding"]["directory"]) / "m1")
        and row["source_binding_sha256"]
        == physical_diagnostic_source_binding(data["binding"]["source_sha256"])
    )
    expected_identity = {
        "schema": "rocell.ownership_experiment_identity.v1",
        "source_sha256": data["binding"]["source_sha256"],
        "directory_sha256": _sha(row["directory"].encode("utf-8")),
        "kind": "NO_DEVICE_IO_SOFTWARE_EXPERIMENT",
        "physical_device": False,
    }
    _require(row["identity"] == expected_identity)
    for key in ("same_owner_cached", "old_permit_denied", "reused_key_denied"):
        _require(type(row[key]) is bool)
    _require(type(row["worker_calls"]) is int and 0 <= row["worker_calls"] <= 1)
    if row["permit"] is None:
        return False
    permit = decode_physical_diagnostic_permit(row["permit"])
    _require(
        permit.request.cell_id == row["cell_id"]
        and permit.request.session_id == row["session_id"]
        and permit.request.action_id == _ACTION
        and permit.registration.effect_class is EffectClass.NO_DEVICE_IO
        and permit.registration.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES
        and permit.admission.source_binding_sha256 == row["source_binding_sha256"]
        and permit.admission.selected_identity_sha256
        == _sha(_canonical(row["identity"]))
        and permit.registration.worker_executable_sha256
        == data["runtime"]["executable_sha256"]
        and permit.registration.worker_id == "ownership-no-device-worker"
        and permit.registration.budget == CampaignBudget(10000, 4096, 0, 0, 0, 0, 0)
        and permit.registration.operation_sha256
        == _sha(
            _canonical(
                {
                    "source_sha256": data["binding"]["source_sha256"],
                    "runtime": data["runtime"],
                    "identity": row["identity"],
                }
            )
        )
        and permit.request.request_key == "original-ownership-request-once"
    )
    _require(type(row["records"]) is dict and len(row["records"]) <= 12)
    for name, record in row["records"].items():
        _require(
            type(name) is str and bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", name))
        )
        _object(
            record,
            {
                "schema",
                "kind",
                "composition",
                "physical_authority",
                "data",
                "record_sha256",
            },
        )
        _require(
            record["schema"] == "rocell.m1_physical_diagnostic_record.v1"
            and record["composition"] == PHYSICAL_DIAGNOSTIC_COMPOSITION
            and record["physical_authority"] is False
            and record["record_sha256"]
            == _sha(
                canonical_json_bytes(
                    {
                        key: value
                        for key, value in record.items()
                        if key != "record_sha256"
                    }
                )
            )
        )
    if row["outcome"] is None or row["evidence"] is None:
        return False
    evidence = row["evidence"]
    _require(
        type(evidence) is dict
        and type(evidence.get("lease_owners")) is list
        and len(evidence["lease_owners"]) == 2
    )
    leases = [LeaseOwnerMetadata.from_dict(value) for value in evidence["lease_owners"]]
    for level, resource, owner in zip(
        (LeaseLevel.CELL, LeaseLevel.SESSION),
        (row["cell_id"], row["session_id"]),
        leases,
    ):
        _require(
            owner.level is level
            and owner.resource_id == resource
            and owner.source_binding_sha256 == row["source_binding_sha256"]
            and owner.state is LeaseOwnerState.ACTIVE
        )
    _require(
        len(
            {
                (owner.pid, owner.process_start_identity, owner.launch_nonce)
                for owner in leases
            }
        )
        == 1
    )
    expected = {
        "schema": _EVIDENCE_SCHEMA,
        "source_sha256": data["binding"]["source_sha256"],
        "permit_sha256": permit.permit_sha256,
        "attempt_id": permit.attempt_id,
        "selected_identity_sha256": permit.admission.selected_identity_sha256,
        "lease_levels": ["CELL", "SESSION"],
        "lease_owners": evidence["lease_owners"],
        "device_effects": ZERO_EFFECTS,
    }
    _require(_canonical(evidence) == _canonical(expected))
    expected_receipt = WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        permit.registration.worker_executable_sha256,
        permit.admission.selected_identity_sha256,
        EffectCertainty.CONFIRMED,
        True,
        ObservedPowerState.UNKNOWN,
        0,
        0,
        0,
        0,
        0,
        len(_canonical(evidence)),
        (_sha(_canonical(evidence)),),
        PHYSICAL_DIAGNOSTIC_COMPOSITION,
    )
    expected_outcome = {
        "attempt_id": permit.attempt_id,
        "state": "SEALED_KNOWN",
        "permit_sha256": permit.permit_sha256,
        "reason_codes": [],
        "receipt": json.loads(_canonical(asdict(expected_receipt))),
        "quarantine_latched": False,
        "composition": PHYSICAL_DIAGNOSTIC_COMPOSITION,
        "physical_authority": "NONE",
    }
    if _canonical(row["outcome"]) != _canonical(expected_outcome):
        return False
    # The exact original reserved permit and final receipt must exist among the
    # audited immutable records, not merely in the outer collector's assertions.
    aid, psha = permit.attempt_id, permit.permit_sha256
    expected_records = {
        f"request-{_sha(permit.request.request_key.encode('ascii'))}.json": (
            "EXACT_REQUEST_RESERVED",
            {
                "request_key": permit.request.request_key,
                "attempt_id": aid,
                "permit_sha256": psha,
                "permit": row["permit"],
            },
        ),
        f"result-{aid}-sealed_known.json": (
            "CAMPAIGN_RESULT",
            {"attempt_id": aid, "permit_sha256": psha, "result": row["outcome"]},
        ),
        f"evidence-{aid}-retained.json": (
            "CAMPAIGN_EVIDENCE",
            {
                "attempt_id": aid,
                "permit_sha256": psha,
                "evidence": [
                    {
                        "schema": _EVIDENCE_SCHEMA,
                        "label": "ownership-no-device",
                        "payload_bytes": len(_canonical(evidence)),
                        "payload_sha256": _sha(_canonical(evidence)),
                        "payload_base64": base64.b64encode(_canonical(evidence)).decode(
                            "ascii"
                        ),
                    }
                ],
            },
        ),
        **{
            f"receipt-{aid}-{state.lower()}.json": (
                "CAMPAIGN_RECEIPT",
                {
                    "attempt_id": aid,
                    "permit_sha256": psha,
                    "state": state,
                    "receipt": expected_outcome["receipt"],
                },
            )
            for state in ("EFFECT_OBSERVED", "CLEANUP_CONFIRMED")
        },
    }
    _require(set(row["records"]) == set(expected_records))
    for filename, (kind, body) in expected_records.items():
        _require(
            row["records"][filename]["kind"] == kind
            and _canonical(row["records"][filename]["data"]) == _canonical(body)
        )
    before, after = row["verification_before"], row["verification_after"]
    if before is None or after is None:
        return False
    for observed in (before, after):
        _verification(observed, row)
    return (
        all(
            row[key]
            for key in ("same_owner_cached", "old_permit_denied", "reused_key_denied")
        )
        and row["worker_calls"] == 1
        and before["attempt_ledger"] == after["attempt_ledger"]
        and before["session"] == after["session"]
        and before["quarantine"] == after["quarantine"]
        and after["attempt_ledger"]["event_count"] == 5
        and after["leases"]["active_or_stale_owners"] == []
    )


def _verification(value: dict[str, Any], experiment: dict[str, Any]) -> None:
    """Reconstruct the actual verification projection, including all hold bits."""
    cell = M1CellDescriptor.from_dict(value["cell"])
    _require(
        cell.cell_id == experiment["cell_id"]
        and cell.source_binding_sha256 == experiment["source_binding_sha256"]
    )
    qualification, attempts, quarantine, session, leases = (
        value[key]
        for key in (
            "qualification",
            "attempt_ledger",
            "quarantine",
            "session",
            "leases",
        )
    )
    for digest in (
        qualification["anchor_sha256"],
        qualification["startup_report_sha256"],
        attempts["head_sha256"],
        quarantine["head_sha256"],
        session["header_sha256"],
        session["head_sha256"],
        session["evidence_inventory_sha256"],
        value["challenge_sha256"],
    ):
        _digest(digest)
    for key in ("event_count",):
        _require(
            type(attempts[key]) is int
            and 0 <= attempts[key] <= 5
            and type(quarantine[key]) is int
            and 0 <= quarantine[key] <= 1
        )
    _require(
        type(quarantine["latched"]) is bool
        and type(session["reconciliation_required"]) is bool
        and session["session_id"] == experiment["session_id"]
    )
    for values in (
        attempts["unresolved_attempt_ids"],
        attempts["uncertain_attempt_ids"],
        leases["active_or_stale_owners"],
    ):
        _require(
            type(values) is list
            and len(values) <= 4
            and all(type(item) is str and len(item) <= 256 for item in values)
        )
    expected = M1RuntimeVerification(
        cell,
        qualification["anchor_sha256"],
        qualification["startup_report_sha256"],
        attempts["head_sha256"],
        attempts["event_count"],
        tuple(attempts["unresolved_attempt_ids"]),
        tuple(attempts["uncertain_attempt_ids"]),
        quarantine["head_sha256"],
        quarantine["event_count"],
        quarantine["latched"],
        session["session_id"],
        session["header_sha256"],
        session["head_sha256"],
        session["reconciliation_required"],
        tuple(leases["active_or_stale_owners"]),
        session["evidence_inventory_sha256"],
        value["challenge_sha256"],
    ).to_dict()
    _require(_canonical(value) == _canonical(expected))


def _derived_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    durability = False
    if data["durability"] is not None:
        report = DurabilityQualificationReport.from_dict(data["durability"])
        _require(
            report.source_binding_sha256 == data["binding"]["source_sha256"]
            and report.root_sha256 == _sha(data["binding"]["directory"].encode("utf-8"))
        )
        durability = report.qualified_for_effects
    values = [durability, *_lease_checks(data), _m1_check(data)]
    return [
        {
            "id": name,
            "passed": value,
            "provenance": (
                "CONTROLLED_FAULT_INJECTION" if index == 5 else "ACTUAL_HOST_MECHANISM"
            ),
        }
        for index, (name, value) in enumerate(zip(CHECK_IDS, values))
    ]


def _validate(payload: bytes) -> dict[str, Any]:
    _require(type(payload) is bytes and 0 < len(payload) <= MAX_REPORT_BYTES)
    data = decode_owned_json(payload, maximum=MAX_REPORT_BYTES)
    _require(_canonical(data) == payload)
    _object(
        data,
        {
            "schema",
            "binding",
            "runtime",
            "started_at_ns",
            "elapsed_ns",
            "durability",
            "lease_experiment",
            "m1_experiment",
            "checks",
            "terminal_error",
            "residuals",
            "device_effects",
            "physical_authority",
            "hardware_qualified",
        },
    )
    _require(
        data["schema"] == SCHEMA
        and data["physical_authority"] is False
        and data["hardware_qualified"] is False
        and data["device_effects"] == ZERO_EFFECTS
        and all(type(value) is int for value in data["device_effects"].values())
        and data["residuals"] == list(RESIDUALS)
    )
    binding = _object(data["binding"], {"workspace", "directory", "source_sha256"})
    _digest(binding["source_sha256"])
    workspace, directory = _path(binding["workspace"]), _path(binding["directory"])
    _require(
        workspace.drive.lower() == directory.drive.lower() and workspace != directory
    )
    runtime = _object(
        data["runtime"],
        {
            "executable",
            "executable_sha256",
            "child",
            "child_sha256",
            "lease_source_sha256",
            "durability_source_sha256",
        },
    )
    _path(runtime["executable"])
    _require(runtime["child"] == str(workspace / PureWindowsPath(CHILD_PATH)))
    for name in (
        "executable_sha256",
        "child_sha256",
        "lease_source_sha256",
        "durability_source_sha256",
    ):
        _digest(runtime[name])
    _require(
        type(data["started_at_ns"]) is int
        and 0 < data["started_at_ns"] < 2**63
        and type(data["elapsed_ns"]) is int
        and 0 <= data["elapsed_ns"] < 2**63
    )
    error = data["terminal_error"]
    if error is not None:
        _object(error, {"code", "type"})
        _require(
            all(
                type(value) is str and bool(re.fullmatch(r"[A-Za-z0-9_]{1,96}", value))
                for value in error.values()
            )
        )
    else:
        _require(data["elapsed_ns"] < MAX_DURATION_NS)
    _require(_canonical(data["checks"]) == _canonical(_derived_checks(data)))
    return data


@dataclass(frozen=True, slots=True)
class PhysicalOwnershipQualification:
    payload: bytes

    def __post_init__(self) -> None:
        _validate(self.payload)

    @property
    def sha256(self) -> str:
        return _sha(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return {
            "schema": SUMMARY_SCHEMA,
            "report_sha256": self.sha256,
            "source_sha256": data["binding"]["source_sha256"],
            "status": (
                "SOFTWARE_OWNERSHIP_COVERED"
                if data["terminal_error"] is None
                and all(row["passed"] for row in data["checks"])
                else "HELD"
            ),
            "checks": data["checks"],
            "residuals": list(RESIDUALS),
            "device_effects": dict(ZERO_EFFECTS),
            "physical_authority": False,
            "hardware_qualified": False,
        }


def verify_physical_ownership_qualification(
    value: bytes | PhysicalOwnershipQualification,
    *,
    expected_source_sha256: str,
    expected_directory: Path | str,
    expected_report_sha256: str,
) -> PhysicalOwnershipQualification:
    report = PhysicalOwnershipQualification(
        value.payload
        if type(value) is PhysicalOwnershipQualification
        else cast(bytes, value)
    )
    _digest(expected_source_sha256)
    _digest(expected_report_sha256)
    _require(
        report.sha256 == expected_report_sha256
        and report.to_dict()["binding"]["source_sha256"] == expected_source_sha256
        and report.to_dict()["binding"]["directory"] == str(expected_directory),
        "OWNERSHIP_REPORT_BINDING",
    )
    return report


def _read_pin(path: Path, maximum: int, check: Callable[[], None]) -> PinnedWorkerFile:
    check()
    require_regular_path(path, directory=False)
    before = path.stat()
    _require(0 < before.st_size <= maximum, "OWNERSHIP_PIN_BOUND")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for _ in range((before.st_size + 65535) // 65536):
            check()
            block = stream.read(65536)
            _require(bool(block), "OWNERSHIP_PIN_CHANGED")
            digest.update(block)
        _require(not stream.read(1), "OWNERSHIP_PIN_CHANGED")
    after = path.stat()
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "OWNERSHIP_PIN_CHANGED",
    )
    check()
    return PinnedWorkerFile(path, digest.hexdigest(), maximum)


def _specs(phase: str) -> tuple[LeaseSpec, ...]:
    return tuple(
        LeaseSpec(level, phase + "-" + level.name.lower()) for level in LeaseLevel
    )


def _owner_rows(
    manager: OnboardingLeaseManager, specs: tuple[LeaseSpec, ...]
) -> list[dict[str, Any]]:
    result = [manager.prior_owner(spec) for spec in specs]
    _require(all(row is not None for row in result), "OWNER_READBACK_MISSING")
    return [cast(LeaseOwnerMetadata, row).to_dict() for row in result]


def _child_phase(
    data: dict[str, Any],
    phase: str,
    pins: tuple[PinnedWorkerFile, ...],
    check: Callable[[], None],
    deadline_ns: int,
) -> None:
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    directory = Path(data["binding"]["directory"])
    source = data["binding"]["source_sha256"]
    report = DurabilityQualificationReport.from_dict(data["durability"])
    manager = OnboardingLeaseManager(
        directory, source, OnboardingLeaseManager.new_launch_nonce(), report
    )
    budget = WorkerProcessBudget(
        run_timeout_ms=15000,
        cleanup_timeout_ms=2000,
        stdin_bytes=16 * 1024,
        stdout_bytes=16 * 1024,
        stderr_bytes=2048,
        process_count=1,
    )
    registration = WorkerProcessRegistration(
        "physical-ownership-fixed-child",
        pins[0],
        ("-I", "-S", "-B", str(pins[1].path)),
        pins[1:],
        pins[1].path.parent,
        budget,
        "INCAPABLE_PROCESS_FIXTURE",
    )
    end = min(deadline_ns - 2_000_000_000, time.monotonic_ns() + 15_000_000_000)
    request = {
        "schema": "rocell.ownership_child_request.v1",
        "source_sha256": source,
        "module_sha256s": {name: pin.sha256 for name, pin in zip(_MODULES, pins[2:])},
        "qualification": data["durability"],
        "phase": phase,
        "deadline_ns": end,
        "directory": str(directory),
    }
    row: dict[str, Any] = {
        "request": request,
        "process": {},
        **{
            key: None
            for key in (
                "held",
                "after_live_denial",
                "live_error",
                "after_exit",
                "reacquired",
                "after_reacquire",
                "stale_error",
                "after_stale_denial",
            )
        },
    }
    data["lease_experiment"][phase] = row
    owns_lock = shared_process._DISPATCH_LOCK.acquire(blocking=False)
    if not owns_lock:
        data["lease_experiment"][phase] = None
        raise PhysicalOwnershipQualificationError("OWNED_PROCESS_ALREADY_RUNNING")
    native = None
    try:
        _require(shared_process._UNRESOLVED_BACKEND is None, "PROCESS_CLEANUP_HOLD")
        native = WindowsOwnedProcess()

        def live() -> None:
            check()
            _require(time.monotonic_ns() < end, "OWNERSHIP_CHILD_TIMED_OUT")

        native.pin(registration)
        live()
        native.start(
            registration, _canonical(request) + b"\n", check=live, keep_stdin_open=True
        )
        while b"\n" not in native.stdout or native.pending:
            live()
            _require(not native.poll(budget), "OWNERSHIP_CHILD_EARLY_EXIT")
            time.sleep(0.005)
        ready = decode_owned_json(native.stdout.split(b"\n", 1)[0], maximum=16384)
        _require(
            set(ready) == {"schema", "request_sha256", "pid", "owners"}
            and ready["schema"] == "rocell.ownership_child_ready.v1"
            and ready["request_sha256"] == _sha(_canonical(request))
            and ready["pid"] == native.pid,
            "OWNERSHIP_CHILD_READY",
        )
        row["held"] = _owner_rows(manager, _specs(phase))
        _require(ready["owners"] == row["held"], "OWNERSHIP_CHILD_OWNER_BINDING")
        live()
        try:
            with manager.acquire(
                _specs(phase),
                operation="OWNERSHIP_LIVE_CONTENDER",
                expected_challenge_sha256=source,
                challenge_callback=lambda: source,
                effectful=True,
            ):
                raise PhysicalOwnershipQualificationError("LIVE_CONTENDER_ACQUIRED")
        except LeaseBusyError:
            row["live_error"] = "LeaseBusyError"
        row["after_live_denial"] = _owner_rows(manager, _specs(phase))
        live()
        native.send_final_input(
            b"CLEAN_RELEASE\n" if phase == "clean" else b"EXIT_HELD\n", check=live
        )
        while not native.poll(budget):
            live()
            time.sleep(0.005)
        live()
        row["after_exit"] = _owner_rows(manager, _specs(phase))
        if phase == "clean":
            with manager.acquire(
                _specs(phase),
                operation="OWNERSHIP_CLEAN_REACQUIRE",
                expected_challenge_sha256=source,
                challenge_callback=lambda: source,
                effectful=True,
            ) as held:
                row["reacquired"] = [owner.to_dict() for owner in held.owners]
            row["after_reacquire"] = _owner_rows(manager, _specs(phase))
        else:
            try:
                with manager.acquire(
                    _specs(phase),
                    operation="OWNERSHIP_STALE_CONTENDER",
                    expected_challenge_sha256=source,
                    challenge_callback=lambda: source,
                    effectful=True,
                ):
                    raise PhysicalOwnershipQualificationError(
                        "STALE_CONTENDER_ACQUIRED"
                    )
            except StaleLeaseOwnerError:
                row["stale_error"] = "StaleLeaseOwnerError"
            row["after_stale_denial"] = _owner_rows(manager, _specs(phase))
    finally:
        try:
            if native is not None:
                cleanup_end = min(deadline_ns, time.monotonic_ns() + 2_000_000_000)
                try:
                    cleanup = native.cleanup(cleanup_end)
                except BaseException as error:
                    cleanup = ("CLEANUP_EXCEPTION_" + type(error).__name__,)
                if time.monotonic_ns() >= cleanup_end:
                    cleanup = (*cleanup, "CLEANUP_DEADLINE_EXCEEDED")
                if (
                    cleanup
                    or native.pending
                    or native.handles
                    or native.pins
                    or native.unclosed_handles
                    or (native.created and not native.tree_exited)
                ):
                    shared_process._UNRESOLVED_BACKEND = native
                row["process"] = {
                    "pid": native.pid,
                    "created": native.created,
                    "resumed": native.resumed,
                    "tree_exited": native.tree_exited,
                    "returncode": native.returncode,
                    "stdin_bytes": native.written,
                    "stdout": native.stdout.decode("ascii"),
                    "stderr": native.stderr.decode("ascii"),
                    "stdout_eof": native.stdout_eof,
                    "stderr_eof": native.stderr_eof,
                    "cleanup_errors": list(cleanup),
                    "remaining_handles": len(native.handles)
                    + len(native.unclosed_handles),
                    "remaining_pins": len(native.pins),
                    "pending_input": native.pending,
                }
            else:
                data["lease_experiment"][phase] = None
        finally:
            shared_process._DISPATCH_LOCK.release()


def _pid_case(data: dict[str, Any], check: Callable[[], None]) -> None:
    source = data["binding"]["source_sha256"]
    manager = OnboardingLeaseManager(
        Path(data["binding"]["directory"]),
        source,
        OnboardingLeaseManager.new_launch_nonce(),
        DurabilityQualificationReport.from_dict(data["durability"]),
    )
    spec = LeaseSpec(LeaseLevel.CELL, "pid-mismatch-cell")
    check()
    actual = process_start_identity()
    _require(actual is not None, "PROCESS_START_UNAVAILABLE")
    owner = LeaseOwnerMetadata.build_active(
        spec,
        source_binding_sha256=source,
        launch_nonce=manager.launch_nonce,
        operation="OWNERSHIP_CONTROLLED_PID_FAULT",
        acquired_at_ns=time.time_ns(),
        previous_owner_sha256=None,
    )
    body = owner.core_dict()
    # An observed creation identity from the now-dead child differs from this
    # live parent. This is controlled metadata injection, not real OS PID reuse.
    body["process_start_identity"] = data["lease_experiment"]["crash"]["held"][0][
        "process_start_identity"
    ]
    owner = LeaseOwnerMetadata.from_dict(
        {**body, "owner_sha256": canonical_sha256(body)}
    )
    _require(owner.process_start_identity != actual, "PID_FAULT_NOT_DISTINCT")
    filename = f"lease-00-{spec.resource_sha256}.owner.json"
    publish_canonical_json(
        manager.coordination_root,
        filename,
        owner.to_dict(),
        mode=PublicationMode.IMMUTABLE,
    )
    row = {
        "provenance": "CONTROLLED_FAULT_INJECTION",
        "observed_pid": os.getpid(),
        "observed_process_start": actual,
        "injected_owner": owner.to_dict(),
        "classification": classify_prior_owner_process(owner).value,
        "denial": None,
        "after_denial": None,
    }
    data["lease_experiment"]["pid_mismatch"] = row
    check()
    try:
        with manager.acquire(
            (spec, LeaseSpec(LeaseLevel.SESSION, "pid-mismatch-session")),
            operation="OWNERSHIP_PID_CONTENDER",
            expected_challenge_sha256=source,
            challenge_callback=lambda: source,
            effectful=True,
        ):
            raise PhysicalOwnershipQualificationError("PID_FAULT_CONTENDER_ACQUIRED")
    except StaleLeaseOwnerError:
        row["denial"] = "StaleLeaseOwnerError"
    row["after_denial"] = cast(LeaseOwnerMetadata, manager.prior_owner(spec)).to_dict()
    check()


class _NoDeviceWorker:
    composition = PHYSICAL_DIAGNOSTIC_COMPOSITION

    def __init__(
        self,
        executable_sha256: str,
        source: str,
        check: Callable[[], None],
        manager: OnboardingLeaseManager,
    ):
        self.worker_executable_sha256, self.source, self.check = (
            executable_sha256,
            source,
            check,
        )
        self.calls = 0
        self.manager = manager

    def run_campaign(self, *args: Any, **kwargs: Any) -> WorkerReceipt:
        raise PhysicalOwnershipQualificationError("RETAINED_NO_DEVICE_ONLY")

    def run_retained_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorize_consumed_permit: Callable[[ExactOperationPermit], None],
    ) -> RetainedCampaignExecution:
        self.check()
        _require(
            self.calls == 0
            and time.monotonic_ns() < deadline_ns
            and not cancellation.is_set(),
            "NO_DEVICE_WORKER_ONE_USE",
        )
        authorize_consumed_permit(permit)
        self.calls += 1
        payload = _canonical(
            {
                "schema": _EVIDENCE_SCHEMA,
                "source_sha256": self.source,
                "permit_sha256": permit.permit_sha256,
                "attempt_id": permit.attempt_id,
                "selected_identity_sha256": permit.admission.selected_identity_sha256,
                "lease_levels": ["CELL", "SESSION"],
                "lease_owners": _owner_rows(
                    self.manager,
                    (
                        LeaseSpec(LeaseLevel.CELL, permit.request.cell_id),
                        LeaseSpec(LeaseLevel.SESSION, permit.request.session_id),
                    ),
                ),
                "device_effects": ZERO_EFFECTS,
            }
        )
        artifact = CampaignEvidence(_EVIDENCE_SCHEMA, "ownership-no-device", payload)
        return RetainedCampaignExecution(
            WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                self.worker_executable_sha256,
                permit.admission.selected_identity_sha256,
                EffectCertainty.CONFIRMED,
                True,
                ObservedPowerState.UNKNOWN,
                0,
                0,
                0,
                0,
                0,
                len(payload),
                (artifact.payload_sha256,),
                self.composition,
            ),
            (artifact,),
        )


def _m1_case(
    data: dict[str, Any], check: Callable[[], None], cancellation: Event
) -> None:
    source = data["binding"]["source_sha256"]
    directory = Path(data["binding"]["directory"]) / "m1"
    suffix = _sha(str(directory).encode("utf-8"))[:32]
    cell, session = (
        "wizard-physical-diagnostic-" + suffix[:16],
        "physical-diagnostic-" + suffix,
    )
    identity = {
        "schema": "rocell.ownership_experiment_identity.v1",
        "source_sha256": source,
        "directory_sha256": _sha(str(directory).encode("utf-8")),
        "kind": "NO_DEVICE_IO_SOFTWARE_EXPERIMENT",
        "physical_device": False,
    }
    row: dict[str, Any] = {
        "directory": str(directory),
        "source_binding_sha256": physical_diagnostic_source_binding(source),
        "cell_id": cell,
        "session_id": session,
        "identity": identity,
        "permit": None,
        "outcome": None,
        "evidence": None,
        "records": {},
        "verification_before": None,
        "verification_after": None,
        "same_owner_cached": False,
        "old_permit_denied": False,
        "reused_key_denied": False,
        "worker_calls": 0,
    }
    data["m1_experiment"] = row

    def facts(
        request: RegisteredActionRequest, snapshot: Any
    ) -> PhysicalDiagnosticAdmissionFacts:
        check()
        _require(
            request.cell_id == cell
            and request.session_id == session
            and request.action_id == _ACTION
            and snapshot.next_action.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES,
            "OWNERSHIP_M1_SCOPE",
        )
        return PhysicalDiagnosticAdmissionFacts(
            {
                "source_sha256": source,
                "kind": "NO_DEVICE_IO_OWNERSHIP_EXPERIMENT",
                "physical_hazards_closed": False,
            },
            tuple(
                {
                    "source_sha256": source,
                    "index": index,
                    "physical_epoch": "UNMEASURED",
                }
                for index in range(8)
            ),
            identity,
        )

    check()
    directory.mkdir(exist_ok=False)
    runtime = PhysicalOnboardingM1Runtime.initialize(
        directory, source_binding_sha256=row["source_binding_sha256"], cell_id=cell
    )
    runtime.create_session(
        session, mode="PHYSICAL_DIAGNOSTIC", workspace_source_sha256=source
    )
    store = M1PhysicalDiagnosticPersistence(
        runtime, workspace_source_sha256=source, admission_facts=facts
    )
    with store.stage_transaction(
        session, expected_challenge_sha256=store.verification(session).challenge_sha256
    ) as tx:
        snapshot = tx.snapshot()
        tx.commit_stage_state(
            PhysicalOnboardingStage.WORKSPACE_SOURCES,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=max(time.time_ns(), snapshot.header.created_at_ns + 1),
            detail_code="OWNERSHIP_NO_DEVICE_EXPERIMENT",
            expected_head_sha256=snapshot.head.head_sha256,
        )
    # Private runtime manager is read only here, while the core owns the exact
    # acknowledged transaction. Retain its original ACTIVE owner identities.
    worker = _NoDeviceWorker(
        data["runtime"]["executable_sha256"], source, check, runtime._leases
    )
    registration = CampaignRegistration(
        _ACTION,
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        EffectClass.NO_DEVICE_IO,
        "ownership-no-device-worker",
        worker.worker_executable_sha256,
        _sha(
            _canonical(
                {
                    "source_sha256": source,
                    "runtime": data["runtime"],
                    "identity": identity,
                }
            )
        ),
        (),
        CampaignBudget(10000, 4096, 0, 0, 0, 0, 0),
    )
    leases = (LeaseSpec(LeaseLevel.CELL, cell), LeaseSpec(LeaseLevel.SESSION, session))
    request = RegisteredActionRequest(
        cell, session, _ACTION, "original-ownership-request-once", source
    )
    with store.transaction(leases) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )

    def coordinator(
        selected: M1PhysicalDiagnosticPersistence,
    ) -> PhysicalDiagnosticPreflightCoordinator:
        return PhysicalDiagnosticPreflightCoordinator(
            persistence=cast(CommissioningPersistence, selected),
            registrations=(registration,),
            workers={registration.worker_id: worker},
            retained_campaign_actions=(_ACTION,),
        )

    core = coordinator(store)
    check()
    permit = core.prepare(request)
    row["permit"] = json.loads(_canonical(asdict(permit)))
    outcome = core.execute(permit, cancellation=cancellation)
    row["outcome"] = json.loads(_canonical(asdict(outcome)))
    row["worker_calls"] = worker.calls
    row["same_owner_cached"] = core.execute(permit) == outcome
    with store.transaction(leases) as tx:
        artifacts = tx.read_campaign_evidence(permit.attempt_id)
        row["records"] = tx._audit_records()
        _require(
            tx.read_campaign_permit(permit.attempt_id) == permit
            and len(artifacts) == 1
            and artifacts[0].schema == _EVIDENCE_SCHEMA,
            "OWNERSHIP_M1_ORIGINAL_READBACK",
        )
        row["evidence"] = decode_owned_json(artifacts[0].payload, maximum=4096)
    row["verification_before"] = store.verification(session).to_dict()
    check()
    reopened = PhysicalOnboardingM1Runtime.open(
        directory, source_binding_sha256=row["source_binding_sha256"], cell_id=cell
    )
    restored = M1PhysicalDiagnosticPersistence(
        reopened, workspace_source_sha256=source, admission_facts=facts
    )
    new_core = coordinator(restored)
    try:
        new_core.execute(permit)
    except CommissioningCoordinatorError:
        row["old_permit_denied"] = True
    with restored.transaction(leases) as tx:
        duplicate = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    fresh = new_core.prepare(duplicate)
    try:
        new_core.execute(fresh, cancellation=cancellation)
    except M1CommissioningPersistenceError as error:
        _require(
            str(error)
            == "request key is durably consumed; restart/session changes cannot replay it",
            "UNEXPECTED_REPLAY_REFUSAL",
        )
        row["reused_key_denied"] = True
    row["worker_calls"] = worker.calls
    row["verification_after"] = restored.verification(session).to_dict()
    check()


def collect_physical_ownership_qualification(
    workspace: Path,
    *,
    assigned_directory: Path,
    source_sha256: str,
    cancellation: Event,
    progress: Callable[[str], None],
    deadline_ns: int | None = None,
) -> PhysicalOwnershipQualification:
    """One explicit fixed experiment; errors carry .report; paths are preserved.

    The synchronous existing NTFS operations have checks before and after each
    bounded operation. The child has separate owned-job timeout/cleanup bounds.
    No collector or historical verifier changes a physical authority flag.
    """
    _require(
        isinstance(workspace, Path)
        and isinstance(assigned_directory, Path)
        and isinstance(cancellation, Event)
        and callable(progress),
        "OWNERSHIP_ARGUMENTS",
    )
    _digest(source_sha256)
    _path(str(workspace))
    _path(str(assigned_directory))
    started = time.monotonic_ns()
    end = started + MAX_DURATION_NS
    if deadline_ns is not None:
        _require(
            type(deadline_ns) is int and started < deadline_ns <= end,
            "OWNERSHIP_DEADLINE",
        )
        end = deadline_ns

    def check() -> None:
        _require(not cancellation.is_set(), "OWNERSHIP_CANCELLED")
        _require(time.monotonic_ns() < end, "OWNERSHIP_TIMED_OUT")

    check()
    _require(os.name == "nt", "OWNERSHIP_WINDOWS_REQUIRED")
    safe_root(workspace)
    safe_root(assigned_directory.parent)
    _require(
        workspace.stat().st_dev == assigned_directory.parent.stat().st_dev
        and workspace != assigned_directory,
        "OWNERSHIP_SAME_VOLUME_REQUIRED",
    )
    _require(source_fingerprint(workspace) == source_sha256, "OWNERSHIP_SOURCE_CHANGED")
    check()
    executable = Path(getattr(sys, "_base_executable", sys.executable))
    child = workspace / CHILD_PATH
    pins = (
        _read_pin(executable, 32 * 1024 * 1024, check),
        _read_pin(child, 64 * 1024, check),
        *(
            _read_pin(child.parent / (name + ".py"), 512 * 1024, check)
            for name in _MODULES
        ),
    )
    data: dict[str, Any] = {
        "schema": SCHEMA,
        "binding": {
            "workspace": str(workspace),
            "directory": str(assigned_directory),
            "source_sha256": source_sha256,
        },
        "runtime": {
            "executable": str(executable),
            "executable_sha256": pins[0].sha256,
            "child": str(child),
            "child_sha256": pins[1].sha256,
            "durability_source_sha256": pins[2].sha256,
            "lease_source_sha256": pins[3].sha256,
        },
        "started_at_ns": time.time_ns(),
        "elapsed_ns": 0,
        "durability": None,
        "lease_experiment": {"clean": None, "crash": None, "pid_mismatch": None},
        "m1_experiment": None,
        "checks": [],
        "terminal_error": None,
        "residuals": list(RESIDUALS),
        "device_effects": dict(ZERO_EFFECTS),
        "physical_authority": False,
        "hardware_qualified": False,
    }
    failure = None
    try:
        with ExitStack() as guards:
            # Preserve assigned ancestry, allowing only the directory write
            # sharing required by existing M1 pointer replacement primitives.
            guards.enter_context(
                _directory_guard(
                    assigned_directory.parent, allow_directory_write_sharing=True
                )
            )
            check()
            assigned_directory.mkdir(exist_ok=False)
            guards.enter_context(
                _directory_guard(assigned_directory, allow_directory_write_sharing=True)
            )
            safe_root(assigned_directory)
            progress(
                "Qualifying the original experiment volume and real Windows locks; no devices."
            )
            check()
            durability = run_on_volume_startup_self_test(
                assigned_directory, source_binding_sha256=source_sha256
            )
            data["durability"] = durability.to_dict()
            _require(durability.qualified_for_effects, "OWNERSHIP_DURABILITY_HELD")
            for phase in ("clean", "crash"):
                check()
                progress(
                    "Running the fixed "
                    + phase
                    + " ownership child; original records are preserved."
                )
                _child_phase(data, phase, pins, check, end)
            _pid_case(data, check)
            progress(
                "Retaining one original NO_DEVICE_IO M1 attempt and checking restart/no replay."
            )
            _m1_case(data, check, cancellation)
            check()
        _require(
            source_fingerprint(workspace) == source_sha256, "OWNERSHIP_SOURCE_CHANGED"
        )
        check()
    except BaseException as error:
        failure = error
        data["terminal_error"] = {
            "code": (
                error.code
                if isinstance(error, PhysicalOwnershipQualificationError)
                else "OWNERSHIP_EXPERIMENT_FAILED"
            ),
            "type": type(error).__name__,
        }
    data["elapsed_ns"] = time.monotonic_ns() - started
    if data["terminal_error"] is None and (
        cancellation.is_set() or time.monotonic_ns() >= end
    ):
        failure = PhysicalOwnershipQualificationError(
            "OWNERSHIP_CANCELLED" if cancellation.is_set() else "OWNERSHIP_TIMED_OUT"
        )
        data["terminal_error"] = {"code": failure.code, "type": type(failure).__name__}
    data["checks"] = _derived_checks(data)
    report = PhysicalOwnershipQualification(_canonical(data))
    if failure is not None:
        raise PhysicalOwnershipQualificationError(
            data["terminal_error"]["code"], report
        ) from failure
    if report.safe_summary()["status"] != "SOFTWARE_OWNERSHIP_COVERED":
        raise PhysicalOwnershipQualificationError("OWNERSHIP_CASES_INCOMPLETE", report)
    return report
