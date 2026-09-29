import unittest

from build_repository_operations_report import collect, render


class RepositoryOperationsReportTests(unittest.TestCase):
    def test_report_is_bounded_and_identifies_current_blocker(self):
        data = collect()
        output = render(data)
        self.assertEqual(len(data["open_release_blockers"]), 1)
        self.assertIn("issues/88", data["open_release_blockers"][0])
        self.assertIn("Operational summary only", output)
        self.assertIn("Shared-contract path patterns", output)


if __name__ == "__main__":
    unittest.main()
