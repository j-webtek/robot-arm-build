from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.application.prehardware_qualification import (
    PrehardwareQualificationPolicy,
    PrehardwareQualificationReport,
    QualificationCaseResult,
)
from rocell.evidence.prehardware_qualification import (
    CASES_ARTIFACT_SCHEMA,
    MANIFEST_SCHEMA,
    MAX_ARTIFACT_BYTES,
    MAX_PACKAGE_BYTES,
    PrehardwareQualificationEvidenceError,
    _artifact_documents,
    _replay_prehardware_qualification_with_runner,
    record_prehardware_qualification,
    replay_prehardware_qualification,
    verify_prehardware_qualification_record,
)
from rocell.evidence.virtual_session import MANIFEST_SCHEMA as SESSION_MANIFEST_SCHEMA


EXPECTED_FILES = {
    "source.json",
    "policy.json",
    "cases.json",
    "coverage.json",
    "resources.json",
    "report.json",
    "manifest.json",
}


def _source() -> dict[str, object]:
    return {
        "bootstrap_sha256": "1" * 64,
        "manifest_id": "TEST-FREEZE-009",
        "manifest_sha256": "2" * 64,
        "snapshot_sha256": "3" * 64,
        "design_revision": "RC03-INT-R1",
        "active_build_id": "TEST-BUILD-001",
        "simulation_bundle_id": "TEST-SIMULATION-BUNDLE",
        "simulation_bundle_lock_sha256": "4" * 64,
        "alignment_status": "PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS",
        "alignment_report_sha256": "5" * 64,
        "virtual_profile_id": "test-virtual-profile",
        "virtual_profile_sha256": "6" * 64,
        "virtual_profile_classification": "UNMEASURED_SENSITIVITY_OVERLAY",
        "virtual_profile_simulation_only": True,
        "virtual_profile_physical_release_effect": "NONE",
        "study_input_id": "test-study-input",
        "park_probe_id": "test-park-probe",
        "historical_layout_report_sha256": "7" * 64,
        "historical_mission_coverage_sha256": "8" * 64,
    }


def _quick_coverage() -> dict[str, object]:
    return {
        "evaluated": False,
        "state": "NOT_RUN",
        "complete_catalog_evidence": False,
        "expected_route_count": 75,
        "expected_keyboard_route_count": 46,
        "expected_phone_route_count": 29,
        "route_count": 0,
        "accepted_route_count": None,
        "rejected_route_count": None,
        "keyboard": None,
        "phone": None,
        "all_routes_accepted": False,
        "coverage_report_sha256": None,
        "selected_profile_source_coverage_sha256": "8" * 64,
        "reason": "QUICK_PROFILE_DOES_NOT_RECOMPUTE_MULTI_MINUTE_75_ROUTE_SCREEN",
    }


def _resource_usage(cases: tuple[QualificationCaseResult, ...]) -> dict[str, object]:
    def total(key: str) -> int:
        return sum(
            value
            for case in cases
            if isinstance((value := case.metrics.get(key, 0)), int)
            and not isinstance(value, bool)
        )

    return {
        "case_count": len(cases),
        "session_run_count": sum(
            case.spec.category
            in {"ADAPTIVE_SESSION", "LEGACY_FAULT_SESSION", "DETERMINISM_REPLAY"}
            for case in cases
        ),
        "virtual_commands_executed": total("virtual_commands_executed"),
        "camera_capture_count": total("camera_capture_count"),
        "correction_installation_count": total("correction_installation_count"),
        "contact_attempt_count": total("contact_attempt_count"),
        "legacy_event_count": total("legacy_event_count"),
        "mission_route_count": total("route_count"),
        "mission_total_waypoint_records": total("total_waypoint_records"),
        "mission_total_ik_solves": total("total_ik_solves"),
        "mission_total_task_jacobian_fk_evaluations": total(
            "total_task_jacobian_fk_evaluations"
        ),
        "wall_clock_time_recorded": False,
        "hardware_commands_generated": 0,
    }


