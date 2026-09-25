"""Actual service/M1/pixels/reopen; setup semantics and native facts are MODELED.

Full-size synthetic YUY2 is produced by an incapable owner. This exercises the
unchanged production file limits, not real optics, throughput or unit identity.
"""

from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter

import pytest

from rocell.application import camera_configuration_original_scope as scope
from rocell.application import camera_operating_original_assessment as assessment
from rocell.application.camera_activation_campaign_contract import (
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from rocell.application.camera_configuration_wizard_contract import CAPTURE_ACTION_ID
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    physical_camera_source_binding,
)
from rocell.application.physical_camera_session import _denied_facts
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    NativeCameraMode,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_original_assessment import originals
from test_camera_original_configuration_service import run_capture
from test_camera_configuration_originals import WINDOWS, LEASES
from test_camera_operating_pixels import packet_for
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner
import test_camera_activation_dispatch_handoff as native_fixture


FRAME_BYTES = 5472 * 3648 * 2
FULL_BUDGET = CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES)


@WINDOWS
@pytest.mark.parametrize("mixed", [False, True])
def test_original_assessment_reopens_complete_checksums_without_launch_promotion(
    originals, tmp_path, monkeypatch, record_property, mixed
):
    c = originals
    prior_fixture = native_fixture.result_fixture

    def full_capture(purpose):
        first, second, raw = prior_fixture(purpose)
        if purpose == "capture":
            mode = asdict(NativeCameraMode(5472, 3648, 8, 1, stride_bytes=10944))
            receipt = raw["native_receipt"]
            receipt.update(modes=[mode], requested_mode=mode, observed_mode=mode)
            receipt["frames"][0].update(length_bytes=FRAME_BYTES, stride_bytes=10944)
        return first, second, raw

    monkeypatch.setattr(native_fixture, "result_fixture", full_capture)
    pixels = b"\x40\x80\x80\x80" * (FRAME_BYTES // 4)
    monkeypatch.setattr(native_fixture, "PIXELS", pixels)
    owners = native_fixture.install_owner(
        tmp_path, monkeypatch, purpose="capture", pixels=True
    )
    keys = ("operation-" + "6" * 32, "operation-" + "7" * 32)
    packets = {}
    for index, key in enumerate(keys):
        sealed = not mixed or index == 1
        c.capture_plan = c.service.preview_activation_plan(
            "capture",
            c.enrollment,
            capture_budget=FULL_BUDGET,
            configuration_verification=True,
            sealed_configuration_capture=sealed,
        )
        started = perf_counter()
        try:
            result = run_capture(c, request_key=key, capture_budget=FULL_BUDGET)
        finally:
            # Test-host timings only, not sensor timestamps or permission to
            # extend production limits. Preserve phase evidence even on failure.
            record_property(f"capture_{index}_elapsed_s", perf_counter() - started)
            record_property(f"capture_{index}_owner_count", len(owners))
        packets[key] = packet_for(result, operation=key)
        c.service.validate_observation_publication(CAPTURE_ACTION_ID, result)
        c.service.publish_retained_observation(key)
    assert len(owners) == 2 and all(owner.cleaned for owner in owners)

    # Fresh adapter and OS leases; it cannot issue new admission facts. Native
    # originals/checksums are read from disk, not copied from the service cache.
    reopened = PhysicalOnboardingM1Runtime.open(
        c.runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(c.service.source_sha256),
        cell_id=c.service.cell_id,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened,
        workspace_source_sha256=c.service.source_sha256,
        admission_facts=_denied_facts,
    )
    c.arguments.update(
        plan=c.capture_plan, expected_plan_sha256=digest(canonical(c.capture_plan))
    )
    with fresh.transaction(LEASES) as tx:
        original = scope.read_camera_configuration_originals(
            c.read_setup(tx), tx, **c.arguments
        )
        before = tx.snapshot()

        def assess():
            return assessment.assess_original_operating_proposal(
                original,
                tx,
                proposal_payload=c.proposal.payload,
                expected_proposal_sha256=c.proposal.sha256,
                capture_request_keys=keys,
                # Mixed case proves even a matching old logged reference is not
                # silently relabeled original. New-only case has NO log packets.
                capture_packets=packets if mixed else None,
            )

        report = assess()
        assert report["schema"] == assessment.SEALED_SCHEMA
        assert all(
            row["verified_bytes"] == FRAME_BYTES for row in report["pixel_checks"]
        )
        assert ("PIXEL_FILES_NOT_VERIFIED" in report["unresolved_checks"]) is mixed
        assert not report["original_stage_record_retained"]
        assert not report["approved_operating_policy"] and not report["connected"]
        assert not report["stage_requirements"]["stage_passed"]
        capture = report["captures"][1]
        stored = tx.read_camera_activation_evidence(capture["attempt_id"])
        outcome = tx.read_campaign_result(capture["attempt_id"])
        assert outcome.receipt.evidence_sha256s == stored.evidence_sha256s
        assert len(outcome.receipt.evidence_sha256s) == 3
        assert capture["capture_checksum_sha256"] == stored.checksum.sha256
        assert report["pixel_checks"][1]["result_sha256"] is None
        assert report["pixel_checks"][1]["native_frame_sha256"] == digest(pixels)

        # Corrupt a byte only after original sealing. No new expected digest,
        # rewrite, alternate selection, native owner or stage mutation is allowed.
        _, native, _ = assessment._native(
            tx,
            capture["attempt_id"],
            SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
        )
        path = (
            Path(native.preparation.camera_plan.request.output_directory)
            / "frame-000000.yuy2"
        )
        with path.open("r+b") as stream:
            stream.write(b"\x41")
        changed = assess()
        assert (
            changed["pixel_checks"][1]["status"] == "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"
        )
        assert changed["pixel_checks"][1]["native_frame_sha256"] == digest(pixels)
        assert "PIXEL_FILES_NOT_VERIFIED" in changed["unresolved_checks"]
        assert tx.snapshot() == before

        read_result = tx.read_campaign_result

        def wrong_receipt(attempt):
            value = read_result(attempt)
            if attempt == capture["attempt_id"]:
                return replace(
                    value,
                    receipt=replace(
                        value.receipt,
                        evidence_sha256s=value.receipt.evidence_sha256s[:2]
                        + ("f" * 64,),
                    ),
                )
            return value

        monkeypatch.setattr(tx, "read_campaign_result", wrong_receipt)
        with pytest.raises(ValueError, match="OPERATING_ORIGINAL_ACCOUNTING"):
            assess()
    assert len(owners) == 2
    assert not reopened.verify(c.service.session_id).active_lease_owners
