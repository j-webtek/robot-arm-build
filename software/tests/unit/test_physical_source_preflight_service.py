"""Actual file/M1/public-service integration; no camera, serial or process opens."""

from pathlib import Path
import os
import shutil
import threading
import time

import pytest

from rocell.application import physical_source_preflight_service as module
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_source_preflight import SOURCE_PREFLIGHT_SCOPE
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from test_incapable_native_admission_campaign import _copy_fixed_source_closure

ROOT = Path(__file__).resolve().parents[3]
LAUNCH = "wizard-" + "1" * 32


def test_constructor_view_and_report_are_inert_and_copies(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("inert view performed I/O")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(module, "source_fingerprint", forbidden)
        service = module.PhysicalSourcePreflightService(
            tmp_path, launch_id=LAUNCH, source_sha256="a" * 64
        )
        view = service.view()
        view["status"] = "FORGED"
        assert service.view()["status"] == "NOT_STARTED"
        assert service.retained_report() is None
        assert service.view()["physical_authority"] is False
        assert service.view()["power_state"] == "UNKNOWN"


@pytest.mark.skipif(os.name != "nt", reason="Windows M1 source preflight only")
@pytest.mark.parametrize("when", ["before", "first-progress"])
def test_known_cancellation_never_starts_storage(tmp_path, monkeypatch, when):
    service = module.PhysicalSourcePreflightService(
        tmp_path, launch_id=LAUNCH, source_sha256="a" * 64
    )
    monkeypatch.setattr(service, "_current_source", lambda: None)
    # Registration is real fixed-file preparation; storage remains entirely absent.
    registration = module.source_preflight_registration(ROOT)
    monkeypatch.setattr(module, "source_preflight_registration", lambda _: registration)
    monkeypatch.setattr(
        module.PhysicalOnboardingM1Runtime,
        "initialize",
        lambda *a, **kw: pytest.fail("cancelled run initialized storage"),
    )
    cancel = threading.Event()
    if when == "before":
        cancel.set()
    with pytest.raises(WizardError, match="stopped"):
        service.perform(
            "operator", cancellation=cancel, progress=lambda _: cancel.set()
        )
    assert service.view()["status"] == "HELD"
    assert not service.directory.exists()
    assert service.blocked_reason()
    assert service.retained_report() is None


def _workspace(target):
    source = _copy_fixed_source_closure(target)
    for name in SOURCE_PREFLIGHT_SCOPE:
        destination = target / name
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
    (target / "software/runs").mkdir()
    assert source_fingerprint(target) == source
    return source


def _action(service, name, values=None):
    ticket = service.prepare_action(name, values or {}, service.view()["revision"])
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return ticket, operation
        time.sleep(0.05)
    pytest.fail("finite public action failed to finish")


@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="actual Windows qualified M1")
def test_actual_source_to_qualified_m1_public_service_and_export(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = _workspace(workspace)

    # Neither the generic diagnostic runner nor any physical provider is needed.
    class ForbiddenRunner:
        def run(self, *a, **kw):
            pytest.fail("file-only service dispatched a generic child")

    service = ArrivalWizardService(
        workspace,
        mode="physical",
        runner=ForbiddenRunner(),
        log_directory=tmp_path / "logs",
        export_directory=tmp_path / "exports",
    )
    try:
        initial = service.view()
        assert initial["source_binding_sha256"] == source
        assert (
            initial["camera"]["status"] == initial["arm"]["status"] == "NOT_CONNECTED"
        )
        assert not Path(initial["physical_source_preflight"]["directory"]).exists()
        ticket, operation = _action(
            service, "physical_source_preflight", {"operator_id": "actual-file-test"}
        )
        assert operation["status"] == "SUCCEEDED", operation
        result = operation["result"]["steps"][0]["report"]
        assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
        assert result["retained_source_report"]["outcome"] == "FILE_CHECKS_COHERENT"
        assert len(result["retained_source_report"]["files"]) == len(
            SOURCE_PREFLIGHT_SCOPE
        )
        view = service.view()
        current = view["physical_source_preflight"]
        assert current["status"] == "FILE_CHECKS_COHERENT"
        assert current["source_observation_current"] is True
        assert current["attempt"]["state"] == "SEALED_KNOWN"
        assert current["canonical_stage_state"] == "WAITING_OPERATOR"
        assert current["canonical_stage_pass"] is False
        assert all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"])
        assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
        assert (
            service.execute_action(ticket["ticket_id"])["operation_id"]
            == operation["operation_id"]
        )
        with pytest.raises(WizardError, match="already attempted"):
            service.prepare_action("physical_source_preflight", {}, view["revision"])
        _, exported = _action(service, "export_logs")
        assert exported["status"] == "SUCCEEDED", exported
        item = service.view()["exports"]["items"][-1]
        verified = verify_export(Path(item["path"]))
        assert verified
        # Full source observations accompany the log without copying live M1 ledgers.
        files = list(Path(item["path"]).glob("attachment-*.json"))
        assert any(
            result["retained_report_sha256"] in path.read_text() for path in files
        )
        assert source_fingerprint(workspace) == source
    finally:
        service.shutdown()


@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="actual Windows qualified M1")
def test_late_source_failure_retains_full_read_back_report(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = _workspace(workspace)
    service = module.PhysicalSourcePreflightService(
        workspace, launch_id=LAUNCH, source_sha256=source
    )
    original = service._current_source

    def late_failure():
        if service.retained_report() is not None:
            raise WizardError(
                "PREFLIGHT_SOURCE_CHANGED",
                "Injected late source drift after actual read-back",
            )
        original()

    monkeypatch.setattr(service, "_current_source", late_failure)
    with pytest.raises(WizardError, match="late source drift"):
        service.perform(
            "operator", cancellation=threading.Event(), progress=lambda _: None
        )
    assert service.view()["status"] == "HELD"
    assert service.view()["attempt"]["state"] == "SEALED_KNOWN"
    retained = service.retained_report()
    assert retained["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert retained["retained_source_report"]["outcome"] == "FILE_CHECKS_COHERENT"
    retained["retention"] = "CHANGED"
    assert service.retained_report()["retention"] == "M1_FULL_BYTES_READ_BACK"
