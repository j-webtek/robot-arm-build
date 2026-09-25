"""Cached mode/control presentation, with actual pure producer cross-checks.

No probe, child process, physical device or received-camera measurement is used.
"""

from copy import deepcopy
import json

import pytest

from test_arrival_wizard_arm_power_ui import terminal
from test_arrival_wizard_reopen_ui import browser, commissioning
from test_wizard_owned_camera_process_ui import summary as process_summary
from test_arrival_wizard_service import make_service  # noqa: F401


CONTROLS = ("exposure", "gain", "white_balance", "brightness", "contrast", "saturation")


def mode(**changes):
    return {
        "width": 5472,
        "height": 3648,
        "fps_numerator": 9,
        "fps_denominator": 1,
        "subtype": "YUY2",
        "stride_bytes": 10944,
        **changes,
    }


def capabilities():
    return {
        "schema": "rocell.camera_capabilities.v1",
        "status": "REPORTED_REHEARSAL_ONLY",
        "capabilities_sha256": "a" * 64,
        "probe_evidence_sha256": "b" * 64,
        "binding": {
            "session_id": "session-fixture",
            "attempt_id": "attempt-probe",
            "source_sha256": "c" * 64,
            "permit_sha256": "d" * 64,
            "operation_sha256": "e" * 64,
            "selected_identity_sha256": "f" * 64,
        },
        "endpoint_sha256": "1" * 64,
        "modes": [
            {
                "choice_id": "mode-" + "0" * 24,
                "mode": mode(),
                "selectable": True,
                "blockers": [],
            },
            {
                "choice_id": "mode-" + "1" * 24,
                "mode": mode(
                    width=1920,
                    height=1080,
                    fps_numerator=30,
                    subtype="MJPG",
                    stride_bytes=None,
                ),
                "selectable": False,
                "blockers": ["UNSUPPORTED_PIXEL_FORMAT"],
            },
        ],
        "controls": [
            {
                "control_id": name,
                "minimum": 0,
                "maximum": 100,
                "step": 5,
                "default": 50,
                "capability_flags": 3,
                "value": 55,
                "flags": 2,
                "unit": "MODELED_DRIVER_UNITS",
            }
            for name in CONTROLS
        ],
        "unavailable_controls": [],
        "physical_authority": False,
        "qualified": False,
        "meaning": "Modeled fixture capabilities, not measured received-unit support.",
    }


def candidate(caps):
    return {
        "schema": "rocell.camera_configuration.v1",
        "status": "STAGED_NOT_APPLIED_REHEARSAL",
        "settings_epoch": "2" * 64,
        **{
            key: caps[key]
            for key in (
                "capabilities_sha256",
                "probe_evidence_sha256",
                "endpoint_sha256",
            )
        },
        **{
            key: caps["binding"][key]
            for key in ("session_id", "source_sha256", "selected_identity_sha256")
        },
        "mode_choice_id": caps["modes"][0]["choice_id"],
        "mode": deepcopy(caps["modes"][0]["mode"]),
        "controls": [
            {"control_id": "exposure", "value": 50, "mode": "manual"},
            {"control_id": "white_balance", "value": 50, "mode": "auto"},
        ],
        "applied": False,
        "physical_authority": False,
        "qualified": False,
        "meaning": "Immutable staged request, not an applied configuration.",
    }


def probe(caps):
    return {
        "schema": "rocell.rehearsal_camera_probe_summary.v1",
        "status": "COMPLETE_PROBE_REHEARSAL",
        "evidence_sha256": caps["probe_evidence_sha256"],
        "binding": deepcopy(caps["binding"]),
        "process": process_summary()["process"],
        "native": {
            "receipt_valid": True,
            "status": "OK",
            "cleanup_confirmed": True,
            "counts": {
                "source_activation_attempts": 1,
                "source_opened": 1,
                "source_shutdown_attempts": 1,
                "control_set_attempts": 0,
                "samples_received": 0,
                "frames_written": 0,
            },
            "mode_count": len(caps["modes"]),
            "control_count": len(caps["controls"]),
        },
        "blockers": [],
        "device_cleanup_proven": False,
        "physical_authority": False,
        "qualified": False,
        "meaning": "Probe fixture only, not capture or device cleanup evidence.",
    }


