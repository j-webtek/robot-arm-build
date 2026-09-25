"""Diagnostic-only runner/log tests; real subprocess checks are pure actions."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import threading

import pytest

from rocell.application import wizard_diagnostic_coordinator as coordinator
from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.application.wizard_diagnostic_log import (
    MAX_EVENT_BYTES,
    WizardDiagnosticLog,
)


WORKSPACE = Path(__file__).resolve().parents[3]
SESSION = "wizard-" + "a" * 32


def fixture_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "software/src/rocell/application").mkdir(parents=True)
    (root / "software/config").mkdir()
    (root / ".venv/Scripts").mkdir(parents=True)
    (root / ".venv/bin").mkdir()
    (root / "software/src/rocell/__init__.py").write_text("# incapable fixture\n")
    (root / "software/src/rocell/application/wizard_worker.py").write_text(
        "# never executed\n"
    )
    (root / "software/config/profile.json").write_text('{"fixture":true}')
    (root / "software/pyproject.toml").write_text('[project]\nname="fixture"\n')
    (root / "rocell.ps1").write_text("# fixture")
    (root / ".venv/Scripts/python.exe").write_bytes(b"INCAPABLE PLACEHOLDER")
    (root / ".venv/bin/python").write_bytes(b"INCAPABLE PLACEHOLDER")
    return root


def valid_result(action_id: str = "camera_profile") -> dict:
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": action_id,
        "status": "SUCCEEDED",
        "steps": [
            {"name": "camera_profile", "exit_code": 0, "report": {"fixture": True}}
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }


class FakeProcess:
    def __init__(
        self, stdout: bytes, stderr: bytes = b"", *, returncode: int | None = 0
    ):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.stdin = io.BytesIO()
        self.returncode = returncode
        self.pid = 123
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -1

    def wait(self, timeout=None):
        return self.returncode


def install_fake(
    monkeypatch, root: Path, result: dict | bytes, *, returncode=0, stderr=b""
):
    process = FakeProcess(
        json.dumps(result).encode() if isinstance(result, dict) else result,
        stderr,
        returncode=returncode,
    )
    calls = []

    def popen(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(coordinator.subprocess, "Popen", popen)
    runner = coordinator.DiagnosticProcessRunner(
        root, expected_source_sha256=coordinator.source_fingerprint(root)
    )
    return runner, process, calls


def invoke(runner, *, cancel=None, action_id="camera_profile", values=None):
    return runner.run(
        action_id,
        values or {},
        cell_id="CELL-A",
        cancel=cancel or threading.Event(),
        progress=lambda message: None,
    )


def test_constructor_and_pre_cancel_are_inert(tmp_path: Path, monkeypatch):
    root = tmp_path / "missing-workspace"
    runner = coordinator.DiagnosticProcessRunner(root, expected_source_sha256="a" * 64)
    monkeypatch.setattr(
        coordinator.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("unexpected process"),
    )
    cancel = threading.Event()
    cancel.set()
    result = invoke(runner, cancel=cancel)
    assert result["status"] == "CANCELLED"


def test_cancellation_during_source_validation_prevents_dispatch(
    tmp_path: Path, monkeypatch
):
    root = fixture_workspace(tmp_path)
    runner, _, calls = install_fake(monkeypatch, root, valid_result())
    cancel = threading.Event()
    expected = runner.expected_source_sha256

    def cancel_during_hash(workspace):
        cancel.set()
        return expected

    monkeypatch.setattr(coordinator, "source_fingerprint", cancel_during_hash)
    result = invoke(runner, cancel=cancel)
    assert result["status"] == "CANCELLED"
    assert calls == []


@pytest.mark.parametrize(
    "action_id",
    [
        "camera_connect",
        "arm_connect",
        "execute_task",
        "export_logs",
        "record_note",
        "stop_operation",
        "arbitrary.module:run",
    ],
)
def test_registry_cannot_dispatch_physical_or_arbitrary_workers(
    tmp_path: Path, monkeypatch, action_id: str
):
    root = fixture_workspace(tmp_path)
    runner, _, calls = install_fake(monkeypatch, root, valid_result())
    with pytest.raises(WizardError) as error:
        invoke(runner, action_id=action_id)
    assert error.value.code == "WORKER_NOT_REGISTERED"
    assert calls == []


def test_source_change_blocks_without_worker(tmp_path: Path, monkeypatch):
    root = fixture_workspace(tmp_path)
    runner, _, calls = install_fake(monkeypatch, root, valid_result())
    (root / "software/src/rocell/application/wizard_worker.py").write_text(
        "# substituted worker"
    )
    with pytest.raises(WizardError) as error:
        invoke(runner)
    assert error.value.code == "SOURCE_CHANGED"
    assert calls == []


def test_source_binding_excludes_logs_but_includes_ui_and_config(tmp_path: Path):
    root = fixture_workspace(tmp_path)
    baseline = coordinator.source_fingerprint(root)
    (root / "software/runs").mkdir()
    (root / "software/runs/log.json").write_text("not a source")
    assert coordinator.source_fingerprint(root) == baseline
    (root / "software/src/rocell/page.html").write_text("<p>new UI</p>")
    assert coordinator.source_fingerprint(root) != baseline


def test_native_process_is_fixed_and_python_environment_isolated(
    tmp_path: Path, monkeypatch
):
    root = fixture_workspace(tmp_path)
    monkeypatch.setenv("PYTHONPATH", "untrusted-module-path")
    monkeypatch.setenv("PYTHONHOME", "untrusted-runtime")
    runner, _, calls = install_fake(monkeypatch, root, valid_result())
    result = invoke(runner)
    assert result["status"] == "SUCCEEDED"
    args, kwargs = calls[0]
    argv = args[0]
    assert argv[1:4] == ["-I", "-B", "-c"]
    assert "find_spec('rocell')" in argv[4]
    assert "wizard_worker import main" in argv[4]
    assert argv[-2] == str(root)
    assert argv[-1] == runner.expected_source_sha256
    assert "source_fingerprint(expected)!=expected_source" in argv[4]
    assert "PYTHONPATH" not in kwargs["env"] and "PYTHONHOME" not in kwargs["env"]
    assert kwargs.get("shell", False) is False
    assert result["physical_authority"] is False


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema":1,"schema":2}',
        b'{"schema":NaN}',
        b"null",
        b"[]",
        b'"unexpected"',
        b"\xff",
        b'{"schema":"wrong"}',
    ],
)
def test_worker_bad_json_is_a_typed_failure(
    tmp_path: Path, monkeypatch, payload: bytes
):
    root = fixture_workspace(tmp_path)
    runner, _, calls = install_fake(monkeypatch, root, payload)
    with pytest.raises(WizardError) as error:
        invoke(runner)
    assert error.value.code == "INVALID_WORKER_RESULT"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(action_id="arm_connect"),
        lambda d: d.update(extra="unregistered output"),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(device_open_count=1),
        lambda d: d.update(serial_write_count=True),
        lambda d: d.update(metadata_inventory_performed=True),
        lambda d: d.update(status="BOGUS"),
        lambda d: d.update(steps=[]),
        lambda d: d["steps"][0].update(exit_code=1),
        lambda d: d["steps"][0]["report"].update(value=float("nan")),
        lambda d: d["steps"][0]["report"].update(value=float("inf")),
    ],
)
def test_worker_results_bind_action_zero_effects_and_status(
    tmp_path: Path, monkeypatch, mutate
):
    root = fixture_workspace(tmp_path)
    result = valid_result()
    mutate(result)
    runner, _, calls = install_fake(monkeypatch, root, result)
    with pytest.raises(WizardError):
        invoke(runner)
    assert len(calls) == 1


def test_duplicate_json_keys_cannot_hide_valid_result(tmp_path: Path, monkeypatch):
    root = fixture_workspace(tmp_path)
    raw = json.dumps(valid_result()).encode()
    raw = raw[:-1] + b',"action_id":"camera_profile"}'
    runner, _, _ = install_fake(monkeypatch, root, raw)
    with pytest.raises(WizardError) as error:
        invoke(runner)
    assert error.value.code == "INVALID_WORKER_RESULT"


def test_registered_error_result_is_retained_without_motion_claim(
    tmp_path: Path, monkeypatch
):
    root = fixture_workspace(tmp_path)
    error = {
        "schema": "rocell.wizard_worker_error.v1",
        "status": "FAILED",
        "code": "DIAGNOSTIC_WORKER_FAILED",
        "message": "fixture failure",
        "error_type": "ValueError",
        "physical_authority": False,
    }
    runner, _, _ = install_fake(monkeypatch, root, error, returncode=1)
    result = invoke(runner)
    assert result["status"] == "FAILED" and result["message"] == "fixture failure"
    assert result["physical_authority"] is False
    assert "robot_stopped" not in result


def test_pipe_budget_excess_fails_without_retry(tmp_path: Path, monkeypatch):
    root = fixture_workspace(tmp_path)
    runner, _, calls = install_fake(
        monkeypatch, root, b"x" * (coordinator.MAX_STDOUT + 1)
    )
    result = invoke(runner)
    assert result["status"] == "FAILED" and result["output_limit_exceeded"]
    assert result["physical_authority"] is False and len(calls) == 1


def test_worker_timeout_requests_cleanup_not_robot_stop(tmp_path: Path, monkeypatch):
    root = fixture_workspace(tmp_path)
    runner, process, calls = install_fake(
        monkeypatch, root, valid_result(), returncode=None
    )
    monkeypatch.setitem(
        ACTION_BY_ID,
        "camera_profile",
        replace(ACTION_BY_ID["camera_profile"], timeout_s=0),
    )
    monkeypatch.setattr(runner, "_stop", lambda child: child.kill())
    result = invoke(runner)
    assert result["status"] == "TIMED_OUT" and process.killed
    assert result["physical_authority"] is False and len(calls) == 1


@pytest.mark.parametrize("uncertain_cleanup", [False, True])
def test_native_arm_metadata_stall_is_contained_without_retry(
    tmp_path: Path, monkeypatch, uncertain_cleanup: bool
):
    """An incapable child models an OS metadata call that never returns."""
    root = fixture_workspace(tmp_path)
    action_id = "inspect_native_arm_metadata"
    result = valid_result(action_id)
    result["metadata_inventory_performed"] = True
    runner, process, calls = install_fake(monkeypatch, root, result, returncode=None)
    monkeypatch.setitem(
        ACTION_BY_ID, action_id, replace(ACTION_BY_ID[action_id], timeout_s=0)
    )

    def stop(child):
        child.kill()
        if uncertain_cleanup:
            raise OSError("incapable cleanup observation unavailable")

    monkeypatch.setattr(runner, "_stop", stop)
    values = {"power_disconnected": True, "metadata_only": True}
    if uncertain_cleanup:
        with pytest.raises(WizardError) as error:
            invoke(runner, action_id=action_id, values=values)
        assert error.value.code == "DIAGNOSTIC_CLEANUP_UNCERTAIN"
    else:
        observed = invoke(runner, action_id=action_id, values=values)
        assert observed["status"] == "TIMED_OUT"
        assert observed["physical_authority"] is False
    assert process.killed and len(calls) == 1


def test_cleanup_failure_is_not_reported_success(tmp_path: Path, monkeypatch):
    root = fixture_workspace(tmp_path)
    runner, _, _ = install_fake(monkeypatch, root, valid_result(), returncode=None)
    monkeypatch.setitem(
        ACTION_BY_ID,
        "camera_profile",
        replace(ACTION_BY_ID["camera_profile"], timeout_s=0),
    )

    def failed_stop(child):
        raise OSError("fixture cleanup failure")

    monkeypatch.setattr(runner, "_stop", failed_stop)
    with pytest.raises(WizardError) as error:
        invoke(runner)
    assert error.value.code == "DIAGNOSTIC_CLEANUP_UNCERTAIN"


def test_broken_output_pipe_is_reported_and_child_is_cleaned(
    tmp_path: Path, monkeypatch
):
    root = fixture_workspace(tmp_path)
    runner, process, _ = install_fake(
        monkeypatch, root, valid_result(), returncode=None
    )

    class BrokenRead(io.BytesIO):
        def read(self, size=-1):
            raise OSError("fixture pipe failure")

    process.stdout = BrokenRead()
    monkeypatch.setattr(runner, "_stop", lambda child: child.kill())
    with pytest.raises(WizardError) as error:
        invoke(runner)
    assert error.value.code == "DIAGNOSTIC_PIPE_FAILED"
    assert process.killed


def test_full_stdin_pipe_remains_supervised_by_deadline(tmp_path: Path, monkeypatch):
    root = fixture_workspace(tmp_path)
    runner, process, _ = install_fake(
        monkeypatch, root, valid_result(), returncode=None
    )
    released = threading.Event()

    class BlockingInput(io.BytesIO):
        def write(self, payload):
            assert released.wait(3), "writer was not released by bounded cleanup"
            return super().write(payload)

    process.stdin = BlockingInput()
    monkeypatch.setitem(
        ACTION_BY_ID,
        "camera_profile",
        replace(ACTION_BY_ID["camera_profile"], timeout_s=0),
    )

    def stop(child):
        child.kill()
        released.set()

    monkeypatch.setattr(runner, "_stop", stop)
    result = invoke(runner)
    assert result["status"] == "TIMED_OUT"
    assert result["schema"] == "rocell.wizard_diagnostic_completion.v1"
    assert process.killed and released.is_set()


@pytest.mark.skipif(os.name != "nt", reason="Windows process-tree cleanup branch")
def test_taskkill_failure_still_terminates_owned_root_child(monkeypatch):
    process = FakeProcess(b"", returncode=None)

    def fail_taskkill(*args, **kwargs):
        raise OSError("fixture tree cleanup failed")

    monkeypatch.setattr(coordinator.subprocess, "run", fail_taskkill)
    with pytest.raises(RuntimeError, match="process-tree cleanup"):
        coordinator.DiagnosticProcessRunner._stop(process)
    assert process.killed


def test_source_actual_read_length_detects_concurrent_growth(
    tmp_path: Path, monkeypatch
):
    root = fixture_workspace(tmp_path)
    target = root / "software/src/rocell/application/wizard_worker.py"
    original = Path.stat

    def shortened_stat(path, *args, **kwargs):
        actual = original(path, *args, **kwargs)
        if path == target:
            from types import SimpleNamespace
            return SimpleNamespace(st_mode=actual.st_mode, st_size=1,
                st_file_attributes=getattr(actual, 'st_file_attributes', 0))
        return actual

    monkeypatch.setattr(Path, "stat", shortened_stat)
    with pytest.raises(WizardError) as error:
        coordinator.source_fingerprint(root)
    assert error.value.code == "SOURCE_CHANGED"


@pytest.mark.parametrize(
    "action_id,values",
    [("camera_profile", {}), ("plan_task", {"device": "keyboard", "text": "hi"})],
)
def test_actual_registered_pure_worker_subprocess(action_id: str, values: dict):
    # The only real subprocess actions in this test module. Neither enumerates
    # devices, activates hardware, writes operational logs or runs pytest again.
    runner = coordinator.DiagnosticProcessRunner(
        WORKSPACE, expected_source_sha256=coordinator.source_fingerprint(WORKSPACE)
    )
    result = invoke(runner, action_id=action_id, values=values)
    assert result["schema"] == "rocell.wizard_worker_result.v1"
    assert result["action_id"] == action_id and result["status"] == "SUCCEEDED"
    assert result["worker_exit_code"] == 0
    assert result["physical_authority"] is False
    for key in (
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ):
        assert result[key] == 0


def log(tmp_path: Path) -> WizardDiagnosticLog:
    return WizardDiagnosticLog(
        tmp_path / "logs", SESSION, source_sha256="b" * 64, mode="rehearsal"
    )


def test_log_constructor_inert_and_hashchain_verifies(tmp_path: Path):
    value = log(tmp_path)
    assert not value.root.exists()
    first = value.append("started", {"fixture": True})
    second = value.append("finished", {"result": "SYNTHETIC"})
    assert first["previous_sha256"] == "0" * 64
    assert second["previous_sha256"] == first["sha256"]
    verified = value.verify(value.directory)
    assert verified["events"] == value.events()
    assert verified["status"] == "VERIFIED_DIAGNOSTIC_ONLY"
    assert (
        verified["physical_authority"] is False and verified["replay_allowed"] is False
    )


def test_log_detaches_nested_caller_and_returned_mutations(tmp_path: Path):
    value = log(tmp_path)
    details = {"report": {"list": ["initial"]}}
    returned = value.append("observation", details)
    details["report"]["list"].append("caller-mutation")
    returned["details"]["report"]["list"].append("return-mutation")
    assert value.events() == value.verify(value.directory)["events"]


def test_existing_log_namespace_is_never_overwritten(tmp_path: Path):
    first = log(tmp_path)
    first.append("start", {})
    previous = (first.directory / "event-00000000.json").read_bytes()
    second = log(tmp_path)
    with pytest.raises((FileExistsError, WizardError)):
        second.append("overwrite", {})
    assert (first.directory / "event-00000000.json").read_bytes() == previous


def test_event_quota_rejects_before_creating_log(tmp_path: Path):
    value = log(tmp_path)
    with pytest.raises(WizardError) as error:
        value.append("too-large", {"payload": ["x" * 20_000 for _ in range(8)]})
    assert error.value.code == "LOG_EVENT_LIMIT"
    assert not value.root.exists()


@pytest.mark.parametrize(
    "fault",
    ["tamper", "truncated", "extra_entry", "missing_first", "oversized", "root_null"],
)
def test_invalid_log_is_typed_failure_not_repaired(tmp_path: Path, fault: str):
    value = log(tmp_path)
    value.append("start", {})
    value.append("finish", {})
    first = value.directory / "event-00000000.json"
    if fault == "tamper":
        first.write_bytes(first.read_bytes().replace(b'"start"', b'"other"'))
    elif fault == "truncated":
        first.write_bytes(first.read_bytes()[:25])
    elif fault == "extra_entry":
        (value.directory / "unregistered.txt").write_text("preserve")
    elif fault == "missing_first":
        first.rename(value.directory / "preserved-first.json")
    elif fault == "oversized":
        first.write_bytes(b"x" * (MAX_EVENT_BYTES + 1))
    else:
        first.write_bytes(b"null")
    before = {p.name: p.read_bytes() for p in value.directory.iterdir()}
    with pytest.raises(WizardError) as error:
        value.verify(value.directory)
    assert error.value.code == "INVALID_LOG"
    assert before == {p.name: p.read_bytes() for p in value.directory.iterdir()}


def rewrite_canonical_event(path: Path, mutate) -> None:
    item = json.loads(path.read_bytes())
    item.pop("sha256")
    mutate(item)
    encode = lambda data: json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()
    item["sha256"] = hashlib.sha256(encode(item)).hexdigest()
    path.write_bytes(encode(item))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(sequence=False),
        lambda d: d.update(extra="unknown"),
        lambda d: d.update(created_at_ns=-1),
        lambda d: d.update(source_sha256="not-a-hash"),
        lambda d: d.update(details=[]),
        lambda d: d.update(mode="live-authorized"),
    ],
)
def test_log_schema_remains_strict_even_with_self_consistent_hash(
    tmp_path: Path, mutate
):
    value = log(tmp_path)
    value.append("start", {})
    rewrite_canonical_event(value.directory / "event-00000000.json", mutate)
    with pytest.raises(WizardError) as error:
        value.verify(value.directory)
    assert error.value.code == "INVALID_LOG"


def test_reparse_or_symlink_log_is_refused(tmp_path: Path):
    value = log(tmp_path)
    value.append("start", {})
    target = tmp_path / "link-log"
    try:
        target.symlink_to(value.directory, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not grant creation of a temporary directory symlink")
    with pytest.raises(WizardError) as error:
        value.verify(target)
    assert error.value.code == "UNSAFE_PATH"
