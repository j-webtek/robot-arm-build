"""Independent public draft/export tests with explicitly modeled M1 readiness.

The prerequisite document/model/export are actual implementations. Upstream
original-store publication and source fingerprint are fixtures; no volume/M1
qualification, camera/serial access or received-hardware observation is made.
Source checking before export is an observation, not a hostile-writer lock.
"""

import hashlib
import json
from pathlib import Path
import threading
import time

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application.physical_camera_prerequisites import (
    collect_physical_camera_prerequisites,
)
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.wizard_diagnostic_export import verify_export
from test_physical_intake_service import (
    FIELDS,
    SOURCE,
    ready,
    make_service,
    workspace,
    no_devices_or_storage_runtime,
    start,
    notebook_result,
    _run,
)


def exported_notebook(service, artifact):
    outcome = _run(service, "export_logs")
    assert outcome["status"] == "SUCCEEDED", outcome
    directory = Path(outcome["result"]["receipt"]["path"])
    assert verify_export(directory)["valid"] is True
    wrapper = json.loads(
        (directory / "attachment-physical-intake-notebook.json").read_bytes()
    )
    view = wrapper["notebook"]
    snapshot = {key: value for key, value in view.items() if key != "snapshot_sha256"}
    payload = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    restored = PhysicalIntakeNotebook.from_payload(
        payload, prerequisites=artifact, expected_sha256=view["snapshot_sha256"]
    )
    assert restored.view() == view
    report = json.loads((directory / "report.json").read_bytes())["snapshot"]
    return wrapper, report, restored, directory


@pytest.mark.parametrize("failure", ["drift", "source-read-failed"])
def test_direct_export_observes_source_failure_but_retains_original(
    ready, monkeypatch, failure
):
    service, runner, source, artifact = ready
    start(ready)
    recorded = _run(service, "physical_intake_record", FIELDS)
    expected = notebook_result(recorded)
    assert service.view()["physical_intake"]["status"] == "CURRENT_DRAFT"
    assert service._source_changed is False
    if failure == "drift":
        source["hash"] = "f" * 64
    else:

        def unavailable(*args, **kwargs):
            raise OSError("modeled source read unavailable")

        monkeypatch.setattr(arrival, "source_fingerprint", unavailable)
    # No intervening non-housekeeping action or explicit invalidation.
    wrapper, report, restored, _ = exported_notebook(service, artifact)
    assert wrapper["status"] == "HISTORICAL_HELD"
    assert wrapper["notebook"] == expected
    assert report["physical_intake"]["status"] == "HISTORICAL_HELD"
    assert report["physical_intake"]["notebook"] is None
    assert report["physical_camera_setup"]["prerequisites"] is None
    assert service._source_changed is True
    assert service._physical_intake.payload == restored.payload
    assert restored.to_dict()["binding"]["source_sha256"] == SOURCE
    assert not runner.calls
    # The held source does not prevent a later explicit diagnostic export either.
    second, _, again, _ = exported_notebook(service, artifact)
    assert second["status"] == "HISTORICAL_HELD" and again.payload == restored.payload


def test_draft_binds_original_reopened_origin_and_current_application_launch(
    ready, workspace
):
    service, runner, _, _ = ready
    origin = "wizard-" + "d" * 32
    canonical = json.dumps(
        {"launch": origin, "source": SOURCE}, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    lineage = hashlib.sha256(canonical).hexdigest()
    original_session = PhysicalCameraSession(
        service.workspace,
        service.workspace / "software/runs/physical-camera-acquisition" / origin,
        launch_id=origin,
        source_sha256=SOURCE,
        cell_id="wizard-physical-camera-" + lineage[:16],
        session_id="physical-camera-" + lineage[16:48],
    )
    binding = original_session.descriptor()
    artifact = collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=binding["session_id"],
        launch_session_id=origin,
        cancellation=threading.Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )
    # Explicitly modeled successful original M1 readback, not an actual reopening.
    setup = service._physical_camera_setup
    setup.session = original_session
    setup._prerequisites = artifact.safe_summary()
    setup._retained = {
        "document": artifact.to_dict(),
        "evidence_sha256": artifact.evidence_sha256,
        "retention": "M1_FULL_BYTES_READ_BACK",
        "reference": None,
    }
    before = setup.view()
    outcome = _run(service, "physical_intake_start")
    assert outcome["status"] == "SUCCEEDED", outcome
    notebook = service.view()["physical_intake"]["notebook"]
    assert notebook["binding"] == {
        "source_sha256": SOURCE,
        "session_id": binding["session_id"],
        "origin_launch_id": origin,
        "launch_session_id": service.session_id,
        "prerequisites_sha256": artifact.evidence_sha256,
    }
    assert origin != service.session_id
    assert setup.view() == before  # no stage writes or adoption performed by notebook
    wrapper, _, restored, _ = exported_notebook(service, artifact)
    assert wrapper["status"] == "CURRENT_DRAFT" and restored.view() == notebook
    assert not runner.calls


def test_all_sixteen_maximum_ascii_narratives_export_without_truncation(ready):
    service, runner, _, artifact = ready
    blank = start(ready)
    for row in blank["rows"]:
        outcome = _run(
            service,
            "physical_intake_record",
            {
                "record_id": row["record_id"],
                "observation_status": "UNKNOWN",
                "observed_value": "x" * 256,
                "method": "m" * 512,
                "evidence_note": "e" * 1024,
                "operator_id": "o" * 64,
            },
        )
        assert outcome["status"] == "SUCCEEDED", outcome
    expected = service._physical_intake
    assert expected is not None
    assert expected.to_dict()["coverage"] == {
        "total": 16,
        "observed": 0,
        "unknown": 16,
        "unrecorded": 0,
    }
    wrapper, report, restored, directory = exported_notebook(service, artifact)
    assert wrapper["status"] == "CURRENT_DRAFT"
    assert restored.payload == expected.payload
    assert len(restored.payload) <= 64 * 1024
    assert report["physical_intake"]["notebook"] == expected.view()
    assert report["result_export_policy"]["included_full_results"] == 7
    assert len(list(directory.glob("attachment-*.json"))) == 8
    assert all(
        len(row["observation"]["evidence_note"]) == 1024
        for row in restored.to_dict()["rows"]
    )
    assert not runner.calls
