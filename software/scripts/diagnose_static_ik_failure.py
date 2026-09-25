"""Finite offline replay of one retained static-route failure; no motion IO."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from rocell.application.static_simulation_context import (
    load_static_simulation_context, static_simulation_context_hashes)
from rocell.application._pinned_model import load_pinned_urdf
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.geometry import JointPosition, Point3Mm
from rocell.kinematics import BoardToolTipTarget, IkOptions, RoArmM3NumericalIk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Existing diagnostic export directory')
    args = parser.parse_args()
    folder = args.input.resolve(strict=True)
    if not verify_export(folder)['valid']:
        raise ValueError('Original export failed integrity check')
    report = json.loads((folder/'attachment-static-task.json').read_text())
    if report.get('tool_selection', {}).get('source', 'NOMINAL') != 'NOMINAL':
        raise ValueError('This diagnostic replays nominal tool inputs only')
    workspace = Path(__file__).resolve().parents[2]
    context = load_static_simulation_context(workspace)
    if report['source_hashes'] != dict(static_simulation_context_hashes(context)):
        raise ValueError('Saved route does not match current static inputs')
    batch = report['dense_route']['round']
    results = batch['joint_results']
    if not results or results[-1]['accepted'] or results[-1]['failure_reason'] != 'IK_NO_CONVERGED_SOLUTION':
        raise ValueError('Expected a retained first IK failure')
    failure = results[-1]
    waypoint = batch['waypoints'][failure['waypoint_sequence']]
    target = BoardToolTipTarget(Point3Mm('board', *waypoint['point_board_mm']))
    seeds = () if len(results) == 1 else ({name: JointPosition.radians(value)
        for name,value in results[-2]['solution_arm_joint_positions_rad'].items()},)
    scenario = context.scenario
    model = load_pinned_urdf(scenario.model_path, scenario.model_sha256).model
    trials = []
    for attempts, iterations in ((scenario.ik_policy.max_attempts,
                                   scenario.ik_policy.max_iterations_per_attempt), (10,140), (16,280)):
        options = IkOptions(max_attempts=attempts, max_iterations_per_attempt=iterations)
        solver = RoArmM3NumericalIk(model=model, board_T_world=scenario.board_T_world,
            hand_tcp_to_tip_z_mm=scenario.hand_tcp_to_tip_z_mm,
            fixed_gripper_position=scenario.fixed_gripper_position,
            ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
            gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
            joint_bounds_rad=scenario.controller_joint_intersection_rad, options=options)
        solved = solver.solve(target, seed_joint_positions=seeds)
        trials.append(dict(options=asdict(options), result=solved.to_dict()))
    evidence = dict(schema='rocell.static_ik_failure_diagnostic.v1', input_export=str(folder),
        source_hashes=report['source_hashes'], waypoint=waypoint,
        trials=trials, hardware_access=False, physical_authority=False,
        conclusion='Finite numerical search only; nonconvergence is not proof of physical unreachability')
    exporter = WizardDiagnosticExporter((workspace/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt = exporter.export(dict(mode='simulation'), [],
        attachments={'ik-failure.json':json.dumps(evidence,allow_nan=False).encode()})
    print(json.dumps(dict(export=receipt['path'], trials=[dict(
        attempts=row['options']['max_attempts'], iterations=row['options']['max_iterations_per_attempt'],
        converged=row['result']['converged'], residual=row['result']['residual']) for row in trials])))


if __name__ == '__main__':
    main()
