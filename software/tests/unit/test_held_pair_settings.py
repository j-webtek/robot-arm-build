import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_settings import (encode_pair_settings,decode_pair_settings,
    require_pair_settings_match,export_pair_settings)
from rocell.application.native_provisioning_validator import NativeProvisioningValidator


def test_settings_roundtrip_binding_and_public_export(tmp_path):
    raw=encode_pair_settings(forward_command_id='forward',return_command_id='return')
    settings=decode_pair_settings(raw)
    digest=require_pair_settings_match(raw,dict(pair_plan=settings))
    report=export_pair_settings(tmp_path,raw)['report']
    assert report['settings_sha256']==digest and not report['provisioning_performed']
    for field,value in [('forward_command_id','different'),('offset_counts',-6),('tolerance_counts',1)]:
        with pytest.raises(ValueError):require_pair_settings_match(raw,dict(pair_plan={**settings,field:value}))


@pytest.fixture
def pair_validator(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'pair-settings.exe'
    # Exercise the actual reviewed candidate headers, not a new reimplementation.
    candidate=root/'.firmware-tools/configured-diagnostic-candidate-r10/RoArm-M3_example'
    build=subprocess.run([compiler,'-std=c++17','-I'+str(candidate),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/validators/validate_pair_provisioning.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    return NativeProvisioningValidator(exe,hashlib.sha256(exe.read_bytes()).hexdigest())


def test_host_matches_immutable_r10_parser(pair_validator):
    validator=pair_validator
    exe=validator.executable
    base=json.loads(encode_pair_settings(forward_command_id='forward',return_command_id='return'))
    cases=[canonical({**base,'offset_counts':offset,'tolerance_counts':tol})
        for offset in (-17,-16,-6,-4,-1,0,1,4,6,16,17) for tol in (0,2,3)]
    valid=canonical(base)
    cases += [valid+b'\n',b' '+valid,valid.replace(b'"offset_counts":6',b'"offset_counts":6.0'),
        valid.replace(b'"offset_counts":6',b'"offset_counts":6,"offset_counts":6'),
        canonical({**base,'offset_counts':True}),canonical({**base,'return_command_id':'forward'}),
        canonical({**base,'forward_command_id':'bad/id'}),canonical({**base,'forward_command_id':'x'*129}),
        canonical({**base,'extra':1}),b'{}',b'[]',b'']
    for raw in cases:
        try:decode_pair_settings(raw);accepted=True
        except ValueError:accepted=False
        native=subprocess.run([str(exe)],input=raw,capture_output=True,timeout=5)
        assert native.returncode in (0,2),native.stderr
        assert (native.returncode==0)==accepted,raw
        if raw:assert validator(raw)==accepted,raw
