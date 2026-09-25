"""Source-excluded script checks, not full M1 or physical qualification."""

from contextlib import nullcontext
from copy import deepcopy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter,
    verify_export,
)
from test_rehearsal_noncontact_stage import actual  # noqa: F401

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SOURCE = "a" * 64


@pytest.fixture
def scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return SimpleNamespace(
        nc=importlib.import_module("wizard_noncontact_smoke"),
        base=importlib.import_module("wizard_arm_setup_rehearsal_smoke"),
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--noncontact"],
        ["--noncontact", "--serve", "--expected-source-sha256", SOURCE],
        [
            "--noncontact",
            "--verify-completed",
            "prior",
            "--expected-source-sha256",
            SOURCE,
        ],
    ],
)
def test_closed_cli_refuses_before_any_application_creation(scripts, monkeypatch, args):
    monkeypatch.setattr(
        scripts.base,
        "ArrivalWizardService",
        lambda *_: pytest.fail("Application created"),
    )
    with pytest.raises(SystemExit) as error:
        scripts.base.main(args)
    assert error.value.code == 2


def test_source_mismatch_precedes_initial_storage(scripts, monkeypatch):
    monkeypatch.setattr(scripts.nc, "source_fingerprint", lambda _: "b" * 64)
    monkeypatch.setattr(
        scripts.base,
        "ArrivalWizardService",
        lambda *_: pytest.fail("Application created"),
    )
    with pytest.raises(RuntimeError, match="Frozen source mismatch"):
        scripts.base.main(["--noncontact", "--expected-source-sha256", SOURCE])


@pytest.mark.parametrize(
    "name",
    ["physical_camera_probe", "native_camera_inventory", "arm_connect", "execute_task"],
)
def test_action_set_rejects_physical_or_inventory_before_preparation(scripts, name):
    with pytest.raises(RuntimeError, match="closed rehearsal"):
        scripts.nc.action(object(), name)


def test_actual_replay_guards_hold_camera_feedback_fit_fk_and_assessors(scripts):
    from rocell.application import rehearsal_noncontact_stage as nc
    from rocell.application import virtual_session
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
    from rocell.geometry.urdf import UrdfModel
    from rocell.calibration import rigid_correspondence

    original = nc.evaluate_rehearsal_noncontact_stage
    with scripts.nc.replay_guards():
        for callable_ in (
            nc.evaluate_rehearsal_noncontact_stage,
            nc.assess_current_collision_readiness,
            nc.assess_target_accuracy_budget,
            virtual_session.run_default_virtual_session,
            WindowsCameraWorkerClient.capture,
            WindowsCameraWorkerClient.enumerate_metadata,
            ArmFeedbackWorker.run,
            UrdfModel.forward_kinematics,
            rigid_correspondence.fit_rigid_correspondence,
        ):
            with pytest.raises(AssertionError, match="attempted"):
                callable_()
    assert nc.evaluate_rehearsal_noncontact_stage is original


def initial():
    return {
        "stage": "noncontact_acceptance",
        "stage_state": "PENDING",
        "session_id": "original-session",
        "cell_id": "original-cell",
        "directory": "C:/assigned/original-only",
        "journal_head_sha256": "b" * 64,
        "attempt_event_count": 15,
        "physical_authority": False,
        "stages": [{"state": "PASS"} for _ in range(13)]
        + [{"state": "PENDING"}, {"state": "PENDING"}],
        "noncontact_evaluation": None,
        "assessment": None,
    }


