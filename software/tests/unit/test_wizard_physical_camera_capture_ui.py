"""Retained capture presentation only; no native/device or M1 operations.

Initial cases use the real physical configuration codecs with explicitly
modeled process/readback and frame facts. The workflow join additionally uses
real tiny YUY2/PNG bytes. Neither group qualifies hardware or authenticates M1.
"""

from copy import deepcopy
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from threading import Event, RLock
from time import monotonic_ns
from types import SimpleNamespace

import pytest
from PIL import Image

from rocell.ui.terminal import _PhysicalCameraDisplay, _TerminalWizard
from test_arrival_wizard_device_selection_ui import _HARNESS, browser as action_browser
from test_arrival_wizard_terminal import Service, action, dispatched, run
from test_wizard_physical_camera_ui import (
    actual_projection,
    browser_transport,
    frame,
    physical,
    render as _render,
    snapshot,
)


def render(projection):
    # The shared Node harness emits UTF-8, not Windows' default code page.
    original = subprocess.run

    def utf8(*args, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        return original(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "run", utf8)
        return _render(projection)


def content(projection, *, published=True):
    result = frame(deepcopy(projection), published=published)
    result["status"] = "CONTENT_VERIFIED"
    return result


def image_snapshot(projection):
    result = snapshot(projection)
    result["camera"] = {
        "image_id": projection["last_frame"]["image_id"],
        "image_provenance": "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2",
    }
    return result


def test_content_and_matched_settings_remain_separate_zero_authority_claims(
    actual_projection,
):
    data = content(actual_projection)
    original = deepcopy(data)
    assert _PhysicalCameraDisplay.physical(data) == data
    assert data["configuration"]["readback"]["frame_content_verified"] is False
    assert data["last_frame"]["frame_content_verified"] is True
    for output in render(data):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "CONTENT_VERIFIED: retained pixel bytes" in output
        assert "Last captured frame — NOT LIVE" in output
        assert "separately from settings readback" in output
        assert (
            "not a live feed, received-model qualification or canonical stage acceptance"
            in output
        )
        assert "not pixel or power proof" in output
        assert (
            "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in output
            or "UNKNOWN REQUIRES SEPARATE OBSERVATION" in output
        )
        assert data["last_frame"]["manifest_sha256"] in output
        assert data["configuration"]["candidate"]["settings_epoch"] in output
    assert data == original


@pytest.mark.parametrize("status", ["NOT_STARTED", "HELD"])
def test_original_initial_and_held_schema_remains_supported(status):
    data = physical()
    data["status"] = status
    assert _PhysicalCameraDisplay.physical(data) == data
    for output in render(data):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "No separately verified physical frame" in output


def test_staged_settings_are_intent_not_applied_or_captured(actual_projection):
    data = deepcopy(actual_projection)
    data.update(status="CONFIGURATION_STAGED", last_frame=None, plan=None)
    data["configuration"]["readback"] = None
    assert _PhysicalCameraDisplay.physical(data) == data
    for output in render(data):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "Immutable settings intent — NOT APPLIED" in output
        assert "No separately verified physical frame" in output
        assert "Retained settings readback — not pixel or power proof" not in output
        assert "Manual lens focus and aperture" in output
        assert data["configuration"]["candidate"]["settings_epoch"] in output


def test_actual_dynamic_configuration_fields_require_explicit_choice_and_actor(
    actual_projection,
):
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.application.wizard_actions import ACTION_BY_ID

    # Existing physical codecs provide real typed metadata. This receiver only
    # models an already-retained workflow to call the real cached field builder.
    owner = SimpleNamespace(
        _lock=RLock(),
        _capture_workflow=SimpleNamespace(
            view=lambda: {"configuration": deepcopy(actual_projection["configuration"])}
        ),
    )
    fields = list(PhysicalCameraAcquisitionService.configuration_fields(owner))
    definition = ACTION_BY_ID["physical_camera_configuration"]
    assert definition.mode == "physical"
    assert definition.worker == "physical_camera_configuration"
    by_name = {field["name"]: field for field in fields}
    assert "default" not in by_name["mode_choice_id"]
    assert "default" not in by_name["operator_id"]
    caps = actual_projection["configuration"]["capabilities"]
    assert [row["value"] for row in by_name["mode_choice_id"]["options"]] == [
        row["choice_id"] for row in caps["modes"] if row["selectable"]
    ]
    for control in caps["controls"]:
        cid = control["control_id"]
        assert by_name[cid + "_mode"]["default"] == "unchanged"
        value = by_name[cid + "_value"]
        assert (value["min"], value["max"], value["step"], value["default"]) == (
            control["minimum"],
            control["maximum"],
            control["step"],
            control["value"],
        )
    item = action(definition.action_id, fields=fields)
    item["section"] = "camera"
    view = snapshot(actual_projection)
    view["actions"] = [item]
    untouched = action_browser(
        None, "camera", snapshot=view, prepare=True, action=definition.action_id
    )
    assert all(row["method"] == "GET" for row in untouched["requests"])
    choices = [row for row in untouched["controls"] if row["tag"] == "SELECT"]
    mode = next(row for row in choices if row["id"].endswith("-mode_choice_id"))
    assert mode["value"] == ""
    values = {field["name"]: field["default"] for field in fields if "default" in field}
    values.update(
        mode_choice_id=by_name["mode_choice_id"]["options"][0]["value"],
        operator_id="settings_operator",
    )
    prepared = action_browser(
        None,
        "camera",
        snapshot=view,
        prepare=True,
        action=definition.action_id,
        values=values,
    )
    posts = [row for row in prepared["requests"] if row["method"] == "POST"]
    assert len(posts) == 1 and posts[0]["path"] == "/api/prepare"
    assert posts[0]["body"]["input"] == values
    service = Service([item])
    code, _, _ = run(
        service,
        [definition.action_id, values["mode_choice_id"]]
        + [""] * (len(fields) - 2)
        + ["settings_operator", "no", "quit"],
    )
    assert code == 0
    assert dispatched(service, "prepare") == [
        ("prepare", definition.action_id, values, 7)
    ]
    assert dispatched(service, "execute") == []


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("process_status", "FAILED", "CAPTURE_CAMPAIGN_NOT_SUCCESSFUL"),
        ("process_cleanup_confirmed", False, "PROCESS_CLEANUP_UNCONFIRMED"),
        ("native_status", "FAILED", "NATIVE_CAPTURE_FAILED"),
        ("native_cleanup_confirmed", False, "NATIVE_CLEANUP_UNCONFIRMED"),
        ("mode_matched", False, "MODE_READBACK_MISMATCH"),
    ],
)
def test_valid_mismatch_readback_cannot_claim_content_verified(
    actual_projection, field, value, reason
):
    data = content(actual_projection, published=False)
    readback = data["configuration"]["readback"]
    readback.update(status="READBACK_MISMATCH_UNQUALIFIED", reasons=[reason])
    readback[field] = value
    held = deepcopy(data)
    held["status"] = "HELD"
    assert _PhysicalCameraDisplay.physical(held) == held
    assert _PhysicalCameraDisplay.physical(data) is None
    for output in render(data):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" in output
        assert "CONTENT_VERIFIED: retained pixel bytes" not in output


