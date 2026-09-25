import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('fault',[None,'boot','reason','writes','sequence','state'])
def test_exact_r29_postwrite_fault_only(fault):
    path=Path(__file__).resolve().parents[2]/'scripts/restart_r24_for_pose_capture.py'
    spec=importlib.util.spec_from_file_location('restart29',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    value=dict(schema='rocell.shoulder_session_status.v1',boot_id='11'*16,
        command_id='shoulder-stable-clearance24-v1',state='FAULT',reason='RISE_STATE_CHANGED',
        sequence=5,preload_writes=1,enable_delivery='NOT_ATTEMPTED',record_available=True,
        whole_arm_ready=False,lift_authorized=False)
    if fault=='boot':value['boot_id']='22'*16
    if fault=='reason':value['reason']='OTHER'
    if fault=='writes':value['preload_writes']=2
    if fault=='sequence':value['sequence']=4
    if fault=='state':value['state']='RUNNING'
    if fault:
        with pytest.raises(ValueError):module.validate_stopped(value,'11'*16,29)
    else:
        module.validate_stopped(value,'11'*16,29)
        with pytest.raises(ValueError):module.validate_stopped(value,'11'*16,24)
