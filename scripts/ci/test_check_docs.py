"""Offline regression checks for public issue-template routing."""
from pathlib import Path
import tempfile
import unittest

from check_docs import issue_template_error


BASE = 'https://github.com/j-webtek/robot-arm-build/issues/new'


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


if __name__ == '__main__':
    unittest.main()
