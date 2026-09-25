"""Actual copied files, no device or M1 durability claims from test permits."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
from threading import Event

import pytest

import rocell.application.physical_source_preflight as module
from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CommissioningMode,
    ExactOperationPermit,
    ObservedPowerState,
    RegisteredActionRequest,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.commissioning_physical_persistence import (
    physical_diagnostic_source_binding,
)

WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture
def workspace(tmp_path):
    """Copy only the declared closure plus broad fingerprint's required entries."""
    for relative in (
        *module.SOURCE_PREFLIGHT_SCOPE,
        "rocell.ps1",
        "software/pyproject.toml",
    ):
        source = WORKSPACE / relative
        if not source.is_file():
            pytest.skip(
                f"Checked-in/local native development artifact missing: {relative}"
            )
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return tmp_path


def components(workspace, *, clock=lambda: 100):
    source = source_fingerprint(workspace)
    registration = module.source_preflight_registration(workspace)
    snapshot = AdmissionSnapshot(
        "wizard-physical-diagnostic-" + "1" * 16,
        "physical-diagnostic-" + "2" * 32,
        CommissioningMode.PHYSICAL_DIAGNOSTIC,
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        V2StageState.WAITING_OPERATOR,
        1,
        physical_diagnostic_source_binding(source),
        *("b" * 64 for _ in range(7)),
        tuple("c" * 64 for _ in range(8)),
        None,
        False,
        0,
    )
    request = RegisteredActionRequest(
        snapshot.cell_id,
        snapshot.session_id,
        module.SOURCE_PREFLIGHT_ACTION_ID,
        "request-1",
        snapshot.challenge_sha256,
    )
    permit = ExactOperationPermit(
        "attempt-1", request, snapshot, registration, 1, 1_000_000_000, "nonce-1"
    )
    worker = module.PhysicalSourcePreflightWorker(
        workspace,
        expected_source_sha256=source,
        worker_executable_sha256=registration.worker_executable_sha256,
        operator_id="operator-a",
        clock_ns=clock,
    )
    return worker, permit


def run(workspace, *, authorization=None):
    worker, permit = components(workspace)
    calls = []
    result = worker.run_retained_campaign(
        permit,
        deadline_ns=900_000_000,
        cancellation=Event(),
        authorize_consumed_permit=authorization or calls.append,
    )
    return worker, permit, result, calls


def document(report):
    return json.loads(report.payload)


def encode(value):
    return module._canonical(value)


def assert_original_probe_source_gap(data, workspace):
    """Current source is newer than the preserved probe build, not reapproved.

    The capture increment intentionally changed camera_worker.cpp; neither this
    copied-file fixture nor the new runtime inspector rebuilds that old binary.
    Require exactly the known gap so unrelated regressions cannot hide in HELD.
    """
    assert data["outcome"] == "HELD", data["checks"]
    assert data["errors"] == []
    assert {row["check_id"]: row["passed"] for row in data["checks"]} == {
        "fixed_source_closure": True,
        "current_software_fingerprint": True,
        "worker_source_binding": True,
        "foundation_semantics": True,
        "native_development_build_bytes": False,
        "unchanged_source_snapshot": True,
    }
    comparisons = data["observations"]["native_development_build"]["comparisons"]
    failed = [row for row in comparisons if not row["matched"]]
    path = module._NATIVE_ROOT + "camera_worker.cpp"
    raw = (workspace / path).read_bytes()
    assert failed == [
        {
            "path": path,
            "expected_sha256": "8aba11a34ba1a20dbaab6563f44b13b21c954445dc466cb52b6a256145896f79",
            "observed_sha256": "ab584dfb3b98d1c82fa41653311f94d321284ec0a13abb0952e47463fba7b4b7",
            "expected_bytes": None,
            "observed_bytes": len(raw),
            "matched": False,
        }
    ]
    assert failed[0]["observed_sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(comparisons) == len(module._NATIVE_SOURCES) + len(
        module._NATIVE_ARTIFACTS
    )
    assert all(row["matched"] for row in comparisons if row["path"] != path)