def _report(*, variant: str = "recorded") -> PrehardwareQualificationReport:
    policy = PrehardwareQualificationPolicy(profile="quick")
    cases = tuple(
        QualificationCaseResult(
            spec=spec,
            observed_status=f"TEST_{variant}_{index}",
            passed=True,
            source_report_sha256=hashlib.sha256(
                f"{variant}|{spec.case_id}".encode("utf-8")
            ).hexdigest(),
            authority_verified=True,
            metrics={
                "virtual_commands_executed": index + 1,
                "camera_capture_count": int(
                    spec.category in {"ADAPTIVE_SESSION", "DETERMINISM_REPLAY"}
                ),
                "correction_installation_count": int(
                    spec.category == "ADAPTIVE_SESSION"
                ),
                "contact_attempt_count": int(spec.category == "ADAPTIVE_SESSION"),
                "legacy_event_count": int(spec.category == "LEGACY_FAULT_SESSION"),
                "hardware_commands_generated": 0,
            },
        )
        for index, spec in enumerate(policy.selected_cases)
    )
    return PrehardwareQualificationReport(
        policy=policy,
        source=_source(),
        cases=cases,
        coverage_summary=_quick_coverage(),
        resource_usage=_resource_usage(cases),
        physical_holds=(
            "PHYSICAL_RELEASE_UNRELEASED",
            "CAMERA_INTRINSICS_UNMEASURED",
        ),
        final_revalidation_passed=True,
    )


@pytest.fixture
def report() -> PrehardwareQualificationReport:
    return _report()


@pytest.fixture
def recorded(
    tmp_path: Path,
    report: PrehardwareQualificationReport,
) -> tuple[Path, PrehardwareQualificationReport]:
    evidence_root = tmp_path / "runs"
    evidence_root.mkdir()
    record = record_prehardware_qualification(report, evidence_root)
    return record.manifest_path, report


