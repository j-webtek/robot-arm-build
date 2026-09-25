"""One finite local cycle with injected device/publisher adapters, no default I/O.

The leg adapter must acquire fresh identity-matched feedback and screen the path
before each send. A publisher must durably export and verify each full leg report.
Saved reports are evidence, never a way to resume or replay a cycle.
"""
from copy import deepcopy
from .compensated_elbow_progression import clean_compensated_completion
from .elbow_local_candidate import candidate_record


class CompensatedElbowCycle:
    MODES=(3,-6)
    JOINT=3
    SCHEMA='rocell.compensated_elbow_cycle.v1'

    def candidate(self,mode):
        return candidate_record(nearby_target=True) if mode==3 else candidate_record(mapping_sample=True)

    def __init__(self, *, require_hold=False):
        if type(require_hold) is not bool:raise ValueError('Explicit hold policy required')
        self._require_hold=require_hold
        self._used=False

    def run(self, *, run_leg, publish_leg, cancelled=lambda:False):
        if self._used:
            return dict(status='CYCLE_ALREADY_USED',legs=[],motion_authorized=False)
        self._used=True  # Burn before invoking any callback, including cancellation.
        result=dict(schema=self.SCHEMA,status='INCOMPLETE',
                    legs=[],maximum_legs=len(self.MODES),automatic_retry_allowed=False,
                    automatic_recovery_return_allowed=False,physical_accuracy_verified=False)
        previous=None
        for index,mode in enumerate(self.MODES):
            if cancelled():
                result['status']='CANCELLED_BEFORE_NEXT_LEG'; break
            candidate=self.candidate(mode)
            try:
                # Adapter checks previous pose BEFORE sending, not only afterward.
                report=run_leg(index=index,mode=mode,previous_joints=deepcopy(previous),cancelled=cancelled)
            except Exception:
                result['status']='LEG_OUTCOME_UNCERTAIN'; break
            run=report.get('run') or {}; tx=run.get('transaction') or {}
            passed=(clean_compensated_completion(run)
                    and report.get('status')==run.get('status')
                    and (report.get('receipt') or {}).get('cleanup_confirmed') is True
                    and tx.get('local_candidate')==candidate
                    and tx.get('command')==dict(T=101,joint=self.JOINT,rad=candidate['command_rad'],spd=20,acc=1)
                    and (run.get('move_request',{}).get('configuration',{}).get('compensated_candidate'))==candidate)
            entry=dict(index=index,mode=mode,passed=passed,export=None)
            next_pose=deepcopy(tx['rows'][-1][3]) if passed else None
            if passed and self._require_hold:
                from .endpoint_hold_review import review_endpoint_hold
                try:
                    hold=review_endpoint_hold(report,report.get('post_completion_observation') or {})
                    passed=hold['status']=='REPORTED_HOLD_VERIFIED'
                    next_pose=hold.get('final_joints_rad') if passed else None
                    entry['hold_review']=hold
                except (ValueError,KeyError,TypeError):
                    passed=False
                entry['passed']=passed
            result['legs'].append(entry)
            try:
                receipt=publish_leg(index=index,report=deepcopy(report))
                if not isinstance(receipt,dict) or receipt.get('verified') is not True or not receipt.get('export'):
                    raise ValueError('Verified export required')
                entry['export']=receipt['export']
            except Exception:
                result['status']='EXPORT_NOT_VERIFIED'; break
            if not passed:
                result['status']='LEG_NOT_VERIFIED'; break
            previous=deepcopy(next_pose)
        else:
            result['status']='LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED'
        return result
