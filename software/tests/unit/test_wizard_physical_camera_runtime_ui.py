"""Cached runtime-file presentation, not native/device qualification.

These modeled compact views exercise the real JS fake-DOM and terminal paths.
Actual inspector/service producer joins are tested separately below when present.
"""

from copy import deepcopy

import pytest

from rocell.ui.terminal import _PhysicalCameraRuntimeDisplay
from test_arrival_wizard_device_selection_ui import MetadataService, browser, selection
from test_arrival_wizard_terminal import Service, action, dispatched, run
from test_wizard_physical_camera_ui import physical, snapshot


SOURCE = "a" * 64
LAUNCH = "wizard-" + "1" * 32
REPORT = "b" * 64
SOURCE_PATH = "software/native/windows_camera/camera_worker.cpp"
FALSE_FLAGS = (
    "dispatch_enabled",
    "driver_qualified",
    "hardware_qualified",
    "connected",
    "physical_authority",
)


def inspection(*, matched=False):
    row = {
        "purpose": "capture",
        "binary_status": "MATCHED",
        "build_status": "MATCHED",
        "source_status": "MATCHED",
        "artifact_status": "MATCHED",
        "source_counts": {"total": 9, "matched": 9, "gaps": 0, "unverified": 0},
        "artifact_counts": {"total": 4, "matched": 4, "gaps": 0, "unverified": 0},
        "gaps": [],
    }
    probe = deepcopy(row)
    probe["purpose"] = "probe"
    if not matched:
        probe["source_status"] = "GAPS"
        probe["source_counts"].update(matched=8, gaps=1)
        probe["gaps"] = [{"relative_path": SOURCE_PATH, "reason": "HASH_MISMATCH"}]
    return {
        "schema": "rocell.physical_camera_runtime_inspection_summary.v1",
        "operator_id": "inspector_exact_label",
        "source_sha256": SOURCE,
        "launch_session_id": LAUNCH,
        "report_sha256": REPORT,
        "status": "FILES_MATCHED" if matched else "HELD",
        "purposes": {"probe": probe, "capture": row},
        "coverage": {"planned_paths": 27, "observed_paths": 27, "unobserved_paths": 0},
        **dict.fromkeys(FALSE_FLAGS, False),
    }


def wrapper(*, matched=False, reviewed=False):
    result = {
        "schema": "rocell.wizard_physical_camera_runtime_review.v1",
        "status": "REVIEW_RECORDED" if reviewed else "INSPECTION_RETAINED",
        "inspection": inspection(matched=matched),
        "review": None,
        "publication": {"status": "CURRENT", "operation_id": "inspect-op"},
        **dict.fromkeys(FALSE_FLAGS, False),
        "meaning": "Fixed-file observations and review only; no runtime release.",
    }
    if reviewed:
        result["review"] = {
            "reviewer_id": "reviewer_exact_label",
            "review_operation_id": "review-op",
            "inspection_sha256": REPORT,
            "status": (
                "ACKNOWLEDGED_FILE_MATCH" if matched else "ACKNOWLEDGED_HELD_REPORT"
            ),
            "distinct_operator_labels": True,
        }
        result["publication"]["operation_id"] = "review-op"
    return result


def view_for(value):
    camera = physical()
    camera["runtime_inspection"] = value
    view = snapshot(camera)
    view["session_id"] = LAUNCH
    return view


def render(value, *, view_changes=None, camera=None):
    view = view_for(value)
    if camera is not None:
        view["physical_camera"] = deepcopy(camera)
    view.update(view_changes or {})
    page = browser(selection(), "camera", snapshot=view)
    assert page["status"] == "Local service connected", page["error"]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert not page["dialogOpen"]
    service = MetadataService(selection())

    def cached():
        service.calls.append(("view",))
        return deepcopy(view)

    service.view = cached
    code, lines, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)]
    assert service.shutdown_count == 0
    return page["text"], "\n".join(lines)


