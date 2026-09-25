"""Combine independent receipt/write/acquisition evidence without motion authority."""
from .first_motion_contract import canonical
from .servo_controller_receipt import assess_controller_receipt
from .servo_write_evidence import assess_write_evidence
from .servo_diagnostic_decode import decode_trace
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .servo_baseline_assessment import assess_baseline


def assess_session(snapshot, sent_bytes, command, policy, *, origin, baseline_policy=None):
    """Command and policy are frozen HOST expectations, never inferred from result.

    Snapshot is the collected/replayed object. This function validates record
    semantics; transport verification and actual device compatibility remain
    separate. A DEVICE_CAPTURE label is not authenticated provenance.
    """
    if origin not in ('SIMULATION','DEVICE_CAPTURE'):
        raise ValueError('Explicit evidence origin required')
    items=snapshot['records'];status=snapshot['status']
    baseline=None
    if len(items)>1 and items[1]['kind']=='baseline':
        baseline=items[1]['record'];items=[items[0],*items[2:]]
    if (baseline is None)!=(baseline_policy is None):
        raise ValueError('Baseline evidence/policy requirement mismatch')
    prefix=['receipt','converted','hook','dispatch','write']
    if len(items)<5 or [item['kind'] for item in items[:5]]!=prefix or any(item['kind']!='pair' for item in items[5:]):
        raise ValueError('Complete command-boundary evidence required')
    receipt,converted,hook,dispatch,write=[item['record'] for item in items[:5]]
    receipt_result=assess_controller_receipt(receipt,sent_bytes,dispatch)
    write_result=assess_write_evidence(write,dispatch)
    if decode_diagnostic_json(sent_bytes,maximum=256)!=command['payload']:
        raise ValueError('Host expected command differs from sent payload')
    fields={'schema','boot_id','command_id','servo_id','wire_count','speed','acceleration',
            'sample_count','sample_interval_us','maximum_lateness_us','maximum_pair_us'}
    if type(converted) is not dict or set(converted)!=fields or converted['schema']!='rocell.converted_command.v2':
        raise ValueError('Versioned conversion evidence required')
    for key in ('boot_id','command_id','servo_id','wire_count','speed','acceleration'):
        if converted[key]!=dispatch[key] or type(converted[key]) is not type(dispatch[key]):
            raise ValueError('Conversion/dispatch mismatch')
    for key,low,high in (('sample_count',1,2000),('sample_interval_us',1000,60000000),
                         ('maximum_lateness_us',1000,60000000),('maximum_pair_us',1,60000000)):
        if type(converted[key]) is not int or not low<=converted[key]<=high:
            raise ValueError('Invalid acquisition schedule')
    if (converted['maximum_pair_us']>converted['sample_interval_us'] or
            converted['maximum_lateness_us']!=converted['sample_interval_us'] or
            converted['maximum_pair_us']!=policy['maximum_pair_us']):
        raise ValueError('Acquisition policy mismatch')
    pairs=[item['record'] for item in items[5:]]
    if len(pairs)>converted['sample_count'] or (status['state']=='CAPTURED' and len(pairs)!=converted['sample_count']):
        raise ValueError('Incomplete or excessive acquisition set')
    hook_fields={'schema','status','write_attempted','started_us_raw','finished_us_raw','capture_stopped'}
    if type(hook) is not dict or set(hook)!=hook_fields or hook['schema']!='rocell.write_hook_outcome.v1':
        raise ValueError('Versioned write-hook outcome required')
    times=[]
    for field in ('started_us_raw','finished_us_raw'):
        value=hook[field]
        if type(value) is not str or not 1<=len(value)<=20 or not value.isascii() or not value.isdigit():
            raise ValueError('Invalid write-hook clock')
        times.append(int(value))
    if not receipt['received_us']<=times[0]<=times[1]==dispatch['device_us']<=2**63-1:
        raise ValueError('Write-hook chronology mismatch')
    expected_hook='WRITE_VERIFIED' if write_result['acknowledgment_verified'] else 'WRITE_NOT_VERIFIED'
    if (hook['write_attempted'] is not True or hook['status']!=expected_hook or
            hook['capture_stopped'] is not (not write_result['acknowledgment_verified'])):
        raise ValueError('Write-hook result mismatch')
    baseline_result=assess_baseline(baseline,receipt,dispatch,times[0],baseline_policy) if baseline is not None else None
    trace=dict(schema='rocell.servo_diagnostic_trace.v2',origin=origin,command=command,
               dispatch=dispatch,samples=pairs,policy=policy)
    endpoint=decode_trace(canonical(trace))['assessment']
    if status['state'] not in ('CAPTURED','FAULT') or type(status['storage_fault']) is not bool:
        raise ValueError('Terminal session status required')
    category='SESSION_FAULT' if status['state']=='FAULT' or status['storage_fault'] else endpoint['category']
    result=dict(schema='rocell.session_assessment.v1',category=category,receipt=receipt_result,
                write=write_result,endpoint=endpoint,progression_authority=False,
                provenance_verified=False,physical_accuracy_verified=False)
    if baseline_result is not None:result['baseline']=baseline_result
    return result
