import hashlib,json,math
from pathlib import Path
import unittest
AI=Path(__file__).resolve().parents[1]

class NormalizedUncertaintyEvidence(unittest.TestCase):
    def test_calibration_and_evaluation_recount(self):
        path=AI/'eval/normalized_uncertainty_v0.manifest.json';m=json.loads(path.read_text())
        r=json.loads((AI/'eval/normalized_uncertainty_v0_scorecard.json').read_text())
        self.assertEqual(r['manifest_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        for f,h in m['file_sha256'].items():self.assertEqual(hashlib.sha256((AI.parents[1]/f).read_bytes()).hexdigest(),h)
        self.assertFalse(set(m['calibration_seeds']) & set(m['evaluation_seeds']))
        scores=sorted(g['maximum_error_mm'] for g in r['calibration_scores'])
        self.assertEqual(r['empirical_radius_mm'],scores[math.ceil(len(scores)*m['empirical_coverage_target'])-1])
        covered=sum(g['maximum_error_mm']<=r['empirical_radius_mm'] for g in r['evaluation_scores'])
        self.assertEqual(covered/len(r['evaluation_scores']),r['evaluation_empirical_coverage'])
        groups=r['actual_oracle_fit_groups']
        self.assertEqual(sum(g['all_targets_fit'] for g in groups),r['actual_oracle_all_targets_fit_groups'])
        self.assertEqual(sum(c['fitting_targets'] for g in groups for c in g['cases']),r['actual_oracle_fitting_targets'])
        passed=r['evaluation_empirical_coverage']>=m['minimum_evaluation_coverage'] and r['actual_oracle_group_fit_fraction']>=m['minimum_actual_group_fit_fraction']
        self.assertEqual(r['status'],'SYNTHETIC_COMBINED_CRITERIA_PASS_UNQUALIFIED' if passed else 'SYNTHETIC_COMBINED_CRITERIA_FAIL')
        self.assertEqual(m['calibration_seeds'],list(range(22000000,22001000)))
        self.assertEqual(m['evaluation_seeds'],list(range(23000000,23000500)))
        self.assertEqual(r['total_target_predictions'],500*7*46)
        for g in groups:
            self.assertEqual([c['condition'] for c in g['cases']],m['conditions'])
            self.assertEqual(g['all_targets_fit'],all(c['fitting_targets']==46 for c in g['cases']))
        self.assertFalse(r['qualification_installed'])
