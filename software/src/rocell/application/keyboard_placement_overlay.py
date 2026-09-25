"""Translate the nominal keyboard and its targets together, never frozen files."""
import math
from dataclasses import replace
import hashlib
from .first_motion_contract import canonical


def translate_keyboard(scene, targets, offset):
    if (type(offset) not in (tuple,list) or len(offset)!=2 or any(
            type(v) not in (int,float) or not math.isfinite(v) or abs(v)>50 for v in offset)):
        raise ValueError('Keyboard overlay requires two finite offsets within +/-50 mm')
    dx,dy=offset
    def point(p): return replace(p,x=p.x+dx,y=p.y+dy)
    original=scene.devices['keyboard']
    envelope=replace(original.envelope,minimum=point(original.envelope.minimum),
                     maximum=point(original.envelope.maximum))
    if not (scene.board.minimum.x<=envelope.minimum.x<=envelope.maximum.x<=scene.board.maximum.x
            and scene.board.minimum.y<=envelope.minimum.y<=envelope.maximum.y<=scene.board.maximum.y):
        raise ValueError('Translated keyboard leaves the nominal board envelope')
    devices=dict(scene.devices); devices['keyboard']=replace(original,envelope=envelope)
    shifted_scene=replace(scene,devices=devices,obstacles=tuple(
        envelope if box.obstacle_id=='keyboard' else box for box in scene.obstacles),
        assumptions=(*scene.assumptions,'Keyboard translation is a simulation overlay, not fixture placement.'))
    shifted_targets=replace(targets,keyboard_targets={
        key:replace(region,center=point(region.center)) for key,region in targets.keyboard_targets.items()})
    selection=dict(schema='rocell.keyboard_placement_overlay.v1',translation_board_xy_mm=list(offset),
        source_target_sha256=targets.content_sha256,rotation_rad=0,scale=1,
        envelope= envelope.to_dict(),installed_position_verified=False,frozen_geometry_modified=False,
        fixture_geometry_relocated=False)
    selection['overlay_sha256']=hashlib.sha256(canonical(selection)).hexdigest()
    return shifted_scene,shifted_targets,selection
