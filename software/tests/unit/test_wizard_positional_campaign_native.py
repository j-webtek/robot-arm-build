"""Wizard native-route plumbing with incapable execution, never live hardware."""
import json
import math
import pytest

from rocell.application import wizard_positional_campaign_coordinator as coordinator
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_reference_reader import ORIGINAL_FILES
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.safety.positional_campaign_authority import BOUNDED_CHECKS
from test_arrival_wizard_service import make_service, _ticket, _run, _complete
from test_endpoint_current_context import fixture as endpoint_fixture


def inputs():
    _, _, _, binding = endpoint_fixture()
    originals = {name: canonical(dict(fixture_only=name)) for name in ORIGINAL_FILES
        if name not in ('runtime_sha256', 'stop_qualification_sha256')}
    originals['native_controller_review_sha256'] = canonical(binding.to_dict())
    originals['bounded_motion_risk_sha256'] = canonical(dict(
        schema='rocell.attended_bounded_motion_risk.v1', operator_present=True,
        entire_accepted_motion_clear=True, no_contact=True, no_added_payload=True,
        accepted_goal_may_finish=True, software_cancel_is_not_physical_stop=True))
    return dict(usb_identity=dict(vid=0x10c4,pid=0xea60,serial_number='A'*32),
        start_joints_rad=[0.]*6, targets_rad=[math.radians(4),0.], originals=originals)


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_base_compensation_uses_wizard_review_slot(make_service,monkeypatch,kind,direction):
    from test_base_compensation_campaign import staging_inputs
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=staging_inputs(monkeypatch,inputs(),kind,direction)
    preview=service.configure_base_compensation_experiment(**args)
    assert preview['selected_joint']=='b' and preview['experiment_kind']==kind
    assert preview['experiment_direction']==direction
    assert len(preview['legs'])==1 and preview['limits']['maximum_writes']==1
    ticket=_ticket(service,'run_positional_campaign',dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    effects=' '.join(ticket['effects'])
    assert ('intended endpoint 0.400' if direction=='DECREASING' else 'intended endpoint 1.000') in effects
    command='-0.684826' if direction=='DECREASING' and kind=='CORRECTED' else '0.400000' if direction=='DECREASING' else '2.335749' if kind=='CORRECTED' else '1.000000'
    assert ('transmitted command '+command) in effects
    assert not runner.calls
    with pytest.raises(ValueError):service.configure_base_compensation_experiment(**args)


def test_fixed_midpoint_uses_wizard_review_slot(make_service,monkeypatch):
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=inputs();args.pop('targets_rad');args['target_name']='negative-midpoint'
    preview=service.configure_base_midpoint_probe(**args)
    assert preview['selected_joint']=='b' and len(preview['legs'])==1
    ticket=_ticket(service,'run_positional_campaign',dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    assert 'intended endpoint -0.709' in ' '.join(ticket['effects'])
    assert not runner.calls


def configure(service, monkeypatch):
    # Selected USB/power setup is a fixture. Runtime/original staging is real.
    monkeypatch.setattr(service, '_powered_setup_context', lambda: 'fixture-powered-context')
    return service.configure_positional_campaign(**inputs())


def test_staging_and_preview_do_not_open_or_sign(make_service, monkeypatch):
    service, runner, _ = make_service(mode='physical')
    preview = configure(service, monkeypatch)
    assert len(preview['legs']) == 2 and not preview['motion_authorized']
    assert not list(service._log.root.glob('*-positional-review.json'))
    assert not list(service._log.root.glob('*-positional-launch.json'))
    ticket = _ticket(service, 'run_positional_campaign',
        dict(operator_id='operator', **dict.fromkeys(BOUNDED_CHECKS,True)))
    assert len([line for line in ticket['effects'] if line.startswith('leg-')]) == 2
    assert not runner.calls
    # Browser-controlled commands/paths cannot enter the native action.
    with pytest.raises(ValueError):
        _ticket(service, 'run_positional_campaign', dict(operator_id='operator',
            **dict.fromkeys(BOUNDED_CHECKS,True), raw_command='{}'))


@pytest.mark.parametrize('completed', [True, False])
def test_wizard_start_outcome_export_and_no_replay(make_service, monkeypatch, completed):
    service, runner, _ = make_service(mode='physical')
    configure(service, monkeypatch)
    calls = []
    def incapable(workspace, staged, **kwargs):
        kwargs['check_current']()
        assert kwargs['checks'] == dict.fromkeys(BOUNDED_CHECKS,True)
        assert kwargs['accepted_ns'] > 0 and not kwargs['cancellation'].is_set()
        calls.append(staged)
        return dict(status='ENDPOINTS_REPORTED_COMPLETE' if completed else 'HELD',
            export_verified=True, endpoint_diagnostics=[dict(leg_id='leg-01',
            reported_endpoint_verified=completed)], fixture_only=True)
    monkeypatch.setattr(coordinator, 'run_staged_positional_campaign', incapable)
    ticket = _ticket(service, 'run_positional_campaign',
        dict(operator_id='operator', **dict.fromkeys(BOUNDED_CHECKS,True)))
    receipt = service.execute_action(ticket['ticket_id'])
    operation = _complete(service, receipt['operation_id'])
    assert operation['status'] == ('SUCCEEDED' if completed else 'FAILED'), json.dumps(operation)
    assert service.execute_action(ticket['ticket_id'])['operation_id'] == receipt['operation_id']
    assert len(calls) == 1 and not runner.calls
    action = next(a for a in service.view()['actions'] if a['action_id']=='run_positional_campaign')
    assert not action['enabled']
    exported = _run(service, 'export_logs')
    from pathlib import Path
    directory = Path(exported['result']['receipt']['path'])
    assert verify_export(directory)['valid']
    retained = json.loads((directory / ('attachment-result-'+receipt['operation_id'].removeprefix('operation-')+'.json')).read_bytes())
    assert retained['steps'][0]['report']['fixture_only']


def test_changed_power_context_prevents_start(make_service, monkeypatch):
    service, _, _ = make_service(mode='physical')
    configure(service, monkeypatch)
    ticket = _ticket(service, 'run_positional_campaign',
        dict(operator_id='operator', **dict.fromkeys(BOUNDED_CHECKS,True)))
    monkeypatch.setattr(service, '_powered_setup_context', lambda: 'changed')
    with pytest.raises(ValueError): service.execute_action(ticket['ticket_id'])
    assert service._positional_campaign_confirmation is None


def test_rehearsal_cannot_configure_native_campaign(make_service):
    service, _, _ = make_service()
    with pytest.raises(ValueError): service.configure_positional_campaign(**inputs())


def test_model_correction_uses_wizard_slot_and_displays_both_targets(make_service,monkeypatch):
    from test_model_corrected_native_campaign import model_inputs
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=inputs()
    args['start_joints_rad'][3]=math.radians(3.779296882)
    args=model_inputs(monkeypatch,args)
    preview=service.configure_model_corrected_campaign(**args)
    assert len(preview['legs'])==1 and preview['limits']['maximum_writes']==1
    ticket=_ticket(service,'run_positional_campaign',
        dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    effects=' '.join(ticket['effects'])
    assert 'intended endpoint 2.000' in effects and 'transmitted command 1.033203' in effects
    assert 'At most 1 wrist commands' in effects
    assert not runner.calls


@pytest.mark.parametrize('synchronize',[False,True])
@pytest.mark.parametrize('magnitude',[1,2])
def test_base_probe_preview_labels_axis_without_opening_hardware(make_service,monkeypatch,synchronize,magnitude):
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=inputs();args.pop('targets_rad');args['delta_deg']=magnitude;args['synchronize']=synchronize
    if magnitude==2 and not synchronize:
        with pytest.raises(ValueError):service.configure_base_mapping_probe(**args)
        assert not runner.calls
        return
    preview=service.configure_base_mapping_probe(**args)
    assert preview['selected_joint']=='b' and preview['legs'][0]['command']['joint']==1
    ticket=_ticket(service,'run_positional_campaign',
        dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    assert 'At most 1 base commands' in ' '.join(ticket['effects'])
    assert ('startup synchronization' in ' '.join(ticket['effects'])) is synchronize
    assert not runner.calls and not preview['motion_authorized']


def test_sequence_wizard_preview_contains_all_four_commands(make_service,monkeypatch):
    import hashlib
    from test_base_compensation_campaign import proposal
    from rocell.application.base_correction_proposal import BaseCorrectionProposal
    from rocell.application.first_motion_contract import canonical
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=inputs();args.pop('targets_rad');args['start_joints_rad'][0]=.007669904
    refs={k:hashlib.sha256(v).hexdigest() for k,v in args['originals'].items()}
    for name,d in [('propose_base_correction','INCREASING'),('propose_decreasing_base_correction','DECREASING')]:
        monkeypatch.setattr('rocell.application.base_correction_proposal.'+name,
            lambda *a,d=d,**kw:BaseCorrectionProposal(canonical(proposal(kw['start_joints_rad'],refs,d))))
    args.update(model_raw=b'fixture',expected_model_sha256='f'*64,training_exports=[],held_out=[])
    preview=service.configure_base_alternating_sequence(**args)
    assert len(preview['legs'])==4 and preview['experiment_direction']=='ALTERNATING'
    ticket=_ticket(service,'run_positional_campaign',dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    effects=' '.join(ticket['effects'])
    assert 'At most 4 base commands' in effects
    assert sum(e.startswith('leg-') and 'intended endpoint' in e for e in ticket['effects'])==4
    assert not runner.calls


def test_speed_wizard_labels_actual_speed_and_single_command(make_service,monkeypatch):
    from test_base_compensation_campaign import staging_inputs
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=staging_inputs(monkeypatch,inputs(),'CORRECTED')
    args.pop('experiment_kind')
    preview=service.configure_base_speed_experiment(**args)
    assert preview['experiment_kind']=='SPEED_CANDIDATE'
    ticket=_ticket(service,'run_positional_campaign',dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    assert 'At most 1 base commands; spd 10, acc 1' in ' '.join(ticket['effects'])
    assert not runner.calls


def test_roll_wizard_labels_correct_axis_and_no_compensation(make_service,monkeypatch):
    from test_roll_mapping_campaign import roll_body
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=inputs();args.pop('targets_rad')
    args.update(start_joints_rad=roll_body()['start_joints_rad'],direction='INCREASING')
    preview=service.configure_roll_mapping_probe(**args)
    assert preview['selected_joint']=='r' and preview['legs'][0]['command']['joint']==5
    ticket=_ticket(service,'run_positional_campaign',dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    assert 'At most 1 wrist roll commands; spd 20, acc 1' in ' '.join(ticket['effects'])
    assert not runner.calls
