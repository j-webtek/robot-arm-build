"""Synthetic localization probes conditioned on archived scene-quality decisions.

This is an offline study harness, never a current-frame motion admission API.
"""
from __future__ import annotations
import copy
from pathlib import Path

from rocell.application.model_motion_bridge import ModelMotionBridgeError
from .scene_observation import canonical_hash, validate_observation
from .motion_sequence_simulation import run


def replay_quality(row: dict) -> bool:
    scene = validate_observation(row['observation'])
    pixel = row['pixel_quality']
    if pixel.get('assessment_sha256') != canonical_hash({k:v for k,v in pixel.items() if k!='assessment_sha256'}):
        raise ValueError('Archived pixel assessment hash mismatch')
    if any(pixel.get(k) != scene[k] for k in ('frame_id', 'image_sha256')):
        raise ValueError('Archived scene and pixel frame binding mismatch')
    if type(pixel.get('accepted')) is not bool:
        raise ValueError('Archived quality decision must be Boolean')
    usable = not scene['abstain'] and pixel['accepted']
    if row.get('observed_usable') is not usable:
        raise ValueError('Archived quality decision inconsistent')
    return usable


def probe(row: dict, proposals: list[dict], *, workspace: Path, dx: float, dy: float,
          confidence: float = 1.0, simulate=run) -> dict:
    base = {'scene_case': row['case'], 'archived_observation_sha256': row['observation']['observation_sha256'],
            'offset_mm': [dx, dy], 'confidence': confidence, 'physical_execution_authorized': False,
            'hardware_writes': 0, 'route_run': False}
    if not replay_quality(row):
        return {**base, 'status': 'ARCHIVED_QUALITY_REJECTED', 'route': None}
    values = copy.deepcopy(proposals)
    for value in values:
        value['target_mm']['x'] += dx
        value['target_mm']['y'] += dy
        value['confidence'] = confidence
    try:
        report = simulate(values, workspace=workspace)
    except ModelMotionBridgeError as exc:
        return {**base, 'status': 'COORDINATE_BRIDGE_REJECTED', 'reason': str(exc), 'route': None}
    route = report['dense_route']
    batch = route.get('round') or {}
    return {**base, 'route_run': True,
            'status': 'SAMPLED_ROUTE_PASS' if route['all_waypoints_accepted'] else 'SAMPLED_ROUTE_BLOCKED',
            'route': {'sequence_sha256': report['sequence_sha256'], 'proposal_sha256': canonical_hash(values),
                      'dense_route_sha256': canonical_hash(route), 'status': route['status'],
                      'evaluated_waypoint_count': batch.get('evaluated_waypoint_count'),
                      'first_failure': next((r['failure_reason'] for r in batch.get('joint_results',[]) if not r['accepted']), None)}}
