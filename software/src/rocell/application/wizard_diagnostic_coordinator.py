"""Bounded subprocess runner for non-actuating wizard diagnostics only.

This is NOT the M2 physical effect coordinator and cannot dispatch native
camera/serial workers. It runs exactly the checked-in diagnostic worker with
bounded semantic input. Process cancellation means diagnostic cancellation,
not a certified stop of a robot or proof of actuator power state.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import threading
import time
from typing import Any, Callable

from .wizard_actions import ACTION_BY_ID, WizardError, validate_action_input

MAX_STDOUT = 4 * 1024 * 1024
MAX_STDERR = 128 * 1024


def decode_diagnostic_json(payload: bytes, *, maximum: int) -> Any:
    """Decode bounded UTF-8 JSON without duplicate fields or nonfinite values."""
    if len(payload) > maximum:
        raise ValueError("JSON byte budget exceeded")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def finite(text: str) -> float:
        number = float(text)
        if not math.isfinite(number):
            raise ValueError("Nonfinite JSON value")
        return number

    def bounded_integer(text: str) -> int:
        if len(text) > 32:
            raise ValueError("JSON integer exceeds diagnostic budget")
        return int(text)

    def reject_constant(text: str) -> None:
        raise ValueError("Nonfinite JSON constant")

    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=unique,
        parse_float=finite,
        parse_int=bounded_integer,
        parse_constant=reject_constant,
    )


def validate_diagnostic_worker_result(
    result: Any, *, action_id: str, returncode: int
) -> dict[str, Any]:
    """A diagnostic cannot change its action, effect counts or result schema."""
    action = ACTION_BY_ID.get(action_id)
    if (
        action is None
        or action.hold
        or action.worker in {"unavailable", "export", "note", "stop"}
    ):
        raise WizardError(
            "WORKER_NOT_REGISTERED",
            "Result action has no registered diagnostic worker.",
        )
    if type(returncode) is not int:
        raise WizardError(
            "INVALID_WORKER_RESULT", "Worker exit code must be an integer."
        )
    if type(result) is not dict:
        raise WizardError("INVALID_WORKER_RESULT", "Worker result must be an object.")
    if result.get("schema") not in {
        "rocell.wizard_worker_result.v1",
        "rocell.wizard_worker_error.v1",
    }:
        raise WizardError(
            "INVALID_WORKER_RESULT", "Worker result schema is not registered."
        )
    if result.get("physical_authority") is not False:
        raise WizardError(
            "WORKER_AUTHORITY_VIOLATION",
            "Diagnostic worker claimed physical authority.",
        )
    effects = {
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    }
    for key in effects & result.keys():
        if type(result[key]) is not int or result[key] != 0:
            raise WizardError(
                "WORKER_AUTHORITY_VIOLATION",
                "Diagnostic worker reported unexpected device effects.",
            )
    schema = result.get("schema")
    if schema == "rocell.wizard_worker_error.v1":
        required = {
            "schema",
            "status",
            "code",
            "message",
            "error_type",
            "physical_authority",
        }
        optional = effects | {"metadata_inventory_performed"}
        if not required <= result.keys() or result.keys() - required - optional:
            raise WizardError(
                "INVALID_WORKER_RESULT", "Worker error fields are not registered."
            )
        if (
            result["status"] != "FAILED"
            or returncode == 0
            or result.get("metadata_inventory_performed", False) is not False
        ):
            raise WizardError(
                "INVALID_WORKER_RESULT",
                "Worker error status disagrees with its exit or effects.",
            )
        for key in ("code", "message", "error_type"):
            if (
                type(result[key]) is not str
                or not result[key]
                or len(result[key]) > 2000
            ):
                raise WizardError(
                    "INVALID_WORKER_RESULT", "Worker error text is invalid."
                )
        return result
    required = effects | {
        "schema",
        "action_id",
        "status",
        "steps",
        "metadata_inventory_performed",
        "physical_authority",
    }
    if schema != "rocell.wizard_worker_result.v1" or result.keys() != required:
        raise WizardError(
            "INVALID_WORKER_RESULT", "Worker result fields are not registered."
        )
    if result["action_id"] != action_id or returncode != 0:
        raise WizardError(
            "INVALID_WORKER_RESULT",
            "Worker action or exit does not match its dispatch.",
        )
    metadata_flag = result["metadata_inventory_performed"]
    # Native metadata is a service-owned action with either an incapable fixture
    # or a separately registered Windows provider. Its packet validator binds
    # that provenance before result publication; review itself does no query.
    native_metadata = action.worker == "native_camera_metadata"
    if (
        type(metadata_flag) is not bool
        or (
            not native_metadata
            and metadata_flag
            is not (action.worker in {"inventory", "native_arm_metadata"})
        )
        or (action_id == "native_camera_review" and metadata_flag is not False)
    ):
        raise WizardError(
            "INVALID_WORKER_RESULT", "Worker metadata effects disagree with its action."
        )
    steps = result["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= 16:
        raise WizardError(
            "INVALID_WORKER_RESULT", "Worker steps exceed the registered result budget."
        )
    for step in steps:
        if (
            type(step) is not dict
            or not {"name", "exit_code", "report"} <= step.keys()
            or step.keys() - {"name", "exit_code", "report", "stderr"}
        ):
            raise WizardError("INVALID_WORKER_RESULT", "Worker step schema is invalid.")
        if (
            type(step["name"]) is not str
            or not 1 <= len(step["name"]) <= 96
            or type(step["exit_code"]) is not int
            or type(step["report"]) is not dict
        ):
            raise WizardError(
                "INVALID_WORKER_RESULT", "Worker step values are invalid."
            )
        if "stderr" in step and type(step["stderr"]) is not str:
            raise WizardError(
                "INVALID_WORKER_RESULT", "Worker step stderr must be text."
            )
    expected_status = (
        "SUCCEEDED" if all(step["exit_code"] == 0 for step in steps) else "FAILED"
    )
    if result["status"] != expected_status:
        raise WizardError(
            "INVALID_WORKER_RESULT",
            "Worker status disagrees with its diagnostic steps.",
        )
    return result


def _diagnostic_completion(
    action_id: str,
    status: str,
    message: str,
    *,
    elapsed_s: float = 0.0,
    output_limit_exceeded: bool = False,
) -> dict[str, Any]:
    """Local runner cessation is a separate schema, never a worker/hardware receipt."""
    return {
        "schema": "rocell.wizard_diagnostic_completion.v1",
        "action_id": action_id,
        "status": status,
        "message": message,
        "elapsed_s": elapsed_s,
        "output_limit_exceeded": output_limit_exceeded,
        "physical_authority": False,
    }


def _regular_path_info(path: Path, *, directory: bool):
    """Validate every ancestor and reuse this call's leaf metadata, not a cache."""
    path = Path(os.path.abspath(path))
    leaf_info = None
    for component in (path, *path.parents):
        info = component.lstat()
        if component == path:
            leaf_info = info
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise WizardError(
                "UNSAFE_PATH", "Links and reparse points are not supported here."
            )
    if not (stat.S_ISDIR(leaf_info.st_mode) if directory else stat.S_ISREG(leaf_info.st_mode)):
        raise WizardError("INVALID_PATH", "Expected a regular file or directory.")
    return path, leaf_info


