"""Setup serialization/publication using real codecs and modeled M1 scopes.

No inbox, native runtime, device, physical acceptance or NTFS qualification is
performed here; the independent session tests cover actual original storage.
"""

from copy import deepcopy
from pathlib import Path
import threading

import pytest

from rocell.application import physical_camera_setup_service as module
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_intake_session import (
    intake_model,
    complete,
    read,
    start,
    COLLECTION,
)
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_session import LAUNCH, SOURCE


@pytest.fixture
def setup_flow(intake_model, monkeypatch):
    owner, _, state = intake_model
    setup = module.PhysicalCameraSetupService(
        PhysicalCameraAcquisitionService(
            Path(owner.descriptor()["workspace"]),
            launch_id=LAUNCH,
            source_sha256=SOURCE,
            mode="physical",
        )
    )
    setup.session = owner  # Explicit modeled original-store selection.
    original = read(owner, state["header"].header_sha256)
    setup._adopt_source_workflow(original)
    setup._publication = {"status": "CURRENT", "operation_id": "original-read"}
    state["refresh_calls"] = 0
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])

    def refresh(**kwargs):
        state["refresh_calls"] += 1
        if state.get("refresh_error"):
            raise RuntimeError("Modeled late original-store audit failure")
        owner._store = state["store"]
        view = state["store"].verification(owner.descriptor()["session_id"])
        value = view.to_dict()
        if state.get("replacement_header"):
            value["session"]["header_sha256"] = "f" * 64
        owner._cached.update(
            status="REFRESHED_STORAGE_ONLY",
            verification=value,
            stages=[row.to_dict() for row in state["snapshot"]().stages],
        )
        if state.get("late_stop"):
            state["late_stop"].set()
        return owner.view()

    monkeypatch.setattr(owner, "refresh", refresh)
    return setup, intake_model, state


def scope(setup, state, cancellation=None):
    return setup.intake_transaction(
        cancellation=cancellation or threading.Event(),
        progress=lambda _: None,
        deadline_ns=state["now"] + 110_000_000_000,
    )


def test_inert_detached_accessor_and_exact_single_operation_scope(setup_flow):
    setup, data, state = setup_flow
    before = canonical(setup.original_source_workflow())
    counts = (state["reads"], state["enters"])
    copy = setup.original_source_workflow()
    copy["binding"]["source_sha256"] = "f" * 64
    assert canonical(setup.original_source_workflow()) == before
    assert (state["reads"], state["enters"]) == counts
    with scope(setup, state) as (prerequisites, workflow):
        assert prerequisites.evidence_sha256 == data[1].evidence_sha256
        assert canonical(workflow) == before
        assert setup.view()["publication"]["status"] == "HISTORICAL_HELD"
        with pytest.raises(WizardError, match="active"):
            with scope(setup, state):
                pytest.fail("concurrent setup operation entered")
        complete(data)
    assert state["refresh_calls"] == 1 and state["enters"] == counts[1] + 1
    assert setup.view()["publication"]["status"] == "PENDING"
    pending = setup.source_workflow_view()
    assert pending["schema"] == "rocell.wizard_workspace_source_workflow.v2"
    assert pending["status"] == "NOT_STARTED" and pending["supplementary"] is None
    assert pending["receipt"] is pending["assessment"] is pending["review"] is None
    setup.publication_completed("logged-intake")
    current = setup.source_workflow_view()
    assert current["status"] == "REVIEWED_BLOCKED"
    assert current["original_source_state"] == "BLOCKED"
    assert current["supplementary"] == {
        "collection_id": COLLECTION,
        "state": "REVIEW_PENDING",
    }
    assert current["review"] == setup._source_summaries["review"]


