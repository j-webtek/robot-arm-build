"""Offline single-target experiment model, not a live controller.

Uses decoded snapshots on one controller clock. The caller must separately
verify raw records, boot identity and provenance. No transport or torque command
exists here. An observed torque transition is a finding, not permission to move.
"""
from .hold_initialization_model import Snapshot


class MixedShoulderTrial:
    progression_authority = False

    def __init__(self, baseline, *, max_age_us=500_000, auxiliary=False):
        if type(max_age_us) is not int or max_age_us <= 0:
            raise ValueError('Positive explicit age budget required')
        self.max_age_us = max_age_us
        self._validate(baseline)
        shoulders = baseline.joints[1:3]
        if not auxiliary and sorted(j.torque for j in shoulders) != [0, 1]:
            raise ValueError('Exactly one passive shoulder required')
        candidates=[i for i in (0,4,5,6) if baseline.joints[i].torque==0]
        if auxiliary and (not candidates or any(baseline.joints[i].torque!=1 for i in (1,2,3))):
            raise ValueError('Enabled shoulders/elbow and passive auxiliary required')
        if any(j.torque and abs(j.position-j.goal)>2 for j in baseline.joints):
            raise ValueError('Enabled joint not tracking')
        self.baseline = baseline
        self.index = candidates[0] if auxiliary else (1 if shoulders[0].torque == 0 else 2)
        self.state = 'READY'
        self.target = None
        self.before = None
        self.sent_us = None

    @staticmethod
    def _validate(scan):
        if (not isinstance(scan, Snapshot) or type(scan.started_us) is not int
                or type(scan.finished_us) is not int or scan.started_us <= 0
                or not scan.started_us <= scan.finished_us <= scan.started_us+100_000
                or len(scan.joints) != 7):
            raise ValueError('Invalid complete scan')
        for j in scan.joints:
            if (any(type(v) is not int for v in (j.position,j.goal,j.torque,j.mode,j.moving))
                    or not 0 <= j.position <= 4095 or not 0 <= j.goal <= 4095
                    or j.torque not in (0,1) or j.mode != 0 or j.moving != 0):
                raise ValueError('Invalid or moving joint')

    def propose(self, fresh, *, now_us):
        """Consume once before delivery; target comes from the fresh scan."""
        if self.state != 'READY':
            raise ValueError('Trial consumed; no retry')
        self.state = 'STOPPED'
        self._validate(fresh)
        if (type(now_us) is not int or fresh.started_us <= self.baseline.finished_us
                or not fresh.finished_us <= now_us <= fresh.finished_us+self.max_age_us):
            raise ValueError('Fresh ordered same-clock scan required')
        for old,new in zip(self.baseline.joints,fresh.joints):
            if (abs(old.position-new.position)>2 or
                    (old.goal,old.torque)!=(new.goal,new.torque)
                    or new.torque and abs(new.position-new.goal)>2):
                raise ValueError('State changed before command')
        self.before=fresh;self.target=fresh.joints[self.index].position
        self.sent_us=now_us;self.state='PROPOSED'
        return dict(servo_id=11+self.index,target=self.target,speed=20,acceleration=1,
                    potentially_actuating=True,torque_command=False,progression_authority=False)

    def assess(self, scans, *, delivery_confirmed):
        """Three later scans distinguish target readback from actual position.

        This same-pose experiment tests target/torque behavior, not travel
        accuracy. It never emits a follow-on enable or a return command.
        """
        if self.state != 'PROPOSED':
            raise ValueError('No unassessed proposal')
        self.state='STOPPED'
        if delivery_confirmed is not True:
            return dict(category='DELIVERY_UNCERTAIN',progression_authority=False)
        if len(scans)!=3:
            raise ValueError('Three post-command scans required')
        previous=self.sent_us;torques=[];errors=[]
        for scan in scans:
            self._validate(scan)
            if scan.started_us<=previous or scan.finished_us-self.sent_us>2_000_000:
                raise ValueError('Invalid post-command ordering/deadline')
            previous=scan.finished_us
            for i,(old,new) in enumerate(zip(self.before.joints,scan.joints)):
                if abs(new.position-old.position)>2:
                    raise ValueError('Unexpected pose displacement')
                if i!=self.index and (old.goal,old.torque)!=(new.goal,new.torque):
                    raise ValueError('Neighbor state changed')
            selected=scan.joints[self.index]
            if selected.goal!=self.target:
                raise ValueError('Acknowledged command did not establish target')
            torques.append(selected.torque);errors.append(selected.position-self.target)
        if torques not in ([0,0,0],[1,1,1]):
            raise ValueError('Unsettled torque state')
        self.state='OBSERVED'
        return dict(category='TARGET_OBSERVED_'+('ENABLED' if torques[0] else 'PASSIVE'),
                    servo_id=11+self.index,target=self.target,errors_counts=errors,
                    max_abs_error_counts=max(map(abs,errors)),
                    progression_authority=False,travel_accuracy_verified=False)
