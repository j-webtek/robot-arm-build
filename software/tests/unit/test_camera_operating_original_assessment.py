"""Real M1/native probe reads; full setup semantics are explicitly MODELED.

Full-resolution metadata allocates no pixels and launches no physical process.
The fixture does not establish genuine identity, USB history or calibration.
"""

from dataclasses import asdict
from pathlib import Path
import shutil
from threading import Event
import time
import json

import pytest

from rocell.application import (
    camera_configuration_original_scope as configuration_scope,
)
from rocell.application import camera_operating_original_assessment as module
from rocell.application.camera_operating_proposal import build_camera_operating_proposal
from rocell.application.physical_camera_mode_entry import (
    build_camera_mode_entry,
    HASH_FIELDS,
)
from rocell.providers.windows.camera_worker_client import (
    NativeCameraMode,
    CameraCampaignBudget,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_configuration_originals import make_context, WINDOWS, LEASES
import test_camera_configuration_originals as context_fixture
import test_camera_activation_dispatch_handoff as native_fixture
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner


@pytest.fixture
def originals(tmp_path, monkeypatch):
    original_fixture = native_fixture.result_fixture

    def full_metadata(purpose):
        first, second, raw = original_fixture(purpose)
        if purpose == "probe":
            raw["native_receipt"]["modes"] = [
                asdict(NativeCameraMode(5472, 3648, 8, 1))
            ]
        return first, second, raw

    monkeypatch.setattr(native_fixture, "result_fixture", full_metadata)
    monkeypatch.setattr(
        context_fixture,
        "BUDGET",
        CameraCampaignBudget(5000, 1, 5472 * 3648 * 2, 5472 * 3648 * 2),
    )
    c = make_context(tmp_path, monkeypatch)
    path = "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).resolve().parents[3] / path, target)
    binding = dict(
        **{key: "a" * 64 for key in HASH_FIELDS},
        cell_id=c.session.descriptor()["cell_id"],
        session_id=c.session.descriptor()["session_id"],
        origin_launch_id="wizard-" + "3" * 32,
        entry_launch_id="wizard-" + "4" * 32,
    )
    entry = build_camera_mode_entry(
        entry_id="cameramode-" + "9" * 32,
        binding=binding,
        operator_id="MODELED entry",
        recorded_at_utc_ns=123,
    )
    c.modeled_workflow["camera_mode_entry"] = dict(
        entry=dict(document=entry.to_dict(), evidence_sha256=entry.sha256)
    )
    c.proposal = build_camera_operating_proposal(
        proposal_id="modepolicy-" + "1" * 32,
        operator_id="MODELED proposal",
        recorded_at_utc_ns=456,
        rationale="Read actual stored modeled probe evidence.",
        variance_rationale="Model the 8-fps exception without approving it.",
        entry_payload=entry.payload,
        expected_entry_id=entry.to_dict()["entry_id"],
        expected_entry_binding=binding,
        purchase_profile_payload=target.read_bytes(),
        expected_purchase_profile_sha256=digest(target.read_bytes()),
        configuration_payload=c.settings.payload,
        expected_settings_epoch=c.settings.settings_epoch,
    )
    return c


def assess(c, *, keys=(), mutate=None):
    with c.session._store.transaction(LEASES) as tx:
        original = configuration_scope.read_camera_configuration_originals(
            c.read_setup(tx), tx, **c.arguments
        )
        before = tx.snapshot()
        if mutate:
            mutate(original, tx)
        result = module.assess_original_operating_proposal(
            original,
            tx,
            proposal_payload=c.proposal.payload,
            expected_proposal_sha256=c.proposal.sha256,
            capture_request_keys=keys,
        )
        assert tx.snapshot() == before
        return result


@WINDOWS
def test_actual_saved_probe_is_read_without_approving_missing_captures(originals):
    report = assess(originals)
    assert report["schema"] == "rocell.camera_original_operating_assessment.v3"
    projection = report["stage_requirements"]
    assert [row["id"] for row in projection["requirements"]] == report[
        "unresolved_checks"
    ]
    assert projection["failed_metadata_checks"] == report["preflight"]["failed_checks"]
    assert projection["stage_passed"] is False
    assert report["original_inputs_authenticated_at_read"] is True
    assert report["preflight"]["status"] == "BLOCKED_METADATA"
    assert "TWO_CAPTURE_REPORTS_PRESENT" in report["preflight"]["failed_checks"]
    assert report["captures"] == []
    assert (
        report["approved_operating_policy"]
        is report["original_stage_record_retained"]
        is False
    )
    assert report["physical_authority"] is report["connected"] is False
    assert "PIXEL_FILES_NOT_VERIFIED" in report["unresolved_checks"]
    assert (
        "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED"
        not in report["unresolved_checks"]
    )


@WINDOWS
@pytest.mark.parametrize(
    "keys", [("missing-original-request",), ("same", "same"), ("a", "b", "c")]
)
def test_absent_or_duplicate_original_capture_requests_are_not_substituted(
    originals, keys
):
    with pytest.raises(ValueError, match="OPERATING_"):
        assess(originals, keys=keys)


@WINDOWS
@pytest.mark.parametrize("fault", ["cancel", "proposal", "entry", "records", "outcome"])
def test_original_read_failure_never_produces_an_assessment(
    originals, monkeypatch, fault
):
    def mutate(original, tx):
        if fault == "cancel":
            original._setup._cancellation.set()
        elif fault == "proposal":
            monkeypatch.setattr(
                originals,
                "proposal",
                type(originals.proposal)(
                    originals.proposal.payload.replace(b"Read actual", b"Fake actual")
                ),
            )
        elif fault == "entry":
            originals.modeled_workflow["camera_mode_entry"]["entry"][
                "evidence_sha256"
            ] = ("f" * 64)
            object.__setattr__(
                original._setup, "_workflow", canonical(originals.modeled_workflow)
            )
        elif fault == "records":
            previous = original._read_current_records
            calls = []

            def changed(*args):
                rows = previous(*args)
                calls.append(True)
                if len(calls) > 1:
                    rows["MODELED-late-change"] = {}
                return rows

            monkeypatch.setattr(
                type(original),
                "_read_current_records",
                lambda self, *args: changed(*args),
            )
        else:
            monkeypatch.setattr(
                tx,
                "read_campaign_result",
                lambda *a: (_ for _ in ()).throw(
                    ValueError("MODELED missing terminal original")
                ),
            )

    # A rationale-only edit is a different valid proposal, so explicitly corrupt
    # a binding-bearing hash for this case rather than relying on signature claims.
    if fault == "proposal":
        monkeypatch.setattr(
            originals,
            "proposal",
            type(originals.proposal)(
                originals.proposal.payload.replace(
                    originals.settings.settings_epoch.encode(), b"f" * 64
                )
            ),
        )
        mutate = None
    with pytest.raises(ValueError):
        assess(originals, mutate=mutate)


def test_serialized_or_forged_owner_is_not_accepted():
    with pytest.raises(ValueError, match="EXACT_ORIGINAL_OWNER"):
        module.assess_original_operating_proposal(
            {},
            {},
            proposal_payload=b"{}",
            expected_proposal_sha256="a" * 64,
            capture_request_keys=(),
        )


@WINDOWS
def test_service_reads_originals_and_releases_both_locks(originals, monkeypatch):
    from rocell.application import camera_operating_assessment_service as service

    c = originals
    # Same explicitly modeled full-setup seam; all new service, original probe,
    # configuration and assessment logic runs normally against the real M1 store.
    monkeypatch.setattr(service, "read_camera_probe_originals", c.read_setup)
    # Public current-context previews now select the checksum-bearing profile;
    # this read-only assessment still does not create a capture or stage record.
    c.capture_plan = c.service.preview_activation_plan(
        "capture",
        c.enrollment,
        capture_budget=CameraCampaignBudget(**c.capture_plan["native_budget"]),
        configuration_verification=True,
        sealed_configuration_capture=True,
    )
    context = dict(
        original_setup=dict(
            expected_header_sha256=c.values["expected_header_sha256"],
            expected_preparation_sha256="1" * 64,
            expected_review_sha256="2" * 64,
        ),
        intent=dict(capture_budget=c.capture_plan["native_budget"]),
        expected_capture_plan_sha256=digest(canonical(c.capture_plan)),
    )
    report = service.run_original_operating_assessment(
        c.service,
        c.session,
        c.enrollment,
        context=context,
        proposal_payload=c.proposal.payload,
        expected_proposal_sha256=c.proposal.sha256,
        capture_request_keys=(),
        request_key="MODELED-original-assessment",
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 240_000_000_000,
        validate_current_context=lambda: None,
        progress=lambda _: None,
    )
    assert (
        report["original_inputs_authenticated_at_read"]
        and not report["approved_operating_policy"]
    )
    for lock in (c.service._dispatch_lock, c.session._operation_lock):
        assert lock.acquire(False)
        lock.release()


@WINDOWS
def test_two_actual_saved_capture_requests_and_settings_are_joined(
    tmp_path, monkeypatch
):
    from test_camera_original_configuration_service import run_capture
    from test_camera_activation_dispatch_handoff import install_owner
    from test_camera_operating_pixels import packet_for
    from rocell.application.camera_operating_pixels import (
        logged_pixel_reference,
        verify_operating_capture_pixels,
    )
    from rocell.application.camera_configuration_wizard_contract import (
        CAPTURE_ACTION_ID,
    )

    c = make_context(tmp_path, monkeypatch)
    install_owner(tmp_path, monkeypatch, purpose="capture", pixels=True)
    keys = ("operation-" + "6" * 32, "operation-" + "7" * 32)
    packets = {}
    for index, key in enumerate(keys):
        result = run_capture(c, request_key=key)
        packets[key] = packet_for(result, operation=key)
        c.service.validate_observation_publication(CAPTURE_ACTION_ID, result)
        c.service.publish_retained_observation("operation-" + str(index + 3) * 32)
    with c.session._store.transaction(LEASES) as tx:
        original = configuration_scope.read_camera_configuration_originals(
            c.read_setup(tx), tx, **c.arguments
        )
        records = original._read_current_records(tx, original._request, tx.snapshot())
        captures, selected, checksums = module._capture_subjects(
            original, tx, records, keys
        )
        assert checksums == {}  # Legacy capture checksums remain launch-only.
        assert [row["request_key"] for row in selected] == list(keys)
        assert len({row["attempt_id"] for row in selected}) == 2
        assert all(
            json.loads(capture.readback_payload)["status"]
            == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
            for capture in captures
        )
        # Real M1 capture subjects joined to exact modeled-launch completions;
        # both original pixel files are read, never captured again or rewritten.
        before = tx.snapshot()
        for capture, row in zip(captures, selected):
            key = row["request_key"]
            reference = logged_pixel_reference(
                packets[key],
                request_key=key,
                source_sha256=c.service.source_sha256,
                session_id=c.service.session_id,
            )
            assert reference is not None
            checked = verify_operating_capture_pixels(
                capture.native,
                reference=reference,
                request_key=key,
                assigned_parent=Path(
                    json.loads(original._plan)["assigned_parent_directory"]
                ),
                settings_epoch=c.settings.settings_epoch,
                cancelled=lambda: False,
            )
            assert checked["status"] == "VERIFIED_AT_READ"
            assert checked["verified_bytes"] == 16 and not checked["physical_authority"]
        assert tx.snapshot() == before
        facts = tx.read_campaign_admission_evidence

        def altered(attempt):
            value = facts(attempt)
            value["hazard_assessment"]["settings"]["settings_epoch"] = "f" * 64
            return value

        monkeypatch.setattr(tx, "read_campaign_admission_evidence", altered)
        with pytest.raises(ValueError, match="OPERATING_ORIGINAL_CAPTURE_SETTINGS"):
            module._capture_subjects(original, tx, records, keys[:1])
