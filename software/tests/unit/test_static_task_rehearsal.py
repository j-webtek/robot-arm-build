"""Real static-source route and numerical solver; no hardware or legacy alias."""
import hashlib
import socket
import subprocess

import pytest
from test_static_simulation_context import workspace
from rocell.application.first_motion_contract import canonical
from rocell.application.static_simulation_context import load_static_simulation_context
from rocell.application.static_task_rehearsal import run_static_task_rehearsal


@pytest.fixture(autouse=True)
def no_device_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Static task rehearsal must not open network or subprocesses')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


@pytest.mark.parametrize('device', ['keyboard', 'phone'])
def test_static_task_real_geometry_and_ik_preserve_gaps(workspace, device):
    context = load_static_simulation_context(workspace)
    report = run_static_task_rehearsal(context, device=device, text='a')
    assert report['architecture'] == 'static_overhead_eye_to_hand'
    assert 'static-overhead' in report['profile_id']
    assert report['geometry']['all_checks_pass']
    assert report['status'] == 'SAMPLED_IK_GAPS'
    assert report['ik']['converged_count'] == 4
    assert report['ik']['sampled_tip_point_count'] == 5
    failures = [row for row in report['ik']['results'] if not row['converged']]
    assert len(failures) == 1 and failures[0]['phase'] == 'PARK'
    assert not report['hardware_access'] and not report['physical_authority']
    assert report['hardware_commands_generated'] == 0
    digest = report.pop('report_sha256')
    assert hashlib.sha256(canonical(report)).hexdigest() == digest
    assert report['bundle_sha256'] == context.bundle.source_sha256


@pytest.mark.parametrize('text', ['', 'abcdefghi', None, 1])
def test_rejects_unbounded_or_invalid_input(text):
    with pytest.raises(ValueError):
        run_static_task_rehearsal(None, device='keyboard', text=text)


def test_rejects_context_alias():
    with pytest.raises(TypeError):
        run_static_task_rehearsal(object(), device='keyboard', text='a')


@pytest.mark.parametrize('device', ['keyboard', 'phone'])
def test_explicit_park_overlay_passes_without_changing_frozen_inputs(workspace, device):
    context = load_static_simulation_context(workspace)
    before = {name: ref.path.read_bytes() for name, ref in context.bundle.artifacts.items()}
    report = run_static_task_rehearsal(context, device=device, text='a',
                                     park_xy_board_mm=(290., 40.))
    assert report['status'] == 'SAMPLED_CHECKS_PASS_NOT_EXECUTABLE'
    assert report['ik']['converged_count'] == report['ik']['sampled_tip_point_count'] == 5
    assert report['park_selection']['source'] == 'EXPLICIT_SIMULATION_OVERLAY'
    assert report['park_selection']['xy_board_mm'] == [290., 40.]
    assert not report['physical_authority']
    assert not report['park_selection']['installed_position_verified']
    assert context.scenario.path_policy.park_xy_board_mm == (305., 400.)
    assert before == {name: ref.path.read_bytes() for name, ref in context.bundle.artifacts.items()}


@pytest.mark.parametrize('point', [(-1., 40.), (611., 40.), (305., 300.),
                                 (120., 120.), (float('nan'), 40.), (True, 40.)])
def test_park_overlay_rejects_offboard_obstacle_tag_and_nonfinite(workspace, point):
    from rocell.application.trajectory_simulation import TrajectorySimulationError
    context = load_static_simulation_context(workspace)
    with pytest.raises((ValueError, TypeError, TrajectorySimulationError)):
        run_static_task_rehearsal(context, device='keyboard', text='a', park_xy_board_mm=point)


