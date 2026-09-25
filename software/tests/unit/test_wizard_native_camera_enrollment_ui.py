"""Native endpoint enrollment views remain metadata-only and hardware inert."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from test_arrival_wizard_device_selection_ui import browser as metadata_browser
from test_arrival_wizard_device_selection_ui import selection
from test_arrival_wizard_terminal import Service, action, dispatched, run


def enrollment(generic: dict[str, Any], status="ENDPOINT_METADATA_REVIEWED"):
    current = generic["devices"]["CAMERA"]["review"]
    value = {
        "schema": "rocell.wizard_native_camera_enrollment.v1",
        "status": status,
        "provenance": {
            "mode": generic["provenance"]["mode"],
            "session_id": generic["provenance"]["session_id"],
            "source_sha256": generic["provenance"]["source_sha256"],
            "provider_provenance": "INCAPABLE_FIXTURE",
            "helper_sha256": "c" * 64,
            "scope": "NATIVE_ENDPOINT_METADATA_ONLY",
        },
        "inventory_sha256": "d" * 64,
        "inventory_operation_id": "native-inventory-operation",
        "generic_candidate_sha256": current["candidate_sha256"],
        "generic_report_sha256": current["report_sha256"],
        "generic_operation_id": current["operation_id"],
        "candidates": [
            {
                "choice_id": "opaque-native-choice",
                "friendly_name": "Unverified native camera name",
                "endpoint_sha256": "e" * 64,
            }
        ],
        "identity": {
            "choice_id": "opaque-native-choice",
            "endpoint_sha256": "e" * 64,
            "identity_sha256": "f" * 64,
            "operation_id": "native-identity-operation",
            "exact_endpoint_observed": True,
            "generic_device_match": True,
            "container_match": True,
            "blockers": [],
        },
        "review": {
            "choice_id": "opaque-native-choice",
            "reviewer_id": "explicit-native-reviewer",
            "binding_sha256": "1" * 64,
            "status": "REVIEWED_ENDPOINT_METADATA_ONLY",
            "physical_authority": False,
        },
        "blockers": [
            "RECEIVED_MODEL_UNVERIFIED",
            "USB3_LINK_UNVERIFIED",
            "PHYSICAL_RELEASE_REQUIRED",
        ],
        "connected": False,
        "qualified": False,
        "persistent_binding": False,
        "physical_authority": False,
        "invalidation_reason": None,
    }
    if status in ("PROVIDER_UNAVAILABLE", "NO_INVENTORY", "INVALIDATED"):
        for key in (
            "inventory_sha256",
            "inventory_operation_id",
            "generic_candidate_sha256",
            "generic_report_sha256",
            "generic_operation_id",
            "identity",
            "review",
        ):
            value[key] = None
        value["candidates"] = []
        if status == "PROVIDER_UNAVAILABLE":
            value["provenance"].update(provider_provenance=None, helper_sha256=None)
        if status == "INVALIDATED":
            value["invalidation_reason"] = "GENERIC_REVIEW_CHANGED"
    elif status == "ENDPOINT_CHOICES_AVAILABLE":
        value.update(identity=None, review=None)
    elif status == "IDENTITY_RETAINED":
        value["review"] = None
    elif status == "REVIEW_HELD":
        value["identity"].update(
            exact_endpoint_observed=False,
            blockers=["EXACT_ENDPOINT_MAPPING_UNAVAILABLE"],
        )
        value["review"].update(
            binding_sha256=None, status="METADATA_ACKNOWLEDGED_BUT_HELD"
        )
    return value


def native_action(action_id):
    fields = []
    if action_id != "native_camera_inventory":
        fields.append(
            {
                "name": "choice_id",
                "type": "select",
                "label": "Native endpoint choice",
                "required": True,
                "options": [
                    {
                        "value": "opaque-native-choice",
                        "label": "Unverified endpoint metadata",
                    }
                ],
            }
        )
    if action_id == "native_camera_review":
        fields.append(
            {
                "name": "reviewer_id",
                "type": "text",
                "label": "Reviewer",
                "required": True,
            }
        )
    fields.append(
        {
            "name": "metadata_only",
            "type": "checkbox",
            "label": "Metadata only",
            "required": True,
            "default": False,
        }
    )
    result = action(action_id, fields=fields)
    result["section"] = "camera"
    return result


class NativeService(Service):
    def __init__(self, native, generic):
        super().__init__(
            [
                native_action(name)
                for name in (
                    "native_camera_inventory",
                    "native_camera_identity",
                    "native_camera_review",
                )
            ]
        )
        self.native, self.generic = native, generic

    def view(self):
        result = super().view()
        result.update(
            camera={},
            arm={},
            stages=[],
            operations=[],
            device_selection=deepcopy(self.generic),
            native_camera_enrollment=deepcopy(self.native),
        )
        return result


def browser(native, generic, page="camera", **options):
    return metadata_browser(
        generic, page, snapshot=NativeService(native, generic).view(), **options
    )


def render(native, generic):
    result = browser(native, generic)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    service = NativeService(native, generic)
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and service.calls == [("view",), ("view",)]
    assert not service.shutdown_count
    page = (
        result["text"]
        .split("Native camera endpoint enrollment", 1)[1]
        .split("Camera actions", 1)[0]
    )
    console = "\n".join(output)
    return page, console


def assert_holds(page, console):
    assert "NOT CONNECTED" in page and "NOT QUALIFIED" in page
    assert "NOT_CONNECTED" in console and "NOT_QUALIFIED" in console
    for text in (page, console):
        assert "No persistent-unit binding or physical authority" in text
        assert "not proof of received camera model, USB3 topology/link speed" in text
        assert "Names never establish identity" in text
        assert (
            "no inventory, identity lookup, review, helper call or camera activation"
            in text
        )
        assert (
            "do not grant capture, calibration, power, motion or contact authority"
            in text
        )


@pytest.mark.parametrize(
    "status",
    [
        "PROVIDER_UNAVAILABLE",
        "NO_INVENTORY",
        "ENDPOINT_CHOICES_AVAILABLE",
        "IDENTITY_RETAINED",
        "ENDPOINT_METADATA_REVIEWED",
        "REVIEW_HELD",
        "INVALIDATED",
    ],
)
def test_exact_states_render_without_activation_or_false_qualification(status):
    generic = selection(review="CAMERA")
    native = enrollment(generic, status)
    page, console = render(native, generic)
    assert_holds(page, console)
    for text in (page, console):
        assert "Native enrollment metadata is inconsistent" not in text
        if status == "PROVIDER_UNAVAILABLE":
            assert "Native metadata helper registration is required" in text
            assert "does not search for, install or execute a helper" in text
        elif status == "INVALIDATED":
            assert "native enrollment was invalidated" in text
            assert "explicit-native-reviewer" not in text
        elif status == "ENDPOINT_METADATA_REVIEWED":
            assert "Explicit native endpoint metadata review" in text
            assert (
                "DIAGNOSTIC_METADATA_ONLY_NOT_PERSISTENT_UNIT_BINDING" in text
                or "DIAGNOSTIC METADATA ONLY NOT PERSISTENT UNIT BINDING" in text
            )
        elif status == "REVIEW_HELD":
            assert "Explicit native review remains held" in text
            assert "EXACT_ENDPOINT_MAPPING_UNAVAILABLE" in text
        for code in native["blockers"]:
            assert code in text


def test_native_card_is_camera_only_and_selection_consent_have_no_defaults():
    generic = selection(review="CAMERA")
    native = enrollment(generic)
    assert (
        "Native camera endpoint enrollment"
        not in browser(native, generic, "arm")["text"]
    )
    result = browser(native, generic)
    for control in result["controls"]:
        if control["tag"] == "SELECT":
            assert control["value"] == ""
            assert control["options"][0] == {"value": "", "selected": True}
            assert not any(option["selected"] for option in control["options"][1:])
        assert control["checked"] is False


@pytest.mark.parametrize("native", [None, False, [], {}, "invalid"])
def test_absent_and_malformed_snapshots_are_readable_without_endpoint_inference(native):
    page, console = render(native, selection(review="CAMERA"))
    assert_holds(page, console)
    phrase = (
        "No native endpoint enrollment snapshot"
        if native is None
        else "Native enrollment metadata is inconsistent"
    )
    assert phrase in page and phrase in console
    assert "explicit-native-reviewer" not in page


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "unknown"),
        (("status",), "CONNECTED"),
        (("connected",), True),
        (("qualified",), True),
        (("persistent_binding",), True),
        (("physical_authority",), True),
        (("inventory_sha256",), None),
        (("generic_report_sha256",), "2" * 64),
        (("generic_candidate_sha256",), "2" * 64),
        (("generic_operation_id",), "older-generic"),
        (("provenance", "scope"), "CONNECTED"),
        (("provenance", "helper_sha256"), None),
        (("provenance", "source_sha256"), "2" * 64),
        (("provenance", "session_id"), "different-session"),
        (("candidates", 0, "friendly_name"), "x" * 1025),
        (("candidates", 0, "friendly_name"), "\ud800"),
        (("candidates", 0, "friendly_name"), "unsafe\x1b[2J"),
        (("candidates", 0, "endpoint_sha256"), "unbound"),
        (("identity", "choice_id"), "other-choice"),
        (("identity", "endpoint_sha256"), "2" * 64),
        (("identity", "identity_sha256"), "unbound"),
        (("identity", "exact_endpoint_observed"), 1),
        (("identity", "generic_device_match"), False),
        (("identity", "container_match"), False),
        (("identity", "blockers"), ["MAPPING_UNAVAILABLE"]),
        (("review", "choice_id"), "other-choice"),
        (("review", "binding_sha256"), None),
        (("review", "physical_authority"), True),
        (("review", "status"), "CONNECTED"),
        (("blockers",), ["BAD CODE"]),
    ],
)
def test_malformed_stale_and_authority_bearing_native_views_fail_closed(path, value):
    generic = selection(review="CAMERA")
    native = enrollment(generic)
    item = native
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    page, console = render(native, generic)
    assert_holds(page, console)
    assert (
        "Native enrollment metadata is inconsistent" in page
        and "Native enrollment metadata is inconsistent" in console
    )
    assert "Explicit native endpoint metadata review" not in page


@pytest.mark.parametrize(
    "mutation", ["no-review", "source", "new-inventory", "other-candidate"]
)
def test_current_generic_review_is_required_not_only_embedded_hashes(mutation):
    generic = selection(review="CAMERA")
    native = enrollment(generic)
    if mutation == "no-review":
        generic["devices"]["CAMERA"]["review"] = None
        generic["status"] = "METADATA_CANDIDATES_AVAILABLE"
    elif mutation == "source":
        generic["provenance"]["source_sha256"] = "2" * 64
    elif mutation == "new-inventory":
        generic["operation_id"] = "new-operation"
        generic["devices"]["CAMERA"]["review"]["operation_id"] = "new-operation"
    else:
        generic["devices"]["CAMERA"]["candidates"][0]["candidate_sha256"] = "2" * 64
        generic["devices"]["CAMERA"]["review"]["candidate_sha256"] = "2" * 64
    page, console = render(native, generic)
    assert (
        "Native enrollment metadata is inconsistent" in page
        and "Native enrollment metadata is inconsistent" in console
    )


@pytest.mark.parametrize("status", ["ENDPOINT_CHOICES_AVAILABLE", "IDENTITY_RETAINED"])
def test_partial_reset_keeps_prior_inventory_without_displaying_an_old_review(status):
    generic = selection(review="CAMERA")
    native = enrollment(generic, status)
    native["invalidation_reason"] = "EXPLICIT_METADATA_REFRESH_STARTED"
    page, console = render(native, generic)
    assert_holds(page, console)
    for text in (page, console):
        assert "Native enrollment metadata is inconsistent" not in text
        assert "EXPLICIT_METADATA_REFRESH_STARTED" in text
        assert "native-inventory-operation" in text
        assert "explicit-native-reviewer" not in text


def test_duplicate_friendly_names_remain_distinct_hash_identified_choices():
    generic = selection(review="CAMERA")
    native = enrollment(generic, "ENDPOINT_CHOICES_AVAILABLE")
    native["candidates"].append(
        {
            **native["candidates"][0],
            "choice_id": "second-opaque-choice",
            "endpoint_sha256": "2" * 64,
        }
    )
    page, console = render(native, generic)
    assert_holds(page, console)
    for text in (page, console):
        assert "second-opaque-choice" in text and "2" * 64 in text
        assert "Identical names remain distinct opaque choices" in text
        assert "no first-device or same-name fallback" in text


def test_full_128_choice_snapshot_and_plain_text_name_are_retained_without_truncation():
    generic = selection(review="CAMERA")
    native = enrollment(generic, "ENDPOINT_CHOICES_AVAILABLE")
    native["candidates"] = [
        {
            "choice_id": f"native-{index}",
            "friendly_name": "<script>UNTRUSTED_NAME</script>",
            "endpoint_sha256": f"{index + 1:064x}",
        }
        for index in range(128)
    ]
    page, console = render(native, generic)
    assert_holds(page, console)
    assert "Native enrollment metadata is inconsistent" not in page
    assert "Native enrollment metadata is inconsistent" not in console
    for index in range(128):
        assert f"native-{index}" in page and f"native-{index}" in console
    assert "<script>UNTRUSTED_NAME</script>" in page


@pytest.mark.parametrize(
    "variant",
    ["unknown-raw-endpoint", "duplicate-choice", "129-candidates", "33-blockers"],
)
def test_unknown_data_and_over_limit_lists_are_not_rendered_or_truncated(variant):
    generic = selection(review="CAMERA")
    native = enrollment(generic)
    if variant == "unknown-raw-endpoint":
        native["candidates"][0]["symbolic_link"] = "NEVER_RENDER_RAW_ENDPOINT"
    elif variant == "duplicate-choice":
        native["candidates"].append(deepcopy(native["candidates"][0]))
    elif variant == "129-candidates":
        native["candidates"] = [
            {**native["candidates"][0], "choice_id": f"choice-{index}"}
            for index in range(129)
        ]
    else:
        native["blockers"] = [f"BLOCKER_{index}" for index in range(33)]
    page, console = render(native, generic)
    assert (
        "Native enrollment metadata is inconsistent" in page
        and "Native enrollment metadata is inconsistent" in console
    )
    assert (
        "NEVER_RENDER_RAW_ENDPOINT" not in page
        and "NEVER_RENDER_RAW_ENDPOINT" not in console
    )


@pytest.mark.parametrize(
    "action_id",
    ["native_camera_inventory", "native_camera_identity", "native_camera_review"],
)
def test_each_native_browser_action_requires_metadata_consent_before_preview(action_id):
    generic = selection(review="CAMERA")
    native = enrollment(generic)
    values = {
        "choice_id": "opaque-native-choice",
        "reviewer_id": "named-reviewer",
        "metadata_only": False,
    }
    fields = {field["name"] for field in native_action(action_id)["fields"]}
    values = {key: value for key, value in values.items() if key in fields}
    result = browser(native, generic, prepare=True, action=action_id, values=values)
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    values["metadata_only"] = True
    result = browser(native, generic, prepare=True, action=action_id, values=values)
    assert [row["path"] for row in result["requests"]] == ["/api/view", "/api/prepare"]
    assert result["requests"][1]["body"]["input"] == values
    assert result["dialogOpen"]


@pytest.mark.parametrize("confirmation", ["", "yes to all hardware", "no"])
def test_native_terminal_review_preview_never_infers_execution(confirmation):
    generic = selection(review="CAMERA")
    service = NativeService(enrollment(generic), generic)
    code, _, _ = run(
        service, ["native_camera_review", "1", "reviewer", "yes", confirmation, "quit"]
    )
    assert code == 0 and len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")


def test_native_terminal_enter_never_selects_first_endpoint():
    generic = selection(review="CAMERA")
    service = NativeService(enrollment(generic), generic)
    code, _, _ = run(service, ["native_camera_identity", "", "quit"])
    assert (
        code == 0
        and not dispatched(service, "prepare")
        and not dispatched(service, "execute")
    )


@pytest.fixture
def actual_service(tmp_path, monkeypatch):
    from rocell.application import arrival_wizard_service as service_module
    from rocell.application import physical_device_inventory as inventory
    from rocell.arm.serial_transport import SerialTransport
    from rocell.providers.windows import camera_worker_client as client
    from rocell.vision.usb_opencv import UsbOpenCvCamera
    from test_wizard_device_selection_integration import InventoryRunner

    def forbidden(*args, **kwargs):
        pytest.fail("Native enrollment UI test attempted physical/provider dispatch")

    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(client, "bounded_subprocess_runner", forbidden)
    monkeypatch.setattr(
        client.WindowsCameraWorkerClient, "_registered_arguments", forbidden
    )
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    monkeypatch.setattr(service_module, "source_fingerprint", lambda _: "a" * 64)
    instances = []

    def create(mode="rehearsal"):
        runner = InventoryRunner()
        service = service_module.ArrivalWizardService(
            Path(__file__).resolve().parents[3],
            mode=mode,
            runner=runner,
            log_directory=tmp_path / f"logs-{mode}",
            export_directory=tmp_path / f"exports-{mode}",
        )
        instances.append(service)
        return service, runner

    yield create
    for service in instances:
        service.shutdown()


@pytest.mark.parametrize(
    "scenario", ["nominal", "missing-mapping", "wrong-device", "duplicate-name"]
)
def test_actual_provider_registry_arrival_and_views_use_exact_retained_metadata(
    actual_service, scenario
):
    from test_wizard_device_selection_integration import action as invoke, review_values

    service, runner = actual_service()
    assert (
        invoke(service, "rehearse_device_inventory", scenario="nominal")["status"]
        == "SUCCEEDED"
    )
    assert (
        invoke(service, "review_camera_candidate", **review_values(service))["status"]
        == "SUCCEEDED"
    )
    inventory = invoke(
        service, "native_camera_inventory", metadata_only=True, scenario=scenario
    )
    assert inventory["status"] == "SUCCEEDED", inventory.get("error")
    initial = service.view()["native_camera_enrollment"]
    assert (
        initial["candidates"]
        and initial["identity"] is None
        and initial["review"] is None
    )
    chosen = initial["candidates"][0]["choice_id"]
    identity = invoke(
        service, "native_camera_identity", choice_id=chosen, metadata_only=True
    )
    assert identity["status"] == "SUCCEEDED", identity.get("error")
    reviewed = invoke(
        service,
        "native_camera_review",
        choice_id=chosen,
        reviewer_id="explicit-native-ui-reviewer",
        metadata_only=True,
    )
    assert reviewed["status"] == "SUCCEEDED", reviewed.get("error")
    snapshot = service.view()
    native = snapshot["native_camera_enrollment"]
    assert native["physical_authority"] is False
    assert native["connected"] is False and native["qualified"] is False
    assert native["persistent_binding"] is False
    assert snapshot["camera"]["status"] == "NOT_CONNECTED"
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in snapshot["stages"])
    assert (
        native["generic_candidate_sha256"]
        == snapshot["device_selection"]["devices"]["CAMERA"]["review"][
            "candidate_sha256"
        ]
    )
    assert native["identity"]["choice_id"] == chosen
    assert native["review"]["choice_id"] == chosen
    if scenario == "nominal":
        assert native["status"] == "ENDPOINT_METADATA_REVIEWED"
        assert native["review"]["binding_sha256"] is not None
        assert native["identity"]["blockers"] == []
        assert "CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED" in native["blockers"]
        assert "CAMERA_USB3_TOPOLOGY_NOT_OBSERVED" in native["blockers"]
    if scenario in ("missing-mapping", "wrong-device"):
        assert native["status"] == "REVIEW_HELD"
        assert native["identity"]["blockers"]
        assert native["review"]["binding_sha256"] is None
    if scenario == "duplicate-name":
        assert len(native["candidates"]) == 2
        assert len({row["friendly_name"] for row in native["candidates"]}) == 1
        assert len({row["choice_id"] for row in native["candidates"]}) == 2
    result = metadata_browser(snapshot["device_selection"], "camera", snapshot=snapshot)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    page = (
        result["text"]
        .split("Native camera endpoint enrollment", 1)[1]
        .split("Camera actions", 1)[0]
    )
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and runner.calls == ["rehearse_device_inventory"]
    console = "\n".join(output)
    assert_holds(page, console)
    for text in (page, console):
        assert "Native enrollment metadata is inconsistent" not in text
        assert "explicit-native-ui-reviewer" in text
        assert native["identity"]["identity_sha256"] in text
        assert native["inventory_sha256"] in text
        for blocker in native["identity"]["blockers"]:
            assert blocker in text
    native_choices = [
        row
        for row in result["controls"]
        if row["id"]
        in (
            "field-native_camera_identity-choice_id",
            "field-native_camera_review-choice_id",
        )
    ]
    assert len(native_choices) == 2 and all(
        row["value"] == "" for row in native_choices
    )
    assert not any(
        row["checked"]
        for row in result["controls"]
        if row["id"].startswith("field-native_camera_")
    )


def test_actual_default_physical_view_shows_helper_registration_hold_without_query(
    actual_service,
):
    service, runner = actual_service("physical")
    snapshot = service.view()
    assert snapshot["native_camera_enrollment"]["status"] == "PROVIDER_UNAVAILABLE"
    assert not next(
        item
        for item in snapshot["actions"]
        if item["action_id"] == "native_camera_inventory"
    )["enabled"]
    result = metadata_browser(snapshot["device_selection"], "camera", snapshot=snapshot)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and not runner.calls
    page = (
        result["text"]
        .split("Native camera endpoint enrollment", 1)[1]
        .split("Camera actions", 1)[0]
    )
    console = "\n".join(output)
    assert_holds(page, console)
    for text in (page, console):
        assert "Native metadata helper registration is required" in text
        assert "Native enrollment metadata is inconsistent" not in text
