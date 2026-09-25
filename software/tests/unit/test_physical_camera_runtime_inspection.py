"""File-only native-runtime diagnostics: no helper, build, process or device."""

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_runtime_inspection as module
from rocell.providers.windows.native_camera_registration import (
    create_native_camera_runtime_registration,
)
from rocell.providers.windows.native_camera_capture_registration import (
    create_native_camera_capture_runtime_registration,
)

WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64
LAUNCH = "wizard-" + "1" * 32


def runtime_fixture(tmp_path, monkeypatch, *, probe_gap=True, mutate_manifest=None):
    """Closed production roster, tiny incapable file contents and test-only pins.

    The files are never executed. Only this isolated fixture replaces the private
    reviewed catalog/source checker; production callers have no such API.
    """
    workspace = tmp_path / "workspace"
    payloads = {}
    for relative in module.FIXED_PATHS:
        if relative.endswith("_manifest.json"):
            continue
        payloads[relative] = ("FILE-ONLY INCAPABLE FIXTURE: " + relative).encode(
            "ascii"
        )
    manifests, pins = {}, {}
    for purpose in ("probe", "capture"):
        original = WORKSPACE / module._PREFIX / module._RECORDS[purpose]
        document = json.loads(original.read_bytes())
        for relative in document["source_files"]:
            document["source_files"][relative] = hashlib.sha256(
                payloads[module._PREFIX + relative]
            ).hexdigest()
        if purpose == "probe" and probe_gap:
            document["source_files"]["camera_worker.cpp"] = hashlib.sha256(
                b"distinct historical fixture source"
            ).hexdigest()
        for artifact in document["artifacts"]:
            raw = payloads[module._PREFIX + artifact["path"]]
            artifact["sha256"] = hashlib.sha256(raw).hexdigest()
            artifact["length_bytes"] = len(raw)
        if mutate_manifest:
            mutate_manifest(purpose, document)
        manifests[purpose] = document
        raw = module._canonical(document)
        payloads[module._PREFIX + module._RECORDS[purpose]] = raw
        pins[purpose] = {
            "helper": hashlib.sha256(
                payloads[module._PREFIX + module._ARTIFACTS[purpose][0]]
            ).hexdigest(),
            "record": hashlib.sha256(raw).hexdigest(),
        }
    for relative, raw in payloads.items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    monkeypatch.setattr(module, "_PINS", pins)
    monkeypatch.setattr(module, "source_fingerprint", lambda path: SOURCE)
    common = {"source_sha256": SOURCE, "catalog_sha256": module._catalog_sha256()}
    probe = create_native_camera_runtime_registration(
        workspace,
        helper_sha256=pins["probe"]["helper"],
        build_record_sha256=pins["probe"]["record"],
        **common,
    )
    capture = create_native_camera_capture_runtime_registration(
        workspace,
        helper_sha256=pins["capture"]["helper"],
        build_record_sha256=pins["capture"]["record"],
        **common,
    )
    return SimpleNamespace(
        workspace=workspace,
        probe=probe,
        capture=capture,
        pins=pins,
        payloads=payloads,
        manifests=manifests,
    )


def inspect(fixture, **kwargs):
    arguments = dict(
        expected_source_sha256=SOURCE,
        launch_session_id=LAUNCH,
        operator_id="fixture-operator",
        probe_candidate=fixture.probe,
        capture_candidate=fixture.capture,
        cancellation=threading.Event(),
    )
    arguments.update(kwargs)
    return module.inspect_physical_camera_runtime_pair(fixture.workspace, **arguments)


def verify(fixture, value, **kwargs):
    raw = (
        value.payload
        if type(value) is module.PhysicalCameraRuntimeInspection
        else module._canonical(value)
    )
    arguments = dict(
        expected_source_sha256=SOURCE,
        expected_launch_session_id=LAUNCH,
        expected_probe_candidate=fixture.probe,
        expected_capture_candidate=fixture.capture,
        expected_report_sha256=hashlib.sha256(raw).hexdigest(),
    )
    arguments.update(kwargs)
    return module.verify_physical_camera_runtime_inspection(value, **arguments)


