"""Native metadata presentation; no host acquisition, ports or qualification.

The main fixture is the actual closed rehearsal snapshot -> strict correlation
producer -> generic registry view. A separate test joins real Arrival publication
with an injected pure runner; neither fixture is physical device evidence.
"""

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory
from rocell.application.wizard_native_arm_metadata import (
    BLOCKER_CODES,
    NATIVE_FIELDS,
    correlate_native_arm_metadata,
    rehearse_native_arm_metadata_snapshot,
    summarize_native_arm_metadata,
)
from rocell.ui.terminal import (
    _NATIVE_ARM_BLOCKERS,
    _NATIVE_ARM_FIELDS,
    _TerminalWizard,
    _native_arm_metadata,
)
from test_arrival_wizard_device_selection_ui import browser
from test_arrival_wizard_service import FakeRunner, _complete, _ticket, make_service
from test_arrival_wizard_terminal import Service, action, dispatched, run


SOURCE = "a" * 64
SESSION = "wizard-" + "1" * 32
ACTION = "rehearse_native_arm_metadata"


def produced(scenario="nominal", *, session=SESSION, source=SOURCE):
    generic = WizardDeviceSelection("rehearsal", session, source)
    generic.ingest(
        rehearsal_device_inventory("nominal"), operation_id="generic_op_exact"
    )
    generic.review(generic.choices("SERIAL")[0]["value"], "SERIAL", "reviewer_exact")
    report = correlate_native_arm_metadata(
        rehearse_native_arm_metadata_snapshot(scenario),
        generic.reviewed_candidate("SERIAL"),
        mode="rehearsal",
        session_id=session,
        source_sha256=source,
        operation_id="native_op_exact",
    )
    wrapper = {
        "schema": "rocell.wizard_native_arm_metadata_view.v1",
        "status": "CURRENT",
        "report": summarize_native_arm_metadata(report),
        "invalidation_reason": None,
        "connected": False,
        "qualified": False,
        "physical_authority": False,
    }
    view = Service([]).view()
    view.update(
        mode="rehearsal",
        session_id=session,
        source_binding_sha256=source,
        device_selection=generic.view(),
        native_arm_metadata=wrapper,
        camera={},
        arm={},
        stages=[],
        operations=[],
    )
    return view, report


class CachedView(Service):
    def __init__(self, snapshot):
        super().__init__(snapshot.get("actions", []))
        self.snapshot = deepcopy(snapshot)

    def view(self):
        self.calls.append(("view",))
        return deepcopy(self.snapshot)


def render(view):
    page = browser(view.get("device_selection"), "arm", snapshot=deepcopy(view))
    assert page["status"] == "Local service connected", page["error"]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["dialogOpen"] is False
    service = CachedView(view)
    code, output, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)] and service.shutdown_count == 0
    return page["text"], "\n".join(output)


def panel(text):
    return text.split("Native arm metadata correlation", 1)[1].split("Arm actions", 1)[
        0
    ]


@pytest.mark.parametrize(
    "scenario",
    ["nominal", "missing-fields", "duplicate-mapping", "changed-device", "incomplete"],
)
def test_actual_producer_is_rendered_without_connection_or_native_field_values(
    scenario,
):
    view, report = produced(scenario)
    original = deepcopy(view)
    value = view["native_arm_metadata"]
    assert _native_arm_metadata(value, view) == value
    assert report["status"] == (
        "METADATA_CORRELATED" if scenario == "nominal" else "HELD"
    )
    for rendered in render(view):
        text = panel(rendered)
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" not in text
        assert "Correlation result: " + report["status"] in text
        assert "NOT_CONNECTED / NOT_QUALIFIED" in text
        assert "INCAPABLE REHEARSAL" in text
        assert "native_op_exact" in text and "generic_op_exact" in text
        assert (
            "generic inventory metadata, not a native USB-descriptor observation"
            in text
        )
        assert "does not create a ReviewedControllerBinding" in text
        assert "driver_version: " + report["native_fields"]["driver_version"] in text
        for code in report["blockers"]:
            assert code in text
        for raw in (
            "COM91",
            "synthetic-not-installed.inf",
            "SYNTHETIC provider",
            "usb#vid_",
        ):
            assert raw not in text
    assert view == original


def test_display_rosters_match_the_producer_without_provider_imports_at_render():
    assert set(_NATIVE_ARM_FIELDS) == set(NATIVE_FIELDS)
    assert _NATIVE_ARM_BLOCKERS == BLOCKER_CODES


def test_modeled_physical_provenance_is_separate_from_incapable_rehearsal():
    view, _ = produced()
    summary = view["native_arm_metadata"]["report"]
    summary["binding"]["mode"] = view["mode"] = "physical"
    summary["provenance"].update(
        origin="PHYSICAL_OBSERVATION", native_source="WINDOWS_CM_METADATA"
    )
    view["device_selection"]["provenance"]["mode"] = "physical"
    for candidate in view["device_selection"]["devices"]["SERIAL"]["candidates"]:
        candidate["source"] = "PYSERIAL_LIST_PORTS"
    for rendered in render(view):
        text = panel(rendered)
        assert "WINDOWS METADATA OBSERVATION ONLY" in text
        assert "atomically bound open handle" in text
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" not in text
        assert "INCAPABLE REHEARSAL" not in text


