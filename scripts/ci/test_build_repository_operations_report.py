import unittest

from build_repository_operations_report import collect, render


class RepositoryOperationsReportTests(unittest.TestCase):
    def test_report_is_bounded_and_identifies_cleared_registry(self):
        data = collect()
        output = render(data)
        self.assertEqual(data["open_release_blockers"], [])
        self.assertEqual(len(data["cleared_release_blockers"]), 4)
        self.assertIn("Open blocker links: None", output)
        self.assertIn("Operational summary only", output)
        self.assertIn("Shared-contract path patterns", output)


if __name__ == "__main__":
    unittest.main()