@pytest.mark.parametrize("reviewed", [False, True])
def test_mixed_probe_source_gap_and_capture_match_are_not_runtime_release(reviewed):
    value = wrapper(reviewed=reviewed)
    original = deepcopy(value)
    assert _PhysicalCameraRuntimeDisplay.projection(value, SOURCE, LAUNCH) == value
    for text in render(value):
        assert "Runtime pair file inspection and review" in text
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        assert "probe: executable pin MATCHED; build-record pin MATCHED" in text
        assert "probe: source closure GAPS; declared artifacts MATCHED" in text
        assert "capture: source closure MATCHED; declared artifacts MATCHED" in text
        assert "inspector_exact_label" in text
        assert SOURCE_PATH in text and "HASH_MISMATCH" in text
        assert "No executable was launched" in text
        assert "NOT_CONNECTED / NOT_QUALIFIED / DISPATCH_DISABLED" in text
        if reviewed:
            assert "reviewer_exact_label" in text and "ACKNOWLEDGED_HELD_REPORT" in text
    assert value == original


@pytest.mark.parametrize("matched", [False, True])
def test_review_preserves_report_result_and_never_grants_runtime_release(matched):
    for text in render(wrapper(matched=matched, reviewed=True)):
        assert (
            "ACKNOWLEDGED_FILE_MATCH" if matched else "ACKNOWLEDGED_HELD_REPORT"
        ) in text
        assert "Labels record procedure, not authenticated independent people" in text
        assert "File agreement is not runtime admission" in text


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_unpublished_or_historical_report_is_never_current(publication):
    value = wrapper(reviewed=True)
    value["publication"]["status"] = publication
    if publication == "PENDING":
        value["status"] = "INSPECTION_RETAINED"
        value["review"] = None
    if publication == "HISTORICAL_HELD":
        value["status"] = publication
        value["inspection"]["source_sha256"] = "f" * 64
        value["inspection"]["launch_session_id"] = "wizard-" + "2" * 32
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        if publication == "PENDING":
            assert "Inspection/review publication pending" in text
            assert "inspector_exact_label" not in text
        else:
            assert "Historical file observations" in text
            assert "inspector_exact_label" in text


@pytest.mark.parametrize("pending", [False, True])
def test_initial_and_admitted_before_observation_have_no_inferred_report(pending):
    value = wrapper()
    value.update(status="NOT_INSPECTED", inspection=None)
    value["publication"] = {
        "status": "PENDING" if pending else "NOT_PUBLISHED",
        "operation_id": None,
    }
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        assert (
            "No runtime-pair inspection retained" in text
            or "publication pending" in text
        )
        assert "inspector_exact_label" not in text


def test_global_hold_is_not_inferred_away_from_all_matching_rows():
    value = wrapper(matched=True)
    value["inspection"]["status"] = "HELD"
    for text in render(value):
        assert "File result: HELD" in text
        assert "global inspection hold may still apply" in text
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text


