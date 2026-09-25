"""Stage-5 readback uses the existing owner; all hardware facts are modeled.

No capable process/device calls. Tiny YUY2 files exercise real ingestion. Original
admission is modeled here; actual-store retention is a separate test lane.
"""

from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from rocell.application.camera_activation_campaign_contract import (
    ACTION_IDS,
    CONFIGURATION_CAPTURE_ACTION_ID,
    CONFIGURATION_CAPTURE_WORKER_ID,
    is_camera_activation_action,
    validate_camera_activation_permit,
    validate_camera_activation_binding,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    PLAN_SCHEMA,
    CONFIGURATION_PLAN_SCHEMA,
    verify_camera_activation_campaign_evidence,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage as Stage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.camera_configuration_wizard_contract import CAPTURE_ACTION_ID
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
)
from test_physical_camera_activation_campaign import campaign, components
from test_camera_activation_application_handoff import (
    workflow_fixture,
    write_pixels,
    accept,
    observation,
    references,
    no_device_calls,
    no_physical_owner,
)
from test_camera_activation_service_handoff import setup, stage_settings
from test_physical_camera_configuration import reported_control


BUDGET = CameraCampaignBudget(5000, 1, 16, 16)


def test_distinct_profile_restores_without_io_and_preserves_v2(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("An inert plan attempted filesystem access")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "resolve", "mkdir", "iterdir", "exists"):
            patch.setattr(Path, name, forbidden)
        new = campaign(tmp_path, "capture", configuration_verification=True)
        # Keep the very same reviewed identity snapshot. The enrollment fixture
        # records timestamps, so two independently created owners are not equal.
        old_plan = new.plan()
        old_plan["schema"] = PLAN_SCHEMA
        del old_plan["verification_stage"]
        old = PhysicalCameraActivationCampaign.from_plan(old_plan)
        restored = PhysicalCameraActivationCampaign.from_plan(new.plan())
        assert (
            PhysicalCameraActivationCampaign.from_plan(old.plan()).plan() == old.plan()
        )
    assert restored.plan() == new.plan()
    assert restored.registration() == new.registration()
    assert new._application_guard is restored._application_guard is None
    assert ACTION_IDS.keys() == {"probe", "capture"}
    assert old.plan()["schema"] == PLAN_SCHEMA
    assert "verification_stage" not in old.plan()
    changed = new.plan()
    assert changed.pop("verification_stage") == Stage.CAMERA_MODE_CONTROLS.value
    assert changed.pop("schema") == CONFIGURATION_PLAN_SCHEMA
    original = old.plan()
    original.pop("schema")
    assert changed == original  # No native settings/runtime/budget changes.
    reg = new.registration()
    assert reg.action_id == CONFIGURATION_CAPTURE_ACTION_ID
    assert reg.worker_id == CONFIGURATION_CAPTURE_WORKER_ID
    assert reg.stage is Stage.CAMERA_MODE_CONTROLS
    assert reg.operation_sha256 != old.registration().operation_sha256
    assert old.registration().stage is Stage.CAMERA_FRAME_FRESHNESS
    assert reg.budget.maximum_frames == reg.budget.maximum_reads == 1
    assert new.plan()["physical_authority"] is new.plan()["hardware_qualified"] is False


@pytest.mark.parametrize("value", [1, 0, "true", None, [], {}])
def test_profile_selection_requires_literal_boolean(tmp_path, value):
    with pytest.raises(ValueError, match="EXACT_CONFIGURATION_CAPTURE_PROFILE"):
        campaign(tmp_path, "capture", configuration_verification=value)


def test_probe_cannot_be_relabelled_as_configuration_capture(tmp_path):
    with pytest.raises(ValueError, match="EXACT_CONFIGURATION_CAPTURE_PROFILE"):
        campaign(tmp_path, configuration_verification=True)


@pytest.mark.parametrize(
    "change",
    ["missing-stage", "stage", "schema", "extra", "duration", "frames", "total"],
)
def test_new_profile_is_closed_and_one_frame_only(tmp_path, change):
    plan = campaign(tmp_path, "capture", configuration_verification=True).plan()
    if change == "missing-stage":
        del plan["verification_stage"]
    elif change == "stage":
        plan["verification_stage"] = Stage.CAMERA_FRAME_FRESHNESS.value
    elif change == "schema":
        plan["schema"] = PLAN_SCHEMA
    elif change == "extra":
        plan["stage_pass"] = True
    else:
        key, value = {
            "duration": ("duration_ms", 6000),
            "frames": ("max_frames", 2),
            "total": ("max_total_bytes", 32),
        }[change]
        plan["native_budget"][key] = value
    with pytest.raises(ValueError):
        PhysicalCameraActivationCampaign.from_plan(plan)


