import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.input_capture_review import review_input_capture
from rocell.application.wizard_worker import run
from test_arrival_wizard_service import make_service, _run, _ticket
from test_movement_campaign_ui import render
from test_arrival_wizard_ui import running_server, request


def capture(word='a'):
    events=[]
    for key in word:
        for kind in ('down','text','up'):
            events.append(dict(kind=kind,key=key,at_ms=len(events)*10,repeat=False,trusted=True))
    return dict(schema='rocell.input_capture.v1',capture_id='12345678-1234-1234-1234-123456789abc',
                expected=word,stop_reason='STOPPED',events=events)


def test_complete_transcript_is_input_evidence_not_robot_proof():
    report=review_input_capture(json.dumps(capture('hello')))
    assert report['status']=='INPUT_MATCH_OBSERVED'
    assert report['observed_text']=='hello' and report['press_count']==5
    assert not report['robot_press_confirmed'] and not report['motion_authorized']
    assert not report['browser_provenance_authenticated']


def test_overlap_is_not_individual_keypress_success():
    data=capture('ab')
    data['events']=[data['events'][i] for i in (0,1,3,4,2,5)]
    for i,event in enumerate(data['events']):event['at_ms']=i*10
    assert 'OVERLAPPING_PRESSES' in review_input_capture(json.dumps(data))['issues']


