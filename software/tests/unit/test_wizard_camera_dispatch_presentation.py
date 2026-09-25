"""Existing browser wording/publication, not a device or M1 admission test.

The late-failure cases reuse actual Arrival completion and publication code,
real tiny YUY2/PNG ingestion, and explicitly modeled native receipts. The Node
fake DOM exercises the production app with cached snapshots only; it is not an
actual browser or production C++ acquisition test.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
from threading import Event

import pytest

from rocell.application.wizard_actions import WizardError
from test_arrival_wizard_device_selection_ui import _HARNESS, MetadataService, selection
from test_arrival_wizard_service import make_service  # noqa: F401
from test_physical_camera_capture_publication import (
    accepted_capture,
    finish_modeled_observation,
    installed,  # noqa: F401
)
from test_wizard_physical_camera_ui import physical, snapshot


WORKSPACE = Path(__file__).resolve().parents[3]


def browser_snapshots(snapshots, page):
    """GET-only scripted polls; fail on an image, prepare, execute, or retry."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime unavailable")
    harness = (
        _HARNESS.replace(
            "global.fetch=async(path,options)=>{",
            "let viewReads=0;global.fetch=async(path,options)=>{",
        )
        .replace(
            "if(path==='/api/view')return{ok:true,json:async()=>input.snapshot};",
            "if(path==='/api/view')return{ok:true,json:async()=>input.snapshots[viewReads++]};"
            "throw new Error('Only cached view GET is allowed: '+path);",
        )
        .replace(
            "if(input.prepare){",
            "for(let i=1;i<input.snapshots.length;i++)await find('#refresh-button').onclick();"
            "if(input.prepare){",
        )
        .replace(
            "JSON.stringify({requests,text:",
            "JSON.stringify({imageCount:nodes.filter(node=>node.tagName==='IMG').length,requests,text:",
        )
    )
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": (
                    WORKSPACE / "software/src/rocell/ui/static/app.js"
                ).read_text(encoding="utf-8"),
                "snapshots": snapshots,
                "page": page,
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "Local service connected", parsed["error"]
    assert parsed["error"] == "", parsed["error"]
    assert parsed["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None}
    ] * len(snapshots)
    assert parsed["dialogOpen"] is False and parsed["imageCount"] == 0
    return parsed["text"]


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_camera_service_selection_and_finite_image_are_separate_claims(mode):
    view = snapshot(physical())
    view["mode"] = mode
    view["device_selection"] = selection(review="CAMERA")
    original = deepcopy(view)
    text = browser_snapshots([view, view], "camera")
    assert "Retained camera image" in text
    assert "cached image, not a live connection" in text
    assert "Service-reported camera state & settings" in text
    assert "Local service connected means this page can reach the application" in text
    assert "not that a camera is connected" in text
    assert (
        "Reviewed endpoint metadata, settings intent/readback and a finite last capture"
        in text
    )
    assert "NOT_CONNECTED / NOT_QUALIFIED" in text
    assert "Last captured frame — NOT LIVE" in text
    assert "No separately verified physical frame has been published" in text
    assert view == original


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_general_arm_connection_is_separate_from_gated_physical_diagnostics(
    mode,
):
    view = MetadataService(selection(review="SERIAL")).view()
    view["mode"] = mode
    original = deepcopy(view)
    text = browser_snapshots([view, view], "arm")
    assert (
        "Controller metadata, rehearsal and separately gated physical diagnostics"
        in text
    )
    assert "Local service connected is not an arm connection" in text
    assert "General Connect and motion remain held" in text
    assert "Rehearsal actions use incapable adapters" in text
    assert "only after their own current setup, identity and confirmation gates" in text
    assert "Even a zero-write read may reset the controller" in text
    assert "not instructions to power or connect the arm now" in text
    assert "No initialization, retry or reconnect is automatic" in text
    assert "Preview one bounded feedback campaign before approving it" not in text
    assert view == original


def test_source_file_check_does_not_invent_disconnected_physical_state():
    from test_arrival_wizard_source_preflight_ui import projection, snapshot, summary

    value = projection("FILE_CHECKS_COHERENT")
    value["summary"] = summary()
    text = browser_snapshots([snapshot(value)], "overview")
    assert "No device connection is established by this file-only check" in text
    assert "physical connection and power state remain unverified" in text
    assert "Hardware remains disconnected" not in text


@pytest.mark.parametrize("fault", ["stop", "source", "log"])
def test_actual_late_publication_holds_render_without_capture_or_replay(
    installed, monkeypatch, fault
):
    from test_physical_camera_capture_publication import no_process_or_devices

    # The imported guard denies native/process/session calls while exercising
    # the isolated file/data/publication join. It is lifted only for Node's
    # fake-DOM process after all application snapshots have been collected.
    with monkeypatch.context() as guard:
        no_process_or_devices.__wrapped__(guard)
        arrival, owner, _, _, evidence, _, ingest, runner, source = accepted_capture(
            installed
        )
        pending = arrival.view()
        assert pending["physical_camera"]["publication"]["status"] == "PENDING"
        if fault == "log":
            append = arrival._log.append

            def fail(name, details):
                if name == "ACTION_FINISHED":
                    raise OSError("Isolated UI publication completion-log failure")
                return append(name, details)

            guard.setattr(arrival._log, "append", fail)
        operation_id, result = finish_modeled_observation(arrival, owner)
        cancellation = Event()
        if fault == "stop":
            cancellation.set()
        elif fault == "source":
            source["hash"] = "f" * 64
        with pytest.raises((ValueError, WizardError)):
            arrival._publish_physical_camera_observation(
                operation_id, result, cancellation=cancellation
            )
        retained = deepcopy(owner.retained_capture_diagnostics())
        operation_ids = tuple(arrival._operations)
        snapshots = [pending, arrival.view(), arrival.view()]
        assert tuple(arrival._operations) == operation_ids
        assert owner.retained_capture_diagnostics() == retained
        assert not runner.calls
        encoded = json.dumps(retained, sort_keys=True)
        assert evidence.evidence_sha256 in encoded and ingest.envelope_sha256 in encoded
        for view in snapshots:
            assert view["camera"]["image_id"] is None
            assert view["physical_camera"]["last_frame"] is None
            assert view["physical_camera"]["connected"] is False
        assert (
            snapshots[-1]["physical_camera"]["publication"]["status"]
            == "HISTORICAL_HELD"
        )
    text = browser_snapshots(snapshots, "camera")
    assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in text
    assert "CONTENT_VERIFIED: retained pixel bytes" not in text
    assert "No separately verified physical frame has been published" in text
    assert "no automatic retries, reconnects or arm power actions" in text
    assert "Local service connected means this page can reach the application" in text
