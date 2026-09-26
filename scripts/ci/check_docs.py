"""Check local file links in maintained entry docs, not archived lab records.

Checks this repository's issue-template URLs against local template files too.
Does not validate URL reachability, Markdown anchors, or visual rendering.
"""
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DOCS = (
    'README.md', 'PROJECT_STATUS.md', 'CONTRIBUTING.md', 'SUPPORT.md', 'SECURITY.md',
    'docs/README.md', 'docs/GETTING_STARTED.md', 'docs/RELEASING.md',
    'docs/releases/EXPERIMENTAL_PREVIEW_DRAFT.md',
    'docs/releases/CANDIDATE_DCD87DB.md',
    'docs/releases/BASELINE_2026-09-26.md',
    'docs/releases/NEWCOMER_CHECK_2026-09-26.md',
    'docs/releases/COMPATIBILITY_CONTENT_REVIEW_2026-09-26.md',
    'docs/HARDWARE_PROVENANCE.md',
    'docs/REPOSITORY_OPERATIONS.md',
    'docs/MAINTAINER_CHECKLIST.md',
    'docs/CI.md', 'docs/AUDIT_FIXTURE_REVIEW.md', 'software/README.md', 'software/ai/README.md',
    'software/ai/docs/README.md', 'assets/brand/README.md',
    'docs/brand/BRAND_GUIDE.md', 'docs/brand/NAMING_REVIEW.md',
    'docs/brand/MIGRATION_PLAN.md',
)


def issue_template_error(target: str, root: Path) -> str | None:
    """Check only this repository's template links, without network requests."""
    parsed = urlsplit(target)
    if (parsed.netloc.lower() != 'github.com'
            or parsed.path.rstrip('/') != '/j-webtek/robot-arm-build/issues/new'):
        return None
    templates = parse_qs(parsed.query, keep_blank_values=True).get('template')
    if templates is None:
        return None  # Generic new-issue link, not a template link.
    if len(templates) != 1 or not templates[0]:
        return f'ambiguous or empty issue template: {target}'
    name = templates[0]
    if name == 'BLANK_ISSUE':
        return None  # GitHub's built-in fallback, not a file.
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:md|yml|yaml)', name):
        return f'invalid issue template filename: {target}'
    if not (root / '.github' / 'ISSUE_TEMPLATE' / name).is_file():
        return f'missing issue template: {name}'
    return None


def main() -> None:
    errors = []
    for relative in DOCS:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f'Missing maintained document: {relative}')
            continue
        content = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
        for target in re.findall(r'\]\(([^)]+)\)', content):
            target = target.strip().strip('<>')
            parsed = urlsplit(target)
            template_error = issue_template_error(target, ROOT)
            if template_error:
                errors.append(f'{relative}: {template_error}')
            if parsed.scheme or target.startswith('#'):
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append(f'{relative}: missing local target {target}')
    for asset in ('tactevra-banner.svg', 'tactevra-mark.svg'):
        try:
            root = ET.parse(ROOT / 'assets/brand' / asset).getroot()
            if root.tag != '{http://www.w3.org/2000/svg}svg':
                errors.append(f'{asset}: expected SVG root')
        except (OSError, ET.ParseError) as exc:
            errors.append(f'{asset}: {exc}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: local file links in {len(DOCS)} maintained docs and two SVG assets')


if __name__ == '__main__':
    main()