def assert_actual_historical_runtime_drift(report):
    """Exact installed-file regression, not new runtime registration pins.

    The driver-v2 identity and cleanup worker sources postdate both preserved
    builds. The capture CMake file also adds an incapable cleanup test target.
    Any additional gap or repinned historical artifact must fail this check.
    """
    prefix = "software/native/windows_camera/"
    files = {row["relative_path"]: row for row in report["files"]}
    assert set(files) == set(module.FIXED_PATHS)
    assert all(row["observation"] == "OBSERVED" for row in files.values())
    preserved = {
        "build-owned/Release/rocell_windows_camera.exe": "e6072f26efa335ada46ef1459a66830a687b2d66c7ff45584aa4ac949eb027a1",
        "owned_build_manifest.json": "705228b1595e1efeb2b8ceef171e3f6fdffad505b6e680b847cec352d712d7b6",
        "build-owned-capture/Release/rocell_windows_camera.exe": "31d2f2742b18c0935b3d7af07f8058f129421871be00860a3d7768e1e940ae2f",
        "owned_capture_build_manifest.json": "b6b60e92b1f95487be7c9230ddade77827b64a30063377b2f41a66d526eda2a5",
    }
    current_sources = {
        "camera_worker.cpp": "0bc84f21e99d1d72eb7bc4a4969945016c7593247e67bf586f14101f59e298be",
        "identity_metadata.cpp": "7c122cd638346a9a4761f504f3560f9d49c1baf7716d7321bdd1538c6e8f2cfd",
        "identity_metadata.h": "e4f39f7156f66b5fe2f2e8f812d9c1a6ab6e3e69d530aad59f50c4166545b3f0",
        "capture/CMakeLists.txt": "dd96798e4250eeff68ab1d27dc42dd2a62e70558e53ffef5a51aeeeee02cfb41",
    }
    for relative, expected in {**preserved, **current_sources}.items():
        assert files[prefix + relative]["observed_sha256"] == expected
    for purpose, source_count, artifact_count, gaps in (
        (
            "probe",
            10,
            3,
            ("camera_worker.cpp", "identity_metadata.cpp", "identity_metadata.h"),
        ),
        (
            "capture",
            15,
            4,
            (
                "camera_worker.cpp",
                "identity_metadata.cpp",
                "identity_metadata.h",
                "capture/CMakeLists.txt",
            ),
        ),
    ):
        row = report["purposes"][purpose]
        assert row["purpose"] == purpose
        assert row["source_status"] == "GAPS"
        assert row["source_counts"] == dict(
            total=source_count,
            matched=source_count - len(gaps),
            gaps=len(gaps),
            unverified=0,
        )
        assert row["gaps"] == [
            dict(relative_path=prefix + path, reason="HASH_MISMATCH") for path in gaps
        ]
        assert all(
            row[key] == "MATCHED"
            for key in ("binary_status", "build_status", "artifact_status")
        )
        assert row["artifact_counts"] == dict(
            total=artifact_count, matched=artifact_count, gaps=0, unverified=0
        )
        manifest = json.loads(
            base64.b64decode(report["manifests"][purpose], validate=True)
        )
        assert (
            manifest["source_files"]["identity_metadata.cpp"]
            == "b4459ca9f9d0d99ed58ed87b7ce8ac9f6f6ed37a37090cf7b13b768a58bf93bd"
        )
        assert (
            manifest["source_files"]["identity_metadata.h"]
            == "3cf6e8da5d18bdea4336d57a1e34ebb174373bfecf1efe22c19b8b29507cb06a"
        )
    assert report["coverage"] == dict(
        planned_paths=27, observed_paths=27, unobserved_paths=0
    )
    assert report["status"] == "HELD"
    assert report["effects"] == {
        "process_start_count": 0,
        "device_open_count": 0,
        "metadata_inventory_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
    }
    assert all(report[key] is False for key in module._FALSE_FIELDS)


def test_current_and_historical_file_claims_are_separate(tmp_path, monkeypatch):
    fixture = runtime_fixture(tmp_path, monkeypatch)
    result = inspect(fixture)
    report, summary = result.to_dict(), result.safe_summary()
    assert len(module.FIXED_PATHS) == 27
    assert summary["status"] == "HELD"
    assert summary["coverage"] == {
        "planned_paths": 27,
        "observed_paths": 27,
        "unobserved_paths": 0,
    }
    probe, capture = summary["purposes"]["probe"], summary["purposes"]["capture"]
    assert (
        probe["binary_status"]
        == probe["build_status"]
        == probe["artifact_status"]
        == "MATCHED"
    )
    assert probe["source_status"] == "GAPS" and probe["source_counts"] == {
        "total": 10,
        "matched": 9,
        "gaps": 1,
        "unverified": 0,
    }
    assert probe["gaps"] == [
        {
            "relative_path": module._PREFIX + "camera_worker.cpp",
            "reason": "HASH_MISMATCH",
        }
    ]
    assert all(
        capture[key] == "MATCHED"
        for key in ("binary_status", "build_status", "source_status", "artifact_status")
    )
    assert report["read_budget"]["native_bytes_read"] == sum(
        map(len, fixture.payloads.values())
    )
    assert report["read_budget"]["source_checks"] == 2
    assert all(report[field] is False for field in module._FALSE_FIELDS)
    assert set(report["effects"].values()) == {0}
    assert len(result.payload) < module.MAX_REPORT_BYTES
    assert verify(fixture, result).payload == result.payload
    assert verify(fixture, report).sha256 == result.sha256