def test_real_campaign_core_retains_modeled_stage5_capture_once(tmp_path, monkeypatch):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, "capture", configuration_verification=True
    )
    assert is_camera_activation_action(permit)
    assert validate_camera_activation_permit(permit) == "capture"
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.receipt.frames == result.receipt.reads == 1
    assert result.physical_authority == "NONE" and owner.cleaned
    assert store.evidence == worker.evidence
    verify_camera_activation_campaign_evidence(
        store.evidence, campaign=worker, expected_permit=permit
    )
    validate_camera_activation_binding(permit, store.evidence)
    assert core.execute(permit) == result and calls["owner"] == 1


@pytest.mark.parametrize("change", ["stage", "worker", "frames", "probe"])
def test_exact_permit_cannot_substitute_stage_worker_or_budget(
    tmp_path, monkeypatch, change
):
    _, _, _, permit, _, calls = components(
        tmp_path, monkeypatch, "capture", configuration_verification=True
    )
    reg = permit.registration
    admission = permit.admission
    if change == "stage":
        reg = replace(reg, stage=Stage.CAMERA_FRAME_FRESHNESS)
        admission = replace(admission, stage=reg.stage)
    elif change == "worker":
        reg = replace(reg, worker_id="scoped-" + ACTION_IDS["capture"])
    elif change == "probe":
        reg = replace(reg, action_id=ACTION_IDS["probe"])
    else:
        reg = replace(
            reg, budget=replace(reg.budget, maximum_reads=2, maximum_frames=2)
        )
    changed = replace(permit, registration=reg, admission=admission)
    with pytest.raises(ValueError):
        validate_camera_activation_permit(changed)
    assert calls["owner"] == 0


@pytest.mark.parametrize(
    "fault", ["bad-result", "cleanup-missing-resource", "post-guard"]
)
def test_settings_capture_failure_retains_uncertainty_not_qualification(
    tmp_path, monkeypatch, fault
):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, "capture", fault, configuration_verification=True
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.evidence == worker.evidence and len(store.evidence) == 2
    assert worker.status()["hardware_qualified"] is False
    assert core.execute(permit) == result and calls["owner"] == 1


@pytest.mark.parametrize("prepared_profile", [False, True])
def test_capture_readback_rejects_the_other_stage_profile(
    tmp_path, monkeypatch, prepared_profile
):
    f = workflow_fixture(
        tmp_path, monkeypatch, configuration_verification=prepared_profile
    )
    with pytest.raises(ValueError, match="ORIGINAL_NATIVE_PREPARATION_CONTEXT"):
        accept(f, configuration_verification=not prepared_profile)
    assert f.workflow.last_preview() is None
    assert f.workflow.view()["status"] == "HELD"
    assert not Path(f.capture.camera_plan.request.output_directory).exists()


def test_stage5_readback_ingests_tiny_pixels_but_does_not_qualify(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(f)
    result = accept(f, configuration_verification=True)
    assert result.verification.content_verified
    view = f.workflow.view()
    assert (
        view["configuration"]["readback"]["status"]
        == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
    )
    assert view["hardware_qualified"] is view["physical_authority"] is False
    assert view["last_frame"]["live"] is False
    assert f.workflow.last_preview().png_bytes.startswith(b"\x89PNG")
    with pytest.raises(ValueError, match="ALREADY"):
        accept(f, configuration_verification=True)


@pytest.mark.parametrize("readback", [4, 5, None])
def test_settings_capture_compares_each_requested_manual_control(
    tmp_path, monkeypatch, readback
):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)

    def capabilities(raw):
        raw["native_receipt"]["controls"] = [reported_control("brightness")]

    probe_evidence = observation(
        tmp_path, monkeypatch, f.probe, raw_change=capabilities
    )
    caps = f.workflow.accept_probe(
        probe_evidence, **references(f.probe, probe_evidence)
    )
    f.configuration = f.workflow.stage_settings(
        caps.view()["modes"][0]["choice_id"],
        (CameraControlSetting("brightness", 4),),
        expected_capabilities_sha256=caps.capabilities_sha256,
    )
    plan = f.workflow.capture_plan(budget=BUDGET, configuration_verification=True)
    f.capture = PhysicalCameraActivationCampaign.from_plan(plan)._prepare(
        "attempt-controls", "f" * 64
    )

    def observed(raw):
        raw["native_receipt"]["controls"] = (
            [] if readback is None else [reported_control("brightness", readback)]
        )
        raw["native_receipt"]["counts"]["control_set_attempts"] = 1

    f.evidence = observation(tmp_path, monkeypatch, f.capture, raw_change=observed)
    if readback == 4:
        write_pixels(f)
    result = accept(f, configuration_verification=True)
    assert (result is not None) == (readback == 4)
    comparison = f.workflow.view()["configuration"]["readback"]
    assert comparison["controls"][0]["matched"] == (readback == 4)
    assert comparison["hardware_qualified"] is False
    if readback != 4:
        assert f.workflow.last_preview() is None
        assert not Path(f.capture.camera_plan.request.output_directory).exists()


