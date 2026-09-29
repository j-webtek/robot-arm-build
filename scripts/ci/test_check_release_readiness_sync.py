import copy
import json
import tempfile
import unittest
from pathlib import Path

from check_release_readiness_sync import (
    BEGIN,
    END,
    check_dashboard,
    load_registry,
    render_dashboard_status,
    render_milestone_description,
    render_tracker_body,
    replace_generated_status,
)


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

    def test_generated_surfaces_follow_registry(self):
        registry = load_registry()
        tracker = render_tracker_body(registry)
        milestone = render_milestone_description(registry)
        dashboard = render_dashboard_status(registry)
        self.assertIn("**1 open blocker**", tracker)
        self.assertIn("- [ ] #88", tracker)
        self.assertIn("- [x] #167", tracker)
        self.assertIn("open blockers: #88", milestone)
        self.assertIn("1 open blocker", dashboard)

    def test_dashboard_drift_is_detected_and_repairable(self):
        registry = load_registry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "READINESS.md"
            path.write_text("# Readiness\n\n## Current gate summary\n", encoding="utf-8")
            repaired = replace_generated_status(path.read_text(encoding="utf-8"), render_dashboard_status(registry))
            path.write_text(repaired, encoding="utf-8")
            self.assertEqual(check_dashboard(registry, path), [])
            path.write_text(repaired.replace("1 open blocker", "2 open blockers"), encoding="utf-8")
            self.assertTrue(check_dashboard(registry, path))
            self.assertIn(BEGIN, repaired)
            self.assertIn(END, repaired)


if __name__ == "__main__":
    unittest.main()