@pytest.mark.parametrize('device', ['keyboard', 'phone'])
def test_dense_route_checks_intermediate_points_and_seeds_in_order(workspace, device):
    context = load_static_simulation_context(workspace)
    report = run_static_task_rehearsal(context, device=device, text='a',
                                     park_xy_board_mm=(290., 40.), dense=True)
    route = report['dense_route']
    assert report['status'] == 'DENSE_SAMPLES_PASS_NOT_EXECUTABLE'
    batch = route['round']
    assert batch['evaluated_waypoint_count'] == batch['waypoint_count'] > 30
    assert all(row['distance_from_previous_mm'] <= 15.00000001 for row in batch['waypoints'])
    assert all(row['source_path_check_passed'] for row in batch['waypoints'])
    assert all(row['accepted'] and row['adjacent_joint_delta_passed']
               and row['solver_weighted_task_jacobian_numerical_rank_passed']
               for row in batch['joint_results'])
    assert all(row['previous_solution_seed_supplied'] for row in batch['joint_results'][1:])
    assert not route['physical_authority'] and not route['full_arm_collision_checked']
    assert not route['continuous_path_proven']


def test_dense_route_stops_at_failed_nominal_park(workspace):
    context = load_static_simulation_context(workspace)
    report = run_static_task_rehearsal(context, device='keyboard', text='a', dense=True)
    assert report['status'] == 'DENSE_ROUTE_FAILED'
    batch = report['dense_route']['round']
    assert batch['evaluated_waypoint_count'] == 1 < batch['waypoint_count']
    assert batch['failure_reason'] == 'IK_NO_CONVERGED_SOLUTION'
    assert not batch['all_waypoints_accepted']
    assert report['task_summary']['first_failure']['phase'] == 'PARK'


def test_eight_repeated_targets_are_not_collapsed(workspace):
    context = load_static_simulation_context(workspace)
    report = run_static_task_rehearsal(context, device='keyboard', text='aaaaaaaa',
                                     park_xy_board_mm=(290.,40.), dense=True)
    assert report['status'] == 'DENSE_SAMPLES_PASS_NOT_EXECUTABLE'
    summary = report['task_summary']
    assert summary['requested_target_count'] == 8
    assert summary['requested_targets'] == ['A'] * 8
    assert summary['planned_waypoint_count'] == summary['evaluated_waypoint_count'] == 108
    assert not summary['input_event_verification_performed']
    assert summary['first_failure'] is None


def test_word_failure_identifies_target_and_phase(workspace):
    context = load_static_simulation_context(workspace)
    report = run_static_task_rehearsal(context, device='keyboard', text='hello',
                                     park_xy_board_mm=(290.,40.), dense=True)
    summary = report['task_summary']
    assert summary['requested_targets'] == ['H','E','L','L','O']
    assert summary['first_failure']['target'] == 'keyboard:H'
    assert summary['first_failure']['phase'] == 'HOVER'
    assert summary['first_failure']['reason'] == 'IK_NO_CONVERGED_SOLUTION'
    assert summary['evaluated_waypoint_count'] < summary['planned_waypoint_count']


@pytest.mark.parametrize('length', [80., 100., 120.])
def test_tool_hypothesis_is_explicit_and_does_not_change_context(workspace, length):
    context = load_static_simulation_context(workspace)
    original = context.scenario
    report = run_static_task_rehearsal(context, device='keyboard', text='a',
                                     park_xy_board_mm=(290.,40.), tool_length_mm=length)
    assert context.scenario == original
    assert report['tool_selection']['hand_tcp_to_tip_z_mm'] == -length
    assert report['tool_selection']['source'] == 'EXPLICIT_SIMULATION_OVERLAY'
    assert not report['tool_selection']['installed_tool_verified']
    assert report['ik']['tool_case_id'] == f'explicit_nominal_tool_{length:g}mm'


@pytest.mark.parametrize('length', [True, 0, -100, 121, float('nan'), '100'])
def test_tool_hypothesis_rejects_unbounded_input(length):
    with pytest.raises(ValueError):
        run_static_task_rehearsal(None, device='keyboard', text='a', tool_length_mm=length)
