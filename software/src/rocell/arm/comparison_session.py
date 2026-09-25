"""Finite comparison scheduling with injected I/O and no native hardware adapter.

The application must supply a single-leg wizard executor, independent export
reviewer and durable event sink. No saved event is permission to resume a session.
Native single-use admissions remain the executor's responsibility.
"""
from copy import deepcopy
import math
from threading import Lock
import uuid

JOINTS=('b','s','e','t','r','g')
LOOKUP_HASH='822965da1d902c86993a50c8647b06e672e37323b56a211a42a1c4bc6e48a910'
LEGS=(('high',2.5,2.5),('center_down',1.25,1.25),
      ('high',2.5,2.5),('lookup',.95,1.25))*2


class ComparisonSession:
    """One-use, exactly two-block session. Construction has no I/O effects."""
    PLAN=LEGS

    def __init__(self):
        self.session_id=uuid.uuid4().hex
        self._used=False
        self._lock=Lock()

    def run(self, *, execute_leg, review_leg, publish, clock, wait, cancelled=lambda:False):
        """Persist intent, execute once, review, persist evidence, then schedule.

        execute_leg(action) returns an export path even for failed movement.
        review_leg(path) returns the independently reconstructed load_leg format.
        publish(event) must complete durable storage or raise before continuation.
        A false scheduling result never revokes or retries a command already sent.
        """
        with self._lock:
            if self._used:
                raise ValueError('Session already used; never resume consumed sessions')
            self._used=True
        records=[];status='STOPPED';reason=None;phase='START';previous=None
        last_clock=None

        def now():
            nonlocal last_clock
            value=clock()
            if not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError('Finite host clock required')
            if last_clock is not None and value<last_clock:
                raise ValueError('Host clock reversed')
            last_clock=value
            return value

        def event(kind, **fields):
            publish(deepcopy(dict(schema='rocell.comparison_session_event.v1',
                session_id=self.session_id,event=kind,host_monotonic_s=now(),**fields)))

        try:
            event('START',leg_count=len(self.PLAN),clock_scope='ONE_RUN_INVOCATION',
                  independent_boot_identity_verified=False)
            for index,(action,command,desired) in enumerate(self.PLAN):
                phase='SCHEDULING'
                if cancelled():reason='CANCELLED';break
                if previous is not None:
                    # Allow evidence review its full duration; never hurry it to
                    # satisfy an experimental timing window.
                    target=previous['last_hold']['response_finished_monotonic_s']+20
                    remaining=target-now()
                    if remaining>20:
                        reason='CLOCK_DOMAIN_MISMATCH';break
                    if remaining>0:
                        wait(remaining)
                    if not target-2<=now()<=target+2:
                        reason='PRE_DISPATCH_WINDOW_MISSED';break
                if cancelled():reason='CANCELLED';break
                predecessor=None if previous is None else dict(
                    export_id=previous['summary']['export_id'],
                    manifest_file_sha256=previous['summary']['manifest_file_sha256'])
                phase='INTENT_PUBLICATION'
                event('LEG_INTENT',index=index,action=action,predecessor=predecessor)
                # Publication itself can be slow; recheck before entering I/O.
                if previous is not None and not target-2<=now()<=target+2:
                    reason='PRE_DISPATCH_WINDOW_MISSED';break
                if cancelled():reason='CANCELLED';break
                phase='EXECUTION'
                started=now()
                path=execute_leg(action)
                phase='EXPORT_PUBLICATION'
                event('LEG_EXPORT',index=index,export_path=str(path))
                phase='EVIDENCE_REVIEW'
                leg=review_leg(path)
                records.append(deepcopy(leg))
                r=leg['summary'];c=r['command'];hold=leg['last_hold']
                if not r['full_validation_success'] or hold is None:
                    reason='HOLD_INCOMPLETE' if r.get('failure_code')=='HOLD_INCOMPLETE' else 'ENDPOINT_OR_HOLD_FAILED'
                    event('LEG_REVIEW_FAILED',index=index,export_id=r['export_id'],
                        manifest_file_sha256=r['manifest_file_sha256'],reason=reason,
                        endpoint_replayed=r.get('endpoint_replayed') is True)
                    break
                if r['export_id'] in [v['summary']['export_id'] for v in records[:-1]]:
                    reason='DUPLICATE_EXPORT';break
                if (c.get('T')!=101 or c.get('joint')!=5 or c.get('spd')!=20 or c.get('acc')!=1
                        or not math.isclose(c.get('rad',math.nan),math.radians(command),abs_tol=1e-12)
                        or not math.isclose(r['desired_endpoint_deg'],desired,abs_tol=1e-12)
                        or r['command_attempts']!=1):
                    reason='COMMAND_PROTOCOL_MISMATCH';break
                candidate=r.get('candidate')
                if action.startswith('sweep_'):
                    characterization=r.get('characterization') or {}
                    if (characterization.get('protocol')!='LOCAL_COMMAND_SPACING_V1'
                            or characterization.get('command_deg')!=command
                            or characterization.get('desired_endpoint_deg')!=desired
                            or characterization.get('held_out') is not False
                            or characterization.get('model_updated') is not False):
                        reason='CHARACTERIZATION_MISMATCH';break
                if ((action=='lookup' and (not candidate or candidate.get('candidate_sha256')!=LOOKUP_HASH))
                        or (action!='lookup' and candidate is not None)):
                    reason='CANDIDATE_MISMATCH';break
                finished=hold['response_finished_monotonic_s']
                dispatch=leg['dispatch_s']
                if not started<=dispatch<=finished<=now():
                    reason='CLOCK_DOMAIN_MISMATCH';break
                interval=None
                if previous is not None:
                    interval=dispatch-previous['last_hold']['response_finished_monotonic_s']
                    if not 18<=interval<=22:
                        reason='ACTUAL_DISPATCH_WINDOW_MISSED';break
                    if leg['baseline']!=[previous['last_hold']['joints_rad'][k] for k in JOINTS]:
                        reason='PREDECESSOR_BASELINE_MISMATCH';break
                phase='EVIDENCE_PUBLICATION'
                event('LEG_VERIFIED',index=index,export_id=r['export_id'],
                    manifest_file_sha256=r['manifest_file_sha256'],predecessor=predecessor,
                    measured_interval_s=interval)
                previous=leg
            else:
                status='COMPLETED'
        except Exception:
            # Do not leak arbitrary transport response/exception content.
            reason='CALLBACK_OR_EVIDENCE_ERROR'
        result=dict(schema='rocell.comparison_session.v1',session_id=self.session_id,
            status=status,reason=reason,last_phase=phase,reviewed_legs=len(records),
            records=records,automatic_retry_allowed=False,automatic_return_allowed=False,
            resumable=False,physical_accuracy_verified=False)
        try:
            event('FINISHED',status=status,reason=reason,reviewed_legs=len(records))
        except Exception:
            result.update(status='STOPPED',reason='FINAL_PUBLICATION_FAILED')
        return result