def _canonical_write(path: Path, document: object) -> None:
    path.write_bytes(
        (
            json.dumps(
                document,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _rehash_artifact_and_manifest(manifest_path: Path, filename: str) -> None:
    manifest = _load(manifest_path)
    payload = (manifest_path.parent / filename).read_bytes()
    row = next(item for item in manifest["artifacts"] if item["path"] == filename)
    row["bytes"] = len(payload)
    row["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest["total_artifact_bytes"] = sum(
        item["bytes"] for item in manifest["artifacts"]
    )
    core = dict(manifest)
    del core["package_sha256"]
    manifest["package_sha256"] = _stable_hash(core)
    _canonical_write(manifest_path, manifest)


def _rehash_manifest_only(manifest_path: Path, manifest: dict[str, Any]) -> None:
    core = dict(manifest)
    del core["package_sha256"]
    manifest["package_sha256"] = _stable_hash(core)
    _canonical_write(manifest_path, manifest)


def _keys(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _keys(child)


def test_record_verify_is_schema_separated_bounded_redacted_and_immutable(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, report = recorded
    record_directory = manifest_path.parent
    manifest = _load(manifest_path)

    assert {item.name for item in record_directory.iterdir()} == EXPECTED_FILES
    assert manifest["schema"] == MANIFEST_SCHEMA
    assert manifest["schema"] != SESSION_MANIFEST_SCHEMA
    assert manifest["report_sha256"] == report.report_hash
    assert manifest["profile"] == "quick"
    assert manifest["case_count"] == 5
    assert manifest["artifact_count"] == 6
    assert manifest["total_artifact_bytes"] <= MAX_PACKAGE_BYTES
    assert all(row["bytes"] <= MAX_ARTIFACT_BYTES for row in manifest["artifacts"])

    verified = verify_prehardware_qualification_record(manifest_path)
    assert verified.report_sha256 == report.report_hash
    assert verified.profile == "quick"
    assert verified.case_count == 5
    assert verified.manifest_path == manifest_path.resolve()
    assert len(verified.manifest_sha256) == 64
    assert len(verified.package_sha256) == 64
    assert verified.document("cases.json")["schema"] == CASES_ARTIFACT_SCHEMA
    # The immutable v1 child report keeps its legacy runner-local declaration.
    # The separate evidence manifest/record—not a rewritten child hash—is the
    # authoritative proof that recording and replay are now available.
    assert verified.document("report.json")["evidence_recording"] == {
        "recorded": False,
        "replay_supported": False,
        "reason": "QUALIFICATION_EVIDENCE_PACKAGE_SCHEMA_NOT_IMPLEMENTED",
    }
    with pytest.raises(TypeError):
        verified.document("source.json")["mutated"] = True  # type: ignore[index]
    with pytest.raises(PrehardwareQualificationEvidenceError, match="no artifact"):
        verified.document("jpeg-0001.jpg")

    documents = {
        name: verified.document(name) for name in EXPECTED_FILES - {"manifest.json"}
    }
    all_keys = {key.lower() for key in _keys(documents)}
    assert {
        "jpeg_bytes",
        "raw_output",
        "plaintext",
        "truth_translation_wv_mm",
        "truth_yaw_board_deg",
    }.isdisjoint(all_keys)
    cases = verified.document("cases.json")["cases"]
    assert isinstance(cases, tuple)
    for item in cases:
        assert isinstance(item, Mapping)
        case = item["case"]
        assert isinstance(case, Mapping)
        commitment = case.get("requested_text")
        if commitment is not None:
            assert commitment["plaintext_serialized"] is False
            assert set(commitment) == {
                "sha256",
                "normalized_codepoint_length",
                "plaintext_serialized",
            }


def test_duplicate_record_is_rejected_as_immutable(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, report = recorded
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="already exists",
    ):
        record_prehardware_qualification(report, manifest_path.parent.parent)


def test_replay_verifies_first_and_compares_all_artifacts(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, report = recorded
    calls: list[tuple[Path, object, Path | None]] = []

    def runner(
        workspace: Path,
        *,
        policy: object,
        runtime_path: Path | None,
    ) -> PrehardwareQualificationReport:
        calls.append((workspace, policy, runtime_path))
        return report

    replay = _replay_prehardware_qualification_with_runner(
        Path("workspace"),
        manifest_path,
        runtime_path=Path("software/config/runtime.json"),
        qualification_runner=runner,
    )

    assert replay.identical is True
    assert replay.status == "QUALIFICATION_REPLAY_IDENTICAL"
    assert replay.recorded_report_sha256 == report.report_hash
    assert replay.recomputed_report_sha256 == report.report_hash
    assert replay.compared_artifact_count == 6
    assert len(calls) == 1
    workspace, policy, runtime_path = calls[0]
    assert workspace == Path("workspace")
    assert isinstance(policy, PrehardwareQualificationPolicy)
    assert policy.to_dict() == report.policy.to_dict()
    assert runtime_path == Path("software/config/runtime.json")
    document = replay.to_dict()
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["execution_authorized"] is False
    assert len(document["replay_sha256"]) == 64


def test_public_replay_uses_only_locked_public_runner(
    recorded: tuple[Path, PrehardwareQualificationReport],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, report = recorded
    import rocell.evidence.prehardware_qualification as evidence

    calls = 0

    def runner(*_args: object, **_kwargs: object) -> PrehardwareQualificationReport:
        nonlocal calls
        calls += 1
        return report

    monkeypatch.setattr(evidence, "run_prehardware_qualification", runner)
    replay = replay_prehardware_qualification(Path("workspace"), manifest_path)

    assert replay.identical
    assert calls == 1


def test_replay_detects_a_valid_but_different_recomputation(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, _ = recorded
    different = _report(variant="recomputed")

    replay = _replay_prehardware_qualification_with_runner(
        Path("workspace"),
        manifest_path,
        runtime_path=None,
        qualification_runner=lambda *_args, **_kwargs: different,
    )

    assert replay.identical is False
    assert replay.status == "QUALIFICATION_REPLAY_DIVERGED"
    assert replay.recorded_report_sha256 != replay.recomputed_report_sha256


def test_replay_rejects_non_report_runner_result(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, _ = recorded
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="invalid report type",
    ):
        _replay_prehardware_qualification_with_runner(
            Path("workspace"),
            manifest_path,
            runtime_path=None,
            qualification_runner=lambda *_args, **_kwargs: object(),  # type: ignore[arg-type,return-value]
        )


@pytest.mark.parametrize("operation", ("missing", "extra", "directory"))
def test_missing_extra_and_partial_packages_are_rejected(
    recorded: tuple[Path, PrehardwareQualificationReport],
    operation: str,
) -> None:
    manifest_path, _ = recorded
    if operation == "missing":
        (manifest_path.parent / "coverage.json").unlink()
    elif operation == "extra":
        (manifest_path.parent / "unexpected.json").write_text("{}", encoding="utf-8")
    else:
        (manifest_path.parent / "partial-child").mkdir()

    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="directory is not exact",
    ):
        verify_prehardware_qualification_record(manifest_path)


def test_byte_tamper_and_duplicate_json_keys_are_rejected(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, _ = recorded
    source_path = manifest_path.parent / "source.json"
    original = source_path.read_bytes()
    source_path.write_bytes(original.replace(b"TEST-FREEZE-009", b"TEST-FREEZE-008"))
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="byte/hash mismatch",
    ):
        verify_prehardware_qualification_record(manifest_path)

    source_path.write_bytes(
        original.replace(
            b'{\n  "schema":',
            b'{\n  "schema": "duplicate",\n  "schema":',
            1,
        )
    )
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="duplicate JSON key",
    ):
        verify_prehardware_qualification_record(manifest_path)


@pytest.mark.parametrize(
    ("filename", "mutator"),
    (
        (
            "source.json",
            lambda value: value["source"].__setitem__("bootstrap_sha256", "9" * 64),
        ),
        (
            "policy.json",
            lambda value: value.__setitem__("maximum_total_virtual_commands", 8_191),
        ),
        (
            "cases.json",
            lambda value: value["cases"][0].__setitem__(
                "source_report_sha256", "9" * 64
            ),
        ),
        (
            "coverage.json",
            lambda value: value.__setitem__("coverage_state", "ALL_ROUTES_ACCEPTED"),
        ),
        (
            "resources.json",
            lambda value: value["resource_usage"].__setitem__("case_count", 4),
        ),
    ),
)
def test_split_artifact_substitution_fails_after_outer_rehash(
    recorded: tuple[Path, PrehardwareQualificationReport],
    filename: str,
    mutator: Callable[[dict[str, Any]], None],
) -> None:
    manifest_path, _ = recorded
    artifact_path = manifest_path.parent / filename
    value = _load(artifact_path)
    mutator(value)
    _canonical_write(artifact_path, value)
    _rehash_artifact_and_manifest(manifest_path, filename)

    with pytest.raises(PrehardwareQualificationEvidenceError):
        verify_prehardware_qualification_record(manifest_path)


@pytest.mark.parametrize("mutation", ("traversal", "duplicate", "reorder"))
def test_manifest_paths_are_plain_unique_and_ordered(
    recorded: tuple[Path, PrehardwareQualificationReport],
    mutation: str,
) -> None:
    manifest_path, _ = recorded
    manifest = _load(manifest_path)
    if mutation == "traversal":
        manifest["artifacts"][0]["path"] = "../source.json"
    elif mutation == "duplicate":
        manifest["artifacts"][1]["path"] = manifest["artifacts"][0]["path"]
    else:
        manifest["artifacts"][0], manifest["artifacts"][1] = (
            manifest["artifacts"][1],
            manifest["artifacts"][0],
        )
    _rehash_manifest_only(manifest_path, manifest)

    with pytest.raises(PrehardwareQualificationEvidenceError):
        verify_prehardware_qualification_record(manifest_path)


def test_noncanonical_manifest_is_rejected(
    recorded: tuple[Path, PrehardwareQualificationReport],
) -> None:
    manifest_path, _ = recorded
    manifest = _load(manifest_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="not canonical JSON",
    ):
        verify_prehardware_qualification_record(manifest_path)


def test_record_failure_removes_partial_directory(
    tmp_path: Path,
    report: PrehardwareQualificationReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.evidence.prehardware_qualification as evidence

    evidence_root = tmp_path / "runs"
    evidence_root.mkdir()
    monkeypatch.setattr(evidence, "MAX_ARTIFACT_BYTES", 64)

    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="artifact exceeds",
    ):
        record_prehardware_qualification(report, evidence_root)

    assert tuple(evidence_root.iterdir()) == ()


def test_record_rejects_missing_root_and_wrong_report_type(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="PrehardwareQualificationReport"):
        record_prehardware_qualification(object(), tmp_path)  # type: ignore[arg-type]
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="root is missing",
    ):
        record_prehardware_qualification(_report(), tmp_path / "missing")


def test_record_rejects_boolean_hardware_command_count(
    tmp_path: Path,
    report: PrehardwareQualificationReport,
) -> None:
    cases = list(report.cases)
    cases[0] = replace(
        cases[0],
        metrics={**dict(cases[0].metrics), "hardware_commands_generated": False},
    )
    malformed = replace(report, cases=tuple(cases))
    evidence_root = tmp_path / "runs"
    evidence_root.mkdir()

    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="hardware commands",
    ):
        record_prehardware_qualification(malformed, evidence_root)


def test_manifest_or_record_directory_symlink_is_rejected(
    recorded: tuple[Path, PrehardwareQualificationReport],
    tmp_path: Path,
) -> None:
    manifest_path, _ = recorded
    link = tmp_path / "manifest-link.json"
    try:
        link.symlink_to(manifest_path)
    except OSError:
        pytest.skip("symlink creation is not available on this host")
    with pytest.raises(
        PrehardwareQualificationEvidenceError,
        match="must not be symlinks",
    ):
        verify_prehardware_qualification_record(link)


def test_completely_replaced_self_consistent_package_requires_replay(
    tmp_path: Path,
) -> None:
    """Hashes detect accidental tamper; recomputation detects wholesale forgery."""

    evidence_root = tmp_path / "runs"
    evidence_root.mkdir()
    forged_report = _report(variant="forged")
    record = record_prehardware_qualification(forged_report, evidence_root)
    # A self-consistent package is structurally valid in the absence of an
    # external signature or pinned manifest digest.
    verify_prehardware_qualification_record(record.manifest_path)

    genuine_report = _report(variant="genuine")
    replay = _replay_prehardware_qualification_with_runner(
        tmp_path,
        record.manifest_path,
        runtime_path=None,
        qualification_runner=lambda *_args, **_kwargs: genuine_report,
    )
    assert replay.identical is False


def test_generated_artifact_documents_never_include_binary_payloads(
    report: PrehardwareQualificationReport,
) -> None:
    documents = _artifact_documents(report)

    def values(value: object) -> Iterator[object]:
        yield value
        if isinstance(value, Mapping):
            for child in value.values():
                yield from values(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from values(child)

    assert not any(isinstance(value, bytes) for value in values(documents))
    assert all(
        len(
            (
                json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
            ).encode("utf-8")
        )
        <= MAX_ARTIFACT_BYTES
        for document in documents.values()
    )
