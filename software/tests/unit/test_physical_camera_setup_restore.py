"""Pure restore/depth joins using actual generated prerequisite documents.

The four fixed requirement files are read by the real collector. Session audit
projections and references are explicitly modeled here, not NTFS qualification;
the public original-store smoke covers that separate integration. No session is
created, no prerequisite is replayed on restore, and no device is accessed.
"""

from collections import OrderedDict
import json
from pathlib import Path
import threading
import time

import pytest

from rocell.application.arrival_wizard_service import (
    ArrivalWizardService,
    MAX_RESULT_BYTES,
)
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_setup_service import PhysicalCameraSetupService
from rocell.application import physical_camera_prerequisites as prerequisites
from rocell.application import physical_source_preflight as preflight
from rocell.application.physical_camera_selection import selection_from_enrollment
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.physical_onboarding_durability import canonical_sha256
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import (
    MAX_DEPTH,
    WizardDiagnosticExportError,
    sanitize_diagnostic_record,
)
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_native_camera_metadata import (
    RehearsalNativeCameraMetadataProvider,
)
from rocell.providers.windows.camera_worker_client import (
    CameraCandidate,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_physical_camera_prerequisites import SOURCE, held_preflight, workspace
from test_wizard_native_camera_enrollment import generic_review

LAUNCH = "wizard-" + "1" * 32


@pytest.fixture(autouse=True)
def no_devices_or_processes(monkeypatch):
    import subprocess

    def denied(*args, **kwargs):
        pytest.fail("restore/retention tests must not invoke processes or devices")

    monkeypatch.setattr(subprocess, "Popen", denied)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, denied)


def enrollment(*, reviewer="endpoint-reviewer", reviewed=True):
    """Closed incapable packets shaped as physical metadata, never observations."""
    provider = RehearsalNativeCameraMetadataProvider()
    inventory = provider.inventory()
    candidate = CameraCandidate(**inventory["receipt"]["devices"][0])
    identity = provider.identity(candidate)
    descriptor = {"provenance": "WINDOWS_NATIVE_METADATA", "helper_sha256": "b" * 64}
    for packet in (inventory, identity):
        packet.update(descriptor)
    model = WizardNativeCameraEnrollment("physical", LAUNCH, SOURCE, descriptor)
    model.ingest_inventory(
        inventory,
        operation_id="incapable-inventory",
        generic_review=generic_review(mode="physical", session=LAUNCH),
    )
    token = model.choices()[0]["value"]
    model.retain_identity(token, identity, operation_id="incapable-identity")
    if reviewed:
        model.review(token, reviewer)
    return model


@pytest.fixture
def generated(workspace):
    acquisition = PhysicalCameraAcquisitionService(
        workspace,
        launch_id=LAUNCH,
        source_sha256=SOURCE,
        mode="physical",
    )
    setup = PhysicalCameraSetupService(acquisition)
    model, report = enrollment(), held_preflight()
    selected = selection_from_enrollment(
        model, source_sha256=SOURCE, launch_session_id=LAUNCH
    )
    artifact = prerequisites.collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=acquisition.session_id,
        launch_session_id=LAUNCH,
        cancellation=threading.Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
        selection=selected,
        source_preflight_report=report,
        expected_source_preflight_sha256=report.sha256,
    )
    # Only the audit projection is modeled: the real payload/hash is generated
    # above, while fake package/manifest hashes do not claim a published store.
    reference = EvidenceReference(
        "evidence-" + "d" * 64,
        STAGE_ORDER[0],
        "d" * 64,
        "e" * 64,
        artifact.evidence_sha256,
        len(artifact.payload),
    ).to_dict()
    setup._retained = {
        "document": artifact.to_dict(),
        "evidence_sha256": artifact.evidence_sha256,
        "retention": "M1_FULL_BYTES_READ_BACK",
        "reference": reference,
    }
    setup.session._cached.update(
        status="REFRESHED_STORAGE_ONLY",
        initialize_attempted=True,
        verification={
            "effects_allowed_by_m1_storage": True,
            "challenge_sha256": "c" * 64,
            "session": {"evidence_inventory_sha256": canonical_sha256([reference])},
        },
        stages=[
            {
                "stage": stage.value,
                "state": "WAITING_OPERATOR" if i == 0 else "PENDING",
                "last_event_sequence": 0 if i == 0 else None,
                "evidence_ids": [],
            }
            for i, stage in enumerate(STAGE_ORDER)
        ],
    )
    return setup, artifact, model, report


