"""Validate content-addressed public records and status freshness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = Path("assets/media/verification_receipt.json")
EXPECTED_MEDIA = {
    "assets/media/tactevra-overview.mp4",
    "assets/media/tactevra-overview-poster.jpg",
    "assets/media/tactevra-overview.en.vtt",
    "assets/media/tactevra-overview.chapters.vtt",
    "assets/media/tactevra-social-preview.jpg",
}
PAGES_WORKFLOW = Path(".github/workflows/pages.yml")
CONFIGURE_PAGES_V6_SHA = "45bfe0192ca1faeb007ade9deae92b16b8254a0d"
DEPLOY_PAGES_V5_SHA = "368f82528645a54fb793d4d04e342629a3f51346"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file(root: Path, value: object, label: str) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    if not isinstance(value, str) or not value:
        return None, [f"{label}: path must be a non-empty string"]
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None, [f"{label}: unsafe repository-relative path: {value!r}"]
    path = root / relative
    if path.is_symlink() or not path.is_file():
        errors.append(f"{label}: expected a regular non-symlink file: {value}")
    return path, errors


def identity_errors(root: Path, record: object, label: str) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label}: expected an object"]
    path, errors = safe_file(root, record.get("path"), label)
    if errors or path is None:
        return errors
    expected_size = record.get("size_bytes")
    if not isinstance(expected_size, int) or expected_size < 0:
        errors.append(f"{label}: size_bytes must be a non-negative integer")
    elif path.stat().st_size != expected_size:
        errors.append(
            f"{label}: size drift for {record['path']}: "
            f"expected {expected_size}, observed {path.stat().st_size}"
        )
    expected_hash = record.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append(f"{label}: sha256 must be 64 lowercase hexadecimal characters")
    else:
        observed_hash = sha256(path)
        if observed_hash != expected_hash:
            errors.append(
                f"{label}: SHA-256 drift for {record['path']}: "
                f"expected {expected_hash}, observed {observed_hash}"
            )
    return errors


def media_errors(root: Path) -> list[str]:
    receipt_path = root / RECEIPT
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"{RECEIPT}: cannot read strict JSON: {exc}"]

    errors: list[str] = []
    if receipt.get("schema") != "tactevra.published-media-verification.v1":
        errors.append(f"{RECEIPT}: unsupported schema")
    if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("asset_revision_commit", ""))):
        errors.append(f"{RECEIPT}: asset_revision_commit must be a full lowercase SHA")
    source_pull_request = receipt.get("source_pull_request")
    if not isinstance(source_pull_request, str) or not re.fullmatch(
        r"https://github\.com/j-webtek/tactevra/pull/[1-9][0-9]*",
        source_pull_request,
    ):
        errors.append(f"{RECEIPT}: source_pull_request must be a canonical Tactevra PR URL")

    errors.extend(identity_errors(root, receipt.get("authority"), "authority"))
    outputs = receipt.get("outputs")
    if not isinstance(outputs, list):
        errors.append(f"{RECEIPT}: outputs must be an array")
    else:
        paths = [entry.get("path") for entry in outputs if isinstance(entry, dict)]
        if len(paths) != len(set(paths)):
            errors.append(f"{RECEIPT}: duplicate output paths")
        if set(paths) != EXPECTED_MEDIA:
            errors.append(
                f"{RECEIPT}: outputs must identify exactly {sorted(EXPECTED_MEDIA)}"
            )
        for index, entry in enumerate(outputs):
            errors.extend(identity_errors(root, entry, f"output[{index}]"))

    limitations = receipt.get("limitations")
    limitation_text = "\n".join(limitations) if isinstance(limitations, list) else ""
    if "https://github.com/j-webtek/tactevra/issues/88" not in limitation_text:
        errors.append(f"{RECEIPT}: limitations must retain the issue #88 disposition")
    if "not physical" not in limitation_text.lower():
        errors.append(f"{RECEIPT}: limitations must deny physical qualification")
    return errors


def status_errors(root: Path) -> list[str]:
    status = (root / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    ledger = (root / "software/ai/docs/EVIDENCE_LEDGER.md").read_text(encoding="utf-8")
    ledger_numbers = [int(value) for value in re.findall(
        r"^### E-\d{8}-ARM-(\d{3})\b", ledger, flags=re.MULTILINE
    )]
    status_match = re.search(
        r"^Reviewed .+ through the ARM-(\d{3})\b", status, flags=re.MULTILINE
    )
    errors: list[str] = []
    if not ledger_numbers:
        errors.append("software/ai/docs/EVIDENCE_LEDGER.md: no ARM record found")
    if not status_match:
        errors.append("PROJECT_STATUS.md: missing reviewed-through ARM marker")
    if ledger_numbers and status_match and int(status_match.group(1)) != max(ledger_numbers):
        errors.append(
            "PROJECT_STATUS.md: reviewed-through ARM marker is stale: "
            f"expected ARM-{max(ledger_numbers):03d}, observed ARM-{int(status_match.group(1)):03d}"
        )
    closed_phrase = (
        "[Issue #45](https://github.com/j-webtek/tactevra/issues/45) was closed"
    )
    if closed_phrase not in status:
        errors.append("PROJECT_STATUS.md: issue #45 must be described as closed")
    return errors


def pages_workflow_errors(root: Path) -> list[str]:
    """Keep the public deployment on the reviewed hosted/runtime baseline."""
    path = root / PAGES_WORKFLOW
    try:
        workflow = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{PAGES_WORKFLOW}: cannot read workflow: {exc}"]
    errors: list[str] = []
    if workflow.count("runs-on: ubuntu-24.04") != 2:
        errors.append(f"{PAGES_WORKFLOW}: both jobs must use ubuntu-24.04")
    if "runs-on: ubuntu-latest" in workflow:
        errors.append(f"{PAGES_WORKFLOW}: ubuntu-latest is not an accepted Pages runner")
    expected_action = f"actions/configure-pages@{CONFIGURE_PAGES_V6_SHA} # v6.0.0"
    if workflow.count(expected_action) != 1:
        errors.append(
            f"{PAGES_WORKFLOW}: configure-pages must use the reviewed v6.0.0 SHA"
        )
    expected_deploy_action = f"actions/deploy-pages@{DEPLOY_PAGES_V5_SHA} # v5.0.1"
    if workflow.count(expected_deploy_action) != 1:
        errors.append(
            f"{PAGES_WORKFLOW}: deploy-pages must use the reviewed v5.0.1 SHA"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--media-only", action="store_true",
        help="check published media identities without the project-status ledger",
    )
    args = parser.parse_args()
    errors = media_errors(ROOT)
    errors.extend(pages_workflow_errors(ROOT))
    if not args.media_only:
        errors.extend(status_errors(ROOT))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    scope = "published media and Pages runtime" if args.media_only else "public records"
    print(f"PASS: {scope} identities and freshness checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
