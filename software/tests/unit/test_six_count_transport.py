import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from test_six_count_recovery_start import six_inputs
from rocell.application.supported_recovery_start import sign_recovery
from rocell.application.hold_transport_snapshot import collect_recovery_snapshot, RECOVERY_STATUS, RECOVERY_RECORD
from rocell.application.supported_recovery_review import assess_recovery
from rocell.application.hold_transport_export import capture_recovery_transport, replay_recovery_transport_export, replay_recovery_transport_bundle
from rocell.application.product_ghost_export_review import _read


def test_native_six_count_listener_envelopes_and_host_collection(tmp_path):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:pytest.skip('Windows crypto/compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'listener.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_configured_six_count_recovery.cpp'),
        '-lbcrypt','-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stderr
    policy,challenge,plan=six_inputs();token=tmp_path/'token.bin'
    token.write_bytes(sign_recovery(plan,challenge,b'k'*32,approved_policy=policy,profile='six_count'))
    run=subprocess.run([str(exe),str(token)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    lines=[s.encode() for s in run.stdout.splitlines()];assert len(lines)==9
    def get(path,**kwargs):
        return lines[0] if path==RECOVERY_STATUS else lines[int(path.removeprefix(RECOVERY_RECORD))+1]
    assert collect_recovery_snapshot(get,expected_boot='11'*16)['category']=='INCONCLUSIVE'
    snapshot=collect_recovery_snapshot(get,expected_boot='11'*16,profile='six_count')
    assert snapshot['category']=='TRANSPORT_CAPTURED'
    import json
    assessment=assess_recovery(snapshot['records'],expected_plan=json.loads(plan.encoded),
        expected_policy=policy,origin='SIMULATION',profile='six_count')
    assert assessment['category']=='SIMULATED_RECOVERY_VERIFIED'
    assert assessment['endpoint']['previous_goal']==2729
    exported=capture_recovery_transport(tmp_path/'exports',get,expected_boot='11'*16,profile='six_count')
    assert exported['replay_verified'] is True
    ident=Path(exported['export_path']).name
    assert replay_recovery_transport_export(tmp_path/'exports',ident,profile='six_count')['matches']
    bundle,_=_read(tmp_path/'exports',ident,'attachment-six_count_recovery-transport.json')
    with pytest.raises(ValueError):replay_recovery_transport_bundle(bundle)
    bundle['summary']['category']='INCONCLUSIVE'
    with pytest.raises(ValueError):replay_recovery_transport_bundle(bundle,profile='six_count')
