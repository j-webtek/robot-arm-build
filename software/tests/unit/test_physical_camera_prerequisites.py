"""Actual fixed-source validators; no native, inventory, acquisition or M1 work."""

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import shutil
from threading import Event
import time

import pytest

from rocell.application import physical_camera_prerequisites as module
from rocell.application import physical_source_preflight as preflight
from rocell.application.physical_camera_selection import PhysicalCameraSelection
from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
from test_physical_camera_selection import physical_enrollment, selected

WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64
SESSION = "physical-camera-" + "1" * 32
LAUNCH = "wizard-native-fixture"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    # Real current four files; the broad source fingerprint is an explicit
    # fixture, not an assertion that this tiny copied tree is the real runtime.
    for _, relative in module.SOURCES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, target)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    return tmp_path


def collect(workspace, **kwargs):
    return module.collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=SESSION,
        launch_session_id=LAUNCH,
        cancellation=kwargs.pop("cancellation", Event()),
        deadline_ns=kwargs.pop("deadline_ns", time.monotonic_ns() + 30_000_000_000),
        **kwargs,
    )


def verify(artifact, **changes):
    expected = dict(
        expected_source_sha256=SOURCE,
        expected_session_id=SESSION,
        expected_launch_session_id=LAUNCH,
        expected_evidence_sha256=artifact.evidence_sha256,
    )
    expected.update(changes)
    return module.verify_physical_camera_prerequisites(artifact.payload, **expected)


def held_preflight():
    """Strict actual report type with deliberately unavailable fixture checks."""
    data = {
        "schema": preflight.SOURCE_PREFLIGHT_SCHEMA,
        "composition": preflight.SOURCE_PREFLIGHT_COMPOSITION,
        "binding": {
            "cell_id": "source-cell",
            "session_id": "source-only-session",
            "attempt_id": "source-attempt",
            "operator_id": "source-operator",
            "workspace_source_sha256": SOURCE,
            "permit_sha256": "b" * 64,
            "worker_sha256": "c" * 64,
            "operation_sha256": preflight.SOURCE_PREFLIGHT_OPERATION_SHA256,
        },
        "files": [],
        "observations": {
            "software_fingerprint_before": SOURCE,
            "software_fingerprint_after": SOURCE,
            "fixed_snapshot_sha256_before": None,
            "fixed_snapshot_sha256_after": None,
            "foundation": None,
            "native_development_build": None,
            "fixed_file_pin": "PORTABLE_BEFORE_AFTER_ONLY",
            "failed_source": None,
        },
        "outcome": "HELD",
        "errors": ["FIXTURE_SOURCES_UNAVAILABLE"],
        "canonical_stage_holds": list(preflight._HOLDS),
        "canonical_stage_pass": False,
        "physical_authority": False,
        "device_io_performed": False,
        "power_state": "UNKNOWN",
        "limitations": list(preflight._LIMITATIONS),
    }
    data["checks"] = preflight._checks(data)
    return preflight.PhysicalSourcePreflightReport(preflight._canonical(data))


def test_actual_questions_hazards_and_epoch_requirements(workspace):
    before = {
        relative: (workspace / relative).read_bytes() for _, relative in module.SOURCES
    }
    artifact = collect(workspace)
    assert verify(artifact) == artifact
    summary = artifact.safe_summary()
    assert summary["status"] == "REQUIREMENTS_RETAINED_NOT_ASSESSED"
    assert [len(row["intake_rows"]) for row in summary["stages"]] == [0, 0, 16, 1]
    assert [row["stage"] for row in summary["stages"]] == [
        stage.value for stage in module.STAGE_ORDER[:4]
    ]
    assert [row["id"] for row in summary["hazards"]] == [
        "HZ-007",
        "HZ-008",
        "HZ-009",
        "HZ-010",
        "HZ-012",
    ]
    assert all(
        row["controls"] and row["required_evidence"] for row in summary["hazards"]
    )
    assert len(summary["epochs"]) == 8
    assert all(
        row["status"] == "UNMEASURED" and row["value"] is None
        for row in summary["epochs"]
    )
    questions = summary["stages"][2]["intake_rows"]
    assert questions[0]["record_id"] == "INT-001"
    assert questions[0]["candidate_or_requirement"] == "610 nominal"
    assert all(q["observation"] is None for q in questions)
    flatness = next(q for q in questions if q["record_id"] == "INT-005")
    assert flatness["template_status"] == "OPEN_LIMIT"
    assert flatness["acceptance"] == {
        "status": "DEFERRED_LIMIT",
        "owner_stage": "noncontact_acceptance",
        "prerequisites": ["TARGET_ACCURACY_BUDGET_CLOSED"],
        "measurement_required": True,
    }
    assert summary["power_state"] == "UNKNOWN"
    for name in (
        "physical_authority",
        "qualified",
        "canonical_stage_pass",
        "device_io_performed",
    ):
        assert summary[name] is False
    assert summary["metadata_selection"] is summary["source_preflight"] is None
    for row in artifact.to_dict()["source_files"]:
        assert row["payload_utf8"].encode("utf-8") == before[row["relative_path"]]
    assert before == {
        relative: (workspace / relative).read_bytes() for _, relative in module.SOURCES
    }
    assert len(artifact.payload) < 112 * 1024


