"""Only fixed incapable children; never devices, inventory, or native adapters."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import threading
import time

import pytest

import rocell.providers.windows.owned_worker_process as module
from rocell.providers.windows.owned_worker_process import (
    FIXTURE_PATH,
    OwnedWindowsWorker,
    OwnedWorkerRequest,
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
)


def pin(path):
    return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())


def registration(tmp_path, scenario="nominal", **budget):
    return WorkerProcessRegistration(
        "incapable-process",
        pin(Path(sys._base_executable)),
        ("-I", "-S", str(FIXTURE_PATH), scenario),
        (pin(FIXTURE_PATH),),
        tmp_path,
        WorkerProcessBudget(**budget),
        "INCAPABLE_PROCESS_FIXTURE",
    )


def request(**kwargs):
    return OwnedWorkerRequest(
        "attempt-fixture",
        "session-fixture",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        time.monotonic_ns() + 15_000_000_000,
        **kwargs,
    )


class FixtureAuthority:
    def __init__(self, expected):
        self.expected = expected
        self.calls = 0

    def __call__(self, registration, value, digest):
        assert value == self.expected
        assert registration.composition == "INCAPABLE_PROCESS_FIXTURE"
        assert len(digest) == 64
        assert self.calls == 0
        self.calls += 1


def run(tmp_path, scenario="nominal", **budget):
    reg, req = registration(tmp_path, scenario, **budget), request()
    authority = FixtureAuthority(req)
    worker = OwnedWindowsWorker(reg, authorizer=authority)
    result = worker.run(
        req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
    )
    return worker, authority, result


def test_constructor_status_are_inert_and_request_is_one_use(tmp_path):
    req = request()
    worker = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=lambda: pytest.fail(
            "No backend on construction/status/precancel"
        ),
    )
    assert not worker.status()["consumed"]
    stop = threading.Event()
    stop.set()
    result = worker.run(req, cancellation=stop, deadline_ns=req.expires_at_ns)
    assert result.status == "CANCELLED" and not result.process_created
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        worker.run(req, cancellation=stop, deadline_ns=req.expires_at_ns)


def test_physical_registration_is_held_before_backend_or_authorizer(tmp_path):
    req = request()
    worker = OwnedWindowsWorker(
        replace(registration(tmp_path), composition="PHYSICAL_UNQUALIFIED"),
        authorizer=lambda *args: pytest.fail("No physical authority redemption"),
        _backend_factory=lambda: pytest.fail("No native backend creation"),
    )
    result = worker.run(
        req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
    )
    assert result.primary_error == "PHYSICAL_PROVIDER_QUALIFICATION_HELD"
    assert not result.process_created


@pytest.mark.parametrize("changed_bound", ["expiration", "deadline"])
def test_authorization_digest_binds_each_monotonic_lifetime_limit(
    tmp_path, changed_bound
):
    class NoProcessBackend:
        def pin(self, _):
            pass

        def start(self, *args, **kwargs):
            pytest.fail("Authority refusal must precede process creation")

        def cleanup(self, _):
            return ()

    reg, original = registration(tmp_path), request()
    digests = []

    def deny(_registration, _request, digest):
        digests.append(digest)
        raise PermissionError("incapable fixture denial")

    for offset in (0, 1_000_000_000):
        req = replace(
            original,
            expires_at_ns=original.expires_at_ns
            + (offset if changed_bound == "expiration" else 0),
        )
        deadline = original.expires_at_ns - (
            offset if changed_bound == "deadline" else 0
        )
        result = OwnedWindowsWorker(
            reg, authorizer=deny, _backend_factory=NoProcessBackend
        ).run(req, cancellation=threading.Event(), deadline_ns=deadline)
        assert result.primary_error == "PermissionError"
        assert not result.process_created and not result.cleanup_errors
        assert result.request_sha256 == digests[-1]
    assert len(set(digests)) == 2


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b"[]", b"{", b"\xff"])
def test_strict_bounded_json(raw):
    with pytest.raises(ValueError):
        decode_owned_json(raw, maximum=1024)


native = pytest.mark.skipif(os.name != "nt", reason="Actual Windows process ownership")


@native
@pytest.mark.parametrize("repeat", range(20))
def test_real_job_child_exact_request_and_cleanup(tmp_path, repeat):
    worker, authority, result = run(tmp_path)
    assert result.primary_error is None
    assert result.status == "SUCCEEDED", result.to_dict()
    assert result.process_created and result.initial_thread_resumed
    assert result.tree_exit_confirmed and not result.cleanup_errors
    assert result.owned_process_id > 0 and result.owned_process_id != os.getpid()
    # The inert fixture deliberately reports PID zero. Ownership comes from
    # CreateProcess, not from a child's self-reported JSON field.
    assert result.parsed_result['fixture_result']['child_pid'] == 0
    assert 0 < result.finished_monotonic_ns <= time.monotonic_ns()
    assert result.stdin_bytes_written > 0 and authority.calls == 1
    assert result.to_dict()["physical_authority"] is False
    assert result.to_dict()["device_cleanup_confirmed"] is False


@native
@pytest.mark.parametrize(
    "scenario,code",
    [
        ("stdout-flood", "STDOUT_LIMIT"),
        ("stderr-flood", "STDERR_LIMIT"),
        ("stall", "TIMED_OUT"),
        ("malformed", "DUPLICATE_JSON_FIELD"),
        ("wrong-binding", "RESULT_BINDING_OR_SCHEMA_MISMATCH"),
        ("exit-failure", "WORKER_EXIT_FAILED"),
        ("spawn-child", "DESCENDANTS_REMAIN_AFTER_ROOT_EXIT"),
        ("handle-flood", "OBSERVED_HANDLE_LIMIT"),
    ],
)
def test_real_failure_is_bounded_and_tree_cleanup_retained(tmp_path, scenario, code):
    worker, authority, result = run(
        tmp_path,
        scenario,
        run_timeout_ms=1000,
        stdout_bytes=1024,
        stderr_bytes=1024,
        observed_handles_per_process=256,
    )
    assert result.primary_error == code, result.to_dict()
    assert result.tree_exit_confirmed and not result.cleanup_errors, result.to_dict()
    assert len(result.stdout) <= 1024 and len(result.stderr) <= 1024
    assert result.elapsed_ns < 5_000_000_000 and authority.calls == 1


@native
def test_stalled_stdin_is_cancelled_without_writer_thread(tmp_path):
    req = request(payload_json=json.dumps({"padding": "x" * 55_000}).encode())
    reg = registration(tmp_path, "stalled-input", run_timeout_ms=300)
    result = OwnedWindowsWorker(reg, authorizer=FixtureAuthority(req)).run(
        req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
    )
    assert result.primary_error == "TIMED_OUT", result.to_dict()
    assert result.tree_exit_confirmed and not result.cleanup_errors, result.to_dict()
    assert result.stdin_bytes_written == 0


@native
@pytest.mark.parametrize(
    "scenario,detail",
    [("breakaway", "breakaway-denied"), ("memory-limit", "memory-limit-observed")],
)
def test_kernel_job_policies_apply_to_incapable_child(tmp_path, scenario, detail):
    _, _, result = run(
        tmp_path,
        scenario,
        process_memory_bytes=64 * 1024 * 1024,
        job_memory_bytes=128 * 1024 * 1024,
    )
    assert json.loads(result.stdout)["fixture_result"]["detail"] == detail
    assert result.status == "SUCCEEDED", (result.to_dict(), result.stdout)
    assert result.parsed_result["fixture_result"]["detail"] == detail


def test_primary_error_survives_cleanup_exception_and_holds_future_dispatch(
    tmp_path, monkeypatch
):
    class Backend:
        created = resumed = tree_exited = False
        returncode = None
        written = peak_handles = peak_processes = 0
        stdout = stderr = b""

        def pin(self, _):
            raise ValueError("original failure")

        def cleanup(self, _):
            raise OSError("cleanup failure")

    monkeypatch.setattr(module, "_UNRESOLVED_BACKEND", None)
    req = request()
    result = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=Backend,
    ).run(req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns)
    assert result.primary_error == "ValueError"
    assert result.cleanup_errors == ("CLEANUP_EXCEPTION:OSError",)
    assert module._UNRESOLVED_BACKEND is not None
    held = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=lambda: pytest.fail("Held after uncertain cleanup"),
    )
    assert (
        held.run(
            req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
        ).primary_error
        == "PROCESS_CLEANUP_HOLD"
    )


@native
def test_root_exit_resamples_job_after_earlier_active_root_observation():
    import ctypes
    from ctypes import wintypes
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    class Api:
        def WaitForSingleObject(self, *_):
            return 0

        def GetExitCodeProcess(self, _, output):
            ctypes.cast(output, ctypes.POINTER(wintypes.DWORD))[0] = 0
            return True

    backend = WindowsOwnedProcess.__new__(WindowsOwnedProcess)
    backend.k = Api()
    backend._poll_write = lambda: None
    backend._read_available = lambda *args: None
    values = iter((1, 0))
    backend._active = lambda **kwargs: next(values)
    backend.outpipe = backend.errpipe = backend.process = 1
    backend.stdout_eof = backend.stderr_eof = True
    backend.pending = False
    backend.errors = []
    assert backend.poll(WorkerProcessBudget()) is True
    assert backend.tree_exited and backend.returncode == 0


def test_two_instances_cannot_replace_an_unresolved_owner(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class Backend:
        created = resumed = tree_exited = False
        returncode = None
        written = peak_handles = peak_processes = 0
        stdout = stderr = b""

        def pin(self, _):
            entered.set()
            assert release.wait(2)
            raise ValueError("fixture pin failure")

        def cleanup(self, _):
            return ("PENDING_STDIN_STORAGE_RETAINED",)

    monkeypatch.setattr(module, "_UNRESOLVED_BACKEND", None)
    req = request()
    owner = Backend()
    first = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=lambda: owner,
    )
    results = []
    thread = threading.Thread(
        target=lambda: results.append(
            first.run(
                req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
            )
        )
    )
    thread.start()
    try:
        assert entered.wait(2)
        second = OwnedWindowsWorker(
            registration(tmp_path),
            authorizer=FixtureAuthority(req),
            _backend_factory=lambda: pytest.fail("No second owner created"),
        )
        result = second.run(
            req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
        )
        assert result.primary_error == "OWNED_PROCESS_ALREADY_RUNNING"
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive() and results[0].cleanup_errors
    assert module._UNRESOLVED_BACKEND is owner


@native
def test_package_hash_denial_and_ancestor_pins_precede_child_creation(tmp_path):
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    req = request()
    reg = registration(tmp_path)
    changed = replace(
        reg, package_files=(replace(reg.package_files[0], sha256="f" * 64),)
    )
    authority = FixtureAuthority(req)
    result = OwnedWindowsWorker(changed, authorizer=authority).run(
        req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
    )
    assert (
        not result.process_created
        and authority.calls == 0
        and not result.cleanup_errors
    )

    class Checking(WindowsOwnedProcess):
        def start(self, *args, **kwargs):
            with pytest.raises(OSError):
                tmp_path.rename(tmp_path.with_name(tmp_path.name + "-retargeted"))
            with pytest.raises(OSError):
                with FIXTURE_PATH.open("r+b"):
                    pass
            return super().start(*args, **kwargs)

    result = OwnedWindowsWorker(
        reg, authorizer=FixtureAuthority(req), _backend_factory=Checking
    ).run(req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns)
    assert result.primary_error is None
    assert result.status == "SUCCEEDED", result.to_dict()


@native
def test_containment_denial_and_cancel_before_resume_never_run_child(tmp_path):
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    class Denied(WindowsOwnedProcess):
        def start(self, *args, **kwargs):
            original = self.k.UpdateProcThreadAttribute
            self.k.UpdateProcThreadAttribute = lambda *values: (
                0 if values[2] == 0x2000D else original(*values)
            )
            return super().start(*args, **kwargs)

    req = request()
    result = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=Denied,
    ).run(req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns)
    assert (
        not result.process_created
        and not result.initial_thread_resumed
        and not result.cleanup_errors
    )
    cancelled = threading.Event()

    class CancelBeforeResume(WindowsOwnedProcess):
        def start(self, registration, wire, *, check):
            def cancel_at_boundary():
                if self.created:
                    cancelled.set()
                check()

            return super().start(registration, wire, check=cancel_at_boundary)

    result = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=CancelBeforeResume,
    ).run(req, cancellation=cancelled, deadline_ns=req.expires_at_ns)
    assert result.process_created and not result.initial_thread_resumed
    assert (
        result.status == "CANCELLED"
        and result.tree_exit_confirmed
        and not result.cleanup_errors
    )


@native
def test_parent_death_kills_its_contained_incapable_child(tmp_path):
    import ctypes
    from ctypes import wintypes

    fixture_parent = Path(__file__).parents[1] / "fixtures" / "owned_process_parent.py"
    process = subprocess.Popen(
        [sys._base_executable, "-I", "-S", str(fixture_parent)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    child = None
    lines = []
    reader = threading.Thread(
        target=lambda: lines.append(process.stdout.readline()), daemon=True
    )
    reader.start()
    try:
        reader.join(5)
        assert (
            not reader.is_alive() and lines and lines[0]
        ), "Incapable parent startup failed"
        pid = json.loads(lines[0])["contained_child_pid"]
        child = kernel.OpenProcess(0x100000, False, pid)
        assert child
        process.kill()  # Exact owned incapable Popen handle; no PID-based kill.
        process.wait(timeout=3)
        assert kernel.WaitForSingleObject(child, 3000) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        reader.join(2)
        if child:
            assert kernel.CloseHandle(child)
        process.stdout.close()
        process.stderr.close()


@pytest.mark.parametrize(
    "transition,code", [("late", "TIMED_OUT"), ("cancel", "CANCELLED")]
)
def test_final_poll_cannot_override_cancellation_or_deadline(
    tmp_path, transition, code
):
    now = [time.monotonic_ns()]
    cancellation = threading.Event()

    class Backend:
        created = resumed = tree_exited = True
        returncode = 0
        written = peak_handles = peak_processes = 0
        stderr = b""

        def pin(self, _):
            pass

        def start(self, _, wire, **kwargs):
            raw = json.loads(wire)
            self.stdout = json.dumps(
                {
                    "schema": module.RESULT_SCHEMA,
                    "request_sha256": raw["request_sha256"],
                    "attempt_id": raw["attempt_id"],
                    "physical_authority": False,
                    "fixture_result": {
                        "scenario": "nominal",
                        "child_pid": 0,
                        "detail": "completed",
                    },
                }
            ).encode()

        def poll(self, _):
            if transition == "late":
                now[0] += 10_000_000_000
            else:
                cancellation.set()
            return True

        def cleanup(self, _):
            return ()

    req = request()
    result = OwnedWindowsWorker(
        registration(tmp_path),
        authorizer=FixtureAuthority(req),
        _backend_factory=Backend,
        _clock=lambda: now[0],
    ).run(req, cancellation=cancellation, deadline_ns=req.expires_at_ns)
    assert result.primary_error == code and result.status == code
    assert result.tree_exit_confirmed and result.process_created and result.stdout
    assert result.parsed_result is None


@native
def test_failed_pin_close_keeps_owner_without_second_attempt():
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    class FailedStream:
        calls = 0

        def close(self):
            self.calls += 1
            raise OSError("fixture close failure")

    backend = WindowsOwnedProcess()
    stream = FailedStream()
    backend.pins = [stream]
    errors = backend.cleanup(time.monotonic_ns() + 1_000_000_000)
    assert errors == ("PIN_CLOSE_UNCONFIRMED",)
    assert backend.pins == [stream] and stream.calls == 1


def test_late_cleanup_is_retained_as_uncertain_without_losing_primary(
    tmp_path, monkeypatch
):
    class Backend:
        created = resumed = tree_exited = False
        returncode = None
        written = peak_handles = peak_processes = 0
        stdout = stderr = b""

        def pin(self, _):
            raise ValueError("fixture original error")

        def cleanup(self, _):
            time.sleep(0.15)
            return ()

    monkeypatch.setattr(module, "_UNRESOLVED_BACKEND", None)
    req = request()
    result = OwnedWindowsWorker(
        registration(tmp_path, cleanup_timeout_ms=100),
        authorizer=FixtureAuthority(req),
        _backend_factory=Backend,
    ).run(req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns)
    assert result.primary_error == "ValueError"
    assert result.cleanup_errors == ("CLEANUP_DEADLINE_EXCEEDED",)
    assert module._UNRESOLVED_BACKEND is not None and result.status == "FAILED"


@native
def test_active_process_limit_refuses_fixture_grandchild(tmp_path):
    _, _, result = run(tmp_path, "spawn-child", process_count=1)
    assert result.primary_error == "WORKER_EXIT_FAILED", result.to_dict()
    # Windows may count the rejected association briefly before terminating it;
    # the fixture's CreateProcess fails and the child never executes its script.
    assert result.tree_exit_confirmed and result.peak_active_processes <= 2


@native
def test_denied_external_authority_never_creates_child(tmp_path):
    req = request()
    calls = []

    def deny(*args):
        calls.append(args)
        raise PermissionError("fixture denied")

    result = OwnedWindowsWorker(registration(tmp_path), authorizer=deny).run(
        req, cancellation=threading.Event(), deadline_ns=req.expires_at_ns
    )
    assert result.primary_error == "PermissionError"
    assert len(calls) == 1 and not result.process_created and not result.cleanup_errors