def readback(config):
    return {
        "schema": "rocell.camera_readback.v1",
        "status": "REQUESTED_SETTINGS_OBSERVED_REHEARSAL",
        **{
            key: config[key]
            for key in (
                "settings_epoch",
                "probe_evidence_sha256",
                "source_sha256",
                "selected_identity_sha256",
            )
        },
        "native_receipt_sha256": "3" * 64,
        "requested_mode": deepcopy(config["mode"]),
        "observed_mode": deepcopy(config["mode"]),
        "mode_matched": True,
        "controls": [
            {
                "control_id": item["control_id"],
                "requested": {"value": item["value"], "mode": item["mode"]},
                "observed": {
                    "value": item["value"] if item["mode"] == "manual" else 65,
                    "flags": 2 if item["mode"] == "manual" else 1,
                    "unit": "MODELED_DRIVER_UNITS",
                },
                "matched": True,
                "reasons": [],
            }
            for item in config["controls"]
        ],
        "reasons": [],
        "physical_authority": False,
        "qualified": False,
        "meaning": "Unexecuted modeled readback comparison only.",
    }


def envelope(status="CONFIGURATION_STAGED"):
    caps = capabilities()
    config = candidate(caps) if status != "PROBE_COMPLETE" else None
    observed = readback(config) if status == "READBACK_COMPLETE" else None
    return {
        "schema": "rocell.wizard_camera_configuration.v1",
        "status": status,
        "probe": probe(caps),
        "capabilities": caps,
        "candidate": config,
        "readback": observed,
        "physical_authority": False,
        "qualified": False,
        "meaning": "Rehearsal reports only; no received hardware authority.",
    }


def render(value, *, old_process=False):
    projection = commissioning()
    projection["camera_configuration"] = value
    if old_process:
        projection["camera_process"] = process_summary()
    page = browser(projection)
    console = terminal(projection)
    assert page["status"] == "Local service connected"
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["controls"] == browser(commissioning())["controls"]
    return page["text"], console


@pytest.mark.parametrize(
    "status", ["PROBE_COMPLETE", "CONFIGURATION_STAGED", "READBACK_COMPLETE"]
)
def test_reported_capabilities_configuration_and_readback_remain_separate(status):
    value = envelope(status)
    page, console = render(value)
    for output in (page, console):
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "not measured support from the purchased camera" in output
        assert "Lens focus and aperture are manual physical adjustments" in output
        assert "A complete probe is not a complete capture" in output
        assert "Every reported mode; no automatic selection" in output
        assert "Six electronic controls" in output
        assert "MJPG" in output and "UNSUPPORTED_PIXEL_FORMAT" in output
        assert "REPORTED_MODE_CAPTURE_HELD" in output
        assert (
            "Reported defaults are informational and never automatically applied"
            in output
        )
        assert "Immutable candidate: staged, not applied" in output
        assert "Requested versus observed modeled readback" in output
        assert "not a fixed-value promise" in output
        assert "does not authenticate capture provenance" in output
        assert "MODELED_DRIVER_UNITS" in output or "MODELED DRIVER UNITS" in output
        for row in value["capabilities"]["modes"]:
            assert row["choice_id"] in output
        for control in CONTROLS:
            assert control.replace("_", " ") in output
    assert "CAMERA CONFIGURATION NOT VERIFIED" not in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" not in console


def test_existing_camera_process_card_remains_separate_and_unchanged():
    page, console = render(envelope(), old_process=True)
    for output in (page, console):
        assert "Contained camera-process rehearsal" in output
        assert "Modeled camera capabilities and configuration" in output
        assert "Synthetic native receipt and cleanup" in output


def test_unreported_control_has_no_inferred_range_and_flags_three_are_ambiguous():
    value = envelope()
    caps = value["capabilities"]
    caps["controls"] = [
        item for item in caps["controls"] if item["control_id"] != "gain"
    ]
    caps["unavailable_controls"] = ["gain"]
    caps["controls"][0]["flags"] = 3
    value["probe"]["native"]["control_count"] = 5
    page, console = render(value)
    for output in (page, console):
        assert (
            "UNAVAILABLE NOT REPORTED" in output or "UNAVAILABLE_NOT_REPORTED" in output
        )
        assert "Current flags 3 are ambiguous, not a confirmed active mode" in output
    assert "AMBIGUOUS AUTO AND MANUAL" in page
    assert "AMBIGUOUS_AUTO_AND_MANUAL" in console


def test_incomplete_probe_never_manufactures_capabilities_or_capture():
    value = envelope()
    value.update(status="HELD", capabilities=None, candidate=None)
    value["probe"].update(
        status="INCOMPLETE_PROBE_REHEARSAL",
        process=None,
        native=None,
        blockers=["OWNED_PROCESS_RESULT_UNAVAILABLE"],
    )
    page, console = render(value)
    for output in (page, console):
        assert (
            "CAPABILITIES UNAVAILABLE" in output or "CAPABILITIES_UNAVAILABLE" in output
        )
        assert "No reported modes or control limits are inferred" in output
        assert "5472" not in output
    assert "CAMERA CONFIGURATION NOT VERIFIED" not in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" not in console


