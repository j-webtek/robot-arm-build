"""Cross-language wire tests of the separately linked incapable presence child.

These direct subprocess tests verify admission, native fixture bytes and bounded
parent cleanup only. They do not qualify a Job, M1 scope, physical absence or a
device API. The production presence executable is never selected or launched.
"""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import threading
import time

import pytest

from rocell.providers.windows import usb_presence_protocol as wire


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "native/windows_usb_presence/build/Release/rocell_usb_presence_entry_tests.exe"
)
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Fixed Windows incapable entry executable only"
)


def request():
    """Explicitly modeled bindings; the builder does not issue an M1 permit."""
    return wire.build_usb_presence_request(
        attempt_id="MODELED_PRESENCE_ENTRY",
        session_id="MODELED_SESSION",
        source_sha256="a" * 64,
        phase_binding_sha256="b" * 64,
        target_instance_id=r"USB\VID_1234&PID_5678\UNIT_A",
        selected_identity_sha256="c" * 64,
        operation_sha256="d" * 64,
        permit_sha256="e" * 64,
        helper_sha256="f" * 64,
        runtime_registration_sha256="1" * 64,
        request_nonce="2" * 64,
    )


class EntryPipe:
    """One fixed child and only its inherited pipes; no process enumeration."""

    def __init__(self, req, *, expected_hash=None, argv=None):
        self.request = req
        self.started = time.monotonic()
        self.deadline = self.started + 8.0
        self.process = subprocess.Popen(
            [
                str(FIXTURE),
                *(
                    argv
                    if argv is not None
                    else [
                        "--owned-usb-presence",
                        "--request-sha256",
                        req.sha256 if expected_hash is None else expected_hash,
                    ]
                ),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS,
        )
        self.streams = (
            self.process.stdin,
            self.process.stdout,
            self.process.stderr,
        )
        # Peek is limited to this exact child's stdout handle. No blocking
        # readline, reader thread or unrelated process/device handle is used.
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.PeekNamedPipe.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPDWORD,
            wintypes.LPDWORD,
            wintypes.LPDWORD,
        ]
        self.kernel.PeekNamedPipe.restype = wintypes.BOOL

    def remaining(self):
        left = self.deadline - time.monotonic()
        assert left > 0, "Fixed entry exceeded the unchanged 8-second test guard"
        return left

    def send(self, payload):
        assert type(payload) is bytes and len(payload) <= wire.MAX_REQUEST_BYTES
        assert self.process.stdin is not None
        self.process.stdin.write(payload)
        self.process.stdin.flush()

    def ready(self):
        import msvcrt

        pending = bytearray()
        assert self.process.stdout is not None
        handle = msvcrt.get_osfhandle(self.process.stdout.fileno())
        while True:
            self.remaining()
            available = wintypes.DWORD()
            ok = self.kernel.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(available), None
            )
            if not ok:
                assert ctypes.get_last_error() == 109  # Own pipe broken.
                assert not pending
                return None
            if available.value:
                assert len(pending) + available.value <= 1024
                chunk = self.process.stdout.read(available.value)
                assert chunk
                pending.extend(chunk)
                if b"\n" in pending:
                    assert pending.endswith(b"\n") and pending.count(b"\n") == 1
                    return wire.decode_usb_presence_ready(
                        bytes(pending).rstrip(b"\r\n"),
                        self.request,
                        child_pid=self.process.pid,
                    )
            elif self.process.poll() is not None:
                assert not pending
                return None
            time.sleep(0.005)

    def finish(self, *, eof=True):
        if not eof:
            # This deliberately withholds EOF through the child's own original
            # five-second admission deadline; no timeout is renewed.
            self.process.wait(timeout=self.remaining())
        if self.process.stdin is not None:
            self.process.stdin.close()
            self.process.stdin = None
        out, err = self.process.communicate(timeout=self.remaining())
        assert len(out) <= wire.MAX_RESULT_BYTES + 1 and len(err) <= 4096
        return out, err

    def cleanup(self):
        if self.process.poll() is None:
            self.process.kill()  # This exact incapable root only.
        if self.process.stdin is not None:
            self.process.stdin.close()
            self.process.stdin = None
        self.process.communicate(timeout=1.0)
        self.process.wait(timeout=1.0)
        for stream in self.streams:
            stream.close()
        assert self.process.poll() is not None
        assert all(stream.closed for stream in self.streams)


