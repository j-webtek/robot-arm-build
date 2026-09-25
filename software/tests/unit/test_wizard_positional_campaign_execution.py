"""Real final-click/collector/export composition with fake metadata and serial.

The process owner is replaced explicitly: this does not qualify Win32 process
containment or demonstrate any physical motion.
"""
from dataclasses import replace
import math
import os
from pathlib import Path
import pytest

from rocell.application import wizard_positional_campaign_coordinator as coordinator
from rocell.application.positional_campaign_native_retention import publish_campaign_process_result
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows import positional_campaign_bootstrap as bootstrap
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.positional_campaign_child_execution import _execute_authenticated_campaign_child
from rocell.providers.windows.positional_campaign_process_codec import prepare_owned_request
from rocell.providers.windows.positional_campaign_native_protocol import decode_request, validate_payload
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.positional_campaign_authority import BOUNDED_CHECKS
from test_positional_campaign_child_execution import prepared as fake_serial
from test_endpoint_current_context import fixture as endpoint_fixture
from test_wizard_positional_campaign_native import inputs


@pytest.mark.parametrize('mode', ['complete', 'miss', 'cancel', 'start_mismatch'])
@pytest.mark.parametrize('synchronize',[False,True])
@pytest.mark.parametrize('base_magnitude',[0,1,2])
@pytest.mark.parametrize('targets_deg', [(4,0), (-4,0), (2,0), (0,2), (2,4), (2,), (4,), (1,), (-1,)])
def test_final_click_through_actual_collector_and_portable_export(tmp_path, monkeypatch, mode, targets_deg,synchronize,base_magnitude,base_experiment=None,direction='INCREASING',base_sequence=False,fault_leg=1,base_speed=False,roll=False):
    if base_magnitude in (0,2) and (not synchronize or targets_deg not in ((1,),(-1,))):
        pytest.skip('Two-degree profile is synchronized base-only')
    if synchronize and targets_deg not in ((1,),(-1,)):
        pytest.skip('Synchronization is base-only')
    fixture_root = tmp_path/'incapable-kernel'
    fixture_root.mkdir()
    corrected=targets_deg==(2,)
    base=targets_deg in ((1,),(-1,))
    start_angle = math.radians(3.779296882) if corrected else math.radians(-1) if targets_deg[0]==0 else 0.
    if targets_deg==(4,):start_angle=math.radians(2.021484368)
    if base_experiment:start_angle=.018407769 if direction=='DECREASING' else .007669904
    if base_sequence:start_angle=.007669904
    initial_pose=None
    if roll:
        from test_roll_mapping_campaign import roll_body
        initial_pose=roll_body()['start_joints_rad'];start_angle=initial_pose[4]
        if roll=='fixed':
            from test_roll_fixed_campaign import fixed_roll_body
            initial_pose=fixed_roll_body(1 if direction=='INCREASING' else -1)['start_joints_rad']
            start_angle=initial_pose[4]
        if roll in ('long_fixed','framed'):
            from test_roll_long_fixed_campaign import long_fixed_body
            initial_pose=long_fixed_body(1 if direction=='INCREASING' else -1)['start_joints_rad']
            start_angle=initial_pose[4]
        if roll=='variation':
            from test_roll_variation_native import variation_body
            initial_pose=variation_body('nominal' if direction=='INCREASING' else 'return-nominal')['start_joints_rad']
            start_angle=initial_pose[4]
    _, _, kernel, cancellation, clock = fake_serial(fixture_root, monkeypatch, mode, start_angle=start_angle,
        response_target_rad=(lambda c:.018407769 if c['rad']>0 else .007669904) if base_sequence else math.radians(.4 if direction=='DECREASING' else 1) if base_experiment else math.radians(2) if corrected else None,selected_axis=4 if roll else 0 if base else 3,
        initial_prefix=b'}\r\n' if synchronize else b'',fault_leg=fault_leg,initial_pose=initial_pose)
    root, exports = tmp_path/'session', tmp_path/'exports'
    root.mkdir()
    exports.mkdir()
    workspace = Path(__file__).resolve().parents[3]
    configuration = inputs()
    configuration['start_joints_rad'][0 if base else 3] = start_angle
    if mode=='start_mismatch':
        configuration['start_joints_rad'][3 if base else 0] = math.radians(1)
    configuration['targets_rad'] = [math.radians(v) for v in targets_deg]
    if corrected:
        from test_model_corrected_native_campaign import model_inputs
        configuration=model_inputs(monkeypatch,configuration)
    stage=coordinator.stage_model_corrected_campaign if corrected else coordinator.stage_positional_campaign
    if base:
        configuration.pop('targets_rad')
        configuration['delta_deg']=targets_deg[0]*base_magnitude
        configuration['synchronize']=synchronize
        stage=coordinator.stage_base_mapping_probe
        if base_magnitude==0:
            configuration.pop('delta_deg');configuration.pop('synchronize')
            configuration['target_name']='positive-midpoint' if targets_deg[0]>0 else 'negative-midpoint'
            stage=coordinator.stage_base_midpoint_probe
    if base_experiment:
        from test_base_compensation_campaign import staging_inputs
        configuration.pop('delta_deg');configuration.pop('synchronize')
        configuration['targets_rad']=[math.radians(1)]
        configuration=staging_inputs(monkeypatch,configuration,base_experiment,direction)
        stage=coordinator.stage_base_compensation_experiment
        if base_speed:
            configuration.pop('experiment_kind')
            stage=coordinator.stage_base_speed_experiment
    if base_sequence:
        from test_base_compensation_campaign import proposal
        from rocell.application.base_correction_proposal import BaseCorrectionProposal
        from rocell.application.first_motion_contract import canonical
        import hashlib
        configuration.pop('delta_deg');configuration.pop('synchronize')
        refs={k:hashlib.sha256(v).hexdigest() for k,v in configuration['originals'].items()}
        for name,d in [('propose_base_correction','INCREASING'),('propose_decreasing_base_correction','DECREASING')]:
            monkeypatch.setattr('rocell.application.base_correction_proposal.'+name,
                lambda *a,d=d,**kw:BaseCorrectionProposal(canonical(proposal(kw['start_joints_rad'],refs,d))))
        configuration.update(model_raw=b'fixture',expected_model_sha256='f'*64,training_exports=[],held_out=[])
        stage=coordinator.stage_base_alternating_sequence
    if roll:
        configuration.pop('delta_deg');configuration.pop('synchronize')
        configuration['start_joints_rad']=list(initial_pose)
        if mode=='start_mismatch':configuration['start_joints_rad'][0]+=.001
        configuration['direction']=direction
        if roll=='framed':configuration['framed']=True
        stage=coordinator.stage_roll_long_fixed_probe if roll in ('long_fixed','framed') else coordinator.stage_roll_persistence_probe if roll=='persistence' else coordinator.stage_roll_fixed_probe if roll=='fixed' else coordinator.stage_roll_mapping_probe
        if roll=='variation':
            configuration.pop('direction')
            configuration['case_id']='nominal' if direction=='INCREASING' else 'return-nominal'
            stage=coordinator.stage_roll_target_variation
    staged = stage(workspace, root=root, session_id='wizard-'+'a'*32, **configuration)
    authority = BenchReviewAuthority(b'k'*32).for_positional_campaign()
    monkeypatch.setattr(bench_review_key, 'load_host_positional_campaign_review_authority', lambda _: authority)
    monkeypatch.setattr(bootstrap, 'load_host_positional_campaign_review_authority', lambda _: authority)
    _, snapshots, _, _ = endpoint_fixture()
    def metadata(**kwargs):
        return lambda: replace(snapshots[0], started_monotonic_ns=clock[0], finished_monotonic_ns=clock[0])
    monkeypatch.setattr(bootstrap, 'WindowsControllerMetadataAcquirer', metadata)
    calls = []
    def incapable_process(registration, payload, **kwargs):
        calls.append(payload)
        _, raw = prepare_owned_request(registration, payload)
        reader = bootstrap.prepare_authenticated_campaign_reader(workspace, raw,
            cancellation=cancellation, clock_ns=lambda: clock[0])
        started = clock[0]
        compact = _execute_authenticated_campaign_child(raw, reader,
            cancellation=cancellation, clock_ns=lambda: clock[0])
        receipt = OwnedWorkerResult('SUCCEEDED', None, (), decode_request(raw)['request_sha256'],
            reader.request.to_dict()['campaign_id'], True, True, True, 0,
            clock[0]-started, len(raw), 10, 1, compact, b'',
            owned_process_id=os.getpid(), finished_monotonic_ns=clock[0])
        path, report = publish_campaign_process_result(root, validate_payload(payload),
            request_original=raw, receipt=receipt)
        checked = verify_native_retained_export(root, path.name)
        return dict(status='ENDPOINTS_REPORTED_COMPLETE' if report['endpoint_reported_complete'] else 'HELD',
            report_file=path.name, report_sha256=checked['report_sha256'], export_verified=checked['valid'],
            endpoint_diagnostics=checked['endpoint_diagnostics'])
    monkeypatch.setattr(coordinator, 'run_campaign_process', incapable_process)
    outcome = coordinator.run_staged_positional_campaign(workspace, staged,
        operator_id='test-operator', checks=dict.fromkeys(BOUNDED_CHECKS,True),
        accepted_ns=1_000_000_000, cancellation=cancellation, export_root=exports,
        check_current=lambda: None, clock_ns=lambda: clock[0])
    assert len(calls) == 1
    if base_speed:
        assert staged.preview()['experiment_kind']=='SPEED_CANDIDATE'
        assert staged.preview()['experiment_direction']==direction
        assert staged.preview()['limits']['spd']==10


    assert len(kernel.writes) == ((4 if base_sequence else len(targets_deg)) if mode=='complete' else 0 if mode=='start_mismatch' else fault_leg)
    assert kernel.closed == [202,201,101]
    assert (outcome['status']=='ENDPOINTS_REPORTED_COMPLETE') == (mode=='complete')
    portable = Path(outcome['export_directory'])
    assert verify_native_retained_export(portable, outcome['report_file'])['valid']
    assert not list(portable.glob('*-native-child'))  # No executable packages in export.
    cancellation.clear()
    with pytest.raises((ValueError,RuntimeError,OSError)):
        coordinator.run_staged_positional_campaign(workspace, staged,
            operator_id='test-operator', checks=dict.fromkeys(BOUNDED_CHECKS,True),
            accepted_ns=clock[0], cancellation=cancellation, export_root=exports,
            check_current=lambda: None, clock_ns=lambda: clock[0])
    assert len(calls) == 1


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_base_experiment_final_click_collector_export_and_no_replay(tmp_path,monkeypatch,kind,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,base_experiment=kind,direction=direction)


