"""Public tickets/log/export with real source codecs and modeled M1 ownership.

The original requirement/source files are real; source identity, isolation,
ownership experiment and durable-store observations are explicit fixtures. No
native helper, device, M1 initialization or ownership child is executed here.
"""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from rocell.application import arrival_wizard_service as arrival_module
from rocell.application.physical_configuration_epochs import (
    build_physical_configuration_epochs,
)
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_intake_evidence_service import (
    PhysicalIntakeEvidenceService,
)
from rocell.application.wizard_diagnostic_export import (
    verify_export,
    sanitize_diagnostic_record,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_arrival_wizard_service import make_service, _run  # noqa: F401
from test_arrival_wizard_intake_evidence import worker
from test_physical_camera_intake_setup import setup_flow  # noqa: F401
from test_physical_camera_intake_session import intake_model, read  # noqa: F401
from test_physical_camera_session_readback import model, workspace  # noqa: F401
from test_physical_source_qualification_readback import source_model, RAW  # noqa: F401
from test_physical_source_qualification_service import modeled, values  # noqa: F401
from test_physical_camera_prerequisites import held_preflight
from test_wizard_physical_camera_setup_ui import modeled_storage
from test_wizard_workspace_source_ui import render_snapshot


@pytest.fixture
def composed(modeled, make_service, monkeypatch):
    qualification, state = modeled
    setup = qualification.setup
    # Fix only construction's current launch identity to the original fixture;
    # all subsequent ticket/operation/qualification IDs remain genuinely unique.
    with monkeypatch.context() as patch:
        patch.setattr(
            arrival_module,
            "uuid",
            SimpleNamespace(uuid4=lambda: uuid.UUID(setup.launch_id[7:])),
        )
        arrival, runner, source = make_service(mode="physical")
    arrival._source_qualification = qualification
    arrival._physical_camera_setup = setup
    arrival._physical_camera = setup._acquisition
    arrival._physical_intake_evidence = PhysicalIntakeEvidenceService(setup)
    arrival._physical_intake_evidence.observe_setup()

    # Retain the actual pure epoch artifact in the modeled original inventory.
    # This is a source-stage boundary record, not observed hardware bindings.
    prerequisites = setup.current_prerequisite_artifact()
    original = state["snapshot"]()
    states = [v2.V2StageState.WAITING_OPERATOR, *([v2.V2StageState.PENDING] * 14)]
    prefix = replace(
        original,
        stages=tuple(
            v2.V2StageSnapshot(row.stage, states[i], 0 if i == 0 else None, ())
            for i, row in enumerate(original.stages)
        ),
        committed_events=original.committed_events[:1],
        evidence=tuple(
            ref
            for ref in original.evidence
            if ref.payload_sha256 == prerequisites.evidence_sha256
        ),
        head=v2.V2CommittedHead.build(original.header, original.committed_events[:1]),
        next_action=v2._derive_next_action(states),
    )
    epochs = build_physical_configuration_epochs(prerequisites, prefix)
    state["add"](epochs.payload, label="physical-configuration-epochs-v1")
    setup._adopt_source_workflow(read(setup.session, state["header"].header_sha256))

    # Complete the fixture's deliberately minimal verification JSON using the
    # existing strict typed M1 view model, preserving every actual fixture hash.
    old_verification = state["store"].verification
    verification_template = modeled_storage(setup.session)["session"]["verification"]

    def verification(session):
        report = old_verification(session)
        original = report.to_dict()
        full = deepcopy(verification_template)
        full["session"].update(original["session"])
        full["challenge_sha256"] = original["challenge_sha256"]
        report.to_dict = lambda: deepcopy(full)
        return report

    state["store"].verification = verification
    setup.session.refresh(
        cancellation=SimpleNamespace(is_set=lambda: False), progress=lambda _: None
    )
    setup._publication = {
        "status": "CURRENT",
        "operation_id": "modeled-original-publication",
    }
    qualification.observe_setup()
    return arrival, qualification, state, runner, source


def public(arrival, action, values=None):
    completed = _run(arrival, action, values)
    assert completed["status"] == "SUCCEEDED", completed
    return completed


@pytest.mark.parametrize("observed", [False, True])
def test_real_codec_public_chain_and_complete_reserved_export(
    composed, monkeypatch, observed
):
    arrival, qualification, state, runner, source = composed
    import subprocess
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

    before_payloads = dict(state["payloads"])
    with monkeypatch.context() as guard:

        def denied(*args, **kwargs):
            pytest.fail(
                "public file-only qualification attempted device/process execution"
            )

        guard.setattr(subprocess, "Popen", denied)
        for method in (
            "probe",
            "capture",
            "enumerate_metadata",
            "resolve_identity_metadata",
        ):
            guard.setattr(WindowsCameraWorkerClient, method, denied)
        public(arrival, "physical_source_isolation_files_discover")
        supplied = values()
        if observed:
            (qualification.inbox.root / "modeled.txt").write_bytes(RAW)
            public(arrival, "physical_source_isolation_files_discover")
            supplied.update(
                isolation_state="OBSERVED_DISCONNECTED",
                isolation_statement="Modeled isolation only; NOT received installation evidence.",
                isolation_choice=qualification.inbox.choices()[0]["value"],
            )
        public(arrival, "physical_source_qualify", supplied)
        public(
            arrival,
            "physical_source_qualification_review",
            {"reviewer_id": "source-reviewer", "file_only": True},
        )
        if observed:
            public(arrival, "physical_static_contract_begin", {"file_only": True})

        # Existing full source-preflight and setup result attachments coexist
        # with the new reserved exports. This strict held preflight is explicitly
        # modeled unavailable data, not a new host/source check or stage PASS.
        for identifier, report in (
            ("operation-modeled-preflight", json.loads(held_preflight().payload)),
            (
                "operation-modeled-setup",
                arrival._physical_camera_setup.retained_diagnostics(),
            ),
        ):
            result = worker(identifier, report)
            if identifier.endswith("setup"):
                result["steps"][0]["report"]["prerequisite_document"] = result["steps"][
                    0
                ]["report"]["prerequisites"].pop("document")
            arrival._full_results[identifier] = sanitize_diagnostic_record(
                result, maximum_bytes=1024 * 1024
            )
        retained = qualification.retained_diagnostics()
        assert (
            sanitize_diagnostic_record(retained, maximum_bytes=1024 * 1024) == retained
        )
        assert all(
            state["payloads"][key] == value for key, value in before_payloads.items()
        )
        exported = public(arrival, "export_logs")
        directory = Path(exported["result"]["receipt"]["path"])
        verify_export(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        report = json.loads((directory / "report.json").read_text())
        attachments = list(directory.glob("attachment-*.json"))
        assert len(attachments) <= 8
        saved = json.loads(
            (directory / "attachment-source-qualification-data.json").read_text()
        )
        assert saved["original_bytes_preserved"] is True
        for key, value in retained.items():
            if key not in {"schema", "meaning"}:
                assert saved[key] == value, key
        for name in ("configuration-records", "workspace-source-workflow"):
            data = json.loads(
                (directory / ("attachment-" + name + ".json")).read_text()
            )
            assert data["original_bytes_preserved"] is True
        names = {path.name for path in attachments}
        assert "attachment-result-modeled-preflight.json" in names
        assert "attachment-result-modeled-setup.json" in names
        assert {
            "source-qualification-data.json",
            "configuration-records.json",
            "workspace-source-workflow.json",
        } <= set(report["snapshot"]["result_export_policy"]["dedicated_attachments"])
        print(
            json.dumps(
                {
                    "observed_fixture": observed,
                    "attachment_count": len(attachments),
                    "attachment_bytes": sum(
                        path.stat().st_size for path in attachments
                    ),
                    "qualification_bytes": (
                        directory / "attachment-source-qualification-data.json"
                    )
                    .stat()
                    .st_size,
                    "snapshot_bytes": len(
                        json.dumps(
                            report["snapshot"],
                            ensure_ascii=True,
                            sort_keys=True,
                            indent=2,
                        ).encode()
                    ),
                    "omitted_generic_count": len(
                        report["snapshot"]["result_export_policy"]["omitted"]
                    ),
                }
            )
        )
        assert "MODELED isolation" not in json.dumps(manifest)
        assert RAW.decode().strip() not in json.dumps(saved)
        assert report["snapshot"]["source_reassessment"]["qualification"][
            "verdict"
        ] == ("PASS" if observed else "BLOCKED")

    # Only now release the process-denial seam for the real JavaScript fake DOM.
    # The same cached public snapshot reaches both renderers; no service action.
    snapshot = arrival.view()
    for text in render_snapshot(snapshot):
        assert "SOURCE_REASSESSMENT_NOT_VERIFIED" not in text
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "Stage 1 accepted only" in text if observed else "BLOCKED" in text
        assert (
            "no camera runtime release" in text
            if observed
            else "No isolation statement recorded." in text
        )
    assert not runner.calls