@pytest.mark.parametrize(
    "fault", ["manual-value", "missing", "wrong-flag", "capability-drift"]
)
def test_mismatching_readback_preserves_requested_and_observed_values(fault):
    value = envelope("READBACK_COMPLETE")
    value["status"] = "HELD"
    report = value["readback"]
    report.update(
        status="READBACK_MISMATCH_REHEARSAL", reasons=["CONTROL_READBACK_MISMATCH"]
    )
    row = report["controls"][0]
    row["matched"] = False
    if fault == "manual-value":
        row["observed"]["value"] = 55
        row["reasons"] = ["MANUAL_VALUE_READBACK_MISMATCH"]
    elif fault == "missing":
        row["observed"] = None
        row["reasons"] = ["CONTROL_READBACK_MISSING"]
    elif fault == "wrong-flag":
        row["observed"]["flags"] = 3
        row["reasons"] = ["CONTROL_MODE_READBACK_MISMATCH"]
    else:
        row["observed"]["unit"] = "CHANGED_MODELED_UNIT"
        row["reasons"] = ["CONTROL_CAPABILITY_DRIFT"]
    page, console = render(value)
    for output in (page, console):
        assert row["reasons"][0] in output
        assert "requested" in output and "observed" in output
    assert "CAMERA CONFIGURATION NOT VERIFIED" not in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" not in console


@pytest.mark.parametrize("count", [0, 128])
def test_all_reported_modes_are_bounded_and_opaque_without_default_selection(count):
    value = envelope("PROBE_COMPLETE")
    value["capabilities"]["modes"] = [
        {
            "choice_id": f"mode-{index:024x}",
            "mode": mode(),
            "selectable": True,
            "blockers": [],
        }
        for index in range(count)
    ]
    value["probe"]["native"]["mode_count"] = count
    page, console = render(value)
    for row in value["capabilities"]["modes"]:
        assert row["choice_id"] in page and row["choice_id"] in console
    assert "CAMERA CONFIGURATION NOT VERIFIED" not in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" not in console


@pytest.mark.parametrize("bad", [None, {}, [], True, "raw projection"])
def test_absent_or_invalid_top_projection_does_not_render_arbitrary_details(bad):
    page, console = render(bad)
    if bad is None:
        assert "Modeled camera capabilities and configuration" not in page
        assert "Modeled camera capabilities and configuration" not in console
    else:
        assert "CAMERA CONFIGURATION NOT VERIFIED" in page
        assert "CAMERA_CONFIGURATION_NOT_VERIFIED" in console


@pytest.mark.parametrize(
    "path,bad",
    [
        (("schema",), "unreviewed"),
        (("status",), "APPLIED"),
        (("physical_authority",), True),
        (("qualified",), 0),
        (("meaning",), "x" * 513),
        (("probe", "evidence_sha256"), "9" * 64),
        (("probe", "binding", "source_sha256"), "9" * 64),
        (("probe", "process", "created"), False),
        (("probe", "native", "mode_count"), True),
        (("probe", "native", "control_count"), 5),
        (("probe", "native", "counts", "control_set_attempts"), 1),
        (("probe", "native", "counts", "samples_received"), 1),
        (("probe", "native", "counts", "source_opened"), 0),
        (("capabilities", "modes", 0, "mode", "width"), True),
        (("capabilities", "modes", 0, "mode", "width"), 5473),
        (("capabilities", "modes", 0, "mode", "height"), 16384),
        (("capabilities", "modes", 0, "mode", "stride_bytes"), 1),
        (("capabilities", "modes", 0, "mode", "fps_numerator"), 1.0),
        (("capabilities", "modes", 1, "selectable"), True),
        (("capabilities", "controls", 0, "capability_flags"), 4),
        (("capabilities", "controls", 0, "capability_flags"), "3"),
        (("capabilities", "controls", 0, "flags"), 0),
        (("capabilities", "controls", 0, "flags"), True),
        (("capabilities", "controls", 0, "minimum"), 101),
        (("capabilities", "controls", 0, "step"), 0),
        (("capabilities", "controls", 0, "unit"), "x" * 65),
        (("capabilities", "controls", 0, "unit"), "é" * 33),
        (("capabilities", "controls", 0, "control_id"), "focus"),
        (("capabilities", "unavailable_controls"), ["gain"]),
        (("candidate", "applied"), True),
        (("candidate", "settings_epoch"), "A" * 64),
        (("candidate", "source_sha256"), "9" * 64),
        (("candidate", "capabilities_sha256"), "9" * 64),
        (("candidate", "mode_choice_id"), "mode-" + "1" * 24),
        (("candidate", "mode", "width"), 640),
        (("candidate", "controls", 0, "value"), 52),
        (("candidate", "controls", 0, "mode"), "automatic"),
        (("readback", "settings_epoch"), "9" * 64),
        (("readback", "controls", 0, "observed", "flags"), 4),
        (("readback", "controls", 0, "observed", "value"), 55),
        (("readback", "controls", 0, "observed", "unit"), "UNVERIFIED_UNIT"),
        (("readback", "controls", 0, "requested", "value"), True),
        (("readback", "controls", 0, "observed"), None),
        (("readback", "controls", 0, "matched"), "true"),
        (("readback", "controls", 0, "reasons"), ["UNKNOWN_CONTROL_FLAG"]),
        (("readback", "observed_mode"), None),
        (("readback", "mode_matched"), False),
    ],
)
def test_malformed_coerced_unknown_or_stale_fields_are_withheld(path, bad):
    value = envelope("READBACK_COMPLETE")
    item = value
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = bad
    page, console = render(value)
    assert "CAMERA CONFIGURATION NOT VERIFIED" in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" in console


