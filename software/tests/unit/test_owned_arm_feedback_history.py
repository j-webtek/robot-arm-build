"""Pure historical arm reconstruction; modeled records, no store or worker replay.

The original request.v1 operation's twelve-field shape was checked against the
retained 2026-09-08 b4868915 incident. These fixtures reproduce that closed shape
without depending on, copying into, or modifying any original M1 directory.
"""

from dataclasses import replace
import ctypes
import hashlib
from pathlib import Path
import subprocess

import pytest

from rocell.application import owned_arm_feedback_rehearsal_campaign as campaign
from rocell.application import cell_commissioning_coordinator as core
from rocell.application.arm_feedback_rehearsal_campaign import ArmFeedbackRehearsalPlan
from rocell.application.commissioning_m1_persistence import rehearsal_source_binding
from rocell.providers.windows import owned_arm_feedback_package as package
from rocell.providers.windows.arm_owned_evidence import retain_arm_owned_evidence
from rocell.providers.windows.arm_owned_protocol import (
    LEGACY_REQUEST_SCHEMA,
    PREVIOUS_REQUEST_SCHEMA,
    REQUEST_SCHEMA,
)
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from test_arm_feedback_rehearsal_campaign import controller
from test_commissioning_coordinator import _components

OLD_OPERATION_KEYS = {
    "schema",
    "plan",
    "runtime",
    "runtime_sha256",
    "directory",
    "scenario",
    "campaign_timeout_ms",
    "feedback_budget",
    "feedback_maximum_line_bytes",
    "maximum_evidence_bytes",
    "composition",
    "physical_authority",
}


def runtime_model():
    """Untrusted structural v1 descriptor: no actual package or file exists."""
    workspace = Path("C:/incapable-historical-fixture")
    digest = hashlib.sha256(b"x").hexdigest()
    names = {name + "/__init__.py" for name in package.NAMESPACES}
    modules = ["rocell/" + name for name in package.LEGACY_ROCELL_MODULES]
    modules += ["packaging/" + name for name in package.PACKAGING_MODULES]
    rows = []
    for name in sorted(names | set(modules)):
        stub = name in names
        rows.append(
            {
                "name": name,
                "path": str(workspace / name),
                "bytes": 1,
                "sha256": digest,
                "role": "NAMESPACE_SOURCE_ONLY" if stub else "EXACT_SOURCE",
                "archive_sha256": (
                    hashlib.sha256(package._STUB).hexdigest() if stub else digest
                ),
            }
        )

    def pin(path, maximum):
        return {"path": str(path), "sha256": digest, "maximum_bytes": maximum}

    return package.OwnedArmRuntime(
        package.canonical(
            {
                "schema": package.LEGACY_SCHEMA,
                "workspace": str(workspace),
                "workspace_source_sha256": "a" * 64,
                "source_closure_sha256": package.digest(rows),
                "files": rows,
                "executable": pin(workspace / "python.exe", 64 * 1024 * 1024),
                "child": pin(
                    workspace
                    / "software/src/rocell/providers/windows/_owned_arm_feedback_child.py",
                    package.MAX_FILE_BYTES,
                ),
                "package": pin(workspace / "runtime.zip", package.MAX_PACKAGE_BYTES),
                "physical_authority": False,
                "composition": "INCAPABLE_NONPURGING_ARM_WORKER",
                "packaging_qualification": "SOURCE_PINNED_DEVELOPMENT_NOT_TRUSTED_RELEASE",
                "namespace_isolation": "FIXED_INERT_STUBS_ORIGINAL_HASHES_RETAINED",
            }
        )
    )


