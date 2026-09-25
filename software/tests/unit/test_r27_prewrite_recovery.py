import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('fault',[None,'write_stage','wrong_hash','wrong_error','retry','missing_stop'])
def test_only_exact_prewrite_failure_can_use_recovery_startup(fault):
    path=Path(__file__).resolve().parents[2]/'scripts/recover_r26_after_r27_connect_failure.py'
    spec=importlib.util.spec_from_file_location('recovery_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=[dict(stage='RESERVED',app_sha256='c46e1ab78cb6b38c1244f1da8dd8b459340704b65af093c3b1875ed3d6158bba',
               offset=65536,bytes=1145280),
          dict(stage='STOPPED',error_type='FatalError',retry=False,
               error='Failed to connect to ESP32: Download mode successfully detected, but getting no sync reply: test')]
    if fault=='write_stage':rows.insert(1,dict(stage='WRITE_ATTEMPT_STARTED'))
    if fault=='wrong_hash':rows[0]['app_sha256']='0'*64
    if fault=='wrong_error':rows[1]['error']='write failed'
    if fault=='retry':rows[1]['retry']=True
    if fault=='missing_stop':rows.pop()
    if fault:
        with pytest.raises(ValueError):module.validate_failure(rows)
    else:module.validate_failure(rows)
