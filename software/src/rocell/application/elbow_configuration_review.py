"""Validate fixed configuration evidence; no device I/O or tuning authority."""
from pathlib import Path
from .first_motion_contract import canonical
from .servo_start_authorization import _hex
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter

REGISTERS = ((3,2),(9,2),(11,2),(26,1),(27,1),(31,2),(33,1),
             (40,1),(41,1),(46,2),(48,2),(55,1))


def assess_configuration(document, *, expected_boot, expected_capture):
    _hex(expected_boot,16)
    fields={'schema','boot_id','capture_id','profile_id','byte_order','complete','reason','reads'}
    if (type(document) is not dict or set(document)!=fields or
            document['schema']!='rocell.elbow_configuration.v1' or
            document['boot_id']!=expected_boot or document['capture_id']!=expected_capture or
            document['profile_id']!='waveshare-sms-sts-reference-b8b377642b3e' or
            document['byte_order']!='little' or type(document['complete']) is not bool or
            type(document['reason']) is not str or
            type(document['reads']) is not list or len(document['reads'])>12):
        raise ValueError('Invalid configuration identity or shape')
    values={}; previous=0; first=None; valid=True
    for i,row in enumerate(document['reads']):
        address,width=REGISTERS[i]
        if (type(row) is not list or len(row)!=4 or
                any(type(v) is not int for v in row[:3]) or row[:3]!=[14,address,width] or
                type(row[3]) is not list or len(row[3])!=7):
            raise ValueError('Unexpected register or read shape')
        seq,start,end,returned,error,success,raw=row[3]
        if (any(type(v) is not int for v in (seq,start,end,returned,error)) or
                seq!=i or type(success) is not bool):
            raise ValueError('Invalid read metadata')
        if first is None:first=start
        good=(0<start<=end<=2**63-1 and start>=previous and end-start<=50000
              and end-first<=500000 and returned==width and error==0)
        if success:
            if not good or type(raw) is not str or len(raw)!=2*width:
                raise ValueError('Unsubstantiated read success')
            try: data=bytes.fromhex(raw)
            except ValueError as exc:raise ValueError('Invalid register bytes') from exc
            if data.hex()!=raw:raise ValueError('Noncanonical register bytes')
            values[str(address)]=int.from_bytes(data,'little')
        else:
            if raw is not None:raise ValueError('Failed read must not expose a value')
            valid=False
        previous=end
    if document['complete'] and (not valid or len(values)!=12 or document['reason']!='CONFIG_CAPTURED'):
        raise ValueError('Incomplete evidence claimed complete')
    complete=document['complete'] and valid and len(values)==12
    return dict(schema='rocell.elbow_configuration_assessment.v1',
        category='CONTROLLER_REPORTED_CONFIGURATION' if complete else 'INCONCLUSIVE',
        register_values_raw=values if complete else {},
        model_compatibility_verified=False, units_calibrated=False,
        motion_authorized=False, configuration_changes_authorized=False)


def export_configuration(root,document,*,expected_boot,expected_capture):
    subject=dict(expected_boot=expected_boot,expected_capture=expected_capture)
    assessment=assess_configuration(document,**subject)
    exporter=WizardDiagnosticExporter(Path(root));exporter.prepare(create=True)
    saved=exporter.export({'mode':'configuration-evidence'},[],attachments={
        'configuration.json':canonical(document),'configuration-subject.json':canonical(subject),
        'configuration-assessment.json':canonical(assessment)})
    if replay_configuration(root,Path(saved['path']).name)!=assessment:
        raise ValueError('Configuration export replay differs')
    return dict(export_path=saved['path'],assessment=assessment)


def replay_configuration(root,export_id):
    document,_=_read(Path(root),export_id,'attachment-configuration.json')
    subject,_=_read(Path(root),export_id,'attachment-configuration-subject.json')
    assessment,_=_read(Path(root),export_id,'attachment-configuration-assessment.json')
    actual=assess_configuration(document,**subject)
    if canonical(actual)!=canonical(assessment):raise ValueError('Configuration assessment changed')
    return actual
