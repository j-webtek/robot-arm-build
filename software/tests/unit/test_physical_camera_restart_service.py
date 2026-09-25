"""Arrival restart/publication with modeled storage; no M1 or device execution.

The registry descriptor comes from explicitly modeled temporary metadata. The
prerequisite document is generated from the four actual fixed build sources.
Selected scopes and session refresh/readback are injected here; the separate
public smoke owns real original-store NTFS coverage.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import threading
import time

import pytest

from rocell.application import physical_camera_reopen_registry as registry_module
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_setup_service import PhysicalCameraSetupService
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.application.physical_camera_prerequisites import (
    collect_physical_camera_prerequisites,
)
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_protocol import canonical
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_physical_camera_prerequisites import workspace, SOURCE
from test_physical_camera_reopen_registry import metadata_store, ORIGIN


@pytest.fixture(autouse=True)
def no_runtime_or_devices(monkeypatch):
    import platform
    import subprocess

    # Avoid Python 3.10's first-call `ver` shell fallback in pure UI fixtures.
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "release", lambda: "10")

    def denied(*args, **kwargs):
        pytest.fail("modeled restart service must not open M1, processes or devices")

    monkeypatch.setattr(subprocess, "Popen", denied)
    for method in ("initialize", "open"):
        monkeypatch.setattr(PhysicalOnboardingM1Runtime, method, denied)
    monkeypatch.setattr(PhysicalCameraSession, "initialize", denied)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, denied)


@pytest.fixture
def modeled(make_service, workspace, monkeypatch):
    service, runner, source = make_service(mode="physical")
    acquisition = PhysicalCameraAcquisitionService(
        workspace, launch_id=service.session_id, source_sha256=SOURCE, mode="physical"
    )
    setup = PhysicalCameraSetupService(acquisition)
    service._physical_camera, service._physical_camera_setup = acquisition, setup
    registry = setup._registry
    metadata_store(workspace)
    monkeypatch.setattr(registry_module, "source_fingerprint", lambda _: SOURCE)
    # Real strict metadata codec/descriptor; no volume qualification or session.
    registry.discover(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 30_000_000_000
    )
    discovered, descriptors = registry.view(), dict(registry._descriptors)
    choice = next(iter(descriptors))
    descriptor = descriptors[choice]
    registry._cached, registry._descriptors = registry._empty("NOT_DISCOVERED"), {}
    artifact = collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=descriptor.session_id,
        launch_session_id=ORIGIN,
        cancellation=threading.Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )
    reference = EvidenceReference(
        "evidence-" + "d" * 64,
        STAGE_ORDER[0],
        "d" * 64,
        "e" * 64,
        artifact.evidence_sha256,
        len(artifact.payload),
    )
    retained = {
        "document": artifact.to_dict(),
        "evidence_sha256": artifact.evidence_sha256,
        "retention": "M1_FULL_BYTES_READ_BACK",
        "reference": reference.to_dict(),
    }
    calls = {
        "discover": 0,
        "selected": [],
        "revalidate": [],
        "refresh": [],
        "read": [],
        "fault": None,
    }

    def discovery(**kwargs):
        calls["discover"] += 1
        assert not kwargs["cancellation"].is_set()
        registry._cached, registry._descriptors = deepcopy(discovered), dict(
            descriptors
        )
        return registry.view()

    @contextmanager
    def selected(token, expected_hash, **kwargs):
        calls["selected"].append((token, expected_hash))
        assert expected_hash == discovered["discovery_sha256"]
        original = registry.descriptor(token)
        try:
            if calls["fault"] == "before-scope":
                raise WizardError(
                    "MODELED_SELECTED_PRECHECK", "Original metadata check failed."
                )
            yield original
            if calls["fault"] == "after-scope":
                raise WizardError(
                    "MODELED_SELECTED_POSTCHECK",
                    "Original metadata changed after readback.",
                )
        except BaseException:
            registry.invalidate("METADATA_CHANGED")
            raise

    @contextmanager
    def revalidate(original, expected_hash, **kwargs):
        calls["revalidate"].append((original.payload, expected_hash))
        checked = registry._original_descriptor(original, expected_hash)
        assert checked.payload == descriptor.payload
        assert not kwargs["cancellation"].is_set()
        yield checked

    def refresh(owner, **kwargs):
        calls["refresh"].append(owner.descriptor())
        bound = owner.descriptor()
        assert (
            bound["launch_id"] == ORIGIN
            and bound["session_id"] == descriptor.session_id
        )
        owner._cached.update(
            status="REFRESHED_STORAGE_ONLY",
            operation="REFRESH",
            error=None,
            verification={
                "effects_allowed_by_m1_storage": True,
                "challenge_sha256": "c" * 64,
                "session": {
                    "session_id": descriptor.session_id,
                    "header_sha256": descriptor.header_sha256,
                },
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
        return owner.view()

    def readback(owner, **kwargs):
        calls["read"].append(kwargs)
        assert kwargs["expected_header_sha256"] == descriptor.header_sha256
        assert time.monotonic_ns() < kwargs["deadline_ns"]
        owner._retained_prerequisite_record = canonical(retained)
        if calls["fault"] == "readback-late":
            owner._cached.update(status="HELD", verification=None, stages=None)
            raise WizardError(
                "MODELED_LATE_READBACK", "Read bytes retained before a late failure."
            )
        return {
            "schema": "rocell.physical_camera_source_workflow_readback.v1",
            "binding": owner.descriptor(),
            "session_header_sha256": descriptor.header_sha256,
            "session_head_sha256": "e" * 64,
            "evidence_inventory_sha256": "f" * 64,
            "stage": "workspace_sources",
            "state": "WAITING_OPERATOR",
            "prerequisites": deepcopy(retained),
            "receipt": None,
            "assessment": None,
            "review": None,
            "physical_authority": False,
            "device_io_performed": False,
        }

    monkeypatch.setattr(registry, "discover", discovery)
    monkeypatch.setattr(registry, "selected", selected)
    monkeypatch.setattr(registry, "revalidate_original", revalidate)
    monkeypatch.setattr(PhysicalCameraSession, "refresh", refresh)
    monkeypatch.setattr(
        PhysicalCameraSession, "read_original_source_workflow", readback
    )
    return service, setup, source, calls, choice, descriptor, retained, runner


def discover(model):
    service, setup, _, calls, choice, *_ = model
    outcome = _run(service, "physical_camera_discover")
    assert outcome["status"] == "SUCCEEDED", outcome
    assert setup.reopen_choices()[0]["value"] == choice
    assert calls["discover"] == 1
    return outcome


def reopen(model):
    return _run(model[0], "physical_camera_reopen", {"choice_id": model[4]})


def test_discovery_choices_are_withheld_until_successful_completion_log(
    modeled, monkeypatch
):
    service, setup, _, calls, choice, *_ = modeled
    original = service._append_event
    observed = []

    def append(kind, value):
        if kind == "ACTION_FINISHED":
            observed.append(kind)
            assert setup._registry.choices()[0]["value"] == choice
            assert setup.reopen_choices() == []
            assert (
                service.view()["physical_camera_setup"]["reopening"]["status"]
                == "NOT_DISCOVERED"
            )
        return original(kind, value)

    monkeypatch.setattr(service, "_append_event", append)
    discover(modeled)
    assert observed == ["ACTION_FINISHED"]
    assert setup.view()["publication"]["status"] == "CURRENT"
    assert setup.view()["reopening"]["status"] == "DISCOVERED"
    assert not calls["selected"] and not calls["refresh"]


@pytest.mark.parametrize(
    "fault", ["intent-log", "completion-log", "redaction", "source", "stop"]
)
def test_failed_discovery_publication_never_exposes_choices(
    modeled, monkeypatch, fault
):
    service, setup, source, calls, *_ = modeled
    if fault.endswith("log"):
        event = "ACTION_EXECUTED" if fault == "intent-log" else "ACTION_FINISHED"
        original = service._append_event
        monkeypatch.setattr(
            service,
            "_append_event",
            lambda kind, value: False if kind == event else original(kind, value),
        )
    else:
        original_perform = setup.perform

        def late(*args, **kwargs):
            result = original_perform(*args, **kwargs)
            if fault == "redaction":
                result["steps"][0]["report"]["note"] = "token=private-fixture"
            elif fault == "source":
                source["hash"] = "f" * 64
            else:
                kwargs["cancellation"].set()
            return result

        monkeypatch.setattr(setup, "perform", late)
    result = _run(service, "physical_camera_discover")
    assert result["status"] == ("SUCCEEDED" if fault == "stop" else "FAILED"), result
    assert setup.reopen_choices() == []
    assert (
        service.view()["physical_camera_setup"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert calls["discover"] == int(fault != "intent-log")
    assert not calls["selected"] and not calls["refresh"]
    if fault == "redaction":
        assert result["result"]["code"] == "BOUND_CAMERA_SETUP_REDACTED"
        assert "private-fixture" not in str(result)


@pytest.mark.parametrize("change", ["discovery", "session", "unknown-choice"])
def test_choice_and_exact_context_change_cannot_open_a_store(modeled, change):
    service, setup, _, calls, choice, *_ = modeled
    discover(modeled)
    if change == "unknown-choice":
        with pytest.raises(WizardError):
            _ticket(
                service, "physical_camera_reopen", {"choice_id": "C:\\arbitrary\\path"}
            )
    else:
        ticket = _ticket(service, "physical_camera_reopen", {"choice_id": choice})
        if change == "discovery":
            setup._registry._cached["discovery_sha256"] = "f" * 64
        else:
            setup.session._cached["partial_store_possible"] = True
        outcome = _complete(
            service, service.execute_action(ticket["ticket_id"])["operation_id"]
        )
        assert outcome["status"] == "FAILED"
        assert outcome["result"]["code"] == "CAMERA_SETUP_CONTEXT_CHANGED"
    assert not calls["selected"] and not calls["refresh"]


@pytest.mark.parametrize("fault", ["before-scope", "after-scope", "readback-late"])
def test_failed_open_then_explicit_refresh_revalidates_only_frozen_original(
    modeled, fault
):
    service, setup, _, calls, _, descriptor, retained, runner = modeled
    discover(modeled)
    new_launch_directory = setup.session.descriptor()["directory"]
    calls["fault"] = fault
    failed = reopen(modeled)
    assert failed["status"] == "FAILED", failed
    assert setup._registry.choices() == []  # First token was invalidated.
    assert setup._original_descriptor.payload == descriptor.payload
    assert len(calls["selected"]) == 1 and calls["revalidate"] == []
    assert setup.planning_blocked_reason() is not None
    for action in (
        "physical_camera_initialize",
        "physical_camera_discover",
        "physical_camera_reopen",
    ):
        with pytest.raises(WizardError):
            _ticket(
                service,
                action,
                {"choice_id": "other"} if action.endswith("reopen") else {},
            )
    for _ in range(3):
        service.view()
    assert len(calls["selected"]) == 1 and calls["revalidate"] == []
    if fault == "readback-late":
        assert setup._retained is None
        assert failed["result"]["retained_camera_setup"]["prerequisites"] == retained
    calls["fault"] = None
    preview = _ticket(service, "physical_camera_refresh")
    assert str(descriptor.directory) in " ".join(preview["effects"])
    assert new_launch_directory not in " ".join(preview["effects"])
    completed = _run(service, "physical_camera_refresh")
    assert completed["status"] == "SUCCEEDED", completed
    assert len(calls["selected"]) == 1
    assert calls["revalidate"] == [(descriptor.payload, descriptor.descriptor_sha256)]
    assert setup.session.descriptor()["directory"] == str(descriptor.directory)
    assert setup.session.descriptor()["directory"] != new_launch_directory
    assert service._physical_camera.directory == descriptor.directory
    assert service._physical_camera.cell_id == descriptor.cell_id
    assert service._physical_camera.session_id == descriptor.session_id
    assert setup.view()["requirements_provenance"] == "REOPENED_ORIGINAL_CONTEXT"
    assert setup.planning_blocked_reason() is None
    planned = service._physical_camera.preview_plan("probe", service._native_camera)
    assert planned["assigned_parent_directory"] == str(descriptor.directory)
    assert planned["camera_store_origin_launch_id"] == ORIGIN
    assert planned["native_campaign_plan"] is None and planned["admitted"] is False
    assert not runner.calls and not Path(new_launch_directory).exists()


def test_refresh_does_not_reinterpret_a_changed_independent_descriptor_hash(modeled):
    service, setup, _, calls, *_ = modeled
    discover(modeled)
    calls["fault"] = "before-scope"
    assert reopen(modeled)["status"] == "FAILED"
    setup._selected_original["descriptor_sha256"] = "f" * 64
    calls["fault"] = None
    result = _run(service, "physical_camera_refresh")
    assert result["status"] == "FAILED"
    assert len(calls["selected"]) == len(calls["revalidate"]) == 1
    assert not calls["refresh"] and setup.planning_blocked_reason() is not None


def test_successful_open_publishes_same_original_without_importing_connection(modeled):
    service, setup, _, calls, _, descriptor, retained, runner = modeled
    discover(modeled)
    outcome = reopen(modeled)
    assert outcome["status"] == "SUCCEEDED", outcome
    assert setup.view()["origin_launch_id"] == ORIGIN
    assert setup.view()["launch_session_id"] == service.session_id
    assert setup.view()["prerequisites"]["metadata_selection"] is None
    assert setup.view()["prerequisites"]["source_preflight"] is None
    assert setup.view()["prerequisites"]["canonical_stage_pass"] is False
    assert (
        outcome["result"]["steps"][0]["report"]["prerequisite_document"]
        == retained["document"]
    )
    assert service._physical_camera.directory == descriptor.directory
    assert service.view()["camera"]["status"] == "NOT_CONNECTED"
    assert service.view()["arm"]["status"] == "NOT_CONNECTED"
    assert len(calls["selected"]) == len(calls["refresh"]) == len(calls["read"]) == 1
    assert not runner.calls
