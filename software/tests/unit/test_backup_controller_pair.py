import importlib.util
from pathlib import Path
import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'scripts/backup_controller_pair.py'
    spec = importlib.util.spec_from_file_location('backup_pair', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Reader:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = 0

    def read_flash(self, offset, size, callback):
        self.calls += 1
        assert offset == 0
        value = next(self.outputs)
        if isinstance(value, Exception):
            raise value
        if callback:
            callback(len(value), size)
        return value


def test_same_reader_two_reads_and_retained_report(tmp_path):
    reader = Reader([b'abcd', b'abcd'])
    events = []
    report = module().read_pair(reader, tmp_path, 4, lambda *event: events.append(event))
    assert reader.calls == 2 and report['matching']
    assert events == [(1, 4, 4), (2, 4, 4)]
    assert (tmp_path / 'flash-pair-a.bin').read_bytes() == b'abcd'


def test_mismatch_retains_both_without_retry(tmp_path):
    reader = Reader([b'abcd', b'efgh'])
    assert not module().read_pair(reader, tmp_path, 4)['matching']
    assert reader.calls == 2
    assert (tmp_path / 'flash-pair-b.bin').read_bytes() == b'efgh'


@pytest.mark.parametrize('first', [b'ab', OSError('read failed')])
def test_failed_first_read_stops(tmp_path, first):
    reader = Reader([first, b'abcd'])
    with pytest.raises((ValueError, OSError)):
        module().read_pair(reader, tmp_path, 4)
    assert reader.calls == 1


def test_existing_second_file_prevents_all_reads(tmp_path):
    (tmp_path / 'flash-pair-b.bin').write_bytes(b'preserve')
    reader = Reader([])
    with pytest.raises(FileExistsError):
        module().read_pair(reader, tmp_path, 4)
    assert reader.calls == 0
    assert (tmp_path / 'flash-pair-b.bin').read_bytes() == b'preserve'