@pytest.mark.parametrize(
    "section", [None, "probe", "capabilities", "candidate", "readback"]
)
def test_unknown_fields_and_private_paths_cannot_fall_through_generic_json(section):
    value = envelope("READBACK_COMPLETE")
    item = value if section is None else value[section]
    item["symbolic_link"] = "NEVER_RENDER_RAW_ENDPOINT_OR_CHILD_ARGUMENTS"
    page, console = render(value)
    for output in (page, console):
        assert "NEVER_RENDER_RAW_ENDPOINT_OR_CHILD_ARGUMENTS" not in output
    assert "CAMERA CONFIGURATION NOT VERIFIED" in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" in console


def test_plain_text_is_escaped_and_does_not_add_control_actions():
    value = envelope()
    value["meaning"] = '<img src="probe" onerror="capture()"> modeled only'
    page, console = render(value)
    assert value["meaning"] in page
    assert json.dumps(value["meaning"]) in console


def test_actual_pure_probe_configuration_and_readback_producers_render_without_io(
    monkeypatch,
):
    from test_camera_configuration import configuration_inputs
    from rocell.application.camera_configuration import compare_camera_readback
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker

    def forbidden(*args, **kwargs):
        raise AssertionError("Presentation must not run a probe, capture or child")

    monkeypatch.setattr(OwnedWindowsWorker, "run", forbidden)
    monkeypatch.setattr(WindowsCameraWorkerClient, "probe", forbidden)
    monkeypatch.setattr(WindowsCameraWorkerClient, "capture", forbidden)
    _, actual_probe, caps, config, receipt = configuration_inputs()
    actual_readback = compare_camera_readback(
        config, receipt, expected_settings_epoch=config.settings_epoch
    )
    assert actual_readback["status"] == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
    value = {
        "schema": "rocell.wizard_camera_configuration.v1",
        "status": "READBACK_COMPLETE",
        "probe": actual_probe.view(),
        "capabilities": caps.view(),
        "candidate": config.view(),
        "readback": actual_readback,
        "physical_authority": False,
        "qualified": False,
        "meaning": "Actual pure producers with unexecuted typed process/readback metadata; not a received-camera observation.",
    }
    page, console = render(value)
    assert "CAMERA CONFIGURATION NOT VERIFIED" not in page
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" not in console
    for output in (page, console):
        assert (
            actual_probe.evidence_sha256 in output and config.settings_epoch in output
        )
        assert actual_readback["native_receipt_sha256"] in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output