@pytest.mark.parametrize("status", ["GAPS", "NOT_VERIFIED"])
def test_missing_observations_do_not_become_zero_or_matching(status):
    value = wrapper()
    row = value["inspection"]["purposes"]["probe"]
    row["binary_status"] = "NOT_OBSERVED"
    row["build_status"] = (
        "MANIFEST_INVALID" if status == "NOT_VERIFIED" else "NOT_OBSERVED"
    )
    for kind in ("source", "artifact"):
        total = row[kind + "_counts"]["total"]
        row[kind + "_status"] = status
        row[kind + "_counts"] = {
            "total": total,
            "matched": 0,
            "gaps": total if status == "GAPS" else 0,
            "unverified": total if status == "NOT_VERIFIED" else 0,
        }
    row["gaps"] = [
        {
            "relative_path": SOURCE_PATH,
            "reason": "MANIFEST_UNVERIFIED" if status == "NOT_VERIFIED" else "MISSING",
        }
    ]
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        assert "executable pin NOT_OBSERVED" in text
        assert f"source closure {status}" in text


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(extra="RAW_SENTINEL"),
        lambda v: v.update(dispatch_enabled=True),
        lambda v: v.update(driver_qualified=0),
        lambda v: v.update(hardware_qualified="false"),
        lambda v: v.update(connected=True),
        lambda v: v.update(physical_authority=True),
        lambda v: v.update(status="RUNTIME_RELEASED"),
        lambda v: v.update(meaning="unsafe\x1b[0m"),
        lambda v: v["inspection"].update(extra="RAW_SENTINEL"),
        lambda v: v["inspection"].update(source_sha256="c" * 64),
        lambda v: v["inspection"].update(launch_session_id="other-launch"),
        lambda v: v["inspection"].update(operator_id=" x "),
        lambda v: v["inspection"].update(operator_id="x" * 65),
        lambda v: v["inspection"].update(operator_id="inspector_<b>_RAW_SENTINEL"),
        lambda v: v["inspection"].update(report_sha256="ABC"),
        lambda v: v["inspection"].update(status="FILES_MATCHED"),
        lambda v: v["inspection"].update(physical_authority=0),
        lambda v: v["inspection"]["coverage"].update(observed_paths=True),
        lambda v: v["inspection"]["coverage"].update(planned_paths=41),
        lambda v: v["inspection"]["coverage"].update(unobserved_paths=1),
        lambda v: v["inspection"]["purposes"].update(unknown="RAW_SENTINEL"),
        lambda v: v["inspection"]["purposes"]["probe"].update(purpose="capture"),
        lambda v: v["inspection"]["purposes"]["probe"].update(
            binary_status="NOT_VERIFIED"
        ),
        lambda v: v["inspection"]["purposes"]["probe"].update(build_status=True),
        lambda v: v["inspection"]["purposes"]["probe"].update(source_status="MATCHED"),
        lambda v: v["inspection"]["purposes"]["probe"]["source_counts"].update(
            total=10
        ),
        lambda v: v["inspection"]["purposes"]["probe"]["source_counts"].update(
            matched=8.5
        ),
        lambda v: v["inspection"]["purposes"]["probe"]["gaps"].append(
            {"relative_path": SOURCE_PATH, "reason": "HASH_MISMATCH"}
        ),
        lambda v: v["inspection"]["purposes"]["probe"]["gaps"][0].update(
            relative_path="C:/RAW_SENTINEL/private.exe"
        ),
        lambda v: v["inspection"]["purposes"]["probe"]["gaps"][0].update(
            relative_path="software/native/windows_camera/../RAW_SENTINEL"
        ),
        lambda v: v["inspection"]["purposes"]["probe"]["gaps"][0].update(
            relative_path="software/native/windows_camera/RAW_SENTINEL.exe"
        ),
        lambda v: v["inspection"]["purposes"]["probe"]["gaps"][0].update(
            reason="RAW_SENTINEL"
        ),
        lambda v: v["review"].update(reviewer_id="inspector_exact_label"),
        lambda v: v["review"].update(reviewer_id="INSPECTOR_exact_label"),
        lambda v: v["review"].update(distinct_operator_labels=1),
        lambda v: v["review"].update(inspection_sha256="d" * 64),
        lambda v: v["review"].update(review_operation_id="different-operation"),
        lambda v: v["review"].update(status="ACKNOWLEDGED_FILE_MATCH"),
        lambda v: v["review"].update(extra="RAW_SENTINEL"),
        lambda v: v["publication"].update(operation_id=None),
        lambda v: v["publication"].update(status="PENDING"),
    ],
)
def test_malformed_or_misbound_summary_is_wholly_withheld(mutation):
    value = wrapper(reviewed=True)
    mutation(value)
    assert _PhysicalCameraRuntimeDisplay.projection(value, SOURCE, LAUNCH) is None
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" in text
        assert "inspector_exact_label" not in text
        assert "RAW_SENTINEL" not in text


def test_exact_labels_are_plain_text_not_humanized():
    value = wrapper(reviewed=True)
    value["inspection"]["operator_id"] = "inspector_exact_label-v1.2"
    value["review"]["reviewer_id"] = "reviewer_exact_label-v1.2"
    for text in render(value):
        assert "inspector_exact_label-v1.2" in text
        assert "reviewer_exact_label-v1.2" in text


def runtime_action(review=False):
    kind, person, consent = (
        ("review", "reviewer_id", "file_review_only")
        if review
        else ("inspect", "operator_id", "file_inspection_only")
    )
    result = action(
        "physical_camera_runtime_" + kind,
        fields=[
            {
                "name": person,
                "label": person,
                "type": "text",
                "required": True,
                "max_length": 64,
            },
            {
                "name": consent,
                "label": consent,
                "type": "checkbox",
                "required": True,
                "default": False,
            },
        ],
    )
    result["section"] = "camera"
    return result


