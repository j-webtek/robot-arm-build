"""Restart presentation only: no discovery, storage qualification or devices."""

from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from time import monotonic_ns

import pytest

from rocell.ui.terminal import _PhysicalSetupDisplay
from test_arrival_wizard_device_selection_ui import MetadataService, browser, selection
from test_arrival_wizard_terminal import action, run
from test_physical_camera_session import session_fixture
from test_wizard_physical_camera_setup_ui import (
    complete_setup,
    prerequisite_summary,
    render,
    setup,
)


CURRENT = "wizard-" + "b" * 32


def registry(launch, source):
    return {
        "schema": "rocell.physical_camera_reopen_registry.v1",
        "status": "NOT_DISCOVERED",
        "current_launch_id": launch,
        "source_sha256": source,
        "discovery_sha256": None,
        "stores": [],
        "issues": [],
        "invalidation_reason": None,
        "physical_authority": False,
        "device_io_performed": False,
        "meaning": "Cached bounded store metadata only, not opened storage.",
    }


def row(index=1, *, matching=True):
    return {
        "choice_id": f"reopen-{index:032x}" if matching else None,
        "origin_launch_id": f"wizard-{index:032x}",
        "cell_id": f"wizard-physical-camera-{index:016x}",
        "session_id": f"physical-camera-{index:032x}",
        # This is an opaque camera-domain hash, not a raw workspace hash.
        "source_binding_sha256": "c" * 64,
        "header_sha256": "d" * 64,
        "descriptor_sha256": "e" * 64,
        "source_matches": matching,
        "selectable": matching,
        "status": "METADATA_DISCOVERED_NOT_OPENED" if matching else "SOURCE_DRIFT_HELD",
        "physical_authority": False,
    }


def version_two(data, *, reopened=False):
    value = deepcopy(data)
    value["schema"] = "rocell.wizard_physical_camera_setup.v2"
    value["origin_launch_id"] = value["session"]["binding"]["launch_id"]
    if reopened:
        value["launch_session_id"] = CURRENT
    value["requirements_provenance"] = (
        "NONE"
        if value["prerequisites"] is None
        else "REOPENED_ORIGINAL_CONTEXT" if reopened else "CURRENT_LAUNCH_ORIGINAL"
    )
    value["reopening"] = registry(value["launch_session_id"], value["source_sha256"])
    return value


@pytest.fixture
def reopened(complete_setup):
    # Actual fixed-file requirements with modeled storage facts. This is not
    # a second NTFS initialization or proof that a store has been reopened.
    return version_two(complete_setup, reopened=True)


def test_v2_initial_state_does_not_infer_discovery_or_open(tmp_path):
    value = version_two(setup(session_fixture(tmp_path)))
    assert _PhysicalSetupDisplay.setup(value) == value
    page, console = render(value)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "No existing store was inferred or selected" in text
        assert "No choice is selected automatically" in text
        assert "does not qualify or open storage" in text
        assert "NO PHYSICAL AUTHORITY" in text


def test_reopened_original_requirements_keep_origin_and_current_launch_distinct(
    reopened,
):
    assert reopened["prerequisites"]["binding"]["launch_session_id"] != CURRENT
    assert _PhysicalSetupDisplay.setup(reopened) == reopened
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert CURRENT in text and reopened["origin_launch_id"] in text
        assert "The original store was explicitly selected for reopening" in text
        assert "storage audit and current publication are separate" in text
        assert "Historical original requirements" in text
        assert "not current-launch observations" in text
        assert "not current camera identity, configuration, image, connection" in text
        assert "INT-005: measurement" in text
        assert "Acceptance is DEFERRED" in text
        assert "UNKNOWN" in text


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_reopened_current_requirements_are_hidden_until_publication(
    reopened, publication
):
    original_hash = reopened["prerequisites"]["evidence_sha256"]
    reopened["prerequisites"] = None
    reopened["requirements_provenance"] = "NONE"
    reopened["publication"]["status"] = publication
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "Current prerequisite details are withheld" in text
        assert "INT-005: measurement" not in text
        assert original_hash not in text


def test_discovered_metadata_eligibility_and_source_drift_are_separate(reopened):
    reopened["reopening"].update(
        status="DISCOVERED",
        discovery_sha256="f" * 64,
        stores=[row(), row(2, matching=False)],
        issues=[
            {
                "store_label": None,
                "code": "UNSAFE_PATH",
                "meaning": "Unsafe entry withheld.",
            }
        ],
    )
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "METADATA ONLY / NOT OPENED" in text
        assert "SOURCE DRIFT / REOPEN HELD" in text
        assert "It has no selectable token" in text
        assert "UNSAFE_PATH" in text
        assert "reopen-" + "0" * 31 + "1" in text


