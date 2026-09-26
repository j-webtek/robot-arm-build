import math
from pathlib import Path
import sys
import unittest
from PIL import Image, ImageDraw
AI=Path(__file__).resolve().parents[1];sys.path.insert(0,str(AI))
from vision.local_refinement import refine

class LocalRefinementTests(unittest.TestCase):
    def test_flat_image_unchanged(self):
        self.assertEqual(refine(Image.new('RGB',(256,192)),(200.0,150.0)),(200.0,150.0))
    def test_correction_bound(self):
        image=Image.new('RGB',(256,192));draw=ImageDraw.Draw(image)
        draw.rectangle((83,58,90,67),fill='white')
        point=(200.0,150.0)
        self.assertLessEqual(math.dist(refine(image,point),point),1.0+1e-12)
    def test_border_unchanged(self):
        self.assertEqual(refine(Image.new('RGB',(256,192)),(0.0,0.0)),(0.0,0.0))
    def test_invalid_point(self):
        with self.assertRaises(ValueError): refine(Image.new('RGB',(256,192)),(float('nan'),0))
