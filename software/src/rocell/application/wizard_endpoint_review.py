"""Human-readable exact request review; never signs, approves, connects or runs."""

from .endpoint_trial_contract import EndpointTrialRequest
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .arm_bench_qualification_contract import _canonical
from rocell.motion.characterization_plan import AXES
from rocell.safety.bench_endpoint import REQUIRED_CHECKS
from rocell.safety.bench_review_authority import OPERATOR_CHECKS


def review_endpoint_request(text):
    if type(text) is not str or not 0<len(text.encode('utf-8'))<=12000:
        raise ValueError('Bounded retained endpoint request JSON required')
    request = EndpointTrialRequest(_canonical(decode_diagnostic_json(text.encode('utf-8'),maximum=12000)))
    body = request.to_dict()
    trial = next(t for t in body['campaign']['trials'] if t['trial_id']==body['trial_id'])
    rows = [{'axis':axis,'unit':'mm' if axis.endswith('_mm') else 'rad',
             'start':trial['start'][axis],'target':trial['target'][axis],
             'delta':trial['target'][axis]-trial['start'][axis]} for axis in AXES]
    return {'schema':'rocell.endpoint_request_review.v1','status':'REVIEW_ONLY_NO_AUTHORITY',
        'request_sha256':request.request_sha256,'attempt_id':body['attempt_id'],'trial_id':body['trial_id'],
        'frame':body['campaign']['frame'],'axes':rows,'spd':trial['spd'],
        'speed_meaning':'Firmware interpolation coefficient; not mm/s or duration.',
        'dwell_s':trial['dwell_s'],'timeout_s':trial['timeout_s'],
        'operator_checks':sorted(OPERATOR_CHECKS),'engineering_checks':sorted(REQUIRED_CHECKS-OPERATOR_CHECKS),
        'references':body['references'],'usb_identity':body['usb_identity'],
        'physical_authority':False,'motion_approved':False,'device_open_count':0,'serial_write_count':0,
        'limitations':['Reviewing this document does not establish current request validity or approval.',
            'All required reviews must be collected for the exact request before execution.',
            'One noncontact endpoint trial only; no automatic return, retry, keyboard or phone contact.',
            'Endpoint telemetry cannot verify continuous travel, overshoot, physical stopping or sample freshness.']}
