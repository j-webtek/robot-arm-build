"""Offline compensated endpoint contract. No transport, signing or live admission.

The fixed r29 residual is a hypothesis. Arrival is judged against the desired
measured endpoint, while goal registers must match separately derived commands.
"""
from dataclasses import dataclass
from .local_pair_offset import LocalPairOffset

REFERENCE=(2047,2414,1702,2904,1591,2041,2047)
GOALS=(2047,2405,1709,2907,1589,2040,2047)
MODEL=LocalPairOffset('r29-frozen-offset-v1',(2419,1695),(2429,1688))


@dataclass(frozen=True)
class Pose:
    positions: tuple
    goals: tuple
    torque: tuple
    moving: tuple
    started_us: int
    finished_us: int

    def __post_init__(self):
        for field in ('positions','goals','torque','moving'):
            object.__setattr__(self,field,tuple(getattr(self,field)))

    def validate(self, now, *, age=1000000):
        if (any(len(v)!=7 for v in (self.positions,self.goals,self.torque,self.moving)) or
            any(type(v) is not int or not 0<=v<=4095 for v in self.positions+self.goals) or
            any(type(v) is not int or v!=1 for v in self.torque) or
            any(type(v) is not bool for v in self.moving) or
            any(type(v) is not int for v in (self.started_us,self.finished_us,now)) or
            not 0<self.started_us<=self.finished_us<=now or
            self.finished_us-self.started_us>300000 or now-self.finished_us>age):
            raise ValueError('Invalid fresh enabled pose')


@dataclass(frozen=True)
class CompensatedShoulderContract:
    reference: Pose
    desired: tuple
    command_goals: tuple
    predicted: tuple

    @classmethod
    def prepare(cls, reference, now):
        reference.validate(now,age=2000000)
        if (any(reference.moving) or reference.goals!=GOALS or
                any(abs(a-b)>2 for a,b in zip(reference.positions,REFERENCE))):
            raise ValueError('Outside compensated local reference')
        desired=(reference.positions[1]-14,reference.positions[2]+14)
        proposal=MODEL.propose(current_positions=reference.positions[1:3],
                               current_goals=reference.goals[1:3],desired=desired)
        return cls(reference,desired,tuple(proposal['proposed_goals']),tuple(proposal['predicted_positions']))

    def prewrite(self, fresh, now):
        fresh.validate(now)
        if (fresh.started_us<=self.reference.finished_us or now-self.reference.finished_us>30000000 or
            any(fresh.moving) or fresh.goals!=self.reference.goals or
            any(abs(a-b)>1 for a,b in zip(fresh.positions,self.reference.positions)) or
            not (0<fresh.positions[1]-self.command_goals[0]<=32 and
                 0<self.command_goals[1]-fresh.positions[2]<=32)):
            raise ValueError('Prewrite pose changed or expired')

    def observe(self, fresh, now, sent_us):
        fresh.validate(now)
        if type(sent_us) is not int or not self.reference.finished_us<sent_us<fresh.started_us or fresh.finished_us-sent_us>5000000:
            raise ValueError('Observation outside command window')
        for i in range(7):
            selected=i in (1,2)
            goal=self.command_goals[i-1] if selected else self.reference.goals[i]
            destination=self.desired[i-1] if selected else self.reference.positions[i]
            low=min(destination,self.reference.positions[i])-2
            high=max(destination,self.reference.positions[i])+2
            if (fresh.goals[i]!=goal or not low<=fresh.positions[i]<=high or
                    (not selected and fresh.moving[i])):
                raise ValueError('Unexpected goals, travel or neighbor motion')
        return not any(fresh.moving) and all(abs(fresh.positions[i]-self.desired[i-1])<=2 for i in (1,2))
