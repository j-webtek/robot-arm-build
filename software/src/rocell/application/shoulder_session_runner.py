"""Finite injected-transport runner. No default network adapter or live CLI.

The caller must validate installation/boot and obtain the defined hold approval.
This module never retries an exchange, restarts, homes, lifts or disables torque.
"""
from pathlib import Path
import time
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .servo_start_authorization import _hex, _key
from .shoulder_start_authorization import sign_shoulder_start
from .shoulder_export_receipt import export_and_sign
from .shoulder_session_review import ShoulderSessionReview
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def run_shoulder_session(root, *, expected_boot, key, exchange, authorized=False,
                         origin='SIMULATION', monotonic=time.monotonic,
                         software_root=None, startup_export=None, revision=23, experiment='PAIR_HOLD',
                         fault_settling=False, pause=time.sleep):
    """exchange(method, path, body, timeout_s) returns exact bytes, no retries.

    Live operation additionally binds the verified r23 installation/startup,
    fixed transport and fresh idle boot. Signing alone is not hardware authority.
    """
    if authorized is not True or origin not in ('SIMULATION','DEVICE_CAPTURE'):
        raise ValueError('Explicit authorized scope and origin required')
    if type(fault_settling) is not bool or (fault_settling and origin!='SIMULATION'):
        raise ValueError('Fault settling live revision is not released')
    if type(revision) is not int or revision not in (23,24,25,26,27,28,29):
        raise ValueError('Reviewed shoulder revision required')
    if experiment not in ('PAIR_HOLD','MIXED_TARGET','POSE_PREPARATION','SHOULDER_RISE','CLEARANCE_RECOVERY','STABLE_CLEARANCE_RECOVERY'):
        raise ValueError('Unknown experiment')
    if origin=='DEVICE_CAPTURE' and ((experiment=='STABLE_CLEARANCE_RECOVERY')!=(revision==29)):
        raise ValueError('Stable recovery experiment/revision binding not released')
    if origin=='DEVICE_CAPTURE' and ((experiment=='CLEARANCE_RECOVERY')!=(revision==28)):
        raise ValueError('Recovery experiment/revision binding not released')
    if origin=='DEVICE_CAPTURE' and ((experiment=='MIXED_TARGET')!=(revision==25)):
        raise ValueError('Experiment/revision binding not released')
    if origin=='DEVICE_CAPTURE' and ((experiment=='POSE_PREPARATION')!=(revision==26)):
        raise ValueError('Pose preparation/revision binding not released')
    if origin=='DEVICE_CAPTURE' and ((experiment=='SHOULDER_RISE')!=(revision==27)):
        raise ValueError('Shoulder rise/revision binding not released')
    from .shoulder_session_http import ShoulderSessionHTTP
    if origin=='SIMULATION' and isinstance(exchange,ShoulderSessionHTTP):
        raise ValueError('Simulation cannot use a device HTTP adapter')
    if origin=='DEVICE_CAPTURE':
        from .supported_recovery_installation import review_recovery_startup
        from .hold_transport_export import capture_hold_transport
        from .hold_transport_snapshot import HoldHTTPReader
        if software_root is None or startup_export is None or type(exchange) is not ShoulderSessionHTTP:
            raise ValueError('Receipt-bound r23 live adapter required')
        binding=review_recovery_startup(software_root,startup_export,revision=revision)
        if (binding['expected_boot']!=expected_boot or exchange.address!=binding['address']
                or exchange.port!=80 or Path(root).resolve()!=Path(software_root).resolve()/'runs/wizard-exports'):
            raise ValueError('Live binding differs')
        capture=capture_hold_transport(root,HoldHTTPReader(binding['address']),expected_boot=expected_boot)
        summary=capture['summary'];status=summary.get('status',{})
        if (summary.get('category')!='TRANSPORT_CAPTURED' or status.get('state')!='IDLE'
                or status.get('reason')!='NOT_CONFIGURED' or status.get('records')!=0
                or status.get('storage_fault') is not False):
            raise ValueError('Fresh same-boot idle status required')
    _hex(expected_boot, 16); _key(key)
    root=Path(root).resolve(); exporter=WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    rising=experiment in ('SHOULDER_RISE','CLEARANCE_RECOVERY','STABLE_CLEARANCE_RECOVERY')
    command=('shoulder-stable-clearance24-v1' if experiment=='STABLE_CLEARANCE_RECOVERY' else 'shoulder-clearance24-v1' if experiment=='CLEARANCE_RECOVERY' else 'shoulder-rise12-v1' if experiment=='SHOULDER_RISE' else 'pose-preparation-v1' if experiment=='POSE_PREPARATION' else
             'mixed-shoulder-target-v1' if experiment=='MIXED_TARGET' else 'r23-shoulder-hold')
    publish_reservation_bytes(root, 'shoulder-session-'+expected_boot+'.json',
        canonical(dict(boot=expected_boot,command=command,origin=origin,retry_allowed=False)),maximum_bytes=2048)
    report=dict(schema='rocell.shoulder_session_run.v1',origin=origin,boot_id=expected_boot,
        command_id=command,revision=revision,experiment=experiment,state='IN_PROGRESS',operations=[],records=[],
        lift_authorized=rising)
    deadline=monotonic()+25

    def save():
        saved=exporter.export({'mode':'shoulder-session-run'},[],attachments={'shoulder-run.json':canonical(report)})
        if not verify_export(Path(saved['path']))['valid']:
            raise ValueError('Run export verification failed')
        return saved['path']

    def call(method, suffix, body=b'', *, settling=False):
        if monotonic() >= deadline: raise TimeoutError('Session deadline')
        op=dict(method=method,path=('/rocell/shoulder-settling/' if settling else '/rocell/shoulder-session/')+suffix,outcome='INTENT')
        report['operations'].append(op)
        # GETs cannot advance this session. Their audit entries are persisted
        # together with the next mutation's intent (or terminal/failure report).
        # Avoid re-exporting the entire growing history twice per read.
        if method=='POST': save()
        remaining=deadline-monotonic()
        if remaining <= 0: raise TimeoutError('Session deadline')
        raw=exchange(method,op['path'],body,min(3,remaining))
        if type(raw) is not bytes or not 0 < len(raw) < 4096:
            raise ValueError('Response budget')
        doc=decode_diagnostic_json(raw,maximum=4095)
        if type(doc) is not dict: raise ValueError('Object response required')
        op['outcome']='RECEIVED';op['response']=doc
        if method=='POST': save()
        return raw,doc

    try:
        save()
        _,challenge=call('POST','prepare')
        if challenge.get('boot_id') != expected_boot: raise ValueError('Boot changed')
        token=sign_shoulder_start(challenge,command,experiment,key)
        _,reply=call('POST','start',token.hex().encode('ascii'))
        if reply != {'status':'SESSION_ACTIVATED'}: raise ValueError('Start not verified')
        from .mixed_shoulder_session_review import MixedShoulderSessionReview
        from .shoulder_rise_review import ShoulderRiseReview
        review=(ShoulderRiseReview(expected_boot,command,recovery=experiment=='CLEARANCE_RECOVERY',stable=experiment=='STABLE_CLEARANCE_RECOVERY') if rising else
                MixedShoulderSessionReview(expected_boot,command,preparation=experiment=='POSE_PREPARATION')
                if experiment in ('MIXED_TARGET','POSE_PREPARATION') else ShoulderSessionReview(expected_boot,command))
        for _ in range(128):
            _,status=call('GET','status')
            if (status.get('schema')!='rocell.shoulder_session_status.v1'
                    or status.get('boot_id')!=expected_boot or status.get('command_id')!=command
                    or type(status.get('sequence')) is not int or status['sequence']!=review.count):
                raise ValueError('Status identity or sequence mismatch')
            state=status.get('state')
            if state=='COMPLETE':
                if rising:
                    if (review.count<(8 if experiment=='STABLE_CLEARANCE_RECOVERY' else 6) or review.arrivals<3 or status.get('preload_writes')!=1
                            or status.get('enable_delivery')!='NOT_ATTEMPTED'):
                        raise ValueError('Incomplete shoulder rise evidence')
                    report['state']='STABLE_CLEARANCE_RECOVERY_OBSERVED' if experiment=='STABLE_CLEARANCE_RECOVERY' else 'CLEARANCE_RECOVERY_OBSERVED' if experiment=='CLEARANCE_RECOVERY' else 'SHOULDER_RISE_OBSERVED'
                    report['targets']=review.targets
                    report['final_positions']=[j.position for j in review.last_scan.joints]
                    return dict(report=report,export_path=save())
                if experiment=='POSE_PREPARATION':
                    if (review.count!=review.expected_count or review.torque!=1
                            or not 6<=review.count<=24 or status.get('preload_writes')!=review.count//6
                            or status.get('enable_delivery')!='NOT_ATTEMPTED'
                            or any(j.torque!=1 for j in review.last_scan.joints)):
                        raise ValueError('Incomplete pose preparation evidence')
                    report['state']='POSE_PREPARATION_OBSERVED'
                    return dict(report=report,export_path=save())
                if experiment=='MIXED_TARGET':
                    if review.count!=6 or status.get('preload_writes')!=1 or status.get('enable_delivery')!='NOT_ATTEMPTED':
                        raise ValueError('Incomplete mixed-target evidence')
                    report['state']='MIXED_TARGET_OBSERVED'
                    report['selected_torque']=review.torque
                    return dict(report=report,export_path=save())
                if review.count<15 or status.get('preload_writes')!=2 or status.get('enable_delivery')!='SENT_UNACKNOWLEDGED':
                    raise ValueError('Incomplete hold evidence')
                report['state']='CONTROLLER_HOLD_OBSERVED';return dict(report=report,export_path=save())
            if state=='FAULT':
                # Retain a reported failure snapshot, but never acknowledge it
                # or send a recovery action. Failure of this GET is not retried.
                if status.get('record_available') is True:
                    raw,_=call('GET','record')
                    if fault_settling:
                        from .shoulder_fault_settling_runner import collect_fault_settling
                        def settling_call(method,suffix,body=b''):
                            return call(method,suffix,body,settling=True)
                        report['settling']=collect_fault_settling(root,raw,boot=expected_boot,
                            command=command,sequence=review.count,key=key,call=settling_call,pause=pause)
                        report['state']='STOPPED';report['error_type']='ControllerMotionFault'
                        return dict(report=report,export_path=save())
                raise ValueError('Controller fault; no progression')
            if state=='RUNNING': continue
            if state!='WAITING_EXPORT': raise ValueError('Unexpected state')
            raw,_=call('GET','record')
            review.accept(raw)
            evidence=export_and_sign(root,raw,key=key,boot=expected_boot,command=command,sequence=review.count-1)
            report['records'].append(evidence['export_path'])
            # call(POST) persists this exact-export reference and intervening
            # read responses before sending the advancement receipt.
            _,ack=call('POST','receipt',evidence['receipt'].hex().encode('ascii'))
            if ack!={'status':'EXPORT_RECEIPT_ACCEPTED','movement_performed_by_handler':False}:
                raise ValueError('Receipt acceptance uncertain')
        raise TimeoutError('Poll budget exhausted')
    except (OSError,ValueError,TypeError) as error:
        report['state']='STOPPED';report['error_type']=type(error).__name__
        return dict(report=report,export_path=save())