@pytest.mark.parametrize(
    "path,value",
    [
        (("last_frame",), None),
        (("last_frame", "frame_content_verified"), False),
        (("last_frame", "live"), True),
        (("last_frame", "frame_index"), 32),
        (("last_frame", "frame_index"), True),
        (("last_frame", "settings_epoch"), "9" * 64),
        (("last_frame", "capture_evidence_sha256"), "9" * 64),
        (("last_frame", "endpoint_sha256"), "9" * 64),
        (("last_frame", "attempt_id"), "another-attempt"),
        (("configuration", "readback"), None),
        (("connected",), True),
        (("physical_authority",), True),
        (("hardware_qualified",), True),
        (("configuration", "candidate", "applied"), True),
    ],
)
def test_content_requires_exact_retained_frame_and_no_promoted_authority(
    actual_projection, path, value
):
    data = content(actual_projection)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert _PhysicalCameraDisplay.physical(data) is None
    for output in render(data):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" in output


@pytest.mark.parametrize("publication", ["CURRENT", "PENDING", "HISTORICAL_HELD"])
def test_only_exact_current_cached_image_is_fetched(actual_projection, publication):
    data = content(actual_projection)
    data["publication"]["status"] = publication
    if publication != "CURRENT":
        data["last_frame"]["image_id"] = None
    view = image_snapshot(data)
    result = browser_transport(view)
    assert result["status"] == "Local service connected", result["error"]
    assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in result["text"]
    assert all(row["method"] == "GET" for row in result["requests"])
    images = [
        row for row in result["requests"] if row["path"].startswith("/api/images/")
    ]
    assert len(images) == (1 if publication == "CURRENT" else 0)
    assert result["dialogOpen"] is False


