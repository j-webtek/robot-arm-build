"""Fixed software-only qualification; no native helper or device inventory."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_ownership_qualification as module


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64


def modeled_report(
    *,
    source_sha256=SOURCE,
    directory=Path(r"C:\modeled\ownership"),
    workspace=WORKSPACE,
    covered=True,
):
    """Pure, explicitly modeled wire records; never a host experiment receipt.

    The production verifier is unchanged. This fixture constructs typed hashes
    and complete lease/permit subjects, not a monkeypatched success predicate.
    """
    from rocell.application.cell_commissioning_coordinator import (
        AdmissionSnapshot,
        CommissioningMode,
        ExactOperationPermit,
        RegisteredActionRequest,
    )
    from rocell.application.physical_onboarding_leases import LEASE_OWNER_SCHEMA
    from rocell.application.physical_onboarding_durability import (
        DURABILITY_REPORT_SCHEMA,
        DURABILITY_ADAPTER_ID,
    )
    from rocell.application.physical_onboarding_m1 import (
        M1CellDescriptor,
        M1RuntimeVerification,
    )

    source = source_sha256
    directory = Path(directory)

    def sha(value):
        return module._sha(module._canonical(value))

    def document(value):
        return json.loads(module._canonical(value))

    def owner(phase, level, pid, nonce, previous=None, at=1000):
        spec = module.LeaseSpec(level, phase + "-" + level.name.lower())
        body = {
            "schema": LEASE_OWNER_SCHEMA,
            "lease_level": level.name,
            "resource_id": spec.resource_id,
            "resource_sha256": spec.resource_sha256,
            "source_binding_sha256": source,
            "pid": pid,
            "process_start_identity": "windows-filetime-" + str(pid),
            "launch_nonce": nonce * 64,
            "operation": "MODELED_OWNERSHIP",
            "acquired_at_ns": at,
            "state": "ACTIVE",
            "released_at_ns": None,
            "previous_owner_sha256": previous,
        }
        return module.LeaseOwnerMetadata.from_dict(
            {**body, "owner_sha256": module.canonical_sha256(body)}
        )

    runtime = {
        "executable": r"C:\modeled\python.exe",
        "executable_sha256": "b" * 64,
        "child": str(workspace / module.CHILD_PATH),
        "child_sha256": "c" * 64,
        "lease_source_sha256": "d" * 64,
        "durability_source_sha256": "e" * 64,
    }
    qualification = {
        "schema": DURABILITY_REPORT_SCHEMA,
        "source_binding_sha256": source,
        "root_sha256": module._sha(str(directory).encode("utf-8")),
        "platform": "Windows",
        "filesystem": "NTFS",
        "volume_identity": "MODELED_ONLY_NOT_OBSERVED",
        "adapter_id": DURABILITY_ADAPTER_ID,
        "checked_at_ns": 1000,
        "checks": [
            {
                "check_id": key,
                "passed": True,
                "detail": "EXPLICITLY MODELED SOFTWARE MECHANISM",
            }
            for key in (
                "LOCKFILEEX_EXCLUSIVE_LEASE",
                "WRITE_THROUGH_FILE_OPEN",
                "FLUSH_FILE_BUFFERS",
                "ATOMIC_REPLACE",
                "DIRECTORY_ENTRY_DURABILITY_TEST",
            )
        ],
        "qualified_for_effects": True,
    }
    qualification["report_sha256"] = module.canonical_sha256(qualification)
    data = {
        "schema": module.SCHEMA,
        "binding": {
            "workspace": str(workspace),
            "directory": str(directory),
            "source_sha256": source,
        },
        "runtime": runtime,
        "started_at_ns": 1000,
        "elapsed_ns": 20_000_000_000,
        "durability": qualification,
        "lease_experiment": {"clean": None, "crash": None, "pid_mismatch": None},
        "m1_experiment": None,
        "checks": [],
        "terminal_error": None,
        "residuals": list(module.RESIDUALS),
        "device_effects": dict(module.ZERO_EFFECTS),
        "physical_authority": False,
        "hardware_qualified": False,
    }
    if not covered:
        data["terminal_error"] = {
            "code": "OWNERSHIP_CANCELLED",
            "type": "PhysicalOwnershipQualificationError",
        }
        data["checks"] = module._derived_checks(data)
        return module.PhysicalOwnershipQualification(module._canonical(data))
    for phase, pid in (("clean", 101), ("crash", 102)):
        request = {
            "schema": "rocell.ownership_child_request.v1",
            "source_sha256": source,
            "module_sha256s": {
                "physical_onboarding_leases": runtime["lease_source_sha256"],
                "physical_onboarding_durability": runtime["durability_source_sha256"],
            },
            "qualification": qualification,
            "phase": phase,
            "deadline_ns": 20_000_000_000,
            "directory": str(directory),
        }
        held = [owner(phase, level, pid, "a") for level in module.LeaseLevel]
        rows = [item.to_dict() for item in held]
        ready = {
            "schema": "rocell.ownership_child_ready.v1",
            "request_sha256": sha(request),
            "pid": pid,
            "owners": rows,
        }
        stdout = module._canonical(ready) + b"\n"
        released = [item.released(released_at_ns=2000) for item in held]
        after = [item.to_dict() for item in released] if phase == "clean" else rows
        if phase == "clean":
            stdout += (
                module._canonical(
                    {"schema": "rocell.ownership_child_released.v1", "owners": after}
                )
                + b"\n"
            )
        acquired = [
            owner(phase, level, 201, "b", previous=prior.owner_sha256, at=3000)
            for level, prior in zip(module.LeaseLevel, released)
        ]
        process = {
            "pid": pid,
            "created": True,
            "resumed": True,
            "tree_exited": True,
            "returncode": 0 if phase == "clean" else 73,
            "stdin_bytes": len(module._canonical(request))
            + 1
            + len(b"CLEAN_RELEASE\n" if phase == "clean" else b"EXIT_HELD\n"),
            "stdout": stdout.decode("ascii"),
            "stderr": "",
            "stdout_eof": True,
            "stderr_eof": True,
            "cleanup_errors": [],
            "remaining_handles": 0,
            "remaining_pins": 0,
            "pending_input": False,
        }
        data["lease_experiment"][phase] = {
            "request": request,
            "process": process,
            "held": rows,
            "after_live_denial": rows,
            "live_error": "LeaseBusyError",
            "after_exit": after,
            "reacquired": (
                [item.to_dict() for item in acquired] if phase == "clean" else None
            ),
            "after_reacquire": (
                [item.released(released_at_ns=4000).to_dict() for item in acquired]
                if phase == "clean"
                else None
            ),
            "stale_error": None if phase == "clean" else "StaleLeaseOwnerError",
            "after_stale_denial": rows if phase == "crash" else None,
        }
    injected = owner("pid-mismatch", module.LeaseLevel.CELL, 201, "c").core_dict()
    injected["process_start_identity"] = "windows-filetime-102"
    injected["owner_sha256"] = module.canonical_sha256(injected)
    data["lease_experiment"]["pid_mismatch"] = {
        "provenance": "CONTROLLED_FAULT_INJECTION",
        "observed_pid": 201,
        "observed_process_start": "windows-filetime-201",
        "injected_owner": injected,
        "classification": "PID_REUSED",
        "denial": "StaleLeaseOwnerError",
        "after_denial": injected,
    }
    root = directory / "m1"
    suffix = module._sha(str(root).encode("utf-8"))[:32]
    cell, session = (
        "wizard-physical-diagnostic-" + suffix[:16],
        "physical-diagnostic-" + suffix,
    )
    identity = {
        "schema": "rocell.ownership_experiment_identity.v1",
        "source_sha256": source,
        "directory_sha256": module._sha(str(root).encode("utf-8")),
        "kind": "NO_DEVICE_IO_SOFTWARE_EXPERIMENT",
        "physical_device": False,
    }
    binding = module.physical_diagnostic_source_binding(source)
    admission = AdmissionSnapshot(
        cell,
        session,
        CommissioningMode.PHYSICAL_DIAGNOSTIC,
        module.PhysicalOnboardingStage.WORKSPACE_SOURCES,
        module.V2StageState.WAITING_OPERATOR,
        1,
        binding,
        *(["f" * 64] * 7),
        tuple(["f" * 64] * 8),
        sha(identity),
        False,
        0,
    )
    registration = module.CampaignRegistration(
        module._ACTION,
        module.PhysicalOnboardingStage.WORKSPACE_SOURCES,
        module.EffectClass.NO_DEVICE_IO,
        "ownership-no-device-worker",
        runtime["executable_sha256"],
        sha({"source_sha256": source, "runtime": runtime, "identity": identity}),
        (),
        module.CampaignBudget(10000, 4096, 0, 0, 0, 0, 0),
    )
    request = RegisteredActionRequest(
        cell,
        session,
        module._ACTION,
        "original-ownership-request-once",
        admission.challenge_sha256,
    )
    permit = ExactOperationPermit(
        "attempt-" + "1" * 32,
        request,
        admission,
        registration,
        1000,
        30_000_001_000,
        "2" * 64,
    )
    m1_owners = []
    for level, resource in (
        (module.LeaseLevel.CELL, cell),
        (module.LeaseLevel.SESSION, session),
    ):
        owned = owner("m1", level, 201, "d").core_dict()
        owned.update(
            resource_id=resource,
            resource_sha256=module.LeaseSpec(level, resource).resource_sha256,
            source_binding_sha256=binding,
        )
        m1_owners.append({**owned, "owner_sha256": module.canonical_sha256(owned)})
    evidence = {
        "schema": module._EVIDENCE_SCHEMA,
        "source_sha256": source,
        "permit_sha256": permit.permit_sha256,
        "attempt_id": permit.attempt_id,
        "selected_identity_sha256": admission.selected_identity_sha256,
        "lease_levels": ["CELL", "SESSION"],
        "lease_owners": m1_owners,
        "device_effects": dict(module.ZERO_EFFECTS),
    }
    receipt = module.WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        runtime["executable_sha256"],
        admission.selected_identity_sha256,
        module.EffectCertainty.CONFIRMED,
        True,
        module.ObservedPowerState.UNKNOWN,
        0,
        0,
        0,
        0,
        0,
        len(module._canonical(evidence)),
        (sha(evidence),),
        module.PHYSICAL_DIAGNOSTIC_COMPOSITION,
    )
    outcome = {
        "attempt_id": permit.attempt_id,
        "state": "SEALED_KNOWN",
        "permit_sha256": permit.permit_sha256,
        "reason_codes": [],
        "receipt": document(asdict(receipt)),
        "quarantine_latched": False,
        "composition": module.PHYSICAL_DIAGNOSTIC_COMPOSITION,
        "physical_authority": "NONE",
    }

    def record(kind, body):
        raw = {
            "schema": "rocell.m1_physical_diagnostic_record.v1",
            "kind": kind,
            "composition": module.PHYSICAL_DIAGNOSTIC_COMPOSITION,
            "physical_authority": False,
            "data": body,
        }
        return {**raw, "record_sha256": module._sha(module.canonical_json_bytes(raw))}

    aid, psha = permit.attempt_id, permit.permit_sha256
    records = {
        f"request-{module._sha(request.request_key.encode('ascii'))}.json": record(
            "EXACT_REQUEST_RESERVED",
            {
                "request_key": request.request_key,
                "attempt_id": aid,
                "permit_sha256": psha,
                "permit": document(asdict(permit)),
            },
        ),
        f"result-{aid}-sealed_known.json": record(
            "CAMPAIGN_RESULT",
            {"attempt_id": aid, "permit_sha256": psha, "result": outcome},
        ),
        f"evidence-{aid}-retained.json": record(
            "CAMPAIGN_EVIDENCE",
            {
                "attempt_id": aid,
                "permit_sha256": psha,
                "evidence": [
                    {
                        "schema": module._EVIDENCE_SCHEMA,
                        "label": "ownership-no-device",
                        "payload_bytes": len(module._canonical(evidence)),
                        "payload_sha256": sha(evidence),
                        "payload_base64": module.base64.b64encode(
                            module._canonical(evidence)
                        ).decode("ascii"),
                    }
                ],
            },
        ),
        **{
            f"receipt-{aid}-{state.lower()}.json": record(
                "CAMPAIGN_RECEIPT",
                {
                    "attempt_id": aid,
                    "permit_sha256": psha,
                    "state": state,
                    "receipt": outcome["receipt"],
                },
            )
            for state in ("EFFECT_OBSERVED", "CLEANUP_CONFIRMED")
        },
    }
    descriptor = M1CellDescriptor.build(
        cell_id=cell,
        source_binding_sha256=binding,
        durability_qualification_sha256="f" * 64,
        created_at_ns=1000,
    )
    verification = M1RuntimeVerification(
        descriptor,
        "f" * 64,
        "f" * 64,
        "f" * 64,
        5,
        (),
        (),
        "f" * 64,
        0,
        False,
        session,
        "f" * 64,
        "f" * 64,
        False,
        (),
        "f" * 64,
        "f" * 64,
    ).to_dict()
    data["m1_experiment"] = {
        "directory": str(root),
        "source_binding_sha256": binding,
        "cell_id": cell,
        "session_id": session,
        "identity": identity,
        "permit": document(asdict(permit)),
        "outcome": outcome,
        "evidence": evidence,
        "records": records,
        "verification_before": verification,
        "verification_after": verification,
        "same_owner_cached": True,
        "old_permit_denied": True,
        "reused_key_denied": True,
        "worker_calls": 1,
    }
    data["checks"] = module._derived_checks(data)
    return module.PhysicalOwnershipQualification(module._canonical(data))


def test_modeled_report_fixture_is_strict_and_detached():
    report = modeled_report()
    assert report.safe_summary()["status"] == "SOFTWARE_OWNERSHIP_COVERED"
    report.to_dict()["device_effects"]["device_opens"] = 100
    assert report.to_dict()["device_effects"]["device_opens"] == 0
    assert modeled_report(covered=False).safe_summary()["status"] == "HELD"


@pytest.fixture
def modeled():
    return modeled_report()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update(physical_authority=True),
        lambda data: data.update(hardware_qualified=True),
        lambda data: data["device_effects"].update(device_opens=1),
        lambda data: data["device_effects"].update(device_opens=False),
        lambda data: data.update(residuals=[]),
        lambda data: data["runtime"].update(child=r"C:\untrusted.py"),
        lambda data: data["checks"][5].update(provenance="ACTUAL_HOST_MECHANISM"),
        lambda data: data["durability"].update(qualified_for_effects=False),
        lambda data: data["lease_experiment"]["clean"]["held"].reverse(),
        lambda data: data["lease_experiment"]["clean"]["process"].update(pid=999),
        lambda data: data["lease_experiment"]["clean"]["request"].update(
            source_sha256="9" * 64
        ),
        lambda data: data["lease_experiment"]["crash"]["request"].update(
            directory=r"C:\elsewhere"
        ),
        lambda data: data["lease_experiment"]["pid_mismatch"].update(
            provenance="ACTUAL_HOST_MECHANISM"
        ),
        lambda data: data["m1_experiment"]["identity"].update(physical_device=True),
        lambda data: data["m1_experiment"]["evidence"]["lease_owners"][0].update(
            pid=999
        ),
        lambda data: data["m1_experiment"]["evidence"].update(
            lease_levels=["CELL", "CAMERA"]
        ),
        lambda data: data["m1_experiment"]["records"].clear(),
        lambda data: data["m1_experiment"]["verification_after"].update(
            runtime_activation=True
        ),
        lambda data: data.update(elapsed_ns=module.MAX_DURATION_NS),
    ],
)
def test_rehashed_invalid_records_cannot_claim_coverage(modeled, mutation):
    data = modeled.to_dict()
    mutation(data)
    with pytest.raises((ValueError, RuntimeError, KeyError, TypeError)):
        module.PhysicalOwnershipQualification(module._canonical(data))


@pytest.mark.parametrize(
    "case,field,value",
    [
        ("clean", "returncode", 2),
        ("clean", "remaining_handles", 1),
        ("crash", "tree_exited", False),
        ("clean", "cleanup_errors", ["PIPE_CLOSE_FAILED"]),
        ("crash", "stdout_eof", False),
    ],
)
def test_real_failed_observations_are_retained_held(modeled, case, field, value):
    data = modeled.to_dict()
    data["lease_experiment"][case]["process"][field] = value
    data["checks"] = module._derived_checks(data)
    report = module.PhysicalOwnershipQualification(module._canonical(data))
    assert report.safe_summary()["status"] == "HELD"
    assert report.to_dict()["lease_experiment"][case]["process"][field] == value


@pytest.mark.parametrize(
    "field", ["same_owner_cached", "old_permit_denied", "reused_key_denied"]
)
def test_missing_no_replay_observation_holds(modeled, field):
    data = modeled.to_dict()
    data["m1_experiment"][field] = False
    data["checks"] = module._derived_checks(data)
    assert (
        module.PhysicalOwnershipQualification(module._canonical(data)).safe_summary()[
            "status"
        ]
        == "HELD"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_source_sha256", "f" * 64),
        ("expected_report_sha256", "f" * 64),
        ("expected_directory", Path(r"C:\other")),
    ],
)
def test_independent_original_context_required(modeled, field, value):
    kwargs = {
        "expected_source_sha256": SOURCE,
        "expected_directory": Path(modeled.to_dict()["binding"]["directory"]),
        "expected_report_sha256": modeled.sha256,
    }
    kwargs[field] = value
    with pytest.raises(module.PhysicalOwnershipQualificationError):
        module.verify_physical_ownership_qualification(modeled, **kwargs)


def test_pure_verifier_never_reopens_or_starts(modeled, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no runtime effects from retained verification")

    monkeypatch.setattr(module, "source_fingerprint", forbidden)
    monkeypatch.setattr(module, "_read_pin", forbidden)
    monkeypatch.setattr(module.PhysicalOnboardingM1Runtime, "open", forbidden)
    monkeypatch.setattr(module.OnboardingLeaseManager, "acquire", forbidden)
    assert (
        module.verify_physical_ownership_qualification(
            modeled,
            expected_source_sha256=SOURCE,
            expected_directory=Path(modeled.to_dict()["binding"]["directory"]),
            expected_report_sha256=modeled.sha256,
        )
        == modeled
    )


@pytest.mark.parametrize(
    "wire",
    [
        b"{}",
        b'{"schema":1,"schema":2}',
        b"[]",
        b'{"number":NaN}',
        b"x" * (module.MAX_REPORT_BYTES + 1),
    ],
    ids=["missing", "duplicate", "array", "nan", "oversized"],
)
def test_strict_json_and_budgets(wire):
    with pytest.raises((ValueError, RuntimeError)):
        module.PhysicalOwnershipQualification(wire)


def test_cancel_before_entry_creates_nothing(tmp_path):
    cancellation = Event()
    cancellation.set()
    directory = tmp_path / "never-created"
    with pytest.raises(
        module.PhysicalOwnershipQualificationError, match="OWNERSHIP_CANCELLED"
    ):
        module.collect_physical_ownership_qualification(
            WORKSPACE,
            assigned_directory=directory,
            source_sha256=SOURCE,
            cancellation=cancellation,
            progress=lambda text: None,
        )
    assert not directory.exists()


@pytest.mark.parametrize("failure", ["cancel", "progress", "source", "timeout"])
def test_partial_directory_and_historical_report_survive(
    tmp_path, monkeypatch, failure
):
    directory = tmp_path / "partial"
    cancellation = Event()
    source_calls = []

    def fingerprint(workspace):
        source_calls.append(workspace)
        return SOURCE if len(source_calls) == 1 else "f" * 64

    monkeypatch.setattr(module, "source_fingerprint", fingerprint)
    # Fixed modeled phase payloads isolate late collection failure boundaries.
    # No process or M1 is run by these tests; the actual case above covers both.
    sample = modeled_report(directory=directory).to_dict()
    monkeypatch.setattr(
        module,
        "run_on_volume_startup_self_test",
        lambda *a, **k: module.DurabilityQualificationReport.from_dict(
            sample["durability"]
        ),
    )

    def phase(data, selected, *args):
        data["lease_experiment"][selected] = sample["lease_experiment"][selected]
        # Use the collector's real pinned runtime hashes in its request body.
        row = data["lease_experiment"][selected]
        row["request"]["module_sha256s"] = {
            "physical_onboarding_leases": data["runtime"]["lease_source_sha256"],
            "physical_onboarding_durability": data["runtime"][
                "durability_source_sha256"
            ],
        }
        ready = {
            "schema": "rocell.ownership_child_ready.v1",
            "request_sha256": module._sha(module._canonical(row["request"])),
            "pid": row["process"]["pid"],
            "owners": row["held"],
        }
        first, _, rest = row["process"]["stdout"].partition("\n")
        row["process"]["stdout"] = (
            module._canonical(ready).decode("ascii") + "\n" + rest
        )

    monkeypatch.setattr(module, "_child_phase", phase)
    monkeypatch.setattr(
        module,
        "_pid_case",
        lambda data, check: data["lease_experiment"].update(
            pid_mismatch=sample["lease_experiment"]["pid_mismatch"]
        ),
    )

    # These tests stop before a M1 result, so the held report contains no made-up
    # partial persistent attempt and never purports to prove M1 no-replay.
    def m1(data, check, event):
        if failure == "cancel":
            cancellation.set()
        elif failure == "progress":
            raise RuntimeError("modeled callback failure")
        elif failure == "timeout":
            raise module.PhysicalOwnershipQualificationError("OWNERSHIP_TIMED_OUT")

    monkeypatch.setattr(module, "_m1_case", m1)
    with pytest.raises(module.PhysicalOwnershipQualificationError) as caught:
        module.collect_physical_ownership_qualification(
            WORKSPACE,
            assigned_directory=directory,
            source_sha256=SOURCE,
            cancellation=cancellation,
            progress=lambda text: None,
        )
    assert directory.is_dir()
    assert caught.value.report is not None
    assert caught.value.report.safe_summary()["status"] == "HELD"
    assert caught.value.report.to_dict()["lease_experiment"]["clean"]["held"]


def test_no_arbitrary_worker_or_module_selectors():
    import inspect

    signature = inspect.signature(module.collect_physical_ownership_qualification)
    assert set(signature.parameters) == {
        "workspace",
        "assigned_directory",
        "source_sha256",
        "cancellation",
        "progress",
        "deadline_ns",
    }
    child = (WORKSPACE / module.CHILD_PATH).read_text(encoding="utf-8")
    assert (
        'names = ("physical_onboarding_durability", "physical_onboarding_leases")'
        in child
    )
    assert "pytest" not in child and "subprocess" not in child and "serial" not in child


@pytest.mark.skipif(os.name != "nt", reason="actual incapable Windows child")
def test_actual_stop_after_ready_retains_stale_records_and_cleans_job(
    tmp_path, monkeypatch
):
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    cancellation = Event()
    original = WindowsOwnedProcess.send_final_input

    def stop_before_final(self, wire, *, check):
        cancellation.set()
        return original(self, wire, check=check)

    monkeypatch.setattr(WindowsOwnedProcess, "send_final_input", stop_before_final)
    monkeypatch.setattr(module, "source_fingerprint", lambda workspace: SOURCE)
    directory = tmp_path / "stopped-original"
    with pytest.raises(module.PhysicalOwnershipQualificationError) as caught:
        module.collect_physical_ownership_qualification(
            WORKSPACE,
            assigned_directory=directory,
            source_sha256=SOURCE,
            cancellation=cancellation,
            progress=lambda text: None,
        )
    report = caught.value.report
    assert report is not None and caught.value.code == "OWNERSHIP_CANCELLED"
    row = report.to_dict()["lease_experiment"]["clean"]
    assert row["held"] and row["after_live_denial"] == row["held"]
    assert row["process"]["created"] and row["process"]["tree_exited"]
    assert row["process"]["remaining_handles"] == row["process"]["remaining_pins"] == 0
    assert row["process"]["stdin_bytes"] == len(module._canonical(row["request"])) + 1
    assert len(list(directory.glob("*.owner.json"))) == 4
    assert all(
        json.loads(path.read_bytes())["state"] == "ACTIVE"
        for path in directory.glob("*.owner.json")
    )
    assert report.to_dict()["m1_experiment"] is None


def test_global_owner_hold_does_not_create_another_process(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "source_fingerprint", lambda workspace: SOURCE)
    source_report = modeled_report(directory=tmp_path / "held").to_dict()["durability"]
    monkeypatch.setattr(
        module,
        "run_on_volume_startup_self_test",
        lambda *a, **k: module.DurabilityQualificationReport.from_dict(source_report),
    )
    assert module.shared_process._DISPATCH_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(module.PhysicalOwnershipQualificationError) as caught:
            module.collect_physical_ownership_qualification(
                WORKSPACE,
                assigned_directory=tmp_path / "held",
                source_sha256=SOURCE,
                cancellation=Event(),
                progress=lambda text: None,
            )
        assert caught.value.code == "OWNED_PROCESS_ALREADY_RUNNING"
        assert caught.value.report.to_dict()["lease_experiment"] == {
            "clean": None,
            "crash": None,
            "pid_mismatch": None,
        }
    finally:
        module.shared_process._DISPATCH_LOCK.release()


def test_byte_counter_and_bool_disguises_cannot_rehash_to_coverage(modeled):
    for mutate in (
        lambda data: data["checks"][0].update(passed=1),
        lambda data: data["lease_experiment"]["clean"]["process"].update(stdin_bytes=0),
        lambda data: data["m1_experiment"]["verification_after"].update(
            runtime_activation=0
        ),
    ):
        data = modeled.to_dict()
        mutate(data)
        with pytest.raises((ValueError, RuntimeError)):
            module.PhysicalOwnershipQualification(module._canonical(data))


@pytest.mark.skipif(os.name != "nt", reason="actual qualified Windows NTFS required")
def test_actual_fixed_child_and_original_m1_no_replay(tmp_path, monkeypatch):
    # Only the current-source check is modeled while peers edit production.
    # All lease/process/NTFS/M1 operations below are the actual implementation.
    monkeypatch.setattr(module, "source_fingerprint", lambda workspace: SOURCE)
    directory = tmp_path / "ownership-experiment"
    try:
        report = module.collect_physical_ownership_qualification(
            WORKSPACE,
            assigned_directory=directory,
            source_sha256=SOURCE,
            cancellation=Event(),
            progress=lambda text: None,
        )
    except module.PhysicalOwnershipQualificationError as error:
        if error.report:
            print(error.report.to_dict()["terminal_error"])
            for phase in ("clean", "crash"):
                row = error.report.to_dict()["lease_experiment"][phase]
                if row:
                    print(phase, row["process"]["stderr"])
        raise
    assert report.safe_summary()["status"] == "SOFTWARE_OWNERSHIP_COVERED"
    assert all(row["passed"] for row in report.safe_summary()["checks"])
    assert report.to_dict()["m1_experiment"]["worker_calls"] == 1
    assert report.to_dict()["lease_experiment"]["crash"]["process"]["returncode"] == 73
    assert len(list(directory.glob("*.owner.json"))) == 9
    assert (
        module.verify_physical_ownership_qualification(
            report.payload,
            expected_source_sha256=SOURCE,
            expected_directory=directory,
            expected_report_sha256=report.sha256,
        )
        == report
    )
    # Preserved stale/crash artifacts are not cleaned/repaired by this verifier.
    before = {path.name: path.read_bytes() for path in directory.glob("*.owner.json")}
    report.safe_summary()
    assert before == {
        path.name: path.read_bytes() for path in directory.glob("*.owner.json")
    }
    with pytest.raises(module.PhysicalOwnershipQualificationError):
        module.collect_physical_ownership_qualification(
            WORKSPACE,
            assigned_directory=directory,
            source_sha256=SOURCE,
            cancellation=Event(),
            progress=lambda text: None,
        )
