"""Synthetic hold HTTP boundary; all source exports and replay code are real."""
import hashlib
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_prepared_start import send_prepared_hold
from rocell.application.hold_observed_review import collect_prepared_hold_observation
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS, RECORD
from rocell.application.held_pair_preparation import prepare_held_pair
from rocell.application.held_pair_prepared_authorization import authorize_prepared_held_pair


def prepare_native_pair_source(root, hold_plan, policy, challenge, meta, monkeypatch, *, prepare_only=False,
                              forward_command_id='forward', return_command_id='return', offset_counts=6):
    document=json.loads(hold_plan.encoded)
    class AcceptedSender:
        def send(self,*args):
            body=canonical(dict(accepted=True,retry_allowed=False))
            return dict(schema='rocell.host_hold_delivery.v1',connection_attempted=True,
                transmission_attempted=True,retry_allowed=False,progression_authority=False,
                endpoint_verified=False,result='CONTROLLER_REPORTED_ACCEPTANCE',
                hold_plan_sha256=hashlib.sha256(hold_plan.encoded).hexdigest(),
                policy_sha256=document['policy_sha256'],boot_id=document['boot_id'],
                command_id=document['command_id'],response_body=body.decode(),
                response_sha256=hashlib.sha256(body).hexdigest())
    prepared=send_prepared_hold(root,AcceptedSender(),hold_plan,dict(challenge,nonce='44'*32),
                               b'k'*32,approved_policy=policy)
    records=meta['hold_records']
    def get(self,path,**kwargs):
        if path==STATUS:
            return canonical(dict(schema='rocell.hold_transport.v1',instance_id=document['boot_id'],
                state='CAPTURED',reason='ELBOW_HOLD_CAPTURED',records=len(records),record_bytes=4096,
                storage_fault=False,durable_export_verified=False))
        index=int(path.removeprefix(RECORD))
        row=records[index]
        return canonical(dict(schema='rocell.hold_record.v1',instance_id=document['boot_id'],
            index=index,kind=row['kind'],record=json.loads(row['raw_json'])))
    with monkeypatch.context() as patch:
        patch.setattr(HoldHTTPReader,'_get',get)
        observed=collect_prepared_hold_observation(root,Path(prepared['export_path']).name,
                                                  address='127.0.0.1')
    assert observed['assessment']['category']=='CONTROLLER_REPORTED_HOLD_VERIFIED'
    pair=prepare_held_pair(root,Path(observed['export_path']).name,
                          forward_command_id=forward_command_id,return_command_id=return_command_id,
                          offset_counts=offset_counts)
    if prepare_only:
        return pair
    from rocell.application.held_pair_challenge_http import request_pair_challenge
    from rocell.application.held_pair_receipt_workflow import authorize_pair_from_receipt
    from test_servo_diagnostic_start_http import once_server
    from test_servo_diagnostic_http import response
    with once_server(response(canonical(challenge))) as (port,requests):
        receipt=request_pair_challenge(root,operation='prepare',expected_boot=challenge['boot_id'],
                                       address='127.0.0.1',port=port)
    assert len(requests)==1
    workflow=authorize_pair_from_receipt(root,Path(receipt['export_path']).name,
                                       Path(pair['export_path']).name,b'k'*32,leg='forward')
    assert workflow['replay_verified']
    return workflow['authorization']