def test_actual_files_and_existing_foundation_producer(workspace, monkeypatch):
    import rocell.application.bootstrap as bootstrap
    import rocell.application.b0477_static_vision as vision

    monkeypatch.setattr(bootstrap, "bootstrap_virtual_workcell", forbidden)
    monkeypatch.setattr(vision, "run_b0477_static_vision_rehearsal", forbidden)
    worker, permit, result, calls = run(workspace)
    report = worker.report
    data = document(report)
    # This uses real copied bytes and real validators, but its permit is a
    # typed fixture; root owns the separate real M1/coordinator integration.
    assert calls == [permit]
    assert_original_probe_source_gap(data, workspace)
    assert len(data["files"]) == len(module.SOURCE_PREFLIGHT_SCOPE)
    assert data["canonical_stage_pass"] is False
    assert "DISCONNECTED_REQUIRED_NOT_OBSERVED" in data["canonical_stage_holds"]
    assert "HZ_012_CANONICAL_EVIDENCE_NOT_CLOSED" in data["canonical_stage_holds"]
    assert data["power_state"] == "UNKNOWN"
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert result.receipt.composition == module.SOURCE_PREFLIGHT_COMPOSITION
    assert [
        result.receipt.opens,
        result.receipt.reads,
        result.receipt.writes,
        result.receipt.frames,
        result.receipt.closes,
    ] == [0] * 5
    assert result.receipt.evidence_sha256s == (report.sha256,)
    assert result.receipt.output_bytes == len(report.payload)
    assert result.evidence[0].payload == report.payload
    assert len(report.payload) < 96 * 1024
    assert str(workspace) not in report.payload.decode()


def test_explicit_incapable_coherent_file_fixture_preserves_positive_checks(workspace):
    """Positive file-comparison coverage, not approval of an installed build.

    Only this test-owned copied closure is changed. All native source/artifact
    bytes are explicitly modeled and no artifact is a runnable native helper.
    The real historical record and executable remain untouched and held above.
    """
    manifest_path = workspace / module._NATIVE_MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["purpose"] = "Explicit incapable file-comparison fixture; not a build"
    for relative in module._NATIVE_SOURCES:
        raw = ("INCAPABLE SOURCE FILE FIXTURE: " + relative).encode("ascii")
        (workspace / module._NATIVE_ROOT / relative).write_bytes(raw)
        manifest["source_files"][relative] = hashlib.sha256(raw).hexdigest()
    for artifact in manifest["artifacts"]:
        raw = ("NOT AN EXECUTABLE; FILE-ONLY FIXTURE: " + artifact["path"]).encode(
            "ascii"
        )
        (workspace / module._NATIVE_ROOT / artifact["path"]).write_bytes(raw)
        artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        artifact["length_bytes"] = len(raw)
        artifact["executed"] = False
    manifest_path.write_bytes(encode(manifest))
    worker, _, result, _ = run(workspace)
    data = document(worker.report)
    assert data["outcome"] == "FILE_CHECKS_COHERENT", data["checks"]
    assert data["errors"] == [] and all(row["passed"] for row in data["checks"])
    assert data["physical_authority"] is data["canonical_stage_pass"] is False
    assert data["canonical_stage_holds"]
    assert data["power_state"] == "UNKNOWN"
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert result.receipt.opens == result.receipt.reads == result.receipt.writes == 0
    assert result.receipt.frames == result.receipt.closes == 0


def forbidden(*args, **kwargs):
    raise AssertionError(
        "This boundary must not perform I/O or invoke another provider"
    )


