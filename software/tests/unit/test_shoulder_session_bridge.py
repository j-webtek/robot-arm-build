import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import pytest
from rocell.application.shoulder_export_receipt import export_and_sign
from rocell.application.shoulder_start_authorization import sign_shoulder_start
from rocell.application.shoulder_session_review import ShoulderSessionReview


@pytest.mark.parametrize('fault',['wrong_scope','bad_receipt_first','bad_receipt_next','export_abort',
    'late_receipt','passive','wrong_goal','drift','neighbor','read_failure','delivery'])
def test_pose_preparation_stops_without_next_joint(tmp_path,bridge,fault):
    from rocell.application.mixed_shoulder_session_review import MixedShoulderSessionReview
    command='pose-preparation-v1'
    token=signed_start('MIXED_TARGET' if fault=='wrong_scope' else 'POSE_PREPARATION',command)
    path=tmp_path/'start.bin';path.write_bytes(token)
    mode='prep_'+fault if fault in ('passive','wrong_goal','drift','neighbor','read_failure','delivery') else 'prep'
    process=subprocess.Popen([str(bridge),str(path),command,mode],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    lines=queue.Queue()
    def read():
        for line in process.stdout:lines.put(line)
        lines.put(None)
    threading.Thread(target=read,daemon=True).start()
    review=MixedShoulderSessionReview('11'*16,command,preparation=True);terminal=None
    try:
        for _ in range(26):
            line=lines.get(timeout=10);assert line is not None
            doc=json.loads(line)
            if doc.get('terminal'):terminal=doc;break
            raw=line.rstrip('\r\n').encode();review.accept(raw)
            if fault=='export_abort' and doc['sequence']==1:
                process.stdin.write('ABORT\n');process.stdin.flush();continue
            evidence=export_and_sign(tmp_path/'exports',raw,key=bytes(range(32)),boot='11'*16,
                command=command,sequence=doc['sequence'])
            receipt=evidence['receipt']
            if doc['sequence']=={'bad_receipt_first':1,'bad_receipt_next':7}.get(fault):
                receipt=receipt[:-1]+bytes([receipt[-1]^1])
            prefix='DELAY:2100000:' if fault=='late_receipt' and doc['sequence']==3 else ''
            process.stdin.write(prefix+receipt.hex()+'\n');process.stdin.flush()
        assert terminal and not terminal['complete'] and terminal['broadcasts']==0
        assert terminal['writes']==(0 if fault in ('wrong_scope','bad_receipt_first','export_abort') else 1)
        assert process.wait(timeout=5)==0,process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)


def signed_start(scope='PAIR_HOLD', command='receipt-test'):
    return sign_shoulder_start(dict(schema='rocell.start_challenge.v1',
        boot_id='11'*16, nonce='00'*32, issued_us=0, expires_us=30_000_000),
        command, scope, bytes(range(32)))


@pytest.mark.parametrize('mode',['recover_baseline_goal','recover_baseline_residual','recover_baseline_elbow_error'])
def test_recovery_rejects_changed_start_without_write(tmp_path,bridge,mode):
    command='shoulder-clearance24-v1'
    path=tmp_path/'start.bin';path.write_bytes(signed_start('CLEARANCE_RECOVERY',command))
    run=subprocess.run([str(bridge),str(path),command,mode],input='',capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout)
    assert not result['complete'] and result['writes']==0 and result['broadcasts']==0


