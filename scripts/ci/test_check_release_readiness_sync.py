import copy
import json
import tempfile
import unittest
from pathlib import Path

from check_release_readiness_sync import load_registry


class ReleaseReadinessSyncTests(unittest.TestCase):
    def test_current_registry_is_valid(self):
        registry = load_registry()
        self.assertTrue(registry["blockers"])
        self.assertEqual(registry["tracker"]["issue"], 57)

    def test_status_domain_is_bounded(self):
        registry = load_registry()
        broken = copy.deepcopy(registry)
        broken["blockers"][0]["status"] = "maybe"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "readiness.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported blocker status"):
                load_registry(path)


if __name__ == "__main__":
    unittest.main()
