"""Successor file checks/registration only; no native executable is launched."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application import wizard_camera_helper_inspection as helper
from rocell.application import wizard_camera_metadata_successor_catalog as successor
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export
from test_wizard_camera_helper_inspection import SOURCE, WORKSPACE, register, verify
from test_wizard_device_selection_integration import action


@pytest.fixture(autouse=True)
def no_native_process(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Successor registration test attempted a process/device")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture
def copied_successor(tmp_path):
    for row in helper.camera_helper_catalog(successor.CATALOG_ID)["files"]:
        target = tmp_path / row["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / row["relative_path"], target)
    return tmp_path


def current(root):
    return helper.inspect_current_camera_helper(
        root, source_sha256=SOURCE, mode="physical"
    )


def test_v1_is_unchanged_and_successor_is_separate_fixed_catalog():
    old = helper.camera_helper_catalog()
    new = helper.camera_helper_catalog(successor.CATALOG_ID)
    assert (
        old["catalog_sha256"]
        == "e6f9e5fb276470cbc4cf6f6dd8176496fd0b63059a663c8667ea5da645377072"
    )
    assert (
        old["native_helper_sha256"]
        == "a0410e866563738bbe0c60c2a763adf094deceba10ae9c81f4becba80a06c797"
    )
    assert new["catalog_id"] != old["catalog_id"]
    assert new["files"][0]["relative_path"] != old["files"][0]["relative_path"]
    assert new["allowed_operations"] == ["inventory", "identity"]
    assert new["trusted_release"] is new["physical_authority"] is False
    assert (
        len(new["files"]) == len({row["relative_path"] for row in new["files"]}) == 17
    )
    new["files"][0]["expected_sha256"] = "f" * 64
    assert (
        helper.camera_helper_catalog(successor.CATALOG_ID)["files"][0][
            "expected_sha256"
        ]
        == successor.NATIVE_HELPER_SHA256
    )


def test_successor_matches_actual_build_inputs_but_is_not_capture_authority(
    copied_successor,
):
    report = current(copied_successor)
    assert verify(report) == report
    assert report["metadata_eligible"] is True
    assert all(row["status"] == "MATCHED" for row in report["files"])
    assert report["historical_full_build_match"] is False
    assert report["camera_activation_allowed"] is False
    record = json.loads(
        (
            copied_successor
            / successor.NATIVE_ROOT
            / "metadata_only_build_record_20260912.json"
        ).read_text()
    )
    assert record["entry_guard"] == "ROCELL_METADATA_ONLY"
    assert record["verification"]["ctest_passed"] == 4
    assert record["verification"]["active_command_denials"] == 9
    pins = {row["relative_path"]: row["observed_sha256"] for row in report["files"]}
    for relative, digest in record["source_sha256"].items():
        resolved = (copied_successor / successor.NATIVE_ROOT / relative).resolve()
        assert pins[resolved.relative_to(copied_successor).as_posix()] == digest
    artifact = register(report)
    assert artifact is not None
    provider = helper.create_metadata_provider(
        copied_successor, artifact, mode="physical", source_sha256=SOURCE
    )
    assert provider.descriptor()["helper_sha256"] == successor.NATIVE_HELPER_SHA256
    assert not hasattr(provider, "probe") and not hasattr(provider, "capture")


@pytest.mark.parametrize(
    "fault", ["missing", "binary_drift", "client_drift", "build_record_drift"]
)
def test_successor_faults_cannot_fall_back_or_register(copied_successor, fault):
    paths = {
        "missing": successor.HELPER_RELATIVE_PATH,
        "binary_drift": successor.HELPER_RELATIVE_PATH,
        "client_drift": "software/src/rocell/providers/windows/camera_worker_client.py",
        "build_record_drift": successor.NATIVE_ROOT
        + "metadata_only_build_record_20260912.json",
    }
    target = copied_successor / paths[fault]
    if fault == "missing":
        target.unlink()
    else:
        target.write_bytes(b"INCAPABLE MODIFIED TEST FILE")
    # Even with the original executable present, successor failure stays held.
    old = copied_successor / helper.HELPER_RELATIVE_PATH
    old.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WORKSPACE / helper.HELPER_RELATIVE_PATH, old)
    report = current(copied_successor)
    assert verify(report)["metadata_eligible"] is False
    assert report["catalog_id"] == successor.CATALOG_ID
    assert register(report) is None


@pytest.mark.parametrize(
    "change", ["unknown_catalog", "mixed_catalog", "mixed_file", "authority"]
)
def test_rehashed_forged_successor_report_is_rejected(change):
    report = helper.rehearsal_camera_helper_inspection(
        source_sha256=SOURCE, catalog_id=successor.CATALOG_ID
    )
    if change == "unknown_catalog":
        report["catalog_id"] = "operator-provided-path-or-catalog"
    elif change == "mixed_catalog":
        report["catalog_id"] = helper.CATALOG_ID
    elif change == "mixed_file":
        old = helper.rehearsal_camera_helper_inspection(source_sha256=SOURCE)
        report["files"][0] = deepcopy(old["files"][0])
    else:
        report["camera_activation_allowed"] = True
    report.pop("inspection_sha256")
    report["inspection_sha256"] = helper._digest(report)
    with pytest.raises(helper.CameraHelperInspectionError):
        verify(report)


def test_provider_uses_successor_path_and_revalidates_before_each_query(
    copied_successor, monkeypatch
):
    artifact = register(current(copied_successor))
    provider = helper.create_metadata_provider(
        copied_successor, artifact, mode="physical", source_sha256=SOURCE
    )
    calls = []
    monkeypatch.setattr(helper, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(
        helper,
        "WindowsCameraWorkerClient",
        lambda path, digest: calls.append((path, digest)),
    )
    monkeypatch.setattr(
        helper,
        "NativeCameraMetadataProvider",
        lambda _: SimpleNamespace(inventory=lambda: {"incapable": True}),
    )
    assert provider.inventory() == {"incapable": True}
    assert calls == [
        (
            copied_successor / successor.HELPER_RELATIVE_PATH,
            successor.NATIVE_HELPER_SHA256,
        )
    ]
    (copied_successor / successor.HELPER_RELATIVE_PATH).write_bytes(
        b"INCAPABLE CHANGED FILE"
    )
    with pytest.raises(helper.CameraHelperInspectionError, match="changed"):
        provider.inventory()
    assert len(calls) == 1


def test_default_physical_wizard_inspects_reviews_and_exports_successor_without_lookup(
    tmp_path,
):
    service = ArrivalWizardService(
        WORKSPACE,
        mode="physical",
        log_directory=tmp_path / "logs",
        export_directory=tmp_path / "exports",
    )
    try:
        before = service.view()
        assert before["camera_helper_registration"]["status"] == "NO_INSPECTION"
        assert service._native_camera_provider is None
        result = action(
            service,
            "camera_helper_inspect",
            operator_id="test-inspector",
            metadata_only=True,
        )
        assert result["status"] == "SUCCEEDED", result
        inspected = service.view()["camera_helper_registration"]
        assert inspected["inspection"]["catalog_id"] == successor.CATALOG_ID
        assert (
            inspected["inspection"]["inspection_status"] == "MATCHED_METADATA_CATALOG"
        )
        assert inspected["review"] is None
        result = action(
            service,
            "camera_helper_review",
            reviewer_id="test-reviewer",
            metadata_only=True,
        )
        assert result["status"] == "SUCCEEDED", result
        registered = service.view()["camera_helper_registration"]
        assert registered["status"] == "METADATA_HELPER_REGISTERED"
        assert not registered["probe_allowed"] and not registered["capture_allowed"]
        assert service.view()["stages"] == before["stages"]
        assert service.view()["camera"]["status"] == "NOT_CONNECTED"
        exported = action(service, "export_logs")
        assert exported["status"] == "SUCCEEDED", exported
        assert verify_export(Path(exported["result"]["receipt"]["path"]))["valid"]
    finally:
        service.shutdown()
