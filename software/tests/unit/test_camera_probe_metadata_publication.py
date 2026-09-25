"""Actual Arrival metadata actions with incapable OS-shaped fixture providers.

Proves the current-owner receipt comes from successful logged actions, not from
reading/restoring a retained snapshot. No real metadata API or device is used.
"""

import pytest

from test_wizard_native_camera_integration import (
    setup,
    discover,
    resolve_review,
    action,
)


def test_current_probe_metadata_is_published_only_after_logged_review(setup):
    app, provider, _ = setup("physical")
    assert app._probe_metadata_current() is False
    selected = discover(app)
    assert app._probe_metadata_current() is False
    completed = resolve_review(app, selected)
    assert completed["completion_log_persisted"] is True
    assert app._probe_metadata_current() is True
    assert len(app._probe_metadata_publication["operations"]) == 4
    assert provider.calls == ["inventory", "identity"]
    assert app.view()["camera"]["status"] == "NOT_CONNECTED"
    # A changed current owner cannot be repaired by retaining the old report.
    app._native_camera.invalidate_review("MODELED_CURRENTNESS_CHANGE")
    assert app._probe_metadata_current() is False


@pytest.mark.parametrize(
    "fault",
    [
        "missing-log",
        "failed-result",
        "changed-action",
        "missing-operation",
        "missing-receipt",
        "source-change",
        "log-error",
    ],
)
def test_current_metadata_requires_all_production_publication_boundaries(setup, fault):
    app, provider, _ = setup("physical")
    resolve_review(app, discover(app))
    assert app._probe_metadata_current()
    op = next(iter(app._probe_metadata_publication["operations"]))
    if fault == "missing-log":
        app._operations[op]["completion_log_persisted"] = False
    elif fault == "failed-result":
        app._operations[op]["status"] = "FAILED"
    elif fault == "changed-action":
        app._operations[op]["action_id"] = "rehearse_device_inventory"
    elif fault == "missing-operation":
        del app._operations[op]
    elif fault == "missing-receipt":
        app._probe_metadata_publication = None
    elif fault == "source-change":
        app._source_changed = True
    else:
        app._log_error = dict(code="MODELED_LOG_FAILURE")
    assert not app._probe_metadata_current()
    assert provider.calls == ["inventory", "identity"]


def test_failed_review_completion_never_publishes_current_owner(setup, monkeypatch):
    app, provider, _ = setup("physical")
    selected = discover(app)
    assert (
        action(app, "native_camera_identity", choice_id=selected, metadata_only=True)[
            "status"
        ]
        == "SUCCEEDED"
    )
    append = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda kind, data: False if kind == "ACTION_FINISHED" else append(kind, data),
    )
    result = action(
        app,
        "native_camera_review",
        choice_id=selected,
        reviewer_id="test-reviewer",
        metadata_only=True,
    )
    assert result["status"] == "FAILED"
    assert app._probe_metadata_publication is None
    assert not app._probe_metadata_current()
