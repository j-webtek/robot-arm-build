"""Offline, signed local-step proposal. No transport or actuator API.

Use measured positions for travel limits, but preserve the existing commanded
pair sum: independently centering coupled servos on load error can make them fight.
"""
import hashlib
import hmac
import json
import re
import struct
from .servo_start_authorization import DOMAIN, _challenge_bytes, _key
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def propose_local_step(records, *, boot, command, now_us, step_counts=24):
    if not re.fullmatch('[0-9a-f]{32}',boot) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',command):
        raise ValueError('Restricted boot/command identity required')
    if type(now_us) is not int or type(step_counts) is not int or not 12<=step_counts<=24:
        raise ValueError('Integer time and 12..24-count local step required')
    if len(records)!=3 or any(type(raw) is not bytes for raw in records):
        raise ValueError('Three exact exported observation records required')
    baseline=None;last=0;positions=goals=None;source_command=None
    for index,raw in enumerate(records):
        doc=decode_diagnostic_json(raw,maximum=4095)
        if (type(doc) is not dict or doc.get('schema')!='rocell.shoulder_hold_event.v1' or doc.get('boot_id')!=boot
                or doc.get('snapshot_role')!='OBSERVATION'
                or doc.get('physical_accuracy_verified') is not False):
            raise ValueError('Same-boot raw observation required')
        if index==0:source_command=doc.get('command_id')
        if not source_command or doc.get('command_id')!=source_command:
            raise ValueError('Mixed capture owners')
        start,finish=doc.get('scan_started_us'),doc.get('scan_finished_us')
        if (type(start) is not int or type(finish) is not int or start<=last
                or not 0<=finish-start<=300_000 or (index and start-last<100_000)):
            raise ValueError('Invalid observation timing')
        rows=doc.get('joints')
        if type(rows) is not list or len(rows)!=7:raise ValueError('Seven joints required')
        for sid,row in enumerate(rows,11):
            if (type(row) is not list or len(row)!=5 or any(type(v) is not int for v in row[:4])
                    or row[0]!=sid or row[3]!=1 or not 0<=row[1]<=4095 or not 0<=row[2]<=4095
                    or type(row[4]) is not str or not re.fullmatch('[0-9a-f]{30}',row[4])):
                raise ValueError('Invalid enabled joint row')
            feedback=bytes.fromhex(row[4])
            if int.from_bytes(feedback[:2],'little')!=row[1] or any(feedback[i] for i in (2,3,10)):
                raise ValueError('Invalid or moving raw feedback')
        positions=[r[1] for r in rows];goals=[r[2] for r in rows]
        if baseline is None:baseline=(positions,goals)
        if goals!=baseline[1] or any(abs(a-b)>1 for a,b in zip(positions,baseline[0])):
            raise ValueError('Unstable reference; no automatic recentering')
        last=finish
    if not 0<=now_us-last<=2_000_000:raise ValueError('Reference capture stale')
    # First release envelope only. Broader workspace admission is not inferred.
    reference=[2047,2429,1688,2904,1591,2041,2047]
    expected_goals=[2047,2419,1695,2907,1589,2040,2047]
    if goals!=expected_goals or any(abs(a-b)>2 for a,b in zip(positions,reference)):
        raise ValueError('Outside reviewed local starting envelope')
    targets=[positions[1]-step_counts, sum(goals[1:3])-(positions[1]-step_counts)]
    travel=[targets[0]-positions[1],targets[1]-positions[2]]
    if not (-32<=travel[0]<0<travel[1]<=32 and targets[0]<goals[1] and targets[1]>goals[2]):
        raise ValueError('Pair direction or actual travel invalid')
    # Length-prefix exact record bytes so concatenation cannot be ambiguous.
    digest=hashlib.sha256(b''.join(struct.pack('>I',len(r))+r for r in records)).hexdigest()
    return dict(schema='rocell.local_shoulder_step.v1',boot_id=boot,command_id=command,
        reference_sha256=digest,reference_finished_us=last,positions=positions,goals=goals,
        targets=targets,speed=20,acceleration=1,maximum_target_packets=1)


def sign_local_step(challenge,plan,key):
    """Authenticate proposal bytes; native validation and admission remain required."""
    _key(key);header=_challenge_bytes(challenge)
    if plan.get('schema')!='rocell.local_shoulder_step.v1' or plan.get('boot_id')!=challenge['boot_id']:
        raise ValueError('Proposal/challenge binding mismatch')
    raw=json.dumps(plan,separators=(',',':'),ensure_ascii=True).encode('ascii')
    if len(raw)>2048:raise ValueError('Proposal budget')
    unsigned=DOMAIN+header+struct.pack('>H',len(raw))+raw
    return unsigned+hmac.digest(key,unsigned,'sha256')
