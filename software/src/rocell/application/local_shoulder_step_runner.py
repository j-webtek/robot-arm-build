"""Finite host workflow. Live operation requires reviewed r31 release binding.

All POST intents are durably exported before transmission. No retries or return.
"""
from pathlib import Path
import time
from .first_motion_contract import canonical
from .local_shoulder_step import sign_local_step
from .local_shoulder_step_review import LocalStepReview
from .physical_onboarding_durability import publish_reservation_bytes
from .servo_start_authorization import _hex,_key
from .shoulder_export_receipt import export_and_sign
from .shoulder_fault_settling_runner import collect_fault_settling
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def run_local_step(root,*,boot,key,exchange,authorized=False,origin='SIMULATION',
                   monotonic=time.monotonic,pause=time.sleep,software_root=None,startup_export=None):
    from .shoulder_session_http import ShoulderSessionHTTP
    if authorized is not True or origin not in ('SIMULATION','DEVICE_CAPTURE'):
        raise ValueError('Explicit authorization and origin required')
    if origin=='SIMULATION' and isinstance(exchange,ShoulderSessionHTTP):
        raise ValueError('Simulation cannot use a live adapter')
    _hex(boot,16);_key(key);root=Path(root).resolve();command='local-step-1'
    binding=None
    if origin=='DEVICE_CAPTURE':
        from .local_shoulder_step_release import bind_local_step
        binding=bind_local_step(root,software_root=software_root,startup_export=startup_export,
                               boot=boot,exchange=exchange)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    publish_reservation_bytes(root,'local-step-'+boot+'.json',canonical(dict(boot=boot,command=command)),maximum_bytes=2048)
    report=dict(schema='rocell.local_step_run.v1',boot_id=boot,command_id=command,origin=origin,
                state='IN_PROGRESS',operations=[],records=[],raw_exports=[])
    if binding is not None:report['release_binding']=binding
    review=LocalStepReview(boot,command);deadline=monotonic()+40

    def save():
        result=exporter.export({'mode':'local-step-run'},[],attachments={'local-step-run.json':canonical(report)})
        if not verify_export(Path(result['path']))['valid']:raise ValueError('Run export invalid')
        return result['path']

    def call(method,suffix,body=b'',*,settling=False):
        if monotonic()>=deadline:raise TimeoutError('Local session deadline')
        path=('/rocell/shoulder-settling/' if settling else '/rocell/local-step/')+suffix
        op=dict(method=method,path=path,outcome='INTENT');report['operations'].append(op)
        if method=='POST':save()
        remaining=deadline-monotonic()
        if remaining<=0:raise TimeoutError('Local session deadline')
        raw=exchange(method,path,body,min(3,remaining))
        if type(raw) is not bytes or not 0<len(raw)<4096:raise ValueError('Response budget')
        doc=decode_diagnostic_json(raw,maximum=4095)
        if type(doc) is not dict:raise ValueError('Object response required')
        op.update(outcome='RECEIVED',response=doc)
        return raw,doc

    def retain(raw):
        saved=exporter.export({'mode':'local-step-raw'},[],attachments={'local-step-record.txt':raw})
        path=Path(saved['path'])
        if not verify_export(path)['valid'] or (path/'attachment-local-step-record.txt').read_bytes()!=raw:
            raise ValueError('Raw export invalid')
        report['raw_exports'].append(str(path))

    try:
        save();_,challenge=call('POST','prepare')
        if challenge.get('boot_id')!=boot:raise ValueError('Startup boot differs')
        for _ in range(160):
            _,status=call('GET','status')
            if (status.get('schema')!='rocell.local_step_status.v1' or status.get('boot_id')!=boot
                    or status.get('command_id')!=command or type(status.get('sequence')) is not int
                    or status['sequence']!=review.count):raise ValueError('Local status binding mismatch')
            state=status.get('state')
            if state=='AUTHORIZATION':
                plan=review.authorize(status.get('controller_now_us'));report['plan']=plan
                token=sign_local_step(challenge,plan,key)
                _,ack=call('POST','authorize',token.hex().encode())
                if ack!={'accepted':True,'movement_performed_by_handler':False}:raise ValueError('Authorization unconfirmed')
            elif state=='WAITING_EXPORT':
                raw,_=call('GET','record');retain(raw);review.accept(raw)
                exported=export_and_sign(root,raw,key=key,boot=boot,command=command,sequence=review.count-1)
                report['records'].append(exported['export_path'])
                _,ack=call('POST','receipt',exported['receipt'].hex().encode())
                if ack!={'accepted':True,'movement_performed_by_handler':False}:raise ValueError('Receipt unconfirmed')
            elif state=='COMPLETE':
                if review.arrivals<3 or review.count<8 or type(status.get('target_packets')) is not int or status['target_packets']!=1:
                    raise ValueError('Incomplete physical-position evidence')
                report.update(state='LOCAL_STEP_OBSERVED',final_positions=review.last_positions)
                return dict(report=report,export_path=save())
            elif state=='FAULT':
                report['state']='STOPPED';report['controller_reason']=status.get('reason')
                if status.get('record_available') is True:
                    raw,doc=call('GET','record');retain(raw)
                    if doc.get('event')=='STATE_MISMATCH':
                        report['settling']=collect_fault_settling(root,raw,boot=boot,command=command,
                            sequence=review.count,key=key,pause=pause,
                            call=lambda m,s,b=b'':call(m,s,b,settling=True))
                return dict(report=report,export_path=save())
            elif state in ('CAPTURE','INTENT','WRITE','OBSERVE'):pause(0.05)
            else:raise ValueError('Unknown local state')
        raise TimeoutError('Poll limit')
    except (OSError,ValueError,TypeError,KeyError) as error:
        report.update(state='STOPPED',error_type=type(error).__name__)
        return dict(report=report,export_path=save())
