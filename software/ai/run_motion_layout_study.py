"""Compare four explicit setup hypotheses for one saved coordinate proposal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

AI_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(AI_DIR), str(AI_DIR.parent / 'src')]

from rocell_ai.motion_assurance import load
from rocell_ai.model_motion_simulation import run
from rocell_ai.scene_observation import canonical_hash


def study(proposal: object, workspace: Path) -> dict:
    rows = []
    for name, park, layout in (
        ('nominal', None, None),
        ('park_only', (290.0, 10.0), None),
        ('rank1_layout_only', None, workspace / 'software/config/virtual_commissioning_profile.json'),
        ('rank1_layout_and_park', (290.0, 10.0), workspace / 'software/config/virtual_commissioning_profile.json'),
    ):
        result = run(proposal, workspace=workspace, park_xy_board_mm=park, robot_layout_profile=layout)
        rows.append({'case': name, 'report': result})
    core = {
        'schema': 'rocell.ai_model_motion_layout_study.v0',
        'cases': rows,
        'passing_cases': [row['case'] for row in rows if row['report']['dense_route_all_waypoints_accepted']],
        'physical_execution_authorized': False,
        'hardware_writes': 0,
        'limitations': [
            'One hand-authored contact proposal, not a model accuracy evaluation',
            'Rank-1 layout jointly changes base pose and tool length; their separate effects are not isolated',
            'Park coordinate and layout were drawn from an existing successful synthetic rehearsal',
            'Exploratory simulation only; no installed geometry, continuous collision proof, or physical input verification',
        ],
    }
    return {**core, 'study_sha256': canonical_hash(core)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(load(args.proposal), AI_DIR.parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    for row in result['cases']:
        report = row['report']
        print(row['case'], report['simulation_status'], report['evaluated_waypoint_count'], report['first_failure'])
