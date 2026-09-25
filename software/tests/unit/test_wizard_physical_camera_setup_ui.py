"""Cached setup/requirements -> both interfaces, without device or M1 effects.

Requirements use actual controlled files and the real producer. Storage-ready
records below use the real typed M1 serialization with explicit modeled ledger
facts; they are not durability qualification. Root's public smoke owns that test.
"""

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


WORKSPACE = Path(__file__).resolve().parents[3]
PUBLIC_SETUP_EXPORT = (
    WORKSPACE
    / "software/runs/wizard-exports"
    / "wizard-20260908T110036648580Z-bff2203dbb184532a27c9d6e8dd9a005"
)


def setup(owner):
    bound = owner.descriptor()
    return {
        "schema": "rocell.wizard_physical_camera_setup.v1",
        "source_sha256": bound["source_sha256"],
        "launch_session_id": bound["launch_id"],
        "session": owner.view(),
        "prerequisites": None,
        "publication": {"status": "NOT_PUBLISHED", "operation_id": None},
        "physical_authority": False,
        "hardware_qualified": False,
        "meaning": "Original camera-only storage and requirements; no hardware qualification.",
    }


def render(data):
    view = MetadataService(selection()).view()
    view.update(mode="physical", physical_camera_setup=data)
    view["actions"] = []
    for name in (
        "physical_camera_initialize",
        "physical_camera_refresh",
        "physical_camera_prerequisites",
    ):
        row = action(name)
        row["section"] = "camera"
        view["actions"].append(row)
    result = browser(selection(), "camera", snapshot=view)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    service = MetadataService(selection())

    def status():
        service.calls.append(("view",))
        return deepcopy(view)

    service.view = status
    code, lines, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)]
    return result["text"], "\n".join(lines)


def modeled_storage(owner):
    from rocell.application.commissioning_camera_persistence import (
        physical_camera_source_binding,
    )
    from rocell.application.physical_onboarding_m1 import (
        M1CellDescriptor,
        M1RuntimeVerification,
    )
    from rocell.application.physical_onboarding_v2 import V2StageSnapshot, V2StageState
    from rocell.application.physical_onboarding import STAGE_ORDER

    data = setup(owner)
    bound = owner.descriptor()
    cell = M1CellDescriptor.build(
        cell_id=bound["cell_id"],
        source_binding_sha256=physical_camera_source_binding(bound["source_sha256"]),
        durability_qualification_sha256="1" * 64,
        created_at_ns=1_800_000_000_000_000_003,
    )
    verified = M1RuntimeVerification(
        cell=cell,
        qualification_anchor_sha256="2" * 64,
        startup_qualification_sha256="3" * 64,
        attempt_head_sha256="4" * 64,
        attempt_event_count=0,
        unresolved_attempt_ids=(),
        uncertain_attempt_ids=(),
        quarantine_head_sha256="5" * 64,
        quarantine_count=0,
        quarantined=False,
        session_id=bound["session_id"],
        session_header_sha256="6" * 64,
        session_head_sha256="7" * 64,
        session_reconciliation_required=False,
        active_lease_owners=(),
        evidence_inventory_sha256="8" * 64,
        challenge_sha256="9" * 64,
    )
    data["session"].update(
        status="STORAGE_READY_PENDING",
        operation="INITIALIZE",
        verification=verified.to_dict(),
        initialize_attempted=True,
        partial_store_possible=True,
        stages=[
            V2StageSnapshot(stage, V2StageState.PENDING, None, ()).to_dict()
            for stage in STAGE_ORDER
        ],
    )
    data["publication"] = {"status": "CURRENT", "operation_id": "storage-operation"}
    return data


