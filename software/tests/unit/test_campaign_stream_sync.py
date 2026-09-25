"""V7 startup partition and original-preserving native-shaped replay tests."""
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import SYNC_BASE_SCHEMA, fixed_campaign_limits
from test_base_mapping_campaign import base_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.arm.campaign_stream_sync import campaign_window


def sync_body():
    body=base_body()
    body.update(schema=SYNC_BASE_SCHEMA,limits=fixed_campaign_limits(SYNC_BASE_SCHEMA))
    return body


@pytest.mark.parametrize('prefix',[b'',b'}\r\n',b'garbage\n',b'\r\n'])
def test_one_startup_line_retained_before_clean_baseline(tmp_path,monkeypatch,prefix):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',sync_body)
    kernel,captures,_,_,result=exercise(tmp_path,monkeypatch,initial_prefix=prefix)
    assert result['status']=='REPORTED_CAMPAIGN_COMPLETE',result
    assert len(kernel.writes)==1 and result['cleanup']['all_handles_closed']
    assert captures[0]['finished_ns']-captures[0]['started_ns']==1_250_000_000


@pytest.mark.parametrize('prefix',[b'}\r\nbad\n',b'}\r\n\r\n',b'}\r\n"b":0}\n'])
def test_second_invalid_line_never_skipped(tmp_path,monkeypatch,prefix):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',sync_body)
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,initial_prefix=prefix)
    assert result['status']=='HELD' and not kernel.writes


@pytest.mark.parametrize('prefix',[b'',b'}\r\n'])
def test_synchronized_portable_export_reproduces_partition(tmp_path,monkeypatch,prefix):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',sync_body)
    path,name,_=bundle(tmp_path,monkeypatch,initial_prefix=prefix)
    verified=verify_native_retained_export(path,name)
    assert verified['valid'] and verified['endpoint_completion_consistent'],verified
    sync=verified['endpoint_diagnostics'][0]['baseline_synchronization']
    assert sync['startup_range'][0]==0 and sync['startup_range'][1]>0
    assert not sync['startup_content_validated'] and not sync['motion_authorized']
    if prefix:assert sync['startup_range']==[0,len(prefix)]


@pytest.mark.parametrize('fault',['cancel_before_open','write_error','read_error'])
def test_sync_transport_faults_do_not_retry(tmp_path,monkeypatch,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',sync_body)
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,initial_prefix=b'}\r\n',failure=fault)
    assert len(kernel.writes)==(1 if fault=='write_error' else 0)
    assert result['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert result['cleanup']['all_handles_closed']


@pytest.mark.parametrize('fault',['delimiter','late','bytes','duration','interior'])
def test_partition_rejects_unbounded_or_insufficient_stream(fault):
    packet=canonical(dict(T=1051,b=0,s=0,e=0,t=0,r=0,g=0,x=0,y=0,z=0,tit=0))+b'\n'
    chunks=[b'}\n']+[packet]*62
    if fault=='delimiter':chunks=[b'x'*200]*62
    if fault=='bytes':chunks=[b'x'*200]*21+[b'\n']+[packet]*40
    if fault=='interior':chunks[3]=b'bad\n'
    raw=b''.join(chunks);windows=[];offset=0
    for i,chunk in enumerate(chunks):
        windows.append([offset,offset+len(chunk),1+i*20_000_000,1+(i+1)*20_000_000]);offset+=len(chunk)
    end=1+1_250_000_000
    if fault=='late':windows[0][3]=260_000_001;windows=windows[:1];raw=chunks[0]
    if fault=='duration':end=500_000_001
    try:
        _,issues,_=campaign_window(sync_body(),'baseline',raw,windows,1,end,maximum_bytes=98304)
    except ValueError:return
    assert issues
