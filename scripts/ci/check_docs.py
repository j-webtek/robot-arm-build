"""Check local file links in maintained entry docs, not archived lab records.

Does not validate URL reachability, Markdown anchors, or visual rendering.
"""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DOCS = (
    'README.md', 'PROJECT_STATUS.md', 'CONTRIBUTING.md', 'SUPPORT.md', 'SECURITY.md',
    'docs/README.md', 'docs/GETTING_STARTED.md', 'docs/RELEASING.md',
    'docs/releases/EXPERIMENTAL_PREVIEW_DRAFT.md',
    'docs/releases/BASELINE_2026-09-26.md',
    'docs/CI.md', 'docs/AUDIT_FIXTURE_REVIEW.md', 'software/README.md', 'software/ai/README.md',
    'software/ai/docs/README.md', 'assets/brand/README.md',
    'docs/brand/BRAND_GUIDE.md', 'docs/brand/NAMING_REVIEW.md',
    'docs/brand/MIGRATION_PLAN.md',
)


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
