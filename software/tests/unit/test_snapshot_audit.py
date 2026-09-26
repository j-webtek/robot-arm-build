"""The reviewed-fixture mechanism must never hide changed or broader matches."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('snapshot_audit', ROOT / 'scripts/audit_github_snapshot.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
PATH = 'software/tests/unit/test_example.py'
LINE = b'password' + b'="' + b'synthetic-placeholder' + b'"'


def entry(**changes):
    return dict(dict(path=PATH, kind='credential-literal-review',
        line_sha256=hashlib.sha256(LINE).hexdigest(), expected_count=1,
        reason='Synthetic redaction test reviewed for scanner regression.'), **changes)


def test_unreviewed_match_fails_without_printing_value(capsys):
    assert audit.scan(PATH, LINE) == 1
    assert 'synthetic-placeholder' not in capsys.readouterr().out


@pytest.mark.parametrize('ending', [b'\n', b'\r\n', b''])
def test_exact_review_accepts_across_line_endings(ending, capsys):
    reviews = audit.ReviewedFixtures([entry()])
    assert audit.scan(PATH, LINE + ending, reviews) == 0
    assert reviews.stale_count() == 0
    assert 'synthetic-placeholder' not in capsys.readouterr().out


def test_changed_value_is_reported_and_old_exception_stales():
    reviews = audit.ReviewedFixtures([entry()])
    assert audit.scan(PATH, LINE.replace(b'placeholder', b'changed'), reviews) == 1
    assert reviews.stale_count() == 1


def test_other_file_and_archive_member_cannot_reuse_exception():
    for label in ('software/src/example.py', PATH + '!payload.txt'):
        reviews = audit.ReviewedFixtures([entry()])
        assert audit.scan(label, LINE, reviews) == 1


def test_additional_identical_match_fails():
    reviews = audit.ReviewedFixtures([entry()])
    assert audit.scan(PATH, LINE + b'\n' + LINE, reviews) == 1


def test_removed_match_stales():
    reviews = audit.ReviewedFixtures([entry()])
    assert audit.scan(PATH, b'no credentials here', reviews) == 0
    assert reviews.stale_count() == 1


@pytest.mark.parametrize('changes', [
    {'path': 'software/src/example.py'}, {'path': 'software/tests/unit/../test_x.py'},
    {'kind': 'github-token'}, {'expected_count': 2}, {'expected_count': True},
    {'line_sha256': 'bad'}, {'reason': ''}, {'extra': True},
])
def test_invalid_or_broad_exception_rejected(changes):
    row = entry()
    row.update(changes)
    with pytest.raises(ValueError):
        audit.ReviewedFixtures([row])


def test_duplicate_exception_rejected():
    with pytest.raises(ValueError):
        audit.ReviewedFixtures([entry(), entry()])


def test_token_pattern_is_never_exempted(capsys):
    reviews = audit.ReviewedFixtures([entry()])
    token = b'ghp_' + b'x' * 36
    assert audit.scan(PATH, token, reviews) == 1
    assert token.decode() not in capsys.readouterr().out


def test_missing_manifest_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(audit, 'ROOT', tmp_path)
    assert audit.main() is True
    assert 'invalid or missing' in capsys.readouterr().out