@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('leg',[1,2,3,4])
def test_sequence_final_click_native_collector_export_and_no_replay(tmp_path,monkeypatch,mode,leg):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,base_sequence=True,fault_leg=leg)


@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_speed_final_click_native_collector_export_and_no_replay(tmp_path,monkeypatch,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,base_experiment='CORRECTED',
        direction=direction,base_speed=True)


@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_roll_final_click_native_collector_export_no_replay(tmp_path,monkeypatch,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,direction=direction,roll=True)


@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_roll_fixed_final_click_export_no_replay(tmp_path,monkeypatch,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,direction=direction,roll='fixed')


@pytest.mark.parametrize('mode', ['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction', ['INCREASING','DECREASING'])
def test_roll_persistence_wizard_execution(tmp_path,monkeypatch,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,direction=direction,roll='persistence')


@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_roll_long_fixed_wizard_execution(tmp_path,monkeypatch,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,direction=direction,roll='long_fixed')


@pytest.mark.parametrize('mode',['complete','miss','cancel','start_mismatch'])
@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_roll_framed_wizard_execution(tmp_path,monkeypatch,mode,direction):
    test_final_click_through_actual_collector_and_portable_export(
        tmp_path,monkeypatch,mode,(1,),True,1,direction=direction,roll='framed')
