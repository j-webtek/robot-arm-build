"""Windows sharing investigation; all handles/mutations target owned tmp_path.

No production guards are modified or invoked against workspace ancestors.
These local NTFS observations are not power-loss qualification.
"""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from typing import Iterator

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Win32 sharing investigation")


@contextmanager
def _guard(paths: tuple[Path, ...], *, access: int, share: int) -> Iterator[None]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handles = []
    try:
        for path in paths:
            handle = kernel.CreateFileW(
                str(path), access, share, None, 3, 0x02200000, None
            )
            if handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            assert kernel.CloseHandle(handle), ctypes.get_last_error()


def _new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _rename_result(source: Path, target: Path, tmp_root: Path) -> str:
    assert source.is_relative_to(tmp_root) and target.is_relative_to(tmp_root)
    try:
        source.rename(target)
    except OSError as error:
        return "blocked:" + str(error.winerror)
    # Successful control probes are restored under the same explicit tmp root.
    target.rename(source)
    return "allowed"


def test_access_share_matrix_and_publication_operations(tmp_path: Path) -> None:
    matrix = []
    for access in (0x80, 0x1, 0x80000000):
        for share in (0x1, 0x3, 0x5, 0x7):
            case = tmp_path / f"case-{access:x}-{share:x}"
            parent = case / "parent"
            leaf = parent / "dataset"
            leaf.mkdir(parents=True)
            _new(leaf / "manifest.pending", b'{"diagnostic":true}\n')
            row = {"access": hex(access), "share": hex(share)}
            with _guard((parent, leaf), access=access, share=share):
                row["leaf_rename"] = _rename_result(
                    leaf, parent / "moved-leaf", tmp_path
                )
                row["ancestor_rename"] = _rename_result(
                    parent, case / "moved-parent", tmp_path
                )
                try:
                    os.link(
                        leaf / "manifest.pending",
                        leaf / "manifest.link",
                        follow_symlinks=False,
                    )
                    row["hardlink"] = "allowed"
                except OSError as error:
                    row["hardlink"] = "blocked:" + str(error.winerror)
                try:
                    _new(leaf / "manifest.json", b'{"diagnostic":true}\n')
                    row["exclusive_final_write_fsync"] = "allowed"
                except OSError as error:
                    row["exclusive_final_write_fsync"] = "blocked:" + str(
                        error.winerror
                    )
                try:
                    (leaf / "manifest.pending").unlink()
                    row["pending_unlink"] = "allowed"
                except OSError as error:
                    row["pending_unlink"] = "blocked:" + str(error.winerror)
            matrix.append(row)
    print(json.dumps(matrix, indent=2))
    strict = next(
        row for row in matrix if row["access"] == "0x80000000" and row["share"] == "0x1"
    )
    assert strict["leaf_rename"].startswith("blocked:")
    assert strict["ancestor_rename"].startswith("blocked:")
    assert strict["exclusive_final_write_fsync"] == "allowed"
    assert strict["pending_unlink"] == "allowed"


@pytest.mark.parametrize("stop_at", ["pending", "final", "commit"])
def test_copy_then_remove_sentinel_preserves_partial_marker(
    tmp_path: Path, stop_at: str
) -> None:
    parent = tmp_path / "owned-parent"
    dataset = parent / "dataset"
    dataset.mkdir(parents=True)
    pending, final = dataset / "manifest.pending", dataset / "manifest.json"
    payload = b'{"unqualified_diagnostic_only":true}\n'
    with _guard((parent, dataset), access=0x80000000, share=0x1):
        _new(pending, payload)
        if stop_at != "pending":
            _new(final, payload)
        if stop_at == "commit":
            pending.unlink()
        # Same invariant as strict dataset inventory: a pending sentinel makes
        # even a complete-looking final payload an incomplete publication.
        committed = {entry.name for entry in dataset.iterdir()} == {"manifest.json"}
        assert committed == (stop_at == "commit")
        if final.exists():
            assert final.read_bytes() == payload
            assert final.stat().st_nlink == 1
            with pytest.raises(FileExistsError):
                _new(final, b"replacement forbidden")
            assert final.read_bytes() == payload
