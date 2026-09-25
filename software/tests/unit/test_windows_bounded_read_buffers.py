"""Bounded file-buffer behavior with incapable Win32 peers and real test files.

The peer covers short reads, growth beyond the limit, IO faults and allocation
failure. Native cases use only newly created ordinary files, never devices.
"""

import ctypes
import os
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application import physical_onboarding_durability as durability


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("bounded file reader tests cannot start processes")

    monkeypatch.setattr(subprocess, "Popen", denied)


class Function:
    """Allow ctypes-like signature attributes without loading a DLL."""

    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


def peer(monkeypatch, payload, *, short_read=None, failure_at=None, invalid_at=None):
    state = SimpleNamespace(offset=0, requests=[], closes=[], opens=[])
    token = object()

    def opened(path, **kwargs):
        state.opens.append((path, kwargs))
        return token

    def read(handle, buffer, requested, count, overlapped):
        assert handle is token and overlapped is None
        assert 0 < requested <= ctypes.sizeof(buffer)
        state.requests.append(requested)
        call = len(state.requests)
        if failure_at == call:
            return False
        if invalid_at == call:
            count._obj.value = requested + 1
            return True
        available = requested if short_read is None else min(short_read, requested)
        chunk = payload[state.offset : state.offset + available]
        ctypes.memmove(buffer, chunk, len(chunk))
        count._obj.value = len(chunk)
        state.offset += len(chunk)
        return True

    def close(handle):
        assert handle is token
        state.closes.append(handle)
        return True

    monkeypatch.setattr(durability, "_windows_open_regular_read_handle", opened)
    monkeypatch.setattr(
        durability,
        "_win32",
        lambda: SimpleNamespace(ReadFile=Function(read), CloseHandle=Function(close)),
    )
    monkeypatch.setattr(
        durability,
        "_win_error",
        lambda label: durability.PhysicalOnboardingDurabilityError(label),
    )
    return state


def count_allocations(monkeypatch):
    sizes = []
    create = durability.ctypes.create_string_buffer

    def counted(size, *args):
        sizes.append(size)
        return create(size, *args)

    monkeypatch.setattr(durability.ctypes, "create_string_buffer", counted)
    return sizes


def read(path, maximum):
    return durability._windows_read_regular_file(
        path, maximum_bytes=maximum, label="incapable file stream"
    )


def test_small_file_reuses_small_buffer_for_eof_and_copies_only_returned_bytes(
    tmp_path, monkeypatch
):
    payload = b"small original\x00with embedded nul\n"
    state = peer(monkeypatch, payload)
    allocations = count_allocations(monkeypatch)
    copies = []
    copy = durability.ctypes.string_at

    def copied(buffer, size):
        copies.append(size)
        return copy(buffer, size)

    monkeypatch.setattr(durability.ctypes, "string_at", copied)
    assert read(tmp_path / "modeled", 64 * 1024 * 1024) == payload
    assert allocations == [65_536]
    assert copies == [len(payload)]
    assert len(state.requests) == 2  # A short read is not treated as EOF.
    assert len(state.opens) == len(state.closes) == 1


@pytest.mark.parametrize("short_read", [1, 7, 65_535])
def test_short_reads_continue_to_actual_eof(tmp_path, monkeypatch, short_read):
    payload = bytes(range(256)) * 7
    state = peer(monkeypatch, payload, short_read=short_read)
    assert read(tmp_path / "modeled", len(payload) + 11) == payload
    assert state.offset == len(payload)
    assert len(state.opens) == len(state.closes) == 1


@pytest.mark.parametrize("size", [0, 1, 65_535, 65_536, 65_537, 1_048_576, 1_048_577])
def test_exact_bounds_binary_bytes_and_eof(tmp_path, monkeypatch, size):
    payload = (bytes(range(256)) * (size // 256 + 1))[:size]
    state = peer(monkeypatch, payload)
    assert read(tmp_path / "modeled", max(1, size)) == payload
    assert len(state.opens) == len(state.closes) == 1


@pytest.mark.parametrize("maximum", [1, 65_535, 65_536, 65_537, 1_048_576])
def test_growth_beyond_open_time_size_cannot_escape_byte_limit(
    tmp_path, monkeypatch, maximum
):
    # The modeled open succeeded, as if the file had initially fit its bound.
    # Every later read still counts actual bytes, including the overflow byte.
    state = peer(monkeypatch, b"x" * (maximum + 4))
    with pytest.raises(
        durability.PhysicalOnboardingDurabilityError, match="byte limit"
    ):
        read(tmp_path / "modeled", maximum)
    assert state.offset == maximum + 1
    assert len(state.closes) == 1


def test_large_file_uses_bounded_adaptive_growth_not_many_small_reads(
    tmp_path, monkeypatch
):
    payload = bytes(range(256)) * (20 * 1024 * 1024 // 256)
    state = peer(monkeypatch, payload)
    allocations = count_allocations(monkeypatch)
    assert read(tmp_path / "modeled", len(payload)) == payload
    assert allocations == [65_536, 131_072, 262_144, 524_288, 1_048_576]
    assert len(state.requests) <= 26
    assert sum(allocations) < 2 * 1024 * 1024
    assert max(state.requests) <= 1_048_576
    assert len(state.closes) == 1


@pytest.mark.parametrize("fault", ["io", "invalid_progress"])
@pytest.mark.parametrize("call", [1, 2])
def test_failure_does_not_return_partial_bytes_and_closes_handle(
    tmp_path, monkeypatch, fault, call
):
    state = peer(
        monkeypatch,
        b"x" * 100_000,
        failure_at=call if fault == "io" else None,
        invalid_at=call if fault == "invalid_progress" else None,
    )
    with pytest.raises(durability.PhysicalOnboardingDurabilityError):
        read(tmp_path / "modeled", 200_000)
    assert len(state.closes) == 1


@pytest.mark.parametrize("failure_at", [1, 2])
def test_allocation_failure_still_closes_handle(tmp_path, monkeypatch, failure_at):
    state = peer(monkeypatch, b"x" * 100_000)
    create = durability.ctypes.create_string_buffer
    calls = []

    def failed(size):
        calls.append(size)
        if len(calls) == failure_at:
            raise MemoryError("modeled buffer allocation failure")
        return create(size)

    monkeypatch.setattr(durability.ctypes, "create_string_buffer", failed)
    with pytest.raises(MemoryError):
        read(tmp_path / "modeled", 200_000)
    assert len(state.closes) == 1


@pytest.mark.skipif(os.name != "nt", reason="actual Windows file/handle path")
@pytest.mark.parametrize("size", [0, 1, 65_535, 65_536, 65_537, 1_048_576, 1_048_577])
def test_actual_windows_files_preserve_bytes_and_reject_overflow(tmp_path, size):
    path = tmp_path / "new-original.bin"
    payload = (bytes(range(256)) * (size // 256 + 1))[:size]
    path.write_bytes(payload)
    assert (
        durability.read_bounded_regular_file(path, maximum_bytes=max(size, 1))
        == payload
    )
    if size > 1:
        with pytest.raises(durability.PhysicalOnboardingDurabilityError):
            durability.read_bounded_regular_file(path, maximum_bytes=size - 1)
    assert path.read_bytes() == payload
