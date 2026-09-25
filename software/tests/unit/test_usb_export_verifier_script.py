"""Developer verifier: real copied exports, explicitly modeled cached subjects."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from test_physical_usb_identity_export import diagnostics, exported
from test_usb_reboot_export import reboot_cache


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_usb_identity_export.py"
SPEC = importlib.util.spec_from_file_location("usb_export_verifier_script", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_process_or_original_store(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Read-only diagnostic verification must not start a process/store")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "__init__", denied)


def make_export(tmp_path, factory=diagnostics):
    return Path(exported(factory(), tmp_path / "exports")["path"])


@pytest.mark.parametrize("factory,version", [(diagnostics, 1), (reboot_cache, 6)])
def test_actual_copy_reconstructs_without_mutation_or_authority(
    tmp_path, factory, version
):
    directory = make_export(tmp_path, factory)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    report = m.verify(directory)
    assert report["valid"] and report["export_schema"].endswith(f".v{version}")
    assert report["original_bytes_preserved"] is True
    assert report["attachment_bytes"] > 0
    assert all(
        report[key] is False
        for key in (
            "physical_authority",
            "hardware_qualified",
            "original_store_authenticated",
            "original_store_reopened",
        )
    )
    assert (
        m.verify(
            directory, expected_original_sha256=report["original_diagnostics_sha256"]
        )
        == report
    )
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_redacted_copy_is_not_presented_as_original_reconstruction(tmp_path):
    value = diagnostics()
    value["original_context"]["password"] = "MODELED-PRIVATE-CREDENTIAL"
    directory = Path(exported(value, tmp_path / "exports")["path"])
    report = m.verify(directory)
    assert report["valid"] and report["credential_redaction_applied"]
    assert report["original_bytes_preserved"] is False
    assert report["reconstruction_status"] == "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
    assert "MODELED-PRIVATE-CREDENTIAL" not in json.dumps(report)


def test_independently_supplied_wrong_original_hash_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        m.verify(make_export(tmp_path), expected_original_sha256="f" * 64)


@pytest.mark.parametrize("corruption", ["missing", "changed", "extra", "hardlink"])
def test_manifest_file_failures_are_not_repaired(tmp_path, corruption):
    directory = make_export(tmp_path)
    target = directory / "report.json"
    if corruption == "missing":
        target.unlink()
    elif corruption == "changed":
        target.write_bytes(target.read_bytes() + b" ")
    elif corruption == "extra":
        (directory / "unmanifested.txt").write_bytes(b"MODELED")
    else:
        os.link(target, tmp_path / "MODELED-hardlink.json")
    with pytest.raises(m.UsbExportVerificationError, match="MANIFEST"):
        m.verify(directory)


def test_read_after_initial_manifest_check_is_independently_hashed(
    tmp_path, monkeypatch
):
    directory = make_export(tmp_path)
    original_read = m._read
    monkeypatch.setattr(
        m, "_read", lambda path, limit: original_read(path, limit) + b" "
    )
    with pytest.raises(m.UsbExportVerificationError, match="CHANGED_DURING_READ"):
        m.verify(directory)


def test_manifest_change_after_reconstruction_is_rejected(tmp_path, monkeypatch):
    directory = make_export(tmp_path)
    original_verify = m.verify_export
    calls = []

    def changed(path):
        calls.append(path)
        result = deepcopy(original_verify(path))
        if len(calls) == 2:
            result["manifest_sha256"] = "f" * 64
        return result

    monkeypatch.setattr(m, "verify_export", changed)
    with pytest.raises(
        m.UsbExportVerificationError, match="CHANGED_DURING_VERIFICATION"
    ):
        m.verify(directory)
    assert len(calls) == 2


def test_cli_reports_success_or_failure_without_raw_private_metadata(tmp_path, capsys):
    directory = make_export(tmp_path, reboot_cache)
    assert m.main([str(directory)]) == 0
    success = json.loads(capsys.readouterr().out)
    assert success["valid"] and not success["physical_authority"]
    assert "MODELED_REBOOT" not in json.dumps(success)
    assert m.main([str(directory), "--expected-original-sha256", "wrong"]) == 1
    assert json.loads(capsys.readouterr().out) == dict(
        valid=False, status="USB_DIAGNOSTIC_VERIFICATION_FAILED"
    )


def test_missing_and_relative_paths_fail_without_creating_any_directory(
    tmp_path, capsys
):
    missing = tmp_path / "missing"
    assert m.main([str(missing)]) == 1
    assert not missing.exists()
    assert m.main(["not-an-absolute-export"]) == 1
    assert len(capsys.readouterr().out.splitlines()) == 2