def test_optional_exact_types_keep_original_domains_and_full_bytes(workspace):
    selection = selected(physical_enrollment(unicode=True))
    report = held_preflight()
    artifact = collect(
        workspace,
        selection=selection,
        source_preflight_report=report,
        expected_source_preflight_sha256=report.sha256,
    )
    data, view = artifact.to_dict(), artifact.safe_summary()
    assert data["selection"]["payload_ascii"].encode("ascii") == selection.payload
    assert data["source_preflight"]["payload_ascii"].encode("ascii") == report.payload
    assert (
        data["source_preflight"]["origin"] == "RETAINED_SEPARATE_SOURCE_ONLY_DIAGNOSTIC"
    )
    assert view["metadata_selection"] == selection.safe_summary()
    assert view["source_preflight"]["origin_session_id"] == "source-only-session"
    assert view["source_preflight"]["outcome"] == "HELD"
    assert "SOURCE_PREFLIGHT_HELD" in view["missing_requirements"]
    assert (
        "METADATA_SELECTION_ONLY_NOT_RECEIVED_UNIT_QUALIFICATION"
        in view["missing_requirements"]
    )
    assert verify(artifact).payload == artifact.payload
    assert "symbolic_link" not in json.dumps(view)


def test_public_envelope_preserves_full_document_and_summary(workspace):
    artifact = collect(
        workspace,
        source_preflight_report=held_preflight(),
        expected_source_preflight_sha256=held_preflight().sha256,
    )
    envelope = {
        "schema": "test.explicit.non_M1_operation",
        "steps": [
            {
                "report": {
                    "prerequisites": artifact.safe_summary(),
                    "full_document": artifact.to_dict(),
                }
            }
        ],
        "physical_authority": False,
    }
    assert sanitize_diagnostic_record(envelope) == envelope
    assert len(json.dumps(envelope).encode()) < 128 * 1024


def test_restore_and_views_pure_immutable_detached(workspace, monkeypatch):
    artifact = collect(workspace, selection=selected(physical_enrollment()))

    def forbidden(*args, **kwargs):
        pytest.fail("Restoration and views must not access files or providers")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(module, "source_fingerprint", forbidden)
    monkeypatch.setattr(
        module.stage_contract, "load_physical_onboarding_stage_catalog", forbidden
    )
    recreated = verify(artifact)
    before = recreated.payload
    view = recreated.safe_summary()
    view["epochs"][0]["status"] = "QUALIFIED"
    data = recreated.to_dict()
    data["physical_authority"] = True
    assert recreated.payload == before
    assert recreated.safe_summary()["epochs"][0]["status"] == "UNMEASURED"
    with pytest.raises(FrozenInstanceError):
        recreated.payload = b"changed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_source_sha256", "b" * 64),
        ("expected_session_id", "other-session"),
        ("expected_launch_session_id", "other-launch"),
        ("expected_evidence_sha256", "b" * 64),
    ],
)
def test_external_expected_bindings_required(workspace, field, value):
    with pytest.raises(module.PhysicalCameraPrerequisitesError):
        verify(collect(workspace), **{field: value})


@pytest.mark.parametrize(
    "change",
    [
        "unknown",
        "authority",
        "integer-false",
        "power",
        "observation",
        "acceptance",
        "intake-omission",
        "hazard",
        "epoch",
        "source-hash",
        "source-bytes",
        "source-role",
        "source-after",
    ],
)
def test_retained_schema_and_derived_claim_tampering_rejected(workspace, change):
    data = collect(workspace).to_dict()
    if change == "unknown":
        data["accepted"] = True
    elif change in {"authority", "integer-false"}:
        data["physical_authority"] = True if change == "authority" else 0
    elif change == "power":
        data["power_state"] = "DISCONNECTED"
    elif change == "observation":
        data["requirements"]["stages"][2]["intake_rows"][0]["observation"] = 610
    elif change == "acceptance":
        data["requirements"]["stages"][2]["intake_rows"][4]["acceptance"][
            "status"
        ] = "PASS"
    elif change == "intake-omission":
        data["requirements"]["stages"][2]["intake_rows"].pop()
    elif change == "hazard":
        data["requirements"]["hazards"][0]["required_evidence"] = []
    elif change == "epoch":
        data["requirements"]["epochs"][0]["value"] = "a" * 64
    elif change == "source-hash":
        data["source_files"][0]["sha256"] = "b" * 64
    elif change == "source-bytes":
        data["source_files"][0]["bytes"] += 1
    elif change == "source-role":
        data["source_files"][0]["role"] = "intake_template"
    else:
        data["source_observations"]["after_source_sha256"] = "b" * 64
    with pytest.raises(module.PhysicalCameraPrerequisitesError):
        module.PhysicalCameraPrerequisites(module._canonical(data))