class CommandSpacingSession(ComparisonSession):
    """Fixed six-probe sweep, with a high positioning leg before every probe."""
    PLAN=tuple(leg for action,command in (
        ('sweep_low',.85),('sweep_center',.95),('sweep_high',1.05),
        ('sweep_high',1.05),('sweep_center',.95),('sweep_low',.85))
        for leg in (('high',2.5,2.5),(action,command,1.25)))


class PairedSpacingSession(ComparisonSession):
    """Four probes in ABBA order; reuse existing admissions and stop rules.

    Each probe follows a verified high-positioning move. This characterizes
    repeatability, not validation of a newly fitted compensation model.
    """
    PLAN=tuple(leg for action,command in (
        ('sweep_center',.95),('sweep_high',1.05),
        ('sweep_high',1.05),('sweep_center',.95))
        for leg in (('high',2.5,2.5),(action,command,1.25)))


class BalancedDirectionSession(ComparisonSession):
    """Fixed ABBA: ascending control versus frozen descending lookup.

    Each probe has its own positioning move and full hold. This does not isolate
    direction from different starting angles or qualify other joints/targets.
    """
    PLAN=(('zero',0.,0.),('center_up',1.25,1.25),
          ('high',2.5,2.5),('lookup',.95,1.25),
          ('high',2.5,2.5),('lookup',.95,1.25),
          ('zero',0.,0.),('center_up',1.25,1.25))
