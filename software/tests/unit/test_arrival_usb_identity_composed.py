"""Actual Arrival/original NTFS/USB service, explicitly modeled hardware facts.

This test never calls the physical USB executable. Only the native runner seam
is replaced with a refusal after real consumed-scope acknowledgement and fresh
original admission checks. The original store, review codecs, tickets, parent
result validator, completion log, separate export and reopening remain real.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event
import time
import traceback
from types import SimpleNamespace
import uuid

import pytest

from rocell.application import arrival_wizard_service as arrival_module
from rocell.application import physical_camera_identity_service as identity_module
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application import physical_usb_identity_dispatch as dispatch_module
from rocell.application.physical_intake_evidence_service import (
    PhysicalIntakeEvidenceService,
)
from rocell.application.physical_source_qualification_service import (
    PhysicalSourceQualificationService,
)
from rocell.application.physical_static_camera_onboarding_service import (
    PhysicalStaticCameraOnboardingService,
)
from rocell.application.physical_received_camera_service import (
    PhysicalReceivedCameraService,
)
from rocell.application.physical_usb_identity_export import (
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.usb_identity_protocol import canonical

from test_arrival_wizard_service import make_service, _ticket
from test_physical_camera_identity_readback import (
    actual_identity_entry,
    identity_inputs,
    no_devices,
    workspace,
)
from test_physical_camera_identity_service_ntfs import (
    adopt_actual_original,
    execute,
    read_original,
)
from test_physical_camera_session import SOURCE
from test_physical_usb_identity_dispatch_m1 import failure_evidence

WORKSPACE = Path(__file__).parents[3]
# Saved before the autouse no-process fixture. Only the exact fixed, cached DOM
# renderer may use it after every hardware-action/export assertion has passed.
_NODE_RENDER_POPEN = subprocess.Popen
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="actual original NTFS and leases"
)


def _complete(arrival, operation_id):
    # Storage tests must await the same live operation, not start a replacement
    # when a normal 5-second unit-test polling helper expires.
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        operation = arrival.operation(operation_id)
        if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return operation
        Event().wait(0.02)
    pytest.fail(f"same public operation did not finish: {operation_id}")


def _run(arrival, action, values):
    ticket = _ticket(arrival, action, values)
    queued = arrival.execute_action(ticket["ticket_id"])
    operation = _complete(arrival, queued["operation_id"])
    assert operation["status"] == "SUCCEEDED", json.dumps(operation, indent=2)
    return operation, ticket


def _copy_fixed_native(workspace):
    """Copy reviewed fixed files, no executable launch or downloaded content."""
    runtime = registration.usb_identity_runtime_candidate(
        workspace, source_sha256=SOURCE
    )
    names = [row[0] for row in registration.FIXED_SOURCE_PINS]
    names.extend([registration.BUILD_RECORD_PATH, runtime.to_dict()["helper"]["path"]])
    for name in names:
        relative = Path(registration.NATIVE_DIRECTORY) / name
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)


@pytest.fixture
def usb_arrival(workspace, make_service, monkeypatch, request):
    from rocell.application import physical_usb_identity_service as usb_module

    for module in (identity_module, setup_impl, dispatch_module, usb_module):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    session, _, state = actual_identity_entry(
        workspace, monkeypatch, include_configuration_epochs=True
    )
    original = read_original(session, state["header"].header_sha256)
    identity_owner, acquisition = adopt_actual_original(session, original)
    inputs = identity_inputs(
        source=SOURCE, launch=identity_owner.launch_id, return_owners=True
    )
    execute(identity_owner, inputs, identity_module.SUBMIT)
    execute(identity_owner, inputs, identity_module.REVIEW)
    setup = identity_owner.setup
    _copy_fixed_native(workspace)
    with monkeypatch.context() as launch:
        launch.setattr(
            arrival_module,
            "uuid",
            SimpleNamespace(uuid4=lambda: uuid.UUID(setup.launch_id[7:])),
        )
        arrival, diagnostic_runner, source = make_service(mode="physical")
    arrival._physical_camera_setup = setup
    arrival._physical_camera = acquisition
    arrival._camera_identity_records = identity_owner
    arrival._physical_intake_evidence = PhysicalIntakeEvidenceService(setup)
    arrival._source_qualification = PhysicalSourceQualificationService(setup)
    arrival._static_camera_onboarding = PhysicalStaticCameraOnboardingService(setup)
    arrival._received_camera = PhysicalReceivedCameraService(setup)
    arrival._usb_identity = usb_module.PhysicalUsbIdentityService(setup)
    for owner in (
        arrival._physical_intake_evidence,
        arrival._source_qualification,
        arrival._static_camera_onboarding,
        arrival._received_camera,
        arrival._usb_identity,
    ):
        owner.observe_setup()

    usb_perform = arrival._usb_identity.perform

    def retain_failure_trace(*args, **kwargs):
        try:
            return usb_perform(*args, **kwargs)
        except Exception:
            # Actual failure location survives fixture cleanup; all subjects
            # in this test are explicitly modeled, never private unit data.
            traceback.print_exc()
            raise

    monkeypatch.setattr(arrival._usb_identity, "perform", retain_failure_trace)

    calls = []
    worker_mode = request.param

    class RefusedNativeRunner:
        """Test-only model, after actual original-scope consumption; no process."""

        def __init__(self, prepared, *, permit, authorization, application_guard):
            self.prepared, self.permit = prepared, permit
            self.authorization, self.guard = authorization, application_guard

        def run(self, *, cancellation, deadline_ns):
            started, utc = time.monotonic_ns(), time.time_ns()
            assert self.guard() is None and not cancellation.is_set()
            self.authorization.acknowledge(self.permit)
            from rocell.providers.windows import (
                owned_usb_identity_evidence as evidence_module,
            )

            boundaries = (
                evidence_module.BOUNDARIES
                if worker_mode == "known-held"
                else ("PRE_PIN",)
            )
            checks = []
            for boundary in boundaries:
                before = time.monotonic_ns()
                self.authorization.revalidate(self.permit)
                checks.append(
                    dict(
                        boundary=boundary,
                        started_ns=before,
                        finished_ns=time.monotonic_ns(),
                        passed=True,
                    )
                )
            if worker_mode == "known-held":
                from test_physical_camera_usb_readback import (
                    modeled_clean_held_evidence,
                )

                raw = modeled_clean_held_evidence(self.prepared).to_dict()
                # Only device/process observations are modeled. Time bounds and
                # all five consumed-original checks above are actual.
                raw.update(
                    original_deadline_ns=deadline_ns,
                    started_monotonic_ns=started,
                    finished_monotonic_ns=time.monotonic_ns(),
                    started_utc_ns=utc,
                    finished_utc_ns=time.time_ns(),
                    scope_checks=checks,
                )
                evidence = evidence_module.OwnedUsbIdentityRunEvidence(canonical(raw))
            else:
                evidence = failure_evidence(
                    self.prepared,
                    deadline_ns=deadline_ns,
                    checks=checks,
                    started_ns=started,
                    started_utc_ns=utc,
                    process_created=True,
                )
            calls.append((self.permit, evidence))
            return evidence

    monkeypatch.setattr(runner_module, "OwnedUsbIdentityRunner", RefusedNativeRunner)
    monkeypatch.setattr(
        runner_module,
        "_new_owner",
        lambda: pytest.fail("physical process must not start"),
    )
    return SimpleNamespace(
        arrival=arrival,
        owner=arrival._usb_identity,
        setup=setup,
        session=session,
        calls=calls,
        source=source,
        runner=diagnostic_runner,
        module=usb_module,
        workspace=workspace,
        worker_mode=worker_mode,
    )


def _fields(owner, action):
    """Use explicit contract values; reject any newly added unreviewed field."""
    forms = {
        "physical_usb_identity_inspect": dict(
            operator_id="usb-operator", confirm_file_inspection=True
        ),
        "physical_usb_identity_review": dict(
            reviewer_id="usb-reviewer",
            confirm_policy_review=True,
            confirm_runtime_review=True,
            confirm_exact_target=True,
        ),
        "physical_usb_identity_collect": dict(
            confirm_usb_query=True, confirm_no_capture_or_arm=True
        ),
        "physical_usb_identity_export": dict(confirm_metadata_export=True),
    }
    known = forms[action]
    fields = owner.fields(action)
    assert {field["name"] for field in fields} == set(known), fields
    return known


@pytest.mark.parametrize("usb_arrival", ["unaccounted", "known-held"], indirect=True)
def test_public_original_usb_inspect_review_query_failure_and_complete_export(
    usb_arrival,
):
    case = usb_arrival
    arrival, owner = case.arrival, case.owner
    prefix = deepcopy(case.setup.original_source_workflow())
    assert not case.calls
    for action in (case.module.INSPECT, case.module.REVIEW):
        before = len(case.calls)
        _run(arrival, action, _fields(owner, action))
        assert len(case.calls) == before
        assert owner.view()["publication"]["status"] == "CURRENT"
    operation, ticket = _run(
        arrival, case.module.COLLECT, _fields(owner, case.module.COLLECT)
    )
    assert len(case.calls) == 1
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == operation["operation_id"]
    )
    assert len(case.calls) == 1
    uncertain = case.worker_mode == "unaccounted"
    assert operation["result"]["device_open_count"] == (None if uncertain else 0)
    assert operation["result"]["counter_coverage"] == (
        "NOT_REPORTED" if uncertain else "NATIVE_RECEIPT"
    )
    assert operation["result"]["physical_authority"] is False
    verified = case.session._store._runtime.verify(
        case.session.descriptor()["session_id"]
    )
    assert verified.quarantined is uncertain
    assert all(row["state"] == "PENDING" for row in case.session.view()["stages"][4:])
    diagnostics = owner.retained_diagnostics()
    assert diagnostics is not None
    saved = diagnostics["attempt"]["dispatch"]["original"]
    assert canonical(saved["evidence"]) == case.calls[0][1].payload
    assert saved["result"]["state"] == (
        "SEALED_UNCERTAIN" if uncertain else "SEALED_KNOWN"
    )
    assert owner.blocked_reason(case.module.COLLECT) is not None
    with pytest.raises(WizardError):
        _ticket(arrival, case.module.COLLECT, _fields(owner, case.module.COLLECT))
    export, _ = _run(arrival, case.module.EXPORT, _fields(owner, case.module.EXPORT))
    receipt = owner.export_metadata()
    assert receipt["valid"] and verify_export(Path(receipt["path"]))["valid"]
    assert Path(receipt["path"]).parent == arrival.export_directory
    report = json.loads((Path(receipt["path"]) / "report.json").read_bytes())[
        "snapshot"
    ]
    parts = {
        row["attachment"]: (Path(receipt["path"]) / row["attachment"]).read_bytes()
        for row in report["parts"]
    }
    restored = restore_usb_identity_diagnostics(report, parts)
    assert (
        canonical(restored["attempt"]["dispatch"]["original"]["evidence"])
        == case.calls[0][1].payload
    )
    assert report["original_bytes_preserved"]
    assert not case.runner.calls
    assert len(case.calls) == 1
    current = case.setup.session.retained_source_workflow()
    assert current["camera_identity_cycles"] == prefix["camera_identity_cycles"]
    baseline = current["usb_baseline"]
    assert (baseline["execution"] is None) is uncertain
    assert (baseline["outcome"] is None) is uncertain
    from rocell.ui.terminal import _UsbIdentityDisplay
    from test_wizard_workspace_source_ui import render_snapshot

    snapshot = arrival.view()
    assert (
        _UsbIdentityDisplay.validate(snapshot["usb_identity"], snapshot)
        == snapshot["usb_identity"]
    )
    from test_arrival_wizard_device_selection_ui import _HARNESS

    node = shutil.which("node")
    assert node is not None, "Node is required for composed renderer acceptance"

    def render_process(*args, **kwargs):
        assert args == ([node, "-e", _HARNESS],), "Only the fixed DOM renderer may run"
        assert kwargs.get("shell", False) is False
        return _NODE_RENDER_POPEN(*args, **kwargs)

    # Do not lift the general process ban: it correctly protects all earlier
    # physical paths. This exact Node script evaluates the UI with a cached
    # snapshot and mocked fetch; it cannot call the real wizard or its workers.
    with pytest.MonkeyPatch.context() as renderer:
        renderer.setattr(subprocess, "Popen", render_process)
        browser, terminal = render_snapshot(snapshot)
    assert "USB_IDENTITY_NOT_VERIFIED" not in browser
    assert "USB_IDENTITY_NOT_VERIFIED" not in terminal
