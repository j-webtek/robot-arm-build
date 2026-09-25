"""Inspect fixed files and incapable registrations; never launch any helper."""

import builtins
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from rocell.application import wizard_camera_helper_inspection as helper
from rocell.application.wizard_camera_helper_registration import (
    ReviewedCameraHelperRegistration,
    WizardCameraHelperRegistration,
)
from rocell.application.wizard_native_camera_metadata import validate_native_packet


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64


def verify(report):
    return helper.verify_camera_helper_inspection(
        report,
        expected_source_sha256=SOURCE,
        expected_inspection_sha256=report["inspection_sha256"],
        expected_provenance=report["inspection_provenance"],
    )


def register(report):
    state = WizardCameraHelperRegistration(report["mode"], "session-fixture", SOURCE)
    state.ingest(report, operation_id="inspect-001", operator_id="Inspector")
    state.review("Reviewer", operation_id="review-001")
    return state.registration()


@pytest.fixture
def copied_catalog(tmp_path):
    """Copy current bytes, preserving the real historical catalog's expected pins."""
    for row in helper.camera_helper_catalog()["files"]:
        destination = tmp_path / row["relative_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / row["relative_path"], destination)
    return tmp_path


@pytest.fixture
def isolated_reviewed_catalog(tmp_path, monkeypatch):
    """Explicit test-only pins for incapable bytes, never a production reapproval.

    The real inspector/verifier/factory still hash and validate regular files.
    The distinct catalog is scoped to this test by monkeypatch; none of these
    files contains an executable or a copy of a production native artifact.
    """
    from rocell.providers.windows import camera_worker_client as camera

    pins = []
    for index, (role, relative, _, _) in enumerate(helper._PINS):
        payload = f"INCAPABLE TEST CATALOG ONLY; row={index}; role={role}\n".encode()
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        pins.append((role, relative, hashlib.sha256(payload).hexdigest(), len(payload)))
    monkeypatch.setattr(helper, "_PINS", tuple(pins))
    monkeypatch.setattr(helper, "NATIVE_HELPER_SHA256", pins[0][2])
    monkeypatch.setattr(helper, "CATALOG_ID", "incapable-isolated-test-catalog-v1")
    monkeypatch.setattr(helper, "CATALOG_LABEL", "Incapable isolated file test catalog")

    def forbidden(*args, **kwargs):
        pytest.fail("An isolated incapable file test attempted native execution")

    monkeypatch.setattr(camera.subprocess, "Popen", forbidden)
    return tmp_path


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("nominal", "MATCHED_METADATA_CATALOG"),
        ("missing-helper", "MISSING_FILES"),
        ("hash-drift", "HASH_DRIFT"),
    ],
)
def test_fixed_incapable_reports_are_pure_strict_and_honest(
    monkeypatch, scenario, status
):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure fixture attempted filesystem or provider access")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(helper, "source_fingerprint", forbidden)
    monkeypatch.setattr(helper, "NativeCameraMetadataProvider", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    report = helper.inspect_camera_helper(
        Path("not-a-real-workspace"),
        source_sha256=SOURCE,
        mode="rehearsal",
        scenario=scenario,
    )
    assert verify(report) == report
    assert report["inspection_status"] == status
    assert report["metadata_eligible"] is (scenario == "nominal")
    assert report["helper_sha256"] == helper.FIXTURE_HELPER_SHA256
    assert report["historical_full_build_match"] is False
    assert "CLIENT_CHANGED_SINCE_BUILD_RECORD" in report["warnings"]
    for field in (
        "physical_authority",
        "camera_activation_allowed",
        "driver_qualified",
        "trusted_release",
    ):
        assert report[field] is False


def test_actual_fixed_catalog_reports_expected_source_drift_without_execution(
    copied_catalog, monkeypatch
):
    monkeypatch.setattr(
        helper,
        "WindowsCameraWorkerClient",
        lambda *a, **k: pytest.fail("Inspector constructed native client"),
    )
    report = helper.inspect_camera_helper(
        copied_catalog, source_sha256=SOURCE, mode="physical"
    )
    assert verify(report)["metadata_eligible"] is False
    assert report["inspection_status"] == "HASH_DRIFT"
    assert report["blockers"] == ["HASH_DRIFT"]
    assert report["helper_sha256"] == helper.NATIVE_HELPER_SHA256
    assert report["files"][0]["bytes"] == 179200
    assert report["files"][0]["status"] == "MATCHED"
    assert report["files"][1]["status"] == "MATCHED"
    changed = {
        row["relative_path"] for row in report["files"] if row["status"] == "HASH_DRIFT"
    }
    assert changed == {
        "software/native/windows_camera/camera_worker.cpp",
        "software/native/windows_camera/CMakeLists.txt",
        "software/native/windows_camera/identity_metadata.h",
        "software/native/windows_camera/identity_metadata.cpp",
        "software/native/windows_camera/identity_metadata_tests.cpp",
        "software/native/windows_camera/identity_metadata_wire_test.py",
        # Capture metadata/file separation changes the client, not the fixed
        # historical catalog. Do not refresh that catalog into an approval.
        "software/src/rocell/providers/windows/camera_worker_client.py",
    }
    assert all(row["status"] in {"MATCHED", "HASH_DRIFT"} for row in report["files"])
    historical = json.loads(
        (
            copied_catalog / helper.camera_helper_catalog()["files"][1]["relative_path"]
        ).read_bytes()
    )
    assert (
        historical["source_sha256"][
            "../../src/rocell/providers/windows/camera_worker_client.py"
        ]
        != report["files"][8]["observed_sha256"]
    )
    assert report["historical_full_build_match"] is False
    assert register(report) is None
    with pytest.raises(helper.CameraHelperInspectionError):
        helper.create_metadata_provider(
            copied_catalog, None, mode="physical", source_sha256=SOURCE
        )


def test_isolated_incapable_catalog_preserves_positive_file_review_coverage(
    isolated_reviewed_catalog, monkeypatch
):
    monkeypatch.setattr(
        helper,
        "WindowsCameraWorkerClient",
        lambda *a, **k: pytest.fail("Inspection/review constructed native client"),
    )
    report = helper.inspect_camera_helper(
        isolated_reviewed_catalog, source_sha256=SOURCE, mode="physical"
    )
    assert verify(report)["metadata_eligible"] is True
    assert report["catalog_id"] == "incapable-isolated-test-catalog-v1"
    assert report["inspection_status"] == "MATCHED_METADATA_CATALOG"
    assert all(row["status"] == "MATCHED" for row in report["files"])
    artifact = register(report)
    assert artifact is not None
    provider = helper.create_metadata_provider(
        isolated_reviewed_catalog, artifact, mode="physical", source_sha256=SOURCE
    )
    assert provider.descriptor()["helper_sha256"] == report["helper_sha256"]
    assert not hasattr(provider, "probe") and not hasattr(provider, "capture")


@pytest.mark.parametrize(
    "fault,status",
    [
        ("missing", "MISSING_FILES"),
        ("hash", "HASH_DRIFT"),
        ("hardlink", "UNSAFE_OR_UNREADABLE"),
        ("directory", "UNSAFE_OR_UNREADABLE"),
    ],
)
def test_physical_file_faults_produce_valid_held_reports(copied_catalog, fault, status):
    path = copied_catalog / helper.HELPER_RELATIVE_PATH
    if fault == "missing":
        path.unlink()
    elif fault == "hash":
        path.write_bytes(b"incapable changed helper bytes")
    elif fault == "hardlink":
        (path.parent / "incapable-alias.exe").hardlink_to(path)
    else:
        path.unlink()
        path.mkdir()
    report = helper.inspect_camera_helper(
        copied_catalog, source_sha256=SOURCE, mode="physical"
    )
    assert verify(report)["inspection_status"] == status
    assert not report["metadata_eligible"] and register(report) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("catalog_sha256", "f" * 64),
        ("metadata_eligible", 1),
        ("trusted_release", True),
        ("historical_full_build_match", True),
        ("source_sha256", "b" * 64),
        ("allowed_operations", ["inventory", "probe"]),
        ("inspection_provenance", "WORKSPACE_FILE_INSPECTION"),
        ("extra", 0),
    ],
)
def test_pure_verifier_rejects_rehashed_context_and_authority_mutation(field, value):
    report = helper.rehearsal_camera_helper_inspection(source_sha256=SOURCE)
    report[field] = value
    report["inspection_sha256"] = helper._digest(
        {k: v for k, v in report.items() if k != "inspection_sha256"}
    )
    with pytest.raises(helper.CameraHelperInspectionError):
        verify(report)