def test_actual_arrival_cached_projection_and_dynamic_fields_render_without_dispatch(
    make_service,
):
    """Inject producer artifacts, not a fake durable transaction or stage PASS."""
    from test_camera_configuration import configuration_inputs
    from test_arrival_wizard_device_selection_ui import browser as action_browser
    from test_arrival_wizard_terminal import Service, run
    from rocell.application.camera_configuration import compare_camera_readback

    service, runner, _ = make_service()
    _, actual_probe, caps, config, receipt = configuration_inputs()
    commissioning_service = service._commissioning
    commissioning_service._camera_probe = actual_probe
    commissioning_service._electronic_configuration = config
    commissioning_service._camera_readback = compare_camera_readback(
        config, receipt, expected_settings_epoch=config.settings_epoch
    )
    commissioning_service._cached["camera_configuration"] = (
        commissioning_service._configuration_projection()
    )
    snapshot = service.view()
    projected = snapshot["commissioning_rehearsal"]["camera_configuration"]
    assert projected["status"] == "READBACK_COMPLETE"
    configured = next(
        item
        for item in snapshot["actions"]
        if item["action_id"] == "rehearsal_camera_configuration"
    )
    assert not configured["enabled"]  # No M1 store was initialized by this test.
    fields = {item["name"]: item for item in configured["fields"]}
    assert len(fields) == 13
    assert "default" not in fields["mode_choice_id"]
    assert (
        fields["mode_choice_id"]["options"][0]["value"]
        == config.view()["mode_choice_id"]
    )
    for control in caps.view()["controls"]:
        cid = control["control_id"]
        assert fields[cid + "_mode"]["default"] == "unchanged"
        number = fields[cid + "_value"]
        assert (number["min"], number["max"], number["step"], number["default"]) == (
            control["minimum"],
            control["maximum"],
            control["step"],
            control["value"],
        )

    class CachedSnapshot(Service):
        def view(self):
            self.calls.append(("view",))
            return deepcopy(snapshot)

    page = action_browser(None, "commissioning", snapshot=snapshot)
    cached = CachedSnapshot()
    code, lines, _ = run(cached, ["view", "quit"])
    console = "\n".join(lines)
    assert code == 0 and cached.calls == [("view",), ("view",)]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert "CAMERA CONFIGURATION NOT VERIFIED" not in page["text"]
    assert "CAMERA_CONFIGURATION_NOT_VERIFIED" not in console
    assert config.settings_epoch in page["text"] and config.settings_epoch in console
    assert runner.calls == []
    choice = next(
        item
        for item in page["controls"]
        if item["id"] == "field-rehearsal_camera_configuration-mode_choice_id"
    )
    assert choice["value"] == ""
    assert not any(
        option["selected"] for option in choice["options"] if option["value"]
    )


@pytest.mark.parametrize("confirmation", ["", "no", "yes"])
def test_actual_dynamic_fields_use_explicit_mode_and_unchanged_intent(confirmation):
    """Generic frontend dispatch is a double; backend authorization is not bypassed."""
    from test_camera_configuration import configuration_inputs
    from test_arrival_wizard_device_selection_ui import browser as action_browser
    from test_arrival_wizard_terminal import Service, action, dispatched, run
    from rocell.application.wizard_camera_configuration import configuration_fields

    _, _, caps, config, _ = configuration_inputs()
    fields = list(configuration_fields(caps))
    definition = action("rehearsal_camera_configuration", fields=fields)
    definition["section"] = "commissioning"
    fixture = Service([definition])
    snapshot = fixture.view()
    values = {field["name"]: field["default"] for field in fields if "default" in field}
    values["mode_choice_id"] = config.view()["mode_choice_id"]
    blocked = action_browser(
        None,
        "commissioning",
        snapshot=snapshot,
        action=definition["action_id"],
        prepare=True,
    )
    assert not any(item["method"] == "POST" for item in blocked["requests"])
    page = action_browser(
        None,
        "commissioning",
        snapshot=snapshot,
        action=definition["action_id"],
        values=values,
        prepare=True,
        execute=confirmation == "yes",
    )
    prepared = [item for item in page["requests"] if item["path"] == "/api/prepare"]
    assert len(prepared) == 1 and prepared[0]["body"]["input"] == values
    assert sum(item["path"] == "/api/execute" for item in page["requests"]) == (
        confirmation == "yes"
    )
    fixture.calls.clear()
    code, _, _ = run(
        fixture,
        [definition["action_id"], values["mode_choice_id"]]
        + [""] * (len(fields) - 1)
        + [confirmation, "quit"],
    )
    assert code == 0
    assert dispatched(fixture, "prepare") == [
        ("prepare", definition["action_id"], values, 7)
    ]
    assert len(dispatched(fixture, "execute")) == (confirmation == "yes")
    for cid in CONTROLS:
        assert values[cid + "_mode"] == "unchanged"


def test_blank_terminal_mode_does_not_infer_the_first_reported_choice():
    from test_camera_configuration import configuration_inputs
    from test_arrival_wizard_terminal import Service, action, dispatched, run
    from rocell.application.wizard_camera_configuration import configuration_fields

    _, _, caps, _, _ = configuration_inputs()
    fixture = Service(
        [
            action(
                "rehearsal_camera_configuration",
                fields=list(configuration_fields(caps)),
            )
        ]
    )
    code, _, _ = run(fixture, ["1", "", "quit"])
    assert code == 0 and not dispatched(fixture, "prepare")
    assert not dispatched(fixture, "execute")
