"""Existing acquisition service through v2 dispatch and staged publication.

Process, source, admission facts and persistence are explicitly modeled here;
the separate M1 tests use the production wrapper. Real small pixels pass through
the existing ingester. Nothing calls a browser or a physical device.
"""

from threading import Event

import pytest

from rocell.application import physical_camera_dispatch as dispatch
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.providers.windows.camera_worker_client import CameraCampaignBudget
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_activation_application_handoff import no_device_calls
from test_camera_activation_dispatch_handoff import ActivationStoreModel, install_owner
from test_native_camera_activation_expectation import enrollment
from test_native_camera_activation_supervisor import no_physical_owner
from test_physical_camera_coordinator import SOURCE
from test_wizard_native_camera_enrollment import generic_review


LAUNCH = "wizard-" + "1" * 32


def service_enrollment(launch=LAUNCH):
    # Enroll the same modeled driver packet in a valid application launch; do
    # not change production launch validation to accept the codec test's label.
    original = enrollment().export_snapshot()
    packet = original["identity_packet"]
    selected = WizardNativeCameraEnrollment(
        "physical",
        launch,
        SOURCE,
        {key: packet[key] for key in ("provenance", "helper_sha256")},
    )
    selected.ingest_inventory(
        original["inventory_packet"],
        operation_id="modeled-v2-service-inventory",
        generic_review=generic_review(mode="physical", source=SOURCE, session=launch),
    )
    choice = selected.choices()[0]["value"]
    selected.retain_identity(choice, packet, operation_id="modeled-v2-service-identity")
    selected.review(choice, "modeled-service-reviewer")
    return selected


def setup(tmp_path, monkeypatch):
    service = PhysicalCameraAcquisitionService(
        tmp_path, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
    )
    selected, transactions, owners = service_enrollment(), [], []

    def constructor(persistence, campaign, *, revalidate_context):
        owner = dispatch._CameraDispatchTransaction(
            ActivationStoreModel(campaign),
            campaign,
            revalidate_context=revalidate_context,
        )
        transactions.append(owner)
        return owner

    # Explicit test-only store seam; production rejects this protocol model.
    monkeypatch.setattr(dispatch, "PhysicalCameraDispatchOwner", constructor)

    def run(purpose="probe", *, configuration_verification=False, **overrides):
        plan = service.preview_activation_plan(
            purpose,
            selected,
            configuration_verification=configuration_verification,
            capture_budget=(
                CameraCampaignBudget(5000, 1, 16, 16) if purpose == "capture" else None
            ),
        )
        values = dict(
            persistence=None,
            request_key="service-v2-" + purpose,
            expected_plan_sha256=digest(canonical(plan)),
            cancellation=Event(),
            revalidate_original_context=lambda: None,
        )
        values.update(overrides)
        owners.append(
            install_owner(tmp_path, monkeypatch, purpose=purpose, pixels=True)
        )
        return service.run_admitted_activation_campaign(
            PhysicalCameraActivationCampaign.from_plan(plan), selected, **values
        )

    return service, selected, transactions, owners, run


def stage_settings(service):
    fields = service.configuration_fields()
    values = {field["name"]: field["default"] for field in fields if "default" in field}
    values["mode_choice_id"] = fields[0]["options"][0]["value"]
    values["operator_id"] = "modeled-settings-operator"
    context = service.configuration_context_sha256()
    service.begin_configuration_action(context)
    staged = service.stage_configuration(
        values, expected_context_sha256=context, cancellation=Event()
    )
    service.publish_configuration("operation-" + "2" * 32, staged)


def test_service_v2_probe_settings_capture_waits_for_each_completion_before_preview(
    tmp_path, monkeypatch
):
    service, selected, transactions, owners, run = setup(tmp_path, monkeypatch)
    assert service.preview_activation_plan("probe", selected)["purpose"] == "probe"
    assert not service.directory.exists()
    probe = run()
    assert probe == service.pending_observation_result("physical_camera_probe")
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.view()["configuration"]["capabilities"] is None
    service.validate_observation_publication("physical_camera_probe", probe)
    service.publish_retained_observation("operation-" + "1" * 32)
    assert service.view()["configuration"]["capabilities"] is not None
    stage_settings(service)
    captured = run("capture")
    assert captured["status"] == "SUCCEEDED"
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.cache_published_preview("image-" + "3" * 32) is None
    service.validate_observation_publication("physical_camera_capture", captured)
    service.publish_retained_observation("operation-" + "4" * 32)
    assert service.cache_published_preview("image-" + "5" * 32).startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert service.view()["status"] == "CONTENT_VERIFIED"
    assert service.view()["connected"] is False
    assert service.view()["last_frame"]["live"] is False
    assert len(transactions) == 2 and [len(group) for group in owners] == [1, 1]
    diagnostic = service.retained_capture_diagnostics()
    assert (
        diagnostic["current"]["capture"]["schema"]
        == "rocell.camera_activation_observation_pair.v2"
    )
    assert (
        diagnostic["dispatch"]["original_evidence"] == diagnostic["current"]["capture"]
    )


@pytest.mark.parametrize("published", [False, True])
def test_service_v2_cannot_replace_pending_or_published_probe(
    tmp_path, monkeypatch, published
):
    service, _, transactions, owners, run = setup(tmp_path, monkeypatch)
    run()
    if published:
        service.publish_retained_observation("operation-" + "1" * 32)
    with pytest.raises(ValueError, match="Finish the existing observation"):
        run()
    assert len(transactions) == 1 and sum(map(len, owners)) == 1


@pytest.mark.parametrize(
    "fault", ["plan", "stop", "guard-denies", "guard-boolean", "context-drift"]
)
def test_service_v2_refuses_stale_or_unapproved_context_before_process(
    tmp_path, monkeypatch, fault
):
    service, _, transactions, owners, run = setup(tmp_path, monkeypatch)
    overrides = {}
    if fault == "plan":
        overrides["expected_plan_sha256"] = "1" * 64
    elif fault == "stop":
        stop = Event()
        stop.set()
        overrides["cancellation"] = stop
    elif fault == "guard-boolean":
        overrides["revalidate_original_context"] = lambda: True
    elif fault == "context-drift":
        overrides["revalidate_original_context"] = service.invalidate
    else:

        def deny():
            raise PermissionError("MODELED_ORIGINAL_NOT_ADMITTED")

        overrides["revalidate_original_context"] = deny
    with pytest.raises((ValueError, PermissionError)):
        run(**overrides)
    assert not transactions and not any(owners)
    assert service.cache_published_preview("image-" + "1" * 32) is None


def test_service_v2_failed_outer_publication_keeps_diagnostics_but_no_current_data(
    tmp_path, monkeypatch
):
    service, _, _, _, run = setup(tmp_path, monkeypatch)
    result = run()
    # Models outer completion-log failure: the owner withdraws current data.
    service.invalidate()
    with pytest.raises(ValueError):
        service.validate_observation_publication("physical_camera_probe", result)
    with pytest.raises(ValueError):
        service.publish_retained_observation("operation-" + "1" * 32)
    assert service.view()["configuration"]["capabilities"] is None
    assert service.retained_capture_diagnostics()["pending"]["probe"]["run"]


def test_service_v2_cannot_plan_capture_from_metadata_alone(tmp_path, monkeypatch):
    service, selected, transactions, owners, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Publish the exact v2 probe"):
        service.preview_activation_plan(
            "capture", selected, capture_budget=CameraCampaignBudget(5000, 1, 16, 16)
        )
    assert not transactions and not owners and not service.directory.exists()
