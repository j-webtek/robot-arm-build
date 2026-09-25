"""Correlate a controller-reported authorization record, not cryptographic proof."""
from .servo_diagnostic_contract import _integer


def assess_authorization(record, plan, following):
    fields={'schema','boot_id','command_id','session_plan_sha256','received_us','expires_us',
            'authentication_verified','phase','dispatch_attempted'}
    document=plan.to_dict();command=document['command']
    if (type(record) is not dict or set(record)!=fields
            or record['schema']!='rocell.start_authorization.v1'
            or record['phase']!='BEFORE_ADMISSION'
            or record['authentication_verified'] is not True
            or record['dispatch_attempted'] is not False
            or document['schema'] not in ('rocell.session_plan.v2','rocell.session_plan.v3')
            or document['schedule']['sample_count']>9
            or record['session_plan_sha256']!=plan.sha256
            or any(record[key]!=command[key] for key in ('boot_id','command_id'))):
        raise ValueError('Authorization differs from frozen plan')
    received=_integer(record['received_us']);expires=_integer(record['expires_us'])
    if not 0<expires-received<=30000000:
        raise ValueError('Invalid authorization time window')
    for item in following:
        body=item['record']
        if item['kind']=='receipt':
            if not received<=_integer(body['received_us'])<expires:
                raise ValueError('Receipt outside authorization window')
        elif item['kind']=='hook':
            start=body.get('started_us_raw')
            if type(start) is not str or not start.isascii() or not start.isdigit() or len(start)>20:
                raise ValueError('Invalid authorized write time')
            if not received<=int(start)<expires:
                raise ValueError('Write outside authorization window')
    return dict(schema='rocell.authorization_record_assessment.v1',
        session_plan_sha256=plan.sha256,controller_reports_authenticated=True,
        plan_identity_matched=True,phase='BEFORE_ADMISSION',
        authenticated_provenance_verified=False,progression_authority=False,
        physical_motion_proven=False)
