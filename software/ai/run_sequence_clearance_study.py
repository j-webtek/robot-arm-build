"""Explore ordered synthetic targets at three explicit hover clearances."""
import copy
import json
from pathlib import Path
import sys

AI_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(AI_DIR), str(AI_DIR.parent / 'src')]
from run_keyboard_route_coverage import proposals
from rocell_ai.motion_sequence_simulation import run
from rocell_ai.scene_observation import canonical_hash


def summarize(report):
    route = report['dense_route']
    batch = route.get('round') or {}
    failed = next((r for r in batch.get('joint_results', []) if not r['accepted']), None)
    core = {k: v for k, v in report.items() if k not in ('schema', 'geometry', 'dense_route', 'sequence_sha256')}
    core.update(
        schema='rocell.ai_sequence_simulation_summary.v0',
        source_sequence_sha256=report['sequence_sha256'],
        geometry_report_sha256=canonical_hash(report['geometry']),
        geometry_all_checks_pass=report['geometry']['all_checks_pass'],
        dense_route_sha256=canonical_hash(route),
        dense_route_status=route['status'],
        dense_route_all_waypoints_accepted=route['all_waypoints_accepted'],
        evaluated_waypoint_count=batch.get('evaluated_waypoint_count'),
        first_failure=failed,
    )
    return {**core, 'summary_sha256': canonical_hash(core)}


def study(workspace: Path):
    catalog = {p['target_id']: p for p in proposals(workspace)}
    rows = []
    for keys in [('H','I'), ('H','H'), ('A','Z'), ('1','SPACE','ENTER')]:
        for clearance in (12.0, 25.0, 40.0):
            values = [copy.deepcopy(catalog[key]) for key in keys]
            for index, value in enumerate(values):
                value['proposal_id'] += f'-{index}-clearance-{clearance:g}'
                value['approach_clearance_mm'] = clearance
            report = run(values, workspace=workspace)
            rows.append(summarize(report))
            print(keys, clearance, report['dense_route']['status'], flush=True)
    core = {'schema': 'rocell.ai_sequence_clearance_study.v0', 'cases': rows,
            'case_count': len(rows), 'passing_count': sum(r['dense_route_all_waypoints_accepted'] for r in rows),
            'physical_execution_authorized': False, 'hardware_writes': 0}
    return {**core, 'study_sha256': canonical_hash(core)}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(AI_DIR.parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True)+'\n').encode())
