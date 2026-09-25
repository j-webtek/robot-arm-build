"""Synthetic wrist-roll policy experiments. No transport or live admissions.

Angles are degrees, unlike the live protocol's radians. Proposed targets are
idealized setpoints, NOT calibrated servo commands. Traces model hypotheses,
not measured hardware behavior. No simulation result authorizes movement.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    time_s: float
    joints_deg: tuple


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def valid_pose(pose):
    return (type(pose) in (tuple, list) and len(pose) == 6
            and all(finite(v) and abs(v) <= 360 for v in pose))


def simulate(initial, episodes, *, desired_deg=1.25):
    """Replay at most three synthetic correction episodes with fixed limits.

    Each episode represents feedback after ONE hypothetical dispatch, with times
    relative to that dispatch. None denotes a failed/uncertain request. Three
    consecutive stable readings spanning >=0.2 s constitute synthetic settling.
    This is not the live 35-second hold qualification. Extra trace rows are
    checked too, so a late fault or drift cannot be hidden behind early settling.
    """
    if not valid_pose(initial) or not finite(desired_deg) or abs(desired_deg) > 3:
        raise ValueError('Finite six-joint pose and bounded desired roll required')
    if abs(initial[4]) > 3:
        raise ValueError('Initial roll outside simulation envelope')
    pose = tuple(initial)
    attempts = []
    travel = 0.0

    def finish(reason):
        return dict(schema='rocell.micro_correction_simulation.v1', reason=reason,
                    attempts=attempts, commanded_travel_deg=travel,
                    final_reported_deg=pose[4], simulation_only=True,
                    motion_authorized=False, hardware_response_validated=False)

    for index in range(3):
        error = desired_deg-pose[4]
        if abs(error) <= .05:
            return finish('IN_BAND')
        delta = math.copysign(min(abs(error), .10), error)
        target = pose[4]+delta
        if abs(target) > 3 or travel+abs(delta) > .30+1e-12:
            return finish('TRAVEL_LIMIT')
        # Consume the hypothetical attempt before inspecting any response.
        travel += abs(delta)
        attempt = dict(index=index, baseline_deg=pose[4], target_deg=target,
                       delta_deg=delta, samples=0)
        attempts.append(attempt)
        if index >= len(episodes) or episodes[index] is None:
            return finish('FEEDBACK_FAILED_OR_MISSING')
        trace = episodes[index]
        previous_time = 0.0
        recent = []
        for sample in trace:
            if sample is None:
                return finish('FEEDBACK_FAILED_OR_MISSING')
            if (not isinstance(sample, Observation) or not finite(sample.time_s)
                    or not valid_pose(sample.joints_deg)):
                return finish('INVALID_FEEDBACK')
            if sample.time_s <= previous_time:
                return finish('NON_MONOTONIC_FEEDBACK')
            if sample.time_s > 10 or sample.time_s-previous_time > 1:
                return finish('FEEDBACK_DEADLINE')
            previous_time = sample.time_s
            if any(abs(sample.joints_deg[j]-initial[j]) > .10 for j in (0,1,2,3,5)):
                return finish('OTHER_JOINT_DRIFT')
            if abs(sample.joints_deg[4]-pose[4]) > .25 or abs(sample.joints_deg[4]) > 3:
                return finish('ROLL_EXCURSION')
            attempt['samples'] += 1
            recent.append(sample)
        if len(recent) < 3:
            return finish('SETTLING_UNVERIFIED')
        tail = recent[-3:]
        if (tail[-1].time_s-tail[0].time_s < .20-1e-12
                or max(s.joints_deg[4] for s in tail)-min(s.joints_deg[4] for s in tail) > .01):
            return finish('SETTLING_UNVERIFIED')
        old_error = error
        old_roll = pose[4]
        pose = tuple(tail[-1].joints_deg)
        attempt['settled_deg'] = pose[4]
        error = desired_deg-pose[4]
        if abs(error) <= .05:
            return finish('IN_BAND')
        if old_error*error < 0:
            return finish('OVERSHOOT_NO_REVERSAL')
        if abs(error) >= abs(old_error)-.01 or abs(pose[4]-old_roll) < .01:
            return finish('NO_USEFUL_PROGRESS')
    return finish('ATTEMPT_LIMIT')


def settled(roll, *, first_s=.1, other_joint=0):
    """Synthetic stable trace helper; never used to fabricate hardware evidence."""
    return [Observation(first_s+i*.1, (other_joint,0,0,0,roll,0)) for i in range(3)]


def scenarios():
    initial = (0,0,0,0,1.40625,0)
    return {
        'ideal_progress': simulate(initial, [settled(1.30625), settled(1.25)]),
        'quantized_progress': simulate(initial, [settled(1.318359375), settled(1.23046875)]),
        'unchanged': simulate(initial, [settled(1.40625)]),
        'overshoot': simulate(initial, [settled(1.17)]),
        'delayed': simulate(initial, [settled(1.3, first_s=1.01)]),
        'uncertain': simulate(initial, [None]),
        'other_joint_drift': simulate(initial, [settled(1.3, other_joint=.11)]),
        'slow_progress': simulate(initial, [settled(1.38), settled(1.35), settled(1.32)]),
        'late_failure': simulate(initial, [settled(1.25)+[None]]),
    }