def test_internal_service_separates_settings_then_freshness_and_publication(
    tmp_path, monkeypatch
):
    service, selected, transactions, owners, run = setup(tmp_path, monkeypatch)
    run()
    service.publish_retained_observation("operation-" + "1" * 32)
    stage_settings(service)
    stable_intent = service.configuration_capture_context()
    configured = run("capture", configuration_verification=True)
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.cache_published_preview("image-" + "3" * 32) is None
    assert configured["action_id"] == CAPTURE_ACTION_ID
    with pytest.raises(ValueError):
        service.validate_observation_publication("physical_camera_capture", configured)
    service.validate_observation_publication(CAPTURE_ACTION_ID, configured)
    service.publish_retained_observation("operation-" + "4" * 32)
    assert service.configuration_capture_context() == stable_intent
    assert service.cache_published_preview("image-" + "5" * 32).startswith(b"\x89PNG")
    first = service.view()["last_frame"]
    captured = run("capture", request_key="separate-modeled-freshness")
    with pytest.raises(ValueError):
        service.validate_observation_publication(CAPTURE_ACTION_ID, captured)
    service.validate_observation_publication("physical_camera_capture", captured)
    service.publish_retained_observation("operation-" + "6" * 32)
    assert [tx._campaign.registration().stage for tx in transactions] == [
        Stage.CAMERA_MODE_CONTROLS,
        Stage.CAMERA_MODE_CONTROLS,
        Stage.CAMERA_FRAME_FRESHNESS,
    ]
    assert (
        transactions[1]._campaign.registration().operation_sha256
        != transactions[2]._campaign.registration().operation_sha256
    )
    assert len(owners) == 3 and all(len(group) == 1 for group in owners)
    assert service.view()["connected"] is service.view()["physical_authority"] is False
    assert service.view()["last_frame"] != first


@pytest.mark.parametrize(
    "failure", ["no-probe", "stop", "source-context", "late-publication"]
)
def test_internal_service_holds_missing_or_failed_settings_capture_context(
    tmp_path, monkeypatch, failure
):
    service, selected, transactions, owners, run = setup(tmp_path, monkeypatch)
    if failure == "no-probe":
        with pytest.raises(ValueError, match="Publish the exact v2 probe"):
            run("capture", configuration_verification=True)
        assert not transactions and not owners
        return
    run()
    service.publish_retained_observation("operation-" + "1" * 32)
    stage_settings(service)
    if failure == "late-publication":
        result = run("capture", configuration_verification=True)
        service.invalidate()
        with pytest.raises(ValueError):
            service.validate_observation_publication(CAPTURE_ACTION_ID, result)
    else:
        stop = Event()
        kwargs = {}
        if failure == "stop":
            stop.set()
            kwargs["cancellation"] = stop
        else:
            kwargs["revalidate_original_context"] = service.invalidate
        with pytest.raises(ValueError):
            run("capture", configuration_verification=True, **kwargs)
        assert len(transactions) == 1
    assert service.cache_published_preview("image-" + "7" * 32) is None


def test_legacy_data_workflow_cannot_select_new_stage5_profile(tmp_path, monkeypatch):
    from test_physical_camera_capture_workflow import workflow_fixture as legacy

    f = legacy(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="EXACT_CONFIGURATION_CAPTURE_PROFILE"):
        f.workflow.capture_plan(budget=BUDGET, configuration_verification=True)
