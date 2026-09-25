"""Actual campaign/core and guarded files; original/native owners are MODELED.

No physical producer is available. Pixels are written by the incapable owner's
cleanup hook, not acquired from a camera. This does not exercise wizard admission.
"""

from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_camera_activation_campaign as campaign_module
from rocell.application import camera_capture_checksum_reader as reader
from rocell.application.camera_sealed_capture_contract import (
    validate_sealed_capture_binding,
)
from rocell.application.camera_sealed_capture_evidence import (
    MAX_SEALED_CAPTURE_BYTES,
    SealedCameraCaptureEvidence,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    SEALED_CONFIGURATION_PLAN_SCHEMA,
    verify_camera_activation_campaign_evidence,
)
from rocell.application.camera_activation_campaign_contract import (
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows.native_camera_protocol import digest
from test_physical_camera_activation_campaign import campaign, components
from test_native_camera_activation_supervisor import no_physical_owner
from test_camera_activation_application_handoff import no_device_calls, PIXELS


def setup(tmp_path, monkeypatch, *, fault=None, pixels=True):
    worker, core, store, permit, owner, calls = components(
        tmp_path,
        monkeypatch,
        "capture",
        fault,
        configuration_verification=True,
        sealed_configuration_capture=True,
    )
    assert len(PIXELS) == 16  # Exact 4 x 2 YUY2 fixture, not a camera observation.
    prepared = worker.preparation_for_permit(permit)
    path = Path(prepared.camera_plan.request.output_directory) / "frame-000000.yuy2"
    cleanup = owner.cleanup

    def finish(deadline):
        result = cleanup(deadline)
        if pixels:
            path.parent.mkdir(parents=True)
            path.write_bytes(PIXELS)
        return result

    def retain(exact, evidence):
        # Only persistence is modeled here. Use the real independent binding
        # contract before letting this fixture stand in for the original store.
        assert store.acknowledged
        validate_sealed_capture_binding(exact, evidence)
        store.evidence = evidence
        store.trace.append("CAMERA_SEALED_EVIDENCE_RETAINED")

    owner.cleanup = finish
    monkeypatch.setattr(store, "retain_camera_activation_evidence", retain)
    return worker, core, store, permit, owner, calls, path


def test_sealed_plan_is_distinct_and_inert_while_old_plan_stays_exact(
    tmp_path, monkeypatch
):
    old = campaign(tmp_path, "capture", configuration_verification=True)

    def refused(*a, **k):
        pytest.fail("Inert plan performed I/O")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "resolve", "mkdir", "iterdir", "exists"):
            patch.setattr(Path, name, refused)
        new = campaign(
            tmp_path,
            "capture",
            configuration_verification=True,
            sealed_configuration_capture=True,
        )
        restored = PhysicalCameraActivationCampaign.from_plan(new.plan())
        legacy = PhysicalCameraActivationCampaign.from_plan(old.plan())
    assert legacy.plan() == old.plan()
    assert legacy.registration() == old.registration()
    assert restored.plan() == new.plan()
    assert restored.registration() == new.registration()
    assert restored._application_guard is None and restored.evidence is None
    assert new.plan()["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA
    assert new.registration().action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
    assert new.registration().budget.maximum_output_bytes == MAX_SEALED_CAPTURE_BYTES
    assert new.registration().budget == replace(
        old.registration().budget, maximum_output_bytes=MAX_SEALED_CAPTURE_BYTES
    )
    assert old.registration().operation_sha256 != new.registration().operation_sha256
    assert new.plan()["physical_authority"] is new.plan()["hardware_qualified"] is False


@pytest.mark.parametrize(
    "purpose,configuration,sealed",
    [
        ("probe", False, True),
        ("capture", False, True),
        ("capture", True, 1),
        ("capture", True, "yes"),
        ("capture", True, None),
    ],
)
def test_profile_selector_is_exact_not_a_permission_flag(
    tmp_path, purpose, configuration, sealed
):
    with pytest.raises(ValueError, match="PROFILE_REQUIRED"):
        campaign(
            tmp_path,
            purpose,
            configuration_verification=configuration,
            sealed_configuration_capture=sealed,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("maximum_evidence_bytes", 1),
        ("verification_stage", "camera_frame_freshness"),
        ("campaign_timeout_ms", 25001),
        ("physical_authority", True),
        ("schema", "rocell.physical_native_camera_configuration_campaign.v3"),
    ],
)
def test_sealed_plan_does_not_restore_changed_contract(tmp_path, field, value):
    plan = campaign(
        tmp_path,
        "capture",
        configuration_verification=True,
        sealed_configuration_capture=True,
    ).plan()
    plan[field] = value
    with pytest.raises(ValueError):
        PhysicalCameraActivationCampaign.from_plan(plan)


