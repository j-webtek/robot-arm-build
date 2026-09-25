"""Original-probe service -> real M1/core/dispatch, with incapable native owner.

Original semantic authentication and substantive facts are MODELED in this lane.
Their real complete composition is tested separately. The real storage journal
here contains labeled synthetic predecessors; it is not hardware qualification.
"""

from threading import Event
from types import SimpleNamespace
import time

import pytest

from rocell.application import camera_probe_admission as admission_impl
from rocell.application import camera_probe_original_scope as original_impl
from rocell.application import physical_camera_session as session_impl
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    PhysicalCameraAdmissionFacts,
    physical_camera_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_activation_service_handoff import service_enrollment, LAUNCH, SOURCE
from test_camera_activation_dispatch_handoff import install_owner
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner
from test_camera_mode_entry_persistence import predecessor
from test_commissioning_camera_persistence import WINDOWS, CELL, SESSION, LEASES


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    return prepare_services(tmp_path, monkeypatch)


def prepare_services(tmp_path, monkeypatch, *, launch=LAUNCH):
    assigned = tmp_path / "software/runs/physical-camera-acquisition" / launch
    assigned.mkdir(parents=True)
    runtime = PhysicalOnboardingM1Runtime.initialize(
        assigned,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
        created_at_ns=1000,
    )
    runtime.create_session(
        SESSION,
        created_at_ns=2000,
        mode="PHYSICAL_DIAGNOSTIC",
        workspace_source_sha256=SOURCE,
    )
    store = M1PhysicalCameraPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        admission_facts=session_impl._denied_facts,
    )
    with store.stage_transaction(
        SESSION, expected_challenge_sha256=store.verification(SESSION).challenge_sha256
    ) as tx:
        predecessor(tx)
        tx.commit_stage_state(
            STAGE_ORDER[4],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=10001,
            detail_code="MODELED_ORIGINAL_PROBE_SERVICE_ONLY",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    monkeypatch.setattr(session_impl, "source_fingerprint", lambda _: SOURCE)
    session = PhysicalCameraSession(
        tmp_path,
        assigned,
        launch_id=launch,
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
    )
    session.refresh(cancellation=Event(), progress=lambda _: None)
    service = PhysicalCameraAcquisitionService(
        tmp_path, launch_id=launch, source_sha256=SOURCE, mode="physical"
    )
    service.bind_verified_session(session)
    enrollment = service_enrollment(launch)
    plan = service.preview_activation_plan("probe", enrollment)
    c = SimpleNamespace(
        service=service,
        session=session,
        runtime=runtime,
        enrollment=enrollment,
        plan=plan,
        original_calls=[],
        condition_calls=[],
        progress=[],
    )
    docs = PhysicalCameraAdmissionFacts(
        {"provenance": "MODELED_ORIGINAL_SERVICE_NOT_PHYSICAL_ADMISSION"},
        tuple({"MODELED_epoch": index} for index in range(8)),
        plan["selection"],
    )

    def read(tx, **kwargs):
        assert tx.held_leases == LEASES
        assert not service._dispatch_lock.acquire(False)
        assert not session._operation_lock.acquire(False)
        assert kwargs["expected_header_sha256"] == tx.snapshot().header.header_sha256
        kwargs["validate_current_context"]()
        c.original_calls.append(tx)
        return SimpleNamespace(
            summary=lambda: {"MODELED_ORIGINAL": True, "physical_authority": False}
        )

    class ModeledAdmission:
        def __init__(self, original, tx, **kwargs):
            assert c.original_calls[-1] is tx
            assert kwargs["enrollment"] is enrollment
            c.condition_calls.append(kwargs)

        def retained_documents(self):
            return docs.retained_documents()

        def campaign(self):
            return PhysicalCameraActivationCampaign.from_plan(plan)

        def persistence(self, actual_runtime):
            assert actual_runtime.deployment_root == runtime.deployment_root

            def facts(tx, request, snapshot):
                assert tx.held_leases == LEASES and tx.snapshot() == snapshot
                return docs

            return M1PhysicalCameraPersistence(
                actual_runtime,
                workspace_source_sha256=SOURCE,
                scoped_admission_facts=facts,
            )

    monkeypatch.setattr(original_impl, "read_camera_probe_originals", read)
    monkeypatch.setattr(admission_impl, "CameraProbeAdmission", ModeledAdmission)
    c.values = dict(
        request_key="MODELED-original-probe-service",
        expected_header_sha256=runtime.session_snapshot(SESSION).header.header_sha256,
        expected_preparation_sha256="1" * 64,
        expected_review_sha256="2" * 64,
        expected_plan_sha256=digest(canonical(plan)),
        operator_id="MODELED operator",
        arm_actuator_supply_disconnected=True,
        bounded_probe_consent=True,
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 240_000_000_000,
        progress=c.progress.append,
        validate_current_context=lambda: None,
    )
    c.run = lambda **changes: service.run_original_probe(
        session, enrollment, **(c.values | changes)
    )
    return c


@WINDOWS
@pytest.mark.parametrize("fault", [None, "bad-result"])
def test_original_probe_joins_real_dispatch_and_retains_facts_without_publication(
    prepared, tmp_path, monkeypatch, fault
):
    c = prepared
    owners = install_owner(tmp_path, monkeypatch, purpose="probe", fault=fault)
    if fault is None:
        result = c.run()
        assert result == c.service.pending_observation_result("physical_camera_probe")
        assert c.service.view()["publication"]["status"] == "PENDING"
        assert c.service.view()["configuration"]["capabilities"] is None
    else:
        with pytest.raises(ValueError):
            c.run()
        assert c.service.view()["publication"]["status"] != "CURRENT"
    assert len(owners) == 1 and len(c.original_calls) == 1
    assert c.condition_calls[0]["bounded_probe_consent"] is True
    assert c.condition_calls[0]["arm_actuator_supply_disconnected"] is True
    retained = c.service.retained_capture_diagnostics()
    assert (
        retained["dispatch"]["original_admission"]
        == retained["original_probe"]["admission"]
    )
    assert retained["original_probe"]["status"] == (
        "RESULT_STAGED_NOT_PUBLISHED" if fault is None else "FAILED_HELD"
    )
    assert (
        c.service.view()["connected"] is c.service.view()["physical_authority"] is False
    )
    for tx in c.original_calls:
        with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
            tx._check_scope()
    assert not c.runtime.verify(SESSION).active_lease_owners
    with pytest.raises(ValueError, match="do not replay"):
        c.run()
    assert len(owners) == 1
    if fault is None:
        c.service.validate_observation_publication("physical_camera_probe", result)
        c.service.publish_retained_observation("operation-" + "1" * 32)
        assert c.service.view()["configuration"]["capabilities"] is not None
        assert c.service.view()["connected"] is False


@WINDOWS
@pytest.mark.parametrize("kind", ["consent", "stop", "guard", "missing-store"])
def test_original_probe_preflight_failure_never_constructs_a_native_owner(
    prepared, tmp_path, monkeypatch, kind
):
    c = prepared
    owners = install_owner(tmp_path, monkeypatch)
    changes = {}
    if kind == "consent":
        changes["bounded_probe_consent"] = False
    elif kind == "stop":
        c.values["cancellation"].set()
    elif kind == "guard":
        changes["validate_current_context"] = lambda: True
    else:
        c.session._store = None
    with pytest.raises(ValueError):
        c.run(**changes)
    assert not owners and not c.original_calls
    assert c.runtime.verify(SESSION).attempt_event_count == 0
    assert not c.runtime.verify(SESSION).active_lease_owners
    assert c.service._dispatch_lock.acquire(False)
    c.service._dispatch_lock.release()
    if kind != "consent":
        retained = c.service.retained_capture_diagnostics()
        assert retained["original_probe"]["status"] == "FAILED_HELD"