def test_file_agreement_is_not_connection_authority_and_copies_are_owned(
    tmp_path, monkeypatch
):
    fixture = runtime_fixture(tmp_path, monkeypatch, probe_gap=False)
    result = inspect(fixture)
    assert result.safe_summary()["status"] == "FILES_MATCHED"
    snapshot = result.to_dict()
    snapshot["files"][0]["observed_sha256"] = "f" * 64
    summary = result.safe_summary()
    summary["purposes"]["capture"]["source_counts"]["matched"] = 0
    assert result.to_dict()["files"][0] != snapshot["files"][0]
    assert (
        result.safe_summary()["purposes"]["capture"]["source_counts"]["matched"] == 15
    )
    with pytest.raises((AttributeError, TypeError)):
        result.payload = b"changed"
    monkeypatch.setattr(
        module, "_read_fixed", lambda *a, **k: pytest.fail("Verifier read files")
    )
    monkeypatch.setattr(
        module, "source_fingerprint", lambda *a: pytest.fail("Verifier rehashed source")
    )
    assert verify(fixture, result).sha256 == result.sha256
    assert all(result.safe_summary()[field] is False for field in module._FALSE_FIELDS)


@pytest.mark.parametrize(
    "fault", ["missing", "hash", "unreadable", "unsafe", "oversize", "changed"]
)
def test_file_faults_are_observations_not_success_or_zero_bytes(
    tmp_path, monkeypatch, fault
):
    fixture = runtime_fixture(tmp_path, monkeypatch, probe_gap=False)
    relative = module._PREFIX + module._ARTIFACTS["capture"][0]
    path = fixture.workspace / relative
    expected = {
        "missing": "MISSING",
        "hash": "OBSERVED",
        "unreadable": "UNREADABLE",
        "unsafe": "UNSAFE_PATH",
        "oversize": "SIZE_LIMIT",
        "changed": "CHANGED_DURING_READ",
    }[fault]
    if fault == "missing":
        path.unlink()
    elif fault == "hash":
        path.write_bytes(b"not the pinned incapable bytes")
    else:
        original = module._read_fixed

        def reader(selected, *args, **kwargs):
            if selected == path:
                if fault == "unreadable":
                    raise PermissionError("modeled denial")
                raise module.PhysicalCameraRuntimeInspectionError(expected)
            return original(selected, *args, **kwargs)

        monkeypatch.setattr(module, "_read_fixed", reader)
    result = inspect(fixture)
    row = next(
        row for row in result.to_dict()["files"] if row["relative_path"] == relative
    )
    assert row["observation"] == expected
    if expected != "OBSERVED":
        assert row["observed_bytes"] is row["observed_sha256"] is None
    assert result.safe_summary()["status"] == "HELD"
    assert result.safe_summary()["purposes"]["capture"]["binary_status"] == (
        "HASH_MISMATCH" if fault == "hash" else "NOT_OBSERVED"
    )
    verify(fixture, result)


@pytest.mark.parametrize(
    "fault",
    [
        "extra-source",
        "missing-source",
        "duplicate-artifact",
        "artifact-path",
        "extra-key",
        "bool-duration",
    ],
)
def test_known_manifest_schema_and_membership_are_closed(tmp_path, monkeypatch, fault):
    def mutate(purpose, document):
        if purpose != "capture":
            return
        if fault == "extra-source":
            document["source_files"]["../unassigned.cpp"] = "f" * 64
        elif fault == "missing-source":
            document["source_files"].pop("camera_worker.cpp")
        elif fault == "duplicate-artifact":
            document["artifacts"][2] = deepcopy(document["artifacts"][1])
        elif fault == "artifact-path":
            document["artifacts"][1]["path"] = "../foreign.exe"
        elif fault == "extra-key":
            document["authorized"] = True
        else:
            document["admission_timeout_ms"] = True

    fixture = runtime_fixture(tmp_path, monkeypatch, mutate_manifest=mutate)
    result = inspect(fixture)
    purpose = result.safe_summary()["purposes"]["capture"]
    assert purpose["build_status"] == "MANIFEST_INVALID"
    assert purpose["source_status"] == purpose["artifact_status"] == "NOT_VERIFIED"
    assert purpose["source_counts"]["unverified"] == 15
    assert result.to_dict()["coverage"]["planned_paths"] == 27
    verify(fixture, result)


