"""Strict mixed-experiment review before signing each export receipt."""
import re
from .hold_initialization_model import Joint,Snapshot
from .mixed_shoulder_trial import MixedShoulderTrial
from .wizard_diagnostic_coordinator import decode_diagnostic_json


class MixedShoulderSessionReview:
    def __init__(self,boot,command,*,preparation=False):
        self.boot,self.command=boot,command
        self.count=0;self.last_finished=0;self.trial=None;self.before=None
        self.target=None;self.sid=None;self.sent=None;self.torque=None
        self.preparation=preparation;self.initial=None;self.last_scan=None;self.expected_count=6

    def accept(self,raw):
        doc=decode_diagnostic_json(raw,maximum=4095)
        seq=self.count%6 if self.preparation else self.count
        names=['BASELINE','PRELOAD_INTENT','PRELOAD_RESULT']+['PRELOAD_VERIFIED']*3
        if (seq>=6 or self.count>=self.expected_count or doc.get('schema')!='rocell.shoulder_hold_event.v1'
                or doc.get('boot_id')!=self.boot or doc.get('command_id')!=self.command
                or type(doc.get('sequence')) is not int or doc['sequence']!=self.count
                or doc.get('event')!=names[seq] or doc.get('physical_accuracy_verified') is not False):
            raise ValueError('Mixed event identity/order')
        rows=doc.get('joints')
        if type(rows) is not list or len(rows)!=7:raise ValueError('Seven joints required')
        joints=[]
        for i,r in enumerate(rows):
            if (type(r) is not list or len(r)!=5 or any(type(x) is not int for x in r[:4])
                    or r[0]!=11+i or type(r[4]) is not str or not re.fullmatch('[0-9a-f]{30}',r[4])):
                raise ValueError('Invalid joint row')
            feedback=bytes.fromhex(r[4])
            if int.from_bytes(feedback[:2],'little')!=r[1] or feedback[2] or feedback[3]:
                raise ValueError('Raw position/speed mismatch')
            joints.append(Joint(r[1],r[2],r[3],0,feedback[10]))
        scan=Snapshot(doc.get('scan_started_us'),doc.get('scan_finished_us'),tuple(joints))
        MixedShoulderTrial._validate(scan)
        if scan.started_us<=self.last_finished:raise ValueError('Scan not fresh')
        result=0 if seq<2 else 1;role='PRE_ACTION' if seq==2 else 'OBSERVATION'
        sid=0 if seq==0 else 11+self.trial.index
        if (type(doc.get('servo_id')) is not int or doc['servo_id']!=sid
                or type(doc.get('result')) is not int or doc['result']!=result
                or doc.get('snapshot_role')!=role):raise ValueError('Action identity/role')
        end=scan.finished_us
        if self.preparation and self.initial is not None:
            if any(abs(a.position-b.position)>2 for a,b in zip(self.initial.joints,scan.joints)):
                raise ValueError('Cumulative preparation drift')
        if seq==0:
            if self.preparation and self.last_scan is not None:
                if self.torque!=1 or any((a.goal,a.torque)!=(b.goal,b.torque)
                        for a,b in zip(self.last_scan.joints,scan.joints)):
                    raise ValueError('Preparation continuity lost')
            self.trial=MixedShoulderTrial(scan,auxiliary=self.preparation)
            self.torque=None
            if self.initial is None:
                self.initial=scan
                if self.preparation:self.expected_count=6*sum(j.torque==0 for j in scan.joints)
        elif seq==1:
            proposal=self.trial.propose(scan,now_us=scan.finished_us)
            self.target=proposal['target'];self.sid=proposal['servo_id'];self.before=scan
        else:
            for i,(base,new) in enumerate(zip(self.trial.baseline.joints,scan.joints)):
                expected=self.target if seq>=3 and i==self.trial.index else base.goal
                if abs(base.position-new.position)>2 or new.goal!=expected:
                    raise ValueError('Unexpected position/target')
                if (seq==2 or i!=self.trial.index) and new.torque!=base.torque:
                    raise ValueError('Unexpected torque')
                if i!=self.trial.index and new.torque and abs(new.position-new.goal)>2:
                    raise ValueError('Enabled neighbor not tracking')
                if self.preparation and new.torque and abs(new.position-new.goal)>2:
                    raise ValueError('Prepared joint not tracking')
            if seq==2:
                a,b=doc.get('action_started_us'),doc.get('action_finished_us')
                if (type(a) is not int or type(b) is not int or not end<=a<=b
                        or type(doc.get('device_error')) is not int or doc['device_error']!=0
                        or scan.joints[self.trial.index].position!=self.target):
                    raise ValueError('Invalid delivery evidence')
                self.sent=b;end=b
            else:
                torque=scan.joints[self.trial.index].torque
                if scan.started_us<=self.sent or scan.finished_us-self.sent>2_000_000:
                    raise ValueError('Post-write deadline')
                if self.torque is not None and torque!=self.torque:raise ValueError('Torque unstable')
                self.torque=torque
                if self.preparation and seq==5 and torque!=1:
                    raise ValueError('Target remained passive')
        if seq in (1,2):
            if any(type(doc.get(k)) is not int or doc[k]!=v for k,v in
                   [('requested_target',self.target),('speed',20),('acceleration',1)]):
                raise ValueError('Target/speed differs')
        self.last_finished=end;self.last_scan=scan;self.count+=1
        return doc
