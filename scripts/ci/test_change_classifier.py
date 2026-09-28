import unittest

from change_classifier import classify_paths, load_policy


class ChangeClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()

    def test_docs_change_uses_lightweight_path(self):
        result = classify_paths(["README.md", "docs/CI.md"], self.policy)
        self.assertTrue(result["docs_only"])
        self.assertFalse(result["portable_full"])
        self.assertEqual(result["labels"], ["area:repository", "documentation"])

    def test_contract_change_routes_both_lanes(self):
        result = classify_paths(
            ["software/ai/schemas/model_motion_proposal_v2.schema.json"], self.policy
        )
        self.assertTrue(result["contract"])
        self.assertIn("area:ai", result["labels"])
        self.assertIn("cross-workstream", result["labels"])
        self.assertTrue(result["portable_full"])

    def test_ci_change_exercises_every_qualification(self):
        result = classify_paths([".github/workflows/offline-checks.yml"], self.policy)
        self.assertTrue(result["portable_full"])
        self.assertTrue(result["rc03_manual"])
        self.assertTrue(result["rc03_reportlab"])
        self.assertTrue(result["rc03_trimesh"])

    def test_hardware_change_is_routed(self):
        result = classify_paths(["hardware/static_overhead_camera/cad/frame.py"], self.policy)
        self.assertIn("area:hardware", result["labels"])
        self.assertTrue(result["rc03_trimesh"])


if __name__ == "__main__":
    unittest.main()