def historical_campaign(*, request_schema=LEGACY_REQUEST_SCHEMA, form="original"):
    runtime = runtime_model()
    plan = ArmFeedbackRehearsalPlan("9" * 64, "a" * 64, controller(), "7" * 64)
    directory = Path("C:/incapable-historical-store/owned-arm-feedback")
    operation = campaign._operation(
        plan, runtime, directory, "nominal", request_schema=request_schema
    )
    if form == "original":
        if request_schema == LEGACY_REQUEST_SCHEMA:
            operation.pop("ipc_request_schema")
            operation.pop("admission_timeout_ms")
    elif form == "both-absent":
        operation.pop("ipc_request_schema")
        operation.pop("admission_timeout_ms")
    elif form == "schema-absent":
        operation.pop("ipc_request_schema")
    elif form == "duration-absent":
        operation.pop("admission_timeout_ms")
    elif form == "unknown-version":
        operation["ipc_request_schema"] = "rocell.arm_owned_request.v999"
    elif form == "mismatched-version":
        operation["ipc_request_schema"] = REQUEST_SCHEMA
    else:
        raise AssertionError(form)
    registration = campaign._operation_registration(runtime, operation)
    _, store, _, _, _ = _components(serial=True)
    snapshot = replace(
        store.snapshot,
        source_binding_sha256=rehearsal_source_binding(plan.source_sha256),
        selected_identity_sha256=plan.controller.identity.identity_sha256,
    )
    request = core.RegisteredActionRequest(
        snapshot.cell_id,
        snapshot.session_id,
        campaign.ACTION_ID,
        "historical-only",
        snapshot.challenge_sha256,
    )
    envelope = replace(
        store.envelope,
        operation_sha256=registration.operation_sha256,
        issued_at_ns=1_000_000_000,
        expires_at_ns=31_000_000_000,
    )
    permit = core.ExactOperationPermit(
        "attempt-history",
        request,
        snapshot,
        registration,
        1_000_000_000,
        31_000_000_000,
        "f" * 64,
        envelope,
    )
    started, deadline, finished = 2_000_000_000, 22_000_000_000, 2_100_000_000
    inner = campaign._request(plan, permit, started, deadline)
    prepared = campaign._prepared(
        runtime,
        inner,
        permit,
        directory,
        "nominal",
        deadline,
        historical_request_schema=request_schema,
    )
    owned = retain_arm_owned_evidence(
        request=prepared.request,
        process_result=OwnedWorkerResult(
            status="FAILED",
            primary_error="ARM_RELEASE_TIMED_OUT",
            cleanup_errors=(),
            request_sha256=prepared.request.request_sha256,
            attempt_id=permit.attempt_id,
            process_created=False,
            initial_thread_resumed=False,
            tree_exit_confirmed=False,
            returncode=None,
            elapsed_ns=finished - started,
            stdin_bytes_written=0,
            peak_observed_handles=0,
            peak_active_processes=0,
            stdout=b"",
            stderr=b"",
            parsed_result=None,
        ),
    )
    payload = campaign._canonical(
        {
            "schema": campaign.SCHEMA,
            "plan": plan.to_dict(),
            "operation": operation,
            "scenario": "nominal",
            "permit_sha256": permit.permit_sha256,
            "request": inner.to_dict(),
            "request_started_monotonic_ns": started,
            "deadline_monotonic_ns": deadline,
            "worker_finished_monotonic_ns": finished,
            "owned_evidence": owned.to_dict(),
            "owned_evidence_sha256": owned.evidence_sha256,
            "final_power_observation": None,
            "actual_effect_counts": campaign._ACTUAL_EFFECTS,
            "physical_authority": False,
            "composition": core.INCAPABLE_COMPOSITION,
        }
    )
    return payload, plan, permit, directory


def verify(fixture):
    payload, plan, permit, directory = fixture
    return campaign.verify_retained_owned_arm_feedback_campaign(
        payload,
        expected_plan=plan,
        expected_permit=permit,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        expected_directory=directory,
    )


def forbid_replay(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("historical verification attempted I/O or new admission")

    for name in ("open", "stat", "mkdir", "read_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(campaign, "prepare_owned_arm_runtime", forbidden)
    monkeypatch.setattr(campaign, "prepare_owned_arm_feedback", forbidden)
    monkeypatch.setattr(campaign, "IncapableOwnedArmFeedbackRunner", forbidden)
    monkeypatch.setattr(core.CellCommissioningCoordinator, "prepare", forbidden)
    monkeypatch.setattr(core.CellCommissioningCoordinator, "execute", forbidden)


@pytest.mark.parametrize("schema", [LEGACY_REQUEST_SCHEMA, PREVIOUS_REQUEST_SCHEMA])
def test_original_versioned_campaign_reconstructs_without_new_admission(
    schema, monkeypatch
):
    fixture = historical_campaign(request_schema=schema)
    original = campaign._decode(fixture[0])
    if schema == LEGACY_REQUEST_SCHEMA:
        assert set(original["operation"]) == OLD_OPERATION_KEYS
    with monkeypatch.context() as guard:
        forbid_replay(guard)
        verified = verify(fixture)
    assert verified.canonical_bytes() == fixture[0]
    assert (
        verified.process_summary()["schema"] == "rocell.arm_owned_evidence_summary.v1"
    )
    assert verified.resolution_diagnostics()["status"] == "NOT_RETAINED"
    assert verified.request.controller == fixture[1].controller


@pytest.mark.parametrize(
    "form",
    ["schema-absent", "duration-absent", "unknown-version", "mismatched-version"],
)
def test_partial_or_changed_historical_version_tags_are_not_guessed(form, monkeypatch):
    fixture = historical_campaign(request_schema=PREVIOUS_REQUEST_SCHEMA, form=form)
    with monkeypatch.context() as guard:
        forbid_replay(guard)
        with pytest.raises(ValueError):
            verify(fixture)


def test_absent_version_pair_cannot_silently_downgrade_a_v2_request(monkeypatch):
    fixture = historical_campaign(
        request_schema=PREVIOUS_REQUEST_SCHEMA, form="both-absent"
    )
    with monkeypatch.context() as guard:
        forbid_replay(guard)
        with pytest.raises(ValueError):
            verify(fixture)


@pytest.mark.parametrize("mutation", ["hash", "unknown-schema", "authority", "extra"])
def test_untagged_version_selection_first_requires_the_full_strict_owned_request(
    monkeypatch, mutation
):
    payload, plan, permit, directory = historical_campaign()
    document = campaign._decode(payload)
    request = document["owned_evidence"]["request"]
    if mutation == "hash":
        request["request_sha256"] = "f" * 64
    elif mutation == "unknown-schema":
        request["schema"] = "rocell.arm_owned_request.v999"
    elif mutation == "authority":
        request["physical_authority"] = True
    else:
        request["authorized"] = True
    if mutation != "hash":
        request["request_sha256"] = package.digest(
            {key: value for key, value in request.items() if key != "request_sha256"}
        )
    fixture = (campaign._canonical(document), plan, permit, directory)
    with monkeypatch.context() as guard:
        forbid_replay(guard)
        with pytest.raises(ValueError):
            verify(fixture)
