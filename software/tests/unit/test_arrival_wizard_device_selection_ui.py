"""Pure metadata cards and explicit consent forms; no hardware enumeration."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

from test_arrival_wizard_terminal import Service, action, dispatched, run


WORKSPACE = Path(__file__).resolve().parents[3]
FOLLOWUPS = [
    "VERIFY_RECEIVED_MODEL_AND_UNIT",
    "RESOLVE_UNIQUE_IDENTITY_AND_NATIVE_PREOPEN_RECHECK",
    "QUALIFY_NATIVE_BACKEND_AND_CONNECTION_CONTRACT",
    "COMPLETE_CANONICAL_STAGE_AND_PHYSICAL_RELEASE_GATES",
]


def candidate(kind: str, index: int = 0) -> dict[str, Any]:
    return {
        "choice_id": f"opaque-{kind}-{index}",
        "display_name": f"Unverified {kind} metadata {index}",
        "vid": "1234",
        "pid": "5678",
        "unit_serial": "metadata-unit-id",
        "source": "WINDOWS_PNP" if kind == "CAMERA" else "INJECTED_SERIAL_ENUMERATOR",
        "identity_blockers": [f"{kind}_MODEL_REQUIRES_SEPARATE_EVIDENCE"],
        "candidate_sha256": f"{index + (1 if kind == 'CAMERA' else 1000):064x}",
    }


def selection(*, review: str | None = None) -> dict[str, Any]:
    value = {
        "schema": "rocell.wizard_device_selection.v1",
        "status": "METADATA_CANDIDATES_AVAILABLE",
        "provenance": {
            "mode": "rehearsal",
            "session_id": "metadata-test-session",
            "source_sha256": "a" * 64,
            "platform_system": "Windows",
            "captured_at_unix_ns": 1_800_000_000_000_000_003,
            "scope": "METADATA_SNAPSHOT_ONLY",
        },
        "report_sha256": "b" * 64,
        "operation_id": "inventory-operation",
        "devices": {
            kind: {"candidates": [candidate(kind)], "review": None}
            for kind in ("CAMERA", "SERIAL")
        },
        "physical_authority": False,
        "connected": False,
        "qualified": False,
        "persistent_binding": False,
        "invalidation_reason": None,
    }
    if review is not None:
        chosen = value["devices"][review]["candidates"][0]
        value["status"] = "METADATA_REVIEW_RECORDED"
        value["devices"][review]["review"] = {
            "choice_id": chosen["choice_id"],
            "candidate_sha256": chosen["candidate_sha256"],
            "reviewer_id": "named-reviewer",
            "report_sha256": value["report_sha256"],
            "operation_id": value["operation_id"],
            "status": "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION",
            "connected": False,
            "qualified": False,
            "persistent_binding": False,
            "physical_authority": False,
            "followup_requirements": list(FOLLOWUPS),
        }
    return value


def review_action(kind: str, count: int = 1) -> dict[str, Any]:
    name = "review_camera_candidate" if kind == "CAMERA" else "review_arm_candidate"
    item = action(
        name,
        fields=[
            {
                "name": "choice_id",
                "type": "select",
                "label": "Metadata candidate",
                "required": True,
                "options": [
                    {"value": f"opaque-{kind}-{index}", "label": f"Candidate {index}"}
                    for index in range(count)
                ],
            },
            {
                "name": "reviewer_id",
                "type": "text",
                "label": "Reviewer",
                "required": True,
            },
            {
                "name": "metadata_only",
                "type": "checkbox",
                "label": "Metadata only",
                "required": True,
                "default": False,
            },
        ],
    )
    item["section"] = "camera" if kind == "CAMERA" else "arm"
    return item


class MetadataService(Service):
    def __init__(self, data: Any, *, count: int = 1) -> None:
        super().__init__(
            [review_action("CAMERA", count), review_action("SERIAL", count)]
        )
        self.data = data

    def view(self) -> dict[str, Any]:
        value = super().view()
        value.update(camera={}, arm={}, stages=[], operations=[])
        value["device_selection"] = deepcopy(self.data)
        return value


_HARNESS = r"""
const fs=require('fs'),vm=require('vm');
const input=JSON.parse(fs.readFileSync(0,'utf8')), nodes=[],ids=new Map(),requests=[];
class Element {
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.textContent='';
    this.listeners={};this.hidden=false;this.value='';this.className='';
    this.classList={add(){},toggle(){}};nodes.push(this);}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  addEventListener(name,callback){this.listeners[name]=callback;}
  setAttribute(name,value){this[name]=value;} removeAttribute(name){delete this[name];}
  focus(){} showModal(){this.open=true;} close(){this.open=false;}
  reportValidity(){return (!this.required || (this.type==='checkbox'?this.checked:this.value!==''))
    && this.children.every(child=>child.reportValidity());}
}
function find(id){if(!ids.has(id))ids.set(id,new Element('div'));return ids.get(id);}
global.document={querySelector:find,querySelectorAll:()=>[],createElement:tag=>new Element(tag),
  createTextNode:text=>{const node=new Element('text');node.textContent=text;return node;},
  createDocumentFragment:()=>new Element('fragment'),activeElement:null,hidden:false};
