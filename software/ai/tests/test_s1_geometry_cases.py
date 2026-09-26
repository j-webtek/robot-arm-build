"""Analytic acceptance examples for S1 review, not production admission."""
import json
from pathlib import Path
import sys
import unittest
AI=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI))
from vision.evaluate_prediction_margin import margin


class S1GeometryCases(unittest.TestCase):
    def test_frozen_analytic_cases(self):
        data=json.loads((AI/'eval/s1_geometry_cases_v0.json').read_text())
        self.assertEqual(data['scope'],'ANALYTIC_TEST_ONLY')
        self.assertEqual(len(data['cases']),10)
        self.assertEqual(len({c['id'] for c in data['cases']}),10)
        for c in data['cases']:
            with self.subTest(case=c['id']):
                result=margin(tuple(c['point_mm']),tuple(c['independent_center_mm']),
                              c['yaw_rad'],tuple(c['half_extents_mm']),c['radius_mm'])
                self.assertEqual(result>=0,c['expected_fit'])

    def test_rotated_bounding_box_is_insufficient(self):
        # At 45 degrees this point lies inside the enclosing AABB, outside the key.
        import math
        aabb_half=(5+2)/math.sqrt(2)
        self.assertLess(4+0.1,aabb_half)
        self.assertLess(margin((104,204),(100,200),math.pi/4,(5,2),0.1),0)

    def test_self_centering_hides_displacement(self):
        point=(150,200)
        self.assertLess(margin(point,(100,200),0,(7,7),1),0)
        self.assertGreater(margin(point,point,0,(7,7),1),0)
        # Geometry cannot establish evidence independence: future registry must.
