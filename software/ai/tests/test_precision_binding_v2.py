from dataclasses import replace
from pathlib import Path
import sys
import pytest
AI=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src'),str(AI.parent/'tests/unit'),str(AI/'tests')]
import test_vision_fusion as vision_fixture
import test_model_motion_ingress_v2 as arm
from rocell_ai.precision_observation import build
from rocell_ai.precision_binding_v2 import preflight


def fixture():
    source=vision_fixture.VisionFusionTests();source.setUp()
    precision=build(source.precision,domain_id='synthetic-keyboard-standard')
    context=arm.load_simulation_context(arm.WORKSPACE,arm.MANIFEST)
    batch=arm._batch(context)
    p=precision['prediction']
    evidence=replace(batch.evidence,precision_observation_sha256=precision['observation_sha256'],
        frame_id=p['frame_id'],image_sha256=p['image_sha256'],model_sha256=p['model_sha256'])
    geometry=replace(batch.geometry,target_catalog_sha256=p['target_catalog_sha256'])
    return precision,evidence,geometry


def test_current_precision_abstains_without_invented_confidence():
    p,e,g=fixture();r=preflight(p,evidence=e,geometry=g)
    assert r['batch'] is None
    assert 'precision_observation_confidence_missing' in r['reasons']
    assert 'precision_capture_clock_provenance_missing' in r['reasons']
    assert r['hardware_writes']==r['physical_movements']==0


@pytest.mark.parametrize('field',['frame_id','image_sha256','model_sha256','precision_observation_sha256'])
def test_mixed_evidence_rejected(field):
    p,e,g=fixture()
    with pytest.raises(ValueError,match='mismatch'):
        preflight(p,evidence=replace(e,**{field:'other' if field=='frame_id' else '0'*64}),geometry=g)


def test_changed_target_map_rejected():
    p,e,g=fixture()
    with pytest.raises(ValueError,match='target_map'):
        preflight(p,evidence=e,geometry=replace(g,target_catalog_sha256='0'*64))


def test_tampered_coordinates_rejected():
    p,e,g=fixture();p['prediction']['targets']['H']['center_board_mm'][0]+=1
    with pytest.raises(ValueError,match='hash mismatch'):
        preflight(p,evidence=e,geometry=g)