@pytest.fixture(scope="module")
def prerequisite_summary():
    from rocell.application import physical_camera_prerequisites as module

    owner = session_fixture(WORKSPACE)
    bound = owner.descriptor()
    with pytest.MonkeyPatch.context() as patch:
        # Exact four-file reads/validators are real; only broad source identity
        # is a fixed test seam to avoid binding this test to concurrent edits.
        patch.setattr(module, "source_fingerprint", lambda _: bound["source_sha256"])
        artifact = module.collect_physical_camera_prerequisites(
            WORKSPACE,
            source_sha256=bound["source_sha256"],
            session_id=bound["session_id"],
            launch_session_id=bound["launch_id"],
            cancellation=Event(),
            deadline_ns=monotonic_ns() + 30_000_000_000,
        )
    return artifact.safe_summary()


@pytest.fixture
def complete_setup(tmp_path, prerequisite_summary):
    data = modeled_storage(session_fixture(tmp_path))
    data["prerequisites"] = deepcopy(prerequisite_summary)
    # Explicitly modeled post-collection stage state, not a manufactured PASS.
    data["session"].update(status="REFRESHED_STORAGE_ONLY", operation="REFRESH")
    data["session"]["stages"][0].update(state="WAITING_OPERATOR", last_event_sequence=1)
    return data


@pytest.mark.parametrize("missing", [False, True])
def test_initial_presentation_has_no_automatic_storage_or_device_action(
    tmp_path, missing
):
    data = None if missing else setup(session_fixture(tmp_path))
    page, console = render(data)
    for text in (page, console):
        assert "Physical camera setup" in text and "NO PHYSICAL AUTHORITY" in text
        assert "not physical-stage PASS" in text
        assert "without replay, repair or quarantine clearing" in text


def test_exact_typed_storage_record_shows_fifteen_pending_stages_not_physical_pass(
    tmp_path,
):
    data = modeled_storage(session_fixture(tmp_path))
    assert _PhysicalSetupDisplay.setup(data) == data
    page, console = render(data)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "not the physical progress checklist" in text
        assert "9" * 64 in text
        assert "1800000000000000003" not in text
        assert "1800000000000000000" not in text
    assert console.count('"recorded_state": "PENDING"') == 15
    assert "storage_prechecks_clear_only" in console


@pytest.mark.parametrize("kind", ["quarantine", "leases", "unresolved"])
def test_refreshed_storage_holds_do_not_enable_replay(tmp_path, kind):
    data = modeled_storage(session_fixture(tmp_path))
    data["session"].update(status="REFRESHED_STORAGE_ONLY", operation="REFRESH")
    verification = data["session"]["verification"]
    verification.update(
        effects_allowed_by_m1_storage=False,
        status="M1_INTEGRITY_VALID_RECONCILIATION_REQUIRED",
    )
    if kind == "quarantine":
        verification.update(status="M1_INTEGRITY_VALID_CELL_QUARANTINED")
        verification["quarantine"].update(latched=True, event_count=1)
    elif kind == "leases":
        verification["leases"].update(
            active_or_stale_owners=["retained-owner"], reconciliation_required=True
        )
    else:
        verification["attempt_ledger"].update(
            unresolved_attempt_ids=["retained-attempt"], event_count=1
        )
    page, console = render(data)
    assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in page
    assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in console
    assert '"storage_prechecks_clear_only": false' in console


def test_actual_requirement_producer_retains_unknown_intake_deferred_flatness_and_hazards(
    complete_setup,
):
    assert _PhysicalSetupDisplay.setup(complete_setup) == complete_setup
    page, console = render(complete_setup)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "17 NOT OBSERVED" in text and "8 UNMEASURED" in text
        assert "INT-005: measurement and evidence are required now" in text
        assert "TARGET_ACCURACY_BUDGET_CLOSED" in text
        assert "not the full retained inventory" in text
        assert "610 nominal" in text
        assert (
            "DISCONNECTED_REQUIRED is a requirement, not an observed power state"
            in text
        )
        for hazard in ("HZ-007", "HZ-008", "HZ-009", "HZ-010", "HZ-012"):
            assert hazard in text
        assert complete_setup["prerequisites"]["evidence_sha256"] in text
    assert console.count("OBSERVATION UNKNOWN") == 17


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_pending_or_historical_publication_withholds_current_requirements(
    complete_setup, publication
):
    complete_setup["publication"]["status"] = publication
    page, console = render(complete_setup)
    for text in (page, console):
        assert "Current prerequisite details are withheld" in text
        assert "INT-005: measurement" not in text
        assert complete_setup["prerequisites"]["evidence_sha256"] not in text
        assert "9" * 64 in text  # Separately labeled retained storage record.


