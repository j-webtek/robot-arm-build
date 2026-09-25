"""Independent host review of local-step events; never sends commands."""
import re
from .local_shoulder_step import propose_local_step
from .wizard_diagnostic_coordinator import decode_diagnostic_json


class LocalStepReview:
    def __init__(self,boot,command):
        self.boot,self.command=boot,command
        self.count=0;self.finished=0;self.sent=None;self.arrivals=0
        self.references=[];self.plan=None;self.last_positions=None

    def authorize(self,now):
        if self.count!=3 or self.plan is not None:raise ValueError('Authorization order')
        self.plan=propose_local_step(self.references,boot=self.boot,command=self.command,now_us=now)
        return self.plan

    def accept(self,raw):
        doc=decode_diagnostic_json(raw,maximum=4095);n=self.count
        expected=['BASELINE','BASELINE_STABILITY','BASELINE_STABILITY','SHOULDER_STEP_INTENT','SHOULDER_STEP_SENT'][n] if n<5 else 'SHOULDER_STEP_SAMPLE'
        if (type(doc) is not dict or n>=64 or doc.get('schema')!='rocell.shoulder_hold_event.v1'
                or doc.get('boot_id')!=self.boot or doc.get('command_id')!=self.command
                or type(doc.get('sequence')) is not int or doc['sequence']!=n
                or doc.get('event')!=expected or doc.get('physical_accuracy_verified') is not False
                or doc.get('snapshot_role')!=('PRE_ACTION' if n==4 else 'OBSERVATION')
                or type(doc.get('servo_id')) is not int or doc['servo_id']!=0):
            raise ValueError('Local event identity/order')
        start,finish=doc.get('scan_started_us'),doc.get('scan_finished_us')
        if (type(start) is not int or type(finish) is not int or start<=self.finished
                or not 0<=finish-start<=300000):raise ValueError('Local scan timing')
        rows=doc.get('joints');positions=[];goals=[];moving=[]
        if type(rows) is not list or len(rows)!=7:raise ValueError('Seven joint rows required')
        for sid,row in enumerate(rows,11):
            if (type(row) is not list or len(row)!=5 or any(type(v) is not int for v in row[:4])
                    or row[0]!=sid or row[3]!=1 or not 0<=row[1]<=4095 or not 0<=row[2]<=4095
                    or type(row[4]) is not str or not re.fullmatch('[0-9a-f]{30}',row[4])):
                raise ValueError('Invalid local joint row')
            feedback=bytes.fromhex(row[4])
            if int.from_bytes(feedback[:2],'little')!=row[1]:raise ValueError('Raw position mismatch')
            positions.append(row[1]);goals.append(row[2]);moving.append(any(feedback[i] for i in (2,3,10)))
        if n<3:
            if any(moving) or (n and start-self.finished<100000):raise ValueError('Unstable capture')
            self.references.append(raw)
        else:
            if self.plan is None:raise ValueError('No reviewed plan')
            p=self.plan;after=n>=5
            if doc.get('requested_targets')!=p['targets'] or type(doc.get('speed')) is not int or doc['speed']!=20 or type(doc.get('acceleration')) is not int or doc['acceleration']!=1:
                raise ValueError('Local command parameters differ')
            for i,(position,goal) in enumerate(zip(positions,goals)):
                selected=i in (1,2);expected_goal=p['targets'][i-1] if selected and after else p['goals'][i]
                low=p['targets'][0] if after and i==1 else p['positions'][i]
                high=p['targets'][1] if after and i==2 else p['positions'][i]
                margin=2 if after else 1
                if goal!=expected_goal or not low-margin<=position<=high+margin or ((not selected or not after) and moving[i]):
                    raise ValueError('Local observation outside plan')
            if n==4:
                a,b=doc.get('action_started_us'),doc.get('action_finished_us')
                if type(a) is not int or type(b) is not int or not finish<=a<=b or doc.get('delivery')!='SENT_UNACKNOWLEDGED':
                    raise ValueError('Invalid send evidence')
                self.sent=b
            if after:
                if self.sent is None or start<=self.sent or finish-self.sent>5000000:raise ValueError('Arrival observation deadline')
                arrived=not any(moving) and all(abs(positions[i]-goals[i])<=2 for i in (1,2))
                self.arrivals=self.arrivals+1 if arrived else 0
        expected_result=int(self.arrivals>0) if n>=5 else 0
        if type(doc.get('result')) is not int or doc['result']!=expected_result:raise ValueError('Arrival flag mismatch')
        self.count+=1;self.finished=self.sent if n==4 else finish;self.last_positions=positions
        return doc
