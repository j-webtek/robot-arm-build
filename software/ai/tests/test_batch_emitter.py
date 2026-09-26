"""Shared batch producer integration and localization abstention regressions."""
import copy
from pathlib import Path
import sys
import unittest
AI_DIR=Path(__file__).resolve().parents[1]
WORKSPACE=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
import test_vision_fusion as fixtures
from rocell.typing import compile_development_text
from rocell.models import decode_model_motion_batch_json
from rocell.application.context import load_simulation_context
from rocell.application.model_motion_ingress import ingest_model_motion_batch
from rocell_ai.precision_observation import build, validate
from rocell_ai.batch_emitter import emit
from rocell_ai.scene_observation import canonical_hash
import json


class BatchEmitterTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.VisionFusionTests();fixture.setUp()
        self.f=fixture
        q={'schema':'rocell.ai_localization_qualification.v0','model_sha256':'b'*64,
           'target_catalog_sha256':fixture.catalog.content_sha256,'domain_id':'TEST_ONLY',
           'calibration_dataset_sha256':'c'*64,'evaluation_dataset_sha256':'d'*64,
           'coverage_probability':0.99,'error_bound_mm':1.0,'target_ids':['H','I'],
           'scope':'SYNTHETIC_OFFLINE_ONLY'}
        self.q={**q,'qualification_sha256':canonical_hash(q)}
        self.plan=compile_development_text('keyboard','hhi')

    def call(self,precision,registry=None,**kwargs):
        return emit(plan=self.plan,request_id='request-1',batch_id='batch-1',workspace=WORKSPACE,
                    frame=self.f.frame,scene_observation=self.f.scene,precision_observation=precision,
                    evaluated_at_utc=kwargs.get('time','2026-09-25T12:00:01Z'),trusted_qualifications=registry,expected_domain_id=kwargs.get('domain','TEST_ONLY'))

    def qualified(self):
        return build(self.f.precision,domain_id='TEST_ONLY',qualification_sha256=self.q['qualification_sha256'])

    def test_uncalibrated_prediction_abstains_even_with_good_scene(self):
        result=self.call(build(self.f.precision,domain_id='TEST_ONLY'))
        self.assertIsNone(result['batch'])
        self.assertIn('localization_uncalibrated',result['fusion']['reasons'])
        self.assertFalse(result['physical_execution_authorized'])

    def test_untrusted_qualification_cannot_self_authorize(self):
        result=self.call(self.qualified())
        self.assertIsNone(result['batch'])
        self.assertIn('localization_qualification_untrusted',result['fusion']['reasons'])

    def test_test_only_qualification_roundtrips_shared_ingress_preserving_repetitions(self):
        result=self.call(self.qualified(),{self.q['qualification_sha256']:self.q})
        batch=decode_model_motion_batch_json(json.dumps(result['batch']).encode())
        self.assertEqual([p.target_id for p in batch.proposals],['H','H','I'])
        self.assertEqual(len({p.proposal_id for p in batch.proposals}),3)
        self.assertTrue(all(p.confidence==0.99 for p in batch.proposals))
        context=load_simulation_context(WORKSPACE,WORKSPACE/'software/config/system_manifest.json')
        report=ingest_model_motion_batch(batch,self.plan,context,
            expected_scene_observation_sha256=self.f.scene['observation_sha256'],
            expected_precision_observation_sha256=result['precision_observation']['observation_sha256'],
            expected_fusion_decision_sha256=result['fusion']['decision_sha256'])
        self.assertEqual(report['ordered_target_ids'],['H','H','I'])
        self.assertFalse(report['physical_authority'])
        self.assertEqual(report['controller_commands'],[])

    def test_stale_frame_and_uncertainty_crossing_target_edge_block(self):
        registry={self.q['qualification_sha256']:self.q}
        stale=self.call(self.qualified(),registry,time='2026-09-25T12:00:10Z')
        self.assertIsNone(stale['batch'])
        changed=copy.deepcopy(self.f.precision)
        changed['targets']['H']['center_board_mm'][0]+=6.5
        changed['observation_sha256']=canonical_hash({k:v for k,v in changed.items() if k!='observation_sha256'})
        precision=build(changed,domain_id='TEST_ONLY',qualification_sha256=self.q['qualification_sha256'])
        result=self.call(precision,registry)
        self.assertIsNone(result['batch'])
        self.assertIn('localization_bound_outside_target',result['fusion']['reasons'])

    def test_rehashed_abstention_suppression_and_domain_mismatch_rejected(self):
        precision=build(self.f.precision,domain_id='TEST_ONLY')
        precision['abstain']=False;precision['abstain_reasons']=[]
        precision['observation_sha256']=canonical_hash({k:v for k,v in precision.items() if k!='observation_sha256'})
        with self.assertRaisesRegex(ValueError,'abstention'):
            validate(precision)
        precision=build(self.f.precision,domain_id='WRONG_DOMAIN',qualification_sha256=self.q['qualification_sha256'])
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            self.call(precision,{self.q['qualification_sha256']:self.q})

    def test_domain_must_be_selected_by_trusted_application(self):
        result=self.call(self.qualified(),{self.q['qualification_sha256']:self.q},domain=None)
        self.assertIsNone(result['batch'])
        self.assertIn('localization_domain_unverified',result['fusion']['reasons'])

    def test_phone_plan_cannot_reuse_a_single_frame(self):
        self.plan=compile_development_text('phone','hi')
        with self.assertRaisesRegex(ValueError,'fresh observation'):
            self.call(build(self.f.precision,domain_id='TEST_ONLY'))

if __name__=='__main__':
    unittest.main()
