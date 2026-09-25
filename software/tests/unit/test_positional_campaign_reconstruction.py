import json
import pytest
from test_positional_owned_campaign import run
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.application.positional_campaign_reconstruction import verify_completed_owned_campaign


def experiment(tmp_path,fault=None):
    result,_=run(tmp_path,fault)
    original=json.loads(next(tmp_path.glob('*-owner.json')).read_bytes())
    return PositionalCampaignIntent(canonical(original['intent'])),result


@pytest.mark.parametrize('fault',[None,'no_response','short_write','write_error'])
def test_recompute_evaluated_campaign_from_originals(tmp_path,fault):
    request,result=experiment(tmp_path,fault)
    verified=verify_completed_owned_campaign(request,result)
    assert verified['valid']
    assert verified['reconstructed_status']==result['status']
    assert not verified['motion_authorized']


@pytest.mark.parametrize('field',['endpoint','raw','hash','order','write','skipped','count','cleanup','authority','dispatch','status'])
def test_inconsistent_saved_claims_rejected(tmp_path,field):
    request,result=experiment(tmp_path)
    first=result['legs'][0]
    if field=='endpoint': first['verification']['endpoint']['final_error_rad']=1
    if field=='raw': first['post']['raw']['base64_chunks'][0]='e30='
    if field=='hash': first['verification']['committed_sha256']='f'*64
    if field=='order': result['legs'].reverse()
    if field=='write': first['write']['confirmed_bytes']=0
    if field=='skipped': result['skipped_leg_ids']=['leg-02']
    if field=='count': result['simulated_write_attempts']=True
    if field=='cleanup': result['cleanup']['finished_ns']+=3_000_000_000
    if field=='authority': result['native_execution_released']=True
    if field=='dispatch': first['verification']['dispatch_claimed_ns']-=1
    if field=='status': result['status']='HELD'
    with pytest.raises(ValueError): verify_completed_owned_campaign(request,result)


@pytest.mark.parametrize('fault',['malformed','cancel_before','cancel_after','close_error','clock_error'])
def test_incomplete_campaign_never_receives_completed_verification(tmp_path,fault):
    request,result=experiment(tmp_path,fault)
    with pytest.raises(ValueError): verify_completed_owned_campaign(request,result)
