"""Script orchestration doubles only: no M1, package, process or hardware I/O."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture
def smoke(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "owned_arm_smoke_export_under_test",
        SCRIPTS / "wizard_arm_setup_rehearsal_smoke.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_owned_success_attempts_once_without_automatic_export(smoke, monkeypatch):
    service = object()
    calls = []
    monkeypatch.setattr(
        smoke, "action", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    monkeypatch.setattr(
        smoke, "export", lambda *_: pytest.fail("Success must not auto-export here")
    )

    assert smoke.run_owned_feedback(service) is None
    assert calls == [
        ((service, "rehearsal_owned_arm_feedback_campaign"), {"scenario": "nominal"})
    ]


@pytest.mark.parametrize("export_fails", [False, True])
def test_owned_failure_exports_once_without_retry_and_preserves_original_exception(
    smoke, monkeypatch, capsys, export_fails
):
    service = object()
    campaign_error = RuntimeError("Original admission rejection; no replay")
    export_error = OSError("PRIVATE_EXPORT_PATH_MUST_NOT_BE_PRINTED")
    calls = []

    def action(*args, **kwargs):
        calls.append(("action", args, kwargs))
        raise campaign_error

    def export(selected):
        calls.append(("export", selected))
        if export_fails:
            raise export_error

    monkeypatch.setattr(smoke, "action", action)
    monkeypatch.setattr(smoke, "export", export)
    with pytest.raises(RuntimeError) as failure:
        smoke.run_owned_feedback(service)
    assert failure.value is campaign_error
    assert calls == [
        (
            "action",
            (service, "rehearsal_owned_arm_feedback_campaign"),
            {"scenario": "nominal"},
        ),
        ("export", service),
    ]
    printed = capsys.readouterr().out
    assert "PRIVATE_EXPORT_PATH_MUST_NOT_BE_PRINTED" not in printed
    if export_fails:
        assert "Failure diagnostics export also failed: OSError" in printed
    else:
        assert printed == ""


@pytest.mark.parametrize("serve", [False, True])
def test_reference_completion_verifies_original_store_but_pending_browser_does_not(
    smoke, monkeypatch, tmp_path, serve
):
    """Control-flow coverage only; the guarded verifier has separate real tests."""
    source = "a" * 64
    session_id = "original-reference-session"
    calls = []
    initial = {
        "session_id": session_id,
        "stage": "reference_frame_calibration",
        "stage_state": "WAITING_OPERATOR",
        "reference_evaluation": {"outcome": "REHEARSAL_CHECKS_PASSED"},
        "attempt_event_count": 15,
    }

    class Service:
        source_sha256 = source

        def __init__(self, name):
            self.name = name
            self.current = deepcopy(initial)
            self.closed = False

        def view(self):
            return {
                "commissioning_rehearsal": deepcopy(self.current),
                "stages": [{"state": "PHYSICAL_PENDING"} for _ in range(15)],
            }

        def shutdown(self):
            self.closed = True
            calls.append(("shutdown", self.name))

    original = Service("original")
    reopened = [Service("receipt-reopened"), Service("review-reopened")]
    remaining = iter(reopened)

    def construct(workspace):
        assert workspace == tmp_path
        return next(remaining)

    def action(service, action_id, **values):
        calls.append(("action", service.name, action_id, values))
        if action_id == "rehearsal_assess":
            service.current.update(
                stage_state="REVIEW_PENDING", assessment={"outcome": "PASS"}
            )
        else:
            assert action_id == "rehearsal_collect"

    def reopen(service, before):
        service.current = deepcopy(before)
        calls.append(("reopen", service.name, before["session_id"]))

    def review(service, reviewer):
        calls.append(("review", service.name, reviewer))
        service.current.update(
            stage="noncontact_acceptance",
            stages=[{"state": "PASS"} for _ in range(13)],
        )

    def verify(workspace, selected, *, reference):
        assert all(item.closed for item in [original, *reopened])
        calls.append(("verify", workspace, selected, reference))

    monkeypatch.setattr(smoke, "ArrivalWizardService", construct)
    monkeypatch.setattr(smoke, "action", action)
    monkeypatch.setattr(smoke, "reopen_original", reopen)
    monkeypatch.setattr(smoke, "review", review)
    monkeypatch.setattr(smoke, "verify_completed", verify)
    monkeypatch.setattr(
        smoke, "export", lambda service: calls.append(("export", service.name))
    )

    class Server:
        launch_url = "http://127.0.0.1:1/fake-script-test"

    def create_server(service):
        assert service is reopened[-1]
        calls.append(("create_server", service.name))
        return Server()

    monkeypatch.setattr(smoke, "create_wizard_server", create_server)
    monkeypatch.setattr(smoke, "run_wizard_server", lambda _: calls.append(("serve",)))
    smoke.run_reference_stage(tmp_path, source, original, serve=serve)

    assert all(item.closed for item in [original, *reopened])
    assert [row for row in calls if row[0] == "reopen"] == [
        ("reopen", "receipt-reopened", session_id),
        ("reopen", "review-reopened", session_id),
    ]
    if serve:
        assert not any(row[0] in {"review", "verify"} for row in calls)
        assert calls[-2:] == [("serve",), ("shutdown", "review-reopened")]
    else:
        assert calls[-2:] == [
            ("shutdown", "review-reopened"),
            ("verify", tmp_path, session_id, True),
        ]
        assert len([row for row in calls if row[0] == "review"]) == 1
        assert not any(row[0] in {"serve", "create_server"} for row in calls)
