"""Rehearse every nominal keyboard center using the fixed candidate layout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

AI_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(AI_DIR), str(AI_DIR.parent / 'src')]

from rocell.targets import load_nominal_target_catalog
from rocell_ai.model_motion_simulation import run
from rocell_ai.scene_observation import canonical_hash


def proposals(workspace: Path) -> list[dict]:
    catalog = load_nominal_target_catalog(workspace)
    rows = []
    for target_id, region in sorted(catalog.keyboard_targets.items()):
        rows.append({
            'schema': 'rocell.model_motion_proposal.v1',
            'proposal_id': f'synthetic-keyboard-coverage-{target_id}',
            'device': 'keyboard', 'target_id': target_id,
            'coordinate_frame': 'board',
            'target_mm': dict(x=region.center.x, y=region.center.y, z=region.center.z),
            'interaction': 'CONTACT', 'approach_clearance_mm': 25.0,
            'speed_class': 'SLOW', 'confidence': 1.0,
            'source': {
                'model_id': 'synthetic-nominal-catalog-generator-v0',
                'frame_id': 'synthetic-no-camera-capture',
                'image_sha256': canonical_hash({'synthetic_placeholder': True, 'target_catalog_sha256': catalog.content_sha256}),
            },
        })
    if not rows:
        raise ValueError('Keyboard catalog is empty')
    return rows


def study(workspace: Path, *, progress=None) -> dict:
    cases = []
    for proposal in proposals(workspace):
        report = run(proposal, workspace=workspace, park_xy_board_mm=(290.0, 10.0),
                     robot_layout_profile=workspace / 'software/config/virtual_commissioning_profile.json')
        cases.append({'target_id': proposal['target_id'], 'proposal': proposal, 'report': report})
        if progress is not None:
            progress(cases[-1])
    passing = [row['target_id'] for row in cases if row['report']['dense_route_all_waypoints_accepted']]
    blocked = [row['target_id'] for row in cases if not row['report']['dense_route_all_waypoints_accepted']]
    core = {
        'schema': 'rocell.ai_keyboard_route_coverage.v0',
        'target_count': len(cases), 'passing_count': len(passing), 'blocked_count': len(blocked),
        'passing_targets': passing, 'blocked_targets': blocked, 'cases': cases,
        'physical_execution_authorized': False, 'hardware_writes': 0,
        'limitations': [
            'Synthetic nominal key centers and confidence=1.0 are generator labels, not measured model predictions',
            'Image hash is an explicitly synthetic placeholder; no camera image was captured or processed',
            'Each route starts and ends at the same park; this does not evaluate inter-key transitions or typing cadence',
            'Base pose, 120 mm tool, and park (290,10) mm remain unmeasured hypotheses',
            'Sampled IK and route screening do not prove continuous full-arm collision clearance or physical key presses',
        ],
    }
    return {**core, 'coverage_sha256': canonical_hash(core)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(AI_DIR.parents[1], progress=lambda row: print(
        row['target_id'], row['report']['simulation_status'], row['report']['first_failure'], flush=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(f"Passed {result['passing_count']}/{result['target_count']}; blocked {result['blocked_count']}")