def test_actual_campaign_reads_owned_synthetic_pixels_before_retention(
    tmp_path, monkeypatch
):
    worker, core, store, permit, owner, calls, path = setup(tmp_path, monkeypatch)
    collect = campaign_module._collect_owned_capture_checksum
    observations = []

    def checked(evidence, **kwargs):
        assert owner.cleaned and "CAMERA_SEALED_EVIDENCE_RETAINED" not in store.trace
        assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 4
        result = collect(evidence, **kwargs)
        observations.append((result, kwargs["deadline_ns"]))
        return result

    monkeypatch.setattr(campaign_module, "_collect_owned_capture_checksum", checked)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, (
        result.reason_codes,
        store.evidence.checksum.to_dict(),
        calls,
    )
    assert type(store.evidence) is SealedCameraCaptureEvidence
    assert store.evidence == worker.evidence
    assert result.receipt.opens == result.receipt.closes == result.receipt.frames == 1
    assert result.receipt.reads == 1 and result.receipt.writes == 0
    assert result.receipt.evidence_sha256s == store.evidence.evidence_sha256s
    assert len(result.receipt.evidence_sha256s) == 3
    assert result.receipt.output_bytes == store.evidence.payload_bytes
    assert store.evidence.checksum.to_dict()["frame"]["sha256"] == digest(PIXELS)
    assert store.evidence.checksum.to_dict()["deadline_ns"] == observations[0][1]
    assert path.read_bytes() == PIXELS
    assert calls == {"guard": 20, "source": 10, "owner": 1}
    assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 5
    assert (
        verify_camera_activation_campaign_evidence(
            store.evidence, campaign=worker, expected_permit=permit
        )
        == store.evidence
    )
    assert core.execute(permit) == result and calls["owner"] == 1