def test_constructor_and_summary_and_verifier_are_inert(workspace, monkeypatch):
    worker, permit, _, _ = run(workspace)
    report = worker.report
    monkeypatch.setattr(module, "_checked", forbidden)
    monkeypatch.setattr(module, "read_bounded_regular_file", forbidden)
    monkeypatch.setattr(module, "source_fingerprint", forbidden)
    monkeypatch.setattr(module, "load_physical_onboarding_foundation", forbidden)
    created = module.PhysicalSourcePreflightWorker(
        workspace,
        expected_source_sha256="a" * 64,
        worker_executable_sha256="b" * 64,
        operator_id="operator",
    )
    assert created.report is None
    verified = module.verify_physical_source_preflight(
        report.payload,
        expected_source_sha256=worker.expected_source_sha256,
        expected_permit_sha256=permit.permit_sha256,
        expected_worker_sha256=worker.worker_executable_sha256,
    )
    assert verified.safe_summary()["physical_authority"] is False
    assert verified.safe_summary()["canonical_stage_pass"] is False
    assert "files" not in verified.safe_summary()


@pytest.mark.parametrize(
    "relative", [module._NATIVE_ARTIFACTS[0], module._NATIVE_SOURCES[0]]
)
def test_native_bytes_changed_not_reapproved(workspace, relative):
    target = workspace / module._NATIVE_ROOT / relative
    target.write_bytes(target.read_bytes() + b"x")
    worker, _, _, _ = run(workspace)
    data = document(worker.report)
    assert data["outcome"] == "HELD"
    assert not next(
        row["passed"]
        for row in data["checks"]
        if row["check_id"] == "native_development_build_bytes"
    )
    # Baseline already has one historical source gap. Prove this corruption
    # adds the exact targeted failure, rather than passing because HELD existed.
    comparisons = data["observations"]["native_development_build"]["comparisons"]
    assert {row["path"] for row in comparisons if not row["matched"]} == {
        module._NATIVE_ROOT + "camera_worker.cpp",
        module._NATIVE_ROOT + relative,
    }
    changed = next(
        row for row in comparisons if row["path"] == module._NATIVE_ROOT + relative
    )
    assert changed["observed_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert changed["expected_sha256"] != changed["observed_sha256"]


def test_missing_file_holds_before_semantic_validation(workspace, monkeypatch):
    worker, permit = components(workspace)
    (workspace / module._NATIVE_ROOT / module._NATIVE_ARTIFACTS[0]).unlink()
    monkeypatch.setattr(module, "load_physical_onboarding_foundation", forbidden)
    result = worker.run_retained_campaign(
        permit,
        deadline_ns=900_000_000,
        cancellation=Event(),
        authorize_consumed_permit=lambda _: None,
    )
    assert document(worker.report)["outcome"] == "HELD"
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN


def test_contract_drift_holds_no_synthetic_replacement(workspace):
    target = workspace / "hardware/static_overhead_camera/config/support_design.json"
    value = json.loads(target.read_bytes())
    value["board"]["width_mm"] = 123
    target.write_text(json.dumps(value), encoding="utf-8")
    worker, _, _, _ = run(workspace)
    assert document(worker.report)["outcome"] == "HELD"
    assert document(worker.report)["observations"]["foundation"] is None


def test_oversized_file_rejected_before_content_read(workspace, monkeypatch):
    worker, permit = components(workspace)
    target = workspace / module._NATIVE_ROOT / module._NATIVE_SOURCES[0]
    with target.open("wb") as stream:
        stream.truncate(module._MAX_FILE_BYTES + 1)
    monkeypatch.setattr(module, "read_bounded_regular_file", forbidden)
    worker.run_retained_campaign(
        permit,
        deadline_ns=900_000_000,
        cancellation=Event(),
        authorize_consumed_permit=lambda _: None,
    )
    assert "FIXED_SOURCE_BYTE_BOUND" in document(worker.report)["errors"]


def test_hardlink_rejected(workspace):
    target = workspace / module._NATIVE_ROOT / module._NATIVE_SOURCES[0]
    linked = workspace / "hardlinked-source"
    os.link(target, linked)
    worker, _, _, _ = run(workspace)
    assert "HARD_LINK_REJECTED" in document(worker.report)["errors"]


@pytest.mark.parametrize(
    "when", ["before", "authorization", "snapshot", "validator", "publication"]
)
def test_cancellation_never_publishes_a_report(workspace, monkeypatch, when):
    worker, permit = components(workspace)
    cancel = Event()
    calls = []
    if when == "before":
        cancel.set()

    def authorize(value):
        calls.append(value)
        if when == "authorization":
            cancel.set()

    if when == "snapshot":
        original = module._snapshot

        def snapshot(*args):
            result = original(*args)
            cancel.set()
            return result

        monkeypatch.setattr(module, "_snapshot", snapshot)
    if when == "validator":
        original = module.load_physical_onboarding_foundation

        def validate(*args):
            result = original(*args)
            cancel.set()
            return result

        monkeypatch.setattr(module, "load_physical_onboarding_foundation", validate)
    if when == "publication":
        original = module.PhysicalSourcePreflightReport

        def report(*args):
            result = original(*args)
            cancel.set()
            return result

        monkeypatch.setattr(module, "PhysicalSourcePreflightReport", report)
    with pytest.raises(module.PhysicalSourcePreflightError, match="CANCELLED"):
        worker.run_retained_campaign(
            permit,
            deadline_ns=900_000_000,
            cancellation=cancel,
            authorize_consumed_permit=authorize,
        )
    assert worker.report is None
    assert len(calls) == (0 if when == "before" else 1)


def test_authorization_rejection_no_file_access_and_no_retry(workspace, monkeypatch):
    worker, permit = components(workspace)
    monkeypatch.setattr(module, "_checked", forbidden)

    def deny(_):
        raise ValueError("not currently consumed")

    with pytest.raises(ValueError, match="not currently consumed"):
        worker.run_retained_campaign(
            permit,
            deadline_ns=900_000_000,
            cancellation=Event(),
            authorize_consumed_permit=deny,
        )
    with pytest.raises(ValueError, match="ALREADY_USED"):
        worker.run_retained_campaign(
            permit,
            deadline_ns=900_000_000,
            cancellation=Event(),
            authorize_consumed_permit=forbidden,
        )


def test_deadline_after_authorizer_never_reads_files(workspace, monkeypatch):
    instant = [100]
    worker, permit = components(workspace, clock=lambda: instant[0])
    monkeypatch.setattr(module, "_checked", forbidden)
    with pytest.raises(ValueError, match="DEADLINE_EXPIRED"):
        worker.run_retained_campaign(
            permit,
            deadline_ns=200,
            cancellation=Event(),
            authorize_consumed_permit=lambda _: instant.__setitem__(0, 200),
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data.update(physical_authority=True),
        lambda data: data.update(canonical_stage_pass=True),
        lambda data: data.update(power_state="DEENERGIZED"),
        lambda data: data.update(composition="HARDWARE_INCAPABLE_REHEARSAL"),
        lambda data: data.update(unexpected=True),
        lambda data: data["binding"].update(operation_sha256="c" * 64),
        lambda data: data["files"][0].update(bytes=True),
        lambda data: data["files"][0].update(path="../../outside"),
        lambda data: data["observations"].update(extra=True),
        lambda data: data["checks"][0].update(passed=1),
        lambda data: data["checks"][0].update(passed=False),
        lambda data: data.update(outcome="PASS"),
    ],
)
def test_report_mutations_fail_closed(workspace, change):
    worker, _, _, _ = run(workspace)
    value = document(worker.report)
    change(value)
    with pytest.raises(ValueError):
        module.PhysicalSourcePreflightReport(encode(value))


