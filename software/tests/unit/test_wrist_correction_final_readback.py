import copy
import math
import pytest
from test_wrist_correction_preview import inputs
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_preview import preview_wrist_correction
from rocell.application.wrist_correction_final_readback import validate_final_readback
from rocell.arm.protocol import encode_line
from rocell.providers.windows.wrist_correction_native_protocol import digest


def fixture():
    originals,old=inputs()
    basis='SYNTHETIC_WIRE_REHEARSAL'
    selected=preview_wrist_correction(originals,expected_basis=basis,**old)
    joints=old['samples'][-1]['joints_rad']
    line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
    windows=[[i*len(line),(i+1)*len(line),1_300_000_000+i*50_000_000,
        1_310_000_000+i*50_000_000] for i in range(3)]
    return originals,dict(basis=basis,baseline_samples=old['samples'],selection_sha256=digest(canonical(selected)),
        usb_identity=old['usb_identity'],raw=line*3,windows=windows,started_ns=1_300_000_000,
        finished_ns=1_420_000_000,now_ns=1_430_000_000,review_deadline_ns=2_000_000_000)


def test_readback_distinguishes_new_evidence_without_renewing_review():
    originals,args=fixture();before=copy.deepcopy(args)
    report=validate_final_readback(originals,**args)
    assert report['original_last_received_ns']==1_200_000_000
    assert report['final_last_received_ns']==1_410_000_000
    assert report['host_age_ns']==20_000_000 and report['review_deadline_ns']==2_000_000_000
    assert not report['motion_authorized'] and not report['device_freshness_verified']
    assert args==before


@pytest.mark.parametrize('fault',['stale','future','deadline','duration','bytes','reads','partial','selection','unit','moved','gap','reorder'])
def test_invalid_readbacks_never_validate(fault):
    originals,args=fixture()
    if fault=='stale': args['now_ns']=1_510_000_001
    elif fault=='future': args['now_ns']=1_400_000_000
    elif fault=='deadline': args['review_deadline_ns']=args['now_ns']
    elif fault=='duration': args['started_ns']-=300_000_000
    elif fault=='bytes': args['raw']=b'x'*8193
    elif fault=='reads': args['windows']*=6
    elif fault=='partial': args['raw']=args['raw'][:-1]
    elif fault=='selection': args['selection_sha256']='0'*64
    elif fault=='unit': args['usb_identity']={}
    elif fault=='gap': args['windows'][1][2:]=[1_410_000_000,1_410_000_000]
    elif fault=='reorder': args['windows'].reverse()
    elif fault=='moved':
        joints=dict(args['baseline_samples'][-1]['joints_rad']);joints['b']+=math.radians(1)
        line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
        args['raw']=line*3
        for i,row in enumerate(args['windows']): row[:2]=[i*len(line),(i+1)*len(line)]
    with pytest.raises((ValueError,TypeError)):
        validate_final_readback(originals,**args)
