"""Nominal endpoint-path checks against existing placemat geometry, no IK claims."""

import hashlib
import json

from rocell.models.frames import Point3Mm, Transform
from rocell.simulation.scene import NominalWorkcellScene
from .characterization_plan import FrozenCampaign, _number


def check_campaign_geometry(plan: FrozenCampaign, scene: NominalWorkcellScene,
                            board_T_plan: Transform | None, *, clearance_mm: float):
    """Bind nominal source geometry, explicit frame transform and clearance policy.

    All obstacles remain active: this is a non-contact campaign. Straight
    endpoint segments are hypotheses, not proof of a controller's actual path.
    The scene/model frames must never be silently equated with R_ctrl.
    """
    if type(plan) is not FrozenCampaign or not isinstance(scene, NominalWorkcellScene):
        raise ValueError('Expected frozen campaign and nominal scene')
    clearance = _number(clearance_mm,'clearance_mm',positive=True)
    data = plan.to_dict()
    if board_T_plan is not None and (type(board_T_plan) is not Transform
            or board_T_plan.from_frame != data['frame'] or board_T_plan.to_frame != scene.board_frame):
        raise ValueError('Explicit plan-to-board frame mapping required')
    transform = None if board_T_plan is None else {
        'from_frame':board_T_plan.from_frame,'to_frame':board_T_plan.to_frame,
        'matrix':list(board_T_plan.matrix)}
    binding = {'scene':scene.to_dict(),'transform':transform,'clearance_mm':clearance}
    digest = hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    rows=[]
    if board_T_plan is not None:
        for trial in data['trials']:
            a,b = [board_T_plan.transform_point(Point3Mm(data['frame'],p['x_mm'],p['y_mm'],p['z_mm']))
                   for p in (trial['start'],trial['target'])]
            check=scene.check_segment_clearance(a,b,clearance_mm=clearance)
            rows.append({'trial_id':trial['trial_id'],'start_board_mm':[a.x,a.y,a.z],
                         'target_board_mm':[b.x,b.y,b.z],
                         'nominal_tip_clear':check.clear,'collisions':list(check.colliding_obstacle_ids),
                         'method':check.method})
    matches = digest == data['evidence']['geometry_sha256']
    if board_T_plan is None:
        status='TRANSFORM_REQUIRED'
    elif not matches:
        status='GEOMETRY_BINDING_MISMATCH'
    elif any(not row['nominal_tip_clear'] for row in rows):
        status='NOMINAL_TIP_COLLISION'
    else:
        status='NOMINAL_TIP_PATH_CLEAR_ONLY'
    return {'schema':'rocell.characterization_geometry.v1','status':status,
            'basis':'NOMINAL_PLACEMAT_STRAIGHT_ENDPOINT_SEGMENTS',
            'plan_sha256':plan.sha256,'geometry_sha256':digest,'plan_geometry_matches':matches,
            'scene_source_hashes':dict(scene.source_hashes),'transform':transform,
            'clearance_mm':clearance,'trial_checks':rows,
            'board_size_mm':[scene.board.maximum.x-scene.board.minimum.x,
                             scene.board.maximum.y-scene.board.minimum.y,
                             scene.board.maximum.z-scene.board.minimum.z],
            'obstacle_count':len(scene.obstacles),
            'ik':'UNKNOWN','full_link_clearance':'UNKNOWN','cable_clearance':'UNKNOWN',
            'actual_controller_path':'UNQUALIFIED','physical_ready':False,'motion_authorized':False}
