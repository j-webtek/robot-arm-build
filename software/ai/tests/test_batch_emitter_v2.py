"""Actual assembler bytes; synthetic consumer fixtures, never deployment evidence."""
from pathlib import Path
import sys
from dataclasses import replace
import pytest
AI=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src'),str(AI.parent/'tests/unit')]
import test_model_motion_ingress_v2 as arm
from rocell_ai.batch_emitter_v2 import assemble, TargetObservationV2


def setup():
    context=arm.load_simulation_context(arm.WORKSPACE,arm.MANIFEST)
    plan=arm.ActionPlan.from_text(device=arm.Device.KEYBOARD,
        profile_id='keyboard-development-v1',text='hhi',
        actions=(arm.PressKey('H'),arm.PressKey('H'),arm.PressKey('I')),
        required_calibrations=('keyboard_pose','keyboard_tcp'))
    fixture=arm._batch(context)
    args=dict(batch_id='producer-v2',request_id='request-v2',capability=fixture.capability,
        geometry=fixture.geometry,evidence=fixture.evidence,uncertainty=fixture.uncertainty,
        observations={p.target_id:TargetObservationV2(p.target,0.93) for p in fixture.proposals})
    return context,plan,args


def test_actual_assembler_order_and_consumer():
    context,plan,args=setup()
    payload=assemble(plan,**args)
    batch=arm.decode_model_motion_batch_v2_json(payload)
    report=arm._ingest(batch,plan,context)
    assert report['ordered_target_ids']==['H','H','I']
    assert len({p.proposal_id for p in batch.proposals})==3
    assert all(p.observation_confidence==0.93 for p in batch.proposals)
    assert batch.uncertainty.coverage_probability==0.99
    assert report['controller_commands']==[]
    assert report['hardware_access'] is report['physical_authority'] is False
    assert assemble(plan,**args)==payload


def test_missing_uncertainty_abstains():
    _,plan,args=setup();args.pop('uncertainty')
    assert assemble(plan,**args) is None


@pytest.mark.parametrize('mutation',['missing','uncovered','profile','confidence','placement'])
def test_bad_assembly_rejected(mutation):
    _,plan,args=setup()
    if mutation=='missing': args['observations'].pop('H')
    if mutation=='uncovered': args['uncertainty']=replace(args['uncertainty'],covered_target_ids=('I',))
    if mutation=='profile': args['capability']=replace(args['capability'],profile_id='other')
    if mutation=='confidence': args['observations']['H']=replace(args['observations']['H'],observation_confidence=True)
    if mutation=='placement': args['geometry']=replace(args['geometry'],placement_observation_sha256=args['evidence'].precision_observation_sha256)
    with pytest.raises(ValueError): assemble(plan,**args)


def test_consumer_rechecks_actual_bytes_at_expiry():
    context,plan,args=setup()
    batch=arm.decode_model_motion_batch_v2_json(assemble(plan,**args))
    with pytest.raises(ValueError):
        arm._ingest(batch,plan,context,current_time_epoch_ms=args['evidence'].expires_at_epoch_ms)
