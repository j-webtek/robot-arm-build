"""Fixed isolated child: real feedback algorithm, sealed memory serial only.

No arbitrary module/backend/port-command selection is accepted. This bootstrap
uses stdlib until the exact closed source archive is verified. The real worker
and non-purging adapter are imported from that pinned archive, not site-packages.
RELEASE and EOF precede construction of even the incapable serial facade.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import secrets
import sys
import time
from threading import Event
from typing import Any
import zipfile

STUB = b'"""Isolated owned-arm child namespace; no application bootstrap."""\n'
NAMESPACES = (
    "rocell",
    "rocell/application",
    "rocell/arm",
    "rocell/providers",
    "rocell/providers/windows",
)
ROCELL_MODULES = (
    "application/physical_connection_contracts.py",
    "application/rehearsal_arm_feedback_evidence.py",
    "arm/protocol.py",
    "arm/feedback.py",
    "arm/feedback_wire.py",
    "providers/windows/arm_feedback_worker.py",
    "providers/windows/arm_nonpurging_adapter.py",
    "providers/windows/nonpurging_serial_api.py",
    "providers/windows/nonpurging_serial_backend.py",
    "providers/windows/owned_worker_process.py",
    "providers/windows/arm_owned_protocol.py",
    "application/arm_controller_resolution.py",
    "application/physical_device_inventory.py",
    "providers/windows/controller_metadata.py",
    "providers/windows/incapable_controller_metadata.py",
)
PACKAGING_MODULES = (
    "__init__.py",
    "_elffile.py",
    "_manylinux.py",
    "_musllinux.py",
    "_parser.py",
    "_ranges.py",
    "_structures.py",
    "_tokenizer.py",
    "dependency_groups.py",
    "direct_url.py",
    "errors.py",
    "markers.py",
    "metadata.py",
    "pylock.py",
    "ranges.py",
    "requirements.py",
    "specifiers.py",
    "tags.py",
    "utils.py",
    "version.py",
)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _bootstrap(archive_path: str, expected_sha256: str) -> None:
    # Parent pins the archive, interpreter and this exact script against writes
    # and ancestor retargeting for the entire owned process lifetime. The child
    # additionally refuses any code not equal to its fixed current source roster.
    path = Path(archive_path)
    require(path.is_absolute() and path.name == "runtime.zip", "FIXED_ARCHIVE_REQUIRED")
    require(0 < path.stat().st_size <= 8 * 1024 * 1024, "ARCHIVE_SIZE")
    with path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    require(
        0 < len(raw) <= 8 * 1024 * 1024
        and hashlib.sha256(raw).hexdigest() == expected_sha256,
        "ARCHIVE_HASH",
    )
    workspace = Path(__file__).parents[5]
    expected = {namespace + "/__init__.py": STUB for namespace in NAMESPACES}
    for name in ROCELL_MODULES:
        source = workspace / "software/src/rocell" / name
        require(source.stat().st_size <= 2 * 1024 * 1024, "SOURCE_LIMIT")
        with source.open("rb") as stream:
            expected["rocell/" + name] = stream.read(2 * 1024 * 1024 + 1)
    for name in PACKAGING_MODULES:
        source = workspace / ".venv/Lib/site-packages/packaging" / name
        require(source.stat().st_size <= 2 * 1024 * 1024, "SOURCE_LIMIT")
        with source.open("rb") as stream:
            expected["packaging/" + name] = stream.read(2 * 1024 * 1024 + 1)
    with zipfile.ZipFile(path) as archive:
        rows = archive.infolist()
        require(
            len(rows) == len(expected)
            and {row.filename for row in rows} == set(expected),
            "ARCHIVE_ROSTER",
        )
        for row in rows:
            require(
                row.compress_type == zipfile.ZIP_STORED
                and row.file_size == len(expected[row.filename])
                and row.file_size <= 2 * 1024 * 1024
                and archive.read(row) == expected[row.filename],
                "ARCHIVE_SOURCE_MISMATCH",
            )
    sys.path.insert(0, str(path))


class _Input:
    """Finite inherited-pipe reader. Kernel pipe calls are not serial calls."""

    def __init__(self) -> None:
        require(os.name == "nt", "WINDOWS_INHERITED_PIPE_REQUIRED")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.GetStdHandle.argtypes, self.api.GetStdHandle.restype = [
            wintypes.DWORD
        ], wintypes.HANDLE
        self.api.GetFileType.argtypes, self.api.GetFileType.restype = [
            wintypes.HANDLE
        ], wintypes.DWORD
        self.api.PeekNamedPipe.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self.api.PeekNamedPipe.restype = wintypes.BOOL
        self.api.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self.api.ReadFile.restype = wintypes.BOOL
        self.handle = self.api.GetStdHandle(-10 & 0xFFFFFFFF)
        require(self.api.GetFileType(self.handle) == 3, "INHERITED_PIPE_REQUIRED")
        self.pending = bytearray()
        self.eof = False

    def _poll(self, deadline: int, maximum: int) -> None:
        require(time.monotonic_ns() < deadline, "CHILD_ADMISSION_DEADLINE")
        available = wintypes.DWORD()
        if not self.api.PeekNamedPipe(
            self.handle, None, 0, None, ctypes.byref(available), None
        ):
            require(ctypes.get_last_error() in {109, 232}, "PIPE_PEEK_FAILED")
            self.eof = True
            return
        if available.value:
            count = min(available.value, maximum + 1 - len(self.pending))
            require(count > 0, "PIPE_INPUT_LIMIT")
            buffer, read = ctypes.create_string_buffer(count), wintypes.DWORD()
            require(
                bool(
                    self.api.ReadFile(
                        self.handle, buffer, count, ctypes.byref(read), None
                    )
                ),
                "PIPE_READ_FAILED",
            )
            self.pending.extend(buffer.raw[: read.value])
            require(len(self.pending) <= maximum, "PIPE_INPUT_LIMIT")
        else:
            time.sleep(0.002)

    def line(self, *, deadline: int, maximum: int) -> bytes:
        while b"\n" not in self.pending:
            require(not self.eof, "EARLY_STDIN_EOF")
            self._poll(deadline, maximum)
        line, rest = bytes(self.pending).split(b"\n", 1)
        self.pending = bytearray(rest)
        require(len(line) + 1 <= maximum, "PIPE_INPUT_LIMIT")
        return line + b"\n"

    def require_eof(self, *, deadline: int) -> None:
        require(not self.pending, "TRAILING_STDIN")
        while not self.eof:
            self._poll(deadline, 1)
            require(not self.pending, "TRAILING_STDIN")


def main() -> int:
    require(
        len(sys.argv) == 6
        and sys.argv[1] == "--incapable-arm"
        and sys.argv[3] == "--package-sha256"
        and sys.argv[5] == "--guarded",
        "FIXED_CHILD_ARGUMENTS_REQUIRED",
    )
    _bootstrap(sys.argv[2], sys.argv[4])
    from rocell.providers.windows.arm_owned_protocol import (
        ADMISSION_TIMEOUT_MS,
        REQUEST_SCHEMA,
        ArmOwnedRequest,
        ArmOwnedChildGate,
        build_arm_owned_result,
    )
    from rocell.application.physical_connection_contracts import EvidenceOrigin

    reader = _Input()
    initial_deadline = time.monotonic_ns() + ADMISSION_TIMEOUT_MS * 1_000_000
    request = ArmOwnedRequest(
        reader.line(deadline=initial_deadline, maximum=60 * 1024)[:-1]
    )
    # Legacy v1/v2 are decoded for historical evidence only, never re-admitted by
    # this executable. The version binds the release wait, not a renewed TTL.
    require(request.to_dict()["schema"] == REQUEST_SCHEMA, "ARM_REQUEST_VERSION_HELD")
    inner = request.feedback_request
    require(
        request.to_dict()["provenance"] == "INCAPABLE_NONPURGING_ARM_WORKER"
        and inner.controller.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL,
        "PHYSICAL_ARM_ACTIVATION_HELD",
    )
    gate = ArmOwnedChildGate(
        request,
        child_pid=os.getpid(),
        challenge_sha256=secrets.token_hex(32),
        started_monotonic_ns=time.monotonic_ns(),
    )
    sys.stdout.buffer.write(gate.ready.wire())
    sys.stdout.buffer.flush()
    release_deadline = time.monotonic_ns() + ADMISSION_TIMEOUT_MS * 1_000_000
    release_wire = reader.line(deadline=release_deadline, maximum=2048)
    reader.require_eof(deadline=release_deadline)
    gate.accept_release(release_wire, now_ns=time.monotonic_ns(), stdin_eof=True)

    # Only after release and EOF may the actual worker's sealed memory backend
    # be constructed. There is no caller-selected backend and no physical branch.
    from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
    from rocell.providers.windows.arm_nonpurging_adapter import (
        NonPurgingArmFeedbackBackend,
    )
    from rocell.providers.windows.nonpurging_serial_api import (
        IncapableWin32Scenario,
        IncapableWin32SerialApi,
    )
    from rocell.application.rehearsal_arm_feedback_evidence import (
        retain_rehearsal_arm_feedback_evidence,
    )
    from rocell.application.arm_controller_resolution import (
        ExplicitArmControllerResolver,
    )
    from rocell.providers.windows.incapable_controller_metadata import (
        IncapableControllerMetadataProducer,
    )

    scenario = request.to_dict()["scenario"]
    if scenario == "child-timeout":
        time.sleep(60)
        return 3
    options: dict[str, dict[str, Any]] = {
        "nominal": {},
        "boot-bytes": {"startup_bytes": b"rst:0x1 boot\n"},
        "short-write": {"short_write": 3},
        "timeout": {"response_bytes": b""},
        "identity-change": {},
        "identity-change-preopen": {},
        "malformed-metadata": {},
        "close-failure": {"fail_operations": ("close_port",)},
        "malformed-response": {"response_bytes": b"not-json\n"},
        "extra-response": {
            "response_bytes": b'{"T":1051,"x":0,"y":0,"z":0}\n{"T":1051,"x":0,"y":0,"z":0}\n'
        },
        "malformed-result": {},
    }
    require(scenario in options, "FIXED_SCENARIO_REQUIRED")
    api = IncapableWin32SerialApi(IncapableWin32Scenario(**options[scenario]))
    backend = NonPurgingArmFeedbackBackend(inner.controller, api=api)
    authorized = False
    cancellation = Event()
    metadata_scenario = (
        scenario
        if scenario
        in {"identity-change", "identity-change-preopen", "malformed-metadata"}
        else "nominal"
    )
    # Exercise the real CM ABI decoder, fresh inventory acquisition, matching
    # and worker boundaries. Only the sealed library/enumerator are modeled;
    # there is no host metadata fallback and no expected-identity shortcut.
    producer = IncapableControllerMetadataProducer(
        inner.controller, scenario=metadata_scenario
    )
    identity = ExplicitArmControllerResolver(
        inner.controller,
        producer.acquirer(
            deadline_ns=inner.expires_monotonic_ns, cancellation=cancellation
        ),
        deadline_ns=inner.expires_monotonic_ns,
        cancellation=cancellation,
    )

    def authorize(exact):
        nonlocal authorized
        require(not authorized and exact is inner, "INNER_ADMISSION_MISMATCH")
        authorized = True

    worker = ArmFeedbackWorker(
        authorizer=authorize, identity_resolver=identity, backend=backend
    )
    result = worker.run(inner, cancellation=cancellation)
    feedback = retain_rehearsal_arm_feedback_evidence(
        inner,
        result,
        binding_sha256=request.request_sha256,
        source_sha256=inner.source_sha256,
    )
    native = backend.retain_evidence(inner, result)
    retained = build_arm_owned_result(
        request,
        feedback_evidence=feedback,
        native_evidence=native,
        resolution_trace=identity.retained_trace(),
    )
    sys.stdout.buffer.write(
        b"malformed-result\n" if scenario == "malformed-result" else retained.wire()
    )
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException as error:
        if isinstance(error, SystemExit):
            raise
        # Raw protocol/port bytes never enter stderr; full valid diagnostics use
        # the retained result. Aborted bootstrap/admission has no fake receipt.
        sys.stderr.write(type(error).__name__ + "\n")
        sys.stderr.flush()
        sys.exit(3)