def test_duplicate_and_noncanonical_json_rejected(workspace):
    worker, _, _, _ = run(workspace)
    payload = worker.report.payload
    for changed in (
        b'{"schema":"duplicate",' + payload[1:],
        payload + b" ",
        b"x" * (96 * 1024 + 1),
    ):
        with pytest.raises(ValueError):
            module.PhysicalSourcePreflightReport(changed)


@pytest.mark.parametrize("field", ["source", "permit", "worker"])
def test_retained_receipt_expected_bindings_are_not_embedded_trust(workspace, field):
    worker, permit, _, _ = run(workspace)
    expected = dict(
        expected_source_sha256=worker.expected_source_sha256,
        expected_permit_sha256=permit.permit_sha256,
        expected_worker_sha256=worker.worker_executable_sha256,
    )
    expected[
        {
            "source": "expected_source_sha256",
            "permit": "expected_permit_sha256",
            "worker": "expected_worker_sha256",
        }[field]
    ] = (
        "d" * 64
    )
    with pytest.raises(ValueError, match="RETAINED_BINDING_CHANGED"):
        module.verify_physical_source_preflight(worker.report.payload, **expected)


def test_registration_is_exact_zero_device_budget(workspace):
    registration = module.source_preflight_registration(workspace)
    assert (
        registration.worker_executable_sha256
        == hashlib.sha256(
            (workspace / module.SOURCE_PREFLIGHT_WORKER_PATH).read_bytes()
        ).hexdigest()
    )
    assert registration.resources == ()
    assert registration.budget.timeout_ms == 20_000
    assert registration.budget.maximum_output_bytes == 96 * 1024
    assert (
        sum(
            getattr(registration.budget, name)
            for name in (
                "maximum_opens",
                "maximum_reads",
                "maximum_writes",
                "maximum_frames",
                "maximum_closes",
            )
        )
        == 0
    )


