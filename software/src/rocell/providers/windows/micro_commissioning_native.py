"""Explicit native commissioning composition, not registered in the wizard.

CALLING run_native_micro_commissioning CAN MOVE THE ARM. Import is inert.
At most one descending 0.95 predecessor and one eligible 0.90 micro command.
No initial positioning, retry, or return is inserted. External-controller
exclusion is an operator assumption, never inferred from a local mutex.
"""
from copy import deepcopy
from pathlib import Path
import time
from threading import Event
import uuid

from rocell.application.first_motion_contract import canonical
from rocell.application.micro_commissioning_coordinator import MicroCommissioningCoordinator
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from .arm_transport_lock import arm_transport_lock
from .arm_wifi_deadline import bounded_probe,observe_bounded
from .wifi_discrete_native import run_native_roll_sweep_center_trial
from .micro_native_transport import MicroNativeBinding,NativeMicroTransport


def run_native_micro_commissioning(*,root,export_root,exclusive_controller_declared=False,
                                   cancelled=lambda:False,check_current=lambda:None):
    """Own the real mutex continuously; retain both predecessor and final reports."""
    # Reject before any lease, sender or filesystem work if declaration is absent.
    if exclusive_controller_declared is not True:
        raise ValueError('Explicit exclusive-controller declaration required')
    check_current()
    exporter=WizardDiagnosticExporter(Path(export_root).resolve())
    exporter.prepare(create=False)
    session_id='wizard-'+uuid.uuid4().hex
    saved=[]
    def save(name,report):
        receipt=exporter.export(dict(session_id=session_id,mode='physical',
                                    workflow='single_micro_commissioning'),[],
                                attachments={name:canonical(report)})
        if not verify_export(Path(receipt['path']).resolve())['valid']:
            raise ValueError('Commissioning export verification failed')
        saved.append(deepcopy(receipt))
        return receipt
    def previous(*,cancelled):
        check_current()
        return run_native_roll_sweep_center_trial(root=root,cancelled=cancelled)
    def save_previous(report,hold):
        steps=[dict(name='predecessor',report=report)]
        if hold is not None:steps.append(dict(name='predecessor_hold',report=hold))
        return save('result-predecessor.json',dict(steps=steps))['path']
    def baseline(*,cancelled):
        check_current()
        return bounded_probe(cancelled=cancelled,retain_response=True)
    def transport(admission,session):
        check_current()
        return NativeMicroTransport(MicroNativeBinding(admission,session,root=root))
    result=MicroCommissioningCoordinator().run(root=root,lease_factory=arm_transport_lock,
        clock_ns=time.perf_counter_ns,wait=Event().wait,run_predecessor=previous,
        observe_hold=observe_bounded,save_predecessor=save_previous,read_baseline=baseline,
        transport_factory=transport,save_micro=lambda report:save('result-micro.json',report),
        save_outcome=lambda report:save('result-commissioning.json',report),
        exclusive_controller_declared=True,cancelled=cancelled)
    result['exports']=saved
    return result
