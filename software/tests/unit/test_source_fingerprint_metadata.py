"""Fresh metadata/content checks with unchanged fingerprint byte ordering."""
import hashlib
from pathlib import Path
import pytest

from rocell.application.wizard_diagnostic_coordinator import source_fingerprint, require_regular_path


def test_digest_unchanged_and_same_size_edits_are_not_cached(tmp_path):
    files = {'software/pyproject.toml':b'project', 'rocell.ps1':b'launcher',
             'software/src/rocell/a.py':b'first', 'software/config/c.json':b'{}'}
    for name, raw in files.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    expected = hashlib.sha256()
    for path in sorted(tmp_path/name for name in files):
        expected.update(path.relative_to(tmp_path).as_posix().encode()+b'\0')
        expected.update(path.read_bytes()+b'\0')
    original = source_fingerprint(tmp_path)
    assert original == expected.hexdigest()
    (tmp_path/'software/src/rocell/a.py').write_bytes(b'other')
    assert source_fingerprint(tmp_path) != original


def test_type_check_uses_current_lstat_without_extra_stat(tmp_path, monkeypatch):
    path = tmp_path/'file'
    path.write_bytes(b'original')
    original_stat = Path.stat
    following_calls = []
    def observed(self, *args, **kwargs):
        if kwargs.get('follow_symlinks', True): following_calls.append(self)
        return original_stat(self, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, 'stat', observed)
        assert require_regular_path(path, directory=False) == path
        with pytest.raises(Exception): require_regular_path(path, directory=True)
        with pytest.raises(Exception): require_regular_path(tmp_path, directory=False)
    assert following_calls == []
