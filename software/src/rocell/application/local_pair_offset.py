"""Offline, constant-offset shoulder hypothesis; no signing or transport.

Predict encoder position as goal + frozen residual. Project desired endpoints
onto the existing coupled goal sum rather than independently offsetting servos.
This is a local hypothesis, not calibration or live-motion admission.
"""
from dataclasses import dataclass


def pair(value):
    if (type(value) not in (list, tuple) or len(value) != 2 or
            any(type(v) is not int or not 0 <= v <= 4095 for v in value)):
        raise ValueError('Two integer servo counts required')
    return tuple(value)


@dataclass(frozen=True)
class LocalPairOffset:
    training_id: str
    goals: tuple
    positions: tuple

    def __post_init__(self):
        object.__setattr__(self, 'goals', pair(self.goals))
        object.__setattr__(self, 'positions', pair(self.positions))
        if not self.training_id or max(abs(v) for v in self.offset) > 16:
            raise ValueError('Bounded identified training observation required')

    @property
    def offset(self):
        return tuple(p-g for p, g in zip(self.positions, self.goals))

    def predict(self, goals):
        goals = pair(goals)
        if sum(goals) != sum(self.goals) or any(abs(a-b)>32 for a,b in zip(goals,self.goals)):
            raise ValueError('Outside local training goal neighborhood')
        return pair(tuple(g+b for g,b in zip(goals,self.offset)))

    def evaluate(self, *, evidence_id, goals, actual):
        if not evidence_id or evidence_id == self.training_id:
            raise ValueError('Separate evaluation evidence required')
        actual = pair(actual); predicted = self.predict(goals)
        return dict(predicted=list(predicted), actual=list(actual),
                    signed_error=[a-p for a,p in zip(actual,predicted)],
                    uncompensated_error=[a-g for a,g in zip(actual,goals)],
                    live_validated=False, physical_accuracy_verified=False)

    def propose(self, *, current_positions, current_goals, desired):
        current_positions, current_goals, desired = map(pair,(current_positions,current_goals,desired))
        predicted_current=self.predict(current_goals)
        if any(abs(p-a)>2 for p,a in zip(predicted_current,current_positions)):
            raise ValueError('Current observation contradicts local offset model')
        travel=[d-p for d,p in zip(desired,current_positions)]
        if not (-24 <= travel[0] < 0 < travel[1] <= 24):
            raise ValueError('Only bounded upward local proposal supported')
        # There are only 65 possible primary commands in this reviewed local
        # goal neighborhood. Enumerating them avoids floating rounding ambiguity.
        candidates=[]
        for primary in range(max(0,self.goals[0]-32),min(4095,self.goals[0]+32)+1):
            goals=(primary,sum(self.goals)-primary)
            if not 0<=goals[1]<=4095:continue
            try:predicted=self.predict(goals)
            except ValueError:continue
            if not (-24<=goals[0]-current_goals[0]<0<goals[1]-current_goals[1]<=24):continue
            if max(abs(g-p) for g,p in zip(goals,current_positions))>32:continue
            errors=[p-d for p,d in zip(predicted,desired)]
            score=(max(map(abs,errors)),sum(e*e for e in errors),abs(primary-current_goals[0]),primary)
            candidates.append((score,goals,predicted,errors))
        if not candidates:raise ValueError('No local coupled candidate')
        _,goals,predicted,errors=min(candidates)
        if max(map(abs,errors))>2:raise ValueError('Desired pair not achievable within two model counts')
        return dict(schema='rocell.local_pair_offset_preview.v1', training_id=self.training_id,
            frozen_offset=list(self.offset), desired=list(desired), proposed_goals=list(goals),
            predicted_positions=list(predicted), predicted_error=errors,
            goal_sum=sum(goals), hardware_access=False, movement_authorized=False,
            physical_accuracy_verified=False)
