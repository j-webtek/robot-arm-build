"""Offline signed compensated plan. No live routes accept this schema yet."""
import hashlib
import hmac
import json
import re
import struct
from .compensated_shoulder_contract import Pose, CompensatedShoulderContract
from .servo_start_authorization import DOMAIN, _challenge_bytes, _key
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def propose_compensated_step(records, *, boot, command, now_us):
    if (type(boot) is not str or not re.fullmatch('[0-9a-f]{32}',boot) or
        type(command) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,100}',command) or
        len(records)!=3 or any(type(raw) is not bytes or not 0<len(raw)<=4095 for raw in records)):
        raise ValueError('Three bounded records and restricted identities required')
    first=None;last=0;owner=None
    for raw in records:
        doc=decode_diagnostic_json(raw,maximum=4095)
        if (type(doc) is not dict or doc.get('schema')!='rocell.shoulder_hold_event.v1' or
            doc.get('boot_id')!=boot or doc.get('snapshot_role')!='OBSERVATION' or
            doc.get('physical_accuracy_verified') is not False):
            raise ValueError('Same-boot observation required')
        source=doc.get('command_id')
        if type(source) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,100}',source):
            raise ValueError('Invalid capture owner')
        if owner is None:owner=source
        if source!=owner:raise ValueError('Mixed capture owners')
        rows=doc.get('joints')
        if type(rows) is not list or len(rows)!=7:raise ValueError('Seven raw joint rows required')
        positions=[];goals=[];torque=[];moving=[]
        for i,row in enumerate(rows):
            if (type(row) is not list or len(row)!=5 or any(type(v) is not int for v in row[:4]) or
                row[0]!=11+i or type(row[4]) is not str or not re.fullmatch('[0-9a-f]{30}',row[4])):
                raise ValueError('Invalid raw row')
            feedback=bytes.fromhex(row[4])
            if int.from_bytes(feedback[:2],'little')!=row[1]:raise ValueError('Raw position mismatch')
            positions.append(row[1]);goals.append(row[2]);torque.append(row[3])
            moving.append(any(feedback[j] for j in (2,3,10)))
        pose=Pose(positions,goals,torque,moving,doc.get('scan_started_us'),doc.get('scan_finished_us'))
        # Age is checked on the last record; earlier records must be ordered,
        # individually valid and stable against the first fixed anchor.
        pose.validate(pose.finished_us)
        if any(pose.moving) or pose.started_us<=last or (last and pose.started_us-last<100000):
            raise ValueError('Unstable or unordered capture')
        if first is None:first=pose
        if pose.goals!=first.goals or any(abs(a-b)>1 for a,b in zip(pose.positions,first.positions)):
            raise ValueError('Reference drift')
        last=pose.finished_us
    contract=CompensatedShoulderContract.prepare(pose,now_us)
    digest=hashlib.sha256(b''.join(struct.pack('>I',len(raw))+raw for raw in records)).hexdigest()
    return dict(schema='rocell.compensated_shoulder_step.v1',boot_id=boot,command_id=command,
        reference_sha256=digest,reference_finished_us=pose.finished_us,positions=list(pose.positions),
        goals=list(pose.goals),model_id='r29-frozen-offset-v1',offsets=[10,-7],
        desired_positions=list(contract.desired),command_goals=list(contract.command_goals),
        predicted_positions=list(contract.predicted),goal_sum=4114,speed=20,acceleration=1,
        maximum_target_packets=1,arrival_tolerance_counts=2)


def sign_compensated_step(challenge,plan,key):
    _key(key);header=_challenge_bytes(challenge)
    if plan.get('schema')!='rocell.compensated_shoulder_step.v1' or plan.get('boot_id')!=challenge['boot_id']:
        raise ValueError('Compensated schema/boot required')
    raw=json.dumps(plan,separators=(',',':'),ensure_ascii=True).encode('ascii')
    if len(raw)>2048:raise ValueError('Plan budget')
    unsigned=DOMAIN+header+struct.pack('>H',len(raw))+raw
    return unsigned+hmac.digest(key,unsigned,'sha256')
