from __future__ import annotations

import hashlib
import json
import operator
from pathlib import Path
from typing import Any

import pytest

from rocell.application.virtual_session import (
    VirtualSessionReport,
    run_default_virtual_session,
)
from rocell.evidence.virtual_session import (
    VirtualSessionEvidenceError,
    record_virtual_session,
    replay_virtual_session,
    verify_virtual_session_record,
)
from rocell.simulation.virtual_workcell import (
    VirtualFaultKind,
    VirtualFaultScript,
    VirtualFaultTrigger,
)


WORKSPACE = Path(__file__).resolve().parents[3]
LEGACY_PIXEL_PREDECESSOR = (
    WORKSPACE
    / "software/runs/virtual-92ebfd731214e512276886b6/manifest.json"
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _rehash_artifact(manifest_path: Path, name: str) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    rows = manifest["artifacts"]
    assert isinstance(rows, list)
    payload = (manifest_path.parent / name).read_bytes()
    row = next(item for item in rows if item["path"] == name)
    row["bytes"] = len(payload)
    row["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest["total_artifact_bytes"] = sum(item["bytes"] for item in rows)
    core = dict(manifest)
    del core["package_hash"]
    manifest["package_hash"] = _stable_hash(core)
    manifest_path.write_bytes(_canonical_bytes(manifest))


def _rebind_report_envelope_after_tamper(record_directory: Path) -> Path:
    """Make outer hashes coherent so semantic correlation checks are exercised."""

    report_path = record_directory / "report.json"
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    report_core = dict(report)
    del report_core["report_hash"]
    report["report_hash"] = _stable_hash(report_core)
    report_path.write_bytes(_canonical_bytes(report))

    manifest_path = record_directory / "manifest.json"
    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    rows = manifest["artifacts"]
    assert isinstance(rows, list)
    report_payload = report_path.read_bytes()
    report_row = next(item for item in rows if item["path"] == "report.json")
    report_row["bytes"] = len(report_payload)
    report_row["sha256"] = hashlib.sha256(report_payload).hexdigest()
    manifest["total_artifact_bytes"] = sum(item["bytes"] for item in rows)
    manifest["report_hash"] = report["report_hash"]
    new_record_id = f"virtual-{report['report_hash'][:24]}"
    manifest["record_id"] = new_record_id
    manifest_core = dict(manifest)
    del manifest_core["package_hash"]
    manifest["package_hash"] = _stable_hash(manifest_core)
    manifest_path.write_bytes(_canonical_bytes(manifest))

    rebound = record_directory.parent / new_record_id
    record_directory.rename(rebound)
    return rebound / "manifest.json"


def _rebind_vision_envelopes_after_nested_tamper(record_directory: Path) -> Path:
    """Rehash every outer vision envelope while leaving nested fraud intact."""

    vision_path = record_directory / "vision.json"
    vision: dict[str, Any] = json.loads(vision_path.read_text(encoding="utf-8"))
    attempt = vision["attempts"][0]
    result = attempt["result"]
    result_core = dict(result)
    del result_core["result_hash"]
    result["result_hash"] = _stable_hash(result_core)
    attempt["result_hash"] = result["result_hash"]
    attempt_core = dict(attempt)
    del attempt_core["attempt_hash"]
    attempt["attempt_hash"] = _stable_hash(attempt_core)
    vision_core = dict(vision)
    del vision_core["ledger_hash"]
    vision["ledger_hash"] = _stable_hash(vision_core)
    vision_path.write_bytes(_canonical_bytes(vision))
    _rehash_artifact(record_directory / "manifest.json", "vision.json")

    report_path = record_directory / "report.json"
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    report["pixel_vision"]["ledger_hash"] = vision["ledger_hash"]
    report_path.write_bytes(_canonical_bytes(report))
    return _rebind_report_envelope_after_tamper(record_directory)


@pytest.fixture(scope="module")
def keyboard_report() -> VirtualSessionReport:
    return run_default_virtual_session(WORKSPACE, "keyboard", "test")


def test_record_verify_replay_is_identical_and_deeply_immutable(
    tmp_path: Path,
    keyboard_report: VirtualSessionReport,
) -> None:
    record = record_virtual_session(keyboard_report, tmp_path)
    verified = verify_virtual_session_record(record.manifest_path)

    outcome = verified.document("report.json")["outcome"]
    actions = verified.document("action-plan.json")["actions"]
    with pytest.raises(TypeError):
        operator.setitem(outcome, "matches", False)
    assert isinstance(actions, tuple)

    replay = replay_virtual_session(WORKSPACE, record.manifest_path)
    assert replay.identical is True
    assert replay.status == "REPLAY_IDENTICAL"


def test_duplicate_record_is_immutable(
    tmp_path: Path,
    keyboard_report: VirtualSessionReport,
) -> None:
    record_virtual_session(keyboard_report, tmp_path)
    with pytest.raises(
        VirtualSessionEvidenceError,
        match="immutable evidence record already exists",
    ):
        record_virtual_session(keyboard_report, tmp_path)


def test_canonical_trajectory_status_forgery_is_rejected(
    tmp_path: Path,
    keyboard_report: VirtualSessionReport,
) -> None:
    record = record_virtual_session(keyboard_report, tmp_path)
    trajectory_path = record.directory / "trajectory.json"
    trajectory: dict[str, Any] = json.loads(
        trajectory_path.read_text(encoding="utf-8")
    )
    trajectory["status"] = "FORGED_STATUS"
    trajectory_path.write_bytes(_canonical_bytes(trajectory))
    _rehash_artifact(record.manifest_path, "trajectory.json")

    with pytest.raises(
        VirtualSessionEvidenceError,
        match="recorded trajectory hash mismatch",
    ):
        verify_virtual_session_record(record.manifest_path)


def test_external_artifact_symlink_is_rejected(
    tmp_path: Path,
    keyboard_report: VirtualSessionReport,
) -> None:
    record = record_virtual_session(keyboard_report, tmp_path)
    artifact = record.directory / "scenario.json"
    external = tmp_path / "outside-scenario.json"
    external.write_bytes(artifact.read_bytes())
    artifact.unlink()
    try:
        artifact.symlink_to(external)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"artifact symlinks are unavailable on this platform: {exc}")

    with pytest.raises(
        VirtualSessionEvidenceError,
        match="directory is not exact|escapes its record directory",
    ):
        verify_virtual_session_record(record.manifest_path)


def test_faulted_session_replays_the_same_fault(tmp_path: Path) -> None:
    trigger = VirtualFaultTrigger(
        "miss-first-a",
        VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
        "keyboard",
        "contact",
        occurrence=1,
        action_index=0,
        target_id="keyboard:A",
    )
    report = run_default_virtual_session(
        WORKSPACE,
        "keyboard",
        "a",
        fault_script=VirtualFaultScript("missed-contact", (trigger,)),
    )
    record = record_virtual_session(report, tmp_path)

    replay = replay_virtual_session(WORKSPACE, record.manifest_path)
    assert replay.identical is True
    assert replay.recomputed_status == "VIRTUAL_SESSION_FAULTED"


def test_observer_result_substitution_is_rejected_after_outer_rehash(
    tmp_path: Path,
    keyboard_report: VirtualSessionReport,
) -> None:
    record = record_virtual_session(keyboard_report, tmp_path)
    report_path = record.directory / "report.json"
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    report["outcome_observer"]["result_hashes"][0] = "0" * 64
    report_path.write_bytes(_canonical_bytes(report))
    rebound_manifest = _rebind_report_envelope_after_tamper(record.directory)

    with pytest.raises(
        VirtualSessionEvidenceError,
        match="device, observer, requested text, and outcome evidence differ",
    ):
        verify_virtual_session_record(rebound_manifest)


def test_nested_pose_substitution_is_rejected_after_all_outer_rehashes(
    tmp_path: Path,
) -> None:
    report = run_default_virtual_session(WORKSPACE, "keyboard", "a")
    record = record_virtual_session(report, tmp_path)
    vision_path = record.directory / "vision.json"
    vision: dict[str, Any] = json.loads(vision_path.read_text(encoding="utf-8"))
    result = vision["attempts"][0]["result"]
    result["pose_observation"]["detection_batch_sha256"] = "0" * 64
    vision_path.write_bytes(_canonical_bytes(vision))
    rebound_manifest = _rebind_vision_envelopes_after_nested_tamper(
        record.directory
    )

    with pytest.raises(
        VirtualSessionEvidenceError,
        match="pixel-vision artifact cannot be decoded",
    ):
        verify_virtual_session_record(rebound_manifest)


def test_schema_v2_pre_pixel_record_remains_byte_verifiable_history() -> None:
    verified = verify_virtual_session_record(LEGACY_PIXEL_PREDECESSOR)

    assert verified.report_hash == (
        "92ebfd731214e512276886b6fdb0eb98e37c8722cb59928650cda76abff65be4"
    )
    assert "vision.json" not in verified.documents
    assert verified.document("report.json")["schema"] == (
        "rocell.virtual_session_report.v2"
    )
