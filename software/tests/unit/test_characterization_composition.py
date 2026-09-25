from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_characterization_composition.cpp'
    binary=tmp_path_factory.mktemp('composition')/'composition.exe'
    build=subprocess.run([compiler,'-std=c++17',str(source),'-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    return binary


def test_authenticated_board_composition(binary):
    run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    assert 'composition_bytes=' in run.stdout


@pytest.mark.parametrize('pattern',['legacy','matched','smoke'])
def test_signed_host_admission_through_composition(binary,pattern):
    from rocell.application.characterization_request_auth import verify_response
    from rocell.application.characterization_challenge import decode_challenge
    from rocell.application.characterization_admission import sign_campaign
    from rocell.application.shoulder_characterization import draft_manifest
    process=subprocess.Popen([str(binary),pattern],stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        body=process.stdout.readline().strip().encode()
        signature=bytes.fromhex(process.stdout.readline().strip())
        verified=verify_response(key=bytes(range(32)),boot='11'*16,sequence=1,
                                 status=200,body=body,signature=signature)
        decoded=decode_challenge(bytes.fromhex(verified.decode()),expected_boot='11'*16)
        assert decoded['manifest']['goals']==[
            leg['command_goals'] for leg in draft_manifest((2405,1709),pattern=pattern)['legs']]
        token=sign_campaign(decoded['manifest'],decoded['challenge'],bytes(range(32)),
                            campaign=decoded['campaign'],reference=decoded['reference'])
        output,error=process.communicate(token.hex()+'\n',timeout=10)
        assert process.returncode==0,error
        assert 'composition_bytes=' in output
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=5)


@pytest.mark.parametrize('pattern,plan_name',[('mapping_batch','r48'),
                                              ('separated_mapping_batch','r49'),
                                              ('fine_lookup_validation','r50'),
                                              ('local_interval_campaign','r51'),
                                              ('ghost_pair_transition_campaign','r52')])
def test_mapping_batch_signed_admission_uses_exact_frozen_manifest(binary,pattern,plan_name):
    from rocell.application.characterization_request_auth import verify_response
    from rocell.application.characterization_challenge import decode_challenge
    from rocell.application.characterization_admission import sign_campaign
    from rocell.application.local_pair_mapping_batch import plan_mapping_batch
    from rocell.application.separated_pair_mapping_batch import plan_separated_mapping_batch
    from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation
    from rocell.application.local_interval_campaign import plan_local_interval_campaign
    from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
    plan = (plan_mapping_batch() if plan_name=='r48' else
            plan_separated_mapping_batch() if plan_name=='r49' else
            plan_fine_lookup_validation() if plan_name=='r50' else
            plan_local_interval_campaign() if plan_name=='r51' else
            plan_ghost_pair_transition_campaign())
    key=bytes(range(32));boot='11'*16
    process=subprocess.Popen([str(binary),pattern],stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        body=process.stdout.readline().strip().encode()
        signature=bytes.fromhex(process.stdout.readline().strip())
        verify_response(key=key,boot=boot,sequence=1,status=200,body=body,signature=signature)
        decoded=decode_challenge(bytes.fromhex(body.decode()),expected_boot=boot)
        assert decoded['manifest']['goals']==plan['manifest']['goals']
        token=sign_campaign(decoded['manifest'],decoded['challenge'],key,
                            campaign=decoded['campaign'],reference=decoded['reference'])
        output,error=process.communicate(token.hex()+'\n',timeout=10)
        assert process.returncode==0,error
        assert 'composition_bytes=' in output
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=5)


@pytest.mark.parametrize('pattern,fail_export', [('legacy',False),('matched',False),('matched',True),
                                                 ('mapping_batch',False),
                                                 ('separated_mapping_batch',False),
                                                 ('fine_lookup_validation',False),
                                                 ('local_interval_campaign',False),
                                                 ('ghost_pair_transition_campaign',False)])
def test_full_native_campaign_exports_and_receipts(binary,tmp_path,monkeypatch,pattern,fail_export,hypothesis=None):
    from rocell.application.characterization_request_auth import verify_response
    from rocell.application.characterization_challenge import decode_challenge
    from rocell.application.characterization_admission import sign_campaign
    from rocell.application.characterization_record_transfer import RecordTransfer
    from rocell.application.characterization_host_session import CharacterizationHostSession
    from rocell.application import characterization_host_session as host_module
    from rocell.application.wizard_diagnostic_export import verify_export
    key=bytes(range(32));boot='11'*16
    command=[str(binary),pattern,'full']
    if hypothesis:command.append(hypothesis)
    process=subprocess.Popen(command,stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        body=process.stdout.readline().strip().encode()
        signature=bytes.fromhex(process.stdout.readline().strip())
        verify_response(key=key,boot=boot,sequence=1,status=200,body=body,signature=signature)
        decoded=decode_challenge(bytes.fromhex(body.decode()),expected_boot=boot)
        token=sign_campaign(decoded['manifest'],decoded['challenge'],key,
                            campaign=decoded['campaign'],reference=decoded['reference'])
        process.stdin.write(token.hex()+'\n');process.stdin.flush()
        host=CharacterizationHostSession(tmp_path/'exports',decoded['manifest'],key=key,
                                        boot=boot,campaign=decoded['campaign'],reference=decoded['reference'])
        last_sequence=1

        def receive():
            nonlocal last_sequence
            line=process.stdout.readline().strip()
            parts=line.split()
            assert len(parts)==4,line or process.stderr.read()
            sequence,status=int(parts[0]),int(parts[1])
            assert sequence>last_sequence
            last_sequence=sequence
            verified=verify_response(key=key,boot=boot,sequence=sequence,status=status,
                                     body=parts[2].encode(),signature=bytes.fromhex(parts[3]))
            assert status==200
            return bytes.fromhex(verified.decode())

        for leg in range(len(decoded['manifest']['goals'])):
            info=receive();assert len(info)==35 and info[0]==leg
            size=int.from_bytes(info[1:3],'big')
            transfer=RecordTransfer(boot=boot,campaign=decoded['campaign'],leg=leg,
                                    size=size,sha256=info[3:].hex())
            offset=0
            while offset<size:
                chunk=receive()
                transfer.append(boot=boot,campaign=decoded['campaign'],leg=leg,offset=offset,data=chunk)
                offset+=len(chunk)
            raw=transfer.finish()
            if pattern=='ghost_pair_transition_campaign' and leg in (2,3,4,5,8,9,10):
                from rocell.application.characterization_result_codec import decode_result
                record=decode_result(raw)
                assert (record['observations'][-1]['finished_us']-
                        record['observations'][0]['started_us'])>=2_000_000
            if fail_export and leg==3:
                def failed(*args,**kwargs):raise OSError('Injected disk export failure')
                monkeypatch.setattr(host_module,'export_result',failed)
                with pytest.raises(OSError):
                    host.export_and_sign(raw,source_boot=boot,source_campaign=decoded['campaign'])
                with pytest.raises(ValueError,match='stopped'):
                    host.export_and_sign(raw,source_boot=boot,source_campaign=decoded['campaign'])
                output,error=process.communicate('ABORT\n',timeout=10)
                assert process.returncode==0,error
                assert output.strip()=='STOPPED 4'
                return
            saved=host.export_and_sign(raw,source_boot=boot,source_campaign=decoded['campaign'])
            assert verify_export(Path(saved['export_path']))['valid']
            assert saved['assessment']['status'] in ('SETTLED_MISS','SETTLED_ACCURATE',
                                                     'SETTLED_SMALL_RESPONSE')
            # Receipt is sent only after file integrity and independent assessment pass.
            process.stdin.write(saved['receipt'].hex()+'\n');process.stdin.flush()
            assert receive()==b'\x01'
        output,error=process.communicate(timeout=10)
        assert process.returncode==0,error
        expected_legs=len(decoded['manifest']['goals'])
        assert f'COMPLETE {expected_legs}' in output
        assert len(list((tmp_path/'exports').glob('wizard-*')))==expected_legs
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=5)


def test_exact_ghost_route_retains_verified_one_count_direct_motion(binary,tmp_path,monkeypatch):
    test_full_native_campaign_exports_and_receipts(binary,tmp_path,monkeypatch,
        'ghost_pair_transition_campaign',False,hypothesis='ghost_small')


def test_exact_ghost_route_waits_for_late_reverse_response(binary,tmp_path,monkeypatch):
    test_full_native_campaign_exports_and_receipts(binary,tmp_path,monkeypatch,
        'ghost_pair_transition_campaign',False,hypothesis='ghost_delayed_reverse')
