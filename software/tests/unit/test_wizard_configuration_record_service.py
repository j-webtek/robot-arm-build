"""Real epoch codec/public export joins with explicitly modeled retention.

These tests do not qualify storage or hardware. The separate file-only public
walkthrough exercises actual original-store writes, readback and restart.
"""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import Event

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application import physical_camera_session as camera_session
from rocell.application.physical_configuration_epochs import PhysicalConfigurationEpochs
from rocell.application.physical_camera_session import PhysicalCameraSessionError
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import (
    sanitize_diagnostic_record,
    verify_export,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _run
from test_physical_configuration_epochs import (
    CELL,
    LAUNCH,
    SESSION,
    SOURCE,
    WORKSPACE,
    epoch_fixture,
    reference,
)


@pytest.fixture(scope="module")
def actual_record():
    return epoch_fixture()


@pytest.fixture(scope="module")
def historical_workflow(actual_record):
    """Real pure reader output; original storage/manifest ownership is modeled."""
    prerequisites, snapshot, artifact = actual_record
    owner = camera_session.PhysicalCameraSession(
        WORKSPACE,
        WORKSPACE / "software/runs/physical-camera-acquisition" / LAUNCH,
        source_sha256=SOURCE,
        launch_id=LAUNCH,
        cell_id=CELL,
        session_id=SESSION,
    )
    epoch_reference = reference(snapshot.next_action.stage, artifact.payload)
    current = replace(
        snapshot,
        evidence=tuple(
            sorted(
                (*snapshot.evidence, epoch_reference), key=lambda ref: ref.evidence_id
            )
        ),
    )
    roles = {
        name: {
            "document": subject.to_dict(),
            "evidence_sha256": digest(subject.payload),
            "reference": ref.to_dict(),
            "retention": "M1_FULL_BYTES_READ_BACK",
        }
        for name, subject, ref in (
            ("prerequisites", prerequisites, snapshot.evidence[0]),
            ("configuration_epochs", artifact, epoch_reference),
        )
    }
    return camera_session._verify_original_source_roles(
        owner.descriptor(), current, snapshot.header.header_sha256, roles
    )


@pytest.fixture
def retained(make_service, actual_record):
    service, runner, source = make_service(mode="physical")
    prerequisites, snapshot, artifact = actual_record
    setup = service._physical_camera_setup
    setup._prerequisites = prerequisites.safe_summary()
    setup._epoch_record = {
        "document": artifact.to_dict(),
        "evidence_sha256": artifact.sha256,
        "reference": reference(snapshot.next_action.stage, artifact.payload).to_dict(),
        "retention": "M1_FULL_BYTES_READ_BACK",
    }
    setup._epoch_attempt_record = deepcopy(setup._epoch_record)
    setup._publication = {"status": "CURRENT", "operation_id": "modeled-publication"}
    return service, setup, artifact, runner, source


def test_constructor_has_no_record_and_status_does_not_build_one(
    make_service, monkeypatch
):
    from rocell.application import physical_camera_setup_service as module

    def forbidden(*args, **kwargs):
        pytest.fail("A status read must not generate configuration evidence")

    monkeypatch.setattr(module, "build_physical_configuration_epochs", forbidden)
    service, runner, _ = make_service(mode="physical")
    for _ in range(3):
        value = service.view()["physical_camera_setup"]
        assert value["schema"] == "rocell.wizard_physical_camera_setup.v3"
        assert value["configuration_records"]["status"] == "NOT_RETAINED"
        assert value["configuration_records"]["summary"] is None
        assert (
            service._physical_camera_setup.retained_configuration_diagnostics() is None
        )
    assert not runner.calls


@pytest.mark.parametrize(
    "publication", ["CURRENT", "PENDING", "HISTORICAL_HELD", "NOT_PUBLISHED"]
)
def test_publication_states_never_promote_hardware(retained, publication):
    service, setup, artifact, runner, _ = retained
    setup._publication["status"] = publication
    value = service.view()
    record = value["physical_camera_setup"]["configuration_records"]
    expected = {"CURRENT": "CURRENT", "PENDING": "NOT_RETAINED"}.get(
        publication, "HISTORICAL_HELD"
    )
    assert record["status"] == expected
    assert record["summary"] == (
        None if publication == "PENDING" else artifact.safe_summary()
    )
    assert value["camera"]["status"] == value["arm"]["status"] == "NOT_CONNECTED"
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in value["stages"])
    assert record["physical_authority"] is record["hardware_qualified"] is False
    assert not runner.calls