@pytest.mark.parametrize(
    "fault",
    [
        "missing-guard",
        "guard-deny",
        "boolean-guard",
        "source-drift",
    ],
)
def test_no_original_authority_means_no_owner_or_checksum(tmp_path, monkeypatch, fault):
    worker, core, store, permit, owner, calls, path = setup(
        tmp_path, monkeypatch, fault=fault
    )
    monkeypatch.setattr(
        campaign_module,
        "_collect_owned_capture_checksum",
        lambda *a, **k: pytest.fail("No file read without original scope"),
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert calls["owner"] == 0 and worker.evidence is None and not path.exists()


@pytest.mark.parametrize(
    "fault,status",
    [
        ("bad-result", "NATIVE_CAPTURE_NOT_COMPLETE"),
        ("cleanup-missing-resource", "NATIVE_CAPTURE_NOT_COMPLETE"),
        ("post-guard", "PIXEL_READ_NOT_ATTESTED"),
        ("post-source", "PIXEL_READ_NOT_ATTESTED"),
        ("post-plan-mutation", "PIXEL_READ_NOT_ATTESTED"),
        ("post-guard-mutation", "PIXEL_READ_NOT_ATTESTED"),
    ],
)
def test_native_evidence_survives_failed_native_or_post_context(
    tmp_path, monkeypatch, fault, status
):
    worker, core, store, permit, owner, calls, path = setup(
        tmp_path, monkeypatch, fault=fault
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    data = store.evidence.checksum.to_dict()
    assert data["status"] == status and data["frame"] is None
    assert data["read_started_ns"] is data["read_finished_ns"] is None
    assert worker.evidence == store.evidence and calls["owner"] == 1
    assert store.trace.index("CAMERA_SEALED_EVIDENCE_RETAINED") < store.trace.index(
        "QUARANTINE_LATCHED"
    )
    if fault == "bad-result":
        assert result.receipt is None
    else:
        assert result.receipt.frames == result.receipt.opens == 1
        assert result.receipt.cleanup_confirmed is False


def test_missing_file_does_not_erase_native_counts_or_recapture(tmp_path, monkeypatch):
    worker, core, store, permit, owner, calls, path = setup(
        tmp_path, monkeypatch, pixels=False
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert store.evidence.checksum.to_dict()["status"] == "PIXEL_READ_FAILED"
    assert result.receipt.frames == result.receipt.opens == result.receipt.closes == 1
    assert result.receipt.cleanup_confirmed is False
    assert core.execute(permit) == result and calls["owner"] == 1
    assert not path.exists()


@pytest.mark.parametrize(
    "fault",
    [
        "cancel-after-native",
        "reader-clock",
        "reader-deadline",
        "reader-shape",
        "reader-key",
        "reader-interrupt",
    ],
)
def test_late_failure_retains_original_counts_without_inventing_read_facts(
    tmp_path, monkeypatch, fault
):
    worker, core, store, permit, owner, calls, path = setup(tmp_path, monkeypatch)
    cancel = Event()
    cleanup = owner.cleanup
    collect = campaign_module._collect_owned_capture_checksum

    if fault == "cancel-after-native":

        def stop(deadline):
            result = cleanup(deadline)
            cancel.set()
            return result

        owner.cleanup = stop
    elif fault == "reader-clock":
        monkeypatch.setattr(reader, "monotonic_ns", lambda: 0)
    elif fault == "reader-deadline":

        def expired(evidence, **kwargs):
            monkeypatch.setattr(reader, "monotonic_ns", lambda: kwargs["deadline_ns"])
            return collect(evidence, **kwargs)

        monkeypatch.setattr(campaign_module, "_collect_owned_capture_checksum", expired)
    elif fault == "reader-shape":
        monkeypatch.setattr(
            campaign_module, "_collect_owned_capture_checksum", lambda *a, **k: None
        )
    elif fault == "reader-key":

        def wrong_key(evidence, **kwargs):
            return collect(evidence, **dict(kwargs, request_key="another-request"))

        monkeypatch.setattr(
            campaign_module, "_collect_owned_capture_checksum", wrong_key
        )
    else:

        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt("MODELED_CHECKSUM_INTERRUPT")

        monkeypatch.setattr(
            campaign_module, "_collect_owned_capture_checksum", interrupt
        )

    if fault == "reader-interrupt":
        with pytest.raises(KeyboardInterrupt, match="MODELED_CHECKSUM_INTERRUPT"):
            core.execute(permit, cancellation=cancel)
        result = store.results[permit.attempt_id]
    else:
        result = core.execute(permit, cancellation=cancel)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.receipt.frames == result.receipt.opens == result.receipt.closes == 1
    assert result.receipt.cleanup_confirmed is False
    data = store.evidence.checksum.to_dict()
    # Cancellation during owner cleanup is already represented as an incomplete
    # native run. Do not relabel it as a successful native run with a later fault.
    expected_status = {
        "reader-deadline": "PIXEL_READ_INTERRUPTED",
        "cancel-after-native": "NATIVE_CAPTURE_NOT_COMPLETE",
    }.get(fault, "PIXEL_READ_NOT_ATTESTED")
    assert data["status"] == expected_status
    assert data["frame"] is None and data["verified_pixel_bytes"] == 0
    assert calls["owner"] == 1 and owner.cleaned


def test_final_context_refusal_keeps_hash_as_diagnostic_not_known_completion(
    tmp_path, monkeypatch
):
    worker, core, store, permit, owner, calls, path = setup(tmp_path, monkeypatch)
    collect = campaign_module._collect_owned_capture_checksum

    def read_then_revoke(evidence, **kwargs):
        subject = collect(evidence, **kwargs)
        worker._application_guard = lambda: None
        return subject

    monkeypatch.setattr(
        campaign_module, "_collect_owned_capture_checksum", read_then_revoke
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.evidence.checksum.to_dict()["frame"]["sha256"] == digest(PIXELS)
    assert "CONSUMED_SCOPE_REVALIDATION_FAILED" in result.reason_codes
    assert calls["owner"] == 1 and worker.status()["post_context_failed"]
