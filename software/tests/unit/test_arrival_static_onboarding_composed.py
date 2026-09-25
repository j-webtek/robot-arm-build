"""Public static-design chain using real services/codecs and modeled M1 scopes.

Controlled design files are real. Isolation, ownership and original-store
durability are explicit fixtures, not received hardware or a native run.
"""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from rocell.application import physical_static_camera_onboarding_service as module
from rocell.application import physical_static_contract as codec
from rocell.application.wizard_diagnostic_export import (
    verify_export,
    sanitize_diagnostic_record,
)
from test_arrival_source_qualification_composed import (
    composed,
    public,
    make_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    RAW,
    values,
)
from test_wizard_workspace_source_ui import render_snapshot
from rocell.ui.terminal import _StaticCameraOnboardingDisplay
from rocell.providers.windows.native_camera_protocol import canonical, digest

WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture
def static_composed(composed, monkeypatch):
    arrival, source, state, runner, fingerprint = composed
    service = module.PhysicalStaticCameraOnboardingService(source.setup)
    arrival._static_camera_onboarding = service
    service.observe_setup()
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(codec, "source_fingerprint", lambda _: state["source"])
    calls = []

    def collect(workspace, **kwargs):
        assert not arrival._lock._is_owned()
        receipt = codec.collect_static_camera_contract(WORKSPACE, **kwargs)
        calls.append(receipt)
        return receipt

    monkeypatch.setattr(module, "collect_static_camera_contract", collect)
    previous = state["store"].stage_transaction

    @contextmanager
    def transaction(*args, **kwargs):
        with previous(*args, **kwargs) as tx:
            tx.store_evidence = lambda stage, payload, **kw: state["add"](
                payload, label=kw["label"], stage=stage, media=kw["media_type"]
            )
            yield tx

    state["store"].stage_transaction = transaction
    return arrival, source, service, state, runner, calls


