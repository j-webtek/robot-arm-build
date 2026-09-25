import pytest
from rocell.application import local_shoulder_step_release as module
from rocell.application.shoulder_session_http import ShoulderSessionHTTP


@pytest.mark.parametrize('fault',[None,'root','port','capability','used','failed','boot','address','busy','capture'])
def test_release_binding_is_read_only_and_exact(tmp_path,monkeypatch,fault):
    software=tmp_path/'software';root=software/'runs/wizard-exports'
    adapter=ShoulderSessionHTTP('192.168.0.225',settling_capability=True,local_step_capability=True)
    binding=dict(expected_boot='11'*16,address=adapter.address)
    capture=dict(summary=dict(category='TRANSPORT_CAPTURED',status=dict(
        state='IDLE',reason='NOT_CONFIGURED',records=0,storage_fault=False)))
    calls=[]
    def review(path,export,*,revision):
        calls.append('review');assert path==software.resolve() and export=='startup' and revision==31
        return binding
    def read(path,reader,*,expected_boot):
        calls.append('capture');assert expected_boot=='11'*16
        return capture
    monkeypatch.setattr(module,'review_recovery_startup',review)
    monkeypatch.setattr(module,'capture_hold_transport',read)
    if fault=='root':root=tmp_path/'other'
    if fault=='port':adapter.port=81
    if fault=='capability':adapter.settling_capability=False
    if fault=='used':adapter.attempts.add(('prepare',b''))
    if fault=='failed':adapter.failed=True
    if fault=='boot':binding['expected_boot']='22'*16
    if fault=='address':binding['address']='192.168.0.226'
    if fault=='busy':capture['summary']['status']['state']='ACTIVE'
    if fault=='capture':capture['summary']['category']='INCONCLUSIVE'
    kwargs=dict(software_root=software,startup_export='startup',boot='11'*16,exchange=adapter)
    if fault:
        with pytest.raises(ValueError):module.bind_local_step(root,**kwargs)
        if fault in ('root','port','capability','used','failed'):assert calls==[]
        if fault in ('boot','address'):assert calls==['review']
    else:
        result=module.bind_local_step(root,**kwargs)
        assert result['revision']==31 and calls==['review','capture']
    assert not root.exists()  # No reservation, POST or mutation by this binding test.