def test_verifier_rejects_byte_accounting_and_copy_aliases():
    report = helper.rehearsal_camera_helper_inspection(source_sha256=SOURCE)
    owned = verify(report)
    report["files"][0]["bytes"] += 1
    assert owned["files"][0]["bytes"] == 179200
    report["inspection_sha256"] = helper._digest(
        {k: v for k, v in report.items() if k != "inspection_sha256"}
    )
    with pytest.raises(helper.CameraHelperInspectionError):
        verify(report)


@pytest.mark.parametrize(
    "scenario", ["nominal", "missing-mapping", "wrong-device", "duplicate-name"]
)
def test_reviewed_fixture_factory_is_inert_and_reuses_packet_parsers(
    monkeypatch, scenario
):
    report = helper.rehearsal_camera_helper_inspection(source_sha256=SOURCE)
    registration = register(report)

    def forbidden(*args, **kwargs):
        pytest.fail("Rehearsal provider touched files/native/client")

    monkeypatch.setattr(helper, "source_fingerprint", forbidden)
    monkeypatch.setattr(helper, "WindowsCameraWorkerClient", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    provider = helper.create_metadata_provider(
        Path("not-real"),
        registration,
        mode="rehearsal",
        source_sha256=SOURCE,
        scenario=scenario,
    )
    descriptor = provider.descriptor()
    assert descriptor is provider.descriptor()
    packet, inventory = validate_native_packet(
        provider.inventory(), kind="inventory", **descriptor
    )
    candidate = inventory.candidates[0]
    _, identity = validate_native_packet(
        provider.identity(candidate),
        kind="identity",
        expected_endpoint=candidate.symbolic_link,
        **descriptor,
    )
    assert identity.physical_authority is False
    assert packet["provenance"] == "INCAPABLE_FIXTURE"
    assert not hasattr(provider, "capture") and not hasattr(provider, "probe")


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "b" * 64),
        ("reviewer_id", "inspector"),
        ("review_operation_id", "inspect-001"),
        ("capture_allowed", True),
        ("helper_sha256", "f" * 64),
        ("inspection_sha256", "f" * 64),
    ],
)
def test_factory_independently_rejects_forged_immutable_registration(field, value):
    registration = register(
        helper.rehearsal_camera_helper_inspection(source_sha256=SOURCE)
    )
    payload = registration.payload
    payload[field] = value
    forged = ReviewedCameraHelperRegistration(
        helper._bytes(payload), helper._bytes(registration.inspection)
    )
    with pytest.raises(helper.CameraHelperInspectionError):
        helper.create_metadata_provider(
            Path("not-real"), forged, mode="rehearsal", source_sha256=SOURCE
        )