@pytest.mark.parametrize("cycles", [1, 8])
def test_public_real_services_original_design_export_and_render(
    static_composed, monkeypatch, cycles
):
    arrival, source, service, state, runner, calls = static_composed
    before = dict(state["payloads"])
    views = []
    with monkeypatch.context() as guard:
        guard.setattr(
            subprocess,
            "Popen",
            lambda *a, **k: pytest.fail("unexpected process/device run"),
        )
        source.inbox.root.mkdir(parents=True, exist_ok=True)
        (source.inbox.root / "modeled-isolation.txt").write_bytes(RAW)
        public(arrival, "physical_source_isolation_files_discover")
        for index in range(cycles):
            supplied = values()
            if index == cycles - 1:
                supplied.update(
                    isolation_state="OBSERVED_DISCONNECTED",
                    isolation_statement="MODELED isolation only; not a received installation observation.",
                    isolation_choice=source.inbox.choices()[0]["value"],
                )
            public(arrival, "physical_source_qualify", supplied)
            public(
                arrival,
                "physical_source_qualification_review",
                {"file_only": True, "reviewer_id": "source-reviewer"},
            )
        public(arrival, "physical_static_contract_begin", {"file_only": True})
        public(
            arrival,
            "physical_static_contract_collect",
            {"operator_id": "static-operator", "file_only": True},
        )
        views.append(deepcopy(arrival.view()))
        public(
            arrival,
            "physical_static_contract_review",
            {"reviewer_id": "static-reviewer", "file_only": True},
        )
        views.append(deepcopy(arrival.view()))
        assert service.view()["stage_states"]["camera_receipt"] == "PENDING"
        public(arrival, "physical_camera_receipt_begin", {"file_only": True})
        views.append(deepcopy(arrival.view()))
        assert len(calls) == 1
        assert not runner.calls
        assert all(state["payloads"][key] == payload for key, payload in before.items())
        full = service.retained_diagnostics()
        assert sanitize_diagnostic_record(full, maximum_bytes=1024 * 1024) == full
        exported = public(arrival, "export_logs")
        directory = Path(exported["result"]["receipt"]["path"])
        verify_export(directory)
        saved = json.loads(
            (directory / "attachment-source-qualification-data.json").read_text()
        )
        assert saved["schema"] == "rocell.wizard_source_qualification_export.v2"
        assert saved["original_bytes_preserved"] is True
        assert saved["source_qualification_original_bytes_preserved"] is True
        static = saved["static_camera_onboarding"]
        assert static["original_bytes_preserved"] is True
        assert static["publication"]["status"] == "CURRENT"
        for key, value in full.items():
            assert static[key] == value, key

        def restored(packet, key):
            document = deepcopy(packet[key])
            for nested in ("software_receipt", "ownership_report"):
                reference = nested + "_document_key"
                if reference in document:
                    document[nested] = restored(packet, document.pop(reference))
            return document

        original = source.setup.original_source_workflow()
        assert len(saved["qualification_cycles"]) == cycles
        for retained, actual in zip(
            saved["qualification_cycles"], original["qualification_cycles"], strict=True
        ):
            for role in ("receipt", "assessment", "review"):
                record = retained[role]
                document = restored(saved, record["document_key"])
                assert document == actual[role]["document"]
                assert digest(canonical(document)) == record["evidence_sha256"]
        for role in ("receipt", "assessment", "review"):
            record = static["static_contract"][role]
            document = restored(static, record["document_key"])
            assert document == original["static_contract"][role]["document"]
            assert digest(canonical(document)) == record["evidence_sha256"]
        assert len(list(directory.glob("attachment-*.json"))) <= 8
        assert RAW.decode().strip() not in json.dumps(saved)
        print(
            json.dumps(
                {
                    "qualification_cycles": cycles,
                    "combined_attachment_bytes": (
                        directory / "attachment-source-qualification-data.json"
                    )
                    .stat()
                    .st_size,
                    "attachments": len(list(directory.glob("attachment-*.json"))),
                }
            )
        )

    # Real JS in a fake DOM; one GET only. Terminal uses a cached view only.
    for index, view in enumerate(views):
        projection = view["static_camera_onboarding"]
        assert _StaticCameraOnboardingDisplay.projection(projection, view) == projection
        for text in render_snapshot(view):
            for error in (
                "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED",
                "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED",
                "SOURCE_REASSESSMENT_NOT_VERIFIED",
            ):
                assert error not in text
            assert "Published and nominal design values" in text
            assert "NOT MEASURED" in text
            assert "DESIGN_NOT_MEASURED" in text
            assert (
                "not authenticated independent people" in text
                if index
                else "exact-subject review is still required" in text
            )
            assert ("Stage 2 design accepted only" in text) == (index > 0)
            if index == 2:
                assert "remains WAITING_OPERATOR" in text
    assert all(service.view()[flag] is False for flag in module._FLAGS)


def test_real_cached_service_before_source_admission_is_not_a_design_subject(
    static_composed,
):
    arrival, source, service, state, runner, calls = static_composed
    before = dict(state["payloads"])
    snapshot = arrival.view()
    value = snapshot["static_camera_onboarding"]
    assert value["publication"]["status"] == "CURRENT"
    assert value["status"] == "NOT_STARTED" and value["contract"] is None
    assert value["stage_states"]["workspace_sources"] == "BLOCKED"
    assert _StaticCameraOnboardingDisplay.projection(value, snapshot) == value
    for text in render_snapshot(snapshot):
        assert "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED" not in text
        assert "No complete static contract is published" in text
        assert "Stage 2 design accepted only" not in text
    service.invalidate()
    held = arrival.view()
    assert held["static_camera_onboarding"]["status"] == "NOT_STARTED"
    for text in render_snapshot(held):
        assert "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED" not in text
        assert "Historical design subject only" in text
    assert state["payloads"] == before and not calls and not runner.calls