def original_inventory(setup):
    setup.session._cached["verification"]["session"]["evidence_inventory_sha256"] = (
        canonical_sha256([setup._retained["reference"]])
    )


def test_exact_audited_original_context_restores_without_replay_or_io(
    generated, monkeypatch
):
    setup, artifact, model, report = generated
    retained_before = setup.retained_diagnostics()

    def denied(*args, **kwargs):
        pytest.fail("original restore replayed collection or performed filesystem IO")

    with monkeypatch.context() as patch:
        patch.setattr(prerequisites, "collect_physical_camera_prerequisites", denied)
        patch.setattr(setup, "_collect", denied)
        for method in ("open", "read_bytes", "stat", "mkdir"):
            patch.setattr(Path, method, denied)
        setup._restore_prerequisites(model, report)
    assert setup._prerequisites == artifact.safe_summary()
    assert setup.view()["prerequisites"] is None  # Outer publication still required.
    assert setup.retained_diagnostics() == retained_before
    assert setup._prerequisites["qualified"] is False
    assert setup._prerequisites["source_preflight"]["outcome"] == "HELD"
    setup._publication = {"status": "PENDING", "operation_id": None}
    setup.publication_completed("explicit-refresh-operation")
    view = setup.view()
    view["prerequisites"]["epochs"][0]["status"] = "CHANGED"
    assert setup.view()["prerequisites"] == artifact.safe_summary()
    assert (
        setup.retained_diagnostics()["prerequisites"]["document"] == artifact.to_dict()
    )


@pytest.mark.parametrize(
    "fault",
    [
        "inventory-empty",
        "inventory-extra",
        "selection-changed",
        "selection-missing",
        "preflight-changed",
        "preflight-missing",
        "unread",
        "unverified",
    ],
)
def test_changed_or_missing_audited_context_withholds_without_recollection(
    generated, fault
):
    setup, artifact, model, report = generated
    original = setup.retained_diagnostics()["prerequisites"]
    if fault.startswith("inventory-"):
        refs = (
            []
            if fault == "inventory-empty"
            else [original["reference"], original["reference"]]
        )
        setup.session._cached["verification"]["session"][
            "evidence_inventory_sha256"
        ] = canonical_sha256(refs)
    elif fault == "selection-changed":
        model = enrollment(reviewer="another-reviewer")
    elif fault == "selection-missing":
        model = enrollment(reviewed=False)
    elif fault == "preflight-changed":
        data = json.loads(report.payload)
        data["binding"]["operator_id"] = "different-source-operator"
        report = preflight.PhysicalSourcePreflightReport(preflight._canonical(data))
    elif fault == "preflight-missing":
        report = None
    elif fault == "unread":
        setup._retained["retention"] = "M1_PUBLISHED_READBACK_PENDING"
    else:
        setup.session._cached["verification"] = None
    setup.invalidate()  # Actual refresh perform invalidates before restoration.
    setup._restore_prerequisites(model, report)
    assert setup._prerequisites is None
    assert setup.view()["prerequisites"] is None
    assert (
        setup.retained_diagnostics()["prerequisites"]["document"] == artifact.to_dict()
    )


@pytest.mark.parametrize(
    "field,value", [("payload_sha256", "f" * 64), ("payload_bytes", 1)]
)
def test_inventory_matching_but_raw_reference_mismatch_is_rejected(
    generated, field, value
):
    setup, _, model, report = generated
    setup._retained["reference"][field] = value
    original_inventory(setup)  # Reach independent reference/content comparison.
    with pytest.raises(WizardError) as raised:
        setup._restore_prerequisites(model, report)
    assert raised.value.code == "CAMERA_SETUP_RETAINED_REFERENCE"
    assert setup._prerequisites is None


@pytest.mark.parametrize(
    "field", ["source_sha256", "session_id", "launch_session_id", "evidence_sha256"]
)
def test_current_expected_document_bindings_cannot_be_replaced(
    generated, field, monkeypatch
):
    setup, _, model, report = generated
    if field == "source_sha256":
        setup.source_sha256 = "f" * 64
    elif field == "launch_session_id":
        setup.launch_id = "wizard-" + "2" * 32
    elif field == "session_id":
        descriptor = setup.session.descriptor()
        descriptor["session_id"] = "physical-camera-" + "2" * 32
        monkeypatch.setattr(setup.session, "descriptor", lambda: descriptor)
    else:
        setup._retained[field] = "f" * 64
    with pytest.raises(prerequisites.PhysicalCameraPrerequisitesError):
        setup._restore_prerequisites(model, report)
    assert setup._prerequisites is None


