"""Finite predecessor-to-micro coordinator; no default providers or auto-run.

Production composition must supply the native lease, existing predecessor action,
bounded observation and durable diagnostic exporters. The starting pose must
already permit the descending predecessor. No high-position move is inserted.
"""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
from threading import Lock
import uuid

from rocell.safety.micro_control_session import MicroControlSession
from rocell.safety.micro_command_admission import MicroCommandAdmission,predecessor
from rocell.application.micro_hardware_runner import run_micro_transaction
from rocell.application.micro_result_summary import summarize_micro_result


class _Stop(Exception):
    pass


class MicroCommissioningCoordinator:
    """One-use workflow. Caller cancellation stops progression, never retries."""
    def __init__(self):
        self._lock=Lock();self._used=False

    def run(self, *, root, lease_factory, clock_ns, wait, run_predecessor,
            observe_hold, save_predecessor, read_baseline, transport_factory,
            save_micro, save_outcome, exclusive_controller_declared, cancelled=lambda:False):
        with self._lock:
            if self._used:raise ValueError('Commissioning coordinator already used')
            self._used=True
        result=dict(schema='rocell.micro_commissioning.v1',status='STOPPED',phase='SETUP',
            predecessor=None,predecessor_hold=None,micro=None,final_export_succeeded=False,
            automatic_retry_allowed=False,automatic_return_allowed=False,
            external_controller_exclusion_proven=False,physical_accuracy_verified=False)
        def check():
            if cancelled():raise _Stop('CANCELLED')
        def finish():
            try:
                result['summary']=summarize_micro_result(result)
                result['final_export']=save_outcome(deepcopy(result))
                result['final_export_succeeded']=True
            except Exception:
                result.update(status='STOPPED',reason='FINAL_EXPORT_FAILED',final_export_succeeded=False)
                if 'summary' in result:
                    result['summary']['status']='STOPPED'
        if exclusive_controller_declared is not True:
            result['reason']='EXCLUSIVE_CONTROLLER_DECLARATION_REQUIRED';finish();return result
        session=MicroControlSession(lease_factory=lease_factory,clock_ns=clock_ns)
        try:
            with session.scope():
                try:
                    check();result['phase']='PREDECESSOR'
                    session.predecessor_intent()
                    report=run_predecessor(cancelled=cancelled)
                    result['predecessor']=deepcopy(report)
                    if report.get('status')=='SUCCEEDED':
                        check();result['phase']='PREDECESSOR_HOLD'
                        result['predecessor_hold']=observe_hold(cancelled=cancelled)
                    # Save even failed predecessor attempts. Never loop for a preferred endpoint.
                    result['phase']='PREDECESSOR_EXPORT'
                    path=Path(save_predecessor(result['predecessor'],result['predecessor_hold'])).resolve()
                    result['predecessor_export']=str(path)
                    check()
                    if report.get('status')!='SUCCEEDED':raise _Stop('PREDECESSOR_FAILED')
                    digest=hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()
                    prior=predecessor(path,digest,require_micro_range=False)
                    result['predecessor_manifest_sha256']=digest
                    angle=math.degrees(prior['pose'][4])
                    if abs(angle-1.25)<=.05:
                        result.update(status='NO_CORRECTION_NEEDED',reason='PREDECESSOR_IN_DESIRED_BAND')
                    elif not 1.35<=angle<=1.45:
                        raise _Stop('PREDECESSOR_OUTSIDE_MICRO_START_RANGE')
                    else:
                        check();result['phase']='MICRO_BASELINE'
                        baseline=read_baseline(cancelled=cancelled)
                        check()
                        admission=MicroCommandAdmission(root=root,attempt_id=uuid.uuid4().hex,
                            predecessor_path=path,predecessor_sha256=digest,baseline=baseline,now_ns=clock_ns())
                        session.bind(admission)
                        check();result['phase']='MICRO_TRANSACTION'
                        transport=transport_factory(admission,session)
                        def export_micro(report):
                            result['micro_export']=save_micro(report)
                        micro=run_micro_transaction(admission,transport=transport,clock_ns=clock_ns,
                            wait=wait,observe_hold=observe_hold,export=export_micro,cancelled=cancelled)
                        result['micro']=micro
                        result['status']=micro['status']
                        result['reason']=micro.get('reason',micro.get('classification'))
                except _Stop as error:
                    result.update(status='STOPPED',reason=str(error))
                except Exception:
                    result.update(status='STOPPED',reason='COORDINATOR_EVIDENCE_OR_IO_FAILURE')
                finally:
                    # Keep participating-controller ownership through final export.
                    finish()
        except Exception:
            result.update(status='STOPPED',reason='LEASE_ACQUISITION_OR_RELEASE_FAILED')
            finish()
        return result
