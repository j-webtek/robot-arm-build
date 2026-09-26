"""Hardware-free tests for the CI summary renderer."""
import unittest

from environment_report import render


class EnvironmentReportTests(unittest.TestCase):
    def test_versions_are_sorted_and_scope_is_explicit(self):
        report = render('3.10.10', 'Windows', [('pytest', '9.1.1'), ('Pillow', '12.3.0')])
        self.assertIn('Python: 3.10.10; OS: Windows.', report)
        self.assertLess(report.index('| Pillow'), report.index('| pytest'))
        self.assertIn('not a lockfile', report)
        self.assertIn('not qualified', report)

    def test_metadata_cannot_inject_table_rows_or_html(self):
        report = render('3.12', 'Linux', [('a|b\n<script>', '1\r2')])
        self.assertIn('a&#124;b &lt;script&gt;', report)
        self.assertIn('| 1 2 |', report)
        self.assertNotIn('<script>', report)

    def test_empty_inventory_does_not_invent_optional_packages(self):
        report = render('3.12', 'Linux', [])
        self.assertNotIn('opencv', report)
        self.assertNotIn('passed', report)


if __name__ == '__main__':
    unittest.main()
