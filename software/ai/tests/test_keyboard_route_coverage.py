"""Coverage generation must preserve exact catalog centers and synthetic provenance."""
import sys
import unittest
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = AI_DIR.parents[1]
sys.path[:0] = [str(AI_DIR), str(AI_DIR.parent / 'src')]

from run_keyboard_route_coverage import proposals
from rocell.targets import load_nominal_target_catalog
from rocell_ai.motion_assurance import build


class KeyboardCoverageTests(unittest.TestCase):
    def test_generated_proposals_cover_catalog_once_and_pass_bridge(self):
        catalog = load_nominal_target_catalog(WORKSPACE)
        rows = proposals(WORKSPACE)
        self.assertEqual(len(rows), len(catalog.keyboard_targets))
        self.assertEqual({row['target_id'] for row in rows}, set(catalog.keyboard_targets))
        for row in rows:
            region = catalog.keyboard_targets[row['target_id']]
            self.assertEqual(row['target_mm'], dict(x=region.center.x, y=region.center.y, z=region.center.z))
            self.assertEqual(row['source']['frame_id'], 'synthetic-no-camera-capture')
            bundle = build(row, workspace=WORKSPACE)
            self.assertFalse(bundle['assurance']['physical_execution_authorized'])
            self.assertEqual(bundle['candidate']['controller_commands'], [])


if __name__ == '__main__':
    unittest.main()