@pytest.mark.parametrize(
    "state", ["absent", "null", "NOT_INSPECTED", "HISTORICAL_HELD"]
)
def test_initial_or_failed_before_observation_has_no_inferred_absence(state):
    view, _ = produced()
    if state == "absent":
        del view["native_arm_metadata"]
    elif state == "null":
        view["native_arm_metadata"] = None
    else:
        view["native_arm_metadata"].update(
            status=state,
            report=None,
            invalidation_reason=(
                None if state == "NOT_INSPECTED" else "ARM_METADATA_NOT_PUBLISHED"
            ),
        )
    for rendered in render(view):
        text = panel(rendered)
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" not in text
        assert "Correlation result:" not in text
        assert "NOT_CONNECTED / NOT_QUALIFIED" in text


def test_historical_original_binding_is_not_reinterpreted_as_current_review():
    view, _ = produced()
    original = deepcopy(view["native_arm_metadata"]["report"])
    view["native_arm_metadata"].update(
        status="HISTORICAL_HELD", invalidation_reason="ARM_METADATA_CONTEXT_CHANGED"
    )
    view.update(
        source_binding_sha256="b" * 64,
        session_id="new_launch_exact",
        device_selection=None,
    )
    for rendered in render(view):
        text = panel(rendered)
        assert "Historical metadata only" in text
        assert "not the current reviewed device" in text
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" not in text
        assert original["binding"]["session_id"] in text
        assert "Correlation result: METADATA_CORRELATED" in text
        assert "Publication: CURRENT" not in text
    assert view["native_arm_metadata"]["report"] == original


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v["native_arm_metadata"].update(extra="RAW_SENTINEL"),
        lambda v: v["native_arm_metadata"].update(connected=True),
        lambda v: v["native_arm_metadata"].update(qualified=0),
        lambda v: v["native_arm_metadata"].update(physical_authority="false"),
        lambda v: v["native_arm_metadata"].update(status="CONNECTED"),
        lambda v: v["native_arm_metadata"].update(report=None),
        lambda v: v["native_arm_metadata"].update(
            invalidation_reason="RAW_SENTINEL/path"
        ),
        lambda v: v["native_arm_metadata"]["report"].update(raw_bytes="RAW_SENTINEL"),
        lambda v: v["native_arm_metadata"]["report"].update(persistent_binding=True),
        lambda v: v["native_arm_metadata"]["report"].update(
            blockers=["UNREGISTERED_BLOCKER"]
        ),
        lambda v: v["native_arm_metadata"]["report"].update(blockers=[{}]),
        lambda v: v["native_arm_metadata"]["report"].update(status="HELD"),
        lambda v: v["native_arm_metadata"]["report"].update(report_sha256="g" * 64),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(mode="physical"),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            operation_id="RAW_SENTINEL/COM91"
        ),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            operation_id="a" * 129
        ),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            source_sha256="b" * 64
        ),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            session_id="old_session"
        ),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            generic_candidate_sha256="b" * 64
        ),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            generic_report_sha256="b" * 64
        ),
        lambda v: v["native_arm_metadata"]["report"]["binding"].update(
            generic_inventory_operation_id="other_op"
        ),
        lambda v: v["native_arm_metadata"]["report"]["provenance"].update(
            origin="PHYSICAL_OBSERVATION"
        ),
        lambda v: v["native_arm_metadata"]["report"]["provenance"].update(
            unit_serial_origin="NATIVE_USB_DESCRIPTOR"
        ),
        lambda v: v["native_arm_metadata"]["report"]["counts"].update(
            native_observations=True
        ),
        lambda v: v["native_arm_metadata"]["report"]["counts"].update(
            native_observations=129
        ),
        lambda v: v["native_arm_metadata"]["report"]["counts"].update(
            native_observations=-1
        ),
        lambda v: v["native_arm_metadata"]["report"]["counts"].update(
            native_observations=0
        ),
        lambda v: v["native_arm_metadata"]["report"]["native_fields"].update(
            port_name="RAW_SENTINEL"
        ),
        lambda v: v["native_arm_metadata"]["report"]["native_fields"].update(
            driver_inf="MISSING"
        ),
        lambda v: v["native_arm_metadata"]["report"]["native_fields"].update(
            driver_provider=True
        ),
        lambda v: v["native_arm_metadata"]["report"]["native_fields"].pop("driver_inf"),
        lambda v: v.update(source_binding_sha256="b" * 64),
        lambda v: v.update(session_id="new_session"),
        lambda v: v.update(device_selection=None),
        lambda v: v["device_selection"]["devices"]["SERIAL"].update(review=None),
        lambda v: v["device_selection"]["provenance"].update(source_sha256="b" * 64),
    ],
)
def test_malformed_or_changed_current_correlation_is_withheld(mutation):
    view, _ = produced()
    mutation(view)
    assert _native_arm_metadata(view["native_arm_metadata"], view) is None
    for rendered in render(view):
        text = panel(rendered)
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" in text
        assert "Correlation result:" not in text and "RAW_SENTINEL" not in text