@pytest.mark.parametrize(
    "fault",
    [
        "pending-publication",
        "missing-review",
        "header",
        "head",
        "inventory",
        "source",
        "stop",
    ],
)
def test_scope_refuses_stale_or_unpublished_original_before_yield(setup_flow, fault):
    setup, _, state = setup_flow
    cancellation = threading.Event()
    if fault == "pending-publication":
        setup._publication["status"] = "PENDING"
    elif fault == "missing-review":
        setup._source_workflow["review"] = None
    elif fault in {"header", "head", "inventory"}:
        field = {
            "header": "session_header_sha256",
            "head": "session_head_sha256",
            "inventory": "evidence_inventory_sha256",
        }[fault]
        setup._source_workflow[field] = "f" * 64
    elif fault == "source":
        state["source"] = "f" * 64
    else:
        cancellation.set()
    counts = (state["enters"], state["reads"])
    with pytest.raises(WizardError):
        with scope(setup, state, cancellation):
            pytest.fail("invalid context yielded")
    assert (state["enters"], state["reads"]) == counts
    assert state["refresh_calls"] == 0
    assert not setup._operation_lock.locked()


@pytest.mark.parametrize(
    "fault", ["body", "refresh", "late-stop", "late-reader", "changed-owner"]
)
def test_failed_mutation_never_retries_or_republishes_and_keeps_predecessor(
    setup_flow, monkeypatch, fault
):
    setup, data, state = setup_flow
    original = setup.original_source_workflow()
    cancellation = threading.Event()
    if fault == "refresh":
        state["refresh_error"] = True
    if fault == "late-stop":
        state["late_stop"] = cancellation
    if fault == "late-reader":
        state["exit_failure"] = True
    with pytest.raises((WizardError, RuntimeError)):
        with scope(setup, state, cancellation):
            complete(data)
            if fault == "body":
                raise RuntimeError("Modeled partial write")
            if fault == "changed-owner":
                monkeypatch.setattr(
                    setup.session,
                    "descriptor",
                    lambda: {**original["binding"], "launch_id": "wizard-" + "f" * 32},
                )
    assert setup.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert setup.original_source_workflow() == original
    assert state["refresh_calls"] <= 1 and not setup._operation_lock.locked()
    setup.publication_completed("must-not-publish-failure")
    assert setup.view()["publication"]["status"] == "HISTORICAL_HELD"
    if fault == "late-reader":
        assert (
            setup.session.retained_source_workflow()["intake_collections"][0]["state"]
            == "REVIEW_PENDING"
        )


def test_normal_exit_reader_uses_independent_pre_yield_header(setup_flow, monkeypatch):
    setup, data, state = setup_flow
    expected = state["header"].header_sha256
    called = []

    def reader(**kwargs):
        called.append(kwargs["expected_header_sha256"])
        raise RuntimeError("Modeled refusal of replacement header")

    monkeypatch.setattr(setup.session, "read_original_source_workflow", reader)
    state["replacement_header"] = True
    with pytest.raises(RuntimeError):
        with scope(setup, state):
            complete(data)
    assert called == [expected]


def test_source_diagnostics_do_not_nest_full_intake_notebooks(setup_flow):
    setup, data, state = setup_flow
    with scope(setup, state):
        complete(data)
    setup.publication_completed("logged")
    original = setup.original_source_workflow()
    diagnostics = setup.retained_source_diagnostics()
    assert "intake_collections" not in diagnostics["original"]
    assert diagnostics["intake_collections_sha256"] == digest(
        canonical(original["intake_collections"])
    )
    assert diagnostics["intake_collections_summary"][0] == {
        "collection_id": COLLECTION,
        "state": "REVIEW_PENDING",
        "attachment_count": 1,
        "submission_sha256": original["intake_collections"][0]["submission"][
            "evidence_sha256"
        ],
        "assessment_sha256": original["intake_collections"][0]["assessment"][
            "evidence_sha256"
        ],
        "review_sha256": None,
    }
    assert b'"row_attachments"' not in canonical(diagnostics)
    assert setup.original_source_workflow() == original


def test_legacy_source_view_remains_exact_v1_until_supplement_exists(setup_flow):
    setup, _, _ = setup_flow
    result = setup.source_workflow_view()
    assert result["schema"] == "rocell.wizard_workspace_source_workflow.v1"
    assert result["status"] == "REVIEWED_BLOCKED"
    assert "supplementary" not in result and "original_source_state" not in result