global.location={hash:'#session=fixture&csrf=fixture',pathname:'/'};
global.history={replaceState(){}};global.sessionStorage={setItem(){},getItem(){return null;}};
global.setInterval=()=>1;
global.fetch=async(path,options)=>{
  requests.push({path,method:options.method||'GET',body:options.body?JSON.parse(options.body):null});
  if(path==='/api/view')return{ok:true,json:async()=>input.snapshot};
  if(path==='/api/prepare')return{ok:true,json:async()=>({ticket_id:'metadata-ticket',label:'Review metadata only',
    effects:['Record exact metadata acknowledgment, not connection'],warnings:['No physical authority']})};
  if(path==='/api/execute')return{ok:true,json:async()=>({operation_id:'review-operation',status:'QUEUED'})};
  throw new Error('Unexpected request: '+path);
};
(async()=>{
  vm.runInThisContext(input.script);await new Promise(resolve=>setTimeout(resolve,20));
  find('#navigation').listeners.click({target:{closest:()=>({dataset:{page:input.page}})}});
  if(input.prepare){
    for(const [name,value] of Object.entries(input.values||{})){
      const field=nodes.find(node=>node.id===`field-${input.action}-${name}`);
      if(field.type==='checkbox')field.checked=value;else field.value=value;
    }
    const form=nodes.find(node=>node.tagName==='FORM' && node.children.some(child=>child.textContent===input.action.replaceAll('_',' ')));
    await form.listeners.submit({preventDefault(){}});
  }
  if(input.execute)await find('#execute-action').onclick();
  const treeText=node=>[node.textContent,...node.children.map(treeText)].join('\n');
  process.stdout.write(JSON.stringify({requests,text:treeText(find('#page-content')),
    status:find('#connection-status').textContent,error:find('#error-banner').textContent,
    dialogOpen:find('#action-dialog').open||false,
    controls:nodes.filter(node=>['INPUT','SELECT','TEXTAREA'].includes(node.tagName)).map(node=>({
      tag:node.tagName,id:node.id,value:node.value,checked:node.checked||false,
      options:node.children.filter(child=>child.tagName==='OPTION').map(child=>({value:child.value,selected:child.selected||false}))}))}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
"""


def browser(data: Any, page: str, **options: Any) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime unavailable")
    payload = {
        "script": (WORKSPACE / "software/src/rocell/ui/static/app.js").read_text(
            encoding="utf-8"
        ),
        "snapshot": MetadataService(data).view(),
        "page": page,
        **options,
    }
    result = subprocess.run(
        [node, "-e", _HARNESS],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def render(data: Any, page: str = "camera") -> tuple[str, str]:
    result = browser(data, page)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    service = MetadataService(data)
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and service.calls == [("view",), ("view",)]
    assert service.shutdown_count == 0
    return result["text"], "\n".join(output)


def assert_holds(page: str, console: str) -> None:
    assert "NOT CONNECTED" in page and "NOT QUALIFIED" in page
    assert "NOT_CONNECTED" in console and "NOT_QUALIFIED" in console
    for text in (page, console):
        assert "Received model: UNKNOWN" in text
        assert "No persistent device binding is created" in text
        assert "does not discover, select, preview, connect or open a device" in text
        assert (
            "cannot authorize capture, serial access, power changes, motion or contact"
            in text
        )


@pytest.mark.parametrize("kind,page_name", [("CAMERA", "camera"), ("SERIAL", "arm")])
def test_device_specific_snapshot_blockers_and_no_default_or_dispatch(kind, page_name):
    value = selection()
    page, console = render(value, page_name)
    assert_holds(page, console)
    for text in (page, console):
        assert f"{kind}_MODEL_REQUIRES_SEPARATE_EVIDENCE" in text
        assert "No metadata review recorded" in text
        assert "RETAINED_NOT_INTERPRETED" in text or "RETAINED NOT INTERPRETED" in text
        assert str(value["provenance"]["captured_at_unix_ns"]) not in text
        assert "b" * 64 in text and "a" * 64 in text
    other = "SERIAL" if kind == "CAMERA" else "CAMERA"
    assert f"Unverified {other}" not in page
    controls = browser(value, page_name)["controls"]
    select = next(row for row in controls if row["tag"] == "SELECT")
    assert select["value"] == "" and select["options"][0] == {
        "value": "",
        "selected": True,
    }
    assert not any(row["selected"] for row in select["options"][1:])
    assert not any(row["checked"] for row in controls)


@pytest.mark.parametrize("kind,page_name", [("CAMERA", "camera"), ("SERIAL", "arm")])
def test_review_remains_snapshot_acknowledgment_with_identity_blockers(kind, page_name):
    page, console = render(selection(review=kind), page_name)
    assert_holds(page, console)
    for text in (page, console):
        assert "Explicit metadata acknowledgment" in text
        assert "named-reviewer" in text
        assert f"{kind}_MODEL_REQUIRES_SEPARATE_EVIDENCE" in text
        for code in FOLLOWUPS:
            assert code in text
    assert "NOT VERIFIED" not in page and "NOT_VERIFIED" not in console


@pytest.mark.parametrize("data", [None, False, [], {}, "invalid"])
def test_absent_or_invalid_projection_is_readable_and_inert(data):
    page, console = render(data)
    assert_holds(page, console)
    phrase = (
        "No metadata inventory snapshot"
        if data is None
        else "Device metadata is inconsistent"
    )
    assert phrase in page and phrase in console
    assert "Explicit metadata acknowledgment" not in page


@pytest.mark.parametrize("status", ["NO_INVENTORY", "INVALIDATED"])
def test_empty_and_invalidated_snapshots_do_not_retain_old_candidates(status):
    value = selection()
    value.update(
        status=status,
        report_sha256=None,
        operation_id=None,
        invalidation_reason="SOURCE_CHANGED" if status == "INVALIDATED" else None,
    )
    value["provenance"].update(platform_system=None, captured_at_unix_ns=None)
    for device in value["devices"].values():
        device.update(candidates=[], review=None)
    page, console = render(value)
    assert_holds(page, console)
    assert "NOT VERIFIED" not in page and "NOT_VERIFIED" not in console
    phrase = (
        "metadata snapshot was invalidated"
        if status == "INVALIDATED"
        else "No candidates in this snapshot"
    )
    assert phrase in page and phrase in console
    assert (
        "Unverified CAMERA" not in page
        and "Explicit metadata acknowledgment" not in page
    )


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "wrong"),
        (("status",), "CONNECTED"),
        (("physical_authority",), True),
        (("connected",), True),
        (("qualified",), True),
        (("persistent_binding",), True),
        (("provenance", "source_sha256"), "unbound"),
        (("provenance", "scope"), "LIVE_CONNECTION"),
        (("provenance", "captured_at_unix_ns"), True),
        (("report_sha256",), None),
        (("devices", "CAMERA", "candidates", 0, "display_name"), "x" * 2049),
        (("devices", "CAMERA", "candidates", 0, "display_name"), "unsafe\x1b[2J"),
        (("devices", "CAMERA", "candidates", 0, "display_name"), "\ud800"),
        (("devices", "CAMERA", "candidates", 0, "vid"), 1234),
        (("devices", "CAMERA", "candidates", 0, "source"), "PYSERIAL_LIST_PORTS"),
        (("devices", "CAMERA", "candidates", 0, "identity_blockers"), ["bad code"]),
        (("devices", "CAMERA", "review", "candidate_sha256"), "f" * 64),
        (("devices", "CAMERA", "review", "choice_id"), "different-choice"),
        (("devices", "CAMERA", "review", "report_sha256"), "f" * 64),
        (("devices", "CAMERA", "review", "operation_id"), "old-inventory"),
        (("devices", "CAMERA", "review", "status"), "CONNECTED"),
        (("devices", "CAMERA", "review", "physical_authority"), True),
        (("devices", "CAMERA", "review", "followup_requirements"), []),
    ],
)
def test_inconsistent_identity_review_or_unknown_fields_never_display_acknowledgment(
    path, value
):
    data = selection(review="CAMERA")
    item = data
    for part in path[:-1]:
        item = item[part]
    item[path[-1]] = value
    page, console = render(data)
    assert_holds(page, console)
    assert (
        "Device metadata is inconsistent" in page
        and "Device metadata is inconsistent" in console
    )
    assert (
        "Explicit metadata acknowledgment" not in page
        and "Explicit metadata acknowledgment" not in console
    )


@pytest.mark.parametrize(
    "variant", ["unknown-key", "duplicate-choice", "129-candidates", "33-blockers"]
)
def test_bounded_lists_are_rejected_not_truncated(variant):
    data = selection()
    rows = data["devices"]["CAMERA"]["candidates"]
    if variant == "unknown-key":
        rows[0]["arbitrary_command"] = "NEVER_DISPLAY_COMMAND"
    elif variant == "duplicate-choice":
        rows.append(deepcopy(rows[0]))
    elif variant == "129-candidates":
        rows[:] = [candidate("CAMERA", index) for index in range(129)]
    else:
        rows[0]["identity_blockers"] = [f"BLOCKER_{index}" for index in range(33)]
    page, console = render(data)
    assert (
        "Device metadata is inconsistent" in page
        and "Device metadata is inconsistent" in console
    )
    assert (
        "NEVER_DISPLAY_COMMAND" not in page and "NEVER_DISPLAY_COMMAND" not in console
    )


def test_no_blockers_and_escaped_metadata_still_do_not_prove_received_model():
    data = selection()
    data["devices"]["CAMERA"]["candidates"][0].update(
        display_name="<script>UNTRUSTED_METADATA</script>", identity_blockers=[]
    )
    page, console = render(data)
    assert_holds(page, console)
    assert "<script>UNTRUSTED_METADATA</script>" in page
    for text in (page, console):
        assert "No identity blocker was recorded" in text
        assert "connection and qualification remain unverified" in text


@pytest.mark.parametrize(
    "values",
    [
        {},
        {
            "choice_id": "opaque-CAMERA-0",
            "reviewer_id": "reviewer",
            "metadata_only": False,
        },
    ],
)
def test_browser_required_candidate_and_acknowledgment_prevent_implicit_preview(values):
    result = browser(
        selection(),
        "camera",
        prepare=True,
        action="review_camera_candidate",
        values=values,
    )
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert not result["dialogOpen"]


def test_browser_exact_preview_requires_a_separate_execute():
    options = dict(
        prepare=True,
        action="review_camera_candidate",
        values={
            "choice_id": "opaque-CAMERA-0",
            "reviewer_id": "reviewer",
            "metadata_only": True,
        },
    )
    preview = browser(selection(), "camera", **options)
    assert [row["path"] for row in preview["requests"]] == ["/api/view", "/api/prepare"]
    assert preview["requests"][1]["body"] == {
        "action_id": "review_camera_candidate",
        "input": options["values"],
        "expected_revision": 7,
    }
    assert preview["dialogOpen"]
    executed = browser(selection(), "camera", execute=True, **options)
    assert [row["path"] for row in executed["requests"]].count("/api/execute") == 1
    assert next(
        row["body"] for row in executed["requests"] if row["path"] == "/api/execute"
    ) == {"ticket_id": "metadata-ticket"}


@pytest.mark.parametrize(
    "replies",
    [
        ["review_camera_candidate", "", "quit"],
        ["review_camera_candidate", "1", "reviewer", "", "quit"],
    ],
)
def test_terminal_enter_never_selects_candidate_or_acknowledges_metadata(replies):
    service = MetadataService(selection())
    code, _, _ = run(service, replies)
    assert (
        code == 0
        and not dispatched(service, "prepare")
        and not dispatched(service, "execute")
    )


@pytest.mark.parametrize("confirmation", ["", "yes to all hardware", "no"])
def test_terminal_metadata_preview_does_not_infer_execute(confirmation):
    service = MetadataService(selection())
    code, _, _ = run(
        service,
        ["review_camera_candidate", "1", "reviewer", "yes", confirmation, "quit"],
    )
    assert code == 0 and len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")


@pytest.mark.parametrize("count", [128, 129])
def test_terminal_selection_matches_exact_inventory_candidate_bound(count):
    service = MetadataService(selection(), count=count)
    replies = (
        ["review_camera_candidate", "128", "reviewer", "yes", "no", "quit"]
        if count == 128
        else ["review_camera_candidate", "quit"]
    )
    code, output, _ = run(service, replies)
    assert code == 0 and not dispatched(service, "execute")
    if count == 128:
        assert dispatched(service, "prepare")[0][2]["choice_id"] == "opaque-CAMERA-127"
    else:
        assert not dispatched(service, "prepare")
        assert "Selection has no bounded choices" in "\n".join(output)


@pytest.mark.parametrize(
    "scenario",
    ["nominal", "missing-identity", "duplicate-identity", "partial-inventory"],
)
@pytest.mark.parametrize("kind,page_name", [("CAMERA", "camera"), ("SERIAL", "arm")])
def test_actual_closed_inventory_producer_and_review_render_without_native_work(
    scenario, kind, page_name, monkeypatch
):
    from rocell.application import physical_device_inventory as inventory
    from rocell.application.wizard_device_selection import (
        DeviceSelectionError,
        WizardDeviceSelection,
    )
    from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata presentation fixture invoked a real OS provider")

    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    # The actual production fixture injects a closed command result/provider
    # into the real metadata parsers; no actual PnP/serial enumeration occurs.
    original = rehearsal_device_inventory(scenario)
    model = WizardDeviceSelection("rehearsal", "ui-test-session", "a" * 64)
    if scenario == "partial-inventory":
        with pytest.raises(DeviceSelectionError, match="Incomplete inventory"):
            model.ingest(original, operation_id="closed-fixture-operation")
        page, console = render(model.view(), page_name)
        assert_holds(page, console)
        for text in (page, console):
            assert "metadata snapshot was invalidated" in text
            assert "Explicit metadata acknowledgment" not in text
            assert "Device metadata is inconsistent" not in text
        assert model.choices(kind) == []
        return
    model.ingest(original, operation_id="closed-fixture-operation")
    before = model.view()
    assert all(device["review"] is None for device in before["devices"].values())
    page, console = render(before, page_name)
    assert_holds(page, console)
    assert "NOT VERIFIED" not in page and "NOT_VERIFIED" not in console
    for row in before["devices"][kind]["candidates"]:
        assert row["choice_id"] in page and row["candidate_sha256"] in console
        for code in row["identity_blockers"]:
            assert code in page and code in console
    if scenario == "duplicate-identity":
        assert len(before["devices"][kind]["candidates"]) == 2
        assert "AMBIGUOUS" in page and "AMBIGUOUS" in console
    if scenario == "missing-identity":
        assert "UNIT_SERIAL_MISSING" in page and "UNIT_SERIAL_MISSING" in console
    choices = model.choices(kind)
    if choices:
        reviewed = model.review(choices[-1]["value"], kind, "explicit-ui-reviewer")
        assert reviewed["inventory_report"] == original
        page, console = render(model.view(), page_name)
        assert_holds(page, console)
        for text in (page, console):
            assert "NOT VERIFIED" not in text and "NOT_VERIFIED" not in text
            assert "Explicit metadata acknowledgment" in text
            assert "explicit-ui-reviewer" in text
            assert "ephemeral_locator" not in text and "inventory_report" not in text
    else:
        assert "No candidates in this snapshot" in page
        assert "not evidence that the device is absent" in console


def test_actual_constructor_and_invalidation_render_without_stale_review():
    from test_wizard_device_selection import (
        report as actual_report,
        selection as actual_selection,
    )

    model = actual_selection()
    page, console = render(model.view())
    assert_holds(page, console)
    assert "NOT VERIFIED" not in page and "NOT_VERIFIED" not in console
    model.ingest(actual_report(), operation_id="old-operation")
    token = model.choices("CAMERA")[0]["value"]
    model.review(token, "CAMERA", "previous-reviewer")
    model.invalidate("SOURCE_CHANGED")
    page, console = render(model.view())
    assert_holds(page, console)
    for text in (page, console):
        assert "SOURCE_CHANGED" in text
        assert "metadata snapshot was invalidated" in text
        assert "previous-reviewer" not in text and token not in text


def test_full_128_candidate_snapshot_is_displayed_without_silent_truncation():
    data = selection()
    data["devices"]["CAMERA"]["candidates"] = [
        candidate("CAMERA", index) for index in range(128)
    ]
    page, console = render(data)
    assert_holds(page, console)
    assert "Device metadata is inconsistent" not in page
    assert "Device metadata is inconsistent" not in console
    for index in range(128):
        assert f"opaque-CAMERA-{index}" in page and f"opaque-CAMERA-{index}" in console


@pytest.mark.parametrize(
    "mutation",
    ["review-status-missing", "active-invalidation", "recorded-without-review"],
)
def test_snapshot_status_must_agree_with_current_review(mutation):
    data = selection(review="CAMERA")
    if mutation == "review-status-missing":
        data["status"] = "METADATA_CANDIDATES_AVAILABLE"
    elif mutation == "active-invalidation":
        data["invalidation_reason"] = "SOURCE_CHANGED"
    else:
        data["devices"]["CAMERA"]["review"] = None
    page, console = render(data)
    assert (
        "Device metadata is inconsistent" in page
        and "Device metadata is inconsistent" in console
    )
    assert (
        "Explicit metadata acknowledgment" not in page
        and "Explicit metadata acknowledgment" not in console
    )


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_actual_arrival_view_after_inventory_and_review_renders_without_connecting(
    mode, tmp_path, monkeypatch
):
    from rocell.application import arrival_wizard_service as service_module
    from rocell.application import physical_device_inventory as inventory
    from rocell.application.arrival_wizard_service import ArrivalWizardService
    from rocell.arm.serial_transport import SerialTransport
    from rocell.vision.usb_opencv import UsbOpenCvCamera
    from test_wizard_device_selection_integration import (
        InventoryRunner,
        action as invoke,
        physical_fixture_report,
        review_values,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Arrival presentation test attempted a physical operation")

    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    monkeypatch.setattr(service_module, "source_fingerprint", lambda _: "a" * 64)
    runner = InventoryRunner()
    if mode == "physical":
        # Test-only injection of OS-shaped metadata, never a physical observation.
        runner.report = physical_fixture_report()
    service = ArrivalWizardService(
        WORKSPACE,
        mode=mode,
        runner=runner,
        log_directory=tmp_path / "logs",
        export_directory=tmp_path / "exports",
    )
    try:
        operation = (
            "rehearse_device_inventory" if mode == "rehearsal" else "inventory_devices"
        )
        values = (
            {"scenario": "missing-identity"}
            if mode == "rehearsal"
            else {"power_disconnected": True}
        )
        assert invoke(service, operation, **values)["status"] == "SUCCEEDED"
        for kind, action_id in (
            ("CAMERA", "review_camera_candidate"),
            ("SERIAL", "review_arm_candidate"),
        ):
            assert (
                invoke(service, action_id, **review_values(service, kind))["status"]
                == "SUCCEEDED"
            )
        snapshot = service.view()
        assert (
            snapshot["camera"]["status"] == snapshot["arm"]["status"] == "NOT_CONNECTED"
        )
        assert snapshot["device_selection"]["qualified"] is False
        assert all(row["state"] == "PHYSICAL_PENDING" for row in snapshot["stages"])
        code, output, _ = run(service, ["view", "quit"])
        assert code == 0 and runner.calls == [operation]
        console = "\n".join(output)
        for page_name in ("camera", "arm"):
            result = browser(snapshot["device_selection"], page_name, snapshot=snapshot)
            assert result["status"] == "Local service connected", result["error"]
            assert result["requests"] == [
                {"path": "/api/view", "method": "GET", "body": None}
            ]
            assert_holds(result["text"], console)
            assert "Device metadata is inconsistent" not in result["text"]
            assert "Device metadata is inconsistent" not in console
            assert "Explicit metadata acknowledgment" in result["text"]
            selects = [
                row
                for row in result["controls"]
                if row["tag"] == "SELECT"
                and row["id"]
                in (
                    "field-review_camera_candidate-choice_id",
                    "field-review_arm_candidate-choice_id",
                )
            ]
            assert selects and all(row["value"] == "" for row in selects)
            assert not any(row["checked"] for row in result["controls"])
    finally:
        service.shutdown()
