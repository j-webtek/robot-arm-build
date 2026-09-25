import pytest
from rocell.application.elbow_configuration_capture import capture_configuration
from rocell.application.elbow_configuration_review import REGISTERS
from rocell.application.first_motion_contract import canonical


@pytest.mark.parametrize('fault',[None,'post','get','changed','boot','short'])
def test_capture_once_and_fail_closed(tmp_path,fault):
    document=dict(schema='rocell.elbow_configuration.v1',boot_id='11'*16,capture_id='elbow-config-1',
        profile_id='waveshare-sms-sts-reference-b8b377642b3e',byte_order='little',
        complete=True,reason='CONFIG_CAPTURED',reads=[])
    for i,(address,width) in enumerate(REGISTERS):
        document['reads'].append([14,address,width,[i,100+i*10,101+i*10,width,0,True,'00'*width]])
    calls=[]
    def exchange(address,method):
        calls.append(method)
        if fault==method.lower():raise OSError('lost response')
        if fault=='boot':document['boot_id']='22'*16
        if fault=='changed' and method=='GET':document['reads'][0][3][-1]='0100'
        if fault=='short':return b'{}'
        return canonical(document)
    result=capture_configuration(tmp_path,address='192.168.0.225',expected_boot='11'*16,exchange=exchange)
    assert result['report']['category']==('CONTROLLER_REPORTED_CONFIGURATION' if fault is None else 'INCONCLUSIVE')
    assert calls==(['POST'] if fault in ('post','boot','short') else ['POST','GET'])
    before=list(calls)
    with pytest.raises(Exception):capture_configuration(tmp_path,address='192.168.0.225',expected_boot='11'*16,exchange=exchange)
    assert calls==before
