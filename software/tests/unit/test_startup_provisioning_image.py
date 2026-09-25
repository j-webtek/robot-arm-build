"""Synthetic filesystem and keys only; no controller access or real staging."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from test_diagnostic_provisioning_image import library, image
from test_native_provisioning_validator import policy
from rocell.application.first_motion_contract import canonical
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import stage_startup_image


@pytest.fixture(scope='module')
def validator(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2]
    exe=tmp_path_factory.mktemp('startup-policy')/'validate.exe'
    subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/configured-diagnostic-candidate-r6/RoArm-M3_example'),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/validate_startup_provisioning_policy.cpp'),'-o',str(exe)],
        check=True,capture_output=True,timeout=60)
    return NativeProvisioningValidator(exe,hashlib.sha256(exe.read_bytes()).hexdigest())


def startup_policy():
    normal=policy()
    startup=dict(policy_id=normal['policy_id'],mode='ZERO_GOAL_TWO_SCAN',reviewed_mode=0,
        joints=normal['whole_arm_policy']['joints'],drift_tolerance=2,
        minimum_separation_us=100000,maximum_wait_us=1000000,
        maximum_pair_us=1000,maximum_scan_us=100000,maximum_age_us=100000)
    return dict(schema='rocell.controller_startup.v1',controller_policy=normal,startup_policy=startup)


def test_review_draft_requires_canonical_serialization(validator):
    raw = (Path(__file__).resolve().parents[2] / 'docs/startup-r6-policy-draft.json').read_bytes()
    encoded = canonical(json.loads(raw))
    assert validator(raw) is False
    assert validator(encoded) is True
    assert hashlib.sha256(encoded).hexdigest() == '75047d49f29468cf69374198321be3f19d56b35a8f98340781458cae56b0a216'


def stage(source,library,validator,document=None):
    return stage_startup_image(source,hashlib.sha256(source).hexdigest(),
        canonical(startup_policy() if document is None else document), b'K'*32,
        littlefs=library,validate_policy=validator)


def test_real_native_validation_and_distinct_preserved_paths(library,validator):
    source=image(library,existing=True)  # Existing normal-mode key must survive.
    candidate,report=stage(source,library,validator)
    assert report['schema']=='rocell.offline_startup_provisioning_image.v1'
    assert report['existing_entries_preserved']==3 and report['remount_verified']
    assert not report['device_modified'] and report['physical_authority']=='NONE'
    context=library.UserContext(buffer=bytearray(candidate))
    fs=library.LittleFS(context=context,mount=False,block_size=4096,block_count=352,read_size=256,prog_size=256)
    fs.mount()
    try:
        with fs.open('/rocell-diagnostics.key','rb') as stream:assert stream.read()==b'preserve me'
        with fs.open('/rocell-startup.key','rb') as stream:assert stream.read()==b'K'*32
        with fs.open('/rocell-startup.json','rb') as stream:assert stream.read()==canonical(startup_policy())
    finally:fs.unmount()
    with pytest.raises(ValueError,match='already exist'):stage(candidate,library,validator)


@pytest.mark.parametrize('fault',['normal','mode','window','id','boolean','conversion'])
def test_invalid_configuration_rejected_before_staging(library,validator,fault):
    document=startup_policy()
    if fault=='normal':document=policy()
    if fault=='mode':document['startup_policy']['mode']='NORMAL'
    if fault=='window':document['startup_policy']['joints']=[[0,4095]]*7
    if fault=='id':document['startup_policy']['policy_id']='other'
    if fault=='boolean':document['startup_policy']['reviewed_mode']=True
    if fault=='conversion':document['controller_policy']['conversion_version']='wrong'
    with pytest.raises(ValueError):stage(image(library),library,validator,document)
