"""Explicit slow lane: real Arrival + original M1 + contained incapable child.

Only the assigned store/log/export roots are injected, not workers, reports,
coordinator decisions or persistence. Physical inventory and activation stay
forbidden. Source must be frozen while this multi-minute test runs.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import time
import uuid

import pytest

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_actions import WizardError


WORKSPACE = Path(__file__).resolve().parents[3]
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.name != "nt", reason="Qualified M1 and owned Job require Windows"
    ),
]


def action(service, name, **values):
    prepared = service.prepare_action(name, values, service.view()["revision"])
    dispatched = service.execute_action(prepared["ticket_id"])
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = service.operation(dispatched["operation_id"])
        if result["status"] not in {"QUEUED", "RUNNING"}:
            if result["status"] != "SUCCEEDED":
                # Public bounded diagnostics only; preserve the exact rejection
                # without pytest abbreviating the nested result or retrying it.
                pytest.fail(json.dumps(result, ensure_ascii=True, sort_keys=True))
            assert result["completion_log_persisted"] is True
            return result
        time.sleep(0.1)
    pytest.fail("Operation deadline exceeded; no replay is authorized")


def test_actual_public_owned_campaign_receipt_assessment_and_pass_reopen(
    tmp_path, monkeypatch
):
    from rocell.application import owned_arm_feedback_rehearsal_campaign as owned
    from rocell.application import physical_device_inventory as inventory
    from rocell.providers.windows.owned_arm_feedback_runner import (
        IncapableOwnedArmFeedbackRunner,
    )
    from test_wizard_owned_arm_feedback_ui import render, contains

    def forbidden(*args, **kwargs):
        pytest.fail("Physical enumeration or replay was attempted")

    for name in (
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
        "inventory_serial_ports_with_pyserial",
    ):
        monkeypatch.setattr(inventory, name, forbidden)
    launches = []
    source = None

    def launch():
        nonlocal source
        service = ArrivalWizardService(
            WORKSPACE,
            log_directory=tmp_path / "logs",
            export_directory=tmp_path / "exports",
        )
        # Server assignment of a real service/store, not a persistence double.
        service._commissioning = CommissioningRehearsalService(
            WORKSPACE,
            tmp_path / "stores" / ("wizard-" + uuid.uuid4().hex),
            source_sha256=service.source_sha256,
        )
        if source is None:
            source = service.source_sha256
        assert service.source_sha256 == source, "Do not migrate source-bound evidence"
        launches.append(service)
        return service

    def reopen_original(previous):
        before = previous.view()["commissioning_rehearsal"]
        previous.shutdown()
        fresh = launch()
        unused = Path(fresh.view()["commissioning_rehearsal"]["directory"])
        with monkeypatch.context() as guard:
            guard.setattr(owned, "prepare_owned_arm_feedback_campaign", forbidden)
            guard.setattr(
                owned.OwnedArmFeedbackRehearsalCampaign,
                "run_scoped_campaign",
                forbidden,
            )
            guard.setattr(IncapableOwnedArmFeedbackRunner, "run", forbidden)
            action(fresh, "rehearsal_discover")
            choice = next(
                row
                for row in fresh.view()["commissioning_rehearsal"]["discovery"][
                    "choices"
                ]
                if row["session_id"] == before["session_id"]
            )
            assert choice["source_matches"] is True
            action(fresh, "rehearsal_reopen", choice_id=choice["choice_id"])
        after = fresh.view()["commissioning_rehearsal"]
        for key in (
            "directory",
            "session_id",
            "cell_id",
            "stage",
            "stage_state",
            "journal_head_sha256",
            "assessment",
            "arm_feedback_evaluation",
            "arm_feedback_process",
        ):
            assert after[key] == before[key], key
        assert not unused.exists()
        assert all(row["state"] == "PHYSICAL_PENDING" for row in fresh.view()["stages"])
        return fresh

    def assess_review(service):
        action(service, "rehearsal_assess")
        assert (
            service.view()["commissioning_rehearsal"]["assessment"]["outcome"] == "PASS"
        )
        action(
            service,
            "rehearsal_review",
            reviewer_id="owned-reviewer",
            accept_assessment=True,
        )

    try:
        current = launch()
        action(current, "rehearsal_initialize")
        for index in range(11):
            if index == 6:
                current = reopen_original(current)  # Stay below per-launch action cap.
            assert (
                current.view()["commissioning_rehearsal"]["stage"]
                == STAGE_ORDER[index].value
            )
            action(current, "rehearsal_collect", operator_id="owned-operator")
            if index == 4:
                action(current, "rehearsal_camera_settings", brightness_offset=0)
            if index in (4, 5):
                action(
                    current, "rehearsal_camera_campaign", frame_count=1, fault="none"
                )
            assess_review(current)
        action(current, "rehearsal_collect", operator_id="owned-operator")
        before_events = current.view()["commissioning_rehearsal"]["attempt_event_count"]
        current = reopen_original(current)  # WAITING_OPERATOR with no campaign.
        completed = action(
            current, "rehearsal_owned_arm_feedback_campaign", scenario="nominal"
        )
        view = current.view()["commissioning_rehearsal"]
        assert view["attempt_event_count"] == before_events + 5
        assert view["arm_feedback_evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
        process = deepcopy(view["arm_feedback_process"])
        assert process["status"] == "COMPLETE_INCAPABLE_EVIDENCE"
        assert process["process"]["status"] == "SUCCEEDED"
        assert process["native"]["native_cleanup_confirmed"] is True
        for output in render(process):
            assert not contains(output, "ARM_PROCESS_NOT_VERIFIED")
            assert process["evidence_sha256"] in output
        receipt = deepcopy(current._commissioning._receipt)
        assert receipt["schema"] == "rocell.rehearsal_owned_feedback_receipt.v1"
        assert receipt["campaign_directory"] == str(
            Path(view["directory"]) / "owned-arm-feedback"
        )
        export_result = action(current, "export_logs")
        folder = Path(export_result["result"]["receipt"]["path"])
        assert folder.parent == tmp_path / "exports"
        assert verify_export(folder)["valid"] is True
        attachments = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in folder.glob("attachment-result-*.json")
        ]
        assert completed["result"] in attachments
        assert process["evidence_sha256"] in json.dumps(attachments)
        current = reopen_original(current)  # Exact receipt, no assessment yet.
        assert current._commissioning._receipt == receipt
        for name in (
            "rehearsal_arm_feedback_campaign",
            "rehearsal_owned_arm_feedback_campaign",
        ):
            with pytest.raises(WizardError):
                current.prepare_action(name, {}, current.view()["revision"])
        action(current, "rehearsal_assess")
        current = reopen_original(current)  # Pending assessment requires fresh review.
        assert (
            current.view()["commissioning_rehearsal"]["assessment"]["outcome"] == "PASS"
        )
        with pytest.raises(WizardError):
            current.prepare_action(
                "rehearsal_review",
                {"reviewer_id": "owned-operator", "accept_assessment": True},
                current.view()["revision"],
            )
        action(
            current,
            "rehearsal_review",
            reviewer_id="fresh-owned-reviewer",
            accept_assessment=True,
        )
        current = reopen_original(current)  # Passed original stage, still no replay.
        final = current.view()["commissioning_rehearsal"]
        assert [row["state"] for row in final["stages"][:12]] == ["PASS"] * 12
        assert final["stage"] == "reference_frame_calibration"
        assert final["arm_feedback_process"] == process
        assert not current._commissioning._store.snapshot(
            current._commissioning.session_id
        ).diagnostic_complete
    finally:
        for service in launches:
            service.shutdown()