@pytest.mark.parametrize("fail_assessment", [False, True])
def test_four_distinct_launches_reopen_same_original_and_never_retry(
    scripts, monkeypatch, tmp_path, capsys, fail_assessment
):
    module = scripts.nc
    created, actions = [], []
    original = initial()
    projection = {
        "outcome": "BLOCKED",
        "physical_authority": False,
        "evaluation_sha256": "c" * 64,
        "checks": [{"check_kind": "NOMINAL", "passed": False} for _ in range(3)]
        + [{"check_kind": "EXPECTED_FAULT", "passed": True} for _ in range(5)],
    }

    class Service:
        source_sha256 = SOURCE

        def __init__(self, workspace):
            self.session_id = "new-launch-" + str(len(created))
            self.current = None
            self.notes = 0
            self.closed = False
            created.append(self)

        def view(self):
            return {
                "commissioning_rehearsal": deepcopy(self.current),
                "camera": {"image_id": None},
                "stages": [{"state": "PHYSICAL_PENDING"} for _ in range(15)],
            }

        def operation(self, operation_id):
            assert operation_id == "original-collect" and self.notes == 9
            return {"result": None}

        def shutdown(self):
            self.closed = True

    def reopen(service, before):
        assert before["session_id"] == original["session_id"]
        actions.extend(["rehearsal_discover", "rehearsal_reopen"])
        service.current = deepcopy(before)

    def action(service, name, **values):
        actions.append(name)
        assert name != "rehearsal_initialize"
        if name == "rehearsal_collect":
            state = "WAITING_OPERATOR"
            service.current["noncontact_evaluation"] = deepcopy(projection)
        elif name == "rehearsal_assess":
            if fail_assessment:
                raise RuntimeError("Exact original assessment failed")
            state = "REVIEW_PENDING"
            service.current["assessment"] = {
                "outcome": "BLOCKED",
                "reason_codes": ["a", "b", "c"],
            }
        elif name == "rehearsal_review":
            assert values == {
                "reviewer_id": "noncontact-independent-reviewer",
                "accept_assessment": True,
            }
            state = "BLOCKED"
            service.current["assessment"] = None
        else:
            assert name == "record_note"
            service.notes += 1
            return {}
        service.current["stage_state"] = state
        service.current["stages"][13]["state"] = state
        return {"operation_id": "original-collect"}

    def export(service, workspace, source, before, expected=None):
        actions.append("export_logs")
        full = {"original-fixture-receipt": True}
        assert expected is None or expected == full
        return full, {"fixture-export": len(actions)}

    monkeypatch.setattr(module, "require_frozen_source", lambda *_: None)
    monkeypatch.setattr(module, "ArrivalWizardService", Service)
    monkeypatch.setattr(module, "replay_guards", nullcontext)
    monkeypatch.setattr(module, "action", action)
    monkeypatch.setattr(module, "export_gap", export)
    monkeypatch.setattr(scripts.base, "reopen_original", reopen)
    if fail_assessment:
        with pytest.raises(RuntimeError, match="Exact original assessment failed"):
            module.run_noncontact_stage(tmp_path, SOURCE, original)
        assert len(created) == 2
        assert actions.count("rehearsal_assess") == 1
        assert actions.count("rehearsal_review") == 0
    else:
        module.run_noncontact_stage(tmp_path, SOURCE, original)
        assert len(created) == 4 and len(actions) == 25
        assert actions.count("rehearsal_collect") == 1
        assert actions.count("record_note") == 9
        assert actions.count("export_logs") == 5
        assert created[-1].current["stage_state"] == "BLOCKED"
        summary = json.loads(
            capsys.readouterr().out.split("verified original noncontact workflow ")[-1]
        )
        assert summary["stage14_actions"] == len(actions)
        assert summary["attempt_event_count"] == 15
    assert all(item.closed for item in created)
    assert original == initial()


@pytest.mark.parametrize("fault", [None, "altered-receipt", "historical"])
def test_actual_full_report_export_shape_hash_and_currentness(
    scripts, tmp_path, monkeypatch, actual, fault
):
    binding, evidence, _ = actual
    module = scripts.nc
    directory = tmp_path / "software/runs/wizard-exports"
    directory.parent.mkdir(parents=True)
    exporter = WizardDiagnosticExporter(directory)
    exporter.prepare(create=True)
    full = {
        "schema": "rocell.rehearsal_noncontact_receipt.v1",
        "stage": "noncontact_acceptance",
        "session_id": binding.session_id,
        "cell_id": binding.cell_id,
        "workspace_source_sha256": binding.workspace_source_sha256,
        "physical_observation": False,
        "evaluation": evidence.to_dict(),
        "evaluation_sha256": evidence.evidence_sha256,
    }
    wrapper = {
        "schema": "rocell.noncontact_diagnostic_export.v1",
        "publication": (
            "HISTORICAL_HELD" if fault == "historical" else "CURRENT_GAP_REPORT"
        ),
        "original_bytes_preserved": True,
        "receipt": full,
        "physical_authority": False,
    }
    receipt = exporter.export(
        {
            "session_id": "script-export-fixture",
            "mode": "rehearsal",
            "source_binding_sha256": binding.workspace_source_sha256,
            "source_identity": {"build": "pure-fixture"},
            "physical_authority": "NONE",
        },
        [],
        attachments={"noncontact-readiness.json": module.canonical(wrapper)},
    )
    monkeypatch.setattr(
        module, "action", lambda *args, **kwargs: {"result": {"receipt": receipt}}
    )
    before = {
        "session_id": binding.session_id,
        "cell_id": binding.cell_id,
        "noncontact_evaluation": {"evaluation_sha256": evidence.evidence_sha256},
    }
    expected = deepcopy(full)
    if fault == "altered-receipt":
        expected["evaluation"]["safe_summary"]["static_geometry"][
            "required_body_count"
        ] = 0
    if fault:
        with pytest.raises(RuntimeError):
            module.export_gap(
                object(), tmp_path, binding.workspace_source_sha256, before, expected
            )
    else:
        retained, checked = module.export_gap(
            object(), tmp_path, binding.workspace_source_sha256, before, expected
        )
        assert retained == full
        assert checked["files"] == 4
        assert checked["attachment_bytes"] > len(evidence.canonical_bytes())


