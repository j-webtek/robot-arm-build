import hashlib,json,sys
from pathlib import Path
import unittest
from PIL import Image
AI=Path(__file__).resolve().parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.diagnose_single_perturbations import perturb

class SinglePerturbationTests(unittest.TestCase):
    def test_transform_does_not_mutate_base(self):
        image=Image.new('RGB',(256,192),(200,100,50));original=image.tobytes()
        for name in ('base','darken','blur','obstruction'):
            result=perturb(image,name)
            self.assertEqual(image.tobytes(),original)
            self.assertEqual(result.size,image.size)
        self.assertEqual(perturb(image,'darken').getpixel((0,0)),(100,50,25))
        with self.assertRaises(ValueError):perturb(image,'unknown')
    def test_paired_recount(self):
        path=AI/'eval/single_perturbations_v0.manifest.json';m=json.loads(path.read_text())
        r=json.loads((AI/'eval/single_perturbations_v0_scorecard.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),r['manifest_sha256'])
        for f,h in m['file_sha256'].items():self.assertEqual(hashlib.sha256((AI.parents[1]/f).read_bytes()).hexdigest(),h)
        self.assertEqual([c['seed'] for c in r['cases']],list(range(15000000,15000200)))
        for name,summary in r['summaries'].items():
            deltas=[c['conditions'][name]['mean_key_error_mm']-c['conditions']['base']['mean_key_error_mm'] for c in r['cases']]
            self.assertAlmostEqual(sum(deltas)/200,summary['mean_paired_error_delta_mm'])
            self.assertEqual(sum(c['conditions'][name]['large_error'] for c in r['cases']),summary['large_error_images'])
