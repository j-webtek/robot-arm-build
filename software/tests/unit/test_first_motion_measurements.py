"""Synthetic measurement intake tests; no actual arm observations are invented."""
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.first_motion_measurements import validate_measurements, record_measurements
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket


def values():
    return dict(operator_id='synthetic-observer',unit_serial='A'*32,
        method='NONCONTACT_ANGLE_REFERENCE',angle_deg=0,angle_uncertainty_deg=1,
        distal_radius_mm=170,radius_uncertainty_mm=5,
        observation_notes='Synthetic test only; no physical measurement occurred.',
        acknowledge_measured=True)


def test_uncertainty_expands_the_interval_and_radius():
    result=validate_measurements(values())
    assert result['reported_wrist_interval_deg']==[-1,1]
    assert result['reported_distal_radius_upper_bound_mm']==175
    assert result['within_proposal_numeric_bounds']


@pytest.mark.parametrize('change', [dict(angle_deg=5),dict(angle_uncertainty_deg=6),
    dict(distal_radius_mm=199,radius_uncertainty_mm=2)])
def test_out_of_proposal_is_retained_not_clamped(make_service,change):
    service,runner,_=make_service(mode='physical')
    given=dict(values(),**change)
    completed=_run(service,'record_first_motion_measurements',given)
    assert completed['status']=='SUCCEEDED',completed
    original=completed['result']['steps'][0]['report']['original']
    assert original['reported']==given
    assert not original['derived']['within_proposal_numeric_bounds']
    assert not original['motion_authorized']
    assert not runner.calls


def test_public_intake_retains_exact_original_and_exports(make_service):
    service,runner,_=make_service(mode='physical')
    ticket=_ticket(service,'record_first_motion_measurements',values())
    assert 'self-reported' in ' '.join(ticket['effects'])
    operation=_run(service,'record_first_motion_measurements',values())
    assert operation['status']=='SUCCEEDED',operation
    report=operation['result']['steps'][0]['report']
    raw=(service._log.root/report['filename']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==report['original_sha256']
    assert json.loads(raw)==report['original']
    assert report['original']['recorded_monotonic_ns']>0
    assert report['original']['measured_monotonic_ns'] is None
    assert not report['original']['measurement_accuracy_independently_verified']
    assert service._endpoint_binding is None
    assert not runner.calls
    export=_run(service,'export_logs')
    folder=Path(export['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    saved=json.loads((folder/('attachment-result-'+operation['operation_id'].removeprefix('operation-')+'.json')).read_bytes())
    assert saved['steps'][0]['report']==report
    with pytest.raises(Exception):
        record_measurements(values(),root=service._log.root,
            session_id=service.session_id,operation_id=operation['operation_id'],
            source_sha256=service.source_sha256,now_ns=report['original']['recorded_monotonic_ns'])
    assert (service._log.root/report['filename']).read_bytes()==raw


@pytest.mark.parametrize('change', [dict(acknowledge_measured=False),dict(angle_deg=True),
    dict(angle_uncertainty_deg=0),dict(distal_radius_mm=0),dict(radius_uncertainty_mm=-1),
    dict(unit_serial='COM7'),dict(method='TELEMETRY'),dict(observation_notes=''),
    dict(operator_id='../unsafe')])
def test_invalid_or_non_independent_inputs_do_not_publish(make_service,change):
    service,runner,_=make_service(mode='physical')
    with pytest.raises(WizardError):
        _ticket(service,'record_first_motion_measurements',dict(values(),**change))
    assert not runner.calls


def test_defaults_do_not_claim_measurement(make_service):
    service,_,_=make_service(mode='physical')
    action=next(a for a in service.view()['actions'] if a['action_id']=='record_first_motion_measurements')
    assert not next(f for f in action['fields'] if f['name']=='acknowledge_measured')['default']


def test_host_selects_only_successful_same_session_original(make_service):
    import time
    from rocell.application.first_motion_contract import REFERENCES, create_first_motion_request
    service,runner,_=make_service(mode='physical')
    operation=_run(service,'record_first_motion_measurements',values())
    report=operation['result']['steps'][0]['report']
    refs=dict.fromkeys(REFERENCES,'a'*64)
    refs['independent_posture_review_sha256']=report['original_sha256']
    now=time.monotonic_ns()
    request=create_first_motion_request(attempt_id='operation-'+'f'*32,
        usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        references=refs,independent_start_interval_deg=[-1,1],distal_radius_mm=175,
        issued_monotonic_ns=now,deadline_monotonic_ns=now+30_000_000_000)
    raw,association=service.select_first_motion_measurement(request=request,
        operation_id=operation['operation_id'])
    assert hashlib.sha256(raw).hexdigest()==report['original_sha256']
    assert not association['motion_authorized']
    assert service._endpoint_binding is None
    assert not runner.calls
    with pytest.raises(WizardError):
        service.select_first_motion_measurement(request=request,operation_id='operation-'+'e'*32)
    other,_,_=make_service(mode='physical')
    with pytest.raises(WizardError):
        other.select_first_motion_measurement(request=request,operation_id=operation['operation_id'])


@pytest.mark.parametrize('log_failure', [False, True])
def test_host_staging_uses_selected_original_and_reports_log_failure(make_service, monkeypatch, log_failure):
    """Exercise real receipt selection; the staging double cannot launch hardware."""
    import time
    import rocell.application.first_motion_staging as staging
    from rocell.application.first_motion_contract import REFERENCES, create_first_motion_request

    service, runner, _ = make_service(mode='physical')
    operation = _run(service, 'record_first_motion_measurements', values())
    report = operation['result']['steps'][0]['report']
    refs = dict.fromkeys(REFERENCES, 'a' * 64)
    refs['independent_posture_review_sha256'] = report['original_sha256']
    now = time.monotonic_ns()
    request = create_first_motion_request(
        attempt_id='operation-' + 'f' * 32,
        usb_identity={'vid': 0x10c4, 'pid': 0xea60, 'serial_number': 'A' * 32},
        references=refs, independent_start_interval_deg=[-1, 1], distal_radius_mm=175,
        issued_monotonic_ns=now, deadline_monotonic_ns=now + 30_000_000_000)
    calls = []
    staged_report = {'motion_authorized': False, 'physical_authority': False}

    def stage(workspace, actual_request, **kwargs):
        assert actual_request is request
        assert kwargs['root'] == service._log.root
        assert kwargs['session_id'] == service.session_id
        assert kwargs['operation_id'] == operation['operation_id']
        assert hashlib.sha256(kwargs['measurement_raw']).hexdigest() == report['original_sha256']
        assert kwargs['check_current']() is None
        calls.append(kwargs)
        return staged_report

    monkeypatch.setattr(staging, 'stage_first_motion_originals', stage)
    append = service._append_event
    monkeypatch.setattr(service, '_append_event',
        lambda name, data: False if log_failure and name == 'first_motion_evidence_staged' else append(name, data))
    if log_failure:
        with pytest.raises(WizardError, match='logging failed'):
            service.stage_first_motion_evidence(request=request,
                operation_id=operation['operation_id'], reference_originals={})
    else:
        assert service.stage_first_motion_evidence(request=request,
            operation_id=operation['operation_id'], reference_originals={}) == staged_report
    assert len(calls) == 1
    assert not runner.calls
    assert service._endpoint_binding is None
