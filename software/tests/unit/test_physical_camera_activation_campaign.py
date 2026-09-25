"""Production v2 campaign/core/supervisor with modeled owners; no native access."""

from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_camera_activation_campaign as module
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    verify_camera_activation_campaign_evidence,
)
from rocell.application.camera_activation_campaign_contract import (
    camera_activation_execution,
)
from rocell.application.cell_commissioning_coordinator import (
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.native_camera_activation_registration import (
    create_activation_runtime,
)
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    NativeCameraMode,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_native_camera_activation_expectation import enrollment
from test_native_camera_activation_registration import ready
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_protocol import fixture as result_fixture
from test_native_camera_activation_supervisor import ModelOwner, no_physical_owner
from test_camera_activation_campaign_contract import CameraV2Store
from test_physical_camera_coordinator import CELL, SESSION, SOURCE, admission
from test_wizard_native_camera_enrollment import SESSION as LAUNCH_SESSION


def campaign(
    directory,
    purpose="probe",
    *,
    configuration_verification=False,
    sealed_configuration_capture=False,
):
    model = enrollment()
    return PhysicalCameraActivationCampaign.from_enrollment(
        directory,
        directory / "assigned-output",
        enrollment=model,
        launch_session_id=LAUNCH_SESSION,
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
        runtime=create_activation_runtime(
            directory,
            purpose=purpose,
            source_sha256=SOURCE,
            catalog_sha256="b" * 64,
            helper_sha256="c" * 64,
            build_record_sha256="d" * 64,
        ),
        mode=NativeCameraMode(4, 2, 9, 1, "YUY2", 8) if purpose == "capture" else None,
        budget=CameraCampaignBudget(5000, 1, 16, 16) if purpose == "capture" else None,
        configuration_verification=configuration_verification,
        sealed_configuration_capture=sealed_configuration_capture,
    )


def components(
    directory,
    monkeypatch,
    purpose="probe",
    fault=None,
    *,
    reviewed_runtime=False,
    configuration_verification=False,
    sealed_configuration_capture=False,
):
    worker = campaign(
        directory,
        purpose,
        configuration_verification=configuration_verification,
        sealed_configuration_capture=sealed_configuration_capture,
    )
    if reviewed_runtime:
        from rocell.application.camera_activation_runtime_policy import (
            reviewed_activation_runtime_candidate,
        )

        plan = worker.plan()
        plan["runtime"] = reviewed_activation_runtime_candidate(
            directory, purpose=purpose, source_sha256=SOURCE
        ).to_dict()
        worker = PhysicalCameraActivationCampaign.from_plan(plan)
    reg = worker.registration()
    snapshot = admission(
        stage=reg.stage,
        selected_identity_sha256=worker.plan()["selected_identity_sha256"],
    )
    store = CameraV2Store(snapshot)
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(reg,),
        workers={reg.worker_id: worker},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, reg.action_id, "actual-v2-adapter", snapshot.challenge_sha256
    )
    permit = core.prepare(request)
    prepared = worker.preparation_for_permit(permit)
    raw_owner, args = modeled(directory, purpose)
    args["ready_wire"] = ready(prepared)
    _, _, raw = result_fixture(purpose)
    raw["request_sha256"] = prepared.admission_request.request_sha256
    raw["permit_sha256"] = permit.permit_sha256
    raw_owner.stdout = args["ready_wire"] + canonical(raw) + b"\n"
    owner = ModelOwner(raw_owner, args, fault)
    calls = {"guard": 0, "source": 0, "owner": 0}

    def new_owner():
        calls["owner"] += 1
        return owner

    def guard():
        calls["guard"] += 1
        if fault == "guard-deny" or (fault == "post-guard" and owner.cleaned):
            raise ValueError("MODELED_ORIGINAL_CONTEXT_REVOKED")
        if fault == "boolean-guard":
            return True
        if fault == "post-interrupt" and owner.cleaned:
            raise KeyboardInterrupt("MODELED_LATE_INTERRUPT")
        if calls["guard"] == 16:
            if fault == "post-plan-mutation":
                worker._plan = worker._plan + b" "
            elif fault == "post-guard-mutation":
                worker._application_guard = lambda: None

    def source(path):
        calls["source"] += 1
        assert path == directory
        return (
            "9" * 64
            if fault == "source-drift" or (fault == "post-source" and owner.cleaned)
            else SOURCE
        )

    monkeypatch.setattr(supervisor, "_new_owner", new_owner)
    monkeypatch.setattr(module, "source_fingerprint", source)
    if not reviewed_runtime:
        # These tests model runtime approval as well as native effects. The
        # separate installed-policy composition below verifies actual file bytes.
        monkeypatch.setattr(
            module, "verify_reviewed_activation_runtime", lambda *a, **k: {}
        )
    if fault != "missing-guard":
        worker._bind_application_guard(guard)
    return worker, core, store, permit, owner, calls


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_plan_and_registration_are_inert_and_exactly_restorable(
    tmp_path, monkeypatch, purpose
):
    def denied(*args, **kwargs):
        pytest.fail("Inert campaign touched filesystem or source")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "resolve", "mkdir", "iterdir", "exists"):
            patch.setattr(Path, name, denied)
        patch.setattr(module, "source_fingerprint", denied)
        worker = campaign(tmp_path, purpose)
        restored = PhysicalCameraActivationCampaign.from_plan(worker.plan())
    assert restored.plan() == worker.plan()
    assert restored.registration() == worker.registration()
    assert worker.status() == dict(
        consumed=False,
        evidence_available=False,
        post_context_failed=False,
        physical_authority=False,
        hardware_qualified=False,
        retries=0,
    )
    assert worker.plan()["runtime"]["dispatch_enabled"] is False
    assert worker.plan()["output_policy"]["reuse"] is False


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_actual_adapter_runs_core_and_supervisor_then_returns_exact_retention(
    tmp_path, monkeypatch, purpose
):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, purpose
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.receipt.opens == result.receipt.closes == 1
    assert result.receipt.frames == int(purpose == "capture")
    assert calls == {"guard": 16, "source": 8, "owner": 1}
    assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 4
    assert store.evidence == worker.evidence and owner.cleaned
    assert (
        verify_camera_activation_campaign_evidence(
            worker.evidence, campaign=worker, expected_permit=permit
        )
        == worker.evidence
    )
    from rocell.application.camera_activation_campaign_evidence import (
        validate_camera_activation_evidence,
    )

    deadline = validate_camera_activation_evidence(worker.evidence).run.to_dict()[
        "parent_deadline_ns"
    ]
    assert (
        camera_activation_execution(
            permit, worker.evidence, expected_deadline_ns=deadline
        ).receipt
        == result.receipt
    )
    assert core.execute(permit) == result and calls["owner"] == 1
    assert not (
        tmp_path / "assigned-output"
    ).exists()  # Owner/filesystem deliberately modeled here.