@pytest.mark.parametrize("status", ["HELD", "INVALIDATED"])
def test_registry_hold_or_invalidation_is_not_a_reopen(reopened, status):
    value = reopened["reopening"]
    value["status"] = status
    if status == "HELD":
        value["issues"] = [
            {
                "store_label": None,
                "code": "DEADLINE_EXPIRED",
                "meaning": "Metadata deadline elapsed.",
            }
        ]
    else:
        value["invalidation_reason"] = "REGISTRY_INVALIDATED"
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "No current selectable store metadata" in text


@pytest.mark.parametrize(
    "path,value",
    [
        (("origin_launch_id",), CURRENT),
        (("requirements_provenance",), "CURRENT_LAUNCH_ORIGINAL"),
        (("requirements_provenance",), "NONE"),
        (("requirements_provenance",), "QUALIFIED"),
        (("reopening", "current_launch_id"), "wizard-" + "c" * 32),
        (("reopening", "source_sha256"), "f" * 64),
        (("reopening", "physical_authority"), True),
        (("reopening", "device_io_performed"), 0),
        (("reopening", "status"), "OPENED"),
        (("reopening", "invalidation_reason"), "RAW_SENTINEL"),
        (("reopening", "extra"), "RAW_SENTINEL"),
        (("reopening", "stores"), [row()]),
        (("prerequisites", "binding", "launch_session_id"), CURRENT),
        (("publication", "status"), "PENDING"),
    ],
)
def test_bad_v2_binding_or_authority_is_withheld(reopened, path, value):
    node = reopened
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert _PhysicalSetupDisplay.setup(reopened) is None
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" in text
        assert "RAW_SENTINEL" not in text
        assert "INT-005: measurement" not in text


@pytest.mark.parametrize(
    "field,value",
    [
        ("choice_id", "../../RAW_SENTINEL"),
        ("source_matches", 1),
        ("selectable", 1),
        ("status", "CONNECTED"),
        ("physical_authority", True),
        ("header_sha256", "x" * 64),
        ("extra", "RAW_SENTINEL"),
    ],
)
def test_bad_store_row_never_becomes_a_qualified_device(reopened, field, value):
    candidate = row()
    candidate[field] = value
    reopened["reopening"].update(
        status="DISCOVERED", discovery_sha256="f" * 64, stores=[candidate]
    )
    assert _PhysicalSetupDisplay.setup(reopened) is None
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" in text
        assert "RAW_SENTINEL" not in text