@pytest.mark.parametrize("review", [False, True])
@pytest.mark.parametrize("consent", [False, True])
def test_generic_browser_file_confirmation_is_separate_from_execution(review, consent):
    item = runtime_action(review)
    view = view_for(wrapper())
    view["actions"] = [item]
    fields = item["fields"]
    values = {fields[0]["name"]: "explicit_actor", fields[1]["name"]: consent}
    page = browser(
        selection(),
        "camera",
        snapshot=view,
        prepare=True,
        action=item["action_id"],
        values=values,
    )
    assert [row["path"] for row in page["requests"]] == ["/api/view"] + (
        ["/api/prepare"] if consent else []
    )
    assert page["dialogOpen"] is consent
    if consent:
        assert page["requests"][1]["body"]["input"] == values
    assert not any(row["path"] == "/api/execute" for row in page["requests"])


@pytest.mark.parametrize("review", [False, True])
@pytest.mark.parametrize("confirmation", ["", "yes to all hardware", "no"])
def test_terminal_file_acknowledgment_never_implies_execute(review, confirmation):
    item = runtime_action(review)
    service = Service([item])
    code, _, _ = run(
        service, [item["action_id"], "explicit_actor", "yes", confirmation, "quit"]
    )
    assert code == 0 and len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")


def test_terminal_cached_runtime_display_does_not_inspect_or_mutate_files(monkeypatch):
    from pathlib import Path
    import subprocess
    from rocell.ui.terminal import _TerminalWizard

    def forbidden(*args, **kwargs):
        pytest.fail("Runtime display attempted file inspection or process launch")

    value = wrapper(reviewed=True)
    original = deepcopy(value)
    output = []
    renderer = _TerminalWizard(
        Service([]), lambda _: "quit", output.append, lambda _: None
    )
    with monkeypatch.context() as guard:
        for name in ("open", "stat", "read_bytes", "read_text"):
            guard.setattr(Path, name, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        renderer.show_camera_runtime_review(value, SOURCE, LAUNCH)
    assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in "\n".join(output)
    assert value == original


def test_current_runtime_report_rejects_wrong_application_launch():
    for text in render(wrapper(), view_changes={"session_id": "another-launch"}):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" in text
        assert "inspector_exact_label" not in text


def test_same_path_different_fixed_gap_reasons_is_retained_without_collapsing():
    value = wrapper()
    value["inspection"]["purposes"]["probe"]["gaps"].append(
        {"relative_path": SOURCE_PATH, "reason": "CHANGED_DURING_READ"}
    )
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        assert "HASH_MISMATCH" in text and "CHANGED_DURING_READ" in text


def test_gap_rows_are_bounded_and_never_silently_truncated():
    value = wrapper()
    gaps = [
        {"relative_path": path, "reason": reason}
        for reason in ("NOT_INSPECTED", "MISSING")
        for path in sorted(_PhysicalCameraRuntimeDisplay.PATHS)
    ]
    value["inspection"]["purposes"]["probe"]["gaps"] = gaps[:40]
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        assert gaps[39]["relative_path"] in text
    value["inspection"]["purposes"]["probe"]["gaps"] = gaps[:41]
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" in text


@pytest.mark.parametrize("review", [False, True])
def test_actual_catalog_fields_render_without_selected_actor_or_consent(review):
    from rocell.application.wizard_actions import ACTION_BY_ID

    expected = runtime_action(review)
    definition = ACTION_BY_ID[expected["action_id"]]
    assert (
        definition.mode == "physical" and definition.worker == "physical_camera_runtime"
    )
    item = definition.view(mode="physical", busy=False)
    assert item["enabled"] is True
    assert definition.view(mode="rehearsal", busy=False)["enabled"] is False
    assert [row["name"] for row in item["fields"]] == [
        row["name"] for row in expected["fields"]
    ]
    assert "default" not in item["fields"][0]
    assert item["fields"][1]["default"] is False
    view = view_for(wrapper())
    view["actions"] = [item]
    page = browser(selection(), "camera", snapshot=view)
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    for row in page["controls"]:
        if row["id"].startswith("field-" + item["action_id"]):
            assert row["value"] == "" and row["checked"] is False


def test_empty_historical_withdrawal_is_a_harmless_hold():
    value = wrapper()
    value.update(status="HISTORICAL_HELD", inspection=None)
    value["publication"] = {"status": "HISTORICAL_HELD", "operation_id": None}
    for text in render(value):
        assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
        assert "Historical file observations" in text
        assert "No runtime-pair inspection retained" in text


def test_actual_inspector_service_projection_and_both_renderers_join(monkeypatch):
    """Actual fixed installed files; broad fingerprint fixed only for isolation.

    No executable is run. This is not the separately source-frozen public smoke
    or received-device qualification. Pure review/display cannot inspect again.
    """
    from pathlib import Path
    import hashlib
    import subprocess
    import threading
    from rocell.application import physical_camera_runtime_inspection as inspector
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.providers.windows.owned_native_camera_runner import (
        OwnedNativeCameraRunner,
    )
    from test_physical_camera_runtime_inspection import (
        assert_actual_historical_runtime_drift,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Runtime file UI join attempted native/device/process access")

    assert set(inspector.FIXED_PATHS) == _PhysicalCameraRuntimeDisplay.PATHS
    workspace = Path(__file__).resolve().parents[3]
    before = {
        path: hashlib.sha256((workspace / path).read_bytes()).hexdigest()
        for path in inspector.FIXED_PATHS
    }
    monkeypatch.setattr(inspector, "source_fingerprint", lambda _: SOURCE)
    with monkeypatch.context() as guard:
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(OwnedNativeCameraRunner, "run", forbidden)
        for method in (
            "enumerate_metadata",
            "resolve_identity_metadata",
            "probe",
            "capture",
        ):
            guard.setattr(WindowsCameraWorkerClient, method, forbidden)
        owner = PhysicalCameraAcquisitionService(
            workspace, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
        )
        initial = owner.view()
        context = owner.runtime_context_sha256()
        owner.begin_runtime_action("physical_camera_runtime_inspect", context)
        admitted = owner.view()
        op = "operation-" + "3" * 32
        result = owner.perform_runtime_action(
            "physical_camera_runtime_inspect",
            expected_context_sha256=context,
            actor_id="actual_file_inspector",
            operation_id=op,
            cancellation=threading.Event(),
            progress=lambda _: None,
        )
        pending = owner.view()
        owner.validate_runtime_publication(op, result)
        owner.publish_runtime_action(op)
        current = owner.view()
        original = owner.retained_runtime_diagnostics()
        actual = current["runtime_inspection"]["inspection"]
        assert_actual_historical_runtime_drift(original["inspection"])
        assert _PhysicalCameraRuntimeDisplay.summary(actual)
        # Review, status and invalidation operate only on immutable cached data.
        for name in ("open", "stat", "read_bytes", "read_text"):
            guard.setattr(Path, name, forbidden)
        context = owner.runtime_context_sha256()
        owner.begin_runtime_action("physical_camera_runtime_review", context)
        review_op = "operation-" + "4" * 32
        reviewed_result = owner.perform_runtime_action(
            "physical_camera_runtime_review",
            expected_context_sha256=context,
            actor_id="actual_file_reviewer",
            operation_id=review_op,
            cancellation=threading.Event(),
            progress=lambda _: None,
        )
        owner.validate_runtime_publication(review_op, reviewed_result)
        owner.publish_runtime_action(review_op)
        reviewed = owner.view()
        owner.invalidate_runtime()
        historical = owner.view()
        assert (
            owner.retained_runtime_diagnostics()["inspection"] == original["inspection"]
        )
    for camera in (initial, admitted, pending, current, reviewed, historical):
        for text in render(camera["runtime_inspection"], camera=camera):
            assert "RUNTIME_INSPECTION_NOT_VERIFIED" not in text
            assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in text
            assert "NOT_CONNECTED / NOT_QUALIFIED / DISPATCH_DISABLED" in text
            if camera["runtime_inspection"]["publication"]["status"] == "PENDING":
                assert "actual_file_inspector" not in text
            elif camera["runtime_inspection"]["inspection"] is not None:
                assert actual["report_sha256"] in text
                assert "probe: source closure GAPS" in text
                assert "capture: source closure GAPS" in text
                for path in ("identity_metadata.cpp", "identity_metadata.h"):
                    assert "software/native/windows_camera/" + path in text
                assert "SOURCE_RUNTIME_COUNTER_SENTINEL" not in text
    assert (
        reviewed["runtime_inspection"]["review"]["status"] == "ACKNOWLEDGED_HELD_REPORT"
    )
    assert {
        path: hashlib.sha256((workspace / path).read_bytes()).hexdigest()
        for path in inspector.FIXED_PATHS
    } == before
