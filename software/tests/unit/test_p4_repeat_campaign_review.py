from pathlib import Path
import pytest
from rocell.application.p4_repeat_campaign_review import review_p4_repeat_campaign

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'
SOURCE = ROOT/'runs/wizard-exports/wizard-20260924T182321443347Z-87b68bc4624a4e1b80c6fb0af4027e5e/attachment-large-pose-relief.hex.txt'
BOOT = '3ce87bcbe82e9ccdc6f8b46854e095b3'


def test_campaign_source_route_and_envelope():
    result = review_p4_repeat_campaign(bytes.fromhex(SOURCE.read_text()), expected_boot=BOOT, model_path=MODEL)
    assert result['maximum_writes'] == 12
    assert result['maximum_command_delta_counts'] == 65
    midpoint = [l for l in result['legs'] if l['target_wrist']==1947]
    assert [l['direction'] for l in midpoint] == [1,-1,1,-1]
    # The midpoint-to-low leg also permits 80 counts of transient travel.
    assert result['wrist_sweep_counts'] == [1947-12-80,1947+12+80]
    assert result['minimum_model_tcp_z_mm'] > 0
    assert result['minimum_model_capsule_clearance_mm'] > 0
    for leg in result['legs']:
        assert leg['maximum_write_attempts'] == 1
        assert leg['target_goals'][:4] == result['source_goals'][:4]
        assert leg['target_goals'][5:] == result['source_goals'][5:]
    assert not result['hardware_access']
    assert not result['movement_authorized']
    assert not result['native_campaign_implemented']


def test_wrong_boot_and_truncation_rejected():
    raw = bytes.fromhex(SOURCE.read_text())
    with pytest.raises(ValueError, match='identity mismatch'):
        review_p4_repeat_campaign(raw, expected_boot='ab'*16, model_path=MODEL)
    with pytest.raises(ValueError, match='framing'):
        review_p4_repeat_campaign(raw[:-1], expected_boot=BOOT, model_path=MODEL)


def test_changed_model_rejected(tmp_path):
    changed = tmp_path/'model.urdf'
    changed.write_bytes(MODEL.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='model differs'):
        review_p4_repeat_campaign(bytes.fromhex(SOURCE.read_text()), expected_boot=BOOT, model_path=changed)
