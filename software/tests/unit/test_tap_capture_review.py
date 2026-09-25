import json
from pathlib import Path
import subprocess
import shutil
import pytest
from rocell.application.tap_capture_review import review_tap_capture
from rocell.application.wizard_worker import run
from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render


def capture():
    return dict(schema='rocell.tap_capture.v1',capture_id='12345678-1234-1234-1234-123456789abc',
        expected_taps=1,viewport=dict(width=400,height=800),
        target=dict(left=100,top=200,right=220,bottom=320),stop_reason='STOPPED',
        events=[dict(kind=k,x=160,y=260,at_ms=i*10,trusted=True)
                for i,k in enumerate(('down','up','click'))])


def test_observation_is_not_robot_attribution():
    result=review_tap_capture(json.dumps(capture()))
    assert result['status']=='TAP_SEQUENCE_OBSERVED'
    assert not result['robot_tap_confirmed'] and not result['physical_accuracy_verified']
    assert not result['browser_provenance_authenticated']


@pytest.mark.parametrize('case,issue',[
    ('missing','TAP_COUNT_MISMATCH'),('extra','TAP_COUNT_MISMATCH'),
    ('edge','OUTSIDE_TARGET_INTERIOR'),('untrusted','UNTRUSTED_EVENT'),
    ('cancel','POINTER_CANCELLED'),('overlap','INVALID_TAP_SEQUENCE'),
    ('held','INCOMPLETE_TAP'),('interrupted','CAPTURE_INTERRUPTED')])
def test_faults_do_not_pass(case,issue):
    d=capture()
    if case=='missing': d['events']=[]
    if case=='extra':
        d['events'] += [dict(e,at_ms=e['at_ms']+30) for e in d['events']]
    if case=='edge': d['events'][0]['x']=100
    if case=='untrusted': d['events'][0]['trusted']=False
    if case=='cancel': d['events'][1]['kind']='cancel'
    if case=='overlap': d['events'][1]['kind']='down'
    if case=='held': d['events']=d['events'][:1]
    if case=='interrupted': d['stop_reason']='INTERRUPTED'
    report=review_tap_capture(json.dumps(d))
    assert report['status']=='TAP_NOT_VERIFIED' and issue in report['issues']


@pytest.mark.parametrize('case',['nan','bool','unknown','outside','reverse_time','oversize'])
def test_malformed_input_rejected(case):
    d=capture()
    if case=='nan': d['target']['left']=float('nan')
    if case=='bool': d['expected_taps']=True
    if case=='unknown': d['authority']=True
    if case=='outside': d['target']['right']=401
    if case=='reverse_time': d['events'][1]['at_ms']=-1
    if case=='oversize': d['events']*=12
    with pytest.raises(ValueError): review_tap_capture(json.dumps(d))


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_wizard_review_render_and_export(make_service,tmp_path,mode):
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(tmp_path,action,values,kw['cell_id'])
    op=_run(service,'review_tap_capture',{'capture_json':json.dumps(capture())})
    assert op['status']=='SUCCEEDED'
    assert op['result']['device_open_count']==0 and op['result']['motion_command_count']==0
    assert 'TAP_SEQUENCE_OBSERVED' in render(op) and 'NOT ESTABLISHED' in render(op)
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
    path=Path(exported['result']['receipt']['path'])/f"attachment-result-{op['operation_id'].removeprefix('operation-')}.json"
    assert json.loads(path.read_bytes())==op['result']


def test_page_handlers_generate_reviewable_transcript_without_network():
    page=Path(__file__).resolve().parents[2]/'tools/phone-tap-test.html'
    harness=r'''
const fs=require('fs'),vm=require('vm');
const nodes={},windows={};
for(const id of ['count','start','stop','target','zone','result','status','download'])
 nodes[id]={value:id==='count'?'1':'',listeners:{},addEventListener(k,f){this.listeners[k]=f},
 getBoundingClientRect(){return {left:100,top:200,right:220,bottom:320}}};
const ctx={document:{getElementById:id=>nodes[id],addEventListener(){}},
 window:{addEventListener(k,f){windows[k]=f}},innerWidth:400,innerHeight:800,
 crypto:{randomUUID:()=> '12345678-1234-1234-1234-123456789abc'},
 performance:{now:()=>100},setTimeout:()=>1,clearTimeout(){}};
const text=fs.readFileSync(process.argv[1],'utf8');
vm.runInNewContext(text.split('<script>')[1].split('</script>')[0],ctx);
nodes.start.onclick();
for(const name of ['pointerdown','pointerup','click']) nodes.zone.listeners[name]({clientX:160,clientY:260,isTrusted:true});
nodes.stop.onclick();const first=JSON.parse(nodes.result.value);
nodes.start.onclick();windows.resize();const interrupted=JSON.parse(nodes.result.value);
process.stdout.write(JSON.stringify({first,interrupted}));
'''
    result=subprocess.run([shutil.which('node'),'--eval',harness,str(page)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    assert review_tap_capture(json.dumps(output['first']))['status']=='TAP_SEQUENCE_OBSERVED'
    assert review_tap_capture(json.dumps(output['interrupted']))['status']=='TAP_NOT_VERIFIED'