def test_terminal_capture_card_is_cached_only(actual_projection, monkeypatch):
    data = content(actual_projection)
    output = []
    wizard = _TerminalWizard(
        Service([]), lambda _: "quit", output.append, lambda _: None
    )

    def forbidden(*_a, **_k):
        pytest.fail("Capture presentation attempted file/process access")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "read_text", "read_bytes"):
            guard.setattr(Path, name, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        wizard.show_physical_camera(data)
    assert any("CONTENT_VERIFIED" in str(line) for line in output)


def browser_retained_png(view, png):
    """The real app consumes only these in-memory retained PNG response bytes."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime unavailable")
    harness = _HARNESS.replace(
        "throw new Error('Unexpected request: '+path);",
        "if(path===input.image_path)return{ok:true,blob:async()=>new Blob([Buffer.from(input.png_base64,'base64')],{type:'image/png'})};"
        "throw new Error('Unexpected request: '+path);",
    )
    path = Path(__file__).resolve().parents[3] / "software/src/rocell/ui/static/app.js"
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": path.read_text(encoding="utf-8"),
                "snapshot": view,
                "page": "camera",
                "image_path": "/api/images/" + view["camera"]["image_id"],
                "png_base64": base64.b64encode(png).decode("ascii"),
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("frame_count", [1, 2])
def test_actual_tiny_yuy2_workflow_adapter_publication_and_both_renderers(
    tmp_path, monkeypatch, frame_count
):
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from test_physical_camera_capture_workflow import workflow_fixture

    def forbidden(*_a, **_k):
        pytest.fail("Retained-data UI join attempted a process or native/device call")

    with monkeypatch.context() as guard:
        guard.setattr(subprocess, "Popen", forbidden)
        for name in (
            "enumerate_metadata",
            "resolve_identity_metadata",
            "probe",
            "capture",
        ):
            guard.setattr(WindowsCameraWorkerClient, name, forbidden)
        f = workflow_fixture(tmp_path, guard, count=frame_count, accepted=False)
        owner = PhysicalCameraAcquisitionService(
            f.args[0],
            launch_id="wizard-" + "d" * 32,
            source_sha256=f.kwargs["source_sha256"],
            mode="physical",
        )
        # Model the trusted handoff of already retained probe/settings context.
        # These exact typed records were produced by the real workflow fixture;
        # no physical dispatcher, original M1 store or authenticated admission
        # is being asserted by installing them into this isolated test adapter.
        owner.directory = f.args[1]
        owner.cell_id = f.kwargs["cell_id"]
        owner.session_id = f.kwargs["session_id"]
        owner.probe_runtime = f.kwargs["probe_runtime"]
        owner.capture_runtime = f.kwargs["capture_runtime"]
        owner._capture_workflow = f.workflow
        owner._view["reviewed_endpoint"] = f.kwargs["selection"].safe_summary()
        owner._view["runtimes"] = {
            "probe": owner._runtime_view(owner.probe_runtime),
            "capture": owner._runtime_view(owner.capture_runtime),
        }
        owner._workflow_projection()
        owner._view["publication"] = {
            "status": "CURRENT",
            "operation_id": "operation-" + "1" * 32,
        }
        staged = owner.view()
        ingest = owner.stage_retained_capture(
            f.capture_evidence,
            expected_preparation=f.capture,
            expected_evidence_sha256=f.capture_evidence.evidence_sha256,
            expected_settings_epoch=f.configuration.settings_epoch,
            cancellation=Event(),
            deadline_ns=monotonic_ns() + 30_000_000_000,
        )
        assert ingest is not None and ingest.verification.content_verified
        assert ingest.domain == "PHYSICAL_UNVERIFIED" and not ingest.m1_qualified
        pending = owner.view()
        result = owner.pending_observation_result("physical_camera_capture")
        owner.validate_observation_publication("physical_camera_capture", result)
        assert owner.view() == pending
        owner.publish_retained_observation("operation-" + "2" * 32)
        no_image_id = owner.view()
        assert no_image_id["last_frame"]["image_id"] is None
        image_id = "image-" + "3" * 32
        png = owner.cache_published_preview(image_id)
        assert png is not None
        current = owner.view()
        original_diagnostics = owner.retained_capture_diagnostics()
        owner.invalidate()
        historical = owner.view()
        assert owner.retained_capture_diagnostics() == original_diagnostics

    assert staged["status"] == "CONFIGURATION_STAGED"
    assert staged["session_id"] == f.kwargs["session_id"] != owner.launch_id
    assert staged["configuration"]["readback"] is None and staged["last_frame"] is None
    assert pending["publication"]["status"] == "PENDING"
    assert (
        pending["configuration"]["readback"] is None and pending["last_frame"] is None
    )
    assert current["status"] == "CONTENT_VERIFIED"
    assert current["configuration"]["readback"]["frame_content_verified"] is False
    record = current["last_frame"]
    assert record["frame_content_verified"] is True and record["live"] is False
    assert record["frame_index"] == frame_count - 1
    assert record["native_frame_sha256"] == hashlib.sha256(f.pixels).hexdigest()
    assert record["preview_sha256"] == hashlib.sha256(png).hexdigest()
    with Image.open(io.BytesIO(png)) as image:
        assert image.size == (4, 2) and image.getpixel((0, 0)) == (0, 0, 0)
    assert historical["publication"]["status"] == "HISTORICAL_HELD"
    assert historical["last_frame"] is None
    for projection in (staged, pending, no_image_id, current, historical):
        original = deepcopy(projection)
        assert _PhysicalCameraDisplay.physical(projection) == projection
        for output in render(projection):
            assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
            assert "NOT_CONNECTED / NOT_QUALIFIED" in output
            if projection["status"] == "CONTENT_VERIFIED":
                assert "CONTENT_VERIFIED: retained pixel bytes" in output
                assert record["preview_sha256"] in output
                assert record["capture_evidence_sha256"] in output
            assert f.kwargs["selection"].binding.symbolic_link not in output
        assert projection == original
    page = browser_retained_png(image_snapshot(current), png)
    assert page["status"] == "Local service connected", page["error"]
    assert page["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None},
        {"path": "/api/images/" + image_id, "method": "GET", "body": None},
    ]
    assert page["dialogOpen"] is False and "LAST CAPTURED · NOT LIVE" in page["text"]
    output = Path(f.capture.camera_plan.request.output_directory)
    assert all(
        (output / row["filename"]).read_bytes() == f.pixels for row in f.raw["frames"]
    )


def test_actual_pending_probe_is_held_readable_without_early_capabilities(
    tmp_path, monkeypatch
):
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from test_physical_camera_acquisition_service import SOURCE, reviewed_enrollment
    from test_physical_camera_capture_publication import pending_probe

    def forbidden(*_a, **_k):
        pytest.fail("Pending-probe presentation attempted process/device or file I/O")

    with monkeypatch.context() as guard:
        guard.setattr(subprocess, "Popen", forbidden)
        for name in (
            "enumerate_metadata",
            "resolve_identity_metadata",
            "probe",
            "capture",
        ):
            guard.setattr(WindowsCameraWorkerClient, name, forbidden)
        launch = "wizard-" + "4" * 32
        owner = PhysicalCameraAcquisitionService(
            tmp_path, launch_id=launch, source_sha256=SOURCE, mode="physical"
        )
        # Actual typed producer/adapter; the probe observations and admission
        # subject are explicit models. No probe, M1 or native runner executes.
        pending_probe(owner, reviewed_enrollment(launch))
        with guard.context() as cached:
            for name in ("open", "stat", "read_text", "read_bytes"):
                cached.setattr(Path, name, forbidden)
            projection = owner.view()
    original = deepcopy(projection)
    assert projection["status"] == "HELD"
    assert projection["publication"] == {"status": "PENDING", "operation_id": None}
    assert projection["configuration"] == {
        "capabilities": None,
        "candidate": None,
        "readback": None,
    }
    assert projection["last_frame"] is None
    assert _PhysicalCameraDisplay.physical(projection) == projection
    for output in render(projection):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "No retained native capability observation" in output
        assert "No separately verified physical frame" in output
        assert "CONTENT_VERIFIED: retained pixel bytes" not in output
    assert projection == original and not owner.directory.exists()


def test_new_image_id_never_displays_prior_cached_object_url(actual_projection):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime unavailable")
    first = image_snapshot(content(actual_projection))
    second = deepcopy(first)
    second["revision"] += 1
    second["physical_camera"]["last_frame"]["image_id"] = "next-retained-image"
    second["camera"]["image_id"] = "next-retained-image"
    # Two snapshots and a deliberately delayed memory image response. Neither
    # Blob is a physical image, and no real service or acquisition is involved.
    harness = (
        _HARNESS.replace(
            "global.fetch=async(path,options)=>{",
            "let viewReads=0, imageReads=0, releaseImage, blobIndex=0;"
            "URL.createObjectURL=()=>`blob:fixture-${++blobIndex}`;URL.revokeObjectURL=()=>{};"
            "global.fetch=async(path,options)=>{",
        )
        .replace(
            "if(path==='/api/view')return{ok:true,json:async()=>input.snapshot};",
            "if(path==='/api/view')return{ok:true,json:async()=>input.snapshots[viewReads++]};",
        )
        .replace(
            "throw new Error('Unexpected request: '+path);",
            "if(path.startsWith('/api/images/')){imageReads++;"
            "if(imageReads===1)return{ok:true,blob:async()=>new Blob(['first'])};"
            "return new Promise(resolve=>{releaseImage=()=>resolve({ok:true,blob:async()=>new Blob(['next'])})});}"
            "throw new Error('Unexpected request: '+path);",
        )
        .replace(
            "if(input.prepare){",
            "const imageTree=node=>[...(node.tagName==='IMG'?[node.src]:[]),...node.children.flatMap(imageTree)];"
            "const firstImages=imageTree(find('#page-content'));"
            "const refresh=find('#refresh-button').onclick();"
            "await new Promise(resolve=>setTimeout(resolve,20));"
            "const duringImages=imageTree(find('#page-content'));"
            "if(!releaseImage)throw new Error('Second cached-image request not reached');"
            "releaseImage();await refresh;"
            "const nextImages=imageTree(find('#page-content'));"
            "if(input.prepare){",
        )
        .replace(
            "JSON.stringify({requests,text:",
            "JSON.stringify({firstImages,duringImages,nextImages,requests,text:",
        )
    )
    path = Path(__file__).resolve().parents[3] / "software/src/rocell/ui/static/app.js"
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": path.read_text(encoding="utf-8"),
                "snapshots": [first, second],
                "page": "camera",
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
    assert parsed["firstImages"] == ["blob:fixture-1"]
    assert parsed["duringImages"] == []
    assert parsed["nextImages"] == ["blob:fixture-2"]
    assert len(parsed["requests"]) == 4
    assert all(row["method"] == "GET" for row in parsed["requests"])
    assert parsed["dialogOpen"] is False
