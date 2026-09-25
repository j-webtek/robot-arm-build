"""Independent review of one local 12-count mirrored shoulder step.

No transport or Cartesian-clearance claim. The sender is unacknowledged; fresh
goal registers and three settled encoder samples establish the observed result.
"""
import re
from .hold_initialization_model import Joint,Snapshot
from .mixed_shoulder_trial import MixedShoulderTrial
from .wizard_diagnostic_coordinator import decode_diagnostic_json


class ShoulderRiseReview:
    def __init__(self,boot,command,*,recovery=False,stable=False):
        self.stable=stable
        self.recovery=recovery or stable
        self.boot,self.command=boot,command
        self.count=0;self.last_finished=0;self.baseline=None;self.intent=None
        self.targets=None;self.sent=None;self.arrivals=0;self.last_scan=None

    def accept(self,raw):
        doc=decode_diagnostic_json(raw,maximum=4095)
        stability=self.stable and self.count in (1,2)
        seq=self.count-2 if self.stable and self.count>=3 else self.count
        name=['BASELINE','SHOULDER_STEP_INTENT','SHOULDER_STEP_SENT'][seq] if seq<3 else 'SHOULDER_STEP_SAMPLE'
        if stability:name='BASELINE_STABILITY'
        if (seq>=64 or doc.get('schema')!='rocell.shoulder_hold_event.v1'
                or doc.get('boot_id')!=self.boot or doc.get('command_id')!=self.command
                or type(doc.get('sequence')) is not int or doc['sequence']!=self.count
                or doc.get('event')!=name or doc.get('physical_accuracy_verified') is not False
                or type(doc.get('servo_id')) is not int or doc['servo_id']!=0
                or doc.get('snapshot_role')!=('PRE_ACTION' if seq==2 and not stability else 'OBSERVATION')):
            raise ValueError('Rise event identity/order')
        rows=doc.get('joints');joints=[];speeds=[]
        if type(rows) is not list or len(rows)!=7:raise ValueError('Seven joints required')
        for i,row in enumerate(rows):
            if (type(row) is not list or len(row)!=5 or any(type(x) is not int for x in row[:4])
                    or row[0]!=11+i or type(row[4]) is not str or not re.fullmatch('[0-9a-f]{30}',row[4])):
                raise ValueError('Joint row malformed')
            feedback=bytes.fromhex(row[4])
            if int.from_bytes(feedback[:2],'little')!=row[1] or feedback[10] not in (0,1):
                raise ValueError('Raw position/moving mismatch')
            # Validate range/type with the shared snapshot contract, then retain
            # actual motion flags separately: travel samples need not be settled.
            joints.append(Joint(row[1],row[2],row[3],0,0))
            speeds.append(bool(feedback[2] or feedback[3] or feedback[10]))
        scan=Snapshot(doc.get('scan_started_us'),doc.get('scan_finished_us'),tuple(joints))
        MixedShoulderTrial._validate(scan)
        if scan.started_us<=self.last_finished:raise ValueError('Rise scan not fresh')
        if stability:
            from rocell.kinematics.shoulder_clearance_recovery import preview_recovery
            preview_recovery([j.position for j in joints],[j.goal for j in joints])
            if (scan.started_us-self.last_finished<100000 or any(speeds)
                    or any(j.torque!=1 or j.goal!=base.goal or abs(j.position-base.position)>1
                           for j,base in zip(joints,self.baseline.joints))
                    or type(doc.get('result')) is not int or doc['result']!=0):
                raise ValueError('Recovery baseline unstable or mistimed')
            self.last_finished=scan.finished_us;self.last_scan=scan;self.count+=1
            return doc
        if seq==0:
            # Bind the host's clearance-order reasoning to the last recorded
            # folded pose, including wrist/base joints, before signing receipt0.
            reference=(2047,2455,1659,2906,1589,2040,2047)
            if self.recovery:
                from rocell.kinematics.shoulder_clearance_recovery import preview_recovery
                proposal=preview_recovery([j.position for j in joints],[j.goal for j in joints])
                self.recovery_targets=proposal['proposed_goals'][1:3]
            if (any(speeds) or any(j.torque!=1 or
                    (not (self.recovery and i in (1,2)) and abs(j.position-j.goal)>(5 if self.stable else 2))
                    for i,j in enumerate(joints))
                    or any(abs(j.position-p)>16 for j,p in zip(joints,reference))
                    or not 2439<=joints[1].position<=2471 or not 1643<=joints[2].position<=1675
                    or not 2890<=joints[3].position<=2922):
                raise ValueError('Rise baseline outside held local window')
            self.baseline=scan
        else:
            for i,(base,joint) in enumerate(zip(self.baseline.joints,joints)):
                after=seq>=3;selected=i in (1,2)
                goal=self.targets[i-1] if after and selected else base.goal
                low=self.targets[0] if after and i==1 else base.position
                high=self.targets[1] if after and i==2 else base.position
                if (joint.torque!=1 or joint.goal!=goal or not low-2<=joint.position<=high+2
                        or (not after or not selected) and (speeds[i] or
                            (not self.stable and not (self.recovery and selected) and abs(joint.position-goal)>2))):
                    raise ValueError('Rise state differs from approved envelope')
            if seq==1:
                self.intent=scan
                self.targets=self.recovery_targets if self.recovery else [joints[1].position-12,joints[2].position+12]
                if self.recovery and not (-32<=self.targets[0]-joints[1].position<0<self.targets[1]-joints[2].position<=32):
                    raise ValueError('Recovery travel bound')
            if seq==2:
                a,b=doc.get('action_started_us'),doc.get('action_finished_us')
                if (type(a) is not int or type(b) is not int or not scan.finished_us<=a<=b
                        or doc.get('delivery')!='SENT_UNACKNOWLEDGED'
                        or any(joints[i].position!=self.intent.joints[i].position for i in (1,2))):
                    raise ValueError('Rise send record differs')
                self.sent=b
            if seq>=3:
                if scan.started_us<=self.sent or scan.finished_us-self.sent>5_000_000:
                    raise ValueError('Rise observation deadline')
                arrived=not any(speeds) and all(abs(j.position-j.goal)<=2 for i,j in enumerate(joints)
                                              if not self.stable or i in (1,2))
                self.arrivals=self.arrivals+1 if arrived else 0
            if (doc.get('requested_targets')!=self.targets
                    or any(type(v) is not int for v in doc['requested_targets'])
                    or type(doc.get('speed')) is not int or doc['speed']!=20
                    or type(doc.get('acceleration')) is not int or doc['acceleration']!=1):
                raise ValueError('Rise targets/speed differ')
        expected_result=int(self.arrivals>0) if seq>=3 else 0
        if type(doc.get('result')) is not int or doc['result']!=expected_result:
            raise ValueError('Rise arrival result differs')
        self.last_finished=self.sent if seq==2 else scan.finished_us
        self.last_scan=scan;self.count+=1
        return doc