def require_regular_path(path: Path, *, directory: bool) -> Path:
    """Reject unresolved links/reparse ancestors before trusting a local path."""
    return _regular_path_info(path, directory=directory)[0]


def source_fingerprint(workspace: Path) -> str:
    """Bind code/configuration, excluding runs, caches and user export data.

    Rechecked at action admission. Pure status reads reuse the cached binding;
    this is diagnostic provenance, not an off-machine rollback anchor.
    """
    root = require_regular_path(workspace, directory=True)
    files = [root / "software/pyproject.toml", root / "rocell.ps1"]
    for relative, suffixes in (
        ("software/src/rocell", {".py", ".html", ".css", ".js"}),
        ("software/config", {".json"}),
    ):
        for current, directories, names in os.walk(root / relative, followlinks=False):
            directories[:] = sorted(
                name for name in directories if name != "__pycache__"
            )
            for name in sorted(names):
                path = Path(current) / name
                if path.suffix in suffixes:
                    files.append(path)
    if len(files) > 4096:
        raise WizardError("SOURCE_LIMIT", "Source inventory exceeded its fixed budget.")
    digest = hashlib.sha256()
    total = 0
    for path in sorted(files):
        checked, info = _regular_path_info(path, directory=False)
        size = info.st_size
        if size > 8 * 1024 * 1024 or total + size > 128 * 1024 * 1024:
            raise WizardError("SOURCE_LIMIT", "Source file budget exceeded.")
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        with checked.open("rb") as stream:
            observed_size = 0
            while chunk := stream.read(128 * 1024):
                observed_size += len(chunk)
                total += len(chunk)
                if observed_size > 8 * 1024 * 1024 or total > 128 * 1024 * 1024:
                    raise WizardError(
                        "SOURCE_LIMIT", "Source changed or grew beyond its read budget."
                    )
                digest.update(chunk)
            if observed_size != size:
                raise WizardError(
                    "SOURCE_CHANGED",
                    "Source changed while its fingerprint was being read.",
                )
        digest.update(b"\0")
    return digest.hexdigest()


