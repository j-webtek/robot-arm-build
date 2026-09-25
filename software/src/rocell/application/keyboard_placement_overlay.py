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


def half_turn_keyboard(scene, targets):
    """Rotate nominal key centers 180 degrees within the keyboard footprint.

    This is a photo-estimate study, not an installed board registration.  A
    half-turn leaves the rectangular keyboard envelope unchanged, so the
    existing conservative obstacle AABB remains applicable.
    """
    original=scene.devices['keyboard']
    envelope=original.envelope
    minimum,maximum=envelope.minimum,envelope.maximum
    if not (minimum.x<maximum.x and minimum.y<maximum.y):
        raise ValueError('Keyboard envelope must have positive XY size')
    def point(p):
        return replace(p,x=minimum.x+maximum.x-p.x,
                       y=minimum.y+maximum.y-p.y)
    turned_targets=replace(targets,keyboard_targets={
        key:replace(region,center=point(region.center))
        for key,region in targets.keyboard_targets.items()})
    for region in turned_targets.keyboard_targets.values():
        p=region.center
        if not (minimum.x<=p.x<=maximum.x and minimum.y<=p.y<=maximum.y):
            raise ValueError('Rotated key leaves the keyboard envelope')
    turned_scene=replace(scene,assumptions=(*scene.assumptions,
        'Keyboard 180-degree photo estimate is simulation-only, not installed registration.'))
    selection=dict(schema='rocell.keyboard_half_turn_overlay.v1',
        rotation_deg=180, pivot_board_xy_mm=[(minimum.x+maximum.x)/2,
                                            (minimum.y+maximum.y)/2],
        source_target_sha256=targets.content_sha256,
        envelope=envelope.to_dict(), installed_position_verified=False,
        frozen_geometry_modified=False, fixture_geometry_relocated=False)
    selection['overlay_sha256']=hashlib.sha256(canonical(selection)).hexdigest()
    return turned_scene,turned_targets,selection


def photo_estimated_keyboard(scene, targets, estimate):
    """Place the nominal key layout using an offline, photo-estimated board pose.

    The keyboard obstacle is expanded by the study margin, while key centers
    remain hypotheses. This overlay must never be interpreted as calibration.
    """
    if (not isinstance(estimate, dict) or
            estimate.get('schema') != 'rocell.photo_keyboard_registration_estimate.v1' or
            estimate.get('status') != 'PHOTO_ESTIMATE_OFFLINE_NOT_MOTION_AUTHORITY' or
            estimate.get('motion_authorized') is not False or
            estimate.get('keyboard_registered') is not False or
            estimate.get('arm_board_transform_verified') is not False):
        raise ValueError('Photo estimate is not an offline-only registration result')
    margin=estimate.get('study_xy_margin_mm')
    if type(margin) not in (int,float) or not math.isfinite(margin) or not 10<=margin<=50:
        raise ValueError('Photo estimate requires a bounded study margin')
    pose=estimate.get('fitted_front_left_board_xy_mm')
    yaw=estimate.get('fitted_footprint_yaw_deg')
    if (type(pose) not in (tuple,list) or len(pose)!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in pose) or
            type(yaw) not in (int,float) or not math.isfinite(yaw)):
        raise ValueError('Photo estimate has no finite board pose')
    original=scene.devices['keyboard']
    source=original.envelope
    width=source.maximum.x-source.minimum.x
    depth=source.maximum.y-source.minimum.y
    theta=math.radians(yaw)
    c,s=math.cos(theta),math.sin(theta)
    corners=[(pose[0]+x*c-y*s,pose[1]+x*s+y*c)
             for x,y in ((0,0),(width,0),(width,depth),(0,depth))]
    xmin=min(x for x,_ in corners)-margin
    xmax=max(x for x,_ in corners)+margin
    ymin=min(y for _,y in corners)-margin
    ymax=max(y for _,y in corners)+margin
    envelope=replace(source,
        minimum=replace(source.minimum,x=xmin,y=ymin),
        maximum=replace(source.maximum,x=xmax,y=ymax))
    if not (scene.board.minimum.x<=xmin<xmax<=scene.board.maximum.x and
            scene.board.minimum.y<=ymin<ymax<=scene.board.maximum.y):
        raise ValueError('Photo-estimated keyboard with margin leaves board')
    estimated_keys=estimate.get('nominal_key_centers_board_xy_mm')
    if not isinstance(estimated_keys,dict) or set(estimated_keys)!=set(targets.keyboard_targets):
        raise ValueError('Photo-estimated keys differ from nominal target identities')
    mapped={}
    for name,region in targets.keyboard_targets.items():
        xy=estimated_keys[name]
        if (type(xy) not in (list,tuple) or len(xy)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in xy) or
                not xmin<=xy[0]<=xmax or not ymin<=xy[1]<=ymax):
            raise ValueError('Photo-estimated key leaves study envelope')
        mapped[name]=replace(region,center=replace(region.center,x=xy[0],y=xy[1]))
    devices=dict(scene.devices); devices['keyboard']=replace(original,envelope=envelope)
    studied_scene=replace(scene,devices=devices,obstacles=tuple(
        envelope if box.obstacle_id=='keyboard' else box for box in scene.obstacles),
        assumptions=(*scene.assumptions,
            'Photo-estimated keyboard pose is simulation-only; board-to-arm and TCP are unverified.'))
    studied_targets=replace(targets,keyboard_targets=mapped)
    selection=dict(schema='rocell.keyboard_photo_estimate_overlay.v1',
        photo_sha256=estimate['photo_sha256'],profile_sha256=estimate['profile_sha256'],
        source_target_sha256=targets.content_sha256,
        fitted_footprint_yaw_deg=yaw,study_xy_margin_mm=margin,
        conservative_envelope=envelope.to_dict(),
        installed_position_verified=False,arm_board_transform_verified=False,
        motion_authorized=False,frozen_geometry_modified=False,
        fixture_geometry_relocated=False)
    selection['overlay_sha256']=hashlib.sha256(canonical(selection)).hexdigest()
    return studied_scene,studied_targets,selection


