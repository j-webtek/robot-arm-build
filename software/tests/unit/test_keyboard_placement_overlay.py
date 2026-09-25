from pathlib import Path
import pytest
from rocell.application.static_simulation_context import load_static_simulation_context
from rocell.application.keyboard_placement_overlay import translate_keyboard


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
