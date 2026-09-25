"""Fixed two-servo evidence replay. No tuning, transport or motion authority."""
from pathlib import Path
from .first_motion_contract import canonical
from .servo_start_authorization import _hex
from .servo_diagnostic_contract import _identifier
from .servo_register_reference import PROFILE_ID, decode_feedback_block
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter

REGISTERS=((3,2),(9,2),(11,2),(21,1),(22,1),(23,1),(26,1),(27,1),
           (31,2),(33,1),(40,1),(41,1),(42,2),(46,2),(48,2),(55,1),(56,15))


def assess(document,*,expected_boot,expected_capture,origin):
    _hex(expected_boot,16);_identifier(expected_capture)
    fields={'schema','boot_id','capture_id','profile_id','byte_order','complete','reason','reads'}
    if (origin not in ('SIMULATION','DEVICE_CAPTURE') or type(document) is not dict or
        set(document)!=fields or document['schema']!='rocell.shoulder_configuration.v1' or
        document['boot_id']!=expected_boot or document['capture_id']!=expected_capture or
        document['profile_id']!=PROFILE_ID or document['byte_order']!='little' or
        type(document['complete']) is not bool or type(document['reason']) is not str or
        type(document['reads']) is not list or len(document['reads'])>34):
        raise ValueError('Invalid shoulder configuration envelope')
    values={'12':{},'13':{}};previous=0;first=None;failed=False
    for index,row in enumerate(document['reads']):
        sid=12+index//17;address,width=REGISTERS[index%17]
        if (failed or type(row) is not list or len(row)!=4 or
            any(type(v) is not int for v in row[:3]) or row[:3]!=[sid,address,width] or
            type(row[3]) is not list or len(row[3])!=7):raise ValueError('Invalid read sequence')
        seq,start,end,returned,error,success,raw=row[3]
        if any(type(v) is not int for v in (seq,start,end,returned,error)) or seq!=index or type(success) is not bool:
            raise ValueError('Invalid read metadata')
        if first is None:first=start
        good=(0<start<=end<=2**63-1 and start>=previous and end-start<=50000 and
              end-first<=1000000 and returned==width and error==0)
        if success:
            if not good or type(raw) is not str or len(raw)!=2*width:raise ValueError('Unsupported read success')
            data=bytes.fromhex(raw)
            if data.hex()!=raw:raise ValueError('Noncanonical bytes')
            values[str(sid)][str(address)]=(decode_feedback_block(data,read_status='SUCCEEDED',byte_order='little')
                if address==56 else int.from_bytes(data,'little'))
        else:
            if raw is not None:raise ValueError('Failed read exposed value')
            failed=True
        previous=end
    complete=document['complete'] and not failed and len(document['reads'])==34
    if document['complete'] and (not complete or document['reason']!='SHOULDER_CONFIG_CAPTURED'):
        raise ValueError('Incomplete capture claimed complete')
    return dict(schema='rocell.shoulder_configuration_assessment.v1',origin=origin,
        category=('SIMULATED_CONFIGURATION' if origin=='SIMULATION' else 'CONTROLLER_REPORTED_CONFIGURATION')
            if complete else 'INCONCLUSIVE',register_values_raw=values if complete else {},
        acquisition_span_us=previous-first if complete else None,
        simultaneous_snapshot=False,shoulder_alignment_verified=False,offset_correction=None,
        physical_scaling_verified=False,motion_authorized=False,configuration_changes_authorized=False)


def export_review(root,document,**subject):
    root=Path(root).resolve();assessment=assess(document,**subject)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'shoulder-configuration'},[],attachments={
        'shoulder-configuration.json':canonical(document),'shoulder-subject.json':canonical(subject),
        'shoulder-assessment.json':canonical(assessment)})
    replay(root,Path(saved['path']).name)
    return dict(export_path=saved['path'],assessment=assessment)


def replay(root,export_id):
    root=Path(root).resolve()
    doc,_=_read(root,export_id,'attachment-shoulder-configuration.json')
    subject,_=_read(root,export_id,'attachment-shoulder-subject.json')
    saved,_=_read(root,export_id,'attachment-shoulder-assessment.json')
    rebuilt=assess(doc,**subject)
    if canonical(saved)!=canonical(rebuilt):raise ValueError('Shoulder assessment does not replay')
    return rebuilt