@pytest.mark.parametrize(
    "fault", ["missing-guard", "guard-deny", "boolean-guard", "source-drift"]
)
def test_original_guard_and_source_are_mandatory_before_owner(
    tmp_path, monkeypatch, fault
):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, fault=fault
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert calls["owner"] == 0 and not owner.created and worker.evidence is None


@pytest.mark.parametrize(
    "fault",
    [
        "bad-result",
        "cleanup-missing-resource",
        "post-guard",
        "post-source",
        "post-plan-mutation",
        "post-guard-mutation",
    ],
)
def test_returned_evidence_survives_failed_native_cleanup_and_final_context(
    tmp_path, monkeypatch, fault
):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, fault=fault
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.evidence == worker.evidence and len(store.evidence) == 2
    if fault == "bad-result":
        assert result.receipt is None
    if fault.startswith("post-"):
        assert worker.status()["post_context_failed"]
        assert "CONSUMED_SCOPE_REVALIDATION_FAILED" in result.reason_codes
    assert store.trace.index("CAMERA_V2_EVIDENCE_RETAINED") < store.trace.index(
        "QUARANTINE_LATCHED"
    )


def test_cancellation_after_owner_cleanup_is_retained_without_success(
    tmp_path, monkeypatch
):
    worker, core, store, permit, owner, calls = components(tmp_path, monkeypatch)
    cancel = Event()
    original = owner.cleanup

    def stop(deadline):
        result = original(deadline)
        cancel.set()
        return result

    owner.cleanup = stop
    result = core.execute(permit, cancellation=cancel)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert store.evidence == worker.evidence and worker.status()["post_context_failed"]


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "expectation_sha256",
        "selected_identity_sha256",
        "launch_session_id",
        "maximum_evidence_bytes",
        "extra",
    ],
)
def test_plan_restoration_cannot_accept_inconsistent_fields(tmp_path, field):
    plan = campaign(tmp_path).plan()
    plan[field] = "not-the-original"
    with pytest.raises((ValueError, TypeError)):
        PhysicalCameraActivationCampaign.from_plan(plan)


