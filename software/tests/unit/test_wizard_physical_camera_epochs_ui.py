"""Actual pure vector/summary, modeled audited storage, cached renderers only.

The original requirements use actual controlled files; the V2 prefix and M1
verification below are explicitly typed modeled facts, not a durability proof.
No application, device, process worker, admission or real M1 is constructed.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from threading import RLock
from types import SimpleNamespace

import pytest

from rocell.application import physical_configuration_epochs as epochs
from rocell.application.physical_camera_setup_service import PhysicalCameraSetupService
from rocell.ui.terminal import (
    _PhysicalConfigurationRecordsDisplay,
    _PhysicalSetupDisplay,
    _TerminalWizard,
)
from test_arrival_wizard_terminal import Service
from test_physical_camera_session import session_fixture
from test_physical_configuration_epochs import epoch_fixture, typed_snapshot, reference
from test_wizard_physical_camera_setup_ui import (
    modeled_storage,
    render as original_render,
)
from test_wizard_physical_camera_restart_ui import registry


@pytest.fixture(scope="module")
def produced():
    return epoch_fixture()


def wrapper(artifact, publication="CURRENT"):
    owner = SimpleNamespace(
        _lock=RLock(),
        _epoch_record={
            "document": artifact.to_dict(),
            "evidence_sha256": artifact.sha256,
            "retention": "M1_FULL_BYTES_READ_BACK",
        },
        _publication={"status": publication},
    )
    # Actual cached service projection over an explicitly modeled retention tag.
    # This exercises neither M1 storage nor any physical acquisition path.
    return PhysicalCameraSetupService.configuration_records_view(owner)


def setup(tmp_path, produced):
    prerequisites, snapshot, artifact = produced
    data = modeled_storage(session_fixture(tmp_path))
    b = artifact.safe_summary()["binding"]
    data.update(
        schema="rocell.wizard_physical_camera_setup.v3",
        source_sha256=b["source_sha256"],
        launch_session_id=b["origin_launch_id"],
        origin_launch_id=b["origin_launch_id"],
        requirements_provenance="CURRENT_LAUNCH_ORIGINAL",
        reopening=registry(b["origin_launch_id"], b["source_sha256"]),
        prerequisites=prerequisites.safe_summary(),
        configuration_records=wrapper(artifact),
    )
    data["session"]["binding"].update(
        source_sha256=b["source_sha256"],
        launch_id=b["origin_launch_id"],
        session_id=b["session_id"],
        cell_id=b["cell_id"],
    )
    data["session"].update(
        status="REFRESHED_STORAGE_ONLY",
        operation="REFRESH",
        stages=[row.to_dict() for row in snapshot.stages],
    )
    verification = data["session"]["verification"]
    verification["cell"].update(
        cell_id=b["cell_id"], source_binding_sha256=b["source_binding_sha256"]
    )
    verification["session"].update(
        session_id=b["session_id"],
        header_sha256=b["session_header_sha256"],
        head_sha256=snapshot.head.head_sha256,
    )
    return data


def render(value):
    original = subprocess.run

    def utf8(*args, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        return original(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "run", utf8)
        return original_render(value)


def panel(text):
    return text.split(
        "Eight-domain configuration records — unqualified dependencies", 1
    )[1]


def test_actual_initial_producer_service_wrapper_to_both_renderers(tmp_path, produced):
    value = setup(tmp_path, produced)
    original = deepcopy(value)
    assert _PhysicalSetupDisplay.setup(value) == value
    assert (
        _PhysicalConfigurationRecordsDisplay.projection(
            value["configuration_records"], value
        )
        == value["configuration_records"]
    )
    assert value["configuration_records"]["summary"] == produced[2].safe_summary()
    for output in render(value):
        text = panel(output)
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in text
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in output
        assert "Record publication: CURRENT" in text
        assert text.count(": UNOBSERVED") == 8
        assert text.count(": PENDING_CURRENT_OUTPUT") == 4
        assert text.count(": PENDING_FUTURE_OUTPUT") == 28
        assert "camera_mode_controls: PENDING_FUTURE_OUTPUT" in text
        assert "NO ADMISSION / NO QUALIFICATION" in text
        assert "Retained references are UNASSESSED" in text
        assert (
            "waive no earlier hazard, isolation, firmware or runtime prerequisite"
            in text
        )
        assert "original prerequisite epoch requirements remain UNMEASURED" in text
        assert "No device control, canonical stage PASS" in text
        assert produced[2].sha256 in text
    assert value == original


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_old_setup_schemas_are_readable_without_implicit_upgrade(
    tmp_path, produced, version
):
    value = setup(tmp_path, produced)
    value["schema"] = "rocell.wizard_physical_camera_setup." + version
    del value["configuration_records"]
    if version == "v1":
        for key in ("origin_launch_id", "requirements_provenance", "reopening"):
            del value[key]
    original = deepcopy(value)
    assert _PhysicalSetupDisplay.setup(value) == value
    for text in render(value):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "legacy snapshot has no progressive configuration record" in text
        assert "Record publication: CURRENT" not in text
    assert value == original


def test_v3_before_initialization_has_no_inferred_record(tmp_path, produced):
    value = setup(tmp_path, produced)
    value.update(prerequisites=None, requirements_provenance="NONE")
    value["publication"] = {"status": "NOT_PUBLISHED", "operation_id": None}
    value["configuration_records"].update(status="NOT_RETAINED", summary=None)
    value["session"].update(
        status="NOT_INITIALIZED",
        operation=None,
        verification=None,
        stages=None,
        initialize_attempted=False,
        partial_store_possible=False,
    )
    assert _PhysicalSetupDisplay.setup(value) == value
    for output in render(value):
        text = panel(output)
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in text
        assert "Record publication: NOT_RETAINED" in text
        assert produced[2].sha256 not in text
        assert "No progressive record is available" in text


@pytest.mark.parametrize(
    "kind", ["pending", "missing_prerequisites", "missing_verification"]
)
def test_current_claim_is_withheld_when_outer_publication_or_context_is_missing(
    tmp_path, produced, kind
):
    value = setup(tmp_path, produced)
    if kind == "pending":
        value["publication"]["status"] = "PENDING"
        value.update(prerequisites=None, requirements_provenance="NONE")
    elif kind == "missing_prerequisites":
        value.update(prerequisites=None, requirements_provenance="NONE")
    else:
        value["session"].update(status="HELD", verification=None, stages=None)
    assert _PhysicalSetupDisplay.setup(value) == value
    for output in render(value):
        text = panel(output)
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" in text
        assert "Record publication: CURRENT" not in text
        assert produced[2].sha256 not in text


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_publication_does_not_upgrade_or_relabel_original_records(
    tmp_path, produced, publication
):
    value = setup(tmp_path, produced)
    value["publication"]["status"] = publication
    value.update(prerequisites=None, requirements_provenance="NONE")
    value["configuration_records"] = wrapper(produced[2], publication)
    for output in render(value):
        text = panel(output)
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in text
        assert "Record publication: CURRENT" not in text
        if publication == "PENDING":
            assert "Configuration details withheld" in text
            assert produced[2].sha256 not in text
        else:
            assert "Historical original configuration context only" in text
            assert produced[2].sha256 in text


def test_new_launch_and_newer_head_do_not_rewrite_original_boundary(tmp_path, produced):
    value = setup(tmp_path, produced)
    value["launch_session_id"] = "wizard-" + "b" * 32
    value["requirements_provenance"] = "REOPENED_ORIGINAL_CONTEXT"
    value["reopening"] = registry(value["launch_session_id"], value["source_sha256"])
    value["session"]["verification"]["session"].update(
        head_sha256="c" * 64, evidence_inventory_sha256="d" * 64
    )
    for text in render(value):
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in text
        assert "Original recorded boundary — not the latest session head" in text
        assert "Historical original requirements" in text
        assert value["origin_launch_id"] in text and value["launch_session_id"] in text


@pytest.mark.parametrize(
    "index,phase",
    [(0, "AFTER_STAGE"), (4, "BEFORE_STAGE"), (4, "AFTER_STAGE"), (13, "BEFORE_STAGE")],
)
def test_actual_producer_classifies_predecessors_and_current_future_outputs(
    tmp_path, produced, index, phase
):
    prerequisite = produced[0]
    snapshot = typed_snapshot(prerequisite, boundary_index=index)
    artifact = epochs.build_physical_configuration_epochs(
        prerequisite, snapshot, boundary=phase
    )
    value = setup(tmp_path, (prerequisite, snapshot, artifact))
    assert (
        _PhysicalConfigurationRecordsDisplay.projection(
            value["configuration_records"], value
        )
        is not None
    )
    for output in render(value):
        text = panel(output)
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in text
        for entry in artifact.safe_summary()["entries"]:
            for row in entry["bindings"]:
                assert f"{row['binding_id']}: {row['status']}" in text
        assert "not missing predecessors" in text and "NO ADMISSION" in text


@pytest.mark.parametrize("count", [1, 4])
def test_retained_references_are_never_qualified_observations(
    tmp_path, produced, count
):
    prerequisite = produced[0]
    ref = reference(epochs.STAGE_ORDER[0])
    snapshot = typed_snapshot(prerequisite, extra=(ref,))
    artifact = epochs.build_physical_configuration_epochs(
        prerequisite,
        snapshot,
        evidence_bindings=tuple(
            epochs.EpochEvidenceBinding(key, (ref,))
            for key in list(epochs.EpochBindingName)[:count]
        ),
    )
    value = setup(tmp_path, (prerequisite, snapshot, artifact))
    for output in render(value):
        text = panel(output)
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in text
        assert text.count(": RETAINED_REFERENCE_UNASSESSED") == count
        assert (
            "PARTIALLY_REFERENCED" in text
            if count == 1
            else "REFERENCES_RETAINED_UNASSESSED" in text
        )
        assert ref.payload_sha256 in text and "not accepted observations" in text


@pytest.mark.parametrize(
    "path,bad",
    [
        (("schema",), "unknown"),
        (("status",), "QUALIFIED"),
        (("status",), "NOT_RETAINED"),
        (("physical_authority",), True),
        (("hardware_qualified",), 0),
        (("raw",), "RAW_SENTINEL"),
        (("summary",), None),
        (("summary", "schema"), "unknown"),
        (("summary", "admission_allowed"), True),
        (("summary", "qualified"), True),
        (("summary", "canonical_stage_pass"), True),
        (("summary", "device_io_performed"), True),
        (("summary", "record_sha256"), "bad"),
        (("summary", "raw"), "RAW_SENTINEL"),
        (("summary", "binding", "source_sha256"), "e" * 64),
        (("summary", "binding", "source_binding_sha256"), "e" * 64),
        (("summary", "binding", "session_header_sha256"), "e" * 64),
        (("summary", "binding", "prerequisites_sha256"), "e" * 64),
        (("summary", "binding", "epoch_policy_sha256"), "e" * 64),
        (("summary", "binding", "stage_catalog_sha256"), "e" * 64),
        (("summary", "binding", "session_id"), "physical-camera-" + "e" * 32),
        (("summary", "binding", "cell_id"), "wizard-physical-camera-" + "e" * 16),
        (("summary", "binding", "origin_launch_id"), "wizard-" + "e" * 32),
        (("summary", "original_snapshot", "event_count"), True),
        (("summary", "original_snapshot", "event_count"), 513),
        (("summary", "original_snapshot", "reference_count"), 33),
        (("summary", "boundary", "phase"), "ACCEPTED"),
        (("summary", "entries"), []),
        (("summary", "entries", 0, "status"), "QUALIFIED"),
        (("summary", "entries", 0, "epoch_id"), "ninth_domain"),
        (("summary", "entries", 0, "bindings", 0, "evidence_count"), True),
        (("summary", "entries", 0, "bindings", 0, "evidence_count"), 5),
        (("summary", "entries", 0, "bindings", 0, "payload_sha256s"), ["e" * 64]),
        (("summary", "entries", 0, "bindings", 0, "owner_stage"), "camera_receipt"),
        (("summary", "entries", 0, "bindings", 0, "relative_position"), "PREDECESSOR"),
        (("summary", "entries", 0, "bindings", 0, "status"), "MISSING_PREDECESSOR"),
        (("summary", "coverage", "total_bindings"), 33),
        (("summary", "coverage", "retained"), True),
        (("summary", "coverage", "pending_current_outputs"), 5),
    ],
)
def test_malformed_or_unbound_records_withhold_only_the_record_panel(
    tmp_path, produced, path, bad
):
    value = setup(tmp_path, produced)
    target = value["configuration_records"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = deepcopy(bad)
    assert (
        _PhysicalConfigurationRecordsDisplay.projection(
            value["configuration_records"], value
        )
        is None
    )
    for output in render(value):
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" in output
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in output
        assert "RAW_SENTINEL" not in output
        assert "Record publication: CURRENT" not in output


def test_display_never_calls_producer_reads_files_or_changes_controls(
    tmp_path, produced, monkeypatch
):
    value = setup(tmp_path, produced)
    lines = []
    terminal = _TerminalWizard(
        Service([]), lambda _: "quit", lines.append, lambda _: None
    )

    def denied(*_a, **_k):
        pytest.fail("Cached configuration display attempted acquisition or persistence")

    with monkeypatch.context() as guard:
        guard.setattr(epochs, "build_physical_configuration_epochs", denied)
        for name in ("open", "stat", "read_bytes", "read_text"):
            guard.setattr(Path, name, denied)
        guard.setattr(subprocess, "Popen", denied)
        terminal.show_physical_configuration_records(value)
    assert any("PENDING_CURRENT_OUTPUT" in str(line) for line in lines)
    # Shared fake-DOM render requires exactly GET /api/view. Existing generic
    # setup actions are supplied; this panel creates no action or selector.
    for output in render(value):
        assert "NO ADMISSION / NO QUALIFICATION" in output


@pytest.mark.parametrize(
    "folder,report_sha,source,record_sha,attachment_sha,reopened",
    [
        (
            "wizard-20260908T193034725734Z-3a9003c8ee4b423994ecf8116f564419",
            "4c4405319948b83346ce692f23951b8ee6aebb5d4f2bc3d7da08465b66a5bc08",
            "61856b76de80d41589b47e292c581f79d540c9ac7d8ef5b0d50f70ed58605006",
            "5c258bed1134c6402e9c9786c45bcd71f6227e06dddeef01ceb3334b79d7e45e",
            "4ac480c98a13f73e32b3633a64a316845f41861ae626ff6e381d6461921b78a9",
            False,
        ),
        (
            "wizard-20260908T193044164409Z-d140ac233eb647b6a2c394d24b185e5c",
            "8be16685a84d6c574db6ea706295f6a5f29b1cbfb9f74b85ddbc6f5276778854",
            "61856b76de80d41589b47e292c581f79d540c9ac7d8ef5b0d50f70ed58605006",
            "5c258bed1134c6402e9c9786c45bcd71f6227e06dddeef01ceb3334b79d7e45e",
            "4ac480c98a13f73e32b3633a64a316845f41861ae626ff6e381d6461921b78a9",
            True,
        ),
        (
            "wizard-20260908T193352199430Z-82026b2978e44258babc9bec71bffa66",
            "5398684402c20ecf467bb0005c8612861c2974c1ed59be1d129716cb806e433f",
            "c3202a941a9a51a8c66ec800b8b032ffa2c23efc51b45e075b9d9a5b786b58a5",
            "2d0ee2d03b6b2bd9a7382bb8b2abfe08b90f6ea02c84a2612f2b98012245df1d",
            "7c0646339f327f97ecb9fd7a675a3d08f9272299b0ed7918d36dc9ff7e5615f7",
            False,
        ),
        (
            "wizard-20260908T193402708784Z-469cf7ade6f64c94a3392971972ba502",
            "635653c01612d5de90bd4e880616b9b3915289d4268480ba2d72d65681bce738",
            "c3202a941a9a51a8c66ec800b8b032ffa2c23efc51b45e075b9d9a5b786b58a5",
            "2d0ee2d03b6b2bd9a7382bb8b2abfe08b90f6ea02c84a2612f2b98012245df1d",
            "7c0646339f327f97ecb9fd7a675a3d08f9272299b0ed7918d36dc9ff7e5615f7",
            True,
        ),
    ],
)
def test_preserved_real_v3_exports_render_exact_original_and_reopened_context(
    folder, report_sha, source, record_sha, attachment_sha, reopened, monkeypatch
):
    """Historical-source exports, not claims about the source currently on disk.

    Both launch snapshots remain byte-identical. Full original configuration
    evidence is decoded purely; no application, M1 reopen or acquisition runs.
    """
    from rocell.application.wizard_diagnostic_export import verify_export
    from test_wizard_workspace_source_ui import render_snapshot

    directory = (
        Path(__file__).resolve().parents[3] / "software/runs/wizard-exports" / folder
    )
    report_path = directory / "report.json"
    attachment_path = directory / "attachment-configuration-records.json"
    if not report_path.exists():
        pytest.skip("Preserved local public v3 export is not installed")
    before = {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    }
    assert hashlib.sha256(before["report.json"]).hexdigest() == report_sha
    assert hashlib.sha256(before[attachment_path.name]).hexdigest() == attachment_sha
    assert verify_export(directory)["valid"] is True
    view = json.loads(before["report.json"])["snapshot"]
    original_view = deepcopy(view)
    setup_view = view["physical_camera_setup"]
    assert view["source_binding_sha256"] == source == setup_view["source_sha256"]
    assert setup_view["schema"] == "rocell.wizard_physical_camera_setup.v3"
    assert (
        setup_view["origin_launch_id"] != setup_view["launch_session_id"]
    ) is reopened
    assert setup_view["requirements_provenance"] == (
        "REOPENED_ORIGINAL_CONTEXT" if reopened else "CURRENT_LAUNCH_ORIGINAL"
    )
    assert setup_view["session"]["stages"][0]["state"] == "BLOCKED"
    assert all(row["state"] == "PENDING" for row in setup_view["session"]["stages"][1:])
    assert len(setup_view["session"]["stages"][0]["evidence_ids"]) == 5
    assert all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"])
    retained = json.loads(before[attachment_path.name])
    artifact = epochs.PhysicalConfigurationEpochs(
        json.dumps(
            retained["document"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    )
    assert artifact.sha256 == retained["record"]["evidence_sha256"] == record_sha
    assert setup_view["configuration_records"]["summary"] == artifact.safe_summary()
    assert _PhysicalSetupDisplay.setup(setup_view) == setup_view
    assert (
        _PhysicalConfigurationRecordsDisplay.projection(
            setup_view["configuration_records"], setup_view
        )
        == setup_view["configuration_records"]
    )

    def denied(*_a, **_k):
        pytest.fail("Viewing an original export attempted to build a new vector")

    original_run = subprocess.run

    def utf8(*args, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        return original_run(*args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(epochs, "build_physical_configuration_epochs", denied)
        guard.setattr(subprocess, "run", utf8)
        page, console = render_snapshot(view)
    for output in (page, console):
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in output
        assert "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED" not in output
        assert "CONFIGURATION_RECORDS_NOT_VERIFIED" not in output
        assert "Saved assessment verdict: BLOCKED" in output
        text = panel(output)
        assert "Record publication: CURRENT" in text and record_sha in text
        assert text.count(": UNOBSERVED") == 8
        assert text.count(": PENDING_CURRENT_OUTPUT") == 4
        assert text.count(": PENDING_FUTURE_OUTPUT") == 28
        assert "NO ADMISSION / NO QUALIFICATION" in text
        assert "Original recorded boundary — not the latest session head" in text
        if reopened:
            assert "Historical original requirements" in output
            assert (
                setup_view["origin_launch_id"] in output
                and setup_view["launch_session_id"] in output
            )
    assert view == original_view
    assert {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    } == before
    assert verify_export(directory)["valid"] is True