class ActionServiceFixture:
    """Modeled public action state only; no coordinator, M1 or device execution."""

    def __init__(
        self,
        status="FAILED",
        export_status="SUCCEEDED",
        export_error=None,
        exporter=None,
    ):
        self.status = status
        self.export_status = export_status
        self.export_error = export_error
        self.exporter = exporter
        self.prepared = []
        self.executed = []
        self.closed = False
        self.receipt = {
            "path": "modeled-export",
            "valid": True,
            "status": "EXPORTED_DIAGNOSTICS",
        }
        self.original = self._operation(
            "original-operation",
            status,
            {
                "physical_authority": False,
                "retained_evidence_sha256": "b" * 64,
                "failure_code": "MODELED_TERMINAL_FAULT",
                "retry_allowed": False,
            },
        )

    @staticmethod
    def _operation(operation_id, status, result):
        return {
            "operation_id": operation_id,
            "status": status,
            "result_sha256": "c" * 64,
            "completion_log_persisted": True,
            "result": result,
        }

    def view(self):
        assert self.closed is False
        return {"revision": 7}

    def prepare_action(self, name, values, revision):
        assert self.closed is False and revision == 7
        self.prepared.append((name, values))
        if name == "export_logs" and self.export_error is not None:
            raise self.export_error
        return {"ticket_id": name}

    def execute_action(self, ticket_id):
        assert self.closed is False
        self.executed.append(ticket_id)
        if ticket_id == "export_logs" and self.exporter is not None:
            self.receipt = self.exporter.export(
                {
                    "session_id": "same-live-modeled-service",
                    "physical_authority": False,
                },
                [self.original],
                attachments={
                    "original-failure.json": json.dumps(self.original).encode("utf-8")
                },
            )
        return {
            "operation_id": (
                "export-operation"
                if ticket_id == "export_logs"
                else "original-operation"
            )
        }

    def operation(self, operation_id):
        assert self.closed is False
        if operation_id == "original-operation":
            return deepcopy(self.original)
        assert operation_id == "export-operation"
        return self._operation(
            operation_id,
            self.export_status,
            {"physical_authority": False, "receipt": self.receipt},
        )

    def shutdown(self):
        self.closed = True


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_terminal_failure_exports_once_same_live_service_before_original_raise(
    scripts, status, capsys
):
    service = ActionServiceFixture(status)
    try:
        with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
            scripts.nc.action(service, "rehearsal_collect", operator_id="operator")
        failure = caught.value
        assert failure.operation == service.original
        assert failure.failure_export_attempted is True
        assert failure.failure_export_operation["operation_id"] == "export-operation"
        assert failure.failure_export_error is None
        assert service.closed is False
        assert service.prepared == [
            ("rehearsal_collect", {"operator_id": "operator"}),
            ("export_logs", {}),
        ]
        assert service.executed == ["rehearsal_collect", "export_logs"]
        assert "modeled-export" in capsys.readouterr().out
    finally:
        service.shutdown()


@pytest.mark.parametrize("export_status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_failed_export_preserves_original_and_secondary_operation_without_recursion(
    scripts, export_status
):
    service = ActionServiceFixture("FAILED", export_status)
    with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
        scripts.nc.action(service, "rehearsal_collect")
    original = caught.value
    assert original.operation["operation_id"] == "original-operation"
    assert original.failure_export_attempted is True
    assert original.failure_export_operation["status"] == export_status
    assert isinstance(original.failure_export_error, scripts.nc.TerminalActionFailure)
    assert original.failure_export_error.failure_export_attempted is False
    assert service.executed == ["rehearsal_collect", "export_logs"]