@pytest.mark.parametrize("count,valid", [(32, True), (33, False)])
def test_store_count_bound(reopened, count, valid):
    reopened["reopening"].update(
        status="DISCOVERED",
        discovery_sha256="f" * 64,
        stores=[row(index + 1) for index in range(count)],
    )
    assert (_PhysicalSetupDisplay.setup(reopened) is not None) is valid
    page, console = render(reopened)
    assert ("PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in page) is valid
    assert ("PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in console) is valid


@pytest.mark.parametrize("count,valid", [(33, True), (34, False)])
def test_issue_count_bound(reopened, count, valid):
    reopened["reopening"].update(
        status="HELD",
        issues=[
            {
                "store_label": None,
                "code": "UNRECOGNIZED_ENTRY",
                "meaning": "Fixed unrecognized entry diagnostic.",
            }
            for _ in range(count)
        ],
    )
    assert (_PhysicalSetupDisplay.setup(reopened) is not None) is valid
    page, console = render(reopened)
    assert ("PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in page) is valid
    assert ("PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in console) is valid


@pytest.mark.parametrize(
    "failure",
    ["duplicate-origin", "duplicate-choice", "issue-path", "issue-code", "issue-extra"],
)
def test_ambiguous_or_unsafe_metadata_is_withheld(reopened, failure):
    one, two = row(), row(2)
    issues = [
        {
            "store_label": None,
            "code": "UNSAFE_PATH",
            "meaning": "Unsafe entry withheld.",
        }
    ]
    if failure == "duplicate-origin":
        two["origin_launch_id"] = one["origin_launch_id"]
    elif failure == "duplicate-choice":
        two["choice_id"] = one["choice_id"]
    elif failure == "issue-path":
        issues[0]["store_label"] = "../RAW_SENTINEL"
    elif failure == "issue-code":
        issues[0]["code"] = "RAW_SENTINEL"
    else:
        issues[0]["extra"] = "RAW_SENTINEL"
    reopened["reopening"].update(
        status="DISCOVERED", discovery_sha256="f" * 64, stores=[one, two], issues=issues
    )
    assert _PhysicalSetupDisplay.setup(reopened) is None
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" in text
        assert "RAW_SENTINEL" not in text


def test_legacy_v1_export_does_not_invent_a_current_launch(complete_setup):
    page, console = render(complete_setup)
    for text in (page, console):
        assert "Legacy v1 read-only snapshot" in text
        assert "restart adoption is not established" in text
        assert "The original store was explicitly adopted" not in text


def test_generic_reopen_form_has_no_default_choice_and_preview_never_opens(reopened):
    selected = row()
    reopened["reopening"].update(
        status="DISCOVERED", discovery_sha256="f" * 64, stores=[selected]
    )
    item = action(
        "physical_camera_reopen",
        fields=[
            {
                "name": "choice_id",
                "type": "select",
                "label": "Original camera store",
                "required": True,
                "options": [
                    {
                        "value": selected["choice_id"],
                        "label": "Original session metadata",
                    }
                ],
            },
            {
                "name": "operator_id",
                "type": "text",
                "label": "Operator",
                "required": True,
                "max_length": 64,
            },
        ],
    )
    item["section"] = "camera"
    view = MetadataService(selection()).view()
    view.update(mode="physical", physical_camera_setup=reopened, actions=[item])
    initial = browser(selection(), "camera", snapshot=view)
    control = next(field for field in initial["controls"] if field["tag"] == "SELECT")
    assert control["value"] == "" and control["options"][0]["selected"]
    preview = browser(
        selection(),
        "camera",
        snapshot=view,
        prepare=True,
        action="physical_camera_reopen",
        values={"choice_id": selected["choice_id"], "operator_id": "operator"},
    )
    assert [request["path"] for request in preview["requests"]] == [
        "/api/view",
        "/api/prepare",
    ]
    assert preview["requests"][-1]["body"]["input"] == {
        "choice_id": selected["choice_id"],
        "operator_id": "operator",
    }
    service = MetadataService(selection())
    service.actions = [item]
    code, _, _ = run(service, ["physical_camera_reopen", "1", "operator", "", "quit"])
    assert code == 0
    assert [call for call in service.calls if call[0] == "prepare"] == [
        (
            "prepare",
            "physical_camera_reopen",
            {"choice_id": selected["choice_id"], "operator_id": "operator"},
            7,
        )
    ]
    assert not any(call[0] == "execute" for call in service.calls)


def test_actual_registry_initial_missing_root_and_invalidation_views(
    tmp_path, monkeypatch, reopened
):
    from rocell.application import physical_camera_reopen_registry as module

    def forbidden(*args, **kwargs):
        pytest.fail("Registry construction/status performed filesystem I/O")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            guard.setattr(Path, name, forbidden)
        owner = module.PhysicalCameraReopenRegistry(
            tmp_path, current_launch_id=CURRENT, source_sha256=reopened["source_sha256"]
        )
        initial = owner.view()
    assert initial["status"] == "NOT_DISCOVERED"
    reopened["reopening"] = initial
    assert _PhysicalSetupDisplay.setup(reopened) == reopened
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: reopened["source_sha256"]
    )
    # Only this explicit call checks the empty assigned metadata root. It must
    # neither initialize M1 nor create the missing root as a side effect.
    observed = owner.discover(
        cancellation=Event(), deadline_ns=monotonic_ns() + 10_000_000_000
    )
    assert observed["status"] == "DISCOVERED"
    assert observed["stores"] == []
    assert [item["code"] for item in observed["issues"]] == ["NO_STORE_ROOT"]
    assert not owner.root.exists()
    reopened["reopening"] = observed
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "NO_STORE_ROOT" in text
    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            guard.setattr(Path, name, forbidden)
        owner.invalidate("STALE_CHOICE")
        invalidated = owner.view()
    reopened["reopening"] = invalidated
    page, console = render(reopened)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "STALE_CHOICE" in text


def test_actual_metadata_registry_through_setup_publication_and_both_renderers(
    tmp_path, monkeypatch
):
    from rocell.application import physical_camera_reopen_registry as registry_module
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.application.physical_camera_setup_service import (
        PhysicalCameraSetupService,
    )
    from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
    from rocell.application.wizard_native_camera_enrollment import (
        WizardNativeCameraEnrollment,
    )
    from test_physical_camera_reopen_registry import metadata_store

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata discovery/UI must not open or initialize M1")

    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "open", forbidden)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "initialize", forbidden)
    source = "a" * 64
    # Self-consistent modeled historical metadata only. There is no real M1
    # qualification, original-session adoption, or device operation here.
    metadata_store(tmp_path, source=source)
    metadata_store(tmp_path, origin="wizard-" + "3" * 32, source="f" * 64)
    monkeypatch.setattr(registry_module, "source_fingerprint", lambda _: source)
    acquisition = PhysicalCameraAcquisitionService(
        tmp_path, launch_id=CURRENT, source_sha256=source, mode="physical"
    )
    service = PhysicalCameraSetupService(acquisition)
    enrollment = WizardNativeCameraEnrollment("physical", CURRENT, source, None)
    result = service.perform(
        "physical_camera_discover",
        expected_context_sha256=service.context_sha256(
            "physical_camera_discover", enrollment, None
        ),
        operator_id="operator",
        enrollment=enrollment,
        source_report=None,
        cancellation=Event(),
        progress=lambda _: None,
    )
    retained = result["steps"][0]["report"]["reopening"]
    assert retained["status"] == "DISCOVERED"
    assert [row["source_matches"] for row in retained["stores"]] == [True, False]
    assert retained["stores"][1]["choice_id"] is None
    pending = service.view()
    assert pending["publication"]["status"] == "PENDING"
    assert pending["reopening"]["status"] == "NOT_DISCOVERED"
    assert service.reopen_choices() == []
    page, console = render(pending)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert retained["stores"][0]["choice_id"] not in text
    # Model the outer completed-log callback only; real Arrival log durability
    # and original M1 reopening are covered by the parent's public integration.
    service.publication_completed("discovery-completion")
    current = service.view()
    assert current["reopening"] == retained
    assert len(service.reopen_choices()) == 1
    page, console = render(current)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "METADATA ONLY / NOT OPENED" in text
        assert "SOURCE DRIFT / REOPEN HELD" in text
        assert retained["stores"][0]["choice_id"] in text
        assert "The original store was explicitly adopted" not in text
    assert result["steps"][0]["report"]["reopening"] == retained


@pytest.mark.parametrize("publication", ["CURRENT", "PENDING", "HISTORICAL_HELD"])
def test_actual_two_launch_public_export_preserves_original_context(publication):
    """Render the actual local restart export without reopening its M1 store.

    CURRENT uses the unmodified exported view. The pending/historical cases are
    display-only variations; no new durable workflow or device action is claimed.
    """
    report = (
        Path(__file__).resolve().parents[3]
        / "software/runs/wizard-exports"
        / "wizard-20260908T113927491670Z-298e4011553c48d5b3198f578001111a"
        / "report.json"
    )
    if not report.is_file():
        pytest.skip("Local two-launch public restart export is not present")
    view = json.loads(report.read_text(encoding="utf-8"))["snapshot"]
    value = view["physical_camera_setup"]
    assert view["mode"] == "physical"
    assert [row["state"] for row in view["stages"]] == ["PHYSICAL_PENDING"] * 15
    assert value["schema"] == "rocell.wizard_physical_camera_setup.v2"
    assert value["source_sha256"] == view["source_binding_sha256"]
    assert value["launch_session_id"] != value["origin_launch_id"]
    assert value["session"]["binding"]["launch_id"] == value["origin_launch_id"]
    assert (
        value["prerequisites"]["binding"]["launch_session_id"]
        == value["origin_launch_id"]
    )
    assert value["requirements_provenance"] == "REOPENED_ORIGINAL_CONTEXT"
    assert value["publication"]["status"] == "CURRENT"
    assert value["session"]["stages"][0]["state"] == "WAITING_OPERATOR"
    assert [row["state"] for row in value["session"]["stages"][1:]] == ["PENDING"] * 14
    evidence_hash = value["prerequisites"]["evidence_sha256"]
    if publication != "CURRENT":
        value.update(prerequisites=None, requirements_provenance="NONE")
        value["publication"]["status"] = publication
    assert _PhysicalSetupDisplay.setup(value) == value
    original = deepcopy(view)
    rendered = browser(selection(), "camera", snapshot=view)
    assert rendered["status"] == "Local service connected", rendered["error"]
    assert rendered["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None}
    ]
    service = MetadataService(selection())

    def cached_view():
        service.calls.append(("view",))
        return deepcopy(view)

    service.view = cached_view
    code, output, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)]
    console = "\n".join(output)
    assert console.count('"recorded_state": "WAITING_OPERATOR"') == 1
    assert console.count('"recorded_state": "PENDING"') == 14
    for text in (rendered["text"], console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert value["origin_launch_id"] in text and value["launch_session_id"] in text
        assert "The original store was explicitly selected for reopening" in text
        assert "storage audit and current publication are separate" in text
        assert "NO PHYSICAL AUTHORITY" in text
        assert "The original store was explicitly adopted" not in text
        if publication == "CURRENT":
            assert "Historical original requirements" in text
            assert "not current-launch observations" in text
            assert (
                "not current camera identity, configuration, image, connection" in text
            )
            assert "INT-005: measurement" in text and "Acceptance is DEFERRED" in text
            assert evidence_hash in text
        else:
            assert "Current prerequisite details are withheld" in text
            assert "Historical original requirements" not in text
            assert "INT-005: measurement" not in text
            assert evidence_hash not in text
    assert view == original
