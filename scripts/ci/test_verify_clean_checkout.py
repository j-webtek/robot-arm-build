from unittest import mock
import unittest

import verify_clean_checkout as clean


class VerifyCleanCheckoutTests(unittest.TestCase):
    @mock.patch.object(clean, "git", return_value="a" * 40)
    def test_identity_accepts_exact_head(self, _):
        self.assertEqual("a" * 40, clean.validate_identity("A" * 40))

    @mock.patch.object(clean, "git", return_value="a" * 40)
    def test_identity_rejects_mismatch(self, _):
        with self.assertRaisesRegex(ValueError, "expected"):
            clean.validate_identity("b" * 40)

    @mock.patch.object(clean.subprocess, "run")
    def test_dirty_tree_is_rejected(self, run):
        run.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, "not clean"):
            clean.require_clean_tracked_tree()


if __name__ == "__main__":
    unittest.main()
