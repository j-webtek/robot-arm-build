import hashlib,json
from pathlib import Path
import unittest
AI=Path(__file__).resolve().parents[1]

class TranslationPairEvidence(unittest.TestCase):
    def test_frozen_sources_and_groups(self):
        path=AI/'eval/translation_pair_v0.manifest.json';m=json.loads(path.read_text())
        r=json.loads((AI/'eval/translation_pair_v0_scorecard.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),r['manifest_sha256'])
        for f,h in m['file_sha256'].items(): self.assertEqual(hashlib.sha256((AI.parents[1]/f).read_bytes()).hexdigest(),h)
        self.assertEqual([g['seed'] for g in r['groups']],list(range(18000000,18000500)))
        for name in m['models']:
            means=[v['mean_mm'] for g in r['groups'] for v in g['models'][name]]
            self.assertAlmostEqual(sum(means)/len(means),r['metrics'][name]['all']['mean_mm'])
        for c,decisions in r['criteria'].items():
            a,b=r['metrics']['control'][c],r['metrics']['candidate'][c]
            self.assertEqual(decisions,dict(mean_key_improves=b['mean_mm']<a['mean_mm'],center_improves=b['center_mean_mm']<a['center_mean_mm'],within_1mm_not_worse=b['within_1mm_fraction']>=a['within_1mm_fraction'],yaw_guard=b['yaw_p95_degrees']<=m['maximum_yaw_p95_ratio']*a['yaw_p95_degrees']))
        self.assertFalse(r['qualification_installed'])
