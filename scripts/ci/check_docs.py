"""Check local file links in maintained entry docs, not archived lab records.

Checks this repository's issue-template URLs against local template files too.
Also enforces explicit public-page titles and required navigation routes.
Only explicitly listed plain-heading anchors are checked; this is not a general
Markdown parser, URL reachability check, or visual review.
"""
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DOCS = (
    'README.md', 'PROJECT_STATUS.md', 'CONTRIBUTING.md', 'SUPPORT.md', 'SECURITY.md',
    'CODE_OF_CONDUCT.md',
    'docs/README.md', 'docs/GETTING_STARTED.md', 'docs/RELEASING.md',
    'docs/SYSTEM_OVERVIEW.md', 'docs/GLOSSARY.md',
    'docs/HARDWARE_BUILD_GUIDE.md',
    'docs/DOCUMENTATION_STANDARD.md',
    'docs/EVIDENCE_RETENTION.md',
    'docs/releases/EXPERIMENTAL_PREVIEW_DRAFT.md',
    'docs/releases/CANDIDATE_DCD87DB.md',
    'docs/releases/BASELINE_2026-09-26.md',
    'docs/releases/NEWCOMER_CHECK_2026-09-26.md',
    'docs/releases/COMPATIBILITY_CONTENT_REVIEW_2026-09-26.md',
    'docs/HARDWARE_PROVENANCE.md',
    'docs/REPOSITORY_OPERATIONS.md',
    'docs/MAINTAINER_CHECKLIST.md',
    'docs/CI.md', 'docs/AUDIT_FIXTURE_REVIEW.md', 'software/README.md',
    'software/RUNTIME_IMPLEMENTATION_HISTORY.md', 'software/ai/README.md',
    'software/ai/docs/README.md', 'assets/brand/README.md',
    'software/ai/docs/CONTRACT.md',
    'software/ai/docs/SHARED_AI_ARM_WORKPLAN.md',
    'software/ai/docs/EVIDENCE_LEDGER.md',
    'software/docs/ARCHITECTURE.md',
    'docs/brand/BRAND_GUIDE.md', 'docs/brand/NAMING_REVIEW.md',
    'docs/brand/MIGRATION_PLAN.md',
)

# Deliberately narrow: compatibility identifiers and historical records are not
# subject to brand-name replacement. Update this contract with intentional UI changes.
PUBLIC_TITLES = {
    'README.md': 'Tactevra',
    'PROJECT_STATUS.md': 'Tactevra project status',
    'CONTRIBUTING.md': 'Contributing to Tactevra',
    'SUPPORT.md': 'Getting help with Tactevra',
    'SECURITY.md': 'Tactevra security reporting',
    'CODE_OF_CONDUCT.md': 'Tactevra community code of conduct',
    'docs/README.md': 'Tactevra documentation',
    'docs/GETTING_STARTED.md': 'Getting started with Tactevra',
    'docs/SYSTEM_OVERVIEW.md': 'Tactevra system overview',
    'docs/GLOSSARY.md': 'Tactevra glossary',
    'docs/HARDWARE_BUILD_GUIDE.md': 'Building the Tactevra RC03 workcell',
    'docs/DOCUMENTATION_STANDARD.md': 'Tactevra documentation standard',
    'software/README.md': 'Tactevra Runtime',
    'software/RUNTIME_IMPLEMENTATION_HISTORY.md': 'Tactevra Runtime implementation history',
    'software/ai/README.md': 'Tactevra AI',
    'software/ai/docs/CONTRACT.md': 'AI-to-Tactevra Runtime integration contract',
    'software/ai/docs/SHARED_AI_ARM_WORKPLAN.md': 'Shared AI-to-arm workplan',
    'software/ai/docs/EVIDENCE_LEDGER.md': 'Tactevra AI/arm evidence ledger',
    'software/docs/ARCHITECTURE.md': 'Tactevra Runtime software architecture',
}

REQUIRED_PHRASES = {
    'docs/SYSTEM_OVERVIEW.md': (
        '**Document status:** Current overview',
        '**Authority:** Explanatory; it does not authorize hardware operation',
    ),
    'docs/GLOSSARY.md': ('**Document status:** Current reference',),
    'docs/HARDWARE_BUILD_GUIDE.md': (
        '**Document status:** Current builder guide',
        '**Authority:** Explanatory; controlled RC03 records determine print and build eligibility',
        '| Powered robot motion | **Not authorized** |',
    ),
    'docs/DOCUMENTATION_STANDARD.md': ('**Document status:** Current policy',),
    'software/RUNTIME_IMPLEMENTATION_HISTORY.md': (
        '**Document status:** Historical evidence index',
        '**Authority:** Historical context only; it does not authorize hardware operation',
    ),
    'software/README.md': (
        '**Document status:** Current software reference',
        '**Authority:** Explanatory; this page does not authorize hardware operation',
    ),
    'software/ai/README.md': (
        '**Document status:** Current research and integration reference',
        '**Authority:** Research guidance only; this page grants no controller authority',
    ),
    'software/ai/docs/SHARED_AI_ARM_WORKPLAN.md': (
        '**Status:** active coordination document',
        '[Tactevra AI/arm evidence ledger](EVIDENCE_LEDGER.md)',
    ),
    'software/ai/docs/EVIDENCE_LEDGER.md': (
        '**Document status:** Append-only evidence record',
        'duplicate `E-20260926-INT-001` identifier',
    ),
    'docs/releases/EXPERIMENTAL_PREVIEW_DRAFT.md': (
        '**Status:** Superseded preparation record; unpublished',
        'https://github.com/j-webtek/tactevra/issues/57',
    ),
    'docs/releases/CANDIDATE_DCD87DB.md': (
        '**Disposition: SUPERSEDED WITHOUT PUBLICATION.**',
    ),
}

