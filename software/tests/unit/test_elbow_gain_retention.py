import base64
from pathlib import Path
import pytest
from rocell.application.elbow_gain_retention import retrieve_retained_gain, replay_retained_gain
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


@pytest.mark.parametrize('fault', [None, 'timeout', 'changed', 'boot', 'truncated'])
def test_single_get_never_reacquires_and_preserves_source(tmp_path, fault):
    doc=dict(schema='rocell.elbow_gain.v1',boot_id='11'*16,capture_id='elbow-gain-1',
        profile_id='roarm-m3-gain-reference-e8d5fc95a60f',byte_order='little',
        complete=True,reason='GAIN_CAPTURED',reads=[
            [14,21+i,1,[i,100+i*10,101+i*10,1,0,True,value]]
            for i,value in enumerate(('20','20','00'))])
    raw=canonical(doc)
    source=dict(schema='rocell.gain_capture_transport.v1',category='INCONCLUSIVE',
        address='192.168.0.225',retry_allowed=False,error_type='TimeoutError',
        subject=dict(expected_boot='11'*16,expected_capture='elbow-gain-1'),
        responses=[dict(method='POST',raw_base64=base64.b64encode(raw).decode())])
    exporter=WizardDiagnosticExporter(tmp_path);exporter.prepare(create=True)
    saved=exporter.export({'mode':'fixture'},[],attachments={'gain-transport.json':canonical(source)})
    ident=Path(saved['path']).name
    source_path=Path(saved['path'])/'attachment-gain-transport.json'
    before=source_path.read_bytes();calls=[]
    def exchange(address,method):
        calls.append((address,method))
        if fault=='timeout':raise TimeoutError('test')
        if fault=='changed':doc['reads'][0][3][-1]='21'
        if fault=='boot':doc['boot_id']='22'*16
        if fault=='truncated':return b'{}'
        return canonical(doc)
    with pytest.raises(ValueError):retrieve_retained_gain(tmp_path,ident,exchange=exchange)
    assert calls==[]
    completed=retrieve_retained_gain(tmp_path,ident,authorized=True,exchange=exchange)
    result=completed['report']
    replay=replay_retained_gain(tmp_path,Path(completed['export_path']).name)
    assert replay['retained_copy_verified'] is (fault is None)
    assert calls==[('192.168.0.225','GET')]
    assert result['retained_copy_verified'] is (fault is None)
    assert result['servo_commands_sent'] is result['acquisition_repeated'] is False
    assert source_path.read_bytes()==before
    with pytest.raises(Exception):retrieve_retained_gain(tmp_path,ident,authorized=True,exchange=exchange)
    assert len(calls)==1
    # Even a newly sealed export cannot make an unsupported success assertion.
    result['retained_copy_verified']=not result['retained_copy_verified']
    altered=exporter.export({'mode':'tampered-fixture'},[],
        attachments={'gain-retention.json':canonical(result)})
    with pytest.raises(ValueError):replay_retained_gain(tmp_path,Path(altered['path']).name)