def test_unknown_power_is_not_claimed_as_disconnected(workspace):
    worker, _, _, _ = run(workspace)
    summary = worker.report.safe_summary()
    assert_original_probe_source_gap(document(worker.report), workspace)
    assert summary["outcome"] == "HELD"
    assert summary["power_state"] == "UNKNOWN"
    assert summary["canonical_stage_holds"]
    assert summary["physical_authority"] is False
    assert summary["canonical_stage_pass"] is False


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows sharing boundary")
def test_fixed_source_cannot_be_written_or_renamed_during_validator(
    workspace, monkeypatch
):
    original = module.load_physical_onboarding_foundation
    target = workspace / module._NATIVE_ROOT / module._NATIVE_SOURCES[0]
    original_bytes = target.read_bytes()
    validator_calls = []

    def validate(root):
        validator_calls.append(root)
        with pytest.raises(OSError):
            target.write_bytes(b"changed")
        with pytest.raises(OSError):
            target.rename(target.with_suffix(".moved"))
        return original(root)

    monkeypatch.setattr(module, "load_physical_onboarding_foundation", validate)
    worker, _, _, _ = run(workspace)
    assert validator_calls == [workspace]
    assert target.read_bytes() == original_bytes
    assert_original_probe_source_gap(document(worker.report), workspace)


@pytest.mark.parametrize("case", ["mode", "domain", "request", "worker", "budget"])
def test_unapproved_permit_rejected_before_authorizer_or_source_reads(
    workspace, monkeypatch, case
):
    worker, permit = components(workspace)
    if case == "mode":
        permit = replace(
            permit,
            admission=replace(permit.admission, mode=CommissioningMode.REHEARSAL),
        )
    elif case == "domain":
        permit = replace(
            permit, admission=replace(permit.admission, source_binding_sha256="d" * 64)
        )
    elif case == "request":
        permit = replace(permit, request=replace(permit.request, action_id="unknown"))
    elif case == "worker":
        permit = replace(
            permit, registration=replace(permit.registration, worker_id="other-worker")
        )
    else:
        permit = replace(
            permit,
            registration=replace(
                permit.registration,
                budget=replace(permit.registration.budget, timeout_ms=120_000),
            ),
        )
    monkeypatch.setattr(module, "_checked", forbidden)
    with pytest.raises(ValueError, match="ZERO_DEVICE_PERMIT_REQUIRED"):
        worker.run_retained_campaign(
            permit,
            deadline_ns=900_000_000,
            cancellation=Event(),
            authorize_consumed_permit=forbidden,
        )


