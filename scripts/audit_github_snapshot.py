"""Read-only pre-upload audit. Prints locations, never matching secret values.

Heuristic review only, not a guarantee that a snapshot contains no private data.
Includes text inside ZIP/3MF packages. Run from any directory in this checkout.
"""
import re
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "aws-access-id": rb"AKIA[A-Z0-9]{16}",
    "credential-literal-review": rb"(?i)(?:password|passwd|sta_pwd|wifi_pwd|api_key|auth_token|signing_key|secret)\s*[\"']?\s*[:=]\s*[\"']([^\"'\r\n]{5,})",
}


class ReviewedFixtures:
    """Exact-path, full-line-content exceptions for reviewed synthetic tests only."""

    def __init__(self, entries):
        self.expected = {}
        self.used = {}
        if not isinstance(entries, list):
            raise ValueError('Invalid fixture review list')
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {
                'path', 'kind', 'line_sha256', 'expected_count', 'reason'
            }:
                raise ValueError('Invalid fixture review fields')
            path = entry['path']
            digest = entry['line_sha256']
            if (not isinstance(path, str) or not re.fullmatch(
                    r'software/tests/unit/test_[a-z0-9_]+\.py', path)
                    or entry['kind'] != 'credential-literal-review'
                    or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
                    or type(entry['expected_count']) is not int or entry['expected_count'] != 1
                    or not isinstance(entry['reason'], str) or not entry['reason'].strip()):
                raise ValueError('Invalid fixture review scope')
            key = (path, entry['kind'], digest)
            if key in self.expected:
                raise ValueError('Duplicate fixture review')
            self.expected[key] = 1
            self.used[key] = 0

    def accept(self, label, kind, line_bytes):
        key = (label, kind, hashlib.sha256(line_bytes).hexdigest())
        if key in self.expected and self.used[key] < self.expected[key]:
            self.used[key] += 1
            return True
        return False

    def stale_count(self):
        count = 0
        for key, expected in self.expected.items():
            if self.used[key] != expected:
                print(f'REVIEW stale fixture exception: {key[0]} ({key[2][:12]})')
                count += 1
        return count


def scan(label, data, reviews=None):
    if b"\x00" in data[:8192]:
        return 0
    count = 0
    for kind, pattern in PATTERNS.items():
        for match in re.finditer(pattern, data):
            line = data.count(b"\n", 0, match.start()) + 1
            # Normalize only the line ending so Windows/Linux checkouts agree.
            line_bytes = data.split(b'\n')[line - 1].removesuffix(b'\r')
            if reviews is not None and reviews.accept(label, kind, line_bytes):
                print(f'REVIEWED synthetic fixture {kind}: {label}:{line}')
                continue
            print(f"REVIEW {kind}: {label}:{line}")
            count += 1
    return count


def main():
    try:
        reviews = ReviewedFixtures(json.loads(
            (ROOT / 'scripts/audit_fixture_reviews.json').read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        print('REVIEW invalid or missing fixture review manifest')
        return True
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    files = sorted(set(p.decode("utf-8") for p in raw.split(b"\0") if p))
    count = 0
    total = 0
    for name in files:
        path = ROOT / name
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if size > 100 * 1024 * 1024:
            print(f"REVIEW large file: {name} ({size} bytes)")
            count += 1
        if path.suffix.lower() in {".zip", ".3mf"}:
            with zipfile.ZipFile(path) as archive:
                for entry in archive.infolist():
                    if not entry.is_dir() and entry.file_size < 10 * 1024 * 1024:
                        count += scan(f"{name}!{entry.filename}", archive.read(entry), reviews)
        elif size < 10 * 1024 * 1024:
            count += scan(name, path.read_bytes(), reviews)
    count += reviews.stale_count()
    reviewed = sum(reviews.used.values())
    print(f"Audited {len(files)} paths; {total / 1024**2:.1f} MiB; "
          f"{count} unresolved review findings; {reviewed} reviewed synthetic fixtures.")
    return bool(count)


if __name__ == "__main__":
    raise SystemExit(main())