def test_unpinned_manifest_is_hashed_but_cannot_supply_expectations(
    tmp_path, monkeypatch
):
    fixture = runtime_fixture(tmp_path, monkeypatch)
    path = fixture.workspace / module._PREFIX / module._RECORDS["probe"]
    path.write_bytes(b'{"source_files":{"arbitrary.exe":"not authority"}}')
    result = inspect(fixture)
    assert result.to_dict()["manifests"]["probe"] is None
    assert result.safe_summary()["purposes"]["probe"]["build_status"] == "HASH_MISMATCH"
    assert result.safe_summary()["purposes"]["probe"]["source_status"] == "NOT_VERIFIED"


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-source",
        "wrong-launch",
        "wrong-operator",
        "swapped-purpose",
        "wrong-catalog",
    ],
)
def test_candidate_context_is_checked_before_any_reads(tmp_path, monkeypatch, fault):
    fixture = runtime_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        module,
        "source_fingerprint",
        lambda *a: pytest.fail("Rejected context read source"),
    )
    monkeypatch.setattr(
        module, "_read_fixed", lambda *a, **k: pytest.fail("Rejected context read file")
    )
    kwargs = {}
    if fault == "wrong-source":
        kwargs["expected_source_sha256"] = "b" * 64
    elif fault == "wrong-launch":
        kwargs["launch_session_id"] = "caller-path"
    elif fault == "wrong-operator":
        kwargs["operator_id"] = "bad operator\n"
    elif fault == "swapped-purpose":
        kwargs["probe_candidate"] = fixture.capture
    else:
        data = fixture.probe.to_dict()
        data["catalog_sha256"] = "f" * 64
        kwargs["probe_candidate"] = type(fixture.probe)(module._canonical(data))
    with pytest.raises(ValueError):
        inspect(fixture, **kwargs)


@pytest.mark.parametrize(
    "fault",
    ["before-stop", "late-stop", "source", "progress", "deadline", "read-budget"],
)
def test_abort_retains_bounded_partial_history_without_success(
    tmp_path, monkeypatch, fault
):
    fixture = runtime_fixture(tmp_path, monkeypatch)
    stop = threading.Event()
    now = [0]
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(monotonic_ns=lambda: now[0], time_ns=lambda: 100),
    )
    checks = [0]

    def fingerprint(path):
        checks[0] += 1
        return "b" * 64 if fault == "source" and checks[0] == 2 else SOURCE

    monkeypatch.setattr(module, "source_fingerprint", fingerprint)

    def progress(path):
        if fault == "late-stop":
            stop.set()
        elif fault == "progress":
            raise ValueError("private UI callback error")
        elif fault == "deadline":
            now[0] = 30_000_000_000

    if fault == "before-stop":
        stop.set()
    elif fault == "read-budget":
        monkeypatch.setattr(module, "MAX_NATIVE_BYTES", 1)
    expected = {
        "before-stop": "CANCELLED",
        "late-stop": "CANCELLED",
        "source": "SOURCE_CHANGED",
        "progress": "PROGRESS_FAILED",
        "deadline": "TIMED_OUT",
        "read-budget": "TOTAL_READ_LIMIT",
    }[fault]
    with pytest.raises(module.PhysicalCameraRuntimeInspectionError) as caught:
        inspect(fixture, cancellation=stop, progress=progress)
    assert caught.value.code == expected
    report = caught.value.inspection_report
    assert (
        report is not None
        and report["status"] == "HELD"
        and report["terminal_error"] == expected
    )
    assert report["read_budget"]["source_checks"] == (
        0 if fault == "before-stop" else 2 if fault == "source" else 1
    )
    verify(fixture, report)
    report["status"] = "changed"
    assert caught.value.inspection_report["status"] == "HELD"


