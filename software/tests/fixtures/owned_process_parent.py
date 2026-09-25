"""Harmless parent-death fixture; never imported by the application.

Its only child is the fixed incapable process fixture. Prints that owned PID
after containment/start so the test can hold a synchronization handle before
terminating this explicitly created parent. No device APIs are imported.
"""

import hashlib
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from rocell.providers.windows.owned_worker_process import (
    FIXTURE_PATH,
    OwnedWindowsWorker,
    OwnedWorkerRequest,
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
)
from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess


def pin(path):
    return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())


class FixtureAuthority:
    consumed = False

    def __call__(self, registration, request, digest):
        if self.consumed or registration.composition != "INCAPABLE_PROCESS_FIXTURE":
            raise ValueError("incapable fixture authority denied")
        self.consumed = True


class ReportingProcess(WindowsOwnedProcess):
    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)
        print(json.dumps({"contained_child_pid": self.pid}), flush=True)


registration = WorkerProcessRegistration(
    "parent-death-fixture",
    pin(Path(sys.executable)),
    ("-I", "-S", str(FIXTURE_PATH), "stall"),
    (pin(FIXTURE_PATH),),
    Path.cwd(),
    WorkerProcessBudget(run_timeout_ms=10_000),
    "INCAPABLE_PROCESS_FIXTURE",
)
request = OwnedWorkerRequest(
    "parent-death",
    "fixture-session",
    "a" * 64,
    "b" * 64,
    "c" * 64,
    time.monotonic_ns() + 15_000_000_000,
)
result = OwnedWindowsWorker(
    registration, authorizer=FixtureAuthority(), _backend_factory=ReportingProcess
).run(request, cancellation=threading.Event(), deadline_ns=request.expires_at_ns)
print(json.dumps(result.to_dict()), flush=True)