# (relative Markdown destination, optional exact plain ATX heading).
PUBLIC_ROUTES = {
    'README.md': (
        ('docs/GETTING_STARTED.md#install-the-software', 'Install the software'),
        ('docs/SYSTEM_OVERVIEW.md', None),
        ('docs/HARDWARE_BUILD_GUIDE.md', None),
        ('PROJECT_STATUS.md', None), ('docs/README.md', None),
        ('SUPPORT.md', None), ('SECURITY.md', None),
    ),
    'docs/README.md': (
        ('GETTING_STARTED.md', None), ('../PROJECT_STATUS.md', None),
        ('SYSTEM_OVERVIEW.md', None), ('GLOSSARY.md', None),
        ('HARDWARE_BUILD_GUIDE.md', None),
        ('../SUPPORT.md', None), ('../CONTRIBUTING.md', None),
        ('../SECURITY.md', None), ('../CODE_OF_CONDUCT.md', None),
    ),
    'SUPPORT.md': (
        ('docs/GETTING_STARTED.md#what-you-can-do-today', 'What you can do today'),
        ('SECURITY.md', None), ('CODE_OF_CONDUCT.md', None),
        ('CONTRIBUTING.md#export-sharing', 'Export sharing'),
    ),
    'docs/GETTING_STARTED.md': (
        ('../PROJECT_STATUS.md', None), ('../CONTRIBUTING.md', None),
    ),
    'docs/HARDWARE_BUILD_GUIDE.md': (
        ('../PROJECT_STATUS.md', None), ('../SUPPORT.md', None),
        ('../CONTRIBUTING.md', None),
        ('../active-project/RoCell_v0_3/README_FIRST.md', None),
        ('../active-project/RoCell_v0_3/PRINT_READINESS.md', None),
        ('../active-project/RoCell_v0_3/PREHARDWARE_READINESS.md', None),
        ('../active-project/RoCell_v0_3/BUILD_TRACKER.md', None),
        ('../active-project/RoCell_v0_3/BUILD_BY_STEP/README.md', None),
    ),
}


def without_fences(content: str) -> str:
    """Exclude backtick/tilde fenced examples from the small entry-doc checks."""
    lines = []
    fence = None
    for line in content.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if (marker and marker[1][0] == fence[0]
                    and len(marker[1]) >= len(fence) and not marker[2].strip()):
                fence = None
            continue
        if marker:
            fence = marker[1]
        else:
            lines.append(line)
    return '\n'.join(lines)


def public_entry_errors(relative: str, content: str, root: Path) -> list[str]:
    """Enforce the reviewed entry-page contract without inspecting runtime code."""
    content = without_fences(content)
    errors = []
    title = PUBLIC_TITLES.get(relative)
    headings = re.findall(r'^# +(.+?)\s*$', content, flags=re.M)
    if title and headings != [title]:
        errors.append(f'expected one public title: # {title}')
    for phrase in REQUIRED_PHRASES.get(relative, ()):
        if phrase not in content:
            errors.append(f'missing required status context: {phrase}')
    links = {target.strip().strip('<>')
             for target in re.findall(r'\]\(([^)]+)\)', content)}
    for target, heading in PUBLIC_ROUTES.get(relative, ()):
        if target not in links:
            errors.append(f'missing required navigation link: {target}')
        destination = root / Path(relative).parent / urlsplit(target).path
        if not destination.is_file():
            errors.append(f'missing navigation destination: {target}')
            continue
        if heading:
            # Only plain headings explicitly listed above; no inferred GitHub slugger.
            fragment = urlsplit(target).fragment
            if fragment != heading.lower().replace(' ', '-'):
                errors.append(f'invalid navigation anchor contract: {target}')
            headings_at_target = re.findall(
                r'^#{1,6} +(.+?)\s*$',
                without_fences(destination.read_text(encoding='utf-8')), flags=re.M)
            if headings_at_target.count(heading) != 1:
                errors.append(f'expected one navigation heading "{heading}" in {target}')
    return errors


def issue_template_error(target: str, root: Path) -> str | None:
    """Check only this repository's template links, without network requests."""
    parsed = urlsplit(target)
    if (parsed.netloc.lower() != 'github.com'
            or parsed.path.rstrip('/') != '/j-webtek/tactevra/issues/new'):
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
        raw_content = path.read_text(encoding='utf-8')
        if 'j-webtek/robot-arm-build' in without_fences(raw_content):
            errors.append(
                f'{relative}: stale canonical repository reference; use j-webtek/tactevra')
        errors.extend(f'{relative}: {error}'
                      for error in public_entry_errors(relative, raw_content, ROOT))
        content = without_fences(raw_content)
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
    print(f'PASS: local file links in {len(DOCS)} maintained docs, '
          f'{len(PUBLIC_TITLES)} public titles, required navigation, and two SVG assets')


if __name__ == '__main__':
    main()
