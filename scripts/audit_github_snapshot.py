"""Read-only pre-upload audit. Prints locations, never matching secret values.

Heuristic review only, not a guarantee that a snapshot contains no private data.
Includes text inside ZIP/3MF packages. Run from any directory in this checkout.
"""
import re
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


def scan(label, data):
    if b"\x00" in data[:8192]:
        return 0
    count = 0
    for kind, pattern in PATTERNS.items():
        for match in re.finditer(pattern, data):
            line = data.count(b"\n", 0, match.start()) + 1
            print(f"REVIEW {kind}: {label}:{line}")
            count += 1
    return count


def main():
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
                        count += scan(f"{name}!{entry.filename}", archive.read(entry))
        elif size < 10 * 1024 * 1024:
            count += scan(name, path.read_bytes())
    print(f"Audited {len(files)} paths; {total / 1024**2:.1f} MiB; {count} review findings.")
    return bool(count)


if __name__ == "__main__":
    raise SystemExit(main())