@pytest.mark.parametrize("flag", ["_source_changed", "_log_error", "_closed"])
def test_outer_holds_remove_current_claim_but_keep_original_record(retained, flag):
    service, setup, artifact, _, _ = retained
    setattr(service, flag, True)
    value = service._physical_camera_setup_view()
    assert value["configuration_records"]["status"] == "HISTORICAL_HELD"
    assert value["configuration_records"]["summary"] == artifact.safe_summary()
    assert value["prerequisites"] is None
    assert (
        setup.retained_configuration_diagnostics()["record"]["document"]
        == artifact.to_dict()
    )
    # Avoid suppressing the fixture's actual shutdown cleanup.
    setattr(service, flag, False)


@pytest.mark.parametrize(
    "retention", ["COLLECTED_NOT_M1_RETAINED", "M1_PUBLISHED_READBACK_PENDING"]
)
def test_partial_retention_is_held_even_after_unrelated_current_publication(
    retained, retention
):
    _, setup, _, _, _ = retained
    setup._epoch_record["retention"] = retention
    assert setup.configuration_records_view()["status"] == "HISTORICAL_HELD"


def test_detached_views_and_original_hash_guard(retained):
    _, setup, artifact, _, _ = retained
    view = setup.configuration_records_view()
    view["summary"]["coverage"]["retained"] = 32
    diagnostics = setup.retained_configuration_diagnostics()
    diagnostics["record"]["document"]["qualified"] = True
    assert setup.configuration_records_view()["summary"] == artifact.safe_summary()
    setup._epoch_record["evidence_sha256"] = "f" * 64
    with pytest.raises(WizardError) as error:
        setup.configuration_records_view()
    assert error.value.code == "CAMERA_CONFIGURATION_RECORD_CHANGED"


def test_record_stays_exportable_when_original_adoption_has_no_epoch(retained):
    _, setup, artifact, _, _ = retained
    setup._epoch_record = None  # Model legacy original adoption after a failed attempt.
    assert setup.configuration_records_view()["status"] == "NOT_RETAINED"
    value = setup.retained_configuration_diagnostics()
    assert value["record_is_current_original"] is False
    assert value["record"]["document"] == artifact.to_dict()