@pytest.mark.parametrize(
    "payload",
    [b"{}", b'{"schema":1,"schema":2}', b"NaN", bytearray(b"{}"), b"{" * 9000],
)
def test_malformed_payloads_rejected(payload):
    with pytest.raises(module.PhysicalCameraPrerequisitesError):
        module.PhysicalCameraPrerequisites(payload)


@pytest.mark.parametrize(
    "failure",
    [
        "source-before",
        "source-after",
        "cancel-before",
        "cancel-after-read",
        "deadline-before",
        "deadline-after-read",
        "deadline-unbounded",
        "file-limit",
        "document-limit",
    ],
)
def test_collection_stops_on_drift_cancel_and_bounds(workspace, monkeypatch, failure):
    kwargs = {}
    cancellation = Event()
    if failure == "source-before":
        monkeypatch.setattr(module, "source_fingerprint", lambda _: "b" * 64)
    elif failure == "source-after":
        hashes = iter((SOURCE, "b" * 64))
        monkeypatch.setattr(module, "source_fingerprint", lambda _: next(hashes))
    elif failure == "cancel-before":
        cancellation.set()
    elif failure in {"deadline-before", "deadline-unbounded"}:
        kwargs["deadline_ns"] = time.monotonic_ns() + (
            -1 if failure == "deadline-before" else 60_000_000_000
        )
    elif failure == "file-limit":
        monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 100)
    elif failure == "document-limit":
        monkeypatch.setattr(module, "MAX_EVIDENCE_BYTES", 1000)
    elif failure in {"cancel-after-read", "deadline-after-read"}:
        reader = module.read_bounded_regular_file

        def changed(*args, **kwargs):
            raw = reader(*args, **kwargs)
            if failure == "cancel-after-read":
                cancellation.set()
            else:
                monkeypatch.setattr(module.time, "monotonic_ns", lambda: 90_000_000_000)
            return raw

        monkeypatch.setattr(module, "read_bounded_regular_file", changed)
        if failure == "deadline-after-read":
            monkeypatch.setattr(module.time, "monotonic_ns", lambda: 1)
            kwargs["deadline_ns"] = 20_000_000_000
    with pytest.raises(module.PhysicalCameraPrerequisitesError):
        collect(workspace, cancellation=cancellation, **kwargs)


def test_validator_reads_must_match_retained_bytes(workspace, monkeypatch):
    original = module.stage_contract.load_physical_onboarding_stage_catalog

    def drift(root):
        path = root / module.SOURCES[0][1]
        path.write_bytes(path.read_bytes() + b"\n")
        return original(root)

    monkeypatch.setattr(
        module.stage_contract, "load_physical_onboarding_stage_catalog", drift
    )
    with pytest.raises(
        module.PhysicalCameraPrerequisitesError, match="VALIDATOR_SOURCE_CHANGED"
    ):
        collect(workspace)


@pytest.mark.parametrize(
    "argument",
    [
        "selection-dict",
        "selection-source",
        "selection-launch",
        "preflight-dict",
        "preflight-missing-hash",
        "preflight-wrong-hash",
        "preflight-missing-report",
    ],
)
def test_context_not_arbitrary_summaries_or_wrong_bindings(workspace, argument):
    kwargs = {}
    if argument.startswith("selection"):
        selection = selected(physical_enrollment())
        if argument == "selection-dict":
            kwargs["selection"] = selection.identity_document
        else:
            # A valid selection's source/launch must still match this collection.
            data = selection.identity_document
            field = (
                "source_sha256"
                if argument == "selection-source"
                else "launch_session_id"
            )
            review_field = (
                "source_sha256" if argument == "selection-source" else "session_id"
            )
            data[field] = (
                "b" * 64 if argument == "selection-source" else "different-launch"
            )
            data["metadata_review"][review_field] = data[field]
            data["metadata_review_binding_sha256"] = hashlib.sha256(
                json.dumps(
                    data["metadata_review"],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            kwargs["selection"] = PhysicalCameraSelection(module._canonical(data))
    else:
        report = held_preflight()
        kwargs["source_preflight_report"] = report
        kwargs["expected_source_preflight_sha256"] = report.sha256
        if argument == "preflight-dict":
            kwargs["source_preflight_report"] = report.safe_summary()
        elif argument == "preflight-missing-hash":
            kwargs.pop("expected_source_preflight_sha256")
        elif argument == "preflight-wrong-hash":
            kwargs["expected_source_preflight_sha256"] = "b" * 64
        else:
            kwargs.pop("source_preflight_report")
    with pytest.raises(module.PhysicalCameraPrerequisitesError):
        collect(workspace, **kwargs)