def test_authorizer_cannot_replace_an_already_admitted_permit(workspace, monkeypatch):
    worker, permit = components(workspace)
    monkeypatch.setattr(module, "_checked", forbidden)

    def authorize(value):
        object.__setattr__(value, "nonce", "changed-nonce")

    with pytest.raises(ValueError, match="PERMIT_CHANGED"):
        worker.run_retained_campaign(
            permit,
            deadline_ns=900_000_000,
            cancellation=Event(),
            authorize_consumed_permit=authorize,
        )


@pytest.mark.parametrize(
    "field", ["foundation_sha256", "catalog_sha256", "icd_sha256", "support_sha256"]
)
def test_retained_foundation_hashes_must_match_fixed_file_rows(workspace, field):
    worker, _, _, _ = run(workspace)
    value = document(worker.report)
    value["observations"]["foundation"][field] = "e" * 64
    with pytest.raises(ValueError, match="FOUNDATION_FILE_BINDING"):
        module.PhysicalSourcePreflightReport(encode(value))


def test_retained_manifest_comparison_is_recomputed(workspace):
    worker, _, _, _ = run(workspace)
    value = document(worker.report)
    value["observations"]["native_development_build"]["comparisons"][-1][
        "expected_bytes"
    ] += 1
    with pytest.raises(ValueError, match="NATIVE_COMPARISON_VALUE"):
        module.PhysicalSourcePreflightReport(encode(value))


def test_expected_m1_evidence_hash_is_enforced(workspace):
    worker, permit, _, _ = run(workspace)
    with pytest.raises(ValueError, match="RETAINED_REPORT_HASH_CHANGED"):
        module.verify_physical_source_preflight(
            worker.report.payload,
            expected_source_sha256=worker.expected_source_sha256,
            expected_permit_sha256=permit.permit_sha256,
            expected_worker_sha256=worker.worker_executable_sha256,
            expected_report_sha256="f" * 64,
        )


def test_current_software_change_is_held_not_rebound(workspace):
    worker, permit = components(workspace)
    target = workspace / "software/pyproject.toml"
    target.write_bytes(target.read_bytes() + b"\n")
    worker.run_retained_campaign(
        permit,
        deadline_ns=900_000_000,
        cancellation=Event(),
        authorize_consumed_permit=lambda _: None,
    )
    assert document(worker.report)["errors"] == ["SOFTWARE_SOURCE_CHANGED"]
    assert document(worker.report)["outcome"] == "HELD"


def test_native_manifest_cannot_add_an_arbitrary_source(workspace):
    target = workspace / module._NATIVE_MANIFEST
    value = json.loads(target.read_bytes())
    value["source_files"]["../../outside"] = "f" * 64
    target.write_text(json.dumps(value), encoding="utf-8")
    worker, _, _, _ = run(workspace)
    assert "NATIVE_MANIFEST_SOURCE_SET" in document(worker.report)["errors"]
    assert document(worker.report)["outcome"] == "HELD"


def test_missing_file_retains_exact_fixed_source_name(workspace):
    worker, permit = components(workspace)
    relative = module._NATIVE_ROOT + module._NATIVE_ARTIFACTS[0]
    (workspace / relative).unlink()
    worker.run_retained_campaign(
        permit,
        deadline_ns=900_000_000,
        cancellation=Event(),
        authorize_consumed_permit=lambda _: None,
    )
    assert document(worker.report)["errors"] == ["SOURCE_FILE_UNAVAILABLE"]
    assert worker.report.safe_summary()["failed_source"] == relative