@pytest.mark.parametrize(
    "path,value",
    [
        (("extra",), "RAW_SENTINEL"),
        (("physical_authority",), 0),
        (("hardware_qualified",), True),
        (("session", "replay_allowed"), True),
        (("session", "binding", "source_sha256"), "f" * 64),
        (("session", "verification", "authority", "device_io_authorized"), True),
        (("session", "verification", "operation_effect", "device_opens"), False),
        (("session", "verification", "quarantine", "latched"), True),
        (("session", "stages", 0, "last_event_sequence"), "1"),
        (("session", "stages", 0, "state"), "READY_FOR_CAMERA"),
        (
            ("prerequisites", "stages", 2, "intake_rows", 4, "observation"),
            {"observed_value": 0},
        ),
        (
            ("prerequisites", "stages", 2, "intake_rows", 4, "acceptance", "status"),
            "PASS",
        ),
        (
            (
                "prerequisites",
                "stages",
                2,
                "intake_rows",
                4,
                "acceptance",
                "owner_stage",
            ),
            "camera_receipt",
        ),
        (
            (
                "prerequisites",
                "stages",
                2,
                "intake_rows",
                4,
                "acceptance",
                "measurement_required",
            ),
            False,
        ),
        (("prerequisites", "stages", 2, "intake_rows", 0, "record_id"), "INT-999"),
        (
            ("prerequisites", "stages", 3, "required_effect_classes"),
            ["BOUNDED_CAMERA_CAMPAIGN"],
        ),
        (("prerequisites", "epochs", 0, "value"), "e" * 64),
        (("prerequisites", "epochs", 0, "status"), "QUALIFIED"),
        (("prerequisites", "hazards", 0, "status"), "RESOLVED"),
        (("prerequisites", "power_state"), "DEENERGIZED"),
        (("prerequisites", "source_files", 0, "relative_path"), "../../RAW_SENTINEL"),
        (("prerequisites", "missing_requirements"), []),
    ],
)
def test_malformed_or_approval_bearing_projection_is_withheld(
    complete_setup, path, value
):
    node = complete_setup
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert _PhysicalSetupDisplay.setup(complete_setup) is None
    page, console = render(complete_setup)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" in text
        assert "RAW_SENTINEL" not in text
        assert "INT-005: measurement" not in text