def normal_result(generated, monkeypatch):
    setup, _, model, report = generated
    monkeypatch.setattr(setup.session, "refresh", lambda **kwargs: setup.session.view())
    # This test isolates wire depth, not M1 role readback. The new explicit
    # refresh performs that separately tested audit before projecting records.
    monkeypatch.setattr(
        setup,
        "_read_source_workflow",
        lambda *args: setup._restore_prerequisites(model, report),
    )
    context = setup.context_sha256("physical_camera_refresh", model, report)
    return setup.perform(
        "physical_camera_refresh",
        expected_context_sha256=context,
        operator_id="operator",
        enrollment=model,
        source_report=report,
        cancellation=threading.Event(),
        progress=lambda _: None,
    )


def depth(value):
    children = (
        value.values()
        if isinstance(value, dict)
        else value if isinstance(value, list) else ()
    )
    return max((depth(child) + 1 for child in children), default=0)


def finish_in_memory(result, status):
    """Actual final sanitizer/retention, isolated from logs and application IO."""
    service = object.__new__(ArrivalWizardService)
    service._operations = {"test": {"action_id": "physical_camera_refresh"}}
    service._tickets, service._latest_by_section = {}, {}
    service._full_results = OrderedDict()
    service._running = None
    service._append_event = lambda *args: True
    service._changed = lambda **kwargs: None
    service._finish("test", status, result)
    return service._operations["test"], service._full_results["test"]


def test_current_shallow_normal_result_preserves_full_payload_at_depth12(
    generated, monkeypatch
):
    setup, artifact, _, _ = generated
    result = normal_result(generated, monkeypatch)
    report = result["steps"][0]["report"]
    assert report["prerequisite_document"] == artifact.to_dict()
    assert "document" not in report["prerequisites"]
    assert (
        setup.retained_diagnostics()["prerequisites"]["document"] == artifact.to_dict()
    )
    assert MAX_DEPTH == 12 and depth(result) == MAX_DEPTH
    validator = object.__new__(ArrivalWizardService)
    assert validator._validated_result("physical_camera_refresh", result) == result
    operation, retained = finish_in_memory(result, "SUCCEEDED")
    assert operation["status"] == "SUCCEEDED" and retained == result
    assert (
        canonical(retained["steps"][0]["report"]["prerequisite_document"])
        == artifact.payload
    )


def test_late_failure_retains_full_normal_and_historical_payloads_without_depth_relaxation(
    generated, monkeypatch
):
    setup, artifact, _, _ = generated
    result = normal_result(generated, monkeypatch)
    setup.invalidate()
    # Exact root exception envelope shape: returned normal result plus original
    # diagnostics survives late source/Stop failure, but is never current.
    result.update(
        status="FAILED",
        retained_camera_setup=setup.retained_diagnostics(),
        code="SOURCE_CHANGED",
        message="Source changed after report return.",
        error_type="WizardError",
        physical_authority=False,
    )
    assert depth(result) == MAX_DEPTH
    assert sanitize_diagnostic_record(result, maximum_bytes=MAX_RESULT_BYTES) == result
    operation, retained = finish_in_memory(result, "FAILED")
    assert operation["status"] == "FAILED" and retained == result
    assert (
        retained["retained_camera_setup"]["prerequisites"]["document"]
        == artifact.to_dict()
    )
    assert retained["steps"][0]["report"]["prerequisite_document"] == artifact.to_dict()
    assert setup.view()["prerequisites"] is None


def test_old_extra_nesting_fails_closed_in_normal_and_terminal_sanitizers(
    generated, monkeypatch
):
    old = normal_result(generated, monkeypatch)
    report = old["steps"][0]["report"]
    report["prerequisites"]["document"] = report.pop("prerequisite_document")
    assert depth(old) == MAX_DEPTH + 1
    with pytest.raises(WizardDiagnosticExportError, match="nesting"):
        sanitize_diagnostic_record(old, maximum_bytes=MAX_RESULT_BYTES)
    validator = object.__new__(ArrivalWizardService)
    with pytest.raises(WizardError) as raised:
        validator._validated_result("physical_camera_refresh", old)
    assert raised.value.code == "RESULT_RETENTION_LIMIT"
    operation, retained = finish_in_memory(old, "SUCCEEDED")
    assert operation["status"] == "FAILED"
    assert retained["code"] == "RESULT_RETENTION_LIMIT"
    assert "steps" not in retained  # No silent partial-document success.
