import unittest

from change_classifier import classify_paths, load_policy
from pr_automation import completeness_findings


COMPLETE_BODY = """## What changes for the user?
Outcome.
## Ownership and handoff
Compatibility: additive; migration documented and rollback is available.
## Evidence
Tests pass.
"""


class PullRequestAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()

    def test_tiny_docs_change_is_exempt_from_long_template(self):
        result = classify_paths(["README.md"], self.policy)
        self.assertEqual(completeness_findings("Small correction", result), [])

    def test_regular_change_requires_core_sections(self):
        result = classify_paths(["software/src/rocell/arm/protocol.py"], self.policy)
        self.assertEqual(len(completeness_findings("", result)), 3)

    def test_unanswered_template_is_not_complete(self):
        result = classify_paths(["software/src/rocell/arm/protocol.py"], self.policy)
        body = COMPLETE_BODY + "\n- Commands run and results:\n"
        self.assertTrue(any("unanswered" in item for item in completeness_findings(body, result)))

    def test_contract_requires_test_and_docs(self):
        result = classify_paths(
            ["software/ai/schemas/model_motion_proposal_v2.schema.json"], self.policy
        )
        findings = completeness_findings(COMPLETE_BODY, result)
        self.assertTrue(any("test" in item for item in findings))
        self.assertTrue(any("documentation" in item for item in findings))

    def test_complete_contract_handoff_passes(self):
        result = classify_paths(
            [
                "software/ai/schemas/model_motion_proposal_v2.schema.json",
                "software/ai/tests/test_model_motion_proposal.py",
                "docs/SYSTEM_OVERVIEW.md",
            ],
            self.policy,
        )
        self.assertEqual(completeness_findings(COMPLETE_BODY, result), [])


if __name__ == "__main__":
    unittest.main()