@pytest.mark.parametrize("drift", ["helper", "source"])
def test_physical_factory_is_inert_and_revalidates_before_any_provider(
    isolated_reviewed_catalog, monkeypatch, drift
):
    copied_catalog = isolated_reviewed_catalog
    report = helper.inspect_camera_helper(
        copied_catalog, source_sha256=SOURCE, mode="physical"
    )
    registration = register(report)
    monkeypatch.setattr(
        helper,
        "WindowsCameraWorkerClient",
        lambda *a, **k: pytest.fail("Native client constructed after drift"),
    )
    monkeypatch.setattr(
        helper,
        "source_fingerprint",
        lambda _: SOURCE if drift == "helper" else "b" * 64,
    )
    provider = helper.create_metadata_provider(
        copied_catalog, registration, mode="physical", source_sha256=SOURCE
    )
    assert provider.descriptor()["helper_sha256"] == helper.NATIVE_HELPER_SHA256
    if drift == "helper":
        (copied_catalog / helper.HELPER_RELATIVE_PATH).write_bytes(
            b"changed incapable bytes"
        )
    with pytest.raises(helper.CameraHelperInspectionError) as caught:
        provider.inventory()
    assert caught.value.code == (
        "HELPER_INSPECTION_CHANGED" if drift == "helper" else "HELPER_SOURCE_CHANGED"
    )
    if drift == "helper":
        retained = caught.value.inspection_report
        assert retained["inspection_status"] == "HASH_DRIFT"
        retained["metadata_eligible"] = True
        assert caught.value.inspection_report["metadata_eligible"] is False


def test_physical_factory_rechecks_each_query_with_incapable_client_runner(
    isolated_reviewed_catalog, monkeypatch
):
    from test_wizard_native_camera_metadata import IncapableRunner
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

    copied_catalog = isolated_reviewed_catalog
    report = helper.inspect_camera_helper(
        copied_catalog, source_sha256=SOURCE, mode="physical"
    )
    runner, inspections = IncapableRunner(), []
    actual_inspect = helper.inspect_camera_helper

    def inspect(*args, **kwargs):
        inspections.append(1)
        return actual_inspect(*args, **kwargs)

    monkeypatch.setattr(helper, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(helper, "inspect_camera_helper", inspect)
    monkeypatch.setattr(
        helper,
        "WindowsCameraWorkerClient",
        lambda path, digest: WindowsCameraWorkerClient(path, digest, runner=runner),
    )
    provider = helper.create_metadata_provider(
        copied_catalog, register(report), mode="physical", source_sha256=SOURCE
    )
    assert not inspections and not runner.calls
    _, inventory = validate_native_packet(
        provider.inventory(), kind="inventory", **provider.descriptor()
    )
    provider.identity(inventory.candidates[0])
    assert len(inspections) == 2 and len(runner.calls) == 2


def test_read_budget_fails_held_without_hash_or_client(copied_catalog, monkeypatch):
    monkeypatch.setattr(helper, "MAX_READS", 0)
    report = helper.inspect_camera_helper(
        copied_catalog, source_sha256=SOURCE, mode="physical"
    )
    assert report["inspection_status"] == "UNSAFE_OR_UNREADABLE"
    assert all(row["observed_sha256"] is None for row in report["files"])


@pytest.mark.parametrize(
    "mode,scenario",
    [("physical", "nominal"), ("rehearsal", ""), ("rehearsal", "unknown")],
)
def test_inspection_rejects_unregistered_fixture_controls(mode, scenario):
    with pytest.raises(helper.CameraHelperInspectionError):
        helper.inspect_camera_helper(
            Path("not-real"), source_sha256=SOURCE, mode=mode, scenario=scenario
        )