def test_export_prepare_exception_still_counts_one_attempt_and_does_not_hide_original(
    scripts,
):
    denied = OSError("modeled export admission failure")
    service = ActionServiceFixture(export_error=denied)
    with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
        scripts.nc.action(service, "rehearsal_collect")
    assert caught.value.operation == service.original
    assert caught.value.failure_export_error is denied
    assert caught.value.failure_export_attempted is True
    assert caught.value.failure_export_operation is None
    assert [name for name, _ in service.prepared] == [
        "rehearsal_collect",
        "export_logs",
    ]
    assert service.executed == ["rehearsal_collect"]


def test_failed_explicit_export_is_not_recursively_exported(scripts):
    service = ActionServiceFixture(export_status="FAILED")
    with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
        scripts.nc.action(service, "export_logs")
    assert caught.value.failure_export_attempted is False
    assert service.executed == ["export_logs"]


def fast_poll_clock(monkeypatch, module):
    ticks = iter(range(0, 10000, 100))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)


def test_unknown_running_timeout_is_not_terminal_or_exportable_even_in_owned_wrapper(
    scripts, monkeypatch
):
    fast_poll_clock(monkeypatch, scripts.nc)
    service = ActionServiceFixture(status="RUNNING")
    monkeypatch.setattr(
        scripts.base,
        "export",
        lambda *_: pytest.fail("Unknown running outcome must not dispatch export"),
    )
    with pytest.raises(scripts.nc.ActionOutcomeUnknown) as caught:
        scripts.base.run_owned_feedback(service)
    assert caught.value.operation_id == "original-operation"
    assert caught.value.last_observed_operation["status"] == "RUNNING"
    assert caught.value.further_actions_prohibited is True
    assert service.executed == ["rehearsal_owned_arm_feedback_campaign"]


def test_unknown_export_outcome_retained_separately_without_replacing_terminal_failure(
    scripts, monkeypatch
):
    fast_poll_clock(monkeypatch, scripts.nc)
    service = ActionServiceFixture(export_status="RUNNING")
    with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
        scripts.nc.action(service, "rehearsal_collect")
    assert caught.value.operation["status"] == "FAILED"
    assert isinstance(
        caught.value.failure_export_error, scripts.nc.ActionOutcomeUnknown
    )
    assert caught.value.failure_export_error.operation_id == "export-operation"
    assert caught.value.failure_export_operation is None
    assert service.executed == ["rehearsal_collect", "export_logs"]


@pytest.mark.parametrize("export_status", ["SUCCEEDED", "FAILED"])
def test_legacy_owned_wrapper_does_not_add_second_export_after_tagged_attempt(
    scripts, monkeypatch, export_status
):
    service = ActionServiceFixture(export_status=export_status)
    monkeypatch.setattr(
        scripts.base, "export", lambda *_: pytest.fail("Duplicate legacy export")
    )
    with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
        scripts.base.run_owned_feedback(service)
    assert caught.value.failure_export_attempted is True
    assert service.executed == ["rehearsal_owned_arm_feedback_campaign", "export_logs"]


def test_terminal_failure_uses_actual_temp_exporter_preserving_original_record(
    scripts, tmp_path, capsys
):
    """Real bounded export; modeled terminal operation, not an M1/campaign replay."""
    exporter = WizardDiagnosticExporter(tmp_path / "exports")
    exporter.prepare(create=True)
    service = ActionServiceFixture(exporter=exporter)
    try:
        with pytest.raises(scripts.nc.TerminalActionFailure) as caught:
            scripts.nc.action(service, "rehearsal_collect")
        receipt = caught.value.failure_export_operation["result"]["receipt"]
        folder = Path(receipt["path"])
        assert verify_export(folder)["valid"] is True
        assert (
            json.loads((folder / "attachment-original-failure.json").read_bytes())
            == service.original
        )
        assert receipt["manifest_sha256"] == verify_export(folder)["manifest_sha256"]
        output = capsys.readouterr().out
        assert "failure diagnostic export retained" in output
        assert receipt["manifest_sha256"] in output
        assert "EXPORTED_DIAGNOSTICS" in output
        assert service.closed is False
    finally:
        service.shutdown()
