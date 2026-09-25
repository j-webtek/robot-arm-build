from pathlib import Path
import pytest
from rocell.application.static_simulation_context import load_static_simulation_context
from rocell.application.keyboard_placement_overlay import (
    translate_keyboard, half_turn_keyboard, photo_estimated_keyboard)
from rocell.application.photo_keyboard_registration import estimate
import hashlib
import json


@pytest.fixture(scope='module')
def context():
    return load_static_simulation_context(Path(__file__).resolve().parents[3])


def test_translation_preserves_size_pitch_source_and_other_devices(context):
    scene,targets,record=translate_keyboard(context.scene,context.targets,(0,-20))
    original=context.scene.devices['keyboard'].envelope
    shifted=scene.devices['keyboard'].envelope
    assert shifted.maximum.x-shifted.minimum.x==original.maximum.x-original.minimum.x==315
    assert shifted.maximum.y-shifted.minimum.y==original.maximum.y-original.minimum.y==147
    assert targets.resolve('keyboard','A').center.y==context.targets.resolve('keyboard','A').center.y-20
    assert targets.resolve('keyboard','S').center.x-targets.resolve('keyboard','A').center.x==pytest.approx(19.05)
    assert scene.devices['phone']==context.scene.devices['phone']
    assert targets.phone_targets==context.targets.phone_targets
    assert targets.content_sha256==context.targets.content_sha256  # Source hash, overlay recorded separately.
    assert next(b for b in scene.obstacles if b.obstacle_id=='keyboard')==shifted
    assert record['scale']==1 and not record['installed_position_verified']
    assert context.scene.devices['keyboard'].envelope==original
    assert translate_keyboard(context.scene,context.targets,(0,-20))[2]==record


@pytest.mark.parametrize('offset',[(0,51),(float('nan'),0),(True,0),(0,),None])
def test_invalid_offsets_rejected(context,offset):
    with pytest.raises(ValueError): translate_keyboard(context.scene,context.targets,offset)


def test_photo_half_turn_preserves_footprint_and_reverses_key_rows(context):
    shifted_scene,shifted_targets,_=translate_keyboard(context.scene,context.targets,(0,-20))
    scene,targets,record=half_turn_keyboard(shifted_scene,shifted_targets)
    envelope=shifted_scene.devices['keyboard'].envelope
    a=shifted_targets.resolve('keyboard','A').center
    turned=targets.resolve('keyboard','A').center
    assert turned.x==pytest.approx(envelope.minimum.x+envelope.maximum.x-a.x)
    assert turned.y==pytest.approx(envelope.minimum.y+envelope.maximum.y-a.y)
    assert scene.devices==shifted_scene.devices
    assert scene.obstacles==shifted_scene.obstacles
    assert targets.phone_targets==shifted_targets.phone_targets
    assert targets.content_sha256==shifted_targets.content_sha256
    assert record['rotation_deg']==180 and not record['installed_position_verified']
    _,twice,_=half_turn_keyboard(scene,targets)
    assert twice.resolve('keyboard','A').center.x==pytest.approx(a.x)
    assert twice.resolve('keyboard','A').center.y==pytest.approx(a.y)


def test_photo_estimate_maps_keys_and_expands_obstacle_without_authorizing_motion(context):
    root=Path(__file__).resolve().parents[2]
    annotation=json.loads((root/'config/photo_keyboard_registration_20260925.json').read_text())
    profile_bytes=(root/'config/static_nominal_target_profiles.json').read_bytes()
    profile=json.loads(profile_bytes)['keyboard']
    result=estimate(annotation,profile,profile_sha256=hashlib.sha256(profile_bytes).hexdigest())
    scene,targets,record=photo_estimated_keyboard(context.scene,context.targets,result)
    assert targets.resolve('keyboard','B').center.x==pytest.approx(271.17,abs=0.01)
    assert targets.resolve('keyboard','B').center.y==pytest.approx(177.94,abs=0.01)
    assert scene.devices['keyboard'].envelope.minimum.x < 78.7
    assert scene.devices['keyboard'].envelope.maximum.x > 393.7
    assert scene.devices['phone']==context.scene.devices['phone']
    assert targets.phone_targets==context.targets.phone_targets
    assert not record['installed_position_verified'] and not record['motion_authorized']
    assert next(b for b in scene.obstacles if b.obstacle_id=='keyboard')==scene.devices['keyboard'].envelope
    with pytest.raises(ValueError,match='offline-only'):
        photo_estimated_keyboard(context.scene,context.targets,{**result,'motion_authorized':True})