class DiagnosticProcessRunner:
    """Constructor is inert; run invokes only our known no-actuation worker."""

    def __init__(self, workspace: Path, *, expected_source_sha256: str) -> None:
        self.workspace = Path(workspace)
        self.expected_source_sha256 = expected_source_sha256

    @staticmethod
    def _stop(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        tree_error: Exception | None = None
        if os.name == "nt":
            # PID belongs to this live child; fixed taskkill argv scopes cleanup
            # to its tree. No shell, task name or arbitrary process selector.
            try:
                result = subprocess.run(
                    [
                        str(
                            Path(os.environ.get("SystemRoot", r"C:\Windows"))
                            / "System32/taskkill.exe"
                        ),
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                if result.returncode != 0:
                    tree_error = RuntimeError(
                        "Diagnostic process-tree cleanup returned a failure."
                    )
            except Exception as exc:
                tree_error = exc
        else:
            import signal

            try:
                # Windows-host type checkers omit these Unix-only definitions.
                getattr(os, "killpg")(process.pid, getattr(signal, "SIGKILL"))
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        if tree_error is not None:
            # Root-child termination is still attempted, but cannot erase
            # uncertainty about descendants when process-tree cleanup failed.
            raise RuntimeError(
                "Diagnostic process-tree cleanup was not confirmed."
            ) from tree_error

    def run(
        self,
        action_id: str,
        values: dict[str, Any],
        *,
        cell_id: str,
        cancel: threading.Event,
        progress: Callable[[str], None],
        deadline_monotonic_ns: int | None = None,
    ) -> dict[str, Any]:
        if deadline_monotonic_ns is not None and (
            type(deadline_monotonic_ns) is not int or not 0 < deadline_monotonic_ns < 2**63
        ):
            raise ValueError('Bounded original diagnostic deadline required')
        def deadline_expired() -> bool:
            return deadline_monotonic_ns is not None and time.monotonic_ns() >= deadline_monotonic_ns
        action = ACTION_BY_ID.get(action_id)
        if (
            action is None
            or action.hold
            or action.worker in {"unavailable", "export", "note", "stop"}
        ):
            raise WizardError(
                "WORKER_NOT_REGISTERED",
                "Only closed diagnostic actions are registered.",
            )
        values = validate_action_input(action, values)
        if deadline_expired():
            return _diagnostic_completion(action_id,'TIMED_OUT','Original diagnostic deadline expired before dispatch.')
        if cancel.is_set():
            return _diagnostic_completion(
                action_id, "CANCELLED", "Cancelled before diagnostic dispatch."
            )
        if source_fingerprint(self.workspace) != self.expected_source_sha256:
            raise WizardError(
                "SOURCE_CHANGED",
                "Source changed after startup. Export diagnostics and restart explicitly.",
            )
        executable = require_regular_path(
            (
                self.workspace / ".venv/Scripts/python.exe"
                if os.name == "nt"
                else self.workspace / ".venv/bin/python"
            ),
            directory=False,
        )
        bootstrap = (
            "import importlib.util,json,pathlib,sys\n"
            "expected=pathlib.Path(sys.argv.pop(1)).resolve()\n"
            "expected_source=sys.argv.pop(1)\n"
            "spec=importlib.util.find_spec('rocell')\n"
            "assert spec is not None and pathlib.Path(spec.origin).resolve()==expected/'software/src/rocell/__init__.py'\n"
            "from rocell.application.wizard_diagnostic_coordinator import source_fingerprint\n"
            "if source_fingerprint(expected)!=expected_source:\n"
            " sys.stdout.write(json.dumps({'schema':'rocell.wizard_worker_error.v1','status':'FAILED','code':'SOURCE_CHANGED','message':'Source changed before diagnostic worker import. Restart after review.','error_type':'SourceBindingError','physical_authority':False}))\n"
            " raise SystemExit(1)\n"
            "from rocell.application.wizard_worker import main\n"
            "raise SystemExit(main())\n"
        )
        request = json.dumps(
            {
                "workspace": str(self.workspace),
                "action_id": action_id,
                "input": values,
                "cell_id": cell_id,
            },
            allow_nan=False,
        ).encode("utf-8")
        if len(request) > 16 * 1024:
            raise WizardError("REQUEST_TOO_LARGE", "Diagnostic request exceeds budget.")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Cancellation may arrive during source/path validation. Do not dispatch
        # a fresh worker after the operator has already requested cessation.
        if cancel.is_set():
            return _diagnostic_completion(
                action_id, "CANCELLED", "Cancelled before diagnostic dispatch."
            )
        if deadline_expired():
            return _diagnostic_completion(action_id,'TIMED_OUT','Original diagnostic deadline expired during preparation.')
        process = subprocess.Popen(
            [
                str(executable),
                "-I",
                "-B",
                "-c",
                bootstrap,
                str(self.workspace),
                self.expected_source_sha256,
            ],
            cwd=self.workspace,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            start_new_session=os.name != "nt",
        )
        started = time.monotonic()
        stdout = bytearray()
        stderr = bytearray()
        excessive = threading.Event()
        pipe_failed = threading.Event()

        def drain(stream: Any, target: bytearray, maximum: int) -> None:
            try:
                while chunk := stream.read(4096):
                    if len(target) + len(chunk) > maximum:
                        excessive.set()
                        return
                    target.extend(chunk)
            except Exception:
                pipe_failed.set()
            finally:
                try:
                    stream.close()
                except Exception:
                    pipe_failed.set()

        readers = [
            threading.Thread(
                target=drain, args=(process.stdout, stdout, MAX_STDOUT), daemon=True
            ),
            threading.Thread(
                target=drain, args=(process.stderr, stderr, MAX_STDERR), daemon=True
            ),
        ]

        def feed() -> None:
            try:
                assert process.stdin is not None
                if process.stdin.write(request) != len(request):
                    pipe_failed.set()
            except Exception:
                pipe_failed.set()
            finally:
                try:
                    if process.stdin is not None:
                        process.stdin.close()
                except Exception:
                    pipe_failed.set()

        # A worker that never reads stdin must not block the caller outside its
        # timeout/cancellation loop, even with a full anonymous pipe.
        feeders = [*readers, threading.Thread(target=feed, daemon=True)]
        for pipe_worker in feeders:
            pipe_worker.start()
        outcome: str | None = None
        cleanup_error: str | None = None
        dispatch_error: Exception | None = None
        try:
            progress(
                "Running registered diagnostic worker; physical device opens are not available."
            )
            while process.poll() is None:
                if cancel.is_set():
                    outcome = "CANCELLED"
                    break
                if excessive.is_set():
                    outcome = "FAILED"
                    break
                if pipe_failed.is_set():
                    outcome = "FAILED"
                    break
                if time.monotonic() - started > action.timeout_s or deadline_expired():
                    outcome = "TIMED_OUT"
                    break
                # Endpoint metadata has a separate 100 ms snapshot-age gate.
                # Tighten only explicitly deadline-bound polling so completed
                # children are not held for an avoidable extra 50 ms tick.
                cancel.wait(0.005 if deadline_monotonic_ns is not None else 0.05)
        except Exception as exc:
            dispatch_error = exc
        finally:
            if process.poll() is None:
                try:
                    self._stop(process)
                except Exception as exc:
                    cleanup_error = f"{type(exc).__name__}: {exc}"
            for pipe_worker in feeders:
                pipe_worker.join(timeout=3)
        if cleanup_error or any(pipe_worker.is_alive() for pipe_worker in feeders):
            raise WizardError(
                "DIAGNOSTIC_CLEANUP_UNCERTAIN",
                cleanup_error or "Output stream cleanup exceeded deadline.",
            )
        if (
            pipe_failed.is_set() and outcome not in {"CANCELLED", "TIMED_OUT"}
        ) or dispatch_error is not None:
            raise WizardError(
                "DIAGNOSTIC_PIPE_FAILED",
                "Diagnostic IPC failed; cleanup completed without automatic replay.",
            ) from dispatch_error
        if excessive.is_set():
            outcome = "FAILED"
        if outcome is None and deadline_expired():
            outcome = 'TIMED_OUT'
        if outcome:
            return _diagnostic_completion(
                action_id,
                outcome,
                "Diagnostic ended without automatic replay.",
                output_limit_exceeded=excessive.is_set(),
                elapsed_s=round(time.monotonic() - started, 3),
            )
        try:
            result = decode_diagnostic_json(bytes(stdout), maximum=MAX_STDOUT)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise WizardError(
                "INVALID_WORKER_RESULT", "Worker did not return bounded JSON."
            ) from exc
        result = validate_diagnostic_worker_result(
            result, action_id=action_id, returncode=process.returncode
        )
        result["worker_exit_code"] = process.returncode
        result["elapsed_s"] = round(time.monotonic() - started, 3)
        result["worker_stderr"] = stderr.decode("utf-8", errors="replace")
        return result
