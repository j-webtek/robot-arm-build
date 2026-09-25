import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('fault',[None,'boot','active','storage','hold','count'])
def test_stopped_startup_admission(fault):
    path=Path(__file__).resolve().parents[2]/'scripts/restart_r21_for_pose_capture.py'
    spec=importlib.util.spec_from_file_location('pose_restart_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    boot='ab'*16
    hold=dict(schema='rocell.hold_transport.v1',instance_id=boot,state='FAULT',
        reason='HOLD_HANDED_OFF',records=0,storage_fault=False)
    pair=dict(schema='rocell.held_pair_transport.v1',boot_id=boot,state='STOPPED',
        reason='LEG_NOT_ARRIVED',records=23,storage_fault=False)
    if fault=='boot':pair['boot_id']='cd'*16
    if fault=='active':pair['state']='RUNNING'
    if fault=='storage':pair['storage_fault']=True
    if fault=='hold':hold['reason']='OTHER'
    if fault=='count':pair['records']=24
    if fault:
        with pytest.raises(ValueError):module.validate_stopped(hold,pair,boot)
    else:module.validate_stopped(hold,pair,boot)
