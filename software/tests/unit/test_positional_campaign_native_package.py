"""Launch actual isolated interpreter, with all native access disabled."""
import hashlib
import io
import json
import subprocess
import sys
import zipfile

import pytest
from rocell.providers.windows import positional_campaign_native_package as package


def invoke(path, digest, mode='check-imports', flags=('-I', '-S')):
    return subprocess.run([getattr(sys, '_base_executable', sys.executable), *flags,
        str(package.CHILD), str(path), digest, mode], input=b'', capture_output=True, timeout=20)


def test_deterministic_explicit_archive():
    raw = package.expected_archive()
    assert raw == package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all('rocell/' + name in names for name in package.EXTRA)
        assert not any(name.startswith(('tests/', 'runs/')) for name in names)


def test_actual_isolated_imports(tmp_path):
    path = package.prepare(tmp_path)
    child = invoke(path, hashlib.sha256(path.read_bytes()).hexdigest())
    assert child.returncode == 0, child.stderr.decode()
    report = json.loads(child.stdout)
    assert report['status'] == 'IMPORTS_OK_NOT_HARDWARE_TESTED'
    assert not any(report[key] for key in ('connected', 'physical_authority', 'live_entry_enabled', 'replay_allowed'))


@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
@pytest.mark.parametrize('version',[15,16,17,18,19,20,21,22])
def test_isolated_v15_validation_includes_lazy_dependencies(tmp_path,direction,version):
    """Decode a real-shaped intent, not merely top-level imports in the parent."""
    from test_base_speed_campaign import speed_body
    from test_roll_mapping_campaign import roll_body
    from test_roll_fixed_campaign import fixed_roll_body
    from test_roll_persistence_campaign import persistence_body
    from test_roll_long_fixed_campaign import long_fixed_body
    from test_roll_framed_campaign import framed_body
    from test_roll_variation_native import variation_body
    path=package.prepare(tmp_path)
    program='''
import sys,json,ctypes,socket,subprocess
def forbidden(*args,**kwargs):
    raise RuntimeError('NATIVE_ACCESS_FORBIDDEN')
ctypes.WinDLL=forbidden
socket.socket=forbidden
subprocess.Popen=forbidden
sys.path.insert(0,sys.argv[1])
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.application.first_motion_contract import canonical
b=PositionalCampaignIntent(canonical(json.loads(sys.stdin.buffer.read()))).to_dict()
assert (b['legs'][0]['command']['joint'],b['legs'][0]['command']['spd']) in ((1,10),(5,20))
print(b['schema'])
if b['schema'].endswith(('.v18','.v19','.v20','.v21','.v22')):
    from rocell.arm.endpoint_persistence import analyze_endpoint_persistence
    assert analyze_endpoint_persistence([],joint='r',start=b['start_joints_rad'],target=0,
        write_finished_ns=1,capture_finished_ns=1)['status']=='OBSERVATION_INCOMPLETE'
'''
    value=(variation_body('nominal' if direction=='INCREASING' else 'return-nominal') if version==22 else framed_body(1 if direction=='INCREASING' else -1) if version==21 else long_fixed_body(1 if direction=='INCREASING' else -1) if version==20 else persistence_body(1 if direction=='INCREASING' else -1,version=version) if version in (18,19)
           else speed_body(direction) if version==15
           else (fixed_roll_body if version==17 else roll_body)(1 if direction=='INCREASING' else -1))
    child=subprocess.run([getattr(sys,'_base_executable',sys.executable),'-I','-S','-c',program,str(path)],
        input=json.dumps(value).encode(),capture_output=True,timeout=20)
    assert child.returncode==0,child.stderr.decode()
    assert child.stdout.strip()==f'rocell.attended_positional_intent.v{version}'.encode()


@pytest.mark.parametrize('fault,code', [('digest', 4), ('bytes', 4), ('filename', 3), ('flags', 2), ('execute', 1)])
def test_unqualified_invocation_rejected(tmp_path, fault, code):
    path = package.prepare(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    flags, mode = ('-I', '-S'), 'check-imports'
    if fault == 'digest': digest = 'f'*64
    if fault == 'bytes': path.write_bytes(path.read_bytes() + b'changed')
    if fault == 'filename':
        other = tmp_path/'other.zip'
        other.write_bytes(path.read_bytes())
        path = other
    if fault == 'flags': flags = ('-I',)
    if fault == 'execute': mode = 'execute-campaign'
    child = invoke(path, digest, mode, flags)
    assert child.returncode == code, child.stderr.decode()
    if fault == 'execute':
        assert json.loads(child.stdout)['physical_authority'] is False
    else:
        assert child.stdout == b''
