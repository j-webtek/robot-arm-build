"""Explicit incapable child for process-ownership tests. No device libraries.

Only fixed scenarios exist. The parent pins this exact file and argv; it never
accepts Python snippets, executable paths, COM endpoints, or camera commands.
"""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    scenario = sys.argv[1]
    if scenario == "fixture-sleeper":
        time.sleep(20)
        return 0
    if scenario == "stalled-input":
        time.sleep(20)
        return 0
    raw = sys.stdin.buffer.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        return 3
    request = json.loads(raw)
    body = {key: value for key, value in request.items() if key != "request_sha256"}
    if (
        hashlib.sha256(
            json.dumps(
                body,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        != request["request_sha256"]
    ):
        return 4
    child_pid = 0
    detail = "completed"
    if scenario == "stall":
        time.sleep(20)
    if scenario == "stdout-flood":
        for _ in range(512):
            sys.stdout.buffer.write(b"x" * 4096)
            sys.stdout.buffer.flush()
    if scenario == "stderr-flood":
        for _ in range(512):
            sys.stderr.buffer.write(b"e" * 4096)
            sys.stderr.buffer.flush()
    if scenario == "malformed":
        sys.stdout.write('{"duplicate":1,"duplicate":2}')
        return 0
    if scenario == "exit-failure":
        return 7
    if scenario in {"spawn-child", "breakaway"}:
        try:
            child = subprocess.Popen(
                [sys.executable, "-I", "-S", str(Path(__file__)), "fixture-sleeper"],
                creationflags=0x01000000 if scenario == "breakaway" else 0x08000000,
                close_fds=True,
            )
            child_pid = child.pid
        except OSError:
            if scenario != "breakaway":
                raise
            detail = "breakaway-denied"
    if scenario == "memory-limit":
        try:
            blocks = [bytearray(16 * 1024 * 1024) for _ in range(64)]
            detail = "unexpected-allocation-success"
            del blocks
        except MemoryError:
            detail = "memory-limit-observed"
    if scenario == "handle-flood":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateEventW.restype = ctypes.c_void_p
        handles = [kernel.CreateEventW(None, False, False, None) for _ in range(1024)]
        time.sleep(20)
        if not handles:
            return 5
    response = {
        "schema": "rocell.owned_worker_fixture_result.v1",
        "request_sha256": (
            "f" * 64 if scenario == "wrong-binding" else request["request_sha256"]
        ),
        "attempt_id": request["attempt_id"],
        "physical_authority": False,
        "fixture_result": {
            "scenario": scenario,
            "child_pid": child_pid,
            "detail": detail,
        },
    }
    sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