@pytest.mark.parametrize(
    "field", ["endpoint", "original_identity_sha256", "instance_id", "container_id"]
)
def test_expectation_cannot_substitute_another_selected_identity(tmp_path, field):
    plan = campaign(tmp_path).plan()
    plan["expectation"][field] = (
        "8" * 64
        if field == "original_identity_sha256"
        else (
            "99999999-9999-9999-9999-999999999999"
            if field == "container_id"
            else "other"
        )
    )
    from rocell.providers.windows.native_camera_protocol import digest

    plan["expectation_sha256"] = digest(canonical(plan["expectation"]))
    with pytest.raises(ValueError):
        PhysicalCameraActivationCampaign.from_plan(plan)


def test_guard_does_not_survive_plan_restoration_and_cannot_be_rebound(
    tmp_path, monkeypatch
):
    worker, core, store, permit, owner, calls = components(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        worker._bind_application_guard(lambda: None)
    restored = PhysicalCameraActivationCampaign.from_plan(worker.plan())
    assert restored._application_guard is None
    core.execute(permit)
    with pytest.raises(ValueError):
        worker._bind_application_guard(lambda: None)
    with pytest.raises(ValueError):
        worker.run_scoped_campaign(
            permit,
            deadline_ns=permit.expires_at_ns,
            cancellation=Event(),
            authorization=object(),
        )


def test_late_interrupt_retains_then_propagates(tmp_path, monkeypatch):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, fault="post-interrupt"
    )
    with pytest.raises(KeyboardInterrupt, match="MODELED_LATE_INTERRUPT"):
        core.execute(permit)
    assert store.evidence == worker.evidence and owner.cleaned
    result = store.results[permit.attempt_id]
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert (
        result.receipt is not None
        and "CONSUMED_SCOPE_REVALIDATION_FAILED" in result.reason_codes
    )


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_actual_installed_software_policy_joins_scoped_campaign(monkeypatch, purpose):
    from rocell.application import camera_activation_runtime_policy as policy

    root = Path(__file__).resolve().parents[3]
    worker, core, store, permit, owner, calls = components(
        root, monkeypatch, purpose, reviewed_runtime=True
    )
    # Original source/identity/stage facts and the process owner remain MODELED.
    # The actual reviewed catalog, helper, build record and 24 native inputs are
    # checked by the real policy on every current scoped campaign boundary.
    monkeypatch.setattr(policy, "source_fingerprint", lambda _: SOURCE)
    reviews = []
    actual = policy.verify_reviewed_activation_runtime

    def checked(*args, **kwargs):
        review = actual(*args, **kwargs)
        reviews.append(review)
        return review

    monkeypatch.setattr(module, "verify_reviewed_activation_runtime", checked)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert len(reviews) == 8 and all(row["files_checked"] == 26 for row in reviews)
    assert owner.cleaned and calls["owner"] == 1
    assert store.evidence == worker.evidence
    assert all(row["hardware_qualified"] is False for row in reviews)


def test_runtime_refusal_cannot_be_bypassed_by_a_matching_original_guard(
    tmp_path, monkeypatch
):
    worker, core, store, permit, owner, calls = components(tmp_path, monkeypatch)

    def refused(*args, **kwargs):
        raise ValueError("SOFTWARE_RUNTIME_REFUSED")

    monkeypatch.setattr(module, "verify_reviewed_activation_runtime", refused)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert calls["guard"] > 0 and calls["owner"] == 0
    assert worker.evidence is None and not owner.created