def test_native_card_is_arm_only():
    view, _ = produced()
    page = browser(view["device_selection"], "camera", snapshot=view)
    assert "Native arm metadata correlation" not in page["text"]
    assert len(page["requests"]) == 1


def test_terminal_cached_render_never_touches_files_or_native_calls(monkeypatch):
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )

    view, _ = produced()
    output = []
    renderer = _TerminalWizard(
        Service([]), lambda _: "quit", output.append, lambda _: None
    )

    def forbidden(*_a, **_k):
        pytest.fail("Cached renderer attempted file/native/process I/O")

    with monkeypatch.context() as guard:
        for method in ("open", "stat", "read_text", "read_bytes"):
            guard.setattr(Path, method, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(WindowsControllerMetadataAcquirer, "__call__", forbidden)
        renderer.show_native_arm_metadata(view["native_arm_metadata"], view)
    assert any(
        "Correlation result: METADATA_CORRELATED" in str(line) for line in output
    )


@pytest.mark.parametrize("physical", [False, True])
def test_actual_catalog_forms_require_explicit_consent_and_no_port_input(physical):
    from rocell.application.wizard_actions import ACTION_BY_ID

    name = "inspect_native_arm_metadata" if physical else ACTION
    definition = ACTION_BY_ID[name]
    item = action(name, fields=list(definition.fields))
    item["section"] = "arm"
    view, _ = produced()
    view["actions"] = [item]
    page = browser(view["device_selection"], "arm", snapshot=view)
    controls = [
        row for row in page["controls"] if row["id"].startswith("field-" + name)
    ]
    assert all(not row["checked"] for row in controls if row["tag"] == "INPUT")
    assert not {field["name"] for field in definition.fields} & {
        "port",
        "command",
        "path",
        "worker",
        "allow_hardware",
    }
    values = {"metadata_only": True}
    values.update({"power_disconnected": True} if physical else {"scenario": "nominal"})
    page = browser(
        view["device_selection"],
        "arm",
        snapshot=view,
        prepare=True,
        action=name,
        values=values,
    )
    assert [row["path"] for row in page["requests"]] == ["/api/view", "/api/prepare"]
    assert page["requests"][1]["body"]["input"] == values
    assert not any(row["path"] == "/api/execute" for row in page["requests"])
    replies = (
        [name, "yes", "yes", "yes to all hardware", "quit"]
        if physical
        else [name, "nominal", "yes", "", "quit"]
    )
    service = Service([item])
    code, _, _ = run(service, replies)
    assert code == 0 and len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")


@pytest.mark.parametrize(
    "scenario",
    ["nominal", "missing-fields", "duplicate-mapping", "changed-device", "incomplete"],
)
def test_actual_arrival_publication_with_pure_runner_renders_actual_summary(
    make_service, monkeypatch, scenario
):
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )

    def forbidden(*_a, **_k):
        pytest.fail("Pure service join attempted host metadata")

    monkeypatch.setattr(WindowsControllerMetadataAcquirer, "__call__", forbidden)
    fake = FakeRunner()
    fake.result_changes = {
        "steps": [
            {
                "name": "native_arm_metadata_snapshot",
                "exit_code": 0,
                "report": rehearse_native_arm_metadata_snapshot(scenario),
            }
        ],
    }
    service, _, _ = make_service(runner=fake)
    generic = service._device_selection
    generic.ingest(
        rehearsal_device_inventory("nominal"), operation_id="generic_op_exact"
    )
    generic.review(generic.choices("SERIAL")[0]["value"], "SERIAL", "reviewer_exact")
    ticket = _ticket(service, ACTION, {"scenario": scenario, "metadata_only": True})
    assert fake.calls == []
    receipt = service.execute_action(ticket["ticket_id"])
    result = _complete(service, receipt["operation_id"])
    assert result["status"] == "SUCCEEDED", result
    view = service.view()
    summary = view["native_arm_metadata"]["report"]
    assert view["native_arm_metadata"]["status"] == "CURRENT"
    assert summary["status"] == (
        "METADATA_CORRELATED" if scenario == "nominal" else "HELD"
    )
    for text in render(view):
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" not in panel(text)
        assert summary["report_sha256"] in text
    assert len(fake.calls) == 1
    generic.invalidate("INVENTORY_REPLACEMENT_NOT_VERIFIED")
    for text in render(service.view()):
        assert "Historical metadata only" in panel(text)
        assert "NATIVE_ARM_METADATA_NOT_VERIFIED" not in panel(text)
    assert len(fake.calls) == 1
