"""Offline state machine for one bounded T102 identification leg.

No transport or authority is supplied here. The adapter must hold the transport
lock, verify hardware identity, bind the exact payload and publish the report.
Faulting prevents further progression; it cannot cancel servo motion in flight.
"""
from copy import deepcopy
import math

from .all_joint_command import JOINT_FIELDS, identification_command
from rocell.application.controller_route_preview import _baseline
from rocell.application.asynchronous_response_review import review_response_envelope
from rocell.application.wrist_tip_review import modeled_tip


class AllJointTransaction:
    """Uncompensated elbow/wrist identification at fixed 20/1 settings.

    Provisional model-space criteria: <=0.5 degrees per changed joint; <=6 mm
    observed hypothetical tip travel; <=0.5 mm endpoint error and <=0.004 rad
    error on every joint, maintained with a one-count stable tail for 2 seconds.
    These are commissioning criteria, not physical accuracy or clearance claims.
    """
    def __init__(self, model, baseline, *, baseline_finished_s, overrides, wrist_single=False, normalized_candidate=False,elbow_single=False):
        _, joints, consistent = _baseline(baseline)
        if not consistent:
            raise ValueError('Baseline model mismatch')
        if not set(overrides) <= {'elbow', 'wrist'}:
            raise ValueError('Elbow/wrist identification only')
        command = identification_command(joints, overrides, speed=20, acceleration=1)
        target = [command[k] for k in JOINT_FIELDS]
        nearby=type(elbow_single) is str and elbow_single=='nearby'
        reverse=type(elbow_single) is str and elbow_single in ('reverse','reverse-speed40')
        if (type(elbow_single) is not bool and not nearby and not reverse) or (elbow_single and (wrist_single or normalized_candidate or set(overrides)!={'elbow'})):
            raise ValueError('Exclusive isolated elbow probe required')
        probe=None
        if elbow_single:
            from rocell.application.press_elbow_probe import frozen_probe
            if reverse:
                from rocell.application.local_elbow_return_probe import frozen_probe
                probe=frozen_probe(speed_comparison=elbow_single=='reverse-speed40')
            else:probe=frozen_probe(nearby=nearby)
            if target[2]!=probe['target_rad'] or any(abs(a-b)>1e-8 for a,b in zip(joints,probe['baseline_joints_rad'])):
                raise ValueError('Exact reviewed elbow start/target required')
            command=probe['command']
        if type(wrist_single) is not bool or (wrist_single and set(overrides)!={'wrist'}):
            raise ValueError('Single-joint comparison requires wrist-only override')
        if wrist_single:
            command=dict(T=101,joint=4,rad=target[3],spd=20,acc=1)
        elbow_candidate=type(normalized_candidate) is str and normalized_candidate=='elbow'
        if elbow_candidate:
            if wrist_single or elbow_single or set(overrides)!={'elbow'}:
                raise ValueError('Exclusive compensated elbow trial required')
            command=dict(T=101,joint=3,rad=target[2],spd=20,acc=1)
        pair=normalized_candidate if type(normalized_candidate) is str and normalized_candidate in ('pair-up','pair-down') else None
        descending=type(normalized_candidate) is str and normalized_candidate in ('descending','pair-down')
        if type(normalized_candidate) is not bool and not descending and not pair and not elbow_candidate:
            raise ValueError('Explicit candidate selection required')
        candidate=None;desired=list(target)
        if normalized_candidate:
            from rocell.application.ascending_wrist_candidate import frozen_candidate
            if descending:
                from rocell.application.descending_wrist_transfer import frozen_candidate
            if elbow_candidate:
                from rocell.application.local_elbow_bias_candidate import frozen_candidate
            if pair:
                from rocell.application.repeated_wrist_pair import pair_candidate
                candidate=pair_candidate(model,joints,pair.removeprefix('pair-'))
            else:candidate=frozen_candidate()
            if (not (wrist_single or elbow_candidate) or command!=candidate['command']
                    or any(abs(a-b)>1e-8 for a,b in zip(joints,candidate['baseline_joints_rad']))):
                raise ValueError('Frozen candidate exact start and payload required')
            desired=list(candidate['desired_joints_rad'])
        if not any(a != b for a, b in zip(joints, target)):
            raise ValueError('A nonzero identification step is required')
        # Only the fixed T101 response probe may exceed the original half-degree
        # scope. This does not enlarge T102 trials or relax endpoint criteria.
        response_probe=(wrist_single and target[3] in (-.080,-.052))
        if response_probe and abs(joints[3]-(-.065961174))>2*math.pi/4096:
            raise ValueError('Fixed wrist response probe starting interval exceeded')
        limit=math.radians(1.5) if descending else .016 if response_probe or normalized_candidate or elbow_single else math.radians(.5)
        if max(abs(a-b) for a,b in zip(joints,target)) > limit:
            raise ValueError('Identification delta exceeds reviewed scope')
        envelope = review_response_envelope(model,joints,target,extra_steps=1)
        if envelope['status'] != 'NO_SAMPLED_EXCEEDANCE':
            raise ValueError('Sampled response envelope rejected')
        self._time(baseline_finished_s)
        self.model = model
        self.start, self.target = tuple(joints), tuple(target)
        self.desired, self.candidate = tuple(desired), candidate
        self.probe=probe
        self.observed_joint_limit_rad=math.radians(1.5 if descending else 1)
        self._command = command
        self.baseline = deepcopy(baseline)
        self.preview = envelope
        self.last = baseline_finished_s
        self.dispatch_s = None
        self.receipt_s = None
        self.state = 'PREPARED'
        self.reason = None
        self.rows = []
        self.stable_since = None
        self.stable_anchor = None

    @staticmethod
    def _time(value):
        if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
            raise ValueError('Finite nonnegative monotonic timestamp required')

    @property
    def command(self):
        return dict(self._command)

    def fault(self, reason):
        self.state, self.reason = 'FAULT', reason

    def dispatch(self, now_s):
        self._time(now_s)
        if self.state != 'PREPARED':
            raise ValueError('Exactly one dispatch attempt is allowed')
        if not 0 <= now_s-self.last <= 1:
            self.fault('STALE_BASELINE')
            raise ValueError('Fresh baseline required')
        # Mark attempted BEFORE calling any transport; uncertain delivery cannot retry.
        self.state, self.dispatch_s, self.last = 'OBSERVING', now_s, now_s
        return self.command

    def observe(self, report, *, now_s):
        if self.state != 'OBSERVING':
            raise ValueError('No observation after terminal outcome or before dispatch')
        try:
            self._time(now_s)
            if not 0 < now_s-self.last <= 1:
                raise ValueError('FEEDBACK_TIMING_INVALID')
            if now_s-self.dispatch_s > 10:
                raise ValueError('ENDPOINT_DEADLINE')
            _, joints, consistent = _baseline(report)
            if not consistent:
                raise ValueError('MODEL_MISMATCH')
            tip = modeled_tip(self.model,joints)
            travel = math.dist(tip,modeled_tip(self.model,self.start))
            residual = [a-b for a,b in zip(joints,self.desired)]
            wire_residual = [a-b for a,b in zip(joints,self.target)]
            tip_error = math.dist(tip,modeled_tip(self.model,self.desired))
            wire_error = math.dist(tip,modeled_tip(self.model,self.target))
            self.rows.append(dict(observed_s=now_s,raw_feedback=deepcopy(report),
                reported_joints_rad=joints,signed_joint_residual_rad=residual,
                desired_tip_error_mm=tip_error,wire_tip_error_mm=wire_error,
                signed_wire_joint_residual_rad=wire_residual,tip_displacement_mm=travel))
            if travel > 6:
                raise ValueError('OBSERVED_TIP_ENVELOPE_EXCEEDED')
            if any(abs(a-b)>self.observed_joint_limit_rad for a,b in zip(joints,self.start)):
                raise ValueError('OBSERVED_JOINT_ENVELOPE_EXCEEDED')
            if any(abs(observed-start)>.004
                   for start,goal,observed in zip(self.start,self.target,joints)
                   if start==goal):
                raise ValueError('NON_TEST_JOINT_DRIFT')
            # Endpoint tolerance alone can accept an unchanged baseline for small
            # steps. Require signed progress on each deliberately changed joint.
            progress = all((observed-start)/(goal-start) >= .5
                for start,goal,observed in zip(self.start,self.desired,joints)
                if goal != start)
            self.rows[-1]['directional_progress_verified'] = progress
            in_band = progress and tip_error <= .5 and max(map(abs,residual)) <= .004
            stable = self.stable_anchor is not None and max(
                abs(a-b) for a,b in zip(joints,self.stable_anchor)) <= 2*math.pi/4096
            if not in_band:
                self.stable_since = self.stable_anchor = None
            elif not stable:
                self.stable_since, self.stable_anchor = now_s, tuple(joints)
            elif now_s-self.stable_since >= 2:
                self.state = 'REPORTED_SETTLED_PENDING_EXPORT'
            self.last = now_s
        except (ValueError, TypeError, KeyError) as exc:
            self.fault(str(exc))

    def acknowledge(self, now_s):
        """Start the first feedback window at receipt, not before the HTTP send.

        Receipt is not arrival. Send must finish within its own one-second window;
        the ten-second completion deadline still begins at dispatch.
        """
        self._time(now_s)
        if (self.state != 'OBSERVING' or self.receipt_s is not None or self.rows
                or not self.dispatch_s <= now_s <= self.dispatch_s+1):
            self.fault('INVALID_COMMAND_RECEIPT_TIMING')
            raise ValueError('One timely command receipt required')
        self.receipt_s = self.last = now_s

    def finish_export(self, *, verified):
        """Adapter calls only after durable export verification, never on HTTP ack."""
        if self.state != 'REPORTED_SETTLED_PENDING_EXPORT':
            raise ValueError('Settled endpoint required before progression')
        if verified is not True:
            self.fault('EXPORT_NOT_VERIFIED')
        else:
            self.state = 'VERIFIED_AND_EXPORTED'

    def report(self):
        return deepcopy(dict(schema='rocell.all_joint_transaction.v1',state=self.state,
            reason=self.reason,baseline=self.baseline,command=self._command,
            desired_joints_rad=self.desired,transmitted_joints_rad=self.target,
            compensation_applied=self.candidate is not None,candidate=self.candidate,
            identification_probe=self.probe,
            observed_joint_limit_rad=self.observed_joint_limit_rad,
            dispatch_s=self.dispatch_s,receipt_s=self.receipt_s,rows=self.rows,
            preview=self.preview,motion_authorized=False,physical_accuracy_verified=False,
            automatic_retry_allowed=False,automatic_return_allowed=False,
            progression_ready=self.state=='VERIFIED_AND_EXPORTED'))

    def snapshot(self):
        """Common durable-reservation interface; returns an isolated report."""
        return self.report()