def test_stable_recovery_stops_on_second_baseline_drift(tmp_path,bridge):
    command='shoulder-stable-clearance24-v1'
    path=tmp_path/'start.bin';path.write_bytes(signed_start('STABLE_CLEARANCE_RECOVERY',command))
    process=subprocess.Popen([str(bridge),str(path),command,'stable_unstable'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        raw=process.stdout.readline().rstrip('\r\n').encode()
        doc=json.loads(raw);assert doc['sequence']==0 and doc['event']=='BASELINE'
        evidence=export_and_sign(tmp_path/'exports',raw,key=bytes(range(32)),boot='11'*16,command=command,sequence=0)
        process.stdin.write('DELAY:100000:'+evidence['receipt'].hex()+'\n');process.stdin.flush()
        terminal=json.loads(process.stdout.readline())
        assert not terminal['complete'] and terminal['writes']==0
        assert terminal['reason']=='RECOVERY_BASELINE_UNSTABLE'
        assert process.wait(timeout=5)==0
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)


@pytest.mark.parametrize('recovery',[False,True,'stable'])
@pytest.mark.parametrize('fault',['wrong_scope','passive','window','wrong_goal','neighbor',
    'wrong_direction','read_failure','no_motion','plateau','bad_receipt','export_abort','late_observation',
    'late_final_export'])
def test_shoulder_rise_bounded_failures_and_final_export(tmp_path,bridge,fault,recovery):
    from rocell.application.shoulder_rise_review import ShoulderRiseReview
    stable=recovery=='stable'
    command='shoulder-stable-clearance24-v1' if stable else 'shoulder-clearance24-v1' if recovery else 'shoulder-rise12-v1'
    scope='STABLE_CLEARANCE_RECOVERY' if stable else 'CLEARANCE_RECOVERY' if recovery else 'SHOULDER_RISE'
    path=tmp_path/'start.bin';path.write_bytes(signed_start('PAIR_HOLD' if fault=='wrong_scope' else scope,command))
    mode='rise_'+fault if fault in ('passive','window','wrong_goal','neighbor','wrong_direction','read_failure','no_motion','plateau') else 'rise'
    if recovery:mode=mode.replace('rise','stable' if stable else 'recover',1)
    process=subprocess.Popen([str(bridge),str(path),command,mode],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    lines=queue.Queue()
    def read():
        for line in process.stdout:lines.put(line)
        lines.put(None)
    threading.Thread(target=read,daemon=True).start()
    review=ShoulderRiseReview('11'*16,command,recovery=bool(recovery),stable=stable);terminal=None
    try:
        for _ in range(64):
            line=lines.get(timeout=10);assert line is not None
            doc=json.loads(line)
            if doc.get('terminal'):terminal=doc;break
            raw=line.rstrip('\r\n').encode();review.accept(raw)
            if fault=='export_abort' and doc['sequence']==1:
                process.stdin.write('ABORT\n');process.stdin.flush();continue
            evidence=export_and_sign(tmp_path/'exports',raw,key=bytes(range(32)),boot='11'*16,
                command=command,sequence=doc['sequence'])
            receipt=evidence['receipt']
            if fault=='bad_receipt' and doc['sequence']==1:receipt=receipt[:-1]+bytes([receipt[-1]^1])
            delay=5100000 if (fault=='late_observation' and doc['sequence']==(4 if stable else 2) or
                            fault=='late_final_export' and doc['sequence']==(7 if stable else 5)) else 100000
            process.stdin.write(f'DELAY:{delay}:'+receipt.hex()+'\n');process.stdin.flush()
        assert terminal and terminal['broadcasts']==0
        assert terminal['complete']==(fault=='late_final_export')
        assert terminal['writes']==(0 if fault in ('wrong_scope','passive','window','bad_receipt','export_abort') else 1)
        assert process.wait(timeout=5)==0,process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)


@pytest.mark.parametrize('mode',['pair','passive','enabled','prep','prep_slow_export','rise','rise_slow','recover','recover_slow','stable','stable_slow'])
def test_complete_host_runner_drives_native_owner(tmp_path,bridge,mode):
    from rocell.application.first_motion_contract import canonical
    from rocell.application.shoulder_session_runner import run_shoulder_session
    process=None;pending=None;raw=None;sequence=0;lines=queue.Queue()
    mixed=mode!='pair'
    stable=mode.startswith('stable')
    recovering=stable or mode.startswith('recover')
    preparing=mode.startswith('prep');rising=recovering or mode.startswith('rise')
    command='shoulder-stable-clearance24-v1' if stable else 'shoulder-clearance24-v1' if recovering else 'shoulder-rise12-v1' if rising else 'pose-preparation-v1' if preparing else 'mixed-shoulder-target-v1' if mixed else 'r23-shoulder-hold'
    def exchange(method,path,body,timeout):
        nonlocal process,pending,raw,sequence
        suffix=path.rsplit('/',1)[1]
        if suffix=='prepare':return canonical(dict(schema='rocell.start_challenge.v1',
            boot_id='11'*16,nonce='00'*32,issued_us=0,expires_us=30_000_000))
        if suffix=='start':
            token=tmp_path/'synthetic-runner-start.bin';token.write_bytes(bytes.fromhex(body.decode()))
            process=subprocess.Popen([str(bridge),str(token),command]+([mode] if mixed else []),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            def read():
                for line in process.stdout:lines.put(line.rstrip('\r\n').encode())
                lines.put(None)
            threading.Thread(target=read,daemon=True).start()
            raw=lines.get(timeout=10);pending=json.loads(raw)
            return canonical(dict(status='SESSION_ACTIVATED'))
        if suffix=='status':return canonical(dict(schema='rocell.shoulder_session_status.v1',
            boot_id='11'*16,command_id=command,sequence=sequence,
            state=('COMPLETE' if pending['complete'] else 'FAULT') if pending.get('terminal') else 'WAITING_EXPORT',
            preload_writes=pending.get('writes',0),enable_delivery='NOT_ATTEMPTED' if mixed else 'SENT_UNACKNOWLEDGED'))
        if suffix=='record':return raw
        assert suffix=='receipt'
        delay=2100000 if mode=='prep_slow_export' and sequence%6==5 else 100000
        process.stdin.write(f'DELAY:{delay}:'+body.decode()+'\n');process.stdin.flush()
        raw=lines.get(timeout=10);pending=json.loads(raw);sequence+=1
        return canonical(dict(status='EXPORT_RECEIPT_ACCEPTED',movement_performed_by_handler=False))
    try:
        result=run_shoulder_session(tmp_path/'exports',expected_boot='11'*16,
            key=bytes(range(32)),exchange=exchange,authorized=True,
            experiment='STABLE_CLEARANCE_RECOVERY' if stable else 'CLEARANCE_RECOVERY' if recovering else 'SHOULDER_RISE' if rising else 'POSE_PREPARATION' if preparing else 'MIXED_TARGET' if mixed else 'PAIR_HOLD')
        assert result['report']['state']==('STABLE_CLEARANCE_RECOVERY_OBSERVED' if stable else 'CLEARANCE_RECOVERY_OBSERVED' if recovering else 'SHOULDER_RISE_OBSERVED' if rising else 'POSE_PREPARATION_OBSERVED' if preparing else 'MIXED_TARGET_OBSERVED' if mixed else 'CONTROLLER_HOLD_OBSERVED'),result['report']
        assert pending['complete'] and pending['writes']==(4 if preparing else 1 if mixed else 2) and pending['broadcasts']==(0 if mixed else 1)
        if mixed and not preparing and not rising:assert result['report']['selected_torque']==int(mode=='enabled')
        if rising:assert result['report']['targets']==([2419,1695] if recovering else [2443,1671])
        assert process.wait(timeout=5)==0
    finally:
        if process and process.poll() is None:process.kill();process.wait(timeout=5)


@pytest.fixture(scope='module')
def bridge(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    binary=tmp_path_factory.mktemp('shoulder-bridge')/'bridge.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_shoulder_session_bridge.cpp'),
        '-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    return binary


@pytest.mark.parametrize('mode',['success','corrupt_receipt','export_abort','corrupt_enable','corrupt_after_enable',
                                'bounded_delay','late_before_enable','late_after_enable'])
def test_real_export_receipts_drive_native_simulation(tmp_path,bridge,mode):
    start_file=tmp_path/'synthetic-start.bin'
    start_file.write_bytes(signed_start())
    process=subprocess.Popen([str(bridge),str(start_file)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,text=True)
    lines=queue.Queue()
    def reader():
        for line in process.stdout:lines.put(line)
        lines.put(None)
    thread=threading.Thread(target=reader,daemon=True);thread.start()
    records=[];exports=[];terminal=None
    review=ShoulderSessionReview('11'*16,'receipt-test')
    try:
        for _ in range(65):
            line=lines.get(timeout=15)
            assert line is not None,'native bridge exited before terminal'
            document=json.loads(line)
            if document.get('terminal'):
                terminal=document;break
            assert document['sequence']==len(records)
            review.accept(line.rstrip('\r\n').encode())
            records.append(document)
            if mode=='export_abort' and document['sequence']==1:
                process.stdin.write('ABORT\n');process.stdin.flush();continue
            # Native prints a delimiter newline; receipt binds the record bytes
            # without that transport delimiter, exactly as the native gate does.
            result=export_and_sign(tmp_path/'exports',line.rstrip('\r\n').encode(),
                key=bytes(range(32)),boot='11'*16,command='receipt-test',sequence=document['sequence'])
            exports.append(result['export_path']);token=result['receipt']
            corrupt_at={'corrupt_receipt':1,'corrupt_enable':7,'corrupt_after_enable':8}.get(mode)
            if document['sequence']==corrupt_at:
                token=token[:-1]+bytes([token[-1]^1])
            delay=100000 if mode=='bounded_delay' else (
                10000001 if mode=='late_before_enable' and document['sequence']==7 else (
                600000 if mode=='late_after_enable' and document['sequence']==8 else 0))
            process.stdin.write((f'DELAY:{delay}:' if delay else '')+token.hex()+'\n');process.stdin.flush()
        assert terminal is not None
        assert process.wait(timeout=5)==0,process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        thread.join(timeout=2)
    if mode in ('success','bounded_delay'):
        assert terminal['complete'] and terminal['writes']==2 and terminal['broadcasts']==1
        assert len(exports)==len(records)
        assert [r['event'] for r in records[:10]]==[
            'BASELINE','PRELOAD_INTENT','PRELOAD_RESULT','PRELOAD_VERIFIED',
            'PRELOAD_INTENT','PRELOAD_RESULT','PRELOAD_VERIFIED','PAIR_ENABLE_INTENT',
            'PAIR_ENABLE_SENT_UNACKNOWLEDGED','PAIR_ENABLE_READBACK']
        timed=[r for r in records if r['event']=='TIMED_HOLD_SAMPLE']
        assert len(timed)>=5 and all(r['result']==1 for r in timed)
    elif mode in ('corrupt_enable','corrupt_after_enable','late_before_enable','late_after_enable'):
        assert not terminal['complete'] and terminal['writes']==2
        assert terminal['broadcasts']==(1 if mode in ('corrupt_after_enable','late_after_enable') else 0)
        if mode=='late_after_enable':assert terminal['reason']=='HOLD_RECEIPT_GAP'
        if mode=='late_before_enable':assert terminal['reason']=='EXPORT_RECEIPT_FAILED'
    else:
        assert not terminal['complete'] and terminal['writes']==0 and terminal['broadcasts']==0


@pytest.mark.parametrize('mode', ['tampered_signature', 'wrong_scope', 'wrong_command'])
def test_signed_start_rejection_has_no_servo_effects(tmp_path, bridge, mode):
    token=signed_start('PRELOAD_ONLY' if mode=='wrong_scope' else 'PAIR_HOLD',
                       'other-command' if mode=='wrong_command' else 'receipt-test')
    if mode=='tampered_signature':
        token=token[:-1]+bytes([token[-1]^1])
    path=tmp_path/'synthetic-rejected-start.bin';path.write_bytes(token)
    run=subprocess.run([str(bridge),str(path)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout)
    assert not result['complete'] and result['writes']==0 and result['broadcasts']==0
    assert result['reason']==('AUTHENTICATION_REJECTED' if mode=='tampered_signature' else 'PLAN_REJECTED')


@pytest.mark.parametrize('fault',['wrong_scope','tampered_start','bad_receipt','export_abort','late_final_receipt'])
def test_mixed_auth_and_export_failures_stop(tmp_path,bridge,fault):
    from rocell.application.mixed_shoulder_session_review import MixedShoulderSessionReview
    command='mixed-shoulder-target-v1'
    token=signed_start('PAIR_HOLD' if fault=='wrong_scope' else 'MIXED_TARGET',command)
    if fault=='tampered_start':token=token[:-1]+bytes([token[-1]^1])
    path=tmp_path/'start.bin';path.write_bytes(token)
    process=subprocess.Popen([str(bridge),str(path),command,'enabled'],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    lines=queue.Queue()
    def read():
        for line in process.stdout:lines.put(line)
        lines.put(None)
    threading.Thread(target=read,daemon=True).start()
    review=MixedShoulderSessionReview('11'*16,command);terminal=None
    try:
        for _ in range(8):
            line=lines.get(timeout=10);assert line is not None
            doc=json.loads(line)
            if doc.get('terminal'):terminal=doc;break
            raw=line.rstrip('\r\n').encode();review.accept(raw)
            if fault=='export_abort' and doc['sequence']==1:
                process.stdin.write('ABORT\n');process.stdin.flush();continue
            evidence=export_and_sign(tmp_path/'exports',raw,key=bytes(range(32)),boot='11'*16,
                                     command=command,sequence=doc['sequence'])
            receipt=evidence['receipt']
            if fault=='bad_receipt' and doc['sequence']==1:receipt=receipt[:-1]+bytes([receipt[-1]^1])
            prefix='DELAY:2100000:' if fault=='late_final_receipt' and doc['sequence']==5 else ''
            process.stdin.write(prefix+receipt.hex()+'\n');process.stdin.flush()
        assert terminal and not terminal['complete'] and terminal['broadcasts']==0
        assert terminal['writes']==(1 if fault=='late_final_receipt' else 0)
        assert process.wait(timeout=5)==0
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