@contextmanager
def entry(req=None, **kwargs):
    if not FIXTURE.is_file():
        pytest.skip("Prebuilt separately linked incapable entry fixture is absent")
    assert FIXTURE.name == "rocell_usb_presence_entry_tests.exe"
    child = EntryPipe(request() if req is None else req, **kwargs)
    try:
        yield child
    finally:
        child.cleanup()


def released(child):
    child.send(child.request.payload + b"\n")
    ready = child.ready()
    assert ready is not None
    release = wire.encode_usb_presence_release(
        ready, child.request, child_pid=child.process.pid
    )
    return ready, release


def test_actual_incapable_entry_roundtrip_uses_strict_python_result_decoder():
    with entry() as child:
        ready, release = released(child)
        child.send(release + b"\n")
        out, err = child.finish()
        assert child.process.returncode == 0 and err == b""
        observed = wire.decode_usb_presence_result(
            out.rstrip(b"\r\n"),
            child.request,
            child_pid=child.process.pid,
            challenge=ready["challenge"],
            expected_provider="INCAPABLE_FIXTURE",
        )
        doc = observed.to_dict()
        assert doc["request_sha256"] == child.request.sha256
        assert doc["outcome"] == "ABSENT" and doc["api_calls"] == 4
        assert len(doc["samples"]) == 2
        assert all(s["complete"] and not s["target_present"] for s in doc["samples"])
        assert doc["device_handle_opens"] == doc["configuration_writes"] == 0
        assert doc["frames"] == 0 and doc["physical_authority"] is False
        assert doc["finished"]["monotonic_ms"] - doc["started"]["monotonic_ms"] < 2000
        with pytest.raises(ValueError, match="RESULT_PROVIDER_BINDING"):
            wire.decode_usb_presence_result(
                out.rstrip(b"\r\n"),
                child.request,
                child_pid=child.process.pid,
                challenge=ready["challenge"],
                expected_provider="WINDOWS_CONFIGURATION_MANAGER",
            )


@pytest.mark.parametrize(
    "field", ["challenge", "request_sha256", "child_pid", "permit_sha256"]
)
def test_wrong_release_subject_never_publishes_observation(field):
    with entry() as child:
        _, release = released(child)
        document = wire._load(release, 1023)
        document[field] = child.process.pid + 1 if field == "child_pid" else "0" * 64
        child.send(wire.canonical(document) + b"\n")
        out, err = child.finish()
        assert child.process.returncode == 2 and out == err == b""


def test_wrong_request_argument_hash_never_emits_ready():
    with entry(expected_hash="0" * 64) as child:
        child.send(child.request.payload + b"\n")
        assert child.ready() is None
        out, err = child.finish()
        assert child.process.returncode == 2 and out == err == b""


def test_extra_bytes_after_release_never_publish_observation():
    with entry() as child:
        _, release = released(child)
        child.send(release + b"\nextra\n")
        out, err = child.finish()
        assert child.process.returncode == 2 and out == err == b""


def test_eof_without_release_never_publishes_observation():
    with entry() as child:
        released(child)
        out, err = child.finish()
        assert child.process.returncode == 2 and out == err == b""


def test_release_without_eof_expires_original_native_admission_deadline():
    with entry() as child:
        _, release = released(child)
        child.send(release + b"\n")
        out, err = child.finish(eof=False)
        assert child.process.returncode == 2 and out == err == b""
        assert 4.5 <= time.monotonic() - child.started < 8.0


def test_parent_cancel_before_eof_kills_only_incapable_child_and_retains_no_result():
    stop = threading.Event()
    with entry() as child:
        _, release = released(child)
        child.send(release + b"\n")
        stop.set()
        if stop.is_set():
            child.process.kill()
        out, err = child.finish()
        assert child.process.returncode != 0 and out == err == b""
        assert time.monotonic() - child.started < 2.0


@pytest.mark.parametrize(
    "argv", [["--endpoint", "arbitrary"], ["--owned-usb-presence", "extra"]]
)
def test_no_alternate_endpoint_or_incomplete_cli_entry(argv):
    with entry(argv=argv) as child:
        out, err = child.finish()
        assert child.process.returncode == 2 and out == err == b""