def synthetic_model_keyboard(scene, targets, estimate):
    """Apply an image-model pose to the offline keyboard study only."""
    if (not isinstance(estimate, dict) or
            estimate.get('schema') != 'rocell.synthetic_model_keyboard_estimate.v1' or
            estimate.get('source') != 'SYNTHETIC_IMAGE_MODEL_PREDICTION' or
            estimate.get('motion_authorized') is not False or
            estimate.get('target_catalog_sha256') != targets.content_sha256):
        raise ValueError('Synthetic model estimate is not bound to static targets')
    for field in ('image_sha256', 'model_sha256'):
        value=estimate.get(field)
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError(f'Invalid {field}')
    center=estimate.get('center_board_xy_mm')
    yaw=estimate.get('yaw_rad')
    if (type(center) not in (tuple,list) or len(center)!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in center) or
            type(yaw) not in (int,float) or not math.isfinite(yaw)):
        raise ValueError('Synthetic model estimate has no finite pose')
    original=scene.devices['keyboard'].envelope
    midx=(original.minimum.x+original.maximum.x)/2
    midy=(original.minimum.y+original.maximum.y)/2
    c,s=math.cos(yaw),math.sin(yaw)
    def transform(x,y):
        dx,dy=x-midx,y-midy
        return [center[0]+c*dx-s*dy,center[1]+s*dx+c*dy]
    front_left=transform(original.minimum.x,original.minimum.y)
    photo_shape=dict(
        schema='rocell.photo_keyboard_registration_estimate.v1',
        status='PHOTO_ESTIMATE_OFFLINE_NOT_MOTION_AUTHORITY',
        motion_authorized=False,keyboard_registered=False,
        arm_board_transform_verified=False,study_xy_margin_mm=10,
        fitted_front_left_board_xy_mm=front_left,
        fitted_footprint_yaw_deg=math.degrees(yaw),
        nominal_key_centers_board_xy_mm={
            name:transform(region.center.x,region.center.y)
            for name,region in targets.keyboard_targets.items()},
        photo_sha256=estimate['image_sha256'],
        profile_sha256=targets.content_sha256)
    scene,targets,base=photo_estimated_keyboard(scene,targets,photo_shape)
    selection=dict(schema='rocell.synthetic_model_keyboard_overlay.v1',
        source='SYNTHETIC_IMAGE_MODEL_PREDICTION',
        image_sha256=estimate['image_sha256'],model_sha256=estimate['model_sha256'],
        source_target_sha256=estimate['target_catalog_sha256'],
        center_board_xy_mm=list(center),yaw_rad=yaw,
        study_xy_margin_mm=10,conservative_envelope=base['conservative_envelope'],
        installed_position_verified=False,arm_board_transform_verified=False,
        motion_authorized=False,frozen_geometry_modified=False)
    selection['overlay_sha256']=hashlib.sha256(canonical(selection)).hexdigest()
    return scene,targets,selection