def test_browser_capture_has_hard_time_event_and_character_bounds():
    script=Path(__file__).resolve().parents[2]/'src/rocell/ui/static/input-test.js'
    code=r'''
const {createCapture}=require(process.argv[1]);
const a=createCapture('a','id',0); for(let i=0;i<66;i++)a.add('down','a',false,true,i);
const b=createCapture('a','id',0); b.add('down','a',false,true,60001);
const c=createCapture('a','id',0); c.add('down','sensitive pasted text',false,true,10);
process.stdout.write(JSON.stringify([a.snapshot(),b.snapshot(),c.snapshot()]));
'''
    result=subprocess.run([shutil.which('node'),'--eval',code,str(script)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    a,b,c=json.loads(result.stdout)
    assert len(a['events'])==64 and a['stop_reason']=='EVENT_LIMIT'
    assert b['stop_reason']=='TIME_LIMIT' and b['events']==[]
    assert c['stop_reason']=='UNSUPPORTED_INPUT' and c['events']==[]


@pytest.mark.parametrize('case,issue',[
    ('missing','MISSING_INPUT'),('extra','EXTRA_INPUT'),('wrong','WRONG_INPUT'),
    ('repeat','REPEAT_EVENT'),('release','MISSING_KEY_RELEASE'),
    ('blur','CAPTURE_INTERRUPTED'),('scripted','SCRIPTED_OR_UNTRUSTED_EVENT'),
    ('text_only','TEXT_WITHOUT_MATCHING_KEY_DOWN')])
def test_failed_capture_is_not_success(case,issue):
    data=capture()
    if case=='missing':data['events']=[]
    if case=='extra':data=capture('aa');data['expected']='a'
    if case=='wrong':data=capture('b');data['expected']='a'
    if case=='repeat':data['events'][0]['repeat']=True
    if case=='release':data['events'].pop()
    if case=='blur':data['stop_reason']='BLUR'
    if case=='scripted':data['events'][0]['trusted']=False
    if case=='text_only':data['events']=data['events'][1:2]
    report=review_input_capture(json.dumps(data))
    assert report['status']=='INPUT_NOT_VERIFIED' and issue in report['issues']


@pytest.mark.parametrize('change',['unknown','oversize','timestamp','nonfinite','secret_key'])
def test_invalid_transcripts_rejected(change):
    data=capture()
    if change=='unknown':data['extra']='not allowed'
    if change=='oversize':data['events']*=30
    if change=='timestamp':data['events'][2]['at_ms']=-1
    if change=='nonfinite':data['events'][0]['at_ms']=float('nan')
    if change=='secret_key':data['events'][0]['key']='private text must not enter transcript'
    with pytest.raises(ValueError):review_input_capture(json.dumps(data))


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_service_retains_and_exports_input_observation(make_service,tmp_path,mode):
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(tmp_path,action,values,kw['cell_id'])
    supplied=dict(capture_json=json.dumps(capture()))
    _ticket(service,'review_input_capture',supplied)
    op=_run(service,'review_input_capture',supplied)
    assert op['status']=='SUCCEEDED'
    report=op['result']['steps'][0]['report']
    assert report['status']=='INPUT_MATCH_OBSERVED'
    assert op['result']['motion_command_count']==0
    page=render(op)
    assert 'NOT ESTABLISHED' in page and 'INPUT_MATCH_OBSERVED' in page
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
    file=Path(exported['result']['receipt']['path'])/f"attachment-result-{op['operation_id'].removeprefix('operation-')}.json"
    assert json.loads(file.read_bytes())['steps'][0]['report']==report


def test_pad_assets_are_read_only_and_loopback_only(running_server):
    server,service=running_server
    for path in ('/input-test','/assets/input-test.js'):
        status,headers,body=request(server,path)
        assert status==200 and body
        assert headers['Cache-Control']=='no-store'
    assert service.calls==[]


@pytest.mark.parametrize('lost_response',[False,True])
def test_actual_browser_handlers_collect_only_focused_pad_and_save_with_ticket(lost_response):
    script=Path(__file__).resolve().parents[2]/'src/rocell/ui/static/input-test.js'
    harness=r'''
const fs=require('fs'), vm=require('vm');
const nodes={}, calls=[];
for(const id of ['expected','pad','status','result','start','stop','prepare','save','saved'])
  nodes[id]={value:id==='expected'?'a':'',listeners:{},addEventListener(k,f){this.listeners[k]=f},focus(){},disabled:false};
const context={document:{getElementById:id=>nodes[id]},performance:{now:()=>100},
 crypto:{randomUUID:()=> '12345678-1234-1234-1234-123456789abc'},setTimeout:()=>1,clearTimeout:()=>{},
 sessionStorage:{getItem:()=> 'test-token'},fetch:async(path,opts)=>{
   calls.push({path,body:opts.body?JSON.parse(opts.body):null});
   if(path==='/api/execute' && process.argv[2]==='lost') throw new Error('Response lost');
   return {ok:true,json:async()=>path==='/api/view'?{revision:3}:path==='/api/prepare'?{ticket_id:'ticket-1'}:{operation_id:'operation-1'}};
 }};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
(async()=>{
 nodes.start.listeners.click();
 const key={key:'a',repeat:false,isTrusted:true,preventDefault(){}};
 nodes.pad.listeners.keydown(key);
 nodes.pad.listeners.beforeinput({...key,inputType:'insertText',data:'a'});
 nodes.pad.listeners.input({...key,data:'a'});
 nodes.pad.listeners.keyup(key);
 nodes.stop.listeners.pointerdown();
 await nodes.prepare.listeners.click(); await nodes.save.listeners.click();
 // Simulate repeated clicks and a late blur/stop notification, including after
 // an uncertain POST response. None may admit another save of this capture.
 nodes.pad.listeners.blur(); nodes.stop.listeners.click();
 await nodes.prepare.listeners.click(); await nodes.save.listeners.click();
 const locked=nodes.prepare.disabled && nodes.save.disabled;
 const message=nodes.saved.textContent;
 const capture=JSON.parse(nodes.result.textContent);
 nodes.start.listeners.click(); nodes.stop.listeners.click();
 const newCaptureCanPrepare=!nodes.prepare.disabled;
 process.stdout.write(JSON.stringify({capture,calls,locked,message,newCaptureCanPrepare,globalKeys:Object.keys(context.document)}));
})().catch(e=>{process.stderr.write(String(e));process.exitCode=1});
'''
    result=subprocess.run([shutil.which('node'),'--eval',harness,str(script),'lost' if lost_response else 'ok'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    assert review_input_capture(json.dumps(output['capture']))['status']=='INPUT_MATCH_OBSERVED'
    assert [c['path'] for c in output['calls']]==['/api/view','/api/prepare','/api/execute']
    assert output['calls'][1]['body']['action_id']=='review_input_capture'
    assert output['calls'][2]['body']==dict(ticket_id='ticket-1')
    assert output['globalKeys']==['getElementById']
    assert output['locked'] and output['newCaptureCanPrepare']
    assert ('outcome uncertain' if lost_response else 'Capture submitted') in output['message']