def test_deadline_between_final_source_check_and_report_keeps_full_history(
    tmp_path, monkeypatch
):
    fixture = runtime_fixture(tmp_path, monkeypatch, probe_gap=False)
    source_checks, late_calls = [0], [0]

    def source(path):
        source_checks[0] += 1
        return SOURCE

    def monotonic():
        if source_checks[0] < 2:
            return 0
        late_calls[0] += 1
        return 29_999_999_999 if late_calls[0] == 1 else 30_000_000_001

    monkeypatch.setattr(module, "source_fingerprint", source)
    monkeypatch.setattr(
        module, "time", SimpleNamespace(monotonic_ns=monotonic, time_ns=lambda: 100)
    )
    with pytest.raises(module.PhysicalCameraRuntimeInspectionError) as caught:
        inspect(fixture)
    assert caught.value.code == "TIMED_OUT"
    report = caught.value.inspection_report
    assert report["coverage"]["observed_paths"] == 27
    assert report["terminal_error"] == "TIMED_OUT" and report["status"] == "HELD"
    verify(fixture, report)


@pytest.mark.parametrize(
    "fault",
    [
        "authority",
        "counter-bool",
        "zero-reads",
        "budget-bool",
        "source",
        "launch",
        "path",
        "count",
        "summary",
        "row-hash",
        "manifest-raw",
        "unknown-key",
    ],
)
def test_pure_verifier_rejects_tampered_rehashed_reports(tmp_path, monkeypatch, fault):
    fixture = runtime_fixture(tmp_path, monkeypatch)
    original = inspect(fixture)
    data = original.to_dict()
    if fault == "authority":
        data["physical_authority"] = True
    elif fault == "counter-bool":
        data["effects"]["process_start_count"] = False
    elif fault == "zero-reads":
        data["read_budget"]["native_read_calls"] = 0
    elif fault == "budget-bool":
        data["read_budget"]["native_bytes_read"] = True
    elif fault in {"source", "launch"}:
        data["binding"][
            "source_sha256" if fault == "source" else "launch_session_id"
        ] = ("f" * 64 if fault == "source" else "wizard-" + "2" * 32)
    elif fault == "path":
        data["files"][0]["relative_path"] = "../arbitrary.exe"
    elif fault == "count":
        data["coverage"]["observed_paths"] -= 1
    elif fault == "summary":
        data["status"] = "FILES_MATCHED"
    elif fault == "row-hash":
        data["files"][0]["observed_sha256"] = "f" * 64
    elif fault == "manifest-raw":
        data["manifests"]["probe"] = base64.b64encode(b"substitution").decode("ascii")
    else:
        data["new_field"] = False
    with pytest.raises(ValueError):
        verify(fixture, data)


def test_independently_held_report_hash_is_mandatory(tmp_path, monkeypatch):
    fixture = runtime_fixture(tmp_path, monkeypatch)
    result = inspect(fixture)
    with pytest.raises(module.PhysicalCameraRuntimeInspectionError):
        verify(fixture, result, expected_report_sha256="f" * 64)


def test_actual_fixed_installed_files_are_read_only_and_not_executed(monkeypatch):
    """Actual file baseline, modeled source to allow concurrent source edits."""
    import subprocess

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **kw: pytest.fail("File inspection must not launch any process"),
    )
    before = {
        path: hashlib.sha256((WORKSPACE / path).read_bytes()).hexdigest()
        for path in module.FIXED_PATHS
    }
    monkeypatch.setattr(module, "source_fingerprint", lambda path: SOURCE)
    common = {"source_sha256": SOURCE, "catalog_sha256": module._catalog_sha256()}
    probe = create_native_camera_runtime_registration(
        WORKSPACE,
        helper_sha256=module._PINS["probe"]["helper"],
        build_record_sha256=module._PINS["probe"]["record"],
        **common,
    )
    capture = create_native_camera_capture_runtime_registration(
        WORKSPACE,
        helper_sha256=module._PINS["capture"]["helper"],
        build_record_sha256=module._PINS["capture"]["record"],
        **common,
    )
    result = inspect(SimpleNamespace(workspace=WORKSPACE, probe=probe, capture=capture))
    assert_actual_historical_runtime_drift(result.to_dict())
    assert {
        path: hashlib.sha256((WORKSPACE / path).read_bytes()).hexdigest()
        for path in module.FIXED_PATHS
    } == before
    print(
        "Actual fixed-file inspection",
        result.sha256,
        len(result.payload),
        result.to_dict()["read_budget"],
    )