@pytest.mark.parametrize(
    "fault", ["CAMERA_SESSION_CANCELLED", "SOURCE_CHANGED", "LEASE_EXIT_FAILED"]
)
def test_new_owner_late_reader_failure_keeps_unadopted_record_exportable(
    retained, historical_workflow, monkeypatch, fault
):
    service, setup, artifact, runner, _ = retained
    original = deepcopy(setup._epoch_record)
    setup._epoch_record = setup._epoch_attempt_record = None
    setup.invalidate()
    assert historical_workflow["schema"] == camera_session.SOURCE_WORKFLOW_EPOCH_SCHEMA
    assert historical_workflow["configuration_epochs"] == original

    def late(**kwargs):
        # Model the exact reader cache boundary, not a successful store audit.
        # The session's actual detached historical getter and the actual
        # service/export code below must preserve these actual codec bytes.
        setup.session._retained_source_workflow = canonical(historical_workflow)
        raise PhysicalCameraSessionError(fault)

    with monkeypatch.context() as model:
        model.setattr(setup.session, "read_original_source_workflow", late)
        model.setattr(
            setup.session,
            "view",
            lambda: {
                "verification": {
                    "session": {
                        "header_sha256": historical_workflow["session_header_sha256"]
                    }
                }
            },
        )
        with pytest.raises(PhysicalCameraSessionError):
            setup._read_source_workflow(Event(), lambda _: None)

    assert setup._epoch_record is setup._epoch_attempt_record is None
    assert setup.configuration_records_view()["status"] == "NOT_RETAINED"
    retained_value = setup.retained_configuration_diagnostics()
    assert retained_value["record"] == original
    assert retained_value["record_is_current_original"] is False
    assert retained_value["publication"]["status"] == "HISTORICAL_HELD"
    outcome = _run(service, "export_logs")
    assert outcome["status"] == "SUCCEEDED", outcome
    folder = Path(outcome["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"]
    value = json.loads((folder / "attachment-configuration-records.json").read_bytes())
    assert value["publication"] == "HISTORICAL_HELD"
    assert value["original_bytes_preserved"] is True
    assert value["document"] == artifact.to_dict()
    assert not runner.calls


@pytest.mark.parametrize(
    "schema", [None, "rocell.physical_camera_source_workflow_readback.unknown"]
)
def test_historical_cache_requires_supported_schema(
    retained, historical_workflow, schema
):
    _, setup, _, _, _ = retained
    invalid = deepcopy(historical_workflow)
    if schema is None:
        invalid.pop("schema")
    else:
        invalid["schema"] = schema
    setup._epoch_record = setup._epoch_attempt_record = None
    setup.session._retained_source_workflow = canonical(invalid)
    with pytest.raises(PhysicalCameraSessionError) as error:
        setup.retained_configuration_diagnostics()
    assert error.value.code == "CAMERA_SESSION_SOURCE_WORKFLOW_CACHE_INVALID"
    assert setup.configuration_records_view()["status"] == "NOT_RETAINED"


def test_actual_summary_survives_existing_nested_diagnostic_limits(retained):
    _, setup, _, _, _ = retained
    result = {"steps": [{"report": setup.retained_diagnostics()}]}
    assert sanitize_diagnostic_record(result) == result


def test_reserved_full_export_survives_nine_result_rotations(retained):
    service, setup, artifact, runner, _ = retained
    original = setup.retained_configuration_diagnostics()
    for index in range(9):
        assert (
            _run(service, "record_note", {"note": f"rotation {index}"})["status"]
            == "SUCCEEDED"
        )
    outcome = _run(service, "export_logs")
    assert outcome["status"] == "SUCCEEDED", outcome
    folder = Path(outcome["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"]
    value = json.loads((folder / "attachment-configuration-records.json").read_bytes())
    assert value["schema"] == "rocell.wizard_physical_configuration_export.v1"
    assert value["publication"] == "CURRENT"
    assert value["original_bytes_preserved"] is True
    assert value["document"] == artifact.to_dict()
    assert (
        PhysicalConfigurationEpochs(canonical(value["document"])).sha256
        == value["record"]["evidence_sha256"]
    )
    assert setup.retained_configuration_diagnostics() == original
    assert not runner.calls


def test_source_change_exports_original_as_held(retained):
    service, _, artifact, _, source = retained
    source["hash"] = "f" * 64
    outcome = _run(service, "export_logs")
    assert outcome["status"] == "SUCCEEDED", outcome
    folder = Path(outcome["result"]["receipt"]["path"])
    value = json.loads((folder / "attachment-configuration-records.json").read_bytes())
    assert value["publication"] == "HISTORICAL_HELD"
    assert value["document"] == artifact.to_dict()


def test_export_budget_failure_does_not_truncate_original(retained, monkeypatch):
    service, setup, artifact, _, _ = retained
    original = arrival._json_payload

    def oversized(value):
        payload = original(value)
        if value.get("schema") == "rocell.wizard_physical_configuration_export.v1":
            return b"x" * (arrival.MAX_RESULT_BYTES + 1)
        return payload

    monkeypatch.setattr(arrival, "_json_payload", oversized)
    with pytest.raises(WizardError) as error:
        service._export()
    assert error.value.code == "CONFIGURATION_RECORD_EXPORT_BUDGET"
    assert (
        setup.retained_configuration_diagnostics()["record"]["document"]
        == artifact.to_dict()
    )
