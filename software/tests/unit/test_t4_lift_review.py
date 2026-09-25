from pathlib import Path
import pytest
from rocell.application.t4_lift_review import review_t4_lift
from rocell.application.wizard_diagnostic_export import verify_export

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'
SOURCE = ROOT / 'runs/wizard-exports/wizard-20260924T000623600641Z-c2103044389a40f4a53461447c9b9ea8'
BOOT = 'f7af4364ee3b87335970ee6052674b12'


def source_record():
    assert verify_export(SOURCE)['valid']
    return bytes.fromhex((SOURCE / 'attachment-large-pose-relief.hex.txt').read_text())


def test_measured_source_and_shoulder_first_order():
    review = review_t4_lift(source_record(), expected_boot=BOOT, model_path=MODEL)
    assert review['source_positions'] == [2047,2291,1825,2780,1850,2041,2047]
    command = review['next_command']
    assert command['servo_ids'] == [12,13]
    assert command['targets'] == [2217,1897]
    assert command['target_minus_measured_position_counts'] == [-74,72]
    assert command['maximum_writes'] == 1
    assert review['shoulder_first_tcp_mm'][2] > review['start_tcp_mm'][2] + 18
    assert review['wrist_first_tcp_mm'][2] < review['start_tcp_mm'][2] - 4
    assert review['first_step_full_travel']['samples'] == 161
    assert review['independent_progress']['samples'] == 1681
    assert review['first_step_full_travel']['minimum_tcp_z_mm'] == pytest.approx(review['start_tcp_mm'][2])
    assert review['first_step_full_travel']['minimum_capsule_clearance_mm'] > 25
    for flag in ('hardware_access','movement_authorized','physical_clearance_verified',
                 'retry_allowed','automatic_wrist_follow_on'):
        assert review[flag] is False


def test_wrong_boot_rejected():
    with pytest.raises(ValueError, match='identity mismatch'):
        review_t4_lift(source_record(), expected_boot='ab'*16, model_path=MODEL)


def test_truncated_record_rejected():
    with pytest.raises(ValueError, match='framing'):
        review_t4_lift(source_record()[:-1], expected_boot=BOOT, model_path=MODEL)
