"""Offline regression checks for public issue-template routing."""
import json
from pathlib import Path
import tempfile
import unittest

from check_docs import (PUBLIC_ROUTES, PUBLIC_TITLES, issue_template_error,
                        public_entry_errors, readiness_dashboard_errors,
                        without_fences)


BASE = 'https://github.com/j-webtek/tactevra/issues/new'


class IssueTemplateLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.templates = self.root / '.github' / 'ISSUE_TEMPLATE'
        self.templates.mkdir(parents=True)
        (self.templates / 'bug_report.yml').touch()
        (self.templates / 'feature_request.md').touch()

    def test_existing_yaml_and_markdown(self):
        for name in ('bug_report.yml', 'feature_request.md'):
            with self.subTest(name=name):
                self.assertIsNone(issue_template_error(f'{BASE}?template={name}', self.root))

    def test_removed_template_is_reported(self):
        self.assertEqual(issue_template_error(f'{BASE}?template=bug_report.md', self.root),
                         'missing issue template: bug_report.md')

    def test_blank_and_generic_routes_are_not_files(self):
        for suffix in ('', '?title=Example', '?template=BLANK_ISSUE', '/choose'):
            self.assertIsNone(issue_template_error(BASE + suffix, self.root))

    def test_other_repository_or_host_is_out_of_scope(self):
        for url in ('https://github.com/other/repo/issues/new?template=missing.yml',
                    'https://example.com/j-webtek/robot-arm-build/issues/new?template=x.yml'):
            self.assertIsNone(issue_template_error(url, self.root))

    def test_query_decoding_and_extra_parameters(self):
        self.assertIsNone(issue_template_error(
            BASE + '/?labels=bug&template=bug%5Freport.yml#section', self.root))

    def test_bad_or_ambiguous_names_are_rejected(self):
        for value in ('', '../bug_report.yml', '%2Ftmp%2Fx.yml', 'a%5Cb.yml',
                      'bug_report.yml&template=feature_request.md'):
            with self.subTest(value=value):
                self.assertIsNotNone(issue_template_error(BASE + '?template=' + value, self.root))

    def test_directory_is_not_a_template(self):
        (self.templates / 'directory.yml').mkdir()
        self.assertEqual(issue_template_error(BASE + '?template=directory.yml', self.root),
                         'missing issue template: directory.yml')


class PublicEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.relative = 'SUPPORT.md'
        self.content = '# ' + PUBLIC_TITLES[self.relative] + '\n'
        for target, heading in PUBLIC_ROUTES[self.relative]:
            self.content += f'[Readable label]({target})\n'
            destination = self.root / target.split('#')[0]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(f'## {heading or "Page"}\n', encoding='utf-8')

    def errors(self, content=None):
        return public_entry_errors(self.relative,
                                   self.content if content is None else content, self.root)

    def test_valid_routes_and_legacy_identifiers(self):
        self.assertEqual(self.errors(self.content + '\nFormerly RoCell; `rocell` stays.\n'), [])

    def test_brand_title_drift(self):
        self.assertIn('expected one public title', self.errors(
            self.content.replace('Tactevra', 'RoCell'))[0])

    def test_duplicate_title(self):
        self.assertTrue(self.errors(self.content + '# Another title\n'))

    def test_missing_private_route(self):
        self.assertIn('missing required navigation link: SECURITY.md',
                      self.errors(self.content.replace('[Readable label](SECURITY.md)', '')))

    def test_missing_destination(self):
        (self.root / 'SECURITY.md').unlink()
        self.assertIn('missing navigation destination: SECURITY.md', self.errors())

    def test_renamed_anchor_heading(self):
        (self.root / 'CONTRIBUTING.md').write_text('## Sharing exports\n', encoding='utf-8')
        self.assertTrue(any('Export sharing' in e for e in self.errors()))

    def test_duplicate_anchor_heading(self):
        (self.root / 'CONTRIBUTING.md').write_text(
            '## Export sharing\n## Export sharing\n', encoding='utf-8')
        self.assertTrue(any('Export sharing' in e for e in self.errors()))

    def test_fenced_heading_does_not_satisfy_anchor(self):
        (self.root / 'CONTRIBUTING.md').write_text(
            '~~~md\n## Export sharing\n~~~\n', encoding='utf-8')
        self.assertTrue(any('Export sharing' in e for e in self.errors()))

    def test_fenced_page_does_not_satisfy_contract(self):
        for fence in ('```', '~~~~'):
            with self.subTest(fence=fence):
                self.assertTrue(self.errors(f'{fence}md\n{self.content}{fence}\n'))

    def test_unlisted_historical_page_is_not_rebranded(self):
        self.assertEqual(public_entry_errors('history.md', '# RoCell\n', self.root), [])

    def test_fence_length_and_kind(self):
        self.assertEqual(without_fences('before\n````md\n```\n~~~\nhidden\n````\nafter'),
                         'before\nafter')


class ReadinessDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.github').mkdir()

    def write_registry(self, blockers):
        (self.root / '.github' / 'release-readiness.json').write_text(
            json.dumps({'blockers': blockers}), encoding='utf-8')

    def test_open_count_and_routes_match(self):
        issue = 'https://github.com/j-webtek/tactevra/issues/167'
        self.write_registry([{'status': 'open', 'issue': issue}])
        content = f'The registry currently has one open blocker.\nSee {issue}.\n'
        self.assertEqual(readiness_dashboard_errors(content, self.root), [])

    def test_count_drift_is_reported(self):
        issue = 'https://github.com/j-webtek/tactevra/issues/167'
        self.write_registry([{'status': 'open', 'issue': issue}])
        errors = readiness_dashboard_errors(
            f'The registry currently has two open blockers.\nSee {issue}.\n', self.root)
        self.assertTrue(any('expected public open-blocker count: one' in e
                            for e in errors))

    def test_missing_open_issue_route_is_reported(self):
        issue = 'https://github.com/j-webtek/tactevra/issues/167'
        self.write_registry([{'status': 'open', 'issue': issue}])
        errors = readiness_dashboard_errors(
            'The registry currently has one open blocker.\n', self.root)
        self.assertTrue(any(issue in e for e in errors))


if __name__ == '__main__':
    unittest.main()
