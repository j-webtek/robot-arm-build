"""Run the actual summary renderer in a minimal inert DOM; no browser requests."""

import json
from pathlib import Path
import shutil
import subprocess
import pytest

from rocell.application.wizard_worker import run

WORKSPACE=Path(__file__).resolve().parents[3]


def render(operation):
    script=(WORKSPACE/'software/src/rocell/ui/static/app.js').read_text(encoding='utf-8')
    function=script[script.index('  function appendMovementCampaignResult('):script.index('  function taskSimulationFeedback(')]
    harness=r'''
const fs=require('fs');const input=JSON.parse(fs.readFileSync(0,'utf8'));
function element(tag,cls,text=''){return {textContent:String(text),children:[],append(...items){this.children.push(...items)}}}
function card(title,subtitle){return element('section','',title+' '+subtitle)}
function facts(values){return element('div','',JSON.stringify(values))}
eval(input.function);
const root=element('main','');appendMovementCampaignResult(root,input.operation);
function flatten(node){return node.textContent+' '+node.children.map(flatten).join(' ')}
process.stdout.write(flatten(root));
'''
    result=subprocess.run([shutil.which('node'),'--eval',harness],
        input=json.dumps({'function':function,'operation':operation}),text=True,
        capture_output=True,timeout=5)
    assert result.returncode==0,result.stderr
    return result.stdout


def operation(fault='NONE'):
    return {'action_id':'movement_campaign_simulate','result':run(WORKSPACE,'movement_campaign_simulate',{'fault':fault},'ui-test')}


def test_completed_simulation_is_explicitly_not_physical():
    page=render(operation())
    assert 'Movement campaign summary' in page
    assert 'TRANSFORM_REQUIRED' in page
    assert 'NOT QUALIFIED' in page
    assert 'Observed in synthetic data only' in page
    assert 'FIRMWARE COEFFICIENT (not mm/s)' in page
    assert 'MODELED_UNTIMED_TRACES' in page
    assert 'no elapsed timing' in page
    assert 'not a verified servo hold' in page
    assert 'Repeatability comparison' in page
    assert 'INSUFFICIENT_REPETITIONS' in page


def test_mismatched_controller_plan_is_not_presented_as_bound_model():
    data=operation()
    data['result']['steps'][0]['report']['controller_model']['plan_sha256']='f'*64
    page=render(data)
    assert 'UNAVAILABLE OR INCONSISTENT' in page
    assert 'MODELED_UNTIMED_TRACES' not in page


def test_reference_ik_failure_is_visible_separately_from_interpolation():
    data = operation()
    controller = data['result']['steps'][0]['report']['controller_model']
    controller['reference_ik_status'] = 'REFERENCE_IK_INCOMPLETE'
    controller['trials'][0]['reference_ik'] = {
        'status': 'REFERENCE_IK_UNRESOLVED', 'evaluated_samples': 3,
        'first_failure': {'sample_index': 2, 'reason': 'REGULAR_BRANCH_OR_ROUNDTRIP_FAILED'}}
    page = render(data)
    assert 'REFERENCE_IK_INCOMPLETE' in page
    assert 'Reference IK unresolved at sample 2' in page
    assert 'Installed joint limits' in page


def test_failure_shows_skipped_return_and_missing_metric():
    page=render(operation('DISCONNECT'))
    assert 'STOPPED' in page and 'Skipped: back' in page
    assert 'Unavailable' in page and 'Not established' in page


@pytest.mark.parametrize('change',['schema','basis','authority'])
def test_inconsistent_report_does_not_render_metrics(change):
    data=operation(); report=data['result']['steps'][0]['report']
    if change=='authority':report['physical_authority']=True
    else:report[change]='invalid'
    page=render(data)
    assert 'unavailable or inconsistent' in page
    assert 'Observed in synthetic data only' not in page