def test_root_setup_service_constructor_and_cached_projection_are_inert(
    tmp_path, monkeypatch
):
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.application.physical_camera_setup_service import (
        PhysicalCameraSetupService,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("setup constructor/status performed filesystem I/O")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            guard.setattr(Path, name, forbidden)
        acquisition = PhysicalCameraAcquisitionService(
            tmp_path,
            launch_id="wizard-" + "1" * 32,
            source_sha256="a" * 64,
            mode="physical",
        )
        service = PhysicalCameraSetupService(acquisition)
        data = service.view()
        assert service.view() == data
    assert _PhysicalSetupDisplay.setup(data) == data
    page, console = render(data)
    assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in page
    assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in console


def test_actual_optional_metadata_and_held_source_context_remain_unqualified(
    complete_setup, monkeypatch
):
    from rocell.application import physical_camera_prerequisites as module
    from rocell.application.physical_camera_selection import selection_from_enrollment
    from test_physical_camera_acquisition_service import reviewed_enrollment
    from test_physical_camera_prerequisites import held_preflight

    bound = complete_setup["session"]["binding"]
    selected = selection_from_enrollment(
        reviewed_enrollment(bound["launch_id"], unicode=True),
        source_sha256=bound["source_sha256"],
        launch_session_id=bound["launch_id"],
    )
    preflight = held_preflight()
    monkeypatch.setattr(module, "source_fingerprint", lambda _: bound["source_sha256"])
    report = module.collect_physical_camera_prerequisites(
        WORKSPACE,
        source_sha256=bound["source_sha256"],
        session_id=bound["session_id"],
        launch_session_id=bound["launch_id"],
        cancellation=Event(),
        deadline_ns=monotonic_ns() + 30_000_000_000,
        selection=selected,
        source_preflight_report=preflight,
        expected_source_preflight_sha256=preflight.sha256,
    )
    complete_setup["prerequisites"] = report.safe_summary()
    assert _PhysicalSetupDisplay.setup(complete_setup) == complete_setup
    page, console = render(complete_setup)
    for text in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "SOURCE_PREFLIGHT_HELD" in text
        assert "not a received-unit measurement" in text
        assert "not stage acceptance" in text
        assert preflight.sha256 in text and selected.sha256 in text


@pytest.mark.parametrize("publication", ["CURRENT", "PENDING", "HISTORICAL_HELD"])
def test_actual_source_frozen_public_setup_export_renders_without_dispatch(publication):
    """Read an optional local smoke artifact, never recreate its durable session.

    The original CURRENT case is the unmodified real Arrival export. The other
    two cases exercise display suppression only; they do not claim new M1 runs.
    A fresh checkout without this intentionally untracked diagnostic skips this
    supplementary check; the portable producer tests above always run.
    """
    report_path = PUBLIC_SETUP_EXPORT / "report.json"
    if not report_path.is_file():
        pytest.skip("Local source-frozen public setup smoke export is not present")
    view = json.loads(report_path.read_text(encoding="utf-8"))["snapshot"]
    assert view["mode"] == "physical"
    projection = view["physical_camera_setup"]
    assert projection["publication"]["status"] == "CURRENT"
    assert projection["session"]["status"] == "REFRESHED_STORAGE_ONLY"
    states = projection["session"]["stages"]
    assert states[0]["state"] == "WAITING_OPERATOR"
    assert [row["state"] for row in states[1:]] == ["PENDING"] * 14
    assert projection["prerequisites"]["status"] == (
        "REQUIREMENTS_RETAINED_NOT_ASSESSED"
    )
    # Export snapshots hold summaries. Full operation reports are detached
    # attachments, not recursively searched for a current setup projection.
    assert [row["status"] for row in view["operations"]] == [
        "SUCCEEDED",
        "SUCCEEDED",
        "SUCCEEDED",
        "QUEUED",
    ]
    for operation in view["operations"]:
        assert "result" not in operation
        assert all("report" not in step for step in operation["steps"])
    projection["publication"]["status"] = publication
    assert _PhysicalSetupDisplay.setup(projection) == projection
    original = deepcopy(view)
    rendered = browser(selection(), "camera", snapshot=view)
    assert rendered["status"] == "Local service connected", rendered["error"]
    assert rendered["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None}
    ]
    service = MetadataService(selection())

    def cached_snapshot():
        service.calls.append(("view",))
        return deepcopy(view)

    service.view = cached_snapshot
    code, output, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)]
    console = "\n".join(output)
    assert console.count('"recorded_state": "WAITING_OPERATOR"') == 1
    assert console.count('"recorded_state": "PENDING"') == 14
    for text in (rendered["text"], console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "NO PHYSICAL AUTHORITY" in text
        assert "not physical-stage PASS" in text
        assert "not the physical progress checklist" in text
        if publication == "CURRENT":
            assert projection["prerequisites"]["evidence_sha256"] in text
            assert "INT-005" in text and "Acceptance is DEFERRED" in text
            assert "HZ-012" in text and "UNKNOWN" in text
        else:
            assert "INT-005: measurement" not in text
            assert projection["prerequisites"]["evidence_sha256"] not in text
    assert view == original
